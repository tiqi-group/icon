"""Inspect the experiment library through ICON.

A small CLI for exploring whatever experiment library ICON is configured to use. It drives
ICON's own :class:`ReconfigurableExperimentLibraryClient`, so it sees exactly what the
running server would: the configured client is instantiated from the ``experiment_library``
section of the ICON config and its metadata is loaded through the same code path.

Commands are grouped by what they inspect:

- ``experiments list`` - enumerate the experiments in the library.
- ``experiments show EXPERIMENT`` - full metadata for one experiment (class, constructor
  kwargs, device parameter groups, and its parameters grouped by display group).
- ``experiments metadata EXPERIMENT`` - readout metadata for one experiment.
- ``experiments instructions EXPERIMENT`` - generate the hardware instructions for one
  experiment.
- ``parameters list`` - enumerate every parameter and its metadata (optionally grouped by
  display group).
- ``parameters show PARAMETER`` - metadata for a single parameter.
- ``hardware`` - the setup hardware description reported by the library.

``EXPERIMENT`` / ``PARAMETER`` may be a full identifier or any unambiguous substring of one.
Every command supports ``--json`` for machine-readable output.

Connection and library configuration come from the ICON config (``get_config``); pass
``--config`` to point at a specific file. If the library is misconfigured, ICON falls back
to an empty library and the tool reports that.

``--experiment-path`` overrides which library is read: instead of the configured client,
the library is taken from that directory as-is (no clone, no revision checkout), which is
what you want while developing against a working tree.

Usage::

    python -m icon.cli.cmd_experiment_library experiments list
    python -m icon.cli.cmd_experiment_library experiments show MyExperiment
    python -m icon.cli.cmd_experiment_library parameters list --group
    python -m icon.cli.cmd_experiment_library parameters list --json
    python -m icon.cli.cmd_experiment_library hardware
    python -m icon.cli.cmd_experiment_library --experiment-path ../my_library experiments list
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

import click

from icon.cli.cmd_parameter_db import latest_values_from_dump
from icon.config.config import get_config, set_config_path
from icon.server.data_access.reconfigurable_experiment_library_client import (
    ReconfigurableExperimentLibraryClient,
)
from icon.server.data_access.repositories.parameters_repository import (
    ParametersRepository,
)

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from icon.server.api.models.experiment_dict import ExperimentDict
    from icon.server.api.models.parameter_metadata import (
        ParameterMetadata,
    )
    from icon.server.data_access.experiment_data import DatabaseValueType
    from icon.server.data_access.experiment_library_client import (
        ExperimentLibraryClient,
        ParameterMetadataDict,
    )

# Splits an experiment identifier into module path, class name and instance name (the
# instance name is the part in parentheses). Mirrors ExperimentIdentifier.from_str in
# icon.server.pre_processing.worker, kept local to avoid importing that heavy module here.
_EXPERIMENT_ID_RE = re.compile(
    r"^(?P<module>.*)\.(?P<cls>[^. ]+) \((?P<instance>[^)]+)\)$"
)

# The category the RF channels are reported under, and the label column of their
# detail block. The categories are built by `PyCrystalClient.get_setup_hardware_description`.
_RF_CATEGORY = "RFs"
_RF_LABEL_WIDTH = len("central frequency")

logger = logging.getLogger("experiment_library")

_T = TypeVar("_T")


def _experiment_path() -> Path | None:
    """Return the ``--experiment-path`` the CLI was invoked with, if any.

    The option lives on the group, so it is read from the root context rather than
    threaded through every command.
    """
    context = click.get_current_context(silent=True)
    if context is None:
        return None
    path: Path | None = context.find_root().params.get("experiment_path")
    return path


def _client() -> ExperimentLibraryClient:
    """Instantiate the client the library is inspected through.

    By default this is the client configured in the ``experiment_library`` section of
    the ICON config, so the tool sees exactly what the running server would. With
    ``--experiment-path`` the library is instead read straight from that directory.
    """
    experiment_path = _experiment_path()
    if experiment_path is not None:
        return _local_client(experiment_path)

    client = ReconfigurableExperimentLibraryClient()
    if not client.is_configured():
        logger.warning(
            "Experiment library is not configured; using the empty fallback library. "
            "Check the 'experiment_library' section of your ICON config.",
        )
    return client


def _local_client(experiment_path: Path) -> ExperimentLibraryClient:
    """Build a client reading the experiment library from a local working tree.

    The library still runs in its own interpreter, ``<experiment_path>/.venv``, exactly
    as it does in production, so a missing venv is reported here rather than as a failed
    subprocess later. The library package name keeps coming from the config, since
    ``--experiment-path`` overrides where the library is, not what it is called.
    """
    # Imported here, not at module level: pulling in pycrystal and the sequence
    # generator costs the better part of a second, and only this path needs them (the
    # configured client imports them itself, when it is loaded).
    from icon.cli.lib_experiment import LocalPyCrystalClient  # noqa: PLC0415

    interpreter = experiment_path / ".venv" / "bin" / "python3"
    if not interpreter.is_file():
        raise click.ClickException(
            f"{experiment_path} has no usable virtual environment: {interpreter} does "
            "not exist. The experiment library runs in its own venv - create it inside "
            "the library (e.g. `uv sync` or `python -m venv .venv`) and try again.",
        )

    module = get_config().experiment_library.client_args.get(
        "experiment_library_module", "experiment_library"
    )
    logger.info(
        "Reading the experiment library from %s (module '%s').", experiment_path, module
    )
    return LocalPyCrystalClient(
        checkout_path=str(experiment_path), experiment_library_module=module
    )


def _run(coro: Coroutine[Any, Any, _T], action: str) -> _T:
    """Run an async library call, turning failures into a clean CLI error.

    The configured library is user code (and may be broken or version-mismatched), so a
    failure is reported as a ``ClickException`` rather than a raw traceback. Pass ``-v``
    for the underlying exception and traceback.
    """
    try:
        return asyncio.run(coro)
    except Exception as exc:
        logger.debug("Failed to %s", action, exc_info=True)
        message = f"Failed to {action}: {exc}. Re-run with -v for the full traceback."
        raise click.ClickException(message) from exc


def _load_metadata(
    client: ExperimentLibraryClient | None = None,
) -> tuple[ExperimentDict, ParameterMetadataDict]:
    """Load ``(experiment_dict, parameter_metadata)`` through ICON's client.

    An experiment comes back as an ``ExperimentMetadata`` dataclass: `PyCrystalClient`
    builds them from the library metadata, and `deserialize_metadata` rebuilds them after
    they cross the venv boundary. The parameter metadata is a ``TypedDict``, so the
    commands below read experiments through attributes and parameters through keys.
    """
    client = client or _client()
    return _run(client.load_metadata(), "load experiment library metadata")


def _split_experiment_id(experiment_id: str) -> tuple[str, str]:
    """Return ``(exp_module_name, exp_instance_name)`` for an experiment identifier."""
    match = _EXPERIMENT_ID_RE.match(experiment_id)
    if match is None:
        raise click.ClickException(
            f"Cannot parse experiment identifier {experiment_id!r}.",
        )
    return match.group("module"), match.group("instance")


def _experiment_namespace(experiment_id: str) -> str:
    """Return the namespace under which an experiment's local parameters are stored.

    Mirrors ``str(ExperimentIdentifier)`` in :mod:`icon.server.pre_processing.worker`,
    which is what the server passes to the parameters repository.
    """
    match = _EXPERIMENT_ID_RE.match(experiment_id)
    if match is None:
        raise click.ClickException(
            f"Cannot parse experiment identifier {experiment_id!r}.",
        )
    return f"{match.group('module')}.{match.group('cls')}.{match.group('instance')}"


def _default_parameter_dict(
    parameter_metadata: ParameterMetadataDict,
) -> dict[str, DatabaseValueType]:
    """Build a ``{parameter_id: default_value}`` mapping from the parameter metadata."""
    parameter_dict: dict[str, DatabaseValueType] = {}
    for parameter_id, meta in parameter_metadata["all parameters"].items():
        parameter_dict[parameter_id] = meta["default_value"]
    return parameter_dict


def _influxdb_parameter_dict(
    parameter_metadata: ParameterMetadataDict,
    namespace: str,
) -> dict[str, DatabaseValueType]:
    """Build a parameter dict from InfluxDB, falling back to the library defaults.

    Mirrors what the pre-processing worker does before generating a sequence: the global
    parameter values are overlaid with the values stored for ``namespace`` (the
    experiment's own local parameters). Parameters absent from InfluxDB keep the default
    value from the library metadata, so the returned dict is always complete.
    """
    parameter_dict = _default_parameter_dict(parameter_metadata)
    influxdb_config = get_config().databases.influxdbv1
    logger.info(
        "Reading parameters from InfluxDB at %s:%d (database %r).",
        influxdb_config.host,
        influxdb_config.port,
        influxdb_config.database,
    )
    try:
        global_values = ParametersRepository.get_influxdb_parameters()
        local_values = ParametersRepository.get_influxdb_parameters(namespace=namespace)
    except Exception as exc:
        logger.debug("Failed to read the parameters from InfluxDB", exc_info=True)
        message = (
            f"Failed to read the parameters from InfluxDB: {exc}. Check the "
            "'databases.influxdbv1' section of your ICON config. Re-run with -v for "
            "the full traceback."
        )
        raise click.ClickException(message) from exc

    stored = {**global_values, **local_values}
    defaults_kept = sum(1 for key in parameter_dict if key not in stored)
    parameter_dict.update(stored)
    logger.info(
        "Read %d parameter value(s) from InfluxDB (%d global, %d local to '%s'); "
        "%d library parameter(s) kept their default value.",
        len(stored),
        len(global_values),
        len(local_values),
        namespace,
        defaults_kept,
    )
    return parameter_dict


def _dump_parameter_dict(
    parameter_metadata: ParameterMetadataDict,
    dump_file: str,
) -> dict[str, DatabaseValueType]:
    """Overlay the values of a parameter-database dump onto the library defaults.

    ``dump_file`` is a file written by ``icon-parameter-db dump``, in either format
    (``-`` reads stdin). When the dump holds a history, the newest value of each
    parameter wins. Parameters absent from the dump keep the default value from the
    library metadata, so the returned dict is always complete.
    """
    parameter_dict = _default_parameter_dict(parameter_metadata)
    stored = latest_values_from_dump(dump_file)
    defaults_kept = sum(1 for key in parameter_dict if key not in stored)
    parameter_dict.update(stored)
    logger.info(
        "Read %d parameter value(s) from the dump %s; %d library parameter(s) kept "
        "their default value.",
        len(stored),
        "stdin" if dump_file == "-" else dump_file,
        defaults_kept,
    )
    return parameter_dict


def _parameter_dict_for(
    parameter_metadata: ParameterMetadataDict,
    experiment_id: str,
    from_influxdb: bool,
    from_dump: str | None,
) -> tuple[dict[str, DatabaseValueType], str]:
    """Return ``(parameter_dict, source_name)`` for the requested parameter source."""
    if from_influxdb and from_dump is not None:
        raise click.UsageError(
            "--from-influxdb and --from-dump are mutually exclusive: pass the one "
            "source the parameters should come from.",
        )
    if from_dump is not None:
        return _dump_parameter_dict(parameter_metadata, from_dump), "dumped"
    if from_influxdb:
        namespace = _experiment_namespace(experiment_id)
        return _influxdb_parameter_dict(parameter_metadata, namespace), "InfluxDB"
    return _default_parameter_dict(parameter_metadata), "default"


def _prettify(sequence: str) -> str:
    """Pretty-print a JSON sequence string, falling back to the raw text."""
    try:
        return json.dumps(json.loads(sequence), indent=2)
    except (json.JSONDecodeError, TypeError):
        return sequence


def _json_default(obj: Any) -> Any:
    """Serialize dataclasses (e.g. ``ExperimentMetadata``) and fall back to ``str``."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    return str(obj)


def _dump_json(data: Any) -> None:
    """Print ``data`` as indented JSON."""
    click.echo(json.dumps(data, indent=2, default=_json_default))


def _compact(obj: Any) -> str:
    """Render a value on a single line for human-readable output."""
    return json.dumps(obj, default=str)


def _echo_parameter(parameter_id: str, meta: ParameterMetadata, indent: int) -> None:
    """Print one parameter's identifier and metadata block."""
    pad = " " * indent
    click.echo(f"{pad}{parameter_id}")
    click.echo(f"{pad}    display_name : {meta['display_name']}")
    click.echo(f"{pad}    unit         : {meta['unit'] or '-'}")
    click.echo(f"{pad}    default      : {meta['default_value']}")
    click.echo(f"{pad}    range        : [{meta['min_value']}, {meta['max_value']}]")
    if meta["allowed_values"] is not None:
        click.echo(f"{pad}    allowed      : {meta['allowed_values']}")


def _resolve_key(requested: str, available: dict[str, Any], kind: str) -> str:
    """Resolve ``requested`` to a key of ``available`` by exact or substring match.

    Raises ``click.ClickException`` when there is no match or the substring is ambiguous.
    """
    if requested in available:
        return requested
    candidates = sorted(key for key in available if requested in key)
    if not candidates:
        raise click.ClickException(
            f"No {kind} matching {requested!r}. Use `list_{kind}s` to see the options.",
        )
    if len(candidates) > 1:
        listing = "\n".join(f"  {candidate}" for candidate in candidates)
        raise click.ClickException(
            f"{requested!r} matches multiple {kind}s:\n{listing}",
        )
    return candidates[0]


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Path to the ICON config file to use (defaults to $ICON_CONFIG, else "
    "~/.config/icon/config.yaml).",
)
@click.option(
    "--experiment-path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Read the experiment library from this directory instead of the client "
    "configured in the ICON config. The directory is used as-is - no clone, no revision "
    "checkout - and the library runs in its own '<PATH>/.venv'.",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
def cli(
    config_path: Path | None,
    experiment_path: Path | None,  # noqa: ARG001 - read from the context by `_client`
    verbose: bool,
) -> None:
    """Inspect the experiment library ICON is configured to use."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    if config_path is not None:
        set_config_path(config_path)


@cli.group()
def experiments() -> None:
    """Inspect the experiments in the library."""


@cli.group()
def parameters() -> None:
    """Inspect the parameters in the library."""


@experiments.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="Emit the full metadata as JSON.")
def list_experiments(as_json: bool) -> None:
    """Enumerate the experiments in the library."""
    experiments, _ = _load_metadata()
    label_width = 25
    if as_json:
        _dump_json(experiments)
        return
    if not experiments:
        click.echo("No experiments found.")
        return
    for experiment_id, meta in experiments.items():
        num_parameters = sum(len(group) for group in meta.parameters.values())
        click.echo(experiment_id)
        click.echo(f"    {'class':<{label_width}} : {meta.class_name}")
        if meta.constructor_kwargs:
            click.echo(
                f"    {'constructor kwargs':<{label_width}} : {_compact(meta.constructor_kwargs)}"
            )
        click.echo(
            f"    {'parameter groups':<{label_width}} : {len(meta.parameters)} "
            f"({num_parameters} parameter(s))"
        )
        click.echo(
            f"    {'device parameter groups':<{label_width}} : {len(meta.device_parameter_groups)} "
        )
    click.echo("")
    click.echo(f"{len(experiments)} experiment(s).")


@experiments.command(name="show")
@click.argument("experiment")
@click.option("--json", "as_json", is_flag=True, help="Emit the full metadata as JSON.")
def show_experiment(experiment: str, as_json: bool) -> None:
    """Show full metadata for one EXPERIMENT (full id or unambiguous substring)."""
    experiments, _ = _load_metadata()
    key = _resolve_key(experiment, experiments, "experiment")
    meta = experiments[key]
    if as_json:
        _dump_json({key: meta})
        return

    click.echo(f"Experiment: {key}")
    click.echo(f"  class_name         : {meta.class_name}")
    click.echo(f"  constructor_kwargs : {_compact(meta.constructor_kwargs)}")
    if meta.device_parameter_groups:
        click.echo(
            f"  device_parameter_groups: {_compact(meta.device_parameter_groups)}"
        )
    click.echo("  parameters:")
    if not meta.parameters:
        click.echo("    (none)")
    for group, params in meta.parameters.items():
        click.echo(f"    [{group}]")
        for parameter_id, parameter_meta in params.items():
            _echo_parameter(parameter_id, parameter_meta, indent=6)


@parameters.command(name="list")
@click.option(
    "--group",
    is_flag=True,
    help="Organize the output by display group instead of a flat list.",
)
@click.option("--json", "as_json", is_flag=True, help="Emit the full metadata as JSON.")
def list_parameters(group: bool, as_json: bool) -> None:
    """Enumerate every parameter and its metadata."""
    _, parameter_metadata = _load_metadata()
    if as_json:
        _dump_json(parameter_metadata)
        return

    if group:
        _list_parameters_grouped(parameter_metadata)
        return

    all_parameters = parameter_metadata["all parameters"]
    if not all_parameters:
        click.echo("No parameters found.")
        return
    for parameter_id, meta in all_parameters.items():
        _echo_parameter(parameter_id, meta, indent=0)
    click.echo("")
    click.echo(f"{len(all_parameters)} parameter(s).")


def _list_parameters_grouped(parameter_metadata: ParameterMetadataDict) -> None:
    """Print parameters organized by display group."""
    groups = parameter_metadata["display groups"]
    if not groups:
        click.echo("No parameters found.")
        return
    total = 0
    for group_name, params in groups.items():
        click.echo(f"[{group_name}]")
        for parameter_id, meta in params.items():
            _echo_parameter(parameter_id, meta, indent=2)
            total += 1
    click.echo("")
    click.echo(f"{total} parameter(s) in {len(groups)} group(s).")


@parameters.command(name="show")
@click.argument("parameter")
@click.option("--json", "as_json", is_flag=True, help="Emit the metadata as JSON.")
def show_parameter(parameter: str, as_json: bool) -> None:
    """Show metadata for one PARAMETER (full id or unambiguous substring)."""
    _, parameter_metadata = _load_metadata()
    all_parameters = parameter_metadata["all parameters"]
    key = _resolve_key(parameter, all_parameters, "parameter")
    meta = all_parameters[key]
    if as_json:
        _dump_json({key: meta})
        return
    _echo_parameter(key, meta, indent=0)


def _hardware_channel(channel: Any) -> str:
    """Render one entry of a description's ``hw_channels`` list.

    A channel is ``{"device": ..., "hardware": ..., "channel": ...}``, but the whole
    description comes from library code, so anything unexpected is shown verbatim
    instead of being dropped.
    """
    if not isinstance(channel, dict):
        return _compact(channel)
    return (
        f"{channel.get('device', '?')} / {channel.get('hardware', '?')} "
        f"ch {channel.get('channel', '?')}"
    )


def _echo_rf_channel(channel_id: str, entry: Any, indent: int) -> None:
    """Print one RF channel with its device name, frequency and hardware channels."""
    pad = " " * indent
    click.echo(f"{pad}{channel_id}")
    if not isinstance(entry, dict):
        click.echo(f"{pad}    {_compact(entry)}")
        return

    click.echo(f"{pad}    {'name':<{_RF_LABEL_WIDTH}}: {entry.get('name', '-')}")
    frequency = entry.get("central_frequency")
    # `RFDevice.hardware_description` reports the central frequency in MHz.
    rendered = f"{frequency:g} MHz" if isinstance(frequency, int | float) else "-"
    click.echo(f"{pad}    {'central frequency':<{_RF_LABEL_WIDTH}}: {rendered}")

    channels = entry.get("hw_channels") or []
    if not isinstance(channels, list):
        channels = [channels]
    label = f"hw channels ({len(channels)})"
    if not channels:
        click.echo(f"{pad}    {label:<{_RF_LABEL_WIDTH}}: -")
        return
    for index, channel in enumerate(channels):
        # Only the first line carries the label; the rest line up underneath it.
        prefix = (
            f"{label:<{_RF_LABEL_WIDTH}}: "
            if index == 0
            else " " * (_RF_LABEL_WIDTH + 2)
        )
        click.echo(f"{pad}    {prefix}{_hardware_channel(channel)}")


def _echo_hardware_category(category: str, entries: Any) -> None:
    """Print one category of the hardware description.

    RF channels are shown in full; the other categories are listed by name, since their
    entries carry no per-channel detail worth a block each (``--json`` has everything).
    """
    click.echo(f"[{category}] ({len(entries)})")
    if category == _RF_CATEGORY and isinstance(entries, dict):
        for channel_id, entry in entries.items():
            _echo_rf_channel(channel_id, entry, indent=4)
        return
    for name in entries:
        click.echo(f"    {name}")


@cli.command(name="hardware")
@click.option("--json", "as_json", is_flag=True, help="Emit the description as JSON.")
def hardware_description(as_json: bool) -> None:
    """Show the setup hardware description reported by the library."""
    description = _run(
        _client().get_setup_hardware_description(), "load the hardware description"
    )
    if as_json:
        _dump_json(description)
        return
    if not description:
        click.echo("No hardware description available.")
        return
    for category, entries in description.items():
        _echo_hardware_category(category, entries)


@experiments.command(name="metadata")
@click.argument("experiment")
@click.option("--json", "as_json", is_flag=True, help="Emit the metadata as JSON.")
def get_experiment_readout_metadata(experiment: str, as_json: bool) -> None:
    """Fetch readout metadata for one EXPERIMENT using default parameter values.

    Parameters are populated with their default values from the parameter metadata.
    """
    client = _client()
    experiments, parameter_metadata = _load_metadata(client)
    key = _resolve_key(experiment, experiments, "experiment")
    module_name, instance_name = _split_experiment_id(key)
    parameter_dict = _default_parameter_dict(parameter_metadata)
    logger.info(
        "Fetching readout metadata for '%s' with %d default parameter value(s).",
        key,
        len(parameter_dict),
    )

    readout_metadata = _run(
        client.get_experiment_readout_metadata(
            exp_module_name=module_name,
            exp_instance_name=instance_name,
            parameter_dict=parameter_dict,
        ),
        "fetch the readout metadata",
    )
    # ReadoutMetadata is a dataclass; flatten it (and its nested PlotWindowMetadata) to
    # plain dicts so both output paths below stay dict-based.
    metadata = dataclasses.asdict(readout_metadata)
    if as_json:
        _dump_json(metadata)
        return
    # All fields are always present, so emptiness means every field is empty.
    if not any(metadata.values()):
        click.echo("No readout metadata available.")
        return
    for name, value in metadata.items():
        suffix = f" ({len(value)})" if isinstance(value, list) else ""
        click.echo(f"{name}{suffix}: {value}")


@experiments.command(name="instructions")
@click.argument("experiment")
@click.option(
    "--n-shots",
    type=click.IntRange(min=1),
    default=100,
    show_default=True,
    help="Number of shots to generate the hardware instructions for.",
)
@click.option(
    "--raw",
    is_flag=True,
    help="Print the hardware instructions exactly as returned instead of pretty-printing it.",
)
@click.option(
    "--from-influxdb",
    is_flag=True,
    help="Populate the parameters from the InfluxDB configured in the ICON config "
    "instead of using the library defaults. Parameters missing from the database keep "
    "their default value.",
)
@click.option(
    "--from-dump",
    type=click.Path(exists=True, dir_okay=False, allow_dash=True),
    default=None,
    help="Populate the parameters from a parameter-database dump written by "
    "`icon-parameter-db dump` (JSON or CSV, '-' reads stdin) instead of using the "
    "library defaults. Parameters missing from the dump keep their default value.",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the hardware instructions to a file instead of stdout.",
)
def create_hardware_instructions(
    experiment: str,
    n_shots: int,
    raw: bool,
    from_influxdb: bool,
    from_dump: str | None,
    output: Path | None,
) -> None:
    """Generate the hardware instructions for one EXPERIMENT.

    Parameters are populated with their default values from the parameter metadata, or,
    with ``--from-influxdb`` / ``--from-dump``, with the values stored in the configured
    InfluxDB or in a parameter-database dump.
    """
    client = _client()
    experiments, parameter_metadata = _load_metadata(client)
    key = _resolve_key(experiment, experiments, "experiment")
    module_name, instance_name = _split_experiment_id(key)
    parameter_dict, source = _parameter_dict_for(
        parameter_metadata, key, from_influxdb, from_dump
    )
    logger.info(
        "Generating sequence for '%s' with %d %s parameter value(s), n_shots=%d.",
        key,
        len(parameter_dict),
        source,
        n_shots,
    )

    sequence = _run(
        client.create_hardware_instructions(
            exp_module_name=module_name,
            exp_instance_name=instance_name,
            parameter_dict=parameter_dict,
            n_shots=n_shots,
        ),
        "generate the hardware instructions",
    )
    text = sequence if raw else _prettify(sequence)
    if output is not None:
        output.write_text(text)
        click.echo(f"Wrote hardware instructions ({len(text)} chars) to {output}.")
        return
    click.echo(text)


if __name__ == "__main__":
    cli()

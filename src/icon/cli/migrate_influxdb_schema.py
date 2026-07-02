"""Migrate the InfluxDB parameter measurement to the typed-field schema.

Legacy layout (one field key per parameter)::

    measurement "Experiment Parameters"
      tags:   namespace, parameter_group, param_type, <extra specifiers...>
      field:  "<full parameter identifier>" = <value>

New layout (typed value fields)::

    measurement "Experiment Parameters"
      tags:   namespace, parameter_group, param_type, <extra specifiers...>
      field:  value_float | value_int | value_str | value_bool = <value>

For every legacy parameter field this script reads the current value and rewrites it
through ICON's own write path (``ParametersRepository._update_influxdb_parameters``), so
the tag/typed-field mapping is never reimplemented here. Only the *reading* of the legacy
field-per-parameter layout is bespoke, because the application no longer knows that
schema.

The migrated data is written to a **new measurement**, the source measurement with an
``icon|v2|`` prefix (e.g. ``Experiment Parameters`` -> ``icon|v2|Experiment Parameters``).
The prefix is a distinctive, collision-resistant marker of the v2 schema. The original
measurement is left completely untouched, so the migration can be rolled back by simply
discarding the prefixed measurement. After verifying the result, point the InfluxDB
``measurement`` config at the prefixed measurement to start using the migrated data.

After writing, the migration verifies the prefixed measurement: it loads all values back
through the ICON API and checks that value *and* timestamp match the source data still
held in memory. A mismatch is reported and the script exits non-zero (with the source
measurement untouched for a clean retry).

Connection and measurement are taken from the ICON config (``get_config``), exactly like
the running application, so this migrates whatever database the app is pointed at. Pass
``--config`` to point at a specific config file (otherwise ``$ICON_CONFIG`` / the default
location is used).

Usage (installed as the ``icon-migrate-influxdb-schema`` console script)::

    icon-migrate-influxdb-schema
    icon-migrate-influxdb-schema migrate --dry-run
    icon-migrate-influxdb-schema --config /etc/icon/config.yaml
    icon-migrate-influxdb-schema assert-parameter-db

It can equivalently be run as a module: ``python -m
icon.cli.migrate_influxdb_schema``. Running the tool with no subcommand is
equivalent to ``migrate``.

The ``assert-parameter-db`` command only verifies connectivity and reports the detected
schema version (``pristine`` / ``v1`` / ``v2``) without modifying anything.

Note: only the *current* value of each parameter is migrated. Historical points remain in
the source measurement; the new schema starts from the migrated value.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import click
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from icon.config.config import get_config, set_config_path
from icon.server.data_access.db_context.influxdb_v1 import (
    InfluxDBv1Session,
    escape_quotes,
)
from icon.server.data_access.parameters_schema import (
    FIELD_KEY_NAMES,
    assert_parameter_db,
    field_key_from_value,
    v2_measurement_name,
)
from icon.server.data_access.repositories.parameters_repository import (
    ParametersRepository,
    build_parameter_identifier_from_specifiers,
    get_specifiers_from_parameter_identifier,
    value_from_point,
)

if TYPE_CHECKING:
    from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType

logger = logging.getLogger("migrate_influxdb_schema")

# A legacy parameter field key always contains the namespace specifier.
_IDENTIFIER_MARKER = "namespace='"


def legacy_parameter_fields(
    session: InfluxDBv1Session, measurement: str
) -> list[str]:
    """Return the legacy field keys that look like parameter identifiers."""
    return [
        key
        for key in session.get_field_keys(measurement)
        if key not in FIELD_KEY_NAMES and _IDENTIFIER_MARKER in key
    ]


def read_latest_point(
    session: InfluxDBv1Session, measurement: str, field_key: str
) -> tuple[DatabaseValueType, int] | None:
    """Return the ``(value, timestamp_ns)`` of a legacy parameter's most recent point."""
    stmt = (
        f'SELECT "{escape_quotes(field_key)}" AS value '
        f'FROM "{escape_quotes(measurement)}" ORDER BY time DESC LIMIT 1'
    )
    point = next(session.query(stmt, epoch="ns").get_points(), None)
    return None if point is None else (point["value"], point["time"])


def collect_current_values(
    session: InfluxDBv1Session, measurement: str
) -> dict[str, tuple[DatabaseValueType, int]]:
    """Read the current value and timestamp of every legacy parameter."""
    field_keys = legacy_parameter_fields(session, measurement)
    logger.info("Found %d legacy parameter field(s) to migrate.", len(field_keys))

    parameter_mapping: dict[str, tuple[DatabaseValueType, int]] = {}
    progress = tqdm(field_keys, desc="Reading parameters", unit="param")
    for index, field_key in enumerate(progress, start=1):
        point = read_latest_point(session, measurement, field_key)
        if point is None:
            logger.warning("No value found for parameter: %s", field_key)
            continue
        parameter_mapping[field_key] = point
        logger.info("[%d/%d] %s = %r", index, len(field_keys), field_key, point[0])

    return parameter_mapping


def write_migrated_parameters(
    parameter_mapping: dict[str, tuple[DatabaseValueType, int]],
    target_measurement: str,
) -> None:
    """Write migrated parameters into the target measurement, preserving timestamps.

    Points are assembled directly (rather than via
    ``ParametersRepository._update_influxdb_parameters``) because the original point
    timestamps must be preserved, which that method does not support. The tag and typed
    field mapping still reuses ``get_specifiers_from_parameter_identifier`` and
    ``field_key_from_value`` so the schema is not reimplemented here.
    """
    points = [
        {
            "measurement": target_measurement,
            "tags": get_specifiers_from_parameter_identifier(parameter_id),
            "time": timestamp_ns,
            "fields": {field_key_from_value(value): value},
        }
        for parameter_id, (value, timestamp_ns) in parameter_mapping.items()
    ]
    with InfluxDBv1Session() as influxdb:
        influxdb.write_points(points=points, time_precision="n")


def read_target_state(
    session: InfluxDBv1Session, measurement: str
) -> dict[str, tuple[DatabaseValueType, int]]:
    """Read ``{parameter_id: (value, timestamp_ns)}`` from a typed-schema measurement.

    Takes the latest point per series (``ORDER BY time DESC LIMIT 1`` applies per group
    under ``GROUP BY *``), matching the ``last()`` semantics of the ICON reader.
    """
    stmt = (
        f'SELECT * FROM "{escape_quotes(measurement)}" '
        f"GROUP BY * ORDER BY time DESC LIMIT 1"
    )
    state: dict[str, tuple[DatabaseValueType, int]] = {}
    for (_measurement, tags), points in session.query(stmt, epoch="ns").items():
        point = next(iter(points), None)
        if point is None:
            continue
        value = value_from_point(point)
        if value is None:
            continue
        parameter_id = build_parameter_identifier_from_specifiers(dict(tags))
        state[parameter_id] = (value, point["time"])
    return state


def _compare_parameter(
    parameter_id: str,
    source: tuple[DatabaseValueType, int],
    api_value: DatabaseValueType | None,
    target_point: tuple[DatabaseValueType, int] | None,
) -> int:
    """Return the number of value/timestamp mismatches for a single parameter."""
    value, timestamp_ns = source
    errors = 0

    if api_value != value:
        errors += 1
        logger.error(
            "value mismatch %s: source=%r target(api)=%r", parameter_id, value, api_value
        )

    if target_point is not None and target_point[1] != timestamp_ns:
        errors += 1
        logger.error(
            "timestamp mismatch %s: source=%d target=%d",
            parameter_id,
            timestamp_ns,
            target_point[1],
        )

    return errors


def verify_migration(
    session: InfluxDBv1Session,
    target_measurement: str,
    source_data: dict[str, tuple[DatabaseValueType, int]],
) -> bool:
    """Check that the migrated data matches the source on value and timestamp.

    Values are loaded through the ICON API (``get_influxdb_parameters``); timestamps are
    read directly from the target measurement (the API does not expose them). Returns
    ``True`` when everything matches.
    """
    logger.info("Verifying migrated data in '%s'...", target_measurement)

    api_values = ParametersRepository.get_influxdb_parameters(
        measurement=target_measurement
    )
    target_state = read_target_state(session, target_measurement)

    errors = 0
    missing = set(source_data) - set(api_values)
    extra = set(api_values) - set(source_data)
    if missing:
        errors += len(missing)
        logger.error("%d parameter(s) missing in target: %s", len(missing), missing)
    if extra:
        errors += len(extra)
        logger.error("%d unexpected parameter(s) in target: %s", len(extra), extra)

    for parameter_id, source in source_data.items():
        errors += _compare_parameter(
            parameter_id,
            source,
            api_values.get(parameter_id),
            target_state.get(parameter_id),
        )

    if errors:
        logger.error("Verification FAILED with %d mismatch(es).", errors)
        return False

    logger.info(
        "Verification OK: %d parameter(s) match on value and timestamp.",
        len(source_data),
    )
    return True


def run_assert() -> int:
    """Run the ``assert-parameter-db`` command."""
    try:
        version = assert_parameter_db()
    except AssertionError as exc:
        # A plain message (no traceback) is the useful output for a failed assertion.
        logger.error("%s", exc)  # noqa: TRY400
        return 1
    logger.info("Parameter DB schema version: %s", version.value)
    return 0


def run_migration(dry_run: bool) -> int:
    """Run the ``migrate`` command."""
    measurement = get_config().databases.influxdbv1.measurement
    target_measurement = v2_measurement_name(measurement)
    logger.info(
        "Migrating '%s' -> '%s'%s",
        measurement,
        target_measurement,
        " (DRY RUN)" if dry_run else "",
    )

    # ``logging_redirect_tqdm`` routes log records through ``tqdm.write`` so the log
    # output stays intact and the progress bar is not corrupted by interleaved lines.
    with InfluxDBv1Session() as session, logging_redirect_tqdm():
        parameter_mapping = collect_current_values(session, measurement)

    if dry_run:
        logger.info(
            "Would migrate %d parameter(s) to '%s'.",
            len(parameter_mapping),
            target_measurement,
        )
        return 0

    if not parameter_mapping:
        logger.info("Nothing to migrate.")
        return 0

    # Logged before the write because it can take a while and must not be interrupted;
    # folding this into the progress bar would be messier than a plain log line.
    logger.info(
        "Writing %d parameter(s) to measurement '%s' - do not interrupt...",
        len(parameter_mapping),
        target_measurement,
    )
    write_migrated_parameters(parameter_mapping, target_measurement)

    with InfluxDBv1Session() as session:
        if not verify_migration(session, target_measurement, parameter_mapping):
            logger.error(
                "Migrated data in '%s' does not match the source. The source "
                "measurement '%s' is untouched; discard '%s' and retry.",
                target_measurement,
                measurement,
                target_measurement,
            )
            return 1

    logger.info(
        "Migrated %d parameter(s) to '%s'. The source measurement '%s' is left "
        "untouched; point the InfluxDB 'measurement' config at '%s' to use the migrated "
        "data.",
        len(parameter_mapping),
        target_measurement,
        measurement,
        target_measurement,
    )
    return 0


@click.group(
    invoke_without_command=True,
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
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
@click.pass_context
def cli(ctx: click.Context, config_path: Path | None, verbose: bool) -> None:
    """Migrate the InfluxDB parameter measurement to the typed-field schema.

    With no subcommand this runs ``migrate``.
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    if config_path is not None:
        set_config_path(config_path)

    if ctx.invoked_subcommand is None:
        ctx.invoke(migrate)


@cli.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Report what would be migrated without writing anything.",
)
def migrate(dry_run: bool) -> None:
    """Read each legacy parameter's current value and rewrite it to the v2 schema."""
    raise SystemExit(run_migration(dry_run))


@cli.command(name="assert-parameter-db")
def assert_parameter_db_command() -> None:
    """Verify the connection and report the detected schema version."""
    raise SystemExit(run_assert())


if __name__ == "__main__":
    cli()

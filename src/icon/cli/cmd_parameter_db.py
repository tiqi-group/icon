"""Dump and load the ICON parameter database."""

from __future__ import annotations

import csv
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import time_ns
from typing import TYPE_CHECKING, Any

import click
import pytz
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from icon.cli.lib_parameter import InfluxDBv1CachedSessionProvider
from icon.config.config import get_config, set_config_path
from icon.server.data_access.db_context.influxdb.influxdb_v1 import escape_quotes
from icon.server.data_access.db_context.influxdb.parameters_backend import (
    FIELD_KEY_NAMES,
    FieldKey,
    InfluxDBParameterBackend,
    ParameterBackendR1,
    ParameterBackendR2,
    ParameterDBSchema,
    assert_parameter_db,
    build_parameter_identifier_from_specifiers,
    get_specifiers_from_parameter_identifier,
    value_from_point,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from icon.server.data_access.db_context.influxdb.influxdb_v1 import (
        InfluxDBSessionProvider,
    )
    from icon.server.data_access.experiment_data import DatabaseValueType

logger = logging.getLogger(__name__)

CLI_HELP = """Dump and load the parameter values of the configured ICON parameter database.

The database (host, credentials, measurement) is taken from the 'databases.influxdbv1'
section of the ICON config; the parameter schema revision (r1 or r2) is detected the same
way the ICON server detects it, so both layouts can be dumped and loaded.

\b
`dump`
        Writes the latest value of every parameter to stdout (or --output). With
        --since, the full history of every parameter from that time onwards is
        written instead.
`load`
        Reads a file written by `dump` (JSON or CSV) and writes those values back
        into the configured database, preserving the timestamps of each point.
        With --format influx-csv it reads the CSV the InfluxDB CLI itself writes
        (`influx -format csv`, queried with `GROUP BY *`) instead.

Dump records carry the parameter identifier, the point timestamp, the value and its
type; they do not carry the schema revision of the database they came from. A dump taken
from an r1 database can therefore be loaded into an r2 database and vice versa - the
records are always written in the schema of the target database.

Examples:

\b
    icon-parameter-db dump -o parameters.json
    icon-parameter-db dump --since 7d --format csv -o last_week.csv
    icon-parameter-db dump --since 2026-08-01T00:00:00 | gzip > august.json.gz
    icon-parameter-db load parameters.json
    icon-parameter-db load --now last_week.csv
    icon-parameter-db load --format influx-csv from_influx_cli.csv
"""

# Timestamps are read and written in nanoseconds - the native InfluxDB precision - so a
# dump/load cycle preserves the original point times exactly.
TIME_EPOCH = "ns"
NANOSECONDS_PER_SECOND = 1_000_000_000

FORMAT_VERSION = 1

DumpFormat = str  # "json", "csv" or "influx-csv"

CSV_FIELDNAMES = ("parameter_id", "time_ns", "timestamp", "value", "type")

# InfluxQL duration literal, e.g. "7d", "30m", "500ms".
_DURATION_RE = re.compile(r"^-?\d+(?:ns|u|ms|s|m|h|d|w)$")

# Fractional seconds of an ISO-8601 timestamp, kept out of ``datetime`` so nanosecond
# precision survives.
_FRACTION_RE = re.compile(r"\.(\d+)")

# Points are written in batches to keep single requests to the database small.
_WRITE_BATCH_SIZE = 5000

# The value columns of `influx -format csv` output and the dump type each maps to. A
# point populates exactly one of them.
_INFLUX_VALUE_TYPES = {
    FieldKey.FLOAT.value: "float",
    FieldKey.INT.value: "int",
    FieldKey.STR.value: "str",
    FieldKey.BOOL.value: "bool",
}

# The InfluxDB CLI joins the tags of a series into a single `key=value,key=value` column.
# Tag values may themselves contain commas, so a pair only starts at a comma directly
# followed by `key=`.
_INFLUX_TAG_SEPARATOR_RE = re.compile(r",(?=\w+=)")

# An epoch timestamp, as opposed to the RFC3339 string `influx -precision rfc3339` writes.
_EPOCH_RE = re.compile(r"^-?\d+$")


@dataclass
class ParameterRecord:
    """One value a parameter had at one point in time."""

    parameter_id: str
    time_ns: int
    value: DatabaseValueType


def _value_type_name(value: DatabaseValueType) -> str:
    """Return the name of a value's type, as stored in the ``type`` dump column."""
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "str"


def _parse_value(raw: Any, type_name: str | None) -> DatabaseValueType:
    """Convert a dumped value back into the type it was stored with.

    ``type_name`` is the ``type`` column of the dump. It is authoritative (CSV values are
    all strings); without it the value is taken as-is, which is lossless for JSON dumps.
    """
    if type_name is None:
        return raw if isinstance(raw, bool | float | int | str) else str(raw)
    if type_name == "bool":
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("true", "1")
    if type_name == "int":
        return int(raw)
    if type_name == "float":
        return float(raw)
    return str(raw)


def _local_timezone() -> Any:
    """Return the timezone naive timestamps are interpreted in (from the ICON config)."""
    return pytz.timezone(get_config().date.timezone)


def _isoformat(time_ns_value: int) -> str:
    """Format a nanosecond timestamp as an ISO-8601 UTC string with nanosecond digits."""
    seconds, nanoseconds = divmod(time_ns_value, NANOSECONDS_PER_SECOND)
    stamp = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return f"{stamp.strftime('%Y-%m-%dT%H:%M:%S')}.{nanoseconds:09d}Z"


def _timestamp_to_ns(value: str) -> int:
    """Parse an ISO-8601 timestamp into nanoseconds since the epoch.

    Accepts any number of fractional-second digits (``datetime`` is limited to
    microseconds, so the fraction is parsed separately). Naive timestamps are interpreted
    in the timezone configured in the ICON config.
    """
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = f"{text[:-1]}+00:00"

    nanoseconds = 0
    if (match := _FRACTION_RE.search(text)) is not None:
        nanoseconds = int(match.group(1).ljust(9, "0")[:9])
        text = f"{text[: match.start()]}{text[match.end() :]}"

    stamp = datetime.fromisoformat(text)
    if stamp.tzinfo is None:
        stamp = _local_timezone().localize(stamp)
    return round(stamp.timestamp()) * NANOSECONDS_PER_SECOND + nanoseconds


def _since_predicate(since: str | None) -> str | None:
    """Build the InfluxQL time predicate selecting everything at or after ``since``.

    ``since`` is either an InfluxQL duration relative to now (``7d``, ``-12h``) or an
    absolute ISO-8601 timestamp (``2026-08-01``, ``2026-08-01T12:00:00+02:00``).
    """
    if since is None:
        return None

    value = since.strip()
    if _DURATION_RE.match(value):
        return f"time >= now() - {value.lstrip('-')}"

    try:
        time_ns_value = _timestamp_to_ns(value)
    except ValueError as exc:
        message = (
            f"{since!r} is neither an InfluxQL duration (e.g. '7d', '12h') nor an "
            f"ISO-8601 timestamp (e.g. '2026-08-01T00:00:00'): {exc}"
        )
        raise click.BadParameter(message) from exc

    logger.info(
        "Dumping parameter values recorded at or after %s.", _isoformat(time_ns_value)
    )
    return f"time >= {time_ns_value}"


class ParameterDumpBackend(InfluxDBParameterBackend):
    """A parameter backend which can read and write timestamped parameter records.

    The read side is schema-specific (see the subclasses); the write side is shared: both
    schemas map an identifier to tags the same way and only differ in the fields written,
    which the backend's own ``_fields_for`` already handles.
    """

    def read_records(self, since_predicate: str | None) -> Iterator[ParameterRecord]:
        """Yield the parameter values in the database.

        Args:
            since_predicate: An InfluxQL time predicate. When given, every point at or
                after that time is yielded; when ``None``, only the latest value of each
                parameter is.
        """
        raise NotImplementedError

    def write_records(self, records: Iterable[ParameterRecord]) -> int:
        """Write records into the measurement, preserving their timestamps.

        Returns:
            The number of points written.
        """
        points = [
            {
                "measurement": self.measurement,
                "tags": get_specifiers_from_parameter_identifier(record.parameter_id),
                "fields": self._fields_for(record.parameter_id, record.value),
                "time": record.time_ns,
            }
            for record in records
        ]
        with self._session_provider() as session:
            session.write_points(
                points=points, time_precision="n", batch_size=_WRITE_BATCH_SIZE
            )
        return len(points)


class ParameterDumpBackendR2(ParameterBackendR2, ParameterDumpBackend):
    """Reads the typed-field (r2) schema, where one series holds one parameter."""

    def read_records(self, since_predicate: str | None) -> Iterator[ParameterRecord]:
        where = f" WHERE {since_predicate}" if since_predicate is not None else ""
        # Without a time filter only the newest point of each series is of interest;
        # `GROUP BY *` makes the LIMIT apply per parameter rather than per measurement.
        limit = "" if since_predicate is not None else " ORDER BY time DESC LIMIT 1"
        stmt = (
            f"SELECT {','.join(FIELD_KEY_NAMES)} "
            f'FROM "{escape_quotes(self.measurement)}"{where} GROUP BY *{limit}'
        )
        with self._session_provider() as session:
            series = session.query(stmt, epoch=TIME_EPOCH).items()

        for (_measurement, tags), points in series:
            if not tags:
                continue
            parameter_id = build_parameter_identifier_from_specifiers(dict(tags))
            for point in points:
                value = value_from_point(point)
                if value is not None:
                    yield ParameterRecord(parameter_id, int(point["time"]), value)


class ParameterDumpBackendR1(ParameterBackendR1, ParameterDumpBackend):
    """Reads the legacy (r1) schema, where one field key holds one parameter."""

    def read_records(self, since_predicate: str | None) -> Iterator[ParameterRecord]:
        field_keys = self.get_influxdb_parameter_keys()
        logger.info("Reading %d legacy parameter field(s).", len(field_keys))
        where = f" WHERE {since_predicate}" if since_predicate is not None else ""
        limit = "" if since_predicate is not None else " ORDER BY time DESC LIMIT 1"

        # One query per parameter: the legacy schema has no way to select "the latest
        # value of every field" in bulk, and reading sequentially is gentler on the
        # database than a single wide query over all field keys.
        with logging_redirect_tqdm():
            for field_key in tqdm(field_keys, desc="Reading parameters", unit="param"):
                stmt = (
                    f'SELECT "{escape_quotes(field_key)}" '
                    f'FROM "{escape_quotes(self.measurement)}"{where}{limit}'
                )
                with self._session_provider() as session:
                    points = list(session.query(stmt, epoch=TIME_EPOCH).get_points())
                for point in points:
                    value = point.get(field_key)
                    if value is not None:
                        yield ParameterRecord(field_key, int(point["time"]), value)


_DUMP_BACKENDS: dict[ParameterDBSchema, type[ParameterDumpBackend]] = {
    ParameterDBSchema.R1: ParameterDumpBackendR1,
    ParameterDBSchema.R2: ParameterDumpBackendR2,
    # A pristine database is initialised with the current (r2) schema.
    ParameterDBSchema.PRISTINE: ParameterDumpBackendR2,
}


def _create_dump_backend(
    schema: ParameterDBSchema, session_provider: InfluxDBSessionProvider
) -> ParameterDumpBackend:
    """Instantiate the dump/load backend for a detected schema revision."""
    return _DUMP_BACKENDS[schema](session_provider=session_provider)


def _connect() -> tuple[ParameterDumpBackend, InfluxDBv1CachedSessionProvider]:
    """Detect the parameter schema and return a backend bound to a cached session."""
    schema = assert_parameter_db()
    session_provider = InfluxDBv1CachedSessionProvider()
    backend = _create_dump_backend(schema, session_provider)
    influx = get_config().databases.influxdbv1
    logger.info(
        'InfluxDB %s:%s database "%s", measurement "%s" (schema %s).',
        influx.host,
        influx.port,
        influx.database,
        backend.measurement,
        backend.schema.value,
    )
    return backend, session_provider


def _record_dict(record: ParameterRecord) -> dict[str, Any]:
    """Render a record as the mapping written to the dump (one row / one object)."""
    return {
        "parameter_id": record.parameter_id,
        "time_ns": record.time_ns,
        "timestamp": _isoformat(record.time_ns),
        "value": record.value,
        "type": _value_type_name(record.value),
    }


def _write_json_dump(
    stream: Any, records: Iterator[ParameterRecord], metadata: dict[str, Any]
) -> int:
    """Write records as a JSON document, streaming them one object per line."""
    stream.write("{\n")
    for key, value in metadata.items():
        stream.write(f"  {json.dumps(key)}: {json.dumps(value)},\n")
    stream.write('  "parameters": [\n')
    count = 0
    for record in records:
        separator = "" if count == 0 else ",\n"
        stream.write(f"{separator}    {json.dumps(_record_dict(record))}")
        count += 1
    stream.write("\n  ]\n}\n" if count else "  ]\n}\n")
    return count


def _write_csv_dump(stream: Any, records: Iterator[ParameterRecord]) -> int:
    """Write records as CSV, one row per value."""
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    count = 0
    for record in records:
        writer.writerow(_record_dict(record))
        count += 1
    return count


def _resolve_format(output_format: str | None, filename: str) -> DumpFormat:
    """Return the dump format, inferring it from the file name when not given."""
    if output_format is not None:
        return output_format
    if filename != "-" and Path(filename).suffix.lower() == ".csv":
        return "csv"
    return "json"


def run_dump(since: str | None, output_format: str | None, output: str) -> int:
    """Run the ``dump`` command."""
    since_predicate = _since_predicate(since)
    dump_format = _resolve_format(output_format, output)

    try:
        backend, session_provider = _connect()
    except AssertionError as exc:
        # The assertion message names the host and the problem; the traceback is noise.
        logger.error("Cannot read the parameter database: %s", exc)  # noqa: TRY400
        logger.debug("Parameter database not usable", exc_info=True)
        return 1

    metadata = {
        "format_version": FORMAT_VERSION,
        "created": _isoformat(time_ns()),
        "source": {
            "host": get_config().databases.influxdbv1.host,
            "port": get_config().databases.influxdbv1.port,
            "database": get_config().databases.influxdbv1.database,
            "measurement": backend.measurement,
            "schema": backend.schema.value,
        },
        "since": since,
    }

    try:
        records = backend.read_records(since_predicate)
        # `click.open_file` handles "-" as stdout and closes real files afterwards.
        with click.open_file(output, "w") as stream:
            if dump_format == "csv":
                count = _write_csv_dump(stream, records)
            else:
                count = _write_json_dump(stream, records, metadata)
    finally:
        session_provider.close()

    logger.info(
        "Dumped %d parameter value(s) as %s to %s.",
        count,
        dump_format,
        "stdout" if output == "-" else output,
    )
    if count == 0:
        logger.warning("The dump is empty: no parameter values matched.")
    return 0


def _records_from_json(
    text: str, fallback_time_ns: int | None
) -> list[ParameterRecord]:
    """Parse the records of a JSON dump (a full dump document or a bare list)."""
    document = json.loads(text)
    rows = document["parameters"] if isinstance(document, dict) else document
    if not isinstance(rows, list):
        raise click.ClickException("The JSON dump does not contain a parameter list.")
    return [_record_from_row(row, fallback_time_ns) for row in rows]


def _records_from_csv(text: str, fallback_time_ns: int | None) -> list[ParameterRecord]:
    """Parse the records of a CSV dump."""
    return [
        _record_from_row(row, fallback_time_ns)
        for row in csv.DictReader(text.splitlines())
    ]


def _specifiers_from_influx_tags(tags: str) -> dict[str, str]:
    """Parse the ``tags`` column of an InfluxDB CLI dump into parameter specifiers."""
    specifiers: dict[str, str] = {}
    for pair in _INFLUX_TAG_SEPARATOR_RE.split(tags):
        key, _, value = pair.partition("=")
        if key:
            specifiers[key] = value
    return specifiers


def _influx_value(row: dict[str, Any]) -> tuple[Any, str] | None:
    """Return the value and dump type name of the row's populated value column.

    ``None`` when the row holds no value. A string parameter whose value is the empty
    string cannot be told apart from an absent value in this format, so it is skipped.
    """
    for column, type_name in _INFLUX_VALUE_TYPES.items():
        value = row.get(column)
        if value:
            return value, type_name
    return None


def _dump_row_from_influx_row(row: dict[str, Any]) -> dict[str, Any] | None:
    """Convert one row of an InfluxDB CLI dump into a dump row, or ``None`` to skip it.

    The layouts differ in every column: the parameter identifier has to be rebuilt from
    the ``tags`` column, and the value comes from whichever typed column is populated.
    Rows carrying no value are skipped, as is the header line the CLI repeats for each
    series when the query groups by tags.
    """
    if row.get("name") == "name":
        return None

    if (value_and_type := _influx_value(row)) is None:
        return None
    value, type_name = value_and_type

    specifiers = _specifiers_from_influx_tags(str(row.get("tags") or ""))
    time_value = str(row.get("time") or "").strip()

    return {
        "parameter_id": build_parameter_identifier_from_specifiers(specifiers),
        # `_record_from_row` reads either column; which one applies depends on the
        # precision the dump was taken with.
        ("time_ns" if _EPOCH_RE.match(time_value) else "timestamp"): time_value,
        "value": value,
        "type": type_name,
    }


def _records_from_influx_csv(
    text: str, fallback_time_ns: int | None
) -> list[ParameterRecord]:
    """Parse the records of a CSV written by the InfluxDB CLI (``influx -format csv``)."""
    reader = csv.DictReader(text.splitlines())
    if reader.fieldnames is None or "tags" not in reader.fieldnames:
        raise click.ClickException(
            "This InfluxDB CSV has no 'tags' column, so its rows carry no parameter "
            "identifier. Add 'GROUP BY *' to the query it came from."
        )

    rows = (_dump_row_from_influx_row(row) for row in reader)
    return [_record_from_row(row, fallback_time_ns) for row in rows if row is not None]


def _record_from_row(
    row: dict[str, Any], fallback_time_ns: int | None
) -> ParameterRecord:
    """Build a record from one dumped row, raising on missing or malformed columns.

    ``fallback_time_ns`` is the timestamp used for rows which carry none at all. It is
    only set for a ``--now`` load, which replaces the dumped timestamps anyway.
    """
    try:
        parameter_id = str(row["parameter_id"])
        value = _parse_value(row["value"], row.get("type"))
    except (KeyError, TypeError, ValueError) as exc:
        raise click.ClickException(f"Malformed dump row {row!r}: {exc}") from exc

    time_ns_value = row.get("time_ns")
    timestamp = row.get("timestamp")
    try:
        if time_ns_value not in (None, ""):
            return ParameterRecord(parameter_id, int(time_ns_value), value)
        if timestamp not in (None, ""):
            return ParameterRecord(
                parameter_id, _timestamp_to_ns(str(timestamp)), value
            )
    except ValueError as exc:
        raise click.ClickException(
            f"Malformed timestamp in row {row!r}: {exc}"
        ) from exc

    if fallback_time_ns is not None:
        return ParameterRecord(parameter_id, fallback_time_ns, value)

    raise click.ClickException(
        f"Row {row!r} has neither a 'time_ns' nor a 'timestamp' column. Pass --now to "
        "load such values with the current time."
    )


def _detect_format(text: str) -> DumpFormat:
    """Return the format of a dump, judged by its content (a file name is only a hint).

    A JSON dump starts with the opening brace of its document (or the bracket of a bare
    record list); an InfluxDB CLI dump is recognised by its typed value columns, which a
    dump written by `dump` never has.
    """
    body = text.lstrip()
    if body.startswith(("{", "[")):
        return "json"
    header = next(iter(body.splitlines()), "")
    if any(field_key in header for field_key in FIELD_KEY_NAMES):
        return "influx-csv"
    return "csv"


def _read_records(
    source: str, input_format: str | None, fallback_time_ns: int | None = None
) -> list[ParameterRecord]:
    """Read and parse a dump file (``-`` reads stdin)."""
    with click.open_file(source, "r") as stream:
        text = stream.read()
    if not text.strip():
        raise click.ClickException(f"{source} is empty.")

    dump_format = input_format or _detect_format(text)

    try:
        if dump_format == "influx-csv":
            return _records_from_influx_csv(text, fallback_time_ns)
        if dump_format == "csv":
            return _records_from_csv(text, fallback_time_ns)
        return _records_from_json(text, fallback_time_ns)
    except (json.JSONDecodeError, csv.Error) as exc:
        raise click.ClickException(
            f"Could not parse {source} as {dump_format}: {exc}"
        ) from exc


def latest_values_from_dump(source: str) -> dict[str, DatabaseValueType]:
    """Return ``{parameter_id: value}`` for the newest value of each parameter in a dump.

    ``source`` is a file written by the ``dump`` command, in either format (``-`` reads
    stdin). When the dump holds a history, the newest value of each parameter wins. This
    is the entry point for other tools which want to run against dumped parameter values
    instead of the live database.
    """
    records = _latest_per_parameter(_read_records(source, None))
    return {record.parameter_id: record.value for record in records}


def _latest_per_parameter(records: list[ParameterRecord]) -> list[ParameterRecord]:
    """Reduce records to the newest value of each parameter."""
    latest: dict[str, ParameterRecord] = {}
    for record in records:
        current = latest.get(record.parameter_id)
        if current is None or record.time_ns >= current.time_ns:
            latest[record.parameter_id] = record
    return list(latest.values())


def _valid_records(records: list[ParameterRecord]) -> list[ParameterRecord]:
    """Drop records whose identifier carries no specifiers, warning about each.

    A parameter identifier is a list of ``key='value'`` specifiers; those become the tags
    of the written point. An identifier without any would be written as an untagged point
    which no longer identifies a parameter, so such records are skipped.
    """
    valid = []
    for record in records:
        if get_specifiers_from_parameter_identifier(record.parameter_id):
            valid.append(record)
        else:
            logger.warning(
                "Skipping %r: not a parameter identifier (no key='value' specifiers).",
                record.parameter_id,
            )
    return valid


def _dry_run_report(source: str, records: list[ParameterRecord]) -> int:
    """Report what a load would write, without writing anything.

    The target measurement follows from the schema of the database, so it can only be
    named when the database is reachable. A dry run checks the dump itself, so an
    unreachable database is a warning here rather than a failure.
    """
    parameters = {record.parameter_id for record in records}

    try:
        backend, session_provider = _connect()
    except AssertionError as exc:
        logger.warning("Cannot name the target measurement: %s", exc)
        logger.debug("Parameter database not usable", exc_info=True)
        logger.info(
            "Would write %d value(s) of %d parameter(s) from %s (DRY RUN).",
            len(records),
            len(parameters),
            source,
        )
        return 0

    try:
        logger.info(
            "Would write %d value(s) of %d parameter(s) from %s to measurement '%s'"
            " (DRY RUN).",
            len(records),
            len(parameters),
            source,
            backend.measurement,
        )
    finally:
        session_provider.close()
    return 0


def run_load(
    source: str, input_format: str | None, dry_run: bool, now: bool, yes: bool
) -> int:
    """Run the ``load`` command."""
    load_time = time_ns() if now else None
    records = _valid_records(_read_records(source, input_format, load_time))
    if not records:
        logger.error("No parameter values to load from %s.", source)
        return 1

    if load_time is not None:
        records = [
            ParameterRecord(record.parameter_id, load_time, record.value)
            for record in _latest_per_parameter(records)
        ]
        logger.info(
            "--now: loading the latest value of each parameter, timestamped %s.",
            _isoformat(load_time),
        )

    if dry_run:
        return _dry_run_report(source, records)

    try:
        backend, session_provider = _connect()
    except AssertionError as exc:
        # The assertion message names the host and the problem; the traceback is noise.
        logger.error("Cannot write to the parameter database: %s", exc)  # noqa: TRY400
        logger.debug("Parameter database not usable", exc_info=True)
        return 1

    try:
        parameters = {record.parameter_id for record in records}
        if not yes and not click.confirm(
            f"Write {len(records)} value(s) of {len(parameters)} parameter(s) from "
            f"{source} into '{backend.measurement}'?",
            default=False,
        ):
            logger.info("Load cancelled.")
            return 1

        written = backend.write_records(records)
    finally:
        session_provider.close()

    logger.info(
        "Loaded %d value(s) of %d parameter(s) into measurement '%s'.",
        written,
        len(parameters),
        backend.measurement,
    )
    return 0


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    help=CLI_HELP,
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Path to the ICON config file to use (defaults to $ICON_CONFIG, else "
    "~/.config/icon/config.yaml).",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging.")
def cli(config_path: Path | None, verbose: bool) -> None:
    # Logging goes to stderr, so a dump written to stdout stays machine-readable.
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s.%(msecs)03d | %(levelname)s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
    )

    if config_path is not None:
        set_config_path(config_path)


@cli.command()
@click.option(
    "--since",
    default=None,
    help="Dump every value recorded at or after this time instead of only the latest "
    "value of each parameter. Either a duration relative to now ('7d', '12h', '30m') "
    "or an ISO-8601 timestamp ('2026-08-01', '2026-08-01T12:00:00+02:00'); a timestamp "
    "without a timezone is read in the timezone configured in the ICON config.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["json", "csv"], case_sensitive=False),
    default=None,
    help="Output format. Defaults to csv if --output ends in '.csv', else json.",
)
@click.option(
    "-o",
    "--output",
    default="-",
    show_default=True,
    help="File to write the dump to; '-' is stdout.",
)
def dump(since: str | None, output_format: str | None, output: str) -> None:
    """Dump parameter values from the configured database."""
    raise SystemExit(run_dump(since, output_format, output))


@cli.command()
@click.argument("source", metavar="FILE", default="-")
@click.option(
    "--format",
    "input_format",
    type=click.Choice(["json", "csv", "influx-csv"], case_sensitive=False),
    default=None,
    help="Format of FILE. 'influx-csv' reads the CSV written by the InfluxDB CLI "
    "(`influx -format csv` over a query with 'GROUP BY *') rather than a file written "
    "by `dump`. Detected from the content of FILE when not given.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Read and check the dump and report what would be written, without writing "
    "anything. Works without a reachable database, which then leaves the target "
    "measurement unnamed.",
)
@click.option(
    "--now",
    is_flag=True,
    help="Write the latest value of each parameter with the current timestamp instead "
    "of restoring the dumped history at its original timestamps. Use this to make a "
    "dump the current state of the database.",
)
@click.option("-y", "--yes", is_flag=True, help="Skip the confirmation prompt.")
def load(
    source: str, input_format: str | None, dry_run: bool, now: bool, yes: bool
) -> None:
    """Load a dump written by `dump` into the configured database ('-' reads stdin)."""
    raise SystemExit(run_load(source, input_format, dry_run, now, yes))


if __name__ == "__main__":
    cli()

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
    icon-migrate-influxdb-schema profile
    icon-migrate-influxdb-schema rollback

It can equivalently be run as a module: ``python -m
icon.cli.migrate_influxdb_schema``. Running the tool with no subcommand is
equivalent to ``migrate``.

The ``profile`` command only verifies connectivity and reports the detected
schema version (``pristine`` / ``v1`` / ``v2``) without modifying anything.

The ``rollback`` command undoes a migration by dropping the ``icon|v2|`` measurement, but
only when **both** the v1 and v2 schemas are present (so v1 remains as a fallback and the
parameters are never left without a copy); otherwise it warns and changes nothing. Pass
``--force`` to skip that check and drop the v2 measurement unconditionally.

Note: only the *current* value of each parameter is migrated. Historical points remain in
the source measurement; the new schema starts from the migrated value.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from attr import dataclass
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from typing_extensions import Self

from icon.config.config import get_config, set_config_path
from icon.server.data_access.db_context.influxdb.influxdb_v1 import (
    DatabaseValueType,
    InfluxDBv1Session,
    escape_quotes,
)
from icon.server.data_access.db_context.influxdb.parameters_backend import (
    FIELD_KEY_NAMES,
    ParameterBackendV1,
    ParameterBackendV2,
    ParameterDBSchema,
    assert_parameter_db,
    build_parameter_identifier_from_specifiers,
    create_parameter_backend,
    detect_schema,
    v2_measurement_name,
    value_from_point,
)

if TYPE_CHECKING:
    import contextlib
    from types import TracebackType

logger = logging.getLogger(__name__)

# A legacy parameter field key always contains the namespace specifier.
_IDENTIFIER_MARKER = "namespace='"


class InfluxDBv1CachedSession(InfluxDBv1Session):
    """A cached InfluxDBv1Session that reuses a connection across calls."""

    def __init__(self) -> None:
        super().__init__()
        self.connect()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ) -> None:
        pass


class InfluxDBv1CachedSessionProvider:
    """Provides cached InfluxDBv1Session instance."""

    def __init__(self) -> None:
        self.session = InfluxDBv1CachedSession()

    def __call__(self) -> contextlib.AbstractContextManager[InfluxDBv1Session]:
        return self.session

    def close(self) -> None:
        self.session.disconnect()


@dataclass
class ParameterValue:
    time: int
    tags: dict[str, str]
    value: DatabaseValueType


ParameterMapping = dict[str, ParameterValue]
ParameterErrors = dict[
    str, tuple[str, dict[str, Any]]
]  # parameter_id -> (error_msg, extra_info)

TIME_EPOCH = "ns"


class ParameterMigrationBackendV1(ParameterBackendV1):
    def get_influxdb_last_parameter_by_id(
        self, field_key: str
    ) -> ParameterValue | None:
        """Read individual field key value from v1 schema with tags and time."""
        stmt = (
            f'SELECT "{escape_quotes(field_key)}",*::tag '
            f'FROM "{escape_quotes(self.measurement)}" ORDER BY time DESC LIMIT 1'
        )
        with self._session_provider() as session:
            point = next(session.query(stmt, epoch=TIME_EPOCH).get_points(), None)
            if point is None:
                return None

            return ParameterValue(
                time=point["time"],
                tags={
                    k: str(v)
                    for k, v in point.items()
                    if k not in ("time", field_key) and v is not None
                },
                value=point[field_key],
            )


class ParameterMigrationBackendV2(ParameterBackendV2):
    def get_influxdb_parameters_with_tags(self) -> ParameterMapping:
        stmt = (
            f"SELECT {','.join(FIELD_KEY_NAMES)} "
            f'FROM "{escape_quotes(self.measurement)}"'
            f"GROUP BY *"
            "ORDER BY time DESC LIMIT 1"
        )
        result: dict[str, ParameterValue] = {}
        t0 = time.perf_counter()
        with self._session_provider() as session:
            for (_measurement, tags), points in session.query(
                stmt, epoch=TIME_EPOCH
            ).items():
                point: dict[str, DatabaseValueType] = next(iter(points), {})
                value = value_from_point(point)
                if tags and value is not None:
                    identifier = build_parameter_identifier_from_specifiers(dict(tags))
                    result[identifier] = ParameterValue(
                        time=int(point["time"]), tags=tags, value=value
                    )
        logger.info(
            "Fetched %d parameters in %.0f ms",
            len(result),
            (time.perf_counter() - t0) * 1000,
        )

        return result

    def write_influxdb_parameters(self, parameter_mapping: ParameterMapping) -> None:
        measurement = self.measurement
        points = [
            {
                "measurement": measurement,
                "tags": v.tags,
                "fields": self._fields_for(p, v.value),
                "time": v.time,
            }
            for p, v in parameter_mapping.items()
        ]
        t0 = time.perf_counter()
        with self._session_provider() as session:
            session.write_points(points=points, time_precision="n")
        logger.info(
            "Wrote %d parameters in %.0f ms",
            len(parameter_mapping),
            (time.perf_counter() - t0) * 1000,
        )


class InfluxDBSchemaMigrationManager:
    def __init__(self) -> None:
        cached_session_provider = InfluxDBv1CachedSessionProvider()
        self.source_backend = ParameterMigrationBackendV1(
            session_provider=cached_session_provider
        )
        self.target_backend = ParameterMigrationBackendV2(
            session_provider=cached_session_provider
        )

    def collect_v1_values(self) -> tuple[ParameterMapping, ParameterErrors]:
        """Read the latest value, time and tags of every legacy parameter. We read individual parameters sequentually. This should be more gentile on the database."""
        with logging_redirect_tqdm():
            field_keys = self.source_backend.get_influxdb_parameter_keys()
            logger.info(
                "Found %d legacy parameter field(s) to migrate.", len(field_keys)
            )

            parameter_mapping: ParameterMapping = {}
            ignored_params: ParameterErrors = {}

            for index, field_key in enumerate(
                tqdm(field_keys, desc="Reading parameters", unit="param"), start=1
            ):
                if (
                    point := self.source_backend.get_influxdb_last_parameter_by_id(
                        field_key
                    )
                ) is None:
                    logger.info(
                        "[%04d/%d] IGNORING %s : %s",
                        index,
                        len(field_keys),
                        field_key,
                        "No value found for parameter",
                    )
                    ignored_params[field_key] = ("No value found for parameter", {})
                    continue

                parameter_id_from_tags = build_parameter_identifier_from_specifiers(
                    point.tags
                )
                if parameter_id_from_tags != field_key:
                    logger.info(
                        "[%04d/%d] IGNORING %s : %s",
                        index,
                        len(field_keys),
                        field_key,
                        "Corrupt parameter id. Ignoring for migration! \n"
                        f'       found="{field_key}" \n'
                        f'    expected="{parameter_id_from_tags}")',
                    )
                    ignored_params[field_key] = (
                        "Field key and tags are not consistent",
                        {
                            "found": field_key,
                            "expected": parameter_id_from_tags,
                            "tags": point.tags,
                        },
                    )
                    continue

                parameter_mapping[field_key] = point
                logger.debug(
                    "[%04d/%d] OK %s = %r  (%s)",
                    index,
                    len(field_keys),
                    field_key,
                    point.value,
                    point.time,
                )

        return parameter_mapping, ignored_params

    def write_v2_parameters(self, parameter_mapping: ParameterMapping) -> None:
        """Write migrated parameters into the target measurement, preserving timestamps.

        The tag/typed-field mapping is delegated to ``update_influxdb_parameters`` (so the
        schema is not reimplemented here); the original point timestamps are passed through
        so they are preserved in the target measurement rather than replaced by the write
        time.
        """
        self.target_backend.write_influxdb_parameters(parameter_mapping)

    def verify_target_values(self, source_data: ParameterMapping) -> bool:
        """Check that the migrated data matches the source on value and timestamp.

        Values are loaded through the ICON API (``get_influxdb_parameters``); timestamps are
        read directly from the target measurement (the API does not expose them). Returns
        ``True`` when everything matches.
        """
        logger.info(
            "Verifying migrated data in '%s'...", self.target_backend.measurement
        )

        target_values = self.target_backend.get_influxdb_parameters_with_tags()

        errors = 0
        missing = set(source_data) - set(target_values)
        extra = set(target_values) - set(source_data)
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
                target_values.get(parameter_id),
            )

        if errors:
            logger.error("Verification FAILED with %d mismatch(es).", errors)
            return False

        logger.info(
            "Verification OK: %d parameter(s) match on value and timestamp.",
            len(source_data),
        )
        return True


def _compare_parameter(
    parameter_id: str,
    source: ParameterValue,
    target_point: ParameterValue | None,
) -> int:
    """Return the number of value/timestamp mismatches for a single parameter."""
    errors = 0

    if target_point is not None and target_point.time != source.time:
        errors += 1
        logger.error(
            "timestamp mismatch %s: source=%s target=%s",
            parameter_id,
            source.time,
            target_point.time,
        )

    return errors


def run_profile(
    assumed_version: ParameterDBSchema | None = None, *, do_v1_bulk_read: bool = False
) -> int:
    if assumed_version is None:
        try:
            detected_version = assert_parameter_db()
        except AssertionError:
            logger.exception("Unable to detect Paramater DB Schema")
            return 1
    schema_version = assumed_version or detected_version

    session_provider = InfluxDBv1CachedSessionProvider()
    backend = create_parameter_backend(schema_version, session_provider)
    logger.info(
        'Parameter DB schema version: %s (Measurement: "%s")',
        backend.schema.value,
        backend.measurement,
    )

    with session_provider() as session:
        measurements = session.get_measurements()
        field_keys = session.get_field_keys(backend.measurement)
        series = session.get_series(backend.measurement)

    logger.info("Field key cardinality: %d ", len(field_keys))
    logger.info("Series cardinality: %d ", len(series))

    measurements_by_icon = filter(
        lambda m: get_config().databases.influxdbv1.measurement in m or "icon|" in m,
        measurements,
    )

    logger.info(
        "%s measurement(s) found. Icon related: %s",
        len(measurements),
        ", ".join(measurements_by_icon) or "None",
    )

    if backend.measurement not in measurements:
        logger.error(
            'Expected measurement "%s" not present. Found: %s',
            backend.measurement,
            measurements,
        )

    if schema_version == ParameterDBSchema.V2:
        t0 = time.perf_counter()
        params = backend.get_influxdb_parameters()
        logger.info(
            "Fetched %d parameter values in %0.1f ms",
            len(params),
            (time.perf_counter() - t0) * 1000,
        )

    if schema_version == ParameterDBSchema.V1:
        backend = ParameterMigrationBackendV1(session_provider)
        pksample = field_keys[:10]
        t0 = time.perf_counter()
        with logging_redirect_tqdm():
            for pk in tqdm(
                pksample, desc="Estimating parameter query rate", unit="param"
            ):
                backend.get_influxdb_last_parameter_by_id(pk)
        logger.info(
            "Migrating %d parameters would take roughly %0.0f s",
            len(field_keys),
            (time.perf_counter() - t0) / len(pksample) * len(field_keys),
        )

        if do_v1_bulk_read:
            t0 = time.perf_counter()
            params = backend.get_influxdb_parameters()
            logger.info(
                "Fetched %d parameter values in %0.1f ms",
                len(params),
                (time.perf_counter() - t0) * 1000,
            )

    return 0


def run_migration(dry_run: bool, confirm_inconsistencies: bool, yes: bool) -> int:
    mm = InfluxDBSchemaMigrationManager()
    config_influx = get_config().databases.influxdbv1

    logger.info(
        'Migrating InfluxDB "%s:%s" database "%s": From measurement "%s" -> "%s" %s',
        config_influx.host,
        config_influx.port,
        config_influx.database,
        mm.source_backend.measurement,
        mm.target_backend.measurement,
        " (DRY RUN)" if dry_run else "",
    )

    parameter_mapping, ignored_params = mm.collect_v1_values()

    if len(ignored_params) > 0:
        logger.warning(
            "%d parameter(s) would not be migrated due to missing values or inconsistent"
            " tags. --confirm-inconsistencies required to perform migration anyway.",
            len(ignored_params),
        )
        if not confirm_inconsistencies:
            logger.error(
                "Migration aborted due to inconsistent parameters. "
                "Use --confirm-inconsistencies to proceed anyway."
            )
            return 1

    if dry_run:
        logger.info(
            "Would migrate %d/%d parameter(s) to '%s'.",
            len(parameter_mapping),
            len(parameter_mapping) + len(ignored_params),
            mm.target_backend.measurement,
        )
        return 0

    if not parameter_mapping:
        logger.info("Nothing to migrate.")
        return 0

    if not yes and not click.confirm(
        f"Migrate {len(parameter_mapping)} parameter(s) from '{mm.source_backend.measurement}' to "
        f"'{mm.target_backend.measurement}'?",
        default=False,
    ):
        logger.info("Migration cancelled.")
        return 1

    logger.info(
        "Writing %d parameter(s) to measurement '%s'",
        len(parameter_mapping),
        mm.target_backend.measurement,
    )
    mm.write_v2_parameters(parameter_mapping)

    if not mm.verify_target_values(parameter_mapping):
        logger.error(
            "Migrated data in '%s' does not match the source.",
            mm.target_backend.measurement,
        )
        return 1

    logger.info(
        "Migrated %d parameter(s) to '%s'. The source measurement '%s' remains for rollback.",
        len(parameter_mapping),
        mm.target_backend.measurement,
        mm.source_backend.measurement,
    )
    return 0


def run_verify() -> int:
    mm = InfluxDBSchemaMigrationManager()
    parameter_mapping, ignored_params = mm.collect_v1_values()

    if not mm.verify_target_values(parameter_mapping):
        logger.error("Migrated data does not match the source.")
        return 1

    if len(ignored_params) > 0:
        logger.info(
            "%d parameters from the source schema ignored for verifcation",
            len(ignored_params),
        )

    return 0


def run_rollback(dry_run: bool, force: bool) -> int:
    """Run the ``rollback`` command.

    Undoes a migration by dropping the v2 (typed-schema) measurement. By default this only
    happens when **both** the v1 legacy measurement and the v2 measurement are present with
    their expected schema: requiring v1 to still exist guarantees a fallback, so a rollback
    can never destroy the only copy of the parameters. If either schema is missing, the v2
    measurement is left untouched and a warning is emitted.

    With ``force`` the v1/v2 existence check is skipped and the v2 measurement is dropped
    unconditionally (dropping a non-existent measurement is a harmless no-op).
    """
    influx = get_config().databases.influxdbv1
    base_measurement = influx.measurement
    v2_name = v2_measurement_name(base_measurement)

    with InfluxDBv1Session() as session:
        try:
            databases = session.get_databases()
        except (
            Exception
        ) as exc:  # connection failures surface as requests/urllib3 errors
            logger.error(  # noqa: TRY400
                "Could not connect to InfluxDB at %s:%s: %s",
                influx.host,
                influx.port,
                exc,
            )
            return 1

        if influx.database not in databases:
            logger.error(
                "Configured InfluxDB database %r does not exist.", influx.database
            )
            return 1

        if force:
            logger.warning(
                "--force given: skipping the v1/v2 existence check before dropping '%s'.",
                v2_name,
            )
        else:
            v1_present = (
                detect_schema(session.get_field_keys(base_measurement))
                is ParameterDBSchema.V1
            )
            v2_present = (
                detect_schema(session.get_field_keys(v2_name)) is ParameterDBSchema.V2
            )
            if not (v1_present and v2_present):
                logger.warning(
                    "Cannot roll back: both schemas must exist (v1 '%s': %s, v2 '%s': %s)."
                    " The v2 measurement was left untouched. Use --force to drop it anyway.",
                    base_measurement,
                    "present" if v1_present else "missing",
                    v2_name,
                    "present" if v2_present else "missing",
                )
                return 1

        if dry_run:
            logger.info("Would drop the v2 measurement '%s' (DRY RUN).", v2_name)
            return 0

        logger.info("Dropping the v2 measurement '%s'...", v2_name)
        session.query(f'DROP MEASUREMENT "{escape_quotes(v2_name)}"')

        if detect_schema(session.get_field_keys(v2_name)) is not None:
            logger.error("Failed to drop the v2 measurement '%s'.", v2_name)
            return 1

    logger.info("Rolled back: dropped the v2 measurement '%s'.", v2_name)
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
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging.")
@click.pass_context
def cli(ctx: click.Context, config_path: Path | None, verbose: bool) -> None:
    """Migrate the InfluxDB parameter measurement to the typed-field schema.

    With no subcommand this runs ``migrate``.
    """
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s.%(msecs)03d | %(levelname)s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
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
@click.option(
    "--confirm-inconsistencies",
    is_flag=True,
    help="Proceed even if some parameters have missing values or inconsistent tags "
    "(those parameters are skipped).",
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    help="Skip the interactive confirmation prompt.",
)
def migrate(dry_run: bool, confirm_inconsistencies: bool, yes: bool) -> None:
    """Read each legacy parameter's current value and rewrite it to the v2 schema."""
    raise SystemExit(run_migration(dry_run, confirm_inconsistencies, yes))


@cli.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Report what would be dropped without changing anything.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Skip the v1/v2 existence check and drop the v2 measurement unconditionally.",
)
def rollback(dry_run: bool, force: bool) -> None:
    """Undo a migration: drop the v2 measurement (only if both schemas exist, unless --force)."""
    raise SystemExit(run_rollback(dry_run, force))


@cli.command()
@click.option(
    "--assume-schema-version",
    type=click.Choice(ParameterDBSchema, case_sensitive=False),
    default=None,
    help="Skip the schema detection and assume the given schema version",
)
@click.option(
    "--do-v1-bulk-read",
    is_flag=True,
    help="Perform bulk read in case of v1 schema. Implies --assume-schema-version=v1. WARNING: This may put significant load on the server. Use with caution. ",
)
def profile(
    assume_schema_version: ParameterDBSchema | None = None,
    *,
    do_v1_bulk_read: bool = False,
) -> None:
    """Run profiling on the parameter database (schema, size, read rate)."""
    if do_v1_bulk_read and assume_schema_version == ParameterDBSchema.V2:
        logger.error("--do_v1_bulk_read and --assume_schema_version=v1 is not allowed")
        raise SystemExit(1)

    if do_v1_bulk_read:
        assume_schema_version = ParameterDBSchema.V1

    raise SystemExit(
        run_profile(assume_schema_version, do_v1_bulk_read=do_v1_bulk_read)
    )


@cli.command()
def verify() -> None:
    """Verify v2 state against v1 state."""
    raise SystemExit(run_verify())


if __name__ == "__main__":
    cli()

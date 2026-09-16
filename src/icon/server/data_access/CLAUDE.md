# data_access — SQLite, InfluxDB v1, HDF5, experiment-library clients

Read `/CLAUDE.md` first. This unit is the **only** place that may touch persistence.
Controllers and workers call repositories; they never open sessions or HDF5 files.

```
data_access/
├── db_context/
│   ├── sqlite/            engine.py (one engine, file from config), migrations.py (alembic upgrade head at startup), alembic/
│   └── influxdb/          influxdb_v1.py (InfluxDBv1Session, InfluxQL) + parameters_backend.py (r1/r2 schema + detection, see §4)
├── models/
│   ├── enums.py           JobStatus, JobRunStatus, DeviceStatus  (stored as strings)
│   └── sqlite/            SQLAlchemy 2.0 declarative models; register new models in __init__.py __all__
├── repositories/          static/class-method repositories; emit socket events via emit_queue
├── experiment_data.py     dataclasses that define the HDF5 <-> API payload contract
├── job_list_item.py       JobListItemDict — slim TypedDict for the paginated job list (scheduler.get_job_list)
├── experiment_library_client.py                abstract ExperimentLibraryClient
├── venv_exec.py / venv_experiment_library_client.py   run code inside the library's own venv (subprocess)
├── pycrystal_experiment_library_client.py       default client (+ GitRepo clone/checkout)
├── reconfigurable_experiment_library_client.py  hot-reloads the client class named in config
└── sqlalchemy_dict_encoder.py                   ORM -> plain dict for socket payloads
```

## 1. What the code actually does (vs. the 2023–24 design docs)

| Design-doc idea | Implementation today | Note |
|---|---|---|
| sqlmodel | **SQLAlchemy 2.0** (`Mapped[...]`, `mapped_column`) + **Alembic** | Models must not leak into API payloads except via `SQLAlchemyDictEncoder` |
| Tables `Job`, `ScanParameter`, `JobExecutionHistory`, `User`, `RemoteSource` | `job_submissions` (`Job`), `job_runs` (`JobRun`), `scan_parameters`, `experiment_sources`, `devices` | No `User`, no `RemoteSource`; `devices` registers pydase services only (deliberate, see §2), realtime hardware lives in `config.hardware` |
| Job `type` (scan/continuous/calibration) + `interval` | No type column. "Continuous" = a scan parameter with `realtime=True` and `variable_id="Real Time"`. Calibration = `Job.auto_calibration` flag (currently unused) | See `NEW_FEATURES.md` for periodic/calibration jobs |
| Job status includes "scheduled" for restart re-scheduling | `SUBMITTED → PROCESSING → PROCESSED` only. Runs: `PENDING/PROCESSING/PAUSED/DONE/FAILED/CANCELLED` | Runs left PENDING/PROCESSING/PAUSED at startup are **cancelled**, never re-scheduled |
| `retry_count` on history | Only `Device.retry_attempts/retry_delay_seconds` (verifying a device set-value). No job-level retries | |
| Valkey/Redis cache for globals | **`multiprocessing.Manager().dict()`** (`SRM.parameters_dict`) held by `ParametersRepository` | Deliberate, see §4 |
| InfluxDB v2 (Flux) | **InfluxDB v1** (InfluxQL). Two parameter schemas since v0.3.0: legacy **r1** (field key = parameter id) and **r2** (measurement `icon\|2\|<base>`, per-type value fields, identity in the tags) — see §4 | |
| `experiment_id` = file path + name | `ExperimentSource.experiment_id` = `"<module>.<Class> (<instance name>)"` string produced by pycrystal; parsed by `pre_processing.worker.ExperimentIdentifier` | |
| HDF5 via pandas `to_hdf` | Hand-built `h5py` datasets (see §3) | |
| Post-processing worker fits + updates parameters | Fits live in `server/fitting`, triggered by the **pre-processing** worker after a run (`try_auto_fit`) or by the API (`data.run_fit`) | Deliberate, see workers file |

## 2. SQLite schema (current head) and rules

```
experiment_sources(id, experiment_id)
job_submissions(id, created, experiment_source_id FK, status, git_commit_hash NULL,
                priority 0..20 CHECK, repetitions, number_of_shots,
                local_parameters_timestamp, auto_calibration, debug_mode,
                parent_job_id FK self NULL)            index by_experiment_id_and_status
job_runs(id, scheduled_time UNIQUE, job_id FK, status, log NULL,
         parameter_update_timestamp NULL)             index by_job_id_and_status
scan_parameters(id, job_id FK, name, variable_id, scan_values JSON-text,
                device_id FK NULL, realtime bool)
devices(id, created, name UNIQUE idx, url, status idx, description NULL,
        retry_attempts, retry_delay_seconds)
```

Rules:

- `Base.type_annotation_map` maps `datetime` → `TIMESTAMP(timezone=True)`. SQLite
  stores it naive; repositories/`SQLAlchemyDictEncoder` re-attach the config timezone
  on the way out. `JobRun.parameter_update_timestamp` is treated as **UTC-naive** and
  compared via `.replace(tzinfo=UTC)` in `hardware_processing.worker.should_divert_task`.
  Keep that convention or migrate all readers at once.
- `Job.created` is set by a `before_insert` listener and may not be set by callers.
- `scan_values` is a `JSONEncodedList` (`TEXT`). Values may be `bool|float|int|str`.
  `ScanParameter.realtime=True` requires `variable_id == "Real Time"` (listener).
- `JobRun.scheduled_time` is **unique** because it is the HDF5 filename (§3). The
  scheduler inserts one run per job; there is no 1:N history in practice even though
  the FK would allow it. `Job.run` is a scalar relationship.
- `Job.priority`: `PriorityQueue` pops the **lowest number first** and the worker calls
  `psutil.Process.nice(priority)`, so **0 = most urgent, 20 = least**, default 20.

  > **Design note** — 0 = most urgent is the definitive semantics. The
  > `Job.priority` docstring ("0 (lowest) … 20 (highest)") is wrong and must be
  > corrected, and the frontend validation widened from `1..20` to `0..20`
  > (`frontend/CLAUDE.md` §3). Until those fixes land, trust the queue behaviour,
  > not the docstring.
- Devices — deliberate scoping: the `devices` table models **pydase `DataService`s
  only** — "device = DataService", i.e. slow devices without realtime capability,
  set point-by-point over the network. Realtime-capable hardware (Zedboard, RFSoC,
  Fastino, …) is **not** a device row; it is driven by a `HardwareController`
  configured in `config.hardware.devices` (see the workers file). No `type` column
  and no separate remote-sources table will be added.
- Run-status updates are **conditional and atomic**: `JobRunRepository.update_run_by_id(...,
  only_if_status=(...))` compiles to `UPDATE … WHERE status IN (…) RETURNING`, so
  cancel/pause/resume cannot race (v0.3.0). New status transitions must use
  `only_if_status` (or `try_update_run_by_id`), never read-then-write.
- The job list is paginated: `JobRepository.get_job_list(before_id=…, limit=…)` returns
  slim `JobListItemDict`s (page size 100, newest first). Extend the TypedDict for list
  views instead of shipping ORM dumps.
- Repositories open a `Session(engine)` per call, `commit`, `refresh`, `expunge` and
  return **detached** objects. Pass `load_experiment_source=True` /
  `load_scan_parameters=True` when you need relationships (they use `selectinload`);
  do not access unloaded relationships on detached objects.
- Every mutating repository method emits a socket event (`job.new`, `job.update`,
  `job_run.new`, `job_run.update`, `device.new`, `device.update`, `parameter.update`)
  through `web_server.socketio_emit_queue.emit_queue`. New mutations must do the same,
  with payloads produced by `SQLAlchemyDictEncoder.encode(...)`.
- Reads from other processes are fine (SQLite allows many readers). Writers are the
  API process, scheduler, and workers — keep write transactions short.

### Migrations (Alembic)

- Migration scripts live in `db_context/sqlite/alembic/versions/`; the server runs
  `alembic upgrade head` on every start (`migrations.run_migrations`). The PyInstaller
  spec bundles the `alembic/` folder — new files there ship automatically.
- `env.py` uses `render_as_batch=True` (required for SQLite `ALTER`). Autogenerate
  cannot detect renames, anonymous constraints or CHECK constraints — write those by
  hand (see `000976b1cd64_renaming_job_table.py`, `35d235813b7a_...`).
- New model → import + add to `models/sqlite/__init__.py.__all__`, else autogenerate
  will not see it.

## 3. HDF5 experiment-data layout (contract with frontend + client)

File: `<config.data.results_dir>/<JobRun.scheduled_time ISO>.h5` (one per job run).
Written by `ExperimentDataRepository`; read by `load_experiment_data` and served through
`ExperimentDataController.get_experiment_data_by_job_id` as `ExperimentData` (dataclass in
`experiment_data.py`).

```
attrs: number_of_data_points, number_of_shots, experiment_id, job_id, repetitions,
       realtime_scan, [local_parameter_timestamp]
scan_parameters        structured dataset (n,1): ("timestamp" S26, <variable_id> f8 ...)   [realtime params excluded]
                       attrs: "<Device(name) variable_id>" -> "name=… url=…description=…" per device param
result_channels        structured dataset (n,): (<channel> f8 ...)  attrs["Plot window metadata"] = JSON list[PlotWindowMetadata]
shot_channels/<ch>     dataset (n, number_of_shots) f8                group attrs["Plot window metadata"]
vector_channels/<ch>/<index>   one dataset per data point (variable length)   group attrs["Plot window metadata"]
hardware_instructions  structured (m,): ("index" i4, "Sequence" str)  — appended only when the JSON changed
parameters/<param_id>  structured (k,): ("timestamp" S26, "value" <dtype>) — appended only on value change
fits/<result_channel>  group, attrs["fit_result"] = JSON(FitResult)
```

Rules:

- All datasets are `maxshape=(None, …)`, `chunks=True`, gzip-9; grow with
  `resize_dataset`. Index = data-point index (repetitions are flattened; the frontend
  regroups using `attrs["repetitions"]`).
- Concurrency (since v0.3.0): `h5_open()` takes a **per-file** `threading.RLock`
  (`_file_locks`; guards against libhdf5 segfaults on concurrent in-process access)
  and retries on the **OS file lock** with backoff, bounded by
  `config.data.h5_open_timeout_seconds` (default 30 s) → `TimeoutError`. Keep every
  `with h5_open(...)` block short; never hold it while doing network I/O or emitting.
- `update_metadata_by_job_id` must run before any `write_*` (it creates the datasets and
  attrs; writers raise `KeyError` otherwise).
- Reads are size-capped: `load_experiment_data(max_transfer_bytes=50 MB)` returns only
  the last N points that fit (`total_data_points` tells the client how many exist).
  `hardware_instructions` are excluded unless requested and can be fetched lazily per
  index via `get_hardware_instructions(job_id=…, index=…)`. Preserve all of these
  behaviours.

  > **Design note** (updated for v0.3.0) — the original process-wide global lock
  > was replaced in v0.3.0 by per-file in-process locks plus a bounded OS-lock retry
  > (`h5_open_timeout_seconds`), removing cross-file serialisation. The larger
  > redesign stays the revisit path: storing results in a single database and
  > demoting HDF5 to an **export format** rather than the live store
  > (`NEW_FEATURES.md` → data_access).

## 4. InfluxDB v1 parameter store

- Two parameter schemas exist since v0.3.0 (`db_context/influxdb/parameters_backend.py`):
  **r1** (legacy) stores one field per parameter — field key = the full parameter id —
  in the configured measurement; **r2** stores per-type value fields
  (`icon_parameter_value_{float,int,str,bool}`) in a measurement prefixed `icon|2|`,
  with parameter identity carried entirely by the **tags** (specifiers). At startup
  `assert_parameter_db()` detects the schema and `ParametersRepository` binds the
  matching backend (`ParameterBackendR1`/`R2`); a pristine database gets r2. Migration
  between schemas is the operator-run `icon-migrate-influxdb-schema` CLI (dry-run /
  migrate / rollback) — ICON never migrates parameter data implicitly. New
  reads/writes go through the backend, never raw InfluxQL.
- `InfluxDBv1Session` (context manager). Queries are InfluxQL strings; **always** pass
  names through `escape_quotes`. `query_last(measurement, namespace, before)` returns
  `{field: value}` of `last(*::field)` optionally `WHERE "namespace"='…' AND time <= …` —
  this is how `local_parameters_timestamp` snapshots work (parameters "as of" a time).
- `ParametersRepository` holds the **shared dict** (fast reads for the API, pre-processing
  workers) and writes through to InfluxDB via the active backend. `update_parameters`
  still casts `int → float` unless the id contains `ParameterTypes.INT` — mandatory on
  r1 (field types are fixed per field key; a type flip makes writes fail forever) and
  kept on r2 for cache/value consistency.
- `ParametersController._create_missing_influxdb_entries` seeds new parameters with
  their `default_value` so every id has a series.

  > **Design note** — keep the `Manager().dict()`. Redis/Valkey **was tried and
  > discarded as too slow** for this access pattern; do not reintroduce it. Keep the
  > cache contained in `ParametersRepository` + `SRM` (no direct `_shared_parameters`
  > access outside the repository) so any future backend swap stays contained.

## 5. Experiment-library clients

- Abstract `ExperimentLibraryClient`: `checkout_revision`, `isolated()` (context manager
  returning a per-worker copy), `load_metadata()`, `create_hardware_instructions()`,
  `get_experiment_readout_metadata()`, `get_setup_hardware_description()`. All async.
- `VEnvExperimentLibraryClient` executes a `BlockingExperimentLibraryClient` **inside the
  experiment library's own virtualenv** as a subprocess (`venv_exec.VirtualEnvironment`)
  so pycrystal versions don't collide with ICON's environment. Results cross the
  boundary as JSON/`deep_asdict` (the stale `templates/` folder references were
  removed in v0.3.0).
- `AsyncPyCrystalClient(checkout_path, repo)` = default. `GitRepo.clone()/checkout()`
  give reproducibility: a job with `git_commit_hash` runs on an isolated checkout; a
  job with `debug_mode=True` (no hash) runs on the shared working copy (fast iteration,
  not reproducible) — mirrors the "development mode" the docs asked for.
- `ReconfigurableExperimentLibraryClient` re-imports `config.experiment_library.module`
  /`client_class` when the config changes. This is the current answer to "pluggable
  control systems": a library client is swappable by config, the hardware side by
  `config.hardware.devices[*].controller_module/class`.

## 6. Backwards compatibility for persistent data (mandatory)

Users upgrade ICON binaries in running labs; existing SQLite files, InfluxDB series,
HDF5 result files and browser `localStorage` must keep working. Rules for any PR:

**SQLite (`icon.db`)**
1. Never edit a merged migration. Add a new revision; chain from current head.
2. Additive changes only where possible: new columns get `server_default`/`default` and
   are nullable or defaulted so old rows load. Removing a column requires a migration
   that drops it **and** a code path that tolerates its absence during rollout
   (readers use `SQLAlchemyDictEncoder`, so the frontend must not require the key).
3. Renames = explicit `op.rename_table` / `batch_alter_table … alter_column(new_column_name=…)`,
   never drop+create (data loss).
4. Enum values are stored as strings: adding a `JobRunStatus` member is safe; renaming
   or removing one needs a data migration (`UPDATE … SET status=…`) and frontend enum
   update (`frontend/src/types/enums.ts`) in the same PR.
5. `scheduled_time` uniqueness and the `.h5` filename derivation must stay in sync —
   changing one breaks lookup of every existing result file.
6. Test the migration against a DB created at the previous release (see `tests/CLAUDE.md`).

**InfluxDB (parameter time series)**
7. Parameter identity is the id string emitted by pycrystal: on **r1** it is the
   field key; on **r2** it is rebuilt from the tags —
   `build_parameter_identifier_from_specifiers` ∘ `get_specifiers_from_parameter_identifier`
   must stay a lossless round-trip. Do not post-process/normalise ids in ICON — old
   series become orphans on either schema.
8. Field types are immutable per field key: keep the `int→float` cast in
   `ParametersRepository.update_parameters` and the `ParameterTypes.INT` exception
   (r1), and never re-type the `icon_parameter_value_*` fields (r2).
9. Measurement names (including the `icon|2|` prefix), tag names (`namespace`,
   specifier keys) and the r1/r2 detection in `assert_parameter_db` are contract; any
   change needs a **new schema revision** plus a step in the
   `icon-migrate-influxdb-schema` CLI — never a silent re-interpretation of existing
   databases.

**HDF5 (experiment results)**
10. Never rename or re-type an existing dataset/attr. Add new datasets/attrs and make
    `load_experiment_data` tolerate their absence (it already uses `.get(...)` for every
    group — keep that pattern).
11. The frontend and client read the `ExperimentData` dataclass shape; adding fields
    with defaults is fine, removing/renaming needs a coordinated frontend change and a
    file-format note in `docs/`.
12. Keep `timestamp` as `S26` ISO strings and scan values as `float64`; readers rely on
    `.decode()`/`.item()` distinctions in `load_experiment_data`.
13. Fit results are JSON in attrs: add keys to `FitResult` only with defaults (`FitResult(**json)`
    must not fail on old files).

**Frontend `localStorage`** — see `frontend/CLAUDE.md` §"Persistent browser state".

**Config YAML** — versioned (`icon.config.v1/v2/latest`) with `migrations.py`. Any
schema change to `latest.ServiceConfig` that is not purely additive requires a new
`vN.py` snapshot + migration function; `get_config()` rewrites the user's file after
migrating, so migrations must be lossless.

## 7. Adding things — recipes

- **New table/column**: model → `__init__.py` → `alembic revision --autogenerate` →
  review (batch mode, defaults, indexes) → repository methods (kw-only, emit event) →
  `SQLAlchemyDictEncoder` handles it automatically → frontend type in `frontend/src/types`.
- **New HDF5 dataset**: writer helper `write_<x>_to_dataset(h5file, …)` + call site in
  `write_experiment_data_point`/`prepare_readout_metadata` → reader branch in
  `load_experiment_data` guarded by `.get` → field with default in `ExperimentData` →
  `frontend/src/types/ExperimentData.ts` → socket event if live updates are needed.
- **New experiment-library backend**: subclass `ExperimentLibraryClient` (or
  `BlockingExperimentLibraryClient` for venv isolation), point
  `config.experiment_library.module/client_class/client_args` at it. No ICON core changes
  should be needed; if they are, that is an architecture smell to raise.

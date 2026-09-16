# server — process topology, workers (scheduler / pre / hardware / post) and API

Read `/CLAUDE.md` first; persistence rules are in `data_access/CLAUDE.md`.
This file covers everything that runs inside the ICON server process tree.

## 1. Process topology (what `__main__.start_server()` builds)

```
main process ─ IconServer (pydase + aiohttp + socket.io) ─ APIService
   │             └─ drains emit_queue → socket.io emits (all processes put events there)
   ├─ SharedResourceManager (SRM)  : PriorityQueue pre_processing_queue
   │                                  PriorityQueue hardware_processing_queue (maxsize 10)
   │                                  dict parameters_dict
   ├─ Scheduler                     : polls SQLite every 0.1 s for SUBMITTED jobs
   ├─ PreProcessingWorker × config.server.pre_processing.workers (default 2)
   │      each has: its own multiprocessing.Queue[UpdateQueue] (API→worker events),
   │                per-job manager Queues data_points_to_process / processed_data_points,
   │                a worker-lifetime PriorityQueue outdated_tasks,
   │                an isolated experiment-library checkout
   ├─ HardwareProcessingWorker × 1  : owns pydase clients to devices + the HardwareController
   └─ PostProcessingWorker × 1      : writes data points to HDF5
```

- Queues that both a pre-processing worker and the hardware worker touch are created
  through the **manager** (`SRM.Queue()/PriorityQueue()`) so they can be pickled inside
  a task; plain `multiprocessing.Queue`s are created in `__main__` and handed to
  constructors. Do not create queues elsewhere.
- Task objects are pydantic models (`pre_processing/task.py`, `hardware_processing/task.py`,
  `post_processing/task.py`) with `__lt__` so `PriorityQueue` orders them: pre-processing
  by `priority`; hardware by `(priority, created)`; post by `priority`. **Lower number
  pops first** (0 = most urgent).
- Every worker `run()` is wrapped in `@handle_keyboard_interrupt(logger)` and loops
  forever; `Scheduler.should_exit()` is a stub. There is no graceful shutdown
  (`NEW_FEATURES.md`).

## 2. Job life cycle (the contract every worker change must keep)

```
API submit_job ──► Job(SUBMITTED) + ScanParameters + ExperimentSource in SQLite     [job.new]
Scheduler      ──► Job→PROCESSING, JobRun(PENDING, scheduled_time=now())            [job.update, job_run.new]
               ──► PreProcessingTask into pre_processing_queue
Pre-processing ──► JobRun→PROCESSING; drain update_queue; nice(priority);
                   checkout_revision(git_commit_hash) (debug_mode → shared working copy)
                   _update_parameter_dict(LOCALS_FROM_TS_GLOBALS_LATEST)   ← locals "as of"
                        job.local_parameters_timestamp, globals latest
                   readout metadata → ExperimentDataRepository.update_metadata_by_job_id
                   regular scan: enumerate(get_scan_combinations(job)) → data_points_to_process
                   realtime scan: counter-driven, regenerates JSON when globals change
                   per point: create_hardware_instructions(client, params∪point) → HardwareProcessingTask
Hardware       ──► per task: reload run; CANCELLED/FAILED → ack; should_divert_task → outdated_tasks;
                   set device params (pydase, verify w/ retries) → controller.send/run/receive
                   → PostProcessingTask; on exception JobRun→FAILED (log = extracted message)
                   always: task.processed_data_points.put(task)   ← pre-processing counts these
Post-processing──► if not cancelled/failed: write_experiment_data_by_job_id      [experiment_<id>]
Pre-processing ──► when processed == expected: JobRun→DONE (unless already CANCELLED/FAILED),
                   try_auto_fit(job); finally Job→PROCESSED                       [job.update, job_run.update]
```

Cancellation is **status-driven** and, since v0.3.0, **atomic**: `cancel_job`/
`pause_job`/`resume_job` go through `update_run_by_id(..., only_if_status=…)`
(`UPDATE … WHERE status IN (…) RETURNING`), so concurrent transitions cannot race.
`cancel_job` sets Job→PROCESSED and JobRun→CANCELLED;
every worker checks `job_run_cancelled_or_failed`/the run status before each data point.
No queue purging. Pause/resume works the same way (`JobRun.PAUSED`): the hardware worker
diverts paused tasks to `outdated_tasks`, the pre-processing worker waits in
`_wait_while_paused` (still draining parameter updates) and then `_regenerate_outdated_jobs`.

Parameter updates mid-scan: `ScansController.trigger_update_job_params(job_id)` (or a
`"calibration"` event with `new_parameters`) is put on **every** pre-processing
`update_queue`; the worker owning the job refreshes `_parameter_dict`, stamps
`JobRun.parameter_update_timestamp`, writes the change to HDF5 `parameters/`, and the
hardware worker diverts tasks whose `created < parameter_update_timestamp` back for
regeneration (realtime scans regenerate in place instead).

## 3. Deviations from the design docs (do not "restore" these without a decision)

| Docs (2023–24) | Code |
|---|---|
| Scheduler runs periodic/interval jobs, `type` continuous/calibration, re-schedules continuous jobs after restart | Single-shot jobs only; realtime scans are "continuous"; restart cancels every non-finished run (`initialise_job_tables`) |
| Hardware worker retries data points, `retry_count` in history | No data-point retries; a hardware exception fails the run. Only device set-value verification retries (`Device.retry_attempts`) |
| Hardware worker requeues stale tasks into the **pre-processing queue** | Stale/paused tasks go to the owning worker's `outdated_tasks` and are regenerated by the same worker (keeps `_parameter_dict` and library checkout local) |
| Globals timestamp as a `multiprocessing.Value` shared variable | `JobRun.parameter_update_timestamp` column in SQLite; hardware worker re-reads the run per task (~ms) |
| Post-processing worker performs fits and updates InfluxDB (calibration) | Post-processing only persists data. Fits: `server/fitting` run in the pre-processing worker after the run (`try_auto_fit`, copies the previous job's fit model) and on demand via `data.run_fit`. **No parameter write-back** (`auto_calibration` is stored but unused) |
| Multiple post-processing workers, "processed data points" queue from post→pre | One post-processing worker; the **hardware** worker acks to pre-processing via `processed_data_points` |
| Hardware worker keeps a temp dir / src_dir per continuous experiment | `src_dir` is the checkout path chosen by the pre-processing client; hardware/post workers just carry it |
| Bayesian/adaptive scans via post→pre feedback | Not implemented |

> **Design note** — fitting stays in the **pre-processing** worker for now, with
> the known costs (JSON generation blocks on scipy after a run; no access to the
> experiment's own analysis code). This placement must be **revisited when the full
> calibration model is implemented** (`NEW_FEATURES.md` → "Calibration workflow
> design"). Do not grow calibration logic in the pre-processing worker meanwhile.

> **Design note** — keep `HARDWARE_PROCESSING_QUEUE_MAX_SIZE = 10` and one JSON
> generator per worker; tune `config.server.pre_processing.workers` per lab instead.
> The queue system needs investigation (deadtime benchmark, `NEW_FEATURES.md` →
> testing) **before** any change to sizes or generator pools — never as a side
> effect of another PR.

> **Design note** — the hardware worker is **singular by design: exactly one
> exists, ever**. This is an invariant, not a tuning knob. Multiple hardware
> *controllers* and multiple devices can and do exist; the single
> `HardwareProcessingWorker` coordinates all of them through the
> `HardwareController` abstraction, which is what guarantees exclusive hardware
> access and `scheduled_time` uniqueness. Never introduce a worker count for it in
> config or `__main__`.

## 4. Module-level rules

**scheduler/** — Only reads `SUBMITTED` jobs, creates the run, builds
`PreProcessingTask` from the ORM objects (detached, relationships preloaded). On any
failure it reverts the job to `SUBMITTED`. Keep it free of experiment-library calls.

**pre_processing/** — All experiment-library interaction goes through the
`ExperimentLibraryClient` passed in; `asyncio.run(...)` per call is the existing pattern
(the worker itself is sync). `ExperimentIdentifier.from_str` is the single parser of
`experiment_id`; `parameter_namespace`/`is_global_parameter` are the single deciders
of the local/global parameter split. `get_scan_combinations` flattens `itertools.product` × `repetitions`
and excludes realtime params. Any new scan mode is a new `_handle_<mode>_scan` generator
yielding once per submitted point so `_regenerate_outdated_jobs` runs between points.

**hardware_processing/** — `HardwareController` (`connect/connected/send/run/status/receive`)
is the hardware plug-in interface; implementations are selected by
`config.hardware.devices[]` (`controller_module`, `controller_class`, `args`, `enabled`)
and hot-reloaded by `Devices` (`DictReloader`). Two Zedboard controllers ship since
v0.3.0: `zedboard_controller.ZedboardController` (default) speaks the Zedboard's
msgpack RPC protocol through the bundled `hardware_processing/rpc/` client and needs
**no extra**; `tiqizedboard_controller.ZedboardController` wraps the legacy
`tiqi-zedboard` package (`zedboard` extra, ETH GitLab SSH).
`FallbackHardwareController` is the
no-op used when nothing is enabled — tests rely on it. `parse_parameter_id` defines the
`"Device(<name>) <access_path>"` convention shared with `ScanParameter.unique_id()` and
the frontend. Device values are set through `pydase.Client` with
`client_call_with_timeout` (`config.devices.set_value_timeout_seconds`).

**post_processing/** — Deliberately thin. If it grows (fits, calibration), keep it a
consumer of `PostProcessingTask` only.

**fitting/** — Pure functions on numpy arrays (`run_curve_fit`), models registered in
`models.py` (`FitModel` with `guess`/`derived`). Add a model = add an entry; the frontend
list in `frontend/src/utils/fitFunctions.ts` must match `func_type` names.

**api/** — Each controller is a `pydase.DataService`; public methods are the API
(names become `access_path`s like `"scheduler.submit_job"`). Conventions:
- `async def` for anything touching HDF5/InfluxDB (`asyncio.to_thread` for blocking
  repository calls); sync methods for quick SQLite reads.
- Keyword-only parameters; return plain dicts/dataclasses/ORM objects — the patched
  `icon.serialization` handles ORM, enums, datetimes.
- Validate at the API boundary and raise `ValueError` with a user-facing message
  (`submit_job` takes `experiment_id: str` since v0.3.0 and creates the
  `ExperimentSource` itself; it checks realtime/repetition rules and casts scan
  values to the parameter's type before persisting).
- Background sync (`@task(autostart=True)`) lives in `APIService`: metadata refresh
  every `experiment_library.update_interval`, `ParametersRepository` initialisation
  retry, status checks in `StatusController`.
- List views paginate: `scheduler.get_job_list(before_id=…, limit=…)` returns slim
  `JobListItemDict`s (page size 100, newest first, ~5x smaller on the wire than
  `get_scheduled_jobs`). Extend the TypedDict rather than sending ORM dumps to lists.
- Controllers never emit socket events directly for data changes — repositories do.
  They may emit UI-only events (`experiment_fit_<id>`, `parameters.update`).

**web_server/** — `IconServer` subclasses `pydase.Server` with `frontend_src` =
built assets, patches serialization (`patch_serialization_methods`) and sio setup
(`patch_sio_setup`, control-lock `take_control`/`release_control`/`control_state`, device
update rooms). `visualiser.patch_web_server()` (v0.3.0) adds an aiohttp middleware
that serves the ionpulse **sequence visualizer** build from
`src/icon/server/frontend_visualizer/` (source: the `frontend/sequence-visualizer`
git submodule). `socketio_emit_queue.emit_queue` is a process-safe queue; a task in the
server drains it. Put events, never call `sio.emit` from workers.

## 5. PR validation checklist (workers/API)

- [ ] New worker state is either in the task object, SQLite, or a queue created in
      `__main__`/SRM.
- [ ] Every loop that waits on hardware or a queue re-checks run status (cancel/pause).
- [ ] `processed_data_points` gets exactly one ack per submitted `HardwareProcessingTask`
      on every path (success, failure, cancel, divert-then-regenerate).
- [ ] `JobRun` status transitions stay monotonic: `PENDING→PROCESSING⇄PAUSED→{DONE,FAILED,CANCELLED}`;
      `Job` ends `PROCESSED` in `finally`.
- [ ] Timestamps use the config timezone; comparisons with
      `parameter_update_timestamp` go through `.replace(tzinfo=UTC)`.
- [ ] New config keys added to `icon/config/latest.py` with defaults (see data_access
      §6 for versioning) and surfaced in `frontend/src/types/Configuration.ts` if editable.
- [ ] New API method documented (Google docstring → mkdocstrings) and, if the frontend
      calls it, added to the socket helper in `frontend/src/utils/`.
- [ ] `tests/server/pre_processing/test_worker.py`-style test for any change to
      divert/regenerate/pause logic (they run without hardware or DB).

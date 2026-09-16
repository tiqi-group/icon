# NEW_FEATURES — design-document features not (yet) in the code

Companion to `CLAUDE.md` and the unit files. Everything here comes from the
requirements/design documents (Confluence 2023-09/2024-01/2024-03, `ICON Databases`,
the Notion project pages and 2024/2025 roadmap) and is **not implemented** as of
**v0.3.0** (= `main`, 2026-09-14). Items are grouped by design unit; priorities in parentheses are the ones the
roadmap gave. Design questions from the first draft were reconciled — the outcomes
live as **Design note** blocks in the unit `CLAUDE.md` files; items marked
*[revisit: calibration workflow]* reopen together when that design happens.

Keep this file honest: when a PR implements something, delete the item (or move it to
the relevant unit file as documented behaviour). When a PR consciously rejects an item,
remove it and note the decision in the PR.

## Calibration workflow design — bundled revisit

Several decisions were deliberately deferred until the full calibration workflow is
designed. When that design happens, reopen these together:

- Fit / calibration write-back placement — currently the pre-processing worker.
- Job ↔ run cardinality and clone-on-resubmit via `parent_job_id`.
- Continuous / periodic / calibration job types — time-as-parameter stays; periodic
  jobs by services resubmitting, the docs' preferred variant.
- Bayesian / adaptive scan feedback path — none for now.
- The calibration items below: write-back, calibration trees, scripted exclusive
  mode, the unused `auto_calibration` flag.

---

## data_access (server)

**Tables / schema**
- `User` table and `Job.user_id` (2024-03 ER diagram; "Job database might have user").
  Today jobs are anonymous; the control-lock identifies a socket, not a person.
- ~~`RemoteSource`/remote-source table separate from `devices`~~ **Rejected**:
  `devices` stays pydase-only ("device = DataService" — slow devices without realtime
  capability). Realtime-capable hardware (Zedboard, RFSoC, Fastino, …) is controlled
  via `HardwareController`s in `config.hardware`, not database rows. No `type`
  column, no new table.
- Job `type` column (`scan | continuous | calibration`) and `interval` for periodic
  jobs (2024-01/03). Reconciled: keep time-as-parameter; periodic jobs are
  handled by **services resubmitting** (the docs' preferred variant) — no schema
  change. *[revisit: calibration workflow]*
- Separate `job_execution_history` with many runs per job, commit hash stored on the
  history row not the job, "rank jobs by number of executions / recency" (2024-03
  rescheduling discussion). Reconciled: keep 1:1 clone-on-resubmit
  (`parent_job_id`; simple, one HDF5 file per run already works).
  *[revisit: calibration workflow]*
- `retry_count` on runs / job-level retries (2024-01 concluded "probably not
  necessary"; shots are retried on the Zedboard). Only device set-value retries exist.
- "Manual scan"/single-data-point jobs: explicit `manual_scan` column (roadmap 2025,
  option 3) so the API can reject unsupported params instead of failing the run.
- Store user **comments** in the HDF5 file + comments section on the job page
  (medium-low).
- Store **display names** of scan parameters/channels in the HDF5 file so axis labels
  use them (medium). `ScanParameter.name` is persisted in SQLite already; HDF5 attrs
  still key by `variable_id`.
- "Store index instead of timestamp for parameters?" in HDF5 `parameters/` — depends on
  how stale global timestamps are handled (roadmap, undecided).
- `invalid data > invalid result channels` dataset for redone data points (see workers).
- Alembic migration tests with `pytest-alembic`.

**Caches / databases**
- ~~Valkey (Redis) as the shared parameter cache~~ **Rejected**: Redis was
  tried and discarded as too slow for this access pattern; the `Manager().dict()`
  stays. (The hashsets-per-group / namespace-timestamp scheme from 2024-03 goes with
  it; namespace timestamps would need another home if ever revived.)
- InfluxDB: query "all parameters between start and stop" for history views (only
  `last()` queries exist).
- Local-parameter semantics from 2024-03: locals read **once** per experiment at the
  timestamp; continuous scans should re-read locals so plots keep running on change.
  Partially covered by the update-queue mechanism; no explicit "locals live in the
  pre-processing worker" separation.
- Single results **database** with HDF5 demoted to an export format — the agreed
  revisit path agreed for the HDF5 locking design. Needs a data model for
  points/shots/vectors, an exporter reproducing today's file layout, and a migration
  story for existing `.h5` files.
- Unix-socket / in-memory DB options for latency (2024-01 "deadtime ≤ 10 %" mock-up
  was requested, never done). Needs a benchmark of DB round-trips per data point.

**Experiment library**
- `ExperimentMetadata` merged into `Experiment(file_path, git_commit_hash)` with
  `file_path` relative to the experiment folder (2024-03). Today ids are pycrystal
  strings.
- Pluggable control systems (Notion): plugin/provider config (`plugins:`/`providers:`
  YAML, versioned repos, `pullInterval`), tracked in SQLite. Today: swappable client
  class + hardware controllers via config, no plugin registry.
- Computed parameters (`ComputedParameter`, dependency tracking via AST) and
  `EnumParameter` serialisation — pycrystal-side items that ICON's metadata pipeline and
  frontend would need to render.

---

## workers (scheduler, pre-processing, hardware, post-processing)

**Scheduler**
- Periodic / interval jobs and "services could submit periodic calibrations"
  (2024-01). Reconciled: **services resubmit** (many job rows accepted); no
  scheduler-internal timer. *[revisit: calibration workflow]*
- Scripted calibration mode that "stops everything in the queue and only runs the
  experiments submitted with the script" (calibration tree / scripting, 2024-01) — an
  exclusive-queue or priority-override mechanism.
- Re-schedule continuous jobs after a server restart (2024-03 state diagram). Today
  they are cancelled at startup.
- Clean shutdown: `should_exit()` is a stub; workers loop forever (Notion "Scheduler
  Implementation").
- Uninterruptable scans / "pause all other experiments" (low).
- Reschedule with "old locals but current globals" vs "everything old" (reschedule
  button, low). `ParamUpdateMode` already has the modes; the API only exposes clone.

**Pre-processing**
- Multiple JSON generators per worker ("threads/processes; I/O bound as they spawn
  subprocesses", medium-high) and "only submit the next index to the hardware queue".
  Blocked on investigation: benchmark deadtime first; interacts with
  `HARDWARE_PROCESSING_QUEUE_MAX_SIZE` and the ack invariant.
- Tell the hardware worker which timestamps must be redone when too many JSONs were
  generated before an `update_queue` event took effect (low) — today the
  `parameter_update_timestamp` divert handles the common case.
- Hardware worker check that a task's generation timestamp is current via SQLite
  (low) — implemented as `should_divert_task`; remaining gap is for realtime scans.
- Single data points / manual control (medium): reuse continuous-scan logic, pass new
  scan parameters through `update_queue` events.
- Redo data points (medium): pause, "redo n points", auto-resume; invalid points moved
  to an `invalid data` HDF5 group.
- Continuous **2D** scans (y = time, x = scanned parameter) (low).

**Post-processing / calibration**
- Post-processing worker performs the fit defined by the user's experiment
  (`fit` + list of `(parameter, value)` pairs; "can return any parameter, e.g. fit
  A+B, return A+C") and, when `Job.auto_calibration` is set, **writes the parameters
  back** to InfluxDB and the cache, then updates the pre-processing worker
  (`globals_timestamp`) (2024-01/03). Today fits are generic scipy models chosen in the
  GUI; `auto_calibration` is stored but ignored. Open question for the calibration
  design: where does the user's fit code run (needs the library venv →
  post-processing has `src_dir`)? *[revisit: calibration workflow]*
- Calibration self-rescheduling on failure; "check whether a calibration has to run"
  predicate; calibration tree structures (2024-01).
- Bayesian / adaptive scans (Notion "Bayesian Estimation"): post-processing queues the
  next point with changed values into pre-processing; alternative "estimate on the
  controller". Reconciled: none for now; 2024-01's four options all stay on
  the table. *[revisit: calibration workflow]*
- Multiple post-processing workers (docs; overview diagram shows "Workers").

**Hardware**
- Decrystallisation handling on the Zedboard (2024-03): ionpulse SDK support, user
  script executed immediately when ions decrystallise, stored on the Zedboard.
- Rounding-tolerant device value verification (`# TODO: check for rounding errors` in
  `hardware_processing/worker.py`).

**API server**
- Job proxy for scripting: subscribe to new data points, get status, cancel /
  reschedule (2024-03 "Job proxy is the main thing for scripting"). Partially
  covered by `experiment_<id>` events; no dedicated proxy object server-side.
- `get_scheduled_jobs(before, after, names)` filters (2024-03 "before/after
  timestamp? names?").
- Logs endpoint: configurable number of retained log entries and level, `SocketioHandler`
  emitting ≥ INFO (low; frontend "logs page").
- Read-only frontend status for DB outages instead of exceptions (partly done via
  `status.*` events; the design wanted no exceptions at all).

---

## frontend (GUI)

- Multiple plot windows taken from the pycrystal `Readout` representation (**HIGH**):
  server sends window metadata (done: `experiment_<id>_metadata`), frontend needs
  default positioning by pycrystal index, minimisable plots, "edit view" (rearrange /
  resize / hide, low).
- Histogram plot for shot channels (**high**): one histogram for all shot channels.
- Parameter components on the job page showing the **worker's** values, highlighting
  in orange when they differ from the global value with a tooltip (low).
- Info card on the job page with "important information" (only the cancel button
  exists).
- Displaying repetitions: "directly merge" default plus alternatives (medium).
- Axis labelling with display names (medium) — needs HDF5 display names (data_access).
- Scan options (medium-low): look at Ionizer's options; `scanPatterns` currently
  `linear | scatter | centred | forwardReverse`; "scan repetitions is not a thing for
  continuous scans" (hide the field).
- `ScanInterface` validation: parameter cards validate input and the interface refuses
  to submit until every card is error-free (partially: priority/shots validated).
- Logs page (low): choosable retained entries (default ~1000) and level.
- Moving-window plot area (medium-high): "show last N data points" number component,
  toolbar button, y-axis min/max with reset (server side already truncates by bytes;
  GUI needs the N-points control — `windowSize_*` localStorage key suggests this is in
  progress).
- Redo data points UI (medium) and pause/resume of *all* experiments (low).
- Annotating data (low).
- Only load n data points / skip loading files that are too large (server cap exists;
  add a GUI hint + "load more").
- Reschedule button with old-locals/current-globals choice (low).
- Device parameter sections inside experiments (low).
- Debug changing parameters during a 2D scan (open bug from roadmap).
- Job windows: "always on top" and "remove URL bar" were found impossible in
  Chrome/Firefox — drop from scope.
- Design inspiration noted in docs: Riverlane Aqueduct.

---

## client (Python)

- General client rework: the client needs a dedicated work package — rewrite
  `api/scheduler_controller.py` (re-synced with the server API in v0.3.0, still
  unwired) into a data/plot proxy and pick up the items below together rather than
  piecemeal.
- Live plotting in Jupyter and CLI (`client` extra: `ipympl`, `matplotlib`):
  1D/2D/nD, live scan and past experiments (roadmap "Python → plotting", all open).
  Existing `api/scheduler_controller.py` prototype is stale — rewrite against
  `data.get_experiment_data_by_job_id` + `experiment_<id>` events.
- Scan value generation on the client: `values` as `{start, stop, num_points}` or
  list, reverse/random patterns, nD scans by passing several parameters (roadmap says
  done for lists; the dict form in the docstring is **not** implemented in
  `ExperimentProxy.schedule`).
- Reference parameters without passing ids manually (proxy objects — done) and
  `device_name` inference from a device-parameter proxy.
- Scanning requirements (Notion "Scanning API"): schedule multiple scans and see plots
  automatically; buttons to start / stop / **accept fit**; set repetitions (done).
- Future-like object that also gives data (`ExperimentJobProxy.data()`), cancel /
  reschedule (2023-09 "returns a future object … information about the scan from the
  Data Service").
- Good API inspired by `rt-setup-automations/experiment_controller.py` (Notion note).

---

## testing

- ~~CI job running `pytest -m "not container"` on every PR~~ **Done in v0.3.0**
  (`test.yaml`, Python 3.11–3.13, UI assets prebuilt). Still open: frontend
  lint/jest in CI and a nightly/optional `container` run with podman
  (`k8s/dev.yml`).
- Template `tests/config.yaml` from `mock_config()` so no developer-specific absolute
  paths or lab-specific URLs ship in the repo.
- `pytest-alembic` (or hand-written) migration tests against a previous-release DB.
- Fixture HDF5 files from previous releases for format-compatibility tests.
- End-to-end test: Fallback hardware controller + mock experiment library + real
  SQLite/HDF5, exercising submit → realtime scan → parameter update → pause/resume →
  cancel, asserting the socket events and the resulting HDF5 file.
- Database-latency benchmark ("how long from clicking run until data comes back,
  excluding HW delay", 2024-01) as a reproducible script.
- Frontend component tests (React Testing Library) — none exist; only pure utils.
- Frontend `pnpm lint` + `pnpm test` in CI (only `build-ui.yml` runs in CI today).

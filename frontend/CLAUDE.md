# frontend — React GUI

Read `/CLAUDE.md` first. Since v0.3.0 `frontend/` is a **pnpm workspace**
(`packageManager: pnpm`, Node 26): the `icon/` package is the GUI — Vite + React 19 +
TypeScript with MUI 7, `@toolpad/core` (dashboard layout, notifications), ECharts 6
(plots), react-router 7, react-window and socket.io-client — and
`sequence-visualizer/` is a **git submodule** (ionpulse-sequence-visualiser; clone
with `--recursive`). `pnpm build` builds both into `src/icon/server/frontend/` and
`src/icon/server/frontend_visualizer/`, which the Python server serves; those build
outputs are **gitignored and never committed** (CI builds them via `build-ui.yml`).

```
frontend/
├── package.json + pnpm-workspace.yaml   workspace scripts: dev/lint/test target the icon package; build = icon + visualizer
├── sequence-visualizer/    git submodule — never edit here; contribute upstream, bump the pointer deliberately
└── icon/
    ├── src/
    │   ├── main.tsx        createBrowserRouter: "/" (dashboard: "", parameters, experiments, data, devices, settings), "/visualiser", and "/data/:jobId" (job-viewer layout, separate browser window)
    │   ├── App.tsx         Toolpad navigation + providers
    │   ├── socket.ts       the ONE socket.io connection; getValue / updateValue / runMethod helpers
    │   ├── components/     UI (scanInterface/, jobView/, devices/, parameterComponents/, settings/, statusCards/, ConnectionIndicator)
    │   ├── contexts/       Experiments, Jobs, Devices, ParameterDisplayGroups, ParameterStore, Scan
    │   ├── hooks/          useX; data-sync hooks subscribe to socket events (useJobsSync, useDevicesSync, useSocketConnected, …)
    │   ├── stores/         parmeterStore.ts — external store (Map + per-key listeners) for useSyncExternalStore
    │   ├── types/          mirrors of server dataclasses/dicts (Job, JobRun, JobListItem, ExperimentData, enums, …)
    │   ├── utils/          pure helpers: submitJob, cancel/pause/resumeJob, deserializer, scanUtils, fitFunctions, windowUtils, chartLayout
    │   └── layouts/        dashboard.tsx, job-viewer.tsx, toolbar-actions/
    ├── tests/              jest (ts-jest, node env) for utils/ and hook reducers
    ├── eslint.config.js, .prettierrc, tsconfig.json, jest.config.js, vite.config.ts (outDir ../../src/icon/server/frontend)
```

Commands (from `frontend/`): `pnpm install`, then `pnpm dev` (talks to
`localhost:8004`), `pnpm lint`, `pnpm test`, `pnpm build` (runs `tsc -b` first — type
errors fail the build — and also builds the sequence visualizer).

## 1. How the GUI talks to the server (contract)

Everything goes over the single socket in `socket.ts`:

- `runMethod("<controller>.<method>", args, kwargs, cb)` → pydase `trigger_method`.
  Access paths in use: `scheduler.submit_job|cancel_job|pause_job|resume_job|get_scheduled_jobs|get_job_list|get_job_by_id|get_job_run_by_id`,
  `parameters.get_all_parameters|get_display_groups|update_parameter_by_id`,
  `experiments.get_experiments|get_hardware_description`, `devices.*`, `config.get_config|update_config_option`,
  `data.get_experiment_data_by_job_id|run_fit|delete_fit`, `scans.trigger_update_job_params`, `status.get_status`.
- `getValue` / `updateValue` for pydase attributes (e.g. `experiments.hardware_description`).
- Payloads are pydase-serialized objects; use `utils/deserializer.ts` / `serializationUtils.ts`
  (unit-tested) — never hand-roll `{type, value}` objects.
- Control lock: `take_control` / `release_control` emits, `control_state` event; components
  that mutate server state must respect `useControlState()` (`OverlayLock`).

Server → client events the GUI subscribes to (keep in sync with `emit_queue` producers):

| Event | Payload | Consumer |
|---|---|---|
| `job.new`, `job.update`, `job_run.new`, `job_run.update` | `{job}` / `{job_run}` dicts (`SQLAlchemyDictEncoder`) | `useJobsSync` → `JobsContext` — live updates layered over pages fetched with `scheduler.get_job_list` (`JobListItemDict`, newest first, `before_id` cursor) |
| `parameter.update` | `{id, value}` | parameter store (`bulkSet`/`set`) |
| `parameters.update` | `null` — metadata/display groups changed, refetch | `useParameterDisplayGroups` |
| `experiments.update` | experiment dict | `useExperiments` |
| `device.new`, `device.update` (+ rooms `subscribe_device_updates`) | device dicts | `useDevicesSync`, `Device.tsx` |
| `config.update` | full config dump | `useConfiguration` |
| `status.influxdb`, `status.hardware` | bool / `HardwareStatus` | status cards |
| `experiment_<jobId>` | `ExperimentDataPoint` | `useExperimentData` (live plot) |
| `experiment_<jobId>_metadata` | `{readout_metadata: {result_channels, shot_channels, vector_channels}}` | plot windows |
| `experiment_params_<jobId>` | `{param_id: {timestamp, value}}` | job parameter display |
| `experiment_fit_<jobId>` | `FitResult` or `{result_channel, deleted: true}` | fit overlay |
| `control_state`, `notify` | | lock overlay, Toolpad notifications |

Adding a server event = add a row here, a type in `types/`, and a hook that
`socket.on(...)`s in a `useEffect` with matching `socket.off` cleanup.

## 2. State-management conventions (from the Nov-2024 frontend design)

- Parameter values are hot (hundreds of ids, updates every scan point). They live in
  the **external store** (`stores/parmeterStore.ts`) and components read a single key
  with `useParameter(id)` (`useSyncExternalStore`). Never put the whole parameter map
  in React state or a context value — that was the re-render problem the design
  explicitly solved.
- Contexts carry *structure* (experiments, display groups, jobs, devices); pass explicit
  props down; wrap leaf parameter components in `React.memo`.
- Scan-interface state per experiment is a reducer (`useScanInfoState`) persisted to
  `localStorage` (see §4). Scan values are generated client-side
  (`submitJob.generateScanValues`: `linear | scatter | centred | forwardReverse`) and sent
  as explicit `values` lists; realtime uses `{n_scan_points}`.
- Plots: `ReactEcharts` wrapper; build series with `buildResultChannelChartSeries`;
  repetitions are regrouped client-side from `attrs.repetitions`.
- Job windows: `openJobWindow` opens `/data/<jobId>` with `window.open` named
  `jobWindow:<experimentId>[:<jobId>]`; bounds are restored from `localStorage`.

## 3. Deviations from the design docs

| Docs | Code |
|---|---|
| Matplotlib/"Aqueduct-inspired" GUI, GUI generated from serialized experiment metadata | Toolpad dashboard; experiments/parameters rendered from `get_experiments`/`get_display_groups` metadata (that part matches) |
| Job table + history table browsing, "rank by executions" | Data page lists jobs by status (`get_scheduled_jobs`), one run per job |
| Scan type selector scan/continuous | "Real Time" pseudo-parameter with `n_scan_points` (0 = continuous) |
| Parameter table shows remote sources | Devices page (pydase services) + scannable device parameters in the scan interface |

> **Design note** — 0 = most urgent; the valid range is `0..20`. Widen the
> priority input validation from `1..20` to `0..20` (scan-interface validation and
> defaults) when touching that component; the server semantics stay as they are.

## 4. Persistent browser state (`localStorage`) — backwards compatibility

`localStorage` is user data that survives ICON upgrades. Existing keys:

| Key | Format | Writer |
|---|---|---|
| `scanInfoState:<experimentId>` | JSON `ScanInfoState` `{priority, shots, repetitions, parameters[], history}` | `useScanInfoState` |
| `jobWindow:<experimentId>` | JSON `{width,height,left,top}` | `pages/job-viewer.tsx`, `windowUtils` |
| `separateJobWindows`, `openExperimentWindows` | `"true"`/`"false"` strings | `useBrowserSetting`, `windowUtils` |
| `showRepetitions` | JSON bool | `JobView` |
| `shotChannelsState_<experiment_source_id>`, `resultChannelsState_<experiment_source_id>` | JSON `{[channel]: bool}` | `JobView` |
| `windowSize_<experiment_source_id>`, `yMin_<…>`, `yMax_<…>` | number as string | `JobView` |
| `libraryAddress`, `libraryPort` | hostname string / port string | `pages/visualiser.tsx`, `windowUtils` — seeded before opening the sequence-visualizer page/popup, which reads them (same origin, shared `localStorage`); the keys belong to the submodule app |

Rules:
1. Never rename a key or change its serialized shape without a **read-side migration**:
   read old key/shape, convert, write new, then delete old (do it lazily in the reader,
   like `useScanInfoState` does for the missing `history` field).
2. Readers must tolerate missing/extra fields (`restored.history ?? emptyScanInfoHistory`
   pattern) and invalid JSON (wrap `JSON.parse` in try/catch → default).
3. Prefer namespaced keys `feature:<scope>` for new state (the `_<id>` suffix keys are
   legacy — do not add more of that style).
4. `experiment_source_id` (integer PK) and `experimentId` (string) are **different
   scopes**; keys must say which one they use. Deleting a DB row orphans the
   `_<experiment_source_id>` keys — acceptable, but don't rely on them existing.
5. Do not store secrets or server config in `localStorage`; server config is edited via
   `config.update_config_option`.
6. When `ScanInfoState` gains fields, bump nothing — just default them; if a field
   changes meaning, add a `version` field and migrate in `getScanInfoStateFromLocalStorage`.
7. Unit-test the migration in `frontend/tests/hooks/` (the reducer tests are the model).

## 5. Conventions and PR checklist

- Components: `PascalCase.tsx`, one exported component per file, props interface named
  `<Component>Props`. Hooks `useX.tsx` in `hooks/`. Pure logic in `utils/` with a jest
  test next to it in `tests/utils/`.
- No `any` (`@typescript-eslint` recommended); use the `SerializedObject` types. Existing
  `eslint-disable` for `window as any` in `socket.ts` is the only accepted exception.
- MUI `sx` props over custom CSS; Toolpad `useNotifications` for user feedback; errors
  from `runMethod` callbacks are surfaced, not swallowed.
- Socket subscriptions always in `useEffect` with cleanup; use the `experiment_<id>`
  rooms via `useExperimentData` rather than raw `socket.on` in components.
- `console.log` is stripped in production builds (`esbuild.pure`); use `console.debug`
  / `console.error` deliberately.
- Checklist: `pnpm lint` clean, `pnpm test` green, `pnpm build` succeeds (CI builds
  the shipped assets — never commit `src/icon/server/frontend{,_visualizer}/`),
  `types/` updated when a server payload changed, `localStorage` rules above
  followed, new server API names added to §1 table, submodule pointer bumped only
  deliberately.

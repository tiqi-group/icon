# client — Python scripting client

Read `/CLAUDE.md` first. The client is what users import in scripts / Jupyter to drive
ICON: list experiments, read/write parameters, schedule scans, wait for results. It
must work with **only** the base install (`uv sync` without `--extra server`); the
`client` extra adds notebook/plotting deps (`ipympl`, `matplotlib`, `notebook`, `pandas`).

```
client/
├── client.py                  Client(pydase.Client): thread-owned asyncio loop; get_value / update_value / trigger_method
└── api/
    ├── experiments_controller.py  ExperimentsController → ExperimentProxy → DisplayGroupProxy → ParameterProxy
    │                               ExperimentJobProxy (status / run / wait / cancel), name-shortening helpers
    ├── parameters_controller.py   ParametersController → DisplayGroupProxy (global display groups)
    ├── scheduler_controller.py    JobProxy with matplotlib live plot (unwired prototype, see §2)
    └── helpers/notebook.py        in_notebook()
```

Typical use (this is the API to preserve):

```python
from icon.client.client import Client

client = Client(url="ws://icon-host:8004")
client.experiments                          # repr lists short names → full experiment ids
ramsey = client.experiments["Ramsey 1"]     # ExperimentProxy
ramsey["Local Parameters"]["Pulse time"].value = 10.0   # ParameterProxy → parameters.update_parameter_by_id
client.parameters["Global Parameters"]["Detection time"].value

job = ramsey.schedule(
    scan_parameters=[{"parameter": ramsey["Local Parameters"]["Pulse time"],
                      "values": [1, 2, 3], "device_name": None}],
    priority=20, repetitions=1, number_of_shots=50, git_commit_hash=None,
)
job.wait()          # polls scheduler.get_job_by_id; raises RuntimeError with JobRun.log on FAILED/CANCELLED
job.cancel()
```

## 1. Design rules

- The client is a **thin proxy over the server API**: every operation is a
  `trigger_method("<controller>.<method>", kwargs=…)` call; no business logic that the
  server also has. If you need a new capability, add it to the server controller first,
  then expose it here with the same name.
- Keep calls synchronous for the user. `Client` runs the socket.io client on a
  background thread with its own event loop; `trigger_method`/`get_value`/`update_value`
  bridge with `asyncio.run_coroutine_threadsafe(...).result()`. The loop is exposed as
  the public `Client.event_loop` property since v0.3.0 (raises `RuntimeError` when
  disconnected) — use it, never `_loop`. Do not expose coroutines in the public API.
- Serialization: always through `icon.serialization.dump/loads` (shared with the server
  and the patched pydase endpoints). Don't import anything from `icon.server` at
  runtime in client modules except type-only imports under `TYPE_CHECKING`
  (`experiments_controller.py` imports `ExperimentMetadata`/`ParameterMetadata` types —
  keep such imports lightweight; the server extras are not installed on client machines).
- Identifiers: server ids are long (`"<module>.<Class> (<instance>)"`, display-group
  keys, `namespace='…' parameter_group='…' param_type='…'`). The client offers
  **short names** via `get_experiment_identifier_dict`, `get_display_group_identifier_dict`,
  `get_parameter_identifier_mapping` (unique short → full, falling back to longer forms on
  collisions). These helpers are pure and unit-tested in `tests/client/api/`; extend them
  with parametrized cases, never change collision behaviour silently.
- `ScanParameter` (TypedDict) is the scan spec: `parameter` (proxy or full id),
  `values` (explicit list), `device_name` (None for InfluxDB parameters). Value
  generation (start/stop/points, patterns) is **not** in the client today — the design
  roadmap wanted it (`NEW_FEATURES.md`); if added, keep explicit `values` as the wire
  format so the server contract (`api/models/scan_parameter.py`) is unchanged.
- Statuses are mirrored enums (`JobStatus`, `RunStatus`) built from the server strings
  with `Enum[name.upper()]`; adding a server status requires adding it here or `wait()`
  raises `KeyError`.
- `local_parameters_timestamp` defaults to `now()` on the client; this is what pins the
  "local parameters as of" snapshot server-side.

## 2. Deviations / stale pieces

| Docs / roadmap | Code |
|---|---|
| Future object returned by scheduler with data-service access | `ExperimentJobProxy` with polling `wait()`; no data retrieval (`data.get_experiment_data_by_job_id` is not wrapped yet) |
| Live matplotlib plotting in notebook/CLI (`get_experiment_data` rooms) | `api/scheduler_controller.py` contains an early `JobProxy._run_plot` prototype using pandas/matplotlib; v0.3.0 re-synced it with the server (`submit_job(experiment_id=…)`, `Client.event_loop`) but it is still **not wired into `Client`** |
| "Buttons in Jupyter to start/stop/accept fit" | Not implemented |

> **Design note** (updated for v0.3.0) — keep `api/scheduler_controller.py`; v0.3.0
> brought it back in sync with the server API (`experiment_id`, public
> `Client.event_loop`), so it no longer contradicts the server — but it remains
> unwired reference material: do not extend it or wire it into `Client` piecemeal.
> It gets rewritten as part of the broader client rework (data/plot proxy,
> scan-value generation — `NEW_FEATURES.md` → client).

## 3. Conventions and PR checklist

- Same ruff/mypy rules as the server; the client is part of `mypy files = ["src/"]`.
- Public proxies implement `__repr__` that lists available children — users discover
  the API from the REPL; keep reprs useful.
- Every public method has a Google docstring with an example (`ParametersController`
  is the model); these feed the docs site.
- Tests: pure helpers in `tests/client/api/test_*.py` (no server needed). Anything that
  needs a server is a `container`/integration test (see `tests/CLAUDE.md`).
- Checklist: no new runtime dependency outside the `client` extra; new server call
  names exist in the server controller; `JobStatus`/`RunStatus` in sync with
  `data_access/models/enums.py`; README/docs example updated.

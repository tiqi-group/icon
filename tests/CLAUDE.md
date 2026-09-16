# tests — testing guide

Read `/CLAUDE.md` first. Backend tests are pytest under `tests/`; frontend tests are
jest under `frontend/icon/tests/`. Since v0.3.0 **CI runs the backend suite**
(`test.yaml`: `pytest -m "not container"` on Python 3.11/3.12/3.13, UI assets
prebuilt by `build-ui.yml`). `container`-marked tests and the frontend lint/jest
suites still run **locally only** (tracked TODO, `NEW_FEATURES.md` → testing) —
run them before every PR.

```
tests/
├── mock_config.py            mock_config(): copies tests/config.yaml to a tmp dir and points ICON_CONFIG at it
├── config.yaml               v3 config used by tests (FallbackHardwareController, InfluxDB on :8087 user tester/passw0rd)
├── generate_test_hdf5.py     DEV TOOL, not a test: seeds HDF5 files + SQLite rows into a running server for GUI work
├── config/test_config.py
├── server/conftest.py        fixtures: `database` (in-memory SQLite StaticPool engine monkeypatched into every repository module, `emit_queue` → MagicMock) and `seed_job` (factory storing one job + run, returns their ids)
├── client/api/test_experiments_controller.py     parametrized pure-function tests (name shortening)
└── server/
    ├── api/test_scheduler_controller.py          controller with repositories patched via unittest.mock
    ├── api/models/scan_parameter.py              (note: not named test_*.py → not collected; rename when touched)
    ├── data_access/db_context/test_influxdbv1.py  @pytest.mark.container — starts k8s/dev.yml via podman if :8087 is closed
    ├── data_access/test_experiment_data_repository.py   round-trips ExperimentData through a temporary HDF5 file
    ├── data_access/test_venv.py                  builds a real venv and runs the mock library client in it
    ├── data_access/mock_experiment_library_client/mock_client.py   reusable BlockingExperimentLibraryClient stand-in
    ├── fitting/test_fit_runner.py, test_models.py
    ├── pre_processing/test_worker.py             pause/divert/regenerate logic with fake tasks + MagicMock repositories
    └── web_server/test_visualiser.py             aiohttp middleware serving the sequence-visualizer build

frontend/icon/tests/
├── hooks/useScanInfoState.reducer.test.ts
└── utils/{MruSelectionTree,ScanInfoSelectionHistory,deserializer,fitFunctions,scanUtils}.test.ts
```

## 1. Running

```bash
uv run pytest                     # everything (container tests need podman + free port 8087)
uv run pytest -m "not container"  # fast, no external services
uv run pytest tests/server/pre_processing -q
cd frontend && pnpm test          # jest (frontend/icon), ts-jest, node env (no DOM)
```

`pyproject.toml`: `asyncio_default_fixture_loop_scope = "session"`, marker `container`
("needs a container runtime"). Tests are allowed `assert` (`S101` per-file ignore) but
otherwise obey the full ruff/mypy rule set — tests are type-checked (`mypy files = ["src/", "tests/"]`,
pyright `include` covers `tests`).

## 2. Layout and naming rules

- Mirror the source tree: `tests/<package path>/test_<module>.py`. Keep `__init__.py`
  in every test package (they exist today; pytest uses package-style imports such as
  `from tests.mock_config import mock_config`).
- Test functions `test_<behaviour>()`; helpers `_private`; fakes named `_FakeX` or
  `MockX` (`mock_client.py`). Parametrize with `@pytest.mark.parametrize(("a", "b"), [...])`
  and a comment per case (see `test_experiments_controller.py`).
- Mark anything that needs podman/network/hardware with `@pytest.mark.container`;
  everything else must pass offline in < 1 s. New markers go into
  `[tool.pytest.ini_options].markers`.
- Config: never read `~/.config/icon`. Wrap tests that call `get_config()` (models,
  repositories, workers) in `with mock_config():` or a fixture built on it. `now()` and
  the SQLite engine module read config at import time — import them inside the context
  or accept `tests/config.yaml` values.

  > **Design note** — keep `tests/config.yaml` as is for now. Tests that write
  > results must still override `results_dir` to a `TemporaryDirectory`. Templating
  > the YAML from `mock_config()` (removing absolute paths) is a tracked TODO
  > (`NEW_FEATURES.md` → testing).

## 3. Patterns to copy

| Unit | Pattern | Example |
|---|---|---|
| Repositories (SQLite) | Use the `database` fixture (`tests/server/conftest.py`): in-memory engine monkeypatched into all repository modules, `emit_queue` a `MagicMock`; seed with `seed_job`, assert stored state via the returned engine and events via the mock | `server/conftest.py`, `server/api/test_scheduler_controller.py` |
| HDF5 | Build `ExperimentDataPoint`s, write with the module-level helpers into `h5py.File(tmp)`, `load_experiment_data`, compare dataclasses (`dataclasses.asdict`) | `test_experiment_data_repository.py` |
| InfluxDB | `influxdbv1_service` session fixture (auto-starts `k8s/dev.yml`), write then `query_last`, mark `container` | `test_influxdbv1.py` |
| Workers | Construct the worker with plain `queue.Queue`s / `SimpleNamespace` tasks; `patch("icon.server.<module>.JobRunRepository")`; drive one iteration of the loop body, never `run()` | `test_worker.py` |
| API controllers | Instantiate the `pydase.DataService` directly with mocked collaborators; call methods as plain Python (they are just methods) | `test_scheduler_controller.py` |
| Experiment library | `MockExperimentLibraryClient` + `VirtualEnvironment` in a throw-away venv | `test_venv.py` |
| Fitting | Synthesise `x, y` from the model with noise, assert recovered params within tolerance and `goodness` keys | `fitting/` |
| Frontend | Pure functions and reducers only (jest node env); no component rendering harness exists | `frontend/tests/` |

Guidelines:
- Prefer real SQLite/HDF5 in temp dirs over mocking SQLAlchemy/h5py — the persistence
  contract is what we must protect. Mock only process boundaries (queues, socket.io,
  pydase clients, hardware controllers, InfluxDB when not `container`).
- Use `FallbackHardwareController` for anything hardware-adjacent; never import
  `tiqi_zedboard` in tests (optional extra, private GitLab).
- Don't sleep-poll in tests; drive worker loops one step at a time as `test_worker.py`
  does (`MAX_ROUNDS` bound instead of wall-clock).
- Assert on socket **events** (`emit_queue.put` calls) when a repository/controller is
  supposed to notify the GUI — the frontend depends on them.

## 4. Required tests for specific kinds of change

- **Alembic migration**: add a test that (a) creates a DB from the *previous* head
  using the previous models or a checked-in fixture DB in `tests/fixtures/`, inserts a
  row, (b) runs `run_migrations()`, (c) reads the row back through the new model. Also
  run `alembic check`/autogenerate once more to prove the models and head agree.
  (`pytest-alembic` was proposed in the design docs — see `NEW_FEATURES.md`. Note:
  the `database` fixture uses `Base.metadata.create_all` and bypasses Alembic
  entirely, so it cannot double as a migration test.)
- **HDF5 format change**: keep a small fixture file written by the previous version
  and assert `load_experiment_data` still loads it (rule 10–13 in
  `data_access/CLAUDE.md`).
- **Worker control flow** (cancel/pause/divert/regenerate/realtime): a `test_worker.py`
  case per new branch, including the "exactly one ack per task" invariant.
- **API signature change**: update `tests/server/api/…`, the client proxy test if
  wrapped, and `frontend/src/utils/*` callers + their jest tests.
- **Config schema change**: test in `tests/config/` that a YAML at the old version
  migrates to `latest` without loss (`get_config()` path).
- **Frontend `localStorage` migration**: reducer/loader test in `frontend/tests/hooks/`.

## 5. Manual/integration checks (not automated)

- Full stack: `podman kube play k8s/dev.yml`, `uv run python -m icon.server -vv` with
  `tests/config.yaml`-like config (Fallback hardware), `uv run python tests/generate_test_hdf5.py`
  to seed data, then exercise the GUI at `http://localhost:8004`.
- Realtime scan + pause/resume + parameter update during scan is the highest-risk
  path; check it by hand when touching workers until an end-to-end test exists
  (`NEW_FEATURES.md` → testing).

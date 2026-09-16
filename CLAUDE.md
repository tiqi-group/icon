# ICON — root guide for agents

ICON (Ion CONtrol) is the ETH TIQI experiment-control framework: a multi-process Python
server (API + scheduler + workers), a React/TypeScript frontend, and a Python scripting
client. Repository: https://github.com/tiqi-group/icon — this guide is verified
against **v0.3.0** (2026-09-14).

This file holds what applies everywhere. Each design unit has its own `CLAUDE.md`:

| Unit | File | Scope |
|---|---|---|
| Data access | `src/icon/server/data_access/CLAUDE.md` | SQLite/Alembic, InfluxDB v1, HDF5, experiment-library clients, **persistent-data compatibility** |
| Workers | `src/icon/server/CLAUDE.md` | Scheduler, pre-processing, hardware, post-processing, process topology, API controllers |
| Frontend | `frontend/CLAUDE.md` | React GUI, socket events, `localStorage` compatibility |
| Client | `src/icon/client/CLAUDE.md` | Python scripting client |
| Testing | `tests/CLAUDE.md` | pytest, containers, jest |
| New features | `NEW_FEATURES.md` | Ideas from the design documents that are **not** implemented, grouped by unit |

> **Precedence.** Where the historical design documents (Confluence/Notion 2023–2025,
> `docs/plantuml_diagrams/*.puml`) disagree with the code, **the code wins**. The
> unit files list the known deviations, and deliberate design choices are recorded
> inline as **Design note** blocks. Several of these are explicitly provisional
> (revisit when the calibration workflow is designed) — do not reopen them silently
> in a PR; follow the revisit notes in the unit files and `NEW_FEATURES.md`.

---

## 1. Repository map

```
src/icon/
├── config/            versioned YAML config (confz): v1.py, v2.py, latest.py (=v3), migrations.py
├── serialization/     pydase serializer/deserializer patched to understand ICON objects
├── logging.py
├── cli/               `icon-migrate-influxdb-schema` entry point (InfluxDB r1→r2 parameter-schema migration)
├── client/            Python scripting client (pydase.Client subclass + proxies)
└── server/
    ├── __main__.py            click CLI; starts SRM, scheduler, workers, IconServer
    ├── shared_resource_manager.py   SyncManager owning shared queues + parameters dict
    ├── api/                   pydase DataService controllers (the public API surface)
    ├── data_access/           models, repositories, db contexts, experiment-library clients
    ├── scheduler/  pre_processing/  hardware_processing/  post_processing/   worker processes
    ├── fitting/               scipy curve fits + auto-fit
    ├── web_server/            pydase/aiohttp server, socket.io setup, emit_queue
    ├── utils/
    └── frontend/, frontend_visualizer/   BUILT frontend assets — gitignored since v0.3.0; built by CI (build-ui.yml) or `pnpm build`, bundled into the wheel. Never edit, never commit
frontend/                      pnpm workspace: icon/ (the React app) + sequence-visualizer/ (git submodule) — clone with --recursive
tests/                         pytest (server/client/config); frontend tests in frontend/icon/tests
docs/                          mkdocs site; docs/plantuml_diagrams/*.puml are the design diagrams
k8s/dev.yml                    podman kube manifest for a dev InfluxDB v1
alembic.ini / src/.../sqlite/alembic/   migrations (see data_access)
icon.spec                      PyInstaller spec for the release binary
```

## 2. Tooling and commands

| Task | Command |
|---|---|
| Install everything | `git submodule update --init --recursive`, then `uv sync --all-extras --group dev` (`--extra zedboard` / `--extra pycrystal` need ETH GitLab SSH; both are optional since v0.3.0 — the built-in RPC Zedboard controller and the venv executor need neither) |
| Run server | `uv run python -m icon.server [-v] [-c config.yaml]` |
| Dev InfluxDB | `podman kube play k8s/dev.yml` |
| Lint / format | `uv run ruff check` and `uv run ruff format --check` (CI runs both, `--max-warnings 0` equivalent) |
| Type check | `uv run mypy` (CI runs it in a full `--extra server --extra client` env, with HTML/line-precision reports) plus `uv run pyright` (basic mode) |
| Tests | `uv run pytest` (`-m "not container"` to skip podman-backed tests) |
| InfluxDB schema migration | `uv run icon-migrate-influxdb-schema [--dry-run]` — operator-run r1→r2 parameter-schema migration (with `rollback`) |
| Frontend | `cd frontend && pnpm install`, then `pnpm dev` / `pnpm lint` / `pnpm test` / `pnpm build` (workspace scripts target the `icon` package; `pnpm build` also builds the sequence visualizer into `src/icon/server/frontend_visualizer/`) |
| Docs | `uv run mkdocs serve` (group `docs`) |
| New DB migration | `uv run alembic revision --autogenerate -m "<desc>"` then review, then `uv run alembic upgrade head` |

CI (`.github/workflows/`): `lint.yaml` runs ruff + mypy (with reports) on every PR;
`test.yaml` runs `pytest -m "not container"` on Python 3.11/3.12/3.13 with UI assets
prebuilt by `build-ui.yml`; `claude.yml` provides a Claude Code action;
`gh-pages.yml` deploys docs on `main`; `release.yml` builds sdist + wheel
(`uv build`) and PyInstaller binaries on tags (only release tags publish).
`container`-marked tests and the frontend lint/jest suites still run **locally
only** (CI jobs for them are a tracked TODO, `NEW_FEATURES.md` → testing).

## 3. Python conventions (enforced by `pyproject.toml`)

- Python `>=3.11,<3.14` at runtime (CI tests 3.11–3.13), ruff `target-version = "py310"`: keep syntax
  3.10-compatible (`X | Y` unions are fine; no `type` statements, no PEP 695 generics).
- `ruff` with `select = ["ALL"]`. Everything not in the ignore list is an error. Notable
  consequences:
  - Google-style docstrings (`pydocstyle convention = "google"`); `D1xx` "undocumented"
    rules are currently ignored (TODO list in pyproject) — still document public
    repository/controller methods, the codebase does.
  - `max-complexity = 7` (mccabe). Split functions rather than adding `# noqa: C901`
    (one existing exception in `fitting/fit_runner.py`).
  - Ignored on purpose: `ANN` (mypy covers it), `E501` (formatter), `PTH`, `TRY003`,
    `EM101/102`, `PLR0913/0917`, `BLE001`, `S6xx` subprocess rules, `SLF001`.
  - When you must suppress, use a specific code: `# noqa: ARG001`, never a bare `# noqa`.
- `mypy`: `disallow_untyped_defs`, `disallow_untyped_calls`, `disallow_incomplete_defs`,
  `disallow_any_generics`, `check_untyped_defs`. Every function is fully annotated.
  Use `from __future__ import annotations` + `TYPE_CHECKING` imports for heavy or
  circular imports (pattern used throughout `server/`). Ruff `TC00x` may then ask you to
  move imports into the `TYPE_CHECKING` block; pydantic models that need runtime types
  opt out with `# ruff: noqa: TC001 TC003` at the top (see `*/task.py`).
- Naming: `snake_case` functions/modules, `PascalCase` classes, `UPPER_CASE` module
  constants, private helpers prefixed `_`. Repository methods are `verb_noun_by_x`
  (`get_job_by_id`, `update_run_by_id`, `write_experiment_data_by_job_id`) and take
  **keyword-only** arguments (`def submit_job(*, job: Job)`).
- Logging: `logger = logging.getLogger(__name__)` at module top; `%`-style lazy
  formatting; `logger.exception` inside `except`.
- Timezone: never `datetime.now()` bare. Use `icon.server.data_access.models.sqlite.now.now()`
  (config timezone, default `Europe/Zurich`). Persisted timestamps are ISO strings.
- Config access: `from icon.config.config import get_config` — it re-reads the YAML
  each call, which is intentional (hot reload, child processes inherit `ICON_CONFIG`).
- Processes, not threads, for workers (`multiprocessing.Process` subclasses). Anything
  crossing a process boundary must be picklable (pydantic `BaseModel` tasks, manager
  proxies). Decorate `run()` with `@handle_keyboard_interrupt(logger)`.
- Errors: raise `RuntimeError`/`ValueError` with a human-readable message that can be
  shown in the frontend (`JobRun.log`).

## 4. Frontend conventions (enforced by `frontend/icon/eslint.config.js` + `.prettierrc`)

- TypeScript strict, React 19 function components, hooks. ESLint: `eslint:recommended`,
  `typescript-eslint` recommended + stylistic, `react` recommended, prettier as an
  error. `pnpm lint` uses `--max-warnings 0`.
- Prettier: 2 spaces, double quotes, semicolons, `printWidth 88`, `arrowParens always`.
- Folder roles are fixed: `components/`, `contexts/`, `hooks/` (`useX`), `layouts/`,
  `pages/`, `stores/`, `types/`, `utils/` (pure functions, unit-tested with jest).

## 5. Architecture in one paragraph (validate PRs against this)

`__main__.py` starts a `SharedResourceManager` (SRM: two priority queues + a shared
parameters dict), a `Scheduler` process, N `PreProcessingWorker` processes, **one**
`HardwareProcessingWorker`, **one** `PostProcessingWorker`, and finally the
`IconServer` (pydase/aiohttp + socket.io) hosting `APIService`. Clients (browser,
Python) only ever talk to `APIService` over socket.io (`trigger_method`, `get_value`,
`update_value`) plus the custom events listed in `frontend/CLAUDE.md`. All persistent
state lives in three stores — SQLite (jobs/runs/scan params/devices/experiment sources),
InfluxDB v1 (parameter time series), HDF5 (one file per job run) — and is reached
**only through repositories** in `data_access/repositories`. Workers signal each other
through queues and through status columns in SQLite; there is no message broker.

PR checklist for architecture fit:

1. Does new persistence go through a repository? (No raw `h5py`/`sqlalchemy` sessions
   in controllers or workers.)
2. Does new cross-process state live in the SRM or a `multiprocessing.Queue` created in
   `__main__.py`? (No globals expected to be shared across processes.)
3. Is a new API method a coroutine/method on an existing `pydase.DataService`
   controller, with a dict/dataclass return that `icon.serialization` can dump?
4. Does it emit the right socket event via `emit_queue` (server-side) so the frontend
   stays in sync?
5. Schema/HDF5/localStorage change? → follow the compatibility rules in
   `data_access/CLAUDE.md` §"Backwards compatibility" and `frontend/CLAUDE.md`.
6. Is the feature already listed in `NEW_FEATURES.md`? Update that file (remove or
   mark done) in the same PR.

## 6. Development guidelines

- Branch from `main`, open a PR; squash-merge is the norm (`Merge pull request #NNN`).
- One concern per PR. Schema migrations and behaviour changes in separate commits at
  least.
- Update docs that describe what you changed: `docs/getting-started/*.md`,
  `docs/plantuml_diagrams/*.puml` (+ regenerate the `.svg`), docstrings feeding
  `mkdocstrings` (`docs/reference/server.md`).
- The Python version is **dynamic** since v0.3.0 (hatch-vcs, derived from git tags) —
  never add a `version =` back to `pyproject.toml`. Releasing = pushing a `vX.Y.Z`
  tag; `release.yml` builds wheel/sdist + binaries, and only release tags publish.
- Never commit built frontend assets: `src/icon/server/frontend{,_visualizer}/` are
  gitignored; CI (`build-ui.yml`) builds them for tests and releases, and hatch
  bundles them into the wheel. Locally, `cd frontend && pnpm build` regenerates them
  for `python -m icon.server`.
- Keep `README.md` sections between `<!--x-start-->`/`<!--x-end-->` markers intact —
  mkdocs includes them.

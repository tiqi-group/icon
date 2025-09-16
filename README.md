<!--introduction-start-->
![icon Banner](./docs/images/logo.svg)

# Ion CONtrol Software (ICON)

[![Version](https://img.shields.io/github/v/release/tiqi-group/icon)](https://github.com/tiqi-group/icon)
[![Python Versions](
https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Ftiqi-group%2Ficon%2Frefs%2Fheads%2Fmain%2Fpyproject.toml
)](https://github.com/tiqi-group/icon)
[![Documentation Status](https://github.com/tiqi-group/icon/actions/workflows/gh-pages.yml/badge.svg)](https://tiqi-group.github.io/icon/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

The **Ion Control Software (ICON)** is a control and data-acquisition framework developed in the Trapped Ion Quantum Computing research group at ETH Zurich. It is designed for laboratories that run experiments written in Python (with the [`pycrystal`](https://gitlab.phys.ethz.ch/tiqi-projects/pycrystal) framework) on M-Action/Quench hardware.

ICON acts as the interface between user-defined Python experiments and the laboratory control hardware. It provides:

* An overview of available experiments by parsing the *experiment library* (a repository containing hardware and experiment descriptions).
* Access to all experiment parameters, including those from external devices integrated via [`pydase`](https://github.com/tiqi-group/pydase) services.
* A job history and live data visualisation for running and past experiments.
* Support for parameter scans, including device parameters from connected services.

The system is built with:

* **Backend**: Python (API server, scheduler, pre-/post-processing, hardware orchestration).
* **Frontend**: React/TypeScript (configuration, monitoring, visualisation).
* **Databases**:
    * SQLite — job and device history
    * InfluxDB — parameter time series
    * HDF5 — experiment results
<!--introduction-end-->


## Getting Started

<!--getting-started-start-->
ICON runs on Linux and requires Python 3 to start. The easiest way to start is by downloading the binary from the [releases page](https://github.com/tiqi-group/icon/releases). Make it executable and run it:

```bash
$ chmod +x icon-linux-amd64
$ ./icon-linux-amd64 --help
Usage: icon-linux-amd64 [OPTIONS]

  Start the ICON server

Options:
  -V, --version      Print version.
  -v, --verbose      Increase verbosity (-v, -vv)
  -q, --quiet        Decrease verbosity (-q)
  -c, --config FILE  Path to the configuration file [default: ~/.config/icon/config.yaml]
  -h, --help         Show this message and exit
```

If you prefer to run ICON from source, clone the repository and use [`uv`](https://docs.astral.sh/uv/) as the dependency manager:

```bash
git clone https://github.com/tiqi-group/icon.git
cd icon
uv sync --extras server
uv run python -m icon.server
```
<!--getting-started-end-->

### Configuration

<!--configuration-start-->
ICON uses a YAML configuration file, located at `~/.config/icon/config.yaml` by default. You can override this path with the `-c` flag.

* If the file does not exist, ICON will create it with default values.
* You can adjust settings either in the file or through the frontend settings page.
<!--configuration-end-->

For more information about the configuration, see [Configuration File](https://tiqi-group.github.io/icon/getting-started/configuration-file/).

### Frontend

<!--frontend-start-->
The web frontend is served automatically by the ICON backend. By default it is available at [http://localhost:8004](http://localhost:8004). The port and address can be changed in the config file.

![Start page](./docs/images/ICON_Start_page.png)
<!--frontend-end-->

## Development

### Backend

Set up the development environment:

```bash
uv sync --all-extras --group dev
source .venv/bin/activate
````

Run the server:

```bash
uv run python -m icon.server
```

### Frontend

The frontend source code is located in the `frontend/` folder. To start development:

```bash
cd frontend
npm install
npm run dev
```

This uses [Vite.js](https://vitejs.dev/) with hot-reloading enabled.

Project structure:

```bash
frontend
└── src
    ├── components  # React components
    ├── contexts    # React contexts
    ├── hooks       # React hooks
    ├── layouts     # Layouts for MUI Toolpad
    ├── pages       # Page definitions
    ├── stores      # State stores (e.g. parameter store)
    ├── types       # Type definitions
    └── utils       # Utility functions
```

### SQLite

ICON uses SQLite to store job history and device metadata.

* Models are defined using **SQLAlchemy**.
* Migrations are managed with **Alembic**.
* On startup, ICON automatically runs `alembic upgrade head`.

For details on updating schemas, see [Alembic README](./src/icon/server/data_access/db_context/sqlite/alembic/README.md).

### PlantUML Diagrams

The design of the software is laid out in PlantUML diagrams located in the [`docs/plantuml_diagrams`](./docs/plantuml_diagrams) directory.

## Acknowledgements

This work was funded by the [ETH Zurich-PSI Quantum Computing Hub](https://www.psi.ch/en/lnq/qchub).

## License

ICON is licensed under the [MIT License](./LICENSE).

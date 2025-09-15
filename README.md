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

<!--getting-started-1-start-->
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

### Configuration

ICON uses a YAML configuration file, located at `~/.config/icon/config.yaml` by default. You can override this path with the `-c` flag.

* If the file does not exist, ICON will create it with default values.
* You can adjust settings either in the file or through the frontend settings page.

### Databases

* **SQLite** — stores metadata about jobs and devices. The path is configurable in the config file (defaults to the binary location).
* **InfluxDB** — stores parameter time series. Both InfluxDB v1 and v2 are supported (v3 may work but is untested).
<!--getting-started-1-end-->

#### Example: InfluxDB v1

<!--influxdbv1-config-start-->
```yaml
databases:
  influxdbv1:
    database: testing
    host: localhost
    measurement: Experiment Parameters
    password: passw0rd
    port: 8086
    username: tester
    ...
```
<!--influxdbv1-config-end-->

#### Example: InfluxDB v2

<!--influxdbv2-config-start-->
```yaml
databases:
  influxdbv1:
    database: testing
    host: localhost
    measurement: Experiment Parameters
    password: <influxdb v2 token>
    port: 8086
    ...
```
<!--influxdbv2-config-end-->

<!--getting-started-2-start-->
### Frontend

The web frontend is served automatically by the ICON backend. By default it is available at [http://0.0.0.0:8004](http://0.0.0.0:8004). The port and address can be changed in the config file.
<!--getting-started-2-end-->

## Development

```bash
uv sync --all-extras --group dev
source .venv/bin/activate  # activating virtual environment
```

Initialise the database using alembic:

```bash
alembic upgrade head
```

(see [here](./alembic/README.md) for how to update the SQLite database schema)

Running the server (when in the virtual environment):

```bash
python -m icon.server
```

### PlantUML Diagrams

The design of the software is laid out in PlantUML diagrams located in the [`docs/plantuml_diagrams`](./docs/plantuml_diagrams) directory.

## Acknowledgements

This work was funded by the [ETH Zurich-PSI Quantum Computing Hub](https://www.psi.ch/en/lnq/qchub).

## License

`icon` is licensed under the [MIT License](./LICENSE).

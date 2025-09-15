![icon Banner](./docs/images/logo.png)

# The Ion CONtrol Software (ICON)

[![Version](https://img.shields.io/github/v/release/tiqi-group/icon)](https://github.com/tiqi-group/icon)
[![Python Versions](
https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Ftiqi-group%2Ficon%2Frefs%2Fheads%2Fmain%2Fpyproject.toml
)](https://github.com/tiqi-group/icon)
[![Documentation Status](https://github.com/tiqi-group/icon/actions/workflows/gh-pages.yml/badge.svg)](https://tiqi-group.github.io/icon/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

This repository contains the source code for the ICON Experiment Control software. It consists of python code for the backend and react (ts) code for the frontend.

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

## License

`icon` is licensed under the [MIT License](./LICENSE).


# The Ion CONtrol Software (ICON)

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


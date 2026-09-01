# The sequence visualizer frontend

`src/icon/server/frontend_visualizer/` holds a build of the
[ionpulse-sequence-visualiser](https://github.com/tiqi-group/ionpulse-sequence-visualiser),
served by the ICON web server under `/visualizer/` (see `visualiser.py` and
issue #103).

The visualizer is a git submodule at `frontend/ionpulse-sequence-visualiser`.
Its build output is committed, like the one of ICON's own frontend, and is
regenerated together with it:

```bash
cd frontend
npm install                # also installs the submodule's dependencies
npm run build              # builds ICON's frontend and the visualizer
npm run build:visualiser   # builds only the visualizer
```

The bundle speaks only the ICON protocol: hardware description and sequences
are fetched via the pydase methods `experiments.get_hardware_description` and
`data.get_hardware_instructions` (optionally scoped by
`?jobId=`/`?datapoint=` URL parameters), and live updates arrive via the
`last_experiment_sequence` socket.io event. ICON's pages embed it with
`?embedded=1&theme=<light|dark>`.

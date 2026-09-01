# Vendored sequence-visualizer build

This directory contains a prebuilt bundle of the
[ionpulse-sequence-visualiser](https://github.com/tiqi-group/ionpulse-sequence-visualiser),
served by the ICON web server under `/visualizer/` (see
`src/icon/server/web_server/visualiser.py` and issue #103).

- Source: branch `icon-embedded` (based on `feature/icon`), submitted upstream
  as a pull request to tiqi-group/ionpulse-sequence-visualiser
- Built locally with `vite build --base=./` (node 24)

The bundle speaks only the ICON protocol: hardware description and sequences
are fetched via the pydase methods `experiments.get_hardware_description` and
`data.get_hardware_instructions` (optionally scoped by
`?jobId=`/`?datapoint=` URL parameters), and live updates arrive via the
`last_experiment_sequence` socket.io event. ICON's pages embed it with
`?embedded=1&theme=<light|dark>`.

Vendoring the built assets is an interim solution: once the upstream pull
request is merged, the bundle should instead be produced by the visualizer
repository's GitHub Actions build and consumed as an artifact rather than
being committed here.

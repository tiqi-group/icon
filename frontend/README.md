# Frontend

The frontend code is organized as a workspace holding two packages. The workspace
is declared both in `package.json` (`workspaces`, used by npm) and in
`pnpm-workspace.yaml` (used by pnpm), keep the two lists in sync.

Project structure:

```bash
frontend
├── icon                 # ICON's own frontend
│   └── src
│       ├── components   # React components
│       ├── contexts     # React contexts
│       ├── hooks        # React hooks
│       ├── layouts      # Layouts for MUI Toolpad
│       ├── pages        # Page definitions
│       ├── stores       # State stores (e.g. parameter store)
│       ├── types        # Type definitions
│       └── utils        # Utility functions
└── sequence-visualizer  # sequence visualizer (git submodule)
```

> [!IMPORTANT]
> sequence-visualizer is a git submodule, clone the icon repository
> with `--recursive` or run `git submodule update --init --recursive`
> after cloning.

To run ICON from source, the UI packages must be built first:

```bash
cd frontend
npm install      # installs dependencies (or: pnpm install | yarn install | bun install)
npm run build    # builds the packages   (or: pnpm build   | yarn build   | bun run build)
```

`build` builds both packages into `src/icon/server/frontend/` and
`src/icon/server/frontend_visualizer/`.

`dev` runs a vite dev server which listens for code changes.

## The ICON frontend

`frontend/icon` holds ICON's React based web application which connects to the backend
via a socket.io websocket.

The build assets are copied into `src/icon/server/frontend/` from where they are served
by the ICON backend.

## The sequence visualizer frontend

`frontend/sequence-visualizer` is a submodule pointing to the
[ionpulse-sequence-visualiser](https://github.com/tiqi-group/ionpulse-sequence-visualiser).
It is a standalone web application which renders hardware instructions as waveforms.
The hardware instructions are picked up from ICON's `experiment_*` socket.io event
which is emitted on every data point.

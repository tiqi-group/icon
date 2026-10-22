# Single-plot viewer

Open a supported plot from a job card in a compact, resizable popup. Normal browser link behavior is retained for modified clicks and when a popup cannot be opened. The viewer also supports fullscreen, with a browser-command hint when the fullscreen API is unavailable.

The route is `/data/:jobId/plot/:kind/:plotIndex?device=<device_id>`, where `kind` is `readout` or `histogram`. Plot identity uses the metadata index rather than array order. A missing requested device or plot never silently selects a different one.

## Supported plots

- Numeric 1D scans, time traces, two-dimensional heatmaps, and the latest histogram are supported.
- Higher-dimensional and vector plots remain available in the existing job view.
- Repeated finite 1D scans show the mean, with optional individual repetition traces. Window size counts scan positions.
- 2D heatmaps join values to recorded X/Y coordinates and leave unobserved cells blank. Planned numeric coordinates keep the grid stable during acquisition. A repetition selector can show one raster pass instead of the mean; the legend selects the displayed channel and its color scale.

## Overlaid 1D curves

Two-dimensional scans open as a heatmap by default. Choose Overlaid curves to compare slices on shared axes without vertical offsets. Either scan parameter can be horizontal; each curve fixes a value of the other parameter. Choose a channel when the plot contains multiple channels.

The compact slice selector shows the fixed parameter once and summarizes the current selection. Open it to choose values with checkboxes or use All/None; larger lists also offer search. The legend shows only the slice values. Selection is retained separately for each horizontal-axis direction. Initially, the first 12 observed slices are shown; up to 32 can be selected at once.

Curves use recorded coordinates and measured values. Missing numeric positions break the line, and unobserved slices are omitted. Show individual repetitions uses the same raster-pass selection as the heatmap. Switching plot mode, horizontal axis or channel resets numeric bounds and zoom so limits are not carried between different coordinates. Hold/Follow and existing plot interactions remain available.

## Interaction

- Pan and Box zoom can target both axes, X only, or Y only. Box selection has no aspect-ratio constraint and returns to Pan after selection; Escape cancels it.
- Wheel zoom, zoom buttons, pan, hover values, and resizing use public ECharts APIs.
- Numeric X/Y bounds accept actual coordinates, including local date/time on time axes. Empty fields mean Auto. Invalid ranges preserve the previous chart. If incoming category data moves outside retained limits, an explicit warning offers adjustment or reset.
- Reset axes clears numeric limits and resets zoom. Follow live resets zoom within retained numeric limits.

## Live data and history

Hold view freezes an immutable snapshot while acquisition and background buffering continue. Zooming, panning, or changing X limits also holds the snapshot; Y limits may follow live data. Follow live returns to the latest available data. These controls do not pause, resume, or cancel acquisition.

Window size controls the newest N points for 1D/time traces, from 1 to 100,000, with a default of 1,000. Enter or blur applies changes. The preference is remembered per browser origin, with a fallback when storage is unavailable. Increasing the live buffer refreshes history without blanking the current plot; Hold remains frozen. Counts indicate when fewer points are available than requested.

The server's 4 MB snapshot transfer limit remains in effect. A viewer may receive fewer points than requested, and 2D heatmaps show all currently loaded cells. Viewer retention does not change saved job data.

## Fitting

Completed numeric 1D scans reuse FitPanel and the existing fit-save/delete APIs for the selected device and channels. Successful fits are saved with the job. Fit range is set separately from zoom and Window size. Parameter-update controls and their handler are disabled in this viewer.

## Integration and development

The route loads lazily. Viewer-specific loading handles reconnects, snapshot/event races, duplicate points, and initial snapshot recovery; the existing `useExperimentData` hook is unchanged. Shared changes are limited to entry links, routing, optional renderer injection, and a FitPanel permission flag whose default preserves existing behavior.

From `frontend/icon/`, run `pnpm exec jest --runInBand` for the frontend tests and `pnpm run build` for the TypeScript/Vite build. Viewer tests cover loading and reconnects, immutable held snapshots, device and plot selection, sparse data, repetitions, window limits, axis bounds, and zoom calculations.

### Screenshot identity

Each standalone chart includes its plot name, job ID, experiment display name, device and scheduled timestamp in the chart canvas. Screenshots retain their identity when cropped to the plot. The header remains available while disconnected; missing display metadata falls back to the experiment identifier. This applies to traces, heatmaps and histograms.

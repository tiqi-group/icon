# Compact Light

Light-mode styling for the Start, Parameters, Experiments, Devices, and Settings pages.
The Data page highlights the selected job with a blue rail.

## Structure

- `base.css`: page layout, parameter density, input alignment, and scan layout.
- `units-muted.css`: the base unit badge styling.
- `units-high-contrast.css`: an optional stronger unit treatment.
- `chooser-states.css`: feedback for selection and focus in parameter choosers.
- `unit-accents.css`: clearer unit labels with color by parameter type. Scan,
  stale-value and invalid-state cues take priority.
- `navigation.css`: selection rails and parameter group dividers.
- `index.css`: entry point loaded by the style selector.

The style is selected under Settings > Browser > Style.
To use the muted badges in a user stylesheet, omit `unit-accents.css` from
`index.css`. To use the high-contrast variant instead, also replace the
`units-muted.css` import with `units-high-contrast.css`.

All selectors are scoped to Toolpad's light-mode root attribute and the selected
page. Dark mode uses the existing upstream styles. No experiment, scheduler,
parameter update, or hardware behavior is changed.

## Maintenance

These styles use existing MUI classes, inline layout structure, and HelpButton
accessible labels. Recheck them when those components change. In particular,
the experiment group indentation and Start/Stop versus Span toggle retain their
current upstream structure.

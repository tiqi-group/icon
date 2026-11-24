# Compact Light

Light-mode styling for the Start, Parameters, Experiments, Devices, and Settings pages.
The Data and Sequence pages retain the upstream styling.

## Structure

- `base.css`: page layout, parameter density, input alignment, and scan layout.
- `units-muted.css`: the default unit badges, with restrained redundant color cues.
- `units-high-contrast.css`: an optional stronger unit treatment.
- `index.css`: imports the base and exactly one unit variant.

The style is selected under Settings > Browser > Style.
To select the alternative unit treatment, replace the unit import in `index.css`.

All selectors are scoped to Toolpad's light-mode root attribute and the selected
page. Dark mode uses the existing upstream styles. No experiment, scheduler,
parameter update, or hardware behavior is changed.

## Maintenance

These styles use existing MUI classes, inline layout structure, and HelpButton
accessible labels. Recheck them when those components change. In particular,
the experiment group indentation and Start/Stop versus Span toggle retain their
current upstream structure.

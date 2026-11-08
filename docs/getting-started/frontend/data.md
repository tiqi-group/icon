# Saved scan settings

The Data page shows a **Scan Parameters** frame for the selected job's saved,
non-realtime scan axes. Each axis is identified by namespace, display group (or
device name), and parameter name. Its number matches the **Scan 1**, **Scan 2**,
etc. markers in Parameter Values.

The frame summarizes the submitted points, rather than the points acquired before
a job finished or was cancelled. Numeric scans show Min, Max, Points, Span,
Center, and Step size. Descending scans have a signed step; reordered uniform
grids show grid spacing, and irregular scans show **Variable**. Repeated identical
values or a single point have no step. Categorical values are listed directly.
Realtime axes are omitted from the frame, and unscanned jobs have no frame.

Scan markers keep the recorded parameter scalar visible in muted text. Missing
recorded scalars say **Not recorded**, without falling back to a live or default
value. Fixed parameters keep their existing display and behavior.

Numeric values are displayed without additional rounding or truncation, using
all digits available in the received JavaScript numbers. Display groups and
units use current experiment metadata when available; they are not a historical
metadata snapshot. Names use the saved scan name, with current metadata and
identifier fallbacks when needed. Unknown units are not inferred.

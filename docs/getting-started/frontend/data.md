# Data page

## Filter job history

Open **Filter** above the job list to limit jobs by experiments, creation dates,
or an exact job ID. Conditions are combined: a job must match every active filter.

- **Experiments** offers a searchable checklist. **All** includes every experiment,
  including future ones; **None** selects no experiments. Historical experiments
  remain available even after they have been removed from the current library.
- **From** and **Through** are inclusive creation dates in ICON's configured time
  zone, shown beneath the fields. Either date can be left empty. **Today** uses
  that time zone, which may differ from the browser's.
- **Job ID** limits the list to one job. **Filter** applies the form; **Clear**
  removes all filters.

Filters are stored in the URL. Reloading or returning through browser history
restores them. The Experiments page also provides **View data for this experiment**.

Filtering happens in the database before pagination, so an older matching job
can be found without loading all intervening jobs. The same filters apply to
In Progress, Queued and Finished jobs. Unfiltered clients retain the existing
job-list behavior. No database migration is needed.

## Selection and live updates

With filters active, **Latest matching** follows the newest matching job and keeps
the filters in the URL. If nothing matches, it waits for a matching job rather
than showing an unrelated one. Following updates the current history entry.

With Latest off, a selected job stays pinned even when it falls outside the
filters; an information notice explains why it is not in the list. Selecting an
older job disables Latest, as before. Latest remains a per-tab preference.

Filtered lists receive live job/run updates and refresh after reconnecting.
Failed requests show an error and a Retry action rather than an empty result.
Changing filters ignores responses from the previous query.

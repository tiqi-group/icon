import { useContext, useEffect, useState } from "react";
import { Alert, Button, TextField, Typography } from "@mui/material";
import { ExperimentFilterPicker } from "./ExperimentFilterPicker";
import FilterListIcon from "@mui/icons-material/FilterList";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import { ExperimentsContext } from "../../contexts/ExperimentsContext";
import { JobsContext } from "../../contexts/JobsContext";
import { runMethod, socket } from "../../socket";
import { deserialize } from "../../utils/deserializer";
import type { SerializedObject } from "../../types/SerializedObject";
import { getExperimentNameFromExperimentId } from "../../utils/experimentUtils";
import { dataFilterError, emptyDataFilters } from "../../utils/dataFilters";
import type { DataFilters as Filters } from "../../utils/dataFilters";

interface DataFiltersProps {
  filters: Filters;
  onApply: (filters: Filters) => void;
}

export function DataFilters(props: DataFiltersProps) {
  const { filters } = props;
  const active = [
    filters.experiments !== null,
    filters.from || filters.to,
    filters.job,
  ].filter(Boolean).length;
  const description = [
    filters.experiments?.map(getExperimentNameFromExperimentId).join(", ") ||
      (filters.experiments?.length === 0 ? "No experiments" : ""),
    filters.from && filters.to
      ? `${filters.from} through ${filters.to}`
      : filters.from
        ? `From ${filters.from}`
        : filters.to
          ? `Through ${filters.to}`
          : "",
    filters.job && `Job ${filters.job}`,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <details className="icon-data-filter-disclosure">
      <summary title={description || "Filter jobs by experiment, date or job ID"}>
        <FilterListIcon />
        <span>Filter{active > 0 ? ` · ${active} active` : ""}</span>
        <ChevronRightIcon className="icon-data-filter-chevron" />
      </summary>
      <DataFilterForm key={JSON.stringify(filters)} {...props} />
    </details>
  );
}

function DataFilterForm({ filters, onApply }: DataFiltersProps) {
  const experiments = useContext(ExperimentsContext);
  const { jobs } = useContext(JobsContext);
  const [draft, setDraft] = useState(filters);
  const [options, setOptions] = useState<{
    experiment_ids: string[];
    timezone: string;
  }>({ experiment_ids: [], timezone: "" });
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let current = true;
    const refresh = () =>
      runMethod("scheduler.get_job_filter_options", [], {}, (ack) => {
        if (!current) return;
        const value = deserialize(ack as SerializedObject);
        if (value && !(value instanceof Error) && Array.isArray(value.experiment_ids))
          setOptions(value);
      });
    if (socket.connected) refresh();
    socket.on("connect", refresh);
    return () => {
      current = false;
      socket.off("connect", refresh);
    };
  }, []);
  const ids = [
    ...new Set([
      ...Object.keys(experiments),
      ...options.experiment_ids,
      ...Object.values(jobs).map((job) => job.experiment_id),
      ...(draft.experiments ?? []),
    ]),
  ].sort(
    (a, b) =>
      getExperimentNameFromExperimentId(a).localeCompare(
        getExperimentNameFromExperimentId(b),
      ) || a.localeCompare(b),
  );
  const submit = (next: Filters) => {
    const problem = dataFilterError(next);
    setError(problem);
    if (!problem) onApply(next);
  };
  return (
    <form
      className="icon-data-filters"
      aria-label="Filter data"
      onSubmit={(event) => {
        event.preventDefault();
        submit(draft);
      }}
    >
      <ExperimentFilterPicker
        options={ids}
        selection={draft.experiments}
        onChange={(experiments) => setDraft((current) => ({ ...current, experiments }))}
      />
      <div className="icon-data-date-range">
        <TextField
          size="small"
          type="date"
          label="From"
          value={draft.from}
          onChange={(event) => setDraft({ ...draft, from: event.target.value })}
          slotProps={{ inputLabel: { shrink: true } }}
        />
        <TextField
          size="small"
          type="date"
          label="Through"
          value={draft.to}
          onChange={(event) => setDraft({ ...draft, to: event.target.value })}
          slotProps={{ inputLabel: { shrink: true } }}
        />
      </div>
      <Typography variant="caption" color="text.secondary">
        Created date{options.timezone ? ` · ${options.timezone}` : " · ICON time zone"}
      </Typography>
      <TextField
        size="small"
        label="Job ID"
        placeholder="Any job"
        value={draft.job}
        onChange={(event) => setDraft({ ...draft, job: event.target.value })}
        slotProps={{ htmlInput: { inputMode: "numeric" } }}
      />
      <div className="icon-data-filter-actions">
        <Button size="small" type="submit" variant="outlined">
          Filter
        </Button>
        <Button
          size="small"
          onClick={() => {
            setDraft(emptyDataFilters);
            setError(null);
            onApply(emptyDataFilters);
          }}
        >
          Clear
        </Button>
        <Button
          size="small"
          disabled={!options.timezone}
          onClick={() => {
            const parts = new Intl.DateTimeFormat("en", {
              timeZone: options.timezone,
              year: "numeric",
              month: "2-digit",
              day: "2-digit",
            }).formatToParts(new Date());
            const value = ["year", "month", "day"]
              .map((part) => parts.find((p) => p.type === part)?.value)
              .join("-");
            const next = { ...draft, from: value, to: value };
            setDraft(next);
            submit(next);
          }}
        >
          Today
        </Button>
      </div>
      {error && <Alert severity="error">{error}</Alert>}
    </form>
  );
}

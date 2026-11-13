import { JobListItem } from "../types/JobListItem";

export interface JobDay {
  /** Local date of the day as YYYY-MM-DD */
  key: string;
  /** The date, e.g. "Wed, 11.11.26" */
  label: string;
  jobs: JobListItem[];
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const pad = (value: number) => String(value).padStart(2, "0");

const dayKey = (date: Date) =>
  `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

/** Formats a date as e.g. "Wed, 11.11.26" */
export const formatDay = (date: Date) =>
  `${WEEKDAYS[date.getDay()]}, ${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${pad(
    date.getFullYear() % 100,
  )}`;

/**
 * Groups jobs by the local day they were created on, keeping their order.
 *
 * @param jobs Jobs sorted newest first
 */
export const groupJobsByDay = (jobs: JobListItem[]): JobDay[] => {
  const days: JobDay[] = [];
  for (const job of jobs) {
    const created = new Date(job.created);
    const key = dayKey(created);
    let day = days.at(-1);
    if (day?.key !== key) {
      day = days.find((d) => d.key === key);
    }
    if (!day) {
      day = { key, label: formatDay(created), jobs: [] };
      days.push(day);
    }
    day.jobs.push(job);
  }
  return days;
};

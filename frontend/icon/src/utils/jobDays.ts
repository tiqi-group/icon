import { JobListItem } from "../types/JobListItem";

export interface JobDay {
  /** Local date of the day as YYYY-MM-DD */
  key: string;
  /** "Today", "Yesterday" or the date */
  label: string;
  jobs: JobListItem[];
}

const pad = (value: number) => String(value).padStart(2, "0");

const dayKey = (date: Date) =>
  `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

/**
 * Groups jobs by the local day they were created on, keeping their order.
 *
 * @param jobs Jobs sorted newest first
 * @param now The current time, for "Today" and "Yesterday"
 */
export const groupJobsByDay = (
  jobs: JobListItem[],
  now: Date = new Date(),
): JobDay[] => {
  const today = dayKey(now);
  const yesterday = dayKey(
    new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1),
  );
  const days: JobDay[] = [];
  for (const job of jobs) {
    const created = new Date(job.created);
    const key = dayKey(created);
    let day = days.at(-1);
    if (day?.key !== key) {
      day = days.find((d) => d.key === key);
    }
    if (!day) {
      const label =
        key === today
          ? "Today"
          : key === yesterday
            ? "Yesterday"
            : new Intl.DateTimeFormat("ch", {
                weekday: "short",
                year: "numeric",
                month: "short",
                day: "numeric",
              }).format(created);
      day = { key, label, jobs: [] };
      days.push(day);
    }
    day.jobs.push(job);
  }
  return days;
};

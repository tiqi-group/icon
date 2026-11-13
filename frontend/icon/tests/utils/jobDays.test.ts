import { groupJobsByDay } from "../../src/utils/jobDays";
import { JobListItem } from "../../src/types/JobListItem";
import { JobStatus } from "../../src/types/enums";

const job = (id: number, created: Date): JobListItem => ({
  id,
  created: created.toISOString(),
  status: JobStatus.PROCESSED,
  experiment_id: "exp",
  num_scan_parameters: 1,
  run_id: null,
  run_status: null,
});

const now = new Date(2026, 10, 13, 15, 0);

describe("groupJobsByDay", () => {
  it("groups jobs by local day, newest first, with today and yesterday named", () => {
    const days = groupJobsByDay(
      [
        job(5, new Date(2026, 10, 13, 9, 0)),
        job(4, new Date(2026, 10, 13, 0, 5)),
        job(3, new Date(2026, 10, 12, 23, 55)),
        job(2, new Date(2026, 10, 10, 12, 0)),
        job(1, new Date(2026, 10, 10, 8, 0)),
      ],
      now,
    );
    expect(days.map((d) => d.key)).toEqual(["2026-11-13", "2026-11-12", "2026-11-10"]);
    expect(days.map((d) => d.jobs.map((j) => j.id))).toEqual([[5, 4], [3], [2, 1]]);
    expect(days[0].label).toBe("Today");
    expect(days[1].label).toBe("Yesterday");
    expect(days[2].label).not.toMatch(/Today|Yesterday/);
  });

  it("puts a job out of order into its day instead of starting it again", () => {
    const days = groupJobsByDay(
      [
        job(3, new Date(2026, 10, 13, 9, 0)),
        job(2, new Date(2026, 10, 12, 9, 0)),
        job(1, new Date(2026, 10, 13, 8, 0)),
      ],
      now,
    );
    expect(days.map((d) => d.jobs.map((j) => j.id))).toEqual([[3, 1], [2]]);
  });

  it("handles the turn of the year for yesterday", () => {
    const days = groupJobsByDay(
      [job(1, new Date(2026, 11, 31, 12, 0))],
      new Date(2027, 0, 1, 8, 0),
    );
    expect(days[0].label).toBe("Yesterday");
  });

  it("gives no days for no jobs", () => {
    expect(groupJobsByDay([], now)).toEqual([]);
  });
});

import { formatDay, groupJobsByDay } from "../../src/utils/jobDays";
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

describe("groupJobsByDay", () => {
  it("groups jobs by local day, newest first, labelled with the date", () => {
    const days = groupJobsByDay([
      job(5, new Date(2026, 10, 13, 9, 0)),
      job(4, new Date(2026, 10, 13, 0, 5)),
      job(3, new Date(2026, 10, 12, 23, 55)),
      job(2, new Date(2026, 10, 10, 12, 0)),
      job(1, new Date(2026, 10, 10, 8, 0)),
    ]);
    expect(days.map((d) => d.label)).toEqual([
      "Fri, 13.11.26",
      "Thu, 12.11.26",
      "Tue, 10.11.26",
    ]);
    expect(days.map((d) => d.jobs.map((j) => j.id))).toEqual([[5, 4], [3], [2, 1]]);
  });

  it("puts a job out of order into its day instead of starting it again", () => {
    const days = groupJobsByDay([
      job(3, new Date(2026, 10, 13, 9, 0)),
      job(2, new Date(2026, 10, 12, 9, 0)),
      job(1, new Date(2026, 10, 13, 8, 0)),
    ]);
    expect(days.map((d) => d.jobs.map((j) => j.id))).toEqual([[3, 1], [2]]);
  });

  it("gives no days for no jobs", () => {
    expect(groupJobsByDay([])).toEqual([]);
  });
});

describe("formatDay", () => {
  it("pads day, month and two-digit year", () => {
    expect(formatDay(new Date(2026, 10, 11))).toBe("Wed, 11.11.26");
    expect(formatDay(new Date(2027, 0, 3))).toBe("Sun, 03.01.27");
  });
});

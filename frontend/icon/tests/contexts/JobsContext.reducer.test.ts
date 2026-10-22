import { reducer, ScheduledJobs } from "../../src/contexts/JobsContext";
import { JobRunStatus, JobStatus } from "../../src/types/enums";

const JOB_ID = 1;
const RUN_ID = 2;
const LOG = "rfsoc: no response to exp.StartTask within 5s";

const jobs: ScheduledJobs = {
  [JOB_ID]: {
    id: JOB_ID,
    created: "2026-10-22T12:00:00",
    status: JobStatus.PROCESSING,
    experiment_id: "test.MockExperiment",
    num_scan_parameters: 1,
    run_id: RUN_ID,
    run_status: JobRunStatus.PROCESSING,
    run_log: null,
  },
};

const updateRun = (state: ScheduledJobs, status: JobRunStatus, log: string | null) =>
  reducer(state, {
    type: "UPDATE_JOB_RUN",
    payload: {
      run_id: RUN_ID,
      updated_properties: { status, log } as Record<string, string>,
    },
  });

test("a failed run update sets the log", () => {
  const state = updateRun(jobs, JobRunStatus.FAILED, LOG);
  expect(state[JOB_ID].run_status).toBe(JobRunStatus.FAILED);
  expect(state[JOB_ID].run_log).toBe(LOG);
});

test("a later run update clears the log", () => {
  const failed = updateRun(jobs, JobRunStatus.FAILED, LOG);
  const state = updateRun(failed, JobRunStatus.PROCESSING, null);
  expect(state[JOB_ID].run_status).toBe(JobRunStatus.PROCESSING);
  expect(state[JOB_ID].run_log).toBeNull();
});

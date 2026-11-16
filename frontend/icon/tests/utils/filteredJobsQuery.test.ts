import { FilteredJobsQuery } from "../../src/utils/filteredJobsQuery";
import { emptyDataFilters } from "../../src/utils/dataFilters";
import { JobStatus } from "../../src/types/enums";
import { latestDataJobId, resolveDataJobId } from "../../src/utils/dataJobSelection";

const job = (id: number, experiment_id = "test.Scan") => ({
  id,
  experiment_id,
  created: "2026-11-05T10:00:00+01:00",
  status: JobStatus.PROCESSED,
  num_scan_parameters: 1,
  run_id: null,
  run_status: null,
});
function harness(experiments = ["test.Scan"]) {
  const requests: {
    method: string;
    args: Record<string, unknown>;
    done: (value: unknown) => void;
  }[] = [];
  const query = new FilteredJobsQuery(
    { ...emptyDataFilters, experiments },
    (method, args, done) => requests.push({ method, args, done }),
    jest.fn(),
  );
  query.refresh();
  return { query, requests };
}

it("paginates matching results with a stable cursor and blocks overlapping requests", () => {
  const { query, requests } = harness();
  expect(requests[0].args).toEqual({
    experiment_ids: ["test.Scan"],
    limit: 100,
  });
  requests[0].done(Array.from({ length: 100 }, (_, i) => job(300 - i)));
  query.loadMore();
  expect(requests).toHaveLength(2); // active jobs still loading
  requests[1].done([]);
  query.loadMore();
  query.loadMore();
  expect(requests).toHaveLength(3);
  expect(requests[2].args).toEqual({
    experiment_ids: ["test.Scan"],
    limit: 100,
    before_id: 201,
  });
  requests[2].done([job(3)]);
  expect(Object.keys(query.state.jobs)).toHaveLength(101);
  expect(query.state.hasMore).toBe(false);
});

it("follows only matching live jobs and retains numbered selections", () => {
  const { query, requests } = harness(["test.Scan", "test.Second"]);
  requests[0].done([job(17)]);
  requests[1].done([]);
  query.update({ type: "ADD_JOB", payload: job(21, "other.Scan") });
  expect(latestDataJobId(query.state.jobs)).toBe(17);
  query.update({
    type: "ADD_JOB",
    payload: { ...job(22, "test.Second"), status: JobStatus.SUBMITTED },
  });
  expect(latestDataJobId(query.state.jobs)).toBe(22);
  expect(resolveDataJobId("11")).toBe(11);
});

it("does not overwrite a live status with a stale in-flight list response", () => {
  const { query, requests } = harness();
  query.update({
    type: "ADD_JOB",
    payload: { ...job(17), status: JobStatus.PROCESSING },
  });
  query.update({
    type: "UPDATE_JOB",
    payload: { job_id: 17, updated_properties: { status: JobStatus.PROCESSED } },
  });
  requests[0].done([]);
  requests[1].done([{ ...job(17), status: JobStatus.SUBMITTED }]);
  expect(query.state.jobs[17].status).toBe(JobStatus.PROCESSED);
});

it("ignores abandoned requests after disconnect, reconnect, and filter disposal", () => {
  const { query, requests } = harness();
  query.disconnect();
  requests[0].done([job(99)]);
  requests[1].done([]);
  expect(query.state.jobs).toEqual({});
  expect(query.state.error).toMatch(/Connection lost/);
  query.refresh();
  requests[2].done([job(17)]);
  requests[3].done([]);
  expect(query.state.error).toBeNull();
  query.loadMore();
  query.refresh();
  query.dispose();
  requests[4].done([job(99)]);
  requests[5].done([]);
  expect(query.state.jobs).toEqual({});
});

it("reports errors instead of treating a failed query as no matches, and retries", () => {
  const { query, requests } = harness();
  requests[0].done(new Error("Request failed"));
  requests[1].done([]);
  expect(query.state.error).toBe("Request failed");
  expect(query.state.loading).toBe(false);
  query.refresh();
  requests[2].done([]);
  requests[3].done([]);
  expect(query.state.error).toBeNull();
  expect(query.state.hasMore).toBe(false);
});

it("sends one query for all selected experiments and preserves the shared cursor", () => {
  const { query, requests } = harness(["test.Scan", "test.Second"]);
  expect(requests.map(({ method, args }) => [method, args])).toEqual([
    [
      "scheduler.get_job_list",
      { experiment_ids: ["test.Scan", "test.Second"], limit: 100 },
    ],
    [
      "scheduler.get_active_jobs",
      { experiment_ids: ["test.Scan", "test.Second"], limit: 100 },
    ],
  ]);
  requests[0].done(
    Array.from({ length: 100 }, (_, i) =>
      job(300 - i, i % 2 ? "test.Scan" : "test.Second"),
    ),
  );
  requests[1].done([{ ...job(302, "test.Second"), status: JobStatus.PROCESSING }]);
  expect(query.state.loading).toBe(false);
  expect(latestDataJobId(query.state.jobs)).toBe(302);
  query.loadMore();
  expect(requests[2].args).toEqual({
    experiment_ids: ["test.Scan", "test.Second"],
    limit: 100,
    before_id: 201,
  });
  requests[2].done([job(10, "test.Second")]);
  expect(Object.keys(query.state.jobs)).toHaveLength(102);
  expect(query.state.hasMore).toBe(false);
});

it("does not query the server when no experiments are selected", () => {
  const { query, requests } = harness([]);
  expect(requests).toHaveLength(0);
  expect(query.state).toEqual({
    jobs: {},
    loading: false,
    loadingMore: false,
    hasMore: false,
    error: null,
  });
  query.update({ type: "ADD_JOB", payload: job(17) });
  query.update({
    type: "UPDATE_JOB",
    payload: { job_id: 17, updated_properties: { status: JobStatus.PROCESSED } },
  });
  expect(requests).toHaveLength(0);
  expect(query.state.jobs).toEqual({});
});

it("does not mutate the supplied filters or request arguments across pages", () => {
  const { query, requests } = harness(["test.Scan", "test.Second"]);
  const firstArgs = requests[0].args;
  requests[0].done(Array.from({ length: 100 }, (_, i) => job(300 - i)));
  requests[1].done([]);
  query.loadMore();
  expect(firstArgs).toEqual({
    experiment_ids: ["test.Scan", "test.Second"],
    limit: 100,
  });
});

it("reports a failed multi-experiment page and retries the whole selection", () => {
  const { query, requests } = harness(["test.Scan", "test.Second"]);
  requests[0].done(new Error("History unavailable"));
  requests[1].done([]);
  expect(query.state.loading).toBe(false);
  expect(query.state.error).toBe("History unavailable");
  query.refresh();
  expect(requests[2].args.experiment_ids).toEqual(["test.Scan", "test.Second"]);
  requests[2].done([job(17)]);
  requests[3].done([]);
  expect(query.state.error).toBeNull();
  expect(Object.keys(query.state.jobs)).toEqual(["17"]);
});

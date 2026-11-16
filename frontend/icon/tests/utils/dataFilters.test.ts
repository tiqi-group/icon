import {
  dataFilterArguments,
  dataFilterError,
  emptyDataFilters,
  experimentDataUrl,
  hasDataFilters,
  matchesDataFilters,
  readDataFilters,
  withDataFilters,
} from "../../src/utils/dataFilters";
import { JobStatus } from "../../src/types/enums";

it("round-trips filters without changing the pinned selection or unrelated parameters", () => {
  const params = new URLSearchParams("jobId=17&context=a&context=b");
  const filters = {
    experiments: ["test.Scan (A & B)", "test.Other (x,y)"],
    from: "2026-10-25",
    to: "2026-11-05",
    job: "17",
  };
  const next = withDataFilters(params, filters);
  expect(readDataFilters(next)).toEqual(filters);
  expect(next.get("jobId")).toBe("17");
  expect(next.getAll("context")).toEqual(["a", "b"]);
  expect(withDataFilters(next, emptyDataFilters).toString()).toBe(params.toString());
  expect(
    new URL(
      experimentDataUrl(filters.experiments[0]),
      "http://localhost",
    ).searchParams.get("experiment"),
  ).toBe(filters.experiments[0]);
});

it("links to an experiment's data without encoding Latest in jobId", () => {
  const url = new URL(experimentDataUrl("test.Scan"), "http://localhost");
  expect(url.searchParams.get("experiment")).toBe("test.Scan");
  expect(url.searchParams.has("jobId")).toBe(false);
});

it.each(["2026-02-30", "2025-02-29", "2026-1-1", "0000-01-01", "9999-12-31"])(
  "rejects invalid calendar date %s",
  (from) => {
    expect(dataFilterError({ ...emptyDataFilters, from })).not.toBeNull();
  },
);

it("validates date order and exact job IDs", () => {
  expect(dataFilterError({ ...emptyDataFilters, from: "2024-02-29" })).toBeNull();
  expect(
    dataFilterError({ ...emptyDataFilters, from: "2026-11-05", to: "2026-11-04" }),
  ).not.toBeNull();
  for (const job of ["0", "-1", "1.5", "1e3", "17x", "9007199254740992"]) {
    expect(dataFilterError({ ...emptyDataFilters, job })).not.toBeNull();
  }
  expect(dataFilterArguments({ ...emptyDataFilters, job: "0017" })).toEqual({
    job_id: 17,
  });
});

it("matches the inclusive ICON calendar date even when UTC is the previous day", () => {
  const job = {
    id: 17,
    experiment_id: "test.Scan",
    created: "2026-10-25T00:15:00+02:00",
    status: JobStatus.PROCESSED,
    num_scan_parameters: 1,
    run_id: null,
    run_status: null,
  };
  const filters = {
    experiments: ["test.Scan", "test.ScanTwo"],
    from: "2026-10-25",
    to: "2026-10-25",
    job: "17",
  };
  expect(matchesDataFilters(job, filters)).toBe(true);
  expect(matchesDataFilters({ ...job, experiment_id: "test.ScanTwo" }, filters)).toBe(
    true,
  );
  expect(matchesDataFilters(job, emptyDataFilters)).toBe(true);
  expect(matchesDataFilters(job, { ...emptyDataFilters, experiments: [] })).toBe(false);
  expect(matchesDataFilters({ ...job, experiment_id: "test.ScanOther" }, filters)).toBe(
    false,
  );
  expect(
    matchesDataFilters({ ...job, created: "2026-10-26T00:00:00+01:00" }, filters),
  ).toBe(false);
});

it("distinguishes All from None and preserves legacy single-experiment links", () => {
  const all = readDataFilters(new URLSearchParams());
  expect(all).toEqual(emptyDataFilters);
  expect(hasDataFilters(all)).toBe(false);
  expect(dataFilterArguments(all)).toEqual({});

  const none = { ...all, experiments: [] };
  const params = withDataFilters(new URLSearchParams("experiment=test.Scan"), none);
  expect(params.toString()).toBe("experiment=");
  expect(readDataFilters(params)).toEqual(none);
  expect(hasDataFilters(none)).toBe(true);
  expect(
    readDataFilters(new URLSearchParams("experiment=test.Scan")).experiments,
  ).toEqual(["test.Scan"]);
});

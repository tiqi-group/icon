import { useEffect, useState } from "react";
import { runMethod, socket } from "../../../src/socket";
import { usePlotViewerJob } from "../../../src/features/plot-viewer/usePlotViewerJob";
import type { Job } from "../../../src/types/Job";
import type { JobRun } from "../../../src/types/JobRun";
import { JobStatus, JobRunStatus } from "../../../src/types/enums";

jest.mock("react", () => ({ useEffect: jest.fn(), useState: jest.fn() }));
jest.mock("../../../src/socket", () => ({
  runMethod: jest.fn(),
  socket: { on: jest.fn(), off: jest.fn() },
}));
jest.mock("../../../src/utils/deserializer", () => ({
  deserialize: (value: unknown) => value,
}));

interface Request {
  path: string;
  args: unknown[];
  kwargs: Record<string, unknown>;
  callback: (ack: unknown) => void;
}
interface Effect {
  dependencies: unknown[];
  cleanup?: () => void;
}
const states: unknown[] = [];
const effects: Effect[] = [];
const pending: (() => void)[] = [];
const requests: Request[] = [];
const listeners = new Map<string, (event: unknown) => void>();
let stateCursor = 0;
let effectCursor = 0;
let dirty = false;
let currentJob = "1";
let connected = true;
let result: ReturnType<typeof usePlotViewerJob>;
const latestRequest = (path: string) =>
  requests.filter((request) => request.path === path).at(-1)!;
const metadataRequests = () =>
  requests.filter((request) => request.path === "experiments.get_metadata");

// Browser-free state/effect harness: dependent metadata effects follow scheduler replies.
function render(jobId = currentJob, isConnected = connected) {
  currentJob = jobId;
  connected = isConnected;
  let renders = 0;
  do {
    if (++renders > 15) throw new Error("Hook did not settle");
    dirty = false;
    stateCursor = 0;
    effectCursor = 0;
    result = usePlotViewerJob(currentJob, connected);
    while (pending.length) pending.shift()!();
  } while (dirty);
  return result;
}
function respond(request: Request, value: unknown) {
  request.callback(value);
  return render();
}
function job(id = 1, experimentId = "package.Experiment"): Job {
  return {
    id,
    experiment_source: { id, experiment_id: experimentId },
    experiment_source_id: id,
    auto_calibration: false,
    created: "2026-10-22T10:00:00+02:00",
    debug_mode: false,
    local_parameters_timestamp: "",
    priority: 0,
    repetitions: 1,
    scan_parameters: [],
    status: JobStatus.PROCESSED,
  };
}
function run(value = job()): JobRun {
  return {
    id: value.id + 10,
    job_id: value.id,
    job: value,
    scheduled_time: "2026-10-22T11:12:13.123456+02:00",
    status: JobRunStatus.DONE,
  };
}
function metadata(name?: string, className = "Readable class") {
  return {
    class_name: className,
    constructor_kwargs: name === undefined ? {} : { name },
    parameters: {},
  };
}

beforeEach(() => {
  jest.clearAllMocks();
  states.length = 0;
  effects.length = 0;
  pending.length = 0;
  requests.length = 0;
  listeners.clear();
  currentJob = "1";
  connected = true;
  stateCursor = 0;
  effectCursor = 0;
  dirty = false;
  (useState as jest.Mock).mockImplementation((initial: unknown) => {
    const index = stateCursor++;
    if (index >= states.length) states.push(initial);
    return [
      states[index],
      (next: unknown) => {
        const value = typeof next === "function" ? next(states[index]) : next;
        if (!Object.is(value, states[index])) {
          states[index] = value;
          dirty = true;
        }
      },
    ];
  });
  (useEffect as jest.Mock).mockImplementation(
    (setup: () => (() => void) | undefined, dependencies: unknown[]) => {
      const index = effectCursor++;
      const previous = effects[index];
      if (
        previous &&
        dependencies.length === previous.dependencies.length &&
        dependencies.every((dependency, item) =>
          Object.is(dependency, previous.dependencies[item]),
        )
      )
        return;
      const effect: Effect = { dependencies };
      effects[index] = effect;
      pending.push(() => {
        previous?.cleanup?.();
        effect.cleanup = setup();
      });
    },
  );
  (runMethod as jest.Mock).mockImplementation(
    (
      path: string,
      args: unknown[],
      kwargs: Record<string, unknown>,
      callback: (ack: unknown) => void,
    ) => {
      requests.push({ path, args, kwargs, callback });
    },
  );
  (socket.on as jest.Mock).mockImplementation(
    (event: string, handler: (event: unknown) => void) => {
      listeners.set(event, handler);
    },
  );
  (socket.off as jest.Mock).mockImplementation(
    (event: string, handler: (event: unknown) => void) => {
      if (listeners.get(event) === handler) listeners.delete(event);
    },
  );
});
afterEach(() => {
  effects.forEach((effect) => effect.cleanup?.());
});

test("uses the source-ID fallback until readable experiment metadata arrives", () => {
  render();
  expect(result.experimentName).toBeUndefined();
  respond(latestRequest("scheduler.get_job_by_id"), job());
  expect(result.experimentName).toBe("Experiment");
  expect(metadataRequests()[0].args).toEqual(["package.Experiment"]);
  respond(metadataRequests()[0], metadata("Custom experiment"));
  expect(result.experimentName).toBe("Custom experiment");
});

test("falls back to metadata class name, then source ID on absent or failed metadata", () => {
  render();
  respond(latestRequest("scheduler.get_job_by_id"), job());
  respond(metadataRequests()[0], metadata());
  expect(result.experimentName).toBe("Readable class");
  render("1", false);
  render("1", true);
  respond(metadataRequests().at(-1)!, new Error("Metadata unavailable"));
  expect(result.experimentName).toBe("Readable class");
  render("2", true);
  respond(latestRequest("scheduler.get_job_by_id"), job(2, "other.Fallback"));
  respond(metadataRequests().at(-1)!, null);
  expect(result.experimentName).toBe("Fallback");
  expect(result.error).toBeNull();
});

test.each(["", "   "])(
  "blank custom name %p falls back to a valid metadata class name",
  (name) => {
    render();
    respond(latestRequest("scheduler.get_job_by_id"), job());
    respond(metadataRequests()[0], metadata(name));
    expect(result.experimentName).toBe("Readable class");
  },
);

test("ignores late metadata for a superseded experiment source", () => {
  render();
  respond(latestRequest("scheduler.get_job_by_id"), job());
  const stale = metadataRequests()[0];
  listeners.get("job.update")?.({ job_id: 1 });
  respond(latestRequest("scheduler.get_job_by_id"), job(1, "package.NewExperiment"));
  const fresh = metadataRequests().at(-1)!;
  expect(result.experimentName).toBe("NewExperiment");
  respond(stale, metadata("Wrong old title"));
  expect(result.experimentName).toBe("NewExperiment");
  respond(fresh, metadata("Correct new title"));
  expect(result.experimentName).toBe("Correct new title");
});

test("preserves known experiment name and scheduled time across disconnect and reconnect", () => {
  render();
  respond(latestRequest("scheduler.get_job_by_id"), job());
  respond(latestRequest("scheduler.get_job_run_by_id"), run());
  respond(metadataRequests()[0], metadata("Stable title"));
  const scheduledTime = result.run?.scheduled_time;
  render("1", false);
  expect(result.experimentName).toBe("Stable title");
  expect(result.run?.scheduled_time).toBe(scheduledTime);
  expect(listeners.size).toBe(0);
  render("1", true);
  const reconnectMetadata = metadataRequests().at(-1)!;
  expect(result.experimentName).toBe("Stable title");
  expect(result.run?.scheduled_time).toBe(scheduledTime);
  respond(reconnectMetadata, metadata("Refreshed title"));
  expect(result.experimentName).toBe("Refreshed title");
});

test("ignores metadata callbacks that finish while disconnected or after a newer reconnect request", () => {
  render();
  respond(latestRequest("scheduler.get_job_by_id"), job());
  const stale = metadataRequests()[0];
  render("1", false);
  respond(stale, metadata("Must not appear"));
  expect(result.experimentName).toBe("Experiment");
  render("1", true);
  const fresh = metadataRequests().at(-1)!;
  respond(fresh, metadata("New connection"));
  respond(stale, metadata("Still stale"));
  expect(result.experimentName).toBe("New connection");
});

test("a newer scheduler refresh invalidates older job and run acknowledgements", () => {
  render();
  const oldJob = latestRequest("scheduler.get_job_by_id");
  const oldRun = latestRequest("scheduler.get_job_run_by_id");
  listeners.get("job.update")?.({ job_id: 1 });
  const newJob = latestRequest("scheduler.get_job_by_id");
  const newRun = latestRequest("scheduler.get_job_run_by_id");
  respond(oldJob, job(1, "package.Wrong"));
  respond(oldRun, run());
  expect(result.job).toBeNull();
  expect(result.run).toBeNull();
  respond(newJob, job(1, "package.Right"));
  respond(newRun, run(job(1, "package.Right")));
  expect(result.experimentName).toBe("Right");
  expect(result.run?.job.experiment_source.experiment_id).toBe("package.Right");
});

test("changing jobs clears old run identity and prevents stale metadata from returning", () => {
  render();
  respond(latestRequest("scheduler.get_job_by_id"), job());
  respond(latestRequest("scheduler.get_job_run_by_id"), run());
  const oldMetadata = metadataRequests()[0];
  render("2", true);
  expect(result.job).toBeNull();
  expect(result.run).toBeNull();
  expect(result.experimentName).toBeUndefined();
  respond(oldMetadata, metadata("Wrong job"));
  respond(latestRequest("scheduler.get_job_by_id"), job(2, "package.Second"));
  expect(result.experimentName).toBe("Second");
});

test("unmount removes listeners and invalidates pending metadata replies", () => {
  render();
  respond(latestRequest("scheduler.get_job_by_id"), job());
  const pendingMetadata = metadataRequests()[0];
  effects.forEach((effect) => effect.cleanup?.());
  const before = [...states];
  pendingMetadata.callback(metadata("After unmount"));
  expect(states).toEqual(before);
  expect(listeners.size).toBe(0);
});

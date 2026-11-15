import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { JobsContext, reducer } from "../src/contexts/JobsContext";
import type { ScheduledJobs } from "../src/contexts/JobsContext";
import { DataPage } from "../src/pages/data";
import { JobStatus } from "../src/types/enums";
import { openVisualizerWindow } from "../src/utils/windowUtils";
import { resolveDataJobId } from "../src/utils/dataJobSelection";
import type { DataFilters } from "../src/utils/dataFilters";
import { emptyFilteredJobs } from "../src/utils/filteredJobsQuery";

interface SwitchProps {
  checked: boolean;
  onChange: (event: unknown, checked: boolean) => void;
}
interface RowProps {
  selected: boolean;
  onClick: () => void;
}
interface ButtonProps {
  onClick: () => void;
}

const mockSetSearchParams = jest.fn<void, [URLSearchParams]>();
const mockNavigate = jest.fn<void, [string]>();
const mockSwitch = jest.fn<void, [SwitchProps]>();
const mockRow = jest.fn<void, [RowProps]>();
const mockVisualizerButton = jest.fn<void, [ButtonProps]>();
let mockLatest: boolean | undefined;
const mockSetLatest = jest.fn((value: boolean) => {
  mockLatest = value;
});
jest.mock("../src/hooks/useBrowserSetting", () => ({
  useBrowserSetting: (_key: string, defaultValue: boolean) => [
    mockLatest ?? defaultValue,
    mockSetLatest,
  ],
}));
const originalSessionStorage = Object.getOwnPropertyDescriptor(
  globalThis,
  "sessionStorage",
);
beforeAll(() =>
  Object.defineProperty(globalThis, "sessionStorage", {
    configurable: true,
    value: {},
  }),
);
afterAll(() => {
  if (originalSessionStorage)
    Object.defineProperty(globalThis, "sessionStorage", originalSessionStorage);
  else Reflect.deleteProperty(globalThis, "sessionStorage");
});
let mockSearchParams: URLSearchParams;
let mockFilteredJobs = {
  ...emptyFilteredJobs,
  loading: false,
  loadMore: jest.fn(),
  retry: jest.fn(),
};
const mockFilters = jest.fn<
  void,
  [{ filters: DataFilters; onApply: (filters: DataFilters) => void }]
>();
jest.mock("../src/hooks/useFilteredDataJobs", () => ({
  useFilteredDataJobs: () => mockFilteredJobs,
}));
jest.mock("../src/components/data/DataFilters", () => ({
  DataFilters: (props: Parameters<typeof mockFilters>[0]) => {
    mockFilters(props);
    return null;
  },
}));
jest.mock("../src/components/data/SelectedJobFilterNotice", () => ({
  SelectedJobFilterNotice: ({ jobId }: { jobId: number }) => (
    <div>Filter notice for {jobId}</div>
  ),
}));
jest.mock("../src/components/data/filters.css", () => ({}));

jest.mock("react-router", () => ({
  useSearchParams: () => [mockSearchParams, mockSetSearchParams],
  useNavigate: () => mockNavigate,
}));

jest.mock("@mui/material", () => {
  const container = ({ children }: { children?: ReactNode }) => <div>{children}</div>;
  return {
    Alert: container,
    Button: (props: ButtonProps) => {
      mockVisualizerButton(props);
      return null;
    },
    CircularProgress: () => null,
    FormControlLabel: ({ control }: { control: ReactNode }) => control,
    List: container,
    ListItem: container,
    ListItemButton: (props: RowProps & { children: ReactNode }) => {
      mockRow(props);
      return container(props);
    },
    ListItemText: container,
    ListSubheader: container,
    Switch: (props: SwitchProps) => {
      mockSwitch(props);
      return null;
    },
    Tooltip: container,
  };
});

jest.mock("@mui/icons-material/SsidChart", () => () => null);
jest.mock("../src/components/JobStatusIndicator", () => ({
  JobStatusIndicator: () => null,
}));
jest.mock("../src/components/JobView", () => ({
  JobView: ({ jobId }: { jobId: string }) => <div>Details for {jobId}</div>,
}));
jest.mock("../src/utils/windowUtils", () => ({
  openJobWindow: jest.fn(),
  openVisualizerWindow: jest.fn(),
}));

const job = (id: number, status: JobStatus = JobStatus.PROCESSED) => ({
  id,
  status,
  created: "2026-11-04T10:00:00Z",
  experiment_id: "experiments.TestScan",
  num_scan_parameters: 1,
  run_id: null,
  run_status: null,
});

const renderData = (jobs: ScheduledJobs, loading = false) =>
  renderToStaticMarkup(
    <JobsContext.Provider
      value={{ jobs, loading, loadingMore: false, hasMore: false, loadMore: jest.fn() }}
    >
      <DataPage />
    </JobsContext.Provider>,
  );

beforeEach(() => {
  jest.clearAllMocks();
  mockLatest = undefined;
  mockSearchParams = new URLSearchParams("context=operator&filter=a&filter=b");
  mockFilteredJobs = {
    ...emptyFilteredJobs,
    loading: false,
    loadMore: jest.fn(),
    retry: jest.fn(),
  };
});

it("uses the filtered feed for Latest and preserves a numeric detail outside the list", () => {
  mockSearchParams.set("experiment", "experiments.TestScan");
  mockLatest = true;
  mockSearchParams.set("jobId", "17");
  mockFilteredJobs.jobs = { 17: job(17) };
  expect(renderData({ 99: job(99) })).toContain("Details for 17");
  mockFilteredJobs.jobs = { 17: job(17), 20: job(20) };
  expect(renderData({ 99: job(99) })).toContain("Details for 20");
  mockSearchParams.set("jobId", "11");
  mockLatest = false;
  mockFilteredJobs.loading = true;
  expect(renderData({ 99: job(99) })).toContain("Details for 11");
  expect(renderData({ 99: job(99) })).toContain("Filter notice for 11");
  mockFilters.mock.lastCall![0].onApply({
    experiments: ["another.Scan"],
    from: "",
    to: "",
    job: "",
  });
  expect(mockSetSearchParams.mock.lastCall![0].get("jobId")).toBe("11");
  expect(mockSetSearchParams.mock.lastCall![0].getAll("filter")).toEqual(["a", "b"]);
});

it("does not fall back to unrelated jobs when no filters match or the URL is invalid", () => {
  mockLatest = true;
  mockSearchParams.set("jobId", "99");
  mockSearchParams.set("job", "123");
  expect(renderData({ 99: job(99) })).toContain("No jobs match these filters");
  expect(renderData({ 99: job(99) })).not.toContain("Details for 99");
  mockSearchParams.set("job", "bad");
  expect(renderData({ 99: job(99) })).toContain(
    "Job ID must be a positive whole number",
  );
});

it.each<[string | null, number | null]>([
  [null, null],
  ["", null],
  ["NaN", null],
  ["latest", null],
  ["7oops", null],
  ["1e3", null],
  ["9007199254740992", null],
  ["0017", 17],
  ["17", 17],
])("resolves URL selection %p to %p", (selection, expected) => {
  expect(resolveDataJobId(selection)).toBe(expected);
});

it("follows a live JobsContext addition, selecting and opening the resolved numeric ID", () => {
  mockLatest = true;
  mockSearchParams.set("jobId", "9");
  const initial = { 4: job(4), 9: job(9) };
  expect(renderData(initial)).toContain("Details for 9");
  expect(mockSwitch).toHaveBeenLastCalledWith(
    expect.objectContaining({ checked: true }),
  );
  expect(mockRow.mock.calls.map(([row]) => row.selected)).toEqual([true, false]);

  mockRow.mockClear();
  const jobs = reducer(initial, {
    type: "ADD_JOB",
    payload: job(10, JobStatus.SUBMITTED),
  });
  expect(renderData(jobs)).toContain("Details for 10");
  expect(mockRow.mock.calls.map(([row]) => row.selected)).toEqual([true, false, false]);
  // Effects are exercised in the browser; rendering already shows the new job.
  expect(mockSearchParams.get("jobId")).toBe("9");
  expect(mockSetSearchParams).not.toHaveBeenCalled();

  const storage = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  const getItem = jest.fn().mockReturnValueOnce(null).mockReturnValueOnce("false");
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: { getItem },
  });
  try {
    const openVisualizer = mockVisualizerButton.mock.lastCall![0].onClick;
    openVisualizer();
    expect(openVisualizerWindow).toHaveBeenCalledWith("10");
    openVisualizer();
    expect(mockNavigate).toHaveBeenCalledWith("/sequence?jobId=10");
  } finally {
    if (storage) Object.defineProperty(globalThis, "localStorage", storage);
    else Reflect.deleteProperty(globalThis, "localStorage");
  }
});

it("defaults to Latest without a job but opens a specific job with Latest off", () => {
  expect(renderData({ 9: job(9) })).toContain("Details for 9");
  expect(mockSwitch.mock.lastCall![0].checked).toBe(true);
  mockSearchParams.set("jobId", "4");
  expect(renderData({ 4: job(4), 9: job(9) })).toContain("Details for 4");
  expect(mockSwitch.mock.lastCall![0].checked).toBe(false);
});

it("remembers Latest off for an unqualified visit", () => {
  mockLatest = false;
  expect(renderData({ 9: job(9) })).toContain("Select a job");
  expect(mockSwitch.mock.lastCall![0].checked).toBe(false);
});

it("toggles Latest and only disables it when an older job is selected", () => {
  const jobs = { 4: job(4), 9: job(9) };
  mockSearchParams.set("jobId", "4");
  expect(renderData(jobs)).toContain("Details for 4");
  expect(mockSwitch).toHaveBeenLastCalledWith(
    expect.objectContaining({ checked: false }),
  );
  mockRow.mock.lastCall![0].onClick();
  expect(mockSetSearchParams).not.toHaveBeenCalled();
  mockSwitch.mock.lastCall![0].onChange(null, true);
  expect(mockSetLatest).toHaveBeenLastCalledWith(true);
  expect(mockSearchParams.get("jobId")).toBe("4");

  mockSearchParams.set("jobId", "9");
  mockRow.mockClear();
  expect(renderData(jobs)).toContain("Details for 9");
  mockSetLatest.mockClear();
  mockRow.mock.calls[0][0].onClick();
  expect(mockSetLatest).not.toHaveBeenCalled();
  mockSwitch.mock.lastCall![0].onChange(null, false);
  expect(mockSetLatest).toHaveBeenLastCalledWith(false);
  expect(renderData(jobs)).toContain("Details for 9");
  mockRow.mock.lastCall![0].onClick();
  expect(mockSetLatest).toHaveBeenLastCalledWith(false);
  expect(mockSetSearchParams.mock.lastCall![0].toString()).toBe(
    "context=operator&filter=a&filter=b&jobId=4",
  );
});

it("has no job consumers while Latest is unresolved", () => {
  mockLatest = true;
  mockSearchParams.set("jobId", "9");
  expect(renderData({}, true)).toContain("Loading...");
  expect(renderData({})).toContain("Waiting for a job");
  expect(mockVisualizerButton).not.toHaveBeenCalled();
  expect(mockSetSearchParams).not.toHaveBeenCalled();
  mockSwitch.mock.lastCall![0].onChange(null, false);
  expect(mockSetLatest).toHaveBeenLastCalledWith(false);
});

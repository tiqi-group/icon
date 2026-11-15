import { renderToStaticMarkup } from "react-dom/server";
import { useRestoredPageUrl } from "../../src/hooks/useRestoredPageUrl";

let mockLocation = { pathname: "/experiments", search: "" };
let mockNavigationType = "PUSH";
let mockLocationState: { clearRememberedSearch: boolean } | null = null;
const savedSearches = new Map<string, string>();

jest.mock("react-router", () => ({
  NavigationType: { Push: "PUSH", Pop: "POP", Replace: "REPLACE" },
  useLocation: () => ({ ...mockLocation, state: mockLocationState }),
  useNavigationType: () => mockNavigationType,
}));

const originalStorage = Object.getOwnPropertyDescriptor(globalThis, "sessionStorage");
beforeAll(() =>
  Object.defineProperty(globalThis, "sessionStorage", {
    configurable: true,
    value: { getItem: (key: string) => savedSearches.get(key) ?? null },
  }),
);
afterAll(() => {
  if (originalStorage)
    Object.defineProperty(globalThis, "sessionStorage", originalStorage);
  else Reflect.deleteProperty(globalThis, "sessionStorage");
});
beforeEach(() => {
  savedSearches.clear();
  mockLocation = { pathname: "/experiments", search: "" };
  mockNavigationType = "PUSH";
  mockLocationState = null;
});

function Destination() {
  return <span>{useRestoredPageUrl() ?? "unchanged"}</span>;
}
const destination = () => renderToStaticMarkup(<Destination />);

it("restores the selected experiment when opening the section without a query", () => {
  savedSearches.set("lastSearch:/experiments", "?experiment=test.Scan");
  expect(destination()).toContain("/experiments?experiment=test.Scan");
});

it("restores a job together with its data filters", () => {
  mockLocation.pathname = "/data";
  savedSearches.set("lastSearch:/data", "?jobId=17&experiment=test.Scan");
  expect(destination()).toContain("/data?jobId=17&amp;experiment=test.Scan");
});

it.each(["POP", "REPLACE"])("does not restore on %s navigation", (navigationType) => {
  mockNavigationType = navigationType;
  savedSearches.set("lastSearch:/experiments", "?experiment=test.Scan");
  expect(destination()).toContain("unchanged");
});

it("honors explicitly clearing the last filter", () => {
  mockLocation.pathname = "/data";
  savedSearches.set("lastSearch:/data", "?experiment=");
  mockLocationState = { clearRememberedSearch: true };
  expect(destination()).toContain("unchanged");
});

it("honors an explicit destination query", () => {
  savedSearches.set("lastSearch:/experiments", "?experiment=test.Scan");
  mockLocation.search = "?experiment=test.Other";
  expect(destination()).toContain("unchanged");
});

it("leaves a fresh section unselected", () => {
  expect(destination()).toContain("unchanged");
});

it.each(["/parameters", "/sequence"])(
  "does not restore unrelated %s state",
  (pathname) => {
    mockLocation.pathname = pathname;
    savedSearches.set(`lastSearch:${pathname}`, "?jobId=17");
    expect(destination()).toContain("unchanged");
  },
);

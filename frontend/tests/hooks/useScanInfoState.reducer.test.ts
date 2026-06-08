import {
  reducer,
  defaultScanInfoState,
  defaultParameter,
  ScanInfoState,
} from "../../src/hooks/useScanInfoState";

class LocalStorageMock {
  store: Record<string, string> = {};
  getItem(key: string) {
    return this.store[key] ?? null;
  }
  setItem(key: string, value: string) {
    this.store[key] = String(value);
  }
  removeItem(key: string) {
    delete this.store[key];
  }
  clear() {
    this.store = {};
  }
}

const EXP = "exp1";
const STORAGE_KEY = `scanInfoState:${EXP}`;
const run = reducer(EXP);

let store: LocalStorageMock;
beforeEach(() => {
  store = new LocalStorageMock();
  (globalThis as unknown as { localStorage: LocalStorageMock }).localStorage = store;
});

const baseState = (): ScanInfoState => structuredClone(defaultScanInfoState);

describe("useScanInfoState reducer", () => {
  it("RESET replaces the whole state with the payload", () => {
    const payload = { ...baseState(), priority: 99 };
    expect(run(baseState(), { type: "RESET", payload })).toBe(payload);
  });

  it("SET_PRIORITY / SET_SHOTS / SET_REPETITIONS update the matching field", () => {
    expect(run(baseState(), { type: "SET_PRIORITY", payload: 5 }).priority).toBe(5);
    expect(run(baseState(), { type: "SET_SHOTS", payload: 7 }).shots).toBe(7);
    expect(run(baseState(), { type: "SET_REPETITIONS", payload: 3 }).repetitions).toBe(
      3,
    );
  });

  it("ADD_PARAMETER appends a default parameter", () => {
    const next = run(baseState(), { type: "ADD_PARAMETER" });
    expect(next.parameters).toHaveLength(2);
    expect(next.parameters[1]).toEqual(defaultParameter);
  });

  it("REMOVE_PARAMETER drops the parameter at the index", () => {
    const twoParams = {
      ...baseState(),
      parameters: [defaultParameter, defaultParameter],
    };
    const next = run(twoParams, { type: "REMOVE_PARAMETER", index: 0 });
    expect(next.parameters).toHaveLength(1);
  });

  it("UPDATE_PARAMETER with id 'Real Time' updates the param but not navHistory", () => {
    const state = baseState();
    const next = run(state, {
      type: "UPDATE_PARAMETER",
      index: 0,
      payload: { id: "Real Time", namespace: "Real Time", n_scan_points: 0 },
    });
    expect(next.parameters[0].id).toBe("Real Time");
    expect(next.navHistory).toBe(state.navHistory); // untouched reference
  });

  it("UPDATE_PARAMETER (normal) resolves the param and records navHistory", () => {
    const next = run(baseState(), {
      type: "UPDATE_PARAMETER",
      index: 0,
      payload: { namespace: "E1" },
    });
    expect(next.parameters[0].namespace).toBe("E1");
    expect(next.parameters[0].generation).toEqual(defaultParameter.generation);
    expect(next.navHistory).not.toEqual(defaultScanInfoState.navHistory);
  });

  it("persists the new state to localStorage", () => {
    run(baseState(), { type: "SET_SHOTS", payload: 42 });
    const saved = JSON.parse(store.getItem(STORAGE_KEY) as string);
    expect(saved.shots).toBe(42);
  });
});

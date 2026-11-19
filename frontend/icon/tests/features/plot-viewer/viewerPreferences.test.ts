import {
  readViewerWindowSize,
  rememberViewerWindowSize,
} from "../../../src/features/plot-viewer/viewerPreferences";
test("Window size survives a fresh read without sharing the job-view setting", () => {
  const values = new Map<string, string>([["defaultWindowSize", "50"]]);
  const storage = {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => {
      values.set(key, value);
    },
  };
  expect(readViewerWindowSize(storage)).toBe(1000);
  rememberViewerWindowSize(250, storage);
  expect(readViewerWindowSize(storage)).toBe(250);
  expect(values.get("defaultWindowSize")).toBe("50");
});
test("invalid or unavailable storage keeps a usable default", () => {
  for (const value of [null, "NaN", "-1", "0", "1.5", "100001"])
    expect(readViewerWindowSize({ getItem: () => value })).toBe(1000);
  expect(
    readViewerWindowSize({
      getItem: () => {
        throw Error();
      },
    }),
  ).toBe(1000);
  expect(() =>
    rememberViewerWindowSize(50, {
      setItem: () => {
        throw Error();
      },
    }),
  ).not.toThrow();
});

test("a throwing global storage getter cannot prevent the viewer from loading", () => {
  const original = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  try {
    Object.defineProperty(globalThis, "localStorage", {
      configurable: true,
      get() {
        throw new Error("Storage is blocked");
      },
    });
    expect(readViewerWindowSize()).toBe(1000);
    expect(() => rememberViewerWindowSize(250)).not.toThrow();
    // Explicit storage still works without touching the unavailable global getter.
    expect(readViewerWindowSize({ getItem: () => "250" })).toBe(250);
  } finally {
    if (original) Object.defineProperty(globalThis, "localStorage", original);
    else Reflect.deleteProperty(globalThis, "localStorage");
  }
});

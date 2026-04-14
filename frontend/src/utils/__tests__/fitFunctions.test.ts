import { FIT_DEFAULT_UPDATE_PARAM, FIT_PARAM_NAMES, FIT_TYPES } from "../fitFunctions";

describe("fit model metadata", () => {
  it("every FIT_TYPE has param names defined", () => {
    for (const ft of FIT_TYPES) {
      expect(FIT_PARAM_NAMES[ft]).toBeDefined();
      expect(FIT_PARAM_NAMES[ft].length).toBeGreaterThan(0);
    }
  });

  it("every FIT_TYPE has a default update param", () => {
    for (const ft of FIT_TYPES) {
      expect(FIT_DEFAULT_UPDATE_PARAM[ft]).toBeDefined();
    }
  });

  it("FIT_TYPES contains expected models", () => {
    expect(FIT_TYPES).toContain("lorentzian");
    expect(FIT_TYPES).toContain("gaussian");
    expect(FIT_TYPES).toContain("poly2");
    expect(FIT_TYPES).toContain("harmonic");
    expect(FIT_TYPES).toContain("damped_harmonic");
  });
});

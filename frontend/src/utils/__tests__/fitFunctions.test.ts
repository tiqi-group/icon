import { evaluateFit } from "../fitFunctions";

describe("evaluateFit", () => {
  describe("lorentzian", () => {
    it("should return peak value at x0", () => {
      const params = { y0: 0, a: 10, x0: 5, gamma: 1 };
      const result = evaluateFit("lorentzian", params, [5]);
      expect(result[0]).toBeCloseTo(10, 5);
    });

    it("should return baseline far from peak", () => {
      const params = { y0: 3, a: 10, x0: 0, gamma: 1 };
      const result = evaluateFit("lorentzian", params, [1e6]);
      expect(result[0]).toBeCloseTo(3, 1);
    });

    it("should be symmetric around x0", () => {
      const params = { y0: 0, a: 1, x0: 5, gamma: 1 };
      const [left] = evaluateFit("lorentzian", params, [3]);
      const [right] = evaluateFit("lorentzian", params, [7]);
      expect(left).toBeCloseTo(right, 10);
    });
  });

  describe("gaussian", () => {
    it("should return peak value at x0", () => {
      const params = { y0: 0, a: 5, x0: 3, sigma: 1 };
      const result = evaluateFit("gaussian", params, [3]);
      expect(result[0]).toBeCloseTo(5, 5);
    });
  });

  describe("poly2", () => {
    it("should compute quadratic correctly", () => {
      const params = { a: 1, b: 2, c: 3 };
      const result = evaluateFit("poly2", params, [0, 1, 2]);
      expect(result[0]).toBeCloseTo(3);
      expect(result[1]).toBeCloseTo(6);
      expect(result[2]).toBeCloseTo(11);
    });
  });

  describe("harmonic", () => {
    it("should return y0 + A at phase 0", () => {
      const params = { y0: 1, a: 2, omega: Math.PI, phi: 0 };
      const result = evaluateFit("harmonic", params, [0]);
      expect(result[0]).toBeCloseTo(3);
    });
  });

  describe("damped_harmonic", () => {
    it("should match harmonic with k=0", () => {
      const x = [0, 1, 2, 3, 4, 5];
      const harmonicParams = { y0: 1, a: 2, omega: 3, phi: 0.5 };
      const dampedParams = { y0: 1, a: 2, k: 0, omega: 3, phi: 0.5 };

      const harmonic = evaluateFit("harmonic", harmonicParams, x);
      const damped = evaluateFit("damped_harmonic", dampedParams, x);

      for (let i = 0; i < x.length; i++) {
        expect(damped[i]).toBeCloseTo(harmonic[i], 10);
      }
    });
  });

  describe("unknown function", () => {
    it("should return NaN for unknown types", () => {
      const result = evaluateFit("unknown", {}, [1, 2, 3]);
      expect(result.every((v) => isNaN(v))).toBe(true);
    });
  });
});

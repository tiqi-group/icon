/**
 * Evaluate a fit function at the given x-values using fitted parameters.
 */
export function evaluateFit(
  funcType: string,
  params: Record<string, number>,
  xValues: number[],
): number[] {
  switch (funcType) {
    case "lorentzian":
      return xValues.map((x) => {
        const { y0, a, x0, gamma } = params;
        return y0 + a / (1 + ((x - x0) / gamma) ** 2);
      });

    case "gaussian":
      return xValues.map((x) => {
        const { y0, a, x0, sigma } = params;
        return y0 + a * Math.exp(-((x - x0) ** 2) / (2 * sigma ** 2));
      });

    case "poly2":
      return xValues.map((x) => {
        const { a, b, c } = params;
        return a * x ** 2 + b * x + c;
      });

    case "harmonic":
      return xValues.map((x) => {
        const { y0, a, omega, phi } = params;
        return y0 + a * Math.cos(omega * x + phi);
      });

    case "damped_harmonic":
      return xValues.map((x) => {
        const { y0, a, k, omega, phi } = params;
        return y0 + Math.exp(k * x) * a * Math.cos(omega * x + phi);
      });

    default:
      return xValues.map(() => NaN);
  }
}

/** Names of the fit parameters for each model type. */
export const FIT_PARAM_NAMES: Record<string, string[]> = {
  lorentzian: ["y0", "a", "x0", "gamma"],
  gaussian: ["y0", "a", "x0", "sigma"],
  poly2: ["a", "b", "c"],
  harmonic: ["y0", "a", "omega", "phi"],
  damped_harmonic: ["y0", "a", "k", "omega", "phi"],
};

/** Available fit model types. */
export const FIT_TYPES = [
  "lorentzian",
  "gaussian",
  "poly2",
  "harmonic",
  "damped_harmonic",
] as const;

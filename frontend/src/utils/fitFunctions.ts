/** Names of the fit parameters for each model type. */
export const FIT_PARAM_NAMES: Record<string, string[]> = {
  lorentzian: ["y0", "a", "x0", "gamma"],
  gaussian: ["y0", "a", "x0", "sigma"],
  poly2: ["a", "b", "c"],
  harmonic: ["y0", "a", "omega", "phi"],
  damped_harmonic: ["y0", "a", "k", "omega", "phi"],
};

/** Default result parameter to use for "Update Parameter" per model. */
export const FIT_DEFAULT_UPDATE_PARAM: Record<string, string> = {
  lorentzian: "x0",
  gaussian: "x0",
  poly2: "vertex",
  harmonic: "f",
  damped_harmonic: "f",
};

/** Available fit model types. */
export const FIT_TYPES = [
  "lorentzian",
  "gaussian",
  "poly2",
  "harmonic",
  "damped_harmonic",
] as const;

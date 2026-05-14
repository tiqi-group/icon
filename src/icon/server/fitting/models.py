from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy as np
import numpy.typing as npt

if TYPE_CHECKING:
    from collections.abc import Callable

FitFunctionType = Literal[
    "gaussian",
    "lorentzian",
    "poly2",
    "harmonic",
    "damped_harmonic",
]

_MIN_FWHM_POINTS = 2


@dataclass(frozen=True)
class FitModel:
    """Definition of a curve-fitting model."""

    func: Callable[..., npt.NDArray[np.float64]]
    param_names: list[str]
    default_update_param: str
    guess: Callable[[npt.NDArray[np.float64], npt.NDArray[np.float64]], list[float]]
    derived_params: (
        Callable[[dict[str, float]], dict[str, float]] | None
    ) = None


def _lorentzian(
    x: npt.NDArray[np.float64],
    y0: float,
    a: float,
    x0: float,
    gamma: float,
) -> npt.NDArray[np.float64]:
    return np.asarray(y0 + a / (1.0 + ((x - x0) / gamma) ** 2))


def _lorentzian_guess(
    x: npt.NDArray[np.float64],
    y: npt.NDArray[np.float64],
) -> list[float]:
    n = len(y)
    n10 = max(1, n // 10)
    sorted_y = np.sort(y)
    baseline = float(np.median(np.concatenate([sorted_y[:n10], sorted_y[-n10:]])))

    peak_idx = int(np.argmax(np.abs(y - baseline)))
    a = float(y[peak_idx] - baseline)
    x0 = float(x[peak_idx])

    above = np.where(np.abs(y - baseline) >= np.abs(a) / 2.0)[0]
    if len(above) >= _MIN_FWHM_POINTS:
        gamma = float(abs(x[above[-1]] - x[above[0]])) / 2.0
    else:
        gamma = float(abs(x[-1] - x[0])) / 4.0

    gamma = max(gamma, 1e-12)
    return [baseline, a, x0, gamma]


def _gaussian(
    x: npt.NDArray[np.float64],
    y0: float,
    a: float,
    x0: float,
    sigma: float,
) -> npt.NDArray[np.float64]:
    return np.asarray(y0 + a * np.exp(-((x - x0) ** 2) / (2.0 * sigma**2)))


def _gaussian_guess(
    x: npt.NDArray[np.float64],
    y: npt.NDArray[np.float64],
) -> list[float]:
    n = len(y)
    n20 = max(1, n // 5)
    baseline = float(np.mean(np.sort(y)[:n20]))

    peak_idx = int(np.argmax(np.abs(y - baseline)))
    a = float(y[peak_idx] - baseline)
    x0 = float(x[peak_idx])

    half_max = np.abs(a) / 2.0
    above = np.where(np.abs(y - baseline) >= half_max)[0]
    if len(above) >= _MIN_FWHM_POINTS:
        fwhm = float(abs(x[above[-1]] - x[above[0]]))
        sigma = fwhm / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    else:
        sigma = float(abs(x[-1] - x[0])) / 10.0

    sigma = max(sigma, 1e-12)
    return [baseline, a, x0, sigma]


def _poly2(
    x: npt.NDArray[np.float64],
    a: float,
    b: float,
    c: float,
) -> npt.NDArray[np.float64]:
    return np.asarray(a * x**2 + b * x + c)


def _poly2_guess(
    x: npt.NDArray[np.float64],
    y: npt.NDArray[np.float64],
) -> list[float]:
    coeffs = np.polyfit(x, y, 2)
    return coeffs.tolist()


def _harmonic(
    x: npt.NDArray[np.float64],
    y0: float,
    a: float,
    omega: float,
    phi: float,
) -> npt.NDArray[np.float64]:
    return np.asarray(y0 + a * np.cos(omega * x + phi))


_MIN_FFT_POINTS = 3


def _harmonic_guess(
    x: npt.NDArray[np.float64],
    y: npt.NDArray[np.float64],
) -> list[float]:
    y0 = float(np.mean(y))
    a = float(np.max(y) - np.min(y)) / 2.0
    n = len(y)
    if n >= _MIN_FFT_POINTS:
        dx = float(np.mean(np.diff(x)))
        fft_vals = np.abs(np.fft.rfft(y - y0))
        fft_vals[0] = 0
        if len(fft_vals) > 1:
            peak_freq_idx = int(np.argmax(fft_vals))
            freq = peak_freq_idx / (n * dx) if dx > 0 else 1.0
            omega = 2.0 * np.pi * freq
        else:
            omega = 1.0
    else:
        omega = 1.0
    phi = 0.0
    return [y0, a, omega, phi]


def _damped_harmonic(  # noqa: PLR0913
    x: npt.NDArray[np.float64],
    y0: float,
    a: float,
    k: float,
    omega: float,
    phi: float,
) -> npt.NDArray[np.float64]:
    return np.asarray(y0 + np.exp(k * x) * a * np.cos(omega * x + phi))


def _damped_harmonic_guess(
    x: npt.NDArray[np.float64],
    y: npt.NDArray[np.float64],
) -> list[float]:
    hg = _harmonic_guess(x, y)
    return [hg[0], hg[1], 0.0, hg[2], hg[3]]


def _poly2_derived(result: dict[str, float]) -> dict[str, float]:
    a = result.get("a", 0)
    if a != 0:
        return {"vertex": -result["b"] / (2.0 * a)}
    return {}


def _harmonic_derived(result: dict[str, float]) -> dict[str, float]:
    if "omega" in result:
        return {"f": result["omega"] / (2.0 * np.pi)}
    return {}


# Adding a new fit model
# ----------------------
# 1. Define _my_model(x, p1, p2, ...) -> NDArray  (the model function).
# 2. Define _my_model_guess(x, y) -> list[float]  (initial parameter estimator).
# 3. (Optional) Define _my_model_derived(result) -> dict  if the model has
#    useful derived quantities (e.g. vertex from quadratic coefficients).
# 4. Add an entry to FIT_MODELS below. The param_names order must match the
#    function signature. default_update_param is the fitted value pre-filled
#    in the "Update Parameter" UI (can be a derived param name).
# 5. Add the model name to FIT_TYPES, FIT_PARAM_NAMES, and
#    FIT_DEFAULT_UPDATE_PARAM in frontend/src/utils/fitFunctions.ts.
# 6. Add tests in tests/server/fitting/.

FIT_MODELS: dict[str, FitModel] = {
    "lorentzian": FitModel(
        func=_lorentzian,
        param_names=["y0", "a", "x0", "gamma"],
        default_update_param="x0",
        guess=_lorentzian_guess,
    ),
    "gaussian": FitModel(
        func=_gaussian,
        param_names=["y0", "a", "x0", "sigma"],
        default_update_param="x0",
        guess=_gaussian_guess,
    ),
    "poly2": FitModel(
        func=_poly2,
        param_names=["a", "b", "c"],
        default_update_param="vertex",
        guess=_poly2_guess,
        derived_params=_poly2_derived,
    ),
    "harmonic": FitModel(
        func=_harmonic,
        param_names=["y0", "a", "omega", "phi"],
        default_update_param="f",
        guess=_harmonic_guess,
        derived_params=_harmonic_derived,
    ),
    "damped_harmonic": FitModel(
        func=_damped_harmonic,
        param_names=["y0", "a", "k", "omega", "phi"],
        default_update_param="f",
        guess=_damped_harmonic_guess,
        derived_params=_harmonic_derived,
    ),
}

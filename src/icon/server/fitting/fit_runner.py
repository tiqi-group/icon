from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from scipy.optimize import curve_fit  # type: ignore[import-untyped]

from icon.server.fitting.models import FIT_MODELS, FitFunctionType

logger = logging.getLogger(__name__)

_EXPECTED_RANGE_LEN = 2
_MAX_FIT_EVALS = 10000


@dataclass
class FitResult:
    """Result of a curve fit operation."""

    result_channel: str
    func_type: str
    x_range: list[float] | None
    init: dict[str, float]
    result: dict[str, float]
    goodness: dict[str, float]
    success: bool
    message: str


def _filter_valid(
    x: npt.NDArray[np.float64],
    y: npt.NDArray[np.float64],
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    mask = np.isfinite(x) & np.isfinite(y)
    return x[mask], y[mask]


def _compute_goodness(
    y: npt.NDArray[np.float64],
    y_fit: npt.NDArray[np.float64],
    n_params: int,
) -> dict[str, float]:
    n = len(y)
    ss_res = float(np.sum((y - y_fit) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))

    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    dof = n - n_params
    chi2_red = ss_res / dof if dof > 0 else float("inf")

    log_term = float(n * np.log(ss_res / n)) if ss_res > 0 and n > 0 else 0.0
    aic = log_term + 2.0 * n_params
    bic = log_term + n_params * float(np.log(n)) if n > 0 else 0.0

    return {"r2": r2, "chi2_red": chi2_red, "aic": aic, "bic": bic}


def _make_error(
    result_channel: str,
    func_type: str,
    x_range: list[float] | None,
    init: dict[str, float],
    message: str,
) -> FitResult:
    return FitResult(
        result_channel=result_channel,
        func_type=func_type,
        x_range=x_range,
        init=init,
        result={},
        goodness={},
        success=False,
        message=message,
    )


def _apply_range(
    x: npt.NDArray[np.float64],
    y: npt.NDArray[np.float64],
    x_range: list[float] | None,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    if x_range is not None and len(x_range) == _EXPECTED_RANGE_LEN:
        mask = (x >= x_range[0]) & (x <= x_range[1])
        return x[mask], y[mask]
    return x, y


def run_curve_fit(  # noqa: PLR0913, C901
    x: npt.NDArray[np.float64],
    y: npt.NDArray[np.float64],
    result_channel: str,
    func_type: FitFunctionType,
    x_range: list[float] | None = None,
    init: dict[str, float] | None = None,
) -> FitResult:
    """Run a curve fit on the given data."""
    if func_type not in FIT_MODELS:
        return _make_error(
            result_channel, func_type, x_range, init or {},
            f"Unknown fit function: {func_type}",
        )

    model = FIT_MODELS[func_type]
    x, y = _apply_range(x, y, x_range)
    x, y = _filter_valid(x, y)

    min_points = len(model.param_names) + 1
    if len(x) < min_points:
        return _make_error(
            result_channel, func_type, x_range, init or {},
            f"Insufficient data points: {len(x)} (need at least {min_points})",
        )

    # Build initial guess: merge user overrides on top of auto-guess
    p0 = list(model.guess(x, y))
    if init:
        for i, name in enumerate(model.param_names):
            if name in init:
                p0[i] = init[name]

    init_dict = dict(zip(model.param_names, p0))

    try:
        popt, _ = curve_fit(model.func, x, y, p0=p0, maxfev=_MAX_FIT_EVALS)
    except (RuntimeError, ValueError) as exc:
        return _make_error(
            result_channel, func_type, x_range, init_dict, str(exc),
        )

    result_dict = dict(zip(model.param_names, (float(v) for v in popt)))

    if func_type == "poly2" and result_dict.get("a", 0) != 0:
        result_dict["vertex"] = -result_dict["b"] / (2.0 * result_dict["a"])

    if func_type in ("harmonic", "damped_harmonic") and "omega" in result_dict:
        result_dict["f"] = result_dict["omega"] / (2.0 * np.pi)

    y_fit = model.func(x, *popt)
    goodness = _compute_goodness(y, y_fit, len(model.param_names))

    return FitResult(
        result_channel=result_channel,
        func_type=func_type,
        x_range=x_range,
        init=init_dict,
        result=result_dict,
        goodness=goodness,
        success=True,
        message="Fit converged",
    )

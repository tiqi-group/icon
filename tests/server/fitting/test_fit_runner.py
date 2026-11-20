import json

import numpy as np
import pytest

from icon.server.fitting.fit_runner import FitResult, run_curve_fit

# Minimum R^2 for a fit on clean synthetic data to be considered good.
MIN_GOOD_R2 = 0.99


def _synthetic_lorentzian(
    n: int = 100,
    noise: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    """Generate synthetic Lorentzian data."""
    true_params = {"y0": 1.0, "a": 5.0, "x0": 5.0, "gamma": 0.5}
    x = np.linspace(0, 10, n)
    y = true_params["y0"] + true_params["a"] / (
        1.0 + ((x - true_params["x0"]) / true_params["gamma"]) ** 2
    )
    if noise > 0:
        rng = np.random.default_rng(42)
        y = y + rng.normal(0, noise, n)
    return x, y, true_params


class TestRunCurveFit:
    def test_lorentzian_clean(self) -> None:
        x, y, true = _synthetic_lorentzian(noise=0.01)
        result = run_curve_fit(x, y, "ch1", "lorentzian")
        assert result.success
        assert result.result["x0"] == pytest.approx(true["x0"], abs=0.1)
        assert result.result["a"] == pytest.approx(true["a"], abs=0.5)
        assert result.goodness["r2"] > MIN_GOOD_R2

    def test_lorentzian_noisy(self) -> None:
        x, y, true = _synthetic_lorentzian(noise=0.5)
        result = run_curve_fit(x, y, "ch1", "lorentzian")
        assert result.success
        assert result.result["x0"] == pytest.approx(true["x0"], abs=1.0)

    def test_unknown_func_type(self) -> None:
        x = np.linspace(0, 10, 50)
        y = np.ones(50)
        result = run_curve_fit(x, y, "ch1", "nonexistent")  # type: ignore[arg-type]
        assert not result.success
        assert "Unknown" in result.message

    def test_insufficient_points(self) -> None:
        x = np.array([1.0, 2.0])
        y = np.array([1.0, 2.0])
        result = run_curve_fit(x, y, "ch1", "lorentzian")
        assert not result.success
        assert "Insufficient" in result.message

    def test_nan_data_filtered(self) -> None:
        x, y, _ = _synthetic_lorentzian(n=100, noise=0.01)
        y[10] = np.nan
        y[20] = np.inf
        x[30] = np.nan
        result = run_curve_fit(x, y, "ch1", "lorentzian")
        assert result.success

    def test_x_range_filter(self) -> None:
        x, y, true = _synthetic_lorentzian(n=200, noise=0.01)
        result = run_curve_fit(x, y, "ch1", "lorentzian", x_range=[3.0, 7.0])
        assert result.success
        assert result.result["x0"] == pytest.approx(true["x0"], abs=0.2)

    def test_init_override(self) -> None:
        x, y, true = _synthetic_lorentzian(noise=0.01)
        result = run_curve_fit(x, y, "ch1", "lorentzian", init={"x0": 4.9})
        assert result.success
        assert result.result["x0"] == pytest.approx(true["x0"], abs=0.2)

    def test_w_shape_with_init(self) -> None:
        """Two Lorentzian dips; init selects correct peak."""
        x = np.linspace(0, 20, 200)
        y = (
            10.0
            - 5.0 / (1 + ((x - 5.0) / 0.5) ** 2)
            - 5.0 / (1 + ((x - 15.0) / 0.5) ** 2)
        )
        # Guide to the second peak
        result = run_curve_fit(x, y, "ch1", "lorentzian", init={"x0": 15.0})
        assert result.success
        assert result.result["x0"] == pytest.approx(15.0, abs=1.0)

    def test_gaussian_fit(self) -> None:
        x = np.linspace(-5, 5, 100)
        y = 2.0 + 3.0 * np.exp(-((x - 1.0) ** 2) / (2.0 * 0.5**2))
        rng = np.random.default_rng(42)
        y += rng.normal(0, 0.05, len(y))
        result = run_curve_fit(x, y, "ch1", "gaussian")
        assert result.success
        assert result.result["x0"] == pytest.approx(1.0, abs=0.3)

    def test_poly2_fit(self) -> None:
        x = np.linspace(-5, 5, 50)
        y = 2.0 * x**2 - 3.0 * x + 1.0
        result = run_curve_fit(x, y, "ch1", "poly2")
        assert result.success
        assert result.result["a"] == pytest.approx(2.0, abs=0.1)
        assert "vertex" in result.result

    def test_fit_result_fields(self) -> None:
        x, y, _ = _synthetic_lorentzian(noise=0.01)
        result = run_curve_fit(x, y, "ch1", "lorentzian")
        assert isinstance(result, FitResult)
        assert result.func_type == "lorentzian"
        assert result.result_channel == "ch1"
        assert "r2" in result.goodness
        assert "chi2_red" in result.goodness
        assert "aic" in result.goodness
        assert "bic" in result.goodness


class TestFitErrors:
    def test_errors_for_all_parameters(self) -> None:
        x = np.linspace(-5, 5, 50)
        rng = np.random.default_rng(0)
        y = 2.0 * x**2 - 3.0 * x + 1.0 + rng.normal(0, 0.5, x.size)
        result = run_curve_fit(x, y, "ch1", "poly2")
        assert set(result.errors) == set(result.result)
        assert all(np.isfinite(e) and e > 0 for e in result.errors.values())

    def test_errors_match_scatter_of_repeated_fits(self) -> None:
        # Rabi flop sampled over ~2.6 periods; first max at 1 / (2 f)
        f_true, noise = 0.13, 0.05
        x = np.linspace(0, 20, 41)
        init = {"y0": 0.5, "a": -0.45, "omega": 2 * np.pi * f_true, "phi": 0.0}
        rng = np.random.default_rng(1)
        fits = []
        for _ in range(200):
            y = 0.5 - 0.45 * np.cos(2 * np.pi * f_true * x)
            y = y + rng.normal(0, noise, x.size)
            fits.append(run_curve_fit(x, y, "ch1", "harmonic", init=init))
        for name in ("f", "x_first_max"):
            values = np.array([fit.result[name] for fit in fits])
            predicted = np.mean([fit.errors[name] for fit in fits])
            assert np.std(values) == pytest.approx(predicted, rel=0.2)
        first_max = np.mean([fit.result["x_first_max"] for fit in fits])
        assert first_max == pytest.approx(1 / (2 * f_true), abs=0.02)

    def test_errors_left_out_when_covariance_cannot_be_estimated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def singular_fit(*_: object, **__: object) -> tuple[np.ndarray, np.ndarray]:
            return np.array([2.0, -3.0, 1.0]), np.full((3, 3), np.inf)

        monkeypatch.setattr("icon.server.fitting.fit_runner.curve_fit", singular_fit)
        x = np.linspace(-5, 5, 10)
        result = run_curve_fit(x, x**2, "ch1", "poly2")
        assert result.success
        assert result.errors == {}

    def test_fit_stored_before_errors_existed_loads(self) -> None:
        # As written to the HDF5 file before FitResult had errors
        stored = (
            '{"result_channel": "ch1", "func_type": "poly2", "x_range": null,'
            ' "init": {}, "result": {"a": 1.0}, "goodness": {}, "success": true,'
            ' "message": "Fit converged", "fit_curve": null}'
        )
        assert FitResult(**json.loads(stored)).errors == {}

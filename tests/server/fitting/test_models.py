import numpy as np
import pytest

from icon.server.fitting.models import FIT_MODELS


class TestLorentzianFunction:
    def test_peak_at_x0(self) -> None:
        model = FIT_MODELS["lorentzian"]
        x = np.array([5.0])
        result = model.func(x, 0.0, 10.0, 5.0, 1.0)
        assert result[0] == pytest.approx(10.0)

    def test_baseline(self) -> None:
        model = FIT_MODELS["lorentzian"]
        x = np.array([1e6])
        result = model.func(x, 3.0, 10.0, 0.0, 1.0)
        assert result[0] == pytest.approx(3.0, abs=0.01)

    def test_symmetry(self) -> None:
        model = FIT_MODELS["lorentzian"]
        x0 = 5.0
        left = model.func(np.array([x0 - 2.0]), 0.0, 1.0, x0, 1.0)
        right = model.func(np.array([x0 + 2.0]), 0.0, 1.0, x0, 1.0)
        assert left[0] == pytest.approx(right[0])


class TestLorentzianGuess:
    def test_reasonable_peak_guess(self) -> None:
        model = FIT_MODELS["lorentzian"]
        x = np.linspace(0, 10, 100)
        y0, a, x0, gamma = 1.0, 5.0, 5.0, 0.5
        y = y0 + a / (1.0 + ((x - x0) / gamma) ** 2)
        guess = model.guess(x, y)
        # x0 guess should be near the peak
        assert abs(guess[2] - x0) < 1.0

    def test_dip_guess(self) -> None:
        model = FIT_MODELS["lorentzian"]
        x = np.linspace(0, 10, 100)
        y = 10.0 - 5.0 / (1.0 + ((x - 5.0) / 0.5) ** 2)
        guess = model.guess(x, y)
        # A should be negative for a dip
        assert guess[1] < 0


class TestGaussianFunction:
    def test_peak_at_x0(self) -> None:
        model = FIT_MODELS["gaussian"]
        x = np.array([3.0])
        result = model.func(x, 0.0, 5.0, 3.0, 1.0)
        assert result[0] == pytest.approx(5.0)


class TestPoly2Function:
    def test_known_values(self) -> None:
        model = FIT_MODELS["poly2"]
        x = np.array([0.0, 1.0, 2.0])
        result = model.func(x, 1.0, 2.0, 3.0)
        np.testing.assert_array_almost_equal(result, [3.0, 6.0, 11.0])

    def test_guess(self) -> None:
        model = FIT_MODELS["poly2"]
        x = np.linspace(-5, 5, 50)
        y = 2.0 * x**2 - 3.0 * x + 1.0
        guess = model.guess(x, y)
        assert guess[0] == pytest.approx(2.0, abs=0.1)


class TestHarmonicFunction:
    def test_at_zero_phase(self) -> None:
        model = FIT_MODELS["harmonic"]
        x = np.array([0.0])
        result = model.func(x, 1.0, 2.0, np.pi, 0.0)
        assert result[0] == pytest.approx(3.0)


class TestDampedHarmonicFunction:
    def test_no_damping_matches_harmonic(self) -> None:
        x = np.linspace(0, 10, 50)
        harmonic = FIT_MODELS["harmonic"].func(x, 1.0, 2.0, 3.0, 0.5)
        damped = FIT_MODELS["damped_harmonic"].func(x, 1.0, 2.0, 0.0, 3.0, 0.5)
        np.testing.assert_array_almost_equal(harmonic, damped)


def _brute_force_first_extrema(
    func_type: str, popt: list[float], x_start: float
) -> tuple[float, float]:
    """First interior local maximum and minimum after x_start, on a fine grid."""
    xx = np.linspace(x_start, x_start + 50, 2_000_001)
    yy = FIT_MODELS[func_type].func(xx, *popt)
    d = np.diff(yy)
    x_mid = xx[1:-1]
    first_max = x_mid[(d[:-1] > 0) & (d[1:] <= 0)][0]
    first_min = x_mid[(d[:-1] < 0) & (d[1:] >= 0)][0]
    return float(first_max), float(first_min)


class TestOscillationExtrema:
    @pytest.mark.parametrize(
        "popt",
        [
            [0.5, 0.45, 0.8, 1.0],
            [0.5, -0.45, 0.8, 1.0],
            [0.5, 0.45, -0.8, -1.0],
            [0.5, -0.45, -0.8, 2.5],
            [0.5, 0.45, 0.8, -7.0],
        ],
    )
    def test_harmonic_matches_brute_force(self, popt: list[float]) -> None:
        x = np.linspace(0.3, 20, 30)
        values, _ = FIT_MODELS["harmonic"].derived_params(  # type: ignore[misc]
            np.array(popt), np.zeros((4, 4)), x
        )
        first_max, first_min = _brute_force_first_extrema("harmonic", popt, 0.3)
        assert values["x_first_max"] == pytest.approx(first_max, abs=1e-4)
        assert values["x_first_min"] == pytest.approx(first_min, abs=1e-4)

    @pytest.mark.parametrize(
        "popt",
        [
            [0.5, 0.45, -0.3, 0.8, 1.0],
            [0.5, -0.45, -0.1, 0.8, 1.0],
            [0.5, 0.45, 0.2, -0.8, -1.0],
        ],
    )
    def test_damped_harmonic_matches_brute_force(self, popt: list[float]) -> None:
        x = np.linspace(0.0, 20, 30)
        values, _ = FIT_MODELS["damped_harmonic"].derived_params(  # type: ignore[misc]
            np.array(popt), np.zeros((5, 5)), x
        )
        first_max, first_min = _brute_force_first_extrema("damped_harmonic", popt, 0.0)
        assert values["x_first_max"] == pytest.approx(first_max, abs=1e-4)
        assert values["x_first_min"] == pytest.approx(first_min, abs=1e-4)

    def test_extremum_just_before_scan_start_within_errors_counts(self) -> None:
        # Minimum at x = -0.01, the scan starts at 0, error of x ~ 0.05
        popt = np.array([0.5, 0.45, 2 * np.pi / 7.7, np.pi + 0.01 * 2 * np.pi / 7.7])
        pcov = np.diag([0.0, 0.0, 0.0, 0.05**2 * popt[2] ** 2])
        values, errors = FIT_MODELS["harmonic"].derived_params(  # type: ignore[misc]
            popt, pcov, np.linspace(0, 20, 41)
        )
        assert values["x_first_min"] == pytest.approx(-0.01, abs=1e-9)
        assert errors["x_first_min"] == pytest.approx(0.05)

    def test_extremum_well_before_scan_start_is_skipped(self) -> None:
        popt = np.array([0.5, 0.45, 2 * np.pi / 7.7, np.pi + 1.0 * 2 * np.pi / 7.7])
        pcov = np.diag([0.0, 0.0, 0.0, 0.05**2 * popt[2] ** 2])
        values, _ = FIT_MODELS["harmonic"].derived_params(  # type: ignore[misc]
            popt, pcov, np.linspace(0, 20, 41)
        )
        assert values["x_first_min"] == pytest.approx(7.7 - 1.0)


class TestDerivedErrors:
    def test_poly2_vertex_error(self) -> None:
        # vertex = -b / (2a); with only b uncertain, sigma_vertex = sigma_b / (2|a|)
        values, errors = FIT_MODELS["poly2"].derived_params(  # type: ignore[misc]
            np.array([2.0, -3.0, 1.0]), np.diag([0.0, 0.1**2, 0.0]), np.array([0.0])
        )
        assert values["vertex"] == pytest.approx(0.75)
        assert errors["vertex"] == pytest.approx(0.1 / 4)

    def test_frequency_error(self) -> None:
        values, errors = FIT_MODELS["harmonic"].derived_params(  # type: ignore[misc]
            np.array([0.0, 1.0, 2.0, 0.0]),
            np.diag([0.0, 0.0, 0.3**2, 0.0]),
            np.array([0.0, 1.0]),
        )
        assert values["f"] == pytest.approx(2.0 / (2 * np.pi))
        assert errors["f"] == pytest.approx(0.3 / (2 * np.pi))

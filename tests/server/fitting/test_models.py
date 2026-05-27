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

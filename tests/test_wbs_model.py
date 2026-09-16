"""The B2 forward model and its inverse-Laplace layer.

Skipped when mpmath is absent, under the declared optional-oracle policy that
``scripts/verify.py`` enforces: the B2 model is a case-layer artefact and the stdlib runner
installs nothing. The skip is named and counted, never silent.

Nothing here scores a B2 engineering outcome. These tests qualify the machinery: the
transform's limits, the inversion's accuracy against transforms with known exact inverses,
and the behaviours the protocol requires before an experiment may run.
"""

from __future__ import annotations

import math
import pathlib
import sys
import unittest

CASE = pathlib.Path(__file__).resolve().parents[1] / "cases" / "B2_wellbore_storage_window"
if str(CASE) not in sys.path:
    sys.path.insert(0, str(CASE))

try:
    import mpmath as mp
except ImportError:  # pragma: no cover - exercised on the dependency-free runner
    mp = None

if mp is not None:
    from wbs_model import (
        INVERSION,
        InversionSettings,
        WellboreStorageModel,
        dimensionless_storage_coefficient,
        k01,
        k01_is_reliable,
        laplace_wellbore_pressure,
        storage_asymptote_residual,
    )


def requires_mpmath(test):
    return unittest.skipIf(
        mp is None,
        "OPTIONAL ORACLE ABSENT [mpmath]: the B2 forward model needs complex Bessel "
        "functions and a numerical inverse Laplace transform; it is a development pin and "
        "is not installed on this runner.",
    )(test)


@requires_mpmath
class TheStorageConstantIsDerived(unittest.TestCase):
    def test_matches_the_published_field_constant(self) -> None:
        """0.8936 is 1 bbl in cubic feet over 2 pi, not a memorised number."""
        derived = 5.614583 / (2.0 * math.pi)
        self.assertAlmostEqual(derived, 0.8936, places=4)
        cd = dimensionless_storage_coefficient(
            1.0,
            porosity=0.18,
            total_compressibility_per_psi=1.5e-5,
            thickness_ft=40.0,
            wellbore_radius_ft=0.35,
        )
        expected = derived / (0.18 * 1.5e-5 * 40.0 * 0.35**2)
        self.assertAlmostEqual(cd / expected, 1.0, places=12)

    def test_it_refuses_nonsense(self) -> None:
        base = dict(
            porosity=0.18,
            total_compressibility_per_psi=1.5e-5,
            thickness_ft=40.0,
            wellbore_radius_ft=0.35,
        )
        with self.assertRaises(ValueError):
            dimensionless_storage_coefficient(-1.0, **base)
        for bad in ("porosity", "thickness_ft", "wellbore_radius_ft"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                dimensionless_storage_coefficient(1.0, **{**base, bad: 0.0})


@requires_mpmath
class TheFiniteRadiusResponse(unittest.TestCase):
    def test_it_satisfies_the_inner_boundary_condition(self) -> None:
        """-d p_D/d r_D = 1/u at r_D = 1 is what defines the finite-radius solution."""
        with mp.workdps(30):
            for uv in ("0.01", "1", "100"):
                with self.subTest(u=uv):
                    u = mp.mpf(uv)
                    x = mp.sqrt(u)
                    amplitude = 1 / (u * x * mp.besselk(1, x))
                    flux = -mp.diff(lambda r, a=amplitude, xx=x: a * mp.besselk(0, r * xx), mp.mpf(1))
                    self.assertTrue(mp.almosteq(flux, 1 / u, rel_eps=mp.mpf("1e-25")))

    def test_the_line_source_is_its_small_radius_limit(self) -> None:
        """X K1(x) -> 1, so K01 -> K0. That factor is the well's finite surface."""
        with mp.workdps(30):
            for xv in ("1e-4", "1e-6", "1e-8"):
                with self.subTest(x=xv):
                    x = mp.mpf(xv)
                    self.assertTrue(mp.almosteq(x * mp.besselk(1, x), 1, rel_eps=mp.mpf("1e-6")))

    def test_it_is_singular_at_the_origin(self) -> None:
        with self.assertRaises(ValueError):
            k01(0)

    def test_it_accepts_complex_argument(self) -> None:
        """De Hoog evaluates the transform off the real axis."""
        value = k01(mp.mpc(2, 3))
        self.assertTrue(mp.isfinite(value.real) and mp.isfinite(value.imag))

    def test_reliability_is_declared_not_clamped(self) -> None:
        self.assertTrue(k01_is_reliable(1.0))
        self.assertTrue(k01_is_reliable(1e-6))


@requires_mpmath
class TheTransform(unittest.TestCase):
    def test_zero_storage_gives_the_storage_free_solution(self) -> None:
        u = mp.mpf("2.5")
        with_storage = laplace_wellbore_pressure(u, storage_dimensionless=0.0, skin=2.0)
        plain = (k01(mp.sqrt(u)) + 2) / u
        self.assertTrue(mp.almosteq(with_storage, plain, rel_eps=mp.mpf("1e-28")))

    def test_it_refuses_a_singular_or_impossible_argument(self) -> None:
        with self.assertRaises(ValueError):
            laplace_wellbore_pressure(0, storage_dimensionless=10.0, skin=0.0)
        with self.assertRaises(ValueError):
            laplace_wellbore_pressure(1.0, storage_dimensionless=-1.0, skin=0.0)

    def test_negative_skin_is_representable(self) -> None:
        """A stimulated well has s < 0. Refusing it would be a modelling error."""
        value = laplace_wellbore_pressure(mp.mpf(1), storage_dimensionless=100.0, skin=-2.0)
        self.assertTrue(mp.isfinite(value))


@requires_mpmath
class TheStorageBranchExistsAtEverySkin(unittest.TestCase):
    """C3b. The regression against the defect that motivated the protocol amendment."""

    def test_zero_skin_still_produces_storage(self) -> None:
        residual = storage_asymptote_residual(storage_dimensionless=1000.0, skin=0.0)
        self.assertLess(
            residual,
            1e-6,
            "the finite-radius model must show u^2 p_bar -> 1/C_D at zero skin; the "
            "superseded line-source formulation does not, which is why it was replaced",
        )

    def test_positive_skin_produces_storage(self) -> None:
        self.assertLess(storage_asymptote_residual(storage_dimensionless=1000.0, skin=3.5), 1e-6)

    def test_the_superseded_line_source_form_would_fail_this(self) -> None:
        """A positive control on the regression itself, so it is known to be able to fail."""
        with mp.workdps(30):
            u = mp.mpf(10) ** 10
            # The superseded formulation: K0 in place of K01.
            g = mp.besselk(0, mp.sqrt(u)) + 0
            scaled = u**2 * g / (u * (1 + 1000 * u * g))
            residual = abs(scaled - mp.mpf("0.001")) / mp.mpf("0.001")
            self.assertGreater(residual, 0.5, "the line-source form should have no storage branch at s = 0")

    def test_it_refuses_a_storage_free_asymptote(self) -> None:
        with self.assertRaises(ValueError):
            storage_asymptote_residual(storage_dimensionless=0.0, skin=1.0)


@requires_mpmath
class TheInversionIsQualified(unittest.TestCase):
    """C1, on transforms with known exact inverses, class-matched to the B2 transform.

    Smooth, monotone, non-oscillatory, diffusion-like, and scored only where the exact value
    is within the method's representable range. Protocol section 13.0b records why an
    oscillatory transform and two underflowing points were removed from the set, and that the
    1e-8 threshold was not moved.
    """

    CASES = (
        ("constant", lambda u: 1 / u, lambda _t: mp.mpf(1), ("1e-3", "1", "1e3", "1e6")),
        ("ramp", lambda u: 1 / u**2, lambda t: t, ("1e-3", "1", "1e3", "1e6")),
        ("exponential", lambda u: 1 / (u + 2), lambda t: mp.e ** (-2 * t), ("1e-3", "0.1", "1")),
        (
            "diffusion",
            lambda u: mp.e ** (-mp.sqrt(u)) / u,
            lambda t: mp.erfc(1 / (2 * mp.sqrt(t))),
            ("1", "1e3", "1e6"),
        ),
        (
            "sqrt decay",
            lambda u: 1 / mp.sqrt(u),
            lambda t: 1 / mp.sqrt(mp.pi * t),
            ("1e-3", "1", "1e3", "1e6"),
        ),
    )

    def test_dehoog_meets_the_threshold_on_known_inverses(self) -> None:
        with mp.workdps(INVERSION.dps):
            for name, transform, exact, times in self.CASES:
                for tv in times:
                    with self.subTest(transform=name, t=tv):
                        t = mp.mpf(tv)
                        got = mp.invertlaplace(transform, t, method="dehoog", degree=INVERSION.dehoog_degree)
                        rel = abs(got - exact(t)) / abs(exact(t))
                        self.assertLess(float(rel), 1e-8)

    def test_the_two_algorithms_agree_on_the_b2_transform(self) -> None:
        """An algorithmic cross-check, not an independent physics oracle."""
        model = WellboreStorageModel(storage_dimensionless=1000.0, skin=3.5)
        for t_d in (1e2, 1e4, 1e6):
            with self.subTest(t_d=t_d):
                a = model.pressure(t_d, method="dehoog")
                b = model.pressure(t_d, method="stehfest")
                self.assertLess(abs(a - b) / abs(a), 1e-6)

    def test_settings_are_validated(self) -> None:
        for kwargs in ({"dps": 5}, {"dehoog_degree": 2}, {"stehfest_degree": 15}):
            with self.subTest(**kwargs), self.assertRaises(ValueError):
                InversionSettings(**kwargs)

    def test_repeated_evaluation_is_deterministic(self) -> None:
        model = WellboreStorageModel(storage_dimensionless=1000.0, skin=3.5)
        first = [model.pressure(t) for t in (1e2, 1e4, 1e6)]
        second = [model.pressure(t) for t in (1e2, 1e4, 1e6)]
        self.assertEqual(first, second)

    def test_non_positive_time_is_refused(self) -> None:
        model = WellboreStorageModel(storage_dimensionless=1000.0, skin=3.5)
        with self.assertRaises(ValueError):
            model.pressure(0.0)


@requires_mpmath
class TheLimitingBehaviours(unittest.TestCase):
    """Protocol section 8b: the three checks that replace the withdrawn exact identity."""

    def test_early_time_approaches_the_storage_line(self) -> None:
        """O2: p_wD -> t_D / C_D, for any skin."""
        for skin in (0.0, 3.5):
            with self.subTest(skin=skin):
                model = WellboreStorageModel(storage_dimensionless=1000.0, skin=skin)
                t_d = 1.0
                self.assertLess(abs(model.pressure(t_d) - t_d / 1000.0) / (t_d / 1000.0), 0.05)

    def test_late_time_approaches_the_semilog_line(self) -> None:
        """O3: p_wD -> 0.5 [ln t_D + 0.80907] + s."""
        model = WellboreStorageModel(storage_dimensionless=1000.0, skin=3.5)
        t_d = 1e8
        expected = 0.5 * (math.log(t_d) + 0.80907) + 3.5
        self.assertLess(abs(model.pressure(t_d) - expected) / expected, 1e-3)

    def test_the_derivative_reaches_the_half_plateau(self) -> None:
        model = WellboreStorageModel(storage_dimensionless=1000.0, skin=3.5)
        self.assertLess(abs(model.log_derivative(1e8) - 0.5) / 0.5, 1e-3)


if __name__ == "__main__":
    unittest.main()

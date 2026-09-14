"""Tests for the line-source transient solution and its semilog interpretation.

Written to attack the implementation rather than to exercise it. Well-test arithmetic has
a small number of famous traps -- a log base, a radius that should be a diameter, a
constant transcribed from a table, a derivative placed on the wrong abscissa, a straight
line fitted where the straight line does not exist -- and each one produces a plausible
number rather than an exception. Several tests below therefore check that a deliberately
wrong variant would *fail*, because a test that both the right and the wrong code pass
is not testing anything.

The oracles are declared in ``docs/evidence/pta_line_source.md``. Each is bounded to the
range where it is defensible, and the bounds are asserted here too: an oracle used
outside its range is worse than no oracle, because it is convincing.
"""

from __future__ import annotations

import math
import unittest
from decimal import Decimal, getcontext

from reservoir_lab.errors import InvalidInputError
from reservoir_lab.transient import (
    EULER_MASCHERONI,
    LINE_SOURCE_CONSTANT,
    PRESSURE_FIELD_FACTOR,
    TIME_FIELD_FACTOR,
    derivative_plateau_constant,
    dimensionless_pressure,
    dimensionless_time,
    exponential_integral_e1,
    line_source_dimensionless_pressure,
    line_source_log_derivative,
    permeability_from_semilog_slope,
    pressure_drop_psi,
    semilog_interpretation,
    semilog_skin_constant,
    semilog_slope_constant,
    skin_from_semilog_line,
)

# The declared B1 truth, repeated here so the tests do not import the case module.
K, H, PHI, MU, CT, RW, B, Q, PI, S = (
    50.0,
    40.0,
    0.18,
    1.2,
    1.5e-5,
    0.35,
    1.25,
    350.0,
    4000.0,
    3.5,
)
LN10 = math.log(10.0)


def t_d(hours: float) -> float:
    """Dimensionless time at the declared B1 properties."""
    return dimensionless_time(
        hours,
        permeability_md=K,
        porosity=PHI,
        viscosity_cp=MU,
        total_compressibility_per_psi=CT,
        wellbore_radius_ft=RW,
    )


def drawdown(hours: float, skin: float = S) -> float:
    """Field-unit drawdown of the declared B1 response."""
    p_d = line_source_dimensionless_pressure(t_d(hours), skin=skin)
    return pressure_drop_psi(
        p_d,
        permeability_md=K,
        thickness_ft=H,
        rate_stb_per_day=Q,
        formation_volume_factor=B,
        viscosity_cp=MU,
    )


def e1_decimal(x: float, digits: int = 40) -> float:
    """Oracle O1: E1 by arbitrary-precision alternating series.

    Declared valid for ``x <= 2`` only. The series loses roughly ``x/ln 10`` digits to
    cancellation, so beyond that the answer is confidently wrong unless the working
    precision is raised to match. The bound is asserted by a test rather than trusted.
    """
    if x > 2.0:
        raise AssertionError("oracle O1 is declared valid only for x <= 2")
    getcontext().prec = digits + 25
    value = Decimal(repr(x))
    gamma = Decimal("0.5772156649015328606065120900824024310421593359399235988057672348849")
    total = Decimal(0)
    term = Decimal(1)
    for n in range(1, 400):
        term *= -value / n
        total += -term / n
        if abs(term / n) < Decimal(10) ** (-(digits + 15)):
            break
    return float(-gamma - value.ln() + total)


def e1_asymptotic(x: float, terms: int = 12) -> float:
    """Oracle O2: asymptotic expansion, declared valid for ``x >= 20``."""
    if x < 20.0:
        raise AssertionError("oracle O2 is declared valid only for x >= 20")
    total = 1.0
    term = 1.0
    for k in range(1, terms):
        term *= -k / x
        if abs(term) > abs(total):
            break
        total += term
    return math.exp(-x) / x * total


class DerivedConstantTests(unittest.TestCase):
    """Every published field constant must be reproducible, not transcribed."""

    def test_line_source_constant(self) -> None:
        """The constant ln 4 - gamma is 0.8090787..., which the literature prints as 0.80907.

        That published form is a truncation, not a rounding: to five decimal places the
        true value rounds to 0.80908. The difference is 8.7e-06 and is invisible in any
        result, but the test says so rather than loosening a tolerance until it passes,
        because a constant that disagrees with its published form by an unexplained
        amount is exactly the kind of thing worth noticing.
        """
        self.assertAlmostEqual(LINE_SOURCE_CONSTANT, math.log(4.0) - EULER_MASCHERONI, places=15)
        self.assertLess(abs(LINE_SOURCE_CONSTANT - 0.80907), 1e-5)
        self.assertEqual(f"{LINE_SOURCE_CONSTANT:.5f}", "0.80908")

    def test_semilog_slope_constant(self) -> None:
        self.assertAlmostEqual(semilog_slope_constant(), 162.6, places=1)
        self.assertAlmostEqual(semilog_slope_constant(), PRESSURE_FIELD_FACTOR * LN10 / 2.0, places=12)

    def test_derivative_plateau_constant(self) -> None:
        self.assertAlmostEqual(derivative_plateau_constant(), 70.6, places=4)

    def test_the_two_plateau_routes_agree(self) -> None:
        """70.6 is both 141.2/2 and 162.6/ln10; if they disagree a log base is wrong."""
        self.assertAlmostEqual(derivative_plateau_constant(), semilog_slope_constant() / LN10, places=12)

    def test_skin_constant(self) -> None:
        self.assertAlmostEqual(semilog_skin_constant(), 3.2275, places=4)

    def test_a_natural_log_slip_would_be_caught(self) -> None:
        """The commonest constant error is ln where log10 belongs, or the reverse."""
        wrong = PRESSURE_FIELD_FACTOR / 2.0  # forgetting the ln(10)
        self.assertNotAlmostEqual(wrong, 162.6, places=1)
        self.assertGreater(abs(wrong - semilog_slope_constant()) / semilog_slope_constant(), 0.5)


class ExponentialIntegralTests(unittest.TestCase):
    """The special function, against two bounded oracles and its own limits."""

    def test_small_argument_against_arbitrary_precision(self) -> None:
        for x in (1e-8, 1e-5, 1e-3, 0.01, 0.1, 0.5, 0.9, 1.0, 1.5, 2.0):
            with self.subTest(x=x):
                got, want = exponential_integral_e1(x), e1_decimal(x)
                self.assertLessEqual(abs(got - want) / abs(want), 1e-12)

    def test_large_argument_against_the_asymptotic_oracle(self) -> None:
        for x in (20.0, 50.0, 100.0, 300.0):
            with self.subTest(x=x):
                got, want = exponential_integral_e1(x), e1_asymptotic(x)
                self.assertLessEqual(abs(got - want) / abs(want), 1e-6)

    def test_the_two_branches_agree_across_the_switch(self) -> None:
        """A discontinuity at the branch point would be invisible in either branch alone."""
        below = exponential_integral_e1(1.0 - 1e-12)
        above = exponential_integral_e1(1.0 + 1e-12)
        self.assertLessEqual(abs(below - above) / abs(below), 1e-10)

    def test_small_argument_logarithmic_limit(self) -> None:
        """As x -> 0, E1(x) -> -gamma - ln x. Independent of both branches."""
        for x in (1e-10, 1e-12, 1e-14):
            with self.subTest(x=x):
                limit = -EULER_MASCHERONI - math.log(x)
                self.assertLessEqual(abs(exponential_integral_e1(x) - limit), 1e-9)

    def test_monotone_decreasing(self) -> None:
        values = [exponential_integral_e1(x) for x in (0.01, 0.1, 1.0, 2.0, 5.0, 20.0)]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_rejects_non_positive_and_non_finite(self) -> None:
        for bad in (0.0, -1.0, float("nan"), float("inf")):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                exponential_integral_e1(bad)

    def test_oracle_o1_refuses_to_be_used_out_of_range(self) -> None:
        with self.assertRaises(AssertionError):
            e1_decimal(50.0)

    def test_oracle_o2_refuses_to_be_used_out_of_range(self) -> None:
        with self.assertRaises(AssertionError):
            e1_asymptotic(1.0)


class MpmathCrossCheckTests(unittest.TestCase):
    """A fourth implementation by other authors, used only if it happens to be present."""

    def test_against_mpmath_if_available(self) -> None:
        try:
            import mpmath
        except ImportError:
            self.skipTest("mpmath is not installed; it is not a dependency of this project")
        mpmath.mp.dps = 40
        for x in (1e-8, 1e-3, 0.1, 1.0, 3.0, 10.0, 100.0):
            with self.subTest(x=x):
                want = float(mpmath.e1(mpmath.mpf(repr(x))))
                self.assertLessEqual(abs(exponential_integral_e1(x) - want) / abs(want), 1e-13)


class LineSourceTests(unittest.TestCase):
    """The forward solution, its limits and its refusals."""

    def test_semilog_limit_at_large_dimensionless_time(self) -> None:
        """p_D -> (1/2)[ln t_D + 0.80907]; the approach is the 1/(4 t_D) term."""
        for t in (1e4, 1e5, 1e6):
            with self.subTest(t_d=t):
                exact = line_source_dimensionless_pressure(t)
                approx = 0.5 * (math.log(t) + LINE_SOURCE_CONSTANT)
                self.assertLessEqual(abs(approx - exact), 0.5 / (4.0 * t) * 1.01)

    def test_skin_is_a_pure_offset(self) -> None:
        for t in (1e3, 1e5):
            base = line_source_dimensionless_pressure(t)
            for skin in (-2.0, 0.0, 3.5, 10.0):
                with self.subTest(t_d=t, skin=skin):
                    self.assertAlmostEqual(
                        line_source_dimensionless_pressure(t, skin=skin), base + skin, places=12
                    )

    def test_negative_skin_is_allowed_and_lowers_the_drawdown(self) -> None:
        """A stimulated well has s < 0. Refusing it would be a modelling error."""
        self.assertLess(
            line_source_dimensionless_pressure(1e5, skin=-2.0),
            line_source_dimensionless_pressure(1e5, skin=0.0),
        )

    def test_skin_away_from_the_wellbore_is_refused(self) -> None:
        with self.assertRaises(InvalidInputError):
            line_source_dimensionless_pressure(1e5, dimensionless_radius=10.0, skin=1.0)

    def test_pressure_rises_monotonically_with_time(self) -> None:
        values = [line_source_dimensionless_pressure(t) for t in (10, 1e2, 1e3, 1e4, 1e5)]
        self.assertEqual(values, sorted(values))

    def test_response_falls_with_radius(self) -> None:
        near = line_source_dimensionless_pressure(1e5, dimensionless_radius=1.0)
        far = line_source_dimensionless_pressure(1e5, dimensionless_radius=100.0)
        self.assertLess(far, near)

    def test_rejects_non_positive_time_and_radius(self) -> None:
        for bad in (0.0, -1.0):
            with self.subTest(bad=bad):
                with self.assertRaises(InvalidInputError):
                    line_source_dimensionless_pressure(bad)
                with self.assertRaises(InvalidInputError):
                    line_source_dimensionless_pressure(1e5, dimensionless_radius=bad)


class LogDerivativeTests(unittest.TestCase):
    """The closed-form derivative, oracle O3."""

    def test_against_a_central_difference_of_the_forward_solution(self) -> None:
        for t in (1.0, 10.0, 1e3, 1e5):
            with self.subTest(t_d=t):
                h = 1e-6
                numeric = (
                    line_source_dimensionless_pressure(t * math.exp(h))
                    - line_source_dimensionless_pressure(t * math.exp(-h))
                ) / (2.0 * h)
                self.assertLessEqual(
                    abs(numeric - line_source_log_derivative(t)) / line_source_log_derivative(t),
                    1e-8,
                )

    def test_approaches_one_half_from_below_with_the_known_deficit(self) -> None:
        """The deficit is 1/(8 t_D). Testing against 1/2 alone would hide it."""
        for t in (1e3, 1e4, 1e5):
            with self.subTest(t_d=t):
                value = line_source_log_derivative(t)
                self.assertLess(value, 0.5)
                self.assertAlmostEqual(0.5 - value, 1.0 / (8.0 * t), delta=1.0 / (8.0 * t) * 1e-3)

    def test_skin_does_not_move_the_derivative(self) -> None:
        """Skin is time-independent, so it cannot appear in a log-time derivative.

        This is the property that makes the derivative a diagnostic: the plateau locates
        permeability-thickness without knowing the skin.
        """
        h = 1e-6
        for skin in (0.0, 5.0):
            with self.subTest(skin=skin):
                numeric = (
                    line_source_dimensionless_pressure(1e5 * math.exp(h), skin=skin)
                    - line_source_dimensionless_pressure(1e5 * math.exp(-h), skin=skin)
                ) / (2.0 * h)
                self.assertAlmostEqual(numeric, line_source_log_derivative(1e5), places=7)


class UnitConversionTests(unittest.TestCase):
    """The boundary where field units meet the dimensionless interior."""

    def test_pressure_round_trip(self) -> None:
        for p_d in (0.5, 2.7, 10.0):
            with self.subTest(p_d=p_d):
                psi = pressure_drop_psi(
                    p_d,
                    permeability_md=K,
                    thickness_ft=H,
                    rate_stb_per_day=Q,
                    formation_volume_factor=B,
                    viscosity_cp=MU,
                )
                back = dimensionless_pressure(
                    psi,
                    permeability_md=K,
                    thickness_ft=H,
                    rate_stb_per_day=Q,
                    formation_volume_factor=B,
                    viscosity_cp=MU,
                )
                self.assertAlmostEqual(back, p_d, places=12)

    def test_dimensionless_time_scales_as_declared(self) -> None:
        self.assertAlmostEqual(t_d(2.0) / t_d(1.0), 2.0, places=12)
        doubled = dimensionless_time(
            1.0,
            permeability_md=2 * K,
            porosity=PHI,
            viscosity_cp=MU,
            total_compressibility_per_psi=CT,
            wellbore_radius_ft=RW,
        )
        self.assertAlmostEqual(doubled / t_d(1.0), 2.0, places=12)

    def test_radius_enters_squared_which_is_where_a_diameter_slip_shows(self) -> None:
        """Using a diameter for r_w would change t_D by exactly four, not two."""
        halved = dimensionless_time(
            1.0,
            permeability_md=K,
            porosity=PHI,
            viscosity_cp=MU,
            total_compressibility_per_psi=CT,
            wellbore_radius_ft=RW / 2.0,
        )
        self.assertAlmostEqual(halved / t_d(1.0), 4.0, places=10)

    def test_porosity_above_one_is_refused(self) -> None:
        with self.assertRaises(InvalidInputError):
            dimensionless_time(
                1.0,
                permeability_md=K,
                porosity=18.0,
                viscosity_cp=MU,
                total_compressibility_per_psi=CT,
                wellbore_radius_ft=RW,
            )

    def test_every_property_must_be_positive(self) -> None:
        base = dict(
            permeability_md=K,
            porosity=PHI,
            viscosity_cp=MU,
            total_compressibility_per_psi=CT,
            wellbore_radius_ft=RW,
        )
        for name in base:
            with self.subTest(name=name), self.assertRaises(InvalidInputError):
                dimensionless_time(1.0, **{**base, name: 0.0})

    def test_zero_and_negative_time_are_refused(self) -> None:
        for bad in (0.0, -1.0):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                t_d(bad)


class SemilogRecoveryTests(unittest.TestCase):
    """The inverse path, against the known answer."""

    @staticmethod
    def window(first: float, last: float, per_decade: int = 50) -> list[float]:
        decades = math.log10(last) - math.log10(first)
        n = max(3, int(per_decade * decades) + 1)
        return [10 ** (math.log10(first) + i * decades / (n - 1)) for i in range(n)]

    def interpret(self, times: list[float], skin: float = S):
        return semilog_interpretation(
            times,
            [drawdown(t, skin) for t in times],
            thickness_ft=H,
            rate_stb_per_day=Q,
            formation_volume_factor=B,
            viscosity_cp=MU,
            porosity=PHI,
            total_compressibility_per_psi=CT,
            wellbore_radius_ft=RW,
        )

    def test_recovers_known_permeability(self) -> None:
        fit = self.interpret(self.window(1.0, 48.0))
        self.assertLessEqual(abs(fit.permeability_md - K) / K, 1e-4)

    def test_recovers_known_permeability_thickness(self) -> None:
        fit = self.interpret(self.window(1.0, 48.0))
        self.assertLessEqual(abs(fit.permeability_thickness_md_ft - K * H) / (K * H), 1e-4)

    def test_recovers_known_skin(self) -> None:
        fit = self.interpret(self.window(1.0, 48.0))
        self.assertLessEqual(abs(fit.skin - S), 1e-3)

    def test_recovers_a_negative_skin(self) -> None:
        fit = self.interpret(self.window(1.0, 48.0), skin=-2.0)
        self.assertLessEqual(abs(fit.skin - (-2.0)), 1e-3)

    def test_recovers_zero_skin(self) -> None:
        fit = self.interpret(self.window(1.0, 48.0), skin=0.0)
        self.assertLessEqual(abs(fit.skin), 1e-3)

    def test_permeability_is_independent_of_skin(self) -> None:
        """Skin shifts the line, it does not tilt it. If k moves with s, the slope is wrong."""
        a = self.interpret(self.window(1.0, 48.0), skin=0.0).permeability_md
        b = self.interpret(self.window(1.0, 48.0), skin=8.0).permeability_md
        self.assertAlmostEqual(a, b, places=9)

    def test_outside_the_valid_window_the_recovery_is_wrong(self) -> None:
        """The negative control, as a unit test: the method must fail where it is invalid."""
        early = [t_target * PHI * MU * CT * RW * RW / (TIME_FIELD_FACTOR * K) for t_target in (1.0, 10.0)]
        fit = self.interpret(self.window(early[0], early[1]))
        self.assertGreater(abs(fit.permeability_md - K) / K, 1e-4)

    def test_fit_quality_is_reported_and_near_perfect_on_clean_data(self) -> None:
        fit = self.interpret(self.window(1.0, 48.0))
        self.assertGreater(fit.r_squared, 0.999999)
        self.assertLess(fit.residual_standard_error_psi, 0.01)

    def test_one_hour_value_comes_from_the_line_not_a_data_point(self) -> None:
        """On a log axis the intercept IS the line at one hour; a data point is not."""
        times = self.window(1.0, 48.0)
        fit = self.interpret(times)
        self.assertAlmostEqual(fit.pressure_drop_at_one_hour, fit.intercept_psi, places=12)

    def test_rejects_unsorted_duplicate_and_short_input(self) -> None:
        good = self.window(1.0, 48.0, per_decade=5)
        drops = [drawdown(t) for t in good]
        common = dict(
            thickness_ft=H,
            rate_stb_per_day=Q,
            formation_volume_factor=B,
            viscosity_cp=MU,
            porosity=PHI,
            total_compressibility_per_psi=CT,
            wellbore_radius_ft=RW,
        )
        with self.assertRaises(InvalidInputError):
            semilog_interpretation(list(reversed(good)), drops, **common)
        dup = list(good)
        dup[2] = dup[1]
        with self.assertRaises(InvalidInputError):
            semilog_interpretation(dup, [drawdown(t) for t in dup], **common)
        with self.assertRaises(InvalidInputError):
            semilog_interpretation(good[:2], drops[:2], **common)

    def test_rejects_non_positive_time(self) -> None:
        times = [0.0, 1.0, 10.0]
        with self.assertRaises(InvalidInputError):
            semilog_interpretation(
                times,
                [1.0, 2.0, 3.0],
                thickness_ft=H,
                rate_stb_per_day=Q,
                formation_volume_factor=B,
                viscosity_cp=MU,
                porosity=PHI,
                total_compressibility_per_psi=CT,
                wellbore_radius_ft=RW,
            )

    def test_rejects_non_finite_pressure(self) -> None:
        times = self.window(1.0, 48.0, per_decade=5)
        drops = [drawdown(t) for t in times]
        drops[3] = float("nan")
        with self.assertRaises(InvalidInputError):
            semilog_interpretation(
                times,
                drops,
                thickness_ft=H,
                rate_stb_per_day=Q,
                formation_volume_factor=B,
                viscosity_cp=MU,
                porosity=PHI,
                total_compressibility_per_psi=CT,
                wellbore_radius_ft=RW,
            )

    def test_mismatched_lengths_are_refused(self) -> None:
        times = self.window(1.0, 48.0, per_decade=5)
        with self.assertRaises(InvalidInputError):
            semilog_interpretation(
                times,
                [drawdown(t) for t in times][:-1],
                thickness_ft=H,
                rate_stb_per_day=Q,
                formation_volume_factor=B,
                viscosity_cp=MU,
                porosity=PHI,
                total_compressibility_per_psi=CT,
                wellbore_radius_ft=RW,
            )


class RoundTripTests(unittest.TestCase):
    """Forward then inverse, with the inverse blind to the truth."""

    def test_recovery_holds_across_a_sweep_of_true_parameters(self) -> None:
        for k_true, s_true in ((10.0, 0.0), (50.0, 3.5), (200.0, -1.5), (500.0, 8.0)):
            with self.subTest(k=k_true, s=s_true):

                def dp(hours: float, k_=k_true, s_=s_true) -> float:
                    td = dimensionless_time(
                        hours,
                        permeability_md=k_,
                        porosity=PHI,
                        viscosity_cp=MU,
                        total_compressibility_per_psi=CT,
                        wellbore_radius_ft=RW,
                    )
                    return pressure_drop_psi(
                        line_source_dimensionless_pressure(td, skin=s_),
                        permeability_md=k_,
                        thickness_ft=H,
                        rate_stb_per_day=Q,
                        formation_volume_factor=B,
                        viscosity_cp=MU,
                    )

                times = [10 ** (0.0 + i * (math.log10(48.0)) / 199) for i in range(200)]
                fit = semilog_interpretation(
                    times,
                    [dp(t) for t in times],
                    thickness_ft=H,
                    rate_stb_per_day=Q,
                    formation_volume_factor=B,
                    viscosity_cp=MU,
                    porosity=PHI,
                    total_compressibility_per_psi=CT,
                    wellbore_radius_ft=RW,
                )
                self.assertLessEqual(abs(fit.permeability_md - k_true) / k_true, 1e-3)
                self.assertLessEqual(abs(fit.skin - s_true), 1e-2)

    def test_permeability_helper_matches_the_full_interpretation(self) -> None:
        times = [10 ** (0.0 + i * math.log10(48.0) / 199) for i in range(200)]
        fit = semilog_interpretation(
            times,
            [drawdown(t) for t in times],
            thickness_ft=H,
            rate_stb_per_day=Q,
            formation_volume_factor=B,
            viscosity_cp=MU,
            porosity=PHI,
            total_compressibility_per_psi=CT,
            wellbore_radius_ft=RW,
        )
        direct = permeability_from_semilog_slope(
            fit.slope_psi_per_cycle,
            thickness_ft=H,
            rate_stb_per_day=Q,
            formation_volume_factor=B,
            viscosity_cp=MU,
        )
        self.assertAlmostEqual(direct, fit.permeability_md, places=12)

    def test_skin_helper_matches_the_full_interpretation(self) -> None:
        times = [10 ** (0.0 + i * math.log10(48.0) / 199) for i in range(200)]
        fit = semilog_interpretation(
            times,
            [drawdown(t) for t in times],
            thickness_ft=H,
            rate_stb_per_day=Q,
            formation_volume_factor=B,
            viscosity_cp=MU,
            porosity=PHI,
            total_compressibility_per_psi=CT,
            wellbore_radius_ft=RW,
        )
        direct = skin_from_semilog_line(
            pressure_drop_at_one_hour=fit.pressure_drop_at_one_hour,
            slope_psi_per_cycle=fit.slope_psi_per_cycle,
            permeability_md=fit.permeability_md,
            porosity=PHI,
            viscosity_cp=MU,
            total_compressibility_per_psi=CT,
            wellbore_radius_ft=RW,
        )
        self.assertAlmostEqual(direct, fit.skin, places=12)


class DerivativeAgainstTheExistingAlgorithmTests(unittest.TestCase):
    """The repository's Bourdet derivative, checked against the closed form.

    The existing implementation is verified against the paper's own Table 1, which says
    it implements the published algorithm. It does not say the algorithm is accurate on
    *this* response, which is a separate question and the one B1 needs answered.
    """

    def test_bourdet_matches_the_closed_form_over_the_b1_window(self) -> None:
        from reservoir_lab.diagnostics import bourdet_derivative

        scale = PRESSURE_FIELD_FACTOR * Q * B * MU / (K * H)
        for per_decade, smoothing in ((50, 0.0), (50, 0.1), (20, 0.1), (10, 0.1)):
            with self.subTest(per_decade=per_decade, smoothing_l=smoothing):
                decades = math.log10(48.0)
                n = int(per_decade * decades) + 1
                times = [10 ** (i * decades / (n - 1)) for i in range(n)]
                xs, derivative = bourdet_derivative(
                    times, [drawdown(t) for t in times], smoothing_l=smoothing
                )
                worst = max(
                    abs(d - line_source_log_derivative(t_d(t)) * scale)
                    / (line_source_log_derivative(t_d(t)) * scale)
                    for t, d in zip(xs, derivative, strict=True)
                )
                self.assertLessEqual(worst, 1e-6)

    def test_the_plateau_sits_below_the_ideal_half_by_the_known_deficit(self) -> None:
        from reservoir_lab.diagnostics import bourdet_derivative

        scale = PRESSURE_FIELD_FACTOR * Q * B * MU / (K * H)
        decades = math.log10(48.0)
        n = int(50 * decades) + 1
        times = [10 ** (i * decades / (n - 1)) for i in range(n)]
        xs, derivative = bourdet_derivative(times, [drawdown(t) for t in times], smoothing_l=0.1)
        for t, d in zip(xs, derivative, strict=True):
            with self.subTest(t=t):
                self.assertLess(d, 0.5 * scale)
                self.assertGreater(d, 0.5 * scale * (1.0 - 1e-4))


if __name__ == "__main__":
    unittest.main()

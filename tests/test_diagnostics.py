"""Tests for the log-time and Bourdet pressure derivatives.

The four contract categories are all present and each class says which one it serves.

The oracles used here are, in order of strength:

* the derivative column published by Bourdet, Ayoub and Pirard in 1989, computed by
  their own implementation thirty-odd years before this code existed;
* closed forms that never pass through the estimator -- the exact log-derivative of the
  line-source solution, ``0.5*exp(-r_D^2/(4 t_D))``, and the exact discretisation bias
  ``sinh(n*h)/(n*h)`` of the three-point estimator on a power law;
* a second, algebraically different transcription of the same three-point estimator
  (the interpolating-parabola coefficient form) with a brute-force window search, used
  to check the two-pointer selection;
* analytic regime responses whose derivative is known exactly.

Numerical tolerances are derived before the answer is known, not fitted to it. The
line-source comparison is gated by the truncation series of the central difference plus
the floating-point noise floor of that difference, both written out at the point of use,
and that bound is itself checked to be tight enough to catch a gain error of one part in
a thousand.

Nothing here asserts a number that this module produced. One test is an equivalence gate
rather than an oracle and says so in place: ``smoothing_l = 0`` against the unsmoothed
path compares two transcriptions inside this package, and its correctness content comes
from the oracles that anchor each end.

The one gap worth stating plainly: no test asserts a published derivative *value* for a
non-zero L. The paper's L = 0.1 column needs its full Delta_p column, which is not
committed to this repository. What is asserted for L > 0 is the published point
selection at published spacings, plus closed forms and a brute-force reference.
"""

from __future__ import annotations

import itertools
import math
import random
import sys
import unittest

from reservoir_lab.diagnostics import (
    BOURDET_L_TYPICAL_RANGE,
    BOURDET_L_WORKING_VALUE,
    bourdet_derivative,
    log_time_derivative,
)
from reservoir_lab.errors import InvalidInputError, NotIdentifiableError

#: Ten points per decade is the sampling density the well-test literature quotes for a
#: readable derivative plot, and it is the grid every bias figure in the evidence card is
#: stated on. ln(10)/10 in natural-log cycles.
POINTS_PER_DECADE = 10
LOG_STEP = math.log(10.0) / POINTS_PER_DECADE


def log_grid(start: float, count: int, step: float = LOG_STEP) -> tuple[float, ...]:
    """Geometric time grid: uniform in ln(t) with the given natural-log spacing."""
    return tuple(start * math.exp(step * index) for index in range(count))


def lopsided_grid() -> tuple[float, ...]:
    """Build a deliberately non-uniform grid from irregular ln-spacings.

    Non-uniformity is the whole point: the correct and the transposed weightings agree
    exactly on a uniform grid, so a uniform grid cannot discriminate between them.
    """
    spacings = (0.05, 0.40, 0.11, 0.62, 0.07, 0.33, 0.90, 0.12, 0.25, 0.71, 0.09, 0.44)
    abscissa = [0.0]
    for step in spacings:
        abscissa.append(abscissa[-1] + step)
    return tuple(math.exp(value) for value in abscissa)


def reference_derivative(
    time: tuple[float, ...], response: tuple[float, ...], smoothing_l: float
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Independent reference: brute-force window search, parabola-coefficient form.

    Two things are transcribed differently from the implementation under test. The
    window search is O(n^2) and looks at every candidate rather than walking two
    monotone pointers. The estimator is written as the derivative at the middle node of
    the parabola through the three selected points,

        f'(x_i) = -b/(a(a+b)) * f_j  +  (b-a)/(ab) * f_i  +  a/(b(a+b)) * f_k

    with ``a`` the left and ``b`` the right log-spacing, which is algebraically the same
    quantity as Bourdet's Eq. 8 but arranged so that no expression is shared with the
    code being checked.
    """
    abscissa = [math.log(value) for value in time]
    times: list[float] = []
    values: list[float] = []
    for centre in range(1, len(abscissa) - 1):
        left = [m for m in range(centre) if abscissa[centre] - abscissa[m] >= smoothing_l]
        right = [m for m in range(centre + 1, len(abscissa)) if abscissa[m] - abscissa[centre] >= smoothing_l]
        if not left or not right:
            continue
        j, k = max(left), min(right)
        a = abscissa[centre] - abscissa[j]
        b = abscissa[k] - abscissa[centre]
        value = (
            -b / (a * (a + b)) * response[j]
            + (b - a) / (a * b) * response[centre]
            + a / (b * (a + b)) * response[k]
        )
        times.append(time[centre])
        values.append(value)
    return tuple(times), tuple(values)


def exponential_integral_e1(x: float) -> float:
    """E1(x) for x > 0, to about 1e-15 relative.

    Two algorithms are needed and one will not do: the power series carries the Euler
    constant and loses all its digits to cancellation for large x, while the continued
    fraction converges slowly and inaccurately for small x. Numerical Recipes' standard
    split at x = 1 with a modified Lentz evaluation of the continued fraction.
    """
    if x <= 0.0:
        raise ValueError("E1 is defined here for x > 0 only")
    euler_gamma = 0.5772156649015328606
    if x < 1.0:
        total = -euler_gamma - math.log(x)
        term = 1.0
        for k in range(1, 80):
            term *= -x / k
            total -= term / k
            if abs(term / k) < 1e-18 * abs(total):
                break
        return total
    tiny = 1e-300
    b = x + 1.0
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 300):
        a = -i * i
        b += 2.0
        d = 1.0 / (a * d + b)
        c = b + a / c
        delta = c * d
        h *= delta
        if abs(delta - 1.0) < 1e-17:
            break
    return h * math.exp(-x)


class PublishedTableOneTests(unittest.TestCase):
    """Independent oracle: the derivative column of Bourdet et al. (1989), Table 1.

    The published value was produced by the authors' own implementation and is the only
    check available that pins the formula, the weighting direction, the sign convention
    and the abscissa convention at once.
    """

    # Buildup 2 of the paper, three consecutive rows: elapsed time [hr], pressure change
    # [psi], and the superposition time column X, which the paper prints in natural
    # logarithm. The module differentiates against ln(time), so the time passed in is
    # exp(X); the round trip through exp and log is exact to a part in 1e16 and is far
    # below the rounding of the published X column itself.
    SUPERPOSITION_TIME = (-8.21072, -7.51785, -7.11265)
    PRESSURE_CHANGE_PSI = (0.57, 3.81, 6.55)
    PUBLISHED_DERIVATIVE_PSI = 5.99244
    #: The transposed weighting -- each slope multiplied by its own spacing -- is
    #: algebraically the plain secant across the window. The paper's own data separates
    #: the two by 9 percent, which is what makes this row worth committing.
    TRANSPOSED_WEIGHTING_PSI = 5.44592

    def setUp(self) -> None:
        self.time = tuple(math.exp(value) for value in self.SUPERPOSITION_TIME)

    def test_reproduces_published_derivative(self):
        _, derivative = bourdet_derivative(self.time, self.PRESSURE_CHANGE_PSI, smoothing_l=0.0)
        # Relative, not absolute. The published X column is rounded to five decimals, and
        # on the full 102-row table that rounding alone moves the largest derivative
        # values by up to 0.32 psi, so an absolute 1e-3 psi tolerance fails on most rows
        # while 3e-3 relative holds on all of them. This particular row happens to agree
        # to 6.4e-5 psi, but the tolerance is set by the table, not by the lucky row.
        self.assertAlmostEqual(derivative[0] / self.PUBLISHED_DERIVATIVE_PSI, 1.0, delta=3e-3)

    def test_transposed_weighting_is_the_secant_and_is_excluded(self):
        _, derivative = bourdet_derivative(self.time, self.PRESSURE_CHANGE_PSI, smoothing_l=0.0)
        abscissa = self.SUPERPOSITION_TIME
        response = self.PRESSURE_CHANGE_PSI
        secant = (response[2] - response[0]) / (abscissa[2] - abscissa[0])
        # The two candidate formulas are 9 percent apart on this row, so the published
        # value discriminates between them with room to spare.
        self.assertAlmostEqual(secant, self.TRANSPOSED_WEIGHTING_PSI, delta=1e-3)
        self.assertGreater(abs(secant - self.PUBLISHED_DERIVATIVE_PSI), 0.5)
        # Relative, for the reason given in the sibling test and in
        # docs/evidence/derivative.md: the published X column is rounded to five
        # decimals, an absolute 1e-3 psi gate fails on 73 of the table's 102 rows, and it
        # would pass here only because this row happens to be a lucky one. 3e-3 relative
        # is the figure that holds across the whole table.
        self.assertAlmostEqual(derivative[0] / self.PUBLISHED_DERIVATIVE_PSI, 1.0, delta=3e-3)


class WeightingDirectionTests(unittest.TestCase):
    """Property: the weighting direction, with a closed-form contrast.

    A response that is quadratic in ln(time) has a known derivative and a non-zero second
    derivative. The correct weighting is the derivative of the interpolating parabola, so
    it is exact for such a response on any grid. The transposed weighting is the secant,
    whose error on a quadratic is exactly the difference of the two log-spacings. That
    gives an analytic statement of how much better the correct weighting is, rather than
    a vague "closer".
    """

    def setUp(self) -> None:
        self.time = lopsided_grid()
        # response = X^2 with X = ln(t); d(response)/dX = 2X exactly.
        self.response = tuple(math.log(value) ** 2 for value in self.time)

    def test_correct_weighting_is_exact_on_a_quadratic(self):
        times, derivative = bourdet_derivative(self.time, self.response, smoothing_l=0.0)
        for time_value, value in zip(times, derivative, strict=True):
            expected = 2.0 * math.log(time_value)
            # Exact up to rounding: the estimator interpolates the parabola it is given.
            self.assertAlmostEqual(value, expected, delta=1e-12 * max(1.0, abs(expected)))

    def test_transposed_weighting_is_wrong_by_the_spacing_difference(self):
        abscissa = [math.log(value) for value in self.time]
        response = self.response
        worst_correct = 0.0
        worst_transposed = 0.0
        for i in range(1, len(abscissa) - 1):
            a = abscissa[i] - abscissa[i - 1]
            b = abscissa[i + 1] - abscissa[i]
            slope_left = (response[i] - response[i - 1]) / a
            slope_right = (response[i + 1] - response[i]) / b
            transposed = (slope_left * a + slope_right * b) / (a + b)
            exact = 2.0 * abscissa[i]
            worst_transposed = max(worst_transposed, abs(transposed - exact))
            # The secant's error on a quadratic in X is exactly (b - a).
            self.assertAlmostEqual(transposed - exact, b - a, delta=1e-12)
        times, derivative = bourdet_derivative(self.time, response, smoothing_l=0.0)
        for time_value, value in zip(times, derivative, strict=True):
            worst_correct = max(worst_correct, abs(value - 2.0 * math.log(time_value)))
        self.assertGreater(worst_transposed, 0.4)
        self.assertLess(worst_correct, 1e-12)
        self.assertGreater(worst_transposed / max(worst_correct, 1e-16), 1e6)

    def test_smoothed_weighting_stays_exact_on_a_quadratic(self):
        # The parabola argument does not depend on which points the L rule picks, so a
        # smoothed window must remain exact too. This catches a weighting error that a
        # transcriber might make only in the windowed branch.
        for smoothing in (0.0, 0.15, 0.5):
            times, derivative = bourdet_derivative(self.time, self.response, smoothing_l=smoothing)
            with self.subTest(smoothing_l=smoothing):
                for time_value, value in zip(times, derivative, strict=True):
                    self.assertAlmostEqual(value, 2.0 * math.log(time_value), delta=1e-11)


class RadialFlowPlateauTests(unittest.TestCase):
    """Limiting case: infinite-acting radial flow, where the answer is a constant.

    During IARF the response is affine in ln(time), the estimator is exact, and the
    plateau must come out to machine precision for every L and on any grid. This is the
    structural test of the whole estimator, and it is also the reason a plateau test
    alone cannot check the weighting direction: the secant is exact on affine data too.
    """

    SLOPE_PSI_PER_LN_CYCLE = 7.25

    def affine_response(self, time):
        return tuple(self.SLOPE_PSI_PER_LN_CYCLE * math.log(value) + 311.0 for value in time)

    def test_plateau_is_exact_on_a_uniform_grid(self):
        time = log_grid(1e-3, 60)
        response = self.affine_response(time)
        for smoothing in (0.0, 0.1, 0.4, 1.0):
            with self.subTest(smoothing_l=smoothing):
                _, derivative = bourdet_derivative(time, response, smoothing_l=smoothing)
                for value in derivative:
                    self.assertAlmostEqual(value / self.SLOPE_PSI_PER_LN_CYCLE, 1.0, delta=1e-12)

    def test_plateau_is_exact_on_a_lopsided_grid(self):
        time = lopsided_grid()
        response = self.affine_response(time)
        for smoothing in (0.0, BOURDET_L_WORKING_VALUE, 0.5):
            with self.subTest(smoothing_l=smoothing):
                _, derivative = bourdet_derivative(time, response, smoothing_l=smoothing)
                for value in derivative:
                    self.assertAlmostEqual(value / self.SLOPE_PSI_PER_LN_CYCLE, 1.0, delta=1e-12)

    def test_constant_response_gives_exactly_zero(self):
        time = lopsided_grid()
        response = tuple(2500.0 for _ in time)
        for smoothing in (0.0, 0.3):
            with self.subTest(smoothing_l=smoothing):
                _, derivative = bourdet_derivative(time, response, smoothing_l=smoothing)
                # Every increment is exactly 0.0, so the result is exactly 0.0, not
                # merely small. assertEqual is deliberate.
                self.assertTrue(all(value == 0.0 for value in derivative))

    def test_plateau_height_matches_the_published_field_unit_constants(self):
        """Independent oracle: 162.6 (semilog slope) and 70.6 (derivative plateau).

        These two field-unit constants are published separately in the well-test
        literature, and the derivative links them: the plateau of d(dp)/d ln(t) must be
        the semilog slope divided by ln(10). A response built from the 162.6 group must
        therefore come out on the 70.6 group.
        """
        rate_stb_per_day = 174.0
        formation_volume_factor_rb_per_stb = 1.06
        viscosity_cp = 2.5
        permeability_md = 12.0
        thickness_ft = 41.0
        group = (
            rate_stb_per_day
            * formation_volume_factor_rb_per_stb
            * viscosity_cp
            / (permeability_md * thickness_ft)
        )
        semilog_slope_psi_per_decade = 162.6 * group
        time_hr = log_grid(0.1, 40)
        response_psi = tuple(semilog_slope_psi_per_decade * math.log10(value) + 40.0 for value in time_hr)
        _, derivative = bourdet_derivative(time_hr, response_psi, smoothing_l=0.1)
        expected_plateau_psi = 70.6 * group
        for value in derivative:
            # 162.6/ln(10) = 70.617, so the two published constants are themselves only
            # consistent to 2.4e-4 relative; the tolerance is set by that rounding, not
            # by the estimator, which is exact here.
            self.assertAlmostEqual(value / expected_plateau_psi, 1.0, delta=1e-3)


class LineSourceClosedFormTests(unittest.TestCase):
    """Independent oracle: the exact log-derivative of the line-source solution.

    With p_D = 0.5*E1(r_D^2/(4 t_D)), differentiating gives d p_D/d ln(t_D) =
    0.5*exp(-r_D^2/(4 t_D)) exactly, because d/d ln(t_D) of the argument is minus the
    argument. The target never passes through the estimator, and unlike the plateau and
    power-law oracles this one has genuine, varying curvature, which is what the
    discretisation error actually responds to.
    """

    def setUp(self) -> None:
        self.time_dimensionless = log_grid(0.1, 81)
        self.response = tuple(
            0.5 * exponential_integral_e1(1.0 / (4.0 * value)) for value in self.time_dimensionless
        )

    def test_e1_implementation_matches_published_values(self):
        # Guard on the oracle itself: an oracle nobody checks is not an oracle. Values
        # are standard published E1 values to eight decimals.
        published = {
            0.1: 1.82292396,
            0.05: 2.46789849,
            0.02: 3.35470778,
            0.01: 4.03792958,
            0.005: 4.72609546,
            0.0025: 5.41674732,
        }
        for argument, expected in published.items():
            with self.subTest(x=argument):
                self.assertAlmostEqual(exponential_integral_e1(argument), expected, places=7)

    @staticmethod
    def error_bound(time_dimensionless: float, step: float, response_value: float) -> float:
        """Bound on the estimator's error at one point, derived before it was measured.

        On a grid uniform in ln(t_D) the three-point weighting collapses to the central
        difference, whose error is the classical truncation series

            (f(X+h) - f(X-h))/(2h) - f'(X) = (h^2/6) f'''(X) + (h^4/120) f^(5)(X) + ...

        For the line-source solution p_D = 0.5*E1(u), u = 1/(4 t_D), the derivatives with
        respect to X = ln(t_D) follow from du/dX = -u, which gives the recursion
        d/dX[0.5 e^-u P(u)] = 0.5 e^-u * u * (P - dP/du) and hence

            p_D'    = 0.5 e^-u
            p_D'''  = 0.5 e^-u (u^2 - u)
            p_D^(5) = 0.5 e^-u (u^4 - 6 u^3 + 7 u^2 - u).

        The two retained terms are summed in absolute value, so this is a majorant of the
        series rather than a cancelling estimate of it, and the factor 1.05 covers the
        first neglected term (h^6/5040) p_D^(7) at the spacings used here.

        The second contribution is floating point rather than truncation: the estimator
        differences two response values of size |p_D| and divides by 2h, so its rounding
        noise is of order eps*|p_D|/h. It is negligible at early time and takes over at
        late time, where the truncation error has decayed below it -- without it the
        bound would be asserting more than double precision can deliver.

        Nothing in this bound is a number that the module produced.
        """
        u = 1.0 / (4.0 * time_dimensionless)
        decay = 0.5 * math.exp(-u)
        third = decay * (u * u - u)
        fifth = decay * (u**4 - 6.0 * u**3 + 7.0 * u * u - u)
        truncation = (step**2 / 6.0) * abs(third) + (step**4 / 120.0) * abs(fifth)
        rounding = 4.0 * sys.float_info.epsilon * abs(response_value) / step
        return 1.05 * truncation + rounding

    def test_derivative_tracks_the_closed_form_within_the_truncation_bound(self):
        # Grid-independent by construction: the bound is a function of the local
        # solution and of h, so the same assertion has to hold whatever the grid start
        # and the sampling density are. Several of each are run for exactly that reason
        # -- a tolerance that only holds on one grid is fitted to it.
        for start, points_per_decade in ((0.1, 10), (0.12, 10), (0.3, 10), (0.1, 8), (0.1, 20)):
            step = math.log(10.0) / points_per_decade
            time = log_grid(start, 81, step)
            response = tuple(0.5 * exponential_integral_e1(1.0 / (4.0 * value)) for value in time)
            response_at = dict(zip(time, response, strict=True))
            times, derivative = bourdet_derivative(time, response, smoothing_l=0.0)
            for time_value, value in zip(times, derivative, strict=True):
                exact = 0.5 * math.exp(-1.0 / (4.0 * time_value))
                with self.subTest(start=start, per_decade=points_per_decade, t_D=time_value):
                    self.assertLess(
                        abs(value - exact),
                        self.error_bound(time_value, step, response_at[time_value]),
                    )

    def test_the_truncation_bound_is_a_gate_and_not_a_formality(self):
        # A tolerance nobody has tried to violate is decoration. A gain error of one part
        # in a thousand -- far smaller than the transposed weighting, and invisible on a
        # log-log plot -- must break the bound at most of the points it is asserted on.
        step = LOG_STEP
        times, derivative = bourdet_derivative(self.time_dimensionless, self.response, smoothing_l=0.0)
        response_at = dict(zip(self.time_dimensionless, self.response, strict=True))
        caught = 0
        for time_value, value in zip(times, derivative, strict=True):
            exact = 0.5 * math.exp(-1.0 / (4.0 * time_value))
            bound = self.error_bound(time_value, step, response_at[time_value])
            if abs(1.001 * value - exact) > bound:
                caught += 1
        self.assertGreater(caught, len(times) // 2)

    def test_error_decays_as_the_curvature_dies(self):
        times, derivative = bourdet_derivative(self.time_dimensionless, self.response, smoothing_l=0.0)
        errors = [
            (time_value, abs(value - 0.5 * math.exp(-1.0 / (4.0 * time_value))))
            for time_value, value in zip(times, derivative, strict=True)
        ]
        early = max(error for time_value, error in errors if 1.0 <= time_value <= 10.0)
        late = max(error for time_value, error in errors if time_value >= 1e4)
        self.assertGreater(early / late, 100.0)

    def test_derivative_is_monotone_and_bounded_by_the_plateau(self):
        # p_D' = 0.5*exp(-1/(4 t_D)) rises monotonically to 0.5 and never exceeds it.
        _, derivative = bourdet_derivative(self.time_dimensionless, self.response, smoothing_l=0.0)
        self.assertTrue(all(b > a for a, b in itertools.pairwise(derivative)))
        self.assertTrue(all(value < 0.5 for value in derivative))


class PowerLawRegimeTests(unittest.TestCase):
    """Independent oracle: the closed-form discretisation bias, and the regime slopes.

    For dp = A*exp(n*X) sampled on a uniform ln grid of spacing h, the three-point
    estimator returns exactly n*dp*sinh(n*h)/(n*h). Asserting "derivative == n*dp" would
    fail at the 0.9 percent level for unit slope at ten points per decade, so the bias is
    asserted, not tolerated.
    """

    COEFFICIENT = 3.7

    def power_law(self, exponent, count=60, step=LOG_STEP):
        time = log_grid(1e-2, count, step)
        response = tuple(self.COEFFICIENT * value**exponent for value in time)
        return time, response

    def test_bias_matches_the_sinh_closed_form(self):
        for exponent in (1.0, 0.5, 0.25, -0.5):
            time, response = self.power_law(exponent)
            times, derivative = bourdet_derivative(time, response, smoothing_l=0.0)
            expected_factor = math.sinh(exponent * LOG_STEP) / (exponent * LOG_STEP)
            with self.subTest(n=exponent):
                for time_value, value in zip(times, derivative, strict=True):
                    analytic = exponent * self.COEFFICIENT * time_value**exponent
                    self.assertAlmostEqual(value / analytic, expected_factor, delta=1e-12)

    def test_bias_grows_with_the_window(self):
        # With ten points per decade, L = 0.5 skips to the third neighbour (3h = 0.691,
        # while 2h = 0.461 < 0.5), so the bias factor is sinh(3nh)/(3nh).
        exponent = 1.0
        time, response = self.power_law(exponent)
        times, derivative = bourdet_derivative(time, response, smoothing_l=0.5)
        spacing = 3.0 * LOG_STEP
        expected_factor = math.sinh(exponent * spacing) / (exponent * spacing)
        self.assertAlmostEqual(expected_factor, 1.0814476, places=6)
        for time_value, value in zip(times, derivative, strict=True):
            analytic = exponent * self.COEFFICIENT * time_value**exponent
            self.assertAlmostEqual(value / analytic, expected_factor, delta=1e-12)

    def test_bias_vanishes_on_a_refined_grid(self):
        # sinh(n h)/(n h) -> 1 as h -> 0, so refinement is a convergence check on the
        # estimator: 100 points per decade must cut the unit-slope bias by about 100.
        exponent = 1.0
        coarse_step = LOG_STEP
        fine_step = LOG_STEP / 10.0
        errors = []
        for step in (coarse_step, fine_step):
            time, response = self.power_law(exponent, count=400, step=step)
            times, derivative = bourdet_derivative(time, response, smoothing_l=0.0)
            index = len(times) // 2
            analytic = exponent * self.COEFFICIENT * times[index] ** exponent
            errors.append(abs(derivative[index] / analytic - 1.0))
        self.assertGreater(errors[0] / errors[1], 90.0)

    def test_wellbore_storage_derivative_coincides_with_the_response(self):
        """Limiting case: during pure wellbore storage dp' equals dp, not merely parallel.

        dp = q*B*dt/(24*C) is a unit-slope power law, so dp' = dt*d(dp)/d(dt) = dp. The
        estimator reproduces the identity up to the sinh bias, which is 0.886 percent on
        this grid, and to well under 1e-4 on a grid ten times finer.
        """
        rate_stb_per_day = 174.0
        formation_volume_factor_rb_per_stb = 1.06
        storage_bbl_per_psi = 9.3e-3
        coefficient = rate_stb_per_day * formation_volume_factor_rb_per_stb / (24.0 * storage_bbl_per_psi)
        for step, tolerance in ((LOG_STEP, 1e-2), (LOG_STEP / 10.0, 1e-4)):
            time_hr = log_grid(1e-4, 120, step)
            response_psi = tuple(coefficient * value for value in time_hr)
            times, derivative = bourdet_derivative(time_hr, response_psi, smoothing_l=0.0)
            with self.subTest(step=step):
                for time_value, value in zip(times, derivative, strict=True):
                    self.assertAlmostEqual(value / (coefficient * time_value), 1.0, delta=tolerance)

    def test_log_log_slope_of_the_derivative_recovers_the_regime_exponent(self):
        """Property: the diagnostic slope d ln(dp')/d ln(t) equals n for each regime.

        Applying the estimator a second time, to ln(dp') against ln(t), is exact here:
        the sinh bias is a constant factor on a uniform grid, so ln(dp') is affine in
        ln(t) and the second pass returns n to machine precision. The target values
        1, 1/2, 1/4 are the published regime slopes for storage, linear flow and bilinear
        flow.
        """
        for exponent in (1.0, 0.5, 0.25):
            time, response = self.power_law(exponent)
            times, derivative = bourdet_derivative(time, response, smoothing_l=0.0)
            _, slope = log_time_derivative(times, tuple(math.log(v) for v in derivative))
            with self.subTest(n=exponent):
                for value in slope:
                    # Chained passes, as in the spherical case: a few hundred rounding
                    # units, not the single-pass 1e-12.
                    self.assertAlmostEqual(value, exponent, delta=1e-10)


class SphericalAndPseudoSteadyTests(unittest.TestCase):
    """Property: the two regimes whose published one-line summaries are wrong or ambiguous.

    Spherical flow is the correction the evidence card carries: the ratio dp'/dp does not
    read -1/2 there. The response is dp = a - b/sqrt(t) with a, b > 0, so the derivative
    is +(b/2)/sqrt(t), strictly positive, while dp tends to the constant a; the ratio
    therefore tends to zero from above, as it also does for radial flow. What reads -1/2
    for spherical flow is the log-log slope of the derivative curve, a different
    quantity. Both are asserted here, separately.

    Pseudo-steady state is the companion ambiguity: its derivative has unit slope, like
    wellbore storage, and only the ratio dp'/dp separates them.
    """

    STEADY_TERM_PSI = 100.0
    TRANSIENT_TERM_PSI = 10.0

    def setUp(self) -> None:
        self.time_hr = log_grid(1e-2, 60)
        self.response_psi = tuple(
            self.STEADY_TERM_PSI - self.TRANSIENT_TERM_PSI / math.sqrt(value) for value in self.time_hr
        )

    def test_spherical_derivative_is_positive_everywhere(self):
        times, derivative = bourdet_derivative(self.time_hr, self.response_psi, smoothing_l=0.0)
        self.assertTrue(all(value > 0.0 for value in derivative))
        factor = math.sinh(-0.5 * LOG_STEP) / (-0.5 * LOG_STEP)
        for time_value, value in zip(times, derivative, strict=True):
            # The constant term contributes exactly nothing to a derivative, so only the
            # t^(-1/2) term survives and its bias factor is the same sinh form.
            analytic = 0.5 * self.TRANSIENT_TERM_PSI / math.sqrt(time_value)
            self.assertAlmostEqual(value / analytic, factor, delta=1e-11)

    def test_spherical_beta_ratio_is_positive_and_tends_to_zero(self):
        times, derivative = bourdet_derivative(self.time_hr, self.response_psi, smoothing_l=0.0)
        response = dict(zip(self.time_hr, self.response_psi, strict=True))
        beta = [value / response[time_value] for time_value, value in zip(times, derivative, strict=True)]
        self.assertTrue(all(value > 0.0 for value in beta))
        self.assertTrue(all(b < a for a, b in itertools.pairwise(beta)))
        self.assertLess(beta[-1], 1e-2)
        # Regression against the claim that spherical flow reads beta = -1/2. It does not,
        # and nothing here is even close to it.
        self.assertGreater(min(beta), 0.0)
        self.assertGreater(min(abs(value + 0.5) for value in beta), 0.4)

    def test_spherical_log_log_derivative_slope_is_minus_one_half(self):
        times, derivative = bourdet_derivative(self.time_hr, self.response_psi, smoothing_l=0.0)
        _, slope = log_time_derivative(times, tuple(math.log(value) for value in derivative))
        for value in slope:
            # Two chained differencing passes plus a logarithm in between, so the
            # tolerance is a few hundred rounding units rather than the single-pass 1e-12.
            self.assertAlmostEqual(value, -0.5, delta=1e-10)

    def test_pseudo_steady_state_is_unit_slope_but_not_coincident(self):
        decline_psi_per_hr = 0.85
        intercept_psi = 240.0
        time_hr = log_grid(1.0, 40)
        response_psi = tuple(decline_psi_per_hr * value + intercept_psi for value in time_hr)
        times, derivative = bourdet_derivative(time_hr, response_psi, smoothing_l=0.0)
        factor = math.sinh(LOG_STEP) / LOG_STEP
        beta = []
        for time_value, value in zip(times, derivative, strict=True):
            # The Cartesian intercept differentiates to nothing, so the derivative is the
            # same unit-slope line as pure storage would give.
            self.assertAlmostEqual(value / (decline_psi_per_hr * time_value), factor, delta=1e-11)
            beta.append(value / (decline_psi_per_hr * time_value + intercept_psi))
        # Storage would give beta = 1 (up to the bias); the non-zero intercept keeps PSS
        # strictly below it and makes beta vary with time. That difference is the only
        # thing separating the two on a log-log plot.
        self.assertTrue(all(value < factor for value in beta))
        self.assertTrue(all(b > a for a, b in itertools.pairwise(beta)))


class SmoothingWindowTests(unittest.TestCase):
    """Independent algorithm and property: the L rule and what it selects."""

    def setUp(self) -> None:
        self.time = lopsided_grid()
        self.response = tuple(
            12.0 * math.log(value) + 0.4 * math.log(value) ** 2 + 3.0 for value in self.time
        )

    def test_unsmoothed_path_is_exact_on_a_quadratic_in_log_time(self):
        """Independent oracle for the unsmoothed path itself, not for the window.

        ``log_time_derivative`` delegates its arithmetic, so it needs an oracle of its
        own rather than a comparison against the code it delegates to. A response that is
        quadratic in ln(t) is differentiated exactly by the three-point weighting on any
        grid, so the closed form 2*ln(t) pins the weighting direction on this path too:
        the transposed form is the secant, whose error on a quadratic is the difference
        of the two log spacings, and the lopsided grid makes that difference large.
        """
        response = tuple(math.log(value) ** 2 for value in self.time)
        times, derivative = log_time_derivative(self.time, response)
        self.assertEqual(times, self.time[1:-1])
        for time_value, value in zip(times, derivative, strict=True):
            expected = 2.0 * math.log(time_value)
            # Exact up to rounding: the estimator reproduces the parabola it is given.
            self.assertAlmostEqual(value, expected, delta=1e-12 * max(1.0, abs(expected)))

    def test_zero_window_agrees_bit_for_bit_with_the_unsmoothed_path(self):
        # An equivalence gate, not an oracle: it compares two code paths in this package
        # against each other, so it would pass if both were wrong in the same way. What
        # it is for is the documented claim that L = 0 degenerates to the immediate
        # neighbours and to the same expression, bit for bit. The numbers on both ends
        # are anchored elsewhere -- by the published Table 1 row for the windowed path,
        # and by the quadratic closed form above for the unsmoothed one.
        expected_times, expected = log_time_derivative(self.time, self.response)
        times, derivative = bourdet_derivative(self.time, self.response, smoothing_l=0.0)
        self.assertEqual(times, expected_times)
        self.assertEqual(derivative, expected)

    def test_matches_a_brute_force_reference_for_every_window(self):
        for smoothing in (0.0, 0.05, 0.1, 0.3, 0.5, 1.0, 1.5):
            with self.subTest(smoothing_l=smoothing):
                expected_times, expected = reference_derivative(self.time, self.response, smoothing)
                times, derivative = bourdet_derivative(self.time, self.response, smoothing_l=smoothing)
                self.assertEqual(times, expected_times)
                for value, reference in zip(derivative, expected, strict=True):
                    # Different algebraic grouping of the same estimator, so agreement is
                    # limited only by floating-point rounding.
                    self.assertAlmostEqual(value, reference, delta=1e-11 * max(1.0, abs(reference)))

    def test_matches_the_brute_force_reference_on_random_grids(self):
        """Independent algorithm: the two-pointer selection against an exhaustive search.

        The pointer walk relies on both window indices being non-decreasing in the centre
        index. That is true, but it is the kind of argument that fails on one awkward
        grid, so it is checked against an exhaustive search on a spread of them. The
        generator is seeded explicitly: an unseeded random test that fails once and
        passes on rerun is worse than no test.
        """
        rng = random.Random(20240613)
        for trial in range(25):
            count = rng.randint(6, 40)
            spacings = [rng.uniform(0.01, 0.9) for _ in range(count - 1)]
            abscissa = [0.0]
            for step in spacings:
                abscissa.append(abscissa[-1] + step)
            time = tuple(math.exp(value) for value in abscissa)
            response = tuple(rng.uniform(-50.0, 50.0) + 8.0 * value + 0.7 * value**2 for value in abscissa)
            smoothing = rng.choice((0.0, 0.05, 0.2, 0.5, 1.0))
            expected_times, expected = reference_derivative(time, response, smoothing)
            with self.subTest(trial=trial, count=count, smoothing_l=smoothing):
                if not expected_times:
                    with self.assertRaises(NotIdentifiableError):
                        bourdet_derivative(time, response, smoothing_l=smoothing)
                    continue
                times, derivative = bourdet_derivative(time, response, smoothing_l=smoothing)
                self.assertEqual(times, expected_times)
                for value, reference in zip(derivative, expected, strict=True):
                    self.assertAlmostEqual(value, reference, delta=1e-9 * max(1.0, abs(reference)))

    def test_window_is_measured_in_natural_log_cycles_not_decades(self):
        """Property: the L unit, on a grid built so the two readings disagree.

        The grid is uniform at 0.15 natural-log cycles. L = 0.1 read in ln cycles selects
        the immediate neighbours; read as 0.1 decades (0.2303 ln cycles) it would skip to
        the second neighbours. On a curved response the two answers differ, and only the
        first is Bourdet's.
        """
        step = 0.15
        exponent = 3.0
        time = log_grid(1.0, 21, step)
        response = tuple(value**exponent for value in time)
        times, derivative = bourdet_derivative(time, response, smoothing_l=0.1)

        def bias(offset):
            # Closed-form bias of the estimator on a power law at a spacing of
            # offset*step, so neither expected value comes from running this module.
            spacing = offset * step
            return math.sinh(exponent * spacing) / (exponent * spacing)

        natural_log_reading = bias(1)
        decade_reading = bias(2)
        self.assertGreater(decade_reading / natural_log_reading - 1.0, 0.09)
        for time_value, value in zip(times, derivative, strict=True):
            analytic = exponent * time_value**exponent
            self.assertAlmostEqual(value / analytic, natural_log_reading, delta=1e-12)
            self.assertGreater(abs(value / analytic - decade_reading), 0.09)

    def test_exact_ties_pin_the_convention_on_both_sides_and_at_the_boundary(self):
        """Convention: the ``>=`` tie-break, at all three places the rule is applied.

        The sibling test below settles the tie on the left walk only -- on its grid the
        right point is the same index either way. The rule is decided in three places:
        the walk left, the walk right, and the guard that asks whether any point at all
        lies a full window to the left of the centre. A grid of powers of two with
        ``L = ln 2`` puts an exact binary tie at every one of them at once.

        The oracle is a closed form, not a recorded value. For a cubic response in
        ``X = ln(t)`` the three-point weighting returns ``f'(X) + (a*b/6)*f'''(X)``, and
        with ``f = (X - X0)^3`` that is ``f'(X) + a*b`` exactly, for any spacings ``a``
        and ``b``. So each admitted triple has an exactly known answer and the
        alternative selections have different, exactly known answers.
        """
        time = (0.5, 1.0, 2.0, 4.0)
        window = math.log(2.0)
        abscissa = [math.log(value) for value in time]
        for lower, upper in itertools.pairwise(abscissa):
            # Bit-for-bit ties: on these four values the logarithm differences land on
            # ln 2 exactly, so the >= and > readings genuinely diverge here. They do not
            # on every power of two -- ln 8 - ln 4 is one unit in the last place short --
            # which is why the grid stops at 4.
            self.assertEqual(upper - lower, window)
        response = tuple(value**3 for value in abscissa)

        times, derivative = bourdet_derivative(time, response, smoothing_l=window)
        # The left-boundary guard. t = 1.0 lies exactly one window from the first point,
        # so it is admitted; a strict comparison there drops it from the record without
        # any other visible effect.
        self.assertEqual(times, (1.0, 2.0))
        for time_value, value in zip(times, derivative, strict=True):
            x = math.log(time_value)
            # a = b = ln 2 for every admitted centre on this grid.
            expected = 3.0 * x * x + window * window
            with self.subTest(t=time_value):
                self.assertAlmostEqual(value, expected, delta=1e-12 * max(1.0, abs(expected)))
        # The right walk. At t = 1.0 the right spacing to t = 2.0 is exactly L, so it is
        # admitted; a strict comparison would step over it to t = 4.0, giving a*b = 2L^2
        # instead of L^2 -- a factor of two in the derivative, not a rounding artefact --
        # and would drop t = 2.0 from the record for want of a right point at all.
        admitted = window * window
        strict_right_reading = 2.0 * window * window
        self.assertAlmostEqual(derivative[0], admitted, delta=1e-12)
        self.assertAlmostEqual(strict_right_reading / admitted, 2.0, delta=1e-12)

    def test_published_spacings_select_the_points_the_paper_reports(self):
        """Independent oracle for the L > 0 selection: the paper's own row, Table 1.

        Bourdet et al. state which neighbours the L = 0.1 rule takes at Delta_t = 0.04583
        hr of Table 1: the left point at 0.03750 is used because Delta_X1 = 0.20013 >= L,
        the right point at 0.05000 is skipped because Delta_X2 = 0.08674 < L, and 0.05833
        with Delta_X2 = 0.24035 is used instead. Those spacings are published; the
        derivative value is not asserted here, because the table's full Delta_p column is
        not committed to this repository (see the note in docs/evidence/derivative.md).
        So the published part of this test is the geometry and the selection, and the
        value is supplied by the same cubic closed form used above.

        It also pins the unit of L on published spacings: read as 0.1 decades, L = 0.2303
        would skip the left neighbour at 0.20013 as well, and the row would drop out of
        the result entirely rather than merely change value.
        """
        # Superposition-time column of Table 1, natural logarithm, four consecutive rows
        # around Delta_t = 0.04583 hr.
        published_abscissa = (-6.01567, -5.81554, -5.72880, -5.57519)
        centre_abscissa = published_abscissa[1]
        self.assertAlmostEqual(centre_abscissa - published_abscissa[0], 0.20013, places=5)
        self.assertAlmostEqual(published_abscissa[2] - centre_abscissa, 0.08674, places=5)
        self.assertAlmostEqual(published_abscissa[3] - centre_abscissa, 0.24035, places=5)

        time = tuple(math.exp(value) for value in published_abscissa)
        response = tuple((value - centre_abscissa) ** 3 for value in published_abscissa)
        times, derivative = bourdet_derivative(time, response, smoothing_l=0.1)

        self.assertIn(time[1], times)
        value = derivative[times.index(time[1])]
        # f' = 0 at the centre of this response, so the estimator returns exactly a*b.
        selected = 0.20013 * 0.24035
        skipped_right = 0.20013 * 0.08674
        # Rounding only: the spacings are differences of the printed five-decimal X
        # column, carried through exp and log, which costs a part in 1e15.
        self.assertAlmostEqual(value, selected, delta=1e-9)
        self.assertGreater(abs(value - skipped_right) / selected, 0.6)
        # The decade reading of L drops the row instead of selecting different points.
        with self.assertRaises(NotIdentifiableError):
            bourdet_derivative(time, response, smoothing_l=math.log(10.0) * 0.1)

    def test_exact_tie_in_spacing_admits_the_point(self):
        """Convention, not oracle: a spacing exactly equal to L counts as satisfying it.

        The paper prints a strict inequality and this implementation uses ``>=``. No
        published data settles the difference, because it shows up only on an exact tie
        and the paper's own table contains none, so this test pins the documented choice
        rather than a physical truth. Powers of two give a tie that is exact in binary
        floating point: ln(4) - ln(2) is bit-for-bit ln(2).
        """
        time = (1.0, 2.0, 4.0, 8.0, 16.0, 32.0)
        window = math.log(2.0)
        abscissa = [math.log(value) for value in time]
        self.assertEqual(abscissa[2] - abscissa[1], window)
        exponent = 3.0
        response = tuple(value**exponent for value in time)

        def closed_form(centre, left, right):
            # General bias of the three-point estimator on dp = A*exp(n*X) with unequal
            # spacings a and b, derived analytically in docs/evidence/derivative.md.
            a = abscissa[centre] - abscissa[left]
            b = abscissa[right] - abscissa[centre]
            factor = ((1.0 - math.exp(-exponent * a)) / a * b + (math.exp(exponent * b) - 1.0) / b * a) / (
                a + b
            )
            return response[centre] * factor

        times, derivative = bourdet_derivative(time, response, smoothing_l=window)
        index = times.index(4.0)
        # The right neighbour at index 3 misses the window by one rounding unit, so the
        # right point is index 4 either way; only the left point is in question.
        admitted = closed_form(2, 1, 4)
        excluded = closed_form(2, 0, 4)
        self.assertAlmostEqual(derivative[index] / admitted, 1.0, delta=1e-12)
        self.assertGreater(abs(admitted - excluded) / admitted, 0.1)

    def test_points_without_a_full_window_are_omitted(self):
        smoothing = 0.5
        times, derivative = bourdet_derivative(self.time, self.response, smoothing_l=smoothing)
        self.assertEqual(len(times), len(derivative))
        abscissa = [math.log(value) for value in self.time]
        kept = set(times)
        for index, time_value in enumerate(self.time):
            has_left = abscissa[index] - abscissa[0] >= smoothing
            has_right = abscissa[-1] - abscissa[index] >= smoothing
            with self.subTest(index=index):
                # Membership, not a one-sided fallback: a point either had a full window
                # on both sides or it is simply not in the result.
                self.assertEqual(time_value in kept, has_left and has_right)

    def test_result_shrinks_as_the_window_grows(self):
        counts = []
        for smoothing in (0.0, 0.2, 0.6, 1.2):
            times, _ = bourdet_derivative(self.time, self.response, smoothing_l=smoothing)
            counts.append(len(times))
        self.assertTrue(all(b <= a for a, b in itertools.pairwise(counts)))
        self.assertGreater(counts[0], counts[-1])

    def test_abscissa_is_an_ordered_subset_of_the_input(self):
        times, _ = bourdet_derivative(self.time, self.response, smoothing_l=0.3)
        self.assertTrue(all(b > a for a, b in itertools.pairwise(times)))
        self.assertTrue(set(times).issubset(set(self.time)))

    def test_typical_range_constants_match_the_source(self):
        # The constants exist so a test can read the published range rather than repeat
        # it: Bourdet et al. quote 0 to 0.5, working value 0.1, in natural-log cycles.
        self.assertEqual(BOURDET_L_TYPICAL_RANGE, (0.0, 0.5))
        self.assertEqual(BOURDET_L_WORKING_VALUE, 0.1)
        low, high = BOURDET_L_TYPICAL_RANGE
        self.assertLessEqual(low, BOURDET_L_WORKING_VALUE)
        self.assertLessEqual(BOURDET_L_WORKING_VALUE, high)


class InvariantTests(unittest.TestCase):
    """Property: the invariances the estimator must have, and the types it must return."""

    def setUp(self) -> None:
        self.time = lopsided_grid()
        self.response = tuple(5.0 * math.log(value) + 0.25 * math.log(value) ** 2 for value in self.time)

    def test_derivative_is_invariant_under_a_change_of_time_unit(self):
        # d/d ln(t) cannot see a constant factor on t: ln(c*t) = ln(c) + ln(t) and the
        # spacings are unchanged. Hours to days must move nothing but the abscissa.
        factor = 1.0 / 24.0
        _, hours = bourdet_derivative(self.time, self.response, smoothing_l=0.2)
        _scaled_times, days = bourdet_derivative(
            tuple(value * factor for value in self.time), self.response, smoothing_l=0.2
        )
        self.assertEqual(len(hours), len(days))
        for a, b in zip(hours, days, strict=True):
            self.assertAlmostEqual(a, b, delta=1e-11 * max(1.0, abs(a)))

    def test_derivative_is_linear_in_the_response(self):
        scale, offset = -3.5, 812.0
        _, base = bourdet_derivative(self.time, self.response, smoothing_l=0.25)
        _, transformed = bourdet_derivative(
            self.time,
            tuple(scale * value + offset for value in self.response),
            smoothing_l=0.25,
        )
        for a, b in zip(base, transformed, strict=True):
            self.assertAlmostEqual(b, scale * a, delta=1e-11 * max(1.0, abs(a)))

    def test_negative_derivatives_are_preserved(self):
        # A falling response is physical information. Nothing may clip it or take its
        # absolute value, so a response that decreases as -3*ln(t) must come back as
        # exactly -3 everywhere.
        response = tuple(-3.0 * math.log(value) + 90.0 for value in self.time)
        for smoothing in (0.0, 0.3):
            with self.subTest(smoothing_l=smoothing):
                _, derivative = bourdet_derivative(self.time, response, smoothing_l=smoothing)
                self.assertTrue(all(value < 0.0 for value in derivative))
                for value in derivative:
                    self.assertAlmostEqual(value, -3.0, delta=1e-12)

    def test_sign_change_within_one_record_is_preserved(self):
        # A response that rises then falls must give a derivative that changes sign, not
        # one that is flattened at zero.
        response = tuple(-((math.log(value) - 0.5) ** 2) for value in self.time)
        _, derivative = bourdet_derivative(self.time, response, smoothing_l=0.0)
        self.assertGreater(max(derivative), 0.0)
        self.assertLess(min(derivative), 0.0)

    def test_returns_tuples_of_floats(self):
        result = bourdet_derivative(self.time, self.response, smoothing_l=0.1)
        self.assertIsInstance(result, tuple)
        times, derivative = result
        self.assertIsInstance(times, tuple)
        self.assertIsInstance(derivative, tuple)
        self.assertTrue(all(isinstance(value, float) for value in times + derivative))

    def test_repeated_calls_are_identical(self):
        first = bourdet_derivative(self.time, self.response, smoothing_l=0.1)
        second = bourdet_derivative(list(self.time), list(self.response), smoothing_l=0.1)
        self.assertEqual(first, second)

    def test_accepts_any_sequence_type(self):
        from_tuple = bourdet_derivative(self.time, self.response, smoothing_l=0.0)
        from_list = bourdet_derivative(list(self.time), list(self.response), smoothing_l=0.0)
        from_generator_backed = bourdet_derivative(iter(self.time), iter(self.response), smoothing_l=0.0)
        self.assertEqual(from_tuple, from_list)
        self.assertEqual(from_tuple, from_generator_backed)


class InvalidInputTests(unittest.TestCase):
    """Invalid input: every documented raise is exercised, for both functions."""

    def setUp(self) -> None:
        self.time = log_grid(1.0, 8)
        self.response = tuple(3.0 * math.log(value) for value in self.time)

    def call_both(self, time, response, **kwargs):
        yield lambda: log_time_derivative(time, response)
        yield lambda: bourdet_derivative(time, response, smoothing_l=kwargs.get("smoothing_l", 0.1))

    def test_length_mismatch(self):
        for call in self.call_both(self.time, self.response[:-1]):
            with self.assertRaises(InvalidInputError):
                call()

    def test_too_few_points(self):
        for count in (0, 1, 2):
            for call in self.call_both(self.time[:count], self.response[:count]):
                with self.subTest(count=count), self.assertRaises(InvalidInputError):
                    call()

    def test_non_finite_values(self):
        for bad in (float("nan"), float("inf"), -float("inf")):
            broken_time = (bad, *self.time[1:])
            broken_response = (bad, *self.response[1:])
            for call in self.call_both(broken_time, self.response):
                with self.subTest(bad=bad, which="time"), self.assertRaises(InvalidInputError):
                    call()
            for call in self.call_both(self.time, broken_response):
                with self.subTest(bad=bad, which="response"), self.assertRaises(InvalidInputError):
                    call()

    def test_non_positive_time(self):
        for bad in (0.0, -1.0):
            broken = (bad, *self.time[1:])
            for call in self.call_both(broken, self.response):
                with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                    call()

    def test_time_not_strictly_increasing(self):
        repeated = (*self.time[:3], self.time[2], *self.time[4:])
        decreasing = tuple(reversed(self.time))
        for candidate in (repeated, decreasing):
            for call in self.call_both(candidate, self.response):
                with self.subTest(case=candidate[:4]), self.assertRaises(InvalidInputError):
                    call()

    def test_non_numeric_and_non_iterable(self):
        for call in self.call_both(self.time, ("a", *self.response[1:])):
            with self.assertRaises(InvalidInputError):
                call()
        with self.assertRaises(InvalidInputError):
            bourdet_derivative(3.0, self.response, smoothing_l=0.1)
        with self.assertRaises(InvalidInputError):
            log_time_derivative(self.time, 3.0)

    def test_invalid_smoothing_window(self):
        for bad in (-1e-9, -0.5, float("nan"), float("inf")):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                bourdet_derivative(self.time, self.response, smoothing_l=bad)

    def test_smoothing_window_wider_than_the_record(self):
        # Not an empty result and not a one-sided fallback: the window and the record are
        # incompatible, and that is a statement about identifiability.
        span = math.log(self.time[-1]) - math.log(self.time[0])
        with self.assertRaises(NotIdentifiableError):
            bourdet_derivative(self.time, self.response, smoothing_l=span)

    def test_overflowing_stencil_raises_instead_of_returning_nan(self):
        """Invalid input: C3 forbids a nan sentinel, so an overflowing stencil raises.

        The increments here are 2e308 apart, so each slope overflows to infinity and
        their weighted mean is inf/inf, that is nan. Without the guard both functions
        return ``((2.0, 4.0), (nan, nan))`` -- a result-shaped object that every other
        assertion in this file accepts, which is precisely why this test exists.
        """
        time = (1.0, 2.0, 4.0, 8.0)
        response = (-1e308, 1e308, -1e308, 1e308)
        for call in self.call_both(time, response, smoothing_l=0.0):
            with self.assertRaises(InvalidInputError) as caught:
                call()
            # Both paths must name the point, and both must be the package's own
            # exception type: a bare ValueError escapes `except ReservoirLabError`.
            self.assertIn("time[1]", str(caught.exception))

    def test_a_record_wider_than_the_ratio_form_is_still_differentiated(self):
        """Regression: a span over 308 decades is well conditioned on the ln axis.

        ``bourdet_derivative`` forms its spacings as ``ln(t_k/t_i)``, which keeps the
        relative precision of a closely spaced pair but overflows when the two times are
        more than about 308 decades apart -- although the spacing itself, a few hundred
        natural-log cycles, is perfectly representable. No real pressure record spans
        that, but rejecting a well-posed input is still a wrong answer. The expected
        values come from the parabola-coefficient transcription evaluated on the
        logarithms directly, so they do not share an expression with the code under test.
        """
        time = (1e-320, 1e-160, 1e160, 1e300)
        response = (0.0, 10.0, 20.0, 30.0)
        abscissa = [math.log(value) for value in time]
        times, derivative = bourdet_derivative(time, response, smoothing_l=0.0)
        self.assertEqual(times, time[1:-1])
        for index, value in enumerate(derivative, start=1):
            a = abscissa[index] - abscissa[index - 1]
            b = abscissa[index + 1] - abscissa[index]
            expected = (
                -b / (a * (a + b)) * response[index - 1]
                + (b - a) / (a * b) * response[index]
                + a / (b * (a + b)) * response[index + 1]
            )
            with self.subTest(index=index):
                self.assertTrue(math.isfinite(value))
                self.assertAlmostEqual(value, expected, delta=1e-12 * abs(expected))
        # The delegate keeps the ratio form and cannot do this, but it may not leak a
        # bare ValueError either: the wrapper converts it and says which call does work.
        with self.assertRaises(InvalidInputError) as caught:
            log_time_derivative(time, response)
        self.assertIn("bourdet_derivative", str(caught.exception))

    def test_error_message_names_the_offending_index(self):
        broken = (*self.time[:4], float("nan"), *self.time[5:])
        with self.assertRaises(InvalidInputError) as caught:
            bourdet_derivative(broken, self.response, smoothing_l=0.1)
        self.assertIn("time[4]", str(caught.exception))


if __name__ == "__main__":
    unittest.main()

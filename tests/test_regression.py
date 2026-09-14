"""Tests for `reservoir_lab.regression`.

The four categories required by api_contract.md C7 appear as four groups of classes:
independent oracles, limiting cases, invalid input, and properties/invariants.

Two of these tests carry most of the module's weight and are worth reading before the
rest.

`DeltaMethodMonteCarlo` is the reason the module exists. It generates many synthetic
realisations of a p/Z line with known noise, measures the scatter of the fitted
x-intercept, and compares it against the delta-method standard error -- and against a
deliberately defective version that drops the slope-intercept covariance. The correct
one agrees; the defective one is wrong by a third. Without that contrast the test would
prove only that the code runs, because the defective estimator is *conservative* and
therefore never looks broken on its own.

`FiellerCoverage` is the same idea applied to the confidence set. Comparing a closed
form against a grid inversion of the same defining inequality is circular with respect
to the set's geometry: both sides inherit an identical mistake. A coverage study is not,
because the truth is the simulated gas in place, known from outside the estimator.
Mishandling the two-half-line case necessarily pushes coverage above nominal, so the
assertion bracket is chosen to exclude the value that the mishandled version produces.

Provenance note on the fixtures. The Pearson/York benchmark arrays below were recalled
rather than read from Pearson (1901) or York (1966); they are corroborated indirectly
but strongly, in that they reproduce five independently published quantities from York
et al. (2004) Table II to six significant figures. The NCSS Example 1 arrays and the
Anscombe arrays are published data.

Provenance of the asserted values. Everything outside the final `RegressionPins` class
comes from a publication, from closed-form algebra, from a Monte Carlo study whose truth
is the simulated quantity, or from a general-purpose numerical method that shares no
algebra with the code under test. `RegressionPins` holds the exceptions -- four numbers
this module produced on data for which no publication states them. They are labelled as
pins rather than oracles and kept apart, because a golden value protects against an
unintended change and proves nothing about correctness, and filing one under
"independent oracle" overstates the evidence.
"""

from __future__ import annotations

import math
import random
import unittest
from dataclasses import FrozenInstanceError

from reservoir_lab.errors import (
    ConvergenceError,
    InvalidInputError,
    NotIdentifiableError,
)
from reservoir_lab.regression import (
    DELTA_METHOD_G_THRESHOLD,
    FIELLER_BOUNDED,
    FIELLER_EXCLUSIVE,
    FIELLER_WHOLE_LINE,
    BlockLengthAdvice,
    BootstrapResult,
    FiellerInterval,
    IntervalEstimate,
    LineFit,
    deming_line,
    moving_block_bootstrap,
    ols_line,
    student_t_quantile,
    suggested_block_length,
    x_intercept,
    x_intercept_fieller,
    x_intercept_variance_collapsed,
    york_line,
)

# --------------------------------------------------------------------------
# Published fixtures
# --------------------------------------------------------------------------

# York, Evensen, Lopez Martinez & De Basabe Delgado (2004), Am. J. Phys. 72(3):367-375,
# Table II data set 3 (the Pearson 1901 points with the York 1966 weights). The weights
# are omega(X) = 1/sigma(X)**2 and omega(Y) = 1/sigma(Y)**2.
YORK_X = (0.0, 0.9, 1.8, 2.6, 3.3, 4.4, 5.2, 6.1, 6.5, 7.4)
YORK_Y = (5.9, 5.4, 4.4, 4.6, 3.5, 3.7, 2.8, 2.8, 2.4, 1.5)
YORK_OMEGA_X = (1000.0, 1000.0, 500.0, 800.0, 200.0, 80.0, 60.0, 20.0, 1.8, 1.0)
YORK_OMEGA_Y = (1.0, 1.8, 4.0, 8.0, 20.0, 20.0, 70.0, 70.0, 100.0, 500.0)
YORK_X_STD = tuple(1.0 / math.sqrt(w) for w in YORK_OMEGA_X)
YORK_Y_STD = tuple(1.0 / math.sqrt(w) for w in YORK_OMEGA_Y)

# NCSS Statistical Software, Chapter 303 "Deming Regression", Example 1 (DemingReg1).
NCSS_X = (7.0, 8.3, 10.5, 9.0, 5.1, 8.2, 10.2, 10.3, 7.1, 5.9)
NCSS_Y = (7.9, 8.2, 9.6, 9.0, 6.5, 7.3, 10.2, 10.6, 6.3, 5.2)
NCSS_VAR_X = 0.032
NCSS_VAR_Y = 0.008
NCSS_LAMBDA = NCSS_VAR_X / NCSS_VAR_Y  # 4.0 in the NCSS/Linnet convention

# Anscombe, F.J. (1973), "Graphs in Statistical Analysis", The American Statistician
# 27(1):17-21, data set 1. Published fit: y = 3.0 + 0.5 x, R-squared 0.67.
ANSCOMBE_X = (10.0, 8.0, 13.0, 9.0, 11.0, 14.0, 6.0, 4.0, 12.0, 7.0, 5.0)
ANSCOMBE_Y1 = (8.04, 6.95, 7.58, 8.81, 8.33, 9.96, 7.24, 4.26, 10.84, 4.82, 5.68)

# Synthetic volumetric p/Z line used throughout: G = 100 Bscf, p_i/Z_i = 4705.9 psia,
# so the slope is -47.059 psia/Bscf. Nothing about it is fitted; it is written down.
DEMO_GAS_IN_PLACE = 100.0
DEMO_INITIAL_P_OVER_Z = 4705.9


def demo_line(depletion_fraction: float, n_points: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Noise-free p/Z survey points over the first `depletion_fraction` of G."""
    xs = tuple(depletion_fraction * DEMO_GAS_IN_PLACE * i / (n_points - 1) for i in range(n_points))
    ys = tuple(DEMO_INITIAL_P_OVER_Z * (1.0 - xi / DEMO_GAS_IN_PLACE) for xi in xs)
    return xs, ys


def wrong_x_intercept_stderr(fit: LineFit) -> float:
    """Return the defective estimator: Var(a) and Var(b) propagated as if uncorrelated.

    This lives in the test file, not in the module, so that no caller can ever reach
    it. It exists to be shown wrong.
    """
    value = -fit.intercept / fit.slope
    variance = (fit.intercept_stderr**2 + value * value * fit.slope_stderr**2) / fit.slope**2
    return math.sqrt(variance)


def least_squares_moments(
    xs: tuple[float, ...], ys: tuple[float, ...], weights: tuple[float, ...] | None = None
) -> dict[str, float]:
    """Recompute a weighted least-squares fit from the raw data, sharing nothing.

    Everything the Fieller set and the inverse-prediction variance need, derived here
    from `x`, `y` and the weights alone. Nothing is read off a `LineFit`: a wrong Sxx,
    a wrong total weight or a wrong residual mean square inside the module has to move
    only one side of any comparison that uses this.
    """
    ws = (1.0,) * len(xs) if weights is None else tuple(weights)
    n = len(xs)
    weight_total = sum(ws)
    x_mean = sum(w * v for w, v in zip(ws, xs, strict=True)) / weight_total
    y_mean = sum(w * v for w, v in zip(ws, ys, strict=True)) / weight_total
    sxx = sum(w * (v - x_mean) ** 2 for w, v in zip(ws, xs, strict=True))
    sxy = sum(w * (a - x_mean) * (b - y_mean) for w, a, b in zip(ws, xs, ys, strict=True))
    slope = sxy / sxx
    intercept = y_mean - slope * x_mean
    sse = sum(w * (b - intercept - slope * a) ** 2 for w, a, b in zip(ws, xs, ys, strict=True))
    return {
        "slope": slope,
        "intercept": intercept,
        "x_mean": x_mean,
        "sxx": sxx,
        "weight_total": weight_total,
        "residual_variance": sse / (n - 2),
        "dof": n - 2,
    }


def brute_force_fieller_set(
    xs: tuple[float, ...],
    ys: tuple[float, ...],
    *,
    confidence: float,
    span: float,
    samples: int,
    weights: tuple[float, ...] | None = None,
) -> list[tuple[float, float]]:
    """Invert the defining inequality on a grid and return its contiguous pieces.

    Deliberately literal: it evaluates `(a + b x)**2 - t**2 s**2 [1/W + (x-xbar)**2/Sxx]`
    at every grid node and reports where it is non-positive. The coefficients and the
    moments come from `least_squares_moments`, i.e. from the raw data, so the only
    thing shared with the closed form under test is the defining inequality itself.
    """
    m = least_squares_moments(xs, ys, weights)
    t = student_t_quantile(0.5 + 0.5 * confidence, m["dof"])
    centre = -m["intercept"] / m["slope"]
    pieces: list[tuple[float, float]] = []
    current: list[float] | None = None
    for index in range(samples):
        x = centre - span + 2.0 * span * index / (samples - 1)
        left = (m["intercept"] + m["slope"] * x) ** 2
        right = t * t * m["residual_variance"] * (1.0 / m["weight_total"] + (x - m["x_mean"]) ** 2 / m["sxx"])
        if left <= right:
            if current is None:
                current = [x, x]
            else:
                current[1] = x
        elif current is not None:
            pieces.append((current[0], current[1]))
            current = None
    if current is not None:
        pieces.append((current[0], current[1]))
    return pieces


def golden_section_minimum(objective, low: float, high: float, *, width: float) -> float:
    """Locate the minimum of a unimodal objective on [low, high] by golden section.

    A general-purpose 1-D minimiser: it knows nothing about lines, variance ratios or
    quadratic roots, so a closed form checked against it is checked against something
    that shares no algebra with it. The bracket is shrunk until it is narrower than
    `width` and the midpoint returned.
    """
    inverse_phi = 0.5 * (math.sqrt(5.0) - 1.0)
    a, b = low, high
    c = b - inverse_phi * (b - a)
    d = a + inverse_phi * (b - a)
    fc, fd = objective(c), objective(d)
    while b - a > width:
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - inverse_phi * (b - a)
            fc = objective(c)
        else:
            a, c, fc = c, d, fd
            d = a + inverse_phi * (b - a)
            fd = objective(d)
    return 0.5 * (a + b)


# --------------------------------------------------------------------------
# C7.1 Independent oracle
# --------------------------------------------------------------------------


#: Published two-sided 95 percent critical values, t(0.975, dof).
PUBLISHED_T_975 = {
    1: 12.70620474,
    2: 4.30265273,
    3: 3.18244630,
    5: 2.57058184,
    8: 2.30600414,
    10: 2.22813885,
    20: 2.08596345,
    30: 2.04227246,
    100: 1.98397152,
}
#: Published one-sided 95 percent critical values, t(0.95, dof).
PUBLISHED_T_95 = {1: 6.31375151, 5: 2.01504837, 10: 1.81246112, 30: 1.69726089}


class StudentTQuantileOracle(unittest.TestCase):
    """The t quantile against published tables, since SciPy is not available."""

    def test_matches_published_two_sided_table(self):
        for dof, reference in PUBLISHED_T_975.items():
            with self.subTest(dof=dof):
                self.assertAlmostEqual(student_t_quantile(0.975, dof), reference, places=7)

    def test_matches_published_one_sided_table(self):
        for dof, reference in PUBLISHED_T_95.items():
            with self.subTest(dof=dof):
                self.assertAlmostEqual(student_t_quantile(0.95, dof), reference, places=7)

    def test_approaches_the_normal_quantile_at_the_published_asymptotic_rate(self):
        # t -> N(0,1) as dof -> infinity, and the leading correction is known in closed
        # form: t(p, nu) - z(p) ~ (z**3 + z) / (4 nu). Asserting the rate rather than
        # just the limit makes this a real check on the inversion at large dof.
        z = 1.9599639845400545
        for dof in (1.0e3, 1.0e4, 1.0e6):
            with self.subTest(dof=dof):
                excess = student_t_quantile(0.975, dof) - z
                predicted = (z**3 + z) / (4.0 * dof)
                self.assertLess(abs(excess / predicted - 1.0), 0.01)
        # By dof = 1e8 the excess itself is only 2.4e-8, so the meaningful claim is
        # absolute rather than relative: the quantile is still good to under 1e-8.
        far = student_t_quantile(0.975, 1.0e8)
        self.assertLess(abs(far - (z + (z**3 + z) / 4.0e8)), 1.0e-8)
        # The excess shrinks like 1/dof, so this also pins down the limit itself: the
        # quantile is within 2.5e-6 of the normal value by dof = 1e6. Beyond about
        # 1e8 the incomplete-beta evaluation loses figures to cancellation, which is
        # stated in the function's validity window and is far outside any regression
        # use, where the degrees of freedom are n - 2.
        self.assertLess(abs(student_t_quantile(0.975, 1.0e6) - z), 2.5e-6)

    def test_symmetry_and_median(self):
        self.assertEqual(student_t_quantile(0.5, 7), 0.0)
        self.assertAlmostEqual(student_t_quantile(0.025, 7), -student_t_quantile(0.975, 7), places=14)

    def test_matches_the_two_closed_form_quantiles(self):
        # Two degrees of freedom have an elementary inverse CDF, and neither one goes
        # anywhere near an incomplete beta function:
        #   dof = 1 is Cauchy, F(t) = 1/2 + arctan(t)/pi, so t = tan(pi (p - 1/2));
        #   dof = 2 has F(t) = 1/2 (1 + t / sqrt(2 + t**2)), so with u = 2p - 1,
        #   t = u sqrt(2 / (1 - u**2)).
        # Both are exact, so the only error admitted is floating point in the two
        # elementary functions and in the inversion: a handful of ulp. 1e-12 relative
        # is three orders above that and still far tighter than any table check.
        for p in (0.6, 0.75, 0.9, 0.975, 0.995, 0.9995):
            with self.subTest(p=p, dof=1):
                cauchy = math.tan(math.pi * (p - 0.5))
                self.assertLess(abs(student_t_quantile(p, 1) / cauchy - 1.0), 1.0e-12)
            with self.subTest(p=p, dof=2):
                u = 2.0 * p - 1.0
                closed = u * math.sqrt(2.0 / (1.0 - u * u))
                self.assertLess(abs(student_t_quantile(p, 2) / closed - 1.0), 1.0e-12)

    def test_small_non_integer_dof_against_the_tail_asymptote(self):
        # The docstring promises that dof need not be an integer and need not be large.
        # Below dof = 1 there is no table to check against, but there is a closed-form
        # asymptote: as x = dof/(dof + t**2) -> 0 the regularised incomplete beta obeys
        # I_x(a, b) = x**a / (a B(a, b)) * (1 + O(x)), so the upper tail is
        #     P(T > t) = 0.5 * (dof/t**2)**(dof/2) / ((dof/2) B(dof/2, 1/2)),
        # which inverts in closed form for t. At these degrees of freedom the quantile
        # is astronomically large, so the neglected O(x) term is smaller than 1e-100
        # and the comparison is limited only by floating point in lgamma and exp --
        # a few ulp on a logarithm of size a few hundred. Compare the logarithms, since
        # the values themselves span 1e6 to 1e128, and allow 1e-12 absolute there.
        for dof in (0.5e-1, 1.0e-1, 2.0e-2, 1.0e-2):
            for p in (0.9, 0.975):
                with self.subTest(dof=dof, p=p):
                    a = 0.5 * dof
                    log_beta = math.lgamma(a) + math.lgamma(0.5) - math.lgamma(a + 0.5)
                    log_rhs = math.log(2.0 * (1.0 - p)) + math.log(a) + log_beta
                    log_reference = 0.5 * (math.log(dof) - log_rhs / a)
                    self.assertLess(abs(math.log(student_t_quantile(p, dof)) - log_reference), 1.0e-12)

    def test_a_quantile_too_large_to_evaluate_is_refused_as_an_input(self):
        # dof this small sends the quantile past 1e150, where the CDF's incomplete-beta
        # argument dof/(dof + t**2) stops being a normal double and the CDF collapses
        # to exactly 1 for every t. The function must say that the input is out of
        # reach; it must not report a solver failure, because nothing failed to solve,
        # and it must not return the artefact a bracket found in the underflow region.
        with self.assertRaises(InvalidInputError) as caught:
            student_t_quantile(0.975, 1.0e-3)
        self.assertIn("degrees_of_freedom", str(caught.exception))


class OlsPublishedOracle(unittest.TestCase):
    """Ordinary least squares against Anscombe (1973) data set 1."""

    def test_anscombe_first_set(self):
        fit = ols_line(ANSCOMBE_X, ANSCOMBE_Y1)
        # Anscombe reports y = 3 + 0.5x and R-squared 0.67 for all four of his sets.
        self.assertAlmostEqual(fit.intercept, 3.0, places=2)
        self.assertAlmostEqual(fit.slope, 0.5, places=3)
        self.assertAlmostEqual(fit.r_squared, 0.6665, places=4)
        # SE(slope) = 0.1179 is the value printed by every textbook treatment of this
        # data set; it is also sqrt(s**2 / Sxx), which is checked independently below.
        self.assertAlmostEqual(fit.slope_stderr, 0.1179, places=4)
        self.assertEqual(fit.degrees_of_freedom, 9)

    def test_closed_form_moments_recomputed_by_hand(self):
        fit = ols_line(ANSCOMBE_X, ANSCOMBE_Y1)
        n = len(ANSCOMBE_X)
        x_mean = sum(ANSCOMBE_X) / n
        y_mean = sum(ANSCOMBE_Y1) / n
        sxx = sum((v - x_mean) ** 2 for v in ANSCOMBE_X)
        sxy = sum((a - x_mean) * (b - y_mean) for a, b in zip(ANSCOMBE_X, ANSCOMBE_Y1, strict=True))
        self.assertAlmostEqual(fit.slope, sxy / sxx, places=13)
        self.assertAlmostEqual(fit.intercept, y_mean - (sxy / sxx) * x_mean, places=13)
        # Cov(a, b) = -xbar * Var(b), negative for a positive abscissa mean.
        self.assertAlmostEqual(fit.covariance, -x_mean * fit.slope_stderr**2, places=15)
        self.assertLess(fit.covariance, 0.0)


class YorkPublishedOracle(unittest.TestCase):
    """York et al. (2004) Table II, data set 3."""

    def setUp(self):
        self.fit = york_line(YORK_X, YORK_Y, x_std=YORK_X_STD, y_std=YORK_Y_STD)

    def test_published_slope_and_intercept(self):
        self.assertAlmostEqual(self.fit.intercept, 5.47991, places=5)
        self.assertAlmostEqual(self.fit.slope, -0.480533, places=6)

    def test_published_mswd(self):
        # York prints S/(n-2) = 1.483 for this set.
        self.assertAlmostEqual(self.fit.mswd, 1.483, places=3)

    def test_published_standard_errors(self):
        # Table II gives Monte Carlo sigmas with a percentage offset Delta, from which
        # the analytic values follow: sigma_a = 0.295713*(1 - 0.00251151) = 0.2949704
        # and sigma_b = 0.058256*(1 - 0.00464447) = 0.0579855. Those back-computed
        # references carry only the six printed figures of the table, so they are
        # compared in relative terms at the 2e-5 level rather than to a fixed number of
        # decimals -- claiming more would be claiming precision the source does not have.
        self.assertLess(abs(self.fit.intercept_stderr / 0.2949704 - 1.0), 2.0e-5)
        self.assertLess(abs(self.fit.slope_stderr / 0.0579855 - 1.0), 2.0e-5)

    def test_axis_swap_is_an_independent_route_to_the_x_intercept(self):
        # York's own recipe (2004, Sec. III): interchange the axes and their weights;
        # the y-intercept of the swapped fit IS the x-intercept of the original and its
        # sigma_a IS its standard error, with no delta method involved. Two different
        # numerical paths, so each is an oracle for the other.
        swapped = york_line(YORK_Y, YORK_X, x_std=YORK_Y_STD, y_std=YORK_X_STD)
        delta = x_intercept(self.fit)
        self.assertAlmostEqual(swapped.intercept, delta.value, places=12)
        self.assertAlmostEqual(swapped.intercept_stderr, delta.stderr, places=12)
        self.assertAlmostEqual(delta.value, 11.403807, places=6)
        self.assertAlmostEqual(delta.stderr, 0.8020969, places=7)

    def test_dropping_the_covariance_disagrees_with_the_axis_swap(self):
        # Same data, same fit: the only difference is the omitted cross term. It is
        # +88 percent here, and it disagrees with York's own axis-swap answer.
        swapped = york_line(YORK_Y, YORK_X, x_std=YORK_Y_STD, y_std=YORK_X_STD)
        wrong = wrong_x_intercept_stderr(self.fit)
        self.assertAlmostEqual(wrong, 1.5067785, places=6)
        self.assertGreater(wrong / swapped.intercept_stderr, 1.80)


class DemingPublishedOracle(unittest.TestCase):
    """Deming regression against NCSS Chapter 303, Example 1."""

    def setUp(self):
        self.fit = deming_line(NCSS_X, NCSS_Y, error_variance_ratio=NCSS_LAMBDA)

    def test_published_coefficients_to_full_printed_precision(self):
        # NCSS prints these in its Estimated Model block at full precision.
        self.assertAlmostEqual(self.fit.slope, 1.00119422781949, places=12)
        self.assertAlmostEqual(self.fit.intercept, -0.0897448990070444, places=12)

    def test_published_jackknife_standard_errors(self):
        self.assertAlmostEqual(self.fit.slope_stderr, 0.18718, places=5)
        self.assertAlmostEqual(self.fit.intercept_stderr, 1.72199, places=5)

    def test_published_confidence_interval_for_the_slope(self):
        # NCSS reports [0.56956, 1.43283] using t(0.975, N-2) with N-2 = 8.
        t = student_t_quantile(0.975, self.fit.degrees_of_freedom)
        low = self.fit.slope - t * self.fit.slope_stderr
        high = self.fit.slope + t * self.fit.slope_stderr
        self.assertAlmostEqual(low, 0.56956, places=5)
        self.assertAlmostEqual(high, 1.43283, places=5)


class DemingAgainstYorkCrossEstimator(unittest.TestCase):
    """Two algorithms with no shared derivation must land on the same line.

    The Deming closed form is a one-shot quadratic root. The York scheme is an
    iteratively reweighted fixed point that reaches the same objective from a different
    direction. Neither can absorb the other's error.
    """

    def setUp(self):
        self.deming = deming_line(NCSS_X, NCSS_Y, error_variance_ratio=NCSS_LAMBDA)
        n = len(NCSS_X)
        self.york = york_line(
            NCSS_X,
            NCSS_Y,
            x_std=(math.sqrt(NCSS_VAR_X),) * n,
            y_std=(math.sqrt(NCSS_VAR_Y),) * n,
            correlation=0.0,
        )

    def test_coefficients_agree_to_machine_precision(self):
        self.assertAlmostEqual(self.york.slope, self.deming.slope, places=13)
        self.assertAlmostEqual(self.york.intercept, self.deming.intercept, places=13)
        self.assertAlmostEqual(self.york.slope, 1.00119422781949, places=12)

    def test_mswd_equals_the_effective_variance_chi_square_computed_by_hand(self):
        # The MSWD is recomputed here from its definition rather than compared against
        # a number this module printed. With constant sigma(x), constant sigma(y) and
        # zero correlation, York's effective weight collapses to the effective-variance
        # form W_i = 1 / (sigma_y**2 + b**2 sigma_x**2), so
        #     S = sum W_i (y_i - a - b x_i)**2,    MSWD = S / (n - 2),
        # evaluated at coefficients that the test above has already pinned to the NCSS
        # published values. Nothing is read off the fit except a and b.
        slope, intercept = self.york.slope, self.york.intercept
        weight = 1.0 / (NCSS_VAR_Y + slope * slope * NCSS_VAR_X)
        chi_square = sum(
            weight * (b - intercept - slope * a) ** 2 for a, b in zip(NCSS_X, NCSS_Y, strict=True)
        )
        by_hand = chi_square / (len(NCSS_X) - 2)
        # Both sides are the same sum of ten terms in double precision; they agree to
        # rounding, so the gate is machine precision rather than a chosen tolerance.
        self.assertLess(abs(self.york.mswd / by_hand - 1.0), 1.0e-13)
        # The physical reading, which is why this number is asserted at all: an MSWD of
        # roughly seventeen says the assigned variances are about seventeen times too
        # small for the observed scatter, so they cannot be trusted at face value.
        self.assertGreater(self.york.mswd, 10.0)

    def test_the_two_standard_errors_answer_different_questions(self):
        # This is asserted, not merely documented, because an implementer handed both
        # oracles will otherwise assume they should agree and chase a non-bug. York's
        # analytic sigma trusts the assigned variances; the jackknife measures the
        # scatter from the data. The observed scatter exceeds the assigned scale by
        # sqrt(MSWD), so the jackknife standard error must exceed the analytic one by
        # roughly that factor -- a prediction, not a recorded ratio.
        self.assertAlmostEqual(self.deming.slope_stderr, 0.187177, places=6)  # NCSS
        ratio = self.deming.slope_stderr / self.york.slope_stderr
        predicted = math.sqrt(self.york.mswd)
        # The residual gap between the two is the difference between a delete-one
        # jackknife of a nonlinear statistic at n = 10 and an analytic standard error,
        # which is an O(1/n) effect and therefore of order 10 percent here; a quarter
        # is the right order of claim for it. The point of the test survives at any
        # tolerance: the two numbers are not interchangeable.
        self.assertLess(abs(ratio / predicted - 1.0), 0.25)
        self.assertGreater(ratio, 4.0)
        # Rescaling York by sqrt(MSWD) does not turn it into the jackknife either.
        rescaled = self.york.slope_stderr * predicted
        self.assertGreater(abs(rescaled / self.deming.slope_stderr - 1.0), 0.10)


class FiellerAgainstBruteForce(unittest.TestCase):
    """The closed-form set against a literal grid inversion of its definition.

    The grid side recomputes the coefficients and the moments from the raw x and y
    (see `least_squares_moments`), so a wrong Sxx or a wrong residual mean square in
    the module moves only one side of the comparison. What it still cannot validate is
    the *classification* of the branches, because both sides share the defining
    inequality -- that is what `FiellerCoverage` is for, and it is why both tests are
    present.
    """

    @staticmethod
    def _series_with_noise(depletion_fraction, n_points, sigma, seed):
        xs, truth = demo_line(depletion_fraction, n_points)
        rng = random.Random(seed)
        return xs, tuple(v + rng.gauss(0.0, sigma) for v in truth)

    def test_bounded_branch(self):
        for depletion, seed in ((0.50, 101), (0.10, 102), (0.06, 103)):
            with self.subTest(depletion=depletion):
                fit_x, fit_y = self._series_with_noise(depletion, 12, 25.0, seed)
                fit = ols_line(fit_x, fit_y)
                result = x_intercept_fieller(fit, confidence=0.95)
                self.assertEqual(result.kind, FIELLER_BOUNDED)
                self.assertTrue(result.bounded)
                pieces = brute_force_fieller_set(fit_x, fit_y, confidence=0.95, span=60.0, samples=240001)
                self.assertEqual(len(pieces), 1)
                self.assertAlmostEqual(pieces[0][0], result.lower, places=3)
                self.assertAlmostEqual(pieces[0][1], result.upper, places=3)
                self.assertTrue(result.contains(result.point_estimate))

    def test_exclusive_branch_is_two_half_lines(self):
        # Low signal-to-noise: 8 surveys over only 5 percent depletion with a 300 psia
        # gauge. The slope stops being significant and the set inverts.
        xs, ys = self._series_with_noise(0.05, 8, 300.0, 2024)
        fit = ols_line(xs, ys)
        result = x_intercept_fieller(fit, confidence=0.95)
        self.assertEqual(result.kind, FIELLER_EXCLUSIVE)
        self.assertFalse(result.bounded)
        self.assertGreater(result.g, 1.0)
        self.assertGreater(result.discriminant, 0.0)
        # The point estimate lies OUTSIDE the excluded middle, always.
        self.assertFalse(result.lower < result.point_estimate < result.upper)
        self.assertTrue(result.contains(result.point_estimate))

        span = 5000.0
        pieces = brute_force_fieller_set(xs, ys, confidence=0.95, span=span, samples=400001)
        self.assertEqual(len(pieces), 2, "the set must come back as two disjoint pieces")
        # The inner edges of the two pieces are the bounds of the excluded middle.
        self.assertAlmostEqual(pieces[0][1], result.lower, places=1)
        self.assertAlmostEqual(pieces[1][0], result.upper, places=1)

    def test_whole_line_branch(self):
        # Force discriminant <= 0 by putting the point estimate essentially on top of
        # the abscissa mean while the slope carries no significance: then D ~ 0 and
        # Delta = g D**2 + (1-g) k is negative because g > 1.
        xs = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0)
        centre = sum(xs) / len(xs)
        rng = random.Random(77)
        ys = tuple(-0.02 * (xi - centre) + rng.gauss(0.0, 30.0) for xi in xs)
        fit = ols_line(xs, ys)
        result = x_intercept_fieller(fit, confidence=0.95)
        self.assertEqual(result.kind, FIELLER_WHOLE_LINE)
        self.assertFalse(result.bounded)
        self.assertGreater(result.g, 1.0)
        self.assertLessEqual(result.discriminant, 0.0)
        self.assertEqual(result.lower, float("-inf"))
        self.assertEqual(result.upper, float("inf"))
        self.assertTrue(result.contains(-1.0e9))
        self.assertTrue(result.contains(1.0e9))
        pieces = brute_force_fieller_set(xs, ys, confidence=0.95, span=1.0e4, samples=20001)
        self.assertEqual(len(pieces), 1)
        self.assertAlmostEqual(pieces[0][0], -1.0e4 + result.point_estimate, places=6)


# --------------------------------------------------------------------------
# C7.2 Limiting case
# --------------------------------------------------------------------------


class ExactlyDeterminedLine(unittest.TestCase):
    """Points lying exactly on a line must be recovered to machine precision."""

    def setUp(self):
        # Chosen so slope and intercept are exactly representable in binary.
        self.xs = (0.0, 2.0, 4.0, 8.0, 16.0, 32.0)
        self.slope = -0.25
        self.intercept = 12.5
        self.ys = tuple(self.intercept + self.slope * v for v in self.xs)

    def test_ols_recovers_the_line_exactly(self):
        fit = ols_line(self.xs, self.ys)
        self.assertEqual(fit.slope, self.slope)
        self.assertEqual(fit.intercept, self.intercept)
        self.assertEqual(max(abs(r) for r in fit.residuals), 0.0)
        self.assertEqual(fit.residual_variance, 0.0)
        self.assertEqual(fit.slope_stderr, 0.0)
        self.assertEqual(fit.intercept_stderr, 0.0)
        self.assertEqual(fit.covariance, 0.0)
        self.assertEqual(fit.r_squared, 1.0)
        self.assertEqual(fit.n_points, 6)
        self.assertEqual(fit.degrees_of_freedom, 4)

    def test_x_intercept_of_an_exact_line_is_exact_and_certain(self):
        estimate = x_intercept(ols_line(self.xs, self.ys))
        self.assertEqual(estimate.value, 50.0)  # 12.5 / 0.25
        self.assertEqual(estimate.stderr, 0.0)
        self.assertEqual(estimate.fieller_g, 0.0)
        self.assertEqual(estimate.warnings, ())

    def test_deming_and_york_recover_the_same_exact_line(self):
        n = len(self.xs)
        deming = deming_line(self.xs, self.ys, error_variance_ratio=3.7)
        york = york_line(self.xs, self.ys, x_std=(0.5,) * n, y_std=(0.9,) * n)
        for fit in (deming, york):
            with self.subTest(method=fit.method):
                self.assertAlmostEqual(fit.slope, self.slope, places=13)
                self.assertAlmostEqual(fit.intercept, self.intercept, places=12)

    def test_noise_free_demo_line_returns_the_gas_in_place_it_was_built_from(self):
        xs, ys = demo_line(0.5, 12)
        estimate = x_intercept(ols_line(xs, ys))
        self.assertAlmostEqual(estimate.value, DEMO_GAS_IN_PLACE, places=10)


class WeightedReducesToUnweighted(unittest.TestCase):
    """Equal weights must return the unweighted fit, for any common weight value."""

    def test_unit_weights(self):
        plain = ols_line(ANSCOMBE_X, ANSCOMBE_Y1)
        weighted = ols_line(ANSCOMBE_X, ANSCOMBE_Y1, weights=(1.0,) * len(ANSCOMBE_X))
        self.assertEqual(weighted.slope, plain.slope)
        self.assertEqual(weighted.intercept, plain.intercept)
        self.assertEqual(weighted.slope_stderr, plain.slope_stderr)
        self.assertEqual(weighted.intercept_stderr, plain.intercept_stderr)
        self.assertEqual(weighted.covariance, plain.covariance)
        self.assertEqual(weighted.method, "wls")
        self.assertEqual(plain.method, "ols")

    def test_a_common_non_unit_weight_cancels_out_of_every_standard_error(self):
        # Weights are relative: the residual mean square scales with them and the
        # leverage scales with them, so both Var(b) and Var(a) are invariant.
        plain = ols_line(ANSCOMBE_X, ANSCOMBE_Y1)
        for common in (0.001, 17.0, 4096.0):
            with self.subTest(weight=common):
                weighted = ols_line(ANSCOMBE_X, ANSCOMBE_Y1, weights=(common,) * len(ANSCOMBE_X))
                self.assertAlmostEqual(weighted.slope, plain.slope, places=14)
                self.assertAlmostEqual(weighted.intercept, plain.intercept, places=13)
                self.assertAlmostEqual(weighted.slope_stderr, plain.slope_stderr, places=14)
                self.assertAlmostEqual(weighted.intercept_stderr, plain.intercept_stderr, places=13)
                self.assertAlmostEqual(weighted.r_squared, plain.r_squared, places=14)

    def test_a_heavier_weight_pulls_the_line_towards_that_point(self):
        xs = (0.0, 1.0, 2.0, 3.0)
        ys = (0.0, 1.0, 2.0, 10.0)
        plain = ols_line(xs, ys)
        heavy_last = ols_line(xs, ys, weights=(1.0, 1.0, 1.0, 100.0))
        self.assertGreater(heavy_last.slope, plain.slope)


class DemingLimits(unittest.TestCase):
    """The variance ratio's two limits, which are the convention's definition.

    lambda is V(x-error) / V(y-error). So lambda -> 0 means an error-free abscissa and
    must return the OLS slope Sxy/Sxx, while lambda -> infinity means an error-free
    ordinate and must return the x-on-y slope Syy/Sxy. Getting the convention backwards
    swaps these two, which is why both are asserted rather than one.
    """

    def setUp(self):
        n = len(NCSS_X)
        x_mean = sum(NCSS_X) / n
        y_mean = sum(NCSS_Y) / n
        self.sxx = sum((v - x_mean) ** 2 for v in NCSS_X)
        self.sxy = sum((a - x_mean) * (b - y_mean) for a, b in zip(NCSS_X, NCSS_Y, strict=True))
        self.syy = sum((v - y_mean) ** 2 for v in NCSS_Y)

    def test_zero_ratio_limit_returns_the_ols_slope_to_ten_significant_figures(self):
        # Ten figures, not six. The direct quadratic form loses all but five here
        # through catastrophic cancellation, so demanding ten is exactly the assertion
        # that the numerically stable conjugate branch is the one that ran.
        ols_slope = self.sxy / self.sxx
        self.assertAlmostEqual(ols_slope, 0.8616233847697906, places=13)
        limit = deming_line(NCSS_X, NCSS_Y, error_variance_ratio=1.0e-12).slope
        self.assertLess(abs(limit / ols_slope - 1.0), 1.0e-10)

    def test_infinite_ratio_limit_returns_the_x_on_y_slope(self):
        reciprocal_slope = self.syy / self.sxy
        self.assertAlmostEqual(reciprocal_slope, 1.041642399534071, places=12)
        limit = deming_line(NCSS_X, NCSS_Y, error_variance_ratio=1.0e12).slope
        self.assertLess(abs(limit / reciprocal_slope - 1.0), 1.0e-10)

    def test_unit_ratio_minimises_the_perpendicular_distances(self):
        # lambda = 1 is orthogonal regression, so the returned line must minimise the
        # sum of squared PERPENDICULAR distances. Checking that against the major-axis
        # quadratic root would be checking the module's own formula against itself --
        # the same expression retyped on both sides. So the reference here is a
        # general-purpose 1-D minimiser run directly on the perpendicular objective,
        #     R(b) = sum (y_i - a - b x_i)**2 / (1 + b**2),   a = ybar - b xbar,
        # which shares no algebra with the closed form. (The optimal line passes
        # through the centroid: dR/da = 0 gives a = ybar - b xbar for any b.)
        n = len(NCSS_X)
        x_mean = sum(NCSS_X) / n
        y_mean = sum(NCSS_Y) / n

        def perpendicular_sum_of_squares(slope):
            intercept = y_mean - slope * x_mean
            return sum((b - intercept - slope * a) ** 2 for a, b in zip(NCSS_X, NCSS_Y, strict=True)) / (
                1.0 + slope * slope
            )

        # R(b) has exactly two stationary points, the two principal axes at b and -1/b,
        # so any bracket confined to the positive half-line holds only the minimum.
        # The bracket [0.1, 10] is set from that structural fact, not from the answer.
        reference = golden_section_minimum(perpendicular_sum_of_squares, 0.1, 10.0, width=1.0e-10)
        slope = deming_line(NCSS_X, NCSS_Y, error_variance_ratio=1.0).slope

        # A 1-D minimiser locates a smooth quadratic minimum only to about
        # sqrt(machine epsilon) ~ 1.5e-8 in the argument, because the objective changes
        # by less than one ulp over any shorter interval no matter how far the bracket
        # is shrunk. 1e-6 relative is two orders looser than that floor and still four
        # orders tighter than the ~1e-2 slope shift a wrong lambda substitution gives.
        self.assertLess(abs(slope / reference - 1.0), 1.0e-6)
        # The tolerance-free half of the claim: the closed form must sit at least as
        # low on the objective as the numerical search does. One ulp of the objective
        # is 1e-16 relative, so 1e-12 is a wide margin around exact equality while
        # still excluding any real disagreement, which would show up at 1e-8 or worse.
        exact_value = perpendicular_sum_of_squares(slope)
        search_value = perpendicular_sum_of_squares(reference)
        self.assertLessEqual(exact_value, search_value * (1.0 + 1.0e-12))


class YorkLimits(unittest.TestCase):
    """York's documented special cases, stated as conditions on the INPUT weights."""

    def test_constant_weights_and_zero_correlation_equal_deming(self):
        # This is the correct statement of the special case: the condition is on
        # omega(X) and omega(Y), which are inputs, not on the derived effective weight.
        n = len(NCSS_X)
        for ratio in (0.25, 1.0, 4.0, 9.0):
            with self.subTest(ratio=ratio):
                york = york_line(
                    NCSS_X,
                    NCSS_Y,
                    x_std=(math.sqrt(ratio),) * n,
                    y_std=(1.0,) * n,
                )
                deming = deming_line(NCSS_X, NCSS_Y, error_variance_ratio=ratio)
                self.assertAlmostEqual(york.slope, deming.slope, places=13)
                self.assertAlmostEqual(york.intercept, deming.intercept, places=12)

    def test_a_negligible_abscissa_error_recovers_weighted_least_squares(self):
        # omega(X) -> infinity with r = 0 makes the effective weight collapse to
        # omega(Y), i.e. weighted y-on-x least squares.
        n = len(NCSS_X)
        y_std = tuple(0.5 + 0.1 * i for i in range(n))
        york = york_line(NCSS_X, NCSS_Y, x_std=(1.0e-7,) * n, y_std=y_std)
        wls = ols_line(NCSS_X, NCSS_Y, weights=tuple(1.0 / s**2 for s in y_std))
        self.assertAlmostEqual(york.slope, wls.slope, places=9)
        self.assertAlmostEqual(york.intercept, wls.intercept, places=8)

    def test_converges_quickly_from_the_ols_start(self):
        fit = york_line(YORK_X, YORK_Y, x_std=YORK_X_STD, y_std=YORK_Y_STD)
        self.assertTrue(fit.converged)
        # An iteration count is a property of the tolerance and the starting point, not
        # of the data, so only a loose budget is asserted, never an exact count.
        self.assertLess(fit.iterations, 50)


class FiellerApproachesTheDeltaInterval(unittest.TestCase):
    """As g -> 0 the exact set must collapse onto the symmetric approximation."""

    def test_high_signal_case(self):
        xs, truth = demo_line(0.50, 12)
        rng = random.Random(31337)
        ys = tuple(v + rng.gauss(0.0, 25.0) for v in truth)
        fit = ols_line(xs, ys)
        exact = x_intercept_fieller(fit, confidence=0.95)
        estimate = x_intercept(fit)
        low, high = estimate.symmetric_interval(0.95)

        self.assertEqual(exact.kind, FIELLER_BOUNDED)
        self.assertLess(exact.g, 0.002)
        self.assertLess(abs(exact.lower / low - 1.0), 0.002)
        self.assertLess(abs(exact.upper / high - 1.0), 0.002)
        # The exact set is still asymmetric, and in the direction the algebra demands:
        # the half-widths are (sqrt(Delta) +/- g*D)/(1-g) with D = x0 - xbar > 0 for a
        # depleting reservoir, so the upper side is the longer one. It is small here
        # but it is not zero, which is exactly why the symmetric interval is an
        # approximation rather than a rearrangement.
        upper_half = exact.upper - exact.point_estimate
        lower_half = exact.point_estimate - exact.lower
        self.assertGreater(upper_half, lower_half)
        self.assertLess(upper_half / lower_half - 1.0, 0.05)


class BootstrapLimitingCases(unittest.TestCase):
    """Block length 1 is the i.i.d. pairs bootstrap; independent data cannot tell them apart."""

    @staticmethod
    def _statistic(xs, ys):
        return x_intercept(ols_line(xs, ys)).value

    def test_block_one_on_independent_data_matches_the_true_sampling_spread(self):
        # The quantity a bootstrap standard error estimates is the spread of the
        # statistic over repetitions of the experiment, so that spread -- not the
        # analytic formula, and not a single bootstrap draw -- is what it is compared
        # against here. Both are built for the same design, n = 40 surveys over half of
        # G with an independent 25 psia gauge error.
        sigma = 25.0
        trials = 1200
        realisations = 12
        xs, truth = demo_line(0.5, 40)

        rng = random.Random(987654)
        values = []
        for _ in range(trials):
            ys = tuple(v + rng.gauss(0.0, sigma) for v in truth)
            values.append(self._statistic(xs, ys))
        mean = math.fsum(values) / trials
        true_sd = math.sqrt(math.fsum((v - mean) ** 2 for v in values) / (trials - 1))

        # First an oracle for the truth itself: with independent errors the closed-form
        # inverse-prediction standard deviation applies, evaluated on the noise-free
        # line with the known sigma, so it is a prediction made before the simulation.
        m = least_squares_moments(xs, truth)
        analytic = (sigma / abs(m["slope"])) * math.sqrt(
            1.0 / len(xs) + (DEMO_GAS_IN_PLACE - m["x_mean"]) ** 2 / m["sxx"]
        )
        # The Monte Carlo error of an estimated standard deviation from N draws is
        # 1/sqrt(2N) = 2.0 percent here, so 7 percent is about three and a half of
        # those and leaves room for the ratio statistic's mild non-normality.
        self.assertLess(abs(true_sd / analytic - 1.0), 0.07)

        # Now the bootstrap. One bootstrap standard error is itself noisy -- measured
        # relative spread across independent realisations of this design is 0.22,
        # larger than the 1/sqrt(2n) = 0.11 of a fixed-design estimator because the
        # pairs bootstrap resamples the leverage as well -- so the gate is placed on
        # the average over twelve realisations, whose standard error is 0.22/sqrt(12)
        # = 0.065. A 20 percent bracket is three of those. Averaging also makes the
        # test sensitive to a systematic error, which a single draw at 35 percent was
        # not: a bootstrap wrong by a steady factor of 1.3 now fails.
        rng = random.Random(5)
        errors = []
        for index in range(realisations):
            ys = tuple(v + rng.gauss(0.0, sigma) for v in truth)
            result = moving_block_bootstrap(
                xs,
                ys,
                block_length=1,
                replicates=600,
                seed=9 + index,
                statistic=self._statistic,
            )
            self.assertEqual(result.block_length, 1)
            self.assertEqual(result.n_starts, len(xs))
            self.assertEqual(result.replicates_used + result.replicates_failed, 600)
            errors.append(result.standard_error)
        mean_error = math.fsum(errors) / realisations
        self.assertLess(abs(mean_error / true_sd - 1.0), 0.20)

    def test_percentile_interval_brackets_the_point_estimate(self):
        xs, truth = demo_line(0.5, 30)
        rng = random.Random(6)
        ys = tuple(v + rng.gauss(0.0, 25.0) for v in truth)
        result = moving_block_bootstrap(
            xs, ys, block_length=3, replicates=800, seed=11, statistic=self._statistic
        )
        low, high = result.percentile_interval(0.90)
        self.assertLess(low, result.point_estimate)
        self.assertGreater(high, result.point_estimate)
        self.assertLess(low, high)


# --------------------------------------------------------------------------
# C7.3 Invalid input -- every documented raise is exercised
# --------------------------------------------------------------------------


class OlsInvalidInput(unittest.TestCase):
    def test_mismatched_lengths(self):
        with self.assertRaises(InvalidInputError):
            ols_line((1.0, 2.0, 3.0), (1.0, 2.0))

    def test_too_few_points(self):
        with self.assertRaises(InvalidInputError):
            ols_line((1.0, 2.0), (1.0, 2.0))

    def test_non_finite_values(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                ols_line((1.0, 2.0, bad), (1.0, 2.0, 3.0))
        with self.assertRaises(InvalidInputError):
            ols_line((1.0, 2.0, 3.0), (1.0, 2.0, float("nan")))

    def test_non_numeric(self):
        with self.assertRaises(InvalidInputError):
            ols_line((1.0, 2.0, "three"), (1.0, 2.0, 3.0))

    def test_non_positive_weight(self):
        for bad in (0.0, -1.0):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                ols_line((1.0, 2.0, 3.0), (1.0, 2.0, 3.0), weights=(1.0, 1.0, bad))

    def test_weights_of_the_wrong_length(self):
        with self.assertRaises(InvalidInputError):
            ols_line((1.0, 2.0, 3.0), (1.0, 2.0, 3.0), weights=(1.0, 1.0))

    def test_identical_abscissae_is_not_identifiable(self):
        with self.assertRaises(NotIdentifiableError):
            ols_line((5.0, 5.0, 5.0), (1.0, 2.0, 3.0))


class DemingInvalidInput(unittest.TestCase):
    def test_non_positive_variance_ratio(self):
        for bad in (0.0, -1.0):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                deming_line(NCSS_X, NCSS_Y, error_variance_ratio=bad)

    def test_non_finite_variance_ratio(self):
        with self.assertRaises(InvalidInputError):
            deming_line(NCSS_X, NCSS_Y, error_variance_ratio=float("inf"))

    def test_zero_cross_product_is_not_identifiable(self):
        # Symmetric response: Sxy is exactly zero, and the Deming slope divides by it.
        with self.assertRaises(NotIdentifiableError):
            deming_line((0.0, 1.0, 2.0, 3.0), (1.0, 2.0, 2.0, 1.0), error_variance_ratio=1.0)

    def test_identical_abscissae_is_not_identifiable(self):
        with self.assertRaises(NotIdentifiableError):
            deming_line((5.0, 5.0, 5.0), (1.0, 2.0, 3.0), error_variance_ratio=1.0)


class DemingJackknifeRefusesWithoutMisdescribingTheData(unittest.TestCase):
    """A degenerate leave-one-out replicate must be reported as what it is.

    The delete-one jackknife evaluates the Deming coefficients on n subsets. A subset
    can be degenerate while the supplied series is not, and the refusal that comes back
    used to be the subset's own message: it named the subset's point count and asserted
    a cross product that is false of the caller's data. That sends an engineer looking
    for a fault in a series that `ols_line` and `york_line` fit without complaint.
    """

    def test_a_shut_in_shaped_series_names_the_replicate_not_the_series(self):
        # Three surveys during a shut-in and one after it. Two distinct abscissae is
        # all a line needs, and both other estimators fit it.
        xs = (1.0, 1.0, 1.0, 2.0)
        ys = (5.0, 4.8, 5.2, 3.0)
        self.assertAlmostEqual(ols_line(xs, ys).slope, -2.0, places=12)
        self.assertTrue(math.isfinite(york_line(xs, ys, x_std=(0.1,) * 4, y_std=(0.1,) * 4).slope))

        with self.assertRaises(NotIdentifiableError) as caught:
            deming_line(xs, ys, error_variance_ratio=1.0)
        message = str(caught.exception)
        # The offending object is the replicate that omits the last survey, and the
        # message has to identify it by index (contract C2) and say that the refusal is
        # about the standard error, not about the line.
        self.assertIn("index 3", message)
        self.assertIn("replicate", message)
        self.assertIn("jackknife", message)
        # It must not describe the caller's four-point series as having three
        # identical abscissae, which is what the unwrapped subset message did.
        self.assertNotIn("all 4 abscissae are identical", message)
        self.assertIn("these 4 points", message)

    def test_a_replicate_with_a_zero_cross_product_names_its_index_too(self):
        # Sxy of the supplied series is 37.4; Sxy of the subset that omits index 4 is
        # exactly zero. The old message claimed the cross product was zero "for these
        # data", which is false by a factor of infinity.
        xs = (0.0, 1.0, 2.0, 3.0, 10.0)
        ys = (1.0, 2.0, 2.0, 1.0, 7.0)
        x_mean = sum(xs) / len(xs)
        y_mean = sum(ys) / len(ys)
        sxy = sum((a - x_mean) * (b - y_mean) for a, b in zip(xs, ys, strict=True))
        self.assertGreater(abs(sxy), 1.0)
        self.assertTrue(math.isfinite(ols_line(xs, ys).slope))

        with self.assertRaises(NotIdentifiableError) as caught:
            deming_line(xs, ys, error_variance_ratio=1.0)
        message = str(caught.exception)
        self.assertIn("index 4", message)
        self.assertIn("replicate", message)

    def test_a_series_that_really_is_degenerate_still_says_so_directly(self):
        # The wrapping must not swallow the genuine case: when every abscissa is
        # identical the point estimate itself is unavailable and the message is about
        # the supplied data, with no replicate index in it.
        with self.assertRaises(NotIdentifiableError) as caught:
            deming_line((5.0, 5.0, 5.0), (1.0, 2.0, 3.0), error_variance_ratio=1.0)
        self.assertNotIn("replicate", str(caught.exception))


class YorkInvalidInput(unittest.TestCase):
    def setUp(self):
        self.n = len(NCSS_X)
        self.kw = dict(x_std=(0.2,) * self.n, y_std=(0.1,) * self.n)

    def test_non_positive_standard_deviation(self):
        for bad in (0.0, -0.1):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                york_line(NCSS_X, NCSS_Y, x_std=(bad,) * self.n, y_std=(0.1,) * self.n)
            with self.subTest(bad=bad, axis="y"), self.assertRaises(InvalidInputError):
                york_line(NCSS_X, NCSS_Y, x_std=(0.2,) * self.n, y_std=(bad,) * self.n)

    def test_standard_deviations_of_the_wrong_length(self):
        with self.assertRaises(InvalidInputError):
            york_line(NCSS_X, NCSS_Y, x_std=(0.2,) * 3, y_std=(0.1,) * self.n)

    def test_perfect_error_correlation_is_rejected(self):
        for bad in (1.0, -1.0, 1.5):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                york_line(NCSS_X, NCSS_Y, correlation=bad, **self.kw)

    def test_per_point_correlation_of_the_wrong_length(self):
        with self.assertRaises(InvalidInputError):
            york_line(NCSS_X, NCSS_Y, correlation=(0.1, 0.2), **self.kw)

    def test_bad_tolerance_and_budget(self):
        with self.assertRaises(InvalidInputError):
            york_line(NCSS_X, NCSS_Y, tolerance=0.0, **self.kw)
        with self.assertRaises(InvalidInputError):
            york_line(NCSS_X, NCSS_Y, max_iterations=0, **self.kw)

    def test_exhausted_budget_raises_rather_than_returning_the_last_iterate(self):
        with self.assertRaises(ConvergenceError) as caught:
            york_line(
                YORK_X,
                YORK_Y,
                x_std=YORK_X_STD,
                y_std=YORK_Y_STD,
                tolerance=1.0e-15,
                max_iterations=2,
            )
        self.assertEqual(caught.exception.iterations, 2)
        self.assertIsNotNone(caught.exception.last_value)


class XInterceptInvalidInput(unittest.TestCase):
    def setUp(self):
        # Sxy is exactly zero for this symmetric response, so the OLS slope is 0.0.
        self.flat = ols_line((0.0, 1.0, 2.0, 3.0), (1.0, 2.0, 2.0, 1.0))
        self.assertEqual(self.flat.slope, 0.0)

    def test_zero_slope_has_no_x_intercept(self):
        with self.assertRaises(NotIdentifiableError):
            x_intercept(self.flat)
        with self.assertRaises(NotIdentifiableError):
            x_intercept_fieller(self.flat)
        with self.assertRaises(NotIdentifiableError):
            x_intercept_variance_collapsed(self.flat)

    def test_wrong_type(self):
        for function in (x_intercept, x_intercept_fieller, x_intercept_variance_collapsed):
            with self.subTest(function=function.__name__), self.assertRaises(InvalidInputError):
                function("not a fit")

    def test_bad_confidence(self):
        fit = ols_line(*demo_line(0.5, 12))
        for bad in (0.0, 1.0, -0.1, 1.5, float("nan")):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                x_intercept_fieller(fit, confidence=bad)
        with self.assertRaises(InvalidInputError):
            x_intercept(fit).symmetric_interval(0.0)

    def test_fieller_refuses_an_errors_in_variables_fit(self):
        n = len(NCSS_X)
        for fit in (
            deming_line(NCSS_X, NCSS_Y, error_variance_ratio=4.0),
            york_line(NCSS_X, NCSS_Y, x_std=(0.2,) * n, y_std=(0.1,) * n),
        ):
            with self.subTest(method=fit.method), self.assertRaises(InvalidInputError):
                x_intercept_fieller(fit)

    def test_collapsed_form_refuses_a_non_least_squares_fit(self):
        with self.assertRaises(InvalidInputError):
            x_intercept_variance_collapsed(deming_line(NCSS_X, NCSS_Y, error_variance_ratio=4.0))

    def test_mswd_refuses_a_relative_weight_fit(self):
        # InvalidInputError, not NotIdentifiableError. Nothing is wrong with the data:
        # a chi-square is undefined for a method fitted with relative weights, so this
        # is the caller asking the wrong object, which is the row the contract's
        # exception table (C3) assigns to InvalidInputError. Keeping the two distinct
        # is what lets a caller tell "your surveys cannot support this" apart from
        # "you asked for something this fit never computed".
        for fit in (
            ols_line(NCSS_X, NCSS_Y),
            deming_line(NCSS_X, NCSS_Y, error_variance_ratio=4.0),
        ):
            with self.subTest(method=fit.method), self.assertRaises(InvalidInputError):
                _ = fit.mswd
        # York carries absolute weights, so the same property answers there.
        n = len(NCSS_X)
        york = york_line(NCSS_X, NCSS_Y, x_std=(0.2,) * n, y_std=(0.1,) * n)
        self.assertGreater(york.mswd, 0.0)


class StudentTInvalidInput(unittest.TestCase):
    def test_probability_outside_the_open_unit_interval(self):
        for bad in (0.0, 1.0, -0.5, 2.0, float("nan")):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                student_t_quantile(bad, 8)

    def test_non_positive_degrees_of_freedom(self):
        for bad in (0.0, -3.0):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                student_t_quantile(0.975, bad)


class BootstrapInvalidInput(unittest.TestCase):
    @staticmethod
    def _statistic(xs, ys):
        return x_intercept(ols_line(xs, ys)).value

    def setUp(self):
        self.xs, self.ys = demo_line(0.5, 12)
        self.kw = dict(replicates=10, seed=1, statistic=self._statistic)

    def test_block_length_out_of_range(self):
        # 12 is the series length: a block that long leaves one possible start, so
        # every resample is the original data and the reported standard error is
        # rounding noise around zero. Refused for the same reason as 0 and 13.
        for bad in (0, -1, 12, 13):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                moving_block_bootstrap(self.xs, self.ys, block_length=bad, **self.kw)

    def test_the_longest_admissible_block_still_resamples(self):
        # n - 1 is admissible and must still produce spread: two starts, so the
        # resample distribution has more than one atom.
        result = moving_block_bootstrap(
            self.xs,
            self.ys,
            block_length=len(self.xs) - 1,
            replicates=40,
            seed=1,
            statistic=self._statistic,
        )
        self.assertEqual(result.n_starts, 2)
        self.assertGreater(len(set(result.values)), 1)
        self.assertGreater(result.standard_error, 0.0)

    def test_block_length_must_be_an_integer(self):
        with self.assertRaises(InvalidInputError):
            moving_block_bootstrap(self.xs, self.ys, block_length=3.0, **self.kw)

    def test_replicates_must_be_a_positive_integer(self):
        for bad in (0, -5, 2.5):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                moving_block_bootstrap(
                    self.xs,
                    self.ys,
                    block_length=3,
                    replicates=bad,
                    seed=1,
                    statistic=self._statistic,
                )

    def test_seed_must_be_an_integer(self):
        with self.assertRaises(InvalidInputError):
            moving_block_bootstrap(
                self.xs,
                self.ys,
                block_length=3,
                replicates=10,
                seed=1.5,
                statistic=self._statistic,
            )

    def test_statistic_must_be_callable(self):
        with self.assertRaises(InvalidInputError):
            moving_block_bootstrap(self.xs, self.ys, block_length=3, replicates=10, seed=1, statistic=42)

    def test_statistic_returning_a_non_finite_value(self):
        with self.assertRaises(InvalidInputError):
            moving_block_bootstrap(
                self.xs,
                self.ys,
                block_length=3,
                replicates=10,
                seed=1,
                statistic=lambda _xs, _ys: float("nan"),
            )

    def test_when_no_replicate_yields_a_value_the_call_refuses(self):
        # A statistic that succeeds on the ordered series but refuses on anything else.
        # Every block resample then fails, and the result would have no measurable
        # spread, so the call must raise rather than return a standard error of zero.
        original = self.xs

        def only_the_original(xs, _ys):
            if xs != original:
                raise NotIdentifiableError("resample is not the original series")
            return 1.0

        with self.assertRaises(NotIdentifiableError):
            moving_block_bootstrap(
                self.xs,
                self.ys,
                block_length=3,
                replicates=20,
                seed=1,
                statistic=only_the_original,
            )

    def test_partial_failures_are_counted_and_excluded(self):
        # Refuse any resample that leaves out the last survey. Some draws do, some do
        # not, so the result must report both counts and compute its spread from the
        # survivors alone -- never by redrawing until the statistic succeeds, which
        # would quietly bias the resampling distribution.
        last = self.xs[-1]

        def refuse_without_the_last_point(xs, ys):
            if last not in xs:
                raise NotIdentifiableError("resample omits the final survey")
            return x_intercept(ols_line(xs, ys)).value

        result = moving_block_bootstrap(
            self.xs,
            self.ys,
            block_length=3,
            replicates=200,
            seed=1,
            statistic=refuse_without_the_last_point,
        )
        self.assertGreater(result.replicates_failed, 0)
        self.assertGreater(result.replicates_used, 1)
        self.assertEqual(result.replicates_used + result.replicates_failed, 200)
        self.assertEqual(len(result.values), result.replicates_used)

    def test_a_non_package_exception_from_the_statistic_propagates(self):
        class MarkerError(Exception):
            pass

        def explode(_xs, _ys):
            raise MarkerError

        with self.assertRaises(MarkerError):
            moving_block_bootstrap(self.xs, self.ys, block_length=3, replicates=5, seed=1, statistic=explode)


class BlockLengthAdviceInvalidInput(unittest.TestCase):
    def test_too_few_residuals(self):
        with self.assertRaises(InvalidInputError):
            suggested_block_length((1.0, -1.0))

    def test_zero_variance_residuals(self):
        with self.assertRaises(NotIdentifiableError):
            suggested_block_length((2.0,) * 10)


# --------------------------------------------------------------------------
# C7.4 Property and invariant
# --------------------------------------------------------------------------


class DeltaMethodMonteCarlo(unittest.TestCase):
    """Check the delta-method standard error against realised Monte Carlo scatter.

    This is the headline test: does the reported uncertainty describe reality?

    Twenty thousand realisations of a known p/Z line with known Gaussian noise. The
    Monte Carlo standard deviation of the fitted x-intercept is the truth; the
    delta-method standard error must reproduce it, and the covariance-dropping version
    must fail to. The contrast is the whole point. A defective estimator that only
    over-states uncertainty is invisible to every other kind of check.
    """

    TRIALS = 20000
    SIGMA = 25.0

    def setUp(self):
        self.xs, self.truth = demo_line(0.5, 12)

    def test_monte_carlo_agrees_with_the_covariance_bearing_delta_method(self):
        rng = random.Random(20240913)
        values = []
        reported = []
        reported_wrong = []
        for _ in range(self.TRIALS):
            ys = tuple(v + rng.gauss(0.0, self.SIGMA) for v in self.truth)
            fit = ols_line(self.xs, ys)
            estimate = x_intercept(fit)
            values.append(estimate.value)
            reported.append(estimate.stderr)
            reported_wrong.append(wrong_x_intercept_stderr(fit))
        mean = math.fsum(values) / self.TRIALS
        observed = math.sqrt(math.fsum((v - mean) ** 2 for v in values) / (self.TRIALS - 1))
        mean_reported = math.fsum(reported) / self.TRIALS
        mean_reported_wrong = math.fsum(reported_wrong) / self.TRIALS

        # The predicted standard error is evaluated on the noise-free line with the
        # known sigma substituted for the estimated s, so it is a prediction made
        # before the simulation rather than an average of its output.
        noise_free = ols_line(self.xs, self.truth)
        predicted = (self.SIGMA / abs(noise_free.slope)) * math.sqrt(
            1.0 / noise_free.n_points
            + (DEMO_GAS_IN_PLACE - noise_free.x_mean) ** 2 / noise_free.sum_squared_x_deviations
        )
        wrong = math.sqrt(
            (
                self.SIGMA**2
                * (1.0 / noise_free.n_points + noise_free.x_mean**2 / noise_free.sum_squared_x_deviations)
                + DEMO_GAS_IN_PLACE**2 * self.SIGMA**2 / noise_free.sum_squared_x_deviations
            )
            / noise_free.slope**2
        )

        # The correct estimator agrees to within Monte Carlo error. With 20000 trials
        # the standard error of an estimated standard deviation is about 1/sqrt(2N),
        # i.e. 0.5 percent, so 3 percent is a comfortable but not vacuous bracket.
        self.assertLess(abs(observed / predicted - 1.0), 0.03)
        # The covariance-dropping version over-states by about 36 percent and is
        # nowhere near. If this assertion ever starts failing because the two agree,
        # the covariance term has been deleted from the module.
        self.assertGreater(wrong / predicted, 1.30)
        self.assertGreater(abs(observed / wrong - 1.0), 0.20)

        # The same comparison against what the module actually reports, trial by trial,
        # rather than against the closed form written out above. The average reported
        # standard error must track the realised scatter; the covariance-dropping
        # average must not.
        self.assertLess(abs(mean_reported / observed - 1.0), 0.03)
        self.assertGreater(mean_reported_wrong / observed, 1.30)

    def test_the_module_reproduces_the_predicted_standard_error_on_one_realisation(self):
        # Same prediction, now flowing through the public API with s estimated from a
        # single realisation instead of sigma being known.
        rng = random.Random(4242)
        ys = tuple(v + rng.gauss(0.0, self.SIGMA) for v in self.truth)
        fit = ols_line(self.xs, ys)
        estimate = x_intercept(fit)
        hand = (math.sqrt(fit.residual_variance) / abs(fit.slope)) * math.sqrt(
            1.0 / fit.n_points + (estimate.value - fit.x_mean) ** 2 / fit.sum_squared_x_deviations
        )
        self.assertAlmostEqual(estimate.stderr, hand, places=12)
        self.assertGreater(wrong_x_intercept_stderr(fit) / estimate.stderr, 1.30)


class InversePredictionVarianceAgainstHandComputedMoments(unittest.TestCase):
    """The x-intercept variance against the classical closed form, rebuilt from the data.

    Comparing `x_intercept().stderr**2` against `x_intercept_variance_collapsed()`
    alone proves very little: both read `residual_variance`, `weight_total`, `x_mean`
    and `sum_squared_x_deviations` off the same `LineFit`, so a wrong Sxx or a wrong
    residual mean square moves both sides together and the comparison stays green. The
    reference here is therefore the classical weighted inverse-prediction variance

        Var(x0) = (s**2 / b**2) [1/W + (x0 - xbar)**2 / Sxx]

    with every ingredient recomputed from x, y and the weights by
    `least_squares_moments`. Both module paths are then checked against something
    external to the fit object, and against each other as well.
    """

    def test_ols_and_wls_over_several_shapes(self):
        rng = random.Random(808)
        for depletion in (0.08, 0.20, 0.50, 0.90):
            xs, truth = demo_line(depletion, 14)
            ys = tuple(v + rng.gauss(0.0, 20.0) for v in truth)
            weights = tuple(0.5 + rng.random() for _ in xs)
            for fit_weights in (None, weights):
                fit = ols_line(xs, ys, weights=fit_weights)
                with self.subTest(depletion=depletion, method=fit.method):
                    m = least_squares_moments(xs, ys, fit_weights)
                    value = -m["intercept"] / m["slope"]
                    reference = (m["residual_variance"] / m["slope"] ** 2) * (
                        1.0 / m["weight_total"] + (value - m["x_mean"]) ** 2 / m["sxx"]
                    )
                    # The two sides are the same algebra over the same fourteen points,
                    # so they differ only by the order of the floating-point operations:
                    # a relative 1e-12 is many orders above that and would still catch
                    # a dropped covariance term, which changes the answer by tens of
                    # percent (see DeltaMethodMonteCarlo).
                    general = x_intercept(fit).stderr ** 2
                    collapsed = x_intercept_variance_collapsed(fit)
                    self.assertLess(abs(general / reference - 1.0), 1.0e-12)
                    self.assertLess(abs(collapsed / reference - 1.0), 1.0e-12)


class EquivarianceIdentities(unittest.TestCase):
    """Structural identities that hold exactly for any correct implementation.

    These are properties of the estimator's equivariance group, not of any particular
    formula, so they hold for any data and any noise realisation. They cost nothing and
    need no reference values.
    """

    def setUp(self):
        xs, truth = demo_line(0.45, 15)
        rng = random.Random(2718)
        self.xs = xs
        self.ys = tuple(v + rng.gauss(0.0, 18.0) for v in truth)
        self.base = x_intercept(ols_line(self.xs, self.ys)).value

    def test_a_pure_gauge_gain_cannot_move_the_x_intercept(self):
        # y -> (1+gamma) y scales both coefficients equally, so their ratio is exactly
        # unchanged. A multiplicative calibration error contributes nothing to G.
        gamma = 0.037
        scaled = tuple((1.0 + gamma) * v for v in self.ys)
        self.assertAlmostEqual(x_intercept(ols_line(self.xs, scaled)).value, self.base, places=11)

    def test_an_abscissa_offset_shifts_the_x_intercept_one_for_one(self):
        offset = 3.0
        shifted = tuple(v + offset for v in self.xs)
        self.assertAlmostEqual(x_intercept(ols_line(shifted, self.ys)).value, self.base + offset, places=10)

    def test_an_abscissa_gain_scales_the_x_intercept_proportionally(self):
        gain = 1.02
        scaled = tuple(gain * v for v in self.xs)
        self.assertAlmostEqual(x_intercept(ols_line(scaled, self.ys)).value, self.base * gain, places=10)

    def test_feeding_psig_for_psia_biases_the_gas_in_place_downward(self):
        # A shared additive offset c on the ordinate moves the x-intercept by exactly
        # c/b. Since psig = psia - 14.696 the offset is negative and the slope is
        # negative, so the shift is negative: a psig mistake makes a reservoir look
        # SMALLER, not larger. The sign is asserted, not only the magnitude -- a
        # magnitude-only assertion would pass under the inverted claim.
        offset = -14.696
        shifted = tuple(v + offset for v in self.ys)
        fit = ols_line(self.xs, self.ys)
        moved = x_intercept(ols_line(self.xs, shifted)).value
        # y -> y + c leaves b alone and sends a -> a + c, so x0 = -a/b moves by -c/b.
        self.assertAlmostEqual(moved - self.base, -offset / fit.slope, places=10)
        self.assertLess(moved, self.base)

        # On the noise-free demo line the shift is exactly -14.696*G/(p_i/Z_i).
        clean_x, clean_y = demo_line(0.5, 12)
        clean = x_intercept(ols_line(clean_x, clean_y)).value
        dirty = x_intercept(ols_line(clean_x, tuple(v + offset for v in clean_y))).value
        expected = -14.696 * DEMO_GAS_IN_PLACE / DEMO_INITIAL_P_OVER_Z
        self.assertAlmostEqual(dirty - clean, expected, places=9)
        self.assertAlmostEqual(expected, -0.31229, places=5)

    def test_rescaling_the_abscissa_leaves_the_physical_answer_invariant(self):
        # Gp expressed in scf rather than Bscf: G in physical units is unchanged, but
        # the Deming variance ratio that describes the same physical errors changes by
        # 1e18. That is why error_variance_ratio has no default.
        scale = 1.0e9
        big_x = tuple(v * scale for v in self.xs)
        small = deming_line(self.xs, self.ys, error_variance_ratio=4.0e-4)
        big = deming_line(big_x, self.ys, error_variance_ratio=4.0e-4 * scale**2)
        small_g = -small.intercept / small.slope
        big_g = -big.intercept / big.slope
        self.assertAlmostEqual(big_g / scale / small_g, 1.0, places=10)

    def test_york_is_symmetric_under_an_axis_swap(self):
        n = len(self.xs)
        x_std = (0.6,) * n
        y_std = (12.0,) * n
        forward = york_line(self.xs, self.ys, x_std=x_std, y_std=y_std)
        backward = york_line(self.ys, self.xs, x_std=y_std, y_std=x_std)
        self.assertAlmostEqual(backward.slope, 1.0 / forward.slope, places=10)
        self.assertAlmostEqual(backward.intercept, -forward.intercept / forward.slope, places=8)


class FiellerCoverage(unittest.TestCase):
    """Check calibration rather than algebra: the set must cover at its nominal rate.

    Grid inversion cannot test the branch classification, because both sides share the
    defining inequality. Coverage can, because the truth is the simulated gas in place
    and mishandling the two-half-line case necessarily *inflates* coverage above
    nominal. The bracket asserted below excludes the value that the "g >= 1 means the
    whole line" shortcut produces, so this test fails loudly if the exclusive branch is
    dropped.
    """

    TRIALS = 20000
    SIGMA = 300.0

    def test_low_signal_to_noise_coverage(self):
        xs, truth = demo_line(0.05, 8)
        rng = random.Random(20240913)
        dof = len(xs) - 2
        # Evaluate the critical value once: it depends only on the degrees of freedom.
        t = student_t_quantile(0.975, dof)

        exact_hits = naive_hits = delta_hits = 0
        unbounded = 0
        all_discriminants_positive = True
        for _ in range(self.TRIALS):
            ys = tuple(v + rng.gauss(0.0, self.SIGMA) for v in truth)
            fit = ols_line(xs, ys)
            result = x_intercept_fieller(fit, confidence=0.95)

            if result.bounded:
                if result.lower <= DEMO_GAS_IN_PLACE <= result.upper:
                    exact_hits += 1
                    naive_hits += 1
            else:
                unbounded += 1
                if result.kind == FIELLER_EXCLUSIVE:
                    all_discriminants_positive &= result.discriminant > 0.0
                    if not result.lower < DEMO_GAS_IN_PLACE < result.upper:
                        exact_hits += 1
                else:
                    exact_hits += 1
                # The naive shortcut scores every unbounded case as a hit.
                naive_hits += 1

            value = -fit.intercept / fit.slope
            half = t * math.sqrt(
                (fit.intercept_stderr**2 + value * value * fit.slope_stderr**2 + 2.0 * value * fit.covariance)
                / fit.slope**2
            )
            if value - half <= DEMO_GAS_IN_PLACE <= value + half:
                delta_hits += 1

        exact = exact_hits / self.TRIALS
        naive = naive_hits / self.TRIALS
        delta = delta_hits / self.TRIALS
        unbounded_fraction = unbounded / self.TRIALS

        # Fieller is an exact method, so anything systematically above nominal is a bug
        # rather than conservatism, and the bracket is therefore centred on the nominal
        # 0.95 rather than on any observed value. Its half-width is four binomial
        # standard errors at this sample size, sqrt(0.95*0.05/TRIALS) = 0.00154, which
        # is a 6e-5 chance of a false failure under a correctly calibrated method. It
        # still excludes the naive value near 0.97 by more than ten standard errors.
        standard_error = math.sqrt(0.95 * 0.05 / self.TRIALS)
        low = 0.95 - 4.0 * standard_error
        high = 0.95 + 4.0 * standard_error
        self.assertTrue(
            low <= exact <= high,
            f"exact Fieller coverage {exact:.4f} is outside [{low:.4f}, {high:.4f}]",
        )
        self.assertGreater(naive, 0.965, f"naive handling gave {naive:.4f}")
        # The delta-method interval collapses here; that collapse is the reason the
        # exact set is implemented at all.
        self.assertLess(delta, 0.85, f"delta coverage {delta:.4f}")
        # Nearly every trial is unbounded at this signal-to-noise, and every unbounded
        # one is the exclusive case; the whole-line case does not occur.
        self.assertGreater(unbounded_fraction, 0.85)
        self.assertTrue(all_discriminants_positive)


class MovingBlockBootstrapProperties(unittest.TestCase):
    """Determinism, and the behaviour that distinguishes a block bootstrap from an i.i.d. one."""

    @staticmethod
    def _statistic(xs, ys):
        return x_intercept(ols_line(xs, ys)).value

    N_POINTS = 48
    RHO = 0.9
    SIGMA = 25.0

    @classmethod
    def _drifting_series(cls, seed, n=None, rho=None, sigma=None):
        """Demo line plus an AR(1) gauge error with the stated marginal scale."""
        n = cls.N_POINTS if n is None else n
        rho = cls.RHO if rho is None else rho
        sigma = cls.SIGMA if sigma is None else sigma
        xs, truth = demo_line(0.5, n)
        rng = random.Random(seed)
        innovation = sigma * math.sqrt(1.0 - rho * rho)
        error = rng.gauss(0.0, sigma)
        ys = []
        for value in truth:
            ys.append(value + error)
            error = rho * error + rng.gauss(0.0, innovation)
        return xs, tuple(ys)

    @classmethod
    def _predicted_standard_deviations(cls):
        """Closed-form sd of the x-intercept under independent and under AR(1) errors.

        The x-intercept is a smooth function of two coefficients that are linear in the
        ordinate, so to first order it is linear in the errors too:

            d x0 / d y_i = -(1/b) [1/W + (x0 - xbar)(x_i - xbar) / Sxx]

        evaluated on the noise-free line. Var(x0) = sum_ij c_i c_j Cov(e_i, e_j), with
        Cov(e_i, e_j) = sigma**2 rho**|i-j| for an AR(1) gauge and sigma**2 delta_ij
        for an independent one. Both predictions are written down from the generator's
        own parameters before any resampling happens, so neither is a bootstrap output.
        """
        xs, truth = demo_line(0.5, cls.N_POINTS)
        m = least_squares_moments(xs, truth)
        n = len(xs)
        gradient = tuple(
            -(1.0 / m["slope"]) * (1.0 / n + (DEMO_GAS_IN_PLACE - m["x_mean"]) * (v - m["x_mean"]) / m["sxx"])
            for v in xs
        )
        variance_iid = cls.SIGMA**2 * math.fsum(c * c for c in gradient)
        variance_ar1 = cls.SIGMA**2 * math.fsum(
            gradient[i] * gradient[j] * cls.RHO ** abs(i - j) for i in range(n) for j in range(n)
        )
        return math.sqrt(variance_iid), math.sqrt(variance_ar1)

    def test_same_seed_gives_a_bit_identical_result(self):
        xs, ys = self._drifting_series(1)
        kw = dict(block_length=6, replicates=300, statistic=self._statistic)
        first = moving_block_bootstrap(xs, ys, seed=99, **kw)
        second = moving_block_bootstrap(xs, ys, seed=99, **kw)
        self.assertEqual(first.values, second.values)
        self.assertEqual(first.standard_error, second.standard_error)
        third = moving_block_bootstrap(xs, ys, seed=100, **kw)
        self.assertNotEqual(first.values, third.values)

    def test_longer_blocks_recover_more_of_the_drift_driven_uncertainty(self):
        # The point of the method. Under a drifting gauge the i.i.d. resample (block
        # length 1) loses the run-to-run component entirely, so its standard error is
        # far too small; lengthening the block restores it. Generating i.i.d. data
        # instead would make this test pass vacuously, because every block length would
        # then agree.
        xs, ys = self._drifting_series(4321)
        errors = []
        for block_length in (1, 4, 12):
            result = moving_block_bootstrap(
                xs,
                ys,
                block_length=block_length,
                replicates=600,
                seed=7,
                statistic=self._statistic,
            )
            errors.append(result.standard_error)
        self.assertLess(errors[0], errors[1])
        self.assertLess(errors[1], errors[2])
        # The closed form in `_predicted_standard_deviations` puts the full drift
        # inflation at sd_ar1/sd_iid > 3 for this design, so demanding that the longest
        # block recovers a factor of 1.5 asks for about half of a derived gap rather
        # than for a number read off a run. It stays deliberately loose because a
        # single realisation's blocked standard error has a 42 percent relative spread.
        sd_iid, sd_ar1 = self._predicted_standard_deviations()
        self.assertGreater(sd_ar1 / sd_iid, 3.0)
        self.assertGreater(errors[2] / errors[0], 1.5)

    def test_the_true_spread_under_drift_matches_the_ar1_covariance_closed_form(self):
        # Before asking whether a bootstrap recovers the truth, establish what the
        # truth is from outside every bootstrap: the first-order AR(1) prediction above
        # against 400 independent regenerations of the whole experiment.
        trials = 400
        truth_values = []
        for seed in range(trials):
            xs, ys = self._drifting_series(10000 + seed)
            truth_values.append(self._statistic(xs, ys))
        mean = math.fsum(truth_values) / trials
        true_sd = math.sqrt(math.fsum((v - mean) ** 2 for v in truth_values) / (trials - 1))

        sd_iid, sd_ar1 = self._predicted_standard_deviations()
        # 1/sqrt(2N) = 3.5 percent is the Monte Carlo error of an estimated standard
        # deviation from 400 draws, so 12 percent is about three and a half of those.
        self.assertLess(abs(true_sd / sd_ar1 - 1.0), 0.12)
        # The inflation the drift causes is a property of the design, not of any fit:
        # at rho = 0.9 over 48 surveys the closed form puts it near a factor of three.
        self.assertGreater(sd_ar1 / sd_iid, 3.0)

    def test_the_iid_bootstrap_cannot_see_the_drift_and_the_blocked_one_can(self):
        # Averaged over independent drift realisations, because a single block
        # bootstrap standard error at n/l = 4 has a measured relative spread of 0.42.
        sd_iid, sd_ar1 = self._predicted_standard_deviations()
        realisations = 10
        iid_errors = []
        blocked_errors = []
        for index in range(realisations):
            xs, ys = self._drifting_series(700 + index)
            iid_errors.append(
                moving_block_bootstrap(
                    xs, ys, block_length=1, replicates=400, seed=3, statistic=self._statistic
                ).standard_error
            )
            blocked_errors.append(
                moving_block_bootstrap(
                    xs, ys, block_length=12, replicates=400, seed=3, statistic=self._statistic
                ).standard_error
            )
        iid_mean = math.fsum(iid_errors) / realisations
        blocked_mean = math.fsum(blocked_errors) / realisations

        # An i.i.d. resample destroys the ordering, so the most it can ever report is
        # the independent-errors spread sd_iid -- and on a drifting series it reports
        # less than that, because part of the drift is absorbed into the fitted line
        # and never appears in the residuals it resamples. The one-sided bound is the
        # derivable claim; the measured mean is 0.65 of sd_iid, so 1.3 leaves a wide
        # margin for its own sampling noise while still failing any implementation that
        # somehow recovered the drift without blocking.
        self.assertLess(iid_mean, 1.3 * sd_iid)
        # Consequence of the two bounds, not a new constant: the truth is more than
        # three times sd_iid, so the i.i.d. bootstrap must understate it by more than a
        # factor of two.
        self.assertGreater(sd_ar1 / iid_mean, 2.0)
        # The blocked estimator is calibrated against the same closed form. The spread
        # of one blocked standard error across realisations is 0.42, so the standard
        # error of this mean is 0.42/sqrt(10) = 0.13 and a 40 percent bracket is three
        # of those. It is wide because n/l = 4 leaves the estimator very little to work
        # with, which is the module's own stated validity caveat, not an accident.
        self.assertLess(abs(blocked_mean / sd_ar1 - 1.0), 0.40)

    def test_result_records_the_scheme_it_used(self):
        xs, ys = self._drifting_series(2)
        result = moving_block_bootstrap(
            xs, ys, block_length=5, replicates=50, seed=17, statistic=self._statistic
        )
        self.assertIsInstance(result, BootstrapResult)
        self.assertEqual(result.block_length, 5)
        self.assertEqual(result.n_starts, len(xs) - 5 + 1)
        self.assertEqual(result.seed, 17)
        self.assertEqual(result.n_points, len(xs))
        self.assertEqual(result.method, "moving_block")
        self.assertEqual(result.replicates_requested, 50)
        self.assertAlmostEqual(result.bias, result.mean - result.point_estimate, places=14)


class BlockLengthAdviceProperties(unittest.TestCase):
    def test_independent_residuals_fall_back_to_the_rate_rule(self):
        rng = random.Random(12)
        residuals = tuple(rng.gauss(0.0, 1.0) for _ in range(64))
        advice = suggested_block_length(residuals)
        self.assertIsInstance(advice, BlockLengthAdvice)
        self.assertEqual(advice.rate_rule, 4)  # ceil(64 ** (1/3))
        self.assertEqual(advice.recommended, max(advice.rate_rule, advice.autocorrelation_floor))
        self.assertLess(abs(advice.lag1_correlation), 0.35)
        self.assertIn("not a published rule", advice.rule)

    def test_a_negative_lag1_correlation_reports_the_tau_it_actually_computed(self):
        # A strictly alternating series has an exactly known lag-1 autocorrelation:
        # with v = (1, -1, ... ) of even length n the mean is 0, the denominator is n
        # and the numerator is -(n-1), so rho = -(n-1)/n = -0.875 at n = 8 and
        # tau = (1 + rho)/(1 - rho) = 0.125/1.875 = 1/15. Both are closed form.
        residuals = (1.0, -1.0) * 4
        advice = suggested_block_length(residuals)
        self.assertAlmostEqual(advice.lag1_correlation, -0.875, places=15)
        self.assertAlmostEqual(advice.integrated_autocorrelation_time, 1.0 / 15.0, places=15)
        # The clamp lives on the block length, where a value below one is meaningless,
        # and nowhere else. Reporting tau = 1.0 here would hand back a number that was
        # never computed from the caller's residuals.
        self.assertEqual(advice.autocorrelation_floor, 1)
        self.assertEqual(advice.recommended, advice.rate_rule)

    def test_a_positive_lag1_correlation_leaves_tau_and_the_floor_consistent(self):
        rho = 0.9
        rng = random.Random(13)
        error = rng.gauss(0.0, 1.0)
        residuals = []
        for _ in range(64):
            residuals.append(error)
            error = rho * error + rng.gauss(0.0, math.sqrt(1.0 - rho * rho))
        advice = suggested_block_length(tuple(residuals))
        tau = (1.0 + advice.lag1_correlation) / (1.0 - advice.lag1_correlation)
        self.assertAlmostEqual(advice.integrated_autocorrelation_time, tau, places=15)
        self.assertEqual(advice.autocorrelation_floor, math.ceil(tau))

    def test_strong_drift_raises_the_floor_well_above_the_rate_rule(self):
        rho = 0.9
        rng = random.Random(13)
        error = rng.gauss(0.0, 1.0)
        residuals = []
        for _ in range(64):
            residuals.append(error)
            error = rho * error + rng.gauss(0.0, math.sqrt(1.0 - rho * rho))
        advice = suggested_block_length(tuple(residuals))
        self.assertGreater(advice.lag1_correlation, 0.6)
        self.assertGreater(advice.autocorrelation_floor, advice.rate_rule)
        self.assertEqual(advice.recommended, advice.autocorrelation_floor)


class ReportingContract(unittest.TestCase):
    """The result objects must be immutable and must say enough to be audited."""

    def test_line_fit_is_frozen_and_series_are_tuples(self):
        fit = ols_line(*demo_line(0.5, 12))
        self.assertIsInstance(fit, LineFit)
        self.assertIsInstance(fit.residuals, tuple)
        with self.assertRaises(FrozenInstanceError):
            fit.slope = 1.0

    def test_interval_and_fieller_results_are_frozen(self):
        fit = ols_line(*demo_line(0.5, 12))
        estimate = x_intercept(fit)
        exact = x_intercept_fieller(fit)
        self.assertIsInstance(estimate, IntervalEstimate)
        self.assertIsInstance(exact, FiellerInterval)
        with self.assertRaises(FrozenInstanceError):
            estimate.value = 0.0
        with self.assertRaises(FrozenInstanceError):
            exact.lower = 0.0

    def test_a_weakly_constrained_fit_warns_and_a_well_constrained_one_does_not(self):
        rng = random.Random(64)
        strong_x, strong_truth = demo_line(0.60, 20)
        strong = x_intercept(ols_line(strong_x, tuple(v + rng.gauss(0.0, 10.0) for v in strong_truth)))
        self.assertLess(strong.fieller_g, DELTA_METHOD_G_THRESHOLD)
        self.assertEqual(strong.warnings, ())

        weak_x, weak_truth = demo_line(0.05, 8)
        weak = x_intercept(ols_line(weak_x, tuple(v + rng.gauss(0.0, 250.0) for v in weak_truth)))
        self.assertGreater(weak.fieller_g, DELTA_METHOD_G_THRESHOLD)
        self.assertTrue(weak.warnings)
        self.assertTrue(any("x_intercept_fieller" in w for w in weak.warnings))

    def test_a_fit_with_an_insignificant_slope_says_the_answer_is_unbounded(self):
        # g >= 1 is the same statement as "the slope is not significant", and the
        # standard error returned alongside it does not describe the true set. The
        # warning has to say so, because the number is still finite and still printable.
        xs, truth = demo_line(0.05, 8)
        rng = random.Random(2024)
        ys = tuple(v + rng.gauss(0.0, 300.0) for v in truth)
        fit = ols_line(xs, ys)
        estimate = x_intercept(fit)
        self.assertGreater(estimate.fieller_g, 1.0)
        self.assertTrue(any("unbounded" in w for w in estimate.warnings))
        self.assertFalse(x_intercept_fieller(fit).bounded)

    def test_a_constant_ordinate_does_not_report_a_perfect_fit(self):
        # Syy = 0 makes R**2 = 1 - SSE/Syy the indeterminate 0/0. Reporting 1.0 there
        # is the one choice that cannot be told apart downstream from a genuine perfect
        # fit, and R**2 is printed next to a gas in place. The flag is what a report
        # must consult; the value is deliberately the conspicuous one.
        flat = ols_line((1.0, 2.0, 3.0, 4.0), (5.0, 5.0, 5.0, 5.0))
        self.assertFalse(flat.r_squared_defined)
        self.assertEqual(flat.r_squared, 0.0)
        self.assertEqual(flat.slope, 0.0)

        # A genuine exact fit is distinguishable from it, which is the whole point.
        exact = ols_line((1.0, 2.0, 3.0, 4.0), (2.0, 4.0, 6.0, 8.0))
        self.assertTrue(exact.r_squared_defined)
        self.assertEqual(exact.r_squared, 1.0)

        # Same rule on the York path, which also reaches a constant ordinate.
        york = york_line((1.0, 2.0, 3.0, 4.0), (5.0,) * 4, x_std=(0.1,) * 4, y_std=(0.2,) * 4)
        self.assertFalse(york.r_squared_defined)
        self.assertEqual(york.r_squared, 0.0)

        # And an ordinary fit is unaffected: the flag is True wherever Syy > 0.
        self.assertTrue(ols_line(ANSCOMBE_X, ANSCOMBE_Y1).r_squared_defined)

    def test_predict_returns_the_fitted_ordinate(self):
        fit = ols_line(*demo_line(0.5, 12))
        self.assertAlmostEqual(fit.predict(0.0), fit.intercept, places=12)
        self.assertAlmostEqual(fit.predict(DEMO_GAS_IN_PLACE), 0.0, delta=1.0e-9 * DEMO_INITIAL_P_OVER_Z)
        with self.assertRaises(InvalidInputError):
            fit.predict(float("nan"))

    def test_errors_in_variables_fits_always_carry_the_independence_caveat(self):
        n = len(NCSS_X)
        for fit in (
            deming_line(NCSS_X, NCSS_Y, error_variance_ratio=4.0),
            york_line(NCSS_X, NCSS_Y, x_std=(0.2,) * n, y_std=(0.1,) * n),
        ):
            with self.subTest(method=fit.method):
                self.assertTrue(any("independent between" in w for w in x_intercept(fit).warnings))


# --------------------------------------------------------------------------
# Regression pins -- NOT oracles
# --------------------------------------------------------------------------


class RegressionPins(unittest.TestCase):
    """Numbers this module produced, pinned so that a silent change is noticed.

    Nothing in this class is evidence that the module is right. These are golden
    values from this implementation, kept because they are cheap protection against an
    unintended change and removed from the oracle sections because presenting them
    there overstated the evidence. Each one has an independent check elsewhere in this
    file that does establish correctness; the comment on each pin says which.

    If a pin fails, the question to ask is "what changed and was the change intended",
    not "which side is right" -- the oracle tests answer that.
    """

    def setUp(self):
        n = len(NCSS_X)
        self.deming = deming_line(NCSS_X, NCSS_Y, error_variance_ratio=NCSS_LAMBDA)
        self.york = york_line(
            NCSS_X,
            NCSS_Y,
            x_std=(math.sqrt(NCSS_VAR_X),) * n,
            y_std=(math.sqrt(NCSS_VAR_Y),) * n,
            correlation=0.0,
        )

    def test_ncss_york_cross_estimator_values(self):
        # Correctness of these comes from: the coefficients against the NCSS published
        # model (DemingPublishedOracle), the MSWD against the effective-variance
        # chi-square recomputed by hand (DemingAgainstYorkCrossEstimator), and the
        # York analytic standard errors against York et al. Table II on the York data
        # (YorkPublishedOracle). The values below are this module's output on the NCSS
        # arrays, where no publication states them.
        self.assertAlmostEqual(self.york.mswd, 17.3624, places=4)
        self.assertAlmostEqual(self.york.slope_stderr, 0.037614, places=6)
        self.assertAlmostEqual(self.deming.slope_stderr / self.york.slope_stderr, 4.98, places=1)
        self.assertAlmostEqual(self.york.slope_stderr * math.sqrt(self.york.mswd), 0.15673, places=5)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

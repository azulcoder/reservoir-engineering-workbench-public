"""Straight-line fitting and the uncertainty of an x-intercept.

Why this module is written the way it is
----------------------------------------
Almost everything here exists to get one number right: the standard error of an
x-intercept. In a volumetric gas material balance the gas in place is

    p/Z = (p_i/Z_i) * (1 - Gp/G)

so ``G`` is where the fitted line crosses the abscissa, ``G = -a/b``. That is a
*ratio of two regression coefficients estimated from the same fit*, and the two are
strongly correlated: for ordinary least squares ``Cov(a, b) = -xbar * Var(b)``, which
is non-zero for any uncentred abscissa, and cumulative production is never centred.
Propagating ``Var(a)`` and ``Var(b)`` as if they were independent produces a number
that is finite, plausible, and wrong -- and wrong in the direction that looks
responsible, because the omitted term is negative and the defective estimator always
over-states the uncertainty. Nothing about the output signals the mistake. The only
defence is an explicit test against a Monte Carlo reference, which is why
``tests/test_regression.py`` carries one.

The second thing a ratio does is break the delta method entirely once the denominator
is not sharply determined. When the slope's t-statistic falls to the critical value,
the exact confidence set for the ratio stops being an interval: it becomes the
complement of an interval, and then the whole real line. A symmetric ``G +/- 1.96*SE``
printed in that regime is not conservative, it is a false statement.
:func:`x_intercept_fieller` implements the exact set with all three geometries and
labels which one occurred.

Units
-----
This module is unit-agnostic, which is why -- alone in the package -- its parameters
do not carry unit suffixes. ``x``, ``y``, ``weights``, ``x_std`` and ``y_std`` are in
whatever units the caller supplies, and every returned quantity inherits them: the
slope is y-units per x-unit, the x-intercept is in x-units. The contract fixes these
names (api_contract.md C6) precisely because pinning them to ``_bscf`` and ``_psia``
would tie a general estimator to one application. The one place where this bites is
:func:`deming_line`: its ``error_variance_ratio`` is a ratio of variances in the two
axes' *native* units and is therefore not scale-invariant. Rescaling Gp from scf to
Bscf changes it by 10**18. That is documented at the call site and has no default.

What is not here
----------------
No plotting, no model selection, no automatic outlier rejection, no data cleaning. A
fit never drops, sorts, clips or reweights a caller's point on its own initiative.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from statistics import NormalDist

from .errors import (
    ConvergenceError,
    InvalidInputError,
    NotIdentifiableError,
    ReservoirLabError,
)
from .validation import (
    as_float_sequence,
    require_finite,
    require_min_length,
    require_positive,
    require_same_length,
)

__all__ = [
    "DELTA_METHOD_G_THRESHOLD",
    "FIELLER_BOUNDED",
    "FIELLER_EXCLUSIVE",
    "FIELLER_WHOLE_LINE",
    "BlockLengthAdvice",
    "BootstrapResult",
    "FiellerInterval",
    "IntervalEstimate",
    "LineFit",
    "deming_line",
    "moving_block_bootstrap",
    "ols_line",
    "student_t_quantile",
    "suggested_block_length",
    "x_intercept",
    "x_intercept_fieller",
    "x_intercept_variance_collapsed",
    "york_line",
]

#: Largest Fieller discriminant ``g`` at which a symmetric delta-method interval is
#: still an honest summary of the exact confidence set. The exact (Fieller) half-width
#: exceeds the delta half-width by roughly a factor ``1/(1 - g)``, so a target of one
#: percent agreement between the two gives ``g < 0.01``. The evidence card states two
#: candidate thresholds (0.01 and 0.05) without deriving either; this repository picks
#: 0.01 and records the tolerance it buys, so the choice can be re-argued from the
#: stated target rather than from taste.
DELTA_METHOD_G_THRESHOLD = 0.01

FIELLER_BOUNDED = "bounded"
FIELLER_EXCLUSIVE = "exclusive"
FIELLER_WHOLE_LINE = "whole_line"

_INF = float("inf")

#: Largest abscissa at which :func:`student_t_quantile` can still evaluate its own CDF.
#: The CDF calls the regularised incomplete beta at ``x = dof / (dof + t**2)``, and at
#: ``t = 1e150`` that argument is about ``dof * 1e-300`` -- the last decade in which it
#: is a normal double for the small ``dof`` that can push the quantile out this far.
#: Past it ``x`` goes subnormal and then to zero, at which point the CDF returns
#: exactly 1 for every ``t`` and a root-bracketing search would "succeed" on an
#: underflow artefact. The quantile itself only exceeds this for ``dof`` well below
#: 0.01; ``dof = n - 2`` never does.
_T_QUANTILE_CEILING = 1.0e150


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LineFit:
    """A fitted straight line ``y = intercept + slope * x`` with its error structure.

    Every field is in the caller's own units. The fields beyond the slope, the
    intercept and their standard errors are not decoration: ``covariance``,
    ``x_mean``, ``sum_squared_x_deviations``, ``weight_total`` and
    ``residual_variance`` are exactly what an x-intercept and a Fieller set need, and
    keeping them on the object is what allows :func:`x_intercept` to be a pure
    function of the fit rather than a re-derivation from the raw data.

    Attributes
    ----------
    slope, intercept:
        Coefficients of ``y = intercept + slope * x``.
    slope_stderr, intercept_stderr:
        Standard errors of those coefficients.
    covariance:
        ``Cov(intercept, slope)``. A first-class field, not an internal temporary,
        because dropping it is the defect this module exists to prevent.
    residuals:
        Vertical residuals ``y_i - (intercept + slope * x_i)`` in input order, for
        every method. For the errors-in-variables methods these are *not* the
        quantity minimised -- the orthogonal-ish distance is -- so they are reported
        as a diagnostic, not as the objective.
    r_squared:
        Coefficient of determination computed with the fit's own weights, over the
        points actually fitted. Never compute it against a different subset. See
        :attr:`r_squared_defined` for the one case in which this number means nothing.
    r_squared_defined:
        ``False`` when the weighted ordinate sum of squares is exactly zero, which
        makes ``R**2 = 1 - SSE/Syy`` the indeterminate form ``0/0``. A constant
        ordinate is the case: the line reproduces every point exactly, but there is no
        variation for it to explain. The field then carries 0.0 rather than 1.0, not
        because zero is the right answer -- there is no right answer -- but because
        1.0 is indistinguishable downstream from a genuine perfect fit and reads as an
        endorsement next to a gas in place, while 0.0 is conspicuous enough to be
        questioned. Consult this flag before printing :attr:`r_squared`.
    n_points:
        Number of ``(x, y)`` pairs consumed.
    method:
        ``"ols"``, ``"wls"``, ``"deming"`` or ``"york"``.
    degrees_of_freedom:
        ``n_points - 2``.
    x_mean:
        Abscissa mean with the fit's own weights. For York this is the mean of the
        *adjusted* abscissae, which is the one the York covariance refers to.
    sum_squared_x_deviations:
        ``Sxx`` with the fit's own weights.
    weight_total:
        Sum of the fit's weights. Equal to ``n_points`` for unweighted OLS. It
        replaces ``n`` in the weighted forms of ``Var(intercept)`` and of the Fieller
        set.
    residual_variance:
        Weighted residual mean square ``S / (n - 2)``, where ``S`` uses the fit's own
        weights. See :attr:`weights_are_absolute` for when this is a goodness-of-fit
        statistic rather than a scale estimate.
    weights_are_absolute:
        ``True`` when the fit's weights were reciprocal *variances supplied by the
        caller* rather than relative weights estimated up to a common scale. Only
        then is :attr:`residual_variance` the MSWD, whose expectation is 1 under the
        assumed errors.
    converged, iterations:
        Iteration diagnostics. Closed-form methods report ``True`` and ``0``.
    """

    slope: float
    intercept: float
    slope_stderr: float
    intercept_stderr: float
    covariance: float
    residuals: tuple[float, ...]
    r_squared: float
    r_squared_defined: bool
    n_points: int
    method: str
    degrees_of_freedom: int
    x_mean: float
    sum_squared_x_deviations: float
    weight_total: float
    residual_variance: float
    weights_are_absolute: bool
    converged: bool
    iterations: int

    @property
    def mswd(self) -> float:
        """Mean square weighted deviation, ``S / (n - 2)``.

        Meaningful only when :attr:`weights_are_absolute` is ``True``: it is then a
        reduced chi-square whose expectation is 1, and a value far above 1 says the
        straight line or the assigned errors are wrong. It is emphatically not a
        licence to inflate the standard errors by ``sqrt(MSWD)`` -- that hides a
        physical failure behind a wider error bar.

        Raises
        ------
        InvalidInputError
            If the fit's weights were relative, so no absolute chi-square exists. This
            is deliberately *not* ``NotIdentifiableError``: nothing about the data is
            at fault, the MSWD is simply undefined for this fitting method, and the
            contract's exception table (api_contract.md C3) reserves
            ``NotIdentifiableError`` for a quantity the supplied data cannot pin down.
            A caller has to be able to tell "your surveys cannot support this" from
            "you asked the wrong object".
        """
        if not self.weights_are_absolute:
            raise InvalidInputError(
                f"method {self.method!r} was fitted with relative weights, so its "
                f"weighted residual mean square is a scale estimate, not an MSWD. "
                f"Supply per-point standard deviations and use york_line if you need "
                f"a goodness-of-fit statistic."
            )
        return self.residual_variance

    def predict(self, x: float) -> float:
        """Return ``intercept + slope * x``. No extrapolation guard: see the module note."""
        return self.intercept + self.slope * require_finite(x, "x")


@dataclass(frozen=True)
class IntervalEstimate:
    """A point estimate with a standard error and an audit trail.

    ``warnings`` is populated when the symmetric interval implied by ``stderr`` is
    not a faithful summary of the exact confidence set -- see
    :data:`DELTA_METHOD_G_THRESHOLD`. It is a tuple of plain sentences meant to be
    printed next to the number, not a severity code.
    """

    value: float
    stderr: float
    degrees_of_freedom: int
    n_points: int
    method: str
    fieller_g: float
    warnings: tuple[str, ...]

    def symmetric_interval(self, confidence: float = 0.95) -> tuple[float, float]:
        """Return the Student-t interval ``value -/+ t * stderr``.

        This is the *approximate* interval. It is symmetric by construction and the
        exact set for a ratio is not, so prefer :func:`x_intercept_fieller` whenever
        ``fieller_g`` exceeds :data:`DELTA_METHOD_G_THRESHOLD`.

        Raises
        ------
        InvalidInputError
            If ``confidence`` is not strictly inside ``(0, 1)``.
        """
        t = student_t_quantile(0.5 + _half_confidence(confidence), self.degrees_of_freedom)
        return (self.value - t * self.stderr, self.value + t * self.stderr)


@dataclass(frozen=True)
class FiellerInterval:
    """The exact confidence set for an x-intercept, with its geometry labelled.

    The set for a ratio has three shapes and only one of them is an interval, so the
    two numbers alone are not interpretable -- ``kind`` tells you what they mean:

    ``"bounded"``
        The set is the closed interval ``[lower, upper]``. ``bounded`` is ``True``.
    ``"exclusive"``
        The set is the *complement* of ``(lower, upper)``: two disjoint half-lines,
        with the point estimate outside the excluded middle. ``bounded`` is ``False``.
        One of ``lower``/``upper`` may be infinite in the measure-zero case ``g == 1``,
        where the set degenerates to a single half-line.
    ``"whole_line"``
        The set is all of the real line; ``lower`` and ``upper`` are infinite.
        ``bounded`` is ``False``.

    When ``bounded`` is ``False`` the x-intercept is not identified at this confidence
    level and no finite error bar should be printed for it. This type reports that
    rather than raising, because the excluded middle is real information -- it says
    which values *are* ruled out -- and an exception would throw it away. Callers that
    want a hard failure should test ``bounded`` and raise
    :class:`~reservoir_lab.errors.NotIdentifiableError` themselves.
    """

    kind: str
    bounded: bool
    lower: float
    upper: float
    point_estimate: float
    g: float
    discriminant: float
    confidence: float
    degrees_of_freedom: int
    n_points: int
    method: str

    def contains(self, value: float) -> bool:
        """Return whether ``value`` lies in the confidence set, honouring ``kind``."""
        v = require_finite(value, "value")
        if self.kind == FIELLER_WHOLE_LINE:
            return True
        if self.kind == FIELLER_BOUNDED:
            return self.lower <= v <= self.upper
        return not (self.lower < v < self.upper)


@dataclass(frozen=True)
class BootstrapResult:
    """Resampling distribution of a statistic, with the resampling scheme recorded.

    ``values`` holds the statistic evaluated on each successful resample, in draw
    order, so a caller can form any interval it likes rather than being limited to the
    two this type computes.

    ``n_starts`` is the number of distinct blocks the scheme had to draw from,
    ``n - block_length + 1``. It is a first-class field because it is the one number
    that says how much resampling actually happened: at ``n_starts = 2`` or 3 the
    resample distribution has only a handful of atoms and the standard error below is
    a description of those few atoms rather than of the sampling distribution. The
    degenerate end of that continuum, ``n_starts = 1``, is refused outright.
    """

    point_estimate: float
    values: tuple[float, ...]
    standard_error: float
    mean: float
    bias: float
    block_length: int
    n_starts: int
    n_points: int
    replicates_requested: int
    replicates_used: int
    replicates_failed: int
    seed: int
    method: str

    def percentile_interval(self, confidence: float = 0.95) -> tuple[float, float]:
        """Return the naive percentile interval from :attr:`values`.

        Naive on purpose. It carries no bias correction and no acceleration, and under
        a short series or a strongly drifting gauge it is too narrow for the same
        reason the block bootstrap exists. Use it as a description of the resample
        spread, not as a calibrated interval.

        Raises
        ------
        InvalidInputError
            If ``confidence`` is not strictly inside ``(0, 1)``.
        """
        half = _half_confidence(confidence)
        ordered = sorted(self.values)
        return (_quantile_sorted(ordered, 0.5 - half), _quantile_sorted(ordered, 0.5 + half))


@dataclass(frozen=True)
class BlockLengthAdvice:
    """Block-length suggestion with both of its ingredients exposed.

    The recommendation is a *repository heuristic*, not a result from the literature,
    and it is returned as a dataclass rather than an integer so the caller has to see
    both numbers that went into it and can disagree with the combination.

    Attributes
    ----------
    recommended:
        ``min(max(rate_rule, autocorrelation_floor), n_points)``.
    rate_rule, autocorrelation_floor:
        The two ingredients, each a usable block length in its own right.
    lag1_correlation:
        ``rho``, the lag-1 autocorrelation of the supplied residuals.
    integrated_autocorrelation_time:
        ``tau = (1 + rho) / (1 - rho)``, always as computed, never clamped. A negative
        ``rho`` puts it below 1; ``autocorrelation_floor`` is where the clamp to a
        usable block length lives, so neither number hides the other.
    """

    recommended: int
    rate_rule: int
    autocorrelation_floor: int
    lag1_correlation: float
    integrated_autocorrelation_time: float
    n_points: int
    rule: str


# ---------------------------------------------------------------------------
# Student-t quantile (needed by Fieller; no third-party statistics available)
# ---------------------------------------------------------------------------


def _incomplete_beta_cf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (modified Lentz)."""
    tiny = 1.0e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        # Even step.
        num = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + num * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + num / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        # Odd step.
        num = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + num * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + num / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3.0e-16:
            return h
    raise ConvergenceError(
        "incomplete beta continued fraction did not converge",
        iterations=400,
        last_value=h,
    )


def _regularised_incomplete_beta(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    front = math.exp(log_front)
    # The continued fraction converges quickly only on one side of the mode; use the
    # symmetry I_x(a,b) = 1 - I_{1-x}(b,a) to stay on the fast side.
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _incomplete_beta_cf(a, b, x) / a
    return 1.0 - front * _incomplete_beta_cf(b, a, 1.0 - x) / b


def _student_t_cdf(t: float, dof: float) -> float:
    tail = 0.5 * _regularised_incomplete_beta(0.5 * dof, 0.5, dof / (dof + t * t))
    return 1.0 - tail if t > 0.0 else tail


def _student_t_pdf(t: float, dof: float) -> float:
    log_pdf = (
        math.lgamma(0.5 * (dof + 1.0))
        - math.lgamma(0.5 * dof)
        - 0.5 * math.log(dof * math.pi)
        - 0.5 * (dof + 1.0) * math.log1p(t * t / dof)
    )
    return math.exp(log_pdf)


def student_t_quantile(probability: float, degrees_of_freedom: float) -> float:
    """Inverse CDF of Student's t distribution.

    Dimensionless in and dimensionless out. The package may not import SciPy
    (api_contract.md C8), so this is computed from the regularised incomplete beta
    function directly: the CDF is inverted by Newton's method started from the
    Cornish-Fisher expansion and safeguarded by a bracket, so the iterate can never
    leave an interval known to contain the root.

    Parameters
    ----------
    probability:
        Cumulative probability, strictly inside ``(0, 1)``.
    degrees_of_freedom:
        Strictly positive. Need not be an integer.

    Returns
    -------
    float
        The value ``t`` with ``P(T <= t) = probability``.

    Validity window
    ---------------
    Verified against published t tables for ``1 <= dof <= 100`` and against the
    asymptotic expansion ``t - z ~ (z**3 + z)/(4 dof)`` up to ``dof = 1e8``, where the
    absolute error stays below about 1e-8 (and below 1e-9 up to ``dof = 1e7``).
    Beyond roughly ``dof = 1e8`` the incomplete
    beta function is evaluated at ``x`` within a few parts in 1e9 of unity and loses
    figures to cancellation; use the normal quantile there instead. A regression in
    this package has ``dof = n - 2`` for a handful of pressure surveys, so that regime
    is never reached in practice.

    What this does not do
    ---------------------
    It does not provide the CDF, the survival function, or non-central variants.

    Raises
    ------
    InvalidInputError
        If ``probability`` is not strictly inside ``(0, 1)``, or ``degrees_of_freedom``
        is not strictly positive, or the requested quantile exceeds ``1e150``. The last
        case is a hard input, not a solver failure: the quantile diverges as
        ``degrees_of_freedom -> 0`` and the CDF used to invert it underflows before the
        answer is reached. It needs ``degrees_of_freedom`` well below 0.01, which no
        call site in this package can produce.
    ConvergenceError
        If the safeguarded Newton/bisection iteration does not converge within its
        budget. The bracket is halved on every rejected step, so with a usable bracket
        this indicates a defect rather than a hard input.
    """
    p = require_finite(probability, "probability")
    dof = require_positive(degrees_of_freedom, "degrees_of_freedom")
    if not 0.0 < p < 1.0:
        raise InvalidInputError(f"probability must lie strictly inside (0, 1), got {p!r}")
    if p == 0.5:
        return 0.0
    if p < 0.5:
        return -student_t_quantile(1.0 - p, dof)

    z = NormalDist().inv_cdf(p)
    # Cornish-Fisher expansion of the t quantile about the normal quantile. Only a
    # starting point; its accuracy is irrelevant because Newton is safeguarded.
    z2 = z * z
    guess = z + (z2 + 1.0) * z / (4.0 * dof) + (5.0 * z2 * z2 + 16.0 * z2 + 3.0) * z / (96.0 * dof * dof)
    if not math.isfinite(guess) or guess <= 0.0:
        guess = max(z, 1.0e-6)

    lower, upper = 0.0, min(max(2.0 * guess, 1.0), _T_QUANTILE_CEILING)
    while _student_t_cdf(upper, dof) < p:
        if upper >= _T_QUANTILE_CEILING:
            raise InvalidInputError(
                f"the t quantile at probability={p!r} and degrees_of_freedom={dof!r} is "
                f"larger than {_T_QUANTILE_CEILING:g}, beyond which this implementation "
                f"cannot evaluate the CDF at all: the incomplete beta is evaluated at "
                f"x = dof / (dof + t**2), which stops being a normal double there, so a "
                f"bracket found further out would be an artefact of underflow rather "
                f"than a property of the distribution. The quantile grows like "
                f"t ~ dof**0.5 * const**(-1/dof) as dof -> 0, so this is reached only "
                f"for degrees_of_freedom far below 1; every call site in this package "
                f"has dof = n - 2 >= 1."
            )
        upper = min(2.0 * upper, _T_QUANTILE_CEILING)

    t = min(max(guess, lower + 1e-12), upper)
    for _iteration in range(1, 101):
        cdf = _student_t_cdf(t, dof)
        if cdf < p:
            lower = t
        else:
            upper = t
        density = _student_t_pdf(t, dof)
        step = (cdf - p) / density if density > 0.0 else 0.0
        candidate = t - step
        if not lower < candidate < upper:
            candidate = 0.5 * (lower + upper)
        if abs(candidate - t) <= 1.0e-15 * max(1.0, abs(candidate)):
            return candidate
        t = candidate
    raise ConvergenceError(
        "Student-t quantile iteration did not converge",
        iterations=100,
        last_value=t,
    )


def _half_confidence(confidence: float) -> float:
    conf = require_finite(confidence, "confidence")
    if not 0.0 < conf < 1.0:
        raise InvalidInputError(f"confidence must lie strictly inside (0, 1), got {conf!r}")
    return 0.5 * conf


def _quantile_sorted(ordered: Sequence[float], probability: float) -> float:
    """Linear-interpolation quantile of an already-sorted sample."""
    n = len(ordered)
    if n == 1:
        return ordered[0]
    position = probability * (n - 1)
    low = math.floor(position)
    high = min(low + 1, n - 1)
    weight = position - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


# ---------------------------------------------------------------------------
# Shared input handling
# ---------------------------------------------------------------------------


def _paired_inputs(x: Sequence[float], y: Sequence[float]) -> tuple[tuple[float, ...], tuple[float, ...]]:
    xs = as_float_sequence(x, "x")
    ys = as_float_sequence(y, "y")
    require_same_length(xs, ys, "x", "y")
    require_min_length(
        xs, "x", 3, "a straight-line fit with a residual variance (n - 2 >= 1 degrees of freedom)"
    )
    return xs, ys


def _weighted_moments(
    xs: Sequence[float], ys: Sequence[float], weights: Sequence[float]
) -> tuple[float, float, float, float, float, float]:
    """Return ``(weight_total, x_mean, y_mean, Sxx, Sxy, Syy)``, all weighted.

    Two-pass (centred) accumulation on purpose. The one-pass
    ``sum(x*x) - sum(x)**2/n`` shortcut loses most of its significant figures when the
    abscissa is large and its spread is small, which is exactly the early-depletion
    case where the x-intercept is a long extrapolation and precision matters most.
    """
    weight_total = math.fsum(weights)
    x_mean = math.fsum(w * xi for w, xi in zip(weights, xs, strict=True)) / weight_total
    y_mean = math.fsum(w * yi for w, yi in zip(weights, ys, strict=True)) / weight_total
    sxx = math.fsum(w * (xi - x_mean) ** 2 for w, xi in zip(weights, xs, strict=True))
    sxy = math.fsum(w * (xi - x_mean) * (yi - y_mean) for w, xi, yi in zip(weights, xs, ys, strict=True))
    syy = math.fsum(w * (yi - y_mean) ** 2 for w, yi in zip(weights, ys, strict=True))
    return weight_total, x_mean, y_mean, sxx, sxy, syy


def _require_spread(sxx: float, n: int) -> None:
    if sxx <= 0.0:
        raise NotIdentifiableError(
            f"all {n} abscissae are identical, so the slope is not identifiable from "
            f"these data. A shut-in period with no production between surveys produces "
            f"exactly this input."
        )


# ---------------------------------------------------------------------------
# Ordinary and weighted least squares
# ---------------------------------------------------------------------------


def ols_line(
    x: Sequence[float],
    y: Sequence[float],
    *,
    weights: Sequence[float] | None = None,
) -> LineFit:
    """Fit ``y = intercept + slope * x`` by (optionally weighted) least squares.

    Unit-agnostic: ``x`` and ``y`` carry the caller's units and the results inherit
    them. ``weights`` are relative and dimensionless -- only their ratios matter, so
    scaling every weight by a common factor returns a bit-identical fit.

    The returned covariance is the exact closed form ``Cov(a, b) = -xbar * Var(b)``,
    which is negative for any positive abscissa mean. That sign is the whole reason
    :func:`x_intercept` needs the covariance term: for a depleting reservoir the
    omitted contribution is negative, so dropping it always over-states the
    uncertainty in the gas in place, and an over-stated uncertainty never looks like
    a bug.

    Parameters
    ----------
    x, y:
        Equal-length sequences of at least three finite values.
    weights:
        Optional strictly positive relative weights, one per point. The usual choice
        is ``1 / sigma_i**2``; passing the reciprocal variances themselves is fine and
        makes no difference to the fit, though the standard errors are still scaled by
        the residual mean square rather than trusting the variances (use
        :func:`york_line` if you want them trusted).

    Returns
    -------
    LineFit
        With ``method`` equal to ``"ols"`` when ``weights`` is ``None`` and ``"wls"``
        otherwise. The two are identical numerically when all weights are equal; they
        are labelled differently so a report says which path ran.

    Assumptions and validity window
    -------------------------------
    The abscissa is error-free, the ordinate errors are independent between points,
    zero-mean and (after weighting) of constant variance, and the underlying relation
    is genuinely straight over the fitted range. The first assumption fails for a p/Z
    plot whose cumulative production carries allocation error; the second fails for a
    drifting gauge; the third fails under water drive, where the plot is curved and a
    line fitted to the straight-looking late segment has a high R-squared and a badly
    biased x-intercept. None of those failures is visible in this function's output.

    What this does not do
    ---------------------
    It does not sort, deduplicate, clip, drop or impute anything, does not test the
    linearity assumption, and does not decide which points belong to the fit.

    Raises
    ------
    InvalidInputError
        Non-finite or mismatched inputs, fewer than three points, or a weight that is
        not strictly positive.
    NotIdentifiableError
        If every abscissa is identical, so there is no slope to estimate.
    """
    xs, ys = _paired_inputs(x, y)
    n = len(xs)
    if weights is None:
        ws: tuple[float, ...] = (1.0,) * n
        method = "ols"
    else:
        ws = as_float_sequence(weights, "weights")
        require_same_length(ws, xs, "weights", "x")
        for index, value in enumerate(ws):
            if value <= 0.0:
                raise InvalidInputError(
                    f"weights[{index}] must be strictly positive, got {value!r}. A zero "
                    f"weight is a request to drop a point, which this function will not "
                    f"do silently -- remove the point upstream and record why."
                )
        method = "wls"

    weight_total, x_mean, y_mean, sxx, sxy, syy = _weighted_moments(xs, ys, ws)
    _require_spread(sxx, n)

    slope = sxy / sxx
    intercept = y_mean - slope * x_mean
    residuals = tuple(yi - (intercept + slope * xi) for xi, yi in zip(xs, ys, strict=True))
    weighted_sse = math.fsum(w * r * r for w, r in zip(ws, residuals, strict=True))
    dof = n - 2
    residual_variance = weighted_sse / dof

    var_slope = residual_variance / sxx
    var_intercept = residual_variance * (1.0 / weight_total + x_mean * x_mean / sxx)
    # Cov(a, b) = -xbar * Var(b). Negative whenever the abscissa mean is positive,
    # which it always is for cumulative production, and material because the fit is
    # never centred.
    covariance = -x_mean * var_slope

    # Syy == 0 (a constant ordinate) makes R**2 the indeterminate 0/0; report the
    # flag rather than a number that cannot be told apart from a perfect fit.
    r_squared_defined = syy > 0.0
    r_squared = 1.0 - weighted_sse / syy if r_squared_defined else 0.0

    return LineFit(
        slope=slope,
        intercept=intercept,
        slope_stderr=math.sqrt(var_slope),
        intercept_stderr=math.sqrt(var_intercept),
        covariance=covariance,
        residuals=residuals,
        r_squared=r_squared,
        r_squared_defined=r_squared_defined,
        n_points=n,
        method=method,
        degrees_of_freedom=dof,
        x_mean=x_mean,
        sum_squared_x_deviations=sxx,
        weight_total=weight_total,
        residual_variance=residual_variance,
        weights_are_absolute=False,
        converged=True,
        iterations=0,
    )


# ---------------------------------------------------------------------------
# Deming regression
# ---------------------------------------------------------------------------


def _deming_coefficients(xs: Sequence[float], ys: Sequence[float], ratio: float) -> tuple[float, float]:
    """Closed-form Deming slope and intercept, with the cancellation-safe branch."""
    n = len(xs)
    weights = (1.0,) * n
    _weight_total, x_mean, y_mean, u, sxy, q = _weighted_moments(xs, ys, weights)
    _require_spread(u, n)
    if sxy == 0.0:
        raise NotIdentifiableError(
            "the Deming slope divides by the x-y cross product, which is exactly zero "
            "for these data, so no line is identifiable. This happens when the "
            "ordinate carries no linear signal in the abscissa at all."
        )
    head = ratio * q - u
    discriminant = math.sqrt(head * head + 4.0 * ratio * sxy * sxy)
    # Cancellation-safe branch selection, not a style choice: for head < 0 the
    # numerator (head + discriminant) is a difference of nearly equal numbers and
    # loses most of its significant figures, so the algebraically equivalent
    # conjugate form is used instead. A ternary would hide which branch is which.
    if head >= 0.0:  # noqa: SIM108
        # Both terms of the numerator are non-negative, so no cancellation.
        slope = (head + discriminant) / (2.0 * ratio * sxy)
    else:
        # head + discriminant subtracts two nearly equal quantities when
        # ratio * Syy ~ Sxx, which is precisely the near-orthogonally-scaled case and
        # also the ratio -> 0 limit. The conjugate form is algebraically identical and
        # adds two positive quantities instead of cancelling them. Verified: at
        # ratio = 1e-12 this returns the OLS slope to 13 significant figures where the
        # direct form manages 5.
        slope = 2.0 * sxy / (-head + discriminant)
    return y_mean - slope * x_mean, slope


def deming_line(
    x: Sequence[float],
    y: Sequence[float],
    *,
    error_variance_ratio: float,
) -> LineFit:
    """Fit a straight line with errors in both variables, for a known variance ratio.

    Minimises ``sum_i[(x_i - Xhat_i)**2 + lambda * (y_i - Yhat_i)**2]`` with
    ``lambda = error_variance_ratio``, following the convention of NCSS Chapter 303
    (after Linnet 1990): **lambda is the variance of the x-error divided by the
    variance of the y-error**. Several packages use the reciprocal, so the convention
    is pinned here and both limits are asserted in the test suite rather than trusted.

    Units and the scale trap
    ------------------------
    ``error_variance_ratio`` is a ratio of variances in the two axes' *native* units,
    so it is not scale-invariant: expressing cumulative production in scf instead of
    Bscf changes the correct value by 10**18. There is deliberately no default. A
    default of 1 would be a silent and physically meaningless claim about the relative
    precision of a pressure gauge and a production allocation.

    Limits, which double as the test oracles
    ----------------------------------------
    ``lambda -> 0`` means an error-free abscissa and returns the OLS slope
    ``Sxy / Sxx``. ``lambda -> infinity`` means an error-free ordinate and returns the
    x-on-y slope ``Syy / Sxy``. ``lambda = 1`` is orthogonal (major-axis) regression.

    Standard errors
    ---------------
    By the delete-one jackknife of NCSS Chapter 303, with pseudovalues
    ``theta*_i = N*theta - (N-1)*theta_{-i}`` and ``Var = sum (theta*_i - mean)**2 /
    (N*(N-1))``. The same construction gives the slope-intercept covariance, so the
    delta method in :func:`x_intercept` works on a Deming fit too. This is *not* the
    same quantity as the analytic York standard error evaluated with the same variance
    ratio, and the two must not be swapped: on the NCSS Example 1 data they differ by
    a factor of five, because the assigned variances there are about seventeen times
    too small for the observed scatter. The jackknife estimates the scatter from the
    data; York trusts the variances you give it. If you know your gauge variances
    absolutely, use :func:`york_line` and read its MSWD.

    The jackknife also assumes independent pairs. Under a drifting gauge it fails in
    exactly the way an i.i.d. bootstrap does -- see :func:`moving_block_bootstrap`.

    A delete-one replicate can be degenerate while the full series is not: drop the one
    survey that carries the abscissa spread and the remaining points share an abscissa.
    The line is still defined there, but its jackknife standard error is not, and this
    function refuses with a message that names the offending replicate rather than
    describing the caller's series as degenerate.

    Parameters
    ----------
    x, y:
        Equal-length sequences of at least three finite values.
    error_variance_ratio:
        Strictly positive, finite. See the scale trap above.

    Returns
    -------
    LineFit
        With ``method="deming"``. ``residual_variance`` is the ordinary vertical
        residual mean square, reported as a descriptive scale; ``weights_are_absolute``
        is ``False``, so :attr:`LineFit.mswd` refuses.

    What this does not do
    ---------------------
    It does not estimate the variance ratio from the data -- that is not identifiable
    from a single straight-line fit -- and it does not accept per-point errors. For
    per-point weights or correlated x-y errors use :func:`york_line`.

    Raises
    ------
    InvalidInputError
        Non-finite or mismatched inputs, fewer than three points, or a non-positive
        ``error_variance_ratio``.
    NotIdentifiableError
        If the abscissae are all identical, or the x-y cross product is exactly zero.
        Also if some delete-one replicate is degenerate while the full series is not,
        in which case the line exists but its jackknife standard error does not; the
        message names the replicate index and says so explicitly, because a subset's
        degeneracy is not a property of the caller's series.
    """
    xs, ys = _paired_inputs(x, y)
    ratio = require_positive(error_variance_ratio, "error_variance_ratio")
    n = len(xs)

    intercept, slope = _deming_coefficients(xs, ys, ratio)

    # Delete-one jackknife. Cheap here because the point estimate is closed form.
    pseudo_intercept = []
    pseudo_slope = []
    for index in range(n):
        reduced_x = xs[:index] + xs[index + 1 :]
        reduced_y = ys[:index] + ys[index + 1 :]
        try:
            sub_intercept, sub_slope = _deming_coefficients(reduced_x, reduced_y, ratio)
        except NotIdentifiableError as exc:
            # The refusal came from a leave-one-out SUBSET, not from the series the
            # caller supplied. Letting it out unwrapped states something false about
            # the caller's own data -- it reports the subset's point count and the
            # subset's cross product -- and sends an engineer looking for a fault in
            # data that fitted perfectly well. Name the replicate instead, and say
            # which quantity is actually unavailable.
            raise NotIdentifiableError(
                f"the delete-one jackknife standard error is not identifiable for these "
                f"{n} points: the leave-one-out replicate that omits index {index} is a "
                f"degenerate {n - 1}-point subset ({exc}). The fitted line itself is "
                f"well defined -- slope {slope!r}, intercept {intercept!r} -- so this is "
                f"a refusal to report an uncertainty, not a refusal to fit. One point "
                f"carrying all of the abscissa spread does this, which is what a shut-in "
                f"leaves behind when several surveys share one cumulative production. "
                f"For a standard error on data shaped like this use york_line with "
                f"per-point errors, or ols_line if the abscissa is error-free."
            ) from exc
        pseudo_intercept.append(n * intercept - (n - 1) * sub_intercept)
        pseudo_slope.append(n * slope - (n - 1) * sub_slope)
    mean_intercept = math.fsum(pseudo_intercept) / n
    mean_slope = math.fsum(pseudo_slope) / n
    scale = n * (n - 1)
    var_intercept = math.fsum((v - mean_intercept) ** 2 for v in pseudo_intercept) / scale
    var_slope = math.fsum((v - mean_slope) ** 2 for v in pseudo_slope) / scale
    covariance = (
        math.fsum(
            (a - mean_intercept) * (b - mean_slope)
            for a, b in zip(pseudo_intercept, pseudo_slope, strict=True)
        )
        / scale
    )

    weights = (1.0,) * n
    weight_total, x_mean, _y_mean, sxx, _sxy, syy = _weighted_moments(xs, ys, weights)
    residuals = tuple(yi - (intercept + slope * xi) for xi, yi in zip(xs, ys, strict=True))
    sse = math.fsum(r * r for r in residuals)
    dof = n - 2

    return LineFit(
        slope=slope,
        intercept=intercept,
        slope_stderr=math.sqrt(var_slope),
        intercept_stderr=math.sqrt(var_intercept),
        covariance=covariance,
        residuals=residuals,
        # A constant ordinate is normally intercepted earlier, because it drives Sxy
        # to zero and the Deming slope divides by it; the guard is kept anyway so that
        # every method reports R**2 under the same rule.
        r_squared=1.0 - sse / syy if syy > 0.0 else 0.0,
        r_squared_defined=syy > 0.0,
        n_points=n,
        method="deming",
        degrees_of_freedom=dof,
        x_mean=x_mean,
        sum_squared_x_deviations=sxx,
        weight_total=weight_total,
        residual_variance=sse / dof,
        weights_are_absolute=False,
        converged=True,
        iterations=0,
    )


# ---------------------------------------------------------------------------
# York errors-in-variables regression
# ---------------------------------------------------------------------------


def _york_weights(
    omega_x: Sequence[float],
    omega_y: Sequence[float],
    alpha: Sequence[float],
    correlations: Sequence[float],
    slope: float,
) -> tuple[float, ...]:
    out = []
    for index, (wx, wy, a, r) in enumerate(zip(omega_x, omega_y, alpha, correlations, strict=True)):
        denominator = wx + slope * slope * wy - 2.0 * slope * r * a
        if denominator <= 0.0:
            raise NotIdentifiableError(
                f"York effective weight {index} has a non-positive denominator "
                f"({denominator!r}) at slope {slope!r}. This happens when the assigned "
                f"error correlation is close to +/-1 and cancels the assigned variances; "
                f"no weight, and therefore no fit, is defined there."
            )
        out.append(wx * wy / denominator)
    return tuple(out)


def york_line(
    x: Sequence[float],
    y: Sequence[float],
    *,
    x_std: Sequence[float],
    y_std: Sequence[float],
    correlation: float | Sequence[float] = 0.0,
    tolerance: float = 1.0e-12,
    max_iterations: int = 200,
) -> LineFit:
    """Fit a straight line with per-point errors in both variables (York et al. 2004).

    Implements the unified equations (13a)-(13d) of York, Evensen, Lopez Martinez and
    De Basabe Delgado, *Am. J. Phys.* **72**(3):367-375, and their iteration steps
    (1)-(10). The estimator is the maximum-likelihood line when the assigned errors
    are correct, and it is symmetric in the two axes: swapping ``(x, x_std)`` with
    ``(y, y_std)`` returns the reciprocal slope and the same line. That symmetry is
    York's own route to an x-intercept and its standard error, and this repository
    uses it as the independent oracle for :func:`x_intercept`.

    Units
    -----
    Unit-agnostic. ``x_std`` shares the units of ``x`` and ``y_std`` those of ``y``,
    by construction, so no suffix would be correct for all callers. Unlike the Deming
    variance ratio, the per-point standard deviations are absolute, which is what
    makes the returned MSWD interpretable.

    The one thing most easily got wrong
    -----------------------------------
    ``sigma_b**2 = 1 / sum(W_i * u_i**2)`` uses the *adjusted* abscissae
    ``x_i = Xbar + beta_i``, not the observed ones. Using the observed values is the
    classical pre-2004 error and changes the answer by well under ten percent on real
    data, so a loose tolerance will not catch it. The tests therefore assert against
    York's own published six-figure values rather than against a round number.

    Parameters
    ----------
    x, y:
        Equal-length sequences of at least three finite values.
    x_std, y_std:
        Strictly positive one-sigma errors, one per point, in the units of ``x`` and
        ``y`` respectively. For a p/Z plot ``y_std`` is the error in ``p/Z``, not the
        error in ``p``: propagate it as ``|d(p/Z)/dp| * sigma(p)``, which needs
        ``dZ/dp`` and is a separate calculation.
    correlation:
        Within-point correlation between the x-error and the y-error, either one value
        for all points or one per point. Must satisfy ``|r| < 1`` strictly; ``r = +/-1``
        collapses the effective weight and is rejected rather than special-cased.
    tolerance:
        Relative convergence tolerance on the slope.
    max_iterations:
        Iteration budget. Exhausting it raises rather than returning the last iterate,
        because the returned standard errors are evaluated at points that depend on the
        converged slope and are meaningless without it.

    Returns
    -------
    LineFit
        With ``method="york"``, ``weights_are_absolute=True`` (so
        :attr:`LineFit.mswd` is available), ``x_mean`` the weighted mean of the
        *adjusted* abscissae, and ``covariance`` equal to ``-xbar * sigma_b**2``.

    Assumptions and validity window
    -------------------------------
    Errors are Normal, known per point up to nothing (they are taken at face value),
    and independent *between* points. That last assumption is what a drifting pressure
    gauge breaks, and no amount of per-point weighting repairs it. An MSWD far above 1
    says either the straight-line model is wrong or the assigned errors are too small;
    it is a diagnostic, not a licence to rescale the standard errors.

    What this does not do
    ---------------------
    It does not estimate the errors from the data, does not rescale the standard errors
    by ``sqrt(MSWD)``, and does not detect between-point correlation.

    Raises
    ------
    InvalidInputError
        Non-finite or mismatched inputs, fewer than three points, a non-positive
        standard deviation, ``|correlation| >= 1``, a non-positive tolerance, or a
        non-positive iteration budget.
    NotIdentifiableError
        If the abscissae are all identical, if an effective-weight denominator is not
        positive, or if the slope update divides by zero.
    ConvergenceError
        If the slope iteration does not meet ``tolerance`` within ``max_iterations``.
    """
    xs, ys = _paired_inputs(x, y)
    n = len(xs)
    sx = as_float_sequence(x_std, "x_std")
    sy = as_float_sequence(y_std, "y_std")
    require_same_length(sx, xs, "x_std", "x")
    require_same_length(sy, xs, "y_std", "x")
    for index, value in enumerate(sx):
        require_positive(value, f"x_std[{index}]")
    for index, value in enumerate(sy):
        require_positive(value, f"y_std[{index}]")

    if isinstance(correlation, (int, float)):
        correlations = (require_finite(correlation, "correlation"),) * n
    else:
        correlations = as_float_sequence(correlation, "correlation")
        require_same_length(correlations, xs, "correlation", "x")
    for index, value in enumerate(correlations):
        if not -1.0 < value < 1.0:
            raise InvalidInputError(
                f"correlation[{index}] must satisfy |r| < 1, got {value!r}. A perfect "
                f"within-point correlation is the Brooks/Wendt/Harre special case and is "
                f"not handled by the general weight."
            )

    tol = require_positive(tolerance, "tolerance")
    if not isinstance(max_iterations, int) or max_iterations < 1:
        raise InvalidInputError(f"max_iterations must be a positive integer, got {max_iterations!r}")

    omega_x = tuple(1.0 / (s * s) for s in sx)
    omega_y = tuple(1.0 / (s * s) for s in sy)
    alpha = tuple(math.sqrt(wx * wy) for wx, wy in zip(omega_x, omega_y, strict=True))

    # Step (1): initialise from the unweighted OLS slope, as York prescribes.
    seed_fit = ols_line(xs, ys)
    slope = seed_fit.slope

    converged = False
    iterations = 0
    weights: tuple[float, ...] = ()
    beta: tuple[float, ...] = ()
    x_bar = y_bar = 0.0
    # `iterations` is read after the loop: the converged count is reported on the fit.
    for iterations in range(1, max_iterations + 1):  # noqa: B007
        weights, beta, x_bar, y_bar = _york_step(xs, ys, omega_x, omega_y, alpha, correlations, slope)
        numerator = math.fsum(w * bi * (yi - y_bar) for w, bi, yi in zip(weights, beta, ys, strict=True))
        denominator = math.fsum(w * bi * (xi - x_bar) for w, bi, xi in zip(weights, beta, xs, strict=True))
        if denominator == 0.0:
            raise NotIdentifiableError(
                "the York slope update divides by zero: the weighted x-leverage of the "
                "adjusted points vanished, so no slope is identifiable from these data "
                "and these assigned errors."
            )
        new_slope = numerator / denominator
        if abs(new_slope - slope) <= tol * abs(new_slope):
            slope = new_slope
            converged = True
            break
        slope = new_slope

    if not converged:
        raise ConvergenceError(
            "York slope iteration did not converge; the standard errors are evaluated "
            "at adjusted points that depend on the slope, so the last iterate is not a "
            "usable answer",
            iterations=max_iterations,
            last_value=slope,
        )

    # Recompute the state at the converged slope so that every reported quantity comes
    # from one consistent set of weights.
    weights, beta, x_bar, y_bar = _york_step(xs, ys, omega_x, omega_y, alpha, correlations, slope)
    intercept = y_bar - slope * x_bar

    weight_total = math.fsum(weights)
    # Steps (8)-(9): the standard errors use the least-squares ADJUSTED abscissae.
    adjusted_x = tuple(x_bar + b for b in beta)
    adjusted_mean = math.fsum(w * v for w, v in zip(weights, adjusted_x, strict=True)) / weight_total
    leverage = math.fsum(w * (v - adjusted_mean) ** 2 for w, v in zip(weights, adjusted_x, strict=True))
    if leverage <= 0.0:
        raise NotIdentifiableError(
            "the weighted spread of the adjusted abscissae is zero, so the York slope "
            "variance is not defined for these data."
        )
    var_slope = 1.0 / leverage
    var_intercept = 1.0 / weight_total + adjusted_mean * adjusted_mean * var_slope
    covariance = -adjusted_mean * var_slope

    residuals = tuple(yi - (intercept + slope * xi) for xi, yi in zip(xs, ys, strict=True))
    weighted_sse = math.fsum(w * r * r for w, r in zip(weights, residuals, strict=True))
    weighted_syy = math.fsum(w * (yi - y_bar) ** 2 for w, yi in zip(weights, ys, strict=True))
    dof = n - 2

    return LineFit(
        slope=slope,
        intercept=intercept,
        slope_stderr=math.sqrt(var_slope),
        intercept_stderr=math.sqrt(var_intercept),
        covariance=covariance,
        residuals=residuals,
        r_squared=1.0 - weighted_sse / weighted_syy if weighted_syy > 0.0 else 0.0,
        r_squared_defined=weighted_syy > 0.0,
        n_points=n,
        method="york",
        degrees_of_freedom=dof,
        x_mean=adjusted_mean,
        sum_squared_x_deviations=leverage,
        weight_total=weight_total,
        residual_variance=weighted_sse / dof,
        weights_are_absolute=True,
        converged=True,
        iterations=iterations,
    )


def _york_step(
    xs: Sequence[float],
    ys: Sequence[float],
    omega_x: Sequence[float],
    omega_y: Sequence[float],
    alpha: Sequence[float],
    correlations: Sequence[float],
    slope: float,
) -> tuple[tuple[float, ...], tuple[float, ...], float, float]:
    """Return the weights, weighted means and beta of York et al. (2004) steps (3)-(4)."""
    weights = _york_weights(omega_x, omega_y, alpha, correlations, slope)
    weight_total = math.fsum(weights)
    x_bar = math.fsum(w * v for w, v in zip(weights, xs, strict=True)) / weight_total
    y_bar = math.fsum(w * v for w, v in zip(weights, ys, strict=True)) / weight_total
    beta = tuple(
        w * ((xi - x_bar) / wy + slope * (yi - y_bar) / wx - (slope * (xi - x_bar) + (yi - y_bar)) * r / a)
        for w, xi, yi, wx, wy, r, a in zip(
            weights, xs, ys, omega_x, omega_y, correlations, alpha, strict=True
        )
    )
    return weights, beta, x_bar, y_bar


# ---------------------------------------------------------------------------
# The x-intercept and its uncertainty
# ---------------------------------------------------------------------------


def x_intercept(fit: LineFit) -> IntervalEstimate:
    r"""Estimate the x-intercept of a fitted line and its delta-method standard error.

    The x-intercept is ``x0 = -a / b`` where ``a`` is the intercept and ``b`` the
    slope. In a volumetric gas material balance this is the gas in place, in the
    units of ``x``.

    Derivation of the variance
    --------------------------
    ``x0`` is a smooth function of the two fitted coefficients, so a first-order
    Taylor expansion about their expectations gives

    .. math::

        \frac{\partial x_0}{\partial a} = -\frac{1}{b}, \qquad
        \frac{\partial x_0}{\partial b} = \frac{a}{b^2} = -\frac{x_0}{b}

    .. math::

        \operatorname{Var}(x_0) \simeq
          \left(\frac{\partial x_0}{\partial a}\right)^2 \operatorname{Var}(a)
        + \left(\frac{\partial x_0}{\partial b}\right)^2 \operatorname{Var}(b)
        + 2 \frac{\partial x_0}{\partial a}\frac{\partial x_0}{\partial b}
            \operatorname{Cov}(a, b)

    .. math::

        \operatorname{Var}(x_0) =
          \frac{1}{b^2}\Bigl[\operatorname{Var}(a) + x_0^2\operatorname{Var}(b)
          + 2 x_0 \operatorname{Cov}(a, b)\Bigr]

    The cross term is the part that gets dropped. It must not be: the two coefficients
    of a line fitted to uncentred data are strongly correlated, with
    ``Cov(a, b) = -xbar * Var(b)``, and since ``xbar > 0`` and ``x0 > 0`` for a
    depleting reservoir the omitted term is negative. Dropping it therefore always
    *inflates* the reported uncertainty -- measured at +36 percent on a 12-survey
    synthetic p/Z line and +88 percent on York's data set 3. A conservative error is
    still an error, and because it is conservative nothing else in a study will ever
    flag it.

    For an ordinary least-squares fit, substituting the closed forms collapses the
    expression exactly to the classical inverse-prediction variance

    .. math::

        \operatorname{Var}(x_0) = \frac{s^2}{b^2}
            \left[\frac{1}{n} + \frac{(x_0 - \bar{x})^2}{S_{xx}}\right]

    which :func:`x_intercept_variance_collapsed` computes independently. The general
    form above is the one used here because it also serves the Deming and York fits,
    where no such collapse exists.

    Parameters
    ----------
    fit:
        Any :class:`LineFit`.

    Returns
    -------
    IntervalEstimate
        ``value`` in the units of ``x``, ``stderr`` likewise, plus the Fieller
        discriminant ``g`` evaluated at 95 percent -- the reporting convention of this
        module -- and a warning tuple when the symmetric interval is no longer a
        faithful summary. ``warnings`` is advisory: this function still returns a
        finite standard error, because the number is a legitimate first-order
        quantity. Deciding whether to print it is what
        :func:`x_intercept_fieller` is for.

    Validity window
    ---------------
    A first-order linearisation of a ratio is trustworthy only while the denominator
    is far from zero, which here means ``g = (t * SE(b) / b)**2`` well below 1. At
    ``g`` of order 1 the true confidence set is unbounded and no symmetric interval
    can represent it; measured coverage of the nominal 95 percent delta interval falls
    to 0.78 in that regime while the exact Fieller set holds 0.95.

    What this does not do
    ---------------------
    It does not correct the bias of a ratio estimator, does not give an asymmetric
    interval, and does not refuse to answer when the linearisation is poor.

    Raises
    ------
    NotIdentifiableError
        If the fitted slope is zero, so the line never crosses the abscissa, or if the
        propagated variance is negative, which would mean the supplied covariance is
        not that of a valid covariance matrix.
    """
    if not isinstance(fit, LineFit):
        raise InvalidInputError(f"fit must be a LineFit, got {type(fit).__name__}")
    slope = fit.slope
    if slope == 0.0:
        raise NotIdentifiableError(
            "the fitted slope is exactly zero, so the line has no x-intercept. In a p/Z "
            "context this means the surveys show no pressure decline at all and the gas "
            "in place is not identifiable from them."
        )

    value = -fit.intercept / slope
    var_intercept = fit.intercept_stderr**2
    var_slope = fit.slope_stderr**2
    variance = (var_intercept + value * value * var_slope + 2.0 * value * fit.covariance) / (slope * slope)
    if variance < 0.0:
        raise NotIdentifiableError(
            f"the delta-method variance of the x-intercept came out negative "
            f"({variance!r}); the supplied slope, intercept and covariance do not form "
            f"a positive semi-definite covariance matrix."
        )

    t = student_t_quantile(0.975, fit.degrees_of_freedom)
    g = (t * fit.slope_stderr / slope) ** 2

    messages: list[str] = []
    if g >= 1.0:
        messages.append(
            f"g = {g:.4g} >= 1 at 95 percent confidence: the exact confidence set for "
            f"this x-intercept is unbounded and the standard error below does not "
            f"describe it. Use x_intercept_fieller and report the set it returns."
        )
    elif g > DELTA_METHOD_G_THRESHOLD:
        messages.append(
            f"g = {g:.4g} exceeds {DELTA_METHOD_G_THRESHOLD}: the exact interval is "
            f"asymmetric and roughly 1/(1-g) = {1.0 / (1.0 - g):.3g} times wider on one "
            f"side than the symmetric approximation. Prefer x_intercept_fieller."
        )
    if fit.method in ("deming", "york"):
        messages.append(
            "the delta method here inherits the errors-in-variables covariance, which "
            "assumes the assigned per-point errors are right and independent between "
            "points; a drifting gauge violates the second assumption."
        )

    return IntervalEstimate(
        value=value,
        stderr=math.sqrt(variance),
        degrees_of_freedom=fit.degrees_of_freedom,
        n_points=fit.n_points,
        method=fit.method,
        fieller_g=g,
        warnings=tuple(messages),
    )


def x_intercept_variance_collapsed(fit: LineFit) -> float:
    """Variance of the x-intercept by the collapsed least-squares closed form.

    Returns ``(s**2 / b**2) * [1/W + (x0 - xbar)**2 / Sxx]`` in squared x-units, where
    ``W`` is the total weight (``n`` unweighted). This is algebraically identical to
    the general delta-method expression in :func:`x_intercept` for a least-squares fit
    -- the substitution is written out in that docstring -- and is kept as a separate
    code path on purpose: the two must agree to machine precision, and a test that
    checks they do is what catches a future tidy-up that deletes the covariance term.

    It is defined only for ``"ols"`` and ``"wls"`` fits, because the collapse uses the
    least-squares forms of ``Var(a)``, ``Var(b)`` and ``Cov(a, b)``.

    Raises
    ------
    InvalidInputError
        If ``fit`` was produced by a method other than ordinary or weighted least
        squares.
    NotIdentifiableError
        If the fitted slope is exactly zero.
    """
    if not isinstance(fit, LineFit):
        raise InvalidInputError(f"fit must be a LineFit, got {type(fit).__name__}")
    if fit.method not in ("ols", "wls"):
        raise InvalidInputError(
            f"the collapsed form is the least-squares inverse-prediction variance and "
            f"does not apply to method {fit.method!r}; use x_intercept, whose general "
            f"delta-method expression covers every fit."
        )
    if fit.slope == 0.0:
        raise NotIdentifiableError("the fitted slope is exactly zero; there is no x-intercept")
    value = -fit.intercept / fit.slope
    return (fit.residual_variance / fit.slope**2) * (
        1.0 / fit.weight_total + (value - fit.x_mean) ** 2 / fit.sum_squared_x_deviations
    )


def x_intercept_fieller(fit: LineFit, *, confidence: float = 0.95) -> FiellerInterval:
    r"""Exact confidence set for the x-intercept by Fieller's theorem.

    The set is every abscissa the fitted line could plausibly cross zero at:

    .. math::

        S = \left\{x : (a + bx)^2 \le t^2 s^2
            \left[\tfrac{1}{W} + \tfrac{(x - \bar{x})^2}{S_{xx}}\right]\right\}

    with ``t`` the Student-t quantile at ``n - 2`` degrees of freedom. Writing
    ``u = x - xbar`` and ``D = x0 - xbar`` this is a quadratic inequality in ``u``,

    .. math::

        (1 - g)u^2 - 2Du + (D^2 - k) \le 0, \qquad
        g = \frac{t^2 s^2}{b^2 S_{xx}}, \qquad k = \frac{t^2 s^2}{W b^2}

    whose half-discriminant is ``Delta = g D**2 + (1 - g) k``. Note ``g`` is exactly
    ``(t * SE(b) / b)**2``, so ``g >= 1`` is the same statement as "the slope is not
    significant at this confidence level".

    The three geometries
    --------------------
    The leading coefficient is ``1 - g``, and its sign decides the shape:

    * ``g < 1``: the parabola opens upward, the set lies *between* the roots, and
      ``Delta > 0`` automatically because both of its terms are positive. The result
      is the bounded interval ``[lower, upper]``.
    * ``g > 1`` with ``Delta > 0``: the parabola opens downward, so the set lies
      *outside* the roots. It is the union of two disjoint half-lines, and the point
      estimate lies outside the excluded middle -- substituting ``u = D`` gives
      ``-gD**2 - k < 0``, so ``x0`` always satisfies the inequality. Returning the two
      roots labelled "lower" and "upper" without saying they bound the *excluded*
      region is the failure mode this type exists to prevent.
    * ``g > 1`` with ``Delta <= 0``: the downward parabola never reaches zero and the
      set is the whole real line.

    Exactly at ``g = 1`` the quadratic degenerates to a linear inequality and the set
    is a single half-line; that is a measure-zero case, reported as ``"exclusive"``
    with one infinite bound so the complement semantics still describe it.

    Behaviour when the set is unbounded
    -----------------------------------
    This function *returns* a result with ``bounded=False`` rather than raising
    :class:`~reservoir_lab.errors.NotIdentifiableError`. The choice is deliberate:
    the excluded middle is genuine information about which values the data rule out,
    and an exception would discard it. A caller that wants a hard stop should test
    ``bounded`` and raise. What must never happen is printing a finite ``+/-`` error
    bar in this regime -- the true set has no finite width.

    Parameters
    ----------
    fit:
        An ``"ols"`` or ``"wls"`` :class:`LineFit`. Fieller's construction here
        assumes Normal errors in the ordinate only, which is the least-squares model;
        it is not valid as written for an errors-in-variables fit.
    confidence:
        Two-sided confidence level, strictly inside ``(0, 1)``.

    Returns
    -------
    FiellerInterval
        Bounds in the units of ``x``, with ``kind`` naming the geometry.

    Validity window and what this does not do
    -----------------------------------------
    Exact under the least-squares model: coverage equals the nominal level at every
    signal-to-noise ratio, unlike the delta-method interval, which degrades to about
    0.78 coverage at nominal 0.95 when the slope is barely significant. It does not
    make an unidentifiable x-intercept identifiable, does not correct for a wrong
    physical model (a water-drive p/Z curve fitted with a straight line produces a
    tight Fieller set around a badly biased value), and does not apply to Deming or
    York fits.

    Raises
    ------
    InvalidInputError
        If ``fit`` is not a least-squares fit, or ``confidence`` is outside ``(0, 1)``.
    NotIdentifiableError
        If the fitted slope is exactly zero.
    """
    if not isinstance(fit, LineFit):
        raise InvalidInputError(f"fit must be a LineFit, got {type(fit).__name__}")
    if fit.method not in ("ols", "wls"):
        raise InvalidInputError(
            f"Fieller's construction as implemented assumes Normal errors in y only, so "
            f"it applies to least-squares fits; got method {fit.method!r}. For an "
            f"errors-in-variables fit, use York's axis-interchange route instead."
        )
    if fit.slope == 0.0:
        raise NotIdentifiableError(
            "the fitted slope is exactly zero, so the line has no x-intercept to bound"
        )
    half = _half_confidence(confidence)
    conf = 2.0 * half

    t = student_t_quantile(0.5 + half, fit.degrees_of_freedom)
    slope = fit.slope
    point = -fit.intercept / slope
    offset = point - fit.x_mean
    g = t * t * fit.residual_variance / (slope * slope * fit.sum_squared_x_deviations)
    k = t * t * fit.residual_variance / (fit.weight_total * slope * slope)
    discriminant = g * offset * offset + (1.0 - g) * k

    def result(kind: str, bounded: bool, lower: float, upper: float) -> FiellerInterval:
        """Fill in the fields every branch shares, so no branch can omit one."""
        return FiellerInterval(
            kind=kind,
            bounded=bounded,
            lower=lower,
            upper=upper,
            point_estimate=point,
            g=g,
            discriminant=discriminant,
            confidence=conf,
            degrees_of_freedom=fit.degrees_of_freedom,
            n_points=fit.n_points,
            method=fit.method,
        )

    # Branch on g BEFORE dividing by (1 - g). Relying on IEEE infinity here silently
    # flips the orientation of the bounds for g > 1 and produces a "confidence
    # interval" that excludes the point estimate.
    if g < 1.0:
        root = math.sqrt(discriminant)
        return result(
            FIELLER_BOUNDED,
            True,
            fit.x_mean + (offset - root) / (1.0 - g),
            fit.x_mean + (offset + root) / (1.0 - g),
        )

    if g == 1.0:
        # Degenerate linear case: -2*D*u + (D^2 - k) <= 0. A single half-line, which
        # the complement semantics of FIELLER_EXCLUSIVE describe with one infinite edge.
        if offset == 0.0:
            return result(FIELLER_WHOLE_LINE, False, -_INF, _INF)
        edge = fit.x_mean + (offset * offset - k) / (2.0 * offset)
        if offset > 0.0:
            return result(FIELLER_EXCLUSIVE, False, -_INF, edge)
        return result(FIELLER_EXCLUSIVE, False, edge, _INF)

    if discriminant <= 0.0:
        return result(FIELLER_WHOLE_LINE, False, -_INF, _INF)

    # g > 1: dividing by the negative (1 - g) swaps which root is the smaller, so the
    # "+root" branch is the LOWER edge of the excluded middle here.
    root = math.sqrt(discriminant)
    return result(
        FIELLER_EXCLUSIVE,
        False,
        fit.x_mean + (offset + root) / (1.0 - g),
        fit.x_mean + (offset - root) / (1.0 - g),
    )


# ---------------------------------------------------------------------------
# Moving-block bootstrap
# ---------------------------------------------------------------------------


def moving_block_bootstrap(
    x: Sequence[float],
    y: Sequence[float],
    *,
    block_length: int,
    replicates: int,
    seed: int,
    statistic: Callable[[tuple[float, ...], tuple[float, ...]], float],
) -> BootstrapResult:
    """Resample ordered ``(x, y)`` pairs in overlapping blocks and re-evaluate a statistic.

    Why blocks, and why the i.i.d. bootstrap is wrong here
    ------------------------------------------------------
    The ordinary pairs bootstrap draws points independently, which assumes the
    measurement errors are independent between surveys. A pressure gauge that drifts
    breaks that assumption in the most damaging way available: its error at survey
    ``t`` is strongly correlated with its error at survey ``t+1``, so a run of surveys
    shares a common offset. That shared offset moves the whole fitted line, and
    therefore moves the x-intercept, without producing any extra scatter *within* the
    run. An i.i.d. resample destroys the ordering, so the resampled series looks like
    white noise, the run-to-run component disappears, and the bootstrap standard error
    collapses to the much smaller i.i.d. value. Measured on a 48-survey AR(1) series
    with lag-1 correlation 0.9: the true sampling standard deviation of the gas in
    place was 1.24 Bscf, the i.i.d. pairs bootstrap reported 0.22 -- a five-fold
    understatement, in the direction that makes a decision look better supported than
    it is. The delete-one jackknife fails identically, for the same reason.

    Resampling consecutive blocks of surveys keeps the local dependence intact inside
    each block, so the run-to-run component survives into the resample. The scheme is
    the moving (overlapping) block bootstrap of Kuensch (1989): blocks
    ``B_j = (z_j, ..., z_{j+l-1})`` for ``j = 1..n-l+1``, ``ceil(n/l)`` starts drawn
    uniformly with replacement, concatenated and truncated to ``n``. Pairs move
    together, so an errors-in-variables structure survives the resample. At
    ``block_length = 1`` this reduces exactly to the i.i.d. pairs bootstrap, which is
    a useful null: any test that generates independent data cannot tell the two apart.

    Choosing the block length, and why there is no default
    ------------------------------------------------------
    ``block_length`` is required because every rule available is either asymptotic or a
    heuristic, and hiding that behind a default would misrepresent it.

    * The rate rule of Hall, Horowitz and Jing (1995) gives an MSE-optimal length of
      order ``n**(1/3)`` for estimating a variance, which is this case. Its
      proportionality constant is not something this repository has from the source,
      and at the sample sizes a pressure-survey history provides -- ten to sixty
      surveys -- ``n**(1/3)`` is only 2.2 to 3.9, far shorter than a drifting gauge's
      correlation length. Applied blindly at ``n = 48`` with AR(1) correlation 0.9 it
      recovered about a third of the true sampling standard deviation.
    * The physical floor is the integrated autocorrelation time of the drift,
      ``tau = (1 + rho) / (1 - rho)`` for an AR(1) error, which is 19 surveys at
      ``rho = 0.9``.
    * :func:`suggested_block_length` combines the two by taking the larger, and says in
      its own return value that this combination is a repository heuristic rather than
      a published rule.

    Report the block length you used alongside any standard error it produced;
    :class:`BootstrapResult` carries it so a report cannot omit it.

    Parameters
    ----------
    x, y:
        Equal-length sequences, **in survey order**. The ordering carries the
        dependence structure the whole method rests on, so nothing is sorted here.
    block_length:
        Number of consecutive pairs per block, an integer in ``1..n-1``. The whole
        series is not an allowed block: it leaves one possible start, so every
        resample reproduces the data and the standard error is zero by construction.
    replicates:
        Number of resamples. At least about 1000 for a standard error and 5000 for a
        percentile interval.
    seed:
        Integer seed for a locally constructed :class:`random.Random`. There is no
        implicit global RNG, so two calls with equal arguments return equal results.
    statistic:
        Callable taking ``(x_resample, y_resample)`` as two tuples and returning one
        float -- typically ``lambda xs, ys: x_intercept(ols_line(xs, ys)).value``.

    Returns
    -------
    BootstrapResult
        Carrying every resampled value, the standard error (sample standard deviation
        of those values, ``ddof=1``), the bootstrap bias estimate, the number of
        distinct block starts the scheme drew from, and the count of resamples on which
        ``statistic`` refused to produce a number.

    Failed replicates
    -----------------
    A block resample can be degenerate -- every drawn block identical, so all abscissae
    coincide and no line exists. Such a replicate is counted in
    ``replicates_failed`` and excluded, rather than being silently retried with a new
    draw, which would bias the resampling distribution. Only a
    :class:`~reservoir_lab.errors.ReservoirLabError` is caught this way; any other
    exception from ``statistic`` propagates, because it is a defect in the caller's
    code and not a property of the data.

    Validity window and what this does not do
    -----------------------------------------
    It needs ``n`` much larger than ``block_length``; below roughly thirty surveys a
    block bootstrap has very little to work with, and at ``n = 48`` with strong drift
    even a well-chosen block length still understated the truth by about 20 percent.
    It is not the circular or stationary bootstrap, it computes no BCa interval, it
    does not choose the block length, and it cannot repair a resampling scheme applied
    to data whose ordering is wrong.

    Raises
    ------
    InvalidInputError
        Non-finite or mismatched inputs, fewer than three points, a ``block_length``
        outside ``1..n-1``, a non-positive ``replicates``, a non-integer ``seed``, or a
        ``statistic`` that is not callable or does not return a finite float.
    NotIdentifiableError
        If fewer than two replicates produced a value, so no spread can be measured.
    """
    xs, ys = _paired_inputs(x, y)
    n = len(xs)
    if not isinstance(block_length, int) or isinstance(block_length, bool):
        raise InvalidInputError(f"block_length must be an int, got {block_length!r}")
    if not 1 <= block_length <= n - 1:
        # The upper bound is n - 1, not n. At block_length == n there is exactly one
        # start, every drawn block is the whole series, every resample is the original
        # data, and the reported standard error is fsum rounding noise -- around 1e-14
        # -- with replicates_failed = 0 and nothing else in the result saying that no
        # resampling took place. A standard error of zero handed back without
        # qualification is worse than a refusal.
        raise InvalidInputError(
            f"block_length must lie in 1..{n - 1} for {n} points, got {block_length}. "
            f"A block as long as the series admits only one start, so every resample "
            f"is the original data and the standard error is identically zero. The "
            f"resample distribution is already thin well before that: the number of "
            f"distinct starts is n - block_length + 1, so keep block_length far below "
            f"n and read n_starts off the result."
        )
    if not isinstance(replicates, int) or isinstance(replicates, bool) or replicates < 1:
        raise InvalidInputError(f"replicates must be a positive int, got {replicates!r}")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise InvalidInputError(
            f"seed must be an int; the RNG is constructed locally from it so that two "
            f"calls with equal arguments agree bit for bit. Got {seed!r}"
        )
    if not callable(statistic):
        raise InvalidInputError(f"statistic must be callable, got {type(statistic).__name__}")

    point_estimate = require_finite(statistic(xs, ys), "statistic(x, y)")

    rng = random.Random(seed)
    n_starts = n - block_length + 1
    n_blocks = -(-n // block_length)  # ceil

    values: list[float] = []
    failed = 0
    for _ in range(replicates):
        resample_x: list[float] = []
        resample_y: list[float] = []
        for _block in range(n_blocks):
            start = rng.randrange(n_starts)
            resample_x.extend(xs[start : start + block_length])
            resample_y.extend(ys[start : start + block_length])
        del resample_x[n:]
        del resample_y[n:]
        try:
            value = statistic(tuple(resample_x), tuple(resample_y))
        except ReservoirLabError:
            # A degenerate resample is a property of the data, not a defect. Count it
            # and move on; redrawing until it succeeds would bias the distribution.
            failed += 1
            continue
        values.append(require_finite(value, "statistic(resample)"))

    used = len(values)
    if used < 2:
        raise NotIdentifiableError(
            f"only {used} of {replicates} block resamples produced a value, so no "
            f"resampling spread is measurable. With {n} points and block length "
            f"{block_length} the resamples are probably degenerate; shorten the block or "
            f"gather more surveys."
        )
    mean = math.fsum(values) / used
    standard_error = math.sqrt(math.fsum((v - mean) ** 2 for v in values) / (used - 1))

    return BootstrapResult(
        point_estimate=point_estimate,
        values=tuple(values),
        standard_error=standard_error,
        mean=mean,
        bias=mean - point_estimate,
        block_length=block_length,
        n_starts=n_starts,
        n_points=n,
        replicates_requested=replicates,
        replicates_used=used,
        replicates_failed=failed,
        seed=seed,
        method="moving_block",
    )


def suggested_block_length(residuals: Sequence[float]) -> BlockLengthAdvice:
    """Suggest a moving-block length from a residual series. Repository heuristic.

    Combines two things that are not the same kind of object, which is why the result
    exposes both rather than only their maximum:

    * ``rate_rule = ceil(n**(1/3))`` -- the Hall, Horowitz and Jing (1995) rate for
      estimating a variance. The exponent is from the published abstract; the
      proportionality constant is not in hand, so this takes it as one. It is an
      asymptotic statement and is far too short at pressure-survey sample sizes.
    * ``autocorrelation_floor = max(1, ceil(tau))`` with ``tau = (1 + rho) / (1 - rho)``,
      the integrated autocorrelation time of an AR(1) error with lag-1 correlation
      ``rho`` estimated from the residuals. A negative ``rho`` puts ``tau`` below 1,
      where a block length is meaningless, so the *floor* is clamped at 1. The reported
      ``integrated_autocorrelation_time`` is never clamped: it is always
      ``(1 + rho) / (1 - rho)`` as computed from the caller's residuals, so the two
      numbers the recommendation rests on stay auditable separately.

    The recommendation is the larger of the two, clipped to ``1..n``. **This
    combination is not from the literature.** It is this repository's rule, stated so
    it can be argued with, and it is recorded in the returned ``rule`` string.

    Parameters
    ----------
    residuals:
        Residuals in survey order, at least three of them. Order is the entire content
        of the estimate, so nothing is sorted.

    Returns
    -------
    BlockLengthAdvice

    What this does not do
    ---------------------
    It is not the Politis-White automatic selector, it does no cross-validation, and
    it does not check that an AR(1) model of the drift is appropriate.

    Raises
    ------
    InvalidInputError
        Non-finite values or fewer than three residuals.
    NotIdentifiableError
        If the residuals have zero variance, so no autocorrelation is defined.
    """
    values = as_float_sequence(residuals, "residuals")
    require_min_length(values, "residuals", 3, "a lag-1 autocorrelation estimate")
    n = len(values)
    mean = math.fsum(values) / n
    denominator = math.fsum((v - mean) ** 2 for v in values)
    if denominator <= 0.0:
        raise NotIdentifiableError(
            "the residuals have zero variance, so their lag-1 autocorrelation is not "
            "defined and no block length can be inferred from them."
        )
    numerator = math.fsum((values[i] - mean) * (values[i - 1] - mean) for i in range(1, n))
    rho = numerator / denominator

    rate_rule = math.ceil(n ** (1.0 / 3.0))
    # rho is strictly inside (-1, 1) whenever the variance guard above has passed:
    # |numerator| <= sum|d_i d_{i-1}| <= denominator - (d_0**2 + d_{n-1}**2)/2 by AM-GM,
    # and equality would force every deviation to zero. So 1 - rho is safely positive.
    tau = (1.0 + rho) / (1.0 - rho)
    # The clamp belongs to the block length, not to tau. A block shorter than one point
    # is meaningless, so the floor is clamped; reporting the clamped value as the
    # integrated autocorrelation time would hand the caller a number that was never
    # computed from their residuals, and tau is reported precisely so it can be argued
    # with. For rho <= 0 the two differ: tau is then in (0, 1] and the floor is 1.
    floor = max(1, math.ceil(tau))
    recommended = min(max(rate_rule, floor), n)

    return BlockLengthAdvice(
        recommended=recommended,
        rate_rule=rate_rule,
        autocorrelation_floor=floor,
        lag1_correlation=rho,
        integrated_autocorrelation_time=tau,
        n_points=n,
        rule=(
            "repository heuristic: max(ceil(n**(1/3)), ceil((1+rho)/(1-rho))), the "
            "Hall-Horowitz-Jing variance rate with unit constant against an AR(1) "
            "integrated autocorrelation floor. The combination is not a published rule."
        ),
    )

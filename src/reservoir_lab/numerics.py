"""Shared root finding and quadrature.

The physics modules do not write their own iterations. There are two reasons, and the
second is the important one.

The first is ordinary reuse. The second is that a naive Newton iteration on a
correlation such as Dranchuk-Abou-Kassem will, at high reduced pressure, take a step
that lands on a non-physical negative reduced density, then diverge or return a
plausible-looking wrong root. That failure is silent. Every solver here is therefore
**bracketed**: a sign-changing interval is established first and the iterate is never
allowed to leave it, so the method either returns a root inside a known bracket or
raises. It cannot return a number from outside the bracket.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .errors import ConvergenceError, InvalidInputError
from .validation import require_finite

__all__ = [
    "QuadratureConvergence",
    "bracket_sign_change",
    "composite_simpson",
    "convergence_study",
    "opposite_signs",
    "richardson_order",
    "safeguarded_newton",
]


def opposite_signs(a: float, b: float) -> bool:
    """Return True when ``a`` and ``b`` are both non-zero and of opposite sign.

    The obvious test, ``a * b < 0``, is wrong and wrong silently. Two residuals of
    magnitude 1e-170 have a product that underflows to +-0.0, so the comparison reports
    no sign change where there plainly is one, and a bracketing routine built on it
    returns a number that is not a root. Residuals that small are not exotic: they arise
    whenever a physical residual is expressed in a unit that makes it tiny, and nothing
    about the algorithm should depend on the unit the caller chose.

    Comparing signs directly cannot underflow. ``math.copysign`` is used rather than
    ``a < 0`` so that the two signed zeros are distinguished consistently; exact zeros
    are handled by the callers before this is reached, since a zero residual means the
    root has been found rather than that a bracket exists.
    """
    if a == 0.0 or b == 0.0:
        return False
    return math.copysign(1.0, a) != math.copysign(1.0, b)


def bracket_sign_change(
    function: Callable[[float], float],
    *,
    lower: float,
    upper_guess: float,
    growth: float = 2.0,
    max_expansions: int = 80,
) -> tuple[float, float]:
    """Find ``(a, b)`` with ``a < b`` and ``f(a) * f(b) <= 0``.

    Starts from ``lower`` and expands the upper end geometrically. Returns as soon as a
    sign change is captured.

    Raises
    ------
    ConvergenceError
        If no sign change is found within ``max_expansions`` expansions. The message
        reports the widest interval tried, so the caller can tell "no root here" from
        "the search was too timid".
    """
    if not (upper_guess > lower):
        raise InvalidInputError(f"upper_guess {upper_guess} must exceed lower {lower}")
    f_low = function(lower)
    if f_low == 0.0:
        return lower, lower
    upper = upper_guess
    for _ in range(max_expansions):
        f_up = function(upper)
        if f_up == 0.0 or opposite_signs(f_low, f_up):
            return lower, upper
        upper = lower + (upper - lower) * growth
    raise ConvergenceError(
        f"no sign change of the residual between {lower!r} and {upper!r}",
        iterations=max_expansions,
        last_value=upper,
        last_residual=function(upper),
    )


def safeguarded_newton(
    function: Callable[[float], float],
    derivative: Callable[[float], float],
    *,
    bracket: tuple[float, float],
    initial_guess: float | None = None,
    tolerance: float = 1.0e-12,
    max_iterations: int = 100,
    description: str = "root",
) -> float:
    """Solve ``function(x) == 0`` inside ``bracket`` using Newton with bisection fallback.

    The iterate is kept inside the bracket at all times. A Newton step is taken when it
    lands inside the current bracket and reduces the interval; otherwise the step is
    replaced by bisection. This gives Newton's speed where the function is well behaved
    and bisection's guarantee where it is not.

    Parameters
    ----------
    bracket:
        ``(a, b)`` with a sign change between them. Obtain one with
        :func:`bracket_sign_change` if it is not known analytically.
    tolerance:
        Convergence is declared when the bracket width falls below
        ``tolerance * max(1, |x|)`` or the residual is exactly zero. The relative form
        matters because reduced density is order 0.1 while pseudopressure is order 1e8.

    Raises
    ------
    InvalidInputError
        If the bracket does not contain a sign change.
    ConvergenceError
        If the iteration budget is exhausted.
    """
    low, high = bracket
    if not (low <= high):
        low, high = high, low
    f_low = function(low)
    f_high = function(high)
    if f_low == 0.0:
        return low
    if f_high == 0.0:
        return high
    if not opposite_signs(f_low, f_high):
        raise InvalidInputError(
            f"bracket ({low!r}, {high!r}) does not contain a sign change for {description}: "
            f"f(low)={f_low!r}, f(high)={f_high!r}"
        )

    x = initial_guess if initial_guess is not None else 0.5 * (low + high)
    if not (low <= x <= high):
        x = 0.5 * (low + high)

    for _iteration in range(1, max_iterations + 1):
        fx = function(x)
        if fx == 0.0:
            return x
        # Maintain the bracket around the current iterate.
        if opposite_signs(f_low, fx):
            high, f_high = x, fx
        else:
            low, f_low = x, fx

        width = high - low
        if width <= tolerance * max(1.0, abs(x)):
            return 0.5 * (low + high)

        dfx = derivative(x)
        step_ok = False
        candidate = x - fx / dfx if dfx != 0.0 and math.isfinite(dfx) else None
        # Take the Newton step only if it stays inside the bracket AND makes real
        # progress; a step that barely moves wastes an iteration that bisection would
        # have used to halve the interval.
        if (
            candidate is not None
            and low < candidate < high
            and (abs(candidate - x) > 0.5 * width * 1e-3 or abs(fx) < abs(f_low))
        ):
            x, step_ok = candidate, True
        if not step_ok:
            x = 0.5 * (low + high)

    raise ConvergenceError(
        f"{description} did not converge within the iteration budget",
        iterations=max_iterations,
        last_value=x,
        last_residual=function(x),
    )


def composite_simpson(
    integrand: Callable[[float], float],
    lower: float,
    upper: float,
    intervals: int,
) -> float:
    """Composite Simpson's rule on ``intervals`` equal subintervals.

    ``intervals`` must be even and positive. Returns ``0.0`` exactly when
    ``lower == upper``, and negates the result for a reversed interval, so that the
    result behaves like an integral rather than like a loop over a grid.

    Simpson is chosen over a black-box adaptive routine deliberately: a fixed rule on a
    controlled grid is what makes the convergence-order study in :func:`convergence_study`
    meaningful. An adaptive routine hides its grid and its error estimate, so a study
    built on one demonstrates nothing about the integrand.
    """
    if intervals <= 0 or intervals % 2 != 0:
        raise InvalidInputError(f"intervals must be a positive even integer, got {intervals}")
    # Guarding the limits matters as much as guarding the interval count: an infinite
    # upper limit returns inf and a NaN lower limit returns nan, and contract C3 forbids
    # returning a sentinel to signal a problem the caller never asked about.
    lower = require_finite(lower, "lower")
    upper = require_finite(upper, "upper")
    if lower == upper:
        return 0.0
    sign = 1.0
    if upper < lower:
        lower, upper, sign = upper, lower, -1.0

    step = (upper - lower) / intervals
    total = integrand(lower) + integrand(upper)
    for index in range(1, intervals):
        weight = 4.0 if index % 2 else 2.0
        total += weight * integrand(lower + index * step)
    return sign * total * step / 3.0


@dataclass(frozen=True)
class QuadratureConvergence:
    """Result of a grid-refinement study.

    Attributes
    ----------
    interval_counts:
        The grids used, in increasing order.
    values:
        The quadrature result on each grid.
    observed_orders:
        Order of accuracy estimated from each successive triple of grids by Richardson
        extrapolation. For composite Simpson on a smooth integrand these approach 4.
    richardson_estimate:
        Richardson-extrapolated value from the two finest grids, used as a proxy for
        the exact integral when no closed form exists.
    relative_changes:
        Relative change between successive grids, a practical stopping diagnostic.
    """

    interval_counts: tuple[int, ...]
    values: tuple[float, ...]
    observed_orders: tuple[float, ...]
    richardson_estimate: float
    relative_changes: tuple[float, ...]

    def best(self) -> float:
        """Return the finest-grid value."""
        return self.values[-1]


def richardson_order(coarse: float, medium: float, fine: float, refinement: float = 2.0) -> float:
    """Estimate the observed order of accuracy from three successively refined results.

    With errors behaving as ``C h**p`` and each grid refined by ``refinement``::

        p = log((coarse - medium) / (medium - fine)) / log(refinement)

    Returns ``nan`` when the differences are zero or of opposite sign, which happens
    once round-off dominates truncation error. A ``nan`` there is honest: the order is
    genuinely not estimable from those three values, and returning a number would
    invent one.
    """
    numerator = coarse - medium
    denominator = medium - fine
    if denominator == 0.0 or numerator == 0.0:
        return math.nan
    ratio = numerator / denominator
    if ratio <= 0.0:
        return math.nan
    return math.log(ratio) / math.log(refinement)


def convergence_study(
    integrand: Callable[[float], float],
    lower: float,
    upper: float,
    interval_counts: Sequence[int],
) -> QuadratureConvergence:
    """Evaluate a quadrature on successively refined grids and report the observed order.

    ``interval_counts`` must be increasing, even, and successively doubling for the
    Richardson order estimate to be valid; the doubling is checked and a non-doubling
    sequence raises rather than producing a meaningless order.
    """
    counts = tuple(int(n) for n in interval_counts)
    if len(counts) < 3:
        raise InvalidInputError("a convergence study needs at least three grids")
    for index in range(1, len(counts)):
        if counts[index] != 2 * counts[index - 1]:
            raise InvalidInputError(
                f"interval_counts must double successively for the Richardson estimate to be "
                f"valid, got {counts[index - 1]} -> {counts[index]}"
            )
    values = tuple(composite_simpson(integrand, lower, upper, n) for n in counts)
    orders = tuple(richardson_order(values[i - 2], values[i - 1], values[i]) for i in range(2, len(values)))
    changes = tuple(
        abs(values[i] - values[i - 1]) / max(abs(values[i]), 1e-300) for i in range(1, len(values))
    )
    # Richardson extrapolation using the observed order where it is estimable, and the
    # theoretical Simpson order otherwise.
    order = orders[-1] if orders and math.isfinite(orders[-1]) and orders[-1] > 0 else 4.0
    factor = 2.0**order
    extrapolated = values[-1] + (values[-1] - values[-2]) / (factor - 1.0)
    return QuadratureConvergence(
        interval_counts=counts,
        values=values,
        observed_orders=orders,
        richardson_estimate=extrapolated,
        relative_changes=changes,
    )

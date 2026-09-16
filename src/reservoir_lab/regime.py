"""Identify an infinite-acting radial-flow window from a diagnostic response.

What this module is for
-----------------------
Case B1 was handed its interpretation window. Case B2 is not, and this is the module that
has to find one. The distinction matters more than it sounds: B1's own placement sweep
measured the cost of getting the window wrong as ``0.5196 / t_D,min`` in permeability, a
3322x spread across three and a half decades of placement, against 1.18x across a
hundredfold change in sampling density. Where the window sits dominates.

The one rule this module must never break
-----------------------------------------
**It sees only what an interpreter sees.** Elapsed time, pressure change, and the derivative
computed from them. It never receives the true permeability, the true skin, the true storage
coefficient, the true start of radial flow, or any regime label from a generator. Those
belong to scoring, which happens afterwards and elsewhere.

That separation is enforced by this module's signature: :func:`identify_radial_window` takes
three sequences and a settings object, and there is no parameter through which truth could
arrive. ``tests/test_regime.py`` asserts the signature, because a rule that quietly reads the
answer is the failure mode this whole case exists to rule out.

The rule, as pre-registered
---------------------------
Fixed in ``cases/B2_wellbore_storage_window/protocol.md`` section 7 before any result
existed. Four conditions, all required:

(a) **Flatness.** Radial flow has a constant derivative, so its log-log slope is zero. A
    candidate interval needs ``|m| <= flatness`` at every point, where
    ``m = d ln D / d ln t``.

(b) **Not storage-contaminated.** During pure wellbore storage the derivative equals the
    pressure change identically -- not approximately, identically, because
    ``dΔp/d ln t = t dΔp/dt = t (qB/24C) = Δp``. A point retaining more than
    ``storage_ratio`` of that identity is excluded. This is why the rule needs no onset
    criterion from the literature: it uses an identity rather than a remembered number.

(c) **Minimum extent.** At least ``min_decades`` of log-10 time and ``min_points``
    observations, so that a brief flat patch inside the storage-to-radial transition cannot
    qualify.

(d) **Edges.** Points without a full Bourdet window on both sides carry no derivative and
    never reach this module.

Selection takes the widest qualifying interval in log-10 time; ties go to the later one,
which sits further from the transition.

**If nothing qualifies, the answer is INCONCLUSIVE.** There is deliberately no
best-available fallback: declining to report is a result, and a rule that always produces a
window cannot tell you when the data does not support one.

Standard library only, like the rest of ``reservoir_lab``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .errors import InvalidInputError

__all__ = [
    "RadialWindow",
    "WindowSettings",
    "identify_radial_window",
    "local_log_slope",
]


@dataclass(frozen=True)
class WindowSettings:
    """The pre-registered rule's constants. Frozen, and identical for every experiment.

    Defaults are the values derived in protocol section 7. ``flatness`` in particular is not
    a taste: it is ``A / (W ln 10)`` with ``A`` the permeability-thickness accuracy target
    and ``W`` the minimum window extent, because a derivative whose log-log slope is bounded
    by ``eps`` over ``W`` cycles varies by at most ``eps W ln 10`` in relative terms, and
    permeability-thickness is inversely proportional to the plateau.
    """

    #: Maximum |d ln D / d ln t| inside the window. A/(W ln10) = 0.05/ln10.
    flatness: float = 0.05 / math.log(10.0)
    #: Maximum D/Δp admitted. The storage identity is 1.0; this keeps an order away from it.
    storage_ratio: float = 0.10
    #: Minimum window extent in log-10 cycles.
    min_decades: float = 1.0
    #: Minimum number of observations in the window.
    min_points: int = 15

    def __post_init__(self) -> None:
        """Reject settings that would make the rule meaningless."""
        if not (self.flatness > 0.0 and math.isfinite(self.flatness)):
            raise InvalidInputError("flatness must be finite and positive")
        if not (self.storage_ratio > 0.0 and math.isfinite(self.storage_ratio)):
            raise InvalidInputError("storage_ratio must be finite and positive")
        if not (self.min_decades > 0.0 and math.isfinite(self.min_decades)):
            raise InvalidInputError("min_decades must be finite and positive")
        if self.min_points < 3:
            raise InvalidInputError("min_points must be at least 3")


@dataclass(frozen=True)
class RadialWindow:
    """The outcome of the rule. ``found`` false means INCONCLUSIVE, and carries the reason."""

    found: bool
    #: Index range into the derivative series, inclusive of both ends.
    start_index: int = -1
    end_index: int = -1
    #: Times bounding the window, in the unit supplied.
    start_time: float = float("nan")
    end_time: float = float("nan")
    #: Extent in log-10 cycles.
    decades: float = 0.0
    points: int = 0
    #: Why no window was selected. Empty when one was.
    reason: str = ""
    #: How many candidate intervals satisfied every condition.
    candidates: int = 0


def local_log_slope(
    time: Sequence[float], response: Sequence[float], *, smoothing_l: float
) -> tuple[tuple[int, ...], tuple[float, ...]]:
    """Return ``(indices, d ln(response) / d ln(time))`` by the derivative's three-point rule.

    Indices, not times. An earlier version returned reconstructed times and the caller matched
    them back by dictionary lookup; ``math.exp(math.log(t))`` is not bitwise equal to ``t``, so
    that silently discarded valid points. Returning the original index removes the round trip.

    Applied to an already-smoothed derivative this compounds the smoothing, so the slope is
    smoother than the data. That is a property of the rule, stated in the protocol rather
    than tuned away, and the pre-registered ``L`` sensitivity is what measures it.

    Points where ``response <= 0`` have no logarithm and are dropped, with their times. Noise
    can drive a derivative non-positive, and silently substituting a floor there would invent
    a slope the data does not support.
    """
    if len(time) != len(response):
        raise InvalidInputError("time and response must have the same length")
    xs: list[float] = []
    ys: list[float] = []
    where: list[int] = []
    for i, (t, r) in enumerate(zip(time, response, strict=True)):
        if not (math.isfinite(t) and math.isfinite(r)):
            raise InvalidInputError("time and response must be finite")
        if t <= 0.0:
            raise InvalidInputError("time must be strictly positive")
        if r > 0.0:
            xs.append(math.log(t))
            ys.append(math.log(r))
            where.append(i)
    if len(xs) < 3:
        return (), ()

    # Bourdet's three-point rule on (ln t, ln D), with the same L selection.
    out_i: list[int] = []
    out_m: list[float] = []
    n = len(xs)
    for i in range(n):
        j = None
        for cand in range(i - 1, -1, -1):
            if xs[i] - xs[cand] >= smoothing_l:
                j = cand
                break
        k = None
        for cand in range(i + 1, n):
            if xs[cand] - xs[i] >= smoothing_l:
                k = cand
                break
        if j is None or k is None:
            continue
        dx1 = xs[i] - xs[j]
        dx2 = xs[k] - xs[i]
        m = ((ys[i] - ys[j]) / dx1 * dx2 + (ys[k] - ys[i]) / dx2 * dx1) / (dx1 + dx2)
        out_i.append(where[i])
        out_m.append(m)
    return tuple(out_i), tuple(out_m)


def identify_radial_window(
    derivative_time: Sequence[float],
    derivative: Sequence[float],
    pressure_change: Sequence[float],
    *,
    settings: WindowSettings,
    smoothing_l: float,
) -> RadialWindow:
    """Select a radial-flow interval, or decline.

    Parameters are exactly what an interpreter has: the times at which a derivative exists,
    the derivative, and the pressure change at those same times. **There is deliberately no
    parameter through which a true permeability, skin, storage coefficient or regime label
    could be passed.**

    Returns a :class:`RadialWindow`. ``found`` false is INCONCLUSIVE and is a legitimate
    answer, not an error.
    """
    n = len(derivative_time)
    if not (n == len(derivative) == len(pressure_change)):
        raise InvalidInputError("derivative_time, derivative and pressure_change must have the same length")
    if n == 0:
        return RadialWindow(found=False, reason="no derivative points supplied")

    slope_i, slope_m = local_log_slope(derivative_time, derivative, smoothing_l=smoothing_l)
    if not slope_i:
        return RadialWindow(
            found=False,
            reason="no point has a full smoothing window on both sides of the log-slope rule",
        )

    admissible: list[int] = []
    for i, m in zip(slope_i, slope_m, strict=True):
        if abs(m) > settings.flatness:
            continue
        dp = pressure_change[i]
        if dp <= 0.0:
            continue
        if derivative[i] / dp > settings.storage_ratio:
            continue
        admissible.append(i)

    if not admissible:
        return RadialWindow(
            found=False,
            reason="no point is both flat enough and free of the storage identity",
        )

    # Maximal contiguous runs of admissible indices.
    runs: list[tuple[int, int]] = []
    run_start = admissible[0]
    previous = admissible[0]
    for i in admissible[1:]:
        if i == previous + 1:
            previous = i
            continue
        runs.append((run_start, previous))
        run_start = i
        previous = i
    runs.append((run_start, previous))

    qualifying: list[tuple[int, int, float, int]] = []
    for a, b in runs:
        points = b - a + 1
        decades = math.log10(derivative_time[b] / derivative_time[a]) if b > a else 0.0
        if points < settings.min_points or decades < settings.min_decades:
            continue
        qualifying.append((a, b, decades, points))

    if not qualifying:
        widest = max((math.log10(derivative_time[b] / derivative_time[a]) if b > a else 0.0) for a, b in runs)
        most = max(b - a + 1 for a, b in runs)
        return RadialWindow(
            found=False,
            reason=(
                f"no interval reaches the minimum extent: widest was {widest:.3f} log cycles "
                f"against {settings.min_decades} required, and the largest held {most} points "
                f"against {settings.min_points} required"
            ),
        )

    # Widest in log-10 time; a tie goes to the later interval, which sits further from the
    # storage transition.
    best = max(qualifying, key=lambda q: (q[2], derivative_time[q[0]]))
    a, b, decades, points = best
    return RadialWindow(
        found=True,
        start_index=a,
        end_index=b,
        start_time=derivative_time[a],
        end_time=derivative_time[b],
        decades=decades,
        points=points,
        candidates=len(qualifying),
    )

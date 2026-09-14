"""Pressure-derivative diagnostics: the log-time derivative and Bourdet's L window.

The quantity every well-test diagnostic plot is built on is the derivative of the
response with respect to the natural logarithm of the time function,

    response' = d(response) / d ln(time) = time * d(response)/d(time),

because that is what turns the flow regimes into straight lines of known slope: a
horizontal plateau for infinite-acting radial flow, a unit slope for wellbore storage,
half slope for linear flow, quarter slope for bilinear flow, and a descending half
slope for spherical flow.

Two things in this module carry the whole result and both are easy to get wrong.

**The weighting.** Bourdet's three-point estimator is a weighted mean of the left and
right slopes in which each slope is weighted by the *opposite* log-time spacing. Writing
it the other way round is the standard transcription error, and it is invisible on a
uniform grid because the two forms coincide there. On a non-uniform grid the transposed
form is algebraically identical to the plain two-point secant across the window, which
is only first-order accurate; the correct form is the derivative of the parabola through
the three points and is second-order accurate. Both are exact when the response is
affine in ln(time), so a radial-plateau test alone cannot tell them apart -- which is why
:mod:`tests.test_diagnostics` tests the two on a curved response on a deliberately
lopsided grid.

**The unit of L.** Bourdet's smoothing distance L is measured in *natural*-log cycles of
the time function. Several commercial packages quote the same parameter in decades. The
two differ by ln(10) = 2.302585 and the difference is not subtle: reproducing the paper's
own L = 0.1 column with L read as decades is wrong by 18.5 percent. This module's
``smoothing_l`` is in natural-log cycles. A caller holding decades converts once, at the
call site: ``smoothing_l = math.log(10.0) * l_decades``.

Conventions this module fixes
-----------------------------
``time`` is the *time function*, not necessarily raw elapsed time. The derivative is
taken with respect to ``ln(time)``, so for a drawdown you pass elapsed time, and for a
buildup you pass Agarwal equivalent time or the superposition time function already
evaluated -- that is, ``exp(X)`` where ``X`` is the superposition abscissa in natural
logarithm. Differentiating a buildup against raw elapsed time instead understates the
derivative by the factor ``t_p / (t_p + dt)``: at ``dt = t_p`` the radial plateau reads
half its true height, and permeability inferred from it is wrong by a factor of two. The
uncorrected curve droops at late time and is routinely misread as a constant-pressure
boundary. This module cannot detect that mistake for you; it only differentiates what it
is given.

Because the derivative is taken with respect to a logarithm, it is invariant under a
change of time unit: hours, days or seconds give identical derivative values, and only
the returned abscissa changes. That is why ``time`` carries no unit suffix, contrary to
the naming rule for dimensional parameters elsewhere in this package. ``response`` is
likewise unit-agnostic and the derivative carries the response's own units -- psi for a
pressure change, psi^2/cp for a pseudopressure change.

Endpoints are omitted, never one-sided. Within L of either end of the record no valid
pair of window points exists. Bourdet's own remedy is a fixed "pseudo right" derivative
reusing the last admissible pair, which produces a smooth artefact at the tail; a
one-sided slope produces a spurious kink that mimics a boundary. This module does
neither: the affected points are dropped, and the returned abscissa tells the caller
exactly which points survived. Dropping is the only one of the three options that cannot
be mistaken for data.

Negative derivatives are returned as they are. A falling derivative is physical
information -- constant-pressure support, a buildup after a rate change, spherical flow
seen through a wrong reference -- and clipping or absolute-valuing it hides precisely the
behaviour the plot exists to reveal.

What this module deliberately does not provide
----------------------------------------------
There is no regime-classification helper here. The tempting single scalar is the
beta-derivative, ``beta = response' / response``, which reads 1 for pure wellbore
storage, 1/2 for linear flow and 1/4 for bilinear flow. It does not separate spherical
from radial flow: for spherical flow the response is ``a - b/sqrt(t)`` with ``a, b > 0``,
so the derivative is ``+(b/2)/sqrt(t) > 0`` while the response tends to the constant
``a``, and beta therefore tends to zero *from above*, exactly as it does for radial flow.
The value -1/2 that is sometimes attached to spherical flow is the log-log *slope* of the
derivative curve, ``d ln(response') / d ln(time)``, which is a different quantity; that
slope is the one that does separate the two regimes (-1/2 against 0). Until a classifier
encodes that distinction correctly it is better not to ship one, so this module ships the
derivative and leaves the reading of it to the interpreter.

There are also no field-unit constants here, because none are needed to differentiate.
If one is added later it must name the rate unit beside it: the gas infinite-acting
radial flow group is ``1422.52`` with the gas rate in Mscf/D, and the frequently quoted
``1.422e6`` belongs to MMscf/D. The two differ by a factor of a thousand and both appear
in the literature, sometimes within one paper.

References
----------
Bourdet, D.P., Ayoub, J.A., and Pirard, Y.M., "Use of Pressure Derivative in Well-Test
Interpretation", SPE Formation Evaluation, June 1989, pp. 293-302 (SPE-12777-PA), Eq. 8
and the "Preferred Algorithm" and "End Effect" paragraphs. Evidence and the corrections
applied to it are recorded in ``docs/evidence/derivative.md``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from . import gas
from .errors import InvalidInputError, NotIdentifiableError
from .validation import (
    as_float_sequence,
    require_finite,
    require_min_length,
    require_same_length,
    require_strictly_increasing,
)

__all__ = ["bourdet_derivative", "log_time_derivative"]

#: Range of L quoted by Bourdet et al. (1989, p. 297): "Common values for L are 0
#: (consecutive points) up to 0.5 in extreme cases", in natural-log cycles. Exposed as a
#: module constant so a test can read it rather than repeat it. It is documentation, not
#: a guard: a larger L is legal here and merely over-smooths, and over-smoothing is a
#: judgement the interpreter makes with the plot in front of them.
BOURDET_L_TYPICAL_RANGE = (0.0, 0.5)

#: The paper's own working value, used for Fig. 10 and for the L = 0.1 column of Table 1.
BOURDET_L_WORKING_VALUE = 0.1


def _validated_series(
    time: Sequence[float], response: Sequence[float]
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Validate a (time, response) pair for logarithmic differentiation."""
    times = as_float_sequence(time, "time")
    responses = as_float_sequence(response, "response")
    require_same_length(times, responses, "time", "response")
    require_min_length(times, "time", 3, "a three-point log-time derivative stencil")
    for index, value in enumerate(times):
        # Not validation.require_positive: its message diagnoses a gauge or Fahrenheit
        # value, which is the wrong hint here. The cause for a time series is almost
        # always the shut-in sample itself, recorded at dt = 0, which has no ln.
        if value <= 0.0:
            raise InvalidInputError(
                f"time[{index}] must be strictly positive, got {value!r}. The derivative "
                f"is taken with respect to ln(time), which does not exist at or below "
                f"zero. A buildup record whose first sample is the shut-in point at "
                f"dt = 0 must have that sample removed, not clamped to a small number."
            )
    require_strictly_increasing(times, "time")
    return times, responses


def _window_indices(log_time: Sequence[float], smoothing_l: float) -> tuple[tuple[int, int, int], ...]:
    """Select the (centre, left, right) index triples admitted by the L rule.

    For each interior point ``i`` the left point is the first point found walking left
    whose separation in ``log_time`` is at least ``smoothing_l``, and the right point is
    the first found walking right with the same property. Points for which either side
    is missing are not returned at all.

    Both ``j(i)`` and ``k(i)`` are non-decreasing in ``i`` because ``log_time``
    increases, so two monotone pointers visit each index once and the whole selection
    costs O(n) rather than O(n^2). That matters on gauge data sampled every second.
    """
    count = len(log_time)
    selected: list[tuple[int, int, int]] = []
    left = 0
    right = 1
    for centre in range(1, count - 1):
        # No point at all lies a full window to the left of this centre.
        if log_time[centre] - log_time[0] < smoothing_l:
            continue
        while left + 1 < centre and log_time[centre] - log_time[left + 1] >= smoothing_l:
            left += 1
        if right <= centre:
            right = centre + 1
        while right < count and log_time[right] - log_time[centre] < smoothing_l:
            right += 1
        if right >= count:
            # The window runs off the end of the record. Every later centre does too,
            # since k(i) is non-decreasing, so the loop simply finds nothing more.
            continue
        selected.append((centre, left, right))
    return tuple(selected)


def _log_spacing(high_time: float, low_time: float, high_log: float, low_log: float) -> float:
    """Separation of two times on the ln axis, formed so it keeps its digits.

    The ratio form ``ln(t_k/t_i)`` is preferred because for a closely spaced pair the
    difference ``ln(t_k) - ln(t_i)`` cancels most of its significant digits, while the
    ratio keeps the full relative precision of the pair. That matters on second-by-second
    gauge data at late time, and it is also what makes the ``smoothing_l = 0`` case
    bit-for-bit identical to the unsmoothed primitive.

    The ratio itself overflows when the two times are more than about 308 decades apart.
    No pressure record spans that, but a rejected input is still a wrong answer, so the
    difference of the precomputed logarithms is used as the fallback: a spacing of
    hundreds of natural-log cycles has no relative precision left to protect.
    """
    ratio = high_time / low_time
    if math.isfinite(ratio):
        return math.log(ratio)
    return high_log - low_log


def log_time_derivative(
    time: Sequence[float], response: Sequence[float]
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Unsmoothed three-point derivative of the response with respect to ln(time).

    This is the L = 0 case of :func:`bourdet_derivative`: the stencil is the three
    consecutive points ``i-1, i, i+1``, weighted by Bourdet's rule. The arithmetic is
    not repeated here -- it is delegated to :func:`reservoir_lab.gas.log_time_derivative`,
    which already implements exactly this estimator. What this wrapper adds is the
    package's validation contract: the argument and index of the offending value are
    named and the failure is an
    :class:`~reservoir_lab.errors.InvalidInputError` rather than a bare ``ValueError``.
    The returned numbers are identical to the delegate's, bit for bit.

    That translation covers the delegate's own overflow guard as well, which fires when
    a response increment divided by its log spacing is not representable. The delegate
    signals it with a bare ``ValueError``; C3 of the API contract requires
    :class:`~reservoir_lab.errors.InvalidInputError`, so it is re-raised as one, naming
    the offending index.

    One record is differentiable by :func:`bourdet_derivative` and not by this function:
    the delegate forms its log spacing as ``ln(t[i+1]/t[i])`` and that ratio overflows
    when consecutive samples are more than about 308 decades apart, where the windowed
    path falls back to a difference of logarithms. No pressure record is anywhere near
    that wide; the case is documented because the failure is reported rather than
    silently approximated, and the message says which call does work.

    Parameters
    ----------
    time : sequence of float
        The time function, strictly increasing and strictly positive, in any unit. For a
        drawdown this is elapsed time. For a buildup it is Agarwal equivalent time or an
        evaluated superposition time function, not raw elapsed time; see the module
        docstring for the size of the error that substitution causes. Because the
        derivative is taken against a logarithm, the choice of time unit does not change
        the derivative values.
    response : sequence of float
        Pressure change, pseudopressure change, or any other response sampled at the
        same points, in any unit. Need not be monotone and may be negative.

    Returns
    -------
    tuple of (tuple of float, tuple of float)
        ``(time_subset, derivative)``. The abscissa is the interior subset of ``time``,
        that is ``time[1:-1]``; the two endpoints have no stencil and are omitted rather
        than approximated with a one-sided slope. The derivative carries the units of
        ``response`` per natural-log cycle.

    Assumptions and validity
    ------------------------
    The estimator is exact to machine precision whenever the response is affine in
    ln(time), which is why the infinite-acting radial flow plateau is recovered without
    bias. On a power-law response ``A*t^n`` sampled on a uniform log grid of spacing
    ``h`` it is high by the closed-form factor ``sinh(n*h)/(n*h)``, which is 0.89 percent
    for unit slope at ten points per decade. There is no noise model: the estimator does
    not create noise, it reveals it, and on data whose increments approach gauge
    resolution the unsmoothed derivative is unusable -- use :func:`bourdet_derivative`
    with a non-zero window instead.

    What this does not do
    ---------------------
    It does not build the time function, apply a superposition or Agarwal
    transformation, correct for a rate change, smooth, de-spike, resample, or classify a
    flow regime. It does not clip negative derivative values.

    Raises
    ------
    InvalidInputError
        If ``time`` and ``response`` differ in length, if fewer than three points are
        supplied, if any value is non-finite, if ``time`` contains a value that is not
        strictly positive or does not strictly increase, or if the stencil itself
        overflows -- a derivative that is not finite is not a result, and C3 forbids
        returning ``nan`` in its place.
    """
    times, responses = _validated_series(time, response)
    # Delegating the arithmetic keeps one implementation of the weighted stencil in the
    # package. The validation contract above disposes of every guard the delegate has
    # except its overflow guard, which raises a plain ValueError that C3 forbids this
    # package from letting out.
    try:
        return gas.log_time_derivative(times, responses)
    except ValueError as exc:
        # bourdet_derivative with a zero window evaluates the identical stencil on the
        # identical points, and its own guard names the offending index, so it is used
        # here to build the message rather than transcribing the stencil a second time.
        try:
            bourdet_derivative(times, responses, smoothing_l=0.0)
        except InvalidInputError as located:
            raise InvalidInputError(str(located)) from exc
        # Reached only when the record spans more than about 308 decades, where the
        # delegate's ratio form overflows and the windowed path's fallback does not.
        decades = math.log10(times[-1]) - math.log10(times[0])
        raise InvalidInputError(
            f"the unsmoothed stencil overflowed inside "
            f"reservoir_lab.gas.log_time_derivative on a record spanning {decades:.1f} "
            f"decades: a ratio t[i+1]/t[i] in it is not representable. Call "
            f"bourdet_derivative(time, response, smoothing_l=0.0), which forms such a "
            f"spacing as a difference of logarithms instead. Delegate reported: {exc}"
        ) from exc


def bourdet_derivative(
    time: Sequence[float],
    response: Sequence[float],
    *,
    smoothing_l: float,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Bourdet L-smoothed derivative of the response with respect to ln(time).

    Implements Bourdet, Ayoub and Pirard (1989), Eq. 8, with the L point-selection rule
    of the same paper. With ``X = ln(time)``, a left point ``j`` and a right point ``k``
    chosen by the L rule below, and

        dX1 = X[i] - X[j],  dp1 = p[i] - p[j]     (left spacing and increment)
        dX2 = X[k] - X[i],  dp2 = p[k] - p[i]     (right spacing and increment)

    the derivative placed at point ``i`` is

        dp/dX|i = ( (dp1/dX1)*dX2 + (dp2/dX2)*dX1 ) / ( dX1 + dX2 ).

    Each slope is weighted by the spacing on the *opposite* side, so the nearer point
    receives the larger weight. This is the derivative of the parabola through the three
    selected points, evaluated at the middle one. Weighting each slope by its own spacing
    instead collapses the formula to the two-point secant ``(p[k] - p[j])/(X[k] - X[j])``
    and loses an order of accuracy on a non-uniform grid, while agreeing exactly on a
    uniform one -- so a uniform-grid test cannot detect the mistake.

    Point selection. ``j`` is the first index found walking left from ``i`` with
    ``X[i] - X[j] >= smoothing_l``; ``k`` is the first index found walking right with
    ``X[k] - X[i] >= smoothing_l``. With ``smoothing_l = 0`` this degenerates to the
    immediate neighbours and the result equals :func:`log_time_derivative` exactly. The
    paper prints a strict ``>``; this implementation uses ``>=``, which differs only on
    an exact tie in log-spacing. The published table used to verify the algorithm
    contains no such tie, so the tie-break itself is untested against the source. The
    same ``>=`` is applied at all three places the rule is decided -- the walk to the
    left, the walk to the right, and the guard that asks whether any point at all lies a
    full window to the left of the centre -- so a point whose spacing equals ``L``
    exactly is admitted on either side and is not dropped from the result.

    Parameters
    ----------
    time : sequence of float
        The time function, strictly increasing and strictly positive, in any unit; see
        :func:`log_time_derivative` and the module docstring for what belongs here in a
        buildup.
    response : sequence of float
        Response sampled at the same points, in any unit. Need not be monotone.
    smoothing_l : float
        Smoothing window, a distance along the ``ln(time)`` axis in **natural**-log
        cycles, not decades and not a time. Must be finite and non-negative. Bourdet
        quotes 0 to 0.5 as the common range with 0.1 as a working value
        (:data:`BOURDET_L_TYPICAL_RANGE`); a caller working in decades converts with
        ``smoothing_l = math.log(10.0) * l_decades``. Larger values are accepted and
        merely over-smooth.

    Returns
    -------
    tuple of (tuple of float, tuple of float)
        ``(time_subset, derivative)``. The abscissa holds only those points that had a
        full window on both sides, in the original order, so it is generally shorter than
        ``time[1:-1]`` and shrinks as ``smoothing_l`` grows. Derivative values carry the
        units of ``response`` per natural-log cycle and are returned with their sign.

    Assumptions and validity
    ------------------------
    L is a distance on the ``ln(time)`` axis, which is what makes the smoothing uniform
    in log cycles; applying the same number to raw time would give no smoothing early and
    total over-smoothing late. Because the axis is logarithmic, a fixed L smooths more
    heavily at late time. On a power-law response the smoothing biases the estimate high
    by ``sinh(n*dX)/(n*dX)`` -- 8.1 percent for unit slope with a window three points
    wide at ten points per decade -- so a large L flattens genuine transitions such as a
    dual-porosity trough. The bias is exactly zero for a radial plateau, where the
    response is affine in ln(time), at any L. When comparing against a type curve, apply
    the same L to the model as to the data; that is the only way the smoothing distortion
    cancels.

    What this does not do
    ---------------------
    It does not implement Bourdet's "pseudo right" end-effect remedy: points within L of
    either end are omitted, not extrapolated (see the module docstring). It does not
    build or transform the time function, correct for rate changes, de-spike, resample,
    or classify a regime, and it does not clip negative values.

    Raises
    ------
    InvalidInputError
        If ``time`` and ``response`` differ in length, if fewer than three points are
        supplied, if any value is non-finite, if ``time`` contains a value that is not
        strictly positive or does not strictly increase, if ``smoothing_l`` is negative
        or non-finite, or if a derivative value itself overflows -- which needs response
        magnitudes near the floating-point maximum, and is reported rather than returned
        as ``nan``, because C3 of the API contract forbids a ``nan`` sentinel.
    NotIdentifiableError
        If no point in the record has a full window on both sides, which happens when
        ``smoothing_l`` is comparable to or larger than half the logarithmic span of the
        data. Returning an empty series instead would look like a result; it is not one,
        it means the window and the record are incompatible.
    """
    times, responses = _validated_series(time, response)
    window = require_finite(smoothing_l, "smoothing_l")
    if window < 0.0:
        raise InvalidInputError(
            f"smoothing_l must be non-negative, got {window!r}. It is a distance along "
            f"the ln(time) axis in natural-log cycles; a negative distance would select "
            f"points on the wrong side of the point being differentiated."
        )

    # Each abscissa is computed from its own time value rather than accumulated from the
    # previous one; accumulation drifts over the tens of thousands of samples a modern
    # gauge produces.
    log_time = tuple(math.log(value) for value in times)

    selected = _window_indices(log_time, window)
    if not selected:
        span = log_time[-1] - log_time[0]
        raise NotIdentifiableError(
            f"no point has a full smoothing window on both sides: smoothing_l={window!r} "
            f"natural-log cycles against a record spanning {span:.4f} cycles over "
            f"{len(times)} points. A window needs room on both sides, so it must be well "
            f"below half the span. Either reduce smoothing_l or extend the record; this "
            f"function will not fall back to a one-sided slope."
        )

    abscissa = []
    derivative = []
    for centre, left, right in selected:
        # The spacings are formed by _log_spacing, which prefers the log of a ratio; see
        # there for why, and for the one case in which it cannot. The precomputed
        # abscissa is still what the L rule compares, where the cancellation is harmless
        # because the comparison is against a window of order 0.1 rather than against a
        # difference of increments.
        spacing_left = _log_spacing(times[centre], times[left], log_time[centre], log_time[left])
        spacing_right = _log_spacing(times[right], times[centre], log_time[right], log_time[centre])
        slope_left = (responses[centre] - responses[left]) / spacing_left
        slope_right = (responses[right] - responses[centre]) / spacing_right
        # Bourdet Eq. 8. The left slope takes the RIGHT spacing and the right slope takes
        # the LEFT spacing. Swapping them here is the transcription error described in
        # the module docstring and it survives every uniform-grid test.
        value = (slope_left * spacing_right + slope_right * spacing_left) / (spacing_left + spacing_right)
        if not math.isfinite(value):
            # C3 forbids returning nan to signal failure, and a stencil that overflows
            # has no result to return. The cause is the response increment over the
            # window, not the spacing: the spacing is guarded by _log_spacing and the
            # times themselves are already validated finite, positive and increasing.
            raise InvalidInputError(
                f"the derivative at time[{centre}]={times[centre]!r} is not finite; the "
                f"response increment over its window "
                f"({responses[left]!r} to {responses[right]!r}) overflowed, so check "
                f"the magnitude and the units of the response values"
            )
        abscissa.append(times[centre])
        derivative.append(value)
    return tuple(abscissa), tuple(derivative)

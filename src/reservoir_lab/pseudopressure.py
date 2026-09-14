"""Real-gas pseudopressure, the Al-Hussainy-Ramey-Crawford transform.

The transform is one integral::

    m(p) - m(p_ref) = 2 * integral from p_ref to p of  p' / (mu(p') Z(p'))  dp'

with pressure absolute (psia) and viscosity in cp, so ``m`` carries psia^2/cp. The
factor 2 is not cosmetic: it comes from ``p grad(p) = (1/2) grad(p^2)`` and is mirrored
by the ``1/2`` in the paper's mass-flux relation. Dropping it consistently would leave
every difference-based workflow unchanged and break every published field-unit
coefficient that goes with it (1637, 1422, 57895.3), so it is kept.

What the transform does and does not do
---------------------------------------
It linearises exactly one nonlinearity. Substituting ``m(p)`` into the rigorous
real-gas flow equation ``div[(p/(mu Z)) grad p] = (phi/k) d(p/Z)/dt`` turns the left,
spatial side into ``grad^2 m`` with no small-pressure-gradient assumption and no
assumption that ``mu Z`` varies slowly. The second-degree gradient term is handled, not
neglected.

The resulting equation is still not linear. Its coefficient is ``phi mu(p) c_g(p) / k``,
which depends on the solution. Everything that engineers routinely blame on
pseudopressure lives in that residual time-side nonlinearity or outside the
single-phase Darcy assumption altogether, and this module does none of it:

* no rate superposition (the 1966 authors validated superposition for increasing rate
  schedules and explicitly declined to claim it for decreasing ones),
* no pseudotime for a changing ``mu c_t`` (pseudotime is an acknowledged non-rigorous
  patch; pseudopressure is an exact change of variable and pseudotime is not),
* no wellbore storage (worse for gas than for liquid, because the wellbore fluid
  compressibility itself moves with pressure),
* no multiphase or condensate-banking behaviour (below the dewpoint ``mu`` and ``Z``
  stop being functions of pressure alone and the transform is ill defined, not merely
  inaccurate),
* no non-Darcy skin (the rate-dependent ``D q`` term is additive and external to
  ``m(p)``; a single-rate gas test cannot separate it from the Darcy skin),
* no pressure-dependent permeability (putting ``k(p)`` inside the integral makes the
  result rock-specific rather than a fluid property).

Datum
-----
The lower limit is arbitrary. The 1966 paper says so in as many words, and choices in
circulation include 0 psia, 14.7 psia, and the base pressure of a PVT table. This
module therefore has no default datum: ``reference_psia`` is required at every call
site, so a bare ``m`` value can never be produced without its datum being written down
next to it. Two ``m`` values built on different datums differ by a constant and must
never be subtracted.

Conditioning
------------
``m`` is of order 1e8 to 1e9 psia^2/cp, so differencing two datum-referenced values for
a small drawdown subtracts two nearly equal large numbers. The API is shaped to avoid
that: a difference is obtained by integrating directly over ``[p_wf, p_i]``, which is
the same mathematics, is better conditioned, and makes the datum irrelevant by
construction.

Unit system: field units per ``docs/api_contract.md`` C1. Pressures are absolute.

Reference: Al-Hussainy, R., Ramey, H.J. Jr., Crawford, P.B., "The Flow of Real Gases
Through Porous Media", JPT 18(05) 624-636, 1966, SPE-1243-A-PA, Eqs. 7, 14-18, 27 and
Table 1. See ``docs/evidence/pseudopressure.md``.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .errors import InvalidInputError, NotIdentifiableError
from .numerics import composite_simpson
from .numerics import convergence_study as _quadrature_convergence_study
from .validation import require_finite, require_non_negative, require_positive

__all__ = [
    "DEFAULT_INTERVALS",
    "SIMPSON_ORDER_WINDOW",
    "SUPPORTED_METHODS",
    "ConvergenceResult",
    "convergence_study",
    "pseudopressure",
    "pseudopressure_constant_properties",
]

#: Quadrature rules this module will accept. There is one, and it is fixed rather than
#: adaptive on purpose: :func:`convergence_study` is only meaningful on a grid the
#: caller controls, and an adaptive routine hides both its grid and its error estimate.
SUPPORTED_METHODS = ("simpson",)

#: Default panel count. Chosen inside the demonstrated order-4 window (see
#: :data:`SIMPSON_ORDER_WINDOW`) and well clear of the round-off floor, at a cost of 257
#: integrand evaluations. It is a default, not a guarantee: a caller whose ``mu_z`` is
#: interpolated from a table, or who integrates across the near-critical hump at
#: ``T_pr`` near 1.05, should run :func:`convergence_study` on their own integrand
#: rather than trust this number.
DEFAULT_INTERVALS = 256

#: Panel counts over which composite Simpson shows a clean observed order near 4 on a
#: smooth analytic ``mu Z`` across a several-thousand-psi interval. Below the lower
#: bound the pre-asymptotic terms still contaminate the estimate; above the upper bound
#: the truncation error has fallen into the round-off of the summation and the observed
#: order collapses. Measured on the smooth test integrand over [14.7, 8000] psia
#: against a 50-digit reference: the absolute error falls 1.8e0, 1.2e-1, 7.4e-3,
#: 4.7e-4, 3.2e-5 over panel counts 64 to 1024, then stops at a few times 1e-6 to 1e-5
#: (of order 1e-15 relative) and does not improve again. The observed order over
#: successive triples runs 4.00, 3.79, 3.04, then becomes unestimable (``nan``) and
#: recovers as 0.59 -- it collapses, but it was not seen to go negative. Exposed so a
#: test can read the window instead of hard-coding it.
SIMPSON_ORDER_WINDOW = (64, 1024)


@dataclass(frozen=True)
class ConvergenceResult:
    """Grid-refinement record for one pseudopressure integral.

    Carries its own audit trail: the interval it integrated, the rule used, the grids
    used, and how many integrand evaluations that cost. A single grid's value proves
    nothing about the method, so the field a caller should read to judge the quadrature
    is :attr:`observed_orders`, not :attr:`values`.

    Attributes
    ----------
    pressure_psia, reference_psia:
        Upper and lower limits of integration, psia absolute. Recorded because ``m``
        values from different datums are not comparable.
    method:
        Quadrature rule used, one of :data:`SUPPORTED_METHODS`.
    interval_counts:
        Panel counts used, increasing and successively doubled.
    values:
        Pseudopressure difference on each grid, psia^2/cp.
    observed_orders:
        Order of accuracy estimated by Richardson extrapolation from each successive
        triple of grids. ``nan`` where the three values do not admit an estimate, which
        is what happens once round-off dominates truncation error. A ``nan`` there is
        the honest answer; a number would be invented.
    relative_changes:
        Relative change between successive grids, one shorter than ``values``.
    richardson_estimate:
        Extrapolated value from the two finest grids, psia^2/cp. Useful as a reference
        when no closed form exists; it is not an error bound.
    integrand_evaluations:
        Calls to ``mu_z`` on each grid.
    n_points:
        Total calls to ``mu_z`` across the whole study.
    extrapolation_order:
        The order actually used to build :attr:`richardson_estimate`. It is the last
        estimable entry of :attr:`observed_orders` when there is one, and the
        theoretical Simpson order 4.0 otherwise.
    extrapolation_order_source:
        ``"observed"`` if :attr:`extrapolation_order` was measured from the grids,
        ``"assumed"`` if the theoretical 4.0 was substituted because no triple admitted
        an estimate. Recorded because an extrapolation built on an assumed order is a
        different object from one built on a measured order, and
        :attr:`richardson_estimate` alone cannot be told apart. The substitution is not
        academic: past the round-off floor it is routine, and there the extrapolation
        can be worse than simply taking the finest grid.
    """

    pressure_psia: float
    reference_psia: float
    method: str
    interval_counts: tuple[int, ...]
    values: tuple[float, ...]
    observed_orders: tuple[float, ...]
    relative_changes: tuple[float, ...]
    richardson_estimate: float
    integrand_evaluations: tuple[int, ...]
    n_points: int
    extrapolation_order: float
    extrapolation_order_source: str

    def best(self) -> float:
        """Finest-grid pseudopressure difference, psia^2/cp."""
        return self.values[-1]

    def last_estimable_order(self) -> float:
        """Observed order from the finest triple of grids that admits an estimate.

        Raises
        ------
        NotIdentifiableError
            If no triple admits an estimate. That happens when successive differences
            vanish or change sign, i.e. when the study has been refined past the
            round-off floor, and in that case the order is genuinely not recoverable
            from these values.
        """
        for order in reversed(self.observed_orders):
            if math.isfinite(order):
                return order
        raise NotIdentifiableError(
            "no observed order is estimable from this study: successive grid "
            "differences vanish or change sign, which means the refinement has "
            "reached the round-off floor. Re-run over coarser grids "
            f"(a clean window for a smooth integrand is {SIMPSON_ORDER_WINDOW})."
        )


def _checked_method(method: str) -> str:
    if method not in SUPPORTED_METHODS:
        raise InvalidInputError(f"method must be one of {SUPPORTED_METHODS}, got {method!r}")
    return method


def _checked_intervals(intervals: int) -> int:
    # bool is an int subclass; True would otherwise sail through as 1 and then be
    # rejected for parity with a message that hides the real mistake.
    if isinstance(intervals, bool) or not isinstance(intervals, int):
        raise InvalidInputError(
            f"intervals must be an even positive int, got {intervals!r} of type {type(intervals).__name__}"
        )
    return intervals


def _coerced_product(value: object, pressure_psia: float) -> float:
    """Coerce a ``mu_z`` return that is not exactly a ``float``, cheaply.

    Split out of :func:`_integrand` so that the diagnostic string naming the offending
    pressure is built only when the coercion actually fails. A ``mu_z`` backed by an
    integer table, a ``Decimal`` or a ``Fraction`` is legitimate, and it must not pay
    for a formatted message at every node of a refinement study.
    """
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        # require_finite owns the wording and the exception type for a non-numeric
        # argument. It raises here rather than returning.
        return require_finite(value, f"mu_z({pressure_psia!r})")  # type: ignore[arg-type]


def _representable(value: float, upper: float, lower: float) -> float:
    """Return ``value``, raising if the pseudopressure difference overflowed.

    ``m`` grows like ``p^2/(mu Z)``, so limits that are individually finite and legal
    can still put the difference outside double precision: 1e200 psia is nonsense
    physically but perfectly finite arithmetically, and so is a denormal ``mu Z``.
    Contract C3 forbids handing back a non-finite value as a signal, and an ``inf``
    that reaches a flow solution becomes a ``nan`` several steps later, where nothing
    records where it came from.
    """
    if math.isfinite(value):
        return value
    raise InvalidInputError(
        f"m({upper!r}) - m({lower!r}) is not representable in double precision: the "
        f"calculation produced {value!r} psia^2/cp. Pseudopressure grows like "
        f"p^2/(mu Z), so check the magnitude of the limits and of mu*Z."
    )


def _integrand(mu_z: Callable[[float], float]) -> Callable[[float], float]:
    """Build ``p -> 2 p / (mu(p) Z(p))`` with the callable's output validated.

    The output check is not defensive clutter. A ``mu Z`` that comes back zero,
    negative or non-finite is the signature of a deviation-factor solve that landed on
    the wrong root, of a correlation evaluated outside its window, or of a table lookup
    that fell off its end. All three produce a plausible-looking finite integral if the
    value is allowed through, so they are rejected at the point of evaluation where the
    offending pressure can still be named.

    The quotient itself is checked for the same reason. A ``mu Z`` small enough to be
    denormal is finite and strictly positive and so passes every guard above, yet
    ``2p/(mu Z)`` overflows; returning ``inf`` from there would put a non-finite value
    into the sum and out through the public return, which contract C3 forbids.
    """
    if not callable(mu_z):
        raise InvalidInputError(f"mu_z must be a callable p -> mu(p)*Z(p) in cp, got {type(mu_z).__name__}")

    def integrand(pressure_psia: float) -> float:
        product = mu_z(pressure_psia)
        if type(product) is not float:
            # A PVT wrapper may hand back an int, a Decimal or a third-party float
            # type. Coerce it by the package's own rule without formatting anything:
            # naming the offending pressure costs a string, and a refinement study
            # runs this a million times.
            product = _coerced_product(product, pressure_psia)
        if math.isfinite(product) and product > 0.0:
            value = 2.0 * pressure_psia / product
            if math.isfinite(value):
                return value
            # A finite, strictly positive mu Z can still be small enough that the
            # quotient overflows. Caught here because this is the last place the
            # offending pressure is still in scope.
            raise InvalidInputError(
                f"the integrand 2p/(mu Z) overflowed at p = {pressure_psia!r} psia: "
                f"mu_z returned {product!r} cp, which is positive and finite but too "
                f"small for 2p/(mu Z) to be representable in double precision"
            )
        # Failure path. require_finite keeps the coercion and the wording for a
        # non-finite return identical to the rest of the package; it raises.
        product = require_finite(product, f"mu_z({pressure_psia!r})")
        raise InvalidInputError(
            f"mu_z({pressure_psia!r}) returned {product!r}; the product of "
            f"viscosity and deviation factor must be strictly positive"
        )

    return integrand


def pseudopressure(
    pressure_psia: float,
    *,
    reference_psia: float,
    mu_z: Callable[[float], float],
    intervals: int = DEFAULT_INTERVALS,
    method: str = "simpson",
) -> float:
    """Pseudopressure difference ``m(p) - m(p_ref)`` by composite Simpson quadrature.

    Evaluates ``2 * integral from reference_psia to pressure_psia of p/(mu Z) dp``
    directly over the interval given. It does not build a datum-referenced table and
    subtract two entries, because for a small drawdown that subtraction loses most of
    the significant digits of an ``m`` of order 1e9.

    Parameters
    ----------
    pressure_psia : float
        Upper limit of integration, psia absolute. Zero is accepted; negative is not.
    reference_psia : float
        Lower limit, psia absolute, i.e. the datum. Required, never defaulted: the
        datum is arbitrary and an ``m`` value quoted without one is meaningless.
        May exceed ``pressure_psia``, in which case the result is negative.
    mu_z : callable
        ``p -> mu(p) * Z(p)`` in cp, at the single reservoir temperature of interest.
        It must be a genuine function of pressure alone: that is what makes ``m(p)``
        unique, and it is what multiphase or variable-composition systems violate.
    intervals : int, optional
        Even, positive panel count for composite Simpson. Default
        :data:`DEFAULT_INTERVALS`.
    method : str, optional
        Quadrature rule; only ``"simpson"`` is accepted. The argument exists so that
        the rule is recorded at the call site rather than assumed.

    Returns
    -------
    float
        ``m(pressure_psia) - m(reference_psia)`` in psia^2/cp.

    Raises
    ------
    InvalidInputError
        If either pressure is non-finite or negative; if ``intervals`` is not an even
        positive int; if ``method`` is not supported; if ``mu_z`` is not callable; if
        ``mu_z`` returns a value that is non-finite or not strictly positive, in which
        case the message names the pressure at which it happened; or if the integrand
        or the result overflows double precision, which a legal but extreme limit or a
        denormal ``mu Z`` can do. The last case raises rather than returning ``inf``:
        contract C3 forbids a non-finite return value, and an ``inf`` that reaches a
        flow solution surfaces as a ``nan`` somewhere its origin is no longer visible.

    Notes
    -----
    One carve-out in the validation above, stated here rather than left to be
    discovered: when ``pressure_psia == reference_psia`` the result is exactly ``0.0``
    and ``mu_z`` is never called, so a ``mu_z`` that would be rejected on any other
    interval is not rejected on this one. The returned value is still right -- an
    integral over a point is zero whatever the integrand does -- but the ``mu_z``
    checks are checks at the nodes actually used, and a zero-width interval uses none.

    Assumptions inherited from the definition: isothermal flow at one reservoir
    temperature, single gas phase of constant composition, and permeability independent
    of pressure. Under those, the transform is exact for any pressure at which ``mu``
    and ``Z`` are defined; ``m(p)`` itself carries no pressure validity window. Any
    window belongs to the correlations behind ``mu_z`` and to the flow solution the
    result is fed into, and this function has no ``strict_range`` keyword because it
    wraps no correlation of its own.

    Accuracy is the caller's to demonstrate, not this function's to assert. On a smooth
    analytic ``mu_z`` the rule converges at order 4 in the panel width; if ``mu_z``
    interpolates a PVT table its derivative kinks make the error behave erratically
    rather than at any clean order, and if it integrates across the near-critical
    integrand hump near ``T_pr`` 1.05 a fixed grid can under-resolve it silently. Run
    :func:`convergence_study` on the actual ``mu_z`` before quoting digits.

    This function performs quadrature only. See the module docstring for the list of
    things the pseudopressure transform does not do; in particular it supplies no rate
    superposition, no pseudotime, no wellbore storage, no multiphase or
    condensate-banking behaviour, and no non-Darcy skin.

    Determinism: no state, no clock, no randomness. Equal arguments give an equal
    result bit for bit.
    """
    upper = require_non_negative(pressure_psia, "pressure_psia")
    lower = require_non_negative(reference_psia, "reference_psia")
    _checked_method(method)
    _checked_intervals(intervals)
    integrand = _integrand(mu_z)
    # composite_simpson owns the parity and positivity check on `intervals`, returns
    # exactly 0.0 for equal limits, and negates for reversed limits. Antisymmetry in
    # the limits therefore holds bit for bit, which one of the invariant tests relies
    # on: it evaluates the same node set either way.
    return _representable(composite_simpson(integrand, lower, upper, intervals), upper, lower)


def pseudopressure_constant_properties(
    pressure_psia: float,
    *,
    reference_psia: float,
    viscosity_cp: float,
    z_factor: float,
) -> float:
    """Closed-form ``m(p) - m(p_ref)`` when ``mu`` and ``Z`` are literally constant.

    With ``mu Z`` constant the integrand ``2p/(mu Z)`` is a first-degree polynomial and
    the integral collapses to::

        m(p) - m(p_ref) = (p^2 - p_ref^2) / (mu Z)

    This is exact, not an approximation, and it is the reason the contract keeps
    ``mu_z`` a callable rather than a table: it gives :func:`pseudopressure` an oracle
    that is correct to machine precision, against which a wrong factor of 2, a mishandled
    datum or a panel-bookkeeping error shows up immediately.

    Parameters
    ----------
    pressure_psia : float
        Upper limit, psia absolute. Zero accepted, negative not.
    reference_psia : float
        Datum, psia absolute. May exceed ``pressure_psia``, giving a negative result.
    viscosity_cp : float
        Constant gas viscosity, cp. Strictly positive.
    z_factor : float
        Constant gas deviation factor, dimensionless. Strictly positive.

    Returns
    -------
    float
        ``m(pressure_psia) - m(reference_psia)`` in psia^2/cp.

    Raises
    ------
    InvalidInputError
        If either pressure is non-finite or negative; if ``viscosity_cp`` or
        ``z_factor`` is non-finite or not strictly positive; or if ``p^2`` or the
        quotient overflows double precision, which a legal but extreme pressure can do.
        The overflow raises rather than returning ``inf``, for the reason given in
        :func:`pseudopressure`.

    Notes
    -----
    Physically, constant ``mu Z`` is a limiting case and not a description of a real
    gas: on a real PVT table ``mu Z`` moves by tens of percent across a few thousand
    psi. Use this for verification, for a manufactured solution, or where the interval
    is narrow enough that the caller has shown the variation is negligible; do not use
    it as a cheap substitute for the integral.

    Note also what this is not. It is not the p-squared deliverability approximation.
    That approximation evaluates a varying ``mu Z`` at an average pressure and is a
    statement about a real gas at low pressure; this is the exact integral of a
    genuinely constant ``mu Z``. They coincide in form and differ in what is being
    claimed.
    """
    upper = require_non_negative(pressure_psia, "pressure_psia")
    lower = require_non_negative(reference_psia, "reference_psia")
    viscosity = require_positive(viscosity_cp, "viscosity_cp")
    deviation = require_positive(z_factor, "z_factor")
    return _representable((upper * upper - lower * lower) / (viscosity * deviation), upper, lower)


def convergence_study(
    pressure_psia: float,
    *,
    reference_psia: float,
    mu_z: Callable[[float], float],
    interval_counts: Sequence[int],
) -> ConvergenceResult:
    """Refine the quadrature over doubling grids and report the observed order.

    The point is to measure the order of accuracy actually achieved on the caller's own
    ``mu_z``, rather than to assert the order the textbook promises. The two differ
    whenever the integrand is less smooth than the rule assumes, and the common cause is
    mundane: ``mu`` and ``Z`` interpolated from a PVT table are only continuous, not
    continuously differentiable, and the error then stops following any clean power of
    the panel width.

    Parameters
    ----------
    pressure_psia : float
        Upper limit of integration, psia absolute.
    reference_psia : float
        Lower limit, psia absolute.
    mu_z : callable
        ``p -> mu(p) * Z(p)`` in cp, as for :func:`pseudopressure`.
    interval_counts : sequence of int
        At least three even, positive panel counts, each exactly double its
        predecessor. The doubling is required, not merely recommended: the Richardson
        estimator assumes a refinement ratio of 2, and a non-doubling sequence would
        produce a number that looks like an order and is not.

    Returns
    -------
    ConvergenceResult
        Values, observed orders, the extrapolated value, and the evaluation cost.

    Raises
    ------
    InvalidInputError
        If either pressure is non-finite or negative; if ``interval_counts`` is not
        iterable or holds fewer than three counts; if any count is not an even positive
        int; if the counts do not double successively; or if ``mu_z`` is not callable
        or returns a non-positive or non-finite value. As in :func:`pseudopressure`, a
        zero-width interval evaluates ``mu_z`` at no node and so detects none of its
        failures.

    Notes
    -----
    Read the result with the round-off floor in mind, and with the right number for it.
    ``m`` here is of order 1e9 psia^2/cp, so one unit in the last place is about 5e-7
    and no quadrature can resolve better than that. Measured on a smooth analytic
    ``mu_z`` over [14.7, 8000] psia against a 50-digit reference, the absolute error
    falls as ``h^4`` to about 3e-5 at 1024 panels, reaches roughly 5e-7 at 2048, and
    then does not improve: at 2^20 panels it is 7.5e-5, worse than at 2048. The wall is
    not double precision itself but the plain running sum inside
    ``numerics.composite_simpson``, whose accumulated round-off grows with the number
    of terms, so refining past the floor makes the answer worse rather than merely
    stalling. Orders reported past that point are arithmetic, not method.
    :data:`SIMPSON_ORDER_WINDOW` records the window where the order is legible for a
    smooth integrand over a several-thousand-psi interval.

    For the same reason, a value from this function refined onto a very fine grid is
    not a trustworthy reference for the error of a coarse one. Where an independent
    reference is needed, use a closed form or a computation done outside this package.

    This function measures quadrature error only. It says nothing about whether
    ``mu_z`` itself is right, and a converged integral of a wrong PVT description is a
    precisely computed wrong answer.
    """
    upper = require_non_negative(pressure_psia, "pressure_psia")
    lower = require_non_negative(reference_psia, "reference_psia")
    try:
        counts = tuple(interval_counts)
    except TypeError as exc:
        raise InvalidInputError(
            f"interval_counts must be an iterable of even positive ints, got {type(interval_counts).__name__}"
        ) from exc
    if len(counts) < 3:
        raise InvalidInputError(
            f"interval_counts needs at least three grids for a Richardson order estimate, got {len(counts)}"
        )
    for index, count in enumerate(counts):
        # Validate before delegating: numerics.convergence_study coerces with int(),
        # which would silently truncate 129.9 to 129 and then complain about parity.
        _checked_intervals(count)
        if count <= 0 or count % 2 != 0:
            raise InvalidInputError(f"interval_counts[{index}] must be an even positive int, got {count!r}")

    integrand = _integrand(mu_z)
    inner = _quadrature_convergence_study(integrand, lower, upper, counts)
    # composite_simpson short-circuits a zero-width interval without touching the
    # integrand, so the honest evaluation count there is zero rather than n + 1.
    evaluations = tuple(0 if upper == lower else count + 1 for count in counts)
    # Mirror of the rule in numerics.convergence_study, which falls back to the
    # theoretical Simpson order when the last observed order is not estimable. Recorded
    # rather than recomputed so the caller can see which of the two produced
    # `richardson_estimate`; the consistency of the mirror is pinned by a test that
    # rebuilds the estimate from these fields.
    last_order = inner.observed_orders[-1] if inner.observed_orders else math.nan
    if math.isfinite(last_order) and last_order > 0.0:
        extrapolation_order, order_source = last_order, "observed"
    else:
        extrapolation_order, order_source = 4.0, "assumed"
    return ConvergenceResult(
        pressure_psia=upper,
        reference_psia=lower,
        method="simpson",
        interval_counts=inner.interval_counts,
        values=inner.values,
        observed_orders=inner.observed_orders,
        relative_changes=inner.relative_changes,
        richardson_estimate=inner.richardson_estimate,
        integrand_evaluations=evaluations,
        n_points=sum(evaluations),
        extrapolation_order=extrapolation_order,
        extrapolation_order_source=order_source,
    )

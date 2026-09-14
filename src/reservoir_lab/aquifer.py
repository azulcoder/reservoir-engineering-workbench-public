"""Fetkovich (1971) pseudosteady-state aquifer influx.

Why this model and not van Everdingen-Hurst or Carter-Tracy
----------------------------------------------------------
This module is a *forward generator*. Its output becomes the synthetic observation set
that an inverse method is later applied to, so any error here is indistinguishable from
the physical effect the study exists to demonstrate. That pushes the choice towards the
model whose arithmetic can be audited end to end rather than the model with the best
physics.

The Fetkovich lumped-parameter recursion is closed form: no dimensionless-influx table,
no superposition sum, no interpolation, and no fitted polynomial whose coefficients
reach a reader only through a secondary source. It also has an unusual property for a
time-stepped scheme, proved under `Notes` below: for a boundary pressure held constant
over each interval it reproduces the closed-form solution of its own governing equation
to machine precision at *any* timestep. The generated history therefore carries no
scheme error into the inverse problem, and a reviewer cannot dismiss the result as a
timestep artefact.

What the model gives up, stated plainly: the aquifer is assumed to have reached
pseudosteady (closed outer boundary) or steady (constant-pressure outer boundary)
state, so the early transient is neglected entirely, and the whole aquifer is
represented by two numbers -- a productivity index and an encroachable volume. Nothing
in this module checks that the pseudosteady assumption is actually satisfied for the
aquifer the caller has described; that judgement, and the calculation of the
productivity index itself, are the caller's.

van Everdingen-Hurst is deliberately NOT implemented. Its dimensionless influx function
WeD(tD) is a published tabulation or a fitted polynomial, and the polynomial's
coefficients are known to have been transmitted with at least one long-lived
transcription error in the literature (the leading coefficient is 2/sqrt(pi) =
1.12838, and 1.2838 appears in print). Shipping a plausible-looking WeD from memory
would put an unverified table at the centre of a counterexample whose entire point is
that unverified numbers propagate. Omission is the honest option.

Units
-----
Field units throughout, per `docs/api_contract.md` C1, with absolute pressure:
pressure psia, volume reservoir bbl, compressibility 1/psi, time days, productivity
index reservoir bbl/day/psi. Every pressure in this module is absolute. A psig value
passed where psia is required produces a smaller influx that still looks plausible,
which is exactly why the parameter names carry the unit.

There is no ``strict_range`` keyword anywhere in this module. C2 requires one on any
function wrapping a correlation, and nothing here is a correlation: the recursion is
the exact solution of a two-parameter material balance, and the two parameters are
supplied by the caller rather than estimated from a fitted curve.

Notes
-----
Governing equations, in Fetkovich's own numbering (SPE-2603-PA, JPT July 1971):

    q_w        = J * (p_aq_bar - p_wf)                                    Eq. (1)
    We         = (Wei / p_i) * (p_i - p_aq_bar)                           Eq. (2), (13)
    Wei        = ct * Wi * p_i                                            Eq. (A-11)
    (q_wi)max  = J * p_i                                                  Eq. (B-6)
    dWe_n      = (Wei/p_i) * (p_aq_{n-1} - p_wf_bar_n)
                 * (1 - exp(-J * p_i * dt_n / Wei))                       Eq. (6)
    p_wf_bar_n = (p_wf_{n-1} + p_wf_n) / 2                                Eq. (8)

Combining Eq. (1) with Eq. (2) gives the governing ordinary differential equation

    dWe/dt = J * (p_i - We/(ct*Wi) - p_wf)

whose solution for a constant p_wf is Fetkovich Eq. (5),

    We(t) = ct * Wi * (p_i - p_wf) * (1 - exp(-t / tau)),   tau = ct*Wi/J,

and whose one-step exact advance is Eq. (6). Because Eq. (6) is that exact advance
rather than a truncated expansion of it, stepping it n times with a constant p_wf
returns Eq. (5) evaluated at t = n*dt for any dt: writing x_n = p_aq_n - p_wf and
r = exp(-dt/tau), Eq. (6) and Eq. (13) together give x_n = r * x_{n-1} exactly.
With a varying p_wf the only error left is the piecewise-constant representation of
p_wf itself, which with the Eq. (8) midpoint rule is second order in dt.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .errors import InvalidInputError
from .validation import (
    as_float_sequence,
    require_finite,
    require_min_length,
    require_positive,
    require_same_length,
    require_strictly_increasing,
)

__all__ = [
    "BOUNDARY_RULE_CALLER_SUPPLIED",
    "BOUNDARY_RULE_EQ8_MIDPOINT",
    "FETKOVICH_METHOD",
    "AquiferStep",
    "FetkovichAquifer",
]

#: Identifier recorded on every returned record, so a result read back from a report
#: names the model that produced it rather than relying on the reader's memory.
FETKOVICH_METHOD = "fetkovich-1971-pss"

#: The caller supplied the inner-boundary pressure for the step directly, already
#: averaged (or deliberately not averaged) by whatever couples the reservoir to the
#: aquifer.
BOUNDARY_RULE_CALLER_SUPPLIED = "caller-supplied"

#: The inner-boundary pressure over the step is the arithmetic mean of its values at
#: the two ends of the interval, which is Fetkovich Eq. (8).
BOUNDARY_RULE_EQ8_MIDPOINT = "eq8-midpoint"


@dataclass(frozen=True)
class AquiferStep:
    """One advance of the aquifer material balance.

    Frozen and self-describing per contract C5: the record names the model and the
    boundary-pressure convention that produced it, so a history written to a report can
    be audited without the call site that generated it.

    Attributes
    ----------
    time_days:
        Time at the END of the step. For a bare :meth:`FetkovichAquifer.step` call the
        step is taken to start at t = 0, so this equals ``timestep_days``. In a history
        it is the absolute time from the caller's own series.
    timestep_days:
        Length of the step, days.
    boundary_pressure_psia:
        The inner-boundary (reservoir/aquifer contact) pressure held constant over the
        step, psia. This is ``p_wf_bar_n`` of Fetkovich Eq. (6).
    aquifer_pressure_start_psia:
        Average aquifer pressure at the start of the step, ``p_aq_bar_{n-1}``, psia.
    aquifer_pressure_end_psia:
        Average aquifer pressure at the end of the step, ``p_aq_bar_n``, psia, from
        Eq. (13).
    influx_increment_bbl:
        Water that crossed into the reservoir during the step, reservoir bbl. Negative
        when the boundary pressure exceeds the aquifer pressure; that is efflux back
        into the aquifer and it is reported signed, not clipped.
    cumulative_influx_bbl:
        Cumulative influx at the end of the step, reservoir bbl, measured from virgin
        aquifer conditions.
    decline_factor:
        ``1 - exp(-dt/tau)``, the fraction of the remaining driving head consumed by
        this step. It lies in (0, 1] and never exceeds 1, which is why the scheme
        cannot overshoot however coarse the step. The interval is closed at the top in
        floating point: once ``dt/tau`` exceeds about 37.4, where ``exp(-dt/tau)``
        drops below half an ulp of 1, the factor is exactly 1.0. That is a complete and
        still non-overshooting advance onto the boundary pressure, not a failure. At
        the other end it is exactly 0.0 only if ``dt/tau`` itself underflows to zero,
        where a step of no measurable duration correctly produces no influx.
    boundary_pressure_rule:
        How ``boundary_pressure_psia`` was obtained: ``BOUNDARY_RULE_CALLER_SUPPLIED``
        or ``BOUNDARY_RULE_EQ8_MIDPOINT``.
    method:
        Model identifier, ``FETKOVICH_METHOD``.
    n_points:
        Number of caller-supplied boundary-pressure samples consumed to form the step:
        one for a direct step, two for a step inside a history.
    """

    time_days: float
    timestep_days: float
    boundary_pressure_psia: float
    aquifer_pressure_start_psia: float
    aquifer_pressure_end_psia: float
    influx_increment_bbl: float
    cumulative_influx_bbl: float
    decline_factor: float
    boundary_pressure_rule: str
    method: str
    n_points: int

    def __post_init__(self) -> None:
        """Validate and normalise the fields after construction."""
        # The validators coerce as well as check (require_finite returns float(value)),
        # so the coerced result is written back onto the frozen instance. Dropping it
        # would leave a record that passed validation while still holding a str or a
        # Decimal, which then fails with TypeError -- not InvalidInputError -- at the
        # first arithmetic use. object.__setattr__ is the documented way to assign to a
        # frozen dataclass from inside __post_init__.
        coerced = {
            "time_days": require_finite(self.time_days, "time_days"),
            "timestep_days": require_positive(self.timestep_days, "timestep_days"),
            "boundary_pressure_psia": require_positive(self.boundary_pressure_psia, "boundary_pressure_psia"),
            "aquifer_pressure_start_psia": require_positive(
                self.aquifer_pressure_start_psia, "aquifer_pressure_start_psia"
            ),
            "aquifer_pressure_end_psia": require_finite(
                self.aquifer_pressure_end_psia, "aquifer_pressure_end_psia"
            ),
            "influx_increment_bbl": require_finite(self.influx_increment_bbl, "influx_increment_bbl"),
            "cumulative_influx_bbl": require_finite(self.cumulative_influx_bbl, "cumulative_influx_bbl"),
            "decline_factor": require_finite(self.decline_factor, "decline_factor"),
        }
        for name, value in coerced.items():
            object.__setattr__(self, name, value)

    def driving_head_psi(self) -> float:
        """Pressure difference that drove the step, ``p_aq_bar_{n-1} - p_wf_bar_n``, psi.

        Positive for influx into the reservoir. Derived, not stored, so it cannot
        disagree with the two pressures it is computed from.
        """
        return self.aquifer_pressure_start_psia - self.boundary_pressure_psia


@dataclass(frozen=True)
class FetkovichAquifer:
    """A finite aquifer represented by a productivity index and an encroachable volume.

    Parameters
    ----------
    initial_pressure_psia:
        Initial aquifer pressure ``p_i``, psia, absolute. Constant for the life of the
        object. This is the pressure that appears in the recursion; see
        :meth:`step` for the symbol-by-symbol audit.
    water_volume_bbl:
        Initial water in place in the aquifer ``Wi``, reservoir bbl, which for a radial
        sector aquifer is the pore volume of the sector actually in contact with the
        reservoir: ``Wi = pi_const * f * (r_a**2 - r_o**2) * h * phi / 5.615`` with
        ``f = theta/360``. The encroachment-angle fraction ``f`` belongs either here or
        in ``Wei``, never in both -- see Notes.
    total_compressibility_per_psi:
        Total (effective) aquifer compressibility ``ct = cw + cf``, 1/psi. May be
        inflated deliberately to lump in other accumulations sharing the aquifer, which
        is a modelling choice the caller owns.
    productivity_index_bbl_per_day_psi:
        Aquifer productivity index ``J``, reservoir bbl/day/psi, defined by Fetkovich
        Eq. (1), ``q_w = J * (p_aq_bar - p_wf)``. This class does NOT compute J from
        geometry and does not check that the pseudosteady state J assumes has been
        reached.

    Raises
    ------
    InvalidInputError
        If any field is non-finite or not strictly positive, or if one of the derived
        groups the arithmetic actually uses -- the storativity ``ct*Wi``, the initial
        encroachable volume ``Wei = ct*Wi*p_i``, or the time constant
        ``tau = ct*Wi/J`` -- is not finite and strictly positive. Four individually
        representable fields can still produce a group that underflows to zero or
        overflows to infinity, and the group is what every later division depends on,
        so it is checked here rather than left to surface as a ZeroDivisionError or a
        NaN from somewhere inside the recursion.

    Notes
    -----
    Two conventions must be pinned down or a factor appears twice, or not at all.

    The first is the placement of the encroachment-angle fraction ``f = theta/360``.
    Fetkovich puts ``f`` inside ``Wi`` (Eq. 17) and writes ``Wei = ct*Wi*p_i``; other
    restatements keep ``f`` out of ``Wi`` and write ``Wei = ct*Wi*p_i*f``. The products
    agree, but taking ``Wi`` from one convention and ``Wei`` from the other is an error
    of ``1/f``, a factor of 2.6 at a 140-degree encroachment angle. This class uses
    Fetkovich's convention: ``f`` is already inside ``water_volume_bbl`` and
    :meth:`maximum_influx_bbl` does not apply it again.

    The second is the definition of ``Wei`` itself, which is the correction recorded in
    ``docs/evidence/aquifer.md``: ``Wei = ct * Wi * p_i``, the water that would encroach
    if aquifer pressure fell to zero absolute. The expression ``ct * Wi * (p_i - p)`` is
    *not* ``Wei``; it is ``We(p)``, the cumulative influx once the aquifer has settled at
    pressure ``p``, and it is available here as :meth:`sustained_influx_limit_bbl`.
    Substituting it for ``Wei`` corrupts both the ``Wei/p_i`` prefactor and the time
    constant, and makes the recursion non-conservative.
    """

    initial_pressure_psia: float
    water_volume_bbl: float
    total_compressibility_per_psi: float
    productivity_index_bbl_per_day_psi: float

    def __post_init__(self) -> None:
        """Validate and normalise the fields after construction."""
        # Write the coerced floats back: the validators return float(value), and an
        # object that kept a str or a Decimal after "passing" validation would raise
        # TypeError rather than InvalidInputError on its first arithmetic use.
        coerced = {
            "initial_pressure_psia": require_positive(self.initial_pressure_psia, "initial_pressure_psia"),
            "water_volume_bbl": require_positive(self.water_volume_bbl, "water_volume_bbl"),
            "total_compressibility_per_psi": require_positive(
                self.total_compressibility_per_psi, "total_compressibility_per_psi"
            ),
            "productivity_index_bbl_per_day_psi": require_positive(
                self.productivity_index_bbl_per_day_psi, "productivity_index_bbl_per_day_psi"
            ),
        }
        for name, value in coerced.items():
            object.__setattr__(self, name, value)

        # Validating the four fields individually is not enough. Every later division
        # is by a derived group, and a group can leave the representable range while
        # each of its factors is perfectly ordinary: ct = 1e-200 with Wi = 1e-200
        # underflows ct*Wi to exactly zero, and ct = Wi = 1e300 overflows it. Checking
        # the groups here is what keeps the failure an InvalidInputError naming the
        # caller's own fields instead of a ZeroDivisionError from time_constant_days()
        # or a NaN that surfaces later as a complaint about an internal record field.
        storage = self.total_compressibility_per_psi * self.water_volume_bbl
        self._require_positive_group(
            storage,
            "total_compressibility_per_psi * water_volume_bbl",
            "the aquifer storativity ct*Wi, in bbl/psi",
        )
        self._require_positive_group(
            storage * self.initial_pressure_psia,
            "total_compressibility_per_psi * water_volume_bbl * initial_pressure_psia",
            "the initial encroachable water in place Wei, in bbl",
        )
        self._require_positive_group(
            storage / self.productivity_index_bbl_per_day_psi,
            "total_compressibility_per_psi * water_volume_bbl / productivity_index_bbl_per_day_psi",
            "the aquifer time constant tau = ct*Wi/J, in days",
        )

    @staticmethod
    def _require_positive_group(value: float, expression: str, meaning: str) -> None:
        """Raise unless a derived group is finite and strictly positive.

        Separate from :func:`~reservoir_lab.validation.require_positive` only because
        the message has to say which *combination* of fields left the representable
        range; the standard message assumes a single named argument and offers a
        gauge-pressure hint that would be misleading here.
        """
        if not math.isfinite(value) or value <= 0.0:
            raise InvalidInputError(
                f"{expression} must be finite and strictly positive, got {value!r}. "
                f"This group is {meaning}, and the recursion divides by it. Each field "
                f"on its own is representable; their combination is not, so rescale the "
                f"units or the aquifer description rather than the individual values."
            )

    # -- derived constants of the aquifer ----------------------------------

    def storage_bbl_per_psi(self) -> float:
        """Aquifer storativity ``ct * Wi``, reservoir bbl per psi of aquifer depletion.

        This is the group that actually appears in the recursion, because
        ``Wei / p_i == ct * Wi`` identically. Keeping it as a named quantity is the
        protective refactor described in the evidence card: it removes ``p_i`` from the
        stepping arithmetic altogether, so the common transcription error of using the
        current aquifer pressure in place of the initial one has nowhere to occur.

        Returns
        -------
        float
            ``ct * Wi``, bbl/psi.
        """
        return self.total_compressibility_per_psi * self.water_volume_bbl

    def time_constant_days(self) -> float:
        """Aquifer time constant ``tau = ct * Wi / J``, days.

        Derived, not published by Fetkovich in this form. It follows from
        ``Wei / (q_wi)max = (ct*Wi*p_i) / (J*p_i) = ct*Wi/J``, and the exact
        cancellation of ``p_i`` there is the cleanest single check that the recursion
        has been transcribed correctly: a time constant that still depends on ``p_i``
        is a transcription error.

        The aquifer consumes a fraction ``1 - exp(-dt/tau)`` of its remaining driving
        head per step, so ``dt/tau`` -- not ``dt`` -- is the number that says whether a
        history is resolved.

        Returns
        -------
        float
            ``tau``, days. Strictly positive.
        """
        return self.storage_bbl_per_psi() / self.productivity_index_bbl_per_day_psi

    def maximum_influx_bbl(self) -> float:
        """Return ``Wei = ct * Wi * p_i``, the initial encroachable water in place, bbl.

        This is Fetkovich's ``Wei`` (Eq. A-11, "defining ct*Wi*p_i = Wei as the initial
        encroachable water in place"), equivalently Dake Eq. (9.20) and Ahmed
        Eq. (10-39). It is the influx that would occur if the aquifer were drawn down to
        zero absolute pressure, so it is a model parameter and an upper bound, not a
        producible volume: reaching it would require the inner boundary to be held at
        zero psia for infinite time.

        It is NOT ``ct * Wi * (p_i - p)``. That expression is the cumulative influx at a
        sustained boundary pressure ``p``, and it is :meth:`sustained_influx_limit_bbl`.
        The two are confused often enough that the evidence card for this module records
        the substitution as its first correction.

        Assumptions
        -----------
        Constant ``ct`` from ``p_i`` down to zero absolute pressure, which is a linear
        extrapolation far outside any range where the compressibility was measured.

        Returns
        -------
        float
            ``Wei``, reservoir bbl.

        Raises
        ------
        InvalidInputError
            Never from here; the fields were validated at construction.
        """
        return self.storage_bbl_per_psi() * self.initial_pressure_psia

    def sustained_influx_limit_bbl(self, boundary_pressure_psia: float) -> float:
        """Cumulative influx approached if the boundary is held at one pressure forever.

        ``We(inf) = ct * Wi * (p_i - p_wf)``, reservoir bbl. This is the asymptote of
        Fetkovich Eq. (5) as ``t -> inf``, and it is the bound that actually constrains
        a history with a sustained pressure drop: it is strictly below
        :meth:`maximum_influx_bbl` for any positive boundary pressure.

        Parameters
        ----------
        boundary_pressure_psia:
            Sustained inner-boundary pressure, psia, absolute.

        Returns
        -------
        float
            Limiting cumulative influx, reservoir bbl. Negative if the boundary
            pressure is above the initial aquifer pressure, which is net efflux.

        Raises
        ------
        InvalidInputError
            If ``boundary_pressure_psia`` is not finite and strictly positive.
        """
        pressure = require_positive(boundary_pressure_psia, "boundary_pressure_psia")
        return self.storage_bbl_per_psi() * (self.initial_pressure_psia - pressure)

    def aquifer_pressure_psia(self, cumulative_influx_bbl: float) -> float:
        """Average aquifer pressure after a cumulative influx, Fetkovich Eq. (13).

        ``p_aq_bar = p_i * (1 - We/Wei) = p_i - We/(ct*Wi)``.

        Parameters
        ----------
        cumulative_influx_bbl:
            Cumulative influx from virgin conditions, reservoir bbl.

        Returns
        -------
        float
            Average aquifer pressure, psia. Not clamped: an influx above ``Wei``
            returns a negative pressure rather than a floor, because a negative
            pressure here is a symptom the caller needs to see.

        Raises
        ------
        InvalidInputError
            If ``cumulative_influx_bbl`` is not finite.
        """
        influx = require_finite(cumulative_influx_bbl, "cumulative_influx_bbl")
        return self.initial_pressure_psia - influx / self.storage_bbl_per_psi()

    # -- the recursion -----------------------------------------------------

    def _advance(
        self, aquifer_pressure: float, boundary_pressure: float, timestep: float
    ) -> tuple[float, float, float]:
        """Advance one step. Returns ``(influx_increment, end_pressure, decline)``.

        The single arithmetic kernel of the module; :meth:`step` and
        :meth:`influx_history` differ only in how they obtain the boundary pressure and
        in what they record.
        """
        # -expm1(-x) rather than 1 - exp(-x): the naive form cancels catastrophically
        # for dt << tau, which is exactly the regime a timestep-refinement study walks
        # into. At dt/tau = 1e-8 it loses about eight significant digits.
        decline = -math.expm1(-timestep / self.time_constant_days())
        influx = self.storage_bbl_per_psi() * (aquifer_pressure - boundary_pressure) * decline
        if not math.isfinite(influx):
            # Reachable only from a driving head so large that ct*Wi*dp overflows even
            # though ct*Wi*p_i does not. The two pressures are the caller's, so the
            # message names them rather than letting a NaN travel on and be reported
            # against an internal field of the record.
            raise InvalidInputError(
                f"the influx increment is not finite: aquifer_pressure_psia="
                f"{aquifer_pressure!r} and reservoir_pressure_psia={boundary_pressure!r} "
                f"give a driving head of {aquifer_pressure - boundary_pressure!r} psi, "
                f"which overflows against a storativity of "
                f"{self.storage_bbl_per_psi()!r} bbl/psi"
            )
        # Eq. (13) applied incrementally. Algebraically identical to
        # p_i * (1 - We_n/Wei), but that form subtracts two numbers of order p_i to
        # leave a small difference early in a history, and loses precision doing it.
        end_pressure = aquifer_pressure - influx / self.storage_bbl_per_psi()
        return influx, end_pressure, decline

    def step(
        self,
        *,
        aquifer_pressure_psia: float,
        reservoir_pressure_psia: float,
        timestep_days: float,
    ) -> AquiferStep:
        """Advance the aquifer material balance by one timestep, Fetkovich Eq. (6).

        The recursion, with every pressure named:

            dWe_n = (Wei / p_i) * (p_aq_bar_{n-1} - p_wf_bar_n)
                    * (1 - exp(-J * p_i * dt_n / Wei))

        ``p_i`` occurs three times in the published form and every one of them is the
        INITIAL aquifer pressure, ``self.initial_pressure_psia``, fixed for the whole
        run. The substitution of the current reservoir or aquifer pressure for any of
        them is the standard transcription error, so each is accounted for here:

        1. ``Wei / p_i``: comes from ``Wei = ct * Wi * p_i`` (Eq. A-11), so the ratio is
           ``ct * Wi``, a constant in bbl/psi. Initial pressure, and it cancels.
        2. ``J * p_i`` in the exponent: comes from the aquifer's initial open-flow
           potential ``(q_wi)max = J * p_i`` (Eq. B-6). Initial pressure, and dividing
           by ``Wei = ct*Wi*p_i`` cancels it again, leaving ``dt / tau`` with
           ``tau = ct*Wi/J``.
        3. ``p_aq_bar_n = p_i * (1 - We_n/Wei)`` (Eq. 13), the aquifer material balance
           that produces the end-of-step pressure. Initial pressure.

        Because ``p_i`` cancels in 1 and 2, the implementation evaluates the cancelled
        form ``dWe = ct*Wi*(p_aq_bar_{n-1} - p_wf_bar_n)*(1 - exp(-dt/tau))``. Initial
        pressure then enters the arithmetic in exactly one place -- the aquifer material
        balance -- and the substitution error has nowhere left to hide.

        The two pressures that are NOT ``p_i``:

        * ``p_aq_bar_{n-1}`` is ``aquifer_pressure_psia``: the average aquifer pressure
          at the START of the step, i.e. the value Eq. (13) produced at the end of the
          previous step. It is the state variable.
        * ``p_wf_bar_n`` is ``reservoir_pressure_psia``: the inner-boundary pressure
          held constant across this step. Fetkovich Eq. (8) sets it to the mean of the
          boundary pressure at the two ends of the interval; this method does not
          perform that averaging, because in a coupled run the end-of-step reservoir
          pressure is itself unknown until the coupled iteration converges. Supply the
          value you intend to hold, or use :meth:`influx_history`, which applies
          Eq. (8) for you.

        Parameters
        ----------
        aquifer_pressure_psia:
            ``p_aq_bar_{n-1}``, psia, absolute.
        reservoir_pressure_psia:
            ``p_wf_bar_n``, psia, absolute, constant over the step.
        timestep_days:
            ``dt_n``, days, strictly positive.

        Returns
        -------
        AquiferStep
            The step record. ``cumulative_influx_bbl`` is reconstructed from the
            starting aquifer pressure through Eq. (13), so it is the cumulative influx
            from virgin conditions and not merely this step's increment.

        Assumptions
        -----------
        Pseudosteady or steady state in the aquifer, single-phase slightly compressible
        water, constant ``ct``, and a boundary pressure that is genuinely constant over
        the step. The step is exact for its own model under those assumptions at any
        ``timestep_days``; there is no stability limit and no truncation error to
        refine away.

        What this does NOT do
        ---------------------
        It does not average the boundary pressure (see above), does not solve the
        coupled reservoir pressure, does not clip a negative increment, does not
        enforce ``We <= Wei``, does not compute ``J``, does not verify that the
        pseudosteady assumption holds, and does not model the early transient period
        that Fetkovich's method neglects by construction.

        Raises
        ------
        InvalidInputError
            If ``aquifer_pressure_psia`` or ``reservoir_pressure_psia`` is not finite
            and strictly positive, or if ``timestep_days`` is not finite and strictly
            positive. A zero timestep raises rather than returning a zero increment:
            a step of no duration is almost always a repeated timestamp in a history,
            and silently returning zero would hide it. Also if the driving head is so
            large that the increment ``ct*Wi*dp`` overflows, in which case the message
            names the two pressures that produced it.
        """
        aquifer_pressure = require_positive(aquifer_pressure_psia, "aquifer_pressure_psia")
        boundary_pressure = require_positive(reservoir_pressure_psia, "reservoir_pressure_psia")
        timestep = require_positive(timestep_days, "timestep_days")

        influx, end_pressure, decline = self._advance(aquifer_pressure, boundary_pressure, timestep)
        influx_before = self.storage_bbl_per_psi() * (self.initial_pressure_psia - aquifer_pressure)
        return AquiferStep(
            time_days=timestep,
            timestep_days=timestep,
            boundary_pressure_psia=boundary_pressure,
            aquifer_pressure_start_psia=aquifer_pressure,
            aquifer_pressure_end_psia=end_pressure,
            influx_increment_bbl=influx,
            cumulative_influx_bbl=influx_before + influx,
            decline_factor=decline,
            boundary_pressure_rule=BOUNDARY_RULE_CALLER_SUPPLIED,
            method=FETKOVICH_METHOD,
            n_points=1,
        )

    def influx_history(
        self,
        *,
        times_days: Sequence[float],
        reservoir_pressure_psia: Sequence[float],
    ) -> tuple[AquiferStep, ...]:
        """Step through a boundary-pressure history from virgin aquifer conditions.

        The aquifer starts at ``initial_pressure_psia`` with zero cumulative influx at
        ``times_days[0]``, and one :class:`AquiferStep` is returned per interval, so a
        history of ``n`` samples yields ``n - 1`` records. Over interval ``n`` the
        inner-boundary pressure is held at the Eq. (8) mean

            p_wf_bar_n = (p_wf_{n-1} + p_wf_n) / 2

        which is what makes the scheme second-order accurate in the timestep for a
        smoothly varying boundary pressure, rather than the first order an end-point
        value would give.

        Parameters
        ----------
        times_days:
            Sample times, days, strictly increasing. Absolute, not interval lengths;
            ``times_days[0]`` need not be zero. Unequal intervals are allowed, and
            unlike the van Everdingen-Hurst superposition convention nothing here
            requires them to be equal.
        reservoir_pressure_psia:
            Inner-boundary pressure at each sample time, psia, absolute. Same length as
            ``times_days``. The first value is the boundary pressure at the start of
            the history; it is used by Eq. (8) for the first interval and is not
            required to equal ``initial_pressure_psia``.

        Returns
        -------
        tuple of AquiferStep
            One record per interval, in time order. A tuple rather than a list per
            contract C5, so a validated history cannot be edited in place.

        Assumptions
        -----------
        Those of :meth:`step`, plus a boundary pressure well enough resolved by the
        supplied samples that the midpoint rule represents it. The scheme itself
        contributes no timestep error; refining the timestep only refines the
        representation of the pressure history.

        What this does NOT do
        ---------------------
        It does not sort, resample, interpolate or de-duplicate the series, and it does
        not extend the history beyond the last sample. A non-monotonic time series
        raises rather than being reordered, because out-of-order times in a production
        history usually mean two sources were concatenated without alignment.

        Raises
        ------
        InvalidInputError
            If the two series differ in length, if either holds a non-finite value, if
            fewer than two samples are supplied, if ``times_days`` does not strictly
            increase, or if any pressure is not strictly positive.
        """
        times = as_float_sequence(times_days, "times_days")
        pressures = as_float_sequence(reservoir_pressure_psia, "reservoir_pressure_psia")
        require_same_length(times, pressures, "times_days", "reservoir_pressure_psia")
        require_min_length(times, "times_days", 2, "at least one aquifer timestep")
        require_strictly_increasing(times, "times_days")
        for index, pressure in enumerate(pressures):
            require_positive(pressure, f"reservoir_pressure_psia[{index}]")

        records = []
        aquifer_pressure = self.initial_pressure_psia
        cumulative = 0.0
        for index in range(1, len(times)):
            timestep = times[index] - times[index - 1]
            boundary_pressure = 0.5 * (pressures[index - 1] + pressures[index])
            influx, end_pressure, decline = self._advance(aquifer_pressure, boundary_pressure, timestep)
            cumulative += influx
            records.append(
                AquiferStep(
                    time_days=times[index],
                    timestep_days=timestep,
                    boundary_pressure_psia=boundary_pressure,
                    aquifer_pressure_start_psia=aquifer_pressure,
                    aquifer_pressure_end_psia=end_pressure,
                    influx_increment_bbl=influx,
                    cumulative_influx_bbl=cumulative,
                    decline_factor=decline,
                    boundary_pressure_rule=BOUNDARY_RULE_EQ8_MIDPOINT,
                    method=FETKOVICH_METHOD,
                    n_points=2,
                )
            )
            aquifer_pressure = end_pressure
        return tuple(records)

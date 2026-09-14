"""Forward generators for synthetic gas-reservoir depletion histories.

Why this is a separate module from ``material_balance``
------------------------------------------------------
``material_balance`` is the *inverse* direction: it takes an observed history and
estimates gas in place. This module is the *forward* direction: it takes a known gas
in place and manufactures the history. The two must not share code.

If the generator called the estimator's routines -- or if both were built on one
shared "the balance is this expression" helper -- then every parameter-recovery test
would be circular. Feeding a generator's output back into an estimator that solves the
identical floating-point expression proves only that the expression was inverted
correctly, which is arithmetic, not physics. It cannot detect a sign error, a wrong
standard-condition basis, or a missing term, because the same defect would be present
on both sides and would cancel. Keeping the two modules apart makes a recovery test a
statement about the physics rather than about algebra that was applied twice.

The same argument is why the aquifer recursion is written out here from the primary
source rather than delegated to ``aquifer.FetkovichAquifer.step``: the generator reads
the aquifer's four published parameters off the dataclass and applies Fetkovich's
Eq. (6) itself, so a transcription error in either implementation shows up as a
disagreement instead of cancelling. ``tests/test_depletion.py`` cross-checks the two
against each other whenever the aquifer module is importable.

The physics implemented
-----------------------
A single-tank dry-gas reservoir at constant temperature, with a constant hydrocarbon
pore volume that may be invaded by water:

    (G - Gp) * Bg(p) = HCPV_i - (We - Bw * Wp)                       [reservoir ft^3]

with ``Bg = (psc / (Tsc * Zsc)) * Z * T / p`` and ``HCPV_i = G * Bg(pi)``. Dividing
through by ``(psc / (Tsc * Zsc)) * T`` puts it in the form this module actually
evaluates, which is Dake's water-drive p/Z equation:

    p/Z = (pi/Zi) * (1 - Gp/G) / (1 - We_net / HCPV_i)

The standard-condition group ``psc / (Tsc * Zsc)`` cancels out of the volumetric case
entirely and survives in the water-drive case only through ``HCPV_i``, which is what
converts a barrel of influx into a fraction of the pore volume. That asymmetry is a
testable property, not an accident, and ``StandardConditions`` is therefore a required
argument rather than a module constant.

What these generators do NOT model
----------------------------------
Rock and connate-water expansion (the ``Efw`` term), retrograde condensation, gas
trapped behind an advancing water front, gas dissolved in the water phase, aquifer
pressure gradients, and any spatial structure whatsoever. A tank model is
zero-dimensional by construction. Dake's magnitude check for the omitted rock and
connate-water term is ``(cw*Swc + cf)*dp/(1 - Swc) = 0.01325`` for
``cw = 3e-6 /psi, cf = 10e-6 /psi, Swc = 0.2, dp = 1000 psi`` -- about 1.3 percent of
the balance, which is not negligible at large drawdown and is the first thing to add
if a study needs it.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .errors import InvalidInputError
from .numerics import safeguarded_newton
from .units import CUBIC_FEET_PER_BARREL, StandardConditions
from .validation import (
    as_float_sequence,
    require_finite,
    require_min_length,
    require_non_negative,
    require_positive,
    require_same_length,
    require_strictly_increasing,
)

__all__ = [
    "NOISE_FREE",
    "DepletionHistory",
    "DepletionTruth",
    "NoiseModel",
    "simulate_volumetric_depletion",
    "simulate_water_drive_depletion",
]

#: How far below one the flooded fraction is held at the lower end of a pressure
#: search. Set from conditioning: ``1 - flooded`` is formed in double precision near
#: one, where the spacing of representable numbers is 2.2e-16, so 1e-9 is roughly
#: 4.5e6 spacings clear of cancellation while still placing the lower end of the
#: bracket a factor 1e9 of p/Z below the root.
_POLE_STANDOFF = 1.0e-9

#: Number of sample intervals used to test whether p/Z is monotone over the pressure
#: search interval. A scan cannot prove monotonicity; this many points resolve the
#: non-monotonicity of any deviation-factor trend whose features are wider than about
#: one part in 128 of the interval, which covers the correlation-shaped cases the
#: generator is meant to be driven with.
_MONOTONICITY_SAMPLES = 256


@dataclass(frozen=True)
class NoiseModel:
    """Measurement error added to a generated history.

    The noise is applied *after* the physics, to the reported series only. It never
    feeds back into the balance, so the underlying history stays exactly conservative
    and :class:`DepletionHistory` can carry both the observed and the true series.
    That separation is the point: an estimator must be judged against the truth the
    generator used, not against a perturbed re-solution of the balance.

    Attributes
    ----------
    pressure_sigma_psia:
        Standard deviation of independent Gaussian error on each reported pressure,
        in psia. Represents gauge and shut-in scatter.
    pressure_bias_psia:
        A systematic offset added to every reported pressure, in psia. Kept separate
        from the random term because bias and scatter have completely different
        consequences for an extrapolated x-intercept, and a study that lumps them
        together cannot tell which one it is seeing.
    z_relative_sigma:
        Relative standard deviation of independent Gaussian error on each reported
        deviation factor, dimensionless. Represents correlation choice and chart
        reading rather than instrument error.
    cumulative_gas_relative_sigma:
        Relative standard deviation of independent Gaussian error on each reported
        cumulative gas volume, dimensionless. Represents allocation and metering
        error.
    label:
        Carried into the run record so a report can name the noise case. It defaults
        to the empty string rather than to a word such as "noise free", because a
        default that asserts something about the sigmas is wrong the moment a caller
        sets a sigma and leaves the label alone. :meth:`describe` supplies the wording
        from the sigmas themselves when no label is given.

    Notes
    -----
    The error on cumulative production is applied point by point. At a large sigma
    this can make the reported series non-monotone, and the generator does not repair
    it -- a real allocated production record can be non-monotone for exactly this
    reason, and silently sorting or clipping it would hide the defect a study of
    measurement error exists to expose.

    Raises
    ------
    InvalidInputError
        If any standard deviation is negative or any field is not finite.
    """

    pressure_sigma_psia: float = 0.0
    pressure_bias_psia: float = 0.0
    z_relative_sigma: float = 0.0
    cumulative_gas_relative_sigma: float = 0.0
    label: str = ""

    def __post_init__(self) -> None:
        """Validate the model at construction, so an invalid one cannot be passed on."""
        require_non_negative(self.pressure_sigma_psia, "pressure_sigma_psia")
        require_finite(self.pressure_bias_psia, "pressure_bias_psia")
        require_non_negative(self.z_relative_sigma, "z_relative_sigma")
        require_non_negative(self.cumulative_gas_relative_sigma, "cumulative_gas_relative_sigma")

    def is_noise_free(self) -> bool:
        """Report whether every term is exactly zero, so observed and true series coincide."""
        return (
            self.pressure_sigma_psia == 0.0
            and self.pressure_bias_psia == 0.0
            and self.z_relative_sigma == 0.0
            and self.cumulative_gas_relative_sigma == 0.0
        )

    def describe(self) -> str:
        """One-line description suitable for a report header or a run record.

        The leading name is the caller's label when one was given. Otherwise it is
        derived from the sigmas, so an unlabelled model never describes itself as
        noise free while carrying a non-zero standard deviation. A run record that
        contradicts the object it was written from is worse than no run record.
        """
        name = self.label or ("noise free" if self.is_noise_free() else "unlabelled noise")
        return (
            f"{name}: sigma_p = {self.pressure_sigma_psia:g} psia, "
            f"bias_p = {self.pressure_bias_psia:g} psia, "
            f"sigma_Z/Z = {self.z_relative_sigma:g}, "
            f"sigma_Gp/Gp = {self.cumulative_gas_relative_sigma:g}"
        )


#: The exactly noise-free case. A frozen dataclass, so it is safe as a shared default
#: and cannot be mutated by a caller into a silently noisy one.
NOISE_FREE = NoiseModel()


@dataclass(frozen=True)
class DepletionTruth:
    """The parameters a history was generated from.

    Every field here is a quantity an estimator is supposed to recover or to assume.
    Shipping them with the history is what makes a recovery test checkable without a
    separate fixture file that can drift away from the data it describes.

    Attributes
    ----------
    gas_in_place_scf:
        The true G, at the declared standard conditions.
    initial_pressure_psia, initial_z_factor, initial_p_over_z_psia:
        Initial reservoir state and the p/Z ordinate it implies.
    temperature_degr:
        Isothermal reservoir temperature, absolute.
    standard_pressure_psia, standard_temperature_degr, standard_z_factor:
        The declared standard-volume basis. Recorded because it is a declared basis
        and not a universal constant: 14.696 psia and 15.025 psia differ by 2.2
        percent in Bg and therefore in any reservoir-volume quantity.
    hydrocarbon_pore_volume_rcf:
        ``G * Bg(pi)``, the constant pore volume available to gas at time zero.
    water_fvf_rb_per_stb:
        Bw, used only to convert produced water back to a reservoir volume.
    drive:
        ``"volumetric"`` or ``"fetkovich_water_drive"``.
    aquifer_parameters:
        Name/value pairs for the aquifer, empty for a volumetric run. A tuple rather
        than an optional dataclass so that "no aquifer" is an empty collection and
        never ``None``.
    noise, seed:
        The noise model and the seed that produced the observed series.
    """

    gas_in_place_scf: float
    initial_pressure_psia: float
    initial_z_factor: float
    initial_p_over_z_psia: float
    temperature_degr: float
    standard_pressure_psia: float
    standard_temperature_degr: float
    standard_z_factor: float
    hydrocarbon_pore_volume_rcf: float
    water_fvf_rb_per_stb: float
    drive: str
    aquifer_parameters: tuple[tuple[str, float], ...]
    noise: NoiseModel
    seed: int

    def gas_fvf_rcf_per_scf(self, pressure_psia: float, z_factor: float) -> float:
        """Bg at ``pressure_psia`` on this history's declared basis, in rcf/scf.

        Provided so a consumer can reconstruct reservoir volumes without guessing the
        standard-condition basis. ``Bg = (psc / (Tsc * Zsc)) * Z * T / p``.
        """
        pressure = require_positive(pressure_psia, "pressure_psia")
        z = require_positive(z_factor, "z_factor")
        coefficient = self.standard_pressure_psia / (self.standard_temperature_degr * self.standard_z_factor)
        return coefficient * z * self.temperature_degr / pressure


@dataclass(frozen=True)
class DepletionHistory:
    """A generated depletion history, observed series plus the truth behind it.

    Attributes
    ----------
    times_days:
        Observation times. Strictly increasing; the first entry is the initial
        condition, at which cumulative production is zero.
    pressures_psia, z_factors, cumulative_gas_scf:
        The reported (noisy) series. Identical to the corresponding ``true_*`` series
        when the noise model is exactly zero.
    cumulative_water_stb:
        Cumulative water production at the surface, in stock-tank barrels. Never
        noised, because the generator's water-production model is a declared
        bookkeeping fraction rather than a measurement. The ``_stb`` suffix is not
        decoration: this series and ``water_influx_bbl`` are different volumes of the
        same water and are bridged by ``truth.water_fvf_rb_per_stb``.
    water_influx_bbl:
        Cumulative water influx from the aquifer, in reservoir barrels. All zeros for
        a volumetric run.
    true_pressures_psia, true_z_factors, true_cumulative_gas_scf:
        The series the balance was actually solved with.
    residual_p_over_z_psia:
        The residual of the coupled balance left at each step, in psia of p/Z. Step
        zero is the initial condition and is exactly zero by construction. Multiply by
        Z to read it as an equivalent pressure error.
    solver_tolerance:
        The bracket tolerance requested of the root finder.
    warnings:
        Conditions found during generation that a consumer must know about before
        quoting the history as a reference dataset. Empty for a clean run. The only
        condition raised at present is a non-monotone ``p/Z``, which allows the step
        balance to have more than one root; see the note on uniqueness in
        :func:`simulate_volumetric_depletion`.
    truth:
        The generating parameters.
    n_points, method:
        Audit metadata required of every result object in this package.

    Notes
    -----
    Series are tuples, so a consumer cannot modify a generated history in place and
    then present it as the original.
    """

    times_days: tuple[float, ...]
    pressures_psia: tuple[float, ...]
    z_factors: tuple[float, ...]
    cumulative_gas_scf: tuple[float, ...]
    cumulative_water_stb: tuple[float, ...]
    water_influx_bbl: tuple[float, ...]
    true_pressures_psia: tuple[float, ...]
    true_z_factors: tuple[float, ...]
    true_cumulative_gas_scf: tuple[float, ...]
    residual_p_over_z_psia: tuple[float, ...]
    solver_tolerance: float
    warnings: tuple[str, ...]
    truth: DepletionTruth
    n_points: int
    method: str

    @property
    def max_abs_residual_p_over_z_psia(self) -> float:
        """Worst absolute balance residual over the whole history, in psia of p/Z.

        This is the number that lets a case study say the generator's own numerical
        error is orders of magnitude below the physical effect being demonstrated.
        Without it a reader cannot tell a solver artefact from reservoir behaviour.
        """
        return max(abs(value) for value in self.residual_p_over_z_psia)

    def p_over_z_psia(self) -> tuple[float, ...]:
        """Observed p/Z ordinate, from the reported pressures and deviation factors."""
        return tuple(p / z for p, z in zip(self.pressures_psia, self.z_factors, strict=True))

    def true_p_over_z_psia(self) -> tuple[float, ...]:
        """Return the true p/Z ordinate, from the series the balance was solved with."""
        return tuple(p / z for p, z in zip(self.true_pressures_psia, self.true_z_factors, strict=True))

    def depletion_fraction(self) -> float:
        """Fraction of the true gas in place produced by the last observation."""
        return self.true_cumulative_gas_scf[-1] / self.truth.gas_in_place_scf


def _require_int(value: object, name: str) -> int:
    """Return ``value`` as an int, rejecting bools and non-integers."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidInputError(f"{name} must be an integer, got {value!r}")
    return int(value)


def _require_callable(value: object, name: str) -> Callable[[float], float]:
    if not callable(value):
        raise InvalidInputError(f"{name} must be callable, got {type(value).__name__}")
    return value


def _require_standard(value: object) -> StandardConditions:
    if not isinstance(value, StandardConditions):
        raise InvalidInputError(
            "standard must be a units.StandardConditions instance; the standard-volume "
            "basis is a declared convention, not a default, and 14.696 psia versus "
            "15.025 psia is a 2.2 percent difference in every reservoir volume"
        )
    return value


def _z_at(z_of_pressure: Callable[[float], float], pressure_psia: float) -> float:
    """Evaluate the caller's deviation-factor callable and validate the result.

    A callable is used rather than a table so that a generator run can be driven by a
    published correlation, by a declared trend, or by an exactly-known constant. The
    last of these is what makes a machine-precision oracle possible.
    """
    try:
        value = z_of_pressure(pressure_psia)
    except Exception as exc:
        raise InvalidInputError(
            f"z_of_pressure({pressure_psia!r}) raised {type(exc).__name__}: {exc}"
        ) from exc
    return require_positive(value, f"z_of_pressure({pressure_psia!r})")


def _p_over_z_monotonicity_warnings(
    z_of_pressure: Callable[[float], float], lower_psia: float, upper_psia: float
) -> tuple[str, ...]:
    """Warn when p/Z is not monotone increasing over the pressure search interval.

    Monotone p/Z is what makes the step balance have a single root, because the p/Z
    the balance demands always falls with the trial pressure. The API contract asks
    only that ``z_of_pressure`` be positive and finite, which does not imply it: a Z
    rising faster than p makes p/Z fall, and the balance then has several roots that
    the bracketed solver resolves to one of, silently, producing a pressure history
    with a jump in it.

    This is a detector, not a proof. It samples ``_MONOTONICITY_SAMPLES`` intervals
    and reports the worst decrease it finds. A feature narrower than the sample
    spacing passes unnoticed, and the absence of a warning is therefore not a
    guarantee of uniqueness. It is reported rather than raised because a deliberately
    pathological Z is a legitimate thing to generate a history with; what is not
    legitimate is doing so without the history saying as much.
    """
    step = (upper_psia - lower_psia) / _MONOTONICITY_SAMPLES
    previous_pressure = lower_psia
    previous_value = previous_pressure / _z_at(z_of_pressure, previous_pressure)
    worst_drop = 0.0
    worst_at = (lower_psia, lower_psia)
    for index in range(1, _MONOTONICITY_SAMPLES + 1):
        pressure = lower_psia + index * step
        value = pressure / _z_at(z_of_pressure, pressure)
        drop = previous_value - value
        if drop > worst_drop:
            worst_drop = drop
            worst_at = (previous_pressure, pressure)
        previous_pressure, previous_value = pressure, value
    if worst_drop <= 0.0:
        return ()
    return (
        f"p/Z is not monotone increasing over the pressure search interval "
        f"({lower_psia!r}, {upper_psia!r}) psia: sampled at {_MONOTONICITY_SAMPLES + 1} "
        f"points it falls by {worst_drop:.6g} psia between {worst_at[0]:.6g} and "
        f"{worst_at[1]:.6g} psia. The step balance can then have more than one root, "
        f"the solver returns one of them without saying which, and the generated "
        f"pressure history can jump between branches. Do not quote this history as a "
        f"reference dataset unless the multiplicity is the thing being studied.",
    )


def _validate_schedule(
    times_days: Sequence[float], gas_rates_scf_per_day: Sequence[float]
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    times = as_float_sequence(times_days, "times_days")
    require_min_length(
        times,
        "times_days",
        2,
        "a depletion history needs an initial state and at least one later observation",
    )
    require_non_negative(times[0], "times_days[0]")
    require_strictly_increasing(times, "times_days")
    rates = as_float_sequence(gas_rates_scf_per_day, "gas_rates_scf_per_day")
    # One rate per interval, not per observation: a reported rate is constant over the
    # interval it is reported for, which is what a daily allocated record means.
    require_same_length(rates, times[:-1], "gas_rates_scf_per_day", "times_days[:-1]")
    for index, rate in enumerate(rates):
        require_non_negative(rate, f"gas_rates_scf_per_day[{index}]")
    return times, rates


def _apply_noise(
    *,
    true_pressures: Sequence[float],
    true_z: Sequence[float],
    true_gas: Sequence[float],
    noise: NoiseModel,
    seed: int,
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    """Draw the measurement error and return the reported series.

    One variate is drawn per point per channel, in the fixed order pressure, Z,
    cumulative gas, whether or not the corresponding standard deviation is zero.
    Consuming the stream unconditionally means that switching one channel on does not
    change the realisation of the others, so two noise cases differing in a single
    sigma remain comparable point by point.
    """
    rng = random.Random(seed)
    pressures = []
    z_factors = []
    gas = []
    for pressure, z, cumulative in zip(true_pressures, true_z, true_gas, strict=True):
        pressure_variate = rng.gauss(0.0, 1.0)
        z_variate = rng.gauss(0.0, 1.0)
        gas_variate = rng.gauss(0.0, 1.0)
        pressures.append(pressure + noise.pressure_bias_psia + noise.pressure_sigma_psia * pressure_variate)
        z_factors.append(z * (1.0 + noise.z_relative_sigma * z_variate))
        gas.append(cumulative * (1.0 + noise.cumulative_gas_relative_sigma * gas_variate))
    return tuple(pressures), tuple(z_factors), tuple(gas)


@dataclass(frozen=True)
class _TankState:
    """The time-invariant tank properties one coupled step needs.

    Grouped so that the step solver takes the varying state as arguments and the
    fixed state as one object, rather than closing over a long argument list that a
    reader has to hold in their head while checking the balance.
    """

    initial_p_over_z_psia: float
    gas_in_place_scf: float
    hydrocarbon_pore_volume_rcf: float
    water_fvf_rb_per_stb: float
    produced_water_fraction: float


def _solve_step(
    *,
    tank: _TankState,
    z_of_pressure: Callable[[float], float],
    produced_gas_scf: float,
    previous_pressure_psia: float,
    previous_influx_bbl: float,
    previous_water_bbl: float,
    aquifer_pressure_psia: float,
    response_bbl_per_psi: float,
    minimum_pressure_psia: float,
    upper_guess_psia: float,
    tolerance: float,
    max_iterations: int,
    label: str,
) -> tuple[float, float, float]:
    """Solve one implicit reservoir/aquifer step for the reservoir pressure.

    Returns ``(pressure_psia, incremental_influx_bbl, residual_p_over_z_psia)``.

    ``response_bbl_per_psi`` is the Fetkovich group ``ct*Wi*(1 - exp(-J*dt/(ct*Wi)))``,
    formed by the caller because it depends only on the timestep. It is exactly zero
    when the productivity index is zero, and then every expression below reduces to the
    closed-tank balance by arithmetic rather than by a branch -- which is what makes
    the zero-productivity-index case identical to the volumetric generator bit for bit
    instead of merely close to it.

    The pole in the required p/Z
    ----------------------------
    ``flooded_fraction`` is affine and strictly decreasing in the trial pressure, so
    ``required_p_over_z`` has exactly one pole: the pressure at which the invaded
    volume equals the whole hydrocarbon pore volume. Below that pressure the balance
    is not merely hard to solve, it is meaningless -- the tank contains more water
    than it has room for. The pole is available in closed form, because the flooded
    fraction is affine::

        p_pole = 2*p_aq - p_prev - 2*(HCPV_bbl - net_influx_prev_bbl) / R'

    with ``R' = (1 - produced_water_fraction) * response_bbl_per_psi`` the part of the
    step response that stays in the reservoir. The search is bracketed on the physical
    side of that pole rather than on ``minimum_pressure_psia``. Bracketing on the
    pressure floor was a defect: for any aquifer strong enough to matter the pole sits
    above the floor long before it has any bearing on the root, and the step was then
    rejected as unsolvable while a unique, entirely physical root with a few percent
    of the pore volume invaded sat inside the interval.

    Uniqueness of the root
    ----------------------
    ``required_p_over_z`` is strictly decreasing in the trial pressure above the pole:
    a higher reservoir pressure reduces the influx, which leaves more pore volume for
    gas and so lowers the p/Z the balance demands. The residual
    ``p/Z(p) - required_p_over_z(p)`` is therefore strictly increasing, and the root
    unique, *whenever p/Z is itself non-decreasing in p*.

    That last condition is a property of the caller's ``z_of_pressure`` and it does
    not follow from the positivity and finiteness the contract asks of it. A Z that
    rises faster than p over some interval makes p/Z fall there, and the step balance
    can then have three roots rather than one. ``_simulate`` samples p/Z over the
    whole search interval once per run and records a warning on the returned history
    when it finds that, but a grid scan detects non-monotonicity only at the scale it
    samples and can never prove uniqueness.
    """

    def incremental_influx_bbl(trial_pressure_psia: float) -> float:
        # Fetkovich Eq. (8): the inner-boundary pressure held constant over the step is
        # the mean of its values at the two ends. That is what makes the step implicit,
        # because the influx depends on the pressure the influx is helping to set.
        boundary_pressure = 0.5 * (previous_pressure_psia + trial_pressure_psia)
        return response_bbl_per_psi * (aquifer_pressure_psia - boundary_pressure)

    def flooded_fraction(trial_pressure_psia: float) -> float:
        delta_influx = incremental_influx_bbl(trial_pressure_psia)
        total_influx = previous_influx_bbl + delta_influx
        total_water = (
            previous_water_bbl + tank.produced_water_fraction * delta_influx / tank.water_fvf_rb_per_stb
        )
        # Produced water is subtracted once, here, as a reservoir volume. Subtracting it
        # again anywhere else would double-count it and bias the recovered gas in place.
        net_influx_rcf = (total_influx - tank.water_fvf_rb_per_stb * total_water) * CUBIC_FEET_PER_BARREL
        return net_influx_rcf / tank.hydrocarbon_pore_volume_rcf

    def required_p_over_z(trial_pressure_psia: float) -> float:
        return (
            tank.initial_p_over_z_psia
            * (1.0 - produced_gas_scf / tank.gas_in_place_scf)
            / (1.0 - flooded_fraction(trial_pressure_psia))
        )

    def residual(trial_pressure_psia: float) -> float:
        return trial_pressure_psia / _z_at(z_of_pressure, trial_pressure_psia) - required_p_over_z(
            trial_pressure_psia
        )

    def residual_derivative(trial_pressure_psia: float) -> float:
        # The deviation factor arrives as an opaque callable, so there is no analytic
        # derivative available. A central difference is safe here only because the
        # solver is bracketed: a poor derivative can slow convergence but cannot move
        # the answer outside the bracket.
        offset = max(1.0e-6, 1.0e-7 * abs(trial_pressure_psia))
        return (residual(trial_pressure_psia + offset) - residual(trial_pressure_psia - offset)) / (
            2.0 * offset
        )

    # Locate the pole and put the lower end of the search on the physical side of it.
    # ``reservoir_response`` is what the pore volume actually keeps; with every
    # encroached barrel produced again it is zero and the flooded fraction does not
    # depend on the trial pressure at all, so there is no pole to stand off from.
    reservoir_response_bbl_per_psi = (1.0 - tank.produced_water_fraction) * response_bbl_per_psi
    lower_psia = minimum_pressure_psia
    pole_limited = False
    if reservoir_response_bbl_per_psi > 0.0:
        pore_volume_bbl = tank.hydrocarbon_pore_volume_rcf / CUBIC_FEET_PER_BARREL
        previous_net_influx_bbl = previous_influx_bbl - tank.water_fvf_rb_per_stb * previous_water_bbl
        pole_psia = (
            2.0 * aquifer_pressure_psia
            - previous_pressure_psia
            - 2.0 * (pore_volume_bbl - previous_net_influx_bbl) / reservoir_response_bbl_per_psi
        )
        # Magnitude of d(flooded)/dp, which is negative, so the affine flooded fraction
        # can be written flooded_fraction(p) = 1 - slope_per_psi * (p - p_pole).
        slope_per_psi = (
            0.5 * reservoir_response_bbl_per_psi * CUBIC_FEET_PER_BARREL / tank.hydrocarbon_pore_volume_rcf
        )
        # Stand off the pole by the pressure that brings the flooded fraction
        # _POLE_STANDOFF below one. The standoff is set from conditioning, not from a
        # trial run: 1 - flooded is evaluated in double precision near 1, where the
        # representation spacing is 2.2e-16, so 1e-9 is some 4.5e6 spacings clear of
        # cancellation; and it leaves required_p_over_z a factor 1e9 above any p/Z the
        # reservoir can reach, so the residual at the lower end is unambiguously
        # negative and the bracket genuinely changes sign.
        lower_psia = max(lower_psia, pole_psia + _POLE_STANDOFF / slope_per_psi)
        pole_limited = lower_psia > minimum_pressure_psia

    if lower_psia >= upper_guess_psia:
        # No trial pressure the reservoir can reach leaves room for the gas. This is
        # the genuine "the aquifer fills the pore volume" failure, and the fraction
        # quoted is the one at the highest attainable pressure, not at the floor.
        raise InvalidInputError(
            f"at {label} the invaded volume reaches "
            f"{flooded_fraction(upper_guess_psia):.4f} of the hydrocarbon pore volume "
            f"even at {upper_guess_psia!r} psia, the highest pressure the reservoir can "
            f"reach. The tank balance has no solution once encroached water fills the "
            f"pore volume; reduce aquifer.productivity_index_bbl_per_day_psi, reduce "
            f"aquifer.water_volume_bbl, or shorten the timestep."
        )
    if not pole_limited:
        # The flooded fraction can still exceed one without a pole when every
        # encroached barrel is produced again, in which case it does not vary with the
        # trial pressure and the whole interval is unusable.
        floor_flooded = flooded_fraction(lower_psia)
        if floor_flooded >= 1.0:
            raise InvalidInputError(
                f"at {label} the invaded volume reaches {floor_flooded:.4f} of the "
                f"hydrocarbon pore volume at every trial pressure. The tank balance has "
                f"no solution once encroached water fills the pore volume; reduce "
                f"aquifer.productivity_index_bbl_per_day_psi, reduce "
                f"aquifer.water_volume_bbl, or shorten the timestep."
            )
        if residual(lower_psia) > 0.0:
            raise InvalidInputError(
                f"at {label} the schedule drives the reservoir below "
                f"minimum_pressure_psia = {minimum_pressure_psia!r}. Lower that floor if "
                f"the depletion is intended, or reduce the offtake."
            )
    # Where the pole binds, the lower end already lies above minimum_pressure_psia, so
    # the root cannot fall below the floor and there is nothing to check.

    # The upper bound is sufficient because required_p_over_z falls with the trial
    # pressure while p/Z rises with it for any physical deviation factor, and neither
    # the remaining gas nor the aquifer can raise the reservoir above the higher of the
    # two initial pressures. If that reasoning is ever violated, safeguarded_newton
    # raises on the missing sign change rather than returning a root from outside the
    # bracket.
    bracket = (lower_psia, upper_guess_psia)
    # Warm start from the previous step's deviation factor. Where Z is constant this
    # lands on the exact root at the first residual evaluation, which is what gives the
    # constant-Z limiting case a p/Z line that is straight to the last bit. The warm
    # start is skipped when the previous pressure is itself below the pole, where
    # required_p_over_z has the wrong sign and would send the iterate backwards.
    guess: float | None = None
    if previous_pressure_psia > lower_psia:
        guess = required_p_over_z(previous_pressure_psia) * _z_at(z_of_pressure, previous_pressure_psia)
        if not math.isfinite(guess):
            guess = None
    pressure = safeguarded_newton(
        residual,
        residual_derivative,
        bracket=bracket,
        initial_guess=guess,
        tolerance=tolerance,
        max_iterations=max_iterations,
        description=f"reservoir pressure at {label}",
    )
    return pressure, incremental_influx_bbl(pressure), residual(pressure)


def _simulate(
    *,
    gas_in_place_scf: float,
    initial_pressure_psia: float,
    temperature_degr: float,
    times_days: Sequence[float],
    gas_rates_scf_per_day: Sequence[float],
    z_of_pressure: Callable[[float], float],
    standard: StandardConditions,
    noise: NoiseModel,
    seed: int,
    minimum_pressure_psia: float,
    solver_tolerance: float,
    max_iterations: int,
    aquifer: object | None,
    produced_water_fraction: float,
    water_fvf_rb_per_stb: float,
    method: str,
) -> DepletionHistory:
    """Shared stepping engine for both public generators.

    The two public functions differ only in whether an aquifer is attached. With no
    aquifer the influx is the literal float ``0.0`` at every step, so the balance
    residual is evaluated by bit-identical arithmetic in both cases. That is what
    makes the zero-productivity-index reduction exact rather than merely close, and it
    is the reason the influx is added into the balance rather than branched around.
    """
    gas_in_place = require_positive(gas_in_place_scf, "gas_in_place_scf")
    initial_pressure = require_positive(initial_pressure_psia, "initial_pressure_psia")
    temperature = require_positive(temperature_degr, "temperature_degr")
    minimum_pressure = require_positive(minimum_pressure_psia, "minimum_pressure_psia")
    tolerance = require_positive(solver_tolerance, "solver_tolerance")
    budget = _require_int(max_iterations, "max_iterations")
    if budget < 1:
        raise InvalidInputError(f"max_iterations must be at least 1, got {budget}")
    if minimum_pressure >= initial_pressure:
        raise InvalidInputError(
            f"minimum_pressure_psia {minimum_pressure!r} must be below "
            f"initial_pressure_psia {initial_pressure!r}"
        )
    if not isinstance(noise, NoiseModel):
        raise InvalidInputError(
            f"noise must be a NoiseModel instance, got {type(noise).__name__}. The noise "
            f"model is explicit because a synthetic history with undeclared noise cannot "
            f"be used as evidence about an estimator."
        )
    seed_value = _require_int(seed, "seed")
    standard_conditions = _require_standard(standard)
    z_callable = _require_callable(z_of_pressure, "z_of_pressure")
    fraction = require_non_negative(produced_water_fraction, "produced_water_fraction")
    if fraction > 1.0:
        raise InvalidInputError(f"produced_water_fraction must lie in [0, 1], got {fraction!r}")
    water_fvf = require_positive(water_fvf_rb_per_stb, "water_fvf_rb_per_stb")
    times, rates = _validate_schedule(times_days, gas_rates_scf_per_day)

    # Aquifer parameters, read off the contract's four fields. Kept as plain floats so
    # the recursion below is written out in the same symbols as Fetkovich Eq. (6).
    if aquifer is None:
        ct_wi_bbl_per_psi = 0.0
        aquifer_initial_pressure = 0.0
        productivity_index = 0.0
        aquifer_parameters: tuple[tuple[str, float], ...] = ()
    else:
        (
            aquifer_initial_pressure,
            water_volume_bbl,
            total_compressibility_per_psi,
            productivity_index,
        ) = _aquifer_parameters(aquifer)
        if aquifer_initial_pressure < initial_pressure:
            raise InvalidInputError(
                f"aquifer.initial_pressure_psia {aquifer_initial_pressure!r} is below "
                f"initial_pressure_psia {initial_pressure!r}. Fetkovich's aquifer starts "
                f"in equilibrium with the reservoir at a common datum, so at time zero "
                f"its pressure is at least the reservoir's. A lower one makes the first "
                f"step an efflux out of the reservoir and the generator would report a "
                f"negative cumulative water production, which is not a physically "
                f"possible observation. Charge the aquifer to at least "
                f"{initial_pressure!r} psia, or model the loss some other way."
            )
        # ct*Wi in bbl/psi is the grouping that actually appears in the recursion.
        ct_wi_bbl_per_psi = total_compressibility_per_psi * water_volume_bbl
        aquifer_parameters = (
            ("initial_pressure_psia", aquifer_initial_pressure),
            ("water_volume_bbl", water_volume_bbl),
            ("total_compressibility_per_psi", total_compressibility_per_psi),
            ("productivity_index_bbl_per_day_psi", productivity_index),
            ("maximum_influx_bbl", ct_wi_bbl_per_psi * aquifer_initial_pressure),
        )
        if productivity_index > 0.0:
            # tau = ct*Wi/J is the aquifer's own response time. Recorded because it is
            # the yardstick for choosing a timestep: the coupled scheme reaches its
            # second-order accuracy only once the timestep is short compared with it.
            aquifer_parameters += (("time_constant_days", ct_wi_bbl_per_psi / productivity_index),)

    initial_z = _z_at(z_callable, initial_pressure)
    initial_p_over_z = initial_pressure / initial_z
    # Bgi and hence HCPV_i are the only place the standard-condition basis enters. The
    # p/Z ordinate itself is basis-free, which is a property the test suite asserts.
    basis_coefficient = standard_conditions.pressure_psia / (
        standard_conditions.temperature_rankine * standard_conditions.z_factor
    )
    gas_fvf_initial_rcf_per_scf = basis_coefficient * initial_z * temperature / initial_pressure
    hydrocarbon_pore_volume_rcf = gas_in_place * gas_fvf_initial_rcf_per_scf

    pressures = [initial_pressure]
    z_factors = [initial_z]
    cumulative_gas = [0.0]
    cumulative_water = [0.0]
    influx = [0.0]
    residuals = [0.0]

    tank = _TankState(
        initial_p_over_z_psia=initial_p_over_z,
        gas_in_place_scf=gas_in_place,
        hydrocarbon_pore_volume_rcf=hydrocarbon_pore_volume_rcf,
        water_fvf_rb_per_stb=water_fvf,
        produced_water_fraction=fraction,
    )
    # The aquifer can only ever push the reservoir back toward its own initial
    # pressure, so that is the upper end of every pressure search.
    upper_guess = max(initial_pressure, aquifer_initial_pressure)
    # Root uniqueness depends on p/Z rising with pressure, which is a property of the
    # caller's deviation factor and not of the balance. Check it once over the whole
    # search interval, not once per step: the answer cannot change from step to step.
    warnings = _p_over_z_monotonicity_warnings(z_callable, minimum_pressure, upper_guess)

    for index in range(1, len(times)):
        timestep_days = times[index] - times[index - 1]
        produced = cumulative_gas[index - 1] + rates[index - 1] * timestep_days
        if produced >= gas_in_place:
            raise InvalidInputError(
                f"the production schedule reaches Gp = {produced!r} scf at times_days"
                f"[{index}] = {times[index]!r}, which is not below gas_in_place_scf "
                f"{gas_in_place!r}. A tank cannot produce its own contents; shorten the "
                f"schedule or lower the rate."
            )
        previous_influx = influx[index - 1]
        previous_water = cumulative_water[index - 1]
        # Fetkovich Eq. (13): the average aquifer pressure is set by cumulative influx
        # against the maximum encroachable volume, and it is the INITIAL aquifer
        # pressure that appears here, never the current reservoir pressure.
        aquifer_pressure = (
            aquifer_initial_pressure - previous_influx / ct_wi_bbl_per_psi if ct_wi_bbl_per_psi > 0.0 else 0.0
        )
        # Fetkovich Eq. (6) with the exponent written as -J*dt/(ct*Wi). The published
        # form is -J*p_i*dt/Wei, but Wei = ct*Wi*p_i, so the initial aquifer pressure
        # cancels exactly; that cancellation is the cheapest check that the recursion
        # was transcribed correctly. The cancelled form also keeps a zero productivity
        # index finite, where the time constant tau = ct*Wi/J would divide by zero.
        decay = (
            math.exp(-productivity_index * timestep_days / ct_wi_bbl_per_psi)
            if ct_wi_bbl_per_psi > 0.0
            else 1.0
        )
        pressure, delta_influx, step_residual = _solve_step(
            tank=tank,
            z_of_pressure=z_callable,
            produced_gas_scf=produced,
            previous_pressure_psia=pressures[index - 1],
            previous_influx_bbl=previous_influx,
            previous_water_bbl=previous_water,
            aquifer_pressure_psia=aquifer_pressure,
            response_bbl_per_psi=ct_wi_bbl_per_psi * (1.0 - decay),
            minimum_pressure_psia=minimum_pressure,
            upper_guess_psia=upper_guess,
            tolerance=tolerance,
            max_iterations=budget,
            label=f"times_days[{index}] = {times[index]!r}",
        )
        pressures.append(pressure)
        z_factors.append(_z_at(z_callable, pressure))
        cumulative_gas.append(produced)
        influx.append(previous_influx + delta_influx)
        produced_water_stb = previous_water + fraction * delta_influx / water_fvf
        if produced_water_stb < previous_water:
            # Reachable through an efflux step: the reservoir pressure has risen above
            # the aquifer's running average and water is flowing back out. The influx
            # may legitimately go both ways, but the declared produced-water fraction
            # is applied to the incremental influx, so an efflux step un-produces water
            # that was already at the surface. A cumulative production is
            # non-decreasing by construction, and the generator says what happened
            # rather than reporting a series that falls.
            raise InvalidInputError(
                f"at times_days[{index}] = {times[index]!r} the incremental influx is "
                f"{delta_influx!r} bbl, an efflux back into the aquifer, and the declared "
                f"produced_water_fraction {fraction!r} would take the cumulative water "
                f"production from {previous_water!r} down to {produced_water_stb!r} STB. "
                f"A cumulative production cannot decrease. Set produced_water_fraction "
                f"to zero for a schedule that lets the reservoir pressure recover above "
                f"the aquifer's own average, or shorten the schedule."
            )
        cumulative_water.append(produced_water_stb)
        residuals.append(step_residual)

    observed_pressures, observed_z, observed_gas = _apply_noise(
        true_pressures=pressures,
        true_z=z_factors,
        true_gas=cumulative_gas,
        noise=noise,
        seed=seed_value,
    )

    truth = DepletionTruth(
        gas_in_place_scf=gas_in_place,
        initial_pressure_psia=initial_pressure,
        initial_z_factor=initial_z,
        initial_p_over_z_psia=initial_p_over_z,
        temperature_degr=temperature,
        standard_pressure_psia=standard_conditions.pressure_psia,
        standard_temperature_degr=standard_conditions.temperature_rankine,
        standard_z_factor=standard_conditions.z_factor,
        hydrocarbon_pore_volume_rcf=hydrocarbon_pore_volume_rcf,
        water_fvf_rb_per_stb=water_fvf,
        drive="volumetric" if aquifer is None else "fetkovich_water_drive",
        aquifer_parameters=aquifer_parameters,
        noise=noise,
        seed=seed_value,
    )
    return DepletionHistory(
        times_days=times,
        pressures_psia=observed_pressures,
        z_factors=observed_z,
        cumulative_gas_scf=observed_gas,
        cumulative_water_stb=tuple(cumulative_water),
        water_influx_bbl=tuple(influx),
        true_pressures_psia=tuple(pressures),
        true_z_factors=tuple(z_factors),
        true_cumulative_gas_scf=tuple(cumulative_gas),
        residual_p_over_z_psia=tuple(residuals),
        solver_tolerance=tolerance,
        warnings=warnings,
        truth=truth,
        n_points=len(times),
        method=method,
    )


_AQUIFER_FIELDS = (
    "initial_pressure_psia",
    "water_volume_bbl",
    "total_compressibility_per_psi",
    "productivity_index_bbl_per_day_psi",
)


def _aquifer_parameters(aquifer: object) -> tuple[float, float, float, float]:
    """Read and validate the four published Fetkovich parameters off an aquifer object.

    Returns them in the order of :data:`_AQUIFER_FIELDS`. Duck typing is deliberate:
    the four names are fixed by the API contract, so any object carrying them is a
    valid parameter set, and the generator does not need to import the aquifer module
    to use one.
    """
    values = []
    for name in _AQUIFER_FIELDS:
        if not hasattr(aquifer, name):
            raise InvalidInputError(
                f"aquifer must expose the four Fetkovich parameters "
                f"{', '.join(_AQUIFER_FIELDS)}, as aquifer.FetkovichAquifer does; "
                f"{type(aquifer).__name__} has no attribute {name!r}"
            )
        values.append(getattr(aquifer, name))
    initial_pressure = require_positive(values[0], "aquifer.initial_pressure_psia")
    water_volume = require_positive(values[1], "aquifer.water_volume_bbl")
    compressibility = require_positive(values[2], "aquifer.total_compressibility_per_psi")
    productivity_index = require_non_negative(values[3], "aquifer.productivity_index_bbl_per_day_psi")
    return initial_pressure, water_volume, compressibility, productivity_index


def simulate_volumetric_depletion(
    *,
    gas_in_place_scf: float,
    initial_pressure_psia: float,
    temperature_degr: float,
    times_days: Sequence[float],
    gas_rates_scf_per_day: Sequence[float],
    z_of_pressure: Callable[[float], float],
    standard: StandardConditions,
    noise: NoiseModel,
    seed: int,
    minimum_pressure_psia: float = 14.696,
    solver_tolerance: float = 1.0e-12,
    max_iterations: int = 200,
) -> DepletionHistory:
    """Generate a closed-tank dry-gas depletion history.

    The reservoir is a single tank of constant hydrocarbon pore volume at constant
    temperature. Gas is withdrawn on the supplied schedule and the pressure at each
    observation is the pressure at which the remaining gas exactly fills the original
    pore volume:

        (G - Gp) * Bg(p) = G * Bg(pi)   which is   p/Z = (pi/Zi) * (1 - Gp/G)

    The p/Z form is exact for any deviation-factor behaviour, not only for a constant
    Z: the standard-condition group and the reservoir temperature cancel identically.
    Constant Z only makes the inversion from p/Z back to p exact as well.

    Parameters
    ----------
    gas_in_place_scf:
        True gas initially in place at the declared standard conditions, scf.
    initial_pressure_psia:
        Initial volume-averaged reservoir pressure, absolute.
    temperature_degr:
        Isothermal reservoir temperature, absolute.
    times_days:
        Observation times, strictly increasing and non-negative. The first entry is
        the initial condition, where cumulative production is zero.
    gas_rates_scf_per_day:
        One rate per interval, so ``len(times_days) - 1`` entries. Each rate is
        constant over the interval it is reported for, which is what a daily allocated
        production record means.
    z_of_pressure:
        Callable returning the gas deviation factor at a pressure in psia. May wrap a
        published correlation from ``gas_properties`` or a declared trend. It must
        return a positive finite number for every pressure between
        ``minimum_pressure_psia`` and ``initial_pressure_psia``.
    standard:
        The declared standard-volume basis. Required, never defaulted: psc/Tsc is a
        convention and two conventions in common use differ by 2.2 percent in Bg.
    noise:
        Measurement error applied to the reported series only.
    seed:
        Seed for the local ``random.Random`` used by the noise model. Required even
        for a noise-free run so that the call site records which realisation it meant.
    minimum_pressure_psia:
        Lower bound of the pressure search, and the pressure below which the schedule
        is rejected rather than extrapolated.
    solver_tolerance:
        Bracket tolerance passed to the root finder, relative for pressures above 1.
    max_iterations:
        Iteration budget per step.

    Returns
    -------
    DepletionHistory
        Observed and true series, the generating parameters, and the balance residual
        achieved at every step.

    Raises
    ------
    InvalidInputError
        Non-finite, non-positive or mis-shaped arguments; a non-monotone time series;
        a negative rate; a schedule that produces at least the gas in place; a
        schedule that drives the pressure below ``minimum_pressure_psia``; a
        ``z_of_pressure`` that returns a non-positive or non-finite value or raises.
        Also, from the solver, a pressure bracket with no sign change; that is
        unreachable while p/Z rises with pressure, so it indicates either a deviation
        factor that violates that or a defect, and the returned history's ``warnings``
        is where the first of those is reported.
    ConvergenceError
        If a step's iteration budget is exhausted. The last iterate is carried on the
        exception rather than returned as if it had converged.

    Notes
    -----
    Validity: normally pressured, single-tank, dry gas, isothermal, volume-averaged
    pressure at a fixed datum. This function does NOT model rock or connate-water
    expansion, retrograde condensation, trapped gas, gas dissolved in water, or any
    aquifer -- use :func:`simulate_water_drive_depletion` for the last of those.
    Because the pore volume is exactly constant, the generated p/Z series is exactly
    linear in Gp with x-intercept equal to ``gas_in_place_scf``; that is the property
    the water-drive counterexample is measured against.

    Root uniqueness. Each step inverts ``p/Z(p) = required``, which has a single
    solution only where p/Z rises with pressure. That holds for every published dry-gas
    deviation-factor correlation over the pressure range these generators are used in,
    but it does not follow from the positivity and finiteness this function asks of
    ``z_of_pressure``, and a Z rising faster than p makes the inversion multivalued.
    The returned history's ``warnings`` is non-empty when a scan of the search interval
    finds that; a scan cannot prove the absence of it.
    """
    return _simulate(
        gas_in_place_scf=gas_in_place_scf,
        initial_pressure_psia=initial_pressure_psia,
        temperature_degr=temperature_degr,
        times_days=times_days,
        gas_rates_scf_per_day=gas_rates_scf_per_day,
        z_of_pressure=z_of_pressure,
        standard=standard,
        noise=noise,
        seed=seed,
        minimum_pressure_psia=minimum_pressure_psia,
        solver_tolerance=solver_tolerance,
        max_iterations=max_iterations,
        aquifer=None,
        produced_water_fraction=0.0,
        water_fvf_rb_per_stb=1.0,
        method="volumetric_tank",
    )


def simulate_water_drive_depletion(
    *,
    gas_in_place_scf: float,
    initial_pressure_psia: float,
    temperature_degr: float,
    times_days: Sequence[float],
    gas_rates_scf_per_day: Sequence[float],
    z_of_pressure: Callable[[float], float],
    standard: StandardConditions,
    aquifer: object,
    noise: NoiseModel,
    seed: int,
    produced_water_fraction: float = 0.0,
    water_fvf_rb_per_stb: float = 1.0,
    minimum_pressure_psia: float = 14.696,
    solver_tolerance: float = 1.0e-12,
    max_iterations: int = 200,
) -> DepletionHistory:
    """Generate a depletion history for a gas tank coupled to a Fetkovich aquifer.

    Each step solves the reservoir balance and the aquifer inflow together. The
    aquifer's incremental influx over a step follows Fetkovich Eq. (6) with the
    inner-boundary pressure of Eq. (8), the mean of the reservoir pressure at the two
    ends of the step:

        dWe = ct*Wi * (p_aq(n-1) - (p(n-1) + p(n))/2) * (1 - exp(-J*dt/(ct*Wi)))
        p_aq(n) = p_aq(0) - We(n)/(ct*Wi)

    Every aquifer pressure in that recursion is the INITIAL aquifer pressure or the
    aquifer's own running average, never the current reservoir pressure; substituting
    the reservoir pressure is the standard transcription error. The exponent is
    written with ``J*dt/(ct*Wi)`` rather than the published ``J*p_i*dt/Wei`` because
    ``Wei = ct*Wi*p_i`` makes the initial aquifer pressure cancel exactly -- that
    cancellation is the cheapest check that the recursion was transcribed correctly,
    and it keeps a zero productivity index finite.

    Because ``p(n)`` appears inside the influx and the influx sets ``p(n)`` through the
    reservoir balance, the step is implicit. It is solved as a one-dimensional
    bracketed root find on ``p(n)`` using ``numerics.safeguarded_newton``, and the
    residual left at every step is recorded on the returned history.

    Parameters
    ----------
    aquifer:
        An ``aquifer.FetkovichAquifer``, or any object exposing its four published
        parameters ``initial_pressure_psia``, ``water_volume_bbl``,
        ``total_compressibility_per_psi`` and
        ``productivity_index_bbl_per_day_psi``. The recursion is applied here rather
        than delegated, so that a transcription error in either implementation shows
        up as a disagreement between them instead of cancelling.
    produced_water_fraction:
        Fraction of the incremental influx that is produced at the surface. A declared
        bookkeeping fraction, not a saturation or relative-permeability calculation;
        the default of zero means every barrel that encroaches stays in the reservoir.
        Because it is applied to the *incremental* influx, a step in which water flows
        back into the aquifer would reduce the cumulative production; the generator
        raises rather than reporting a cumulative production that decreases.
    water_fvf_rb_per_stb:
        Bw, used to convert produced water back to a reservoir volume. Close to unity
        but not equal to it at high pressure and temperature, so it is exposed rather
        than assumed.

    Other parameters are as for :func:`simulate_volumetric_depletion`.

    Returns
    -------
    DepletionHistory
        With ``water_influx_bbl`` populated and
        ``max_abs_residual_p_over_z_psia`` reporting the worst coupled-step residual.

    Raises
    ------
    InvalidInputError
        Everything :func:`simulate_volumetric_depletion` raises, plus: an aquifer that
        does not expose the four parameters or whose volume, compressibility or
        initial pressure is not positive, an ``aquifer.initial_pressure_psia`` below
        the reservoir's ``initial_pressure_psia``, a negative productivity index, a
        ``produced_water_fraction`` outside [0, 1], a step whose declared produced
        water would take the cumulative water production negative, and a schedule
        under which the invaded volume reaches the hydrocarbon pore volume at every
        pressure the reservoir can reach. That last test is made against the highest
        attainable pressure, not against ``minimum_pressure_psia``: the required p/Z
        has a pole at the pressure where the invaded volume equals the pore volume,
        and for any aquifer strong enough to matter that pole lies above the pressure
        floor while the step still has a perfectly ordinary root above it.
    ConvergenceError
        If a step's iteration budget is exhausted.

    Notes
    -----
    Validity: the Fetkovich pseudosteady-state aquifer is a finite aquifer whose
    pressure is taken as uniform at each instant. It is not valid for an infinite
    aquifer in its transient period.

    Choosing a timestep. The aquifer sub-step is unconditionally stable at any
    timestep, because ``1 - exp(-J*dt/(ct*Wi))`` is bounded in (0, 1) and the influx
    can never overshoot the maximum encroachable volume. Stability is not accuracy: the
    coupled scheme converges at second order in the timestep only once the timestep is
    short compared with the aquifer time constant ``tau = ct*Wi/J``, which is recorded
    in ``truth.aquifer_parameters``. Run with ``dt`` several times larger than ``tau``
    and the answer is still bounded and still monotone, but its error behaves like
    first order and is much larger than a refinement study on a coarse grid would
    suggest. Check ``dt/tau`` before quoting a generated history as a reference.

    This function does NOT model trapped gas behind
    the water front, which a real water-drive gas reservoir has and which changes the
    recoverable volume materially; it also does not model rock or connate-water
    expansion. With ``productivity_index_bbl_per_day_psi`` exactly zero the influx is
    the literal float ``0.0`` at every step and the result is bit-for-bit identical to
    :func:`simulate_volumetric_depletion` on the same schedule.
    """
    if aquifer is None:
        raise InvalidInputError(
            "aquifer is required; for a closed tank call simulate_volumetric_depletion "
            "instead, which states the absence of an aquifer in its name rather than in "
            "an argument value"
        )
    return _simulate(
        gas_in_place_scf=gas_in_place_scf,
        initial_pressure_psia=initial_pressure_psia,
        temperature_degr=temperature_degr,
        times_days=times_days,
        gas_rates_scf_per_day=gas_rates_scf_per_day,
        z_of_pressure=z_of_pressure,
        standard=standard,
        noise=noise,
        seed=seed,
        minimum_pressure_psia=minimum_pressure_psia,
        solver_tolerance=solver_tolerance,
        max_iterations=max_iterations,
        aquifer=aquifer,
        produced_water_fraction=produced_water_fraction,
        water_fvf_rb_per_stb=water_fvf_rb_per_stb,
        method="fetkovich_coupled_tank",
    )

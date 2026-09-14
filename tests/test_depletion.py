"""Verification of the forward depletion generators.

The four contract categories are all present: an independent oracle (Dake's published
Exercise 1.2, a closed-form pressure inversion, and Fetkovich's own iterative
substitution scheme), limiting cases (constant Z, ideal gas, zero aquifer productivity
index), invalid input, and properties (mass conservation, determinism, timestep
convergence, standard-condition invariance).

Two rules are observed throughout. No expected value here was produced by
``reservoir_lab.depletion``; every oracle is a closed form, a published number, or an
algorithm written independently in this file. And nothing in this file imports
``material_balance``: the generators are tested as generators, not by round-tripping
them through the estimator they exist to challenge.

A note on what is deliberately not tested here. A "mass is conserved at every step"
check built from the recorded series is an algebraic rearrangement of the equation the
solver drives to zero, with the standard-condition group and the reservoir temperature
cancelling on both sides. It can only report that the root finder converged, so
quoting it as a statement about the physics would be dressing a convergence result up
as a conservation result. The content that such a check does carry -- that the recorded
pore volume is the right reservoir volume for the declared gas in place -- is tested
directly instead, against the published ideal-gas molar volume and the universal gas
constant, neither of which appears anywhere in the module.
"""

from __future__ import annotations

import math
import unittest
from dataclasses import FrozenInstanceError, dataclass

from reservoir_lab.depletion import (
    NOISE_FREE,
    DepletionHistory,
    NoiseModel,
    simulate_volumetric_depletion,
    simulate_water_drive_depletion,
)
from reservoir_lab.errors import ConvergenceError, InvalidInputError
from reservoir_lab.numerics import richardson_order
from reservoir_lab.units import CUBIC_FEET_PER_BARREL, StandardConditions

try:  # The aquifer module is developed alongside this one; cross-check it when present.
    from reservoir_lab.aquifer import FetkovichAquifer
except ImportError:  # pragma: no cover - exercised only before that module lands
    FetkovichAquifer = None


SPE = StandardConditions(pressure_psia=14.696, temperature_degf=60.0, z_factor=1.0, label="SPE")
#: The Louisiana and Mississippi statutory base, used only to show that a generated
#: p/Z series does not depend on the standard-volume basis while a reservoir volume does.
LOUISIANA = StandardConditions(
    pressure_psia=15.025, temperature_degf=60.0, z_factor=1.0, label="Louisiana base"
)

#: Molar volume of an ideal gas at 14.696 psia and 60 degF, as tabulated in the
#: petroleum engineering literature (Craft and Hawkins; Ahmed; the GPSA data book).
#: Printed to five significant figures, so it carries a half-unit-in-last-place
#: uncertainty of 0.005/379.49 = 1.32e-5 relative.
PUBLISHED_MOLAR_VOLUME_SCF_PER_LBMOL = 379.49

#: Universal gas constant in field units, psia ft^3 / (lbmol degR). Printed to six
#: significant figures, so its half-ulp uncertainty is 0.00005/10.7316 = 4.66e-6
#: relative.
PUBLISHED_GAS_CONSTANT_PSIA_CUFT_PER_LBMOL_DEGR = 10.7316

#: Worst-case relative disagreement the two published constants above can produce
#: against an exactly declared psc/Tsc basis, from their printed precision alone:
#: 1.32e-5 + 4.66e-6. Fixed before any comparison was run.
PUBLISHED_CONSTANT_ROUNDING = 1.32e-5 + 4.66e-6


@dataclass(frozen=True)
class StubAquifer:
    """The four Fetkovich parameters fixed by the API contract.

    Used so that these tests exercise the generator's coupling on their own terms and
    stay runnable before ``reservoir_lab.aquifer`` exists. The dedicated cross-check
    below runs the real class when it is importable.
    """

    initial_pressure_psia: float
    water_volume_bbl: float
    total_compressibility_per_psi: float
    productivity_index_bbl_per_day_psi: float


def constant_z(value: float):
    """Return a deviation factor that does not vary with pressure."""

    def _z(pressure_psia: float) -> float:  # noqa: ARG001 - signature fixed by the generator
        return value

    return _z


def linear_z(intercept: float, slope_per_psi: float):
    """Return a declared linear Z trend; ``p/Z = t`` then has a closed-form root."""

    def _z(pressure_psia: float) -> float:
        return intercept + slope_per_psi * pressure_psia

    return _z


def uniform_schedule(total_days: float, steps: int, rate_scf_per_day: float):
    """Equal timesteps at one constant rate."""
    times = tuple(total_days * index / steps for index in range(steps + 1))
    return times, (rate_scf_per_day,) * steps


def pore_volume_from_published_constants_rcf(
    *, gas_in_place_scf: float, z_factor: float, temperature_degr: float, pressure_psia: float
) -> float:
    """Reservoir volume of ``gas_in_place_scf`` at ``pressure_psia``, from first principles.

    Deliberately built the long way round, through moles: a standard volume is turned
    into lbmol with the published ideal-gas molar volume at 14.696 psia and 60 degF,
    and the moles are turned back into a reservoir volume with ``V = Z n R T / p``.

    Neither the molar volume nor the universal gas constant appears anywhere in
    ``reservoir_lab.depletion``, which forms Bg as ``psc/(Tsc*Zsc) * Z*T/p`` and never
    needs R at all. The two routes therefore agree only if the module's
    standard-condition group and its temperature handling are both right, which is the
    content a "produced plus remaining equals the gas in place" check cannot supply.
    """
    moles_lbmol = gas_in_place_scf / PUBLISHED_MOLAR_VOLUME_SCF_PER_LBMOL
    return (
        z_factor
        * moles_lbmol
        * PUBLISHED_GAS_CONSTANT_PSIA_CUFT_PER_LBMOL_DEGR
        * temperature_degr
        / pressure_psia
    )


def coupled_history_by_scan_and_bisection(
    *,
    gas_in_place_scf: float,
    initial_pressure_psia: float,
    temperature_degr: float,
    times_days,
    gas_rates_scf_per_day,
    z_of_pressure,
    standard: StandardConditions,
    aquifer: StubAquifer,
    minimum_pressure_psia: float = 14.696,
    samples: int = 4000,
):
    """March the coupled balance with a scanned bracket and plain bisection.

    This exists to answer the one question the module's own bracketing cannot answer
    about itself: where does the step residual actually change sign, and how many
    times? The invaded fraction falls with the trial pressure, so the p/Z the balance
    demands has a pole; below that pole the tank holds more water than it has room
    for. This routine locates the pole by bisecting on the invaded fraction -- no
    closed form, so it shares nothing with the module's pole algebra -- then scans the
    physical interval above it for every sign change and bisects each one.

    Returns ``(pressures, cumulative_influx, roots_per_step)``. The last of these is
    what makes the routine an instrument rather than a second opinion: a step that
    reports anything other than one root is a step where "the" answer is not defined.
    """
    coefficient = standard.pressure_psia / (standard.temperature_rankine * standard.z_factor)
    initial_z = z_of_pressure(initial_pressure_psia)
    initial_p_over_z = initial_pressure_psia / initial_z
    pore_volume_rcf = gas_in_place_scf * coefficient * initial_z * temperature_degr / initial_pressure_psia
    ct_wi = aquifer.total_compressibility_per_psi * aquifer.water_volume_bbl
    upper = max(initial_pressure_psia, aquifer.initial_pressure_psia)

    pressures = [initial_pressure_psia]
    influx = [0.0]
    roots_per_step = []
    cumulative_gas = 0.0
    for index in range(1, len(times_days)):
        timestep = times_days[index] - times_days[index - 1]
        cumulative_gas += gas_rates_scf_per_day[index - 1] * timestep
        previous_pressure = pressures[-1]
        previous_influx = influx[-1]
        aquifer_pressure = aquifer.initial_pressure_psia - previous_influx / ct_wi
        response = ct_wi * (1.0 - math.exp(-aquifer.productivity_index_bbl_per_day_psi * timestep / ct_wi))

        def increment(pressure, _prev=previous_pressure, _paq=aquifer_pressure, _r=response):
            return _r * (_paq - 0.5 * (_prev + pressure))

        def invaded(pressure, _prev_we=previous_influx):
            return (_prev_we + increment(pressure)) * CUBIC_FEET_PER_BARREL / pore_volume_rcf

        def residual(pressure, _gp=cumulative_gas):
            demanded = initial_p_over_z * (1.0 - _gp / gas_in_place_scf) / (1.0 - invaded(pressure))
            return pressure / z_of_pressure(pressure) - demanded

        low = minimum_pressure_psia
        if invaded(low) >= 1.0:
            flooded_end, clear_end = low, upper
            for _ in range(200):
                middle = 0.5 * (flooded_end + clear_end)
                if invaded(middle) >= 1.0:
                    flooded_end = middle
                else:
                    clear_end = middle
            low = clear_end

        roots = []
        step = (upper - low) / samples
        previous_probe, previous_value = low, residual(low)
        for sample in range(1, samples + 1):
            probe = low + sample * step
            value = residual(probe)
            if previous_value == 0.0:
                roots.append(previous_probe)
            elif previous_value * value < 0.0:
                left, right = previous_probe, probe
                for _ in range(100):
                    middle = 0.5 * (left + right)
                    if residual(left) * residual(middle) <= 0.0:
                        right = middle
                    else:
                        left = middle
                roots.append(0.5 * (left + right))
            previous_probe, previous_value = probe, value
        roots_per_step.append(len(roots))
        pressure = roots[0]
        pressures.append(pressure)
        influx.append(previous_influx + increment(pressure))
    return tuple(pressures), tuple(influx), tuple(roots_per_step)


def count_sign_changes(function, *, lower: float, upper: float, samples: int) -> int:
    """Count the sign changes of ``function`` on a uniform scan of ``(lower, upper)``.

    Used to establish, independently of anything in the module, that a balance really
    does have more than one root -- so that a test asserting the generator warns about
    multiplicity is asserting something true rather than something convenient.
    """
    changes = 0
    previous = function(lower)
    step = (upper - lower) / samples
    for index in range(1, samples + 1):
        value = function(lower + index * step)
        if previous == 0.0 or previous * value < 0.0:
            changes += 1
        previous = value
    return changes


def two_point_x_intercept(x_values, y_values) -> float:
    """x-intercept of the straight line through the first and last points."""
    slope = (y_values[-1] - y_values[0]) / (x_values[-1] - x_values[0])
    return x_values[0] - y_values[0] / slope


def bisect_pressure_for_p_over_z(target_psia: float, z_of_pressure, low: float, high: float) -> float:
    """Invert ``p / Z(p) = target`` by plain bisection.

    Deliberately not ``numerics.safeguarded_newton``: this is the inversion used by the
    independent oracle below, and an oracle that shares the production root finder
    tests the caller rather than the answer.
    """
    for _ in range(200):
        middle = 0.5 * (low + high)
        if middle / z_of_pressure(middle) < target_psia:
            low = middle
        else:
            high = middle
    return 0.5 * (low + high)


def fetkovich_iterative_substitution(
    *,
    gas_in_place_scf: float,
    initial_pressure_psia: float,
    temperature_degr: float,
    times_days,
    gas_rates_scf_per_day,
    z_of_pressure,
    standard: StandardConditions,
    aquifer: StubAquifer,
):
    """Fetkovich's own trial-and-error coupling scheme, written independently here.

    Per step: guess the reservoir pressure, form the mean inner-boundary pressure of
    Eq. (8), take the influx from Eq. (6), solve the gas balance for a new pressure by
    bisection, and repeat until the pressure stops moving. Fetkovich reports the second
    trial being within 1 psi of the answer on a desk calculator; here it is iterated to
    1e-11 psi so that any disagreement with the generator is the generator's.

    Returns the pressure and cumulative influx series.
    """
    initial_z = z_of_pressure(initial_pressure_psia)
    initial_p_over_z = initial_pressure_psia / initial_z
    coefficient = standard.pressure_psia / (standard.temperature_rankine * standard.z_factor)
    hydrocarbon_pore_volume_rcf = (
        gas_in_place_scf * coefficient * initial_z * temperature_degr / initial_pressure_psia
    )
    ct_wi = aquifer.total_compressibility_per_psi * aquifer.water_volume_bbl

    pressures = [initial_pressure_psia]
    influx = [0.0]
    cumulative_gas = 0.0
    for index in range(1, len(times_days)):
        timestep = times_days[index] - times_days[index - 1]
        cumulative_gas += gas_rates_scf_per_day[index - 1] * timestep
        previous_pressure = pressures[-1]
        previous_influx = influx[-1]
        aquifer_pressure = aquifer.initial_pressure_psia - previous_influx / ct_wi
        decay = math.exp(-aquifer.productivity_index_bbl_per_day_psi * timestep / ct_wi)
        pressure = previous_pressure
        delta_influx = 0.0
        for _ in range(500):
            boundary_pressure = 0.5 * (previous_pressure + pressure)
            delta_influx = ct_wi * (1.0 - decay) * (aquifer_pressure - boundary_pressure)
            total_influx_rcf = (previous_influx + delta_influx) * CUBIC_FEET_PER_BARREL
            target = (
                initial_p_over_z
                * (1.0 - cumulative_gas / gas_in_place_scf)
                / (1.0 - total_influx_rcf / hydrocarbon_pore_volume_rcf)
            )
            updated = bisect_pressure_for_p_over_z(
                target,
                z_of_pressure,
                1.0,
                max(initial_pressure_psia, aquifer.initial_pressure_psia),
            )
            if abs(updated - pressure) < 1.0e-11:
                pressure = updated
                break
            pressure = updated
        boundary_pressure = 0.5 * (previous_pressure + pressure)
        delta_influx = ct_wi * (1.0 - decay) * (aquifer_pressure - boundary_pressure)
        pressures.append(pressure)
        influx.append(previous_influx + delta_influx)
    return tuple(pressures), tuple(influx)


class IndependentOracles(unittest.TestCase):
    """Category 1: published worked examples and independently derived closed forms."""

    def test_dake_exercise_1_2_abandonment_pressure(self):
        """Dake's Exercise 1.2: 491.04e9 scf produced from 699.70e9 scf leaves 1200 psia.

        Dake works the problem forward from a bulk volume to G = 699.70e9 scf at
        pi = 4290 psia with Zi = 0.887, then reads off the cumulative production at an
        abandonment pressure of 1200 psia where Z = 0.832, obtaining 491.04e9 scf. This
        test runs the reverse direction through the generator: produce Dake's 491.04e9
        scf and require his abandonment pressure back.

        The declared Z trend is the straight line through Dake's own two tabulated
        values, so Z at the answer is his value by construction and the only thing under
        test is the balance and its inversion. Note that this oracle is independent of
        the standard-condition basis, because psc/Tsc cancels out of p/Z entirely.
        """
        gas_in_place_scf = 699.70e9
        z_trend = linear_z(
            intercept=0.832 - 1200.0 * (0.887 - 0.832) / (4290.0 - 1200.0),
            slope_per_psi=(0.887 - 0.832) / (4290.0 - 1200.0),
        )
        history = simulate_volumetric_depletion(
            gas_in_place_scf=gas_in_place_scf,
            initial_pressure_psia=4290.0,
            temperature_degr=660.0,
            times_days=(0.0, 1000.0),
            gas_rates_scf_per_day=(491.04e9 / 1000.0,),
            z_of_pressure=z_trend,
            standard=SPE,
            noise=NOISE_FREE,
            seed=0,
        )
        self.assertAlmostEqual(history.true_z_factors[0], 0.887, places=12)
        # Dake prints five significant figures, so 0.05 psia is the meaningful window.
        self.assertAlmostEqual(history.true_pressures_psia[-1], 1200.0, delta=0.05)
        self.assertAlmostEqual(history.true_z_factors[-1], 0.832, delta=1.0e-5)

    def test_pressure_matches_closed_form_for_a_linear_z_trend(self):
        """With Z = a + b p the balance has an algebraic root; the solver must find it.

        p/Z = t with Z = a + b p rearranges to p (1 - b t) = a t, so p = a t / (1 - b t)
        with t = (pi/Zi)(1 - Gp/G). No iteration is involved in the oracle.
        """
        intercept, slope = 0.86, 2.0e-5
        gas_in_place_scf = 100.0e9
        times, rates = uniform_schedule(3650.0, 10, 100.0e9 * 0.5 / 3650.0)
        history = simulate_volumetric_depletion(
            gas_in_place_scf=gas_in_place_scf,
            initial_pressure_psia=4000.0,
            temperature_degr=660.0,
            times_days=times,
            gas_rates_scf_per_day=rates,
            z_of_pressure=linear_z(intercept, slope),
            standard=SPE,
            noise=NOISE_FREE,
            seed=0,
        )
        initial_p_over_z = 4000.0 / (intercept + slope * 4000.0)
        for index, cumulative in enumerate(history.true_cumulative_gas_scf):
            target = initial_p_over_z * (1.0 - cumulative / gas_in_place_scf)
            expected = intercept * target / (1.0 - slope * target)
            self.assertAlmostEqual(history.true_pressures_psia[index] / expected, 1.0, delta=1.0e-12)

    def test_coupled_step_matches_fetkovich_iterative_substitution(self):
        """The bracketed implicit solve must agree with Fetkovich's own scheme.

        The oracle here is a different algorithm on the same equations: successive
        substitution on the reservoir pressure with a bisection inversion, which is what
        Fetkovich describes doing on a desk calculator. Agreement to well under a
        thousandth of a psi means the generator's answer is a property of the coupled
        system rather than of the root finder chosen for it.
        """
        aquifer = StubAquifer(
            initial_pressure_psia=5000.0,
            water_volume_bbl=3.0e8,
            total_compressibility_per_psi=9.0e-6,
            productivity_index_bbl_per_day_psi=400.0,
        )
        times, rates = uniform_schedule(3650.0, 10, 100.0e9 * 0.5 / 3650.0)
        z_trend = linear_z(0.86, 2.0e-5)
        history = simulate_water_drive_depletion(
            gas_in_place_scf=100.0e9,
            initial_pressure_psia=5000.0,
            temperature_degr=660.0,
            times_days=times,
            gas_rates_scf_per_day=rates,
            z_of_pressure=z_trend,
            standard=SPE,
            aquifer=aquifer,
            noise=NOISE_FREE,
            seed=0,
        )
        pressures, influx = fetkovich_iterative_substitution(
            gas_in_place_scf=100.0e9,
            initial_pressure_psia=5000.0,
            temperature_degr=660.0,
            times_days=times,
            gas_rates_scf_per_day=rates,
            z_of_pressure=z_trend,
            standard=SPE,
            aquifer=aquifer,
        )
        for index in range(len(times)):
            self.assertAlmostEqual(history.true_pressures_psia[index], pressures[index], delta=1.0e-6)
            self.assertAlmostEqual(history.water_influx_bbl[index], influx[index], delta=1.0e-3)

    def test_pore_volume_matches_the_published_molar_volume_basis(self):
        """The recorded pore volume must agree with a moles-and-R calculation.

        ``reservoir_lab.depletion`` never uses the universal gas constant: it forms Bg
        as ``psc/(Tsc*Zsc) * Z*T/p``, in which R has already cancelled. Going the long
        way round instead -- scf to lbmol through the published ideal-gas molar volume
        at 14.696 psia and 60 degF, lbmol to reservoir cubic feet through ``V = ZnRT/p``
        -- exercises the same physical statement through two constants the module has
        never seen.

        The tolerance is set by those two constants' printed precision and nothing
        else: 1.32e-5 relative for the five-figure molar volume plus 4.66e-6 for the
        six-figure gas constant. The declared basis 14.696 psia and 519.67 degR is
        exact by convention, so it contributes no uncertainty. A disagreement larger
        than that sum would be a real error in the standard-condition group or in the
        temperature handling.
        """
        initial_pressure_psia = 4290.0
        temperature_degr = 660.0
        gas_in_place_scf = 699.70e9
        z_trend = linear_z(0.86, 2.0e-5)
        history = simulate_volumetric_depletion(
            gas_in_place_scf=gas_in_place_scf,
            initial_pressure_psia=initial_pressure_psia,
            temperature_degr=temperature_degr,
            times_days=(0.0, 365.0),
            gas_rates_scf_per_day=(1.0e8,),
            z_of_pressure=z_trend,
            standard=SPE,
            noise=NOISE_FREE,
            seed=0,
        )
        expected_rcf = pore_volume_from_published_constants_rcf(
            gas_in_place_scf=gas_in_place_scf,
            z_factor=z_trend(initial_pressure_psia),
            temperature_degr=temperature_degr,
            pressure_psia=initial_pressure_psia,
        )
        self.assertAlmostEqual(
            history.truth.hydrocarbon_pore_volume_rcf / expected_rcf,
            1.0,
            delta=PUBLISHED_CONSTANT_ROUNDING,
        )
        # The same statement one gas volume at a time, through the public accessor,
        # at a pressure the history actually visited.
        pressure = history.true_pressures_psia[-1]
        z_factor = history.true_z_factors[-1]
        expected_fvf = pore_volume_from_published_constants_rcf(
            gas_in_place_scf=1.0,
            z_factor=z_factor,
            temperature_degr=temperature_degr,
            pressure_psia=pressure,
        )
        self.assertAlmostEqual(
            history.truth.gas_fvf_rcf_per_scf(pressure, z_factor) / expected_fvf,
            1.0,
            delta=PUBLISHED_CONSTANT_ROUNDING,
        )

    def test_a_strong_water_drive_is_solved_rather_than_refused(self):
        """Regression: bracket the pressure search at the pole, not at the pressure floor.

        The p/Z the balance demands has a pole at the pressure where the invaded volume
        equals the pore volume. For any aquifer strong enough to be worth studying that
        pole lies well above ``minimum_pressure_psia``, so a guard that evaluates the
        invaded fraction at the pressure floor reads back a number greater than one and
        refuses the step -- while the step itself has a single, entirely ordinary root
        a few percent invaded. This aquifer is such a case: it was refused outright at
        the first step, with a diagnostic quoting an invaded fraction of 1.0497 that
        occurs nowhere in the solution.

        The oracle brackets and solves the same steps by scanning for sign changes and
        bisecting, sharing none of the module's bracketing. The 1e-6 psia window is the
        sum of the two stopping rules, decided from them rather than from the outcome:
        the module stops at a bracket width of ``solver_tolerance * max(1, p)``, which
        is 5e-9 psia here, and the oracle's bisection runs to the spacing of double
        precision. A thousandfold margin on the larger of the two.
        """
        aquifer = StubAquifer(
            initial_pressure_psia=5000.0,
            water_volume_bbl=3.0e9,
            total_compressibility_per_psi=9.0e-6,
            productivity_index_bbl_per_day_psi=400.0,
        )
        times, rates = uniform_schedule(3650.0, 10, 100.0e9 * 0.5 / 3650.0)
        z_trend = linear_z(0.86, 2.0e-5)
        arguments = dict(
            gas_in_place_scf=100.0e9,
            initial_pressure_psia=5000.0,
            temperature_degr=660.0,
            times_days=times,
            gas_rates_scf_per_day=rates,
            z_of_pressure=z_trend,
            standard=SPE,
            aquifer=aquifer,
        )
        history = simulate_water_drive_depletion(noise=NOISE_FREE, seed=0, **arguments)
        pressures, influx, roots_per_step = coupled_history_by_scan_and_bisection(**arguments)

        self.assertEqual(set(roots_per_step), {1})
        self.assertEqual(history.n_points, len(times))
        for index in range(len(times)):
            self.assertAlmostEqual(history.true_pressures_psia[index], pressures[index], delta=1.0e-6)
            self.assertAlmostEqual(history.water_influx_bbl[index], influx[index], delta=1.0e-2)

        pore_volume_rcf = history.truth.hydrocarbon_pore_volume_rcf
        invaded = [volume * CUBIC_FEET_PER_BARREL / pore_volume_rcf for volume in history.water_influx_bbl]
        self.assertLess(max(invaded), 0.5)
        for index in range(1, len(invaded)):
            self.assertGreater(invaded[index], invaded[index - 1])

        # The condition the defective guard tested: the invaded fraction extrapolated
        # down to the pressure floor, at the very first step, is above one. That is
        # what made this a false rejection, and it has to stay above one for this test
        # to still be testing the thing it was written for.
        ct_wi = aquifer.total_compressibility_per_psi * aquifer.water_volume_bbl
        timestep = times[1] - times[0]
        response = ct_wi * (1.0 - math.exp(-aquifer.productivity_index_bbl_per_day_psi * timestep / ct_wi))
        floor_psia = 14.696
        invaded_at_floor = (
            response
            * (aquifer.initial_pressure_psia - 0.5 * (5000.0 + floor_psia))
            * CUBIC_FEET_PER_BARREL
            / pore_volume_rcf
        )
        self.assertGreater(invaded_at_floor, 1.0)
        self.assertLess(invaded[1], 0.05)


class LimitingCases(unittest.TestCase):
    """Category 2: cases whose answer is known analytically."""

    def test_constant_z_gives_a_straight_p_over_z_line(self):
        """Zero noise and constant Z: p/Z against Gp is the analytic line.

        The volumetric balance is p/Z = (pi/Zi)(1 - Gp/G) exactly, for any Z behaviour.
        With Z constant the warm start ``required * Z`` is already the root, so the
        solver has nothing to do beyond confirming it.

        What the test may assert about that depends on the value of Z, and it is worth
        being precise about why. The warm start is exact only if ``(t*Z)/Z == t`` in
        binary floating point. That holds for Z = 1 and, as it happens, for Z = 0.9; it
        does not hold in general, and at Z = 0.87 or Z = 1.13 the first residual is a
        few ulps off zero and the solver bisects. So bit-for-bit equality is asserted
        only at Z = 1, where it is a property of the arithmetic rather than a lucky
        draw, and every other constant Z is held to the solver's own declared stopping
        rule: a returned bracket of width ``solver_tolerance * max(1, p)``, which maps
        to an error in p/Z of at most ``solver_tolerance * p / Z``. The factor of two
        covers the final midpoint and the division.
        """
        gas_in_place_scf = 100.0e9
        times, rates = uniform_schedule(3650.0, 10, 100.0e9 * 0.5 / 3650.0)
        shared = dict(
            gas_in_place_scf=gas_in_place_scf,
            initial_pressure_psia=4000.0,
            temperature_degr=660.0,
            times_days=times,
            gas_rates_scf_per_day=rates,
            standard=SPE,
            noise=NOISE_FREE,
            seed=0,
        )
        history = simulate_volumetric_depletion(z_of_pressure=constant_z(1.0), **shared)
        initial_p_over_z = history.truth.initial_p_over_z_psia
        observed = history.p_over_z_psia()
        for index, cumulative in enumerate(history.cumulative_gas_scf):
            expected = initial_p_over_z * (1.0 - cumulative / gas_in_place_scf)
            self.assertEqual(observed[index], expected)
        self.assertEqual(history.max_abs_residual_p_over_z_psia, 0.0)
        intercept = two_point_x_intercept(history.cumulative_gas_scf, observed)
        self.assertAlmostEqual(intercept / gas_in_place_scf, 1.0, delta=1.0e-12)

        for z_value in (0.87, 0.9, 1.13):
            with self.subTest(z_factor=z_value):
                run = simulate_volumetric_depletion(z_of_pressure=constant_z(z_value), **shared)
                line = run.p_over_z_psia()
                budget = 2.0 * run.solver_tolerance * run.truth.initial_pressure_psia / z_value
                for index, cumulative in enumerate(run.cumulative_gas_scf):
                    expected = run.truth.initial_p_over_z_psia * (1.0 - cumulative / gas_in_place_scf)
                    self.assertLessEqual(abs(line[index] - expected), budget)
                self.assertLessEqual(run.max_abs_residual_p_over_z_psia, budget)

    def test_ideal_gas_pressure_is_linear_in_cumulative_production(self):
        """With Z = 1 the pressure itself, not only p/Z, falls linearly with Gp."""
        gas_in_place_scf = 80.0e9
        times, rates = uniform_schedule(1000.0, 8, 80.0e9 * 0.4 / 1000.0)
        history = simulate_volumetric_depletion(
            gas_in_place_scf=gas_in_place_scf,
            initial_pressure_psia=3000.0,
            temperature_degr=700.0,
            times_days=times,
            gas_rates_scf_per_day=rates,
            z_of_pressure=constant_z(1.0),
            standard=SPE,
            noise=NOISE_FREE,
            seed=0,
        )
        for pressure, cumulative in zip(
            history.true_pressures_psia, history.true_cumulative_gas_scf, strict=True
        ):
            self.assertEqual(pressure, 3000.0 * (1.0 - cumulative / gas_in_place_scf))

    def test_zero_productivity_index_reduces_to_the_volumetric_generator(self):
        """The single most important test in the module.

        A Fetkovich aquifer with J = 0 delivers no water, so the coupled generator must
        return the closed-tank answer. The requirement is bit-for-bit equality, not
        approximate agreement: the influx enters the balance as the literal float 0.0
        and the two code paths then perform identical arithmetic. Anything weaker would
        leave room for a coupling term that is merely small rather than absent.
        """
        aquifer = StubAquifer(
            initial_pressure_psia=4000.0,
            water_volume_bbl=5.0e8,
            total_compressibility_per_psi=9.0e-6,
            productivity_index_bbl_per_day_psi=0.0,
        )
        times, rates = uniform_schedule(3650.0, 10, 100.0e9 * 0.5 / 3650.0)
        shared = dict(
            gas_in_place_scf=100.0e9,
            initial_pressure_psia=4000.0,
            temperature_degr=660.0,
            times_days=times,
            gas_rates_scf_per_day=rates,
            z_of_pressure=linear_z(0.86, 2.0e-5),
            standard=SPE,
            noise=NoiseModel(pressure_sigma_psia=5.0, z_relative_sigma=1.0e-3, label="gauge"),
            seed=20240913,
        )
        volumetric = simulate_volumetric_depletion(**shared)
        coupled = simulate_water_drive_depletion(aquifer=aquifer, **shared)

        self.assertEqual(coupled.true_pressures_psia, volumetric.true_pressures_psia)
        self.assertEqual(coupled.true_z_factors, volumetric.true_z_factors)
        self.assertEqual(coupled.true_cumulative_gas_scf, volumetric.true_cumulative_gas_scf)
        self.assertEqual(coupled.pressures_psia, volumetric.pressures_psia)
        self.assertEqual(coupled.z_factors, volumetric.z_factors)
        self.assertEqual(coupled.cumulative_gas_scf, volumetric.cumulative_gas_scf)
        self.assertEqual(coupled.residual_p_over_z_psia, volumetric.residual_p_over_z_psia)
        self.assertEqual(coupled.water_influx_bbl, volumetric.water_influx_bbl)
        self.assertEqual(coupled.cumulative_water_stb, volumetric.cumulative_water_stb)
        self.assertEqual(coupled.water_influx_bbl, (0.0,) * len(times))

    def test_a_complete_water_drive_invades_the_pore_volume_in_step_with_recovery(self):
        """The opposite limit from a closed tank, and it has a closed form too.

        Let the aquifer be large enough and fast enough that its own pressure barely
        moves. The reservoir is then held at its initial pressure, p/Z stays at
        (pi/Zi), and the balance collapses to

            (pi/Zi) = (pi/Zi)(1 - Gp/G)/(1 - We_net/HCPV)   so   We_net/HCPV = Gp/G

        Every standard cubic foot produced is replaced barrel for barrel by water. It
        is the pathological case for a p/Z plot -- the line is flat, its x-intercept is
        at infinity, and no amount of production reveals G -- which is exactly why the
        generator has to be able to produce it rather than refuse it.

        The aquifer here is finite, so the limit is approached rather than attained,
        and the tolerance says by how much: its pressure falls by We/(ct*Wi), at most
        HCPV = 7.5e7 bbl over 9.0e6 bbl/psi, i.e. 8.3 psia out of 4000, so 2.1e-3
        relative. That number comes from the aquifer's storage and the pore volume,
        both fixed before the run.
        """
        gas_in_place_scf = 100.0e9
        initial_pressure_psia = 4000.0
        times, rates = uniform_schedule(3650.0, 10, gas_in_place_scf * 0.95 / 3650.0)
        aquifer = StubAquifer(
            initial_pressure_psia=initial_pressure_psia,
            water_volume_bbl=1.0e12,
            total_compressibility_per_psi=9.0e-6,
            productivity_index_bbl_per_day_psi=1.0e9,
        )
        history = simulate_water_drive_depletion(
            gas_in_place_scf=gas_in_place_scf,
            initial_pressure_psia=initial_pressure_psia,
            temperature_degr=660.0,
            times_days=times,
            gas_rates_scf_per_day=rates,
            z_of_pressure=constant_z(0.9),
            standard=SPE,
            aquifer=aquifer,
            noise=NOISE_FREE,
            seed=0,
        )
        pore_volume_bbl = history.truth.hydrocarbon_pore_volume_rcf / CUBIC_FEET_PER_BARREL
        storage_bbl_per_psi = aquifer.water_volume_bbl * aquifer.total_compressibility_per_psi
        budget = pore_volume_bbl / storage_bbl_per_psi / initial_pressure_psia
        self.assertLess(budget, 3.0e-3)
        for index in range(history.n_points):
            recovery = history.true_cumulative_gas_scf[index] / gas_in_place_scf
            invaded = history.water_influx_bbl[index] / pore_volume_bbl
            self.assertAlmostEqual(
                history.true_pressures_psia[index] / initial_pressure_psia, 1.0, delta=budget
            )
            self.assertAlmostEqual(invaded, recovery, delta=budget)
        # Nearly all of the pore volume ends up water, which is the whole point: this
        # is the regime a straight-line p/Z reading is blind to.
        self.assertGreater(history.water_influx_bbl[-1] / pore_volume_bbl, 0.9)
        self.assertEqual(history.warnings, ())

    def test_a_vanishing_aquifer_volume_approaches_the_volumetric_answer(self):
        """Shrinking the aquifer, not its productivity index, must also close the gap.

        The asymptotic statement is sharper than "the gap gets small", so that is what
        is asserted. At these volumes ``J*dt/(ct*Wi)`` is enormous, the step response
        saturates at ``ct*Wi``, and the influx is therefore exactly proportional to the
        aquifer volume. The pressure gap is linear in the influx to first order, so
        shrinking the volume by a decade must shrink the gap by a decade.

        The 1 percent window on each decade ratio comes from the size of the neglected
        second-order term: the gap at the coarsest volume is 4.6 psia against a
        pressure of about 4000 psia, so the leading correction to linearity is of
        relative size 1.1e-3. One percent is roughly ten times that, and it was fixed
        from that estimate rather than from the ratios the run produced.
        """
        times, rates = uniform_schedule(3650.0, 10, 100.0e9 * 0.5 / 3650.0)
        shared = dict(
            gas_in_place_scf=100.0e9,
            initial_pressure_psia=4000.0,
            temperature_degr=660.0,
            times_days=times,
            gas_rates_scf_per_day=rates,
            z_of_pressure=linear_z(0.86, 2.0e-5),
            standard=SPE,
            noise=NOISE_FREE,
            seed=0,
        )
        volumetric = simulate_volumetric_depletion(**shared)
        gaps = []
        for water_volume_bbl in (1.0e7, 1.0e5, 1.0e3):
            coupled = simulate_water_drive_depletion(
                aquifer=StubAquifer(4000.0, water_volume_bbl, 9.0e-6, 400.0), **shared
            )
            gaps.append(abs(coupled.true_pressures_psia[-1] - volumetric.true_pressures_psia[-1]))
        self.assertGreater(gaps[0], gaps[1])
        self.assertGreater(gaps[1], gaps[2])
        # The premise of the 1 percent window: the largest gap is a 1e-3 perturbation
        # on the initial pressure, so the neglected second-order term really is small.
        self.assertLess(gaps[0] / volumetric.truth.initial_pressure_psia, 2.0e-3)
        for index in range(1, len(gaps)):
            self.assertAlmostEqual(gaps[index - 1] / gaps[index] / 100.0, 1.0, delta=0.01)


class InvalidInput(unittest.TestCase):
    """Category 3: every documented raise is exercised."""

    def setUp(self):
        times, rates = uniform_schedule(3650.0, 10, 100.0e9 * 0.5 / 3650.0)
        self.valid = dict(
            gas_in_place_scf=100.0e9,
            initial_pressure_psia=4000.0,
            temperature_degr=660.0,
            times_days=times,
            gas_rates_scf_per_day=rates,
            z_of_pressure=constant_z(0.9),
            standard=SPE,
            noise=NOISE_FREE,
            seed=0,
        )

    def run_with(self, **overrides):
        arguments = dict(self.valid)
        arguments.update(overrides)
        return simulate_volumetric_depletion(**arguments)

    def test_non_positive_gas_in_place(self):
        with self.assertRaises(InvalidInputError):
            self.run_with(gas_in_place_scf=0.0)

    def test_non_finite_initial_pressure(self):
        with self.assertRaises(InvalidInputError):
            self.run_with(initial_pressure_psia=float("nan"))

    def test_times_must_strictly_increase(self):
        with self.assertRaises(InvalidInputError):
            self.run_with(times_days=(0.0, 100.0, 100.0), gas_rates_scf_per_day=(1.0, 1.0))

    def test_times_are_not_sorted_for_the_caller(self):
        with self.assertRaises(InvalidInputError):
            self.run_with(times_days=(0.0, 200.0, 100.0), gas_rates_scf_per_day=(1.0, 1.0))

    def test_one_rate_per_interval(self):
        with self.assertRaises(InvalidInputError):
            self.run_with(times_days=(0.0, 100.0, 200.0), gas_rates_scf_per_day=(1.0, 1.0, 1.0))

    def test_negative_rate(self):
        with self.assertRaises(InvalidInputError):
            self.run_with(times_days=(0.0, 100.0), gas_rates_scf_per_day=(-1.0,))

    def test_a_single_observation_is_not_a_history(self):
        with self.assertRaises(InvalidInputError):
            self.run_with(times_days=(0.0,), gas_rates_scf_per_day=())

    def test_schedule_may_not_produce_the_whole_tank(self):
        with self.assertRaises(InvalidInputError):
            self.run_with(times_days=(0.0, 100.0), gas_rates_scf_per_day=(2.0e9,))

    def test_schedule_may_not_fall_below_the_pressure_floor(self):
        with self.assertRaises(InvalidInputError):
            self.run_with(
                times_days=(0.0, 100.0),
                gas_rates_scf_per_day=(0.999e9,),
                minimum_pressure_psia=500.0,
            )

    def test_pressure_floor_must_lie_below_the_initial_pressure(self):
        with self.assertRaises(InvalidInputError):
            self.run_with(minimum_pressure_psia=4000.0)

    def test_z_callable_returning_a_non_positive_value(self):
        with self.assertRaises(InvalidInputError):
            self.run_with(z_of_pressure=constant_z(0.0))

    def test_z_callable_returning_a_non_finite_value(self):
        with self.assertRaises(InvalidInputError):
            self.run_with(z_of_pressure=constant_z(float("inf")))

    def test_z_callable_that_raises_is_reported_as_invalid_input(self):
        def broken(pressure_psia: float) -> float:  # noqa: ARG001 - fixed signature
            raise KeyError("no table entry")

        with self.assertRaises(InvalidInputError):
            self.run_with(z_of_pressure=broken)

    def test_z_must_be_callable(self):
        with self.assertRaises(InvalidInputError):
            self.run_with(z_of_pressure=0.9)

    def test_noise_must_be_a_noise_model(self):
        with self.assertRaises(InvalidInputError):
            self.run_with(noise=None)

    def test_seed_must_be_an_integer(self):
        with self.assertRaises(InvalidInputError):
            self.run_with(seed=1.5)

    def test_seed_may_not_be_a_bool(self):
        with self.assertRaises(InvalidInputError):
            self.run_with(seed=True)

    def test_standard_conditions_are_not_optional(self):
        with self.assertRaises(InvalidInputError):
            self.run_with(standard=14.696)

    def test_negative_noise_sigma(self):
        with self.assertRaises(InvalidInputError):
            NoiseModel(pressure_sigma_psia=-1.0)

    def test_iteration_budget_is_reported_as_convergence_failure(self):
        """A budget too small to converge raises rather than returning the last iterate."""

        def wiggly(pressure_psia: float) -> float:
            return 0.9 + 0.05 * math.sin(pressure_psia / 100.0)

        with self.assertRaises(ConvergenceError):
            self.run_with(z_of_pressure=wiggly, max_iterations=1)

    def test_water_drive_requires_an_aquifer(self):
        with self.assertRaises(InvalidInputError):
            simulate_water_drive_depletion(aquifer=None, **self.valid)

    def test_aquifer_must_expose_the_four_fetkovich_parameters(self):
        class Incomplete:
            initial_pressure_psia = 4000.0
            water_volume_bbl = 1.0e8

        with self.assertRaises(InvalidInputError):
            simulate_water_drive_depletion(aquifer=Incomplete(), **self.valid)

    def test_negative_productivity_index(self):
        with self.assertRaises(InvalidInputError):
            simulate_water_drive_depletion(aquifer=StubAquifer(4000.0, 1.0e8, 9.0e-6, -1.0), **self.valid)

    def test_non_positive_aquifer_volume(self):
        with self.assertRaises(InvalidInputError):
            simulate_water_drive_depletion(aquifer=StubAquifer(4000.0, 0.0, 9.0e-6, 100.0), **self.valid)

    def test_produced_water_fraction_outside_the_unit_interval(self):
        with self.assertRaises(InvalidInputError):
            simulate_water_drive_depletion(
                aquifer=StubAquifer(4000.0, 1.0e8, 9.0e-6, 100.0),
                produced_water_fraction=1.5,
                **self.valid,
            )

    def test_an_aquifer_that_would_fill_the_pore_volume(self):
        """Encroachment reaching the pore volume is refused, not clamped.

        The case has to be one that genuinely has no solution, and "no solution" means
        the invaded volume exceeds the pore volume at every pressure the reservoir can
        reach -- not merely at the pressure floor, which is where an earlier version of
        this guard looked and which made it reject well-posed strong-water-drive runs.

        Here the aquifer sits at 8000 psia against a 4000 psia gas tank with 7.5e7 bbl
        of pore volume, and its step response is 9.0e6 bbl/psi. Even at 8000 psia, the
        highest pressure the reservoir can reach, the first step encroaches
        9.0e6 * 0.5 * (8000 - 4000) = 1.8e10 bbl, some 240 times the pore volume. The
        tank would be full of water within the first step at any pressure, so there is
        nothing for the generator to return.
        """
        with self.assertRaises(InvalidInputError) as caught:
            simulate_water_drive_depletion(aquifer=StubAquifer(8000.0, 1.0e12, 9.0e-6, 1.0e9), **self.valid)
        message = str(caught.exception)
        self.assertIn("hydrocarbon pore volume", message)
        # The diagnostic must quote the invaded fraction at a pressure the reservoir
        # can actually reach, which is what makes it checkable by the caller.
        self.assertIn("8000.0 psia", message)
        self.assertIn("240.", message)

    def test_a_strong_aquifer_short_of_the_pore_volume_is_not_refused(self):
        """The companion to the test above: strong is not the same as unsolvable.

        Same fixture, same schedule, a productivity index and volume large enough that
        the invaded fraction extrapolated to the pressure floor is far above one, but
        small enough that the step still has a root with the tank mostly gas. This must
        run to completion. It is here in the invalid-input class on purpose: the point
        is which inputs are refused, and this one must not be.
        """
        history = simulate_water_drive_depletion(
            aquifer=StubAquifer(4000.0, 1.0e10, 9.0e-6, 1.0e6), **self.valid
        )
        self.assertEqual(history.n_points, len(self.valid["times_days"]))
        invaded = [
            volume * CUBIC_FEET_PER_BARREL / history.truth.hydrocarbon_pore_volume_rcf
            for volume in history.water_influx_bbl
        ]
        self.assertLess(max(invaded), 1.0)

    def test_an_aquifer_below_the_initial_reservoir_pressure_is_rejected(self):
        """An aquifer charged below the gas tank is refused, and by name.

        Fetkovich's aquifer is in equilibrium with the reservoir at time zero, so its
        pressure at a common datum is at least the reservoir's. Accepting a lower one
        made the first step an efflux and produced a negative cumulative water
        production -- a quantity that cannot be negative, offered to a consumer as a
        reported observation.
        """
        with self.assertRaises(InvalidInputError) as caught:
            simulate_water_drive_depletion(
                aquifer=StubAquifer(3000.0, 3.0e8, 9.0e-6, 400.0),
                produced_water_fraction=0.3,
                water_fvf_rb_per_stb=1.05,
                **self.valid,
            )
        self.assertIn("aquifer.initial_pressure_psia", str(caught.exception))

    def test_a_falling_cumulative_water_production_is_refused(self):
        """An efflux step may not be allowed to un-produce water at the surface.

        The influx itself is free to change sign: an aquifer that has charged the
        reservoir above its own falling average pressure takes water back, and that is
        real. What is not real is the consequence for the reported series, because the
        declared produced-water fraction is applied to the *incremental* influx, so an
        efflux step reduces a cumulative production. Here the aquifer is charged to
        6000 psia against a 4000 psia tank and has only 9e7 bbl/psi of storage, so its
        pressure crashes below the reservoir it has just charged and the second step
        runs backwards.

        With ``produced_water_fraction`` at zero the same run is admissible, and the
        test asserts that too: the refusal has to be attributable to the bookkeeping
        fraction rather than to the influx reversing.
        """
        overpressured = StubAquifer(6000.0, 1.0e7, 9.0e-6, 400.0)
        arguments = dict(self.valid)
        # A token offtake, so the pressure path is set by the aquifer rather than by
        # the schedule and the reversal is visible.
        arguments["gas_rates_scf_per_day"] = (1.0,) * len(self.valid["gas_rates_scf_per_day"])
        with self.assertRaises(InvalidInputError) as caught:
            simulate_water_drive_depletion(
                aquifer=overpressured,
                produced_water_fraction=0.3,
                water_fvf_rb_per_stb=1.05,
                **arguments,
            )
        message = str(caught.exception)
        self.assertIn("produced_water_fraction", message)
        self.assertIn("cannot decrease", message)

        history = simulate_water_drive_depletion(aquifer=overpressured, **arguments)
        self.assertEqual(history.cumulative_water_stb, (0.0,) * history.n_points)
        increments = [
            history.water_influx_bbl[index] - history.water_influx_bbl[index - 1]
            for index in range(1, history.n_points)
        ]
        self.assertLess(min(increments), 0.0)


class PropertiesAndInvariants(unittest.TestCase):
    """Category 4: conservation, determinism, convergence and scaling."""

    def setUp(self):
        self.times, self.rates = uniform_schedule(3650.0, 10, 100.0e9 * 0.5 / 3650.0)
        self.shared = dict(
            gas_in_place_scf=100.0e9,
            initial_pressure_psia=5000.0,
            temperature_degr=660.0,
            times_days=self.times,
            gas_rates_scf_per_day=self.rates,
            z_of_pressure=linear_z(0.86, 2.0e-5),
            standard=SPE,
            noise=NOISE_FREE,
            seed=7,
        )
        self.aquifer = StubAquifer(
            initial_pressure_psia=5000.0,
            water_volume_bbl=3.0e8,
            total_compressibility_per_psi=9.0e-6,
            productivity_index_bbl_per_day_psi=400.0,
        )

    def test_produced_water_and_influx_are_bridged_by_the_water_formation_volume_factor(self):
        """The two water series carry different units, and the field names must say so.

        ``water_influx_bbl`` is a reservoir volume and ``cumulative_water_stb`` is the
        surface volume produced from it; they are the same water measured two ways and
        are related by the declared bookkeeping fraction and Bw. Both once ended in
        ``_bbl``, which made that relation invisible at a call site and invited a
        consumer to subtract one from the other.

        The relation is exact arithmetic, not a converged quantity, so the tolerance is
        round-off in a single multiply-divide chain: four operations on values of order
        1e6, i.e. a few ulps, and 1e-15 relative is a comfortable bound on that.
        """
        fraction = 0.2
        water_fvf = 1.05
        history = simulate_water_drive_depletion(
            aquifer=self.aquifer,
            produced_water_fraction=fraction,
            water_fvf_rb_per_stb=water_fvf,
            **self.shared,
        )
        self.assertEqual(history.truth.water_fvf_rb_per_stb, water_fvf)
        self.assertGreater(history.cumulative_water_stb[-1], 0.0)
        for index in range(history.n_points):
            expected_stb = fraction * history.water_influx_bbl[index] / water_fvf
            if expected_stb == 0.0:
                self.assertEqual(history.cumulative_water_stb[index], 0.0)
            else:
                self.assertAlmostEqual(history.cumulative_water_stb[index] / expected_stb, 1.0, delta=1.0e-15)
        # A surface barrel is worth more than a reservoir barrel here, so the produced
        # surface volume is strictly below the fraction of the reservoir volume it came
        # from. Getting Bw the wrong way up would reverse that.
        self.assertLess(history.cumulative_water_stb[-1], fraction * history.water_influx_bbl[-1])
        # Water lifted to the surface is pore volume handed back to the gas, so at the
        # same schedule and the same aquifer the reservoir pressure is lower at every
        # step than it is when every encroached barrel stays down there. That is a
        # statement about which way the produced volume is subtracted, and it is the
        # only thing that distinguishes the right sign from the wrong one: both give a
        # perfectly self-consistent history.
        retained = simulate_water_drive_depletion(aquifer=self.aquifer, **self.shared)
        for index in range(1, history.n_points):
            self.assertLess(history.true_pressures_psia[index], retained.true_pressures_psia[index])
        # And the reservoir volume the balance actually removes from the pore space is
        # the influx less the produced volume converted back to reservoir barrels.
        for index in range(1, history.n_points):
            net_bbl = history.water_influx_bbl[index] - water_fvf * history.cumulative_water_stb[index]
            self.assertGreater(net_bbl, 0.0)
            self.assertLess(net_bbl, history.water_influx_bbl[index])

    def test_determinism_under_a_fixed_seed(self):
        """Two calls with equal arguments return equal results, bit for bit."""
        noisy = dict(self.shared)
        noisy["noise"] = NoiseModel(
            pressure_sigma_psia=15.0,
            pressure_bias_psia=-4.0,
            z_relative_sigma=2.0e-3,
            cumulative_gas_relative_sigma=1.0e-3,
            label="gauge and allocation",
        )
        first = simulate_water_drive_depletion(aquifer=self.aquifer, **noisy)
        second = simulate_water_drive_depletion(aquifer=self.aquifer, **noisy)
        self.assertEqual(first.pressures_psia, second.pressures_psia)
        self.assertEqual(first.z_factors, second.z_factors)
        self.assertEqual(first.cumulative_gas_scf, second.cumulative_gas_scf)
        self.assertEqual(first.water_influx_bbl, second.water_influx_bbl)
        self.assertEqual(first.residual_p_over_z_psia, second.residual_p_over_z_psia)

        noisy["seed"] = 8
        different = simulate_water_drive_depletion(aquifer=self.aquifer, **noisy)
        self.assertNotEqual(different.pressures_psia, first.pressures_psia)
        # A different seed changes the observations only; the physics is untouched.
        self.assertEqual(different.true_pressures_psia, first.true_pressures_psia)

    def test_noise_does_not_feed_back_into_the_balance(self):
        """The true series must not depend on the noise model at all."""
        clean = simulate_volumetric_depletion(**self.shared)
        noisy_arguments = dict(self.shared)
        noisy_arguments["noise"] = NoiseModel(pressure_sigma_psia=25.0, label="noisy")
        noisy = simulate_volumetric_depletion(**noisy_arguments)
        self.assertEqual(noisy.true_pressures_psia, clean.true_pressures_psia)
        self.assertNotEqual(noisy.pressures_psia, clean.pressures_psia)

    def test_zero_noise_makes_observed_and_true_series_identical(self):
        history = simulate_volumetric_depletion(**self.shared)
        self.assertTrue(history.truth.noise.is_noise_free())
        self.assertEqual(history.pressures_psia, history.true_pressures_psia)
        self.assertEqual(history.z_factors, history.true_z_factors)
        self.assertEqual(history.cumulative_gas_scf, history.true_cumulative_gas_scf)

    def test_timestep_refinement_converges_at_second_order(self):
        """Refining the coupled timestep must converge at the order the scheme has.

        Fetkovich's recursion is exact for a step-constant inner-boundary pressure, so
        the only truncation error comes from representing a falling reservoir pressure
        across the step by the Eq. (8) mean of its two end values. That is a midpoint
        rule against the aquifer's exponential memory kernel, and it is second order
        once the timestep is short compared with the aquifer time constant
        tau = ct*Wi/J. This aquifer is deliberately given tau = 135 days so that the
        grids used here sit in that regime; see the companion test for what happens
        when they do not. The assertion is on the demonstrated order, not on any single
        grid's value.

        The root-finder tolerance is tightened for this test so that the quantity being
        refined is the scheme's truncation error and not the solver's stopping rule.
        """
        aquifer = StubAquifer(
            initial_pressure_psia=5000.0,
            water_volume_bbl=3.0e8,
            total_compressibility_per_psi=9.0e-6,
            productivity_index_bbl_per_day_psi=20.0,
        )
        finals = []
        for steps in (40, 80, 160, 320):
            times, rates = uniform_schedule(3650.0, steps, 100.0e9 * 0.5 / 3650.0)
            arguments = dict(self.shared)
            arguments["times_days"] = times
            arguments["gas_rates_scf_per_day"] = rates
            arguments["solver_tolerance"] = 1.0e-14
            history = simulate_water_drive_depletion(aquifer=aquifer, **arguments)
            finals.append(history.true_pressures_psia[-1])
            self.assertLess(history.max_abs_residual_p_over_z_psia, 1.0e-6)
        differences = [abs(finals[i] - finals[i - 1]) for i in range(1, len(finals))]
        for index in range(1, len(differences)):
            self.assertLess(differences[index], differences[index - 1])
        for index in range(2, len(finals)):
            order = richardson_order(finals[index - 2], finals[index - 1], finals[index])
            self.assertGreater(order, 1.8)
            self.assertLess(order, 2.2)

    def test_the_recorded_time_constant_flags_an_under_resolved_timestep(self):
        """A timestep far longer than tau converges more slowly, and tau is recorded.

        This is the honest counterpart to the order test above. The scheme stays stable
        and monotone at any timestep, so nothing announces that a coarse run is poorly
        resolved; the recorded aquifer time constant is what lets a caller notice.
        """
        aquifer = StubAquifer(
            initial_pressure_psia=5000.0,
            water_volume_bbl=3.0e8,
            total_compressibility_per_psi=9.0e-6,
            productivity_index_bbl_per_day_psi=400.0,
        )
        finals = []
        for steps in (10, 20, 40, 80):
            times, rates = uniform_schedule(3650.0, steps, 100.0e9 * 0.5 / 3650.0)
            arguments = dict(self.shared)
            arguments["times_days"] = times
            arguments["gas_rates_scf_per_day"] = rates
            arguments["solver_tolerance"] = 1.0e-14
            history = simulate_water_drive_depletion(aquifer=aquifer, **arguments)
            finals.append(history.true_pressures_psia[-1])
        time_constant_days = dict(history.truth.aquifer_parameters)["time_constant_days"]
        self.assertAlmostEqual(time_constant_days, 9.0e-6 * 3.0e8 / 400.0, delta=1.0e-9)
        self.assertGreater(3650.0 / 80.0, time_constant_days)
        differences = [abs(finals[i] - finals[i - 1]) for i in range(1, len(finals))]
        for index in range(1, len(differences)):
            self.assertLess(differences[index], differences[index - 1])
        order = richardson_order(finals[-3], finals[-2], finals[-1])
        self.assertLess(order, 1.5)

    def test_the_recorded_residual_is_consistent_with_an_independent_solve(self):
        """The recorded residual must be no larger than the error it is quoted to bound.

        Recomputing the same residual expression from the same stored series would
        prove nothing -- it is the quantity the solver drove to zero, so it is small by
        construction and re-evaluating it cannot detect anything the stopping rule did
        not. What the number is actually quoted for in a case study is that the
        generator's own numerical error is negligible against the effect being shown,
        and that claim is checkable only against a solve the module had no part in.

        So the residual is read as a pressure error, ``|residual| * Z``, and compared
        with the distance from an independently bracketed and bisected solve of the
        same steps. The 1e-6 psia window is the oracle's own resolution: its bisection
        runs to the spacing of double precision, but the scan that brackets it steps in
        increments of about a psi, so agreement is asserted only to a millionth of a
        psi rather than to the last bit.
        """
        history = simulate_water_drive_depletion(aquifer=self.aquifer, **self.shared)
        pressures, _influx, roots_per_step = coupled_history_by_scan_and_bisection(
            gas_in_place_scf=self.shared["gas_in_place_scf"],
            initial_pressure_psia=self.shared["initial_pressure_psia"],
            temperature_degr=self.shared["temperature_degr"],
            times_days=self.shared["times_days"],
            gas_rates_scf_per_day=self.shared["gas_rates_scf_per_day"],
            z_of_pressure=self.shared["z_of_pressure"],
            standard=self.shared["standard"],
            aquifer=self.aquifer,
        )
        self.assertEqual(set(roots_per_step), {1})
        for index in range(1, history.n_points):
            self.assertAlmostEqual(history.true_pressures_psia[index], pressures[index], delta=1.0e-6)
        worst_pressure_error = max(
            abs(history.true_pressures_psia[index] - pressures[index]) for index in range(history.n_points)
        )
        recorded_as_pressure = history.max_abs_residual_p_over_z_psia * max(history.true_z_factors)
        self.assertLess(recorded_as_pressure, 1.0e-6)
        self.assertLess(worst_pressure_error, 1.0e-6)
        # The generator's numerical error is orders of magnitude below the effect this
        # module exists to demonstrate, which is tens of psia of aquifer support.
        self.assertLess(worst_pressure_error, 1.0e-6 * self.shared["initial_pressure_psia"])

    def test_a_non_monotone_p_over_z_is_reported_on_the_history(self):
        """A deviation factor that makes the step balance multivalued must be flagged.

        Root uniqueness needs p/Z to rise with pressure, which the API contract does
        not require of ``z_of_pressure`` and which a Z rising faster than p violates.
        ``0.9 + 0.05 sin(p/100)`` is positive and finite everywhere, so it satisfies
        the contract, and yet at these conditions one of the steps has three roots. The
        solver returns one of them and the generated history acquires a 456 psi drop in
        a step whose neighbours drop about 70 psi.

        There is no honest way for a bracketed solver to pick the right branch, so the
        requirement is that the history says so rather than that the answer changes.
        """
        wiggly_arguments = dict(self.shared)
        wiggly_arguments["initial_pressure_psia"] = 4000.0
        wiggly_arguments["z_of_pressure"] = lambda pressure_psia: 0.9 + 0.05 * math.sin(pressure_psia / 100.0)
        history = simulate_volumetric_depletion(**wiggly_arguments)
        self.assertTrue(history.warnings)
        joined = " ".join(history.warnings)
        self.assertIn("not monotone", joined)
        self.assertIn("p/Z", joined)
        # The condition being warned about is real: at least one step has more than one
        # root, found by an independent scan that shares nothing with the solver.
        initial_p_over_z = history.truth.initial_p_over_z_psia
        multiplicities = []
        for cumulative in history.true_cumulative_gas_scf:
            target = initial_p_over_z * (1.0 - cumulative / history.truth.gas_in_place_scf)
            multiplicities.append(
                count_sign_changes(
                    lambda pressure, _t=target: pressure / wiggly_arguments["z_of_pressure"](pressure) - _t,
                    lower=14.696,
                    upper=4000.0,
                    samples=40000,
                )
            )
        self.assertGreater(max(multiplicities), 1)

    def test_a_monotone_p_over_z_leaves_the_history_unflagged(self):
        """The counterpart: a well-behaved Z must not produce a spurious warning."""
        trends = {"constant 0.9": constant_z(0.9), "0.86 + 2e-5 p": linear_z(0.86, 2.0e-5)}
        for description, z_callable in trends.items():
            with self.subTest(z_of_pressure=description):
                arguments = dict(self.shared)
                arguments["z_of_pressure"] = z_callable
                self.assertEqual(simulate_volumetric_depletion(**arguments).warnings, ())
                self.assertEqual(
                    simulate_water_drive_depletion(aquifer=self.aquifer, **arguments).warnings,
                    (),
                )

    def test_p_over_z_is_invariant_to_the_standard_volume_basis(self):
        """psc/Tsc cancels out of p/Z but not out of a reservoir volume.

        This is the metamorphic check the evidence card recommends against a hard-coded
        standard-condition constant. For a closed tank the whole p/Z series must be
        bit-identical between two bases, while the hydrocarbon pore volume scales by
        exactly the ratio of the two standard pressures.
        """
        spe = simulate_volumetric_depletion(**self.shared)
        louisiana_arguments = dict(self.shared)
        louisiana_arguments["standard"] = LOUISIANA
        louisiana = simulate_volumetric_depletion(**louisiana_arguments)
        self.assertEqual(louisiana.true_pressures_psia, spe.true_pressures_psia)
        self.assertEqual(louisiana.true_z_factors, spe.true_z_factors)
        self.assertAlmostEqual(
            louisiana.truth.hydrocarbon_pore_volume_rcf / spe.truth.hydrocarbon_pore_volume_rcf,
            15.025 / 14.696,
            delta=1.0e-12,
        )

    def test_water_drive_p_over_z_is_not_invariant_to_the_standard_volume_basis(self):
        """The influx enters as a fraction of the pore volume, so the basis matters."""
        spe = simulate_water_drive_depletion(aquifer=self.aquifer, **self.shared)
        louisiana_arguments = dict(self.shared)
        louisiana_arguments["standard"] = LOUISIANA
        louisiana = simulate_water_drive_depletion(aquifer=self.aquifer, **louisiana_arguments)
        self.assertNotEqual(louisiana.true_pressures_psia, spe.true_pressures_psia)

    def test_influx_grows_and_aquifer_support_holds_pressure_up(self):
        """Monotone influx, and a pressure above the closed-tank case at every step."""
        volumetric = simulate_volumetric_depletion(**self.shared)
        coupled = simulate_water_drive_depletion(aquifer=self.aquifer, **self.shared)
        for index in range(1, coupled.n_points):
            self.assertGreater(coupled.water_influx_bbl[index], coupled.water_influx_bbl[index - 1])
            self.assertGreater(coupled.true_pressures_psia[index], volumetric.true_pressures_psia[index])

    def test_water_drive_inflates_the_apparent_gas_in_place(self):
        """The counterexample this module exists to generate.

        A weak water drive holds p/Z up, which flattens the depletion line and moves its
        x-intercept to the right. The straight-line reading of the generated history
        must therefore exceed the true gas in place, by a margin comparable to the
        published field and simulation cases rather than by a rounding error.
        """
        volumetric = simulate_volumetric_depletion(**self.shared)
        coupled = simulate_water_drive_depletion(aquifer=self.aquifer, **self.shared)
        true_gas = self.shared["gas_in_place_scf"]
        volumetric_reading = two_point_x_intercept(volumetric.cumulative_gas_scf, volumetric.p_over_z_psia())
        coupled_reading = two_point_x_intercept(coupled.cumulative_gas_scf, coupled.p_over_z_psia())
        self.assertAlmostEqual(volumetric_reading / true_gas, 1.0, delta=1.0e-12)
        self.assertGreater(coupled_reading / true_gas, 1.05)

    def test_an_aquifer_above_the_initial_reservoir_pressure_is_handled(self):
        """The search must expand above pi rather than assume the root lies below it.

        An aquifer charged above the gas reservoir's initial pressure is unusual but
        admissible, and it can push the reservoir above pi in the first steps. This
        exercises the upper end of the bracket, which a fixed bound at pi would
        silently get wrong. The check is against the independently bracketed and
        bisected solve rather than against a rearrangement of the equation the module
        solved; the 1e-6 psia window is that oracle's scan-plus-bisection resolution.
        """
        overpressured = StubAquifer(
            initial_pressure_psia=6000.0,
            water_volume_bbl=3.0e8,
            total_compressibility_per_psi=9.0e-6,
            productivity_index_bbl_per_day_psi=400.0,
        )
        arguments = dict(self.shared)
        arguments["gas_rates_scf_per_day"] = (1.0,) * len(self.rates)
        history = simulate_water_drive_depletion(aquifer=overpressured, **arguments)
        self.assertGreater(history.true_pressures_psia[1], history.true_pressures_psia[0])
        pressures, influx, roots_per_step = coupled_history_by_scan_and_bisection(
            gas_in_place_scf=arguments["gas_in_place_scf"],
            initial_pressure_psia=arguments["initial_pressure_psia"],
            temperature_degr=arguments["temperature_degr"],
            times_days=arguments["times_days"],
            gas_rates_scf_per_day=arguments["gas_rates_scf_per_day"],
            z_of_pressure=arguments["z_of_pressure"],
            standard=arguments["standard"],
            aquifer=overpressured,
        )
        self.assertEqual(set(roots_per_step), {1})
        for index in range(history.n_points):
            self.assertAlmostEqual(history.true_pressures_psia[index], pressures[index], delta=1.0e-6)
            self.assertAlmostEqual(history.water_influx_bbl[index], influx[index], delta=1.0e-2)

    def test_the_public_derived_series_agree_with_the_recorded_ones(self):
        """``p_over_z_psia``, ``true_p_over_z_psia`` and ``depletion_fraction`` are ratios.

        Three small accessors a consumer reads straight into a plot or a report. They
        are exact arithmetic on the stored series, so equality is asserted bit for bit
        rather than with a tolerance; a tolerance here would only hide a wrong series
        being divided by the right one.
        """
        noisy = dict(self.shared)
        noisy["noise"] = NoiseModel(pressure_sigma_psia=10.0, z_relative_sigma=1.0e-3, label="gauge")
        history = simulate_water_drive_depletion(aquifer=self.aquifer, **noisy)
        observed = history.p_over_z_psia()
        truth_line = history.true_p_over_z_psia()
        self.assertEqual(len(observed), history.n_points)
        self.assertNotEqual(observed, truth_line)
        for index in range(history.n_points):
            self.assertEqual(observed[index], history.pressures_psia[index] / history.z_factors[index])
            self.assertEqual(
                truth_line[index],
                history.true_pressures_psia[index] / history.true_z_factors[index],
            )
        self.assertEqual(
            history.depletion_fraction(),
            history.true_cumulative_gas_scf[-1] / history.truth.gas_in_place_scf,
        )
        # The schedule produces half the tank, so the recorded fraction must be a half.
        self.assertAlmostEqual(history.depletion_fraction(), 0.5, delta=1.0e-12)

    def test_history_is_immutable_and_self_describing(self):
        history = simulate_water_drive_depletion(aquifer=self.aquifer, **self.shared)
        self.assertIsInstance(history, DepletionHistory)
        self.assertIsInstance(history.pressures_psia, tuple)
        self.assertIsInstance(history.water_influx_bbl, tuple)
        self.assertIsInstance(history.cumulative_water_stb, tuple)
        self.assertIsInstance(history.warnings, tuple)
        self.assertEqual(history.n_points, len(self.times))
        self.assertEqual(history.method, "fetkovich_coupled_tank")
        self.assertEqual(history.truth.drive, "fetkovich_water_drive")
        self.assertEqual(dict(history.truth.aquifer_parameters)["water_volume_bbl"], 3.0e8)
        with self.assertRaises(FrozenInstanceError):
            history.truth.gas_in_place_scf = 1.0


class NoiseModelSemantics(unittest.TestCase):
    """The dimensioned meaning of each noise term, and what the model says about itself.

    ``_apply_noise`` is the one part of the module whose arguments are not pinned down
    by the physics: nothing in a balance residual notices whether a relative sigma was
    applied relatively, or whether a bias was added or subtracted. Those have to be
    asserted directly or they are not tested at all.
    """

    def setUp(self):
        self.times, self.rates = uniform_schedule(3650.0, 10, 100.0e9 * 0.5 / 3650.0)
        self.shared = dict(
            gas_in_place_scf=100.0e9,
            initial_pressure_psia=5000.0,
            temperature_degr=660.0,
            times_days=self.times,
            gas_rates_scf_per_day=self.rates,
            standard=SPE,
            seed=4242,
        )

    def test_a_positive_pressure_bias_raises_every_reported_pressure(self):
        """``pressure_bias_psia`` is added, in psia, to every point.

        A sign error here is invisible to every other test in this file, and it matters
        more than scatter does: a bias on an extrapolated x-intercept moves the answer
        rather than widening it.
        """
        bias = 25.0
        biased = simulate_volumetric_depletion(
            z_of_pressure=linear_z(0.86, 2.0e-5),
            noise=NoiseModel(pressure_bias_psia=bias, label="offset gauge"),
            **self.shared,
        )
        for reported, true_value in zip(biased.pressures_psia, biased.true_pressures_psia, strict=True):
            self.assertEqual(reported, true_value + bias)
            self.assertGreater(reported, true_value)

    def test_the_z_sigma_is_relative_not_absolute(self):
        """``z_relative_sigma`` scales with Z, so the perturbation is proportional.

        Run the identical seed at two constant deviation factors differing by a factor
        of two. A relative sigma makes the absolute departures differ by that same
        factor; an absolute one would make them identical. The comparison is exact
        because the two runs consume the same variates in the same order.
        """
        arguments = dict(self.shared)
        arguments["noise"] = NoiseModel(z_relative_sigma=5.0e-3, label="chart reading")
        low = simulate_volumetric_depletion(z_of_pressure=constant_z(0.45), **arguments)
        high = simulate_volumetric_depletion(z_of_pressure=constant_z(0.90), **arguments)
        for index in range(low.n_points):
            low_departure = low.z_factors[index] - low.true_z_factors[index]
            high_departure = high.z_factors[index] - high.true_z_factors[index]
            self.assertNotEqual(low_departure, 0.0)
            self.assertAlmostEqual(high_departure / low_departure, 2.0, delta=1.0e-12)

    def test_the_cumulative_gas_sigma_is_relative_not_absolute(self):
        """``cumulative_gas_relative_sigma`` scales with Gp, so Gp = 0 stays exactly zero.

        An allocation error is a percentage of what was allocated. Applied absolutely it
        would put gas on the meter before a well opened, which also destroys the one
        point on a p/Z plot whose abscissa is known without error.
        """
        arguments = dict(self.shared)
        arguments["noise"] = NoiseModel(cumulative_gas_relative_sigma=1.0e-2, label="allocation")
        history = simulate_volumetric_depletion(z_of_pressure=linear_z(0.86, 2.0e-5), **arguments)
        self.assertEqual(history.cumulative_gas_scf[0], 0.0)
        self.assertEqual(history.true_cumulative_gas_scf[0], 0.0)
        for index in range(1, history.n_points):
            true_value = history.true_cumulative_gas_scf[index]
            relative = history.cumulative_gas_scf[index] / true_value - 1.0
            self.assertNotEqual(relative, 0.0)
            # Ten points drawn at sigma = 1e-2; the largest |z| in ten standard normals
            # exceeds 5 with probability about 3e-7, so 5e-2 is a bound on the relative
            # departure that is safe for any seed rather than tuned to this one.
            self.assertLess(abs(relative), 5.0e-2)

    def test_describe_does_not_call_a_noisy_model_noise_free(self):
        """``describe`` goes into a run record, so it may not contradict the object.

        The label used to default to the words "noise free", which meant an unlabelled
        model with a 5 psia gauge sigma described itself as noise free while
        ``is_noise_free`` returned False for the same object.
        """
        noisy = NoiseModel(pressure_sigma_psia=5.0)
        self.assertFalse(noisy.is_noise_free())
        self.assertNotIn("noise free", noisy.describe())
        self.assertIn("5 psia", noisy.describe())

        self.assertTrue(NOISE_FREE.is_noise_free())
        self.assertTrue(NOISE_FREE.describe().startswith("noise free"))

        labelled = NoiseModel(pressure_sigma_psia=5.0, label="gauge scatter")
        self.assertTrue(labelled.describe().startswith("gauge scatter"))
        # Every sigma is printed either way, so a reader can check the wording.
        for model in (noisy, NOISE_FREE, labelled):
            self.assertIn("sigma_Z/Z", model.describe())
            self.assertIn("bias_p", model.describe())


@unittest.skipIf(FetkovichAquifer is None, "reservoir_lab.aquifer is not available yet")
class AquiferModuleCrossCheck(unittest.TestCase):
    """Two independent transcriptions of Fetkovich Eq. (6) must agree.

    The generator applies the recursion itself rather than delegating, so that a
    transcription error on either side shows up instead of cancelling. That only pays
    off if the two are actually compared, which is what this does.
    """

    def setUp(self):
        self.parameters = dict(
            initial_pressure_psia=5000.0,
            water_volume_bbl=3.0e8,
            total_compressibility_per_psi=9.0e-6,
            productivity_index_bbl_per_day_psi=400.0,
        )
        self.aquifer = FetkovichAquifer(**self.parameters)
        self.times, self.rates = uniform_schedule(3650.0, 10, 100.0e9 * 0.5 / 3650.0)
        self.history = simulate_water_drive_depletion(
            gas_in_place_scf=100.0e9,
            initial_pressure_psia=5000.0,
            temperature_degr=660.0,
            times_days=self.times,
            gas_rates_scf_per_day=self.rates,
            z_of_pressure=linear_z(0.86, 2.0e-5),
            standard=SPE,
            aquifer=self.aquifer,
            noise=NOISE_FREE,
            seed=0,
        )

    def test_maximum_encroachable_volume_agrees(self):
        recorded = dict(self.history.truth.aquifer_parameters)["maximum_influx_bbl"]
        self.assertAlmostEqual(recorded / self.aquifer.maximum_influx_bbl(), 1.0, delta=1.0e-12)

    def test_influx_series_agrees_with_the_aquifer_module(self):
        """Replay the generated pressure path through the aquifer module's own history.

        Both apply the Eq. (8) mean boundary pressure over each interval, so on a given
        pressure path the two cumulative influx series must coincide to round-off.
        """
        steps = self.aquifer.influx_history(
            times_days=self.history.times_days,
            reservoir_pressure_psia=self.history.true_pressures_psia,
        )
        self.assertEqual(len(steps), self.history.n_points - 1)
        for index, step in enumerate(steps, start=1):
            self.assertAlmostEqual(
                step.cumulative_influx_bbl / self.history.water_influx_bbl[index],
                1.0,
                delta=1.0e-12,
            )

    def test_a_stub_carrying_the_same_parameters_gives_the_same_history(self):
        """The coupling depends on the four published parameters and nothing else."""
        stub = StubAquifer(**self.parameters)
        with_stub = simulate_water_drive_depletion(
            gas_in_place_scf=100.0e9,
            initial_pressure_psia=5000.0,
            temperature_degr=660.0,
            times_days=self.times,
            gas_rates_scf_per_day=self.rates,
            z_of_pressure=linear_z(0.86, 2.0e-5),
            standard=SPE,
            aquifer=stub,
            noise=NOISE_FREE,
            seed=0,
        )
        self.assertEqual(self.history.true_pressures_psia, with_stub.true_pressures_psia)
        self.assertEqual(self.history.water_influx_bbl, with_stub.water_influx_bbl)


if __name__ == "__main__":
    unittest.main()

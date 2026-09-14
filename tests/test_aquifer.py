"""Verification of the Fetkovich aquifer recursion.

The four contract C7 categories, and where each one lives:

* Independent oracle -- :class:`PublishedWorkedExampleTests` runs Ahmed's Example
  10-10, a Fetkovich calculation performed by hand on data from Dake (1978) and
  printed with its intermediate columns, and :class:`IndependentAlgorithmTests`
  integrates the governing differential equation with a fourth-order Runge-Kutta that
  shares no code with the recursion.
* Limiting case -- :class:`ClosedFormLimitTests`: the constant-boundary-pressure
  closed form, the infinite-aquifer (Schilthuis steady state) limit, the
  infinite-productivity limit, and zero drawdown. One test in that class,
  test_single_coarse_step_matches_runge_kutta, is an oracle rather than a limit: it
  is where the one-step advance is checked against the foreign integrator, because at
  a single step the closed form and the module's kernel are the same expression and
  comparing them would prove nothing.
* Invalid input -- :class:`InvalidInputTests` exercises every raise documented in the
  module.
* Property or invariant -- :class:`InvariantTests` and :class:`TimestepRefinementTests`
  cover the influx bounds, monotonicity, dimensional scaling, internal consistency of
  the returned records, and the observed order of convergence in the timestep.

One test class, :class:`EvidenceCardFixtureTests`, is a regression fixture rather than
an oracle and says so: its expected values were produced by the independent scratch
implementation written while the evidence card was assembled, not by a published
source. It is kept because it also encodes a correction the card's adversarial review
made to its own fixture.
"""

from __future__ import annotations

import dataclasses
import decimal
import fractions
import itertools
import math
import sys
import unittest

from reservoir_lab.aquifer import (
    BOUNDARY_RULE_CALLER_SUPPLIED,
    BOUNDARY_RULE_EQ8_MIDPOINT,
    FETKOVICH_METHOD,
    AquiferStep,
    FetkovichAquifer,
)
from reservoir_lab.errors import InvalidInputError
from reservoir_lab.numerics import richardson_order

CUBIC_FEET_PER_BARREL = 5.615

#: Double-precision unit round-off, 2.22e-16. Every round-off tolerance below is built
#: from this and from a count of operations, never from an observed error.
EPS = sys.float_info.epsilon


def radial_sector_pore_volume_bbl(
    *,
    aquifer_radius_ft: float,
    reservoir_radius_ft: float,
    thickness_ft: float,
    porosity: float,
    encroachment_fraction: float,
) -> float:
    """Wi for a radial sector aquifer, Fetkovich Eq. (17), in reservoir bbl.

    Kept in the test rather than in the module: the module takes Wi as a given, and a
    geometry helper shipped alongside it would make the convention check below circular.
    The encroachment fraction sits inside Wi here, which is Fetkovich's own placement
    and the one the module's docstring requires.
    """
    annulus_ft3 = (
        math.pi
        * encroachment_fraction
        * (aquifer_radius_ft**2 - reservoir_radius_ft**2)
        * thickness_ft
        * porosity
    )
    return annulus_ft3 / CUBIC_FEET_PER_BARREL


def radial_closed_boundary_pi_bbl_per_day_psi(
    *,
    permeability_md: float,
    thickness_ft: float,
    encroachment_fraction: float,
    water_viscosity_cp: float,
    aquifer_radius_ft: float,
    reservoir_radius_ft: float,
) -> float:
    """Fetkovich's radial pseudosteady productivity index, k in md.

    ``J = 0.00708 * k * h * f / (mu_w * (ln(r_a/r_o) - 0.75))``. The constant is
    ``2*pi*0.001127``, the field-unit Darcy constant times the circumference factor;
    with k in darcies it would be 7.08 and the influx would be a thousandfold wrong.
    Also a test-side helper, for the same reason as the pore volume above.
    """
    radius_ratio = aquifer_radius_ft / reservoir_radius_ft
    shape = math.log(radius_ratio) - 0.75
    if shape <= 0.0:
        raise ValueError("the -0.75 pseudosteady shape term is invalid below rD = exp(0.75)")
    return 0.00708 * permeability_md * thickness_ft * encroachment_fraction / (water_viscosity_cp * shape)


def closed_form_influx_bbl(
    aquifer: FetkovichAquifer, *, boundary_pressure_psia: float, time_days: float
) -> float:
    """Cumulative influx for a boundary pressure held constant since t = 0.

    Derived here rather than taken from the module, so that it is an oracle and not a
    restatement. Fetkovich Eq. (1) gives the rate as ``J*(p_aq - p_wf)`` and Eq. (2)
    gives ``p_aq = p_i - We/(ct*Wi)``, so

        dWe/dt = J * (p_i - p_wf - We/(ct*Wi)),

    a linear first-order equation with We(0) = 0 whose solution is

        We(t) = ct*Wi*(p_i - p_wf) * (1 - exp(-t/tau)),   tau = ct*Wi/J.

    This is Fetkovich Eq. (5) with ``(q_wi)max = J*p_i`` substituted, and none of the
    module's own arithmetic appears in it.
    """
    storage = aquifer.total_compressibility_per_psi * aquifer.water_volume_bbl
    tau = storage / aquifer.productivity_index_bbl_per_day_psi
    drawdown = aquifer.initial_pressure_psia - boundary_pressure_psia
    return storage * drawdown * (1.0 - math.exp(-time_days / tau))


def runge_kutta_influx_bbl(
    aquifer: FetkovichAquifer, *, boundary_pressure, end_time_days: float, steps: int
) -> float:
    """Cumulative influx by classical RK4 on the governing differential equation.

    A genuinely different algorithm: a fixed-step explicit integrator of

        dWe/dt = J * (p_i - We/(ct*Wi) - p_wf(t))

    which converges to the true solution from outside the Fetkovich scheme and shares
    no expression with it. ``boundary_pressure`` is a callable of time in days, so the
    pressure history is continuous here and is not sampled on the same grid the
    recursion uses.
    """
    storage = aquifer.total_compressibility_per_psi * aquifer.water_volume_bbl
    productivity = aquifer.productivity_index_bbl_per_day_psi
    initial_pressure = aquifer.initial_pressure_psia

    def rate(time: float, influx: float) -> float:
        return productivity * (initial_pressure - influx / storage - boundary_pressure(time))

    step = end_time_days / steps
    influx = 0.0
    for index in range(steps):
        time = index * step
        k1 = rate(time, influx)
        k2 = rate(time + step / 2.0, influx + step * k1 / 2.0)
        k3 = rate(time + step / 2.0, influx + step * k2 / 2.0)
        k4 = rate(time + step, influx + step * k3)
        influx += step * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
    return influx


def reference_aquifer() -> FetkovichAquifer:
    """Build the aquifer used by most of the checks below.

    k = 100 md, h = 50 ft, phi = 0.20, mu_w = 0.55 cp, ct = 7e-6 1/psi, r_o = 2000 ft,
    r_a = 10000 ft, full 360-degree encroachment, p_i = 3000 psia. rD = 5, comfortably
    above the exp(0.75) = 2.117 floor where the pseudosteady shape term changes sign.
    """
    water_volume = radial_sector_pore_volume_bbl(
        aquifer_radius_ft=10000.0,
        reservoir_radius_ft=2000.0,
        thickness_ft=50.0,
        porosity=0.20,
        encroachment_fraction=1.0,
    )
    productivity = radial_closed_boundary_pi_bbl_per_day_psi(
        permeability_md=100.0,
        thickness_ft=50.0,
        encroachment_fraction=1.0,
        water_viscosity_cp=0.55,
        aquifer_radius_ft=10000.0,
        reservoir_radius_ft=2000.0,
    )
    return FetkovichAquifer(
        initial_pressure_psia=3000.0,
        water_volume_bbl=water_volume,
        total_compressibility_per_psi=7.0e-6,
        productivity_index_bbl_per_day_psi=productivity,
    )


class PublishedWorkedExampleTests(unittest.TestCase):
    """Ahmed, Reservoir Engineering Handbook, Example 10-10 (data from Dake 1978).

    A hand calculation published with its intermediate columns, produced decades before
    any code in this repository. It pins six things at once: the 0.00708 constant with
    permeability in millidarcies, the ln(rD) - 0.75 shape term, the 5.615 ft^3/bbl
    conversion, Wei = ct*Wi*p_i with the encroachment fraction inside Wi, the Eq. (6)
    recursion, and the Eq. (8) mid-interval boundary pressure.

    Tolerances are loose on purpose. The published columns are rounded to three or four
    figures and the rounding is carried forward by hand from one step to the next, so
    an implementation that agreed to more digits than this would be suspicious rather
    than reassuring.
    """

    INITIAL_PRESSURE = 2740.0
    COMPRESSIBILITY = 7.0e-6
    ENCROACHMENT = 140.0 / 360.0
    TIMES = (0.0, 365.0, 730.0, 1095.0, 1460.0)
    BOUNDARY_PRESSURE = (2740.0, 2500.0, 2290.0, 2109.0, 1949.0)
    #: Ahmed's printed cumulative influx column, MM bbl.
    PUBLISHED_CUMULATIVE_MMBBL = (3.925, 13.540, 25.510, 37.971)
    #: Ahmed's printed start-of-step aquifer pressure column, psia.
    PUBLISHED_AQUIFER_PRESSURE = (2740.0, 2689.0, 2565.0, 2409.0)

    def setUp(self) -> None:
        self.water_volume = radial_sector_pore_volume_bbl(
            aquifer_radius_ft=46000.0,
            reservoir_radius_ft=9200.0,
            thickness_ft=100.0,
            porosity=0.25,
            encroachment_fraction=self.ENCROACHMENT,
        )
        self.productivity = radial_closed_boundary_pi_bbl_per_day_psi(
            permeability_md=200.0,
            thickness_ft=100.0,
            encroachment_fraction=self.ENCROACHMENT,
            water_viscosity_cp=0.55,
            aquifer_radius_ft=46000.0,
            reservoir_radius_ft=9200.0,
        )
        self.aquifer = FetkovichAquifer(
            initial_pressure_psia=self.INITIAL_PRESSURE,
            water_volume_bbl=self.water_volume,
            total_compressibility_per_psi=self.COMPRESSIBILITY,
            productivity_index_bbl_per_day_psi=self.productivity,
        )

    def test_published_setup_quantities(self):
        # Ahmed prints Wi = 28.41e9 bbl WITHOUT the encroachment fraction and then
        # applies it in Wei; this module keeps it in Wi. The two products must agree,
        # which is the check that the fraction is applied once and only once.
        full_circle_volume = self.water_volume / self.ENCROACHMENT
        self.assertAlmostEqual(full_circle_volume / 28.41e9, 1.0, places=3)
        self.assertAlmostEqual(self.productivity / 116.5, 1.0, places=3)
        self.assertAlmostEqual(self.aquifer.maximum_influx_bbl() / 211.9e6, 1.0, places=3)

    def test_published_decline_factor(self):
        # Ahmed prints J*p_i/Wei = 1.506e-3 1/day and 1 - exp(-J*p_i*dt/Wei) = 0.4229
        # for dt = 365 d. The first of those is 1/tau, which is where the cancellation
        # of the initial pressure shows up as a number rather than as an argument.
        self.assertAlmostEqual(1.0 / self.aquifer.time_constant_days(), 1.506e-3, places=6)
        history = self.aquifer.influx_history(
            times_days=self.TIMES, reservoir_pressure_psia=self.BOUNDARY_PRESSURE
        )
        self.assertAlmostEqual(history[0].decline_factor, 0.4229, places=4)

    def test_published_influx_trace(self):
        history = self.aquifer.influx_history(
            times_days=self.TIMES, reservoir_pressure_psia=self.BOUNDARY_PRESSURE
        )
        self.assertEqual(len(history), 4)
        for index, (record, published) in enumerate(
            zip(history, self.PUBLISHED_CUMULATIVE_MMBBL, strict=True)
        ):
            with self.subTest(step=index + 1):
                # 0.5%, set by the published data rather than by the outcome: Ahmed
                # prints the cumulative column to four significant figures and carries
                # the rounded driving head forward by hand from step to step, so a
                # half-percent band is roughly what that hand arithmetic can support.
                # It still discriminates -- with the Eq. (8) mid-interval pressure the
                # worst step here is 0.08%, while a start-of-interval or end-of-interval
                # boundary pressure misses by of order 100%.
                self.assertLess(abs(record.cumulative_influx_bbl / (published * 1e6) - 1.0), 5e-3)

    def test_published_aquifer_pressure_trace(self):
        history = self.aquifer.influx_history(
            times_days=self.TIMES, reservoir_pressure_psia=self.BOUNDARY_PRESSURE
        )
        # 2 psi rather than 1: Ahmed rounds the driving-head column to whole psi at
        # every step and the rounding accumulates, reaching 1.3 psi by the fourth step.
        for index, (record, published) in enumerate(
            zip(history, self.PUBLISHED_AQUIFER_PRESSURE, strict=True)
        ):
            with self.subTest(step=index + 1):
                self.assertLess(abs(record.aquifer_pressure_start_psia - published), 2.0)

    def test_published_mid_interval_boundary_pressures(self):
        history = self.aquifer.influx_history(
            times_days=self.TIMES, reservoir_pressure_psia=self.BOUNDARY_PRESSURE
        )
        for record, expected in zip(history, (2620.0, 2395.0, 2199.5, 2029.0), strict=True):
            self.assertAlmostEqual(record.boundary_pressure_psia, expected, places=10)


class ClosedFormLimitTests(unittest.TestCase):
    """Limits where the answer is known in closed form."""

    def setUp(self) -> None:
        self.aquifer = reference_aquifer()

    def test_constant_boundary_pressure_reproduces_closed_form(self):
        # The exactness claim: for a boundary pressure held constant the recursion is
        # the exact solution of its own equation at any step count, not a first-order
        # approximation to it. Splitting the same interval into 7 or into 10000 steps
        # must therefore land on the same number to round-off.
        #
        # The single-step case is deliberately absent. At n = 1 closed_form_influx_bbl
        # evaluates storage*drawdown*(1 - exp(-t/tau)) and the module evaluates
        # storage*(p_aq - p_wf)*(-expm1(-dt/tau)) -- algebraically the same expression,
        # so the comparison would test exp against expm1 and nothing else. The one-step
        # advance is checked against a genuinely foreign algorithm in
        # test_single_coarse_step_matches_runge_kutta below.
        boundary = 2500.0
        for end_time in (10.0, 50.0, 100.0, 365.0, 3650.0):
            expected = closed_form_influx_bbl(
                self.aquifer, boundary_pressure_psia=boundary, time_days=end_time
            )
            for steps in (7, 365, 10000):
                with self.subTest(end_time=end_time, steps=steps):
                    times = [end_time * i / steps for i in range(steps + 1)]
                    history = self.aquifer.influx_history(
                        times_days=times, reservoir_pressure_psia=[boundary] * (steps + 1)
                    )
                    # There is no truncation error to allow for, so the whole budget is
                    # round-off, and it is bounded a priori rather than measured. Each
                    # step performs four roundings in the kernel, and the absolute error
                    # carried on the aquifer pressure is amplified by the conditioning
                    # of the driving-head subtraction, p_aq/(p_aq - p_wf) = 3000/500 = 6
                    # at these pressures. So the per-step relative error is at most
                    # about (4 + 6)*EPS and n of them accumulate linearly in the worst
                    # case. Errors partly cancel in practice, which is headroom, not
                    # slack: the bound is a bound.
                    tolerance = 10.0 * (steps + 1) * EPS
                    self.assertLess(abs(history[-1].cumulative_influx_bbl / expected - 1.0), tolerance)

    def test_single_coarse_step_matches_runge_kutta(self):
        # The one-step exactness claim against an algorithm that shares no expression
        # with it: RK4 marched over the same interval in many substeps. This is the
        # real content of the n = 1 case removed from the closed-form test above --
        # here the reference is produced by a different numerical method, so agreement
        # says something about the recursion rather than about exp versus expm1.
        boundary = 2500.0
        tau = self.aquifer.time_constant_days()
        for end_time in (10.0, 50.0, 100.0, 365.0, 3650.0):
            # Fix the RK4 substep at z = h/tau = 0.002 so its own error is known before
            # the comparison is made, rather than chosen to fit the outcome.
            target_z = 0.002
            substeps = max(8, math.ceil((end_time / tau) / target_z))
            z = (end_time / tau) / substeps
            reference = runge_kutta_influx_bbl(
                self.aquifer,
                boundary_pressure=lambda _time: boundary,
                end_time_days=end_time,
                steps=substeps,
            )
            record = self.aquifer.step(
                aquifer_pressure_psia=self.aquifer.initial_pressure_psia,
                reservoir_pressure_psia=boundary,
                timestep_days=end_time,
            )
            with self.subTest(end_time=end_time):
                # RK4's own error, derived rather than observed. For dWe/dt = (A-We)/tau
                # the scheme multiplies the remaining head by its stability polynomial
                # R(z) = 1 - z + z^2/2 - z^3/6 + z^4/24, and R(z) - exp(-z) = z^5/120 to
                # leading order, so after N steps the relative error in We is
                # exp(-T/tau) * N * z^5 * exp(z)/120 divided by (1 - exp(-T/tau)). The
                # factor 1.5 covers the O(z^6) term dropped from that expansion. The
                # second term is round-off: about eight roundings per RK4 step, each on
                # a quantity of order A, expressed relative to We.
                decay = math.exp(-end_time / tau)
                grown = -math.expm1(-end_time / tau)
                truncation = decay * substeps * z**5 * math.exp(z) / 120.0 / grown
                round_off = 8.0 * substeps * EPS / grown
                tolerance = 1.5 * truncation + round_off
                self.assertLess(abs(record.influx_increment_bbl / reference - 1.0), tolerance)

    def test_unequal_timesteps_also_reproduce_the_closed_form(self):
        # Nothing in the exactness argument requires equal steps, unlike the van
        # Everdingen-Hurst superposition convention. Ragged steps must land on the same
        # answer as smooth ones.
        boundary = 2200.0
        times = [0.0, 1.0, 1.5, 90.0, 91.25, 400.0, 1000.0, 1000.5, 3650.0]
        history = self.aquifer.influx_history(
            times_days=times, reservoir_pressure_psia=[boundary] * len(times)
        )
        expected = closed_form_influx_bbl(self.aquifer, boundary_pressure_psia=boundary, time_days=times[-1])
        self.assertLess(abs(history[-1].cumulative_influx_bbl / expected - 1.0), 1e-12)

    def test_infinite_aquifer_tends_to_steady_state_influx(self):
        # As ct*Wi grows with J fixed, the aquifer stops depleting and the model becomes
        # Schilthuis steady state, q_w = J*(p_i - p_wf) with p_i held forever. The
        # closed form for one step is then simply J*(p_i - p_wf)*dt, derived from
        # Eq. (1) with p_aq frozen at p_i. The error must fall like 1/(ct*Wi).
        boundary = 2500.0
        timestep = 30.0
        errors = []
        analytic_leading_error = []
        dimensionless_steps = []
        for scale in (1e2, 1e4, 1e6, 1e8):
            aquifer = FetkovichAquifer(
                initial_pressure_psia=3000.0,
                water_volume_bbl=self.aquifer.water_volume_bbl * scale,
                total_compressibility_per_psi=7.0e-6,
                productivity_index_bbl_per_day_psi=(self.aquifer.productivity_index_bbl_per_day_psi),
            )
            steady = aquifer.productivity_index_bbl_per_day_psi * (3000.0 - boundary) * timestep
            record = aquifer.step(
                aquifer_pressure_psia=3000.0,
                reservoir_pressure_psia=boundary,
                timestep_days=timestep,
            )
            errors.append(abs(record.influx_increment_bbl / steady - 1.0))
            # Expanding 1 - exp(-dt/tau) leaves a leading relative defect of dt/(2*tau),
            # so the departure from the steady-state limit is not merely small, it is
            # predictable. Asserting against the prediction is stronger than asserting
            # against a threshold.
            analytic_leading_error.append(timestep / (2.0 * aquifer.time_constant_days()))
            dimensionless_steps.append(timestep / aquifer.time_constant_days())
        self.assertLess(errors[-1], 1e-8)
        for observed, predicted, x in zip(errors, analytic_leading_error, dimensionless_steps, strict=True):
            # The expansion is known to more than one term, so assert against more than
            # one term. With x = dt/tau, (1 - exp(-x))/x = 1 - x/2 + x^2/6 - x^3/24, so
            # the relative defect is (x/2)*(1 - x/3 + x^2/12 - ...) and therefore
            #     observed/predicted = 1 - x/3 + x^2/12 - ...
            # exactly. Asserting the x/3 correction as well as the leading term is what
            # makes this a shape check rather than a magnitude check; the residual left
            # over is the x^2/12 term.
            #
            # Two contributions bound that residual. The first is x^2/12 itself, with a
            # 20% margin for the -x^3/60 term after it. The second is round-off: the
            # measured defect is |influx/steady - 1|, a subtraction of two numbers that
            # agree to within x/2, so its absolute error of a few EPS becomes
            # (a few EPS)/(x/2) once divided by predicted. At the widest scale in the
            # sweep x is 6e-9 and this floor is what the assertion is really made of --
            # stated plainly, because it means the tightest aquifer here is the loosest
            # assertion, and no arrangement of the arithmetic avoids that.
            tolerance = 1.2 * x * x / 12.0 + 8.0 * EPS / x
            self.assertLess(abs(observed / predicted - (1.0 - x / 3.0)), tolerance)
        for coarse, fine in itertools.pairwise(errors):
            self.assertLess(fine, coarse / 50.0)

    def test_infinite_productivity_index_equilibrates_within_one_step(self):
        # The other limit: as J grows the time constant collapses, the decline factor
        # saturates at 1, and the aquifer gives up its whole driving head in one step.
        # The closed form is then the aquifer material balance alone, We = ct*Wi*dp.
        storage = self.aquifer.total_compressibility_per_psi * self.aquifer.water_volume_bbl
        boundary = 2400.0
        aquifer = FetkovichAquifer(
            initial_pressure_psia=3000.0,
            water_volume_bbl=self.aquifer.water_volume_bbl,
            total_compressibility_per_psi=self.aquifer.total_compressibility_per_psi,
            productivity_index_bbl_per_day_psi=1.0e12,
        )
        record = aquifer.step(
            aquifer_pressure_psia=3000.0, reservoir_pressure_psia=boundary, timestep_days=1.0
        )
        self.assertAlmostEqual(record.decline_factor, 1.0, places=15)
        self.assertAlmostEqual(record.influx_increment_bbl / (storage * 600.0), 1.0, places=12)
        self.assertAlmostEqual(record.aquifer_pressure_end_psia, boundary, places=6)

    def test_zero_pressure_drop_gives_exactly_zero_influx(self):
        # Exactly zero, not nearly zero: the increment is a product with the driving
        # head as a factor, so a floating-point residue here would mean the difference
        # is being formed somewhere it should not be.
        record = self.aquifer.step(
            aquifer_pressure_psia=3000.0, reservoir_pressure_psia=3000.0, timestep_days=100.0
        )
        self.assertEqual(record.influx_increment_bbl, 0.0)
        self.assertEqual(record.cumulative_influx_bbl, 0.0)
        self.assertEqual(record.aquifer_pressure_end_psia, 3000.0)

        history = self.aquifer.influx_history(
            times_days=[0.0, 100.0, 500.0, 2000.0], reservoir_pressure_psia=[3000.0] * 4
        )
        for record in history:
            self.assertEqual(record.influx_increment_bbl, 0.0)
            self.assertEqual(record.cumulative_influx_bbl, 0.0)

    def test_wei_is_the_zero_pressure_extrapolation_not_the_drawdown_volume(self):
        """Wei is recovered from the influx path as the boundary pressure tends to zero.

        The correction recorded in docs/evidence/aquifer.md is that Wei = ct*Wi*p_i,
        the influx that would occur if the aquifer were drawn to zero absolute
        pressure, while ct*Wi*(p_i - p) is We(p), the influx at a sustained boundary
        pressure p.

        The earlier form of this test recomputed ct*Wi in the test body and asserted
        maximum_influx_bbl()/(ct*Wi*p_i) == 1, which is a restatement of the one line
        the method contains and cannot fail while that line exists. What is asserted
        instead is the definition itself: run the recursion to convergence against a
        boundary pressure that is a billionth of p_i, and the cumulative influx it
        produces must approach Wei. That routes the claim through the stepping
        arithmetic, which does not evaluate maximum_influx_bbl() at all, so the two
        sides are computed by different code.

        The published gate on the numerical value of Wei is separate and lives in
        PublishedWorkedExampleTests.test_published_setup_quantities, against Ahmed's
        printed 211.9e6 bbl.
        """
        initial = self.aquifer.initial_pressure_psia
        pressure_ratio = 1.0e-9
        boundary = initial * pressure_ratio
        tau = self.aquifer.time_constant_days()
        # Sixty time constants: exp(-60) = 9e-27, far below the round-off floor, so the
        # run has genuinely converged and the residual below is not a truncated decay.
        end_time = 60.0 * tau
        history = self.aquifer.influx_history(
            times_days=[0.0, end_time], reservoir_pressure_psia=[boundary, boundary]
        )
        wei = self.aquifer.maximum_influx_bbl()
        # The converged influx is ct*Wi*(p_i - p_wf) = Wei*(1 - p_wf/p_i), so the gap to
        # Wei is the pressure ratio itself plus the unconverged exponential remainder
        # plus a few roundings. Each term is known before the comparison.
        tolerance = pressure_ratio + math.exp(-60.0) + 8.0 * EPS
        self.assertLess(abs(history[-1].cumulative_influx_bbl / wei - 1.0), tolerance)
        # And the gap is not zero either: at a finite boundary pressure the influx is
        # strictly below Wei, which is the whole distinction being drawn.
        self.assertLess(history[-1].cumulative_influx_bbl, wei)
        self.assertGreater(abs(history[-1].cumulative_influx_bbl / wei - 1.0), 0.5 * pressure_ratio)
        # The same limit taken at an ordinary boundary pressure: five sixths of Wei is
        # still unreachable at 2500 psia, so Wei is not a producible volume.
        sustained = self.aquifer.sustained_influx_limit_bbl(2500.0)
        settled = self.aquifer.influx_history(
            times_days=[0.0, end_time], reservoir_pressure_psia=[2500.0, 2500.0]
        )
        self.assertLess(
            abs(settled[-1].cumulative_influx_bbl / sustained - 1.0),
            math.exp(-60.0) + 8.0 * EPS,
        )
        self.assertLess(sustained, wei / 5.0)


class IndependentAlgorithmTests(unittest.TestCase):
    """The recursion against a fourth-order Runge-Kutta integration of the same equation.

    The oracle here is an algorithm, not a number: RK4 on dWe/dt with a continuous
    pressure history. It converges to the same solution by an entirely different route,
    so agreement is evidence about the recursion rather than about a stored value.
    """

    END_TIME = 3650.0

    def setUp(self) -> None:
        self.aquifer = reference_aquifer()

    @staticmethod
    def boundary_pressure(time_days: float) -> float:
        """Return a smooth declining boundary pressure, 3000 psia falling to 2400."""
        return 3000.0 - 600.0 * (1.0 - math.exp(-time_days / 1000.0))

    def fetkovich_influx(self, steps: int) -> float:
        times = [self.END_TIME * i / steps for i in range(steps + 1)]
        history = self.aquifer.influx_history(
            times_days=times,
            reservoir_pressure_psia=[self.boundary_pressure(t) for t in times],
        )
        return history[-1].cumulative_influx_bbl

    def test_agreement_with_runge_kutta(self):
        reference = runge_kutta_influx_bbl(
            self.aquifer,
            boundary_pressure=self.boundary_pressure,
            end_time_days=self.END_TIME,
            steps=36500,
        )
        # RK4 must first be shown to have converged, or the comparison below is between
        # two unknowns rather than against a reference.
        coarser = runge_kutta_influx_bbl(
            self.aquifer,
            boundary_pressure=self.boundary_pressure,
            end_time_days=self.END_TIME,
            steps=3650,
        )
        self.assertLess(abs(coarser / reference - 1.0), 1e-10)
        self.assertLess(abs(self.fetkovich_influx(3650) / reference - 1.0), 1e-6)
        self.assertGreater(
            abs(self.fetkovich_influx(365) / reference - 1.0),
            abs(self.fetkovich_influx(3650) / reference - 1.0),
        )


class TimestepRefinementTests(unittest.TestCase):
    """Observed order of convergence in the timestep.

    Two regimes, and the distinction matters for the claim this module makes:

    * With a boundary pressure that is constant over each interval, the scheme is the
      exact solution of its own equation and there is no timestep error at all to
      refine. That is asserted in :class:`ClosedFormLimitTests`.
    * With a continuously varying boundary pressure the only error left is the
      piecewise-constant representation of that pressure. The Eq. (8) mid-interval
      average is a midpoint rule, so the local error is third order and the global
      error second order in dt.

    Five grids give three Richardson triples, and on the grids below the observed order
    rises 1.920, 1.979, 1.995 as the finest step in the triple falls from 28.5 days to
    14.3 days to 7.1 days. The assertion is on the direction and on the rough
    magnitude, not on any one grid's number.
    """

    END_TIME = 3650.0
    COUNTS = (32, 64, 128, 256, 512)

    def setUp(self) -> None:
        self.aquifer = reference_aquifer()

    @staticmethod
    def boundary_pressure(time_days: float) -> float:
        return 3000.0 - 600.0 * (1.0 - math.exp(-time_days / 1000.0))

    def influx(self, steps: int) -> float:
        times = [self.END_TIME * i / steps for i in range(steps + 1)]
        history = self.aquifer.influx_history(
            times_days=times,
            reservoir_pressure_psia=[self.boundary_pressure(t) for t in times],
        )
        return history[-1].cumulative_influx_bbl

    def test_observed_order_is_second_order(self):
        values = [self.influx(count) for count in self.COUNTS]
        orders = [richardson_order(values[i - 2], values[i - 1], values[i]) for i in range(2, len(values))]
        for count, order in zip(self.COUNTS[2:], orders, strict=True):
            with self.subTest(steps=count):
                self.assertTrue(math.isfinite(order))
                self.assertGreater(order, 1.7)
                self.assertLess(order, 2.3)
        # The estimate must be settling on a value, not drifting.
        self.assertGreater(orders[-1], orders[0])
        self.assertLess(abs(orders[-1] - 2.0), 0.05)

    def test_successive_halving_converges(self):
        values = [self.influx(count) for count in self.COUNTS]
        gaps = [abs(fine - coarse) for coarse, fine in itertools.pairwise(values)]
        for coarse_gap, fine_gap in itertools.pairwise(gaps):
            self.assertLess(fine_gap, coarse_gap / 3.0)
        # Every refinement approaches the limit from the same side here, because the
        # midpoint rule under-resolves a convex pressure decline consistently.
        for coarse, fine in itertools.pairwise(values):
            self.assertGreater(fine, coarse)


class InvariantTests(unittest.TestCase):
    """Bounds, monotonicity, scaling and internal consistency.

    Contract C7 category 4 and nothing more. Two of these -- test_step_chaining_matches
    _history and test_records_are_internally_consistent -- compare the module against
    itself by construction: one checks that influx_history is step() applied in
    sequence, the other that a returned record satisfies Eq. (13) as the module
    evaluates it. They have real power against a transcription error that breaks one
    path and not the other, which is why they are here, but they are invariants and
    must not be counted towards the independent-oracle obligation. The oracles are
    PublishedWorkedExampleTests and IndependentAlgorithmTests.
    """

    def setUp(self) -> None:
        self.aquifer = reference_aquifer()
        self.storage = self.aquifer.total_compressibility_per_psi * self.aquifer.water_volume_bbl

    def test_sustained_drawdown_is_bounded(self):
        # Cumulative influx under a sustained drawdown is bounded above by
        # ct*Wi*(p_i - p), the asymptote of Eq. (5), and that bound is itself strictly
        # below Wei = ct*Wi*p_i. Both bounds are asserted at every step, including the
        # very long ones where the aquifer is essentially fully drained.
        boundary = 2400.0
        times = [0.0] + [10.0 * 2**i for i in range(14)]
        history = self.aquifer.influx_history(
            times_days=times, reservoir_pressure_psia=[boundary] * len(times)
        )
        bound = self.aquifer.sustained_influx_limit_bbl(boundary)
        self.assertLess(bound, self.aquifer.maximum_influx_bbl())
        for record in history:
            self.assertGreater(record.cumulative_influx_bbl, 0.0)
            # Less than or equal, not strictly less: the approach to the asymptote is
            # exponential, so after a few hundred time constants the running sum lands
            # on the bound exactly in floating point. Exceeding it would be the defect.
            self.assertLessEqual(record.cumulative_influx_bbl, bound)
            self.assertLess(record.cumulative_influx_bbl, self.aquifer.maximum_influx_bbl())
            self.assertGreaterEqual(record.aquifer_pressure_end_psia, boundary)
            self.assertLessEqual(record.aquifer_pressure_end_psia, 3000.0)
        # Early in the history the bound must be strict and far from tight, otherwise
        # the assertion above would be satisfied by an implementation that clamps.
        self.assertLess(history[0].cumulative_influx_bbl, 0.25 * bound)
        # A run several hundred time constants long must have converged onto the bound.
        self.assertAlmostEqual(history[-1].cumulative_influx_bbl / bound, 1.0, places=12)

    def test_coarse_steps_cannot_overshoot(self):
        # The decline factor lies in (0, 1] for any positive step, so a single step of
        # a thousand time constants still cannot push the aquifer past its asymptote.
        # There is no stability limit to respect. The interval is closed at the top and
        # the assertion says so: beyond dt/tau = 745 the factor is exactly 1.0 because
        # exp() has underflowed, which is a complete advance to the boundary pressure
        # and not an overshoot. test_decline_factor_saturates_at_one covers that end.
        boundary = 2400.0
        record = self.aquifer.step(
            aquifer_pressure_psia=3000.0,
            reservoir_pressure_psia=boundary,
            timestep_days=1.0e6,
        )
        self.assertGreater(record.decline_factor, 0.0)
        self.assertLessEqual(record.decline_factor, 1.0)
        self.assertLessEqual(record.cumulative_influx_bbl, self.aquifer.sustained_influx_limit_bbl(boundary))
        self.assertGreaterEqual(record.aquifer_pressure_end_psia, boundary)

    def test_decline_factor_saturates_at_one(self):
        # The documented interval is (0, 1], closed at the top, and this is the case
        # that closes it. 1 - exp(-x) rounds to exactly 1.0 once exp(-x) falls below
        # half an ulp of 1, i.e. below 2**-54, which happens at x = -log(2**-54) =
        # 37.43 -- long before exp() itself underflows at 745. The two steps below
        # bracket that threshold. Beyond it the aquifer lands exactly on the boundary
        # pressure. The earlier docstring claimed the open interval (0, 1), which is
        # false here, and only the weaker assertLessEqual in the test above kept the
        # suite green while the prose said otherwise.
        tau = self.aquifer.time_constant_days()
        below = self.aquifer.step(
            aquifer_pressure_psia=3000.0,
            reservoir_pressure_psia=2400.0,
            timestep_days=37.0 * tau,
        )
        self.assertLess(below.decline_factor, 1.0)
        self.assertGreater(below.decline_factor, 1.0 - 1e-12)
        saturated = self.aquifer.step(
            aquifer_pressure_psia=3000.0,
            reservoir_pressure_psia=2400.0,
            timestep_days=38.0 * tau,
        )
        self.assertEqual(saturated.decline_factor, 1.0)
        self.assertEqual(saturated.aquifer_pressure_end_psia, 2400.0)
        self.assertEqual(saturated.cumulative_influx_bbl, self.aquifer.sustained_influx_limit_bbl(2400.0))

    def test_larger_pressure_drop_gives_more_influx(self):
        influxes = []
        for boundary in (2950.0, 2800.0, 2500.0, 2000.0, 1000.0, 100.0):
            record = self.aquifer.step(
                aquifer_pressure_psia=3000.0,
                reservoir_pressure_psia=boundary,
                timestep_days=90.0,
            )
            influxes.append(record.influx_increment_bbl)
        for smaller, larger in itertools.pairwise(influxes):
            self.assertGreater(larger, smaller)
        # Linear in the driving head, since Eq. (1) has the backpressure exponent n = 1.
        self.assertAlmostEqual(influxes[2] / influxes[1], 500.0 / 200.0, places=12)

    def test_longer_timestep_gives_more_influx(self):
        cumulative = [
            self.aquifer.step(
                aquifer_pressure_psia=3000.0,
                reservoir_pressure_psia=2500.0,
                timestep_days=timestep,
            ).influx_increment_bbl
            for timestep in (1.0, 10.0, 100.0, 1000.0)
        ]
        for shorter, longer in itertools.pairwise(cumulative):
            self.assertGreater(longer, shorter)

    def test_influx_scales_with_storage_at_fixed_time_constant(self):
        # Doubling both ct*Wi and J leaves tau unchanged, so the response shape is
        # identical and the influx simply doubles. A dimensional error in the exponent
        # would break this, because the exponent would then carry a scale.
        doubled = FetkovichAquifer(
            initial_pressure_psia=self.aquifer.initial_pressure_psia,
            water_volume_bbl=self.aquifer.water_volume_bbl * 2.0,
            total_compressibility_per_psi=self.aquifer.total_compressibility_per_psi,
            productivity_index_bbl_per_day_psi=(self.aquifer.productivity_index_bbl_per_day_psi * 2.0),
        )
        self.assertAlmostEqual(
            doubled.time_constant_days() / self.aquifer.time_constant_days(), 1.0, places=15
        )
        kwargs = dict(aquifer_pressure_psia=2900.0, reservoir_pressure_psia=2600.0, timestep_days=45.0)
        ratio = doubled.step(**kwargs).influx_increment_bbl / self.aquifer.step(**kwargs).influx_increment_bbl
        self.assertAlmostEqual(ratio, 2.0, places=12)

    def test_time_constant_does_not_depend_on_initial_pressure(self):
        # The p_i cancellation in tau = Wei/(J*p_i) = ct*Wi/J. If a transcription error
        # left an initial pressure in the exponent, this is where it would surface.
        other = FetkovichAquifer(
            initial_pressure_psia=self.aquifer.initial_pressure_psia * 3.7,
            water_volume_bbl=self.aquifer.water_volume_bbl,
            total_compressibility_per_psi=self.aquifer.total_compressibility_per_psi,
            productivity_index_bbl_per_day_psi=(self.aquifer.productivity_index_bbl_per_day_psi),
        )
        self.assertEqual(other.time_constant_days(), self.aquifer.time_constant_days())
        self.assertAlmostEqual(
            self.aquifer.time_constant_days(),
            self.aquifer.maximum_influx_bbl()
            / (self.aquifer.productivity_index_bbl_per_day_psi * self.aquifer.initial_pressure_psia),
            places=9,
        )

    def test_records_are_internally_consistent(self):
        times = [0.0, 60.0, 200.0, 700.0, 1500.0, 3000.0]
        pressures = [3000.0, 2900.0, 2750.0, 2600.0, 2480.0, 2400.0]
        history = self.aquifer.influx_history(times_days=times, reservoir_pressure_psia=pressures)
        running = 0.0
        previous_end = self.aquifer.initial_pressure_psia
        for index, record in enumerate(history):
            running += record.influx_increment_bbl
            with self.subTest(step=index + 1):
                self.assertAlmostEqual(record.cumulative_influx_bbl, running, places=6)
                self.assertEqual(record.aquifer_pressure_start_psia, previous_end)
                self.assertEqual(record.time_days, times[index + 1])
                self.assertAlmostEqual(record.timestep_days, times[index + 1] - times[index], places=12)
                # Eq. (13) must hold on the record itself, not merely inside the loop.
                self.assertAlmostEqual(
                    self.aquifer.aquifer_pressure_psia(record.cumulative_influx_bbl),
                    record.aquifer_pressure_end_psia,
                    places=6,
                )
                self.assertAlmostEqual(
                    record.driving_head_psi(),
                    record.aquifer_pressure_start_psia - record.boundary_pressure_psia,
                    places=12,
                )
                self.assertEqual(record.method, FETKOVICH_METHOD)
                self.assertEqual(record.boundary_pressure_rule, BOUNDARY_RULE_EQ8_MIDPOINT)
                self.assertEqual(record.n_points, 2)
            previous_end = record.aquifer_pressure_end_psia

    def test_step_chaining_matches_history(self):
        # influx_history must be nothing more than step() applied in sequence with the
        # Eq. (8) averaging done for the caller.
        times = [0.0, 120.0, 365.0, 900.0]
        pressures = [3000.0, 2880.0, 2700.0, 2550.0]
        history = self.aquifer.influx_history(times_days=times, reservoir_pressure_psia=pressures)
        aquifer_pressure = self.aquifer.initial_pressure_psia
        for index, record in enumerate(history):
            manual = self.aquifer.step(
                aquifer_pressure_psia=aquifer_pressure,
                reservoir_pressure_psia=0.5 * (pressures[index] + pressures[index + 1]),
                timestep_days=times[index + 1] - times[index],
            )
            self.assertEqual(manual.influx_increment_bbl, record.influx_increment_bbl)
            # The increments are bit-identical; the cumulative figures differ in the
            # last ulp because step() reconstructs the prior influx from the aquifer
            # pressure while the history carries a running sum.
            self.assertAlmostEqual(manual.cumulative_influx_bbl, record.cumulative_influx_bbl, places=6)
            self.assertEqual(manual.n_points, 1)
            self.assertEqual(manual.boundary_pressure_rule, BOUNDARY_RULE_CALLER_SUPPLIED)
            aquifer_pressure = record.aquifer_pressure_end_psia

    def test_efflux_is_reported_signed(self):
        # A boundary pressure above the aquifer pressure drives water back into the
        # aquifer. Fetkovich's own nomenclature calls Eq. (1) a water influx or efflux
        # rate, so the negative increment is physical and is not clipped.
        record = self.aquifer.step(
            aquifer_pressure_psia=2800.0,
            reservoir_pressure_psia=2900.0,
            timestep_days=30.0,
        )
        self.assertLess(record.influx_increment_bbl, 0.0)
        self.assertGreater(record.aquifer_pressure_end_psia, 2800.0)

    def test_returns_a_tuple_not_a_list(self):
        history = self.aquifer.influx_history(
            times_days=[0.0, 30.0, 60.0], reservoir_pressure_psia=[3000.0, 2900.0, 2800.0]
        )
        self.assertIsInstance(history, tuple)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            history[0].influx_increment_bbl = 0.0


class InvalidInputTests(unittest.TestCase):
    """Every documented raise."""

    def setUp(self) -> None:
        self.aquifer = reference_aquifer()

    def test_construction_rejects_non_positive_and_non_finite_fields(self):
        base = dict(
            initial_pressure_psia=3000.0,
            water_volume_bbl=5.0e8,
            total_compressibility_per_psi=7.0e-6,
            productivity_index_bbl_per_day_psi=75.0,
        )
        for field in base:
            for bad in (0.0, -1.0, float("nan"), float("inf"), "bad", None):
                with self.subTest(field=field, bad=bad):
                    kwargs = dict(base, **{field: bad})
                    with self.assertRaises(InvalidInputError):
                        FetkovichAquifer(**kwargs)

    def test_construction_coerces_numeric_types_it_accepts(self):
        # The validators coerce as well as check, and a numeric string, a Decimal or a
        # Fraction all survive float(). Before the coercion was written back to the
        # frozen instance these constructed successfully and then failed with TypeError
        # -- not InvalidInputError -- at the first multiplication, which breaks contract
        # C3 in the worst way: the object reports itself as validated and is not.
        for value in ("3000", decimal.Decimal("3000"), fractions.Fraction(3000, 1), 3000):
            with self.subTest(value=value):
                aquifer = FetkovichAquifer(
                    initial_pressure_psia=value,
                    water_volume_bbl="5.3712e8",
                    total_compressibility_per_psi=decimal.Decimal("7e-6"),
                    productivity_index_bbl_per_day_psi=fractions.Fraction(7489, 100),
                )
                for field in dataclasses.fields(aquifer):
                    self.assertIsInstance(getattr(aquifer, field.name), float)
                self.assertEqual(aquifer.initial_pressure_psia, 3000.0)
                # The arithmetic that used to raise TypeError.
                self.assertAlmostEqual(
                    aquifer.maximum_influx_bbl() / (3000.0 * 7.0e-6 * 5.3712e8), 1.0, places=12
                )
                record = aquifer.step(
                    aquifer_pressure_psia=3000.0,
                    reservoir_pressure_psia=2500.0,
                    timestep_days=30.0,
                )
                self.assertGreater(record.influx_increment_bbl, 0.0)

    def test_record_coerces_numeric_types_it_accepts(self):
        # AquiferStep is public and had the identical write-back gap.
        record = AquiferStep(
            time_days="30",
            timestep_days=decimal.Decimal("30"),
            boundary_pressure_psia="2500",
            aquifer_pressure_start_psia=fractions.Fraction(3000, 1),
            aquifer_pressure_end_psia="2990",
            influx_increment_bbl="1000",
            cumulative_influx_bbl="1000",
            decline_factor="0.5",
            boundary_pressure_rule=BOUNDARY_RULE_CALLER_SUPPLIED,
            method=FETKOVICH_METHOD,
            n_points=1,
        )
        for field in dataclasses.fields(record):
            if field.name in ("boundary_pressure_rule", "method", "n_points"):
                continue
            self.assertIsInstance(getattr(record, field.name), float)
        self.assertEqual(record.driving_head_psi(), 500.0)

    def test_construction_rejects_derived_groups_outside_the_representable_range(self):
        # Four individually valid fields whose product or quotient leaves the
        # representable range. Each of these used to construct successfully and then
        # fail later: the underflow cases with ZeroDivisionError out of
        # time_constant_days(), the overflow cases with an InvalidInputError blaming
        # aquifer_pressure_end_psia, an internal record field the caller never supplied.
        cases = {
            "storage underflows": (3000.0, 1e-200, 1e-200, 1.0),
            "storage overflows": (3000.0, 1e300, 1e300, 1.0),
            "wei overflows": (1e10, 1e150, 1e150, 1.0),
            "wei underflows": (1e-100, 1e-150, 1e-150, 1e-300),
            "tau underflows": (3000.0, 1e-300, 1.0, 1e300),
            "tau overflows": (3000.0, 1e300, 1.0, 1e-300),
        }
        for label, args in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(InvalidInputError) as caught:
                    FetkovichAquifer(*args)
                message = str(caught.exception)
                # C2: the message names the caller's own fields, not an internal one.
                self.assertIn("water_volume_bbl", message)
                self.assertIn("total_compressibility_per_psi", message)
                self.assertNotIn("aquifer_pressure_end_psia", message)

    def test_step_rejects_an_overflowing_driving_head(self):
        # The remaining overflow path once the constructor guards are in place: a
        # storativity and an initial pressure that are both fine, and a caller-supplied
        # aquifer pressure so far above them that ct*Wi*dp overflows. The raise must
        # name the two pressures the caller passed.
        aquifer = FetkovichAquifer(
            initial_pressure_psia=1e-100,
            water_volume_bbl=1e100,
            total_compressibility_per_psi=1e100,
            productivity_index_bbl_per_day_psi=1.0,
        )
        with self.assertRaises(InvalidInputError) as caught:
            aquifer.step(
                aquifer_pressure_psia=1e300,
                reservoir_pressure_psia=1.0,
                timestep_days=1e30,
            )
        message = str(caught.exception)
        self.assertIn("aquifer_pressure_psia", message)
        self.assertIn("reservoir_pressure_psia", message)

    def test_step_rejects_bad_arguments(self):
        good = dict(
            aquifer_pressure_psia=3000.0,
            reservoir_pressure_psia=2500.0,
            timestep_days=30.0,
        )
        for name in good:
            for bad in (0.0, -1.0, float("nan"), float("inf"), "bad"):
                with self.subTest(argument=name, bad=bad), self.assertRaises(InvalidInputError):
                    self.aquifer.step(**dict(good, **{name: bad}))

    def test_history_rejects_mismatched_lengths(self):
        with self.assertRaises(InvalidInputError):
            self.aquifer.influx_history(
                times_days=[0.0, 30.0, 60.0], reservoir_pressure_psia=[3000.0, 2900.0]
            )

    def test_history_rejects_a_single_sample(self):
        with self.assertRaises(InvalidInputError):
            self.aquifer.influx_history(times_days=[0.0], reservoir_pressure_psia=[3000.0])

    def test_history_rejects_non_monotonic_or_repeated_times(self):
        for times in ([0.0, 60.0, 30.0], [0.0, 30.0, 30.0], [0.0, -30.0]):
            with self.subTest(times=times), self.assertRaises(InvalidInputError):
                self.aquifer.influx_history(
                    times_days=times,
                    reservoir_pressure_psia=[3000.0] * len(times),
                )

    def test_history_rejects_non_finite_and_non_positive_pressures(self):
        for pressures in (
            [3000.0, float("nan")],
            [3000.0, float("inf")],
            [3000.0, 0.0],
            [3000.0, -2900.0],
        ):
            with self.subTest(pressures=pressures), self.assertRaises(InvalidInputError):
                self.aquifer.influx_history(times_days=[0.0, 30.0], reservoir_pressure_psia=pressures)

    def test_history_rejects_non_finite_times_and_non_iterables(self):
        with self.assertRaises(InvalidInputError):
            self.aquifer.influx_history(
                times_days=[0.0, float("nan")], reservoir_pressure_psia=[3000.0, 2900.0]
            )
        with self.assertRaises(InvalidInputError):
            self.aquifer.influx_history(times_days=42.0, reservoir_pressure_psia=[3000.0])

    def test_derived_quantity_guards(self):
        for bad in (0.0, -10.0, float("nan"), "bad"):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                self.aquifer.sustained_influx_limit_bbl(bad)
        for bad in (float("nan"), float("inf"), "bad"):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                self.aquifer.aquifer_pressure_psia(bad)

    def test_record_rejects_a_non_positive_timestep(self):
        fields = dict(
            time_days=0.0,
            timestep_days=0.0,
            boundary_pressure_psia=2500.0,
            aquifer_pressure_start_psia=3000.0,
            aquifer_pressure_end_psia=3000.0,
            influx_increment_bbl=0.0,
            cumulative_influx_bbl=0.0,
            decline_factor=0.0,
            boundary_pressure_rule=BOUNDARY_RULE_CALLER_SUPPLIED,
            method=FETKOVICH_METHOD,
            n_points=1,
        )
        with self.assertRaises(InvalidInputError):
            AquiferStep(**fields)


class EvidenceCardFixtureTests(unittest.TestCase):
    """Regression fixture from docs/evidence/aquifer.md, not a published oracle.

    These values came from the scratch implementation written while the evidence card
    was assembled. That implementation is independent of this module in the sense that
    it shares no code, but it is not a third party and it is not in print, so this class
    is a regression check on agreement between two private implementations rather than
    verification against a source. The published oracle is in
    :class:`PublishedWorkedExampleTests`.

    It is kept for one further reason. The card's adversarial review corrected the
    fixture's own stated diagnostic: the settled gap between the end-of-step aquifer
    pressure and the mid-interval boundary pressure is 0.0418 psi, not the 30.0418 psi
    originally written, which was the gap against the end-of-interval boundary pressure
    instead. The corrected form is what is asserted here.

    The decimal places asserted below are tight -- four places on numbers of order
    1.9e6 is 3e-11 relative -- and that tightness is warranted only because the
    recursion carries no truncation error for a boundary pressure held constant over
    the step, so there is nothing for a looser band to absorb. Read it as evidence that
    two independent arithmetic implementations agree, which is what it is, and not as
    evidence that either one is physically accurate to eleven digits.
    """

    def setUp(self) -> None:
        self.aquifer = reference_aquifer()

    def test_setup_quantities(self):
        self.assertAlmostEqual(self.aquifer.water_volume_bbl / 5.371200e8, 1.0, places=6)
        self.assertAlmostEqual(self.aquifer.productivity_index_bbl_per_day_psi / 74.890385, 1.0, places=7)
        self.assertAlmostEqual(self.aquifer.maximum_influx_bbl() / 1.127952e7, 1.0, places=6)
        self.assertAlmostEqual(self.aquifer.time_constant_days() / 50.2046, 1.0, places=6)

    def test_linear_pressure_ramp_trace(self):
        times = [365.0 * i for i in range(11)]
        pressures = [3000.0 - 60.0 * i for i in range(11)]
        history = self.aquifer.influx_history(times_days=times, reservoir_pressure_psia=pressures)
        expected_increment = (112716.71, 225511.86, 225590.36)
        for index, expected in enumerate(expected_increment):
            with self.subTest(step=index + 1):
                self.assertAlmostEqual(history[index].influx_increment_bbl, expected, places=2)
        self.assertAlmostEqual(history[0].aquifer_pressure_end_psia, 2970.0209, places=4)
        self.assertAlmostEqual(history[1].cumulative_influx_bbl, 338228.57, places=2)
        self.assertAlmostEqual(history[-1].cumulative_influx_bbl, 2142951.80, places=2)
        self.assertAlmostEqual(history[-1].aquifer_pressure_end_psia, 2430.0418, places=4)

    def test_settled_lag_behind_a_linear_ramp(self):
        times = [365.0 * i for i in range(11)]
        pressures = [3000.0 - 60.0 * i for i in range(11)]
        history = self.aquifer.influx_history(times_days=times, reservoir_pressure_psia=pressures)
        final = history[-1]
        self.assertAlmostEqual(
            final.aquifer_pressure_end_psia - final.boundary_pressure_psia, 0.0418, places=4
        )
        # The driving head the step actually saw, which settles one increment higher.
        self.assertAlmostEqual(final.driving_head_psi(), 60.0418, places=4)

    def test_constant_pressure_golden_values(self):
        boundary = 2500.0
        expected = {
            10.0: 339516.8171,
            50.0: 1185512.2635,
            100.0: 1623418.6405,
            365.0: 1878611.7885,
            3650.0: 1879920.0919,
        }
        for end_time, value in expected.items():
            with self.subTest(end_time=end_time):
                history = self.aquifer.influx_history(
                    times_days=[0.0, end_time], reservoir_pressure_psia=[boundary, boundary]
                )
                self.assertAlmostEqual(history[0].cumulative_influx_bbl, value, places=4)
        self.assertAlmostEqual(self.aquifer.sustained_influx_limit_bbl(boundary), 1879920.0919, places=4)


if __name__ == "__main__":
    unittest.main()

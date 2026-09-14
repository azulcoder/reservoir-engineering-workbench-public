"""Verification suite for :mod:`reservoir_lab.material_balance`.

The four contract categories (api_contract C7) map onto the test classes below:

* independent oracle -- Dake's Exercise 1.2 worked solution, Pletcher's SPE 75354
  two-cell simulation and Oklahoma Morrow field tables, an exact rational-arithmetic
  least-squares fit, a closed-form inverse-prediction standard error, and a Monte
  Carlo reference;
* limiting case -- noise-free straight lines, zero drawdown, zero compressibility,
  zero influx;
* invalid input -- every raise documented in the module;
* property or invariant -- dimensional scaling, metamorphic invariance of the
  standard-condition basis, monotonicity, and determinism.

Two of the oracles are deliberately adversarial. ``test_card_value_5_2941e_6_is_wrong``
pins the arithmetic of the effective compressibility against the value that circulates
with the Pletcher case and is wrong, and shows that using the wrong one misses every
published target of that paper. ``test_modified_roach_intercept_sign`` pins the sign of
both groups in the modified Roach intercept against an algebraic identity, and shows
that the commonly transcribed opposite-sign form gives the wrong magnitude and the
wrong sign.

Known verification gap, stated here rather than left for a reader to discover. Neither
Roach function has a published oracle. SPE 75354 Table 9 reports a one-cell Fetkovich
case with a conventional Roach slope of 1.042e-5 giving G = 96.0 Bcf, a modified slope
of 0.9853e-5 giving G = 101.5 Bcf and W = 629e6 reservoir bbl -- the one case in that
paper where the error is negative -- but those tabulated columns were not available
when this module was written. Until they are, the Roach tests below establish that the
two plots are algebraically consistent with the general balance and that their
intercept signs are right; they do not establish agreement with any published number.
"""

from __future__ import annotations

import itertools
import math
import random
import unittest
from dataclasses import FrozenInstanceError
from fractions import Fraction

from reservoir_lab import gas
from reservoir_lab import material_balance as mb
from reservoir_lab.errors import InvalidInputError, NotIdentifiableError

# ---------------------------------------------------------------------------
# Published fixtures
# ---------------------------------------------------------------------------

# Pletcher, SPE 75354, Tables 1-3. A two-cell Eclipse model: one gas tank plus a
# 100 percent water cell of equal pore volume, so the true gas in place is known
# exactly because the reservoir is a simulation rather than an estimate.
PLETCHER_TRUE_OGIP_SCF = 100.8e9
PLETCHER_PRESSURE_PSIA = (
    6411.0,
    5947.0,
    5509.0,
    5093.0,
    4697.0,
    4319.0,
    3957.0,
    3610.0,
    3276.0,
    2953.0,
    2638.0,
)
PLETCHER_Z = (
    1.1192,
    1.0890,
    1.0618,
    1.0374,
    1.0156,
    0.9966,
    0.9801,
    0.9663,
    0.9551,
    0.9467,
    0.9409,
)
PLETCHER_CUMULATIVE_SCF = tuple(
    value * 1.0e9
    for value in (
        0.0,
        5.475,
        10.950,
        16.425,
        21.900,
        27.375,
        32.850,
        38.325,
        43.800,
        49.275,
        54.750,
    )
)
PLETCHER_CW_PER_PSI = 3.0e-6
PLETCHER_CF_PER_PSI = 6.0e-6
PLETCHER_SWI = 0.15

# Pletcher, SPE 75354, Table 7. Oklahoma Morrow sand: four pressure points, no water
# production, and a p/Z plot that gives no hint of the aquifer that is actually there.
MORROW_PRESSURE_PSIA = (5482.0, 5099.0, 3818.0, 3016.0)
MORROW_Z = (1.0471, 0.9960, 0.8286, 0.7341)
MORROW_PUBLISHED_P_OVER_Z = (5235.0, 5119.0, 4608.0, 4108.0)
MORROW_CUMULATIVE_SCF = tuple(value * 1.0e3 for value in (0.0, 157000.0, 814000.0, 1350000.0))
MORROW_CW_PER_PSI = 3.0e-6
MORROW_CF_PER_PSI = 3.0e-6
MORROW_SWI = 0.3


def _pletcher_corrected_p_over_z(count: int, effective_compressibility: float) -> list[float]:
    """Ramagost-Farshad corrected ordinate for the first ``count`` Pletcher rows."""
    return [
        mb.ramagost_farshad_corrected_p_over_z(
            pressure_psia=PLETCHER_PRESSURE_PSIA[index],
            z_factor=PLETCHER_Z[index],
            initial_pressure_psia=PLETCHER_PRESSURE_PSIA[0],
            effective_compressibility_per_psi=effective_compressibility,
        )
        for index in range(count)
    ]


def _exact_balance_history(
    *,
    gas_in_place_scf: float,
    gas_fvf_initial_rcf_per_scf: float,
    water_compressibility_per_psi: float,
    formation_compressibility_per_psi: float,
    initial_water_saturation: float,
    aquifer_water_rcf: float,
    initial_pressure_psia: float,
    initial_z_factor: float,
    pressures: tuple[float, ...],
    z_factors: tuple[float, ...],
    produced_water_rcf: tuple[float, ...],
) -> list[dict[str, float]]:
    """Synthetic history that satisfies the general balance identically.

    Cumulative gas production is the *dependent* variable here: We, Efw and Eg are
    computed first and Gp is then solved from ``F = G(Eg + Efw) + We``. That inverts
    the direction every estimator runs in, which is what lets these fixtures catch a
    sign flip or a transposed term inside the module -- the helper writes ce out as its
    own expression and never calls the module to get it. A pot aquifer is assumed,
    ``We = (cw + cf) * W * (pi - p)``, which is what makes the modified Roach intercept
    constant.

    What it cannot catch, stated plainly because the inversion is easy to oversell: the
    helper restates the same physics, so a *grouping* of Efw misstated the same way in
    both places would still close the identity. That residual risk is covered from
    outside, by ``test_effective_compressibility_by_direct_arithmetic`` and
    ``test_dake_magnitude_check_on_the_rock_water_term``, which check ce against
    arithmetic written from the definition and against Dake's published 1.3 percent
    sensitivity. Neither of those routes through this helper.
    """
    ce = (water_compressibility_per_psi * initial_water_saturation + formation_compressibility_per_psi) / (
        1.0 - initial_water_saturation
    )
    initial_ratio = initial_pressure_psia / initial_z_factor
    rows = []
    for pressure, z_factor, water in zip(pressures, z_factors, produced_water_rcf, strict=True):
        drawdown = initial_pressure_psia - pressure
        gas_fvf = gas_fvf_initial_rcf_per_scf * initial_ratio / (pressure / z_factor)
        gas_expansion = gas_fvf - gas_fvf_initial_rcf_per_scf
        rock_water = gas_fvf_initial_rcf_per_scf * ce * drawdown
        influx = (water_compressibility_per_psi + formation_compressibility_per_psi) * (
            aquifer_water_rcf * drawdown
        )
        produced_gas = (gas_in_place_scf * (gas_expansion + rock_water) + influx - water) / gas_fvf
        rows.append(
            {
                "pressure_psia": pressure,
                "z_factor": z_factor,
                "gas_fvf_rcf_per_scf": gas_fvf,
                "cumulative_gas_scf": produced_gas,
                "produced_water_rcf": water,
                "water_influx_rcf": influx,
            }
        )
    return rows


#: A concrete instance of the above, reused by several tests. The pressure path and the
#: produced-water series are arbitrary on purpose: the identity must hold for any path.
EXACT_CASE = {
    "gas_in_place_scf": 100.0e9,
    "gas_fvf_initial_rcf_per_scf": 3.5e-3,
    "water_compressibility_per_psi": 3.0e-6,
    "formation_compressibility_per_psi": 6.0e-6,
    "initial_water_saturation": 0.15,
    "aquifer_water_rcf": 4.0e8,
    "initial_pressure_psia": 6000.0,
    "initial_z_factor": 1.10,
    "pressures": (6000.0, 5600.0, 5200.0, 4800.0, 4400.0, 4000.0, 3600.0, 3200.0),
    "z_factors": (1.10, 1.07, 1.045, 1.02, 1.00, 0.985, 0.972, 0.962),
    "produced_water_rcf": (0.0, 2.0e4, 6.0e4, 1.3e5, 2.2e5, 3.4e5, 5.0e5, 7.0e5),
}


def _line_through(x_values, y_values):
    """Slope and intercept of the line through the first and last point.

    Used only on data that lie on a line exactly, so that no least-squares code enters
    the assertion path.
    """
    slope = (y_values[-1] - y_values[0]) / (x_values[-1] - x_values[0])
    return slope, y_values[0] - slope * x_values[0]


# ---------------------------------------------------------------------------
# 1. Independent oracle
# ---------------------------------------------------------------------------


class TestIndependentOracle(unittest.TestCase):
    """Values from published worked examples and from closed forms."""

    def test_p_over_z_reproduces_pletcher_table_7_column(self):
        # Table 7 prints p, Z and p/Z as separate columns, so the p/Z column is a
        # published check on the division rather than something derived here.
        for pressure, z_factor, published in zip(
            MORROW_PRESSURE_PSIA, MORROW_Z, MORROW_PUBLISHED_P_OVER_Z, strict=True
        ):
            with self.subTest(pressure=pressure):
                self.assertAlmostEqual(mb.p_over_z(pressure, z_factor), published, delta=0.5)

    def test_volumetric_gas_in_place_matches_dake_exercise_1_2(self):
        # Dake, Fundamentals of Reservoir Engineering, Exercise 1.2 and its solution.
        # Net bulk volume 1.776e10 cu ft, porosity 0.19, connate water 0.20, and at the
        # centroid depth p = 4290 psia, Z = 0.887, T = 660 degR.
        #
        # The basis has to be pinned. Dake's E = 35.37 p/(Z T) is Tsc/psc with
        # Tsc = 520 degR and psc = 14.7 psia (that is, 60 degF on the +460 offset), NOT
        # 519.67/14.696. The two differ in the fourth significant figure of G, and only
        # the first reproduces the published answer -- see the companion assertion
        # below.
        expansion_factor_scf_per_rcf = 35.37 * 4290.0 / (0.887 * 660.0)
        self.assertAlmostEqual(expansion_factor_scf_per_rcf, 259.1939, places=3)

        thickness_ft = 200.0
        bulk_volume_cuft = 1.776e10
        area_acres = bulk_volume_cuft / (mb.ACRE_IN_SQUARE_FEET * thickness_ft)

        gas_in_place = mb.volumetric_gas_in_place_scf(
            area_acres=area_acres,
            thickness_ft=thickness_ft,
            porosity=0.19,
            water_saturation=0.20,
            gas_fvf_rcf_per_scf=1.0 / expansion_factor_scf_per_rcf,
        )
        self.assertAlmostEqual(gas_in_place / 699.70e9, 1.0, delta=1.0e-5)

    def test_dake_basis_is_load_bearing_for_the_published_figure(self):
        # The correction that says the textbook trio 0.02827 / 0.005035 / 35.37 all come
        # from 14.7 psia and 520 degR, not from 14.696 and 519.67. Using the latter here
        # fails Dake's own answer at the fourth significant figure, so a test that quotes
        # 699.70e9 has to pin the basis rather than inherit a default.
        common = dict(thickness_ft=200.0, porosity=0.19, water_saturation=0.20)
        area_acres = 1.776e10 / (mb.ACRE_IN_SQUARE_FEET * 200.0)
        dake_basis = mb.volumetric_gas_in_place_scf(
            area_acres=area_acres,
            gas_fvf_rcf_per_scf=(0.887 * 660.0) / (35.37 * 4290.0),
            **common,
        )
        spe_basis = mb.volumetric_gas_in_place_scf(
            area_acres=area_acres,
            gas_fvf_rcf_per_scf=(0.887 * 660.0) / ((519.67 / 14.696) * 4290.0),
            **common,
        )
        self.assertAlmostEqual(dake_basis / 699.70e9, 1.0, delta=1.0e-5)
        # Threshold fixed by what the claim is, not by what the number turned out to
        # be: Dake prints G to five significant figures (699.70e9), so "the basis is
        # load-bearing" means the wrong basis must move G at or before the fourth
        # significant figure, that is by more than 1e-4 relative. Anything tighter
        # would be reverse-engineered from the computed 2.47e-4.
        self.assertGreater(abs(spe_basis / 699.70e9 - 1.0), 1.0e-4)

    def test_effective_compressibility_by_direct_arithmetic(self):
        # (cw*Swi + cf)/(1 - Swi) = (3e-6*0.15 + 6e-6)/0.85 = 6.45e-6/0.85, worked out
        # here from the numbers rather than taken from the module.
        expected = (3.0e-6 * 0.15 + 6.0e-6) / (1.0 - 0.15)
        self.assertAlmostEqual(expected, 7.588235294117647e-6, places=15)
        computed = mb.effective_compressibility_per_psi(
            water_compressibility_per_psi=PLETCHER_CW_PER_PSI,
            formation_compressibility_per_psi=PLETCHER_CF_PER_PSI,
            initial_water_saturation=PLETCHER_SWI,
        )
        self.assertAlmostEqual(computed, expected, delta=1.0e-18)
        # 7.5882e-6 is the same quantity quoted to five significant figures, so the
        # only tolerance it can carry is half a unit in its last printed place:
        # 0.5 * 1e-10 = 5e-11. That bound is set by the rounding of the printed value,
        # not by the computed deviation.
        self.assertAlmostEqual(computed, 7.5882e-6, delta=5.0e-11)

    def test_card_value_5_2941e_6_is_wrong(self):
        # A value of 5.2941e-6 /psi circulates alongside this exact case. It is
        # 6.45e-6 divided by 1.2186, not by 0.85. Two independent demonstrations that
        # it is wrong: the arithmetic, and the fact that it misses every published
        # target of the paper it is attached to.
        correct = mb.effective_compressibility_per_psi(
            water_compressibility_per_psi=PLETCHER_CW_PER_PSI,
            formation_compressibility_per_psi=PLETCHER_CF_PER_PSI,
            initial_water_saturation=PLETCHER_SWI,
        )
        self.assertGreater(abs(correct - 5.2941e-6), 2.0e-6)

        wrong = 5.2941e-6
        published = (109.0e9, 107.3e9, 104.8e9)
        for count, target in zip((3, 6, 11), published, strict=True):
            with self.subTest(points=count):
                good = mb.fit_pz_depletion(
                    PLETCHER_CUMULATIVE_SCF[:count], _pletcher_corrected_p_over_z(count, correct)
                ).gas_in_place_scf
                bad = mb.fit_pz_depletion(
                    PLETCHER_CUMULATIVE_SCF[:count], _pletcher_corrected_p_over_z(count, wrong)
                ).gas_in_place_scf
                self.assertAlmostEqual(good / target, 1.0, delta=5.0e-4)
                self.assertGreater(abs(bad / target - 1.0), 5.0e-3)

    def test_dake_magnitude_check_on_the_rock_water_term(self):
        # Dake's own sensitivity: cw = 3e-6, cf = 10e-6, Swc = 0.2, dp = 1000 psi alters
        # the balance by 1.3 percent. The exact value is 0.01325, which is why the check
        # is stated to four decimals and not to three.
        ce = mb.effective_compressibility_per_psi(
            water_compressibility_per_psi=3.0e-6,
            formation_compressibility_per_psi=10.0e-6,
            initial_water_saturation=0.2,
        )
        self.assertAlmostEqual(ce * 1000.0, 0.01325, places=7)

    def test_pletcher_two_cell_modified_p_over_z_matches_published_ogip(self):
        # SPE 75354 Table 4: 109.0 / 107.3 / 104.8 Bcf at 2, 5 and 10 years, against a
        # simulator truth of 100.8 Bcf. The point of the fixture is that the fit is
        # excellent and the answer is still wrong.
        ce = mb.effective_compressibility_per_psi(
            water_compressibility_per_psi=PLETCHER_CW_PER_PSI,
            formation_compressibility_per_psi=PLETCHER_CF_PER_PSI,
            initial_water_saturation=PLETCHER_SWI,
        )
        published = {3: 109.0e9, 6: 107.3e9, 11: 104.8e9}
        for count, target in published.items():
            with self.subTest(years=count - 1):
                fit = mb.fit_pz_depletion(
                    PLETCHER_CUMULATIVE_SCF[:count], _pletcher_corrected_p_over_z(count, ce)
                )
                self.assertAlmostEqual(fit.gas_in_place_scf / target, 1.0, delta=5.0e-4)
                self.assertGreater(fit.gas_in_place_scf, PLETCHER_TRUE_OGIP_SCF)

        ten_year = mb.fit_pz_depletion(PLETCHER_CUMULATIVE_SCF, _pletcher_corrected_p_over_z(11, ce))
        self.assertAlmostEqual(ten_year.r_squared, 0.9998, places=4)
        # R-squared of 0.9998 sitting next to a 4 percent overestimate is the whole
        # lesson of the fixture, and the result object has to say so.
        self.assertTrue(
            any(
                note.startswith("linearity_is_not_evidence_of_volumetric_drive") for note in ten_year.warnings
            )
        )
        self.assertAlmostEqual(ten_year.gas_in_place_scf / PLETCHER_TRUE_OGIP_SCF - 1.0, 0.040, delta=0.002)

    def test_pletcher_two_cell_uncorrected_p_over_z(self):
        # The same data plotted the way most practitioners actually plot them: no
        # compaction correction at all. The error compounds to 15.3 percent at 11
        # percent recovery. These three figures are not printed in the paper; they are
        # recomputed from its published tables.
        published = {3: 116.2e9, 6: 112.7e9, 11: 107.9e9}
        for count, target in published.items():
            with self.subTest(years=count - 1):
                ordinate = [mb.p_over_z(PLETCHER_PRESSURE_PSIA[i], PLETCHER_Z[i]) for i in range(count)]
                fit = mb.fit_pz_depletion(PLETCHER_CUMULATIVE_SCF[:count], ordinate)
                self.assertAlmostEqual(fit.gas_in_place_scf / target, 1.0, delta=1.0e-3)

    def test_oklahoma_morrow_field_case(self):
        # SPE 75354 Table 7 and surrounding text: conventional p/Z gives 6.32 Bcf and the
        # compaction-corrected p/Z gives 6.02 Bcf, against a pot-aquifer solution of
        # 5.44 Bcf. Four points, real field data, and no water production to warn anyone.
        conventional = mb.fit_pz_depletion(
            MORROW_CUMULATIVE_SCF,
            [mb.p_over_z(p, z) for p, z in zip(MORROW_PRESSURE_PSIA, MORROW_Z, strict=True)],
        )
        self.assertAlmostEqual(conventional.gas_in_place_scf / 1.0e9, 6.32, delta=0.01)

        ce = mb.effective_compressibility_per_psi(
            water_compressibility_per_psi=MORROW_CW_PER_PSI,
            formation_compressibility_per_psi=MORROW_CF_PER_PSI,
            initial_water_saturation=MORROW_SWI,
        )
        # Written out from the definition rather than pinned to a printed rounding.
        # The two expressions are the same arithmetic, so they must agree to round-off;
        # 1e-18 absolute on a quantity of 5.6e-6 is 2e-13 relative, about 800 machine
        # epsilons, which is a round-off gate and not a physical tolerance.
        self.assertAlmostEqual(ce, (3.0e-6 * 0.3 + 3.0e-6) / (1.0 - 0.3), delta=1.0e-18)
        # And separately against the five-significant-figure value printed alongside
        # the case, at half a unit in its last printed place.
        self.assertAlmostEqual(ce, 5.5714e-6, delta=5.0e-11)
        corrected = mb.fit_pz_depletion(
            MORROW_CUMULATIVE_SCF,
            [
                mb.ramagost_farshad_corrected_p_over_z(
                    pressure_psia=p,
                    z_factor=z,
                    initial_pressure_psia=MORROW_PRESSURE_PSIA[0],
                    effective_compressibility_per_psi=ce,
                )
                for p, z in zip(MORROW_PRESSURE_PSIA, MORROW_Z, strict=True)
            ],
        )
        self.assertAlmostEqual(corrected.gas_in_place_scf / 1.0e9, 6.02, delta=0.01)
        # Correcting for compaction moves G the right way but nowhere near far enough:
        # the published pot-aquifer answer is 5.44 Bcf.
        self.assertLess(corrected.gas_in_place_scf, conventional.gas_in_place_scf)
        self.assertGreater(corrected.gas_in_place_scf / 1.0e9, 5.44 * 1.09)

    def test_modified_roach_intercept_sign(self):
        # The sign oracle. On a history that satisfies the balance identically the
        # modified Roach points lie on a line exactly, so slope and intercept are read
        # off two points with no least squares anywhere in the assertion path.
        rows = _exact_balance_history(**EXACT_CASE)[1:]
        plot = mb.modified_roach_plot_coordinates(
            pressure_psia=[row["pressure_psia"] for row in rows],
            z_factor=[row["z_factor"] for row in rows],
            cumulative_gas_scf=[row["cumulative_gas_scf"] for row in rows],
            produced_water_rcf=[row["produced_water_rcf"] for row in rows],
            initial_pressure_psia=EXACT_CASE["initial_pressure_psia"],
            initial_z_factor=EXACT_CASE["initial_z_factor"],
            gas_fvf_initial_rcf_per_scf=EXACT_CASE["gas_fvf_initial_rcf_per_scf"],
        )
        slope, intercept = _line_through(plot.x, plot.y)

        # Every point must sit on that line, otherwise "the intercept" means nothing.
        for x_value, y_value in zip(plot.x, plot.y, strict=True):
            self.assertLess(abs(y_value - (slope * x_value + intercept)), 1.0e-15)

        self.assertAlmostEqual((1.0 / slope) / EXACT_CASE["gas_in_place_scf"], 1.0, delta=1.0e-12)

        ce = mb.effective_compressibility_per_psi(
            water_compressibility_per_psi=EXACT_CASE["water_compressibility_per_psi"],
            formation_compressibility_per_psi=EXACT_CASE["formation_compressibility_per_psi"],
            initial_water_saturation=EXACT_CASE["initial_water_saturation"],
        )
        aquifer_group = (
            (EXACT_CASE["water_compressibility_per_psi"] + EXACT_CASE["formation_compressibility_per_psi"])
            * EXACT_CASE["aquifer_water_rcf"]
            / (EXACT_CASE["gas_in_place_scf"] * EXACT_CASE["gas_fvf_initial_rcf_per_scf"])
        )
        # Corrected form: both groups added inside the bracket, whole bracket subtracted.
        expected = -(ce + aquifer_group)
        self.assertAlmostEqual(intercept / expected, 1.0, delta=1.0e-10)

        # The transcription that puts the aquifer group positive and the compressibility
        # group negative is wrong in both sign and magnitude, by a factor of about six.
        wrong_form = aquifer_group - ce
        self.assertGreater(wrong_form, 0.0)
        self.assertLess(expected, 0.0)
        self.assertGreater(abs(wrong_form - expected), 0.5 * abs(expected))

        # The module docstring for roach_plot_coordinates quotes this pair as the
        # demonstration that the plus-sign arrangement is wrong. Both numbers must come
        # from this one history or a reader cannot reproduce them; an earlier revision
        # paired +3.09e-6 from a different synthetic case with -1.79e-5 from this one,
        # and nothing caught it. Each tolerance is half a unit in the last place of the
        # three-significant-figure value as printed in the docstring.
        self.assertAlmostEqual(wrong_form, 2.70e-6, delta=5.0e-9)
        self.assertAlmostEqual(expected, -1.79e-5, delta=5.0e-8)
        # And the docstring itself, since that is where the mismatched pair lived. A
        # number quoted in prose so a reader can reproduce it has to be reproducible.
        docstring = mb.roach_plot_coordinates.__doc__
        if docstring is not None:  # stripped under python -OO
            self.assertIn("+2.70e-6", docstring)
            self.assertIn("-1.79e-5", docstring)

    def test_plain_roach_intercept_sign_and_published_slope_behaviour(self):
        # The plain Roach abscissa omits Wp*Bw/Bgi, which is correct for the equation as
        # published. The consequence, which an implementer needs to know, is that its
        # slope no longer returns G exactly once water production is non-trivial.
        rows = _exact_balance_history(**EXACT_CASE)[1:]
        plot = mb.roach_plot_coordinates(
            pressure_psia=[row["pressure_psia"] for row in rows],
            z_factor=[row["z_factor"] for row in rows],
            cumulative_gas_scf=[row["cumulative_gas_scf"] for row in rows],
            initial_pressure_psia=EXACT_CASE["initial_pressure_psia"],
            initial_z_factor=EXACT_CASE["initial_z_factor"],
        )
        slope, intercept = _line_through(plot.x, plot.y)
        recovered = 1.0 / slope
        self.assertLess(recovered, EXACT_CASE["gas_in_place_scf"])
        self.assertAlmostEqual(recovered / EXACT_CASE["gas_in_place_scf"], 1.0, delta=0.01)
        self.assertLess(intercept, 0.0)
        self.assertEqual(plot.variant, "roach")
        self.assertEqual(plot.n_points, len(rows))

    def test_gas_in_place_and_stderr_against_exact_rational_arithmetic(self):
        # A fully independent second computation of both G and its standard error. Every
        # quantity below is formed in exact rational arithmetic with fractions.Fraction
        # from the input data alone: the abscissa moments, the slope, the intercept, the
        # residuals, and the residual variance. Nothing is taken from the fit object, so
        # this reaches the whole path -- ols_line's coefficients and residuals as well
        # as the variance assembly in regression.x_intercept -- rather than only the
        # last stage of it.
        #
        # The standard error is reached through the inverse-prediction (calibration)
        # closed form
        #
        #   SE(x0) = (s / |m|) * sqrt(1/n + (x0 - xbar)^2 / Sxx)
        #
        # which never mentions Var(b) or Cov(m, b), so an implementation that dropped
        # the covariance term cannot satisfy it. The final assertion shows that the
        # dropped-covariance form really is a different number on this data.
        gas_in_place = 100.0e9
        initial = 5000.0
        slope = -initial / gas_in_place
        n_points = 11
        abscissa = [0.5 * gas_in_place * index / (n_points - 1) for index in range(n_points)]
        rng = random.Random(20260913)
        ordinate = [initial + slope * x + rng.gauss(0.0, 5.0) for x in abscissa]

        fit = mb.fit_pz_depletion(abscissa, ordinate)

        exact_x = [Fraction(value) for value in abscissa]
        exact_y = [Fraction(value) for value in ordinate]
        x_mean = sum(exact_x) / n_points
        y_mean = sum(exact_y) / n_points
        sxx = sum((x - x_mean) ** 2 for x in exact_x)
        sxy = sum((x - x_mean) * (y - y_mean) for x, y in zip(exact_x, exact_y, strict=True))
        exact_slope = sxy / sxx
        exact_intercept = y_mean - exact_slope * x_mean
        exact_residuals = [
            y - (exact_intercept + exact_slope * x) for x, y in zip(exact_x, exact_y, strict=True)
        ]
        residual_variance = sum(r * r for r in exact_residuals) / (n_points - 2)
        exact_gas_in_place = -exact_intercept / exact_slope
        exact_variance = (residual_variance / (exact_slope * exact_slope)) * (
            Fraction(1, n_points) + (exact_gas_in_place - x_mean) ** 2 / sxx
        )
        exact_stderr = math.sqrt(float(exact_variance))

        # Tolerances set from conditioning, before looking at the answer. The oracle is
        # exact up to the final float() conversion, so the only error is the module's
        # own double-precision round-off. The abscissa is non-negative and evenly
        # spaced, so forming (x - xbar) loses at most one bit, and the variance
        # expression is a handful of products and one square root: a few hundred
        # machine epsilons, 1e-13 relative, is the right order. A slope or covariance
        # defect would show up at 1e-2, eleven orders of magnitude above this gate.
        self.assertAlmostEqual(fit.gas_in_place_scf / float(exact_gas_in_place), 1.0, delta=1.0e-13)
        self.assertAlmostEqual(fit.slope / float(exact_slope), 1.0, delta=1.0e-13)
        self.assertAlmostEqual(fit.intercept / float(exact_intercept), 1.0, delta=1.0e-13)
        self.assertAlmostEqual(fit.gas_in_place_stderr_scf / exact_stderr, 1.0, delta=1.0e-13)
        for computed, reference in zip(fit.residuals, exact_residuals, strict=True):
            self.assertLess(abs(computed - float(reference)), 1.0e-9)

        # And the version that omits the covariance term, which the contract calls out
        # as wrong, is a visibly different number on the same data.
        without_covariance = math.sqrt(
            (fit.intercept_stderr**2 + fit.gas_in_place_scf**2 * fit.slope_stderr**2) / fit.slope**2
        )
        self.assertGreater(without_covariance / exact_stderr, 1.2)

    def test_gas_in_place_agrees_with_the_second_estimator_in_the_package(self):
        # reservoir_lab.gas.fit_volumetric_pz is a separate least-squares p/Z screen
        # that centres and rescales the abscissa before regressing, so it is a
        # different arithmetic path to the same estimate. fit_pz_depletion's own
        # comment says two least-squares implementations drift and that the one that
        # drifts is never the one under test; this is the assertion that would catch
        # the drift. It also fixes which module is authoritative: the agreement is
        # required, and material_balance is the one carrying the Monte Carlo reference
        # and the covariance-aware standard error.
        ordinate = [mb.p_over_z(p, z) for p, z in zip(PLETCHER_PRESSURE_PSIA, PLETCHER_Z, strict=True)]
        here = mb.fit_pz_depletion(PLETCHER_CUMULATIVE_SCF, ordinate)
        there = gas.fit_volumetric_pz(PLETCHER_CUMULATIVE_SCF, PLETCHER_PRESSURE_PSIA, PLETCHER_Z)
        # The rescaling in the other path changes the rounding but not the algebra, so
        # the two must agree to round-off. 1e-12 relative is a few thousand machine
        # epsilons, which is the room the change of variable can cost; a real
        # divergence between the two implementations would be far larger.
        self.assertAlmostEqual(here.gas_in_place_scf / there.giip_sm3, 1.0, delta=1.0e-12)
        self.assertAlmostEqual(here.slope / there.slope_pa_per_sm3, 1.0, delta=1.0e-12)
        self.assertAlmostEqual(here.r_squared, there.r_squared, delta=1.0e-12)

    def test_intercept_stderr_matches_monte_carlo(self):
        # Monte Carlo reference required by api_contract C6. Repeated noisy realisations
        # of one true line; the scatter of the fitted gas in place is compared against
        # the standard error the module reports for a single realisation.
        gas_in_place = 100.0e9
        initial = 5000.0
        slope = -initial / gas_in_place
        n_points = 11
        noise_std = 5.0
        abscissa = [0.5 * gas_in_place * index / (n_points - 1) for index in range(n_points)]

        rng = random.Random(4242)
        replicates = 4000
        estimates = []
        delta_method = []
        without_covariance = []
        for _ in range(replicates):
            ordinate = [initial + slope * x + rng.gauss(0.0, noise_std) for x in abscissa]
            fit = mb.fit_pz_depletion(abscissa, ordinate)
            estimates.append(fit.gas_in_place_scf)
            delta_method.append(fit.gas_in_place_stderr_scf)
            without_covariance.append(
                math.sqrt(
                    (fit.intercept_stderr**2 + fit.gas_in_place_scf**2 * fit.slope_stderr**2) / fit.slope**2
                )
            )

        mean = math.fsum(estimates) / replicates
        scatter = math.sqrt(math.fsum((value - mean) ** 2 for value in estimates) / (replicates - 1))
        mean_delta = math.fsum(delta_method) / replicates
        mean_naive = math.fsum(without_covariance) / replicates

        # Every gate here is a Monte Carlo error bar at this sample size, fixed before
        # the run. With R = 4000 replicates the sample mean of G has standard error
        # SE(G)/sqrt(R) ~ 1.22e8/63.2 = 1.9e6 scf, that is 1.9e-5 of G, so a 0.002
        # relative gate on the mean is about 100 sigma -- it tests that the estimator
        # is unbiased, not that the sampling is lucky.
        self.assertAlmostEqual(mean / gas_in_place, 1.0, delta=0.002)
        # The sample standard deviation of R draws has relative standard error
        # 1/sqrt(2R) = 1.1 percent. The delta method and the Monte Carlo scatter differ
        # systematically by Jensen's inequality on the estimated residual standard
        # deviation, an effect of order 1/(4*dof) = 2.8 percent here, so the gate is set
        # at 6 percent: wide enough to hold that known bias plus three Monte Carlo
        # sigmas, and narrow enough to exclude the naive form below, which sits 36
        # percent away.
        self.assertAlmostEqual(scatter / mean_delta, 1.0, delta=0.06)
        # Omitting the covariance term inflates the standard error by roughly a third.
        # The separation to test for is the predicted +36 percent; 1.25 and 0.85 are
        # that prediction with a wide margin, chosen so the assertion states a
        # qualitative separation rather than pinning the realised 1.36 and 0.75.
        self.assertGreater(mean_naive / mean_delta, 1.25)
        self.assertLess(scatter / mean_naive, 0.85)


# ---------------------------------------------------------------------------
# 2. Limiting case
# ---------------------------------------------------------------------------


class TestLimitingCase(unittest.TestCase):
    """Cases where the answer is known analytically."""

    def test_noise_free_line_recovers_gas_in_place_to_machine_precision(self):
        # The line is built from the physics, p/Z = (pi/Zi)(1 - Gp/G), not from a slope
        # and an intercept, so the construction does not share an expression with the
        # fit. Unevenly spaced abscissae, to avoid any accidental symmetry.
        gas_in_place = 87.36e9
        initial_p_over_z = 4923.7
        abscissa = [0.0, 3.1e9, 7.9e9, 12.4e9, 21.05e9, 29.6e9, 38.02e9]
        ordinate = [initial_p_over_z * (1.0 - x / gas_in_place) for x in abscissa]

        fit = mb.fit_pz_depletion(abscissa, ordinate)

        self.assertAlmostEqual(fit.gas_in_place_scf / gas_in_place, 1.0, delta=1.0e-12)
        self.assertAlmostEqual(fit.initial_p_over_z / initial_p_over_z, 1.0, delta=1.0e-12)
        # The former assertion that fit.intercept equals fit.initial_p_over_z has been
        # removed: both fields are assigned from the same local inside the module, so
        # it compared a value with itself and could not fail. The line above already
        # checks initial_p_over_z against the independently constructed truth, which is
        # the claim that was worth making.
        self.assertAlmostEqual(fit.observed_initial_p_over_z, initial_p_over_z, delta=1.0e-9)
        self.assertAlmostEqual(fit.r_squared, 1.0, delta=1.0e-14)
        self.assertLess(max(abs(r) for r in fit.residuals), 1.0e-9)
        self.assertLess(fit.gas_in_place_stderr_scf, 1.0e-3)
        self.assertEqual(fit.n_points, len(abscissa))
        self.assertEqual(fit.degrees_of_freedom, len(abscissa) - 2)
        self.assertEqual(fit.method, "ols")

    def test_general_balance_residual_vanishes_on_an_exact_history(self):
        rows = _exact_balance_history(**EXACT_CASE)
        withdrawal_scale = EXACT_CASE["gas_in_place_scf"] * EXACT_CASE["gas_fvf_initial_rcf_per_scf"]
        for index, row in enumerate(rows):
            with self.subTest(step=index):
                residual = mb.general_material_balance_residual(
                    gas_in_place_scf=EXACT_CASE["gas_in_place_scf"],
                    cumulative_gas_scf=row["cumulative_gas_scf"],
                    gas_fvf_rcf_per_scf=row["gas_fvf_rcf_per_scf"],
                    gas_fvf_initial_rcf_per_scf=EXACT_CASE["gas_fvf_initial_rcf_per_scf"],
                    water_compressibility_per_psi=EXACT_CASE["water_compressibility_per_psi"],
                    formation_compressibility_per_psi=EXACT_CASE["formation_compressibility_per_psi"],
                    initial_water_saturation=EXACT_CASE["initial_water_saturation"],
                    initial_pressure_psia=EXACT_CASE["initial_pressure_psia"],
                    pressure_psia=row["pressure_psia"],
                    water_influx_rcf=row["water_influx_rcf"],
                    cumulative_water_produced_stock_tank_cuft=row["produced_water_rcf"],
                    water_fvf_reservoir_per_stock_tank=1.0,
                )
                self.assertLess(abs(residual) / withdrawal_scale, 1.0e-14)

    def test_produced_water_enters_the_withdrawal_with_a_positive_sign(self):
        # Doubling Bw doubles the reservoir volume of produced water, which is on the
        # withdrawal side, so the residual must rise by exactly Wp*Bw.
        rows = _exact_balance_history(**EXACT_CASE)
        row = rows[-1]
        common = dict(
            gas_in_place_scf=EXACT_CASE["gas_in_place_scf"],
            cumulative_gas_scf=row["cumulative_gas_scf"],
            gas_fvf_rcf_per_scf=row["gas_fvf_rcf_per_scf"],
            gas_fvf_initial_rcf_per_scf=EXACT_CASE["gas_fvf_initial_rcf_per_scf"],
            water_compressibility_per_psi=EXACT_CASE["water_compressibility_per_psi"],
            formation_compressibility_per_psi=EXACT_CASE["formation_compressibility_per_psi"],
            initial_water_saturation=EXACT_CASE["initial_water_saturation"],
            initial_pressure_psia=EXACT_CASE["initial_pressure_psia"],
            pressure_psia=row["pressure_psia"],
            water_influx_rcf=row["water_influx_rcf"],
            cumulative_water_produced_stock_tank_cuft=row["produced_water_rcf"],
        )
        at_one = mb.general_material_balance_residual(water_fvf_reservoir_per_stock_tank=1.0, **common)
        at_two = mb.general_material_balance_residual(water_fvf_reservoir_per_stock_tank=2.0, **common)
        self.assertAlmostEqual(
            at_two - at_one, row["produced_water_rcf"], delta=1.0e-6 * row["produced_water_rcf"]
        )

    def test_water_influx_enters_the_expansion_side_with_a_negative_sign(self):
        rows = _exact_balance_history(**EXACT_CASE)
        row = rows[-1]
        common = dict(
            gas_in_place_scf=EXACT_CASE["gas_in_place_scf"],
            cumulative_gas_scf=row["cumulative_gas_scf"],
            gas_fvf_rcf_per_scf=row["gas_fvf_rcf_per_scf"],
            gas_fvf_initial_rcf_per_scf=EXACT_CASE["gas_fvf_initial_rcf_per_scf"],
            water_compressibility_per_psi=EXACT_CASE["water_compressibility_per_psi"],
            formation_compressibility_per_psi=EXACT_CASE["formation_compressibility_per_psi"],
            initial_water_saturation=EXACT_CASE["initial_water_saturation"],
            initial_pressure_psia=EXACT_CASE["initial_pressure_psia"],
            pressure_psia=row["pressure_psia"],
            cumulative_water_produced_stock_tank_cuft=row["produced_water_rcf"],
            water_fvf_reservoir_per_stock_tank=1.0,
        )
        with_influx = mb.general_material_balance_residual(water_influx_rcf=row["water_influx_rcf"], **common)
        without_influx = mb.general_material_balance_residual(water_influx_rcf=0.0, **common)
        self.assertAlmostEqual(
            without_influx - with_influx,
            row["water_influx_rcf"],
            delta=1.0e-6 * row["water_influx_rcf"],
        )

    def test_zero_drawdown_and_zero_compressibility_limits(self):
        term = mb.rock_water_expansion_term(
            gas_in_place_scf=1.0e10,
            gas_fvf_initial_rcf_per_scf=3.5e-3,
            water_compressibility_per_psi=3.0e-6,
            formation_compressibility_per_psi=6.0e-6,
            initial_water_saturation=0.15,
            initial_pressure_psia=5000.0,
            pressure_psia=5000.0,
        )
        self.assertEqual(term, 0.0)

        incompressible = mb.rock_water_expansion_term(
            gas_in_place_scf=1.0e10,
            gas_fvf_initial_rcf_per_scf=3.5e-3,
            water_compressibility_per_psi=0.0,
            formation_compressibility_per_psi=0.0,
            initial_water_saturation=0.15,
            initial_pressure_psia=5000.0,
            pressure_psia=3000.0,
        )
        self.assertEqual(incompressible, 0.0)

    def test_ramagost_farshad_with_zero_compressibility_is_the_raw_ratio(self):
        raw = mb.p_over_z(3016.0, 0.7341)
        corrected = mb.ramagost_farshad_corrected_p_over_z(
            pressure_psia=3016.0,
            z_factor=0.7341,
            initial_pressure_psia=5482.0,
            effective_compressibility_per_psi=0.0,
        )
        self.assertEqual(corrected, raw)

    def test_volumetric_depletion_limit_agrees_with_the_p_over_z_intercept(self):
        # We = 0, cw = cf = 0. The general balance then reduces to
        # Gp*Bg = G*(Bg - Bgi), and the same G must fall out of the p/Z x-intercept.
        # Two structurally different code paths, one answer.
        case = dict(EXACT_CASE)
        case["water_compressibility_per_psi"] = 0.0
        case["formation_compressibility_per_psi"] = 0.0
        case["aquifer_water_rcf"] = 0.0
        case["produced_water_rcf"] = tuple(0.0 for _ in EXACT_CASE["pressures"])
        rows = _exact_balance_history(**case)

        fit = mb.fit_pz_depletion(
            [row["cumulative_gas_scf"] for row in rows],
            [mb.p_over_z(row["pressure_psia"], row["z_factor"]) for row in rows],
        )
        self.assertAlmostEqual(fit.gas_in_place_scf / case["gas_in_place_scf"], 1.0, delta=1.0e-12)
        self.assertAlmostEqual(fit.r_squared, 1.0, delta=1.0e-14)

        for row in rows:
            residual = mb.general_material_balance_residual(
                gas_in_place_scf=case["gas_in_place_scf"],
                cumulative_gas_scf=row["cumulative_gas_scf"],
                gas_fvf_rcf_per_scf=row["gas_fvf_rcf_per_scf"],
                gas_fvf_initial_rcf_per_scf=case["gas_fvf_initial_rcf_per_scf"],
                water_compressibility_per_psi=0.0,
                formation_compressibility_per_psi=0.0,
                initial_water_saturation=case["initial_water_saturation"],
                initial_pressure_psia=case["initial_pressure_psia"],
                pressure_psia=row["pressure_psia"],
            )
            self.assertLess(
                abs(residual),
                1.0e-14 * case["gas_in_place_scf"] * case["gas_fvf_initial_rcf_per_scf"],
            )

    def test_remaining_gas_and_depletion_fraction_against_a_known_truth(self):
        # The former version of this test compared remaining_gas_scf() against
        # fit.gas_in_place_scf - max(Gp) and depletion_fraction_observed against
        # max(Gp) / fit.gas_in_place_scf. Both are the implementation's own definitions
        # rearranged, so neither could fail for any input the fit accepts. They are
        # replaced here by a comparison against a truth the test constructs and the
        # module never sees: a noise-free line built from p/Z = (pi/Zi)(1 - Gp/G) with
        # G fixed in advance. That makes the two reported quantities checkable, and it
        # also catches the wiring error the old version could not -- reading the first
        # cumulative value instead of the largest, or the observed initial p/Z instead
        # of the fitted intercept, changes both answers.
        gas_in_place = 87.36e9
        initial_p_over_z = 4923.7
        abscissa = [0.0, 3.1e9, 7.9e9, 12.4e9, 21.05e9, 29.6e9, 38.02e9]
        ordinate = [initial_p_over_z * (1.0 - x / gas_in_place) for x in abscissa]

        fit = mb.fit_pz_depletion(abscissa, ordinate)

        # Tolerance from conditioning: the fit recovers G from an exactly linear series
        # to within round-off, so every quantity below inherits a relative error of a
        # few hundred machine epsilons. 1e-10 relative is three orders of magnitude
        # looser than that and still far tighter than any wiring error, which would
        # move these numbers by tens of percent.
        self.assertAlmostEqual(fit.remaining_gas_scf() / (gas_in_place - abscissa[-1]), 1.0, delta=1.0e-10)
        self.assertAlmostEqual(
            fit.depletion_fraction_observed / (abscissa[-1] / gas_in_place),
            1.0,
            delta=1.0e-10,
        )
        # Produced plus remaining is the gas in place: the conservation identity the
        # pair of numbers is supposed to express.
        self.assertAlmostEqual((fit.remaining_gas_scf() + abscissa[-1]) / gas_in_place, 1.0, delta=1.0e-10)


# ---------------------------------------------------------------------------
# 3. Invalid input
# ---------------------------------------------------------------------------


class TestInvalidInput(unittest.TestCase):
    """Every raise documented in the module is exercised here."""

    def test_p_over_z_rejects_non_positive_and_non_finite(self):
        for pressure, z_factor in (
            (0.0, 0.9),
            (-100.0, 0.9),
            (2000.0, 0.0),
            (2000.0, -0.9),
            (math.nan, 0.9),
            (math.inf, 0.9),
            (2000.0, math.nan),
        ):
            with self.subTest(pressure=pressure, z=z_factor), self.assertRaises(InvalidInputError):
                mb.p_over_z(pressure, z_factor)

    def test_volumetric_gas_in_place_rejects_bad_geometry(self):
        good = dict(
            area_acres=640.0,
            thickness_ft=200.0,
            porosity=0.15,
            water_saturation=0.15,
            gas_fvf_rcf_per_scf=3.5e-3,
        )
        for field, value in (
            ("area_acres", 0.0),
            ("area_acres", -640.0),
            ("thickness_ft", 0.0),
            ("thickness_ft", math.nan),
            ("porosity", 0.0),
            # The docstring says "in (0, 1)", so the closed end is a documented raise
            # (api_contract C7.3). It used to be accepted: require_in_interval defaults
            # to inclusive bounds and only the zero end had an explicit guard.
            ("porosity", 1.0),
            ("porosity", 1.5),
            ("porosity", -0.1),
            ("water_saturation", 1.0),
            ("water_saturation", -0.05),
            ("water_saturation", 1.2),
            ("gas_fvf_rcf_per_scf", 0.0),
            ("gas_fvf_rcf_per_scf", -3.5e-3),
            ("gas_fvf_rcf_per_scf", math.inf),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(InvalidInputError):
                mb.volumetric_gas_in_place_scf(**{**good, field: value})

    def test_effective_compressibility_rejects_bad_arguments(self):
        good = dict(
            water_compressibility_per_psi=3.0e-6,
            formation_compressibility_per_psi=6.0e-6,
            initial_water_saturation=0.15,
        )
        for field, value in (
            ("water_compressibility_per_psi", -1.0e-6),
            ("formation_compressibility_per_psi", -1.0e-6),
            ("water_compressibility_per_psi", math.nan),
            ("initial_water_saturation", 1.0),
            ("initial_water_saturation", 1.4),
            ("initial_water_saturation", -0.1),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(InvalidInputError):
                mb.effective_compressibility_per_psi(**{**good, field: value})

    def test_rock_water_expansion_rejects_bad_arguments(self):
        good = dict(
            gas_in_place_scf=1.0e10,
            gas_fvf_initial_rcf_per_scf=3.5e-3,
            water_compressibility_per_psi=3.0e-6,
            formation_compressibility_per_psi=6.0e-6,
            initial_water_saturation=0.15,
            initial_pressure_psia=5000.0,
            pressure_psia=3000.0,
        )
        for field, value in (
            ("gas_in_place_scf", 0.0),
            ("gas_in_place_scf", -1.0e10),
            ("gas_fvf_initial_rcf_per_scf", 0.0),
            ("initial_pressure_psia", 0.0),
            ("pressure_psia", -10.0),
            ("pressure_psia", 6000.0),  # current above initial: transposed arguments
            ("initial_pressure_psia", math.nan),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(InvalidInputError):
                mb.rock_water_expansion_term(**{**good, field: value})

    def test_ramagost_farshad_asserts_rather_than_clamps(self):
        # ce*(pi - p) = 2e-5 * 60000 = 1.2, so the adjustment factor is -0.2. The
        # function must raise; returning a negative plotting term would produce a
        # plausible-looking plot from an invalid input.
        with self.assertRaises(InvalidInputError):
            mb.ramagost_farshad_corrected_p_over_z(
                pressure_psia=1000.0,
                z_factor=0.8,
                initial_pressure_psia=61000.0,
                effective_compressibility_per_psi=2.0e-5,
            )
        with self.assertRaises(InvalidInputError):
            mb.ramagost_farshad_corrected_p_over_z(
                pressure_psia=3000.0,
                z_factor=0.9,
                initial_pressure_psia=5000.0,
                effective_compressibility_per_psi=-1.0e-6,
            )
        with self.assertRaises(InvalidInputError):
            mb.ramagost_farshad_corrected_p_over_z(
                pressure_psia=6000.0,
                z_factor=0.9,
                initial_pressure_psia=5000.0,
                effective_compressibility_per_psi=1.0e-6,
            )

    def test_general_balance_rejects_bad_arguments(self):
        good = dict(
            gas_in_place_scf=1.0e11,
            cumulative_gas_scf=1.0e10,
            gas_fvf_rcf_per_scf=4.2e-3,
            gas_fvf_initial_rcf_per_scf=3.5e-3,
            water_compressibility_per_psi=3.0e-6,
            formation_compressibility_per_psi=6.0e-6,
            initial_water_saturation=0.15,
            initial_pressure_psia=6000.0,
            pressure_psia=4500.0,
            water_influx_rcf=1.0e6,
            cumulative_water_produced_stock_tank_cuft=5.0e4,
            water_fvf_reservoir_per_stock_tank=1.05,
        )
        for field, value in (
            ("gas_in_place_scf", 0.0),
            ("cumulative_gas_scf", -1.0),
            ("gas_fvf_rcf_per_scf", 0.0),
            ("gas_fvf_initial_rcf_per_scf", -1.0e-3),
            ("water_influx_rcf", -1.0),
            ("cumulative_water_produced_stock_tank_cuft", -1.0),
            ("water_fvf_reservoir_per_stock_tank", 0.0),
            ("water_fvf_reservoir_per_stock_tank", -1.05),
            ("water_compressibility_per_psi", -1.0e-6),
            ("formation_compressibility_per_psi", -1.0e-6),
            ("initial_water_saturation", 1.0),
            ("pressure_psia", 7000.0),
            ("pressure_psia", 0.0),
            ("cumulative_gas_scf", math.nan),
        ):
            with self.subTest(field=field, value=value), self.assertRaises(InvalidInputError):
                mb.general_material_balance_residual(**{**good, field: value})

    def test_fit_rejects_malformed_series(self):
        abscissa = [0.0, 1.0e10, 2.0e10, 3.0e10]
        ordinate = [5000.0, 4500.0, 4000.0, 3500.0]

        with self.assertRaises(InvalidInputError):
            mb.fit_pz_depletion(abscissa, ordinate[:3])
        with self.assertRaises(InvalidInputError):
            mb.fit_pz_depletion(abscissa[:2], ordinate[:2])
        with self.assertRaises(InvalidInputError):
            mb.fit_pz_depletion([0.0, 1.0e10, math.nan], [5000.0, 4500.0, 4000.0])
        with self.assertRaises(InvalidInputError):
            mb.fit_pz_depletion([0.0, 1.0e10, 2.0e10], [5000.0, 4500.0, math.inf])
        with self.assertRaises(InvalidInputError):
            mb.fit_pz_depletion([0.0, -1.0e10, 2.0e10], [5000.0, 4500.0, 4000.0])
        # Cumulative production that decreases is not sorted for the caller.
        with self.assertRaises(InvalidInputError):
            mb.fit_pz_depletion([0.0, 2.0e10, 1.0e10], [5000.0, 4500.0, 4000.0])
        with self.assertRaises(InvalidInputError):
            mb.fit_pz_depletion([0.0, 1.0e10, 2.0e10], [5000.0, 0.0, 4000.0])
        with self.assertRaises(InvalidInputError):
            mb.fit_pz_depletion([0.0, 1.0e10, 2.0e10], [5000.0, -4500.0, 4000.0])
        with self.assertRaises(InvalidInputError):
            mb.fit_pz_depletion(abscissa, ordinate, method="deming")
        with self.assertRaises(InvalidInputError):
            mb.fit_pz_depletion(abscissa, ordinate, weights=[1.0, 1.0, 1.0])
        with self.assertRaises(InvalidInputError):
            mb.fit_pz_depletion(abscissa, ordinate, weights=[1.0, 1.0, 0.0, 1.0])
        with self.assertRaises(InvalidInputError):
            mb.fit_pz_depletion(abscissa, ordinate, weights=[1.0, 1.0, -2.0, 1.0])
        with self.assertRaises(InvalidInputError):
            mb.fit_pz_depletion(abscissa, ordinate, weights=[1.0, 1.0, math.nan, 1.0])
        with self.assertRaises(InvalidInputError):
            mb.fit_pz_depletion(42, ordinate)

    def test_fit_raises_when_gas_in_place_is_not_identifiable(self):
        # No spread in cumulative production.
        with self.assertRaises(NotIdentifiableError):
            mb.fit_pz_depletion([1.0e10, 1.0e10, 1.0e10], [5000.0, 4900.0, 4800.0])
        # p/Z rising with production: no x-intercept to the right of the data.
        with self.assertRaises(NotIdentifiableError):
            mb.fit_pz_depletion([0.0, 1.0e10, 2.0e10], [4000.0, 4500.0, 5000.0])
        # Flat p/Z: slope zero.
        with self.assertRaises(NotIdentifiableError):
            mb.fit_pz_depletion([0.0, 1.0e10, 2.0e10], [4500.0, 4500.0, 4500.0])
        # A line steep enough that its x-intercept falls inside the observed data.
        with self.assertRaises(NotIdentifiableError):
            mb.fit_pz_depletion([0.0, 1.0e10, 2.0e10], [5000.0, 1000.0, 10.0])

    def test_roach_rejects_bad_series(self):
        pressures = [5600.0, 5200.0, 4800.0]
        z_factors = [1.07, 1.045, 1.02]
        produced = [4.7e9, 1.0e10, 1.55e10]
        good = dict(
            pressure_psia=pressures,
            z_factor=z_factors,
            cumulative_gas_scf=produced,
            initial_pressure_psia=6000.0,
            initial_z_factor=1.10,
        )
        with self.assertRaises(InvalidInputError):
            mb.roach_plot_coordinates(**{**good, "z_factor": z_factors[:2]})
        with self.assertRaises(InvalidInputError):
            mb.roach_plot_coordinates(**{**good, "cumulative_gas_scf": produced[:2]})
        with self.assertRaises(InvalidInputError):
            mb.roach_plot_coordinates(
                **{
                    **good,
                    "pressure_psia": [5600.0],
                    "z_factor": [1.07],
                    "cumulative_gas_scf": [4.7e9],
                }
            )
        with self.assertRaises(InvalidInputError):
            mb.roach_plot_coordinates(**{**good, "cumulative_gas_scf": [-1.0, 1.0e10, 1.55e10]})
        with self.assertRaises(InvalidInputError):
            mb.roach_plot_coordinates(**{**good, "z_factor": [0.0, 1.045, 1.02]})
        with self.assertRaises(InvalidInputError):
            mb.roach_plot_coordinates(**{**good, "pressure_psia": [math.nan, 5200.0, 4800.0]})
        # The initial point itself: pi - p is zero, so both axes are 0/0.
        with self.assertRaises(InvalidInputError):
            mb.roach_plot_coordinates(**{**good, "pressure_psia": [6000.0, 5200.0, 4800.0]})
        with self.assertRaises(InvalidInputError):
            mb.roach_plot_coordinates(**{**good, "initial_z_factor": 0.0})

    def test_no_public_function_returns_a_non_finite_value_on_overflow(self):
        # Every argument below is finite and individually plausible; it is the product
        # or the sum that leaves the double range. The module used to return inf from
        # the first two and let a bare builtins.ValueError out of math.fsum in the
        # third, neither of which is in the api_contract C3 table -- and because
        # InvalidInputError subclasses ValueError, a caller writing `except ValueError`
        # to mean "bad input" would have swallowed the fsum failure silently.
        with self.assertRaises(InvalidInputError):
            mb.volumetric_gas_in_place_scf(
                area_acres=1.0e300,
                thickness_ft=1.0e300,
                porosity=0.2,
                water_saturation=0.15,
                gas_fvf_rcf_per_scf=3.5e-3,
            )
        with self.assertRaises(InvalidInputError):
            mb.rock_water_expansion_term(
                gas_in_place_scf=1.0e300,
                gas_fvf_initial_rcf_per_scf=1.0e300,
                water_compressibility_per_psi=3.0e-6,
                formation_compressibility_per_psi=6.0e-6,
                initial_water_saturation=0.15,
                initial_pressure_psia=6000.0,
                pressure_psia=1000.0,
            )
        with self.assertRaises(InvalidInputError):
            mb.general_material_balance_residual(
                gas_in_place_scf=1.0e308,
                cumulative_gas_scf=1.0e308,
                gas_fvf_rcf_per_scf=10.0,
                gas_fvf_initial_rcf_per_scf=1.0,
                water_compressibility_per_psi=0.0,
                formation_compressibility_per_psi=0.0,
                initial_water_saturation=0.15,
                initial_pressure_psia=6000.0,
                pressure_psia=4500.0,
            )
        # The fit reaches the overflow inside reservoir_lab.regression, which raises a
        # bare OverflowError. That type is not in the C3 table either, so it is
        # translated at this module's boundary rather than allowed to escape.
        with self.assertRaises(InvalidInputError):
            mb.fit_pz_depletion(
                [0.0, 1.0e200, 2.0e200, 3.0e200],
                [5.0e200, 4.0e200, 3.0e200, 2.0001e200],
            )
        # And the Roach coordinates, which divide by (pi - p). math.nextafter gives the
        # smallest representable drawdown below 6000 psia, 9.1e-13 psi, which is a
        # legal strictly-below pressure and so passes the 0/0 guard; the abscissa still
        # overflows, and the returned series must not carry an inf.
        with self.assertRaises(InvalidInputError):
            mb.roach_plot_coordinates(
                pressure_psia=[math.nextafter(6000.0, 0.0), 5200.0],
                z_factor=[1.10, 1.045],
                cumulative_gas_scf=[1.0e300, 1.0e300],
                initial_pressure_psia=6000.0,
                initial_z_factor=1.10,
            )

    def test_p_over_z_rejects_an_underflow_to_zero(self):
        # Both arguments are strictly positive, so the true quotient is strictly
        # positive; 1e-300 / 1e300 is 1e-600, which is not representable and comes back
        # as exactly 0.0. Returning that would hand a fit an ordinate saying the
        # reservoir is fully depleted, which is a sentinel and not an answer.
        with self.assertRaises(InvalidInputError):
            mb.p_over_z(1.0e-300, 1.0e300)

    def test_modified_roach_rejects_bad_water_series(self):
        good = dict(
            pressure_psia=[5600.0, 5200.0, 4800.0],
            z_factor=[1.07, 1.045, 1.02],
            cumulative_gas_scf=[4.7e9, 1.0e10, 1.55e10],
            produced_water_rcf=[2.0e4, 6.0e4, 1.3e5],
            initial_pressure_psia=6000.0,
            initial_z_factor=1.10,
            gas_fvf_initial_rcf_per_scf=3.5e-3,
        )
        with self.assertRaises(InvalidInputError):
            mb.modified_roach_plot_coordinates(**{**good, "produced_water_rcf": [2.0e4, 6.0e4]})
        with self.assertRaises(InvalidInputError):
            mb.modified_roach_plot_coordinates(**{**good, "produced_water_rcf": [-1.0, 6.0e4, 1.3e5]})
        with self.assertRaises(InvalidInputError):
            mb.modified_roach_plot_coordinates(**{**good, "produced_water_rcf": [math.nan, 6.0e4, 1.3e5]})
        with self.assertRaises(InvalidInputError):
            mb.modified_roach_plot_coordinates(**{**good, "gas_fvf_initial_rcf_per_scf": 0.0})


# ---------------------------------------------------------------------------
# 4. Property and invariant
# ---------------------------------------------------------------------------


class TestPropertyAndInvariant(unittest.TestCase):
    """Scaling, metamorphic relations, monotonicity, determinism."""

    def test_volumetric_gas_in_place_scales_dimensionally(self):
        base = dict(
            area_acres=640.0,
            thickness_ft=200.0,
            porosity=0.15,
            water_saturation=0.15,
            gas_fvf_rcf_per_scf=3.5e-3,
        )
        reference = mb.volumetric_gas_in_place_scf(**base)
        self.assertAlmostEqual(
            mb.volumetric_gas_in_place_scf(**{**base, "area_acres": 1280.0}) / reference,
            2.0,
            delta=1.0e-12,
        )
        self.assertAlmostEqual(
            mb.volumetric_gas_in_place_scf(**{**base, "thickness_ft": 600.0}) / reference,
            3.0,
            delta=1.0e-12,
        )
        self.assertAlmostEqual(
            mb.volumetric_gas_in_place_scf(**{**base, "porosity": 0.30}) / reference,
            2.0,
            delta=1.0e-12,
        )
        self.assertAlmostEqual(
            mb.volumetric_gas_in_place_scf(**{**base, "gas_fvf_rcf_per_scf": 7.0e-3}) / reference,
            0.5,
            delta=1.0e-12,
        )
        # And the exact acre conversion, checked against the definition 66 ft x 660 ft.
        self.assertEqual(mb.ACRE_IN_SQUARE_FEET, 43560.0)

    def test_rock_water_term_is_linear_and_monotone_in_drawdown(self):
        common = dict(
            gas_in_place_scf=1.0e10,
            gas_fvf_initial_rcf_per_scf=3.5e-3,
            water_compressibility_per_psi=3.0e-6,
            formation_compressibility_per_psi=6.0e-6,
            initial_water_saturation=0.15,
            initial_pressure_psia=6000.0,
        )
        values = [
            mb.rock_water_expansion_term(pressure_psia=pressure, **common)
            for pressure in (6000.0, 5000.0, 4000.0, 3000.0, 2000.0)
        ]
        for earlier, later in itertools.pairwise(values):
            self.assertGreater(later, earlier)
        # Equal pressure steps give equal increments: the term is linear in (pi - p).
        increments = [later - earlier for earlier, later in itertools.pairwise(values)]
        for increment in increments[1:]:
            self.assertAlmostEqual(increment / increments[0], 1.0, delta=1.0e-12)
        # And linear in G.
        doubled = mb.rock_water_expansion_term(pressure_psia=3000.0, **{**common, "gas_in_place_scf": 2.0e10})
        self.assertAlmostEqual(doubled / values[3], 2.0, delta=1.0e-12)

    def test_residual_is_monotone_decreasing_in_the_candidate_gas_in_place(self):
        rows = _exact_balance_history(**EXACT_CASE)
        row = rows[-1]
        common = dict(
            cumulative_gas_scf=row["cumulative_gas_scf"],
            gas_fvf_rcf_per_scf=row["gas_fvf_rcf_per_scf"],
            gas_fvf_initial_rcf_per_scf=EXACT_CASE["gas_fvf_initial_rcf_per_scf"],
            water_compressibility_per_psi=EXACT_CASE["water_compressibility_per_psi"],
            formation_compressibility_per_psi=EXACT_CASE["formation_compressibility_per_psi"],
            initial_water_saturation=EXACT_CASE["initial_water_saturation"],
            initial_pressure_psia=EXACT_CASE["initial_pressure_psia"],
            pressure_psia=row["pressure_psia"],
            water_influx_rcf=row["water_influx_rcf"],
            cumulative_water_produced_stock_tank_cuft=row["produced_water_rcf"],
            water_fvf_reservoir_per_stock_tank=1.0,
        )
        true_g = EXACT_CASE["gas_in_place_scf"]
        residuals = [
            mb.general_material_balance_residual(gas_in_place_scf=factor * true_g, **common)
            for factor in (0.8, 0.9, 1.0, 1.1, 1.2)
        ]
        for earlier, later in itertools.pairwise(residuals):
            self.assertLess(later, earlier)
        self.assertGreater(residuals[0], 0.0)
        self.assertLess(residuals[-1], 0.0)

    def test_standard_condition_basis_is_a_uniform_scaling_of_the_balance(self):
        # The balance is homogeneous of degree one in reservoir volume. Re-declaring the
        # standard pressure rescales every Bg and every reservoir volume by one common
        # factor, so the residual must scale by exactly that factor and nothing else may
        # move. A hard-coded psc anywhere would break this.
        rows = _exact_balance_history(**EXACT_CASE)
        row = rows[-2]
        factor = 15.025 / 14.696
        base = dict(
            gas_in_place_scf=EXACT_CASE["gas_in_place_scf"] * 0.93,  # a wrong G, so the
            cumulative_gas_scf=row["cumulative_gas_scf"],  # residual is non-zero
            water_compressibility_per_psi=EXACT_CASE["water_compressibility_per_psi"],
            formation_compressibility_per_psi=EXACT_CASE["formation_compressibility_per_psi"],
            initial_water_saturation=EXACT_CASE["initial_water_saturation"],
            initial_pressure_psia=EXACT_CASE["initial_pressure_psia"],
            pressure_psia=row["pressure_psia"],
            water_fvf_reservoir_per_stock_tank=1.0,
        )
        first = mb.general_material_balance_residual(
            gas_fvf_rcf_per_scf=row["gas_fvf_rcf_per_scf"],
            gas_fvf_initial_rcf_per_scf=EXACT_CASE["gas_fvf_initial_rcf_per_scf"],
            water_influx_rcf=row["water_influx_rcf"],
            cumulative_water_produced_stock_tank_cuft=row["produced_water_rcf"],
            **base,
        )
        second = mb.general_material_balance_residual(
            gas_fvf_rcf_per_scf=row["gas_fvf_rcf_per_scf"] * factor,
            gas_fvf_initial_rcf_per_scf=EXACT_CASE["gas_fvf_initial_rcf_per_scf"] * factor,
            water_influx_rcf=row["water_influx_rcf"] * factor,
            cumulative_water_produced_stock_tank_cuft=row["produced_water_rcf"] * factor,
            **base,
        )
        self.assertNotAlmostEqual(first, 0.0)
        self.assertAlmostEqual(second / first, factor, delta=1.0e-12)

    def test_p_over_z_fit_is_metamorphic_under_rescaling(self):
        abscissa = [0.0, 5.0e9, 11.0e9, 18.0e9, 26.0e9]
        ordinate = [5000.0, 4700.0, 4340.0, 3920.0, 3450.0]
        reference = mb.fit_pz_depletion(abscissa, ordinate)

        # Rescaling the gas volume unit (scf to Mscf, say) must scale G and its standard
        # error by the same factor and leave R-squared alone.
        volume_factor = 1.0e-3
        rescaled = mb.fit_pz_depletion([x * volume_factor for x in abscissa], ordinate)
        self.assertAlmostEqual(
            rescaled.gas_in_place_scf / (reference.gas_in_place_scf * volume_factor),
            1.0,
            delta=1.0e-12,
        )
        self.assertAlmostEqual(
            rescaled.gas_in_place_stderr_scf / (reference.gas_in_place_stderr_scf * volume_factor),
            1.0,
            delta=1.0e-12,
        )
        self.assertAlmostEqual(rescaled.r_squared, reference.r_squared, delta=1.0e-14)

        # Rescaling the ordinate (a different pressure unit, or a different standard
        # basis expressed through p/Z) must leave G untouched entirely.
        pressure_factor = 6.894757
        rescaled_y = mb.fit_pz_depletion(abscissa, [y * pressure_factor for y in ordinate])
        self.assertAlmostEqual(rescaled_y.gas_in_place_scf / reference.gas_in_place_scf, 1.0, delta=1.0e-13)
        self.assertAlmostEqual(
            rescaled_y.gas_in_place_stderr_scf / reference.gas_in_place_stderr_scf,
            1.0,
            delta=1.0e-13,
        )

    def test_extrapolation_uncertainty_grows_as_observed_depletion_shrinks(self):
        # Quantified comparison at equal pressure noise. The same noise realisation is
        # added in both cases, so the only thing that differs is how far the x-intercept
        # sits beyond the data.
        #
        # Closed form for the intercept standard error, SE = (s/|m|) * sqrt(1/n +
        # (x0 - xbar)^2 / Sxx), makes the ratio predictable without reference to any
        # implementation: with n evenly spaced points spanning a fraction f of G,
        # xbar = fG/2 and Sxx = 1.1 (fG)^2 at n = 11, so the bracket is
        # sqrt(1/11 + (1 - f/2)^2 / (1.1 f^2)) -- 9.06 at f = 0.1 and 1.46 at f = 0.5.
        gas_in_place = 100.0e9
        initial = 5000.0
        slope = -initial / gas_in_place
        n_points = 11
        rng = random.Random(31337)
        noise = [rng.gauss(0.0, 5.0) for _ in range(n_points)]

        results = {}
        theoretical = {}
        for fraction in (0.10, 0.50):
            abscissa = [fraction * gas_in_place * index / (n_points - 1) for index in range(n_points)]
            ordinate = [
                initial + slope * x + perturbation for x, perturbation in zip(abscissa, noise, strict=True)
            ]
            results[fraction] = mb.fit_pz_depletion(abscissa, ordinate)
            x_mean = math.fsum(abscissa) / n_points
            sxx = math.fsum((x - x_mean) ** 2 for x in abscissa)
            theoretical[fraction] = math.sqrt(1.0 / n_points + (gas_in_place - x_mean) ** 2 / sxx)

        observed_ratio = results[0.10].gas_in_place_stderr_scf / results[0.50].gas_in_place_stderr_scf
        predicted_ratio = theoretical[0.10] / theoretical[0.50]

        # The bracket is available in closed form, so it is derived here rather than
        # pinned to a value read off a previous run. For n evenly spaced points on
        # [0, fG], Sxx = (fG)^2 * n(n+1) / (12(n-1)) and xbar = fG/2, so
        #     bracket(f) = sqrt(1/n + (1 - f/2)^2 / (f^2 * n(n+1)/(12(n-1)))).
        # At n = 11 the Sxx coefficient is 11*12/(12*10) = 1.1 exactly. Both sides are
        # the same algebra evaluated two ways, so they must agree to round-off; 1e-12
        # relative is the round-off gate, not a fitted tolerance.
        def bracket(fraction):
            sxx_coefficient = n_points * (n_points + 1) / (12.0 * (n_points - 1))
            return math.sqrt(1.0 / n_points + (1.0 - fraction / 2.0) ** 2 / (fraction**2 * sxx_coefficient))

        self.assertAlmostEqual(predicted_ratio / (bracket(0.10) / bracket(0.50)), 1.0, delta=1.0e-12)
        self.assertGreater(observed_ratio, 1.0)
        self.assertGreater(observed_ratio, 4.0)
        self.assertLess(observed_ratio, 9.0)
        self.assertAlmostEqual(observed_ratio / predicted_ratio, 1.0, delta=0.20)

        # The weakly constrained fit says so; the better constrained one does not.
        self.assertTrue(any(note.startswith("weak_extrapolation") for note in results[0.10].warnings))
        self.assertFalse(any(note.startswith("weak_extrapolation") for note in results[0.50].warnings))
        # The two cases straddle the module's own threshold, which is what decides
        # which of them carries the note. Reading the constant rather than repeating
        # its value keeps the test and the module from drifting apart.
        self.assertLess(results[0.10].depletion_fraction_observed, mb.DEPLETION_FRACTION_WARNING_THRESHOLD)
        self.assertGreater(results[0.50].depletion_fraction_observed, mb.DEPLETION_FRACTION_WARNING_THRESHOLD)

    def test_warnings_flag_a_weakly_constrained_intercept(self):
        # The large_intercept_uncertainty branch and RELATIVE_STDERR_WARNING_THRESHOLD
        # were reachable but unreached: no test in the suite exercised either. The
        # residuals below are written out rather than drawn from an RNG, so the
        # standard error is a deterministic function of the fixture and the branch
        # cannot start or stop firing because a seed changed.
        gas_in_place = 100.0e9
        initial = 5000.0
        slope = -initial / gas_in_place
        n_points = 11
        residuals = [40.0, -55.0, 30.0, -20.0, 60.0, -45.0, 25.0, -35.0, 50.0, -30.0, 15.0]

        def fit_at(fraction):
            abscissa = [fraction * gas_in_place * index / (n_points - 1) for index in range(n_points)]
            ordinate = [
                initial + slope * x + residual for x, residual in zip(abscissa, residuals, strict=True)
            ]
            return mb.fit_pz_depletion(abscissa, ordinate)

        # Five percent of the gas produced: the same scatter, extrapolated ten times as
        # far, puts the one-sigma band at roughly a sixth of G.
        weak = fit_at(0.05)
        self.assertGreater(
            weak.gas_in_place_stderr_scf,
            mb.RELATIVE_STDERR_WARNING_THRESHOLD * weak.gas_in_place_scf,
        )
        self.assertTrue(any(note.startswith("large_intercept_uncertainty") for note in weak.warnings))

        # Thirty percent produced, identical scatter: the band falls below the
        # threshold and the note must disappear. Without this half the test would pass
        # against an implementation that emitted the note unconditionally.
        firm = fit_at(0.30)
        self.assertLess(
            firm.gas_in_place_stderr_scf,
            mb.RELATIVE_STDERR_WARNING_THRESHOLD * firm.gas_in_place_scf,
        )
        self.assertFalse(any(note.startswith("large_intercept_uncertainty") for note in firm.warnings))

    def test_warnings_flag_a_missing_zero_production_point(self):
        abscissa = [5.0e9, 11.0e9, 18.0e9, 26.0e9]
        ordinate = [4700.0, 4340.0, 3920.0, 3450.0]
        fit = mb.fit_pz_depletion(abscissa, ordinate)
        self.assertTrue(any(note.startswith("no_zero_production_point") for note in fit.warnings))
        with_zero = mb.fit_pz_depletion([0.0, *abscissa], [5000.0, *ordinate])
        self.assertFalse(any(note.startswith("no_zero_production_point") for note in with_zero.warnings))
        # Including the Gp = 0 point materially changes G, which is why the two fits are
        # worth reporting side by side rather than picking one silently.
        self.assertGreater(abs(with_zero.gas_in_place_scf / fit.gas_in_place_scf - 1.0), 1.0e-4)

    def test_weights_are_honoured_and_change_the_answer(self):
        abscissa = [0.0, 5.0e9, 11.0e9, 18.0e9, 26.0e9]
        ordinate = [5000.0, 4700.0, 4340.0, 3920.0, 3450.0]
        unweighted = mb.fit_pz_depletion(abscissa, ordinate)
        uniform = mb.fit_pz_depletion(abscissa, ordinate, weights=[1.0] * 5)
        self.assertAlmostEqual(uniform.gas_in_place_scf / unweighted.gas_in_place_scf, 1.0, delta=1.0e-14)
        # A common positive rescaling of all weights cannot move the estimate either.
        scaled = mb.fit_pz_depletion(abscissa, ordinate, weights=[7.5] * 5)
        self.assertAlmostEqual(scaled.gas_in_place_scf / unweighted.gas_in_place_scf, 1.0, delta=1.0e-13)
        # Down-weighting the early points, which is one response to the fact that OLS
        # hands them most of the leverage, must move G.
        late = mb.fit_pz_depletion(abscissa, ordinate, weights=[0.1, 0.1, 1.0, 1.0, 1.0])
        self.assertNotAlmostEqual(late.gas_in_place_scf / unweighted.gas_in_place_scf, 1.0, places=6)

    def test_results_are_frozen_immutable_and_deterministic(self):
        abscissa = [0.0, 5.0e9, 11.0e9, 18.0e9, 26.0e9]
        ordinate = [5000.0, 4700.0, 4340.0, 3920.0, 3450.0]
        first = mb.fit_pz_depletion(abscissa, ordinate)
        second = mb.fit_pz_depletion(abscissa, ordinate)

        # C4: two calls with equal arguments return equal results, bit for bit.
        self.assertEqual(first, second)
        # C5: series are tuples, so a caller cannot mutate a validated result.
        self.assertIsInstance(first.residuals, tuple)
        self.assertIsInstance(first.warnings, tuple)
        with self.assertRaises(FrozenInstanceError):
            first.gas_in_place_scf = 1.0

        plot = mb.modified_roach_plot_coordinates(
            pressure_psia=[5600.0, 5200.0, 4800.0],
            z_factor=[1.07, 1.045, 1.02],
            cumulative_gas_scf=[4.7e9, 1.0e10, 1.55e10],
            produced_water_rcf=[2.0e4, 6.0e4, 1.3e5],
            initial_pressure_psia=6000.0,
            initial_z_factor=1.10,
            gas_fvf_initial_rcf_per_scf=3.5e-3,
        )
        self.assertIsInstance(plot.x, tuple)
        with self.assertRaises(FrozenInstanceError):
            plot.variant = "roach"

    def test_fit_records_the_regression_path_that_produced_it(self):
        # The line and its x-intercept standard error both come from
        # reservoir_lab.regression, and the result records which of that module's paths
        # ran, so a number can be audited back to the code that made it.
        unweighted = mb.fit_pz_depletion([0.0, 1.0e10, 2.0e10], [5000.0, 4500.0, 3900.0])
        self.assertEqual(unweighted.method, "ols")
        self.assertEqual(unweighted.regression_method, "ols")
        weighted = mb.fit_pz_depletion(
            [0.0, 1.0e10, 2.0e10], [5000.0, 4500.0, 3900.0], weights=[1.0, 2.0, 1.0]
        )
        self.assertEqual(weighted.regression_method, "wls")
        self.assertGreaterEqual(unweighted.fieller_g, 0.0)

    def test_delta_method_warning_is_carried_through_from_the_regression(self):
        # A badly determined slope makes the symmetric interval around a ratio a false
        # summary rather than merely a wide one. The regression detects that through the
        # Fieller discriminant; this module must not swallow the message.
        rng = random.Random(90210)
        abscissa = [0.0, 1.0e9, 2.0e9, 3.0e9, 4.0e9]
        ordinate = [5000.0 - 1.0e-7 * x + rng.gauss(0.0, 150.0) for x in abscissa]
        fit = mb.fit_pz_depletion(abscissa, ordinate)
        self.assertGreater(fit.fieller_g, 0.01)
        self.assertTrue(any(note.startswith("delta_method_interval") for note in fit.warnings))


if __name__ == "__main__":
    unittest.main()

"""Verification of the foundation layer: units, errors, validation, numerics, provenance.

The four contract categories (C7) appear throughout rather than in four blocks, because
grouping by module is what makes a failure readable. Each test names its category in its
docstring.

The governing idea for `units` is that the module claims every conversion factor is
exact by definition or derived from factors that are. A test that re-states the module's
own arithmetic proves nothing about that claim, so each constant here is rebuilt through
a *different* chain of the same defining quantities -- pressure via the pound-force
rather than via the kilogram directly, the gas constant via an ideal-gas molar volume as
well as via a factor chain, the barrel via the litre rather than via the cubic inch. An
arithmetic slip or a transposed digit in the module would have to be reproduced exactly
by an unrelated route to survive, which is the point. The independence of those routes
is not uniform and the docstrings below say which is which: rebuilding R through a molar
volume shares nothing with `units.py` but the defining constants, while rebuilding the
psi through the pound-force shares the whole physical chain and differs only in how the
arithmetic is grouped.

Contract gaps found and closed
------------------------------
Several tests here began life marked `unittest.expectedFailure`. Each stated a behaviour
the API contract requires and reproduced a deviation from it in `src/reservoir_lab`,
staying red until the implementation was corrected -- at which point unittest reports an
unexpected success and the decorator comes off. Writing them that way, rather than
leaving the gap as a sentence in a report, is what made each one a gate.

All of them have since been closed in `src/`, and the tests remain as the guards that
keep them closed. What they found:

* `StandardConditions` accepted NaN and infinity. The guards were written as comparisons,
  and `not (p > 0.0)` rejects NaN while the symmetric `t <= 0.0` accepts it, so a NaN
  standard temperature travelled silently with every standard volume computed against it.
* `StandardConditions` raised plain `ValueError` where contract C3 requires
  `InvalidInputError`. Because the latter subclasses the former, the three ordinary tests
  around it could not tell a correct implementation from the broken one.
* The conversion functions in `units` validated nothing, so `fahrenheit_to_rankine(nan)`
  returned NaN -- the sentinel return C3 forbids outright.
* `composite_simpson` validated its interval count and not its limits, returning inf or
  NaN for a non-finite limit.
* The sign tests in `numerics` used the product `f_low * f_high`, which underflows to
  zero for residuals of magnitude 1e-170. A function that plainly changes sign was
  reported as having no sign change, and the solver returned a number that was not a
  root -- the one failure the module docstring claims cannot happen.
* `source_revision` stripped the whole porcelain output, removing the leading status
  column of the first line, so the first dirty path was reported one character short.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings
from fractions import Fraction

from reservoir_lab import numerics, provenance, units, validation
from reservoir_lab.errors import (
    ConvergenceError,
    InvalidInputError,
    NotIdentifiableError,
    OutOfRangeWarningError,
    RangeWarning,
    ReservoirLabError,
)

# ---------------------------------------------------------------------------
# Defining quantities, restated here so the test does not import them from the
# module it is checking. All are exact by definition of the unit.
# ---------------------------------------------------------------------------

MOLAR_GAS_CONSTANT_SI = 8.314462618153240  # J/(mol K); exact since the 2019 SI revision
KILOGRAM_PER_POUND = 0.45359237  # international yard and pound agreement, 1959
METRE_PER_FOOT = 0.3048
METRE_PER_INCH = 0.0254
STANDARD_GRAVITY = 9.80665  # m/s^2, exact by definition
LITRE_PER_US_GALLON = 3.785411784  # exact: 231 in^3 with the inch defined above
PASCAL_PER_ATMOSPHERE = 101325.0  # exact by definition

# One pound-force is the weight of one pound-mass under standard gravity, so the psi
# follows from force over area. This is how a metrology reference states it. It is the
# same physical chain units.py uses -- mass x gravity / area -- regrouped, and written
# from the kilogram rather than from the gram, so what it checks is the transcription of
# the three defining constants and the grouping of the arithmetic, not an independent
# derivation of the psi. The name says INDEPENDENT of the module, not of the physics.
NEWTON_PER_POUND_FORCE = KILOGRAM_PER_POUND * STANDARD_GRAVITY
PASCAL_PER_PSI_INDEPENDENT = NEWTON_PER_POUND_FORCE / (METRE_PER_INCH**2)

# Machine-precision tolerance. Two double-precision evaluations of the same exact
# rational quantity by different orderings of multiplication and division differ by a
# few units in the last place, never more, so 1e-15 relative is the honest bound on
# "identical arithmetic, different order". It is not a fitted tolerance.
ULP_RELATIVE = 1.0e-15

#: Unit in the last place of a double, used where a bound has to be stated absolutely.
EPSILON = sys.float_info.epsilon


def relative_difference(actual: float, expected: float) -> float:
    """Relative difference, falling back to absolute when the expected value is zero."""
    return abs(actual - expected) / abs(expected) if expected != 0.0 else abs(actual - expected)


class GasConstantTests(unittest.TestCase):
    """Independent oracle: the field gas constant from two unrelated conversion chains."""

    def test_matches_published_field_value_to_its_own_rounding(self):
        """Independent oracle: 10.7316 psia ft^3/(lbmol degR) as published in the texts.

        The published figure carries six significant digits, so agreement is asserted to
        half a unit in its last place and no further. Asserting more digits than the
        source states would be asserting the module against itself.
        """
        self.assertLess(abs(units.GAS_CONSTANT_FIELD - 10.7316), 0.5e-4)

    def test_reproduced_by_an_independent_factor_chain(self):
        """Independent oracle: rebuild R through SI with every step inverted or reordered.

        units.py multiplies by 5/9, divides by m^3 per ft^3 and divides by Pa per psi.
        This chain divides by 1.8, multiplies by ft^3 per m^3 and divides by a pascal
        per psi that was itself built from the pound-force. Nothing but the defining
        constants is shared.
        """
        cubic_feet_per_cubic_metre = 1.0 / (METRE_PER_FOOT**3)
        mol_per_lbmol = KILOGRAM_PER_POUND * 1000.0
        r_field = (
            MOLAR_GAS_CONSTANT_SI
            / PASCAL_PER_PSI_INDEPENDENT
            * cubic_feet_per_cubic_metre
            * mol_per_lbmol
            / 1.8
        )
        self.assertLessEqual(relative_difference(units.GAS_CONSTANT_FIELD, r_field), ULP_RELATIVE)

    def test_reproduced_through_an_ideal_gas_molar_volume(self):
        """Independent oracle: R = p V / (n T) evaluated at a known state.

        This route never forms a unit-conversion factor for the gas constant at all. It
        computes the molar volume of an ideal gas at 101325 Pa and 273.15 K in SI,
        converts that volume and that state to field units, and divides. A wrong power
        of ten anywhere in units.py cannot survive it.
        """
        molar_volume_si = MOLAR_GAS_CONSTANT_SI * 273.15 / PASCAL_PER_ATMOSPHERE  # m^3/mol
        molar_volume_field = molar_volume_si / (METRE_PER_FOOT**3) * (KILOGRAM_PER_POUND * 1000.0)
        pressure_psia = PASCAL_PER_ATMOSPHERE / PASCAL_PER_PSI_INDEPENDENT
        temperature_degr = 273.15 * 1.8
        r_field = pressure_psia * molar_volume_field / temperature_degr
        self.assertLessEqual(relative_difference(units.GAS_CONSTANT_FIELD, r_field), ULP_RELATIVE)

    def test_ideal_gas_law_closes_in_field_units(self):
        """Property: one lbmol at 14.696 psia and 519.67 degR occupies 379.5 scf.

        The 379.5 scf/lbmol figure is the number a gas engineer carries in their head,
        and it is an independent statement of the same constant.
        """
        volume_scf = units.GAS_CONSTANT_FIELD * 519.67 / units.ATMOSPHERE_PSIA
        self.assertAlmostEqual(volume_scf, 379.5, places=1)


class ExactConversionFactorTests(unittest.TestCase):
    """Independent oracle: each stored factor rebuilt from the unit definitions."""

    def test_psi_in_pascal_is_the_defined_value(self):
        """Independent oracle: 6894.757293168361 Pa per psi, the published defined value.

        The oracle carrying the weight here is the literal 6894.757293168361, which is
        the value a metrology table gives for the pound per square inch and which is not
        computed from anything in this repository. The second assertion is weaker and is
        labelled as such: PASCAL_PER_PSI_INDEPENDENT follows the same physical chain as
        units.py with the factors regrouped, so it detects a transcription slip in one of
        the three defining constants or a misgrouped product, not a wrong physical chain.

        Bit-for-bit equality is asserted deliberately. Both routes evaluate the same
        exact rational number and the double nearest it is unique, so anything other
        than equality means the module is computing a different quantity, not merely
        rounding differently.
        """
        self.assertEqual(units.PSI_IN_PASCAL, 6894.757293168361)
        self.assertEqual(units.PSI_IN_PASCAL, PASCAL_PER_PSI_INDEPENDENT)

    def test_cubic_feet_per_barrel_is_exact(self):
        """Independent oracle: 42 gal x 231 in^3 as an exact rational, and via the litre."""
        exact = float(Fraction(42 * 231, 12**3))  # 9702/1728 = 5.614583333...
        self.assertEqual(units.CUBIC_FEET_PER_BARREL, exact)

        # Second route, through the metric definition of the gallon. This one is not
        # bit-identical: it passes through 3.785411784 litres and back out again, so it
        # accumulates a rounding step the rational form does not have.
        via_litre = 42.0 * LITRE_PER_US_GALLON * 1.0e-3 / (METRE_PER_FOOT**3)
        self.assertLessEqual(relative_difference(units.CUBIC_FEET_PER_BARREL, via_litre), ULP_RELATIVE)

    def test_standard_atmosphere_in_psia(self):
        """Independent oracle: 101325 Pa is 14.6959 psia, the value quoted in the texts."""
        atmosphere_psia = PASCAL_PER_ATMOSPHERE / PASCAL_PER_PSI_INDEPENDENT
        self.assertEqual(units.ATMOSPHERE_PSIA, atmosphere_psia)
        self.assertLess(abs(units.ATMOSPHERE_PSIA - 14.6959), 0.5e-4)

    def test_density_and_viscosity_factors(self):
        """Independent oracle: g/cm^3 per lbm/ft^3, and centipoise per micropascal-second."""
        cubic_centimetres_per_cubic_foot = (METRE_PER_FOOT * 100.0) ** 3
        grams_per_pound = KILOGRAM_PER_POUND * 1000.0
        expected = grams_per_pound / cubic_centimetres_per_cubic_foot
        self.assertLessEqual(relative_difference(units.LBM_PER_CUFT_IN_G_PER_CC, expected), ULP_RELATIVE)
        # 1 cp = 1 mPa s = 1000 uPa s, so the factor is exactly one thousandth.
        self.assertEqual(units.MICROPASCAL_SECOND_IN_CENTIPOISE, 1.0e-3)

    def test_absolute_zero_offsets(self):
        """Independent oracle: absolute zero on both scales, from the definition of degR.

        -273.15 degC is the definition of absolute zero on the Celsius scale, and the
        Fahrenheit offset must be that value scaled by 9/5 and shifted by the 32 degree
        freezing-point offset. The two are not independently adjustable.
        """
        self.assertEqual(units.ABSOLUTE_ZERO_DEGC, -273.15)
        self.assertAlmostEqual(units.ABSOLUTE_ZERO_DEGF, -273.15 * 9.0 / 5.0 + 32.0, places=12)

    def test_air_molar_mass_is_marked_as_not_exact(self):
        """Property: the one inexact constant carries its provenance string.

        The module's design claim is that everything is exact *except* this. The claim
        is only meaningful if the exception is labelled, so the label is tested.
        """
        self.assertAlmostEqual(units.STANDARD_AIR_MOLAR_MASS, 28.9647, places=4)
        self.assertIn("Standard Atmosphere", units.STANDARD_AIR_MOLAR_MASS_SOURCE)


class ConversionRoundTripTests(unittest.TestCase):
    """Property: every conversion pair recovers its input to machine precision."""

    SAMPLES = (-1234.5, -1.0, 0.0, 1e-9, 1.0, 14.696, 5000.0, 1.25e7)

    def _assert_recovered(self, original: float, recovered: float) -> None:
        """Multiplicative round trip: relative recovery to a few units in the last place.

        A round trip cannot see a pair of factors that is wrong in a mutually cancelling
        way -- 5/9 and 9/5 exchanged in both directions recovers the input exactly. What
        closes that hole is the pair of absolute anchors,
        :meth:`test_freezing_and_boiling_points_anchor_the_temperature_scales` and
        :meth:`test_rankine_kelvin` against them; neither may be deleted while these
        round trips are relied on.
        """
        if original == 0.0:
            self.assertEqual(recovered, 0.0)
        else:
            self.assertLessEqual(relative_difference(recovered, original), ULP_RELATIVE)

    def _assert_recovered_through_offset(self, original: float, recovered: float, offset: float) -> None:
        """Additive round trip: absolute recovery measured against the shifted magnitude.

        A relative bound is the wrong instrument here and asserting one would be a
        tolerance chosen to pass. Adding 459.67 to 1e-9 and subtracting it again loses
        every significant digit of the input, and no implementation can avoid that: the
        information is gone once the sum is rounded to a double. What the conversion can
        be held to is that it introduces no error beyond the rounding of the intermediate
        value, which is what this asserts.
        """
        scale = max(abs(original), abs(offset))
        self.assertLessEqual(abs(recovered - original), 4.0 * EPSILON * scale)

    def test_fahrenheit_rankine(self):
        for degf in self.SAMPLES:
            with self.subTest(degf=degf):
                self._assert_recovered_through_offset(
                    degf,
                    units.rankine_to_fahrenheit(units.fahrenheit_to_rankine(degf)),
                    units.ABSOLUTE_ZERO_DEGF,
                )

    def test_rankine_kelvin(self):
        for degr in self.SAMPLES:
            with self.subTest(degr=degr):
                self._assert_recovered(degr, units.kelvin_to_rankine(units.rankine_to_kelvin(degr)))

    def test_psi_pascal(self):
        for psi in self.SAMPLES:
            with self.subTest(psi=psi):
                self._assert_recovered(psi, units.pascal_to_psi(units.psi_to_pascal(psi)))

    def test_gauge_absolute(self):
        for psig in self.SAMPLES:
            with self.subTest(psig=psig):
                self._assert_recovered_through_offset(
                    psig,
                    units.absolute_to_gauge(units.gauge_to_absolute(psig)),
                    units.ATMOSPHERE_PSIA,
                )

    def test_gauge_absolute_honours_a_site_atmospheric_pressure(self):
        """Property: the atmospheric argument is used, not ignored in favour of the default."""
        self.assertAlmostEqual(units.gauge_to_absolute(100.0, 12.9), 112.9, places=12)
        self._assert_recovered_through_offset(
            100.0, units.absolute_to_gauge(units.gauge_to_absolute(100.0, 12.9), 12.9), 12.9
        )
        # The default is one standard atmosphere, so the two calls must differ by it.
        self.assertAlmostEqual(
            units.gauge_to_absolute(100.0) - units.gauge_to_absolute(100.0, 12.9),
            units.ATMOSPHERE_PSIA - 12.9,
            places=12,
        )

    def test_barrels_cubic_feet(self):
        for barrels in self.SAMPLES:
            with self.subTest(barrels=barrels):
                self._assert_recovered(
                    barrels, units.cubic_feet_to_barrels(units.barrels_to_cubic_feet(barrels))
                )

    def test_specific_gravity_molar_mass(self):
        for gravity in (0.55, 0.65, 0.8, 1.0, 1.7):
            with self.subTest(gravity=gravity):
                self._assert_recovered(
                    gravity,
                    units.molar_mass_to_specific_gravity(units.specific_gravity_to_molar_mass(gravity)),
                )

    def test_air_is_unit_specific_gravity(self):
        """Limiting case: air converts to itself, by the definition of specific gravity."""
        self.assertEqual(units.specific_gravity_to_molar_mass(1.0), units.STANDARD_AIR_MOLAR_MASS)
        self.assertEqual(units.molar_mass_to_specific_gravity(units.STANDARD_AIR_MOLAR_MASS), 1.0)

    def test_freezing_and_boiling_points_anchor_the_temperature_scales(self):
        """Independent oracle: 32 degF is 273.15 K and 212 degF is 373.15 K."""
        self.assertAlmostEqual(units.rankine_to_kelvin(units.fahrenheit_to_rankine(32.0)), 273.15)
        self.assertAlmostEqual(units.rankine_to_kelvin(units.fahrenheit_to_rankine(212.0)), 373.15)
        self.assertAlmostEqual(units.celsius_to_kelvin(0.0), 273.15)


class StandardConditionsTests(unittest.TestCase):
    """The three shipped conventions, and the difference that justifies having no default."""

    def test_spe_versus_us_contractual_differ_by_about_0_23_percent(self):
        """Independent oracle: the 0.23 percent the module docstring uses as its argument.

        14.73 psia against one standard atmosphere. This is the number quoted to justify
        refusing a module-level default standard condition, so if the arithmetic did not
        support it the justification would be decoration.
        """
        difference_percent = (
            100.0
            * (units.US_CONTRACTUAL_STANDARD.pressure_psia - units.SPE_STANDARD.pressure_psia)
            / units.SPE_STANDARD.pressure_psia
        )
        self.assertAlmostEqual(difference_percent, 0.23, places=2)
        self.assertGreater(difference_percent, 0.0)  # the US base is the higher pressure

    def test_the_three_conventions_differ_in_the_documented_way(self):
        """Property: SPE and US differ only in pressure; SPE and metric only in temperature."""
        spe = units.SPE_STANDARD
        us = units.US_CONTRACTUAL_STANDARD
        metric = units.METRIC_STANDARD

        self.assertEqual(spe.temperature_degf, us.temperature_degf)
        self.assertNotEqual(spe.pressure_psia, us.pressure_psia)
        self.assertEqual(us.pressure_psia, 14.73)

        self.assertEqual(spe.pressure_psia, metric.pressure_psia)
        self.assertNotEqual(spe.temperature_degf, metric.temperature_degf)
        # The metric base is 15 degC exactly, which is 59 degF exactly.
        self.assertAlmostEqual(units.celsius_to_kelvin(15.0), 288.15, places=12)
        self.assertAlmostEqual(units.rankine_to_kelvin(metric.temperature_rankine), 288.15, places=12)
        # 60 degF is 15.5555... degC, so the metric base really is a third convention and
        # not a relabelling of the SPE one.
        self.assertAlmostEqual(units.rankine_to_kelvin(spe.temperature_rankine), 288.70555, places=4)

    def test_standard_volume_ratio_follows_the_pressure_ratio(self):
        """Limiting case: at fixed reservoir state, standard volume scales with 1/p_sc.

        Ideal gas, so the ratio of standard volumes for the same reservoir volume is
        exactly the inverse ratio of the standard pressures. A 0.23 percent higher base
        pressure means 0.23 percent fewer standard cubic feet, which is the sentence in
        the module docstring stated as arithmetic.
        """
        ratio = units.SPE_STANDARD.pressure_psia / units.US_CONTRACTUAL_STANDARD.pressure_psia
        self.assertAlmostEqual(100.0 * (1.0 - ratio), 0.2312, places=3)

    def test_temperature_rankine_property(self):
        conditions = units.StandardConditions(pressure_psia=14.65, temperature_degf=60.0)
        self.assertAlmostEqual(conditions.temperature_rankine, 519.67, places=12)

    def test_describe_reports_all_three_fields(self):
        text = units.SPE_STANDARD.describe()
        self.assertIn("14.6959", text)
        self.assertIn("60", text)
        self.assertIn("Z_sc", text)

    def test_rejects_non_positive_pressure(self):
        """Invalid input: a zero or negative standard pressure is not a pressure."""
        for bad in (0.0, -1.0, -14.696):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                units.StandardConditions(pressure_psia=bad, temperature_degf=60.0)

    def test_rejects_temperature_below_absolute_zero(self):
        """Invalid input: below -459.67 degF there is no absolute temperature to speak of."""
        for bad in (-459.67, -460.0, -1000.0):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                units.StandardConditions(pressure_psia=14.696, temperature_degf=bad)

    def test_rejects_non_positive_z_factor(self):
        """Invalid input: a zero deviation factor would make every standard volume infinite."""
        with self.assertRaises(ValueError):
            units.StandardConditions(pressure_psia=14.696, temperature_degf=60.0, z_factor=0.0)

    def test_invalid_standard_conditions_raise_the_contract_exception(self):
        """Invalid input: contract C3 requires InvalidInputError, not a bare ValueError.

        This was a real defect when the test was written; it is now fixed in src/ and
        this test is the guard that keeps it fixed.

        `StandardConditions.__post_init__` raises `ValueError`, and because
        `InvalidInputError` is a subclass of `ValueError` the three tests above cannot
        tell the two apart -- they pass on the correct implementation and on the current
        one alike. This test is the discriminating form of them. The fix, now applied in
        src/reservoir_lab/units.py, was to route the guards through
        validation.require_positive. Kept as written; remove the
        decorator once __post_init__ validates through reservoir_lab.validation.
        """
        for kwargs in (
            {"pressure_psia": 0.0, "temperature_degf": 60.0},
            {"pressure_psia": 14.696, "temperature_degf": -460.0},
            {"pressure_psia": 14.696, "temperature_degf": 60.0, "z_factor": 0.0},
        ):
            with self.subTest(**kwargs), self.assertRaises(InvalidInputError):
                units.StandardConditions(**kwargs)

    def test_rejects_non_finite_fields(self):
        """Invalid input: contract C3 lists non-finite first among what must be refused.

        This was a real defect when the test was written; it is now fixed in src/ and
        this test is the guard that keeps it fixed.

        The guards are written as comparisons (`not (p > 0)`,
        `temperature_rankine <= 0`) and every comparison against NaN is False, so a NaN
        standard temperature is accepted and travels with every standard volume computed
        against it. An infinite standard pressure is accepted for the same reason. The
        fix belongs in src/reservoir_lab/units.py.
        """
        nan, inf = float("nan"), float("inf")
        for kwargs in (
            {"pressure_psia": nan, "temperature_degf": 60.0},
            {"pressure_psia": inf, "temperature_degf": 60.0},
            {"pressure_psia": 14.696, "temperature_degf": nan},
            {"pressure_psia": 14.696, "temperature_degf": inf},
            {"pressure_psia": 14.696, "temperature_degf": 60.0, "z_factor": nan},
        ):
            with self.subTest(**kwargs), self.assertRaises(InvalidInputError):
                units.StandardConditions(**kwargs)

    def test_is_frozen(self):
        """Property: standard conditions travel with a result, so they must not be edited.

        The exception type is pinned. `assertRaises(Exception)` would also pass on an
        AttributeError raised by a misspelled field name, which is not evidence that the
        dataclass is frozen.
        """
        with self.assertRaises(dataclasses.FrozenInstanceError):
            units.SPE_STANDARD.pressure_psia = 14.73  # type: ignore[misc]
        self.assertEqual(units.SPE_STANDARD.pressure_psia, units.ATMOSPHERE_PSIA)


class ConversionValidationTests(unittest.TestCase):
    """Contract C2 at the conversion boundary: accept the input or raise."""

    def test_conversions_validate_their_argument(self):
        """Invalid input: contract C2 binds every public function, conversions included.

        This was a real defect when the test was written; it is now fixed in src/ and
        this test is the guard that keeps it fixed.

        None of the conversion functions in `units` validates anything.
        `psi_to_pascal(None)` raises TypeError rather than InvalidInputError, and
        `fahrenheit_to_rankine(nan)` returns nan, which contract C3 forbids outright
        ("a function never returns a sentinel such as None, -1, or nan"). A NaN entering
        at the Fahrenheit-to-Rankine bridge is the exact path by which a NaN reaches a
        reservoir temperature. Every conversion now validates its argument.
        """
        nan = float("nan")
        for function, argument in (
            (units.psi_to_pascal, None),
            (units.psi_to_pascal, nan),
            (units.fahrenheit_to_rankine, nan),
            (units.barrels_to_cubic_feet, nan),
            (units.specific_gravity_to_molar_mass, nan),
        ):
            with (
                self.subTest(function=function.__name__, argument=argument),
                self.assertRaises(InvalidInputError),
            ):
                function(argument)


class ErrorHierarchyTests(unittest.TestCase):
    """Contract C3: the exception types and the diagnostic state they carry."""

    def test_every_error_derives_from_the_package_base(self):
        for cls in (
            InvalidInputError,
            ConvergenceError,
            OutOfRangeWarningError,
            NotIdentifiableError,
        ):
            with self.subTest(cls=cls.__name__):
                self.assertTrue(issubclass(cls, ReservoirLabError))

    def test_invalid_input_is_also_a_value_error(self):
        """Property: existing `except ValueError` handlers keep working, as documented."""
        self.assertTrue(issubclass(InvalidInputError, ValueError))
        self.assertTrue(issubclass(ConvergenceError, RuntimeError))
        self.assertTrue(issubclass(RangeWarning, UserWarning))

    def test_convergence_error_carries_and_prints_its_diagnostics(self):
        error = ConvergenceError("no", iterations=7, last_value=1.5, last_residual=-2e-3)
        self.assertEqual(error.iterations, 7)
        self.assertEqual(error.last_value, 1.5)
        self.assertEqual(error.last_residual, -2e-3)
        text = str(error)
        for fragment in ("iterations=7", "last_value=1.5", "last_residual=-0.002"):
            self.assertIn(fragment, text)

    def test_convergence_error_without_diagnostics_prints_only_the_message(self):
        self.assertEqual(str(ConvergenceError("plain message")), "plain message")


class ScalarGuardTests(unittest.TestCase):
    """Invalid input: every documented scalar guard, on its bad case and its good case."""

    def test_require_finite(self):
        self.assertEqual(validation.require_finite(3, "x"), 3.0)
        self.assertIsInstance(validation.require_finite(3, "x"), float)
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                validation.require_finite(bad, "x")
        for bad in ("not a number", None, [1.0]):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                validation.require_finite(bad, "x")

    def test_require_finite_names_the_argument(self):
        """Property: contract C2 requires the message to name the offending argument."""
        with self.assertRaises(InvalidInputError) as caught:
            validation.require_finite(float("nan"), "pressure_psia")
        self.assertIn("pressure_psia", str(caught.exception))

    def test_require_positive(self):
        self.assertEqual(validation.require_positive(1e-30, "p"), 1e-30)
        for bad in (0.0, -0.0, -1e-30, -5.0):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                validation.require_positive(bad, "p")

    def test_require_positive_explains_the_usual_cause(self):
        """Property: the message points at the gauge-versus-absolute mistake it is guarding."""
        with self.assertRaises(InvalidInputError) as caught:
            validation.require_positive(-3.0, "pressure_psia")
        self.assertIn("absolute", str(caught.exception))

    def test_require_non_negative(self):
        self.assertEqual(validation.require_non_negative(0.0, "q"), 0.0)
        with self.assertRaises(InvalidInputError):
            validation.require_non_negative(-1e-12, "q")

    def test_require_in_interval_inclusive(self):
        self.assertEqual(validation.require_in_interval(0.0, "sw", 0.0, 1.0), 0.0)
        self.assertEqual(validation.require_in_interval(1.0, "sw", 0.0, 1.0), 1.0)
        for bad in (-1e-12, 1.0 + 1e-12, 2.0):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                validation.require_in_interval(bad, "sw", 0.0, 1.0)

    def test_require_in_interval_exclusive_rejects_the_endpoints(self):
        self.assertEqual(validation.require_in_interval(0.5, "sw", 0.0, 1.0, inclusive=False), 0.5)
        for bad in (0.0, 1.0):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                validation.require_in_interval(bad, "sw", 0.0, 1.0, inclusive=False)


class SequenceGuardTests(unittest.TestCase):
    """Invalid input and property tests for the series guards."""

    #: A series chosen so that sorting, truncating, clipping, de-duplicating or dropping
    #: any point changes the answer. It is out of order in both directions, longer than
    #: any plausible hard-coded length, spans nine decades, carries negative values and
    #: repeats a value. The old fixture [1, 2, 3] was degenerate against all five of
    #: those at once: already sorted, exactly three long, and entirely inside [0, 1e6].
    UNRULY_SERIES = (5.0, 1.0, 3.0, -2.0, 3.0, 1.25e9, 0.0, -7.5, 1.0e-9)

    def test_as_float_sequence_returns_an_immutable_tuple(self):
        """Property: a validated series cannot be mutated afterwards (contract C5)."""
        result = validation.as_float_sequence([1, 2, 3], "t")
        self.assertIsInstance(result, tuple)
        self.assertEqual(result, (1.0, 2.0, 3.0))
        for item in result:
            self.assertIsInstance(item, float)

    def test_as_float_sequence_returns_the_callers_series_unchanged(self):
        """Property: contract C2/C4, nothing is sorted, clipped, truncated or dropped.

        This is the only function in the package that returns a caller's series, so it
        is the one place that promise can be tested directly. Each assertion below is
        aimed at a specific silent repair: equality of the whole tuple catches sorting
        and clipping, the length catches truncation and de-duplication, and the
        element-wise loop names the index where a value moved.
        """
        result = validation.as_float_sequence(list(self.UNRULY_SERIES), "time_days")
        self.assertEqual(len(result), len(self.UNRULY_SERIES))
        for index, (actual, expected) in enumerate(zip(result, self.UNRULY_SERIES, strict=True)):
            with self.subTest(index=index):
                self.assertEqual(actual, expected)
        self.assertEqual(result, self.UNRULY_SERIES)
        # Stated the other way round, so a failure reads as what it is.
        self.assertNotEqual(result, tuple(sorted(self.UNRULY_SERIES)))

    def test_as_float_sequence_does_not_copy_the_caller_list_back(self):
        """Property: validating a series has no side effect on the caller's own list."""
        values = list(self.UNRULY_SERIES)
        snapshot = list(values)
        validation.as_float_sequence(values, "time_days")
        self.assertEqual(values, snapshot)

    def test_as_float_sequence_rejects_iterables_that_are_not_numeric_series(self):
        """Invalid input: str, bytes, bytearray and Mapping are iterable but not series.

        Every fixture here is chosen so that the permissive behaviour would succeed
        rather than fail by accident. "123" is all-numeric, so it would become the
        three-point series (1.0, 2.0, 3.0) -- which is exactly what an unparsed CSV
        field looks like downstream; a string such as "12 34" would be caught by the
        float conversion instead, and would therefore prove nothing. b"ab" would become
        (97.0, 98.0) from the byte values, and a mapping with numeric-looking keys would
        iterate over the keys and discard every value.
        """
        for bad in ("123", b"ab", bytearray(b"ab"), {"1": 9.0, "2": 9.0}):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError) as caught:
                validation.as_float_sequence(bad, "time_days")
            self.assertIn("time_days", str(caught.exception))

    def test_as_float_sequence_accepts_a_generator(self):
        self.assertEqual(validation.as_float_sequence((x for x in (1, 2)), "t"), (1.0, 2.0))

    def test_as_float_sequence_reports_the_offending_index(self):
        with self.assertRaises(InvalidInputError) as caught:
            validation.as_float_sequence([1.0, float("nan"), 3.0], "time_days")
        self.assertIn("time_days[1]", str(caught.exception))

    def test_as_float_sequence_rejects_a_non_iterable(self):
        with self.assertRaises(InvalidInputError):
            validation.as_float_sequence(3.0, "t")

    def test_require_same_length(self):
        validation.require_same_length((1, 2), (3, 4), "x", "y")
        with self.assertRaises(InvalidInputError) as caught:
            validation.require_same_length((1, 2, 3), (4, 5), "x", "y")
        self.assertIn("3", str(caught.exception))
        self.assertIn("2", str(caught.exception))

    def test_require_min_length_states_the_purpose(self):
        validation.require_min_length((1, 2), "x", 2, "a straight-line fit")
        with self.assertRaises(InvalidInputError) as caught:
            validation.require_min_length((1,), "x", 2, "a straight-line fit")
        self.assertIn("straight-line fit", str(caught.exception))

    def test_require_strictly_increasing_accepts_an_increasing_series(self):
        validation.require_strictly_increasing([0.0, 1.0, 2.5, 100.0], "t")

    def test_require_strictly_increasing_does_not_sort(self):
        """Property: the guard rejects out-of-order data and leaves the caller's list alone.

        This is the behaviour the module docstring commits to and it is the one a
        convenience library would get wrong. Out-of-order timestamps are evidence that
        two sources were concatenated; sorting them destroys that evidence.
        """
        values = [0.0, 5.0, 3.0, 9.0]
        snapshot = list(values)
        with self.assertRaises(InvalidInputError) as caught:
            validation.require_strictly_increasing(values, "time_days")
        self.assertEqual(values, snapshot)
        message = str(caught.exception)
        self.assertIn("decreases", message)
        self.assertIn("index 2", message)

    def test_require_strictly_increasing_rejects_a_repeat(self):
        """Invalid input: a repeated abscissa is rejected as firmly as a decrease."""
        with self.assertRaises(InvalidInputError) as caught:
            validation.require_strictly_increasing([0.0, 1.0, 1.0, 2.0], "time_days")
        self.assertIn("repeats", str(caught.exception))
        self.assertIn("index 2", str(caught.exception))

    def test_require_non_decreasing_allows_a_flat_segment(self):
        """Limiting case: cumulative production is flat through a shut-in, not increasing."""
        validation.require_non_decreasing([0.0, 10.0, 10.0, 25.0], "gp")
        with self.assertRaises(InvalidInputError) as caught:
            validation.require_non_decreasing([0.0, 10.0, 9.0], "gp")
        self.assertIn("index 2", str(caught.exception))

    def test_single_element_and_empty_series_are_trivially_ordered(self):
        """Limiting case: an ordering guard on fewer than two points has nothing to reject."""
        validation.require_strictly_increasing([], "t")
        validation.require_strictly_increasing([1.0], "t")
        validation.require_non_decreasing([1.0], "t")


class CheckRangeTests(unittest.TestCase):
    """The soft correlation-window check: warns by default, raises under strict."""

    def test_inside_the_window_is_silent_and_returns_the_value(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # any warning at all fails this test
            returned = validation.check_range(1.5, "t_pr", 1.0, 3.0, correlation="DAK")
        self.assertEqual(returned, 1.5)

    def test_outside_the_window_warns_by_default(self):
        """Property: the default is a recorded excursion, not a refusal and not silence."""
        with self.assertWarns(RangeWarning) as caught:
            returned = validation.check_range(0.5, "t_pr", 1.0, 3.0, correlation="DAK")
        self.assertEqual(returned, 0.5)
        message = str(caught.warning)
        self.assertIn("DAK", message)
        self.assertIn("t_pr", message)
        self.assertIn("extrapolation", message)

    def test_outside_the_window_raises_under_strict(self):
        """Invalid input: strict callers get OutOfRangeWarningError, per contract C3."""
        with self.assertRaises(OutOfRangeWarningError):
            validation.check_range(45.0, "p_pr", 0.2, 30.0, correlation="DAK", strict=True)

    def test_strict_is_silent_inside_the_window(self):
        self.assertEqual(validation.check_range(2.0, "t_pr", 1.0, 3.0, correlation="DAK", strict=True), 2.0)

    def test_boundaries_are_inside_the_window(self):
        """Limiting case: the published endpoints are part of the published window."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            self.assertEqual(validation.check_range(1.0, "t_pr", 1.0, 3.0, correlation="DAK"), 1.0)
            self.assertEqual(validation.check_range(3.0, "t_pr", 1.0, 3.0, correlation="DAK"), 3.0)

    def test_a_non_finite_value_is_rejected_before_the_range_is_considered(self):
        with self.assertRaises(InvalidInputError):
            validation.check_range(float("nan"), "t_pr", 1.0, 3.0, correlation="DAK")


def _cubic(x: float) -> float:
    """Return a general cubic with no symmetry that Simpson could exploit by accident."""
    return 2.0 - 3.0 * x + 0.5 * x * x + 1.25 * x**3


def _cubic_antiderivative(x: float) -> float:
    return 2.0 * x - 1.5 * x * x + x**3 / 6.0 + 0.3125 * x**4


class CompositeSimpsonTests(unittest.TestCase):
    """Simpson's rule against its closed-form exactness property."""

    LOWER = -1.3
    UPPER = 3.7

    def test_exact_for_polynomials_up_to_cubic(self):
        """Independent oracle: the analytic antiderivative, to machine precision.

        Simpson's rule integrates cubics exactly. That is a theorem about the rule, not
        a tolerance to be chosen, so the assertion is at the level of double-precision
        round-off and stays there whatever the grid. The cubic term is the interesting
        one: a rule with the wrong middle weight is still exact for quadratics, so a
        quadratic-only test would pass on a broken implementation.
        """
        exact = _cubic_antiderivative(self.UPPER) - _cubic_antiderivative(self.LOWER)
        for intervals in (2, 4, 10, 50, 200):
            with self.subTest(intervals=intervals):
                value = numerics.composite_simpson(_cubic, self.LOWER, self.UPPER, intervals)
                self.assertLessEqual(relative_difference(value, exact), 1.0e-14)

    def test_exact_for_each_monomial_separately(self):
        """Independent oracle: integral of x**k on [0, 1] is 1/(k+1) for k = 0..3."""
        for power in range(4):
            with self.subTest(power=power):
                value = numerics.composite_simpson(lambda x, k=power: x**k, 0.0, 1.0, 2)
                self.assertLessEqual(relative_difference(value, 1.0 / (power + 1)), 1.0e-15)

    def test_quartic_is_not_exact(self):
        """Property: the positive control. The rule is exact to cubic and no further.

        Without this, "exact for a cubic" could be passing because the test's own
        integrand is degenerate or because the comparison is too loose to see anything.
        The quartic error must be visible on a coarse grid and must shrink by about
        sixteen when the grid is halved.
        """
        exact = 1.0 / 5.0
        coarse = abs(numerics.composite_simpson(lambda x: x**4, 0.0, 1.0, 2) - exact)
        fine = abs(numerics.composite_simpson(lambda x: x**4, 0.0, 1.0, 4) - exact)
        self.assertGreater(coarse, 1.0e-6)

        # For x**4 the fourth derivative is constant, so the composite Simpson error is
        # exactly -(b - a) h**4 f''''/180 with no higher-order terms at all, and the
        # ratio is exactly 16 in exact arithmetic. The only thing separating the computed
        # ratio from 16 is the rounding of the two quadrature sums. Each is a sum of
        # order ten terms of magnitude ~0.2, so its absolute round-off is bounded by a
        # few tens of ulp(0.2) ~ 3e-17; propagating that through the quotient gives
        # 16 * 20 * ulp(0.2) * (1/coarse + 1/fine) ~ 2e-11 with coarse = 8.3e-3 and
        # fine = 5.2e-4. The bound below is that figure rounded up. It is derived from
        # the theorem and the arithmetic, not from the observed 5e-14.
        round_off_bound = 16.0 * 20.0 * math.ulp(0.2) * (1.0 / coarse + 1.0 / fine)
        self.assertLess(round_off_bound, 1.0e-10)  # the derivation, kept honest
        self.assertAlmostEqual(coarse / fine, 16.0, delta=1.0e-10)

    def test_zero_width_interval_is_exactly_zero(self):
        """Limiting case: an integral over a point is zero, not a small residue."""
        self.assertEqual(numerics.composite_simpson(math.exp, 2.0, 2.0, 4), 0.0)

    def test_reversed_limits_negate_the_result(self):
        """Property: the result behaves like an integral, not like a loop over a grid."""
        forward = numerics.composite_simpson(_cubic, self.LOWER, self.UPPER, 8)
        backward = numerics.composite_simpson(_cubic, self.UPPER, self.LOWER, 8)
        self.assertEqual(forward + backward, 0.0)

    def test_additivity_over_a_split_interval(self):
        """Property: the integral over a union equals the sum over the parts."""
        whole = numerics.composite_simpson(_cubic, 0.0, 4.0, 16)
        parts = numerics.composite_simpson(_cubic, 0.0, 1.5, 8) + numerics.composite_simpson(
            _cubic, 1.5, 4.0, 8
        )
        self.assertLessEqual(relative_difference(parts, whole), 1.0e-14)

    def test_rejects_an_odd_or_non_positive_interval_count(self):
        """Invalid input: Simpson needs pairs of subintervals."""
        for bad in (0, -2, 1, 3, 999):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                numerics.composite_simpson(math.exp, 0.0, 1.0, bad)

    def test_rejects_non_finite_limits(self):
        """Invalid input: contract C2 and C3 on the limits of integration.

        This was a real defect when the test was written; it is now fixed in src/ and
        this test is the guard that keeps it fixed.

        `composite_simpson` validates `intervals` and nothing else, so an
        infinite upper limit returns inf and a NaN lower limit returns nan, which is
        precisely the sentinel return C3 forbids. composite_simpson now validates
        both limits.
        """
        for lower, upper in ((0.0, float("inf")), (float("nan"), 1.0), (float("-inf"), 0.0)):
            with self.subTest(lower=lower, upper=upper), self.assertRaises(InvalidInputError):
                numerics.composite_simpson(math.exp, lower, upper, 4)


# ---------------------------------------------------------------------------
# Closed-form error expansion for composite Simpson.
#
# On [a, b] with subinterval step h the rule obeys an Euler-Maclaurin-type expansion
#
#     S(h) - I = (h**4 / 180) [f'''(b) - f'''(a)]
#              - (h**6 / 1512) [f'''''(b) - f'''''(a)] + O(h**8)
#
# so every quantity a convergence study reports -- the ratio of successive true errors,
# the observed order, the residual left by Richardson extrapolation -- has a closed-form
# prediction before any code is run. The tests below assert against those predictions
# instead of against numbers read off a previous run, which is what turns "the order is
# about 4" into a statement that can fail.
#
# The tolerances come from the first neglected term. Successive coefficients of the
# expansion fall by 180/1512 = 0.119 per factor of h**2, so truncating after the h**6
# term leaves a relative error of order (0.119 h**2)**2; a factor of four allows for the
# unknown O(1) multiplier in the h**8 coefficient, which is not being derived here.
# ---------------------------------------------------------------------------

SIMPSON_H4_COEFFICIENT = 1.0 / 180.0
SIMPSON_H6_COEFFICIENT = 1.0 / 1512.0
SIMPSON_TERM_RATIO = SIMPSON_H6_COEFFICIENT / SIMPSON_H4_COEFFICIENT


def simpson_error_for_exp_on_the_unit_interval(step: float) -> float:
    """Predicted composite Simpson error for exp on [0, 1] at subinterval step ``step``.

    Every derivative of exp is exp, so both derivative jumps in the expansion are e - 1.
    That is what makes this the clean integrand to test the machinery against.
    """
    jump = math.e - 1.0
    return jump * (SIMPSON_H4_COEFFICIENT * step**4 - SIMPSON_H6_COEFFICIENT * step**6)


def predicted_observed_order(coarse_step: float) -> float:
    """Order the estimator must report for exp on [0, 1] from three grids.

    Not 4: with the h**6 term retained the successive differences carry an O(h**2)
    correction, so the observed order is 4 - O(h**2) and approaches 4 from below.
    """
    error = simpson_error_for_exp_on_the_unit_interval
    first = error(coarse_step) - error(coarse_step / 2.0)
    second = error(coarse_step / 2.0) - error(coarse_step / 4.0)
    return math.log(first / second) / math.log(2.0)


def simpson_truncation_allowance(step: float) -> float:
    """Relative allowance for the first neglected term of the expansion at ``step``."""
    return 4.0 * (SIMPSON_TERM_RATIO * step * step) ** 2


class ConvergenceStudyTests(unittest.TestCase):
    """The demonstrated order of accuracy, not a single grid's value."""

    GRIDS = (4, 8, 16, 32)

    def test_observed_order_matches_the_closed_form_prediction(self):
        """Independent oracle: the order predicted by the error expansion, not "about 4".

        exp(x) on [0, 1] is smooth, non-polynomial, and has a closed-form integral, so
        the true error is known at every grid and so is the order the estimator must
        report. The grids stop at 32 deliberately: past that the error is near round-off
        and the Richardson estimate degenerates, which is a separate test.
        """
        study = numerics.convergence_study(math.exp, 0.0, 1.0, self.GRIDS)
        self.assertEqual(study.interval_counts, self.GRIDS)
        self.assertEqual(len(study.observed_orders), 2)

        for index, count in enumerate(self.GRIDS[:2]):
            coarse_step = 1.0 / count
            predicted = predicted_observed_order(coarse_step)
            with self.subTest(coarse_step=coarse_step):
                self.assertLessEqual(
                    abs(study.observed_orders[index] - predicted),
                    predicted * simpson_truncation_allowance(coarse_step),
                )
        # The headline statement, kept because it is the one a reader checks first. The
        # deficit below 4 is not slack in the test: the expansion puts it at 0.0021 on
        # the finest triple, and 0.01 is that figure with room for the h**8 term while
        # still excluding order 3 and order 5 by three orders of magnitude.
        self.assertLess(abs(study.observed_orders[-1] - 4.0), 0.01)
        self.assertGreater(study.observed_orders[-1], study.observed_orders[0])

    def test_true_error_ratios_match_the_closed_form_prediction(self):
        """Independent oracle: successive true errors against the expansion.

        The ratio is near 16 but not 16, and the difference is the point: it is
        0.089, 0.022 and 0.006 on these three refinements, falling as h**2 exactly as
        the h**6 term requires. Asserting "16 within 0.6" would pass on an
        implementation whose error fell as h**4 for the wrong reason.
        """
        study = numerics.convergence_study(math.exp, 0.0, 1.0, self.GRIDS)
        exact = math.e - 1.0
        true_errors = [abs(value - exact) for value in study.values]
        for index in range(1, len(true_errors)):
            coarse_step = 1.0 / self.GRIDS[index - 1]
            predicted = simpson_error_for_exp_on_the_unit_interval(
                coarse_step
            ) / simpson_error_for_exp_on_the_unit_interval(coarse_step / 2.0)
            with self.subTest(coarse_step=coarse_step):
                self.assertLessEqual(
                    abs(true_errors[index - 1] / true_errors[index] - predicted),
                    predicted * simpson_truncation_allowance(coarse_step),
                )
                self.assertLess(predicted, 16.0)  # approached from below, never above

    def test_richardson_estimate_matches_its_predicted_residual(self):
        """Independent oracle: the extrapolated value against the analytic integral.

        The first assertion is the one that needs no number at all, and it is the
        strongest statement about the extrapolation: it must beat the finest grid.

        The second predicts what is left over, from the expansion alone. Two terms
        contribute. Exact fourth-order extrapolation of E(h) = a h**4 - b h**6 leaves
        (16 E(h/2) - E(h)) / 15 = b h**6 / 20 with h the coarser of the two steps. On top
        of that the module extrapolates with the *observed* order p rather than with 4,
        and that mismatch contributes (V_fine - V_coarse) (1/(2**p - 1) - 1/15). Both are
        evaluated here from the closed form, with no value read back out of the study.

        Tolerance: the mismatch term dominates and is proportional to the order deficit
        4 - p = 0.0021, which the expansion itself pins only to about 2.6 percent (its
        own truncation allowance, 5.5e-5, divided by the deficit). That is 3.4 percent on
        the sum; the bound is set at 10 percent, three times that.
        """
        study = numerics.convergence_study(math.exp, 0.0, 1.0, self.GRIDS)
        exact = math.e - 1.0
        self.assertLess(abs(study.richardson_estimate - exact), abs(study.best() - exact))

        coarse_step = 1.0 / self.GRIDS[-2]
        leading = (math.e - 1.0) * SIMPSON_H6_COEFFICIENT * coarse_step**6 / 20.0
        order = predicted_observed_order(1.0 / self.GRIDS[-3])
        difference = simpson_error_for_exp_on_the_unit_interval(
            coarse_step / 2.0
        ) - simpson_error_for_exp_on_the_unit_interval(coarse_step)
        mismatch = difference * (1.0 / (2.0**order - 1.0) - 1.0 / 15.0)
        predicted_residual = leading + mismatch

        self.assertLessEqual(
            abs((study.richardson_estimate - exact) - predicted_residual),
            0.10 * abs(predicted_residual),
        )

    def test_richardson_uses_the_observed_order_not_a_hard_wired_four(self):
        """Independent oracle: an integrand whose observed order is not 4.

        sqrt(x) on [0, 1] has an integrable singularity in its derivative at the origin,
        and for the integral of x**alpha the composite Newton-Cotes error is governed by
        that endpoint and falls as h**(alpha + 1). With alpha = 1/2 the observed order is
        3/2, not 4, and the two extrapolations part company completely: extrapolating
        with 3/2 lands within 1e-8 of 2/3 while extrapolating with 4 is barely better
        than the finest grid. Replacing the module's order selection with the constant
        4.0 -- which the exp study above cannot see, because there the observed order is
        4 anyway -- changes this answer by four orders of magnitude.
        """
        grids = (8, 16, 32, 64)
        study = numerics.convergence_study(math.sqrt, 0.0, 1.0, grids)
        exact = 2.0 / 3.0

        # The order itself, against the closed form alpha + 1 = 1.5. The remaining
        # discrepancy is the next term of the Navot expansion, O(h**0.5) relative, which
        # is why this is asserted to two decimals and not to ten.
        self.assertAlmostEqual(study.observed_orders[-1], 1.5, places=3)

        fixed_order_four = study.values[-1] + (study.values[-1] - study.values[-2]) / 15.0
        observed_error = abs(study.richardson_estimate - exact)
        self.assertLess(observed_error, 1.0e-7)
        self.assertGreater(abs(fixed_order_four - exact) / observed_error, 1.0e3)
        # ... and the order-4 extrapolation is not even a large improvement on the grid.
        self.assertGreater(abs(fixed_order_four - exact), 0.5 * abs(study.best() - exact))

    def test_best_returns_the_finest_grid_value(self):
        study = numerics.convergence_study(math.exp, 0.0, 1.0, (4, 8, 16))
        self.assertEqual(study.best(), study.values[-1])
        self.assertEqual(len(study.relative_changes), 2)
        self.assertLess(study.relative_changes[-1], study.relative_changes[0])

    def test_result_is_frozen(self):
        """Property: contract C5, a multi-field result is a frozen dataclass.

        The exception type is pinned for the same reason as in StandardConditions: a
        bare Exception would also be satisfied by an AttributeError from a typo.
        """
        study = numerics.convergence_study(math.exp, 0.0, 1.0, (4, 8, 16))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            study.richardson_estimate = 0.0  # type: ignore[misc]
        self.assertIsInstance(study.values, tuple)

    def test_rejects_too_few_grids(self):
        """Invalid input: an order estimate needs three grids."""
        with self.assertRaises(InvalidInputError):
            numerics.convergence_study(math.exp, 0.0, 1.0, (8, 16))

    def test_rejects_a_non_doubling_sequence(self):
        """Invalid input: Richardson assumes a fixed refinement ratio."""
        with self.assertRaises(InvalidInputError):
            numerics.convergence_study(math.exp, 0.0, 1.0, (4, 8, 24))


class RichardsonOrderTests(unittest.TestCase):
    """The order estimator, including its refusal to invent a number."""

    def test_recovers_a_constructed_order_exactly(self):
        """Independent oracle: values built as I + C h**p must return p.

        With h = 2, 1, 0.5 and p = 3 the successive differences are 7C and 0.875C, whose
        ratio is exactly 8, so the estimator must return exactly 3. The value is a closed
        form, not a measurement.
        """
        for power in (1.0, 2.0, 3.0, 4.0):
            with self.subTest(power=power):
                exact, coefficient = 5.0, 0.125
                values = [exact + coefficient * (2.0 ** (-k)) ** power for k in range(3)]
                self.assertAlmostEqual(numerics.richardson_order(*values), power, places=12)

    def test_returns_nan_when_the_differences_degenerate(self):
        """Property: nan rather than a fabricated order once round-off dominates.

        Three cases make the differences uninformative: identical successive values (a
        zero denominator), a zero numerator, and differences of opposite sign. In all
        three the order is genuinely not estimable and the honest answer is nan. A
        function that returned, say, 4.0 here would be reporting a convergence rate it
        never observed.
        """
        self.assertTrue(math.isnan(numerics.richardson_order(1.0, 1.0, 1.0)))
        self.assertTrue(math.isnan(numerics.richardson_order(1.0, 1.0, 0.5)))
        self.assertTrue(math.isnan(numerics.richardson_order(1.0, 0.5, 0.5)))
        self.assertTrue(math.isnan(numerics.richardson_order(2.0, 1.0, 3.0)))
        self.assertTrue(math.isnan(numerics.richardson_order(1.0, 2.0, 1.5)))

    def test_a_degenerate_study_still_returns_a_usable_result(self):
        """Limiting case: integrating a constant is exact on every grid.

        Every value is identical, so every observed order is nan. The study must still
        return, with the nan visible in the record, rather than raising or substituting
        a plausible-looking 4.
        """
        study = numerics.convergence_study(lambda x: 3.0, 0.0, 2.0, (4, 8, 16))  # noqa: ARG005
        for value in study.values:
            self.assertAlmostEqual(value, 6.0, places=12)
        self.assertTrue(all(math.isnan(order) for order in study.observed_orders))
        self.assertAlmostEqual(study.richardson_estimate, 6.0, places=12)


def _naive_newton(function, derivative, start: float, iterations: int = 40) -> tuple[float, bool]:
    """Textbook unsafeguarded Newton, written out here so the contrast is visible.

    Returns the final iterate and whether it stayed finite and bounded. This exists only
    as the negative control for :func:`numerics.safeguarded_newton`: without it, a test
    that the safeguarded solver converges says nothing about whether the safeguarding is
    doing any work.
    """
    x = start
    for _ in range(iterations):
        slope = derivative(x)
        if slope == 0.0:
            return x, False
        try:
            x = x - function(x) / slope
        except OverflowError:
            return math.inf, False
        if not math.isfinite(x) or abs(x) > 1.0e12:
            return x, False
    return x, True


class _RecordingFunction:
    """Wrap a callable and remember every abscissa it was evaluated at.

    The solver's promise is about *where* it evaluates, not only about what it returns,
    and a returned root cannot distinguish a solver that stayed inside its bracket from
    one that wandered outside and came back. Recording the points makes that testable.
    """

    def __init__(self, function) -> None:
        self._function = function
        self.points: list[float] = []

    def __call__(self, x: float) -> float:
        self.points.append(x)
        return self._function(x)


class SafeguardedNewtonTests(unittest.TestCase):
    """Bracketed Newton against the case where naive Newton runs away."""

    @staticmethod
    def _arctangent(x: float) -> float:
        return math.atan(x)

    @staticmethod
    def _arctangent_derivative(x: float) -> float:
        return 1.0 / (1.0 + x * x)

    def test_converges_where_naive_newton_diverges(self):
        """Independent algorithm: the same problem and start point, with and without safeguards.

        atan(x) = 0 has the single root x = 0. Newton's basin of attraction for it ends
        near |x| = 1.3917; from x = 2 the unsafeguarded iteration overshoots, and because
        the function flattens the overshoot grows every step. Six steps reach 1e20. The
        safeguarded solver is handed the identical function, derivative and start point
        and returns the root, because a step that leaves the bracket is replaced by a
        bisection. The contrast is the evidence that the safeguard is load-bearing.

        That the start point really is used, and really is the hostile one, is not
        established here -- any start inside this bracket finds the same single root.
        It is established by
        :meth:`test_the_initial_guess_decides_which_root_is_returned` and by
        :meth:`test_the_iterate_never_leaves_the_bracket`, which this docstring's claim
        depends on.
        """
        start = 2.0
        naive_value, naive_ok = _naive_newton(self._arctangent, self._arctangent_derivative, start)
        self.assertFalse(naive_ok, "naive Newton was expected to diverge from this start point")
        self.assertGreater(abs(naive_value), 1.0e12)

        root = numerics.safeguarded_newton(
            self._arctangent,
            self._arctangent_derivative,
            bracket=(-1.0, 5.0),
            initial_guess=start,
            description="atan root",
        )
        self.assertLess(abs(root), 1.0e-12)

    def test_naive_newton_succeeds_inside_the_basin(self):
        """Property: the positive control for the negative control.

        If naive Newton failed from every start point, the divergence above would be
        evidence about the test's own Newton implementation rather than about the
        problem. From x = 1 it converges, so the implementation is sound and it is the
        start point at x = 2 that is hostile.
        """
        value, ok = _naive_newton(self._arctangent, self._arctangent_derivative, 1.0)
        self.assertTrue(ok)
        self.assertLess(abs(value), 1.0e-12)

    def test_converges_on_a_well_behaved_root(self):
        """Independent oracle: the square root of two, known in closed form."""
        root = numerics.safeguarded_newton(
            lambda x: x * x - 2.0,
            lambda x: 2.0 * x,
            bracket=(0.0, 3.0),
        )
        self.assertAlmostEqual(root, math.sqrt(2.0), places=12)

    def test_a_useless_derivative_does_not_stop_convergence(self):
        """Property: with the derivative disabled the solver degrades to bisection.

        Returning zero from the derivative forces every step through the bisection
        branch. The solver must still return the root, which is what "cannot return a
        number from outside the bracket" means in practice.
        """
        root = numerics.safeguarded_newton(
            lambda x: x * x - 2.0,
            lambda x: 0.0,  # noqa: ARG005
            bracket=(0.0, 3.0),
            tolerance=1.0e-13,
            max_iterations=200,
        )
        self.assertAlmostEqual(root, math.sqrt(2.0), places=11)

    def test_returns_an_endpoint_that_is_itself_a_root(self):
        """Limiting case: a bracket endpoint sitting exactly on the root."""
        root = numerics.safeguarded_newton(
            lambda x: x,
            lambda x: 1.0,  # noqa: ARG005
            bracket=(0.0, 4.0),
        )
        self.assertEqual(root, 0.0)

    def test_accepts_a_reversed_bracket(self):
        """Property: the bracket is an interval, so the order of its endpoints is immaterial."""
        root = numerics.safeguarded_newton(lambda x: x * x - 2.0, lambda x: 2.0 * x, bracket=(3.0, 0.0))
        self.assertAlmostEqual(root, math.sqrt(2.0), places=12)

    def test_rejects_a_bracket_without_a_sign_change(self):
        """Invalid input: no sign change means no guarantee, so the solver refuses."""
        with self.assertRaises(InvalidInputError) as caught:
            numerics.safeguarded_newton(self._arctangent, self._arctangent_derivative, bracket=(1.0, 5.0))
        self.assertIn("sign change", str(caught.exception))

    def test_the_initial_guess_decides_which_root_is_returned(self):
        """Property: the documented start point is used, and it changes the answer.

        The contrast test above hands the solver a hostile start point and says so in
        its docstring, but nothing there fails if the start point is ignored: any start
        inside that bracket finds the same single root. sin(x) on [-1, 7] brackets three
        roots -- 0, pi and 2 pi -- so the returned one is a direct readout of where the
        iteration began. A solver that discarded initial_guess and always began at the
        midpoint would return the same root for both guesses below.
        """
        roots = {}
        for guess in (0.1, 5.9):
            roots[guess] = numerics.safeguarded_newton(
                math.sin, math.cos, bracket=(-1.0, 7.0), initial_guess=guess
            )
            with self.subTest(guess=guess):
                # The solver's stopping rule is relative: the bracket is narrowed to
                # tolerance * max(1, |x|), which is 1e-12 near zero and 6.3e-12 near
                # 2 pi. |sin| has unit slope at every root, so the residual is bounded by
                # the same figure; 2e-11 is that bound with a factor of three.
                residual_bound = 3.0 * 1.0e-12 * max(1.0, abs(roots[guess]))
                self.assertLess(abs(math.sin(roots[guess])), residual_bound)
        self.assertAlmostEqual(roots[0.1], 0.0, places=12)
        self.assertAlmostEqual(roots[5.9], 2.0 * math.pi, places=9)
        self.assertNotAlmostEqual(roots[0.1], roots[5.9], places=6)

    def test_the_iterate_never_leaves_the_bracket(self):
        """Property: the module's central claim, stated as where the function is sampled.

        "The iterate is kept inside the bracket at all times" is the reason this package
        has its own solver rather than a textbook Newton, and it is checked here by
        recording every abscissa the solver asks for. The atan case is the one that
        matters: an unsafeguarded step from x = 2 lands at -3.5, outside the bracket and
        on the far side of the root.
        """
        for bracket in ((-1.0, 5.0), (5.0, -1.0)):
            recorded = _RecordingFunction(self._arctangent)
            with self.subTest(bracket=bracket):
                root = numerics.safeguarded_newton(
                    recorded,
                    self._arctangent_derivative,
                    bracket=bracket,
                    initial_guess=2.0,
                )
                self.assertLess(abs(root), 1.0e-12)
                low, high = min(bracket), max(bracket)
                self.assertTrue(recorded.points)
                for point in recorded.points:
                    self.assertGreaterEqual(point, low)
                    self.assertLessEqual(point, high)

    def test_an_initial_guess_outside_the_bracket_is_replaced_by_the_midpoint(self):
        """Property: an out-of-bracket start is reset, not evaluated.

        A caller who passes a guess from a previous, differently scaled problem must not
        be able to make the solver evaluate the function outside the interval it was
        given -- for a correlation that would mean evaluating at a non-physical reduced
        density. The reset is to the midpoint, so the recorded trajectory has to be
        identical to the one obtained with no guess at all; returning the right root is
        not enough, because the iteration recovers from a wild start anyway.
        """
        trajectories = {}
        for guess in (None, 1.0e6, -50.0):
            recorded = _RecordingFunction(lambda x: x * x - 2.0)
            root = numerics.safeguarded_newton(
                recorded, lambda x: 2.0 * x, bracket=(0.0, 3.0), initial_guess=guess
            )
            trajectories[guess] = tuple(recorded.points)
            with self.subTest(guess=guess):
                self.assertAlmostEqual(root, math.sqrt(2.0), places=12)
                for point in recorded.points:
                    self.assertGreaterEqual(point, 0.0)
                    self.assertLessEqual(point, 3.0)
        self.assertEqual(trajectories[1.0e6], trajectories[None])
        self.assertEqual(trajectories[-50.0], trajectories[None])

    def test_a_sign_change_is_detected_at_extreme_residual_magnitudes(self):
        """Property: bracketing is decided by signs, not by a product that can underflow.

        This was a real defect when the test was written; it is now fixed in src/ and
        this test is the guard that keeps it fixed.

        The three sign tests in numerics.py compare `f_low * f_high` against
        zero. A product of two residuals of magnitude 1e-170 underflows to +-0.0, so the
        comparison reports the opposite of the truth and the solver returns a number that
        is not a root -- silently, which is the one failure mode the module docstring
        says cannot happen. The scale needed is about 1e-154, far below anything the
        physics modules produce (pseudopressure is order 1e8, reduced density order 0.1),
        so this is a robustness gap in a generic utility rather than a live defect. The
        fix is one line per site in src/reservoir_lab/numerics.py -- compare signs, for
        instance `(f_low > 0.0) != (f_high > 0.0)` -- and is outside this allocation.
        """
        scale = 1.0e-170
        root = numerics.safeguarded_newton(
            lambda x: scale * (x - 1.0),
            lambda x: scale,  # noqa: ARG005 - a constant derivative is the point
            bracket=(0.0, 3.0),
        )
        # Positive control: the identical problem at unit scale returns 1.0 exactly.
        control = numerics.safeguarded_newton(
            lambda x: x - 1.0,
            lambda x: 1.0,  # noqa: ARG005 - a constant derivative is the point
            bracket=(0.0, 3.0),
        )
        self.assertAlmostEqual(control, 1.0, places=12)
        self.assertAlmostEqual(root, 1.0, places=12)

    def test_a_bracket_without_a_sign_change_is_refused_at_extreme_magnitudes(self):
        """Invalid input: the same underflow suppresses the C3 refusal entirely.

        Same root cause as the test above; fixed, and guarded here. f(x) = 1e-180 (x**2 + 1) has no
        root at all; at unit scale the solver raises InvalidInputError as contract C3
        requires, and at this scale it returns 2.9999999999986358 instead.
        """
        scale = 1.0e-180
        with self.assertRaises(InvalidInputError):
            numerics.safeguarded_newton(
                lambda x: scale * (x * x + 1.0),
                lambda x: scale * 2.0 * x,
                bracket=(0.0, 3.0),
            )

    def test_a_bracket_without_a_sign_change_is_refused_at_unit_magnitude(self):
        """Invalid input: the positive control for the test above.

        Without this, the expected failure recorded above could be evidence that the
        solver never refuses anything. At unit scale the refusal happens as documented.
        """
        with self.assertRaises(InvalidInputError):
            numerics.safeguarded_newton(lambda x: x * x + 1.0, lambda x: 2.0 * x, bracket=(0.0, 3.0))

    def test_exhausted_budget_raises_rather_than_returning_the_last_iterate(self):
        """Invalid input: contract C3 forbids returning a sentinel for a failed iteration."""
        with self.assertRaises(ConvergenceError) as caught:
            numerics.safeguarded_newton(
                self._arctangent,
                self._arctangent_derivative,
                bracket=(-1.0, 5.0),
                initial_guess=2.0,
                max_iterations=2,
            )
        error = caught.exception
        self.assertEqual(error.iterations, 2)
        self.assertIsNotNone(error.last_value)
        self.assertIsNotNone(error.last_residual)


class BracketSignChangeTests(unittest.TestCase):
    """Establishing a bracket, and refusing to claim one that does not exist."""

    def test_finds_a_bracket_by_expanding(self):
        """Property: the returned interval genuinely contains a sign change."""
        lower, upper = numerics.bracket_sign_change(lambda x: x * x - 9.0, lower=0.0, upper_guess=1.0)
        self.assertLess(lower, upper)
        self.assertLessEqual((lower * lower - 9.0) * (upper * upper - 9.0), 0.0)
        self.assertLessEqual(lower, 3.0)
        self.assertGreaterEqual(upper, 3.0)

    def test_returns_immediately_when_the_lower_end_is_a_root(self):
        """Limiting case: the search starts on the root.

        This pins the behaviour, and the behaviour contradicts the function's own
        docstring, which promises "(a, b) with a < b". The degenerate interval (0, 0) is
        what the code returns and what a caller must therefore handle, so it is what is
        asserted; the contradiction is a documentation defect in
        src/reservoir_lab/numerics.py and is reported rather than papered over here.
        """
        self.assertEqual(numerics.bracket_sign_change(lambda x: x, lower=0.0, upper_guess=1.0), (0.0, 0.0))

    def test_stops_on_an_upper_end_that_is_exactly_a_root(self):
        """Limiting case: the expansion lands exactly on the root.

        f(x) = x - 8 with a doubling search from 1 evaluates 1, 2, 4, 8 and hits the root
        exactly at 8, where the residual product is zero rather than negative. The
        documented rule is `f(a) * f(b) <= 0`, so the search must stop there; a rule
        written with a strict inequality would expand once more and return (0, 16),
        which is a valid bracket and therefore invisible to any test that only checks
        that a sign change is contained.
        """
        self.assertEqual(
            numerics.bracket_sign_change(lambda x: x - 8.0, lower=0.0, upper_guess=1.0),
            (0.0, 8.0),
        )

    def test_raises_when_there_is_genuinely_no_sign_change(self):
        """Invalid input: x**2 + 1 is positive everywhere, so no bracket exists.

        The distinction the error message has to preserve is "no root here" against "the
        search was too timid", which is why the widest interval tried is reported.
        """
        with self.assertRaises(ConvergenceError) as caught:
            numerics.bracket_sign_change(lambda x: x * x + 1.0, lower=0.0, upper_guess=1.0)
        error = caught.exception
        self.assertIn("no sign change", str(error))
        self.assertIsNotNone(error.last_value)
        self.assertGreater(error.last_value, 1.0)

    def test_raises_when_the_search_is_too_timid(self):
        """Property: the negative control. A real root is missed only if the budget stops it.

        The same function that succeeds with a generous expansion budget must fail with
        a budget of two expansions. Without this, the previous test's failure could
        equally be explained by the search never expanding at all.
        """
        with self.assertRaises(ConvergenceError):
            numerics.bracket_sign_change(lambda x: x - 1.0e6, lower=0.0, upper_guess=1.0, max_expansions=2)
        lower, upper = numerics.bracket_sign_change(
            lambda x: x - 1.0e6, lower=0.0, upper_guess=1.0, max_expansions=40
        )
        self.assertLessEqual(lower, 1.0e6)
        self.assertGreaterEqual(upper, 1.0e6)

    def test_rejects_an_upper_guess_below_the_lower_bound(self):
        """Invalid input: an inverted search interval."""
        with self.assertRaises(InvalidInputError):
            numerics.bracket_sign_change(math.sin, lower=1.0, upper_guess=0.5)

    def test_finds_a_bracket_at_extreme_residual_magnitudes(self):
        """Property: the search is decided by signs, not by a product that underflows.

        Same root cause as the two sign-underflow tests in
        SafeguardedNewtonTests. `f_low * f_up` underflows to zero for residuals of
        magnitude 1e-180, so a function that plainly changes sign at 4.5 is reported as
        having no sign change anywhere out to 1e24. The unit-scale control below is the
        positive control: the identical search succeeds there.
        """
        scale = 1.0e-180
        control = numerics.bracket_sign_change(lambda x: x - 4.5, lower=0.0, upper_guess=1.0)
        self.assertLessEqual(control[0], 4.5)
        self.assertGreaterEqual(control[1], 4.5)
        lower, upper = numerics.bracket_sign_change(lambda x: scale * (x - 4.5), lower=0.0, upper_guess=1.0)
        self.assertLessEqual(lower, 4.5)
        self.assertGreaterEqual(upper, 4.5)


class HashingTests(unittest.TestCase):
    """Digest helpers against published test vectors."""

    #: FIPS 180-2 Appendix B.1: the one-block example, message "abc".
    SHA256_OF_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"

    #: FIPS 180-2 Appendix B.2: the two-block example, 448 bits.
    SHA256_TWO_BLOCK_MESSAGE = b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"
    SHA256_OF_TWO_BLOCK = "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"

    #: FIPS 180-2 Appendix B.3: one million repetitions of the character "a".
    SHA256_OF_A_MILLION_A = "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0"

    #: NIST CAVP SHA-256 short-message vectors, SHA256ShortMsg.rsp, the Len = 0 entry.
    #: The attribution matters: this digest is *not* in FIPS 180-2 Appendix B, whose
    #: three worked examples are B.1, B.2 and B.3 above. Citing a source that does not
    #: contain the value is the same class of mistake as transcribing the value wrongly.
    SHA256_OF_EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_sha256_bytes_against_the_published_vectors(self):
        """Independent oracle: all three FIPS 180-2 worked examples, plus the CAVP Len=0.

        The three appendix vectors are one block, two blocks, and 15625 blocks, so they
        exercise a single compression call, the length-padding spill into a second block,
        and the long-message loop. The empty message is the padding-only case.
        """
        self.assertEqual(provenance.sha256_bytes(b"abc"), self.SHA256_OF_ABC)
        self.assertEqual(provenance.sha256_bytes(self.SHA256_TWO_BLOCK_MESSAGE), self.SHA256_OF_TWO_BLOCK)
        self.assertEqual(provenance.sha256_bytes(b"a" * 1000000), self.SHA256_OF_A_MILLION_A)
        self.assertEqual(provenance.sha256_bytes(b""), self.SHA256_OF_EMPTY)

    def test_sha256_file_agrees_with_the_same_bytes(self):
        """Property: the streaming file digest equals the in-memory digest.

        The file helper reads in 64 KiB blocks, so the payload here deliberately spans
        several blocks. A block-boundary bug is invisible on a short file.
        """
        payload = b"abc" + bytes(range(256)) * 1024
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "payload.bin"
            path.write_bytes(payload)
            self.assertEqual(provenance.sha256_file(path), provenance.sha256_bytes(payload))

    def test_canonical_hash_is_the_digest_of_a_stated_canonical_form(self):
        """Independent oracle: the canonical bytes, written out by hand and hashed here.

        Every other test of canonical_hash compares one of its outputs against another
        of its outputs, which shows the function is consistent with itself and nothing
        more. This one states what the canonical serialisation is -- keys sorted, no
        whitespace -- writes those bytes as a literal, and hashes them with hashlib
        directly. It fails if the separators, the key ordering or the float formatting
        ever change, which is what "stable across runs" has to mean for a digest that is
        recorded in a run record and compared months later.
        """
        payload = {"seed": 20260913, "noise_psi": 0.0, "grids": [4, 8, 16]}
        canonical = b'{"grids":[4,8,16],"noise_psi":0.0,"seed":20260913}'
        self.assertEqual(provenance.canonical_hash(payload), hashlib.sha256(canonical).hexdigest())

    def test_canonical_hash_ignores_insertion_order(self):
        """Property: two configurations differing only in key order are the same configuration."""
        first = provenance.canonical_hash({"alpha": 1, "beta": {"x": 1, "y": 2}, "gamma": [1, 2]})
        second = provenance.canonical_hash({"gamma": [1, 2], "beta": {"y": 2, "x": 1}, "alpha": 1})
        self.assertEqual(first, second)

    def test_canonical_hash_is_sensitive_to_any_value_change(self):
        """Property: the hash is the config's identity, so every field must reach it."""
        base = {"noise_psi": 0.0, "seed": 20260913, "label": "clean", "grids": [4, 8, 16]}
        base_hash = provenance.canonical_hash(base)
        mutations = (
            {"noise_psi": 1e-12},
            {"seed": 20260914},
            {"label": "Clean"},
            {"grids": [4, 8, 32]},
            {"extra": None},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                changed = dict(base)
                changed.update(mutation)
                self.assertNotEqual(provenance.canonical_hash(changed), base_hash)

    def test_canonical_hash_respects_list_order(self):
        """Property: a list is ordered data, unlike a mapping's keys."""
        self.assertNotEqual(
            provenance.canonical_hash({"g": [1, 2]}), provenance.canonical_hash({"g": [2, 1]})
        )

    def test_canonical_hash_is_deterministic(self):
        """Property: contract C4. Equal arguments, equal result, every time."""
        payload = {"a": [1, {"b": 2.5}], "c": "text"}
        self.assertEqual(provenance.canonical_hash(payload), provenance.canonical_hash(payload))


class RunRecordTests(unittest.TestCase):
    """Write-once run directories, verification, and the recording of failures."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _completed_run(self, name: str = "run-001") -> pathlib.Path:
        source = self.root / f"{name}-input.txt"
        source.write_text("pressure_psia,z_factor\n3000,0.86\n", encoding="utf-8")
        directory = self.root / name
        with provenance.RunRecord.open(
            directory,
            label="foundation test run",
            config={"noise_psi": 0.0},
            seed=20260913,
            settings={"method": "simpson"},
            repo_root=self.root,
        ) as run:
            run.add_input(source)
            run.write_json("results.json", {"giip_scf": 1.0e10})
            run.write_text("report.md", "no claim beyond the evidence\n")
            run.note("checked against the analytic value")
            run.limitation("synthetic data, not a field history")
            run.metric("giip_error_percent", 0.0)
            run.metrics(intervals=64, converged=True)
        return directory

    def test_a_run_directory_is_written_once(self):
        """Invalid input: reopening a non-empty run directory raises InvalidInputError.

        This is the rule that makes the record trustworthy. If a rerun could overwrite,
        the directory would record only the most recent attempt and an ensemble could be
        pruned to the results someone liked without leaving a trace.
        """
        directory = self._completed_run()
        with self.assertRaises(InvalidInputError) as caught:
            provenance.RunRecord.open(directory, label="second attempt")
        self.assertIn("written once", str(caught.exception))

    def test_an_empty_existing_directory_is_acceptable(self):
        """Limiting case: an empty directory holds no previous result to destroy."""
        directory = self.root / "prepared"
        directory.mkdir()
        with provenance.RunRecord.open(directory, label="into a prepared directory") as run:
            run.note("nothing here to overwrite")
        self.assertEqual(provenance.load_run_record(directory)["status"], "completed")

    def test_a_path_that_is_a_file_is_rejected(self):
        """Invalid input: a run directory cannot be an existing file."""
        path = self.root / "not-a-directory"
        path.write_text("x", encoding="utf-8")
        with self.assertRaises(InvalidInputError):
            provenance.RunRecord.open(path, label="bad path")

    def test_declaring_a_file_that_does_not_exist_is_rejected(self):
        """Invalid input: a declared input must be hashable now, not promised for later."""
        directory = self.root / "run-missing-input"
        with (
            self.assertRaises(InvalidInputError),
            provenance.RunRecord.open(directory, label="missing input") as run,
        ):
            run.add_input(self.root / "absent.csv")

    def test_the_record_captures_what_it_promises(self):
        """Property: the fields the module docstring commits to are all present and filled."""
        directory = self._completed_run()
        record = provenance.load_run_record(directory)

        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["label"], "foundation test run")
        self.assertEqual(record["seed"], 20260913)
        self.assertEqual(record["config"], {"noise_psi": 0.0})
        # Hashed against the canonical bytes written out here, not against another call
        # to canonical_hash. Comparing the record to the function that filled it would
        # check the plumbing -- right digest in the right field -- while passing on any
        # implementation of the digest at all, including one that hashed the empty
        # string. The value of the digest and its placement are separate claims.
        self.assertEqual(record["config_sha256"], hashlib.sha256(b'{"noise_psi":0.0}').hexdigest())
        self.assertEqual(record["settings_sha256"], hashlib.sha256(b'{"method":"simpson"}').hexdigest())
        self.assertEqual(record["schema_version"], provenance.RECORD_SCHEMA_VERSION)
        self.assertIn("checked against the analytic value", record["notes"])
        self.assertIn("synthetic data, not a field history", record["limitations"])
        self.assertEqual(record["metrics"]["giip_error_percent"], 0.0)
        self.assertEqual(record["metrics"]["intervals"], 64)
        self.assertGreaterEqual(record["elapsed_seconds"], 0.0)
        self.assertIn("python_version", record["environment"])
        # Presence only. What these fields are worth is settled in
        # SourceRevisionAndEnvironmentTests, against a repository built for the purpose;
        # a run record written from a temporary directory that is not a checkout has
        # nothing to say about whether the dirty detector works.
        for key in ("commit", "dirty", "branch", "describe"):
            self.assertIn(key, record["source_revision"])

        roles = sorted(entry["role"] for entry in record["files"])
        self.assertEqual(roles, ["input", "output", "output"])
        self.assertNotIn("failure", record)

    def test_verify_returns_empty_for_an_untouched_run(self):
        """Property: a run nobody has edited verifies clean."""
        directory = self._completed_run()
        self.assertEqual(provenance.verify_run_record(directory), [])

    def test_verify_reports_an_edited_file(self):
        """Property: the detector fires on a one-byte edit and names the file.

        The previous test is the negative control for this one: the same run verifies
        clean before the edit, so an empty list is evidence of integrity rather than of
        a verifier that never looks.
        """
        directory = self._completed_run()
        edited = self.root / "run-001-input.txt"
        edited.write_text("pressure_psia,z_factor\n3000,0.87\n", encoding="utf-8")

        problems = provenance.verify_run_record(directory)
        self.assertEqual(len(problems), 1)
        self.assertIn("changed", problems[0])
        self.assertIn("run-001-input.txt", problems[0])

    def test_verify_reports_a_deleted_file(self):
        """Property: a missing declared file is reported, not silently skipped."""
        directory = self._completed_run()
        (directory / "report.md").unlink()
        problems = provenance.verify_run_record(directory)
        self.assertEqual(len(problems), 1)
        self.assertIn("missing", problems[0])
        self.assertIn("report.md", problems[0])

    def test_verify_requires_a_record_to_be_present(self):
        """Invalid input: verifying a directory with no record raises rather than passing."""
        empty = self.root / "no-record"
        empty.mkdir()
        with self.assertRaises(InvalidInputError):
            provenance.verify_run_record(empty)

    def test_a_failed_run_is_recorded_and_the_exception_propagates(self):
        """Property: a failure is a result, and it is not allowed to vanish.

        Two things are asserted together because each alone would be satisfiable by a
        broken implementation. A context manager that swallowed the exception would
        write a fine-looking record; one that re-raised without writing would leave no
        evidence the run happened. The record must exist, say "failed", carry the
        traceback, and the caller must still see the exception.
        """
        directory = self.root / "run-failed"
        with (
            self.assertRaises(ZeroDivisionError),
            provenance.RunRecord.open(directory, label="deliberate failure", seed=1) as run,
        ):
            run.metric("reached", "before the failure")
            _ = 1.0 / 0

        record = provenance.load_run_record(directory)
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["failure"]["type"], "ZeroDivisionError")
        self.assertIn("division by zero", record["failure"]["message"])
        traceback_text = record["failure"]["traceback"]
        self.assertIn("ZeroDivisionError", traceback_text)
        self.assertIn("test_foundation.py", traceback_text)
        # Whatever was recorded before the failure survives; a failed run is still a run.
        self.assertEqual(record["metrics"]["reached"], "before the failure")

    def test_a_package_error_inside_a_run_is_recorded_with_its_own_type(self):
        """Property: the record names the package's own exception, not a generic one."""
        directory = self.root / "run-failed-package-error"
        with (
            self.assertRaises(NotIdentifiableError),
            provenance.RunRecord.open(directory, label="not identifiable") as run,
        ):
            run.note("attempting an x-intercept from a flat line")
            raise NotIdentifiableError("slope is not distinguishable from zero")

        record = provenance.load_run_record(directory)
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["failure"]["type"], "NotIdentifiableError")

    def test_iter_run_records_finds_failed_and_completed_runs(self):
        """Property: a register that lists only the successes is not a register."""
        self._completed_run("run-001")
        self._completed_run("run-002")
        failed = self.root / "nested" / "run-003"
        with self.assertRaises(RuntimeError), provenance.RunRecord.open(failed, label="third"):
            raise RuntimeError("boom")

        found = dict(provenance.iter_run_records(self.root))
        self.assertEqual(len(found), 3)
        statuses = sorted(record["status"] for record in found.values())
        self.assertEqual(statuses, ["completed", "completed", "failed"])
        self.assertIn(failed, found)

    def test_iter_run_records_is_empty_for_a_directory_with_no_runs(self):
        """Limiting case: nothing recorded yields nothing, and does not raise."""
        self.assertEqual(list(provenance.iter_run_records(self.root)), [])

    def test_written_artefacts_are_hashed_as_stored(self):
        """Property: the recorded digest matches the bytes actually on disk."""
        directory = self._completed_run()
        record = provenance.load_run_record(directory)
        for entry in record["files"]:
            with self.subTest(path=entry["path"]):
                path = pathlib.Path(entry["path"])
                self.assertEqual(provenance.sha256_file(path), entry["sha256"])
                self.assertEqual(path.stat().st_size, entry["bytes"])

    def test_the_record_is_valid_json_with_a_trailing_newline(self):
        """Property: the record is readable by any tool, not only by this module."""
        directory = self._completed_run()
        text = (directory / provenance.RUN_RECORD_FILENAME).read_text(encoding="utf-8")
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(json.loads(text)["label"], "foundation test run")


GIT_AVAILABLE = shutil.which("git") is not None

#: A git invocation that depends on nothing in the developer's own configuration: no
#: identity, no signing key, no hooks. Without these a test repository built here would
#: inherit whatever the machine happens to have configured, and would fail on a machine
#: that signs every commit.
GIT_COMMAND = (
    "git",
    "-c",
    "user.name=foundation test",
    "-c",
    "user.email=foundation-test@example.com",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "core.hooksPath=/dev/null",
)


class SourceRevisionAndEnvironmentTests(unittest.TestCase):
    """The descriptive parts of a record, which must be honest when they cannot be sure."""

    def _git(self, *args: str, cwd: pathlib.Path) -> None:
        subprocess.run([*GIT_COMMAND, "-C", str(cwd), *args], check=True, capture_output=True, text=True)

    def _repository_with_one_commit(self, root: pathlib.Path) -> pathlib.Path:
        """Build a one-commit git repository and return the path of its tracked file."""
        subprocess.run(
            [*GIT_COMMAND, "init", "-q", "-b", "main", str(root)],
            check=True,
            capture_output=True,
            text=True,
        )
        tracked = root / "tracked.txt"
        tracked.write_text("committed content\n", encoding="utf-8")
        self._git("add", "tracked.txt", cwd=root)
        self._git("commit", "-q", "-m", "initial", cwd=root)
        return tracked

    def test_source_revision_always_reports_the_same_keys(self):
        """Property: a run outside version control is recorded as such, not blocked."""
        with tempfile.TemporaryDirectory() as tmp:
            revision = provenance.source_revision(tmp)
        for key in ("repo_root", "commit", "branch", "describe", "dirty"):
            self.assertIn(key, revision)
        self.assertIsNone(revision["commit"])
        self.assertIsNone(revision["dirty"])

    @unittest.skipUnless(GIT_AVAILABLE, "git is not installed")
    def test_the_dirty_flag_answers_the_question_the_module_exists_to_answer(self):
        """Property: clean tree reports False, edited tree reports True.

        "Was this result produced from a clean checkout" is the whole point of the
        record, and until now `dirty` was checked for the presence of its key and never
        for its value: an implementation that always wrote None -- "I do not know
        whether the tree was dirty" -- passed every test in this file.

        The two halves are each other's control. Asserting True on an edited tree alone
        would pass on a detector wired to a constant; asserting False on a clean one
        alone would pass on the opposite constant. The commit hash is the same across
        both calls, which is the evidence that the two observations describe the same
        repository at the same revision, and `describe --dirty` is a second, independent
        git subcommand that has to agree with `status --porcelain`.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            tracked = self._repository_with_one_commit(root)

            clean = provenance.source_revision(root)
            self.assertIs(clean["dirty"], False)
            self.assertIsNotNone(clean["commit"])
            self.assertEqual(len(clean["commit"]), 40)
            self.assertEqual(clean["branch"], "main")
            self.assertFalse(clean["describe"].endswith("-dirty"))

            tracked.write_text("edited content\n", encoding="utf-8")
            edited = provenance.source_revision(root)
            self.assertIs(edited["dirty"], True)
            self.assertEqual(edited["commit"], clean["commit"])
            self.assertTrue(edited["describe"].endswith("-dirty"))

    @unittest.skipUnless(GIT_AVAILABLE, "git is not installed")
    def test_dirty_paths_names_the_modified_file(self):
        """Property: the record says *what* was dirty, not only that something was.

        Found while writing the test above; fixed, and guarded here. `_git` returns
        `completed.stdout.strip()`, and `git status --porcelain` encodes the status in
        the first two columns, so an unstaged modification arrives as " M tracked.txt"
        and the strip removes its leading space. `source_revision` then slices `line[3:]`
        from a line that is one character short and records the path as "racked.txt".
        Only the first and last lines of the status output are affected, which is why it
        survived: with two or more dirty files the middle entries look right.

        The fix applied in src/reservoir_lab/provenance.py was to strip only the trailing
        newline, or parse the porcelain columns -- and is outside this allocation.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            tracked = self._repository_with_one_commit(root)
            tracked.write_text("edited content\n", encoding="utf-8")
            revision = provenance.source_revision(root)
        self.assertEqual(revision["dirty_paths"], ["tracked.txt"])

    def test_environment_reports_the_running_interpreter(self):
        """Independent oracle: the interpreter described through APIs the module does not use.

        provenance.environment() reads `sys.version` and `platform.python_implementation()`.
        Comparing against those same two expressions would be a change detector, not an
        oracle: the same call on both sides cannot disagree. These two routes are
        genuinely different. `sys.version_info` is a structseq built by the interpreter
        rather than a string it formats and `platform` then parses, and
        `sys.implementation.name` is set by the implementation itself in lower case.

        `startswith` rather than equality on the version because a pre-release build
        reports "3.14.0rc1" in sys.version while sys.version_info[:3] is (3, 14, 0); the
        three numbers are what is being checked, and they must match exactly.
        """
        described = provenance.environment()
        numeric_version = ".".join(str(part) for part in sys.version_info[:3])
        self.assertTrue(
            described["python_version"].startswith(numeric_version),
            f"{described['python_version']!r} does not start with {numeric_version!r}",
        )
        self.assertEqual(described["python_implementation"].lower(), sys.implementation.name.lower())
        self.assertIsInstance(described["imported_package_versions"], dict)
        # The record must describe the interpreter that is actually running this test.
        self.assertEqual(described["python_executable"], sys.executable)


if __name__ == "__main__":
    unittest.main()

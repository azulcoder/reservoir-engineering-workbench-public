"""Verification of the real-gas pseudopressure transform.

The four contract categories (``docs/api_contract.md`` C7) map onto this file as
follows.

Independent oracle
    Three closed forms that the module does not contain -- the constant-property
    integral, a logarithmic case where Simpson is not exact, and a quadratic-integrand
    case where it is -- plus the ideal-gas limit of Table 1 of Al-Hussainy, Ramey and
    Crawford (1966), compared against values read from the primary paper.

Limiting case
    Constant ``mu Z``, where the integrand is first degree and any rule of degree of
    exactness one or better must reproduce the answer to machine precision; and zero
    interval width, where the answer is exactly zero.

Invalid input
    Every documented raise, including the failure of the supplied ``mu_z`` callable
    itself, which is the realistic way a deviation-factor solve on the wrong root
    reaches the quadrature.

Property or invariant
    Sign, antisymmetry under reversed limits, additivity over adjacent intervals,
    datum invariance of differences against datum dependence of absolute values,
    monotonicity, inverse scaling in ``mu Z``, the derivative identity
    ``dm/dp = 2p/(mu Z)``, determinism, and the demonstrated order of accuracy.

No expected value here was produced by ``reservoir_lab.pseudopressure``.
"""

from __future__ import annotations

import dataclasses
import itertools
import math
import unittest
from decimal import Decimal
from fractions import Fraction
from typing import ClassVar

from reservoir_lab.errors import InvalidInputError, NotIdentifiableError
from reservoir_lab.pseudopressure import (
    DEFAULT_INTERVALS,
    SIMPSON_ORDER_WINDOW,
    SUPPORTED_METHODS,
    ConvergenceResult,
    convergence_study,
    pseudopressure,
    pseudopressure_constant_properties,
)

# ---------------------------------------------------------------------------
# Synthetic but smooth PVT behaviour, used wherever the integrand must be C-infinity
# for the convergence argument to mean anything. These are analytic functions with
# roughly the right shape and magnitude for a natural gas at reservoir temperature;
# they are not a correlation and no physical claim is made for them. The purpose is to
# separate quadrature error from correlation error, which is impossible if the two are
# measured together.
# ---------------------------------------------------------------------------

SMOOTH_INTERVAL_PSIA = (14.7, 8000.0)


def smooth_viscosity_cp(pressure_psia: float) -> float:
    return 0.0125 * (1.0 + 1.1e-4 * pressure_psia + 2.0e-9 * pressure_psia**2)


def smooth_z_factor(pressure_psia: float) -> float:
    return 1.0 - 2.1e-4 * pressure_psia + 3.0e-8 * pressure_psia**2 + 1.0e-12 * pressure_psia**3


def smooth_mu_z(pressure_psia: float) -> float:
    return smooth_viscosity_cp(pressure_psia) * smooth_z_factor(pressure_psia)


def constant_mu_z(value: float):
    """Return a ``mu_z`` callable that ignores pressure."""

    def mu_z(_pressure_psia: float) -> float:
        return value

    return mu_z


#: One unit in the last place, at a relative scale of one. Used where the claim is
#: "machine precision" and the arithmetic is short enough that saying so is honest.
ULP = 2.220446049250313e-16

#: The pseudopressure integral of :func:`smooth_mu_z` over :data:`SMOOTH_INTERVAL_PSIA`,
#: computed outside this package and outside double precision. Every convergence
#: assertion below is anchored to this number rather than to a finely refined run of the
#: module itself, because a reference produced by the same rule with the same
#: accumulation shares the module's round-off and therefore cannot measure it.
#:
#: Derivation, reproducible with ``pip install mpmath``::
#:
#:     import mpmath as mp
#:     mp.mp.dps = 50
#:     mu = lambda p: mp.mpf(0.0125) * (1 + mp.mpf(1.1e-4)*p + mp.mpf(2.0e-9)*p**2)
#:     z = lambda p: 1 - mp.mpf(2.1e-4)*p + mp.mpf(3.0e-8)*p**2 + mp.mpf(1.0e-12)*p**3
#:     mp.quad(lambda p: 2*p/(mu(p)*z(p)), [mp.mpf(14.7), mp.mpf(8000.0)])
#:     # -> 3483863807.85917679014681435215
#:
#: Wrapping each float literal in ``mp.mpf`` reproduces the exact binary coefficients
#: the module integrates, so this is the integral of the same integrand and not of a
#: decimal lookalike. Splitting the interval into four panels changes no digit of the
#: fifty, and SciPy's QUADPACK in float64 returns the same double. The figure
#: 3.4838638079e9 quoted in the evidence review is this number truncated to eleven
#: digits; it is checked against this one below and otherwise superseded by it.
SMOOTH_REFERENCE_PSIA2_PER_CP = 3483863807.8591766

#: Jump in the third derivative of the integrand ``f(p) = 2p/(mu(p) Z(p))`` across
#: :data:`SMOOTH_INTERVAL_PSIA`, i.e. ``f'''(8000) - f'''(14.7)``, in psia^2/cp per
#: psia^3. This is the only quantity the composite Simpson error constant needs: the
#: leading Euler-Maclaurin term is ``S_n - I = (h^4/180) (f'''(b) - f'''(a))``. Obtained
#: by symbolic differentiation at fifty digits in the same session as the reference
#: above::
#:
#:     mp.diff(f, mp.mpf(8000.0), 3) - mp.diff(f, mp.mpf(14.7), 3)
#:     # -> 1.41872171583e-6
SMOOTH_THIRD_DERIVATIVE_JUMP = 1.41872171583e-6


# ---------------------------------------------------------------------------
# Al-Hussainy, Ramey & Crawford (1966), Table 1, page 34 of the retrieved scan.
#
# Header convention, read from the table and confirmed against the Fig. 2 ordinate:
#
#     F(T_pr, p_pr) = mu_1 * m(p) / (2 * p_pc^2 * T_pr)
#                   = integral from 0.20 to p_pr of  p' dp' / [ T_pr (mu/mu_1) Z ]
#
# The 1/T_pr sits inside the tabulated integral, and the lower limit 0.20 is the
# authors' arbitrary datum choice for the chart, not a physical constant.
#
# Only values transcribed directly from the scan appear here. The entry at
# T_pr = 1.50, p_pr = 5.00 is 6.6377; an earlier transcription recorded 6.3770, a digit
# transposition, and the neighbours test below is what keeps that correction from
# quietly reverting.
# ---------------------------------------------------------------------------

TABLE_1 = {
    (1.05, 1.00): 0.5326,
    (1.05, 2.00): 2.3821,
    (1.05, 3.00): 4.0165,
    (1.05, 5.00): 6.6368,
    (1.15, 5.00): 6.7235,
    (1.15, 8.50): 11.1935,
    (1.30, 5.00): 6.9714,
    (1.50, 1.00): 0.3246,
    (1.50, 2.00): 1.3164,
    (1.50, 4.75): 6.1412,
    (1.50, 5.00): 6.6377,
    (1.50, 5.25): 7.1355,
    (1.50, 10.00): 16.3205,
    (1.50, 15.00): 24.9921,
    (1.75, 5.00): 6.0234,
    (2.00, 1.00): 0.2397,
    (2.00, 2.00): 0.9653,
    (2.00, 5.00): 5.3860,
    (2.00, 10.00): 16.0274,
    (2.00, 15.00): 27.0862,
    (2.50, 0.50): 0.0421,
    (2.50, 5.00): 4.4664,
    (3.00, 0.50): 0.0349,
    (3.00, 1.00): 0.1580,
    (3.00, 2.00): 0.6378,
    (3.00, 5.00): 3.7865,
    (3.00, 10.00): 13.2545,
    (3.00, 15.00): 25.3268,
}

#: Lower limit of the reduced integral chosen by the authors for Table 1 and Fig. 2.
TABLE_1_REDUCED_DATUM = 0.20


def table_1_ideal_limit(t_pr: float, p_pr: float) -> float:
    """Ideal-gas limit of the tabulated integral: ``(p_pr^2 - 0.04) / (2 T_pr)``.

    As ``mu/mu_1 -> 1`` and ``Z -> 1`` the tabulated integrand collapses to
    ``p_pr / T_pr`` and the integral from the authors' datum 0.20 is elementary. The
    0.04 is ``0.20^2``. This is the paper's own dashed ideal-gas line in Fig. 1.
    """
    return (p_pr**2 - TABLE_1_REDUCED_DATUM**2) / (2.0 * t_pr)


def reduced_pseudopressure_ideal(
    t_pr: float,
    p_pr: float,
    *,
    pseudocritical_pressure_psia: float,
    viscosity_at_one_atmosphere_cp: float,
    intervals: int = 8,
) -> float:
    """Compute the paper's tabulated group from :func:`pseudopressure`, ideal gas.

    Runs the module's own quadrature in field units over ``[0.20 p_pc, p_pr p_pc]``
    with ``mu Z = mu_1`` (the ideal limit, where ``mu/mu_1 = 1`` and ``Z = 1``), then
    forms ``mu_1 m / (2 p_pc^2 T_pr)``. Both ``p_pc`` and ``mu_1`` must cancel, which
    is itself checked below.
    """
    m = pseudopressure(
        p_pr * pseudocritical_pressure_psia,
        reference_psia=TABLE_1_REDUCED_DATUM * pseudocritical_pressure_psia,
        mu_z=constant_mu_z(viscosity_at_one_atmosphere_cp),
        intervals=intervals,
    )
    return viscosity_at_one_atmosphere_cp * m / (2.0 * pseudocritical_pressure_psia**2 * t_pr)


class ConstantPropertyOracleTests(unittest.TestCase):
    """Exact closed form: ``m(p) - m(p_ref) = (p^2 - p_ref^2) / (mu Z)``.

    With ``mu Z`` constant the integrand is first degree, so composite Simpson is exact
    on any even grid, down to two panels. A failure here is a factor of 2, a datum, or
    panel bookkeeping -- not physics.
    """

    def test_closed_form_matches_hand_value(self):
        # Hand arithmetic, independent of the module: (5000^2 - 14.7^2)/(0.02*0.9).
        expected = (25_000_000.0 - 216.09) / 0.018
        got = pseudopressure_constant_properties(5000.0, reference_psia=14.7, viscosity_cp=0.02, z_factor=0.9)
        self.assertLessEqual(abs(got - expected) / expected, 2.0 * ULP)
        self.assertAlmostEqual(got / 1.388876883889e9, 1.0, places=11)

    def test_two_panel_simpson_reproduces_closed_form(self):
        closed = pseudopressure_constant_properties(
            5000.0, reference_psia=14.7, viscosity_cp=0.02, z_factor=0.9
        )
        quadrature = pseudopressure(
            5000.0,
            reference_psia=14.7,
            mu_z=constant_mu_z(0.02 * 0.9),
            intervals=2,
        )
        self.assertLessEqual(abs(quadrature - closed) / abs(closed), 4.0 * ULP)

    def test_agreement_holds_across_grids_and_states(self):
        # The exactness is a property of the rule's degree, so it must not depend on
        # the panel count. Growing accumulation error over 1025 terms is why the
        # tolerance is 1e-14 rather than a few ulp at the finest grid.
        for viscosity_cp, z_factor in ((0.0125, 0.86), (0.0237, 1.13), (0.031, 0.70)):
            for reference_psia, pressure_psia in ((0.0, 3000.0), (14.7, 8000.0), (2500.0, 500.0)):
                for intervals in (2, 4, 16, 256, 1024):
                    with self.subTest(
                        viscosity_cp=viscosity_cp,
                        z_factor=z_factor,
                        reference_psia=reference_psia,
                        pressure_psia=pressure_psia,
                        intervals=intervals,
                    ):
                        closed = pseudopressure_constant_properties(
                            pressure_psia,
                            reference_psia=reference_psia,
                            viscosity_cp=viscosity_cp,
                            z_factor=z_factor,
                        )
                        quadrature = pseudopressure(
                            pressure_psia,
                            reference_psia=reference_psia,
                            mu_z=constant_mu_z(viscosity_cp * z_factor),
                            intervals=intervals,
                        )
                        self.assertTrue(
                            math.isclose(quadrature, closed, rel_tol=1.0e-14),
                            msg=f"{quadrature!r} vs {closed!r}",
                        )

    def test_default_intervals_are_usable_for_the_limiting_case(self):
        closed = pseudopressure_constant_properties(
            6000.0, reference_psia=100.0, viscosity_cp=0.02, z_factor=0.9
        )
        quadrature = pseudopressure(6000.0, reference_psia=100.0, mu_z=constant_mu_z(0.018))
        self.assertTrue(math.isclose(quadrature, closed, rel_tol=1.0e-14))


class ClosedFormQuadratureOracleTests(unittest.TestCase):
    """Closed forms where Simpson is, and is not, exact.

    The constant-property case alone is a weak oracle: it is exact for any rule of
    degree one or better, so it cannot distinguish Simpson from the trapezoid rule.
    These two cases can. Neither ``mu_z`` is a gas; both are manufactured integrands
    chosen because their integrals are elementary.
    """

    def test_logarithmic_closed_form(self):
        # mu(p) Z(p) = alpha p^2 gives integrand 2/(alpha p), hence
        # m = (2/alpha) ln(p / p_ref). Simpson is not exact on this one.
        alpha = 4.0e-9
        lower, upper = 200.0, 6400.0
        expected = (2.0 / alpha) * math.log(upper / lower)
        # 8192 panels, not the default: over a 32-fold pressure range a 1/p integrand
        # is far more curved than a real 2p/(mu Z), and at the default grid the
        # quadrature error is 8e-9 relative. That is the rule behaving exactly as
        # advertised, so the grid is raised rather than the tolerance loosened.
        got = pseudopressure(
            upper,
            reference_psia=lower,
            mu_z=lambda p: alpha * p * p,
            intervals=8192,
        )
        self.assertTrue(math.isclose(got, expected, rel_tol=1.0e-11), msg=f"{got!r} vs {expected!r}")

    def test_cubic_integrand_is_reproduced_exactly(self):
        # mu(p) Z(p) = 1/(1 + p) gives integrand 2p(1 + p) = 2p + 2p^2, a second-degree
        # polynomial. Simpson is exact to degree three, so two panels must suffice, and
        # that pins the rule's degree rather than merely its convergence.
        lower, upper = 10.0, 4000.0
        expected = (upper**2 - lower**2) + (2.0 / 3.0) * (upper**3 - lower**3)
        for intervals in (2, 8, 64):
            with self.subTest(intervals=intervals):
                got = pseudopressure(
                    upper,
                    reference_psia=lower,
                    mu_z=lambda p: 1.0 / (1.0 + p),
                    intervals=intervals,
                )
                self.assertTrue(math.isclose(got, expected, rel_tol=1.0e-14))


class AlHussainyTable1IdealLimitTests(unittest.TestCase):
    """The paper's own Table 1, in the ideal-gas limit where the definition is closed.

    The full Table 1 regression is deliberately not attempted. Reproducing the
    non-ideal entries requires the Standing-Katz deviation factor and the Carr,
    Kobayashi and Burrows viscosity ratio ``mu/mu_1`` on which the 1966 table was
    built, and neither is available here; a miss would then be unattributable between
    the deviation factor, the viscosity ratio and the quadrature. The ideal-gas limit
    is free of that ambiguity: it is a closed form, and it still pins the three things
    most easily got wrong -- the factor of 2, the arbitrary datum at ``p_pr = 0.20``,
    and the ``1/T_pr`` that sits inside the tabulated integral.
    """

    def test_module_reproduces_the_reduced_group_in_the_ideal_limit(self):
        for t_pr in (1.05, 1.50, 2.00, 2.50, 3.00):
            for p_pr in (0.50, 1.00, 2.00, 5.00):
                with self.subTest(t_pr=t_pr, p_pr=p_pr):
                    got = reduced_pseudopressure_ideal(
                        t_pr,
                        p_pr,
                        pseudocritical_pressure_psia=670.0,
                        viscosity_at_one_atmosphere_cp=0.0125,
                    )
                    self.assertTrue(math.isclose(got, table_1_ideal_limit(t_pr, p_pr), rel_tol=1.0e-13))

    def test_reduced_group_is_free_of_the_pseudocritical_and_mu_1(self):
        # p_pc and mu_1 cancel algebraically. If they do not cancel numerically, the
        # reduced-variable convention has been misread, which is exactly the error that
        # would silently rescale every result taken off the paper's chart.
        first = reduced_pseudopressure_ideal(
            1.75, 3.00, pseudocritical_pressure_psia=640.0, viscosity_at_one_atmosphere_cp=0.0110
        )
        second = reduced_pseudopressure_ideal(
            1.75, 3.00, pseudocritical_pressure_psia=712.0, viscosity_at_one_atmosphere_cp=0.0193
        )
        self.assertTrue(math.isclose(first, second, rel_tol=1.0e-13))

    def test_published_entries_approach_the_ideal_limit_where_expected(self):
        # Tolerance 1.5 percent, not the tighter figure that a first reading of the
        # data suggests: the table's own entry at T_pr = 3.00, p_pr = 1.00 deviates by
        # 1.25 percent, so anything tighter fails on the source's own numbers.
        for t_pr, p_pr in ((2.00, 1.00), (2.50, 0.50), (3.00, 0.50), (3.00, 1.00)):
            with self.subTest(t_pr=t_pr, p_pr=p_pr):
                published = TABLE_1[(t_pr, p_pr)]
                computed = reduced_pseudopressure_ideal(
                    t_pr,
                    p_pr,
                    pseudocritical_pressure_psia=670.0,
                    viscosity_at_one_atmosphere_cp=0.0125,
                )
                self.assertLess(abs(published / computed - 1.0), 0.015)


class Table1TranscriptionGuardTests(unittest.TestCase):
    """Guards on the transcribed table itself. These exercise no module code.

    Both tests below read only the ``TABLE_1`` literal and the local
    ``table_1_ideal_limit`` helper. They catch a digit transposed while copying the
    scan, which is a real failure mode and worth a test, but they prove nothing about
    ``reservoir_lab.pseudopressure`` and are kept out of the paper-regression class so
    that nobody counts them as evidence about the implementation.
    """

    def test_deviation_from_ideal_decreases_with_reduced_temperature(self):
        # At fixed p_pr the ratio table/ideal falls monotonically with T_pr and crosses
        # unity; below the crossing Z < 1 raises the integrand, above it the rising
        # mu/mu_1 and Z > 1 lower it. What must NOT be asserted is that the magnitude of
        # the deviation grows as T_pr falls: between T_pr 2.00 and 3.00 it grows as
        # T_pr RISES, and a test written the other way round fails on real data.
        ratios = [
            TABLE_1[(t_pr, 1.00)] / table_1_ideal_limit(t_pr, 1.00) for t_pr in (1.05, 1.50, 2.00, 3.00)
        ]
        self.assertEqual(ratios, sorted(ratios, reverse=True))
        self.assertGreater(ratios[1], 1.0)  # T_pr = 1.50, still below the crossing
        self.assertLess(ratios[2], 1.0)  # T_pr = 2.00, above it

    def test_corrected_table_entry_is_consistent_with_its_neighbours(self):
        # A transcription guard, not a check on the module. The T_pr = 1.50 column at
        # p_pr = 5.00 reads 6.6377; a transposed 6.3770 would break the smoothness of a
        # column that is a cumulative integral over a uniform 0.25 step in p_pr. The
        # increments either side agree to better than one percent as written, and
        # differ by a factor of three if the digits are transposed.
        below = TABLE_1[(1.50, 4.75)]
        entry = TABLE_1[(1.50, 5.00)]
        above = TABLE_1[(1.50, 5.25)]
        lower_increment = entry - below
        upper_increment = above - entry
        self.assertGreater(lower_increment, 0.0)
        self.assertLess(abs(upper_increment / lower_increment - 1.0), 0.01)


class SignDatumAndAdditivityTests(unittest.TestCase):
    """Invariants that follow from the definition alone."""

    def test_zero_width_interval_is_exactly_zero(self):
        for pressure_psia in (0.0, 14.7, 3500.0):
            with self.subTest(pressure_psia=pressure_psia):
                self.assertEqual(
                    pseudopressure(pressure_psia, reference_psia=pressure_psia, mu_z=smooth_mu_z),
                    0.0,
                )
                self.assertEqual(
                    pseudopressure_constant_properties(
                        pressure_psia,
                        reference_psia=pressure_psia,
                        viscosity_cp=0.02,
                        z_factor=0.9,
                    ),
                    0.0,
                )

    def test_sign_follows_the_limits(self):
        forward = pseudopressure(5000.0, reference_psia=1000.0, mu_z=smooth_mu_z)
        self.assertGreater(forward, 0.0)
        reverse = pseudopressure(1000.0, reference_psia=5000.0, mu_z=smooth_mu_z)
        self.assertLess(reverse, 0.0)

    def test_reversing_the_limits_negates_the_result_exactly(self):
        # Both directions evaluate the same node set, so this is bit-for-bit, not
        # approximate. A tolerance here would hide a rule that quietly reorders nodes.
        forward = pseudopressure(7000.0, reference_psia=250.0, mu_z=smooth_mu_z, intervals=64)
        reverse = pseudopressure(250.0, reference_psia=7000.0, mu_z=smooth_mu_z, intervals=64)
        self.assertEqual(forward, -reverse)

    def test_additive_over_adjacent_intervals_constant_properties(self):
        # Exact case first: with mu Z constant every piece is integrated exactly, so
        # additivity holds to round-off and nothing else.
        a, b, c = 300.0, 2200.0, 6800.0
        mu_z = constant_mu_z(0.0185)
        whole = pseudopressure(c, reference_psia=a, mu_z=mu_z, intervals=32)
        parts = pseudopressure(b, reference_psia=a, mu_z=mu_z, intervals=32) + pseudopressure(
            c, reference_psia=b, mu_z=mu_z, intervals=32
        )
        self.assertTrue(math.isclose(whole, parts, rel_tol=1.0e-14))

    def test_additive_over_adjacent_intervals_variable_properties(self):
        # With a varying mu Z the three integrals use three different grids, so
        # additivity holds only to quadrature error. The tolerance is stated against
        # the difference itself, never against an absolute m, because an m of order
        # 1e9 would make almost any error look small.
        a, b, c = 300.0, 2200.0, 6800.0
        whole = pseudopressure(c, reference_psia=a, mu_z=smooth_mu_z, intervals=512)
        parts = pseudopressure(b, reference_psia=a, mu_z=smooth_mu_z, intervals=512) + pseudopressure(
            c, reference_psia=b, mu_z=smooth_mu_z, intervals=512
        )
        self.assertTrue(math.isclose(whole, parts, rel_tol=1.0e-12), msg=f"{whole!r} vs {parts!r}")

    def test_difference_is_datum_free_while_the_value_is_not(self):
        lower_datum, upper_datum = 0.0, 500.0
        first, second = 1800.0, 6200.0
        from_zero = [
            pseudopressure(p, reference_psia=lower_datum, mu_z=smooth_mu_z, intervals=512)
            for p in (first, second)
        ]
        from_500 = [
            pseudopressure(p, reference_psia=upper_datum, mu_z=smooth_mu_z, intervals=512)
            for p in (first, second)
        ]
        difference_a = from_zero[1] - from_zero[0]
        difference_b = from_500[1] - from_500[0]
        self.assertTrue(
            math.isclose(difference_a, difference_b, rel_tol=1.0e-11),
            msg=f"{difference_a!r} vs {difference_b!r}",
        )

        # The absolute values, by contrast, differ by the datum shift, and they differ
        # by an amount far larger than the agreement just asserted. That asymmetry is
        # the whole reason an m value is meaningless without its datum recorded.
        offset = pseudopressure(upper_datum, reference_psia=lower_datum, mu_z=smooth_mu_z, intervals=512)
        self.assertGreater(offset, 0.0)
        for value_a, value_b in zip(from_zero, from_500, strict=True):
            self.assertGreater(abs(value_a - value_b), 1.0e-3 * abs(value_a))
            self.assertTrue(math.isclose(value_a - value_b, offset, rel_tol=1.0e-11))


class PropertyTests(unittest.TestCase):
    """Scaling, monotonicity, the derivative identity, and determinism."""

    def test_strictly_increasing_in_pressure(self):
        datum = 14.7
        values = [
            pseudopressure(p, reference_psia=datum, mu_z=smooth_mu_z, intervals=64)
            for p in (100.0, 500.0, 1500.0, 3000.0, 5000.0, 8000.0)
        ]
        self.assertEqual(values, sorted(values))
        self.assertTrue(all(b > a for a, b in itertools.pairwise(values)))

    def test_inverse_scaling_in_mu_z(self):
        # m is linear in 1/(mu Z), so scaling mu Z by a constant scales m by its
        # reciprocal exactly, whatever the pressure dependence.
        base = pseudopressure(6000.0, reference_psia=100.0, mu_z=smooth_mu_z, intervals=64)
        scaled = pseudopressure(
            6000.0,
            reference_psia=100.0,
            mu_z=lambda p: 2.5 * smooth_mu_z(p),
            intervals=64,
        )
        self.assertTrue(math.isclose(scaled * 2.5, base, rel_tol=1.0e-14))

    #: Predicted relative error of the central difference below, one entry per test
    #: pressure. Central-differencing m with step h returns m'(p) + (h^2/6) m'''(p),
    #: and m' is the integrand f, so the relative error is exactly (h^2/6) f''(p)/f(p)
    #: with h = 1 psi. Computed externally by symbolic differentiation of the analytic
    #: integrand at fifty digits, in the same session as
    #: :data:`SMOOTH_REFERENCE_PSIA2_PER_CP`::
    #:
    #:     mp.diff(f, mp.mpf(p), 2) / 6 / f(mp.mpf(p))
    #:
    #: These are a prediction, not a record of what the module produced.
    CENTRAL_DIFFERENCE_TRUNCATION: ClassVar[dict[float, float]] = {
        500.0: 5.926145537e-8,
        2000.0: -1.155082053e-8,
        4500.0: -2.239202414e-8,
        7000.0: 2.727847278e-9,
    }

    def test_derivative_identity(self):
        # dm/dp = 2p/(mu Z), the paper's Eqs. 15-16 and the algebraic reason the datum
        # cancels out of every derivative-based diagnostic. Central-differencing a
        # datum-referenced m is the way this bites in practice, so that is what is
        # differenced here rather than a direct narrow-interval integral.
        #
        # The gate is on the difference between the measured deviation and the
        # predicted truncation term above, not a loose absolute band on the deviation
        # itself. The previous rel_tol of 1e-6 sat 17 to 370 times above the deviations
        # it was measuring and so could not have caught a regression at the 1e-7 level,
        # even though the truncation error was available in closed form.
        #
        # Five percent of the predicted term is the band. What is left over after the
        # h^2 term is the h^4 term, smaller by h^2 f''''/f'' (of order 1e-6 here), plus
        # the quadrature error of the two integrals, which is about 3e-5 psia^2/cp each
        # and largely common to both, and the cancellation in forward - backward, worth
        # eps*m/(2h) = 4e-7 psia^2/cp against a derivative of order 1e6. All three are
        # below 1e-5 of the predicted term, so five percent is generous by four orders
        # and still ties the test to a derived quantity rather than to an observed one.
        step_psia = 1.0
        for pressure_psia, predicted in self.CENTRAL_DIFFERENCE_TRUNCATION.items():
            with self.subTest(pressure_psia=pressure_psia):
                forward = pseudopressure(
                    pressure_psia + step_psia,
                    reference_psia=14.7,
                    mu_z=smooth_mu_z,
                    intervals=1024,
                )
                backward = pseudopressure(
                    pressure_psia - step_psia,
                    reference_psia=14.7,
                    mu_z=smooth_mu_z,
                    intervals=1024,
                )
                numerical = (forward - backward) / (2.0 * step_psia)
                analytic = 2.0 * pressure_psia / smooth_mu_z(pressure_psia)
                deviation = numerical / analytic - 1.0
                self.assertLess(
                    abs(deviation - predicted),
                    0.05 * abs(predicted),
                    msg=f"{deviation!r} vs predicted {predicted!r}",
                )

    def test_repeated_calls_are_bit_identical(self):
        kwargs = {"reference_psia": 14.7, "mu_z": smooth_mu_z, "intervals": 128}
        first = pseudopressure(6000.0, **kwargs)
        second = pseudopressure(6000.0, **kwargs)
        self.assertEqual(first, second)

    def test_supported_methods_are_declared(self):
        self.assertIn("simpson", SUPPORTED_METHODS)
        self.assertEqual(DEFAULT_INTERVALS % 2, 0)
        self.assertGreater(DEFAULT_INTERVALS, 0)


class ConvergenceStudyTests(unittest.TestCase):
    """The order of accuracy is demonstrated by refinement, never asserted."""

    def test_observed_order_approaches_four_on_a_smooth_integrand(self):
        lower, upper = SMOOTH_INTERVAL_PSIA
        study = convergence_study(
            upper,
            reference_psia=lower,
            mu_z=smooth_mu_z,
            interval_counts=(64, 128, 256, 512, 1024),
        )
        self.assertEqual(study.method, "simpson")
        self.assertEqual(len(study.observed_orders), 3)
        for order in study.observed_orders:
            self.assertTrue(math.isfinite(order))
            self.assertGreater(order, 3.7)
            self.assertLess(order, 4.3)
        self.assertGreater(study.last_estimable_order(), 3.7)

        # The grids used must sit inside the window where the order is legible at all.
        self.assertGreaterEqual(min(study.interval_counts), SIMPSON_ORDER_WINDOW[0])
        self.assertLessEqual(max(study.interval_counts), SIMPSON_ORDER_WINDOW[1])

    def test_quoted_eleven_digit_figure_agrees_with_the_high_precision_reference(self):
        # Documentation consistency, not a property of the module: the evidence review
        # quotes 3.4838638079e9, and the fifty-digit value above must be that figure to
        # the eleven digits it was reported to. Half a unit in the eleventh digit is
        # 0.05 psia^2/cp, i.e. 1.4e-11 relative, which is the tolerance.
        self.assertLess(abs(3.4838638079e9 / SMOOTH_REFERENCE_PSIA2_PER_CP - 1.0), 1.4e-11)

    def test_value_on_the_finest_useful_grid_matches_the_external_reference(self):
        # Tolerance decided from the arithmetic, before the answer was looked at. At
        # 2048 panels the leading Simpson truncation term is (h^4/180)(f'''(b)-f'''(a))
        # = 1.8e-6 absolute, 5e-16 relative. The running sum in composite_simpson adds
        # round-off that behaves like a random walk over its ~2000 terms, sqrt(n)*eps =
        # 1.0e-14 relative. Their sum, 1.0e-14 relative, is the gate. Nothing here is
        # reverse-engineered from the measured 1.4e-16.
        lower, upper = SMOOTH_INTERVAL_PSIA
        got = pseudopressure(upper, reference_psia=lower, mu_z=smooth_mu_z, intervals=2048)
        self.assertTrue(
            math.isclose(got, SMOOTH_REFERENCE_PSIA2_PER_CP, rel_tol=1.0e-14),
            msg=repr(got),
        )

    def test_error_falls_by_sixteen_per_halving_of_the_panel_width(self):
        # The order restated as an error ratio, so that a bug in the Richardson
        # estimator cannot make the order test pass on its own. The errors are measured
        # against the external fifty-digit reference. They were previously measured
        # against pseudopressure(..., intervals=2**20), which is the same function with
        # the same rule and the same accumulation; that reference carries 7.5e-5 of its
        # own round-off, which is 14 percent of the error at 64 panels and dragged the
        # last ratio from 15.9 down to 13.9.
        #
        # Band: the theoretical ratio is exactly 16. The neglected Euler-Maclaurin term
        # is O(h^2) and so shrinks by 4 per refinement; it is 3.5 percent of the error
        # at 64 panels, 0.9 percent at 128, 0.2 percent at 256. A band of 15.0 to 16.5
        # covers that drift and still fails for any other order: order 3 would give 8
        # and order 5 would give 32.
        lower, upper = SMOOTH_INTERVAL_PSIA
        errors = [
            abs(
                pseudopressure(upper, reference_psia=lower, mu_z=smooth_mu_z, intervals=n)
                - SMOOTH_REFERENCE_PSIA2_PER_CP
            )
            for n in (64, 128, 256, 512)
        ]
        self.assertTrue(all(b < a for a, b in itertools.pairwise(errors)))
        for coarse, fine in itertools.pairwise(errors):
            self.assertGreater(coarse / fine, 15.0)
            self.assertLess(coarse / fine, 16.5)

    def test_error_matches_the_euler_maclaurin_leading_term(self):
        # Stronger than an order test: it pins the error *constant*, hence the node
        # weights, not merely the exponent on h. For composite Simpson on a smooth
        # integrand the leading term is
        #
        #     S_n - I = (h^4 / 180) (f'''(b) - f'''(a)),
        #
        # with the jump in f''' supplied externally by SMOOTH_THIRD_DERIVATIVE_JUMP.
        # The signed error, not its magnitude, is compared: a rule with the wrong
        # interior weights reproduces the magnitude far more easily than the sign.
        #
        # Band: the first neglected term is O(h^6), measured at 3.5 percent of the
        # leading term at 64 panels and falling by 4 per refinement, so it is under 0.3
        # percent at the two grids used here. Two percent leaves room for that and for
        # the round-off in the sum, and would still catch a weight error of one part in
        # fifty.
        lower, upper = SMOOTH_INTERVAL_PSIA
        for intervals in (256, 512):
            with self.subTest(intervals=intervals):
                step = (upper - lower) / intervals
                predicted = step**4 * SMOOTH_THIRD_DERIVATIVE_JUMP / 180.0
                actual = (
                    pseudopressure(upper, reference_psia=lower, mu_z=smooth_mu_z, intervals=intervals)
                    - SMOOTH_REFERENCE_PSIA2_PER_CP
                )
                self.assertLess(abs(actual / predicted - 1.0), 0.02, msg=repr(actual))

    def test_refining_past_the_order_window_does_not_diverge(self):
        # The honest other half of an order test, with no lower bound on the error.
        # A lower bound would forbid the quadrature from becoming more accurate, and
        # the previous version of this test did exactly that: it asserted that the
        # error at 4096 panels stayed above 1e-6, a threshold that was in fact
        # measuring the round-off of its own 2**20-panel reference.
        #
        # What can be asserted is that refinement past the window does not blow up.
        # composite_simpson accumulates with a plain running sum, so its round-off
        # grows with the number of terms; over 2**20 terms a random-walk model gives
        # sqrt(n)*eps = 2.3e-13 relative, and four standard deviations of that, 9.1e-13,
        # is the gate. The measured value is 2.1e-14, i.e. the growth is real but well
        # inside the model. The floor itself is not a defect of this module and is
        # reported against numerics.composite_simpson separately.
        lower, upper = SMOOTH_INTERVAL_PSIA
        intervals = 2**20
        value = pseudopressure(upper, reference_psia=lower, mu_z=smooth_mu_z, intervals=intervals)
        relative_error = abs(value - SMOOTH_REFERENCE_PSIA2_PER_CP) / abs(SMOOTH_REFERENCE_PSIA2_PER_CP)
        self.assertLess(relative_error, 4.0 * math.sqrt(intervals) * ULP)

    def test_richardson_estimate_beats_the_finest_grid(self):
        lower, upper = SMOOTH_INTERVAL_PSIA
        reference = SMOOTH_REFERENCE_PSIA2_PER_CP
        study = convergence_study(
            upper,
            reference_psia=lower,
            mu_z=smooth_mu_z,
            interval_counts=(32, 64, 128, 256),
        )
        self.assertLess(abs(study.richardson_estimate - reference), abs(study.best() - reference))

    def test_reports_its_own_cost_and_interval(self):
        study = convergence_study(
            4000.0,
            reference_psia=500.0,
            mu_z=smooth_mu_z,
            interval_counts=(16, 32, 64),
        )
        self.assertEqual(study.interval_counts, (16, 32, 64))
        self.assertEqual(study.integrand_evaluations, (17, 33, 65))
        self.assertEqual(study.n_points, 115)
        self.assertEqual(study.pressure_psia, 4000.0)
        self.assertEqual(study.reference_psia, 500.0)
        self.assertEqual(len(study.values), 3)
        self.assertEqual(len(study.relative_changes), 2)

    def test_zero_width_interval_costs_nothing(self):
        study = convergence_study(
            2000.0, reference_psia=2000.0, mu_z=smooth_mu_z, interval_counts=(8, 16, 32)
        )
        self.assertEqual(study.values, (0.0, 0.0, 0.0))
        self.assertEqual(study.n_points, 0)

    def test_unestimable_order_raises_rather_than_inventing_one(self):
        # Built directly, because the situation it describes -- successive grid
        # differences that vanish or change sign -- is what refining past the round-off
        # floor produces, and reproducing that reliably would make the test a hostage to
        # the exact bit pattern of the arithmetic.
        result = ConvergenceResult(
            pressure_psia=8000.0,
            reference_psia=14.7,
            method="simpson",
            interval_counts=(8192, 16384, 32768),
            values=(1.0e9, 1.0e9, 1.0e9),
            observed_orders=(math.nan,),
            relative_changes=(0.0, 0.0),
            richardson_estimate=1.0e9,
            integrand_evaluations=(8193, 16385, 32769),
            n_points=57347,
            extrapolation_order=4.0,
            extrapolation_order_source="assumed",
        )
        with self.assertRaises(NotIdentifiableError):
            result.last_estimable_order()
        self.assertEqual(result.best(), 1.0e9)

    def test_records_whether_the_extrapolation_order_was_measured_or_assumed(self):
        # Contract C5: the result must be auditable on its own. richardson_estimate is
        # built on the observed order where one exists and on the theoretical 4.0 where
        # none does, and the two are different objects -- past the round-off floor the
        # assumed-order extrapolation can be worse than simply taking the finest grid.
        # Without these two fields a reader cannot tell which was used.
        lower, upper = SMOOTH_INTERVAL_PSIA
        inside = convergence_study(
            upper,
            reference_psia=lower,
            mu_z=smooth_mu_z,
            interval_counts=(64, 128, 256, 512),
        )
        self.assertEqual(inside.extrapolation_order_source, "observed")
        self.assertEqual(inside.extrapolation_order, inside.observed_orders[-1])
        self.assertGreater(inside.extrapolation_order, 3.7)

        # A zero-width interval gives three identical values, so no order is estimable
        # and the theoretical order must be declared as assumed.
        degenerate = convergence_study(
            2000.0, reference_psia=2000.0, mu_z=smooth_mu_z, interval_counts=(8, 16, 32)
        )
        self.assertEqual(degenerate.extrapolation_order_source, "assumed")
        self.assertEqual(degenerate.extrapolation_order, 4.0)
        with self.assertRaises(NotIdentifiableError):
            degenerate.last_estimable_order()

    def test_the_recorded_order_reproduces_the_reported_extrapolation(self):
        # The recorded order is a mirror of a decision taken inside
        # numerics.convergence_study. This rebuilds the extrapolation from the recorded
        # fields and requires it bit for bit, so the mirror cannot drift out of step
        # with the estimator it describes without failing here.
        lower, upper = SMOOTH_INTERVAL_PSIA
        for counts in ((64, 128, 256), (8, 16, 32, 64), (1024, 2048, 4096)):
            with self.subTest(counts=counts):
                study = convergence_study(
                    upper, reference_psia=lower, mu_z=smooth_mu_z, interval_counts=counts
                )
                self.assertIn(study.extrapolation_order_source, ("observed", "assumed"))
                finest, previous = study.values[-1], study.values[-2]
                rebuilt = finest + (finest - previous) / (2.0**study.extrapolation_order - 1.0)
                self.assertEqual(rebuilt, study.richardson_estimate)


class InvalidInputTests(unittest.TestCase):
    """Every documented raise is exercised."""

    # Note on what is not listed below. The shared validator coerces with ``float()``,
    # so a numeric string such as ``"3000"`` is accepted rather than rejected. That is
    # the behaviour of ``reservoir_lab.validation``, not of this module, and it is not
    # enshrined here in either direction: these cases assert only the raises this
    # module documents.

    def test_rejects_non_physical_pressures(self):
        for bad in (-1.0, -1.0e-9, math.nan, math.inf, -math.inf, None, object()):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                pseudopressure(bad, reference_psia=14.7, mu_z=smooth_mu_z)
            with self.subTest(bad=bad, argument="reference"), self.assertRaises(InvalidInputError):
                pseudopressure(3000.0, reference_psia=bad, mu_z=smooth_mu_z)

    def test_rejects_non_physical_pressures_in_the_closed_form(self):
        for bad in (-1.0, math.nan, math.inf, None):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                pseudopressure_constant_properties(bad, reference_psia=14.7, viscosity_cp=0.02, z_factor=0.9)

    def test_rejects_non_physical_properties_in_the_closed_form(self):
        for bad in (0.0, -0.02, math.nan, math.inf):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                pseudopressure_constant_properties(
                    3000.0, reference_psia=14.7, viscosity_cp=bad, z_factor=0.9
                )
            with self.subTest(bad=bad, argument="z_factor"), self.assertRaises(InvalidInputError):
                pseudopressure_constant_properties(
                    3000.0, reference_psia=14.7, viscosity_cp=0.02, z_factor=bad
                )

    def test_rejects_bad_interval_counts(self):
        for bad in (3, 0, -2, 4.0, True, "8", None):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                pseudopressure(3000.0, reference_psia=14.7, mu_z=smooth_mu_z, intervals=bad)

    def test_rejects_unsupported_method(self):
        for bad in ("trapezoid", "gauss-kronrod", "Simpson", ""):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                pseudopressure(3000.0, reference_psia=14.7, mu_z=smooth_mu_z, method=bad)

    def test_rejects_a_mu_z_that_is_not_callable(self):
        for bad in (0.018, None, (0.018, 0.019)):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                pseudopressure(3000.0, reference_psia=14.7, mu_z=bad)

    def test_rejects_a_mu_z_that_returns_an_unusable_value(self):
        # The realistic origin of each of these is a deviation-factor solve that landed
        # on the wrong root, a correlation evaluated off the end of its window, or a
        # table lookup that fell off its last node. All three would otherwise integrate
        # to a plausible-looking finite number.
        for bad in (0.0, -0.018, math.nan, math.inf, None, [0.018]):
            with self.subTest(bad=bad), self.assertRaises(InvalidInputError):
                pseudopressure(3000.0, reference_psia=14.7, mu_z=lambda _p, bad=bad: bad)

    def test_a_result_too_large_to_represent_raises_rather_than_returning_inf(self):
        # Contract C3: no non-finite return value. m grows like p^2/(mu Z), so inputs
        # that are each finite, positive and inside the documented domain can still put
        # the result outside double precision. Before this was guarded, all three of
        # these returned inf silently, and an inf fed to a flow solution reappears as a
        # nan several steps downstream with nothing recording where it came from.
        with self.assertRaises(InvalidInputError):
            pseudopressure_constant_properties(1.0e200, reference_psia=0.0, viscosity_cp=1.0, z_factor=1.0)
        with self.assertRaises(InvalidInputError):
            pseudopressure(1.0e200, reference_psia=0.0, mu_z=lambda _p: 1.0, intervals=2)
        # Smallest positive denormal: finite and strictly positive, so it passes the
        # mu_z guard, and 2p/(mu Z) overflows anyway.
        with self.assertRaises(InvalidInputError) as raised:
            pseudopressure(3000.0, reference_psia=14.7, mu_z=lambda _p: 5.0e-324)
        self.assertIn("overflow", str(raised.exception))

    def test_a_zero_width_interval_never_evaluates_mu_z(self):
        # Documented carve-out, pinned so that it stays a decision rather than an
        # accident. With equal limits the answer is exactly zero whatever the integrand
        # does, and the mu_z guards are guards at the nodes actually used, of which
        # there are none. A mu_z that raises is therefore never called.
        calls = []

        def exploding_mu_z(pressure_psia: float) -> float:
            calls.append(pressure_psia)
            raise AssertionError("mu_z must not be evaluated on a zero-width interval")

        self.assertEqual(pseudopressure(3000.0, reference_psia=3000.0, mu_z=exploding_mu_z), 0.0)
        study = convergence_study(
            3000.0,
            reference_psia=3000.0,
            mu_z=exploding_mu_z,
            interval_counts=(8, 16, 32),
        )
        self.assertEqual(study.values, (0.0, 0.0, 0.0))
        self.assertEqual(calls, [])

        # The same mu_z on any non-degenerate interval is evaluated, and the module's
        # own guards apply there. This is the asymmetry the docstring now states.
        with self.assertRaises(InvalidInputError):
            pseudopressure(3000.0, reference_psia=2999.0, mu_z=lambda _p: math.nan)

    def test_a_mu_z_returning_a_non_float_numeric_type_is_accepted(self):
        # A PVT wrapper backed by a table, a Decimal or a Fraction does not necessarily
        # return exactly float, and such a mu_z is legitimate. It must give the same
        # answer as the float one, and it must not be routed through the failure path,
        # whose diagnostic message costs a formatted string at every node.
        expected = pseudopressure_constant_properties(
            5000.0, reference_psia=14.7, viscosity_cp=1.0, z_factor=2.0
        )
        for factory in (int, Decimal, Fraction):
            with self.subTest(factory=factory.__name__):
                got = pseudopressure(
                    5000.0,
                    reference_psia=14.7,
                    mu_z=lambda _p, factory=factory: factory(2),
                    intervals=2,
                )
                self.assertIsInstance(got, float)
                self.assertTrue(math.isclose(got, expected, rel_tol=4.0 * ULP))

        # A return that is not numeric at all still raises, and the message still names
        # the pressure at which it happened. A numeric *string* is deliberately not
        # used here: the shared validator coerces with float(), so "0.018" is accepted,
        # which is a property of reservoir_lab.validation and not of this module.
        with self.assertRaises(InvalidInputError) as raised:
            pseudopressure(3000.0, reference_psia=14.7, mu_z=lambda _p: [0.018], intervals=2)
        self.assertIn("mu_z(", str(raised.exception))

    def test_error_message_names_the_offending_pressure(self):
        def mu_z(pressure_psia: float) -> float:
            return -1.0 if pressure_psia > 2000.0 else 0.018

        with self.assertRaises(InvalidInputError) as raised:
            pseudopressure(3000.0, reference_psia=14.7, mu_z=mu_z, intervals=2)
        self.assertIn("mu_z(", str(raised.exception))

    def test_convergence_study_rejects_bad_grids(self):
        cases = (
            (16, 32),
            (16,),
            (),
            (16, 32, 96),
            (16, 32, 64, 256),
            (32, 16, 8),
            (15, 30, 60),
            (0, 0, 0),
            (16.0, 32.0, 64.0),
        )
        for counts in cases:
            with self.subTest(counts=counts), self.assertRaises(InvalidInputError):
                convergence_study(
                    8000.0,
                    reference_psia=14.7,
                    mu_z=smooth_mu_z,
                    interval_counts=counts,
                )

    def test_convergence_study_rejects_bad_pressures_and_callables(self):
        with self.assertRaises(InvalidInputError):
            convergence_study(-1.0, reference_psia=14.7, mu_z=smooth_mu_z, interval_counts=(16, 32, 64))
        with self.assertRaises(InvalidInputError):
            convergence_study(8000.0, reference_psia=math.nan, mu_z=smooth_mu_z, interval_counts=(16, 32, 64))
        with self.assertRaises(InvalidInputError):
            convergence_study(8000.0, reference_psia=14.7, mu_z=0.018, interval_counts=(16, 32, 64))
        with self.assertRaises(InvalidInputError):
            convergence_study(8000.0, reference_psia=14.7, mu_z=smooth_mu_z, interval_counts=64)


class ReturnTypeTests(unittest.TestCase):
    """Contract C5: scalars are floats, multi-field results are frozen dataclasses."""

    def test_scalar_returns_are_floats(self):
        self.assertIsInstance(pseudopressure(3000.0, reference_psia=14.7, mu_z=smooth_mu_z), float)
        self.assertIsInstance(
            pseudopressure_constant_properties(3000.0, reference_psia=14.7, viscosity_cp=0.02, z_factor=0.9),
            float,
        )

    def test_convergence_result_is_frozen_and_uses_tuples(self):
        study = convergence_study(8000.0, reference_psia=14.7, mu_z=smooth_mu_z, interval_counts=(16, 32, 64))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            study.method = "trapezoid"  # type: ignore[misc]
        for field_value in (
            study.interval_counts,
            study.values,
            study.observed_orders,
            study.relative_changes,
            study.integrand_evaluations,
        ):
            self.assertIsInstance(field_value, tuple)


if __name__ == "__main__":
    unittest.main()

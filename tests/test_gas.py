"""Independent analytical checks and explicit invalid-input tests."""

import itertools
import math
import unittest

from reservoir_lab.gas import (
    component_balance_error,
    cumulative_step_volume,
    fit_volumetric_pz,
    gas_fvf,
    log_time_derivative,
    relative_pseudopressure,
)


class GasFvfTests(unittest.TestCase):
    def test_standard_state_identity(self):
        self.assertEqual(
            gas_fvf(
                101325,
                288.15,
                0.99,
                standard_pressure_pa=101325,
                standard_temperature_k=288.15,
                standard_z=0.99,
            ),
            1.0,
        )

    def test_pressure_doubling_halves_volume(self):
        kw = dict(temperature_k=360, z=0.9, standard_pressure_pa=101325, standard_temperature_k=288.15)
        self.assertAlmostEqual(gas_fvf(20e6, **kw) / gas_fvf(10e6, **kw), 0.5)

    def test_invalid_inputs(self):
        for bad in (0, -1, float("nan"), float("inf"), True, "bad"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                gas_fvf(bad, 360, 0.9, standard_pressure_pa=101325, standard_temperature_k=288.15)

    def test_invalid_standard_state(self):
        with self.assertRaises(ValueError):
            gas_fvf(1e7, 360, 0.9, standard_pressure_pa=101325, standard_temperature_k=0)


class PzTests(unittest.TestCase):
    def setUp(self):
        # Hand-defined p/Z = [20,16,12] MPa, not produced by the fitting code.
        self.gp = [0, 4e8, 8e8]
        self.p = [16e6, 13.6e6, 10.8e6]
        self.z = [0.8, 0.85, 0.9]

    def test_exact_giip(self):
        result = fit_volumetric_pz(self.gp, self.p, self.z)
        self.assertAlmostEqual(result.giip_sm3 / 2e9, 1.0, places=12)
        self.assertAlmostEqual(result.slope_pa_per_sm3, -0.01, places=12)
        self.assertAlmostEqual(result.r_squared, 1.0)

    def test_prediction(self):
        result = fit_volumetric_pz(self.gp, self.p, self.z)
        self.assertAlmostEqual(result.predict_p_over_z(1e9), 10e6)
        with self.assertRaises(ValueError):
            result.predict_p_over_z(2.1e9)

    def test_scale_invariance(self):
        a = fit_volumetric_pz(self.gp, self.p, self.z)
        b = fit_volumetric_pz([x / 1000 for x in self.gp], self.p, self.z)
        self.assertAlmostEqual(a.giip_sm3 / b.giip_sm3, 1000)

    def test_no_initial_observation_warning(self):
        r = fit_volumetric_pz([1e8, 4e8, 8e8], [15.2e6, 13.6e6, 10.8e6], self.z)
        self.assertTrue(any("extrapolated" in x for x in r.warnings))

    def test_shallow_decline_warning(self):
        r = fit_volumetric_pz([0, 1e6, 2e6], [20e6, 19.99e6, 19.98e6], [1, 1, 1])
        self.assertTrue(any("weakly constrained" in x for x in r.warnings))

    def test_invalid_vectors(self):
        cases = [
            ([0, 1], [3, 2], [1, 1]),
            ([0, 0, 0], self.p, self.z),
            ([0, 8e8, 4e8], self.p, self.z),
            (self.gp, self.p, [0.8, 0, 0.9]),
            (self.gp, [1, 2, 3], [1, 1, 1]),
            (self.gp, [1, 1, 1], [1, 1, 1]),
            (self.gp, [float("nan"), 2, 1], self.z),
            ([-1, 4e8, 8e8], self.p, self.z),
        ]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                fit_volumetric_pz(*args)


class PseudopressureTests(unittest.TestCase):
    def test_constant_properties_analytic_integral(self):
        p = [1e5, 3e5, 8e5, 1e6]
        m = relative_pseudopressure(p, [1e-5] * 4, [0.8] * 4)
        for pi, mi in zip(p, m, strict=True):
            expected = (pi * pi - p[0] * p[0]) / (1e-5 * 0.8)
            self.assertTrue(math.isclose(mi, expected, rel_tol=1e-12, abs_tol=1))

    def test_monotone_and_datum(self):
        m = relative_pseudopressure([1, 2, 4], [1, 1.1, 1.2], [0.9, 0.8, 0.9])
        self.assertEqual(m[0], 0)
        self.assertTrue(all(b > a for a, b in itertools.pairwise(m)))

    def test_mu_scaling(self):
        a = relative_pseudopressure([1, 2, 4], [1] * 3, [1] * 3)
        b = relative_pseudopressure([1, 2, 4], [2] * 3, [1] * 3)
        self.assertEqual(b[-1], a[-1] / 2)

    def test_quadrature_refinement(self):
        # Manufactured case: mu=p**2, Z=1 gives integral 2*ln(4).
        # This is an analytic quadrature oracle, not a physical gas-viscosity law.
        errors = []
        for n in (8, 16, 32):
            p = [1 + 3 * i / n for i in range(n + 1)]
            m = relative_pseudopressure(p, [x * x for x in p], [1] * (n + 1))
            errors.append(abs(m[-1] - 2 * math.log(4)))
        self.assertTrue(errors[2] < errors[1] < errors[0])
        self.assertLess(errors[2], 0.002)
        self.assertTrue(3.5 < errors[1] / errors[2] < 4.1)

    def test_bad_grids_and_properties(self):
        cases = [
            ([2, 1], [1, 1], [1, 1]),
            ([1, 1], [1, 1], [1, 1]),
            ([0, 1], [1, 1], [1, 1]),
            ([1, 2], [1, 0], [1, 1]),
            ([1], [1], [1]),
            ([1, 2], [1], [1, 1]),
        ]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                relative_pseudopressure(*args)


class DerivativeTests(unittest.TestCase):
    def test_log_line_nonuniform_spacing(self):
        t = [1, 1.7, 4, 11, 40]
        interior, d = log_time_derivative(t, [7 * math.log(x) + 3 for x in t])
        self.assertEqual(interior, tuple(t[1:-1]))
        for v in d:
            self.assertAlmostEqual(v, 7, places=12)

    def test_log_quadratic(self):
        t = [1, 2, 5, 20, 100]
        times, d = log_time_derivative(t, [math.log(x) ** 2 for x in t])
        for ti, di in zip(times, d, strict=True):
            self.assertAlmostEqual(di, 2 * math.log(ti), places=12)

    def test_negative_derivatives_preserved(self):
        _, d = log_time_derivative([1, 2, 4], [3, 2, 1])
        self.assertLess(d[0], 0)

    def test_bad_times(self):
        for t in ([0, 1, 2], [1, 1, 2], [2, 1, 3], [1, 2]):
            with self.subTest(t=t), self.assertRaises(ValueError):
                log_time_derivative(t, [1] * len(t))

    def test_bad_response(self):
        with self.assertRaises(ValueError):
            log_time_derivative([1, 2, 3], [1, float("nan"), 3])


class VolumeTests(unittest.TestCase):
    def test_intervals_and_shutin(self):
        self.assertEqual(cumulative_step_volume([0, 10, 30, 40], [2, 0, 3]), (0, 20, 20, 50))

    def test_nonzero_start(self):
        self.assertEqual(cumulative_step_volume([10, 20], [2]), (0, 20))

    def test_invalid_intervals(self):
        for args in [([0, 1, 1], [1, 1]), ([0, 1], [1, 2]), ([0, 1], [-1]), ([0], [1])]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                cumulative_step_volume(*args)


class BalanceTests(unittest.TestCase):
    def test_closed_tank(self):
        self.assertEqual(component_balance_error(100, 80, 20), 0)

    def test_all_boundary_terms(self):
        self.assertEqual(
            component_balance_error(
                100, 90, 20, cumulative_injection_mass=15, boundary_in_mass=5, boundary_out_mass=10
            ),
            0,
        )

    def test_signed_residual(self):
        self.assertAlmostEqual(component_balance_error(100, 79, 20), 0.01)
        self.assertAlmostEqual(component_balance_error(100, 81, 20), -0.01)

    def test_invalid_mass(self):
        with self.assertRaises(ValueError):
            component_balance_error(0, 0, 0)
        with self.assertRaises(ValueError):
            component_balance_error(100, -1, 20)


if __name__ == "__main__":
    unittest.main()

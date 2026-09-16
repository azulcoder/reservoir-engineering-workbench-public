"""The radial-window rule, on invented fixtures rather than on B2 physics.

Every fixture here is constructed by hand from an analytic shape. None comes from the B2
forward model, so a defect in that model cannot make these tests pass, and a defect here
cannot be explained away as physics.

The first test is the one that matters most: it asserts that no true reservoir parameter can
reach the selector at all. B1 measured what wrong inputs do to an interpretation -- five of
ten seeded errors were materially wrong and moved no diagnostic -- and B2's whole claim is
that a rule can find the regime *without* the answer. A selector that could read the answer
would make the claim unfalsifiable.
"""

from __future__ import annotations

import inspect
import math
import unittest

from reservoir_lab.errors import InvalidInputError
from reservoir_lab.regime import (
    WindowSettings,
    identify_radial_window,
    local_log_slope,
)

L = 0.1  # the pre-registered smoothing, protocol section 8


def log_grid(first: float, last: float, per_decade: int) -> list[float]:
    """Log-spaced times, the sampling the protocol declares."""
    n = round(math.log10(last / first) * per_decade)
    return [first * 10.0 ** (i / per_decade) for i in range(n + 1)]


def storage_then_plateau(
    times: list[float],
    *,
    crossover: float,
    dp_at_crossover: float = 300.0,
    semilog_slope: float = 42.67,
) -> tuple[list[float], list[float]]:
    """Unit-slope storage joined to a semilog line, in realistic proportions.

    Deliberately not the B2 solution: a piecewise shape carrying only the two limiting
    behaviours, which is all the rule is entitled to assume.

    The proportions matter and an earlier version of this fixture got them backwards. Through
    the transition the derivative **falls** -- from the storage value, where ``D == Δp``
    identically, down to the radial plateau ``m / ln 10`` -- while ``Δp`` keeps rising along
    the semilog line. So ``D/Δp`` runs from 1.0 during storage down to a few hundredths in
    radial flow. The defaults are B1's own scale: a 42.67 psi/cycle slope gives an 18.5 psi
    plateau against a ``Δp`` of several hundred psi, so the ratio lands near 0.06, which is
    what puts it below the rule's 0.10 exclusion. A fixture whose ratio never falls below 0.10
    is not a fixture the rule should accept.
    """
    dp: list[float] = []
    der: list[float] = []
    plateau = semilog_slope / math.log(10.0)
    for t in times:
        if t <= crossover:
            storage = dp_at_crossover * (t / crossover)
            dp.append(storage)
            der.append(storage)  # the identity that holds during pure storage
        else:
            dp.append(dp_at_crossover + semilog_slope * math.log10(t / crossover))
            der.append(plateau)
    return dp, der


class SelectorCannotSeeTheAnswer(unittest.TestCase):
    """No true parameter may reach the rule. Enforced on the signature itself."""

    #: Names that would indicate a TRUE value rather than a rule constant. "storage_ratio"
    #: is deliberately not here: it is a declared exclusion strength, not a true C_D, and a
    #: filter that rejects it would reject the rule's own vocabulary.
    FORBIDDEN = (
        "permeability",
        "kh",
        "skin",
        "truth",
        "true_",
        "_true",
        "known",
        "actual",
        "regime_label",
        "iarf_start",
        "crossover",
    )

    def test_no_parameter_could_carry_truth(self) -> None:
        names = set(inspect.signature(identify_radial_window).parameters)
        self.assertEqual(
            names,
            {"derivative_time", "derivative", "pressure_change", "settings", "smoothing_l"},
            "the selector's parameters changed; a new one may be a truth channel",
        )
        for name in names:
            for forbidden in self.FORBIDDEN:
                self.assertNotIn(
                    forbidden,
                    name.lower(),
                    f"parameter {name!r} looks like it could carry hidden truth",
                )

    def test_settings_carry_no_truth_either(self) -> None:
        for field in WindowSettings.__dataclass_fields__:
            for forbidden in self.FORBIDDEN:
                self.assertNotIn(forbidden, field.lower(), f"setting {field!r} may carry truth")

    def test_the_rule_is_deterministic(self) -> None:
        times = log_grid(1e-3, 48.0, 20)
        dp, der = storage_then_plateau(times, crossover=0.25)
        a = identify_radial_window(times, der, dp, settings=WindowSettings(), smoothing_l=L)
        b = identify_radial_window(times, der, dp, settings=WindowSettings(), smoothing_l=L)
        self.assertEqual(a, b)


class TheRuleFindsAWindowWhenOneExists(unittest.TestCase):
    def test_clear_storage_then_long_plateau(self) -> None:
        times = log_grid(1e-3, 48.0, 20)
        dp, der = storage_then_plateau(times, crossover=0.25)
        w = identify_radial_window(times, der, dp, settings=WindowSettings(), smoothing_l=L)
        self.assertTrue(w.found, w.reason)
        self.assertGreaterEqual(w.decades, 1.0)
        self.assertGreaterEqual(w.points, 15)
        self.assertGreater(w.start_time, 0.25, "the window must start after the crossover")

    def test_the_window_excludes_the_storage_branch(self) -> None:
        times = log_grid(1e-3, 48.0, 20)
        dp, der = storage_then_plateau(times, crossover=0.25)
        w = identify_radial_window(times, der, dp, settings=WindowSettings(), smoothing_l=L)
        self.assertTrue(w.found, w.reason)
        for i in range(w.start_index, w.end_index + 1):
            self.assertLessEqual(
                der[i] / dp[i],
                WindowSettings().storage_ratio,
                "a storage-contaminated point entered the window",
            )


class TheRuleDeclines(unittest.TestCase):
    """INCONCLUSIVE is an answer. None of these may return a window."""

    def test_no_plateau_at_all(self) -> None:
        times = log_grid(1e-3, 48.0, 20)
        dp = [10.0 * t for t in times]
        der = list(dp)  # storage identity the whole way: never leaves storage
        w = identify_radial_window(times, der, dp, settings=WindowSettings(), smoothing_l=L)
        self.assertFalse(w.found)
        self.assertIn("storage", w.reason)

    def test_plateau_shorter_than_the_minimum_extent(self) -> None:
        times = log_grid(1e-3, 48.0, 20)
        dp, der = storage_then_plateau(times, crossover=20.0)
        w = identify_radial_window(times, der, dp, settings=WindowSettings(), smoothing_l=L)
        self.assertFalse(w.found, "a plateau under one decade must not qualify")
        self.assertIn("minimum extent", w.reason)

    def test_too_few_points_even_though_wide_enough(self) -> None:
        times = log_grid(1e-3, 48.0, 3)  # 3 per decade: a decade holds only 4 points
        dp, der = storage_then_plateau(times, crossover=0.25)
        w = identify_radial_window(times, der, dp, settings=WindowSettings(), smoothing_l=L)
        self.assertFalse(w.found, "an interval below the point floor must not qualify")

    def test_a_flat_patch_inside_a_transition_is_rejected(self) -> None:
        """A transition carries a brief inflection where the slope passes through zero."""
        times = log_grid(1e-3, 48.0, 20)
        dp: list[float] = []
        der: list[float] = []
        for t in times:
            # A smooth S-shaped rise: flat only instantaneously, never for a decade.
            x = math.log10(t / 0.5)
            d = 40.0 / (1.0 + math.exp(-1.5 * x))
            der.append(d)
            dp.append(d * 12.0)
        w = identify_radial_window(times, der, dp, settings=WindowSettings(), smoothing_l=L)
        self.assertFalse(w.found, "an inflection is not a regime")

    def test_empty_input_declines_rather_than_raising(self) -> None:
        w = identify_radial_window([], [], [], settings=WindowSettings(), smoothing_l=L)
        self.assertFalse(w.found)

    def test_it_never_falls_back_to_best_available(self) -> None:
        """The decisive property: no window is better than a bad window."""
        times = log_grid(1e-3, 48.0, 20)
        dp, der = storage_then_plateau(times, crossover=20.0)
        w = identify_radial_window(times, der, dp, settings=WindowSettings(), smoothing_l=L)
        self.assertFalse(w.found)
        self.assertEqual(w.start_index, -1)
        self.assertEqual(w.points, 0)


class TwoCandidates(unittest.TestCase):
    def test_the_wider_interval_wins(self) -> None:
        times = log_grid(1e-3, 1e3, 20)
        dp: list[float] = []
        der: list[float] = []
        for t in times:
            if t < 1e-2:
                d = 40.0  # a short flat stretch
            elif t < 1.0:
                d = 40.0 * (1.0 + 0.5 * math.log10(t / 1e-2))  # sloping
            else:
                d = 60.0  # a long flat stretch
            der.append(d)
            dp.append(d * 12.0)
        w = identify_radial_window(times, der, dp, settings=WindowSettings(), smoothing_l=L)
        self.assertTrue(w.found, w.reason)
        self.assertGreater(w.start_time, 1.0, "the wider late interval should win")


class LogSlopeEdgeCases(unittest.TestCase):
    def test_non_positive_derivative_points_are_dropped_not_floored(self) -> None:
        times = [1.0, 2.0, 3.0, 4.0, 5.0]
        der = [1.0, -0.5, 1.0, 1.0, 1.0]
        idx_out, _ = local_log_slope(times, der, smoothing_l=0.0)
        self.assertNotIn(1, idx_out, "the non-positive point's index must not survive")

    def test_indices_are_returned_not_reconstructed_times(self) -> None:
        """exp(log(t)) is not bitwise t; returning indices removes that round trip."""
        times = [1e-3 * 10.0 ** (i / 20.0) for i in range(60)]
        der = [40.0] * len(times)
        idx_out, _ = local_log_slope(times, der, smoothing_l=0.1)
        self.assertTrue(all(isinstance(i, int) for i in idx_out))
        self.assertTrue(all(0 <= i < len(times) for i in idx_out))

    def test_mismatched_lengths_are_rejected(self) -> None:
        with self.assertRaises(InvalidInputError):
            local_log_slope([1.0, 2.0], [1.0], smoothing_l=0.0)

    def test_non_positive_time_is_rejected(self) -> None:
        with self.assertRaises(InvalidInputError):
            local_log_slope([0.0, 1.0, 2.0], [1.0, 1.0, 1.0], smoothing_l=0.0)


class SettingsAreValidated(unittest.TestCase):
    def test_nonsense_settings_are_refused(self) -> None:
        for kwargs in (
            {"flatness": 0.0},
            {"flatness": float("inf")},
            {"storage_ratio": -1.0},
            {"min_decades": 0.0},
            {"min_points": 2},
        ):
            with self.subTest(**kwargs), self.assertRaises(InvalidInputError):
                WindowSettings(**kwargs)

    def test_the_default_flatness_is_the_derived_value(self) -> None:
        """Eps = A/(W ln10) with A = 0.05 and W = 1.0, from protocol section 7."""
        self.assertAlmostEqual(WindowSettings().flatness, 0.05 / math.log(10.0), places=12)


if __name__ == "__main__":
    unittest.main()

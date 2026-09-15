"""Every quantitative claim in the B1 report, checked against the B1 run snapshot.

This is the case B1 claims audit, written as a test rather than as a one-off pass so that
the report cannot quietly drift away from the artifact it describes. A claim that stops
being true fails here.

The test reads the committed snapshot and the committed report. It does not recompute the
case: if the run and the report disagree, that is the finding.
"""

from __future__ import annotations

import itertools
import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASE = ROOT / "cases" / "B1_iarf_known_answer"
SUMMARY = json.loads((CASE / "results" / "summary.json").read_text())
REPORT = (CASE / "report.md").read_text()
PROTOCOL = (CASE / "protocol.md").read_text()
BRIDGE = ROOT / "docs" / "bridges" / "saphir_b1_manual_validation.md"


class ReportQuotesTheSnapshot(unittest.TestCase):
    """Numbers printed in the report are the numbers in the snapshot."""

    def test_recovery_values(self) -> None:
        recovery = SUMMARY["b1_0_mathematical_baseline"]["recovery"]
        self.assertIn(repr(recovery["permeability_thickness_recovered"]), REPORT)
        self.assertIn(repr(recovery["permeability_md_recovered"]), REPORT)
        self.assertIn(repr(recovery["skin_recovered"]), REPORT)

    def test_metrics_hash_matches(self) -> None:
        self.assertIn(SUMMARY["metrics_sha256"], REPORT)

    def test_protocol_commit_and_blob_match(self) -> None:
        protocol = SUMMARY["config"]["protocol"]
        self.assertIn(protocol["commit"][:7], REPORT)
        self.assertIn(protocol["blob_digest"][:8], REPORT)

    def test_thresholds_quoted_are_the_thresholds_enforced(self) -> None:
        thresholds = SUMMARY["config"]["thresholds"]
        self.assertEqual(thresholds["C3_kh_relative"], 1e-4)
        self.assertEqual(thresholds["C4_skin_absolute"], 1e-3)
        self.assertEqual(thresholds["C5_derivative_relative"], 1e-6)
        self.assertEqual(thresholds["C1_forward_oracle_relative"], 1e-12)
        # The report states these in prose; a changed threshold must fail here too.
        for text in ("`1e-4` and `1e-3`", "`<= 1e-12`"):
            self.assertIn(text, REPORT)


class ClaimedMagnitudes(unittest.TestCase):
    """Claims the report makes about sizes and ratios, recomputed from the snapshot."""

    def test_headroom_claims(self) -> None:
        recovery = SUMMARY["b1_0_mathematical_baseline"]["recovery"]
        kh_headroom = 1e-4 / recovery["permeability_thickness_relative_error"]
        skin_headroom = 1e-3 / recovery["skin_absolute_error"]
        self.assertAlmostEqual(kh_headroom, 64, delta=1)
        self.assertAlmostEqual(skin_headroom, 63, delta=1)
        self.assertIn("64x and 63x", REPORT)

    def test_placement_dominates_density(self) -> None:
        sweep = SUMMARY["b1_1_sampling_and_placement"]
        self.assertTrue(sweep["placement_dominates"])
        self.assertAlmostEqual(sweep["placement_error_spread_ratio"], 3322, delta=1)
        self.assertAlmostEqual(sweep["density_error_spread_ratio"], 1.18, delta=0.01)
        self.assertIn("3322x", REPORT)
        self.assertIn("1.18x", REPORT)

    def test_placement_sweep_covers_every_declared_start(self) -> None:
        """The protocol declares six window starts. All six must have been run."""
        declared = {"10", "25", "50", "100", "1000", "3.32e4"}
        self.assertTrue(all(f"{d}" in PROTOCOL for d in declared))
        starts = [
            r["window_start_dimensionless_time"]
            for r in SUMMARY["b1_1_sampling_and_placement"]["placement_sweep"]
        ]
        self.assertEqual(len(starts), 6, "the placement sweep is missing a declared start")
        self.assertIn(3.32e4, starts)

    def test_least_squares_projection_predicts_the_measured_bias(self) -> None:
        """The report claims six significant figures at the declared window."""
        rows = SUMMARY["b1_1_sampling_and_placement"]["placement_sweep"]
        for row in rows:
            measured = row["permeability_thickness_relative_error"]
            projected = row["projected_bias_least_squares"]
            ratio = measured / projected
            # The residual shrinks as 1/t_D, so the bound is looser at the early windows.
            tolerance = 1.0 / row["window_start_dimensionless_time"]
            self.assertLess(abs(ratio - 1.0), tolerance, f"start {row['window_start_dimensionless_time']}")
        declared = rows[-1]
        self.assertAlmostEqual(
            declared["permeability_thickness_relative_error"] / declared["projected_bias_least_squares"],
            1.0,
            places=6,
        )

    def test_protocol_prediction_was_off_by_the_factor_reported(self) -> None:
        """The report says 1.925, and says so as a correction rather than a success."""
        row = SUMMARY["b1_1_sampling_and_placement"]["placement_sweep"][-2]
        factor = row["predicted_bias_one_over_ten_t_d"] / row["projected_bias_least_squares"]
        self.assertAlmostEqual(factor, 1.925, places=3)
        self.assertIn("1.925", REPORT)

    def test_negative_control_fails_while_looking_good(self) -> None:
        control = SUMMARY["b1_3_negative_control"]
        self.assertTrue(control["c7_negative_control_fails_c3"])
        self.assertGreater(control["recovery"]["permeability_thickness_relative_error"], 1e-4)
        self.assertGreater(control["r_squared"], 0.999)
        self.assertIn("0.9993", REPORT)

    def test_noise_response_is_proportional_within_the_monte_carlo_error(self) -> None:
        levels = SUMMARY["b1_2_pressure_noise"]["levels"]
        for lower, upper in itertools.pairwise(levels):
            sigma_ratio = upper["sigma_psi"] / lower["sigma_psi"]
            error_ratio = upper["kh_relative_error_mean"] / lower["kh_relative_error_mean"]
            self.assertLess(abs(error_ratio - sigma_ratio) / sigma_ratio, 0.02)
        worst = levels[-1]
        self.assertAlmostEqual(worst["skin_absolute_error_p95"], 0.86, delta=0.01)
        self.assertIn("`0.86`", REPORT)


class DefectVisibilityClaims(unittest.TestCase):
    """Section 6 is the report's headline finding, so it is checked hardest."""

    def setUp(self) -> None:
        self.diagnostic = SUMMARY["diagnostic_defect_visibility"]

    def test_the_diagnostic_is_ungated(self) -> None:
        """A post-hoc block must not be able to change the verdict."""
        self.assertNotIn("diagnostic", " ".join(SUMMARY["criteria"]))
        self.assertTrue(SUMMARY["all_criteria_met"])

    def test_five_defects_are_materially_wrong_and_silent(self) -> None:
        self.assertEqual(self.diagnostic["silent_but_materially_wrong_count"], 5)
        self.assertIn("five", REPORT)
        silent = set(self.diagnostic["silent_but_materially_wrong"])
        for expected in ("rate", "thickness", "radius", "porosity", "viscosity"):
            self.assertTrue(
                any(expected in name for name in silent),
                f"{expected} is no longer reported as silent; the report says it is",
            )

    def test_every_metadata_defect_is_silent(self) -> None:
        """The report's central claim: nothing inside an interpretation validates its inputs."""
        metadata_rows = [r for r in self.diagnostic["rows"] if r.get("kind") == "metadata"]
        self.assertEqual(len(metadata_rows), 5)
        for row in metadata_rows:
            self.assertFalse(row["visible_without_truth"], row["defect"])
            self.assertTrue(row["materially_wrong"], row["defect"])

    def test_thickness_error_leaves_kh_right_and_k_wrong(self) -> None:
        row = next(r for r in self.diagnostic["rows"] if "thickness" in r["defect"])
        self.assertLess(row["permeability_thickness_relative_error"], 1e-4)
        self.assertAlmostEqual(row["permeability_relative_error"], 1 / 3, places=3)

    def test_sign_flip_is_caught_only_by_the_derivative(self) -> None:
        row = next(r for r in self.diagnostic["rows"] if "sign" in r["defect"])
        self.assertGreater(row["r_squared"], 0.999999)
        self.assertGreater(row["derivative_versus_fit_relative_difference"], 1.0)
        self.assertTrue(row["visible_without_truth"])

    def test_wrong_time_zero_is_detectable(self) -> None:
        row = next(r for r in self.diagnostic["rows"] if "time zero" in r["defect"])
        self.assertLess(row["r_squared"], 0.999)
        self.assertTrue(row["visible_without_truth"])


class PortabilityClaims(unittest.TestCase):
    """Section 10 claims every published quantity is bit-identical across platforms.

    The measurement itself lives in CI, which runs the case on four platforms. What can be
    checked here is that the report does not overstate what a nine-significant-figure label
    can carry, and that the two tiers are not conflated.
    """

    def test_nine_figure_labels_are_justified_against_a_measured_spread(self) -> None:
        self.assertIn("sensitive at about `5e-10`", REPORT)
        self.assertIn("measured spread on every", REPORT)

    def test_the_two_tiers_are_named_separately(self) -> None:
        self.assertIn("**Canonical**", REPORT)
        self.assertIn("**Portable**", REPORT)
        # C8 is determinism in one environment, not portability. Conflating them is the
        # specific error this project corrected in Stage A.
        self.assertIn("C8 is a claim about one environment", REPORT)

    def test_no_unqualified_bitwise_claim(self) -> None:
        """'Bitwise reproducible' must never appear without naming the environment."""
        lowered = REPORT.lower()
        for index in range(len(lowered)):
            if lowered.startswith("bit-identical", index) or lowered.startswith("byte for byte", index):
                window = lowered[max(0, index - 260) : index + 260]
                self.assertTrue(
                    any(
                        marker in window
                        for marker in ("canonical", "environment", "platform", "macos", "two runs")
                    ),
                    f"an unqualified reproducibility claim near: ...{window[200:320]}...",
                )


class BridgeStaysHonest(unittest.TestCase):
    """The external comparison is not run, and nothing may imply otherwise."""

    def test_bridge_status_is_not_run(self) -> None:
        text = BRIDGE.read_text()
        self.assertIn("SAPHIR MANUAL COMPARISON — NOT RUN", text)

    def test_no_document_claims_external_validation(self) -> None:
        forbidden = (
            "validated against saphir",
            "verified against saphir",
            "matches saphir",
            "agrees with saphir",
            "commercial validation",
            "field validated",
            "peer reviewed",
        )
        for document in (REPORT, PROTOCOL, BRIDGE.read_text()):
            lowered = document.lower()
            for phrase in forbidden:
                self.assertNotIn(phrase, lowered, phrase)

    def test_report_records_the_comparison_as_not_performed(self) -> None:
        self.assertIn("NOT RUN", REPORT)


class ScopeClaimsAreBounded(unittest.TestCase):
    """The report must keep saying the things that make its result narrow."""

    def test_limitations_present_in_both_report_and_snapshot(self) -> None:
        self.assertGreaterEqual(len(SUMMARY["limitations"]), 6)
        for required in ("wellbore storage", "synthetic", "no field data"):
            self.assertIn(
                required,
                " ".join(SUMMARY["limitations"]).lower(),
                f"the snapshot stopped recording the {required} limitation",
            )

    def test_report_does_not_overstate_zero_storage(self) -> None:
        self.assertIn("storage is zero by declared design", REPORT.lower().replace("**", ""))

    def test_no_unaided_authorship_or_tooling_claims(self) -> None:
        lowered = REPORT.lower()
        for phrase in ("unaided", "without assistance", "generated with", "co-authored-by"):
            self.assertNotIn(phrase, lowered, phrase)

    def test_significant_figures_claimed_are_not_more_than_measured(self) -> None:
        """The report says 'about six significant figures'; check that is not generous."""
        error = SUMMARY["b1_0_mathematical_baseline"]["recovery"]["permeability_thickness_relative_error"]
        # A relative error of 1.56e-06 supports about six correct significant figures.
        # Claiming seven would require the error to be below 1e-07.
        exponent = int(re.search(r"e([+-]\d+)", f"{error:e}").group(1))
        self.assertLessEqual(-exponent, 6, "the report claims more precision than measured")
        self.assertGreaterEqual(-exponent, 5)
        self.assertIn("about six significant figures", REPORT)


if __name__ == "__main__":
    unittest.main()

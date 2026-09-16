"""The case B2 claims audit, and the reporting policy the result makes load-bearing.

B2 returned a result that declines to answer. That makes a specific class of mistake easy:
letting a permeability the rule refused to certify leak into a table, a figure or a sentence,
where a reader would read it as an estimate. These tests exist to make that leak fail.

They read the committed snapshot and the committed prose. They do not recompute the case: if
the run and the report disagree, that disagreement is the finding.

Bounded on purpose. Nothing here snapshots a paragraph, because a test that pins wording
prevents editing rather than preventing error.
"""

from __future__ import annotations

import json
import math
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASE = ROOT / "cases" / "B2_wellbore_storage_window"
SUMMARY = json.loads((CASE / "results" / "summary.json").read_text())
REPORT = (CASE / "report.md").read_text()
PROTOCOL = (CASE / "protocol.md").read_text()
HARD_STOP = (CASE / "HARD_STOP_01.md").read_text()
AMENDMENT = (CASE / "PROTOCOL_AMENDMENT_01.md").read_text()
EVIDENCE = (ROOT / "docs" / "evidence" / "pta_wellbore_storage.md").read_text()
FOLLOWUP = (ROOT / "docs" / "planning" / "B2_FOLLOWUP_WINDOW_RULE.md").read_text()

#: Every prose artefact B2 publishes, so a claim cannot hide in whichever one is unchecked.
B2_PROSE = {
    "report.md": REPORT,
    "protocol.md": PROTOCOL,
    "HARD_STOP_01.md": HARD_STOP,
    "PROTOCOL_AMENDMENT_01.md": AMENDMENT,
    "pta_wellbore_storage.md": EVIDENCE,
    "B2_FOLLOWUP_WINDOW_RULE.md": FOLLOWUP,
}

PARAMETER_KEYS = ("permeability_thickness_md_ft", "permeability_md", "skin", "slope_psi_per_cycle")


def walk(node, path=""):
    """Yield every (path, mapping) pair in the summary, so no branch escapes inspection."""
    if isinstance(node, dict):
        yield path, node
        for key, value in node.items():
            yield from walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from walk(value, f"{path}[{i}]")


class DecliningCasesReportNoParameters(unittest.TestCase):
    """Protocol section 7 and the reporting policy: INCONCLUSIVE carries no estimate.

    This is the test the whole case rests on. The rule's value is that it declines; if a
    declined case still emits a permeability somewhere in the artefact, the decline was
    decorative.
    """

    def test_no_analyst_block_that_declined_carries_a_parameter(self) -> None:
        checked = 0
        for path, node in walk(SUMMARY):
            if node.get("window_found") is not False:
                continue
            checked += 1
            for key in PARAMETER_KEYS:
                self.assertNotIn(
                    key,
                    node,
                    f"{path} declined but still carries {key}; a refused window must leave "
                    f"no estimate behind",
                )
        self.assertGreater(checked, 5, "the audit found almost no declining blocks to check")

    def test_the_declining_blocks_say_why(self) -> None:
        for path, node in walk(SUMMARY):
            if node.get("window_found") is False:
                self.assertEqual(node.get("verdict"), "INCONCLUSIVE", path)
                self.assertTrue(str(node.get("reason", "")).strip(), f"{path} declined silently")

    def test_every_truth_scored_block_is_labelled_as_such(self) -> None:
        """A number scored against the generator is never an analyst result."""
        labelled = 0
        for path, node in walk(SUMMARY):
            if "basis" in node and "EX POST" in str(node["basis"]):
                labelled += 1
            if "permeability_thickness_relative_error" in node or "skin_absolute_error" in node:
                self.assertIn(
                    "EX POST",
                    str(node.get("basis", "")),
                    f"{path} scores against truth without saying so",
                )
        self.assertGreater(labelled, 3)


class TheFailureStaysVisible(unittest.TestCase):
    """C4 failed. The artefact must keep saying so, near the front and without euphemism."""

    def test_the_snapshot_records_c4_as_failed(self) -> None:
        self.assertIs(SUMMARY["criteria"]["C4_window_detection_on_b2_1"]["met"], False)

    def test_the_primary_case_declined(self) -> None:
        self.assertIs(SUMMARY["b2_1_primary_noise_free"]["analyst"]["window_found"], False)

    def test_the_report_names_c4_in_its_first_third(self) -> None:
        head = REPORT[: len(REPORT) // 3]
        self.assertIn("C4", head, "C4's failure is not in the first third of the report")

    def test_the_classification_is_the_one_the_rules_produce(self) -> None:
        self.assertIn(SUMMARY["classification"], ("ESTABLISHED", "INCONCLUSIVE", "INVALID"))
        self.assertIn(SUMMARY["classification"], REPORT)

    def test_no_verification_criterion_failed_silently(self) -> None:
        for name, state in SUMMARY["criteria"].items():
            if state["met"] is None:
                self.assertTrue(
                    str(state.get("detail", "")).strip(), f"{name} is unevaluable without saying why"
                )


class PostHocStaysLabelled(unittest.TestCase):
    """Section 12 of the governing instruction: exploratory work is never a pre-registered one."""

    def test_the_namespace_is_separate(self) -> None:
        self.assertIn("posthoc_exploratory", SUMMARY)
        self.assertIn("POST-HOC", SUMMARY["posthoc_exploratory"]["label"])

    def test_it_is_not_among_the_criteria(self) -> None:
        for name in SUMMARY["criteria"]:
            self.assertNotIn("posthoc", name.lower())
            self.assertNotIn("duration_to_certif", name.lower())

    def test_the_report_marks_the_section(self) -> None:
        self.assertRegex(REPORT, r"(?i)post-hoc")

    def test_durations_are_not_reported_to_false_precision(self) -> None:
        for level in SUMMARY["posthoc_exploratory"]["levels"]:
            reported = level["reported_days"]
            if reported is None:
                continue
            self.assertRegex(reported, r"^about \d+(\.\d)? (hours|days)$", reported)

    def test_every_crossing_was_checked_both_sides(self) -> None:
        for level in SUMMARY["posthoc_exploratory"]["levels"]:
            selector = level["frozen_selector"]
            if not selector["certified"]:
                self.assertIn("searched_to_hours", selector)
                continue
            self.assertIs(selector["rerun_at_crossing_found"], True)
            self.assertIs(selector["rerun_below_crossing_found"], False)
            self.assertIs(selector["monotone_after_crossing"], True)


class ProjectRulesAreNotIndustryStandards(unittest.TestCase):
    """Section 4 of the governing instruction. The one-log-cycle extent is this project's."""

    STANDARD_WORDS = ("industry standard", "industry-standard", "standard practice", "mandatory minimum")

    #: A denial is the opposite of a claim. "it is not an industry-standard minimum" is the
    #: sentence this rule wants written, so the check looks for an unnegated assertion.
    NEGATIONS = (" not ", "never ", "no source", "rather than")

    def test_no_artefact_calls_the_window_extent_a_standard(self) -> None:
        for name, text in B2_PROSE.items():
            lowered = text.lower()
            for phrase in self.STANDARD_WORDS:
                for match in re.finditer(re.escape(phrase), lowered):
                    context = lowered[max(0, match.start() - 300) : match.end() + 300]
                    if "log cycle" not in context:
                        continue
                    before = lowered[max(0, match.start() - 120) : match.start()]
                    self.assertTrue(
                        any(negation in before for negation in self.NEGATIONS),
                        f"{name} asserts {phrase!r} of the log-cycle extent without negating it",
                    )

    def test_the_snapshot_declares_the_rule_as_project_defined(self) -> None:
        self.assertIn("PROJECT-DEFINED", SUMMARY["config"]["window_rule"]["status"])

    def test_the_report_says_whose_criterion_it_is(self) -> None:
        self.assertRegex(REPORT, r"(?i)project[- ]defined")


class FieldClaimsAreScoped(unittest.TestCase):
    """Section 5. A synthetic sweep never becomes a statement about field practice."""

    def test_no_artefact_presents_the_storage_range_as_typical_of_the_field(self) -> None:
        banned = ("practical field range", "typical field", "typical of field", "field practice range")
        for name, text in B2_PROSE.items():
            lowered = text.lower()
            for phrase in banned:
                if phrase in lowered:
                    index = lowered.index(phrase)
                    context = lowered[max(0, index - 400) : index + 400]
                    self.assertTrue(
                        any(
                            marker in context
                            for marker in ("withdrawn", "corrected", "not establish", "superseded")
                        ),
                        f"{name} carries {phrase!r} without the withdrawal that the source audit required",
                    )

    def test_the_evidence_register_records_the_withdrawal(self) -> None:
        self.assertIn("WITHDRAWN", EVIDENCE)
        self.assertRegex(EVIDENCE, r"(?i)uncited")

    def test_the_snapshot_limitations_scope_the_sweep(self) -> None:
        joined = " ".join(SUMMARY["limitations"]).lower()
        self.assertIn("synthetic", joined)
        self.assertRegex(joined, r"no source .* establishes them as a typical field range")


class ThresholdsDidNotMove(unittest.TestCase):
    """Section 14 and section 25. The rule that produced the result is the rule that was frozen."""

    def test_the_window_rule_constants_are_the_derived_ones(self) -> None:
        rule = SUMMARY["config"]["window_rule"]
        self.assertAlmostEqual(rule["flatness_epsilon"], 0.05 / math.log(10.0), places=15)
        self.assertEqual(rule["storage_ratio"], 0.10)
        self.assertEqual(rule["min_decades"], 1.0)
        self.assertEqual(rule["min_points"], 15)

    def test_the_protocol_still_declares_those_numbers(self) -> None:
        self.assertIn("0.0217", PROTOCOL)
        self.assertIn("W = 1.0", PROTOCOL)
        self.assertRegex(PROTOCOL, r"at least 15 points|15 points at 20 per decade")

    def test_the_scored_thresholds_are_the_protocol_thresholds(self) -> None:
        thresholds = SUMMARY["config"]["thresholds"]
        self.assertEqual(thresholds["C5_kh_relative"], 0.05)
        self.assertEqual(thresholds["C6_skin_absolute"], 0.5)
        self.assertEqual(thresholds["C7_derivative_relative"], 1e-3)
        self.assertEqual(thresholds["C1_known_inverse"], 1e-8)

    def test_the_sweep_levels_are_the_pre_registered_ones(self) -> None:
        config = SUMMARY["config"]
        self.assertEqual(config["storage_levels_dimensionless"], [100.0, 1000.0, 3000.0, 10000.0])
        self.assertEqual(config["duration_hours"], [48.0, 24.0, 12.0, 6.0, 3.0])
        self.assertEqual(config["sampling_per_decade"], [5, 10, 20, 50])
        self.assertEqual(config["noise_sigmas_psi"], [0.1, 0.5, 2.0, 10.0])
        self.assertEqual(config["noise_replicates"], 200)


class NothingExternalWasValidated(unittest.TestCase):
    """The standing honesty gate, extended to B2."""

    def test_saphir_is_not_run(self) -> None:
        self.assertEqual(SUMMARY["saphir_comparison"], "NOT RUN")
        self.assertRegex(REPORT, r"(?i)saphir[^.]{0,40}not run")

    def test_no_artefact_claims_a_saphir_comparison_happened(self) -> None:
        """A mention of Saphir's status is fine. A claim that it agreed is not."""
        claimed = re.compile(
            r"(?i)saphir[^.]{0,80}\b(confirm|confirms|confirmed|validat|agree|agrees|agreed|"
            r"match|matches|matched|reproduc)"
        )
        for name, text in B2_PROSE.items():
            self.assertIsNone(claimed.search(text), f"{name} implies a Saphir comparison occurred")

    def test_no_external_comparator(self) -> None:
        self.assertIn("NOT SELECTED", SUMMARY["external_comparator"])

    def test_no_field_or_peer_claim(self) -> None:
        self.assertEqual(SUMMARY["field_validation"], "NOT PERFORMED")
        self.assertEqual(SUMMARY["peer_review"], "NOT PERFORMED")

    def test_the_cross_check_is_not_called_an_independent_oracle(self) -> None:
        inversion = SUMMARY["numerical_qualification"]["inversion"]
        self.assertIn("not an independent physics oracle", inversion["cross_check_status"])

    def test_no_unaided_authorship_or_tooling_claim(self) -> None:
        for name, text in B2_PROSE.items():
            lowered = text.lower()
            for phrase in ("without assistance", "unaided", "generated with", "co-authored-by"):
                self.assertNotIn(phrase, lowered, f"{name} carries {phrase!r}")


class TheFollowUpIsNotImplemented(unittest.TestCase):
    """Section 15 and 33: the follow-up is planned, and planning is all it is."""

    def test_the_plan_declares_itself_unimplemented(self) -> None:
        self.assertRegex(FOLLOWUP, r"(?i)planning only")

    def test_it_selects_no_threshold(self) -> None:
        self.assertRegex(FOLLOWUP, r"(?i)no threshold is chosen|does not choose a threshold")

    def test_it_names_the_holdout_as_unrun(self) -> None:
        self.assertRegex(FOLLOWUP, r"(?i)prepared, not run|to be frozen before")

    def test_b2_data_are_marked_as_discovery_data(self) -> None:
        self.assertRegex(FOLLOWUP, r"(?i)discovery data")


if __name__ == "__main__":
    unittest.main()

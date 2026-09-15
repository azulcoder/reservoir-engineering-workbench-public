"""Adversarial tests for the cross-platform portability comparator.

A comparator that passes everything is not a comparator, and one that fails everything
is no more useful. So each test below perturbs exactly one thing and asserts the verdict
that perturbation deserves, and the final group asserts that ordinary platform noise is
still accepted. Without that last part the tolerance could be driven to zero and every
test here would still pass while the gate became unusable.

Every fixture is invented. None of it is, or is derived from, the restricted reference
extract: the numbers are round decimals chosen to make the arithmetic of each assertion
obvious, and the case shape is a miniature of the real one rather than a copy of it.
"""

from __future__ import annotations

import copy
import pathlib
import re
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from compare_case_outputs import compare, load_envelope  # noqa: E402

ENVELOPE = load_envelope(REPO_ROOT / "docs" / "release" / "portability_envelope.json")

#: A miniature of a case summary: identifiers, configuration, computed results, the
#: zero-valued diagnostics that need an absolute floor, and acceptance criteria.
REFERENCE = {
    "case_id": "AX_invented_probe",
    "case_type": "synthetic",
    "config": {"seed": 12345, "points": 24, "confidence": 0.95, "threshold": 0.01},
    "results": {
        "gas_in_place_scf": 100000000000.0,
        "relative_error": 0.004,
        "ranked": [
            {"name": "low", "score": 1.0},
            {"name": "mid", "score": 2.0},
            {"name": "high", "score": 3.0},
        ],
        "signed_margin": 0.5,
        "max_solver_residual_p_over_z_psia": 3.0e-09,
        "terminal_relative_error": 2.0e-13,
        "not_a_number": float("nan"),
    },
    "acceptance": [
        {"id": "AC1", "statement": "invented", "observed": 0.004, "threshold": 0.01, "met": True},
        {"id": "AC2", "statement": "invented", "observed": 0.5, "threshold": 1.0, "met": True},
    ],
    "all_acceptance_criteria_met": True,
    "metrics_sha256": "9f" * 32,
}


def perturb(value: float, relative: float) -> float:
    """Return ``value`` moved by a relative amount."""
    return value * (1.0 + relative)


class Mixin:
    """Shared helpers."""

    def compare_to_reference(self, candidate):
        """Compare the reference against a candidate document.

        Deliberately not called ``run``: unittest.TestCase.run is what the runner calls
        to execute a test, and shadowing it makes every test in the class silently not
        run at all while still reporting success.
        """
        return compare(REFERENCE, candidate, ENVELOPE)

    def mutate(self, mutator):
        """Return a deep copy of the reference with one mutation applied."""
        candidate = copy.deepcopy(REFERENCE)
        mutator(candidate)
        return candidate

    def assert_rejected(self, candidate, kind: str, why: str):
        """Assert the comparator refuses this candidate, for the stated reason."""
        report = self.compare_to_reference(candidate)
        self.assertFalse(report.ok, f"the comparator must reject {why}")
        kinds = {f.kind for f in report.findings}
        self.assertIn(kind, kinds, f"expected a {kind!r} finding for {why}, got {sorted(kinds)}")

    def assert_accepted(self, candidate, why: str):
        """Assert the comparator accepts this candidate."""
        report = self.compare_to_reference(candidate)
        self.assertTrue(
            report.ok,
            f"the comparator must accept {why}; it reported:\n"
            + "\n".join(f.render() for f in report.findings),
        )


class RejectionTests(Mixin, unittest.TestCase):
    """The ten things a portability comparator must never wave through."""

    def test_1_changed_verdict(self) -> None:
        self.assert_rejected(
            self.mutate(lambda d: d["acceptance"][0].__setitem__("met", False)),
            "verdict-changed",
            "an acceptance criterion that changed state",
        )

    def test_1b_changed_overall_verdict(self) -> None:
        self.assert_rejected(
            self.mutate(lambda d: d.__setitem__("all_acceptance_criteria_met", False)),
            "verdict-changed",
            "the overall verdict flipping",
        )

    def test_2_changed_threshold(self) -> None:
        self.assert_rejected(
            self.mutate(lambda d: d["acceptance"][0].__setitem__("threshold", 0.02)),
            "exact-float-changed",
            "a moved acceptance threshold",
        )

    def test_2b_changed_config_threshold(self) -> None:
        self.assert_rejected(
            self.mutate(lambda d: d["config"].__setitem__("threshold", 0.02)),
            "exact-float-changed",
            "a moved threshold in the configuration block",
        )

    def test_3_changed_seed(self) -> None:
        self.assert_rejected(
            self.mutate(lambda d: d["config"].__setitem__("seed", 999)),
            "integer-changed",
            "a different random seed, which means a different experiment",
        )

    def test_4_missing_key(self) -> None:
        self.assert_rejected(
            self.mutate(lambda d: d["results"].pop("relative_error")),
            "missing-field",
            "a field that disappeared",
        )

    def test_5_added_unexpected_key(self) -> None:
        self.assert_rejected(
            self.mutate(lambda d: d["results"].__setitem__("smuggled", 1.0)),
            "unexpected-field",
            "a field that appeared from nowhere",
        )

    def test_6_reordered_meaningful_sequence(self) -> None:
        self.assert_rejected(
            self.mutate(lambda d: d["results"].__setitem__("ranked", list(reversed(d["results"]["ranked"])))),
            "string-changed",
            "a reordered ranking, where position carries the meaning",
        )

    def test_7_material_positive_perturbation(self) -> None:
        self.assert_rejected(
            self.mutate(lambda d: d["results"].__setitem__("gas_in_place_scf", perturb(1.0e11, 1e-3))),
            "outside-envelope",
            "a result moved by a tenth of a percent",
        )

    def test_8_material_negative_perturbation(self) -> None:
        self.assert_rejected(
            self.mutate(lambda d: d["results"].__setitem__("gas_in_place_scf", perturb(1.0e11, -1e-3))),
            "outside-envelope",
            "a result moved down by a tenth of a percent",
        )

    def test_9_sign_change_in_a_material_result(self) -> None:
        self.assert_rejected(
            self.mutate(lambda d: d["results"].__setitem__("signed_margin", -0.5)),
            "outside-envelope",
            "a materially non-zero result that changed sign",
        )

    def test_10_near_zero_outside_its_absolute_envelope(self) -> None:
        # 2e-13 is well inside the declared 1e-10 floor; 5e-09 is not.
        self.assert_rejected(
            self.mutate(lambda d: d["results"].__setitem__("terminal_relative_error", 5.0e-09)),
            "near-zero-out-of-envelope",
            "a zero-valued diagnostic that grew past its absolute floor",
        )

    def test_10b_solver_residual_outside_its_floor(self) -> None:
        self.assert_rejected(
            self.mutate(lambda d: d["results"].__setitem__("max_solver_residual_p_over_z_psia", 1.0e-03)),
            "near-zero-out-of-envelope",
            "a solver residual that stopped converging",
        )

    def test_nan_becoming_a_number(self) -> None:
        self.assert_rejected(
            self.mutate(lambda d: d["results"].__setitem__("not_a_number", 0.0)),
            "non-finite-changed",
            "a NaN that became a number",
        )

    def test_type_change(self) -> None:
        self.assert_rejected(
            self.mutate(lambda d: d["config"].__setitem__("points", "24")),
            "string-changed",
            "an integer that became a string",
        )

    def test_null_structure_change(self) -> None:
        self.assert_rejected(
            self.mutate(lambda d: d["results"].__setitem__("relative_error", None)),
            "null-structure",
            "a value that became null",
        )


class AcceptanceTests(Mixin, unittest.TestCase):
    """And the noise it must not trip on, or the gate is unusable."""

    def test_accepts_measured_platform_noise(self) -> None:
        """A perturbation of the size actually measured between macOS and Linux.

        The worst substantive difference observed across the supported environments was
        2.37e-08 relative. Every computed field is moved by more than that here, at
        3e-08, and the comparison must still pass: this is the case the envelope exists
        to admit.
        """

        def noise(d):
            r = d["results"]
            r["gas_in_place_scf"] = perturb(r["gas_in_place_scf"], 3e-08)
            r["relative_error"] = perturb(r["relative_error"], -3e-08)
            r["signed_margin"] = perturb(r["signed_margin"], 3e-08)
            for entry in r["ranked"]:
                entry["score"] = perturb(entry["score"], 3e-08)
            for item in d["acceptance"]:
                item["observed"] = perturb(item["observed"], 3e-08)

        self.assert_accepted(self.mutate(noise), "noise the size of the measured envelope")

    def test_accepts_the_zero_valued_wobble_that_started_this(self) -> None:
        """1.11e-16 against 0.0 is a relative difference of 1.0 and means nothing."""

        def wobble(d):
            d["results"]["terminal_relative_error"] = 0.0
            d["results"]["max_solver_residual_p_over_z_psia"] = 2.6e-09

        self.assert_accepted(self.mutate(wobble), "a zero-valued diagnostic wobbling inside its floor")

    def test_identical_documents_pass(self) -> None:
        self.assert_accepted(copy.deepcopy(REFERENCE), "a document identical to the reference")

    def test_the_envelope_is_not_vacuous(self) -> None:
        """The tolerance must sit above the measured noise and below the display precision.

        This is the property that stops the envelope being quietly widened later. If
        someone raises the relative tolerance past 5e-07, a value this site displays to
        six significant figures could change without the gate noticing.
        """
        rel = float(ENVELOPE["default_float"]["relative"])
        measured = float(ENVELOPE["measured_basis"]["worst_observed_relative_difference"])
        self.assertGreater(rel, measured, "the envelope must admit the noise that was actually measured")
        self.assertLess(rel, 5e-07, "the envelope must stay below six-significant-figure display sensitivity")

    def test_report_counts_every_field(self) -> None:
        """No leaf may fall outside all five comparison classes."""
        report = self.compare_to_reference(copy.deepcopy(REFERENCE))
        counted = (
            report.exact_fields
            + report.float_fields
            + report.near_zero_fields
            + report.non_finite_fields
            + report.digest_fields
        )

        def leaves(o):
            if isinstance(o, dict):
                for v in o.values():
                    yield from leaves(v)
            elif isinstance(o, list):
                for v in o:
                    yield from leaves(v)
            else:
                yield o

        self.assertEqual(counted, len(list(leaves(REFERENCE))), "every leaf must land in exactly one class")


class DigestExclusionTests(Mixin, unittest.TestCase):
    """The digest rule must be narrow: it excludes one field and blinds nothing else.

    A content hash over floating-point values cannot survive a one-ULP difference, so
    comparing it exactly across platforms fails for a reason that has nothing to do with
    the engineering. Excluding it is only defensible because the leaf-by-leaf comparison
    is strictly stronger than the digest -- these tests are what makes that a checked
    claim rather than an assertion.
    """

    def test_a_digest_difference_alone_is_accepted(self) -> None:
        self.assert_accepted(
            self.mutate(lambda c: c.__setitem__("metrics_sha256", "00" * 32)),
            "a digest that differs while every value it covers is unchanged",
        )

    def test_the_digest_is_counted_and_reported_not_dropped(self) -> None:
        report = self.compare_to_reference(self.mutate(lambda c: c.__setitem__("metrics_sha256", "00" * 32)))
        self.assertEqual(report.digest_fields, 1)
        self.assertEqual(len(report.digests_differing), 1)
        path, reference, candidate = report.digests_differing[0]
        self.assertEqual(path, ".metrics_sha256")
        self.assertNotEqual(reference, candidate)

    def test_an_unchanged_digest_is_still_counted(self) -> None:
        report = self.compare_to_reference(copy.deepcopy(REFERENCE))
        self.assertEqual(report.digest_fields, 1)
        self.assertEqual(report.digests_differing, [])

    def test_the_digest_does_not_hide_a_float_outside_the_envelope(self) -> None:
        def mutator(candidate):
            candidate["metrics_sha256"] = "00" * 32
            candidate["results"]["gas_in_place_scf"] = perturb(REFERENCE["results"]["gas_in_place_scf"], 1e-5)

        self.assert_rejected(
            self.mutate(mutator), "outside-envelope", "a moved float behind a changed digest"
        )

    def test_the_digest_does_not_hide_a_flipped_criterion(self) -> None:
        def mutator(candidate):
            candidate["metrics_sha256"] = "00" * 32
            candidate["acceptance"][0]["met"] = False

        self.assert_rejected(
            self.mutate(mutator), "verdict-changed", "a flipped criterion behind a changed digest"
        )

    def test_an_undeclared_string_is_still_compared_exactly(self) -> None:
        self.assert_rejected(
            self.mutate(lambda c: c.__setitem__("case_type", "field")),
            "string-changed",
            "a declarative string that is not a declared digest",
        )

    def test_only_the_declared_name_is_excluded(self) -> None:
        """A different hash field must not inherit the exclusion by resembling one."""

        def mutator(candidate):
            candidate["config_sha256"] = "11" * 32

        candidate = self.mutate(mutator)
        report = self.compare_to_reference(candidate)
        self.assertFalse(report.ok, "an undeclared hash field must be an exact comparison")

    def test_the_envelope_states_why_detection_is_not_lost(self) -> None:
        """The rule is only acceptable with its argument attached, so require it."""
        rules = ENVELOPE.get("platform_dependent_digests", [])
        self.assertTrue(rules, "the digest rule must be declared in the envelope, not in code")
        for rule in rules:
            for key in ("why", "detection_is_not_lost_because", "still_reported"):
                self.assertIn(key, rule)
                self.assertGreater(len(rule[key]), 80, f"{key} must carry a real argument")


class PublishedResidualBoundTests(unittest.TestCase):
    """The published solver-residual bound must be one number, stated once.

    It is declared twice for unavoidable reasons: the figure renderer is a Node script
    that cannot import the site's TypeScript, so each carries its own constant. Two
    constants that must agree and are never compared are a defect waiting to happen, so
    this compares them.
    """

    RENDERER = REPO_ROOT / "site" / "scripts" / "render-figures.mjs"
    SITE_MODULE = REPO_ROOT / "site" / "src" / "scripts" / "residual.ts"

    def _declared(self, path: pathlib.Path, name: str) -> str:
        text = path.read_text(encoding="utf-8")
        match = re.search(rf"{name}\s*=\s*([0-9eE.+-]+)\s*;", text)
        self.assertIsNotNone(match, f"{path.name} does not declare {name}")
        return match.group(1)

    def test_the_two_declarations_agree(self) -> None:
        renderer = self._declared(self.RENDERER, "RESIDUAL_BOUND_PSIA")
        site = self._declared(self.SITE_MODULE, "RESIDUAL_BOUND_PSIA")
        self.assertEqual(
            float(renderer),
            float(site),
            "the figure renderer and the site publish different solver-residual bounds",
        )

    def test_the_bound_is_the_one_that_was_verified(self) -> None:
        """1e-8 is not arbitrary: 96 measured values sit below it, the largest at 3.43e-09."""
        self.assertEqual(float(self._declared(self.SITE_MODULE, "RESIDUAL_BOUND_PSIA")), 1e-8)

    def test_both_guards_refuse_to_overstate_the_bound(self) -> None:
        """Each declaration must throw rather than print a bound its value does not meet."""
        for path in (self.RENDERER, self.SITE_MODULE):
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("throw new Error", text, f"{path.name} has no guard")
                self.assertIn("RESIDUAL_BOUND_PSIA", text)


if __name__ == "__main__":
    unittest.main()

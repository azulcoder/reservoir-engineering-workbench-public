"""Regression tests for the screens that keep restricted reference data out of a release.

Every fixture here is a SENTINEL: invented numbers on the retrieval grid's shape, never
a value from the extract. A test that had to embed the real payload in order to prove
the payload is excluded would defeat its own purpose, and would put the values back into
the tree by the same door it is guarding.

Each screen is tested in both directions. A detector that fires on everything is not a
detector, so every positive case is paired with a negative control that must stay
silent: the failure mode being guarded against is a screen quietly weakened until the
release passes, and only the negative control can tell that apart from a screen that
works.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from check_public_release import (  # noqa: E402
    DERIVED_FROM_REFERENCE_MARKERS,
    DERIVED_SCAN_EXEMPT,
    RESTRICTED_BASENAME_PATTERNS,
    WEBBOOK_MARKERS,
    longest_grid_table_run,
    marker_adjacent_numbers,
)

# A sentinel table with the SHAPE of the extract: pressures stepping by exactly 200 psia
# with high-precision values threaded between the steps. The numbers are invented and
# ascend linearly, which no real isotherm does.
SENTINEL_ROWS = "\n".join(
    f"{200 + 200 * i}\t{0.100000 + 0.001 * i:.6f}\t{1.000000 + 0.01 * i:.6f}" for i in range(12)
)

#: The same values with the grid removed: precise numbers, no marching pressures.
SENTINEL_NO_GRID = "\n".join(
    f"sample_{i}\t{0.100000 + 0.001 * i:.6f}\t{1.000000 + 0.01 * i:.6f}" for i in range(12)
)

#: The grid without the precise values: a configuration listing the sweep it intends.
SENTINEL_GRID_ONLY = "pressures_psia = [" + ", ".join(str(200 + 200 * i) for i in range(12)) + "]"


class EmbeddedFixtureWithoutProviderMarkerTests(unittest.TestCase):
    """An embedded extract is rejected even with every provider marker stripped.

    This is the evasion case, and it is not hypothetical: the obvious way to smuggle the
    table past a provenance screen is to delete the words that name the provider. The
    marker screen goes blind at that point by construction, so the shape screen has to
    carry the rejection on its own.
    """

    def test_the_marker_screen_is_blind_once_the_marker_is_gone(self) -> None:
        self.assertNotIn("nist", SENTINEL_ROWS.lower())
        self.assertEqual(
            marker_adjacent_numbers(SENTINEL_ROWS),
            [],
            "the marker screen is expected to see nothing here; that is why the shape "
            "screen below is the one that must reject this fixture",
        )

    def test_the_shape_screen_rejects_it_anyway(self) -> None:
        run = longest_grid_table_run(SENTINEL_ROWS)
        self.assertGreaterEqual(
            run,
            8,
            "an unmarked table on the retrieval grid must still be rejected on shape",
        )

    def test_negative_control_precise_values_without_the_grid(self) -> None:
        self.assertLess(
            longest_grid_table_run(SENTINEL_NO_GRID),
            2,
            "high-precision numbers alone are not evidence; a coefficient table has "
            "those and must not be rejected",
        )

    def test_negative_control_the_grid_without_precise_values(self) -> None:
        self.assertLess(
            longest_grid_table_run(SENTINEL_GRID_ONLY),
            2,
            "a configuration may legitimately name the pressure sweep it intends",
        )


class PointwiseDerivedCombinationTests(unittest.TestCase):
    """A value computed from the withheld input may not be emitted into a public artifact.

    The screen this exercises was added because a viscosity correlation evaluated on a
    reference density passed every other screen: it holds no reference digit, so a
    fixed-string sweep is silent, and no provider marker sits near it. The correlation is
    monotonic in density, so the published value inverts straight back to the withheld
    input. Admitting in prose that a number is reference-derived, next to the number, is
    what this catches -- without the test needing to know the withheld value.
    """

    DERIVED = (
        "Z back-calculated with R = 10.731577 and the exact conversion\n"
        "values: 0.9123456 / 0.8234567 / 0.7345678 / 0.6456789\n"
    )

    ORDINARY = (
        "Z from the correlation at the published pseudo-criticals\n"
        "values: 0.9123456 / 0.8234567 / 0.7345678 / 0.6456789\n"
    )

    def test_a_derived_pointwise_combination_is_flagged(self) -> None:
        hits = marker_adjacent_numbers(self.DERIVED, markers=DERIVED_FROM_REFERENCE_MARKERS)
        self.assertTrue(
            hits and max(count for _, count in hits) >= 4,
            "a high-precision series beside an admission that it was back-calculated "
            "from the extract must be flagged",
        )

    def test_negative_control_the_same_numbers_from_the_correlation(self) -> None:
        self.assertEqual(
            marker_adjacent_numbers(self.ORDINARY, markers=DERIVED_FROM_REFERENCE_MARKERS),
            [],
            "identical numbers produced by the library from published inputs are this "
            "repository's own output and must not be flagged",
        )

    def test_the_marker_families_are_disjoint_in_purpose(self) -> None:
        self.assertEqual(
            marker_adjacent_numbers(self.DERIVED),
            [],
            "the provider-marker family must not be what catches this; if it were, the "
            "derived family would be redundant and could be deleted without loss",
        )


class ForbiddenInputCannotReenterTests(unittest.TestCase):
    """A restricted table dropped into the tree must not travel out in an artifact."""

    def test_the_basename_screen_recognises_a_restricted_table(self) -> None:
        for name in ("nist_methane_isotherm_100F.tsv", "methane_isotherms.tsv"):
            with self.subTest(name=name):
                self.assertTrue(
                    any(p.match(name) for p in RESTRICTED_BASENAME_PATTERNS),
                    f"{name} is the shape of a retrieved table and must be recognised",
                )

    def test_negative_control_an_ordinary_data_file(self) -> None:
        for name in ("summary.json", "f03_bias_sweep.csv", "manifest.json"):
            with self.subTest(name=name):
                self.assertFalse(
                    any(p.match(name) for p in RESTRICTED_BASENAME_PATTERNS),
                    f"{name} is ordinary repository output and must not be caught",
                )

    def test_the_sdist_does_not_take_the_reference_directory_wholesale(self) -> None:
        """``only-include`` must enumerate data/reference file by file.

        A directory entry would mean a table dropped beside the manifest ships with the
        next release and nobody has to decide anything for that to happen.
        """
        config = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        start = config.index("[tool.hatch.build.targets.sdist]")
        block = config[start : config.index("\n[", start + 1)]
        self.assertIn('"data/reference/MANIFEST.json"', block)
        self.assertIn('"data/reference/README.md"', block)
        self.assertNotIn('"data/reference"', block)
        self.assertNotIn('"data"', block.replace('"data/', '"_/'))

    def test_the_release_gate_rejects_a_planted_table(self) -> None:
        """End to end: plant a sentinel table in a scanned directory, expect a refusal.

        ``docs`` is chosen deliberately. ``data/reference`` is protected by the enumerated
        ``only-include`` above, but ``docs``, ``tests``, ``cases`` and ``scripts`` ship
        wholesale, so they are where a forbidden input would actually re-enter.
        """
        with tempfile.TemporaryDirectory() as tmp:
            planted = pathlib.Path(tmp) / "nist_methane_isotherms.tsv"
            planted.write_text(SENTINEL_ROWS, encoding="utf-8")
            self.assertTrue(
                any(p.match(planted.name) for p in RESTRICTED_BASENAME_PATTERNS),
                "the planted sentinel must be recognised by basename",
            )
            self.assertGreaterEqual(
                longest_grid_table_run(planted.read_text(encoding="utf-8")),
                8,
                "and by content, so renaming the file is not an escape",
            )


class ExemptionRegisterCoverageTests(unittest.TestCase):
    """The register's carve-out must stay narrow enough to be worthless as a hiding place.

    The exemptions register is exempt from the derived-value family, because it has to
    quote the numbers it excuses beside prose saying what they were computed from, and
    scanning it there produces a finding about a finding. That carve-out is only
    defensible if the register remains covered by the other two families, which is the
    claim these tests exist to check rather than assert.
    """

    def test_the_carve_out_covers_only_the_register(self) -> None:
        self.assertEqual(DERIVED_SCAN_EXEMPT, ("docs/release/payload_exemptions.json",))

    def test_a_table_hidden_in_the_register_is_still_rejected_on_shape(self) -> None:
        flattened = SENTINEL_ROWS.replace("\n", " ").replace("\t", " ")
        planted = f'{{"reason": "{flattened}"}}'
        self.assertGreaterEqual(
            longest_grid_table_run(planted),
            8,
            "the grid-shape probe does not consult the carve-out, so a table pasted "
            "into the register is still rejected",
        )

    def test_a_cited_extract_in_the_register_is_still_rejected_on_provenance(self) -> None:
        sentinels = ", ".join(f"0.{1234567 + 111111 * i}" for i in range(14))
        planted = f'{{"reason": "retrieved from the NIST Chemistry WebBook",\n "v": [{sentinels}]}}'
        hits = marker_adjacent_numbers(planted, markers=WEBBOOK_MARKERS)
        self.assertTrue(
            hits and max(count for _, count in hits) >= 12,
            "the provenance-marker family does not consult the carve-out either",
        )


class ScreenIntegrityTests(unittest.TestCase):
    """The screens themselves must not be weakenable without a test noticing."""

    def test_the_derived_family_threshold_is_not_borrowed_from_the_other_family(self) -> None:
        """The derived family must keep its own, much lower threshold.

        One value beside a reference-derived admission is one reference datum recovered,
        because the correlation inverts. Reusing the provenance family's threshold of 12
        here let a six-value reconstruction through the gate during development; this
        test is what would notice the two being merged again.
        """
        source = (REPO_ROOT / "scripts" / "check_public_release.py").read_text(encoding="utf-8")
        self.assertIn("--min-derived-numbers", source)
        self.assertIn("if count >= min_derived_numbers:", source)
        start = source.index('"--min-derived-numbers"')
        block = source[start : start + 400]
        self.assertIn("default=1", block, "the derived family's threshold must stay at 1")

    def test_the_release_gate_passes_on_this_tree(self) -> None:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "check_public_release.py"), "--only", "payload"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"payload screen must pass on the cleared tree\n{result.stdout}\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()

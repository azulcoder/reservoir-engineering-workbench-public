"""Verification of ``reservoir_lab.gas_properties``.

The four contract categories (``docs/api_contract.md`` C7) map onto this file as
follows.

*Independent oracle.* The NIST Chemistry WebBook extract loaded by
:mod:`oracles.nist` -- reference equations of state from a different model family,
produced by a different organisation, sharing no code with anything here -- compared
against all three deviation-factor correlations, plus two published worked examples
(Wichert-Aziz epsilon and the sour-gas pseudocritical chain), the published
formation-volume-factor coefficients, and one closed-form limit of the viscosity
correlation.

*Limiting case.* The ideal-gas limit of Z as Ppr falls, the ideal-gas limit of
compressibility, and the zero-density limit of Lee-Gonzalez-Eakin, which isolates the
K group from the exponential.

*Invalid input.* Every documented raise in the module is exercised, and so is every
documented raise in the oracle loader :mod:`oracles.nist` -- the loader is the chain of
custody between the published NIST values and the numbers asserted on here, and a guard
that is never executed is a guard that is assumed.

*Property or invariant.* The residual of the converged root against an independently
retyped polynomial, the analytic derivatives against central differences, the
insensitivity of the returned root to a tightened solver tolerance, and the
cross-correlation agreement bands.

Where the fix belongs in ``src`` and not here, the gap is carried as an
``unittest.expectedFailure`` naming the contract clause it violates, so that the suite
says what is missing instead of staying quiet about it, and so that fixing the source
turns the suite red until the expectation is removed deliberately.

Two things this file deliberately does not do.

It does not set a tolerance by looking at what the implementation produced. Every gate
below is argued from a published accuracy figure or from a numerical-analysis bound
before the number is compared, and the argument is written next to the gate. Where the
observed agreement is much better than the gate, the observed figure appears in a
comment as information, not as the gate.

It does not treat agreement between Dranchuk-Abou-Kassem and Dranchuk-Purvis-Robinson
as evidence. The two share the Benedict-Webb-Rubin structure, the 0.27 reduced-density
constant and the same 1500 digitised Standing-Katz points; they are one fit published
twice. Hall-Yarborough is a different functional family fitted by different authors, so
DAK-versus-HY is the informative comparison and DAK-versus-DPR is the weak one. The
test names say which is which.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import pathlib
import statistics
import sys
import unittest
import warnings
from contextlib import contextmanager
from dataclasses import dataclass

from oracles import nist
from reservoir_lab import gas_properties as gp
from reservoir_lab.errors import (
    ConvergenceError,
    InvalidInputError,
    OutOfRangeWarningError,
    RangeWarning,
)
from reservoir_lab.gas_properties import (
    PseudoCriticals,
    _dak_dz_drho,
    _dak_z_of_reduced_density,
    _dpr_dz_drho,
    _dpr_z_of_reduced_density,
)
from reservoir_lab.units import (
    SPE_STANDARD,
    StandardConditions,
    fahrenheit_to_rankine,
    lbm_per_cuft_to_g_per_cc,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "src" / "reservoir_lab"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


@contextmanager
def quiet_range_warnings():
    """Silence :class:`RangeWarning` inside the block.

    Several tests deliberately evaluate a correlation outside its published window --
    that is the thing under test. Silencing the warning locally keeps the suite's
    output meaningful, and the tests that check the warning *fires* do so explicitly
    rather than relying on it leaking out of an unrelated test.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RangeWarning)
        yield


@dataclass(frozen=True)
class ErrorStatistics:
    """Summary of a set of signed relative errors.

    Attributes
    ----------
    count:
        Number of points compared.
    mean_absolute:
        Mean of the absolute relative errors.
    median_absolute:
        Median of the absolute relative errors.
    max_absolute:
        Largest absolute relative error.
    min_signed, max_signed:
        Extremes of the signed error, which is what reveals a one-sided bias.
    worst_label:
        Human-readable identification of the worst point.
    """

    count: int
    mean_absolute: float
    median_absolute: float
    max_absolute: float
    min_signed: float
    max_signed: float
    worst_label: str

    def describe(self, name: str) -> str:
        """One-line summary, used both in reports and in assertion messages."""
        return (
            f"{name}: n={self.count} mean|e|={100 * self.mean_absolute:.3f}% "
            f"median|e|={100 * self.median_absolute:.3f}% max|e|={100 * self.max_absolute:.3f}% "
            f"signed range {100 * self.min_signed:+.3f}%..{100 * self.max_signed:+.3f}% "
            f"worst at {self.worst_label}"
        )


def summarise(errors: list[tuple[float, str]]) -> ErrorStatistics:
    """Reduce ``[(signed_relative_error, label), ...]`` to :class:`ErrorStatistics`."""
    if not errors:
        raise AssertionError("no points were compared; an empty comparison is not a pass")
    absolute = [abs(value) for value, _ in errors]
    worst = max(errors, key=lambda item: abs(item[0]))
    return ErrorStatistics(
        count=len(errors),
        mean_absolute=statistics.fmean(absolute),
        median_absolute=statistics.median(absolute),
        max_absolute=max(absolute),
        min_signed=min(value for value, _ in errors),
        max_signed=max(value for value, _ in errors),
        worst_label=worst[1],
    )


#: Dranchuk & Abou-Kassem (1975) A1..A11, retyped here from the published paper rather
#: than imported, so that the independent evaluation below is independent of the
#: module's own transcription as well as of its algorithm.
DAK_COEFFICIENTS = (
    0.3265,
    -1.0700,
    -0.5339,
    0.01569,
    -0.05165,
    0.5475,
    -0.7361,
    0.1844,
    0.1056,
    0.6134,
    0.7210,
)


def dak_z_by_bisection(t_pr: float, p_pr: float, coefficients: tuple[float, ...] = DAK_COEFFICIENTS) -> float:
    """Z from the DAK correlation, evaluated independently of the module under test.

    Two things differ from the production path and both are deliberate. The eleven
    coefficients are retyped from the paper, so a transcription slip in either copy
    shows up as a disagreement. The root is found by pure bisection rather than by the
    module's safeguarded Newton, so a defect in the solver -- a spurious root, an early
    exit, a bracket that does not contain the root -- cannot be shared between the two
    sides. The algebraic form is necessarily the same; that is what is being compared.

    Two hundred halvings of a bracket of order one drives the interval to well below
    machine epsilon, so this side's own numerical error is not a term in any budget.
    """
    a = coefficients

    def z_of(rho: float) -> float:
        u = a[10] * rho**2
        return (
            1.0
            + (a[0] + a[1] / t_pr + a[2] / t_pr**3 + a[3] / t_pr**4 + a[4] / t_pr**5) * rho
            + (a[5] + a[6] / t_pr + a[7] / t_pr**2) * rho**2
            - a[8] * (a[6] / t_pr + a[7] / t_pr**2) * rho**5
            + (a[9] / t_pr**3) * rho**2 * (1.0 + u) * math.exp(-u)
        )

    target = 0.27 * p_pr / t_pr

    def residual(rho: float) -> float:
        return rho * z_of(rho) - target

    low, high = 1.0e-14, 1.0
    while residual(high) < 0.0:
        high *= 2.0
    for _ in range(200):
        middle = 0.5 * (low + high)
        if residual(middle) < 0.0:
            low = middle
        else:
            high = middle
    return 0.27 * p_pr / (0.5 * (low + high) * t_pr)


def load_or_skip(test_case: unittest.TestCase, species: str) -> nist.ReferenceSpecies:
    """Load a verified species table, skipping the test if the extract is absent."""
    nist.require_reference_data(test_case)
    return nist.load_species(species)


def true_criticals(species: nist.ReferenceSpecies) -> PseudoCriticals:
    """Wrap a pure component's TRUE critical constants as a :class:`PseudoCriticals`.

    For a pure component the reduced properties are the real Tr and pr. Entering the
    correlations this way keeps Standing and Sutton out of the comparison, so a
    disagreement is attributable to the deviation-factor correlation alone.
    """
    return PseudoCriticals(
        species.critical.temperature_degr,
        species.critical.pressure_psia,
        correlation=f"true critical constants, {species.name}",
    )


# ---------------------------------------------------------------------------
# C8: dependency policy
# ---------------------------------------------------------------------------


class StandardLibraryOnlyTests(unittest.TestCase):
    """Contract C8: ``src/reservoir_lab`` imports the standard library and nothing else.

    The check walks the AST of every module rather than importing them, so a module
    that is not imported by ``__init__`` is still covered, and so the check reports the
    offending file and line rather than an ImportError from somewhere in the stack.

    Limitation worth stating: an AST walk sees ``import`` statements. A dynamic import
    through ``importlib`` or ``__import__`` would evade it. Neither appears in the
    package today; if one ever does, this test needs extending rather than trusting.
    """

    def module_paths(self) -> list[pathlib.Path]:
        paths = sorted(PACKAGE_ROOT.rglob("*.py"))
        # An empty walk would pass every assertion below while checking nothing.
        self.assertGreaterEqual(len(paths), 5, f"expected to find the package modules under {PACKAGE_ROOT}")
        return paths

    def test_every_top_level_import_is_stdlib_or_internal(self):
        offenders = []
        for path in self.module_paths():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        continue  # a relative import is internal by construction
                    names = [node.module or ""]
                else:
                    continue
                for name in names:
                    root = name.split(".")[0]
                    if root == "reservoir_lab" or root in sys.stdlib_module_names:
                        continue
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} imports {name!r}")
        self.assertEqual(
            offenders,
            [],
            "src/reservoir_lab must import only the standard library (contract C8): " + "; ".join(offenders),
        )

    def test_package_does_not_import_the_test_helpers(self):
        # The oracles package is a test-side dependency. If the implementation ever
        # imported it, the oracle would no longer be independent of the code it checks.
        #
        # This walks the AST rather than searching the source text. A substring search
        # for "import oracles" misses "from oracles import nist", which is the form the
        # import would actually take, so the text version could not fail in the case it
        # exists to prevent.
        offenders = []
        for path in self.module_paths():
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and not node.level:
                    names = [node.module or ""]
                else:
                    continue
                for name in names:
                    if name.split(".")[0] == "oracles":
                        offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} imports {name!r}")
        self.assertEqual(
            offenders, [], "the package must not import the test oracles: " + "; ".join(offenders)
        )

    def test_the_oracle_import_guard_sees_the_from_import_form(self):
        # Positive control for the guard above, and the reason it is an AST walk: the
        # form a real accidental import would take is "from oracles import nist", which
        # a substring search for "import oracles" does not match at all.
        tree = ast.parse("from oracles import nist\n")
        found = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "oracles"
        ]
        self.assertEqual(found, ["oracles"])
        self.assertEqual("from oracles import nist".find("import oracles"), -1)


# ---------------------------------------------------------------------------
# The oracle loader itself
# ---------------------------------------------------------------------------


class ReferenceLoaderTests(unittest.TestCase):
    """The oracle has to be trustworthy before anything measured against it is."""

    def test_every_species_loads_with_the_expected_shape(self):
        nist.require_reference_data(self)
        for name in nist.SPECIES:
            with self.subTest(species=name):
                species = nist.load_species(name)
                self.assertEqual(len(species.states), 150)
                self.assertGreater(species.molar_mass_lbm_per_lbmol, 0.0)
                self.assertTrue(species.eos_reference)
                # Both citations, not just the equation of state. The viscosity
                # attribution is the one a report would print next to the LGE
                # comparison, and it was previously asserted nowhere at all.
                self.assertTrue(species.viscosity_reference)
                for state in species.states:
                    self.assertGreater(state.density_lbm_per_cuft, 0.0)
                    self.assertGreater(state.viscosity_upa_s, 0.0)
                    self.assertIn(state.phase, {"vapor", "liquid", "supercritical"})

    def test_digest_mismatch_raises_rather_than_skipping(self):
        # The whole point of the manifest: an edited reference file must not be able to
        # make a failing test pass. Verified on a temporary file so the committed
        # extract is never touched.
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "edited.tsv"
            path.write_text("not the reference data\n", encoding="utf-8")
            with self.assertRaises(nist.ReferenceDataError):
                nist._verify_digest(path, "0" * 64)

    def test_unknown_species_raises(self):
        nist.require_reference_data(self)
        with self.assertRaises(KeyError):
            nist.load_species("argon")

    def test_critical_constants_are_consistent_with_the_field_unit_figures(self):
        # Cross-check of the module's SI critical constants against the degF/psia
        # figures the same NIST fluid pages print. The conversion runs through the
        # exact factors in reservoir_lab.units, so a mismatch means a transcription
        # error in the SI values, not a rounding artefact.
        expected = {
            "methane": (-116.65, 667.06),
            "carbon_dioxide": (87.7608, 1070.0),
            "nitrogen": (-232.524, 492.52),
        }
        # Tolerance argument, per species and fixed before the residuals were looked
        # at. A printed figure that has been correctly rounded differs from the value
        # behind it by at most half of its own display resolution, so that is the bound
        # a correct SI transcription has to satisfy, and it is the largest bound that
        # can still fail on an incorrect one. It is NOT the coarsest of the three
        # applied to all three: 1070.0 is printed to one decimal (half-resolution
        # 0.05 psia) while 667.06 and 492.52 are printed to two (half-resolution
        # 0.005 psia), and the same reasoning gives 0.005 degF, 0.00005 degF and
        # 0.0005 degF on the three temperatures.
        for name, (degf, psia), (temperature_delta, pressure_delta) in (
            ("methane", (-116.65, 667.06), (0.005, 0.005)),
            ("carbon_dioxide", (87.7608, 1070.0), (0.00005, 0.05)),
            ("nitrogen", (-232.524, 492.52), (0.0005, 0.005)),
        ):
            with self.subTest(species=name):
                constants = nist.CRITICAL_CONSTANTS[name]
                # A degF interval and a degR interval are the same size, so the
                # half-resolution of the printed degF figure transfers unchanged.
                self.assertAlmostEqual(
                    constants.temperature_degr,
                    fahrenheit_to_rankine(degf),
                    delta=temperature_delta,
                )
                self.assertAlmostEqual(constants.pressure_psia, psia, delta=pressure_delta)
        self.assertEqual(set(expected), set(nist.CRITICAL_CONSTANTS))

    def test_deviation_factor_uses_the_field_gas_constant(self):
        # Replaces a round-trip through gas_density_lbm_per_cuft, which was an exact
        # algebraic identity: Z = pM/(rho R T) composed with rho = pM/(Z R T) cancels R
        # and M, and passed to machine precision with the gas constant set to 42.
        #
        # Here R is written out in the test from the SI definitions instead, so the
        # comparison has a value that did not come out of the package. With
        # R = 8.314462618153240 J/(mol K) (exact, SI defining constants) and the exact
        # definitions lbm = 453.59237 g, ft = 0.3048 m, in = 0.0254 m, g0 = 9.80665
        # m/s^2, the field-unit value is 10.7315770890 psia ft^3 / (lbmol degR), quoted
        # here to twelve significant figures. The truncation of the literal is 1.5e-12
        # relative, so 1e-10 is the gate: two orders above the literal's own error and
        # far below any transcription slip.
        gas_constant_field = 10.7315770890
        species = load_or_skip(self, "methane")
        for state in species.states[:20]:
            expected = (
                state.pressure_psia
                * species.molar_mass_lbm_per_lbmol
                / (state.density_lbm_per_cuft * gas_constant_field * state.temperature_degr)
            )
            self.assertAlmostEqual(species.deviation_factor(state) / expected, 1.0, delta=1.0e-10)

    def test_deviation_factor_approaches_unity_in_the_ideal_gas_limit(self):
        # The physical check the algebraic round-trip could not make. At the lowest
        # pressure in the extract, 200 psia, methane and nitrogen sit at reduced
        # pressure below 0.31 and reduced temperature above 1.6, where the second
        # virial correction to Z is a couple of percent at most. Ten percent is the
        # stated bound: comfortably outside the real gas imperfection, and nowhere near
        # wide enough to admit a wrong gas constant, a lbm/lbmol slip or a degF-for-degR
        # mistake, each of which moves Z by tens of percent or more.
        #
        # Carbon dioxide is excluded by argument, not by result: its 100 degF isotherm
        # is at Tr = 1.02, where the virial expansion is not a small correction.
        for name in ("methane", "nitrogen"):
            species = load_or_skip(self, name)
            for state in species.states:
                if state.pressure_psia != 200.0:
                    continue
                with self.subTest(species=name, temperature_degf=state.temperature_degf):
                    self.assertAlmostEqual(species.deviation_factor(state), 1.0, delta=0.10)

    def test_manifest_methane_viscosity_citation_contradicts_the_evidence_card(self):
        # Known provenance defect, recorded as an expected failure because the fix is in
        # data/reference/MANIFEST.json and not in this file.
        #
        # docs/evidence/viscosity.md records, marked verified verbatim from the WebBook
        # fluid page for C74828, that NIST cites Quinones-Cisneros, Huber and Deiters
        # (unpublished work, 2011) for methane viscosity, along with that model's
        # uncertainty ladder. MANIFEST.json attributes the same column to Younglove &
        # Ely (1987), and the manifest is the machine-readable field that travels into a
        # report. Correcting the manifest makes this pass, which will fail the suite as
        # an unexpected success and force the expectation to be removed deliberately.
        species = load_or_skip(self, "methane")
        self.assertNotIn("Younglove", species.viscosity_reference)


class ReferenceLoaderGuardTests(unittest.TestCase):
    """Every documented raise in :mod:`oracles.nist`, exercised on a fixture extract.

    Contract C7 category three applies to the oracle loader as much as to the library:
    the loader exists to keep the chain of custody between the published NIST values
    and the numbers this suite asserts on, and its guards were previously dead code.
    Nine of the ten raise sites were never executed, which means the digest-and-shape
    story rested on guards nobody had ever seen fire.

    Each test builds a small fixture directory and points the module's two path
    constants at it, so the committed extract is never touched and no test depends on
    another's mutation.
    """

    HEADER = "Temperature (F)\tPressure (psia)\tDensity (lbm/ft3)\tViscosity (uPa*s)\tPhase"
    # An INVENTED row, not a row of the reference extract. These tests exercise the
    # parser, the schema and the digest guard, none of which cares what the numbers mean,
    # so the fixture is generated here rather than taken from data this project does not
    # redistribute. The temperature, pressure, density and viscosity below are chosen to
    # be well-formed and obviously not a retrieval: they are on no isotherm and no grid.
    # See docs/release/PUBLIC_DATA_POLICY.md.
    ROW = "137.00000\t321.00000\t0.71828180\t13.579000\tvapor"

    @contextmanager
    def fixture(self, *, table: str | None, rows: int = 2, species: str = "methane"):
        """Yield a temporary reference directory with ``nist.REFERENCE_DIR`` pointed at it.

        ``table`` is written verbatim so a test can supply a malformed one; the manifest
        digest is computed from whatever was written, which is what lets a test reach
        the parsing guards that sit downstream of the digest check. ``table=None``
        writes no table file at all.
        """
        import tempfile
        from unittest import mock

        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            path = root / "fixture.tsv"
            digest = ""
            if table is not None:
                path.write_text(table, encoding="utf-8")
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            manifest = {
                "files": [
                    {
                        "path": "fixture.tsv",
                        "species": species,
                        "formula": "CH4",
                        "molar_mass_lbm_per_lbmol": 16.0425,
                        "eos_reference": "fixture",
                        "viscosity_reference": "fixture",
                        "rows": rows,
                        "sha256": digest,
                    }
                ]
            }
            (root / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
            with (
                mock.patch.object(nist, "REFERENCE_DIR", root),
                mock.patch.object(nist, "MANIFEST_PATH", root / "MANIFEST.json"),
            ):
                yield root

    def default_table(self, rows: int = 2) -> str:
        return "\n".join([self.HEADER] + [self.ROW] * rows) + "\n"

    def test_the_fixture_itself_loads(self):
        # Positive control. Without it, every test below could be passing because the
        # fixture is broken in some way of its own rather than in the way it names.
        with self.fixture(table=self.default_table()):
            species = nist.load_species("methane")
        self.assertEqual(len(species.states), 2)
        self.assertEqual(species.states[0].phase, "vapor")
        self.assertAlmostEqual(species.states[0].density_lbm_per_cuft, 0.71828180)

    def test_a_non_numeric_cell_is_reported_with_its_file_line_and_column(self):
        table = self.HEADER + "\n" + self.ROW.replace("0.71828180", "undefined") + "\n"
        with self.fixture(table=table, rows=1), self.assertRaises(nist.ReferenceDataError) as caught:
            nist.load_species("methane")
        message = str(caught.exception)
        self.assertIn("Density (lbm/ft3)", message)
        self.assertIn("line 2", message)

    def test_a_non_finite_cell_is_rejected_rather_than_propagated(self):
        # float("infinite") raises, float("inf") does not: the second is the one that
        # would otherwise travel into a mean as a NaN or an infinity.
        table = self.HEADER + "\n" + self.ROW.replace("13.579000", "inf") + "\n"
        with self.fixture(table=table, rows=1), self.assertRaises(nist.ReferenceDataError) as caught:
            nist.load_species("methane")
        self.assertIn("not finite", str(caught.exception))

    def test_an_empty_table_is_rejected(self):
        with self.fixture(table="", rows=0), self.assertRaises(nist.ReferenceDataError) as caught:
            nist.load_species("methane")
        self.assertIn("is empty", str(caught.exception))

    def test_a_renamed_column_header_is_rejected(self):
        # Columns are located by name, so a WebBook change of units -- "Density
        # (kg/m3)" for "Density (lbm/ft3)" -- must stop the load rather than silently
        # read a different column by position.
        table = self.default_table().replace("Density (lbm/ft3)", "Density (kg/m3)")
        with self.fixture(table=table), self.assertRaises(nist.ReferenceDataError) as caught:
            nist.load_species("methane")
        self.assertIn("expected columns", str(caught.exception))

    def test_a_short_row_is_rejected(self):
        table = self.HEADER + "\n" + self.ROW + "\n" + "100.0\t200.0\tvapor\n"
        with self.fixture(table=table, rows=2), self.assertRaises(nist.ReferenceDataError) as caught:
            nist.load_species("methane")
        self.assertIn("fields", str(caught.exception))

    def test_a_row_count_that_disagrees_with_the_manifest_is_rejected(self):
        # The guard that would catch a truncated download, which is the failure mode
        # that otherwise produces a smaller comparison that still passes.
        with (
            self.fixture(table=self.default_table(rows=2), rows=150),
            self.assertRaises(nist.ReferenceDataError) as caught,
        ):
            nist.load_species("methane")
        self.assertIn("150 rows", str(caught.exception))

    def test_a_manifest_entry_pointing_at_a_missing_file_is_rejected(self):
        with self.fixture(table=None), self.assertRaises(nist.ReferenceDataError) as caught:
            nist.load_species("methane")
        self.assertIn("not present", str(caught.exception))

    def test_a_species_without_recorded_critical_constants_is_rejected(self):
        # Loading would otherwise have to invent a critical point, and every reduced
        # property formed from it would be wrong without anything saying so.
        table = self.default_table()
        with self.fixture(table=table, species="argon"), self.assertRaises(KeyError) as caught:
            nist.load_species("argon")
        self.assertIn("critical constants", str(caught.exception))

    def test_an_edited_table_fails_its_digest_through_the_public_entry_point(self):
        # The digest guard reached the way a real edit would reach it, rather than by
        # calling the private hash helper with a deliberately wrong digest.
        with self.fixture(table=self.default_table()) as root:
            (root / "fixture.tsv").write_text(
                self.default_table().replace("0.71828180", "0.71828181"), encoding="utf-8"
            )
            with self.assertRaises(nist.ReferenceDataError) as caught:
                nist.load_species("methane")
        self.assertIn("does not match its manifest digest", str(caught.exception))

    def test_an_absent_manifest_raises_from_the_loader(self):
        import tempfile
        from unittest import mock

        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            with (
                mock.patch.object(nist, "REFERENCE_DIR", root),
                mock.patch.object(nist, "MANIFEST_PATH", root / "MANIFEST.json"),
            ):
                with self.assertRaises(nist.ReferenceDataError) as caught:
                    nist.load_species("methane")
                # ... while the availability probe reports absence rather than raising,
                # because a checkout without the extract is a legitimate state.
                self.assertFalse(nist.reference_data_available())
        self.assertIn("no manifest", str(caught.exception))

    def test_availability_reports_false_for_an_unreadable_or_incomplete_manifest(self):
        import tempfile
        from unittest import mock

        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            manifest = root / "MANIFEST.json"
            with (
                mock.patch.object(nist, "REFERENCE_DIR", root),
                mock.patch.object(nist, "MANIFEST_PATH", manifest),
            ):
                manifest.write_text("{not json", encoding="utf-8")
                self.assertFalse(nist.reference_data_available())
                manifest.write_text(json.dumps({"files": [{"path": "absent.tsv"}]}), encoding="utf-8")
                self.assertFalse(nist.reference_data_available())

    def test_require_reference_data_skips_instead_of_failing_when_the_extract_is_absent(self):
        # Absence must not be reported as a failure, or a filtered checkout would look
        # like a broken library. Verified by driving a throwaway test case through the
        # helper and reading the result, rather than by trusting the docstring.
        import tempfile
        from unittest import mock

        class Probe(unittest.TestCase):
            def runTest(self):  # noqa: N802 - unittest's own name for a bare case
                nist.require_reference_data(self)

        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            with (
                mock.patch.object(nist, "REFERENCE_DIR", root),
                mock.patch.object(nist, "MANIFEST_PATH", root / "MANIFEST.json"),
            ):
                result = Probe().run()
        self.assertEqual(len(result.skipped), 1)
        self.assertEqual(result.failures, [])
        self.assertEqual(result.errors, [])
        self.assertIn("fetch it with", result.skipped[0][1])


# ---------------------------------------------------------------------------
# Independent oracle: deviation factor against NIST
# ---------------------------------------------------------------------------


class DeviationFactorAgainstNistTests(unittest.TestCase):
    """Z from DAK against reference equations of state for three pure components.

    Tolerance argument, written before the comparison was run.

    Dranchuk & Abou-Kassem report 0.486 percent average absolute error against the 1500
    Standing-Katz chart points they fitted. That is the error of the *fit*, and it is
    the smaller of the two terms here. The larger term is the model itself: the
    Standing-Katz chart is two-parameter corresponding states, calibrated on light
    natural gas, and a pure component is not a natural gas. For a light hydrocarbon
    close to the chart's own fluid family the additional error is of order one to two
    percent; for a non-hydrocarbon with a different acentric factor it is larger; and
    near the critical point two-parameter corresponding states has no claim at all.

    The gates below follow that argument, per species, and the carbon-dioxide case is
    written as a documented expectation of failure rather than as a loosened global
    tolerance. Loosening one tolerance until every species passes would destroy exactly
    the information this comparison exists to produce.

    Demonstrated resolving power, and its limit. Perturbing DAK's A2 from -1.0700 to
    -1.7000 moves the methane mean error from 1.0 to 20.5 percent, so this comparison
    catches a gross transcription. That statement is executed, not asserted in prose:
    see test_the_methane_gate_rejects_a_gross_coefficient_error, which runs the
    perturbed correlation through the independent bisection and requires it to fail
    both halves of the methane gate.

    It does NOT catch a slip in the fourth significant figure of A1, A10 or A11: those
    move the methane mean by less than 0.05 percentage points, far inside the
    corresponding-states error the gate has to accommodate. A coefficient-level
    regression fixture would need the digitised Standing-Katz chart points DAK was
    fitted to, which this repository does not hold. What covers that case instead is
    test_module_solvers_match_an_independent_bisection_of_the_same_correlation, where
    the coefficients are retyped from the paper and compared at 1e-9 relative -- a
    fourth-figure slip fails it by four orders. Stated here so the gate is read as
    exactly as strong as it is, and no stronger.
    """

    def errors_for(self, name: str, *, predicate=None, method: str = "dak") -> ErrorStatistics:
        """Signed relative errors of a correlation against the reference states."""
        species = load_or_skip(self, name)
        pseudocriticals = true_criticals(species)
        errors = []
        with quiet_range_warnings():
            for state in species.states:
                t_pr, p_pr = species.reduced(state)
                if predicate is not None and not predicate(t_pr, p_pr):
                    continue
                reference = species.deviation_factor(state)
                correlated = gp.z_factor(
                    state.pressure_psia, state.temperature_degr, pseudocriticals, method=method
                )
                label = (
                    f"Tr={t_pr:.3f} pr={p_pr:.3f} ({state.temperature_degf:g} degF, "
                    f"{state.pressure_psia:g} psia, Z_ref={reference:.5f}, "
                    f"Z_{method}={correlated:.5f})"
                )
                errors.append(((correlated - reference) / reference, label))
        return summarise(errors)

    def test_methane_agrees_to_about_one_percent(self):
        stats = self.errors_for("methane")
        # Methane is the closest of the three to the chart's own fluid family: light,
        # small acentric factor, and every state well above the critical temperature
        # (Tr 1.63 to 2.27 over this extract). The fit error plus the corresponding-
        # states error should stay inside a couple of percent.
        self.assertLess(stats.mean_absolute, 0.02, stats.describe("methane"))
        self.assertLess(stats.max_absolute, 0.03, stats.describe("methane"))

    def test_the_error_ordering_follows_distance_from_the_charts_fluid_family(self):
        # The argued statement about nitrogen, and the only one this comparison can
        # make without inventing a number. Two-parameter corresponding states carries
        # no quantitative error bound for a fluid outside the family it was drawn for,
        # so the defensible claim is the ordering: methane, a light hydrocarbon the
        # chart was built from, must be the best; nitrogen, a non-hydrocarbon whose
        # extract also runs past the DAK reduced-temperature ceiling, must be worse;
        # carbon dioxide, strongly polarisable and sampled through its own critical
        # region, must be worse again. The ordering is scale-free and survives any
        # change of tolerance.
        methane = self.errors_for("methane")
        nitrogen = self.errors_for("nitrogen")
        carbon_dioxide = self.errors_for("carbon_dioxide")
        self.assertLess(
            methane.mean_absolute,
            nitrogen.mean_absolute,
            f"{methane.describe('methane')} vs {nitrogen.describe('nitrogen')}",
        )
        self.assertLess(
            nitrogen.mean_absolute,
            carbon_dioxide.mean_absolute,
            f"{nitrogen.describe('nitrogen')} vs {carbon_dioxide.describe('carbon_dioxide')}",
        )

    def test_nitrogen_regression_guard_not_a_correctness_gate(self):
        # Named for what it is. The previous gates here were 3 percent mean and
        # 4 percent max with only a qualitative justification -- "wider than methane's
        # is the honest expectation" -- which does not produce those two numbers and so
        # was calibrated to the answer whether or not it was meant to be.
        #
        # There is no published accuracy figure for DAK against pure nitrogen to anchor
        # a correctness gate to, so this test does not claim to be one. The reference
        # extract is digest-verified and the correlation is deterministic, so the only
        # thing that can move these numbers is a change in the code; that makes a tight
        # guard the useful form. The observed mean and maximum at the time of writing are
        # statistics of the withheld comparison and are not published with this release;
        # the gates below are unchanged. The correctness statements about nitrogen are the
        # ordering test above and the ideal-gas limit.
        stats = self.errors_for("nitrogen")
        self.assertLess(stats.mean_absolute, 0.020, stats.describe("nitrogen"))
        self.assertLess(stats.max_absolute, 0.028, stats.describe("nitrogen"))

    def test_carbon_dioxide_fails_near_its_critical_point_as_expected(self):
        near_critical = self.errors_for("carbon_dioxide", predicate=lambda t_pr, _p_pr: t_pr <= 1.05)
        # This is a documented expectation of failure. Every state in this extract sits
        # at Tr between 1.02 and 1.42 -- carbon dioxide's critical temperature is
        # 87.8 degF, inside the isotherm set -- and two-parameter corresponding states
        # cannot represent the near-critical region of a strongly polarisable molecule.
        # Asserting that the error IS large is what stops the expectation quietly
        # becoming untrue: if a future change made this pass at one percent, either the
        # correlation was replaced or the comparison stopped comparing.
        self.assertGreater(
            near_critical.max_absolute,
            0.10,
            "carbon dioxide near its critical point is expected to disagree strongly; "
            + near_critical.describe("CO2 Tr <= 1.05"),
        )
        # ... and bounded. The previous form of this bound was max|e| < 0.60, a round
        # number with no derivation, against a materially smaller observed
        # value that is not published with this release. What the sentence above
        # actually wants to say is that the correlation is wrong here and the SOLVER is
        # not, so that is what is now asserted, in terms that have a meaning
        # independent of the observed error: every returned Z lies inside the physical
        # band the Standing-Katz chart spans, and every returned Z is a true root of the
        # DAK residual, checked against the independent bisection.
        species = load_or_skip(self, "carbon_dioxide")
        pseudocriticals = true_criticals(species)
        with quiet_range_warnings():
            for state in species.states:
                t_pr, p_pr = species.reduced(state)
                with self.subTest(t_pr=round(t_pr, 3), p_pr=round(p_pr, 3)):
                    correlated = gp.z_factor(state.pressure_psia, state.temperature_degr, pseudocriticals)
                    self.assertGreater(correlated, 0.05)
                    self.assertLess(correlated, 3.5)
                    # Gate argued from the solvers' own settings: the module's bracket
                    # tolerance is 1e-12 on reduced density, and reduced density does
                    # not fall below about 0.02 anywhere in the DAK window, so the
                    # returned Z is determined to about 5e-11 relative. 1e-9 leaves an
                    # order of margin over that and is still tight enough that a
                    # spurious root would be an enormous failure.
                    self.assertAlmostEqual(correlated / dak_z_by_bisection(t_pr, p_pr), 1.0, delta=1.0e-9)

    def test_carbon_dioxide_recovers_at_low_reduced_pressure(self):
        # The failure is located, not global. Where the gas is close to ideal the same
        # correlation on the same species is accurate, which is the positive control
        # that the near-critical failure above is physics and not a broken entry path.
        stats = self.errors_for("carbon_dioxide", predicate=lambda _t_pr, p_pr: p_pr <= 0.5)
        self.assertLess(stats.mean_absolute, 0.02, stats.describe("CO2 pr <= 0.5"))

    def test_carbon_dioxide_is_materially_worse_than_methane(self):
        # A scale-free statement of the same expectation: whatever the absolute gates,
        # carbon dioxide must be substantially worse than methane over the same kind of
        # sweep. This survives a change of tolerance.
        methane = self.errors_for("methane")
        carbon_dioxide = self.errors_for("carbon_dioxide")
        self.assertGreater(
            carbon_dioxide.mean_absolute,
            2.0 * methane.mean_absolute,
            f"{carbon_dioxide.describe('carbon_dioxide')} vs {methane.describe('methane')}",
        )

    def test_the_methane_gate_rejects_a_gross_coefficient_error(self):
        # Coded positive control for the headline gate. This was previously stated only
        # in the class docstring, as a number measured once and written down; a positive
        # control that is not executed is an assertion about the past.
        #
        # The perturbation is DAK's A2, -1.0700 -> -1.7000, evaluated through the
        # independent bisection so that the module is not touched. If the gate has
        # resolving power, the perturbed correlation must fail both halves of
        # test_methane_agrees_to_about_one_percent.
        species = load_or_skip(self, "methane")
        perturbed = list(DAK_COEFFICIENTS)
        perturbed[1] = -1.7000
        errors = []
        for state in species.states:
            t_pr, p_pr = species.reduced(state)
            reference = species.deviation_factor(state)
            value = dak_z_by_bisection(t_pr, p_pr, tuple(perturbed))
            errors.append(((value - reference) / reference, f"Tr={t_pr:.3f} pr={p_pr:.3f}"))
        stats = summarise(errors)
        self.assertGreater(stats.mean_absolute, 0.02, stats.describe("A2 = -1.7000"))
        self.assertGreater(stats.max_absolute, 0.03, stats.describe("A2 = -1.7000"))
        # ... and the same machinery with the published coefficients passes, so the
        # failure above is the perturbation and not the comparison path.
        published = summarise(
            [
                (
                    (dak_z_by_bisection(*species.reduced(state)) - species.deviation_factor(state))
                    / species.deviation_factor(state),
                    "",
                )
                for state in species.states
            ]
        )
        self.assertLess(published.mean_absolute, 0.02, published.describe("published A"))

    def test_hall_yarborough_has_its_own_external_oracle(self):
        # Hall-Yarborough previously had no comparison to anything outside the library:
        # its only check was agreement with DAK, which is a check on two
        # implementations of one chart, not on either one's physics. The gate is argued
        # exactly as DAK's is -- Hall-Yarborough is a fit of comparable quality to the
        # same Standing-Katz chart, so against light methane well above its critical
        # temperature the corresponding-states error dominates and a couple of percent
        # is the expectation.
        stats = self.errors_for("methane", method="hall-yarborough")
        self.assertLess(stats.mean_absolute, 0.02, stats.describe("methane, Hall-Yarborough"))
        self.assertLess(stats.max_absolute, 0.03, stats.describe("methane, Hall-Yarborough"))

    def test_dpr_has_its_own_external_oracle(self):
        # Same argument, and the same gap it closes: DPR was previously compared only
        # against DAK, the correlation it shares its ancestry, structure and fitting
        # data with, which is the weakest possible check.
        stats = self.errors_for("methane", method="dpr")
        self.assertLess(stats.mean_absolute, 0.02, stats.describe("methane, DPR"))
        self.assertLess(stats.max_absolute, 0.03, stats.describe("methane, DPR"))

    def test_report_error_statistics(self):
        # Numbers, not just a pass. A tolerance that passes tells the reader nothing
        # about how much margin there was.
        nist.require_reference_data(self)
        lines = ["", "deviation factor against NIST reference equations of state:"]
        for method in ("dak", "hall-yarborough", "dpr"):
            for name in nist.SPECIES:
                lines.append("  " + self.errors_for(name, method=method).describe(f"{method:16s}{name}"))
        print("\n".join(lines))


# ---------------------------------------------------------------------------
# Property: cross-correlation agreement
# ---------------------------------------------------------------------------


def spread_over_band(
    t_range: tuple[float, float],
    p_range: tuple[float, float],
    *,
    t_step: float = 0.05,
    p_step: float = 0.2,
) -> dict[str, float]:
    """Largest absolute and relative Z differences between the three correlations.

    Returned keys are ``dak-hy``, ``dak-dpr`` and ``hy-dpr`` for the absolute spreads,
    the same names suffixed ``-rel`` for the relative ones, and ``count``.
    """
    worst = {key: 0.0 for key in ("dak-hy", "dak-dpr", "hy-dpr")}
    worst.update({f"{key}-rel": 0.0 for key in tuple(worst)})
    count = 0
    with quiet_range_warnings():
        t_pr = t_range[0]
        while t_pr <= t_range[1] + 1e-9:
            p_pr = p_range[0]
            while p_pr <= p_range[1] + 1e-9:
                dak = gp.z_factor_dak(t_pr, p_pr)
                hall_yarborough = gp.z_factor_hall_yarborough(t_pr, p_pr)
                dpr = gp.z_factor_dpr(t_pr, p_pr)
                pairs = {
                    "dak-hy": abs(dak - hall_yarborough),
                    "dak-dpr": abs(dak - dpr),
                    "hy-dpr": abs(hall_yarborough - dpr),
                }
                for key, value in pairs.items():
                    worst[key] = max(worst[key], value)
                    worst[f"{key}-rel"] = max(worst[f"{key}-rel"], value / dak)
                count += 1
                p_pr += p_step
            t_pr += t_step
    worst["count"] = float(count)
    return worst


class CrossCorrelationAgreementTests(unittest.TestCase):
    """Agreement between the three correlations, and the zones where it breaks.

    What this family of tests can and cannot show is worth being precise about. All
    three correlations are fits to the same Standing-Katz chart, so agreement is
    evidence that the *implementations* are faithful, not that the physics is right.
    The physics claim is made only by the NIST comparison above.

    Within that, the three are not equally informative about each other. DAK and DPR
    are the same group's successive fits, share the Benedict-Webb-Rubin structure and
    the 0.27 constant, and track each other more closely than either tracks
    Hall-Yarborough everywhere: by the measured bands in docs/evidence/zfactor.md the
    ratio runs from 1.7 times in the 5 to 15 reduced-pressure band up to 13 times in
    the near-critical band, and it is 2.4 times in the core engineering band. A
    DAK-versus-DPR test would not notice a coefficient transcribed wrongly in a term
    both share.

    What none of these comparisons can do is see a defect in the solver, because all
    three go through the same one. That is what
    test_module_solvers_match_an_independent_bisection_of_the_same_correlation is for.
    """

    def test_informative_pair_dak_versus_hall_yarborough_in_the_core_band(self):
        # Core engineering band: 1.2 <= Tpr <= 3.0, 0.2 <= Ppr <= 8, inside all three
        # published windows. Two independent fits to one chart should agree to roughly
        # the sum of their fitting errors; DAK reports 0.486 percent average absolute
        # error against the chart and Hall-Yarborough is of the same order, so a few
        # percent at the worst point is the expectation and three percent is the gate.
        # Observed: 0.0089 absolute, 1.61 percent relative.
        worst = spread_over_band((1.2, 3.0), (0.2, 8.0))
        self.assertGreater(worst["count"], 1000)
        self.assertLess(worst["dak-hy"], 0.02, f"DAK vs HY core-band spread {worst['dak-hy']:.4f}")
        self.assertLess(worst["dak-hy-rel"], 0.03)

    def test_weak_pair_dak_versus_dpr_in_the_core_band(self):
        # Named "weak" deliberately. Passing this proves very little: the two share
        # ancestry, structure and fitting data. It is kept because a gross error in one
        # of them would still show up, and because the comparison with the informative
        # pair below is what makes the point.
        #
        # Tolerance basis: docs/evidence/zfactor.md tabulates the measured agreement
        # bands on this same grid, and gives band C -- 1.2 <= Tpr <= 3.0,
        # 0.2 <= Ppr <= 8, n = 1480 -- as max |dZ| DAK-DPR 0.0037. The gate is that
        # published band figure with a 50 percent margin, which makes this a regression
        # guard against implementation drift with a citable reference point, rather than
        # the round 0.01 it replaced.
        worst = spread_over_band((1.2, 3.0), (0.2, 8.0))
        self.assertLess(worst["dak-dpr"], 0.0056, f"DAK vs DPR core-band spread {worst['dak-dpr']:.4f}")

    def test_module_solvers_match_an_independent_bisection_of_the_same_correlation(self):
        # The check that the agreement bands above cannot make: those compare three
        # correlations to each other, so a defect in the shared solver moves all three
        # together. This compares the module's safeguarded Newton against a plain
        # bisection of the same residual, with the eleven coefficients retyped in the
        # test, over the whole declared DAK window.
        #
        # Gate: the module declares a bracket tolerance of 1e-12 on reduced density, and
        # reduced density stays above about 0.02 across this window, so the returned Z
        # is pinned to roughly 5e-11 relative. 1e-9 is an order of margin over that,
        # decided from the solver's settings and not from the observed agreement.
        worst = 0.0
        worst_label = ""
        with quiet_range_warnings():
            t_pr = 1.0
            while t_pr <= 3.0001:
                p_pr = 0.2
                while p_pr <= 30.0001:
                    ratio = gp.z_factor_dak(t_pr, p_pr) / dak_z_by_bisection(t_pr, p_pr)
                    if abs(ratio - 1.0) > worst:
                        worst = abs(ratio - 1.0)
                        worst_label = f"Tpr={t_pr:.2f} Ppr={p_pr:.1f}"
                    p_pr += 0.5
                t_pr += 0.05
        self.assertLess(worst, 1.0e-9, f"worst disagreement {worst:.3e} at {worst_label}")

    def test_the_independent_bisection_would_notice_a_changed_coefficient(self):
        # Positive control for the cross-check above: it is only worth running if a
        # coefficient slip on either side would break it. A fourth-significant-figure
        # change to A1 -- far smaller than the gross A2 perturbation used against the
        # NIST gate -- moves Z by four orders more than the 1e-9 gate.
        perturbed = list(DAK_COEFFICIENTS)
        perturbed[0] = 0.3268
        ratio = dak_z_by_bisection(1.5, 8.0, tuple(perturbed)) / dak_z_by_bisection(1.5, 8.0)
        self.assertGreater(abs(ratio - 1.0), 1.0e-5)

    def test_shared_ancestry_shows_up_as_a_tighter_weak_pair_in_every_band(self):
        # The structural claim itself, asserted rather than asserted-about-in-prose:
        # in every band, the two correlations that share a lineage agree more closely
        # with each other than either does with the independent one. If this ever
        # inverted, the "DAK vs DPR is weak" reasoning above would need revisiting.
        bands = {
            "core 1.2-3.0 / 0.2-8": ((1.2, 3.0), (0.2, 8.0)),
            "high pressure 1.2-3.0 / 15-20": ((1.2, 3.0), (15.2, 20.0)),
            "near critical 1.05-1.15 / 0.2-5": ((1.05, 1.15), (0.2, 5.0)),
        }
        for label, (t_range, p_range) in bands.items():
            with self.subTest(band=label):
                worst = spread_over_band(t_range, p_range)
                self.assertLess(
                    worst["dak-dpr"],
                    worst["dak-hy"],
                    f"{label}: DAK-DPR {worst['dak-dpr']:.4f} should stay inside "
                    f"DAK-HY {worst['dak-hy']:.4f}",
                )

    def test_known_divergence_zone_below_reduced_temperature_of_one_point_two(self):
        # Hall & Yarborough smoothed an apparent discrepancy in the Standing-Katz chart
        # for 1.05 <= Tpr <= 1.15, so HY disagrees with DAK there BY DESIGN. This zone
        # is also below the reduced-temperature floor the module declares for HY. The
        # assertion is that the divergence is present and large: a consistency test that
        # flagged this as a defect would be wrong, and a test suite that never looked
        # would not know the zone exists.
        worst = spread_over_band((1.05, 1.15), (0.2, 5.0))
        self.assertGreater(
            worst["dak-hy-rel"],
            0.05,
            "the documented Hall-Yarborough smoothing zone should show a large "
            f"divergence, found {worst['dak-hy-rel']:.4f}",
        )
        # ... while the shared-ancestry pair barely notices it, which is precisely why
        # DAK-vs-DPR must not be used as the consistency check. Tolerance basis: this
        # is band A of the measured table in docs/evidence/zfactor.md -- 1.05 <= Tpr
        # <= 1.15, 0.2 <= Ppr <= 5, n = 75 -- whose published relative DAK-DPR spread is
        # 0.7 percent against a DAK-HY spread of 16.3 percent. The gate is that
        # published figure with a 40 percent margin.
        self.assertLess(worst["dak-dpr-rel"], 0.01)

    def test_known_divergence_zone_above_the_hall_yarborough_pressure_window(self):
        # Beyond Ppr = 20 Hall-Yarborough is extrapolating past the module's declared
        # window, and the spread grows by roughly a factor of six over the core band.
        # DPR stays glued to DAK out there, which is the false confidence the evidence
        # card warns about.
        #
        # Tolerance basis for the DAK-DPR half: this sweep spans bands E and F of the
        # measured table in docs/evidence/zfactor.md, whose published max |dZ| DAK-DPR
        # figures are 0.0084 and 0.0103. The gate is the larger of the two with a
        # 50 percent margin, replacing an unargued 0.02.
        worst = spread_over_band((1.2, 3.0), (20.2, 30.0), p_step=0.5)
        core = spread_over_band((1.2, 3.0), (0.2, 8.0))
        self.assertGreater(worst["dak-hy"], 3.0 * core["dak-hy"])
        self.assertLess(worst["dak-dpr"], 0.0155, f"DAK vs DPR spread {worst['dak-dpr']:.4f}")


# ---------------------------------------------------------------------------
# Property: analytic derivatives against central differences
# ---------------------------------------------------------------------------


def central_difference(function, x: float, step: float) -> float:
    """Central difference of a scalar function, the oracle for an analytic derivative."""
    return (function(x + step) - function(x - step)) / (2.0 * step)


class AnalyticDerivativeTests(unittest.TestCase):
    """dZ/d(rho_r) against a central difference of the same polynomial.

    These tests reach for module-private functions. That is deliberate: the analytic
    derivative is not part of the public surface, but it is the single expression whose
    silent corruption would not change any Z and would quietly wreck every
    compressibility. It has to be checked directly.

    The step is 1e-6 and the comparison is on an ABSOLUTE tolerance of 1e-6. Absolute
    rather than relative because dZ/d(rho_r) passes through zero -- near Tpr = 1.3,
    rho_r = 1.0 it is about 2.6e-4 -- where a relative comparison is meaningless. At
    h = 1e-6 the central difference carries a truncation error of order h^2 f'''/6 and
    a round-off of order eps|f|/h, both around 1e-9 here, so 1e-6 is three orders of
    margin over the oracle's own error and still far tighter than any plausible
    transcription slip.
    """

    def test_dak_derivative_matches_a_central_difference(self):
        for t_pr in (1.05, 1.3, 1.7, 1.8, 2.5, 3.0):
            for rho_r in (0.05, 0.1, 0.3, 0.5, 0.8, 1.0, 1.5, 1.6, 2.2):
                with self.subTest(t_pr=t_pr, rho_r=rho_r):
                    analytic = _dak_dz_drho(rho_r, t_pr)
                    numerical = central_difference(
                        lambda rho, t=t_pr: _dak_z_of_reduced_density(rho, t), rho_r, 1.0e-6
                    )
                    self.assertAlmostEqual(analytic, numerical, delta=1.0e-6)

    def test_dpr_derivative_matches_a_central_difference(self):
        for t_pr in (1.05, 1.3, 1.8, 2.5):
            for rho_r in (0.1, 0.5, 1.0, 1.6, 2.2):
                with self.subTest(t_pr=t_pr, rho_r=rho_r):
                    analytic = _dpr_dz_drho(rho_r, t_pr)
                    numerical = central_difference(
                        lambda rho, t=t_pr: _dpr_z_of_reduced_density(rho, t), rho_r, 1.0e-6
                    )
                    self.assertAlmostEqual(analytic, numerical, delta=1.0e-6)

    def test_the_check_has_resolving_power_away_from_unit_reduced_density(self):
        # A widely reproduced textbook form of this derivative carries rho_r^3 where
        # rho_r^2 belongs. The two forms are exactly equal at rho_r = 1, so a check
        # placed only there would pass while the expression was wrong. This test states
        # the discriminating points explicitly and shows that the wrong form would be
        # caught by the gate used above.
        t_pr = 1.3
        for rho_r in (0.5, 1.5, 2.0):
            with self.subTest(rho_r=rho_r):
                correct = _dak_dz_drho(rho_r, t_pr)
                wrong = self.textbook_variant(rho_r, t_pr)
                self.assertGreater(abs(correct - wrong), 1.0e-2)
        # ... and the coincidence at rho_r = 1 is real, which is why it is named here.
        self.assertAlmostEqual(_dak_dz_drho(1.0, t_pr), self.textbook_variant(1.0, t_pr), delta=1e-12)

    @staticmethod
    def textbook_variant(rho_r: float, t_pr: float) -> float:
        """Evaluate the published derivative carrying the ``rho_r**3`` transcription slip.

        Written out here rather than imported from anywhere: it exists only so the test
        above can demonstrate that the gate would catch it.
        """
        a10, a11 = 0.6134, 0.7210
        c1, c2, c3, _, _ = _dak_terms_for_test(t_pr)
        exponential = (
            2.0
            * (a10 / t_pr**3)
            * rho_r
            * math.exp(-a11 * rho_r**2)
            * ((1.0 + 2.0 * a11 * rho_r**3) - a11 * rho_r**2 * (1.0 + a11 * rho_r**2))
        )
        return c1 + 2.0 * c2 * rho_r - 5.0 * c3 * rho_r**4 + exponential


def _dak_terms_for_test(t_pr: float) -> tuple[float, float, float, float, float]:
    """Recompute the DAK temperature groups independently of the module under test."""
    a = DAK_COEFFICIENTS
    c1 = a[0] + a[1] / t_pr + a[2] / t_pr**3 + a[3] / t_pr**4 + a[4] / t_pr**5
    c2 = a[5] + a[6] / t_pr + a[7] / t_pr**2
    c3 = a[8] * (a[6] / t_pr + a[7] / t_pr**2)
    return c1, c2, c3, a[9] / t_pr**3, a[10]


# ---------------------------------------------------------------------------
# Compressibility
# ---------------------------------------------------------------------------


class CompressibilityTests(unittest.TestCase):
    """Isothermal gas compressibility from the analytic derivative.

    ``c_g = 1/p - (1/Z)(dZ/dp)_T`` is a definition, so the only thing that can be wrong
    in the production path is the chain rule that carries the derivative from reduced
    density to pressure through the implicit dependence rho = 0.27 Ppr/(Z Tpr). A
    central difference of the converged Z is the oracle for exactly that.
    """

    PSEUDOCRITICALS = PseudoCriticals(373.97, 670.91, "synthetic, for a reduced-property sweep")

    def finite_difference_compressibility(self, pressure_psia: float, temperature_degr: float) -> float:
        """``1/p - (1/Z) dZ/dp`` with dZ/dp from a relative-step central difference.

        The step is 1e-5 of the pressure. A relative step is necessary: an absolute
        step of a few psi is far too coarse at 200 psia and needlessly noisy at
        6000 psia. Test-only, per contract C6.
        """
        step = 1.0e-5 * pressure_psia
        with quiet_range_warnings():
            z_value = gp.z_factor(pressure_psia, temperature_degr, self.PSEUDOCRITICALS)
            derivative = central_difference(
                lambda p: gp.z_factor(p, temperature_degr, self.PSEUDOCRITICALS),
                pressure_psia,
                step,
            )
        return 1.0 / pressure_psia - derivative / z_value

    def test_analytic_matches_the_finite_difference_everywhere_in_the_window(self):
        # The two routes differ only by the finite-difference error, which at
        # h = 1e-5 p is around 1e-9 relative. A gate of 1e-6 relative is loose against
        # that and still tight enough that dropping any single term in the chain rule
        # fails by orders of magnitude -- see the positive control below.
        for p_pr in (0.5, 1.5, 3.0, 6.0, 12.0, 25.0):
            for t_pr in (1.2, 1.5, 2.0, 3.0):
                with self.subTest(t_pr=t_pr, p_pr=p_pr):
                    pressure = p_pr * self.PSEUDOCRITICALS.pressure_psia
                    temperature = t_pr * self.PSEUDOCRITICALS.temperature_degr
                    with quiet_range_warnings():
                        analytic = gp.gas_compressibility_per_psi(pressure, temperature, self.PSEUDOCRITICALS)
                    numerical = self.finite_difference_compressibility(pressure, temperature)
                    self.assertAlmostEqual(analytic / numerical, 1.0, delta=1.0e-6)

    def test_dpr_route_matches_its_own_finite_difference(self):
        for p_pr in (1.5, 6.0, 12.0):
            for t_pr in (1.2, 2.0):
                with self.subTest(t_pr=t_pr, p_pr=p_pr):
                    pressure = p_pr * self.PSEUDOCRITICALS.pressure_psia
                    temperature = t_pr * self.PSEUDOCRITICALS.temperature_degr
                    step = 1.0e-5 * pressure
                    with quiet_range_warnings():
                        analytic = gp.gas_compressibility_per_psi(
                            pressure, temperature, self.PSEUDOCRITICALS, method="dpr"
                        )
                        z_value = gp.z_factor(pressure, temperature, self.PSEUDOCRITICALS, method="dpr")
                        derivative = central_difference(
                            lambda p, t=temperature: gp.z_factor(p, t, self.PSEUDOCRITICALS, method="dpr"),
                            pressure,
                            step,
                        )
                    numerical = 1.0 / pressure - derivative / z_value
                    self.assertAlmostEqual(analytic / numerical, 1.0, delta=1.0e-6)

    def test_the_implicit_function_correction_is_what_the_gate_is_catching(self):
        # Positive control for the test above. The most common hand-rolled error is to
        # differentiate the polynomial and forget that rho_r itself depends on Z, that
        # is, to drop the (1 + (rho/Z) dZ/drho) denominator. Reproducing that error here
        # measures how far the 1e-6 gate is from the error it is meant to catch.
        #
        # The size of the omission is (rho/Z)(dZ/drho), which vanishes as the gas
        # approaches ideal and grows past 5 at high reduced pressure. So the honest
        # statement has two halves: near the ideal-gas corner the correction really is
        # negligible, and where it is not, the omission is catastrophic.
        worst = 0.0
        with quiet_range_warnings():
            for t_pr in (1.2, 1.5, 2.0, 3.0):
                for p_pr in (0.5, 1.5, 3.0, 6.0, 12.0, 25.0):
                    rho_r = gp.reduced_density_dak(t_pr, p_pr)
                    z_value = 0.27 * p_pr / (rho_r * t_pr)
                    derivative = _dak_dz_drho(rho_r, t_pr)
                    scale = 0.27 / (z_value**2 * t_pr)
                    correct = 1.0 / p_pr - scale * derivative / (1.0 + (rho_r / z_value) * derivative)
                    omitted = 1.0 / p_pr - scale * derivative
                    worst = max(worst, abs(omitted / correct - 1.0))
        self.assertGreater(
            worst,
            1.0,
            "omitting the implicit-function denominator should be a factor-of-two-scale "
            f"error somewhere in the window, found {worst:.4f}",
        )

    def test_ideal_gas_limit(self):
        # Closed form: Z = 1 and dZ/dp = 0 give c_g = 1/p exactly. Approached rather
        # than forced: as Ppr falls the correlation tends to the ideal gas, so the
        # product c_g p must tend to 1 and the approach must be monotone in |c_g p - 1|.
        for t_pr in (1.3, 1.5, 2.0, 3.0):
            temperature = t_pr * self.PSEUDOCRITICALS.temperature_degr
            previous = None
            for p_pr in (0.5, 0.2, 0.05, 0.01, 0.002):
                pressure = p_pr * self.PSEUDOCRITICALS.pressure_psia
                with quiet_range_warnings():
                    product = (
                        gp.gas_compressibility_per_psi(pressure, temperature, self.PSEUDOCRITICALS) * pressure
                    )
                if previous is not None:
                    self.assertLess(abs(product - 1.0), abs(previous - 1.0))
                previous = product
            self.assertAlmostEqual(previous, 1.0, delta=1.0e-3)

    def test_sign_of_the_derivative_term_flips_at_the_deviation_factor_minimum(self):
        # The structural test for the SIGN of the dZ/dp term, which no magnitude check
        # can make: c_g > 1/p wherever Z falls with pressure, c_g < 1/p wherever it
        # rises, with the crossover at the minimum of Z. An implementation with the sign
        # reversed would sit on the wrong side of 1/p everywhere.
        t_pr = 1.5
        temperature = t_pr * self.PSEUDOCRITICALS.temperature_degr
        grid = [0.2 + 0.2 * index for index in range(75)]
        with quiet_range_warnings():
            deviation_factors = [gp.z_factor_dak(t_pr, p_pr) for p_pr in grid]
            above_ideal = []
            for p_pr in grid:
                pressure = p_pr * self.PSEUDOCRITICALS.pressure_psia
                value = gp.gas_compressibility_per_psi(pressure, temperature, self.PSEUDOCRITICALS)
                above_ideal.append(value > 1.0 / pressure)
        minimum_index = deviation_factors.index(min(deviation_factors))
        # Below the minimum Z falls, so c_g must exceed 1/p; above it, the reverse.
        self.assertTrue(all(above_ideal[: minimum_index - 1]))
        self.assertFalse(any(above_ideal[minimum_index + 1 :]))

    def test_against_compressibility_differentiated_from_nist_methane_densities(self):
        # An oracle that never touches a deviation factor: c_g = (1/rho)(drho/dp)_T
        # differentiated straight from the reference densities.
        #
        # Error budget. DAK is about one percent low in Z against pure methane, and
        # compressibility involves the derivative of that error, so a couple of percent
        # is expected. The reference side carries its own truncation: a three-point
        # central difference on a 200 psia grid. Gate: 5 percent per point.
        species = load_or_skip(self, "methane")
        pseudocriticals = true_criticals(species)
        errors = []
        for temperature_degf in (100.0, 160.0, 200.0, 260.0, 320.0):
            isotherm = sorted(
                (state for state in species.states if state.temperature_degf == temperature_degf),
                key=lambda state: state.pressure_psia,
            )
            for index in range(1, len(isotherm) - 1):
                below, here, above = isotherm[index - 1], isotherm[index], isotherm[index + 1]
                step = here.pressure_psia - below.pressure_psia
                reference = (1.0 / here.density_lbm_per_cuft) * (
                    (above.density_lbm_per_cuft - below.density_lbm_per_cuft) / (2.0 * step)
                )
                with quiet_range_warnings():
                    correlated = gp.gas_compressibility_per_psi(
                        here.pressure_psia, here.temperature_degr, pseudocriticals
                    )
                errors.append(
                    (
                        (correlated - reference) / reference,
                        f"{temperature_degf:g} degF, {here.pressure_psia:g} psia",
                    )
                )
        stats = summarise(errors)
        self.assertLess(stats.max_absolute, 0.05, stats.describe("c_g vs NIST methane"))
        self.assertLess(stats.mean_absolute, 0.03, stats.describe("c_g vs NIST methane"))

    def test_the_nist_compressibility_check_can_tell_a_real_error_apart(self):
        # Positive control for the comparison above: at 1000 psia and 100 degF the
        # ideal-gas value 1/p misses the density-derived compressibility by about eight
        # percent, well outside the five percent gate, while the analytic route lands
        # inside one percent. The gate therefore has resolving power rather than being
        # wide enough to admit anything.
        species = load_or_skip(self, "methane")
        pseudocriticals = true_criticals(species)
        isotherm = sorted(
            (state for state in species.states if state.temperature_degf == 100.0),
            key=lambda state: state.pressure_psia,
        )
        index = next(i for i, state in enumerate(isotherm) if state.pressure_psia == 1000.0)
        below, here, above = isotherm[index - 1], isotherm[index], isotherm[index + 1]
        step = here.pressure_psia - below.pressure_psia
        reference = (1.0 / here.density_lbm_per_cuft) * (
            (above.density_lbm_per_cuft - below.density_lbm_per_cuft) / (2.0 * step)
        )
        with quiet_range_warnings():
            correlated = gp.gas_compressibility_per_psi(
                here.pressure_psia, here.temperature_degr, pseudocriticals
            )
        ideal = 1.0 / here.pressure_psia
        self.assertGreater(abs(ideal / reference - 1.0), 0.07)
        self.assertLess(abs(correlated / reference - 1.0), 0.02)

    def test_compressibility_falls_with_pressure_and_stays_positive(self):
        # Thermodynamic requirement: a single-phase fluid has positive isothermal
        # compressibility, and for a gas it falls monotonically over this range.
        temperature = 1.8 * self.PSEUDOCRITICALS.temperature_degr
        previous = math.inf
        for p_pr in (0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 25.0):
            with quiet_range_warnings():
                value = gp.gas_compressibility_per_psi(
                    p_pr * self.PSEUDOCRITICALS.pressure_psia, temperature, self.PSEUDOCRITICALS
                )
            self.assertGreater(value, 0.0)
            self.assertLess(value, previous)
            previous = value


# ---------------------------------------------------------------------------
# Viscosity
# ---------------------------------------------------------------------------


class ViscosityTests(unittest.TestCase):
    """Lee-Gonzalez-Eakin against the reference transport model for methane.

    This comparison runs only when the operator supplies the reference extract locally.
    The extract is not redistributed with this release, so in a public checkout every
    test in this class reports as skipped rather than passing vacuously, and the
    observed error statistics against it are not published here. See
    ``docs/release/PUBLIC_DATA_POLICY.md``.

    Tolerance argument. The authors report roughly two percent average absolute error
    at low pressure and four percent at high pressure for gases of gravity below one.
    A later large-database validation (Londono, Archer & Blasingame, SPE 75721) reports
    3.34 percent average absolute error over 4909 points. So: mean absolute error under
    five percent, and no single point worse than eight percent, which is about twice the
    authors' own high-pressure average -- the usual relationship between an average
    absolute error and the tail of the same distribution.

    The sharper assertion is the sign. Against pure methane the correlation is known to
    run high, so a consistently positive bias is a structural property that a
    coefficient or unit error would break even where it happened to preserve the
    magnitude.

    Demonstrated resolving power, and its limit. Transposing 9.379 to 9.739 pushes both
    the mean and the worst point well outside the gates below; transposing 209.2 to 290.2
    leaves the mean almost unchanged but flips the bias negative, which the sign
    assertion catches; a ten-fold slip on the M coefficient of K is caught by an
    enormous margin. What this comparison canNOT do is discriminate the X constant
    3.448 from the erroneous 3.488 that circulates in one secondary source: the two
    constants give mean errors that both sit inside the correlation's own quoted
    accuracy, and are separated by far less than it. That constant rests on the documentary evidence recorded in
    ``docs/evidence/viscosity.md``, not on this test, and it is worth saying plainly
    rather than implying the suite pins it.

    Margin, stated because it is the thinnest in the file. The eight percent per-point
    gate leaves less headroom over the observed worst point than any other comparison
    here; the observed figure itself is a statistic of the withheld comparison and is not
    published with this release. The gate is argued from the authors' own
    quoted accuracy rather than fitted to the observation, so it stays as it is, but a
    re-fetch of the reference extract at a different WebBook revision is the change
    most likely to move it.
    """

    def test_against_nist_methane_viscosity(self):
        species = load_or_skip(self, "methane")
        errors = []
        with quiet_range_warnings():
            for state in species.states:
                correlated = gp.gas_viscosity_lee_gonzalez_eakin(
                    state.temperature_degr,
                    species.molar_mass_lbm_per_lbmol,
                    state.density_lbm_per_cuft,
                )
                errors.append(
                    (
                        (correlated - state.viscosity_cp) / state.viscosity_cp,
                        f"{state.temperature_degf:g} degF, {state.pressure_psia:g} psia",
                    )
                )
        stats = summarise(errors)
        print("\nLee-Gonzalez-Eakin against NIST methane:\n  " + stats.describe("methane viscosity"))
        self.assertLess(stats.mean_absolute, 0.05, stats.describe("methane viscosity"))
        self.assertLess(stats.max_absolute, 0.08, stats.describe("methane viscosity"))
        self.assertGreater(
            stats.min_signed, 0.0, "the bias against pure methane should be positive everywhere"
        )

    def test_zero_density_limit_isolates_the_k_group(self):
        # Closed form: exp(X rho^Y) -> 1 as rho -> 0 for Y > 0, so mu -> 1e-4 K. This
        # is the only check that sees K without any contamination from X or Y, which is
        # what makes it able to localise a transposed digit in 9.379, 0.01607, 209.2 or
        # 19.26. Evaluated as a limit because the function requires a positive density.
        temperature_degr = 559.6704  # 100 degF
        molar_mass = 16.0425
        k = (
            (9.379 + 0.01607 * molar_mass)
            * temperature_degr**1.5
            / (209.2 + 19.26 * molar_mass + temperature_degr)
        )
        self.assertAlmostEqual(k, 118.3787, places=4)  # published intermediate value
        with quiet_range_warnings():
            near_zero = gp.gas_viscosity_lee_gonzalez_eakin(temperature_degr, molar_mass, 1.0e-9)
        self.assertAlmostEqual(near_zero, 1.0e-4 * k, places=12)

    def test_density_argument_is_field_units_not_cgs(self):
        # The correlation's own density variable is g/cm^3 and the public function takes
        # lbm/ft^3, converting internally. Feeding it a g/cm^3 number therefore
        # under-reads by the conversion factor rather than raising, so the test states
        # the relationship explicitly: the right call and the wrong call differ, and
        # the right one is the one that matches NIST.
        species = load_or_skip(self, "methane")
        state = next(s for s in species.states if s.temperature_degf == 100.0 and s.pressure_psia == 1000.0)
        with quiet_range_warnings():
            correct = gp.gas_viscosity_lee_gonzalez_eakin(
                state.temperature_degr, species.molar_mass_lbm_per_lbmol, state.density_lbm_per_cuft
            )
            mistaken = gp.gas_viscosity_lee_gonzalez_eakin(
                state.temperature_degr,
                species.molar_mass_lbm_per_lbmol,
                lbm_per_cuft_to_g_per_cc(state.density_lbm_per_cuft),
            )
        self.assertLess(abs(correct / state.viscosity_cp - 1.0), 0.08)
        self.assertGreater(abs(mistaken / state.viscosity_cp - 1.0), 0.05)

    def test_viscosity_rises_with_density_at_fixed_temperature(self):
        # Structural: the correlation is K exp(X rho^Y) with X and Y positive over any
        # realistic (M, T), so it must increase with density. A sign slip in X would
        # invert this while leaving the magnitude at one point plausible.
        temperature_degr = fahrenheit_to_rankine(200.0)
        previous = 0.0
        for density in (0.5, 1.0, 2.0, 5.0, 10.0, 15.0):
            value = gp.gas_viscosity_lee_gonzalez_eakin(temperature_degr, 16.0425, density)
            self.assertGreater(value, previous)
            previous = value


# ---------------------------------------------------------------------------
# Pseudocriticals: Wichert-Aziz and the Standing variants
# ---------------------------------------------------------------------------


class WichertAzizTests(unittest.TestCase):
    """The sour-gas pseudocritical correction, including the transcription trap.

    The published form is::

        eps  = 120 (A^0.9 - A^1.6) + 15 (B^0.5 - B^4),  A = yCO2 + yH2S, B = yH2S
        Tpc' = Tpc - eps
        Ppc' = Ppc (Tpc - eps) / (Tpc + B (1 - B) eps)

    The denominator carries the UNCORRECTED Tpc. Using the corrected value there is the
    classic implementation error and it moves Ppc' in the wrong direction by tens of
    psia, so it is tested against a published worked example that can tell the two
    apart.
    """

    #: Ahmed, Reservoir Engineering Handbook, worked example: gamma = 0.7 dry gas with
    #: 5 mol% CO2 and 10 mol% H2S. The book prints eps = 20.735 degR, T'pc = 368.64 degR
    #: and p'pc = 630.44 psia.
    GRAVITY = 0.7
    Y_CO2 = 0.05
    Y_H2S = 0.10
    PUBLISHED_EPSILON = 20.735
    PUBLISHED_CORRECTED_TEMPERATURE = 368.64
    PUBLISHED_CORRECTED_PRESSURE = 630.44

    def base(self) -> PseudoCriticals:
        # The published example uses the Standing dry-gas form with the 677 constant,
        # which is the module's default variant; the example's own printed pseudo-
        # criticals (389.38 degR, 669.1 psia) confirm which constant it used.
        return gp.pseudocritical_standing(self.GRAVITY, variant="ahmed")

    def test_reproduces_the_published_worked_example(self):
        base = self.base()
        self.assertAlmostEqual(base.temperature_degr, 389.38, delta=0.01)
        self.assertAlmostEqual(base.pressure_psia, 669.1, delta=0.05)
        corrected = gp.wichert_aziz_correction(base, y_h2s=self.Y_H2S, y_co2=self.Y_CO2)
        epsilon = base.temperature_degr - corrected.temperature_degr
        self.assertAlmostEqual(epsilon, self.PUBLISHED_EPSILON, delta=0.001)
        self.assertAlmostEqual(corrected.temperature_degr, self.PUBLISHED_CORRECTED_TEMPERATURE, delta=0.01)
        self.assertAlmostEqual(corrected.pressure_psia, self.PUBLISHED_CORRECTED_PRESSURE, delta=0.05)

    def test_denominator_uses_the_uncorrected_pseudocritical_temperature(self):
        # The discriminating test. With the published inputs the correct denominator
        # gives 630.44 psia and the transcription error gives about 665.7 psia -- a
        # 35 psia gap, far outside any tolerance. Constructed so that it would fail if
        # the corrected temperature were used in the denominator.
        base = self.base()
        corrected = gp.wichert_aziz_correction(base, y_h2s=self.Y_H2S, y_co2=self.Y_CO2)
        epsilon = base.temperature_degr - corrected.temperature_degr
        if_corrected_were_used = (
            base.pressure_psia
            * corrected.temperature_degr
            / (corrected.temperature_degr + self.Y_H2S * (1.0 - self.Y_H2S) * epsilon)
        )
        self.assertGreater(abs(if_corrected_were_used - corrected.pressure_psia), 30.0)
        self.assertAlmostEqual(corrected.pressure_psia, self.PUBLISHED_CORRECTED_PRESSURE, delta=0.05)

    def test_epsilon_matches_the_closed_form_in_isolation(self):
        # Nothing here touches a solver or a Z coefficient: it checks the six constants
        # of epsilon against a published arithmetic result. A failure points straight at
        # a constant or at a mole-percent-for-mole-fraction mix-up.
        base = PseudoCriticals(400.0, 650.0, "synthetic")
        for y_co2, y_h2s in ((0.05, 0.10), (0.10, 0.05), (0.0, 0.20), (0.30, 0.0)):
            with self.subTest(y_co2=y_co2, y_h2s=y_h2s):
                a = y_co2 + y_h2s
                expected = 120.0 * (a**0.9 - a**1.6) + 15.0 * (y_h2s**0.5 - y_h2s**4)
                corrected = gp.wichert_aziz_correction(base, y_h2s=y_h2s, y_co2=y_co2)
                self.assertAlmostEqual(
                    base.temperature_degr - corrected.temperature_degr, expected, places=10
                )

    def test_zero_acid_gas_returns_the_input_unchanged(self):
        base = gp.pseudocritical_sutton(0.75)
        unchanged = gp.wichert_aziz_correction(base, y_h2s=0.0, y_co2=0.0)
        self.assertIs(unchanged, base)
        self.assertEqual(unchanged.corrections, ())

    def test_correction_always_lowers_the_pseudocritical_temperature(self):
        base = PseudoCriticals(400.0, 650.0, "synthetic")
        for y_co2, y_h2s in ((0.01, 0.0), (0.0, 0.01), (0.10, 0.05), (0.30, 0.20), (0.55, 0.0)):
            with self.subTest(y_co2=y_co2, y_h2s=y_h2s):
                corrected = gp.wichert_aziz_correction(base, y_h2s=y_h2s, y_co2=y_co2)
                self.assertLess(corrected.temperature_degr, base.temperature_degr)
                self.assertLess(corrected.pressure_psia, base.pressure_psia)
                self.assertEqual(corrected.corrections, ("wichert-aziz-1972",))

    def test_carbon_dioxide_alone_still_corrects(self):
        # The correction is not H2S-only: with B = 0 the first bracket survives. Code
        # that short-circuits on zero H2S produces a silently uncorrected sour gas.
        base = PseudoCriticals(400.0, 650.0, "synthetic")
        corrected = gp.wichert_aziz_correction(base, y_h2s=0.0, y_co2=0.20)
        self.assertLess(corrected.temperature_degr, base.temperature_degr - 10.0)


class StandingVariantTests(unittest.TestCase):
    """Both reported constant terms of the Standing dry-gas pressure correlation.

    Two values circulate for the constant term, 667 and 677, and the original was not
    consulted for this repository. The module exposes both and records which one it
    used. These tests pin the arithmetic of each and bound what the disagreement can do
    to a deviation factor, so that a study can state the consequence rather than the
    concern.
    """

    def test_both_variants_carry_the_constant_their_source_prints(self):
        # A transcription check, not an arithmetic one. Asserting that the two variants
        # differ by exactly 10 psia -- which is what this test used to do -- is true by
        # construction of STANDING_DRY_GAS_PRESSURE_CONSTANTS and would stay true if
        # both constants were wrong. What can actually fail is the pair of literals, so
        # those are what is pinned: 677 as printed in Ahmed's Reservoir Engineering
        # Handbook and 667 as printed in Whitson & Brule.
        self.assertEqual(gp.STANDING_DRY_GAS_PRESSURE_CONSTANTS, {"ahmed": 677.0, "whitson-brule": 667.0})
        for gamma in (0.55, 0.65, 0.75, 0.9, 1.05):
            with self.subTest(specific_gravity=gamma):
                ahmed = gp.pseudocritical_standing(gamma, variant="ahmed")
                whitson = gp.pseudocritical_standing(gamma, variant="whitson-brule")
                # The two sources differ only in the pressure constant, so the
                # temperature correlation must be untouched by the choice.
                self.assertEqual(ahmed.temperature_degr, whitson.temperature_degr)
                self.assertIn("ahmed", ahmed.correlation)
                self.assertIn("whitson-brule", whitson.correlation)

    def test_both_variants_match_their_own_closed_form(self):
        for gamma in (0.6, 0.8, 1.0):
            for variant, constant in gp.STANDING_DRY_GAS_PRESSURE_CONSTANTS.items():
                with self.subTest(specific_gravity=gamma, variant=variant):
                    result = gp.pseudocritical_standing(gamma, variant=variant)
                    self.assertAlmostEqual(
                        result.temperature_degr, 168.0 + 325.0 * gamma - 12.5 * gamma**2, places=10
                    )
                    self.assertAlmostEqual(
                        result.pressure_psia, constant + 15.0 * gamma - 37.5 * gamma**2, places=10
                    )

    def test_the_variant_choice_moves_z_by_a_bounded_amount(self):
        # 10 psia on roughly 665 psia is a 1.5 percent shift in Ppc and therefore a
        # 1.5 percent shift in Ppr. Over the window swept here Z changes by less than
        # about 2 per unit of ln Ppr, so the induced change in Z is bounded by a few
        # hundredths. Gate: 0.03 absolute and 2 percent relative, with the difference
        # required to be non-zero -- the two variants are genuinely different and a
        # test that let them collapse would hide the disagreement rather than bound it.
        largest = 0.0
        largest_relative = 0.0
        any_difference = False
        with quiet_range_warnings():
            for gamma in (0.55, 0.65, 0.75, 0.9, 1.0):
                ahmed = gp.pseudocritical_standing(gamma, variant="ahmed")
                whitson = gp.pseudocritical_standing(gamma, variant="whitson-brule")
                for temperature_degr in (560.0, 620.0, 700.0, 760.0):
                    for pressure_psia in (200.0, 1000.0, 3000.0, 5000.0, 8000.0, 12000.0):
                        first = gp.z_factor(pressure_psia, temperature_degr, ahmed)
                        second = gp.z_factor(pressure_psia, temperature_degr, whitson)
                        largest = max(largest, abs(first - second))
                        largest_relative = max(largest_relative, abs(first - second) / first)
                        any_difference = any_difference or first != second
        self.assertTrue(any_difference)
        self.assertLess(largest, 0.03, f"largest |dZ| between Standing variants was {largest:.5f}")
        self.assertLess(largest_relative, 0.02)

    def test_wet_gas_form_is_a_different_correlation(self):
        # The dry-gas and wet-gas fits are not interchangeable, and the split at
        # gamma = 0.75 is part of the correlation rather than a convenience.
        dry = gp.pseudocritical_standing(0.8, fluid="dry_gas")
        wet = gp.pseudocritical_standing(0.8, fluid="wet_gas")
        self.assertGreater(abs(dry.temperature_degr - wet.temperature_degr), 5.0)
        self.assertAlmostEqual(wet.temperature_degr, 187.0 + 330.0 * 0.8 - 71.5 * 0.64, places=10)
        self.assertAlmostEqual(wet.pressure_psia, 706.0 - 51.7 * 0.8 - 11.1 * 0.64, places=10)

    def test_dpr_coefficients_match_the_published_set_where_the_sources_agree(self):
        # Nothing in this file pinned any DPR coefficient, so either reading of the
        # disputed one would have passed unnoticed. This pins all eight, and is
        # deliberately agnostic about the eighth decimal place of A3.
        #
        # docs/evidence/zfactor.md records the disagreement: the CRAN zFactor package
        # and Ahmed's Reservoir Engineering Handbook both print -0.57832720 while
        # predico prints -0.57832729, and the card's own adversarial review concluded
        # the majority reading should be the default. The module ships ...29. The
        # numerical consequence is below 1e-8 in Z, so this test does not take a side:
        # A3 is compared with a tolerance of 1e-7, which is larger than the 9e-8 the two
        # readings differ by and smaller than any digit above the dispute, and the other
        # seven are pinned exactly.
        published = (
            0.31506237,
            -1.04670990,
            -0.57832720,
            0.53530771,
            -0.61232032,
            -0.10488813,
            0.68157001,
            0.68446549,
        )
        module = gp._DPR
        self.assertEqual(len(module), len(published))
        for index, (mine, theirs) in enumerate(zip(module, published, strict=True), start=1):
            with self.subTest(coefficient=f"A{index}"):
                delta = 1.0e-7 if index == 3 else 5.0e-11
                self.assertAlmostEqual(mine, theirs, delta=delta)

    def test_sutton_matches_its_closed_form(self):
        for gamma in (0.6, 0.9, 1.4):
            with self.subTest(specific_gravity=gamma):
                result = gp.pseudocritical_sutton(gamma)
                self.assertAlmostEqual(
                    result.temperature_degr, 169.2 + 349.5 * gamma - 74.0 * gamma**2, places=10
                )
                self.assertAlmostEqual(
                    result.pressure_psia, 756.8 - 131.0 * gamma - 3.6 * gamma**2, places=10
                )


# ---------------------------------------------------------------------------
# Range windows
# ---------------------------------------------------------------------------


class RangeWindowTests(unittest.TestCase):
    """Contract C2: outside a published window the default warns and strict raises."""

    def assert_warns_and_strict_raises(self, call, **kwargs):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            call(**kwargs)
        categories = [item.category for item in caught]
        self.assertIn(RangeWarning, categories, f"{call.__name__} did not warn outside its window")
        with self.assertRaises(OutOfRangeWarningError):
            call(**kwargs, strict_range=True)

    def test_dak_reduced_temperature_below_the_window(self):
        self.assert_warns_and_strict_raises(gp.z_factor_dak, t_pr=0.95, p_pr=0.5)

    def test_dak_reduced_pressure_above_the_window(self):
        self.assert_warns_and_strict_raises(gp.z_factor_dak, t_pr=1.5, p_pr=35.0)

    def test_hall_yarborough_warns_outside_every_cited_reading_of_its_window(self):
        # The probe points are outside every reading of the Hall-Yarborough window that
        # docs/evidence/zfactor.md actually cites, and outside the module constant as
        # well. That is deliberate, and it is a change from what this test used to do.
        #
        # The module declares t_pr (1.2, 3.0) and p_pr (0.2, 20.0) and its error message
        # calls that "the published validity range". No source in the evidence card
        # supports 1.2 or 20: the two cited readings are Whitson & Brule, "valid for
        # 1 <= Tr <= 3 and 0.2 <= pr <= 25 to 30", and nafta.wiki, 1.05 <= Tpr <= 3 and
        # 0.2 <= Ppr <= 15. The earlier version of this test asserted a warning at
        # Tpr = 1.1, a point both cited sources call valid, and asserted that the DAK
        # floor lies below the Hall-Yarborough floor -- that is, it locked in the
        # unsourced narrowing as though it were the published one. Correcting the
        # constant and its message belongs in src/reservoir_lab/gas_properties.py; it is
        # recorded as a known problem rather than fixed here. What this test can
        # honestly assert is that the guard fires where every cited source agrees the
        # correlation is being extrapolated.
        self.assert_warns_and_strict_raises(gp.z_factor_hall_yarborough, t_pr=0.95, p_pr=3.0)
        self.assert_warns_and_strict_raises(gp.z_factor_hall_yarborough, t_pr=1.5, p_pr=32.0)

    def test_dpr_outside_its_window(self):
        # 1.01 is below the 1.05 floor the evidence card records for
        # Dranchuk-Purvis-Robinson, which is the module's declared floor as well.
        self.assert_warns_and_strict_raises(gp.z_factor_dpr, t_pr=1.01, p_pr=3.0)

    def test_standing_and_sutton_gravity_windows(self):
        # 1.5 is above every cited reading of the Standing gravity range, and 0.5 is
        # below Sutton's cited 0.57 floor, so neither probe depends on the exact
        # module constant. Standing's declared (0.55, 1.10) is itself unsourced in the
        # evidence card, and its documented dry/wet split at gamma = 0.75 is not
        # encoded at all; both are recorded as known problems against the source
        # module rather than pinned here.
        self.assert_warns_and_strict_raises(gp.pseudocritical_standing, specific_gravity=1.5)
        self.assert_warns_and_strict_raises(gp.pseudocritical_sutton, specific_gravity=0.5)

    def test_wichert_aziz_exposes_a_composition_window(self):
        # Known contract violation, recorded as an expected failure because the fix is
        # in src/reservoir_lab/gas_properties.py and not in this file.
        #
        # Contract C2: "Every function that wraps a correlation exposes a
        # strict_range: bool = False keyword." wichert_aziz_correction wraps Wichert &
        # Aziz (1972), whose composition window docs/evidence/zfactor.md records as CO2
        # 0-55 mol% and H2S 0-74 mol%, and it has neither the keyword nor any
        # check_range call: 80 percent CO2 and 90 percent H2S are accepted in silence.
        # Adding the window makes this pass, which fails the suite as an unexpected
        # success and forces the expectation to be removed deliberately.
        base = PseudoCriticals(400.0, 650.0, "synthetic")
        self.assert_warns_and_strict_raises(
            gp.wichert_aziz_correction, pseudocriticals=base, y_h2s=0.0, y_co2=0.80
        )

    def test_lee_gonzalez_eakin_temperature_window(self):
        # 50 degF is below the 100 degF floor of the correlation's fitted window.
        self.assert_warns_and_strict_raises(
            gp.gas_viscosity_lee_gonzalez_eakin,
            temperature_degr=fahrenheit_to_rankine(50.0),
            molar_mass=16.0425,
            density_lbm_per_cuft=1.0,
        )

    def test_inside_the_window_nothing_warns(self):
        # The other half of the contract. A guard that warned on valid input would
        # train the reader to ignore it.
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            gp.z_factor_dak(1.5, 3.0)
            gp.z_factor_hall_yarborough(1.5, 3.0)
            gp.z_factor_dpr(1.5, 3.0)
            gp.pseudocritical_standing(0.7)
            gp.pseudocritical_sutton(0.7)
            gp.gas_viscosity_lee_gonzalez_eakin(fahrenheit_to_rankine(180.0), 18.0, 5.0)
        self.assertEqual([item for item in caught if item.category is RangeWarning], [])

    def test_declared_windows_admit_the_states_the_suite_exercises(self):
        # A range guard is only useful if it agrees with the data the library is used
        # on. Methane over this extract sits at Tr 1.63 to 2.27 and pr up to 9, all
        # inside the DAK window, so the NIST comparison is not quietly extrapolating.
        species = load_or_skip(self, "methane")
        for state in species.states:
            t_pr, p_pr = species.reduced(state)
            self.assertGreaterEqual(t_pr, gp.DAK_RANGE["t_pr"][0])
            self.assertLessEqual(t_pr, gp.DAK_RANGE["t_pr"][1])
            self.assertGreaterEqual(p_pr, gp.DAK_RANGE["p_pr"][0])
            self.assertLessEqual(p_pr, gp.DAK_RANGE["p_pr"][1])


# ---------------------------------------------------------------------------
# Convergence
# ---------------------------------------------------------------------------


class ConvergenceBehaviourTests(unittest.TestCase):
    """Contract C3: an exhausted iteration budget raises and carries its diagnostics."""

    def test_dak_raises_rather_than_returning_the_last_iterate(self):
        with self.assertRaises(ConvergenceError) as caught:
            gp.z_factor_dak(1.5, 3.0, max_iterations=1)
        error = caught.exception
        self.assertEqual(error.iterations, 1)
        self.assertIsNotNone(error.last_value)
        self.assertIsNotNone(error.last_residual)
        self.assertIn("did not converge", str(error))

    def test_hall_yarborough_raises_on_an_exhausted_budget(self):
        with self.assertRaises(ConvergenceError):
            gp.z_factor_hall_yarborough(1.5, 3.0, max_iterations=2)

    def test_dpr_raises_on_an_exhausted_budget(self):
        with self.assertRaises(ConvergenceError):
            gp.z_factor_dpr(1.5, 3.0, max_iterations=1)

    def test_a_tighter_budget_never_returns_a_different_answer(self):
        # The failure mode this guards against is a solver that quietly returns its last
        # iterate when the budget runs out: that would produce a slightly different
        # number instead of an exception. Either the value is converged or there is no
        # value at all.
        reference = gp.z_factor_dak(1.5, 3.0)
        for budget in range(1, 12):
            try:
                value = gp.z_factor_dak(1.5, 3.0, max_iterations=budget)
            except ConvergenceError:
                continue
            self.assertAlmostEqual(value, reference, places=10)

    def test_the_default_budget_converges_across_the_declared_window(self):
        # Property test over the declared window rather than at a few comfortable
        # points, because the reason to bracket a solver is the corner it fails in.
        with quiet_range_warnings():
            t_pr = 1.0
            while t_pr <= 3.0001:
                p_pr = 0.2
                while p_pr <= 30.0001:
                    with self.subTest(t_pr=round(t_pr, 2), p_pr=round(p_pr, 1)):
                        z_value = gp.z_factor_dak(t_pr, p_pr)
                        self.assertGreater(z_value, 0.0)
                        self.assertLess(z_value, 3.5)
                    p_pr += 2.0
                t_pr += 0.25

    def test_the_default_budget_has_measured_headroom(self):
        # How much margin the default budget actually has, at the slowest point found
        # on the grid above. The bracketed solver declares convergence when the BRACKET
        # closes, not when the Newton iterate stops moving, so the iteration count is
        # materially higher than a textbook Newton count would suggest.
        slowest = 0
        for t_pr, p_pr in ((1.5, 0.2), (1.0, 0.2), (2.0, 1.2), (3.0, 30.0)):
            needed = None
            for budget in range(1, 101):
                try:
                    with quiet_range_warnings():
                        gp.z_factor_dak(t_pr, p_pr, max_iterations=budget)
                except ConvergenceError:
                    continue
                needed = budget
                break
            self.assertIsNotNone(needed, f"no convergence within 100 iterations at Tpr={t_pr}, Ppr={p_pr}")
            slowest = max(slowest, needed)
        self.assertLess(slowest, 100, f"slowest observed convergence took {slowest} iterations")
        print(f"\nslowest DAK convergence over the sampled corners: {slowest} iterations of a budget of 100")


# ---------------------------------------------------------------------------
# Invalid input
# ---------------------------------------------------------------------------


class InvalidInputTests(unittest.TestCase):
    """Contract C7 category three: every documented raise is exercised."""

    NON_POSITIVE = (0.0, -1.0, float("nan"), float("inf"), "not a number")

    def test_pseudocritical_correlations_reject_a_non_positive_gravity(self):
        for bad in self.NON_POSITIVE:
            with self.subTest(specific_gravity=bad):
                with self.assertRaises(InvalidInputError):
                    gp.pseudocritical_standing(bad)
                with self.assertRaises(InvalidInputError):
                    gp.pseudocritical_sutton(bad)

    def test_standing_rejects_an_unknown_fluid_or_variant(self):
        with self.assertRaises(InvalidInputError):
            gp.pseudocritical_standing(0.7, fluid="condensate")
        with self.assertRaises(InvalidInputError):
            gp.pseudocritical_standing(0.7, variant="ahmed-1989")

    def test_pseudocriticals_reject_non_positive_fields(self):
        with self.assertRaises(InvalidInputError):
            PseudoCriticals(-1.0, 650.0, "synthetic")
        with self.assertRaises(InvalidInputError):
            PseudoCriticals(400.0, 0.0, "synthetic")

    def test_reduced_rejects_non_positive_states(self):
        base = PseudoCriticals(400.0, 650.0, "synthetic")
        with self.assertRaises(InvalidInputError):
            base.reduced(0.0, 600.0)
        with self.assertRaises(InvalidInputError):
            base.reduced(1000.0, -10.0)

    def test_wichert_aziz_rejects_impossible_compositions(self):
        base = PseudoCriticals(400.0, 650.0, "synthetic")
        for y_h2s, y_co2 in ((-0.01, 0.0), (0.0, -0.01), (1.5, 0.0), (0.0, 1.5)):
            with self.subTest(y_h2s=y_h2s, y_co2=y_co2), self.assertRaises(InvalidInputError):
                gp.wichert_aziz_correction(base, y_h2s=y_h2s, y_co2=y_co2)
        # Mole fractions that individually pass but sum above one: the shape a
        # mole-percent-for-fraction mistake takes.
        with self.assertRaises(InvalidInputError):
            gp.wichert_aziz_correction(base, y_h2s=0.6, y_co2=0.6)

    def test_wichert_aziz_rejects_a_correction_that_would_invert_the_temperature(self):
        # A pseudocritical temperature small enough that the correction would drive it
        # to or below absolute zero. Returning a negative Tpc would produce a negative
        # Tpr and a confidently wrong Z.
        tiny = PseudoCriticals(10.0, 650.0, "synthetic")
        with self.assertRaises(InvalidInputError):
            gp.wichert_aziz_correction(tiny, y_h2s=0.5, y_co2=0.4)

    def test_z_factor_solvers_reject_non_positive_reduced_properties(self):
        solvers = (
            gp.z_factor_dak,
            gp.z_factor_hall_yarborough,
            gp.z_factor_dpr,
            gp.reduced_density_dak,
        )
        for solver in solvers:
            for bad in self.NON_POSITIVE:
                with self.subTest(solver=solver.__name__, value=bad):
                    with self.assertRaises(InvalidInputError):
                        solver(bad, 3.0)
                    with self.assertRaises(InvalidInputError):
                        solver(1.5, bad)

    def test_z_factor_rejects_an_unknown_method(self):
        base = PseudoCriticals(400.0, 650.0, "synthetic")
        with self.assertRaises(InvalidInputError):
            gp.z_factor(2000.0, 600.0, base, method="brill-beggs")

    def test_compressibility_refuses_a_method_it_has_no_derivative_for(self):
        # Hall-Yarborough solves for a different reduced variable, so the
        # Mattar-Brar-Aziz chain rule does not apply to it. Refusing is the contract;
        # silently substituting DAK would be the defect.
        base = PseudoCriticals(400.0, 650.0, "synthetic")
        with self.assertRaises(InvalidInputError) as caught:
            gp.gas_compressibility_per_psi(2000.0, 600.0, base, method="hall-yarborough")
        self.assertIn("hall-yarborough", str(caught.exception).lower())

    def test_density_rejects_non_positive_arguments(self):
        for bad in self.NON_POSITIVE:
            with self.subTest(value=bad):
                with self.assertRaises(InvalidInputError):
                    gp.gas_density_lbm_per_cuft(bad, 600.0, 0.9, 18.0)
                with self.assertRaises(InvalidInputError):
                    gp.gas_density_lbm_per_cuft(2000.0, bad, 0.9, 18.0)
                with self.assertRaises(InvalidInputError):
                    gp.gas_density_lbm_per_cuft(2000.0, 600.0, bad, 18.0)
                with self.assertRaises(InvalidInputError):
                    gp.gas_density_lbm_per_cuft(2000.0, 600.0, 0.9, bad)

    def test_viscosity_rejects_non_positive_arguments(self):
        for bad in self.NON_POSITIVE:
            with self.subTest(value=bad):
                with self.assertRaises(InvalidInputError):
                    gp.gas_viscosity_lee_gonzalez_eakin(bad, 18.0, 5.0)
                with self.assertRaises(InvalidInputError):
                    gp.gas_viscosity_lee_gonzalez_eakin(620.0, bad, 5.0)
                with self.assertRaises(InvalidInputError):
                    gp.gas_viscosity_lee_gonzalez_eakin(620.0, 18.0, bad)

    def test_extreme_but_finite_arguments_raise_invalid_input(self):
        # Known contract violation, recorded as an expected failure because the fix is
        # in src/reservoir_lab/gas_properties.py and not in this file. NON_POSITIVE
        # above covers zero, negative, nan, inf and a string; it does not cover finite
        # magnitudes far outside any physical domain, and those behave differently.
        #
        # Contract C3: a malformed, non-finite or physically impossible argument raises
        # InvalidInputError, and a function never returns a sentinel to signal failure.
        # Measured behaviour instead: z_factor_dak(1e-300, 1.0) raises
        # ZeroDivisionError, because t_pr**5 underflows; the Lee-Gonzalez-Eakin
        # exponential raises OverflowError; and Hall-Yarborough returns 0.0 and
        # 3.6e10 as values where DAK and DPR raise ConvergenceError on the same input.
        # A returned deviation factor of 3.6e10 is the sentinel problem in its worst
        # form: it is not flagged at all.
        with quiet_range_warnings():
            with self.assertRaises(InvalidInputError):
                gp.z_factor_dak(1.0e-300, 1.0)
            with self.assertRaises(InvalidInputError):
                gp.gas_viscosity_lee_gonzalez_eakin(620.0, 18.0, 1.0e6)
            with self.assertRaises((InvalidInputError, ConvergenceError)):
                gp.z_factor_hall_yarborough(1.0e-8, 1.0)
            with self.assertRaises((InvalidInputError, ConvergenceError)):
                gp.z_factor_hall_yarborough(1.5, 1.0e12)

    def test_formation_volume_factor_rejects_non_positive_arguments(self):
        for bad in self.NON_POSITIVE:
            with self.subTest(value=bad):
                with self.assertRaises(InvalidInputError):
                    gp.gas_fvf_rcf_per_scf(bad, 600.0, 0.9, SPE_STANDARD)
                with self.assertRaises(InvalidInputError):
                    gp.gas_fvf_rb_per_scf(2000.0, bad, 0.9, SPE_STANDARD)


# ---------------------------------------------------------------------------
# Limiting cases and invariants
# ---------------------------------------------------------------------------


class LimitingCaseTests(unittest.TestCase):
    """Limits with a known analytic answer, and identities the solvers must satisfy."""

    def test_ideal_gas_limit_of_every_correlation(self):
        # As Ppr falls every correlation must approach Z = 1. Note that
        # Hall-Yarborough crosses slightly ABOVE 1 at high Tpr; that is a property of
        # the fit, so the assertion is on the distance from 1 and not on Z <= 1.
        with quiet_range_warnings():
            for t_pr in (1.3, 2.0, 3.0):
                for solver in (gp.z_factor_dak, gp.z_factor_hall_yarborough, gp.z_factor_dpr):
                    with self.subTest(t_pr=t_pr, solver=solver.__name__):
                        self.assertLess(abs(solver(t_pr, 0.2) - 1.0), 0.04)
                        self.assertLess(abs(solver(t_pr, 0.02) - 1.0), 0.005)

    def test_the_dak_root_satisfies_an_independently_retyped_polynomial(self):
        # This used to lead with rho_r Z Tpr / Ppr = 0.27 at thirteen places. That
        # assertion cannot fail: z_factor_dak returns 0.27 Ppr / (rho_r Tpr) computed
        # from the same reduced_density_dak call, so it restates the return statement.
        # It has been removed rather than kept under a different name.
        #
        # What is left is the assertion that was doing the work, strengthened. The
        # returned reduced density is fed into the DAK polynomial retyped in this file
        # from the published coefficients, and the Z it produces must match the Z the
        # module returned. A wrong coefficient in either copy, or a root the solver
        # never actually converged to, breaks it.
        #
        # Gate: 1e-10 relative, one order above the roughly 5e-11 the module's 1e-12
        # bracket tolerance on reduced density implies for Z over this window.
        with quiet_range_warnings():
            for t_pr, p_pr in ((1.05, 15.0), (1.3, 3.0), (2.0, 10.0), (3.0, 25.0)):
                with self.subTest(t_pr=t_pr, p_pr=p_pr):
                    rho_r = gp.reduced_density_dak(t_pr, p_pr)
                    z_value = gp.z_factor_dak(t_pr, p_pr)
                    independent = dak_z_by_bisection(t_pr, p_pr)
                    self.assertAlmostEqual(z_value / independent, 1.0, delta=1.0e-10)
                    # ... and the reduced density the solver reports is the one that
                    # belongs to that Z, which is what makes the compressibility path
                    # entitled to reuse it.
                    self.assertAlmostEqual(rho_r, 0.27 * p_pr / (independent * t_pr), delta=1.0e-11)
                    self.assertAlmostEqual(_dak_z_of_reduced_density(rho_r, t_pr), z_value, places=10)

    def test_hall_yarborough_root_satisfies_an_independently_retyped_residual(self):
        # Recover the reduced density from the returned Z and check the residual is
        # zero. The groups A, B, C and D are retyped here from Hall & Yarborough (1973)
        # rather than imported from the module: with the module's own groups on both
        # sides, a swapped or mistyped coefficient left the residual exactly zero and
        # the test green, so it pinned convergence and nothing else.
        #
        # Gate: the residual is order one in y, and y is determined by the solver's
        # 1e-12 bracket tolerance, so a converged root gives a residual of order 1e-11.
        # 1e-10 absolute is the gate, which is an order of margin on that.
        def groups(t_pr: float) -> tuple[float, float, float, float]:
            t = 1.0 / t_pr
            return (
                0.06125 * t * math.exp(-1.2 * (1.0 - t) ** 2),
                14.76 * t - 9.76 * t**2 + 4.58 * t**3,
                90.7 * t - 242.2 * t**2 + 42.4 * t**3,
                2.18 + 2.82 * t,
            )

        with quiet_range_warnings():
            for t_pr, p_pr in ((1.3, 3.0), (1.5, 8.0), (2.5, 15.0)):
                with self.subTest(t_pr=t_pr, p_pr=p_pr):
                    alpha, b, c, d = groups(t_pr)
                    z_value = gp.z_factor_hall_yarborough(t_pr, p_pr)
                    y = alpha * p_pr / z_value
                    self.assertGreater(y, 0.0)
                    self.assertLess(y, 1.0)
                    residual = -alpha * p_pr + (y + y**2 + y**3 - y**4) / (1.0 - y) ** 3 - b * y**2 + c * y**d
                    self.assertAlmostEqual(residual, 0.0, delta=1.0e-10)

    def test_the_retyped_hall_yarborough_residual_would_notice_a_swapped_group(self):
        # Positive control for the test above, and the reason retyping the groups was
        # worth doing. Swapping the B and C groups -- the shape a transposition takes --
        # leaves a residual of order one where zero is required.
        t_pr, p_pr = 1.3, 3.0
        t = 1.0 / t_pr
        alpha = 0.06125 * t * math.exp(-1.2 * (1.0 - t) ** 2)
        b = 14.76 * t - 9.76 * t**2 + 4.58 * t**3
        c = 90.7 * t - 242.2 * t**2 + 42.4 * t**3
        d = 2.18 + 2.82 * t
        with quiet_range_warnings():
            y = alpha * p_pr / gp.z_factor_hall_yarborough(t_pr, p_pr)
        swapped = -alpha * p_pr + (y + y**2 + y**3 - y**4) / (1.0 - y) ** 3 - c * y**2 + b * y**d
        self.assertGreater(abs(swapped), 1.0e-2)

    def test_the_returned_root_does_not_move_when_the_tolerance_is_tightened(self):
        # The property the convergence tests never checked: they vary max_iterations,
        # which shows that an exhausted budget raises, but nothing showed that the
        # default tolerance is actually converged rather than merely stopping early.
        # Tightening the bracket tolerance by three orders must not move the answer by
        # more than the looser tolerance already claims.
        #
        # Gate: 1e-9 relative, the same figure argued for the bisection cross-check --
        # a 1e-12 bracket on a reduced density of order 0.02 or larger pins Z to about
        # 5e-11 relative, and the gate sits an order above that.
        with quiet_range_warnings():
            for solver, window in (
                (gp.z_factor_dak, ((1.0, 3.0), (0.2, 30.0))),
                (gp.z_factor_hall_yarborough, ((1.2, 3.0), (0.2, 20.0))),
                (gp.z_factor_dpr, ((1.05, 3.0), (0.2, 30.0))),
            ):
                (t_low, t_high), (p_low, p_high) = window
                t_pr = t_low
                while t_pr <= t_high + 1e-9:
                    p_pr = p_low
                    while p_pr <= p_high + 1e-9:
                        with self.subTest(solver=solver.__name__, t_pr=round(t_pr, 2), p_pr=round(p_pr, 1)):
                            loose = solver(t_pr, p_pr)
                            tight = solver(t_pr, p_pr, tolerance=1.0e-15)
                            self.assertAlmostEqual(loose / tight, 1.0, delta=1.0e-9)
                        p_pr += 2.0
                    t_pr += 0.2

    def test_deviation_factor_exceeds_one_at_high_reduced_pressure(self):
        # Z is not bounded above by 1. Any code path that clamped it would be wrong,
        # and this states the expectation where it bites.
        with quiet_range_warnings():
            self.assertGreater(gp.z_factor_dak(1.5, 20.0), 1.0)
            self.assertGreater(gp.z_factor_dak(1.05, 30.0), 3.0)

    def test_deviation_factor_is_monotone_in_pressure_above_its_minimum(self):
        # Structural shape of the Standing-Katz isotherm: Z falls, reaches a minimum,
        # then rises without turning again. A single interior minimum is the property.
        with quiet_range_warnings():
            values = [gp.z_factor_dak(1.5, 0.2 + 0.2 * index) for index in range(150)]
        turning_points = sum(
            1
            for index in range(1, len(values) - 1)
            if (values[index] - values[index - 1]) * (values[index + 1] - values[index]) < 0.0
        )
        self.assertEqual(turning_points, 1)

    def test_density_reproduces_the_standard_molar_volume(self):
        # Closed-form check on the gas constant and the unit chain: at one standard
        # atmosphere and 60 degF with Z = 1 the molar volume is R T / p, and the
        # published figure is 379.4 scf/lbmol (Whitson & Brule Eq. 3.27). Nothing
        # correlational is involved, and this is what pins R for the whole file.
        #
        # Tolerance, built from two terms rather than chosen. The published figure is
        # printed to four significant figures, so half of its last digit is
        # 0.05 scf/lbmol. It does not say which standard basis it used, and the two in
        # common use disagree by 0.14: 14.696 psia and 519.67 degR give 379.48,
        # 14.7 psia and 520 degR give 379.62. The gate is the sum of the two, 0.19.
        # The molar mass is arbitrary: it cancels, which is the point of quoting a
        # molar volume rather than a density.
        #
        # A second assertion here previously compared the same molar volume to
        # R T / p computed from the module's own gas constant. That is the definition
        # of gas_density_lbm_per_cuft rearranged and could not fail; it has been
        # removed rather than renamed.
        molar_mass = 18.0
        density = gp.gas_density_lbm_per_cuft(
            SPE_STANDARD.pressure_psia, SPE_STANDARD.temperature_rankine, 1.0, molar_mass
        )
        self.assertAlmostEqual(molar_mass / density, 379.4, delta=0.19)

    def test_density_scales_as_the_ideal_gas_law_at_fixed_z(self):
        # Dimensional scaling: at fixed Z, doubling pressure doubles density and
        # doubling absolute temperature halves it.
        base = gp.gas_density_lbm_per_cuft(2000.0, 600.0, 0.9, 18.0)
        doubled_pressure = gp.gas_density_lbm_per_cuft(4000.0, 600.0, 0.9, 18.0)
        doubled_temperature = gp.gas_density_lbm_per_cuft(2000.0, 1200.0, 0.9, 18.0)
        self.assertAlmostEqual(doubled_pressure / base, 2.0, places=12)
        self.assertAlmostEqual(doubled_temperature / base, 0.5, places=12)

    def test_formation_volume_factor_matches_the_published_coefficients(self):
        # Replaces a check that Bg = 1 at the standard state. That one held for any
        # StandardConditions whatsoever, a wrong one included, because the leading
        # group is p_sc/(Z_sc T_sc) and the state substituted back is p_sc, T_sc, Z_sc;
        # it could not fail and said nothing about the coefficient the docstring is
        # actually worried about.
        #
        # This checks that group against the two constants every textbook prints,
        # 0.02827 rcf/scf and 0.005035 rb/scf. Both assume 14.7 psia and 520 degR --
        # not 14.696 and 519.67, which give 0.028279 and 0.0050368 -- so the basis is
        # constructed here explicitly, which is itself the point the module docstring
        # makes about not hard-coding the familiar number.
        #
        # Tolerance: half of the last printed digit of each published constant,
        # 5e-6 on 0.02827 and 5e-7 on 0.005035. Nothing else is admissible for a
        # comparison against a printed constant.
        textbook_basis = StandardConditions(
            pressure_psia=14.7,
            temperature_degf=60.33,  # exactly 520 degR, the rounding the constants use
            z_factor=1.0,
            label="textbook basis, 14.7 psia and 520 degR",
        )
        self.assertAlmostEqual(textbook_basis.temperature_rankine, 520.0, places=9)
        pressure_psia, temperature_degr, z_value = 2000.0, 620.0, 0.85
        cubic_feet = gp.gas_fvf_rcf_per_scf(pressure_psia, temperature_degr, z_value, textbook_basis)
        barrels = gp.gas_fvf_rb_per_scf(pressure_psia, temperature_degr, z_value, textbook_basis)
        group = z_value * temperature_degr / pressure_psia
        self.assertAlmostEqual(cubic_feet / group, 0.02827, delta=5.0e-6)
        self.assertAlmostEqual(barrels / group, 0.005035, delta=5.0e-7)
        # ... and the SPE basis genuinely differs, which is the reason the coefficient
        # is computed from the supplied conditions instead of being hard-coded.
        spe = gp.gas_fvf_rcf_per_scf(pressure_psia, temperature_degr, z_value, SPE_STANDARD)
        self.assertGreater(abs(spe / cubic_feet - 1.0), 0.0003)

    def test_formation_volume_factor_barrel_conversion(self):
        cubic_feet = gp.gas_fvf_rcf_per_scf(2000.0, 620.0, 0.85, SPE_STANDARD)
        barrels = gp.gas_fvf_rb_per_scf(2000.0, 620.0, 0.85, SPE_STANDARD)
        self.assertAlmostEqual(cubic_feet / barrels, 5.614583333333333, places=12)

    def test_pseudocriticals_describe_their_own_provenance(self):
        # Contract C5: a result carries enough metadata to be auditable. A corrected
        # set must say so, because Tpr formed from uncorrected pseudocriticals after a
        # sour-gas correction is a silent and material error.
        base = gp.pseudocritical_sutton(0.8)
        corrected = gp.wichert_aziz_correction(base, y_h2s=0.05, y_co2=0.10)
        self.assertIn("sutton", corrected.describe())
        self.assertIn("wichert-aziz", corrected.describe())

    def test_results_are_deterministic(self):
        # Contract C4: equal arguments, equal results, bit for bit.
        with quiet_range_warnings():
            solvers = (gp.z_factor_dak, gp.z_factor_hall_yarborough, gp.z_factor_dpr)
            first = [solver(1.4, 4.0) for solver in solvers]
            second = [solver(1.4, 4.0) for solver in solvers]
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
r"""Profile-aware verification entry point.

This repository can be verified to two different depths, and the difference matters
enough that it deserves a name rather than a footnote.

``public-core``
    What anyone can run from a clone of the public tree: no restricted reference files,
    no network. It covers the numerical core, the analytic identities, and the synthetic
    case studies whose committed snapshots it re-derives and compares byte for byte.
    The checks that need the restricted reference extract are not silently skipped --
    they are reported as NOT RUN, with a count and a reason.

``external-reference``
    An explicit opt-in for someone who has obtained the NIST Chemistry WebBook extract
    themselves. It requires a local directory holding that extract and a recorded
    statement of the basis on which it was obtained, and it fails clearly if either is
    missing. It is the only profile that compares this library against values it did
    not produce.

``public-core`` is not external validation and this script never calls it that. It is a
self-consistency and reproducibility result: the code agrees with its own committed
snapshots, its own analytic limits, and its own closed forms. A profile that cannot see
an independent reference cannot tell you the library is right about the physical world,
only that it is internally coherent and has not drifted.

Exit status is 0 only when every mandatory check in the selected profile passed.

Usage
-----
    python3 scripts/verify.py --profile public-core
    python3 scripts/verify.py --profile public-core --cases fast --json report.json
    python3 scripts/verify.py --profile external-reference \\
        --reference-dir /path/to/my/nist/extract \\
        --access-basis "Downloaded 2026-09-13 from webbook.nist.gov under SRD 69 terms"
    python3 scripts/verify.py --hook-stage pre-push
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict, dataclass, field
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
SRC = REPO_ROOT / "src"
TESTS = REPO_ROOT / "tests"
CASES = REPO_ROOT / "cases"
REFERENCE_DIR = REPO_ROOT / "data" / "reference"
MANIFEST_PATH = REFERENCE_DIR / "MANIFEST.json"
PRE_COMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"

# The data-policy stream owns this script. It is the gate that decides what may appear
# in a published tree, and it is a prerequisite for every profile here. If it has not
# landed yet, the check below reports that by name rather than passing quietly.
PUBLIC_RELEASE_CHECK = SCRIPTS / "check_public_release.py"

# Emitted by tests/oracles/nist.py:require_reference_data when the extract is absent.
# Matching on it is how a reference-dependent skip is told apart from any other skip:
# an "expected" skip is one this policy explains, and every other skip fails the run.
REFERENCE_SKIP_SENTINEL = "NIST reference extract not present"

# The second, and only other, declared reason a skip is permitted. An oracle that
# corroborates a result already checked by an in-tree oracle may live behind an optional
# dependency, because the stdlib runner deliberately installs nothing and a hard import
# there would make the dependency-free claim false. Such a test must skip with this
# sentinel so the skip is counted, named and reported rather than silently tolerated.
#
# The bar for adding an id here is that the check is CORROBORATING: something else in the
# tree must already be testing the same property unconditionally. An id that is the only
# test of a property does not belong here -- that would be a check nobody runs, wearing a
# declaration. The registry maps the id to the unconditional check it corroborates.
OPTIONAL_ORACLE_SENTINEL = "OPTIONAL ORACLE ABSENT"
OPTIONAL_ORACLES: dict[str, str] = {
    "mpmath": (
        "corroborates the exponential integral, which tests/test_transient.py already "
        "checks unconditionally against a stdlib decimal oracle and an asymptotic oracle"
    ),
}

# Field names in MANIFEST.json belong to the data-policy stream. The manifest must
# record a citation obligation; which of these keys carries it is that stream's call.
CITATION_KEYS = ("citation_required", "attribution_required")

# Markers that say a case study reads the restricted reference extract. A case whose
# source names any of these cannot run in a public checkout, and that is the reason
# reported for it rather than a bare "not run".
REFERENCE_SOURCE_MARKERS = ("data/reference", "REFERENCE_DIR", "nist_")

PROFILES = ("public-core", "external-reference")
CASE_SELECTIONS = ("all", "fast", "none")
# A1 is the cheapest reproduction that still exercises the whole run-record path, so it
# is the one the pre-push hook runs. A3 and A4 take about fifteen and twelve seconds.
FAST_CASES = ("A1_volumetric_baseline",)

PASSED, FAILED, NOT_RUN = "passed", "failed", "not run"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass
class Check:
    """One named verification step and what happened to it."""

    id: str
    title: str
    status: str
    mandatory: bool
    detail: str = ""
    reason: str = ""
    count: int | None = None


@dataclass
class TestCounts:
    """Test-suite counts, separated into the mandatory part and the reference part."""

    collected: int = 0
    passed: int = 0
    failed: int = 0
    errored: int = 0
    skipped: int = 0
    reference_dependent_skipped: int = 0
    optional_oracle_skipped: int = 0
    mandatory_collected: int = 0
    unexpected_skips: list[str] = field(default_factory=list)
    optional_oracles_absent: list[str] = field(default_factory=list)


def _import_check_module():
    """Import ``scripts/check.py``, which owns the shared warning policy."""
    for entry in (str(SRC), str(REPO_ROOT), str(SCRIPTS), str(TESTS)):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    import check

    return check


# ---------------------------------------------------------------------------
# Reference manifest policy
# ---------------------------------------------------------------------------


def check_reference_manifest_policy() -> Check:
    """Validate the reference manifest as a policy document, without hashing anything.

    In a published tree the three NIST tables are deliberately absent, so a digest check
    would fail by design and tell nobody anything. What is still checkable, and what
    actually matters for a reader, is that the manifest is a complete and well-formed
    record of provenance: what the numbers are, where they came from, what has to be
    cited, and what digest each file is required to have if someone fetches it.
    """
    if not MANIFEST_PATH.is_file():
        return Check(
            id="reference-manifest-policy",
            title="reference manifest is a complete provenance record",
            status=FAILED,
            mandatory=True,
            detail=f"{MANIFEST_PATH.relative_to(REPO_ROOT)} is missing",
        )
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return Check(
            id="reference-manifest-policy",
            title="reference manifest is a complete provenance record",
            status=FAILED,
            mandatory=True,
            detail=f"manifest could not be parsed: {exc}",
        )

    problems: list[str] = []
    for key in ("source", "source_url", "what_these_numbers_are", "files"):
        if not manifest.get(key):
            problems.append(f"top-level key {key!r} is missing or empty")
    # The manifest's exact field names belong to the data-policy stream, so this asks
    # for the substance rather than one spelling: somewhere in the manifest there must
    # be a statement of what a reader has to cite. Accepting a small set of aliases
    # keeps this check from breaking every time that file is reworded, while still
    # failing if the obligation disappears altogether.
    if not any(manifest.get(alias) for alias in CITATION_KEYS):
        problems.append(
            "no citation obligation recorded: expected one of "
            + ", ".join(repr(alias) for alias in CITATION_KEYS)
        )

    entries = manifest.get("files") or []
    if not isinstance(entries, list) or not entries:
        problems.append("'files' must be a non-empty list")
        entries = []

    present, absent = [], []
    for index, entry in enumerate(entries):
        label = entry.get("path", f"files[{index}]") if isinstance(entry, dict) else f"files[{index}]"
        if not isinstance(entry, dict):
            problems.append(f"{label}: entry is not an object")
            continue
        for key in ("path", "species", "sha256", "rows", "eos_reference", "request_urls"):
            if not entry.get(key):
                problems.append(f"{label}: required field {key!r} is missing or empty")
        digest = entry.get("sha256", "")
        if isinstance(digest, str) and not SHA256_PATTERN.match(digest):
            problems.append(f"{label}: sha256 is not 64 lowercase hex characters")
        if not isinstance(entry.get("rows"), int) or entry.get("rows", 0) <= 0:
            problems.append(f"{label}: 'rows' must be a positive integer")
        (present if (REFERENCE_DIR / str(entry.get("path"))).is_file() else absent).append(label)

    if problems:
        return Check(
            id="reference-manifest-policy",
            title="reference manifest is a complete provenance record",
            status=FAILED,
            mandatory=True,
            detail="; ".join(problems),
        )
    detail = (
        f"{len(entries)} declared tables, {len(present)} present in the checkout, "
        f"{len(absent)} absent. No file was hashed here: digest verification is what the "
        f"external-reference profile is for, and hashing a file the public tree is "
        f"supposed to not have would fail by design."
    )
    return Check(
        id="reference-manifest-policy",
        title="reference manifest is a complete provenance record",
        status=PASSED,
        mandatory=True,
        detail=detail,
        count=len(entries),
    )


def check_public_release_gate() -> Check:
    """Report the data-policy gate that decides what may appear in a published tree.

    This is reported as a prerequisite rather than folded into the profile's verdict,
    because it answers a different question. "Is this tree publishable" is about what
    files may leave the machine; "is this code verified" is about whether the numbers
    are right. Conflating them means a documentation path that leaks a local directory
    name turns into a numerical failure, and a reader cannot tell which one happened.

    CI keeps the hard version of this gate: the source-policy job runs the same script
    and every verification job depends on it, so a failing policy blocks the pipeline
    even though it does not change the number this script prints.
    """
    if not PUBLIC_RELEASE_CHECK.is_file():
        return Check(
            id="public-release-policy",
            title="published-tree data policy (prerequisite, enforced by CI)",
            status=FAILED,
            mandatory=False,
            detail=(
                f"{PUBLIC_RELEASE_CHECK.relative_to(REPO_ROOT)} is not present. It is the "
                f"gate that decides what may appear in a published tree. CI runs it as a "
                f"job that every verification job depends on, so its absence blocks the "
                f"pipeline there."
            ),
        )
    completed = subprocess.run(  # fixed argv, never a shell
        [sys.executable, str(PUBLIC_RELEASE_CHECK)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    status = PASSED if completed.returncode == 0 else FAILED
    tail = (completed.stdout + completed.stderr).strip().splitlines()
    return Check(
        id="public-release-policy",
        title="published-tree data policy (prerequisite, enforced by CI)",
        status=status,
        mandatory=False,
        detail=f"exit {completed.returncode}" + (f"; {tail[-1]}" if tail else ""),
    )


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------


def run_test_suite(pattern: str = "test_*.py") -> tuple[TestCounts, unittest.TestResult]:
    """Run the suite under the declared warning policy and classify every skip."""
    check = _import_check_module()
    _, result = check.run_tests(pattern, verbosity=1)

    counts = TestCounts(
        collected=result.testsRun,
        failed=len(result.failures),
        errored=len(result.errors),
        skipped=len(result.skipped),
    )
    for test, reason in result.skipped:
        if REFERENCE_SKIP_SENTINEL in reason:
            counts.reference_dependent_skipped += 1
        elif OPTIONAL_ORACLE_SENTINEL in reason:
            # The sentinel alone is not enough: the id must be one this policy knows
            # about, so that adding an optional dependency is a deliberate edit here
            # rather than a sentence someone wrote into a test.
            declared = next((name for name in OPTIONAL_ORACLES if f"[{name}]" in reason), None)
            if declared is None:
                counts.unexpected_skips.append(
                    f"{test.id()}: claims {OPTIONAL_ORACLE_SENTINEL} but names no "
                    f"registered oracle; known ids are {sorted(OPTIONAL_ORACLES)}"
                )
            else:
                counts.optional_oracle_skipped += 1
                counts.optional_oracles_absent.append(f"{declared} ({test.id()})")
        else:
            counts.unexpected_skips.append(f"{test.id()}: {reason}")
    counts.mandatory_collected = counts.collected - counts.reference_dependent_skipped
    counts.passed = counts.collected - counts.failed - counts.errored - counts.skipped
    return counts, result


def test_suite_checks(counts: TestCounts, expect_reference_skips: int | None) -> list[Check]:
    """Turn the suite counts into pass/fail checks with their reasons spelled out."""
    checks: list[Check] = []

    # Zero collected is a failure here too, not just in the next check: a line that
    # reads "0 collected, 0 passed, 0 failed" next to the word "pass" is exactly the
    # kind of green a reader should never be shown.
    outcome = PASSED if (counts.failed == 0 and counts.errored == 0 and counts.collected > 0) else FAILED
    checks.append(
        Check(
            id="test-suite",
            title="numerical, analytic and synthetic unit tests",
            status=outcome,
            mandatory=True,
            detail=(
                f"{counts.collected} collected, {counts.passed} passed, "
                f"{counts.failed} failed, {counts.errored} errored, {counts.skipped} skipped"
            ),
            count=counts.collected,
        )
    )

    # An empty suite is the failure mode that looks most like success. Guard it
    # explicitly rather than trusting that it cannot happen.
    checks.append(
        Check(
            id="mandatory-tests-collected",
            title="the mandatory part of the suite is non-empty",
            status=PASSED if counts.mandatory_collected > 0 else FAILED,
            mandatory=True,
            detail=(
                f"{counts.mandatory_collected} mandatory tests collected "
                f"({counts.collected} total minus {counts.reference_dependent_skipped} "
                f"reference-dependent). Zero would mean discovery is broken, not that "
                f"everything passed."
            ),
            count=counts.mandatory_collected,
        )
    )

    checks.append(
        Check(
            id="no-unexpected-skips",
            title="every skip carries a reason this policy declares",
            status=PASSED if not counts.unexpected_skips else FAILED,
            mandatory=True,
            detail=(
                "every skip carries a declared reason"
                if not counts.unexpected_skips
                else "unexplained skips: " + "; ".join(counts.unexpected_skips)
            ),
            count=len(counts.unexpected_skips),
        )
    )

    # Reported, never failed. An absent optional oracle is a corroboration that did not
    # happen, and a reader is entitled to see that rather than infer it from a count that
    # went quiet. The run it is absent on is the stdlib runner, which installs nothing on
    # purpose; the pytest runner installs requirements-dev.lock and this check reads zero.
    checks.append(
        Check(
            id="optional-oracles-present",
            title="corroborating oracles behind optional dependencies",
            status=PASSED,
            mandatory=False,
            detail=(
                "every declared optional oracle ran"
                if not counts.optional_oracles_absent
                else (
                    "not installed here, so the corroboration did not run: "
                    + "; ".join(counts.optional_oracles_absent)
                    + ". The properties themselves are checked unconditionally elsewhere: "
                    + "; ".join(
                        f"{name} -- {why}"
                        for name, why in OPTIONAL_ORACLES.items()
                        if any(entry.startswith(name) for entry in counts.optional_oracles_absent)
                    )
                )
            ),
            count=counts.optional_oracle_skipped,
        )
    )

    if expect_reference_skips is not None:
        matched = counts.reference_dependent_skipped == expect_reference_skips
        checks.append(
            Check(
                id="reference-skip-count-drift",
                title="the reference-dependent skip count has not drifted",
                status=PASSED if matched else FAILED,
                mandatory=True,
                detail=(
                    f"measured {counts.reference_dependent_skipped}, "
                    f"caller expected {expect_reference_skips}. The measured number is the "
                    f"source of truth; the expected number is a drift alarm, so a mismatch "
                    f"means either tests were added or removed, or the extract appeared."
                ),
                count=counts.reference_dependent_skipped,
            )
        )
    return checks


# ---------------------------------------------------------------------------
# Case reproduction
# ---------------------------------------------------------------------------


def discover_cases() -> tuple[list[pathlib.Path], list[pathlib.Path]]:
    """Split ``cases/`` into the reproducible ones and the ones that need the extract.

    The split is derived from the tree rather than listed here: a case that ships a
    committed ``results/summary.json`` is one whose numbers a reader is meant to be able
    to re-derive, and a case without one is a case whose inputs this tree does not hold.
    """
    reproducible, other = [], []
    for directory in sorted(p for p in CASES.iterdir() if p.is_dir()):
        (reproducible if (directory / "results" / "summary.json").is_file() else other).append(directory)
    return reproducible, other


def case_needs_reference_data(case_dir: pathlib.Path) -> bool:
    """Report whether a case names the restricted reference extract in its source."""
    source = case_dir / "run.py"
    if not source.is_file():
        return False
    text = source.read_text(encoding="utf-8")
    return any(marker in text for marker in REFERENCE_SOURCE_MARKERS)


def in_canonical_environment() -> bool:
    """Return True when this machine is the environment the snapshots are published from.

    The canonical environment is Linux on x86_64. It is checked by platform rather than by
    container digest on purpose: a reader who clones this repository onto an ordinary
    x86_64 Linux box should get the byte comparison, because that is the comparison that
    holds there. It was measured to hold across glibc 2.36 and 2.39 and across CPython
    3.11, 3.12 and 3.13, so the useful boundary is the platform, not the image.

    CI pins the image anyway, because "the canonical environment" has to mean one exact
    thing when it is used to publish, and a digest is the only way to say that.
    """
    return platform.system() == "Linux" and platform.machine() in {"x86_64", "AMD64"}


def _portability_check(case_dir: pathlib.Path, produced: pathlib.Path) -> Check:
    """Compare a fresh run against the canonical snapshot semantically, not byte for byte.

    Off the canonical platform, byte identity is the wrong question: libm is permitted to
    differ in its last place and a Newton iteration turns that into a different final
    digit. What must hold is that the case reaches the same verdict and stays inside the
    declared numerical envelope. `scripts/compare_case_outputs.py` owns that judgement and
    compares every acceptance state exactly.
    """
    committed = case_dir / "results" / "summary.json"
    completed = subprocess.run(  # fixed argv, never a shell
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "compare_case_outputs.py"),
            str(committed),
            str(produced),
            "--label",
            case_dir.name,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    ok = completed.returncode == 0
    tail = [line for line in (completed.stdout or "").splitlines() if "max relative" in line]
    return Check(
        id=f"case-{case_dir.name}",
        title=f"{case_dir.name} is numerically portable to this platform",
        status=PASSED if ok else FAILED,
        mandatory=True,
        detail=(
            "not the canonical environment, so this is the portability comparison and not "
            "byte identity: every acceptance state matched exactly and every value stayed "
            "inside the declared envelope" + (f" ({tail[0].strip()})" if ok and tail else "")
            if ok
            else "the fresh run falls outside the declared portability envelope; "
            + (completed.stdout or completed.stderr).strip().splitlines()[-1:][0]
            if (completed.stdout or completed.stderr).strip()
            else "the portability comparison failed"
        ),
    )


def reproduce_case(case_dir: pathlib.Path) -> Check:
    """Re-run one case and check it against its committed canonical snapshot.

    Inside the canonical environment that means byte identity, with no tolerance.
    Outside it that means the portability comparison. Both are mandatory; they are
    different questions, and reporting them under the same name would hide which one was
    actually asked.
    """
    committed = case_dir / "results" / "summary.json"
    with tempfile.TemporaryDirectory(prefix=f"verify-{case_dir.name}-") as temporary:
        out = pathlib.Path(temporary) / "run"
        completed = subprocess.run(  # fixed argv, never a shell
            [sys.executable, str(case_dir / "run.py"), "--out", str(out)],
            cwd=REPO_ROOT,
            env={**_case_environment()},
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            tail = (completed.stderr or completed.stdout).strip().splitlines()[-1:]
            return Check(
                id=f"case-{case_dir.name}",
                title=f"{case_dir.name} reproduces its committed snapshot",
                status=FAILED,
                mandatory=True,
                detail=f"run.py exited {completed.returncode}" + (f": {tail[0]}" if tail else ""),
            )
        produced = out / "summary.json"
        if not produced.is_file():
            return Check(
                id=f"case-{case_dir.name}",
                title=f"{case_dir.name} reproduces its committed snapshot",
                status=FAILED,
                mandatory=True,
                detail=f"the run produced no summary.json under {out}",
            )
        if not in_canonical_environment():
            return _portability_check(case_dir, produced)
        same = produced.read_bytes() == committed.read_bytes()
        return Check(
            id=f"case-{case_dir.name}",
            title=f"{case_dir.name} reproduces its canonical snapshot",
            status=PASSED if same else FAILED,
            mandatory=True,
            detail=(
                "canonical environment: the fresh run reproduces results/summary.json byte for byte"
                if same
                else "canonical environment: the fresh run disagrees with the committed "
                "results/summary.json, and here that comparison has no tolerance"
            ),
        )


def _case_environment() -> dict[str, str]:
    """Build the environment a case needs: the src layout on PYTHONPATH, nothing else."""
    environment = dict(os.environ)
    existing = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = f"{SRC}{':' + existing if existing else ''}"
    return environment


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------


def run_public_core(
    cases: str,
    expect_reference_skips: int | None,
    policy_only: bool = False,
) -> dict[str, Any]:
    """Run everything a clone of the public tree can run, offline.

    ``policy_only`` stops after the cheap structural checks and runs no tests and no
    cases. It exists so CI can put the policy gates in a job that every other job
    depends on, and fail the pipeline in a few seconds when a policy is broken instead
    of after a full matrix has run.
    """
    checks: list[Check] = [check_public_release_gate(), check_reference_manifest_policy()]

    check_module = _import_check_module()
    try:
        specs = check_module.read_warning_policy()
        checks.append(
            Check(
                id="warning-policy",
                title="both runners share one warning policy",
                status=PASSED if specs else FAILED,
                mandatory=True,
                detail=(
                    "policy read from pyproject.toml: " + ", ".join(specs)
                    if specs
                    else "pyproject.toml declares no filterwarnings entries, so an "
                    "out-of-range correlation call would pass silently under both runners"
                ),
            )
        )
    except check_module.WarningPolicyError as exc:
        checks.append(
            Check(
                id="warning-policy",
                title="both runners share one warning policy",
                status=FAILED,
                mandatory=True,
                detail=str(exc),
            )
        )

    if policy_only:
        report = _assemble("public-core", checks, [], TestCounts())
        report["profile"] = "public-core (policy only)"
        report["evidence_class"] = (
            "structural policy checks only. No test was run and no case was reproduced, "
            "so this says nothing about whether the numbers are right."
        )
        return report

    counts, _ = run_test_suite()
    checks.extend(test_suite_checks(counts, expect_reference_skips))

    reproducible, other = discover_cases()
    selected = [c for c in reproducible if cases == "all" or (cases == "fast" and c.name in FAST_CASES)]
    for case_dir in selected:
        checks.append(reproduce_case(case_dir))

    not_run: list[Check] = []
    if counts.reference_dependent_skipped:
        not_run.append(
            Check(
                id="reference-property-tests",
                title="library values compared against the NIST reference tables",
                status=NOT_RUN,
                mandatory=False,
                count=counts.reference_dependent_skipped,
                reason=(
                    "The NIST Chemistry WebBook extract is not in this tree. The count is "
                    "measured from the suite's own skip reasons, not asserted here. Run the "
                    "external-reference profile with a local copy to execute these."
                ),
            )
        )
    for case_dir in other:
        not_run.append(
            Check(
                id=f"case-{case_dir.name}",
                title=f"{case_dir.name}",
                status=NOT_RUN,
                mandatory=False,
                count=1,
                reason=(
                    "No committed results/summary.json to reproduce, and the case source "
                    "names data/reference as an input, so it exits non-zero when the "
                    "extract is absent."
                    if case_needs_reference_data(case_dir)
                    else "No committed results/summary.json to reproduce."
                ),
            )
        )
    for case_dir in reproducible:
        if case_dir not in selected:
            not_run.append(
                Check(
                    id=f"case-{case_dir.name}",
                    title=f"{case_dir.name}",
                    status=NOT_RUN,
                    mandatory=False,
                    count=1,
                    reason=f"not selected by --cases {cases}",
                )
            )
    not_run.append(
        Check(
            id="reference-digest-verification",
            title="sha256 of each reference table matches the manifest",
            status=NOT_RUN,
            mandatory=False,
            count=len(json.loads(MANIFEST_PATH.read_text(encoding="utf-8")).get("files", []))
            if MANIFEST_PATH.is_file()
            else 0,
            reason=(
                "The tables are deliberately absent from the public tree. Their required "
                "digests are recorded in data/reference/MANIFEST.json and are checked by "
                "the external-reference profile against a copy the user supplies."
            ),
        )
    )

    return _assemble("public-core", checks, not_run, counts)


def run_external_reference(
    reference_dir: pathlib.Path | None,
    access_basis: str | None,
    cases: str,
) -> dict[str, Any]:
    """Verify against a user-supplied copy of the restricted reference extract."""
    checks: list[Check] = []
    not_run: list[Check] = []

    if reference_dir is None:
        checks.append(
            Check(
                id="reference-directory-supplied",
                title="a local reference directory was named",
                status=FAILED,
                mandatory=True,
                detail=(
                    "--reference-dir is required by this profile. This profile exists to "
                    "compare the library against values it did not produce, and there is "
                    "nothing in this repository to compare against."
                ),
            )
        )
    if not access_basis:
        checks.append(
            Check(
                id="access-basis-recorded",
                title="the basis for holding the reference data is recorded",
                status=FAILED,
                mandatory=True,
                detail=(
                    "--access-basis or --access-basis-file is required by this profile. "
                    "Access rights and redistribution rights are different rights, and a "
                    "verification record that does not say which one the operator has is "
                    "not a record worth keeping."
                ),
            )
        )
    if reference_dir is None or not access_basis:
        return _assemble("external-reference", checks, not_run, TestCounts())

    resolved = reference_dir.expanduser().resolve()
    checks.append(
        Check(
            id="access-basis-recorded",
            title="the basis for holding the reference data is recorded",
            status=PASSED,
            mandatory=True,
            detail=access_basis.strip(),
        )
    )
    if not resolved.is_dir():
        checks.append(
            Check(
                id="reference-directory-present",
                title="the named reference directory exists",
                status=FAILED,
                mandatory=True,
                detail=f"{resolved} is not a directory",
            )
        )
        return _assemble("external-reference", checks, not_run, TestCounts())
    checks.append(
        Check(
            id="reference-directory-present",
            title="the named reference directory exists",
            status=PASSED,
            mandatory=True,
            detail=str(resolved),
        )
    )

    # Digest verification runs offline: --verify-only never touches the network.
    completed = subprocess.run(  # fixed argv, never a shell
        [
            sys.executable,
            str(SCRIPTS / "fetch_nist_reference.py"),
            "--out",
            str(resolved),
            "--verify-only",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    checks.append(
        Check(
            id="reference-digest-verification",
            title="sha256 of each reference table matches the manifest",
            status=PASSED if completed.returncode == 0 else FAILED,
            mandatory=True,
            detail=(completed.stdout + completed.stderr).strip().replace("\n", " | ")[:400],
        )
    )

    # The test oracle reads one fixed directory. If the user's copy lives somewhere
    # else, the reference-dependent tests cannot see it, and saying so is the honest
    # outcome -- this script will not write the extract into the tree on its behalf.
    oracle_dir = REFERENCE_DIR.resolve()
    visible = resolved == oracle_dir
    checks.append(
        Check(
            id="reference-visible-to-test-oracle",
            title="the reference tables are where the test oracle reads them",
            status=PASSED if visible else FAILED,
            mandatory=True,
            detail=(
                f"{oracle_dir}"
                if visible
                else (
                    f"tests/oracles/nist.py reads {oracle_dir} and nothing else, but the "
                    f"supplied directory is {resolved}. Place or symlink the verified files "
                    f"there yourself and re-run. This script will not put restricted data "
                    f"into the repository tree for you."
                )
            ),
        )
    )
    if not visible:
        not_run.append(
            Check(
                id="reference-property-tests",
                title="library values compared against the NIST reference tables",
                status=NOT_RUN,
                mandatory=False,
                count=0,
                reason="the supplied directory is not the one the test oracle reads",
            )
        )
        return _assemble("external-reference", checks, not_run, TestCounts())

    counts, _ = run_test_suite()
    checks.extend(test_suite_checks(counts, expect_reference_skips=0))
    reproducible, other = discover_cases()
    for case_dir in reproducible:
        if cases == "all" or (cases == "fast" and case_dir.name in FAST_CASES):
            checks.append(reproduce_case(case_dir))
    for case_dir in other:
        completed = subprocess.run(  # fixed argv, never a shell
            [sys.executable, str(case_dir / "run.py"), "--out", str(_fresh_case_dir(case_dir))],
            cwd=REPO_ROOT,
            env=_case_environment(),
            capture_output=True,
            text=True,
            check=False,
        )
        checks.append(
            Check(
                id=f"case-{case_dir.name}",
                title=f"{case_dir.name} runs against the supplied reference tables",
                status=PASSED if completed.returncode == 0 else FAILED,
                mandatory=True,
                detail=f"exit {completed.returncode}; this case has no committed snapshot, "
                f"so the check is that it completes, not that it reproduces one",
            )
        )
    return _assemble("external-reference", checks, not_run, counts)


def _fresh_case_dir(case_dir: pathlib.Path) -> pathlib.Path:
    """Return an unused run directory under artifacts/ for a case with no snapshot."""
    stamp = dt.datetime.now(dt.UTC).strftime("%Y%m%dT%H%M%SZ")
    target = REPO_ROOT / "artifacts" / "verify" / case_dir.name / stamp
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _assemble(
    profile: str,
    checks: list[Check],
    not_run: list[Check],
    counts: TestCounts,
) -> dict[str, Any]:
    """Build the machine-readable report for one profile."""
    mandatory = [c for c in checks if c.mandatory]
    failed = [c for c in mandatory if c.status == FAILED]
    prerequisites_failed = [c for c in checks if not c.mandatory and c.status == FAILED]
    not_run_tests = sum(c.count or 0 for c in not_run if c.id == "reference-property-tests")
    not_run_checks = len([c for c in not_run if c.id != "reference-property-tests"])
    return {
        "profile": profile,
        "status": "fail" if failed else "pass",
        "prerequisites_status": "fail" if prerequisites_failed else "pass",
        "prerequisites_failed": [c.id for c in prerequisites_failed],
        "generated_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "repository": str(REPO_ROOT),
        "totals": {
            "checks_collected": len(checks),
            "checks_passed": len([c for c in checks if c.status == PASSED]),
            "checks_failed": len(failed),
            "tests_collected": counts.collected,
            "tests_passed": counts.passed,
            "tests_failed": counts.failed + counts.errored,
            "tests_skipped": counts.skipped,
            "not_run_tests": not_run_tests,
            "not_run_checks": not_run_checks,
        },
        "tests": asdict(counts),
        "checks": [asdict(c) for c in checks],
        "not_run": [asdict(c) for c in not_run],
        "evidence_class": (
            "self-consistency and reproducibility against this repository's own committed "
            "snapshots, analytic limits and closed forms. Not external validation."
            if profile == "public-core"
            else "comparison against a reference extract the operator supplied and whose "
            "digests match the committed manifest."
        ),
    }


def print_report(report: dict[str, Any]) -> None:
    """Print the report as a console summary a human can read at a glance."""
    profile = report["profile"]
    print("=" * 78)
    print(f"profile: {profile}")
    print(f"python {report['python']} on {report['platform']}")
    print(f"repository {report['repository']}")
    print("=" * 78)

    for check in report["checks"]:
        mark = {PASSED: "pass", FAILED: "FAIL"}.get(check["status"], check["status"])
        required = "mandatory" if check["mandatory"] else "prereq   "
        print(f"[{mark:>4}] {required}  {check['id']}")
        print(f"         {check['title']}")
        if check["detail"]:
            print(f"         {check['detail']}")

    if report["not_run"]:
        print("-" * 78)
        print("NOT RUN in this profile:")
        for item in report["not_run"]:
            count = f"{item['count']} " if item["count"] else ""
            print(f"  - {item['id']} ({count}not run)")
            print(f"    {item['reason']}")

    totals = report["totals"]
    print("-" * 78)
    print(f"{profile}: counts")
    print(
        f"  checks   collected {totals['checks_collected']}, "
        f"passed {totals['checks_passed']}, failed {totals['checks_failed']}"
    )
    print(
        f"  tests    collected {totals['tests_collected']}, "
        f"passed {totals['tests_passed']}, failed {totals['tests_failed']}, "
        f"skipped {totals['tests_skipped']}"
    )
    print(f"  not run  {totals['not_run_tests']} tests, {totals['not_run_checks']} checks")
    print(f"  evidence {report['evidence_class']}")
    print("-" * 78)
    if report["prerequisites_status"] == "fail":
        print(
            "PREREQUISITE FAILING: "
            + ", ".join(report["prerequisites_failed"])
            + ". This does not change the verification verdict below, which is about "
            "whether the numbers are right. It does block the pipeline: CI runs these as "
            "their own job and every verification job depends on it."
        )
    print("PASS" if report["status"] == "pass" else "FAIL")


# ---------------------------------------------------------------------------
# Hook shim
# ---------------------------------------------------------------------------


def run_hook_stage(stage: str) -> int:
    """Run the hooks .pre-commit-config.yaml declares for ``stage``, offline.

    The installed git hooks call ``pre-commit`` when it is available, because that is
    the tool the configuration is written for. This path exists for a checkout where it
    is not installed: the hooks still fire, running the same entries out of the same
    file, so there is one declaration of what a stage does rather than two.
    """
    if shutil.which("pre-commit"):
        return subprocess.call(  # fixed argv, never a shell
            ["pre-commit", "run", "--all-files", "--hook-stage", stage], cwd=REPO_ROOT
        )
    try:
        import yaml
    except ImportError:
        print(
            "neither `pre-commit` nor PyYAML is available, so the hooks declared in "
            f"{PRE_COMMIT_CONFIG.name} cannot be run. Install pre-commit "
            "(pip install pre-commit) and run `pre-commit install --hook-type pre-commit "
            "--hook-type pre-push`. Refusing to pass a stage that did not run.",
            file=sys.stderr,
        )
        return 1

    config = yaml.safe_load(PRE_COMMIT_CONFIG.read_text(encoding="utf-8"))
    default_stages = config.get("default_stages", ["pre-commit"])
    failures, ran = 0, 0
    for repo in config.get("repos", []):
        for hook in repo.get("hooks", []):
            if stage not in hook.get("stages", default_stages):
                continue
            argv = shlex.split(hook["entry"])
            # pre-commit hands a file-taking hook the staged paths. This shim has no
            # staging context, so it gives such a hook the whole tree, which is what CI
            # does anyway. A hook declaring pass_filenames: false takes no paths.
            if hook.get("pass_filenames", True):
                argv.append(".")
            # flush before handing the terminal to a child, or this script's buffered
            # output lands after every hook's output and the log reads back to front.
            print(f"--- {hook['id']}: {hook.get('name', '')}", flush=True)
            try:
                code = subprocess.call(argv, cwd=REPO_ROOT)  # fixed argv, never a shell
            except FileNotFoundError:
                # A missing tool is a failed check, not a crash. Say which tool and how
                # to get it, at the version the lock file pins.
                print(
                    f"{argv[0]!r} is not on PATH. This hook needs it; install the pinned "
                    f"development toolchain with "
                    f"`python3 -m pip install -r requirements-dev.lock`.",
                    file=sys.stderr,
                    flush=True,
                )
                code = 127
            ran += 1
            if code != 0:
                print(f"--- {hook['id']} FAILED (exit {code})", file=sys.stderr, flush=True)
                failures += 1
    if ran == 0:
        print(
            f"no hook is declared for stage {stage!r} in {PRE_COMMIT_CONFIG.name}. "
            f"Treating that as a failure: a hook stage that silently runs nothing is "
            f"indistinguishable from a hook stage that passed.",
            file=sys.stderr,
        )
        return 1
    print(f"--- {ran} hook(s) ran for stage {stage}, {failures} failed")
    return 1 if failures else 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--profile", choices=PROFILES, help="which verification profile to run")
    parser.add_argument(
        "--cases",
        choices=CASE_SELECTIONS,
        default="all",
        help="which synthetic case reproductions to run (default: all)",
    )
    parser.add_argument(
        "--expect-reference-skips",
        type=int,
        default=None,
        help=(
            "fail if the measured reference-dependent skip count differs from this. "
            "A drift alarm for CI, not the source of truth: the measured number is."
        ),
    )
    parser.add_argument(
        "--policy-only",
        action="store_true",
        help="public-core: run only the structural policy checks, no tests and no cases",
    )
    parser.add_argument("--json", type=pathlib.Path, default=None, help="write the report here")
    parser.add_argument(
        "--reference-dir",
        type=pathlib.Path,
        default=None,
        help="external-reference profile: local directory holding the NIST extract",
    )
    parser.add_argument(
        "--access-basis",
        default=None,
        help="external-reference profile: how the operator came to hold that data",
    )
    parser.add_argument(
        "--access-basis-file",
        type=pathlib.Path,
        default=None,
        help="external-reference profile: read the access basis from this file",
    )
    parser.add_argument(
        "--hook-stage",
        choices=("pre-commit", "pre-push"),
        default=None,
        help="run the git hooks declared for this stage instead of a profile",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.hook_stage:
        return run_hook_stage(args.hook_stage)
    if not args.profile:
        parser.error("--profile is required (or use --hook-stage)")

    if args.profile == "public-core":
        report = run_public_core(args.cases, args.expect_reference_skips, args.policy_only)
    else:
        basis = args.access_basis
        if basis is None and args.access_basis_file is not None:
            if not args.access_basis_file.is_file():
                parser.error(f"--access-basis-file {args.access_basis_file} does not exist")
            basis = args.access_basis_file.read_text(encoding="utf-8").strip()
        report = run_external_reference(args.reference_dir, basis, args.cases)

    print_report(report)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"report written to {args.json}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

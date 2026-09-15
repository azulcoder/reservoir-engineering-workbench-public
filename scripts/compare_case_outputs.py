#!/usr/bin/env python3
"""Semantic comparison of two case outputs, for cross-platform portability.

    python3 scripts/compare_case_outputs.py REFERENCE.json CANDIDATE.json
    python3 scripts/compare_case_outputs.py --envelope docs/release/portability_envelope.json A.json B.json

This is NOT the canonical gate. Canonical reproduction is byte identity inside the
pinned environment and is checked with ``diff``; nothing here relaxes that, and this
tool is not used for it.

What this answers is a different question: running the same case implementation on a
different operating system, C library and CPU, did it produce the same *scientific
result*? Bitwise equality is the wrong test for that. Every transcendental function in
libm is permitted a fraction of a unit in the last place, implementations disagree
within that allowance, and a Monte Carlo draw or a Newton iteration turns a one-ULP
disagreement into a last-digit difference in the answer. Demanding identical bytes
across platforms would therefore fail for a reason that has nothing to do with the
reservoir engineering.

So the comparison is split by what the field means rather than by its type alone:

  EXACT      Anything discrete or declarative. Keys, array lengths, strings, booleans,
             integers, units, identifiers, seeds, configuration, thresholds, criterion
             names, criterion PASS/FAIL states, verdicts, enumerations, and the
             null/non-null shape. A difference here is never rounding. It means the two
             runs did different work, and it fails.

  FLOAT      Computed quantities, compared against declared relative and absolute
             tolerances. The tolerance is a portability envelope, not an acceptance
             criterion: it asks whether the published result survived the platform
             change, not whether the engineering is right. Each case still runs its own
             acceptance criteria independently, and those are compared EXACTLY above.

  NEAR ZERO  A quantity whose exact value is zero -- a solver residual, an error against
             an analytic oracle -- cannot be judged by relative difference, because the
             denominator is the noise being measured. 1.1e-16 against 0.0 is a relative
             error of 1.0 and means nothing. These are matched against a declared
             absolute floor instead, and the report states the scale they should be read
             against so the floor can be argued with.

  NON-FINITE NaN and the infinities are compared exactly, including sign. A NaN that
             becomes a number, or an infinity that changes sign, is a structural change.

  DIGEST     A content hash taken over floating-point values. It is an integrity device
             for the canonical environment, where it is compared byte for byte along with
             everything else, and it is meaningless across platforms: a one-ULP difference
             anywhere in the payload changes every bit of the hash, so it can report only
             "something differs", which is what this comparison is already measuring leaf
             by leaf and in far more detail. Excluding it therefore costs no detection
             power -- the leaf comparison is strictly stronger than the digest it replaces
             -- and a path must be declared in the envelope to land here. The count and the
             differing values are still reported, so the digest cannot go quiet.

Nothing is skipped silently. Every leaf lands in exactly one class and every class is
counted in the report, so a field cannot vanish from the comparison by not matching a
rule.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import sys
from dataclasses import dataclass, field
from typing import Any

DEFAULT_ENVELOPE = "docs/release/portability_envelope.json"

EXACT = "exact"
FLOAT = "float"
NEAR_ZERO = "near-zero"
NON_FINITE = "non-finite"
DIGEST = "digest"


@dataclass
class Finding:
    """One field the comparison objects to."""

    kind: str
    path: str
    reference: Any
    candidate: Any
    detail: str

    def render(self) -> str:
        """Return a printable block for this finding."""
        return (
            f"  [{self.kind}] {self.path}\n"
            f"      reference {self.reference!r}\n"
            f"      candidate {self.candidate!r}\n"
            f"      {self.detail}"
        )


@dataclass
class Report:
    """Counts and findings for one comparison."""

    exact_fields: int = 0
    float_fields: int = 0
    near_zero_fields: int = 0
    non_finite_fields: int = 0
    digest_fields: int = 0
    max_abs: float = 0.0
    max_abs_path: str = ""
    max_rel: float = 0.0
    max_rel_path: str = ""
    near_zero_paths: list[tuple[str, float, float]] = field(default_factory=list)
    digests_differing: list[tuple[str, str, str]] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Return True when nothing exceeded its declared envelope."""
        return not self.findings


def load_envelope(path: pathlib.Path | None) -> dict:
    """Read the declared portability envelope, or fall back to the committed one."""
    if path is None:
        path = pathlib.Path(__file__).resolve().parents[1] / DEFAULT_ENVELOPE
    return json.loads(path.read_text(encoding="utf-8"))


def leaf_name(path: str) -> str:
    """Return the final key of a JSON path, without any array index."""
    segment = path.rsplit(".", 1)[-1]
    return re.sub(r"\[\d+\]$", "", segment)


def classify(path: str, envelope: dict) -> tuple[str, dict]:
    """Return the comparison class for a float leaf, and the rule that decided it."""
    name = leaf_name(path)
    for rule in envelope.get("exact_float_fields", []):
        if re.search(rule["match"], name):
            return EXACT, rule
    for rule in envelope.get("zero_valued_fields", []):
        if re.search(rule["match"], name):
            return NEAR_ZERO, rule
    return FLOAT, envelope["default_float"]


def is_declared_digest(path: str, envelope: dict) -> bool:
    """Return True when a path is declared a content hash over floating-point values."""
    return any(
        re.search(rule["match"], leaf_name(path)) for rule in envelope.get("platform_dependent_digests", [])
    )


def is_exact_by_path(path: str, envelope: dict) -> bool:
    """Return True when a path sits inside a subtree declared wholly exact."""
    return any(re.search(rx, path) for rx in envelope.get("exact_subtrees", []))


def walk(node: Any, prefix: str = ""):
    """Yield ``(path, value)`` for every leaf of a JSON document."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from walk(value, f"{prefix}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from walk(value, f"{prefix}[{index}]")
    else:
        yield prefix, node


def compare(reference: Any, candidate: Any, envelope: dict) -> Report:
    """Compare two case outputs and return a structured report."""
    report = Report()
    ref_leaves = dict(walk(reference))
    cand_leaves = dict(walk(candidate))

    for path in sorted(set(ref_leaves) | set(cand_leaves)):
        if path not in cand_leaves:
            report.findings.append(
                Finding(
                    "missing-field",
                    path,
                    ref_leaves[path],
                    None,
                    "present in the reference and absent from the candidate",
                )
            )
            continue
        if path not in ref_leaves:
            report.findings.append(
                Finding(
                    "unexpected-field",
                    path,
                    None,
                    cand_leaves[path],
                    "present in the candidate and absent from the reference",
                )
            )
            continue

        a, b = ref_leaves[path], cand_leaves[path]

        # Structure first. A null that becomes a value is not a rounding difference.
        if (a is None) != (b is None):
            report.findings.append(
                Finding("null-structure", path, a, b, "one side is null and the other is not")
            )
            continue
        if a is None:
            report.exact_fields += 1
            continue

        # bool is a subclass of int; check it first or True compares equal to 1.
        if isinstance(a, bool) or isinstance(b, bool):
            report.exact_fields += 1
            if type(a) is not type(b) or a != b:
                report.findings.append(
                    Finding(
                        "verdict-changed",
                        path,
                        a,
                        b,
                        "a boolean field changed; this is a decision, not arithmetic",
                    )
                )
            continue

        if isinstance(a, str) or isinstance(b, str):
            if is_declared_digest(path, envelope):
                # Declared in the envelope as a hash over floating-point values. It is
                # counted and, when it differs, reported -- but a difference here is not a
                # finding, because every float it covers was just compared individually.
                report.digest_fields += 1
                if a != b:
                    report.digests_differing.append((path, str(a), str(b)))
                continue
            report.exact_fields += 1
            if type(a) is not type(b) or a != b:
                report.findings.append(Finding("string-changed", path, a, b, "a declarative field changed"))
            continue

        if isinstance(a, int) and isinstance(b, int):
            report.exact_fields += 1
            if a != b:
                report.findings.append(
                    Finding(
                        "integer-changed",
                        path,
                        a,
                        b,
                        "an integer field changed; counts and seeds are not rounded",
                    )
                )
            continue

        if not isinstance(a, float) or not isinstance(b, float):
            report.exact_fields += 1
            if type(a) is not type(b) or a != b:
                report.findings.append(
                    Finding("type-changed", path, a, b, f"type {type(a).__name__} became {type(b).__name__}")
                )
            continue

        # From here both sides are floats.
        if math.isnan(a) or math.isnan(b) or math.isinf(a) or math.isinf(b):
            report.non_finite_fields += 1
            same = (math.isnan(a) and math.isnan(b)) or (
                a == b and math.copysign(1.0, a) == math.copysign(1.0, b)
            )
            if not same:
                report.findings.append(
                    Finding(
                        "non-finite-changed",
                        path,
                        a,
                        b,
                        "NaN and infinity are compared exactly, including sign",
                    )
                )
            continue

        if is_exact_by_path(path, envelope):
            report.exact_fields += 1
            if a != b:
                report.findings.append(
                    Finding(
                        "exact-float-changed",
                        path,
                        a,
                        b,
                        "this field is declared exact; it is configuration or a "
                        "threshold, not a computed result",
                    )
                )
            continue

        kind, rule = classify(path, envelope)

        if kind == EXACT:
            report.exact_fields += 1
            if a != b:
                report.findings.append(
                    Finding(
                        "exact-float-changed",
                        path,
                        a,
                        b,
                        f"declared exact by rule {rule['match']!r}: {rule.get('why', '')}",
                    )
                )
            continue

        if kind == NEAR_ZERO:
            report.near_zero_fields += 1
            floor = float(rule["absolute"])
            scale = max(abs(a), abs(b))
            report.near_zero_paths.append((path, scale, floor))
            if scale > floor:
                report.findings.append(
                    Finding(
                        "near-zero-out-of-envelope",
                        path,
                        a,
                        b,
                        f"exact value is zero ({rule.get('why', '')}); |value| reached {scale:.3e}, "
                        f"above the declared absolute floor {floor:.3e}. Compare "
                        f"against {rule.get('scale_note', 'the quantity it is a residual of')}.",
                    )
                )
            continue

        # Ordinary computed float.
        report.float_fields += 1
        if a == b:
            continue
        absolute = abs(a - b)
        scale = max(abs(a), abs(b))
        relative = absolute / scale if scale > 0 else math.inf
        if absolute > report.max_abs:
            report.max_abs, report.max_abs_path = absolute, path
        if relative > report.max_rel:
            report.max_rel, report.max_rel_path = relative, path
        rel_tol = float(rule["relative"])
        abs_tol = float(rule["absolute"])
        if absolute > abs_tol and relative > rel_tol:
            report.findings.append(
                Finding(
                    "outside-envelope",
                    path,
                    a,
                    b,
                    f"relative {relative:.3e} exceeds {rel_tol:.3e} and "
                    f"absolute {absolute:.3e} exceeds {abs_tol:.3e}",
                )
            )
    return report


def render(report: Report, label: str, verbose: bool = False) -> str:
    """Return the human-readable report."""
    lines = [
        f"portability comparison: {label}",
        f"  exact fields      {report.exact_fields}",
        f"  float fields      {report.float_fields}",
        f"  near-zero fields  {report.near_zero_fields}",
        f"  non-finite fields {report.non_finite_fields}",
        f"  digest fields     {report.digest_fields}"
        + (
            f" ({len(report.digests_differing)} differ, as a hash over floats must when any float differs)"
            if report.digests_differing
            else ""
        ),
    ]
    if report.float_fields:
        lines.append(f"  max absolute      {report.max_abs:.6e}   at {report.max_abs_path or '-'}")
        lines.append(f"  max relative      {report.max_rel:.6e}   at {report.max_rel_path or '-'}")
    if report.near_zero_paths and verbose:
        lines.append("  near-zero fields, with the floor each was judged against:")
        for path, scale, floor in report.near_zero_paths:
            lines.append(f"      {path}: |value| <= {scale:.3e}, floor {floor:.3e}")
    if report.findings:
        lines.append("")
        lines.append(f"  {len(report.findings)} field(s) outside the declared envelope:")
        for finding in report.findings:
            lines.append(finding.render())
        lines.append("")
        lines.append("portability: FAIL")
    else:
        lines.append("")
        lines.append("portability: PASS - every field is equal, or inside its declared envelope")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Compare two case outputs and return a process exit status."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("reference", type=pathlib.Path)
    parser.add_argument("candidate", type=pathlib.Path)
    parser.add_argument("--envelope", type=pathlib.Path, default=None)
    parser.add_argument("--label", default=None)
    parser.add_argument("--json", type=pathlib.Path, default=None)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    envelope = load_envelope(args.envelope)
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    label = args.label or f"{args.reference.name} vs {args.candidate.name}"
    report = compare(reference, candidate, envelope)
    print(render(report, label, args.verbose))

    if args.json is not None:
        args.json.write_text(
            json.dumps(
                {
                    "label": label,
                    "ok": report.ok,
                    "exact_fields": report.exact_fields,
                    "float_fields": report.float_fields,
                    "near_zero_fields": report.near_zero_fields,
                    "non_finite_fields": report.non_finite_fields,
                    "max_absolute": report.max_abs,
                    "max_absolute_path": report.max_abs_path,
                    "max_relative": report.max_rel,
                    "max_relative_path": report.max_rel_path,
                    "findings": [
                        {
                            "kind": f.kind,
                            "path": f.path,
                            "reference": f.reference,
                            "candidate": f.candidate,
                            "detail": f.detail,
                        }
                        for f in report.findings
                    ],
                },
                indent=2,
                default=str,
            )
            + "\n",
            encoding="utf-8",
        )
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())

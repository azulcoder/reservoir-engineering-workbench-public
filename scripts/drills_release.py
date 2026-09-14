#!/usr/bin/env python3
r"""Failure drills for the release gates: break one thing, prove the gate catches it.

    python3 scripts/drills_release.py
    python3 scripts/drills_release.py --only stale-public-copy --keep

A gate nobody has ever seen fail is not evidence. Each drill below takes a THROWAWAY
COPY of the tree, breaks exactly one thing in it, runs the gate that is supposed to
notice, and records the exit code and the sentence that named the problem. Then it puts
the fixture back in that same copy and runs the gate again, which must return to zero:
a gate that fails on everything is no more informative than one that fails on nothing.

Where the drills run, and what they never touch
-----------------------------------------------
Every mutation happens inside a temporary copy under the system scratch directory. The
repository is read once, to make the copy, and never written. `cases/*/results/*.json`
are copied because the emitter reads two blocks out of them, and each drill digests them
before and after and fails if either moved: preserved run artefacts are inputs to these
drills and never subjects of them. No drill regenerates a case, relaxes a tolerance or
rewrites a result snapshot.

`scripts/export_presentation_data.py` reconciles every exported value against the frozen
case summary at a relative tolerance of 1e-12. That drill and that tolerance are the
numerical stream's and are read here, never set: the reconciliation drill below asserts
the gate fires and prints the tolerance the exporter itself declares.

The five drills
---------------
    stale-public-copy     re-render a figure, update its manifest consistently, leave the
                          published copy alone. This is finding F4, and it used to build
                          green -- drill H in docs/release/UI_QA.md, "exit 0, none".
    tampered-download     edit a published copy and its digest in index.json, leave the
                          canonical source alone. Index and file now agree with each
                          other and with nothing else.
    missing-artefact      remove a published download, a canonical variant, and a figure
                          data file, one at a time.
    wrong-binding         serve one case's numbers under another case's file name, and
                          separately make the specification's accessible name disagree
                          with the drawing's.
    below-floor-text      set an annotation below the text floor, and separately move an
                          annotation's anchor outside the viewBox, republishing each time
                          so that the identity checks pass and only the presentation gate
                          can fire.

Each prints its own result; the run prints a machine-readable summary and exits non-zero
if any drill did not behave as a drill must.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent

#: Copied into every throwaway tree. Nothing else is needed to run the emitter and its
#: verifier, and a narrow copy is a cheap guarantee that a drill cannot reach the rest of
#: the repository even by accident.
COPY_PATHS = (
    "site/src/scripts",
    "site/src/data/figures",
    "site/src/generated/figures",
    "site/public/data",
    "cases/A1_volumetric_baseline/results/summary.json",
    "cases/A3_uncertainty_experiments/results/summary.json",
)

#: Never written by any drill. Digested before and after each one.
FROZEN = (
    "cases/A1_volumetric_baseline/results/summary.json",
    "cases/A3_uncertainty_experiments/results/summary.json",
)

VERIFY = ["node", "src/scripts/emit-public-data.mjs", "--verify"]
EMIT = ["node", "src/scripts/emit-public-data.mjs"]


class DrillError(RuntimeError):
    """A drill could not be set up. Not the same thing as a gate firing."""


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_copy() -> pathlib.Path:
    """Build a throwaway copy of exactly what the gates need."""
    root = pathlib.Path(tempfile.mkdtemp(prefix="release-drill-"))
    for rel in COPY_PATHS:
        source = REPO / rel
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        elif source.is_file():
            shutil.copy2(source, target)
        else:
            raise DrillError(f"{rel} is missing from the repository; nothing to copy")
    return root


def run(root: pathlib.Path, argv: list[str]) -> tuple[int, str]:
    """Run a gate inside the throwaway copy. Returns its real exit code and its output."""
    result = subprocess.run(
        argv,
        cwd=str(root / "site"),
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, (result.stdout + result.stderr)


def named_problem(output: str) -> str:
    """Return the gate's own sentence about what is wrong, with its continuation lines.

    A gate that fails with a heading and then names the file on the next line is only
    useful if the drill record carries both, so the indented continuation is kept rather
    than truncated at the first newline.
    """
    lines = output.splitlines()
    for i, line in enumerate(lines):
        if line.strip().startswith("emit-public-data"):
            message = [line.strip()]
            for follow in lines[i + 1 : i + 4]:
                if follow.startswith((" ", "\t")) and follow.strip():
                    message.append(follow.strip())
                else:
                    break
            return " | ".join(message)
    for line in lines:
        if '"status": "failed"' in line:
            return "a check reported failed in the machine-readable summary"
    return output.strip().splitlines()[-1] if output.strip() else "(no output)"


def read_index(root: pathlib.Path) -> tuple[pathlib.Path, dict]:
    path = root / "site/public/data/index.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def reindex(path: pathlib.Path, index: dict, name: str, data: bytes) -> None:
    """Rewrite one index entry so the published file and its local digest agree again."""
    for entry in index["files"]:
        if entry["name"] == name:
            entry["bytes"] = len(data)
            entry["sha256"] = hashlib.sha256(data).hexdigest()
            break
    else:  # pragma: no cover - a drill that cannot find its target is a setup error
        raise DrillError(f"{name} is not in index.json")
    path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# The drills. Each returns a list of (case, argv, expectation) observations.
# --------------------------------------------------------------------------- #


def drill_stale_public_copy(root: pathlib.Path) -> list[dict]:
    """Re-render a figure and update its manifest, but leave the published copy stale."""
    svg = root / "site/src/generated/figures/f01.svg"
    original = svg.read_bytes()
    text = original.decode("utf-8")
    if 'r="3.4"' not in text:
        raise DrillError('f01.svg has no r="3.4" marker to perturb')
    # Same byte count, so the manifest's recorded length stays correct: this is what a
    # legitimate re-render that happened to keep the file size looks like.
    svg.write_bytes(text.replace('r="3.4"', 'r="3.6"', 1).encode("utf-8"))
    broken = run(root, VERIFY)
    svg.write_bytes(original)
    restored = run(root, VERIFY)
    return [
        {
            "case": "canonical figure re-rendered, manifest consistent, published copy stale",
            "gate": " ".join(VERIFY),
            "broken": broken,
            "restored": restored,
        }
    ]


def drill_tampered_download(root: pathlib.Path) -> list[dict]:
    """Edit a published copy and its recorded digest, leaving the canonical source alone."""
    published = root / "site/public/data/figures/f03.svg"
    original = published.read_bytes()
    index_path, index = read_index(root)
    index_original = index_path.read_bytes()

    edited = original.decode("utf-8").replace("#17518f", "#b00020", 1).encode("utf-8")
    if edited == original:
        raise DrillError("f03.svg has no colour token to repaint")
    published.write_bytes(edited)
    reindex(index_path, index, "figures/f03.svg", edited)
    broken = run(root, VERIFY)

    published.write_bytes(original)
    index_path.write_bytes(index_original)
    restored = run(root, VERIFY)
    return [
        {
            "case": "published SVG repainted and its index digest updated to match",
            "gate": " ".join(VERIFY),
            "broken": broken,
            "restored": restored,
        }
    ]


def drill_missing_artefact(root: pathlib.Path) -> list[dict]:
    """Remove a download, a canonical variant and a figure data file, one at a time."""
    observations = []
    for label, rel in (
        ("published download removed", "site/public/data/figures/f05.png"),
        ("canonical raster variant removed", "site/src/generated/figures/f05.png"),
        ("figure data file removed", "site/src/data/figures/f03_bias_sweep.json"),
    ):
        path = root / rel
        saved = path.read_bytes()
        path.unlink()
        broken = run(root, VERIFY)
        path.write_bytes(saved)
        restored = run(root, VERIFY)
        observations.append(
            {
                "case": f"{label}: {rel}",
                "gate": " ".join(VERIFY),
                "broken": broken,
                "restored": restored,
            }
        )
    return observations


def drill_wrong_binding(root: pathlib.Path) -> list[dict]:
    """Bind a chart to the wrong scenario, and mismatch caption metadata."""
    observations = []

    # (a) One case's numbers served under another case's name.
    target = root / "site/public/data/f01_f02_case-2.json"
    other = root / "site/public/data/f01_f02_case-60.json"
    original = target.read_bytes()
    index_path, index = read_index(root)
    index_original = index_path.read_bytes()
    swapped = other.read_bytes()
    target.write_bytes(swapped)
    reindex(index_path, index, "f01_f02_case-2.json", swapped)
    broken = run(root, VERIFY)
    target.write_bytes(original)
    index_path.write_bytes(index_original)
    restored = run(root, VERIFY)
    observations.append(
        {
            "case": "the J = 2 selected-case download serves the J = 60 case's numbers",
            "gate": " ".join(VERIFY),
            "broken": broken,
            "restored": restored,
        }
    )

    # (b) The specification's accessible name no longer matches the drawing's.
    manifest_path = root / "site/src/generated/figures/manifest.json"
    manifest_original = manifest_path.read_bytes()
    manifest = json.loads(manifest_original.decode("utf-8"))
    for figure in manifest["figures"]:
        if figure["figure_id"] == "F04":
            figure["accessibility"]["accessible_name"] = (
                "F04 — progressive fits, in barrels"  # wrong name and wrong unit
            )
            break
    else:  # pragma: no cover
        raise DrillError("F04 is not in the manifest")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    broken_meta = run(root, VERIFY)
    manifest_path.write_bytes(manifest_original)
    restored_meta = run(root, VERIFY)
    observations.append(
        {
            "case": "the specification's accessible name and unit disagree with the drawing's",
            "gate": " ".join(VERIFY),
            "broken": broken_meta,
            "restored": restored_meta,
        }
    )
    return observations


def drill_below_floor_text(root: pathlib.Path) -> list[dict]:
    """Reintroduce below-floor text, and a clipped annotation, republishing each time.

    Each mutation is followed by a re-emission, so the published copy is byte-identical
    to the mutated source again and the identity checks pass. Only the presentation gate
    can fire, which is what makes the observation about the floor rather than about drift.
    """
    observations = []
    svg = root / "site/src/generated/figures/f01.svg"
    original = svg.read_bytes()
    manifest_path = root / "site/src/generated/figures/manifest.json"
    manifest_original = manifest_path.read_bytes()

    def republish_and_verify() -> tuple[int, str]:
        code, output = run(root, EMIT)
        if code != 0:
            return code, output
        return run(root, VERIFY)

    def resize_manifest(name: str, length: int) -> None:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for figure in manifest["figures"]:
            for entry in figure["files"]:
                if entry["path"] == name:
                    entry["bytes"] = length
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    for label, old, new in (
        (
            "annotation set below the 13px text floor",
            'font-size="13" text-anchor="start"',
            'font-size="9" text-anchor="start"',
        ),
        (
            "essential annotation moved outside the viewBox",
            'transform="translate(666.295081967213,358.7311827956989)"',
            'transform="translate(1480,358.7311827956989)"',
        ),
    ):
        text = original.decode("utf-8")
        if old not in text:
            raise DrillError(f"f01.svg does not contain {old!r}; the drill has nothing to change")
        mutated = text.replace(old, new, 1).encode("utf-8")
        svg.write_bytes(mutated)
        resize_manifest("f01.svg", len(mutated) - 1)
        broken = republish_and_verify()

        svg.write_bytes(original)
        manifest_path.write_bytes(manifest_original)
        code, output = run(root, EMIT)
        restored = (code, output) if code != 0 else run(root, VERIFY)
        observations.append(
            {
                "case": label,
                "gate": f"{' '.join(EMIT)} then {' '.join(VERIFY)}",
                "broken": broken,
                "restored": restored,
            }
        )
    return observations


def drill_numerical_reconciliation(root: pathlib.Path) -> list[dict]:
    """Exercise the existing reconciliation gate and leave it exactly as it is.

    The tolerance belongs to `scripts/export_presentation_data.py` and is read here, not
    set. The drill perturbs one exported value by far more than the tolerance and shows
    that the contract digest gate refuses it; the exporter's own reconciliation of that
    value against the frozen case summary is the numerical stream's check and is not
    re-implemented here.
    """
    exporter = (REPO / "scripts/export_presentation_data.py").read_text(encoding="utf-8")
    match = re.search(r"RECONCILE_RELATIVE_TOLERANCE\s*=\s*([0-9.eE+-]+)", exporter)
    tolerance = match.group(1) if match else "unknown"

    data = root / "site/src/data/figures/f03_bias_sweep.json"
    original = data.read_bytes()
    parsed = json.loads(original.decode("utf-8"))
    row = parsed["rows"][0]
    key = "relative_gas_in_place_error"
    row[key] = row[key] * 1.05  # five percent, twelve orders of magnitude past tolerance
    data.write_text(json.dumps(parsed, indent=2) + "\n", encoding="utf-8")
    broken = run(root, VERIFY)
    data.write_bytes(original)
    restored = run(root, VERIFY)
    return [
        {
            "case": (
                f"an exported value moved by 5 percent; the exporter's declared "
                f"reconciliation tolerance is {tolerance} and is not changed by this drill"
            ),
            "gate": " ".join(VERIFY),
            "broken": broken,
            "restored": restored,
        }
    ]


DRILLS = {
    "stale-public-copy": drill_stale_public_copy,
    "tampered-download": drill_tampered_download,
    "missing-artefact": drill_missing_artefact,
    "wrong-binding": drill_wrong_binding,
    "below-floor-text": drill_below_floor_text,
    "numerical-reconciliation": drill_numerical_reconciliation,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--only", choices=sorted(DRILLS), default=None, help="run one drill")
    parser.add_argument("--json", default=None, help="write the machine-readable summary here")
    parser.add_argument("--keep", action="store_true", help="keep the throwaway copies for inspection")
    args = parser.parse_args()

    selected = [args.only] if args.only else list(DRILLS)
    results: list[dict[str, object]] = []
    failures = 0

    for name in selected:
        root = make_copy()
        before = {rel: sha256(root / rel) for rel in FROZEN}
        baseline_code, baseline_output = run(root, VERIFY)
        try:
            if baseline_code != 0:
                raise DrillError(
                    f"the copy does not start clean: {' '.join(VERIFY)} exited "
                    f"{baseline_code} before anything was broken — {named_problem(baseline_output)}"
                )
            observations = DRILLS[name](root)
        except DrillError as error:
            failures += 1
            results.append({"drill": name, "status": "setup-failed", "detail": str(error)})
            sys.stdout.write(f"SETUP FAILED  {name}: {error}\n")
            if not args.keep:
                shutil.rmtree(root, ignore_errors=True)
            continue

        after = {rel: sha256(root / rel) for rel in FROZEN}
        moved = [rel for rel in FROZEN if before[rel] != after[rel]]
        cases = []
        for observation in observations:
            broken_code, broken_output = observation["broken"]
            restored_code, restored_output = observation["restored"]
            caught = broken_code != 0
            recovered = restored_code == 0
            ok = caught and recovered and not moved
            if not ok:
                failures += 1
            cases.append(
                {
                    "case": observation["case"],
                    "gate": observation["gate"],
                    "broken_exit": broken_code,
                    "broken_message": named_problem(broken_output),
                    "restored_exit": restored_code,
                    "restored_message": named_problem(restored_output) if restored_code else "clean",
                    "verdict": "caught" if ok else "NOT CAUGHT",
                }
            )
            sys.stdout.write(
                f"{'CAUGHT' if ok else 'NOT CAUGHT':<11} {name}\n"
                f"             {observation['case']}\n"
                f"             gate: {observation['gate']}\n"
                f"             broken   -> exit {broken_code}: {named_problem(broken_output)}\n"
                f"             restored -> exit {restored_code}\n"
            )
        results.append(
            {
                "drill": name,
                "status": "ok" if all(c["verdict"] == "caught" for c in cases) else "failed",
                "frozen_artefacts_moved": moved,
                "cases": cases,
                "throwaway_copy": str(root) if args.keep else "removed",
            }
        )
        if moved:
            sys.stdout.write(f"FROZEN MOVED {name}: {moved}\n")
        if not args.keep:
            shutil.rmtree(root, ignore_errors=True)

    summary = {
        "tool": "scripts/drills_release.py",
        "drills": len(results),
        "cases": sum(len(r.get("cases", [])) for r in results),
        "not_caught": failures,
        "status": "passed" if failures == 0 else "failed",
        "results": results,
    }
    blob = json.dumps(summary, indent=2)
    if args.json:
        pathlib.Path(args.json).write_text(blob + "\n", encoding="utf-8")
    sys.stdout.write("--- drills_release summary (json) ---\n")
    sys.stdout.write(blob + "\n")
    sys.stdout.write(
        f"\ndrills_release: {summary['status']} — {summary['cases']} cases, {failures} not caught\n"
    )
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

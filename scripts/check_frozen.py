#!/usr/bin/env python3
"""Confirm the frozen scientific artefacts are byte-identical to a recorded baseline.

Presentation work regenerates figures and downloads. It must never touch a historical run
record, a case summary, or the exported figure data those summaries were reconciled against.
This compares the current bytes with a snapshot taken before the work started and exits
non-zero on any difference, naming the file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

PATTERNS = ("cases/*/results/*.json", "site/src/data/figures/*.json")


def digests(root: pathlib.Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for pattern in PATTERNS:
        for path in sorted(root.glob(pattern)):
            out[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--baseline", required=True, help="JSON snapshot to compare against")
    parser.add_argument("--write", action="store_true", help="write the snapshot instead of checking")
    parser.add_argument("--root", default=".", help="repository root")
    args = parser.parse_args(argv)

    root = pathlib.Path(args.root).resolve()
    current = digests(root)
    baseline_path = pathlib.Path(args.baseline)

    if args.write:
        baseline_path.write_text(json.dumps(current, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {len(current)} digests to {baseline_path}")
        return 0

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    problems = []
    for name, digest in baseline.items():
        if name not in current:
            problems.append(f"MISSING  {name}")
        elif current[name] != digest:
            problems.append(f"CHANGED  {name}\n         was {digest}\n         now {current[name]}")
    for name in current:
        if name not in baseline:
            problems.append(f"NEW      {name} (not in the frozen baseline)")

    for line in problems:
        print(line, file=sys.stderr)
    print(f"frozen artefacts: {len(baseline)} checked, {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())

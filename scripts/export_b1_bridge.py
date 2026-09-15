#!/usr/bin/env python3
"""Export case B1 as a plain pressure-versus-time table for an external well-test package.

This exists so that the comparison described in ``docs/bridges/saphir_b1_manual_validation.md``
can actually be carried out by someone who has such a package. It reads the audited run
snapshot in ``cases/B1_iarf_known_answer/results/summary.json`` and writes CSV. It does not
recompute anything, so the exported numbers are the numbers the case reports.

Running this script produces an input file. It does not produce a validation, and nothing
in this repository may cite its output as one.
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

SUMMARY = pathlib.Path("cases/B1_iarf_known_answer/results/summary.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="docs/bridges/b1_pressure_history.csv",
        help="destination CSV path",
    )
    args = parser.parse_args(argv)

    if not SUMMARY.exists():
        print(f"missing {SUMMARY}", file=sys.stderr)
        return 1
    summary = json.loads(SUMMARY.read_text())
    baseline = summary["b1_0_mathematical_baseline"]
    series = baseline["series"]
    truth = summary["config"]["truth"]

    destination = pathlib.Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="") as handle:
        writer = csv.writer(handle)
        # A leading comment block, because an import that loses the well and fluid
        # properties cannot be interpreted and would silently be interpreted anyway.
        writer.writerow([f"# case B1, drawdown, constant rate {truth['rate_stb_per_day']} STB/D"])
        writer.writerow([f"# initial pressure {truth['initial_pressure_psia']} psia"])
        writer.writerow(
            [
                f"# h={truth['thickness_ft']} ft, phi={truth['porosity']},"
                f" ct={truth['total_compressibility_per_psi']} 1/psi,"
                f" mu={truth['viscosity_cp']} cp, B={truth['formation_volume_factor']} rb/STB,"
                f" rw={truth['wellbore_radius_ft']} ft"
            ]
        )
        writer.writerow(["# wellbore storage is zero by design; there is no storage period to fit"])
        writer.writerow([f"# withheld answer: k={truth['permeability_md']} md, s={truth['skin']}"])
        writer.writerow([f"# source run metrics_sha256 {summary['metrics_sha256']}"])
        writer.writerow(["elapsed_hours", "pressure_psia", "drawdown_psi"])
        initial = truth["initial_pressure_psia"]
        for hours, drop in zip(series["time_hours"], series["drawdown_psi"], strict=True):
            writer.writerow([repr(hours), repr(initial - drop), repr(drop)])

    print(f"wrote {destination} ({len(series['time_hours'])} points)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

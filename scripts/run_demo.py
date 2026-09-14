"""Generate and analyse a labelled, idealized synthetic volumetric-gas dataset.

Run: python scripts/run_demo.py --out artifacts/demo
No downloads, external packages, external executables, or simulator runs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import random
import subprocess
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from reservoir_lab.gas import fit_volumetric_pz  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(out: Path) -> dict:
    config_path = ROOT / "configs/synthetic_volumetric_gas.json"
    config = json.loads(config_path.read_text())
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError("Output directory must be empty; preserve existing runs or choose a new path")
    rng = random.Random(config["seed"])
    giip = config["true_giip_sm3"]
    pi, zi = config["initial_pressure_pa"], config["initial_z"]
    gp, p, zz = [], [], []
    for f in config["recovery_fractions"]:
        z = zi + 0.06 * f  # Deliberately illustrative, NOT a validated PVT model.
        noise = 0.0 if f == 0 else rng.gauss(0, config["pressure_noise_sd_pa"])
        gp.append(giip * f)
        p.append((pi / zi) * (1 - f) * z + noise)
        zz.append(z)
    cut = config["training_observations"]
    fit = fit_volumetric_pz(gp[:cut], p[:cut], zz[:cut])
    holdout_errors = [fit.predict_p_over_z(gp[i]) * zz[i] - p[i] for i in range(cut, len(gp))]
    rmse = math.sqrt(math.fsum(e * e for e in holdout_errors) / len(holdout_errors))
    relative_giip_error = abs(fit.giip_sm3 / giip - 1)
    summary = {
        "case_type": "synthetic_self_consistency_demo",
        "model": "volumetric_isothermal_gas",
        "fit": asdict(fit),
        "known_synthetic_giip_sm3": giip,
        "relative_giip_error": relative_giip_error,
        "holdout_pressure_rmse_pa": rmse,
        "holdout_pressure_rmse_fraction_initial_pressure": rmse / pi,
        "training_observations": cut,
        "holdout_observations": len(gp) - cut,
        "passes_demo_gates": relative_giip_error < config["max_relative_giip_error"]
        and rmse / pi < config["max_holdout_rmse_fraction_initial_pressure"],
        "limitations": [
            "Synthetic generator and inverse model share the same physical assumptions.",
            "Successful recovery is verification/self-consistency, not validation against field data.",
            "Toy Z values are not measured or EOS-calibrated PVT.",
            "No aquifer, condensate, compaction, transient forward model, or simulator execution.",
            "Known future Z values are supplied; the holdout is a conditional pressure "
            "check, not a standalone forecast.",
        ],
    }
    csv_path = out / "observations.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["observation", "split", "cumulative_gas_sm3", "average_pressure_pa_absolute", "z_dimensionless"]
        )
        for i, (a, b, c) in enumerate(zip(gp, p, zz, strict=True)):
            w.writerow(
                [
                    i,
                    "training" if i < cut else "holdout",
                    format(a, ".16g"),
                    format(b, ".16g"),
                    format(c, ".16g"),
                ]
            )
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True, timeout=5
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            ).stdout.strip()
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        commit, dirty = None, None
    record = {
        "run_utc": datetime.now(UTC).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "git_commit": commit,
        "working_tree_dirty": dirty,
        "config_sha256": sha256(config_path),
        "seed": config["seed"],
        "source_hashes": {
            str(p.relative_to(ROOT)): sha256(p)
            for p in [ROOT / "src/reservoir_lab/gas.py", ROOT / "scripts/run_demo.py"]
        },
        "output_hashes": {p.name: sha256(p) for p in [csv_path, out / "summary.json"]},
        "standard_conditions": config["standard_conditions"],
        "data_origin": "generated locally; no field measurements or third-party raw data",
    }
    (out / "run_manifest.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    report = f"""# Synthetic volumetric-gas check

This run is a verification demonstration, not a field interpretation.

The first {cut} pressure observations were used for OLS fitting; the last {len(gp) - cut}
were held out. Holdout pressures are conditional on supplied synthetic Z values.

| Quantity | Result |
|---|---:|
| Known synthetic GIIP | {giip:,.0f} standard m3 |
| Fitted GIIP | {fit.giip_sm3:,.0f} standard m3 |
| Absolute relative GIIP error | {relative_giip_error:.4%} |
| Holdout pressure RMSE | {rmse:,.1f} Pa |
| Holdout RMSE / initial pressure | {rmse / pi:.4%} |
| Predefined demonstration gates | {"PASS" if summary["passes_demo_gates"] else "FAIL"} |

## Interpretation

Agreement shows that this implementation recovers a known volumetric-gas relationship
with the stated small measurement perturbation. It does not establish that a real field
has constant gas pore volume, no water influx, or representative pressure measurements.
A high R-squared cannot establish these assumptions. Next test a mechanistically distinct
forward model and quantify sensitivity to pressure selection and fluid-property error.

## Boundaries

No reserve classification, operational drawdown limit, commercial simulator proficiency,
or validated production forecast is established by this run. The source code, configuration,
checksums and runtime information are recorded in `run_manifest.json`.
"""
    (out / "report.md").write_text(report)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/demo")
    args = parser.parse_args()
    try:
        result = run(args.out)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passes_demo_gates"] else 1)

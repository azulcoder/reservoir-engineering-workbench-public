#!/usr/bin/env python3
"""Export the presentation data the website renders, from the audited case code.

Why this exists
---------------
The committed case summary is a *summary*. It carries every aggregate the case report
quotes, but it stores only nine sampled rows of the residual table and no full
observation trace, because the case was written to be read, not plotted. A website that
needs 49 points cannot get them from the summary, and inventing them -- by splining a
printed table, or by re-deriving them from a fitted line -- would put numbers on a chart
that no run produced.

So this exporter imports the case module itself and calls the same functions the audited
run called: ``simulate``, ``observed`` and ``fit_pz_depletion``. It is not a second
implementation of the physics, and it contains no reservoir equation of its own.

Because it is nonetheless a separate execution, it does two things before it writes
anything:

* it **reconciles** every quantity it recomputes against the corresponding value in the
  audited summary, and fails closed on any disagreement;
* it records itself as a **new run** with its own run record, rather than presenting its
  output as part of the original case run.

What it does not do
-------------------
It does not modify, overwrite or re-date any existing run, summary or record. It does not
read the NIST reference extract and does not depend on it.

Usage
-----
    PYTHONPATH=src python3 scripts/export_presentation_data.py --out artifacts/export/run-001
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

CASE_DIR = REPO_ROOT / "cases" / "A4_misleading_fit_counterexample"
BASELINE_SUMMARY = CASE_DIR / "results" / "summary.json"

#: Where the site reads its figure data from.
SITE_DATA_DIR = REPO_ROOT / "site" / "src" / "data" / "figures"

CONTRACT_VERSION = "1.0.0"

#: Same-environment determinism target. The exporter and the audited run execute the same
#: code on the same interpreter, so agreement is expected to be exact; a tolerance is
#: declared anyway so that a cross-platform run reports a quantified disagreement instead
#: of an unexplained failure. Declared BEFORE the comparison is evaluated.
RECONCILE_RELATIVE_TOLERANCE = 1.0e-12

from reservoir_lab.provenance import RunRecord, sha256_file  # noqa: E402


class ReconciliationError(RuntimeError):
    """A recomputed quantity disagrees with the audited baseline."""


def load_case_module() -> Any:
    """Import the A4 case runner as a module, without executing its ``main``."""
    spec = importlib.util.spec_from_file_location("a4_case", CASE_DIR / "run.py")
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot import the case module at {CASE_DIR / 'run.py'}")
    module = importlib.util.module_from_spec(spec)
    # Register before executing: @dataclass resolves a class's own module through
    # sys.modules while the class body is being processed, and a module that is not
    # there yet makes that lookup fail.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def finite(value: float, where: str) -> float:
    """Return ``value``, refusing NaN and infinity.

    JSON has no NaN or Infinity. A serialiser that emits them produces a file that some
    parsers reject and others silently turn into ``null``, and a chart that silently drops
    a point is worse than a build that stops.
    """
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"non-finite value at {where}: {value!r}")
    return out


def series(values: Any, where: str) -> list[float]:
    """Materialise a numeric series, checking every element."""
    return [finite(v, f"{where}[{i}]") for i, v in enumerate(values)]


def reconcile(name: str, recomputed: float, baseline: float) -> None:
    """Fail closed unless a recomputed value matches the audited baseline."""
    if recomputed == baseline:
        return
    scale = max(abs(baseline), 1.0)
    relative = abs(recomputed - baseline) / scale
    if relative > RECONCILE_RELATIVE_TOLERANCE:
        raise ReconciliationError(
            f"{name}: exporter computed {recomputed!r}, audited baseline holds "
            f"{baseline!r}, relative difference {relative:.3e} exceeds the declared "
            f"tolerance {RECONCILE_RELATIVE_TOLERANCE:.1e}. The exporter does not publish "
            f"a figure it cannot trace to the audited run."
        )


def build_scenarios(case: Any, baseline: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Regenerate every computed aquifer case and export its full observation trace."""
    sweep = {row["productivity_index_bbl_per_day_psi"]: row for row in baseline["strength_sweep"]}
    scenarios = []
    checks = 0

    for productivity_index in case.PRODUCTIVITY_INDICES:
        history = case.simulate(productivity_index)
        cumulative, p_over_z, z_factors, pressures = case.observed(history)
        fit = case.fit_pz_depletion(cumulative, p_over_z)

        row = sweep[productivity_index]
        # Reconcile against the audited summary before anything is exported.
        reconcile(
            f"J={productivity_index} fitted_gas_in_place_scf",
            fit.gas_in_place_scf,
            row["fitted_gas_in_place_scf"],
        )
        reconcile(f"J={productivity_index} r_squared", fit.r_squared, row["r_squared"])
        reconcile(
            f"J={productivity_index} relative_gas_in_place_error",
            fit.gas_in_place_scf / case.GAS_IN_PLACE_SCF - 1.0,
            row["relative_gas_in_place_error"],
        )
        reconcile(
            f"J={productivity_index} terminal_pressure_psia",
            history.true_pressures_psia[-1],
            row["terminal_pressure_psia"],
        )
        reconcile(
            f"J={productivity_index} invaded_pore_volume_fraction",
            case.invaded_fraction(history),
            row["invaded_pore_volume_fraction"],
        )
        checks += 5

        # The declared constant must agree with what the fit and the reported relative
        # error imply. This is the check the old downstream division performed implicitly;
        # doing it here keeps it, and keeps it at full precision rather than after the
        # value has been rounded for display.
        reconcile(
            f"J={productivity_index} true gas in place",
            case.GAS_IN_PLACE_SCF,
            fit.gas_in_place_scf / (1.0 + row["relative_gas_in_place_error"]),
        )
        checks += 1

        fitted = [fit.intercept + fit.slope * g for g in cumulative]
        residuals = [observed_value - f for observed_value, f in zip(p_over_z, fitted, strict=True)]
        step_days = case.HORIZON_DAYS / case.BASE_STEPS
        times_days = [i * case.OBSERVATION_STRIDE * step_days for i in range(len(cumulative))]

        scenarios.append(
            {
                "productivity_index_bbl_per_day_psi": finite(productivity_index, "J"),
                "label": "volumetric control (no aquifer)"
                if productivity_index == 0.0
                else f"J = {productivity_index:g} bbl/day/psi",
                "is_base_case": productivity_index == case.BASE_PRODUCTIVITY_INDEX,
                "is_volumetric_control": productivity_index == 0.0,
                "n_observations": len(cumulative),
                "times_days": series(times_days, "times_days"),
                "times_years": series([t / 365.25 for t in times_days], "times_years"),
                "cumulative_gas_scf": series(cumulative, "cumulative_gas_scf"),
                "cumulative_gas_bscf": series([g / 1.0e9 for g in cumulative], "cumulative_gas_bscf"),
                # The case's declared true gas in place, carried through rather than left
                # to be reconstructed downstream. The site used to recover it by dividing
                # the fitted volume by one plus the relative error, which is algebraically
                # right and numerically lossy: on one platform that division returned
                # 100000000000.0 and on another 99999999999.99884, a relative difference of
                # 1.2e-14. Three of the forty-nine production fractions are exact ties at
                # four decimals -- 0.20625, 0.34375, 0.48125 -- so that last-place wobble
                # decided which way the tie rounded and moved a published digit. The
                # declared constant is identical on every platform and ends that.
                "true_gas_in_place_scf": finite(case.GAS_IN_PLACE_SCF, "true gas in place"),
                "p_over_z_psia": series(p_over_z, "p_over_z_psia"),
                "pressure_psia": series(pressures, "pressure_psia"),
                "z_factor": series(z_factors, "z_factor"),
                "fitted_p_over_z_psia": series(fitted, "fitted_p_over_z_psia"),
                "residual_p_over_z_psia": series(residuals, "residual_p_over_z_psia"),
                "fit": {
                    "intercept_psia": finite(fit.intercept, "intercept"),
                    "slope_psia_per_scf": finite(fit.slope, "slope"),
                    "gas_in_place_scf": finite(fit.gas_in_place_scf, "fitted G"),
                    "gas_in_place_bscf": finite(fit.gas_in_place_scf / 1.0e9, "fitted G bscf"),
                    "gas_in_place_stderr_scf": finite(fit.gas_in_place_stderr_scf, "stderr"),
                    "r_squared": finite(fit.r_squared, "r_squared"),
                    "n_points": fit.n_points,
                    "depletion_fraction_observed": finite(
                        fit.depletion_fraction_observed, "depletion_fraction"
                    ),
                },
                "observed_extent_bscf": finite(cumulative[-1] / 1.0e9, "observed extent"),
                "relative_gas_in_place_error": finite(row["relative_gas_in_place_error"], "relative error"),
                "relative_remaining_gas_error": finite(
                    row["relative_remaining_gas_error"], "remaining error"
                ),
                "bias_over_stderr": finite(row["bias_over_stderr"], "bias/stderr"),
                "invaded_pore_volume_fraction": finite(
                    row["invaded_pore_volume_fraction"], "invaded fraction"
                ),
                "terminal_pressure_psia": finite(row["terminal_pressure_psia"], "terminal p"),
                "max_solver_residual_p_over_z_psia": finite(
                    row["max_solver_residual_p_over_z_psia"], "solver residual"
                ),
            }
        )
    return {"scenarios": scenarios}, checks


def build_holdout(case: Any, baseline: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Export the holdout split and its conditional pressure reconstruction."""
    recorded = baseline["holdout"]
    history = case.simulate(case.BASE_PRODUCTIVITY_INDEX)
    cumulative, p_over_z, z_factors, pressures = case.observed(history)
    points = len(cumulative)
    count = round(case.HOLDOUT_CALIBRATION_FRACTION * (points - 1)) + 1
    fit = case.fit_pz_depletion(cumulative[:count], p_over_z[:count])

    reconcile("holdout calibration_points", float(count), float(recorded["calibration_points"]))
    reconcile(
        "holdout calibration_relative_gas_in_place_error",
        fit.gas_in_place_scf / case.GAS_IN_PLACE_SCF - 1.0,
        recorded["calibration_relative_gas_in_place_error"],
    )
    reconcile("holdout calibration_r_squared", fit.r_squared, recorded["calibration_r_squared"])

    predicted = [fit.intercept + fit.slope * cumulative[i] for i in range(count, points)]
    # The pressure reconstruction multiplies the predicted p/Z by the deviation factor of
    # the held-out state -- a synthetic quantity from the future of the record. It is a
    # conditional reconstruction, not a self-contained forecast, and the exported field
    # name says so.
    reconstructed_pressure = [
        pred * z_factors[i] for pred, i in zip(predicted, range(count, points), strict=True)
    ]
    pressure_errors = [
        rec - pressures[i] for rec, i in zip(reconstructed_pressure, range(count, points), strict=True)
    ]
    held = len(pressure_errors)
    rmse_pressure = math.sqrt(math.fsum(e * e for e in pressure_errors) / held)
    reconcile("holdout rmse_pressure_psia", rmse_pressure, recorded["holdout_rmse_pressure_psia"])

    step_days = case.HORIZON_DAYS / case.BASE_STEPS
    times_years = [i * case.OBSERVATION_STRIDE * step_days / 365.25 for i in range(points)]

    return (
        {
            "calibration_points": count,
            "holdout_points": held,
            "split_index": count,
            "split_cumulative_gas_bscf": finite(cumulative[count - 1] / 1.0e9, "split"),
            "times_years": series(times_years, "holdout times"),
            "cumulative_gas_bscf": series([g / 1.0e9 for g in cumulative], "holdout cumulative"),
            "observed_p_over_z_psia": series(p_over_z, "holdout observed"),
            "fitted_p_over_z_psia": series(
                [fit.intercept + fit.slope * g for g in cumulative], "holdout fitted"
            ),
            "observed_pressure_psia": series(pressures, "holdout observed pressure"),
            "reconstructed_pressure_psia_conditional": [None] * count
            + series(reconstructed_pressure, "reconstructed pressure"),
            "future_synthetic_z_used": [None] * count
            + series([z_factors[i] for i in range(count, points)], "future z"),
            "metrics": {
                "calibration_relative_gas_in_place_error": finite(
                    recorded["calibration_relative_gas_in_place_error"], "cal G error"
                ),
                "calibration_r_squared": finite(recorded["calibration_r_squared"], "cal r2"),
                "holdout_rmse_pressure_psia": finite(rmse_pressure, "rmse"),
                "holdout_rmse_fraction_of_initial_pressure": finite(
                    recorded["holdout_rmse_fraction_of_initial_pressure"], "rmse fraction"
                ),
                "initial_pressure_psia_denominator": finite(case.INITIAL_PRESSURE_PSIA, "denominator"),
                "borrowed_demonstration_gate": finite(recorded["plan_section_12_holdout_gate"], "gate"),
            },
        },
        3,
    )


def passthrough(baseline: dict[str, Any]) -> dict[str, Any]:
    """Figures whose data the audited summary already carries in full."""
    detect = baseline["residuals_and_detectability"]
    post = baseline["post_review_sensitivities"]
    return {
        "f03_bias_sweep": {
            "source_pointer": "/strength_sweep",
            "rows": baseline["strength_sweep"],
            "note": "Only the aquifer productivity index was varied. The invaded pore-volume "
            "fraction on the horizontal axis is a model output of this generator, not an "
            "independent field observation.",
        },
        "f04_progressive": {
            "source_pointer": "/progressive_fits",
            "rows": baseline["progressive_fits"],
            "x_axis": "requested fraction of history",
            "note": "Prefix fits share observations and are not independent samples. The axis "
            "is the requested fraction; the realised point count is reported per row.",
        },
        "f06_detection": {
            "original": {
                "source_pointer": "/residuals_and_detectability/noise_sweep",
                "rows": detect["noise_sweep"],
                "replicates": baseline["config"]["noise_replicates"] if "config" in baseline else 400,
                "seed_note": "One seed, reset identically at every sigma.",
            },
            "post_review_power_curve": {
                "source_pointer": "/post_review_sensitivities/power_curve",
                "rows": post["power_curve"]["levels"],
                "replicates": post["power_curve"].get("replicates_per_level"),
                "note": "A separate post-review experiment with its own replicate count and "
                "seed. It is not spliced into the original sweep.",
            },
        },
        "f07_z_mismatch": {
            "source_pointer": "/post_review_sensitivities/z_correlation_sensitivity",
            "values": post["z_correlation_sensitivity"],
            "critical_t": detect["critical_t"],
            "note": "Signed statistics are kept signed. Rejecting the straight-line model "
            "does not uniquely identify aquifer support.",
        },
        "f08_refinement": {
            "source_pointer": "/timestep_refinement",
            "J_2": baseline["timestep_refinement"]["J_2"],
            "J_60": baseline["timestep_refinement"]["J_60"],
            "note": "The finest computation is a numerical comparator, not an exact solution.",
        },
    }


def repo_relative(path: Path) -> Path:
    """Express a path relative to the repository root when it lies inside it.

    A run record that stamps an absolute path writes the author's home-directory layout
    into a file meant to be published, and the commit hash is the identity that matters
    anyway. The case runners already do this; the exporter was recording absolute paths
    and the public-release gate caught it.
    """
    try:
        return path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return path


def write_json(path: Path, payload: Any) -> str:
    """Write UTF-8 JSON with no NaN or Infinity, and return its digest."""
    text = json.dumps(payload, indent=2, allow_nan=False, sort_keys=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="fresh, empty run directory")
    parser.add_argument(
        "--site-data",
        default=str(SITE_DATA_DIR),
        help="directory the site reads figure data from",
    )
    arguments = parser.parse_args(argv)

    if not BASELINE_SUMMARY.is_file():
        print(f"baseline summary not found: {BASELINE_SUMMARY}", file=sys.stderr)
        return 2
    baseline = json.loads(BASELINE_SUMMARY.read_text(encoding="utf-8"))
    baseline_digest = sha256_file(BASELINE_SUMMARY)

    case = load_case_module()
    site_data = Path(arguments.site_data)

    with RunRecord.open(
        arguments.out,
        label="A4 presentation export",
        config={
            "exports_for": "A4_misleading_fit_counterexample",
            "contract_version": CONTRACT_VERSION,
            "baseline_summary_sha256": baseline_digest,
            "reconcile_relative_tolerance": RECONCILE_RELATIVE_TOLERANCE,
            "productivity_indices": list(case.PRODUCTIVITY_INDICES),
        },
        seed=case.NOISE_SEED,
        repo_root=".",
    ) as run:
        run.add_input(repo_relative(BASELINE_SUMMARY), role="baseline-summary")
        run.add_input(repo_relative(CASE_DIR / "run.py"), role="case-source")
        run.add_input(repo_relative(CASE_DIR / "protocol.md"), role="protocol")

        scenarios, scenario_checks = build_scenarios(case, baseline)
        holdout, holdout_checks = build_holdout(case, baseline)
        rest = passthrough(baseline)

        figures: dict[str, Any] = {
            "f01_f02_scenarios": scenarios,
            "f05_holdout": holdout,
            **rest,
        }

        digests = {}
        for name, payload in figures.items():
            digests[name] = write_json(site_data / f"{name}.json", payload)

        contract = {
            "contract_version": CONTRACT_VERSION,
            "case_id": "A4_misleading_fit_counterexample",
            "numerical_source": {
                "baseline_summary_path": str(BASELINE_SUMMARY.relative_to(REPO_ROOT)),
                "baseline_summary_sha256": baseline_digest,
                "case_source_sha256": sha256_file(CASE_DIR / "run.py"),
                "protocol_sha256": sha256_file(CASE_DIR / "protocol.md"),
            },
            "export": {
                "exporter_path": "scripts/export_presentation_data.py",
                "exporter_sha256": sha256_file(Path(__file__)),
                "reconciliation_checks_passed": scenario_checks + holdout_checks,
                "reconcile_relative_tolerance": RECONCILE_RELATIVE_TOLERANCE,
            },
            "units": {
                "pressure": "psia (absolute)",
                "p_over_z": "psia",
                "cumulative_gas": "scf, also reported as Bscf = 1e9 scf",
                "time": "days, also reported as years of 365.25 days",
                "standard_conditions": case.STANDARD.describe(),
            },
            "evidence_class": "synthetic; generator and estimator are separate modules; "
            "known inventory is evaluation-only information that no field measurement provides",
            "files": [
                {"figure_data": name, "path": f"{name}.json", "sha256": digest}
                for name, digest in digests.items()
            ],
        }
        contract_digest = write_json(site_data / "contract.json", contract)

        for name in [*figures, "contract"]:
            run.add_output(repo_relative(site_data / f"{name}.json"), role="figure-data")

        run.metrics(
            reconciliation_checks_passed=scenario_checks + holdout_checks,
            scenarios_exported=len(scenarios["scenarios"]),
            observations_per_scenario=scenarios["scenarios"][0]["n_observations"],
            contract_sha256=contract_digest,
        )
        run.note(
            "Every exported scenario metric was reconciled against the audited summary "
            "before the file was written; a disagreement raises and writes nothing."
        )
        run.limitation(
            "This is a separate execution from the audited case run. It reuses the case "
            "module's own generator and estimator, but it is registered as a new run and "
            "does not replace the original."
        )
        run.limitation(
            "The holdout pressure series is a conditional reconstruction that multiplies a "
            "predicted p/Z by the deviation factor of the held-out state. It is not a "
            "self-contained blind pressure forecast."
        )

    print(f"reconciliation checks passed: {scenario_checks + holdout_checks}")
    print(f"scenarios exported:          {len(scenarios['scenarios'])}")
    print(f"observations per scenario:   {scenarios['scenarios'][0]['n_observations']}")
    print(f"figure data written to:      {site_data}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

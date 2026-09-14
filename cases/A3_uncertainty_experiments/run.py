#!/usr/bin/env python3
"""Case A3: what dominates the uncertainty in a gas-in-place estimate.

Executable study for `cases/A3_uncertainty_experiments/protocol.md`. Seven experiments, each
perturbing one thing in a synthetic closed-tank dry-gas depletion history, plus a ranking pass
and a projection of what the next measurement would buy.

Standard library only. Pure and deterministic: every random draw comes from a locally
constructed `random.Random` seeded from the configuration below, so two runs with the same
configuration produce identical numbers.

Run it as

    PYTHONPATH=src python3 cases/A3_uncertainty_experiments/run.py --out artifacts/A3/run-001

The output directory must not already exist with content in it; that is `RunRecord`'s
write-once rule and it is deliberate.
"""

from __future__ import annotations

import argparse
import math
import pathlib
import random
import statistics
import warnings
from collections.abc import Sequence
from typing import Any

from reservoir_lab import depletion, gas_properties, material_balance, regression
from reservoir_lab.errors import RangeWarning, ReservoirLabError
from reservoir_lab.provenance import RunRecord
from reservoir_lab.units import SPE_STANDARD, US_CONTRACTUAL_STANDARD, fahrenheit_to_rankine

# ---------------------------------------------------------------------------
# Configuration. Everything the study depends on, in one hashable object.
# ---------------------------------------------------------------------------

CONFIG: dict[str, Any] = {
    "case_id": "A3_uncertainty_experiments",
    "case_type": "synthetic_measurement_error_budget",
    "gas_in_place_scf": 1.0e11,
    "initial_pressure_psia": 4500.0,
    "temperature_degf": 200.0,
    "gas_specific_gravity": 0.65,
    "pseudocritical_correlation": "sutton-1985",
    "z_correlation": "dak",
    "alternative_z_correlations": ["hall-yarborough", "dpr"],
    "standard_basis": "SPE_STANDARD (14.696 psia, 60 degF)",
    "alternative_standard_basis": "US_CONTRACTUAL_STANDARD (14.73 psia, 60 degF)",
    "minimum_pressure_psia": 400.0,
    "base_surveys": 12,
    "base_depletion_fraction": 0.50,
    "survey_interval_days": 365.0,
    "pressure_sigma_psia": 45.0,
    "calibration_bias_grid_psia": [-50.0, -25.0, -14.696, 0.0, 25.0, 50.0],
    "reference_calibration_bias_psia": 25.0,
    "atmosphere_psia": 14.696,
    "multiplicative_z_error_grid": [-0.05, -0.02, -0.01, 0.01, 0.02, 0.05],
    "z_profile_scan_points": 401,
    "z_tilt_grid": [-0.01, -0.005, 0.005, 0.01],
    "depletion_fraction_grid": [0.10, 0.20, 0.35, 0.50],
    "degraded_surveys": 6,
    "degraded_depletion_fraction": 0.04,
    "degraded_pressure_sigma_psia": 120.0,
    "sigma_robustness_grid_psia": [22.5, 45.0, 90.0],
    "monte_carlo_replicates": 4000,
    "sweep_monte_carlo_replicates": 2000,
    "bootstrap_replicates": 4000,
    "ar1_lag1_correlation": 0.8,
    "holdout_training_surveys": 8,
    "confidence": 0.95,
    "seed": 20260913,
}

#: Machine-precision tolerance for the identity-style acceptance criteria (AC1-AC4, AC7, AC8).
IDENTITY_TOLERANCE = 1.0e-9
TIGHT_IDENTITY_TOLERANCE = 1.0e-12

#: Coverage acceptance band: nominal 0.95 plus three Monte Carlo standard errors at the smallest
#: ensemble any coverage criterion has to cover, 2000 draws, so 3 sqrt(0.95 * 0.05 / 2000) = 0.0146,
#: rounded out to 0.015. At the 4000-draw ensembles the same half-width is 4.35 standard errors, so
#: the band is looser there than three standard errors; AC5 reports the gap.
COVERAGE_BAND = (0.935, 0.965)

#: Files whose bytes the run record hashes, so the result can be tied to the code that made it.
DECLARED_INPUTS = (
    "cases/A3_uncertainty_experiments/run.py",
    "cases/A3_uncertainty_experiments/protocol.md",
    "src/reservoir_lab/depletion.py",
    "src/reservoir_lab/gas_properties.py",
    "src/reservoir_lab/material_balance.py",
    "src/reservoir_lab/regression.py",
    "src/reservoir_lab/units.py",
)


# ---------------------------------------------------------------------------
# Gas model and history generation
# ---------------------------------------------------------------------------

TEMPERATURE_DEGR = fahrenheit_to_rankine(CONFIG["temperature_degf"])
PSEUDOCRITICALS = gas_properties.pseudocritical_sutton(CONFIG["gas_specific_gravity"])


def z_at(pressure_psia: float, method: str = "dak") -> float:
    """Return the deviation factor at one absolute pressure, on this case's gas model."""
    return gas_properties.z_factor(pressure_psia, TEMPERATURE_DEGR, PSEUDOCRITICALS, method=method)


def ordinate(pressures_psia: Sequence[float], method: str = "dak") -> tuple[float, ...]:
    """Return p/Z for a series of reported pressures, with Z computed at the reported pressure.

    This is the analyst workflow fixed in the protocol: Z is not measured, it is computed from
    whatever pressure was reported, so a pressure error propagates into both factors of p/Z.
    """
    return tuple(p / z_at(p, method) for p in pressures_psia)


def ordinate_sensitivity(pressure_psia: float, step_psia: float = 0.01) -> float:
    """Return d(p/Z)/dp at one pressure by central difference, in psia of p/Z per psi.

    Used only to turn an assumed pressure standard deviation into an ordinate standard
    deviation for the design-based analytic predictions. It is never used in a fit.
    """
    high = (pressure_psia + step_psia) / z_at(pressure_psia + step_psia)
    low = (pressure_psia - step_psia) / z_at(pressure_psia - step_psia)
    return (high - low) / (2.0 * step_psia)


def build_history(n_surveys: int, depletion_fraction: float) -> depletion.DepletionHistory:
    """Generate a noise-free volumetric depletion history with evenly spaced cumulative gas.

    Constant offtake between annual surveys, so the abscissa is an even grid from zero to
    ``depletion_fraction * G``. The noise is applied later, in this script, to the reported
    series only; the generator's own history stays exactly conservative.
    """
    gas_in_place = CONFIG["gas_in_place_scf"]
    interval = CONFIG["survey_interval_days"]
    times = [interval * index for index in range(n_surveys)]
    step_scf = depletion_fraction * gas_in_place / (n_surveys - 1)
    rates = [step_scf / interval] * (n_surveys - 1)
    return depletion.simulate_volumetric_depletion(
        gas_in_place_scf=gas_in_place,
        initial_pressure_psia=CONFIG["initial_pressure_psia"],
        temperature_degr=TEMPERATURE_DEGR,
        times_days=times,
        gas_rates_scf_per_day=rates,
        z_of_pressure=z_at,
        standard=SPE_STANDARD,
        noise=depletion.NOISE_FREE,
        seed=CONFIG["seed"],
        minimum_pressure_psia=CONFIG["minimum_pressure_psia"],
    )


# ---------------------------------------------------------------------------
# Estimation helpers
# ---------------------------------------------------------------------------


def intercept_value(x: Sequence[float], y: Sequence[float]) -> float:
    """Return the OLS x-intercept of ``y`` against ``x``, in the units of ``x``."""
    return regression.x_intercept(regression.ols_line(x, y)).value


def predicted_intercept(x: Sequence[float], fit: regression.LineFit, deltas: Sequence[float]) -> float:
    """Return the x-intercept the fit would have after adding ``deltas`` to the ordinate.

    Ordinary least squares is linear in the ordinate, so the coefficient changes are exact:
    ``Delta_b = sum (x_i - xbar) delta_i / Sxx`` and ``Delta_a = mean(delta) - Delta_b * xbar``.
    Evaluating ``-(a + Delta_a) / (b + Delta_b)`` is then an exact prediction, obtained without
    calling the estimator on the perturbed data. That independence is what makes it an oracle
    rather than a restatement.
    """
    x_mean = fit.x_mean
    sxx = fit.sum_squared_x_deviations
    delta_slope = math.fsum((xi - x_mean) * di for xi, di in zip(x, deltas, strict=True)) / sxx
    delta_intercept = math.fsum(deltas) / len(deltas) - delta_slope * x_mean
    return -(fit.intercept + delta_intercept) / (fit.slope + delta_slope)


def design_stderr(n_surveys: int, depletion_fraction: float, sigma_psia: float) -> float:
    """Return the design-based one-sigma standard error of G, in scf, before any data exist.

    The exact least-squares inverse-prediction variance evaluated on the *planned* abscissa grid
    with the assumed ordinate standard deviation, rather than on a realised residual variance.
    This is what a survey-design calculation looks like: no data, only a programme.
    """
    gas_in_place = CONFIG["gas_in_place_scf"]
    history = build_history(n_surveys, depletion_fraction)
    x = history.cumulative_gas_scf
    x_mean = math.fsum(x) / n_surveys
    sxx = math.fsum((xi - x_mean) ** 2 for xi in x)
    sigma_y = sigma_psia * statistics.fmean(ordinate_sensitivity(p) for p in history.pressures_psia)
    slope = -initial_p_over_z() / gas_in_place
    return (sigma_y / abs(slope)) * math.sqrt(1.0 / n_surveys + (gas_in_place - x_mean) ** 2 / sxx)


def shared_offset_shift(n_surveys: int, depletion_fraction: float, offset_psia: float) -> float:
    """Return |dG|/G for a shared pressure offset on a noise-free programme, Z recomputed."""
    history = build_history(n_surveys, depletion_fraction)
    shifted = ordinate([p + offset_psia for p in history.pressures_psia])
    value = intercept_value(history.cumulative_gas_scf, shifted)
    return abs(value / CONFIG["gas_in_place_scf"] - 1.0)


def bias_break_even_psia(
    n_surveys: int, depletion_fraction: float, target_relative: float, upper_psia: float = 200.0
) -> float:
    """Return the shared offset whose relative shift in G equals ``target_relative``.

    Bisection on the exact refit, not on the linearised rate, because the shift is only
    approximately linear in the offset. Used to state how much residual datum error the
    recommended calibration option can carry before it stops being the best of the four.
    """
    if target_relative <= 0.0:
        return 0.0
    low, high = 0.0, upper_psia
    if shared_offset_shift(n_surveys, depletion_fraction, high) < target_relative:
        raise ValueError("break-even offset is outside the bracket")
    for _ in range(200):
        middle = 0.5 * (low + high)
        if shared_offset_shift(n_surveys, depletion_fraction, middle) < target_relative:
            low = middle
        else:
            high = middle
        if high - low < 1.0e-9:
            break
    return 0.5 * (low + high)


def initial_p_over_z() -> float:
    """Return A = p_i / Z_i for this case's reservoir, in psia."""
    initial = CONFIG["initial_pressure_psia"]
    return initial / z_at(initial)


def gaussian_errors(rng: random.Random, sigma: float, count: int) -> list[float]:
    """Return ``count`` independent zero-mean Gaussian draws of standard deviation ``sigma``."""
    return [rng.gauss(0.0, sigma) for _ in range(count)]


def ar1_errors(rng: random.Random, sigma: float, rho: float, count: int) -> list[float]:
    """Return an AR(1) error series with lag-1 correlation ``rho`` and marginal sd ``sigma``.

    The innovation is scaled by ``sqrt(1 - rho**2)`` so the marginal standard deviation is
    ``sigma`` at every index, not only asymptotically. Without that the correlated case would
    differ from the independent case in two ways at once and neither could be attributed.
    """
    series = [rng.gauss(0.0, sigma)]
    for _ in range(count - 1):
        series.append(rho * series[-1] + math.sqrt(1.0 - rho * rho) * rng.gauss(0.0, sigma))
    return series


def monte_carlo(
    pressures_psia: Sequence[float],
    cumulative_scf: Sequence[float],
    *,
    sigma_psia: float,
    replicates: int,
    seed: int,
    rho: float = 0.0,
    offset_psia: float = 0.0,
) -> dict[str, Any]:
    """Run a noise ensemble on one survey programme and summarise the sampling distribution.

    Each replicate perturbs the reported pressures, rebuilds the ordinate through the analyst
    workflow, and refits. Replicates that the library refuses -- a non-negative slope, an
    x-intercept below the observed production -- are counted, never retried and never dropped
    silently: a retried replicate is how an ensemble becomes a selected sample.
    """
    truth = CONFIG["gas_in_place_scf"]
    rng = random.Random(seed)
    values: list[float] = []
    stderrs: list[float] = []
    delta_covered = 0
    fieller_covered = 0
    unbounded = 0
    refused_by_library = 0
    kinds: dict[str, int] = {}
    for _ in range(replicates):
        errors = (
            ar1_errors(rng, sigma_psia, rho, len(pressures_psia))
            if rho
            else gaussian_errors(rng, sigma_psia, len(pressures_psia))
        )
        reported = [p + e + offset_psia for p, e in zip(pressures_psia, errors, strict=True)]
        y = ordinate(reported)
        try:
            material_balance.fit_pz_depletion(cumulative_scf, y)
        except ReservoirLabError:
            refused_by_library += 1
        try:
            fit = regression.ols_line(cumulative_scf, y)
            estimate = regression.x_intercept(fit)
            fieller = regression.x_intercept_fieller(fit, confidence=CONFIG["confidence"])
        except ReservoirLabError:
            kinds["no_line"] = kinds.get("no_line", 0) + 1
            continue
        values.append(estimate.value)
        stderrs.append(estimate.stderr)
        low, high = estimate.symmetric_interval(CONFIG["confidence"])
        if low <= truth <= high:
            delta_covered += 1
        if fieller.contains(truth):
            fieller_covered += 1
        if not fieller.bounded:
            unbounded += 1
        kinds[fieller.kind] = kinds.get(fieller.kind, 0) + 1
    used = len(values)
    lower_quartile, _, upper_quartile = statistics.quantiles(values, n=4, method="inclusive")
    return {
        "replicates_requested": replicates,
        "replicates_used": used,
        "library_refusals": refused_by_library,
        "mean_gas_in_place_scf": statistics.fmean(values),
        "median_gas_in_place_scf": statistics.median(values),
        "sampling_sd_scf": statistics.stdev(values),
        "robust_scale_scf": (upper_quartile - lower_quartile) / 1.3489795003921634,
        "median_delta_stderr_scf": statistics.median(stderrs),
        "delta_coverage": delta_covered / used,
        "fieller_coverage": fieller_covered / used,
        "unbounded_fraction": unbounded / used,
        "fieller_kinds": kinds,
    }


def bootstrap_stderr(
    x: Sequence[float], y: Sequence[float], *, block_length: int, seed: int
) -> dict[str, Any]:
    """Return a moving-block bootstrap standard error of the x-intercept, with its scheme."""
    result = regression.moving_block_bootstrap(
        x,
        y,
        block_length=block_length,
        replicates=CONFIG["bootstrap_replicates"],
        seed=seed,
        statistic=lambda xs, ys: regression.x_intercept(regression.ols_line(xs, ys)).value,
    )
    low, high = result.percentile_interval(CONFIG["confidence"])
    return {
        "block_length": result.block_length,
        "n_starts": result.n_starts,
        "standard_error_scf": result.standard_error,
        "bias_scf": result.bias,
        "percentile_low_scf": low,
        "percentile_high_scf": high,
        "replicates_used": result.replicates_used,
        "replicates_failed": result.replicates_failed,
    }


def fieller_summary(fit: regression.LineFit) -> dict[str, Any]:
    """Return the exact confidence set for the x-intercept as a JSON-safe mapping."""
    interval = regression.x_intercept_fieller(fit, confidence=CONFIG["confidence"])
    return {
        "kind": interval.kind,
        "bounded": interval.bounded,
        "lower_scf": interval.lower,
        "upper_scf": interval.upper,
        "g": interval.g,
        "discriminant": interval.discriminant,
    }


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------


def experiment_0_oracle() -> dict[str, Any]:
    """Fit the noise-free history and check that the x-intercept returns the generated G."""
    truth = CONFIG["gas_in_place_scf"]
    history = build_history(CONFIG["base_surveys"], CONFIG["base_depletion_fraction"])
    x = history.cumulative_gas_scf
    y = ordinate(history.pressures_psia)
    fit = material_balance.fit_pz_depletion(x, y)
    line = regression.ols_line(x, y)
    collapsed = math.sqrt(regression.x_intercept_variance_collapsed(line))

    train = CONFIG["holdout_training_surveys"]
    train_fit = regression.ols_line(x[:train], y[:train])
    predicted = [train_fit.predict(xi) for xi in x[train:]]
    residuals = [p - o for p, o in zip(predicted, y[train:], strict=True)]
    holdout_rmse = math.sqrt(math.fsum(r * r for r in residuals) / len(residuals))

    return {
        "initial_z_factor": z_at(CONFIG["initial_pressure_psia"]),
        "initial_p_over_z_psia": initial_p_over_z(),
        "generator_max_residual_p_over_z_psia": history.max_abs_residual_p_over_z_psia,
        "generator_warnings": list(history.warnings),
        "pressures_psia": list(history.pressures_psia),
        "cumulative_gas_scf": list(x),
        "p_over_z_psia": list(y),
        "gas_in_place_scf": fit.gas_in_place_scf,
        "relative_error": fit.gas_in_place_scf / truth - 1.0,
        "slope_psia_per_scf": fit.slope,
        "r_squared": fit.r_squared,
        "fieller_g": fit.fieller_g,
        "depletion_fraction_observed": fit.depletion_fraction_observed,
        "pz_fit_warnings": list(fit.warnings),
        "stderr_scf": fit.gas_in_place_stderr_scf,
        "collapsed_stderr_scf": collapsed,
        "stderr_identity_relative_difference": (
            abs(collapsed - fit.gas_in_place_stderr_scf) / max(fit.gas_in_place_stderr_scf, 1e-300)
        ),
        "holdout_training_surveys": train,
        "holdout_gas_in_place_scf": regression.x_intercept(train_fit).value,
        "holdout_depletion_fraction": x[train - 1] / truth,
        "holdout_rmse_p_over_z_psia": holdout_rmse,
        "holdout_rmse_fraction_of_initial_p_over_z": holdout_rmse / initial_p_over_z(),
    }


def experiment_1_random_noise() -> dict[str, Any]:
    """Perturb every reported pressure with independent Gaussian error and measure the spread."""
    sigma = CONFIG["pressure_sigma_psia"]
    history = build_history(CONFIG["base_surveys"], CONFIG["base_depletion_fraction"])
    x = history.cumulative_gas_scf
    rng = random.Random(CONFIG["seed"])
    errors = gaussian_errors(rng, sigma, len(x))
    reported = [p + e for p, e in zip(history.pressures_psia, errors, strict=True)]
    y = ordinate(reported)
    fit = regression.ols_line(x, y)
    estimate = regression.x_intercept(fit)
    advice = regression.suggested_block_length(fit.residuals)

    ensemble = monte_carlo(
        history.pressures_psia,
        x,
        sigma_psia=sigma,
        replicates=CONFIG["monte_carlo_replicates"],
        seed=CONFIG["seed"] + 1,
    )
    doubled = build_history(2 * CONFIG["base_surveys"], CONFIG["base_depletion_fraction"])
    ensemble_doubled = monte_carlo(
        doubled.pressures_psia,
        doubled.cumulative_gas_scf,
        sigma_psia=sigma,
        replicates=CONFIG["monte_carlo_replicates"],
        seed=CONFIG["seed"] + 2,
    )

    # Chronological holdout on the noisy realisation. The noise-free version of this check in E0
    # is exact by construction and therefore says nothing about measurement error; this one is the
    # holdout the protocol asks for. Nothing is tuned on surveys 9 to 12.
    train = CONFIG["holdout_training_surveys"]
    train_fit = regression.ols_line(x[:train], y[:train])
    residuals = [train_fit.predict(xi) - yi for xi, yi in zip(x[train:], y[train:], strict=True)]
    holdout_rmse = math.sqrt(math.fsum(r * r for r in residuals) / len(residuals))
    train_estimate = regression.x_intercept(train_fit)

    return {
        "pressure_sigma_psia": sigma,
        "holdout": {
            "training_surveys": train,
            "training_depletion_fraction": x[train - 1] / CONFIG["gas_in_place_scf"],
            "gas_in_place_from_training_scf": train_estimate.value,
            "stderr_from_training_scf": train_estimate.stderr,
            "gas_in_place_from_full_history_scf": estimate.value,
            "rmse_p_over_z_psia": holdout_rmse,
            "rmse_fraction_of_initial_p_over_z": holdout_rmse / initial_p_over_z(),
            "residuals_p_over_z_psia": residuals,
        },
        "named_realisation": {
            "gas_in_place_scf": estimate.value,
            "relative_error": estimate.value / CONFIG["gas_in_place_scf"] - 1.0,
            "delta_stderr_scf": estimate.stderr,
            "delta_interval_scf": list(estimate.symmetric_interval(CONFIG["confidence"])),
            "delta_warnings": list(estimate.warnings),
            "r_squared": fit.r_squared,
            "fieller": fieller_summary(fit),
            "suggested_block_length": advice.recommended,
            "suggested_block_rule": advice.rule,
            "estimated_lag1_correlation": advice.lag1_correlation,
            "bootstrap_iid": bootstrap_stderr(x, y, block_length=1, seed=CONFIG["seed"] + 3),
            "bootstrap_suggested": bootstrap_stderr(
                x, y, block_length=advice.recommended, seed=CONFIG["seed"] + 3
            ),
        },
        "ensemble_n12": ensemble,
        "ensemble_n24": ensemble_doubled,
        "sd_ratio_n24_over_n12": ensemble_doubled["sampling_sd_scf"] / ensemble["sampling_sd_scf"],
        "root_n_prediction": 1.0 / math.sqrt(2.0),
    }


def experiment_1b_correlated_noise() -> dict[str, Any]:
    """Repeat the noise experiment with an AR(1) drifting gauge, the bootstrap's positive control."""
    sigma = CONFIG["pressure_sigma_psia"]
    rho = CONFIG["ar1_lag1_correlation"]
    history = build_history(CONFIG["base_surveys"], CONFIG["base_depletion_fraction"])
    x = history.cumulative_gas_scf
    rng = random.Random(CONFIG["seed"] + 10)
    errors = ar1_errors(rng, sigma, rho, len(x))
    reported = [p + e for p, e in zip(history.pressures_psia, errors, strict=True)]
    y = ordinate(reported)
    fit = regression.ols_line(x, y)
    estimate = regression.x_intercept(fit)
    advice = regression.suggested_block_length(fit.residuals)
    ensemble = monte_carlo(
        history.pressures_psia,
        x,
        sigma_psia=sigma,
        replicates=CONFIG["monte_carlo_replicates"],
        seed=CONFIG["seed"] + 11,
        rho=rho,
    )
    bootstraps = {
        f"block_length_{length}": bootstrap_stderr(x, y, block_length=length, seed=CONFIG["seed"] + 12)
        for length in (1, 3, 6)
    }
    return {
        "lag1_correlation_imposed": rho,
        "named_realisation": {
            "gas_in_place_scf": estimate.value,
            "delta_stderr_scf": estimate.stderr,
            "estimated_lag1_correlation": advice.lag1_correlation,
            "integrated_autocorrelation_time": advice.integrated_autocorrelation_time,
            "suggested_block_length": advice.recommended,
            "bootstraps": bootstraps,
        },
        "ensemble": ensemble,
        "sd_over_median_delta_stderr": (ensemble["sampling_sd_scf"] / ensemble["median_delta_stderr_scf"]),
    }


def experiment_2_shared_bias() -> dict[str, Any]:
    """Add the same offset to every reported pressure and compare against three closed forms."""
    truth = CONFIG["gas_in_place_scf"]
    a_intercept = initial_p_over_z()
    history = build_history(CONFIG["base_surveys"], CONFIG["base_depletion_fraction"])
    x = history.cumulative_gas_scf
    base_y = ordinate(history.pressures_psia)
    base_fit = regression.ols_line(x, base_y)

    rows = []
    for offset in CONFIG["calibration_bias_grid_psia"]:
        shifted = [p + offset for p in history.pressures_psia]
        y_full = ordinate(shifted)
        # The second variant holds Z at its true value, so only the numerator of p/Z moves. It
        # isolates the part of the shift the rule of thumb is about from the part that arrives
        # because the analyst also recomputes Z at the wrong pressure.
        y_fixed = tuple(s / z_at(p) for s, p in zip(shifted, history.pressures_psia, strict=True))
        deltas_full = [new - old for new, old in zip(y_full, base_y, strict=True)]
        deltas_fixed = [new - old for new, old in zip(y_fixed, base_y, strict=True)]
        observed_full = intercept_value(x, y_full)
        observed_fixed = intercept_value(x, y_fixed)
        predicted_full = predicted_intercept(x, base_fit, deltas_full)
        predicted_fixed = predicted_intercept(x, base_fit, deltas_fixed)
        card_rule = truth * (1.0 + offset / a_intercept)
        rows.append(
            {
                "offset_psia": offset,
                "gas_in_place_z_recomputed_scf": observed_full,
                "gas_in_place_z_held_scf": observed_fixed,
                "relative_shift_z_recomputed": observed_full / truth - 1.0,
                "relative_shift_z_held": observed_fixed / truth - 1.0,
                "exact_prediction_z_recomputed_scf": predicted_full,
                "exact_prediction_z_held_scf": predicted_fixed,
                "prediction_error_z_recomputed": abs(observed_full - predicted_full) / truth,
                "prediction_error_z_held": abs(observed_fixed - predicted_fixed) / truth,
                "card_rule_of_thumb_scf": card_rule,
                "card_rule_relative_shift": card_rule / truth - 1.0,
                "card_rule_understatement_factor_z_recomputed": (
                    (observed_full - truth) / (card_rule - truth) if offset else None
                ),
            }
        )

    invariance = []
    reference_offset = CONFIG["reference_calibration_bias_psia"]
    for n_surveys in (12, 24, 48):
        sized = build_history(n_surveys, CONFIG["base_depletion_fraction"])
        shifted = ordinate([p + reference_offset for p in sized.pressures_psia])
        value = intercept_value(sized.cumulative_gas_scf, shifted)
        invariance.append(
            {
                "n_surveys": n_surveys,
                "relative_shift": value / truth - 1.0,
                "design_stderr_relative": design_stderr(
                    n_surveys, CONFIG["base_depletion_fraction"], CONFIG["pressure_sigma_psia"]
                )
                / truth,
            }
        )

    return {
        "initial_p_over_z_psia": a_intercept,
        "grid": rows,
        "invariance_to_sample_size": invariance,
        "max_prediction_error": max(
            max(row["prediction_error_z_recomputed"], row["prediction_error_z_held"]) for row in rows
        ),
    }


def experiment_3_psig() -> dict[str, Any]:
    """Supply psig where psia was required and verify the sign and magnitude of the resulting shift."""
    truth = CONFIG["gas_in_place_scf"]
    offset = -CONFIG["atmosphere_psia"]
    a_intercept = initial_p_over_z()
    history = build_history(CONFIG["base_surveys"], CONFIG["base_depletion_fraction"])
    x = history.cumulative_gas_scf
    base_y = ordinate(history.pressures_psia)
    base_fit = regression.ols_line(x, base_y)

    gauge = [p + offset for p in history.pressures_psia]
    y_full = ordinate(gauge)
    y_fixed = tuple(g / z_at(p) for g, p in zip(gauge, history.pressures_psia, strict=True))
    observed_full = intercept_value(x, y_full)
    observed_fixed = intercept_value(x, y_fixed)
    predicted_full = predicted_intercept(x, base_fit, [n - o for n, o in zip(y_full, base_y, strict=True)])
    predicted_fixed = predicted_intercept(x, base_fit, [n - o for n, o in zip(y_fixed, base_y, strict=True)])
    card_rule = truth * offset / a_intercept

    noise_sd = design_stderr(
        CONFIG["base_surveys"], CONFIG["base_depletion_fraction"], CONFIG["pressure_sigma_psia"]
    )
    ensemble = monte_carlo(
        history.pressures_psia,
        x,
        sigma_psia=CONFIG["pressure_sigma_psia"],
        replicates=CONFIG["monte_carlo_replicates"],
        seed=CONFIG["seed"] + 20,
        offset_psia=offset,
    )
    return {
        "offset_psia": offset,
        "gas_in_place_z_recomputed_scf": observed_full,
        "gas_in_place_z_held_scf": observed_fixed,
        "shift_z_recomputed_scf": observed_full - truth,
        "shift_z_held_scf": observed_fixed - truth,
        "relative_shift_z_recomputed": observed_full / truth - 1.0,
        "relative_shift_z_held": observed_fixed / truth - 1.0,
        "sign_is_negative": observed_full < truth and observed_fixed < truth,
        "exact_prediction_z_recomputed_scf": predicted_full,
        "exact_prediction_z_held_scf": predicted_fixed,
        "prediction_error_z_recomputed": abs(observed_full - predicted_full) / truth,
        "prediction_error_z_held": abs(observed_fixed - predicted_fixed) / truth,
        "card_rule_of_thumb_shift_scf": card_rule,
        "card_rule_relative_shift": card_rule / truth,
        "card_rule_understatement_factor": (observed_full - truth) / card_rule,
        "shift_in_units_of_design_sigma": (observed_full - truth) / noise_sd,
        "design_sigma_scf": noise_sd,
        "coverage_of_truth_with_offset_present": ensemble["delta_coverage"],
        "ensemble_median_scf": ensemble["median_gas_in_place_scf"],
    }


def experiment_4_z_factor() -> dict[str, Any]:
    """Separate the level of the deviation factor from its shape across the observed window."""
    truth = CONFIG["gas_in_place_scf"]
    history = build_history(CONFIG["base_surveys"], CONFIG["base_depletion_fraction"])
    x = history.cumulative_gas_scf
    pressures = history.pressures_psia
    base_y = ordinate(pressures)
    base_value = intercept_value(x, base_y)

    multiplicative = []
    for epsilon in CONFIG["multiplicative_z_error_grid"]:
        y = tuple(p / (z_at(p) * (1.0 + epsilon)) for p in pressures)
        value = intercept_value(x, y)
        multiplicative.append(
            {
                "relative_z_error": epsilon,
                "gas_in_place_scf": value,
                "relative_shift_from_base": (value - base_value) / truth,
            }
        )

    low, high = min(pressures), max(pressures)
    correlations = []
    for method in CONFIG["alternative_z_correlations"]:
        y = ordinate(pressures, method=method)
        value = intercept_value(x, y)
        correlations.append(
            {
                "method": method,
                "gas_in_place_scf": value,
                "relative_shift": value / truth - 1.0,
                "z_at_first_survey": z_at(pressures[0], method),
                "z_at_last_survey": z_at(pressures[-1], method),
                "relative_z_difference_first": z_at(pressures[0], method) / z_at(pressures[0]) - 1.0,
                "relative_z_difference_last": z_at(pressures[-1], method) / z_at(pressures[-1]) - 1.0,
            }
        )

    profiles = []
    scan_points = CONFIG["z_profile_scan_points"]
    scan = [low + (high - low) * index / (scan_points - 1) for index in range(scan_points)]
    for method in CONFIG["alternative_z_correlations"]:
        differences = [z_at(p, method) / z_at(p) - 1.0 for p in scan]
        worst = max(range(scan_points), key=lambda index: abs(differences[index]))
        profiles.append(
            {
                "method": method,
                "scan_points": scan_points,
                "signed_difference_at_worst": differences[worst],
                "max_absolute_relative_difference": abs(differences[worst]),
                "pressure_at_worst_psia": scan[worst],
                "min_signed_relative_difference": min(differences),
                "max_signed_relative_difference": max(differences),
            }
        )

    tilts = []
    for epsilon in CONFIG["z_tilt_grid"]:
        y = tuple(p / (z_at(p) * (1.0 + epsilon * (p - low) / (high - low))) for p in pressures)
        value = intercept_value(x, y)
        tilts.append(
            {
                "tilt_across_window": epsilon,
                "gas_in_place_scf": value,
                "relative_shift": value / truth - 1.0,
                "amplification": (value / truth - 1.0) / epsilon,
            }
        )

    return {
        "observed_pressure_window_psia": [low, high],
        "z_at_first_survey_dak": z_at(pressures[0]),
        "z_at_last_survey_dak": z_at(pressures[-1]),
        "multiplicative": multiplicative,
        "max_multiplicative_relative_shift": max(
            abs(row["relative_shift_from_base"]) for row in multiplicative
        ),
        "correlation_choice": correlations,
        "correlation_profile_over_window": profiles,
        "tilt": tilts,
    }


def experiment_5_short_depletion() -> dict[str, Any]:
    """Hold the noise fixed and shorten the observed depletion, comparing three uncertainty treatments."""
    truth = CONFIG["gas_in_place_scf"]
    sigma = CONFIG["pressure_sigma_psia"]
    rows = []
    for index, fraction in enumerate(CONFIG["depletion_fraction_grid"]):
        history = build_history(CONFIG["base_surveys"], fraction)
        x = history.cumulative_gas_scf
        rng = random.Random(CONFIG["seed"] + 30 + index)
        reported = [
            p + e for p, e in zip(history.pressures_psia, gaussian_errors(rng, sigma, len(x)), strict=True)
        ]
        y = ordinate(reported)
        fit = regression.ols_line(x, y)
        estimate = regression.x_intercept(fit)
        collapsed = math.sqrt(regression.x_intercept_variance_collapsed(fit))
        ensemble = monte_carlo(
            history.pressures_psia,
            x,
            sigma_psia=sigma,
            replicates=CONFIG["sweep_monte_carlo_replicates"],
            seed=CONFIG["seed"] + 40 + index,
        )
        rows.append(
            {
                "depletion_fraction": fraction,
                "n_surveys": CONFIG["base_surveys"],
                "gas_in_place_scf": estimate.value,
                "delta_stderr_scf": estimate.stderr,
                "delta_stderr_relative": estimate.stderr / truth,
                "collapsed_stderr_scf": collapsed,
                "stderr_identity_relative_difference": abs(collapsed - estimate.stderr) / estimate.stderr,
                "design_stderr_scf": design_stderr(CONFIG["base_surveys"], fraction, sigma),
                "fieller_g": estimate.fieller_g,
                "fieller": fieller_summary(fit),
                "delta_interval_scf": list(estimate.symmetric_interval(CONFIG["confidence"])),
                "delta_warnings": list(estimate.warnings),
                "bootstrap_iid": bootstrap_stderr(x, y, block_length=1, seed=CONFIG["seed"] + 50 + index),
                "ensemble": ensemble,
            }
        )

    degraded_history = build_history(CONFIG["degraded_surveys"], CONFIG["degraded_depletion_fraction"])
    degraded_sigma = CONFIG["degraded_pressure_sigma_psia"]
    dx = degraded_history.cumulative_gas_scf
    rng = random.Random(CONFIG["seed"] + 60)
    degraded_reported = [
        p + e
        for p, e in zip(
            degraded_history.pressures_psia, gaussian_errors(rng, degraded_sigma, len(dx)), strict=True
        )
    ]
    degraded_y = ordinate(degraded_reported)
    degraded_fit = regression.ols_line(dx, degraded_y)
    degraded_estimate = regression.x_intercept(degraded_fit)
    degraded_ensemble = monte_carlo(
        degraded_history.pressures_psia,
        dx,
        sigma_psia=degraded_sigma,
        replicates=CONFIG["sweep_monte_carlo_replicates"],
        seed=CONFIG["seed"] + 61,
    )
    degraded = {
        "n_surveys": CONFIG["degraded_surveys"],
        "depletion_fraction": CONFIG["degraded_depletion_fraction"],
        "pressure_sigma_psia": degraded_sigma,
        "gas_in_place_scf": degraded_estimate.value,
        "delta_stderr_scf": degraded_estimate.stderr,
        "delta_stderr_relative": degraded_estimate.stderr / truth,
        "delta_interval_scf": list(degraded_estimate.symmetric_interval(CONFIG["confidence"])),
        "delta_warnings": list(degraded_estimate.warnings),
        "fieller": fieller_summary(degraded_fit),
        "bootstrap_iid": bootstrap_stderr(dx, degraded_y, block_length=1, seed=CONFIG["seed"] + 62),
        "ensemble": degraded_ensemble,
    }
    return {"sweep": rows, "degraded_programme": degraded}


def experiment_6_standard_basis() -> dict[str, Any]:
    """Change the declared standard-volume basis and separate its static and dynamic consequences."""
    initial = CONFIG["initial_pressure_psia"]
    z_initial = z_at(initial)
    ratio = US_CONTRACTUAL_STANDARD.pressure_psia / SPE_STANDARD.pressure_psia
    bg_spe = gas_properties.gas_fvf_rcf_per_scf(initial, TEMPERATURE_DEGR, z_initial, SPE_STANDARD)
    bg_us = gas_properties.gas_fvf_rcf_per_scf(initial, TEMPERATURE_DEGR, z_initial, US_CONTRACTUAL_STANDARD)
    static_spe = material_balance.volumetric_gas_in_place_scf(
        area_acres=2000.0,
        thickness_ft=60.0,
        porosity=0.18,
        water_saturation=0.25,
        gas_fvf_rcf_per_scf=bg_spe,
    )
    static_us = material_balance.volumetric_gas_in_place_scf(
        area_acres=2000.0,
        thickness_ft=60.0,
        porosity=0.18,
        water_saturation=0.25,
        gas_fvf_rcf_per_scf=bg_us,
    )
    history = build_history(CONFIG["base_surveys"], CONFIG["base_depletion_fraction"])
    y = ordinate(history.pressures_psia)
    dynamic_spe = intercept_value(history.cumulative_gas_scf, y)
    rescaled = tuple(value / ratio for value in history.cumulative_gas_scf)
    dynamic_us = intercept_value(rescaled, y)
    rounded_ratio = 14.73 / CONFIG["atmosphere_psia"]
    return {
        "standard_pressure_ratio_us_over_spe": ratio,
        "rounded_ratio_14p73_over_14p696": rounded_ratio,
        "relative_gap_declared_ratio_against_rounded": abs(ratio - rounded_ratio) / rounded_ratio,
        "gas_fvf_spe_rcf_per_scf": bg_spe,
        "gas_fvf_us_rcf_per_scf": bg_us,
        "gas_fvf_ratio": bg_us / bg_spe,
        "static_gas_in_place_spe_scf": static_spe,
        "static_gas_in_place_us_scf": static_us,
        "static_relative_shift": static_us / static_spe - 1.0,
        "static_identity_error": abs(static_us / static_spe - 1.0 / ratio) * ratio,
        "dynamic_gas_in_place_spe_scf": dynamic_spe,
        "dynamic_gas_in_place_us_scf": dynamic_us,
        "dynamic_relative_shift": dynamic_us / dynamic_spe - 1.0,
        "dynamic_identity_error": abs(dynamic_us / dynamic_spe - 1.0 / ratio) * ratio,
        "comment": (
            "The p/Z x-intercept inherits the basis of the cumulative production supplied to it. "
            "It carries no basis error of its own; the error appears when a dynamic G on one basis "
            "is compared with a static G on another."
        ),
    }


def experiment_7_ranking(
    oracle: dict[str, Any],
    bias: dict[str, Any],
    psig: dict[str, Any],
    zfactor: dict[str, Any],
    basis: dict[str, Any],
) -> dict[str, Any]:
    """Rank the error sources, test the ranking against the assumed sigma, and price the next step."""
    truth = CONFIG["gas_in_place_scf"]
    base_n = CONFIG["base_surveys"]
    base_f = CONFIG["base_depletion_fraction"]
    reference_bias_row = next(
        row for row in bias["grid"] if row["offset_psia"] == CONFIG["reference_calibration_bias_psia"]
    )
    correlation_shift = max(abs(row["relative_shift"]) for row in zfactor["correlation_choice"])
    multiplicative_magnitude = max(abs(value) for value in CONFIG["multiplicative_z_error_grid"])
    multiplicative_label = f"uniform multiplicative Z error, {multiplicative_magnitude * 100:g} percent"

    rankings = {}
    for sigma in CONFIG["sigma_robustness_grid_psia"]:
        entries = [
            ("random pressure scatter, one sigma", design_stderr(base_n, base_f, sigma) / truth),
            ("shared calibration bias, 25 psia", abs(reference_bias_row["relative_shift_z_recomputed"])),
            ("psig supplied as psia", abs(psig["relative_shift_z_recomputed"])),
            ("deviation-factor correlation choice", correlation_shift),
            ("standard basis 14.696 against 14.73", abs(basis["static_relative_shift"])),
            (multiplicative_label, zfactor["max_multiplicative_relative_shift"]),
        ]
        rankings[f"sigma_{sigma:g}_psia"] = [
            {"source": name, "relative_effect": value}
            for name, value in sorted(entries, key=lambda item: item[1], reverse=True)
        ]
    top_two = {key: [row["source"] for row in value[:2]] for key, value in rankings.items()}
    ranking_stable = len({tuple(value) for value in top_two.values()}) == 1

    short_depletion_penalty = design_stderr(base_n, 0.10, CONFIG["pressure_sigma_psia"]) / design_stderr(
        base_n, base_f, CONFIG["pressure_sigma_psia"]
    )

    def option(
        label: str, n_surveys: int, fraction: float, sigma: float, bias_present: bool
    ) -> dict[str, Any]:
        """Return the projected error budget for one candidate survey programme."""
        history = build_history(n_surveys, fraction)
        offset = CONFIG["reference_calibration_bias_psia"] if bias_present else 0.0
        shifted = ordinate([p + offset for p in history.pressures_psia])
        bias_relative = abs(intercept_value(history.cumulative_gas_scf, shifted) / truth - 1.0)
        stderr_relative = design_stderr(n_surveys, fraction, sigma) / truth
        return {
            "option": label,
            "n_surveys": n_surveys,
            "depletion_fraction": fraction,
            "pressure_sigma_psia": sigma,
            "calibration_bias_present": bias_present,
            "design_stderr_relative": stderr_relative,
            "bias_relative": bias_relative,
            "total_relative": stderr_relative + bias_relative,
        }

    sigma_p = CONFIG["pressure_sigma_psia"]
    options = [
        option("base programme as it stands", base_n, base_f, sigma_p, True),
        option("double the survey count at the same depletion", 24, base_f, sigma_p, True),
        option("wait three more years, to 65 percent depletion", 15, 0.65, sigma_p, True),
        option("halve the average-pressure scatter", base_n, base_f, sigma_p / 2, True),
        option("calibrate the pressure datum, removing the bias", base_n, base_f, sigma_p, False),
    ]
    best = min(options[1:], key=lambda row: row["total_relative"])
    calibrated = next(row for row in options if not row["calibration_bias_present"])
    runner_up = min(
        (row for row in options[1:] if row["option"] != calibrated["option"]),
        key=lambda row: row["total_relative"],
    )
    break_even_margin = runner_up["total_relative"] - calibrated["total_relative"]
    break_even_residual = bias_break_even_psia(base_n, base_f, break_even_margin)

    return {
        "rankings_by_assumed_sigma": rankings,
        "top_two_by_assumed_sigma": top_two,
        "ranking_stable_under_sigma_factor_two": ranking_stable,
        "short_depletion_penalty_f010_over_f050": short_depletion_penalty,
        "noise_free_relative_error": oracle["relative_error"],
        "options": options,
        "best_option": best["option"],
        "best_option_total_relative": best["total_relative"],
        "best_option_runner_up": runner_up["option"],
        "best_option_margin_relative": break_even_margin,
        "residual_datum_error_break_even_psia": break_even_residual,
        "break_even_note": (
            "The recommended option assumes the calibration check leaves no systematic behind. A "
            "residual datum error larger than residual_datum_error_break_even_psia, applied as a "
            "shared offset on every survey, puts the calibrated programme behind "
            "best_option_runner_up on the same linear combination convention."
        ),
        "combination_convention": (
            "one-sigma random standard error and the absolute value of the systematic shift are "
            "added linearly. A bias is not a random variable and adding it in quadrature would "
            "understate it; the two components are reported separately as well."
        ),
    }


# ---------------------------------------------------------------------------
# Acceptance
# ---------------------------------------------------------------------------


def evaluate_acceptance(results: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate every pre-registered acceptance criterion against the results just computed."""
    oracle = results["E0_oracle"]
    noise = results["E1_random_noise"]
    bias = results["E2_shared_bias"]
    psig = results["E3_psig_for_psia"]
    zfactor = results["E4_z_factor"]
    sweep = results["E5_short_depletion"]
    basis = results["E6_standard_basis"]

    coverages = [row["ensemble"]["fieller_coverage"] for row in sweep["sweep"]]
    coverages.append(sweep["degraded_programme"]["ensemble"]["fieller_coverage"])
    coverages.append(noise["ensemble_n12"]["fieller_coverage"])
    coverages.append(noise["ensemble_n24"]["fieller_coverage"])
    identity_errors = [oracle["stderr_identity_relative_difference"]]
    identity_errors += [row["stderr_identity_relative_difference"] for row in sweep["sweep"]]

    checks = [
        {
            "id": "AC1",
            "criterion": "noise-free x-intercept recovers G to better than 1e-9 relative",
            "observed": abs(oracle["relative_error"]),
            "threshold": IDENTITY_TOLERANCE,
            "met": abs(oracle["relative_error"]) < IDENTITY_TOLERANCE,
        },
        {
            "id": "AC2",
            "criterion": "exact linear-perturbation prediction matches the refit for every offset",
            "observed": bias["max_prediction_error"],
            "threshold": IDENTITY_TOLERANCE,
            "met": bias["max_prediction_error"] < IDENTITY_TOLERANCE,
        },
        {
            "id": "AC3",
            "criterion": "psig slip moves G negative and matches its exact prediction",
            "observed": max(psig["prediction_error_z_recomputed"], psig["prediction_error_z_held"]),
            "threshold": IDENTITY_TOLERANCE,
            "met": psig["sign_is_negative"]
            and max(psig["prediction_error_z_recomputed"], psig["prediction_error_z_held"])
            < IDENTITY_TOLERANCE,
        },
        {
            "id": "AC4",
            "criterion": "uniform multiplicative Z error leaves G unchanged",
            "observed": zfactor["max_multiplicative_relative_shift"],
            "threshold": TIGHT_IDENTITY_TOLERANCE,
            "met": zfactor["max_multiplicative_relative_shift"] < TIGHT_IDENTITY_TOLERANCE,
        },
        {
            "id": "AC5",
            "criterion": "delta-method 95 percent coverage at f = 0.50 inside [0.935, 0.965]",
            "observed": noise["ensemble_n12"]["delta_coverage"],
            "threshold": list(COVERAGE_BAND),
            "met": COVERAGE_BAND[0] <= noise["ensemble_n12"]["delta_coverage"] <= COVERAGE_BAND[1],
            "shortfall_in_monte_carlo_standard_errors": (
                (0.95 - noise["ensemble_n12"]["delta_coverage"])
                / math.sqrt(0.95 * 0.05 / CONFIG["monte_carlo_replicates"])
            ),
            "band_half_width_in_monte_carlo_standard_errors": (
                0.015 / math.sqrt(0.95 * 0.05 / CONFIG["monte_carlo_replicates"])
            ),
        },
        {
            "id": "AC6",
            "criterion": (
                "Fieller 95 percent coverage inside [0.935, 0.965] at every setting whose error "
                "model is the fitted least-squares one: E5 f = 0.10, 0.20, 0.35, 0.50, the degraded "
                "programme, E1 n = 12 and E1 n = 24. E1b violates that model by construction and is "
                "excluded from this criterion and reported separately"
            ),
            "observed": [min(coverages), max(coverages)],
            "threshold": list(COVERAGE_BAND),
            "met": all(COVERAGE_BAND[0] <= value <= COVERAGE_BAND[1] for value in coverages),
        },
        {
            "id": "AC7",
            "criterion": "library delta standard error equals the collapsed closed form",
            "observed": max(identity_errors),
            "threshold": TIGHT_IDENTITY_TOLERANCE,
            "met": max(identity_errors) < TIGHT_IDENTITY_TOLERANCE,
        },
        {
            "id": "AC8",
            "criterion": (
                "standard-basis change scales static and dynamic G by exactly the declared "
                "standard-pressure ratio SPE_STANDARD/US_CONTRACTUAL_STANDARD = "
                "14.695948775513450/14.73, the constants the library carries rather than the "
                "rounded 14.696/14.73"
            ),
            "observed": max(basis["static_identity_error"], basis["dynamic_identity_error"]),
            "threshold": TIGHT_IDENTITY_TOLERANCE,
            "met": max(basis["static_identity_error"], basis["dynamic_identity_error"])
            < TIGHT_IDENTITY_TOLERANCE,
        },
        {
            "id": "AC9",
            "criterion": "degraded programme reaches the unbounded Fieller regime in >= 10 percent of draws",
            "observed": sweep["degraded_programme"]["ensemble"]["unbounded_fraction"],
            "threshold": 0.10,
            "met": sweep["degraded_programme"]["ensemble"]["unbounded_fraction"] >= 0.10,
        },
    ]
    return checks


def evaluate_inconclusive(results: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate the three pre-registered conditions that would make the case inconclusive."""
    noise = results["E1_random_noise"]["ensemble_n12"]
    degraded = results["E5_short_depletion"]["degraded_programme"]["ensemble"]
    ranking = results["E7_ranking"]
    spread_ratio = noise["sampling_sd_scf"] / noise["median_delta_stderr_scf"]
    refusal_rate = degraded["library_refusals"] / degraded["replicates_requested"]
    return [
        {
            "condition": "ranking of the top two sources changes when sigma_p is halved or doubled",
            "observed": ranking["top_two_by_assumed_sigma"],
            "triggered": not ranking["ranking_stable_under_sigma_factor_two"],
        },
        {
            "condition": "Monte Carlo sd and median delta standard error differ by more than 1.5x",
            "observed": spread_ratio,
            "triggered": not (1.0 / 1.5 <= spread_ratio <= 1.5),
        },
        {
            "condition": "degraded programme library refusal rate above 25 percent",
            "observed": refusal_rate,
            "triggered": refusal_rate > 0.25,
        },
    ]


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def bscf(value: float) -> str:
    """Format a standard gas volume in Bscf, for the console summary only."""
    return f"{value / 1.0e9:,.3f}"


def print_summary(
    results: dict[str, Any], acceptance: list[dict[str, Any]], inconclusive: list[dict[str, Any]]
) -> None:
    """Print a readable console summary of the whole study."""
    truth = CONFIG["gas_in_place_scf"]
    oracle = results["E0_oracle"]
    print("Case A3: what dominates the uncertainty in a gas-in-place estimate")
    print("=" * 96)
    print(
        f"true G                          {bscf(truth)} Bscf   p_i = {CONFIG['initial_pressure_psia']:g} psia"
    )
    print(
        f"Z_i, p_i/Z_i                    {oracle['initial_z_factor']:.6f}, "
        f"{oracle['initial_p_over_z_psia']:.2f} psia"
    )
    print(
        f"E0 noise-free recovery          {bscf(oracle['gas_in_place_scf'])} Bscf, "
        f"relative error {oracle['relative_error']:+.3e}"
    )
    print(f"   generator balance residual   {oracle['generator_max_residual_p_over_z_psia']:.3e} psia of p/Z")
    print(
        f"   noise-free holdout residual  {oracle['holdout_rmse_p_over_z_psia']:.3e} psia of p/Z "
        f"(exact by construction; the informative holdout is under E1)"
    )

    noise = results["E1_random_noise"]
    print()
    print(f"E1 random scatter, sigma_p = {noise['pressure_sigma_psia']:g} psia")
    print(
        f"   Monte Carlo sd of G          {bscf(noise['ensemble_n12']['sampling_sd_scf'])} Bscf "
        f"({noise['ensemble_n12']['sampling_sd_scf'] / truth:.2%})"
    )
    print(f"   median delta-method SE       {bscf(noise['ensemble_n12']['median_delta_stderr_scf'])} Bscf")
    print(
        f"   coverage delta / Fieller     {noise['ensemble_n12']['delta_coverage']:.3f} / "
        f"{noise['ensemble_n12']['fieller_coverage']:.3f}"
    )
    print(
        f"   sd ratio n=24 over n=12      {noise['sd_ratio_n24_over_n12']:.4f} "
        f"(1/sqrt(2) = {noise['root_n_prediction']:.4f})"
    )
    holdout = noise["holdout"]
    print(
        f"   holdout: fit surveys 1-{holdout['training_surveys']} "
        f"(f = {holdout['training_depletion_fraction']:.2f}), predict the rest"
    )
    print(
        f"      G from training only      {bscf(holdout['gas_in_place_from_training_scf'])} "
        f"+/- {bscf(holdout['stderr_from_training_scf'])} Bscf, against "
        f"{bscf(holdout['gas_in_place_from_full_history_scf'])} Bscf from the full history"
    )
    print(
        f"      holdout RMSE              {holdout['rmse_p_over_z_psia']:.1f} psia of p/Z "
        f"= {holdout['rmse_fraction_of_initial_p_over_z']:.3%} of p_i/Z_i"
    )

    drift = results["E1b_correlated_noise"]
    print()
    print(f"E1b drifting gauge, AR(1) rho = {drift['lag1_correlation_imposed']:g}")
    print(f"   Monte Carlo sd of G          {bscf(drift['ensemble']['sampling_sd_scf'])} Bscf")
    print(
        f"   median delta-method SE       {bscf(drift['ensemble']['median_delta_stderr_scf'])} Bscf "
        f"(understates the truth by {drift['sd_over_median_delta_stderr']:.2f}x)"
    )
    print(
        f"   coverage delta / Fieller     {drift['ensemble']['delta_coverage']:.3f} / "
        f"{drift['ensemble']['fieller_coverage']:.3f} at nominal 0.95"
    )
    for name, entry in drift["named_realisation"]["bootstraps"].items():
        print(f"   bootstrap {name:<18} {bscf(entry['standard_error_scf'])} Bscf")

    print()
    print("E2 shared calibration bias (noise free)")
    print(
        f"   {'offset psia':>12} {'dG, Z recomputed':>18} {'dG, Z held':>14} {'card rule':>12} "
        f"{'card understates by':>20}"
    )
    for row in results["E2_shared_bias"]["grid"]:
        factor = row["card_rule_understatement_factor_z_recomputed"]
        factor_text = "-" if factor is None else f"{factor:.2f}x"
        print(
            f"   {row['offset_psia']:>12.3f} {row['relative_shift_z_recomputed']:>18.4%} "
            f"{row['relative_shift_z_held']:>14.4%} {row['card_rule_relative_shift']:>12.4%} "
            f"{factor_text:>20}"
        )
    print("   invariance to survey count at +25 psia:")
    for row in results["E2_shared_bias"]["invariance_to_sample_size"]:
        print(
            f"      n = {row['n_surveys']:>2}: bias {row['relative_shift']:+.4%}, "
            f"design one-sigma {row['design_stderr_relative']:.4%}"
        )

    psig = results["E3_psig_for_psia"]
    print()
    print("E3 psig supplied where psia was required")
    print(
        f"   shift, Z recomputed          {bscf(psig['shift_z_recomputed_scf'])} Bscf "
        f"({psig['relative_shift_z_recomputed']:+.4%})"
    )
    print(
        f"   shift, Z held at true p      {bscf(psig['shift_z_held_scf'])} Bscf "
        f"({psig['relative_shift_z_held']:+.4%})"
    )
    print(
        f"   card rule 14.696 G/(p_i/Z_i) {bscf(psig['card_rule_of_thumb_shift_scf'])} Bscf "
        f"({psig['card_rule_relative_shift']:+.4%})"
    )
    print(f"   sign negative as reviewed    {psig['sign_is_negative']}")
    print(f"   size in design sigma units   {psig['shift_in_units_of_design_sigma']:+.2f}")
    print(f"   coverage of truth with slip  {psig['coverage_of_truth_with_offset_present']:.3f}")

    zf = results["E4_z_factor"]
    print()
    print("E4 deviation factor")
    print(
        f"   uniform multiplicative error, worst relative shift in G "
        f"{zf['max_multiplicative_relative_shift']:.3e}"
    )
    for row in zf["correlation_choice"]:
        print(
            f"   {row['method']:<18} G {bscf(row['gas_in_place_scf'])} Bscf "
            f"({row['relative_shift']:+.4%}); Z differs by "
            f"{row['relative_z_difference_first']:+.4%} at {zf['observed_pressure_window_psia'][1]:.0f} psia "
            f"and {row['relative_z_difference_last']:+.4%} at "
            f"{zf['observed_pressure_window_psia'][0]:.0f} psia"
        )
    for row in zf["correlation_profile_over_window"]:
        print(
            f"   {row['method']:<18} scanned at {row['scan_points']} pressures across the window: "
            f"worst Z difference {row['signed_difference_at_worst']:+.4%} at "
            f"{row['pressure_at_worst_psia']:.0f} psia"
        )
    for row in zf["tilt"]:
        print(
            f"   tilt {row['tilt_across_window']:+.3f} across the window -> "
            f"{row['relative_shift']:+.4%} in G (amplification {row['amplification']:.2f})"
        )

    print()
    print("E5 observed depletion, same noise")
    print(
        f"   {'f':>6} {'G Bscf':>10} {'delta SE':>10} {'bootstrap':>10} {'MC sd':>10} {'g':>9} "
        f"{'Fieller':>28}"
    )
    for row in results["E5_short_depletion"]["sweep"]:
        fieller = row["fieller"]
        text = (
            f"[{bscf(fieller['lower_scf'])}, {bscf(fieller['upper_scf'])}]"
            if fieller["bounded"]
            else f"{fieller['kind']}"
        )
        print(
            f"   {row['depletion_fraction']:>6.2f} {bscf(row['gas_in_place_scf']):>10} "
            f"{bscf(row['delta_stderr_scf']):>10} "
            f"{bscf(row['bootstrap_iid']['standard_error_scf']):>10} "
            f"{bscf(row['ensemble']['sampling_sd_scf']):>10} {row['fieller_g']:>9.4f} {text:>28}"
        )
    degraded = results["E5_short_depletion"]["degraded_programme"]
    print(
        f"   degraded programme: n = {degraded['n_surveys']}, f = {degraded['depletion_fraction']:g}, "
        f"sigma_p = {degraded['pressure_sigma_psia']:g} psia"
    )
    print(
        f"      G {bscf(degraded['gas_in_place_scf'])} Bscf, delta SE "
        f"{bscf(degraded['delta_stderr_scf'])} Bscf, Fieller {degraded['fieller']['kind']} "
        f"g = {degraded['fieller']['g']:.3f}"
    )
    print(
        f"      Monte Carlo sd {bscf(degraded['ensemble']['sampling_sd_scf'])} Bscf; "
        f"unbounded Fieller in {degraded['ensemble']['unbounded_fraction']:.1%} of draws; "
        f"coverage delta {degraded['ensemble']['delta_coverage']:.3f} vs Fieller "
        f"{degraded['ensemble']['fieller_coverage']:.3f}"
    )

    basis = results["E6_standard_basis"]
    print()
    print("E6 standard-condition basis 14.696 against 14.73 psia")
    print(f"   static volumetric G shift    {basis['static_relative_shift']:+.4%}")
    print(
        f"   dynamic p/Z G shift          {basis['dynamic_relative_shift']:+.4%} "
        f"(same scale, inherited from cumulative production)"
    )

    ranking = results["E7_ranking"]
    print()
    print(f"E7 ranking at sigma_p = {CONFIG['pressure_sigma_psia']:g} psia")
    for row in ranking["rankings_by_assumed_sigma"][f"sigma_{CONFIG['pressure_sigma_psia']:g}_psia"]:
        print(f"   {row['relative_effect']:>10.4%}  {row['source']}")
    print(
        f"   ranking stable under a factor of two in sigma_p: "
        f"{ranking['ranking_stable_under_sigma_factor_two']}"
    )
    for key, pair in ranking["top_two_by_assumed_sigma"].items():
        print(f"      {key:<18} first: {pair[0]}; second: {pair[1]}")
    print()
    print("   candidate next steps, one-sigma random plus systematic, as a fraction of G")
    for row in ranking["options"]:
        print(
            f"      {row['total_relative']:>8.4%} = {row['design_stderr_relative']:.4%} random + "
            f"{row['bias_relative']:.4%} systematic   {row['option']}"
        )
    print(f"   best of the four interventions: {ranking['best_option']}")
    print(
        f"      margin over {ranking['best_option_runner_up']}: "
        f"{ranking['best_option_margin_relative']:.4%} of G, which a residual datum error of "
        f"{ranking['residual_datum_error_break_even_psia']:.2f} psia would consume"
    )

    print()
    print("Acceptance")
    for check in acceptance:
        status = "met" if check["met"] else "NOT MET"
        print(f"   {check['id']} {status:<8} {check['criterion']}")
        print(f"        observed {check['observed']}  threshold {check['threshold']}")
    print("Pre-registered inconclusive conditions")
    for condition in inconclusive:
        status = "TRIGGERED" if condition["triggered"] else "not triggered"
        print(f"   {status:<14} {condition['condition']}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build_results() -> dict[str, Any]:
    """Run every experiment in order and return the complete result mapping."""
    oracle = experiment_0_oracle()
    noise = experiment_1_random_noise()
    drift = experiment_1b_correlated_noise()
    bias = experiment_2_shared_bias()
    psig = experiment_3_psig()
    zfactor = experiment_4_z_factor()
    sweep = experiment_5_short_depletion()
    basis = experiment_6_standard_basis()
    ranking = experiment_7_ranking(oracle, bias, psig, zfactor, basis)
    return {
        "E0_oracle": oracle,
        "E1_random_noise": noise,
        "E1b_correlated_noise": drift,
        "E2_shared_bias": bias,
        "E3_psig_for_psia": psig,
        "E4_z_factor": zfactor,
        "E5_short_depletion": sweep,
        "E6_standard_basis": basis,
        "E7_ranking": ranking,
    }


LIMITATIONS = (
    "Synthetic throughout. No field data, no simulator execution, no third-party dataset.",
    "The generator and the estimator share the volumetric tank assumption, so this measures a "
    "measurement error budget, not model adequacy.",
    "Every mechanism that biases a p/Z line physically -- aquifer support, rock and connate-water "
    "expansion, retrograde condensation, multi-tank communication -- is excluded by construction "
    "and is larger than anything ranked here.",
    "sigma_p = 45 psia is an assumed representativeness figure for a volume-averaged shut-in "
    "pressure, not a measured gauge specification. The ranking is conditional on it.",
    "The shared calibration bias is treated as a single unknown constant, not as a distribution. "
    "No prior is placed on its size.",
    "The Monte Carlo noise is applied to the reported series only and never feeds back into the "
    "balance, which is the NoiseModel contract, not a claim about real measurement physics.",
    "Deviation-factor differences are between published correlations, not against laboratory PVT. "
    "The repository's own check.py compares DAK with NIST reference equations of state for pure "
    "methane and reports a signed range of -1.696 to -0.129 percent across its sampled corners, a "
    "wider spread than the correlation-choice row of the ranking table uses.",
    "Cumulative production is never perturbed. The abscissa is the noise-free generated volume in "
    "every experiment, so this is an error budget on the ordinate only. A metering or allocation "
    "error scales the x-intercept by exactly the same factor (the E6 rescale identity), which would "
    "place a 1 percent metering bias above every row of the ranking table, and an error in the "
    "abscissa also violates the errors-free-regressor assumption that ordinary least squares rests "
    "on, biasing the slope rather than only widening it.",
    "Gas gravity, composition and reservoir temperature are treated as exactly known. An error in "
    "any of them is a shape error on Z(p), which is the mechanism this case finds matters most.",
    "The calibrated option in the next-measurement table is modelled as leaving no systematic "
    "behind. A residual datum error above residual_datum_error_break_even_psia reverses the "
    "recommendation.",
    "The pressure error is homoscedastic and additive in psia over a window from 4500 down to "
    "2071 psia. A proportional error would tilt the line rather than scatter it, and by this case's "
    "own tilt result a tilt is the damaging mode. No heteroscedastic case was run.",
    "The estimator is unweighted ordinary least squares by declaration. No weighted, "
    "errors-in-variables or robust fit was tried, and under a non-constant ordinate variance that "
    "choice would change every standard error reported here.",
    "The abscissa grid is evenly spaced, that is, constant offtake. The design formula, the 1/f "
    "scaling and the short-depletion penalty all rest on that geometry; real programmes have "
    "irregular spacing and shut-in timing that correlates with rate.",
    "Every percentage is for one synthetic tank at G = 100 Bscf, p_i = 4500 psia, T = 200 degF and "
    "gamma = 0.65. No sensitivity to initial pressure, temperature or gravity was run, so the "
    "magnitudes are not known to transfer to another reservoir.",
)


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, run the study inside a run record, and write the artefacts."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="fresh run directory; it must be empty or absent")
    args = parser.parse_args(argv)

    # An out-of-range correlation evaluation is a silent extrapolation, so make it a hard failure
    # rather than a warning that scrolls past. The pressure window here is comfortably inside both
    # published windows; if that ever stops being true the run must stop, not extrapolate.
    warnings.simplefilter("error", RangeWarning)

    with RunRecord.open(
        args.out,
        label="A3 gas-in-place uncertainty experiments",
        config=CONFIG,
        seed=CONFIG["seed"],
        settings={
            "identity_tolerance": IDENTITY_TOLERANCE,
            "tight_identity_tolerance": TIGHT_IDENTITY_TOLERANCE,
            "coverage_band": list(COVERAGE_BAND),
        },
        repo_root=".",
    ) as run:
        for declared in DECLARED_INPUTS:
            path = pathlib.Path(declared)
            if path.is_file():
                run.add_input(path, role="source" if path.suffix == ".py" else "protocol")

        results = build_results()
        acceptance = evaluate_acceptance(results)
        inconclusive = evaluate_inconclusive(results)
        summary = {
            "case_id": CONFIG["case_id"],
            "config": CONFIG,
            "results": results,
            "acceptance": acceptance,
            "all_acceptance_criteria_met": all(check["met"] for check in acceptance),
            "inconclusive_conditions": inconclusive,
            "any_inconclusive_condition_triggered": any(c["triggered"] for c in inconclusive),
            "limitations": list(LIMITATIONS),
        }
        run.write_json("summary.json", summary)

        ranking = results["E7_ranking"]
        run.metrics(
            noise_free_relative_error=results["E0_oracle"]["relative_error"],
            random_noise_relative_sd=results["E1_random_noise"]["ensemble_n12"]["sampling_sd_scf"]
            / CONFIG["gas_in_place_scf"],
            psig_relative_shift=results["E3_psig_for_psia"]["relative_shift_z_recomputed"],
            correlation_choice_relative_shift=max(
                abs(row["relative_shift"]) for row in results["E4_z_factor"]["correlation_choice"]
            ),
            multiplicative_z_relative_shift=results["E4_z_factor"]["max_multiplicative_relative_shift"],
            standard_basis_relative_shift=results["E6_standard_basis"]["static_relative_shift"],
            degraded_unbounded_fieller_fraction=results["E5_short_depletion"]["degraded_programme"][
                "ensemble"
            ]["unbounded_fraction"],
            best_next_step=ranking["best_option"],
            all_acceptance_criteria_met=summary["all_acceptance_criteria_met"],
        )
        for check in acceptance:
            run.note(f"{check['id']} {'met' if check['met'] else 'NOT MET'}: {check['criterion']}")
        run.note(
            "The evidence card's rule of thumb for a shared offset, c*G/(p_i/Z_i), is the Z = 1 "
            "special case. With a real Z(p) and Z recomputed at the reported pressure it understates "
            f"the shift by a factor of "
            f"{results['E3_psig_for_psia']['card_rule_understatement_factor']:.2f} here."
        )
        for limitation in LIMITATIONS:
            run.limitation(limitation)

        print_summary(results, acceptance, inconclusive)
        print()
        print(f"run directory: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

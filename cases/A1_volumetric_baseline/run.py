"""Case A1 -- volumetric baseline: does the p/Z inverse recover a known gas in place exactly.

Executable study for ``cases/A1_volumetric_baseline/protocol.md``. Four experiments on a
single fixed design:

1. noise-free recovery with a constant deviation factor, where the p/Z line is exactly
   straight and the recovery is a statement about floating-point conditioning alone;
2. the same with a pressure-dependent Dranchuk-Abou-Kassem deviation factor, fitted both
   consistently and with the initial Z reused throughout, which is the inconsistency that
   actually biases the answer;
3. a 1000-realisation Monte Carlo that checks whether the reported standard error of the
   x-intercept matches the spread it claims to describe;
4. the cost of the extrapolation, by recovering from 50 percent and from 10 percent
   observed depletion with the same eleven noise draws.

Two post-hoc diagnostics were added after run-005 and are neither pre-registered nor
gated: D1 seeds known defects into the experiment-1 arm and reports which classes the
design can see at all, and D2 sweeps the depletion window across the minimum of Z(p) to
test whether the sign of experiment 2b's bias generalises. Neither changed any threshold.

Standard library only. The forward generator is ``reservoir_lab.depletion`` and the
inverse is ``reservoir_lab.material_balance``; they share no code, so a coding slip in one
of them does not cancel against the other. They do share the physical assumption set, and
diagnostic D1 measures how narrow the resulting detection is: a uniform error in the
ordinate, including a wrong standard-volume basis, is invisible to this comparison.

Usage::

    PYTHONPATH=src python3 cases/A1_volumetric_baseline/run.py --out artifacts/A1_volumetric_baseline/run-001
"""

from __future__ import annotations

import argparse
import math
import statistics
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from reservoir_lab.depletion import NOISE_FREE, DepletionHistory, NoiseModel  # noqa: E402
from reservoir_lab.depletion import simulate_volumetric_depletion as simulate  # noqa: E402
from reservoir_lab.gas_properties import pseudocritical_sutton, z_factor  # noqa: E402
from reservoir_lab.material_balance import PZFit, fit_pz_depletion  # noqa: E402
from reservoir_lab.provenance import RunRecord, canonical_hash  # noqa: E402
from reservoir_lab.regression import student_t_quantile  # noqa: E402
from reservoir_lab.units import SPE_STANDARD, StandardConditions  # noqa: E402

# ---------------------------------------------------------------------------
# Fixed design. Section 4 of the protocol; none of these is chosen after a result.
# ---------------------------------------------------------------------------

CASE_ID = "A1_volumetric_baseline"

GAS_IN_PLACE_SCF = 1.0e11
INITIAL_PRESSURE_PSIA = 4000.0
TEMPERATURE_DEGR = 640.0
GAS_RATE_SCF_PER_DAY = 2.5e7
N_POINTS = 11
CONSTANT_Z = 0.900
SPECIFIC_GRAVITY = 0.65

#: 200 psia, not the 14.696 psia default. The generator scans p/Z over
#: ``[floor, p_i]``; at 14.696 psia the Dranchuk-Abou-Kassem reduced pressure is 0.022,
#: far outside the published window [0.2, 30.0]. At 200 psia it is 0.298 and every
#: evaluation in this run sits inside the window the correlation was fitted on.
MINIMUM_PRESSURE_PSIA = 200.0
SOLVER_TOLERANCE = 1.0e-12
MAX_ITERATIONS = 200

PRESSURE_SIGMA_PSIA = 5.0
MONTE_CARLO_REPLICATES = 1000
MONTE_CARLO_FIRST_SEED = 1000
EXTRAPOLATION_SEED = 20260913
NOISE_FREE_SEED = 0

DEPLETION_FRACTION_DEEP = 0.50
DEPLETION_FRACTION_SHALLOW = 0.10

# Predeclared acceptance thresholds, protocol section 6.
TOLERANCE_CONSTANT_Z = 5.0e-12
TOLERANCE_VARIABLE_Z = 2.0e-11
INCONSISTENT_Z_BIAS_BAND = (0.01, 0.10)
SPREAD_RATIO_BAND = (0.90, 1.15)
MEAN_BIAS_LIMIT = 5.0e-4
COVERAGE_BAND = (0.92, 0.97)
MEAN_SE_RATIO_BAND = (0.95, 1.00)
PREDICTED_STDERR_RATIO = 6.2005
STDERR_RATIO_TOLERANCE = 0.05

PSEUDOCRITICALS = pseudocritical_sutton(SPECIFIC_GRAVITY)


# ---------------------------------------------------------------------------
# Independent oracles, coded here rather than taken from the library
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClosedFormLine:
    """Straight-line fit and inverse-prediction interval written out independently.

    The library reaches the same numbers through ``regression.ols_line`` and the general
    delta-method ``regression.x_intercept``. This is a second implementation of the
    classical collapsed form, so a disagreement localises to one of the two code paths.
    It is an independent implementation, not an independent formula.
    """

    slope: float
    intercept: float
    x_intercept: float
    stderr: float
    residual_sd: float
    x_mean: float
    sxx: float


def closed_form_line(xs: Sequence[float], ys: Sequence[float]) -> ClosedFormLine:
    """Fit ``y = intercept + slope * x`` by least squares and extrapolate to ``y = 0``.

    Parameters
    ----------
    xs, ys :
        Abscissa and ordinate, equal length, at least three points.

    Returns
    -------
    ClosedFormLine
        Coefficients, the x-intercept, and its inverse-prediction standard error
        ``(s/b) * sqrt(1/n + (x0 - xbar)^2 / Sxx)``.
    """
    n = len(xs)
    x_mean = math.fsum(xs) / n
    y_mean = math.fsum(ys) / n
    sxx = math.fsum((x - x_mean) ** 2 for x in xs)
    sxy = math.fsum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True))
    slope = sxy / sxx
    intercept = y_mean - slope * x_mean
    x_intercept = -intercept / slope
    residual_sum_squares = math.fsum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys, strict=True))
    residual_sd = math.sqrt(residual_sum_squares / (n - 2))
    variance = (residual_sd**2 / slope**2) * (1.0 / n + (x_intercept - x_mean) ** 2 / sxx)
    return ClosedFormLine(
        slope=slope,
        intercept=intercept,
        x_intercept=x_intercept,
        stderr=math.sqrt(variance),
        residual_sd=residual_sd,
        x_mean=x_mean,
        sxx=sxx,
    )


def two_point_gas_in_place(x1: float, y1: float, x2: float, y2: float) -> float:
    """Return the x-intercept of the line through two points, with no least squares.

    For an exactly collinear series any two distinct points determine the line, so this
    is an oracle for the noise-free experiments that shares nothing with the estimator:
    no sums of squares, no normal equations, no delta method.
    """
    return x1 + y1 * (x2 - x1) / (y1 - y2)


def leverage(depletion_fraction: float) -> float:
    """Return ``1/n + (G - xbar)^2 / Sxx`` for the evenly spaced design of this case.

    With ``x_i = i * fG/(n-1)`` the design moments are exact:
    ``xbar = fG/2`` and ``Sxx = f^2 G^2 n(n+1) / (12(n-1))``. This is the squared norm of
    the row that maps the ordinate onto the fitted value at the x-intercept, so its square
    root is the amplification the extrapolation applies to any ordinate perturbation.
    """
    return leverage_at(GAS_IN_PLACE_SCF, depletion_fraction)


def leverage_at(x_intercept: float, depletion_fraction: float) -> float:
    """Return ``1/n + (x0 - xbar)^2 / Sxx`` at an arbitrary x-intercept.

    :func:`leverage` is this evaluated at the true gas in place, which is what a
    prediction made before the run can use. The estimator necessarily evaluates it at the
    *fitted* x-intercept, because that is the only one it knows. The two differ by the
    estimation error, and on a long extrapolation that difference is not negligible.
    """
    sxx_coefficient = N_POINTS * (N_POINTS + 1) / (12.0 * (N_POINTS - 1))
    x_mean = 0.5 * depletion_fraction * GAS_IN_PLACE_SCF
    sxx = sxx_coefficient * (depletion_fraction * GAS_IN_PLACE_SCF) ** 2
    return 1.0 / N_POINTS + (x_intercept - x_mean) ** 2 / sxx


# ---------------------------------------------------------------------------
# Forward generation
# ---------------------------------------------------------------------------


def constant_z(_pressure_psia: float) -> float:
    """Return a pressure-independent deviation factor, so that p/Z is linear in p."""
    return CONSTANT_Z


def dak_z(pressure_psia: float) -> float:
    """Return the Dranchuk-Abou-Kassem deviation factor at the case temperature."""
    return z_factor(pressure_psia, TEMPERATURE_DEGR, PSEUDOCRITICALS, method="dak")


def depletion_schedule(depletion_fraction: float) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Return times and interval rates that deplete a fixed fraction on a uniform Gp grid.

    A constant rate over equal intervals puts the cumulative production on an evenly
    spaced grid, which is what makes the design moments in :func:`leverage` exact rather
    than approximate.
    """
    duration_days = GAS_IN_PLACE_SCF * depletion_fraction / GAS_RATE_SCF_PER_DAY
    step_days = duration_days / (N_POINTS - 1)
    times = tuple(index * step_days for index in range(N_POINTS))
    rates = tuple(GAS_RATE_SCF_PER_DAY for _ in range(N_POINTS - 1))
    return times, rates


def generate(
    *,
    depletion_fraction: float,
    z_of_pressure: Callable[[float], float],
    noise: NoiseModel,
    seed: int,
) -> DepletionHistory:
    """Run the forward generator on this case's fixed tank and schedule."""
    times, rates = depletion_schedule(depletion_fraction)
    return simulate(
        gas_in_place_scf=GAS_IN_PLACE_SCF,
        initial_pressure_psia=INITIAL_PRESSURE_PSIA,
        temperature_degr=TEMPERATURE_DEGR,
        times_days=times,
        gas_rates_scf_per_day=rates,
        z_of_pressure=z_of_pressure,
        standard=SPE_STANDARD,
        noise=noise,
        seed=seed,
        minimum_pressure_psia=MINIMUM_PRESSURE_PSIA,
        solver_tolerance=SOLVER_TOLERANCE,
        max_iterations=MAX_ITERATIONS,
    )


def fit_summary(fit: PZFit) -> dict[str, Any]:
    """Return the fields of a :class:`PZFit` that the report quotes."""
    return {
        "gas_in_place_scf": fit.gas_in_place_scf,
        "gas_in_place_stderr_scf": fit.gas_in_place_stderr_scf,
        "relative_error": fit.gas_in_place_scf / GAS_IN_PLACE_SCF - 1.0,
        "slope_psia_per_scf": fit.slope,
        "intercept_psia": fit.intercept,
        "slope_stderr_psia_per_scf": fit.slope_stderr,
        "covariance_psia2_per_scf": fit.covariance,
        "r_squared": fit.r_squared,
        "max_abs_residual_psia": max(abs(value) for value in fit.residuals),
        "n_points": fit.n_points,
        "degrees_of_freedom": fit.degrees_of_freedom,
        "fieller_g": fit.fieller_g,
        "depletion_fraction_observed": fit.depletion_fraction_observed,
        "warnings": list(fit.warnings),
    }


# ---------------------------------------------------------------------------
# Experiment 1: noise-free recovery, constant Z
# ---------------------------------------------------------------------------


def experiment_1() -> dict[str, Any]:
    """Recover G from an exactly straight, noise-free p/Z line."""
    history = generate(
        depletion_fraction=DEPLETION_FRACTION_DEEP,
        z_of_pressure=constant_z,
        noise=NOISE_FREE,
        seed=NOISE_FREE_SEED,
    )
    produced = history.cumulative_gas_scf
    ordinate = history.p_over_z_psia()
    fit = fit_pz_depletion(produced, ordinate)
    closed = closed_form_line(produced, ordinate)
    oracle = two_point_gas_in_place(produced[0], ordinate[0], produced[-1], ordinate[-1])

    initial_p_over_z = history.truth.initial_p_over_z_psia
    generator_residual = history.max_abs_residual_p_over_z_psia
    # Inconclusiveness guard, protocol section 8: the generator's own numerical error must
    # be well below the effect the acceptance threshold is measuring.
    resolvable = generator_residual <= 1.0e-2 * TOLERANCE_CONSTANT_Z * initial_p_over_z

    relative_error = fit.gas_in_place_scf / GAS_IN_PLACE_SCF - 1.0
    oracle_difference = abs(fit.gas_in_place_scf - oracle) / GAS_IN_PLACE_SCF
    amplification = math.sqrt(leverage(DEPLETION_FRACTION_DEEP) * N_POINTS)

    return {
        "description": "noise-free, constant Z, 50 percent observed depletion",
        "initial_p_over_z_psia": initial_p_over_z,
        "initial_z_factor": history.truth.initial_z_factor,
        "final_pressure_psia": history.pressures_psia[-1],
        "generator_max_abs_residual_p_over_z_psia": generator_residual,
        "generator_warnings": list(history.warnings),
        "fit": fit_summary(fit),
        "closed_form_gas_in_place_scf": closed.x_intercept,
        "closed_form_relative_difference": abs(closed.x_intercept - fit.gas_in_place_scf) / GAS_IN_PLACE_SCF,
        "two_point_oracle_gas_in_place_scf": oracle,
        "two_point_oracle_relative_difference": oracle_difference,
        "condition_number_sqrt_h": math.sqrt(leverage(DEPLETION_FRACTION_DEEP)),
        "condition_number_sqrt_hn": amplification,
        "conditioning_bound_from_generator_residual": amplification * generator_residual / initial_p_over_z,
        "predicted_tolerance": TOLERANCE_CONSTANT_Z,
        "generator_error_resolvable": resolvable,
        "criterion_A1_met": abs(relative_error) <= TOLERANCE_CONSTANT_Z,
        "criterion_A2_met": oracle_difference <= TOLERANCE_CONSTANT_Z,
    }


# ---------------------------------------------------------------------------
# Experiment 2: pressure-dependent Z, consistent and inconsistent
# ---------------------------------------------------------------------------


def experiment_2() -> dict[str, Any]:
    """Recover G with a pressure-dependent Z, fitted consistently and with Z frozen at Zi."""
    history = generate(
        depletion_fraction=DEPLETION_FRACTION_DEEP,
        z_of_pressure=dak_z,
        noise=NOISE_FREE,
        seed=NOISE_FREE_SEED,
    )
    produced = history.cumulative_gas_scf
    pressures = history.pressures_psia
    z_factors = history.z_factors

    consistent = fit_pz_depletion(produced, history.p_over_z_psia())
    consistent_error = consistent.gas_in_place_scf / GAS_IN_PLACE_SCF - 1.0
    oracle = two_point_gas_in_place(
        produced[0], history.p_over_z_psia()[0], produced[-1], history.p_over_z_psia()[-1]
    )

    # The curvature the p/Z transform removes: how far the raw pressure series departs
    # from the straight line through its own endpoints.
    def pressure_chord(cumulative: float) -> float:
        span = produced[-1] - produced[0]
        return pressures[0] + (pressures[-1] - pressures[0]) * (cumulative - produced[0]) / span

    pressure_nonlinearity_psia = max(
        abs(p - pressure_chord(x)) for x, p in zip(produced, pressures, strict=True)
    )

    # The inconsistency that does bias G: the analyst reuses the initial deviation factor.
    initial_z = z_factors[0]
    frozen_ordinate = tuple(p / initial_z for p in pressures)
    frozen = fit_pz_depletion(produced, frozen_ordinate)
    frozen_error = frozen.gas_in_place_scf / GAS_IN_PLACE_SCF - 1.0
    ordinate_shortfall = max(
        abs(frozen_value / true_value - 1.0)
        for frozen_value, true_value in zip(frozen_ordinate, history.p_over_z_psia(), strict=True)
    )

    bias_in_band = (
        frozen_error < 0.0 and INCONSISTENT_Z_BIAS_BAND[0] <= abs(frozen_error) <= INCONSISTENT_Z_BIAS_BAND[1]
    )

    return {
        "description": "noise-free, Dranchuk-Abou-Kassem Z, 50 percent observed depletion",
        "pseudocritical_temperature_degr": PSEUDOCRITICALS.temperature_degr,
        "pseudocritical_pressure_psia": PSEUDOCRITICALS.pressure_psia,
        "pseudocritical_correlation": PSEUDOCRITICALS.correlation,
        "initial_z_factor": initial_z,
        "final_z_factor": z_factors[-1],
        "minimum_z_factor_observed": min(z_factors),
        "initial_p_over_z_psia": history.truth.initial_p_over_z_psia,
        "final_pressure_psia": pressures[-1],
        "generator_max_abs_residual_p_over_z_psia": history.max_abs_residual_p_over_z_psia,
        "generator_warnings": list(history.warnings),
        "consistent_z": {
            "fit": fit_summary(consistent),
            "two_point_oracle_gas_in_place_scf": oracle,
            "two_point_oracle_relative_difference": abs(consistent.gas_in_place_scf - oracle)
            / GAS_IN_PLACE_SCF,
            "conditioning_bound_from_generator_residual": math.sqrt(
                leverage(DEPLETION_FRACTION_DEEP) * N_POINTS
            )
            * history.max_abs_residual_p_over_z_psia
            / history.truth.initial_p_over_z_psia,
            "predicted_tolerance": TOLERANCE_VARIABLE_Z,
            "criterion_A3_met": abs(consistent_error) <= TOLERANCE_VARIABLE_Z,
        },
        "pressure_curvature": {
            "max_abs_deviation_from_chord_psia": pressure_nonlinearity_psia,
            "as_fraction_of_initial_pressure": pressure_nonlinearity_psia / INITIAL_PRESSURE_PSIA,
        },
        "frozen_initial_z": {
            "fit": fit_summary(frozen),
            "max_relative_ordinate_shortfall": ordinate_shortfall,
            "predicted_sign": "underestimate",
            "predicted_band": list(INCONSISTENT_Z_BIAS_BAND),
            "criterion_A4_met": bias_in_band,
        },
    }


# ---------------------------------------------------------------------------
# Experiment 3: is the reported standard error meaningful
# ---------------------------------------------------------------------------


def experiment_3() -> dict[str, Any]:
    """Compare the reported x-intercept standard error with a Monte Carlo spread."""
    noise = NoiseModel(pressure_sigma_psia=PRESSURE_SIGMA_PSIA, label="gauge scatter")
    estimates: list[float] = []
    stderrs: list[float] = []
    fieller_g: list[float] = []
    failures: list[dict[str, Any]] = []

    t_critical = student_t_quantile(0.975, N_POINTS - 2)
    covered = 0
    for offset in range(MONTE_CARLO_REPLICATES):
        seed = MONTE_CARLO_FIRST_SEED + offset
        try:
            history = generate(
                depletion_fraction=DEPLETION_FRACTION_DEEP,
                z_of_pressure=constant_z,
                noise=noise,
                seed=seed,
            )
            fit = fit_pz_depletion(history.cumulative_gas_scf, history.p_over_z_psia())
        # A failed realisation is recorded with its seed and reason, never dropped: a
        # filtered ensemble is how a selected sample is manufactured.
        except Exception as error:
            failures.append({"seed": seed, "error": type(error).__name__, "message": str(error)})
            continue
        estimates.append(fit.gas_in_place_scf)
        stderrs.append(fit.gas_in_place_stderr_scf)
        fieller_g.append(fit.fieller_g)
        if abs(fit.gas_in_place_scf - GAS_IN_PLACE_SCF) <= t_critical * fit.gas_in_place_stderr_scf:
            covered += 1

    spread = statistics.stdev(estimates)
    mean_stderr = statistics.fmean(stderrs)
    mean_estimate = statistics.fmean(estimates)

    # Analytic standard error, protocol section 5.4. The ordinate noise is the pressure
    # noise divided by the constant deviation factor and the slope is (pi/Zi)/G.
    ordinate_sigma = PRESSURE_SIGMA_PSIA / CONSTANT_Z
    slope_magnitude = (INITIAL_PRESSURE_PSIA / CONSTANT_Z) / GAS_IN_PLACE_SCF
    analytic_stderr = (ordinate_sigma / slope_magnitude) * math.sqrt(leverage(DEPLETION_FRACTION_DEEP))

    spread_ratio = spread / mean_stderr
    mean_bias = mean_estimate / GAS_IN_PLACE_SCF - 1.0
    coverage = covered / len(estimates)
    monte_carlo_stderr_of_spread = 1.0 / math.sqrt(2.0 * len(estimates))

    return {
        "description": "1000 realisations, constant Z, 5 psia gauge scatter, 50 percent depletion",
        "replicates_requested": MONTE_CARLO_REPLICATES,
        "replicates_fitted": len(estimates),
        "failed_realisations": failures,
        "first_seed": MONTE_CARLO_FIRST_SEED,
        "pressure_sigma_psia": PRESSURE_SIGMA_PSIA,
        "mean_gas_in_place_scf": mean_estimate,
        "mean_relative_bias": mean_bias,
        "monte_carlo_spread_scf": spread,
        "mean_reported_stderr_scf": mean_stderr,
        "analytic_stderr_scf": analytic_stderr,
        "spread_over_mean_reported_stderr": spread_ratio,
        "mean_reported_stderr_over_analytic": mean_stderr / analytic_stderr,
        "spread_over_analytic": spread / analytic_stderr,
        "monte_carlo_stderr_of_spread_fraction": monte_carlo_stderr_of_spread,
        "t_critical_0975_dof9": t_critical,
        "coverage_of_95_percent_interval": coverage,
        "mean_fieller_g": statistics.fmean(fieller_g),
        "criterion_A5_met": SPREAD_RATIO_BAND[0] <= spread_ratio <= SPREAD_RATIO_BAND[1],
        "criterion_A6_met": abs(mean_bias) <= MEAN_BIAS_LIMIT,
        "criterion_A7_met": COVERAGE_BAND[0] <= coverage <= COVERAGE_BAND[1],
        "criterion_A8_met": MEAN_SE_RATIO_BAND[0] <= mean_stderr / analytic_stderr <= MEAN_SE_RATIO_BAND[1],
    }


# ---------------------------------------------------------------------------
# Experiment 4: what the extrapolation costs
# ---------------------------------------------------------------------------


def extrapolation_arm(depletion_fraction: float, noise: NoiseModel) -> dict[str, Any]:
    """Generate and fit one arm of the extrapolation comparison."""
    history = generate(
        depletion_fraction=depletion_fraction,
        z_of_pressure=constant_z,
        noise=noise,
        seed=EXTRAPOLATION_SEED,
    )
    produced = history.cumulative_gas_scf
    ordinate = history.p_over_z_psia()
    fit = fit_pz_depletion(produced, ordinate)
    closed = closed_form_line(produced, ordinate)
    return {
        "depletion_fraction_designed": depletion_fraction,
        "last_cumulative_gas_scf": produced[-1],
        "final_pressure_psia": history.true_pressures_psia[-1],
        "fit": fit_summary(fit),
        "relative_stderr": fit.gas_in_place_stderr_scf / fit.gas_in_place_scf,
        "closed_form_gas_in_place_scf": closed.x_intercept,
        "closed_form_stderr_scf": closed.stderr,
        "closed_form_stderr_relative_difference": abs(closed.stderr - fit.gas_in_place_stderr_scf)
        / fit.gas_in_place_stderr_scf,
        "residual_sd_psia": closed.residual_sd,
        "sqrt_leverage_at_true_g": math.sqrt(leverage(depletion_fraction)),
        "sqrt_leverage_at_fitted_g": math.sqrt(leverage_at(fit.gas_in_place_scf, depletion_fraction)),
        "pz_residuals_psia": list(fit.residuals),
    }


def experiment_4() -> dict[str, Any]:
    """Recover G from 50 and from 10 percent observed depletion with identical noise."""
    noise = NoiseModel(pressure_sigma_psia=PRESSURE_SIGMA_PSIA, label="gauge scatter")
    deep = extrapolation_arm(DEPLETION_FRACTION_DEEP, noise)
    shallow = extrapolation_arm(DEPLETION_FRACTION_SHALLOW, noise)

    stderr_ratio = shallow["fit"]["gas_in_place_stderr_scf"] / deep["fit"]["gas_in_place_stderr_scf"]
    leverage_ratio = shallow["sqrt_leverage_at_true_g"] / deep["sqrt_leverage_at_true_g"]
    fitted_leverage_ratio = shallow["sqrt_leverage_at_fitted_g"] / deep["sqrt_leverage_at_fitted_g"]
    slope_ratio = abs(deep["fit"]["slope_psia_per_scf"]) / abs(shallow["fit"]["slope_psia_per_scf"])
    residual_sd_ratio = shallow["residual_sd_psia"] / deep["residual_sd_psia"]
    deep_error = deep["fit"]["gas_in_place_scf"] - GAS_IN_PLACE_SCF
    shallow_error = shallow["fit"]["gas_in_place_scf"] - GAS_IN_PLACE_SCF

    residual_difference = max(
        abs(a - b) for a, b in zip(deep["pz_residuals_psia"], shallow["pz_residuals_psia"], strict=True)
    )

    return {
        "description": "identical eleven noise draws, 50 percent versus 10 percent observed depletion",
        "seed": EXTRAPOLATION_SEED,
        "pressure_sigma_psia": PRESSURE_SIGMA_PSIA,
        "deep": deep,
        "shallow": shallow,
        "reported_stderr_ratio": stderr_ratio,
        "sqrt_leverage_ratio_at_true_g": leverage_ratio,
        "sqrt_leverage_ratio_at_fitted_g": fitted_leverage_ratio,
        "slope_magnitude_ratio_deep_over_shallow": slope_ratio,
        "residual_sd_ratio_shallow_over_deep": residual_sd_ratio,
        "predicted_stderr_ratio": PREDICTED_STDERR_RATIO,
        "predicted_stderr_ratio_with_slope_correction": leverage_ratio * slope_ratio,
        # Post-hoc decomposition, added after run-001. The estimator evaluates the
        # leverage at the fitted x-intercept, not at the true G a prediction must use;
        # with that one substitution the reported ratio is reproduced to rounding.
        "reconstructed_stderr_ratio": fitted_leverage_ratio * slope_ratio * residual_sd_ratio,
        "reconstruction_relative_error": (fitted_leverage_ratio * slope_ratio * residual_sd_ratio)
        / stderr_ratio
        - 1.0,
        "stderr_ratio_relative_departure": stderr_ratio / PREDICTED_STDERR_RATIO - 1.0,
        "point_error_ratio": shallow_error / deep_error,
        "deep_error_scf": deep_error,
        "shallow_error_scf": shallow_error,
        "max_abs_residual_difference_psia": residual_difference,
        "criterion_A9_met": abs(stderr_ratio / PREDICTED_STDERR_RATIO - 1.0) <= STDERR_RATIO_TOLERANCE,
    }


# ---------------------------------------------------------------------------
# Diagnostic D1: which defect classes this design can see at all
#
# Added after run-005 and NOT pre-registered. No acceptance threshold in protocol
# section 6 changed and nothing here is gated. Experiments 1 and 2a report a recovery
# error of zero; that is evidence of correctness only for defects this design can
# detect, and nothing in the case established which those are. This diagnostic seeds
# known defects into the constant-Z noise-free arm of experiment 1 -- whose realised
# error is exactly 0.0 -- and reports the recovery error each one produces.
# ---------------------------------------------------------------------------

#: Ordinate scale factors probed as a multiplicative defect class.
ORDINATE_SCALE_DEFECTS = (1.0e-10, 1.0e-3, 0.5)
#: Relative cumulative-production biases probed as an abscissa defect class.
CUMULATIVE_GAS_SCALE_DEFECTS = (1.0e-3, 1.0e-2)
#: Single-point ordinate displacement, psia of p/Z.
SINGLE_POINT_SHIFT_PSIA = 0.01


def _relative_error(produced: Sequence[float], ordinate: Sequence[float]) -> float:
    """Fit one (Gp, p/Z) series and return the recovery error against the true G."""
    return fit_pz_depletion(produced, ordinate).gas_in_place_scf / GAS_IN_PLACE_SCF - 1.0


def _generate_constant_z(
    *,
    standard: StandardConditions = SPE_STANDARD,
    temperature_degr: float = TEMPERATURE_DEGR,
) -> DepletionHistory:
    """Regenerate the experiment-1 history with a possibly corrupted basis or temperature."""
    times, rates = depletion_schedule(DEPLETION_FRACTION_DEEP)
    return simulate(
        gas_in_place_scf=GAS_IN_PLACE_SCF,
        initial_pressure_psia=INITIAL_PRESSURE_PSIA,
        temperature_degr=temperature_degr,
        times_days=times,
        gas_rates_scf_per_day=rates,
        z_of_pressure=constant_z,
        standard=standard,
        noise=NOISE_FREE,
        seed=NOISE_FREE_SEED,
        minimum_pressure_psia=MINIMUM_PRESSURE_PSIA,
        solver_tolerance=SOLVER_TOLERANCE,
        max_iterations=MAX_ITERATIONS,
    )


def diagnostic_d1() -> dict[str, Any]:
    """Seed known defects into the experiment-1 arm and report what each one costs."""
    history = _generate_constant_z()
    produced = list(history.cumulative_gas_scf)
    ordinate = list(history.p_over_z_psia())
    pressures = list(history.pressures_psia)
    standard_degr = SPE_STANDARD.temperature_degf + 459.67

    cases: list[dict[str, Any]] = []

    def record(name: str, defect_class: str, magnitude: str, relative_error: float) -> float:
        cases.append(
            {
                "name": name,
                "defect_class": defect_class,
                "magnitude": magnitude,
                "recovery_relative_error": relative_error,
                "detected_at_A1_gate": abs(relative_error) > TOLERANCE_CONSTANT_Z,
            }
        )
        return relative_error

    record("baseline_uncorrupted", "none", "-", _relative_error(produced, ordinate))

    # Standard-condition basis. The balance p/Z = (pi/Zi)(1 - Gp/G) contains no standard
    # group at all, so these corruptions cannot move the answer; the case previously
    # claimed they would.
    for label, corrupted in (
        (
            "standard_pressure_x1.5",
            StandardConditions(
                pressure_psia=SPE_STANDARD.pressure_psia * 1.5,
                temperature_degf=SPE_STANDARD.temperature_degf,
                z_factor=SPE_STANDARD.z_factor,
                label="corrupted standard pressure",
            ),
        ),
        (
            "standard_temperature_x1.5",
            StandardConditions(
                pressure_psia=SPE_STANDARD.pressure_psia,
                temperature_degf=standard_degr * 1.5 - 459.67,
                z_factor=SPE_STANDARD.z_factor,
                label="corrupted standard temperature",
            ),
        ),
        (
            "standard_z_factor_x1.5",
            StandardConditions(
                pressure_psia=SPE_STANDARD.pressure_psia,
                temperature_degf=SPE_STANDARD.temperature_degf,
                z_factor=SPE_STANDARD.z_factor * 1.5,
                label="corrupted standard deviation factor",
            ),
        ),
    ):
        corrupted_history = _generate_constant_z(standard=corrupted)
        record(
            label,
            "standard-volume basis",
            "+50 percent",
            _relative_error(
                list(corrupted_history.cumulative_gas_scf), list(corrupted_history.p_over_z_psia())
            ),
        )

    hot = _generate_constant_z(temperature_degr=900.0)
    record(
        "reservoir_temperature_640_to_900_degr",
        "reservoir temperature",
        "+40.6 percent",
        _relative_error(list(hot.cumulative_gas_scf), list(hot.p_over_z_psia())),
    )

    # Multiplicative ordinate error: invisible, because the x-intercept of a line is
    # unchanged by scaling the ordinate.
    scale_errors: list[float] = []
    for scale in ORDINATE_SCALE_DEFECTS:
        scaled = [value * (1.0 + scale) for value in ordinate]
        scale_errors.append(
            record(
                f"ordinate_scaled_by_1_plus_{scale:g}",
                "ordinate multiplicative",
                f"{scale:+.1e} relative",
                _relative_error(produced, scaled),
            )
        )
    wrong_z_ordinate = [pressure / 0.8 for pressure in pressures]
    scale_errors.append(
        record(
            "analyst_divides_by_z_0.8_not_0.9",
            "ordinate multiplicative",
            "-11.1 percent relative",
            _relative_error(produced, wrong_z_ordinate),
        )
    )

    # Multiplicative abscissa error: visible, and it maps one for one into G.
    abscissa_sensitivity = 0.0
    for scale in CUMULATIVE_GAS_SCALE_DEFECTS:
        biased = [value * (1.0 + scale) for value in produced]
        error = record(
            f"cumulative_gas_scaled_by_1_plus_{scale:g}",
            "abscissa multiplicative",
            f"{scale:+.1e} relative",
            _relative_error(biased, ordinate),
        )
        if scale == CUMULATIVE_GAS_SCALE_DEFECTS[0]:
            abscissa_sensitivity = error / scale

    # Point-wise ordinate error: visible, with a sensitivity that depends on which point
    # moves, because the leverage of a point on the x-intercept depends on its abscissa.
    point_sensitivity = 0.0
    for index, label in ((0, "first"), (N_POINTS // 2, "middle"), (N_POINTS - 1, "last")):
        shifted = list(ordinate)
        shifted[index] += SINGLE_POINT_SHIFT_PSIA
        error = record(
            f"{label}_point_ordinate_plus_{SINGLE_POINT_SHIFT_PSIA:g}_psia",
            "ordinate point-wise",
            f"{SINGLE_POINT_SHIFT_PSIA:g} psia of p/Z on one point",
            _relative_error(produced, shifted),
        )
        point_sensitivity = max(point_sensitivity, abs(error) / SINGLE_POINT_SHIFT_PSIA)

    largest_invisible = max(abs(error) for error in scale_errors)
    return {
        "description": (
            "post-hoc positive control, not pre-registered and not gated: seeded defects "
            "against the experiment-1 arm, whose uncorrupted recovery error is exactly 0.0"
        ),
        "gate_used_for_detection": TOLERANCE_CONSTANT_Z,
        "cases": cases,
        "detection_thresholds": {
            "ordinate_multiplicative": {
                "detected": any(
                    case["detected_at_A1_gate"]
                    for case in cases
                    if case["defect_class"] == "ordinate multiplicative"
                ),
                "largest_magnitude_probed_relative": max(max(ORDINATE_SCALE_DEFECTS), abs(1.0 - 0.8 / 0.9)),
                "largest_recovery_error_observed": largest_invisible,
                "note": (
                    "no detection at any probed magnitude; the x-intercept of a straight "
                    "line is invariant under a uniform rescaling of the ordinate"
                ),
            },
            "standard_volume_basis": {
                "detected": any(
                    case["detected_at_A1_gate"]
                    for case in cases
                    if case["defect_class"] == "standard-volume basis"
                ),
                "note": "no detection at +50 percent; the standard group cancels out of the balance",
            },
            "abscissa_multiplicative": {
                "detected": True,
                "sensitivity_dG_over_dbias": abscissa_sensitivity,
                "minimum_detectable_relative_bias": TOLERANCE_CONSTANT_Z / abs(abscissa_sensitivity),
            },
            "ordinate_point_wise": {
                "detected": True,
                "sensitivity_relative_error_per_psia": point_sensitivity,
                "minimum_detectable_shift_psia": TOLERANCE_CONSTANT_Z / point_sensitivity,
            },
        },
    }


# ---------------------------------------------------------------------------
# Diagnostic D2: does the sign of the frozen-Zi bias generalise
#
# Also added after run-005, also not pre-registered and not gated. The report claimed
# that the sign of experiment 2b's bias generalises while its magnitude does not. This
# sweep tests that claim inside the case's own machinery, by moving the depletion window
# relative to the minimum of Z(p).
# ---------------------------------------------------------------------------

#: Initial pressures swept at the case's own 50 percent depletion.
FROZEN_Z_SWEEP_PRESSURES_PSIA = (4000.0, 3000.0, 2500.0, 2000.0, 1500.0, 1000.0)
#: Depletion fractions swept at the case's own 4000 psia initial pressure.
FROZEN_Z_SWEEP_DEPLETION_FRACTIONS = (0.5, 0.7, 0.9)


def frozen_z_arm(initial_pressure_psia: float, depletion_fraction: float) -> dict[str, Any]:
    """Refit one depletion window against an ordinate built with Z frozen at Z_i."""
    times, rates = depletion_schedule(depletion_fraction)
    history = simulate(
        gas_in_place_scf=GAS_IN_PLACE_SCF,
        initial_pressure_psia=initial_pressure_psia,
        temperature_degr=TEMPERATURE_DEGR,
        times_days=times,
        gas_rates_scf_per_day=rates,
        z_of_pressure=dak_z,
        standard=SPE_STANDARD,
        noise=NOISE_FREE,
        seed=NOISE_FREE_SEED,
        minimum_pressure_psia=MINIMUM_PRESSURE_PSIA,
        solver_tolerance=SOLVER_TOLERANCE,
        max_iterations=MAX_ITERATIONS,
    )
    produced = list(history.cumulative_gas_scf)
    initial_z = history.z_factors[0]
    frozen = fit_pz_depletion(produced, [pressure / initial_z for pressure in history.pressures_psia])
    consistent = fit_pz_depletion(produced, list(history.p_over_z_psia()))
    return {
        "initial_pressure_psia": initial_pressure_psia,
        "depletion_fraction": depletion_fraction,
        "final_pressure_psia": history.pressures_psia[-1],
        "initial_z_factor": initial_z,
        "minimum_z_factor_observed": min(history.z_factors),
        "final_z_factor": history.z_factors[-1],
        "frozen_z_relative_error": frozen.gas_in_place_scf / GAS_IN_PLACE_SCF - 1.0,
        "frozen_z_r_squared": frozen.r_squared,
        "consistent_z_relative_error": consistent.gas_in_place_scf / GAS_IN_PLACE_SCF - 1.0,
    }


def diagnostic_d2() -> dict[str, Any]:
    """Sweep the depletion window across the minimum of Z(p) and report the bias sign."""
    grid = [200.0 + index for index in range(int(INITIAL_PRESSURE_PSIA - 200.0) + 1)]
    minimum_pressure = min(grid, key=dak_z)

    pressure_sweep = [
        frozen_z_arm(pressure, DEPLETION_FRACTION_DEEP) for pressure in FROZEN_Z_SWEEP_PRESSURES_PSIA
    ]
    depletion_sweep = [
        frozen_z_arm(INITIAL_PRESSURE_PSIA, fraction) for fraction in FROZEN_Z_SWEEP_DEPLETION_FRACTIONS
    ]
    all_arms = pressure_sweep + depletion_sweep
    return {
        "description": (
            "post-hoc counterexample sweep, not pre-registered and not gated: the sign of "
            "the frozen-Zi bias against the position of the depletion window"
        ),
        "z_minimum_pressure_psia": minimum_pressure,
        "z_minimum_value": dak_z(minimum_pressure),
        "z_minimum_grid_step_psia": 1.0,
        "initial_pressure_sweep": pressure_sweep,
        "depletion_fraction_sweep": depletion_sweep,
        "sign_is_negative_everywhere": all(arm["frozen_z_relative_error"] < 0.0 for arm in all_arms),
        "most_positive_relative_error": max(arm["frozen_z_relative_error"] for arm in all_arms),
        "most_negative_relative_error": min(arm["frozen_z_relative_error"] for arm in all_arms),
    }


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def collect_criteria(results: dict[str, Any]) -> dict[str, bool]:
    """Pull the predeclared acceptance flags out of the four experiment payloads."""
    return {
        "A1_constant_z_recovery": results["experiment_1"]["criterion_A1_met"],
        "A2_two_point_oracle_agreement": results["experiment_1"]["criterion_A2_met"],
        "A3_variable_z_recovery": results["experiment_2"]["consistent_z"]["criterion_A3_met"],
        "A4_frozen_z_bias_in_band": results["experiment_2"]["frozen_initial_z"]["criterion_A4_met"],
        "A5_spread_matches_reported_stderr": results["experiment_3"]["criterion_A5_met"],
        "A6_mean_bias_within_limit": results["experiment_3"]["criterion_A6_met"],
        "A7_interval_coverage": results["experiment_3"]["criterion_A7_met"],
        "A8_mean_stderr_versus_analytic": results["experiment_3"]["criterion_A8_met"],
        "A9_extrapolation_stderr_ratio": results["experiment_4"]["criterion_A9_met"],
    }


def build_config() -> dict[str, Any]:
    """Return the configuration hashed into the run record."""
    return {
        "case_id": CASE_ID,
        "gas_in_place_scf": GAS_IN_PLACE_SCF,
        "initial_pressure_psia": INITIAL_PRESSURE_PSIA,
        "temperature_degr": TEMPERATURE_DEGR,
        "gas_rate_scf_per_day": GAS_RATE_SCF_PER_DAY,
        "n_points": N_POINTS,
        "constant_z": CONSTANT_Z,
        "specific_gravity": SPECIFIC_GRAVITY,
        "pseudocritical_correlation": PSEUDOCRITICALS.correlation,
        "z_correlation": "dranchuk-abou-kassem-1975",
        "standard_conditions": SPE_STANDARD.describe(),
        "minimum_pressure_psia": MINIMUM_PRESSURE_PSIA,
        "solver_tolerance": SOLVER_TOLERANCE,
        "max_iterations": MAX_ITERATIONS,
        "pressure_sigma_psia": PRESSURE_SIGMA_PSIA,
        "monte_carlo_replicates": MONTE_CARLO_REPLICATES,
        "monte_carlo_first_seed": MONTE_CARLO_FIRST_SEED,
        "extrapolation_seed": EXTRAPOLATION_SEED,
        "depletion_fractions": [DEPLETION_FRACTION_DEEP, DEPLETION_FRACTION_SHALLOW],
        "acceptance": {
            "A1_A2_tolerance": TOLERANCE_CONSTANT_Z,
            "A3_tolerance": TOLERANCE_VARIABLE_Z,
            "A4_band": list(INCONSISTENT_Z_BIAS_BAND),
            "A5_band": list(SPREAD_RATIO_BAND),
            "A6_limit": MEAN_BIAS_LIMIT,
            "A7_band": list(COVERAGE_BAND),
            "A8_band": list(MEAN_SE_RATIO_BAND),
            "A9_predicted_ratio": PREDICTED_STDERR_RATIO,
            "A9_tolerance": STDERR_RATIO_TOLERANCE,
        },
    }


LIMITATIONS = (
    "Numerical verification only. The generator and the estimator share the volumetric "
    "assumption set: one tank, constant hydrocarbon pore volume, dry gas of fixed "
    "composition, isothermal, no influx, no injection, one declared standard basis. "
    "Agreement checks the arithmetic and cannot validate any of those assumptions.",
    "No field data and no published benchmark is used. Exact recovery here is compatible "
    "with the same estimator being badly wrong on a reservoir that violates the "
    "volumetric assumption; that case is A2, not this one.",
    "Experiments 1 and 2a are blind to any multiplicative error in the ordinate. "
    "Diagnostic D1 shows that corrupting the standard-volume basis by 50 percent, "
    "changing the reservoir temperature, or rescaling the whole p/Z series leaves the "
    "recovery error at zero, because the x-intercept of a line does not move when the "
    "ordinate is rescaled. Zero recovery error is evidence only against the defect "
    "classes D1 shows are visible: abscissa bias and point-wise ordinate error.",
    "Only the pressure channel of NoiseModel is exercised anywhere in this case. Error "
    "in cumulative production is never simulated, and diagnostic D1 shows it maps one "
    "for one into the recovered G, which makes allocation and metering bias the most "
    "consequential untested input.",
    "The fit is ordinary least squares, which assumes an error-free abscissa. Once "
    "cumulative production carries error the problem is errors-in-variables and OLS is "
    "the wrong estimator; the library's Deming and York fits are not exercised here, so "
    "nothing establishes what the reported standard error means in that case.",
    "The Dranchuk-Abou-Kassem deviation factor is a correlation evaluated inside its "
    "published window, not a measured PVT report. One composition is used: a 0.65 "
    "specific-gravity dry gas with no H2S, CO2 or N2, so no Wichert-Aziz correction is "
    "exercised. For pure carbon dioxide this repository's own check.py records DAK "
    "errors against NIST of up to 39.7 percent.",
    "The Monte Carlo in experiment 3 uses independent Gaussian pressure error only. Real "
    "shut-in pressures carry shared calibration bias and temporally correlated error, "
    "which a per-point independent model cannot represent and which the reported standard "
    "error would understate.",
    "Average reservoir pressure is handed to the estimator exactly. In the field it is "
    "itself an estimate, from a build-up extrapolation and a datum correction, whose "
    "error is systematic rather than Gaussian and whose well count may not sample the "
    "drainage volume.",
    "Constant hydrocarbon pore volume is asserted, not tested. Formation and connate-water "
    "compressibility, which is what makes an abnormally pressured gas reservoir curve its "
    "p/Z plot and overestimate G, is not represented at all, and it is a non-water-drive "
    "violation of the same assumption.",
    "Dry gas of fixed composition is asserted. Retrograde condensate dropout, which "
    "removes liquid from the reservoir gas and changes the composition as pressure falls, "
    "is outside the generator's model.",
    "Cumulative production is evenly spaced by construction, which is what makes the "
    "section-5 error budget exact: xbar = fG/2 and Sxx = 1.1 f^2 G^2. Real survey dates "
    "cluster, and every leverage and tolerance in that budget changes with the spacing.",
    "Experiment 2b measures one specific Z inconsistency, the initial deviation factor "
    "reused throughout, on one depletion window. Diagnostic D2 shows that both the "
    "magnitude and the sign of that bias depend on where the window sits relative to the "
    "minimum of Z(p); neither transfers.",
    "No reserves terminology, development decision or operational limit follows from any number here.",
)


def render_summary(payload: dict[str, Any]) -> str:
    """Return the readable console summary the run prints."""
    exp1 = payload["experiment_1"]
    exp2 = payload["experiment_2"]
    exp3 = payload["experiment_3"]
    exp4 = payload["experiment_4"]
    d1 = payload["diagnostic_d1_defect_sensitivity"]
    d2 = payload["diagnostic_d2_frozen_z_sign_sweep"]
    ordinate_class = d1["detection_thresholds"]["ordinate_multiplicative"]
    abscissa_class = d1["detection_thresholds"]["abscissa_multiplicative"]
    point_class = d1["detection_thresholds"]["ordinate_point_wise"]
    curvature = exp2["pressure_curvature"]
    lines = [
        f"Case {CASE_ID}",
        f"  true gas in place            {GAS_IN_PLACE_SCF:.6e} scf",
        "",
        "Experiment 1 -- noise-free, constant Z, 50 percent depletion",
        f"  recovered G                  {exp1['fit']['gas_in_place_scf']:.15e} scf",
        f"  relative error               {exp1['fit']['relative_error']:+.3e}"
        f"   (predeclared |e| <= {TOLERANCE_CONSTANT_Z:.1e})",
        f"  two-point oracle difference  {exp1['two_point_oracle_relative_difference']:.3e}",
        f"  generator balance residual   {exp1['generator_max_abs_residual_p_over_z_psia']:.3e} psia",
        f"  extrapolation sqrt(h)        {exp1['condition_number_sqrt_h']:.6f}",
        "",
        "Experiment 2 -- noise-free, Dranchuk-Abou-Kassem Z, 50 percent depletion",
        f"  Z at pi / at last point      {exp2['initial_z_factor']:.6f} / {exp2['final_z_factor']:.6f}",
        f"  pressure gap from chord      {curvature['max_abs_deviation_from_chord_psia']:.2f} psia"
        f" ({curvature['as_fraction_of_initial_pressure']:.4%} of pi)",
        f"  consistent Z, relative error {exp2['consistent_z']['fit']['relative_error']:+.3e}"
        f"   (predeclared |e| <= {TOLERANCE_VARIABLE_Z:.1e})",
        f"  Z frozen at Zi, rel. error   {exp2['frozen_initial_z']['fit']['relative_error']:+.4%}",
        f"  Z frozen at Zi, R-squared    {exp2['frozen_initial_z']['fit']['r_squared']:.8f}",
        "",
        "Experiment 3 -- reported standard error against Monte Carlo spread",
        f"  realisations fitted          {exp3['replicates_fitted']} of {exp3['replicates_requested']}",
        f"  Monte Carlo spread           {exp3['monte_carlo_spread_scf']:.6e} scf",
        f"  mean reported stderr         {exp3['mean_reported_stderr_scf']:.6e} scf",
        f"  analytic stderr              {exp3['analytic_stderr_scf']:.6e} scf",
        f"  spread / mean reported       {exp3['spread_over_mean_reported_stderr']:.4f}"
        f"   (predeclared {SPREAD_RATIO_BAND[0]:.2f} to {SPREAD_RATIO_BAND[1]:.2f})",
        f"  mean relative bias of G      {exp3['mean_relative_bias']:+.3e}",
        f"  95 percent interval coverage {exp3['coverage_of_95_percent_interval']:.3f}",
        "",
        "Experiment 4 -- cost of the extrapolation, identical noise",
        f"  50 pct: G = {exp4['deep']['fit']['gas_in_place_scf']:.6e} scf"
        f"  +- {exp4['deep']['fit']['gas_in_place_stderr_scf']:.3e}"
        f"  ({exp4['deep']['relative_stderr']:.3%})",
        f"  10 pct: G = {exp4['shallow']['fit']['gas_in_place_scf']:.6e} scf"
        f"  +- {exp4['shallow']['fit']['gas_in_place_stderr_scf']:.3e}"
        f"  ({exp4['shallow']['relative_stderr']:.3%})",
        f"  stderr ratio                 {exp4['reported_stderr_ratio']:.4f}"
        f"   (predicted {PREDICTED_STDERR_RATIO:.4f})",
        f"  identical residuals, max gap {exp4['max_abs_residual_difference_psia']:.3e} psia",
        "",
        "Diagnostic D1 -- seeded defects, post-hoc, not gated",
        f"  ordinate scale probed to     {ordinate_class['largest_magnitude_probed_relative']:.3f} relative"
        f" -> error {ordinate_class['largest_recovery_error_observed']:.2e}",
        f"  smallest visible Gp bias     {abscissa_class['minimum_detectable_relative_bias']:.2e} relative",
        f"  smallest visible point shift {point_class['minimum_detectable_shift_psia']:.2e} psia",
        "",
        "Diagnostic D2 -- sign of the frozen-Zi bias, post-hoc, not gated",
        f"  Z(p) minimum near            {d2['z_minimum_pressure_psia']:.0f} psia"
        f" (Z = {d2['z_minimum_value']:.6f})",
        f"  frozen-Zi error, most / least {d2['most_negative_relative_error']:+.4%}"
        f" / {d2['most_positive_relative_error']:+.4%}",
        f"  sign negative everywhere     {d2['sign_is_negative_everywhere']}",
        "",
        "Predeclared acceptance criteria",
    ]
    for name, met in payload["criteria"].items():
        lines.append(f"  {'MET    ' if met else 'NOT MET'}  {name}")
    lines.append("")
    lines.append(f"  all criteria met: {payload['all_criteria_met']}")
    lines.append(f"  metrics hash:     {payload['metrics_sha256']}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the four experiments and write the run record."""
    parser = argparse.ArgumentParser(description=f"Case {CASE_ID}: volumetric p/Z baseline")
    parser.add_argument("--out", required=True, help="fresh run directory; must not already have content")
    args = parser.parse_args(argv)

    config = build_config()
    with RunRecord.open(
        args.out,
        label=CASE_ID,
        config=config,
        seed=EXTRAPOLATION_SEED,
        settings={"python_float": "IEEE 754 binary64", "dependencies": "standard library only"},
        # "." and not ROOT. provenance.source_revision writes the repo root into the
        # record verbatim, and an absolute path here is a machine-local home path that
        # scripts/check_repository.py rejects the moment the record is committed under
        # cases/*/results/ -- which .gitignore explicitly invites. A relative root keeps
        # the record committable, and the commit hash beside it is the real identity of
        # the source anyway. The run must therefore be launched from the repository root,
        # which is the documented invocation. See report.md, library defects.
        repo_root=".",
    ) as record:
        results: dict[str, Any] = {
            "experiment_1": experiment_1(),
            "experiment_2": experiment_2(),
            "experiment_3": experiment_3(),
            "experiment_4": experiment_4(),
            "diagnostic_d1_defect_sensitivity": diagnostic_d1(),
            "diagnostic_d2_frozen_z_sign_sweep": diagnostic_d2(),
        }
        criteria = collect_criteria(results)
        payload: dict[str, Any] = {
            "case_id": CASE_ID,
            "config": config,
            **results,
            "criteria": criteria,
            "all_criteria_met": all(criteria.values()),
            "limitations": list(LIMITATIONS),
        }
        payload["metrics_sha256"] = canonical_hash(results)
        record.write_json("summary.json", payload)

        record.metrics(
            experiment_1_relative_error=results["experiment_1"]["fit"]["relative_error"],
            experiment_2_consistent_relative_error=results["experiment_2"]["consistent_z"]["fit"][
                "relative_error"
            ],
            experiment_2_frozen_z_relative_error=results["experiment_2"]["frozen_initial_z"]["fit"][
                "relative_error"
            ],
            experiment_3_spread_over_reported=results["experiment_3"]["spread_over_mean_reported_stderr"],
            experiment_3_coverage=results["experiment_3"]["coverage_of_95_percent_interval"],
            experiment_4_stderr_ratio=results["experiment_4"]["reported_stderr_ratio"],
            all_criteria_met=payload["all_criteria_met"],
            metrics_sha256=payload["metrics_sha256"],
        )
        record.note(
            "Forward generation by reservoir_lab.depletion, inversion by "
            "reservoir_lab.material_balance. The two modules share no code, so a coding "
            "slip in one does not cancel against the other. They do share the physical "
            "assumption set, and diagnostic D1 shows the comparison is blind to any "
            "uniform multiplicative error in the ordinate, the standard-volume basis "
            "included."
        )
        record.note(
            "Acceptance thresholds were fixed in cases/A1_volumetric_baseline/protocol.md "
            "before this run.py was first executed. Diagnostics D1 and D2 were added "
            "afterwards, are not gated, and changed no threshold."
        )
        for limitation in LIMITATIONS:
            record.limitation(limitation)

        print(render_summary(payload))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

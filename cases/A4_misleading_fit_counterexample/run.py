"""Case A4 -- when a straight p/Z line is convincing and wrong.

Generates water-drive gas depletion histories with a coupled Fetkovich aquifer and
fits each of them with the volumetric p/Z inverse, deliberately. Reports the fit
quality of the wrong model, the bias in recovered gas in place against aquifer
strength, how that bias drifts as more history is observed, and whether the residual
pattern betrays the misfit above realistic measurement noise.

Standard library only. Pure and deterministic: two runs with the same configuration
produce identical numbers.

Run:
    PYTHONPATH=src python3 cases/A4_misleading_fit_counterexample/run.py --out artifacts/A4/run-001
"""

from __future__ import annotations

import argparse
import itertools
import math
import random
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

#: The repository root as the run record should name it. An absolute path would stamp
#: the author's home directory into every committed run record, which the repository
#: hygiene gate refuses and which carries no information a reader can use -- the commit
#: hash is the identity that matters. Relative to the working directory when the
#: documented command is used, which runs from the repository root; absolute otherwise,
#: so a run from elsewhere is still recorded truthfully rather than mislabelled.
try:
    RECORDED_REPO_ROOT: Path = REPO_ROOT.relative_to(Path.cwd())
except ValueError:  # pragma: no cover - only when run from outside the repository
    RECORDED_REPO_ROOT = REPO_ROOT

from reservoir_lab import units  # noqa: E402
from reservoir_lab.aquifer import FetkovichAquifer  # noqa: E402
from reservoir_lab.depletion import (  # noqa: E402
    NOISE_FREE,
    DepletionHistory,
    NoiseModel,
    simulate_volumetric_depletion,
    simulate_water_drive_depletion,
)
from reservoir_lab.gas_properties import pseudocritical_standing, z_factor  # noqa: E402
from reservoir_lab.material_balance import fit_pz_depletion  # noqa: E402
from reservoir_lab.provenance import RunRecord  # noqa: E402
from reservoir_lab.regression import student_t_quantile  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration. Every number here is declared in protocol.md and fixed before the
# run. Nothing below is tuned against a result.
# ---------------------------------------------------------------------------

GAS_IN_PLACE_SCF = 1.0e11
INITIAL_PRESSURE_PSIA = 4000.0
TEMPERATURE_DEGF = 180.0
SPECIFIC_GRAVITY = 0.65
#: Keeps every deviation-factor evaluation inside the published DAK window p_pr >= 0.2.
#: The generator scans the whole search interval for p/Z monotonicity, so a floor of
#: 14.696 psia would drive the correlation into extrapolation on every run.
MINIMUM_PRESSURE_PSIA = 250.0

HORIZON_DAYS = 12.0 * 365.25
RECOVERY_FRACTION = 0.55
BASE_STEPS = 144
#: Every third simulation step is reported as an observation: a quarterly pressure
#: survey, which is a realistic surveillance cadence for a mature gas field.
OBSERVATION_STRIDE = 3

AQUIFER_INITIAL_PRESSURE_PSIA = 4000.0
AQUIFER_WATER_VOLUME_BBL = 3.0e9
AQUIFER_COMPRESSIBILITY_PER_PSI = 6.0e-6
PRODUCTIVITY_INDICES = (0.0, 0.05, 0.2, 0.6, 2.0, 6.0, 20.0, 60.0)
BASE_PRODUCTIVITY_INDEX = 2.0
STRONGEST_PRODUCTIVITY_INDEX = 60.0

HISTORY_FRACTIONS = (0.2, 0.4, 0.6, 0.8, 1.0)
REFINEMENT_MULTIPLIERS = (1, 2, 4, 8)
HOLDOUT_CALIBRATION_FRACTION = 0.6
PRODUCED_WATER_FRACTION_VARIANT = 0.30

NOISE_SIGMAS_PSI = (1.0, 2.0, 5.0, 10.0, 20.0, 40.0, 80.0)
NOISE_REPLICATES = 400
NOISE_SEED = 20260913
CONFIDENCE = 0.95

# ---------------------------------------------------------------------------
# E9 -- post-review sensitivities. These were added AFTER the pre-registered
# experiments had been run and reported, in response to an independent referee pass.
# They are not pre-registered, no acceptance criterion depends on them, and they are
# reported as sensitivities rather than as gates. They exist because three claims in
# the first version of the report reached further than the run supported: that the
# closed-form sigma was a half-power point, that one seed characterises the detector,
# and that the deviation-factor correlation could be ignored.
# ---------------------------------------------------------------------------

#: Grid for the empirical power curve, chosen to bracket the closed-form sigma at which
#: the expected statistic equals the critical value (12.5 psi) from both sides.
POWER_CURVE_SIGMAS_PSI = (8.0, 9.0, 10.0, 11.0, 11.5, 12.0, 12.5, 13.0, 14.0, 16.0)
POWER_CURVE_REPLICATES = 4000
#: A seed different from NOISE_SEED, so the power curve is not a rescaling of the
#: pre-registered sweep's single draw set.
POWER_CURVE_SEED = 20260914
#: Eight consecutive seeds, declared as a block, for the seed-sensitivity check of the
#: single-seed detection rates. The first is the pre-registered NOISE_SEED itself.
SEED_SENSITIVITY_SEEDS = (20260913, 20260915, 20260916, 20260917, 20260918, 20260919, 20260920, 20260921)
SEED_SENSITIVITY_SIGMA_PSI = 5.0
#: Pooled null replicates on a fresh seed, to separate the declared seed's draw from
#: the detector's actual size.
POOLED_NULL_REPLICATES = 20000
POOLED_NULL_SEED = 20260922
#: Noise levels at which the two ways of forming the p/Z ordinate are compared.
Z_HANDLING_SIGMAS_PSI = (5.0, 10.0, 20.0, 40.0)

#: Pre-registered acceptance thresholds. See protocol.md, table in "Verification and
#: acceptance". Named here so the run record carries them next to the results.
ACCEPTANCE = {
    "A2_max_relative_error_zero_aquifer": 1.0e-9,
    "A3_max_solver_residual_psia": 1.0e-5,
    "A3_min_orders_below_signal": 6.0,
    "A4_max_refinement_change": 1.0e-3,
    "A5_max_relative_error_known_influx": 1.0e-8,
    "A6_min_r_squared": 0.999,
    "A6_min_relative_bias": 0.10,
    "A8_min_drift_fraction_of_g": 0.03,
    "A9_negative_control_sigma_psi": 5.0,
    "A9_detection_rate_low": 0.01,
    "A9_detection_rate_high": 0.12,
    "A10_positive_control_sigma_psi": 1.0,
    "A10_min_detection_rate": 0.95,
}

STANDARD = units.SPE_STANDARD
TEMPERATURE_DEGR = units.fahrenheit_to_rankine(TEMPERATURE_DEGF)
PSEUDOCRITICALS = pseudocritical_standing(SPECIFIC_GRAVITY)


@dataclass(frozen=True)
class InertAquifer:
    """A Fetkovich parameter set with a zero productivity index.

    ``FetkovichAquifer`` refuses a zero productivity index, and correctly so: an
    aquifer that cannot flow is not an aquifer. The generator's contract nevertheless
    accepts any object exposing the four published parameters, which is what makes the
    exact-reduction check of protocol.md E3 possible at all. The initial pressure is
    set equal to the reservoir's by the caller so that the generator's pressure search
    bracket, ``max(reservoir p_i, aquifer p_i)``, is identical to the volumetric
    generator's and the comparison is bit for bit rather than merely close.
    """

    initial_pressure_psia: float
    water_volume_bbl: float
    total_compressibility_per_psi: float
    productivity_index_bbl_per_day_psi: float


_Z_CACHE: dict[float, float] = {}
_Z_HY_CACHE: dict[float, float] = {}


def z_of_pressure(pressure_psia: float) -> float:
    """Return the DAK deviation factor at ``pressure_psia``, memoised.

    Memoisation is a speed device only. The underlying correlation is a pure function
    of pressure at fixed temperature and composition, so the cache cannot change a
    result; it only avoids re-running the Newton solve at pressures already visited.
    """
    cached = _Z_CACHE.get(pressure_psia)
    if cached is None:
        cached = z_factor(pressure_psia, TEMPERATURE_DEGR, PSEUDOCRITICALS, method="dak")
        _Z_CACHE[pressure_psia] = cached
    return cached


def z_of_pressure_hall_yarborough(pressure_psia: float) -> float:
    """Return the Hall-Yarborough deviation factor at ``pressure_psia``, memoised.

    Used only by the post-review correlation sensitivity (E9). Hall-Yarborough is a
    different functional family fitted by different authors, so the spread between it
    and DAK is a usable proxy for the correlation error the whole p/Z ordinate carries.
    """
    cached = _Z_HY_CACHE.get(pressure_psia)
    if cached is None:
        cached = z_factor(pressure_psia, TEMPERATURE_DEGR, PSEUDOCRITICALS, method="hall-yarborough")
        _Z_HY_CACHE[pressure_psia] = cached
    return cached


def schedule(steps: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Return ``(times_days, gas_rates_scf_per_day)`` for a constant-rate history."""
    timestep = HORIZON_DAYS / steps
    times = tuple(index * timestep for index in range(steps + 1))
    rate = RECOVERY_FRACTION * GAS_IN_PLACE_SCF / HORIZON_DAYS
    return times, (rate,) * steps


def simulate(
    productivity_index: float,
    *,
    steps: int = BASE_STEPS,
    noise: NoiseModel = NOISE_FREE,
    seed: int = 1,
    produced_water_fraction: float = 0.0,
    z_function: Callable[[float], float] = z_of_pressure,
) -> DepletionHistory:
    """Generate one water-drive history at the given aquifer productivity index."""
    times, rates = schedule(steps)
    if productivity_index > 0.0:
        aquifer: object = FetkovichAquifer(
            initial_pressure_psia=AQUIFER_INITIAL_PRESSURE_PSIA,
            water_volume_bbl=AQUIFER_WATER_VOLUME_BBL,
            total_compressibility_per_psi=AQUIFER_COMPRESSIBILITY_PER_PSI,
            productivity_index_bbl_per_day_psi=productivity_index,
        )
    else:
        aquifer = InertAquifer(
            initial_pressure_psia=INITIAL_PRESSURE_PSIA,
            water_volume_bbl=AQUIFER_WATER_VOLUME_BBL,
            total_compressibility_per_psi=AQUIFER_COMPRESSIBILITY_PER_PSI,
            productivity_index_bbl_per_day_psi=0.0,
        )
    return simulate_water_drive_depletion(
        gas_in_place_scf=GAS_IN_PLACE_SCF,
        initial_pressure_psia=INITIAL_PRESSURE_PSIA,
        temperature_degr=TEMPERATURE_DEGR,
        times_days=times,
        gas_rates_scf_per_day=rates,
        z_of_pressure=z_function,
        standard=STANDARD,
        aquifer=aquifer,
        noise=noise,
        seed=seed,
        produced_water_fraction=produced_water_fraction,
        minimum_pressure_psia=MINIMUM_PRESSURE_PSIA,
    )


def observation_indices(steps: int) -> tuple[int, ...]:
    """Return the indices of the reported observations within a history of ``steps`` steps."""
    stride = OBSERVATION_STRIDE * (steps // BASE_STEPS)
    return tuple(range(0, steps + 1, stride))


def observed(history: DepletionHistory, steps: int = BASE_STEPS) -> tuple[tuple[float, ...], ...]:
    """Return ``(cumulative_gas, p_over_z, z_factor, pressure)`` at the observation times."""
    indices = observation_indices(steps)
    p_over_z = history.true_p_over_z_psia()
    return (
        tuple(history.true_cumulative_gas_scf[i] for i in indices),
        tuple(p_over_z[i] for i in indices),
        tuple(history.true_z_factors[i] for i in indices),
        tuple(history.true_pressures_psia[i] for i in indices),
    )


def invaded_fraction(history: DepletionHistory) -> float:
    """Terminal water influx as a fraction of the initial hydrocarbon pore volume."""
    influx_rcf = history.water_influx_bbl[-1] * units.CUBIC_FEET_PER_BARREL
    return influx_rcf / history.truth.hydrocarbon_pore_volume_rcf


def known_influx_gas_in_place_scf(history: DepletionHistory, index: int) -> float:
    """Recover G from the full balance with the influx known -- Oracle 2 of the protocol.

    Rearranging ``(G - Gp) * Bg(p) = G * Bg(p_i) - (We - Bw*Wp)`` gives

        G = (Gp * Bg(p) - net influx in rcf) / (Bg(p) - Bg(p_i))

    which uses no function from ``material_balance`` and no regression. It is the
    quantitative form of "measure the influx and the ambiguity disappears".
    """
    truth = history.truth
    bg_initial = truth.gas_fvf_rcf_per_scf(truth.initial_pressure_psia, truth.initial_z_factor)
    bg = truth.gas_fvf_rcf_per_scf(history.true_pressures_psia[index], history.true_z_factors[index])
    net_influx_rcf = (
        history.water_influx_bbl[index] - truth.water_fvf_rb_per_stb * history.cumulative_water_stb[index]
    ) * units.CUBIC_FEET_PER_BARREL
    return (history.true_cumulative_gas_scf[index] * bg - net_influx_rcf) / (bg - bg_initial)


# ---------------------------------------------------------------------------
# Quadratic curvature test. Written out here rather than taken from the library
# because `regression` supplies straight lines only, and because the detectability
# statistic must be visible in the case that quotes it.
# ---------------------------------------------------------------------------


def _solve(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Solve a small dense system by Gaussian elimination with partial pivoting."""
    size = len(rhs)
    augmented = [[*row, value] for row, value in zip(matrix, rhs, strict=True)]
    for k in range(size):
        pivot = max(range(k, size), key=lambda r: abs(augmented[r][k]))
        augmented[k], augmented[pivot] = augmented[pivot], augmented[k]
        for r in range(k + 1, size):
            factor = augmented[r][k] / augmented[k][k]
            for c in range(k, size + 1):
                augmented[r][c] -= factor * augmented[k][c]
    solution = [0.0] * size
    for k in reversed(range(size)):
        total = math.fsum(augmented[k][c] * solution[c] for c in range(k + 1, size))
        solution[k] = (augmented[k][size] - total) / augmented[k][k]
    return solution


def quadratic_fit(u: tuple[float, ...], y: tuple[float, ...]) -> tuple[float, float, float, float]:
    """Fit ``y = a + b*u + c*u**2`` and return ``(a, b, c, inverse_gram_cc)``.

    ``inverse_gram_cc`` is the (2, 2) element of the inverse Gram matrix, so that the
    standard error of the curvature coefficient is ``sigma * sqrt(inverse_gram_cc)``
    for a residual standard deviation ``sigma``. Keeping it separate from ``sigma`` is
    what allows the detectability threshold to be solved in closed form rather than
    searched for by simulation.
    """
    gram = [[math.fsum(value ** (i + j) for value in u) for j in range(3)] for i in range(3)]
    rhs = [math.fsum(value**i * target for value, target in zip(u, y, strict=True)) for i in range(3)]
    coefficients = _solve(gram, rhs)
    unit = [0.0, 0.0, 1.0]
    inverse_column = _solve(gram, unit)
    return coefficients[0], coefficients[1], coefficients[2], inverse_column[2]


def curvature_t_statistic(u: tuple[float, ...], y: tuple[float, ...]) -> float:
    """Two-sided t statistic of the quadratic coefficient against zero."""
    a, b, c, inverse_gram_cc = quadratic_fit(u, y)
    residuals = [target - (a + b * value + c * value * value) for value, target in zip(u, y, strict=True)]
    dof = len(u) - 3
    variance = math.fsum(r * r for r in residuals) / dof
    standard_error = math.sqrt(variance * inverse_gram_cc)
    if standard_error == 0.0:
        return math.inf
    return c / standard_error


# ---------------------------------------------------------------------------
# Experiments
# ---------------------------------------------------------------------------


def experiment_strength_sweep() -> list[dict[str, object]]:
    """E1 -- one volumetric fit per aquifer strength, over the full history."""
    rows: list[dict[str, object]] = []
    for productivity_index in PRODUCTIVITY_INDICES:
        history = simulate(productivity_index)
        cumulative, p_over_z, _, pressures = observed(history)
        fit = fit_pz_depletion(cumulative, p_over_z)
        produced = cumulative[-1]
        true_remaining = GAS_IN_PLACE_SCF - produced
        storage = AQUIFER_COMPRESSIBILITY_PER_PSI * AQUIFER_WATER_VOLUME_BBL
        rows.append(
            {
                "productivity_index_bbl_per_day_psi": productivity_index,
                "aquifer_time_constant_days": (
                    storage / productivity_index if productivity_index > 0.0 else None
                ),
                "timestep_over_time_constant": (
                    (HORIZON_DAYS / BASE_STEPS) * productivity_index / storage
                    if productivity_index > 0.0
                    else 0.0
                ),
                "terminal_water_influx_bbl": history.water_influx_bbl[-1],
                "invaded_pore_volume_fraction": invaded_fraction(history),
                "terminal_pressure_psia": pressures[-1],
                "r_squared": fit.r_squared,
                "fitted_gas_in_place_scf": fit.gas_in_place_scf,
                "relative_gas_in_place_error": fit.gas_in_place_scf / GAS_IN_PLACE_SCF - 1.0,
                "fitted_stderr_scf": fit.gas_in_place_stderr_scf,
                "bias_over_stderr": (
                    (fit.gas_in_place_scf - GAS_IN_PLACE_SCF) / fit.gas_in_place_stderr_scf
                    if fit.gas_in_place_stderr_scf > 0.0
                    else None
                ),
                "relative_remaining_gas_error": (fit.gas_in_place_scf - produced) / true_remaining - 1.0,
                "max_abs_residual_psia": max(abs(r) for r in fit.residuals),
                "rms_residual_psia": math.sqrt(math.fsum(r * r for r in fit.residuals) / len(fit.residuals)),
                "depletion_fraction_observed": fit.depletion_fraction_observed,
                "max_solver_residual_p_over_z_psia": history.max_abs_residual_p_over_z_psia,
                "generator_warnings": list(history.warnings),
            }
        )
    return rows


def experiment_progressive_fits() -> list[dict[str, object]]:
    """E2 -- recovered G against the fraction of the history that has been observed."""
    rows: list[dict[str, object]] = []
    for productivity_index in PRODUCTIVITY_INDICES:
        history = simulate(productivity_index)
        cumulative, p_over_z, _, _ = observed(history)
        points = len(cumulative)
        for fraction in HISTORY_FRACTIONS:
            count = max(3, round(fraction * (points - 1)) + 1)
            fit = fit_pz_depletion(cumulative[:count], p_over_z[:count])
            rows.append(
                {
                    "productivity_index_bbl_per_day_psi": productivity_index,
                    "history_fraction": fraction,
                    "n_points": count,
                    "years_observed": fraction * HORIZON_DAYS / 365.25,
                    "r_squared": fit.r_squared,
                    "relative_gas_in_place_error": fit.gas_in_place_scf / GAS_IN_PLACE_SCF - 1.0,
                    "relative_stderr": fit.gas_in_place_stderr_scf / fit.gas_in_place_scf,
                    "depletion_fraction_observed": fit.depletion_fraction_observed,
                }
            )
    return rows


def experiment_zero_aquifer_reduction() -> dict[str, object]:
    """E3 -- the case must reduce exactly to the volumetric case at J = 0."""
    times, rates = schedule(BASE_STEPS)
    volumetric = simulate_volumetric_depletion(
        gas_in_place_scf=GAS_IN_PLACE_SCF,
        initial_pressure_psia=INITIAL_PRESSURE_PSIA,
        temperature_degr=TEMPERATURE_DEGR,
        times_days=times,
        gas_rates_scf_per_day=rates,
        z_of_pressure=z_of_pressure,
        standard=STANDARD,
        noise=NOISE_FREE,
        seed=1,
        minimum_pressure_psia=MINIMUM_PRESSURE_PSIA,
    )
    inert = simulate(0.0)
    series = (
        "true_pressures_psia",
        "true_z_factors",
        "true_cumulative_gas_scf",
        "residual_p_over_z_psia",
        "water_influx_bbl",
        "cumulative_water_stb",
    )
    comparisons = {}
    identical = True
    for name in series:
        left = getattr(volumetric, name)
        right = getattr(inert, name)
        same = left == right
        identical = identical and same
        comparisons[name] = {
            "bitwise_identical": same,
            "max_absolute_difference": max(abs(a - b) for a, b in zip(left, right, strict=True)),
        }
    cumulative, p_over_z, _, _ = observed(inert)
    fit = fit_pz_depletion(cumulative, p_over_z)
    relative_error = fit.gas_in_place_scf / GAS_IN_PLACE_SCF - 1.0
    return {
        "series_comparisons": comparisons,
        "all_series_bitwise_identical": identical,
        "fitted_gas_in_place_scf": fit.gas_in_place_scf,
        "relative_gas_in_place_error": relative_error,
        "r_squared": fit.r_squared,
        "max_abs_residual_psia": max(abs(r) for r in fit.residuals),
        "a1_passed": identical,
        "a2_passed": abs(relative_error) < ACCEPTANCE["A2_max_relative_error_zero_aquifer"],
    }


def experiment_known_influx_oracle() -> dict[str, object]:
    """E4 -- recover G from the full balance with the influx supplied."""
    rows = []
    worst = 0.0
    for productivity_index in PRODUCTIVITY_INDICES:
        history = simulate(productivity_index)
        errors = [
            abs(known_influx_gas_in_place_scf(history, index) / GAS_IN_PLACE_SCF - 1.0)
            for index in observation_indices(BASE_STEPS)[1:]
        ]
        worst = max(worst, max(errors))
        rows.append(
            {
                "productivity_index_bbl_per_day_psi": productivity_index,
                "max_relative_error": max(errors),
                "terminal_relative_error": errors[-1],
            }
        )
    return {
        "per_strength": rows,
        "worst_relative_error": worst,
        "a5_passed": worst < ACCEPTANCE["A5_max_relative_error_known_influx"],
    }


def experiment_timestep_refinement() -> dict[str, object]:
    """E5 -- is the bias resolved in time, or is it a discretisation artefact."""
    results: dict[str, object] = {}
    passed = True
    for productivity_index in (BASE_PRODUCTIVITY_INDEX, STRONGEST_PRODUCTIVITY_INDEX):
        rows = []
        for multiplier in REFINEMENT_MULTIPLIERS:
            steps = BASE_STEPS * multiplier
            history = simulate(productivity_index, steps=steps)
            cumulative, p_over_z, _, _ = observed(history, steps=steps)
            fit = fit_pz_depletion(cumulative, p_over_z)
            rows.append(
                {
                    "timestep_days": HORIZON_DAYS / steps,
                    "steps": steps,
                    "terminal_water_influx_bbl": history.water_influx_bbl[-1],
                    "relative_gas_in_place_error": fit.gas_in_place_scf / GAS_IN_PLACE_SCF - 1.0,
                    "max_solver_residual_p_over_z_psia": history.max_abs_residual_p_over_z_psia,
                }
            )
        span = max(float(r["relative_gas_in_place_error"]) for r in rows) - min(
            float(r["relative_gas_in_place_error"]) for r in rows
        )
        passed = passed and span < ACCEPTANCE["A4_max_refinement_change"]
        results[f"J_{productivity_index:g}"] = {"levels": rows, "error_span_over_refinement": span}
    results["a4_passed"] = passed
    return results


def experiment_residuals_and_detectability() -> dict[str, object]:
    """E6 -- does the residual pattern give the misfit away, and above what noise."""
    history = simulate(BASE_PRODUCTIVITY_INDEX)
    cumulative, p_over_z, z_factors, pressures = observed(history)
    fit = fit_pz_depletion(cumulative, p_over_z)
    points = len(cumulative)
    u = tuple(value / GAS_IN_PLACE_SCF for value in cumulative)
    _, _, curvature, inverse_gram_cc = quadratic_fit(u, p_over_z)
    critical = student_t_quantile(0.5 + CONFIDENCE / 2.0, points - 3)
    mean_z = math.fsum(z_factors) / points
    #: Noise-free curvature divided by the critical value and the design factor gives
    #: the residual standard deviation at which the EXPECTED t statistic equals the
    #: critical value. That is not the 50 percent-power point: the statistic is a ratio
    #: whose denominator is itself random, so power at this sigma is below one half. E9
    #: measures the half-power point directly rather than inferring it from here.
    sigma_p_over_z_star = abs(curvature) / (critical * math.sqrt(inverse_gram_cc))
    sigma_pressure_star = sigma_p_over_z_star * mean_z

    observation_years = OBSERVATION_STRIDE * HORIZON_DAYS / BASE_STEPS / 365.25
    residual_table = [
        {
            "years": index * observation_years,
            "cumulative_gas_scf": cumulative[index],
            "cumulative_gas_fraction_of_true_g": cumulative[index] / GAS_IN_PLACE_SCF,
            "observed_p_over_z_psia": p_over_z[index],
            "fitted_p_over_z_psia": fit.intercept + fit.slope * cumulative[index],
            "residual_psia": fit.residuals[index],
        }
        for index in range(points)
        if index % 6 == 0 or index == points - 1
    ]

    null_history = simulate(0.0)
    null_cumulative, _, null_z, null_pressures = observed(null_history)
    null_u = tuple(value / GAS_IN_PLACE_SCF for value in null_cumulative)

    def detection_rate(
        true_pressures: tuple[float, ...],
        z_values: tuple[float, ...],
        design: tuple[float, ...],
        sigma: float,
    ) -> float:
        rng = random.Random(NOISE_SEED)
        detected = 0
        for _ in range(NOISE_REPLICATES):
            noisy = tuple(
                (pressure + rng.gauss(0.0, sigma)) / z
                for pressure, z in zip(true_pressures, z_values, strict=True)
            )
            if abs(curvature_t_statistic(design, noisy)) > critical:
                detected += 1
        return detected / NOISE_REPLICATES

    sweep = []
    for sigma in NOISE_SIGMAS_PSI:
        sweep.append(
            {
                "pressure_sigma_psi": sigma,
                "detection_rate_water_drive": detection_rate(pressures, z_factors, u, sigma),
                "detection_rate_volumetric_null": detection_rate(null_pressures, null_z, null_u, sigma),
            }
        )

    positive = next(
        row for row in sweep if row["pressure_sigma_psi"] == ACCEPTANCE["A10_positive_control_sigma_psi"]
    )
    negative = next(
        row for row in sweep if row["pressure_sigma_psi"] == ACCEPTANCE["A9_negative_control_sigma_psi"]
    )
    null_rate = float(negative["detection_rate_volumetric_null"])
    return {
        "base_productivity_index_bbl_per_day_psi": BASE_PRODUCTIVITY_INDEX,
        "n_observations": points,
        "r_squared": fit.r_squared,
        "relative_gas_in_place_error": fit.gas_in_place_scf / GAS_IN_PLACE_SCF - 1.0,
        "max_abs_residual_psia": max(abs(r) for r in fit.residuals),
        "max_abs_residual_fraction_of_initial_p_over_z": max(abs(r) for r in fit.residuals)
        / history.truth.initial_p_over_z_psia,
        "rms_residual_psia": math.sqrt(math.fsum(r * r for r in fit.residuals) / points),
        "curvature_coefficient_psia": curvature,
        "critical_t": critical,
        "noise_free_curvature_t_statistic": curvature_t_statistic(u, p_over_z),
        "sigma_p_over_z_at_expected_t_equals_critical_psia": sigma_p_over_z_star,
        "sigma_pressure_at_expected_t_equals_critical_psi": sigma_pressure_star,
        "mean_z_factor": mean_z,
        "residual_table": residual_table,
        "noise_sweep": sweep,
        "a10_positive_control_rate": positive["detection_rate_water_drive"],
        "a10_passed": float(positive["detection_rate_water_drive"]) >= ACCEPTANCE["A10_min_detection_rate"],
        "a9_negative_control_rate": null_rate,
        "a9_passed": (
            ACCEPTANCE["A9_detection_rate_low"] <= null_rate <= ACCEPTANCE["A9_detection_rate_high"]
        ),
    }


def experiment_holdout() -> dict[str, object]:
    """E7 -- a chronological holdout the wrong model can still pass."""
    history = simulate(BASE_PRODUCTIVITY_INDEX)
    cumulative, p_over_z, z_factors, pressures = observed(history)
    points = len(cumulative)
    count = round(HOLDOUT_CALIBRATION_FRACTION * (points - 1)) + 1
    fit = fit_pz_depletion(cumulative[:count], p_over_z[:count])
    predicted = [fit.intercept + fit.slope * cumulative[i] for i in range(count, points)]
    p_over_z_errors = [pred - p_over_z[i] for pred, i in zip(predicted, range(count, points), strict=True)]
    pressure_errors = [
        pred * z_factors[i] - pressures[i] for pred, i in zip(predicted, range(count, points), strict=True)
    ]
    held = len(pressure_errors)
    rmse_pressure = math.sqrt(math.fsum(e * e for e in pressure_errors) / held)
    produced = cumulative[count - 1]
    return {
        "calibration_points": count,
        "calibration_years": (count - 1) * OBSERVATION_STRIDE * HORIZON_DAYS / BASE_STEPS / 365.25,
        "holdout_points": held,
        "calibration_relative_gas_in_place_error": fit.gas_in_place_scf / GAS_IN_PLACE_SCF - 1.0,
        "calibration_r_squared": fit.r_squared,
        "holdout_rmse_p_over_z_psia": math.sqrt(math.fsum(e * e for e in p_over_z_errors) / held),
        "holdout_rmse_pressure_psia": rmse_pressure,
        "holdout_rmse_fraction_of_initial_pressure": rmse_pressure / INITIAL_PRESSURE_PSIA,
        "plan_section_12_holdout_gate": 0.01,
        "passes_plan_holdout_gate": rmse_pressure / INITIAL_PRESSURE_PSIA < 0.01,
        "relative_remaining_gas_error_at_calibration_end": (fit.gas_in_place_scf - produced)
        / (GAS_IN_PLACE_SCF - produced)
        - 1.0,
    }


def experiment_water_production() -> dict[str, object]:
    """E8 -- the observable that would have given the mechanism away."""
    history = simulate(BASE_PRODUCTIVITY_INDEX, produced_water_fraction=PRODUCED_WATER_FRACTION_VARIANT)
    cumulative, p_over_z, _, _ = observed(history)
    fit = fit_pz_depletion(cumulative, p_over_z)
    samples = []
    for fraction in (0.25, 0.5, 0.75, 1.0):
        index = int(fraction * BASE_STEPS)
        gas = history.true_cumulative_gas_scf[index]
        water = history.cumulative_water_stb[index]
        samples.append(
            {
                "years": history.times_days[index] / 365.25,
                "cumulative_water_stb": water,
                "cumulative_gas_scf": gas,
                "water_gas_ratio_stb_per_mmscf": water / (gas / 1.0e6),
            }
        )
    return {
        "produced_water_fraction": PRODUCED_WATER_FRACTION_VARIANT,
        "r_squared": fit.r_squared,
        "relative_gas_in_place_error": fit.gas_in_place_scf / GAS_IN_PLACE_SCF - 1.0,
        "samples": samples,
        "note": (
            "produced_water_fraction is a declared bookkeeping fraction of the incremental "
            "influx, not a relative-permeability or saturation calculation. The water-gas "
            "ratio it produces is indicative of the order of magnitude only."
        ),
    }


def noisy_p_over_z(
    pressures: tuple[float, ...],
    z_values: tuple[float, ...],
    sigma: float,
    rng: random.Random,
    *,
    z_at_measured_pressure: bool,
) -> tuple[float, ...]:
    """Return one noisy p/Z realisation.

    Two ways of forming the ordinate. ``z_at_measured_pressure=False`` divides the
    noisy pressure by the noise-free true deviation factor, which is what E6 does.
    ``True`` re-evaluates the correlation at the measured pressure, which is what an
    engineer with a pressure reading in hand actually does. The two differ because Z
    varies with pressure, and the difference is reported rather than assumed small.
    """
    if not z_at_measured_pressure:
        return tuple(
            (pressure + rng.gauss(0.0, sigma)) / z for pressure, z in zip(pressures, z_values, strict=True)
        )
    measured = [pressure + rng.gauss(0.0, sigma) for pressure in pressures]
    return tuple(pressure / z_of_pressure(pressure) for pressure in measured)


def detection_rate_at(
    pressures: tuple[float, ...],
    z_values: tuple[float, ...],
    design: tuple[float, ...],
    sigma: float,
    *,
    seed: int,
    replicates: int,
    critical: float,
    z_at_measured_pressure: bool = False,
) -> float:
    """Fraction of ``replicates`` in which the curvature t-test fires."""
    rng = random.Random(seed)
    detected = 0
    for _ in range(replicates):
        noisy = noisy_p_over_z(pressures, z_values, sigma, rng, z_at_measured_pressure=z_at_measured_pressure)
        if abs(curvature_t_statistic(design, noisy)) > critical:
            detected += 1
    return detected / replicates


def experiment_post_review_sensitivities() -> dict[str, object]:
    """E9 -- sensitivities added after the referee pass. Not pre-registered.

    Four questions the first version of the report answered by assertion rather than
    by running anything: where the detector's power actually crosses one half, what
    the choice of a single seed is worth, whether evaluating Z at the measured rather
    than the true pressure matters, and whether the deviation-factor correlation
    itself can imitate the curvature the detector looks for.
    """
    history = simulate(BASE_PRODUCTIVITY_INDEX)
    cumulative, p_over_z, z_factors, pressures = observed(history)
    design = tuple(value / GAS_IN_PLACE_SCF for value in cumulative)
    critical = student_t_quantile(0.5 + CONFIDENCE / 2.0, len(cumulative) - 3)

    null_history = simulate(0.0)
    null_cumulative, _, null_z, null_pressures = observed(null_history)
    null_design = tuple(value / GAS_IN_PLACE_SCF for value in null_cumulative)

    # --- empirical power curve and the true half-power point --------------------
    power_rows = [
        {
            "pressure_sigma_psi": sigma,
            "detection_rate": detection_rate_at(
                pressures,
                z_factors,
                design,
                sigma,
                seed=POWER_CURVE_SEED,
                replicates=POWER_CURVE_REPLICATES,
                critical=critical,
            ),
        }
        for sigma in POWER_CURVE_SIGMAS_PSI
    ]
    half_power_sigma: float | None = None
    for lower, upper in itertools.pairwise(power_rows):
        low_rate = float(lower["detection_rate"])
        high_rate = float(upper["detection_rate"])
        if (low_rate - 0.5) * (high_rate - 0.5) <= 0.0 and low_rate != high_rate:
            low_sigma = float(lower["pressure_sigma_psi"])
            high_sigma = float(upper["pressure_sigma_psi"])
            half_power_sigma = low_sigma + (low_rate - 0.5) * (high_sigma - low_sigma) / (
                low_rate - high_rate
            )
            break

    # --- one seed against eight -------------------------------------------------
    seed_rows = [
        {
            "seed": seed,
            "detection_rate_water_drive": detection_rate_at(
                pressures,
                z_factors,
                design,
                SEED_SENSITIVITY_SIGMA_PSI,
                seed=seed,
                replicates=NOISE_REPLICATES,
                critical=critical,
            ),
            "detection_rate_volumetric_null": detection_rate_at(
                null_pressures,
                null_z,
                null_design,
                SEED_SENSITIVITY_SIGMA_PSI,
                seed=seed,
                replicates=NOISE_REPLICATES,
                critical=critical,
            ),
        }
        for seed in SEED_SENSITIVITY_SEEDS
    ]
    pooled_null = detection_rate_at(
        null_pressures,
        null_z,
        null_design,
        SEED_SENSITIVITY_SIGMA_PSI,
        seed=POOLED_NULL_SEED,
        replicates=POOLED_NULL_REPLICATES,
        critical=critical,
    )
    nominal = 1.0 - CONFIDENCE
    standard_error_400 = math.sqrt(nominal * (1.0 - nominal) / NOISE_REPLICATES)

    # --- Z at the measured pressure rather than at truth ------------------------
    z_handling_rows = [
        {
            "pressure_sigma_psi": sigma,
            "detection_rate_z_at_true_pressure": detection_rate_at(
                pressures,
                z_factors,
                design,
                sigma,
                seed=NOISE_SEED,
                replicates=NOISE_REPLICATES,
                critical=critical,
            ),
            "detection_rate_z_at_measured_pressure": detection_rate_at(
                pressures,
                z_factors,
                design,
                sigma,
                seed=NOISE_SEED,
                replicates=NOISE_REPLICATES,
                critical=critical,
                z_at_measured_pressure=True,
            ),
        }
        for sigma in Z_HANDLING_SIGMAS_PSI
    ]

    # --- the deviation-factor correlation itself --------------------------------
    hy_p_over_z = tuple(pressure / z_of_pressure_hall_yarborough(pressure) for pressure in pressures)
    hy_null_p_over_z = tuple(
        pressure / z_of_pressure_hall_yarborough(pressure) for pressure in null_pressures
    )
    matched_fit = fit_pz_depletion(cumulative, p_over_z)
    mismatched_fit = fit_pz_depletion(cumulative, hy_p_over_z)
    mismatched_null_fit = fit_pz_depletion(null_cumulative, hy_null_p_over_z)
    consistent_history = simulate(BASE_PRODUCTIVITY_INDEX, z_function=z_of_pressure_hall_yarborough)
    consistent_cumulative, consistent_p_over_z, _, _ = observed(consistent_history)
    consistent_fit = fit_pz_depletion(consistent_cumulative, consistent_p_over_z)

    return {
        "status": (
            "post-review sensitivities, added after the referee pass and after the "
            "pre-registered experiments were run. Not pre-registered; no acceptance "
            "criterion depends on them."
        ),
        "power_curve": {
            "replicates_per_level": POWER_CURVE_REPLICATES,
            "seed": POWER_CURVE_SEED,
            "levels": power_rows,
            "half_power_sigma_pressure_psi": half_power_sigma,
            "monte_carlo_standard_error_at_half_power": math.sqrt(0.25 / POWER_CURVE_REPLICATES),
            "note": (
                "The closed-form sigma reported by E6 is the level at which the EXPECTED "
                "statistic equals the critical value. It is not the 50 percent-power point, "
                "because the statistic is a ratio with a random denominator. This curve "
                "measures the 50 percent-power point directly."
            ),
        },
        "seed_sensitivity": {
            "pressure_sigma_psi": SEED_SENSITIVITY_SIGMA_PSI,
            "replicates_per_seed": NOISE_REPLICATES,
            "levels": seed_rows,
            "null_rate_min": min(float(row["detection_rate_volumetric_null"]) for row in seed_rows),
            "null_rate_max": max(float(row["detection_rate_volumetric_null"]) for row in seed_rows),
            "null_rate_mean": math.fsum(float(row["detection_rate_volumetric_null"]) for row in seed_rows)
            / len(seed_rows),
            "pooled_null_rate": pooled_null,
            "pooled_null_replicates": POOLED_NULL_REPLICATES,
            "pooled_null_seed": POOLED_NULL_SEED,
            "binomial_standard_error_at_nominal_400": standard_error_400,
            "derived_three_sigma_band": [
                nominal - 3.0 * standard_error_400,
                nominal + 3.0 * standard_error_400,
            ],
            "declared_a9_band": [
                ACCEPTANCE["A9_detection_rate_low"],
                ACCEPTANCE["A9_detection_rate_high"],
            ],
            "note": (
                "The pre-registered A9 band was declared without a binomial derivation and "
                "is loose: its upper limit sits about 6.4 standard errors above nominal. The "
                "band is reported here as derived, alongside the declared one; the declared "
                "band is the one the run was scored against and it has not been changed."
            ),
        },
        "z_ordinate_handling": {
            "seed": NOISE_SEED,
            "replicates_per_level": NOISE_REPLICATES,
            "levels": z_handling_rows,
            "note": (
                "E6 divides the noisy pressure by the noise-free true deviation factor. "
                "Re-evaluating the correlation at the measured pressure is what an engineer "
                "does, and it raises the detection rate at every level tested, so the "
                "pre-registered sweep understates detectability slightly."
            ),
        },
        "z_correlation_sensitivity": {
            "max_relative_difference_dak_vs_hall_yarborough": max(
                abs(z_of_pressure_hall_yarborough(pressure) / z - 1.0)
                for pressure, z in zip(pressures, z_factors, strict=True)
            ),
            "base_case_matched_relative_gas_in_place_error": (
                matched_fit.gas_in_place_scf / GAS_IN_PLACE_SCF - 1.0
            ),
            "base_case_mismatched_relative_gas_in_place_error": (
                mismatched_fit.gas_in_place_scf / GAS_IN_PLACE_SCF - 1.0
            ),
            "base_case_consistent_hall_yarborough_relative_gas_in_place_error": (
                consistent_fit.gas_in_place_scf / GAS_IN_PLACE_SCF - 1.0
            ),
            "base_case_matched_curvature_t": curvature_t_statistic(design, p_over_z),
            "base_case_mismatched_curvature_t": curvature_t_statistic(design, hy_p_over_z),
            "null_mismatched_relative_gas_in_place_error": (
                mismatched_null_fit.gas_in_place_scf / GAS_IN_PLACE_SCF - 1.0
            ),
            "null_mismatched_curvature_t": curvature_t_statistic(null_design, hy_null_p_over_z),
            "null_mismatched_max_abs_residual_psia": max(abs(r) for r in mismatched_null_fit.residuals),
            "critical_t": critical,
            "note": (
                "Matched means the analyst uses the correlation the history was generated "
                "with; mismatched means the history is DAK and the analyst reads Z from "
                "Hall-Yarborough, which is the realistic case since nature uses neither. The "
                "gas-in-place bias is insensitive to the choice. The curvature detector is "
                "not: a mismatched correlation on a strictly volumetric history produces a "
                "curvature statistic larger than the aquifer's own, with the opposite sign."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def evaluate_acceptance(results: dict[str, object]) -> dict[str, object]:
    """Score the pre-registered acceptance criteria against the results."""
    sweep = results["strength_sweep"]
    reduction = results["zero_aquifer_reduction"]
    oracle = results["known_influx_oracle"]
    refinement = results["timestep_refinement"]
    detect = results["residuals_and_detectability"]
    progressive = results["progressive_fits"]

    worst_solver_residual = max(float(row["max_solver_residual_p_over_z_psia"]) for row in sweep)
    smallest_quoted_signal = min(
        float(row["max_abs_residual_psia"])
        for row in sweep
        if abs(float(row["relative_gas_in_place_error"])) >= ACCEPTANCE["A6_min_relative_bias"]
    )
    orders_below = math.log10(smallest_quoted_signal / worst_solver_residual)

    counterexamples = [
        row
        for row in sweep
        if float(row["r_squared"]) >= ACCEPTANCE["A6_min_r_squared"]
        and abs(float(row["relative_gas_in_place_error"])) >= ACCEPTANCE["A6_min_relative_bias"]
    ]
    errors = [float(row["relative_gas_in_place_error"]) for row in sweep]
    monotone = all(later > earlier for earlier, later in itertools.pairwise(errors))

    base_rows = [
        row for row in progressive if row["productivity_index_bbl_per_day_psi"] == BASE_PRODUCTIVITY_INDEX
    ]
    early = next(float(r["relative_gas_in_place_error"]) for r in base_rows if r["history_fraction"] == 0.2)
    late = next(float(r["relative_gas_in_place_error"]) for r in base_rows if r["history_fraction"] == 1.0)
    drift = abs(late - early)

    return {
        "A1_zero_aquifer_bitwise_reduction": reduction["a1_passed"],
        "A2_zero_aquifer_gas_in_place": reduction["a2_passed"],
        "A3_worst_solver_residual_psia": worst_solver_residual,
        "A3_smallest_quoted_misfit_psia": smallest_quoted_signal,
        "A3_orders_of_magnitude_below_signal": orders_below,
        "A3_passed": worst_solver_residual < ACCEPTANCE["A3_max_solver_residual_psia"]
        and orders_below >= ACCEPTANCE["A3_min_orders_below_signal"],
        "A4_timestep_refinement": refinement["a4_passed"],
        "A5_known_influx_oracle": oracle["a5_passed"],
        "A6_counterexample_count": len(counterexamples),
        "A6_passed": len(counterexamples) >= 1,
        "A7_monotone_in_productivity_index": monotone,
        "A8_drift_fraction_of_true_g": drift,
        "A8_passed": drift >= ACCEPTANCE["A8_min_drift_fraction_of_g"],
        "A9_negative_control": detect["a9_passed"],
        "A10_positive_control": detect["a10_passed"],
    }


def verdict(acceptance: dict[str, object]) -> str:
    """Return the case verdict implied by the pre-registered decision rules."""
    if not (acceptance["A1_zero_aquifer_bitwise_reduction"] and acceptance["A2_zero_aquifer_gas_in_place"]):
        return "INVALID: the generator does not reduce to the volumetric case at J = 0"
    if not acceptance["A5_known_influx_oracle"]:
        return "INVALID: the generator's own material balance does not close"
    if not (acceptance["A3_passed"] and acceptance["A4_timestep_refinement"]):
        return "INCONCLUSIVE: numerical error is not separable from the demonstrated bias"
    if not acceptance["A6_passed"]:
        return "INCONCLUSIVE: no setting produced a high-R-squared fit with a material bias"
    if not (acceptance["A9_negative_control"] and acceptance["A10_positive_control"]):
        return "PARTIAL: bias established, detectability conclusions withdrawn (controls failed)"
    return "ESTABLISHED: high-R-squared volumetric fits with material, drifting gas-in-place bias"


def summarise(results: dict[str, object]) -> str:
    """Render the human-readable run summary printed to stdout and saved as text."""
    lines: list[str] = []
    sweep = results["strength_sweep"]
    lines.append("Case A4 -- when a straight p/Z line is convincing and wrong")
    lines.append(f"True gas in place: {GAS_IN_PLACE_SCF:.4g} scf at {INITIAL_PRESSURE_PSIA:g} psia")
    lines.append("")
    lines.append("E1  Aquifer strength against recovered gas in place (full 12-year history)")
    lines.append(
        f"{'J':>7} {'tau,d':>9} {'We/HCPV':>9} {'p_end':>8} {'R^2':>10} "
        f"{'G error':>10} {'remaining':>10} {'bias/SE':>9}"
    )
    for row in sweep:
        tau = row["aquifer_time_constant_days"]
        tau_text = f"{float(tau):9.0f}" if tau is not None else "      inf"
        ratio = row["bias_over_stderr"]
        ratio_text = f"{float(ratio):9.1f}" if ratio is not None else "      n/a"
        lines.append(
            f"{float(row['productivity_index_bbl_per_day_psi']):7.2f} {tau_text} "
            f"{float(row['invaded_pore_volume_fraction']):9.4f} "
            f"{float(row['terminal_pressure_psia']):8.1f} "
            f"{float(row['r_squared']):10.6f} "
            f"{float(row['relative_gas_in_place_error']) * 100:+9.2f}% "
            f"{float(row['relative_remaining_gas_error']) * 100:+9.2f}% {ratio_text}"
        )
    lines.append("")
    lines.append("E2  Recovered gas-in-place error against fraction of history observed")
    progressive = results["progressive_fits"]
    header = "      J  " + "".join(f"{f:>9.0%}" for f in HISTORY_FRACTIONS)
    lines.append(header)
    for productivity_index in PRODUCTIVITY_INDICES:
        cells = []
        for fraction in HISTORY_FRACTIONS:
            value = next(
                float(r["relative_gas_in_place_error"])
                for r in progressive
                if r["productivity_index_bbl_per_day_psi"] == productivity_index
                and r["history_fraction"] == fraction
            )
            cells.append(f"{value * 100:+8.2f}%")
        lines.append(f"{productivity_index:7.2f}  " + "".join(cells))
    lines.append("")

    reduction = results["zero_aquifer_reduction"]
    oracle = results["known_influx_oracle"]
    refinement = results["timestep_refinement"]
    lines.append("E3  Exact reduction at J = 0")
    lines.append(f"    all six series bitwise identical : {reduction['all_series_bitwise_identical']}")
    lines.append(
        f"    recovered G relative error       : {float(reduction['relative_gas_in_place_error']):.3e}"
    )
    lines.append("E4  Known-influx balance (Oracle 2)")
    lines.append(
        f"    worst relative error over all strengths and observations : "
        f"{float(oracle['worst_relative_error']):.3e}"
    )
    lines.append("E5  Timestep refinement")
    for key in (f"J_{BASE_PRODUCTIVITY_INDEX:g}", f"J_{STRONGEST_PRODUCTIVITY_INDEX:g}"):
        block = refinement[key]
        lines.append(
            f"    {key}: recovered-G error span over dt to dt/8 = "
            f"{float(block['error_span_over_refinement']):.3e}"
        )
    lines.append("")

    detect = results["residuals_and_detectability"]
    lines.append(f"E6  Residual pattern, base case J = {BASE_PRODUCTIVITY_INDEX:g}")
    lines.append(
        f"    R^2 {float(detect['r_squared']):.6f}, G error "
        f"{float(detect['relative_gas_in_place_error']) * 100:+.2f}%, "
        f"largest residual {float(detect['max_abs_residual_psia']):.2f} psia "
        f"({float(detect['max_abs_residual_fraction_of_initial_p_over_z']) * 100:.2f}% of pi/Zi)"
    )
    lines.append(
        f"    closed form: expected t equals the critical value at sigma_p = "
        f"{float(detect['sigma_pressure_at_expected_t_equals_critical_psi']):.1f} psi "
        f"(this is NOT the half-power point; see E9)"
    )
    lines.append(f"{'sigma_p, psi':>14} {'detect, water drive':>21} {'detect, volumetric null':>25}")
    sweep_rows = detect["noise_sweep"]
    for row in sweep_rows:
        lines.append(
            f"{float(row['pressure_sigma_psi']):14.1f} "
            f"{float(row['detection_rate_water_drive']):21.3f} "
            f"{float(row['detection_rate_volumetric_null']):25.3f}"
        )
    lines.append("")

    holdout = results["holdout"]
    lines.append("E7  Chronological holdout, base case")
    lines.append(
        f"    calibrated on {holdout['calibration_points']} points "
        f"({float(holdout['calibration_years']):.1f} years), G error "
        f"{float(holdout['calibration_relative_gas_in_place_error']) * 100:+.2f}%"
    )
    lines.append(
        f"    holdout pressure RMSE {float(holdout['holdout_rmse_pressure_psia']):.1f} psi = "
        f"{float(holdout['holdout_rmse_fraction_of_initial_pressure']) * 100:.3f}% of p_i "
        f"(PLAN section 12 gate: 1%) -> passes = {holdout['passes_plan_holdout_gate']}"
    )
    lines.append("")

    water = results["water_production"]
    lines.append("E8  Water-production variant")
    samples = water["samples"]
    for sample in samples:
        lines.append(
            f"    t = {float(sample['years']):5.2f} yr : WGR = "
            f"{float(sample['water_gas_ratio_stb_per_mmscf']):7.2f} STB/MMscf"
        )
    lines.append("")

    post = results["post_review_sensitivities"]
    lines.append("E9  Post-review sensitivities (NOT pre-registered)")
    power = post["power_curve"]
    lines.append(
        f"    empirical half-power sigma_p = "
        f"{float(power['half_power_sigma_pressure_psi']):.1f} psi "
        f"({power['replicates_per_level']} replicates per level, seed {power['seed']})"
    )
    for row in power["levels"]:
        lines.append(
            f"      sigma_p {float(row['pressure_sigma_psi']):5.1f} psi : "
            f"detection {float(row['detection_rate']):.4f}"
        )
    seeds = post["seed_sensitivity"]
    lines.append(
        f"    null detection rate at sigma_p = {float(seeds['pressure_sigma_psi']):.0f} psi over "
        f"{len(seeds['levels'])} seeds: {float(seeds['null_rate_min']):.4f} to "
        f"{float(seeds['null_rate_max']):.4f}, mean {float(seeds['null_rate_mean']):.4f}; "
        f"pooled over {seeds['pooled_null_replicates']} replicates: "
        f"{float(seeds['pooled_null_rate']):.4f}"
    )
    low, high = seeds["derived_three_sigma_band"]
    lines.append(
        f"    A9 band as declared {seeds['declared_a9_band']}, as derived from the binomial "
        f"standard error [{float(low):.3f}, {float(high):.3f}]"
    )
    handling = post["z_ordinate_handling"]
    lines.append("    p/Z ordinate formed with Z at truth against Z at the measured pressure")
    for row in handling["levels"]:
        lines.append(
            f"      sigma_p {float(row['pressure_sigma_psi']):5.1f} psi : "
            f"Z at truth {float(row['detection_rate_z_at_true_pressure']):.4f}, "
            f"Z at measured {float(row['detection_rate_z_at_measured_pressure']):.4f}"
        )
    correlation = post["z_correlation_sensitivity"]
    matched = float(correlation["base_case_matched_relative_gas_in_place_error"])
    mismatched = float(correlation["base_case_mismatched_relative_gas_in_place_error"])
    consistent = float(correlation["base_case_consistent_hall_yarborough_relative_gas_in_place_error"])
    lines.append(
        f"    DAK against Hall-Yarborough: worst Z difference "
        f"{float(correlation['max_relative_difference_dak_vs_hall_yarborough']) * 100:.2f}%; "
        f"base-case G error {matched * 100:+.2f}% matched, "
        f"{mismatched * 100:+.2f}% mismatched, {consistent * 100:+.2f}% consistent"
    )
    lines.append(
        f"    curvature t on a VOLUMETRIC history read with the wrong correlation: "
        f"{float(correlation['null_mismatched_curvature_t']):.2f} against a critical value of "
        f"{float(correlation['critical_t']):.2f} "
        f"(water drive, matched: {float(correlation['base_case_matched_curvature_t']):.2f})"
    )
    lines.append("")

    acceptance = results["acceptance"]
    lines.append("Pre-registered acceptance")
    for key in sorted(acceptance):
        lines.append(f"    {key:<42} {acceptance[key]}")
    lines.append("")
    lines.append(f"Verdict: {results['verdict']}")
    return "\n".join(lines)


def main() -> int:
    """Run every experiment, write the run record, print the summary."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="fresh, empty run directory")
    arguments = parser.parse_args()

    config = {
        "case_id": "A4_misleading_fit_counterexample",
        "gas_in_place_scf": GAS_IN_PLACE_SCF,
        "initial_pressure_psia": INITIAL_PRESSURE_PSIA,
        "temperature_degf": TEMPERATURE_DEGF,
        "specific_gravity": SPECIFIC_GRAVITY,
        "z_correlation": "dranchuk-abou-kassem on standing dry-gas pseudocriticals",
        "standard_conditions": STANDARD.describe(),
        "minimum_pressure_psia": MINIMUM_PRESSURE_PSIA,
        "horizon_days": HORIZON_DAYS,
        "recovery_fraction_of_g": RECOVERY_FRACTION,
        "base_steps": BASE_STEPS,
        "observation_stride": OBSERVATION_STRIDE,
        "aquifer_initial_pressure_psia": AQUIFER_INITIAL_PRESSURE_PSIA,
        "aquifer_water_volume_bbl": AQUIFER_WATER_VOLUME_BBL,
        "aquifer_total_compressibility_per_psi": AQUIFER_COMPRESSIBILITY_PER_PSI,
        "productivity_indices_bbl_per_day_psi": list(PRODUCTIVITY_INDICES),
        "base_productivity_index_bbl_per_day_psi": BASE_PRODUCTIVITY_INDEX,
        "history_fractions": list(HISTORY_FRACTIONS),
        "refinement_multipliers": list(REFINEMENT_MULTIPLIERS),
        "holdout_calibration_fraction": HOLDOUT_CALIBRATION_FRACTION,
        "produced_water_fraction_variant": PRODUCED_WATER_FRACTION_VARIANT,
        "noise_sigmas_psi": list(NOISE_SIGMAS_PSI),
        "noise_replicates": NOISE_REPLICATES,
        "noise_seed": NOISE_SEED,
        "confidence": CONFIDENCE,
        "acceptance_thresholds": ACCEPTANCE,
        "post_review_power_curve_sigmas_psi": list(POWER_CURVE_SIGMAS_PSI),
        "post_review_power_curve_replicates": POWER_CURVE_REPLICATES,
        "post_review_power_curve_seed": POWER_CURVE_SEED,
        "post_review_seed_sensitivity_seeds": list(SEED_SENSITIVITY_SEEDS),
        "post_review_seed_sensitivity_sigma_psi": SEED_SENSITIVITY_SIGMA_PSI,
        "post_review_pooled_null_replicates": POOLED_NULL_REPLICATES,
        "post_review_pooled_null_seed": POOLED_NULL_SEED,
        "post_review_z_handling_sigmas_psi": list(Z_HANDLING_SIGMAS_PSI),
        "post_review_alternative_z_correlation": "hall-yarborough",
    }

    with RunRecord.open(
        arguments.out,
        label="A4 misleading p/Z fit counterexample",
        config=config,
        seed=NOISE_SEED,
        settings={"solver_tolerance": 1.0e-12, "max_iterations": 200},
        repo_root=RECORDED_REPO_ROOT,
    ) as record:
        results: dict[str, object] = {
            "case_id": "A4_misleading_fit_counterexample",
            "case_type": "synthetic_structural_counterexample",
            "true_gas_in_place_scf": GAS_IN_PLACE_SCF,
            "strength_sweep": experiment_strength_sweep(),
            "progressive_fits": experiment_progressive_fits(),
            "zero_aquifer_reduction": experiment_zero_aquifer_reduction(),
            "known_influx_oracle": experiment_known_influx_oracle(),
            "timestep_refinement": experiment_timestep_refinement(),
            "residuals_and_detectability": experiment_residuals_and_detectability(),
            "holdout": experiment_holdout(),
            "water_production": experiment_water_production(),
            "post_review_sensitivities": experiment_post_review_sensitivities(),
        }
        results["acceptance"] = evaluate_acceptance(results)
        acceptance = results["acceptance"]
        results["verdict"] = verdict(acceptance)

        text = summarise(results)
        record.write_json("summary.json", results)
        record.write_text("summary.txt", text + "\n")
        record.metrics(
            verdict=results["verdict"],
            base_r_squared=results["residuals_and_detectability"]["r_squared"],
            base_relative_gas_in_place_error=(
                results["residuals_and_detectability"]["relative_gas_in_place_error"]
            ),
            worst_relative_gas_in_place_error=max(
                float(row["relative_gas_in_place_error"]) for row in results["strength_sweep"]
            ),
            worst_solver_residual_p_over_z_psia=acceptance["A3_worst_solver_residual_psia"],
            known_influx_oracle_worst_relative_error=(results["known_influx_oracle"]["worst_relative_error"]),
            sigma_pressure_at_expected_t_equals_critical_psi=(
                results["residuals_and_detectability"]["sigma_pressure_at_expected_t_equals_critical_psi"]
            ),
            half_power_sigma_pressure_psi=(
                results["post_review_sensitivities"]["power_curve"]["half_power_sigma_pressure_psi"]
            ),
            holdout_rmse_fraction_of_initial_pressure=(
                results["holdout"]["holdout_rmse_fraction_of_initial_pressure"]
            ),
        )
        record.note(
            "Synthetic throughout. The generator is a coupled Fetkovich water-drive tank; the "
            "estimator is the volumetric p/Z x-intercept. They are structurally different models "
            "in separate library modules and share no balance or fitting code."
        )
        record.note(
            "The J = 0 member of the sweep uses a duck-typed four-field aquifer because "
            "FetkovichAquifer refuses a zero productivity index."
        )
        record.limitation(
            "No field data. Synthetic self-consistency of a generator with a known answer is not "
            "field validation, and the size of the bias reported here is a property of these "
            "declared aquifer parameters, not a general figure."
        )
        record.limitation(
            "Trapped gas behind the water front is not modelled. Including it would reduce the "
            "true recoverable gas further, so the recovery consequences reported here are "
            "optimistic relative to a real water-drive gas reservoir."
        )
        record.limitation(
            "Rock and connate-water expansion, condensate dropout, gas dissolved in water, and "
            "any areal or vertical pressure gradient within the tank are excluded."
        )
        record.limitation(
            "The detectability result is conditional on the declared detector (t-test on the "
            "quadratic term of a second-order fit), on 49 quarterly observations, and on "
            "independent Gaussian pressure error. A correlated or systematically biased "
            "pressure error would behave differently and was not tested."
        )
        record.limitation(
            "produced_water_fraction in E8 is a declared bookkeeping fraction, not a "
            "relative-permeability calculation; the water-gas ratios are indicative only."
        )
        record.limitation(
            "The E6 noise sweep forms the ordinate by dividing the noisy pressure by the "
            "noise-free true deviation factor, not by Z re-evaluated at the measured "
            "pressure. E9 shows the second choice raises the detection rate at every level "
            "tested, so the pre-registered sweep understates detectability slightly."
        )
        record.limitation(
            "The E6 sweep uses one seed, reset identically at every noise level and for both "
            "series, so its seven levels are rescalings of one draw set rather than seven "
            "independent experiments. E9 reports the spread over eight seeds and a pooled "
            "null rate; the declared seed's 0.0675 is a high draw."
        )
        record.limitation(
            "The curvature detector was characterised under independent Gaussian pressure "
            "error with the deviation-factor correlation held identical between generator "
            "and analyst. E9 shows a correlation mismatch alone -- DAK history read with "
            "Hall-Yarborough -- produces a larger curvature statistic than the aquifer does, "
            "of the opposite sign, on a strictly volumetric history. The curvature test is "
            "therefore not a clean aquifer diagnostic in the presence of correlation error."
        )
        record.limitation(
            "The average reservoir pressure is assumed to exist and to be unbiased. In a real "
            "water-drive reservoir the surviving wells are the ones the water has not reached, "
            "so the sampled average is biased high -- the same sign as the effect demonstrated "
            "here, which makes these bias figures conservative rather than pessimistic."
        )
        record.limitation(
            "Constant offtake for twelve years, 49 clean quarterly observations, no shut-ins, "
            "no rate or well-count changes, no gaps and no outliers. Real rate variation "
            "imprints pressure transients that are themselves a diagnostic, and no real "
            "history is this clean in either direction."
        )
        record.limitation(
            "The aquifer starts at equilibrium with the reservoir and is instantly "
            "pseudosteady. The smoothness of the influx that makes the misfit hard to detect "
            "is therefore partly a consequence of the model choice, not a demonstrated "
            "property of aquifers; a transient van Everdingen-Hurst aquifer is not "
            "implemented in this library and was not tested."
        )
        record.limitation(
            "Pre-registration rests on the author's word. The cases tree is untracked in git, "
            "so no commit timestamp separates protocol.md from the runs, and protocol.md's "
            "own mtime is later than both runs because of the disclosed run-001 amendment."
        )

    print(text)
    print(f"\nRun directory: {arguments.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

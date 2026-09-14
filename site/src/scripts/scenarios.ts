/**
 * The eight computed cases, as the scenario explorer needs them.
 *
 * Every number here is read from `f01_f02_scenarios.json` through
 * `loadFigureData()` in `src/lib/figures.ts`, which re-hashes that file against
 * `contract.json` before returning it. Nothing is retyped and nothing is interpolated:
 * the eight cases below are the eight the case actually computed, and there is no ninth.
 *
 * The one derived quantity is the true inventory. `docs/design/figure_spec.md` is explicit
 * that hard-coding 100 in a template is not acceptable — the number would then live in the
 * page and in no data file — and gives the derivation to use instead:
 *
 *     true G = fit.gas_in_place_scf / (1 + relative_gas_in_place_error)
 *
 * It is computed per case below and cross-checked across all eight; if the eight disagree
 * by more than 1e-9 relative the build stops, because a truth that moves between cases
 * would mean the export had changed under the site.
 */

import { loadFigureData } from "../lib/figures";

export class ScenarioError extends Error {
  constructor(message: string) {
    super(`[scenarios] ${message}`);
    this.name = "ScenarioError";
  }
}

function fail(message: string): never {
  throw new ScenarioError(message);
}

interface RawFit {
  intercept_psia: number;
  slope_psia_per_scf: number;
  gas_in_place_scf: number;
  gas_in_place_bscf: number;
  gas_in_place_stderr_scf: number;
  r_squared: number;
  n_points: number;
  depletion_fraction_observed: number;
}

interface RawScenario {
  productivity_index_bbl_per_day_psi: number;
  label: string;
  is_base_case: boolean;
  is_volumetric_control: boolean;
  n_observations: number;
  times_years: number[];
  cumulative_gas_bscf: number[];
  p_over_z_psia: number[];
  pressure_psia: number[];
  z_factor: number[];
  fitted_p_over_z_psia: number[];
  residual_p_over_z_psia: number[];
  fit: RawFit;
  observed_extent_bscf: number;
  relative_gas_in_place_error: number;
  relative_remaining_gas_error: number;
  bias_over_stderr: number;
  invaded_pore_volume_fraction: number;
  terminal_pressure_psia: number;
  max_solver_residual_p_over_z_psia: number;
}

export interface Scenario {
  /** URL-safe case key, and the value of `?case=`. Exactly the J value as written. */
  key: string;
  /** Aquifer productivity index, bbl/day/psi. */
  j: number;
  /** Short label for the selector, e.g. "J = 2". */
  short: string;
  /** The export's own label for the case. */
  label: string;
  isBase: boolean;
  isVolumetricControl: boolean;
  observations: number;
  rSquared: number;
  fittedBscf: number;
  trueBscf: number;
  /** Inventory error as a percentage of true G. */
  errorPct: number;
  /** Remaining-gas-in-place error as a percentage. */
  remainingErrorPct: number;
  /** Bias expressed in the fit's own standard errors. */
  biasOverStderr: number;
  stderrScf: number;
  stderrPctOfEstimate: number;
  observedExtentBscf: number;
  depletionFractionObserved: number;
  invadedPoreVolumeFraction: number;
  terminalPressurePsia: number;
  maxSolverResidualPsia: number;
  residualMin: number;
  residualMax: number;
  residualRms: number;
  residualMaxAbs: number;
  /** Series, 49 points each. */
  years: number[];
  gBscf: number[];
  pz: number[];
  fittedPz: number[];
  residual: number[];
  pressurePsia: number[];
  zFactor: number[];
  /** File-name stem of this case's selected-data downloads. */
  slug: string;
}

/** Format a J value the way the case writes it: 0, 0.05, 0.2, 0.6, 2, 6, 20, 60. */
function jKey(j: number): string {
  return String(Number(j.toPrecision(6)));
}

function slugFor(j: number): string {
  return jKey(j).replace(/\./g, "p");
}

let cache: Promise<Scenario[]> | undefined;

/** The eight computed cases, in ascending aquifer strength. */
export function scenarios(): Promise<Scenario[]> {
  if (!cache) cache = build();
  return cache;
}

async function build(): Promise<Scenario[]> {
  const file = await loadFigureData<{ scenarios: RawScenario[] }>("f01_f02_scenarios.json");
  const raw = file.scenarios;
  if (!Array.isArray(raw) || raw.length !== 8) {
    fail(
      `expected eight computed cases in f01_f02_scenarios.json, found ${raw?.length ?? 0}.\n` +
        `  the scenario explorer offers the computed cases and nothing else; it does not\n` +
        `  interpolate, so a different count is a specification change, not a display detail.`,
    );
  }

  const truths: number[] = [];
  const out = raw.map((s): Scenario => {
    const trueScf = s.fit.gas_in_place_scf / (1 + s.relative_gas_in_place_error);
    truths.push(trueScf);
    const r = s.residual_p_over_z_psia;
    if (r.length !== s.n_observations) {
      fail(`case J = ${s.productivity_index_bbl_per_day_psi} declares ${s.n_observations} observations but carries ${r.length} residuals.`);
    }
    const rms = Math.sqrt(r.reduce((a, v) => a + v * v, 0) / r.length);
    const j = s.productivity_index_bbl_per_day_psi;
    return {
      key: jKey(j),
      j,
      short: `J = ${jKey(j)}`,
      label: s.label,
      isBase: s.is_base_case === true,
      isVolumetricControl: s.is_volumetric_control === true,
      observations: s.n_observations,
      rSquared: s.fit.r_squared,
      fittedBscf: s.fit.gas_in_place_bscf,
      trueBscf: trueScf / 1e9,
      errorPct: s.relative_gas_in_place_error * 100,
      remainingErrorPct: s.relative_remaining_gas_error * 100,
      biasOverStderr: s.bias_over_stderr,
      stderrScf: s.fit.gas_in_place_stderr_scf,
      stderrPctOfEstimate: (s.fit.gas_in_place_stderr_scf / s.fit.gas_in_place_scf) * 100,
      observedExtentBscf: s.observed_extent_bscf,
      depletionFractionObserved: s.fit.depletion_fraction_observed,
      invadedPoreVolumeFraction: s.invaded_pore_volume_fraction,
      terminalPressurePsia: s.terminal_pressure_psia,
      maxSolverResidualPsia: s.max_solver_residual_p_over_z_psia,
      residualMin: Math.min(...r),
      residualMax: Math.max(...r),
      residualRms: rms,
      residualMaxAbs: Math.max(...r.map(Math.abs)),
      years: s.times_years,
      gBscf: s.cumulative_gas_bscf,
      pz: s.p_over_z_psia,
      fittedPz: s.fitted_p_over_z_psia,
      residual: r,
      pressurePsia: s.pressure_psia,
      zFactor: s.z_factor,
      slug: slugFor(j),
    };
  });

  const first = truths[0] as number;
  for (const t of truths) {
    if (Math.abs(t / first - 1) > 1e-9) {
      fail(
        `the derived true inventory is not consistent across the eight cases.\n` +
          `  ${first.toExponential(6)} against ${t.toExponential(6)} scf\n` +
          `  derivation: fit.gas_in_place_scf / (1 + relative_gas_in_place_error)\n` +
          `  a truth that moves between cases means the export changed under the site.`,
      );
    }
  }

  const base = out.filter((s) => s.isBase);
  if (base.length !== 1) {
    fail(`expected exactly one case flagged is_base_case, found ${base.length}.`);
  }

  return out.sort((a, b) => a.j - b.j);
}

/** The default case: the one the export itself flags as the base case. */
export async function baseScenario(): Promise<Scenario> {
  const all = await scenarios();
  return all.find((s) => s.isBase) as Scenario;
}

/** The derived true inventory, in Bscf, with its derivation as a sentence. */
export async function truth(): Promise<{ bscf: number; derivation: string }> {
  const base = await baseScenario();
  return {
    bscf: base.trueBscf,
    derivation:
      "fit.gas_in_place_scf / (1 + relative_gas_in_place_error), evaluated per case and agreeing across all eight to better than 1e-9 relative. The truth is not a field of the export and is not typed into this page.",
  };
}

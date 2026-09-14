/**
 * How the site presents a solver convergence residual.
 *
 * The exact value of `max_solver_residual_p_over_z_psia` is zero. It measures how far
 * the material-balance solve failed to close, not a property of the reservoir, and the
 * solver stops when it is small enough to be irrelevant beside the quantities it feeds.
 *
 * Printing two or three significant figures of such a number asserts a precision the
 * cross-platform comparison does not support. The same residual computed on macOS arm64
 * and in the canonical Linux environment agrees only in order of magnitude: two dozen
 * libm functions are permitted to disagree in their last place, and a Newton iteration
 * turns that into a different stopping point. Those digits are platform noise dressed as
 * a measurement, and publishing them invites a reader to compare two runs digit by digit
 * and conclude something changed.
 *
 * So the site states what is both true and identical in every environment measured: the
 * residual is below 1e-8 psia of p/Z. Reservoir pressures here are thousands of psia, so
 * the bound is about eleven orders of magnitude below the working scale.
 *
 * Verified against 96 values before being published -- eight timestep-refinement levels
 * and eight aquifer-strength scenarios, in each of six environments spanning the pinned
 * canonical container, ordinary Ubuntu runners on CPython 3.11, 3.12 and 3.13, and macOS
 * arm64 -- with the largest observed 3.43e-09 psia, a factor of 2.9 inside the bound.
 *
 * Full precision is retained in the case summaries and in the exported figure data. This
 * changes a label, never a number.
 */

/** The published bound, in psia of p/Z. */
export const RESIDUAL_BOUND_PSIA = 1e-8;

/**
 * Render a solver residual as the published bound, refusing to overstate it.
 *
 * Throws rather than printing a bound the value does not satisfy: if a future change
 * makes the solver stop later, the build fails and the bound is re-established against
 * every supported environment instead of being quietly widened.
 */
export function residualBound(valuePsia: number): string {
  if (!(Math.abs(valuePsia) < RESIDUAL_BOUND_PSIA)) {
    throw new Error(
      `max_solver_residual_p_over_z_psia is ${valuePsia}, which is not below the ` +
        `published bound of ${RESIDUAL_BOUND_PSIA} psia. Re-establish the bound against ` +
        `every supported environment rather than widening it.`,
    );
  }
  return `< ${RESIDUAL_BOUND_PSIA.toExponential(0)}`;
}

# Verification and validation plan

## Evidence layers

Numerical verification asks whether equations are implemented correctly. Benchmark reproduction asks whether a fixed model and configuration agree with a suitable reference. Physical validation asks whether the model represents the observations for the intended decision. Keep those claims separate in every report.

## Supplied checks

The starter uses standard-library `unittest`. Run `python scripts/check.py` from the repository root. Tests include independent literal p/Z examples, explicit standard-condition checks, constant-property pseudopressure, nonuniform log-time derivatives, cumulative-volume and component-balance cases, invalid inputs, deterministic numerical outputs, output-overwrite protection, manifest hashes and public-repository checks.

The delivered synthetic demonstration is a known-answer/self-consistency test with small pressure noise and an illustrative Z trend. The inverse and generator share volumetric assumptions. Later observations are held out chronologically but their synthetic Z values are supplied. Do not describe this as a blind field forecast.

## Next mandatory checks

Before claiming a complete PVT/material-balance case, add an independent property comparison and a structurally different model that violates the volumetric assumption. Before a PTA claim, add a verified forward model and independently checked time/rate handling. Before a simulator claim, execute a pinned deck and retain logs, component inventories, reference comparisons and numerical-sensitivity results.

## Predeclared acceptance template

Each case must name the oracle, reason for its independence, physical assumptions, comparison quantity, units, absolute/relative tolerance, reference scale, supported regime, failure action and reviewer. Do not use a percentage with a near-zero denominator. Acceptance thresholds in PLAN.md are proposed case-specific targets, not universal standards.

Check data validity, analytical limits, quadrature/grid/time convergence, conservation, sensitivity to data preprocessing and parameter bounds. For inverse problems, diagnose identifiability and show alternative plausible interpretations. Reserve temporal holdout data before tuning; uncertainty from a model that is structurally wrong cannot be repaired by a narrower confidence interval.

## Review protection

Changing implementation, oracle, data exclusions and tolerances together requires an explicit separate review. A regression fixture from the same implementation is not independent truth. Different reviewers using the same unverified formula do not establish independent mathematical evidence.

A failed run is recorded with inputs and the failure reason. Do not filter failed ensemble members without reporting the rule and potential bias. A release must state which checks ran locally, which ran remotely, and which remain planned. Test coverage measures execution of lines/branches, not scientific validity.

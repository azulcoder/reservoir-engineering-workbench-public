# Case protocol template

Replace the prompts below with actual decisions before implementing the case. Keep a dated change log for material amendments.

## Engineering question and decision

What decision or uncertainty does the case address? What would a useful answer change? What would disprove the favored interpretation?

## Sources and model identity

Record exact sources, access level, dataset revision, license decision, file hashes, simulator/tool version, fluid formulation, units, initial/boundary conditions, well controls and reference results. Distinguish a published benchmark from a modified variant.

## Governing model and assumptions

Write the equations, symbols and units. Explain which mechanisms are included, excluded or represented by proxies. State what the observations must satisfy for the model to be appropriate.

## Experiments

Define the baseline, one-factor checks, structural alternatives, parameter ranges/dependencies, seeds, noise model, calibration interval and chronological holdout. Define data-exclusion rules before reviewing their effect on fit quality.

## Verification and acceptance

Name the independent oracle and why it is independent. Set justified tolerances, numerical refinement checks, conservation checks and failure handling. Specify whether the outcome may legitimately be inconclusive.

## Interpretation and artifacts

List required figures/tables, residual and uncertainty analysis, alternative explanations, decision sensitivity and information gaps. Save code, config, data manifest, run manifest, logs and decision memo. Record actual reviewers and open limitations.

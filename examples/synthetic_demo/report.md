# Synthetic volumetric-gas check

This run is a verification demonstration, not a field interpretation.

The first 9 pressure observations were used for OLS fitting; the last 4
were held out. Holdout pressures are conditional on supplied synthetic Z values.

| Quantity | Result |
|---|---:|
| Known synthetic GIIP | 1,000,000,000 standard m3 |
| Fitted GIIP | 1,001,492,564 standard m3 |
| Absolute relative GIIP error | 0.1493% |
| Holdout pressure RMSE | 16,284.6 Pa |
| Holdout RMSE / initial pressure | 0.0651% |
| Predefined demonstration gates | PASS |

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

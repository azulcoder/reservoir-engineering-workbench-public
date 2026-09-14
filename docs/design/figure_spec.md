# Figure specification, F01–F09

Nine figures for the case site. Every field named below was checked to exist in
`site/src/data/figures/` before it was specified. Nothing here asks for a quantity that was
not exported; where a figure needs a value that is only in the audited summary, that is
called out as a gap rather than assumed.

Design decisions these specifications depend on are in `decisions.md`; the colour and type
tokens are in `tokens.css`.

## Provenance of each figure's numbers

Two distinct classes, and the distinction is load-bearing because one class is a full
observation trace and the other is an aggregate.

| Figure | Source file | Class |
|---|---|---|
| F01 | `f01_f02_scenarios.json` | **full 49-point trace from the new export** (`scripts/export_presentation_data.py`) |
| F02 | `f01_f02_scenarios.json` | **full 49-point trace from the new export** |
| F03 | `f03_bias_sweep.json` | audited summary, pointer `/strength_sweep` |
| F04 | `f04_progressive.json` | audited summary, pointer `/progressive_fits` |
| F05 | `f05_holdout.json` | **full 49-point trace from the new export** |
| F06 | `f06_detection.json` | audited summary, pointers `/residuals_and_detectability/noise_sweep` and `/post_review_sensitivities/power_curve` |
| F07 | `f07_z_mismatch.json` | audited summary, pointer `/post_review_sensitivities/z_correlation_sensitivity` |
| F08 | `f08_refinement.json` | audited summary, pointer `/timestep_refinement` |
| F09 | `contract.json` | the export contract itself |

The reason F01, F02 and F05 come from the new export at all is stated in the exporter's own
docstring: the committed summary "stores only nine sampled rows of the residual table and no
full observation trace, because the case was written to be read, not plotted", and a site
that needs 49 points "cannot get them from the summary, and inventing them — by splining a
printed table, or by re-deriving them from a fitted line — would put numbers on a chart that
no run produced." The exporter imports the case module and calls the same `simulate`,
`observed` and `fit_pz_depletion` the audited run called, then reconciles 43 quantities
against the audited summary at a relative tolerance of 1e-12 before writing.

The five aggregate figures come from the audited summary, which means their numbers are the
ones in `cases/A4_misleading_fit_counterexample/results/summary.json` and in the case report
tables, unchanged.

## Global rules for all nine

- Units are printed on every axis. `contract.json` declares them: pressure and p/Z in psia
  absolute, cumulative gas in scf and Bscf where 1 Bscf = 1e9 scf, time in days and in years
  of 365.25 days, standard conditions 14.6959 psia and 60 degF with Z_sc = 1.
- Every figure carries the evidence class from `contract.json`, in short form, in its caveat
  line: synthetic, generator and estimator are separate modules, known inventory is
  evaluation-only information that no field measurement provides.
- Short description: one or two sentences, identifying the figure and naming where the long
  description is. Long description: the data table, structurally associated with the figure.
  This is the two-part alternative from the W3C complex-images tutorial (see `research.md`,
  S11).
- Gridlines and band fills are `aria-hidden` and are not counted as information-bearing
  (`decisions.md`, D13). Which marks that covers, and the removal test each one had to pass
  before it was called decorative, is in "Non-text contrast: what each mark does" below.
- Every string the renderer draws is measured before it is placed, and the build refuses to
  emit a figure whose text would fall outside the panel that contains it. See "Text metrics
  and the containment guard" below.
- Series colour is never the only channel. Dash pattern, marker shape and direct label are
  specified per figure.
- Tables default to collapsed above ten rows, expanded at ten rows or fewer.

## A gap the site stream must handle: the true gas in place

The truth value G = 1.0e11 scf (100.0 Bscf) is the reference line in F01, F03, F04 and F05.
It exists in the audited summary as `true_gas_in_place_scf`, and it is **not** a field in any
file under `site/src/data/figures/`. Two honest routes, in order of preference:

1. Add `true_gas_in_place_scf` to the export and to `contract.json`, and read it. This
   requires a change to `scripts/export_presentation_data.py`, which this pass does not own.
2. Derive it from exported fields, with the derivation shown on the page:
   `true = fit.gas_in_place_scf / (1 + relative_gas_in_place_error)`. On the base-case
   scenario this returns 1.000000e11 scf.

What is not acceptable is hard-coding 100 in a template. The number would then be in the
page and in no data file, which is the failure mode the exporter was written to prevent.

---

## F01 — The fit that looks right

**Source.** `f01_f02_scenarios.json` → `scenarios[]`, full 49-point traces. Default scenario
is the one with `is_base_case: true` (J = 2.0 bbl/day/psi).

**Audience question (T1).** What does a volumetric p/Z fit to an aquifer-supported reservoir
actually look like, and where does its x-intercept land relative to the truth?

**Encoding.** A scatter-and-line plot on a common position scale, which is the strongest
channel available for the quantitative comparison this figure exists to make.

- 49 observed points: `cumulative_gas_bscf[i]` against `p_over_z_psia[i]`, circle markers,
  `--c-series-observed`.
- The fitted line over the observed range: `cumulative_gas_bscf[i]` against
  `fitted_p_over_z_psia[i]`, long dash, `--c-series-model`.
- The fitted line **extrapolated** from `observed_extent_bscf` (54.9999… Bscf) to its
  x-intercept `fit.gas_in_place_bscf` (112.50 Bscf at the base case), same colour, same dash,
  at half the stroke weight, with an explicit "extrapolated, no data here" label. The
  extrapolation is computed from `fit.intercept_psia` and `fit.slope_psia_per_scf`, which are
  both exported, not by extending a drawn path.
- A vertical truth rule at 100.0 Bscf, `--c-series-truth`, fine dotted, diamond marker at the
  axis, label "true G = 100.0 Bscf (known only because this is synthetic)".
- The seven non-selected scenarios as thin `--c-series-context` traces behind, sparse dotted,
  1px, unlabelled, named only in the caption. This is the direct consequence of `decisions.md`
  D14: eight coloured lines would be above the range Wilke's chapter 19 calls workable.
- Scenario selection: a labelled listbox of the eight `label` values, 44px targets, default
  base case. The volumetric control (`is_volumetric_control: true`, J = 0) is a listed option
  and is the natural second thing to look at.

**Axes and units.** x: cumulative gas produced, Bscf, linear, 0 to about 120 so that the
intercept is on screen and the gap between data end and intercept is visible. y: p/Z, psia,
linear, starting at 0 so that the intercept's meaning is geometrically honest — a truncated
y-axis on a straight-line extrapolation figure would misstate exactly the quantity in
question.

**Non-colour channel.** Observed = solid, circle markers. Fitted = long dash `7 4`, no
markers. Extrapolation = the same dash at half stroke, plus its own text label. Truth = fine
dotted `2 3`, diamond. Context = sparse dotted `1 4`, 1px.

**Short description.** "Scatter plot of p/Z against cumulative gas produced for the base-case
water-drive scenario, with the volumetric straight-line fit and its extrapolation to the
x-axis. The fitted line crosses zero at 112.5 Bscf; the true gas in place is 100.0 Bscf. Full
values in the data table below the figure."

**Long description.** The data table, 49 rows, disclosed by a labelled control. The figure's
one-sentence finding line also functions as a summary for a reader who does not open it.

**Caveat text.** "Synthetic. The history comes from a Fetkovich-aquifer tank model; the fit
comes from a separate constant-pore-volume estimator with no influx term. R-squared =
`fit.r_squared` for the selected scenario, 0.999859 at the base case — this value and the
short description's numbers are bound to the selection and must re-render when it changes.
Everything to the right of `observed_extent_bscf` = 55.0 Bscf is extrapolation: no
observation exists there. The true gas in place is known only because the history was
generated, and no field measurement provides it."

**Data table.** One row per observation: index, time in years (`times_years`), cumulative gas
in Bscf (`cumulative_gas_bscf`), observed p/Z in psia (`p_over_z_psia`), fitted p/Z in psia
(`fitted_p_over_z_psia`), residual in psia (`residual_p_over_z_psia`), pressure in psia
(`pressure_psia`), deviation factor (`z_factor`). A summary block above the table carries
`fit.gas_in_place_bscf`, `fit.gas_in_place_stderr_scf`, `fit.r_squared`, `fit.n_points`,
`fit.depletion_fraction_observed`, `relative_gas_in_place_error`,
`relative_remaining_gas_error`, `bias_over_stderr`, `invaded_pore_volume_fraction`,
`terminal_pressure_psia`, and `max_solver_residual_p_over_z_psia`.

---

## F02 — The residuals that would have had to give it away

**Source.** `f01_f02_scenarios.json` → `scenarios[].residual_p_over_z_psia`, full 49-point
trace. Same scenario selection as F01, and the two figures share their selected scenario.

**Audience question (T2, T3).** Is there structure in the residuals of that excellent fit,
and how large is it compared with the pressure accuracy a real field could achieve?

**Encoding.** Residual plot: `cumulative_gas_bscf[i]` against `residual_p_over_z_psia[i]`,
points joined by a thin line because the sequence is the signal — the residuals sweep down,
back up and down again rather than scattering. A zero rule at y = 0 in
`--c-border-strong`. A horizontal reference band at ±10 psia and a second at ±50 psia,
`--c-band-neutral`, labelled "realistic accuracy of a volume-averaged reservoir pressure, 10
to 50 psi", with the label stating that this band is the report author's engineering
judgement, not a retrieved figure. The largest excursion (+24.63 psia at cumulative gas = 0)
is annotated directly.

**Axes and units.** x: cumulative gas produced, Bscf, linear, matching F01's scale for the
observed range so that the two figures can be read against each other. y: residual of the
volumetric straight-line fit, psia of p/Z, linear, symmetric about zero.

**Aspect.** Wider and shorter than the default — `--plot-aspect-wide` — because the residual
range is roughly ±25 psia against an x-range of 55 Bscf, and a 16:9 box would exaggerate the
vertical structure.

**Non-colour channel.** One series only, so it is solid with circle markers per
`decisions.md` section 9. The zero rule and the two bands are distinguished from the data by
being rules and fills rather than marked lines, and each carries a text label.

**Short description.** "Residuals of the volumetric straight-line fit for the base-case
scenario, in psia of p/Z, against cumulative gas produced. The residuals are not scattered:
they sweep down, up and down again, with an RMS of 7.38 psia and a largest excursion of 24.63
psia at zero cumulative production. Full values in the data table below the figure."

**Long description.** The residual column of the F01 table, disclosed separately so that a
reader arriving at F02 does not have to scroll back.

**Caveat text.** "Noise-free. These are the residuals of an exact fit to an exact history;
real data adds measurement error on top of this structure. The largest excursion, 24.63 psia,
is 0.57 percent of the initial p/Z. The 10 to 50 psi band drawn here is the case author's
engineering judgement about volume-averaged reservoir pressure accuracy, not a retrieved
figure, and it is the single load-bearing premise of the detectability conclusion: if the
real band is 1 to 5 psi, that conclusion reverses."

**Data table.** Index, years, cumulative gas in Bscf, observed p/Z, fitted p/Z, residual in
psia, and residual as a fraction of the initial p/Z. Plus the aggregate line: RMS residual
7.38 psia, largest absolute residual 24.63 psia, from the same scenario record.

---

## F03 — How the bias scales with aquifer strength

**Source.** `f03_bias_sweep.json` → `rows[]`, eight rows, from the audited summary at
`/strength_sweep`.

**Audience question (T1, T2).** Does the error grow with aquifer strength, and does the fit
statistic warn you about it?

**Encoding.** Two stacked panels sharing one x-axis, rather than one panel with two y-axes.
A dual axis would invite the reader to compare two incommensurable quantities by their
crossing point, and this figure exists to show R-squared staying high while the inventory
error grows.

- Upper panel: `relative_gas_in_place_error` against `invaded_pore_volume_fraction`, points
  joined, `--c-series-model` (this is the wrong model's error, so it takes the reserved
  colour). A second series in `--c-series-context`, square markers, sparse dotted:
  `relative_remaining_gas_error`, which is the quantity an engineer acts on and is larger at
  every point. A zero rule.
- Lower panel: `r_squared` against the same x, `--c-series-observed`, on a reversed or
  log-of-(1 − R²) scale so that 0.9952 and 1.0000 are distinguishable at all. A plain linear
  R² axis compresses every row into the top two percent of the panel and shows nothing. The
  axis must be labelled explicitly as 1 − R² on a log scale if that transform is used.
- The base case (J = 2.0) is annotated in both panels.

**Axes and units.** x: terminal water influx as a fraction of the initial hydrocarbon pore
volume, `invaded_pore_volume_fraction`, dimensionless, 0 to 0.34. y upper: relative error in
gas in place, dimensionless, shown as percent. y lower: R-squared, or 1 − R² on a log scale.

The productivity index `productivity_index_bbl_per_day_psi` is **not** the x-axis, because
the exported note says so: "Only the aquifer productivity index was varied. The invaded
pore-volume fraction on the horizontal axis is a model output of this generator, not an
independent field observation." J appears as a per-point label and in the table.

**Non-colour channel.** Gas-in-place error: long dash, no marker. Remaining-gas error: sparse
dotted, square markers. R-squared: solid, circle markers. All three directly labelled.

**Short description.** "Two stacked panels against aquifer strength. The upper panel shows
the relative error in fitted gas in place rising from zero to plus 74 percent as water
influx reaches 33 percent of the initial hydrocarbon pore volume. The lower panel shows
R-squared over the same range, falling only from 1.000000 to 0.9952. Full values in the data
table below the figure."

**Caveat text.** "Only the aquifer productivity index was varied; the horizontal axis is a
model output of this generator, not an independent field observation. The `bias / stderr`
column in the table is meaningless for the J = 0 row — its residuals are at the 1e-10 level,
so its standard error is a rounding artefact — and that row's value of −2.06 is reported as
exported and excluded from the 50-to-88 range quoted elsewhere."

**Data table.** All 17 exported columns per row, in the report's order:
`productivity_index_bbl_per_day_psi`, `aquifer_time_constant_days` (null for J = 0),
`timestep_over_time_constant`, `terminal_water_influx_bbl`, `invaded_pore_volume_fraction`,
`terminal_pressure_psia`, `r_squared`, `fitted_gas_in_place_scf`,
`relative_gas_in_place_error`, `fitted_stderr_scf`, `bias_over_stderr`,
`relative_remaining_gas_error`, `max_abs_residual_psia`, `rms_residual_psia`,
`depletion_fraction_observed`, `max_solver_residual_p_over_z_psia`, `generator_warnings`.

---

## F04 — Drift as history accumulates

**Source.** `f04_progressive.json` → `rows[]`, 40 rows: eight `productivity_index` values ×
five `history_fraction` values (0.2, 0.4, 0.6, 0.8, 1.0), from the audited summary at
`/progressive_fits`.

**Audience question (T2).** If you had refitted every few years, would the estimate have
been stable, and does stability mean correctness?

**Encoding.** Eight-line slope chart: `relative_gas_in_place_error` against
`history_fraction`, one line per J. The base case in `--c-series-model` at emphasis stroke
with a direct label at its right end; the other seven in `--c-series-context` with direct
labels only where they do not collide, and the full set in the table. A zero rule.

Two annotations, both stating things the data shows and the naive reading misses: the base
case moves 6.96 percentage points of true G between the first fifth of the history and all of
it, always upward; and the two strongest aquifers (J = 20, J = 60) **peak and fall back** —
J = 60 runs +91.84, +97.65, +91.64, +83.70, +74.01 — so a stabilising estimate is not
evidence that the estimate is right.

**Axes and units.** x: requested fraction of history, dimensionless, five ordinal positions
labelled 20, 40, 60, 80, 100 percent. y: relative error in fitted gas in place, percent,
linear, with zero included.

**Non-colour channel.** Emphasised line solid at `--stroke-emphasis` with circle markers;
context lines sparse dotted at 1px. Direct labels carry J values.

**Short description.** "Slope chart of the relative error in fitted gas in place against the
fraction of history used, one line per aquifer strength. The volumetric line is flat at zero;
every water-drive line drifts, and the two strongest peak and fall back. Full values in the
data table below the figure."

**Caveat text.** "Prefix fits share observations and are not independent samples. The axis is
the requested fraction of history; the realised point count is in the table. The volumetric
row is flat at machine precision, as it must be. The direction of drift is specific to a
reservoir whose aquifer support weakens over time; a constant-pressure aquifer would drift
differently."

That first sentence is the exported `note` field verbatim, and it should be rendered from the
file rather than retyped.

**Data table.** `productivity_index_bbl_per_day_psi`, `history_fraction`, `n_points`,
`years_observed`, `r_squared`, `relative_gas_in_place_error`, `relative_stderr`,
`depletion_fraction_observed` — all eight exported columns, 40 rows, sortable by J and by
fraction.

---

## F05 — The holdout the wrong model passes

**Source.** `f05_holdout.json`, full 49-point traces from the new export.

**Audience question (T2).** Does a genuine chronological holdout catch the error?

**Encoding.** Two panels, and the choice of which is primary matters more here than in any
other figure.

- **Primary panel, p/Z space, no leakage.** `cumulative_gas_bscf` against
  `observed_p_over_z_psia` (observed, solid, circles) and `fitted_p_over_z_psia` (long dash,
  `--c-series-model`). The calibration region, indices 0 to 29, is shaded `--c-band-neutral`
  and labelled "calibrated here, 30 points, 7.25 years"; the holdout region, indices 30 to 48,
  is unshaded and labelled "predicted, 19 points". A labelled vertical rule at
  `split_cumulative_gas_bscf` = 33.229 Bscf.
- **Secondary panel, opt-in, pressure space.** `observed_pressure_psia` against
  `reconstructed_pressure_psia_conditional`, which is null for the first 30 indices by
  construction. This panel must carry a prominent inline warning, not a footnote, because of
  what the reconstruction does.

**The leak, stated plainly.** The exported field name says it: `future_synthetic_z_used`. In
`cases/A4_misleading_fit_counterexample/run.py`, the pressure prediction for held-out index
`i` is `predicted_p_over_z * z_factors[i]` — the deviation factor of the **held-out** state,
which in a real forecast is not available. The headline holdout RMSE of 15.71 psia
(`holdout_rmse_pressure_psia`), and its 0.393 percent of initial pressure
(`holdout_rmse_fraction_of_initial_pressure` against
`initial_pressure_psia_denominator` = 4000.0), therefore describe a reconstruction that
borrowed future information. That is why the p/Z panel is primary and the pressure panel is
opt-in, and why `metrics.borrowed_demonstration_gate` (0.01) is labelled on the page as a
borrowed demonstration gate rather than as a forecast-accuracy result.

**Axes and units.** Primary: x cumulative gas in Bscf, y p/Z in psia. Secondary: x time in
years (`times_years`), y pressure in psia. Both y-axes include zero or state their truncation
in the axis label.

**Non-colour channel.** Observed solid with circles; predicted long dash without markers; the
calibration/holdout boundary is a labelled rule, and the two regions differ by fill as well
as by label.

**Short description.** "Chronological holdout for the base case. A volumetric fit calibrated
on the first 30 of 49 observations, then used to predict the remaining 19. The calibration
R-squared is 0.999641 and the calibration gas in place is 11.30 percent too high, yet the
held-out pressure RMSE is 15.7 psia, 0.393 percent of the initial pressure. Full values in the
data table below the figure."

**Caveat text.** "This is the most uncomfortable number in the case: a genuine chronological
holdout, with no tuning on the held-out points, is passed comfortably by a model whose gas in
place is 11.3 percent wrong. A holdout tests the forecast over the horizon it covers; it does
not test a quantity that lives outside the data. Separately, the pressure reconstruction
multiplies a predicted p/Z by the deviation factor of the held-out state — future synthetic
Z, exported as `future_synthetic_z_used` — so the 15.7 psia figure is a borrowed
demonstration, not an attainable forecast error."

**Data table.** 49 rows: index, `times_years`, `cumulative_gas_bscf`,
`observed_p_over_z_psia`, `fitted_p_over_z_psia`, `observed_pressure_psia`,
`reconstructed_pressure_psia_conditional` (blank for the calibration region, and the blanks
must render as an explicit "not applicable, calibration region" rather than as an empty cell),
and `future_synthetic_z_used` with the same treatment. A metrics block carries all six fields
of `metrics`, plus `calibration_points`, `holdout_points`, `split_index` and
`split_cumulative_gas_bscf`.

---

## F06 — Could anyone have told, under noise?

**Source.** `f06_detection.json`, two separate blocks from the audited summary:
`original` (pointer `/residuals_and_detectability/noise_sweep`, 400 replicates, seven sigma
levels) and `post_review_power_curve` (pointer `/post_review_sensitivities/power_curve`,
4000 replicates, ten sigma levels).

**Audience question (T2).** At what pressure measurement accuracy does the curvature detector
actually work, and does it false-positive on a reservoir with no aquifer?

**Encoding.** Detection rate against pressure noise sigma, log x-axis.

- `original.rows[].detection_rate_water_drive`, `--c-series-observed`, solid, circles:
  the positive control.
- `original.rows[].detection_rate_volumetric_null`, `--c-series-context`, sparse dotted,
  squares: the negative control, flat at 0.0675 at every level.
- `post_review_power_curve.rows[].detection_rate`, `--c-series-model` — drawn as a
  **separate, visually offset series with its own label and its own replicate annotation**,
  never joined to the original sweep. The exported note is explicit: "A separate post-review
  experiment with its own replicate count and seed. It is not spliced into the original
  sweep." Two options are acceptable: a second panel sharing the x-axis, or the same panel
  with a visible break in the line and both replicate counts labelled. Splicing them into one
  continuous curve is not acceptable at any level of annotation.
- A horizontal reference at 0.5 and a nominal-size reference at 0.05, both labelled.
- The half-power crossing may be annotated at 11.2 psi, derived on the page by linear
  interpolation between the two exported rows that bracket it (11.0 → 0.51625 and
  11.5 → 0.48075, giving 11.23), with the ±0.2 psi uncertainty quoted from the case report.
  The derivation must be shown; the number itself is not an exported field.

**Axes and units.** x: standard deviation of independent Gaussian error added to the reported
pressures, psi, log scale from 1 to 80. y: detection rate, dimensionless, 0 to 1, linear.

**Non-colour channel.** Three distinct dash patterns and three distinct marker shapes, plus
direct labels, plus the replicate count printed next to each series name — which is also the
frequency framing Wilke's uncertainty chapter argues for (`research.md`, S4).

**Short description.** "Detection rate of the pre-registered curvature test against added
pressure noise, on a log x-axis. The water-drive rate falls from 1.00 at 1 psi to 0.0725 at
80 psi; the volumetric null rate is flat at 0.0675. A separate post-review experiment with
4000 replicates and a different seed measures the power curve between 8 and 16 psi. Full
values in the data table below the figure."

**Caveat text.** "Rates are exact, not rounded: at 400 replicates every rate is a multiple of
0.0025. The null rate is identical at every noise level because the null p/Z series is exactly
linear, so the t statistic is scale-invariant — and because one seed was reset identically at
every level, so the seven levels are rescalings of one draw set rather than seven independent
experiments. The 0.0675 null rate is a high draw of that seed, not the detector's size:
pooled over 20000 replicates on a fresh seed it is 0.0473. The power curve is a different
experiment with its own seed and 4000 replicates and is not part of the pre-registered sweep.
Conditional on this detector, 49 quarterly observations, and independent Gaussian pressure
error; correlated or systematically biased error was not tested."

**Data table.** Two tables, never one. Table A: `pressure_sigma_psi`,
`detection_rate_water_drive`, `detection_rate_volumetric_null`, with the header carrying
`replicates` = 400 and `seed_note` = "One seed, reset identically at every sigma." Table B:
`pressure_sigma_psi`, `detection_rate`, with the header carrying `replicates` = 4000 and the
exported `note`.

---

## F07 — The detector is not a clean aquifer diagnostic

**Source.** `f07_z_mismatch.json` → `values{}` and `critical_t`, from the audited summary at
`/post_review_sensitivities/z_correlation_sensitivity`.

**Audience question (T2, T6).** If the analyst reads the deviation factor from a different
correlation than the one that generated the history — which is the realistic case, since
nature uses neither — what happens to the bias, and what happens to the detector?

**Encoding.** Two small panels, because the answer differs between the two questions and a
single panel would blur that.

- **Left, the bias is insensitive.** A dot plot on a common position scale, three values:
  `base_case_matched_relative_gas_in_place_error` 0.12503,
  `base_case_mismatched_relative_gas_in_place_error` 0.12219,
  `base_case_consistent_hall_yarborough_relative_gas_in_place_error` 0.12543. Axis in percent,
  with a range wide enough to show that all three sit inside 0.3 percentage points of one
  another, and labelled to say so.
- **Right, the detector is not.** A signed dot plot of curvature t statistics on one axis:
  `base_case_matched_curvature_t` +4.512, `base_case_mismatched_curvature_t` +3.545,
  `null_mismatched_curvature_t` −9.046. A shaded acceptance band between −`critical_t` and
  +`critical_t` (±2.0129), labelled "below this, the straight-line model is not rejected". The
  null-mismatched point is the one that matters: a strictly volumetric history with no aquifer
  at all produces a statistic twice the aquifer's own, with the opposite sign.

**Axes and units.** Left: relative error in gas in place, percent. Right: curvature t
statistic, dimensionless, signed, symmetric about zero so the sign reversal is visible as a
reversal and not as two separate magnitudes.

**Aspect.** `--plot-aspect-square` per panel; these are three-point dot plots and a wide box
would waste the reader's eye movement.

**Non-colour channel.** Each point carries its own direct text label, which is the only
channel a three-point dot plot really needs; marker shapes still differ (circle for matched,
diamond for mismatched, square for consistent-Hall-Yarborough) so that a greyscale print
remains readable.

**Short description.** "Two panels on deviation-factor correlation choice. On the left, three
gas-in-place errors that agree within 0.3 percentage points. On the right, three curvature t
statistics against a critical value of 2.01: the matched water-drive case at plus 4.51, the
mismatched water-drive case at plus 3.54, and a strictly volumetric history read with the
wrong correlation at minus 9.05. Full values in the data table below the figure."

**Caveat text.** The exported `values.note`, rendered from the file: matched means the analyst
uses the correlation the history was generated with; mismatched means the history is DAK and
the analyst reads Z from Hall-Yarborough, which is the realistic case since nature uses
neither. Then, from the top-level `note` and the report: signed statistics are kept signed,
and rejecting the straight-line model does not uniquely identify aquifer support. Then the
consequence: the detector's false-positive rate of about 0.05 is conditional on the analyst
using exactly the correlation that generated the history, a condition no field analysis can
meet. This block is post-review and was not pre-registered, and the page must say so.

**Data table.** All eleven fields of `values`, plus the top-level `critical_t` and `note`:
`max_relative_difference_dak_vs_hall_yarborough` (0.00310, the largest difference between the
two correlations inside this case's pressure window),
`base_case_matched_relative_gas_in_place_error`,
`base_case_mismatched_relative_gas_in_place_error`,
`base_case_consistent_hall_yarborough_relative_gas_in_place_error`,
`base_case_matched_curvature_t`, `base_case_mismatched_curvature_t`,
`null_mismatched_relative_gas_in_place_error` (−0.00265),
`null_mismatched_curvature_t`, `null_mismatched_max_abs_residual_psia` (3.986),
`critical_t`, `note`.

---

## F08 — Is the bias resolved in time?

**Source.** `f08_refinement.json` → `J_2.levels[]` and `J_60.levels[]`, four refinement levels
each, from the audited summary at `/timestep_refinement`.

**Audience question (T4, T6).** Is the reported bias a physical result or a timestep
artefact?

**Encoding.** The naive encoding — relative gas-in-place error against timestep — fails,
because the two series differ by a factor of six in magnitude (0.1250 and 0.7401) while the
quantity of interest is a change of order 1e-6. Plot the convergence instead.

- y: absolute deviation of each level's `relative_gas_in_place_error` from that series' finest
  level, log scale. The measured values are, for J = 2: 7.74e-7, 1.84e-7, 3.68e-8, 0 at
  dt = 30.44, 15.22, 7.61, 3.80 days; and for J = 60: 1.99e-5, 4.76e-6, 9.52e-7, 0.
- x: timestep in days, log scale, decreasing to the right so that "more refined" reads
  rightward.
- Two series: J = 2 in `--c-series-observed`, J = 60 in `--c-series-context`, each directly
  labelled with its `error_span_over_refinement` (7.74e-7 and 1.99e-5).
- A horizontal rule at the pre-registered threshold 1e-3, labelled "pre-registered
  acceptance threshold A4". Both series sit three to four decades below it, which is the
  figure's entire point.
- A second-order reference slope may be drawn, labelled as a reference, since successive
  ratios are about 4.2 and 5.0 per halving.

**Axes and units.** x: timestep, days, log. y: absolute change in the relative gas-in-place
error relative to the finest level, dimensionless, log.

**Non-colour channel.** Solid with circles, and sparse dotted with squares. Both labelled at
their left ends where the two series are furthest apart.

**Short description.** "Timestep refinement for two aquifer strengths, both axes logarithmic.
The recovered gas-in-place error changes by 7.7e-7 for the base case and 2.0e-5 for the
strongest aquifer across a refinement from 30.4 to 3.8 day steps, against a pre-registered
acceptance threshold of 1e-3. Full values in the data table below the figure."

**Caveat text.** The exported `note`, rendered from the file: "The finest computation is a
numerical comparator, not an exact solution." Plus: the deviations plotted are differences
against that finest level, so the finest level sits at zero by construction and is drawn at
the axis floor with an explicit label rather than silently dropped by the log scale.

**Data table.** Per series, per level: `timestep_days`, `steps`, `terminal_water_influx_bbl`,
`relative_gas_in_place_error` at full precision, the derived deviation from the finest level,
and `max_solver_residual_p_over_z_psia`. Plus `error_span_over_refinement` per series and the
exported `note`.

---

## F09 — How to check all of this

**Source.** `contract.json`. This is the one figure whose subject is the provenance chain
rather than a physical quantity, and it is a structured table with a small diagram, not a
chart.

**Audience question (T4, T5).** Are the numbers on this page the numbers in the repository,
and how would I check without taking anyone's word for it?

**Encoding.** A four-stage chain, left to right, drawn with rules and labelled boxes at
`--c-border-strong`, no gradient, no badge, no tick:

1. **Protocol** — `numerical_source.protocol_sha256`, pre-registered before the run.
2. **Case source** — `numerical_source.case_source_sha256`, `cases/A4_.../run.py`.
3. **Audited summary** — `numerical_source.baseline_summary_sha256`, at
   `numerical_source.baseline_summary_path`.
4. **Export** — `export.exporter_sha256` for `scripts/export_presentation_data.py`, annotated
   with `export.reconciliation_checks_passed` = 43 and
   `export.reconcile_relative_tolerance` = 1e-12.

Below the chain, a table of the seven `files[]` entries: `figure_data`, `path`, `sha256`, and
which figure on this page consumes it. Every hash is rendered as selectable monospace text
with a copy control, next to the command that reproduces it
(`shasum -a 256 <path>`). The `units` block and the `evidence_class` string are printed in
full, verbatim from the file.

**Non-colour channel.** No series, no colour encoding at all. The chain is conveyed by
position, rules and text.

**Short description.** "Provenance chain for every number on this page: the pre-registered
protocol, the case source, the audited summary and the export script, each with its SHA-256,
followed by a table of the seven figure data files with their hashes. Values and the commands
that reproduce them are in the table."

**Caveat text — and this is the figure where the caveats are the content.**

- The reconciliation tolerance is a **declared same-environment determinism target**: the
  exporter and the audited run execute the same code on the same interpreter, so exact
  agreement is expected, and the 1e-12 tolerance exists so that a cross-platform run reports a
  quantified disagreement rather than an unexplained failure. It was declared before the
  comparison was evaluated.
- Three NIST reference extracts are deliberately absent from this repository. As a direct
  consequence: 20 tests in `tests/test_gas_properties.py` skip with the message "NIST
  reference extract not present", `cases/A2_pvt_independent_check/run.py` exits 1 with a
  declared reference-table-absent status, and `scripts/fetch_nist_reference.py --verify-only`
  exits 1 reporting 3 files MISSING. The page states all three, in those words, and points at
  `scripts/fetch_nist_reference.py` as the route by which a reader obtains the extracts
  themselves.
- No hosted continuous-integration run, no journal peer review, no field validation and no
  deployment is claimed. The referee pass described in the case report was a review of the
  case, and the page uses that phrase and no stronger one.
- The known-influx oracle tests the solve, not the formulation: it is an algebraic
  rearrangement of the same governing equation the generator solves, so an equation
  mis-transcribed identically in both would still close to 3.6e-11. An independent
  from-scratch reimplementation exists but is not a committed artifact of this repository, and
  the page says exactly that rather than presenting it as evidence a reader can check.

**Data table.** The full contents of `contract.json`, rendered: `contract_version`, `case_id`,
all four fields of `numerical_source`, all four of `export`, all five of `units`,
`evidence_class`, and the seven `files[]` rows.

**One open dependency.** Any statement of test counts — the counts measured while preparing
this specification were 633 tests, 613 passed, 20 skipped — cannot be rendered from any file
currently in `site/src/data/`. Either the site stream renders them from a committed artifact
that actually exists, or the page prints the command and lets the reader produce the numbers
locally. Printing a count that no committed file contains would reproduce, on this page, the
exact failure the case is about.

---

## Non-text contrast: what each mark does

WCAG 2.2 SC 1.4.11 asks for 3:1 against adjacent colours for graphics that carry
information. `aria-hidden` removes a thing from the accessibility tree; it does not make a
visually necessary mark decorative and it does not exempt one from this ratio. So every
chart mark below 3:1 on the plot ground was classified by what it does to a reader, and the
ones that turned out to be doing work were given contrast rather than a hidden label.

The test is concrete: render the figure with the mark removed and see whether the same
conclusions are still available. The renders used for the four decisions below are
reproducible by stripping every `aria-hidden` group from the emitted SVG and rasterising the
result.

| mark | token | ratio on plot ground | verdict | what was done |
| --- | --- | --- | --- | --- |
| divider above the caveat and provenance lines | `--c-rule` #e1dfda | 1.33:1 | **necessary** | redrawn in `--c-border-strong` (3.51:1) |
| separator between table rows | `--c-rule` #e1dfda | 1.33:1 | **necessary** | redrawn in `--c-border-strong` (3.51:1) |
| legend swatch for a shaded band | `--c-band-neutral` #efeeea | 1.16:1 | **necessary** | boundary added in `--c-border-strong`; the fill inside it stays decorative and `aria-hidden` |
| axis gridlines | `--c-gridline` #e4e6e8 | 1.25:1 | decorative | unchanged, `aria-hidden` |
| band fills in the plot | `--c-band-neutral` #efeeea | 1.16:1 | decorative | unchanged, `aria-hidden` |

**Why the divider is necessary.** It is the boundary between the figure's evidence and the
caveat, provenance and standard-conditions lines that govern how that evidence may be read.
Below it sits 13px prose on the same ground with no other boundary of any kind. Removed, the
first caveat line reads as one more axis annotation, which is precisely the reading the
caveat exists to prevent.

**Why the table separator is necessary.** Cells wrap independently inside their column, so a
three-line sentence in the last column sits beside a one-line value in the first. The rule is
what says which value belongs to which row. Remove it and a reader cannot tell where one row
ends — the absence changes what can be concluded from the table, which is the definition of
information-bearing.

**Why the legend swatch is necessary but its fill is not.** A swatch at 1.16:1 is a blank gap
beside a label: the reader is told a colour exists and cannot see it. The swatch therefore
carries a 1px boundary in `--c-border-strong`, and it is the boundary, not the fill, that
makes the entry legible. The fill inside stays what it is in the plot.

**Why the gridlines and the band fills are decorative.** Both passed the removal test.

- F02 with every `aria-hidden` group removed still shows the ±10 and ±50 psia limits as
  dotted rules in `--c-border-strong`, each directly labelled "±10 psia" and "±50 psia", the
  zero rule, the axis ticks, the residual sweep and the labelled largest excursion. No
  statement F02 makes depends on the fills or on the gridlines.
- F05 with every `aria-hidden` group removed still shows the calibration split as a solid
  rule in `--c-border-strong`, both regions labelled in words ("calibrated here — 30 points,
  7.25 years" and "predicted — 19 points, no tuning here"), and the held-out observations
  still distinguished by square markers rather than by the shading.

In both figures the shaded region is redundant reinforcement of a boundary that is drawn at
3.51:1 and labelled in text. That redundancy is the whole of its job, and it is why it may
stay below the ratio.

`--c-rule` is consequently no longer used as a chart mark anywhere in the figures. It remains
a page hairline in the stylesheet, where it separates blocks of prose and is not a graphic
that conveys information.

---

## Text metrics and the containment guard

`linkedom` has no layout engine, so nothing in the render process can ask a browser how wide
a string is. The renderer used to guess with one average advance per character, and the guess
under-counted capitals, digits and wide punctuation — which is how F05's calibration note came
to be drawn 62 CSS pixels outside its own canvas, cropped in the exported SVG and in the PNG.

What replaces the guess:

- **An advance-width table**, in thousandths of an em, at weight 400 and weight 600, measured
  once in a browser as the *maximum* over every family `--font-sans` resolves to on the
  measuring machine: Arial, Helvetica Neue, Helvetica, `-apple-system`, `system-ui` and the
  generic `sans-serif`. Three stack members could not be measured because they are not
  installed there — Segoe UI, Roboto, Noto Sans — so a further 4 percent is carried on top.
  Segoe UI and Roboto are narrower than Arial across the ASCII range and Noto Sans is drawn to
  Arial's metrics. The estimate is deliberately an upper bound: it may break a line one word
  early, and it will not let a line run past its frame.
- **Wrapping against that measurement**, for titles, sub-headings, legend entries, table cells
  and in-plot annotations alike, each against its own weight and its own face.
- **In-plot annotations placed from the panel's own scales.** Plot's `lineWidth` is a budget in
  ems expressed independently of where the text sits, so a label two thirds of the way across a
  panel can satisfy its `lineWidth` and still leave the canvas. The budget used here is the
  distance from the anchor to the edge of the plot area, in pixels, so the block cannot
  overhang by construction.
- **A build-time containment guard.** Before a figure is written, every label is measured and
  judged against the box that contains it — a mark inside a panel against that panel,
  everything else against the canvas. A violation throws, names the figure and prints the
  sentence. Nothing is cropped and no qualification is dropped to make room; the fix is to
  wrap, to move the anchor, or to widen the panel. The guard found one overflow beyond the two
  already known: F07's category label "mismatched (DAK → H-Y)" ran 3 px past the left edge of
  its panel, and the panel's left margin was widened from 170 to 182 px.

### Panels are groups, not nested viewports

Each Plot panel used to be placed as a nested `<svg>` with `x` and `y`. It is now flattened
into a `<g transform="translate(...)">`. The drawing is identical — the renderer refuses to
flatten any panel whose `viewBox` is not its own box, so the scale is 1 by construction — but
two things improve.

1. There is one coordinate system in the figure instead of several.
2. `getBoundingClientRect()` on a *nested* `<svg>` does not agree between engines: Chromium and
   WebKit return the union of the rendered content, Firefox returns the viewport rectangle. A
   browser check that divides that box by the element's `viewBox` to recover a scale factor
   therefore gets a number that is not a scale factor at all on two engines out of three. That
   is what reported this project's 13px labels as 10.9px on Chromium and WebKit while Firefox,
   measuring the same drawing, reported 13px. A `<g>` has no viewport of its own, so
   `ownerSVGElement` resolves to the figure's root `<svg>`, whose box and `viewBox` are the
   same thing everywhere.

Flattening also gives up the clipping a nested viewport provided for free. That is why the
containment guard above enforces the same boundary explicitly, at build time, where a
violation names the figure instead of silently cutting a caveat in half.

### The 13px floor is met, and the check still has teeth

Measured through `getScreenCTM()`, which is the transform actually applied to the glyphs, the
smallest chart label renders at exactly 13.00 px on Chromium, Firefox and WebKit, at 1440 and
at 375 CSS pixels of viewport. The floor is not lowered anywhere and no figure has a compact
variant: there was nothing to trade away, because nothing was rendering below the floor.

Three controls, run on all three engines, establish that the check which measures this is not
vacuous after the flattening:

| control | reported smallest label |
| --- | --- |
| the site as shipped | 13.0 px |
| one label authored at 9px, injected into a figure | 9.0 px |
| the figure scaled by CSS to 600 of its 1000 px | 7.8 px |

The second and third are the two ways chart text can genuinely fall below the floor, and the
check sees both.

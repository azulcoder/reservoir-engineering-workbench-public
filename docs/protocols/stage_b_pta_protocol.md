# Stage B protocol — pressure-transient analysis on a synthetic gas well test

Status: pre-registered, not executed.

No Stage B study has been run. No Stage B result exists anywhere in this repository.
Every number in this document is either a target, a threshold, a closed-form sensitivity
derived here, or a value quoted from an evidence card; none of them is a measurement of a
Stage B run, because there has not been one. There is no Stage B case directory, no Stage
B run record, no Stage B summary and no Stage B figure. The public site must not display a
permeability, a skin, a derivative plot, a type-curve match or any other Stage B result,
and must not describe Stage B as under way, partially complete or nearly finished. What
exists is this protocol.

The repository is at release 0.2, whose delivered scope is gas properties and volumetric
material balance. Stage B is release 0.3 in `PLAN.md` section 16 and it has not started.

## 1. Standing and scope

This document fixes the design of the Stage B study before the study is implemented. It
is written under `PLAN.md` section 11 ("plan and pre-register"), expands `PLAN.md` section
6, and inherits the project gates of `PLAN.md` section 12. It follows the structure of
`docs/case_protocol_template.md` with the additions that pressure-transient work requires:
derivative conventions, interpretation windows, and an identifiability statement.

In scope: a controlled synthetic single-well gas pressure-transient study, analysed in
real-gas pseudopressure, with a declared rate history, on data the study generates itself.

Out of scope for Stage B, and not to be implied anywhere: field data, a licensed-software
comparison, a numerical (gridded) well-test model, multiphase or condensate behaviour,
horizontal or hydraulically fractured well geometry, dual-porosity models, and any
operational recommendation about how a real well should be drawn down or shut in.

Why synthetic. `PLAN.md` section 6 requires it, and the reason is identifiability rather
than convenience: the only way to state that an estimator recovered a parameter is to know
the parameter. An aggregate production dataset relabelled as a well test cannot support
that statement, and the acquisition gate of `PLAN.md` section 4 would reject it anyway.

## 2. Engineering question and decision

The question. Given a pressure and rate history from a single gas well, does the
interpretation chain in this workbench — pseudopressure transform, Bourdet derivative,
flow-regime identification, semilog analysis on a declared window — recover the
permeability-thickness product and the apparent skin of a known reservoir, and does it
refuse to report them when the data cannot support them?

The two halves are equally weighted. An estimator that returns a number on every dataset
is not an instrument; the refusal is part of the result.

The decision this affects. Whether a derivative plot produced by this library may be used
to size a well test, that is, to decide how long a test must run before its parameters are
worth extracting, and whether a reported kh and skin from a short test may be carried into
a deliverability or completion decision. A useful answer changes test duration and the
order of work; it does not change how a well is operated, and no operational recommendation
follows from it.

What would disprove the favoured interpretation. The favoured interpretation is that flow
regime identification governs identifiability: that kh is recoverable exactly when
infinite-acting radial flow is observed over a sufficient span, and that before that span
exists the data constrain only the storage-and-skin group, not kh and skin separately. It
is disproved if the truncated-record exhibit (B8 below) recovers kh within the recovery
tolerance anyway. Then the identifiability claim is wrong, must be withdrawn in full, and
the inconclusive exhibit must be redesigned or abandoned rather than re-tuned until it
fails.

## 3. What would make this study inconclusive

Declared before the work, because a study that can only succeed is not a test.

The study as a whole is INCONCLUSIVE, and must be reported as such rather than repaired
after the fact, if any of the following holds.

| ID | Condition | Consequence |
|---|---|---|
| I1 | The forward model and the estimator cannot be shown to be structurally independent, so a successful recovery cannot be distinguished from a shared error | No recovery claim. The study reports only the external-oracle checks. |
| I2 | The recovery exhibit's own numerical error (quadrature, solver tolerance, time discretisation) is within one order of magnitude of the recovery error being reported | Recovery is not resolved. Report a discretisation-limited bound only. |
| I3 | The inconclusive exhibit's estimator cannot be shown to work on the same data extended into radial flow | "Inconclusive" is indistinguishable from a broken fitter. No identifiability claim. |
| I4 | The derivative implementation fails the published Bourdet Table 1 regression at the tolerance declared in section 13 | Every diagnostic in the study is suspect. Nothing is published beyond the defect. |
| I5 | The gas-property chain feeding the pseudopressure integral cannot be checked against an independent reference in this repository | kh and skin are reported as conditional on the correlations, with the dependency quantified, and no absolute accuracy claim is made. See section 6. |

I5 is not hypothetical. The independent fluid-property reference extracts are absent from
this repository by deliberate policy, and 20 tests in `tests/test_gas_properties.py` skip
with the message "NIST reference extract not present". `cases/A2_pvt_independent_check`
exits non-zero for the same reason, and `scripts/fetch_nist_reference.py --verify-only`
reports the files missing. Stage B therefore begins in condition I5 and must say so in its
report rather than discover it afterwards.

Individual exhibits may also be inconclusive on their own terms. Exhibit B8 is designed to
be inconclusive; that is a result, not a failure.

## 4. What the library provides today, and what Stage B must add

Read this before implementing anything, because the gap is larger than it looks.

Provided now, verified, with its conventions already fixed:

| Capability | Entry point | Convention already fixed |
|---|---|---|
| Bourdet L-smoothed log-time derivative | `diagnostics.bourdet_derivative` | Eq. 8 weighting with each slope taking the opposite spacing; `smoothing_l` in natural-log cycles; `>=` tie-break; endpoints dropped, never one-sided; negative values preserved; `NotIdentifiableError` when no point has a full window |
| Unsmoothed three-point derivative | `diagnostics.log_time_derivative` | The `smoothing_l = 0` case, delegating to `gas.log_time_derivative`, identical bit for bit |
| Real-gas pseudopressure | `pseudopressure.pseudopressure` | `reference_psia` required at every call; `mu_z` a callable, not a table; composite Simpson; default 256 panels |
| Demonstrated quadrature order | `pseudopressure.convergence_study`, `numerics.richardson_order` | Observed order from successive refinement, with the clean order-4 window recorded as `SIMPSON_ORDER_WINDOW = (64, 1024)` |
| Deviation factor and viscosity | `gas_properties.z_factor` (DAK, Hall-Yarborough, DPR), `gas_viscosity_lee_gonzalez_eakin`, `gas_compressibility_per_psi` | Newton with analytic derivative; published validity windows exposed as module constants; analytic `dZ/dp` in production, finite difference only as a test oracle |
| Standard conditions | `units.SPE_STANDARD` | One standard atmosphere, 60 degF, `Z_sc = 1` |
| Linear estimators and intervals | `regression.ols_line`, `deming_line`, `york_line`, `x_intercept_fieller`, `moving_block_bootstrap`, `student_t_quantile` | Frequentist; Fieller classification of a ratio interval as bounded, exclusive or whole-line |
| Immutable run records | `provenance.RunRecord` | Write-once directories; source revision, dirty state, input and output hashes, environment, seed, exit status |

Not provided, and therefore part of Stage B's build rather than its analysis:

- No analytical forward well-test solution of any kind. There is no exponential-integral
  function, no line-source solution, no wellbore-storage-and-skin solution, no Laplace
  inversion, no bounded-reservoir solution, and no type curve.
- No time-function construction. There is no Agarwal equivalent time, no Horner or
  superposition time function, and no multirate rate-history handling. The derivative
  functions differentiate against `ln` of whatever time array they are given; the module
  docstring states plainly that they cannot detect the substitution of raw shut-in time
  for a superposition function.
- No pseudotime. The pseudopressure module's docstring lists it as deliberately absent and
  records why: pseudopressure is an exact change of variable, pseudotime is not.
- No nonlinear estimator. `regression` fits straight lines. There is no least-squares
  model fit, no parameter covariance from a nonlinear fit, and no optimiser beyond
  `numerics.safeguarded_newton` for scalar root-finding.
- No regime classifier. `diagnostics` states in its docstring why it ships none: the
  beta-derivative does not separate spherical from radial flow, and a classifier that
  encodes the commonly quoted -1/2 for spherical beta would be wrong.
- No gas field-unit constants. Neither 1422.52 nor 711.26 nor 1637.74 appears anywhere in
  `src/reservoir_lab` as a number; they appear only in two docstrings, as warnings about
  the rate-unit trap. Stage B introduces them, and section 15 fixes how.
- No end-effect remedy. Bourdet's fixed "pseudo right" derivative is not implemented and
  is not planned; points within L of either end are dropped.
- No full published-table fixture. `tests/test_diagnostics.py` already anchors the
  estimator on individual rows of Bourdet's Table 1, including the row where the `L` rule
  skips a point and the row that separates the correct weighting from the secant, but the
  complete derivative columns are not committed. Criterion B-A1 below is a column-wide
  regression and it cannot run until that fixture exists. Adding it is Stage B work.

Nothing in this list may be described as available, partially available, or straightforward
before it is written and tested.

## 5. Governing model, transforms and constants

Field units throughout, per `docs/api_contract.md` C1. Pressure absolute in psia,
temperature absolute in degR, time in hours for transient work, gas rate in Mscf/D.

The transform, Al-Hussainy, Ramey and Crawford (1966), Eq. 14:

    m(p) - m(p_ref) = 2 * integral from p_ref to p of  p' / (mu(p') Z(p'))  dp'      [psia^2/cp]

Differences are formed by integrating `[p_wf, p_i]` directly, never by subtracting two
datum-referenced values. That is the same mathematics, is better conditioned against the
1e8 to 1e9 magnitude of `m`, and makes the datum irrelevant by construction. The datum is
recorded anyway, on the object that carries the curve, and two curves on different datums
are never subtracted.

Infinite-acting radial flow in pseudopressure, with `q_sc` in Mscf/D:

    m(p_i) - m(p_wf) = (1422.52 * q_sc * T / (k h)) * [ 1.1513 * log10( k t / (1688 phi (mu c_t)_i r_w^2) ) + s' ]
    semilog slope, per log10 cycle:   m_slope = 1637.74 * q_sc * T / (k h)
    derivative plateau, per ln cycle: D_plateau = m_slope / ln(10) = 711.26 * q_sc * T / (k h)
    apparent skin:                    s' = s + D_nd * q_sc

so that `k h = 711.26 * q_sc * T / D_plateau` and a relative error in the plateau maps
one-for-one into a relative error in `kh`. The three constants are arithmetically tied:
1422.52 / 2 = 711.26 exactly, and 1422.52 * 1.1513 = 1637.75 against the published 1637.74.
Stage B defines 1422.52 once, as a single module constant carrying its rate unit in its
name, and derives the other two from it rather than transcribing them.

What the transform does not do, taken from the pseudopressure module's own docstring and
its evidence card: it does not provide rate superposition, pseudotime, wellbore storage,
non-Darcy skin separation, multiphase behaviour, or pressure-dependent permeability. The
spatial operator is linearised exactly; the diffusivity coefficient `phi mu(p) c_g(p) / k`
still depends on the solution. Stage B has no pseudotime, so section 6 bounds the drawdown
instead.

## 6. Data-quality requirements and disqualification

Stage B generates its own data, so these rules serve two purposes: they constrain the
synthetic design, and they are the gate any real dataset would have to pass before it could
be substituted later. Both uses are pre-registered here so that a later dataset cannot be
admitted by relaxing a rule after seeing what it does to the fit.

Resolution and noise. For a real gauge, the resolution and the quoted accuracy are read
from the gauge's own datasheet and recorded in the run record; no gauge specification is
asserted in this protocol, because none has been read. For the synthetic study the
equivalent quantity is the declared noise model in the config, and the requirement is
expressed as a ratio rather than an absolute figure, derived as follows.

On a uniform natural-log grid with window spacing `h` on both sides, the Bourdet estimator
reduces to `(p_k - p_j) / (2h)`: the centre point cancels. With independent noise of
standard deviation `sigma` on the response, the derivative at one point therefore has
standard deviation

    sd(derivative) = sigma / (h * sqrt(2))

This was confirmed against a 200,000-draw Monte Carlo simulation while writing this
protocol (3.530 measured against 3.536 predicted at `sigma = 1`, `h = 0.2`); it is a
property of the estimator, not of any Stage B run. Requiring a single derivative point on
the plateau to be within 10 percent of the plateau height gives

    sigma <= 0.10 * sqrt(2) * h * D_plateau  =  0.0283 * D_plateau   at h = 0.2

so the declared response noise must not exceed about 2.8 percent of the derivative plateau
height for the recovery exhibit. Averaging over a plateau of `N` points improves this, but
by less than `sqrt(N)`, because neighbouring Bourdet points share raw samples; the study
must not claim the `sqrt(N)` improvement, and section 12 replaces it with a block
bootstrap.

Rate-history synchronisation. The rate history and the pressure history must share one
clock, one time origin and one time unit, and every rate change must be timestamped at the
resolution of the pressure record or better. An undetected rate change appears as a
derivative feature and is routinely read as a boundary; this is listed as a failure mode in
`docs/evidence/derivative.md` and it is exactly what exhibit B7 exists to demonstrate. For
the synthetic study the rate history is exact by construction and B7 perturbs it
deliberately.

Sampling density. At least 10 samples per log10 cycle of the time function over the whole
analysis interval. That is the density at which the evidence card's discretisation-bias
table is stated, and it is what keeps the unsmoothed bias on a unit slope at 0.89 percent.

Span. An interpretation window must span at least 1.0 log10 cycle, that is 2.303 natural-log
cycles, and must leave at least `L` of data beyond each of its ends so that the derivative
exists there at all. `bourdet_derivative` raises `NotIdentifiableError` rather than
returning a short series when the window and the record are incompatible; the study treats
that exception as a finding, not as an error to be worked around by shrinking `L`.

Drawdown size, gas-specific. Because there is no pseudotime, the residual time-side
nonlinearity is uncorrected, and the design must keep it small instead. The requirement is
on the viscosity-compressibility product: `(mu c_t)` evaluated at the minimum flowing
pressure must lie within a factor of 1.25 of its initial value. The cost of that window is
bounded in closed form. An error of factor `f` in the effective `mu c_t` shifts the semilog
intercept by `log10(f)` cycles and therefore the apparent skin by `1.1513 * |log10(f)|`,
which is 0.112 at `f = 1.25`, and it does not bias the slope, so it does not bias `kh` at
all. The ratio is reported with the result in every exhibit.

Disqualifying conditions. Any one of these disqualifies a dataset outright, and none may be
waived after the fit has been seen:

- Pressure recorded as gauge, or with an unstated datum, or with an unstated depth
  correction. Absolute pressure is required by the transform and by every field-unit
  constant in section 5.
- Temperature stated in degF where degR is required. The error is dimensionally invisible
  and produces roughly a factor 1.8 in `kh`.
- No rate history, or a rate history reconstructed from monthly allocation, or a rate
  history whose timestamps cannot be aligned with the pressure record.
- Fewer than 10 samples per log10 cycle in the candidate analysis interval.
- Duplicate or non-increasing timestamps that have not been resolved upstream.
  `bourdet_derivative` refuses a non-increasing time array and must not be given an epsilon
  guard to get past it.
- A buildup whose first sample is the shut-in point at `dt = 0`. It has no logarithm and
  must be removed, not clamped.
- Any evidence of two-phase flow in the wellbore or in the reservoir over the analysis
  interval, at which point the single-phase pseudopressure is ill-defined rather than
  merely inaccurate.
- A single-rate record used to support a claim about the Darcy skin `s` rather than the
  apparent skin `s'`.

## 7. Required figures and diagnostics

Every exhibit produces all of the following, and a report that omits one states why:

1. Rate history, as a step plot against real time, on the same time axis as the pressure
   history. A PTA figure without its rate history is not interpretable.
2. Pressure history against real time, absolute pressure, with the analysed flow period
   marked.
3. Pseudopressure difference `Delta_m` against the time function, log-log, together with
   the Bourdet derivative `Delta_m'` on the same axes. Both curves, same axes, always: the
   vertical relationship between them carries the wellbore-storage and pseudo-steady-state
   discrimination and nothing else does.
4. Semilog plot of `Delta_m` against `log10` of the time function, with the fitted straight
   line and the interpretation window shaded.
5. Derivative smoothing sensitivity: the same derivative at `L = 0`, 0.1 and 0.3 natural-log
   cycles, overlaid. The window actually used is declared in advance (section 9) and the
   other two are shown to demonstrate that the conclusion does not depend on it.
6. Residuals of the fit against the time function, not against the fitted value, so that
   structure in time is visible.
7. The log-log slope of the derivative, `d ln(Delta_m') / d ln t`, over the identified
   regimes. This is the diagnostic that separates spherical from radial flow; the
   beta-derivative does not, and must not be plotted as if it did. See section 15.
8. For the inconclusive exhibit, the identifiable group and its interval, plotted in place
   of the parameters that are not identifiable.

Type-curve overlays, if used, apply the identical `L` to the model curve and to the data.
That is the only way the smoothing distortion cancels, and it is Bourdet's own instruction.

## 8. Derivative conventions

These are fixed here and are not negotiable during interpretation. They match what
`diagnostics.py` already implements, so the protocol records them rather than introducing
them.

Weighting. Bourdet, Ayoub and Pirard (1989), Eq. 8, with the left slope multiplied by the
right spacing and the right slope by the left spacing:

    dp/dX|i = ( (dp1/dX1) * dX2 + (dp2/dX2) * dX1 ) / ( dX1 + dX2 )

The nearer point receives the larger weight. Transposing the two weights is the standard
transcription error. It is not a small error and it is not detectable by the usual test:
the transposed form is algebraically identical to the plain two-point secant through the
outer points, for any spacing, and the secant is exact on data affine in `ln t`, so the
radial-plateau oracle returns exactly 0.5 for both. The discriminating checks are the
published Table 1 regression and an explicit assertion that the estimator differs from the
secant on a deliberately lopsided grid.

Smoothing window. `L` is a distance on the `X = ln(time function)` axis, in natural-log
cycles. Bourdet's quoted range is 0 to 0.5 with 0.1 as the working value. Commercial
packages commonly quote the same parameter in decades; the two differ by `ln(10) = 2.303`
and reading 0.1 as decades reproduces the paper's own column 18.5 percent wrong. `L` is
never applied to raw elapsed time. A caller holding decades converts once, at the call
site, with `smoothing_l = math.log(10.0) * l_decades`.

Point selection. The left point is the first found walking left with `X_i - X_j >= L`; the
right point is the first found walking right with `X_k - X_i >= L`. The implementation uses
`>=` where the paper prints `>`; the two differ only on an exact tie, the published table
contains no tie, and the tie-break is therefore untested against the source. That is
recorded as a known gap, not presented as verified.

Endpoint omission. Points within `L` of either end of the record have no valid window and
are dropped. They are not extrapolated with Bourdet's fixed pseudo-right remedy and they are
not filled with a one-sided slope. A one-sided slope produces a spurious kink that mimics a
boundary; dropping is the only option that cannot be mistaken for data. The returned
abscissa tells the caller which points survived, and the study plots that abscissa rather
than assuming it equals `time[1:-1]`.

Negative values. Preserved, never clipped and never absolute-valued. A falling derivative is
physical information, and the behaviour a diagnostic plot exists to reveal is exactly the
behaviour clipping destroys.

Discretisation bias. On a power-law response `A t^n` sampled on a uniform log grid of
spacing `h`, the estimator is high by the closed-form factor `sinh(n h) / (n h)`: 0.886
percent for unit slope at 10 points per decade, 0.221 percent for half slope, 0.055 percent
for quarter slope, and exactly zero for a radial plateau at any `h` and any `L`, because the
response is then affine in `ln t`. Every power-law assertion in the study's tests is made
against the `sinh`-corrected value, never against `n` itself.

Buildup. If a buildup is analysed, the derivative is taken with respect to the superposition
or Agarwal time function, in natural logarithm, and plotted against elapsed shut-in time.
Differentiating against `ln(dt)` instead understates the derivative by `t_p / (t_p + dt)`:
the plateau reads half its true height at `dt = t_p`, `kh` is then wrong by a factor of two,
and the curve droops in a way that is routinely read as aquifer support. The library cannot
detect this substitution; the study's own tests must.

Smoothing sensitivity is reported, not optimised. The declared `L` is fixed in section 9
before any fit. If a different `L` changes the interpretation, that is a finding about the
data and it is reported as one; it is not grounds for choosing the `L` that makes the
preferred model look better.

## 9. Interpretation windows

The window is the interval of the time function over which a straight line is fitted. It is
the single largest source of analyst freedom in pressure-transient work, so it is removed
from the analyst here.

The rule, fixed before any fit:

1. Compute the derivative at `L = 0.1` natural-log cycles. That is the declared working
   value for every exhibit unless the exhibit's own entry in section 11 says otherwise.
2. Identify the candidate radial-flow interval as the longest run of consecutive derivative
   points over which the log-log slope `d ln(Delta_m') / d ln t` stays within `+/- 0.05` of
   zero. The tolerance is a declared number, not a judgement.
3. Trim the interval's early end to `t_D / r_D^2 >= 300`. The approach to the plateau is
   known in closed form from the line-source solution, whose log-derivative is exactly
   `0.5 exp(-r_D^2 / (4 t_D))`; at `t_D = 300` the plateau is still 0.083 percent low, at
   `t_D = 100` it is 0.25 percent low, and at `t_D = 1000` it is 0.025 percent low.
   Trimming at 300 caps the approach bias at 0.083 percent of `kh`.
4. Trim the late end at the first derivative point whose log-log slope leaves the `+/- 0.05`
   band, with no extension past it.
5. Require the surviving interval to span at least 1.0 log10 cycle. If it does not, the
   window does not exist and no semilog fit is reported for that exhibit. That outcome is a
   result and is what exhibit B8 is built to produce.

Step 3 uses `k` to compute `t_D`, which is what is being estimated, so the rule iterates:
take `k` from step 2's plateau, apply step 3, refit, and stop when the window indices stop
changing. The iteration is bounded at five passes and the number of passes taken is
reported. If it does not settle, the window is not well defined and the exhibit reports no
parameters.

Nothing about the window is chosen after seeing the recovered parameters. In particular, the
window is not widened to improve a confidence interval and not narrowed to improve a
residual pattern. If the rule produces a window the analyst believes is wrong, the rule is
amended in the change log with a date and a reason, and every affected exhibit is rerun.

## 10. Parameter identifiability

The study estimates only what its design can separate, and says so in advance.

Separable in the recovery exhibit, given a record that reaches radial flow:

| Quantity | From what | Conditional on |
|---|---|---|
| `k h` | The derivative plateau, `k h = 711.26 q_sc T / D_plateau` | `q_sc`, `T`; nothing else |
| `s'` (apparent skin) | The semilog line's offset at unit time | `k h`, and the supplied `phi`, `(mu c_t)_i`, `r_w`, `h` |
| Wellbore storage `C` | The early unit slope, where `Delta_m'` and `Delta_m` coincide | The storage being constant over that interval |

Not separable, in any design this protocol admits:

- `k` and `h` individually. The plateau constrains the product. `h` is supplied from the
  declared model and `k` is reported as a derived quantity carrying that assumption.
- `s` and the non-Darcy coefficient `D_nd`. A single-rate test constrains only
  `s' = s + D_nd q_sc`. Every skin in this study is reported as apparent skin, with the
  symbol `s'`, and never as "skin" without qualification. Separating them needs at least two
  stabilised rates, which is outside Stage B's scope.
- `phi`, `c_t` and `r_w` from the transient alone. They enter only inside the logarithm,
  multiplied together with `k`, so the record cannot distinguish them from each other or
  from a skin. Their errors transfer to skin at a known rate: a relative error `e` in the
  group `phi (mu c_t)_i r_w^2` shifts `s'` by `1.1513 * |log10(1 + e)|`, which is 0.048 at
  `e = 0.10` and 0.112 at `e = 0.25`. They are declared, not fitted, and the transfer is
  quoted with the result.
- `C` and `s` before radial flow appears. Storage-and-skin behaviour is governed by the
  single group `C_D exp(2s)`, so a record that ends in the storage-to-radial transition
  constrains that group and not its factors. This is the basis of exhibit B8 and the reason
  its verdict is inconclusive by construction rather than by accident.
- A boundary from a rate-history error. Both produce a late-time derivative feature and
  neither is distinguishable from the other without the rate history. Exhibit B7 puts the two
  side by side.
- A single sealing fault from a halved `kh`, if the first plateau is never observed. The
  fault doubles the plateau; a record that starts after the doubling is indistinguishable from
  a homogeneous reservoir of half the `kh`.

The study states, for each exhibit, which of these it is relying on being supplied and which
it claims to have estimated. A quantity that is supplied is never reported in a results table
as though it were recovered.

## 11. Experiments

Built in this order. Each step is verified before the next begins; `PLAN.md` section 6 is
explicit that the first inverse problem must not contain every mechanism.

| ID | Experiment | Purpose |
|---|---|---|
| B1 | Estimator regression against the published Bourdet Table 1 columns, `L = 0` and `L = 0.1` | Validates weighting, `L` units, selection rule and sign convention together, against data produced by someone else's implementation in 1989 |
| B2 | Line-source oracle: derivative of `0.5 E1(r_D^2 / (4 t_D))` against its exact closed form `0.5 exp(-r_D^2 / (4 t_D))` | Exercises the curved transition, which no plateau or power-law test touches |
| B3 | Constant-rate drawdown in pseudopressure, homogeneous infinite-acting, no storage, no skin | The simplest recovery: plateau to `kh` with everything else absent |
| B4 | The same with a non-zero skin, then with wellbore storage added | Introduces the semilog offset, then the early-time regime, one at a time |
| B5 | Pseudopressure fidelity: constant `mu Z` closed form, then the convergence-order study with the interpolated-table negative control | Establishes that the transform feeding every exhibit is correct and that its order is demonstrated, not asserted |
| B6 | Buildup after a single drawdown, differentiated against the superposition function and plotted against elapsed time | Demonstrates the `t_p / (t_p + dt)` factor by showing both curves |
| B7 | Controlled contrast: a true no-flow boundary against a record with one undeclared rate change, both producing a late-time derivative rise | Shows that the derivative feature alone does not identify the cause |
| B8 | The inconclusive exhibit (section 11.2) | Required by `PLAN.md` section 6 |
| B9 | The recovery exhibit (section 11.1) | Required by `PLAN.md` section 6 |

Noise. B1 through B7 run noise-free, so that any error reported there is method error alone.
B8 and B9 carry the declared noise model. Every seed is declared in the config and reset
identically across compared cases, so that two exhibits differing in one factor are not also
differing in their noise realisation.

### 11.1 Exhibit B9, successful parameter recovery

A single constant-rate gas drawdown, homogeneous and infinite-acting, with wellbore storage
and a non-zero skin, run long enough that radial flow is observed over at least 1.5 log10
cycles after the window rule of section 9 has trimmed it. The drawdown is bounded by the
`mu c_t` rule of section 6. Noise at the declared level, which is at or below 2.8 percent of
the plateau height by the derivation in section 6.

Reported: `kh` and its interval, `s'` and its interval, `C` and its interval, the window
actually used and the number of iterations the window rule took, the `(mu c_t)` ratio, the
smoothing sensitivity at three values of `L`, and the coverage check of section 12.

The claim this exhibit is allowed to make, if it passes: that on a synthetic problem inside
the estimator's supported class, with the relevant regime observed and the parameters
identifiable, the chain recovers `kh` and `s'` within the section 13 tolerances. Not that
the library is validated, not that it works on field data, and not that the tolerances are
industry standards. `PLAN.md` section 6 states plainly that they are project targets.

### 11.2 Exhibit B8, the deliberately inconclusive case

The same reservoir and the same well as B9, and the same noise realisation, with the record
truncated so that it ends inside the storage-to-radial transition, before the plateau exists.
The window rule of section 9 then finds no interval spanning 1.0 log10 cycle and no semilog
fit is reported.

What is reported instead: the identifiable group `C_D exp(2s)` with its interval, the
statement that `kh` and `s'` are not separately identifiable from this record, the derivative
plot showing why, and the duration the test would have needed to reach the window rule's
threshold. No `kh` point estimate and no skin point estimate appear anywhere in the exhibit,
including in an appendix, including with a caveat attached.

The positive control, and it is mandatory. The identical estimator, on the identical noise
realisation, is run on the untruncated record of B9 and must recover `kh` within the recovery
tolerance. Without that control, "inconclusive" is indistinguishable from a broken fitter,
and the exhibit would establish nothing. This is condition I3 of section 3.

The falsifier. If the truncated record does yield `kh` within the recovery tolerance, the
identifiability claim of section 10 is wrong. The claim is then withdrawn in full and the
exhibit is redesigned from its premise. It is not made to fail by adding noise until it does.

## 12. Uncertainty treatment and probability convention

The convention is frequentist and it is stated wherever a number with an interval appears.
An interval is a confidence interval with a stated nominal coverage of 95 percent, meaning
that the procedure covers the fixed unknown parameter in 95 percent of repetitions of the
experiment. It is not a credible interval and carries no statement about the probability that
a parameter lies in it. No Bayesian posterior is computed and no prior is elicited.

There is no probability attached to a model being correct. Where alternative models are
compared, the study reports which measurement would discriminate between them, not a
posterior odds ratio. `PLAN.md` section 6 requires exactly that framing.

Mechanics, all from the existing library:

- Straight-line parameters and their standard errors from `regression.ols_line`, with
  Student-t quantiles from `regression.student_t_quantile` at the residual degrees of freedom.
  Degrees of freedom are counted from the number of derivative points actually in the window,
  not from the number of raw samples.
- Neighbouring Bourdet derivative points share raw pressure samples, so the plateau residuals
  are serially correlated and an ordinary standard error understates the uncertainty. The
  plateau interval is therefore taken from `regression.moving_block_bootstrap`, with the block
  length chosen by `regression.suggested_block_length` and reported. The ordinary interval is
  reported alongside it, and the ratio of the two is reported, because the size of that ratio
  is the point.
- Any interval on a ratio of two fitted quantities uses `regression.x_intercept_fieller` and
  its classification, not the delta method. An interval that Fieller classifies as exclusive
  or whole-line is reported with that classification and is not silently rendered as a pair of
  finite bounds.
- Systematic contributions are separated from the statistical interval and never merged into
  it. The known systematic terms are listed with their sizes: the plateau approach bias capped
  at 0.083 percent by the window rule, the smoothing bias which is exactly zero on a radial
  plateau, the `mu c_t` drift bounded at 0.112 in skin by section 6, and the transfer from the
  declared `phi (mu c_t)_i r_w^2` group at `1.1513 |log10(1 + e)|` per relative error `e`.

Coverage is checked, not assumed. The recovery exhibit is repeated over a declared set of at
least 200 seeds, and the fraction of repetitions whose 95 percent interval contains the known
`kh` is reported. That fraction is the positive control on the uncertainty machinery: an
interval procedure whose coverage has never been measured is a decoration. The acceptance band
for it is derived in section 13.

## 13. Acceptance criteria

Every threshold below is fixed now, before any Stage B code exists. Where a threshold is
inherited from `PLAN.md` it is marked as such; where it is derived, the derivation is given.
A threshold is not changed after a result is seen. If one proves unsuitable, the change is
recorded in the change log with a date and a reason and the affected exhibits are rerun, per
`PLAN.md` section 12.

| ID | Criterion | Threshold | If it fails |
|---|---|---|---|
| B-A1 | Bourdet Table 1 regression, `L = 0` and `L = 0.1`, against the published derivative columns | relative tolerance 3e-3 | Diagnostics are wrong. Nothing published beyond the defect. Condition I4. |
| B-A2 | The estimator differs from the two-point secant on a lopsided grid | difference above 1 percent on the declared triplet | The weighting may be transposed. Same consequence as B-A1. |
| B-A3 | `L` unit discriminator: the same column computed with `L` read as decades | must differ materially from the published column | The `L` convention is unpinned. Same consequence as B-A1. |
| B-A4 | Radial-plateau exactness on a response affine in `ln t`, any grid, any `L` | 0.5 to within 1e-12 | Formula or point selection is wrong. |
| B-A5 | Power-law regimes against the `sinh(n h)/(n h)` corrected value | relative 1e-6 on a noise-free uniform grid | The discretisation model is wrong, so no bias correction can be trusted. |
| B-A6 | Line-source derivative against `0.5 exp(-r_D^2/(4 t_D))`, `t_D > 300` | relative 1e-5 | The estimator is not accurate through a curved transition. |
| B-A7 | Pseudopressure against the constant-`mu Z` closed form | machine precision, 1e-13 relative | The transform is wrong; every exhibit is invalid. |
| B-A8 | Demonstrated Simpson order on a smooth analytic integrand, inside `SIMPSON_ORDER_WINDOW` | observed order in [3.7, 4.3] | The quadrature is not performing as documented. |
| B-A9 | Negative control for B-A8: the same study with `mu` and `Z` linearly interpolated from a table | observed order near 2, and clearly below the B-A8 band | The order test proves nothing about the production path. |
| B-A10 | Gas constant chain: a published worked gas example recovers its stated permeability | within 2 percent of the example's own answer | The 1422.52 / 1.422e6 trap is not closed. See section 15. |
| B-A11 | Exhibit B9 recovery of `k h` | within 5 percent of the known value (inherited, `PLAN.md` sections 6 and 12) | Recovery not demonstrated. Report the shortfall; do not widen the tolerance. |
| B-A12 | Exhibit B9 recovery of `s'` | within 0.5 of the known value (inherited, `PLAN.md` sections 6 and 12) | As B-A11. |
| B-A13 | Exhibit B9 numerical error against its recovery error | generator and quadrature error at least one order of magnitude below the reported recovery error | Condition I2. Discretisation-limited bound only. |
| B-A14 | Coverage of the 95 percent `kh` interval over at least 200 declared seeds | observed fraction within 3 binomial standard errors of 0.95, that is [0.904, 0.996] at 200 seeds | The interval procedure is not calibrated. Intervals are reported as nominal only and labelled uncalibrated. |
| B-A15 | Exhibit B8 window rule | finds no window spanning 1.0 log10 cycle | The exhibit is not inconclusive. See the falsifier in 11.2. |
| B-A16 | Exhibit B8 positive control on the untruncated record | recovers `k h` within 5 percent | Condition I3. No identifiability claim. |
| B-A17 | Smoothing sensitivity of the B9 result across `L` = 0, 0.1, 0.3 | `k h` varies by less than 1 percent | The conclusion depends on the smoothing choice and must be reported as such. |
| B-A18 | `(mu c_t)` ratio at minimum flowing pressure in B9 | within [0.8, 1.25] of initial | The uncorrected time nonlinearity is outside its declared budget; reduce the drawdown and rerun. |

Derivation of the inherited targets. `PLAN.md` gives 5 percent on `kh` and 0.5 on skin as
candidate project targets. This protocol accepts them and checks that they are attainable,
because a target the instrument cannot meet is not a gate.

For `kh`, the error budget on a clean synthetic is: 0.083 percent from the plateau approach,
capped by the section 9 window rule; exactly zero from the Bourdet smoothing bias, because the
plateau is affine in `ln t`; of order 1e-11 relative from the pseudopressure quadrature at the
module default; and the remainder from noise, which section 6 caps at 10 percent on one
derivative point and rather less on a plateau of many. The method floor is therefore around
0.1 percent and the 5 percent gate leaves roughly a factor of fifty of headroom for noise and
for the residual gas nonlinearity. The gate is attainable and is not merely a restatement of
the instrument's precision.

For `s'`, the transfers are all in closed form: 0.025 from a 5 percent error in `kh`, 0.112
from the worst admitted `mu c_t` drift, 0.048 from a 10 percent error in the declared
`phi (mu c_t)_i r_w^2` group, and `1.1513 * dm_1hr / m_slope` from an error `dm_1hr` in the
extrapolated one-hour pseudopressure. Those add to about 0.19 before the last term, so the 0.5
gate is attainable provided the one-hour extrapolation is good to about 27 percent of one
semilog cycle. That last condition is what the window rule of section 9 is really buying, and
it is the reason the window is fixed before the fit.

Derivation of B-A14's band. At 200 replicates the binomial standard error at `p = 0.95` is
`sqrt(0.95 * 0.05 / 200) = 0.0154`, so three standard errors is 0.046 and the band is
[0.904, 0.996]. The band is derived from the declared replicate count rather than chosen as a
round number; case A4's change log records why that matters.

## 14. Independence of the inverse from its reference

`PLAN.md` section 6 is explicit that an identical forward and inverse equation can pass a
self-consistency test while sharing one mistake, and requires the study to record which form
of independence was achieved. Stage B must record one of the following for each recovery
claim, and must not describe a weaker form as a stronger one.

1. External published data. The Bourdet Table 1 regression is the strongest available here:
   the derivative columns were produced by the authors' own implementation in 1989 with no
   knowledge of this code. It binds the formula, the weighting, the `L` rule, the units of `L`
   and the sign convention in one check.
2. External published worked example. A gas well-test example whose permeability answer is
   stated by its source anchors the whole field-unit constant chain against a number this
   project did not compute.
3. Closed-form analytic oracle. The line-source log-derivative `0.5 exp(-r_D^2/(4 t_D))` and
   the constant-`mu Z` pseudopressure closed form are derived from the governing equations and
   do not pass through the estimator at all.
4. Structural separation inside the repository. The forward generator lives in a different
   module from the estimator and shares no fitting code, exactly as `depletion` is separated
   from `material_balance` for Stage A. This is the weakest of the four and is never the only
   one claimed.

No licensed-software comparison has been performed, none is planned within this protocol, and
none may be implied. No independent human review of Stage B has occurred; when the author
reviews the work in separate numerical and interpretation passes, the report says that is what
happened and does not call it peer review.

## 15. Evidence-card corrections that bind Stage B

These are corrections already recorded in the evidence cards after adversarial review. They
are repeated here because each one is a live trap for Stage B specifically, and a protocol
that does not name them invites the implementation to rediscover them.

The gas radial-flow constant is 1422.52 with the gas rate in Mscf/D. The frequently printed
1.422e6 belongs to MMscf/D, and the two differ by a factor of a thousand. The source that
Stage B will most naturally reach for is internally inconsistent on this point: its
dimensionless pseudopressure equation prints 1422.52 and its semilog equation prints 1.422e6
in the same paper. The consistency check is arithmetic and takes one line, `1422.52 * 1.1513 =
1637.75` against the published 1637.74, and the worked-example check (B-A10) catches the
thousand-fold error outright. Stage B defines the constant once, with its rate unit in the
name, and derives 711.26 and 1637.74 from it. The standard-condition convention that
reproduces 1422.52 is one standard atmosphere and 60 degF, which is `units.SPE_STANDARD`; the
repository already uses that convention and Stage B does not introduce a second one.

The beta-derivative for spherical flow tends to zero from above, not to -1/2. Spherical flow
has `Delta_p = a - b t^(-1/2)` with `a, b > 0`, so the derivative is `+(b/2) t^(-1/2) > 0`
while the response tends to the constant `a`, and `beta = Delta_p' / Delta_p` therefore
approaches zero from above, exactly as it does for radial flow. The value -1/2 is the log-log
slope of the derivative curve, `d ln(Delta_p') / d ln t`, which is a different quantity. The
practical consequence is that beta does not separate spherical from radial flow and cannot be
used as a single-scalar regime classifier; the discriminator is the log-log slope, -1/2 against
0. This is why `diagnostics.py` deliberately ships no classifier, and why section 7 requires
the log-log slope plot rather than a beta plot.

The transposed Bourdet weighting equals the plain two-point secant, for any spacing. Both are
exact on data affine in `ln t`, so the radial-plateau oracle returns 0.5 for both and cannot
detect the error. Only the published-table regression, or an explicit "not the secant"
assertion on a lopsided grid, is discriminating. B-A2 exists for that reason and is not
redundant with B-A4.

The Table 1 regression tolerance is relative, not absolute. An absolute tolerance of 1e-3 psi
fails on most rows, because the published time column is rounded to five decimals and the
derivative values are large. B-A1 states 3e-3 relative.

The end-effect value quoted in an earlier draft of the derivative card is not reproducible and
is not an oracle. Under the plain `L` rule the affected point has no valid right neighbour and
the correct behaviour is to flag or drop it; the library drops it. Stage B asserts the drop,
not a value.

The pseudo-steady-state onset criteria `t_DA > 0.1` and `t > 948 phi mu c_t r_e^2 / k` are not
equivalent; they differ by a factor `pi/4`. `t_DA = 0.1` corresponds to `1192`, not `948`.
Stage B picks one and states it.

The bilinear-flow constant is 44.10, not 44.11; the printed 44.11 does not square to its own
companion constant and is almost certainly a transcription artefact. Bilinear flow is out of
scope for Stage B, so this matters only if the regime table is written down; if it is, use
44.10.

## 16. Registration

The problem with a hash inside the document it certifies is that the document changes when the
hash is written into it, so a naive self-hash can never be correct. Two ways out are used
together here.

First, the protocol's digest is defined over the protocol with its own digest block removed.
The rule is exact and reproducible:

    sed '/^<!-- registration-digest:begin -->$/,/^<!-- registration-digest:end -->$/d' \
      docs/protocols/stage_b_pta_protocol.md | shasum -a 256

Everything between and including the two marker lines is deleted before hashing, so writing a
digest into that block does not change the digest. Any edit anywhere else in the file does
change it. The digest therefore certifies the content of this protocol other than its own
registration block.

<!-- registration-digest:begin -->

    protocol digest (SHA-256, canonical rule above):
      594d53ee9ea05049ac84cfbb92c662943dd8e7cfd3f54b87806dfbd66239099a
    computed on: 2026-09-13
    repository revision at the time of computation: a9ce17c614db46cbe1079b1227c4f0b47b5bb2e0
    working tree at that revision: contains untracked files not part of this protocol

<!-- registration-digest:end -->

Second, and more important, a digest establishes integrity, not priority. It proves that this
file has not changed since the digest was computed; it does not prove that the file existed
before a run, because the author can recompute it at any moment. Nothing inside a file can
establish when the file was written. The only ordering evidence this repository will have is
the git commit that first contains this protocol, compared with the commit that first contains
any Stage B result, and a reader who wants that ordering guaranteed should check those two
commits rather than take this section's word for it. Case A4's protocol makes the same
disclosure for the same reason.

What the future Stage B run must record, in addition, through `provenance.RunRecord`:

| Item | How it is recorded |
|---|---|
| This protocol | SHA-256 by the canonical rule above, written into the run record's config, together with the digest this section carries so that a mismatch is visible |
| Code revision | The source revision and the dirty state of the working tree, which `RunRecord` already captures |
| Configuration | `configs/stage_b_pta.json`, hashed as a declared input. It does not exist yet; it is created with the case and must contain every number the run depends on, including the seed set, the noise standard deviation, the declared reservoir and well parameters, the `L` values, the window-rule tolerances and every acceptance threshold in section 13 |
| Inputs | There are none beyond the config. Stage B generates its own data, and the generator's parameters are in the config |
| Outputs | `summary.json` and every figure, hashed |
| Environment | Interpreter version, platform and package versions, which `RunRecord` already captures |

Hashing the config and the code revision is the part that does the real work. If the digest of
this protocol matches, and the config hash in the run record matches the config in the tree,
and the code revision is a commit that predates nothing, then a reader can check that the run
that produced a number is the run this protocol describes. That is a weaker claim than
pre-registration in a public registry, and it is stated as the weaker claim.

## 17. Deliverables and publication constraints

On completion Stage B produces a case directory under `cases/`, following the layout A1, A3
and A4 already use: `run.py`, `protocol.md` (a pointer to this document plus any
exhibit-specific additions), `results/summary.json`, `results/run_record.json`, `report.md`,
and a decision memo if and only if the study supports a decision.

Until that directory exists and its acceptance criteria have been evaluated:

- The site must show no Stage B figure, no permeability, no skin, no derivative plot and no
  type-curve match.
- The site must not list Stage B as in progress, in review, or nearly complete. It is not
  started.
- The release status stays at 0.2. `PLAN.md` section 16 gates release 0.3 on a defensible
  inconclusive case existing alongside a successful parameter recovery, and neither exists.
- No document in this repository may cite this protocol as evidence that Stage B works. It is
  evidence that Stage B has been designed.

When the study is complete, the report states which acceptance criteria passed, which failed,
which exhibits were inconclusive and why, and what would change the conclusion. A criterion
that was not evaluated is listed as not evaluated, never omitted.

## 18. Change log

- 2026-09-13 — protocol written. No Stage B code exists, no Stage B run has been performed,
  and no acceptance criterion in section 13 has been evaluated. The closed-form sensitivity
  results quoted in sections 6 and 13 were derived and arithmetically checked while writing
  this document; they are properties of the estimator and of the field-unit constants, not
  measurements of a Stage B run.

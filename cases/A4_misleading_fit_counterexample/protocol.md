# Case A4 protocol — when a straight p/Z line is convincing and wrong

Status: pre-registered. Written before the run. Every threshold below was fixed before
any recovered gas in place was looked at. Amendments are recorded in the change log at
the end of this file, with a date and a reason.

The pre-registration claim rests on the author's word and cannot be checked from the
repository state. The `cases/` tree is untracked in git, so there is no commit timestamp
separating this file from the runs, and this file's own modification time is later than
run-001's and run-002's because of the amendment recorded below. A reader who wants that
ordering guaranteed should ask for the case to be committed before the next run rather
than take this paragraph for it.

## Engineering question and decision

A dry-gas reservoir has a twelve-year pressure and production history. Plotting p/Z
against cumulative gas gives a straight line, and the line is extrapolated to its
x-intercept to obtain gas in place. The reservoir is in fact supported by an aquifer.

Three questions, in the order an engineer meets them:

1. How good does the volumetric fit look? Specifically, what R-squared does the wrong
   model achieve.
2. How wrong is the recovered gas in place, as a function of aquifer strength, and how
   does the error evolve as more history is observed.
3. Could anyone have told from the data alone? Does the residual pattern of the
   straight-line fit betray the misfit, and at what measurement noise does that signal
   disappear.

The decision this affects is whether a p/Z x-intercept may be used as the gas-in-place
basis for a development or depletion plan without an independent drive-mechanism
diagnosis. A useful answer changes the order of work: it either supports using the
straight line directly, or it makes a water-production and influx diagnosis a
prerequisite rather than a later refinement.

What would disprove the favoured interpretation. The favoured interpretation is that a
high R-squared carries no information about the x-intercept's correctness. It would be
disproved if, across the aquifer-strength sweep, R-squared fell materially wherever the
gas-in-place error was material — that is, if fit quality and intercept bias moved
together. Then the straight line would carry its own warning and no counterexample
exists.

## Sources and model identity

No field data. Every number is generated locally and is labelled synthetic throughout.

| Item | Identity |
|---|---|
| Forward generator | `reservoir_lab.depletion.simulate_water_drive_depletion`, coupled Fetkovich tank |
| Aquifer | `reservoir_lab.aquifer.FetkovichAquifer`, pseudosteady lumped-parameter |
| Inverse model under test | `reservoir_lab.material_balance.fit_pz_depletion`, volumetric OLS x-intercept |
| Deviation factor | `gas_properties.z_factor(method="dak")` on `pseudocritical_standing(0.65)` |
| Standard conditions | `units.SPE_STANDARD`, 14.696 psia and 60 degF, Z_sc = 1 |
| Source revision | recorded by `provenance.RunRecord` in `run_record.json` |

The generator and the estimator are structurally different models, not two arrangements
of one equation. The generator solves a coupled reservoir/aquifer balance in which the
hydrocarbon pore volume available to gas shrinks as water encroaches; the estimator
solves a constant-pore-volume inventory balance with no influx term. They live in
separate modules of the library and share no fitting or balance code. That separation
is what makes the bias reported here a statement about model structure rather than
about arithmetic applied twice.

## Governing model and assumptions

Generator, per step, in field units:

    (G - Gp) * Bg(p) = HCPV_i - (We - Bw * Wp)                      [reservoir ft^3]
    Bg = (p_sc / (T_sc * Z_sc)) * Z(p) * T / p                      [rcf/scf]
    dWe = ct*Wi * (p_aq(n-1) - (p(n-1) + p(n))/2) * (1 - exp(-J*dt/(ct*Wi)))   [bbl]
    p_aq(n) = p_aq(0) - We(n) / (ct*Wi)                             [psia]

Estimator:

    p/Z = (p_i/Z_i) * (1 - Gp/G),  fitted by OLS, G taken as the x-intercept.

Included: isothermal single-tank dry gas; pressure-dependent Z from a published
correlation; finite aquifer with pseudosteady influx; optional declared fraction of the
influx produced at surface.

Deliberately excluded: trapped (residual) gas behind the advancing water front; rock and
connate-water expansion; retrograde condensation; gas dissolved in water; areal or
vertical pressure gradients within the tank; any relative-permeability or saturation
calculation. The excluded mechanisms matter for the size of the effect and are listed
again in the report, because omitting trapped gas means the case understates how
optimistic a water-drive p/Z extrapolation is in practice: the true remaining
*recoverable* gas is below the true remaining gas in place, while the p/Z intercept is
above the true gas in place.

For the estimator to be appropriate, the observations would have to come from a tank of
constant hydrocarbon pore volume. Nothing in a p/Z plot asserts that, and testing that
assertion is the whole subject of this case.

## Experiments

Base reservoir, fixed for every experiment:

| Quantity | Value |
|---|---|
| True gas in place G | 1.0e11 scf (100 Bscf) |
| Initial pressure p_i | 4000 psia |
| Reservoir temperature | 180 degF (639.67 degR) |
| Gas specific gravity | 0.65 |
| Pressure floor for the solver | 250 psia, chosen to keep every deviation-factor call inside the published DAK window p_pr >= 0.2 |
| Production | constant rate, 0.55 * G over 12.0 years (4383 days) |
| Simulation timestep | 4383/144 = 30.44 days |
| Observations | every third step, quarterly, 49 points including t = 0 |
| Aquifer | p_aq(0) = 4000 psia, Wi = 3.0e9 bbl, ct = 6.0e-6 1/psi, so ct*Wi = 18000 bbl/psi and Wei = 7.2e7 bbl |

Aquifer strength is swept through the productivity index
J = 0, 0.05, 0.2, 0.6, 2.0, 6.0, 20.0, 60.0 bbl/day/psi, everything else held fixed.
Strength is *reported* as the terminal invaded pore-volume fraction
We_end * 5.614583 / HCPV_i, because that is the physical quantity the bias depends on;
J and the aquifer time constant tau = ct*Wi/J are reported alongside it.

J = 0 cannot be expressed as a `FetkovichAquifer`, which requires a strictly positive
productivity index. It is supplied as a four-field duck-typed object, which the
generator's documented contract accepts, with its initial pressure set equal to the
reservoir's so that the pressure search bracket is identical to the volumetric
generator's.

The declared base case for every single-case exhibit is J = 2.0 bbl/day/psi.

| ID | Experiment |
|---|---|
| E1 | Aquifer-strength sweep. One volumetric fit to the full history per strength. Core exhibit. |
| E2 | Progressive fits to the first 20, 40, 60, 80 and 100 percent of the history, per strength. |
| E3 | Exact reduction at J = 0: compare every series against `simulate_volumetric_depletion` on the same schedule. |
| E4 | Known-influx oracle: recover G from the full water-drive balance using the generator's reported We, at every observation, for every strength. |
| E5 | Timestep refinement at 1x, 2x, 4x and 8x for the base case and for the strongest aquifer. |
| E6 | Residual pattern and detectability. Tabulate the noise-free residuals of the volumetric fit against Gp; test the quadratic term of a second-order fit; find the pressure-noise level at which the test loses power. |
| E7 | Chronological holdout: calibrate on the first 60 percent of the observations, predict p/Z and pressure over the remaining 40 percent. |
| E8 | Water-production variant: base case with `produced_water_fraction = 0.30`, reporting the water-gas ratio trend. |
| E9 | POST-REVIEW, NOT PRE-REGISTERED. Added after the referee pass on run-002: empirical power curve of the E6 detector; detection rate over eight seeds and a pooled null; the ordinate formed with Z at the measured pressure instead of at truth; and the sensitivity of both the bias and the detector to the deviation-factor correlation (DAK against Hall-Yarborough). No acceptance criterion depends on E9 and none was added for it. |

Noise model. E1 to E5, E7 and E8 are run noise-free, so that the reported bias is the
model-structure error alone and not a realisation of measurement scatter. E6 is the only
pre-registered experiment with noise: independent Gaussian error on reported pressure,
standard deviation swept over 1, 2, 5, 10, 20, 40 and 80 psi, with 400 realisations per
level from a single declared seed. The noisy p/Z ordinate is formed by dividing the noisy
pressure by the true noise-free deviation factor; re-evaluating the correlation at the
measured pressure is the more realistic choice and is tested in E9 instead. The single
seed is reset identically at every noise level and for both the water-drive and the null
series, so the seven levels are rescalings of one draw set rather than seven independent
experiments; E9 reports the spread over eight seeds.

The relevant quantity is not gauge resolution but the error in a volume-averaged
reservoir pressure, which includes build-up extrapolation, datum correction and
incomplete stabilisation. This protocol takes 10 to 50 psi as the realistic band for that
quantity on a mature field and 1 psi as an unrealistically favourable limit. That band is
the author's engineering judgement and is not sourced to a published figure; what
`docs/evidence/matbal.md` supports is the order of magnitude, through Dake's 0.0465 to
0.117 psi/ft gas gradient over a datum error of hundreds of feet and through the
below-average pressure returned by an unstabilised build-up. It is the load-bearing
premise of the detectability conclusion and it is listed as a reversal condition in the
report.

Detection rule for E6, fixed here: fit `p/Z = a + b*u + c*u^2` with `u = Gp/G_true`, and
declare the curvature detected when the two-sided t-test of `c` against zero exceeds the
95 percent critical value at n - 3 degrees of freedom. No other statistic may be
substituted after seeing the residuals.

Data-exclusion rules, fixed here: no observation is excluded, no outlier is removed, no
point is reweighted, and the t = 0 point is retained in every fit. Progressive fits take
a prefix of the observation series and nothing else.

## Verification and acceptance

Independent oracle. Two, at different levels.

*Oracle 1, the closed form.* With the aquifer inert the balance reduces to
`p/Z = (p_i/Z_i)(1 - Gp/G)`, whose x-intercept is G exactly and analytically. This is
independent of the estimator because it is the analytic solution of the generator's own
equation, not the estimator's regression.

*Oracle 2, the full balance with influx known.* Rearranging the generator's balance,

    G = (Gp * Bg(p) - (We - Bw*Wp) * 5.614583) / (Bg(p) - Bg(p_i))

recovers G from a single observation once the influx is known. It is computed in the
case script from the history's reported series and the truth object's Bg, using no
function from `material_balance` and no regression. It is independent of the estimator
under test and it is the quantitative form of the answer to "what additional observation
would discriminate".

Acceptance criteria, all fixed before the run.

| ID | Criterion | Threshold | Failure action |
|---|---|---|---|
| A1 | J = 0 history matches `simulate_volumetric_depletion` | every one of the six series identical bit for bit | case INVALID, generator defect reported, nothing else published |
| A2 | J = 0 recovered G against Oracle 1 | relative error < 1e-9 | case INVALID |
| A3 | Worst coupled-solve residual over all runs | < 1e-5 psia of p/Z, and at least six orders of magnitude below the smallest straight-line misfit amplitude quoted | numerical error not separable from physics; bias claims withdrawn |
| A4 | Time-discretisation sensitivity of the recovered-G relative error, dt to dt/8 | changes by < 1e-3 | bias unresolved; report as a discretisation-limited bound only |
| A5 | Oracle 2 at every observation and every strength | relative error < 1e-8 | generator balance not closed; case INVALID |
| A6 | The counterexample exists: some strength with high R-squared and material bias | R-squared >= 0.999 together with G error >= 10 percent | INCONCLUSIVE: state that fit quality tracked bias and no counterexample was produced at these settings |
| A7 | G error rises monotonically with J across the sweep | strict monotonicity | not fatal; report the non-monotonicity and do not describe the relationship as monotone |
| A8 | Drift is real: base-case G from the first 20 percent against the full history | differ by >= 3 percentage points of true G | the drift diagnostic is declared not established at these settings |
| A9 | Detector negative control: J = 0 history, sigma_p = 5 psi | detection rate in [0.01, 0.12], nominal 0.05 | detector broken; every detectability conclusion withdrawn |
| A10 | Detector positive control: base case, sigma_p = 1 psi | detection rate >= 0.95 | detector cannot see the curvature it exists to see; detectability conclusions withdrawn |

A9 and A10 are a matched pair and both are required. A negative finding about
detectability is only worth recording once the instrument has been shown to see the
positive case and to stay quiet on the null case.

A9's band was declared without a derivation, and it is too loose. This is recorded here
rather than repaired, because repairing a threshold after seeing the answer is the thing
pre-registration exists to prevent. At 400 replicates the binomial standard error at
p = 0.05 is 0.0109, so a three-standard-error band would be [0.017, 0.083]; the declared
upper limit of 0.12 sits about 6.4 standard errors above nominal, and a detector with a
false-positive rate more than twice nominal would pass A9 unnoticed. The declared band is
the one the run was scored against and it has not been changed; the derived band is
reported alongside it in the run output. The observed 0.0675 is inside both. Future cases
in this workbench derive a control band from the binomial standard error at the declared
replicate count rather than declaring round numbers.

The case is declared INCONCLUSIVE if A6 fails, or if A3 or A4 fails in a way that leaves
the bias within an order of magnitude of the generator's own numerical error. It is
declared INVALID, and nothing is published beyond the defect, if A1, A2 or A5 fails.

Refinement and convergence. E5 is the timestep-refinement check. No spatial refinement
exists in a tank model. The root-finder residual is reported per run rather than
assumed.

## Interpretation and artifacts

Required tables: aquifer strength against recovered-G error and R-squared (E1);
progressive-fit drift (E2); residual against cumulative production for the base case
(E6); detection rate against pressure noise with both controls (E6).

Required analysis: separation of model-structure error from parameter uncertainty; the
relationship between the fitted standard error of G and the actual bias, since a
confidence interval computed inside the wrong model cannot cover the truth; the holdout
result stated against PLAN section 12's proposed 1 percent-of-initial-pressure gate.

Artifacts: `run.py`, `summary.json`, `run_record.json`, `report.md`, `decision_memo.md`,
and the two JSON files copied into `results/`.

Reviewers: author only, in separate numerical and interpretation passes. That is not
independent peer review and is not described as such anywhere in the case.

## Change log

- 2026-09-13 — protocol written and fixed before the first run.
- 2026-09-13 — run-001 executed and all ten criteria passed. Its run record stamped an
  absolute machine-local `repo_root`, which the repository hygiene gate refuses for a
  committed file, so `run.py` was changed to record the repository root relative to the
  working directory and the case was rerun as run-002. No experiment, threshold or
  numerical path was touched: the two runs' `summary.json` files are byte-identical.
  Run-001 is retained in the artifact tree.
- 2026-09-13, after the run and after an independent referee pass — E9 added. This is an
  amendment made with the answers in hand and it is labelled as such everywhere it
  appears. It adds no acceptance criterion, changes no threshold and touches no
  pre-registered experiment; run-003 reproduces every pre-registered result of run-002
  field for field, and run-004 repeats run-003 byte-identically. E9 exists because three
  claims in the first version of the report reached past the run: that the closed-form
  sigma was a half-power point (it is the level at which the expected statistic equals the
  critical value, and the half-power point is measured in E9 at 11.2 psi), that one seed
  characterised the detector, and that the deviation-factor correlation could be ignored.
  Two keys in `summary.json` were renamed in the same change, from
  `sigma_*_at_half_power_*` to `sigma_*_at_expected_t_equals_critical_*`, because the old
  names asserted the mislabelling.
- 2026-09-13, same amendment — the A9 derivation note above was added. The threshold
  itself is unchanged.

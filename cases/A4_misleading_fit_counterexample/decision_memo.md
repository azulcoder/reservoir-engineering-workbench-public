# Decision memo — Case A4

Subject: whether a p/Z x-intercept may be used as the gas-in-place basis for a
depletion or development decision, when the only evidence for the volumetric assumption
is the quality of the straight line.

Synthetic study. This memo is a methodological finding, not an instruction about any
field. Revised after a separate review pass conducted under a different role by the same
author, not by a different person; the corrections it prompted are listed at the end of
`report.md`. A further correction pass followed a repository-wide claims audit, and the
changes it made are listed in `docs/release/CORRECTIVE_RELEASE_REPORT.md`.

Four statements are kept apart everywhere in this memo, because the case reaches the
first two and does not reach the last two:

1. **Numerical verification** — the estimator inverts the forward map its own generator
   solves, to the precision the arithmetic allows.
2. **Conditional synthetic pressure reconstruction** — a held-out pressure series is
   reconstructed under stated conditions, including conditions an analyst could not meet.
3. **Physical interpretation** — what a reservoir is actually doing.
4. **Decision adequacy** — whether a number is fit to carry a depletion or development
   decision.

Clearing a project demonstration gate is evidence about (1) and (2). It is not evidence
about (3) or (4).

## Question and recommendation

An engineer holds twelve years of quarterly average reservoir pressure and cumulative
gas for a dry-gas reservoir. The p/Z plot is a straight line, R-squared 0.9999, and the
x-intercept gives 112.5 Bscf.

**Recommendation, conditional: do not adopt a p/Z x-intercept as a volumetric gas-in-place
basis until the drive mechanism has been established from an observation other than the
p/Z line itself.** On the evidence of this case, the fit statistic and the chronological
holdout error are both incapable of distinguishing a closed tank from an
aquifer-supported reservoir whose gas in place is overstated by 12.5 percent and whose
remaining gas in place is overstated by 27.8 percent.

The required extra evidence is a *metered water-production record*. That is the new
observation. A Cole or pot-aquifer plot is not: both are re-plots of the same pressure and
production history the p/Z fit already uses, so they add information only to the extent
that produced water is separately measured and entered into them. Neither plot was run in
this case.

`G` and `G - G_p` in this memo are inventory in place. Recoverable gas is smaller by
whatever the drive mechanism and the abandonment condition leave behind, and reserves are
a further commercial and regulatory classification of a recoverable quantity. No number
here is a recoverable volume and no number here is a reserve.

**The recommendation reverses only under a narrower condition than the first version of
this memo stated, and the reversal evidence is weaker than it looks.** The candidate
trigger is a metered water-gas ratio that stays flat and small, no aquifer identified in
the structural interpretation, and a p/Z estimate that does not drift materially in either
direction as history accumulates. Four qualifications travel with it.

- Low water production does not establish a closed tank. `docs/evidence/matbal.md:515`
  records an Oklahoma Morrow sand field case in which no water production and a straight
  p/Z plot together suggested a closed tank while the conventional extrapolation was about
  16 percent too high. The same record has an aquifer-supported well making only
  1.5 STB/MMscf after ten years. This trigger is the evidence set that has already failed
  in the repository's own documented field counterexample, and jointly these three
  indicators leave a bias of that order unexcluded.
- A stable p/Z estimate is not evidence that the estimate is right. In this sweep the two
  strongest aquifers produce an estimate that peaks and falls back as the aquifer depletes.
- The two rows the reversal leans on are the weakest aquifers in the sweep, at time
  constants of 986 and 247 years against a 4383-day horizon. Those are precisely the rows
  where the Fetkovich model's pseudosteady assumption is least defensible
  (`docs/evidence/aquifer.md:586`), and a transient van Everdingen-Hurst aquifer is the
  change most likely to move them. Terminal invaded pore-volume fraction is also not an
  observable in the field; it is a generator parameter.
- The gate those rows are scored against does not say what the first version of this memo
  said it said. See the next paragraph.

**Against the PLAN gate, only one row clears it.** At J = 0.05 the p/Z gas-in-place error
is +0.32 percent, which is below 1 percent. At J = 0.2 it is **+1.26 percent, which is
above 1 percent** — the first version of this memo stated both as inside the gate, and
that was arithmetically wrong. Separately, the gate itself is narrower than it was used
as: `PLAN.md:289` scopes the 1 percent row by its own words to "the delivered small-noise
demonstration", and `PLAN.md:282` states that these are proposed project gates, not
regulatory requirements or universal engineering tolerances, to be scaled and justified for
each case. This case is a noise-free structural counterexample and never rescaled that row.
Clearing a project demonstration gate is not evidence of general reservoir-interpretation
adequacy and not evidence of development-decision adequacy. The conclusion is about
conditions, and it now rests on one row rather than two.

The recommendation is not "p/Z is unreliable". The method is exact under its stated
assumptions; the finding is about the conditions under which a straight line stops
carrying the information people read from it.

## Evidence

All figures from run `artifacts/A4_misleading_fit_counterexample/run-006`; see
`results/summary.json` and `results/run_record.json`. Every pre-registered result in it
is identical to run-002's; run-003 onwards add the post-review sensitivities (E9).

| Observation | Source | Value |
|---|---|---|
| Synthetic observations | coupled Fetkovich generator, noise-free | 49 quarterly points over 12.0 years |
| Fit quality of the wrong model, base case | volumetric OLS | R-squared 0.999859 |
| Gas-in-place error, base case | against known truth 1.0e11 scf | +12.50% |
| Remaining-gas-in-place error, base case | same fit | +27.78% |
| Bias expressed in the fit's own standard errors | delta-method x-intercept stderr | 83.6 sigma |
| Range over the aquifer sweep | 8 productivity indices | +0.00% to +74.01%, R-squared 1.000000 down to 0.995207 |
| Drift over observed history, base case | five nested prefix fits of one noise-free history | +5.54% at 20% of history to +12.50% at 100% |
| Conditional synthetic pressure reconstruction, base case | calibrate 7.25 yr, reconstruct 4.75 yr using the held-out states' own synthetic Z | pressure RMSE 15.7 psi = 0.39% of p_i; below the borrowed 1% demonstration gate |
| Curvature detectable to | pre-registered t-test, power curve measured post-review on this design | 50% power at pressure sigma 11.2 psi on this design |
| Gas in place recovered when the influx, pressures and PVT are all supplied exactly, noise-free | independent balance, no regression | within 3.6e-11 relative — an identifiability statement under exactness assumptions, not an attainable accuracy |
| Water-gas ratio in the produced-water variant | declared 30% of incremental influx produced | 15.6 STB/MMscf at 3 years, 46.8 at 12 years |

Actual data: none. Synthetic observations: all of the above. Model estimates: the fitted
gas in place and its standard error. Assumed inputs: reservoir size, initial pressure,
temperature, gas gravity, aquifer volume, compressibility, productivity index, offtake
schedule, produced-water fraction — all declared in `protocol.md` before the run.

## Interpretation

The mechanism is a pore-volume bookkeeping error, not a statistical one. The volumetric
balance assumes the gas occupies a fixed hydrocarbon pore volume, so that the remaining
gas is proportional to p/Z and the line's x-intercept is the whole inventory. When water
encroaches, part of that pore volume is no longer available to gas. Pressure is then held
up relative to the volumetric expectation, the p/Z line is flatter than it should be, and
a flatter line has its x-intercept further to the right. The reservoir looks bigger
because the pressure has not fallen as far as the produced volume implies.

The reason this is hard to see is that the influx enters slowly and smoothly. Over a
twelve-year window a Fetkovich aquifer contributes a gently curving perturbation, and a
gentle curve over a limited range is nearly indistinguishable from a straight line with a
slightly different slope. The regression absorbs it into the slope, which is precisely
the parameter that sets the x-intercept. R-squared measures the part the regression could
not absorb, which is small by construction, so it cannot report the part it did absorb.

The competing explanations an engineer should hold open are not only "volumetric versus
water drive". A geopressured reservoir with significant rock and connate-water expansion
produces a qualitatively similar early flattening from a completely different mechanism,
and `material_balance.ramagost_farshad_corrected_p_over_z` exists for that case. A
communicating adjacent block would also flatten the line. These are not distinguished by
this case and they are not distinguished by a p/Z plot.

An unrepresentative average pressure deserves separate treatment. The figures in this memo
assume a pore-volume weighted average that exists and is unbiased, and a real surveillance
record does not supply one. Which way the resulting error points is an argument, not a
result of this case: the wells that survive to be surveyed may be the ones the water has
not reached, biasing the sample toward the un-swept, higher-pressure part of the tank and
pushing the x-intercept further right; the opposite selection is equally available, since
wells that are shut in long enough to give a good build-up are not a random sample either.
The tank model here has no areal gradient at all, so nothing in this case can decide the
sign. It is recorded as an untested mechanism, not as a direction.

This is a known result, not a new one. `docs/evidence/matbal.md` records Pletcher (SPE
75354): a two-cell water-drive simulation at R-squared 0.9998 whose uncorrected p/Z
extrapolation is 15.3 percent high, and an Oklahoma Morrow sand field case where no water
production and a straight p/Z plot together suggested a closed tank while the conventional
extrapolation was about 16 percent too high. This case's +12.50 percent at R-squared
0.99986 sits in the same decade, which is the only external corroboration a synthetic
study can have.

Non-uniqueness is the practical core of it, and it is practical rather than structural.
Aquifer strength and gas in place trade off against each other along the observed history:
a larger reservoir with no aquifer and a smaller reservoir with an aquifer produce nearly
the same pressure record.

The parameter count has to be stated correctly, because the first version of this memo got
it wrong. `fit_pz_depletion` is not a one-parameter fit. It fits a free intercept and a
free slope — two parameters — and `G = -a/b` is a derived function of both; the intercept
is not pinned to the measured `p_i/Z_i`, which is exactly why the residual table shows the
fitted line missing the measured initial p/Z by 24.63 psia. Adding an influx term gives a
two-parameter physical fit in (G, J), and that fit is identifiable in principle on
noise-free data. A direct least-squares minimisation over (G, J) against the base-case
history, with **no influx observation supplied at all**, returns G within 1.0e-11 relative of
the truth and J = 2.0000 to ten figures, at a residual of 1.8e-9 psia of p/Z. What defeats it
in the field is conditioning rather than structure. Profiling the noise-free
base history over J at fixed G gives a best-fit misfit of 0.57 psia of p/Z at +0.5 percent
in G, 1.16 psia at +1 percent, 6.03 psia at +5 percent and 20.3 psia — about 20.5 psi rms
in pressure — at the +12.5 percent the volumetric fit actually returns. The last of those
is inside the 10-to-50-psi pressure error this memo assumes, so at field accuracy the
aquifer parameter absorbs a large error in G at no detectable cost. The honest statement is
therefore **practical, noise-limited ambiguity**, not structural non-identifiability, and
the reason to measure water is that it breaks the conditioning, not that the problem is
otherwise unsolvable.

Provenance of that joint fit and that profile: both were computed during the claims-audit
correction pass by calling the committed generator directly, with J re-optimised by
golden-section search at each G and G by an outer golden-section search. Neither is part of
run-006's payload, neither was pre-registered, and neither appears in `results/summary.json`.
They are reported here because they are what retires a false structural claim; if either is
to become a gated result it needs its own pre-registered experiment and its own run ID.

An operating constraint changes what the data can reveal. This case used constant
offtake. A reservoir on a plateau constrained by facilities produces a smoother pressure
record with less curvature information, and the same aquifer would be correspondingly
harder to detect. The converse is also true and this memo should say so: a real history
with rate changes, shut-ins and varying well counts imprints pressure transients that are
themselves a diagnostic, so a clean constant-rate history is neither the best nor the
worst case for detection. It is simply not a realistic one.

## Uncertainty and limits

**Data uncertainty.** The detectability result is driven by the error in the
volume-averaged reservoir pressure, and by the sampling design and the aquifer strength
alongside it — 49 quarterly observations over twelve years at J = 2.0, tested by a
quadratic t-test. It is not driven by gauge resolution: a quartz gauge resolves below
1 psi, but the ordinate of a p/Z plot is a pressure inferred from a build-up extrapolation
at a datum. This memo takes 10 to 50 psi as the realistic band for that on a mature field;
that is the author's judgement, supported for its order of magnitude by the
datum-correction and build-up entries in `docs/evidence/matbal.md` but not sourced to a
published figure, and it is the load-bearing premise of the conclusion below. **On this
design** the curvature test loses half its power at 11.2 psi — measured over 4000
replicates per level, not inferred from the closed form, which is a different quantity
(see `report.md`) — and is effectively blind by 40 psi, where it fires at 0.0850 against a
0.0675 false-positive rate on the declared seed. Change the horizon, the cadence or the
aquifer strength and that crossing moves.

**The detectability figures are the weak half of this case.** Four qualifications, three
added after the separate review pass and one after the claims audit. The measured power
curve that supersedes the closed form is itself ten rescalings of a single 4000-draw set,
not ten independent experiments, so it inherits the limitation it was introduced to
expose. The pre-registered noise sweep uses one seed reset
identically at every level and for both series, so its seven levels are rescalings of one
draw set; over eight seeds the null rate runs 0.0425 to 0.0675 and pools to 0.0473 at
20000 replicates, so the quoted 0.0675 is a high draw rather than the detector's size.
The sweep divides the noisy pressure by the true deviation factor rather than by Z
re-evaluated at the measured pressure, which understates detectability a little. And the
detector's false-positive rate holds only if the analyst reads Z from the same
correlation that generated the history: reading a DAK history with Hall-Yarborough
produces a curvature statistic of -9.05 on a strictly volumetric reservoir, against a
critical value of 2.01 and against the aquifer's own +4.51. The gas-in-place bias is
untouched by that — it moves from +12.50 to +12.22 percent — but the curvature test is
not a clean aquifer diagnostic in the field.

**Numerical error.** Bounded and negligible. Worst coupled-solve residual 3.43e-9 psia of
p/Z, which is 9.9 orders of magnitude below the smallest per-exhibit largest residual
quoted in the pre-registered exhibits, and 9.1 orders below the smallest such figure
quoted anywhere in the report. Individual tabulated residuals go down to 0.24 psia, still
7.9 orders above the solver residual. Recovered
gas-in-place error changes by at most 2.0e-5 between dt and dt/8. The demonstration
reduces bitwise to the volumetric generator at zero aquifer productivity.

**Parameter uncertainty.** The fit's own standard error on gas in place is 0.13 percent
at the base case. It is worse than useless here: it is 84 times smaller than the actual
error, so quoting it would give a false impression of precision. Bootstrapping, weighted
regression and errors-in-variables methods were not run in this case, so no direction is
claimed for what they would do to the interval. The argument that survives without them is
the stronger one and does not need a direction: the error is model-structure error, it is
not represented anywhere inside the fitted model, and an interval recomputed by any method
inside that model cannot contain it.

**Model-structure uncertainty.** This is the whole finding and it is not representable
inside the fitted model. The only way to bound it is to fit a structurally different
model or to measure the missing term.

**Not measured or represented.** Trapped gas behind the water front. Its absence is a gap
between two different quantities rather than a measured direction: this case reports
inventory in place, and trapped gas would reduce *recoverable* gas without moving the
inventory the p/Z intercept claims to estimate. That is an argument about the practical
consequence and it was not run here. Sampling bias in the average reservoir pressure,
whose sign this case cannot decide. Rock and connate-water
expansion, condensate dropout, gas dissolved in water, areal and vertical pressure
gradients, transient aquifer behaviour, correlated or systematically biased pressure
error, and any facility constraint on offtake. The aquifer is pseudosteady from the first
timestep and starts in equilibrium with the reservoir, so the smooth influx that makes
the misfit hard to see is partly assumed rather than demonstrated. The production history
is unrealistically clean: constant rate for twelve years, 49 evenly spaced observations,
no shut-ins, no gaps, no outliers.

**Probability conventions.** No probabilistic forecast is quoted. Detection rates are
frequencies over 400 seeded Monte-Carlo realisations at each noise level and carry a
Monte-Carlo standard error of roughly 0.01 to 0.025. Percentages of gas in place are
deterministic, computed from noise-free histories against a known truth.

## Next measurement or action

**First: a metered water-production record, and a water-gas ratio plotted against time.**
In the produced-water variant the ratio reaches 15.6 STB/MMscf by year three and 46.8 by
year twelve, while the p/Z fit is still returning R-squared 0.9999. Water production is
visible years before the p/Z drift accumulates, and it is a direct observation of the
mechanism rather than an inference from the shape of a line.

**Second: convert that record into an influx estimate, and close the full balance.** The
conversion is two steps, not one, and collapsing them is how a produced-water record gets
mistaken for an influx measurement. Cumulative produced water `W_p` is a standard-condition
volume. Its reservoir-volume equivalent is `W_p * B_w`. Total influx `W_e` is a third
quantity, and `W_p * B_w -> W_e` follows only from an aquifer model or from closing the
balance. In this case's own produced-water variant `W_p * B_w` is 30 percent of `W_e` by
declaration, so the produced record there understates the influx by a factor of 3.33 and
bounds it from below rather than measuring it.

This case shows why the direction is right, with a caveat that has to travel with the
number: supplied with the *exact* influx, the *exact* pressures and the *exact* PVT on
*noise-free* observations, the full balance recovers gas in place to 3.6e-11 relative with
no regression at all. That is a statement about identifiability under a set of exactness
assumptions broader than "the influx alone", and not an accuracy anyone will achieve. A
field influx estimate carries an error that would dominate the recovered gas in place, and
nothing in this case quantifies how well an influx can be estimated in practice. A Cole or
pot-aquifer plot is the routine presentational form of the closed balance; it is a
transformation of the pressure and production history already in hand, not a further
observation, and neither plot was run in this case. `aquifer.FetkovichAquifer` and
`material_balance.general_material_balance_residual` support the quantitative form.

**Third, cheap and immediate: refit the existing history on prefixes and look at the
drift.** No new data are required. A material move in the estimate over the observed
history, **in either direction**, with each fit still visually straight, is evidence
against the volumetric assumption. The direction is not a signature: in this case's base
history the estimate marches 7 percentage points upward, while `docs/evidence/matbal.md`
records Pletcher's modified p/Z running the other way, from +8.2 percent at 11 percent
recovery down to +4.0 percent at 54 percent, because his aquifer does not deplete over the
window. Look for movement, not for a sign. The power and the size of this diagnostic under
measurement noise were never measured in this case, so the claim that it needs less
pressure accuracy than the curvature test is an untested argument and is recorded as one.

As a methodological lesson rather than a field instruction: this case says that a fit
statistic and a conditional holdout reconstruction are tests of the residuals and of the
reconstructed series over the observed horizon respectively. Neither is a test of an
extrapolated quantity that lives outside the data, neither is a physical interpretation of
the drive mechanism, and neither establishes that a number is adequate to carry a
development decision. A gas-in-place estimate from an x-intercept should always be quoted
with the observed depletion fraction attached — the library attaches it, and warns below
about 20 percent — should be labelled as inventory in place rather than as a recoverable
volume or a reserve, and should never be quoted with a confidence interval as its only
statement of uncertainty.

## Reproducibility and review

| Item | Value |
|---|---|
| Run ID | `artifacts/A4_misleading_fit_counterexample/run-006` |
| Command | `PYTHONPATH=src python3 cases/A4_misleading_fit_counterexample/run.py --out artifacts/A4_misleading_fit_counterexample/run-006` |
| Source revision, config hash, environment, seed | recorded in `results/run_record.json` |
| Seed | 20260913, single `random.Random`, used by the E6 noise sweep; E9 declares separate seeds 20260914 to 20260922 |
| Dependencies | Python standard library only |
| Reference comparison | closed-form volumetric x-intercept (Oracle 1) and the full balance with influx known (Oracle 2), both independent of the estimator under test |

Determinism: run-001 and run-002 are the same computation and their `summary.json` files
are byte-identical; run-003 to run-007 are likewise byte-identical to each other. No run
directory has been deleted. Run-001 was superseded because its run record carried an
absolute machine-local `repo_root`, which the repository hygiene gate refuses for a
committed file; run-002 was superseded by run-003, which adds the post-review
sensitivities and leaves every pre-registered result unchanged.

Pre-registration rests on the author's word. The reason given in the first version of this
memo — that `cases/` is untracked in git — is stale: the tree is tracked. The reason the
ordering is still unverifiable is different and still holds. This case's `run.py` declares
no inputs in its run record, so nothing machine-written pins `protocol.md` to the runs, and
every A4 file entered git in a single commit, so no commit timestamp separates the protocol
from the runs either. **A1 and A4 prospective ordering therefore remains unverified.** A2
and A3 do declare `protocol.md` as an input and pin it by SHA-256 inside a record the run
itself wrote; that establishes internal content linkage as recorded. It is not an
independent trusted timestamp and it is not proof against retrospective construction. The
shipped `results/run_record.json` still carries the stale "cases tree is untracked" string
in its limitations list; it is a contemporaneous machine-written record and has deliberately
not been edited.

Checks actually executed: the ten pre-registered acceptance criteria A1 to A10, all
passed; `ruff check` and `ruff format --check` on `cases/A4_misleading_fit_counterexample`;
`python3 scripts/check_repository.py`. Verdict recorded by the run:
`ESTABLISHED: high-R-squared volumetric fits with material, drifting gas-in-place bias`.

Review findings. A separate review pass on run-002 checked the reported numbers against
the run output and attacked the claims; it found one mis-rounded cell, two rounding
inconsistencies, a mislabelled closed-form quantity, five overclaims and seven
unacknowledged limitations. All are corrected or conceded in `report.md`, which carries
the audit trail. From the author's own interpretation pass, two items are carried forward
rather than resolved. The residual table exposes a second
diagnostic — the fitted line undershooting the measured initial p/Z by 0.57 percent —
which was not pre-registered and is therefore recorded as a hypothesis, not a result. And
the sweep varies one aquifer parameter only, so the bias figures are illustrative
magnitudes and not a mapped sensitivity surface.

**No human peer review took place, and no external or independent reviewer participated,
in the original case or in any revision of it.** Every pass — the numerical pass, the
interpretation pass, the review pass that produced this revision, and the later
repository-wide claims audit — was conducted under a different role by the same author,
not by a different person, and `AGENTS.md:46` states the governing rule: different role
names do not create independent expertise or independent evidence. The first version of
this memo called the revision pass "independent" and "external"; both words are withdrawn.
What those passes did was check reported numbers against the run output and attack the
claims. They did not independently re-derive the physics. That raises the confidence in
what is reported and does not make any of it a peer-reviewed result.

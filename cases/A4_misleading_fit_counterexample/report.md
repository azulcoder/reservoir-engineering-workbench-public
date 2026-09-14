# Case A4 — when a straight p/Z line is convincing and wrong

Run: `artifacts/A4_misleading_fit_counterexample/run-006`.
Artifacts copied to `cases/A4_misleading_fit_counterexample/results/`
(`summary.json`, `run_record.json`). Every number below comes from that run.

Run history, kept in full; no run directory has been deleted or overwritten.

- run-001 and run-002 are the same computation, `summary.json` byte-identical. Run-001
  was superseded because its run record stamped the author's absolute home directory
  into the `repo_root` field, which the repository hygiene gate refuses for a committed
  file. Only that provenance field differs and no result changed.
- run-003 adds E9, the block of post-review sensitivities described below, and renames
  two keys whose old names asserted a mislabelling (`sigma_*_at_half_power_*` became
  `sigma_*_at_expected_t_equals_critical_*`). Every pre-registered result in it is
  identical to run-002's, field for field. **[SUPERSEDED] That rename was presented as the
  fix for a mislabelling and it substituted a second mislabel for the first.** The shipped
  key names still assert a statistical property the number does not have; the derivation is
  worked through under "Could anyone have told from the data alone?" below. The key names
  in `results/summary.json` are left exactly as the run wrote them, because a shipped run
  record is not edited after the fact.
- run-004 and run-005 follow a cosmetic reformat of `run.py`. The E9 configuration keys
  enter the run record at run-006, not at run-004: run-004 and run-005 carry none of
  them. All four of run-004 to run-007 have `summary.json` byte-identical to run-003's,
  which is this case's determinism check: five runs, one byte-for-byte answer. run-007
  is a determinism repeat of the shipped run-006.

This revision follows a separate review pass — conducted under a different role by the same
author, not by a different person, and not human peer review. Corrections and retractions
made in response to it are marked in place, and the section "What the review pass changed"
at the end lists them. A later repository-wide claims audit produced a second set of
corrections, also marked in place; `docs/release/CORRECTIVE_RELEASE_REPORT.md` lists those.

Synthetic throughout. No field data of any kind is used, implied or represented.

Four statements are kept apart throughout this report, because the case reaches the first
two and does not reach the last two: **numerical verification** (the estimator inverts the
forward map to the precision the arithmetic allows); **conditional pressure reconstruction**
(a held-out synthetic pressure series reconstructed under stated conditions, including
conditions a field analyst could not meet); **physical interpretation** (what a reservoir is
actually doing); and **decision adequacy** (whether a number is fit to carry a depletion or
development decision). Clearing a project demonstration gate is evidence about the first two
only.

Quantities are also kept apart. `G` and `G - G_p` here are inventory in place. Recoverable
gas is smaller by whatever the drive mechanism and the abandonment condition leave behind,
and reserves are a further commercial and regulatory classification of a recoverable
quantity. Nothing in this report is a recoverable volume or a reserve.

## The question

A dry-gas reservoir is supported by an aquifer and is being interpreted with the
volumetric p/Z model. How good does the fit look, how wrong is the recovered gas in
place, and could anyone have told from the data alone?

## The answer

The fit looks excellent and the answer is badly wrong, and a close fit does not, by
itself, establish that the volumetric assumption is appropriate.

**[SUPERSEDED] The first version of this paragraph said that over most of the range "one
carries no information about the other". That overstated what the study shows. The
evidence here is that an extremely high R-squared can coexist with a materially biased
gas-in-place estimate; that is not a demonstration that R-squared and estimation error are
statistically independent, nor that R-squared carries no information in any other context.
The narrower statement above is what the runs support.**

At the declared base case — a Fetkovich aquifer with productivity index
J = 2.0 bbl/day/psi, which lets water occupy 11.3 percent of the hydrocarbon pore volume
over twelve years — the volumetric fit to 49 quarterly noise-free observations returns
R-squared = 0.999859 and a gas in place of 1.1250e11 scf against a true 1.0000e11 scf.
That is an overestimate of 12.50 percent. The same fit reports a one-sigma standard error
on gas in place of 1.496e8 scf, which is 0.13 percent of the estimate: the bias is 83.6
standard errors. The fitted interval does not contain the truth and could not, because
the interval is computed inside the wrong model.

At J = 6.0 the fit still returns R-squared = 0.999352 and overestimates gas in place by
33.6 percent. Only at the two strongest aquifers in the sweep does R-squared fall below
0.999, and even at J = 60, where gas in place is 74 percent too high, R-squared is
0.9952, which still looks like a good straight line.

The straight-line fit is not useless. It is exact when the reservoir is volumetric, and
at negligible aquifer strength its error is small. What it stops doing, once any
meaningful influx is present, is carrying the information people read from it: the
x-intercept stops being gas in place, and the fit statistic stops warning them.

## Evidence

### The generator and the estimator are different models

The histories come from `reservoir_lab.depletion.simulate_water_drive_depletion`, which
solves a reservoir tank coupled to a `FetkovichAquifer` implicitly at every step. The
estimator is `reservoir_lab.material_balance.fit_pz_depletion`, a constant-pore-volume
inventory balance with no influx term. They are separate modules and share no balance or
fitting code. The bias reported here is therefore a model-structure error and not
algebra applied twice in the same direction.

Reservoir: G = 1.0e11 scf, p_i = 4000 psia, 180 degF, gas gravity 0.65, deviation factor
from Dranchuk-Abou-Kassem on Standing dry-gas pseudocriticals, SPE standard conditions.
Constant offtake of 0.55 G over 12.0 years, 144 monthly timesteps, observations every
third step. Aquifer: p_aq(0) = 4000 psia, W_i = 3.0e9 bbl, c_t = 6.0e-6 1/psi, so
c_t*W_i = 18000 bbl/psi. Only the productivity index is varied.

### Core exhibit: aquifer strength against recovered gas in place

| J, bbl/d/psi | tau, days | We_end/HCPV_i | p_end, psia | R-squared | G error | remaining-gas error | bias / stderr |
|---|---|---|---|---|---|---|---|
| 0 | infinite | 0.0000 | 1714.8 | 1.000000 | -0.00% | -0.00% | n/a |
| 0.05 | 360000 | 0.0036 | 1720.6 | 1.000000 | +0.32% | +0.70% | 88 |
| 0.2 | 90000 | 0.0141 | 1737.7 | 0.999998 | +1.26% | +2.81% | 88 |
| 0.6 | 30000 | 0.0402 | 1781.9 | 0.999985 | +3.79% | +8.43% | 86 |
| **2.0** | **9000** | **0.1127** | **1919.1** | **0.999859** | **+12.50%** | **+27.78%** | **84** |
| 6.0 | 3000 | 0.2215 | 2176.0 | 0.999352 | +33.59% | +74.65% | 84 |
| 20.0 | 900 | 0.3037 | 2430.6 | 0.997451 | +62.74% | +139.41% | 62 |
| 60.0 | 300 | 0.3303 | 2528.8 | 0.995207 | +74.01% | +164.46% | 50 |

`We_end/HCPV_i` is the terminal water influx as a fraction of the initial hydrocarbon
pore volume, which is the physical measure of aquifer strength; J and the aquifer time
constant tau = c_t*W_i/J are the parameters that produce it. The error in gas in place
rises monotonically with J across the whole sweep.

Two features of this table matter more than the headline bias.

The first is the last column. Across the sweep the bias is 50 to 88 times the standard
error the fit reports for its own x-intercept. A narrower confidence interval does not
help; it makes the answer more confidently wrong. Model-structure error is not
represented anywhere in the regression's uncertainty. (The volumetric row is excluded
from that statement: its residuals are at the 1e-10 level, so its standard error is a
rounding artefact and the ratio is meaningless.)

The second is the remaining-gas column. The quantity an engineer acts on is not G but
G − G_p. At the base case, G is 12.50 percent high while remaining gas in place is 27.78
percent high, because the same absolute error is being expressed against a much smaller
denominator. That amplification is a property of late-life estimates and it works
against the interpreter every time.

### Where this sits against prior work

This effect is not new and the case does not claim it is. The repository's own evidence
file records it from the literature, and that record should be read alongside the table
above rather than after it (`docs/evidence/matbal.md`, "Failure modes"):

- Pletcher (SPE 75354) simulated a two-cell weak water drive and obtained R-squared =
  0.9998 over ten years while the compressibility-corrected p/Z extrapolation was 8.2
  percent high at 11 percent recovery, 6.5 percent high at 27 percent and still 4.0
  percent high after 54 percent of the gas had been produced. The evidence file's own
  recomputation of the same data without the compressibility correction gives +15.3
  percent at 11 percent recovery.
- The same paper documents a field case — an Oklahoma Morrow sand — where no water
  production and a straight p/Z plot together suggested a closed tank, and the
  conventional p/Z extrapolation was about 16 percent too high uncorrected and nearly 11
  percent too high after correction, with a cumulative influx of only 3 percent of the
  original hydrocarbon pore volume supplying about 10 percent of the voidage.
- Dake states the mechanism directly: early material-balance plots all appear linear,
  and extrapolating that early trend as a depletion reservoir returns too large a gas in
  place.

The comparison is a corroboration, not a match: this case's +12.50 percent at R-squared =
0.99986 is at 55 percent recovery with an influx of 11.3 percent of the hydrocarbon pore
volume, while Pletcher's figures are at a different aquifer size, a different recovery
fraction and a different deviation-factor treatment. What agrees is the order of
magnitude and the qualitative shape: a fit statistic in the fourth or fifth nine
alongside a ten-to-sixteen-percent overestimate of gas in place. Two independent
demonstrations landing in the same decade of error is the strongest external check
available to a synthetic case, and it is better evidence than either alone.

One difference matters for the drift diagnostic the decision memo recommends, and it is
recorded here because it is the difference a reader would act on: **the direction of drift
is opposite.** Pletcher's modified p/Z runs +8.2 percent at 11 percent recovery, +6.5
percent at 27 percent and +4.0 percent at 54 percent — decreasing — because his aquifer
does not deplete over the window, while this case's base-case progressive fits rise from
+5.54 percent to +12.50 percent. The diagnostic to look for is a material move in either
direction, not an upward march.

What this case adds is not the effect but the attack on it: a pre-registered protocol, a
bitwise reduction to the volumetric limit, a timestep-refinement check, an estimator-free
oracle, a matched pair of detector controls, and a measured power curve for the
detectability question.

### Drift: recovered G against the fraction of history observed

Volumetric fits to the first 20, 40, 60, 80 and 100 percent of the history, each fitted
separately. They are nested prefixes of one noise-free realisation at each aquifer setting,
not five independent experiments:

| J | 20% | 40% | 60% | 80% | 100% |
|---|---|---|---|---|---|
| 0 | +0.00% | -0.00% | -0.00% | -0.00% | -0.00% |
| 0.05 | +0.14% | +0.23% | +0.28% | +0.31% | +0.32% |
| 0.2 | +0.56% | +0.90% | +1.14% | +1.24% | +1.26% |
| 0.6 | +1.67% | +2.70% | +3.41% | +3.73% | +3.79% |
| **2.0** | **+5.54%** | **+8.95%** | **+11.30%** | **+12.34%** | **+12.50%** |
| 6.0 | +16.36% | +25.95% | +31.96% | +34.06% | +33.59% |
| 20.0 | +48.66% | +67.04% | +71.56% | +68.97% | +62.74% |
| 60.0 | +91.84% | +97.65% | +91.64% | +83.70% | +74.01% |

The volumetric row is flat at machine precision, as it must be. Every water-drive row
drifts. At the base case the estimate moves 6.96 percentage points of true G between the
first fifth of the history and the whole of it, always upward, while each individual fit
looks like a clean straight line.

Two honest qualifications. The drift is not always upward: for the two strongest
aquifers the estimate peaks and then falls back as the aquifer itself depletes and its
support fades, so a stabilising estimate is not evidence that the estimate is right.
And the sign of the drift here is specific to a reservoir whose support weakens over
time; a constant-pressure aquifer would drift differently.

The practical reading is the one a reservoir engineer can act on: a p/Z estimate that
moves materially as history accumulates, while each fit remains visually straight, is
evidence that the straight line is not the right model. A stable estimate is weaker
evidence than it looks.

### Attacking the demonstration

A counterexample that works only at one contrived setting is not a counterexample. Four
checks, all pre-registered in `protocol.md` before the run.

**Exact reduction at zero aquifer productivity (A1, A2).** With the productivity index
set to exactly zero, all six generated series — true pressure, deviation factor,
cumulative gas, step residual, water influx and cumulative water — are **bitwise
identical** to `simulate_volumetric_depletion` on the same schedule. Not close: equal.
The volumetric fit to that history returns R-squared = 1.0 and a gas in place in error by
−9.6e-14 relative, against a pre-registered threshold of 1e-9. The generator therefore
contains the volumetric case exactly, and the bias reported above is the aquifer and
nothing else. (`FetkovichAquifer` refuses a zero productivity index, correctly, so the
inert member of the sweep is supplied as a four-field duck-typed object, which the
generator's documented contract accepts.)

**The generator's own numerical error (A3).** The worst coupled-solve residual over every
run in the case is 3.43e-9 psia of p/Z. The comparison the acceptance criterion makes is
against the smallest *per-exhibit largest residual*, which is the 24.6 psia largest residual
of the base-case fit, and the solver residual is 9.9 orders of magnitude below it. The
smallest such per-exhibit figure anywhere in this report is the 4.0 psia of the post-review
correlation-mismatch check below, still 9.1 orders above the solver residual.
**[SUPERSEDED] The first version of this paragraph called 4.0 psia "the smallest misfit
quoted anywhere in this report at all".** It is not: the residual table below quotes
individual residuals down to +0.24 psia at 1.50 years. Even against that figure the solver
residual is 7.9 orders of magnitude below, so no acceptance outcome changes. A reader can
separate the physics from the generator's arithmetic without taking anything on trust.

**Time discretisation (A4).** A small root-finder residual is not the same as a converged
time integration, so the base case and the strongest aquifer were rerun at dt, dt/2, dt/4
and dt/8. The recovered gas-in-place error changes by 7.7e-7 (base case) and 2.0e-5
(strongest aquifer) across that refinement, against a pre-registered threshold of 1e-3.
Terminal water influx converges at second order, as the scheme's documentation says it
should. The bias is resolved in time and is not a timestep artefact.

**Independent oracle: the balance with influx known (A5).** Rearranging the generator's
own balance gives, at any single observation,

    G = (G_p*B_g(p) − (W_e − B_w*W_p)*5.614583) / (B_g(p) − B_g(p_i))

computed in the case script from the reported series, using no function from
`material_balance` and no regression. Over every observation of every aquifer strength
its worst relative error is 3.6e-11, against a pre-registered threshold of 1e-8.

What that does and does not establish, stated more narrowly than the first version of
this report stated it. Oracle 2 is an algebraic rearrangement of the same governing
equation the generator solves, evaluated on the generator's own reported influx. It
therefore tests the *solve* — that the implicit coupled step converges to a state
satisfying the balance — and it is independent of the estimator under test. It does not
test the *formulation*: an equation mis-transcribed identically in the generator and in
the oracle would still close to 3.6e-11. The earlier claim that it shows "the histories
are not artefacts of a mis-transcribed equation" is withdrawn; closing that gap needs a
reimplementation written from the physics rather than from this code, which this case
does not contain. **[SUPERSEDED] The first version of this paragraph presented a
separately implemented tank as though it closed that gap, and quoted its digits.** What
actually exists is a *reported comparison that is not reproducible from this repository*: a
separately written tank — own bisection, own Fetkovich increment, own OLS, borrowing nothing
from `reservoir_lab` except `z_factor` — was reported to reproduce the sweep to five or six
significant figures. No script, no output, no digest, no command and no log for it exists
anywhere in this repository, so none of its figures can be checked from here and the quoted
digits are withdrawn. The comparison is recorded as a claim about work done outside the
repository, not as evidence this repository supplies. The case's own evidence for the
formulation stops at the solve. (Separately, the directory
`artifacts/A4_misleading_fit_counterexample/referee-run/` is unrelated to that tank: it is a
re-execution of this case's own `run.py`, not an independent implementation, and the shared
word "referee" in its name is the only connection.)

The second consequence is the one that matters for the decision, and it needs its own
caveat: once the influx is known *exactly*, on *noise-free* data, the gas in place is
recovered essentially exactly. That is a statement about identifiability, and its conditions
are broader than the first version of this report stated. Oracle 2 supplies not only the
exact influx but also the exact pressures, the exact deviation factors, the exact `B_w` and
the exact `W_p`. So what it establishes is: **G is recoverable when the influx *and* the
pressures *and* the PVT are all exact** — not that the influx is the only missing piece.
Nor is supplying the influx the only route to G on this data. A direct least-squares
minimisation over the two physical parameters (G, J) against the same base-case history, with
no influx observation supplied at all, returns G within 1.0e-11 relative of the truth and
J = 2.0000, at a residual of 1.8e-9 psia of p/Z — so the field-relevant obstacle is
measurement error, not identifiability. (That minimisation was run during the claims-audit
correction pass on the committed generator; it is not pre-registered, not in
`results/summary.json`, and the shipped run is unchanged.) Either way 3.6e-11 is not an
attainable field accuracy; any real influx estimate carries an error that would dominate the
recovered gas in place completely.

### Could anyone have told from the data alone?

Base case, noise-free residuals of the volumetric straight-line fit, in psia of p/Z
against cumulative production (every sixth observation and the last):

| years | G_p / G_true | observed p/Z | fitted p/Z | residual |
|---|---|---|---|---|
| 0.00 | 0.0000 | 4344.20 | 4319.56 | +24.63 |
| 1.50 | 0.0688 | 4055.83 | 4055.59 | +0.24 |
| 3.00 | 0.1375 | 3782.81 | 3791.63 | −8.82 |
| 4.50 | 0.2062 | 3518.97 | 3527.66 | −8.69 |
| 6.00 | 0.2750 | 3259.74 | 3263.69 | −3.95 |
| 7.50 | 0.3437 | 3001.48 | 2999.73 | +1.76 |
| 9.00 | 0.4125 | 2741.13 | 2735.76 | +5.37 |
| 10.50 | 0.4812 | 2475.92 | 2471.79 | +4.13 |
| 12.00 | 0.5500 | 2203.23 | 2207.82 | −4.59 |

There is structure. The residuals are not scattered: they sweep down, back up and down
again, with an RMS of 7.38 psia and a largest excursion of 24.63 psia, which is 0.57
percent of the initial p/Z. That excursion sits at G_p = 0, where the fitted line
undershoots the measured initial p/Z by 24.63 psia.

The pre-registered detector is a t-test of the quadratic coefficient of
`p/Z = a + b*u + c*u^2`, with `u = G_p/G_true`, at 95 percent and n − 3 = 46 degrees of
freedom. On the noise-free data the statistic is 4.51 against a critical value of 2.01.
Adding independent Gaussian error to the reported pressures, 400 realisations per level
from one declared seed:

| pressure sigma, psi | detection rate, water drive | detection rate, volumetric null |
|---|---|---|
| 1 | 1.0000 | 0.0675 |
| 2 | 1.0000 | 0.0675 |
| 5 | 0.9775 | 0.0675 |
| 10 | 0.5550 | 0.0675 |
| 20 | 0.2100 | 0.0675 |
| 40 | 0.0850 | 0.0675 |
| 80 | 0.0725 | 0.0675 |

Rates are quoted exactly: at 400 replicates every rate is a multiple of 0.0025, and the
first version of this report rounded two cells of this table in opposite directions.

The closed form the run computes, `sigma* = |c| / (t_crit * sqrt(inverse_gram_cc))`,
where `inverse_gram_cc` is the (2, 2) element of the *inverse* Gram matrix as named in
`run.py`, is 14.21 psia of p/Z error, which the run converts to 12.49 psi of pressure error
through the unweighted mean deviation factor over the history.

**[SUPERSEDED] The first version of this report called that the half-power point and said
it was consistent with the Monte Carlo. It is not the half-power point.** The consistency
with the Monte Carlo was asserted and never computed.

**[SUPERSEDED] The replacement reading — "the noise level at which the *expected* statistic
equals the critical value", with a random denominator said to push the power below one half
— is also wrong, and the shipped `summary.json` keys still carry it in their names.** Both
halves of it fail. Here is what the quantity is, taken from its derivation rather than from
the key name.

The statistic is `t = c_hat / (s * sqrt(I_cc))`, where `s` is the residual standard
deviation *estimated from the fit* and `I_cc` is that inverse-Gram element. The standard
deviation of the coefficient estimator itself is `sd(c_hat) = sigma * sqrt(I_cc)` for a true
ordinate error `sigma`. Setting `sigma = |c| / (t_crit * sqrt(I_cc))` therefore makes
`|c| / sd(c_hat) = t_crit` exactly. That ratio is the **noncentrality parameter** of the
test, not the expectation of the statistic: `E[t]` differs from the noncentrality because
`s` sits in the denominator and is itself estimated. Verified against the case's own code at
the base-case design: `|c| / (sigma* sqrt(I_cc)) = 2.0128955989`, equal to `t_crit` to eleven
figures. So **`sigma*` is the noise level at which the noncentrality parameter equals the
critical value.**

The reason the power at `sigma*` is below one half is also not the random denominator. For
an exactly quadratic mean, a two-sided t-test on 46 degrees of freedom at a noncentrality of
`t_crit` has power 0.504 — just *above* one half, not below it — so that mechanism carries a
+0.4 percentage-point effect of the opposite sign. The actual cause is a deterministic
lack-of-fit floor: the true p/Z curve is not a quadratic, so the noise-free quadratic fit
already leaves a residual sum of squares of 1847.69 psia^2 on 46 degrees of freedom, i.e.
`s_0 = 6.34 psia` with no measurement error present at all. That floor inflates the estimated
residual variance from `sigma^2` to about `sigma^2 + s_0^2`, which deflates the effective
noncentrality at `sigma*` from 2.013 to 1.838, 0.913 times the critical value. The
noncentral-t power at 1.838 is 0.436, against the 0.432 E9 actually measured at 12.5 psi —
inside one Monte-Carlo standard error of it. The lack-of-fit explanation accounts for the
whole of the roughly seven-point shortfall; the random denominator accounts for none of it,
in the wrong direction.

Provenance of the three checks in the last two paragraphs: `|c| / (sigma* sqrt(I_cc))` and
`s_0` were computed during the claims-audit correction pass by calling the case's own
`quadratic_fit` on the case's own base-case design; the two power values come from the
noncentral-t distribution evaluated outside this repository, which carries no such
dependency. They are diagnostics of an existing number, not new results: none is
pre-registered, none is in `results/summary.json`, and the shipped run is unchanged.

E9 measures the power curve directly — 4000 replicates per level on a seed different
from the pre-registered sweep's:

| pressure sigma, psi | 8 | 9 | 10 | 11 | 11.5 | 12 | 12.5 | 13 | 14 | 16 |
|---|---|---|---|---|---|---|---|---|---|---|
| detection rate | 0.754 | 0.664 | 0.590 | 0.516 | 0.481 | 0.456 | 0.432 | 0.406 | 0.361 | 0.297 |

Two things have to be kept apart here: the **empirical crossing** and the **uncertainty in
that crossing**.

The crossing is an interpolation, not a measurement. Rates of 0.51625 at 11.0 psi and
0.48075 at 11.5 psi give a linear crossing of one half at **11.2 psi**. No replicate was run
at 11.2 psi; the two bracketing rates were, and the crossing is read off the straight line
between them.

The uncertainty attached to it is Monte-Carlo only. The binomial standard error on a rate
near one half at 4000 replicates is 0.0079, and the curve falls at about 0.071 per psi there.
**[SUPERSEDED] The first version of this paragraph added the two levels' contributions in
quadrature, giving 0.16 psi.** That is the wrong operation: E9 resets the same seed at every
level and `random.gauss` draws a standard normal before scaling, so the ten levels are one
4000-draw set rescaled ten ways — the scaled draws agree to the last bit — and the two
bracketing levels agree replicate by replicate on 96.5 percent of their reject/accept
decisions when re-run from the committed seed. Their errors move together, so the crossing
inherits about one level's worth, 0.0079 / 0.071 = 0.11 psi, not two levels' worth added in
quadrature. The stated plus or minus 0.2 psi is conservative either way and no reported number
moves; the derivation is corrected because the quadrature reasoning applied to a wider grid
would understate the common-mode error badly.

That Monte-Carlo figure is also the *only* uncertainty it covers. It says nothing about
design dependence, and E9 inherits the single-draw-set limitation this report criticises in
the pre-registered E6 sweep — the same sentence belongs on both: the ten levels are
rescalings of one 4000-draw set, not ten independent experiments. This report was candid
about that for E6 and silent about it for E9, and that asymmetry is corrected here.

At the closed-form 12.5 psi the measured power is 0.432, not 0.5. The closed form overstates
the half-power sigma by about 11 percent, and the correction runs against this report's own
conclusion: the curvature is slightly harder to detect than the first version claimed, not
easier.

Both controls pass (A9, A10). At 1 psi the detector finds the curvature in every one of
400 realisations, so it can see the positive case. On the volumetric null history, where
the p/Z line is exactly straight, it fires at 0.0675 against a nominal 0.05, within the
pre-registered band. Three qualifications belong with that number.

The null rate is identical at every noise level because the null p/Z series is exactly
linear, so scaling the noise scales the fitted coefficient and its standard error equally
and the t statistic is invariant. That invariance is expected behaviour and not a defect —
but with one seed reset identically at every level, it is also the only thing that could
have happened, because the seven levels are rescalings of one draw set rather than seven
independent experiments.

0.0675 is a high draw of the declared seed, not the detector's size. Over the eight seeds
of E9 at sigma = 5 psi the null rate runs from 0.0425 to 0.0675 with a mean of 0.0528,
and pooled over 20000 replicates on a fresh seed it is 0.0473. The detector's actual size
is close to its nominal 0.05; the pre-registered sweep happened to draw the top of the
range.

The A9 band itself is loose. It was declared as [0.01, 0.12] around a nominal 0.05 with
no derivation. At 400 replicates the binomial standard error at p = 0.05 is 0.0109, so a
three-standard-error band is [0.017, 0.083]; the declared upper limit sits about 6.4
standard errors above nominal, and a detector with a false-positive rate more than twice
nominal would have passed A9 unnoticed. The observed 0.0675 is inside the derived band as
well as the declared one, so the criterion's looseness does not change this case's
outcome, but A9 as written is a weak gate. The threshold has not been changed after the
fact; it is recorded as declared and its weakness is recorded with it.

**So the answer to "could anyone have told", on this design — 49 quarterly observations
over twelve years at J = 2.0, tested by a quadratic t-test — is: only at a pressure accuracy
of order ten psi, this detector's power crossing one half at 11.2 psi, and the relevant
accuracy is not the gauge's.** The design qualifier is load-bearing and is not decoration:
the crossing is a property of the horizon, the cadence, the aquifer strength and the
lack-of-fit floor as much as of the pressure error, and a reader with 24 monthly
observations or a stronger aquifer gets a different number. A quartz gauge resolves well
below 1 psi, but the ordinate of a p/Z
plot is a *volume-averaged reservoir pressure*, and its error is dominated by build-up
extrapolation, datum correction and incomplete stabilisation. This report takes 10 to 50
psi as the realistic band for that quantity on a mature field. That band is the single
load-bearing premise of the conclusion and it deserves its source stated exactly: it is
the author's engineering judgement, not a retrieved figure. What the repository's
evidence file supports is the order of magnitude and the mechanism, not the band —
`docs/evidence/matbal.md` records Dake's gas gradient of 0.0465 to 0.117 psi/ft, which
over a few hundred feet of datum error is "tens of psi, comparable to the signal in early
depletion", and records that a build-up that has not reached the boundary-dominated
plateau returns a pressure below the true average by an amount that varies well by well.
Both of those put the error in the tens of psi; neither fixes the band at 10 to 50. If
the true band is 1 to 5 psi the conclusion reverses, and that reversal condition is
listed below.

Over most of the band as taken, the curvature this case demonstrates is not recoverable
from the p/Z plot, while the gas-in-place error remains 12.5 percent.

Three limits on that conclusion, stated plainly. It is conditional on this detector, on
49 quarterly observations, and on independent Gaussian pressure error; a correlated or
systematically biased error behaves differently and was not tested. The sweep forms the
noisy ordinate by dividing the noisy pressure by the *true* deviation factor rather than
by Z re-evaluated at the measured pressure, which is what an engineer would do; E9 tested
both and the second raises the detection rate at every level (0.5550 to 0.6500 at 10 psi,
0.2100 to 0.2350 at 20 psi, 0.0850 to 0.1000 at 40 psi), so the pre-registered sweep
understates detectability slightly. And the intercept mismatch noted above — the fitted
line missing the measured initial p/Z by 0.57 percent — is a second, different diagnostic
that this case did **not** pre-register a test for. It is recorded here as an observation
and as a hypothesis for a follow-up case with its own pre-registered threshold. It is not
claimed as a result.

### The detector is not a clean aquifer diagnostic

E9, post-review and not pre-registered. The whole exhibit is a p/Z ordinate, so it
carries whatever error the deviation-factor correlation carries. **[SUPERSEDED] The first
version of this paragraph attributed the correlation-versus-reference percentages to
`scripts/check.py`.** That file is the repository's test runner and reports no such figures;
a reader who ran it to reproduce them would get nothing. The figures belong to case A2's
comparison of DAK and Hall-Yarborough against the NIST reference equations of state — DAK up
to 1.70 percent for pure methane, Hall-Yarborough up to 1.64 percent, both mostly in the same
direction, so the spread between two correlations understates the error of either against
nature. A2 reads a NIST reference extract that this repository does not redistribute, so
**those two percentages cannot be reproduced from this checkout**; they are quoted as
background and nothing in this case's results depends on them. What this case did measure is
the last sentence: within this case's pressure window the two correlations differ by at most
0.31 percent.

Two different questions follow, with two different answers.

The gas-in-place bias is insensitive to the correlation. A constant multiplicative error
in Z scales the whole p/Z ordinate and leaves the x-intercept untouched; only the
pressure-dependence of the error can move it. Reading a DAK-generated history with
Hall-Yarborough moves the base-case bias from +12.50 to +12.22 percent, and generating
and fitting consistently under Hall-Yarborough gives +12.54 percent. The headline result
survives the correlation choice to within 0.3 percentage points.

The curvature detector does not survive it. On the *volumetric* history — a strictly
straight p/Z line, no aquifer at all — reading Z from the wrong correlation produces a
largest residual of 4.0 psia and a curvature statistic of −9.05 against a critical value
of 2.01. That is twice the water drive's own noise-free statistic of +4.51, in the
opposite direction. A systematic correlation error is not detected as a correlation error;
it is detected as curvature. So the detector's false-positive rate of about 0.05 is
conditional on the analyst using exactly the correlation that generated the history, a
condition no field analysis can meet. Nothing in this paragraph changes the bias figures;
it changes how much weight the detectability numbers can carry, and the sign of the
correlation artefact is at least opposite to the aquifer's, which is the one piece of
luck in it.

### The conditional synthetic pressure reconstruction a wrong model passes

Calibrating on the first 30 observations (7.25 years) and reconstructing the remaining 19:

| quantity | value |
|---|---|
| calibration R-squared | 0.999641 |
| calibration gas-in-place error | +11.30% |
| reconstructed-pressure RMSE | 15.7 psi |
| as a fraction of initial pressure | 0.393% |
| borrowed PLAN section 12 demonstration gate | 1% |
| below that gate | yes |

**[SUPERSEDED] The first version of this report called this a chronological holdout and
nothing more.** It is a *conditional synthetic pressure reconstruction*, and the condition
has to be stated. `run.py:625` forms the predicted pressure as `pred * z_factors[i]`, where
`z_factors[i]` is the noise-free *true* deviation factor of the held-out state, evaluated at
the true future pressure. Future truth therefore enters the predictor. An analyst holding
only the calibration data cannot know Z at a pressure that has not happened yet; the
self-consistent alternative is to solve `p/Z(p) = predicted` for `p` using the same
correlation. The chronological discipline is real — no tuning of any kind touches the
held-out points — and the calculation has deliberately **not** been changed to improve the
claim. Only the label and the surrounding description are corrected, and the 15.7 psi is the
number the committed run produced.

So what the row establishes is a conditional reconstruction of a synthetic pressure series,
not a field-realisable forecast, and not physical interpretation or decision adequacy.

The gate it is scored against also needs its scope stated. `PLAN.md:289` scopes the 1 percent
row by its own words to "the delivered small-noise demonstration", and `PLAN.md:282` states
that these are proposed project gates, not regulatory requirements or universal engineering
tolerances, to be scaled and justified for each case. A4 is a noise-free structural
counterexample and borrows that row without rescaling it. Being below it is a project
demonstration result; it is not evidence of general reservoir-interpretation adequacy and not
evidence of development-decision adequacy. (Of the two halves of that PLAN row, only the
holdout half is pre-registered for this case, at `protocol.md:233`; the gas-in-place half is
not.)

This is still the most uncomfortable number in the case. A genuine chronological split, with
no tuning on the held-out points, is cleared comfortably by a model whose gas in place is 11.3
percent wrong and whose remaining gas in place is 16.9 percent wrong. The reason is
structural: over a 4.75-year extrapolation the wrong model's error stays small, while the
x-intercept is an extrapolation far beyond the data where the same curvature integrates into
a large displacement. A holdout tests the reconstruction over the horizon it covers. It does
not test a quantity that lives outside the data.

### The observation that would have given it away

Rerunning the base case with a declared 30 percent of the incremental influx produced at
surface — a bookkeeping fraction, not a relative-permeability calculation — the fit is
still excellent (R-squared = 0.999938, gas in place +8.41 percent) while the water record
says plainly what is happening:

| years | cumulative water, STB | water-gas ratio, STB/MMscf |
|---|---|---|
| 3.0 | 214018 | 15.6 |
| 6.0 | 767344 | 27.9 |
| 9.0 | 1571417 | 38.1 |
| 12.0 | 2576327 | 46.8 |

A rising water-gas ratio of this size is not subtle, and it is visible from the third
year, long before the p/Z drift has accumulated. That cuts the other way too, and the
prior work is the reason to say so: `docs/evidence/matbal.md` records from Pletcher (SPE
75354) an aquifer-supported well making only 1.5 STB/MMscf after ten years, an order of
magnitude below the ratios in this table, with the comment that a real reservoir with
saturation gradients would likely make even less. **A dry gas well is not evidence of a
closed tank, and neither is a p/Z estimate that looks stable.** The ratios above are
indicative of order of magnitude only, because the produced-water fraction is declared
rather than computed, and a real reservoir could easily produce the same influx with a water
record far less obvious than this one.

Three quantities are involved here and they are not interchangeable. Cumulative produced
water `W_p` is a volume at standard conditions. Its reservoir-volume equivalent is
`W_p * B_w`. Total influx `W_e` is a third quantity, reached from `W_p * B_w` only through an
aquifer model or a closed balance. In this variant `W_p * B_w` is 30 percent of `W_e` by
declaration (`run.py:649`), so the produced record understates the influx by a factor of 3.33
and bounds it from below rather than measuring it. A Cole or pot-aquifer plot does not change
that arithmetic: it is a re-plot of the same pressure and production history the p/Z fit
already uses, so it is a transformation and not an additional independent observation, and it
becomes informative only to the extent that `W_p` is separately metered. Neither plot was run
in this case.

## What this case does not establish

- **It is not field validation.** Both the generator and the estimator are models. A
  known-answer study with a synthetic generator establishes the behaviour of an
  estimator under a stated structural violation. It says nothing about how often that
  violation occurs in any real field, or about the size of the bias in one.
- **The numbers are not general.** The +12.5 percent at the base case is a property of
  these declared aquifer parameters, this offtake schedule and this twelve-year window.
  Changing W_i, c_t, the rate or the horizon changes it.
- **Trapped gas is not modelled, and what that omission costs is an argument rather than a
  result.** Trapped gas behind the advancing water front would reduce the true *recoverable*
  gas below the true remaining gas *in place*, while the p/Z intercept sits above the true gas
  in place. Those are two different quantities and the comparison between them was not run
  here. The argument that the two errors compound is plausible and untested in this case; it
  is recorded as an argument, not as a measured direction, and the recoverable-versus-in-place
  distinction is the part that is certain.
- **Excluded mechanisms.** Rock and connate-water expansion, retrograde condensation,
  gas dissolved in water, and any areal or vertical pressure gradient within the tank.
  A geopressured reservoir produces a superficially similar p/Z curvature from a
  completely different mechanism and is not distinguished here.
- **The average reservoir pressure is assumed to exist and to be unbiased.** This is the
  first thing a reservoir engineer will object to. **[SUPERSEDED] The first version of this
  bullet asserted a direction — that surviving-well sampling makes a real reservoir "worse,
  not better".** That sign is not established by anything in this case and the opposite is
  available on ordinary reservoir physics. The argument for the stated direction is that the
  wells surviving to be surveyed are the ones the water has not reached, biasing the sample
  toward the un-swept, higher-pressure part of the tank, which would flatten the p/Z line
  further and move the x-intercept further right. The counter-argument is that the wells shut
  in long enough to give a usable build-up are not a random sample either, and can be biased
  the other way. **The tank model in this case has no areal gradient at all, so nothing here
  can decide between them.** It is recorded as an untested mechanism, not as a direction, and
  the "the figures are conservative" framing that rested on it is withdrawn.
- **The Fetkovich aquifer is itself a model, and its smoothness is assumed.** It assumes
  the aquifer has reached pseudosteady state, starts at equilibrium with the reservoir,
  and is represented by two numbers. The mechanism paragraph in the decision memo turns
  on the influx entering "slowly and smoothly" — that smoothness is a consequence of the
  model choice, not something this case demonstrates. A transient aquifer in its early
  period is precisely where Dake's warning bites hardest, and van Everdingen-Hurst is not
  implemented in this library and was not tested.
- **The history is unrealistically clean.** Constant offtake for twelve years, no
  shut-ins, no rate or well-count changes, no plateau, 49 evenly spaced quarterly points,
  no gaps and no outliers. The protocol's "no observation is excluded" rule is a strength
  for pre-registration and a limitation for realism. It cuts both ways and the report
  should say so: a facilities-constrained plateau carries less curvature information and
  would make the aquifer harder to detect, while real rate variation imprints pressure
  transients that are themselves a diagnostic and would make it easier.
- **Detectability is conditional**, as set out above: one detector, one sampling cadence,
  independent Gaussian error only, one seed in the pre-registered sweep, the deviation
  factor held at truth in the ordinate, and — the sharpest of these — a false-positive
  rate that is only valid if the analyst's Z correlation is the one that generated the
  data.
- **Pre-registration rests on the author's word, and A4's prospective ordering remains
  unverified.** **[SUPERSEDED] The stated reason — that the `cases/` tree is untracked in
  git — is stale; the tree is tracked.** The conclusion survives for two different reasons.
  This case's `run.py` declares no inputs in its run record, so nothing machine-written pins
  `protocol.md` to the runs; and every A4 file entered git in a single commit, so no commit
  timestamp separates the protocol from the runs either. `protocol.md`'s own modification
  time is later than run-001's and run-002's because of the disclosed amendment. The change
  log records what was amended and why, and the claim that run-001 and run-002 are
  byte-identical is checkable from the retained artifacts; the ordering of protocol against
  run is not. For contrast, A2 and A3 do declare `protocol.md` as an input and pin it by
  SHA-256 inside a record the run itself wrote; that establishes internal content linkage as
  recorded, and it is **not** an independent trusted timestamp and **not** proof against
  retrospective construction. The shipped `results/run_record.json` still carries the stale
  reason in its limitations list, and is deliberately left unedited as a contemporaneous
  machine-written record.
- **No human peer review took place, in the original case or in any revision.** The author
  performed the numerical and interpretation passes separately, which is a working practice
  and not peer review. The revision pass that produced this version was conducted under a
  different role by the same author, not by a different person; `AGENTS.md:46` states the
  rule that different role names do not create independent expertise or independent evidence.
  **[SUPERSEDED] That pass was described here as "external" and "independent"; both words are
  withdrawn.** It found the errors listed at the end of this report and did not re-derive the
  physics. The later claims audit has the same status: a separate automated review pass is
  not human peer review.

## What would change the conclusion

- A water-drive history in which the volumetric fit's R-squared fell in step with the
  bias. That would mean the straight line carries its own warning and no counterexample
  exists. It did not happen anywhere in this sweep, but the sweep varies one parameter.
- A demonstration that realistic average-reservoir-pressure uncertainty is materially
  better than 10 psi on a mature field. The detectability conclusion is a statement
  about that number, and it would move directly. The 10 to 50 psi band is this report's
  weakest premise: it is the author's judgement, sourced only to the order of magnitude
  of the datum and build-up effects recorded in `docs/evidence/matbal.md`.
- A demonstration that a realistic deviation-factor treatment leaves the curvature
  detector's size near nominal. As E9 shows, a correlation mismatch alone fires the
  detector harder than the aquifer does, which limits the detectability half of this
  case more than any other single finding in it.
- Aquifer parameters under which the recovered-G error stays below the 1 percent gate
  `PLAN.md:289` proposes for the delivered small-noise demonstration. **[SUPERSEDED] The
  first version of this bullet listed J = 0.05 at 0.32 percent and J = 0.2 at 1.26 percent
  as two such rows.** +1.26 percent is *above* a 1 percent gate, not inside it. Only
  J = 0.05, at +0.32 percent, is below it, and the conclusion is about conditions on one row
  rather than two. The gate is also borrowed: `PLAN.md:289` scopes it to the delivered
  small-noise demonstration and `PLAN.md:282` calls these proposed project gates, not
  regulatory requirements or universal engineering tolerances, to be scaled and justified per
  case. This noise-free structural counterexample never rescaled it, and clearing it would be
  a project demonstration result rather than evidence of reservoir-interpretation or
  development-decision adequacy. Note also that J = 0.05 and J = 0.2 are the two members of
  the sweep with aquifer time constants of 986 and 247 years against a 4383-day horizon —
  precisely where the Fetkovich model's pseudosteady assumption is least defensible
  (`docs/evidence/aquifer.md:586`), so they are the rows a transient aquifer would be most
  likely to move.

## Plus / minus / recommendation

**Plus.** The counterexample is established and survives its own attack. A volumetric
p/Z fit to an aquifer-supported history returns R-squared at or above 0.999 while
overestimating gas in place by 12.5 to 33.6 percent, and by 27.8 to 74.7 percent on
remaining gas in place. The bias is 50 to 88 times the fit's own reported standard error.
The demonstration reduces bitwise to the volumetric case at zero aquifer productivity,
its generator's numerical error is 9.9 orders of magnitude below the effect, the bias is
converged in time to 2e-5, and it is insensitive to the deviation-factor correlation to
within 0.3 percentage points. An estimator-free balance with the influx, the pressures and
the PVT all supplied exactly recovers gas in place to 3.6e-11 on noise-free data. A
pre-registered chronological split — a conditional synthetic pressure reconstruction, on the
terms set out above — is cleared by the wrong model at 0.39 percent of initial pressure
against a borrowed 1 percent demonstration gate. The magnitude agrees with Pletcher's
published simulation and field case to within the decade.

**Minus.** Everything is synthetic and one-dimensional in its parameter variation: only
the aquifer productivity index is swept, with pore volume, compressibility, schedule and
horizon fixed, so the reported biases are illustrative magnitudes rather than a mapped
surface. Trapped gas is absent and the average pressure is assumed unbiased; both are
untested omissions whose direction this case cannot establish, and the earlier claim that
they make the case conservative is withdrawn. The detectability half is the weaker half: it
rests on one pre-registered detector, one sampling design, an independent-Gaussian error
model, a single seed in the pre-registered sweep — and, as the claims audit found, a single
draw set behind the E9 power curve that was introduced to correct it — an uncited
10-to-50-psi premise, and a false-positive rate that E9 shows is conditional on the analyst
using the same deviation-factor correlation as the generator, a condition no field analysis
meets. The first version of this report mislabelled the closed-form sigma as a half-power
point and asserted a Monte-Carlo consistency it had not computed; the revision that replaced
that label substituted a second wrong one, and the correct reading, derived rather than
renamed, is above. The separately implemented tank that was presented as an independent
check of the formulation is a reported comparison not reproducible from this repository, and
its digits are withdrawn.

**Recommendation.** The single most useful next measurement is a **metered water-production
record**. That is the new observation; a Cole or pot-aquifer plot is a transformation of the
history already in hand and adds information only once water is measured, and neither plot
was run here. Supply the influx, the pressures and the PVT exactly, on noise-free
observations, and the same data return gas in place to 3.6e-11 relative — an identifiability
statement under those exactness assumptions, and not an attainable accuracy. A field influx
estimate carries an error that would dominate the recovered gas in place entirely, and no
part of this case quantifies how well an influx estimate can be made. Note also that the
conversion from a water record to an influx is two steps, not one: `W_p` at standard
conditions, then `W_p * B_w` in reservoir volume, then `W_e` only through an aquifer model or
a closed balance. The next step for the workbench is the companion diagnostic case:
pre-register a test of the fitted-versus-measured initial p/Z mismatch and of the Cole plot's
power against the same noise sweep, with the deviation-factor correlation mismatched between
generator and analyst so that the false-positive rate quoted is one an engineer could
actually rely on, and with an independent seed per noise level so the power curve is not one
draw set rescaled.

## What the review pass changed

A separate review pass — a different role, the same author, not a different person and not
peer review — checked every number in the first version of this report against the run
output and attacked the claims. What follows is the audit trail; the corrections themselves
are made in place above. A second, later set of corrections came from a repository-wide
claims audit and is listed after this one.

Numbers that did not reproduce:

- The bias/standard-error cell at J = 20 read 63. The run gives 62.469. Corrected to 62.
  The 50-to-88 range across the sweep is unaffected.
- The detection rate at sigma = 80 psi read 0.072 while the null column rounded 0.0675 up
  to 0.068 in the same table. The run gives 0.0725 exactly. The whole table is now quoted
  exactly.
- The closed-form 12.5 psi was called the half-power point and asserted to be consistent
  with the Monte Carlo. It is not the half-power point, the consistency check had never been
  run, and the measured crossing is 11.2 psi. E9 was added to the run to measure it. The
  replacement reading recorded at the time — "the level at which the expected statistic
  equals the critical value" — was itself wrong and was corrected later by the claims audit;
  see below.

Claims weakened or withdrawn:

- Oracle 2 was said to show the histories are not artefacts of a mis-transcribed
  equation. Withdrawn: it tests the solve, not the formulation.
- The 4e-11 known-influx figure was used as the payoff of the recommendation without its
  conditions. It now carries them wherever it appears.
- The case is now positioned against Pletcher and Dake rather than presented on its own.
- The 10-to-50-psi band is now labelled as the author's judgement with the evidence file
  cited for the order of magnitude only.
- The detectability figure was quoted as "about 10 psi" in one place and 12.5 psi in
  another. One number now, measured: 11.2 psi.

Limitations added: average-pressure sampling bias, recorded at the time as having the same
sign as the demonstrated effect and since downgraded to an untested mechanism of undecided
sign; the unrealistically clean production history; the assumed smoothness of a
pseudosteady aquifer starting at equilibrium; the deviation factor held at truth in the
noise model; one seed behind the whole pre-registered noise sweep; the Z-correlation
confound in the detector; pre-registration resting on the author's word, for a reason since
restated.

One review point is not accepted. The pass read the run's `ESTABLISHED` verdict as a
novelty claim that needed positioning against prior work. The citation gap was real and
is fixed above, but the verdict string is produced by `verdict()` in `run.py` from the
outcomes of A1 to A10 and means only that the pre-registered criteria for a counterexample
were met at these settings. The case does not claim priority anywhere: the words "new",
"novel" and "first" do not appear in it in that sense, and the protocol's decision rules
define `ESTABLISHED`, `INCONCLUSIVE` and `INVALID` explicitly in terms of those criteria.

## What the claims audit changed

A later repository-wide claims audit re-read every sentence in this case against the run
output and against `PLAN.md`. It was, again, a separate review pass and not human peer
review. The corrections are marked `[SUPERSEDED]` in place above; nothing was deleted, no
`summary.json` or `run_record.json` was edited, no threshold was relaxed and no number was
re-rounded. The full ledger is `docs/release/disposition_ledger.csv`.

Arithmetic and scope:

- +1.26 percent was stated as inside a 1 percent gate, in this report and in the decision
  memo. It is above it. Only the +0.32 percent row is below.
- The borrowed PLAN gate is now cited with its own scope: it is a project demonstration
  gate for the delivered small-noise demonstration, not a general adequacy criterion.
- `fit_pz_depletion` was called a one-parameter fit in the decision memo. It fits two
  parameters and `G = -a/b` is derived from both. Practical, noise-limited ambiguity is now
  separated from structural non-identifiability, with a measured profile behind the
  distinction.
- The smallest-misfit sentence in the A3 discussion was false under a plain reading; the
  definition the code applies is now stated.

Labels:

- The chronological holdout is now labelled a conditional synthetic pressure
  reconstruction, because the predictor multiplies by the held-out state's own synthetic
  deviation factor. The calculation is unchanged.
- The closed-form sigma is now interpreted from its derivation — the noise level at which
  the noncentrality parameter equals the critical value — and the sub-half power is
  attributed to the quadratic lack-of-fit floor rather than to a random denominator.
- The separately implemented tank is labelled a reported comparison not reproducible from
  this repository, and its digits are withdrawn.
- "Independent" and "external" are withdrawn from every description of a review pass.

Directions withdrawn for want of evidence:

- Average-pressure sampling bias: sign undecided, tank has no areal gradient.
- Trapped gas: a recoverable-versus-in-place distinction, not a measured direction.
- Drift diagnostic: material movement in either direction, since Pletcher's runs the other
  way.
- Interval methods on the fitted model: no direction claimed, since none was run here.

Quantities kept apart:

- `W_p`, `W_p * B_w` and `W_e` are three quantities with two conversions between them; a
  Cole or pot-aquifer plot is a transformation of the existing history, not an additional
  observation.
- Inventory in place, recoverable gas and reserves are three different things and none is
  presented as another.

Provenance restated:

- A4's prospective ordering is unverified, for the correct reason. A2 and A3 have protocol
  hashes inside their own run records, which is internal content linkage as recorded, not
  an independent trusted timestamp.

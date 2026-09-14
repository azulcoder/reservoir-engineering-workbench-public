# Case A3 protocol: what dominates the uncertainty in a gas-in-place estimate

Stage A, PLAN.md section 5. Backlog task 07, "Analyse pressure/Z error and short-history
uncertainty". Written before the experiments were run; see the pre-registration note at the
end for exactly what was and was not fixed in advance, and the change log for amendments.

## 1. Engineering question and decision

A dry-gas field is being appraised from shut-in pressure surveys and metered cumulative
production. The dynamic gas in place comes from the x-intercept of a p/Z line. Several error
sources act on that line at once: random scatter in the reported average reservoir pressure, a
calibration offset shared by every survey, a units slip, the choice of deviation-factor
correlation, the declared standard-volume basis, and the plain fact that only part of the field
has been produced.

The decision the case supports is a surveillance decision, not a development decision: **given
a fixed budget, which single additional measurement most reduces the uncertainty in G?** The
candidates are more surveys, deeper depletion before quoting a number, a better average-pressure
determination, and a calibration check on the pressure datum. A useful answer changes what the
next survey programme is asked to do.

What would disprove the expected interpretation. The working expectation is that random scatter
and short depletion dominate a well-run programme, and that shared biases are second order. That
is wrong if a plausible calibration offset moves G by more than the one-sigma noise band of the
base programme, or if the deviation-factor correlation choice does. Either outcome reverses the
recommendation from "collect more and deeper surveys" to "fix the systematic first".

## 2. Sources and model identity

Everything here is synthetic and generated locally. No field data, no third-party dataset, no
simulator execution.

| Item | Value | Provenance |
|---|---|---|
| Generator | `reservoir_lab.depletion.simulate_volumetric_depletion` | This repository, source revision recorded in the run record |
| Estimator | `reservoir_lab.material_balance.fit_pz_depletion` and `reservoir_lab.regression` | Separate modules from the generator by design (api_contract.md C6) |
| Deviation factor | Dranchuk-Abou-Kassem (1975), Sutton (1985) pseudocriticals | `docs/evidence/zfactor.md` |
| Alternative deviation factors | Hall-Yarborough (1973), Dranchuk-Purvis-Robinson (1974) | Same card |
| Standard basis | 14.696 psia / 60 degF, and 14.73 psia / 60 degF | `reservoir_lab.units.SPE_STANDARD`, `US_CONTRACTUAL_STANDARD` |
| Fieller construction | Three-case set, `regression.x_intercept_fieller` | `docs/evidence/statistics.md`, corroborated there by von Luxburg and Franz |
| Sign of the psig error | psig = psia - 14.696, so the shift in G is negative | `docs/evidence/statistics.md`, adversarial-review correction to the card's own claim |

Declared reservoir. Single tank, dry gas, isothermal, constant hydrocarbon pore volume,
volume-averaged pressure at a fixed datum.

| Parameter | Value |
|---|---|
| True gas in place G | 1.0e11 scf (100 Bscf) at 14.696 psia, 60 degF |
| Initial pressure | 4500 psia, absolute |
| Reservoir temperature | 200 degF = 659.67 degR |
| Gas gravity | 0.65, no H2S or CO2 |
| Abandonment floor for the generator's pressure search | 400 psia |

Declared survey programme, the "base programme". Twelve shut-in surveys at annual spacing,
constant offtake, so cumulative production is evenly spaced from 0 to 50 Bscf and the observed
depletion fraction at the last survey is 0.50. That corresponds to about 12.5 MMscf/d from a
100 Bscf field, which is a plausible single-train development.

## 3. Governing model and assumptions

The inventory balance for a closed tank of constant hydrocarbon pore volume is

    p/Z = (p_i/Z_i) (1 - G_p/G)

with both pressures absolute and one declared standard basis carried by both G and G_p. Write
A = p_i/Z_i for the ordinate intercept, x for cumulative production and y for the ordinate. The
estimator is ordinary least squares on (x, y) and G is the x-intercept -a/b.

Mechanisms deliberately excluded. No aquifer, no rock or connate-water expansion, no retrograde
condensation, no adsorbed gas, no multi-tank communication, no injection. Every one of those
biases the same line, and several of them bias it by more than anything studied here; they are
excluded so that this case measures the *measurement* error budget alone and does not attribute
a drive-mechanism bias to a gauge. The water-drive counterexample is a separate case.

Mechanisms represented by a proxy. "Gauge noise" is a proxy for the whole chain that produces a
reported average reservoir pressure: gauge resolution, shut-in duration, build-up extrapolation
to p-star, and the well-to-tank volumetric averaging. The working assumption is that gauge
resolution is the smallest of those, and it stays an assumption: one lumped standard deviation
cannot separate the contributors, so no result of this case tests that ordering. The assumed
standard deviation is therefore a representativeness figure, not an instrument specification,
and it is an assumption, not a measurement.

Not represented at all. Cumulative production enters every fit as the noise-free generated
volume. Metering error, well-to-tank allocation, lease fuel and flare, shrinkage and condensate
accounting are not perturbed anywhere in this case, so what follows is an error budget on the
ordinate of the p/Z line and not on its abscissa. That is a deliberate scope limit, not a claim
that the abscissa is accurate: a uniform metering error scales the x-intercept by exactly the
same factor, so it would enter the ranking table roughly one-for-one, and a non-uniform one
breaks the errors-free-regressor assumption that ordinary least squares rests on.

Assumed error magnitudes, fixed before the experiments and used throughout:

| Symbol | Value | Why this value |
|---|---|---|
| sigma_p | 45 psia | 1.0 percent of the initial pressure. A representativeness figure for a volume-averaged shut-in pressure, chosen round and stated as an assumption. |
| shared bias c | plus or minus 25 psia | 0.25 percent of full scale for a 10,000 psi gauge, one calibration class. |
| psig slip | -14.696 psia exactly | One standard atmosphere rounded to three decimals. This literal value is what the run applies; the library constant `units.ATMOSPHERE_PSIA` is 14.695948775513450 psia and the 5e-5 psia difference is immaterial at the precision reported. |
| multiplicative Z error | plus or minus 1, 2 and 5 percent | The spread between published dry-gas correlations at these conditions, rounded up, with 5 percent added as a deliberately extreme level error. See the change log. |
| standard-basis slip | 14.696 against 14.73 psia | The two conventions actually in use. |

The analyst workflow is fixed for every experiment: each survey reports a pressure; the analyst
computes Z at *the reported pressure* with DAK and Sutton pseudocriticals, forms p/Z, and fits
OLS against reported cumulative production. This matters, because it means a pressure error
propagates into Z as well as into the numerator, and the two effects do not cancel.

## 4. Experiments

Each experiment perturbs one thing. Unless stated, the base programme and the base gas model
are used and every other input is the noise-free truth.

**E0. Noise-free oracle.** Fit the generated noise-free history. The x-intercept must return G.
This is the check that the generator, the ordinate construction and the estimator agree before
anything is perturbed.

**E1. Random gauge noise.** Independent Gaussian error, sigma_p = 45 psia, on every reported
pressure. One named realisation reported in full, then a 4000-replicate Monte Carlo for the
sampling distribution of G, the coverage of the delta-method interval and the coverage of the
Fieller set. Repeated at n = 24 surveys over the same depletion to test the 1/sqrt(n) scaling.

**E1b. Temporally correlated gauge error.** An AR(1) error with lag-1 correlation 0.8 and the
same marginal standard deviation. Added to the pre-registered list because it is the positive
control for the moving-block bootstrap: a method that exists to handle dependence must be shown
to see dependence before its behaviour under independence means anything.

**E2. Shared calibration bias.** The same offset c on every reported pressure, noise free, for
c in {-50, -25, -14.696, 0, +25, +50} psia. Two variants: Z recomputed at the offset pressure
(the realistic workflow) and Z held at the true value (isolates the numerator). Repeated at
n = 12, 24 and 48 surveys to test invariance to sample size.

**E3. psig supplied where psia was required.** The special case c = -14.696 psia, reported
separately because the sign is the point. Also run as a Monte Carlo with noise added, to measure
how often the resulting 95 percent interval still covers the truth, that is, how often the error
is invisible.

**E4. Deviation-factor error.** (a) A uniform multiplicative error, Z' = (1 + eps) Z. (b) The
correlation-choice difference: Hall-Yarborough and Dranchuk-Purvis-Robinson applied to the same
reported pressures in place of DAK, with the relative difference from DAK also scanned on a
401-point grid across the observed window, because two survey pressures cannot show whether the
difference is monotone. (c) A shape error: Z tilted linearly across the observed pressure window
by plus or minus 1 percent, which separates the level of Z from its slope.

**E5. Short observed depletion.** The same noise at observed depletion fractions of 0.10, 0.20,
0.35 and 0.50, twelve surveys in each case. The standard error is reported for each, together
with the Fieller set, a moving-block bootstrap, the Fieller discriminant g, and a design-based
analytic prediction. A deliberately degraded programme (six surveys, 4 percent depletion,
sigma_p = 120 psia) is added to reach the regime where the exact confidence set is unbounded.

**E6. Standard-condition basis.** 14.696 against 14.73 psia, applied to a static volumetric
estimate and to the dynamic p/Z estimate separately, because the two do not respond the same way.

**E7. Ranking and information value.** Collate the effect of each source on G, ranked, with the
ranking recomputed at sigma_p of 22.5, 45 and 90 psia to test whether it survives the assumption
that produced it. Then project the one-sigma standard error and the bias floor for four
candidate next steps using the exact least-squares inverse-prediction identity.

Chronological holdout. The base programme is refitted on surveys 1 to 8 only and used to predict
p/Z at surveys 9 to 12. No parameter is tuned on the holdout; the fit has no free parameter
beyond the line itself.

Data-exclusion rule, fixed in advance: no point is excluded from any fit, for any reason,
including a fit that fails. A fit that `fit_pz_depletion` refuses is counted as a refusal and
reported as such, not retried with a trimmed series.

## 5. Verification and acceptance

The independent reference answer is not another regression. For each perturbation it is a closed
form derived from the least-squares algebra, which is independent of the estimator's code path
in the sense that matters here: it is evaluated from the *unperturbed* fit plus the perturbation
vector, and never calls the estimator on the perturbed data. Because OLS is linear in the
ordinate, this prediction is exact, not asymptotic:

    Delta_b = sum_i (x_i - xbar) delta_i / S_xx
    Delta_a = mean(delta) - Delta_b xbar
    G_predicted = -(a + Delta_a) / (b + Delta_b)

where delta_i is the change in the ordinate at survey i. The card's rule of thumb,
Delta_G = c G / (p_i/Z_i), is the special case delta_i = c, that is Z identically 1, and it is
reported alongside so the size of the Z correction is visible rather than assumed away.

Acceptance criteria, fixed before the experiments:

| ID | Criterion | Threshold | Basis for the threshold |
|---|---|---|---|
| AC1 | Noise-free x-intercept recovers G | relative error below 1e-9 | Both sides are the same algebra; only floating point separates them |
| AC2 | Exact linear-perturbation prediction matches the refitted G for every shared offset, both Z variants | relative error below 1e-9 | An identity, not an approximation |
| AC3 | psig slip moves G in the negative direction | strictly negative, and within 1e-9 of the AC2 prediction | Sign from the evidence card's review; the case must confirm it, not assume it |
| AC4 | Uniform multiplicative Z error leaves G unchanged | relative shift below 1e-12 | Scaling the ordinate scales a and b equally, so -a/b is exactly invariant |
| AC5 | Delta-method 95 percent interval coverage at f = 0.50 | between 0.935 and 0.965 | Nominal 0.95 plus three Monte Carlo standard errors at the smallest ensemble any coverage criterion has to cover, 2000 replicates: 3 sqrt(0.95 x 0.05 / 2000) = 0.0146, rounded out to 0.015. At the 4000-replicate ensembles the same half-width is 4.35 standard errors, so the band is looser there than three; the run reports how far inside the observed value sits in units of its own Monte Carlo standard error |
| AC6 | Fieller 95 percent coverage at every setting whose error model is the fitted least-squares one: the four E5 depletions, the degraded programme, E1 at n = 12 and at n = 24 | between 0.935 and 0.965 | Fieller is exact under the least-squares model, so it must hold at low signal where the delta method fails. E1b violates that model deliberately and is excluded from the criterion; its coverage is reported separately and is expected to fail |
| AC7 | Library delta-method standard error equals the collapsed inverse-prediction closed form | relative difference below 1e-12 | Two code paths for one identity; disagreement is a library defect |
| AC8 | Standard-basis change scales both the static volumetric G and the rescaled p/Z intercept by exactly the declared standard-pressure ratio, `SPE_STANDARD.pressure_psia` / 14.73 = 14.695948775513450/14.73 | relative error below 1e-12 | Bg is linear in p_sc; the x-intercept is equivariant under a scale on x. The identity is against the constants the library carries, not against the rounded literal 14.696/14.73, which differs from them by 3.5e-6 relative and would fail this tolerance |
| AC9 | The degraded programme reaches the unbounded Fieller regime | at least 10 percent of replicates with g >= 1 | The three-case handling must be exercised by data, not asserted |

Failure handling. AC1 failing voids every downstream number and the case is reported as failed.
AC5 or AC6 failing means the noise model or the interval machinery is misbehaving and no ranking
is published. AC9 failing means the unbounded-Fieller discussion is reported as not exercised
rather than described from the literature.

The case is INCONCLUSIVE, and must say so, if any of the following holds:

1. The ranking of the top two error sources changes when sigma_p is varied by a factor of two in
   either direction. The ranking is then a restatement of the assumed sigma_p and not a result.
2. The Monte Carlo standard deviation of G and the median delta-method standard error disagree
   by more than a factor of 1.5 at f = 0.50, which would mean the sampling distribution is not
   summarised by any single number and no error budget can be built from it.
3. The degraded programme's `fit_pz_depletion` refusal rate exceeds 25 percent, in which case
   the surviving fits are a selected sample and their spread understates the truth.

## 6. Interpretation and artifacts

Required outputs: `results/summary.json` with every number quoted in the report, and
`results/run_record.json` with the source revision, config hash, environment and seed. The
report must carry the ranking table, the three-treatment comparison of delta, Fieller and
bootstrap, the unbounded-Fieller paragraph, and the explicit statement of what the case does not
establish.

What this case cannot establish, stated before it runs: it is synthetic self-consistency for the
*measurement* error budget of a closed-tank model. It says nothing about whether the tank model
is right. A weak aquifer biases G by more than every source studied here combined, produces a
better-looking straight line while doing so, and is invisible to all three uncertainty
treatments. Nothing here is a reserves statement.

## 7. Pre-registration note

A scoping pass was run before this protocol was written, to size the survey programme and to
check that the degraded programme could reach the unbounded-Fieller regime at all. That pass
fixed *design* parameters: sigma_p, the number of surveys, the bias magnitudes and the degraded
programme's settings. No acceptance threshold in section 5 was chosen after seeing the quantity
it judges. AC1 to AC4 and AC7 to AC8 are machine-precision identities, fixed by the algebra.
AC5 and AC6 are the nominal confidence level plus its own Monte Carlo error. AC9 is a round
number chosen to be clearly exceeded or clearly missed. Because the degraded programme's
settings came from that scoping pass, AC9 confirms that the unbounded-Fieller code path is
exercised by data; it is not the discovery that such a programme exists. The inconclusive
conditions in section 5 were written before the ranking was computed.

The one thing the scoping pass did reveal, and which is recorded here rather than presented as
a prediction: the two closed forms for the shared-offset shift, the card's Z = 1 rule of thumb
and the exact linear-perturbation form, do not agree. The case therefore reports both and
quantifies the gap, instead of reporting the rule of thumb as verified.

## 8. Change log

| Date | Change |
|---|---|
| 2026-09-13 | Protocol written. E1b added to the pre-registered list as the bootstrap's positive control. |
| 2026-09-13 | After run-001: the chronological holdout moved from the noise-free history (where it is exactly zero by construction and therefore says nothing) to the noisy base realisation under E1. No acceptance threshold changed; run-001 is retained in the experiment register and run-002 is the run the report quotes. |
| 2026-09-13 | After referee review of the run-002 report. Four amendments, none of them a threshold change. (a) E4(a)'s multiplicative grid extended from plus or minus 1 and 2 percent to plus or minus 1, 2 and 5 percent, because the report quoted a 5 percent magnitude the grid had never tested; the invariance is exact algebra and the extended grid returns the same machine zero. (b) E4(b) gained the 401-point scan of the correlation difference across the window, because the report described the difference as a two-point tilt when the run had only evaluated it at two points. (c) AC6's text now names the settings its coverage list actually contains, and E1 at n = 24 was added to that list; E1b remains excluded and is reported separately. (d) AC8's text now names the constants the identity is actually tested against. The stated basis of the AC5 and AC6 band was corrected from 4000 to 2000 replicates: the band itself, 0.95 plus or minus 0.015, is unchanged, and the run now reports the observed coverage's distance from nominal in its own Monte Carlo standard errors so a reader can apply a tighter band. The section 3 provenance of the psig slip and the scope limit on cumulative production were corrected in the same pass. Run-002 and run-003 are retained; run-006 is the run the report quotes. |

# Case A3: what actually dominates the uncertainty in a gas-in-place estimate

Run quoted throughout: `artifacts/A3_uncertainty_experiments/run-006`, source revision
855fe5447b5f2a87ea006727dd893204a18a2832 (working tree dirty: `.gitignore`, `CHANGELOG.md` and
`cases/`), config SHA-256 `3274099046e3...`, seed 20260913, 14.2 s wall clock. The two artefacts
the numbers come from are copied into `results/`. Protocol: `protocol.md`, written before the run;
section 8 of it lists the amendments made after a separate review pass and what each one changed.
That pass, and the later repository-wide claims audit whose corrections are marked
`[SUPERSEDED]` below, were both conducted under a different role by the same author, not by a
different person. `AGENTS.md:46` states the rule: different role names do not create
independent expertise or independent evidence. **No human peer review took place, and no
external or independent reviewer participated.** The claims-audit corrections are listed in
`docs/release/CORRECTIVE_RELEASE_REPORT.md`.

Four statements are kept apart throughout this report, because this case reaches the first
and speaks to the second only in p/Z space: **numerical verification** (the estimator inverts
the forward map to the precision the arithmetic allows); **conditional pressure
reconstruction** (a held-out series reconstructed under stated conditions); **physical
interpretation** (what a reservoir is actually doing); and **decision adequacy** (whether a
number is fit to carry a depletion or development decision). This case is a measurement error
budget. Clearing any tolerance in it is not evidence of physical interpretation or of decision
adequacy. And `G` here is inventory in place: not a recoverable volume, which depends on the
drive mechanism and the abandonment condition, and not a reserve, which is a further
commercial and regulatory classification of a recoverable volume.

**Prospective ordering.** This case's `run.py` declares `protocol.md` as an input and its run
record pins it by SHA-256, so the protocol content that existed at run time is provably the
committed content. That establishes internal content linkage as recorded. It is **not** an
independent trusted timestamp and **not** proof against retrospective construction: the
repository has no remote, no tag and no signature, so every date in it is self-reported. Cases
A1 and A4 declare no inputs at all, and their ordering is unverified.

## Question and answer

**Question.** Given a realistic survey programme on a synthetic closed-tank dry-gas reservoir,
which error source dominates the inferred gas in place, and which would be most worth reducing?

**Answer.** At the declared base programme -- twelve annual shut-in surveys, 50 percent of the
gas produced by the last one, an assumed 45 psia standard deviation on the reported average
reservoir pressure -- random pressure scatter is the largest single contributor at 1.32 percent
of G at one sigma, and a 25 psia shared calibration bias is second at 0.86 percent. **That
ranking is not robust.** It was pre-registered as an inconclusive condition, and the condition
triggered: halving the assumed scatter to 22.5 psia reverses the order, putting the shared bias
first at 0.86 percent against 0.66 percent. The ranking of the top two is a restatement of an
assumed number, not a result, and is reported as such.

Everything in that answer is an ordinate-side statement. Cumulative production is never
perturbed anywhere in this case, so what follows is an error budget on the p/Z axis and not on
the volume axis. The limitations section says what that leaves out and why it matters.

What the case does establish, and what does not depend on the assumed scatter:

* The *level* of the deviation factor is exactly irrelevant to G. Over a grid of uniform
  multiplicative errors in Z of -5, -2, -1, +1, +2 and +5 percent, the largest movement of the
  x-intercept is 3.1e-16 relative -- machine zero, not a small number. That is algebra, not a
  measurement, and it is the one result here that transfers to any reservoir. What moves G is the
  *shape* of Z across the observed pressure window, roughly one-for-one: on this reservoir's Z(p)
  a 1 percent tilt across the window moves G by 1.09 percent.
* A shared offset behaves qualitatively differently from scatter: it does not shrink with more
  surveys. At +25 psia the bias is +0.8624 percent at 12 surveys, +0.8645 percent at 24 and
  +0.8655 percent at 48, while the random one-sigma falls from 1.32 to 0.98 to 0.70 percent.
  Past about 30 surveys the bias is the larger term and no further surveying touches it.
* Supplying psig where psia was required makes the reservoir look **smaller**. The sign in the
  evidence card's review is confirmed and is general. The magnitude here is 0.504 percent
  (0.504 Bscf out of 100), which is 1.58 times the card's rule of thumb -- that factor is a
  property of this Z(p) over this window, not a constant.
* Short observed depletion is the strongest *design* lever this case examined: at fixed noise,
  fixed survey count and an evenly spaced abscissa, the one-sigma error at 10 percent depletion
  is 5.06 times the error at 50 percent.
* The standard-condition basis is a 0.231 percent bookkeeping scale, exact to machine precision,
  and the p/Z fit is completely blind to it.
* Of the four candidate next steps compared, a calibration check on the pressure datum gives the
  lowest projected total error, 1.32 percent against 1.52 to 1.84 percent for the others, under a
  stated convention for combining a random and a systematic term. That conclusion assumes the
  check leaves no residual datum error; a residual above 5.83 psia would put it behind the
  next-best option. No cost or effort model is part of this case.

## The programme and the oracle

True G is 1.0e11 scf at 14.696 psia and 60 degF. Initial pressure 4500 psia, temperature
200 degF, gas gravity 0.65, Sutton pseudocriticals, Dranchuk-Abou-Kassem deviation factor. That
gives Z_i = 0.974045 and A = p_i/Z_i = 4619.91 psia. The observed pressure window runs from
4500 psia down to 2070.9 psia, over which Z falls from 0.9740 to 0.8965.

The analyst workflow is fixed for every experiment: each survey reports a pressure, the analyst
computes Z at *the reported pressure*, forms p/Z, and fits OLS against reported cumulative
production. So a pressure error propagates into both factors of the ordinate.

**E0, the oracle.** On the noise-free generated history the OLS x-intercept returns
100.000000000000 Bscf, a relative error of +7.19e-14. The generator's own balance residual is
1.05e-09 psia of p/Z, eight orders of magnitude below the smallest effect studied. The
noise-free chronological holdout residual is 4.5e-10 psia of p/Z, which confirms exact linearity
and says nothing about measurement error; the informative holdout is under E1.

**E1 holdout.** On the noisy base realisation, fitting surveys 1 to 8 only (32 percent depletion)
and predicting surveys 9 to 12 gives an RMSE of 69.3 psia of p/Z, 1.50 percent of p_i/Z_i, with
G from training alone of 97.25 +/- 2.15 Bscf against 100.37 Bscf from the full history. Nothing
was tuned on the held-out surveys. The 3.124 Bscf move between the two fits is 1.45 times the
training fit's own standard error, so the one-sigma band from eight surveys, [95.09, 99.40] Bscf,
excludes both the full-history answer and the truth; the truth sits 1.28 sigma out. Two sigma
covers both. The reading is that eight surveys had not yet pinned G down, and that on this
realisation the truth fell outside the one-sigma band -- not that the two fits agreed.
One draw says nothing about whether the interval is calibrated; at 68 percent nominal
coverage a single miss is the expected outcome about a third of the time. E3 is where
coverage is actually measured.

[SUPERSEDED] The run-002 report stated that this move was *inside* the training fit's one-sigma
band. It is not; the sentence inverted the comparison, in the direction that made the holdout
look more reassuring than the arithmetic supports. Corrected here against the same numbers,
which have not changed.

## Experiment 1: random gauge noise

Independent Gaussian error, sigma_p = 45 psia, on every reported pressure. 4000 replicates.

| Quantity | Value |
|---|---|
| Monte Carlo standard deviation of G | 1.413 Bscf (1.41 percent) |
| Median delta-method standard error | 1.294 Bscf |
| Delta-method 95 percent coverage | 0.9405 |
| Fieller 95 percent coverage | 0.9410 |
| Monte Carlo mean of G | 100.065 Bscf |
| Standard deviation at 24 surveys / at 12 | 0.7159, against 1/sqrt(2) = 0.7071 |

The delta-method standard error is a usable summary here, with one qualification. The median
standard error sits 8 percent below the Monte Carlo standard deviation because the sampling
distribution of a ratio has heavier tails than its own interquartile range implies -- the robust
scale of the ensemble, 1.387 Bscf, sits about 7 percent above the median standard error. The
ratio estimator's bias is small at this signal: the ensemble mean is 0.065 percent above the
truth. The qualification is coverage: 0.9405 against a nominal 0.95 is 2.76 Monte Carlo standard
errors low at 4000 replicates. It passes the pre-registered band, but the band is wider than
three of its own standard errors at this ensemble size (see the acceptance section), and the
honest reading is a small genuine under-coverage at twelve surveys rather than coverage exactly
at nominal. Fieller, at 0.9410, is in the same place.

The 1/sqrt(n) scaling holds to 1.2 percent, which is the check that the noise is behaving as
declared before anything is attributed to it.

## Experiment 1b: a drifting gauge, the bootstrap's positive control

This was added to the pre-registered list because a method that exists to handle dependence must
be shown to see dependence before its behaviour under independence means anything. An AR(1)
pressure error with lag-1 correlation 0.8 and the same marginal 45 psia:

| Quantity | Independent | AR(1), rho = 0.8 |
|---|---|---|
| Monte Carlo sd of G | 1.413 Bscf | 2.310 Bscf |
| Median delta-method standard error | 1.294 Bscf | 0.752 Bscf |
| Delta-method 95 percent coverage | 0.941 | 0.544 |
| Fieller 95 percent coverage | 0.941 | 0.544 |

Correlated error nearly doubles the true uncertainty in G and the delta method *reduces* its
reported error bar by 42 percent while that happens. The mechanism is not subtle: a smoothly
drifting gauge displaces the whole line without scattering the points around it, so the residual
variance falls while the intercept moves further. Coverage collapses to 0.544 at nominal 0.95.

The finding that matters most here is the second row of that column. **The Fieller set collapses
identically.** It is exact under the least-squares model and the least-squares model is what the
drift violates, so exactness buys nothing. An exact interval is not a robust interval, and no
choice among the three treatments repairs a wrong error model.

On the named drifting realisation the moving-block bootstrap moves in the right direction and
does not get there: block length 1 gives 0.863 Bscf, block length 3 gives 1.208, block length 6
gives 1.222, against a true 2.310 -- a 47 percent shortfall at twelve surveys. At twelve surveys
there is not enough series to resample. The library's own docstring records a comparable failure
at a longer history: at n = 48 with strong drift, even a well-chosen block length still
understated the truth by about 20 percent. That is not the same experiment as this one -- the
only AR(1) correlation the docstring names is rho = 0.9, against 0.8 here -- so the two figures
show the same direction of failure and are not two points on one scaling.

## Experiment 2: a shared calibration bias

The same offset on every survey, noise free, so the shift is deterministic. Two variants: Z
recomputed at the offset pressure, which is the realistic workflow, and Z held at its true value,
which isolates the numerator.

| Offset, psia | dG, Z recomputed | dG, Z held | Card rule of thumb c G/(p_i/Z_i) | Card understates by |
|---|---|---|---|---|
| -50.000 | -1.7037% | -1.3197% | -1.0823% | 1.57x |
| -25.000 | -0.8554% | -0.6605% | -0.5411% | 1.58x |
| -14.696 | -0.5037% | -0.3884% | -0.3181% | 1.58x |
| 0.000 | 0.0000% | 0.0000% | 0.0000% | - |
| +25.000 | +0.8624% | +0.6617% | +0.5411% | 1.59x |
| +50.000 | +1.7319% | +1.3247% | +1.0823% | 1.60x |

Every row is matched by the exact linear-perturbation prediction to 3.1e-16 relative (AC2), so
these are not fitted numbers, they are the algebra.

**Why a shared bias is not a small random error.** Three things separate it from scatter.

First, it does not average out. Adding surveys reduces the random term as 1/sqrt(n) and leaves
the bias exactly where it is: +0.8624, +0.8645, +0.8655 percent at 12, 24 and 48 surveys, against
a random one-sigma of 1.3242, 0.9761 and 0.7046 percent. Somewhere near 30 surveys the two cross
and further surveying stops helping.

Second, it is invisible in the fit diagnostics. A constant offset on the pressure shifts a
straight line to another straight line. R-squared does not move, the residual pattern does not
move, and the delta-method standard error does not move. Nothing in the regression output is
different. With the psig slip present and the usual noise added, the 95 percent interval still
covered the truth in 92.5 percent of 4000 replicates, against a nominal 95 percent: a 14.7 psi
units error costs two and a half points of coverage and is otherwise undetectable from the fit.

Third -- and this is the part the rule of thumb misses -- the offset does not act uniformly on
the ordinate. The ordinate is p/Z, not p. A constant offset c in pressure becomes an ordinate
shift of roughly c/Z at each survey, and Z falls from 0.974 to 0.897 across the observed window,
so the later points are displaced about 9 percent more than the earlier ones. That tilts the
line as well as lifting it, and the tilt adds to the intercept shift rather than cancelling it.
With Z recomputed at the offset pressure a second term appears, because d(p/Z)/dp is not 1/Z but
(1/Z)(1 - (p/Z) dZ/dp). The two together account for the whole factor of 1.58 at this Z(p) over
this window; the factor is not a constant of nature and another gas would give another one.

## Experiment 3: psig supplied where psia was required

The specific case c = -14.696 psia, the rounded standard atmosphere declared in the protocol.
(The library constant `units.ATMOSPHERE_PSIA` is 14.695948775513450 psia; the run applies the
rounded value, and the 5e-5 psia difference is four orders below the reported precision.)

| Quantity | Value |
|---|---|
| Shift in G, Z recomputed at the reported pressure | **-0.504 Bscf, -0.5037 percent** |
| Shift in G, Z held at the true pressure | -0.388 Bscf, -0.3884 percent |
| Card rule of thumb, 14.696 G/(p_i/Z_i) | -0.318 Bscf, -0.3181 percent |
| Sign negative, as the card's review states | confirmed |
| Agreement with the exact linear-perturbation prediction | 1.5e-16 relative |
| Size relative to the design one-sigma of the base programme | -0.38 sigma |
| Coverage of the truth with the slip present | 0.9245 against a nominal 0.95 |

The sign is confirmed and was not taken on trust: the fit was rerun on gauge pressures and the
x-intercept moved down. psig = psia - 14.696, so the shared offset is negative, the whole p/Z
line drops, and the line crosses zero sooner. The reservoir looks smaller.

The magnitude is not confirmed. The card's rule of thumb, 14.696 G/(p_i/Z_i) = 0.318 Bscf, is
the Z = 1 special case of the general perturbation. With this reservoir's real Z(p) the shift is
1.58 times larger. Anyone using the rule of thumb as a screening bound on a gas of this kind is
under-bounding the error, in the direction that makes the slip look more tolerable than it is;
how much larger the true shift is depends on the Z(p) of the gas in question, and this case
measured it for one gas. The general form -- change the ordinate by the actual delta vector and
recompute -(a + da)/(b + db) -- costs nothing and is exact.

At -0.38 of the base programme's one-sigma, this error is not detectable from the data. It is
only findable by reading the units on the survey report. That is the practical conclusion: this
is a data-intake problem, not an estimation problem.

## Experiment 4: errors in the deviation factor

**A uniform multiplicative error does nothing at all.** For Z' = (1 + eps) Z with eps of -5, -2,
-1, +1, +2 and +5 percent, the largest shift in G is 3.05e-16 relative. This is exact, not
approximate: scaling the whole ordinate by a constant scales the fitted intercept and slope by
the same constant, and the x-intercept -a/b is invariant. Anyone worried that their Z correlation
might be 1 percent high everywhere can stop worrying about *that* effect on a p/Z gas in place.
It matters for Bg, for a static volumetric estimate and for reservoir-volume bookkeeping; it does
not touch the dynamic x-intercept.

**Correlation choice does move G, through the shape of the difference, not its size.**

| Correlation used by the analyst | G, Bscf | Shift | Z difference from DAK at 4500 psia | at 2071 psia |
|---|---|---|---|---|
| Hall-Yarborough (1973) | 99.801 | -0.1985% | -0.1733% | +0.0229% |
| Dranchuk-Purvis-Robinson (1974) | 100.333 | +0.3326% | +0.3526% | +0.0517% |

Scanned at 401 pressures across the observed window, both correlations stay within 0.36 percent
of DAK: Hall-Yarborough runs from -0.2705 to +0.0229 percent, DPR from +0.0517 to +0.3526
percent. The difference is not monotone in pressure. Hall-Yarborough's worst point is interior,
-0.2705 percent at 3547 psia, an order of magnitude larger than its value at the bottom of the
window, while DPR's worst point is the top of the window. So the two survey pressures in the
table above show that a residual tilt exists and understate its shape; what the x-intercept
responds to is the whole difference profile weighted by the least-squares leverages, not the gap
between the endpoints.

**The shape sensitivity is about one for one.** Tilting Z linearly across the observed window:

| Tilt across the window | Shift in G | Amplification |
|---|---|---|
| -1.0% | -1.0686% | 1.07 |
| -0.5% | -0.5368% | 1.07 |
| +0.5% | +0.5419% | 1.08 |
| +1.0% | +1.0891% | 1.09 |

So the useful statement about Z is not "how accurate is my correlation" but "how accurate is the
*change* in my correlation across the pressures I am fitting over". A PVT check at one pressure
constrains the level and constrains nothing that matters here. Two checks, one near initial
pressure and one near the current pressure, would constrain the tilt. The amplification factor
itself, 1.07 to 1.09, is a property of this window and this Z(p); the qualitative statement --
level irrelevant, shape roughly one-for-one -- is what carries over, and only its first half is
exact.

## Experiment 5: short observed depletion

Same noise, twelve surveys, varying the depletion reached by the last survey. Each row is one
named realisation plus a 2000-replicate ensemble.

| f | G, Bscf | delta SE, Bscf | bootstrap SE (l=1), Bscf | MC sd, Bscf | design one-sigma | g | Fieller 95 percent set, Bscf |
|---|---|---|---|---|---|---|---|
| 0.10 | 91.116 | 6.607 | 5.863 | 7.109 | 6.702 | 0.0292 | [78.541, 108.870] |
| 0.20 | 93.291 | 3.404 | 3.867 | 3.473 | 3.383 | 0.0082 | [86.335, 101.632] |
| 0.35 | 99.228 | 1.641 | 1.656 | 2.035 | 1.932 | 0.0020 | [95.726, 103.052] |
| 0.50 | 103.022 | 0.842 | 0.649 | 1.364 | 1.324 | 0.0006 | [101.187, 104.943] |

Monte Carlo coverage of the delta interval was 0.948, 0.950, 0.9385 and 0.9465 across the four
rows; Fieller 0.947, 0.948, 0.9415 and 0.944. All eight sit inside the pre-registered band.

**The trend, analytically.** For ordinary least squares the standard error of the x-intercept is
exactly

    SE(G) = (s / |b|) sqrt( 1/n + (G - xbar)^2 / S_xx )

Put the abscissa on an even grid from 0 to fG. Then xbar = fG/2, S_xx is approximately
n f^2 G^2 / 12, and b = -A/G, so

    SE(G) ~ (s G / A) (1/sqrt(n)) sqrt( 1 + 12 (1 - f/2)^2 / f^2 )

The bracket is dominated by the second term for any f a survey programme actually reaches, so
SE(G) grows very nearly as 1/f. That is what the table shows: 6.607 against 0.842 Bscf between
f = 0.10 and f = 0.50 is a factor of 7.8 in one realisation; on the design formula, which removes
the realisation-to-realisation variation in s, the ratio is 5.06. Both the formula and that 5.06
rest on the even grid. An irregular survey programme has a different S_xx and a different
penalty. The physical statement is simple. The x-intercept is an extrapolation, its distance
beyond the data is (1 - f)/f data spans, and the lever arm on the slope error grows with that
distance.

The `PZFit` warning machinery marks this: at f = 0.10 the library emitted `weak_extrapolation`
and a `delta_method_interval` note that g = 0.0292 exceeds the 0.01 reporting threshold, so the
exact interval is about 3 percent wider on one side than the symmetric one. That is a small
asymmetry and the two treatments still agree. It is a different story one programme further down.

## The three uncertainty treatments, and where they disagree

Compared on the same data at every row of the table above and on the degraded programme.

At the base programme the three agree well enough that the choice does not matter. On the named
E1 realisation: delta-method 100.372 +/- 1.116 Bscf, symmetric interval [97.885, 102.859];
Fieller set [97.962, 102.940]; bootstrap with block length 1, standard error 1.016 Bscf,
percentile interval [98.267, 102.184]. g = 0.00104, so the Fieller set is bounded and nearly
symmetric, exactly as the theory says it must be at this signal.

They disagree in three specific ways.

**The bootstrap's answer depends entirely on a block length that twelve surveys cannot
determine.** On the same independent-error realisation, `suggested_block_length` returned 3 --
the Hall-Horowitz-Jing rate rule ceil(12^(1/3)), the repository heuristic's own stated basis --
and that more than doubled the reported standard error, 2.251 Bscf against 1.016 for the correct
i.i.d. scheme and 1.413 for the Monte Carlo truth. The estimated lag-1 correlation from twelve
residuals was 0.098, which is not distinguishable from zero at that sample size. So the heuristic
over-blocks when the errors are independent, and E1b shows it under-blocks when they are not. The
block length has to come from knowledge of the measurement process -- is this gauge drifting, is
the same crew extrapolating every build-up -- not from the residuals of twelve points.

**At low signal the delta method prints a number that is not merely imprecise but impossible.**
On the degraded programme the symmetric 95 percent interval is [-16.4, +193.7] Bscf. A negative
gas in place is not a wide estimate, it is a statement outside the sample space, and the
symmetric construction produced it without complaint.

**The bootstrap at low signal is describing its own tails.** The degraded programme's block
bootstrap with l = 1 reported a standard error of 211.7 Bscf and a percentile interval of
[38.4, 542.4] Bscf, against a Monte Carlo sampling standard deviation of 2480 Bscf and a robust
scale of 58.8 Bscf. Three numbers, three orders of magnitude, all describing the same
distribution. That is what a ratio estimator does when its denominator can approach zero.

**Which I would report.** The Fieller set, with g printed next to it. It held the pre-registered
band at every setting tested where the error model was the fitted one -- 0.941 to 0.948 across the
E5 sweep and the two E1 ensembles, 0.9425 on the degraded programme against the delta method's
0.908 -- and it is the only one of the three whose return type can say "unbounded" rather than
inventing a finite width. It buys nothing when the error model is wrong: E1b's 0.544 is identical
for both interval methods. The delta-method standard error is a legitimate summary when g < 0.01
and it is easier to communicate, so I would quote it in that regime and quote the Fieller set
outside it, which is the rule the library's own threshold encodes. The bootstrap I would report
as a diagnostic of error *structure*, not as the headline uncertainty: the gap between its l = 1
and l = 3 answers is informative about whether the surveys are independent, and its absolute
value at n = 12 is not trustworthy either way.

## The unbounded confidence set

The degraded programme -- six surveys, 4 percent depletion, sigma_p = 120 psia -- is a
deliberately hard configuration, fixed in the scoping pass recorded in protocol section 7 so that
the unbounded-Fieller regime would be reached at all. It is not evidence about what early-life
appraisal programmes typically look like, and nothing in this case establishes that. It is where
the three-case Fieller handling stops being a technicality.

On the named realisation the fit returned G = 88.661 Bscf with a delta-method standard error of
37.831 Bscf, and g = 1.469. Because g exceeds 1, the exact 95 percent confidence set is not an
interval. It is the *complement* of the open interval (-406.98, +41.17) Bscf: the union of two
half-lines. The data rule out gas in place between 41 Bscf and (irrelevantly) -407 Bscf, and say
nothing whatever about the upper end. The point estimate, 88.661, lies in the set, as it must.

Across 2000 replicates of that programme, 73.6 percent of fits produced an unbounded set --
1471 exclusive against 529 bounded. The delta method's coverage over the same ensemble was 0.908;
Fieller's was 0.9425. The Monte Carlo standard deviation of G was 2480 Bscf on a 100 Bscf
reservoir, while the median delta-method standard error was 51.2 Bscf. Both numbers are correct
descriptions of different things, and neither is an error bar anyone should quote.

`material_balance.fit_pz_depletion` refused 94 of the 2000 fits outright, 4.7 percent, because
the fitted slope came out non-negative -- six noisy surveys over 4 percent depletion sometimes
show no decline at all. Those refusals are counted, not retried and not dropped: a retried
replicate is how an ensemble becomes a selected sample. The pre-registered inconclusive threshold
was 25 percent and was not reached, so the surviving ensemble is usable.

The practical reading is that at 4 percent depletion this survey programme does not measure gas
in place. It measures a lower bound of about 41 Bscf. That is a real result and it is more useful
than "100 +/- 38 Bscf", which is what the symmetric machinery would have printed. The engineering
response is to say the estimate is not identified yet and to state the bound, not to widen an
error bar until it looks honest.

## Experiment 6: the standard-condition basis

14.696 psia against 14.73 psia, both at 60 degF. The ratio actually applied is the one the
library's constants give, 14.73 / 14.695948775513450 = 1.0023170.

| Quantity | 14.696 psia | 14.73 psia | Shift |
|---|---|---|---|
| Bg at 4500 psia, rcf/scf | 0.00403797 | 0.00404733 | +0.2317% |
| Static volumetric G, Bscf (2000 acres, 60 ft, 0.18, Sw 0.25) | 174.759 | 174.355 | -0.2312% |
| Dynamic p/Z x-intercept, Bscf | 100.000 | 99.769 | -0.2312% |

Both shifts match that ratio to 1.1e-16 relative. Against the rounded literal 14.696/14.73 =
1.0023136 they agree only to 3.5e-6, because the two ratios themselves differ by that much: the
identity is exact against the constants the code carries, not against the three-decimal
shorthand. The higher standard pressure packs more gas into a standard cubic foot, so the same
reservoir volume is fewer scf.

[SUPERSEDED] The run-002 report and the run-002 text of AC8 both said "exactly 14.696/14.73".
Tested against that literal the agreement is 3.5e-6, which the criterion's own 1e-12 tolerance
would fail by six orders of magnitude. The numbers reported were always the ones the run
produced; the prose and the criterion text named the wrong constant, and both are corrected here.

The important part is what this does *not* do. The p/Z line's x-intercept is in whatever units
the cumulative production was supplied in. If the sales meter reports on the 14.73 basis, the
fitted G comes out on the 14.73 basis, and the fit is correct. The standard-basis error is
therefore not an estimation error at all -- it is a bookkeeping error, and it appears only when a
dynamic G on one basis is compared with a static volumetric G, a contracted volume, or another
field's number on a different basis. A 0.23 percent inconsistency is small against everything
else measured here, but unlike the others it is free to eliminate: declare the basis and carry it.

This experiment also establishes, as a by-product, the one thing the case can say about the
abscissa: rescaling cumulative production by a constant rescales the x-intercept by exactly the
same constant, to 0 relative here. A metering error that is uniform over the history therefore
passes straight into G one-for-one, and would rank at or above the top row of the table below.
Nothing in this case perturbs cumulative production in any other way.

## Ranking, and why it is not robust

Effect on G, as a fraction of G, at the base programme. Ordinate sources only: the abscissa is
absent from this table because it was never perturbed.

| Source | sigma_p = 22.5 | sigma_p = 45 | sigma_p = 90 |
|---|---|---|---|
| random pressure scatter, one sigma | 0.662% | **1.324%** | 2.648% |
| shared calibration bias, 25 psia | 0.862% | 0.862% | 0.862% |
| psig supplied as psia | 0.504% | 0.504% | 0.504% |
| deviation-factor correlation choice | 0.333% | 0.333% | 0.333% |
| standard basis 14.696 against 14.73 | 0.231% | 0.231% | 0.231% |
| uniform multiplicative Z error, 5 percent | 0.000% | 0.000% | 0.000% |

Only the first row moves. At the declared sigma_p of 45 psia the order is scatter, then bias,
then the psig slip, then the correlation choice, then the standard basis, then nothing. At
22.5 psia the top two swap.

That is a pre-registered inconclusive condition and it triggered. **The ranking of the top two
error sources is conditional on an assumed pressure standard deviation that this case did not
measure and could not measure, because the reservoir is synthetic.** Everything below the top two
is stable across the factor of four in sigma_p tested, and those positions are reportable. The
top two are not.

Three further honesty points on the ranking. The 25 psia calibration bias is a *chosen*
magnitude, justified as 0.25 percent of full scale for a 10,000 psi gauge; a different gauge
class gives a different row. The correlation-choice row is the spread between two published
correlations and DAK, which is not the same quantity as the error against laboratory PVT.
[SUPERSEDED] An earlier version of this paragraph attributed a DAK-against-NIST signed range of
-1.696 to -0.129 percent to `scripts/check.py` "over its sampled corners". Two things were wrong
with that. `scripts/check.py` is the test runner and reports no such figures, so a reader who ran
it to reproduce them would get nothing; the comparison belongs to case A2. And the range is over
all states of that case's reference extract, not over sampled corners. A2 reads a NIST reference
extract that this repository does not redistribute, so **the range cannot be reproduced from this
checkout** and is quoted only as background. It is pure methane over a wide temperature range and
not this 0.65-gravity gas at 200 degF, so it does not transfer directly in any case. What the
comparison supports, and all it supports here, is the qualitative point that a
correlation-against-reference error is wider than a correlation-against-correlation spread and
tilts across the range rather than shifting the level -- so 0.333 percent is a lower bound on the
Z risk rather than an estimate of it. And the whole table is conditional on the tank model
being right. A weak aquifer biases G by 4 to 8 percent at these recoveries according to the
documented case in `docs/evidence/matbal.md`, which is larger than every row of this table added
together, and it does it while improving the apparent straightness of the line. Nothing in this
case tests whether the tank is closed, and the usual field arguments would not settle it either:
the same evidence file records a field case in which no water production and a straight p/Z plot
together suggested a closed tank while the extrapolation was about 16 percent high. Low water
production does not establish a closed tank, and neither does a p/Z estimate that looks stable.

## The next measurement

Projected error budget for four candidate next steps, using the exact least-squares
inverse-prediction identity on the planned abscissa grid. The convention is stated rather than
assumed: the one-sigma random standard error and the absolute value of the systematic shift are
added **linearly**. A bias is not a random variable; adding it in quadrature would understate it.
Both components are given separately so a reader who prefers another convention can recombine.

| Option | random, one sigma | systematic | total |
|---|---|---|---|
| Base programme as it stands | 1.324% | 0.862% | 2.187% |
| Double the survey count at the same depletion (24 surveys) | 0.976% | 0.865% | 1.841% |
| Wait three more years, to 65 percent depletion (15 surveys) | 0.889% | 0.799% | 1.687% |
| Halve the average-pressure scatter (longer shut-ins, more wells) | 0.662% | 0.862% | 1.524% |
| **Calibrate the pressure datum, removing the bias** | 1.324% | 0.000% | **1.324%** |

**The recommendation is the calibration check**, on the projected total and on one structural
argument: it is the only intervention of the four that removes a term instead of shrinking one,
and a term that does not shrink with n is the one that eventually binds.

How much that recommendation is worth, exactly. It wins by 0.200 percent of G over halving the
scatter, and that margin exists only because the table credits the calibration with driving the
systematic to zero. A real dead-weight-tester check and datum reconciliation leaves a residual.
Solving the exact refit for the residual shared offset that consumes the margin gives
**5.83 psia**: if the calibration exercise cannot establish the datum to better than about
6 psia, halving the scatter is the better buy instead. That number is the testable content of the
recommendation, and checking it against what a real calibration can deliver is the first thing to
do with this table.

What this case does not say is which option is cheapest. No cost, day rate, deferred-production
value or budget appears anywhere in the run, the protocol or this report, and the four options
are compared on error percentage alone. The protocol frames the question as "given a fixed
budget" and the case does not close that frame; a reader with cost figures can divide the column
by them.

The reversal conditions. If the calibration check comes back clean, so the bias term really is
near zero, then the base programme is already at 1.32 percent and the ranking is purely about the
random term: the recommendation becomes "wait for deeper depletion". If the residual datum error
is worse than 5.83 psia, it becomes "halve the scatter". And if the assumed sigma_p is materially
wrong in either direction, the top of this table reorders; the first thing the calibration
exercise should produce is a measured sigma_p, at which point this ranking can be recomputed from
a number rather than from an assumption. Halving the scatter, incidentally, means changing how
the volume-averaged pressure is determined -- longer shut-ins, more wells, better build-up
extrapolation. Which link in that chain dominates is an input assumption of this case, which
lumps all of them into one sigma_p, and not something the run can resolve.

## Verification and acceptance

Every acceptance criterion in `protocol.md` section 5 was met.

| ID | Criterion | Observed | Threshold |
|---|---|---|---|
| AC1 | Noise-free x-intercept recovers G | 7.19e-14 | < 1e-9 |
| AC2 | Exact perturbation prediction matches the refit, every offset | 3.05e-16 | < 1e-9 |
| AC3 | psig slip negative and matches its prediction | negative; 1.53e-16 | < 1e-9 |
| AC4 | Uniform multiplicative Z error leaves G unchanged | 3.05e-16 | < 1e-12 |
| AC5 | Delta-method coverage at f = 0.50 | 0.9405 | [0.935, 0.965] |
| AC6 | Fieller coverage at every setting whose error model is the fitted one | [0.941, 0.948] | [0.935, 0.965] |
| AC7 | Delta standard error equals the collapsed closed form | 2.83e-16 | < 1e-12 |
| AC8 | Standard-basis change is exactly the declared standard-pressure ratio | 1.11e-16 | < 1e-12 |
| AC9 | Degraded programme reaches the unbounded Fieller regime | 0.7355 | >= 0.10 |

Three of these need their basis stated plainly rather than left to the table.

*The coverage band.* [0.935, 0.965] is 0.95 plus or minus 0.015. Three Monte Carlo standard
errors at the smallest ensemble any coverage criterion has to cover, 2000 replicates, is 0.0146,
which is what the 0.015 rounds out from. At the 4000-replicate E1 ensembles the same half-width
is 4.35 standard errors, so the band is looser there than three, and AC5's observed 0.9405 sits
2.76 standard errors below nominal -- inside the declared band, but only 0.24 standard errors
inside the tighter band its own ensemble size would justify. The threshold is unchanged; the run
now reports both distances so a reader can apply the tighter one. The run-002 protocol gave the
band's basis as three standard errors at 4000 replicates, which is arithmetically wrong and
looser than it sounds; protocol section 8 records the correction.

*What AC6 covers.* Seven settings: the four E5 depletions, the degraded programme, and E1 at
n = 12 and n = 24. It deliberately excludes E1b, where the AR(1) drift violates the least-squares
model that makes Fieller exact and coverage is 0.544. That exclusion follows the criterion's own
stated basis, and the excluded result is reported in full above, but the run-002 criterion text
read "at every setting", which is broader than the test that was run; it now names the settings.

*What AC9 is.* A confirmation that the unbounded-Fieller code path is exercised by data rather
than described from the literature. The degraded programme's settings were fixed in a scoping
pass for that purpose, so AC9 is not evidence that such programmes arise in practice, only that
the handling works when they do.

Of the three pre-registered inconclusive conditions, one triggered -- the ranking instability
discussed above. The Monte Carlo standard deviation and the median delta-method standard error
agreed to within a factor of 1.09 at f = 0.50 (condition 2 not triggered), and the degraded
programme's refusal rate was 4.7 percent against a 25 percent limit (condition 3 not triggered).

Independence of the oracle. The reference answer for every perturbation is the exact
linear-perturbation form evaluated from the *unperturbed* fit plus the perturbation vector. It
never calls the estimator on perturbed data, so agreement is evidence that the estimator did what
the algebra says and not that two copies of one formula agree with each other. AC7 is a second
independence check of the same kind: the library computes the x-intercept variance twice, once by
the general delta method and once by the collapsed inverse-prediction form, and the two agreed to
2.8e-16 across every fit in this study.

Determinism. `run-004`, `run-005` and `run-006` were executed from the same configuration and
their `summary.json` files are byte-identical, SHA-256 `0fa6192a...`. This is same-machine,
same-interpreter reproduction (CPython 3.13.2, macOS arm64); nothing here establishes determinism
across platforms or Python versions, although the design supports it -- the runner is
standard-library only, with no global RNG state and every draw from a locally seeded
`random.Random`.

Run register. Nothing is deleted and no previous run directory is overwritten.

| Run | Status | What distinguishes it |
|---|---|---|
| run-001 | superseded | First complete execution. Its chronological holdout was taken on the noise-free history, where it is exactly zero by construction and therefore uninformative. |
| run-002 | superseded | Holdout moved to the noisy base realisation. The run the first version of this report quoted, `summary.json` SHA-256 `59322cb1...`. |
| run-003 | retained | Determinism check on run-002, byte-identical to it. |
| run-004, run-005 | superseded | First runs after the review-pass amendments, byte-identical to run-006, but executed before the protocol text and the source formatting were final, so their recorded input digests are not the current ones. |
| run-006 | quoted | The run this report quotes. |

What changed between run-002 and run-006, key by key: one block added under `E4_z_factor` holding
the 401-point correlation scan for both correlations, two multiplicative grid points added (-5 and
+5 percent), two keys added under `E6_standard_basis` for the rounded-ratio gap, four keys added
under `E7_ranking` for the break-even margin, two keys added to the AC5 acceptance entry, seven
limitations added and one extended, and the AC6 and AC8 criterion texts rewritten. One label changed, the ranking
table's multiplicative row, from "2 percent" to "5 percent", because the grid now reaches it. No
acceptance threshold was changed and no previously reported quantity moved: every value common to
the two files is identical. No holdout, calibration window, standard condition or tolerance was
changed in this pass.

## Library observations

No defect was found in `reservoir_lab`. Two observations worth recording.

**`suggested_block_length` at pressure-survey sample sizes.** At n = 12 with independent errors
it returned 3, driven by its rate rule ceil(n^(1/3)), and using that block length inflated the
bootstrap standard error from 1.016 to 2.251 Bscf against a Monte Carlo truth of 1.413. The
docstring states plainly that the combination is a repository heuristic and not a published rule,
and that the rate rule is far too short for a drifting gauge; this run quantifies the cost of the
opposite error at the sample size a survey history actually provides. Nothing to fix, but a case
should not take the recommendation without deciding, from the measurement process, whether the
errors are dependent at all.

**`PZFit` reports the Fieller discriminant but not the Fieller set.** On the degraded realisation
`fit_pz_depletion` did the right thing: it returned `fieller_g = 1.469` and a
`delta_method_interval` warning saying in plain words that the exact set is unbounded and that
the standard error does not describe it. But the object still carries a finite
`gas_in_place_stderr_scf` of 37.8 Bscf and offers no way to obtain the set itself, so a caller who
uses only `material_balance` has to reach into `regression.x_intercept_fieller` to find out what
the data actually support. Given contract C5's rule that a result should be auditable at its own
use site, an optional Fieller field on `PZFit` would close the gap. This is an API observation,
not a defect: the warning is present, correct, and hard to miss.

## What this case does not establish

* It is synthetic throughout. There is no field data, no simulator execution and no third-party
  dataset. Synthetic self-consistency is not field validation.
* The generator and the estimator share the volumetric tank assumption. This is a *measurement*
  error budget, not a test of model adequacy, and a good fit here is a property of the arithmetic.
* **Cumulative production is never perturbed.** The abscissa is the noise-free generated volume
  in every experiment, so this is an error budget on the ordinate of the p/Z line only. Metering
  error, well-to-tank allocation, lease fuel and flare, shrinkage and condensate accounting are
  the other leg of the line and none of them appears anywhere in the ranking. A uniform metering
  error goes into G one-for-one by the E6 rescale identity, so a meter reading 1 percent high
  would sit at the top of the table; a non-uniform one additionally breaks the errors-free
  regressor assumption that ordinary least squares rests on, which biases the slope rather than
  only widening its error bar. This is the largest gap in the case.
* Gas gravity, composition and reservoir temperature are treated as exactly known. An error in
  any of them is a shape error on Z(p), which is the mechanism this case finds matters most, and
  produced gravity does drift over the life of a dry-gas field. E4 varies which correlation is
  applied at a fixed, exactly-known gravity and temperature; it does not vary the gas.
* Every mechanism that biases a p/Z line physically is excluded by construction: aquifer support,
  rock and connate-water expansion, retrograde condensation, multi-tank communication, adsorbed
  gas. At least one of them is larger than everything ranked here, and it makes the line look
  straighter while doing it.
* sigma_p = 45 psia is an assumed representativeness figure for a volume-averaged shut-in
  pressure, not a measured gauge specification. The ranking of the top two error sources is
  conditional on it and reverses at 22.5 psia. It is also one lumped number for the whole chain
  that produces a reported average pressure -- gauge resolution, shut-in duration, build-up
  extrapolation to p-star, well-to-tank averaging -- so the case cannot say which link in that
  chain dominates, and does not.
* The pressure error is homoscedastic and additive in psia across a window running from 4500 down
  to 2071 psia. Build-up extrapolation to p-star gets harder as rate and pressure fall, so a real
  uncertainty is more likely to grow through the history or to scale with pressure -- and a
  proportional error tilts the line rather than scattering it, which by this case's own E4(c)
  result is the damaging mode. No heteroscedastic case was run.
* The estimator is unweighted OLS by declaration. No weighted least squares, no
  errors-in-variables fit and no robust fit was tried, and under a non-constant ordinate variance
  that choice would change every standard error reported here.
* The abscissa grid is evenly spaced, that is, constant offtake. The design formula, the 1/f
  scaling and the 5.06 short-depletion penalty all rest on that geometry. Real survey programmes
  have irregular spacing and shut-in timing that correlates with rate and with the pressures
  being measured.
* The shared calibration bias is treated as one unknown constant of chosen size. No prior is
  placed on it, so the "systematic" column of the next-measurement table is a scenario, not an
  expectation -- and its calibrated row is modelled as leaving no residual at all, which is what
  the 5.83 psia break-even above is there to expose.
* Deviation-factor differences are between published correlations, not against laboratory PVT.
  Nothing here validates any Z correlation against measurement. Case A2's DAK-against-NIST
  comparison is wider than the correlation-choice row used in the ranking, and that comparison
  is not reproducible from this checkout because the NIST reference extract is not
  redistributed with this repository.
* Every percentage is for one synthetic tank: G = 100 Bscf, p_i = 4500 psia, T = 200 degF,
  gamma = 0.65, one depletion window. No sensitivity to initial pressure, temperature or gravity
  was run, so none of the magnitudes is known to transfer to another reservoir. The exact
  Z-level invariance is the exception: it is algebra and holds anywhere.
* The Monte Carlo noise is applied to the reported series only and never feeds back into the
  balance. That is the `NoiseModel` contract; it is not a claim about measurement physics.
* No reserves terminology attaches to any number here. These are estimates of a synthetic `G`,
  which is an inventory in place. Recoverable gas is a different and smaller quantity, set by
  the drive mechanism and the abandonment condition, and reserves are a further commercial and
  regulatory classification of a recoverable volume. None of the three is presented as another.
* No claim of prospective ordering is made beyond internal content linkage. The protocol hash
  inside this case's own run record shows that the committed `protocol.md` is the content the
  run read. It is not an independent trusted timestamp, and it does not exclude retrospective
  construction of both files together.

## Plus, minus, recommendation

**Plus.** One result here is exact and transfers anywhere: the level of Z is irrelevant to a p/Z
gas in place, to machine precision, over a grid running to plus and minus 5 percent, while its
shape is roughly one-for-one. Alongside it the case fixes three conditional but useful numbers
for this reservoir: a psig-for-psia slip makes the reservoir look smaller, by 0.504 percent and
by 1.58 times the common rule of thumb; short observed depletion multiplies the random error by
about 5 between 50 and 10 percent depletion on an even survey grid; and at 4 percent depletion
the exact confidence set is unbounded 74 percent of the time, so the correct engineering output
there is a lower bound rather than an error bar. Every identity-style acceptance criterion held
at machine precision against an oracle that never touched the perturbed data.

**Minus.** The headline ranking is not robust: the top two sources swap when the assumed pressure
standard deviation is halved, which was pre-registered as an inconclusive condition and is
reported as inconclusive. The budget is ordinate-only -- cumulative production is never perturbed,
and a metering bias would enter it one-for-one -- so "what dominates the uncertainty in G" is
answered for the pressure side of the line and not for the volume side. The recommended
intervention wins by 0.200 percent of G on an assumption of perfect calibration, which about
6 psia of residual datum error would erase. The whole study is conditional on a tank model that a
weak aquifer would break by more than every error source measured here combined. And no treatment
survives a drifting gauge: the delta method, the Fieller set and the bootstrap all fail at
rho = 0.8, with coverage falling from 0.94 to 0.54 for both interval methods.

**Recommendation.** Within the study's own frame the next measurement is a calibration and datum
check on the pressure surveys, stated with its break-even: it is worth doing if it can establish
the datum to better than about 6 psia, and the same exercise would produce a measured sigma_p and
so remove the assumption the ranking rests on. For the repository, the next case should be the
abscissa, not the aquifer: put a metering bias and a random metering error through the existing
E7 machinery and onto the same percentage scale as the ranking table. The infrastructure is
already there, the cost is low, and on the E6 identity alone it is likely to change the top row,
which makes it worth more than the water-drive counterexample previously proposed here. The
water-drive case remains the right step after that, because it is the only way to put model error
and measurement error on one scale.

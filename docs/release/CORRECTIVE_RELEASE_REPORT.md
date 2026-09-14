# Corrective release report — claims and interpretation

Scope of this pass: the sentences, not the numbers. A repository-wide claims audit read every
interpretive statement in the case reports, the decision memo and the deviation-factor
evidence card against the committed run output and against `PLAN.md`. It found that the
computational core reproduces and that a number of the sentences written around it claim more
than the runs support. This document records what was corrected, why, which audit finding each
correction closes, and what is still open.

The full row-by-row disposition is `docs/release/disposition_ledger.csv`: 72 findings, with
status, evidence, the change made, the file touched, the check run, and the limitation that
remains.

## What this pass did not do

- **No `results/summary.json` or `results/run_record.json` was edited.** Not one field.
- **No threshold was relaxed** and no acceptance criterion was rewritten to fit an outcome.
- **No number was re-rounded** to make a claim work. Where a number was wrong in prose, the
  prose was corrected to the value the run actually produced.
- **No calculation was changed to improve a claim.** The one case where that temptation was
  real — the holdout predictor that multiplies by the held-out state's own synthetic deviation
  factor — was handled by correcting the label and the surrounding text and leaving the
  arithmetic exactly as it ran.
- **No new experiment was invented to close a scope limitation.** Where the honest answer was
  "this was never measured", that is what the text now says.

## Historical corrections: how the audit trail is kept

This repository's convention is that a record of a run is a record of that run. It is not
edited when a later reading finds the prose around it wrong.

1. **Old run records and summaries were not edited.** `results/summary.json` and
   `results/run_record.json` for A1, A3 and A4 are byte-for-byte what their runs wrote. That
   includes fields the audit showed to be misleading: A4's
   `sigma_*_at_expected_t_equals_critical_*` keys still carry a name that asserts a property
   the number does not have, and A4's `run_record.json` limitations list still says the
   `cases/` tree is untracked in git, which was true when it was written and is not true now.
   Both are corrected in the prose, in place, with a pointer — not by rewriting the artefact.
2. **Superseded statements are marked, not deleted.** Every corrected claim is left where it
   was and marked `[SUPERSEDED]`, with the correction beside it. In `docs/evidence/zfactor.md`
   the refuted body statements are struck through in place and point at the correction section
   that refutes them. A reader who arrives at an old sentence finds the retraction attached to
   it rather than finding a clean document that hides the change.
3. **Corrected outputs get new run IDs.** Nothing in this pass regenerated a result, so no new
   run ID was allocated. If any of the corrections here is later turned into a computed result
   — renaming the two mislabelled `summary.json` keys, adding `s0` so a reader can redo the
   power arithmetic, adding the self-consistent holdout RMSE, re-running E9 with an
   independent seed per level, or adding a pre-registered noisy prefix-drift experiment — it
   must be produced by a fresh run under a new run ID, with the superseded run directory
   retained. Editing an existing `summary.json` to carry a corrected value is not an available
   option.
4. **Checks made during this pass are labelled as such.** A few figures below were recomputed
   from the committed library to retire a false claim. Each is marked in place as a
   correction-pass computation: not pre-registered, not in any `summary.json`, and carrying no
   run ID. They are diagnostics of existing numbers, not new results.

## The corrections

### 1. An arithmetic error in a gate comparison (A4-01)

`+1.26 percent` was stated, in the A4 report and in the decision memo, as inside the 1 percent
gate `PLAN.md` section 12 proposes. It is above it. The backing values are `0.003157` at
J = 0.05 and `0.012636` at J = 0.2; only the first is below `0.01`. Both sentences now keep
J = 0.05 at +0.32 percent as the only row below the gate and state J = 0.2 at +1.26 percent as
above it. The surrounding argument — that the conclusion is about conditions rather than about
the method being useless — survives on one row instead of two, and the memo's reversal
recommendation now says so.

### 2. The borrowed gate is a project demonstration gate (A4-02)

`PLAN.md:289` scopes the 1 percent row by its own words to "the delivered small-noise
demonstration", and `PLAN.md:282` states that these are proposed project gates, not regulatory
requirements or universal engineering tolerances, to be scaled and justified for each case. A4
is a noise-free structural counterexample and never rescaled that row. Every site that cites
the gate now says so, and every site now says what clearing it does and does not establish:
it is a project demonstration result, not evidence of general reservoir-interpretation
adequacy and not evidence of development-decision adequacy. Of the two halves of that PLAN
row, only the holdout half is pre-registered for A4, at `protocol.md:233`; that is now stated
too.

### 3. Four statements, kept apart (cross-cutting)

The reports now open by separating four things that were previously allowed to blur into one
another, and they keep them apart throughout:

- **Numerical verification** — the estimator inverts the forward map its own generator solves,
  to the precision the arithmetic allows.
- **Conditional pressure reconstruction** — a held-out pressure series reconstructed under
  stated conditions, including conditions a field analyst could not meet.
- **Physical interpretation** — what a reservoir is actually doing.
- **Decision adequacy** — whether a number is fit to carry a depletion or development
  decision.

A1 reaches the first. A3 is a measurement error budget and reaches the first, speaking to the
second only in p/Z space. A4 reaches the first and the second. None of the three reaches the
third or the fourth, and none of them may be read as if it did.

### 4. Produced water is not total influx (A4-08, A4-09)

Three quantities were being collapsed into one: cumulative produced water `W_p` at standard
conditions, its reservoir-volume equivalent `W_p * B_w`, and total influx `W_e`. There are two
conversions between them, and the second — `W_p * B_w` to `W_e` — follows only from an aquifer
model or from closing the balance. In A4's own produced-water variant `W_p * B_w` is 30 percent
of `W_e` by declaration, so the produced record understates the influx by a factor of 3.33 and
bounds it from below rather than measuring it.

Two consequences are now written out. **Low water production does not establish a closed tank,
and neither does a p/Z estimate that looks stable** — the repository's own evidence file records
a field case where exactly that pair suggested a closed tank while the extrapolation was about
16 percent high. And **a derived diagnostic plot is not an additional observation**: a Cole or
pot-aquifer plot is a re-plot of the same pressure and production history the p/Z fit already
uses, so it adds information only to the extent that water is separately metered. Neither plot
was run in A4. The metered water record is the new observation; the plots are transformations.

### 5. Inventory, recoverable gas and reserves (cross-cutting)

`G` and `G - G_p` in these cases are inventory in place. Recoverable gas is smaller by whatever
the drive mechanism and the abandonment condition leave behind, and reserves are a further
commercial and regulatory classification of a recoverable volume. All three reports now state
this, and none presents one as another. The A4 trapped-gas bullet, which previously moved
between recoverable and in-place quantities to argue that the case was conservative, is
rewritten around the distinction.

### 6. The estimator fits two parameters, not one (A4-07-1)

The decision memo called `fit_pz_depletion` "an identifiable one-parameter fit". It fits a free
intercept and a free slope, and `G = -a/b` is a derived function of both; the intercept is not
pinned to the measured `p_i/Z_i`, which is why the case's own residual table shows the fitted
line missing the measured initial p/Z by 24.63 psia.

The interpretive claim built on the wrong count is also corrected. Adding an influx term gives
a two-parameter physical fit in `(G, J)`, and that fit is identifiable in principle on
noise-free data. Measured during this pass on the committed generator: a direct least-squares
minimisation over `(G, J)`, with no influx observation supplied at all, returns `G` within
1.0e-11 relative of the truth and `J = 2.0000`, at a residual of 1.8e-9 psia of p/Z. Profiling
over `J` at fixed `G` gives best-fit misfits of 0.57, 1.16, 6.03 and 20.3 psia of p/Z at +0.5,
+1, +5 and +12.5 percent error in `G` — the last being about 20.5 psi rms in pressure, inside
the 10-to-50-psi band the case assumes. So the obstacle is **practical, noise-limited
ambiguity**, not structural non-identifiability, and the reason to measure water is that it
breaks the conditioning.

### 7. Standing 667 versus 677: the measured figures and the unresolved conflict (PVT-03, PVT-04, PVT-11)

The same quantity was stated four mutually inconsistent ways across the repository. The
measured figures, recomputed from the shipped library during this pass over gamma 0.55 to 1.10
at 500 to 6000 psia and 200 degF with Z by Dranchuk-Abou-Kassem, are:

| quantity | value |
|---|---|
| difference in Ppc | 10 psia, 1.53 percent mean over the gravity grid |
| difference in Z, mean | 0.45 percent |
| difference in Z, maximum | 1.15 percent, at gamma 1.10 and 6000 psia |

The maximum sits on the corner of the sampled domain, so it is a lower bound on the maximum
over any wider range, not a bound on it. **A mean is not a bound**, and the three figures travel
together with their domain or not at all. The library comment in
`src/reservoir_lab/gas_properties.py` previously said the difference "propagates to well under
1 percent in Z over the range this project uses" and that it "is not a difference that changes
a decision"; the first is falsified by the 1.15 percent maximum and the second was never that
comment's to assert. Both are withdrawn. Comment text only was changed; no code was touched.

In `docs/evidence/zfactor.md` the card body at three places still instructed that 667 is right
and that a 677 variant "is wrong" and "is NOT supported", while the file's own correction
section records the conflict as unresolved and the claimed Ahmed corroboration as false —
Ahmed prints 677 and reproduces his own worked examples only with 677. Those three statements
are now marked `[SUPERSEDED]` in place, struck through and pointed at the correction, as are
the methane-anchor row that was used as a discriminator and the Standing row of the sources
table. The header is changed from "Corrections applied" to "Corrections recorded", with a note
on reading order, because the body deliberately preserves the original claims. An Ahmed row is
added to the sources table with its access level and the fact that no URL, digest or retrieval
date was recorded.

**The conflict is not resolved and is not presented as resolved.** The original Standing (1977)
has never been read. The library ships both values as named variants and defaults to 677; that
is a documented choice, not a finding.

### 8. Unsupported universal sign claims, withdrawn (A4-04, A4-07, A4-12)

Four directional claims were being stated in the vocabulary of results with no run behind
them. All four are now labelled as arguments or withdrawn:

- **Average-pressure sampling bias.** The claim that surviving-well sampling makes a real
  reservoir "worse, not better" is withdrawn. The counter-argument is available on ordinary
  reservoir physics, and A4's tank model has no areal gradient, so nothing in the case can
  decide the sign. It is now recorded as an untested mechanism.
- **Trapped gas.** Recorded as a recoverable-versus-in-place distinction, which is certain,
  rather than as a measured direction, which is not.
- **Uncertainty methods.** The claim that bootstrapping, weighted regression or an
  errors-in-variables fit "would all narrow or shift" the interval is withdrawn: none was run
  in this case, so no direction is claimed. The argument that survives needs no direction — a
  model-structure error is not represented inside the fitted model, so no interval recomputed
  inside that model can contain it.
- **Drift diagnostic superiority.** The drift rule is now sign-agnostic: look for a material
  move in either direction. Pletcher's published case drifts the other way because his aquifer
  does not deplete over the window. The claim that the drift rule "does not need 10-psi
  pressures" is labelled untested, because its power and size under noise were never measured.

None of these was closed by inventing an experiment. Each scope limitation is documented as a
limitation.

### 9. The closed-form curvature quantity, corrected from its derivation (A4-08-1, A4-08-2, A4-08-3, A4-08-5)

The run computes `sigma* = |c| / (t_crit * sqrt(I_cc))`. The first version of the A4 report
called it the half-power point; the revision that corrected that called it the level at which
the expected statistic equals the critical value, and renamed two `summary.json` keys
accordingly. The second reading is also wrong, and the key name is not evidence for it.

From the derivation: the statistic is `t = c_hat / (s * sqrt(I_cc))` with `s` estimated from
the fit, while the estimator's own standard deviation is `sd(c_hat) = sigma * sqrt(I_cc)`.
Setting `sigma = sigma*` therefore makes `|c| / sd(c_hat) = t_crit` exactly — that ratio is the
**noncentrality parameter**, not `E[t]`. Verified on the case's own base-case design:
`|c| / (sigma* sqrt(I_cc)) = 2.0128955989`, equal to the critical value to eleven figures.

The stated mechanism for the sub-half power was also wrong in sign. For an exactly quadratic
mean, a two-sided t-test on 46 degrees of freedom at a noncentrality of `t_crit` has power
0.504 — above one half. The actual cause is a deterministic lack-of-fit floor: the true p/Z
curve is not a quadratic, so the noise-free quadratic fit already leaves `SSE = 1847.69 psia^2`
on 46 degrees of freedom, `s_0 = 6.34 psia`, with no measurement error at all. That inflates the
estimated residual variance and deflates the effective noncentrality at `sigma*` to 1.838,
0.913 times critical, whose noncentral-t power is 0.436 — against the 0.432 E9 measured at
12.5 psi, inside one Monte-Carlo standard error.

**The measured detection frequencies are preserved unchanged.** Both noise-sweep tables are as
the run produced them. Two further separations are now made explicit: the **empirical crossing**
(11.2 psi is a linear interpolation between measured rates at 11.0 and 11.5 psi; no replicate
was run at 11.2) is distinguished from the **uncertainty in that crossing** (Monte-Carlo only,
covering nothing about design dependence); and the quadrature combination of the two levels'
errors is replaced with the common-mode figure 0.0079/0.071 = 0.11 psi, because E9's ten levels
are one 4000-draw set rescaled ten ways. Re-run from the committed seed during this pass, the
two bracketing levels reproduce 0.51625 and 0.48075 and agree replicate by replicate on 96.5
percent of their reject/accept decisions. E9 therefore inherits the single-draw-set limitation
it was introduced to expose, and that is now disclosed as plainly as it already was for E6.

### 10. Provenance: what the protocol hashes do and do not establish (A4-10-1, A4-11)

A4's prose asserted that the `cases/` tree is untracked in git and drew a pre-registration
limitation from it. The tree is tracked, so the premise is stale. The conclusion survives for
two different reasons, both now stated: A4's `run.py` declares no inputs in its run record, so
nothing machine-written pins `protocol.md` to the runs, and every A4 file entered git in a
single commit, so no commit timestamp separates them either.

**A1 and A4 prospective ordering remains unverified, and nothing was retrofitted to change
that.** A2 and A3 declare `protocol.md` as an input and pin it by SHA-256 inside a record the
run itself wrote. That establishes internal content linkage as recorded — the protocol content
the run read is provably the committed content. It is **not** an independent trusted timestamp
and **not** proof against retrospective construction: this repository has no remote, no tag and
no signature, so every date in it is self-reported. That wording is used in A1 and A3 as well,
and is not strengthened anywhere.

### 11. Review passes and the reported external comparison (A4-11-1, A4-11-2)

Two things were being described in language they had not earned.

The separately implemented tank that the A4 report leaned on for its formulation check is **a
reported comparison that is not reproducible from this repository**. No script, output, digest,
command or log for it exists here. Its quoted digits are withdrawn and the passage is relabelled.
The directory `artifacts/A4_misleading_fit_counterexample/referee-run/` is named for what it is:
a re-execution of the case's own `run.py`, not an independent implementation.

Every review pass on these cases — the numerical pass, the interpretation pass, the pass that
produced the current revision, and this claims audit — was conducted under a different role by
the same author, not by a different person. `AGENTS.md:46` states the rule: different role names
do not create independent expertise or independent evidence. **Separate automated review passes
are not human peer review.** "Independent" and "external" are withdrawn from every description of
a review pass. No human peer review has taken place, no external reviewer participated, and
nothing here is field validation.

### 12. The holdout is a conditional synthetic pressure reconstruction (A4-09-1)

`run.py:625` forms the predicted pressure as `pred * z_factors[i]`, where `z_factors` comes from
`observed(history)` and is `history.true_z_factors[i]` — the noise-free deviation factor at the
*true future pressure*. Future truth enters the predictor. An analyst holding only the
calibration data cannot know Z at a pressure that has not happened yet.

The chronological discipline is real: no tuning of any kind touches the held-out points. What the
row establishes is a **conditional synthetic pressure reconstruction**, not a field-realisable
forecast. The report heading, the results table and the memo's evidence table are relabelled and
the condition is stated. **The calculation was not changed.** The 15.7 psi is the number the
committed run produced, and the self-consistent alternative was not computed, because doing so
would need a new run under a new run ID.

## What remains open

Everything below is recorded rather than fixed, and each has a row in the ledger.

**In the files this pass owns.**

- The 667-versus-677 conflict is unresolved. The original Standing (1977) has never been read,
  and neither side of the conflict rests on a re-checkable retrieval: one text was fetched over
  a host with an expired TLS certificate with verification disabled, the other from a
  file-sharing aggregator with no URL, digest or date recorded.
- The DAK-against-NIST percentages quoted as background in the A1, A3 and A4 reports **cannot be
  reproduced from this checkout**, because the NIST reference extract is not redistributed with
  this repository. They are reattributed to case A2 and flagged; no result depends on them.
- A4's reversal advice now rests on a single sweep row, and that row is one of the two where the
  Fetkovich pseudosteady assumption is least defensible.
- The power and size of the prefix-drift diagnostic under measurement noise are unmeasured.
- The sign of average-pressure sampling bias in a real water drive is unknown and would need an
  areal model.
- Neither the Cole nor the pot-aquifer plot has been implemented or exercised, so this repository
  has no measurement of their power.
- A1's and A4's prospective ordering is unverifiable and is not retrofitted.

**Outside this pass's file list**, and therefore untouched here even where the correction is
known. The ledger names the owner file for each:

- `results/summary.json` and `results/run_record.json` for A4 still carry the mislabelled
  `sigma_*_at_expected_t_equals_critical_*` keys and the stale "cases tree is untracked"
  limitation string. Correcting either needs a new run under a new run ID.
- `cases/A4_misleading_fit_counterexample/protocol.md` carries the same stale premise and lacks
  the noise-model heteroscedasticity note.
- `README.md` and `CHANGELOG.md` state the Standing consequence as "bounded at 0.45 percent" and
  as "0.13-0.23 percent" respectively. Neither is right; the corrected formulation is in this
  document and in the two files this pass owns.
- The one numerical defect in the audit (a de-duplication rule that keeps a stale phase label for
  15 reference states) is in `scripts/fetch_nist_reference.py`.
- The NIST redistribution question, the runner warnings asymmetry, the absence of any executed
  CI, the unpinned lint tooling, the mypy scope, and the stale present-tense guard-test prose
  are all outside this pass.

## How the dispositions were read

The audit filed 72 findings. Its cross-checkers struck 19 sub-claims inside 15 of those findings
as not reproducible and disputed the severity of 23. This pass used the final cross-check
disposition, not the raw filing: no struck sub-claim was "fixed", and a disputed severity was
taken as an argument about how loudly to say something, not about whether it is true. No whole
finding was struck by the cross-check, which is why the ledger's `status` column carries no
`struck` rows — 24 findings are closed as `confirmed` in the files this pass owns, 6 are
`narrowed` because the correction is deliberately narrower than the minimal action proposed, and
42 are `deferred` to the file that owns them.

## Plus / minus / recommendation

**Plus.** Every correction here is either arithmetic that can be checked against a committed
artefact, or a label brought into line with what the code does. Four of them are backed by
numbers recomputed from the shipped library during the pass — the Standing variant grid, the
quadratic lack-of-fit floor, the noncentrality identity, and the two-parameter `(G, J)` fit — so
the claims that replaced the wrong ones are measured rather than asserted. The audit trail is
intact: nothing was deleted, no run artefact was edited, and every superseded sentence is still
where a reader will meet it, with its retraction attached.

**Minus.** This pass fixed sentences. It measured nothing new that is gated, and the largest
weaknesses it documents are unchanged by it: A4's reversal advice is thinner than it was, the
detectability half of A4 still rests on one design and one draw set, the 667/677 conflict is
still open on two unreproducible retrievals, and the mislabelled keys still ship in
`summary.json` because correcting them properly costs a new run. Several corrections are of the
form "this was never measured", which is honest and is not progress.

**Recommendation.** Do not chase the deferred rows one at a time. The cheapest thing that closes
several at once is a single re-run of A4 under a new run ID that renames the two keys, adds
`s_0`, adds the self-consistent holdout RMSE, and re-runs E9 with an independent seed per noise
level — four of the open items, one run, no new science, superseded directory retained. Before
that, though, dogfood what is here: read the three reports end to end as a stranger would and
check whether the four-way separation actually holds up under reading, because that separation
is the load-bearing change in this pass and it has not yet been tested on anyone.

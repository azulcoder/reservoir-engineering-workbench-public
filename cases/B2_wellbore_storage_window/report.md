# Case B2 — wellbore storage, and finding the radial window

**Classification: INCONCLUSIVE**, by protocol §15 applied without reinterpretation.

**Criterion C4 — window detection on the primary noise-free case — failed.** The
pre-registered rule was run as written on the case it was written for, and it declined to
certify a radial-flow window. No threshold was adjusted, no sweep level moved, no experiment
re-specified. That decline is this case's result and it is on the first line of this report
because it belongs there.

## Question

B1 was handed its interpretation window. A real interpreter is not. B2 asks whether a
declared, mechanical, truth-blind rule can find the infinite-acting radial-flow interval in a
drawdown that begins under wellbore storage — and whether the permeability-thickness and skin
read from that interval are good enough to act on.

## Pre-registered expectation

Protocol §10 names B2.1 the *primary proof of concept*: `C_D = 1000`, 48 hours, noise free,
storage and semilog lines crossing at 0.25 h. A 48-hour record was expected to leave ample
radial flow behind that crossover for the rule to find. C4 scores the finding; C5 and C6 score
the `kh` and skin recovered from what C4 finds.

The protocol was committed at `d6624f7`, before any result-producing code existed, and amended
once — `PROTOCOL_AMENDMENT_01.md`, also before any result — to replace a line-source inner
boundary with a finite-radius one, because the line source had no wellbore storage at all at
zero skin.

## What actually happened

The rule returned INCONCLUSIVE:

> no interval reaches the minimum extent: widest was 0.100 log cycles against 1.0 required,
> and the largest held 3 points against 15 required

It declined at every pre-registered smoothing value, `L ∈ {0.0, 0.1, 0.2, 0.3}`. It declined
at every pre-registered sampling density, 5 through 50 points per decade. At `C_D = 3000` it
declined at every pre-registered duration from 3 to 48 hours. Across 800 noisy replicates it
declined 800 times.

**The rule is not broken.** On the storage-free control it finds 4.1 decades and recovers
`kh` to 1.8e-3 relative. It answers when the evidence is there.

| Case | Storage | Certified? | Extent | `kh` error |
| --- | --- | --- | --- | --- |
| B2.0 control | `C_D = 1e-3` | **yes** | 4.100 cycles | 1.85e-03 |
| B2.2 | `C_D = 100` | **yes** | 1.200 cycles | 7.06e-03 |
| **B2.1 primary** | `C_D = 1000` | **no** | — | not reportable |
| B2.2 | `C_D = 3000` | no | — | not reportable |
| B2.2 | `C_D = 10000` | no | — | not reportable |

`kh` and skin are absent from the declining rows deliberately. The rule refused to certify a
window, so there is no analyst estimate to put there, and a number in that column would be a
number no interpreter could have defended.

## Why the numerics are not the explanation

Excluded before the result was accepted as scientific, because a hard stop on an arithmetic
artefact would waste a reader's attention.

| Check | Result | Threshold |
| --- | --- | --- |
| de Hoog at dps 30 / 50 / 80 × degree 18 / 24 / 30 | `p_wD = 10.8781840527` at all nine, identically | — |
| Gaver–Stehfest cross-check on the B2 transform | worst 6.0e-08 | C1, 1e-06 |
| de Hoog on transforms with known exact inverses | worst inside the declared range | C1, 1e-08 |
| Storage-free limit `C_D → 0` | met | C2a, 1e-06 |
| Late-time consistency with B1's closed form | worst 1.6e-05 | C2b, 1e-04 |
| Storage branch `p_wD → t_D/C_D` | worst 5.6e-04 | C3, 1e-02 |
| Zero-skin storage regression | 1.0e-08 | C3b |
| Bourdet chain against the model's analytic derivative, B2.0 window | 3.3e-05 | C7, 1e-03 |
| Determinism, two runs one environment | byte-identical | C8 |

One implementation defect was found this way and is recorded rather than quietly fixed. The
first execution returned **INVALID** because the C3 probe searched the wrong direction, failed
to find its condition anywhere in its bracket, silently collapsed to the bracket's upper bound
and scored the storage branch deep in radial flow, where no storage branch exists. The
criterion's own derivation settled the direction: it predicts the correction to pure storage
is about 0.1 percent, and the early-time reading measures 0.055 percent while the literal
reading measures 99. The probe now checks its bracket instead of assuming it. **The 1000×
factor and the 1e-2 threshold are untouched.**

The Gaver–Stehfest agreement is an **algorithmic inversion cross-check and not an independent
physics oracle**. Both methods invert the same transform, so a formulation error would survive
both.

## Diagnosis

**Wellbore storage contaminates the derivative far longer than the crossover time suggests.**

At `C_D = 1000` the storage and semilog lines cross at 0.25 h. The derivative is still
6.4 percent above the half plateau at 10 h, 1.8 percent at 35 h and 1.3 percent at 48 h. The
approach is algebraic, not exponential — measured over this record it follows

    D − ½  ~  C_D · p_wD / t_D

so each further decade of test time removes one order of the remaining offset and no more.
The frozen rule bounds the derivative's local log-log slope at `ε = 0.0217`; that slope decays
at the same algebraic rate, and inside 48 hours it never gets there for long enough.

**Crossover is not the start of a usable radial interval, and the gap is large.** The classic
`t_D > (60 + 3.5 s) C_D` onset form, applied here, puts the start of the semilog straight line
at 2.2 h — where this model's derivative is still 43 percent above the plateau. That form was
developed for pressure semilog analysis; it is not a derivative-accuracy criterion, and B2
neither uses it nor verified it against an inspected primary source.

## What the analyst can defend

Nothing about the permeability or the skin at `C_D ≥ 1000`. That is the honest content of
the result, and it is narrower than it sounds: **the preregistered evidence standard did not
certify an IARF interval from which to report `kh` and skin.** It is not the claim that `kh`
cannot be estimated.

What the analyst can defend is the decline itself, and its reason, and the fact that the
widest admissible stretch in the record was 0.100 log cycles against the 1.0 required — a
shortfall of an order of magnitude, not a near miss.

## What the hidden truth shows

Scored afterwards, with the generator's truth, which no part of the rule ever sees:

**The data an interpreter needed was present.** The region where the generator's own semilog
departure was already inside the 5 percent `kh` target runs from 1.26 h to 50.1 h — **1.6
decades**, where the rule requires 1.0.

So the two numbers that matter sit side by side:

| | |
| --- | --- |
| Adequate data present, measured ex post | **1.6 decades** |
| Data certifiable ex ante, by the frozen rule | **0 decades** |

An accurate answer existed before the test contained enough evidence to certify it. Those are
different things and B2 exists to keep them apart.

**The plateau-offset observation cannot become a rule.** Saying the derivative is "1.8 percent
above the plateau" requires the plateau, and in pressure units the plateau is
`70.6 q B μ / kh` — the unknown the interpretation exists to estimate. It is a **post-hoc
truth-based diagnostic**, available to a scorer and to nobody else.

## Storage, duration, sampling and noise

**Storage (B2.2).** Of the four pre-registered levels, one certifies. `C_D = 100` yields 1.200
cycles and 7.1e-03 `kh` error. The other three decline, and the reason changes as storage
grows: at `C_D = 1000` there are admissible points but no long enough run of them; at 3000 and
10000 no point is both flat enough and clear of the storage identity at all.

**Duration (B2.3).** At `C_D = 3000`, every truncation — 48, 24, 12, 6 and 3 hours — declines.
The sweep was designed to locate the duration at which the criterion stops being satisfiable;
it found instead that at this storage strength the boundary lies beyond the longest record the
protocol specified.

**Sampling (B2.4).** 5, 10, 20 and 50 points per decade all decline at `C_D = 1000`. Sampling
is not the binding constraint. One structural detail is worth stating: the rule needs 15
points in a window of at least 1.0 decade, so **10 points per decade cannot certify a
one-decade window at any duration** — it would need 1.4 decades of flat derivative before the
point count could be met. That is a property of the rule, derivable from it, and not a
discovery about the physics.

**Noise (B2.5).** Four sigmas, 200 fixed seeds each, 800 records. **800 of 800 returned
INCONCLUSIVE.** Since the noise-free record already declines, this is the expected direction —
noise removes evidence, it does not add it. The result worth recording is the other half:
**not one of the 800 replicates produced a false acceptance.** Noise never assembled a
spurious flat stretch long enough to satisfy the rule. Recovery error is not reported for any
sigma because no seed returned an answer to report it over.

## The deliberately inconclusive control

**B2.6 declined, as designed.** `C_D = 10000` truncated at 3 hours against a 2.9 h crossover.
C10 is met: no permeability and no skin are reported. It declined one condition earlier than
the protocol anticipated — on the storage identity rather than on the extent — which is a
stricter refusal than expected, not a weaker one.

B2.6's role is diminished by B2.1's outcome, and that should be said plainly. A control that
demonstrates the gate closing on a record designed to be hopeless is less informative when the
primary case also had the gate close on it.

## Post-hoc time-to-certification analysis

**POST-HOC EXPLORATORY ANALYSIS. Not pre-registered, and no part of the classification.**

How long would the record have to be before the frozen rule first certifies a window? The
selector was run over progressively longer truncations of a long record, at the pre-registered
sampling and smoothing.

| `C_D` | Crossover | First certifying record | Reported |
| --- | --- | --- | --- |
| 100 | 0.022 h | 31.6 h | about 1.3 days |
| 1000 | 0.254 h | 398 h | **about 17 days** |
| 3000 | 0.813 h | 1259 h | **about 52 days** |
| 10000 | 2.903 h | 4467 h | **about 190 days** |

Verified as the instruction required: the crossing is monotone above it at every level, a
direct rerun at the crossing certifies, and a direct rerun one sampling step below it does
not. A closed-form estimate, `t_D ≈ 2 C_D p_wD / ε`, agrees with a numerical bisection on the
model's own slope to within 8 percent by a route that touches neither the Bourdet chain nor
the selector.

The durations are rounded because the evidence is rounded. The crossing is resolved to one
sampling interval — a factor of `10^(1/20)`, about 12 percent in time — so two significant
figures is already the edge of what the measurement carries.

**Sensitivity is material and is reported rather than smoothed over.** Raising the Bourdet
smoothing from `L = 0.1` to `L = 0.3` pushes the required duration up by a factor of about
1.6 at every level. At 10 points per decade the rule does not certify within the searched
horizon at all, for the structural reason given above. Cadence sensitivity was measured at the
primary storage level only, to bound the numerical inversions that dominate this case's run
time; that bound is stated here rather than left to be inferred from an absent row.

**This is a property of this synthetic model at these declared properties. It is not a field
test-design recommendation and nothing here should be read as one.**

## What this does not establish

- **No field claim of any kind.** Every record is synthetic. No gauge, no well, no field data.
- **The storage levels are a synthetic sweep.** No source inspected in this work establishes
  `C_D` 100 to 10,000 as typical of field practice. An earlier draft of the hard-stop record
  said so on the strength of one vendor documentation page; that page's range sentence is
  uncited, names no class of well, and the claim is withdrawn. See the evidence register §10.2.
- **One log cycle is a project-defined certification criterion**, this project's own, derived from
  the 5 percent `kh` target through `ε = A/(W ln10)` and fixed before results. **It is not an
  industry-standard mandatory minimum.** No log-cycle requirement appears in any primary source
  inspected in this pass. See §10.3.
- **Nothing about other unit-slope mechanisms.** Rule (b) uses the storage identity `D = Δp`,
  not the shape of a slope.
- **Nothing about changing storage, multiphase flow, boundaries, or gas.** All excluded by §16.
- **No external validation.** SAPHIR: **NOT RUN**. External comparator: **NOT SELECTED**.
  Field validation: **NOT PERFORMED**. Peer review: **NOT PERFORMED**.
- **C5, C6 and C7 could not be evaluated on B2.1**, because each is scored over the selected
  window and no window was selected. Not evaluable is not the same as passed.

## Engineering implication

A diagnostic rule honest enough to decline will decline often, and the conditions that make it
decline are ordinary rather than exotic: enough wellbore storage, and a test of normal length.

The value of that is easiest to see by inverting it. A rule that always returns a window would
have returned one here — there was a 0.100-cycle flat patch to return — and the `kh` behind it
would have carried a convincing straight line and no signal that anything was wrong. That is
the failure B1 spent its defect-visibility experiment demonstrating. Bourdet's own paper makes
the same point about pressure plots: it is always possible to find
"several reasonably straight portions on a standard pressure curve" (SPE-12777-PA).

The practical reading, scoped to this model: **check whether the test is long enough to certify
the interpretation before planning to read one from it**, because crossover time will tell you
much earlier than the evidence actually arrives.

## Technical evidence

- Protocol `d6624f7`, amended by `PROTOCOL_AMENDMENT_01.md`. Both digests are re-derived at run
  time and recorded in `results/summary.json`.
- Forward model: finite-radius inner boundary with constant storage and skin,
  `p̄_wD = [K01(√u) + S] / {u[1 + C_D u (K01(√u) + S)]}`, `K01(x) = K₀(x)/(x K₁(x))`, derived
  in `docs/evidence/pta_wellbore_storage.md` §2 rather than cited.
- Inversion: de Hoog–Knight–Stokes, 30 digits, degree 18, frozen in §4.5 before any experiment.
- Window rule: protocol §7, implemented in `src/reservoir_lab/regime.py`, whose signature has
  no parameter through which truth could arrive.
- Run provenance: metrics digest `2a9f5d3d8232311cc8516d010cff91d15f6c42d0242c6a2a3d3ba121d8d8350c`, protocol commit `d6624f7`
  blob `4aa49535`, amendment blob `1d536b0e`,
  mpmath 1.3.0 on the `python` backend.
- Full criterion table, every sweep level and every series: `results/summary.json`.
- The failed expectation and what was eliminated before accepting it: `HARD_STOP_01.md`.

## Reproducibility

Byte-identical reproduction in the pinned canonical container; semantic comparison against the
declared portability envelope elsewhere, with every criterion verdict compared exactly.

**One thing changed in the canonical environment for this case and is declared rather than
assumed.** B2's forward model needs modified Bessel functions at complex argument and a
numerical inverse Laplace transform, neither of which the standard library has, so `mpmath` is
installed in the canonical and portability jobs, pinned to the version in
`requirements-dev.lock`. The library under `src/` is unaffected and still installs with nothing
behind it. mpmath computes in pure Python and switches to a gmpy backend when `gmpy2` is
present, which would change the arithmetic beneath every Bessel evaluation, so the run record
stores the **backend** alongside the version.

## Follow-up hypothesis

Recorded in `docs/planning/B2_FOLLOWUP_WINDOW_RULE.md`, as a plan and nothing more.

The rule bounds the derivative's local **slope**. The gap this case measured — 1.6 decades
adequate, 0 certifiable — suggests it may be bounding the wrong quantity, since a derivative
can sit within 1.8 percent of its final value while its slope is still outside a bound tied to
a 5 percent accuracy target.

**That is a hypothesis and it cannot be tested on this data.** A rule designed after seeing
which cases failed cannot be validated on the cases that shaped it. B2's results are discovery
data for that question, and the follow-up carries a holdout — unseen storage levels, unseen
durations, disjoint noise seeds — to be pre-registered before any candidate rule is written.

The one result the follow-up must not regress: across 800 noisy replicates, the frozen rule's
false-acceptance count was **zero**. Certifying more intervals is only an improvement if that
stays true.

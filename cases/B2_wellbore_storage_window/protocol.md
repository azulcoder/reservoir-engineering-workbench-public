# Case B2 protocol — wellbore storage, and finding the radial window

**Pre-registration. Written and committed before any result-producing B2 code exists.**
No B2 number has been computed. Every threshold below is derived from an analytic error
estimate or from a stated engineering requirement, and none may be changed after a result
exists.

Evidence register: `docs/evidence/pta_wellbore_storage.md`. Every equation used here is
derived there or inherited from B1; five of the nine priority sources for this pass were not
accessible and the register says which.

---

## 1. The question

**Can permeability and skin still be recovered when finite wellbore storage obscures the
early-time response and the analyst must identify the infinite-acting radial-flow window from
the diagnostic response rather than being given it?**

One question. B2 does not ask whether a better estimator exists, and does not ask anything
about gas, boundaries, rate history or real wells.

## 2. The claim under test

That a declared, mechanical rule operating only on data an interpreter actually has can
locate an interval of infinite-acting radial flow in a storage-contaminated record, and that
the parameters recovered from the interval it selects are accurate enough to be useful — or,
when they are not, that the same rule declines to report them.

The second half is not a fallback. B2.6 exists to test it and its expected outcome is
INCONCLUSIVE.

## 3. What B1 established, and what it granted

B1 recovered a known permeability-thickness to `1.564e-06` relative and a known skin to
`1.594e-05` absolute. It did so under two conveniences, both declared in its own protocol and
named in its limitations:

- wellbore storage was **exactly zero by design**;
- the interpretation window was **supplied**, and B1's own placement sweep measured what a
  wrong one costs — the permeability bias scales as `0.5196/t_D,min`, a 3322x spread across
  three and a half decades of placement against 1.18x across a hundredfold change in sampling
  density.

B2 removes both. Nothing else changes.

## 4. Model, stated in full

### 4.1 Physical assumptions

Single vertical well, homogeneous isotropic infinite reservoir, single-phase slightly
compressible fluid of constant properties, constant surface rate, isothermal, gravity and
capillarity neglected, constant finite wellbore storage, steady-state skin as a
rate-proportional pressure drop at the well.

### 4.2 Governing forward model

From Duhamel's principle and the wellbore storage balance (evidence register §2.1):

    p̄_wD(u) = (u p̄_D + s) / { u [ 1 + C_D u (u p̄_D + s) ] }

with the line-source reservoir response `p̄_D(u) = K₀(√u)/u`, giving

    p̄_wD(u) = [K₀(√u) + s] / { u [ 1 + C_D u (K₀(√u) + s) ] }              (B2-1)

**Initial condition** `p_wD(0) = 0`. **Inner boundary** equation (B2-1)'s storage balance,
`1 - q_sfD = C_D dp_wD/dt_D`. **Outer boundary** infinite-acting, `p_D → 0` as `r_D → ∞`.

The line source is chosen over the finite-radius solution for one reason: setting `C_D = 0`
in (B2-1) recovers B1's committed closed form `½E₁(1/(4t_D)) + s` **exactly, at every t_D**,
so the reduction test in §9 is an identity rather than a statement about an asymptotic
regime.

### 4.3 Declared model validity condition

Taking `u → ∞` in (B2-1), `C_D u K₀(√u) → 0` because `K₀` decays exponentially. With `s > 0`
the response tends to `p_wD = t_D/C_D`, the storage-dominated branch. **With `s = 0` it does
not**: the storage term vanishes and the storage-free response is recovered. A line source has
zero wellbore radius, so with zero skin there is no pressure drop at the well to charge the
wellbore.

**B2 is therefore declared valid for `s > 0` only.** A zero-skin case is outside the model.
Criterion C3 tests the storage branch against the declared truth so that this condition can
fail rather than be assumed. This was derived in this pass and has not been checked against an
independent implementation; it is item R1 in the risk register.

### 4.4 Dimensionless groups and conventions

    t_D = 0.0002637 k t / (φ μ c_t r_w²)                       t in hours
    C_D = [5.614583/(2π)] · C / (φ c_t h r_w²)                 C in bbl/psi
    p_D = k h Δp / (141.2 q B μ)

`5.614583/(2π) = 0.8935886`, which is the published `0.8936` to 1.1e-5. As with B1's
`162.6`, `70.6` and `3.2275`, the derivation is stored and the literal is not.

**Skin** enters as a rate-proportional additive offset in `p_D`, identical to B1. **Logs**:
`ln` in the dimensionless solution, `log₁₀` on the semilog plot, and the derivative is taken
with respect to `ln t` throughout. **Pressure** is absolute (psia); drawdown `Δp = p_i - p_wf`
is positive. **Rate** is positive for production.

### 4.5 Numerical inversion

(B2-1) is inverted numerically. The algorithm, its parameter and its accuracy study are an
implementation decision recorded in the decision log before the run; the inversion must
satisfy C1 and C7, which are what make it admissible. All Bessel arguments are real and
positive, so a real-argument inversion is sufficient.

## 5. Generator truth

Identical to B1 except for storage, so that B2.0 is a like-for-like regression.

| | |
| --- | --- |
| permeability `k` | 50 md |
| net thickness `h` | 40 ft |
| porosity `φ` | 0.18 |
| total compressibility `c_t` | 1.5e-5 /psi |
| viscosity `μ` | 1.2 cp |
| formation volume factor `B` | 1.25 rb/STB |
| wellbore radius `r_w` | 0.35 ft |
| initial pressure `p_i` | 4000 psia |
| rate `q` | 350 STB/D, constant |
| skin `s` | **+3.5**, non-zero by model validity (§4.3) |
| storage `C` | varies; `C_D = 67,543 × C` at these properties |

Record span **0.001 h to 48 h**, log-spaced, **20 points per decade** — 4.681 decades, 95
points. The record starts at `t_D = 33`, deep inside storage for every `C_D` studied, so the
storage branch is observed rather than assumed.

B2.0 additionally reproduces B1's exact sampling (50 points per decade over 1 h to 48 h) so
the regression compares like with like.

## 6. The analyst's information set

**No truth reaches the window rule or the estimator.** The rule sees only what an
interpretation of a real test would have.

| Quantity | Generator | Analyst | Analyst estimates | Scoring only |
| --- | --- | --- | --- | --- |
| elapsed time, pressure | yes | **yes** | — | — |
| rate `q`, `B`, `μ`, `h`, `φ`, `c_t`, `r_w`, `p_i` | yes | **yes** | — | — |
| permeability `k` | yes | **no** | yes, from the selected window | yes |
| skin `s` | yes | **no** | yes, from the selected window | yes |
| storage `C`, `C_D` | yes | **no** | not in B2 | yes |
| true start of IARF | yes | **no** | inferred by the §7 rule | yes |
| generator regime labels | yes | **no** | — | yes |
| which experiment this is | yes | **no** | — | yes |

The well and fluid metadata are given because a real interpretation has them — and because
B1's defect-visibility experiment showed that being wrong about exactly these quantities is
silent. B2 does not repeat that experiment; it assumes the metadata correct and says so.

## 7. The window-identification rule

Declared here in full. It is preregistered, mechanical, and takes no argument that depends on
the answer.

Let `Δp(t)` be the drawdown and `D(t) = dΔp/d ln t` the Bourdet derivative at the declared
smoothing `L`. Define the local log-log slope of the derivative,
`m(t) = d ln D / d ln t`, by the same three-point rule applied to `ln D` against `ln t`.

`m` is computed on `ln D` against `ln t` at the same declared `L`. Two consequences are
stated rather than discovered later: where `D ≤ 0` — possible under noise — `ln D` does not
exist and the point is unusable and excluded, and computing `m` from an already-smoothed `D`
compounds the smoothing, so `m` is smoother than the data. Both are limitations of the rule,
not defects to be tuned away, and the `L` sensitivity in §8 is what measures them.

A candidate interval must satisfy **all four**:

**(a) Flatness.** `|m(t)| ≤ ε` at every point in the interval, with

    ε = A / (W ln 10) = 0.05 / (1.0 × ln 10) = 0.0217

`A = 0.05` is the permeability-thickness accuracy target (§10, C5) and `W = 1.0` is the
minimum window extent in log₁₀ cycles from (c). Derived, not chosen: a derivative whose
log-log slope is bounded by `ε` over `W` cycles varies by at most `ε W ln10` in relative
terms, and `kh` is inversely proportional to the plateau.

**(b) Not storage-contaminated.** During pure storage `D = Δp` identically (evidence register
§4). A point is storage-contaminated when

    D(t) / Δp(t) > 0.10

and no candidate interval may contain one. The bound is a declared exclusion strength, not a
tuned one: the storage identity is `D/Δp = 1`, and 0.10 excludes everything retaining more
than a tenth of it — one order of magnitude from the identity. **It is deliberately justified
without reference to the declared truth**, since an interpreter computing it has no truth. An
earlier draft justified it from the plateau ratio at these specific properties, which would
have been truth leaking into the rule under another name. Whether 0.10 is well placed for
these properties is not assumed; C4 and C11 test it.

**(c) Minimum extent.** At least `W = 1.0` log₁₀ cycle and at least 15 points. One cycle is
the span over which (a)'s bound delivers the C5 target; 15 points at 20 per decade is
three-quarters of a cycle of genuine samples, so a flat patch inside the transition cannot
qualify on point count alone.

**(d) Edges.** Points within `L` of either end of the record carry no Bourdet derivative and
are unavailable. No further edge rule is added.

**Selection.** Among all intervals satisfying (a)–(d), take the one of greatest log₁₀ extent;
ties break to the later interval, because a later interval is further from the storage
transition. **If no interval qualifies, the case returns INCONCLUSIVE and reports no
permeability and no skin.**

**A unit slope is not by itself a storage diagnosis.** Rule (b) uses the identity `D = Δp`,
not the shape of a slope. Several mechanisms outside B2's scope produce a unit slope, and B2
makes no claim about distinguishing them; within B2's declared model the identity is
sufficient, and the protocol says so rather than implying generality.

## 8. Derivative settings

Bourdet three-point derivative, SPE-12777-PA Eq. 8, already implemented and tested in this
repository. **`L = 0.1` natural-log cycles**, fixed for every primary result, identical to
B1.

The implementation documents that the smoothing bias is **exactly zero on a radial plateau at
any `L`** — the plateau is affine in `ln t` — and non-zero on a power-law response such as the
storage unit slope. The storage branch is therefore biased by the smoothing and the radial
branch is not. The magnitude at the declared `L` must be computed and recorded before the run;
C7 tests it.

`L ∈ {0.0, 0.1, 0.2, 0.3}` is a preregistered sensitivity, reported separately. **`L` is not
re-chosen per case, and not chosen after seeing a recovery.**

## 9. Parameter recovery

Once the window is selected, interpretation is B1's, unchanged: least-squares straight line of
`Δp` against `log₁₀ t` over the selected interval only; `kh` from the slope via
`162.6 q B μ / m`; skin from the line's value at one hour via the `3.2275` form. Reusing B1's
estimator without modification is what makes B2 a test of window identification rather than a
test of a new estimator.

Every field constant is derived at run time from `141.2`, `0.0002637`, `ln 10` and the
Euler–Mascheroni constant, as B1 does.

## 10. Experiments

| | | |
| --- | --- | --- |
| **B2.0** | storage-free regression | `C_D = 1e-3`. Does (B2-1) reproduce B1? Two forms: pointwise against B1's closed form, and parameter-level over B1's exact window and sampling |
| **B2.1** | constant storage, noise-free | `C_D = 1000` (`C = 0.0148 bbl/psi`, crossover 0.25 h). The analyst must find the window. Primary proof of concept |
| **B2.2** | storage-strength sweep | `C_D ∈ {100, 1000, 3000, 10000}`, crossovers 0.02, 0.25, 0.81, 2.90 h. Spans below the practical field range to its top (`C = 0.0015` to `0.148 bbl/psi`). How much usable radial flow survives? |
| **B2.3** | test-duration sweep | `C_D = 3000` fixed; record truncated at 48, 24, 12, 6, 3 h. When does the criterion stop being satisfiable? |
| **B2.4** | sampling | `{5, 10, 20, 50}` points per decade at `C_D = 1000`. Effect on derivative, window and recovery |
| **B2.5** | pressure noise | `C_D = 1000`; `σ ∈ {0.1, 0.5, 2.0, 10.0}` psi, 200 seeds per level, seeds `20260916 + i` for `i` in `0..199`. Same sigmas as B1 so the two are comparable. **The fraction of seeds returning INCONCLUSIVE is a primary reported output, not a failure**: a rule that declines more often as noise rises is behaving correctly, and recovery error is reported over the seeds that did return an answer, with the fraction stated beside it |
| **B2.6** | deliberately inconclusive | `C_D = 10000`, record truncated at **3 h**, against a crossover of 2.90 h. Usable radial extent is **0.0147 log cycles** against a required 1.0. **Expected outcome: INCONCLUSIVE** |

Four storage levels, five durations, four sampling densities, four noise levels. **Each level
answers a stated question**, and there is no sweep here whose only justification is that it is
cheap.

| Parameter | Levels | Why it varies | Expected effect | Decision it informs |
| --- | --- | --- | --- | --- |
| `C_D` | 100, 1000, 3000, 10000 | Spans below the practical field range to its top; crossover moves 0.02 → 2.90 h | Storage eats a growing share of the record | How much storage the rule tolerates before radial flow is unusable |
| duration | 48, 24, 12, 6, 3 h | Holds physics fixed and removes late data | Usable radial extent shrinks toward the §7(c) minimum | The shortest test that still supports an interpretation at this storage |
| points/decade | 5, 10, 20, 50 | Derivative quality depends on log-spacing | Noisier `D` and `m` at low density; §7(c) point count binds first | Whether sampling or duration is the binding constraint |
| `σ` | 0.1, 0.5, 2.0, 10.0 psi | Same levels as B1, so B2 and B1 are comparable | Regime identification degrades before parameter recovery does | Whether noise breaks the window rule or only the estimate |
| `L` | 0.0, 0.1, 0.2, 0.3 | Smoothing is exact on the plateau and biased on the storage slope | Storage branch biased; plateau unaffected | Whether the primary `L` choice is load-bearing |

## 11. Noise model

Additive, independent, zero-mean Gaussian error on pressure only. **This is a controlled
synthetic assumption and not a field error model.** It is not gauge specification, not model
error, not rate-history error and not time-synchronisation error, and B2 includes none of
those. No statement about field performance follows from B2.5.

## 12. Oracles

| | Oracle | Checks | Independence |
| --- | --- | --- | --- |
| O1 | `C_D → 0` reduction to B1's `½E₁(1/(4t_D)) + s` | Formulation and inversion, at every `t_D` | Exact, analytic |
| O2 | Early-time `p_wD = t_D/C_D` | Storage branch and the `s>0` validity condition | Exact, analytic |
| O3 | Late-time `½[ln t_D + 0.80907] + s` | Radial branch | Exact, analytic, inherited from B1 |
| O4 | Inversion parameter study | Inversion sensitivity only | Weak, shares the formulation |

**Stated limitation.** O1–O3 are analytic limits of the same formulation, so they cannot catch
an error in (B2-1) itself. That equation's defence is its derivation from Duhamel's principle
and the storage balance, not a quoted result. No independently implemented storage solution
was available as an external oracle; see §16.

## 13. Acceptance criteria

Derived before any result exists. **None may be changed after one does.**

| # | Criterion | Threshold | Derivation |
| --- | --- | --- | --- |
| C1 | (B2-1) at `C_D = 1e-3` against B1's closed form, over B1's window | relative `≤ 1e-5` | The analytic storage perturbation there is `≈ C_D u (K₀+s) ≈ 2.6e-7`; the remaining allowance is numerical inversion error, an order above typical double-precision performance on a smooth monotone function |
| C2 | Parameter-level reduction: `kh` from B2 at `C_D = 1e-3`, B1's window and sampling, against B1's committed `2000.0031` md·ft | relative `≤ 1e-4` | B1's own C3 threshold. The perturbation is far below B1's own `1.564e-6` bias, so the recovered value must be indistinguishable from B1's |
| C3 | Storage branch: `p_wD` against `t_D/C_D` where the pure-storage prediction exceeds the storage-free response by **1000x** | relative `≤ 1e-2` | The correction to pure storage is the reservoir response, so at 1000x it is about 0.1 percent and the threshold carries an order of headroom. An earlier draft used 100x, where the expected correction equals the threshold and a correct model could fail. **This is the criterion that can fail the §4.3 validity condition** |
| C4 | Window detection on B2.1 | an interval is found, and every point in it has generator semilog departure `\|p_wD - ½(ln t_D + 0.80907) - s\| / p_wD ≤ 0.05` | The departure is the generator's own, used for scoring only. The bound is the C5 target: a point the estimator could not have interpreted to 5 percent has no business in the window. Scored three ways per §14 |
| C5 | `kh` recovery on B2.1 | relative `≤ 0.05` | The accuracy at which a permeability-thickness is engineering-useful, and the value that fixes `ε` in §7(a) through `ε = A/(W ln10)` |
| C6 | skin recovery on B2.1 | absolute `≤ 0.5` | A slope error `ε_m` gives `Δs ≈ 1.151 ε_m (log₁₀ t_c + 0.4343)`, which at the C5 target and a 10 h centroid is `0.083`. The remaining allowance covers extrapolating the one-hour intercept from a window that begins after storage. 0.5 is also the difference between interpretations that would be acted on differently |
| C7 | Bourdet derivative against the analytic log-derivative of (B2-1), over the selected window | relative `≤ 1e-3` | The algorithm is exact for data affine in `ln t`, which the plateau is; the residual is transition curvature. Two orders below C5 so it cannot mask a `kh` error |
| C8 | Determinism: two runs in one environment | byte-identical | The canonical model already in use |
| C9 | Portability | passes `compare_case_outputs.py` at the declared envelope, and every criterion state identical | The two-tier model already in use |
| C10 | B2.6 returns INCONCLUSIVE | no `k`, no `s` reported | Usable radial extent is 0.0147 cycles against a required 1.0. Reporting a parameter here is a failure of the case |
| C11 | No window is selected inside the storage-to-radial transition on B2.1 | the selected interval starts after the crossover | The transition carries a local inflection where the derivative is briefly flat; §7(c)'s extent requirement must reject it |

### 13.1 Why C5 is not circular

`ε` in §7(a) is derived from the C5 target, and `ε` governs which window is selected, and the
selected window determines the `kh` that C5 scores. That loop is closed but falsifiable, and
it is worth saying exactly why.

`ε` bounds only the **variation of the derivative inside the window**. It does not bound the
semilog bias from where the window sits — B1 measured that as `0.5196/t_D,min` — nor the
Bourdet smoothing bias, nor any residual storage contamination that rule (b) admitted, nor
inversion error. C5 can therefore fail with `ε` satisfied, and if it does, the finding is that
a derivative flat to `ε` is not sufficient for 5 percent on `kh` at these conditions. That is
a real possible outcome of B2 and it is not designed away.

## 14. Three ways a window is scored

Kept apart, because they can disagree and the disagreement is informative.

**Detection** — was any interval found? **Localisation** — how does the selected interval
overlap the region where the generator's own semilog departure is below the C5 target?
**Parameter consequence** — did the selected interval recover `kh` and skin inside C5 and C6?

The primary criterion is parameter consequence. A neighbouring interval that is not the
generator's own labelled region but recovers the right answer is a **success**, not a
near-miss: truth is used for scoring, never for selection.

## 15. Classification

**ESTABLISHED** — C1 through C11 all met. The claim that follows is exactly: *in this model,
at these properties, over this storage range, a declared mechanical rule locates a radial-flow
interval and the parameters recovered from it fall inside the stated accuracy.* Nothing wider.

**INCONCLUSIVE** — the diagnostic criteria do not support a unique radial-flow interpretation.
For B2.6 this is the **expected and correct** outcome, not a failure. Elsewhere it means the
case could not answer its question under the conditions run, and the report says which
condition.

**INVALID** — a verification criterion (C1, C2, C3, C7, C8) fails, so the experiment cannot
support the intended claim. The defect is fixed, the failed run is kept, and a new run ID is
issued.

An INCONCLUSIVE B2.6 with everything else ESTABLISHED is a **successful case**.

## 16. Exclusions

Not in B2, and not implied by it: multiple-rate history, buildup and superposition, Horner
analysis, changing wellbore storage, gas pseudopressure, pseudotime, non-Darcy flow,
rate-dependent skin, fractures, dual porosity, boundaries of any kind, multilayer
interpretation, condensate banking, and real field data.

**Metadata error is excluded and this is deliberate.** B1 measured what wrong rate, net pay,
porosity and viscosity do — five of ten seeded errors were materially wrong and moved no
diagnostic. B2 assumes the metadata correct so that the window rule is the only thing under
test. Nothing in B2 revisits or weakens B1's finding.

**OPEN-SOURCE EXTERNAL COMPARATOR — NOT SELECTED.** `Yous3ry/Pressure_Transient_Analysis`
states no licence, so it is all rights reserved, and independently it implements no forward
model and no Laplace inversion. CAPTAS is GPL and cannot be vendored into this MIT
repository.

**SAPHIR B2 COMPARISON — NOT RUN.** A bridge document and an export will be prepared. Saphir
has not been run and nothing in B2 may be read as a commercial-package comparison.

## 17. Limitations, stated before the result exists

- Synthetic throughout. No field data, no gauge, no real well.
- One model: homogeneous, isotropic, infinite-acting, single phase, constant rate, line
  source, constant storage, steady-state skin. Nothing here establishes behaviour outside it.
- **Valid for `s > 0` only** (§4.3). A zero-skin case is outside the model.
- Constant storage. Real storage changes during a test, and that is not represented.
- The independence is between derivation and implementation, not between this project and the
  world. The data come from a solution this project derived and implemented.
- The noise model is the forgiving one: independent, per-point, zero-mean, pressure only.
- Constant fluid properties. Despite the project's name this is not a gas-well result.

## 18. Planned figures

Five, planned before any data exists. None is rendered yet and no claim below is written as
though its outcome were known.

| | Role | Question | Claim if it succeeds | Data | Encoding | Caveat |
| --- | --- | --- | --- | --- | --- | --- |
| B2-F01 | **hero** | Can a reader see why early time cannot be read as radial flow? | Storage, transition and the selected window are three visibly different things | `Δp` and `D` against `t`, log-log | Two series plus the selected interval shaded | The unit slope is diagnostic only within this model |
| B2-F02 | supporting | Which data actually determine `kh` and skin? | Only the selected interval does | `Δp` against `log₁₀ t`, fitted line over the window only | Selected points solid, excluded points faint | The line is fitted to the window, not the record |
| B2-F03 | supporting | How much usable radial flow survives as storage grows? | Usable extent shrinks in a measurable way | B2.2 sweep | Usable log-cycles against `C_D` | Four levels, not a continuum |
| B2-F04 | supporting | When does the test stop being interpretable? | There is a duration below which the criterion cannot be met | B2.3 sweep | Recovery error and window extent against duration | One storage level only |
| B2-F05 | **hero** | What does declining to answer look like? | The gate refuses where a fit could have been forced | B2.6 | The same log-log plot with no window and no fitted line | The absence is the result |

## 19. Reproducibility

Byte-identical reproduction in the pinned canonical environment; semantic comparison against
the declared portability envelope elsewhere, plus each case's own criteria. Immutable run
directories, no run overwritten. The run record carries this protocol's commit SHA and
re-derives its git blob digest at execution time, as B1's does. Python standard library only
at runtime.

## 20. Risk register

| # | Risk | Detection or control | Remaining limitation |
| --- | --- | --- | --- |
| R1 | The `s = 0` degeneracy (§4.3) was derived in this pass and is unverified | C3 tests the storage branch against the declared truth and can fail | Unverified against an independent implementation |
| R2 | Truth leaking into window selection | §6 information-set table; the rule takes only time, pressure and metadata | Enforced by review and by the estimator's signature, not by a type system |
| R3 | Forward and inverse sharing a defect | The inverse is B1's, already tested against three oracles; the forward is new | A shared convention error would survive both |
| R4 | Derivative smoothing tuned to truth | `L = 0.1` fixed for all primaries; the `L` sweep is preregistered and reported separately | — |
| R5 | An arbitrary flatness threshold | `ε` derived from the C5 target via `ε = A/(W ln10)` | The 5 percent target is an engineering judgement, stated as one |
| R6 | Transition mistaken for radial flow | §7(c) minimum extent; C11 tests it directly | — |
| R7 | Unit slope read as storage in general | §7(b) uses the identity `D = Δp`, not slope; the protocol states the limit of the claim | B2 makes no claim about other unit-slope mechanisms |
| R8 | Numerical inversion error masquerading as physics | C1 and C7; the inversion study in O4 | A formulation error is invisible to all of them |
| R9 | Insufficient duration producing a forced answer | C10, and INCONCLUSIVE as a first-class outcome | — |
| R10 | Field-unit, log-base, radius, sign or convention error | Every constant derived at run time; B1's tests already cover the shared ones | New storage constants are new surface |
| R11 | Portability | C9 and the existing two-tier model | — |
| R12 | Overclaiming field relevance | §15 fixes the exact sentence the case may assert; §17 limitations | — |

## 21. What would change the conclusion

- A C1 or C2 failure would mean (B2-1) does not reduce to B1, and the formulation would be
  wrong before any storage question is reached.
- A C3 failure would mean the storage branch is not `t_D/C_D` for the declared truth, which
  would put the §4.3 validity condition — and the choice of the line source — in question.
- A B2.6 that reported a permeability would mean the gate does not gate, and would invalidate
  the central claim regardless of how well B2.1 performed.
- A C11 failure would mean the extent requirement does not exclude the transition, and the
  window rule would need rederivation rather than retuning.

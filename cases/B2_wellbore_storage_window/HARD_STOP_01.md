# B2 HARD STOP 01 — mandatory noise-free criterion fails on the primary case

**B2 SCIENTIFIC RESULT REQUIRES OWNER REVIEW.**

No threshold has been adjusted. No sweep level has been changed. No experiment has been
re-specified. The frozen protocol was run as written and this is what it returned.

## What was expected

Protocol §10 records B2.1 as the *"primary proof of concept"*: at `C_D = 1000` the storage and
semilog lines cross at 0.25 h, and a 48-hour record was expected to leave ample radial flow
for the pre-registered rule to find. §13 scores that expectation as criterion C4, and C5 and
C6 then score the permeability and skin recovered from the window C4 finds.

## What happened

Criterion **C4 — window detection on B2.1** fails. B2.1 is the primary noise-free case, at
`C_D = 1000` over a 48-hour record, and the pre-registered window rule returns **INCONCLUSIVE**:

> no interval reaches the minimum extent: widest was 0.100 log cycles against 1.0 required,
> and the largest held 3 points against 15 required

## Implementation defects and inversion error are excluded

Checked before writing this, because a hard stop on a numerical artefact would waste an owner
decision.

| Check | Result |
| --- | --- |
| de Hoog at dps 30 / 50 / 80, degree 18 / 24 / 30 | `p_wD = 10.8781840527` identically, `D = 0.50916494` identically |
| Gaver–Stehfest cross-check | agrees to 4e-10 on the pressure |
| finite-difference step refinement 1e-2 → 1e-4 | `D` converges 0.5091650906 → 0.5091649414 |
| storage-free control at the same time | `D = 0.49999682`, i.e. the 0.5 plateau |
| Bourdet chain against the model's own analytic derivative | −0.0174 against −0.0176 at 35 h |
| the rule on a storage-free record | finds 4.1 decades, `kh` error 1.85e-3 |

The rule is not broken and the model is not wrong. Both behave correctly.

## The physical finding behind it

**Wellbore storage contaminates the derivative for far longer than the crossover time
suggests.** At `C_D = 1000` the storage and semilog lines cross at 0.25 h, but the derivative
is still 1.83 percent above the 0.5 plateau at 35 h and 1.35 percent above it at 48 h, with a
log-log slope of −0.013 there. The approach to the plateau is algebraic, not exponential:
measured over this record it follows `D − ½ ∝ 1/t_D`, so each further decade of test time
removes only one order of the remaining offset.

The rules of thumb in circulation are quoted as *one to one-and-a-half log cycles after the
**end of wellbore storage***, which is not the crossover time and is much later than it.
**No rule of thumb was verified against an inspected primary source in this pass**, and none
is used as a criterion here. What can be said without one: the classic
`t_D > (60 + 3.5 s) C_D` onset form, applied at `C_D = 1000`, places the start of the semilog
straight line at 2.2 h, where this model's derivative is still 43 percent above the plateau.

Measured with the frozen rule, over a 48-hour record:

| `C_D` | `C`, bbl/psi | crossover | window found | decades | `kh` error | skin error |
| --- | --- | --- | --- | --- | --- | --- |
| 1e-3 (B2.0) | 1.5e-08 | — | yes | 4.100 | 1.85e-03 | 1.69e-02 |
| 100 | 0.0015 | 0.022 h | yes | 1.200 | 7.06e-03 | 7.31e-02 |
| 1000 | 0.0148 | 0.254 h | **no** | — | — | — |
| 3000 | 0.0444 | 0.813 h | **no** | — | — | — |
| 10000 | 0.1481 | 2.903 h | **no** | — | — | — |

Where the rule does find a window it recovers well inside C5 (5 percent) and C6 (0.5).

A first estimate of how long a test would have to run, taken from the model's own analytic
derivative — the time at which its log-log slope first falls inside `ε`, plus the one decade
the rule's minimum extent needs:

| `C_D` | slope first inside ε | one decade later |
| --- | --- | --- |
| 100 | 2.5 h | 25 h |
| 1000 | 28.3 h | 283 h |
| 3000 | 89.8 h | 898 h |
| 10000 | 317.7 h | 3177 h |

**These are estimates, not measurements, and they run low.** They ignore the Bourdet
smoothing and the rule's 15-point minimum, both of which demand more record than the bare
flatness condition does. Running the frozen selector over truncated records instead puts the
crossings about 1.4 times later. The measured, sensitivity-tested version is the post-hoc
analysis in the case report and it supersedes this table; these rows are only the first
estimate that prompted it.

**Across the tested synthetic storage range above `C_D = 100`, a 48-hour drawdown on this
synthetic reservoir does not yield a radial window certifiable under the pre-registered
rule.**

> **[CORRECTED]** An earlier version of this paragraph read *"Recorded practical field storage
> is roughly `C_D` 500 to 10,000. Across that entire range..."*. That sentence was withdrawn
> during the source audit performed before publication. The range traces to a single
> commercial software vendor's reference page, which states only that *"in practice, a range
> of values from 500 to 10,000 has been observed"* — with no citation, no data, no sample and
> no class of well named. An uncited vendor sentence does not establish a field-practice
> claim. Independently, B2's own sweep is `C_D` 100 to 10,000, which is not the quoted range
> anyway. The statement is now scoped to what was actually run.

## Why this is a hard stop rather than something to fix

The protocol chose `C_D = 1000` for B2.1 expecting a 0.25 h crossover to leave ample radial
flow in a 48-hour test. That expectation was wrong, and it was wrong for a reason that is
itself B2's subject matter. Every available way to make B2.1 pass is a change made after
seeing the result:

- loosening the flatness bound `ε`, which is derived from the `kh` accuracy target;
- shortening the minimum window extent, which is what `ε`'s derivation is tied to;
- moving B2.1 to a smaller `C_D`;
- lengthening the record.

Each would be threshold-moving of exactly the kind this project's B1 report exists to call
out, and §27 of the governing instruction forbids it explicitly.

## What the owner is being asked to decide

The result is not a null. It is a sharper finding than the one B2 set out to demonstrate, and
it arrives at the primary case rather than at the designed limit. Three readings, and the
choice between them is a scientific judgement rather than an implementation one:

1. **Report it as it stands.** B2 classifies INCONCLUSIVE under its own frozen logic: the
   diagnostic criteria do not support a radial interpretation at the declared conditions. The
   finding is that at the storage strengths tested here, a 48-hour record on this synthetic
   reservoir leaves no certifiable radial window — and that a rule honest enough to say so
   will say so often. Whether that carries to real wells is not something B2 can establish.
   B2.6's deliberately-inconclusive case becomes redundant, because B2.1 already is one.

2. **The declared conditions were mis-specified, not the rule.** A 48-hour test was chosen by
   analogy with B1, where storage was zero. Re-specifying the record length is a protocol
   amendment before results are adopted, of the same kind as amendment 01 — but it is being
   proposed *after* seeing a result, which is materially weaker, and it must be recorded that
   way if it is done at all.

3. **The flatness criterion may bound the wrong quantity.** At 35 h the derivative is
   1.8 percent high, which maps to a `kh` about 1.8 percent low — inside the 5 percent target.
   The rule declines where an adequate answer existed.

   **This observation is a POST-HOC TRUTH-BASED DIAGNOSTIC, not a candidate selection rule.**
   Measuring "1.8 percent above the plateau" requires the plateau, and in pressure units the
   plateau is `70.6 q B μ / kh` — it is the unknown the case exists to estimate. An analyst
   holding only the record cannot compute this number. It is therefore evidence about how
   close the answer *was*, and no evidence at all that the answer was *certifiable*. Any
   follow-up rule must reach a comparable judgement from the record alone, and designing one
   against these results makes them discovery data rather than validation data.

Reading 3 is the one I would examine first, because it identifies a possible defect in the
rule's derivation rather than in the physics or the conditions. It is not a change I should
make autonomously: the rule is the pre-registered heart of the case, and rewriting it after
seeing which cases fail is precisely the move the pre-registration exists to prevent.

## State

Implementation is complete and green: the forward model, the inversion layer, the window
selector and their tests all pass. **No B2 result artefact has been written**, no `summary.json`
exists, and nothing has been published. The work is committed so it is not lost; the scientific
decision is the owner's.

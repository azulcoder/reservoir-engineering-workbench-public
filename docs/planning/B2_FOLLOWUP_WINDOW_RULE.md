# Follow-up plan — can a less conservative window rule certify earlier?

**Status: PLANNING ONLY. Nothing here is implemented, no rule is selected, no threshold is
chosen, and no case has been run against any of it.** This document exists so that the
question B2 raised is recorded with its constraints attached, before anyone is tempted to
answer it by adjusting the rule that produced B2.

## Discovery

Case B2 pre-registered a window rule, ran it, and it declined on its own primary case. The
detail that makes a follow-up worth considering is not the decline itself but what sat beside
it.

At `C_D = 1000` over 48 hours the frozen rule certified **no** interval. Scored afterwards
against the generator's truth, the region where the semilog departure was already inside the
5 percent permeability-thickness target ran from 1.26 h to 50.1 h — **1.6 decades**, where the
rule requires 1.0. The data an interpreter needed was present. The evidence that it was
present was not.

That gap is the whole finding, and it has a specific cause. The rule bounds the derivative's
**local log-log slope**. Late in a storage-affected record the derivative approaches its
plateau algebraically, as `D − ½ ~ C_D p_wD / t_D`, so the slope decays only as fast as the
offset does. A derivative can be within 1.8 percent of its final value while its slope is
still outside a bound derived from a 5 percent accuracy target, because slope and offset are
different quantities and `ε = A/(W ln10)` ties the bound to the wrong one.

**None of this licenses relaxing `ε`.** It suggests the rule may be measuring the wrong thing,
which is a different claim, and one that has to be established prospectively.

## Hypothesis

A truth-blind certification rule that reasons about the derivative's **own asymptote** rather
than its instantaneous slope may certify useful intervals from shorter finite-storage records
without materially increasing false regime identification.

## The risk that governs the design

**False acceptance is worse than fewer answers.** A rule that declines leaves an engineer
knowing they do not know. A rule that certifies a transition as radial flow hands them a
permeability with a plausible straight line behind it and no signal that anything is wrong —
which is the failure mode case B1 spent its whole defect-visibility experiment demonstrating.
Any candidate must be scored on false acceptance first and on yield second, and a candidate
that improves yield while admitting one transition interval has failed.

B2 supplies an encouraging baseline the follow-up must not regress: across 800 noisy
replicates at four noise levels, the frozen rule **never once** certified a window on a record
whose noise-free version it had declined. Its false-acceptance rate on that set is zero.

## Candidate evidence to research — not to select

Recorded as a research list. No commitment, no ranking, no thresholds.

| Candidate | Idea | The obvious objection |
| --- | --- | --- |
| Derivative asymptote fit | Fit `D(t) = D∞ + a/t` over the tail and certify when the extrapolated `D∞` is tightly enough determined | Assumes the `1/t` form, which is a model consequence; a rule that assumes the model is not identifying a regime, it is fitting one |
| Nested-window stability | Certify when `kh` from the last half-decade, one decade and two decades agree within the target | Needs the record to be long enough to nest, which may not be cheaper than the current rule |
| Split-window consistency | Fit two halves of a candidate interval separately and require agreement | Cheap and truth-blind, but a slowly drifting derivative is locally consistent everywhere |
| Semilog / derivative consistency | Require the semilog slope and the derivative plateau to agree | Two views of the same data; may be weaker independence than it appears |
| Uncertainty-derived sufficiency | Replace the fixed one-decade extent with the extent at which the `kh` confidence interval is inside the target | Principled, but the interval's width depends on a noise model, and B2's noise model is the forgiving one |

**Shorter required extent and a retuned `ε` are deliberately absent from this list.** Both are
the same rule with a weaker number, chosen after seeing which cases failed, and neither is a
hypothesis.

## Holdout design — prepared, not run

The current B2 data are **discovery data**. Any rule shaped by looking at them cannot be
validated on them; that is the whole reason B2's own rule was pre-registered.

A prospective validation set, small and deliberately so, to be frozen before any candidate
rule is implemented:

| Axis | Held-out levels | Why these |
| --- | --- | --- |
| `C_D` | 300, 5000 — neither used in B2 | Between and above B2's levels, so a rule tuned to 100/1000/3000/10000 cannot have memorised them |
| duration | 72 h and 168 h | Longer than B2's 48 h, in the region where the post-hoc analysis says certification becomes possible and where a candidate rule's yield claim actually bites |
| noise seeds | a seed base disjoint from `20260916 + 0..199` | So no replicate is shared with B2 |
| skin | `s = 0` and `s = 8` | Only if justified: `s = 0` is the case amendment 01 made valid and C3b made mandatory, and a large skin lengthens the transition. Two values, not a sweep |

Three things the holdout must measure, reported separately and never summed into one score:

- **False acceptance** — an interval certified inside the storage-to-radial transition. Scored
  against the generator's own regime boundaries, which exist only in scoring.
- **False rejection** — a record where an adequate interval existed ex post and the rule
  declined. B2's own primary case is the reference example of this.
- **Parameter consequence** — the `kh` and skin error on everything certified, because a rule
  that certifies more intervals at worse accuracy has not improved anything.

The holdout is to be pre-registered with its acceptance criteria, in the form B2 used, and
committed before the candidate rule exists.

## What this document does not do

It does not choose a rule. It does not choose a threshold. It does not implement or run
anything. It does not revise B2, whose result stands as measured under the rule that was
frozen before it.

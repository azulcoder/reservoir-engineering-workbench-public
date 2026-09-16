# B2 protocol — adversarial review before the pre-registration commit

Run against the protocol draft before it was committed. Every finding is recorded with its
disposition, including the ones that were fixed, so that the fixes are visible rather than
silently folded in.

| # | Attack | Finding | Disposition |
| --- | --- | --- | --- |
| A1 | Does truth leak into the window rule under another name? | **Yes.** The storage-exclusion bound of 0.10 was justified from the radial plateau ratio *at the declared truth*, using `s = 3.5` and the truth's `t_D` range. An interpreter has neither | **FIXED.** Re-justified as a declared exclusion strength one order of magnitude from the storage identity `D/Δp = 1`, with no reference to truth. C4 and C11 test whether it is well placed |
| A2 | Is any threshold set where a correct model would fail? | **Yes.** C3 defined its interval at 100x, where the expected physical correction is about 1 percent and the threshold was also 1 percent — no headroom | **FIXED.** Interval moved to 1000x, where the correction is about 0.1 percent, giving the threshold an order of headroom |
| A3 | Is any criterion scored against an undefined quantity? | **Yes.** C4 scored "semilog departure" without saying departure of what, measured how | **FIXED.** Defined as the generator's own relative departure from its semilog asymptote, bounded by the C5 target, and marked scoring-only |
| A4 | Can the window rule be evaluated at all points it claims to? | **No.** `m = d ln D/d ln t` does not exist where `D ≤ 0`, which noise can produce, and computing `m` from an already-smoothed `D` compounds the smoothing | **FIXED.** Both stated in §7: non-positive derivative points are excluded, and the compounded smoothing is named as a limitation the `L` sensitivity measures |
| A5 | What happens to a noise realisation that returns INCONCLUSIVE? | Undefined. B2.5 would have had no rule for scoring them, and the tempting move is to drop them, which would bias the reported error downward | **FIXED.** The INCONCLUSIVE fraction per noise level is a primary reported output; recovery error is reported over the seeds that answered, with the fraction stated beside it |
| A6 | Is C5 circular? `ε` is derived from the C5 target, selects the window, which determines the `kh` C5 scores | Closed but falsifiable — and the protocol did not say why | **FIXED.** New §13.1 names the four error sources `ε` does not bound: window placement bias, Bourdet smoothing bias, admitted storage contamination, and inversion error. C5 can fail with `ε` satisfied, and that outcome is not designed away |
| A7 | Can the case return INCONCLUSIVE? | Yes — §7 selection, C10, and §15 make it a first-class outcome with B2.6 expecting it | No action |
| A8 | Is a unit slope treated as synonymous with storage? | No — §7(b) uses the identity `D = Δp`, and §7 and R7 state that other mechanisms produce the same shape and that B2 claims nothing about them | No action |
| A9 | Is the same implementation acting as its own oracle? | **Partly, and unavoidably.** O1–O3 are analytic limits of the same formulation and cannot catch an error in (B2-1) itself | **DEFERRED WITH LIMITATION.** Stated in §12 and §17. The formulation's defence is its derivation from Duhamel plus the storage balance, not a quoted result. No independently implemented storage solution was available; the Saphir bridge would close it and is NOT RUN |
| A10 | Is any numerical tolerance larger than the scientific margin it protects? | No. C7 at 1e-3 is two orders below C5 at 0.05; C1 at 1e-5 is tighter than C2 at 1e-4 | No action |
| A11 | Is an unverified literature rule load-bearing? | No. The `t_D > 60 C_D e^{0.14 s}` onset criterion could not be verified from any accessible source and is used nowhere — not as a threshold, a default, or a sanity check | No action. Recorded in the evidence register |
| A12 | Is there an impossible field claim? | No. §15 fixes the exact sentence the case may assert and §17 lists what it does not establish | No action |
| A13 | Is the `s = 0` degeneracy assumed rather than tested? | It was derived in this pass and is unverified against an independent implementation | **DEFERRED WITH LIMITATION.** C3 tests the storage branch for the declared truth and can fail; R1 records the residual risk |

**No HARD STOP finding.** Six fixes applied in place, two deferred with the limitation stated
in the protocol.

## Post-review finding, found after this pass

| # | Attack | Finding | Disposition |
| --- | --- | --- | --- |
| A14 | Was the forward model chosen for a physical reason or a convenient one? | **Convenient.** The line source was adopted because `C_D → 0` then reproduced B1 exactly, and the same pass derived that it has no storage at `s = 0` and declared the region out of scope rather than fixing the model. A case about wellbore behaviour was given an inner boundary with no wellbore | **FIXED before implementation.** Finite-radius inner boundary adopted, derived and verified; `s = 0` becomes a mandatory regression (C3b) instead of an excluded region. `PROTOCOL_AMENDMENT_01.md` |

A13 in the table above is superseded by A14: the `s = 0` degeneracy is no longer a deferred
limitation, because the model that produced it is no longer the model.

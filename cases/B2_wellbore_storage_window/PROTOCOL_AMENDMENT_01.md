# B2 protocol amendment 01 — finite-radius inner boundary

**PROTOCOL AMENDED BEFORE RESULT-PRODUCING IMPLEMENTATION.**

No B2 code existed when this was written and none exists now. No B2 number has been computed.
The original protocol is kept unaltered at its commit; this amendment records what was wrong
with it, what replaced it, and why the correction had to happen before implementation rather
than after.

| | |
| --- | --- |
| original protocol commit | **`d6624f7`** — `cases/B2_wellbore_storage_window/protocol.md`, one file |
| original evidence register | `6cc6e25` |
| original adversarial review | `aec7f54` |
| status when the issue was found | pre-registration merged to no branch, **no implementation begun** |

## 1. The issue

The original protocol used a **line-source** reservoir response inside the storage transform:

    p̄_wD(u) = [K₀(√u) + S] / { u [1 + C_D u (K₀(√u) + S)] }                (original)

The same research pass that adopted it also derived that it develops a storage-dominated
period **only when `S ≠ 0`**, and recorded that as a declared validity condition with a
criterion able to fail it (original §4.3, C3, risk R1).

Recording the defect was right. **Adopting the model anyway was not.**

## 2. Why the original choice was wrong

The reason given for the line source was that `C_D → 0` then recovers B1's committed closed
form *exactly at every t_D*, making the reduction test an identity rather than an asymptotic
statement.

That is a reason about **test convenience**, not about physics. B2 exists to study wellbore
behaviour, and it was given an inner boundary with no wellbore. The convenience was bought
with a model that cannot represent the zero-skin case at all, and the protocol then declared
the broken region out of scope rather than fixing the model.

## 3. Evidence consulted

Primary well-test sources were again largely unreachable — OnePetro returned HTTP 403 and the
ScienceDirect topic page returned 403. Rather than rest on a citation that could not be read,
the formulation was derived and verified directly.

**(a) The general transform is not in question.** From Duhamel's principle and the storage
balance, with `p̄_D` the reservoir's constant-unit-rate response at the well:

    p̄_wD(u) = (u p̄_D + S) / { u [1 + C_D u (u p̄_D + S)] }

This was confirmed algebraically identical, to 35 digits, to the candidate form circulated
for review. **Only the choice of `u p̄_D` was wrong.**

**(b) The finite-radius response, derived and verified.** The diffusivity equation in Laplace
space, bounded at infinity, gives `p̄_D = A K₀(r_D √u)`. The constant-unit-rate inner boundary
at `r_D = 1` requires `-∂p̄_D/∂r_D = 1/u`, and since `∂/∂r_D K₀(r_D x) = -x K₁(r_D x)`,

    A x K₁(x) = 1/u   ⟹   A = 1/(u x K₁(x))   ⟹   u p̄_D = K₀(x)/(x K₁(x)) ≡ K01(x)

with `x = √u`. The boundary condition was verified numerically at `u = 0.01, 1, 100`: the
computed flux equals `1/u` to better than 1e-30 relative in all three.

**(c) The line source is its `r_w → 0` limit.** `x K₁(x) → 1` as `x → 0` (verified: 0.99974 at
`x=1e-2`, 1.0 at `x=1e-8`), so `K01(x) → K₀(x)`. **The factor `x K₁(x)` is the well's finite
surface.** Dropping it removes the well's ability to sustain a pressure drop at early time,
which is the mechanism of the `S = 0` degeneracy — not a coincidence, and not a corner case.

**(d) Numerical confirmation of the defect and the fix.** With `C_D = 1000`, storage requires
`u² p̄_wD → 1/C_D = 0.001` as `u → ∞`:

| `u` | `S` | line source | finite radius |
| --- | --- | --- | --- |
| 1e6 | 0 | 2.0e-430 | 0.000999999 |
| 1e10 | 0 | 1.4e-43422 | 0.00099999999 |
| 1e6 | 3.5 | 0.001 | 0.001 |
| 1e10 | 3.5 | 0.001 | 0.001 |

The line-source form collapses to zero at `S = 0` — no storage at any time. The finite-radius
form converges to `1/C_D` exactly. At `S = 3.5` both work, **which is why the original
protocol's declared truth masked the defect**.

## 4. Original model and amended model

| | Original | Amended |
| --- | --- | --- |
| inner boundary | line source, `r_w → 0` | **finite radius**, `r_D = 1` |
| `u p̄_D` | `K₀(√u)` | **`K01(√u) = K₀(√u)/(√u K₁(√u))`** |
| well radius | not represented in the response | `r_w` is the length scale of `r_D` |
| `S = 0` | degenerate, declared out of scope | **valid; now a mandatory regression** |
| `C_D → 0` against B1 | exact identity at every `t_D` | approaches the storage-free finite-radius solution; B1 consistency becomes a derived late-time check |

## 5. What is unchanged

- **The central question is unchanged.** Can permeability and skin be recovered when storage
  obscures early time and the analyst must identify the radial window?
- The experimental intent, the seven-experiment sequence and every sweep level.
- The analyst information set and the no-truth-leakage requirement.
- The window-identification rule's structure, its derived flatness tolerance, and the
  truth-leak correction made in the original adversarial review.
- The derivative method and settings.
- The parameter-recovery method, which remains B1's unchanged.
- ESTABLISHED / INCONCLUSIVE / INVALID, and B2.6's expected INCONCLUSIVE outcome.
- Exclusions, Saphir status and the external-comparator decision.

## 6. Affected criteria, oracle and reduction test

Re-derived in the revised protocol §13, each with OLD, NEW, REASON, DERIVATION, and why the
change occurs before results. Summary:

- **C1** forward-vs-oracle becomes inversion qualification against transforms with known exact
  inverses, plus the finite-radius zero-storage limit.
- **C2** becomes the derived late-time B1 consistency check rather than an exact identity.
- **C3** storage branch is retained and strengthened, because it now has to hold at `S = 0`
  as well.
- **C3b** is new and mandatory: `S = 0, C_D > 0` must produce storage, a transition, and a
  coherent finite response. This directly attacks the defect that motivated the amendment.
- **O1** becomes the finite-radius zero-storage limit. **O4** is renamed an *algorithmic
  inversion cross-check*, not an independent physics oracle.

## 7. Why this is recorded rather than edited away

The original protocol is evidence. It records a model choice made for a stated reason, a
defect found by the same pass that made the choice, and a decision to proceed anyway. Editing
it would remove the only record that the reasoning was once wrong and how it was caught.

The chronology `6cc6e25` → `aec7f54` → **`d6624f7`** → this amendment → revised protocol is
preserved, and the original commit is not amended, rebased or squashed.

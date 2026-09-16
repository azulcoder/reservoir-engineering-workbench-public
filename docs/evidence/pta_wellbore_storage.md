# Evidence register — wellbore storage, skin, and radial-flow identification

Supporting case B2. Written before the B2 protocol and before any B2 implementation.

Convention, as in `pta_line_source.md`: every source carries an access status, nothing is
claimed from metadata alone, and anything that can be derived is derived here rather than
cited. Where a widely repeated rule could not be verified from an accessible source, that is
said plainly and the rule is not used.

---

## 1. Source register

| # | Source | Access | What it is used for |
| --- | --- | --- | --- |
| S1 | Agarwal, R.G.; Al-Hussainy, R.; Ramey, H.J. Jr. *An Investigation of Wellbore Storage and Skin Effect in Unsteady Liquid Flow: I. Analytical Treatment.* SPE Journal 10(3), 1970, 279–290. DOI 10.2118/2466-PA | **METADATA ONLY** — OnePetro returned HTTP 403; abstract and figures not reached | Establishes that the storage-and-skin early-time problem has a standard analytical treatment. **No equation is taken from it.** |
| S2 | Bourdet, D.; Ayoub, J.A.; Pirard, Y.M. *Use of Pressure Derivative in Well-Test Interpretation.* SPE Formation Evaluation, 1989. SPE-12777-PA | **FULL TEXT INSPECTED** in the B1 pass; see `pta_line_source.md` | The three-point derivative algorithm (Eq. 8) and the L point-selection rule, already implemented and tested in this repository |
| S3 | S&P Global / IHS WellTest documentation, *Dimensionless Wellbore Storage Constant* | **PARTIAL** — prose reached, the defining equation is an inaccessible image | Practical range of `C_D` in the field, quoted as roughly 500 to 10,000. Used only to choose plausible sweep levels, never as a derivation |
| S4 | ScienceDirect topic pages, *Wellbore Storage Effect* and *Infinite Acting Radial Flow* | **PARTIAL** — summary text only | Confirms `C_D e^{2s}` as the early-time correlating group, and records the common "two log cycles after the unit slope ends" rule of thumb |
| S5 | Bourdet, D. *Well Test Analysis: The Use of Advanced Interpretation Models* | **NOT ACCESSED** | — |
| S6 | Horne, R.N. *Modern Well Test Analysis* | **NOT ACCESSED** | — |
| S7 | Lee, J.; Rollins, J.B.; Spivey, J.P. *Pressure Transient Testing* | **NOT ACCESSED** | — |
| S8 | Earlougher, R.C. *Advances in Well Test Analysis* | **NOT ACCESSED** | — |
| S9 | KAPPA / Saphir official documentation | **NOT ACCESSED** | — |

**Five of the nine named priority sources were not reached.** Every equation B2 uses is
therefore derived below from first principles, or inherited from B1 where it was already
established. Nothing in B2 rests on a source this pass could not read.

### A rule that is deliberately not used

A numeric onset criterion of the form `t_D > 60 C_D e^{0.14 s}` is widely quoted for the
start of infinite-acting radial flow. **It could not be verified from any source reached in
this pass.** It is recalled, not confirmed, and B2 does not use it — not as a threshold, not
as a default, and not as a sanity check. The window rule in section 6 is derived instead.

The "two log cycles after the unit slope ends" rule (S4) is a rule of thumb by its own
description. It is recorded for orientation and is not a criterion.

---

## 2. The forward problem, derived

### 2.1 Storage and skin as an inner boundary condition

Let `q` be the constant surface rate and `q_sf(t)` the sandface rate. Fluid stored in the
wellbore accounts for the difference:

    q - q_sf = (C / B) dp_w/dt

with `C` the wellbore storage coefficient. In dimensionless form, with
`q_sfD = q_sf / q`,

    1 - q_sfD = C_D dp_wD/dt_D                                            (1)

Let `p_D(t_D)` be the reservoir's dimensionless pressure response at the well for a constant
unit rate. For a time-varying sandface rate, Duhamel's principle gives the sandface pressure,
and the skin adds a rate-proportional drop:

    p_wD(t_D) = ∫₀^{t_D} q_sfD(τ) p_D'(t_D - τ) dτ + s q_sfD(t_D)         (2)

Transforming (2), with `L{p_D} = p̄_D`:

    p̄_wD = q̄_sfD (u p̄_D + s)                                            (3)

Transforming (1), with `p_wD(0) = 0`:

    1/u - q̄_sfD = C_D u p̄_wD   ⟹   q̄_sfD = 1/u - C_D u p̄_wD            (4)

Substituting (4) into (3) and solving for `p̄_wD`:

    p̄_wD(u) = (u p̄_D + s) / { u [ 1 + C_D u (u p̄_D + s) ] }             (5)

Equation (5) is the whole forward model. It is derived here, not cited.

### 2.2 The reservoir response B2 uses

B1 uses the line source, for which `p_D(t_D) = ½E₁(1/(4t_D))` and

    p̄_D(u) = K₀(√u)/u        so       u p̄_D = K₀(√u)                     (6)

Substituting (6) into (5):

    p̄_wD(u) = [K₀(√u) + s] / { u [ 1 + C_D u (K₀(√u) + s) ] }            (7)

**Why the line source rather than the finite-radius solution.** Setting `C_D = 0` in (7)
gives `p̄_wD = [K₀(√u) + s]/u`, which inverts exactly to `½E₁(1/(4t_D)) + s` — B1's committed
solution, at every `t_D`, with no asymptotic gap. The finite-radius solution converges to
B1's only for large `t_D`, which would make the reduction test in section 5 a statement about
an asymptotic regime rather than an identity. The exact reduction is worth more here than
conformity with the type-curve literature's usual choice.

### 2.3 A validity condition that falls out of the derivation, and can fail

Take `u → ∞` in (7), which is `t_D → 0`.

`K₀(√u) ~ √(π/2) u^{-1/4} e^{-√u}` decays faster than any power of `u`, so
`C_D u K₀(√u) → 0`.

- **With `s > 0`:** the numerator tends to `s` and the denominator to `u(1 + C_D u s) ≈ C_D s u²`,
  so `p̄_wD → 1/(C_D u²)`, which inverts to

        p_wD = t_D / C_D                                                  (8)

  This is the storage-dominated response. The model produces it.

- **With `s = 0`:** `C_D u K₀(√u) → 0` leaves `p̄_wD → K₀(√u)/u`, the storage-free response.
  The model produces **no** storage-dominated period at asymptotically early time.

The physical reading is consistent: a line source has zero wellbore radius, so with zero skin
there is no pressure drop at the well to charge the wellbore, and nothing is stored.

**Consequence for B2.** The formulation is valid for `s > 0` and degenerate at `s = 0`. B2's
declared truth carries `s > 0`, as B1's did. This is stated as a model validity condition,
and B2 criterion C3 tests equation (8) against the declared truth so that the condition can
fail rather than be assumed.

This was derived in this pass and has not been checked against an independent implementation.
It is listed in the B2 risk register.

---

## 3. Dimensionless storage coefficient, derived

    C_D = C / (2π φ c_t h r_w²)

in consistent units. With `C` in bbl/psi and lengths in feet, converting barrels to cubic
feet with 1 bbl = 5.614583 ft³:

    C_D = [5.614583 / (2π)] · C / (φ c_t h r_w²) = 0.8935886 · C / (φ c_t h r_w²)

The published field constant is quoted as 0.8936 (S3, S4). The derived value agrees to
1.1×10⁻⁵, which is a rounding of the published figure rather than a different number. As with
B1's `162.6`, `70.6` and `3.2275`, B2 stores the derivation and not the literal.

---

## 4. The storage signature, derived

During pure storage all production comes from the wellbore, so in field units

    Δp = q B t / (24 C)

with `t` in hours, `q` in STB/D, `B` in rb/STB and `C` in bbl/psi. Two consequences follow
immediately and neither is a rule of thumb:

**Unit slope.** `log Δp = log t + log(qB/24C)`, so the pressure change has slope exactly 1 on
a log-log plot.

**The derivative overlies the pressure change.** The Bourdet derivative is taken with respect
to `ln t`, so

    dΔp/d(ln t) = t dΔp/dt = t · qB/(24C) = Δp                            (9)

During pure storage the derivative curve and the pressure-change curve coincide. In
dimensionless form, `p_wD = t_D/C_D` gives `dp_wD/d ln t_D = t_D/C_D = p_wD`.

Equation (9) is what B2's window rule uses to exclude storage-dominated data. It is an
identity, not an appearance.

---

## 5. The radial limit, inherited

B1 established, and this repository already implements and tests:

    p_wD → ½[ln t_D + (ln 4 - γ)] + s = ½[ln t_D + 0.80907] + s

with the departure from the semilog asymptote exactly `1/(8 t_D)`, and the dimensionless
log-derivative `½exp(-1/(4t_D))`, approaching `½` from below with deficit `1/(8t_D)`.

B2's forward response must approach this same limit at late time, since (7) reduces to B1's
solution when the storage term becomes negligible. That gives B2 a late-time analytic oracle
without any new derivation.

---

## 6. Identifying the radial window without the answer

The requirement is a rule that selects a candidate interval using only what an interpreter
has: elapsed time, pressure, the derivative computed from them, and the well and fluid
metadata. Not the true permeability, not the true skin, not the true regime boundaries.

Four ingredients, each with a reason:

**(a) Flatness of the derivative.** In radial flow the derivative is constant, so its
log-log slope is zero. Let `m(t) = d ln(dΔp/d ln t) / d ln t`. Radial flow requires `|m| ≤ ε`.

The tolerance is derived rather than chosen. Over a window spanning `W` log₁₀ cycles, a
derivative whose log-log slope is bounded by `ε` changes by at most a factor `10^{εW}`, so
the relative variation is about `εW ln10`. Permeability-thickness is inversely proportional
to the derivative plateau, so a target relative accuracy `A` on `kh` requires

    ε ≤ A / (W ln 10)                                                     (10)

with `A` and `W` fixed in the protocol before any run.

**(b) Exclusion of storage-dominated data.** By equation (9), storage-dominated points have
`dΔp/d ln t ≈ Δp`. Points where the ratio `(dΔp/d ln t)/Δp` exceeds a declared bound are
storage-contaminated and excluded. This uses the identity, not a slope guess, and it is the
reason B2 does not need the unverified onset rule.

**(c) Minimum extent.** A window must span at least a declared number of log cycles and
contain at least a declared number of points, so that a short flat patch inside the
transition cannot be mistaken for the regime.

**(d) Edge exclusion.** The Bourdet derivative already omits points within `L` of either end
of the record. No further edge handling is introduced, and the omission is inherited.

A unit slope alone is **not** treated as proof of storage. The rule requires the unit-slope
behaviour, the derivative-to-pressure identity (9), and the position of the interval in the
record to agree before an interval is classified. Slope on its own is a shape, and several
mechanisms outside B2's scope produce the same shape.

If no interval satisfies (a) through (d), the case returns INCONCLUSIVE. That outcome is a
result, not a failure.

---

## 7. What verifies the forward model

Ranked by strength, with the independence limit of each stated.

| | Oracle | What it checks | Independence |
| --- | --- | --- | --- |
| O1 | `C_D → 0` reduces (7) to B1's `½E₁(1/(4t_D)) + s` | The whole formulation and the inversion, at every `t_D` | Exact and analytic. Shares B1's line-source assumption, which B1 verified against an arbitrary-precision oracle |
| O2 | Early-time limit `p_wD = t_D/C_D`, equation (8) | The storage branch, and the `s > 0` validity condition | Exact and analytic; derived here |
| O3 | Late-time semilog limit, section 5 | The radial branch | Exact and analytic; inherited from B1 |
| O4 | Numerical inversion at two or more parameter settings, with a convergence study | Sensitivity of the inversion, not of the formulation | Weak — shares the formulation |

**Stated limitation.** O1 through O3 are analytic limits of the same formulation. They can
catch an implementation error, an inversion error and the `s = 0` degeneracy. They cannot
catch an error in equation (5) or (7) itself, because they are derived from it. The
formulation's own defence is the derivation in section 2, which proceeds from Duhamel's
principle and the storage balance rather than from a quoted result.

No independently implemented storage solution was found that could be used as a true external
oracle. The Saphir bridge would close this and has not been run.

---

## 8. External comparator

**OPEN-SOURCE EXTERNAL COMPARATOR — NOT SELECTED.**

| Candidate | Finding |
| --- | --- |
| `Yous3ry/Pressure_Transient_Analysis` (GitHub) | **No licence file or licence statement**, so it is all rights reserved by default and cannot be used or vendored. Independently, it analyses supplied gauge data and implements no forward model and no Laplace inversion, so it could not serve as a forward comparator even if it were licensed |
| CAPTAS | GPL, recorded in `pta_line_source.md`. Cannot be vendored into this MIT repository |

Neither is usable. B2 proceeds with the oracle set in section 7 and records the gap.

---

## 9. What this register does not establish

- No source among S5 through S9 was read. Five of the nine priority sources named for this
  pass were not accessed, and the register says which.
- The derivation in section 2 has not been checked against an independent implementation.
- The `s = 0` degeneracy in section 2.3 was derived in this pass and is unverified.
- Nothing here is field evidence. Every equation is about a declared idealisation.
- No B2 result exists. This register precedes the protocol, which precedes any code that
  produces a number.

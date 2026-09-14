# Evidence card — line-source radial flow and its semilog interpretation

> What this card is: a statement of evidence with its access status attached, written
> before the B1 code that uses it. A card is not an authority. Where a source was not
> read, this says so, and the equation is then carried by a derivation performed here
> rather than by the citation.

**Scope.** Everything B1 needs: the constant-rate line-source solution for an
infinite-acting, homogeneous, isotropic, single-phase radial system; its semilog
approximation; the field-unit mapping; the skin offset; and the analytic log-derivative.
Nothing about boundaries, storage, fractures, multiphase flow or real-gas behaviour.

---

## 1. Sources, with access status

| # | Source | Access | What it is used for here |
| --- | --- | --- | --- |
| S1 | Bourdet, D.P., Ayoub, J.A., Pirard, Y.M., "Use of Pressure Derivative in Well-Test Interpretation", *SPE Formation Evaluation*, June 1989, SPE-12777-PA | **FULL TEXT INSPECTED** (OCR, 2026-09-13 source review, recorded in `docs/evidence/derivative.md`) | Eq. 8, the three-point log-derivative algorithm, and the L point-selection rule. Already implemented and verified against the paper's Table 1. |
| S2 | Bourdet, D., *Well Test Analysis: The Use of Advanced Interpretation Models*, Elsevier, 2002 | **NOT ACCESSED** | Named as the standard monograph. No equation in B1 rests on it. |
| S3 | Horne, R.N., *Modern Well Test Analysis: A Computer-Aided Approach*, 2nd ed., Petroway, 1995 | **NOT ACCESSED** | Named as the standard text. No equation in B1 rests on it. No statement in B1 is attributed to it. |
| S4 | Lee, J., Rollins, J.B., Spivey, J.P., *Pressure Transient Testing*, SPE Textbook Series Vol. 9, 2003 | **NOT ACCESSED** | Named as the standard SPE text. No equation in B1 rests on it. |
| S5 | Earlougher, R.C., *Advances in Well Test Analysis*, SPE Monograph Vol. 5, 1977 | **NOT ACCESSED** | Named as the origin of much of the field-unit convention. No equation in B1 rests on it. |
| S6 | KAPPA Engineering, Saphir product documentation | **METADATA / PUBLIC WORKFLOW PAGE ONLY** (register entry R09) | Workflow vocabulary for the manual-validation bridge only. Not a validation, not a comparison, and not evidence about any number in B1. |
| S7 | Theis, C.V. (1935) line-source solution / the exponential-integral form of the radial diffusivity solution | **NOT ACCESSED as an original paper** | The solution form is derived below rather than cited, precisely because the original was not read. |

**The honest position.** Four of the five textbooks were not opened. This card therefore
does not write "according to Horne" or "per Earlougher" anywhere, and no constant is
entered because a book is said to contain it. Every equation B1 uses is derived in
section 2 and checked numerically in section 4. The one source that *is* load-bearing,
S1, was read in full and its algorithm is already verified against its own published
table.

---

## 2. The equations B1 uses, derived rather than quoted

### 2.1 Dimensionless line-source response

For radial flow of a slightly compressible single-phase fluid in an infinite,
homogeneous, isotropic medium at constant rate, the dimensionless pressure at
dimensionless radius `r_D` and dimensionless time `t_D` is the exponential-integral
("line source") solution

    p_D(t_D, r_D) = -(1/2) Ei(-r_D^2 / (4 t_D)) = (1/2) E1(r_D^2 / (4 t_D))

with `E1` the exponential integral `E1(x) = integral_x^inf e^-u / u du`, `x > 0`. At the
wellbore `r_D = 1`, so B1 evaluates `p_D = (1/2) E1(1/(4 t_D))`.

A constant skin `s` adds a rate-proportional, time-independent offset:

    p_D_with_skin = (1/2) E1(1/(4 t_D)) + s

This is a declared model property, not a derivation: skin is *defined* as that offset.

### 2.2 The semilog approximation, and the constant in it

For large `t_D` the series `E1(x) = -gamma - ln x + x - x^2/4 + ...` with
`gamma = 0.5772156649...` gives, at `x = 1/(4 t_D)`,

    (1/2) E1(1/(4 t_D)) -> (1/2) [ ln(4 t_D) - gamma ] = (1/2) [ ln t_D + (ln 4 - gamma) ]

so the familiar constant is

    ln 4 - gamma = 0.809079...

which is where `0.80907` comes from. It is not a fitted number.

### 2.3 Field-unit mapping, and every constant in it

B1 works dimensionlessly inside and converts at the boundary. The two conversion
factors are the standard oil-field ones:

    p_D = k h dp / (141.2 q B mu)          dp in psi, k in md, h in ft, q in STB/D, B in RB/STB, mu in cp
    t_D = 0.0002637 k t / (phi mu c_t r_w^2)    t in hours, c_t in 1/psi, r_w in ft

Every other published constant follows from those two and section 2.2, and B1 computes
them rather than storing them:

| published constant | derived as | value |
| --- | --- | --- |
| 0.80907 | `ln 4 - gamma` | 0.809079 |
| 162.6 (semilog slope) | `141.2 * ln(10)/2` | 162.5625 |
| 70.6 (derivative plateau) | `141.2 * 0.5`, equivalently `162.5625 / ln 10` | 70.6000 |
| 1.151 | `ln(10)/2` | 1.151293 |
| 3.2275 (skin constant) | `-log10(0.0002637) - (ln 4 - gamma)/ln 10` | 3.2275 |

Reproduced to the published digits by `tests/test_pta.py`. A magic constant that cannot
be re-derived is a magic constant; these can be, and the test says so.

### 2.4 Interpretation relations

From `dp = p_D * 141.2 q B mu / (k h)` and section 2.2, over the semilog straight line:

    m = 162.5625 q B mu / (k h)                      slope per log10 cycle
    k = 162.5625 q B mu / (m h)
    s = (ln10/2) [ dp_1hr / m - log10( k / (phi mu c_t r_w^2) ) ] + (ln10/2) * 3.2275

where `dp_1hr` is read from the fitted line extrapolated to one hour, not from a data
point. `dp_1hr` is an extrapolation of the line, and B1 treats it as such.

### 2.5 The analytic log-derivative

Differentiating the line-source solution with respect to `ln t_D`:

    d p_D / d ln t_D = t_D * d/dt_D [ (1/2) E1(a/t_D) ],   a = r_D^2/4
                     = (1/2) exp(-r_D^2 / (4 t_D))

At the well this tends to `1/2` from below, with deficit `1/(8 t_D)` to first order.
This closed form is the single most useful oracle in B1: it is an exact expression for
the quantity the Bourdet algorithm estimates numerically, and it is structurally
unrelated to that algorithm. It is verified against a central difference of the forward
solution in `tests/test_pta.py`.

---

## 3. Independent oracles, and what each is good for

B1 refuses to call a forward-versus-inverse comparison "independent" when both sides
share an implementation. Three oracles are used, each bounded to where it is defensible:

| oracle | independent of | valid where | role |
| --- | --- | --- | --- |
| **O1** high-precision `E1` by arbitrary-precision series, standard-library `decimal` | the float implementation's arithmetic entirely | small argument; the alternating series loses about `x/ln 10` digits to cancellation, so it is declared valid for `x <= 2` and given guard digits | checks the forward solution where B1 actually evaluates it |
| **O2** asymptotic expansion `E1(x) ~ e^-x/x * (1 - 1/x + 2/x^2 - ...)` | the series and the continued fraction both | `x >= 20` | checks the large-argument branch, which B1 does not use but the implementation exposes |
| **O3** the closed-form log-derivative `(1/2) exp(-1/(4 t_D))` | the Bourdet numerical algorithm entirely | everywhere | checks the derivative |

**Which argument range does B1 need?** At the wellbore `x = 1/(4 t_D)`, and IARF needs
large `t_D`, so B1's whole interpretation window sits at `x < 0.01`. That is deep inside
O1's declared range. The large-`x` branch is early time or far radius and is exercised
only by unit tests.

**mpmath** is a fourth, fully independent implementation by other authors (BSD licence).
It is *not* a dependency of this project, not in the lock file, and not required by any
test: where it happens to be importable a test uses it as an extra cross-check and skips
cleanly otherwise. The repository stays dependency-free at runtime, which is a property
worth more than a fourth oracle.

**CAPTAS and other open-source PTA implementations.** Read as references only. No code
is copied or ported. `captas` is GPL-licensed; copying or linking it into this
MIT-licensed repository is not permitted and is not done. An optional black-box
comparison would be recorded separately if one were ever run. Status:
**EXTERNAL OPEN-SOURCE COMPARATOR — NOT RUN.**

---

## 4. What was checked before the protocol was written

Numbers below were produced while designing B1, in a scratch directory, and are
reproduced by the committed tests. They are recorded here because acceptance criteria
that are chosen after seeing results are not criteria.

- `E1` float implementation against O1 and against mpmath: worst relative difference
  `1.4e-15` across `x` from `1e-8` to `300`.
- O1 against mpmath: exact agreement inside O1's declared range; O1 is *wrong* outside it,
  which is why the range is declared. The first version of that oracle was silently wrong
  at large `x` and looked convincing; the bound exists because of it.
- The closed-form log-derivative against a central difference of the forward solution:
  worst relative difference `9.3e-10`.
- The five field constants above reproduced to their published digits.
- The existing `bourdet_derivative` against the closed-form derivative on the B1 response:
  worst relative error `2.5e-9` at `L = 0` and `2.1e-8` at `L = 0.1`, over the B1 window.

---

## 5. Limitations of this card

- Four of the five textbooks are unread. Nothing here is attributed to them.
- The line-source solution is derived from its standard form rather than from the
  original paper, which was not accessed.
- The field-unit factors `141.2` and `0.0002637` are taken as the conventional oil-field
  definitions. They are *conventions*, and everything downstream is derived from them;
  if a reader uses a different convention the derived constants change with it, which is
  the point of deriving rather than storing them.
- Nothing here has been compared against a commercial well-test package, against field
  data, or against an independent implementation of the *interpretation* workflow.

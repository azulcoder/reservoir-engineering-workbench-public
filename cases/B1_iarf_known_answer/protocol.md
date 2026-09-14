# Case B1 protocol — infinite-acting radial flow, known answer

**Status: pre-registration. Written and committed before any code that produces a B1
number.** The commit that carries this file is recorded in the B1 run record, and it is
not amended, squashed or rebased once results exist. If a threshold below turns out to be
wrong, it is wrong in public and the run is classified against it as written.

---

## 1. Engineering question and decision

**Question.** Can this workbench recover a known permeability and a known non-zero skin
from a deliberately simple synthetic pressure transient, before it is pointed at anything
harder?

**Decision it supports.** Whether the transient instrument is trustworthy enough to build
Stage B on. A negative answer stops Stage B here; it does not produce a caveat.

**What this is not.** Not a well-test interpretation service, not a field study, not a
demonstration of PTA breadth. B1 is the transient analogue of A1: establish the
instrument on a case whose answer is known exactly, and find out where it stops working.

---

## 2. Physical model, declared in full

Single vertical well, constant rate, in a homogeneous, isotropic, infinite-acting radial
reservoir containing one slightly compressible fluid of constant properties.

| quantity | symbol | value | unit |
| --- | --- | --- | --- |
| permeability | k | 50.0 | md |
| net thickness | h | 40.0 | ft |
| porosity | phi | 0.18 | fraction |
| total compressibility | c_t | 1.5e-5 | 1/psi |
| viscosity | mu | 1.2 | cp |
| formation volume factor | B | 1.25 | RB/STB |
| wellbore radius | r_w | 0.35 | ft |
| initial pressure | p_i | 4000.0 | psia |
| constant production rate | q | 350.0 | STB/D |
| skin | s | +3.5 | dimensionless |
| wellbore storage | C | **0, by declared design** | bbl/psi |

**Wellbore storage is zero by design, not by oversight.** A real drawdown has a storage
period that distorts early time and interacts with skin; ignoring it silently would make
B1 look better than it is. Finite storage, buildup, superposition and rate history are
**B2**, and B1's negative control is deliberately not made harder by borrowing them.

**Excluded, all of them deliberately:** boundaries of any kind, hydraulic fractures,
horizontal or deviated wells, multilayer response, dual porosity, non-Darcy flow,
multiphase flow, gas condensate, real-gas property variation, rate changes, numerical
reservoir models, and field data of any kind.

**Governing solution.** The constant-rate line-source solution at the wellbore,
`p_D = (1/2) E1(1/(4 t_D)) + s`, with the field-unit mapping and every derived constant as
set out in `docs/evidence/pta_line_source.md` section 2. Units are oil-field throughout
the public interface; the solution is evaluated dimensionlessly inside.

---

## 3. Two structurally distinct paths, and three oracles

The forward generator evaluates the exponential integral. The inverse recovers parameters
from a **least-squares straight line on log10 time** and a skin offset read from that
line. These are not the same algebra run backwards: one is a special-function evaluation,
the other is a regression on a logarithmic transform, and the inverse never sees the true
parameters.

Oracles, each bounded to its valid range, as declared in the evidence card:

- **O1** arbitrary-precision `E1` via standard-library `decimal`, declared valid for
  argument `x <= 2`, which contains the whole B1 window.
- **O2** asymptotic expansion for `x >= 20`, checking the branch B1 does not use.
- **O3** the closed-form log-derivative `(1/2) exp(-1/(4 t_D))`, exact, and structurally
  unrelated to the Bourdet three-point algorithm that estimates it.
- **mpmath**, where importable, as a fourth independent implementation. No test depends
  on it and the runtime stays dependency-free.

**What is not independently verified:** the field-unit conventions `141.2` and
`0.0002637` themselves. Everything downstream is derived from them and re-derived by
test, but the conventions are taken as given.

---

## 4. Time design and the interpretation window

Sampling is logarithmic in time. The declared interpretation window is **1 hour to 48
hours**, which at these properties is `t_D` from `3.32e4` to `1.60e6` — between one and
two orders of magnitude past the usual `t_D > 100` rule, so IARF is not marginal.

The window is declared here, before results, and is **not** moved after seeing a fit.

---

## 5. Experiments

### B1.0 — mathematical baseline
Noise-free, 50 points per decade over the declared window. Recover `k`, `kh` and `s`.
Purpose: prove the instrument where the answer is exact.

### B1.1 — sampling and window placement
Physics held fixed. Two sweeps: points per decade in `{2, 3, 5, 10, 20, 50, 200}` over the
declared window; and window start at `t_D` in `{10, 25, 50, 100, 1000, 3.32e4}` at fixed
density. Purpose: find which of the two actually limits a noise-free interpretation.

**Pre-registered expectation, recorded so it can be wrong:** point density will barely
matter, because least squares on an almost-exact straight line is insensitive to how many
points lie on it; window *placement* will matter, with a permeability bias close to
`1/(10 t_D,min)`. If density turns out to dominate, that is a finding and it is reported
as one.

### B1.2 — pressure noise
Additive, independent, zero-mean Gaussian error on pressure only. Sigma in
`{0.1, 0.5, 2.0, 10.0}` psi. **200 seeds per level**, seeds `20260915 + i` for
`i` in `0..199`, fixed and recorded. Report mean and 95th percentile of `|dk/k|` and
`|ds|`, with the Monte Carlo standard error of the mean. Purpose: measure degradation,
not to demonstrate robustness.

Sigma is chosen relative to the signal: the drawdown over the window is about 72 psi and
the semilog slope about 43 psi/cycle, so 0.1 psi is a good gauge, 10 psi is a bad one.

### B1.3 — negative control
The same interpretation applied to a window at `t_D` from 1 to 10, where the semilog
approximation is **invalid by construction**. Purpose: show the acceptance machinery
rejecting an interpretation that still looks like a straight line on a plot.

This must FAIL the B1.0 criteria. A negative control that passes is a broken negative
control and is itself a B1 failure.

---

## 6. Acceptance criteria, derived before results

Every threshold below is derived from an analytic error estimate, not chosen to be
comfortably met. The derivations are in `docs/evidence/pta_line_source.md` section 2 and
the predicted magnitudes were computed during design.

| # | criterion | threshold | where the number comes from |
| --- | --- | --- | --- |
| B1-C1 | forward solution vs oracle O1, over the B1 window | relative `<= 1e-12` | the float implementation agrees with arbitrary precision to `~1e-15`; the threshold is three orders looser |
| B1-C2 | the five derived field constants reproduce their published values | relative `<= 1e-4` | the published values are quoted to 4-5 significant figures |
| B1-C3 | B1.0 permeability-thickness recovery | `\|d(kh)/kh\| <= 1e-4` | the semilog approximation biases the slope by about `1/(10 t_D,min)`; at `t_D,min = 3.32e4` that is `3.0e-6`, so the threshold carries about 33x headroom |
| B1-C4 | B1.0 skin recovery | `\|ds\| <= 1e-3` | the skin error tracks the same slope bias through `(ln10/2) * dp_1hr/m`; predicted `~1.7e-5`, threshold about 60x looser |
| B1-C5 | Bourdet derivative vs the closed form O3, over the window | relative `<= 1e-6` | measured worst `2.1e-8` at `L = 0.1`; the algorithm is exact for data affine in `ln t` and the residual is the `E1` curvature |
| B1-C6 | derivative plateau matches `(1/2) exp(-1/(4 t_D))`, not `1/2` | same as C5 | the deficit from `1/2` is `1/(8 t_D)` and is a real feature of the solution, not an error |
| B1-C7 | B1.3 negative control FAILS C3 | `\|d(kh)/kh\| > 1e-4` | it must fail, by at least an order of magnitude |
| B1-C8 | determinism: two runs in one environment agree byte for byte | exact | the canonical model already in use |
| B1-C9 | B1.2 noise degradation is monotone in sigma for the mean of `\|dk/k\|` | monotone | a non-monotone response would mean the estimator or the seeding is wrong |

**Also compared against the older, looser project targets in `PLAN.md`** — permeability-
thickness within 5% and skin within 0.5 — which B1.0 is expected to beat by orders of
magnitude and which the negative control is expected to miss on `kh`.

**Thresholds are not to be changed after results.** If a criterion fails without an
identified implementation defect, the run is classified INCONCLUSIVE or INVALID and the
owner is told; the number is not moved.

---

## 7. Classification rules, declared in advance

- **ESTABLISHED** — C1 through C9 all met. The claim that follows is precisely: *in this
  model, at these properties, over this window, the instrument recovers the known answer
  to the stated precision.* Nothing wider.
- **INCONCLUSIVE** — a criterion is missed for a reason traceable to sampling, noise or
  window placement rather than to the implementation, and the report says which.
- **INVALID** — a criterion is missed and the cause is an implementation defect, or the
  negative control passes. The defect is fixed, the failed run is kept, and a new run ID
  is issued.

---

## 8. Outputs

`summary.json` carrying the true parameters, the recovered parameters, every criterion
flag, the noise and sampling sweeps, and the negative-control result; a `run_record.json`
carrying this protocol's commit SHA, the source SHA, the canonical environment, the seeds
and the digests. Figures as listed in the case report. Immutable run directories; no run
is ever overwritten.

---

## 9. Limitations, stated before the result exists

B1 establishes an instrument on a synthetic case whose answer is known. It does not
establish that the instrument works on a real well test, on a gas well, with wellbore
storage, with a boundary, with a rate history, or with a model outside the one declared
in section 2. It is not field validation, not a comparison against any commercial
package, and not a peer-reviewed result. The recovered numbers are recovered from data
this project generated using a solution this project implemented; the independence in B1
is between the forward and inverse *methods*, not between this project and the world.

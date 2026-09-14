# Evidence card: Aquifer influx models

> Each card records what an implementer needs, where it came from, and how far it was
> verified. A card is not an authority: it is a statement of evidence with its access
> level attached. Items marked unverified are unverified, and the implementation must
> treat them as such.

**Adversarial review verdict:** `SOUND_WITH_CORRECTIONS`  
**Corrections applied:** 8  
**Items left unverified:** 8

## Summary

Main recommendation: use **Fetkovich (1971) PSS finite aquifer** as the forward generator, not van Everdingen-Hurst (vEH) or Carter-Tracy. The reason is not sophistication but auditability — the Fetkovich recursion is closed-form, with no tables and no superposition, and (I proved it numerically in the 2026-09-13 source review) **exact for a piecewise-constant boundary pressure at any Δt**, so the timestep does not inject scheme error into the synthetic data that is inverted later. One important correction to the draft specification this work started from: `Wei = ct * Wi * (pi - p)` is **wrong**; the primary source (Fetkovich Eq. A-11/17) writes `Wei = ct * Wi * pi` — the maximum encroachable water at zero aquifer pressure. The form `ct*Wi*(pi - p)` is `We(p)`, the cumulative influx at aquifer pressure p, not Wei; if the two are swapped, the whole time constant `J*pi/Wei` goes wrong along with it. The recursion `ΔWe_n = (Wei/pi)(p_aq_{n-1} - p_avg_n)(1 - exp(-J*pi*Δt/Wei))` in that specification is **correct as it stands**, and both occurrences of `pi` there are the *initial* aquifer pressure (not the current one) — they follow from `(q_wi)max = J*pi` (Fetkovich Eq. B-6), which I verified in the original text. The constant `B = 1.119 * f * phi * ct * h * ro^2` is verified along two routes: `1.119 = 2*pi/5.615` (dimensional derivation, accurate to 1e-7) and the pywaterflood v0.3.4 docstring. I also found a real transcription bug in an open-source library that people use (pywaterflood `klins` branch: `1.2838` instead of `1.12838`, and short-time `sqrt(tD/pi)` instead of `2*sqrt(tD/pi)`) — exactly the class of transcription error the specification warned about, and it is quantified below.

## Equations

### Fetkovich Eq.1 - aquifer inflow (rate) equation, geometry-independent

```
q_w = J * (p_aq_bar - p_wf)^n     with n = 1 for Darcy flow at pseudosteady or steady state
```

*Unit system:* oilfield/field units

| Symbol | Meaning | Units |
|---|---|---|
| `q_w` | water influx rate from aquifer into reservoir (Fetkovich nomenclature: 'water influx or efflux rate') | reservoir bbl/D |
| `J` | aquifer productivity index (PI), analogous to an oil-well PI | reservoir bbl/D/psi |
| `p_aq_bar` | average (shut-in) aquifer pressure - ABSOLUTE | psia |
| `p_wf` | pressure at the inner aquifer boundary = reservoir/aquifer contact - ABSOLUTE | psia |
| `n` | backpressure exponent; Fetkovich states it is 'usually represented as unity (1) when the flow obeys Darcy's law' | dimensionless |

Assumptions:

- Aquifer has reached pseudosteady state (closed outer boundary) or steady state (constant-pressure outer boundary). Early transient period is explicitly NEGLECTED.
- Single-phase, slightly compressible water; constant ct.
- Homogeneous aquifer, Darcy flow.

*Source:* Fetkovich, M.J., SPE-2603-PA, JPT July 1971 (pp. 814-828), Eq. (1) - OCR text layer of the scanned original read this session  
*Access:* full-text retrieved (scanned PDF with OCR text layer; prose verbatim, but displayed equations are page images so numeric constants inside them are NOT verbatim-legible)

### Fetkovich Eq.2 / Eq.13 - aquifer material balance (converts cumulative influx to aquifer pressure)

```
p_aq_bar_n = p_i * (1 - We_n / Wei)        <=>        We_n = (Wei / p_i) * (p_i - p_aq_bar_n)
```

*Unit system:* oilfield/field units

| Symbol | Meaning | Units |
|---|---|---|
| `p_i` | INITIAL aquifer pressure - ABSOLUTE. Constant for the whole run; never replaced by the current pressure. | psia |
| `We_n` | cumulative water influx into the reservoir (= efflux from aquifer) at end of step n | reservoir bbl |
| `Wei` | initial encroachable water in place at p_i (maximum encroachable water, i.e. the influx that would occur if aquifer pressure fell to zero) | reservoir bbl |

Assumptions:

- Constant total compressibility ct over the pressure range.
- Aquifer stays 100% water-saturated; Wei is NOT the aquifer pore volume (Fetkovich states this explicitly: 'Note that the term Wei is not total water in place, Wi').
- No water production from / injection into the aquifer, no interference from other reservoirs (Fetkovich Eq. A-9 keeps those terms; Eq. A-10/A-11 drops them).

*Source:* Fetkovich SPE-2603-PA, Eqs. (2), (13), (A-10), (A-11)  
*Access:* full-text retrieved (OCR)

### Wei - maximum encroachable water (CORRECTED FORM - the spec handed to me was wrong)

```
Wei = ct * Wi * p_i        [CORRECT]

NOT  Wei = ct * Wi * (p_i - p)   [INCORRECT - that expression is We(p), the cumulative influx at aquifer pressure p, i.e. We = ct*Wi*(p_i - p_aq_bar)]
```

*Unit system:* oilfield/field units

| Symbol | Meaning | Units |
|---|---|---|
| `Wi` | initial water in place in the aquifer = aquifer PORE VOLUME (Fetkovich nomenclature: 'initial water in place, surface bbl'; used as reservoir bbl in Eq. 17) | bbl |
| `ct` | total (effective) aquifer compressibility = cw + cf; Fetkovich: 'total or effective aquifer compressibility, psi^-1' | 1/psi |
| `p_i` | initial aquifer pressure - ABSOLUTE | psia |
| `Wei` | initial encroachable water in place | reservoir bbl |

Assumptions:

- Linear (constant-compressibility) fluid/rock expansion from p_i down to zero absolute pressure. This is an extrapolation, not a physical claim - Wei is a model parameter, not a producible volume.
- ct may be inflated deliberately (Fetkovich, citing Muskat) to lump in the compressibility of other non-producing hydrocarbon accumulations sharing the aquifer.

*Source:* Fetkovich SPE-2603-PA, Appendix A: 'Defining ct*Wi*p_i = Wei as the initial encroachable water in place' (Eq. A-11 region), and Eq. (17)  
*Access:* full-text retrieved (OCR prose verbatim; the defining sentence IS in the recovered text)

### Fetkovich Eq.17 - Wi for radial geometry (aquifer pore volume)

```
Wi   = pi_const * f * (r_a^2 - r_o^2) * h * phi / 5.615        [bbl]
Wei  = ct * Wi * p_i
     = (pi_const / 5.615) * f * (r_a^2 - r_o^2) * h * phi * ct * p_i
```

*Unit system:* oilfield/field units

| Symbol | Meaning | Units |
|---|---|---|
| `pi_const` | the number 3.14159265... (DO NOT confuse with p_i, initial pressure - this is a classic transcription trap; use distinct identifiers in code) | dimensionless |
| `f` | encroachment-angle fraction = theta/360, theta = angle of the aquifer sector actually in contact with the reservoir. Fetkovich's own study used theta = 360 deg, i.e. f = 1. | dimensionless, 0 < f <= 1 |
| `r_a` | external (outer) radius of the aquifer | ft |
| `r_o` | inner radius of the aquifer = effective outer radius of the reservoir (Fetkovich writes r_r; vEH writes r_o or R) | ft |
| `h` | aquifer thickness (NOT necessarily the reservoir net pay) | ft |
| `phi` | aquifer porosity, fraction | dimensionless |
| `5.615` | ft^3 per bbl conversion | ft^3/bbl |

Assumptions:

- Radial sector geometry. Fetkovich explicitly says Wei determination 'is not basically geometry-dependent except to the extent that fundamental mensuration rules can be applied' - isopach planimetry is more rigorous.

*Source:* Fetkovich SPE-2603-PA, Eq. (17)  
*Access:* full-text retrieved (OCR; the form is legible as an image-derived fragment, and it is independently confirmed by the cross-model identity in independent_checks #2)

### Fetkovich Eq.5 - closed-form cumulative influx for CONSTANT inner-boundary pressure

```
We(t) = (Wei / p_i) * (p_i - p_wf) * ( 1 - exp( -(q_wi)max * t / Wei ) )

with   (q_wi)max = J * p_i        (Fetkovich Eq. B-6, the aquifer 'initial open-flow potential')

=>  We(t) = (Wei / p_i) * (p_i - p_wf) * ( 1 - exp( -J * p_i * t / Wei ) )
```

*Unit system:* oilfield/field units

| Symbol | Meaning | Units |
|---|---|---|
| `(q_wi)max` | initial open-flow potential of the aquifer = influx rate if the inner boundary were dropped to zero absolute pressure at t=0 | reservoir bbl/D |
| `t` | time | days |
| `tau = Wei/(J*p_i)` | aquifer time constant (useful derived quantity; NOT in the paper) | days |

Assumptions:

- p_wf held constant for all t. Fetkovich: this form 'is not useful by itself because it cannot handle a changing inner boundary pressure while representing the aquifer pressure always at its initial value.'
- This is the exponential-decline form referred to in the task; it is the t -> single-step limit of the recursion below.

*Source:* Fetkovich SPE-2603-PA, Eq. (5) and Appendix B Eq. (B-28), with (q_wi)max = J*p_i from Eq. (B-6)  
*Access:* full-text retrieved (OCR; Eq. B-6 '(q_wi)max = J*(p_i)' is legible in the recovered Appendix B text)

### Fetkovich Eq.6 - the time-stepped recursion (THE generator kernel). The spec as handed to me is CORRECT.

```
delta_We_n = (Wei / p_i) * ( p_aq_bar_{n-1} - p_wf_bar_n ) * ( 1 - exp( -J * p_i * delta_t_n / Wei ) )

We_n        = We_{n-1} + delta_We_n                                  (Eq. 12)
p_aq_bar_n  = p_i * ( 1 - We_n / Wei )                               (Eq. 13)
p_wf_bar_n  = ( p_wf_{n-1} + p_wf_n ) / 2                            (Eq. 8)

AUDIT OF EVERY 'p_i' OCCURRENCE (3 of them, all INITIAL aquifer pressure, never current):
  1. Wei/p_i           -> p_i = INITIAL aquifer pressure   (comes from Wei = ct*Wi*p_i, so Wei/p_i = ct*Wi, a constant bbl/psi)
  2. exponent J*p_i*dt -> p_i = INITIAL aquifer pressure   (comes from (q_wi)max = J*p_i, Eq. B-6)
  3. Eq.13 p_aq = p_i*(...) -> p_i = INITIAL aquifer pressure
Equivalently and less error-prone in code:
  delta_We_n = ct * Wi * ( p_aq_bar_{n-1} - p_wf_bar_n ) * ( 1 - exp( -delta_t_n / tau ) ),  tau = Wei/(J*p_i) = ct*Wi*p_i/(J*p_i) ... NO:
  tau = Wei/(J*p_i) = (ct*Wi*p_i)/(J*p_i) = ct*Wi/J   [days]   <-- p_i cancels exactly; this cancellation is the cleanest check that you transcribed it right.
```

*Unit system:* oilfield/field units

| Symbol | Meaning | Units |
|---|---|---|
| `p_aq_bar_{n-1}` | average aquifer (shut-in) pressure at the START of step n, i.e. the value produced by Eq.13 at the end of step n-1 | psia |
| `p_wf_bar_n` | constant inner-boundary pressure used over step n; Fetkovich Eq.8 sets it to the arithmetic mean of the boundary pressure at the start and end of the interval | psia |
| `delta_t_n` | length of timestep n | days |
| `delta_We_n` | incremental water influx during step n | reservoir bbl |

Assumptions:

- Inner-boundary pressure is a step-constant over each interval (Fetkovich Figs. 5-6). Restarting the aquifer material balance every step is what REMOVES the need for superposition.
- p_wf_bar_n depends on p_wf_n, which in a coupled run depends on We_n -> implicit, needs iteration (see coupled scheme below).

*Source:* Fetkovich SPE-2603-PA, Eqs. (6), (8), (12), (13)  
*Access:* full-text retrieved (OCR; Eq. 8's averaging rule and Eqs. 12/13 are legible in recovered prose)

### Fetkovich aquifer productivity index J - RADIAL, finite aquifer with CLOSED (no-flow) outer boundary [pseudosteady state]

```
J = 0.00708 * k * h * f / ( mu_w * ( ln(r_a / r_o) - 0.75 ) )

with k in MILLIDARCIES. If k is expressed in DARCIES the constant becomes 7.08.
Derivation of the constant: 0.00708 = 2*pi * 0.001127, where 0.001127 is the field-unit Darcy constant
for q[bbl/D] = 0.001127 * k[md] * A[ft^2] * (dp/dx)[psi/ft] / mu[cp].
```

*Unit system:* oilfield/field units

| Symbol | Meaning | Units |
|---|---|---|
| `k` | aquifer permeability | md (see note: Fetkovich's own nomenclature lists k in darcies) |
| `mu_w` | aquifer water viscosity | cp |
| `f` | theta/360 encroachment-angle fraction | dimensionless |
| `0.75` | the 3/4 pseudosteady-state shape term for a circular closed drainage area | dimensionless |
| `J` | aquifer productivity index | reservoir bbl/D/psi |

Assumptions:

- reD = r_a/r_o must exceed exp(0.75) = 2.117, otherwise the denominator goes to zero or negative and J is nonsense (see failure_modes).
- Pseudosteady state has been reached (see t_pss estimate below).
- Fetkovich himself notes he tested variants of the constant in 'ln(r_a/r_r) - X' using X = 1/2 and X = 1, and that 'in all cases, the results obtained were significantly poorer than those reported in this study' - i.e. 3/4 is the fitted/justified choice.

*Source:* Fetkovich SPE-2603-PA Eq. (15) and Table 1 (equation images; OCR of the constant is truncated to '.08', consistent with 0.00708 or 7.08). Form with the (theta/360) factor confirmed via ScienceDirect Topics 'Fetkovich' search summary: 'J = 0.00708kh(theta/360) / mu [ln(ra/rr) - 0.75]'. Constant independently re-derived as 2*pi*0.001127.  
*Access:* secondary source + derivation (primary equation image not machine-readable; form verified against a search-result summary of a textbook excerpt and by first-principles derivation)

### Fetkovich J - RADIAL, finite aquifer with CONSTANT-PRESSURE outer boundary [steady state]

```
J = 0.00708 * k * h * f / ( mu_w * ln(r_a / r_o) )        [k in md]

(identical to above with the -0.75 shape term removed)
```

*Unit system:* oilfield/field units

| Symbol | Meaning | Units |
|---|---|---|
| `all` | as in the closed-boundary radial case | as above |

Assumptions:

- Outer boundary held at p_i forever (infinite recharge); this makes the aquifer a Schilthuis steady-state aquifer in the limit Wei -> infinity (Fetkovich Eq. 4: q_w = J*(p_i - p_wf)).

*Source:* Fetkovich SPE-2603-PA Table 1, row 'Finite - constant pressure at outer boundary'  
*Access:* Unverified — cited source not inspected + structure confirmed in retrieved OCR of Table 1 row labels (the row labels 'Finite--closed (no flow) at outer boundary' and 'Finite--constant pressure at outer boundary' ARE legible; the constants inside the equation images are not)

### Fetkovich J - LINEAR aquifer

```
Constant-pressure (steady-state) outer boundary:   J = 0.001127 * k * w * h / ( mu_w * L )
Closed (no-flow, pseudosteady) outer boundary:     J = 0.003381 * k * w * h / ( mu_w * L )

Note 0.003381 = 3 * 0.001127. Derivation for the closed case:
  PSS linear depletion gives q(x) = q0*(1 - x/L);  p_avg - p(0) = mu*q0*L/(3*k*A)  =>  q0 = 3*k*A*(p_avg-p0)/(mu*L).
```

*Unit system:* oilfield/field units

| Symbol | Meaning | Units |
|---|---|---|
| `w` | aquifer width (Fetkovich nomenclature: 'w = width, ft') | ft |
| `L` | aquifer length in the flow direction | ft |
| `k` | aquifer permeability | md |
| `A = w*h` | cross-sectional flow area | ft^2 |

Assumptions:

- Cross-sectional area to use is the area INSIDE the aquifer, not necessarily the reservoir/aquifer contact area. Fetkovich: 'The cross-sectional area at the aquifer-reservoir boundary is not necessarily applicable, especially after pseudosteady state or steady state has been established.'
- No encroachment-angle factor f for linear geometry - the geometry is carried entirely by w, h, L.

*Source:* 0.001127 confirmed by ScienceDirect Topics search summary ('J = 0.001127kwh / muL'); 0.003381 derived by me from the PSS linear pressure profile (factor 3). Fetkovich Table 1 OCR shows '1.127' and '.127' fragments consistent with 1.127e-3 but is not readable enough to settle which row carries 3.381e-3.  
*Access:* secondary source (0.001127) + own derivation (0.003381) - NOT verbatim-verified against the primary

### EXACTNESS LEMMA for the Fetkovich recursion (derived and numerically confirmed this session)

```
For constant p_wf, define x_n = p_aq_bar_n - p_wf and r = exp(-delta_t/tau), tau = ct*Wi/J.
  delta_We_n  = ct*Wi*x_{n-1}*(1-r)
  p_aq_bar_n  = p_aq_bar_{n-1} - (p_i/Wei)*delta_We_n = p_aq_bar_{n-1} - x_{n-1}*(1-r)
  => x_n = x_{n-1} * r        (exactly geometric)
  => We_n = ct*Wi*(p_i - p_wf)*(1 - r^n) = closed-form Eq.(5) evaluated at t = n*delta_t, EXACTLY, for ANY delta_t.

CONSEQUENCE: for a step-constant boundary-pressure history the Fetkovich recursion has ZERO timestep truncation error. It is not a first-order scheme; it is the exact solution of its own ODE.
```

*Unit system:* unit-free (algebraic identity)

| Symbol | Meaning | Units |
|---|---|---|
| `r` | per-step decay factor, always in (0,1) | dimensionless |

Assumptions:

- p_wf constant over the window considered. With a varying p_wf the scheme is exact per interval and the only error is the piecewise-constant representation of p_wf itself.

*Source:* Derived by me; verified numerically to all printed digits (see independent_checks #3)  
*Access:* own derivation, numerically verified this session

### van Everdingen & Hurst - dimensionless time tD

```
tD = 6.328e-3 * k * t / ( phi * mu_w * ct * r_o^2 )

with k [md], t [DAYS], phi [frac], mu_w [cp], ct [1/psi], r_o [ft].
If t is in HOURS use 2.637e-4 instead (6.328e-3 = 24 * 2.637e-4).
```

*Unit system:* oilfield/field units

| Symbol | Meaning | Units |
|---|---|---|
| `tD` | dimensionless time referenced to the INNER radius r_o (the reservoir radius), not to r_a | dimensionless |
| `r_o` | inner boundary radius = effective reservoir radius | ft |
| `ct` | aquifer total compressibility cw + cf | 1/psi |

Assumptions:

- Radial diffusivity equation, single-phase slightly compressible flow, constant k, phi, mu, ct.

*Source:* GEOS (LLNL) Aquifer Boundary Condition docs give the SI-consistent structure verbatim: t_D = t/T_c with T_c = mu_w * phi * c_t * r_0^2 / k. The field-unit constant 6.328e-3 = 24*2.637e-4 is standard textbook and re-derived, not retrieved verbatim.  
*Access:* structure: full-text retrieved (GEOS); field-unit constant: Unverified — supporting source not established - not retrieved (but internally consistent - see independent_checks #6)

### van Everdingen & Hurst - dimensionless radius reD

```
reD = r_a / r_o

reD -> infinity  =>  infinite-acting aquifer
Finite closed aquifer: WeD saturates at WeD_max = (reD^2 - 1)/2
```

*Unit system:* dimensionless

| Symbol | Meaning | Units |
|---|---|---|
| `reD` | aquifer-to-reservoir radius ratio | dimensionless |
| `WeD_max` | maximum dimensionless influx of a finite closed aquifer | dimensionless |

Assumptions:

- Concentric circular aquifer and reservoir.

*Source:* pywaterflood v0.3.4 docs: 'r_ed : dimensionless radius, r_a/r_o'; WeD_max = 0.5*(r_ed**2 - 1) appears explicitly in its finite-aquifer branch. Also confirmed numerically by my own Laplace inversion (converges to exactly 12.0 for reD=5 and 49.5 for reD=10).  
*Access:* full-text retrieved (pywaterflood source) + numerically verified this session

### van Everdingen & Hurst - water influx constant B (CONFIRMED: 1.119)

```
B = 1.119 * f * phi * ct * h * r_o^2        [bbl/psi]

EXACT VALUE: 1.119 = 2*pi / 5.615 = 1.11900012...
(if you instead use 5.6146 ft^3/bbl you get 2*pi/5.6146 = 1.1190798 - pick ONE conversion and document it)

f = theta/360, the ENCROACHMENT-ANGLE FRACTION (fraction of the full 360-deg circle over which the aquifer contacts the reservoir).
f is NOT a formation volume factor - one retrieved search summary mis-stated this; do not follow it.
```

*Unit system:* oilfield/field units

| Symbol | Meaning | Units |
|---|---|---|
| `B` | water influx constant (some texts call it U) | bbl/psi |
| `f` | theta/360, encroachment angle fraction, 0 < f <= 1 | dimensionless |
| `phi` | aquifer porosity | fraction |
| `ct` | aquifer total compressibility | 1/psi |
| `h` | aquifer thickness | ft |
| `r_o` | inner (reservoir) radius - SQUARED, and it is r_o NOT r_a | ft |

Assumptions:

- Radial geometry. For LINEAR geometry the influx constant is different (B_linear = 1.119*... does not apply; linear uses B = phi*ct*w*h*L/5.615 with its own WeD table).
- Consistency requirement: B * WeD_max must equal ct * Wi for the same aquifer - verified to 5e-8 relative (independent_checks #2).

*Source:* pywaterflood v0.3.4 aquifer module docstring (retrieved verbatim): 'aquifer_constant : aquifer constant in RB/psi  1.119 h f r_o^2 phi c_t'. GEOS docs give the SI analogue verbatim: 'beta = 6.283 h^A theta^A phi^A c_t^A (r_0^A)^2' where 6.283 = 2*pi. Value re-derived as 2*pi/5.615.  
*Access:* full-text retrieved (two independent official docs) + derivation

### van Everdingen & Hurst - superposition sum for cumulative influx

```
We(t_n) = B * SUM_{j=0}^{n-1} [ delta_p_j * WeD( tD_n - tD_j ) ]

Standard half-interval pressure-drop convention (constant-terminal-pressure superposition):
  delta_p_0 = ( p_i      - p_1 ) / 2
  delta_p_1 = ( p_i      - p_2 ) / 2
  delta_p_j = ( p_{j-1}  - p_{j+1} ) / 2      for j >= 2
where p_j is the inner-boundary pressure at time t_j.
```

*Unit system:* oilfield/field units

| Symbol | Meaning | Units |
|---|---|---|
| `delta_p_j` | the j-th pressure-drop increment applied at time t_j | psi |
| `WeD` | dimensionless cumulative water influx (vEH's Q(tD); some texts write WeD or QtD) | dimensionless |
| `tD_j` | dimensionless time at which increment j was applied | dimensionless |

Assumptions:

- Linearity of the diffusivity equation (required for superposition). Breaks if ct or k are pressure-dependent.
- Cost is O(N^2) in the number of timesteps and the whole history must be retained - the reason Carter-Tracy and Fetkovich exist.
- The half-interval convention deliberately lags total applied pressure drop by half a step; do not 'fix' it by using the full drop or you double count.

*Source:* pywaterflood v0.3.4 aquifer_production() retrieved verbatim implements exactly this sum. Fetkovich's paper confirms 'Hurst and others have handled this problem by the method of superposition'.  
*Access:* full-text retrieved (pywaterflood code) + the delta_p convention is Unverified — supporting source not established - not retrieved verbatim

### WeD(tD) for an INFINITE-acting radial aquifer - the three practical routes

```
(A) EXACT (Laplace domain, invertible with Stehfest in ~30 dependency-free lines if you also code K0/K1):
    WeD_bar(s) = K1(sqrt(s)) / ( s^(3/2) * K0(sqrt(s)) )

(B) Edwardson et al. (1962) polynomial - the one to implement:
    tD < 0.01       : WeD = 2*sqrt(tD/pi)
    0.01 <= tD <= 200 : WeD = (1.12838*sqrt(tD) + 1.19328*tD + 0.269872*tD^1.5 + 0.00855294*tD^2)
                             / (1 + 0.616599*sqrt(tD) + 0.0413008*tD)
    tD > 200        : WeD = (-4.29881 + 2.02566*tD) / ln(tD)

(C) Marsal / Walsh polynomial (used by pywaterflood as 'marsal-walsh'):
    tD <= 1   : WeD = 2*sqrt(tD/pi) + tD/2 - (tD/6)*sqrt(tD/pi) + tD^2/16
    1 < tD <= 100 : WeD = sum_{i=0}^{7} a_i * tD^i,  a = [8.1638e-1, 8.5373e-1, -2.7455e-2, 1.0284e-3,
                                                        -2.274e-5, 2.8354e-7, -1.8436e-9, 4.8534e-12]
    tD > 100  : WeD = 2*tD/ln(tD)

FINITE closed aquifer, PSS branch (pywaterflood 'klins'-style):
    J_star = reD^4*ln(reD)/(reD^2-1) + 0.25*(1 - 3*reD^2)
    WeD    = 0.5*(reD^2-1) * (1 - exp(-2*tD/J_star))     for tD >= 0.4*(reD^2-1)
    (infinite-acting expression used below that threshold)
```

*Unit system:* dimensionless

| Symbol | Meaning | Units |
|---|---|---|
| `K0, K1` | modified Bessel functions of the second kind, orders 0 and 1 | dimensionless |
| `s` | Laplace variable conjugate to tD | dimensionless |
| `J_star` | pseudosteady-state shape factor of the finite closed aquifer | dimensionless |

Assumptions:

- 1.12838 = 2/sqrt(pi) = 1.1283792, chosen precisely so the polynomial matches the exact small-time limit 2*sqrt(tD/pi). This is the strongest argument that 1.12838, not 1.2838, is correct.
- The Marsal-Walsh mid-range polynomial is an 8-term power series in tD and is numerically fragile above tD~100 (see numerical_pitfalls).

*Source:* Coefficients retrieved verbatim from pywaterflood v0.3.4 source (both 'klins' and 'marsal-walsh' branches); the 1.12838 value from a WebSearch summary quoting Edwardson et al. (1962); exact Laplace form constructed and numerically inverted by me this session.  
*Access:* full-text retrieved (pywaterflood, which contains a transcription bug - see uncertainties) + secondary (search summary for 1.12838) + own numerical verification

### Carter & Tracy (1960) - non-superposition recursion, field units

```
We_n = We_{n-1} + ( tD_n - tD_{n-1} ) * [ ( B * delta_p_n_TOTAL - We_{n-1} * pD'(tD_n) )
                                           / ( pD(tD_n) - tD_{n-1} * pD'(tD_n) ) ]

where delta_p_n_TOTAL = p_i - p_n   (TOTAL drop from initial, NOT the incremental drop - this is the single
most common Carter-Tracy transcription error)

Infinite-acting dimensionless pressure and derivative:
    pD(tD)  = 0.5 * ( ln(tD) + 0.80907 )        (valid roughly tD > 25-100)
    pD'(tD) = 0.5 / tD

B is the SAME van Everdingen-Hurst water influx constant, B = 1.119*f*phi*ct*h*r_o^2 [bbl/psi].
```

*Unit system:* oilfield/field units

| Symbol | Meaning | Units |
|---|---|---|
| `pD` | dimensionless pressure drop at the inner boundary for CONSTANT-RATE production (the constant-terminal-RATE solution, not the constant-pressure one) | dimensionless |
| `pD'` | d(pD)/d(tD) | dimensionless |
| `0.80907` | the line-source/exponential-integral constant, = ln(4/gamma_Euler) with gamma = 1.781072 | dimensionless |

Assumptions:

- Carter & Tracy assume CONSTANT WATER INFLUX RATE over each finite time interval (vs Hurst's constant oil-production rate) - this is the stated 'principal difference' in the 1960 abstract.
- Uses the constant-terminal-RATE solution pD, whereas vEH uses the constant-terminal-PRESSURE solution WeD. They are different functions; do not swap them.
- It is an APPROXIMATION to vEH, not an alternate exact route. See independent_checks #5: it does NOT converge to the vEH answer as delta_t -> 0.

*Source:* Carter, R.D. and Tracy, G.W., 'An Improved Method for Calculating Water Influx', Trans. AIME 219 (1960) 415-417, SPE-1626-G. Field-unit recursion form recalled; its STRUCTURE confirmed verbatim against the GEOS (LLNL) SI formulation retrieved this session (a and b coefficients with the identical denominator P_D(t_D^{n+1}) - t_D^{n+1} * P'_D(t_D^{n+1})).  
*Access:* abstract/metadata only for the 1960 primary; full-text retrieved for the GEOS SI restatement; the field-unit recursion itself is Unverified — cited source not inspected - not retrieved

### Carter & Tracy as implemented in GEOS (LLNL) - SI, verbatim

```
q_f^A   = alpha_f^A * ( a - b * ( p_K(t^{n+1}) - p_K(t^n) ) )
T_c     = mu_w^A * phi^A * c_t^A * (r_0^A)^2 / k^A
beta    = 6.283 * h^A * theta^A * phi^A * c_t^A * (r_0^A)^2
a       = (1/T_c) * ( beta*dPhi_K^A(t_D^n) - W^A(t_D^n) * P'_D(t_D^{n+1}) ) / ( P_D(t_D^{n+1}) - t_D^{n+1} * P'_D(t_D^{n+1}) )
b       = (1/T_c) * beta / ( P_D(t_D^{n+1}) - t_D^{n+1} * P'_D(t_D^{n+1}) )
```

*Unit system:* SI

| Symbol | Meaning | Units |
|---|---|---|
| `mu_w^A` | aquifer water viscosity | Pa.s |
| `phi^A` | aquifer porosity | dimensionless |
| `c_t^A` | aquifer total compressibility | 1/Pa |
| `r_0^A` | inner radius of aquifer | m |
| `k^A` | aquifer permeability | m^2 |
| `h^A` | aquifer thickness | m |
| `theta^A` | aquifer angle (GEOS labels it 'degrees' but it enters as the sector fraction; 6.283 = 2*pi) | see note |
| `beta` | influx constant (SI analogue of B) | m^3/Pa |
| `alpha_f^A` | area fraction of face f | dimensionless |

Assumptions:

- GEOS writes the influx as a linearised function of the NEW cell pressure (the a - b*dp form), i.e. it treats Carter-Tracy semi-implicitly inside the reservoir Newton loop. This is the production-grade way to do the coupling and is worth copying.

*Source:* GEOS documentation, 'Aquifer Boundary Condition' page  
*Access:* full-text retrieved

### Gas material balance with water influx - the equation the WRONG volumetric inverse will be fitted against

```
Reservoir volume balance:   G*Bgi = (G - Gp)*Bg + ( We - Bw*Wp )      [all volumes in reservoir bbl or all in ft^3 - be consistent]

Solved for the p/Z ordinate:
    p/Z = (p_i/Z_i) * ( G - Gp ) / ( G - ( We - Bw*Wp ) * 5.615 / Bgi )      [We, Wp in bbl; Bgi in ft^3/scf]

Bg = 0.02827 * Z * T / p        [ft^3/scf, T in degrees RANKINE, p in psia]

The VOLUMETRIC (wrong) inverse assumes We = 0 and fits a straight line:
    p/Z = (p_i/Z_i) * ( 1 - Gp/G )    ->   G_apparent = x-intercept of the fitted line
```

*Unit system:* oilfield/field units

| Symbol | Meaning | Units |
|---|---|---|
| `G` | original gas in place | scf |
| `Gp` | cumulative gas produced | scf |
| `Bg` | gas formation volume factor | ft^3/scf |
| `Z` | gas deviation (compressibility) factor at p, T | dimensionless |
| `T` | reservoir temperature - ABSOLUTE | degrees Rankine |
| `p` | average reservoir pressure - ABSOLUTE | psia |
| `Wp` | cumulative water produced | surface bbl |
| `Bw` | water formation volume factor | reservoir bbl/surface bbl |
| `0.02827` | = 14.696/(519.67) * ... standard-condition constant for Bg in ft^3/scf at 14.696 psia and 60 F | ft^3 psia /(scf R) |

Assumptions:

- No rock/connate-water compressibility term (add cf, cw if you want the full form). Fetkovich's own Eq. (26) is the gas MBE with water influx and water injection.
- Sw in the gas cap is immobile and residual gas saturation behind the water front is not modelled here - a real water-drive gas reservoir traps gas; if you want the counterexample to be honest about magnitude you must eventually add trapped-gas saturation.
- 0.02827 assumes standard conditions 14.696 psia / 60 F; state your standard conditions explicitly.

*Source:* Standard gas material balance; Fetkovich SPE-2603-PA Eq. (26) is the same balance with an added water-injection term (retrieved). The p/Z rearrangement is my algebra.  
*Access:* Unverified — supporting source not established - not retrieved (structure cross-checked against Fetkovich Eq. 26 in retrieved OCR)

### Coupled reservoir-aquifer solution scheme (part (e))

```
IMPLICIT / iterative-substitution scheme (what Fetkovich himself did), per timestep n:
  given: p_{n-1}, p_aq_{n-1}, We_{n-1}, Gp_{n-1}, and the offtake for step n
  1. Gp_n = Gp_{n-1} + qg * delta_t
  2. guess p_n^(0) = p_{n-1}
  3. repeat k = 0,1,2,...:
       p_wf_bar   = 0.5 * ( p_{n-1} + p_n^(k) )                        [Fetkovich Eq.8]
       delta_We   = (Wei/p_i) * ( p_aq_{n-1} - p_wf_bar ) * (1 - exp(-J*p_i*delta_t/Wei))
       We_n^(k)   = We_{n-1} + delta_We
       solve gas MBE for p_n^(k+1):  p/Z|_{p_n} = (p_i/Z_i)*(G-Gp_n)/(G - (We_n^(k)-Bw*Wp_n)*5.615/Bgi)
         (1-D root find in p; bisection on [p_min, p_i] is monotone and safe because p/Z is monotone increasing in p)
     until | p_n^(k+1) - p_n^(k) | < tol   (tol = 1e-6 psi is plenty)
  4. accept p_n, We_n; then p_aq_n = p_i * ( 1 - We_n / Wei )

EXPLICIT variant: replace step 3's p_wf_bar with p_{n-1} alone. First-order in delta_t, no iteration, and it systematically UNDER-predicts influx on a declining-pressure run.
```

*Unit system:* oilfield/field units

| Symbol | Meaning | Units |
|---|---|---|
| `tol` | fixed-point convergence tolerance on reservoir pressure | psi |
| `k` | iteration index (do not collide with permeability k in code) | - |

Assumptions:

- The fixed-point map is a contraction whenever the aquifer's per-step influx response (Wei/p_i)*(1-exp(-delta_t/tau))*(1/2) times the reservoir's dp/dWe sensitivity is < 1. For gas reservoirs this holds comfortably at monthly-to-annual steps.
- Fetkovich's own empirical statement (retrieved verbatim): 'The calculations were performed on a desk calculator using the simple trial-and-error procedure of iterative substitution... During the period of constant producing rate, the second trial was always within 1 psi of the final answer. When the producing rate was limited by the backpressure curve, an additional iteration was required.'
- The aquifer SUB-step is unconditionally stable for any delta_t because (1 - exp(-delta_t/tau)) is bounded in (0,1), so We can never overshoot Wei and p_aq can never go negative. Instability, if any, comes from the RESERVOIR side of the coupling, not the aquifer.

*Source:* Scheme structure: Fetkovich SPE-2603-PA (Example Calculations section, retrieved verbatim). Convergence behaviour: measured by me this session (6-9 iterations to 1e-8 psi at delta_t = 182.5 d).  
*Access:* full-text retrieved (OCR, verbatim quote) + own numerical verification

## Constants

| Name | Value | Units | Source | How verified |
|---|---|---|---|---|
| Radial Darcy constant, field units (Fetkovich J radial) | `0.00708` | (bbl/D/psi) per (md*ft/cp) | ScienceDirect Topics 'Fetkovich' search summary quoting J = 0.00708kh(theta/360)/mu[ln(ra/rr)-0.75]; re-derived as 2*pi*0.001127 = 0.0070812 | derivation + secondary source. The primary (Fetkovich Table 1 / Eq.15) is a page image; OCR returned only '.08'. If your k is in DARCIES the constant is 7.08 - Fetkovich's own nomenclature lists 'k = aquifer permeability, darcies'. |
| Linear Darcy constant, field units (steady-state linear J) | `0.001127` | (bbl/D/psi) per (md*ft^2/(cp*ft)) | ScienceDirect Topics 'Fetkovich' search summary ('J = 0.001127kwh / muL') | secondary source; consistent with 0.00708 = 2*pi*0.001127 |
| Linear PSS (closed outer boundary) constant | `0.003381` | (bbl/D/psi) per (md*ft^2/(cp*ft)) | no source retrieved this session | UNVERIFIED - needs primary source. I derived the factor-of-3 relationship (0.003381 = 3 * 0.001127) from the pseudosteady linear pressure profile, p_avg - p(0) = mu*q0*L/(3*k*A). The derivation is sound but I could not read Fetkovich Table 1 to confirm he used this value. |
| Pseudosteady-state shape term for a closed circular drainage area | `0.75 (i.e. 3/4)` | dimensionless | Fetkovich SPE-2603-PA (he reports testing 1/2 and 1 as alternatives and finding them 'significantly poorer') | full-text retrieved (OCR prose); standard PSS result |
| van Everdingen-Hurst water influx constant coefficient | `1.119 (exact: 2*pi/5.615 = 1.11900012)` | bbl/(psi * ft^3-of-(phi*ct*h*r^2)-group) - net result B in bbl/psi | pywaterflood v0.3.4 docstring ('1.119 h f r_o^2 phi c_t', RB/psi); GEOS SI analogue beta = 6.283 (=2*pi) h theta phi ct r0^2 | full-text retrieved (two official docs) AND derived (2*pi/5.615). Cross-model identity B*WeD_max / (ct*Wi) = 0.9999999511 - see independent_checks #2. |
| ft^3 per bbl conversion | `5.615 (or 5.6146 to 5 s.f.)` | ft^3/bbl | pywaterflood uses 5.6146 in effective_reservoir_radius(); the 1.119 constant implies 5.615 | full-text retrieved. NOTE the inconsistency: 2*pi/5.6146 = 1.1190798, not 1.119. Pick one and use it everywhere, or your Fetkovich and vEH branches will disagree at the 1e-5 level. |
| Dimensionless time constant, field units, t in DAYS | `6.328e-3` | dimensionless per (md*day/(cp*psi^-1*ft^2)) | not retrieved verbatim this session | Unverified — supporting source not established + derived as 24 * 2.637e-4 (the standard t-in-hours constant). Structure confirmed against GEOS T_c = mu*phi*ct*r0^2/k. Internally consistent: 0.00708*5.615/pi = 0.0126543 = 2*(6.3271e-3), matching 2*6.328e-3 to 1.4e-4 relative - i.e. the two published constants are mutually consistent to their own rounding. |
| Dimensionless time constant, field units, t in HOURS | `2.637e-4` | dimensionless per (md*hr/(cp*psi^-1*ft^2)) | not retrieved verbatim this session | Unverified — supporting source not established - standard well-test constant. Cross-check: 6.328e-3/24 = 2.6367e-4. |
| Exponential-integral / line-source constant in pD | `0.80907` | dimensionless | not retrieved verbatim this session | Unverified — supporting source not established; equals ln(4/gamma) with gamma = e^0.5772157 = 1.781072, i.e. ln(4/1.781072) = 0.80908. Self-consistent to 1e-5. |
| Edwardson et al. (1962) infinite-acting WeD polynomial coefficients | `numerator 1.12838, 1.19328, 0.269872, 0.00855294 ; denominator 1, 0.616599, 0.0413008 ; large-tD branch -4.29881, 2.02566` | dimensionless | WebSearch summary attributing them to Edwardson (1962); pywaterflood v0.3.4 carries the same set EXCEPT it has 1.2838 | 1.12838 verified by me numerically: it is 2/sqrt(pi) = 1.1283792, which makes the polynomial match the exact small-tD limit 2*sqrt(tD/pi), and reproduces my exact Laplace inversion to within 0.02% over 0.05 <= tD <= 1000. The variant 1.2838 is wrong by up to +4% (see independent_checks #1). The remaining coefficients were retrieved only as a search summary and from pywaterflood; treat them as secondary. |
| Marsal/Walsh mid-range WeD polynomial coefficients (1 < tD <= 100) | `8.1638e-1, 8.5373e-1, -2.7455e-2, 1.0284e-3, -2.274e-5, 2.8354e-7, -1.8436e-9, 4.8534e-12` | dimensionless | pywaterflood v0.3.4 aquifer module source | full-text retrieved; numerically agrees with my exact Laplace inversion to within 0.4% over 1 <= tD <= 100 |
| Gas FVF constant (Bg in ft^3/scf) | `0.02827` | ft^3 * psia / (scf * degR) | not retrieved this session | Unverified — supporting source not established. Standard conditions assumed 14.696 psia and 60 F (519.67 R). If your project uses 14.65 psia or 15.025 psia standard pressure, this constant changes - state it. |
| Fetkovich time-to-pseudosteady-state / time-to-steady-state constants (Eqs. 18 and 19) | `OCR returned '.02' and '.04' - not resolvable` | days, with phi, mu[cp], ct[1/psi], r[ft], k[darcies] | Fetkovich SPE-2603-PA Eqs. (18),(19) - equation images, unreadable | UNVERIFIED - needs primary source. Use instead the standard result t_pss[days] = 0.0496 * phi * mu * ct * r_a^2 / k[darcy] (from t_DA = 0.1 for a closed circle and t_DA = 2.637e-4*k[md]*t[hr]/(phi*mu*ct*A)), which I derived and which is the same order as the OCR fragments. |

## Validity ranges

- Fetkovich radial closed-boundary J: requires reD = r_a/r_o > exp(0.75) = 2.117. At reD = 2 the denominator ln(2)-0.75 = -0.0569 is NEGATIVE and J is unphysical. Note Fetkovich's own Table 3 lists r_a/r_r = 2 cases, so he must have handled small reD differently or accepted the regime limit - do not blindly use the -0.75 form below reD ~ 2.5.
- Fetkovich PSS approximation error vs the exact vEH finite-aquifer pseudosteady shape factor (measured this session): reD=2.5 -> 173% error, reD=3 -> 66%, reD=5 -> 13.5%, reD=10 -> 2.7%, reD=20 -> 0.6%, reD=50 -> 0.09%, reD=100 -> 0.02%. For a defensible synthetic generator use reD >= 10.
- Fetkovich neglects the early transient entirely. It is valid only for t >> t_pss. Fetkovich himself found his 10-md/r_a=100,000 ft case never reached PSS within a 20-year forecast and had to fall back on the Hurst-simplified equation.
- van Everdingen-Hurst infinite-acting solution is valid only while tD < 0.4*(reD^2 - 1) (pywaterflood's switching criterion, retrieved). Beyond that a finite aquifer has felt its boundary and the infinite solution over-predicts without bound.
- Edwardson polynomial: branch boundaries tD = 0.01 and tD = 200 as written. Do not extrapolate the mid-range rational function past tD = 200 (it drifts; I measured +0.07% at tD=200 and the large-tD branch takes over correctly).
- Marsal/Walsh mid-range polynomial: 1 < tD <= 100 ONLY. It is an 8-term power series with alternating signs down to 4.85e-12 - it diverges violently outside its window.
- pD(tD) = 0.5*(ln tD + 0.80907) is the infinite-acting line-source approximation: error 6% at tD=10, 1.2% at tD=50, 0.6% at tD=100, 0.08% at tD=750 (measured this session against exact Laplace inversion). Below tD ~ 25 Carter-Tracy with this pD is not trustworthy.
- Carter-Tracy with an infinite-acting pD is only valid while the aquifer is infinite-acting. For a finite aquifer you must swap in the finite-aquifer pD (e.g. the Klins series, or the PSS form), or the model will keep feeding water forever.
- All correlations assume constant ct, k, phi, mu_w. A gas-cap or free-gas-bearing aquifer (Muskat's East Texas Woodbine observation, ct ~ 6e-6 to 100e-6 psi^-1) violates constant-ct badly - Fetkovich's Eq. (24) exists precisely to lump that in.
- Absolute units mandatory: p_i, p, p_aq, p_wf in PSIA (not psig); T in RANKINE (not F). ct in 1/psi. t in DAYS for the 6.328e-3 and for J in bbl/D/psi.

## Failure modes

- Wei written as ct*Wi*(p_i - p) instead of ct*Wi*p_i. This was in the spec handed to me and it is wrong. It makes Wei shrink as the aquifer depletes, which corrupts BOTH the (Wei/p_i) prefactor and the exp(-J*p_i*dt/Wei) time constant, and makes the recursion non-conservative (We can then exceed the true maximum encroachable volume).
- Using the CURRENT aquifer pressure instead of the INITIAL aquifer pressure anywhere p_i appears in the Fetkovich recursion. Protective refactor: compute tau = ct*Wi/J and C = ct*Wi once at setup, then delta_We = C*(p_aq_prev - p_wf_bar)*(1 - exp(-dt/tau)). p_i then appears exactly once, in Wei = ct*Wi*p_i and in p_aq = p_i*(1 - We/Wei), and the cancellation p_i/(J*p_i) is done for you.
- Naming collision between pi (3.14159) and p_i (initial pressure). In Fetkovich Eq. 17 both appear in the same expression. Use PI_CONST and p_init.
- Using r_a instead of r_o in B = 1.119*f*phi*ct*h*r_o^2. It is the INNER (reservoir) radius, squared. Using r_a inflates B by reD^2 - a factor of 25 at reD = 5.
- Interpreting f as a formation volume factor. One of the search summaries I retrieved this session literally states 'f = formation volume factor'. It is theta/360, the encroachment-angle fraction. Wrong reading, wrong answer by up to 4x.
- Feeding Carter-Tracy the INCREMENTAL pressure drop instead of the TOTAL drop (p_i - p_n). Carter-Tracy's whole point is that it is a total-drop formulation; using increments silently produces a fraction of the true influx.
- Swapping pD (constant-terminal-RATE) for WeD (constant-terminal-PRESSURE) between Carter-Tracy and vEH. They are different functions of tD and both are ~O(1-10) over the useful range, so the bug does not blow up - it just gives wrong numbers.
- Using a mixed-unit k: 0.00708 for k in md vs 7.08 for k in darcies. Fetkovich's nomenclature says darcies; every modern textbook restatement says md. A factor of 1000 in J, which becomes a factor of 1000 in the aquifer time constant.
- Silent degeneracy of the counterexample: if the aquifer is too weak (small J or small Wei), the p/Z plot stays straight and the volumetric inverse recovers G correctly - you then have no counterexample. Conversely, too strong and p/Z curves so obviously that no engineer would fit a line. The example must be tuned to the honest 'looks linear, is not' regime.
- Trapped gas behind the advancing water front is NOT in the simple gas MBE written above. A real water-drive gas reservoir leaves 25-50% residual gas. Omitting it makes the synthetic data physically incomplete - state this as a deliberate model simplification, do not let a reviewer discover it.
- Assuming Carter-Tracy converges to vEH as delta_t -> 0. It does not (measured: +2.0% residual with the log pD, +1.4% with exact pD). If you use Carter-Tracy as the generator and vEH as the 'check', you will chase a 1-2% discrepancy that is a property of the method, not a bug.

## Numerical pitfalls

- 1 - exp(-x) catastrophically cancels for small x. Use -math.expm1(-x). At dt/tau = 1e-8 the naive form loses ~8 significant digits.
- The Fetkovich exponent is dimensionless only if dt is in DAYS and J in bbl/D/psi. A monthly loop written with dt=1 ('one month') silently runs 30x too fast.
- pi (3.14159) vs p_i (initial pressure) collision, especially in Python where `pi` is the obvious import from math. Name them PI and P_INIT.
- Marsal-Walsh mid-range WeD polynomial: coefficients span 8.16e-1 down to 4.85e-12 with alternating signs, and tD^7 at tD=100 is 1e14. Evaluate with Horner, and NEVER evaluate it outside 1 < tD <= 100 - it blows up immediately.
- Edwardson branch discontinuity at tD = 0.01: the polynomial at 0.01 gives 0.11284 while the exact answer is 0.11775 (a 4.2% jump). If you sample tD near the branch point you get a visible kink in the generated data. Either move the branch to tD=0.05 or accept and document the kink.
- Stehfest inversion (if you code the exact vEH check) is ill-conditioned: N=12 is about the practical maximum in double precision, and it requires evaluating K0/K1 at large arguments where they underflow. Use the exponentially SCALED Bessel functions (kve) or the ratio K1/K0 directly, never K1 and K0 separately.
- Carter-Tracy denominator pD(tD_n) - tD_{n-1}*pD'(tD_n) can approach zero if tD_{n-1} is large and pD' is evaluated inconsistently. With the log pD this is pD - tD_{n-1}/(2*tD_n), which is safe for tD_n ~ tD_{n-1}, but guard it anyway.
- Carter-Tracy at the FIRST timestep is the worst case: with a yearly step I measured -1.5% at the end but the first-step value was 52% off (5,499,996 vs 6,427,099 exact). Start Carter-Tracy with several small steps or it poisons the whole trace.
- The vEH half-interval superposition convention deliberately under-applies the total pressure drop by half a step. Comparing a vEH run against a Fetkovich or Carter-Tracy run at the same coarse delta_t will show a systematic offset that is pure convention, not physics. I measured ~6% between my vEH superposition and a converged Carter-Tracy on a 10-year linear ramp - a large part of that is this convention.
- The coupled fixed-point loop's convergence tolerance should be on PRESSURE (psi), not on We (bbl). We is O(1e6-1e7) so a relative tolerance on We is far looser than it looks.
- Don't compare float p/Z values for equality when detecting the 'linear' regime. The whole point of the counterexample is that the curvature is small - use an explicit residual/R^2 metric and report it, so 'it looked linear' is a number and not an impression.

## Implementation notes

- PART (d) ANSWER - use Fetkovich, and the argument is transparency plus checkability, not physics quality. (i) It is ~25 lines of dependency-free Python: no Bessel functions, no tables, no interpolation, no O(N^2) history. (ii) Its recursion is EXACT for its own model at any timestep (proved and numerically confirmed), so the synthetic data carries zero scheme error into the inverse problem - a reviewer cannot claim your counterexample is a timestep artefact. (iii) It has TWO independent closed-form checks built in: the Eq.(5) exponential, and the conservation invariant We(inf) = ct*Wi*(p_i - p_wf). (iv) It has an independent CROSS-MODEL check against vEH (B*WeD_max == ct*Wi, agreeing to 5e-8). (v) Every constant in it can be derived from first principles (0.00708 = 2*pi*0.001127, Wi from mensuration, Wei from ct*Wi*p_i) rather than digitised from a chart. By contrast vEH needs WeD tables or a polynomial whose published coefficients I could only reach through secondary sources (and found corrupted in a real library), and Carter-Tracy carries a non-vanishing ~1.5-2% method error that would contaminate the counterexample.
- Structure the core as three pure functions: aquifer_pi(geometry, rock, fluid) -> J ; aquifer_capacity(geometry, rock, p_i) -> (Wi, Wei) ; aquifer_step(state, p_wf_bar, dt) -> delta_We. Keep J, Wi, Wei as immutable setup outputs so the recursion has no way to recompute them with a current pressure.
- Refactor p_i out of the hot loop: precompute C = ct*Wi [bbl/psi] and tau = ct*Wi/J [days]. Then delta_We = C*(p_aq_prev - p_wf_bar)*(1 - exp(-dt/tau)) and p_aq = p_i - We/C. Mathematically identical, and the p_i-transcription failure mode disappears.
- Use math.expm1(-dt/tau) and write (1 - exp(-x)) as -expm1(-x) to keep full precision when dt << tau (short steps in a slow aquifer).
- Implement BOTH the recursion and the Eq.(5) closed form, and assert they agree under a constant-p_wf regression test at three different step counts. That test is cheap and it is the one that catches essentially every transcription error in part (a).
- Carry a unit-tagged parameter object (or at least a docstring table) that states: p in psia, T in R, t in days, k in md, mu in cp, ct in 1/psi, h and r in ft, J in bbl/D/psi, Wi/Wei/We in bbl. Assert p_i > 0 and reject psig input by requiring p_i > 14.7.
- Validate reD at construction: raise if r_a/r_o <= exp(0.75) for the closed-boundary radial J, and warn if reD < 10 (Fetkovich PSS error > 2.7%).
- For part (e), implement the IMPLICIT scheme (Fetkovich Eq.8 mid-step boundary pressure + fixed-point iteration on reservoir pressure). Measured: 6-9 iterations to 1e-8 psi at delta_t = 182.5 days. Cap iterations at ~50 and raise on non-convergence rather than silently accepting. Also implement the explicit variant behind a flag so the report can show the explicit/implicit difference as a numerical-sensitivity result.
- Inside each iteration you must invert p/Z(p) = RHS for p. Because p/Z is monotone increasing in p for any physical Z(p), bisection on [p_abandon, p_i] is unconditionally safe and needs no derivative. Do not use Newton here - a bad Z correlation can produce a non-monotone derivative and Newton will wander.
- Keep a running conservation assertion: 0 <= We <= Wei and p_aq in (0, p_i]. With the exact recursion these hold automatically; if they ever trip, you have a sign or a p_i error.
- If you later add vEH as a cross-check generator: implement WeD via the Edwardson polynomial with 1.12838 (NOT 1.2838) and the short-time branch 2*sqrt(tD/pi) (NOT sqrt(tD/pi)), and unit-test it against the exact values in independent_checks #1.
- Log both the 'true' generator parameters (G, J, Wei, r_a) and the fitted volumetric parameters (G_apparent) in the same record, so the counterexample's bias is reproducible from the artefact alone.
- Record the choice of 5.615 vs 5.6146 ft^3/bbl once, as a named module constant, and use it in BOTH the Fetkovich Wi and the 1.119 in B. Mixing them is a silent 1e-4 inconsistency that will show up as a failure of independent_check #2.

## Open uncertainties

- The single biggest gap: the Fetkovich 1971 PDF I retrieved is a SCAN. Its prose OCR is usable (and I quote it verbatim above) but every displayed equation is a page image, so I could NOT read the numeric constants inside Eq. (15), Eq. (17), Eq. (18), Eq. (19) or Table 1 verbatim. The OCR returns truncated fragments like '.08' and '1.127'. Everything I state about those constants is derivation plus secondary-source corroboration, not primary verification.
- 0.003381 for the linear closed-boundary Fetkovich J is UNVERIFIED against any source. I derived the factor 3 from the PSS linear pressure profile. Treat it as verified_how = 'UNVERIFIED - needs primary source' until someone reads Fetkovich Table 1 or a clean textbook restatement.
- Fetkovich's nomenclature lists 'k = aquifer permeability, darcies' and he writes 'All units in the above equations are in terms of days, centipoises, psi^-1, feet, and darcies'. Modern restatements of his J use 0.00708 with k in MILLIDARCIES. I could not determine from the scan whether Fetkovich's own Eq.15 constant is 0.00708 (md) or 7.08 (darcy). This is a factor of 1000 and MUST be pinned before publication.
- The constants 6.328e-3 (tD, t in days) and 2.637e-4 (tD, t in hours) and 0.80907 (line-source) and 0.02827 (Bg) are Unverified — supporting source not established: not retrieved in the 2026-09-13 source review. They are bedrock textbook values and they pass internal-consistency checks, but none of them was read off a source in this session.
- Fetkovich Eqs. (18) and (19), the times to reach pseudosteady and steady state, could not be read. I substituted my own derivation (t_pss[days] ~ 0.0496*phi*mu*ct*r_a^2/k[darcy], from t_DA=0.1). The Fetkovich values may differ.
- The Edwardson (1962) polynomial coefficients other than 1.12838 reached me only through a WebSearch summary and through pywaterflood's source - and pywaterflood's copy is demonstrably corrupted in two places. So the OTHER six coefficients might also carry transcription errors I cannot detect. My numerical agreement with the exact Laplace inversion (<=0.02%) is strong evidence they are right, but it is evidence, not verification against Edwardson et al.
- CONFIRMED DEFECT in a third-party library, reported honestly: pywaterflood v0.3.4, function water_dimensionless_infinite(), method='klins'. (a) short-time branch returns sqrt(tD/pi) where the correct small-time limit is 2*sqrt(tD/pi) - it is 2x low, 0.05642 vs exact 0.11775 at tD=0.01. (b) mid-range numerator leading coefficient is 1.2838 where it should be 1.12838 = 2/sqrt(pi) - this makes WeD 2-11% high over 0.01 < tD < 200. I verified both numerically against an exact Laplace inversion. I have NOT checked whether Klins et al. (1988) themselves published a different polynomial that legitimately has 1.2838 - I could not retrieve that paper. So: high confidence the pywaterflood values disagree with the exact solution; lower confidence about which publication the error originates from.
- I could NOT retrieve any published worked example with numbers (Ahmed, Craft & Hawkins, Dake, or Fetkovich's own Tables 3-5). Five different routes failed (connection refused, HTTP 500, 403, PetroWiki retired, Wayback blocked). Every numerical check I give is self-generated. The structural checks (#2, #6) and the exact-solution check (#1) are genuinely independent of any single implementation, but an adversarial reviewer is entitled to ask for one published number and I do not have one.
- The Carter-Tracy field-unit recursion form I give is recalled. Its structure is confirmed verbatim against GEOS's SI restatement (same denominator, same total-drop convention), but I did not read Carter & Tracy (1960) itself - only its abstract/metadata.
- The gas material balance p/Z form and the 0.02827 constant are recalled. Fetkovich Eq. (26) (retrieved) confirms the structure of the gas MBE with water influx but the OCR does not give me the coefficients.
- The GEOS docs label theta^A as 'degrees' while the constant is 6.283 = 2*pi, which only makes sense if theta enters as a fraction of a full circle. Either the GEOS doc's unit label is loose or there is a normalisation elsewhere in their code. Do not copy their units blindly.
- My counterexample's Z(p) is a documented linear toy, not a real EOS. The +6.5% OGIP bias I report is therefore indicative of the mechanism, not a quantitative claim. Swap in a real Z correlation (Dranchuk-Abou-Kassem, or Standing-Katz) before the number is quoted anywhere.

## Independent check values

| Check | Inputs | Expected | Source | Retrieved or recalled |
|---|---|---|---|---|
| Exact van Everdingen-Hurst infinite-acting WeD(tD) via Stehfest inversion of WeD_bar(s) = K1(sqrt s)/(s^1.5 K0(sqrt s)), compared against the Edwardson polynomial (1.12838), the pywaterflood variant (1.2838), and Marsal-Walsh. Use these as unit-test golden values. | `tD = 0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 5000; Stehfest N=12 in double precision` | `exact: 0.11775, 0.27639, 0.40434, 1.02436, 1.56829, 2.44540, 4.53365, 7.40152, 12.32013, 24.84078, 43.02513, 75.58764, 162.22768, 292.61126, 1188.62794.  Edwardson(1.12838) matches to <=0.02% for tD>=0.05 and -4.2% at tD=0.01 (branch switch).  pywaterflood's 1.2838 variant is +2 to +11% high across the whole mid range and its short-time branch is 52% LOW at tD=0.01 (0.05642 vs 0.11775) because it drops the factor 2 in 2*sqrt(tD/pi).  Marsal-Walsh matches to <=0.4%.` | Computed by me this session from the analytic Laplace-domain solution; cross-checked with two independent inversion algorithms (Stehfest N=12 float, Talbot 40-dps mpmath) | computed this session (not retrieved). The single value I can cross-check against memory is WeD(tD=1.0) ~ 1.569 from the published vEH table, which matches my 1.56829 - but that memory is RECALLED, not retrieved, so treat it as corroboration only. |
| Cross-model consistency: the maximum influx of a finite closed aquifer computed two completely independent ways - vEH (B * WeD_max) and Fetkovich (ct * Wi). This is the single best structural check that your 1.119, your 5.615, your pi, and your Wi formula are all mutually consistent. | `f=1, phi=0.20, ct=7e-6 1/psi, h=50 ft, r_o=2000 ft, r_a=10000 ft (reD=5)` | `B = 1.119*f*phi*ct*h*r_o^2 = 313.320000 bbl/psi ; WeD_max = (reD^2-1)/2 = 12 ; B*WeD_max = 3759.840000 bbl/psi.  ct*Wi with Wi = pi*f*(r_a^2-r_o^2)*h*phi/5.615 = 5.371200e8 bbl gives ct*Wi = 3759.840184 bbl/psi.  RATIO = 0.9999999511, which is exactly 1.119*5.615/(2*pi) - i.e. the entire residual is the 4-digit rounding of 1.119.` | Computed by me this session | computed this session |
| Fetkovich recursion exactness: with a CONSTANT inner-boundary pressure, the time-stepped recursion must reproduce the closed-form Eq.(5) to machine precision for ANY number of steps. This is the strongest possible implementation test of part (a) and it will instantly catch a p_i/Wei transcription error. | `k=100 md, h=50 ft, phi=0.20, mu_w=0.55 cp, ct=7e-6 1/psi, p_i=3000 psia, r_o=2000 ft, r_a=10000 ft, f=1, p_wf=2500 psia held constant.  Derived: J=74.890385 bbl/D/psi, Wi=5.371200e8 bbl, Wei=1.127952e7 bbl, J*p_i/Wei=1.99185023e-2 1/day, tau=50.2046 d.` | `We(10 d)=339516.8171 bbl ; We(50 d)=1185512.2635 ; We(100 d)=1623418.6405 ; We(365 d)=1878611.7885 ; We(3650 d)=1879920.0919.  The recursion with n=10, n=1000 and n=100000 steps reproduces EVERY one of these to all 4 decimal places printed.  Asymptote We(inf) = ct*Wi*(p_i - p_wf) = 1879920.0919 bbl exactly.` | Computed by me this session; the exactness is proved algebraically (x_n = x_{n-1}*exp(-dt/tau)) | computed this session |
| Golden Fetkovich trace with a declining boundary pressure - a directly runnable regression fixture. | `Same aquifer as above (J=74.890385, Wei=1.127952e7, p_i=3000). Boundary pressure declines linearly 3000 -> 2400 psia over 3650 days, delta_t = 365 d, p_wf_bar_n = mean of start/end (Fetkovich Eq.8).` | `n=1: p_wf_bar=2970.00, delta_We=112716.71, We=112716.71, p_aq=2970.0209
n=2: p_wf_bar=2910.00, delta_We=225511.86, We=338228.57, p_aq=2910.0418
n=3: p_wf_bar=2850.00, delta_We=225590.36, We=563818.92, p_aq=2850.0418
n=4..10: delta_We settles to exactly 225590.41 bbl/step; We(3650 d)=2142951.80 bbl, p_aq=2430.0418 psia.
The fact that delta_We becomes constant, and that p_aq stabilises exactly 30.0418 psi above p_wf_bar, is itself a diagnostic: the aquifer has reached a fixed lag behind a linear pressure ramp.` | Computed by me this session | computed this session |
| Carter-Tracy vs exact vEH on a clean step-pressure benchmark (no superposition convention to argue about). This quantifies the claim in part (c) and is the check that stops you trusting Carter-Tracy to 3 digits. | `Infinite-acting aquifer, k=100 md, h=50 ft, phi=0.20, mu_w=0.55 cp, ct=7e-6, r_o=2000 ft, f=1 => B=313.32 bbl/psi, tD = 0.20545455 * t[days]. Boundary pressure steps 3000 -> 2400 psia at t=0 and is held. Reference: We = B * 600 * WeD_exact(tD).` | `At t=3650 d (tD=749.91): exact vEH We = 43,009,732 bbl.  Carter-Tracy with pD = 0.5(ln tD + 0.80907): n=10 steps -> 42,364,752 (-1.500%) ; n=100 -> 43,553,333 (+1.264%) ; n=1000 -> 43,773,451 (+1.776%) ; n=10000 -> 43,875,733 (+2.013%).  With an EXACT pD (Laplace-inverted) at n=1000 -> 43,607,113 (+1.389%).  KEY FINDING: Carter-Tracy does NOT converge to the vEH answer as delta_t -> 0; it converges to its own answer ~1.4-2% high. The error also CHANGES SIGN between n=10 and n=100, so a coarse-step run can look deceptively accurate.` | Computed by me this session | computed this session |
| Internal consistency of the two published field-unit constants 0.00708 (Fetkovich J) and 6.328e-3 (vEH tD). They are not independent - Fetkovich's decay rate must reduce to a multiple of tD. | `Algebra: J*p_i/Wei with J = 0.00708*k*h*f/(mu*(ln reD - 0.75)) and Wei = ct*Wi*p_i, Wi = pi*f*(r_a^2-r_o^2)*h*phi/5.615` | `J*p_i/Wei = [0.00708*5.615/pi] * k / ( phi*mu*ct*r_o^2 * (reD^2-1)*(ln reD - 0.75) ).  The bracket evaluates to 0.0126543 = 2 * 0.00632713, which must equal 2 * 6.328e-3.  Agreement to 1.4e-4 relative - exactly the rounding level of the two published constants. If your code disagrees by more than ~0.02%, one of the constants is mistyped.` | Derived and evaluated by me this session | computed this session |
| Fetkovich PSS shape factor vs the exact finite-aquifer pseudosteady shape factor - quantifies how wrong Fetkovich is as a function of reD, which is what justifies the reD >= 10 recommendation. | `Fetkovich equivalent: J_F = (reD^2-1)*(ln reD - 0.75).  Exact: J_star = reD^4*ln(reD)/(reD^2-1) + 0.25*(1-3*reD^2) (the form used in pywaterflood's finite branch).` | `reD=2.5: 0.8730 vs 2.3801 (ratio 2.726) ; reD=3: 2.7889 vs 4.6234 (1.658) ; reD=5: 20.6265 vs 23.4124 (1.135) ; reD=10: 153.7059 vs 157.8344 (1.027) ; reD=20: 896.047 vs 901.546 (1.006) ; reD=50: 7901.90 vs 7909.22 (1.0009) ; reD=100: 38547.85 vs 38556.56 (1.0002). Both converge to reD^2*(ln reD - 0.75) as reD -> infinity.` | Computed by me this session; J_star form retrieved verbatim from pywaterflood v0.3.4 | computed this session (J_star form retrieved) |
| End-to-end counterexample check: does the volumetric p/Z straight-line inverse actually mis-estimate G when fed water-drive data? | `G = 100.0 Bscf, T = 620 R, p_i = 3000 psia, Z_i = 0.880, Z(p) = 0.880 + 4e-5*(3000-p) [documented toy Z, replace with a real EOS before publishing], Bw = 1.0, Wp = 0, constant offtake qg = 25 MMscf/D, delta_t = 182.5 d, 20 steps. Aquifer as in check #3 (J=74.8904, Wei=1.127952e7). Implicit coupled loop, tol 1e-8 psi.` | `Coupled loop converges in 6-9 fixed-point iterations per step. Trace: t=182.5 d -> p=2884.77, p/Z=3261.06, We=210,915 bbl ; t=1825 d -> p=1803.51, p/Z=1943.74, We=4,241,671 ; t=3650 d -> p=329.31, p/Z=333.70, We=9,715,254.  Fitting the WRONG volumetric straight line p/Z = (p_i/Z_i)(1 - Gp/G): first 5 points -> G_apparent = 108.415 Bscf (+8.4%) ; first 10 points -> 106.465 Bscf (+6.5%) ; all 20 points -> 102.580 Bscf (+2.6%). The bias is POSITIVE (classic water-drive over-estimate of OGIP) and DECREASES with more data - which is itself the interesting pathology to document.` | Computed by me this session | computed this session |
| Published worked example - NOT OBTAINED. I attempted Tarek Ahmed's Reservoir Engineering Handbook water-influx chapter (sb.uta.cl, connection refused), the SUST MATLAB thesis (HTTP 500), PetroWiki (folded into OnePetro, page gone; Wayback blocked), ScienceDirect Topics (403), and pdfcoffee/sweetstudy mirrors (chapter body not served). Fetkovich's own Tables 3-5 ARE in the scanned primary but the OCR of the numeric tables is unusable. | `n/a` | `n/a - this is an honest gap. My checks #1-#8 are all self-generated (though #1 and #2 are independent of any single model implementation). Before an adversarial review, one published number should be pinned: the vEH Table of Q(tD) for an infinite aquifer, or Ahmed's Fetkovich example.` | n/a | NOT RETRIEVED - flagged as a gap |

## Adversarial review

### Corrections

**independent_checks #1 + equations['WeD(tD) ... three practical routes'] — claimed accuracy of the Marsal/Walsh polynomial** — severity medium — a regression test written to the card's stated 0.4% tolerance will fail at the branch join; an implementer may then 'fix' a correct polynomial, confidence high — reproduced with two independent inversion algorithms

- Claimed: 'Marsal-Walsh matches to <=0.4%' (check #1) and 'numerically agrees with my exact Laplace inversion to within 0.4% over 1 <= tD <= 100' (constants block).
- Correct: Worst error is +4.81% at tD=1 (mid-range 8-term polynomial evaluated at its own lower branch bound), -1.35% at tD=3, -0.96% at tD=2, then settling to +0.15..+0.36% over 20<=tD<=100. The tD<=1 short-time series is separately +1.82% at tD=1 and +0.58% at tD=0.5. The '<=0.4%' claim is wrong by roughly 12x at the branch join.
- Evidence: Recomputed this session: exact WeD by Stehfest N=14 (float, K1/K0 ratio form) cross-checked against mpmath Talbot inversion at 40 dps of WeD_bar(s)=K1(sqrt s)/(s^1.5 K0(sqrt s)). Marsal-Walsh mid-range Horner evaluation with the card's own coefficient set [8.1638e-1 ... 4.8534e-12]. tD=1: exact 1.56829, MWpoly 1.64366 (+4.806%); tD=3: exact 3.19975, MWpoly 3.15647 (-1.353%); tD=100: exact 43.02510, MWpoly 43.17938 (+0.359%).

**numerical_pitfalls — 'Edwardson branch discontinuity at tD = 0.01' (and the same mislabel inside independent_checks #1: 'Edwardson ... -4.2% at tD=0.01')** — severity medium — the card's stated fix makes the artefact worse, and this sits in the implementation-facing pitfalls list, confidence high

- Claimed: 'the polynomial at 0.01 gives 0.11284 while the exact answer is 0.11775 (a 4.2% jump)'; remedy offered: 'Either move the branch to tD=0.05 or accept and document the kink.'
- Correct: The RATIONAL POLYNOMIAL at tD=0.01 gives 0.117733, i.e. -0.014% from exact — it is excellent. The value 0.112838 is the SHORT-TIME branch 2*sqrt(tD/pi), and that is the branch carrying the -4.15% error. The card has attributed the bad number to the wrong branch. Consequently the proposed remedy is backwards: moving the branch point up to tD=0.05 EXTENDS the inaccurate sqrt branch over a wider window (-3.0% at tD=0.005 grows toward -4.2% at tD=0.0099). Correct remedy: either use the rational polynomial all the way down, or replace the sqrt branch with the four-term small-time series 2*sqrt(tD/pi) + tD/2 - (tD/6)*sqrt(tD/pi) + tD^2/16, which is exact to 7 significant figures for tD <= 0.01 (0.11774957 vs exact 0.11774961).
- Evidence: Direct evaluation this session. Edwardson mid-range with 1.12838 at tD=0.0099 -> the sqrt branch fires and returns 0.112271 vs exact 0.117141 (-4.152%); at tD=0.01 the polynomial fires and returns 0.117733 vs exact 0.117750 (-0.014%). Small-time series reproduces exact to 0.000% at tD=0.001 and tD=0.01.

**summary + uncertainties['CONFIRMED DEFECT in a third-party library'] — provenance of the 1.2838 coefficient** — severity medium — a false accusation against a named third-party project is exactly the kind of claim an adversarial reviewer will punish, confidence high on the Ahmed rendering and the pywaterflood source; the Edwardson 1962 primary remains unread, so which of Edwardson/the handbook introduced the typo is still open

- Claimed: 'I also found a real transcription bug in an open-source library that people use (pywaterflood klins branch: 1.2838 instead of 1.12838 ...)' — i.e. the 1.2838 value is framed as a pywaterflood transcription bug.
- Correct: 1.2838 is NOT a pywaterflood transcription error. Tarek Ahmed, Reservoir Engineering Handbook, Eq. (10-27) prints the identical coefficient 1.2838, and the value propagates through the circulating secondary restatements as well. pywaterflood faithfully transcribed the published textbook rendering. The card's NUMERICAL conclusion stands (1.12838 = 2/sqrt(pi) is the correct value; 1.2838 is +12.4% at tD=0.01, +5.98% at tD=1, +1.98% at tD=10, +0.23% at tD=200) but the ATTRIBUTION is wrong — do not file a bug report against pywaterflood on that basis, and do not present it in the repo as 'a library bug we caught'. The right framing is: a long-lived typo in the published literature that both the handbook and the library inherited. NOTE the second half of the card's library claim IS a genuine pywaterflood-only defect: its short-time branch returns sqrt(tD/pi) where Ahmed Eq. (10-26) and the exact asymptote both give 2*sqrt(tD/pi) (0.056419 vs exact 0.117750 at tD=0.01, -52.1%).
- Evidence: Ahmed, Reservoir Engineering Handbook, p. 700 (Eq. 10-26, 10-27, 10-28) read this session from the PDF already present in the session scratchpad (<local session scratch, not part of this repository>). pywaterflood v0.3.4 source re-fetched this session and confirmed to contain 1.2838 and np.sqrt(time_D/np.pi). WebSearch for the coefficient set returns 1.2838 from the secondary corpus as well.

**equations['Gas material balance with water influx'] — stated standard conditions for the 0.02827 Bg constant** — severity low in magnitude (0.036% on Bgi, which partially cancels in the p/Z ratio) but it is precisely the class of unit-provenance error the card's own rules forbid, confidence high

- Claimed: symbol note '0.02827 ... = 14.696/(519.67) * ...' and assumption '0.02827 assumes standard conditions 14.696 psia and 60 F'.
- Correct: 14.696/519.67 = 0.0282795, which rounds to 0.02828, not 0.02827. The value 0.02827 corresponds to p_sc/T_sc = 14.7/520 = 0.0282692. The card's constant and its stated provenance are mutually inconsistent by 0.036%. Either quote 0.02828 with (14.696 psia, 519.67 R) or quote 0.02827 with (14.7 psia, 520 R) — but the card instructs the implementer to 'state your standard conditions explicitly' while itself stating the wrong pair.
- Evidence: Arithmetic this session: 14.696/519.67 = 0.02827948506; 14.7/520 = 0.02826923077.

**independent_checks #4 — the 'golden Fetkovich trace' regression fixture, stated diagnostic** — severity low — but it is inside a block advertised as 'a directly runnable regression fixture', confidence high

- Claimed: 'p_aq stabilises exactly 30.0418 psi above p_wf_bar'.
- Correct: Reproduced: p_aq_n - p_wf_bar_n settles at 0.0418 psi, not 30.0418 psi. The 30.0418 figure is p_aq_n minus p_wf at the END of step n (2430.0418 - 2400). The driving head p_aq_{n-1} - p_wf_bar_n settles at 60.0418 psi. All three numbers appear in the same fixture, so the label must be exact or the assertion will fail.
- Evidence: Re-ran the card's own fixture this session (J=74.890385, Wei=1.127952e7, p_i=3000, p_wf 3000->2400 linear over 3650 d, dt=365): n=10 gives p_wf_bar=2430.00, dWe=225590.41, We=2142951.80, p_aq=2430.0418. Every other number in the fixture reproduces to all printed digits.

**equations['van Everdingen & Hurst - water influx constant B'] — decimal expansion of 2*pi/5.615** — severity low, confidence high

- Claimed: 'EXACT VALUE: 1.119 = 2*pi / 5.615 = 1.11900012...'
- Correct: 2*pi/5.615 = 1.1190000547. The card's 8th-9th digits are wrong. (The companion figure in independent_checks #2, 1.119*5.615/(2*pi) = 0.9999999511, IS exactly right, so this is a transcription slip in one place only.) Related cosmetic slip: the card writes '6.328e-3 = 24 * 2.637e-4', but 24*2.637e-4 = 6.3288e-3; the SI-derived exact value is 6.32829e-3 = 5.615 * 0.00112712.
- Evidence: Arithmetic this session; SI derivation of the field-unit Darcy constant gives 0.0011271161 (bbl/D per md.ft^2.psi/ft/cp) and of the tD constant 2.63679e-4 (t in hours) / 6.32829e-3 (t in days).

**validity_ranges — 'Fetkovich PSS approximation error ... For a defensible synthetic generator use reD >= 10'** — severity medium — it needlessly narrows the design space of the counterexample, and the card holds the fix in its hand without using it, confidence high

- Claimed: reD=2.5 -> 173% error, reD=3 -> 66%, reD=5 -> 13.5%, reD=10 -> 2.7%; therefore restrict the generator to reD >= 10.
- Correct: The error figures are arithmetically right (I reproduced every one), but the conclusion is over-restrictive and the card misses that the defect is fully REMOVABLE. The entire error lives in the -0.75 shape term. Replacing ln(reD) - 0.75 with the exact pseudosteady shape factor G(reD) = [reD^4*ln(reD)/(reD^2-1) + 0.25*(1-3*reD^2)]/(reD^2-1) makes the Fetkovich J exact-PSS at any reD > 1 — including reD = 2, where ln(2)-0.75 = -0.0569 produces a NEGATIVE J. The card already carries this expression (as pywaterflood's J_star) inside check #7 but never proposes using it. Dake (1978) says exactly this: 'For small radial aquifers, the equivalent assumption that (ro/re)^2 is negligible may not always be applicable and the correct PI expression should then be obtained by solving the radial diffusivity equation', and reports 'Fetkovitch has demonstrated an almost perfect match between his results and those of Hurst and van Everdingen for values of reD as small as three' — which reconciles with the card only once you understand the 66% is in the PSS time constant, not in the matched influx history.
- Evidence: I derived the exact PSS shape factor from first principles this session (closed annulus ro..ra, q(r)=q0*(ra^2-r^2)/(ra^2-ro^2), dp/dr = mu*q(r)/(2*pi*k*h*r), pore-volume-weighted p_avg) and it reproduces the Klins/pywaterflood J_star to 30 dps at reD = 2, 2.5, 3, 4, 5, 10, 20, 50, 100. G_exact vs G_Fetkovich: reD=2 -> 0.315595 vs -0.056853; reD=3 -> 0.577931 vs 0.348612; reD=10 -> 1.594286 vs 1.552585. Dake, Fundamentals of Reservoir Engineering, Sec. 9.4, read this session from scratchpad/dake.pdf.

**independent_checks #2 and #6 listed under 'independent_checks'** — severity medium — it inflates the card's claimed evidence base from 8 independent checks to 6, confidence high

- Claimed: #2 is 'the single best structural check' and implementation_notes calls it 'an independent CROSS-MODEL check against vEH (B*WeD_max == ct*Wi, agreeing to 5e-8)'. #6 is presented as a check on 0.00708 vs 6.328e-3.
- Correct: Both are algebraic tautologies, not checks. #2: B*WeD_max = (2*pi/5.615)*f*phi*ct*h*ro^2 * (reD^2-1)/2 and ct*Wi = (pi/5.615)*f*phi*ct*h*ro^2*(reD^2-1) are the SAME expression; the check tests only that the rounded literal 1.119 equals 2*pi/5.615, and its stated residual 0.9999999511 is literally 1.119*5.615/(2*pi). It has zero power to detect a wrong 2*pi, a wrong WeD_max = (reD^2-1)/2, or a wrong Wi, so long as they are mutually consistent. #6 reduces to the unit identity 6.328e-3 = 5.615 * 0.001127 — the card concedes 'They are not independent' and then lists it as an independent check anyway. Keep both as CONSISTENCY assertions; do not count them toward independent validation. Checks #1, #3, #4, #5, #7, #8 survive as genuine (see below).
- Evidence: Symbolic reduction plus numerical confirmation this session: B=313.320000, WeD_max=12, B*WeD_max=3759.840000, ct*Wi=3759.840184, ratio=0.9999999511 = 1.119*5.615/(2*pi) exactly.

### Left unverified

- Edwardson et al. (1962) coefficients OTHER than the leading 1.12838 — namely 1.19328, 0.269872, 0.00855294, 0.616599, 0.0413008, and the large-tD branch (-4.29881 + 2.02566*tD)/ln(tD). I now have a second printed witness (Ahmed Eqs. 10-27 and 10-28, which match the card exactly on all of these) but that same witness is demonstrably wrong on the leading coefficient, so it does not raise these to 'verified'. Numerical agreement with the exact Laplace solution is <=0.09% over 0.01<=tD<=5000, which is strong circumstantial evidence, not source verification. Flag in the repo as: reproduced numerically, provenance still secondary.
- The Edwardson (1962) primary itself. Ahmed's reference list gives the actual title, which the card lacks: Edwardson, M. et al., 'Calculation of Formation Temperature Disturbances Caused by Mud Circulation', JPT, April 1962, pp. 416-425; Trans. AIME 225. The WeD polynomials are a by-product of a mud-circulation temperature paper, which explains why direct searches for a 'water influx' paper fail. Not retrieved this session.
- Klins, Bouchard & Cable (1988), SPE-15433-PA — still abstract/metadata only. Which polynomial Klins et al. actually published, and therefore whether pywaterflood's 'klins' branch is faithful to Klins or to Edwardson-via-Ahmed, remains unresolved.
- van Everdingen & Hurst (1949) primary — not retrieved. The vEH WeD table IS now available at second hand (Ahmed Tables 10-1 and 10-2, reproduced 'Permission to publish by the SPE'), which is materially better than the card's position, but it is not the 1949 paper.
- Fetkovich Eqs. (18) and (19), the times to reach pseudosteady and steady state. Still not machine-readable in the scanned primary, and no textbook restatement located. The card's substitute t_pss[days] = 0.0496*phi*mu*ct*r_a^2/k[darcy] is derivationally sound — I get 0.04965 from t_DA = 0.1 for a closed circle with the (now verified) 6.328e-3 constant — but Fetkovich's own coefficients may differ.
- 0.80907 in pD = 0.5*(ln tD + 0.80907). The mathematically exact value is ln(4) - gamma_Euler = 0.8090787, i.e. 0.80908. 0.80907 is the universally published convention (Ahmed p. 727 prints 0.80907), so use it for compatibility, but record that it is a literature rounding and not the exact constant.
- The card's claim that the EXPLICIT coupling variant 'systematically UNDER-predicts influx on a declining-pressure run'. The sign is correct by inspection (on a declining run p_{n-1} > p_wf_bar, so the driving head p_aq - p_wf is smaller, hence less influx), but I did not run the explicit scheme to quantify it. Treat the magnitude as unmeasured.
- Trapped/residual gas behind the advancing water front. The card correctly flags its absence from the gas MBE as a deliberate simplification and quotes a 25-50% residual gas saturation range; I did not source that range this session. Keep it labelled.

### Missing before implementation

- PRIMARY-SOURCE UPGRADE — the card's biggest self-declared gap is now closed, and the repo should record it. The session scratchpad already contained the sources the card reported as unobtainable: <local session scratch, not part of this repository> (Tarek Ahmed, Reservoir Engineering Handbook, 1463 pp, Ch. 10 'Water Influx'), scratchpad/dake.pdf (Dake, Fundamentals of Reservoir Engineering, Sec. 9.4), and scratchpad/fetkovich1971.pdf whose OCR DOES in fact contain Table 1. Re-author the derivations against these, not against search summaries.
- Wei = ct*Wi*p_i is now VERIFIED TWICE against textbook sources, not merely derived. Dake Eq. (9.20): 'where Wei = c Wipi is defined as the initial amount of encroachable water and represents the maximum possible expansion of the aquifer'. Ahmed Eq. (10-39): 'Wei = ct Wi pi f'. And the form the card called wrong, ct*Wi*(pi - p), is Dake Eq. (9.19) / Ahmed Eq. (10-38) for We, the CUMULATIVE INFLUX — exactly as the card argued. The card's correction of the handed-down spec is confirmed; state it in the repo as sourced, not inferred.
- 0.003381 is now PRIMARY-VERIFIED and must be moved out of 'UNVERIFIED - needs primary source'. Fetkovich's own Table 1 ('RADIAL AND LINEAR AQUIFER RATE EQUATIONS') is recoverable from the scanned PDF's text layer and reads, for 'Finite--closed (no flow) at outer boundary', linear column: q_w = 3(1.127) k b h (p_bar - p_wf)/(mu L). Fetkovich literally wrote the factor 3 as '3(1.127)'. The card's PSS-linear-profile derivation (p_avg - p(0) = mu*q0*L/(3*k*A)) is exactly right. Ahmed Eq. (10-45) independently prints 0.003381.
- The k-units ambiguity is RESOLVED and the card's 'factor of 1000 ... MUST be pinned before publication' can be closed. Fetkovich's nomenclature says 'k = aquifer permeability, darcies' and his Table 1 constants are correspondingly 7.08 and 1.127 (and his infinite-linear row carries 6.33, which is the tD constant in darcies). Dake states the conversion explicitly: 'Multiplying the radial PI functions by 7.08e-3 and the linear by 1.127e-3 will convert these expressions to field units.' Ahmed states 'k = permeability of the aquifer, md' with 0.00708/0.001127/0.003381. Both renderings are correct in their own unit system; pick md and 0.00708 and assert it in a docstring.
- 6.328e-3 (tD, t in days, k in md) is now RETRIEVED, not recalled: Ahmed Eq. (10-18), and exercised numerically in his Example 10-6 where it collapses to tD = 0.9888*t. My SI derivation gives 6.32829e-3. Same for B = 1.119*f*phi*ct*h*r_o^2: Ahmed Eq. (10-22)/(10-23) plus Example 10-6, B = 1.119(0.2)(1e-6)(2000)^2(25)(360/360) = 22.4 bbl/psi — confirming that the radius is the RESERVOIR radius squared and that f = theta/360, exactly as the card says.
- Carter-Tracy total-drop form is now RETRIEVED: Ahmed Eq. (10-34), with the nomenclature line 'Delta p_n = total pressure drop, p_i - p_n, psi'. The card's recalled field-unit recursion is confirmed verbatim in structure and in the total-drop convention. Ahmed also supplies an Edwardson rational approximation for pD itself (his Eq. 10-35/10-36) which the card does not carry and which is the right thing to use below tD ~ 100 instead of the log form.
- MISSING VALIDITY RANGE — the vEH half-interval superposition convention requires EQUAL timesteps. Ahmed states it explicitly: 'The time intervals must all be equal in order to preserve the accuracy of these modifications.' The card gives the convention (delta_p_j = (p_{j-1} - p_{j+1})/2) but never states the restriction. With unequal steps the convention is simply wrong, not merely biased.
- MISSING FAILURE MODE — the symbol r_e means OPPOSITE things in the two sources the implementer will read side by side. Fetkovich's nomenclature has 'r_r = internal radius of aquifer' (the reservoir radius) with r_e the external aquifer radius, so his Table 1 denominator is ln(r_e/r_r). Ahmed uses r_e = RESERVOIR radius and r_a = aquifer radius, so his is ln(r_a/r_e) = ln(r_D). Mixing them inverts reD. The card flags the pi/p_i collision but not this one, which is at least as likely.
- MISSING FAILURE MODE — the f-placement convention. Ahmed's Wi = pi*(r_a^2 - r_e^2)*h*phi/5.615 carries NO f and his Wei = ct*Wi*p_i*f carries it; the card's Wi carries f and its Wei = ct*Wi*p_i does not. The products agree, so both are correct internally, but taking Wi from one source and Wei from the other is a factor-1/f error (2.57x at theta = 140 deg). Assert Wei/(ct*p_i) == Wi at construction so the convention cannot be mixed.
- TIGHTEN a validity range — the card says pD = 0.5*(ln tD + 0.80907) is 'valid roughly tD > 25-100'. Ahmed states tD > 100. My measured errors (signed, which the card omits — the log form UNDER-predicts pD everywhere): -5.76% at tD=10, -2.33% at 25, -1.17% at 50, -0.58% at 100, -0.075% at 750. Use tD > 100, or use Ahmed Eq. 10-35 below that.
- ADD the removable-defect note on Fetkovich's J. Ship aquifer_pi() with a shape_factor='fetkovich'|'exact' switch, where 'exact' uses G(reD) = [reD^4*ln(reD)/(reD^2-1) + 0.25*(1-3*reD^2)]/(reD^2-1). This makes the generator defensible at any reD > 1 instead of only reD >= 10, removes the negative-J cliff at reD <= 2.117, and gives the report a clean numerical-sensitivity result (the two J's differ by 66% at reD=3 and 2.7% at reD=10, converging as reD -> infinity since both tend to reD^2*(ln reD - 0.75)).

### Recommended independent test oracles

**PUBLISHED WORKED EXAMPLE — Fetkovich, Ahmed Example 10-10 (data originally from Dake 1978)**

- Inputs: `p_i = 2740 psia, h = 100 ft, phi = 0.25, c_t = 7e-6 1/psi, mu_w = 0.55 cp, k = 200 md, theta = 140 deg (f = 0.38889), r_e (reservoir) = 9200 ft, r_a (aquifer) = 46000 ft, r_D = 5. Boundary pressure history p_r = 2740, 2500, 2290, 2109, 1949 psia at t = 0, 365, 730, 1095, 1460 days; dt = 365 d; p_r_bar_n = (p_r,n-1 + p_r,n)/2.`
- Expected: `Setup: W_i = 28.41e9 bbl, W_ei = 211.9e6 bbl, J = 116.5 bbl/D/psi, J*p_i/W_ei = 1.506e-3 1/day, 1 - exp(-J*p_i*dt/W_ei) = 0.4229, lumped step coefficient 32,705 bbl/psi. Trace (dWe, We in MM bbl): n=1 p_r_bar=2620, p_a_prev=2740, dp=120, dWe=3.925, We=3.925; n=2 p_r_bar=2395, p_a_prev=2689, dp=294, dWe=9.615, We=13.540; n=3 p_r_bar=2199.5, p_a_prev=2565, dp=366, dWe=11.970, We=25.510; n=4 p_r_bar=2029, p_a_prev=2409, dp=381, dWe=12.461, We=37.971. I reproduced this to 3 significant figures this session (my We = 3.925 / 13.550 / 25.500 / 37.973 MM bbl; the residual is Ahmed's hand-rounding of the intermediate dp column). Tolerance: 0.5% on We, 1 psi on p_a.`
- Why independent: This is the card's single largest self-declared gap ('Published worked example - NOT OBTAINED ... an adversarial reviewer is entitled to ask for one published number and I do not have one'). It is a third-party number computed by hand decades before any implementation here, and it simultaneously pins SIX constants at once: 0.00708 with k in md, the ln(r_D) - 0.75 shape term, the 5.615 conversion, Wei = ct*Wi*p_i*f, the recursion of Eq. (6), and the Eq. (8) mid-interval averaging. It is the highest-value oracle in this report. Source: Ahmed, Reservoir Engineering Handbook, Example 10-10, pp. 726-728.

**PUBLISHED WORKED EXAMPLE — van Everdingen-Hurst superposition, Ahmed Examples 10-6 and 10-7**

- Inputs: `Aquifer: r_e (reservoir) = 2000 ft, infinite aquifer, h = 25 ft, k = 100 md, phi = 0.20, mu_w = 0.8 cp, c_t = 1e-6 1/psi, theta = 360 deg. Boundary pressure 2500, 2490, 2472, 2444, 2408 psia at 0, 6, 12, 18, 24 months.`
- Expected: `B = 1.119*(0.2)*(1e-6)*(2000^2)*(25)*(360/360) = 22.4 bbl/psi; tD = 0.9888*t[days]. Half-interval drops dp = 5, 14, 23, 32 psi. Published We = 7,080 / 32,435 / 85,277 / 175,522 bbl at 6/12/18/24 months. IMPORTANT TRAP TO ENCODE DELIBERATELY: Ahmed computes B = 22.4 and then performs all the arithmetic with 20.4. Reproducing his printed We requires B = 20.4; using the correct 22.4 shifts every number by +9.8%. Ship the test with B = 22.4 and the scaled expectations (7,770 / 35,594 / 93,580 / 192,634), and document the textbook slip in the test docstring.`
- Why independent: Third-party published superposition arithmetic, independent of any code written here, and it pins B, tD, the half-interval convention, and the WeD table read-off simultaneously. The embedded typo is itself a useful artefact: it is direct evidence for the card's thesis that published transcriptions carry errors, and it gives the repo a concrete example rather than an assertion. Source: Ahmed, pp. 691, 696-699.

**PUBLISHED WORKED EXAMPLE — Carter-Tracy, Ahmed Example 10-9, including its timestep-sensitivity table**

- Inputs: `Same aquifer as Example 10-7 (B = 20.4 as Ahmed uses it, tD = 0.9888*t), pD = 0.5*(ln tD + 0.80907), pD' = 1/(2 tD), Delta p_n = p_i - p_n (TOTAL drop).`
- Expected: `With 6-month steps: We = 12,266 / 42,546 / 104,400 / 202,477 bbl at 6/12/18/24 months. With 30-day steps: We = 7,057 / 31,591 / 81,579 / 165,119 bbl at the same four times, against vEH's 7,080 / 32,435 / 85,277 / 175,522.`
- Why independent: Pins the Carter-Tracy recursion form, and specifically the total-drop convention that the card correctly identifies as 'the single most common Carter-Tracy transcription error' — feeding incremental drops instead reproduces neither column. It also independently corroborates the card's warning that the Carter-Tracy first timestep is the worst case. CAVEAT to record: this oracle must NOT be used to argue about Carter-Tracy-vs-vEH convergence, because it compares CT at monthly steps against vEH at 6-month steps under the half-interval convention — exactly the apples-to-oranges trap the card itself warns about. Use oracle #5 below for the convergence question. Source: Ahmed, pp. 719-721.

**PUBLISHED TABLE with a documented exact-solution discrepancy — vEH Table 10-1, infinite aquifer WeD**

- Inputs: `tD = 0.01, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 1, 2, 3, 4, 5, 50, 100.`
- Expected: `Published (van Everdingen & Hurst, reproduced by Ahmed with SPE permission): 0.112, 0.278, 0.404, 0.520, 0.606, 0.689, 0.758, 0.898, 1.020, 1.569, 2.447, 3.202, 3.893, 4.539, 24.855, 43.129. Exact (my 40-dps mpmath Talbot inversion of K1(sqrt s)/(s^1.5 K0(sqrt s)), independently reproduced by Stehfest N=14 in float): 0.117750, 0.276392, 0.404339, -, -, -, 0.756400, -, 1.024359, 1.568292, 2.445399, 3.199750, -, 4.533646, 24.840772, 43.025107. Agreement is within 0.25% for tD >= 0.05 but the published table is -4.9% at tD = 0.01. ENCODE BOTH: assert against the published table at 0.5% for tD >= 0.05, and assert the exact value 0.117750 at tD = 0.01 with an explicit comment that the 1949 hand-computed table entry is the inaccurate one.`
- Why independent: Two genuinely independent authorities that disagree, which is more valuable than either alone. It independently validates the card's check #1 golden values (which I reproduced to 6-7 significant figures) while exposing that a naive 'test against the published table' would fail at the small-tD end for the right reason. The tD=0.01 disagreement is itself corroborated by the analytic small-time asymptote (next oracle), so the exact value wins on two counts.

**DIMENSIONAL/ANALYTIC IDENTITY — the WeD-pD convolution, integral_0^tD WeD(tau)*pD(tD - tau) d_tau = tD^2 / 2**

- Inputs: `tD = 1, 10, 100, with WeD and pD from whatever routines the implementation actually ships.`
- Expected: `Exactly tD^2/2, i.e. 0.5, 50, 5000. I verified this to ~1e-6 relative this session using Stehfest-inverted WeD and pD with scipy quad.`
- Why independent: This follows from the Laplace-domain identity WeD_bar(s) * pD_bar(s) = [K1/(s^1.5 K0)] * [K0/(s^1.5 K1)] = 1/s^3, which is a property of the diffusivity equation itself and carries NO empirical constant, no unit system, no correlation and no tabulated value. It is the only oracle in this set that directly tests the card's own listed failure mode 'Swapping pD (constant-terminal-RATE) for WeD (constant-terminal-PRESSURE)' — for which the card offers no test at all, while noting the bug 'does not blow up, it just gives wrong numbers'. Swapping the two functions turns the integral into something that is not tD^2/2 and the test fires immediately. NOTE: the intuitive-looking form 'integral = tD' is WRONG; verify against tD^2/2.

**FIRST-PRINCIPLES DERIVATION — exact pseudosteady shape factor for a closed annulus, vs the Klins/pywaterflood J_star**

- Inputs: `reD = 2, 2.5, 3, 4, 5, 10, 20, 50, 100. Derive G(reD) by integrating the PSS annulus profile directly: q(r) = q0*(r_a^2 - r^2)/(r_a^2 - r_o^2), dp/dr = mu*q(r)/(2*pi*k*h*r), then pore-volume-weight p_avg over [r_o, r_a].`
- Expected: `G_exact = 0.315595, 0.453360, 0.577931, 0.793962, 0.975519, 1.594286, 2.259514, 3.164954, 3.856041. This must equal [reD^4*ln(reD)/(reD^2-1) + 0.25*(1 - 3*reD^2)]/(reD^2 - 1) to machine precision — I confirmed agreement to 30 dps at all nine radii. Compare against G_Fetkovich = ln(reD) - 0.75 = -0.056853, 0.166291, 0.348612, 0.636294, 0.859438, 1.552585, 2.245732, 3.162023, 3.855170; both must converge to ln(reD) - 0.75 as reD -> infinity.`
- Why independent: A closed-form quadrature derived from the diffusivity equation, with no reference to any library, table, or correlation. It independently certifies the J_star expression that the card imported verbatim from pywaterflood — a library the card itself demonstrates is defective elsewhere — so this closes the one place where the card leans on a source it has already impeached. It also supplies the corrected-J option in the missing_for_implementation list, and the negative value at reD = 2 is a ready-made guard-rail test.

**ASYMPTOTIC LIMIT — small-tD series for WeD**

- Inputs: `tD = 1e-4, 1e-3, 5e-3, 1e-2.`
- Expected: `WeD -> 2*sqrt(tD/pi) + tD/2 - (tD/6)*sqrt(tD/pi) + tD^2/16, which reproduces the exact inversion to 0.000% at tD <= 0.01 (at tD = 0.01: series 0.1177496 vs exact 0.1177496) and degrades smoothly to +0.034% at tD = 0.1, +0.58% at 0.5, +1.82% at 1.`
- Why independent: A pure asymptotic expansion of the Laplace solution (from K1(x)/K0(x) -> 1 + 1/(2x) as x -> infinity), containing no fitted constant. It settles the tD = 0.01 dispute between the published vEH table and the exact inversion without appealing to either, it proves 1.12838 = 2/sqrt(pi) rather than 1.2838 is the correct leading Edwardson coefficient, and it is the correct replacement for the Edwardson sqrt branch identified in correction #2.

**SELF-CONSISTENCY OF FETKOVICH'S OWN TABLE 1 — the exact factor 3 between linear closed and linear steady-state J**

- Inputs: `Any linear aquifer: compute J_closed/J_steady with the shipped constants.`
- Expected: `Exactly 3.000000 (0.003381/0.001127 = 3.0000). Independently, the PSS linear pressure profile gives p_avg - p(0) = mu*q0*L/(3*k*A) while the steady-state profile gives p_i - p(0) = mu*q0*L/(k*A), so the ratio is 3 by construction.`
- Why independent: Fetkovich wrote the coefficient literally as '3(1.127)' in his own Table 1, so this is a structural relation asserted by the primary source AND independently derivable from the linear diffusivity equation. It catches a mistyped 0.003381 (e.g. 0.0003381, which is what an ambiguous OCR of Dake's Table 9.8 would suggest) without needing to read the scanned table at all.

## Sources

| Citation | Access level | Supports |
|---|---|---|
| Fetkovich, M.J., 'A Simplified Approach to Water Influx Calculations - Finite Aquifer Systems', SPE-2603-PA, Journal of Petroleum Technology 23(7), July 1971, pp. 814-828; Trans. AIME 251. (Presented at SPE 44th Annual Fall Meeting, Denver, Sept. 28-Oct. 1, 1969.) | full-text retrieved (scanned PDF, OCR text layer; PROSE verbatim, DISPLAYED EQUATIONS are page images and not machine-readable) | PRIMARY source for part (a): Eq.(1) rate equation with exponent n, Eq.(2)/(13) aquifer material balance, Eq.(5) exponential closed form, Eq.(6) the time-stepped recursion, Eq.(8) mid-interval boundary pressure, Eq.(12) accumulation, Eq.(17) Wi radial, Eq.(B-6) (q_wi)max = J*p_i, Eq.(A-11) definition 'ct*Wi*p_i = Wei as the initial encroachable water in place' (this is the sentence that refutes the Wei = ct*Wi*(pi-p) form in the spec), Eq.(4) reduction to Schilthuis steady state, Eq.(26) gas MBE with water influx, the full nomenclature with units, the Table 1 row labels for radial/linear x closed/constant-pressure/infinite, and the verbatim statement of the iterative-substitution coupling scheme and its convergence ('the second trial was always within 1 psi'). NOTE: the site serves an EXPIRED TLS certificate; I fetched it with verification disabled. |
| GEOS (Lawrence Livermore National Laboratory), 'Aquifer Boundary Condition', GEOS documentation, coreComponents/fieldSpecification. | full-text retrieved | PART (c): the Carter-Tracy formulation as implemented in a production reservoir simulator, in SI, verbatim: q_f = alpha*(a - b*dp), T_c = mu*phi*ct*r0^2/k, beta = 6.283*h*theta*phi*ct*r0^2 (6.283 = 2*pi, confirming the 1.119 = 2*pi/5.615 field-unit analogue), and the a/b coefficients with the P_D - t_D*P'_D denominator. Also supports the recommended semi-implicit coupling in part (e). |
| pywaterflood v0.3.4, module pywaterflood.aquifer (source listing in the project's official documentation). | full-text retrieved | PART (b): the water influx constant docstring '1.119 h f r_o^2 phi c_t' in RB/psi (verbatim confirmation of the 1.119 constant and that f is the flow-solid-angle fraction theta/360, with flow_solid_angle documented as 'solid angle between well and reservoir in degrees, ranges from 0-360'); the superposition sum We = B*sum(WeD(tD_n - tD_j)*dp_j); reD = r_a/r_o; the infinite-acting switching criterion tD < 0.4*(reD^2-1); WeD_max = 0.5*(reD^2-1); the finite-aquifer J_star shape factor; the Marsal-Walsh coefficient set; the 5.6146 ft^3/bbl conversion in effective_reservoir_radius(). ALSO the source of a confirmed transcription defect (1.2838 vs 1.12838; sqrt(tD/pi) vs 2*sqrt(tD/pi)) - see uncertainties. |
| Carter, R.D. and Tracy, G.W., 'An Improved Method for Calculating Water Influx', SPE-1626-G, Trans. AIME 219 (1960) 415-417. | abstract/metadata only | PART (c): the citation itself, and the stated basis of the method - 'the principal difference between this method and that of Hurst is that over finite intervals of time, constant oil-production rates are assumed by Hurst whereas constant water influx rates are assumed in the Carter-Tracy method', and that 'superposition calculations may be eliminated'. This reference also appears as ref. 22 in Fetkovich's own (retrieved) reference list, which independently confirms the year, volume and page range. |
| van Everdingen, A.F. and Hurst, W., 'The Application of the Laplace Transformation to Flow Problems in Reservoirs', Trans. AIME 186 (1949) 305-324; SPE-949305-G. | Unverified — cited source not inspected - not retrieved | PART (b) primary attribution. I did NOT read this paper this session. Its full citation (Trans. AIME 186, 305-324, 1949) IS verified, because it appears as reference 7 in Fetkovich's retrieved reference list and again in the pywaterflood docstring. |
| Klins, M.A., Bouchard, A.J. and Cable, C.L., 'A Polynomial Approach to the van Everdingen-Hurst Dimensionless Variables for Water Encroachment', SPE Res Eng 3 (1988) 320-326, SPE-15433-PA. | abstract/metadata only (citation read from the retrieved pywaterflood docstring) | The finite-aquifer polynomial/Bessel-series route and the naming of the 'klins' branch. I could not verify which polynomial coefficients Klins et al. actually published, which is why I cannot attribute pywaterflood's 1.2838 to a specific origin. |
| Edwardson, M.J. et al. (1962), polynomial approximation to the van Everdingen-Hurst dimensionless water influx. | secondary source (WebSearch result summary only; the primary was not located) | The coefficient set 1.12838 / 1.19328 / 0.269872 / 0.00855294 over 1 + 0.616599*sqrt(tD) + 0.0413008*tD, and the large-tD branch (-4.29881 + 2.02566*tD)/ln(tD). The leading 1.12838 is independently corroborated by the exact small-time limit 2/sqrt(pi) = 1.1283792 and by my numerical comparison against the exact Laplace inversion. |
| ScienceDirect Topics, 'Fetkovich' (auto-generated topic page compiling textbook excerpts, principally Tarek Ahmed's Reservoir Engineering Handbook). | secondary source - WebSearch result summary only; direct fetch returned HTTP 403 | The field-unit form J = 0.00708*k*h*(theta/360)/(mu*[ln(ra/rr) - 0.75]) for radial finite no-flow, and J = 0.001127*k*w*h/(mu*L) for linear. Cross-check only; NOT an authority for a derivation. |
| Adjei-Kwakwa et al. (UMaT), 'Comparison of Analytical and Numerical Water Influx Models in Bottom Water Reservoir', UMaT conference proceedings. | full-text retrieved (PDF text extracted) but all equations are embedded images | Only the qualitative statement that ECLIPSE 100 implements Carter-Tracy and Fetkovich but not vEH, and the nomenclature 'B = water influx constant, bbl/psi'. No usable numbers. Secondary, low weight. |
| Own computations, this session: exact van Everdingen-Hurst WeD(tD) by Stehfest (N=12, float) and Talbot (mpmath, 40 dps) inversion of K1(sqrt s)/(s^1.5 K0(sqrt s)) for the infinite aquifer and the corresponding finite-aquifer Laplace expression; Fetkovich recursion-vs-closed-form exactness test; Fetkovich/vEH maximum-influx identity; Carter-Tracy timestep-refinement benchmark; coupled gas-reservoir forward generator and volumetric p/Z line fit. | computed this session (not a literature source) | Every number in independent_checks #1-#8. Scripts live at <local session scratch, not part of this repository>,golden.py,cross.py,ct3.py,coupled.py}. These are scratch files and should be re-authored inside the repo if you want them as regression tests. |

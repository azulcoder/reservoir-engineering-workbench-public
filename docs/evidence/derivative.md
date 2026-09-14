# Evidence card: Pressure derivative diagnostics

> Each card records what an implementer needs, where it came from, and how far it was
> verified. A card is not an authority: it is a statement of evidence with its access
> level attached. Items marked unverified are unverified, and the implementation must
> treat them as such.

**Adversarial review verdict:** `SOUND_WITH_CORRECTIONS`  
**Corrections applied:** 12  
**Items left unverified:** 11

## Summary

Primary source Bourdet, Ayoub & Pirard, SPEFE June 1989 (SPE-12777-PA) was successfully retrieved in full text (OCR) in the 2026-09-13 source review, so Eq. 8 (the derivative algorithm) and Eq. 7 (the Agarwal-modified Horner derivative) are quoted verbatim rather than from memory. The weighting is confirmed: the left slope is multiplied by the RIGHT spacing and the right slope by the LEFT spacing — (dp/dX)_i = [(Dp1/DX1)*DX2 + (Dp2/DX2)*DX1]/(DX1+DX2) — and I verified this numerically against Table 1 of the original paper (reproduced to ~1e-3 psi; the transposed weighting gives 5.44592 versus the published 5.99244, so the test is discriminative). L is the minimum distance on the X axis in NATURAL-log units of the time function (not decades): the reconstruction of the L=0.1 column of Table 1 matches (26.07274 vs 26.07281) only if L is read as ln-units; reading it as 0.1 decades gives 30.90 — this is implementation trap number two after the weighting. All the field-unit constants (0.0002637, 141.2, 162.6, 70.6, 4.064, 2452.9, 0.23395, 0.8935, 1422) I re-derived from SI unit conversions and they match the published values to 4-5 digits, so each one has an independent verification path. The strongest analytic oracle for unit tests: the log-derivative of the line-source solution is exactly 0.5*exp(-rD^2/(4 tD)) in pD, and the Bourdet algorithm is exact to machine precision for data that are linear in ln(t) — so the IARF plateau must come out at exactly 0.5000000000 for any L. For a power law Dp = A t^n on a uniform ln grid of spacing h, the estimator has a closed-form bias sinh(n*h)/(n*h) that must be used as the test tolerance rather than ignored.

## Equations

### Bourdet three-point derivative on non-uniform log-time grid (Bourdet et al. 1989, Eq. 8) — VERBATIM

```
(dp/dX)_i = [ (Delta_p1 / Delta_X1) * Delta_X2 + (Delta_p2 / Delta_X2) * Delta_X1 ] / ( Delta_X1 + Delta_X2 )

where, with j = chosen LEFT index (j < i) and k = chosen RIGHT index (k > i):
  Delta_X1 = X_i - X_j   (left spacing, > 0)
  Delta_p1 = p_i - p_j   (left pressure increment)
  Delta_X2 = X_k - X_i   (right spacing, > 0)
  Delta_p2 = p_k - p_i   (right pressure increment)

Equivalently: dp/dX|_i = ( w1*s1 + w2*s2 ) / (w1 + w2) with s1 = Delta_p1/Delta_X1, s2 = Delta_p2/Delta_X2, w1 = Delta_X2, w2 = Delta_X1.

WEIGHTING DIRECTION (the commonly transcribed error): the LEFT slope is multiplied by the RIGHT spacing and the RIGHT slope by the LEFT spacing — i.e. each slope is weighted by the OPPOSITE interval. The nearer point therefore gets the LARGER weight. Verified numerically against the paper's own Table 1 (see independent_checks).

Plotted quantity (the 'Bourdet derivative'): Delta_p_prime = dDelta_p/dln(t) = t * dDelta_p/dt for drawdown, i.e. the semilog slope expressed per natural-log cycle.
```

*Unit system:* unit-agnostic (X and p in any consistent units); in practice X = ln(time function) [dimensionless], p in psi (field) or kPa (SI)

| Symbol | Meaning | Units |
|---|---|---|
| `i` | index of the point at which the derivative is placed | - |
| `X` | time function: ln(Delta t) for drawdown; modified-Horner or superposition time expressed in NATURAL logarithm for buildup | dimensionless (natural-log argument) |
| `p` | pressure or pressure change Delta_p at the corresponding point | psi (field) / kPa (SI) |
| `Delta_X1, Delta_X2` | log-time spacing to the selected left (1) and right (2) point | natural-log cycles |
| `Delta_p1, Delta_p2` | pressure increment to the selected left (1) and right (2) point | psi / kPa |

Assumptions:

- Points 1 and 2 are 'point before i' and 'point after i' (paper's words: '1 = point before i, 2 = point after').
- X must be monotonically increasing; p need not be.
- Formula reduces to the ordinary central difference (p_k - p_j)/(X_k - X_j) when Delta_X1 = Delta_X2, and to the plain forward/backward slope when one spacing tends to zero.
- It is exact (machine precision) whenever p is an affine function of X — hence the IARF plateau is reproduced exactly.

*Source:* Bourdet, D.P., Ayoub, J.A., Pirard, Y.M., 'Use of Pressure Derivative in Well-Test Interpretation', SPE Formation Evaluation, June 1989, p. 296, Eq. 8 (SPE-12777-PA). OCR full text retrieved this session.  
*Access:* full-text retrieved

### L-smoothing window: point selection rule (Bourdet et al. 1989) — VERBATIM paraphrase of the selection criterion

```
Given smoothing parameter L (a distance on the X axis, i.e. in NATURAL-log cycles of the time function):
  left index  j = max{ m < i : X_i - X_m >= L }   (i.e. the FIRST point going left whose Delta_X1 >= L)
  right index k = min{ m > i : X_m - X_i >= L }   (i.e. the FIRST point going right whose Delta_X2 >= L)
Paper text: 'The differentiation algorithm selects Points 1 and 2 as being the first ones such that Delta_X_{1,2} > L.'

L = 0 degenerates to the three-consecutive-points algorithm (j = i-1, k = i+1).

END EFFECT (paper's own term): when i is closer to the last recorded point than L, no right point satisfies the rule. Bourdet's remedy is a 'pseudo right' derivative that becomes FIXED: it is defined between the LAST point and the first point before the last such that Delta_X > L. The symmetric statement applies at the start of the data.
```

*Unit system:* L is dimensionless, measured in natural-log cycles of X

| Symbol | Meaning | Units |
|---|---|---|
| `L` | minimum abscissa distance, on the X (time-function) axis, between point i and the points used for the left/right slopes | natural-log cycles (dimensionless). NOTE: L = 0.1 in ln units = 0.0434 decades; L = 0.1 decades = 0.2303 in ln units |
| `i` | point of interest | - |

Assumptions:

- The paper uses '>' ; a '>=' implementation differs only on exact ties and did not change the Table 1 reproduction.
- Because X is a semilog/superposition axis, a fixed L gives naturally MORE smoothing at late time (the paper notes the late-time compression effect, more pronounced on Horner/superposition plots).
- The paper permits a variable L (larger at early time) to avoid over-smoothing at late times.
- L is applied to X, NOT to t. Applying L to raw elapsed time is a defect.

*Source:* Bourdet et al. 1989, SPEFE p. 296-297 ('Preferred Algorithm', 'End Effect'). Typical-value statement, verbatim: 'Common values for L are 0 (consecutive points) up to 0.5 in extreme cases.' Fig. 10 of the same paper uses L = 0.1 and states it 'proved to be sufficient and does not affect the shape of the original derivative'.  
*Access:* full-text retrieved

### Infinite-acting radial flow: semilog slope m and derivative plateau (oil, field units)

```
Semilog straight line (MDH form):
  Delta_p = 162.6 * (q*B*mu)/(k*h) * [ log10(Delta_t) + log10( k/(phi*mu*c_t*r_w^2) ) - 3.2275 + 0.86859*S ]
  => m = |semilog slope| = 162.6 * q*B*mu/(k*h)   [psi per LOG10 cycle]

Bourdet log-derivative plateau (the horizontal line on the log-log plot):
  Delta_p_prime_plateau = dDelta_p/dln(t) = m / ln(10) = m / 2.302585
                        = 70.6 * q*B*mu/(k*h)   [psi]

EXACT relation between the constants:
  162.6 / ln(10) = 70.617 ;  141.2 / 2 = 70.60 ;  141.2 * ln(10)/2 = 162.57

WHICH CONSTANT APPLIES TO WHAT:
  141.2 -> scales dimensionless pressure to pressure:  Delta_p = 141.2*(q*B*mu/(k*h)) * p_D
  162.6 -> the SEMILOG SLOPE per decade of the IARF straight line (162.6 = 141.2*ln(10)/2)
   70.6 -> the DERIVATIVE PLATEAU height on the log-log plot (70.6 = 141.2/2 = 162.6/ln10), because p_D' = 0.5 during IARF

Permeability from the derivative alone:
  k = 70.6 * q*B*mu / ( h * Delta_p_prime_plateau )

In dimensionless form (Bourdet et al. 1989, Eq. 6):  (t_D/C_D) * p_D' = 0.5
```

*Unit system:* oilfield/field units; pressure ABSOLUTE (psia) where an absolute value is used, Delta_p is a difference so gauge/absolute is immaterial

| Symbol | Meaning | Units |
|---|---|---|
| `Delta_p` | pressure change, p_i - p_wf (drawdown) or p_ws - p_wf(dt=0) (buildup) | psi |
| `q` | surface oil rate (constant) | STB/D |
| `B` | formation volume factor | res bbl/STB |
| `mu` | oil viscosity | cp |
| `k` | effective permeability | md |
| `h` | net pay thickness | ft |
| `phi` | porosity | fraction |
| `c_t` | total compressibility | 1/psi |
| `r_w` | wellbore radius | ft |
| `Delta_t` | elapsed time | hours |
| `S` | van Everdingen-Hurst skin | dimensionless |
| `m` | absolute value of semilog straight-line slope | psi/log10-cycle |
| `Delta_p_prime` | Bourdet log-derivative, dDelta_p/dln(t) | psi (per natural-log cycle) |

Assumptions:

- Single-phase slightly compressible liquid, constant q, constant properties, infinite-acting homogeneous reservoir.
- Wellbore storage finished, boundaries not yet felt.
- Delta_t in HOURS (the 3.2275 and 0.0002637 constants carry the hour convention).
- 3.2275 = -log10(0.0002637) - 0.80907/ln(10) ; 0.86859 = 2/ln(10).

*Source:* Bourdet et al. 1989 (141.2 group quoted verbatim: 'kh/141.2 q B mu in usual oilfield units'); semilog field-unit form retrieved from Kazan Federal University 'Well Test Analysis' course notes (reproducing Bourdet, 'Well Test Analysis: The Use of Advanced Interpretation Models', Elsevier 2002), Eqs. 2a/3a/4a; constants re-derived independently this session from SI unit conversion.  
*Access:* full-text retrieved

### Dimensionless groups, field units (oil)

```
t_D   = 0.0002637 * k * t / ( phi * mu * c_t * r_w^2 )
t_D/r_D^2 = 0.0002637 * k * t / ( phi * mu * c_t * r^2 ),   r_D = r/r_w
p_D   = k * h * Delta_p / ( 141.2 * q * B * mu )
C_D   = 0.8935 * C / ( phi * h * c_t * r_w^2 )
t_D/C_D = 0.0002951 * k * h * t / ( mu * C )   [= 0.0002637/0.8935 * kh t/(mu C)]

EXACT VALUES AND WHAT THEY CARRY:
  0.0002637 = (1 md * 1 hr)/(1 cp * 1 psi^-1 * 1 ft^2) expressed dimensionlessly. Re-derived: (9.869233e-16 m^2 * 3600 s)/(1e-3 Pa.s * 1.450377e-4 Pa^-1 * 0.3048^2 m^2) = 2.636786e-4. It carries md-hr-cp-psi^-1-ft.
  141.2 = 1/(2*pi) group: p_D = 2*pi*k*h*Delta_p/(q_res*mu) in SI. Re-derived: 2*pi*9.869233e-16*0.3048*6894.757/(1.840131e-6*1e-3) = 7.081879e-3 = 1/141.2055. It carries STB/D, res bbl/STB, cp, md, ft, psi.
  0.8935 = 5.614583/(2*pi) = 0.893544 (bbl -> ft^3 conversion inside the 2*pi group); C in bbl/psi.
```

*Unit system:* oilfield/field units; t in HOURS

| Symbol | Meaning | Units |
|---|---|---|
| `t_D` | dimensionless time | - |
| `p_D` | dimensionless pressure | - |
| `C` | wellbore storage constant | bbl/psi |
| `C_D` | dimensionless wellbore storage | - |
| `r` | radial distance | ft |

Assumptions:

- t in hours. If t is in days the constant becomes 0.006328 (= 0.0002637*24).
- k in md, h in ft, mu in cp, c_t in 1/psi, r_w in ft, q in STB/D, B in res bbl/STB, Delta_p in psi.
- Radial, single-phase, slightly compressible.

*Source:* 0.0002637 and 141.2 as printed in Bourdet et al. 1989 and in Escobar, 'Gas Well Testing' (IntechOpen, 2017, Eqs. 17-22); C_D = 0.8935 C/(phi h c_t r_w^2) from the same Escobar Eq. 22. All three re-derived from SI conversions this session (agreement to 4-5 significant figures).  
*Access:* full-text retrieved

### Line-source (Theis / exponential-integral) solution and its logarithmic approximation

```
Exact line-source (constant rate, infinite homogeneous, S = 0, no storage):
  p_D(r_D, t_D) = -(1/2) * Ei( -r_D^2 / (4*t_D) ) = (1/2) * E1( r_D^2 / (4*t_D) )
  with E1(x) = integral_x^inf ( e^-u / u ) du ,  Ei(-x) = -E1(x)

Field units (oil):
  p(r,t) = p_i + 70.6 * (q*B*mu/(k*h)) * Ei( -948 * phi*mu*c_t*r^2 / (k*t) )
  (Ei is negative, so pressure drops.)  948 = 1/(4*0.0002637) = 948.047, i.e. exactly the argument r_D^2/(4 t_D).

LOGARITHMIC APPROXIMATION:
  For x = r_D^2/(4*t_D) small,  E1(x) -> -ln(gamma*x) = -ln(x) - 0.5772156649
  so  p_D = (1/2) * [ ln(t_D/r_D^2) + 0.80907 ]
  with 0.80907 = ln(4/gamma) = ln(4) - 0.5772156649 = 0.8090691, gamma = exp(0.5772156649) = 1.7810724 (Bourdet's nomenclature: 'gamma = exponential of Euler constant (~1.78)')

VALIDITY CRITERION: t_D/r_D^2 > 25  (equivalently x < 0.01).
  Verified numerically this session: at t_D/r_D^2 = 25 the log approximation is 0.247% LOW relative to E1; at 12.5 it is 0.59% low; at 2.5 it is 5.35% low; at 100 it is 0.046% low.

EXACT LOG-DERIVATIVE OF THE Ei SOLUTION (the strongest oracle):
  t_D * dp_D/dt_D = dp_D/dln(t_D) = 0.5 * exp( -r_D^2/(4*t_D) )
  -> at the well (r_D = 1) this rises monotonically to the 0.5 plateau; for an observation well it is the same curve shifted by r_D^2.
  Using the log approximation instead gives exactly 0.5 for all t_D (see independent_checks).

Other standard time limits (both self-consistent with 0.0002637):
  Line-source valid (finite-wellbore effect negligible): t_D > 100, i.e. t > 3.79e5 * phi*mu*c_t*r_w^2/k   [0.0002637*3.79e5 = 99.9]
  Infinite-acting ends (closed circle, t_D = 0.25*r_eD^2): t < 948 * phi*mu*c_t*r_e^2/k
```

*Unit system:* dimensionless, plus field-unit form (t in hours, r in ft)

| Symbol | Meaning | Units |
|---|---|---|
| `E1(x)` | exponential integral, = -Ei(-x) | - |
| `gamma` | exp(Euler-Mascheroni constant) | - |
| `r_D` | r/r_w | - |
| `p_i` | initial reservoir pressure, ABSOLUTE (psia) | psia |

Assumptions:

- Infinite, homogeneous, isotropic, horizontal, constant-thickness reservoir; single slightly compressible fluid of constant mu and c_t; constant rate; zero wellbore storage; line (zero-radius) source.
- Constant c_t: for gas this fails and pseudopressure/pseudotime must be used.
- The 25 / 100 / 948 criteria are conventional rounded thresholds, not sharp boundaries.

*Source:* Theis (1935); Matthews & Russell / Earlougher / J. Lee, 'Well Testing' (SPE Textbook Vol. 1) for the field-unit Ei form with 70.6 and 948. The t_D/r_D^2 > 25 criterion with p_D = 0.5[ln(t_D/r_D^2) + 0.80907] was confirmed in a retrieved search result; the 0.25%-error figure and the exact derivative identity were computed independently this session.  
*Access:* secondary source

### Pure wellbore storage: unit slope and the Delta_p = derivative identity

```
Delta_p = q*B*Delta_t / (24*C)        [field units, Delta_t in hours, C in bbl/psi]
log10(Delta_p) = log10(q*B/(24*C)) + log10(Delta_t)   -> UNIT SLOPE on log-log

Derivative:  Delta_p_prime = Delta_t * dDelta_p/dDelta_t = q*B*Delta_t/(24*C) = Delta_p
=> IDENTITY: during pure wellbore storage the Bourdet derivative curve and the Delta_p curve are COINCIDENT (not merely parallel), both on a unit slope.

Dimensionless (Bourdet et al. 1989, Eqs. 1 and 5):  p_D = t_D/C_D  and  (t_D/C_D)*p_D' = t_D/C_D.

C from the storage straight line:  C = q*B / (24 * m_WBS),  m_WBS = slope of Delta_p vs Delta_t on a CARTESIAN plot [psi/hr].

24 = hours per day (q is per day, Delta_t in hours).
```

*Unit system:* oilfield/field units

| Symbol | Meaning | Units |
|---|---|---|
| `C` | wellbore storage coefficient | bbl/psi |
| `m_WBS` | slope of Delta_p vs Delta_t, Cartesian | psi/hr |

Assumptions:

- Constant C (changing storage breaks both the unit slope and the identity).
- Pure storage only: the identity is lost as soon as sandface rate starts to differ from surface rate.
- In practice the identity is the single best sanity check on a derivative implementation applied to real early-time data.

*Source:* Bourdet et al. 1989 Eqs. 1 and 5; Delta_p = q B Delta_t/(24 C) and C = q B/(24 m_WBS) retrieved from the Kazan Federal University 'Well Test Analysis' notes (Bourdet 2002 book equations).  
*Access:* full-text retrieved

### Linear flow (infinite-conductivity vertical fracture / channel): 1/2 slope

```
Delta_p = 4.064 * ( q*B/(h*x_f) ) * sqrt( mu/(phi*k*c_t) ) * sqrt(Delta_t)
Delta_p_prime = Delta_t * dDelta_p/dDelta_t = (1/2) * Delta_p
=> both Delta_p and Delta_p_prime are straight lines of slope +1/2 on log-log, separated by a factor of 2 (0.30103 log10 cycles).

Specialized plot: Delta_p vs sqrt(Delta_t), straight line through the ORIGIN with slope m_LF [psi/hr^0.5]
  x_f = 4.064 * (q*B/(h*m_LF)) * sqrt( mu/(phi*k*c_t) )

Constant re-derived this session from the 1-D constant-flux diffusion solution Delta_p = (q_res*mu/(k*A))*2*sqrt(eta*t/pi) with A = 4*x_f*h (two wings, two faces) and eta = k/(phi*mu*c_t): gives 4.064095 in field units.
```

*Unit system:* oilfield/field units, Delta_t in hours

| Symbol | Meaning | Units |
|---|---|---|
| `x_f` | fracture HALF-length | ft |
| `m_LF` | slope of Delta_p vs sqrt(Delta_t) | psi/hr^0.5 |
| `eta` | hydraulic diffusivity k/(phi mu c_t) | ft^2/hr in field form (with the 0.0002637 conversion) |

Assumptions:

- Infinite fracture conductivity (no pressure drop along the fracture), fully penetrating vertical fracture, symmetric wings.
- Flow strictly perpendicular to the fracture face: valid only for t_Dxf = 0.0002637*k*t/(phi*mu*c_t*x_f^2) below about 0.016 (recalled threshold, Gringarten et al. 1974 — NOT retrieved this session).
- Same 1/2 slope is produced by a channel/two-parallel-sealing-fault geometry at late time, so a 1/2 slope is NOT by itself diagnostic of a fracture.

*Source:* Field-unit form (printed as 4.06) retrieved from Kazan Federal University 'Well Test Analysis' notes, Eqs. 8a/9a (Bourdet 2002 book). Constant independently re-derived as 4.064095 this session.  
*Access:* full-text retrieved

### Bilinear flow (finite-conductivity vertical fracture): 1/4 slope

```
Delta_p = 44.11 * ( q*B*mu ) / ( h * sqrt(k_f*w_f) * (phi*mu*c_t*k)^(1/4) ) * Delta_t^(1/4)
Delta_p_prime = Delta_t * dDelta_p/dDelta_t = (1/4) * Delta_p
=> both curves have slope +1/4 on log-log, separated by a factor of 4 (0.60206 log10 cycles).

Specialized plot: Delta_p vs Delta_t^(1/4), straight line through the origin with slope m_BLF [psi/hr^0.25]
  k_f*w_f = 1944.8 * sqrt( 1/(phi*mu*c_t*k) ) * ( q*B*mu/(h*m_BLF) )^2
  (consistency check performed this session: 44.11^2 = 1945.7, matching the printed 1944.8 to 0.05%)
```

*Unit system:* oilfield/field units, Delta_t in hours

| Symbol | Meaning | Units |
|---|---|---|
| `k_f` | fracture permeability | md |
| `w_f` | fracture width | ft |
| `k_f*w_f` | fracture conductivity | md-ft |
| `k` | reservoir permeability | md |
| `m_BLF` | slope of Delta_p vs Delta_t^(1/4) | psi/hr^0.25 |

Assumptions:

- Simultaneous incompressible linear flow inside the fracture + compressible linear flow from formation into the fracture; fracture tips not yet felt.
- Exists only for low dimensionless conductivity; commonly quoted range C_fD = k_f*w_f/(k*x_f) < about 300, and the regime ends near t_Dxf ~ 0.1/C_fD^2 for C_fD >= 3 (RECALLED from Cinco-Ley & Samaniego 1981 — NOT retrieved this session, treat as unverified).
- Constant printed as 44.11 in the retrieved source; 44.1 is the value usually quoted in secondary literature.

*Source:* Field-unit form retrieved from Kazan Federal University 'Well Test Analysis' notes, Eqs. 10a/11a (Bourdet 2002 book), attributed there to Cinco-Ley et al. 1978.  
*Access:* full-text retrieved

### Spherical (and hemispherical) flow: -1/2 derivative slope

```
Delta_p = 70.6 * (q*B*mu)/(k_S * r_S)  -  2452.9 * q*B*mu*sqrt(phi*mu*c_t) / ( k_S^(3/2) * sqrt(Delta_t) )

Delta_p_prime = Delta_t * dDelta_p/dDelta_t = + (1/2) * 2452.9 * q*B*mu*sqrt(phi*mu*c_t) / ( k_S^(3/2) * sqrt(Delta_t) )
              = 1226.45 * q*B*mu*sqrt(phi*mu*c_t) / ( k_S^(3/2) * sqrt(Delta_t) )
=> derivative is a straight line of slope -1/2 on log-log (a DESCENDING half slope), while Delta_p itself flattens toward the constant 70.6 q B mu/(k_S r_S).

Specialized plot: Delta_p vs 1/sqrt(Delta_t), straight line of slope -m_SPH; k_S from m_SPH.

Constant re-derived this session: 70.6/sqrt(pi*0.0002637) = 2453.07, versus the published 2452.9 (0.007% agreement). This confirms the radicand is sqrt(phi*mu*c_t) with k_S^(3/2) in the denominator.
Also 70.6 = 141.2/2 follows exactly from the spherical steady term q*B*mu/(4*pi*k_S*r_S) versus the radial 1/(2*pi*k*h) group.
```

*Unit system:* oilfield/field units, Delta_t in hours

| Symbol | Meaning | Units |
|---|---|---|
| `k_S` | spherical permeability, (k_H^2 * k_V)^(1/3) | md |
| `r_S` | equivalent spherical-flow radius (from the open/perforated interval) | ft |
| `Delta_p_prime` | Bourdet derivative | psi |

Assumptions:

- Partially penetrating / partially completed well, or a wireline formation tester (RFT/MDT/WFT) pretest.
- Top and bottom boundaries not yet reached (otherwise flow reverts to radial and the derivative returns to the 0.5-equivalent plateau).
- Hemispherical flow (well at a sealing boundary) has the same -1/2 slope with a factor-2 change in the constant.
- The retrieved OCR of the source equation renders the radicand ambiguously as sqrt(phi*mu*c_t*k); the form above (sqrt(phi*mu*c_t), no k) is the one that reproduces the published 2452.9 constant by independent derivation.

*Source:* Kazan Federal University 'Well Test Analysis' notes, Eq. 12a (Bourdet 2002 book): 'Delta p = 70.6 qBmu/(k_S r_S) - 2452.9 qBmu sqrt(...)/(k_S^{3/2} sqrt(Delta t))'. Constant re-derived independently this session.  
*Access:* full-text retrieved

### Pseudo-steady state (closed reservoir): unit slope on the DERIVATIVE only

```
Delta_p = m_star * Delta_t + b        (Cartesian straight line)
  m_star = 0.23395 * q*B / ( phi * c_t * A * h )   [psi/hr]   (0.23395 = 5.614583/24)
  b      = 141.2*(q*B*mu/(k*h)) * [ 0.5*ln(4*A/(gamma*C_A*r_w^2)) + S ]  (Dietz shape factor form)

Derivative:  Delta_p_prime = Delta_t * dDelta_p/dDelta_t = m_star * Delta_t
=> the DERIVATIVE has unit slope on log-log; in dimensionless terms p_D' = 2*pi*t_DA.

CRITICAL DIAGNOSTIC DIFFERENCE FROM WELLBORE STORAGE:
  Wellbore storage: BOTH Delta_p and Delta_p_prime have unit slope and are COINCIDENT (b = 0).
  Pseudo-steady state: only Delta_p_prime has unit slope; Delta_p is NOT a unit slope because of the nonzero intercept b (Delta_p flattens then bends up).
  Hence 'unit slope' alone is ambiguous; the Delta_p/Delta_p_prime ratio settles it.

0.23395 re-derived this session: (1 bbl = 5.614583 ft^3) / (24 hr/day).
```

*Unit system:* oilfield/field units, Delta_t in hours

| Symbol | Meaning | Units |
|---|---|---|
| `A` | drainage area | ft^2 |
| `C_A` | Dietz shape factor (31.62 for a circle) | - |
| `t_DA` | 0.0002637*k*t/(phi*mu*c_t*A) | - |
| `m_star` | rate of pressure decline during PSS | psi/hr |

Assumptions:

- Closed (no-flow) outer boundary, all boundaries felt, constant rate.
- Drawdown only. In a BUILDUP there is no pseudo-steady state; the corresponding late-time buildup derivative falls instead of rising.
- Onset conventionally t_DA > 0.1 for a circle (equivalently t > 948*phi*mu*c_t*r_e^2/k).

*Source:* m_star = 0.23395 q B/(phi c_t A h) is the standard field-unit reservoir-limit-test slope (J. Lee, 'Well Testing', SPE Textbook Vol. 1) — RECALLED, not retrieved; the constant was re-derived from 5.614583/24 this session. The 1/2, 1/4, -1/2 and unit slopes are confirmed in retrieved sources (Bourdet 2002 notes; Zonoozi/Blasingame SPE 103204 power-law table).  
*Access:* secondary source

### Power-law identity linking Delta_p and the Bourdet derivative (general oracle)

```
If Delta_p = A * t^n  then  Delta_p_prime = dDelta_p/dln(t) = n * A * t^n = n * Delta_p

=> On log-log, Delta_p and Delta_p_prime are PARALLEL lines of slope n, separated vertically by the constant factor n (i.e. log10(n) cycles).
   n = 1    wellbore storage / PSS-derivative   ratio 1     (coincident for pure storage)
   n = 1/2  linear flow                         ratio 0.5   (factor-2 separation)
   n = 1/4  bilinear flow                       ratio 0.25  (factor-4 separation)
   n = -1/2 spherical flow                      ratio -0.5  (derivative descends)
   n = 0    radial flow: Delta_p ~ ln(t), ratio -> 0, derivative is a horizontal plateau

This is Blasingame's beta-derivative: beta = dln(Delta_p)/dln(t) = Delta_p_prime/Delta_p = n, which is constant exactly over a power-law regime.
```

*Unit system:* unit-agnostic

| Symbol | Meaning | Units |
|---|---|---|
| `n` | power-law exponent = log-log slope | - |
| `A` | power-law coefficient | psi/hr^n |

Assumptions:

- Holds exactly for the analytic form; the discrete Bourdet estimator introduces a known bias (see the sinh equation below).

*Source:* Zonoozi & Blasingame et al., SPE 103204, 'The Pressure Derivative Revisited' (2006) — full text retrieved this session; the paper tabulates the beta-derivative constant values 1, 1/2, 1/4 for storage/boundaries, infinite-conductivity fracture and finite-conductivity fracture respectively.  
*Access:* full-text retrieved

### Bourdet Eq. 7: derivative with respect to Agarwal equivalent time (buildup) — VERBATIM

```
dp / d{ ln[ t_p*Delta_t / (t_p + Delta_t) ] } = Delta_t * [ (t_p + Delta_t) / t_p ] * (dp/dDelta_t)

Agarwal equivalent time:  Delta_t_e = t_p * Delta_t / ( t_p + Delta_t )

Consequences (all exact, testable):
  (a) d ln(Delta_t_e)/d Delta_t = t_p / ( Delta_t * (t_p + Delta_t) )
  (b) TRUE derivative = NAIVE derivative * (t_p + Delta_t)/t_p,
      where NAIVE = Delta_t * dp/dDelta_t = dp/dln(Delta_t)
  (c) => plotting a buildup derivative against ln(Delta_t) alone UNDERSTATES the true value by the factor t_p/(t_p+Delta_t):
        Delta_t = 0.1*t_p -> reads 0.909 of true (-9%)
        Delta_t = t_p     -> reads 0.500 of true (plateau reads 0.25 instead of 0.5 => k in error by a factor 2)
        Delta_t = 10*t_p  -> reads 0.091 of true (-91%)
      The uncorrected buildup derivative therefore DROOPS at late time and mimics a constant-pressure boundary / aquifer support that is not there.
  (d) Note ln(Delta_t_e) and ln(Delta_t/(t_p+Delta_t)) differ only by the additive constant ln(t_p), so they give IDENTICAL derivatives. Only the plotting abscissa changes.
  (e) Bourdet's practice: differentiate with respect to the superposition/Horner function, but PLOT against Delta_t; the result then matches drawdown type curves.
```

*Unit system:* consistent time units (hours in field practice)

| Symbol | Meaning | Units |
|---|---|---|
| `t_p` | producing (flowing) time before shut-in; Horner pseudo-producing time t_p = 24*N_p/q_last for multirate | hours |
| `Delta_t` | shut-in (elapsed) time | hours |
| `Delta_t_e` | Agarwal radial equivalent time | hours |

Assumptions:

- Valid when the Horner method itself is valid: the drawdown must have reached radial flow before shut-in (paper's own caveat). For short t_p the buildup derivative will differ from the drawdown behaviour even after the correction.
- Agarwal's equivalent time is built from LOGARITHMIC (radial) approximations to the Ei solution, so it collapses buildup onto drawdown only for radial flow. There are separate linear (sqrt) and bilinear (quarter-root) equivalent-time forms for fracture regimes; using the radial form in a linear-flow regime is a defect.
- Delta_t_e is NOT monotone-safe at late time for very short t_p: Delta_t_e -> t_p, so the abscissa compresses and many points pile up.

*Source:* Bourdet et al. 1989, SPEFE p. 295, Eq. 7, verbatim, attributed there to Agarwal (ref. 12). Agarwal, R.G., SPE-9289-MS, SPE ATCE Dallas, 21-24 Sept 1980, DOI 10.2118/9289-MS.  
*Access:* full-text retrieved

### Bourdet Eq. 9: multirate superposition time function

```
X = [ 1/(q_n - q_{n-1}) ] * SUM_{i=1}^{n-1} (q_i - q_{i-1}) * ln( SUM_{j=i}^{n-1} Delta_t_j + Delta_t )  +  ln(Delta_t)

Single drawdown then buildup (n = 2, q_1 = q, q_2 = 0) reduces to:
  X = -ln(t_p + Delta_t) + ln(Delta_t) = ln( Delta_t / (t_p + Delta_t) )
which differs from ln(Delta_t_e) only by the additive constant ln(t_p) -> identical derivative.

VERIFIED NUMERICALLY this session: the 'Superposition Time' column of the paper's own Table 1 is reproduced by X = ln(Delta_t/(t_p+Delta_t)) with t_p = 15.330 hr, consistent to +/-0.0002 in X across the full range Delta_t = 0.00417 to 12.25 hr.
```

*Unit system:* time in hours; X dimensionless (natural log)

| Symbol | Meaning | Units |
|---|---|---|
| `q_i` | rate of flow period i (q_0 = 0) | STB/D |
| `n` | index of the current (last) period, whose response is being analysed | - |
| `Delta_t_j` | duration of flow period j | hours |
| `Delta_t` | elapsed time within the current period | hours |

Assumptions:

- Rates piecewise constant; superposition in time valid (linear diffusivity equation) — for gas this requires pseudopressure, and strictly also pseudotime.
- The index arrangement above is reconstructed from a partially OCR-garbled Eq. 9; the reduction to the single-drawdown case was confirmed numerically against the paper's Table 1, but the exact printed index limits should be re-checked against a clean copy of SPE-12777-PA.
- Any additive constant in X is irrelevant to the derivative; only the shape matters.

*Source:* Bourdet et al. 1989, SPEFE p. 296, Eq. 9 (OCR partially garbled); reduction validated numerically against the paper's Table 1 this session.  
*Access:* full-text retrieved

### Gas analogues in pseudopressure (field units) — for a gas reservoir lab

```
Pseudopressure (Al-Hussainy, Ramey & Crawford 1966):
  m(p) = 2 * integral_{p_ref}^{p} [ p' / ( mu(p') * Z(p') ) ] dp'      [psi^2/cp],  p ABSOLUTE (psia)

Dimensionless:
  m(p)_D = k*h*[ m(p_i) - m(p) ] / ( 1422.52 * q_sc * T )
  t_D    = 0.0002637 * k * t / ( phi * (mu*c_t)_i * r_w^2 )

IARF semilog line:
  m(p_i) - m(p_wf) = ( 1.422e6 * q_sc * T / (k*h) ) * [ 1.1513 * log10( k*t/(1688*phi*(mu*c_t)_i*r_w^2) ) + s' + D*q_sc ]
  slope m = 1637.74 * q_sc * T / (k*h)   [psi^2/cp per LOG10 cycle]   ->  k = 1637.74*q_sc*T/(m*h)

BOURDET DERIVATIVE PLATEAU FOR GAS:
  [ t * dDelta_m(p)/dt ]_plateau = m/ln(10) = 1422.52/2 * q_sc*T/(k*h) = 711.26 * q_sc * T / (k*h)   [psi^2/cp]

Mapping to the oil constants: 1422 <-> 141.2*q*B*mu ; 1637.74 <-> 162.6 ; 711.26 <-> 70.6.
Cross-checks done this session: 1422.52*ln(10)/2 = 1637.75 (matches the printed 1637.74); log10(1688) = 3.2274 (matches the oil-case 3.2275); 1422 re-derived from 2*141.2055*1000*B_g with B_g = 0.005035*z*T/p res bbl/scf -> 1421.9.
```

*Unit system:* oilfield/field units for gas. q_sc in Mscf/D, T in DEGREES RANKINE (ABSOLUTE, = degF + 459.67), m(p) in psi^2/cp, pressure ABSOLUTE (psia), t in hours

| Symbol | Meaning | Units |
|---|---|---|
| `m(p)` | real gas pseudopotential | psi^2/cp |
| `q_sc` | gas rate at standard conditions | Mscf/D |
| `T` | reservoir temperature, ABSOLUTE | degR |
| `Z` | gas compressibility factor | - |
| `s'` | apparent (rate-dependent) skin = s + D*q_sc | - |
| `D` | non-Darcy (turbulence) coefficient | 1/(Mscf/D) |
| `t_a(p)` | pseudotime = integral dt/(mu*c_t) | hr-psi/cp |

Assumptions:

- Pseudopressure linearises the mu-Z dependence but NOT the (mu*c_t) time dependence; for drawdowns with large pressure change, and for essentially all buildups, pseudotime t_a(p) is also required (then t_Da = 0.0002637*k*t_a(p)/(phi*r_w^2) and (mu c_t)_i is set to unity).
- The 1422 constant depends on the standard-condition convention (p_sc = 14.7 psia, T_sc = 520 degR gives 1421.9; 14.65 psia / 519.67 degR shifts it by ~0.3%). Use one convention consistently.
- Absolute temperature is mandatory: using degF silently produces a ~1.8x error in k.
- Non-Darcy skin means two flow rates are needed to separate s from D.

*Source:* Escobar, F.H., 'Gas Well Testing', Ch. 5 in Advances in Natural Gas Emerging Technologies, IntechOpen 2017, DOI 10.5772/67620 — Eqs. 7, 17-21, 25, 29 (full text retrieved this session). Original pseudopressure: Al-Hussainy, Ramey & Crawford (1966) — recalled, not retrieved.  
*Access:* full-text retrieved

### Exact discretisation bias of the Bourdet estimator on a power law (derived this session)

```
For Delta_p = A*exp(n*X) sampled at X_j = X_i - a and X_k = X_i + b (a, b > 0 in natural-log units), the Bourdet three-point estimator returns EXACTLY:

  est = A*exp(n*X_i) * [ (1 - exp(-n*a))/a * b + (exp(n*b) - 1)/b * a ] / (a + b)

Uniform log grid (a = b = h):
  est = A*exp(n*X_i) * sinh(n*h)/h = (n*Delta_p) * [ sinh(n*h)/(n*h) ]

=> the estimator is HIGH by the factor sinh(n*h)/(n*h) >= 1 (equality only at n*h = 0).
Worked values (grid of 10 points/decade, h = ln(10)/10 = 0.230259):
  L = 0 (nearest neighbours, h = 0.230259): n = 1 -> +0.886% ; n = 1/2 -> +0.221% ; n = 1/4 -> +0.055%
  L = 0.5 (3 steps away, spacing 0.690776): n = 1 -> +8.14% ; n = 1/2 -> +2.00%
Radial flow (n = 0, Delta_p affine in X): bias is exactly ZERO for any h and any L.
```

*Unit system:* unit-agnostic

| Symbol | Meaning | Units |
|---|---|---|
| `h` | uniform natural-log spacing between samples | natural-log cycles |
| `a, b` | actual left and right log spacings selected by the L rule | natural-log cycles |
| `n` | power-law exponent | - |

Assumptions:

- Noise-free data; this is a pure discretisation/smoothing bias, independent of noise.
- Explains why the unit-slope storage asymptote is the regime most distorted by large L, and why the radial plateau is not distorted at all.

*Source:* Derived analytically and confirmed numerically this session (sinh(0.5*0.230259)/(0.5*0.230259) = 1.002211 matched the measured ratio 0.501105/0.5 to 6 digits).  
*Access:* Unverified — supporting source not established - not retrieved

## Constants

| Name | Value | Units | Source | How verified |
|---|---|---|---|---|
| Bourdet L, typical range | `0 to 0.5, with 0.1 the paper's own working value` | natural-log cycles of the time function X | Bourdet et al. 1989, SPEFE p. 297: 'Common values for L are 0 (consecutive points) up to 0.5 in extreme cases.' Fig. 10 uses L = 0.1. | verbatim from retrieved OCR full text; the L = 0.1 column of the paper's Table 1 was reproduced numerically this session |
| Bourdet L, typical range (commercial-software convention) | `0.01 to 0.2` | DECADIC log cycles (log10), NOT natural log | IHS/Fekete WellTest documentation, 'Derivative Analyses': 'DX represents the log-cycle fraction used to control the amount of smoothing... this value is typically quite small (0.01 to 0.2)' | retrieved this session (text of the page; the equation image itself was not retrievable). Flagged as a UNIT-CONVENTION CLASH with Bourdet's L |
| t_D field-unit constant | `0.0002637 (exact derived value 2.636786e-4)` | carries md, hr, cp, psi^-1, ft^2; i.e. dimensionless when k[md], t[hr], mu[cp], c_t[1/psi], r_w[ft] | Bourdet et al. 1989; Escobar 2017 Eq. 17 | re-derived from SI this session: (9.869233e-16 m^2 * 3600 s)/(1e-3 Pa.s * 1.450377e-4 Pa^-1 * 0.09290304 m^2) = 2.636786e-4 |
| p_D field-unit constant | `141.2 (exact derived value 141.2055)` | carries STB/D, res bbl/STB, cp, md, ft, psi | Bourdet et al. 1989 verbatim: 'kh/141.2 q B mu in usual oilfield units' | re-derived from p_D = 2*pi*k*h*Delta_p/(q_res*mu) in SI this session: 1/7.081879e-3 = 141.2055 |
| Semilog slope constant (oil) | `162.6 (exact derived value 162.569)` | psi per log10 cycle, per (STB/D * res bbl/STB * cp)/(md*ft) | Kazan Federal University 'Well Test Analysis' notes Eq. 2a/3a (Bourdet 2002 book equations) | re-derived this session as 141.2055*ln(10)/2 = 162.5688 |
| Derivative plateau constant (oil) | `70.6 (exact derived value 70.6028)` | psi, per (STB/D * res bbl/STB * cp)/(md*ft) | same source; also appears as the Ei-solution prefactor in Lee/Earlougher | re-derived this session two ways: 141.2055/2 = 70.6028 and 162.5688/ln(10) = 70.6028 |
| Euler exponential gamma | `1.7810724 (= exp(0.5772156649))` | dimensionless | Bourdet et al. 1989 nomenclature: 'gamma = exponential of Euler constant (~1.78)' | computed this session |
| Log-approximation constant in p_D | `0.80907 (exact 0.8090692)` | dimensionless | Bourdet et al. 1989 Eq. 2 ('p_D = 0.5[ln(t_D/C_D) + 0.80907 + ln C_D e^{2S}]') | re-derived this session as ln(4) - 0.5772156649 = ln(4/gamma) = 0.8090692 |
| Semilog field-unit offset | `3.2275 (often printed 3.23)` | dimensionless (log10 units) | Kazan Federal University notes Eq. 2a/4a; equivalently the 1688 inside the gas form (log10(1688) = 3.2274) | re-derived this session as -log10(0.0002637) - 0.80907/ln(10) = 3.5787 - 0.35137 = 3.2273 |
| Ei-argument constant | `948 (exact 948.047)` | carries phi, cp, psi^-1, ft^2, md, hr | Standard field-unit Ei solution (Lee, 'Well Testing', SPE Textbook Vol. 1) — recalled | re-derived this session as 1/(4*0.0002637) = 948.047, i.e. exactly r_D^2/(4 t_D) |
| Line-source lower time limit constant | `3.79e5 (t_D > 100)` | carries phi, cp, psi^-1, ft^2, md, hr | Lee, 'Well Testing' — recalled, not retrieved | self-consistency check this session: 3.79e5 * 0.0002637 = 99.94, i.e. t_D = 100 |
| Linear flow constant | `4.064 (printed as 4.06 in the retrieved source)` | psi per (STB/D * res bbl/STB)/(ft*ft) * sqrt(cp/(md/psi)) * hr^-0.5 — i.e. field units throughout | Kazan Federal University notes Eq. 8a (Bourdet 2002) | re-derived this session from the 1-D constant-flux solution with A = 4*x_f*h: 4.064095 |
| Bilinear flow constant | `44.11 (commonly quoted as 44.1)` | field units (psi, STB/D, res bbl/STB, cp, ft, md-ft, hr^0.25) | Kazan Federal University notes Eq. 10a (Bourdet 2002), after Cinco-Ley et al. 1978 | retrieved; NOT independently re-derived. Internal consistency only: 44.11^2 = 1945.7 vs the printed companion constant 1944.8 (0.05%) |
| Spherical flow constant | `2452.9 (derived 2453.07)` | field units (psi, STB/D, res bbl/STB, cp, md^1.5, hr^0.5) | Kazan Federal University notes Eq. 12a (Bourdet 2002) | re-derived this session as 70.6028/sqrt(pi*0.0002637) = 2453.07 |
| Pseudo-steady-state depletion constant | `0.23395 (exact 0.2339410)` | psi/hr per (STB/D * res bbl/STB)/(fraction * psi^-1 * ft^2 * ft) | Standard reservoir-limit-test slope (Lee, 'Well Testing') — recalled | re-derived this session as 5.614583/24 |
| Wellbore storage time constant | `24` | hours per day (q in STB/D, Delta_t in hr, C in bbl/psi) | Kazan Federal University notes (Delta_p = q*B*Delta_t/(24*C)) | retrieved and dimensionally checked this session |
| C_D field-unit constant | `0.8935 (exact 0.893544)` | carries bbl/psi, fraction, ft, psi^-1, ft^2 | Escobar 2017 Eq. 22 | re-derived this session as 5.614583/(2*pi) |
| Gas p_D constant | `1422.52 (commonly quoted 1422)` | carries Mscf/D, degR, md, ft, psi^2/cp | Escobar 2017 Eqs. 19a/20/21 | re-derived this session as 2*141.2055*1000*B_g with B_g = 0.0050349 res bbl/scf (p_sc = 14.7 psia, T_sc = 520 degR) -> 1421.9; the residual ~0.05% is the standard-condition convention |
| Gas semilog slope constant | `1637.74 (commonly quoted 1637)` | psi^2/cp per log10 cycle, per (Mscf/D * degR)/(md*ft) | Escobar 2017 Eq. 29: 'k = 1637.74 q T/(m h)' | re-derived this session as 1422.52*ln(10)/2 = 1637.75 |
| Gas derivative plateau constant | `711.26 (commonly quoted 711)` | psi^2/cp, per (Mscf/D * degR)/(md*ft) | Implied by Escobar 2017 Eqs. 19a/20 (plateau = half the p_D group) | derived this session as 1422.52/2 = 711.26; consistent with 1637.74/ln(10) = 711.26 |
| Log-approximation validity threshold | `t_D/r_D^2 > 25 (equivalently r_D^2/(4 t_D) < 0.01)` | dimensionless | Standard criterion; confirmed in a retrieved search result stating 'When t_D/r_D^2 > 25, p_D = 1/2[ln(t_D/r_D^2) + 0.80907]' | error magnitude computed independently this session: 0.247% low at t_D/r_D^2 = 25, 0.593% at 12.5, 5.35% at 2.5, 0.046% at 100 |

## Validity ranges

- Bourdet Eq. 8 itself has no physical validity range - it is a pure numerical estimator. Its accuracy range is set by the discretisation bias sinh(n*h)/(n*h): exact for radial flow (n = 0), and increasingly biased HIGH as |n|*spacing grows. With 10 points/decade and L = 0 the worst case (unit slope) is +0.89%; with L = 0.5 it is +8.1%.
- L must be expressed on the X axis (natural log of the time function). Bourdet's tested range is L = 0 to 0.5 ln-cycles, i.e. 0 to 0.217 decades. Commercial software conventions quoting 0.01-0.2 are in DECADES (0.023-0.46 ln-cycles) - the two ranges overlap but are not the same numbers.
- Line-source (Ei) solution: valid once finite-wellbore effects are negligible, t_D > 100 (t > 3.79e5*phi*mu*c_t*r_w^2/k), and while the reservoir is infinite-acting, t < 948*phi*mu*c_t*r_e^2/k (closed circle).
- Logarithmic approximation to Ei: t_D/r_D^2 > 25 for <0.25% error. Below t_D/r_D^2 ~ 10 the approximation is worse than 0.6% and must not be used to pick a semilog slope.
- IARF derivative plateau: only after wellbore storage has died out. Common rule of thumb t > (200000 + 12000*S)*C/(k*h/mu) hours (RECALLED, not retrieved - treat as unverified).
- Linear flow (infinite-conductivity fracture): t_Dxf below about 0.016 (RECALLED from Gringarten et al. 1974 - unverified).
- Bilinear flow: C_fD = k_f*w_f/(k*x_f) below roughly 300; the regime ends near t_Dxf ~ 0.1/C_fD^2 for C_fD >= 3 (RECALLED from Cinco-Ley & Samaniego 1981 - unverified).
- Spherical flow: between the end of the local radial flow across the open interval and the time the top/bottom no-flow boundaries are reached.
- Pseudo-steady state: drawdown only, after all boundaries are felt (t_DA > 0.1 for a circle). PSS does not exist in a buildup.
- Agarwal equivalent time: collapses buildup onto drawdown only for RADIAL flow and only when the drawdown reached radial flow before shut-in (Bourdet's own caveat). Separate sqrt and quarter-root equivalent-time forms exist for linear and bilinear regimes.
- Gas pseudopressure: linearises mu-Z only. For drawdowns with appreciable pressure change, and for essentially all buildups, pseudotime is also required.
- All field-unit constants above assume t in HOURS. Days multiply 0.0002637 by 24 (-> 0.006328) and change the 3.2275 offset accordingly.

## Failure modes

- WEIGHTING TRANSPOSED - the single most common transcription error. Writing [(Dp1/DX1)*DX1 + (Dp2/DX2)*DX2]/(DX1+DX2) (each slope weighted by its OWN spacing) is a plausible-looking but wrong formula; it silently degrades to a spacing-biased average and gives 5.44592 instead of 5.99244 on the published Table 1 row. It agrees with the correct formula on a uniform grid, so uniform-grid tests do NOT catch it.
- L UNIT CONFUSION - Bourdet's L is in natural-log cycles; many commercial tools quote it in decades. A factor ln(10) = 2.303 in either direction. Reproducing the paper's Table 1 L=0.1 column gives 26.073 (ln units, correct) vs 30.901 (decade units, wrong) at Delta_t = 0.04583 hr.
- L APPLIED TO t RATHER THAN TO X - selecting points on |t_k - t_i| >= L instead of |X_k - X_i| >= L destroys the whole point of log-cycle smoothing (no smoothing at early time, total over-smoothing at late time).
- BUILDUP DERIVATIVE TAKEN WITH RESPECT TO ln(Delta_t) instead of the superposition/Agarwal function - the derivative is low by the factor t_p/(t_p+Delta_t) and droops at late time, which is routinely misread as a constant-pressure boundary or aquifer support. At Delta_t = t_p the plateau reads 0.25 instead of 0.5 and k is wrong by a factor of 2.
- END EFFECT untreated - within L of the first or last point no valid left/right neighbour exists. Silently falling back to a one-sided slope produces a spurious late-time kink or drop that mimics a boundary. Bourdet's own remedy is the FIXED 'pseudo right' derivative between the last point and the first point before the last with Delta_X > L.
- OVER-SMOOTHING - large L flattens genuine transitions (dual-porosity trough, fault doubling) and biases power-law regimes high by sinh(n*L)/(n*L). The paper is explicit that a compromise between smoothness and distortion is required; the recommended cure is to apply the SAME L to the model/type curve as to the data.
- UNIT-SLOPE AMBIGUITY - both pure wellbore storage and pseudo-steady state give a unit-slope derivative. They are distinguished by the ratio Delta_p_prime/Delta_p: exactly 1 (coincident curves) for storage, but less than 1 and varying for PSS because of the nonzero Cartesian intercept.
- HALF-SLOPE AMBIGUITY - 1/2 derivative slope is produced by fracture linear flow, channel/parallel-fault geometry, and horizontal-well formation linear flow. The derivative slope alone does not identify the model.
- GAS TREATED AS LIQUID - using Delta_p or Delta_p^2 instead of Delta_m(p) over a large drawdown gives a derivative that is not flat during radial flow, which is then misdiagnosed as heterogeneity. Absolute temperature (degR) and absolute pressure (psia) are mandatory in the gas groups.
- VARIABLE-RATE / UNDETECTED RATE CHANGE - superposition time must use the true rate history. A missed rate change appears as a fake derivative feature.
- CORRELATION USED OUTSIDE ITS FITTED WINDOW - applying the bilinear 44.11 form outside the C_fD window, or the linear 4.064 form after t_Dxf ~ 0.016, returns a confidently wrong x_f or k_f w_f.
- NOISE - the derivative does not create noise, it reveals it (paper's own wording: 'The derivative approach does not produce errors or noise but only reveals them'). Gauge resolution sets a hard floor: when Delta_p increments approach the gauge resolution, no value of L recovers a usable derivative.

## Numerical pitfalls

- Catastrophic cancellation at early time: Delta_p1 = p_i - p_j can be at or below gauge resolution while Delta_X1 is small, so the slope is resolution/spacing - pure quantisation noise amplified by 1/Delta_X. This is exactly the case L exists to fix, but no L fixes a Delta_p that is identically zero over the window.
- ln(Delta_t) at Delta_t = 0: the first buildup sample is often recorded at Delta_t = 0 (the shut-in point itself). It must be excluded from X, not clamped to a small epsilon.
- Loss of precision in X: superposition time is a sum of logs of similar magnitudes. Compute ln(Delta_t) - ln(t_p + Delta_t) rather than ln(Delta_t/(t_p+Delta_t)) when Delta_t << t_p to avoid underflow of the ratio, and use log1p-style forms where the argument is near 1.
- The published Table 1 X column is given to 5 decimals, so the reproduction tolerance is set by that rounding (~5e-3 psi on the largest derivative values), not by your algorithm. Do not chase a tighter tolerance against that table.
- The sinh discretisation bias means a 'derivative == n*Delta_p' assertion on synthetic power-law data will fail at the 1% level for unit slope on a 10 pt/decade grid. Either assert the sinh-corrected value or generate the synthetic data on a much finer grid.
- E1(x) needs two algorithms: the series (with the Euler constant) for x < 1 and a continued fraction for x >= 1. A single series diverges numerically for large x; a single continued fraction is inaccurate for small x. Both were needed to get the Ei oracle to 1e-8 this session.
- exp(-r_D^2/(4 t_D)) underflows to 0 for very small t_D - correct behaviour (derivative -> 0), but guard any subsequent division.
- Non-uniform real data: the L rule produces abruptly changing (j, k) pairs as i advances, which introduces small jumps in the derivative curve even on noise-free data. This is inherent to the algorithm, not a bug; it is also the reason Bourdet recommends applying the identical treatment to the type curve.
- Float accumulation: if X is built incrementally (X_i = X_{i-1} + delta) the error accumulates over tens of thousands of gauge samples. Compute each X_i directly from its own time value.
- Sign conventions: define Delta_p as a positive pressure CHANGE in both drawdown and buildup, and X as increasing. Then the derivative is positive in both cases and the plateau comparison to 70.6*qBmu/(kh) is a plain equality with no sign bookkeeping.

## Implementation notes

- Store the time function X explicitly as an array (natural log). Do not recompute ln(t) inside the derivative loop, and never pass raw t where X is expected - the L rule is defined on X.
- Point selection should scan OUTWARD from i: walk left until X_i - X_j >= L, walk right until X_k - X_i >= L. A naive linear scan is O(n) per point; on high-frequency gauge data (seconds sampling) use two monotone pointers to get O(n) total, since both j(i) and k(i) are non-decreasing in i.
- Handle the three boundary cases explicitly and separately: (1) no left point satisfies L, (2) no right point satisfies L, (3) fewer than 3 points. Bourdet's documented remedy for the right-hand case is a FIXED pseudo-right derivative between the LAST point and the first point before the last with Delta_X > L - note it is fixed, i.e. the same pair is reused for every remaining i, which makes the tail of the derivative curve a smooth artefact rather than noise.
- Expose L in natural-log cycles in the core API, and if a decade-based UI is wanted, convert once at the boundary (L_ln = ln(10) * L_decades). Put the unit in the parameter name (L_ln_cycles) - this is the defect the Table 1 test exists to catch.
- For buildup: build X from the full rate history via the superposition function, differentiate with respect to X, then PLOT against Delta_t (Bourdet's own procedure). Do not plot against Delta_t_e unless you also want the abscissa compressed; the derivative values are identical either way.
- If you only have t_p and a single rate, the shortcut is X = ln(Delta_t/(t_p+Delta_t)) or equivalently ln(Delta_t_e); both give the same derivative.
- Offer a diagnostic overlay of Delta_p_prime/Delta_p (the beta-derivative). It reads 1 for pure storage, 1/2 for linear, 1/4 for bilinear, -1/2 for spherical, and tends to 0 for radial - a single scalar that classifies the regime and is far easier to unit-test than eyeballing slopes.
- Apply the SAME L to any model/type curve you compare against the data. Bourdet is explicit that this is the only way the smoothing distortion cancels; it also makes the regression tests stable.
- For the gas lab: differentiate Delta_m(p) with respect to ln(superposition pseudotime) when pseudotime is in use. Keep pseudopressure and pseudotime tables monotone and interpolate in pressure, not in index.
- Keep an assertion that X is strictly increasing before differentiating. Duplicate timestamps (common after a gauge restart) give Delta_X = 0 and a division by zero; drop or merge duplicates upstream, do not guard inside the formula with an epsilon that silently returns a finite wrong number.
- Write the estimator so that it also returns the actually-selected (j, k, Delta_X1, Delta_X2). Every one of the tests above becomes far easier to diagnose when the selection is inspectable, and the end-effect flag falls out for free.
- The pure-wellbore-storage identity Delta_p_prime == Delta_p is the best acceptance test on REAL data: if the early-time derivative does not lie on top of Delta_p, either the derivative is wrong or the storage is not constant. Use it as a smoke test on any new dataset before trusting the late-time plateau.

## Open uncertainties

- Bourdet Eq. 9 (the multirate superposition function) came through the OCR partially garbled: 'Il(qn-qn-1>[ ... (q;-q;-1)ln( ... ~tj+~,)]+ln(~t)'. The form I give is the standard reconstruction and its single-drawdown reduction was validated numerically against the paper's own Table 1, but the exact printed index limits of the two summations should be re-checked against a clean copy of SPE-12777-PA before being encoded.
- The spherical-flow equation's radicand is rendered ambiguously by the OCR of the retrieved source as sqrt(phi*mu*c_t*k) while dimensional analysis and my re-derivation of the 2452.9 constant both require sqrt(phi*mu*c_t) with k_S^(3/2) in the denominator. I have given the derivation-consistent form. Confirm against Bourdet (2002) Section 1.2 or Moran & Finklea before shipping the spherical estimator.
- The bilinear constant 44.11 is RETRIEVED but NOT independently re-derived (unlike 4.064, 2452.9, 141.2, 0.0002637, 70.6, 162.6, 0.23395, 0.8935). Its only cross-check here is internal (44.11^2 vs the companion 1944.8). Treat it as verified-by-single-source until checked against Cinco-Ley & Samaniego (1981), SPE-10179 / SPEJ.
- The bilinear and linear flow VALIDITY WINDOWS (C_fD < ~300, t_Dxf ~ 0.1/C_fD^2, t_Dxf < 0.016) are RECALLED from Cinco-Ley & Samaniego (1981) and Gringarten et al. (1974). Neither paper was retrieved this session. Mark these thresholds UNVERIFIED - needs primary source.
- The wellbore-storage end criterion t > (200000 + 12000*S)*C/(kh/mu) is RECALLED from J. Lee, 'Well Testing' (SPE Textbook Vol. 1). Not retrieved. UNVERIFIED - needs primary source.
- The pseudo-steady-state constant 0.23395 and the field-unit Ei form with 70.6 and 948 are standard textbook results that I re-derived from unit conversions, but I did NOT retrieve Lee or Earlougher this session. The DERIVATIONS are sound and self-consistent; the attributions are from memory.
- The gas constant 1422 depends on the standard-condition convention. Escobar prints 1422.52; my derivation with p_sc = 14.7 psia and T_sc = 520 degR gives 1421.9, and with p_sc = 14.65 psia it drops to ~1418 (0.3%). Pick and document one convention in the repo; do not mix values taken from different textbooks.
- The Kazan Federal University 'Well Test Analysis' PDF reproduces Bourdet (2002) equations essentially verbatim but is a course handout, i.e. a SECONDARY source. Every constant taken from it that I could re-derive, I did. The one I could not (44.11) is flagged above.
- Agarwal (1980), SPE-9289, was confirmed only at the abstract/metadata level; the equivalent-time formula itself is quoted from Bourdet's Eq. 7, which is primary and retrieved.
- The IHS/Fekete statement that the smoothing window is typically 0.01-0.2 was retrieved as TEXT, but the equation on that page is an image I could not read, so I could not confirm that their formula is identical to Bourdet's Eq. 8. Their 'DX' range is therefore evidence about conventions, not about the formula.
- I did not retrieve any source for the exact numerical shape of the dual-porosity or fault-doubling derivative signatures; those are outside the scope of what was asked but will be needed if the lab implements heterogeneous models.

## Independent check values

| Check | Inputs | Expected | Source | Retrieved or recalled |
|---|---|---|---|---|
| PRIMARY REGRESSION TEST - reproduce the published derivative column of Bourdet et al. 1989 Table 1 (Buildup 2), L = 0, using the paper's own Delta_p and superposition-time columns. This test simultaneously validates the formula, the weighting direction, and the sign convention. | `Three consecutive rows (Delta_t [hr], Delta_p [psi], X = superposition time [natural log]): (0.00417, 0.57, -8.21072), (0.00833, 3.81, -7.51785), (0.01250, 6.55, -7.11265). Derivative is requested at the middle point.` | `5.99244 psi (published). My implementation of Eq. 8 returns 5.99238 (error -6e-5, limited by the 5-decimal rounding of the published X column). DISCRIMINATOR: the transposed (same-side) weighting returns 5.44592 - a 9% difference, far outside any rounding tolerance. Suggested unit-test tolerance: 1e-3 psi absolute against the published value.` | Bourdet, Ayoub & Pirard, SPEFE June 1989, Table 1 (SPE-12777-PA) | RETRIEVED this session (OCR full text) and RECOMPUTED this session |
| L-SMOOTHING TEST + L-UNIT DISCRIMINATOR - reproduce the L = 0.1 column of the same table at a row where the L rule actually skips a point. | `Same Table 1 dataset; derivative at Delta_t = 0.04583 hr (X = -5.81554). Left neighbour at 0.03750 has Delta_X1 = 0.20013 >= 0.1 so it is used; right neighbour at 0.05000 has Delta_X2 = 0.08674 < 0.1 so it is SKIPPED and 0.05833 (Delta_X2 = 0.24035) is used instead.` | `26.07281 psi (published). My implementation returns 26.07274 with L in NATURAL-log units. DISCRIMINATOR: interpreting L = 0.1 as 0.1 DECADES (0.230259 ln) returns 30.90125 - wrong by 18.5%. This test pins the unit convention of L.` | Bourdet, Ayoub & Pirard, SPEFE June 1989, Table 1, column 'Pressure Derivative L = 0.1' | RETRIEVED this session and RECOMPUTED this session |
| SUPERPOSITION-TIME CONSISTENCY CHECK - confirm that the paper's superposition-time column is the natural-log Horner-type function. | `The Table 1 pairs (Delta_t, X) across the full range 0.00417 to 12.25 hr.` | `X = ln( Delta_t / (t_p + Delta_t) ) with a single constant t_p = 15.330 hr reproduces every listed value to within +/-0.0002 in X. This also demonstrates that ln(Delta_t_e) and ln(Delta_t/(t_p+Delta_t)) differ only by the additive constant ln(t_p) and yield identical derivatives.` | Bourdet, Ayoub & Pirard, SPEFE June 1989, Table 1 | RETRIEVED (the table) + DERIVED/COMPUTED this session (the t_p fit) |
| ANALYTIC ORACLE 1 - exact log-derivative of the line-source solution, the cleanest closed-form target for a derivative implementation. | `p_D(t_D) = 0.5*E1(r_D^2/(4*t_D)) with r_D = 1, sampled at 10 points per decade over t_D = 0.1 to 1e7.` | `dp_D/dln(t_D) = 0.5*exp(-r_D^2/(4*t_D)) EXACTLY. Measured this session with L = 0: t_D = 3.16 -> exact 0.4619937 vs estimator 0.4616960 (-3.0e-4); t_D = 31.6 -> 0.4960627 vs 0.4960283 (-3.4e-5); t_D = 316 -> 0.4996049 vs 0.4996014 (-3.5e-6); t_D = 3.16e4 -> agreement to 3.5e-8. Error falls as the curvature of p_D in ln(t_D) dies out.` | Derived analytically this session from p_D = 0.5*E1(u), u = r_D^2/(4 t_D): dp_D/dln t_D = 0.5*exp(-u). Underlying solution: Theis (1935) / standard line-source. | DERIVED AND COMPUTED this session (the Ei solution itself is recalled/secondary) |
| ANALYTIC ORACLE 2 - exactness on the semilog approximation. This is the strongest structural test of the estimator. | `p_D = 0.5*(ln(t_D) + 0.80907) sampled on ANY grid, uniform or not.` | `The Bourdet estimator must return 0.500000000000 to machine precision for EVERY interior point and for EVERY value of L (verified this session at t_D = 10, 1e3, 1e5 with L = 0 and L = 0.4, all giving 0.500000000000). Any deviation beyond ~1e-12 means the formula or the point selection is wrong. This is the test that proves the radial plateau is recovered without bias.` | Bourdet et al. 1989 Eq. 2 / Eq. 6 ((t_D/C_D)*p_D' = 0.5) | Equation RETRIEVED this session; numerical verification COMPUTED this session |
| ANALYTIC ORACLE 3 - power-law regimes and the exact discretisation bias. | `Delta_p = 3.7 * t^n for n = 1, 1/2, 1/4, -1/2, on a 10 pt/decade log grid (h = ln(10)/10 = 0.230259), L = 0.` | `Estimator/Delta_p ratio = n * sinh(n*h)/(n*h). Measured this session: n = 1 -> 1.008860 (theory sinh(0.230259)/0.230259 = 1.008860); n = 0.5 -> 0.501105 (theory 0.5*1.002211); n = 0.25 -> 0.250138 (theory 0.25*1.000552); n = -0.5 -> -0.501105. All agree to 6 significant figures. A test that asserts the ratio is exactly n will FAIL and should assert the sinh-corrected value instead, or use a tolerance of at least 1% for the unit-slope case.` | Derived analytically and verified numerically this session; the 1, 1/2, 1/4 regime exponents are corroborated by the beta-derivative table in Zonoozi/Blasingame SPE 103204 (retrieved). | DERIVED AND COMPUTED this session |
| CONSTANT-CONSISTENCY CHECKS - closed-form relations among the field-unit constants that any implementation should assert once. | `The published constants 0.0002637, 141.2, 162.6, 70.6, 948, 3.79e5, 0.80907, 3.2275, 2452.9, 4.064, 0.23395, 0.8935, 1422.52, 1637.74.` | `141.2055*ln(10)/2 = 162.5688 ; 141.2055/2 = 70.6028 ; 162.5688/ln(10) = 70.6028 ; 1/(4*0.0002637) = 948.047 ; 3.79e5*0.0002637 = 99.94 (t_D = 100) ; ln(4/1.7810724) = 0.8090692 ; -log10(0.0002637) - 0.80907/ln(10) = 3.2273 ; 70.6028/sqrt(pi*0.0002637) = 2453.07 vs published 2452.9 ; 5.614583/24 = 0.2339410 ; 5.614583/(2*pi) = 0.893544 ; 1422.52*ln(10)/2 = 1637.75 vs published 1637.74 ; log10(1688) = 3.2274 (matches the oil-case 3.2275).` | Constants from Bourdet et al. 1989, Bourdet 2002 (via Kazan Federal University notes), Escobar 2017; relations derived this session | Constants RETRIEVED; relations DERIVED AND COMPUTED this session |
| Ei log-approximation error table (for asserting the t_D/r_D^2 > 25 criterion). | `x = r_D^2/(4*t_D) = 0.1, 0.05, 0.02, 0.01, 0.005, 0.0025` | `E1(x) = 1.82292396, 2.46789849, 3.35470778, 4.03792958, 4.72609546, 5.41674732; -ln(gamma*x) = 1.72536943, 2.41851661, 3.33480734, 4.02795452, 4.72110170, 5.41424888; relative error = -5.35%, -2.00%, -0.593%, -0.247%, -0.106%, -0.046%. The corresponding t_D/r_D^2 = 2.5, 5, 12.5, 25, 50, 100.` | Computed this session with a series/continued-fraction E1 implementation; the threshold statement itself corroborated by a retrieved search result | COMPUTED this session |
| END-EFFECT REGRESSION - deliberately reproduce the distortion so it is a known, tested behaviour rather than a surprise. | `Truncate the Table 1 dataset at Delta_t = 0.25 hr and request the L = 0.1 derivative at the second-to-last point (Delta_t = 0.22917).` | `With the truncated data my implementation returns 144.25 where the full-dataset published value is 146.17935 - a 1.3% distortion caused purely by the missing right-hand points. An implementation must either flag these points or apply Bourdet's fixed 'pseudo right' derivative; silently returning the distorted value is the defect.` | Bourdet et al. 1989 'End Effect' paragraph + my truncation experiment this session | Behaviour described in RETRIEVED text; the specific number COMPUTED this session |

## Adversarial review

### Corrections

**Gas IARF semilog equation — constant 1.422e6 with q_sc in Mscf/D** — severity critical, confidence high

- Claimed: m(p_i) - m(p_wf) = (1.422e6 * q_sc * T/(k*h)) * [1.1513*log10(k*t/(1688*phi*(mu*c_t)_i*r_w^2)) + s' + D*q_sc], with q_sc declared in Mscf/D; and on the next line 'slope m = 1637.74 q_sc T/(k h)'.
- Correct: The correct constant for q_sc in Mscf/D is 1422.52, not 1.422e6. The consistent form: m(p_i)-m(p_wf) = (1422.52*q_sc*T/(k*h))*[1.1513*log10(...) + s' + D*q_sc], so that slope = 1422.52*1.1513 = 1637.7 q_sc T/(k h). The value 1.422e6 is valid only if q_sc is in MMscf/D. The card transcribed Escobar Eq. 25 verbatim without catching this, even though its own cross-check (1422.52*ln10/2 = 1637.75) should have exposed it immediately — a 1000x internal inconsistency inside a single equation block.
- Evidence: The Escobar 2017 full text was re-extracted this session from cdn.intechopen.com/pdfs/54370.pdf (decoding the FlateDecode stream locally). Eq. (20) prints m(P)_D = kh[m(Pi)-m(P)]/(1422.52 q T) and Eq. (29) k = 1637.74 qT/(mh), but Eq. (25) prints 1.422x10^6 — the source itself is inconsistent. Escobar's worked example settles the matter: q=6184 MSCF/D, T=710 R, h=41 ft, simulated k=44 md, observed semilog slope m=3,995,147.42 psi^2/cp per cycle. Eq. 25 with 1.422e6 predicts a slope of 3.9846e9 — the ratio to observed = 997.3 (i.e. 1000x). With 1422.52 it predicts 3.986e6, matching to 0.23%. And k = 1637.74*6184*710/(3995147.42*41) = 43.90 md vs simulated 44 md. Independent derivation from SI: 2*141.2055*1000*B_g = 1421.9 (Mscf/D), never 1.42e6.

**Beta-derivative (Delta_p_prime/Delta_p) for spherical flow** — severity high, confidence high

- Claimed: The power-law table: 'n = -1/2 spherical flow ratio -0.5 (derivative descends)', and implementation_note: 'Offer a diagnostic overlay of Delta_p_prime/Delta_p ... reads 1 for pure storage, 1/2 for linear, 1/4 for bilinear, -1/2 for spherical, and tends to 0 for radial - a single scalar that classifies the regime'.
- Correct: beta = Delta_p_prime/Delta_p for spherical flow is POSITIVE and tends to 0; it is never -0.5. The card's own spherical equation is already correct: Delta_p = a - b*t^(-1/2) with a = 70.6 qBmu/(k_S r_S), b = 2452.9(...). Hence Delta_p_prime = t*dDelta_p/dt = +(b/2)*t^(-1/2) > 0, while Delta_p -> a (constant). So beta -> 0+. The value -1/2 is the log-log SLOPE of the derivative curve, not beta. Practical consequence: beta does NOT separate spherical from radial (both -> 0), so the claim 'a single scalar that classifies the regime' is wrong; the correct discriminator is d ln(Delta_p_prime)/d ln t = -1/2 (spherical) vs 0 (radial). The card contradicts itself: the spherical section already writes the '+' sign correctly.
- Evidence: Computed this session from the card's own spherical equation: for Delta_p = 100 - 10 t^(-1/2), beta = 0.0556, 0.0163, 0.0051, 0.0016 at t = 1, 10, 100, 1000 — positive and decreasing. The value -0.5 appears only if Delta_p itself is proportional to t^(-1/2), which would mean the pressure drop decreases with time (not physical for a drawdown). The card's Oracle 3 (Delta_p = 3.7 t^n, n = -1/2 -> -0.501105) is correct as a purely mathematical test of the estimator, but the label 'spherical flow' on that row is wrong.

**independent_checks #1 — tolerance for the Table 1 regression** — severity medium, confidence high

- Claimed: 'Suggested unit-test tolerance: 1e-3 psi absolute against the published value' and 'the full 26-row block I checked agrees within 5.3e-3 psi worst case'.
- Correct: A 1e-3 psi absolute tolerance FAILS. I reproduced the whole of Table 1 (102 interior points for L=0): 73 of 102 rows exceed 1e-3 psi, worst case 0.3204 psi at Delta_t = 0.33333 hr (published 193.82046 vs 194.14089). Even within the first 26 rows that the card claims are <=5.3e-3, the actual worst case is 0.2108 psi (Delta_t = 0.25, published 155.45732 vs 155.24653). The correct tolerance is RELATIVE: max rel 1.65e-3 (L=0), 1.93e-3 (L=0.1), p95 2.5e-4, median 3.8e-5. Recommendation: assert rtol = 3e-3, or atol 0.35 psi if an absolute tolerance is still wanted. The cause is the 5-decimal rounding of the X column for large derivative values — exactly the pitfall the card itself names but did not apply when it set the tolerance.
- Evidence: The complete Table 1 (102 rows: Delta_t, Delta_p, derivative L=0, derivative L=0.1, superposition time) was extracted this session from the OCR text of SPE-12777-PA and re-processed with my own implementation of Eq. 8. The statistics above were computed directly from that reproduction.

**independent_checks #5 (ANALYTIC ORACLE 2) — the claim 'strongest structural test of the estimator'** — severity medium, confidence high

- Claimed: 'ANALYTIC ORACLE 2 - exactness on the semilog approximation. This is the strongest structural test of the estimator... Any deviation beyond ~1e-12 means the formula or the point selection is wrong.'
- Correct: This oracle CANNOT catch the transposed weighting, which is the number-one failure mode the card itself states. The proof is structural: the transposed form [(Delta_p1/Delta_X1)*Delta_X1 + (Delta_p2/Delta_X2)*Delta_X2]/(Delta_X1+Delta_X2) simplifies IDENTICALLY to (Delta_p1+Delta_p2)/(Delta_X1+Delta_X2) = (p_k - p_j)/(X_k - X_j), i.e. the two-point secant through the outer points — for ANY spacing, not only on a uniform grid. The secant is also exact for affine data, so it returns exactly the same 0.500000000000. The card's sentence is true in one direction, but its converse (which is what is used as the test) is not: passing this oracle does not prove the weighting is correct. The card's characterisation in failure_modes ('it silently degrades to a spacing-biased average') is also inaccurate — it is exactly the plain secant. Only the Table 1 regression, or an explicit assertion 'estimator != secant on a non-uniform grid', is discriminative.
- Evidence: Verified algebraically and numerically this session: on 4 random non-uniform triplets, transposed == secant to 12 decimals every time. On the Table 1 row Delta_t=0.00833: correct 5.99238, transposed 5.44592, secant 5.44592 (difference 1e-15). On affine data on the non-uniform grid X=[0,0.37,1.91], both variants return 0.5 to machine precision.

**independent_checks #9 — the end-effect value 144.25** — severity medium, confidence high

- Claimed: 'With the truncated data my implementation returns 144.25 where the full-dataset published value is 146.17935 - a 1.3% distortion.'
- Correct: 144.25 is not reproducible and is not an oracle — it is an artefact of an unspecified fallback rule. Under the pure L rule (Bourdet's '>L'), the point Delta_t=0.22917 in data truncated at 0.25 has NO valid right point (Delta_X to 0.25 = 0.08567 < 0.1), so the correct result is undefined/flagged. The pseudo-right remedy that the card itself quotes (fixed pair: the last point 0.25 with 0.21250, Delta_X = 0.16011) gives 141.36, not 144.25. The one-sided left-slope fallback gives 136.60. None of them equals 144.25. Turn this check into two assertions: (a) the point is FLAGGED as an end effect, (b) if pseudo-right is active, its value is 141.36 — the distortion relative to the published full-data 146.17935 is then 3.3%, not 1.3%.
- Evidence: Computed this session from the extracted Table 1, using the pseudo-right definition verbatim from the paper, which I confirmed myself: 'One solution consists of using a "pseudo right" derivative in Eq. 8, which becomes fixed. It is defined between the last point and the first point before the last such that [Delta_X] > L.'

**independent_checks #3 — the superposition-time tolerance** — severity low, confidence high

- Claimed: 'reproduces every listed value to within +/-0.0002 in X across the full range Delta_t = 0.00417 to 12.25 hr', tolerance '+/-0.0005 in X'.
- Correct: With t_p = 15.33 hr (the value PRINTED in Table 1, not a fitted one), max |Delta_X| = 7.97e-4 — exceeding both of the card's figures (0.0002 and the 0.0005 tolerance). The best-fit t_p = 15.333 hr still gives 6.01e-4. The correct tolerance is +/-1e-3 in X. Two notes that actually strengthen this check: t_p need not be fitted at all, because Table 1 prints 'Flow History tp, hours 15.33' directly; and the table's actual range is 0.00417 to 28.50 hr, not 12.25 hr.
- Evidence: Computed this session over the 102 rows of the Table 1 Superposition Time column against X = ln(Delta_t/(t_p+Delta_t)); t_p scanned from 15.29 to 15.37 in steps of 0.001.

**The bilinear flow constant 44.11 and its 'cannot be re-derived' status** — severity low, confidence medium

- Claimed: 'Constant printed as 44.11 in the retrieved source'; 'The bilinear constant 44.11 is RETRIEVED but NOT independently re-derived... Internal consistency only: 44.11^2 = 1945.7 vs the printed companion constant 1944.8 (0.05%)'.
- Correct: The constant CAN be re-derived, and the result is 44.100, not 44.11. From the Cinco-Ley bilinear solution p_wD = [pi/(Gamma(5/4)*sqrt(2))]*t_Dxf^(1/4)/sqrt(C_fD) = 2.450833*t_Dxf^(1/4)/sqrt(C_fD), then substituting Delta_p = 141.2055 qBmu/(kh)*p_wD, t_Dxf = 0.0002637 kt/(phi mu c_t x_f^2), C_fD = k_f w_f/(k x_f): the constant = 141.2055 * 2.450833 * (0.0002636786)^(1/4) = 44.0995, with x_f cancelling exactly as it should for bilinear flow. And 44.0995^2 = 1944.77, matching the printed companion 1944.8 to 4 digits — whereas 44.11^2 = 1945.69 does not. So '44.11' is almost certainly an OCR misreading of 44.1; use 44.10 in the repo.
- Evidence: Derivation plus numerics this session (Gamma(1.25) = 0.9064025, pi/(Gamma(1.25)*sqrt2) = 2.4508334). Cross-consistent with the companion constant 1944.8 that the card itself quotes. The Kazan PDF has no text layer, so the transcription '44.11' cannot be re-confirmed from its source.

**C_D field-unit constant — the 'exact' value** — severity low, confidence high

- Claimed: '0.8935 (exact 0.893544)' and '0.8935 = 5.614583/(2*pi) = 0.893544' (stated twice).
- Correct: 5.614583/(2*pi) = 0.8935886, not 0.893544 — a digit slip in the 5th digit. The form of the equation itself is correct. The card's t_D/C_D derivation is also correct once this is fixed: 0.0002636786/0.8935886 = 2.95078e-4.
- Evidence: Computed this session. The form C_D = 0.8935 C/(phi h c_t r_w^2) was confirmed verbatim from the text of Escobar 2017 Eq. (22) that I extracted. The value t_D/C_D = 0.000295 was confirmed verbatim from the OCR of Bourdet 1989, match parameters section: 'C={0.000295(kh/mu)[Delta_t/(tD/CD)]M}= 9.3 X 10-3 bbl/psi'.

**Re-derivation of the semilog offset 3.2275** — severity low, confidence high

- Claimed: 're-derived this session as -log10(0.0002637) - 0.80907/ln(10) = 3.5787 - 0.35137 = 3.2273'.
- Correct: -log10(2.636786e-4) = 3.578925 (not 3.5787), so 3.578925 - 0.351373 = 3.227551. This matches the published 3.2275 to 5 digits, rather than missing it by 2e-4 as the card reports. The correction actually STRENGTHENS the card, but the 3.2273 printed at present will be read by a reviewer as a derivation that failed to match.
- Evidence: Computed this session; cross-checks log10(1688) = 3.227372 and 1/(0.0002636786*e^0.8090787) = 1688.68. Escobar Eq. (30) as I extracted it prints '-3.227+0.8686 s', which is consistent.

**Provenance of the gas constant 1422.52** — severity low, confidence medium

- Claimed: 'my derivation with p_sc = 14.7 psia and T_sc = 520 degR gives 1421.9, and with p_sc = 14.65 psia it drops to ~1418 (0.3%). Pick and document one convention in the repo.'
- Correct: A convention that really does reproduce 1422.52 exists and should be documented rather than left as 'pick one': p_sc = 14.696 psia (1 atm), T_sc = 519.67 degR (60 degF) gives 2*141.2055*1000*(14.696/519.67)/5.614583 = 1422.44, matching the published 1422.52 to 0.006%. Compare 14.7/520 -> 1421.93 and 14.65/519.67 -> 1417.99. So 1422.52 is not an unresolvable ambiguity; it is the atm/60F convention.
- Evidence: Computed this session from C141 = 141.20546, which was already verified from SI (2*pi*md*ft*psi/(res-bbl-per-day * cp)).

**Equivalence of the PSS onset t_DA > 0.1 with t > 948 phi mu c_t r_e^2/k** — severity low, confidence high

- Claimed: 'Onset conventionally t_DA > 0.1 for a circle (equivalently t > 948*phi*mu*c_t*r_e^2/k)'.
- Correct: The two criteria are not equivalent; they differ by a factor pi/4 = 1.257. The 948 criterion corresponds to t_D = 0.25*r_eD^2, and t_DA = t_D*r_w^2/(pi r_e^2) = 0.25/pi = 0.0796, not 0.1. t_DA = 0.1 corresponds to t > 1192 phi mu c_t r_e^2/k. Pick one and delete the word 'equivalently'.
- Evidence: Algebra plus numerics this session using the t_D constant 0.0002636786 already verified from SI; 948.12 = 1/(4*0.0002636786).

**Vertical separation of Delta_p and Delta_p_prime on log-log** — severity low, confidence high

- Claimed: 'separated vertically by the constant factor n (i.e. log10(n) cycles)' in the power-law table, which in the following rows lists n = -1/2 and n = 0.
- Correct: log10(n) is undefined for n <= 0, yet the same table lists n = -1/2 and n = 0. State it as |log10(|n|)| cycles and restrict it to n > 0, or delete the phrase.
- Evidence: Internal inspection of the card; it interacts directly with the spherical beta correction above (that n = -1/2 row is also the physically problematic one).

### Left unverified

- The Kazan Federal University 'Well Test Analysis' PDF (kpfu.ru/portal/docs/F1634229975/metodichka.well.test_Zaschita.pdf) has NO extractable text layer — I downloaded it and decoded its streams, and the result was empty (1 byte). That means EVERY transcription the card takes from it cannot be re-confirmed by me from its source: 4.06, 44.11, 1944.8, 2452.9, the spherical 70.6, 162.6, Delta_p = qB Delta_t/(24C), C = qB/(24 m_WBS), and the inversion forms for x_f and k_f w_f. I re-derived the physics myself from first principles (4.0641, 44.0995, 2453.07 — all matching), so what is unverified is the TRANSCRIPTION, not the physics. Mark this source 'secondary, not re-readable'.
- The radicand of the spherical flow equation. The card is honest that the OCR is ambiguous and chooses sqrt(phi*mu*c_t) with k_S^(3/2) on the basis of a re-derivation. I confirmed independently that the derivation is correct (70.6028/sqrt(pi*0.0002636786) = 2453.065, from the spherical-source asymptote Delta_p = (q mu/(4 pi k r_s)) erfc(r_s/(2 sqrt(eta t)))), but the primary text of Bourdet 2002 Section 1.2 / Moran & Finklea was still NOT retrieved. Status: derivation-verified, source-unverified.
- The linear flow validity window t_Dxf < 0.016 (Gringarten, Ramey & Raghavan 1974). I searched for it this session and found no confirmation of the figure 0.016 from any source; one search result instead states that pseudoradial flow begins at t_Dxf between 1 and 3, which does not determine the end of linear flow. STILL UNVERIFIED - needs primary source.
- The bilinear flow validity window: C_fD < ~300 and t_Dxf ~ 0.1/C_fD^2 for C_fD >= 3 (Cinco-Ley & Samaniego 1981, SPE-10179). Not retrieved this session; the search only confirmed qualitatively that Delta_p vs t^(1/4) is Cartesian through the origin with slope m_bf. STILL UNVERIFIED - needs primary source.
- The wellbore storage end criterion t > (200000 + 12000*S)*C/(kh/mu). Not retrieved; I cannot derive it from first principles. STILL UNVERIFIED - needs primary source (J. Lee, Well Testing, SPE Textbook Vol. 1).
- Bourdet Eq. 9 (superposition time) index limits. I confirmed MYSELF that the OCR really is corrupted — the extracted text reads exactly 'Il(qn-qn-1>[ (q;-q;-1)ln( :~: ~tj+~,)]+ln(~t)'. The card's reconstruction passes the single-drawdown reduction test against Table 1 (I reproduced it: max |Delta_X| = 8e-4 with t_p = 15.33), but the index limits of the two summations for the multirate case n > 2 remain unverified against a clean copy.
- Whether the L selection rule uses a strict '>' or '>='. The paper prints 'selects Points 1 and 2 as being the first ones such that Delta_X_{1,2} > L'. I used '>' and the Table 1 reproduction succeeded, but this dataset contains no exact tie, so it is not discriminative. The tie-break remains untested.
- The provenance of 1422.52 in Escobar. Escobar prints the figure without stating p_sc/T_sc. My reconstruction (14.696 psia / 519.67 R -> 1422.44) matches to 0.006% but is an inference, not a quotation.
- The attribution (not the arithmetic) of the field-unit Ei form with 70.6/948, the t_D > 100 / 3.79e5 limit, the t_D/r_D^2 > 25 criterion, and the PSS slope 0.23395 to Lee/Earlougher/Theis. I re-verified every one of those NUMBERS from SI conversions this session (948.12, 99.93, the E1 error table matching exactly to 8 decimals, 0.2339410 via TWO independent routes), but none of the Lee/Earlougher/Theis texts was retrieved.
- The IHS/Fekete claim that the smoothing window 0.01-0.2 is expressed in decades. The card already notes that their formula is an unreadable image; I did not retry it. This is evidence about conventions, not about the formula, and must not be used to support or to refute the units of Bourdet's L.
- Derivative signatures for dual-porosity and fault doubling: no source, no numbers. The card honestly states that this is out of scope, but the gas lab will most likely need it.

### Missing before implementation

- The complete Table 1 dataset as a fixture. The card quotes only 3 rows; I have extracted all 102 rows (Elapsed Time, Pressure Change, Derivative L=0.0, Derivative L=0.1, Superposition Time) from the OCR of SPE-12777-PA. This must be committed as a CSV fixture in the repo, because without the full Delta_p column none of independent_check #1/#2/#9 can be re-run by a reviewer. The run metadata is printed in the table too: t_p = 15.33 hr, q = 174 STB/D, B = 1.06.
- An explicit contract for the return value at end-effect points. Three different behaviours give three different numbers (undefined/flagged, pseudo-right = 141.36, left-slope-only = 136.60). The API must pick one, return a flag, and return the selected (j, k) — the card already recommends the last of these; keep it.
- A decision on the standard-condition convention for gas (14.696 psia/519.67 R -> 1422.44 vs 14.7/520 -> 1421.93), written once as a single module constant rather than taken equation by equation from different textbooks.
- The tie-break rule '>' vs '>=' in the L selection, plus the behaviour for duplicate timestamps (Delta_X = 0) and for Delta_t = 0 in the first buildup sample.
- A primary source for the four validity windows that are still recalled (t_Dxf < 0.016, C_fD < 300, t_Dxf ~ 0.1/C_fD^2, the WBS end criterion). Until there is one, do not encode them as guards that raise; encode them as warnings marked UNVERIFIED.
- A clean copy of SPE-12777-PA Eq. 9 for the multirate case n > 2 before the superposition function is encoded for a general rate history. The single-buildup reduction is already safe; multirate is not.
- A definition of a slope diagnostic to replace beta for separating spherical from radial, since beta fails (both -> 0). What is needed: d ln(Delta_p_prime)/d ln t, with the target table 1, 1/2, 1/4, -1/2, 0.
- A reference type-curve model (storage+skin p_D vs t_D/C_D) if the lab wants to follow the Bourdet recommendation I confirmed verbatim: 'differentiate both data and theoretical curves with the same smoothing coefficient, L'. The card recommends it but does not supply the type-curve solution.
- For the 'Gas Reservoir Performance Lab' specifically: there is not a single gas material-balance equation, z-factor correlation, or pseudopressure quadrature scheme in this card. m(p) = 2*integral p/(mu Z) dp is mentioned but without an integration rule, without mu(p)/Z(p) tables, and without p_ref. The gas section cannot be implemented as it stands.

### Recommended independent test oracles

**table1_full_column_regression**

- Inputs: `All 102 rows of Table 1 SPE-12777-PA: X = the Superposition Time column, p = the Pressure Change column. Compute the derivative for L = 0 and L = 0.1 (ln units) at every interior point that has valid neighbours.`
- Expected: `Matches the 'Pressure Derivative L=0.0' column (102 points) and the 'L=0.1' column (96 points) at rtol = 3e-3. Statistics measured this session: max rel 1.65e-3 (L=0) and 1.93e-3 (L=0.1), p95 2.5e-4, median 3.8e-5, max abs 0.3204 psi at Delta_t = 0.33333. DO NOT use atol 1e-3 psi — it fails on 73/102 rows.`
- Why independent: Those columns are the output of Bourdet's own implementation as printed in 1989, produced with no knowledge whatsoever of our code. It exercises the formula, the weighting direction, the L selection rule, the units of L and the sign convention all at once in a single regression — the only check in the card that binds all five.

**weighting_is_not_the_secant**

- Inputs: `Any non-uniform triplet; use the Table 1 row Delta_t = 0.00833 with neighbours 0.00417 and 0.01250 (Delta_X1 = 0.69287, Delta_X2 = 0.40520).`
- Expected: `Estimator = 5.99238 (published 5.99244). SEPARATELY assert that estimator != (p_k - p_j)/(X_k - X_j) = 5.44592, a 10% difference.`
- Why independent: It closes the hole in ANALYTIC ORACLE 2. I proved that the transposed weighting variant is ALGEBRAICALLY IDENTICAL to the two-point secant for any spacing, and therefore also exact for affine data — so the 0.5 plateau test cannot distinguish them. The 'not the secant' assertion on a non-uniform grid is the only purely structural test (needing no published data) that is discriminative.

**L_unit_discriminator_full_column**

- Inputs: `The full Table 1, run L = 0.1 twice: once with L interpreted as ln-cycles, once as decades (0.230259 ln).`
- Expected: `ln interpretation: mean |err| 0.011 psi against the published column. Decade interpretation: mean |err| 5.28 psi, max 21.66 psi at Delta_t = 3.5. On the single row Delta_t = 0.04583: published 26.07281, ln 26.07274, decade 30.90125.`
- Why independent: Besides the numerical reproduction, there is now direct primary textual support that the card did not have. I extracted Eq. 8 verbatim: 'X =time function (ln [Delta t] for drawdown, modified Horner, or superposition times expressed in natural logarithm for buildups)', and the L rule: 'The minimum distance considered between the abscissa of the points and that of Point i, L, is expressed in terms of the time function.' So the units of L are tied to the natural-log axis by definition, not merely empirically.

**ei_log_derivative_closed_form**

- Inputs: `p_D(t_D) = 0.5*E1(r_D^2/(4 t_D)), r_D = 1, 10 points/decade, t_D = 0.1 to 1e7.`
- Expected: `dp_D/d ln t_D = 0.5*exp(-r_D^2/(4 t_D)) exactly. I accept the card's tolerance (3e-4 at t_D ~ 3, tightening to 1e-6 for t_D > 300). I also reproduce the card's log-approximation error table exactly: E1 = 1.82292396, 2.46789849, 3.35470778, 4.03792958, 4.72609546, 5.41674732 at x = 0.1...0.0025, with relative error -5.35%, -2.00%, -0.593%, -0.247%, -0.106%, -0.046%.`
- Why independent: The closed-form target is derived analytically from the Theis solution (dp_D/dln t_D = 0.5 e^-u because du/dt_D = -u/t_D) and does not pass through the discrete estimator at all. It exercises the transition behaviour with nonzero curvature — the part that neither the plateau oracle nor the power-law oracle touches at all.

**sinh_discretisation_bias**

- Inputs: `Delta_p = A*exp(n*X) on a uniform ln grid of spacing h; test n = 1, 1/2, 1/4, -1/2 at h = ln(10)/10 and at the spacing selected by L=0.5 (3h = 0.690776).`
- Expected: `estimator/(n*Delta_p) = sinh(n h)/(n h) exactly. Verified this session: 1.0088600 (n=1, h), 1.0022106 (n=1/2), 1.0005524 (n=1/4), 1.0022106 (n=-1/2, an even function); at 3h: 1.0814476 (n=1), 1.0200010 (n=1/2). The bias is exactly zero for n = 0.`
- Why independent: A closed-form identity that I re-derived from the definition of the estimator rather than from running it. It also sets the correct tolerance for every power-law regime test, so that the naive assertion 'ratio == n' is not used — that would fail at the 0.9% level for unit slope on 10 points/decade.

**escobar_gas_worked_example**

- Inputs: `q_sc = 6184 Mscf/D, T = 710 degR, h = 41 ft, phi = 0.1004, mu_g = 0.0992 cp, c_t = 0.0002561 1/psi, r_w = 0.4271 ft; measured semilog slope m = 3,995,147.42 psi^2/cp per log10 cycle; m(P)_1hr = 342,125,555.5; m(P_i) = 340,920,304.2; simulated k = 44 md.`
- Expected: `k = 1637.74*q*T/(m*h) = 43.90 md vs simulated k 44 md (the paper reports 43.45). The derivative plateau must equal m/ln(10) = 1,735,092 psi^2/cp = 711.26*q*T/(k*h). KEY ASSERTION: the slope predicted by the semilog form must be 3.99e6, not 3.98e9.`
- Why independent: A published worked example with a k answer known from a simulator, so it locks the whole chain of gas constants against a single external number. It is also the test that CATCHES the 1.422e6 vs 1422.52 bug — I ran it and the ratio came out at 997.3.

**two_route_constant_identity**

- Inputs: `Derive each field-unit constant twice, along routes that do not borrow from each other, and compare.`
- Expected: `0.2339410 via 5.614583/24 MUST equal 141.20546*2*pi*0.0002636786 = 0.2339410 (the volumetric route vs the p_D' = 2 pi t_DA route — the card uses only the first). 70.6028 = 141.2055/2 = 162.5688/ln(10). 948.12 = 1/(4*0.0002636786). 3.227551 = -log10(0.0002636786) - 0.8090787/ln(10) = log10(1688.68). 0.00029508 = 0.0002636786/0.8935886. 2453.07 = 70.6028/sqrt(pi*0.0002636786). 4.064095 = (1/(2 sqrt(pi))) * (res-bbl/D per ft^2) * sqrt(cp*hr/(md*psi^-1)) in psi. 44.0995 = 141.2055*2.4508334*0.0002636786^0.25, and its square 1944.77 = the companion constant 1944.8.`
- Why independent: Each constant is bracketed from two directions that do not borrow from each other: one from raw SI unit conversion, one from the algebraic relations among the constants. Agreement between two unrelated routes is evidence; repeating a single route is circular. The second route for 0.23395 and the whole 44.10 derivation are both new — the card does not have them.

**wellbore_storage_coincidence_identity**

- Inputs: `Synthetic early-time data Delta_p = q*B*Delta_t/(24*C) with constant C, plus any real gauge data in a pure storage regime.`
- Expected: `Delta_p_prime == Delta_p point by point (not merely parallel), both on a unit slope. On a 10 points/decade grid the estimator will be 0.886% high because of the sinh bias — assert against the sinh-corrected value, not against exact equality.`
- Why independent: This identity involves no field-unit constant at all and holds in any units; it exercises the time-function + weighting + plotting chain in a case where the correct answer is known without any external reference. It is also the best acceptance test on new field data before the late-time plateau is trusted.

**corrected_regime_slope_table**

- Inputs: `Synthetic data per regime: storage Delta_p = a*t; linear a*sqrt(t); bilinear a*t^0.25; spherical a - b/sqrt(t) with a, b > 0; radial m*ln(t) + c; PSS m_star*t + b with b > 0.`
- Expected: `Assert on d ln(Delta_p_prime)/d ln t = 1, 1/2, 1/4, -1/2, 0, 1. Assert SEPARATELY on beta = Delta_p_prime/Delta_p = 1, 1/2, 1/4, POSITIVE-tending-to-0, tending-to-0, and < 1 varying for PSS. Explicitly assert that the spherical beta is POSITIVE — this is the regression test against the -1/2 error in the card.`
- Why independent: It separates two quantities the card conflates. The slope column is backed by an independent second source (the beta-derivative table of Zonoozi/Blasingame SPE 103204 for 1, 1/2, 1/4), while the beta column is derived analytically from each functional form — so the two columns have different justification routes, and the disagreement between them is exactly what exposed the spherical bug.

**agarwal_buildup_correction_factor**

- Inputs: `A synthetic buildup with a known radial drawdown; differentiate once with respect to ln(Delta_t) and once with respect to ln(Delta_t_e).`
- Expected: `Ratio naive/true = t_p/(t_p + Delta_t) exactly: 0.9091 at Delta_t = 0.1 t_p, 0.5000 at Delta_t = t_p, 0.09091 at Delta_t = 10 t_p. And the derivative with respect to ln(Delta_t_e) must be IDENTICAL bit for bit to the derivative with respect to ln(Delta_t/(t_p+Delta_t)), because the two differ by the additive constant ln(t_p).`
- Why independent: The correction factor is a calculus consequence of Eq. 7, which I confirmed verbatim from the primary text: 'dp/{d ln[tpAtl(tp +At)]} =At[(tp +At)/tp](dp/dt)'. The additive-constant invariance part is a structural identity that does not depend on the reservoir model at all, so it catches a mismatched axis without needing field data.

## Sources

| Citation | Access level | Supports |
|---|---|---|
| Bourdet, D.P., Ayoub, J.A., and Pirard, Y.M.: 'Use of Pressure Derivative in Well-Test Interpretation', SPE Formation Evaluation, June 1989, pp. 293-302 (SPE-12777-PA). Flopetrol-Johnston Schlumberger. | full-text retrieved | PRIMARY. Eq. 8 (the three-point weighted derivative, verbatim, confirming the opposite-spacing weighting); the L point-selection rule verbatim; typical L values (0 to 0.5, working value 0.1); the End Effect and its pseudo-right remedy; Eq. 7 (Agarwal equivalent-time derivative, verbatim); Eq. 9 (superposition time, partially OCR-garbled); Eqs. 1-6 (p_D = t_D/C_D storage, p_D semilog form with 0.80907, (t_D/C_D)p_D' = 0.5); the 141.2 q B mu group; nomenclature with units. Table 1 is the regression dataset used in independent_checks 1-3 and 9. |
| Kazan Federal University, 'WELL TEST ANALYSIS' course notes (methodichka), reproducing the equation set of Bourdet, D.: 'Well Test Analysis: The Use of Advanced Interpretation Models', Handbook of Petroleum Exploration and Production 3, Elsevier, 2002. | secondary source | Field-unit (a) and SI (b) forms of: radial semilog (162.6, 3.23, 0.87 S), wellbore storage (Delta_p = qB Delta_t/(24C), C = qB/(24 m_WBS)), linear flow (4.06 and the x_f inversion), bilinear flow (44.11 and the k_f w_f inversion, 1944.8), spherical flow (70.6 and 2452.9), and the definition p' = d(Delta_p)/d(ln Delta_t) attributed to Bourdet 1983. Full text extracted this session. |
| Escobar, F.H.: 'Gas Well Testing', Chapter 5 in Advances in Natural Gas Emerging Technologies, IntechOpen, 2017. DOI 10.5772/67620. | full-text retrieved | Gas analogues: pseudopressure definition m(p) = 2*integral p/(mu Z) dp (Eq. 7); pseudotime (Eq. 6); t_D with 0.0002637 (Eq. 17) and t_Da (Eqs. 18-19); dimensionless pseudopressure and pseudopressure derivative with 1422.52 (Eqs. 19a-21); C_D = 0.8935 C/(phi h c_t r_w^2) (Eq. 22); the 1.422e6 / 1688 semilog form (Eq. 25) and k = 1637.74 q T/(m h) (Eq. 29); apparent skin s' = s + D q and the Geertsma beta correlation. SECONDARY for the underlying Al-Hussainy/Ramey/Crawford and Cinco-Ley results. |
| Zonoozi, Ilk, Blasingame et al.: 'The Pressure Derivative Revisited - Improved Formulations and Applications', SPE 103204, SPE ATCE San Antonio, 24-27 September 2006. | full-text retrieved | Independent corroboration of the power-law exponents: beta-derivative = 1 for wellbore storage and closed-reservoir boundaries, 1/2 for two-parallel-faults, three-perpendicular-faults, infinite-conductivity vertical fracture and horizontal-well formation linear flow, 1/4 for finite-conductivity vertical fracture. Also confirms the naming 'Bourdet well testing derivative' for Delta_p_d(t) = dDelta_p/dln(t). |
| IHS / Fekete WellTest documentation, 'Derivative Analyses' (conventional test analyses). | abstract/metadata only | SECONDARY, convention evidence only: 'To calculate the Bourdet derivative at any given point, one point before and one point after that point is used'; 'DX represents the log-cycle fraction used to control the amount of smoothing'; 'this value is typically quite small (0.01 to 0.2) and a small increase represents a significant increase in smoothing'. The formula itself is served as an SVG image and could NOT be read, so this source does not corroborate the weighting direction. |
| Agarwal, R.G.: 'A New Method to Account for Producing Time Effects When Drawdown Type Curves Are Used to Analyze Pressure Buildup and Other Test Data', SPE-9289-MS, SPE ATCE Dallas, 21-24 September 1980. DOI 10.2118/9289-MS. | abstract/metadata only | Origin of the equivalent time Delta_t_e = t_p Delta_t/(t_p + Delta_t). The formula itself is taken from Bourdet Eq. 7 (primary, retrieved); this reference supplies only the citation and the fact that the method is built from logarithmic approximations to Ei-function solutions. |
| J. Lee: 'Well Testing', SPE Textbook Series Vol. 1 (1982); Earlougher, R.C.: 'Advances in Well Test Analysis', SPE Monograph 5 (1977); Theis, C.V. (1935). | Unverified — cited source not inspected - not retrieved | The field-unit Ei solution with 70.6 and 948, the t_D > 100 / t > 3.79e5 phi mu c_t r_w^2/k line-source limit, the t < 948 phi mu c_t r_e^2/k infinite-acting limit, the t_D/r_D^2 > 25 log-approximation criterion, and the pseudo-steady-state slope constant 0.23395. Every one of these numbers was independently RE-DERIVED this session from the 0.0002637 and 141.2 groups and the SI unit conversions, so the arithmetic does not rest on the recalled attribution - but the attribution itself is from memory. |
| Cinco-Ley, H. and Samaniego-V., F.: 'Transient Pressure Analysis for Fractured Wells', JPT (September 1981); Gringarten, A.C., Ramey, H.J. and Raghavan, R.: 'Unsteady-State Pressure Distributions Created by a Well With a Single Infinite-Conductivity Vertical Fracture', SPEJ (August 1974). | Unverified — cited source not inspected - not retrieved | Origin of the bilinear (44.11) and linear (4.064) flow solutions and their validity windows. The two constants are corroborated by the retrieved Bourdet-2002 equation set (and 4.064 was re-derived); the VALIDITY WINDOWS are recalled only and are flagged UNVERIFIED. |

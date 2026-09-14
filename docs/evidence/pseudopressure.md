# Evidence card: Real-gas pseudopressure

> Each card records what an implementer needs, where it came from, and how far it was
> verified. A card is not an authority: it is a statement of evidence with its access
> level attached. Items marked unverified are unverified, and the implementation must
> treat them as such.

**Adversarial review verdict:** `SOUND_WITH_CORRECTIONS`  
**Corrections applied:** 12  
**Items left unverified:** 10

## Summary

The Al-Hussainy-Ramey-Crawford pseudopressure is m(p) = 2 * int_{p_m}^{p} p'/(mu(p') Z(p')) dp', with p_m "a low base pressure" chosen arbitrarily; the factor of 2 is real and comes from p*grad(p) = (1/2)*grad(p^2), and it is matched by a 1/2 in the mass-flux relation (their Eq. 20, flux = -(M k / 2RT) grad m). In field units m(p) carries psia^2/cp and all pressures are ABSOLUTE. m(p) transforms their Eq. 7, div[ p/(mu Z) grad p ] = (phi/k) d/dt (p/Z), into Eq. 18, grad^2 m = (phi mu(p) c_g(p) / k) dm/dt: the LEFT side (the spatial/flux operator) is linearised EXACTLY, with no small-pressure-gradient assumption, but the paper states plainly that "Eq. 18 is still non-linear because diffusivity is a function of potential". Everything downstream that people blame on pseudopressure - rate superposition, changing mu*c_t in time, wellbore storage, condensate banking, non-Darcy skin - lives in that residual RHS nonlinearity or outside the single-phase Darcy assumption altogether, and pseudotime (Agarwal 1979) is the acknowledged non-rigorous patch for the time term. For an implementer the exact oracles are: constant mu and Z gives m(p)-m(p_ref) = (p^2 - p_ref^2)/(mu Z) reproduced to machine precision by 2-panel Simpson (the integrand is then a degree-1 polynomial), and the ideal-gas limit of their Table 1 reduces to (p_pr^2 - 0.04)/(2 T_pr). The integrand p/(mu Z) is C-infinity in p away from the near-critical hump at T_pr ~ 1.05, so composite Simpson shows a clean observed order 4 under Richardson refinement - but only if mu and Z come from a smooth analytic correlation; I demonstrated that linearly interpolating a PVT table caps the observed order at 2, and that double precision floors the error at ~3e-14 relative because m(p) values are O(1e9).

## Equations

### Real gas pseudopressure (Al-Hussainy-Ramey-Crawford Eq. 14)

```
m(p) = 2 * integral_{p_m}^{p} [ p' / ( mu(p') * Z(p') ) ] dp'
```

*Unit system:* field (oilfield) units; p and p_m are ABSOLUTE pressures in psia

| Symbol | Meaning | Units |
|---|---|---|
| `m(p), also written psi(p)` | real gas pseudopressure / real gas potential | psia^2/cp |
| `p` | absolute pressure (upper limit of integration) | psia |
| `p_m` | base (datum) pressure, lower limit of integration; the paper calls it 'a low base pressure' and says the limit 'can be set arbitrarily' | psia |
| `p'` | dummy integration variable | psia |
| `mu(p)` | gas viscosity at p and reservoir temperature T | cp |
| `Z(p)` | gas-law deviation (compressibility) factor at p and T | dimensionless |

Assumptions:

- Isothermal flow at reservoir temperature T, so mu and Z are functions of p ALONE - this is what makes the definition unique (the paper says so explicitly).
- Single phase gas of CONSTANT composition.
- Homogeneous medium; laminar (Darcy) flow used to simplify the presentation (the paper says the laminar assumption can be removed).
- Permeability treated as NOT a function of pressure (Klinkenberg effect judged negligible for gas reservoir conditions); if k(p) matters it must go INSIDE the integral - see their Eq. 36.
- The factor 2 originates from p*grad(p) = (1/2)*grad(p^2) (their Eq. 8) and is mirrored by the 1/2 in their mass-flux Eq. 20. Dropping it does not change any DIFFERENCE-based workflow if dropped consistently, but it breaks every published field-unit coefficient (1637, 1422, 57895.3).

*Source:* Al-Hussainy, R., Ramey, H.J. Jr., Crawford, P.B., 'The Flow of Real Gases Through Porous Media', JPT 18(05) 624-636, May 1966, SPE-1243-A-PA, DOI 10.2118/1243-A-PA - Eq. 14, read directly from the scanned paper  
*Access:* full-text retrieved

### Rigorous (un-linearised) real-gas flow PDE that m(p) acts on (Eq. 7)

```
div[ ( p / ( mu(p) * Z(p) ) ) * grad p ] = ( phi / k ) * d/dt [ p / Z(p) ]
```

*Unit system:* consistent (Darcy/SI-like) units as written in the paper; convert with the usual field-unit factors

| Symbol | Meaning | Units |
|---|---|---|
| `phi` | porosity | fraction |
| `k` | absolute permeability (liquid permeability; treated as pressure independent) | md (field) or darcy (consistent) |
| `t` | time | hr (field) |

Assumptions:

- Follows from continuity (Eq. 1) + Darcy (Eq. 2) + real gas density rho = (M/RT)(p/Z) (Eq. 4).
- The paper calls Eq. 5 (the density form) 'one form of the fundamental non-linear partial differential equation describing isothermal flow of real gases through porous media'; Eq. 7 is Eq. 5 with k pulled out as pressure independent and is 'correct for all practical purposes'.

*Source:* Al-Hussainy et al. 1966, Eqs. 3-7  
*Access:* full-text retrieved

### What m(p) linearises: the pseudopressure diffusivity equation (Eqs. 17-18), radial form (Eq. 29)

```
grad^2 m(p) = ( phi * mu(p) * c_g(p) / k ) * dm(p)/dt      ;   radial:  d2m/dr2 + (1/r) dm/dr = ( phi * mu(p) * c_g(p) / k ) * dm/dt
```

*Unit system:* consistent units as written; in field units the RHS coefficient becomes phi*mu*c_t/(0.0002637*k) with t in hr, k in md, mu in cp, c_t in 1/psi, r in ft

| Symbol | Meaning | Units |
|---|---|---|
| `c_g(p)` | isothermal gas compressibility, c_g = 1/p - (1/Z) dZ/dp (their Eq. 10) | 1/psi |
| `m(p)` | real gas pseudopressure | psia^2/cp |

Assumptions:

- THIS IS THE KEY CLAIM AND ITS LIMIT. Eq. 18 is obtained from Eq. 7 with NO small-pressure-gradient assumption and NO assumption that mu*Z varies slowly - the paper states both exclusions explicitly. The second-degree gradient term (grad p)^2 is handled rigorously, not neglected.
- BUT the paper states: 'Eq. 18 is still non-linear because diffusivity is a function of potential'. The coefficient mu(p)*c_g(p) still depends on the solution. Z no longer appears explicitly but is buried inside m(p) and c_g(p).
- Compare with Eq. 13, grad^2 (p^2) = (phi mu(p) c_g(p)/k) d(p^2)/dt, which the paper derives only AFTER assuming either that d[ln(mu Z)]/d(p^2) is negligible OR that pressure gradients are small. m(p) removes that extra assumption; it does not remove the diffusivity nonlinearity.
- Boundary conditions must be converted too: a no-flow boundary becomes dm/dn = 0 (Eq. 21); steady state becomes Laplace's equation grad^2 m = 0 (Eq. 22).

*Source:* Al-Hussainy et al. 1966, Eqs. 12, 13, 17, 18, 21, 22, 29  
*Access:* full-text retrieved

### Chain rule / derivative identity (Eqs. 15-16) - the invariant to unit-test

```
dm(p)/dp = 2*p / ( mu(p) * Z(p) )   ;   dm/dt = [2p/(mu Z)] * dp/dt   ;   dm/dx = [2p/(mu Z)] * dp/dx
```

*Unit system:* field units: dm/dp in psia/cp

| Symbol | Meaning | Units |
|---|---|---|
| `dm/dp` | derivative of pseudopressure w.r.t. pressure; equals the integrand | psia/cp |

Assumptions:

- Follows from the fundamental theorem of calculus. Independent of the datum p_m - this is the algebraic reason the datum cancels in every derivative-based (Bourdet-type) diagnostic.
- Excellent implementation test: finite-difference your m(p) table and compare against 2p/(mu Z) evaluated directly; they must agree to the quadrature/interp error, not merely 'look similar'.

*Source:* Al-Hussainy et al. 1966, Eqs. 15-16  
*Access:* full-text retrieved

### ANALYTIC ORACLE 1 - constant mu and constant Z (exact, machine precision)

```
m(p) - m(p_ref) = ( p^2 - p_ref^2 ) / ( mu * Z )
```

*Unit system:* field: psia^2/cp

| Symbol | Meaning | Units |
|---|---|---|
| `mu` | constant gas viscosity | cp |
| `Z` | constant deviation factor | dimensionless |

Assumptions:

- Exact, not an approximation, when mu and Z are literally constant. Integrand is then 2p/(mu Z), a degree-1 polynomial, so ANY quadrature of degree of exactness >= 1 reproduces it exactly: trapezoid with 1 interval, composite Simpson with 2 panels, 1-point Gauss-Legendre. I verified relative error = 0.000e+00 with mu=0.02, Z=0.9, p_ref=14.7, p=5000 using 2-panel Simpson.
- Use this as the FIRST regression test. If it does not pass to machine precision, the bug is in the factor 2, the datum handling, or the panel bookkeeping - not in the physics.

*Source:* Direct consequence of Al-Hussainy et al. Eq. 14; verified numerically this session  
*Access:* full-text retrieved

### ANALYTIC ORACLE 2 - ideal-gas limit of the paper's own reduced integral (Eq. 27 / Table 1)

```
m(p) = ( 2 * p_pc^2 / mu_1 ) * integral_{(p_pr)_m}^{p_pr} [ p_pr' / ( (mu/mu_1)(p_pr') * Z(p_pr') ) ] dp_pr'    ;  Table 1 tabulates  mu_1*m(p)/(2*p_pc^2*T_pr) = integral_{0.2}^{p_pr} p_pr' dp_pr' / [ T_pr * (mu/mu_1) * Z ]   ;  IDEAL LIMIT (mu/mu_1 -> 1, Z -> 1):  = ( p_pr^2 - 0.04 ) / ( 2 * T_pr )
```

*Unit system:* reduced/dimensionless (pseudo-reduced pressure and temperature); p_pc in psia, mu_1 in cp

| Symbol | Meaning | Units |
|---|---|---|
| `p_pr` | pseudo-reduced pressure, p/p_pc (Eq. 23) | dimensionless |
| `T_pr` | pseudo-reduced temperature, T/T_pc (Eq. 24), T ABSOLUTE | dimensionless |
| `p_pc, T_pc` | pseudo-critical pressure and temperature | psia, degR |
| `mu_1` | gas viscosity at one atmosphere and reservoir T (Carr et al. correlating variable) | cp |
| `(p_pr)_m` | lower limit of the reduced integral; the paper CHOSE 0.20 | dimensionless |

Assumptions:

- The 0.20 lower limit is an arbitrary datum choice made by the authors for their table, NOT a physical constant. It cancels in every difference.
- The ideal-gas dashed line in their Fig. 1 (p_pr/[(mu/mu_1) Z] vs p_pr) is a straight line through the origin, which is the graphical statement of this oracle.

*Source:* Al-Hussainy et al. 1966, Eqs. 23-27, Fig. 1, Fig. 2, Table 1  
*Access:* full-text retrieved

### ANALYTIC ORACLE 3 - p-squared (low pressure) approximation

```
m(pbar) - m(p_wf) ~= ( pbar^2 - p_wf^2 ) / ( mu_g * Z )|_{p_avg}  , with  p_avg = sqrt( ( pbar^2 + p_wf^2 ) / 2 )   ;  deliverability form:  q_g = k*h*( pbar^2 - p_wf^2 ) / [ 1422 * T * (mu_g Z)|_avg * ( ln(re/rw) - 0.75 + s ) ]
```

*Unit system:* field: q_g in Mscf/D, k in md, h in ft, T in degR (ABSOLUTE), p in psia, mu in cp

| Symbol | Meaning | Units |
|---|---|---|
| `pbar` | average reservoir pressure | psia |
| `p_wf` | bottomhole flowing pressure | psia |
| `s` | skin (Darcy part only) | dimensionless |
| `1422` | field-unit constant for gas Darcy flow with q in Mscf/D (= 1422, Ahmed Eqs. 6-43 and 8-11) | psia^2/(cp) per (Mscf/D * degR / (md*ft)) |

Assumptions:

- VALIDITY: BOTH pbar and p_wf below ~2000 psi (Region I). The physical basis is that the PRODUCT mu_g*Z is nearly constant there, so 2p/(mu Z) is nearly LINEAR in p. Ahmed attributes the 'mu_g*Z essentially constant below 2000 psi' statement to Golan and Whitson (1986).
- ERROR I MEASURED on real retrieved PVT (Anaconda Gas Field table, Ahmed Example 6-7): mu*Z varies +17.6% from 400 to 2000 psi (0.01205 -> 0.014168), yet the p-squared estimate of the pseudopressure DROP is only -0.17% to -0.50% in error for pbar/p_wf pairs inside Region I, because evaluating mu*Z at p_avg makes the errors cancel. Do NOT generalise 0.5% to other gases; it is one dataset.
- The approximation degrades fast if one endpoint leaves Region I. Ahmed: between 2000 and 3000 psi 'the pressure function shows distinct curvature' and the full pseudopressure MUST be used.

*Source:* Ahmed, T., 'Reservoir Engineering Handbook', Eqs. 8-11 to 8-14 and p.550-551 (Region I); Golan & Whitson (1986) cited therein; error magnitudes computed by me this session from Ahmed's Example 6-7 table  
*Access:* full-text retrieved

### ANALYTIC ORACLE 4 - pressure (high pressure) approximation

```
m(pbar) - m(p_wf) ~= [ 2*p / ( mu_g * Z ) ]|_{p_avg} * ( pbar - p_wf )  , with p_avg = ( pbar + p_wf )/2   ;  equivalently, since 1/(mu_g B_g) ~ const:  q_g = 70.81e-6 * k*h*( pbar - p_wf ) / [ (mu_g B_g)|_avg * ( ln(re/rw) - 0.75 + s ) ]
```

*Unit system:* field: q_g in Mscf/D, B_g in bbl/scf, k in md, h in ft, p in psia, mu in cp

| Symbol | Meaning | Units |
|---|---|---|
| `B_g` | gas formation volume factor | bbl/scf |
| `[2p/(mu Z)]|_avg` | the pseudopressure integrand, treated as constant over the interval | psia/cp |

Assumptions:

- VALIDITY: BOTH p_wf and pbar above ~3000 psi (Region III). Physical basis: above ~3000 psi mu_g*Z becomes approximately PROPORTIONAL to p, so the integrand 2p/(mu Z) is nearly CONSTANT and m(p) is nearly LINEAR in p.
- ERROR I MEASURED on the same retrieved table: 2p/(mu Z) = 343167 / 348247 / 349711 / 346924 psia/cp at 3200/3600/4000/4400 psia - variation under 2% across 1200 psi. The pressure-approximation estimate of the pseudopressure drop is +0.17% to +0.20% in error for (4400->3600) and (4000->3200).
- CAUTION on the 70.81e-6 coefficient: I read it out of a PDF text layer that garbled the surrounding characters. Treat the 70.81e-6 value as needing an independent check before use. The [2p/(mu Z)]|_avg * delta_p form above is clean and is the one to implement.

*Source:* Ahmed, T., 'Reservoir Engineering Handbook', Eqs. 8-8 to 8-10 and p.549-550 (Region III); error magnitudes computed by me this session  
*Access:* full-text retrieved

### Field-unit constant-rate drawdown solution in pseudopressure (the payoff equation)

```
m(p_wf) = m(p_i) - ( 1637 * q_g * T / ( k * h ) ) * [ log10( k*t / ( phi * mu_i * c_ti * r_w^2 ) ) - 3.23 ]     ;  equivalently  m(p_wf) = m(p_i) - (1637 q_g T/(k h)) * log10( 4*t_D / gamma ),  t_D = 0.0002637 * k * t / ( phi * mu_i * c_ti * r_w^2 ),  gamma = exp(0.5772)
```

*Unit system:* field units: m in psia^2/cp, q_g in Mscf/D, T in degR (ABSOLUTE), k in md, h in ft, t in hr, phi fraction, mu_i in cp, c_ti in 1/psi, r_w in ft

| Symbol | Meaning | Units |
|---|---|---|
| `1637` | field-unit semilog slope constant; = 57895.3 * (p_sc/T_sc) with p_sc = 14.7 psia, T_sc = 520 degR (57895.3*14.7/520 = 1636.7) | composite |
| `3.23` | = -log10( 4 * 0.0002637 / exp(0.5772) ) = 3.227; ties the two forms together exactly | dimensionless |
| `0.0002637` | field-unit diffusivity constant (Ahmed rounds it to 0.000264 in Ch.6 and writes 0.0002637 elsewhere in the same book) | composite |
| `mu_i, c_ti` | gas viscosity and total compressibility evaluated at INITIAL pressure p_i | cp, 1/psi |

Assumptions:

- This is the liquid-analogy solution transplanted onto m(p). The paper justifies it (Eqs. 29-31, Fig. 3): mu*c_g vs m(p) for a real gas resembles 1/p vs p^2 for an ideal gas, so t_D built on INITIAL mu and c is the right correlating group.
- mu_i and c_ti are at INITIAL pressure, not average, not flowing. Mixing this up is a classic defect.
- The paper is explicit that this is an engineering approximation: their Fig. 5 shows m_D(t_D) departs from p_D(t_D) at long times and the departure is RATE DEPENDENT; 'no single set of m_D(t_D) correlations could be expected to apply to all real gases at long production times'.

*Source:* Ahmed, T., 'Reservoir Engineering Handbook', Eqs. 6-107 to 6-109 and Example 6-9; constants reproduced exactly by me this session  
*Access:* full-text retrieved

### Dimensionless pseudopressure drop and dimensionless time (Eqs. 30-31)

```
m_D(r_D, t_D) = pi * k * h * T_sc * [ m(p_i) - m(r,t) ] / ( q_sc * p_sc * T )    ;   t_D = k * t / ( phi * (mu*c_g)_i * r_w^2 )
```

*Unit system:* consistent (Darcy) units as written in the paper; add 0.0002637 to t_D for field units

| Symbol | Meaning | Units |
|---|---|---|
| `m_D` | dimensionless real gas pseudopressure drop, analogue of van Everdingen-Hurst p_D | dimensionless |
| `q_sc, p_sc, T_sc` | rate, pressure, temperature at standard conditions | scf/D, psia, degR |
| `(mu*c_g)_i` | viscosity-compressibility product at INITIAL pressure | cp/psi |

Assumptions:

- The paper's own headline caveat (Figs. 4-5): the m_D(t_D) correlation 'is actually not as good as it appears' - good before boundary effects, with 'considerable difference' at long times, and the deviation grows with flow rate Q and is much worse for condensate than for dry natural gas.

*Source:* Al-Hussainy et al. 1966, Eqs. 30-31, Figs. 3-5  
*Access:* full-text retrieved

### Normalised pseudopressure (modern practice)

```
p_pn = ( mu_i * Z_i / ( 2 * p_i ) ) * m(p) = ( mu_i * Z_i / p_i ) * integral_{p_0}^{p} [ p' / ( mu(p') Z(p') ) ] dp'
```

*Unit system:* field: p_pn has units of PRESSURE, psia

| Symbol | Meaning | Units |
|---|---|---|
| `p_pn` | normalised pseudopressure (Meunier et al. normalised pseudovariable) | psia |
| `mu_i, Z_i, p_i` | viscosity, deviation factor and pressure at the INITIAL (reference) condition | cp, dimensionless, psia |

Assumptions:

- Purpose is purely cosmetic/numerical: it restores the units and magnitude of pressure so liquid-case equations and type curves can be used verbatim and so an engineer retains physical feel. The paper (Meunier, Kabir, Wittmann 1987) states the results are IDENTICAL to conventional pseudovariables.
- Because it is an affine map of m(p), every statement below about datum cancellation applies unchanged.
- WHY THE DATUM MATTERS FOR DIFFERENCES BUT NOT DERIVATIVES: changing p_m -> p_m' adds the SAME constant C = 2*int_{p_m'}^{p_m} p/(mu Z) dp to every m value. Any DIFFERENCE m(p_a) - m(p_b) is invariant, so drawdowns and deliverability are safe PROVIDED both endpoints use the same datum. Any DERIVATIVE dm/dp, dm/dt, dm/d(ln t) (Bourdet derivative) kills the constant identically. But a BARE m value - reported, plotted against a fixed axis, or compared against another vendor's table - is meaningless without its datum. NEVER mix two m(p) tables built on different p_m.

*Source:* Meunier, D.F., Kabir, C.S., Wittmann, M.J., 'Gas Well Test Analysis: Use of Normalized Pseudovariables', SPE Formation Evaluation 2(04) 629-636, 1987, DOI 10.2118/13082-PA (metadata verified via Crossref); the explicit (mu Z / 2p)_i * m(p) form taken from a secondary encyclopedia entry  
*Access:* abstract/metadata only (primary); secondary source for the explicit formula

### Real gas pseudotime (Agarwal 1979) and normalised pseudotime

```
t_a(p) = integral_{0}^{t} dt' / [ mu_g(p) * c_t(p) ]      ;    normalised:  t_an = mu_gi * c_ti * integral_{0}^{t} dt' / [ mu_g(p) * c_t(p) ]
```

*Unit system:* field: t_a in hr*psi/cp; t_an in hr

| Symbol | Meaning | Units |
|---|---|---|
| `t_a` | real gas pseudotime | hr*psi/cp (i.e. hr / (cp * psi^-1)) |
| `t_an` | normalised pseudotime, restored to units of time | hr |
| `mu_g(p), c_t(p)` | gas viscosity and total compressibility at the chosen reference pressure, which is a function of TIME | cp, 1/psi |
| `mu_gi, c_ti` | same properties at initial conditions (normalising constants) | cp, 1/psi |

Assumptions:

- THE REFERENCE PRESSURE IS THE WHOLE ARGUMENT AND IT IS NOT SETTLED. Agarwal (1979) evaluated mu_g and c_t at WELLBORE pressure (buildup of MHF gas wells with long wellbore-storage distortion). Blasingame and co-workers use AVERAGE RESERVOIR pressure (requires gas-in-place and a material balance, i.e. it is implicit). Anderson and Mattar (2005, 2007) use the average pressure of the REGION OF INVESTIGATION during transient flow, arguing it matches numerical simulation better.
- CRITICAL HONEST STATEMENT, quoted from the IHS/Fekete reference material retrieved this session: 'the concept of pseudo-time is not amenable to a completely rigorous solution, as is the case for pseudo-pressure, because the gas properties change with pressure, not time.' Pseudopressure is an exact change of variable; pseudotime is NOT. It is a fitted/iterative correction.
- Agarwal used a simplified form of total compressibility c_t (per secondary sources); do not assume it equals the modern c_t = c_g S_g + c_w S_w + c_f without checking.

*Source:* Agarwal, R.G., "'Real Gas Pseudo-Time' - A New Function For Pressure Buildup Analysis Of MHF Gas Wells", SPE-8279-MS, SPE ATCE, Las Vegas, 23-26 Sept 1979, DOI 10.2118/8279-MS (metadata verified via Crossref); units and reference-condition statements from IHS WellTest 'Pseudo-Time' reference page retrieved this session  
*Access:* abstract/metadata only (primary paper); secondary vendor documentation retrieved for units and conventions

### Material balance pseudotime (Palacio-Blasingame type), RECALLED FORM - VERIFY BEFORE CODING

```
t_ca = ( mu_gi * c_ti / q_g(t) ) * integral_{0}^{t} [ q_g(tau) / ( mu_g(pbar) * c_t(pbar) ) ] dtau
```

*Unit system:* field: t_ca in hr or days depending on q_g units; q_g in Mscf/D

| Symbol | Meaning | Units |
|---|---|---|
| `t_ca` | material balance pseudotime (a.k.a. t_ma) | hr or D |
| `q_g(t)` | instantaneous surface gas rate | Mscf/D |
| `pbar` | average reservoir pressure from the gas material balance, itself a function of cumulative production and gas-in-place | psia |

Assumptions:

- I did NOT retrieve the Palacio-Blasingame paper text this session. Crossref returns the record for SPE-25909-MS (Palacio & Blasingame, 1993) with the title marked 'UNAVAILABLE'. The formula above is Unverified — cited source not inspected — and matches the descriptions in secondary sources (rate-normalised pseudopressure dp_p/q_g plotted vs t_ca gives a pseudosteady-state straight line whose slope is inversely proportional to contacted pore volume), but the exact placement of q_g(t) outside the integral must be confirmed against the primary paper.
- It is IMPLICIT: pbar depends on gas-in-place, which is what the analysis is trying to determine. Implementations iterate.

*Source:* Palacio, J.C. and Blasingame, T.A., 'Decline-Curve Analysis With Type Curves - Analysis of Gas Well Production Data', SPE-25909-MS, 1993, DOI 10.2118/25909-MS (Crossref metadata only); formula recalled  
*Access:* Unverified — cited source not inspected (not retrieved)

### Pressure-dependent permeability inside the pseudopressure (Eq. 36) - the paper's own extension

```
m'(p) = 2 * integral_{p_m}^{p} [ k(p') * p' / ( mu(p') * Z(p') ) ] dp'    ;   then  ln(r_d/r_w) = pi*h*T_sc*[ m'(pbar) - m'(p_wf) ] / ( q_sc * p_sc * T )
```

*Unit system:* field: m'(p) carries md*psia^2/cp

| Symbol | Meaning | Units |
|---|---|---|
| `m'(p)` | pseudopressure with permeability inside the integral | md*psia^2/cp |
| `k(p)` | effective permeability as a known function of pressure (condensate dropout, Klinkenberg, stress sensitivity) | md |

Assumptions:

- The paper offers this for gas condensate via the Eilerts et al. treatment, and immediately hedges: 'The usefulness of considering k a function of pressure to handle condensate flow might be open to question.' It is a first-order patch, not the modern treatment.
- m'(p) is reservoir- and rock-specific; it is NOT a fluid property and cannot be tabulated once per gas.
- This also captures Klinkenberg k(p) = k_l*(1 + b/p) (their Eq. 6), which they judged negligible for gas reservoir pressures but which matters in tight/shale systems.

*Source:* Al-Hussainy et al. 1966, Eqs. 6, 35-36  
*Access:* full-text retrieved

### Non-Darcy skin sits OUTSIDE the pseudopressure (Eq. 37)

```
pi * k * h * T_sc * [ m(pbar) - m(p_wf) ] / ( q_sc * p_sc * T ) = ln( r_d / r_w ) + s + D * q_sc
```

*Unit system:* consistent units as written; field-unit equivalents use 1422 or 1424

| Symbol | Meaning | Units |
|---|---|---|
| `s` | steady-state (Darcy) skin | dimensionless |
| `D` | non-Darcy (turbulence/inertial) flow coefficient | 1/(Mscf/D) in field units |
| `r_d` | Aronofsky-Jenkins transient drainage radius; -> 0.472*r_e at long time | ft |

Assumptions:

- The D*q_sc term is RATE DEPENDENT and ADDITIVE to skin. m(p) does nothing about it. It is the reason a single-rate gas test cannot separate s from D and why multi-rate (isochronal / modified isochronal) testing exists.
- The paper introduced this by borrowing the Eilerts et al. steady-state non-Darcy region near the well; it is an approximation bolted onto the linearised solution, not a consequence of it.

*Source:* Al-Hussainy et al. 1966, Eq. 37 and Eq. 32; Fig. 6 for r_d -> 0.472 r_e  
*Access:* full-text retrieved

### Gas-condensate replacement for m(p) (Fevang-Whitson, black-oil form)

```
q_g = C * integral_{p_wf}^{p_R} [ ( k_ro / ( B_o * mu_o ) ) * R_s + k_rg / ( B_g * mu_g ) ] dp   ,   C = 2*pi*a1*k*h / ( ln(re/rw) - 0.75 + s ) ,  a1 = 1/(2*pi*141.2) for field units
```

*Unit system:* field units as stated by the authors

| Symbol | Meaning | Units |
|---|---|---|
| `k_rg, k_ro` | gas and oil relative permeability, functions of saturation (hence of radius and time) | dimensionless |
| `B_g, B_o` | gas and oil formation volume factors | bbl/scf, bbl/STB |
| `R_s` | solution gas-oil ratio | scf/STB |
| `p_R` | reservoir pressure at the outer boundary of the integration | psia |

Assumptions:

- Below the dewpoint the integrand is NOT a function of pressure alone - it depends on saturation, which depends on radius and time. The single-phase m(p) is then not merely inaccurate, it is not well defined.
- Fevang-Whitson three-region model: Region 1 = inner near-wellbore region where gas AND oil flow (constant flowing composition/GOR, dewpoint of the produced wellstream equals pressure at its outer edge) and is 'the main source of deliverability loss'; Region 2 = net condensate accumulation, effectively only gas flowing, saturations approximated by the CVD liquid dropout curve; Region 3 = single-phase original reservoir gas, where ordinary m(p) IS valid.
- The authors note the pseudopressure integral, evaluated properly, is 'for practical purposes independent of well geometry'.
- Blockage severity depends on relative permeability only in the range 1 < k_rg/k_ro < 50.

*Source:* Fevang, O. and Whitson, C.H., 'Modeling Gas-Condensate Well Deliverability', SPE Reservoir Engineering 11(04) 221-230, 1996, SPE-30714, DOI 10.2118/30714-PA - Eqs. 1-3 and the Flow Regions section  
*Access:* full-text retrieved

### Composite Simpson error term (the order you should DEMONSTRATE, not assert)

```
E_n(f) = - ( ( b - a ) / 180 ) * h^4 * f''''(xi) ,  a < xi < b   ,  h = (b-a)/n  , n even
```

*Unit system:* pure mathematics (unit-agnostic)

| Symbol | Meaning | Units |
|---|---|---|
| `h` | panel width in the integration variable (here, pressure step in psia) | psia |
| `f''''` | fourth derivative of the integrand p/(mu Z) with respect to p | psia^-3/cp |
| `n` | number of subintervals (must be even) | count |

Assumptions:

- Requires f in C^4 on [a,b]. Composite Simpson is exact for polynomials of degree <= 3.
- n-point Gauss-Legendre is exact for polynomials of degree <= 2n-1 (DLMF 3.5(v)). A Kronrod extension of an n'-point Gauss rule adds n'+1 nodes for 2n'+1 total and is exact to degree 3n'+1, which is where the embedded error estimate comes from.
- QUADPACK QAGS (the engine behind scipy.integrate.quad) defaults to the 10-point Gauss / 21-point Kronrod pair with adaptive bisection and epsilon-algorithm extrapolation.

*Source:* NIST Digital Library of Mathematical Functions, section 3.5, Eq. 3.5.8 (Simpson error) and 3.5.20_1 (Gauss degree of exactness); Gauss-Kronrod degree from secondary numerical-library documentation  
*Access:* full-text retrieved (DLMF); secondary for Gauss-Kronrod specifics

### Richardson order estimator - the grid-refinement test that PROVES the order

```
For I_h computed at h and I_{h/2} at h/2 and I_{h/4} at h/4 (no exact answer needed):  p_obs = log2( | I_h - I_{h/2} | / | I_{h/2} - I_{h/4} | )    ;  with a trusted reference I_ref:  p_obs = log2( | I_h - I_ref | / | I_{h/2} - I_ref | )   ;  extrapolated value:  I_ext = I_{h/2} + ( I_{h/2} - I_h ) / ( 2^p - 1 )
```

*Unit system:* pure mathematics

| Symbol | Meaning | Units |
|---|---|---|
| `p_obs` | observed (empirical) convergence order | dimensionless |
| `I_ref` | reference value, e.g. Simpson at n = 2^20 or an adaptive Gauss-Kronrod result at tight tolerance | psia^2/cp |

Assumptions:

- p_obs -> 4 for composite Simpson on a smooth integrand ONLY in the asymptotic window: coarse enough that discretisation error dominates, fine enough that the leading-order term dominates, and above the roundoff floor. Outside that window the number is meaningless.
- For Simpson, I_ext with p=4 is exactly Romberg's next column; a working alternative is to run full Romberg and watch the table columns.
- Gauss-Legendre on a fixed interval does NOT have an h-refinement order; it converges by increasing n, and for an analytic integrand the convergence is GEOMETRIC (error falls roughly like rho^-2n). So a log-log h-refinement test is the wrong instrument for Gauss-Legendre - plot log(error) vs n and expect a straight line, not a slope-4 line.
- Adaptive Gauss-Kronrod converges to a user tolerance, not an order. Test it by tightening epsabs/epsrel and checking the answer stops moving, and by checking the returned error estimate against the true error on the constant-mu-Z oracle.

*Source:* Standard numerical analysis (Richardson extrapolation / Romberg); the Simpson h^4 term is DLMF 3.5.8; orders demonstrated numerically by me this session  
*Access:* full-text retrieved (DLMF for the error term); the test recipe is standard practice

## Constants

| Name | Value | Units | Source | How verified |
|---|---|---|---|---|
| Factor of 2 in the m(p) definition | `2` | dimensionless | Al-Hussainy, Ramey & Crawford 1966, Eq. 14 (and its partner, the 1/2 in the mass-flux Eq. 20 and the identity p*grad p = (1/2) grad p^2, Eq. 8) | Read directly off the scanned page 32 of the retrieved paper PDF. Eq. 14 reads m(p) = 2 * integral_{p_m}^{p} [p / (mu(p) z(p))] dp, and Eq. 20 reads (q/A)*rho = -(M k / 2 R T) * grad m(p). |
| Lower integration limit / datum p_m | `arbitrary; the paper says 'a low base pressure' and 'the lower limit of the integration can be set arbitrarily'` | psia (absolute) | Al-Hussainy et al. 1966, text after Eq. 14 and text after Eq. 27 | Read directly from the retrieved paper. There is NO canonical value. Common choices in practice: p_m = 0 (Ahmed's Example 6-7 integrates from 0), p_m = 14.7 psia, p_m = p_base of a PVT table. |
| Reduced lower limit used for the paper's Table 1 and Fig. 2 | `(p_pr)_m = 0.20` | dimensionless (pseudo-reduced pressure) | Al-Hussainy et al. 1966, 'Evaluation of Real Gas Pseudo-Pressure' section | Read directly: 'The lower limit of the integration (p_pr)_m can be set arbitrarily. A value of 0.20 was chosen.' This is a chart convention, not a physical constant. |
| Units of m(p) in field units | `psia^2/cp` | psia^2/cp | Al-Hussainy et al. 1966: 'The variable m(p) has the dimensions of pressure-squared per centipoise'; and later 'a chart of m(p) in units of psi-squared per centipoise vs pressure in psi' | Read directly from the retrieved paper. Pressures MUST be absolute (psia); temperature MUST be absolute (degR) wherever T appears in the downstream coefficients. |
| Field-unit semilog slope constant for the pseudopressure drawdown solution | `1637` | composite: psia^2/cp per [ (Mscf/D)*(degR) / (md*ft) ] | Ahmed, 'Reservoir Engineering Handbook', Eq. 6-108/6-109 (attributed to Al-Hussainy et al. 1966) | Read from the retrieved handbook PDF text layer AND reproduced numerically: 1637 = 57895.3 * p_sc/T_sc with p_sc=14.7 psia, T_sc=520 degR (57895.3*14.7/520 = 1636.7). I also reran the book's Example 6-9 end to end and recovered m(p_wf) = 1.0775e9 psia^2/cp and p_wf = 4367 psi, matching the book exactly. |
| General field-unit constant with q_sc in Mscf/D, before the p_sc/T_sc substitution | `57,895.3` | composite | Ahmed, 'Reservoir Engineering Handbook', Eq. 6-107 | Read from the retrieved PDF text layer; cross-checked for internal consistency against 1637 as above. |
| Field-unit gas Darcy/deliverability constant | `1422` | composite: psia^2/cp per [ (Mscf/D)*(degR) / (md*ft) ] | Ahmed, 'Reservoir Engineering Handbook', Eqs. 6-43, 6-44, 8-11, 8-14 | Read from the retrieved PDF text layer in several independent equations. Note some texts use 1424; the difference is the standard-condition convention. Pick one and state it. |
| Field-unit diffusivity constant | `0.0002637 (Ahmed rounds it to 0.000264 in Chapter 6)` | composite: makes t_D = C*k*t/(phi*mu*c_t*r_w^2) dimensionless with t in hr, k in md, mu in cp, c_t in 1/psi, r_w in ft | Ahmed, 'Reservoir Engineering Handbook' - 0.000264 on the diffusivity-constant page and in Example 6-9, 0.0002637 elsewhere in the same book | Both spellings located by full-text scan of the retrieved PDF. I reproduced the book's Example 6-9 t_D = 224,498.6 using 0.000264 exactly. Flagging the inconsistency: the book uses BOTH values, ~0.03% apart. Pick 0.0002637 and document it. |
| Semilog intercept constant 3.23 | `3.23 (exactly 3.227)` | dimensionless | Ahmed, 'Reservoir Engineering Handbook', Eq. 6-108 | Verified by derivation this session: 3.23 = -log10( 4 * 0.0002637 / exp(0.5772) ) = -log10(5.929e-4) = 3.227. Consistency between Ahmed Eq. 6-108 and Eq. 6-109 confirms it. |
| Aronofsky-Jenkins long-time transient drainage radius | `r_d = 0.472 * r_e` | ft | Al-Hussainy et al. 1966, Fig. 6 and accompanying text | Read directly from the retrieved paper. Also read the paper's own caveat: 'The fact that r_d eventually becomes constant at 0.472 r_e does not mean the physical drainage radius stabilizes about half-way out in the reservoir. The entire reservoir volume is being drained.' |
| Pressure thresholds delimiting the three approximation regions | `Region I (p-squared): both p_wf and pbar < ~2000 psi. Region II (must use full m(p)): 2000-3000 psi. Region III (pressure approximation): both > ~3000 psi.` | psi | Ahmed, 'Reservoir Engineering Handbook', Ch. 8, 'Region I/II/III' headings, p.549-551; Ahmed attributes the 'mu_g*z essentially constant below 2000 psi' statement to Golan and Whitson (1986) | Read directly from the retrieved PDF text layer. These are CONVENTIONAL engineering thresholds derived from the shape of the 2p/(mu z) curve for typical natural gases - NOT universal constants. They will shift with gas gravity, temperature and contaminant content. Treat them as guidance and verify on the actual PVT. |
| Table 1 coverage in the 1966 paper | `T_pr from 1.05 to 3.00 (8 isotherms: 1.05, 1.15, 1.30, 1.50, 1.75, 2.00, 2.50, 3.00); p_pr from 0.30 to 15.00` | dimensionless | Al-Hussainy et al. 1966, Table 1 | Read directly from the scanned table. Note: entries are blank (dashes) at high p_pr for the low-T_pr isotherms - the T_pr=1.05 column stops at p_pr=5.00 and T_pr=1.15 stops at p_pr=8.50. Extrapolating past those is unsupported. |
| Standard conditions implied by the 1637 constant | `p_sc = 14.7 psia, T_sc = 520 degR` | psia, degR | Ahmed, 'Reservoir Engineering Handbook', text between Eq. 6-107 and 6-108 | Read directly; confirmed numerically via 57895.3*14.7/520 = 1636.7 ~ 1637. Other jurisdictions use 14.65 psia / 60 degF or 15.025 psia - the constant changes. State your standard conditions in the code. |

## Validity ranges

- m(p) ITSELF has no pressure validity range. It is an exact change of variable for any single-phase gas of constant composition under isothermal conditions, valid from the datum up to any pressure for which mu(p) and Z(p) are defined. Do not attach a pressure limit to m(p); attach limits to the CORRELATIONS you feed it and to the SOLUTIONS you apply it to.
- The linearised SOLUTIONS (the liquid analogy m_D = p_D) are approximate and degrade with (a) increasing flow rate and (b) increasing depletion. The paper's Fig. 5 shows m_D(t_D) falling progressively below p_D(t_D) at long times, with the gap widening as Q rises from 0.05 to 0.10, and far worse for condensate than for dry gas. Their Fig. 4/Fig. 6 show the drainage-radius correlation (Eq. 32) is a much better correlation than m_D(t_D) at all times.
- Al-Hussainy et al. Table 1 / Fig. 2: valid for T_pr in [1.05, 3.00] and p_pr in [0.30, 15.00], with truncated coverage at low T_pr (see constants). The underlying charts are the Standing-Katz Z-factor and Carr-Kobayashi-Burrows viscosity correlations, so their validity envelopes bound the table. The paper warns the table is 'limited to gases containing small amounts of contaminants'.
- p-squared approximation: BOTH pbar and p_wf below ~2000 psi (Region I). On the retrieved Anaconda Gas Field PVT this gave -0.17% to -0.50% error in the pseudopressure drop with mu*Z evaluated at p_avg = sqrt((pbar^2 + p_wf^2)/2), even though mu*Z itself varies +17.6% across the interval. Not a universal error bound - one dataset only.
- Pressure approximation: BOTH pbar and p_wf above ~3000 psi (Region III). On the same dataset, 2p/(mu Z) varies under 2% from 3200 to 4400 psia and the approximation errs by +0.17% to +0.20%.
- Between 2000 and 3000 psi neither approximation is defensible; Ahmed states the pressure function 'shows distinct curvature' there and the full pseudopressure must be used. Also: if ONE endpoint is inside a region and the other outside, NEITHER approximation applies - the criterion is on both endpoints, not on the average.
- Pseudotime has no clean validity range because it is not a rigorous transform. Its accuracy depends entirely on how well the chosen reference pressure (wellbore / average reservoir / average over the region of investigation) represents the pressure controlling mu*c_t at that time. It is weakest exactly where it is most needed: early transient flow in very low permeability, where the wellbore and the average reservoir pressure are far apart.
- Near-critical conditions (T_pr around 1.05-1.15, p_pr around 1-2) the integrand p_pr/[(mu/mu_1) Z] has a sharp local maximum (visible in the paper's Fig. 1). Smoothness-based quadrature arguments weaken there; use adaptive quadrature, not fixed-panel Simpson.

## Failure modes

- MIXED DATUMS. Two m(p) values computed with different lower limits p_m differ by a constant and cannot be subtracted. This is silent and produces a plausible-looking wrong drawdown. Defence: store p_m as a field on the m(p) table object and refuse to subtract across tables with different p_m.
- CATASTROPHIC CANCELLATION. m(p) values are O(1e8-1e9) psia^2/cp. Computing m(p_i) - m(p_wf) for a small drawdown subtracts two nearly equal large numbers. At 1e9 magnitude, double precision leaves ~1e-7 absolute resolution; I measured the quadrature roundoff floor at ~1e-4 absolute on a value of 3.48e9. Defence: for a DIFFERENCE, integrate directly over [p_wf, p_i] rather than differencing two datum-referenced values.
- NON-ABSOLUTE PRESSURE OR TEMPERATURE. Feeding psig instead of psia, or degF instead of degR, is dimensionally undetectable and quietly wrong. The integrand is 2p/(mu Z) with p ABSOLUTE; every field-unit constant (1637, 1422, 57895.3) assumes T in degR.
- MULTIPHASE. Below the dewpoint of a gas condensate, or with mobile/condensing water, mu and Z are no longer functions of pressure alone - they depend on saturation, hence on radius and time. The single-phase m(p) is then not merely inaccurate; the transformation is ill-defined. Use the Fevang-Whitson / Evinger-Muskat two-phase pseudopressure. The 1966 paper's own Fig. 5 already shows the condensate case departing dramatically from the liquid analogy.
- VARIABLE COMPOSITION. Compositional gradients, gas injection/cycling, or produced-stream composition changing with depletion break the 'constant composition' premise. Sour gas (H2S/CO2) needs a pseudocritical correction (e.g. Wichert-Aziz) before the reduced-property charts apply at all.
- RATE SUPERPOSITION IN REAL TIME. The 1966 paper is candid: because real-gas solutions 'do depend slightly upon production rate', superposition is not exact. They validated it for INCREASING rate schedules (against Carter's finite-difference solutions with wellbore storage) and found it excellent, and for one DECREASING-rate case (against Dykstra) found a 20 psi discrepancy out of a 2150 psi drawdown (0.9%). But they explicitly flag that 'it is not apparent that a decreasing rate schedule is susceptible to superposition' and that 'insufficient comparisons between finite-difference build-up solutions and superposition solutions for the real gas flow case have been made to completely explore this problem'. Modern boundary-dominated practice replaces real-time superposition with material-balance (pseudo)time, which is an admission that real-time superposition does not carry through depletion.
- CHANGING mu*c_t IN TIME. m(p) linearises the spatial operator exactly but leaves the diffusivity coefficient mu(p)*c_g(p) as a function of the solution. Over a large depletion (mu roughly doubles from 400 to 4400 psi on the retrieved PVT; c_g falls like 1/p at low pressure) the effective diffusivity changes by an order of magnitude. Pseudotime is the patch; it is explicitly not rigorous.
- WELLBORE STORAGE. Pseudopressure does nothing for storage, and gas-well storage is WORSE than liquid-well storage because the wellbore fluid compressibility itself changes with pressure, so the storage coefficient C is not constant. The 1966 paper handled Carter's storage cases by borrowing a constant C ~ 300 and noting 'the value of C for Carter's solutions does vary slightly with pressure'. Agarwal's 1979 pseudotime paper was motivated precisely by long-duration wellbore-storage distortion in low-permeability gas wells.
- NON-DARCY SKIN. The rate-dependent D*q_sc term is additive and external to m(p) (paper Eq. 37). A single-rate test cannot separate s from D; you need multi-rate data. Reporting a 'skin' from a single gas drawdown without saying it is the apparent skin s' = s + D*q is a defect.
- PRESSURE-DEPENDENT PERMEABILITY. The paper assumes k is not a function of p (Klinkenberg negligible at reservoir pressures). In tight/shale or stress-sensitive rock this fails. The fix (their Eq. 36) puts k(p) inside the integral, which makes the resulting m'(p) rock-specific and no longer a pure fluid property.
- ADSORBED GAS. In shale/coal the total compressibility and the gas in place are not the conventional free-gas values; every pseudotime formulation that uses c_t and a material balance to get pbar is then built on the wrong c_t.
- USING TABLE 1 OUTSIDE ITS FILLED CELLS. The low-T_pr columns are truncated. Extrapolating the T_pr=1.05 column past p_pr=5.00 has no support in the source.

## Numerical pitfalls

- MAGNITUDE / ROUNDOFF FLOOR. m(p) is O(1e8-1e9) psia^2/cp. In IEEE double the relative resolution is ~2.2e-16, so absolute noise is ~1e-7 at 1e9. I measured composite Simpson's error bottom out at ~7e-5 absolute on a reference value of 3.4838638079e9 (~2e-14 relative) around n = 2048, after which the apparent order goes negative. Any convergence test that refines past that point will report nonsense orders (I observed -0.26 at n = 8192).
- ORDER TEST WINDOW. The clean order-4 window on my smooth test integrand over [14.7, 8000] psia was roughly n = 128 to 512 (observed 3.96, 3.98, 3.80-4.12). At n = 8 to 64 the pre-asymptotic terms still contaminate it (I observed 4.09, 3.00, 3.83 - the 3.00 is not a real order-3 regime, it is two error terms crossing). Report the window, not a single ratio.
- TABLE INTERPOLATION CAPS THE ORDER. This is the pitfall most likely to bite. With mu and Z linearly interpolated from a 200-psi PVT table, the integrand is only C0 and composite Simpson degrades to observed order ~2 (I measured 1.98, 1.89, 2.01 at n = 1024, 2048, 4096), against ~4 for the same integrand evaluated analytically. If the production path uses interpolated tables, you have an order-2 method no matter what your Simpson unit test says. Fix by using an analytic correlation, or by aligning panel boundaries with table nodes, or by using a C2 monotone interpolant and accepting the reduced but higher order.
- LOOSE INNER SOLVER TOLERANCE. An implicit Z correlation with a Newton solve converged to only 1e-6 makes f(p) effectively noisy at the 1e-6 level. Adaptive quadrature will then either stall, return a wildly optimistic error estimate, or subdivide forever chasing noise.
- LOWER LIMIT AT p = 0. The integrand 2p/(mu Z) -> 0 as p -> 0 (mu tends to a finite one-atmosphere value, Z -> 1), so there is no singularity. But most Z and mu correlations are not fitted down to p = 0 and may return garbage or fail to converge there. If you adopt p_ref = 0 (as Ahmed's example does), guard the first panel explicitly.
- THE INTEGRAL IS TOP-HEAVY. m(p) grows roughly like p^2, so almost all of the value comes from the highest-pressure panels. A uniform grid wastes effort at low p and under-resolves nothing - but it also means that a relative-error tolerance on the WHOLE integral can hide a large relative error on a low-pressure sub-interval. If you need accurate small drawdowns at low p, set the tolerance on that interval, not on the cumulative value.
- NEAR-CRITICAL NON-SMOOTHNESS. The paper's Fig. 1 shows a pronounced local maximum in p_pr/[(mu/mu_1) Z] near p_pr ~ 1.3 on the T_pr = 1.05 isotherm. Fixed-panel Simpson straddling that feature will under-resolve it silently. Adaptive quadrature handles it; a fixed grid needs a node placed near the feature.
- GAUSS-LEGENDRE IS NOT AN h-METHOD. Do not run an h-refinement order test on a fixed-interval Gauss-Legendre rule and report 'order 2n'. Its convergence for an analytic integrand is geometric in n, not algebraic in h. Test it by increasing n and watching the error fall on a log-linear plot, or by composite Gauss-Legendre with fixed n per panel (which IS order 2n in h).
- ODD NUMBER OF PANELS IN COMPOSITE SIMPSON. Composite Simpson needs an EVEN number of subintervals. A 12-row PVT table has 11 intervals; a naive loop silently drops the last interval. I hit exactly this bug while cross-checking Ahmed's table and it produced a 51% error that looked like a physics failure. Assert n is even, or fall back to a 3/8 panel for the odd tail.
- REPORTING RELATIVE ERROR AGAINST A NEAR-ZERO DIFFERENCE. For a tiny drawdown, delta_m is small while m itself is huge. Always report the error of delta_m relative to delta_m, never relative to m.

## Implementation notes

- Store the datum with the table. Make p_ref an explicit, required, immutable field of whatever object holds the m(p) curve, and make the difference operator assert the two operands share it. This one guard kills the most common class of pseudopressure bug.
- For a DIFFERENCE, integrate the interval directly. Compute delta_m = 2*int_{p_wf}^{p_i} p/(mu Z) dp rather than m(p_i) - m(p_wf). Same mathematics, far better conditioning, and it makes the datum irrelevant by construction.
- Build the cumulative table by accumulating panel-by-panel with the SAME rule you would use for a single interval, so that m(p_k) - m(p_j) equals the direct integral over [p_j, p_k] to roundoff. Mixing a cumulative trapezoid table with a direct Simpson interval integral gives two answers that differ by percent-level amounts, and someone will eventually compare them.
- Assert monotonicity. For p > 0 the integrand 2p/(mu Z) is strictly positive, so m(p) must be strictly increasing. A cheap invariant that catches sign errors, bad Z roots (the DAK density solve picking a wrong branch), and table-ordering bugs.
- Use a monotone interpolant for the inverse map m -> p. Analysis workflows invert m(p_wf) back to p_wf (the retrieved Example 6-9 does exactly this). A cubic spline can overshoot and produce a non-monotone inverse; PCHIP or monotone Hermite is the safe choice, and it is implementable dependency-free in ~40 lines.
- Recommended quadrature policy: (a) adaptive Gauss-Kronrod as the default general-case engine, since it handles the near-critical hump and tight tolerances without the caller choosing a grid; (b) composite Simpson as the reference/teaching path and for the convergence test; (c) a closed-form fast path when mu and Z are literally constant, so the constant-mu-Z oracle returns exactly. Dependency-free adaptive GK is a few hundred lines with hard-coded 10/21 nodes; if that is too much, adaptive Simpson with an error-doubling bisection criterion is an honest fallback and still passes the order test.
- Prefer integrating in p, not in p^2 or in reduced variables, unless you have a reason. The p-space integrand is smooth and monotone-ish; substitutions mostly move the problem around.
- Feed the quadrature ANALYTIC correlations (e.g. Dranchuk-Abou-Kassem for Z, Lee-Gonzalez-Eakin for mu), not interpolated tables, whenever the goal is high accuracy or a demonstrated convergence order. Get the coefficients from a separate, separately-verified evidence card; do not transcribe them from memory.
- If Z comes from an implicit correlation (DAK solves for reduced density by Newton), converge that inner solve to ~1e-12 relative or tighter. A loose inner tolerance injects a non-smooth O(tol) perturbation into f(p) that destroys the observed convergence order and floors adaptive quadrature well above its requested tolerance. This is the single most common reason a correct integrator 'fails' the order test.
- Write the convergence test as a TEST, not a comment. Assert that p_obs lands in [3.7, 4.3] over a stated window of n (I observed 3.98 to 4.12 for n = 128 to 512 on a smooth synthetic integrand over 14.7-8000 psia), and assert separately that the test's reference value is converged. Pin the window; do not let the test walk into the roundoff floor.
- Add the negative control to the same test file: run the identical order test with mu and Z linearly interpolated from a 200-psi table and assert p_obs lands near 2, not 4. I measured 1.89 to 2.01 for n = 1024 to 4096. Without this control, an order-4 pass proves nothing about whether your PRODUCTION path (which probably does use tables) is fourth order - and it almost certainly is not.
- PLUS: the 1966 primary source is fully retrievable and unusually explicit. It gives you the exact equation numbers, the arbitrary-datum statement in the authors' own words, the residual-nonlinearity admission, a 8x40 numerical table you can regression-test against, and a candid discussion of where superposition was and was not validated. You can build this module with almost no reliance on secondary sources.
- MINUS: two of the deliverables have soft spots. The pseudotime side is genuinely unsettled in the literature (three competing reference-pressure conventions, and the Palacio-Blasingame material-balance form in this card is recalled, not retrieved). And the only field-units worked m(p) table I could retrieve (Ahmed Example 6-7) has a chart-digitised psi column that does not reproduce from its own tabulated integrand - see independent_checks. Treat it as a smoke test, not an oracle.
- RECOMMENDATION: implement and test in this order - (1) constant-mu-Z closed form to machine precision, (2) the ideal-gas limit of the paper's Table 1, (3) the 2p/(mu Z) column of Ahmed Example 6-7 to 6 significant figures, (4) the end-to-end Example 6-9 drawdown, (5) the Simpson order-4 test WITH the linear-interpolation order-2 negative control. Only after all five pass should you build pseudotime on top - and when you do, retrieve the Palacio-Blasingame and Anderson-Mattar primaries first rather than coding from this card's recalled form.

## Open uncertainties

- The Palacio-Blasingame material balance pseudotime formula in this card is Unverified — cited source not inspected: SPE-25909-MS is identified below but its text was not obtained. Crossref returns SPE-25909-MS (Palacio & Blasingame, 1993-04-26) with the title field literally marked 'UNAVAILABLE', and I could not obtain the text. The placement of q_g(t) outside the integral and the exact normalisation must be confirmed against the primary before coding.
- The explicit normalised-pseudopressure formula p_pn = (mu_i Z_i / (2 p_i)) * m(p) comes from a secondary encyclopedia aggregation, not from Meunier, Kabir & Wittmann (1987) directly. I verified the paper's existence and metadata (SPE Formation Evaluation 2(04) 629-636, DOI 10.2118/13082-PA) via Crossref but did not retrieve its text. The formula is dimensionally consistent (cp * 1 / psia * psia^2/cp = psia) and matches the paper's stated purpose of preserving pressure units, but the exact reference-condition convention is unconfirmed.
- Agarwal's (1979) exact definition of c_t inside the pseudotime integral is not retrieved. Secondary sources state he used 'a simplified version of the total system compressibility'. Do not assume it equals the modern c_t = c_g S_g + c_w S_w + c_f.
- Fraim & Wattenbarger's (1987, DOI 10.2118/14238-PA) normalised-time definition is metadata-verified only; I did not retrieve the formula.
- I did not retrieve Anderson & Mattar's (JCPT 46(07), 2007, DOI 10.2118/07-07-05) corrected-pseudotime equation; the description of it (average pressure of the region of investigation, based on gas-in-place of the investigated volume) is from secondary summaries.
- The Transactions AIME volume number for the 1966 paper (often cited as Trans. AIME 237) is RECALLED, not verified. Crossref returns only the JPT record. The PDF I retrieved is paginated 30-38, which is NOT the JPT pagination (624-636), so it is a reprint-series scan; I inferred this rather than confirming which reprint volume.
- The coefficient 70.81e-6 in the Region III deliverability equation was read from a garbled PDF text layer and should be independently checked before use.
- The 0.2-0.5% error figure I quote for the p-squared approximation and the 0.17-0.20% for the pressure approximation are measured on ONE retrieved PVT dataset (Anaconda Gas Field, via Donohue & Ertekin 1982 as reproduced by Ahmed) over a handful of pressure pairs. They are evidence that the approximations are good inside their regions, not a general error bound. Do not quote them as such.
- The 2000 psi and 3000 psi region boundaries are conventional engineering thresholds for typical natural gases, not derived constants. Their provenance in the retrieved source is Ahmed citing Golan & Whitson (1986), which I did not retrieve.
- The Gauss-Kronrod degree-of-exactness statement (a Kronrod extension of an n'-point Gauss rule with 2n'+1 total nodes is exact to degree 3n'+1) and the QUADPACK QAGS 10/21-point default come from secondary numerical-library documentation, not from Kronrod (1964) or Piessens et al. (1983) directly.
- Whether Simpson vs Gauss-Kronrod is the right production default depends on how mu and Z are supplied, which is out of this card's scope. If the project ends up using interpolated PVT tables, the whole convergence-order discussion becomes largely academic and panel alignment with table nodes matters more than the rule's formal order.

## Independent check values

| Check | Inputs | Expected | Source | Retrieved or recalled |
|---|---|---|---|---|
| EXACT ORACLE - constant mu and constant Z. The integrand 2p/(mu Z) is a degree-1 polynomial, so composite Simpson with 2 panels (or trapezoid with 1) must be exact to machine precision. | `mu = 0.02 cp, Z = 0.9, p_ref = 14.7 psia, p = 5000 psia` | `m(p) - m(p_ref) = (5000^2 - 14.7^2)/(0.02*0.9) = 1.388876883889e9 psia^2/cp. I computed 2-panel Simpson = 1.388876883889e9, relative error 0.000e+00.` | Direct consequence of Al-Hussainy et al. 1966 Eq. 14 | Derived from the retrieved primary equation and verified numerically by me this session |
| IDEAL-GAS LIMIT of the paper's own Table 1. As T_pr rises and p_pr stays modest, (mu/mu_1) -> 1 and Z -> 1, so the tabulated integral must approach (p_pr^2 - 0.04)/(2 T_pr). This also confirms you have read the table header convention correctly (the 1/T_pr sits inside the tabulated integral). | `Table 1 entries at (T_pr, p_pr)` | `T_pr=2.00, p_pr=1.00: table 0.2397 vs ideal 0.2400 (ratio 0.9988). T_pr=3.00, p_pr=0.50: table 0.0349 vs ideal 0.0350 (0.9971). T_pr=2.50, p_pr=0.50: table 0.0421 vs ideal 0.0420 (1.0024). T_pr=3.00, p_pr=1.00: 0.1580 vs 0.1600 (0.9875). T_pr=3.00, p_pr=3.00: 1.4159 vs 1.4933 (0.9481 - Z deviation now real, as expected). T_pr=1.05, p_pr=1.00: 0.5326 vs 0.4571 (1.1651 - near-critical, mu and Z both well below 1, integrand raised, exactly as the paper's Fig. 1 shows).` | Al-Hussainy, Ramey & Crawford 1966, Table 1 (page 34 of the retrieved scan) | Table values RETRIEVED by reading the scanned page; ideal-gas comparison computed by me this session |
| REGRESSION TABLE - selected verbatim Table 1 values for direct comparison if you implement the reduced-variable form with Standing-Katz Z and Carr et al. viscosity | `Table 1 header: mu_1*m(p)/(2*p_pc^2*T_pr) = integral from 0.2 to p_pr of p_pr dp_pr / [ T_pr * (mu/mu_1)(p_pr) * Z(p_pr) ]` | `T_pr=1.05: p_pr=1.00 -> 0.5326, 2.00 -> 2.3821, 3.00 -> 4.0165, 5.00 -> 6.6368 (column ends). T_pr=1.50: 1.00 -> 0.3246, 2.00 -> 1.3164, 5.00 -> 6.3770, 10.00 -> 16.3205, 15.00 -> 24.9921. T_pr=2.00: 1.00 -> 0.2397, 2.00 -> 0.9653, 5.00 -> 5.3860, 10.00 -> 16.0274, 15.00 -> 27.0862. T_pr=3.00: 1.00 -> 0.1580, 2.00 -> 0.6378, 5.00 -> 3.7865, 10.00 -> 13.2545, 15.00 -> 25.3268.` | Al-Hussainy, Ramey & Crawford 1966, Table 1 | RETRIEVED - read directly from the scanned page of the primary paper |
| HARD ORACLE - the integrand column of a published field-units worked example. Reproduces 2p/(mu_g z) exactly from tabulated mu and z. | `Anaconda Gas Field PVT (p psia, mu_g cp, z): (0, 0.0127, 1.000), (400, 0.01286, 0.937), (800, 0.01390, 0.882), (1200, 0.01530, 0.832), (1600, 0.01680, 0.794), (2000, 0.01840, 0.770), (2400, 0.02010, 0.763), (2800, 0.02170, 0.775), (3200, 0.02340, 0.797), (3600, 0.02500, 0.827), (4000, 0.02660, 0.860), (4400, 0.02831, 0.896)` | `2p/(mu_g z) psia/cp = 0, 66391, 130508, 188537, 239894, 282326, 312983, 332986, 343167, 348247, 349711, 346924. I reproduced ALL TWELVE values to better than 0.001% relative.` | Ahmed, T., 'Reservoir Engineering Handbook', Example 6-7 Step 1; PVT data attributed there to Donohue & Ertekin, 'Gas Well Testing, Theory, Practice & Regulations', IHRDC (1982) | RETRIEVED (full text of the handbook) and verified numerically by me this session |
| CAUTION - the psi column of that SAME published example is chart-digitised and does NOT reproduce from its own tabulated integrand. Honest negative finding; do not use it as an oracle. | `Same Anaconda table; integrate 2p/(mu z) from 0 with trapezoid and with composite Simpson at h=400` | `Book psi (psia^2/cp): 13.2e6, 52.0e6, 113.1e6, 198.0e6, 304.0e6, 422.0e6, 542.4e6, 678.0e6, 816.0e6, 950.0e6, 1089.0e6. My trapezoid on the same table gives 13.28e6, 52.66e6, 116.47e6, 202.15e6, 306.60e6, 425.66e6, 554.85e6, 690.08e6, 828.37e6, 967.96e6, 1107.29e6 - systematically 0.6% to 3.0% HIGH. Composite Simpson is 1.2% to 2.4% high. The book says the areas were obtained 'numerically or graphically' from a plotted curve (its Figure 6-16, after Donohue & Ertekin), so the published psi values are chart-grade, not quadrature of the printed table.` | Ahmed, T., 'Reservoir Engineering Handbook', Example 6-7 Step 3 | RETRIEVED; the discrepancy was found by me this session by recomputing |
| SECOND CAUTION in the same example - an internal inconsistency in the published source. The problem statement gives r_w = 0.3 ft but the printed arithmetic uses ln(1000/0.25). | `k=65 md, h=15 ft, T=600 degR, r_e=1000 ft, r_w=0.3 ft, psi_e=1089e6, psi_w=816e6, q_g = k h (psi_e - psi_w) / (1422 T ln(r_e/r_w))` | `With r_w = 0.3 the answer is 38,459 Mscf/D. The book prints 37,614 Mscf/D, which I reproduced exactly only by substituting r_w = 0.25. Do not use this as a regression target without deciding which r_w you mean.` | Ahmed, T., 'Reservoir Engineering Handbook', Example 6-7 Step 4 | RETRIEVED; inconsistency found by me this session |
| END-TO-END ORACLE - published worked constant-rate gas drawdown in pseudopressure. This exercises the field-unit constants, the dimensionless time, and the inverse m -> p interpolation in one shot. | `Same Anaconda m(p) table; k=65 md, h=15 ft, phi=0.15, T=600 degR, q_g=2000 Mscf/D, r_w=0.3 ft, p_i=4400 psia (m(p_i)=1089e6 psia^2/cp), mu_i=0.02831 cp, c_ti=3e-4 1/psi, t=1.5 hr` | `t_D = 0.000264*65*1.5/(0.15*0.02831*3e-4*0.3^2) = 224,498.6 (book: 224,498.6). m(p_wf) = 1089e6 - (1637*2000*600/(65*15)) * log10(4*224498.6/exp(0.5772)) = 1.0775106e9 psia^2/cp (book: 1077.5e6). Linear interpolation back into the m(p) table between 4000 and 4400 psia gives p_wf = 4366.94 psi (book: 4367 psi). psi_D = 0.5*(ln(224498.6) + 0.8090) = 6.5653 (book: 6.565). ALL FOUR reproduce exactly.` | Ahmed, T., 'Reservoir Engineering Handbook', Example 6-9 (which cites Al-Hussainy et al. 1966 for the solution) | RETRIEVED (full text) and reproduced numerically by me this session |
| CONVERGENCE-ORDER DEMONSTRATION for composite Simpson on a smooth synthetic integrand - the test that PROVES order 4 rather than asserting it | `mu(p) = 0.0125*(1 + 1.1e-4 p + 2.0e-9 p^2) cp, Z(p) = 1 - 2.1e-4 p + 3.0e-8 p^2 + 1.0e-12 p^3, integrand 2p/(mu Z), interval [14.7, 8000] psia, reference = composite Simpson at n = 2^20` | `Error vs n: n=16 -> 2.098e2, n=32 -> 2.624e1, n=64 -> 1.843e0, n=128 -> 1.184e-1, n=256 -> 7.519e-3, n=512 -> 5.417e-4. Observed order log2(e_n/e_2n): 4.09, 3.00, 3.83, 3.96, 3.98, 3.80. Clean order-4 window is n = 64 to 512. Beyond n ~ 1024 the error hits the double-precision floor (~7e-5 absolute on a value of 3.4838638079e9, i.e. ~2e-14 relative) and the observed order collapses to 0.5, then 0.08, then negative.` | Synthetic problem constructed by me; the h^4 error law is NIST DLMF Eq. 3.5.8 | Computed by me this session; the underlying error theorem RETRIEVED from DLMF section 3.5 |
| NEGATIVE CONTROL for the order test - prove the instrument can see the FAILURE case, not just the success case. Linear interpolation of the PVT table must drop the observed order from 4 to 2. | `Same analytic mu(p), Z(p) as above, but sampled onto a 200-psi grid over [0, 8000] and LINEARLY interpolated; same composite Simpson refinement` | `Observed order: n=256 -> 2.20, n=512 -> 2.36, n=1024 -> 1.98, n=2048 -> 1.89, n=4096 -> 2.01. Errors at n=1024/2048/4096: 9.66e-1, 2.61e-1, 6.48e-2 (factor ~4 per halving, i.e. order 2). Compare the analytic case at the same n, where the error is already at the 1e-5 roundoff floor.` | Constructed by me as a positive control on the failure mode | Computed by me this session |
| DATUM-INVARIANCE PROPERTY TEST - cheap and catches the most common bug class | `Any mu(p), Z(p); build m(p) twice with p_ref = 0 and with p_ref = 14.7 psia (or 500 psia)` | `m_A(p) - m_B(p) is the SAME constant for every p (to quadrature error), every difference m(p_a) - m(p_b) is identical between the two tables, and every finite-differenced derivative dm/dp is identical between the two tables. Meanwhile a bare m(p) value differs by that constant.` | Al-Hussainy et al. 1966 ('the lower limit of the integration can be set arbitrarily') plus the fundamental theorem of calculus | Property statement RETRIEVED from the primary paper; the test design is mine |

## Adversarial review

### Corrections

**Region III (pressure-approximation) deliverability coefficient, ANALYTIC ORACLE 4** — severity HIGH, confidence CONFIRMED - derived three ways and matched against a published worked answer

- Claimed: q_g = 70.81e-6 * k*h*(pbar - p_wf) / [(mu_g B_g)|_avg * (ln(re/rw) - 0.75 + s)]  (card flags it as 'needs an independent check' but leaves 70.81e-6 in the equation body)
- Correct: 7.081e-6 (Ahmed prints 7.08(10^-6) in the worked example). Factor of 10 too large in the card.
- Evidence: THREE independent confirmations. (1) Closed-form derivation: B_g = (p_sc/T_sc)(ZT/p)/5.6146 = 0.005035 ZT/p bbl/scf, so 2p/(muZ) = 0.01007*T/(mu*B_g); substituting into the verified 1422 form gives coefficient 2*0.005035/1422 = 7.0815e-6. (2) I downloaded Ahmed's Reservoir Engineering Handbook (irmat-ucan.com PDF, 1463 pp) and extracted the text: Eq. 8-9 renders as '70 81 0 ... 6' in the broken text layer, but the worked Example 8-1 Step 3 renders '7 08 10 ... 6' i.e. 7.08(10^-6) and prints the answer 44,490 Mscf/D. (3) Reproducing that example: 7.08e-6*65*15*800/(0.025*0.000695*(ln(1000/0.25)-0.75-0.4)) = 44,490 Mscf/D exactly; 70.81e-6 gives 400,155 Mscf/D, versus the book's own exact pseudopressure answer of 43,509 Mscf/D (which I also reproduce from 1422). The card's own 'garbled PDF text layer' suspicion was correct; the resolution is a decimal point, and the digit string 7081 matches my derivation exactly.

**Regression table of Al-Hussainy et al. Table 1, T_pr = 1.50 isotherm** — severity HIGH (it is a stated regression target), confidence CONFIRMED - read from the primary scan

- Claimed: T_pr=1.50: p_pr=5.00 -> 6.3770
- Correct: 6.6377
- Evidence: I retrieved the paper scan (ipt.ntnu.no/~curtis/.../Hussainy-theory.pdf), rendered page 34 and read Table 1 directly. Row p_pr=5.00 reads 6.6368 / 6.7235 / 6.9714 / 6.6377 / 6.0234 / 5.3860 / 4.4664 / 3.7865 for T_pr = 1.05/1.15/1.30/1.50/1.75/2.00/2.50/3.00. Digit transposition in the card. Independent confirmation from monotone increments: the T_pr=1.50 column runs 6.1412 (4.75) -> 6.6377 (5.00) -> 7.1355 (5.25), increments 0.4965 and 0.4978; 6.3770 would give increments 0.236 and 0.759, which is not consistent with a smooth integral. Every other Table 1 value the card quotes (0.5326, 2.3821, 4.0165, 6.6368, 0.3246, 1.3164, 16.3205, 24.9921, 0.2397, 0.9653, 5.3860, 16.0274, 27.0862, 0.1580, 0.6378, 3.7865, 13.2545, 25.3268, 0.0421, 0.0349, 1.4159, 11.1935) checks out exactly.

**ANALYTIC ORACLE 2 / independent check 2 - stated tolerance** — severity MEDIUM, confidence CONFIRMED

- Claimed: 'tolerance: within 0.5% for T_pr >= 2.0 and p_pr <= 1.0'
- Correct: ~1.5%. The card's own listed datum violates its own tolerance by 2.5x.
- Evidence: Card lists T_pr=3.00, p_pr=1.00: table 0.1580 vs ideal 0.1600, ratio 0.9875 = 1.25% deviation. That point satisfies T_pr>=2.0 and p_pr<=1.0, so a test coded to the card's tolerance fails on the card's own data. I confirmed 0.1580 against the primary Table 1. Full set at p_pr=1.00 (table/ideal): T_pr=1.05 1.1651, 1.15 1.1095, 1.30 1.0533, 1.50 1.0144, 1.75 1.0073, 2.00 0.99875, 2.50 0.99063, 3.00 0.9875.

**ANALYTIC ORACLE 2 - asserted direction of deviation** — severity MEDIUM, confidence CONFIRMED

- Claimed: 'the deviation should grow smoothly and in the right direction as p_pr rises or T_pr falls'
- Correct: At fixed p_pr the deviation is NON-MONOTONE in T_pr: the table/ideal ratio decreases monotonically with T_pr and crosses unity between T_pr=1.75 and T_pr=2.00, so |deviation| is MINIMUM near T_pr ~ 1.9 and grows in BOTH directions. The closest-to-ideal isotherm at p_pr=1.0 is T_pr=2.00 (0.13%), not the highest T_pr.
- Evidence: Computed from the retrieved Table 1 ratios above: 1.1651, 1.1095, 1.0533, 1.0144, 1.0073, 0.99875, 0.99063, 0.9875 for T_pr = 1.05..3.00. Physically: below T_pr~1.9 the Z<1 effect dominates (integrand raised, ratio>1); above it the (mu/mu_1)>1 and Z>1 effects dominate (ratio<1). The card's own listed T_pr=2.50/p_pr=0.50 ratio of 1.0024 and T_pr=3.00/p_pr=0.50 ratio of 0.9971 already straddle unity, contradicting the monotone claim inside the card itself.

**NEGATIVE CONTROL for the convergence-order test (independent check 9)** — severity MEDIUM-HIGH as a test-design defect — coded as written it is a flaky test, confidence CONFIRMED (success case reproduced exactly; failure case not reproducible)

- Claimed: Linear interpolation of a 200-psi PVT table 'caps the observed order at 2'; asserts p_obs in [1.7, 2.3] for n in [1024, 4096], with errors 9.66e-1, 2.61e-1, 6.48e-2
- Correct: Not reproducible. With the card's own mu(p), Z(p), a 200-psi grid and composite Simpson on [14.7, 8000], the observed order is erratic, not 2. Restate the control as an error-MAGNITUDE and BIAS control, not an order control.
- Evidence: I re-ran the card's exact analytic setup and reproduced its success case to the digit (reference 3.4838638079e9; errors 2.0980e2, 2.6237e1, 1.8428e0, 1.1841e-1, 7.5188e-3, 5.4169e-4; orders 3.00, 3.83, 3.96, 3.98, 3.79; floor ~7e-5 by n=4096 with order collapsing to -0.26 at n=8192). The negative control does not reproduce. Against a properly aligned exact reference (60-point Gauss-Legendre on each smooth 200-psi sub-piece = 3.4826667462e9) I get errors 5.2645e-1 (n=1024), 7.3523e-2 (2048), 1.1533e-1 (4096), 7.4428e-2 (8192), 5.6968e-3 (16384) and observed orders 4.25, 2.84, -0.65, 0.63, 3.71. Theory agrees with the erratic behaviour: a fixed number of derivative kinks (44) gives a per-kink-panel error whose constant depends on where the kink falls relative to a node/midpoint, so there is no clean asymptotic h-power. The card's clean 1.98/1.89/2.01 is not a stable property of the setup it specifies.

**p-squared average-pressure convention (ANALYTIC ORACLE 3, validity_ranges)** — severity MEDIUM, confidence CONFIRMED

- Claimed: p_avg = sqrt((pbar^2 + p_wf^2)/2), presented as THE convention for the p-squared method
- Correct: Correct for Ahmed Chapter 8 (Eq. 8-11), but Ahmed Chapter 6 (Eq. 6-45, Example 6-8) uses the ARITHMETIC mean for the same method. The card missed this second internal inconsistency in its own primary field-unit source.
- Evidence: Retrieved Ahmed text. Ch. 8 Example 8-1b: pbar=2000, pwf=1200 -> p_avg printed as 1649, and sqrt((2000^2+1200^2)/2) = 1649.24 (arithmetic mean would be 1600). Ch. 6 Example 6-8: pe=4400, pwf=3600 -> p_avg printed as 4020, i.e. (4400+3600)/2 (sqrt-mean-square would be 4024.9). My numerics on the Anaconda table confirm sqrt-mean-square is the right one: for the 2000->400 pair the p-squared estimate errs -0.24% with sqrt-mean-square versus +2.65% with the arithmetic mean.

**Quoted error magnitudes for the Region I and Region III approximations** — severity LOW-MEDIUM (the card does warn against generalising, but the numbers themselves should not be asserted to 2 significant figures), confidence CONFIRMED

- Claimed: '-0.17% to -0.50%' (p-squared, Region I) and '+0.17% to +0.20%' (pressure, Region III), presented as measured on retrieved PVT
- Correct: These are REFERENCE-METHOD artifacts, not error magnitudes of the approximation. They only reproduce if the 'true' value is 3-point Simpson on the printed integrand nodes; against a finer reference they roughly double.
- Evidence: With Simpson on the printed 2p/(muZ) nodes as reference I get +0.203% (4400->3600) and +0.173% (4000->3200), matching the card. With a converged reference that interpolates mu and Z linearly between table nodes I get +0.308% and +0.244%. Region I with sqrt-mean-square p_avg against the converged reference: 2000->400 = -0.242%, 2000->800 = -0.116%, 1200->400 = +0.060%, 2000->1200 = -0.001% — the SIGN is not uniformly negative, so the card's '-0.17% to -0.50%' band is wrong in both endpoints and in sign coverage.

**Radial pseudopressure diffusivity equation, Eq. 29 sign** — severity LOW but trap-worthy, confidence CONFIRMED (read from the scan)

- Claimed: radial: d2m/dr2 + (1/r) dm/dr = (phi mu c_g / k) dm/dt (correct form, stated without comment)
- Correct: The form is right, but the PRINTED Eq. 29 in the 1966 scan shows a MINUS sign on the 1/r term. Flag this so an implementer checking the source does not 'correct' the code to match the paper.
- Evidence: Page 35 of the retrieved scan renders Eq. 29 as d2m(p)/dr2 - (1/r) dm(p)/dr = (phi mu(p) c_g(p)/k) dm(p)/dt, while Eq. 28 immediately above (ideal-gas p-squared form) clearly shows a +. The radial Laplacian is unambiguously +1/r d/dr, so the printed minus is a typo or scan artifact in the primary source. The card silently gives the correct sign but does not warn.

**Table 1 dimensions** — severity LOW, confidence CONFIRMED

- Claimed: 'a 8x40 numerical table' (stated twice)
- Correct: 8 columns x 66 rows: p_pr = 0.30-3.00 in 0.10 steps (28), 3.25-5.00 in 0.25 steps (8), 5.25-10.00 in 0.25 steps (20), 10.50-15.00 in 0.50 steps (10).
- Evidence: Counted directly off the retrieved page 34.

**'57895.3 ... reproduced exactly by me this session' and the 1422 vs 1424 note** — severity LOW, confidence CONFIRMED

- Claimed: 57895.3 verified; '1424 ... the difference is the standard-condition convention' (convention not identified)
- Correct: 57,895.3 is present in Ahmed (I located it) but is NOT exact: derived from base conversions it is 57,916.5 (0.037% high). 1424 corresponds to p_sc = 14.73 psia: my derivation gives 1424.83 at 14.73/520 versus 1421.93 at 14.7/520.
- Evidence: First-principles derivation: q_sc[Mscf/D] = 1.98809e-5 * (T_sc/p_sc) * k h dm/(T ln), from 1 darcy = cm^2 cp/(atm s), 1 atm = 14.6959488 psi, 1 ft = 30.48 cm, 1 ft^3 = 28316.846592 cm^3. Gives 1/C = 1421.93 (14.7/520), 1424.83 (14.73/520), 1417.09 (14.65/520), 1453.37 (15.025/520); and semilog slope 1637.1 at 14.7/520. The other card constants ALL check out from first principles: 0.0002637 = (1e-3*3600)/(14.6959488*30.48^2) = 2.63679e-4 (exact); 3.2275 = -log10(4*2.637e-4/e^0.5772); 1637 = 1422*ln(10)/2 = 1637.14; ln(4) - 0.5772 = 0.80909.

**Sourcing of the pseudotime units** — severity LOW, confidence CONFIRMED

- Claimed: 'units and reference-condition statements from IHS WellTest Pseudo-Time reference page retrieved this session'; 'the units of Agarwal's pseudotime (hr*psi/cp)'
- Correct: The IHS/Fekete Harmony pseudo-time page states NO units and serves its three equations as SVG images. The hr*psi/cp units are trivially derivable from the definition and are right, but the attribution is an overclaim.
- Evidence: I fetched https://www.ihsenergy.ca/support/documentation_ca/Harmony/content/html_files/reference_material/general_concepts/pseudo-time.htm this session. It gives the three reference-pressure conventions (wellbore for buildup, average reservoir for drawdown, average over the region of investigation for corrected) — the card is right on that — but explicitly no units and no extractable equations (equation543.svg, equation544.svg, equation545.svg).

**Internal inconsistency in the card's own convergence-order numbers** — severity LOW, confidence CONFIRMED

- Claimed: implementation_notes: 'I observed 3.98 to 4.12 for n = 128 to 512'; independent_checks: '3.96, 3.98, 3.80' for the same window
- Correct: 3.96, 3.98, 3.79 — I reproduce the independent_checks figures. The 4.12 upper figure is unsupported.
- Evidence: Re-ran the card's exact synthetic integrand and interval; orders at n=128/256/512 are 3.96/3.98/3.79.

### Left unverified

- Meunier, Kabir & Wittmann (1987) normalized pseudopressure p_pn = (mu_i Z_i/(2 p_i)) m(p). I located and downloaded the paper PDF from blasingame.engr.tamu.edu but it is a scan with no text layer and I did not OCR it. The card's two written forms are mutually consistent, are dimensionally correct (cp * 1 / psia * psia^2/cp = psia), and imply dp_pn/dp = 1 at p = p_i, which is the standard normalization intent — but the factor and the reference-condition convention remain unconfirmed against the primary. Keep the card's own 'abstract/metadata only' label.
- Agarwal (1979) SPE-8279-MS: the exact pseudotime integrand, and specifically which c_t he used. Not retrieved. The card's own caveat stands.
- Palacio & Blasingame (1993) SPE-25909-MS material-balance pseudotime t_ca: the placement of q_g(t) outside the integral. Card labels it recalled; I could not retrieve it either. DO NOT CODE FROM THE CARD.
- Fraim & Wattenbarger (1987) and Anderson & Mattar (2005/2007) definitions — metadata only in the card, not retrieved by me.
- Fevang & Whitson (1996) SPE-30714: the card claims 'full-text retrieved' but I did not retrieve it. The a1 = 1/(2*pi*141.2) = 1.1272e-3 value is consistent with the standard field Darcy constant 0.001127, and the integrand is dimensionally coherent, but the 'blockage severity depends on k_rg/k_ro only in 1 < k_rg/k_ro < 50' claim and the three-region description are unverified by me.
- Golan & Whitson (1986) as the authority for 'mu_g*z essentially constant below 2000 psi'. I confirmed Ahmed CITES them for it (retrieved text, Chapter 8, Region I) but did not retrieve Golan & Whitson. Note also that this statement is false on Ahmed's own Anaconda table: mu*Z rises 17.58% from 400 to 2000 psi. What actually makes Region I work is error cancellation from the sqrt-mean-square p_avg, not constancy of mu*Z.
- Donohue & Ertekin (1982) as the provenance of the Anaconda psi column. Not retrieved. The card's negative finding (the published psi values do not reproduce from the printed integrand) is plausible and the book does say the areas were obtained 'numerically or graphically' from Figure 6-16, which I confirmed in the retrieved text.
- Trans. AIME volume number for the 1966 paper. Still unverified; my retrieved scan is also paginated 30-38, consistent with the card's reprint-series inference.
- Al-Hussainy et al. Table 1's underlying Z and viscosity correlations. The paper says Standing & Katz for z and Carr et al. for mu/mu_1 (I read this on page 32-33), and that the integrals were done by trapezoidal rule on an IBM 709 (page 33) — so the ~1% tolerance the card recommends is justified, but the actual reproduction accuracy against a modern DAK/LGE implementation is untested.
- The Gauss-Kronrod degree-of-exactness (3n'+1) and the QUADPACK QAGS 10/21 default. Standard and almost certainly right, but I did not verify against Kronrod (1964) or Piessens et al. (1983) either.

### Missing before implementation

- A statement that normalized pseudopressure does NOT satisfy p_pn(p_i) = p_i. The normalization sets the SLOPE to unity at p_i (dp_pn/dp|_{p_i} = 1), not the value; for constant mu,Z it gives p_pn(p_i) = p_i/2. An implementer will otherwise 'fix' a correct implementation.
- Units of q_g in the Fevang-Whitson equation. With a1 = 0.001127, B_g in bbl/scf and B_o in bbl/STB, the integral yields scf/D, not Mscf/D. The card gives no unit for q_g there.
- A standard-conditions constant table so the implementer can choose and document: p_sc = 14.7 psia, T_sc = 520 degR -> 1421.93 / 1637.1; p_sc = 14.73 psia -> 1424.83 / 1640.4; p_sc = 14.65 psia -> 1417.09 / 1631.5; p_sc = 15.025 psia -> 1453.37 / 1673.2. The card names 1422 and 1424 without identifying which convention gives which.
- How to obtain dZ/dp for c_g = 1/p - (1/Z)dZ/dp. Analytic differentiation of the Z correlation versus central difference changes the smoothness of c_g and therefore the pseudotime integrand. Nothing in the card specifies this, and the card correctly warns about loose inner-solver tolerance but not about this.
- Behaviour when the PVT table's lowest tabulated pressure is above the chosen datum p_ref (very common). The card covers p_ref = 0 but not this case.
- The identity that closes the three Ahmed deliverability forms: 2p/(mu Z) = 0.01007 * T / (mu * B_g) with B_g = 0.005035 * Z * T / p bbl/scf. Without it the implementer cannot check the p-squared, pressure and pseudopressure paths against each other, and cannot catch the 70.81e-6 error.
- Ahmed Example 8-1 (both parts) is a better field-unit oracle than Example 6-7 and is absent from the card. It pins the corrected 7.081e-6, the sqrt-mean-square p_avg, and the 1422 path in one place, with three published answers.
- Guidance on gas-condensate q_sc: the card says Region 3 is where 'ordinary m(p) IS valid' but does not say the implementer must detect the dewpoint, so a single-phase m(p) module has no gate.

### Recommended independent test oracles

**Unit-conversion identity suite (recompute the four field constants, never hard-code)**

- Inputs: `Base conversions only: 1 atm = 14.6959488 psi, 1 ft = 30.48 cm, 1 ft^3 = 28316.846592 cm^3, 1 bbl = 5.614583 ft^3, gamma = exp(0.5772). Standard conditions p_sc = 14.7 psia, T_sc = 520 degR.`
- Expected: `t_D constant = (1e-3*3600)/(14.6959488*30.48^2) = 2.63679e-4 (round to 0.0002637). q_sc coefficient = pi*(1e-3)*(30.48)/(14.6959488) * 86400/28316.846592/1000 = 1.98809e-5, so 1/(1.98809e-5 * 520/14.7) = 1421.93 -> 1422. Semilog slope = 1422*ln(10)/2 = 1637.14 -> 1637. Intercept = -log10(4*2.637e-4/exp(0.5772)) = 3.2275 -> 3.23. Also ln(4) - 0.5772 = 0.80909. Also B_g coefficient = (14.7/520)/5.614583 = 0.005035 bbl/scf per (ZT/p). Also the Region III coefficient = 2*0.005035/1422 = 7.0815e-6.`
- Why independent: Derived from SI/definitional conversion factors alone with no reference to any reservoir-engineering text, so it cannot inherit a typo from Ahmed's PDF. It is exactly the instrument that catches the card's 70.81e-6 error, the 1422/1424 convention ambiguity, and the 0.000264/0.0002637 split. It also checks that the implementation's constants are internally consistent with each other (1637 = 1422*ln10/2 is a hard identity, not a coincidence).

**Ahmed Example 8-1 — three published answers on one dataset (NEW; replaces the card's chart-digitised Example 6-7 smoke test)**

- Inputs: `k = 65 md, h = 15 ft, T = 600 degR, r_e = 1000 ft, r_w = 0.25 ft, s = -0.4 (NOTE: the book's problem statement renders as 's = 0.4' in the PDF text layer but only s = -0.4 reproduces the printed arithmetic — the minus is lost in extraction). Anaconda PVT with psi and B_g columns. (a) pbar = 4000, p_wf = 3200 psi, mu_g = 0.025 cp, B_g = 0.000695 bbl/scf at p_avg = 3600 = (4000+3200)/2. (b) pbar = 2000, p_wf = 1200 psi, mu_g = 0.017 cp, z = 0.791 at p_avg = 1649 = sqrt((2000^2+1200^2)/2).`
- Expected: `(a) pressure-approximation with 7.08e-6: 44,490 Mscf/D. (a) exact pseudopressure with 1422 and psi = 950.0e6 - 678.0e6: 43,509 Mscf/D. (b) p-squared with 1422: 30,453 Mscf/D. I reproduced all three to within 1 Mscf/D from the retrieved text.`
- Why independent: Published worked answers from a source the implementation does not consult at runtime, and they cross-check three DIFFERENT equation forms against each other on the same PVT. The (a)-pair is the decisive discriminator for the 7.081e-6 vs 70.81e-6 question: 70.81e-6 gives 400,155 Mscf/D against an exact-method 43,509, a 10x disagreement that no tolerance can hide. The (b) p_avg value of 1649 independently pins the sqrt-mean-square convention against the arithmetic mean (which would give 1600).

**Compressibility-derivative identity (tests c_g against Z with no reference to m(p))**

- Inputs: `Any Z(p) correlation and any p in the working range; c_g(p) computed as 1/p - (1/Z)dZ/dp.`
- Expected: `d/dp [ p/Z(p) ] must equal (p/Z(p)) * c_g(p) to machine precision (relative error < 1e-10 with an analytic dZ/dp, < 1e-6 with a well-scaled central difference). Corollary that must also hold: the pseudopressure PDE closes exactly — (1/2) grad^2 m = (phi/k) d(p/Z)/dt implies grad^2 m = (phi mu c_g / k) dm/dt with the factors of 2 cancelling identically, because d(p/Z)/dp * dp/dt = (p/Z) c_g * (mu Z/(2p)) dm/dt = (mu c_g / 2) dm/dt.`
- Why independent: A pure calculus identity between two separately-coded quantities (the Z correlation and the c_g function). It never touches the quadrature, the datum, or any published constant, so a failure localises unambiguously to the c_g implementation. It is also the numerical form of the derivation that proves the card's central claim (Eq. 7 -> Eq. 18 with no small-gradient assumption), so passing it validates the physics claim, not just the code.

**Cross-form closure: 2p/(mu Z) == 0.01007 * T / (mu * B_g)**

- Inputs: `Ahmed's own printed B_g column for the Anaconda table at T = 600 degR: p = 400 -> Z = 0.937, B_g = 0.007080; p = 3600 -> Z = 0.827, B_g = 0.000695; p = 4000 -> Z = 0.860, B_g = 0.000650.`
- Expected: `B_g = 0.005035 * Z * T / p reproduces the printed column to the book's 3 significant figures (0.005035*0.937*600/400 = 0.007078 vs 0.007080; 0.005035*0.827*600/3600 = 0.000694 vs 0.000695). Then 2p/(mu Z) and 0.01007*T/(mu*B_g) must agree to the same precision at every row.`
- Why independent: It is a dimensional identity linking two independently tabulated columns in a published source, with the implementation contributing only arithmetic. It closes the loop between the pseudopressure form (1422), the p-squared form (1422) and the pressure form (7.081e-6), so any one of the three being wrong shows up here rather than as a plausible-looking deliverability number.

**Al-Hussainy Table 1 regression, CORRECTED**

- Inputs: `Reduced-variable pseudopressure integral with the paper's own header convention, verified against the retrieved page 34 and against the Fig. 2 ordinate label: mu_1*m(p)/[2*(p_pc)^2*T_pr] = integral from 0.2 to p_pr of p_pr dp_pr / [T_pr * (mu/mu_1)(p_pr) * Z(p_pr)]. Lower limit (p_pr)_m = 0.20 (the paper: 'The lower limit of the integration (p_pr)_m can be set arbitrarily. A value of 0.20 was chosen'). Isotherms T_pr = 1.05, 1.15, 1.30, 1.50, 1.75, 2.00, 2.50, 3.00; 66 rows, p_pr = 0.30 to 15.00.`
- Expected: `T_pr=1.05: 1.00 -> 0.5326, 2.00 -> 2.3821, 3.00 -> 4.0165, 5.00 -> 6.6368 (column ends; dashes from 5.25). T_pr=1.15 ends at 8.50 -> 11.1935. T_pr=1.50: 1.00 -> 0.3246, 2.00 -> 1.3164, 5.00 -> 6.6377 (CORRECTED from the card's 6.3770), 10.00 -> 16.3205, 15.00 -> 24.9921. T_pr=2.00: 1.00 -> 0.2397, 2.00 -> 0.9653, 5.00 -> 5.3860, 10.00 -> 16.0274, 15.00 -> 27.0862. T_pr=3.00: 1.00 -> 0.1580, 2.00 -> 0.6378, 5.00 -> 3.7865, 10.00 -> 13.2545, 15.00 -> 25.3268. Tolerance ~1%; the table was produced by trapezoidal rule on an IBM 709 (stated on page 33) and rests on Standing-Katz z and Carr et al. mu.`
- Why independent: Computed in 1966 by different people, a different quadrature rule and different property charts from anything the implementation will use. But state the failure mode honestly: a miss is unattributable between the Z correlation, the viscosity correlation and the quadrature, so run it AFTER the constant-mu-Z oracle and the derivative-identity test, never as the first line of defence.

**Ideal-gas limit of Table 1, with corrected tolerance and no monotonicity assertion**

- Inputs: `Table 1 entries; ideal limit = (p_pr^2 - 0.04)/(2*T_pr).`
- Expected: `Assert |table/ideal - 1| < 1.5% for T_pr in [2.00, 3.00] and p_pr <= 1.00 (measured: 0.13% at T_pr=2.00, 0.94% at 2.50, 1.25% at 3.00 for p_pr=1.00). Assert the ratio is MONOTONE DECREASING in T_pr at fixed p_pr and crosses 1.0 between T_pr=1.75 and 2.00. Do NOT assert that deviation grows as T_pr falls — it does not above T_pr ~ 1.9. Also do not tighten the tolerance at p_pr = 0.30-0.40, where the table's 4-decimal printing gives ~0.4% quantisation on its own.`
- Why independent: The limit is derived from the paper's own printed integral definition (I read the Fig. 2 ordinate label directly and it matches the card's header convention exactly), while the comparison values come from the 1966 numerical run. It independently validates that the implementer has the 1/T_pr inside the integral, which is the one convention error that would silently rescale every reduced-variable result.

**Normalized-pseudopressure slope test**

- Inputs: `Any mu(p), Z(p); p_pn(p) = (mu_i * Z_i / (2 * p_i)) * m(p) with m from the implementation.`
- Expected: `d p_pn / dp evaluated at p = p_i equals 1.000000 to quadrature precision, for every choice of mu and Z correlation and every datum. For constant mu and Z it must further give p_pn(p) = p^2/(2*p_i) exactly, hence p_pn(p_i) = p_i/2 — NOT p_i.`
- Why independent: A property test that follows from the definition and the fundamental theorem of calculus alone, independent of the numerical value of m(p), of the datum, and of the (still unverified) Meunier reference-condition convention. It is also the cheapest way to catch the factor-of-2 in the normalization, and it documents the p_pn(p_i) != p_i surprise in executable form.

**Quadrature-fidelity controls, replacing the card's flaky order-2 negative control**

- Inputs: `Card's synthetic integrand: mu(p) = 0.0125*(1 + 1.1e-4 p + 2.0e-9 p^2), Z(p) = 1 - 2.1e-4 p + 3.0e-8 p^2 + 1.0e-12 p^3, interval [14.7, 8000] psia. Run twice: (A) analytic mu, Z; (B) mu, Z linearly interpolated from a 200-psi grid.`
- Expected: `(A) POSITIVE CONTROL, keep as the card has it: reference 3.4838638079e9; assert p_obs in [3.7, 4.3] for n in [128, 512] (measured 3.96, 3.98, 3.79) and assert the roundoff floor (~7e-5 absolute, ~2e-14 relative) is reached by n = 4096. (B) NEGATIVE CONTROL, RESTATED: assert (i) a BIAS — the interpolated integrand converges to 3.4826667462e9, which differs from the analytic answer by 1.197e6 absolute / 0.0344% relative, and no amount of Simpson refinement removes it; and (ii) an ERROR-MAGNITUDE GAP — at n = 1024 the analytic error is 1.07e-4 while the interpolated error is 5.26e-1, a factor of ~4900. Do NOT assert an observed order for (B): I measured 4.25, 2.84, -0.65, 0.63, 3.71 at n = 1024..16384 against an exact reference (60-point Gauss-Legendre on each smooth 200-psi sub-piece).`
- Why independent: (A) tests the quadrature against Richardson's theory, which is independent of the integrand's physical meaning. (B) as restated tests a quantity that IS a stable property of table interpolation — a systematic bias with a fixed sign and magnitude, set by the interpolant and the grid, not by node alignment — instead of an observed order that is not asymptotic and will flap between CI runs. It still delivers the card's real message (an interpolated PVT path is not a fourth-order path) but in a form that will not produce phantom failures.

**Datum invariance and difference conditioning**

- Inputs: `Build m(p) twice, p_ref = 0 and p_ref = 500 psia, on the same mu, Z. Then compute a small drawdown two ways: as m(p_i) - m(p_wf) with p_i = 4400, p_wf = 4395 psia, and as the direct integral 2*int_{4395}^{4400} p/(mu Z) dp.`
- Expected: `m_A(p) - m_B(p) is the same constant for all p to quadrature tolerance; every difference and every finite-differenced derivative is identical between the two tables; a bare m value is not. The two routes to the 5-psi drawdown must agree to within the direct-integral tolerance, and the differencing route must be measurably worse-conditioned (m ~ 1e9, so differencing leaves ~2e-7 absolute resolution, against a delta_m of ~1.7e6 — assert the direct route's error relative to DELTA_m, never relative to m).`
- Why independent: Pure algebraic properties of the definition (additivity of the integral, and the fundamental theorem of calculus for the derivative part), verified against the paper's own statement that the lower limit can be set arbitrarily. No published number is involved, so it cannot inherit a source error, and it catches the card's top-ranked failure mode (mixed datums) plus the cancellation pitfall in one test.

## Sources

| Citation | Access level | Supports |
|---|---|---|
| Al-Hussainy, R., Ramey, H.J. Jr., and Crawford, P.B., 'The Flow of Real Gases Through Porous Media', Journal of Petroleum Technology, Vol. 18, Issue 05, pp. 624-636, May 1966. SPE-1243-A-PA. DOI 10.2118/1243-A-PA. Manuscript received in SPE office 28 June 1965; revised manuscript of SPE 1243A received 18 Feb 1966; paper presented at the SPE Annual Fall Meeting, Denver, Colorado, 3-6 October 1965. | full-text retrieved | THE primary source. Eq. 14 (the m(p) definition and its factor of 2), the 'low base pressure' arbitrary-datum statement, the psia^2/cp dimensions, Eq. 7 (the rigorous PDE that m(p) acts on), Eqs. 17-18 and 29 (what m(p) linearises and the explicit admission that it remains nonlinear), Eq. 13 (the p-squared equation and the assumptions m(p) removes), Eq. 20 (mass flux, showing the matching 1/2), Eq. 27 and Table 1 and Figs. 1-2 (the reduced-variable form with the arbitrary 0.20 lower limit and the 8x40 numerical table), Eqs. 30-31 (t_D and m_D), Figs. 3-5 (how good and how bad the liquid analogy is), Eq. 32 and Fig. 6 (drainage radius, 0.472 r_e), Eq. 34 (material balance), Eq. 36 (k(p) inside the integral), Eq. 37 (non-Darcy D*q term outside m(p)), and the pages 36-38 discussion of superposition for increasing vs decreasing rate schedules with wellbore storage. DOI and year confirmed independently against the Crossref record. |
| Crossref REST API record for DOI 10.2118/1243-A-PA | full-text retrieved | Independent confirmation of the DOI, title, all three authors, Journal of Petroleum Technology, volume 18, issue 05, pages 624-636, published-print 1966-05-01, publisher Society of Petroleum Engineers. Resolves the 'publication year vs archival year' question together with the paper's own footnote: CONFERENCE PAPER SPE 1243-A presented October 1965, JOURNAL ARTICLE published May 1966. Cite 1966. |
| Al-Hussainy, R. and Ramey, H.J. Jr., 'Application of Real Gas Flow Theory to Well Testing and Deliverability Forecasting', Journal of Petroleum Technology, Vol. 18, pp. 637-642, May 1966. DOI 10.2118/1243-B-PA. | abstract/metadata only | The companion applications paper published immediately after the theory paper in the same JPT issue. Worth retrieving if the project needs the authors' own deliverability and well-testing worked procedures. Metadata (title, authors, journal, volume, pages 637-642, 1966-05-01) confirmed via Crossref. |
| Ahmed, T., 'Reservoir Engineering Handbook', Gulf Professional Publishing. Chapter 6 'Fundamentals of Reservoir Fluid Flow' (Eq. 6-39 pseudopressure definition, Example 6-7 Anaconda Gas Field, Eqs. 6-107 to 6-109 and Example 6-9 constant-rate drawdown, Eq. 6-75 diffusivity constant) and Chapter 8 'Gas Well Performance' (Regions I/II/III, Eqs. 8-8 to 8-14). | full-text retrieved | Field-unit constants 1637, 1422, 57895.3, 0.0002637/0.000264, 3.23; the three-region pressure thresholds (<2000 psi, 2000-3000 psi, >3000 psi) and the physical reasons for each; two worked numerical examples (6-7 and 6-9) used as independent checks. SECONDARY relative to the 1966 primary for the theory, but it is the source actually retrieved for the field-unit coefficients and the approximation regions. Note two internal inconsistencies I found and flagged: the r_w = 0.3 vs 0.25 discrepancy in Example 6-7, and 0.000264 vs 0.0002637 for the diffusivity constant in different chapters. |
| Donohue, D.A.T. and Ertekin, T., 'Gas Well Testing, Theory, Practice & Regulations', IHRDC Corporation (1982). | secondary source | Original source of the Anaconda Gas Field PVT table (p, mu_g, z) and the psi curve used in Ahmed's Example 6-7. Cited by Ahmed; NOT retrieved by me. If the psi column matters as a regression target, retrieve this and check whether the values are tabulated or only plotted. |
| Golan, M. and Whitson, C.H., 'Well Performance' (1986). | secondary source | Cited by Ahmed as the authority for 'the product (mu_g z) is essentially constant when evaluating any pressure below 2,000 psi', which is the physical basis of the p-squared approximation's Region I limit. NOT retrieved by me. |
| Agarwal, R.G., "'Real Gas Pseudo-Time' - A New Function For Pressure Buildup Analysis Of MHF Gas Wells", SPE-8279-MS, SPE Annual Technical Conference and Exhibition, Las Vegas, Nevada, 23-26 September 1979. DOI 10.2118/8279-MS. | abstract/metadata only | The origin of real gas pseudotime t_a(p), motivated specifically by long-duration wellbore-storage distortion in low-permeability (MHF) gas wells. Metadata confirmed via Crossref (author Agarwal, 1979-09-23). The equation form and the wellbore-pressure reference convention come from secondary vendor documentation, not from this paper directly. |
| IHS Markit / Fekete 'Harmony' and 'WellTest' reference material: 'Pseudo-Time' and 'Pseudo-Pressure' pages. | secondary source | Retrieved this session. Supplies: the units of Agarwal's pseudotime (hr*psi/cp) and the normalisation by mu_gi*c_ti to recover hours; the three reference-pressure conventions (wellbore for buildup, average reservoir for drawdown, average of the region of investigation for corrected); and the key honest statement that 'the concept of pseudo-time is not amenable to a completely rigorous solution, as is the case for pseudo-pressure, because the gas properties change with pressure, not time.' Vendor documentation - use as a cross-check, not as an authority for a derivation. Its equations are served as images, so no formula was extractable. |
| Fraim, M.L. and Wattenbarger, R.A., 'Gas Reservoir Decline-Curve Analysis Using Type Curves With Real Gas Pseudopressure and Normalized Time', SPE Formation Evaluation, Vol. 2, Issue 04, pp. 671-682, December 1987. DOI 10.2118/14238-PA. | abstract/metadata only | Normalised time for gas decline-curve analysis with mu and c evaluated at average reservoir pressure. Metadata confirmed via Crossref. Formula NOT retrieved. |
| Meunier, D.F., Kabir, C.S., and Wittmann, M.J., 'Gas Well Test Analysis: Use of Normalized Pseudovariables', SPE Formation Evaluation, Vol. 2, Issue 04, pp. 629-636, December 1987. DOI 10.2118/13082-PA. (Earlier as SPE-13082-MS, SPE ATCE 1984.) | abstract/metadata only | The normalised pseudovariables that retain the units of pressure and time, so liquid-case equations and type curves apply unmodified and the engineer keeps physical feel. Metadata confirmed via Crossref. The explicit (mu Z / 2p)_i * m(p) formula given in this card comes from a secondary aggregation, not from this paper directly. |
| Palacio, J.C. and Blasingame, T.A., 'Decline-Curve Analysis With Type Curves - Analysis of Gas Well Production Data', SPE-25909-MS, 1993. DOI 10.2118/25909-MS. | Unverified — cited source not inspected (not retrieved) | Material balance pseudotime t_ca and the rate-normalised-pseudopressure vs t_ca plot whose pseudosteady-state slope gives contacted pore volume. The Crossref record exists but its title field is literally marked 'UNAVAILABLE' and I could not obtain the text. The formula in this card is RECALLED and must be verified before implementation. |
| Anderson, D.M. and Mattar, L., 'An Improved Pseudo-Time for Gas Reservoirs With Significant Transient Flow', Journal of Canadian Petroleum Technology, Vol. 46, July 2007. DOI 10.2118/07-07-05. (Earlier as Canadian International Petroleum Conference 2005, DOI 10.2118/2005-114.) | abstract/metadata only | Corrected pseudotime evaluated at the average pressure of the region of investigation rather than the whole-reservoir average, which they report matches numerical simulation better during transient and transitional flow. Metadata confirmed via Crossref; content from secondary summaries only. |
| Agarwal, R.G., Al-Hussainy, R., and Ramey, H.J. Jr., 'An Investigation of Wellbore Storage and Skin Effect in Unsteady Liquid Flow: I. Analytical Treatment', SPE Journal, Vol. 10, Issue 03, pp. 279-290, September 1970. DOI 10.2118/2466-PA. | abstract/metadata only | The canonical analytical treatment of wellbore storage and skin, which is a SEPARATE problem from the pseudopressure transform and is not solved by it. Metadata confirmed via Crossref. |
| Fevang, O. and Whitson, C.H., 'Modeling Gas-Condensate Well Deliverability', SPE Reservoir Engineering, Vol. 11, Issue 04, pp. 221-230, 1996. SPE-30714. DOI 10.2118/30714-PA. | full-text retrieved | What replaces m(p) below the dewpoint: the modified Evinger-Muskat two-phase pseudopressure (their Eqs. 1-3, black-oil form q_g = C * int [ k_ro R_s/(B_o mu_o) + k_rg/(B_g mu_g) ] dp), the three-region flow model (near-well two-phase flow region that causes the deliverability loss, condensate-buildup region where only gas flows with saturations from the CVD curve, and outer single-phase original-gas region where ordinary m(p) IS valid), and their literature review of O'Dell-Miller, Fussell, and Jones-Raghavan. Metadata also confirmed via Crossref. |
| NIST Digital Library of Mathematical Functions, Chapter 3 'Numerical Methods', section 3.5 'Quadrature'. Eq. 3.5.8 (composite Simpson error) and section 3.5(v) / Eq. 3.5.20_1 (Gauss-Legendre degree of exactness). | full-text retrieved | Composite Simpson error E_n(f) = -((b-a)/180) h^4 f''''(xi), a < xi < b, i.e. O(h^4), exact for polynomials of degree <= 3. n-point Gauss-Legendre exact for polynomials of degree <= 2n-1. Standards-body authority for the convergence-order claims. |
| QuadGK.jl documentation, 'Quadrature rules'; GNU Scientific Library Numerical Integration documentation; QUADPACK (Piessens, de Doncker-Kapenga, Uberhuber, Kahaner, 1983). | secondary source | The Kronrod extension of an n'-point Gauss rule adds n'+1 nodes (2n'+1 total) and is exact to degree 3n'+1, which is where the embedded error estimate comes from; QUADPACK's QAGS pairs a 10-point Gauss with a 21-point Kronrod rule and adds adaptive bisection plus epsilon-algorithm extrapolation. Library documentation, used as a cross-check for implementation choices - NOT an authority for a derivation. Kronrod (1964) and the QUADPACK book itself were not retrieved. |
| PetroWiki (SPE), 'Deliverability testing of gas wells'. | secondary source | Cross-check only, via search-result excerpts: 'the pressure-squared form of the equation should be used only for gas reservoirs at low pressures (less than 2,000 psia) and high temperatures'; pseudopressure forms 'are applicable at all pressures and temperatures'; and the advantage that pseudopressure flow coefficients do not change as pressure declines during a pseudosteady-state flow test. The page itself 302-redirected and was not directly retrieved; treat as corroboration of the Ahmed thresholds, not as an independent source. |

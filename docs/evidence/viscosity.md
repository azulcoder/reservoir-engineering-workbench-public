# Evidence card: Gas viscosity and compressibility

> Each card records what an implementer needs, where it came from, and how far it was
> verified. A card is not an authority: it is a statement of evidence with its access
> level attached. Items marked unverified are unverified, and the implementation must
> treat them as such.

**Adversarial review verdict:** `SOUND_WITH_CORRECTIONS`  
**Corrections applied:** 11  
**Items left unverified:** 10

## Summary

The Lee-Gonzalez-Eakin (LGE) coefficients were verified in the 2026-09-13 source review against full text of SPE 75721 (Londono, Archer & Blasingame, TAMU-hosted PDF), which reproduces the original JPT 1966 equations: mu_g = 1e-4 * K * exp(X * rho^Y) with K = (9.379 + 0.01607*M)*T^1.5 / (209.2 + 19.26*M + T), X = 3.448 + 986.4/T + 0.01009*M, Y = 2.447 - 0.2224*X, with T in deg R (absolute), M in lbm/lbmol, rho in g/cm3, mu_g in cp. Note the widely-circulated "rounded" variant (9.4, 0.02, 209, 19, 3.5, 986, 2.4, 0.2) is a DIFFERENT parameter set — do not mix the two; and at least one online wiki prints X0 = 3.488, which is a transcription error (3.448 is correct; the numerical discrimination against 3.488 used the reference extract, and its error statistics are excluded from this release under docs/release/PUBLIC_DATA_POLICY.md). Gas density must be rho[g/cm3] = p*M/(Z*R*T) / 62.427960576 with R = 10.731577 psia*ft3/(lbmol*degR); the original paper prints the conversion as 62.37, which is 0.09% off the exact SI-derived 62.42796 — use the exact value. Isothermal compressibility is c_g = 1/p - (1/Z)(dZ/dp)_T; the DAK analytic route (Mattar-Brar-Aziz 1975) is c_pr = 1/p_pr - (0.27/(Z^2*T_pr)) * D / (1 + (rho_r/Z)*D) with D = (dZ/d rho_r)_Tpr, and c_g = c_pr / p_pc. I verified D analytically by hand-differentiation AND numerically against central finite differences (rel. err ~1e-11), and verified the full c_pr expression against finite-differencing the DAK root solve (rel. err ~1e-11) across T_pr 1.05-3.0, p_pr 0.5-25. Independent physical check: DAK+MBA gives c_g = 1.0958e-3 /psi for methane at 1000 psia, 310.928 K. The reference-derived counterpart, the agreement statistic against it, and the LGE bias band against the reference are excluded from this release under docs/release/PUBLIC_DATA_POLICY.md; they are reproduced locally when the operator supplies the extract.

## Equations

### Lee-Gonzalez-Eakin (1966) gas viscosity

```
mu_g = 1.0e-4 * K * exp( X * rho_g^Y )
```

*Unit system:* oilfield/field (mixed: absolute deg R, lbm/lbmol, but density in g/cm3 - CGS)

| Symbol | Meaning | Units |
|---|---|---|
| `mu_g` | gas dynamic viscosity at p and T | cp (centipoise) |
| `K` | LGE dimensional group (see own equation) | dimensionless as used; the 1e-4 carries the cp scaling |
| `X` | LGE density-exponent prefactor | (g/cm3)^(-Y), effectively dimensionless as used |
| `Y` | LGE density exponent | dimensionless |
| `rho_g` | gas mass density at the SAME p and T | g/cm3 (= g/cc) |

Assumptions:

- rho_g MUST be in g/cm3, not lbm/ft3. Substituting lbm/ft3 gives a viscosity of order 1e7 cp (verified numerically) - a useful unit-error tripwire. The magnitude is quoted to one figure: the mis-called correlation is steep enough that a three-figure value would invert back to the density that produced it.
- The 1e-4 factor is part of the correlation, not a unit conversion; mu_g comes out directly in cp.
- Sweet (non-sour) hydrocarbon gas. CO2 up to 3.2 mol% was in the development set.
- Specific gravity below ~1.0 for the quoted accuracy.

*Source:* Lee, A.L., Gonzalez, M.H., Eakin, B.E., 'The Viscosity of Natural Gases', JPT (Aug. 1966) 997-1000; Trans. AIME 234. Equations reproduced verbatim as Eqs. 4-7 in SPE 75721.  
*Access:* full-text retrieved (SPE 75721 reproduction of the primary equations); primary JPT paper itself: abstract/metadata only

### LGE K coefficient

```
K = (9.379 + 0.01607 * M) * T^1.5 / (209.2 + 19.26 * M + T)
```

*Unit system:* oilfield, ABSOLUTE temperature

| Symbol | Meaning | Units |
|---|---|---|
| `M` | molecular weight of the gas mixture (apparent MW) | lbm/lbmol (numerically equal to g/mol) |
| `T` | ABSOLUTE temperature; T[degR] = T[degF] + 459.67 | deg R |

Assumptions:

- T must be absolute Rankine. Using deg F silently produces garbage, not an error.
- 9.379 and 0.01607 and 209.2 and 19.26 are the ORIGINAL published values (verified full-text in SPE 75721).

*Source:* SPE 75721 Eq. 5, reproducing Lee, Gonzalez & Eakin (1966)  
*Access:* full-text retrieved

### LGE X coefficient

```
X = 3.448 + 986.4 / T + 0.01009 * M
```

*Unit system:* oilfield, ABSOLUTE temperature

| Symbol | Meaning | Units |
|---|---|---|
| `T` | absolute temperature | deg R |
| `M` | gas molecular weight | lbm/lbmol |

Assumptions:

- Leading constant is 3.448, NOT 3.488. nafta.wiki prints 3.488; that is a typo. Discriminated numerically against the reference extract as well; the error statistics are excluded from this release under docs/release/PUBLIC_DATA_POLICY.md.

*Source:* SPE 75721 Eq. 6, reproducing Lee, Gonzalez & Eakin (1966)  
*Access:* full-text retrieved

### LGE Y coefficient

```
Y = 2.447 - 0.2224 * X
```

*Unit system:* dimensionless

| Symbol | Meaning | Units |
|---|---|---|
| `X` | the LGE X coefficient computed above | dimensionless |

Assumptions:

- Y depends on X, so an error in X propagates twice (into the prefactor and into the exponent).

*Source:* SPE 75721 Eq. 7, reproducing Lee, Gonzalez & Eakin (1966)  
*Access:* full-text retrieved

### LGE 'rounded/simplified' variant (DO NOT MIX with the original)

```
K = (9.4 + 0.02*M)*T^1.5/(209 + 19*M + T);  X = 3.5 + 986/T + 0.001*M;  Y = 2.4 - 0.2*X
```

*Unit system:* same units as the original LGE

| Symbol | Meaning | Units |
|---|---|---|
| `M` | gas molecular weight | lbm/lbmol |
| `T` | absolute temperature | deg R |

Assumptions:

- This is the form printed by many secondary sources (e.g. pengtools wiki, many textbooks). Note 0.001*M in X vs 0.01009*M in the original - that is a 10x difference, not a rounding. It is a genuinely different parameterisation.
- If you implement both, expose them as separate named variants ('LGE1966' vs 'LGE_rounded') and never silently substitute one for the other.

*Source:* pengtools wiki 'Lee correlation' (secondary); the 0.001 vs 0.01009 discrepancy is unresolved against a primary source this session  
*Access:* secondary source

### Gas density consistent with LGE (real-gas law, field units)

```
rho_g[lbm/ft3] = p * M / (Z * R * T)   with R = 10.731577 psia*ft3/(lbmol*degR)
```

*Unit system:* oilfield, absolute p and T

| Symbol | Meaning | Units |
|---|---|---|
| `p` | ABSOLUTE pressure | psia (NOT psig) |
| `M` | apparent molecular weight of the gas | lbm/lbmol |
| `Z` | gas compressibility (deviation) factor | dimensionless |
| `R` | universal gas constant in field units | psia*ft3/(lbmol*degR) |
| `T` | ABSOLUTE temperature | deg R |

Assumptions:

- p must be absolute (psia). psig is a classic silent failure in reservoir codes.
- Z must come from the SAME p, T (and same pseudocritical basis) used elsewhere in the calculation.

*Source:* SPE 75721 Eq. 8; R value computed this session from CODATA R = 8.31446261815324 J/(mol*K) with exact SI-to-field factors  
*Access:* full-text retrieved (form); constant re-derived numerically this session

### lbm/ft3 -> g/cm3 conversion for LGE

```
rho_g[g/cm3] = rho_g[lbm/ft3] / 62.427960576144606   (equivalently * 0.016018463373960140)
```

*Unit system:* exact SI-derived

| Symbol | Meaning | Units |
|---|---|---|
| `62.427960576...` | lbm/ft3 per g/cm3; = (1 ft in cm)^3 / (1 lbm in g) = 30.48^3 / 453.59237 | (lbm/ft3)/(g/cm3) |

Assumptions:

- Exact by definition: 1 lbm = 453.59237 g exactly, 1 ft = 30.48 cm exactly. Computed this session: 30.48^3/453.59237 = 62.427960576144606.
- The LGE source paper (and SPE 75721 Eq. 8) prints 62.37, which is 0.093% low. Effect on mu_g is small (~0.014% at methane/1000 psia, computed this session) but the effect on rho and on any Z backed out of rho is 0.09%. Use 62.42796.

*Source:* NIST SP 811 / international yard-and-pound agreement (1959) definitions; arithmetic performed this session  
*Access:* recalled definitions, arithmetic verified this session

### Combined one-line LGE density (field units in, g/cm3 out)

```
rho_g[g/cm3] = (1/62.427960576) * p * M / (Z * 10.731577 * T)
```

*Unit system:* oilfield in, CGS out

| Symbol | Meaning | Units |
|---|---|---|
| `p` | absolute pressure | psia |
| `M` | apparent molecular weight | lbm/lbmol |
| `Z` | z-factor | dimensionless |
| `T` | absolute temperature | deg R |

Assumptions:

- Equivalent to the pengtools form which uses 1/62.428 and R = 10.732.

*Source:* pengtools wiki (secondary) cross-checked against SPE 75721 Eq. 8  
*Access:* secondary source, arithmetic verified this session

### Apparent molecular weight from gas specific gravity

```
M = 28.9625 * SG_g      (many references use M = 28.97 * SG_g or 28.967 * SG_g)
```

*Unit system:* oilfield

| Symbol | Meaning | Units |
|---|---|---|
| `SG_g` | gas specific gravity relative to dry air at the same p, T | dimensionless |
| `28.9625` | molar mass of standard dry air | lbm/lbmol (= g/mol) |

Assumptions:

- The dry-air molar mass in current use is 28.96546 g/mol (CIPM-2007) / 28.9625 g/mol (older). Petroleum texts use 28.96, 28.97, or 28.967. The spread is <0.02% - immaterial for LGE but pick ONE and document it.
- 28.967 is what the pengtools page uses; I did not verify a primary petroleum-standard value this session.

*Source:* pengtools wiki (28.967); air molar mass value recalled  
*Access:* secondary source / recalled - not retrieved

### Dranchuk & Abou-Kassem (1975) z-factor EOS

```
Z = 1 + c1*rho_r + c2*rho_r^2 - c3*rho_r^5 + c4
c1 = A1 + A2/Tpr + A3/Tpr^3 + A4/Tpr^4 + A5/Tpr^5
c2 = A6 + A7/Tpr + A8/Tpr^2
c3 = A9*(A7/Tpr + A8/Tpr^2)
c4 = A10*(1 + A11*rho_r^2)*(rho_r^2/Tpr^3)*exp(-A11*rho_r^2)
rho_r = 0.27*Ppr/(Z*Tpr)
```

*Unit system:* dimensionless (reduced)

| Symbol | Meaning | Units |
|---|---|---|
| `Z` | gas compressibility factor | dimensionless |
| `rho_r` | reduced density, rho/rho_c with z_c = 0.27 | dimensionless |
| `Ppr` | pseudo-reduced pressure = p/p_pc (p absolute) | dimensionless |
| `Tpr` | pseudo-reduced temperature = T/T_pc (T absolute, deg R / deg R) | dimensionless |

Assumptions:

- Implicit in Z - must be solved iteratively (Newton on f(Z) = RHS - Z, or solve for rho_r).
- z_c is FIXED at 0.27 by definition inside the correlation; it is not the real critical z-factor of the mixture.
- Requires a pseudocritical correlation (Standing, Sutton, or composition + Kay's rule) and, for sour gas, the Wichert-Aziz correction. These are outside this card.

*Source:* Dranchuk, P.M. & Abou-Kassem, J.H., 'Calculation of Z-Factors for Natural Gases Using Equations of State', J. Can. Pet. Tech. (Jul-Sep 1975) 14, 34-36. A1..A11 verified full-text in SPE 75721 Eq. 10 AND in Condor Tarco (Univ. of Regina) report Eqs. 2.1-2.6.  
*Access:* full-text retrieved (two independent reproductions agree exactly); primary JCPT paper: metadata only

### Analytic DAK derivative dZ/d(rho_r) at constant Tpr

```
D = (dZ/d rho_r)_Tpr = c1 + 2*c2*rho_r - 5*c3*rho_r^4 + (2*A10*rho_r/Tpr^3) * (1 + A11*rho_r^2 - (A11*rho_r^2)^2) * exp(-A11*rho_r^2)
```

*Unit system:* dimensionless

| Symbol | Meaning | Units |
|---|---|---|
| `D` | partial derivative of Z w.r.t. reduced density at fixed Tpr (Z treated as the EXPLICIT polynomial in rho_r, not through the implicit loop) | dimensionless |
| `c1,c2,c3` | the DAK groups defined above | dimensionless |

Assumptions:

- The bracket is (1 + A11*rho_r^2 - A11^2*rho_r^4). I derived this by hand from d/d rho_r [ (rho_r^2 + A11*rho_r^4) e^(-A11 rho_r^2) ] = 2*rho_r*(1 + A11*rho_r^2 - A11^2*rho_r^4)*e^(-A11 rho_r^2), and confirmed it numerically against central finite differences of the explicit polynomial (rel. err ~1e-11 at Tpr 1.05/1.3/1.8/2.5 and rho_r 0.1/0.5/1.0/1.6).
- This is the derivative of the EXPLICIT polynomial. Do NOT also differentiate through rho_r = 0.27 Ppr/(Z Tpr) here - that coupling is handled in the c_pr equation below.

*Source:* Structure per Mattar, L., Brar, G.S. & Aziz, K., 'Compressibility of Natural Gases', J. Can. Pet. Tech. (Oct-Dec 1975) 14, 77-80 (PETSOC-75-04-08). Derivation re-done and numerically verified this session.  
*Access:* Unverified — cited source not inspected - not retrieved (MBA paper text); derivation independently verified this session

### Isothermal gas compressibility (definition and derivation)

```
c_g = -(1/V)*(dV/dp)_T ;  V = n*Z*R*T/p
(dV/dp)_T = n*R*T*[ (1/p)*(dZ/dp)_T - Z/p^2 ]
=> c_g = (1/p) - (1/Z)*(dZ/dp)_T
```

*Unit system:* any consistent; in field units c_g is 1/psi with p in psia

| Symbol | Meaning | Units |
|---|---|---|
| `c_g` | isothermal gas compressibility | psi^-1 (field) or Pa^-1 (SI) |
| `p` | ABSOLUTE pressure | psia |
| `Z` | z-factor at p, T | dimensionless |
| `(dZ/dp)_T` | partial derivative of Z w.r.t. pressure at constant T | psi^-1 |

Assumptions:

- Constant T, constant composition (no retrograde condensation, no gas dissolving into water). For a gas-condensate below dewpoint this definition is wrong - you need c_g from a total-system/CVD basis.
- Ideal-gas limit: Z = 1, dZ/dp = 0 => c_g = 1/p exactly. This is the first unit test.
- Sign behaviour: at low p, dZ/dp < 0 so c_g > 1/p; at high p (Z rising) dZ/dp > 0 so c_g < 1/p. Verified numerically: gamma=0.65 gas at 180 degF gives c_g = 2.090e-3 vs 1/p = 2.000e-3 at 500 psia, and c_g = 3.002e-4 vs 1/p = 3.333e-4 at 3000 psia.

*Source:* Standard thermodynamic definition; presented identically in Trube (1957), Mattar-Brar-Aziz (1975), and every reservoir-engineering text  
*Access:* Unverified — cited source not inspected - not retrieved; derivation is elementary and re-done here

### Pseudo-reduced compressibility (Trube form)

```
c_pr = c_g * p_pc  =>  c_pr = 1/p_pr - (1/Z)*(dZ/dp_pr)_Tpr
```

*Unit system:* dimensionless

| Symbol | Meaning | Units |
|---|---|---|
| `c_pr` | pseudo-reduced isothermal compressibility | dimensionless |
| `p_pc` | pseudocritical pressure | psia |
| `p_pr` | p/p_pc, absolute | dimensionless |

Assumptions:

- Follows directly because p = p_pr * p_pc with p_pc constant at fixed composition.
- Trube (1957) and Mattar et al. often chart the product c_pr*T_pr vs p_pr, T_pr - if you digitise a chart, check which product is plotted.

*Source:* Trube, A.S., 'Compressibility of Natural Gases', Trans. AIME (1957) 210, 355-357; Mattar, Brar & Aziz (1975)  
*Access:* Unverified — cited source not inspected - not retrieved

### Mattar-Brar-Aziz analytic c_pr through DAK (THE implementable route)

```
c_pr = 1/p_pr - (0.27/(Z^2 * Tpr)) * D / ( 1 + (rho_r/Z)*D )
where D = (dZ/d rho_r)_Tpr from the equation above, rho_r = 0.27*p_pr/(Z*Tpr), and Z is the converged DAK root.
Then: c_g = c_pr / p_pc
```

*Unit system:* dimensionless c_pr; c_g in psi^-1 when p_pc in psia

| Symbol | Meaning | Units |
|---|---|---|
| `D` | analytic DAK derivative dZ/d rho_r | dimensionless |
| `rho_r` | converged reduced density | dimensionless |
| `Z` | converged DAK z-factor | dimensionless |
| `0.27` | the DAK fixed z_c | dimensionless |

Assumptions:

- Chain-rule derivation (re-done this session): rho_r = 0.27 p_pr/(Z Tpr) => d rho_r/d p_pr = rho_r/p_pr - (rho_r/Z) dZ/dp_pr. Substituting dZ/dp_pr = D * d rho_r/d p_pr and solving gives dZ/dp_pr = (0.27/(Z Tpr)) * D / (1 + (rho_r/Z) D). Insert into c_pr = 1/p_pr - (1/Z) dZ/dp_pr.
- The denominator (1 + (rho_r/Z)*D) is exactly the implicit-function correction. Omitting it is the single most common bug in hand-rolled implementations.
- Z must be fully converged before D is evaluated; a loose Newton tolerance contaminates c_g much more than it contaminates Z.

*Source:* Mattar, Brar & Aziz, J. Can. Pet. Tech. (1975), PETSOC-75-04-08, applied to the DAK EOS  
*Access:* Unverified — cited source not inspected - not retrieved (paper); expression fully re-derived and numerically verified this session

### Finite-difference fallback for dZ/dp

```
(dZ/dp)_T ~= [Z(p+h) - Z(p-h)] / (2h),  h = 1e-5 * p  (relative step)
```

*Unit system:* field

| Symbol | Meaning | Units |
|---|---|---|
| `h` | pressure perturbation | psi |

Assumptions:

- Central differences with h = 1e-5*p reproduced the analytic c_pr to rel. err ~1e-11 across Tpr 1.05-3.0 and p_pr 0.5-25 in this session's test. Use this as the REGRESSION TEST for the analytic route, not as the production path.
- Too small an h (< ~1e-8*p) hits cancellation error amplified by the iterative Z solve's own tolerance; too large an h biases near the critical region where Z(p) is strongly curved.
- One-sided differences are materially worse; do not use them.

*Source:* Standard numerical differentiation; tolerance figures measured this session  
*Access:* verified numerically this session

### Total system compressibility

```
c_t = c_g*S_g + c_o*S_o + c_w*S_w + c_f      (dry gas reservoir: c_t = c_g*S_g + c_w*S_w + c_f)
```

*Unit system:* field

| Symbol | Meaning | Units |
|---|---|---|
| `c_t` | total system compressibility | psi^-1 |
| `c_g` | gas isothermal compressibility | psi^-1 |
| `S_g` | gas saturation (fraction of pore volume) | fraction, dimensionless |
| `c_w` | water (brine) isothermal compressibility | psi^-1 |
| `S_w` | water saturation (connate + mobile) | fraction, dimensionless |
| `c_f` | formation (pore-volume) compressibility | psi^-1 |

Assumptions:

- S_g + S_o + S_w = 1 must hold; assert it.
- c_f is PORE-VOLUME compressibility (c_f = (1/phi)(d phi/dp)), NOT bulk-rock or grain compressibility. Mixing these up is a factor-of-1/phi error (~5-25x).
- Saturation weighting assumes each phase occupies its saturation fraction of the pore volume and that phases do not exchange mass with pressure (no solution gas coming out, no gas dissolving in water). For a saturated oil the c_o term must include the Rs/Bo term.

*Source:* Standard material-balance / well-test formulation (e.g. Craft & Hawkins; Lee & Wattenbarger, Gas Reservoir Engineering)  
*Access:* Unverified — cited source not inspected - not retrieved

### Carr-Kobayashi-Burrows (1954) structure - two-step

```
Step 1: mu_1 = mu_1(T[degF], SG_g) at 1 atm, plus additive non-hydrocarbon corrections for N2, CO2, H2S
Step 2: mu_g = mu_1 * (mu_g/mu_1)(p_pr, T_pr)
No closed form exists in the 1954 paper itself - both steps are CHARTS.
```

*Unit system:* oilfield; mu in cp; T in degF for step 1, reduced (absolute-based) for step 2

| Symbol | Meaning | Units |
|---|---|---|
| `mu_1` | gas viscosity at 1 atm and reservoir temperature | cp |
| `mu_g/mu_1` | viscosity ratio (pressure correction) | dimensionless |
| `p_pr, T_pr` | pseudo-reduced pressure and temperature (both from ABSOLUTE p and T) | dimensionless |

Assumptions:

- HONEST STATEMENT: Carr, Kobayashi & Burrows (1954) is chart-based. Any 'CKB equation' you find is a later curve fit (Dempsey 1965, or the JCPT 86-01-03 mathematical representation), not CKB's own work. Cite it as such.
- The T in step 1 is deg F in the Standing/Dempsey fit (unusual - most of this card uses deg R). This is a real trap.
- CKB explicitly includes non-hydrocarbon (N2, CO2, H2S) corrections, which LGE does NOT. For sour gas, CKB/Dempsey is the better structure; LGE is stated to be inapplicable to sour gases.

*Source:* Carr, N.L., Kobayashi, R. & Burrows, D.B., 'Viscosity of Hydrocarbon Gases Under Pressure', Trans. AIME (1954) 201, 264-272. Two-step chart structure described verbatim in SPE 75721.  
*Access:* full-text retrieved (structural description in SPE 75721); primary 1954 paper: recalled / metadata only

### Dempsey (1965) / Standing fit to CKB - atmospheric viscosity (mu_1)

```
mu_1_uncorrected = (1.709e-5 - 2.062e-6 * SG_g) * T[degF] + 8.188e-3 - 6.15e-3 * log10(SG_g)
mu_1 = mu_1_uncorrected + (mu)_N2 + (mu)_CO2 + (mu)_H2S
(mu)_N2  = y_N2  * (8.48e-3 * log10(SG_g) + 9.59e-3)
(mu)_CO2 = y_CO2 * (9.08e-3 * log10(SG_g) + 6.24e-3)
(mu)_H2S = y_H2S * (8.49e-3 * log10(SG_g) + 3.73e-3)
```

*Unit system:* oilfield; T in deg F (NOT deg R)

| Symbol | Meaning | Units |
|---|---|---|
| `mu_1` | gas viscosity at 1 atm and reservoir T | cp |
| `T` | temperature | deg F |
| `SG_g` | gas specific gravity (air = 1) | dimensionless |
| `y_N2, y_CO2, y_H2S` | mole fractions of the non-hydrocarbons | fraction, dimensionless |

Assumptions:

- The uncorrected-mu_1 coefficients 1.709e-5, 2.062e-6, 8.188e-3, 6.15e-3 were cross-checked this session against an open-source implementation (rNodal gas_correlations.R) which prints 1.709/100000, 2.062/1000000, 8.188/1000, 6.15/1000. That is a SECONDARY cross-check only.
- The N2/CO2/H2S correction coefficients are RECALLED and were NOT verified against any source this session. Treat as UNVERIFIED.
- log10, not ln.

*Source:* Dempsey, J.R. (1965) / Standing, M.B., 'Volumetric and Phase Behavior of Oil Field Hydrocarbon Systems', SPE (1977). Cross-check: rNodal R package source (secondary).  
*Access:* secondary source (partially); non-hydrocarbon corrections: Unverified — cited source not inspected - not retrieved

### Dempsey (1965) viscosity-ratio polynomial

```
ln( T_pr * (mu_g/mu_1) ) = a0 + a1*Ppr + a2*Ppr^2 + a3*Ppr^3
 + T_pr   * (a4  + a5*Ppr  + a6*Ppr^2  + a7*Ppr^3)
 + T_pr^2 * (a8  + a9*Ppr  + a10*Ppr^2 + a11*Ppr^3)
 + T_pr^3 * (a12 + a13*Ppr + a14*Ppr^2 + a15*Ppr^3)
then mu_g = mu_1 * exp(RHS) / T_pr
```

*Unit system:* dimensionless reduced variables; mu in cp

| Symbol | Meaning | Units |
|---|---|---|
| `T_pr` | pseudo-reduced temperature (from ABSOLUTE T) | dimensionless |
| `Ppr` | pseudo-reduced pressure (from ABSOLUTE p) | dimensionless |
| `a0..a15` | Dempsey regression coefficients (see constants) | dimensionless |

Assumptions:

- Note the LHS is ln(T_pr * ratio), so you must divide by T_pr after exponentiating. Getting this wrong is a common bug and is NOT caught by a unit check.
- The exact grouping (which power of T_pr multiplies which a-coefficients) is recalled; I could not confirm it against a primary source this session. It MUST be validated by reproducing a published chart point before use.
- Stated applicability of the fit: roughly 32-400 degF and reduced pressure below 20 (per a secondary source; unverified).

*Source:* Dempsey, J.R., 'Computer Routine Treats Gas Viscosity as a Variable', Oil & Gas Journal (Aug 16, 1965) 141-143. Coefficient values cross-checked against rNodal R source (secondary).  
*Access:* secondary source / Unverified — cited source not inspected - not retrieved

### NIST viscosity unit conversion

```
mu[cp] = mu[uPa*s] * 1.0e-3      (exactly, since 1 cP = 1 mPa*s = 1000 uPa*s exactly)
```

*Unit system:* SI <-> CGS-derived

| Symbol | Meaning | Units |
|---|---|---|
| `mu[uPa*s]` | viscosity as reported by NIST Chemistry WebBook | micropascal-second |
| `mu[cp]` | viscosity in centipoise | cp |

Assumptions:

- Exact by definition: 1 poise = 0.1 Pa*s exactly, so 1 cP = 1e-3 Pa*s = 1e3 uPa*s. No approximation.
- Reverse: mu[uPa*s] = mu[cp] * 1000.

*Source:* SI definition of the poise; NIST SP 811  
*Access:* recalled definition - exact by construction

## Constants

| Name | Value | Units | Source | How verified |
|---|---|---|---|---|
| LGE 1e-4 scaling factor | `1.0e-4` | cp per unit of K*exp(...) | SPE 75721 Eq. 4 (reproducing Lee, Gonzalez & Eakin 1966) | full-text retrieved this session |
| LGE K numerator constant | `9.379` | dimensionless | SPE 75721 Eq. 5 | full-text retrieved this session |
| LGE K numerator M-coefficient | `0.01607` | per (lbm/lbmol) | SPE 75721 Eq. 5 | full-text retrieved this session |
| LGE K denominator constant | `209.2` | deg R | SPE 75721 Eq. 5 | full-text retrieved this session |
| LGE K denominator M-coefficient | `19.26` | deg R per (lbm/lbmol) | SPE 75721 Eq. 5 | full-text retrieved this session |
| LGE X constant term | `3.448` | dimensionless | SPE 75721 Eq. 6 | full-text retrieved this session; also discriminated numerically against the erroneous 3.488 using the reference extract (error statistics excluded from this release under docs/release/PUBLIC_DATA_POLICY.md) |
| LGE X temperature coefficient | `986.4` | deg R | SPE 75721 Eq. 6 | full-text retrieved this session |
| LGE X molecular-weight coefficient | `0.01009` | per (lbm/lbmol) | SPE 75721 Eq. 6 | full-text retrieved this session |
| LGE Y constant term | `2.447` | dimensionless | SPE 75721 Eq. 7 | full-text retrieved this session |
| LGE Y X-coefficient | `0.2224` | dimensionless | SPE 75721 Eq. 7 | full-text retrieved this session |
| lbm/ft3 per g/cm3 (exact) | `62.427960576144606` | (lbm/ft3)/(g/cm3) | 30.48^3 / 453.59237 (1959 international yard & pound, exact definitions) | computed exactly this session; NOT the 62.37 printed in SPE 75721 Eq. 8 / the LGE-era literature |
| g/cm3 per lbm/ft3 (exact) | `0.016018463373960140` | (g/cm3)/(lbm/ft3) | 453.59237 / 30.48^3 | computed exactly this session |
| lbm/ft3 per g/cm3 as printed in the LGE-era source | `62.37` | (lbm/ft3)/(g/cm3) | SPE 75721 Eq. 8 nomenclature line | full-text retrieved this session - retrieved but KNOWN to be 0.093% off the exact value; documented for audit, do not use |
| Universal gas constant, field units | `10.731577089` | psia*ft3/(lbmol*deg R) | CODATA R = 8.31446261815324 J/(mol*K), converted with exact SI factors (453.59237 mol/lbmol, 1/6894.757293168361 psi/Pa, 35.31466672148859 ft3/m3, /1.8 K per degR) | computed this session; petroleum literature rounds this to 10.732 or 10.7316 (SPE 75721 uses 10.732) |
| DAK A1 | `0.3265` | dimensionless | Dranchuk & Abou-Kassem (1975); SPE 75721 Eq. 10 and Condor Tarco report | full-text retrieved this session from two independent reproductions, identical |
| DAK A2 | `-1.0700` | dimensionless | as above | full-text retrieved this session (two sources agree) |
| DAK A3 | `-0.5339` | dimensionless | as above | full-text retrieved this session (two sources agree) |
| DAK A4 | `0.01569` | dimensionless | as above | full-text retrieved this session (two sources agree) |
| DAK A5 | `-0.05165` | dimensionless | as above | full-text retrieved this session (two sources agree) |
| DAK A6 | `0.5475` | dimensionless | as above | full-text retrieved this session (two sources agree) |
| DAK A7 | `-0.7361` | dimensionless | as above | full-text retrieved this session (two sources agree) |
| DAK A8 | `0.1844` | dimensionless | as above | full-text retrieved this session (two sources agree) |
| DAK A9 | `0.1056` | dimensionless | as above | full-text retrieved this session (two sources agree) |
| DAK A10 | `0.6134` | dimensionless | as above | full-text retrieved this session (two sources agree) |
| DAK A11 | `0.7210` | dimensionless | as above | full-text retrieved this session (two sources agree) |
| DAK fixed critical z-factor | `0.27` | dimensionless | Dranchuk & Abou-Kassem definition rho_r = 0.27*Ppr/(Z*Tpr); SPE 75721 and Condor Tarco Eq. 2.2 | full-text retrieved this session |
| Dempsey a0 | `-2.46211820` | dimensionless | Dempsey (1965); cross-check rNodal gas_correlations.R | secondary source only - needs primary source |
| Dempsey a1 | `2.97054714` | dimensionless | as above | secondary source only - needs primary source |
| Dempsey a2 | `-0.286264054` | dimensionless | as above (rNodal prints -0.28626405) | secondary source only - needs primary source; trailing digit beyond 8 s.f. is RECALLED |
| Dempsey a3 | `0.00805420522` | dimensionless | as above (rNodal prints 0.00805420) | secondary source only - needs primary source; trailing digits RECALLED |
| Dempsey a4 | `2.80860949` | dimensionless | as above | secondary source only - needs primary source |
| Dempsey a5 | `-3.49803305` | dimensionless | as above | secondary source only - needs primary source |
| Dempsey a6 | `0.360373020` | dimensionless | as above (rNodal prints 0.36037302) | secondary source only - needs primary source |
| Dempsey a7 | `-0.0104432413` | dimensionless | as above (rNodal prints -0.01044324) | secondary source only - needs primary source; trailing digits RECALLED |
| Dempsey a8 | `-0.793385684` | dimensionless | as above (rNodal prints -0.79338568) | secondary source only - needs primary source |
| Dempsey a9 | `1.39643306` | dimensionless | as above | secondary source only - needs primary source |
| Dempsey a10 | `-0.149144925` | dimensionless | as above (rNodal prints -0.14914493) | secondary source only - needs primary source |
| Dempsey a11 | `0.00441015512` | dimensionless | as above (rNodal prints 0.00441016) | secondary source only - needs primary source; trailing digits RECALLED |
| Dempsey a12 | `0.0839387178` | dimensionless | as above (rNodal prints 0.08393872) | secondary source only - needs primary source |
| Dempsey a13 | `-0.186408848` | dimensionless | as above (rNodal prints -0.18640885) | secondary source only - needs primary source |
| Dempsey a14 | `0.0203367881` | dimensionless | as above (rNodal prints 0.02033679) | secondary source only - needs primary source |
| Dempsey a15 | `-0.000609579263` | dimensionless | as above (rNodal prints -0.00060958) | secondary source only - needs primary source; trailing digits RECALLED |
| Methane critical temperature (for pure-CH4 cross-checks) | `190.564 (= 343.0152 deg R)` | K | NIST Chemistry WebBook fluid page for methane (Setzmann & Wagner 1991 basis) | full-text retrieved this session from webbook.nist.gov |
| Methane critical pressure | `667.06` | psia | NIST Chemistry WebBook fluid page for methane | full-text retrieved this session (= 4.5992 MPa; my SI-to-psia conversion gives 667.058, consistent) |
| Methane critical density | `162.66` | kg/m3 | NIST Chemistry WebBook fluid page for methane | full-text retrieved this session |
| Methane acentric factor | `0.01142` | dimensionless | NIST Chemistry WebBook fluid page for methane | full-text retrieved this session |
| Methane molar mass | `16.0425 (16.043 also used)` | g/mol = lbm/lbmol | IUPAC standard atomic weights | Unverified — cited source not inspected - not retrieved (but universally agreed to 5 s.f.) |
| uPa*s -> cp conversion factor | `1.0e-3` | cp per uPa*s | SI definition: 1 P = 0.1 Pa*s exactly | exact by definition |
| Typical brine compressibility c_w | `~2e-6 to 4e-6 (commonly 3e-6)` | psi^-1 | Dodson & Standing (1944) / Osif (1988) correlations; ScienceDirect topic page (secondary) | secondary source / Unverified — cited source not inspected - not retrieved. UNVERIFIED - needs primary source if used quantitatively |
| Typical pore-volume (formation) compressibility c_f | `~3e-6 to 30e-6 for consolidated-to-unconsolidated; consolidated sandstone commonly 3e-6 to 6e-6` | psi^-1 | Hall (1953), Newman (1973); ScienceDirect 'Formation Compressibility' topic page (secondary) | secondary source - range confirmed this session in a secondary aggregator; primary Hall/Newman NOT retrieved. UNVERIFIED - needs primary source |

## Validity ranges

- LGE (1966) development data: pressure 100 to 8,000 psia; temperature 100 to 340 deg F (= 559.67 to 799.67 deg R). VERIFIED full-text in SPE 75721.
- LGE: hydrocarbon (sweet) natural gases with specific gravity below 1.0 for the quoted accuracy; explicitly 'less accurate' above SG 1.0. VERIFIED full-text.
- LGE: CO2 content up to 3.2 mol% was represented in the development data. VERIFIED full-text. H2S is NOT covered - the correlation cannot be used for sour gases.
- LGE accuracy as reported by the authors: ~2% average absolute error at low pressures, ~4% at high pressures, for SG < 1.0. VERIFIED full-text in SPE 75721. A separate frequently-quoted figure is 2.7% standard deviation / 8.99% maximum deviation - I did NOT verify this against the JPT paper this session.
- LGE against a modern large database: 3.34% average absolute error over 4,909 points (pure components + natural gas mixtures). VERIFIED full-text in SPE 75721. The corresponding check against the reference extract is consistent with it; its bias statistic is excluded from this release under docs/release/PUBLIC_DATA_POLICY.md.
- DAK (1975): accurate over 1.0 < T_pr < 3.0 with 0.2 <= p_pr <= 30. Average absolute error 0.486% against 1,500 data points from the Standing-Katz chart. VERIFIED full-text (Condor Tarco report; range statement partly garbled in PDF extraction but the standard published range is as stated - flag for one more confirmation).
- DAK: a commonly cited additional caveat is that it is also acceptable for 0.7 < T_pr < 1.0 only when p_pr <= 1.0. This is RECALLED, not verified this session.
- Carr-Kobayashi-Burrows (1954): chart-based; the Dempsey fit is stated (secondary source) to be valid roughly 32-400 deg F and reduced pressure below 20. UNVERIFIED.
- NIST methane viscosity (Quinones-Cisneros, Huber & Deiters 2011): estimated uncertainty < 0.3% for 200-400 K at p < 30 MPa; < 2% over the rest of the fluid surface to 100 MPa; up to 5% for 100-500 MPa; 10% for 500-1000 MPa to 625 K. VERIFIED verbatim from the NIST page.
- NIST methane EOS (Setzmann & Wagner 1991): density uncertainty 0.03% for p < 12 MPa and T < 350 K, up to 0.07% for p < 50 MPa. VERIFIED verbatim from the NIST page. Valid melting line to 625 K, to 1000 MPa.
- c_g = 1/p - (1/Z) dZ/dp is valid only for a single-phase, constant-composition gas at constant T. It is NOT the right c_g below the dewpoint of a gas condensate.

## Failure modes

- Passing rho in lbm/ft3 into LGE instead of g/cm3: produces a viscosity of order 1e7 cp (verified numerically at a representative reservoir methane density). No exception is raised - guard with an explicit range assert (reservoir gas rho is ~0.005-0.35 g/cm3).
- Passing T in deg F instead of deg R into K, X: silently wrong, and the error is non-monotonic because T appears as T^1.5, as +T in a denominator, and as 986.4/T.
- Passing p in psig instead of psia into the density equation or into p_pr: at low reservoir pressures this is a large relative error and it propagates into Z, rho, mu and c_g simultaneously.
- Mixing the ORIGINAL LGE coefficient set (9.379/0.01607/209.2/19.26/3.448/986.4/0.01009/2.447/0.2224) with the ROUNDED set (9.4/0.02/209/19/3.5/986/0.001/2.4/0.2). Note X's M-coefficient differs by 10x (0.01009 vs 0.001) between the two sets - that is not a rounding.
- Copying X0 = 3.488 from nafta.wiki (a typo). Correct value is 3.448.
- Using 62.37 instead of 62.427960576 for the lbm/ft3 -> g/cm3 conversion: 0.093% error in rho. Negligible in mu_g (0.014%) but not negligible if you invert rho to get Z, or if you unit-test against NIST to 0.1%.
- Omitting the (1 + (rho_r/Z)*D) denominator in the Mattar-Brar-Aziz c_pr expression (i.e. forgetting that rho_r itself depends on Z). This is the single most common c_g bug and it gets WORSE at high density where D is large.
- Differentiating the DAK expression while treating rho_r as fixed AND separately through the implicit loop (double-counting). Use the explicit polynomial derivative D, then apply the chain-rule correction exactly once.
- Using LGE on sour gas. H2S is outside the development set; use CKB/Dempsey (which has an explicit H2S correction) and/or an EOS-based model, and say so in the output.
- Applying c_t = c_g*S_g + c_w*S_w + c_f with c_f taken as BULK-ROCK or GRAIN compressibility instead of PORE-VOLUME compressibility. Off by ~1/phi.
- Forgetting the Wichert-Aziz pseudocritical correction for sour gas before feeding T_pr, p_pr into DAK. Z will be wrong and so will c_g.
- Evaluating D from a non-converged Z. c_g is far more sensitive to Z-solver tolerance than Z itself is.

## Numerical pitfalls

- LGE exponent: exp(X * rho^Y) with X ~ 5.4 and rho up to ~0.35 g/cm3 gives an exponent up to ~1.3 - well-behaved. But if rho is accidentally in lbm/ft3 (up to ~22) the exponent reaches ~200 and you get a number near overflow instead of an exception. Guard the input, not the output.
- rho^Y with Y ~ 1.25 and rho = 0 raises 0.0 correctly in Python but 0**negative would raise. If any variant produces Y < 0 (it should not for realistic M, T), guard rho > 0.
- DAK near the critical region (T_pr ~ 1.0-1.1, p_pr ~ 1-3) is stiff: Z drops to ~0.18-0.42 and dZ/dp is very large. Newton from Z0 = 1.0 can overshoot to negative Z. I found a single sign-change root in [0.01, 3] at (T_pr, p_pr) = (1.0,1.0), (1.05,1.2), (1.05,1.5), (1.1,2.0) - so bracketing bisection is safe there, but Newton needs damping or a bracket fallback.
- c_g convergence is far more sensitive to the Z-solver tolerance than Z is, because you divide by Z^2 and because D multiplies a near-cancelling difference. Converge Z to 1e-12 relative before computing c_g, not 1e-6.
- 1/p_pr - (something) is a cancelling subtraction at large p_pr where c_pr becomes small (c_pr ~ 5.5e-3 at T_pr=1.05, p_pr=25 vs 1/p_pr = 0.04). At p_pr > 20 you lose roughly 1 decimal digit. Acceptable in double precision; would not be in float32.
- Finite-difference step selection for the FD oracle: h = 1e-5 * p is a good relative step (verified to 1e-11 agreement). Absolute steps like h = 1 psi fail badly at low pressure and are needlessly noisy at high pressure.
- D crosses zero (I measured D = 2.647e-4 at T_pr = 1.3, rho_r = 1.0). Any test on D must use an absolute tolerance near that crossing, not a relative one.
- T[degR] = T[degF] + 459.67, not + 460. The 0.33 degR difference is ~0.06% in T and shows up at the 4th significant figure of mu_g - enough to break a 1e-4 regression test against a reference implementation that used 459.67.
- Do not use float32 anywhere in the Z/c_g chain. The DAK exponential term and the c_pr cancellation both need double.
- Methane at exactly the NIST table rows returned duplicate 'vapor'/'supercritical' entries at 1000 psia (same numbers, different phase label). If you scrape NIST tables programmatically, de-duplicate on pressure.

## Implementation notes

- Recommended call order: (1) M from composition or SG; (2) pseudocriticals (+ Wichert-Aziz if sour); (3) T_pr, p_pr from ABSOLUTE T and p; (4) solve DAK for Z; (5) rho in lbm/ft3 then convert to g/cm3; (6) LGE mu_g; (7) D and c_pr; (8) c_g = c_pr/p_pc; (9) c_t. Each step should carry its units in the type/name, e.g. rho_g_cm3 vs rho_lbm_ft3.
- Solve DAK on rho_r rather than Z when you can: substituting Z = 0.27*p_pr/(rho_r*T_pr) turns the implicit equation into an explicit polynomial-plus-exponential in rho_r alone, which Newton handles cleanly and which gives you D for free.
- If you solve for Z with bisection, bracket [1e-4, 5.0] and run ~200 iterations for full double precision, or use Newton with the analytic df/dZ seeded from Z0 = 1.0 (or from the Hall-Yarborough / Brill-Beggs estimate). Bisection is slow but never diverges; I used it for the reference values in this card.
- Expose LGE as two explicitly named variants ('lge_1966' with 9.379/0.01607/209.2/19.26/3.448/986.4/0.01009 and 'lge_rounded' with 9.4/0.02/209/19/3.5/986/0.001) and make the caller choose. Do not default silently.
- Provide c_g through BOTH paths (analytic MBA, and a finite-difference fallback) behind one interface, and ship the FD path as a test-only oracle. My sweep showed they agree to ~1e-11, so any regression in the analytic path will be caught immediately.
- Store viscosity internally in Pa*s (SI) and convert at the boundary; the cp <-> uPa*s factor is exactly 1e-3 / 1e3 so round-tripping is lossless in binary floating point only if you use powers of ten carefully - prefer multiplying by 1e-3 over dividing by 1000 for consistency (they are identical here, but pick one).
- Assert physical ranges rather than trusting callers: 0.001 <= rho_g[g/cm3] <= 0.6; 0.2 <= Z <= 2.5; 0.005 <= mu_g[cp] <= 0.15; c_g > 0 always.
- When a caller asks for LGE outside 100-8000 psia or 100-340 degF, emit a warning with the actual bound rather than silently extrapolating. Same for DAK outside 1.0 < T_pr < 3.0, 0.2 <= p_pr <= 30.
- For c_t: require saturations to sum to 1 within 1e-9 and require c_f to be documented as pore-volume compressibility at the call site.
- Magnitudes for a reader's intuition (gamma=0.65, 180 degF, Standing pseudocriticals, computed this session): c_g = 2.09e-3 /psi at 500 psia, 1.08e-3 at 1000, 5.23e-4 at 2000, 3.00e-4 at 3000, 1.24e-4 at 5000, 5.23e-5 at 8000. With S_g = 0.75, S_w = 0.25, c_w = 3e-6, c_f = 4e-6: c_t = 1.57e-3 at 500 psia down to 4.40e-5 at 8000 psia. Note that at 500 psia c_g*S_g is >99% of c_t, while at 8000 psia the c_w+c_f contribution is already ~11% - so c_f and c_w are NOT negligible in deep high-pressure gas reservoirs, contrary to the common textbook shortcut.
- PLUS: LGE, DAK and the Mattar-Brar-Aziz derivative are all now grounded in retrieved full text (SPE 75721 + a second DAK reproduction), and the c_g chain rule is verified two ways - analytically by hand and numerically to 1e-11 against finite differences - plus a real physical cross-check against the reference extract (its agreement statistics are excluded from this release under docs/release/PUBLIC_DATA_POLICY.md). This is enough to defend in front of a petroleum engineer. MINUS: two things are still weak - (a) Dempsey a0..a15 and the N2/CO2/H2S corrections have only secondary/recalled backing, so CKB cannot yet be claimed implementable-verified; (b) c_w and c_f typical values still have no primary source, and the pseudocritical correlation (Standing/Sutton) is deliberately outside the scope of this card even though it feeds directly into T_pr/p_pr and therefore also determines c_g. RECOMMENDATION: implement (a), (b), (d), (e) now with a test suite built from the independent_checks above; for (c) ship the two-step CKB structure plus an honest statement that it is chart-based, and mark the Dempsey path as UNVERIFIED until Dempsey (1965) OGJ or JCPT 86-01-03 is actually retrieved. Do not chain to the next primitive before this test suite is green - dogfood first.

## Open uncertainties

- I did NOT retrieve the original Lee, Gonzalez & Eakin JPT 1966 paper itself (OnePetro returned 403). Every LGE coefficient here comes from SPE 75721's verbatim reproduction (Eqs. 4-7), which is a peer-reviewed SPE paper by Londono, Archer & Blasingame. Two independent reproductions (SPE 75721 and nafta.wiki) agree on 9.379/0.01607/209.2/19.26/986.4/0.01009/2.447/0.2224; they DISAGREE on the X constant (3.448 vs 3.488). I resolved this numerically in favour of 3.448 against retrieved NIST data, and SPE 75721's own extracted text reads 3.448. Confidence high but not primary-sourced.
- The frequently-quoted LGE accuracy figures '2.7% standard deviation, 8.99% maximum deviation' appeared only in a search-result summary, not in any full text I retrieved. UNVERIFIED. What I DID verify full-text is '2 percent average absolute error (low pressures) and 4 percent average absolute error (high pressures) for SG < 1.0'. Use the verified statement.
- The 'rounded' LGE variant (9.4 / 0.02 / 209 / 19 / 3.5 / 986 / 0.001 / 2.4 / 0.2) comes from a secondary wiki. I cannot establish its provenance - whether it is Standing's simplification, a textbook rounding, or an error that propagated. In particular X's M-coefficient 0.001 vs the original 0.01009 is a 10x difference that rounding cannot explain. UNVERIFIED - needs a primary source before shipping.
- All Dempsey a0..a15 values and the Standing mu_1 coefficients are backed only by an open-source R implementation (rNodal), which is a SECONDARY source. The digits beyond 8 significant figures (e.g. -0.286264054 vs rNodal's -0.28626405) are Unverified — cited source not inspected: rNodal is identified but its digits beyond 8 significant figures were not read from it. The N2/CO2/H2S correction coefficients (8.48e-3/9.59e-3, 9.08e-3/6.24e-3, 8.49e-3/3.73e-3) are Unverified — supporting source not established.
- The exact algebraic grouping of the Dempsey polynomial - specifically that the left side is ln(T_pr * mu/mu_1) rather than ln(mu/mu_1), and which a-coefficients pair with which power of T_pr - is RECALLED. I could not confirm it against Dempsey (1965) or JCPT 86-01-03 this session. Do NOT ship this without reproducing a published chart point.
- The DAK validity-range statement extracted from the Condor Tarco PDF was garbled by the PDF text extractor (digits appeared reversed: '0.1 < T_r', '2.0 <= p_r', '< T_r 0.3'). I read these as 1.0 < T_r < 3.0 and 0.2 <= p_r <= 30, which matches the standard published statement, but the extraction itself is not clean evidence. The AAE of 0.486% over 1,500 points WAS cleanly extracted.
- The commonly-cited DAK secondary range '0.7 < T_pr < 1.0 for p_pr <= 1.0' is RECALLED, not retrieved.
- I did not retrieve Mattar, Brar & Aziz (1975) itself (OnePetro/ADS abstract only). The c_pr expression I give was RE-DERIVED from first principles this session and verified numerically to 1e-11 against finite differences, so its correctness does not depend on the citation - but the attribution does. Search results independently confirm MBA 'expressed c_pr as a function of dZ/d rho_r rather than dZ/d p_pr', which matches the structure given.
- The Standing pseudocritical correlation used for the illustrative magnitude table (T_pc = 168 + 325g - 12.5g^2, p_pc = 677 + 15.0g - 37.5g^2) is RECALLED and UNVERIFIED. Those illustrative c_g numbers are therefore soft; the sign/ordering assertions built on them are not.
- c_w and c_f typical magnitudes come from a secondary aggregator (ScienceDirect topic pages) and recall. The primary Hall (1953) and Newman (1973) papers were not retrieved. UNVERIFIED - needs primary source before any quantitative claim.
- The NIST methane viscosity model is cited by NIST itself as 'Quinones-Cisneros, S.E., Huber, M.L., and Deiters, U.K., unpublished work, 2011'. A 2025 paper in Int. J. Thermophysics ('Correlation for the Viscosity of Methane (CH4) from the Triple Point to 625 K and Pressures to 1000 MPa', DOI pending confirmation, PMC12686087) appears to be the eventual publication, but I did NOT verify that it is the same model now served by the WebBook. Cite what the WebBook page itself says.
- Air molar mass: petroleum references use 28.96, 28.97, 28.9625 and 28.967 interchangeably. I did not resolve which is the petroleum-industry standard. Spread is <0.02%, immaterial for LGE, but the implementer should pin one value.

## Independent check values

| Check | Inputs | Expected | Source | Retrieved or recalled |
|---|---|---|---|---|
| LGE vs NIST reference data for pure methane at 310.928 K (100.0 deg F), 500-3000 psia. Using M = 16.0425, T = 559.6704 deg R, and NIST's own densities converted kg/m3 -> g/cm3 (divide by 1000). | `T = 310.928 K = 559.6704 deg R; M = 16.0425 lbm/lbmol; [reference values withheld -- see docs/release/PUBLIC_DATA_POLICY.md; re-acquire locally with scripts/fetch_nist_reference.py to run this check] ` | `NIST viscosity: [reference values withheld -- see docs/release/PUBLIC_DATA_POLICY.md; re-acquire locally with scripts/fetch_nist_reference.py to run this check] ` | NIST Chemistry WebBook, methane isothermal table, retrieved via https://webbook.nist.gov/cgi/fluid.cgi (Action=Data, T=310.928 K, PUnit=psia, VisUnit=uPa*s). Viscosity model: Quinones-Cisneros, Huber & Deiters, unpublished work, 2011. EOS: Setzmann & Wagner, J. Phys. Chem. Ref. Data 20(6):1061-1151, 1991. | RETRIEVED this session (raw tab-delimited NIST output, 8 significant digits); LGE values COMPUTED this session |
| LGE K, X, Y intermediate values at T = 559.6704 deg R, M = 16.0425 lbm/lbmol (a direct unit test on the coefficient expressions, independent of density). | `T = 559.6704 deg R; M = 16.0425 lbm/lbmol` | `K = 118.3787, X = 5.3723, Y = 1.2522 (4 decimal places)` | Computed this session from the full-text-verified LGE equations | COMPUTED this session from retrieved coefficients |
| Isothermal gas compressibility of methane from NIST densities vs DAK + Mattar-Brar-Aziz analytic route, at 1000 psia and 310.928 K. | `NIST densities at 310.928 K: [reference values withheld -- see docs/release/PUBLIC_DATA_POLICY.md; re-acquire locally with scripts/fetch_nist_reference.py to run this check] ` | `c_g from the NIST reference densities: [reference values withheld -- see docs/release/PUBLIC_DATA_POLICY.md; re-acquire locally with scripts/fetch_nist_reference.py to run this check] ` | NIST Chemistry WebBook methane isotherm (retrieved); DAK A1-A11 and MBA chain rule (implemented this session) | NIST densities RETRIEVED this session; c_g values COMPUTED this session |
| Analytic dZ/d rho_r vs central finite differences of the explicit DAK polynomial (pure math check, no physics). | `T_pr in {1.05, 1.3, 1.8, 2.5}; rho_r in {0.1, 0.5, 1.0, 1.6}; h = 1e-6` | `Relative error between the analytic D and the central difference must be <= 1e-8. Measured this session: 7e-12 to 1e-8 (worst case is at T_pr=1.3, rho_r=1.0 where D crosses zero at D = 2.647e-4, so use ABSOLUTE tolerance there, not relative). Sample values: D(T_pr=1.05, rho_r=0.1) = -1.0725741442; D(1.8, 1.0) = 0.3389463178; D(2.5, 1.6) = 1.6740364205.` | Derived and computed this session | COMPUTED this session |
| Analytic c_pr (Mattar-Brar-Aziz through DAK) vs central finite differences on the converged DAK root solve. | `T_pr in {1.05, 1.2, 1.5, 2.0, 3.0}; p_pr in {0.5, 1.5, 3.0, 6.0, 12.0, 25.0}; FD step h = 1e-5 * p_pr on c_g = 1/p_pr - (1/Z) dZ/dp_pr` | `Relative agreement 5e-13 to 2e-9 across all 30 combinations. Sample anchor values computed this session: (T_pr=1.5, p_pr=3.0) -> Z = 0.77613, rho_r = 0.6958, c_pr = 0.36124438; (T_pr=2.0, p_pr=6.0) -> Z = 0.98567, rho_r = 0.8218, c_pr = 0.13612169; (T_pr=1.2, p_pr=1.5) -> Z = 0.65324, rho_r = 0.5167, c_pr = 1.04176170.` | Implemented and computed this session from the full-text-verified DAK coefficients | COMPUTED this session; the DAK coefficients feeding it were RETRIEVED |
| Ideal-gas degenerate case for c_g. | `Force Z = 1, dZ/dp = 0 at any p` | `c_g = 1/p exactly. And c_pr = 1/p_pr exactly. Observed in the high-T_pr, low-p_pr corner of the numeric sweep: at T_pr = 3.0, p_pr = 0.5, Z = 0.99845 and c_pr = 2.00170 vs 1/p_pr = 2.00000.` | Elementary; confirmed numerically this session | COMPUTED this session |
| Sign/ordering check on c_g vs 1/p (catches a wrong sign on the dZ/dp term). | `gamma_g = 0.65 gas, T = 180 deg F, Standing pseudocriticals (T_pc = 373.97 deg R, p_pc = 670.91 psia)` | `At 500 psia (Z falling with p): c_g = 2.0898e-3 > 1/p = 2.0000e-3. At 3000 psia (Z rising with p): c_g = 3.0019e-4 < 1/p = 3.3333e-4. At 8000 psia: c_g = 5.2272e-5 << 1/p = 1.2500e-4. If your c_g is always below 1/p, or always above, the sign of the dZ/dp term is wrong.` | Computed this session; the Standing pseudocritical correlation used (T_pc = 168 + 325g - 12.5g^2, p_pc = 677 + 15.0g - 37.5g^2) is RECALLED and NOT verified - treat the absolute numbers as illustrative, the ordering/sign as the real assertion | COMPUTED this session on a RECALLED pseudocritical correlation |
| Z-factor vs NIST for pure methane (sanity on DAK applied outside its intended mixture domain). | `methane, 310.928 K, T_pr = 1.63162; p = 500/1000/2000/3000 psia` | `Z from the reference densities: [reference comparison withheld -- the reference values and the pointwise deviations against them are excluded from this release under docs/release/PUBLIC_DATA_POLICY.md; re-acquire the extract locally with scripts/fetch_nist_reference.py to run this check]. Z from DAK: 0.94567 / 0.89791 / 0.84021 / 0.84695. The comparison itself is withheld for the same reason. This is EXPECTED - DAK was fitted to the Standing-Katz natural-gas chart, not to pure methane. Do not use this as a DAK accuracy claim.` | reference densities acquired locally; Z back-calculated with R = 10.731577 and the exact 62.42796 conversion | reference densities acquired locally and not redistributed; Z values computed from them |

## Adversarial review

### Corrections

**LGE 'rounded/simplified' variant — X equation molecular-weight coefficient** — severity high — this is the one defect that would ship as a silent numerical bug; error reaches -10% for rich gas and the card explicitly instructs the implementer to expose it as a named production variant, confidence high

- Claimed: X = 3.5 + 986/T + 0.001*M. Card asserts: 'Note 0.001*M in X vs 0.01009*M in the original - that is a 10x difference, not a rounding. It is a genuinely different parameterisation.' Baked into failure_modes and into implementation_notes as the shipping spec for variant 'lge_rounded'.
- Correct: X = 3.5 + 986/T + 0.01*M. pengtools is a transcription typo; the card faithfully copied the typo but then elevated it to a claimed second parameterisation. There is no 'genuinely different parameterisation' — the rounded form is exactly what its name says.
- Evidence: Penn State PNG 520 course page (courses.ems.psu.edu/png520/m19_p4.html, independent of pengtools) prints verbatim: kv = (9.4 + 0.02MWg)T^1.5/(209 + 19MWg + T); xv = 3.5 + 986/T + 0.01MWg; yv = 2.4 - 0.2xv. WebSearch returns the same 0.01M form from multiple further sources. Numerical discrimination computed this session: over the LGE fitted window (M 16-30, T 560-800 degR, rho 0.01-0.30 g/cm3) the rounded form with 0.01M departs from the original by at most 6.5%, while with 0.001M it departs by up to 17.8%. Point value at M=30, T=700 degR, rho=0.28: original 0.032949 cp, rounded-0.01M 0.031556 cp, rounded-0.001M 0.028379 cp — the 0.001M form is 10.1% below the 0.01M form. A rounding of 0.01009 to 0.01 is coherent; to 0.001 it is not. Note also the card applied asymmetric scepticism: it correctly rejected nafta.wiki's 3.488 as a typo but accepted pengtools' 0.001 at face value and reasoned outward from it.

**implementation_notes — recommended physical-range assertion on Z** — severity medium-high — self-inconsistent; the shipped guard fires on valid input, confidence high

- Claimed: 'Assert physical ranges rather than trusting callers: ... 0.2 <= Z <= 2.5'
- Correct: Upper bound must be at least 3.4 (or the assert must be scoped to a narrower p_pr band). DAK returns Z > 2.5 at points inside the card's own declared validity box and inside its own published c_pr sweep.
- Evidence: Computed this session by sweeping the card's own declared DAK box (1.0 <= T_pr <= 3.0, 0.2 <= p_pr <= 30.2, 201x301 grid): max Z = 3.3056 at (T_pr, p_pr) = (1.0, 30.2). Worse, the card's own numerical_pitfalls entry cites (T_pr, p_pr) = (1.05, 25) — I reproduce Z = 2.71816 there, which also violates the assert. The card would therefore raise on a legal, in-range input that it itself exercises.

**access_level labelling — LGE sour-gas / H2S exclusion** — severity medium — the engineering advice is right, the provenance label is false, which is exactly the failure mode the card was written to prevent, confidence high

- Claimed: validity_ranges: 'H2S is NOT covered - the correlation cannot be used for sour gases. VERIFIED full-text.' Also equations block: 'LGE is stated to be inapplicable to sour gases', sourced to SPE 75721.
- Correct: The substantive claim is almost certainly true, but it is NOT verified full-text in SPE 75721. It should be labelled 'recalled / secondary — not retrieved'.
- Evidence: I extracted the full text of the card's own cited PDF (SPE_075721_(Londono)_Gas_Density_y_Viscosity.pdf, 45,802 chars via pypdf) and searched it directly. The string 'sour' appears 0 times. 'H2S' appears exactly 1 time, in the nomenclature list ('yN2, CO2, H2S = Mole fraction of the non-hydrocarbon component'), not in any statement about LGE applicability. The LGE limitations paragraph that IS present states only specific gravity below 1.0, 100-8,000 psia, 100-340 degF, and CO2 to 3.2 mole percent. This is a direct violation of the card's own Rule 2.

**access_level labelling — Dempsey attributed via SPE 75721** — severity low-medium — scoping error in the source table, confidence high

- Claimed: SPE 75721 is listed as supporting 'the description of Carr-Kobayashi-Burrows as a two-step chart procedure' and the card repeatedly leans on it for the CKB/Dempsey lineage.
- Correct: SPE 75721 supports the CKB two-step structure only. It says nothing whatsoever about Dempsey.
- Evidence: Full-text search of the extracted PDF: 'Dempsey' appears 0 times. The CKB structural claim IS supported verbatim ('Carr, et al.2 developed a two-step procedure to estimate hydrocarbon gas viscosity. The first step is to determine the gas viscosity at atmospheric conditions...'), so that half of the card's claim stands.

**Meaning and units of the LGE 1e-4 factor and of K** — severity low — no numerical impact, but it is a wrong unit statement in a card whose stated purpose is unit discipline, confidence high

- Claimed: assumptions: 'The 1e-4 factor is part of the correlation, not a unit conversion; mu_g comes out directly in cp.' Symbol table gives K units as 'dimensionless as used; the 1e-4 carries the cp scaling'.
- Correct: The 1e-4 IS precisely a unit conversion. K carries units of micropoise (uP); 1 uP = 1e-4 cP exactly, so 1e-4 converts the correlation's native uP output to cP. K is not dimensionless.
- Evidence: The original LGE correlation is published with mu in micropoise — WebSearch returns the standard statement 'mu = K*exp(X*rho^y) ... with mu in micropoise, rho as density in g/cm3'. SPE 75721 then writes mu_g = 1e-4 * K * exp(X*rho^Y) with 'mu_g = Gas viscosity at temperature and pressure, cp' (confirmed verbatim in my own extraction). The factor 1e-4 is exactly the uP->cP ratio. No numerical consequence, but the card makes an affirmative and incorrect unit statement and mislabels a symbol.

**Dimensional homogeneity of LGE** — severity low — but a petroleum-engineer reviewer will probe exactly this, and the honest answer is stronger than the fudge, confidence high

- Claimed: X units given as '(g/cm3)^(-Y), effectively dimensionless as used'; Y equation's symbol table then declares X 'dimensionless'.
- Correct: LGE is dimensionally INHOMOGENEOUS and should be stated as such. X*rho^Y must be dimensionless, requiring X to carry (g/cm3)^(-Y); but Y = 2.447 - 0.2224*X requires X to be a bare number. Both cannot hold. LGE is a unit-locked empirical fit with no dimensional consistency — that, not convention, is the real reason rho must be g/cm3 and T must be degR.
- Evidence: Dimensional analysis performed this session. The card's two symbol tables contradict each other on the same symbol (X) and the phrase 'effectively dimensionless as used' papers over the contradiction rather than naming it. Same applies to K (T^1.5 over a sum of degR and dimensionless M-terms) and to the X equation (3.448 dimensionless + 986.4/T in degR^-1 + 0.01009*M per lbm/lbmol added together).

**Claimed AAE values discriminating 3.448 from 3.488** — severity low — conclusion right, supporting argument weaker than presented, confidence high

- Claimed: a specific pair of error statistics against the reference extract, discriminating 3.448 from 3.488.
- Correct: recomputing from the exact reference rows shifts both statistics slightly, and the recomputed values are excluded from this release under docs/release/PUBLIC_DATA_POLICY.md. More importantly, this test is weak evidence and is oversold.
- Evidence: I re-retrieved the NIST isotherm at 310.928 K myself and recomputed. The card used its own rounded transcriptions for the 2500 and 3000 psia points rather than the retrieved values, which shifts the statistic; both the transcriptions and the retrieved values are excluded from this release under docs/release/PUBLIC_DATA_POLICY.md. Substantively: LGE's own bias against the reference sits well above the gap between the two candidate constants, so that gap is inside the correlation's own systematic error and cannot cleanly discriminate them. The 3.448 value is nonetheless CORRECT — but on documentary grounds, not numerical ones (see unverified_items note on my own extraction).

**Fabricated trailing precision in the Dempsey constants table** — severity low-medium — no realistic numerical impact, but it is the card's own stated cardinal sin, confidence high

- Claimed: a2 = -0.286264054, a3 = 0.00805420522, a7 = -0.0104432413, a11 = 0.00441015512, a15 = -0.000609579263 — presented as table entries with the prose noting rNodal prints fewer digits.
- Correct: Truncate to the 8 significant figures actually sourced (-0.28626405, 0.00805420, -0.01044324, 0.00441016, -0.00060958). The extra digits exist in no retrieved source.
- Evidence: The card's own uncertainties section admits 'The digits beyond 8 significant figures ... are not retrieved.' Rule 1 forbids inventing a coefficient; carrying unsourced digits into the constants table — the exact artefact an implementer copy-pastes from — violates it regardless of the prose caveat. WebSearch independently returns only the 8-s.f. forms (a0 = -2.46211820, a1 = 2.97054714, a2 = -0.28626405, a3 = 0.00805420 ... a15 = -0.00060958).

**Provenance of the 62.37 constant** — severity low — card's action item is right; adding the provenance prevents a downstream mis-'fix', confidence medium

- Claimed: 'The LGE source paper (and SPE 75721 Eq. 8) prints 62.37, which is 0.093% low' — implicitly treated as a sloppy conversion factor.
- Correct: 62.37 is not a botched g/cm3 conversion; it is the density of water at 60 degF (999.0 kg/m3 = 62.366 lbm/ft3). SPE 75721's nomenclature line does label it '62.37 = Conversion constant: 1 g/cc = 62.37 lbm/ft3', which is wrong as written, but knowing the provenance matters: an implementer must not 'correct' 62.37 to 62.428 in any context where specific gravity relative to water at 60 degF is actually intended.
- Evidence: Extracted verbatim from the card's own cited PDF: 'R = Universal gas constant, 10.732 (psia cu ft)/(lb-mole deg R); 62.37 = Conversion constant: 1 g/cc = 62.37 lbm/ft3'. Water at 60 degF = 999.0 kg/m3 = 62.366 lbm/ft3. The card's recommendation (use the exact 62.427960576 in the p,M,z,T density path) is correct and I confirm the exact value: 30.48^3/453.59237 = 62.427960576144606.

**Missing validity constraint — CKB non-hydrocarbon content limit** — severity medium — a correlation used outside its fitted range is a defect, and this range is simply absent, confidence medium

- Claimed: CKB validity given only as 'roughly 32-400 degF and reduced pressure below 20 (per a secondary source; unverified)'.
- Correct: Add the non-hydrocarbon concentration ceiling: CO2, N2 and H2S each below ~15 mol%. The card ships the N2/CO2/H2S correction equations with no upper bound on their arguments.
- Evidence: WebSearch on the CKB correlation returns: 'The correlation was published in 1954 and is valid between temperatures of 32 degF to 400 degF, reduced pressures below 20, and CO2, N2, and H2S concentrations below 15%.' Secondary, but it closes a gap the card leaves completely open — the card's failure_modes flags extrapolating LGE outside its window but never bounds the CKB non-hydrocarbon mole fractions, which is the whole reason one reaches for CKB over LGE.

**Missing validity caveat — DAK behaviour at T_pr = 1.0** — severity low-medium — the card demonstrates numerical convergence at a point where the correlation is documented to be inaccurate, which risks reading as validation, confidence medium

- Claimed: numerical_pitfalls cites '(T_pr, p_pr) = (1.0,1.0)' as a case where a single sign-change root was found and bracketing bisection is safe, with no accuracy caveat.
- Correct: DAK is documented to give poor results at T_pr = 1.0 with p_pr > 1.0, and T_pr = 1.0 is on the open boundary of the stated range (1.0 < T_pr < 3.0, so T_pr = 1.0 is excluded). Root existence is not accuracy.
- Evidence: WebSearch: 'The Dranchuk-Abou-Kassem correlation has an average absolute error of 0.486% for 0.2 < Ppr < 30 and 1.0 < Tpr < 3.0, and for Ppr < 1.0 with 0.7 < Tpr < 1.0. However, there are poor results for Tpr = 1.0 and Ppr > 1.0.' This also independently confirms the card's 0.7 < T_pr < 1.0 / p_pr <= 1.0 clause that the card had marked RECALLED, upgrading it to secondary-confirmed.

### Left unverified

- N2/CO2/H2S atmospheric-viscosity corrections (8.48e-3/9.59e-3 for N2; 9.08e-3/6.24e-3 for CO2; 8.49e-3/3.73e-3 for H2S). I made two independent retrieval attempts this session (targeted WebSearch on the literal coefficient values; WebFetch of the IJSEI sour-gas viscosity paper, which returned HTTP 403). Neither produced a source. The card's own UNVERIFIED label STANDS and is confirmed after independent effort. Do not ship these without retrieving JCPT 86-01-03.
- Dempsey a0..a15 remain backed only by one open-source R implementation (rNodal) plus a WebSearch summary echoing the same 8-s.f. values. Two secondary sources that may share an ancestor are not independent corroboration. Primary (Dempsey 1965 OGJ, or JCPT 86-01-03) still not retrieved.
- The Dempsey polynomial's algebraic GROUPING is now upgraded from 'recalled' to weak-secondary but is still not primary-sourced. The rNodal source line 'visc.gas <- visc.base / temp.pr * exp(visc.r)' does confirm the card's claim that the LHS is ln(T_pr * mu/mu_1) and that one divides by T_pr after exponentiating. Which a-coefficient pairs with which power of T_pr remains unconfirmed against any source.
- Standing pseudocritical correlation (T_pc = 168 + 325g - 12.5g^2, p_pc = 677 + 15.0g - 37.5g^2). Not retrieved this session. I verified only internal consistency: at g=0.65 it reproduces the card's T_pc = 373.97 degR and p_pc = 670.91 psia exactly. Provenance unverified — and this correlation feeds T_pr and p_pr and therefore every c_g number in the card.
- c_w (brine compressibility) magnitudes ~2e-6 to 4e-6 /psi. Still secondary/recalled. Not attempted this session; card's UNVERIFIED label stands.
- c_f (pore-volume compressibility) magnitudes ~3e-6 to 30e-6 /psi, attributed to Hall (1953) and Newman (1973). Neither primary retrieved. Card's UNVERIFIED label stands.
- Air molar mass for the M = 28.96xx * SG_g conversion. The card's equation header uses 28.9625, its assumptions cite 28.96546 (CIPM-2007) and note pengtools uses 28.967 — three different values in one card entry, none verified against a petroleum standard. Spread is immaterial (<0.02%) but the card is internally inconsistent about which one it is recommending.
- The primary Lee-Gonzalez-Eakin JPT 1966 paper itself remains unretrieved (OnePetro 403 for the card; I did not re-attempt). All original LGE coefficients rest on SPE 75721's reproduction. I independently confirmed that reproduction (see below), so confidence is high, but it is still one primary source removed.
- My own confirmation of the LGE X constant as 3.448 carries a caveat: the SPE 75721 PDF text layer emits equation digit-runs in reversed token order. The X equation extracts as '..X  0.0100949864483', which parses unambiguously as {0.01009}, {986, 4}, {448, 3} = X = 3.448 + 986.4/T + 0.01009*M, and the string '3.488' appears nowhere in the 45,802-character extraction. I read this as decisive, but it is a reconstruction from a scrambled text layer, not a clean read of rendered glyphs. The K, Y and DAK coefficient blocks extracted cleanly and unambiguously and need no such caveat.
- LGE has been validated in this card ONLY against pure methane. Every external check in the card (viscosity, density, Z, c_g) is a single pure component at a single temperature (310.928 K). LGE is a natural-gas-MIXTURE correlation; no mixture worked example was retrieved by the card or by me.

### Missing before implementation

- Pseudocritical property correlation (Standing or Sutton) plus the Wichert-Aziz sour-gas correction. The card explicitly scopes these out, but T_pr and p_pr are inputs to DAK and therefore to every c_g in the card — c_g cannot be computed at all without them. This is not an optional sibling card; it is a hard dependency and the card's own MINUS section concedes it. Ship it first or ship neither.
- A primary source for Dempsey a0..a15 AND the three non-hydrocarbon corrections before any CKB path is exposed. JCPT 86-01-03 ('A Mathematical Representation Of The Carr, Kobayashi And Burrows Natural Gas Viscosity Correlations') is the retrievable citable source; Dempsey 1965 is an OGJ trade article. Until then the CKB path must be marked UNVERIFIED and, ideally, not exported.
- Decide and pin ONE air molar mass, and make the card internally consistent about it (currently 28.9625 in the equation, 28.96546 in the assumption, 28.967 in the cross-reference).
- Corrected 'lge_rounded' variant definition using 0.01*M, plus a cross-variant agreement test (see oracles) so the two named variants can never silently diverge again.
- Recalibrated range assertions. Sweep the declared DAK box and set the Z bound from measurement, not intuition (max Z = 3.3056 over 1.0 <= T_pr <= 3.0, 0.2 <= p_pr <= 30.2). Same exercise for the mu_g and rho_g bounds, which were not checked at all.
- CKB non-hydrocarbon ceiling (~15 mol% each for N2, CO2, H2S) as an enforced input bound on the correction terms.
- A real c_w correlation (Osif 1988, or Dodson-Standing) and a real c_f correlation (Hall 1953 / Newman 1973) as equations with fitted ranges — not magnitude bands. The card's own c_t sensitivity result (c_w + c_f are ~11% of c_t at 8000 psia) is precisely the argument for why a band is not good enough here.
- At least one LGE validation point on a gas MIXTURE from a published worked example, to cover the domain LGE was actually fitted for. All present external validation is pure methane.
- A specified Z-solver contract near T_pr -> 1.0: bracketing strategy, tolerance (the card correctly argues for 1e-12 relative before differentiating), and an explicit refusal or warning at T_pr = 1.0 with p_pr > 1.0 where DAK is documented to be poor.

### Recommended independent test oracles

**LGE vs NIST methane viscosity, 500-3000 psia at 100 degF**

- Inputs: `M = 16.0425 lbm/lbmol, T = 559.6704 degR; rho from [reference values withheld -- see docs/release/PUBLIC_DATA_POLICY.md; re-acquire locally with scripts/fetch_nist_reference.py to run this check] `
- Expected: `LGE evaluated on the reference densities [values withheld: LGE is strictly monotonic in density at fixed M and T, so publishing this side of the comparison would invert back to the reference densities themselves] against the reference values [reference comparison withheld -- the reference values and the pointwise deviations against them are excluded from this release under docs/release/PUBLIC_DATA_POLICY.md; re-acquire the extract locally with scripts/fetch_nist_reference.py to run this check]. With the extract present, assert every point within the tolerance the protocol declares and assert the bias is POSITIVE at every point; without it, report this check as not run. The reference side of this check is not reproduced here.`
- Why independent: The reference values come from an external reference-quality EOS and viscosity model (Setzmann-Wagner 1991; Quinones-Cisneros-Huber-Deiters 2011), computed by NIST, with no LGE content whatsoever. It exercises the density conversion, the degF->degR conversion, the K/X/Y expressions and the exponential simultaneously. The sign assertion is the sharp part: LGE's known systematic under-prediction at high viscosity means the bias must be consistently positive here, so a sign or coefficient error breaks the PATTERN and not merely the magnitude.

**Cross-variant agreement: lge_1966 vs lge_rounded**

- Inputs: `Grid M in {16, 18, 20, 22, 25, 28, 30} lbm/lbmol, T in {560, 620, 680, 740, 800} degR, rho in {0.01, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30} g/cm3 — i.e. the LGE fitted window`
- Expected: `max |mu_rounded/mu_original - 1| <= 0.08 across the whole grid. Measured this session: with the CORRECT 0.01*M the worst case is 6.5 percent; with the erroneous 0.001*M it is 17.8 percent. Set the gate at 8 percent so the correct coefficient passes and the typo fails.`
- Why independent: It is a consistency identity between two independently published parameterisations of the same physics, requiring no external data at all and no appeal to either source's authority. Critically, THIS IS THE ORACLE THAT CATCHES THE DEFECT FOUND IN THIS REVIEW — a 'rounded' correlation that disagrees with its parent by 18 percent is definitionally not a rounding, and the test says so without needing anyone to re-read pengtools. Add it precisely because the card's review process failed here.

**Zero-density closed-form limit of LGE (isolates K from X and Y)**

- Inputs: `rho_g = 0 exactly, any M and T in range; e.g. M = 16.0425, T = 559.6704 degR`
- Expected: `mu_g -> 1.0e-4 * K exactly, since exp(X * 0^Y) = exp(0) = 1 for Y > 0. At these inputs K = 118.3787 so mu_g = 0.01183787 cp, to machine precision. Assert also that Y > 0 over the full declared (M, T) box so the limit is well posed.`
- Why independent: A closed-form analytic limit of the correlation, not a restatement of it. It tests the K expression ALONE with the exponential branch switched off, so a transposed digit in 9.379 / 0.01607 / 209.2 / 19.26 is exposed without any contamination from X or Y — something the card's own 'K, X, Y intermediate values' check cannot do (see circularity note). It also pins the 1e-4 factor in isolation and doubles as the guard for the 0**negative hazard the card flags.

**Unit-error tripwire: lbm/ft3 fed into LGE**

- Inputs: `Pass any reservoir methane density in lbm/ft3 -- 3.0 lbm/ft3 is representative and is used here so the tripwire depends on no withheld value -- straight into the g/cm3 slot`
- Expected: `mu_g of order 1e7 cp. The magnitude is quoted to one figure deliberately: the mis-called correlation is so steep that a viscosity given to three figures would invert back to the density that produced it, and at this state that density is a reference value this release does not publish. Reproduce the exact figure locally from the invented density above. The implementation must REJECT this via an input-domain assert on rho (reservoir gas is ~0.005-0.35 g/cm3) rather than returning a finite nonsense number.`
- Why independent: A dimensional identity test, independent of any coefficient value: it asserts on the structure of the failure (no exception, no overflow, just a silently absurd magnitude) rather than on a numeric result. Because 62.428 is the only thing separating the two unit systems, this is the single highest-yield guard in the whole module, and it works even if every coefficient is wrong.

**Ideal-gas analytic limit for c_g (forced, not sampled)**

- Inputs: `Force Z == 1 and dZ/dp == 0 identically at arbitrary p; separately, force Z == 1 in the MBA expression by setting D = 0`
- Expected: `c_g = 1/p to machine precision (relative error < 1e-15), and c_pr = 1/p_pr to machine precision.`
- Why independent: An exact closed-form thermodynamic limit of c_g = -(1/V)(dV/dp)_T with V = nZRT/p, derivable on paper in two lines with no correlation involved. NOTE: this replaces the card's version, which is partly circular — the card quotes (T_pr = 3.0, p_pr = 0.5) -> c_pr = 2.00170 as the evidence, but that number is produced by the very DAK+MBA code under test (I reproduce it exactly: Z = 0.998450, c_pr = 2.00170143). Only the FORCED limit is a genuine oracle; the sampled near-ideal point is a regression fixture.

**c_g from NIST methane densities vs DAK+MBA analytic route**

- Inputs: `NIST densities at 310.928 K: [reference values withheld -- see docs/release/PUBLIC_DATA_POLICY.md; re-acquire locally with scripts/fetch_nist_reference.py to run this check] `
- Expected: `c_g from the reference densities via c_g = (1/rho)(drho/dp)_T, at two step sizes with a Richardson extrapolation: values excluded from this release, because a quantity derived from the extract is not exempt under docs/release/PUBLIC_DATA_POLICY.md, and neither is the agreement statistic against it. DAK+MBA analytic: 1.095779e-3 /psi (Z = 0.89791). With the extract present, assert the two routes agree within 2 percent, and compare against the ideal-gas 1/p = 1.000e-3 to prove the test has resolving power; without it, report this check as not run.`
- Why independent: The reference c_g is differentiated from externally measured/EOS-computed DENSITIES, never touching DAK, MBA, or the z-factor concept. It validates the physics end-to-end. The ideal-gas comparison is the positive control: it shows the 2 percent gate is tight enough to detect a real error, since the naive answer misses by 8.6 percent. Dropping the (1 + (rho_r/Z)*D) denominator would blow well past the gate.

**Cross-correlation agreement on c_g: DAK+MBA vs Hall-Yarborough + finite difference**

- Inputs: `T_pr in {1.2, 1.5, 2.0, 2.5}, p_pr in {1, 3, 6, 10} — restricted to the region where both correlations are fitted`
- Expected: `c_g from the two routes agreeing within ~2-3 percent. Both correlations were fitted to the same Standing-Katz chart, so they must agree to roughly the sum of their fitting errors; they share no coefficients and no algebra.`
- Why independent: This is the test the card is MISSING and it is the important one. Every derivative check the card offers (analytic D vs finite differences; analytic c_pr vs finite-differenced DAK root solve) shares the DAK coefficients A1..A11 and the same Z solver with the implementation — so those confirm the chain rule and nothing else. A second, structurally unrelated z-correlation is the only cheap way to catch a wrong A-coefficient or a mis-stated reduced-density definition. I verified the card's chain rule is algebraically correct by re-deriving it independently, so this oracle is about the CONSTANTS, not the algebra.

**DAK Z against digitised Standing-Katz chart points**

- Inputs: `A handful of read-off points spanning 1.05 <= T_pr <= 2.5, 0.5 <= p_pr <= 15, retrieved from a published reproduction of the Standing-Katz chart (RETRIEVE BEFORE USE — I did not source chart points this session)`
- Expected: `Agreement consistent with DAK's published 0.486 percent AAE over 1,500 chart points; assert each point within ~1.5 percent. Do NOT reuse the card's pure-methane Z comparison for this purpose: DAK sits low against pure methane (this implementation returns 0.94567 / 0.89791 / 0.84021 / 0.84695; the reference side and the deviation against it are excluded from this release under docs/release/PUBLIC_DATA_POLICY.md), which is expected behaviour for a mixture correlation applied to a pure component and is NOT a DAK accuracy measurement.`
- Why independent: The Standing-Katz chart is the actual fitting target of DAK, so it is the only data against which DAK's stated accuracy is meaningful. It is external, published, and predates the implementation. This is the one oracle that can actually falsify an A-coefficient transcription.

**Boyle-crossover structural assertion on c_g vs 1/p**

- Inputs: `gamma_g = 0.65, T = 180 degF, Standing pseudocriticals (T_pc = 373.97 degR, p_pc = 670.91 psia); sweep p = 500 to 8000 psia`
- Expected: `c_g > 1/p wherever dZ/dp < 0, c_g < 1/p wherever dZ/dp > 0, with exactly ONE crossover, located at the Z minimum. Reproduced this session: 500 psia c_g = 2.0898e-3 > 2.0000e-3; 1000 psia 1.0759e-3 > 1.0000e-3; 2000 psia 5.2292e-4 > 5.0000e-4; 3000 psia 3.0019e-4 < 3.3333e-4; 5000 psia 1.2374e-4 < 2.0000e-4; 8000 psia 5.2272e-5 < 1.2500e-4. Assert the ordering and the uniqueness of the crossover, and assert that the crossover pressure coincides with argmin Z to within the sweep resolution.`
- Why independent: A qualitative thermodynamic structure argument that follows from c_g = 1/p - (1/Z)(dZ/dp)_T alone — it holds for ANY z-correlation and needs no reference values, so it survives even if every coefficient in the card is wrong. It pins the SIGN of the dZ/dp term, which no magnitude-based check does. Tying the crossover to argmin Z is the strengthening the card omits: the card's version only asserts the ordering at hand-picked pressures, which a sign error could coincidentally satisfy. Caveat: the absolute numbers inherit the UNVERIFIED Standing pseudocritical correlation, so assert only the ordering and the crossover location, never the values.

**Range-assert calibration sweep (guards the guards)**

- Inputs: `Full declared validity boxes: DAK 1.0 <= T_pr <= 3.0 and 0.2 <= p_pr <= 30; LGE 100-8000 psia and 100-340 degF with SG 0.55-1.0`
- Expected: `Record max/min of Z, rho_g and mu_g over each box and assert that every shipped range-guard admits the entire box. Measured this session for DAK: max Z = 3.3056 at (T_pr, p_pr) = (1.0, 30.2) — which FAILS the card's proposed 'assert 0.2 <= Z <= 2.5'. The guard must be widened (or scoped) before shipping.`
- Why independent: It is a self-consistency test between two independent artefacts of the card — its declared validity ranges and its proposed defensive asserts — rather than a test of the physics. Neither artefact is derived from the other, so the contradiction is detectable without any external source. This class of test catches the second defect found in this review, and should be standard for every card that ships both a validity range and an input guard.

## Sources

| Citation | Access level | Supports |
|---|---|---|
| Londono, F.E., Archer, R.A., Blasingame, T.A., 'Simplified Correlations for Hydrocarbon Gas Viscosity and Gas Density - Validation and Correlation of Behavior Using a Large-Scale Database', SPE 75721 (SPE Gas Technology Symposium, Calgary, 2002). | full-text retrieved | PRIMARY EVIDENCE for this card. Verbatim LGE Eqs. 4-7 with all coefficients (9.379, 0.01607, 209.2, 19.26, 3.448, 986.4, 0.01009, 2.447, 0.2224) and the 1e-4 factor; LGE units (g/cc, lb/lb-mole, deg R, cp); LGE validity 100-8000 psia and 100-340 degF; LGE accuracy 2% AAE low-p / 4% AAE high-p for SG<1.0, CO2 to 3.2 mol%; LGE AAE 3.34% on a 4,909-point modern database; the gas density Eq. 8 with R = 10.732 and the 62.37 conversion; DAK A1-A11; the description of Carr-Kobayashi-Burrows as a two-step chart procedure; Lee et al. 'refit' coefficients (k1=16.7175, k2=4.19188e-2, k3=1.40256, k4=212.209, k5=18.1349, x1=2.12574, x2=2063.71, x3=1.19260e-2, y1=1.09809, y2=-3.92851e-2, AAE 2.29%). |
| Lee, A.L., Gonzalez, M.H., Eakin, B.E., 'The Viscosity of Natural Gases', J. Pet. Tech. (Aug. 1966) 997-1000; Trans. AIME 234. SPE-1340-PA. | abstract/metadata only (OnePetro returned HTTP 403) | The primary correlation. NOT directly retrieved - all coefficients in this card come from SPE 75721's reproduction. |
| NIST Chemistry WebBook, SRD 69 - Thermophysical Properties of Fluid Systems: Methane (CAS 74-82-8), isothermal data at 310.928 K. | full-text retrieved | Retrieved 8-significant-digit density and viscosity for methane over the stated pressure range (values withheld from this repository; see the public data policy); methane Tc = 190.564 K, Pc = 667.06 psia, Dc = 162.66 kg/m3, acentric factor 0.01142; the EOS citation (Setzmann & Wagner 1991) with its density uncertainties; the viscosity model citation (Quinones-Cisneros, Huber & Deiters, unpublished, 2011) with its uncertainty ladder verbatim. |
| Setzmann, U. & Wagner, W., 'A New Equation of State and Tables of Thermodynamic Properties for Methane Covering the Range from the Melting Line to 625 K at Pressures up to 1000 MPa', J. Phys. Chem. Ref. Data 20(6):1061-1155, 1991. doi:10.1063/1.555898 | abstract/metadata only (cited verbatim by the NIST page) | The reference EOS NIST uses for methane density/thermodynamics. Density uncertainty 0.03% (p<12 MPa, T<350 K) rising to 0.07% (p<50 MPa). |
| Quinones-Cisneros, S.E., Huber, M.L. & Deiters, U.K., unpublished work, 2011 (as cited by NIST SRD 69). | abstract/metadata only (the citation itself is full-text retrieved from NIST; the work is unpublished) | The reference model NIST uses for METHANE VISCOSITY. Uncertainty <0.3% for 200-400 K at p<30 MPa; <2% elsewhere to 100 MPa; up to 5% for 100-500 MPa; 10% for 500-1000 MPa to 625 K; valid only when paired with the Setzmann-Wagner EOS. |
| Huber, M.L. et al. (2025), 'Correlation for the Viscosity of Methane (CH4) from the Triple Point to 625 K and Pressures to 1000 MPa', Int. J. Thermophysics. PMC12686087. | abstract/metadata only | Likely the published form of the methane viscosity model NIST currently serves as 'unpublished 2011'. NOT confirmed to be the same model - verify before citing it in place of the WebBook citation. |
| Dranchuk, P.M. & Abou-Kassem, J.H., 'Calculation of Z-Factors for Natural Gases Using Equations of State', J. Can. Pet. Tech. (Jul-Sep 1975) 14, 34-36. | abstract/metadata only (primary); coefficients full-text retrieved via two reproductions | A1-A11, the reduced-density definition rho_r = 0.27 p_pr/(Z T_pr), validity 1.0 < T_pr < 3.0 and 0.2 <= p_pr <= 30, AAE 0.486% on 1,500 points. |
| Condor Tarco, J., 'Dranchuk and Abou-Kassem Equation of State for Calculating Gas Z Factor Using Newton's and the Secant Numerical Methods', University of Regina project report. | full-text retrieved | SECOND independent full-text reproduction of the DAK equation structure (Eqs. 2.1-2.6: Z = 1 + c1 rho_r + c2 rho_r^2 - c3 rho_r^5 + c4, with c1..c4 explicit), A1-A11 to 5 decimals, R = 10.732, the 0.486%/1,500-point statement, and the validity range. Agrees exactly with SPE 75721. Note: this is a student project report - it is a CROSS-CHECK, not an authority. |
| Mattar, L., Brar, G.S. & Aziz, K., 'Compressibility of Natural Gases', J. Can. Pet. Tech. (Oct-Dec 1975) 14(4), PETSOC-75-04-08. | abstract/metadata only | The analytic route for c_pr expressed through dZ/d rho_r rather than dZ/d p_pr. The abstract confirms the structural claim; the algebra in this card was independently re-derived and numerically verified. |
| Carr, N.L., Kobayashi, R. & Burrows, D.B., 'Viscosity of Hydrocarbon Gases Under Pressure', Trans. AIME (1954) 201, 264-272. | Unverified — cited source not inspected - not retrieved (structural description retrieved via SPE 75721) | The two-step chart procedure (mu_1 at 1 atm from T and SG with non-hydrocarbon corrections; then mu/mu_1 from p_pr, T_pr). Chart-based; no closed form in the original. |
| Dempsey, J.R., 'Computer Routine Treats Gas Viscosity as a Variable', Oil & Gas Journal (Aug 16, 1965) 141-143. | Unverified — cited source not inspected - not retrieved | The 16-coefficient polynomial fit to the CKB viscosity-ratio chart. Coefficients here are from a secondary implementation only. |
| Dempsey-style mathematical representation: 'A Mathematical Representation Of The Carr, Kobayashi And Burrows Natural Gas Viscosity Correlations', J. Can. Pet. Tech. (1986) 25(1), PETSOC-86-01-03. | abstract/metadata only | An alternative published closed-form representation of CKB. Worth retrieving as the authoritative source for a CKB closed form, since Dempsey (1965) is an OGJ trade article and harder to cite. |
| pengtools wiki, 'Lee correlation'. | secondary source | The ROUNDED LGE variant (9.4/0.02/209/19/3.5/986/0.001/2.4/0.2), the combined density form rho = (1/62.428) 28.967 SG p /(z 10.732 T), and a stated range 560 <= T < 800 degR, 100 < p <= 8000 psia. Secondary - used here to document that a competing parameterisation exists, not as authority. |
| nafta.wiki glossary, 'Lee-Gonzalez-Eakin (1966) gas viscosity correlation'. | secondary source | Cross-check on the ORIGINAL coefficient set (agrees on 9.379/0.01607/209.2/19.26/986.4/0.01009/2.447/0.2224) and the 100-340 degF / 100-8000 psi range. IMPORTANT: it prints X = 3.488 (typo, should be 3.448) and omits the 1e-4 factor. Documented here as a known-bad transcription. |
| f0nzie, rNodal R package, R/gas_correlations.R. | secondary source | Numeric cross-check on Dempsey a0..a15 (to 8 s.f.) and the Standing atmospheric-viscosity coefficients 1.709e-5, 2.062e-6, 8.188e-3, 6.15e-3. Open-source implementation - a cross-check only, NOT an authority for a derivation. |
| ScienceDirect topic pages: 'Formation Compressibility', 'Total Compressibility', 'Rock Compressibility'. | secondary source | Typical magnitude ranges for c_f (3e-6 to 30e-6 psi^-1) and the qualitative statement that c_g dominates c_t in gas reservoirs. Aggregator content - UNVERIFIED for any quantitative claim; retrieve Hall (1953) / Newman (1973) before shipping numbers. |

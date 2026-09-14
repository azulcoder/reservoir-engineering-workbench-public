# Evidence card: Gas deviation factor correlations

> Each card records what an implementer needs, where it came from, and how far it was
> verified. A card is not an authority: it is a statement of evidence with its access
> level attached. Items marked unverified are unverified, and the implementation must
> treat them as such.

**Adversarial review verdict:** `SOUND_WITH_CORRECTIONS`  
**Corrections recorded:** 10  
**Items left unverified:** 12

> Reading order matters in this card. The body sections below are the *original* claims and
> are deliberately preserved; where a later review refuted one, the body statement is marked
> `[SUPERSEDED]` in place with a pointer to its correction rather than rewritten, so the
> audit trail survives. "Corrections recorded" therefore means recorded in the review
> section, not silently applied to the body above it. The header previously read
> "Corrections applied", which overstated what had happened to the body text.

## Summary

All three Z-correlations (DAK, HY, DPR) are fits to the same Standing-Katz chart, so a cross-correlation test measures the consistency of the fits, not physical correctness — and all three inherit the same chart limits. The functional forms of DAK and HY were verified against the full text of Whitson & Brulé, SPE Phase Behavior Monograph Vol. 20 Ch. 3 (retrieved in the 2026-09-13 source review) plus two independent reference implementations; the DAK A1..A11, HY and DPR A1..A8 coefficients all agree across sources. The analytic derivative dF/drho for DAK and DPR was checked numerically against central differences (max relative deviation 6.6e-9 over 80 points) — and I found a real typo (rhor^3 where rhor^2 belongs) in the DAK Fprime published by the R package `zFactor`, which many people have copied. An important numerical finding: naive Newton on the standard-form DAK/DPR residual (the one carrying the -R2/rho term) converged at 6150/6150 grid points, but naive Newton on HY failed (y left (0,1)) at 502/6150 points with y0=0.001 and at 1008/6150 with y0=0.0125*Ppr*t*exp(...) — HY must be damped/bracketed. The divergence between the correlations is concentrated in two zones: 1.05<=Tpr<=1.15 at low Ppr (HY deliberately "smoothed" the chart anomaly there; DAK-HY max |dZ| = 0.047, 16.3% relative) and Ppr > 25 (outside the HY fit; max |dZ| = 0.060). In the core band 1.2<=Tpr<=3.0, 0.2<=Ppr<=8 all three agree within |dZ| <= 0.0114 (<=2.02%), and DAK-DPR always track each other far more tightly (<=0.0037) than either tracks HY — so DAK vs DPR is not an independent test; DAK/DPR vs HY is the informative one.

## Equations

### Pseudo-reduced properties (definition)

```
Tpr = T / Tpc ;  Ppr = P / Ppc
```

*Unit system:* oilfield (field units)

| Symbol | Meaning | Units |
|---|---|---|
| `T` | ABSOLUTE temperature of the gas | deg R (Rankine) = deg F + 459.67 |
| `P` | ABSOLUTE pressure of the gas | psia (NOT psig; psia = psig + local atmospheric, commonly 14.696 psi) |
| `Tpc` | pseudocritical temperature of the mixture (corrected for sour gas if applicable) | deg R |
| `Ppc` | pseudocritical pressure of the mixture (corrected for sour gas if applicable) | psia |
| `Tpr, Ppr` | pseudo-reduced temperature and pressure | dimensionless |

Assumptions:

- Corresponding-states principle applied to a mixture via pseudocriticals (Kay's rule or a gravity correlation).
- Single-phase gas. Do not apply below the dewpoint of a gas-condensate at the prevailing T.
- If Wichert-Aziz correction is used, Tpr and Ppr MUST be formed from the CORRECTED Tpc' and Ppc', not the raw ones.

*Source:* Whitson, C.H. & Brulé, M.R., Phase Behavior, SPE Monograph Vol. 20, Ch. 3, Eq. 3.46  
*Access:* full-text retrieved

### Dranchuk & Abou-Kassem (1975) reduced density definition

```
rho_r = 0.27 * Ppr / (Z * Tpr)
```

*Unit system:* dimensionless (oilfield inputs)

| Symbol | Meaning | Units |
|---|---|---|
| `rho_r` | reduced density (rho/rho_c-like group; NOT a physical density) | dimensionless |
| `0.27` | the critical compressibility constant Zc assumed by the fit; it is a fixed constant of the correlation, not an adjustable parameter | dimensionless |
| `Z` | gas deviation (compressibility) factor | dimensionless |

Assumptions:

- 0.27 is hard-coded in the correlation; substituting a real mixture Zc invalidates the published coefficients.
- rho_r and Z are mutually defined, hence the correlation is implicit and must be iterated.

*Source:* Dranchuk & Abou-Kassem (1975); form confirmed against Whitson & Brulé Ch. 3, pengtools wiki, GasCompressibility-py DAK.py, zFactor R Dranchuk-AbouKassem.R  
*Access:* full-text retrieved (secondary reproductions); original JCPT paper NOT retrieved

### Dranchuk & Abou-Kassem (1975) eleven-coefficient Z equation

```
Z = 1 + (A1 + A2/Tpr + A3/Tpr^3 + A4/Tpr^4 + A5/Tpr^5) * rho_r + (A6 + A7/Tpr + A8/Tpr^2) * rho_r^2 - A9 * (A7/Tpr + A8/Tpr^2) * rho_r^5 + A10 * (1 + A11*rho_r^2) * (rho_r^2 / Tpr^3) * exp(-A11 * rho_r^2)
```

*Unit system:* dimensionless (Tpr, Ppr dimensionless; requires absolute T and P upstream)

| Symbol | Meaning | Units |
|---|---|---|
| `A1..A11` | the eleven fitted coefficients (see constants list) | dimensionless |
| `rho_r` | reduced density = 0.27*Ppr/(Z*Tpr) | dimensionless |
| `Tpr` | pseudo-reduced temperature | dimensionless |

Assumptions:

- Benedict-Webb-Rubin-type EOS fitted to 1500 points digitised from the Standing-Katz chart; it reproduces the CHART, not experimental data.
- Note that A9 multiplies the bracket (A7/Tpr + A8/Tpr^2), i.e. it reuses A7 and A8 — this is not a typo; there are only 11 independent coefficients.
- A11 appears in three places (the (1+A11*rho^2) factor and inside the exponential); it must be the same value in all three.

*Source:* Whitson & Brulé Ch. 3 (attribution + validity); coefficient/functional form cross-checked in 3 independent implementations  
*Access:* secondary source (three independent reproductions agree); original 1975 JCPT paper NOT retrieved

### DAK Newton-Raphson residual and its analytic derivative (recommended implementable form)

```
R1 = A1 + A2/Tpr + A3/Tpr^3 + A4/Tpr^4 + A5/Tpr^5
R2 = 0.27*Ppr/Tpr
R3 = A6 + A7/Tpr + A8/Tpr^2
R4 = A9*(A7/Tpr + A8/Tpr^2)
R5 = A10/Tpr^3

F(rho) = 1 + R1*rho - R2/rho + R3*rho^2 - R4*rho^5 + R5*rho^2*(1 + A11*rho^2)*exp(-A11*rho^2)

dF/drho = R1 + R2/rho^2 + 2*R3*rho - 5*R4*rho^4 + 2*R5*rho*exp(-A11*rho^2) * (1 + A11*rho^2 - A11^2*rho^4)

iterate rho_{k+1} = rho_k - F(rho_k)/F'(rho_k),  rho_0 = 0.27*Ppr/Tpr   (i.e. Z=1)
then  Z = R2 / rho
```

*Unit system:* dimensionless

| Symbol | Meaning | Units |
|---|---|---|
| `F(rho)` | residual; F = 0 at the solution. Obtained by substituting rho_r = R2/Z into the Z equation and multiplying through by 1 (keeping the -R2/rho pole). | dimensionless |
| `rho` | rho_r being solved for | dimensionless |
| `R1..R5` | temperature-only groups, computed once per (Tpr,Ppr) | dimensionless |

Assumptions:

- The bracket (1 + A11*rho^2 - A11^2*rho^4) is algebraically identical to the commonly published ((1 + 2*A11*rho^2) - A11*rho^2*(1 + A11*rho^2)); either is correct.
- KEEP the -R2/rho term rather than clearing the pole by multiplying through by rho: the 1/rho barrier is what keeps Newton from stepping to rho<=0 (verified numerically, see numerical_pitfalls).
- Convergence criterion |F| < 1e-13 or |delta rho| < 1e-13 is sufficient; observed mean 6.3 and max 20 iterations over 6150 grid points.

*Source:* Derivative derived here and verified numerically against central differences (max rel. dev. 6.6e-9 over 80 (Tpr,Ppr,rho) points); residual form matches Ahmed Eq. 3-41 as reproduced in zFactor R package  
*Access:* derived and numerically verified this session

### Hall & Yarborough (1973) implicit equation in reduced density y

```
t = 1/Tpr
alpha = 0.06125 * t * exp(-1.2*(1 - t)^2)
A = 14.76*t - 9.76*t^2 + 4.58*t^3
B = 90.7*t - 242.2*t^2 + 42.4*t^3
C = 2.18 + 2.82*t

f(y) = -alpha*Ppr + (y + y^2 + y^3 - y^4)/(1 - y)^3 - A*y^2 + B*y^C = 0

Z = alpha * Ppr / y
```

*Unit system:* dimensionless

| Symbol | Meaning | Units |
|---|---|---|
| `t` | reciprocal pseudo-reduced temperature, 1/Tpr | dimensionless |
| `y` | reduced density: the product of a van der Waals covolume and density. Physically confined to 0 < y < 1. | dimensionless |
| `alpha` | the 0.06125*t*exp(-1.2(1-t)^2) group; it appears BOTH in f(y) and in the recovery of Z — use the same value | dimensionless |
| `A, B, C` | temperature-dependent groups (some texts label them A2, A3, A4 with A1 = alpha) | dimensionless |

Assumptions:

- Based on the Carnahan-Starling hard-sphere EOS; the (y+y^2+y^3-y^4)/(1-y)^3 term is the hard-sphere repulsive part and has a pole at y = 1.
- The exponent on the last term is C = 2.18 + 2.82*t, so B*y^C is a NON-integer power — y must stay strictly positive or the power is undefined/complex.
- HY deliberately 'smoothed' an apparent discrepancy in the Standing-Katz chart for 1.05 <= Tpr <= 1.15; it therefore does NOT agree with DAK/DPR there by design.

*Source:* Whitson & Brulé, Phase Behavior, SPE Monograph Vol. 20, Ch. 3, Eqs. 3.42 and 3.43 (full text retrieved); coefficients independently confirmed in GasCompressibility-py hall_yarborough.py, zFactor R, nafta.wiki  
*Access:* full-text retrieved

### Hall & Yarborough analytic derivative df/dy for Newton iteration

```
df/dy = (1 + 4*y + 4*y^2 - 4*y^3 + y^4)/(1 - y)^4 - (29.52*t - 19.52*t^2 + 9.16*t^3)*y + (2.18 + 2.82*t) * (90.7*t - 242.2*t^2 + 42.4*t^3) * y^(1.18 + 2.82*t)

equivalently:  df/dy = (1 + 4y + 4y^2 - 4y^3 + y^4)/(1-y)^4 - 2*A*y + C*B*y^(C-1)
```

*Unit system:* dimensionless

| Symbol | Meaning | Units |
|---|---|---|
| `29.52, 19.52, 9.16` | exactly 2x the A-group coefficients (2*14.76, 2*9.76, 2*4.58) — a useful self-check | dimensionless |
| `1.18 + 2.82*t` | C - 1, the reduced exponent | dimensionless |

Assumptions:

- Recommended initial guess (Whitson & Brulé): y = 0.001, converging in 3 to 10 iterations for |f(y)| <= 1e-8.
- Alternative initial guess (Yarborough & Hall 1974, and the zFactor/pengtools implementations): y0 = 0.0125*Ppr*t*exp(-1.2*(1-t)^2), i.e. alpha*Ppr/4.9.
- BOTH initial guesses fail with unsafeguarded Newton on a substantial fraction of the domain — see numerical_pitfalls.

*Source:* Whitson & Brulé Ch. 3, Eq. 3.44 (full text retrieved); verified consistent with zFactor R Fprime  
*Access:* full-text retrieved

### Dranchuk, Purvis & Robinson (1974) eight-coefficient Z equation

```
rho_r = 0.27*Ppr/(Z*Tpr)

Z = 1 + (A1 + A2/Tpr + A3/Tpr^3)*rho_r + (A4 + A5/Tpr)*rho_r^2 + (A5*A6/Tpr)*rho_r^5 + A7*(rho_r^2/Tpr^3)*(1 + A8*rho_r^2)*exp(-A8*rho_r^2)
```

*Unit system:* dimensionless

| Symbol | Meaning | Units |
|---|---|---|
| `A1..A8` | the eight fitted coefficients (see constants list) | dimensionless |
| `A5*A6` | the rho^5 term coefficient is the PRODUCT A5*A6, not an independent coefficient | dimensionless |

Assumptions:

- Same BWR-type structure and the same 1500 Standing-Katz chart points as DAK; DPR is the predecessor that DAK was published to improve on.
- DPR is NOT statistically independent of DAK — they share fit data and near-identical structure. Numerically they track each other to |dZ| <= 0.011 across 0.2 <= Ppr <= 30.

*Source:* Coefficients confirmed in zFactor R Dranchuk-Purvis-Robinson.R and in predico AFA theory reference; equation form from Ahmed's Reservoir Engineering Handbook as reproduced in zFactor  
*Access:* secondary source (two independent reproductions agree); original IP 74-008 paper NOT retrieved

### DPR Newton residual and analytic derivative

```
T1 = A1 + A2/Tpr + A3/Tpr^3
T2 = A4 + A5/Tpr
T3 = A5*A6/Tpr
T4 = A7/Tpr^3
T5 = 0.27*Ppr/Tpr

F(rho) = 1 + T1*rho + T2*rho^2 + T3*rho^5 + T4*rho^2*(1 + A8*rho^2)*exp(-A8*rho^2) - T5/rho

dF/drho = T1 + 2*T2*rho + 5*T3*rho^4 + 2*T4*rho*exp(-A8*rho^2)*(1 + A8*rho^2 - A8^2*rho^4) + T5/rho^2

rho_0 = 0.27*Ppr/Tpr ;  Z = T5/rho
```

*Unit system:* dimensionless

| Symbol | Meaning | Units |
|---|---|---|
| `T1..T5` | temperature-only groups computed once per (Tpr,Ppr) | dimensionless |

Assumptions:

- Note dF/drho has +T5/rho^2 (positive) because F carries -T5/rho.
- The bracket (1 + A8*rho^2 - A8^2*rho^4) is identical to the published ((1 + 2*A8*rho^2) - A8*rho^2*(1 + A8*rho^2)).

*Source:* zFactor R Dranchuk-Purvis-Robinson.R (Fprime as published there is correct); verified numerically here  
*Access:* secondary source, numerically verified this session

### Standing (1977) pseudocriticals — DRY hydrocarbon gas (gamma_gHC <= 0.75)

```
TpcHC = 168 + 325*gamma_gHC - 12.5*gamma_gHC^2     [deg R]
PpcHC = 667 + 15.0*gamma_gHC - 37.5*gamma_gHC^2    [psia]
```

*Unit system:* oilfield (field units)

| Symbol | Meaning | Units |
|---|---|---|
| `gamma_gHC` | specific gravity of the HYDROCARBON portion of the gas relative to air at standard conditions | dimensionless |
| `TpcHC` | hydrocarbon pseudocritical temperature | deg R (absolute) |
| `PpcHC` | hydrocarbon pseudocritical pressure | psia (absolute) |

Assumptions:

- Applies to the HYDROCARBON fraction only. If N2/CO2/H2S are present, first strip them out via gamma_gHC = (gamma_g - (yN2*MN2 + yCO2*MCO2 + yH2S*MH2S)/Mair) / (1 - yN2 - yCO2 - yH2S), then recombine with Kay's rule (Whitson Eqs. 3.53, 3.54).
- **[SUPERSEDED — see the correction under "Adversarial review / Corrections", "Standing (1977) dry-gas pseudocritical pressure — constant term", below.]** ~~Constant term is 667, NOT 677. A 677 variant circulates in secondary sources and is wrong — see uncertainties.~~ The status is an **unresolved 667-versus-677 conflict**: Whitson & Brulé Eq. 3.48b prints 667, Ahmed's Reservoir Engineering Handbook Eq. 2-19 prints 677 and reproduces its own worked examples only with 677, and the original Standing (1977) was not retrieved. The library ships both as named variants and defaults to 677 (`gas_properties.STANDING_DEFAULT_VARIANT`). The original claim is kept in place, struck through, because the audit trail is the point of this card.
- Fitted to low-molecular-weight California natural gases with zero inorganic content.

*Source:* Whitson & Brulé, Phase Behavior, SPE Monograph Vol. 20, Ch. 3, Eqs. 3.48a/3.48b (full text retrieved), citing Standing (1977)  
*Access:* full-text retrieved

### Standing (1977) pseudocriticals — WET gas / gas-condensate (gamma_gHC > 0.75)

```
TpcHC = 187 + 330*gamma_gHC - 71.5*gamma_gHC^2     [deg R]
PpcHC = 706 - 51.7*gamma_gHC - 11.1*gamma_gHC^2    [psia]
```

*Unit system:* oilfield (field units)

| Symbol | Meaning | Units |
|---|---|---|
| `gamma_gHC` | specific gravity of the hydrocarbon portion; for gas-condensate use the WELLSTREAM gravity gamma_w, not the separator-gas gravity | dimensionless |
| `TpcHC` | hydrocarbon pseudocritical temperature | deg R |
| `PpcHC` | hydrocarbon pseudocritical pressure | psia |

Assumptions:

- Whitson & Brulé note this wet-gas Tpc form and Sutton's Tpc give 'basically the same results'; the three Ppc correlations diverge markedly for gamma_g > 0.85.
- Using separator-gas gravity instead of wellstream gravity for a condensate is a classic silent error.

*Source:* Whitson & Brulé Ch. 3, Eqs. 3.49a/3.49b (full text retrieved), citing Standing (1977)  
*Access:* full-text retrieved

### Sutton (1985) pseudocriticals for high-molecular-weight gases

```
TpcHC = 169.2 + 349.5*gamma_gHC - 74.0*gamma_gHC^2     [deg R]
PpcHC = 756.8 - 131*gamma_gHC - 3.6*gamma_gHC^2        [psia]
```

*Unit system:* oilfield (field units)

| Symbol | Meaning | Units |
|---|---|---|
| `gamma_gHC` | hydrocarbon specific gravity relative to air | dimensionless |
| `TpcHC` | hydrocarbon pseudocritical temperature | deg R |
| `PpcHC` | hydrocarbon pseudocritical pressure | psia |

Assumptions:

- Whitson & Brulé recommend Sutton over Standing for hydrocarbon pseudocriticals in general.
- Fitted with H2S = 0, N2 < 1 mol%, CO2 < 1 mol% (per nafta.wiki); apply Wichert-Aziz for anything sour.
- The linear coefficient is 131 in Whitson's reproduction but 131.07 in several implementations — see uncertainties. The difference is 0.05 psia at gamma=0.75, i.e. below implementation significance, but pick one and document it.

*Source:* Whitson & Brulé Ch. 3, Eqs. 3.47a/3.47b (full text retrieved), citing Sutton SPE 14265 (1985)  
*Access:* full-text retrieved

### Wichert & Aziz (1972) sour-gas pseudocritical correction

```
A = yCO2 + yH2S
B = yH2S

epsilon = 120*(A^0.9 - A^1.6) + 15*(B^0.5 - B^4)     [deg R]

Tpc' = Tpc - epsilon                                  [deg R]
Ppc' = Ppc * (Tpc - epsilon) / (Tpc + B*(1 - B)*epsilon)   [psia]
```

*Unit system:* oilfield (field units)

| Symbol | Meaning | Units |
|---|---|---|
| `yCO2, yH2S` | MOLE fractions (0..1) of CO2 and H2S in the mixture — not percent, not mass fractions | dimensionless |
| `epsilon` | pseudocritical temperature adjustment factor | deg R |
| `Tpc, Ppc` | UNCORRECTED mixture pseudocriticals (Whitson writes them T*pc, p*pc; they should come from Kay's mixing rule including the non-hydrocarbons, or from a gravity correlation applied to gamma_gHC then recombined) | deg R / psia |
| `Tpc', Ppc'` | corrected pseudocriticals to be used in Tpr and Ppr | deg R / psia |

Assumptions:

- The DENOMINATOR of the Ppc' expression uses the UNCORRECTED Tpc, while the numerator uses (Tpc - epsilon). Getting this backwards is the most common implementation bug.
- If yH2S = 0 but yCO2 > 0, epsilon is still non-zero (the first bracket survives) — the correction is not H2S-only.
- epsilon is identically zero when A = 0, and A^0.9 with A=0 must be handled without a domain error.
- A^0.9 - A^1.6 is NEGATIVE for A > 1, which cannot occur physically but can occur if percent is passed instead of fraction — guard the input.

*Source:* Whitson & Brulé Ch. 3, Eqs. 3.52a/3.52b/3.52c (full text retrieved), citing Wichert & Aziz (1972); form independently confirmed by midstreamcalculator.com  
*Access:* full-text retrieved

### Gas molecular weight and density from specific gravity

```
gamma_g = Mg / Mair        =>   Mg = 28.97 * gamma_g      [lbm/lbmol]
rho_g = P*Mg / (Z*R*T)     =   28.97 * P * gamma_g / (Z*R*T)   [lbm/ft^3]
```

*Unit system:* oilfield (field units)

| Symbol | Meaning | Units |
|---|---|---|
| `gamma_g` | gas specific gravity relative to air at the SAME standard conditions | dimensionless |
| `Mg` | apparent molecular weight of the gas | lbm/lbmol |
| `Mair` | molecular weight of air | lbm/lbmol |
| `R` | universal gas constant in oilfield units | psia*ft^3/(lbmol*deg R) |
| `P, T` | ABSOLUTE pressure and temperature | psia, deg R |

Assumptions:

- Mair = 28.97 is the value used by Standing, Sutton and Whitson & Brulé; use it for consistency with the gravity correlations even though GPA 2145 specifies 28.9625.
- For wet-gas / gas-condensate mixtures the WELLSTREAM gravity gamma_w must replace gamma_g.

*Source:* Whitson & Brulé Ch. 3, Eqs. 3.28 and 3.35 (full text retrieved)  
*Access:* full-text retrieved

## Constants

| Name | Value | Units | Source | How verified |
|---|---|---|---|---|
| DAK A1 | `0.3265` | dimensionless | pengtools wiki; GasCompressibility-py DAK.py; zFactor R; midstreamcalculator | Four independent reproductions agree exactly. Original JCPT 1975 paper NOT retrieved. |
| DAK A2 | `-1.0700` | dimensionless | same four sources | Four independent reproductions agree exactly. |
| DAK A3 | `-0.5339` | dimensionless | same four sources | Four independent reproductions agree exactly. |
| DAK A4 | `0.01569` | dimensionless | same four sources | Four independent reproductions agree exactly. |
| DAK A5 | `-0.05165` | dimensionless | same four sources | Four independent reproductions agree exactly. |
| DAK A6 | `0.5475` | dimensionless | same four sources | Four independent reproductions agree exactly. |
| DAK A7 | `-0.7361` | dimensionless | same four sources | Four independent reproductions agree exactly. |
| DAK A8 | `0.1844` | dimensionless | same four sources | Four independent reproductions agree exactly. |
| DAK A9 | `0.1056` | dimensionless | same four sources | Four independent reproductions agree exactly. |
| DAK A10 | `0.6134` | dimensionless | same four sources | Four independent reproductions agree exactly. |
| DAK A11 | `0.7210` | dimensionless | same four sources | Four independent reproductions agree exactly. Appears in three places in the equation; must be identical in all. |
| DAK reduced-density constant (critical Z assumed) | `0.27` | dimensionless | Whitson & Brulé Ch. 3; all reproductions | Full-text retrieved; same constant used by DPR. |
| HY alpha group | `alpha = 0.06125 * t * exp(-1.2*(1 - t)^2), t = 1/Tpr` | dimensionless | Whitson & Brulé Ch. 3, Eq. 3.42 | Full-text retrieved; confirmed against GasCompressibility-py, zFactor R, nafta.wiki. |
| HY A group (coefficient of -y^2) | `14.76*t - 9.76*t^2 + 4.58*t^3` | dimensionless | Whitson & Brulé Ch. 3, Eq. 3.43 | Full-text retrieved; three independent implementations agree. |
| HY B group (coefficient of +y^C) | `90.7*t - 242.2*t^2 + 42.4*t^3` | dimensionless | Whitson & Brulé Ch. 3, Eq. 3.43 | Full-text retrieved; three independent implementations agree. Note the sign pattern + - + (242.2 is subtracted). |
| HY C exponent | `2.18 + 2.82*t` | dimensionless | Whitson & Brulé Ch. 3, Eq. 3.43 | Full-text retrieved; three independent implementations agree. |
| HY derivative middle-term coefficients | `29.52*t - 19.52*t^2 + 9.16*t^3  (= 2 x the A group)` | dimensionless | Whitson & Brulé Ch. 3, Eq. 3.44 | Full-text retrieved; algebraically consistent with d(-A*y^2)/dy = -2*A*y. |
| DPR A1 | `0.31506237` | dimensionless | zFactor R; predico AFA theory reference | Two independent reproductions agree. Original IP 74-008 NOT retrieved. |
| DPR A2 | `-1.0467099` | dimensionless | zFactor R; predico AFA | Two independent reproductions agree. |
| DPR A3 | `-0.57832729` | dimensionless | predico AFA theory reference (also widely cited in journal literature) | CONFLICT: zFactor R publishes -0.57832720. Difference is 9e-8 absolute, Z effect < 1e-8. Use -0.57832729; document the variant. |
| DPR A4 | `0.53530771` | dimensionless | zFactor R; predico AFA | Two independent reproductions agree. |
| DPR A5 | `-0.61232032` | dimensionless | zFactor R; predico AFA | Two independent reproductions agree. |
| DPR A6 | `-0.10488813` | dimensionless | zFactor R; predico AFA | Two independent reproductions agree. |
| DPR A7 | `0.68157001` | dimensionless | zFactor R; predico AFA | Two independent reproductions agree. |
| DPR A8 | `0.68446549` | dimensionless | zFactor R; predico AFA | Two independent reproductions agree. |
| Standing dry-gas Tpc coefficients | `168, +325, -12.5` | deg R (constant and coefficients on gamma_g, gamma_g^2) | Whitson & Brulé Ch. 3, Eq. 3.48a | Full-text retrieved. Physical sanity check: at gamma = 16.043/28.97 = 0.5538 (methane) gives Tpc = 344.1 deg R vs methane Tc = 343.0 deg R. |
| Standing dry-gas Ppc coefficients | `667 or 677, +15.0, -37.5` | psia (constant and coefficients on gamma_g, gamma_g^2) | Whitson & Brulé Ch. 3, Eq. 3.48b gives 667; Ahmed, Reservoir Engineering Handbook, Eq. 2-19 gives 677 | **[SUPERSEDED] The original cell read `667, +15.0, -37.5`, sourced as "independently confirmed as 667 in Ahmed's Reservoir Engineering Handbook", with "two independent sources give 667" and "A 677 variant circulating in some notes is NOT supported". The Ahmed corroboration is false — Ahmed prints 677 — and the conflict is unresolved. See the correction below.** Both texts retrieved in full; the original Standing (1977) was not. The methane-gravity sanity check (663.8 psia against methane Pc 666.4) is a loose smoke test and is NOT a valid arbiter between the two values. The library ships both as named variants and defaults to 677. |
| Standing wet-gas Tpc coefficients | `187, +330, -71.5` | deg R | Whitson & Brulé Ch. 3, Eq. 3.49a | Full-text retrieved; also matches nafta.wiki. |
| Standing wet-gas Ppc coefficients | `706, -51.7, -11.1` | psia | Whitson & Brulé Ch. 3, Eq. 3.49b | Full-text retrieved; also matches nafta.wiki. |
| Sutton Tpc coefficients | `169.2, +349.5, -74.0` | deg R | Whitson & Brulé Ch. 3, Eq. 3.47a; nafta.wiki; GasCompressibility-py sutton.py | Three independent sources agree exactly. |
| Sutton Ppc coefficients | `756.8, -131 (variant: -131.07), -3.6` | psia | Whitson & Brulé Ch. 3, Eq. 3.47b (131); midstreamcalculator (131.0); GasCompressibility-py sutton.py and nafta.wiki (131.07) | CONFLICT between 131 and 131.07. Original SPE 14265 NOT retrieved. Effect: 0.053 psia at gamma = 0.75 (8e-5 relative). Pick one, document it, and do not let a cross-check test tolerance sit below this. |
| Wichert-Aziz epsilon coefficients | `120, exponents 0.9 and 1.6 on A = yCO2 + yH2S; 15, exponents 0.5 and 4 on B = yH2S` | deg R | Whitson & Brulé Ch. 3, Eq. 3.52c; midstreamcalculator; multiple textbook reproductions | Full-text retrieved; independently confirmed by a worked example that reproduces to 3 significant figures. |
| Universal gas constant R, oilfield units (literature value used by the correlations' own era) | `10.73146` | psia*ft^3/(lbmol*deg R) | Whitson & Brulé, Phase Behavior, SPE Monograph Vol. 20, Ch. 3, Eq. 3.23 | Full-text retrieved. Based on the pre-2019 R = 8.3143 J/(mol*K). |
| Universal gas constant R, oilfield units (computed from the 2019 SI exact definition) | `10.73157709 (10.7315770890)` | psia*ft^3/(lbmol*deg R) | Derived here from CODATA-2019 exact R = 8.31446261815324 J/(mol*K), psi = 6894.757293168361 Pa (exact from lbf and inch definitions), ft = 0.3048 m (exact), lbmol = 453.59237 mol (exact), deg R = K/1.8 (exact) | Computed this session with exact unit definitions. Differs from the literature 10.73146 by 1.1e-5 relative. Recommend 10.7316 for engineering work and 10.73157709 if you want SI-exact traceability; state which one the code uses. |
| Molecular weight of air (as used by Standing / Sutton / Whitson) | `28.97` | lbm/lbmol | Whitson & Brulé Ch. 3, Eq. 3.28 | Full-text retrieved. USE THIS ONE for consistency with the gravity-based pseudocritical correlations. |
| Molecular weight of air (GPA 2145 standard, modern) | `28.9625` | lbm/lbmol | GPA Standard 2145 (cited via secondary sources) | Secondary source only; GPA 2145 not retrieved. Effect on Mg at gamma = 0.65: 18.8305 vs 18.8256 lbm/lbmol (2.6e-4 relative). Do not mix it with 28.97 inside one calculation chain. |
| Standard molar volume check value | `379.5 (379.4828 at 60 deg F and 14.696 psia using R = 10.73157709; 379.3754 at 60 deg F and 14.70 psia using R = 10.73146)` | scf/lbmol | Whitson & Brulé Ch. 3, Eq. 3.27 gives 379.4 scf/lbmol | Computed this session; matches Whitson's 379.4. Sensitive to which psc you adopt (14.696 vs 14.70 vs 14.73) — state it. |

## Validity ranges

- DAK (1975), published window per pengtools wiki: 0.2 <= Ppr < 30 for 1.0 < Tpr <= 3.0, PLUS Ppr < 1.0 for 0.7 < Tpr <= 1.0. The second sub-window is the low-temperature low-pressure extension and is easy to miss.
- Hall & Yarborough and DAK together, per Whitson & Brulé (full text): 'Both equations are valid for 1 <= Tr <= 3 and 0.2 <= pr <= 25 to 30.' Note the deliberate vagueness of the upper Ppr bound.
- Hall & Yarborough, per nafta.wiki: 1.05 <= Tpr <= 3 and 0.2 <= Ppr <= 15. This is a TIGHTER window than Whitson quotes; the conservative reading is 1.05 <= Tpr <= 3, 0.2 <= Ppr <= 15, degrading beyond.
- DPR (1974), commonly cited: 1.05 <= Tpr <= 3.0 and 0.2 <= Ppr <= 30. This range is recalled, not retrieved — treat the upper Ppr with suspicion.
- Standing (1977) dry-gas form: gamma_gHC <= 0.75; wet-gas form: gamma_gHC > 0.75 (Whitson & Brulé state the split explicitly). Both were fitted to California gases with zero inorganic content.
- Sutton (1985): 0.57 < gamma_g < 1.68, with H2S = 0, N2 < 1 mol%, CO2 < 1 mol% (nafta.wiki). Sutton was developed specifically for HIGH-molecular-weight gas/condensate where Kay's rule biases Z by 10-15% at gamma > 1.5.
- Wichert & Aziz (1972): CO2 molar concentration 0 to 55%, H2S molar concentration 0 to 74% (Whitson & Brulé, full text). Other sources give the tighter 54.4% CO2 / 73.8% H2S. Combined acid gas <= 74 mol%.
- Kay's mixing rule for pseudocriticals is adequate only up to gamma_g ~ 0.85; beyond that Z errors grow roughly linearly, reaching 10-15% at gamma_g ~ 1.5 (Whitson & Brulé, citing Sutton).
- Standing-Katz chart itself (the ground truth all three correlations fit) does not cover water-bearing gases or non-hydrocarbon concentrations beyond the Wichert-Aziz limits; for those use AGA-8, Lee-Kesler or DDMIX instead.

## Failure modes

- Tpr between 1.05 and 1.15 at low Ppr: Whitson & Brulé state explicitly that 'an apparent discrepancy in the Standing-Katz Z-factor chart for 1.05 <= Tr <= 1.15 has been smoothed in the Hall-Yarborough correlations.' Consequence: HY and DAK/DPR DISAGREE BY DESIGN there. Measured this session: max |Z_DAK - Z_HY| = 0.047 (16.3% relative) over 1.05 <= Tpr <= 1.15, 0.2 <= Ppr <= 5. A cross-correlation consistency test must NOT flag this as a bug.
- Near-critical region generally (Tpr -> 1.0, Ppr in 1 to 3): all three correlations deviate strongly from the digitised Standing-Katz chart. Measured per-Tpr AAPE vs the zFactor digitised chart: Tpr=1.05 -> DAK 4.96%, HY 8.83%, DPR 5.22%; Tpr=1.10 -> DAK 2.08%, HY 3.49%, DPR 1.87%. Everywhere from Tpr >= 1.20 the AAPE drops to 0.14-0.57%. Part of this is chart-digitisation error on a near-vertical curve, but not all of it. Do not trust Z to better than ~5% for Tpr < 1.15.
- Ppr > 25: beyond HY's fitted range. Measured max |Z_DAK - Z_HY| = 0.060 (2.4%) over 25 < Ppr <= 30, versus 0.0089 (1.6%) in the core band. DPR stays glued to DAK (max 0.010) because they share structure, so DAK-vs-DPR agreement gives FALSE confidence out there.
- psig passed where psia is expected, or deg F where deg R is expected. Both produce a silently plausible Z. Guard with an assertion that T > 0 in deg R and P > 0 in psia, and range-check Tpr in [0.7, 3.5] and Ppr in [0, 35] before iterating.
- Mole PERCENT passed to Wichert-Aziz instead of mole FRACTION: A = yCO2 + yH2S becomes > 1, A^0.9 - A^1.6 goes negative, epsilon goes negative, Tpc' exceeds Tpc, and Z comes out wrong without any exception being raised.
- Using the UNCORRECTED Tpc/Ppc to form Tpr/Ppr after computing a Wichert-Aziz correction. Silent and large for sour gas: in the worked case here (10% CO2, 5% H2S) epsilon = 19.35 deg R, which moves Tpr from 1.565 to 1.646 and Ppr from 2.285 to 2.410.
- Separator-gas gravity used instead of wellstream gravity for a gas-condensate. Standing's wet-gas and Sutton's correlations both assume wellstream gravity; the error propagates into both Tpc and Ppc.
- Applying a gravity-based pseudocritical correlation to a sour gas without first stripping the non-hydrocarbons (Whitson Eq. 3.53) and recombining via Kay's rule (Eqs. 3.54a/3.54b). The gravity correlations were fitted on hydrocarbon-only gas.
- Extrapolating Sutton below gamma_g = 0.57 or above 1.68, or Standing dry above gamma_g = 0.75. At gamma_g = 1.2 the three Ppc correlations spread from 594 psia (Sutton) to 631 psia (Standing dry) — a 6% spread that propagates straight into Ppr.
- Assuming Z <= 1. Z exceeds 1 for Ppr above roughly 6-8 and reaches 3.2 at Tpr = 1.05, Ppr = 30. Any code path that clamps Z to [0,1] is wrong.

## Numerical pitfalls

- Clearing the 1/rho pole in the DAK/DPR residual (multiplying F through by rho) removes the barrier that keeps Newton on rho > 0 and lets it converge to spurious roots with NEGATIVE Z. Observed here at Tpr = 1.05, Ppr = 2 to 5 (Z came out as -0.215, -0.322, -0.531) and Tpr = 1.10, Ppr = 2 and 5. Keep the pole, or bracket.
- Hall & Yarborough's (y + y^2 + y^3 - y^4)/(1-y)^3 blows up as y -> 1 and the B*y^(2.18+2.82t) term is a non-integer power, so ANY Newton step that puts y <= 0 or y >= 1 produces a NaN, a ZeroDivisionError, or a complex result. Clamp every step into (0, 1) — the measured failure rate without clamping is 8% to 16% of the domain.
- DAK's exp(-A11*rho_r^2) with rho_r reaching 2.4 at Tpr = 1.05, Ppr = 30 gives exp(-4.2) ~ 0.015 — no underflow risk in float64, but the -A9*(...)*rho_r^5 term reaches order 10 there, so the residual is dominated by terms of very different magnitude. A relative convergence test on |F| alone can stall; test |delta rho| as well (or instead).
- Convergence tolerance: 1e-13 to 1e-14 on |delta rho| or |F| is comfortably reachable in float64 and costs at most 20 iterations. Do not use a loose tolerance like 1e-6 as a way to dodge a convergence problem — it hides the spurious-root failure rather than fixing it.
- Wichert-Aziz epsilon evaluates A^0.9 where A = yCO2 + yH2S. At A = 0 exactly, 0**0.9 = 0 in IEEE and in Python, so the sweet-gas path is safe — but guard it explicitly anyway, because a negative A from a bad mass-vs-mole conversion raises a domain error or returns a complex number depending on the language.
- B^0.5 in epsilon with B = yH2S: the square root has infinite derivative at B = 0, so any attempt to differentiate epsilon with respect to composition (for a sensitivity study or an optimiser) is singular at zero H2S. Use a one-sided difference or special-case it.
- Z is NOT bounded above by 1 and reaches 3.24 at Tpr = 1.05, Ppr = 30. Any bisection bracket on Z (rather than on rho_r or y) must span at least [0.1, 3.5]. Bracketing on rho_r in [1e-8, 3.0] or on y in (0, 1) is cleaner.
- Catastrophic cancellation in the DAK numerator R1 = A1 + A2/Tpr + A3/Tpr^3 + A4/Tpr^4 + A5/Tpr^5: at Tpr near 1 this is 0.3265 - 1.0700 - 0.5339 + 0.01569 - 0.05165 = -1.31336, a sum of terms of mixed sign and comparable magnitude. It is fine in float64 but will lose precision badly in float32. Do not run this correlation in single precision.
- The two candidate R values (10.73146 vs 10.73157709) and the two Mair values (28.97 vs 28.9625) differ at the 1e-5 and 2.6e-4 relative level respectively. If a cross-correlation or regression test tolerance is set tighter than 1e-3 relative, these constant choices will start producing spurious test failures across library versions. Pin the constants in one module and reference them everywhere.
- Do not cache Z across a pressure sweep by reusing the previous rho_r as the initial guess without re-bracketing. It is faster and usually fine, but in the 1.05 <= Tpr <= 1.15 zone where Z falls steeply (Z drops from 0.587 at Ppr = 1.0 to 0.284 at Ppr = 1.5 at Tpr = 1.05), a warm start can land on the wrong side of a steep segment.

## Implementation notes

- Cross-correlation consistency test — the measured agreement bands (computed this session on a Tpr step 0.05 / Ppr step 0.2 grid, bracketed solver, all points converged). Band A, 1.05 <= Tpr <= 1.15 and 0.2 <= Ppr <= 5 (n=75): max |dZ| DAK-HY 0.0468, DAK-DPR 0.0036, HY-DPR 0.0482; relative 16.3% / 0.7% / 13.5%. Band B, same Tpr, 5 < Ppr <= 15 (n=150): 0.0107 / 0.0062 / 0.0131. Band C, 1.2 <= Tpr <= 3.0 and 0.2 <= Ppr <= 8, the core engineering band (n=1480): 0.0089 / 0.0037 / 0.0114, relative 1.61% / 0.48% / 2.02%. Band D, 8 < Ppr <= 15 (n=1295): 0.0123 / 0.0048 / 0.0145. Band E, 15 < Ppr <= 25 (n=1850): 0.0402 / 0.0084 / 0.0412. Band F, 25 < Ppr <= 30 (n=925): 0.0599 / 0.0103 / 0.0600. Set per-band tolerances from these numbers.
- The single most important structural fact for the test design: DAK and DPR agree with each other 3 to 6 times more tightly than either agrees with HY, in EVERY band. They share the BWR structure, the 0.27 constant, the same 1500 chart points, and the same 5th-power-plus-Gaussian tail. So DAK-vs-DPR is a near-duplicate check and will not catch a shared modelling error; DAK-vs-HY (and DPR-vs-HY) is the informative pair. Build the consistency test around a three-way spread with band-dependent tolerance, and log WHICH pair drives the spread.
- Solver recommendation, DAK and DPR: keep the residual in the form that retains the -R2/rho (or -T5/rho) pole and do NOT clear it by multiplying through by rho. Measured this session: unsafeguarded Newton from rho_0 = 0.27*Ppr/Tpr on the pole-retaining form converged at 6150/6150 grid points (1.0 <= Tpr <= 3.0 step 0.05, 0.2 <= Ppr <= 30 step 0.2), mean 6.3 iterations, max 20 for DAK and mean 6.2 / max 13 for DPR. The polynomial-cleared form (multiply by rho) has no barrier at rho = 0 and I observed Newton converging to SPURIOUS NEGATIVE-Z roots at Tpr = 1.05-1.10 for Ppr in 2 to 5. Even so, wrap the iteration in a bracket [1e-8, 3.0] with bisection fallback: the cost is negligible and it turns a silent wrong answer into a guaranteed correct one.
- Solver recommendation, Hall & Yarborough: safeguarding is MANDATORY, not optional. Unsafeguarded Newton on f(y) failed (y stepped outside (0,1)) at 502/6150 grid points with the Whitson initial guess y0 = 0.001, and at 1008/6150 with the Yarborough & Hall guess y0 = 0.0125*Ppr*t*exp(-1.2*(1-t)^2). Failures cluster at Tpr <= 1.55. With a bracketed/damped Newton (maintain [lo, hi] from the sign of f, halve any step that leaves the bracket, fall back to bisection) all 6150 points converge. Whitson & Brulé quote 3 to 10 iterations for |f(y)| <= 1e-8; I measured mean 7.9 iterations on the converging subset.
- Initial guesses, side by side: DAK/DPR rho_0 = 0.27*Ppr/Tpr (equivalent to Z = 1). HY y0 = 0.001 (Whitson & Brulé, Eq. 3.45 discussion) is more robust than y0 = 0.0125*Ppr*t*exp(-1.2*(1-t)^2) (Yarborough & Hall 1974, used by zFactor and pengtools) — by a factor of 2 in failure count here. Use y0 = 0.001.
- KNOWN BUG in a widely copied reference implementation: the CRAN zFactor package's DAK Fprime contains `(1 + 2*A11*rhor^3)` where the correct expression is `(1 + 2*A11*rhor^2)`. Verified numerically this session — at Tpr = 1.3, Ppr = 3.0 the published expression gives dF/drho = 2.0753 at rho = 0.5 versus the true 2.1174, and 1.2887 at rho = 1.5 versus the true 1.0204. It happens to be exactly right at rho = 1.0, so a test point at rho = 1 will NOT catch it. This only degrades convergence rate (the root is unchanged) but it will silently corrupt any analytic dZ/dP derived from it. Do not copy that expression. The zFactor DPR Fprime is correct.
- Precompute the Tpr-only groups (R1..R5 for DAK, T1..T5 for DPR, alpha/A/B/C for HY) once per (Tpr, Ppr) pair outside the Newton loop. For a pseudo-pressure integral or a material-balance sweep along an isotherm, hoist the Tpr-only parts out of the pressure loop entirely.
- Order of operations for a sour, heavy gas: (1) strip non-hydrocarbons to get gamma_gHC (Whitson Eq. 3.53); (2) Sutton (or Standing) on gamma_gHC to get TpcHC, PpcHC; (3) recombine with the non-hydrocarbon criticals via Kay's rule (Eqs. 3.54a/b) to get T*pc, p*pc; (4) Wichert-Aziz on T*pc, p*pc with yCO2 and yH2S to get Tpc', Ppc'; (5) form Tpr, Ppr from the CORRECTED values; (6) solve for Z. Skipping step (1) or (3) and applying Wichert-Aziz directly to a gravity correlation output is common and introduces a bias that is hard to see.
- Whitson & Brulé's own recommendation, worth honouring as the library default: Sutton (1985) for hydrocarbon pseudocriticals when only gravity is known; Kay's rule with Matthews et al. C7+ criticals when composition is available; Hall & Yarborough OR Dranchuk & Abou-Kassem for Z. They explicitly discourage Brill & Beggs now that computation is cheap.
- Expose the solver's iteration count and final residual in the return value. For a research library, a Z that took 20 iterations at Tpr = 1.05 is a different epistemic object from one that took 5 at Tpr = 2.0, and the caller should be able to see that without re-running.
- PLUS / MINUS / RECOMMENDATION. PLUS: the functional forms of DAK, HY and Wichert-Aziz plus the Standing and Sutton coefficients are now anchored to a full-text retrieval of an SPE monograph chapter, the analytic derivatives are numerically confirmed, and I found a concrete published-derivative bug plus a concrete HY convergence hazard with measured failure counts — the implementer has real numbers, not vibes. MINUS: none of the four original papers (DAK 1975 JCPT, HY 1973 OGJ, DPR 1974 IP 74-008, Sutton 1985 SPE 14265) was retrieved, so the coefficient VALUES rest on agreement between independent reproductions rather than on primary text; two small conflicts (Sutton 131 vs 131.07, DPR A3 last digit) remain open, and my only Z 'ground truth' is somebody else's chart digitisation, which is not an independent measurement. RECOMMENDATION: implement now against this card — the open conflicts are all below 1e-4 relative and cannot change an engineering answer — but before this library is used for anything published, buy or borrow the four originals and close the two coefficient conflicts and the DAK/HY validity-window discrepancy in writing. And do not let the DAK-vs-DPR agreement be read as validation: it is the same fit twice.

## Open uncertainties

- NONE of the four primary papers was retrieved this session. Dranchuk & Abou-Kassem (1975 JCPT), Hall & Yarborough (1973 OGJ), Dranchuk, Purvis & Robinson (1974, IP 74-008) and Sutton (1985, SPE 14265) are all behind paywalls or not online. Everything about their COEFFICIENT VALUES rests on agreement between independent secondary reproductions. The functional FORMS of DAK and HY are on firmer ground because they appear verbatim in a retrieved SPE monograph chapter.
- Sutton Ppc linear coefficient: 131 (Whitson & Brulé full text; midstreamcalculator) versus 131.07 (GasCompressibility-py sutton.py; nafta.wiki). UNRESOLVED. Magnitude: 0.053 psia at gamma_g = 0.75. I could not retrieve SPE 14265 to settle it. Mark this constant verified_how = 'two published variants, primary source not retrieved' in the code and pick 131 (the monograph reading) as default.
- DPR A3: -0.57832729 (predico AFA reference; the value the literature search reports as more commonly cited) versus -0.57832720 (CRAN zFactor R source). UNRESOLVED. Magnitude: 9e-8 absolute, below any conceivable engineering significance, but a reviewer will notice.
- DAK reported accuracy: I saw 0.486% average absolute error (midstreamcalculator, secondary) and 0.585% (a literature-search summary of the original abstract). I could not verify either against the paper. Do NOT quote an accuracy figure for DAK in the repo without retrieving the original.
- DAK validity window: pengtools wiki gives two sub-windows (0.2 <= Ppr < 30 with 1.0 < Tpr <= 3.0, and Ppr < 1.0 with 0.7 < Tpr <= 1.0) attributed to the original paper. Whitson & Brulé give a single joint statement for HY and DAK of 1 <= Tr <= 3 and 0.2 <= pr <= 25 to 30. These are not the same claim. Not resolved.
- Hall & Yarborough validity window: Whitson says 1 <= Tr <= 3, 0.2 <= pr <= 25 to 30; nafta.wiki says 1.05 <= Tpr <= 3, 0.2 <= Ppr <= 15. Roughly a factor of two apart on the upper Ppr. My own measurement (HY diverges from DAK/DPR by up to 2.4% for 25 < Ppr <= 30) is consistent with the CONSERVATIVE reading being the honest one.
- DPR validity range (1.05 <= Tpr <= 3.0, 0.2 <= Ppr <= 30) is Unverified — supporting source not established: not retrieved, and no source is identified for it. Treat it as unverified.
- **[SUPERSEDED — see "Standing (1977) dry-gas pseudocritical pressure — constant term" under "Adversarial review / Corrections" below.]** ~~My own recall was WRONG on Standing's dry-gas Ppc constant: I initially had 677 and the retrieved sources (Whitson & Brulé full text, plus Ahmed) both say 667, and the methane physical anchor confirms 667.~~ Both supporting claims in that sentence are false: Ahmed prints 677, not 667, and the methane anchor is not a valid arbiter. **Standing's dry-gas Ppc constant remains UNRESOLVED at 667 versus 677.** Whitson & Brulé Eq. 3.48b gives 667; Ahmed Eq. 2-19 gives 677 and only 677 reproduces Ahmed's own worked examples; the original Standing (1977) was not retrieved by anyone. The measured consequence is quantified in case A2 and is restated in the correction below. The original sentence is kept, struck through, because this card's job is to keep the audit trail rather than to look consistent.
- The 'ground truth' Z values used for the accuracy numbers in independent_checks are a third party's DIGITISATION of the Standing-Katz chart, published in the CRAN zFactor package. That is a secondary source twice over (digitisation of a chart that is itself a smoothed fit to 1942 experimental data). The reported AAPE values are a measure of agreement with THAT digitisation, not of physical accuracy. Real physical accuracy versus modern experimental PVT data was not assessed here at all.
- Wichert-Aziz composition limits: Whitson & Brulé (retrieved) say CO2 0 to 55% and H2S 0 to 74%; other sources say 54.4% and 73.8%. Probably rounding of the same underlying dataset, but not confirmed.
- The critical constants for methane (Tc = 343.0 deg R, Pc = 666.4 psia) used in the physical sanity check are Unverified — cited source not inspected, not retrieved. Verify them against a physical-property table (GPA 2145, DIPPR, or NIST) before turning that check into an assertion.
- Pressure and temperature bounds of the Wichert-Aziz dataset (some sources quote 154 to 7026 psia and 40 to 300 deg F) could NOT be confirmed against any retrieved source this session. Do not state them as fact.
- Whether the DAK 1975 paper intends rho_r bounded above (e.g. rho_r < 3) is unknown. I used [1e-8, 3.0] as a bracket because rho_r reaches 2.43 at the corner Tpr = 1.05, Ppr = 30; that upper bound is my engineering choice, not a published one.

## Independent check values

| Check | Inputs | Expected | Source | Retrieved or recalled |
|---|---|---|---|---|
| DAK / HY / DPR versus digitised Standing-Katz chart points, full sweep. 569 (Tpr, Ppr, Z) points across Tpr = 1.05, 1.10, 1.20, 1.30, 1.40, 1.50, 1.70, 2.00, 2.20, 2.40, 2.60, 3.00, low- and high-pressure branches. | `the zFactor R package digitised chart files inst/extdata/sk_lp_tpr_*.txt and sk_hp_tpr_*.txt (columns: Ppr, Z)` | `AAPE over all 569 points: DAK 1.094%, HY 1.746%, DPR 1.130%. Max APE: DAK 18.46%, HY 28.75%, DPR 18.77% (all maxima occur at Tpr = 1.05, Ppr ~ 1.5-2). Excluding Tpr <= 1.10, per-Tpr AAPE is 0.14% to 0.57% for all three.` | https://github.com/cran/zFactor/tree/master/inst/extdata (chart digitisation by the zFactor author; SECONDARY, a digitisation of the Standing & Katz 1942 chart, not the chart itself) | retrieved this session (files downloaded and compared numerically) |
| Spot values from that digitised chart (retrieved), with the values my implementation produces | `(Tpr, Ppr) pairs` | `Tpr 1.30, Ppr 3.008: chart 0.624, DAK 0.6243, HY 0.6240, DPR 0.6239. Tpr 1.50, Ppr 3.006: chart 0.776, DAK 0.7760, HY 0.7747, DPR 0.7763. Tpr 1.50, Ppr 2.006: chart 0.822, DAK 0.8211, HY 0.8204, DPR 0.8202. Tpr 2.00, Ppr 3.006: chart 0.937, DAK 0.9376, HY 0.9396, DPR 0.9378. Tpr 1.20, Ppr 7.00: chart 0.891, DAK 0.8910, HY 0.8883, DPR 0.8890. Tpr 1.05, Ppr 15.0: chart 1.751, DAK 1.7495, HY 1.7504, DPR 1.7557.` | zFactor inst/extdata digitised Standing-Katz; correlation values computed this session | chart values retrieved; correlation values computed this session |
| End-to-end sour-gas worked example: Sutton pseudocriticals + Wichert-Aziz + DAK | `gamma_g = 0.75, yCO2 = 0.10, yH2S = 0.05, P = 1500 psia, T = 150 deg F (609.67 deg R)` | `Published: Tpc = 389.6 deg R, Ppc = 656.5 psia, A = 0.15, B = 0.05, epsilon = 19.3 deg R, Tpc' = 370.3 deg R, Ppc' ~ 622.6 psia, Tpr' = 1.647, Ppr' = 2.409, Z ~ 0.861. My implementation: Tpc = 389.700, Ppc = 656.525, epsilon = 19.3475, Tpc' = 370.3525, Ppc' = 622.4624, Tpr' = 1.64619, Ppr' = 2.40978, Z_DAK = 0.86052, Z_HY = 0.86049, Z_DPR = 0.86029.` | https://midstreamcalculator.com/engineering/thermodynamics/z-factor-fundamentals.html (SECONDARY — an engineering calculator site, not primary literature; usable only as a cross-check) | retrieved this session; reproduced numerically this session to 3 significant figures |
| Analytic derivative dF/drho for DAK versus central finite difference | `80 combinations: Tpr in {1.05, 1.3, 1.7, 2.5}, Ppr in {0.5, 3, 10, 25}, rho in {0.05, 0.3, 0.8, 1.5, 2.2}, h = 1e-6` | `max relative deviation 6.605e-9 — the analytic derivative given in the equations section is CONFIRMED.` | derived and verified this session | computed this session |
| Physical anchor: Standing dry-gas pseudocriticals evaluated at pure-methane gravity | `gamma_g = 16.043 / 28.97 = 0.5538` | `Tpc = 344.1 deg R versus methane Tc = 343.0 deg R (0.3% high); Ppc = 663.8 psia versus methane Pc = 666.4 psia (0.4% low).` **[SUPERSEDED] The cell continued: "This confirms the constant term is 667 and NOT 677 (the 677 form gives 673.9 psia, 1.1% high and in the wrong direction)." It does not. Standing's correlation is a fit to a mixture-gas chart and is not constrained to pass through pure methane's critical point; the 10 psia that separates the two variants is inside the correlation's own scatter, and the methane constants used here are recalled rather than retrieved. Use this only as a loose smoke test — Ppc within about 2 percent of 666 psia — never as the arbiter between 667 and 677. See the correction below.** | methane critical constants are standard reference values (recalled, widely tabulated); Standing coefficients from Whitson & Brulé | Standing coefficients retrieved; methane Tc/Pc Unverified — supporting source not established; verify against a physical-property table before using as a hard test |
| Ideal-gas limit | `Ppr -> 0 at any Tpr in the valid window` | `Z -> 1. Measured at Ppr = 0.2: DAK 0.99921, HY 1.00006, DPR 0.99912 at Tpr = 3.0. Note HY crosses slightly ABOVE 1 at high Tpr — this is a property of the fit, not a bug.` | real-gas law, exact | computed this session |
| Standard molar volume from the oilfield gas constant | `Tsc = 60 deg F = 519.67 deg R, psc = 14.696 psia (or 14.70), Z = 1` | `Vm = R*Tsc/psc = 379.48 scf/lbmol with R = 10.73157709 and psc = 14.696; 379.38 with R = 10.73146 and psc = 14.70. Whitson & Brulé Eq. 3.27 publishes 379.4 scf/lbmol (= 23.69 std m3/kmol).` | Whitson & Brulé, Phase Behavior, SPE Monograph Vol. 20, Ch. 3, Eq. 3.27 | retrieved this session; reproduced numerically |

## Adversarial review

### Corrections

**Standing (1977) dry-gas pseudocritical pressure — constant term (card: "667, NOT 677. A 677 variant circulates in secondary sources and is wrong")** — severity high, confidence high (that the card's claim "Ahmed confirms 667" is wrong and that the true status is a conflict); medium (that 677 is Standing's original value — the original paper was still not retrieved)

- Claimed: PpcHC = 667 + 15.0*g - 37.5*g^2, with the supporting claims "independently confirmed as 667 in Ahmed's Reservoir Engineering Handbook" and a methane physical anchor said to "confirm the constant term is 667 and NOT 677".
- Correct: UNRESOLVED CONFLICT, and the default should be flipped to 677. Ahmed, Reservoir Engineering Handbook, Eq. 2-19 literally prints ppc = 677 + 15.0*gg - 37.5*gg^2 and uses it in at least four worked examples (gg=0.699 -> 669.2 psia; gg=0.7 -> 669.1; gg=0.72 -> 668.4; gg=0.854 -> 662.5). So the corroboration claim in the card is FALSE — Ahmed says 677, not 667. What is true: Whitson & Brule Eq. 3.48b prints 667 (I retrieved the full text and confirmed the card's transcription is accurate), while the Ahmed/GPSA-chart line prints 677. The original Standing (1977) was not retrieved by anyone, so the honest status is a 667 vs 677 conflict, not "677 is wrong". Recommendation: default to 677 (the majority of the independent reproductions, and the only reading that reproduces the published worked examples), expose it as a configurable constant, mark it UNVERIFIED.
- Evidence: Retrieved this session: (1) NTNU copy of SPE Monograph Vol.20 Ch.3 PDF, the text of Eq. 3.48b = '667 + 15.0 gHC - 37.5 g^2HC'; (2) the full text of Ahmed's Reservoir Engineering Handbook via dokumen.pub, 'Standing (1977) expressed this graphical correlation in the following mathematical forms: Case 1: Natural Gas Systems Tpc = 168 + 325 gg - 12.5 gg2 (2-18) ppc = 677 + 15.0 gg - 37.5 gg2 (2-19)'; (3) Ahmed's worked example: 'ppc = 677 + 15 (0.7) - 37.5 (0.7)2 = 669.1 psia' then 'p'pc = 630.44' — the value 630.44 is reproducible only from 677 (with 667 the result is 621.0 psia). Measured impact at one state: 10 psia = 1.5% in Ppc; at gg=0.7, 3000 psia, 180 F -> dZ = 0.0016 (0.18% of Z), larger in zones where dZ/dPpr is steep.
- Measured consequence over a domain, added after the claims audit and recomputed from the shipped library during that pass: over gamma_g 0.55 to 1.10 in steps of 0.05 at 500 to 6000 psia in steps of 500 psia and 200 degF, with Z by DAK and Bg at SPE standard conditions, the two variants differ by **1.53 percent in Ppc on average** and, in Z, by **0.45 percent on average with a maximum of 1.15 percent**. The maximum sits on the corner of the sampled grid (gamma_g = 1.10, 6000 psia), so it is a lower bound on the maximum over any wider range, not a bound on it. A mean is not a bound and must not be quoted as one; state the mean, the maximum and the domain together or none of them. This restates a measurement first made in `cases/A2_pvt_independent_check`, whose outputs are not distributed with this repository because the case reads a NIST reference extract that is not redistributed here; the 667/677 comparison itself uses no reference data and is reproducible from the library alone.

**Independent check #6 — the methane physical anchor as a 667 vs 677 discriminator** — severity medium, confidence high

- Claimed: "Tpc = 344.1 deg R vs methane Tc = 343.0; Ppc = 663.8 vs 666.4. This confirms the constant term is 667 and NOT 677 (the 677 form gives 673.9, 1.1% high and in the wrong direction)." Presented as a 'discriminating check'.
- Correct: The arithmetic is right (I reproduce 344.145, 663.81, 673.81) but the inference is not valid. The Standing correlation is a fit to the Brown et al. (1948)/GPSA chart for MIXTURE gases, not a constraint required to pass through the critical point of pure methane; gg=0.5538 sits at the lower edge of the fit window. The difference used to decide (0.4% vs 1.1%, i.e. 10 psia) is well inside the scatter of the correlation itself, and the methane Tc/Pc used are admitted to be 'Unverified — supporting source not established'. This anchor gives the opposite answer to Ahmed's worked-example evidence. Demote it to a loose sanity check only (Ppc within 2% of ~666 psia); never use it to decide a coefficient.
- Evidence: Recomputed this session. Ahmed's Example (gg=0.7, 5% CO2, 10% H2S, 3500 psia, 160 F) prints p'pc = 630.44 psia, which is consistent only with 677; the methane anchor 'picks' 667. The two pieces of evidence collide, and the worked-example evidence is the stronger one because it is traceable to published numbers rather than to an extrapolation.

**DPR coefficient A3 — default pick** — severity low, confidence high

- Claimed: "Use -0.57832729; document the variant" (predico AFA), with zFactor's -0.57832720 described as a minor variant.
- Correct: Flip the default back to -0.57832720, or state agnosticism. Two independent sources I retrieved print -0.57832720: CRAN zFactor R/Dranchuk-Purvis-Robinson.R line 60, and Ahmed's Reservoir Engineering Handbook ('A3 = -0.57832720'). Only predico gives ...29. The card picks the minority reading and calls it 'the value the literature search reports as more commonly cited' — that is not supported.
- Evidence: curl raw.githubusercontent.com/cran/zFactor/master/R/Dranchuk-Purvis-Robinson.R -> 'A3 <- -0.57832720'; the Ahmed text -> 'A1 = 0.31506237 A2 = -1.0467099 A3 = -0.57832720 A4 = 0.53530771 A5 = -0.61232032 A6 = -0.10488813 A7 = 0.68157001 A8 = 0.68446549'. All seven other coefficients match the card exactly.

**Attribution of the DAK analytic-derivative bug ("KNOWN BUG in a widely copied reference implementation: the CRAN zFactor package's DAK Fprime")** — severity medium, confidence high

- Claimed: The typo (1 + 2*A11*rhor^3) is localised to the R package zFactor.
- Correct: The typo is real and the card's numbers are exactly right, but its source is not zFactor — it is in Ahmed, Reservoir Engineering Handbook itself, in the f'(rho_r) that accompanies Eq. 2-41. zFactor merely copied it. Its reach is therefore far wider than the card states: an implementer retyping from a standard textbook will hit it, not only someone copying the R package.
- Evidence: The Ahmed text: "f'(rho_r) = (R1) + R2/rho_r^2 + 2(R3)rho_r - 5(R4)rho_r^4 + 2(R5)rho_r ... exp[-A11 rho_r^2][(1 + 2 A11 rho_r^3) - A11 rho_r^2 (1 + A11 rho_r^2)]". zFactor R/Dranchuk-AbouKassem.R line 56 is identical. My numerical verification (Tpr=1.3, Ppr=3.0): correct/typo = 2.1174/2.0753 at rho=0.5, 0.6233/0.6233 at rho=1.0 (invisible), 1.0204/1.2887 at rho=1.5, 3.3542/3.7144 at rho=2.0 — exactly the card's numbers.

**Independent check #3 — the sour-gas worked example from midstreamcalculator** — severity medium, confidence high

- Claimed: Used as an 'End-to-end sour-gas worked example ... reproduced numerically this session to 3 significant figures', listed in the independent_checks section.
- Correct: CIRCULAR. midstreamcalculator is a web calculator running the same Sutton/Wichert-Aziz/DAK equations; agreement to 3 s.f. tests only the arithmetic, not the correctness of the coefficients or of the form. The card does label it SECONDARY but still counts it as an independent check. Replace it with Ahmed's Example (a chart-read z, not the output of the same code) — see recommended_test_oracles.
- Evidence: The card itself: 'SECONDARY — an engineering calculator website'. There is no physical measurement and no human chart reading in it; the Z value 0.861 is only DAK output.

**Implementation note: "DAK and DPR agree with each other 3 to 6 times more tightly than either agrees with HY, in EVERY band"** — severity low, confidence high

- Claimed: A ratio of 3x-6x in every band.
- Correct: Contradicted by the card's own table. The ratio (DAK-HY)/(DAK-DPR) from the card's numbers: band A 13.0, band B 1.7, band C 2.4, band D 2.6, band E 4.8, band F 5.8. In the core engineering band (C) the ratio is 2.4x, not 3-6x, and band B is only 1.7x. The qualitative conclusion (DAK-vs-DPR is not an independent test) still stands; it is the quantification that is overstated.
- Evidence: I reproduce the whole band table exactly (C: 0.0089/0.0037/0.0114 n=1480; D: 0.0123/0.0048/0.0145 n=1295; E: 0.0402/0.0084/0.0412 n=1850; F: 0.0599/0.0103/0.0600 n=925) on a grid of Tpr 1.2-3.0 step 0.05, Ppr 0.2-30 step 0.2. The ratios are computed directly from it.

**Hall-Yarborough validity range — the lower Tpr bound** — severity medium, confidence high

- Claimed: The card quotes only Whitson ('1 <= Tr <= 3') and nafta.wiki ('1.05 <= Tpr <= 3'), then sweeps the grid from Tpr = 1.00.
- Correct: There is a firmer statement by the authors that the card does not quote: Ahmed records "Hall and Yarborough pointed out that the method is not recommended for application if the pseudo-reduced temperature is less than one." DAK, on the other hand, has a second sub-window (0.7 < Tpr <= 1.0 with Ppr < 1.0), so below Tpr = 1 only DAK has any claim to validity. The library must reject or warn on HY for Tpr < 1, and the cross-correlation test must not include Tpr < 1.
- Evidence: The Ahmed text (retrieved). My numbers at Ppr = 2.0: Tpr 0.90 -> HY 0.2842 vs DAK 0.2964 (dZ -0.0122), Tpr 0.95 -> dZ -0.0075, Tpr 1.00 -> dZ -0.0031. HY still converges (it does not blow up) — so the failure is silent, exactly the pattern the card says must be guarded against.

**A cross-source hazard the card does not mention: the HY hard-sphere form** — severity medium, confidence high

- Claimed: The card states the form (y + y^2 + y^3 - y^4)/(1-y)^3 and mentions only one published typo (the DAK Fprime).
- Correct: The card's form is CORRECT, but there is a second, equally widespread textbook typo that goes unwarned: Ahmed Eq. 2-37 prints the hard-sphere numerator as (Y + Y^2 + Y^3 + Y^4) — a plus sign on Y^4 — whereas Carnahan-Starling and Whitson Eq. 3.43 give -Y^4, and Ahmed's own derivative (Eq. 2-39, numerator 1 + 4Y + 4Y^2 - 4Y^3 + Y^4) is the derivative of the -Y^4 form. So Ahmed is internally inconsistent, and an implementer copying his residual will be wrong.
- Evidence: The Ahmed text (retrieved): 'F(Y) = X1 + (Y + Y2 + Y3 + Y4)/(1 - Y)3 - (X2)Y2 + (X3)Y^X4 = 0 (2-37)' and 'f'(Y) = (1 + 4Y + 4Y2 - 4Y3 + Y4)/(1 - Y)4 - 2(X2)Y + (X3)(X4)Y^(X4-1) (2-39)'. The derivative of the +Y^4 version would be (1 + 4y + 4y^2 + 4y^3 - y^4)/(1-y)^4, so it is 2-37 that carries the typo. Whitson Eq. 3.43 (full text retrieved) gives '-y^4'.

**The maximum Z value at the domain corner** — severity low, confidence high

- Claimed: numerical_pitfalls: "Z ... reaches 3.24 at Tpr = 1.05, Ppr = 30"; failure_modes: "reaches 3.2".
- Correct: 3.24 is the HY value, not DAK. Measured at Tpr=1.05, Ppr=30: DAK Z = 3.1808 (rho_r = 2.4253, matching the 2.43 in the card), HY Z = 3.2416, DPR Z = 3.1963. The suggested bracket [0.1, 3.5] remains safe; only the attribution of the number needs correcting.
- Evidence: Computed this session with a bracketed solver.

**Reproducibility of two rows in the spot-value table** — severity low, confidence high

- Claimed: "Tpr 1.20, Ppr 7.00: chart 0.891, DAK 0.8910..." dan "Tpr 1.05, Ppr 15.0: chart 1.751, DAK 1.7495..."
- Correct: The 'inputs' column is rounded. At exactly Ppr = 7.000 I get DAK 0.8906 / HY 0.8879 / DPR 0.8886 (not 0.8910/0.8883/0.8890); the actual chart abscissa is 7.004. The same for the 1.05 row: the chart abscissa is 15.003, not 15.0. The +/-0.005 tolerance the card proposes absorbs this difference, so it is not a functional defect — but the fixture must store the exact chart abscissa rather than the rounded one if the tolerance is ever tightened.
- Evidence: sk_lp_tpr_120.txt line '7.004 0.891'; sk_hp_tpr_105.txt line '15.003 1.751' (downloaded this session). The other four spot rows reproduce exactly to 4 decimal places.

### Left unverified

- Standing (1977) dry-gas ppc constant: 667 (Whitson & Brule Eq. 3.48b, full text retrieved) vs 677 (Ahmed Eq. 2-19 plus four worked examples, full text retrieved). The original Standing 1977 paper/book was NOT retrieved, by the card or by me. This is the single most important item still open; mark the constant UNVERIFIED in the code and make it replaceable.
- Sutton (1985) ppc linear coefficient: 131 (Whitson & Brule Eq. 3.47b, full text retrieved — I confirm the card's transcription is accurate) vs 131.07 (GasCompressibility-py sutton.py line 123, which I confirmed; also nafta.wiki). SPE 14265 could not be retrieved (OnePetro paywall). Still unresolved; impact 0.053 psia at gg=0.75.
- DPR A3 last digit: -0.57832720 (zFactor + Ahmed, two retrieved sources) vs -0.57832729 (predico). The original IP 74-008 was not retrieved. Impact < 1e-8 on Z.
- DAK coefficients A1..A11: three independent retrieved sources (Ahmed textbook, zFactor R, GasCompressibility-py) all match the card exactly. The original JCPT 1975 was still not retrieved — the coefficient values still rest on a consensus of reproductions, not on primary text.
- HY coefficients (0.06125, 14.76/9.76/4.58, 90.7/242.2/42.4, 2.18+2.82t): match exactly in Whitson Eq. 3.42-3.43 (full text) and Ahmed Eq. 2-36/2-37 (full text). The original OGJ 1973 was not retrieved.
- Sutton validity window (0.57 < gg < 1.68, H2S = 0, N2 < 1%, CO2 < 1%): nafta.wiki only (secondary); not confirmed from any source retrieved this session.
- Wichert-Aziz pressure/temperature dataset bounds (154-7026 psia, 40-300 F): not confirmed; the card is right to flag them, and I could not confirm them either.
- Wichert-Aziz composition limits: Whitson (retrieved) writes CO2 0-55% and H2S 0-74%; the 54.4%/73.8% variant is not confirmed.
- Methane Tc = 343.0 deg R and Pc = 666.4 psia as used in the physical anchor: still recalled, not retrieved from a property table (GPA 2145 / NIST / DIPPR). Do not turn them into an assertion.
- GPA 2145 Mair = 28.9625: not retrieved. It should also be noted that Ahmed uses a THIRD variant, Mair = 28.96, throughout his worked examples — reproducing Ahmed's examples needs 28.96, not 28.97.
- The "ground truth" chart is a third party's digitisation (zFactor inst/extdata) of the 1942 Standing-Katz chart. I reproduce all of its statistics exactly, but it is still not a physical measurement. Accuracy against modern experimental PVT data was never assessed — neither in the card nor in this review.
- The DAK two-part validity window (Ppr < 1.0 for 0.7 < Tpr <= 1.0) comes only from the pengtools wiki; Ahmed (retrieved) gives only '0.2 <= ppr <= 30, 1.0 < Tpr <= 3.0'. The low-temperature sub-window remains unverified.

### Missing before implementation

- A written decision on the Standing dry-gas ppc: 667 or 677, with an UNVERIFIED flag, an overridable constant, and a test that deliberately does NOT lock the value tighter than 10 psia until the original Standing 1977 is obtained.
- The dZ/dP relation for DAK and DPR. The card warns that a wrong Fprime 'will silently corrupt any analytic dZ/dP', but it never writes dZ/dP down. For a gas reservoir lab this is mandatory (isothermal gas compressibility cg = 1/p - (1/Z)(dZ/dp)_T and the pseudo-pressure integral). Whitson Eq. 3.45 gives only the HY form. For DAK/DPR: from rho = R2/Z with R2 = 0.27*Ppr/Tpr, implicit differentiation gives dZ/dPpr = -(R2/rho^2)/(F'(rho) + R2/rho^2) * ... — it must be derived and verified numerically before use, not copied.
- The standard-conditions convention must be pinned down in a single module: psc = 14.696 vs 14.7 (Whitson Eq. 3.27 uses 14.7) vs 14.73, and Tsc = 60 F = 519.67 R. Without this, the molar-volume test will flap between versions.
- The choice of Mair must be pinned down and documented: 28.97 (Whitson/Standing/Sutton), 28.96 (all of Ahmed's worked examples), 28.9625 (GPA 2145). Reproducing published oracles depends on this choice.
- A table of component critical constants (C1..C7+, N2, CO2, H2S) for the Kay's rule path — the card references Whitson Eq. 3.50/3.54a/3.54b and Matthews et al. C7+ (Eq. 3.51a/3.51b) but carries not a single component Tc/pc value. The composition-based path cannot be implemented from this card.
- A dewpoint/two-phase guard: the card forbids use below the dewpoint but gives no operational criterion or API for rejecting it.
- The lower bracket for y in HY: the card says to clamp into (0,1) but gives no lower bracket proven to enclose the root. A sign argument is needed: f(y->0+) = -alpha*Ppr < 0 and f(y->1-) -> +inf, so [eps, 1-eps] is a valid bracket — that must be stated explicitly as the basis for the bisection fallback.
- Out-of-range policy: whether the library raises, warns, or clamps when Tpr < 1 (HY), Ppr > 25 (HY), gg outside 0.57-1.68 (Sutton), or acid gas > 74 mol% (Wichert-Aziz). The card names all the limits but does not choose the behaviour.
- Precision policy: the card is right that float32 will wreck R1; an explicit assertion is needed that every path is forced to float64.

### Recommended independent test oracles

**Ahmed sour-gas worked example, end-to-end (a replacement for the circular midstreamcalculator oracle)**

- Inputs: `gamma_g = 0.7, yCO2 = 0.05, yH2S = 0.10, P = 3500 psia, T = 160 deg F (620 deg R). Standing dry-gas pseudocriticals + Wichert-Aziz + Standing-Katz chart. Mair = 28.96, R = 10.73.`
- Expected: `Tpc = 389.38 deg R; ppc = 669.1 psia (with the constant 677; the constant 667 gives 659.1); epsilon = 20.735 deg R; T'pc = 368.64 deg R; p'pc = 630.44 psia; Ppr = 5.55; Tpr = 1.68; z = 0.89 (read from the chart); Ma = 20.27 lbm/lbmol; rho_g = 11.98 lbm/ft^3. My implementation this session: epsilon = 20.735 (exact match), T'pc = 368.64, p'pc = 630.47, Tpr = 1.6819, Ppr = 5.5514, Z_DAK = 0.8968 — consistent with the chart-read 0.89 to within 0.8%.`
- Why independent: A worked example published in a textbook, with Z read by a HUMAN from the Standing-Katz chart rather than produced by the correlation under test. It exercises the full chain (pseudocriticals -> WA -> Tpr/Ppr -> Z -> density) at once, and as a bonus it discriminates 677 vs 667 decisively through p'pc (630.44 vs 621.0) — something the methane anchor fails to do.

**Wichert-Aziz epsilon, isolated closed form**

- Inputs: `yCO2 = 0.05, yH2S = 0.10 (A = 0.15, B = 0.10)`
- Expected: `epsilon = 120*(0.15^0.9 - 0.15^1.6) + 15*(0.10^0.5 - 0.10^4) = 20.735 deg R (printed exactly so in Ahmed; I reproduce 20.7350).`
- Why independent: It touches no solver and no Z coefficient at all. It tests only the five epsilon constants (120, 0.9, 1.6, 15, 0.5, 4) against a published number. A failure here points straight at either a constant or a mole-percent-vs-fraction bug.

**Carnahan-Starling identity: the HY hard-sphere derivative**

- Inputs: `Symbolic/numerical verification that d/dy[(y + y^2 + y^3 - y^4)/(1-y)^3] = (1 + 4y + 4y^2 - 4y^3 + y^4)/(1-y)^4 for y in (0,1).`
- Expected: `An exact identity. The derivative N'(1-y) + 3N with N = y+y^2+y^3-y^4 gives 1 + 4y + 4y^2 - 4y^3 + y^4 — I rederived it by hand this session. If the code uses +y^4 (the Ahmed Eq. 2-37 typo), the numerator of the derivative becomes 1 + 4y + 4y^2 + 4y^3 - y^4 and the test fails.`
- Why independent: Pure calculus, depending on no literature and no fit. It is the only oracle that locks the SIGN on the y^4 term — the textbook typo the card does not warn about.

**Analytic derivative dF/drho vs complex-step / central difference, MANDATORY at rho != 1**

- Inputs: `Tpr in {1.05, 1.3, 1.7, 2.5} x Ppr in {0.5, 3, 10, 25} x rho in {0.05, 0.3, 0.8, 1.5, 2.2}, h = 1e-6 (or complex-step h = 1e-20 for machine precision).`
- Expected: `max relative deviation < 1e-6 (I measured 1.9e-9 for DAK and DPR combined). Discriminating points for the textbook typo (1 + 2*A11*rho^3): at Tpr=1.3, Ppr=3.0 -> correct/typo = 2.1174/2.0753 (rho=0.5), 0.6233/0.6233 (rho=1.0, INVISIBLE), 1.0204/1.2887 (rho=1.5), 3.3542/3.7144 (rho=2.0).`
- Why independent: Numerical calculus, not literature. Critically: the test MUST include points with rho != 1, because the Ahmed/zFactor typo is exactly zero at rho = 1. The card already names this trap; the oracle has to enforce it.

**Reduced density definition identity (Zc = 0.27)**

- Inputs: `For every (Tpr, Ppr) and every root rho the solver returns: compute rho * Z * Tpr / Ppr.`
- Expected: `= 0.27 exactly (I measured 0.270000000000000 at Tpr 1.1/1.5/2.5/3.0). For HY: y * Z / (alpha * Ppr) = 1 exactly.`
- Why independent: A dimensional/definitional identity, not a fit. It catches a Z recovered from the wrong iteration variable, an alpha computed twice with different values, or a solver that returns a spurious root.

**Ideal-gas asymptote and slope sign**

- Inputs: `Ppr -> 0 at fixed Tpr; then compare Z(Ppr=0.2) vs Z(Ppr=0.4).`
- Expected: `Z -> 1. Measured at Ppr=0.2: DAK 0.99921 / HY 1.00006 / DPR 0.99912 at Tpr=3.0 (exactly the card's numbers). The initial slope is NEGATIVE for every Tpr I tested (1.3, 2.0, 2.5, 3.0) — attraction dominates below the Boyle temperature. Do not assert Z <= 1: HY crosses slightly above 1.`
- Why independent: An exact thermodynamic limit (real gas -> ideal gas), not a published number. It catches unit errors (psig vs psia) and a sign error on the linear rho term.

**Standard molar volume from the oilfield R**

- Inputs: `Tsc = 519.67 deg R, psc = 14.7 psia, Z = 1.`
- Expected: `Vm = R*Tsc/psc = 379.38 scf/lbmol with R = 10.73146 and psc = 14.7 (Whitson Eq. 3.27 prints 379.4). With psc = 14.696 and R = 10.7315771 -> 379.48. I also verified the oilfield R from the exact SI definitions: 8.31446261815324 / 6894.757293168361 / 0.3048^3 * 453.59237 / 1.8 = 10.731577089 — the card's claim is CONFIRMED to the last digit.`
- Why independent: Pure unit arithmetic from the exact SI definitions; it does not touch the correlations at all. It catches an inverted Rankine conversion, lbmol vs mol, and an inconsistent choice of R.

**Digitised Standing-Katz chart regression fixture (569 points)**

- Inputs: `zFactor inst/extdata sk_lp_tpr_*.txt and sk_hp_tpr_*.txt for Tpr = 1.05, 1.10, 1.20, 1.30, 1.40, 1.50, 1.70, 2.00, 2.20, 2.40, 2.60, 3.00. Use the exact file abscissae (e.g. 7.004, 15.003), not the rounded ones.`
- Expected: `I reproduce ALL of the card's numbers exactly: AAPE DAK 1.094%, HY 1.746%, DPR 1.130%; max APE 18.46% / 28.75% / 18.77% (all at Tpr=1.05, Ppr ~1.39-1.75); per-Tpr AAPE Tpr=1.05 -> 4.961/8.826/5.218, Tpr=1.10 -> 2.081/3.489/1.865, and 0.139%-0.581% for all Tpr >= 1.20. Assert AAPE < 1.5% (DAK/DPR), < 2.0% (HY) over the whole set; < 0.7% per Tpr for Tpr >= 1.20.`
- Why independent: Semi-independent only, and it must be labelled as such: this is a third party's digitisation of the 1942 chart, not a measurement. Its value is as a REGRESSION fixture (catching drift between versions), not as a claim of physical accuracy. Its added value: my exact reproduction confirms that the card's entire numerical layer is honest and reproducible.

**Solver robustness: naive Newton failure counts (a regression over the card's claim)**

- Inputs: `Grid Tpr 1.0-3.0 step 0.05 x Ppr 0.2-30 step 0.2 (6150 points).`
- Expected: `REPRODUCED EXACTLY this session: DAK naive Newton on the pole-retaining form converged 6150/6150, mean 6.27 iterations, max 20. HY naive Newton failed 502/6150 with y0 = 0.001 and 1008/6150 with y0 = 0.0125*Ppr*t*exp(-1.2*(1-t)^2). The DAK form with the pole cleared (multiplied by rho) converges to NEGATIVE rho roots (negative Z) — I got 11 points, all at Tpr = 1.00, Ppr 2.8-4.8, Z from -0.314 to -0.533. Note: the card reports the location as Tpr = 1.05-1.10; I only reproduce the phenomenon at Tpr = 1.00, so its exact location depends on the details of the derivative implementation — the behaviour is real, but do not hard-code the coordinates.`
- Why independent: A numerical experiment rerun from scratch with a separate implementation. It turns the card's narrative claim into an assertion that will fail if someone 'tidies up' the residual by multiplying out its pole.

**Methane-gravity sanity check — DEMOTED in status, not to be used as a discriminator**

- Inputs: `gamma_g = 16.043/28.97 = 0.5538 into the Standing dry-gas correlation.`
- Expected: `Tpc = 344.15 deg R, Ppc = 673.81 psia (constant 677) or 663.81 psia (constant 667). Assert loosely only: Tpc within 2% of methane Tc and Ppc within 2% of methane Pc, with Tc/Pc taken from a RETRIEVED property table (GPA 2145 / NIST), not from memory.`
- Why independent: A physical anchor against a pure component — valid as an order-of-magnitude smoke test, NOT valid as the arbiter between 667 and 677 (the two differ by 1.5%, inside the correlation's own scatter, and this anchor gives the opposite answer to the published worked example). It is listed here precisely so that the limits of its usefulness are documented.

## Sources

| Citation | Access level | Supports |
|---|---|---|
| Whitson, C.H. and Brulé, M.R.: Phase Behavior, SPE Monograph Series Vol. 20, Chapter 3 'Gas and Oil Properties and Correlations' (PDF, 29 pp.), Society of Petroleum Engineers | full-text retrieved | THE primary-quality anchor for this card. Hall & Yarborough equation and its analytic derivative (Eqs. 3.42-3.45) verbatim; Sutton (Eqs. 3.47a/b); Standing dry (3.48a/b) and wet (3.49a/b); Kay's mixing rule (3.50); Matthews et al. C7+ criticals (3.51); Wichert-Aziz (3.52a/b/c) with the 0-55% CO2 / 0-74% H2S range; non-hydrocarbon stripping and recombination (3.53, 3.54); R = 10.73146 psia*ft3/(lbmol*degR) (3.23); Mair = 28.97 (3.28); 379.4 scf/lbmol (3.27); the joint DAK/HY validity statement 1 <= Tr <= 3, 0.2 <= pr <= 25-30; the HY initial guess y = 0.001; and the explicit statement that HY 'smoothed' a Standing-Katz chart discrepancy for 1.05 <= Tr <= 1.15. NOTE: the PDF is served over a host with an expired TLS certificate; I fetched it with verification disabled. |
| aegis4048, GasCompressibility-py, source files gascompressibility/z_correlation/DAK.py, hall_yarborough.py, pseudocritical/sutton.py (GitHub, master branch) | full-text retrieved | Independent reference implementation. DAK A1..A11 and the full functional form; Hall & Yarborough alpha/A/B/C groups; Sutton Tpc/Ppc (with the 131.07 variant); Wichert-Aziz epsilon and Tpc' with units documented as deg R / psia. SECONDARY: a package, not a derivation — used here only as a cross-check on coefficient values. |
| CRAN package zFactor (f0nzie), R sources R/Dranchuk-AbouKassem.R, R/Dranchuk-Purvis-Robinson.R, R/Hall-Yarborough.R, and the digitised Standing-Katz chart data in inst/extdata/sk_lp_tpr_*.txt and sk_hp_tpr_*.txt | full-text retrieved | DPR A1..A8 and its correct Fprime; DAK residual in the R1..R5 form; the HY Newton implementation and the y0 = 0.0125*Ppr*t*exp(...) initial guess; and 569 digitised Standing-Katz (Tpr, Ppr, Z) points used as the independent numerical check set. ALSO the source of the confirmed DAK Fprime typo (rhor^3 for rhor^2). SECONDARY, and in one place demonstrably wrong — cite it for data, not for authority. |
| pengtools wiki, 'Dranchuk correlation' | full-text retrieved | DAK A1..A11; rho_r = 0.27*Ppr/(Z*Tpr); and the two-part published validity window (0.2 <= Ppr < 30 with 1.0 < Tpr <= 3.0, and Ppr < 1.0 with 0.7 < Tpr <= 1.0). SECONDARY. |
| Nafta Wiki, 'Hall and Yarborough (1973) Z-factor Correlation' and 'Pseudo-Critical Point Correlations' | full-text retrieved | HY equation with A1..A4 groups and the t = 1/Tpr substitution; HY range 1.05 <= Tpr <= 3, 0.2 <= Ppr <= 15; Sutton with the 131.07 variant and the gamma_g range 0.57 to 1.68 with H2S = 0, N2 < 1%, CO2 < 1%; Standing condensate form 187/330/71.5 and 706/51.7/11.1. SECONDARY, and its 'Standing dry gas' entry is internally inconsistent (it repeats the condensate equation) — do not rely on it for the Standing split. |
| Midstream Calculator, 'Z-Factor (Gas Compressibility Factor) Fundamentals' | full-text retrieved | Cross-check only. DAK A1..A11 and form; HY groups and the y0 = 0.0125*Ppr*t*exp(...) guess; Wichert-Aziz epsilon, Tpc', Ppc'; and the end-to-end sour-gas worked example (gamma 0.75, 10% CO2, 5% H2S, 1500 psia, 150 F -> Z ~ 0.861) that my implementation reproduces. SECONDARY — an engineering calculator website, explicitly NOT an authority for any derivation. |
| Predico / AFA Documentation, Theory Reference Manual, 'Gas Deviation Factor' | full-text retrieved | DPR A1..A8 (giving A3 = -0.57832729, the variant that disagrees with zFactor's last digit). SECONDARY. |
| Dranchuk, P.M. and Abou-Kassem, J.H.: 'Calculation of Z Factors for Natural Gases Using Equations of State,' Journal of Canadian Petroleum Technology (July-Sept 1975) 14, No. 3, 34-36 | abstract/metadata only | The primary source for DAK. NOT RETRIEVED — paywalled. Its stated accuracy and exact validity wording remain unverified. |
| Hall, K.R. and Yarborough, L.: 'A New Equation of State for Z-factor Calculations,' Oil and Gas Journal (18 June 1973) 82; and Yarborough, L. and Hall, K.R.: 'How to Solve Equation of State for Z-factors,' Oil and Gas Journal (18 Feb 1974) 86 | abstract/metadata only | The primary source for HY (1973) and for the y0 = 0.0125*Ppr*t*exp(...) initial guess (1974). NOT RETRIEVED. |
| Dranchuk, P.M., Purvis, R.A. and Robinson, D.B.: 'Computer Calculation of Natural Gas Compressibility Factors Using the Standing and Katz Correlation,' Institute of Petroleum Technical Series No. IP 74-008 (1974) | Unverified — cited source not inspected - not retrieved | The primary source for DPR. Citation details themselves are recalled and should be checked before being printed in a bibliography. |
| Sutton, R.P.: 'Compressibility Factors for High-Molecular-Weight Reservoir Gases,' SPE 14265, presented at the 1985 SPE Annual Technical Conference and Exhibition, Las Vegas, 22-25 September 1985 | abstract/metadata only | The primary source for the Sutton pseudocriticals and the only thing that would settle 131 vs 131.07. NOT RETRIEVED. |
| Ahmed, T.: Reservoir Engineering Handbook, Eq. 2-18 / 2-19 and the worked examples that follow them; and the DPR coefficient list A1..A8 | full-text retrieved, via a file-sharing aggregator (dokumen.pub); no URL, digest or retrieval date was recorded at the time | Added after the claims audit: this source supplies the library's shipped Standing dry-gas Ppc default (677) and the DPR A3 value -0.57832720, and it was cited throughout this card's prose without ever appearing in this table. SECONDARY, and its retrieval route is not re-checkable by a third party from what is recorded here. It is one of the two sides of the unresolved 667/677 conflict; the other, Whitson & Brulé, was itself fetched over a host with an expired TLS certificate with verification disabled. Neither side of that conflict rests on a re-checkable retrieval, and the primary source has never been read. |
| Standing, M.B.: Volumetric and Phase Behavior of Oil Field Hydrocarbon Systems, Society of Petroleum Engineers, Dallas (1977) | Unverified — cited source not inspected - not retrieved | The primary source for the dry-gas and wet-gas pseudocritical correlations. **[SUPERSEDED] This cell previously read that the coefficients "come from Whitson & Brulé's retrieved reproduction of it, corroborated by Ahmed".** Ahmed does not corroborate Whitson & Brulé on the dry-gas Ppc constant: Whitson & Brulé print 667, Ahmed prints 677, and the conflict is unresolved because this primary source has never been read. |
| Wichert, E. and Aziz, K.: 'Calculate Z's for Sour Gases,' Hydrocarbon Processing (May 1972) 51, 119-122 | Unverified — cited source not inspected - not retrieved | The primary source for the sour-gas correction. The equation form and the 0-55% / 0-74% composition limits come from Whitson & Brulé's retrieved reproduction. |
| CODATA 2019 SI redefinition: R = 8.31446261815324 J/(mol*K) exact; plus the exact unit definitions lbf = 4.4482216152605 N, inch = 0.0254 m, ft = 0.3048 m, lb = 0.45359237 kg | Unverified — cited source not inspected - not retrieved | The derivation of R = 10.7315770890 psia*ft3/(lbmol*degR). The arithmetic was done this session and the intermediate 1 psi = 6894.757293168361 Pa was reproduced from the base definitions as a check, but the CODATA value itself was not re-retrieved. |

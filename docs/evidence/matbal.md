# Evidence card: Gas material balance

> Each card records what an implementer needs, where it came from, and how far it was
> verified. A card is not an authority: it is a statement of evidence with its access
> level attached. Items marked unverified are unverified, and the implementation must
> treat them as such.

**Adversarial review verdict:** `SOUND_WITH_CORRECTIONS`  
**Corrections applied:** 9  
**Items left unverified:** 9

## Summary

Bg follows directly from pV = ZnRT applied at reservoir and standard conditions with Zsc taken as 1: Bg = (psc/Tsc)(zT/p). With psc = 14.696 psia and Tsc = 519.67 °R this gives 0.0282795 rcf/scf, and dividing by 5.615 ft3/bbl gives 0.0050364 rb/scf — the "0.02827" and "0.005035" coefficients are not fitted constants, they are psc/Tsc in two unit conventions, so the standard-condition basis must be an explicit input, never hard-coded. I proved this matters: within one single paper (Pletcher, SPE 75354) the two-cell simulation Bg table is reproduced only by psc = 15.025 psia (Texas-style base) while the Oklahoma Morrow field table is reproduced by psc = 14.699 psia — a 2.2% Bg difference between two tables in the same reference. The volumetric line p/Z = (pi/Zi)(1 - Gp/G) is an inventory balance under a constant hydrocarbon pore volume; it requires no water influx, negligible cf and cw, no retrograde condensation, single tank, and a volume-averaged (not flowing) pressure. The general balance is F = G(Eg + Efw) + We with F = Gp·Bg + Wp·Bw, Eg = Bg - Bgi and Efw = Bgi[(Swi·cw + cf)/(1 - Swi)](pi - p) — item (d)'s form confirmed verbatim against two independent retrieved sources. The critical item (e) is fully quantified and independently reproduced: a weak pot aquifer of equal pore volume produces a modified p/Z plot with R2 = 0.9998 over ten years that still overestimates OGIP by +8.2% at 11% recovery and +4.0% at 54% recovery; without the cf correction the same data give +15.3% at 11% recovery. The documented Oklahoma Morrow field case gives +11% (modified p/Z) and +16% (conventional p/Z) against the pot-aquifer solution. Every published number in both cases was recomputed from the published tables and matched to 3-4 significant figures, so both are directly usable as regression tests.

## Equations

### Real gas equation of state (field units)

```
p * V = Z * n * R * T
```

*Unit system:* oilfield (field) units

| Symbol | Meaning | Units |
|---|---|---|
| `p` | ABSOLUTE pressure | psia |
| `V` | gas volume | ft^3 |
| `Z` | gas deviation (compressibility) factor | dimensionless |
| `n` | number of lb-moles | lbmol |
| `R` | universal gas constant | psia*ft^3/(lbmol*degR) |
| `T` | ABSOLUTE temperature | degR |

Assumptions:

- Z is evaluated at the reservoir's isothermal T and at the pressure of interest
- R = 10.732 psia*ft^3/(lbmol*degR) is the field-unit value; using 10.73 introduces ~2e-4 relative error
- degR = degF + 459.67 (Dake writes 460, a 0.33 degR / ~0.05% bias at 660 degR)

*Source:* Dake, Fundamentals of Reservoir Engineering, eq. (1.15) and the text following eq. (1.13), pp. 12-13  
*Access:* full-text retrieved

### Bg definition on a molar basis (reservoir volume per standard volume)

```
Bg = V_res / V_std = (Z_res * n * R * T_res / p_res) / (Z_std * n * R * T_std / p_std) = (Z_res * T_res * p_std) / (Z_std * T_std * p_res)
```

*Unit system:* unit-system independent as written (ratio); becomes oilfield on substitution

| Symbol | Meaning | Units |
|---|---|---|
| `Bg` | gas formation volume factor | res volume / std volume (rcf/scf or rb/scf) |
| `V_res` | volume occupied at reservoir p,T by the gas that yields V_std at standard conditions | ft^3 (rcf) or bbl (rb) |
| `V_std` | same mass of gas measured at standard conditions | scf |
| `p_std, psc` | standard-condition ABSOLUTE pressure | psia |
| `T_std, Tsc` | standard-condition ABSOLUTE temperature | degR |
| `Z_std, Zsc` | Z factor at standard conditions | dimensionless |

Assumptions:

- The number of moles n is unchanged between reservoir and surface. This fails for a retrograde gas condensate once liquid drops out in the reservoir, and for any gas that partitions into the water phase
- T_res is constant (isothermal depletion)
- n cancels exactly, so Bg is a pure state ratio

*Source:* IHS/Fekete Harmony 'Material Balance Analysis Theory' (equation image gasmatbal_theory_gas_law_eqn.png, read directly); Adewumi, PNG 520 (Penn State) eq. (18.6)-(18.7)  
*Access:* full-text retrieved

### Bg in reservoir cubic feet per standard cubic foot (rcf/scf)

```
Bg = (psc / Tsc) * (Z * T / p) / Zsc ;  with Zsc = 1, psc = 14.696 psia, Tsc = 519.67 degR:  Bg = 0.0282795 * Z * T / p   [rcf/scf]
```

*Unit system:* oilfield

| Symbol | Meaning | Units |
|---|---|---|
| `Bg` | gas formation volume factor | ft^3(reservoir)/scf |
| `p` | reservoir ABSOLUTE pressure | psia |
| `T` | reservoir ABSOLUTE temperature | degR |
| `Z` | gas deviation factor at p,T | dimensionless |

Assumptions:

- Zsc set to exactly 1. For a typical 0.65-0.70 gravity natural gas at 14.7 psia / 60 degF the true Zsc is about 0.998, so this introduces a ~0.2% systematic bias in Bg and therefore in G (REASONED, not retrieved)
- psc/Tsc is a DECLARED basis, not a universal constant. 14.696 psia / 519.67 degR gives 0.0282795; 14.65/519.67 gives 0.0281910; 15.025/519.67 (Texas-style base) gives 0.0289129 - a spread of 2.6%
- The 0.02827 you see in textbooks is simply psc/Tsc rounded to 4 significant figures

*Source:* Derived from the retrieved definition (Dake eq. 1.15; Adewumi eq. 18.7-18.8); coefficient computed this session to 6 sig figs  
*Access:* full-text retrieved (form); coefficient computed and cross-checked this session

### Bg in reservoir barrels per standard cubic foot (rb/scf), showing the 5.615 conversion

```
Bg[rb/scf] = Bg[rcf/scf] / 5.615 = (psc / (Tsc * 5.615)) * (Z * T / p) = 0.0050364 * Z * T / p   [rb/scf]   (1 bbl = 5.615 ft^3 exactly by petroleum convention).  Equivalently Bg[rb/Mscf] = 5.0364 * Z * T / p
```

*Unit system:* oilfield

| Symbol | Meaning | Units |
|---|---|---|
| `5.615` | cubic feet per US oil barrel (42 US gal); a definitional conversion, not a physical constant | ft^3/bbl |
| `Bg` | gas formation volume factor | rb/scf or rb/Mscf |

Assumptions:

- 5.615 is a rounding of 42 gal/bbl * 231 in^3/gal / 1728 in^3/ft^3 = 5.614583... ft^3/bbl. Using 5.615 rather than 5.614583 is a +7.4e-5 relative shift; harmless but it must be one constant used consistently
- Pletcher's SPE 75354 tables use rb/Mscf; Dake uses rcf/scf and its reciprocal. Mixing rb/Mscf with G in scf is a factor-1000 defect

*Source:* Adewumi PNG 520 eq. (18.9) and the sentence '1 RB = 5.615 RCF'; conversion arithmetic verified this session  
*Access:* full-text retrieved (with a defect - see uncertainties)

### Gas expansion factor E (Dake's reciprocal convention)

```
E = 1 / Bg[rcf/scf] = (Tsc / psc) * p / (Z * T) = 35.37 * p / (Z * T)   [scf/rcf]
```

*Unit system:* oilfield

| Symbol | Meaning | Units |
|---|---|---|
| `E` | gas expansion factor: standard cubic feet contained in one reservoir cubic foot | scf/rcf |

Assumptions:

- Same standard-condition basis as Bg. Dake's 35.37 is 1/0.0282795 = 35.3613 rounded up; the 0.02% difference is immaterial but should be noted if reproducing Dake's worked numbers to 5 figures
- Dake evaluates E at the reservoir CENTROID depth pressure, not at the gas-water contact

*Source:* Dake, Fundamentals of Reservoir Engineering, eq. (1.25) usage and Exercise 1.2 solution, pp. 33-35  
*Access:* full-text retrieved

### Volumetric (tank) dry-gas inventory balance

```
Gp = G - (HCPV) * E   where HCPV = V * phi * (1 - Swc) = G / Ei ;  hence  Gp = G - (G/Ei) * E  =>  Gp/G = 1 - E/Ei
```

*Unit system:* oilfield; all gas volumes at standard conditions

| Symbol | Meaning | Units |
|---|---|---|
| `Gp` | cumulative gas produced, measured at standard conditions | scf |
| `G` | gas initially in place (GIIP/OGIP) at standard conditions | scf |
| `HCPV` | hydrocarbon pore volume occupied by gas | rcf |
| `V` | net bulk reservoir rock volume | ft^3 |
| `phi` | porosity | fraction |
| `Swc, Swi` | connate / initial water saturation | fraction of pore volume |
| `E, Ei` | gas expansion factor at current and initial pressure | scf/rcf |

Assumptions:

- THE SINGLE LOAD-BEARING ASSUMPTION: HCPV is CONSTANT during depletion. Everything else follows.
- Production at standard conditions = (gas originally in place) - (gas still in the same pore volume at lower pressure)

*Source:* Dake, Fundamentals of Reservoir Engineering, eqs. (1.26), (1.33), (1.34), pp. 25-26  
*Access:* full-text retrieved

### (b) The volumetric dry-gas p/Z straight line

```
p/Z = (pi/Zi) * (1 - Gp/G)   ;  equivalently  p/Z = (pi/Zi) - [(pi/Zi)/G] * Gp   (slope m = -(pi/Zi)/G, y-intercept pi/Zi, x-intercept G)
```

*Unit system:* oilfield; p in psia (ABSOLUTE), Gp and G in the SAME standard-volume unit

| Symbol | Meaning | Units |
|---|---|---|
| `p` | current volume-averaged reservoir ABSOLUTE pressure | psia |
| `Z` | gas deviation factor at p and reservoir T | dimensionless |
| `pi` | initial reservoir ABSOLUTE pressure at the same datum | psia |
| `Zi` | gas deviation factor at pi and reservoir T | dimensionless |
| `Gp` | cumulative gas production at standard conditions | scf (or Mscf/Bscf, matching G) |
| `G` | gas initially in place at standard conditions | same unit as Gp |

Assumptions:

- FULL LIST for the straight line to be valid and its x-intercept to equal the true G:
- 1. No water influx (We = 0) - the aquifer is absent or so small its expansion is negligible
- 2. Hydrocarbon pore volume constant: connate-water expansion (cw*Swi) and pore-volume compaction (cf) are negligible relative to gas compressibility cg ~ 1/p. Dake's worked check: cw = 3e-6, cf = 10e-6, Swc = 0.2, dp = 1000 psi gives a 1.3% effect
- 3. Dry gas, or at least no retrograde liquid dropout in the reservoir - n does not change, and Z is a single-phase Z. For a gas condensate below dew point you must use a two-phase Z
- 4. Isothermal depletion at a single reservoir temperature T
- 5. Standard-condition basis (psc, Tsc, Zsc) identical for G, Gp and Bg - it cancels out of p/Z but NOT out of G computed volumetrically
- 6. The reservoir behaves as ONE tank: no communication with other reservoirs, no gas influx, no injection
- 7. p is a volume-averaged (pore-volume-weighted) reservoir pressure at a fixed datum, referred consistently (Dake: the centroid depth). NOT a flowing pressure, NOT an arithmetic well average with uneven drainage volumes
- 8. Z evaluated by a single consistent correlation/EOS over the whole history, at reservoir T
- 9. Gp measured at the same declared standard conditions as the sales meter, with shrinkage/fuel/flare accounted consistently
- 10. No adsorbed/desorbed gas (fails for coalbed methane and organic shale, where King's p/Z* is required)

*Source:* Dake eq. (1.35), p. 25; IHS/Fekete Harmony 'Material Balance Analysis Theory' (gasmatbal_theory_pz_eqn.png, read directly)  
*Access:* full-text retrieved

### (d) Rock and connate-water expansion term - CONFIRMED EXACT FORM

```
Efw = Bgi * [ (cw * Swi + cf) / (1 - Swi) ] * (pi - p)     [rb/Mscf or rcf/scf, same unit as Bgi]
and the reservoir-volume contribution is  G * Efw = G * Bgi * [ (cw*Swi + cf) / (1 - Swi) ] * (pi - p)     [res bbl]
```

*Unit system:* oilfield

| Symbol | Meaning | Units |
|---|---|---|
| `Efw` | cumulative formation and connate-water expansion per unit of gas in place | RB/Mscf (Pletcher) or rcf/scf |
| `Bgi` | gas FVF at initial reservoir pressure pi | RB/Mscf |
| `cw` | connate water isothermal compressibility | 1/psi |
| `cf` | formation (pore-volume) compressibility, cf = (1/Vf)(dVf/dp) at constant grain pressure convention | 1/psi |
| `Swi` | initial (connate) water saturation | fraction |
| `pi - p` | pressure DROP from initial, always taken as a positive number | psi |
| `G` | gas initially in place | Mscf |

Assumptions:

- DERIVATION (verified): total pore volume Vf = HCPV/(1 - Swi); connate water volume Vw = Vf*Swi = HCPV*Swi/(1 - Swi). Reduction in HCPV = (cw*Vw + cf*Vf)*(pi - p) = HCPV * [(cw*Swi + cf)/(1 - Swi)] * (pi - p). Substituting HCPV = G*Bgi gives the form above.
- cf and cw are CONSTANT over the pressure range. This is the weak point in geopressured reservoirs, where cf is strongly pressure-dependent and can be hysteretic (compaction is not fully reversible)
- cf is defined on PORE volume, not bulk volume and not rock-matrix volume. Mixing the three definitions is a common silent defect
- The (1 - Swi) in the DENOMINATOR is what converts a per-HCPV basis to a per-pore-volume basis. Omitting it understates the term by the factor (1 - Swi)
- The sign: this is a REDUCTION in hydrocarbon pore volume, which acts like extra production, so it appears with a + sign on the expansion (right-hand) side of F = G(Eg + Efw) + We
- cw here is connate water only; aquifer water compressibility enters separately through We
- Dake's identical form appears as a bracket [1 - (cw*Swc + cf)*dp/(1 - Swc)] multiplying E/Ei in his eq. (1.39)

*Source:* Pletcher, SPE 75354 (SPE Res Eval & Eng, Feb 2002), eq. (4); IHS/Fekete Harmony (matbal_theory_water_fm_exp_eqn.png: Efw = (cf + cw*Sw)/(1 - Sw) * dp, per unit HCPV); Dake eq. (1.38)-(1.39)  
*Access:* full-text retrieved - confirmed independently by TWO retrieved sources plus first-principles rederivation

### (c) GENERAL gas material balance - Havlena-Odeh arrangement

```
F = G * (Eg + Efw) + We
where
  F   = Gp * Bg + Wp * Bw            [res bbl]   (cumulative reservoir voidage)
  Eg  = Bg - Bgi                      [RB/Mscf]   (cumulative gas expansion)
  Efw = Bgi * (Swi*cw + cf)/(1 - Swi) * (pi - p)   [RB/Mscf]
  We  = cumulative water influx       [res bbl]
Defining Et = Eg + Efw, the Havlena-Odeh straight-line form is:
  F / Et = G + We / Et
so a plot of F/Et vs Gp is HORIZONTAL at height G for a pure depletion reservoir, and sloping when We != 0 (the Cole plot, or its Efw-corrected 'modified Cole' version).
```

*Unit system:* oilfield: F and We in reservoir barrels; Bg, Bgi, Eg, Efw in RB/Mscf; G, Gp in Mscf; Wp in STB; Bw in RB/STB

| Symbol | Meaning | Units |
|---|---|---|
| `F` | cumulative reservoir voidage (underground withdrawal) | res bbl |
| `Gp` | cumulative gas production at standard conditions | Mscf |
| `Wp` | cumulative water production measured at the SURFACE (stock tank) | STB |
| `Bw` | water formation volume factor - converts produced STB to reservoir barrels | RB/STB |
| `We` | cumulative water influx from the aquifer | res bbl in Pletcher's convention; STB in Dake's convention (then multiplied by Bw) |
| `Et` | total reservoir expansion = Eg + Efw | RB/Mscf |

Assumptions:

- SIGN CONVENTIONS - three equivalent conventions exist and MUST NOT be mixed:
- (i) Pletcher/Havlena-Odeh: Wp*Bw is part of the WITHDRAWAL F on the left; We sits alone on the right in RESERVOIR barrels. F = Gp*Bg + Wp*Bw = G(Eg+Efw) + We
- (ii) Dake: net influx (We - Wp)*Bw appears on the RIGHT, with We and Wp both in STB. Wp is NOT in the withdrawal term
- (iii) IHS/Fekete general MBE: Wp*Bw on the left with the production terms, We*Bw on the right
- DEFECT TO AVOID: putting Wp*Bw in F AND also using (We - Wp*Bw) on the right double-counts produced water and biases G
- Bw is close to unity (1.045-1.057 in Pletcher's example) because gas solubility in water is small; do not silently set it to exactly 1 for a high-pressure, high-temperature case
- Water influx is TIME-DEPENDENT for any aquifer larger than the reservoir. F = G(Eg+Efw)+We is still an exact volume balance at each instant, but We must come from an aquifer model (pot/Schilthuis/Fetkovich/van Everdingen-Hurst), and choosing that model is a fitted, non-unique step
- The equation is ZERO-DIMENSIONAL: it is evaluated at a point, comparing current volumes at p with original volumes at pi. It is NOT evaluated step-wise or differentially
- This form assumes no gas cap, no oil leg, no gas injection and no gas influx from a connected reservoir

*Source:* Pletcher, SPE 75354, eqs. (1), (2), (3), (4), (6), (7); IHS/Fekete Harmony general MBE image matbal_theory_general_eqn.png  
*Access:* full-text retrieved

### Cole plot rearrangement (the water-drive diagnostic)

```
Gp * Bg / (Bg - Bgi) = G + (We - Wp*Bw) / (Bg - Bgi)
Plot y = Gp*Bg/(Bg - Bgi) against x = Gp.  Depletion drive: horizontal line at y = G.  Strong waterdrive: positive slope.  Moderate: hump-shaped.  WEAK waterdrive: NEGATIVE slope (and the apparent OGIP decreases with time).  Significant cf with no aquifer also produces a negative slope on the ORIGINAL Cole plot but a horizontal 'modified' Cole plot (F/Et vs Gp).
```

*Unit system:* oilfield

| Symbol | Meaning | Units |
|---|---|---|
| `y` | apparent OGIP that would be calculated assuming no water drive | Mscf |

Assumptions:

- Derived by neglecting Efw in eq. (1) then rearranging; the modified Cole plot F/Et restores Efw
- Cole's extrapolation of the SLOPING line back to the y-intercept is explicitly NOT recommended by Pletcher: 'the slope usually changes with each plotted point'
- The most recent plotted point is a useful UPPER BOUND on OGIP for a weak waterdrive

*Source:* Pletcher, SPE 75354, eq. (5) and Fig. 1; Dake Fig. 6.6 (cited therein)  
*Access:* full-text retrieved

### (c) Water-drive p/Z form (Dake)

```
p/Z = (pi/Zi) * [ 1 - Gp/G ] / [ 1 - We*Ei/G ]
equivalently, as printed by Dake:  p/Z = (pi/Zi) * (1 - Gp/G) * 1/(1 - We*Ei/G)
with We*Ei/G = the fraction of the initial hydrocarbon pore volume flooded by water, always < 1.
The underlying inventory balance is: Gp = G - (G/Ei - We) * E
```

*Unit system:* oilfield; We in the same reservoir-volume unit as G/Ei (i.e. rcf if Ei is scf/rcf)

| Symbol | Meaning | Units |
|---|---|---|
| `We` | cumulative water influx (net of produced water, if produced water is subtracted here) | reservoir volume consistent with G/Ei |
| `We*Ei/G` | fraction of the original HCPV now occupied by encroached water | fraction, < 1 |

Assumptions:

- Dake's eq. (1.40)/(1.41) neglects connate-water expansion and pore compaction; add Efw for the full form
- Dake: 'If some of the water influx has been produced it can be accounted for by subtracting this volume, Wp, from the influx, We' - i.e. this We is the NET influx in Dake's arrangement
- Dake assumes no difference between surface and reservoir water volumes here (Bw = 1); relax this to (We - Wp)*Bw for rigour
- The equation is NON-LINEAR in Gp, which is precisely why the straight-line extrapolation fails
- Effect of the influx is to HOLD p/Z UP for a given Gp, so the apparent x-intercept moves right

*Source:* Dake, Fundamentals of Reservoir Engineering, eqs. (1.40), (1.41), Fig. 1.11, pp. 29-30  
*Access:* full-text retrieved

### Bruns/Dake apparent-GIIP straight line for a water-drive gas reservoir

```
Apparent gas in place:  Ga = Gp / (1 - E/Ei)
True gas in place:      G  = (Gp - We*E) / (1 - E/Ei)
Subtracting:            Ga = G + We*E / (1 - E/Ei)
Plot Ga on the y-axis against We*E/(1 - E/Ei) on the x-axis; with the CORRECT aquifer model the points fall on a straight line whose y-intercept is the true G. A curved trend means the aquifer model is wrong (too small / too large).
```

*Unit system:* oilfield

| Symbol | Meaning | Units |
|---|---|---|
| `Ga` | apparent GIIP computed from the depletion balance at each history point | scf |
| `We` | cumulative water influx from the trial aquifer model | reservoir volume consistent with E |

Assumptions:

- Successive Ga values INCREASE with time when an active water drive is present - a direct diagnostic
- Aquifer fitting is explicitly 'a trial and error business which continues until a straight line is obtained' (Dake) - it is a fitted, non-unique procedure

*Source:* Dake, Fundamentals of Reservoir Engineering, eqs. (1.42), (1.43), (1.44), Fig. 1.12, pp. 31-32, after Bruns, Fetkovich and Meitzen, JPT 17(3), 1965  
*Access:* full-text retrieved

### Pot (small, time-independent) aquifer model and the pot-aquifer plot

```
We = (cw + cf) * W * (pi - p)                                        (eq. 12)
Substituting into F = G(Eg+Efw)+We and rearranging gives a straight line:
  F / Eg = G + [ G*Bgi*(Swi*cw + cf)/(1 - Swi) + (cw + cf)*W ] * (pi - p)/Eg      (eq. 13)
Plot F/Eg on y against (pi - p)/Eg on x. y-intercept = G; slope A = the bracket.
Aquifer size:  W = [ A - G*Bgi*(Swi*cw + cf)/(1 - Swi) ] / (cw + cf)             (eq. 14)
If there is NO aquifer (W -> 0), the slope instead yields cf:
  cf = A*(1 - Swi)/(G*Bgi) - Swi*cw                                              (eq. 15)
Original hydrocarbon pore volume:  PV = G*Bgi / (1 - Swi)                        (eq. 16)
```

*Unit system:* oilfield: F in res bbl, Eg in RB/Mscf, G in Mscf, W in res bbl, A in RB/psi

| Symbol | Meaning | Units |
|---|---|---|
| `W` | aquifer original water in place | res bbl |
| `A` | slope of the pot-aquifer plot | RB/psi |
| `cw + cf` | total aquifer compressibility | 1/psi |

Assumptions:

- Pot aquifer = any pressure drop in the reservoir is transmitted INSTANTANEOUSLY through the whole aquifer. Valid only for a small, high-permeability, hydraulically-isolated water leg (Dake: aquifer of the same order of magnitude as the reservoir; Gulf Coast fault-bounded sands)
- Requires NO prior knowledge of aquifer size, cf, cw or even Swi to get G - that is the plot's value
- Early-time points fall BELOW the eventual true straight line and have a negative slope, so the plot is unusable in very early life (in Pletcher's example the slope does not turn over until ~9 months)
- Eq. 15's cf is only meaningful if you are confident there is no aquifer; a cf that comes out implausibly large (Pletcher: 14.3e-6 vs known 6e-6, and 12e-6 vs estimated 3e-6) is itself evidence of an unaccounted energy source

*Source:* Pletcher, SPE 75354, eqs. (12)-(16), Figs. 4 and 7  
*Access:* full-text retrieved

### Roach plot and modified Roach plot (cf unknown, with/without water drive)

```
Roach (eq. 17):
  [ (p/z)i/(p/z) - 1 ] / (pi - p)  =  (1/G) * [ (p/z)i/(p/z) * Gp ] / (pi - p)  -  [ (We - Wp*Bw)/((pi - p)*G*Bgi)  -  (Swi*cw + cf)/(1 - Swi) ]
Slope = 1/G, so G = 1/slope; the y-intercept carries cf, cw and the water terms.
Modified Roach (eq. 18), for a POT aquifer, moves the water-production term into the x-axis:
  [ (p/z)i/(p/z) - 1 ]/(pi - p) = (1/G) * [ (p/z)i/(p/z)*Gp + Wp*Bw/Bgi ]/(pi - p)  +  [ (cw + cf)*W/(G*Bgi) - (Swi*cw + cf)/(1 - Swi) ]
```

*Unit system:* oilfield

| Symbol | Meaning | Units |
|---|---|---|
| `(p/z)i` | initial p/Z | psia |
| `1/G` | slope of the Roach plot | 1/Mscf |

Assumptions:

- In the presence of a water drive the plain Roach y-intercept is NOT constant (the We and Wp terms move), so the correct slope is hard to establish and 'significant errors in OGIP can easily result'
- The modified form fixes this only when the pot-aquifer model applies
- Solves for G WITHOUT knowing cf - the point of the method

*Source:* Pletcher, SPE 75354, eqs. (17) and (18), citing Roach (ref 17) and Poston et al. (ref 11, their eq. 6.10)  
*Access:* full-text retrieved

### Ramagost-Farshad corrected p/Z for abnormally (geo)pressured gas reservoirs

```
(p/Z) * [ 1 - ce*(pi - p) ]  =  (pi/Zi) * ( 1 - Gp/G )
with  ce = (cw*Swi + cf) / (1 - Swi)
Plot the LEFT side against Gp; the x-intercept is G.
```

*Unit system:* oilfield; p, pi in psia (ABSOLUTE); ce in 1/psi

| Symbol | Meaning | Units |
|---|---|---|
| `ce` | effective (rock + connate water) compressibility referred to hydrocarbon pore volume | 1/psi |
| `1 - ce*(pi - p)` | the Ramagost-Farshad adjustment factor | dimensionless, must remain > 0 |

Assumptions:

- Validity requires ce*(pi - p) < 1 (stated explicitly in the IHS/Fekete well-test documentation). At ce = 2e-5 1/psi and a 6000 psi drawdown the factor is already 0.88
- cf constant. In real geopressured rock cf declines strongly as pressure falls and compaction is partly irreversible; this is the main physical weakness
- Water influx is assumed ZERO. The correction fixes compaction, NOT aquifer support - Pletcher's counterexample shows a corrected p/Z can still be 8% high when a weak aquifer is present
- IMPORTANT: this equation form was NOT retrieved from the original SPE 10125. It is reconstructed from secondary descriptions AND validated numerically: using ce = (cw*Swi + cf)/(1 - Swi) with cw=3e-6, cf=6e-6, Swi=0.15 on Pletcher's Table 2/3 reproduces his published 'modified p/z' OGIP values 109.0 / 107.3 / 104.8 Bcf exactly, and his R2 = 0.9998

*Source:* Ramagost, B.P. and Farshad, F.F.: 'P/Z Abnormally Pressured Gas Reservoirs', SPE-10125-MS, SPE ATCE, San Antonio, 5-7 Oct 1981 (abstract retrieved via OSTI 6470177); form reconstructed and numerically validated against Pletcher SPE 75354  
*Access:* abstract/metadata only for the primary; equation form reconstructed from secondary sources and verified numerically this session

### Fekete/IHS advanced p/Z** (unified over-pressure, water-drive and connected-reservoir correction)

```
p / Z**  =  (pi / Zi**) * ( 1 - Gp/G )
with
  Z** = p / { [ (1/Sgi) * (p/Z) * (Sgi - cwip - cep - cd) + (pi/Zi) * (G/Gf - 1) ] * (Gf/G) }
and the over-pressure compressibility term
  cep = ( cf + Swi*cw + Soi*co ) * (pi - p)
```

*Unit system:* oilfield

| Symbol | Meaning | Units |
|---|---|---|
| `Z**` | modified compressibility factor that restores linearity of the p/Z plot | dimensionless |
| `Sgi` | initial gas saturation | fraction |
| `cep` | cumulative formation + residual-fluid expansion as a fraction of initial pore volume | fraction |
| `cwip` | net encroached-water term as a fraction of initial pore volume (symbol definition NOT retrieved) | fraction |
| `cd` | desorption term (CBM/shale); zero for conventional gas (symbol definition NOT retrieved) | fraction |
| `Gf` | free gas in place (vs G = total gas in place including adsorbed) | scf |
| `Soi, co` | initial residual oil saturation and oil compressibility | fraction, 1/psi |

Assumptions:

- cep as printed uses the SIMPLE (pore-volume-referenced) grouping cf + Swi*cw + Soi*co, i.e. WITHOUT the 1/(1-Swi) factor, because it is referenced to initial PORE volume rather than hydrocarbon pore volume. Do not confuse it with Efw
- The rigorous forms use exp(...) rather than the (1 + x) linearisation; the approximate forms shown are the linearised versions
- The full symbol list for Z** was not retrieved; treat cwip and cd as unverified
- This is commercial-software documentation - a SECONDARY source. The underlying paper is Moghadam, Jeje and Mattar, 'Advanced Gas Material Balance in Simplified Format', JCPT 50(1), 2011 / PETSOC 2009-149, which was NOT retrieved

*Source:* IHS/Fekete Harmony Enterprise 2019.3 'Material Balance Analysis Theory' (equation images advgmb_theory_eqn_pzstarstar.png, advgmb_theory_eqn_zstarstar.png, advgmb_theory_eqn_cep_approx.png, read directly)  
*Access:* secondary source (vendor documentation), equation images retrieved

### Gas drive indices (solution-correctness check)

```
IGD = G*Eg / (Gp*Bg)                (gas drive index)
ICD = G*Efw / (Gp*Bg)               (formation + connate water compressibility drive index)
IWD = (We - Wp*Bw) / (Gp*Bg)        (water drive index)
IGD + ICD + IWD = 1
```

*Unit system:* oilfield; numerator and denominator both in res bbl

| Symbol | Meaning | Units |
|---|---|---|
| `IGD, ICD, IWD` | fraction of cumulative reservoir voidage supplied by each energy source | fraction |

Assumptions:

- If the raw indices do not sum to unity, a correct material-balance solution has NOT been obtained
- NEVER normalise the indices to sum to unity - Pletcher is emphatic that commercial software doing this 'deprives the engineer of a tool for evaluating the correctness of his solution and gives the false impression that a valid solution has been obtained'
- With field data the sum scatters either side of unity; a CONSISTENT trend (steadily increasing or decreasing) is the signature of a wrong solution, as opposed to noise

*Source:* Pletcher, SPE 75354, eqs. (8)-(11) and Tables 5, 6, 8  
*Access:* full-text retrieved

## Constants

| Name | Value | Units | Source | How verified |
|---|---|---|---|---|
| Universal gas constant, field units | `10.732` | psia*ft^3/(lbmol*degR) | Dake, Fundamentals of Reservoir Engineering, text following eq. (1.13), p. 12 | retrieved verbatim from full text this session |
| Standard pressure psc (1 atm basis, API/SPE default) | `14.696` | psia (ABSOLUTE) | Adewumi PNG 520 / Engineering LibreTexts 18.5 ('ps is 1 atm (14.696 psia)') | retrieved this session; and 14.696/519.67/5.615 = 0.0050364 reproduces the textbook 0.005035 coefficient |
| Standard temperature Tsc | `519.67 (i.e. 60 degF)` | degR (ABSOLUTE) | Adewumi PNG 520 / Engineering LibreTexts 18.5 ('Ts is 60 degF (519.67 degR)') | retrieved this session |
| Z at standard conditions, Zsc | `1 (assumed)` | dimensionless | Adewumi PNG 520 eq. (18.8) 'recalling that Zsc ~ 1'; IHS/Fekete 'The compressibility factor (Z) for standard conditions is assumed to be 1' | retrieved this session. The TRUE value for a typical natural gas at 14.696 psia / 60 degF is approximately 0.998 - that number is RECALLED, not retrieved |
| Bg coefficient, rcf/scf basis (= psc/Tsc) | `0.0282795 (textbook rounding 0.02827)` | psia/degR, giving ft^3(res)/scf when multiplied by Z*T/p | Derived from psc = 14.696, Tsc = 519.67 | computed this session to 6 sig figs; cross-checked that /5.615 gives 0.0050364 which matches the published 0.005035 |
| Bg coefficient, rb/scf basis (= psc/(Tsc*5.615)) | `0.0050364 (textbook rounding 0.005035)` | psia/degR/(ft^3/bbl), giving rb/scf when multiplied by Z*T/p | Adewumi PNG 520 eq. (18.8)/(18.9) | retrieved AND recomputed this session; they agree to 4 sig figs |
| Barrel to cubic feet conversion | `5.615` | ft^3/bbl | Adewumi PNG 520 ('1 RB = 5.615 RCF'); Pletcher SPE 75354 nomenclature (RB, Mscf) | retrieved this session. Exact definitional value is 42*231/1728 = 5.614583 ft^3/bbl - that arithmetic is mine, computed this session |
| Gas expansion factor coefficient Tsc/psc (Dake's form E = 35.37*p/(Z*T)) | `35.37 (exact reciprocal of 0.0282795 is 35.3613)` | degR/psia, giving scf/rcf | Dake, Exercise 1.2 solution, p. 34 | retrieved verbatim; reciprocal computed this session (0.02% discrepancy noted) |
| Standard pressure implied by Pletcher's two-cell simulation Bg table | `15.025` | psia (ABSOLUTE) | Back-computed from Pletcher SPE 75354 Table 3 (p, Z, Bg) with T = 239 degF | computed this session: Bg*p/(Z*T) = 0.0051492 bbl/scf is constant to +/-4e-5 across all 11 rows; *5.615*519.67 = 15.025 psia. This is a Texas-style standard base pressure - that ATTRIBUTION is RECALLED, not retrieved. The numerical value 15.025 is solid |
| Standard pressure implied by Pletcher's Oklahoma Morrow field Bg table | `14.699` | psia (ABSOLUTE) | Back-computed from Pletcher SPE 75354 Table 7 (p, Z, Bg) with T = 140 degF | computed this session: Bg*p/(Z*T)/1000 = 0.0050376 bbl/scf constant to +/-3e-7 across all 4 rows; *5.615*519.67 = 14.699 psia. NOTE: this is a DIFFERENT basis from Table 3 in the SAME paper |
| Absolute temperature offset | `459.67 (Dake uses 460)` | degR per degF | Standard; Dake writes 'degR = 460 + degF' (p. 12) | retrieved (Dake's rounded 460); the exact 459.67 is standard and RECALLED. The 0.33 degR difference is a 0.05% bias on Bg at 660 degR |
| Pletcher two-cell simulation model properties | `node area 640 acres; net pay 200 ft; porosity 15%; gas reservoir pore volume 74.5e6 res bbl; aquifer original water in place 74.5e6 res bbl; Sw 15%; OGIP 100.8 Bcf; permeability 100 md; cf 6e-6 1/psi; cw 3e-6 1/psi; reservoir temperature 239 degF` | as listed | Pletcher, SPE 75354, Table 1 | retrieved verbatim from full text this session |
| Oklahoma Morrow gas reservoir properties | `reservoir temperature 140 degF; cf = 3e-6 1/psi; cw = 3e-6 1/psi; Sw = 0.3` | as listed | Pletcher, SPE 75354, Table 7 footnote | retrieved verbatim from full text this session |
| Typical residual (trapped) gas saturation behind a waterflood front | `30 to 50` | % of pore volume | Dake, Fundamentals of Reservoir Engineering, p. 32 (citing his refs 7 and 17) | retrieved verbatim this session |
| Formation compressibility in shallow unconsolidated reservoirs (upper bound example) | `in excess of 100e-6` | 1/psi | Dake, p. 27, citing measurements in the Bolivar Coast fields, Venezuela | retrieved verbatim this session |
| Anderson 'L' gas reservoir initial pressure and OGIP (the classic Ramagost-Farshad geopressured example) | `NOT ESTABLISHED` | psia / Bscf | Ramagost & Farshad, SPE-10125-MS (1981) - abstract only retrieved via OSTI; the data table was not obtainable | UNVERIFIED - needs primary source. OSTI confirms the paper applied the method to three reservoirs: North Ossun Field (Louisiana), Anderson 'L' (South Texas) and an unnamed offshore Louisiana gas reservoir. Any pi, Z, Gp table you have seen quoted for Anderson 'L' must be re-sourced from SPE-10125 before use |

## Validity ranges

- p/Z straight line: only for a volumetric (closed) DRY gas reservoir where HCPV is constant. Dake's own sensitivity: with cw = 3e-6, cf = 10e-6, Swc = 0.2 and a 1000 psi drawdown, ignoring rock/water expansion changes the balance by 1.3%. At normal pressures and small dp this is genuinely negligible; at large dp or large cf it is not.
- Rock/water expansion term Efw: assumes cf and cw are CONSTANT over the pressure interval. Defensible for consolidated, normally-pressured rock (cf typically 3e-6 to 10e-6 1/psi). NOT defensible for geopressured reservoirs, where cf is pressure-dependent, nor for shallow unconsolidated rock where cf can exceed 100e-6 1/psi.
- Ramagost-Farshad correction: requires ce*(pi - p) < 1 (explicit in the IHS/Fekete documentation). Practically it degrades well before that: at ce = 2e-5 1/psi and dp = 6000 psi the factor is 0.88 and the correction is no longer a small perturbation.
- Bg from Bg = (psc/Tsc)(ZT/p): valid wherever a single-phase Z is valid. Below the dew point of a gas condensate the mole count changes and a single-phase Bg is wrong; a two-phase Z or a compositional treatment is required.
- Pot aquifer model (We = (cw+cf)*W*dp): only for a small, high-permeability, hydraulically isolated water leg where pressure equilibration is effectively instantaneous. Dake: aquifer of the same order of magnitude as the reservoir. Pletcher: US Gulf Coast high-permeability sands broken up by faulting. For a regional aquifer this model is wrong and We becomes time-dependent.
- Pot-aquifer plot: unusable in very early life. In Pletcher's simulation the early monthly points have a NEGATIVE slope and do not turn over toward the correct positive slope until roughly three-quarters of the way through year 1.
- Cole plot: the y-axis denominator is (Bg - Bgi), which approaches zero as p approaches pi. With Bg tabulated to 4 decimal places, year 1 of Pletcher's example gives Bg - Bgi = 0.0308, i.e. only ~3 significant figures survive. Early Cole points are numerically fragile and pressure-measurement error dominates.
- p/Z and all forms above assume no adsorbed gas. For coalbed methane or organic-rich shale, use King's p/Z* (or Fekete's p/Z**) which carries a desorption term, otherwise total gas in place is understated.
- Drive indices: sum to unity only if the material balance solution and We model are correct. The test is diagnostic only when the indices are reported RAW, never normalised.

## Failure modes

- THE HEADLINE FAILURE (item e): a weak-to-moderate water drive or a geopressured reservoir yields a p/Z (or even a cf-corrected p/Z) plot that is visually and statistically an excellent straight line, whose extrapolation OVERESTIMATES G. Pletcher's two-cell simulation: R2 = 0.9998 over ten years, yet the modified p/Z extrapolation is +8.2% high at 11% recovery, +6.5% at 27% recovery and still +4.0% after 54% of the OGIP has been produced. Using the UNCORRECTED p/Z on the same data, my recomputation gives +15.3% at 11% recovery. The aquifer here has pore volume equal to the gas reservoir - Pletcher calls it 'very small'.
- The water drive is undetectable from well performance in that case: after 10 years the well made only 1.5 STB water per MMscf gas, and in a real reservoir with saturation gradients it would likely make even less. A dry gas well is NOT evidence of a closed tank.
- Documented FIELD case (Oklahoma Morrow sand, Pletcher SPE 75354): 'The lack of water production, together with the decline in reservoir pressure, suggested that no aquifer was present. The p/z plot also gives no hint of aquifer support.' Modified p/Z gave G = 6.02 Bcf; conventional p/Z gave 6.32 Bcf; the pot-aquifer solution gave 5.44 Bcf. The p/Z extrapolation was 'nearly 11% too high, even after being modified to account for formation compressibility' - and 16% too high uncorrected. Cumulative influx was only 3% of the original HCPV yet supplied ~10% of the cumulative voidage.
- MECHANISM, water drive: the aquifer response is TIME-LAGGED (unsteady state). During the transient period the influx grows in a way that happens to hold p/Z up along a line of shallower slope than the true depletion line. Dake: 'initially, all the material balance plots appear to be linear and, if there is insufficient production and pressure history to show the deviation from linearity, one may be tempted to extrapolate the early trends, assuming a depletion type reservoir, which would result in the determination of too large a value of the GIIP.' A shallower slope with the same y-intercept pi/Zi moves the x-intercept G to the right.
- MECHANISM, geopressured: compaction and residual-fluid expansion supply extra energy early, so the p/Z trend is BOW-SHAPED with a shallow first slope; once gas expansion dominates a second, steeper slope appears. IHS/Fekete: 'When matching on the shallower slope of this bow-shaped trend, all later pressure data is lower than the analysis line, and the estimated original gas-in-place is higher than the true original gas-in-place.' Secondary sources state engineers applying conventional p/Z to abnormally pressured reservoirs can see errors up to 100% in G.
- A third mechanism that mimics both: an unaccounted-for connected reservoir depleting into the one being analysed. Pletcher notes a negative Cole slope 'can result from any unaccounted-for source of energy that is decreasing with time relative to gas expansion... for example, communication with other depleting reservoirs.'
- Correcting for cf does NOT protect you from an aquifer. Pletcher's headline result is precisely that a Ramagost-Farshad-corrected p/Z still overestimated by 4-8% because the energy actually came from a weak aquifer, not from compaction. Conversely, fitting the pot-aquifer plot assuming no aquifer gave cf = 14.3e-6 1/psi versus the known 6e-6 - the misattribution runs both ways.
- USING FLOWING BOTTOMHOLE PRESSURE (item f): pwf = p_avg - (drawdown + skin + non-Darcy term). The non-Darcy (turbulent) component in gas wells is strongly RATE dependent, so pwf is a function of the production rate, not of the gas inventory. Substituting it violates the zero-dimensional premise of the balance outright. Directionally (my derivation, not retrieved): a roughly constant drawdown shifts the whole p/Z line down without changing its slope, lowering the x-intercept and UNDERestimating G; a drawdown that grows with time steepens the line and underestimates further; wells choked back late in life flatten the line and can OVERestimate. Worst of all, the scatter is correlated with rate, so it looks like reservoir physics rather than like measurement error.
- Insufficiently long shut-ins: a buildup that has not reached the boundary-dominated plateau returns a pressure BELOW the true average, with the deficit varying by well and by shut-in duration. This produces exactly the same class of defect as using pwf, only smaller.
- Arithmetic (rather than pore-volume-weighted) averaging of well pressures: biases the average toward whichever wells happen to have most gauges, not toward the bulk of the pore volume.
- Not referring all pressures to one datum depth: in a tall gas column the gas gradient is small (Dake computes 0.0465 to 0.117 psi/ft) but over hundreds of feet it is tens of psi, comparable to the signal in early depletion.
- Trusting R2 as evidence of a volumetric reservoir. R2 = 0.9998 in a case that is 8% wrong. R2 measures how well points lie on A line, not whether that line's x-intercept is G. State this explicitly in any report the repository produces.
- Normalising drive indices so they sum to unity - this destroys the single best independent check that the solution is correct.
- Double-counting produced water by placing Wp*Bw in the withdrawal term F AND also subtracting it inside the influx term.

## Numerical pitfalls

- Gauge vs absolute pressure. p/Z has no meaning with gauge pressure; a 14.7 psi offset at 2638 psia is a 0.56% error in p/Z and shifts the extrapolated G.
- degF vs degR, and 460 vs 459.67. The latter is a 0.05% bias on Bg at typical reservoir temperature - small, but it will stop you reproducing published worked examples to 5 figures and will look like a bug.
- Catastrophic cancellation in (Bg - Bgi) on the Cole plot at early times. With Bg to 4 decimals, year 1 of Pletcher's case gives 0.0308 from two numbers near 0.63 - about 3 significant figures survive.
- Catastrophic cancellation in (pi - p) in the Ramagost-Farshad and Efw terms at very early times, for the same reason.
- scf vs Mscf vs MMscf vs Bscf; rcf/scf vs rb/scf vs rb/Mscf. Pletcher's G is in Mscf and Bg in RB/Mscf; Dake's G is in scf and E in scf/rcf. These are factor-1000 traps and they do not announce themselves - the answer just comes out 1000x wrong or, worse, only the slope is wrong.
- Ordinary least squares on p/Z vs Gp weights all points equally in p/Z units, so late-life low-pressure points (where p/Z is small but relatively less certain) get relatively little leverage on the slope while early high-pressure points dominate. This is precisely the regime where the water-drive bias is worst. Report the sensitivity to dropping the earliest points.
- Whether to include the (0, pi/Zi) point in the fit, and whether to force the line through it, materially changes G. Decide, document, and report both.
- The Ramagost-Farshad factor (1 - ce*(pi - p)) goes to zero and then negative at large drawdown. Assert, do not clamp.
- Zsc is taken as exactly 1; the true value is around 0.998 for typical natural gas. This is a ~0.2% systematic bias in Bg and hence in a volumetric G, in the SAME direction every time. It cancels out of the p/Z ratio, so it affects volumetric GIIP but not the p/Z-extrapolated G.
- 5.615 vs 5.614583 ft^3/bbl: a 7.4e-5 relative difference. Immaterial, but use one value everywhere so round-trip conversions are exact.
- Z-factor correlation choice (Standing-Katz chart reading vs Dranchuk-Abou-Kassem vs Hall-Yarborough vs an EOS) changes Z by a few tenths of a percent and therefore changes p/Z and Bg. Use ONE correlation for the whole history; switching mid-history injects a fake kink into the p/Z plot that will be mistaken for reservoir physics.
- Pletcher's Table 2 'Cumulative Water Influx' column header says STB while the discussion quotes res bbl (2,359,460 STB * Bw = 2,494,185 res bbl). Any table you ingest may carry the same ambiguity; verify by the Bw factor before use.
- Pletcher's eq. (16) text prints PV = 4.84 million res bbl but the subsequent ratio uses 4.48; 4.48 is the arithmetically correct value (5,440,000 Mscf * 0.5770 RB/Mscf / 0.7). Published papers contain typos - recompute before trusting a printed intermediate.
- The published PNG 520 / LibreTexts pages print Bg = 0.005035*Z*T/p labelled [RCF/SCF] for BOTH the rcf and the rb form; the rcf coefficient should be 0.02827. Do not copy a coefficient without checking it against psc/Tsc yourself.

## Implementation notes

- Make (psc, Tsc, Zsc) explicit REQUIRED arguments of the Bg routine, not module constants. Default them to 14.696 psia / 519.67 degR / 1.0 but record the values used in the result object, and print them on every plot and report. The Pletcher paper alone contains two different bases (15.025 and 14.699 psia) two tables apart - a 2.2% Bg difference. This is the single most likely silent defect in a from-scratch implementation.
- Represent Bg internally in one canonical unit (suggest rb/scf) and convert at the boundaries. Pletcher tabulates RB/Mscf and G in Mscf; Dake works in rcf/scf and scf. The factor-1000 confusion between scf and Mscf is the second most likely silent defect.
- Take absolute pressure and absolute temperature as the only accepted inputs. Reject gauge pressure and degF at the API boundary rather than converting silently. Expose the degR offset (459.67) as a named constant so Dake's 460 can be selected when reproducing his worked numbers to 5 figures.
- Implement the p/Z fit as an ordinary least-squares of p/Z on Gp and report G = -intercept/slope, plus R2, plus the standard error of the x-intercept. Also report the fit WITHOUT the Gp = 0 point and the fit CONSTRAINED to pass through the measured (0, pi/Zi). These three give materially different G and the difference is informative. My reproduction of Pletcher's published values used the unconstrained fit INCLUDING the Gp = 0 point.
- Always compute and return the drive indices IGD, ICD, IWD un-normalised alongside any G. Refuse to normalise them. Flag any solution whose index sum shows a monotone trend across the history - that is Pletcher's explicit test for a wrong material-balance solution and it catches the water-drive counterexample.
- Implement the Cole plot and the modified Cole plot (F/Et) as first-class diagnostics, not options. Pletcher's central practical finding is that 'the p/z plot is completely ambiguous' where the Cole plot 'indicates unambiguously that a weak waterdrive exists'. Expect a NEGATIVE Cole slope for a weak aquifer, positive for strong, hump-shaped for moderate, horizontal for depletion. Do not offer extrapolation of a sloping Cole line to the y-intercept as an OGIP estimator - Pletcher explicitly recommends against it; use the latest point as an UPPER BOUND on G.
- Implement the pot-aquifer plot (F/Eg vs (pi-p)/Eg) as the recommended estimator when the Cole plot shows a weak drive. Provide the option to drop early points from the least-squares fit; Pletcher's published values require excluding year 1 for the 5- and 10-year analyses (Table 6 footnote marks year 1 'Excluded from least-square fit').
- Provide the Ramagost-Farshad corrected p/Z as a separate function and assert ce*(pi - p) < 1 at every point, raising rather than silently returning a negative plotting term.
- Sign conventions: pick ONE arrangement (recommend Pletcher's, F = Gp*Bg + Wp*Bw = G(Eg + Efw) + We with F and We in reservoir barrels) and document that We in that convention is a RESERVOIR volume. If the input We is in STB (as in Pletcher's own Table 2), multiply by Bw at ingest. Put an assertion in the We ingest path that names the expected unit.
- Guard the Cole-plot denominator (Bg - Bgi). Return NaN with an explicit reason, not a huge number, when (Bg - Bgi)/Bgi falls below a threshold (suggest 5%). Also propagate the input precision: with Bg given to 4 decimals, the year-1 Cole point carries only ~3 significant figures.
- Build the deliberate counterexample from Pletcher's Table 1/2/3 verbatim. It is ideal: published, fully tabulated, the true OGIP (100.8 Bcf) is exactly known because it is a simulation, and every published derived quantity (109.0/107.3/104.8 Bcf, R2 = 0.9998, Cole 107.2, modified Cole 104.4, pot aquifer 105.3/101.6/101.0, slope 1103 RB/psi, W = 69.1e6, We = 2.346e6 res bbl) was reproduced this session to 3-4 significant figures. Ship it as a golden-file test, and ship the Morrow case as the field counterpart.
- For item (f), average reservoir pressure: the material balance is ZERO-DIMENSIONAL (Dake), so it requires a single pore-volume-weighted average pressure referred to a fixed datum. Accept only (i) a static/build-up-derived pressure that has reached the boundary-dominated plateau, or (ii) an MBH/Dietz/Horner-extrapolated p* corrected to p_avg. Dake: the final build-up pressure 'is the average pressure within the bounded volume being drained and is consistent with the material balance for that volume'. Since a well cannot practically be shut in long enough, p* is obtained by extrapolating the early Horner straight line to ln((t+dt)/dt) = 0 and then corrected via the MBH charts - Dake is explicit that 'apart from this special case p* cannot be thought of as having any clearly defined physical meaning but is merely a mathematical device used in calculating the average reservoir pressure'.
- Multi-well averaging must be HYDROCARBON-PORE-VOLUME weighted across drainage regions, not arithmetic. For a gas reservoir Dake recommends evaluating the pressure at the CENTROID depth - 'the depth at which there is as much gas above as there is beneath' - and states 'the pressures for use in the material balance equation will always be evaluated at this depth'. Store the datum depth with every pressure record and apply the gas gradient (Dake computes 0.0465 psi/ft for a light gas and 0.117 psi/ft at 4309 psia) to refer everything to it.
- Make flowing bottomhole pressure structurally impossible to pass into the material balance: give pressure records a typed tag (STATIC_EXTRAPOLATED, BUILDUP_PLATEAU, FLOWING) and have the balance reject FLOWING with a message rather than a warning. Record the shut-in duration alongside each static pressure so short shut-ins can be down-weighted or flagged.
- Report every OGIP estimate with the fraction of OGIP already produced at which it was made. Pletcher's error series (8.2% at 11% recovered, 6.5% at 27%, 4.0% at 54%) is the honest way to communicate that a p/Z-derived G is a lower-confidence number early in life, and that the error decays slowly.
- Do not let R2 appear anywhere near a G estimate without an accompanying statement that high R2 is compatible with an 8% error. Consider returning a named 'linearity_is_not_evidence_of_volumetric_drive' note on any p/Z result.

## Open uncertainties

- The ORIGINAL Ramagost & Farshad (1981) SPE-10125 paper was NOT retrieved - only the OSTI abstract. The equation form (p/Z)[1 - ce*(pi - p)] = (pi/Zi)(1 - Gp/G) with ce = (cw*Swi + cf)/(1 - Swi) is reconstructed from secondary descriptions. It IS strongly supported numerically: with that exact form I reproduced Pletcher's published 'modified p/z' OGIP values (109.0, 107.3, 104.8 Bcf) and his R2 = 0.9998 exactly. But the printed equation itself remains unconfirmed against the primary source.
- The Anderson 'L' gas reservoir data table (the classic geopressured worked example) was NOT obtained. OSTI confirms only that Ramagost & Farshad applied their method to North Ossun Field (Louisiana), the Anderson 'L' (South Texas) and an unnamed offshore Louisiana reservoir. I have no verified pi, Z, Gp values, and none should be written into the repository until SPE-10125 is obtained. Marked UNVERIFIED in the constants list.
- The '226% overestimation with R2 = 0.992 at 50% recovery' figure comes from a web-search result summary of a 2023 Springer paper that I could not fetch (303 redirect to an auth endpoint). Treat as unverified. The verified quantitative claims in this card are Pletcher's +8.2%/+6.5%/+4.0% (simulation) and ~+11%/+16% (Oklahoma Morrow field).
- The attribution of psc = 15.025 psia to a Texas Railroad Commission standard base is RECALLED, not retrieved. The NUMBER 15.025 psia is solid - it is back-computed from Pletcher's Table 3 and is constant to 1.5e-4 relative across all eleven rows. The regulatory attribution should be checked before it is written into documentation.
- Zsc ~ 0.998 for a typical natural gas at 14.696 psia / 60 degF is RECALLED, not retrieved. The direction (Zsc < 1, so assuming Zsc = 1 slightly understates Bg) is certain; the magnitude should be confirmed against a Z correlation before being quoted.
- The directional analysis of what substituting flowing bottomhole pressure does to the fitted G (constant drawdown lowers the intercept and underestimates G; increasing drawdown steepens the line; late-life choking flattens it and can overestimate) is MY DERIVATION from the geometry of the fit, not a retrieved statement. The retrieved part is only that drawdown is 'the difference between the average reservoir and bottom hole flowing pressures' (Dake, p. 28) and that the balance is zero-dimensional and requires a volume-averaged pressure (Dake, p. 75).
- The full symbol definitions for Fekete's Z** (specifically cwip and cd) were not retrieved; the equation image was read but the accompanying nomenclature was not. The underlying primary reference (Moghadam, Jeje & Mattar, JCPT 50(1), 2011) was not retrieved either. Treat the p/Z** block as secondary and incomplete.
- Bruns, Fetkovich & Meitzen, 'The Effect of Water Influx on p/z-Cumulative Gas Production Curves', JPT 17(3), 1965, p. 287 - the primary reference for the apparent-GIIP method - was NOT retrieved (OnePetro returned 403). What I have is Dake's rendering of their method (eqs. 1.42-1.44), retrieved in full.
- SPE-103258-MS, 'A Straight Line p/z Plot is Possible in Waterdrive Gas Reservoirs' (SPE Rocky Mountain, 2007) was not retrieved beyond a search summary. It appears to be the most on-point primary reference for item (e)'s mechanism (that specific production rate schedules combined with unsteady-state aquifer behaviour can produce genuine linearity) and is worth obtaining.
- My reproduced error percentages for Pletcher's modified p/Z are 8.2% / 6.4% / 3.9% against his published 8.2% / 6.5% / 4.0%. The 0.1 pp differences are rounding in the intermediate G values, not a methodological disagreement - his G values 109.0 / 107.3 / 104.8 match mine to the decimal place he printed.
- My Oklahoma Morrow pot-aquifer fit gives G = 5.457 Bcf with R2 = 0.9275 against his published 5.44 Bcf with R2 = 0.934. The small difference is probably whether the day-0 point was included or exactly how the Bg column was generated. Use his published 5.44 Bcf as the regression target with a 0.05 Bcf tolerance, not a tighter one.
- Everything about gas CONDENSATE material balance (two-phase Z, the change in moles below the dew point, the Vo/Vt correction) is outside what I verified here. The dry-gas assumption is load-bearing throughout and should be an explicit precondition in the code.

## Independent check values

| Check | Inputs | Expected | Source | Retrieved or recalled |
|---|---|---|---|---|
| REGRESSION TEST 1 (textbook, volumetric depletion, end-to-end). Dake Exercise 1.2: from bulk volume to GIIP via the centroid pressure, then cumulative production at an abandonment pressure via the p/Z line. | `Net bulk volume V = 1.776e10 cu.ft; phi = 0.19; Swc = 0.20; gas gravity 0.85; GWC at 9700 ft; centroid depth 9537 ft; water gradient pw = 0.441*D + 31 psia; temperature gradient 1.258 degF/100 ft with 80 degF surface ambient. Given in the solution: Z at GWC = 0.888, Z at centroid = 0.887, Z at 1200 psia = 0.832. Use E = 35.37*p/(Z*T) scf/rcf.` | `pw at GWC = 4309 psia; T at GWC = 662 degR; E_GWC = 259.3 scf/rcf; gas gradient = 0.117 psi/ft; centroid pressure p = 4290 psia; centroid T = 660 degR; Ei = 259.19 scf/rcf; GIIP G = 699.70e9 scf. Then at p = 1200 psia, Z = 0.832: Gp = 491.04e9 scf.` | Dake, L.P., Fundamentals of Reservoir Engineering, Developments in Petroleum Science 8, Elsevier - Exercise 1.2 and its solution, pp. 33-35 | RETRIEVED full text this session AND independently recomputed: HCPV = 2.6995e9 rcf, Ei = 259.1939, G = 6.9970e11 scf (exact match), (1200/0.832)/(4290/0.887) = 0.298211, Gp = 4.91041e11 scf (exact match) |
| REGRESSION TEST 2 - THE COUNTEREXAMPLE (item e). Pletcher's two-cell Eclipse simulation: a gas tank cell plus an equal-pore-volume 100%-water cell (a pot aquifer). True OGIP is known exactly. Fit the Ramagost-Farshad-corrected p/Z at three points in the history and confirm the overestimate despite near-perfect linearity. | `Table 1: OGIP 100.8 Bcf, cf = 6e-6 1/psi, cw = 3e-6 1/psi, Sw = 0.15, T = 239 degF, aquifer OWIP W = 74.5e6 res bbl. Table 2 (years 0-10): p [psia] = 6411, 5947, 5509, 5093, 4697, 4319, 3957, 3610, 3276, 2953, 2638; Gp [Bscf] = 0, 5.475, 10.950, 16.425, 21.900, 27.375, 32.850, 38.325, 43.800, 49.275, 54.750; Wp [STB] = 0, 378, 1434, 3056, 5284, 8183, 11864, 16425, 22019, 28860, 37256; We [STB] = 0, 273294, 552946, 817481, 1068632, 1307702, 1535212, 1752942, 1962268, 2163712, 2359460. Table 3: Z = 1.1192, 1.0890, 1.0618, 1.0374, 1.0156, 0.9966, 0.9801, 0.9663, 0.9551, 0.9467, 0.9409; Bg [RB/Mscf] = 0.6279, 0.6587, 0.6933, 0.7327, 0.7778, 0.8300, 0.8910, 0.9628, 1.0487, 1.1532, 1.2829; Bw [RB/STB] = 1.0452, 1.0467, 1.0480, 1.0493, 1.0506, 1.0517, 1.0529, 1.0540, 1.0551, 1.0560, 1.0571. Use ce = (cw*Swi + cf)/(1-Swi) = 5.2941e-6 1/psi.` | `Modified p/Z least-squares x-intercept including the Gp=0 point: after 2 years (11% recovered) G = 109.0 Bcf (+8.2%); after 5 years (27%) G = 107.3 Bcf (+6.5%); after 10 years (54%) G = 104.8 Bcf (+4.0%). R2 of the 10-year modified p/Z fit = 0.9998. Cole plot y-value at year 10 = ~107 Bcf; modified Cole plot at year 10 = 104.4 Bcf. Pot-aquifer plot: G = 105.3 (+4.5%), 101.6 (+0.8%), 101.0 (+0.2%) Bcf, excluding year 1 from the 5- and 10-year fits; slope after 10 years = 1103 RB/psi; W from eq. 14 = 69.1e6 res bbl (7% low vs the true 74.5e6); We at 10 years from eq. 12 = 2,346,000 res bbl (~6% less than the simulator's 2,494,000 res bbl).` | Pletcher, J.L.: 'Improvements to Reservoir Material-Balance Methods', SPE Reservoir Evaluation & Engineering, Feb 2002, pp. 49-59 (SPE 75354, revised from SPE 62882) - Tables 1, 2, 3, 4, Figs. 2, 3, 4 | RETRIEVED full text this session (open PDF on blasingame.engr.tamu.edu) AND fully recomputed. My independent results: modified p/Z 109.0 / 107.3 / 104.8 Bcf with errors 8.2% / 6.4% / 3.9%; R2 = 0.999788 over 10 years; Cole year-10 = 107.23 Bcf; modified Cole year-10 = 104.43 Bcf; pot aquifer 105.27 / 101.58 / 100.99 Bcf, slope 1103 RB/psi, W = 6.90e7 res bbl, We(10yr) = 2,344,383 res bbl. Every published number reproduced. NOTE: Table 2's We column is in STB; 2,359,460 STB * Bw 1.0571 = 2,494,185 res bbl, which is exactly the 2,494,000 res bbl quoted in the text - this confirms the unit convention |
| REGRESSION TEST 2b (the same data, uncorrected). Fit the RAW p/Z (no Ramagost-Farshad factor) to show the compounded error - this is the form most practitioners actually plot. | `Same Pletcher Table 2/3 data; plot p/Z vs Gp with no cf correction.` | `G = 116.2 Bcf after 2 years (+15.3%), 112.7 Bcf after 5 years (+11.8%), 107.9 Bcf after 10 years (+7.1%); R2 = 0.99997 / 0.99976 / 0.99933.` | Derived by me from Pletcher's published Tables 2 and 3 | COMPUTED this session from retrieved data. These specific uncorrected values are NOT printed in the paper - they are my extension, and should be labelled as such in the repository |
| REGRESSION TEST 3 - REAL FIELD CASE (item e, field evidence). Oklahoma Morrow sand gas reservoir with only 4 pressure points and no water production, where the p/Z plot gives 'no hint of aquifer support'. | `T = 140 degF; cf = 3e-6 1/psi; cw = 3e-6 1/psi; Sw = 0.3. Days = 0, 72, 237, 332; p [psia] = 5482, 5099, 3818, 3016; Z = 1.0471, 0.9960, 0.8286, 0.7341; Bg [RB/Mscf] = 0.5770, 0.5901, 0.6556, 0.7353; Gp [Mscf] = 0, 157000, 814000, 1350000; p/Z [psia] = 5235, 5119, 4608, 4108.` | `Conventional p/Z extrapolation G = 6.32 Bcf; modified (cf-corrected) p/Z G = 6.02 Bcf; pot-aquifer plot G = 5.44 Bcf with R2 = 0.934 and slope 58 RB/psi, giving W = 6.74e6 res bbl and cf (from eq. 15, assuming no aquifer) = 12e-6 1/psi versus the estimated 3e-6. Original PV = G*Bgi/(1-Swi) = 4.48e6 res bbl, so the aquifer is 1.5x the gas reservoir. We at 332 days = 99,800 res bbl = ~3% of the original HCPV but ~10% of the cumulative voidage (Gp*Bg = 992,700 res bbl). The p/Z extrapolation is 'nearly 11% too high, even after being modified to account for formation compressibility'.` | Pletcher, SPE 75354, Table 7, Figs. 5, 6, 7 and surrounding text, p. 53-54 | RETRIEVED full text this session AND recomputed. My results: conventional p/Z G = 6.325 Bcf (R2 = 0.9978); modified p/Z G = 6.017 Bcf (R2 = 0.9986); pot aquifer G = 5.457 Bcf, slope 57.0 RB/psi, R2 = 0.9275, W = 6.58e6 res bbl, cf from eq.15 = 11.8e-6 1/psi, We(332d) = 97,331 res bbl, PV = 4.48e6 res bbl. All within rounding of the published values. CAUTION: the paper's eq. (16) text prints '4.84 million res bbl' but then divides 6.74/4.48 = 1.5 - 4.48 is correct and 4.84 is a typo in the paper |
| CHECK 4 - Bg standard-condition sensitivity (item a). Demonstrate that psc/Tsc is a declared basis, not a constant, by back-solving it from two tables in the SAME paper. | `Pletcher Table 3 (T = 239 degF) and Table 7 (T = 140 degF): compute Bg*p/(Z*T) for every row.` | `Table 3 gives 0.0051492 bbl/scf constant across all 11 rows, implying psc = 15.025 psia at Tsc = 519.67 degR. Table 7 gives 0.0050376 bbl/scf constant across all 4 rows, implying psc = 14.699 psia. The two bases differ by 2.2% in Bg.` | Back-computation by me from Pletcher SPE 75354 Tables 3 and 7 | COMPUTED this session from retrieved tables. Table 3 rows: coeff*T = 3.59674 to 3.59727 (spread 1.5e-4 relative). Table 7 rows: 0.0050375, 0.0050378, 0.0050375, 0.0050377. The 15.025 psia figure is a real Texas-style standard base - that attribution is RECALLED, not retrieved, but the numerical value is solid |
| CHECK 5 - Bg unit-conversion identity. | `psc = 14.696 psia, Tsc = 519.67 degR, 5.615 ft^3/bbl.` | `psc/Tsc = 0.0282795 rcf/scf; divided by 5.615 = 0.0050364 rb/scf; times 1000 = 5.0364 rb/Mscf; reciprocal of 0.0282795 = 35.3613 scf/rcf (Dake's 35.37).` | Adewumi PNG 520 eqs. (18.8)-(18.9); Dake Exercise 1.2 | Published coefficients RETRIEVED; the arithmetic recomputed this session and agrees to 4 sig figs |
| CHECK 6 - Z-factor pseudo-critical mixing rule (needed before any p/Z work). Dake's worked Standing-Katz example. | `The 15-component composition of Dake Table 1.1 (mole fractions summing to 1.0000), with the component pc and Tc values listed there; evaluate at p = 2000 psia and T = 180 degF (Dake uses 640 degR, i.e. 180+460).` | `ppc = 663.3 psia; Tpc = 374.1 degR; ppr = 3.02; Tpr = 1.71; Z = 0.865 from the Standing-Katz chart (Dake Fig. 1.6).` | Dake, Fundamentals of Reservoir Engineering, Table 1.1 and pp. 15-16 | RETRIEVED full text this session AND recomputed: mole fractions sum to exactly 1.0, ppc = 663.29, Tpc = 374.13, ppr = 3.0153, Tpr = 1.7106. Exact match. The Z = 0.865 was read off a chart by Dake and is NOT machine-verifiable |
| CHECK 7 - Dake's magnitude check on the rock/connate-water term (item d sanity test). | `cw = 3e-6 1/psi, cf = 10e-6 1/psi, Swc = 0.2, dp = 1000 psi.` | `(cw*Swc + cf)*dp/(1 - Swc) = (3*0.2 + 10)*1e-6*1000/0.8 = 0.0132, i.e. 'only alters the material balance by 1.3%'.` | Dake, Fundamentals of Reservoir Engineering, p. 27 | RETRIEVED verbatim this session; arithmetic trivially confirmed (10.6e-6*1000/0.8 = 0.01325) |
| CHECK 8 - drive-index closure on the Pletcher two-cell case (correctness detector). | `Pletcher Tables 2 and 3, with G from the pot-aquifer solution (101.0 Bcf) versus G from the modified p/Z solution (104.8 Bcf).` | `With the pot-aquifer G, IGD + ICD + IWD = 1.000 to 1.005 in every year (Table 6). With the modified p/Z G (which ignores the aquifer), the sum runs 0.959 at year 1 and climbs monotonically to 1.004 at year 10 - a consistent INCREASING trend that flags the solution as wrong.` | Pletcher, SPE 75354, Tables 5 and 6 | Tables RETRIEVED verbatim this session; I did not recompute the individual index values (only the OGIP and We values were recomputed) |
| CROSS-CHECK (weaker evidence) - a larger documented overestimation in the recent literature. | `A water-drive gas reservoir case at 50% recovery factor.` | `The p_avg/Z plot gives a straight line with R2 = 0.992 but G = 375 Bscf, described as a 226% overestimation of the true OGIP.` | Reported for 'A novel material-balance approach for estimating in-place volumes of gas and water in gas reservoirs with aquifer support', J. Petroleum Exploration and Production Technology (2023), DOI 10.1007/s13202-023-01630-5 | NOT RETRIEVED - Springer blocked the fetch (303 to an auth endpoint). These numbers come from a web-search result summary only. Do NOT use as a regression test or cite as verified; re-source the paper before quoting the 226% figure |

## Adversarial review

### Corrections

**Regression Test 2 inputs: "Use ce = (cw*Swi + cf)/(1 - Swi) = 5.2941e-6 1/psi"** — severity critical, confidence certain

- Claimed: ce = 5.2941e-6 1/psi for the Pletcher two-cell case (cw=3e-6, cf=6e-6, Swi=0.15)
- Correct: ce = 7.5882e-6 1/psi. (3e-6*0.15 + 6e-6)/(1-0.15) = 6.45e-6/0.85 = 7.588235e-6. The stated formula is right; the number printed next to it is wrong and is what an implementer will hard-code.
- Evidence: Two independent confirmations. (1) Direct arithmetic. (2) Reproduction of the paper: with ce=7.5882e-6 the Ramagost-Farshad-corrected p/Z least-squares x-intercept on Pletcher Tables 2+3 gives 109.026 / 107.294 / 104.770 Bcf at years 2/5/10 with R2 = 0.999994 / 0.999931 / 0.999788 — matching SPE 75354 Table 4 (109.0 / 107.3 / 104.8) and the published R2 = 0.9998. With the card's 5.2941e-6 the same fits give 111.10 / 108.86 / 105.71 Bcf — every published target missed. The card's own downstream numbers also require 7.5882e-6: Eq. 14 with slope A = 1103 RB/psi, G = 101.0e6 Mscf, Bgi = 0.6279 gives W = (1103 - 63.42e6*7.5882e-6)/9e-6 = 6.91e7 res bbl = the paper's 69.1 million res bbl; with 5.2941e-6 it gives 8.53e7. SPE 75354 full text retrieved and text-extracted this session (blasingame.engr.tamu.edu PDF): Table 1 confirms cf = 6e-6, cw = 3e-6, Sw = 15%; Table 4 confirms 109.0/107.3/104.8; body text confirms "slope ... after 10 years is 1,103 RB/psi, giving a calculated W of 69.1 million res bbl".

**Equation block "Roach plot and modified Roach plot", Eq. 17** — severity high, confidence certain

- Claimed: ... - [ (We - Wp*Bw)/((pi - p)*G*Bgi) - (Swi*cw + cf)/(1 - Swi) ]  (i.e. the compressibility group enters the intercept with a + sign)
- Correct: ... - [ (Swi*cw + cf)/(1 - Swi) + (We - Wp*Bw)/((pi - p)*G*Bgi) ]  — both terms inside the bracket are ADDED, and the whole bracket is subtracted. The y-intercept is negative of the sum, not a difference.
- Evidence: Verbatim from SPE 75354 (text extracted from the retrieved PDF this session): Eq. 17 reads "[(p/z)i/(p/z) - 1]/(pi - p) = (1/G)[(p/z)i/(p/z)*Gp/(pi - p)] - [(Swi*cw + cf)/(1 - Swi) + (We - Wp*Bw)/((pi - p)*G*Bgi)]". Independently re-derived from Pletcher Eqs. 1-4: dividing F = G(Eg + Efw) + We by G*Bgi and using Bg/Bgi = (p/z)i/(p/z) yields [(p/z)i/(p/z) - 1]/dp = (1/G)[Gp*(p/z)i/(p/z) + Wp*Bw/Bgi]/dp - ce - We/(G*Bgi*dp). Sign of ce is unambiguously negative.

**Equation block "Roach plot and modified Roach plot", Eq. 18 (modified Roach)** — severity high, confidence certain

- Claimed: ...  + [ (cw + cf)*W/(G*Bgi) - (Swi*cw + cf)/(1 - Swi) ]
- Correct: ...  - [ (Swi*cw + cf)/(1 - Swi) + (cw + cf)*W/(G*Bgi) ]. Both the aquifer term and the compressibility term are negative. The card's Eq. 17 and Eq. 18 are also mutually inconsistent: substituting We = (cw+cf)*W*dp into the card's own Eq. 17 produces the exact opposite signs to its Eq. 18.
- Evidence: Verbatim from the retrieved SPE 75354 text: Eq. 18 = "(1/G)[((p/z)i/(p/z)*Gp + Wp*Bw/Bgi)/(pi - p)] - [(Swi*cw + cf)/(1 - Swi) + (cw + cf)*W/(G*Bgi)]". Numerical proof on synthetic data constructed to satisfy the MBE exactly (G = 100.0 Bcf, Bgi = 0.6279, cw = 3e-6, cf = 6e-6, Swi = 0.15, W = 74.5e6, arbitrary pressure path and Wp): fitted intercept = -1.82667e-5, which equals -(ce + (cw+cf)W/(G*Bgi)) = -(7.5882e-6 + 1.06785e-5) to 13 significant figures. The card's expression evaluates to +3.090e-6. The same synthetic test also shows the card's Eq. 17 x-axis (which omits Wp*Bw/Bgi) recovers 1/slope = 99.70 Bcf instead of the true 100.00 Bcf when water production is non-trivial — that omission is correct for Eq. 17 as published, but the implementer must use Eq. 18's x-axis to get G exactly.

**Constants: "Bg coefficient, rcf/scf basis", "Bg coefficient, rb/scf basis", "Gas expansion factor coefficient Tsc/psc"** — severity medium, confidence certain

- Claimed: 0.02827 is psc/Tsc (14.696/519.67) rounded to 4 sig figs; 14.696/519.67/5.615 = 0.0050364 "reproduces the textbook 0.005035"; "Dake's 35.37 is 1/0.0282795 = 35.3613 rounded up"
- Correct: The published trio 0.02827 / 0.005035 / 35.37 all come from psc = 14.7 psia and Tsc = 520 degR (i.e. 60 degF with Dake's 460 offset), NOT from 14.696/519.67. Computed this session: 14.7/520 = 0.0282692 -> 0.02827; /5.615 = 0.0050346 -> 0.005035; 520/14.7 = 35.3741 -> 35.37. Whereas 14.696/519.67 = 0.0282795 -> 0.02828; /5.615 = 0.0050364 -> 0.005036; reciprocal 35.3613 -> 35.36 (35.3613 does not round to 35.37 in any convention). For completeness, Craft & Hawkins' 0.02829 = 14.7/519.67 = 0.0282872.
- Evidence: Pure arithmetic, computed this session and tabulated across five (psc,Tsc) pairs. The card's own claim that its number 'matches the published 0.005035 to 4 sig figs' is false: 0.0050364 rounds to 0.005036. This is not cosmetic — it is the card's central thesis (that these coefficients are a declared basis, not constants) applied incorrectly to its own examples, and it means the three most-quoted textbook coefficients are silently attributed to the wrong basis.

**Independent check REGRESSION TEST 1 (Dake Exercise 1.2) vs implementation_notes default (psc=14.696, Tsc=519.67)** — severity medium, confidence certain

- Claimed: G = 699.70e9 scf at 5-significant-figure tolerance, while the implementation notes recommend defaulting the Bg/E routine to psc = 14.696 psia, Tsc = 519.67 degR
- Correct: The two are incompatible. HCPV = 1.776e10*0.19*0.80 = 2.69952e9 rcf. With E = 35.37 (= 520/14.7): Ei = 259.1939, G = 6.99699e11 — matches. With the card's own default basis (E = 519.67/14.696 = 35.3613): Ei = 259.1303, G = 6.99527e11 — fails at the 4th significant figure. The test must pin the Dake basis (psc = 14.7, Tsc = degF + 460) explicitly, or relax the tolerance to 3 sig figs.
- Evidence: Computed this session. Note Dake's own Exercise 1.2 intermediates independently confirm the 460 offset: T at 9700 ft = 80 + 1.258*97 = 202.03 degF -> 662.03 degR, matching the card's stated 662 degR only with +460 (with +459.67 it is 661.70).

**Constants: "Standard pressure implied by Pletcher's two-cell simulation Bg table" = 15.025 psia, "Texas-style base"** — severity medium, confidence high

- Claimed: 15.025 psia, attributed (twice, affirmatively) to a Texas-style standard base pressure; "the numerical value 15.025 is solid"
- Correct: The regulatory attribution is wrong. The Texas Railroad Commission base is 14.65 psia at 60 degF; 15.025 psia at 60 degF is the Louisiana (and Mississippi) statutory base. Separately, the back-solve does not support 5 significant figures: Bg*p/(Z*T) over Pletcher Table 3 gives psc = 15.0228 psia with the 459.67 offset and 15.0157 psia with the 460 offset, with a 1.5e-4 relative spread across rows from the 4-decimal Bg column. The defensible statement is "psc ~ 15.02 psia, consistent with the 15.025 psia Louisiana/Mississippi base".
- Evidence: Web search of state gas-measurement bases this session (Texas RRC Form G-10 instructions / 16 TAC 3.79; industry measurement references): "14.65 psia for Texas and Oklahoma, and 15.025 psia for Louisiana and Mississippi". Back-solve recomputed this session on the retrieved Table 3. Note the paper itself places the pot-aquifer archetype in the U.S. Gulf Coast, which is consistent with a Louisiana base.

**Pot aquifer equation block, Eq. 16** — severity medium, confidence certain

- Claimed: "Original hydrocarbon pore volume:  PV = G*Bgi / (1 - Swi)"
- Correct: G*Bgi/(1 - Swi) is the TOTAL pore volume, not the hydrocarbon pore volume. HCPV = G*Bgi. For the Morrow case: HCPV = 5.44e6 Mscf * 0.5770 RB/Mscf = 3,139,000 res bbl; total PV = 3,139,000/0.7 = 4,484,000 res bbl. Pletcher's wording is "the original pore volume of the hydrocarbon reservoir".
- Evidence: Retrieved SPE 75354 text uses HCPV = 3,139,000 res bbl and PV = 4.48e6 res bbl as distinct quantities ("only 3% of the original hydrocarbon pore volume (HCPV) of approximately 3,139,000 res bbl"). The card's own Efw derivation states the relation correctly ("total pore volume Vf = HCPV/(1 - Swi)"), so this is an internal contradiction. Consequence if implemented as labelled: HCPV overstated by 1/(1-Swi) = 1.43x, and the card's own "We = ~3% of HCPV" statistic becomes 2.2%.

**Constants: "Z at standard conditions, Zsc" and the associated ~0.2% bias claim** — severity low, confidence high

- Claimed: Zsc ~ 0.998 for typical natural gas at 14.696 psia / 60 degF, giving a ~0.2% systematic bias in Bg (flagged RECALLED)
- Correct: ~0.997, i.e. a ~0.3% bias. Independent computation with Dranchuk-Abou-Kassem plus Standing pseudo-criticals gives Zsc = 0.99759 (gamma 0.60), 0.99724 (0.65), 0.99686 (0.70), 0.99549 (0.85). The direction stated in the card (Zsc < 1, so Zsc = 1 understates Bg) is correct.
- Evidence: DAK implemented and run this session at ppr = 14.696/ppc, Tpr = 519.67/Tpc. Low severity, but the card should stop calling this 'recalled' now that an independent correlation supplies it — and should state 0.997/0.3%.

**Independent check CHECK 7 (Dake rock/connate-water magnitude check)** — severity low, confidence certain

- Claimed: "(cw*Swc + cf)*dp/(1 - Swc) = 0.0132 ... tolerance: exact to 3 decimals"
- Correct: 0.01325. To 3 decimals that is 0.013, not 0.0132. Either quote 0.01325 (4 decimals) or state the tolerance as 0.013 +/- 0.0005. Trivial, but the card presents it as an exact-to-3-decimals oracle, so as written the test contradicts its own tolerance.
- Evidence: (3e-6*0.2 + 10e-6)*1000/0.8 = 10.6e-6*1000/0.8 = 0.01325, computed this session. The card's own note in the same entry says 0.01325.

### Left unverified

- Everything sourced to Dake, Fundamentals of Reservoir Engineering. The PDF was NOT retrieved this session (only the Pletcher paper was). Unverified against primary text: R = 10.732 at eq. (1.13); the 35.37 value and Exercise 1.2 data/solution on pp. 33-35; eqs. (1.26), (1.33)-(1.35), (1.36)-(1.39), (1.40)-(1.41), (1.42)-(1.44); Table 1.1 composition and the ppc = 663.3 / Tpc = 374.1 / Z = 0.865 Standing-Katz reading; the 1.3% sensitivity on p. 27; residual gas saturation 30-50%; cf > 100e-6 in the Bolivar Coast; the 0.0465-0.117 psi/ft gradients; the p* / MBH quotations. The Exercise 1.2 arithmetic is internally self-consistent and one number in it (0.117 psi/ft from rho = p*M/(Z*R*T) = 0.1168) is independently reproducible, which supports but does not confirm the transcription.
- The claim that "Dake writes degR = 460 + degF". Strongly implied by the coefficient forensics (0.02827 and 35.37 both require Tsc = 520) and by Exercise 1.2's 662 degR, but not read from the book this session.
- Ramagost & Farshad, SPE 10125 (1981). Still only abstract-level. IMPORTANT UPGRADE though: the equation FORM is no longer merely 'reconstructed from secondary sources' — it is derivable in three lines from Pletcher Eqs. 1-4 with We = 0 (divide F = G(Eg + Efw) by G*Bgi, use Bg/Bgi = (p/z)i/(p/z), rearrange), which I did this session and which yields (p/Z)[1 - ce*(pi - p)] = (pi/Zi)(1 - Gp/G) with ce = (cw*Swi + cf)/(1 - Swi) exactly. What remains unverified is only (a) that SPE 10125 prints it in that algebraic arrangement and (b) the attribution itself; Pletcher says only that he used "a method equivalent to that of Ramagost and Farshad".
- The Anderson 'L' geopressured data table. Agreed with the card: not obtained, must not be written into the repository.
- The "226% overestimation, R2 = 0.992" figure from the 2023 JPEPT paper. Agreed: search-summary only, not usable.
- Bruns, Fetkovich & Meitzen (JPT 1965) primary text. Not retrieved. The apparent-GIIP algebra in the card is, however, self-consistent and I verified it reduces correctly from Gp = G - (G/Ei - We)*E.
- IHS/Fekete p/Z** and Z**, including the symbols cwip and cd, and the Moghadam/Jeje/Mattar primary. Not retrieved this session; agreed with the card that this block is secondary and incomplete. Recommend it not ship as a first-class primitive.
- The card's own claim that Pletcher's Table 3 Bg column is 'reproduced only by psc = 15.025 psia'. The back-solve is a zero-degree-of-freedom fit: psc is the single unknown in Bg = (psc/Tsc)(ZT/p), so the procedure cannot fail to produce a psc. What it genuinely verifies is the functional form (Bg*p/(Z*T) constant to 1.5e-4 relative across 11 rows), not the value. Label it as a fitted basis, not a verified constant.
- The claim "Zsc is assumed 1 ... cancels out of the p/Z ratio" is correct as stated, but the card nowhere verifies that Pletcher's Bg tables and the p/Z column were generated on the same basis. Table 7 prints both Bg and p/z, and the two imply different bases (Bg -> 14.699 psia; p/z is basis-free). Ingest published Bg columns as data; never recompute them.

### Missing before implementation

- No Z-factor correlation is actually specified. The card's only Z oracle (CHECK 6) terminates in a Standing-Katz CHART READING of 0.865, which is not machine-verifiable and the card says so. Nothing in the card lets an implementer compute Z. Either (a) declare Z an input column only (which is sufficient for all three regression tests, since Pletcher tabulates Z), or (b) source Dranchuk-Abou-Kassem / Hall-Yarborough with their published coefficients as a separate evidence card. Do not let the implementer improvise one.
- The standard-condition basis for each regression fixture must be pinned as fixture metadata, not recomputed. Concretely: Dake Ex. 1.2 requires psc = 14.7 psia / Tsc = degF + 460; Pletcher Table 3 requires psc ~ 15.02 psia at T = 239 degF; Pletcher Table 7 requires psc ~ 14.70 psia at T = 140 degF. Without this the card's own tolerances are unachievable.
- The exact least-squares protocol behind each published target is unstated and materially changes the answer: (i) modified p/Z targets 109.0/107.3/104.8 require an unconstrained OLS of the corrected p/Z on Gp INCLUDING the Gp = 0 point (verified this session); (ii) the pot-aquifer 2-year fit uses only Years 1 and 2 — two points, so R2 is undefined and the 'line' is exact; (iii) the 5- and 10-year pot-aquifer fits require Year 1 excluded (Pletcher: 'Analyses conducted after 5 and 10 years would likely have excluded the Year 1 data'); (iv) Table 6's Year 1 pot-aquifer row is footnoted 'Excluded from least-square fit'. Encode all four as fixture flags.
- The R2 definition used for the published 0.9998 / 0.934 is not stated. I reproduced them with ordinary R2 on the fitted y-axis; if the implementer uses an x-intercept-referenced or through-origin R2 the numbers will not match.
- Unit-assertion rule for We is underspecified. Pletcher's Table 2 column header is STB but Eq. 1 and Eq. 12 both require reservoir barrels; 2,359,460 STB * Bw 1.0571 = 2,494,185 res bbl, which is the 2,494,000 res bbl the body text quotes. The ingest path needs an explicit STB->res bbl multiplication by Bw and an assertion naming the expected unit.
- Roach-plot slope units are not fixed. Pletcher reports the one-cell Roach slope as 1.042e-5 MMscf^-1 (G = 96.0 Bcf); the card states 1/Mscf. Pick one and state it, or the Roach G will be off by 1e3 or 1e6.
- No standard error / confidence interval formula is given for the x-intercept, although the implementation notes ask for one. The x-intercept of an OLS line is a ratio of correlated estimates; specify either the delta method or a bootstrap, otherwise the implementer will invent something.
- The one-cell Fetkovich-aquifer model (Pletcher Table 9) is not in the card at all, yet it is the ONLY dataset in the paper that exercises the Roach and modified Roach plots (conventional slope 1.042e-5 -> G = 96.0 Bcf, ~5% LOW; modified 0.9853e-5 -> G = 101.5 Bcf, <1% high; W = 629e6 res bbl vs true 633e6). Since the card ships Roach equations, it must ship this fixture — note it is also the one case where the error is NEGATIVE, which is a useful counter-counterexample to the card's 'always overestimates' framing.
- Pletcher's explicit caveat on the modified Roach plot is missing from the card: 'the modified Roach plot has not been verified with actual field data because suitable field data have not become available.' That belongs in validity_ranges.
- Drive indices: Tables 5 and 6 give only IGD, ICD and Total for the modified p/z solution (no IWD, because that solution assumes no aquifer). The implementer needs to know the sum is over two indices in that branch, or the golden file will not reconcile.

### Recommended independent test oracles

**Exact-MBE synthetic reservoir (the sign-error detector)**

- Inputs: `Choose G, Bgi, cw, cf, Swi, W and an ARBITRARY pressure path and Wp series. Compute We = (cw+cf)*W*(pi-p), Efw = Bgi*ce*(pi-p), Bg = Bgi*(pi/Zi)/(p/Z), then SOLVE Gp from F = G(Eg+Efw)+We rather than supplying it. Feed the resulting (p, Z, Gp, Wp, We) table to every estimator.`
- Expected: `Pot-aquifer plot y-intercept = G exactly and slope = G*Bgi*ce + (cw+cf)*W exactly. Modified Roach: 1/slope = G to machine precision and intercept = -[ce + (cw+cf)*W/(G*Bgi)] to machine precision. Conventional p/Z x-intercept > G. All to ~1e-12 relative, since the data satisfy the balance identically.`
- Why independent: The data are generated from the material balance itself, with Gp as the dependent variable, so the oracle is an algebraic identity rather than a restatement of any estimator's code path. This is exactly the test that caught the Eq. 17 and Eq. 18 sign errors in this card: the card's printed intercept evaluates to +3.090e-6 where the identity requires -1.82667e-5.

**Standard-condition metamorphic invariance**

- Inputs: `Run the full pipeline twice on identical (p, Z, Gp) data, once with psc = 14.696 psia and once with psc = 15.025 psia, Tsc fixed.`
- Expected: `The p/Z-extrapolated G must be BIT-IDENTICAL between runs (psc cancels out of p/Z). Every Bg, every reservoir-barrel quantity (F, Eg, Efw, We, HCPV) and any volumetrically-derived G must scale by exactly 15.025/14.696 = 1.02239. Any quantity that moves when it should not have a hard-coded basis somewhere.`
- Why independent: A metamorphic relation over the whole program, requiring no reference values at all. It directly enforces the card's headline thesis and will catch the single defect the card itself predicts is most likely (a module-level psc constant).

**Degenerate-limit collapse of all six estimators**

- Inputs: `Volumetric dry-gas data with We = 0, cw = cf = 0: generate p/Z exactly linear in Gp from a chosen G, with Wp = 0.`
- Expected: `p/Z x-intercept, Ramagost-Farshad-corrected p/Z with ce = 0, Cole plot y-value at every point, modified Cole F/Et at every point, pot-aquifer y-intercept, and Roach 1/slope must ALL equal the same G to machine precision. The Cole plot must be exactly horizontal; the pot-aquifer slope exactly zero.`
- Why independent: A closed-form limit that every estimator must satisfy simultaneously. It is cross-validation between six structurally different code paths, so no shared bug can hide unless it is in the shared Bg routine — and oracle 2 covers that.

**Pletcher two-cell golden file (published, simulator-truth OGIP)**

- Inputs: `SPE 75354 Tables 1, 2 and 3 verbatim, T = 239 degF, cw = 3e-6, cf = 6e-6, Swi = 0.15, ce = 7.5882e-6 1/psi, We ingested as STB and multiplied by Bw.`
- Expected: `Modified p/Z x-intercept 109.0 / 107.3 / 104.8 Bcf at 11% / 27% / 54% recovery (I get 109.026 / 107.294 / 104.770), 10-year R2 = 0.9998 (I get 0.999788). Modified Cole 108.9 / 107.2 / 104.4 Bcf; original Cole at year 10 = 107.2 Bcf (I get 107.235). Pot aquifer 105.3 / 101.6 / 101.0 Bcf (I get 105.27 / 101.58 / 101.00), 10-year slope 1,103 RB/psi (I get 1102.6), W = 69.1e6 res bbl (I get 6.904e7), We(10 yr) from Eq. 12 = 2,346,000 res bbl (I get 2,344,383) against the simulator's 2,494,000. Uncorrected p/Z: 116.2 / 112.7 / 107.9 Bcf. Drive-index sums: pot-aquifer solution 1.005*/1.001/1.000/0.999/1.000/1.000/1.000/1.000/1.000/1.001; modified-p/Z solution 0.959/0.962/0.967/0.972/0.978/0.984/0.989/0.994/0.999/1.004 (monotone increasing — the wrong-solution signature).`
- Why independent: Truth is known exactly (100.8 Bcf) because the reservoir is an Eclipse simulation, not an estimate; the published targets were produced by a different engineer with different software in 2002. I re-derived every one of them this session from the tables. It is the single strongest oracle available and is what disproved the card's ce value.

**Oklahoma Morrow field golden file (four points, real data)**

- Inputs: `SPE 75354 Table 7 verbatim: T = 140 degF, cf = 3e-6, cw = 3e-6, Sw = 0.3, so ce = 5.5714e-6 1/psi. Days 0/72/237/332.`
- Expected: `Conventional p/Z G = 6.32 Bcf (I get 6.325); modified p/Z G = 6.02 Bcf (I get 6.017); pot-aquifer G = 5.44 Bcf with R2 = 0.934 and slope 58 RB/psi (I get 5.457, R2 = 0.9275, 57.0 RB/psi — use 0.05 Bcf and 2 RB/psi tolerances, not tighter); W from Eq. 14 with cf = 3e-6 gives 6.74e6 res bbl; cf from Eq. 15 assuming no aquifer gives 12e-6 1/psi against the estimated 3e-6; HCPV = 3,139,000 res bbl; total PV = 4.48e6 res bbl; We(332 d) = 99,800 res bbl = 3% of HCPV but 10% of the 992,700 res bbl cumulative voidage. Note Pletcher's Eq. 16 prints '4.84 million res bbl' — a typo; the correct value 4.48e6 is used in his very next sentence. Confirmed verbatim in the retrieved text.`
- Why independent: Real field data with noise and only four points, analysed by a third party, with all intermediates published. It exercises the numerically fragile early-time regime (Bg - Bgi = 0.0131 at the first non-zero point) that the synthetic oracles cannot.

**Drive-index closure as an algebraic identity**

- Inputs: `Any (p, Z, Gp, Wp, We) history plus any candidate G.`
- Expected: `IGD + ICD + IWD = G*Eg/(Gp*Bg) + G*Efw/(Gp*Bg) + (We - Wp*Bw)/(Gp*Bg) = 1 identically whenever G, We and the compressibilities satisfy F = G(Eg+Efw)+We at that point. Assert to 1e-12 on synthetic data; on the Pletcher pot-aquifer solution assert |sum - 1| < 0.005 per year; on a deliberately wrong G assert the sum shows a MONOTONE trend (Kendall tau = +/-1 over the history).`
- Why independent: It is Pletcher Eqs. 8-11 rearranged — a consequence of the balance, not of any estimator. It is the only check in the card that detects a wrong G without knowing the true G, and the monotone-trend test distinguishes a wrong solution from ordinary data scatter.

**Gas gradient from first principles (Bg-independent path)**

- Inputs: `gamma_g = 0.85, p = 4309 psia, T = 662 degR, Z = 0.888, M_air = 28.97 lbm/lbmol, R = 10.732.`
- Expected: `rho = p*M/(Z*R*T) = 4309*0.85*28.97/(0.888*10.732*662) = 16.82 lbm/ft3, i.e. 0.1168 psi/ft — matching the 0.117 psi/ft the card attributes to Dake, and hence the centroid pressure 4309 - 0.117*163 = 4290 psia.`
- Why independent: It reaches the same physical quantity through density rather than through Bg or E, so it validates the datum-correction code path without touching the psc/Tsc basis at all. I ran it this session and it is the one number in the un-retrieved Dake exercise that independently checks out.

**Ramagost-Farshad equivalence assertion**

- Inputs: `Synthetic data from oracle 1 with W = 0 (compaction only, no aquifer).`
- Expected: `(p/Z)*(1 - ce*(pi - p)) - (pi/Zi)*(1 - Gp/G) = 0 to machine precision at every point, and the corrected p/Z x-intercept returns G exactly. Also assert the guard: ce*(pi - p) < 1 must raise, not clamp, and never silently return a negative plotting term.`
- Why independent: The R-F form is a strict algebraic consequence of F = G(Eg + Efw) with We = 0 — I derived it this session — so the assertion is a closed-form identity rather than a second implementation of the same formula. It fails immediately for any mis-evaluated ce, which is precisely the defect found in this card.

## Sources

| Citation | Access level | Supports |
|---|---|---|
| Pletcher, J.L.: 'Improvements to Reservoir Material-Balance Methods', SPE Reservoir Evaluation & Engineering, Vol. 5, No. 1 (February 2002), pp. 49-59. SPE 75354, revised for publication from SPE 62882 presented at the 2000 SPE ATCE, Dallas, 1-4 October. | full-text retrieved | THE primary source for this card. Eqs. (1)-(18): the general gas MBE F = G(Eg+Efw)+We, Efw = Bgi[(Swi*cw+cf)/(1-Swi)](pi-p), Cole and modified Cole plots, drive indices, pot aquifer model and plot, Roach and modified Roach plots. Tables 1-8: the two-cell weak-waterdrive counterexample with true OGIP 100.8 Bcf and the Oklahoma Morrow field case. Every quantified overestimation figure in this card that I call verified comes from here and was independently recomputed. |
| Dake, L.P.: Fundamentals of Reservoir Engineering, Developments in Petroleum Science 8, Elsevier. Chapter 1 (secs. 1.5, 1.7) pp. 12-35; Chapter 3 (sec. 3.2) pp. 71-76; Chapter 7 (sec. 7.6) pp. 174-176. | full-text retrieved | Real gas law in field units with R = 10.732; the gas expansion factor E = 35.37 p/(ZT); the volumetric inventory balance eqs. (1.33)-(1.35) giving p/Z = (pi/Zi)(1-Gp/G); the HCPV reduction derivation eqs. (1.36)-(1.39); the water-drive forms eqs. (1.40)-(1.41); the Bruns apparent-GIIP method eqs. (1.42)-(1.44); the explicit warning that early water-drive p/Z trends look linear and give 'too large a value of the GIIP'; the zero-dimensional nature of the MBE and the requirement for a volume-averaged pressure at the centroid depth; Horner/MBH determination of average reservoir pressure; Exercise 1.2 with its full worked solution; Table 1.1 composition and the Standing-Katz worked example. |
| IHS Markit / Fekete, Harmony Enterprise 2019.3 documentation, 'Material Balance Analysis Theory' and 'Average Reservoir Pressure' reference pages. | secondary source, full-text and equation images retrieved | Independent confirmation of Bg = (Z_res n R T_res p_std)/(Z_std n R T_std p_res) and of Efw = (cf + cw*Sw)/(1 - Sw)*dp; the general MBE with Wp*Bw on the withdrawal side and We*Bw on the expansion side; the advanced p/Z** and Z** equations and cep = (cf + Swi*cw + Soi*co)(pi - p); the explicit prose statement of the geopressured failure mode ('When matching on the shallower slope of this bow-shaped trend... the estimated original gas-in-place is higher than the true original gas-in-place'); and the constraint ce(pi - p) < 1 on the Ramagost-Farshad average-pressure equation. Vendor documentation - use as corroboration, never as the sole authority for a derivation. |
| Adewumi, M.: PNG 520, Phase Relations in Reservoir Engineering, Penn State College of Earth and Mineral Sciences, module 18.5 'Volumetric Factors (Bo and Bg)'. Mirrored as Engineering LibreTexts 18.5. | full-text retrieved | The step-by-step Bg derivation eqs. (18.5)-(18.9): molar-volume definition, the compressibility-factor form Bg = (Psc R Tsc Zsc)/(P R T Z), the Zsc ~ 1 simplification, the standard conditions psc = 1 atm = 14.696 psia and Tsc = 60 degF = 519.67 degR, and the 1 RB = 5.615 RCF conversion. CAUTION: this page prints 0.005035 labelled [RCF/SCF] in BOTH eq. (18.8) and eq. (18.9); the rcf/scf coefficient should be 0.02827. Verified by computation this session - do not copy its coefficients blindly. |
| Ramagost, B.P. and Farshad, F.F.: 'P/Z Abnormally Pressured Gas Reservoirs', SPE-10125-MS, SPE Annual Technical Conference and Exhibition, San Antonio, TX, 5-7 October 1981. OSTI ID 6470177. | abstract/metadata only | The existence and scope of the compaction-corrected p/Z method ('maintains the straight line relationship for conventional P/Z's... by incorporating rock and water compressibility in the adjustment factor term') and the three case-study reservoirs: North Ossun Field (Louisiana), Anderson 'L' (South Texas) and an unnamed offshore Louisiana gas reservoir. The equation itself and the Anderson 'L' data table are NOT in the abstract. |
| Bruns, J.R., Fetkovich, M.J. and Meitzen, V.C.: 'The Effect of Water Influx on p/z-Cumulative Gas Production Curves', Journal of Petroleum Technology, Vol. 17, No. 3 (March 1965), p. 287. | abstract/metadata only | The original apparent-GIIP-versus-aquifer-model straight-line method. Retrieved here only as a citation; its content reaches this card through Dake's eqs. (1.42)-(1.44), which WERE retrieved in full. OnePetro returned 403 for the article itself. |
| Elahmady, M. et al.: 'Overestimation of Original Gas in Place in Water-Drive Gas Reservoirs Due to a Misleading Linear p/z Plot', Bulletin of Canadian Petroleum Geology, Vol. 41, 2002, p. 1101 (ADS record 2002BCaPG..41.1101E). | abstract/metadata only | Independent corroboration that the linear p/z plot, historically taken as the signature of a volumetric reservoir, can be produced by an aquifer-supported reservoir and cause major overestimation of OGIP. ADS returned 405 for the abstract page; this reaches me only via search-result metadata. Title and venue are usable; do not quote content from it. |
| 'A Straight Line p/z Plot is Possible in Waterdrive Gas Reservoirs', SPE-103258-MS, SPE Rocky Mountain Petroleum Technology Conference / Low Permeability Reservoirs Symposium, 2007. | abstract/metadata only | The mechanism claim that the combination of particular production rate schedules with the unsteady-state nature of aquifers can produce a genuinely straight p/z plot that masks an active aquifer. This is the most on-point primary reference for item (e) and should be obtained before the repository's counterexample documentation is finalised. |
| 'A novel material-balance approach for estimating in-place volumes of gas and water in gas reservoirs with aquifer support', Journal of Petroleum Exploration and Production Technology, 2023, DOI 10.1007/s13202-023-01630-5. | abstract/metadata only (fetch blocked; content reaches me only as a search-result summary) | The reported case of a p_avg/Z straight line with R2 = 0.992 at 50% recovery factor yielding G = 375 Bscf, a 226% overestimation. UNVERIFIED - do not cite this number without re-sourcing the paper. |
| Moghadam, S., Jeje, O. and Mattar, L.: 'Advanced Gas Material Balance in Simplified Format', Journal of Canadian Petroleum Technology, Vol. 50, No. 1 (2011), pp. 90-98; also PETSOC 2009-149, Canadian International Petroleum Conference, 2009. | abstract/metadata only | The primary reference behind the p/Z** method that unifies overpressured, water-drive and connected-reservoir corrections into a single straight-line plot. Reaches this card only through the Fekete/IHS vendor documentation. |

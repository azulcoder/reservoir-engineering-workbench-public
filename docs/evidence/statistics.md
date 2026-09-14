# Evidence card: Regression and uncertainty for p/Z

> Each card records what an implementer needs, where it came from, and how far it was
> verified. A card is not an authority: it is a statement of evidence with its access
> level attached. Items marked unverified are unverified, and the implementation must
> treat them as such.

**Adversarial review verdict:** `SOUND_WITH_CORRECTIONS`  
**Corrections applied:** 11  
**Items left unverified:** 14

## Summary

In essence: the x-intercept G = -a/b is a ratio, so its variance MUST use Cov(a,b); if that term is dropped, the estimator is wrong and consistently over-estimates uncertainty. For OLS, the delta method collapses into an elegant closed identity: Var(G) = (s^2/b^2)[1/n + (G - xbar)^2 / Sxx] — and I verified this numerically in the 2026-09-13 source review against Monte Carlo (0.7489 vs 0.7482, 200k trials) and against its long expansion (identical to machine precision); the version without Cov gives 1.019 instead of 0.749 (+36 percent), and on the York dataset-3 data it gives 1.5068 instead of 0.8021 (+88 percent). For errors-in-variables, the Deming closed form with lambda = V(eps_x)/V(delta_y) I reproduced to 13 digits against the published NCSS worked example (slope 1.00119422781949, intercept -0.0897448990070444), and the iterative York (2004) Eq. (13a)-(13d) scheme I reproduced exactly against York's own Table II dataset 3 (a = 5.47991, b = -0.480533, sigma_a = 0.294970, sigma_b = 0.057985, S/(n-2) = 1.483). An important trick from York himself: to obtain the x-intercept together with its standard error, interchange the x and y axes and refit — I checked that this gives an answer identical to the delta method with Cov (0.8020969448329495 vs 0.8020969448329499), so the two serve as oracles for each other. R-squared cannot validate the physical model: on a synthetic water-drive material balance, the post-inflection segment gives R^2 = 0.99993 with G biased +63 percent, and with realistic gauge noise R^2 = 0.9941 with +48 percent bias; Bruns, Fetkovich & Meitzen (1965, JPT, full text retrieved) report an over-estimate of more than 100 percent (990 vs ~475 Bscf) at 63 percent depletion. Finally, SE(G) scales roughly as 1/f with the depletion fraction f: at the same n and sigma, a reservoir that has produced only 10 percent of G has an SE(G) about 6.2x larger than one already at 50 percent (computed exactly: 4.645 vs 0.749 Bscf).

## Equations

### Volumetric (depletion-drive) gas material balance, p/Z straight line

```
p/Z = (p_i/Z_i) * (1 - Gp/G)   ;  slope b = -(p_i/Z_i)/G ,  intercept a = p_i/Z_i ,  x-intercept = G
```

*Unit system:* field units; p in psia (ABSOLUTE pressure), T in degrees Rankine (ABSOLUTE), Gp and G in scf (or consistently Bscf/MMscf), Z dimensionless

| Symbol | Meaning | Units |
|---|---|---|
| `p` | average reservoir pressure, absolute | psia |
| `Z` | real-gas compressibility (deviation) factor at p and reservoir T | dimensionless |
| `p_i, Z_i` | initial reservoir pressure and Z at that pressure | psia, dimensionless |
| `Gp` | cumulative gas produced, surface-measured | scf |
| `G` | original gas in place (GIIP) = x-intercept of the line | scf |

Assumptions:

- Closed (volumetric) reservoir: no water influx, We = 0
- Negligible formation and connate-water compressibility (no c_f, c_w term)
- Single average reservoir pressure representative of the whole tank at each survey
- Isothermal reservoir; Z evaluated at constant reservoir T
- Dry gas / no retrograde condensation, no gas dissolved in aquifer water

*Source:* Bruns, Fetkovich & Meitzen (1965) JPT, Appendix A Eqs. (A-1)-(A-6) [full text retrieved this session]; standard in Craft & Hawkins and Dake  
*Access:* full-text retrieved

### Water-drive gas material balance (the TRUE generating model for the demonstration)

```
(G - Gp)*Bg = G*Bgi - (We - Wp*Bw)   =>   p/Z = (p_i/Z_i) * (1 - Gp/G) / (1 - (We - Wp*Bw)/(G*Bgi))
```

*Unit system:* field units; Bg, Bgi in reservoir cu ft/scf (or rb/scf if We in rb); We, Wp*Bw in the SAME reservoir volume unit as G*Bgi

| Symbol | Meaning | Units |
|---|---|---|
| `Bg, Bgi` | gas formation volume factor at p and at p_i | rcf/scf (reservoir cu ft per standard cu ft) |
| `We` | cumulative water influx from the aquifer | rcf (reservoir cu ft) |
| `Wp` | cumulative water produced | STB or scf-consistent |
| `Bw` | water formation volume factor | rcf/STB (consistent with Wp) |

Assumptions:

- Tank (zero-dimensional) model; instantaneous pressure equilibration
- Aquifer influx supplied by an external model: Schilthuis steady-state, Hurst simplified, or van Everdingen-Hurst unsteady-state
- Residual gas saturation in the water-invaded zone is neglected in this simplest form (a trapped-gas term would add a further correction)

*Source:* Bruns, Fetkovich & Meitzen (1965) JPT 287-291 (SPE-898-PA), Appendix A Eqs. (A-7)-(A-11): G_r = G_p*Bg/(Bg - Bgi) - K_e*S(p,t)/(Bg - Bgi), i.e. G_apparent = G_real + K_e*S(p,t)/(Bg - Bgi)  
*Access:* full-text retrieved

### Ordinary least squares closed form (y = a + b*x)

```
xbar = (1/n)*sum(x_i) ; ybar = (1/n)*sum(y_i) ; Sxx = sum((x_i - xbar)^2) ; Sxy = sum((x_i - xbar)*(y_i - ybar)) ; Syy = sum((y_i - ybar)^2)
b = Sxy / Sxx
a = ybar - b*xbar
s^2 = SSE/(n-2) , SSE = sum((y_i - a - b*x_i)^2)
```

*Unit system:* unit-agnostic; for this application x = Gp [Bscf], y = p/Z [psia], so b is [psia/Bscf] and a is [psia]

| Symbol | Meaning | Units |
|---|---|---|
| `n` | number of (Gp, p/Z) survey points | count |
| `b` | fitted slope | psia/Bscf |
| `a` | fitted y-intercept, estimate of p_i/Z_i | psia |
| `s^2` | residual mean square, unbiased estimate of the y-error variance sigma^2 | psia^2 |

Assumptions:

- x (Gp) treated as error-free
- y errors iid N(0, sigma^2), homoscedastic, independent across surveys
- Model is truly linear over the fitted range

*Source:* Draper & Smith, Applied Regression Analysis, 3rd ed., Wiley 1998, Ch. 1  
*Access:* Unverified — cited source not inspected - not retrieved

### OLS standard errors of slope and intercept AND the covariance term (do not omit)

```
Var(b) = s^2 / Sxx
Var(a) = s^2 * (1/n + xbar^2 / Sxx)
Cov(a, b) = - xbar * s^2 / Sxx = - xbar * Var(b)
corr(a,b) = -xbar / sqrt(Sxx/n + xbar^2)
```

*Unit system:* same as the OLS block

| Symbol | Meaning | Units |
|---|---|---|
| `Cov(a,b)` | covariance of intercept and slope estimators; NEGATIVE whenever xbar > 0, which is always true for Gp >= 0 | psia^2/Bscf |

Assumptions:

- Same as OLS block
- Cov(a,b) = 0 ONLY if the x data are centred (xbar = 0). Fitting p/Z on raw Gp is never centred, so the covariance is always material.

*Source:* Draper & Smith (1998); also York et al. (2004) Sec. II, which states the analogous result cov(a,b) = -xbar*sigma_b^2 for the general EIV case [retrieved]  
*Access:* full-text retrieved

### x-intercept (G) and its delta-method variance INCLUDING the covariance term

```
G_hat = -a / b
d(G)/da = -1/b ,  d(G)/db = a/b^2 = -G_hat/b
Var(G_hat) = (1/b^2) * [ Var(a) + G_hat^2 * Var(b) + 2*G_hat*Cov(a,b) ]

Substituting the OLS expressions above this collapses EXACTLY to:
Var(G_hat) = (s^2 / b^2) * [ 1/n + (G_hat - xbar)^2 / Sxx ]
SE(G_hat) = (s/|b|) * sqrt( 1/n + (G_hat - xbar)^2 / Sxx )
```

*Unit system:* G_hat and SE in Bscf when x is in Bscf

| Symbol | Meaning | Units |
|---|---|---|
| `G_hat` | estimated gas in place, the x-intercept | Bscf |
| `Sxx` | sum of squared deviations of Gp about its mean; the lever arm of the fit | Bscf^2 |

Assumptions:

- First-order (delta-method) linearisation of the ratio -a/b; valid only while the slope is sharply determined
- Requires g = t^2*Var(b)/b^2 << 1 (see the Fieller block); as g -> 1 the linearisation is invalid and the true interval is unbounded
- Same OLS error assumptions

*Source:* Standard delta method; the collapsed form is the classical inverse-prediction/calibration variance (Draper & Smith 1998 Ch. 3; Graybill). Both forms and their equality VERIFIED numerically this session, and the collapsed form matched a 200,000-trial Monte Carlo.  
*Access:* Unverified — cited source not inspected - not retrieved (but numerically verified in-session against Monte Carlo and against the York axis-swap oracle)

### WRONG estimator to guard against (covariance omitted) - regression-test target

```
Var_WRONG(G_hat) = (1/b^2) * [ Var(a) + G_hat^2 * Var(b) ]        <-- DEFECTIVE
Because Cov(a,b) = -xbar*Var(b) < 0 and G_hat > 0, the omitted term 2*G_hat*Cov(a,b) is NEGATIVE, so the defective estimator ALWAYS over-states Var(G_hat) for a depleting gas reservoir.
Ratio of the two: Var_WRONG/Var_TRUE = [1/n + xbar^2/Sxx + G_hat^2/Sxx] / [1/n + (G_hat-xbar)^2/Sxx]
```

*Unit system:* same as above

| Symbol | Meaning | Units |
|---|---|---|
| `Var_WRONG` | the defective variance an implementation produces if it treats a and b as independent | Bscf^2 |

Assumptions:

- Direction of the error (always conservative/too wide) holds for xbar > 0 and G_hat > 0, i.e. every physical p/Z fit

*Source:* Algebraic consequence of Cov(a,b) = -xbar*Var(b); magnitudes measured in-session  
*Access:* secondary source

### Fieller / inverse-prediction exact confidence set for the x-intercept (use when the slope is not sharply determined)

```
Confidence set = { x : (a + b*x)^2 <= t^2_{1-alpha/2, n-2} * s^2 * [ 1/n + (x - xbar)^2 / Sxx ] }
Let g = t^2 * s^2 / (b^2 * Sxx)  ( = [t*SE(b)/b]^2 ; note g >= 1 exactly when |b|/SE(b) <= t, i.e. the slope is not significant )
If g < 1 the set is the bounded interval
  x_{L,U} = xbar + [ (G_hat - xbar) -/+ (t*s/|b|) * sqrt( (G_hat - xbar)^2 / Sxx + (1-g)/n ) ] / (1 - g)
If g >= 1 the set is UNBOUNDED (a half-line or the whole line): G is not identified at that confidence level and no finite error bar should be printed.
```

*Unit system:* same as OLS block

| Symbol | Meaning | Units |
|---|---|---|
| `g` | Fieller/Creasy discriminant; squared inverse t-statistic of the slope | dimensionless |
| `t_{1-alpha/2, n-2}` | Student-t quantile, n-2 degrees of freedom | dimensionless |

Assumptions:

- Normal errors in y only (the OLS case)
- Interval is asymmetric about G_hat by construction; the delta-method interval is its symmetric small-g limit
- This is the same algebra as the classical calibration (inverse-regression) interval

*Source:* Fieller, E.C. (1954), 'Some Problems in Interval Estimation', JRSS Series B 16(2):175-185 [metadata/abstract retrieved]; closed form VERIFIED in-session against brute-force inversion of the quadratic set and against Monte Carlo coverage  
*Access:* abstract/metadata only

### Deming regression closed form with known error-variance ratio lambda

```
Model: x_i = X_i + eps_i ,  y_i = Y_i + delta_i ,  Y_i = beta0 + beta1*X_i
lambda = V(eps_i) / V(delta_i)     [ = variance of the X-error over the variance of the Y-error ]
Objective: SS = sum_i [ (x_i - Xhat_i)^2 + lambda * (y_i - Yhat_i)^2 ]
u = sum((x_i - xbar)^2)  ;  q = sum((y_i - ybar)^2)  ;  p = sum((x_i - xbar)*(y_i - ybar))
b1 = [ (lambda*q - u) + sqrt( (u - lambda*q)^2 + 4*lambda*p^2 ) ] / ( 2*lambda*p )
b0 = ybar - b1*xbar
Adjusted (true-value) points:  d_i = y_i - (b0 + b1*x_i)
  Xhat_i = x_i + lambda*b1*d_i / (1 + lambda*b1^2)
  Yhat_i = y_i -          d_i / (1 + lambda*b1^2)
Limits (sanity checks): lambda -> 0 gives the OLS slope p/u ; lambda -> infinity gives the x-on-y slope q/p ; lambda = 1 gives orthogonal (major-axis) regression.
```

*Unit system:* unit-agnostic, but lambda is a ratio of variances in the NATIVE units of each axis, so lambda is NOT scale-invariant: rescaling Gp from scf to Bscf changes lambda by 10^18. Pin the units in the API.

| Symbol | Meaning | Units |
|---|---|---|
| `lambda` | error variance ratio V(x-error)/V(y-error) in the NCSS/Linnet convention used here | (x-units)^2 / (y-units)^2, i.e. Bscf^2/psia^2 for p/Z vs Gp |
| `u, q, p` | Sxx, Syy, Sxy | Bscf^2, psia^2, Bscf*psia |
| `b1, b0` | Deming slope and intercept | psia/Bscf, psia |

Assumptions:

- eps_i and delta_i independent of each other and across points, Normal, zero mean
- lambda CONSTANT over all points (or errors at least proportional)
- Points independent - violated when the gauge drifts; see the drift section
- For p/Z vs Gp: y = p/Z carries gauge + Z-correlation error, x = Gp carries allocation/metering error, so lambda = sigma^2_Gp / sigma^2_(p/Z)

*Source:* NCSS Statistical Software, Chapter 303 'Deming Regression' (formulas stated to follow Linnet K. 1990) [full text retrieved]; Linnet K. (1990) Stat. Med. 9:1463-1473 and Linnet K. (1993) Clin. Chem. 39:424-432 [cited by NCSS, not retrieved]  
*Access:* full-text retrieved

### Deming standard errors (jackknife, the method the reference implementation uses)

```
For any statistic theta_hat (slope, intercept, predicted value, G_hat):
1. theta_hat from all N points
2. theta_hat_{-i} from the data with pair (x_i,y_i) deleted, i = 1..N
3. pseudovalues:  theta*_i = N*theta_hat - (N-1)*theta_hat_{-i}
4. theta_jack = (1/N) * sum_i theta*_i
5. Va(theta_hat) = sum_i (theta*_i - theta_jack)^2 / (N-1)
6. SE(theta_hat) = sqrt( Va(theta_hat) / N )
Confidence interval: theta_hat +/- t_{1-alpha/2, N-2} * SE(theta_hat)  (CLSI EP09-A3 App. H specifies N-2 df; some packages use N-1)
```

*Unit system:* same units as theta

| Symbol | Meaning | Units |
|---|---|---|
| `theta*_i` | i-th jackknife pseudovalue | units of theta |
| `N` | number of pairs | count |

Assumptions:

- Jackknife assumes independent pairs - it is INVALID under gauge drift; use a block jackknife / block bootstrap instead
- Linnet (1990) showed the jackknife performs adequately for Deming regression under iid errors

*Source:* NCSS Chapter 303, 'Jackknife Standard Error Estimation' [full text retrieved]; VERIFIED in-session: reproduced NCSS Example 1 published SE(slope)=0.18718 and SE(intercept)=1.72199  
*Access:* full-text retrieved

### York (1968/1969, unified 2004) general EIV estimator with per-point weights and correlated errors

```
Notation (York et al. 2004, Table I):
  omega(X_i) = 1/sigma^2(X_i)   (weight of the i-th x observation)
  omega(Y_i) = 1/sigma^2(Y_i)   (weight of the i-th y observation)
  alpha_i = sqrt( omega(X_i) * omega(Y_i) )
  r_i = correlation coefficient between the errors in X_i and Y_i
  W_i = omega(X_i)*omega(Y_i) / ( omega(X_i) + b^2*omega(Y_i) - 2*b*r_i*alpha_i )
        [ for r_i = 0 this is the familiar effective-variance weight W_i = 1/( sigma_Y_i^2 + b^2*sigma_X_i^2 ) ]
  Xbar = sum(W_i*X_i)/sum(W_i) ;  Ybar = sum(W_i*Y_i)/sum(W_i)
  U_i = X_i - Xbar ;  V_i = Y_i - Ybar
  beta_i = W_i * [ U_i/omega(Y_i) + b*V_i/omega(X_i) - (b*U_i + V_i)*r_i/alpha_i ]

Unified equations (York et al. 2004, Eqs. 13a-13d):
  (13b)  b = sum(W_i*beta_i*V_i) / sum(W_i*beta_i*U_i)          <- solved ITERATIVELY
  (13a)  a = Ybar - b*Xbar
  (13d)  sigma_b^2 = 1 / sum(W_i * u_i^2)
  (13c)  sigma_a^2 = 1/sum(W_i) + xbar^2 * sigma_b^2
with the least-squares-ADJUSTED points  x_i = Xbar + beta_i ,  y_i = Ybar + b*beta_i ,
     xbar = sum(W_i*x_i)/sum(W_i) ,  u_i = x_i - xbar
and  cov(a,b) = - xbar * sigma_b^2 ,  corr(a,b) = - xbar * sigma_b / sigma_a

Iteration (York et al. 2004, steps 1-10):
  (1) initialise b from OLS of y on x
  (2) form omega(X_i), omega(Y_i)
  (3) form W_i from the current b and the r_i
  (4) form Xbar, Ybar, U_i, V_i, beta_i
  (5) update b from Eq. (13b)
  (6) repeat (3)-(5) until successive b agree to tolerance (York suggests 1 part in 1e15; ~10 iterations typical, <50 for pathological sets)
  (7) a = Ybar - b*Xbar
  (8) x_i = Xbar + beta_i
  (9) xbar and u_i from the ADJUSTED x_i
  (10) sigma_b then sigma_a from Eqs. (13d), (13c)

Goodness of fit: S = sum( W_i * (Y_i - b*X_i - a)^2 ) is chi-square with n-2 df, so E[S/(n-2)] = 1 (this is the MSWD).
```

*Unit system:* unit-agnostic; weights are the reciprocal of the variance in each axis's own units, so omega(X) is 1/Bscf^2 and omega(Y) is 1/psia^2

| Symbol | Meaning | Units |
|---|---|---|
| `sigma(X_i), sigma(Y_i)` | per-point 1-sigma measurement errors in x and y | Bscf, psia |
| `r_i` | within-point correlation of the x and y errors (e.g. if Z is computed from the same measured p, or if Gp and p share a common allocation model) | dimensionless, in [-1, 1] |
| `W_i` | York effective weight, depends on the current slope b | 1/psia^2 |
| `S/(n-2)` | MSWD, reduced chi-square; >> 1 means the straight-line model or the assigned errors are wrong | dimensionless |

Assumptions:

- Errors Normal, per-point known (up to a common scale), INDEPENDENT BETWEEN POINTS (this is the assumption gauge drift breaks)
- The sigma_a, sigma_b formulas above are evaluated at the ADJUSTED points - that is the whole point of the 2004 unification and makes LSE identical to MLE
- Equations (13) are symmetric in x and y: swapping the two axes (and their weights) returns the same line
- York's special cases: r_i = 0 and W_i = 1 gives major-axis; r_i = 0 and W_i = omega(Y_i) gives weighted y-on-x OLS; r_i = -1 recovers the Brooks/Wendt/Harre solution

*Source:* York, D., Evensen, N.M., Lopez Martinez, M., De Basabe Delgado, J. (2004), 'Unified equations for the slope, intercept, and standard errors of the best straight line', Am. J. Phys. 72(3):367-375, DOI 10.1119/1.1632486 [full text retrieved]; original: York (1966) Can. J. Phys. 44:1079-1086 and York (1969) Earth Planet. Sci. Lett. 5:320-324  
*Access:* full-text retrieved

### York's own recipe for the x-intercept and its standard error (the preferred route for G)

```
Because Eqs. (13) are symmetric in x and y, refit with the axes INTERCHANGED:
  york_fit( X <- (p/Z)_i , Y <- Gp_i , omega(X) <- 1/sigma^2(p/Z)_i , omega(Y) <- 1/sigma^2(Gp)_i , r_i unchanged )
The y-intercept 'a' of the swapped fit IS the x-intercept of the original fit, i.e. G, and its sigma_a IS SE(G) directly - no delta method needed. The swapped slope is the reciprocal of the original slope.
```

*Unit system:* G in Bscf, SE(G) in Bscf

| Symbol | Meaning | Units |
|---|---|---|
| `a_swapped` | y-intercept of the axis-swapped York fit = G | Bscf |
| `sigma_a_swapped` | its standard error = SE(G) | Bscf |

Assumptions:

- Same York assumptions
- Gives a second, independent numerical route to SE(G) - use it as the repository's oracle for the delta-method code path

*Source:* York et al. (2004), Sec. III: 'In our work with 40Ar-39Ar geochronology, where the x intercept is significant, we normally interchange x and y data to obtain the original x intercept and its standard error.' [full text retrieved]. VERIFIED in-session: axis swap gave SE = 0.8020969448329495 vs delta-method-with-Cov 0.8020969448329499 on York's dataset 3.  
*Access:* full-text retrieved

### Moving-block bootstrap (Kuensch 1989) for correlated pressure error

```
Given ordered pairs z_t = (Gp_t, (p/Z)_t), t = 1..n, and block length l:
  Blocks B_j = (z_j, z_{j+1}, ..., z_{j+l-1}) for j = 1..n-l+1   (overlapping)
  Draw k = ceil(n/l) block start indices j uniformly from {1..n-l+1} with replacement
  Concatenate the drawn blocks and truncate to length n -> one resample
  Refit (OLS / Deming / York) on the resample -> G*_1..G*_B
  SE_MBB(G) = sd{ G*_b } ; percentile or BCa interval from the G* distribution
Circular block bootstrap (CBB): wrap the series so every observation has the same inclusion probability.
Stationary bootstrap (Politis & Romano 1994): block lengths are Geometric(1/L) so the resample is stationary; L is the MEAN block length.
```

*Unit system:* l and n are counts of pressure surveys

| Symbol | Meaning | Units |
|---|---|---|
| `l` | block length (number of consecutive surveys per block) | count |
| `k = ceil(n/l)` | number of blocks drawn per resample | count |
| `B` | number of bootstrap resamples, >= 1000 for an SE, >= 5000 for a percentile interval | count |

Assumptions:

- Blocks must be drawn over the TIME/SURVEY index, never over a shuffled order - the whole point is to preserve local dependence
- Pairs (x_t, y_t) must move together so the EIV structure survives
- Requires n >> l; with n < ~30 surveys the block bootstrap has very little to work with

*Source:* Kuensch, H.R. (1989), 'The jackknife and the bootstrap for general stationary observations', Annals of Statistics 17(3):1217-1241; Politis, D.N. & Romano, J.P. (1994), 'The stationary bootstrap', JASA 89:1303-1313 [the Politis-Romano citation was retrieved from the reference list of Patton, Politis & White (2009), full text retrieved]  
*Access:* Unverified — cited source not inspected - not retrieved

### Block-length selection rule

```
Rate rule (Hall, Horowitz & Jing 1995): the MSE-optimal block length is of order
  l_opt ~ C * n^(1/3)   for estimating a VARIANCE or a BIAS   <- this is our case (SE of G)
  l_opt ~ C * n^(1/4)   for a ONE-SIDED distribution function
  l_opt ~ C * n^(1/5)   for a TWO-SIDED distribution function (e.g. a two-sided percentile CI for G)
HHJ empirical rule: estimate l_opt at a subsample size m by cross-validation, then rescale to the full sample by the same exponent, e.g. l_opt(n) = l_opt(m) * (n/m)^(1/3) for the variance case.
Data-driven plug-in (Politis & White 2004, as corrected by Patton, Politis & White 2009): choose b to minimise the asymptotic MSE of the zero-frequency spectral-density estimate, using flat-top lag-window estimates; the CORRECTED variance constant is D_SB = 2*g^2(0) and its estimator is D_SB_hat = 2*g_hat^2(0). Rate is n^(1/3).
PHYSICAL FLOOR for this repository: l must also exceed the integrated autocorrelation time of the gauge drift, tau_int = (1 + rho)/(1 - rho) for an AR(1) drift with lag-1 correlation rho.
```

*Unit system:* counts of surveys

| Symbol | Meaning | Units |
|---|---|---|
| `l_opt` | MSE-optimal block length | count |
| `rho` | lag-1 autocorrelation of the pressure-survey error series | dimensionless |
| `tau_int` | integrated autocorrelation time of an AR(1) drift | count of surveys |
| `g(0), g_hat(0)` | the quantity whose square enters the corrected stationary-bootstrap variance constant D_SB (Politis & White 2004 Thm 3.1 notation) | as defined in that paper |

Assumptions:

- The n^(1/3) rate is ASYMPTOTIC. With n = 10-60 pressure surveys, n^(1/3) is only 2.2-3.9, which is far smaller than tau_int for a realistically drifting gauge (rho = 0.9 gives tau_int = 19). Do not apply the rate rule blindly at these sample sizes.
- Politis-White requires a long enough series to estimate the autocorrelation function at all

*Source:* Hall, P., Horowitz, J.L., Jing, B.-Y. (1995), 'On blocking rules for the bootstrap with dependent data', Biometrika 82(3):561-574 [abstract retrieved: the n^(1/3), n^(1/4), n^(1/5) statement is quoted from the published abstract]; Politis, D.N. & White, H. (2004), Econometric Reviews 23(1):53-70 [metadata only]; Patton, A., Politis, D.N., White, H. (2009), 'Correction to Automatic Block-Length Selection for the Dependent Bootstrap', Econometric Reviews 28(4):372-375 [full text retrieved]  
*Access:* abstract/metadata only

### How each error type propagates into the x-intercept (exact algebra)

```
Let the fitted line be y = a + b*x and G_hat = -a/b.
(A) RANDOM iid GAUGE NOISE on y, sd sigma:  SE(G) = (sigma/|b|)*sqrt(1/n + (G - xbar)^2/Sxx)  ->  shrinks as 1/sqrt(n). AVERAGES OUT.
(B) SHARED ADDITIVE CALIBRATION BIAS c on y (same offset every survey): a -> a + c, b unchanged, so
       G_hat -> G_hat - c/b = G_hat + c*G/(p_i/Z_i)
    SE contribution = sigma_c/|b| = sigma_c * G / (p_i/Z_i), INDEPENDENT OF n AND OF DEPLETION. It is an irreducible floor.
(C) SHARED MULTIPLICATIVE GAIN on y (y -> (1+gam)*y): a and b BOTH scale by (1+gam), so G_hat = -a/b is EXACTLY INVARIANT. A pure gauge gain error does not bias G at all.
(D) ADDITIVE OFFSET on Gp (allocation baseline error, x -> x + c_x): G_hat -> G_hat + c_x, a ONE-FOR-ONE shift.
(E) MULTIPLICATIVE GAIN on Gp (x -> (1+gam_x)*x): G_hat -> (1+gam_x)*G_hat, a PROPORTIONAL error. A 2 percent allocation gain error is a 2 percent error in G, full stop, and no amount of data removes it.
(F) TEMPORALLY CORRELATED DRIFT on y (AR(1), or a ramp): intermediate between (A) and (B). It does not average out at rate 1/sqrt(n); the effective sample size is n/tau_int. A monotone ramp is the most dangerous because it projects directly onto the slope, and the slope is what sets G.
```

*Unit system:* field units as above

| Symbol | Meaning | Units |
|---|---|---|
| `c` | shared additive gauge offset on p/Z | psia |
| `gam` | fractional gauge gain error on p/Z | dimensionless |
| `c_x, gam_x` | additive and fractional errors in cumulative production allocation | Bscf, dimensionless |

Assumptions:

- (C) holds exactly only if the SAME gain multiplies p/Z at every survey; a drifting gain does bias G
- (B) and (D) are pure translations and therefore cannot be detected from the residuals or from R-squared - they need external calibration evidence

*Source:* Elementary algebra of the OLS estimator; every case VERIFIED numerically in-session by Monte Carlo (see independent_checks)  
*Access:* secondary source

### How SE(G) scales with the depletion fraction reached

```
Let the surveys be spread roughly uniformly over Gp in [0, f*G], where f = fraction of G produced so far, with n surveys.
Then xbar ~= f*G/2 and Sxx ~= n*f^2*G^2/12, and
  SE(G) ~= (sigma/|b|) * sqrt( (1 + 12*(1 - f/2)^2 / f^2) / n )
         = (sigma * G / (p_i/Z_i)) * sqrt( (1 + 12*(1 - f/2)^2 / f^2) / n )
For small f the bracket is dominated by 12/f^2, so
  SE(G) ~ (sigma*G/(p_i/Z_i)) * sqrt(12/n) * (1 - f/2)/f     i.e. SE(G) scales essentially as 1/f.
Ratio at f = 0.10 versus f = 0.50, same sigma and same n:  sqrt(1+12*0.9025/0.01)/sqrt(1+12*0.5625/0.25) = 32.92/5.29 = 6.22.
```

*Unit system:* Bscf, psia

| Symbol | Meaning | Units |
|---|---|---|
| `f` | fraction of G produced at the time of the last survey, Gp_max/G | dimensionless in (0,1] |
| `sigma` | 1-sigma error on p/Z per survey | psia |

Assumptions:

- Surveys uniformly spread over the produced range; a clustered schedule does worse
- Same sigma and same n in both comparisons - if a longer history also means MORE surveys, the improvement is larger still (extra 1/sqrt(n))
- Assumes the reservoir really is volumetric; at f = 0.10 the data also cannot yet discriminate a volumetric from a water-drive reservoir, which is a separate and larger problem

*Source:* Derived from the closed-form Var(G_hat) above; ratio VERIFIED numerically in-session (6.2025 for 12 equally spaced surveys)  
*Access:* secondary source

### Gas formation volume factor (needed to build the water-drive generator)

```
Bg = (p_sc/T_sc) * (Z*T/p) = 0.02827 * Z*T/p   [reservoir cu ft per scf]
Bg = 0.005035 * Z*T/p                            [reservoir bbl per scf]
```

*Unit system:* field units; p in psia (ABSOLUTE), T in degrees Rankine (ABSOLUTE)

| Symbol | Meaning | Units |
|---|---|---|
| `T` | reservoir temperature, absolute | degrees Rankine (deg F + 459.67) |
| `p_sc, T_sc` | standard conditions, 14.696 psia and 519.67 R (60 deg F) | psia, R |

Assumptions:

- Standard conditions 14.696 psia / 60 deg F. If your jurisdiction uses 14.65 or 15.025 psia, the constant changes and every volume changes with it - make it a named constant, not a literal.

*Source:* Standard petroleum engineering identity; the numeric constant 0.02827 = 14.696/519.67 was re-derived and checked this session  
*Access:* secondary source

## Constants

| Name | Value | Units | Source | How verified |
|---|---|---|---|---|
| p_sc / T_sc conversion constant in Bg = C * Z*T/p (reservoir cu ft per scf) | `0.028280 (commonly written 0.02827)` | (psia/R), giving rcf/scf when T in R and p in psia | = 14.696 psia / 519.67 R (standard conditions 14.696 psia, 60 deg F) | Re-derived arithmetically in-session: 14.696/519.67 = 0.0282797. Consistent with the value used to reproduce Bruns et al. (1965) Table 1 GIIP (see independent_checks). |
| Same constant expressed in reservoir barrels | `0.0050365` | rb/scf when T in R and p in psia | = 0.028280 / 5.615 ft^3 per bbl | Re-derived arithmetically in-session |
| Standard pressure p_sc (US customary) | `14.696` | psia | Standard conditions convention | recalled - NOT retrieved this session. Jurisdiction-dependent (14.65 psia in Texas RRC practice, 14.73 psia in some gas contracts, 15.025 psia in Louisiana). Treat as a configurable constant. |
| Standard temperature T_sc (US customary) | `519.67 (= 60 deg F)` | degrees Rankine | Standard conditions convention | recalled - NOT retrieved this session |
| ft^2 per acre | `43560` | ft^2/acre | Exact definition of the acre | exact by definition |
| Hall-Horowitz-Jing block-length exponent for VARIANCE/BIAS estimation | `1/3` | exponent on n | Hall, Horowitz & Jing (1995), Biometrika 82(3):561-574 | Quoted from the published abstract retrieved this session ('equal to n^(1/3), n^(1/4), and n^(1/5) in the cases of variance or bias estimation, estimation of a one-sided distribution function, and estimation of a two-sided distribution function, respectively') |
| HHJ exponent for a two-sided distribution function (percentile CI) | `1/5` | exponent on n | Hall, Horowitz & Jing (1995), Biometrika 82(3):561-574 | Quoted from the published abstract retrieved this session |
| Corrected stationary-bootstrap variance constant D_SB (Politis & White 2004 Theorem 3.1) | `D_SB = 2*g^2(0), estimator D_SB_hat = 2*g_hat^2(0)` | as defined in Politis & White (2004) | Patton, Politis & White (2009), Econometric Reviews 28(4):372-375, items 1 and 4 | Full text of the 2009 correction retrieved and read this session. The corresponding D_CB and the explicit form of PW2004 Eqs. (6)-(9) were NOT retrieved. |
| Asymptotic relative efficiency of circular block vs stationary bootstrap | `ARE_CB/SB = (2/3)^(2/3) ~= 0.7631` | dimensionless | Patton, Politis & White (2009), Eq. (1) | Full text retrieved this session (the OCR rendered the decimal as 0/periodori7631428, i.e. 0.7631428; (2/3)^(2/3) = 0.763143 checks out arithmetically) |
| Deming default lambda when no error information exists | `1.0 (orthogonal / major-axis regression)` | dimensionless ratio, but in the NATIVE units of each axis | NCSS Chapter 303, Deming Regression | Full text retrieved. WARNING: lambda = 1 in native units is scale-dependent and is a physically arbitrary default for p/Z [psia] vs Gp [Bscf]; do not silently default to it. |
| Degrees of freedom for Deming jackknife t-intervals | `N - 2` | count | CLSI EP09-A3, Appendix H, as cited by NCSS Chapter 303 | NCSS text retrieved this session states CLSI EP09-A3 App. H specifies N-2; the CLSI standard itself was NOT retrieved. Some packages (MedCalc, the Deal SAS macro) use N-1. |
| Bruns et al. (1965) synthetic field: volumetric GIIP | `~475-500 Bscf (475 at Z_i = 1.00, 489 at Z_i = 0.97, 500 at Z_i = 0.95)` | Bscf | Computed from Bruns, Fetkovich & Meitzen (1965) Table 1 field conditions: 2500 acres, 100 ft pay, phi = 0.25, Swc = 0.30, p_i = 5000 psia, T = 250 deg F | Computed in-session from the RETRIEVED Table 1; brackets the paper's own weak-aquifer (Ra/Rr = 1.5) estimate of 475 Bscf, which is the internal consistency check |

## Validity ranges

- OLS delta-method SE(G) is trustworthy only while g = [t_{1-alpha/2,n-2} * SE(b)/b]^2 << 1, equivalently while the slope t-statistic |b|/SE(b) is comfortably above the t critical value. Measured in-session: at |b|/SE(b) = 17-107 the delta interval has 94.9-95.2 percent coverage; at low signal (n=8, f=0.05, sigma=300 psia, so |b|/SE(b) near t) coverage collapses to 78.7 percent while the Fieller set holds 97.2 percent. Compute g and report it; refuse to print a symmetric +/- interval when g > ~0.05.
- Deming closed form requires lambda known and CONSTANT across points. For p/Z vs Gp, lambda = sigma^2_Gp / sigma^2_(p/Z) in native units. Early-life Gp is small and its relative allocation error is usually larger, so constant-lambda is questionable early; weighted Deming (proportional errors) or York per-point weights is the correct escalation.
- York's iterative scheme converged in 9 iterations on York's own dataset 3 in-session; York reports ~10 iterations typical and fewer than 50 for pathological sets (Reed's data set II). Cap iterations at 200 and FAIL LOUDLY rather than returning a non-converged slope.
- The Deming slope formula divides by 2*lambda*p where p = Sxy. It is singular at Sxy = 0 and numerically unstable for |Sxy| small. For a depleting gas reservoir Sxy is strongly negative and well away from zero, but the guard is still required for degenerate inputs (a shut-in period with no production, all Gp identical).
- The p/Z straight line itself is valid only for a volumetric, dry-gas, normally-pressured reservoir. For abnormally pressured (geopressured) reservoirs the rock and connate-water compressibility terms are NOT negligible and the p/Z plot shows two straight-line segments; a single-line fit over-estimates G. For water-drive reservoirs the line is curved (see the demonstration). For gas-condensate below the dew point, Z must be a two-phase Z.
- The n^(1/3) HHJ block-length rate is asymptotic. At the sample sizes a real pressure-survey history provides (n = 10-60), n^(1/3) is 2.2-3.9 surveys, which is much shorter than the correlation length of a drifting gauge. Verified in-session: with n = 48 and AR(1) rho = 0.9 (tau_int = 19), MBB at l = n^(1/3) ~= 3.6 recovered only ~32 percent of the true sampling sd; l = 12 recovered ~82 percent; the iid bootstrap recovered 18 percent.
- Every reported G must be accompanied by the depletion fraction f = Gp_max/G_hat at which it was estimated. Below roughly f = 0.15-0.20 the extrapolation is dominated by lever-arm amplification and, worse, cannot yet discriminate a volumetric from a water-drive reservoir at all.
- Absolute units are mandatory: p must be psia not psig (a 14.7 psi offset is exactly the 'shared additive calibration bias' failure mode, and it biases G by +14.7*G/(p_i/Z_i), i.e. ~0.3 percent for p_i/Z_i = 5000 psia) and T must be Rankine not Fahrenheit.

## Failure modes

- Omitting Cov(a,b) from Var(-a/b). Because Cov(a,b) = -xbar*Var(b) < 0 and G_hat > 0, the omitted term is negative, so the defective estimator ALWAYS over-states the uncertainty in a depleting gas reservoir. Measured in-session: +36 percent on the OLS demo and +88 percent (1.5068 vs 0.8021) on York's dataset 3. It is conservative, so it will never trip an obvious test - it needs an explicit regression test against the closed form (s^2/b^2)[1/n + (G-xbar)^2/Sxx].
- Reporting a symmetric G +/- 1.96*SE when the Fieller discriminant g >= 1. The true confidence set is then unbounded, and a finite error bar is an outright false statement. In the low-SNR case measured in-session, 90.5 percent of the trials had an unbounded Fieller set while the delta interval happily printed a finite number with 78.7 percent coverage.
- Trusting a high R-squared as evidence that the reservoir is volumetric. Measured in-session on synthetic water-drive data: R-squared = 0.99993 over 40 post-inflection points with G over-estimated by +63 percent; with realistic gauge noise (13 quarterly surveys, sigma = 15 psia) R-squared = 0.9941 with +48 percent bias. Bruns et al. (1965) report the same phenomenon on real physics: apparent reserve of 990 Bscf against ~475 Bscf actual, an over-estimate of more than 100 percent, read at 63 percent depletion.
- Fitting only the 'nice straight' late-time segment. This is precisely the worst choice under water drive: the post-inflection segment is the flattest and the straightest, so it maximises both R-squared and the bias. Bruns et al. explicitly warn that the early curved portion 'should not be neglected' but regarded as an indication of possible water encroachment.
- Using an iid (pairs) bootstrap over pressure points when the gauge drifts. It destroys the temporal ordering, so the resampled series looks like white noise and the bootstrap SE collapses to the iid value. Measured in-session with n=48, AR(1) rho=0.9: iid bootstrap gave sd(G_hat) = 0.223 Bscf against a true sampling sd of 1.237 Bscf - a 5.5x understatement of the real uncertainty.
- Applying the jackknife (the NCSS/Linnet default for Deming SEs) under drift. The delete-one jackknife has exactly the same independence assumption as the iid bootstrap and fails the same way. Under drift it must be replaced by a delete-a-block jackknife.
- Defaulting Deming to lambda = 1. lambda is a ratio of variances in each axis's NATIVE units, so it is not scale-invariant: converting Gp from scf to Bscf changes lambda by 10^18. lambda = 1 on (psia, Bscf) is a physically meaningless statement about the relative precision of a pressure gauge and a production allocation.
- Passing psig instead of psia, or degrees F instead of Rankine. Both are silent: the fit still looks perfect. A psig-for-psia error is exactly a shared additive calibration bias of 14.696 psi.
- Feeding the York algorithm weights of zero (a point declared error-free in one axis). W_i has omega(X_i)+b^2*omega(Y_i)-2*b*r_i*alpha_i in the denominator; degenerate weights and r_i = +/-1 can make it vanish. Guard the denominator and reject |r_i| = 1 unless the caller explicitly asks for the Brooks/Wendt/Harre special case.
- Reporting G to more significant figures than the data support. At 10 percent depletion with 12 surveys and sigma = 25 psia the in-session SE(G) was 4.6 percent of G; three significant figures on G is already over-claiming.
- Silently accepting a non-converged York iteration. If the slope oscillates, the returned sigma_b (which is evaluated at the adjusted points, which depend on b) is meaningless.
- Ignoring the MSWD. York's S/(n-2) has expectation 1 under the assumed errors; a value much greater than 1 means the straight-line model is wrong or the assigned gauge errors are too small, and inflating sigma_a, sigma_b by sqrt(S/(n-2)) papers over a physical failure. York warns explicitly that this rescaling 'should not be applied mechanically'.

## Numerical pitfalls

- Catastrophic cancellation in the Deming slope. When lambda*q and u are close (which happens whenever the data are near-orthogonally scaled), the numerator (lambda*q - u) + sqrt((u - lambda*q)^2 + 4*lambda*p^2) subtracts two nearly equal quantities. Measured in-session: at lambda = 1e-12 the closed form returned 0.8616029 against the exact OLS answer 0.8616234 - only 5 correct figures. Fix: when (lambda*q - u) < 0, use the numerically stable conjugate form b1 = 2*p / [ (u - lambda*q) + sqrt((u - lambda*q)^2 + 4*lambda*p^2) ], which is algebraically identical and avoids the cancellation.
- Sxx and Sxy computed by the naive sum-of-squares-minus-square-of-sums shortcut lose precision badly when Gp is large and its spread is small - exactly the early-depletion case where precision matters most. Use the centred (two-pass) or Welford formulation.
- Scale disparity: p/Z is O(5000) psia and Gp may be O(1e11) scf. In the York W_i the term b^2*omega(Y_i) then spans many orders of magnitude. Work in Bscf (or Tscf) and psia, and document the unit contract; do not let the caller pass raw scf.
- The Fieller denominator (1 - g) -> 0 as the slope loses significance. Branch on g explicitly BEFORE dividing; do not rely on IEEE infinity to signal it, because the resulting interval silently flips orientation for g > 1.
- Deming b1 divides by 2*lambda*p with p = Sxy; York's b divides by sum(W_i*beta_i*U_i). Both can vanish for degenerate inputs. Guard with an explicit check and a named exception, not a NaN.
- York's W_i denominator omega(X_i) + b^2*omega(Y_i) - 2*b*r_i*alpha_i can go to zero or negative for |r_i| near 1 combined with a particular b. Validate |r_i| < 1 and assert the denominator is positive at every iteration.
- sigma_b^2 = 1/sum(W_i*u_i^2) uses the ADJUSTED points x_i = Xbar + beta_i, not the observed X_i. Using the observed points is the classical (pre-2004) LSE error and gives a different number - York et al. measured the difference at under 10 percent for nine real data sets, with two thirds under 1 percent, so a test with loose tolerance will NOT catch the mistake. Test against the tight published values instead.
- The iid-versus-block bootstrap difference is invisible to any test that generates iid data. The block-bootstrap test MUST generate an AR(1) or ramp error series, otherwise both estimators agree and the test passes vacuously (verified in-session: MBB at l=1 gave 0.2238 versus iid 0.2233 - identical, as expected).
- R-squared on a p/Z plot is computed against ybar of the FITTED SUBSET. Reporting R-squared from a different subset than the one fitted is a common and misleading slip; bind them together in the return object.
- A jackknife or leave-one-out loop over a York fit re-runs the whole iteration N times. For N = 50 surveys this is fine, but a naive nested bootstrap-of-jackknife is O(B*N) York fits - budget it or use the analytic sigmas.

## Implementation notes

- The API structure I recommend: a single function `fit_pz(Gp, pz, *, method, sigma_pz=None, sigma_gp=None, rho=None, lam=None)` that ALWAYS returns an object containing (a, b, Var_a, Var_b, Cov_ab, G_hat, Var_G, fieller_low, fieller_high, g_discriminant, mswd, n, depletion_fraction, method, converged). Cov_ab must be a first-class field, not an internal intermediate that is thrown away - that is the only way to prevent the bug this task is about.
- Use the closed form (s^2/b^2)*[1/n + (G-xbar)^2/Sxx] as the primary implementation of Var(G) for OLS, BUT also keep the long route (1/b^2)*[Var_a + G^2*Var_b + 2*G*Cov_ab] as an assertion in the tests: the two must be identical to machine precision. This catches the regression if someone 'tidies up' the code and deletes the covariance term.
- Always compute and return g = t^2 * Var(b) / b^2. The reporting rule I suggest: g < 0.01 may print a symmetric G +/- 1.96*SE; 0.01 <= g < 1 must print the asymmetric Fieller interval; g >= 1 must refuse to print a number and return 'G not identified at this confidence level' plus a one-sided bound.
- For York, provide TWO routes to SE(G) and compare them in the tests: (i) the delta method with cov(a,b) = -xbar*sigma_b^2, (ii) the axis swap (interchange X<->Y and omega(X)<->omega(Y), refit, take a and sigma_a). This session demonstrated that the two agree to 15 digits. Make this a permanent oracle.
- York weights: omega(X_i) = 1/sigma^2(Gp_i), omega(Y_i) = 1/sigma^2((p/Z)_i). Note that sigma(p/Z) is NOT sigma(p): if sigma(p) is known, propagate it through p/Z by including the sensitivity dZ/dp, and that is precisely the source of a non-zero correlation r_i when Z is computed from the same p. For Z from any correlation, d(p/Z)/dp = (1/Z)*(1 - (p/Z)*dZ/dp), so sigma(p/Z) = |d(p/Z)/dp| * sigma(p), and the x-y error correlation stays zero unless Gp and p share an allocation model.
- Never default lambda = 1 in Deming. Require lambda explicitly, or derive it from the sigma_Gp and sigma_pz supplied by the caller: lambda = sigma_Gp^2 / sigma_pz^2 in native units. Document in the docstring that lambda changes if the units change.
- Implement York with a bounded iteration (cap 200), relative tolerance 1e-14 on b, and return a `converged` flag. York himself mentions ~10 iterations typical, <50 for pathological data; this session converged in 9 iterations on York's dataset.
- Provide MSWD = S/(n-2) with S = sum(W_i*(Y_i - b*X_i - a)^2) as a mandatory output for York. MSWD >> 1 is an alarm about the physical model (possibly water drive or geopressure), NOT a reason to multiply sigma by sqrt(MSWD) automatically. If the repository provides that rescaling, make it explicitly opt-in and record in the output that rescaling was used.
- For the bootstrap: resample PAIRS (Gp_t, (p/Z)_t) in blocks over the time-ordered survey index, not over values. Provide MBB (Kuensch) and CBB; offer the stationary bootstrap as an option. Default block length: l = max(ceil(n^(1/3)), ceil(tau_int_hat)) with tau_int_hat = (1+rho1_hat)/(1-rho1_hat) from the lag-1 autocorrelation of the residuals - this is not a rule from the literature, so mark it in the docstring as a repository heuristic that combines the HHJ rate rule with a physical floor, and report both numbers.
- Always report the sensitivity curve SE(G) vs f. A function `se_g_vs_depletion(sigma, n, G, pz_i)` that plots (sigma*G/pz_i)*sqrt((1+12*(1-f/2)^2/f^2)/n) is the single chart that explains directly to a petroleum engineer why a G figure obtained early in production is not fit to be used for an investment decision.
- For demonstration (c), do not generate just one case. Sweep aquifer strength J and report a table (J, depletion, R^2, G_hat, bias percent) exactly as in this session's results, then attach Bruns et al. (1965) Fig. 10 as a positive control from the literature. Add a J = 0 control that must give 0.0 percent bias and R^2 = 1 - without that control, the demonstration proves nothing about the instrument.
- Store p as psia and T as Rankine throughout the internals; accept psig/degF only at an explicit, named conversion boundary. Add one test that feeds psig and confirms the result differs from psia in line with the predicted bias +14.696*G/(p_i/Z_i).
- PLUS: parts (a), (b), (e), (f) now all have closed forms validated numerically against sources genuinely retrieved this session (NCSS full output, York Table II, Bruns Fig. 10), plus two independent oracles for SE(G) that agree to 15 digits. An implementer can write the test suite straight from independent_checks without having to guess a single number.
- MINUS: three gaps I did not close. (1) I did not obtain an analytic standard error for Deming with known lambda in a verified closed form - NCSS uses the jackknife and I did not retrieve Linnet (1990/1993), so the analytic route is still empty (York covers this need in general, but if the repository wants a closed-form Deming SE, that requires a primary source). (2) I did not retrieve the explicit form of Politis & White (2004) Eq. (6)-(9) for automatic block length - only the correction constant D_SB = 2*g^2(0) from PPW (2009). (3) All the water-drive numbers in (c) come from my own synthetic generator with a simple Schilthuis aquifer; only the Bruns magnitude comes from the literature, and Bruns does not report R-squared at all - so the claim 'R^2 typically 0.99-0.9999' is a result of this session's simulation, not a published number.
- RECOMMENDATION: build the OLS + delta-method-with-Cov + Fieller route first, with the test suite from Check 3, 6, 7, 13, 14, 15 - that already covers the whole of requests (a) and (f) and is the most frequently used estimator. Only once that route is green, add Deming (test from NCSS Example 1) and then York (test from Table II dataset 3 plus the axis-swap oracle). Bootstrap and the water-drive demonstration last, since both depend on the core estimators already being correct. Before adding new features after that, dogfood first: run the estimator on one real field dataset and see whether the reported g, MSWD and depletion fraction genuinely move the decision.

## Open uncertainties

- I did NOT retrieve a closed-form analytic standard error for Deming regression with known lambda. NCSS states its SEs come from the jackknife, and it attributes the point estimates to Linnet K. (1990); I did not retrieve Linnet (1990) Statistics in Medicine 9:1463-1473 or Linnet (1993) Clinical Chemistry 39:424-432. If the repository wants an analytic Deming SE rather than a jackknife, that formula must be sourced from a primary reference before it is coded. Mark any such constant UNVERIFIED until then.
- I did NOT retrieve the explicit form of Politis & White (2004) Equations (6)-(9) - the actual automatic block-length estimator. I retrieved only the Patton/Politis/White (2009) correction, which tells me D_SB = 2*g^2(0) and D_SB_hat = 2*g_hat^2(0) but refers back to the 2004 paper for the rest. The corresponding D_CB, the flat-top lag-window bandwidth rule, and the multiplicative constants in b_opt are UNVERIFIED - needs the primary source (Econometric Reviews 23(1):53-70). Do not code an 'automatic' block length from memory.
- The Hall-Horowitz-Jing n^(1/3) statement is quoted from the published ABSTRACT, not the full text. The proportionality CONSTANT C in l_opt = C*n^(1/3) is not something I have, and HHJ's own empirical rule (the subsample cross-validation and its rescaling) I know only by description, not by retrieved formula. UNVERIFIED - needs the primary source.
- The Pearson-York benchmark data (the X, Y, omega(X), omega(Y) arrays) is Unverified — cited source not inspected: neither Pearson (1901) nor York (1966) was read for these arrays. It is strongly corroborated because it reproduces York's published a = 5.47991, b = -0.480533 and S/(n-2) = 1.483 exactly, but if the repository ships it as a test fixture it should carry a note that the array values themselves were not read from Pearson (1901) or York (1966).
- The Fieller (1954) citation is verified at metadata level only (title, journal, volume 16 issue 2, pages 175-185, 1954). The calibration/inverse-prediction closed form I give is the textbook specialisation, which I verified numerically in-session against brute-force set inversion, but I did NOT read Fieller's paper or a textbook page this session. The Draper & Smith and Graybill attributions are recalled, not retrieved.
- The 'typical R-squared' figures for the water-drive case (0.99 to 0.9999) come from MY synthetic generator with a simple Schilthuis steady-state aquifer and a constant-Z assumption, not from any publication. Bruns et al. (1965) confirm the BIAS magnitude (over 100 percent over-estimate) from real unsteady-state aquifer physics but they report no R-squared. Anyone quoting the R-squared number must attribute it to the repository's own simulation.
- I read the Bruns et al. (1965) PDF through OCR that was visibly imperfect (Eq. 1 in particular came out garbled). The Appendix A derivation (Eqs. A-1 to A-11), the Table 1 field conditions, the Fig. 10 reserve estimates (475 / 596 / 990 Bscf) and the Conclusions text were legible and I am confident in them; I am NOT confident in the exact typography of Eq. (1) or Eq. (3) as I transcribed them.
- The Deming lambda convention is a genuine trap. NCSS/Linnet use lambda = V(eps_x)/V(delta_y), and the objective SS = sum[(x-Xhat)^2 + lambda*(y-Yhat)^2]. Several other sources (and several software packages) use the reciprocal convention. I verified the NCSS convention numerically via its limiting cases, but the repository must pin its own convention in the API and test both limits explicitly rather than trusting any external reference.
- The 6.2x ratio for SE(G) at 10 percent versus 50 percent depletion assumes the SAME number of surveys and the SAME per-survey noise at both depletion levels. In reality a reservoir at 50 percent depletion will usually have more surveys, so the real-world contrast is larger. I did not model the realistic joint scaling.
- Whether the residual mean square s^2 is the right noise estimate is itself model-dependent: under water drive the residuals are dominated by MODEL error (curvature), not measurement error, so s^2 is inflated and SE(G) will look large while G_hat is biased. A large SE does not protect against the bias. I have not quantified how badly s^2 misrepresents the gauge noise in that case.
- Two-phase Z, condensate dropout, formation and connate-water compressibility in geopressured reservoirs, and residual gas trapped behind the water front are all real effects that put curvature into a p/Z plot and are NOT covered by anything here. Each is a separate literature.

## Independent check values

| Check | Inputs | Expected | Source | Retrieved or recalled |
|---|---|---|---|---|
| Deming closed form (slope and intercept) against a fully published worked example with printed full-precision output | `x = [7, 8.3, 10.5, 9, 5.1, 8.2, 10.2, 10.3, 7.1, 5.9]; y = [7.9, 8.2, 9.6, 9.0, 6.5, 7.3, 10.2, 10.6, 6.3, 5.2]; V(X error) = 0.032, V(Y error) = 0.008, lambda = 4.0` | `slope = 1.00119422781949, intercept = -0.0897448990070444 (NCSS prints these to full precision in the 'Estimated Model' block)` | NCSS Statistical Software, Chapter 303 'Deming Regression', Example 1 (DemingReg1 dataset) | RETRIEVED this session (PDF text extracted) and REPRODUCED in-session: my closed form gave slope 1.0011942278194905 and intercept -0.08974489900704263 |
| Deming jackknife standard errors against the same published example | `same as above, jackknife with N-2 = 8 degrees of freedom` | `SE(slope) = 0.18718, SE(intercept) = 1.72199; 95 percent CI for slope [0.56956, 1.43283]` | NCSS Chapter 303, Example 1 'Regression Coefficient Estimation' report | RETRIEVED and REPRODUCED in-session: 0.18717705279939656 and 1.7219874128187012 |
| Deming limiting cases (essential unit tests) | `same NCSS data; lambda -> 0 and lambda -> infinity` | `lambda -> 0 must return the OLS slope Sxy/Sxx = 0.8616233847697906; lambda -> infinity must return the x-on-y slope Syy/Sxy = 1.041642399534071; lambda = 1 must return the orthogonal/major-axis slope` | Algebraic limits of the NCSS/Linnet formula | Computed in-session: lambda = 1e-12 gave 0.8616029 vs OLS 0.8616234 (only 5 figures - the cancellation is real and must be handled), lambda = 1e12 gave 1.0416424 vs 1.0416424 (exact) |
| York (2004) full algorithm against York's own published Monte Carlo table | `Pearson (1901) data with York (1966) weights, zero error correlations: X = [0.0,0.9,1.8,2.6,3.3,4.4,5.2,6.1,6.5,7.4]; Y = [5.9,5.4,4.4,4.6,3.5,3.7,2.8,2.8,2.4,1.5]; omega(X) = [1000,1000,500,800,200,80,60,20,1.8,1.0]; omega(Y) = [1.0,1.8,4,8,20,20,70,70,100,500]` | `York Table II data set 3: a = 5.47991, b = -0.480533, S/(n-2) = 1.483, Monte Carlo sigma_a_hat = 0.295713 with Delta_a = -0.251151 percent, Monte Carlo sigma_b_hat = 0.058256 with Delta_b = -0.464447 percent. Since Delta = 100*(sigma_analytic - sigma_MC)/sigma_MC, the ANALYTIC values implied by the table are sigma_a = 0.295713*(1-0.00251151) = 0.2949704 and sigma_b = 0.058256*(1-0.00464447) = 0.0579855.` | York, Evensen, Lopez Martinez, De Basabe Delgado (2004), Am. J. Phys. 72(3):367-375, Table II row 3 | Table II values RETRIEVED this session from the full-text PDF. The DATA ITSELF (X, Y, weights) is Unverified — cited source not inspected, NOT retrieved - but it is confirmed by the fact that it reproduces York's published a, b and MSWD exactly. My implementation gave a = 5.4799102240328645, b = -0.48053340744620204, S/(n-2) = 1.4832941492576808, sigma_a = 0.29497073549310865, sigma_b = 0.05798500900077447. All six match. |
| Two independent routes to SE(x-intercept) must agree exactly (the repository's primary oracle for the delta-method code path) | `York dataset 3 above` | `Route A: fit y on x, then G_hat = -a/b and Var(G) = (1/b^2)[sigma_a^2 + G^2*sigma_b^2 + 2*G*cov(a,b)] with cov(a,b) = -xbar*sigma_b^2. Route B (York's own recommendation): swap the axes and their weights, refit; the y-intercept of the swapped fit IS G and its sigma_a IS SE(G).` | York et al. (2004) Sec. III (axis interchange) plus the delta method | Computed in-session: Route A gave SE = 0.8020969448329499, Route B gave 0.8020969448329495; G_hat agreed at 11.403806975993373 vs 11.403806975993376. The covariance-omitted version gave 1.5067784578508985, i.e. +87.9 percent. |
| Delta-method Var(x-intercept) against direct Monte Carlo | `12 equally spaced Gp in [0, 50] Bscf, true line p/Z = 4705.9 - 47.059*Gp (so G = 100 Bscf), iid Normal noise sigma = 25 psia on p/Z, 200000 trials` | `Monte Carlo sd of the x-intercept should match (sigma/|b|)*sqrt(1/n + (G-xbar)^2/Sxx)` | Self-constructed, but this is the definitional check of the estimator | Computed in-session: closed form 0.7488862593876134, Monte Carlo 0.748218650358047 (0.09 percent apart). The covariance-omitted version gave 1.0190393663179351 (+36 percent). |
| Fieller closed form against brute-force inversion of the quadratic set | `Same synthetic line, f = 0.50 / 0.10 / 0.06 depletion, n = 12, sigma = 25 psia, alpha = 0.05` | `The closed-form x_{L,U} must coincide with the set {x : (a+bx)^2 <= t^2 s^2 [1/n + (x-xbar)^2/Sxx]} found by evaluating on a fine grid` | Fieller (1954) applied to the OLS calibration problem | Computed in-session: f=0.50 closed form [98.95, 102.18] vs brute force [98.95, 102.17]; f=0.10 [90.63, 109.29] vs [90.63, 109.29]; f=0.06 [85.14, 109.00] vs [85.14, 109.00]. Exact agreement. |
| Confidence-interval COVERAGE of delta vs Fieller across depletion and signal-to-noise | `n = 12, sigma = 25 psia, f in {0.50, 0.30, 0.15, 0.10, 0.05}, 20000 trials each; then a low-SNR battery (n=8 f=0.05 sigma=300; n=8 f=0.04 sigma=400; n=10 f=0.08 sigma=250)` | `Nominal 95 percent` | Self-constructed coverage study | Computed in-session. High SNR: delta 0.949/0.950/0.952/0.950/0.949 and Fieller 0.949/0.950/0.952/0.951/0.953 - both fine. Low SNR: delta 0.787 / 0.676 / 0.880, Fieller 0.972 / 0.964 / 0.975 with 90.5 / 93.2 / 72.8 percent of Fieller sets UNBOUNDED. This is the exact boundary where a repository must switch estimators. |
| SE(G) at 10 percent versus 50 percent depletion, same sigma and same n (the quantitative answer to part f) | `12 equally spaced surveys over [0, f*G], G = 100 Bscf, p_i/Z_i = 4705.9 psia, sigma = 25 psia on p/Z` | `SE(G) ~= (sigma*G/(p_i/Z_i)) * sqrt((1 + 12*(1-f/2)^2/f^2)/n); ratio(10 percent : 50 percent) ~= 6.2` | Derived closed form; ratio computed exactly | Computed in-session: f=0.10 gives SE(G) = 4.645 Bscf (4.6 percent of G); f=0.50 gives 0.749 Bscf (0.7 percent of G); exact ratio 6.2025. Uniform-spread approximation gave 5.049 and 0.811, ratio 6.22. |
| Water-drive demonstration: high R-squared with a badly biased G (part c) | `Synthetic Schilthuis steady-state aquifer coupled to the water-drive p/Z balance. p_i = 4000 psia, Z = 0.85 constant, T = 640 R, G = 100 Bscf, q = 25 MMscf/d, 30-day steps, HCPV = G*Bgi. Observe the first 60 percent of the history, then fit an OLS straight line to the LAST HALF of the observed points (the post-inflection, straightest-looking segment) - which is what a practitioner would actually do.` | `R-squared close to 1 while G is materially over-estimated` | Self-constructed generator from the Bruns et al. (1965) Appendix A balance | Computed in-session. J=0 (volumetric control): R^2 = 1.00000, G_hat = 100.0, bias 0.0 percent. J=10: R^2 = 0.99999, +6.2 percent. J=30: R^2 = 0.99997, +22.5 percent. J=60: R^2 = 0.99993, +62.7 percent. J=100: R^2 = 0.99633, +178.2 percent. J=150: R^2 = 0.97183, +570 percent. With realistic gauge noise added (13 quarterly surveys, sigma = 15 psia): J=0 gives R^2 = 0.99905 with +0.3 percent, J=60 gives R^2 = 0.99410 with +48.2 percent, J=150 gives R^2 = 0.88894 with +222.9 percent. HEADLINE: expect R-squared in the 0.99 to 0.9999 band for a water-drive reservoir whose G is over-estimated by 20-60 percent. |
| Water-drive bias magnitude against a RETRIEVED primary source (the positive control that the demonstration is physically realistic, not a strawman) | `Bruns, Fetkovich & Meitzen (1965) Fig. 10: van Everdingen-Hurst radial finite aquifer, three aquifer sizes, reserve estimated by straight-line extrapolation at Gp = 300 Bscf` | `Estimated reserve = 475 Bscf for Ra/Rr = 1.5, 596 Bscf for Ra/Rr = 5.0, 990 Bscf for Ra/Rr = 10.0. Paper's conclusion: 'the error increases from a negligible amount to an estimate of over 100 per cent of the actual initial gas in place. This estimate would be made after 65 per cent of the initial gas in place is produced.'` | Bruns, J.R., Fetkovich, M.J., Meitzen, V.C. (1965), 'The Effect of Water Influx on p/z-Cumulative Gas Production Curves', JPT March 1965, 287-291 (SPE-898-PA), Fig. 10 and Conclusions | RETRIEVED this session (full-text PDF). Cross-checked in-session: the paper's Table 1 field conditions (2500 acres, 100 ft, phi 0.25, Swc 0.30, p_i 5000 psia, T 250 F) give a volumetric GIIP of 475-500 Bscf depending on Z_i (474.7 at Z=1.00, 489.4 at Z=0.97, 499.7 at Z=0.95), which brackets the paper's own weak-aquifer estimate of 475 Bscf. So 990/475 = 208 percent, i.e. over-estimate of 108 percent - exactly the 'over 100 per cent' the Conclusions state, and 300/475 = 63 percent depletion matches their 'after 65 per cent'. |
| Propagation of each error class into G (part e) | `12 surveys over f = 0.4 of G = 100 Bscf, p_i/Z_i = 4705.9 psia; four error mechanisms each with the same 25 psia marginal scale; 40000 trials; repeated at n = 12/48/200 and f = 0.4/0.7` | `iid noise shrinks like 1/sqrt(n) and with depletion; shared additive bias is a constant floor sigma_c/|b| independent of n and f; shared multiplicative gain is exactly zero; drift sits between and does NOT shrink with n` | Self-constructed, checked against the closed-form algebra | Computed in-session. iid gauge noise: sd(G_hat) = 0.984 (n=12,f=.4), 0.528 (n=48), 0.480 (f=.7), 0.263 (n=200) - shrinks as expected. Shared additive bias: 0.531, 0.534, 0.533, 0.531 - FLAT in both n and f, and equal to the predicted sigma_c/|b| = 25/47.059 = 0.5312. Shared multiplicative gain: 0.0000 exactly at every setting, as the algebra predicts. Linear ramp drift: 1.328, 1.330, 1.326 (flat in n) and 0.758 at f = 0.7 - it shrinks with DEPLETION but not with SAMPLE SIZE. |
| Allocation error in Gp (x-axis) propagation | `Same line; additive Gp offset with sd 1.0 Bscf, and multiplicative Gp gain with sd 2 percent; 40000 trials` | `Additive Gp offset shifts G one-for-one; multiplicative gain scales G proportionally` | Self-constructed | Computed in-session: additive sd 1.0 Bscf -> sd(G_hat) = 0.9985 Bscf (1:1 confirmed); multiplicative 2 percent -> sd(G_hat) = 2.0063 Bscf on G = 100, i.e. exactly 2 percent (confirmed) |
| iid bootstrap versus moving-block bootstrap under a drifting gauge (part d) | `n = 48 surveys over f = 0.5, AR(1) pressure error with rho = 0.9 and marginal sd 25 psia (so tau_int = (1+rho)/(1-rho) = 19 surveys); 4000 bootstrap resamples; true sampling sd from 20000 independent regenerations` | `iid pairs bootstrap should badly understate the true sd; MBB should improve monotonically with block length until l is comparable to tau_int` | Self-constructed, structured on Kuensch (1989) MBB | Computed in-session. TRUE sampling sd(G_hat) = 1.2369 Bscf. iid pairs bootstrap: 0.2233 (18 percent of truth - a 5.5x understatement). MBB l=1: 0.2238 (identical to iid, as it must be). MBB l=3 (~n^(1/3)=3.63): 0.3912 (32 percent). MBB l=6: 0.5560 (45 percent). MBB l=12: 1.0124 (82 percent). Conclusion: at n=48 with strong drift, even l chosen well above n^(1/3) still understates; the n^(1/3) rate rule is not enough at these sample sizes. |

## Adversarial review

### Corrections

**validity_ranges (last bullet) and implementation_notes (psig test spec): sign of the psig-for-psia bias in G** — severity HIGH - the card tells the implementer to encode the wrong sign as a regression test, so the defect would be locked in by a passing test, confidence certain - reproduced numerically and derived in closed form

- Claimed: passing psig instead of psia 'biases G by +14.7*G/(p_i/Z_i), i.e. ~0.3 percent for p_i/Z_i = 5000 psia'; implementation_notes instructs the implementer to write a test asserting 'bias +14.696*G/(p_i/Z_i)'
- Correct: The bias is NEGATIVE: -14.696*G/(p_i/Z_i). psig = psia - 14.696, so the shared additive offset is c = -14.696, and the card's own (correct) general rule G_hat -> G_hat + c*G/(p_i/Z_i) then gives an UNDER-estimate. Feeding psig makes a reservoir look smaller, not larger.
- Evidence: Re-ran the card's own synthetic line (12 surveys over [0,50] Bscf, G=100, p_i/Z_i=4705.9, noise-free). p in psia: G_hat = 100.0000. Same data fed as psig (y - 14.696): G_hat = 99.6877, shift = -0.3123 Bscf. Card predicts +0.3123. Magnitude right, sign inverted. Algebra: with Z=1, y = A - 14.7 - (A/G)Gp, x-intercept = G(1 - 14.7/A) < G.

**Fieller block: stated geometry of the confidence set when g >= 1** — severity HIGH - the card's recommended API returns scalar fieller_low/fieller_high, which structurally cannot represent the case that dominates every low-SNR fit, confidence certain - derived, brute-forced, and confirmed against a retrieved primary methodological source

- Claimed: 'If g >= 1 the set is UNBOUNDED (a half-line or the whole line): G is not identified at that confidence level and no finite error bar should be printed.'
- Correct: Three cases, not two. Let D = G_hat - xbar, k = t^2*s^2/(n*b^2), Delta = g*D^2 + (1-g)*k (this is exactly the quantity under the card's own square root, times t^2*s^2/b^2). (i) g < 1: bounded interval (card correct). (ii) g > 1 and Delta > 0: the set is the COMPLEMENT of the bounded interval whose endpoints are xbar + (D -/+ sqrt(Delta))/(1-g) - i.e. the union of TWO disjoint half-lines, with G_hat lying OUTSIDE the excluded middle. (iii) g > 1 and Delta <= 0: the whole real line. A single half-line occurs only at exactly g = 1 (measure zero). The card's formula, applied blindly at g > 1, returns the endpoints of the EXCLUDED interval while labelling them x_L and x_U.
- Evidence: Brute-force inversion of the card's own defining set {x : (a+bx)^2 <= t^2 s^2 [1/n + (x-xbar)^2/Sxx]} on a g=3.548 realisation (n=8, f=0.05, sigma=300) returns TWO contiguous pieces, (-4038.69,-38.70) and (15.08,4015.08), whose inner edges are exactly the card's lo=-38.69 / hi=15.08; G_hat=38.96 is outside (lo,hi). Over 20,000 trials at the card's own low-SNR setting, 90.4% of trials had g>=1 and 100% of those were the exclusive/two-half-line case - the whole-line case never occurred. Independently sourced: von Luxburg & Franz, 'A Geometric Approach to Confidence Sets for Ratios: Fieller's Theorem, Generalizations, and Bootstrap' (arXiv 0711.0198, full text retrieved this session): 'If Delta > 0, then S is the union of two disjoint half-lines. If Delta <= 0, then S = R.'

**independent_checks #8: reported Fieller coverage in the low-SNR battery** — severity MEDIUM-HIGH - these numbers would be pasted into the repo as validated coverage, confidence high - the three-way numeric fingerprint is unambiguous

- Claimed: 'Fieller 0.972 / 0.964 / 0.975' at (n=8,f=0.05,sigma=300), (n=8,f=0.04,sigma=400), (n=10,f=0.08,sigma=250)
- Correct: Exact Fieller coverage is nominal 0.95 at all three settings - it is an exact method, so anything systematically above 0.95 is a bug, not conservatism. Correct set handling gives 0.9512 / 0.9513 / 0.9507. The card's numbers are what you get if every g>=1 case is scored as 'whole line, therefore always covers': that naive handling reproduces 0.9703 / 0.9661 / 0.9739, matching the card's 0.972 / 0.964 / 0.975 to Monte Carlo error.
- Evidence: 20,000 trials per setting, same generator as the card. My unbounded fractions 0.906 / 0.935 / 0.734 match the card's stated 90.5 / 93.2 / 72.8 percent, confirming I replicated its harness faithfully; the coverage then splits cleanly into EXACT 0.9512/0.9513/0.9507 vs NAIVE 0.9703/0.9661/0.9739. The card's reported numbers track the naive column, so its in-session Fieller code carried the defect in correction #2. The qualitative conclusion (Fieller >> delta at low SNR: 0.951 vs 0.787) survives; the specific numbers do not.

**independent_checks #7: 'Fieller closed form against brute-force inversion ... Exact agreement'** — severity MEDIUM - a check listed as independent evidence for a code path it does not reach, confidence certain

- Claimed: Presented as validation of the Fieller implementation, at f = 0.50 / 0.10 / 0.06 with n=12, sigma=25
- Correct: That check never exercised the g>=1 branch and therefore cannot support the branch it is cited for. Over 2,000 trials per setting the maximum g observed was 0.0015 (f=0.50), 0.0397 (f=0.10) and 0.1275 (f=0.06); P(g>=1) = 0 everywhere. It validates the bounded branch only - which is precisely why the exclusive-region defect survived in-session.
- Evidence: Simulated g distribution at the card's stated inputs (n=12, sigma=25, t(0.975,10)). Median g = 0.00044 / 0.01105 / 0.03071, max g = 0.00154 / 0.03968 / 0.12753.

**uncertainties #1 and implementation_notes MINUS (1): 'no closed-form analytic standard error for Deming with known lambda'** — severity MEDIUM - the card's stated gap is closable today from a source already in hand, confidence certain - reproduced to machine precision

- Claimed: 'I did NOT retrieve a closed-form analytic standard error for Deming regression with known lambda ... the analytic path is still empty ... that formula must be sourced from a primary reference before it is coded.'
- Correct: Not empty. Deming with known lambda is exactly the York estimator with constant weights omega(X_i) = 1/sigma_x^2, omega(Y_i) = 1/sigma_y^2, r_i = 0. York (2004) Eqs. (13c)/(13d) - which the card already has full text for - therefore supply the analytic Deming standard errors from a primary source, with no need for Linnet. This also yields a free cross-estimator oracle (closed form vs iterative) that the card does not propose.
- Evidence: Ran the York iteration on the NCSS Example 1 data with omega(X)=1/0.032, omega(Y)=1/0.008 (lambda=4): slope = 1.0011942278194903, intercept = -0.08974489900704263, against NCSS's published 1.00119422781949 / -0.0897448990070444. Agreement to 16 significant figures on the slope.

**Deming SE: the card's two 'verified' standard errors are mutually inconsistent by 5x and this is not flagged** — severity MEDIUM - an implementer given both oracles will assume they should agree and will chase a non-bug, or will ship whichever is smaller, confidence certain

- Claimed: NCSS jackknife SE(slope)=0.18718 and SE(intercept)=1.72199 are presented as the verified Deming SE oracle; York sigma_a/sigma_b are presented as the general EIV SE. Both are treated as interchangeable routes to an SE.
- Correct: They answer different questions and must not be swapped. On the card's own NCSS Example 1 dataset: York analytic sigma_b = 0.03761 vs NCSS jackknife 0.18718 - a factor of 5.0. The reason is that the MSWD there is 17.36, i.e. the assigned error variances (0.032, 0.008) are roughly 17x too small for the observed scatter. York's analytic sigma trusts the assigned variances; the jackknife estimates scatter from the data. Even sqrt(MSWD)-rescaling York (0.1567) does not recover the jackknife value.
- Evidence: Computed in-session on x,y = NCSS DemingReg1 with constant weights: sigma_b = 0.037614, sigma_a = 0.313390, MSWD = S/(n-2) = 17.3624; jackknife reproduced at 0.18717705 / 1.72198741. Ratio 0.18718/0.03761 = 4.98.

**constants: D_CB and the Politis-White automatic block-length equations listed as unverified** — severity MEDIUM - not an error in the card, but it leaves buildable, fully-sourced functionality on the table and would push the implementer to a hand-rolled heuristic, confidence certain - both papers retrieved in full text

- Claimed: uncertainties #2: 'the explicit form of Politis & White (2004) Equations (6)-(9) ... the corresponding D_CB, the flat-top lag-window bandwidth rule, and the multiplicative constants in b_opt are UNVERIFIED ... Do not code an automatic block length from memory.'
- Correct: All of it is retrievable and I retrieved it. PW2004 Eq. (6): b_opt,SB = (2G^2/D_SB)^(1/3) N^(1/3). Eq. (9): b_hat_opt,SB = (2*Ghat^2/Dhat_SB)^(1/3) N^(1/3). Eq. (8): Ghat = sum_{k=-M}^{M} lambda(k/M)*|k|*Rhat(k), with the flat-top lag window lambda(t) = 1 for |t| in [0,1/2], 2(1-|t|) for |t| in [1/2,1], 0 otherwise, and Rhat(k) = N^-1 sum (X_i - Xbar)(X_{i+|k|} - Xbar). Eq. (11): b_opt,CB = [(2G^2/D_CB)^(1/3) N^(1/3)] (closest integer). Eq. (13): Dhat_CB = (4/3)*ghat^2(0) - and PPW (2009) corrects ONLY D_SB, so this stands uncorrected. Bandwidth rule: M = 2*mhat, where mhat is the smallest lag after which the correlogram is negligible. The card's D_SB = 2g^2(0) and Dhat_SB = 2ghat^2(0) are CONFIRMED verbatim.
- Evidence: Full text of Politis & White (2004), Econometric Reviews 23(1):53-70, retrieved and text-extracted this session from https://public.econ.duke.edu/~ap172/Politis_White_2004.pdf (Secs. 3.2-3.3, Eqs. 6-14). PPW (2009) correction items 1-5 read verbatim: 'The correct value for the variance constant D_SB ... is D_SB = 2g^2(0)'; 'Equation (8) ... should be corrected as follows: Dhat_SB = 2*ghat^2(0)'; 'ARE_CB/SB := (2/3)^(2/3) = 0.7631428'. Consistency cross-check: D_CB/D_SB = (4/3)/2 = 2/3, and ARE = (D_CB/D_SB)^(2/3) = (2/3)^(2/3) = 0.7631428 - the two constants confirm each other.

**implementation_notes vs validity_ranges: the g threshold for printing a symmetric interval** — severity LOW - but it is the single most load-bearing branch in the reporting logic, confidence certain (the contradiction), medium (my suggested derivation is a rule of thumb, not sourced)

- Claimed: validity_ranges: 'refuse to print a symmetric +/- interval when g > ~0.05'. implementation_notes: 'g < 0.01 boleh print G +/- 1.96*SE simetris; 0.01 <= g < 1 wajib print interval Fieller'.
- Correct: Pick one. 0.01 and 0.05 differ by a factor of 5 in the variance-inflation tolerance they imply, and the card gives no basis for either. A defensible rule derived from the geometry: the Fieller interval's half-width exceeds the delta half-width by roughly 1/(1-g), so g < 0.01 buys agreement to ~1%, g < 0.05 only to ~5%. State the tolerance you are targeting and derive the threshold from it.
- Evidence: Internal contradiction between two fields of the same card; no source cited for either number.

**York block, assumptions: statement of the special cases** — severity LOW, confidence high

- Claimed: 'York's special cases: r_i = 0 and W_i = 1 gives major-axis; r_i = 0 and W_i = omega(Y_i) gives weighted y-on-x OLS'
- Correct: W_i is a derived quantity, not an input that can be set. The conditions are on the input weights: r_i = 0 with omega(X_i) = omega(Y_i) = const gives major-axis (orthogonal) regression; omega(X_i) -> infinity (x error-free) with r_i = 0 gives weighted y-on-x OLS, which is what makes W_i reduce to omega(Y_i). Phrasing the condition on W_i inverts cause and effect and will mislead anyone writing the special-case unit tests.
- Evidence: W_i = omega(X_i)*omega(Y_i)/(omega(X_i) + b^2*omega(Y_i) - 2*b*r_i*alpha_i) is a function of the inputs and of the current b; setting it directly is not an available operation in the algorithm the card itself specifies.

**Water-drive block, symbols: units of Bw** — severity LOW - flag it in the API, do not just document it, confidence high

- Claimed: Bw in 'rcf/STB (consistent with Wp)', alongside Bg in 'rcf/scf'
- Correct: Self-consistent but a trap worth naming. Bw is conventionally quoted in rb/STB with a value near 1.0; in rcf/STB the same fluid has a value near 5.615. Any implementation that accepts a literature Bw value (~1.0) into a slot documented as rcf/STB introduces a silent 5.615x error in the water term.
- Evidence: 1 bbl = 5.615 ft^3 exactly by the conventions this card already uses (it derives 0.0050365 rb/scf = 0.028280/5.615).

**validity_ranges: York iteration count on dataset 3** — severity LOW, confidence certain

- Claimed: 'York's iterative scheme converged in 9 iterations on York's own dataset 3 in-session'
- Correct: Iteration count is not a property of the data, it is a property of the tolerance and the initialisation. With OLS initialisation and a relative tolerance of 1e-15 on b I get 11 iterations on the same data. Do not encode a specific iteration count as a test assertion.
- Evidence: Reproduced York dataset 3 (a=5.479910224032864, b=-0.4805334074462021 - matching the card exactly) in 11 iterations at rtol 1e-15.

### Left unverified

- Bruns, Fetkovich & Meitzen (1965) JPT 287-291, SPE-898-PA - I could NOT retrieve this paper this session (OnePetro is paywalled). Every quantitative claim attributed to it remains single-sourced on the other engineer's OCR of a PDF they themselves describe as 'visibly imperfect': the Fig. 10 reserve estimates 475 / 596 / 990 Bscf, the Table 1 field conditions, the Appendix A equation numbering (A-1 to A-11), and the quoted Conclusions text ('over 100 per cent', 'after 65 per cent'). This is the card's only petroleum-engineering primary source and the entire positive control for part (c) rests on it. What I CAN confirm is internal: the volumetric GIIP arithmetic from the stated Table 1 conditions is self-consistent (2500 acres, 100 ft, phi=0.25, Swc=0.30, p_i=5000 psia, T=250F=709.67R gives 474.8 / 489.5 / 499.8 Bscf at Z_i = 1.00 / 0.97 / 0.95, versus the card's 474.7 / 489.4 / 499.7), and the algebra G_apparent = G_real + K_e*S(p,t)/(Bg - Bgi) follows correctly from the stated material balance. Neither confirms what the paper actually prints. REQUIRE independent re-retrieval before any of these numbers ships.
- Fieller, E.C. (1954) JRSS-B 16(2):175-185 - still metadata only; neither the card nor I opened it. The closed form is now corroborated independently by von Luxburg & Franz (arXiv 0711.0198, retrieved in full text this session), which I used to confirm the three-case classification, but that is a 2009 methodological paper, not Fieller.
- Hall, Horowitz & Jing (1995) Biometrika 82(3):561-574 - abstract only, as the card states. The n^(1/3), n^(1/4), n^(1/5) rate exponents are quoted from the abstract; the proportionality constant C in l_opt = C*n^(1/3) and the subsample cross-validation/rescaling rule remain unretrieved. NOTE: the constant is no longer needed for the stationary and circular block bootstrap, because Politis & White (2004) Eqs. (6), (9), (11), (14) - now retrieved in full - give it explicitly for those two schemes. It is still missing for the moving-block bootstrap the card actually recommends as the default.
- Linnet, K. (1990) Stat. Med. 9:1463-1473 and Linnet, K. (1993) Clin. Chem. 39:424-432 - not retrieved by the card, not retrieved by me. NCSS Chapter 303 remains vendor documentation, i.e. a secondary source for the Deming derivation. (Superseded in practical importance by correction #5: York 2004 supplies the analytic SE from a primary source.)
- CLSI EP09-A3 Appendix H - the N-2 degrees-of-freedom convention is known only through NCSS's citation of it. I confirmed only that N-2 is internally consistent with NCSS's own printed CI: t(0.975, 8) = 2.306004 times SE 0.18717705 reproduces [0.5695632, 1.4328253] against the published [0.56956, 1.43283]. That shows NCSS used N-2; it does not show CLSI specifies it.
- Draper & Smith (1998) and Graybill - recalled, not retrieved, by either of us. Every OLS formula attributed to them I re-derived symbolically and confirmed numerically, so the mathematics is not in doubt; the attribution is.
- Kuensch (1989) Ann. Statist. 17(3):1217-1241 - not retrieved. The MBB scheme as described is standard and behaves correctly (MBB at l=1 must reduce exactly to the iid bootstrap), but the citation is uncorroborated.
- The Pearson-York benchmark arrays (X, Y, omega(X), omega(Y)) - Unverified — cited source not inspected; stated by the card, not read from Pearson (1901) or York (1966), and I did not retrieve them either. Corroboration is strong but indirect: these arrays reproduce five independently published quantities (a = 5.47991, b = -0.480533, MSWD = 1.483, and the back-computed sigma_a = 0.2949704, sigma_b = 0.0579855) to 6 significant figures. Ship with the provenance note the card recommends.
- York et al.'s claim that using observed rather than adjusted points changes sigma_b by 'under 10 percent for nine real data sets, with two thirds under 1 percent' - not verified. On dataset 3 I measure the effect directly: sigma_b goes from 0.0579850 to 0.0583021, i.e. 0.55%, consistent with the claim but a single data point.
- York's suggested convergence tolerance of '1 part in 1e15' and the '~10 iterations typical, <50 for pathological sets' guidance - not verified against the retrieved text by me.
- The water-drive R-squared band (0.99 to 0.9999 with G biased +20 to +60 percent), the full aquifer-strength sweep (J = 0/10/30/60/100/150), and the gauge-noise variants - entirely from the other engineer's own synthetic Schilthuis generator. The card is honest about this. I did not re-run it. The R-squared numbers are a property of that generator's parameterisation, not a published result, and must never be quoted as literature.
- All moving-block-bootstrap recovery percentages (true sd 1.2369; iid 0.2233; l=1 0.2238; l=3 0.3912; l=6 0.5560; l=12 1.0124) - self-generated, not re-run by me.
- The delta-method coverage figures in the high-SNR battery (0.949/0.950/0.952/0.950/0.949) - not re-run by me, though I did faithfully replicate the low-SNR harness (my unbounded fractions 0.906/0.935/0.734 match the card's 90.5/93.2/72.8 percent), which makes the generator description trustworthy.
- Standard-condition constants p_sc = 14.696 psia and T_sc = 519.67 R, and the jurisdictional variants (14.65 Texas RRC, 14.73 gas contracts, 15.025 Louisiana) - recalled by the card, not retrieved by either of us. The DERIVED constants are exact given them: 14.696/519.67 = 0.02827948505782516 rcf/scf and /5.615 = 0.005036417641642949 rb/scf, both confirmed arithmetically this session.

### Missing before implementation

- A Fieller RETURN TYPE that can express all three cases. The card's proposed API returns scalar fieller_low / fieller_high, which structurally cannot represent the exclusive case (union of two disjoint half-lines) that occurs in 73-94 percent of low-SNR fits. Required shape: a tagged result - kind in {BOUNDED, EXCLUSIVE, WHOLE_LINE} plus (lo, hi) whose meaning depends on kind (for EXCLUSIVE, (lo,hi) is the EXCLUDED middle and the set is its complement). Branch on g and on Delta = g*(G_hat-xbar)^2 + (1-g)*t^2*s^2/(n*b^2) BEFORE dividing by (1-g). Never return two floats a caller can mistake for an interval.
- The correct psig test. Rewrite the card's spec to assert G_hat_psig - G_hat_psia = -14.696*G/(p_i/Z_i) (negative), and assert the sign, not just the magnitude - a magnitude-only assertion passes under the card's inverted claim.
- The full Politis-White automatic block-length estimator, now sourced and quotable: b_hat_opt,SB = (2*Ghat^2/Dhat_SB)^(1/3) * N^(1/3) with Dhat_SB = 2*ghat^2(0) (PPW 2009 correction), and b_hat_opt,CB = [(2*Ghat^2/Dhat_CB)^(1/3) * N^(1/3)] with Dhat_CB = (4/3)*ghat^2(0) (PW 2004 Eq. 13, NOT corrected by PPW 2009). Ghat = sum_{k=-M}^{M} lambda(k/M)*|k|*Rhat(k); ghat(w) = sum_{k=-M}^{M} lambda(k/M)*Rhat(k)*cos(wk); flat-top window lambda(t) = 1 on [0,1/2], 2(1-|t|) on [1/2,1], 0 beyond; bandwidth M = 2*mhat with mhat the smallest lag beyond which the correlogram is insignificant. This replaces the card's admitted 'repo heuristic' for the two schemes it covers.
- The analytic Deming standard error via York with constant weights (omega_X = 1/sigma_x^2, omega_Y = 1/sigma_y^2, r = 0), together with an explicit doc note that it is NOT interchangeable with the NCSS jackknife SE and that the two differ by 5x on NCSS Example 1 because MSWD = 17.36 there. Return MSWD for Deming too, not only for York - it is the diagnostic that tells the caller which SE is meaningful.
- Gp is a CUMULATIVE quantity, so its measurement errors are a partial sum of per-period allocation errors - a random walk, not iid. The card's error taxonomy (cases D and E) treats x-errors as a single additive offset or a single multiplicative gain, and its Deming/York blocks assume errors independent between points. Neither covers the structural case: an allocation error in month t contaminates Gp at every later survey, giving a strongly positively autocorrelated, heteroscedastic, monotonically growing x-error. This breaks constant-lambda, breaks York's between-point independence, and is not stationary, so it also undermines the block bootstrap's own premise. Nothing in the card addresses it and it is arguably the dominant real-world EIV structure for this problem.
- A Z-factor model and its derivative. implementation_notes correctly requires sigma(p/Z) = |d(p/Z)/dp|*sigma(p) with d(p/Z)/dp = (1/Z)*(1 - (p/Z)*dZ/dp) - I re-derived this and it is correct - but the card supplies no Z correlation (Standing-Katz / Dranchuk-Abou-Kassem / Hall-Yarborough) and therefore no dZ/dp. Without one, every York weight and every Deming lambda in this application is unspecified. This is a whole missing evidence card.
- Independent re-retrieval of Bruns, Fetkovich & Meitzen (1965) before any of its numbers ship. It is the sole petroleum-engineering primary source and the sole positive control for part (c), and I could not reach it. Until then mark 475/596/990 Bscf and the 'over 100 per cent at 65 per cent depletion' quote as single-sourced OCR.
- A block length for the MOVING-block bootstrap specifically. Politis-White gives b_opt for the stationary and circular schemes; the card's default recommendation is MBB, for which the HHJ proportionality constant is still unretrieved. Either switch the default to CBB/SB (where the constant is now sourced) or state plainly that the MBB block length is a repo heuristic.
- A guard and a named exception for the Deming degenerate cases the card identifies but does not specify behaviour for: Sxy = 0 (shut-in period, all Gp identical) and the catastrophic-cancellation branch. The stable conjugate form the card gives, b1 = 2p/[(u - lambda*q) + sqrt((u - lambda*q)^2 + 4*lambda*p^2)], must be selected when (lambda*q - u) < 0 - verify the branch predicate, not just the formula.
- A decision on the g threshold (0.01 vs 0.05 - the card states both), with the target agreement tolerance written down as the justification.

### Recommended independent test oracles

**Exact-Fieller coverage must equal nominal, and must FAIL under whole-line handling**

- Inputs: `n=8, 8 surveys uniform over [0, 0.05*G], G=100 Bscf, p_i/Z_i=4705.9 psia, true line p/Z = 4705.9*(1 - Gp/100), iid Normal noise sigma=300 psia, alpha=0.05, 20000 trials. Score a trial as covered using the correct three-case set: BOUNDED -> lo<=G<=hi; EXCLUSIVE -> NOT(lo<G<hi); WHOLE_LINE -> always.`
- Expected: `Coverage = 0.951 +/- 0.005 (nominal 0.95). The same harness with the naive 'g>=1 implies whole line' rule gives 0.970, and with the delta interval gives 0.787. Assert coverage is in [0.945, 0.957] - this bracket excludes the naive value, so the test fails loudly if the exclusive branch is dropped. Also assert the fraction of g>=1 trials is ~0.906 and that Delta>0 in 100 percent of them.`
- Why independent: It tests calibration, not algebra. Every check in the card that compares a closed form to a grid inversion of the same defining inequality is circular with respect to the set's geometry - both sides inherit the same mistake. A coverage study is the only construct where the truth is known externally (the simulated G) and where a wrong set geometry cannot hide: mis-handling the exclusive case necessarily inflates coverage above nominal, which is exactly the fingerprint that exposed the card's 0.972.

**AR(1) closed-form optimal block size vs Politis & White (2004) Table 1**

- Inputs: `AR(1) with rho in {0.7, 0.1, -0.4} and N in {200, 800}. Closed form for AR(1): G/g(0) = 2*rho/(1-rho^2), so b_opt,SB = |2*rho/(1-rho^2)|^(2/3) * N^(1/3), and b_opt,CB = (3/2)^(1/3) * b_opt,SB.`
- Expected: `b_opt,SB = 11.47, 18.20, 2.01, 3.20, 5.66, 8.99 and b_opt,CB = 13.12, 20.83, 2.31, 3.66, 6.48, 10.23 - the published Table 1 of the PPW (2009) corrected paper. I reproduced 11 of 12 to the printed precision (the two misses, 2.30 vs 2.31 and 10.29 vs 10.23, are the paper's closest-integer bracket and rounding).`
- Why independent: A published numerical table from a primary source, hit by an analytic formula derived from the AR(1) autocovariance - no shared code path with any implementation. It simultaneously validates the corrected D_SB = 2g^2(0), the uncorrected D_CB = (4/3)g^2(0), and their ratio, because the only way all six SB entries and all six CB entries land is if both constants are right. This is the block-bootstrap oracle the card entirely lacks: it has a rate exponent but no constant and no published reference value.

**Deming(lambda) must equal York(constant weights) to machine precision**

- Inputs: `NCSS DemingReg1: x = [7, 8.3, 10.5, 9, 5.1, 8.2, 10.2, 10.3, 7.1, 5.9]; y = [7.9, 8.2, 9.6, 9.0, 6.5, 7.3, 10.2, 10.6, 6.3, 5.2]. Path A: the Deming closed form with lambda = 0.032/0.008 = 4. Path B: the York iteration with omega(X_i) = 1/0.032, omega(Y_i) = 1/0.008, r_i = 0, all points.`
- Expected: `Both slopes = 1.001194227819490 and both intercepts = -0.089744899007043, agreeing to at least 14 significant figures, and both matching NCSS's published 1.00119422781949 / -0.0897448990070444. Additionally assert MSWD = 17.3624 and that the York analytic sigma_b = 0.037614 is deliberately NOT expected to equal the jackknife 0.187177.`
- Why independent: Two algorithms with no shared derivation: a one-shot quadratic root versus an iterative reweighted fixed point that converges on the same objective from a different direction. Neither can absorb the other's error. It is strictly stronger than the card's axis-swap oracle, which relies on the algebraic symmetry of a single estimator. The bundled MSWD assertion is what stops an implementer from silently swapping the two SEs.

**Exact invariance and equivariance identities under input perturbation**

- Inputs: `Any fitted dataset. Apply, one at a time: (i) y -> (1+gamma)*y for gamma = 0.037; (ii) x -> x + c_x for c_x = 3.0 Bscf; (iii) x -> (1+gamma_x)*x for gamma_x = 0.02; (iv) y -> y + c for c = -14.696 psia; (v) rescale Gp from Bscf to scf and back.`
- Expected: `(i) G_hat EXACTLY unchanged to machine precision (a pure gauge gain cannot bias G); (ii) G_hat shifts by exactly +3.0; (iii) G_hat scales by exactly 1.02; (iv) G_hat shifts by exactly -14.696*G/(p_i/Z_i) = -0.3123 Bscf on the card's demo line - note the sign; (v) G_hat in physical units invariant, while the Deming lambda changes by exactly 1e18.`
- Why independent: Structural identities that hold exactly for ANY correct implementation regardless of the data, the noise realisation, or the estimator chosen - they are properties of the estimator's equivariance group, not of any formula in the card. They cost nothing, need no reference values, and case (i) in particular is a machine-precision test that no approximate implementation can fake. Case (iv) is the corrected psig oracle.

**Volumetric positive control: the instrument must see the null case**

- Inputs: `Generate an exactly volumetric dataset from p/Z = (p_i/Z_i)*(1 - Gp/G) with G = 100 Bscf, zero noise, then with sigma = 15 psia gauge noise. Run the same water-drive demonstration pipeline with aquifer strength J = 0.`
- Expected: `Noise-free: G_hat = 100.000000 to machine precision, bias 0.0 percent, R^2 = 1, MSWD -> 0. With noise: bias within Monte Carlo error of zero and R^2 ~ 0.999. Only then is the J > 0 bias attributable to water drive rather than to a bug in the generator or the fitter.`
- Why independent: It is the positive control for the demonstration instrument itself. The card's part (c) conclusion - 'high R^2 with badly biased G' - is only evidence about water drive if the same pipeline provably returns zero bias when there is no water drive. Without it, an arithmetic error in the generator produces exactly the same headline. The card does include a J=0 control; it must be a hard assertion, not a reported row.

**Asymptotic limit agreement: Fieller -> delta as g -> 0, and Deming -> OLS / x-on-y**

- Inputs: `Fieller: the card's demo line at f = 0.50, n = 12, sigma = 25, where max g = 0.0015. Deming: NCSS data at lambda = 1e-12 and lambda = 1e12, using the stable conjugate form.`
- Expected: `Fieller [x_L, x_U] agrees with G_hat -/+ t*SE(G) to better than 0.2 percent and is asymmetric by less than g in relative terms. Deming at lambda -> 0 returns Sxy/Sxx = 0.8616233847697906 to at least 10 significant figures (the card's naive form manages only 5 - that degradation is itself the assertion that the conjugate branch is active), and at lambda -> infinity returns Syy/Sxy = 1.041642399534071.`
- Why independent: Limiting behaviour is fixed by the mathematics independently of the implementation, and the reference values come from a completely different estimator (plain OLS) computed in one line. The lambda -> 0 case doubles as a numerical-conditioning test: demanding 10 significant figures rather than the card's 6 converts a documented pitfall into a failing test.

## Sources

| Citation | Access level | Supports |
|---|---|---|
| York, D., Evensen, N.M., Lopez Martinez, M., De Basabe Delgado, J. (2004). 'Unified equations for the slope, intercept, and standard errors of the best straight line.' American Journal of Physics 72(3):367-375. DOI 10.1119/1.1632486 | full-text retrieved | The complete York EIV algorithm: Table I symbol definitions (omega, alpha_i, r_i, W_i, U_i, V_i, beta_i, u_i), Eqs. (13a)-(13d) for a, b, sigma_a, sigma_b, the 10-step iteration, cov(a,b) = -xbar*sigma_b^2, the MSWD S/(n-2), the axis-interchange recipe for the x-intercept and its standard error, the special cases (major axis, reduced major axis, y-on-x, r_i = -1), and Table II Monte Carlo benchmark values used as the independent check |
| NCSS Statistical Software, Chapter 303: 'Deming Regression.' NCSS, LLC. (formulas attributed to Linnet K. 1990) | full-text retrieved | Deming closed form with lambda = V(eps)/V(delta), the objective SS, the slope/intercept formulas, the adjusted true-value estimates, the weighted (proportional-error) variant and its weights, the iterative re-weighting scheme, the jackknife SE procedure, the N-2 vs N-1 df question (CLSI EP09-A3 App. H), and a fully published worked example with full-precision output used as the regression test. NOTE: this is vendor documentation, a SECONDARY source for the underlying Linnet derivation - the derivation itself should be traced to Linnet (1990) Stat. Med. 9:1463-1473 before anything is claimed as primary. |
| Bruns, J.R., Fetkovich, M.J., Meitzen, V.C. (1965). 'The Effect of Water Influx on p/z-Cumulative Gas Production Curves.' Journal of Petroleum Technology, March 1965, 287-291. SPE-898-PA | full-text retrieved | The primary petroleum-engineering authority for part (c): the volumetric p/Z derivation (Appendix A, Eqs. A-1 to A-6), the water-drive balance (Eqs. A-7 to A-11) showing G_apparent = G_real + K_e*S(p,t)/(Bg - Bgi), the Schilthuis / Hurst-simplified / van Everdingen-Hurst aquifer families, Table 1 field conditions (used to cross-check volumetric GIIP), Fig. 10 reserve estimates 475/596/990 Bscf at Gp = 300 Bscf, and the explicit conclusion that straight-line extrapolation can over-estimate GIIP by more than 100 percent at 65 percent depletion, plus the warning that early curvature must not be dismissed as measurement error |
| Patton, A., Politis, D.N., White, H. (2009). 'Correction to Automatic Block-Length Selection for the Dependent Bootstrap by D. Politis and H. White.' Econometric Reviews 28(4):372-375. DOI 10.1080/07474930802459016 | full-text retrieved | The corrected stationary-bootstrap variance constant D_SB = 2*g^2(0) and its estimator D_SB_hat = 2*g_hat^2(0), the corrected ARE_CB/SB = (2/3)^(2/3) = 0.7631, the statement that PW2004 Eqs. (6), (7) and (9) remain valid with the corrected D_SB, the corrected simulation tables, and the retrieved citations for Politis & Romano (1994) JASA 89:1303-1313, Lahiri (1999) Ann. Statist. 27:386-404 and Nordman (2008) |
| Hall, P., Horowitz, J.L., Jing, B.-Y. (1995). 'On blocking rules for the bootstrap with dependent data.' Biometrika 82(3):561-574 | abstract/metadata only | The primary statistics citation requested for block-length choice: optimal block size of order n^(1/3) for variance or bias estimation (our case, since we want SE(G)), n^(1/4) for a one-sided distribution function, n^(1/5) for a two-sided distribution function. The proportionality constant and the empirical cross-validation rule are NOT covered by the abstract and remain unverified. |
| Politis, D.N., White, H. (2004). 'Automatic block-length selection for the dependent bootstrap.' Econometric Reviews 23(1):53-70. DOI 10.1081/ETC-120028836 | abstract/metadata only | The existence and framing of the data-driven spectral-density plug-in block-length estimator (flat-top lag windows of Politis & Romano 1995). The explicit Eqs. (6)-(9) were NOT retrieved and must not be reproduced from memory. |
| Fieller, E.C. (1954). 'Some Problems in Interval Estimation.' Journal of the Royal Statistical Society, Series B (Methodological) 16(2):175-185. DOI 10.1111/j.2517-6161.1954.tb00159.x | abstract/metadata only | The exact (non-delta-method) confidence set for a ratio, which is what the x-intercept -a/b is. Citation verified at metadata level; the closed form given in this card is the standard calibration specialisation and was verified numerically in-session against brute-force set inversion and Monte Carlo coverage, not read from Fieller's paper. |
| Kuensch, H.R. (1989). 'The jackknife and the bootstrap for general stationary observations.' Annals of Statistics 17(3):1217-1241 | Unverified — cited source not inspected - not retrieved | The moving-block bootstrap itself. Retrieve before citing it as primary in a publication; the resampling scheme as described here is standard and was verified to behave correctly in-session (MBB at l=1 reduces exactly to the iid bootstrap). |
| Politis, D.N., Romano, J.P. (1994). 'The stationary bootstrap.' Journal of the American Statistical Association 89:1303-1313 | secondary source | The stationary bootstrap with Geometric block lengths. The citation string was retrieved from the reference list of Patton, Politis & White (2009) this session; the paper itself was not read. |
| Draper, N.R., Smith, H. (1998). Applied Regression Analysis, 3rd ed. Wiley | Unverified — cited source not inspected - not retrieved | OLS closed form, Var(a), Var(b), Cov(a,b) = -xbar*s^2/Sxx, and the inverse-prediction (calibration) interval. Every formula attributed to it here was independently verified numerically in-session against Monte Carlo, but the textbook page was not opened. |
| Linnet, K. (1990). 'Estimation of the linear relationship between the measurements of two methods with proportional errors.' Statistics in Medicine 9:1463-1473; and Linnet, K. (1993). Clinical Chemistry 39:424-432 | secondary source | The primary derivation behind the Deming formulas and the adequacy of the jackknife for Deming SEs. Cited by NCSS Chapter 303 (retrieved); the Linnet papers themselves were NOT retrieved this session. |
| CLSI EP09-A3, Appendix H (Clinical and Laboratory Standards Institute) | secondary source | The N-2 degrees of freedom convention for Deming jackknife standard errors. Known only through the NCSS text retrieved this session; the standard itself was not retrieved. |
| Craft, B.C., Hawkins, M.F. (rev. Terry, R.E.), Applied Petroleum Reservoir Engineering; and Dake, L.P., Fundamentals of Reservoir Engineering (Elsevier) | Unverified — cited source not inspected - not retrieved | Standard textbook statements of the gas material balance and the p/Z plot, including the abnormally-pressured two-slope behaviour. Everything load-bearing here is instead sourced to Bruns et al. (1965), which WAS retrieved. |

# API contract for `reservoir_lab`

This document fixes the shape of the numerical core before any physics module is
written. It exists because the modules are developed against each other: a case study
composes `gas_properties`, `material_balance`, `aquifer` and `regression` in one
script, and if their conventions drift the composition silently produces a number that
is wrong in a way no single module's tests can see.

It is a contract, not documentation. Where it conflicts with an implementation, the
implementation is wrong.

## C1. Unit system

Field (oilfield) units throughout the public API, with absolute pressure and absolute
temperature.

| Quantity | Unit | Notes |
|---|---|---|
| Pressure | psia | Absolute. A function never accepts psig. |
| Temperature | degR for reservoir calculations, degF only at explicit conversion boundaries | `units.fahrenheit_to_rankine` is the only bridge. |
| Volume, reservoir | ft^3, or bbl where the correlation is published in bbl | The unit is in the parameter name. |
| Volume, surface gas | scf | Always accompanied by a `StandardConditions`. |
| Viscosity | cp | |
| Density | lbm/ft^3, converted internally to g/cm^3 where a correlation demands it | |
| Permeability | md | |
| Compressibility | 1/psi | |
| Time | days for material balance and aquifer influx, hours for pressure transients | The unit is in the parameter name. |

**Parameter naming rule.** Every public parameter carrying a dimensional quantity ends
in its unit: `pressure_psia`, `temperature_degr`, `thickness_ft`, `time_days`,
`viscosity_cp`, `permeability_md`, `compressibility_per_psi`. A reviewer must be able
to check dimensional consistency from the call site alone, without opening the callee.
Dimensionless groups take no suffix: `z_factor`, `t_pr`, `p_pr`, `skin`,
`specific_gravity`.

## C2. Validation

Every public function validates through `reservoir_lab.validation`. No public function
sorts, clips, truncates, interpolates, or drops a caller's data. It either accepts the
input or raises `InvalidInputError` naming the offending argument and index.

Correlation validity windows use `validation.check_range`, which warns by default with
`RangeWarning` and raises under `strict=True`. Every function that wraps a correlation
exposes a `strict_range: bool = False` keyword.

## C3. Errors

| Condition | Exception |
|---|---|
| Malformed, non-finite, or physically impossible argument | `InvalidInputError` |
| Iteration budget exhausted | `ConvergenceError`, carrying `iterations`, `last_value`, `last_residual` |
| Outside a published correlation window, `strict_range=True` | `OutOfRangeWarningError` |
| Quantity not identifiable from the data supplied | `NotIdentifiableError` |

A function never returns a sentinel such as `None`, `-1`, or `nan` to signal failure.

## C4. Purity and determinism

Public functions are pure: no globals, no module-level mutable state, no I/O, no
implicit clock, no implicit RNG. Any function needing randomness takes a
`random.Random` instance or an integer `seed` and constructs one locally. Two calls
with equal arguments return equal results, bit for bit, within one interpreter build.

## C5. Return types

Scalars return `float`. Series return `tuple[float, ...]`, never a mutable list, so a
caller cannot modify a validated result in place.

Anything with more than one meaningful component returns a frozen dataclass, not a
tuple and not a dict, so that fields are named at the use site and an added field does
not silently break unpacking. Every such dataclass carries enough metadata to make its
own result auditable -- at minimum the method used and the number of points consumed.

## C6. Module map and required signatures

Signatures below are the contract. Keyword-only arguments after `*` are keyword-only in
the implementation.

### `units` — implemented

Exact conversion factors and `StandardConditions`. No physics.

### `errors`, `validation`, `provenance` — implemented

Exceptions, input guards, and write-once run records.

### `gas_properties`

```python
def pseudocritical_standing(specific_gravity, *, fluid="dry_gas", strict_range=False) -> PseudoCriticals
def pseudocritical_sutton(specific_gravity, *, strict_range=False) -> PseudoCriticals
def wichert_aziz_correction(pseudocriticals, *, y_h2s, y_co2) -> PseudoCriticals
def z_factor_dak(t_pr, p_pr, *, tolerance=1e-12, max_iterations=100, strict_range=False) -> float
def z_factor_hall_yarborough(t_pr, p_pr, *, tolerance=1e-12, max_iterations=100, strict_range=False) -> float
def z_factor_dpr(t_pr, p_pr, *, tolerance=1e-12, max_iterations=100, strict_range=False) -> float
def z_factor(pressure_psia, temperature_degr, pseudocriticals, *, method="dak", **kw) -> float
def gas_density_lbm_per_cuft(pressure_psia, temperature_degr, z_factor, molar_mass) -> float
def gas_viscosity_lee_gonzalez_eakin(temperature_degr, molar_mass, density_lbm_per_cuft, *, strict_range=False) -> float
def gas_compressibility_per_psi(pressure_psia, temperature_degr, pseudocriticals, *, method="dak") -> float
def gas_fvf_rcf_per_scf(pressure_psia, temperature_degr, z_factor, standard) -> float
def gas_fvf_rb_per_scf(pressure_psia, temperature_degr, z_factor, standard) -> float
```

`PseudoCriticals` is a frozen dataclass with `temperature_degr`, `pressure_psia`,
`correlation`, and `corrections: tuple[str, ...]`.

Z-factor solvers are **Newton with an analytic derivative**, not fixed-point iteration,
and they raise `ConvergenceError` rather than returning the last iterate. Each records
its published validity window as a module constant so a test can read it.

`gas_compressibility_per_psi` uses the analytic `dZ/dp` obtained by differentiating the
correlation through reduced density. A finite-difference fallback is permitted only as a
*test oracle* for the analytic derivative, never as the production path.

### `pseudopressure`

```python
def pseudopressure(pressure_psia, *, reference_psia, mu_z, intervals=..., method="simpson") -> float
def pseudopressure_constant_properties(pressure_psia, *, reference_psia, viscosity_cp, z_factor) -> float
def convergence_study(pressure_psia, *, reference_psia, mu_z, interval_counts) -> ConvergenceResult
```

`mu_z` is a callable `p -> mu(p) * Z(p)` in cp. Keeping it a callable rather than a
table is what allows the constant-property analytic limit to be used as an exact oracle.

`ConvergenceResult` reports the observed order of accuracy from successive refinements,
so a test asserts the *demonstrated* order rather than asserting a single grid's value.

### `material_balance`

```python
def p_over_z(pressure_psia, z_factor) -> float
def volumetric_gas_in_place_scf(*, area_acres, thickness_ft, porosity, water_saturation, gas_fvf_rcf_per_scf) -> float
def fit_pz_depletion(cumulative_gas_scf, p_over_z_psia, *, method="ols", weights=None) -> PZFit
def rock_water_expansion_term(...) -> float
def general_material_balance_residual(...) -> float
```

`PZFit` is a frozen dataclass carrying `gas_in_place_scf`,
`gas_in_place_stderr_scf`, `initial_p_over_z`, `slope`, `intercept`, `r_squared`,
`residuals`, `covariance`, `n_points`, `method`, and `depletion_fraction_observed`.

`gas_in_place_stderr_scf` **must** be the delta-method standard error of the
x-intercept including the slope-intercept covariance term. An implementation that
propagates only the slope and intercept variances is wrong and the test suite proves
it against a Monte Carlo reference.

`PZFit` additionally exposes `warnings: tuple[str, ...]` populated when the fit is
weakly constrained -- notably when `depletion_fraction_observed` is small, where the
x-intercept is an extrapolation far outside the data.

### `aquifer`

```python
@dataclass(frozen=True)
class FetkovichAquifer:
    initial_pressure_psia: float
    water_volume_bbl: float
    total_compressibility_per_psi: float
    productivity_index_bbl_per_day_psi: float
    def maximum_influx_bbl(self) -> float
    def step(self, *, aquifer_pressure_psia, reservoir_pressure_psia, timestep_days) -> AquiferStep
    def influx_history(self, *, times_days, reservoir_pressure_psia) -> tuple[AquiferStep, ...]
```

The recursion is the published Fetkovich form; the implementation states in its
docstring which pressure appears in each position, because the common transcription
error is using the current reservoir pressure where the initial aquifer pressure
belongs.

### `depletion`

Forward generators. These produce the synthetic observations that the inverse methods
are then applied to. They are deliberately in a **separate module from
`material_balance`** so that the generator and the estimator do not share code; sharing
would make every recovery test circular.

```python
def simulate_volumetric_depletion(...) -> DepletionHistory
def simulate_water_drive_depletion(...) -> DepletionHistory   # couples FetkovichAquifer
```

`simulate_water_drive_depletion` solves the coupled reservoir/aquifer pressure at each
step to a stated tolerance and records the achieved residual, so the generator's own
numerical error is known and can be shown to be far below the effect being studied.

### `regression`

```python
def ols_line(x, y, *, weights=None) -> LineFit
def deming_line(x, y, *, error_variance_ratio) -> LineFit
def york_line(x, y, *, x_std, y_std, correlation=0.0, tolerance=1e-12, max_iterations=200) -> LineFit
def x_intercept(fit) -> IntervalEstimate
def moving_block_bootstrap(x, y, *, block_length, replicates, seed, statistic) -> BootstrapResult
```

`LineFit` carries `slope`, `intercept`, `slope_stderr`, `intercept_stderr`,
`covariance`, `residuals`, `r_squared`, `n_points`, `method`, `degrees_of_freedom`.

### `diagnostics`

```python
def log_time_derivative(time, response) -> tuple[tuple[float, ...], tuple[float, ...]]
def bourdet_derivative(time, response, *, smoothing_l) -> tuple[tuple[float, ...], tuple[float, ...]]
```

Both return `(time_subset, derivative)`. Endpoints where the stencil is undefined are
omitted rather than one-sided, and negative derivative values are preserved: a negative
derivative is physical information about the response, and clipping it hides exactly
the behaviour a diagnostic plot exists to reveal.

### `rates`

```python
def cumulative_from_rates(*, times_days, rates_per_day, method="stepwise") -> tuple[float, ...]
def average_rates_from_cumulative(*, times_days, cumulative) -> tuple[float, ...]
```

`method="stepwise"` treats a reported rate as constant over its reporting interval,
which is what a daily allocated production record actually means.
`method="trapezoid"` treats the rate as linear between reports. The two differ by an
amount that matters, so the choice is explicit and recorded.

### `balance`

```python
def component_balance_residual(*, initial, injected, influx, remaining, produced, efflux) -> float
```

All arguments in one consistent mass or mole basis for a single component. The
docstring states plainly that summing reservoir phase *volumes* is not a conserved
quantity when compressibility, dissolution or vaporisation is active.

## C7. Test obligations

Each module ships tests in these four categories, and a module is not complete without
all four:

1. **Independent oracle.** A value from a closed form, a published worked example, an
   independent reference dataset, or a different correlation -- never the module's own
   output from a previous run.
2. **Limiting case.** Behaviour where the answer is known analytically (ideal gas,
   constant properties, zero noise, zero influx, infinite aquifer volume).
3. **Invalid input.** Every documented raise is exercised.
4. **Property or invariant.** Monotonicity, dimensional scaling, symmetry, conservation,
   or convergence order.

## C8. Dependency policy

`src/reservoir_lab` imports **only the Python standard library**. This is a hard rule,
verified by a test that walks the AST of every module. The reason is not minimalism: it
is that a reviewer can check the numerics without reproducing an environment, and a
result cannot silently change because a third-party solver changed its defaults.

Case studies under `cases/` and plotting scripts may use the optional `analysis` extra
(NumPy, SciPy, Matplotlib). Where an optional dependency is used for anything other
than plotting, the same quantity is also computed with the stdlib core and the two are
compared in the case report.

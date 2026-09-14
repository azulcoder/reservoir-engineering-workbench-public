"""Gas-reservoir calculations with explicit units and deliberately narrow scope.

References: docs/references.md, R01, R02, R03, R08 and R09.
These functions are calculation primitives, not field-validated interpretation tools.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass


def _number(value: float, name: str, *, zero_ok: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a number, not a Boolean")
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(result) or (result < 0 if zero_ok else result <= 0):
        condition = "nonnegative" if zero_ok else "positive"
        raise ValueError(f"{name} must be finite and {condition}")
    return result


def _vector(values: Sequence[float], name: str, *, zero_ok: bool = False) -> tuple[float, ...]:
    return tuple(_number(v, f"{name}[{i}]", zero_ok=zero_ok) for i, v in enumerate(values))


def _finite_result(value: float, name: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{name} overflowed; check units and input magnitudes")
    return value


def gas_fvf(
    pressure_pa: float,
    temperature_k: float,
    z: float,
    *,
    standard_pressure_pa: float,
    standard_temperature_k: float,
    standard_z: float = 1.0,
) -> float:
    """Gas formation-volume factor in reservoir m3 / standard m3.

    Bg = (Z*T/P) / (Zsc*Tsc/Psc). Both pressures are ABSOLUTE;
    both temperatures are Kelvin. Standard conditions must be supplied.
    No phase-equilibrium or fluid-property calculation is performed here.
    """
    p = _number(pressure_pa, "pressure_pa")
    t = _number(temperature_k, "temperature_k")
    zz = _number(z, "z")
    ps = _number(standard_pressure_pa, "standard_pressure_pa")
    ts = _number(standard_temperature_k, "standard_temperature_k")
    zs = _number(standard_z, "standard_z")
    return _finite_result((zz / zs) * (t / ts) * (ps / p), "Bg")


@dataclass(frozen=True)
class PzFit:
    """Ordinary least-squares screen; no confidence interval or physical validation."""

    giip_sm3: float
    intercept_pa: float
    slope_pa_per_sm3: float
    rmse_pa: float
    r_squared: float
    n_observations: int
    warnings: tuple[str, ...]

    def predict_p_over_z(self, cumulative_gas_sm3: float) -> float:
        """Evaluate the fitted line at a cumulative production.

        Raises rather than returning a non-positive value: past the fitted gas in place
        the straight line predicts a negative p/Z, which is not a pressure.
        """
        gp = _number(cumulative_gas_sm3, "cumulative_gas_sm3", zero_ok=True)
        value = self.intercept_pa + self.slope_pa_per_sm3 * gp
        if value <= 0:
            raise ValueError("Prediction reaches/exceeds fitted gas in place")
        return _finite_result(value, "predicted p/z")


def fit_volumetric_pz(
    cumulative_gas_sm3: Sequence[float],
    pressure_pa: Sequence[float],
    z: Sequence[float],
) -> PzFit:
    """Fit p/Z = intercept + slope*Gp; GIIP = -intercept/slope.

    Applicability must be established outside this function: representative
    average reservoir pressure, isothermal single gas phase of fixed composition,
    constant gas pore volume, no aquifer influx, injection or material leakage,
    negligible rock/water expansion. Inputs use ONE declared standard-volume basis.
    Do not substitute flowing BHP for average reservoir pressure.

    Repeated Gp observations are accepted; there must be variation in Gp.
    No sorting, outlier removal, anchoring, weighting, or extrapolation is hidden.
    This OLS screen treats Gp as exact and is not an errors-in-variables analysis.
    """
    gp = _vector(cumulative_gas_sm3, "cumulative_gas_sm3", zero_ok=True)
    p = _vector(pressure_pa, "pressure_pa")
    zz = _vector(z, "z")
    n = len(gp)
    if n < 3 or len(p) != n or len(zz) != n:
        raise ValueError("Provide equal-length vectors with at least three observations")
    if any(b < a for a, b in itertools.pairwise(gp)):
        raise ValueError("Gp must be chronologically nondecreasing; do not sort silently")
    scale = gp[-1] - gp[0]
    if scale <= 0:
        raise ValueError("Gp must contain variation")
    # Scale the independent variable before regression to improve conditioning.
    x = tuple((v - gp[0]) / scale for v in gp)
    y = tuple(_finite_result(a / b, "p/z") for a, b in zip(p, zz, strict=True))
    xm, ym = math.fsum(x) / n, math.fsum(y) / n
    xx = math.fsum((v - xm) ** 2 for v in x)
    slope_scaled = math.fsum((a - xm) * (b - ym) for a, b in zip(x, y, strict=True)) / xx
    slope = slope_scaled / scale
    intercept = ym - slope_scaled * xm - slope * gp[0]
    if slope >= 0 or intercept <= 0:
        raise ValueError("Nonphysical volumetric p/z fit: require negative slope and positive intercept")
    giip = _finite_result(-intercept / slope, "GIIP")
    if giip <= max(gp):
        raise ValueError("Fitted GIIP does not exceed observed cumulative production")
    residuals = tuple(yi - (intercept + slope * xi) for xi, yi in zip(gp, y, strict=True))
    ss_res = math.fsum(e * e for e in residuals)
    ss_tot = math.fsum((yi - ym) ** 2 for yi in y)
    warnings = ["OLS screening only; a high R-squared does not validate reservoir assumptions."]
    if gp[0] != 0:
        warnings.append("No initial Gp=0 observation; initial p/z is extrapolated.")
    if abs(slope) * scale / intercept < 0.05:
        warnings.append("Less than 5% fitted p/z decline: GIIP extrapolation is weakly constrained.")
    return PzFit(
        giip,
        intercept,
        slope,
        math.sqrt(ss_res / n),
        1.0 - ss_res / ss_tot if ss_tot else 0.0,
        n,
        tuple(warnings),
    )


def relative_pseudopressure(
    pressure_pa: Sequence[float],
    viscosity_pa_s: Sequence[float],
    z: Sequence[float],
) -> tuple[float, ...]:
    """Cumulative trapezoidal integral of 2p/(mu*Z), relative to FIRST pressure.

    Pressure must increase strictly. No extrapolation, sorting, or gas-property
    correlation is applied. The first result is zero, not an absolute m(p) at p=0.
    Units are Pa^2/(Pa*s). Differences do not depend on the integration datum.
    This transform alone is NOT a gas PTA model, pseudotime, or rate superposition.
    """
    p = _vector(pressure_pa, "pressure_pa")
    mu = _vector(viscosity_pa_s, "viscosity_pa_s")
    zz = _vector(z, "z")
    if len(p) < 2 or len(mu) != len(p) or len(zz) != len(p):
        raise ValueError("Provide equal-length vectors with at least two pressure nodes")
    if any(b <= a for a, b in itertools.pairwise(p)):
        raise ValueError("Pressure grid must be strictly increasing")
    f = tuple(
        _finite_result(2.0 * pi / mui / zi, "pseudopressure integrand")
        for pi, mui, zi in zip(p, mu, zz, strict=True)
    )
    result = [0.0]
    for i in range(1, len(p)):
        area = 0.5 * (f[i - 1] + f[i]) * (p[i] - p[i - 1])
        result.append(_finite_result(result[-1] + area, "pseudopressure"))
    return tuple(result)


def log_time_derivative(
    elapsed_time_s: Sequence[float],
    response: Sequence[float],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Unsmoothed three-point weighted derivative d(response)/d ln(t).

    Returns INTERIOR times and derivatives; endpoints are omitted deliberately.
    Response may be pressure difference or pseudopressure difference, with units
    retained. Natural logarithms are used. Negative derivatives are preserved.
    This is a numerical primitive, not a full windowed Bourdet/PTA workflow.
    Buildup time transformations and variable-rate corrections are NOT included.
    """
    t = _vector(elapsed_time_s, "elapsed_time_s")
    try:
        y = tuple(float(v) for v in response)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Response must contain finite numbers") from exc
    if len(t) < 3 or len(y) != len(t) or not all(math.isfinite(v) for v in y):
        raise ValueError("Provide equal-length finite vectors with at least three observations")
    if any(b <= a for a, b in itertools.pairwise(t)):
        raise ValueError("Elapsed time must be strictly increasing and positive")
    d = []
    for i in range(1, len(t) - 1):
        hl, hr = math.log(t[i] / t[i - 1]), math.log(t[i + 1] / t[i])
        left = (y[i] - y[i - 1]) / hl
        right = (y[i + 1] - y[i]) / hr
        d.append(_finite_result((left * hr + right * hl) / (hl + hr), "log derivative"))
    return t[1:-1], tuple(d)


def cumulative_step_volume(
    interval_edges_s: Sequence[float],
    interval_average_rate_sm3_s: Sequence[float],
) -> tuple[float, ...]:
    """Integrate nonnegative interval-average production rates.

    N+1 strictly increasing edges for N rates; output begins at zero at edge[0].
    Rate means average over the ENTIRE calendar interval. Do not multiply uptime
    again if downtime has already been included in the average. Missing intervals
    must be resolved explicitly before calling. Injection is a separate stream.
    """
    t = _vector(interval_edges_s, "interval_edges_s", zero_ok=True)
    q = _vector(interval_average_rate_sm3_s, "interval_average_rate_sm3_s", zero_ok=True)
    if len(t) < 2 or len(q) != len(t) - 1:
        raise ValueError("N rates require N+1 interval edges")
    if any(b <= a for a, b in itertools.pairwise(t)):
        raise ValueError("Interval edges must increase strictly")
    result = [0.0]
    # Pair the N+1 edges into N intervals explicitly. Writing zip(t, t[1:], q) and
    # letting it truncate would work, but it hides the off-by-one in the idiom and
    # then strict=True cannot be used to catch a genuine edge/rate mismatch.
    for left, right, rate in zip(t[:-1], t[1:], q, strict=True):
        result.append(_finite_result(result[-1] + (right - left) * rate, "cumulative volume"))
    return tuple(result)


def component_balance_error(
    initial_mass: float,
    remaining_mass: float,
    cumulative_production_mass: float,
    *,
    cumulative_injection_mass: float = 0.0,
    boundary_in_mass: float = 0.0,
    boundary_out_mass: float = 0.0,
) -> float:
    """Signed component balance residual / total component mass supplied.

    All arguments are nonnegative masses of ONE conserved component in the same
    units; consistent moles are also allowed. Include all boundary fluxes.
    Not valid for adding phase volumes or components with chemical reactions
    unless all relevant source/sink terms are included separately.
    Positive residual means apparent missing mass; negative means apparent gain.
    """
    vals = [
        _number(v, n, zero_ok=True)
        for v, n in [
            (initial_mass, "initial_mass"),
            (remaining_mass, "remaining_mass"),
            (cumulative_production_mass, "cumulative_production_mass"),
            (cumulative_injection_mass, "cumulative_injection_mass"),
            (boundary_in_mass, "boundary_in_mass"),
            (boundary_out_mass, "boundary_out_mass"),
        ]
    ]
    m0, mr, mp, mi, bin_, bout = vals
    supplied = math.fsum((m0, mi, bin_))
    if supplied == 0:
        raise ValueError("Relative residual is undefined for zero supplied mass")
    return _finite_result(math.fsum((m0, mi, bin_, -mr, -mp, -bout)) / supplied, "balance residual")

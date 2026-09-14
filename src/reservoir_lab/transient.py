"""Constant-rate radial transient flow: the line-source solution and its interpretation.

The whole module is the one solution and the one straight line that reads it back:

    p_D(t_D, r_D) = (1/2) E1(r_D^2 / (4 t_D))  + s

the constant-rate line-source response of an infinite, homogeneous, isotropic radial
system to a slightly compressible single-phase fluid of constant properties, plus a
skin offset. Nothing here knows about boundaries, wellbore storage, fractures, multiple
layers, rate changes, or real-gas behaviour, and none of those can be smuggled in by
passing a different argument.

Why the arithmetic is dimensionless inside
------------------------------------------
Field-unit well-test formulae are a thicket of constants -- 141.2, 0.0002637, 162.6,
70.6, 1.151, 3.2275 -- and every one of them is a place to hide a mistake that a
self-consistent test will not find. So the solution is evaluated in dimensionless form,
where the only constants are ``ln 4 - gamma`` and one half, and the conversion happens
at the boundary in :func:`dimensionless_time` and :func:`dimensionless_pressure`.

The published constants are then *derived* rather than stored:

    162.5625 = 141.2 * ln(10) / 2          semilog slope, per log10 cycle
    70.6     = 141.2 / 2                   derivative plateau, per natural-log cycle
    1.151293 = ln(10) / 2
    3.2275   = -log10(0.0002637) - (ln 4 - gamma)/ln(10)
    0.809079 = ln 4 - gamma

``tests/test_transient.py`` recomputes each one and compares it with the published
value, so a transcription error in any of them is a failing test rather than a plausible
answer. The two factors they all descend from, ``141.2`` and ``0.0002637``, are the
conventional oil-field definitions and are the one thing here taken as given.

The exponential integral
------------------------
``E1(x) = integral from x to infinity of exp(-u)/u du`` for ``x > 0``. Two branches,
because no single expansion is good everywhere:

* ``x <= 1``: the alternating series ``-gamma - ln x + sum (-1)^(n+1) x^n / (n n!)``.
* ``x > 1``: the continued fraction in modified Lentz form, which converges quickly and
  avoids the cancellation that destroys the series as ``x`` grows.

At the wellbore ``x = 1/(4 t_D)``, and infinite-acting radial flow needs large ``t_D``,
so every interpretation this module supports lives in the first branch. The second is
reachable at very early time or at large radius and is tested, not merely present.

What "independent" means here
-----------------------------
The forward solution evaluates a special function; the inverse fits a straight line to
the logarithm of time and never sees the true parameters. Those are different pieces of
mathematics, so agreement between them is evidence. Running one equation backwards
through itself would not be, and this module does not do it.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from .errors import InvalidInputError
from .validation import (
    as_float_sequence,
    require_min_length,
    require_positive,
    require_same_length,
    require_strictly_increasing,
)

__all__ = [
    "EULER_MASCHERONI",
    "LINE_SOURCE_CONSTANT",
    "PRESSURE_FIELD_FACTOR",
    "TIME_FIELD_FACTOR",
    "SemilogInterpretation",
    "derivative_plateau_constant",
    "dimensionless_pressure",
    "dimensionless_time",
    "exponential_integral_e1",
    "line_source_dimensionless_pressure",
    "line_source_log_derivative",
    "permeability_from_semilog_slope",
    "pressure_drop_psi",
    "semilog_interpretation",
    "semilog_skin_constant",
    "semilog_slope_constant",
    "skin_from_semilog_line",
]

#: Euler-Mascheroni constant, to the precision a double can carry.
EULER_MASCHERONI = 0.5772156649015329

#: ``ln 4 - gamma``. The ``0.80907`` that appears in every semilog form.
LINE_SOURCE_CONSTANT = math.log(4.0) - EULER_MASCHERONI

#: Oil-field dimensionless-pressure factor: ``p_D = k h dp / (141.2 q B mu)``.
PRESSURE_FIELD_FACTOR = 141.2

#: Oil-field dimensionless-time factor: ``t_D = 0.0002637 k t / (phi mu c_t r_w^2)``.
TIME_FIELD_FACTOR = 0.0002637

_LN10 = math.log(10.0)
_SERIES_LIMIT = 1.0
_MAX_TERMS = 200
_TINY = 1.0e-300


def semilog_slope_constant() -> float:
    """Return the ``162.6`` of ``m = 162.6 q B mu / (k h)``, derived not stored."""
    return PRESSURE_FIELD_FACTOR * _LN10 / 2.0


def derivative_plateau_constant() -> float:
    """Return the ``70.6`` of the infinite-acting derivative plateau, derived not stored."""
    return PRESSURE_FIELD_FACTOR / 2.0


def semilog_skin_constant() -> float:
    """Return the ``3.2275`` of the skin equation, derived not stored."""
    return -math.log10(TIME_FIELD_FACTOR) - LINE_SOURCE_CONSTANT / _LN10


def exponential_integral_e1(x: float) -> float:
    """Return ``E1(x)`` for ``x > 0``.

    Two branches, chosen so that neither is used where it loses its digits. Below
    ``x = 1`` the alternating series is well conditioned; above it the terms grow before
    they shrink and the cancellation ruins the answer, so the continued fraction takes
    over. The switch point is not tuned to a test: it is where the largest term of the
    series stops being the first one.

    Raises
    ------
    InvalidInputError
        If ``x`` is not a finite, strictly positive number. ``E1`` diverges at zero and
        is not real for negative argument, so neither is quietly accepted.
    """
    value = require_positive(x, "x")
    if value <= _SERIES_LIMIT:
        total = 0.0
        term = 1.0
        for n in range(1, _MAX_TERMS):
            term *= -value / n
            total += -term / n
            if abs(term / n) < 1.0e-18 * max(abs(total), _TINY):
                break
        return -EULER_MASCHERONI - math.log(value) + total

    # Modified Lentz continued fraction:
    #   E1(x) = exp(-x) / (x + 1 - 1^2/(x + 3 - 2^2/(x + 5 - ...)))
    b = value + 1.0
    c = 1.0 / _TINY
    d = 1.0 / b
    h = d
    for i in range(1, _MAX_TERMS):
        a = -float(i * i)
        b += 2.0
        d = 1.0 / (a * d + b)
        c = b + a / c
        delta = c * d
        h *= delta
        if abs(delta - 1.0) < 1.0e-16:
            break
    return h * math.exp(-value)


def line_source_dimensionless_pressure(
    dimensionless_time_value: float,
    *,
    dimensionless_radius: float = 1.0,
    skin: float = 0.0,
) -> float:
    """Return ``p_D`` for the constant-rate line source, with a skin offset.

    ``p_D = (1/2) E1(r_D^2 / (4 t_D)) + s``. The skin term is added only at the wellbore,
    because that is what skin means: a rate-proportional pressure drop across a thin
    region at the sandface. Asking for a skin at ``r_D != 1`` is a modelling error rather
    than a number worth returning, so it is refused.
    """
    t_d = require_positive(dimensionless_time_value, "dimensionless_time_value")
    r_d = require_positive(dimensionless_radius, "dimensionless_radius")
    if skin != 0.0 and r_d != 1.0:
        raise InvalidInputError(
            f"skin={skin!r} was given with dimensionless_radius={r_d!r}. Skin is a "
            "pressure drop at the sandface and is defined at the wellbore, r_D = 1. "
            "Evaluate the unskinned solution away from the well, or ask at r_D = 1."
        )
    argument = r_d * r_d / (4.0 * t_d)
    return 0.5 * exponential_integral_e1(argument) + skin


def line_source_log_derivative(
    dimensionless_time_value: float, *, dimensionless_radius: float = 1.0
) -> float:
    """Return ``d p_D / d ln t_D`` for the line source, in closed form.

    Differentiating ``(1/2) E1(a/t_D)`` with ``a = r_D^2/4`` gives exactly

        d p_D / d ln t_D = (1/2) exp(-r_D^2 / (4 t_D))

    which is the single most useful check in this module. It is an exact expression for
    the quantity the Bourdet three-point algorithm estimates numerically, and it shares
    no code with it, so the two disagreeing means something.

    Note what it does *not* equal. At the wellbore it approaches ``1/2`` from below with
    a deficit of ``1/(8 t_D)``, and that deficit is a property of the solution rather than
    an error in anything. Testing a measured derivative against ``1/2`` would hide a real
    systematic difference inside whatever tolerance was generous enough to pass.
    """
    t_d = require_positive(dimensionless_time_value, "dimensionless_time_value")
    r_d = require_positive(dimensionless_radius, "dimensionless_radius")
    return 0.5 * math.exp(-r_d * r_d / (4.0 * t_d))


def dimensionless_time(
    time_hours: float,
    *,
    permeability_md: float,
    porosity: float,
    viscosity_cp: float,
    total_compressibility_per_psi: float,
    wellbore_radius_ft: float,
) -> float:
    """Return ``t_D = 0.0002637 k t / (phi mu c_t r_w^2)`` in oil-field units."""
    t = require_positive(time_hours, "time_hours")
    k = require_positive(permeability_md, "permeability_md")
    phi = require_positive(porosity, "porosity")
    mu = require_positive(viscosity_cp, "viscosity_cp")
    c_t = require_positive(total_compressibility_per_psi, "total_compressibility_per_psi")
    r_w = require_positive(wellbore_radius_ft, "wellbore_radius_ft")
    if phi >= 1.0:
        raise InvalidInputError(
            f"porosity={phi!r} is a fraction of bulk volume and must be below 1. A value "
            "in percent is the usual cause."
        )
    return TIME_FIELD_FACTOR * k * t / (phi * mu * c_t * r_w * r_w)


def dimensionless_pressure(
    pressure_drop: float,
    *,
    permeability_md: float,
    thickness_ft: float,
    rate_stb_per_day: float,
    formation_volume_factor: float,
    viscosity_cp: float,
) -> float:
    """Return ``p_D = k h dp / (141.2 q B mu)`` in oil-field units."""
    k = require_positive(permeability_md, "permeability_md")
    h = require_positive(thickness_ft, "thickness_ft")
    q = require_positive(rate_stb_per_day, "rate_stb_per_day")
    b = require_positive(formation_volume_factor, "formation_volume_factor")
    mu = require_positive(viscosity_cp, "viscosity_cp")
    return k * h * pressure_drop / (PRESSURE_FIELD_FACTOR * q * b * mu)


def pressure_drop_psi(
    dimensionless_pressure_value: float,
    *,
    permeability_md: float,
    thickness_ft: float,
    rate_stb_per_day: float,
    formation_volume_factor: float,
    viscosity_cp: float,
) -> float:
    """Return the field-unit drawdown for a dimensionless pressure. Inverse of the above."""
    k = require_positive(permeability_md, "permeability_md")
    h = require_positive(thickness_ft, "thickness_ft")
    q = require_positive(rate_stb_per_day, "rate_stb_per_day")
    b = require_positive(formation_volume_factor, "formation_volume_factor")
    mu = require_positive(viscosity_cp, "viscosity_cp")
    return dimensionless_pressure_value * PRESSURE_FIELD_FACTOR * q * b * mu / (k * h)


def permeability_from_semilog_slope(
    slope_psi_per_cycle: float,
    *,
    thickness_ft: float,
    rate_stb_per_day: float,
    formation_volume_factor: float,
    viscosity_cp: float,
) -> float:
    """Return ``k = 162.6 q B mu / (m h)`` from the magnitude of the semilog slope."""
    m = require_positive(abs(slope_psi_per_cycle), "slope_psi_per_cycle")
    h = require_positive(thickness_ft, "thickness_ft")
    q = require_positive(rate_stb_per_day, "rate_stb_per_day")
    b = require_positive(formation_volume_factor, "formation_volume_factor")
    mu = require_positive(viscosity_cp, "viscosity_cp")
    return semilog_slope_constant() * q * b * mu / (m * h)


def skin_from_semilog_line(
    *,
    pressure_drop_at_one_hour: float,
    slope_psi_per_cycle: float,
    permeability_md: float,
    porosity: float,
    viscosity_cp: float,
    total_compressibility_per_psi: float,
    wellbore_radius_ft: float,
) -> float:
    """Return the skin implied by a fitted semilog line.

    ``s = (ln10/2) [ dp_1hr/m - log10(k / (phi mu c_t r_w^2)) + 3.2275 ]``.

    ``pressure_drop_at_one_hour`` must come from the fitted line extrapolated to one
    hour, not from whichever measurement happens to sit nearest to it. On a log time axis
    a single point carries the local noise of one gauge reading straight into the skin,
    while the line carries the average of the window. The distinction is worth more than
    it looks: at the sampling densities used here the two differ by a good deal more than
    the acceptance threshold.
    """
    m = require_positive(abs(slope_psi_per_cycle), "slope_psi_per_cycle")
    k = require_positive(permeability_md, "permeability_md")
    phi = require_positive(porosity, "porosity")
    mu = require_positive(viscosity_cp, "viscosity_cp")
    c_t = require_positive(total_compressibility_per_psi, "total_compressibility_per_psi")
    r_w = require_positive(wellbore_radius_ft, "wellbore_radius_ft")
    group = k / (phi * mu * c_t * r_w * r_w)
    return (_LN10 / 2.0) * (pressure_drop_at_one_hour / m - math.log10(group) + semilog_skin_constant())


@dataclass(frozen=True)
class SemilogInterpretation:
    """What a semilog straight line says about a transient, and how well it fitted."""

    slope_psi_per_cycle: float
    intercept_psi: float
    pressure_drop_at_one_hour: float
    permeability_md: float
    permeability_thickness_md_ft: float
    skin: float
    r_squared: float
    residual_standard_error_psi: float
    points_used: int
    first_time_hours: float
    last_time_hours: float

    def describe(self) -> str:
        """Return a one-line summary for a log or a report."""
        return (
            f"k = {self.permeability_md:.6g} md, kh = "
            f"{self.permeability_thickness_md_ft:.6g} md.ft, s = {self.skin:.6g}, "
            f"from {self.points_used} points over "
            f"{self.first_time_hours:.6g}-{self.last_time_hours:.6g} hr"
        )


def semilog_interpretation(
    time_hours: Sequence[float],
    pressure_drop_psi_values: Sequence[float],
    *,
    thickness_ft: float,
    rate_stb_per_day: float,
    formation_volume_factor: float,
    viscosity_cp: float,
    porosity: float,
    total_compressibility_per_psi: float,
    wellbore_radius_ft: float,
) -> SemilogInterpretation:
    """Fit ``dp`` against ``log10 t`` and read permeability and skin off the line.

    This is the inverse path, and it is deliberately ignorant. It receives times and
    pressure drops and nothing else about where they came from: no permeability, no skin,
    no flag saying which model generated them. It cannot therefore return the right answer
    by echoing an input, which is the failure mode that makes a forward-inverse agreement
    worthless as evidence.

    It also does not choose its own window. The caller passes the points to fit, because
    selecting the interval is the interpretation step that carries the judgement, and
    burying it in a fitting routine would hide the decision that matters most.
    """
    times = as_float_sequence(time_hours, "time_hours")
    drops = as_float_sequence(pressure_drop_psi_values, "pressure_drop_psi_values")
    require_same_length(times, drops, "time_hours", "pressure_drop_psi_values")
    require_min_length(times, "time_hours", 3, "fitting a line and reporting its scatter")
    require_strictly_increasing(times, "time_hours")
    if times[0] <= 0.0:
        raise InvalidInputError(
            f"time_hours starts at {times[0]!r}. A semilog analysis takes the logarithm "
            "of elapsed time, so the first time must be strictly positive; a zero or "
            "negative entry usually means the time origin was not removed."
        )

    xs = [math.log10(t) for t in times]
    n = len(xs)
    mean_x = math.fsum(xs) / n
    mean_y = math.fsum(drops) / n
    s_xx = math.fsum((x - mean_x) ** 2 for x in xs)
    if s_xx <= 0.0:
        raise InvalidInputError(
            "every time in the window maps to the same log10 value, so no line can be "
            "fitted. A duplicated timestamp is the usual cause."
        )
    s_xy = math.fsum((x - mean_x) * (y - mean_y) for x, y in zip(xs, drops, strict=True))
    slope = s_xy / s_xx
    intercept = mean_y - slope * mean_x

    fitted = [intercept + slope * x for x in xs]
    ss_res = math.fsum((y - f) ** 2 for y, f in zip(drops, fitted, strict=True))
    ss_tot = math.fsum((y - mean_y) ** 2 for y in drops)
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 1.0
    residual_se = math.sqrt(ss_res / (n - 2)) if n > 2 else 0.0

    # The line at t = 1 hour, which is log10(t) = 0, so this is the intercept itself.
    drop_one_hour = intercept
    permeability = permeability_from_semilog_slope(
        slope,
        thickness_ft=thickness_ft,
        rate_stb_per_day=rate_stb_per_day,
        formation_volume_factor=formation_volume_factor,
        viscosity_cp=viscosity_cp,
    )
    skin = skin_from_semilog_line(
        pressure_drop_at_one_hour=drop_one_hour,
        slope_psi_per_cycle=slope,
        permeability_md=permeability,
        porosity=porosity,
        viscosity_cp=viscosity_cp,
        total_compressibility_per_psi=total_compressibility_per_psi,
        wellbore_radius_ft=wellbore_radius_ft,
    )
    return SemilogInterpretation(
        slope_psi_per_cycle=slope,
        intercept_psi=intercept,
        pressure_drop_at_one_hour=drop_one_hour,
        permeability_md=permeability,
        permeability_thickness_md_ft=permeability * thickness_ft,
        skin=skin,
        r_squared=r_squared,
        residual_standard_error_psi=residual_se,
        points_used=n,
        first_time_hours=times[0],
        last_time_hours=times[-1],
    )

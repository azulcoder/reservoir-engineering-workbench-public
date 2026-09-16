"""The B2 forward model: finite-radius well, constant wellbore storage, skin.

Why this lives in the case directory and not in ``reservoir_lab``
----------------------------------------------------------------
``reservoir_lab`` is standard-library only and that policy is worth keeping. This module
needs modified Bessel functions at **complex** argument, which ``math`` does not provide at
any argument, and a numerical inverse Laplace transform. ``mpmath`` supplies both. It is a
development and research dependency, pinned in ``requirements-dev.lock``, never imported by
``src/``. ``pyproject.toml`` already carries that convention for the case studies.

The model, from the frozen protocol
-----------------------------------
Pre-registered in ``protocol.md`` section 4.2 as amended, and derived rather than cited:

    p_wD_bar(u) = [K01(sqrt u) + S] / { u [1 + C_D u (K01(sqrt u) + S)] }      (B2-1)
    K01(x)      = K0(x) / (x K1(x))                                            (B2-2)

(B2-2) is the finite-radius constant-rate reservoir response. Solving the diffusivity
equation in Laplace space bounded at infinity gives ``p_D_bar = A K0(r_D sqrt u)``; the inner
boundary ``-d p_D_bar/d r_D = 1/u`` at ``r_D = 1`` forces ``A = 1/(u x K1(x))``.

**The factor ``x K1(x)`` is the well's finite surface.** The line source is its ``r_w -> 0``
limit, where ``x K1(x) -> 1``. An earlier version of this protocol used that limit and
consequently had no wellbore storage at all when the skin was zero -- a well with no radius
and no skin has no pressure drop to charge. ``PROTOCOL_AMENDMENT_01.md`` records the
correction. :func:`storage_asymptote_residual` is the regression that keeps it corrected.

Inversion
---------
de Hoog-Knight-Stokes is primary. Gaver-Stehfest at arbitrary precision is an **algorithmic
inversion cross-check**, not an independent physics oracle: both invert the same transform, so
a formulation error survives both. Settings are frozen in :data:`INVERSION` and are not tuned
per case.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

import mpmath as mp

__all__ = [
    "INVERSION",
    "InversionSettings",
    "WellboreStorageModel",
    "dimensionless_storage_coefficient",
    "k01",
    "laplace_wellbore_pressure",
    "storage_asymptote_residual",
]

#: 1 bbl in cubic feet. The C_D field constant 0.8936 is this over 2*pi; the derivation is
#: stored rather than the literal, as B1 does for 162.6, 70.6 and 3.2275.
BARREL_CUBIC_FEET = 5.614583


@dataclass(frozen=True)
class InversionSettings:
    """Frozen before any B2 experiment, per protocol section 4.5. Not tuned per case."""

    #: Working precision in decimal digits.
    dps: int = 30
    #: de Hoog degree. Qualified in C1 against transforms with known exact inverses.
    dehoog_degree: int = 18
    #: Gaver-Stehfest degree for the cross-check. Must be even.
    stehfest_degree: int = 16

    def __post_init__(self) -> None:
        """Reject settings that would make the rule meaningless."""
        if self.dps < 15:
            raise ValueError("dps below 15 defeats the purpose of arbitrary precision")
        if self.dehoog_degree < 6:
            raise ValueError("dehoog_degree is too small to converge")
        if self.stehfest_degree % 2:
            raise ValueError("Gaver-Stehfest requires an even degree")


#: The frozen settings. Qualification is criterion C1.
INVERSION = InversionSettings()


def dimensionless_storage_coefficient(
    storage_bbl_per_psi: float,
    *,
    porosity: float,
    total_compressibility_per_psi: float,
    thickness_ft: float,
    wellbore_radius_ft: float,
) -> float:
    """C_D = [1 bbl in ft3 / 2 pi] * C / (phi c_t h r_w^2), protocol section 4.4.

    The bracket is 0.8935886, which is the published 0.8936 to 1.1e-5. Derived here rather
    than stored, so the constant cannot drift from its definition.
    """
    for name, value in (
        ("storage_bbl_per_psi", storage_bbl_per_psi),
        ("porosity", porosity),
        ("total_compressibility_per_psi", total_compressibility_per_psi),
        ("thickness_ft", thickness_ft),
        ("wellbore_radius_ft", wellbore_radius_ft),
    ):
        if not (value == value and value not in (float("inf"), float("-inf"))):
            raise ValueError(f"{name} must be finite")
    if storage_bbl_per_psi < 0.0:
        raise ValueError("storage must not be negative")
    for name, value in (
        ("porosity", porosity),
        ("total_compressibility_per_psi", total_compressibility_per_psi),
        ("thickness_ft", thickness_ft),
        ("wellbore_radius_ft", wellbore_radius_ft),
    ):
        if value <= 0.0:
            raise ValueError(f"{name} must be strictly positive")
    import math

    denominator = porosity * total_compressibility_per_psi * thickness_ft * wellbore_radius_ft**2
    return (BARREL_CUBIC_FEET / (2.0 * math.pi)) * storage_bbl_per_psi / denominator


def k01(x):
    """K0(x) / (x K1(x)), the finite-radius reservoir response, equation (B2-2).

    Accepts real or complex ``x``; de Hoog needs complex. Evaluated as written rather than
    through an asymptotic shortcut, because the shortcut's validity boundary would become an
    unstated assumption of the whole case.

    For large ``|x|`` both Bessel functions underflow individually while their ratio stays
    finite and tends to 1. mpmath carries enough exponent range at the working precision that
    the ratio is formed without either operand reaching zero; :func:`k01_is_reliable` states
    where that stops being true rather than letting it fail silently.
    """
    x = mp.mpmathify(x)
    if x == 0:
        raise ValueError("k01 is singular at x = 0")
    return mp.besselk(0, x) / (x * mp.besselk(1, x))


def k01_is_reliable(x, *, dps: int = INVERSION.dps) -> bool:
    """Whether ``k01`` can be formed at ``x`` without an operand underflowing to zero.

    Declared rather than clamped: a value the method cannot compute is reported, not replaced
    by a plausible-looking substitute.
    """
    try:
        with mp.workdps(dps):
            xv = mp.mpmathify(x)
            k1 = mp.besselk(1, xv)
            return bool(k1 != 0 and mp.isfinite(mp.besselk(0, xv) / (xv * k1)))
    except (ValueError, ZeroDivisionError, OverflowError):
        return False


def laplace_wellbore_pressure(u, *, storage_dimensionless: float, skin: float):
    """Equation (B2-1): the dimensionless wellbore pressure in Laplace space.

    ``u`` may be complex. ``storage_dimensionless`` may be zero, which gives the storage-free
    finite-radius solution. ``skin`` may be zero -- that case is a mandatory regression, C3b,
    and is the defect the protocol amendment fixed.
    """
    if storage_dimensionless < 0.0:
        raise ValueError("C_D must not be negative")
    u = mp.mpmathify(u)
    if u == 0:
        raise ValueError("the transform is singular at u = 0")
    g = k01(mp.sqrt(u)) + mp.mpmathify(skin)
    return g / (u * (1 + mp.mpmathify(storage_dimensionless) * u * g))


@dataclass(frozen=True)
class WellboreStorageModel:
    """The forward model at declared dimensionless parameters.

    Holds no field units and no truth beyond its own two parameters; converting to and from
    field units is the caller's job, which keeps the unit conventions in one place.
    """

    storage_dimensionless: float
    skin: float
    settings: InversionSettings = INVERSION

    def transform(self) -> Callable:
        """Return the Laplace-domain function bound to these parameters."""

        def evaluate(u):
            return laplace_wellbore_pressure(
                u, storage_dimensionless=self.storage_dimensionless, skin=self.skin
            )

        return evaluate

    def pressure(self, t_d: float, *, method: str = "dehoog") -> float:
        """Dimensionless wellbore pressure at dimensionless time ``t_d``.

        ``method`` is ``"dehoog"`` for the primary result or ``"stehfest"`` for the
        algorithmic cross-check. The cross-check is not an independent oracle.
        """
        if t_d <= 0.0:
            raise ValueError("t_D must be strictly positive")
        with mp.workdps(self.settings.dps):
            degree = self.settings.dehoog_degree if method == "dehoog" else self.settings.stehfest_degree
            value = mp.invertlaplace(self.transform(), mp.mpf(t_d), method=method, degree=degree)
            return float(value)

    def log_derivative(self, t_d: float, *, relative_step: float = 1e-4) -> float:
        """D p_wD / d ln t_D, evaluated analytically on the inverted response.

        A central difference in ``ln t`` at the working precision, not the Bourdet estimate.
        The two are compared in criterion C7, which is only meaningful if they are computed
        differently.
        """
        with mp.workdps(self.settings.dps):
            h = mp.mpf(relative_step)
            lo = self.pressure(float(mp.e ** (mp.log(t_d) - h)))
            hi = self.pressure(float(mp.e ** (mp.log(t_d) + h)))
            return float((mp.mpf(hi) - mp.mpf(lo)) / (2 * h))

    def with_settings(self, **changes) -> WellboreStorageModel:
        """Return a copy at different inversion settings, for the qualification study only."""
        return replace(self, settings=replace(self.settings, **changes))


def storage_asymptote_residual(*, storage_dimensionless: float, skin: float, u_exponent: int = 10) -> float:
    """How far ``u^2 p_wD_bar`` is from ``1/C_D`` deep in the storage branch.

    The storage-dominated response is ``p_wD = t_D / C_D``, whose transform is
    ``1/(C_D u^2)``. So ``u^2 p_wD_bar -> 1/C_D`` as ``u -> infinity`` if and only if the model
    has a storage period at all.

    **This is the regression against the defect that motivated the protocol amendment.** The
    superseded line-source formulation returns something near 1.0 here at ``skin = 0`` -- it
    has no storage branch. The finite-radius formulation returns a residual near zero for any
    ``skin >= 0``.
    """
    if storage_dimensionless <= 0.0:
        raise ValueError("a storage asymptote needs C_D > 0")
    with mp.workdps(INVERSION.dps):
        u = mp.mpf(10) ** u_exponent
        scaled = u**2 * laplace_wellbore_pressure(u, storage_dimensionless=storage_dimensionless, skin=skin)
        target = 1 / mp.mpf(storage_dimensionless)
        return float(abs(scaled - target) / target)

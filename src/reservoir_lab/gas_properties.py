"""Gas PVT properties: pseudocriticals, deviation factor, density, viscosity, FVF.

Every correlation here is a *correlation*: a curve fitted to data over a stated window.
Three consequences are designed into the module rather than left to the caller.

1. Each solver reports its published validity window as a module constant, and each
   public entry point routes the reduced properties through
   :func:`~reservoir_lab.validation.check_range`. Evaluating outside the window is
   allowed and warned about, never silent.
2. Three independent Z-factor correlations are provided, not one. Two correlations
   agreeing is weak evidence that the *implementations* are right; two correlations
   disagreeing localises the problem. The test suite uses their mutual agreement as
   one check and an external reference dataset as another.
3. Iteration is bracketed (see :mod:`reservoir_lab.numerics`). A Z-factor routine that
   returns the last iterate after failing to converge is the origin of numbers that
   look reasonable and are not.

Unit system: field units, absolute pressure and absolute temperature throughout, per
``docs/api_contract.md`` C1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .errors import InvalidInputError
from .numerics import bracket_sign_change, safeguarded_newton
from .units import (
    CUBIC_FEET_PER_BARREL,
    GAS_CONSTANT_FIELD,
    StandardConditions,
    lbm_per_cuft_to_g_per_cc,
)
from .validation import (
    check_range,
    require_in_interval,
    require_positive,
)


def _require_computable_reduced(t_pr: float, p_pr: float, correlation: str) -> tuple[float, float]:
    """Reject pseudo-reduced properties outside the range the arithmetic can carry.

    Separate from :func:`~reservoir_lab.validation.check_range`, which warns about a
    deliberate excursion beyond a fitted window. This is a hard refusal for inputs where
    the evaluation itself loses meaning through underflow or overflow, and where a
    returned number would be indistinguishable from a real answer.
    """
    t = require_positive(t_pr, "t_pr")
    p = require_positive(p_pr, "p_pr")
    low_t, high_t = REDUCED_TEMPERATURE_BOUNDS
    low_p, high_p = REDUCED_PRESSURE_BOUNDS
    if not (low_t <= t <= high_t):
        raise InvalidInputError(
            f"{correlation}: t_pr={t!r} is outside the computable range [{low_t}, {high_t}]. "
            f"Terms in Tpr**5 underflow or overflow there and the result would be arithmetic "
            f"noise rather than a deviation factor."
        )
    if not (low_p <= p <= high_p):
        raise InvalidInputError(
            f"{correlation}: p_pr={p!r} is outside the computable range [{low_p}, {high_p}]. "
            f"A solve at that reduced pressure returns a number with no physical meaning and "
            f"nothing would mark it as meaningless."
        )
    return t, p


__all__ = [
    "DAK_RANGE",
    "DPR_RANGE",
    "HALL_YARBOROUGH_RANGE",
    "LGE_RANGE",
    "REDUCED_PRESSURE_BOUNDS",
    "REDUCED_TEMPERATURE_BOUNDS",
    "STANDING_DEFAULT_VARIANT",
    "STANDING_DRY_GAS_PRESSURE_CONSTANTS",
    "SUTTON_GRAVITY_RANGE",
    "WICHERT_AZIZ_RANGE",
    "PseudoCriticals",
    "gas_compressibility_per_psi",
    "gas_density_lbm_per_cuft",
    "gas_fvf_rb_per_scf",
    "gas_fvf_rcf_per_scf",
    "gas_viscosity_lee_gonzalez_eakin",
    "pseudocritical_standing",
    "pseudocritical_sutton",
    "reduced_density_dak",
    "wichert_aziz_correction",
    "z_factor",
    "z_factor_dak",
    "z_factor_dpr",
    "z_factor_hall_yarborough",
]

# ---------------------------------------------------------------------------
# Published validity windows, exposed so tests and reports can read them
# ---------------------------------------------------------------------------

#: Dranchuk & Abou-Kassem (1975): 1.0 <= Tpr <= 3.0, 0.2 <= Ppr <= 30.0.
DAK_RANGE = {"t_pr": (1.0, 3.0), "p_pr": (0.2, 30.0)}

#: Hall & Yarborough (1973). Not recommended below Tpr = 1.0; the published fit covers
#: roughly 1.2 <= Tpr <= 3.0 and Ppr up to 20-24 depending on the source consulted.
HALL_YARBOROUGH_RANGE = {"t_pr": (1.2, 3.0), "p_pr": (0.2, 20.0)}

#: Dranchuk, Purvis & Robinson (1974): 1.05 <= Tpr <= 3.0, 0.2 <= Ppr <= 30.0.
DPR_RANGE = {"t_pr": (1.05, 3.0), "p_pr": (0.2, 30.0)}

#: Lee, Gonzalez & Eakin (1966): fitted over roughly 100-8000 psia and 100-340 degF
#: on four natural gases with limited non-hydrocarbon content. The published average
#: deviation is a few percent; it is not a reference-quality transport model.
LGE_RANGE = {"temperature_degf": (100.0, 340.0), "pressure_psia": (100.0, 8000.0)}

#: Sutton (1985) regressed the Katz pseudocritical curves over this gravity range.
SUTTON_GRAVITY_RANGE = (0.57, 1.68)

#: Wichert & Aziz (1972) fitted their correction over roughly CO2 0-55 mol% and
#: H2S 0-74 mol%. Outside that composition the epsilon expression is an extrapolation.
WICHERT_AZIZ_RANGE = {"y_co2": (0.0, 0.55), "y_h2s": (0.0, 0.74)}

#: Hard computability bounds on the pseudo-reduced properties, distinct from the
#: correlations' published validity windows above. A window excursion is a modelling
#: choice a study may make deliberately, and warns. A value outside these bounds is not
#: a modelling choice: at Tpr = 1e-300 the term Tpr**5 underflows to zero and the DAK
#: polynomial divides by it, and at Ppr = 1e12 the Hall-Yarborough solve returns a
#: deviation factor of 3.6e10, which is a sentinel result in its worst form because
#: nothing marks it as meaningless. These raise.
REDUCED_TEMPERATURE_BOUNDS = (0.1, 100.0)
REDUCED_PRESSURE_BOUNDS = (1.0e-6, 1.0e6)

#: Standing (1977) pseudocriticals are quoted for roughly this gravity range.
STANDING_GRAVITY_RANGE = (0.55, 1.10)


# ---------------------------------------------------------------------------
# Pseudocritical properties
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PseudoCriticals:
    """Pseudocritical temperature and pressure of a gas mixture.

    Attributes
    ----------
    temperature_degr:
        Pseudocritical temperature, degrees Rankine.
    pressure_psia:
        Pseudocritical pressure, psia.
    correlation:
        Which correlation produced the base values.
    corrections:
        Corrections applied on top, in the order applied, e.g. ``("wichert-aziz",)``.
        Carried so that a report can state what the reduced properties actually mean.
    """

    temperature_degr: float
    pressure_psia: float
    correlation: str
    corrections: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate and normalise the fields after construction."""
        require_positive(self.temperature_degr, "temperature_degr")
        require_positive(self.pressure_psia, "pressure_psia")

    def reduced(self, pressure_psia: float, temperature_degr: float) -> tuple[float, float]:
        """Return ``(t_pr, p_pr)`` for an absolute pressure and temperature."""
        p = require_positive(pressure_psia, "pressure_psia")
        t = require_positive(temperature_degr, "temperature_degr")
        return t / self.temperature_degr, p / self.pressure_psia

    def describe(self) -> str:
        """One-line description for a report or run record."""
        suffix = f" + {'+'.join(self.corrections)}" if self.corrections else ""
        return (
            f"{self.correlation}{suffix}: Tpc = {self.temperature_degr:.2f} degR, "
            f"Ppc = {self.pressure_psia:.2f} psia"
        )


#: The constant term of Standing's dry-gas pseudocritical *pressure* correlation is
#: reported inconsistently in the secondary literature. Two values circulate:
#:
#:   677 + 15.0 g - 37.5 g^2      (Ahmed, Reservoir Engineering Handbook, Eq. 2-19,
#:                                 and the worked examples in that book)
#:   667 + 15.0 g - 37.5 g^2      (Whitson & Brule, SPE Monograph Vol. 20, Eq. 3.48b)
#:
#: The original is Standing's 1977 monograph, which was not consulted for this
#: repository, so the conflict is recorded rather than pronounced upon. Note that the
#: 677 form evaluates to 667.2 psia at gamma = 0.75, which is a plausible origin for
#: the discrepancy: a value quoted at one gravity being mistaken for the constant term.
#:
#: The practical consequence, measured rather than asserted. Over gamma 0.55 to 1.10 at
#: 500 to 6000 psia and 200 degF, with Z by Dranchuk-Abou-Kassem and Bg at SPE standard
#: conditions, the two forms differ by 10 psia in Ppc -- 1.53 percent on average -- and in
#: Z by 0.45 percent on average with a maximum of 1.15 percent. The maximum sits on the
#: corner of that grid, at gamma 1.10 and 6000 psia, so it is a lower bound on the maximum
#: over any wider range rather than a bound on it. The mean is not a bound and must not be
#: quoted as one.
#:
#: An earlier version of this comment said the difference "propagates to well under 1
#: percent in Z over the range this project uses" and that it "is not a difference that
#: changes a decision". The first is falsified by the 1.15 percent maximum above. The
#: second was never this comment's to assert: whether a difference changes a decision
#: depends on the decision, and nothing here establishes that. What remains true is that a
#: study which does not say which form it used cannot be reproduced exactly.
#:
#: The measurement is the one ``cases/A2_pvt_independent_check`` performs. That case's
#: outputs are not distributed with this repository because it also reads a NIST reference
#: extract that is not redistributed here; the 667-versus-677 comparison itself uses no
#: reference data and is reproducible from this module alone.
STANDING_DRY_GAS_PRESSURE_CONSTANTS = {"ahmed": 677.0, "whitson-brule": 667.0}

#: Which of the above is used when the caller does not choose. The Ahmed form is the
#: default because it is the one carried by the worked examples most readily available
#: for checking an implementation against, not because the conflict is settled.
STANDING_DEFAULT_VARIANT = "ahmed"


def pseudocritical_standing(
    specific_gravity: float,
    *,
    fluid: str = "dry_gas",
    variant: str = STANDING_DEFAULT_VARIANT,
    strict_range: bool = False,
) -> PseudoCriticals:
    """Standing (1977) pseudocritical properties from gas specific gravity.

    Two distinct fits are published and they are not interchangeable. ``"dry_gas"`` is
    the natural-gas-system fit; ``"wet_gas"`` is the gas-condensate-system fit. At
    gamma = 0.7 the two differ by about 12 degR in Tpc, which moves Tpr by roughly
    2 percent -- enough to matter near the critical region.

    Parameters
    ----------
    specific_gravity:
        Gas gravity relative to air.
    fluid:
        ``"dry_gas"`` or ``"wet_gas"``.
    variant:
        Which reported constant term to use in the dry-gas pressure correlation; see
        :data:`STANDING_DRY_GAS_PRESSURE_CONSTANTS`. Ignored for ``"wet_gas"``, whose
        constant term is not in dispute. The chosen variant is recorded in the returned
        object's ``correlation`` field so that it travels into the run record.
    """
    gamma = require_positive(specific_gravity, "specific_gravity")
    check_range(
        gamma,
        "specific_gravity",
        *STANDING_GRAVITY_RANGE,
        correlation="Standing (1977) pseudocriticals",
        strict=strict_range,
    )
    if fluid == "dry_gas":
        if variant not in STANDING_DRY_GAS_PRESSURE_CONSTANTS:
            raise InvalidInputError(
                f"variant must be one of {sorted(STANDING_DRY_GAS_PRESSURE_CONSTANTS)}, got {variant!r}"
            )
        constant = STANDING_DRY_GAS_PRESSURE_CONSTANTS[variant]
        t_pc = 168.0 + 325.0 * gamma - 12.5 * gamma**2
        p_pc = constant + 15.0 * gamma - 37.5 * gamma**2
        label = f"standing-1977-dry_gas[{variant}]"
    elif fluid == "wet_gas":
        t_pc = 187.0 + 330.0 * gamma - 71.5 * gamma**2
        p_pc = 706.0 - 51.7 * gamma - 11.1 * gamma**2
        label = "standing-1977-wet_gas"
    else:
        raise InvalidInputError(f"fluid must be 'dry_gas' or 'wet_gas', got {fluid!r}")
    return PseudoCriticals(t_pc, p_pc, correlation=label)


def pseudocritical_sutton(specific_gravity: float, *, strict_range: bool = False) -> PseudoCriticals:
    """Sutton (1985) pseudocritical properties from gas specific gravity.

    A regression of the Katz pseudocritical curves over 0.57 <= gamma <= 1.68, and the
    usual default for a rich or high-gravity gas where the Standing dry-gas fit is
    least reliable.
    """
    gamma = require_positive(specific_gravity, "specific_gravity")
    check_range(
        gamma,
        "specific_gravity",
        *SUTTON_GRAVITY_RANGE,
        correlation="Sutton (1985) pseudocriticals",
        strict=strict_range,
    )
    t_pc = 169.2 + 349.5 * gamma - 74.0 * gamma**2
    p_pc = 756.8 - 131.0 * gamma - 3.6 * gamma**2
    return PseudoCriticals(t_pc, p_pc, correlation="sutton-1985")


def wichert_aziz_correction(
    pseudocriticals: PseudoCriticals,
    *,
    y_h2s: float = 0.0,
    y_co2: float = 0.0,
    strict_range: bool = False,
) -> PseudoCriticals:
    """Wichert & Aziz (1972) correction for acid-gas content.

    ``A`` is the combined mole fraction of H2S and CO2, ``B`` the mole fraction of H2S
    alone::

        eps  = 120 (A**0.9 - A**1.6) + 15 (B**0.5 - B**4)
        Tpc' = Tpc - eps
        Ppc' = Ppc * Tpc' / (Tpc + B (1 - B) eps)

    Note that the denominator uses the **uncorrected** Tpc. Using the corrected value
    there is a common transcription error and shifts Ppc' in the wrong direction.

    Returns the input unchanged when both mole fractions are zero, so it is safe to
    apply unconditionally in a pipeline.
    """
    b = require_in_interval(y_h2s, "y_h2s", 0.0, 1.0)
    co2 = require_in_interval(y_co2, "y_co2", 0.0, 1.0)
    a = b + co2
    if a > 1.0:
        raise InvalidInputError(f"y_h2s + y_co2 must not exceed 1, got {a!r}")
    if a == 0.0:
        return pseudocriticals
    # The correlation was fitted over a bounded composition. Outside it the epsilon
    # expression still evaluates, which is exactly why the excursion has to be said out
    # loud: 80 percent CO2 returns a plausible-looking number from an extrapolation.
    check_range(
        co2,
        "y_co2",
        *WICHERT_AZIZ_RANGE["y_co2"],
        correlation="Wichert-Aziz (1972)",
        strict=strict_range,
    )
    check_range(
        b,
        "y_h2s",
        *WICHERT_AZIZ_RANGE["y_h2s"],
        correlation="Wichert-Aziz (1972)",
        strict=strict_range,
    )

    epsilon = 120.0 * (a**0.9 - a**1.6) + 15.0 * (b**0.5 - b**4)
    t_pc = pseudocriticals.temperature_degr
    t_corrected = t_pc - epsilon
    if t_corrected <= 0.0:
        raise InvalidInputError(
            f"Wichert-Aziz correction drove Tpc non-positive ({t_corrected!r}); "
            f"check the acid-gas mole fractions"
        )
    p_corrected = pseudocriticals.pressure_psia * t_corrected / (t_pc + b * (1.0 - b) * epsilon)
    return PseudoCriticals(
        t_corrected,
        p_corrected,
        correlation=pseudocriticals.correlation,
        corrections=(*pseudocriticals.corrections, "wichert-aziz-1972"),
    )


# ---------------------------------------------------------------------------
# Dranchuk & Abou-Kassem (1975)
# ---------------------------------------------------------------------------

_DAK = (
    0.3265,
    -1.0700,
    -0.5339,
    0.01569,
    -0.05165,
    0.5475,
    -0.7361,
    0.1844,
    0.1056,
    0.6134,
    0.7210,
)


def _dak_terms(t_pr: float) -> tuple[float, float, float, float, float]:
    """Temperature-only groups of the DAK polynomial, computed once per call."""
    a1, a2, a3, a4, a5, a6, a7, a8, a9, a10, a11 = _DAK
    c1 = a1 + a2 / t_pr + a3 / t_pr**3 + a4 / t_pr**4 + a5 / t_pr**5
    c2 = a6 + a7 / t_pr + a8 / t_pr**2
    c3 = a9 * (a7 / t_pr + a8 / t_pr**2)
    c4_coefficient = a10 / t_pr**3
    return c1, c2, c3, c4_coefficient, a11


def _dak_z_of_reduced_density(rho_r: float, t_pr: float) -> float:
    c1, c2, c3, c4_coefficient, a11 = _dak_terms(t_pr)
    u = a11 * rho_r**2
    exponential_term = c4_coefficient * rho_r**2 * (1.0 + u) * math.exp(-u)
    return 1.0 + c1 * rho_r + c2 * rho_r**2 - c3 * rho_r**5 + exponential_term


def _dak_dz_drho(rho_r: float, t_pr: float) -> float:
    """Analytic dZ/d(rho_r) at fixed Tpr.

    The exponential group differentiates to a compact form. With ``u = A11 rho_r**2``::

        d/drho [ (A10/Tpr**3) rho**2 (1 + u) exp(-u) ]
            = (2 A10 rho / Tpr**3) exp(-u) (1 + u - u**2)

    which the test suite checks against a central difference.
    """
    c1, c2, c3, c4_coefficient, a11 = _dak_terms(t_pr)
    u = a11 * rho_r**2
    d_exponential = 2.0 * c4_coefficient * rho_r * math.exp(-u) * (1.0 + u - u**2)
    return c1 + 2.0 * c2 * rho_r - 5.0 * c3 * rho_r**4 + d_exponential


def reduced_density_dak(
    t_pr: float,
    p_pr: float,
    *,
    tolerance: float = 1.0e-12,
    max_iterations: int = 100,
    strict_range: bool = False,
) -> float:
    """Solve the DAK correlation for reduced density ``rho_r``.

    The residual solved is ``F(rho_r) = rho_r * Z(rho_r) - 0.27 * Ppr / Tpr``, which
    follows from the definition ``rho_r = 0.27 Ppr / (Z Tpr)``. ``F`` is negative as
    ``rho_r -> 0`` and grows without bound, so a bracket always exists and is found by
    geometric expansion rather than assumed.
    """
    t, p = _require_computable_reduced(t_pr, p_pr, "Dranchuk-Abou-Kassem (1975)")
    check_range(
        t,
        "t_pr",
        *DAK_RANGE["t_pr"],
        correlation="Dranchuk-Abou-Kassem (1975)",
        strict=strict_range,
    )
    check_range(
        p,
        "p_pr",
        *DAK_RANGE["p_pr"],
        correlation="Dranchuk-Abou-Kassem (1975)",
        strict=strict_range,
    )

    target = 0.27 * p / t

    def residual(rho: float) -> float:
        return rho * _dak_z_of_reduced_density(rho, t) - target

    def residual_derivative(rho: float) -> float:
        return _dak_z_of_reduced_density(rho, t) + rho * _dak_dz_drho(rho, t)

    bracket = bracket_sign_change(residual, lower=1.0e-14, upper_guess=max(1.0, 2.0 * target))
    return safeguarded_newton(
        residual,
        residual_derivative,
        bracket=bracket,
        initial_guess=target,  # the Z = 1 ideal-gas estimate
        tolerance=tolerance,
        max_iterations=max_iterations,
        description="DAK reduced density",
    )


def z_factor_dak(
    t_pr: float,
    p_pr: float,
    *,
    tolerance: float = 1.0e-12,
    max_iterations: int = 100,
    strict_range: bool = False,
) -> float:
    """Gas deviation factor by the Dranchuk & Abou-Kassem (1975) eleven-constant fit.

    The most widely used explicit fit to the Standing-Katz chart. Published validity
    is ``1.0 <= Tpr <= 3.0`` and ``0.2 <= Ppr <= 30``.
    """
    rho_r = reduced_density_dak(
        t_pr, p_pr, tolerance=tolerance, max_iterations=max_iterations, strict_range=strict_range
    )
    return 0.27 * p_pr / (rho_r * t_pr)


# ---------------------------------------------------------------------------
# Hall & Yarborough (1973)
# ---------------------------------------------------------------------------


def _hall_yarborough_groups(t_pr: float) -> tuple[float, float, float, float]:
    t = 1.0 / t_pr
    a = 0.06125 * t * math.exp(-1.2 * (1.0 - t) ** 2)
    b = 14.76 * t - 9.76 * t**2 + 4.58 * t**3
    c = 90.7 * t - 242.2 * t**2 + 42.4 * t**3
    d = 2.18 + 2.82 * t
    return a, b, c, d


def z_factor_hall_yarborough(
    t_pr: float,
    p_pr: float,
    *,
    tolerance: float = 1.0e-12,
    max_iterations: int = 100,
    strict_range: bool = False,
) -> float:
    """Gas deviation factor by the Hall & Yarborough (1973) Starling-Carnahan fit.

    Solves for the reduced density ``Y`` in ``(0, 1)``::

        F(Y) = -A Ppr + (Y + Y^2 + Y^3 - Y^4)/(1-Y)^3 - B Y^2 + C Y^D = 0
        Z    = A Ppr / Y

    with ``t = 1/Tpr`` and ``A = 0.06125 t exp(-1.2 (1-t)^2)``.

    Structurally independent of DAK -- a different functional family fitted by different
    authors -- which is what makes the agreement between the two a meaningful check
    rather than a restatement.
    """
    t, p = _require_computable_reduced(t_pr, p_pr, "Hall-Yarborough (1973)")
    check_range(
        t,
        "t_pr",
        *HALL_YARBOROUGH_RANGE["t_pr"],
        correlation="Hall-Yarborough (1973)",
        strict=strict_range,
    )
    check_range(
        p,
        "p_pr",
        *HALL_YARBOROUGH_RANGE["p_pr"],
        correlation="Hall-Yarborough (1973)",
        strict=strict_range,
    )

    a, b, c, d = _hall_yarborough_groups(t)

    def residual(y: float) -> float:
        one_minus = 1.0 - y
        value: float = -a * p + (y + y**2 + y**3 - y**4) / one_minus**3 - b * y**2 + c * y**d
        return value

    def residual_derivative(y: float) -> float:
        one_minus = 1.0 - y
        value: float = (
            (1.0 + 4.0 * y + 4.0 * y**2 - 4.0 * y**3 + y**4) / one_minus**4
            - 2.0 * b * y
            + c * d * y ** (d - 1.0)
        )
        return value

    # F(0+) = -A*Ppr < 0 and F(1-) -> +inf, so the bracket is analytic.
    upper = 1.0 - 1.0e-12
    y = safeguarded_newton(
        residual,
        residual_derivative,
        bracket=(1.0e-14, upper),
        initial_guess=min(
            0.9, max(1.0e-10, 0.0125 * p * (1.0 / t_pr) * math.exp(-1.2 * (1.0 - 1.0 / t_pr) ** 2))
        ),
        tolerance=tolerance,
        max_iterations=max_iterations,
        description="Hall-Yarborough reduced density",
    )
    return a * p / y


# ---------------------------------------------------------------------------
# Dranchuk, Purvis & Robinson (1974)
# ---------------------------------------------------------------------------

_DPR = (
    0.31506237,
    -1.04670990,
    -0.57832729,
    0.53530771,
    -0.61232032,
    -0.10488813,
    0.68157001,
    0.68446549,
)


def _dpr_z_of_reduced_density(rho_r: float, t_pr: float) -> float:
    a1, a2, a3, a4, a5, a6, a7, a8 = _DPR
    u = a8 * rho_r**2
    return (
        1.0
        + (a1 + a2 / t_pr + a3 / t_pr**3) * rho_r
        + (a4 + a5 / t_pr) * rho_r**2
        + (a5 * a6 * rho_r**5) / t_pr
        + (a7 * rho_r**2 / t_pr**3) * (1.0 + u) * math.exp(-u)
    )


def _dpr_dz_drho(rho_r: float, t_pr: float) -> float:
    a1, a2, a3, a4, a5, a6, a7, a8 = _DPR
    u = a8 * rho_r**2
    return (
        (a1 + a2 / t_pr + a3 / t_pr**3)
        + 2.0 * (a4 + a5 / t_pr) * rho_r
        + 5.0 * (a5 * a6 * rho_r**4) / t_pr
        + (2.0 * a7 * rho_r / t_pr**3) * math.exp(-u) * (1.0 + u - u**2)
    )


def z_factor_dpr(
    t_pr: float,
    p_pr: float,
    *,
    tolerance: float = 1.0e-12,
    max_iterations: int = 100,
    strict_range: bool = False,
) -> float:
    """Gas deviation factor by the Dranchuk, Purvis & Robinson (1974) eight-constant fit.

    The predecessor of DAK by the same group, kept as a third opinion. It shares the
    Benedict-Webb-Rubin ancestry with DAK, so it is *less* independent of DAK than
    Hall-Yarborough is; the test suite treats it accordingly.
    """
    t, p = _require_computable_reduced(t_pr, p_pr, "Dranchuk-Purvis-Robinson (1974)")
    check_range(
        t,
        "t_pr",
        *DPR_RANGE["t_pr"],
        correlation="Dranchuk-Purvis-Robinson (1974)",
        strict=strict_range,
    )
    check_range(
        p,
        "p_pr",
        *DPR_RANGE["p_pr"],
        correlation="Dranchuk-Purvis-Robinson (1974)",
        strict=strict_range,
    )

    target = 0.27 * p / t

    def residual(rho: float) -> float:
        return rho * _dpr_z_of_reduced_density(rho, t) - target

    def residual_derivative(rho: float) -> float:
        return _dpr_z_of_reduced_density(rho, t) + rho * _dpr_dz_drho(rho, t)

    bracket = bracket_sign_change(residual, lower=1.0e-14, upper_guess=max(1.0, 2.0 * target))
    rho_r = safeguarded_newton(
        residual,
        residual_derivative,
        bracket=bracket,
        initial_guess=target,
        tolerance=tolerance,
        max_iterations=max_iterations,
        description="DPR reduced density",
    )
    return 0.27 * p / (rho_r * t)


_Z_METHODS = {
    "dak": z_factor_dak,
    "hall-yarborough": z_factor_hall_yarborough,
    "dpr": z_factor_dpr,
}


def z_factor(
    pressure_psia: float,
    temperature_degr: float,
    pseudocriticals: PseudoCriticals,
    *,
    method: str = "dak",
    tolerance: float = 1.0e-12,
    max_iterations: int = 100,
    strict_range: bool = False,
) -> float:
    """Gas deviation factor at an absolute pressure and temperature.

    Parameters
    ----------
    method:
        ``"dak"``, ``"hall-yarborough"`` or ``"dpr"``.
    """
    if method not in _Z_METHODS:
        raise InvalidInputError(f"method must be one of {sorted(_Z_METHODS)}, got {method!r}")
    t_pr, p_pr = pseudocriticals.reduced(pressure_psia, temperature_degr)
    return _Z_METHODS[method](
        t_pr, p_pr, tolerance=tolerance, max_iterations=max_iterations, strict_range=strict_range
    )


# ---------------------------------------------------------------------------
# Density, viscosity, compressibility, formation volume factor
# ---------------------------------------------------------------------------


def gas_density_lbm_per_cuft(
    pressure_psia: float, temperature_degr: float, z_factor_value: float, molar_mass: float
) -> float:
    """Real-gas mass density, ``rho = p M / (Z R T)``, in lbm/ft^3.

    ``molar_mass`` is in lbm/lbmol; use
    :func:`~reservoir_lab.units.specific_gravity_to_molar_mass` to obtain it from gas
    gravity. ``R`` is :data:`~reservoir_lab.units.GAS_CONSTANT_FIELD`, derived from the
    SI-defined molar gas constant rather than transcribed.
    """
    p = require_positive(pressure_psia, "pressure_psia")
    t = require_positive(temperature_degr, "temperature_degr")
    z = require_positive(z_factor_value, "z_factor_value")
    m = require_positive(molar_mass, "molar_mass")
    return p * m / (z * GAS_CONSTANT_FIELD * t)


def gas_viscosity_lee_gonzalez_eakin(
    temperature_degr: float,
    molar_mass: float,
    density_lbm_per_cuft: float,
    *,
    strict_range: bool = False,
) -> float:
    """Lee, Gonzalez & Eakin (1966) gas viscosity, in centipoise.

    ::

        K   = (9.379 + 0.01607 M) T^1.5 / (209.2 + 19.26 M + T)
        X   = 3.448 + 986.4 / T + 0.01009 M
        Y   = 2.447 - 0.2224 X
        mu  = 1e-4 K exp(X rho^Y)

    with ``T`` in degrees Rankine, ``M`` in lbm/lbmol and ``rho`` in **g/cm^3**. The
    density conversion from lbm/ft^3 is performed here so that a caller working in
    field units cannot forget it; passing a field-unit density straight into the
    exponential is the classic way to get a viscosity wrong by orders of magnitude.

    The coefficients above are the commonly tabulated form. The original paper also
    appears in a rounded form (9.4, 0.02, 209, 19); the two differ by well under the
    correlation's own quoted accuracy of a few percent, but they are not identical, and
    a comparison against an external reference should not attribute that difference to
    an implementation error.
    """
    t = require_positive(temperature_degr, "temperature_degr")
    m = require_positive(molar_mass, "molar_mass")
    rho_field = require_positive(density_lbm_per_cuft, "density_lbm_per_cuft")
    check_range(
        t - 459.67,
        "temperature_degf",
        *LGE_RANGE["temperature_degf"],
        correlation="Lee-Gonzalez-Eakin (1966)",
        strict=strict_range,
    )
    rho = lbm_per_cuft_to_g_per_cc(rho_field)
    k = (9.379 + 0.01607 * m) * t**1.5 / (209.2 + 19.26 * m + t)
    x = 3.448 + 986.4 / t + 0.01009 * m
    y = 2.447 - 0.2224 * x
    # The exponential is the whole correlation, and it overflows long before the density
    # reaches anything a caller would notice as absurd. Checking the exponent rather than
    # catching OverflowError afterwards lets the message name the argument at fault.
    exponent = x * rho**y
    if exponent > 700.0:
        raise InvalidInputError(
            f"Lee-Gonzalez-Eakin: density_lbm_per_cuft={rho_field!r} gives an exponent of "
            f"{exponent:.3e}, which overflows. A gas density this high is outside any "
            f"reservoir condition; check the unit of the density supplied."
        )
    viscosity_cp: float = 1.0e-4 * k * math.exp(exponent)
    return viscosity_cp


def gas_compressibility_per_psi(
    pressure_psia: float,
    temperature_degr: float,
    pseudocriticals: PseudoCriticals,
    *,
    method: str = "dak",
    strict_range: bool = False,
) -> float:
    """Isothermal gas compressibility, 1/psi, from the analytic derivative of the correlation.

    ``c_g = 1/p - (1/Z)(dZ/dp)_T``. In pseudo-reduced form, with ``Z`` expressed through
    reduced density::

        c_r = 1/Ppr - [0.27 / (Z^2 Tpr)] * (dZ/drho) / (1 + (rho/Z)(dZ/drho))
        c_g = c_r / Ppc

    The derivative is analytic, obtained by differentiating the correlation through
    reduced density and applying the chain rule to the implicit dependence
    ``rho = 0.27 Ppr / (Z Tpr)``. A finite difference is used in the test suite as an
    oracle for this expression, never as the production path: near the critical region
    ``dZ/dp`` is steep and a fixed finite-difference step is inaccurate exactly where
    ``c_g`` matters most.
    """
    if method not in {"dak", "dpr"}:
        raise InvalidInputError(
            f"analytic compressibility is available for 'dak' and 'dpr', got {method!r}. "
            f"Hall-Yarborough solves for a different reduced variable and would need its "
            f"own derivative; it is not silently substituted."
        )
    t_pr, p_pr = pseudocriticals.reduced(pressure_psia, temperature_degr)
    if method == "dak":
        rho_r = reduced_density_dak(t_pr, p_pr, strict_range=strict_range)
        z_value = 0.27 * p_pr / (rho_r * t_pr)
        dz_drho = _dak_dz_drho(rho_r, t_pr)
    else:
        z_value = z_factor_dpr(t_pr, p_pr, strict_range=strict_range)
        rho_r = 0.27 * p_pr / (z_value * t_pr)
        dz_drho = _dpr_dz_drho(rho_r, t_pr)

    reduced_compressibility = 1.0 / p_pr - (0.27 / (z_value**2 * t_pr)) * (
        dz_drho / (1.0 + (rho_r / z_value) * dz_drho)
    )
    return reduced_compressibility / pseudocriticals.pressure_psia


def gas_fvf_rcf_per_scf(
    pressure_psia: float,
    temperature_degr: float,
    z_factor_value: float,
    standard: StandardConditions,
) -> float:
    """Gas formation volume factor in reservoir ft^3 per standard ft^3.

    ::

        Bg = (p_sc / (Z_sc T_sc)) * (Z T / p)

    The leading group is computed from the supplied :class:`StandardConditions` rather
    than hard-coded as 0.02827, because that familiar number silently assumes
    14.696 psia, 60 degF and Z_sc = 1. On the US contractual base of 14.73 psia the
    coefficient is 0.02834, a 0.23 percent difference carried into every standard
    volume the study reports.
    """
    p = require_positive(pressure_psia, "pressure_psia")
    t = require_positive(temperature_degr, "temperature_degr")
    z = require_positive(z_factor_value, "z_factor_value")
    coefficient = standard.pressure_psia / (standard.z_factor * standard.temperature_rankine)
    return coefficient * z * t / p


def gas_fvf_rb_per_scf(
    pressure_psia: float,
    temperature_degr: float,
    z_factor_value: float,
    standard: StandardConditions,
) -> float:
    """Gas formation volume factor in reservoir barrels per standard ft^3."""
    return (
        gas_fvf_rcf_per_scf(pressure_psia, temperature_degr, z_factor_value, standard) / CUBIC_FEET_PER_BARREL
    )

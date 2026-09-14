"""Units, exact conversion factors and standard-condition handling.

Design rule
-----------
Every conversion factor in this module is either (a) exact by definition of the unit,
or (b) derived arithmetically from factors that are exact by definition. Nothing is a
number copied out of a table. The gas constant in oilfield units, for example, is
computed here from the SI-defined molar gas constant and the exact inch-pound
definitions rather than being transcribed as ``10.7316``. A transcription error in a
constant is a class of defect that this arrangement removes entirely.

The one value that is *not* exact is :data:`STANDARD_AIR_MOLAR_MASS`, which depends on
an assumed dry-air composition. Its provenance is recorded next to it.

Standard conditions
-------------------
A gas volume is meaningless without the standard conditions it was measured against.
Several incompatible conventions are in routine use, and they differ by enough to
matter: 14.73 psia versus 14.696 psia is a 0.23 percent difference in every standard
volume, which is larger than the tolerance this project applies to its own numerics.
:class:`StandardConditions` therefore has no module-level default that functions fall
back to silently; callers pass one explicitly and it travels with the result.
"""

from __future__ import annotations

from dataclasses import dataclass

from .validation import require_finite, require_positive

# ---------------------------------------------------------------------------
# Exact-by-definition anchors
# ---------------------------------------------------------------------------

#: Molar gas constant. Exact since the 2019 SI redefinition fixed both the Boltzmann
#: constant and the Avogadro constant. Units: J/(mol K) == Pa m^3/(mol K).
GAS_CONSTANT_SI = 8.314462618153240

#: Exact by international yard-and-pound agreement (1959).
POUND_MASS_IN_GRAMS = 453.59237
FOOT_IN_METRES = 0.3048
INCH_IN_METRES = 0.0254

#: Exact: the pound per square inch is defined from the standard gravity value
#: 9.80665 m/s^2, itself exact by definition.
STANDARD_GRAVITY_SI = 9.80665
PSI_IN_PASCAL = POUND_MASS_IN_GRAMS * 1e-3 * STANDARD_GRAVITY_SI / (INCH_IN_METRES**2)

#: Exact: the Rankine degree is five ninths of a kelvin.
RANKINE_IN_KELVIN = 5.0 / 9.0

#: Exact: the US petroleum barrel is 42 US liquid gallons, each of 231 cubic inches.
CUBIC_INCHES_PER_US_GALLON = 231.0
US_GALLONS_PER_BARREL = 42.0
CUBIC_FEET_PER_BARREL = US_GALLONS_PER_BARREL * CUBIC_INCHES_PER_US_GALLON / 12.0**3  # 5.614583333...

#: Exact, derived from the two exact length definitions above.
CUBIC_FOOT_IN_CUBIC_METRES = FOOT_IN_METRES**3

# ---------------------------------------------------------------------------
# Derived constants
# ---------------------------------------------------------------------------

#: Molar gas constant in oilfield units, psia ft^3 / (lbmol degR).
#:
#: Derivation, each step exact::
#:
#:     Pa m^3 / (mol K)
#:       x POUND_MASS_IN_GRAMS       -> Pa m^3 / (lbmol K)     (mol -> lbmol)
#:       x RANKINE_IN_KELVIN         -> Pa m^3 / (lbmol degR)  (per K -> per degR)
#:       / CUBIC_FOOT_IN_CUBIC_METRES-> Pa ft^3 / (lbmol degR)
#:       / PSI_IN_PASCAL             -> psia ft^3 / (lbmol degR)
#:
#: Evaluates to 10.731 577... , which is the familiar 10.7316.
GAS_CONSTANT_FIELD = (
    GAS_CONSTANT_SI * POUND_MASS_IN_GRAMS * RANKINE_IN_KELVIN / CUBIC_FOOT_IN_CUBIC_METRES / PSI_IN_PASCAL
)

#: Molar mass of dry air, lbm/lbmol. NOT exact: it depends on an assumed composition.
#: 28.9647 g/mol is the value adopted by the US Standard Atmosphere (1976) and is the
#: figure conventionally used when converting gas specific gravity to molar mass. A
#: different assumed composition shifts it in the fourth significant figure, which is
#: below the accuracy of any Z-factor correlation in this package.
STANDARD_AIR_MOLAR_MASS = 28.9647
STANDARD_AIR_MOLAR_MASS_SOURCE = "US Standard Atmosphere 1976, dry-air mean molar mass"

#: Absolute zero expressed on the Fahrenheit and Celsius scales. Exact by definition.
ABSOLUTE_ZERO_DEGF = -459.67
ABSOLUTE_ZERO_DEGC = -273.15

#: One standard atmosphere, exact by definition, in psia.
ATMOSPHERE_PSIA = 101325.0 / PSI_IN_PASCAL

#: Centipoise per micropascal-second. Exact: 1 cp = 1 mPa s = 1000 uPa s.
MICROPASCAL_SECOND_IN_CENTIPOISE = 1.0e-3

#: Grams per cubic centimetre per pound-mass per cubic foot. Exact.
LBM_PER_CUFT_IN_G_PER_CC = POUND_MASS_IN_GRAMS / (CUBIC_FOOT_IN_CUBIC_METRES * 1.0e6)


# ---------------------------------------------------------------------------
# Temperature
# ---------------------------------------------------------------------------


def fahrenheit_to_rankine(degf: float) -> float:
    """Convert degrees Fahrenheit to degrees Rankine (absolute)."""
    degf = require_finite(degf, "degf")
    return degf - ABSOLUTE_ZERO_DEGF


def rankine_to_fahrenheit(degr: float) -> float:
    """Convert degrees Rankine to degrees Fahrenheit."""
    degr = require_finite(degr, "degr")
    return degr + ABSOLUTE_ZERO_DEGF


def celsius_to_kelvin(degc: float) -> float:
    """Convert degrees Celsius to kelvin (absolute)."""
    degc = require_finite(degc, "degc")
    return degc - ABSOLUTE_ZERO_DEGC


def kelvin_to_rankine(kelvin: float) -> float:
    """Convert kelvin to degrees Rankine."""
    kelvin = require_finite(kelvin, "kelvin")
    return kelvin / RANKINE_IN_KELVIN


def rankine_to_kelvin(degr: float) -> float:
    """Convert degrees Rankine to kelvin."""
    degr = require_finite(degr, "degr")
    return degr * RANKINE_IN_KELVIN


# ---------------------------------------------------------------------------
# Pressure
# ---------------------------------------------------------------------------


def psi_to_pascal(psi: float) -> float:
    """Convert pounds per square inch to pascals."""
    psi = require_finite(psi, "psi")
    return psi * PSI_IN_PASCAL


def pascal_to_psi(pascal: float) -> float:
    """Convert pascals to pounds per square inch."""
    pascal = require_finite(pascal, "pascal")
    return pascal / PSI_IN_PASCAL


def gauge_to_absolute(psig: float, atmospheric_psia: float = ATMOSPHERE_PSIA) -> float:
    """Convert gauge pressure to absolute pressure.

    The local atmospheric pressure is an explicit argument because it is a site
    property, not a universal constant; at 1500 m elevation the standard-atmosphere
    default is wrong by about 2 psi, which is not negligible in a late-life depleted
    gas reservoir where the total remaining drawdown may be only a few hundred psi.
    """
    psig = require_finite(psig, "psig")
    atmospheric_psia = require_finite(atmospheric_psia, "atmospheric_psia")
    return psig + atmospheric_psia


def absolute_to_gauge(psia: float, atmospheric_psia: float = ATMOSPHERE_PSIA) -> float:
    """Convert absolute pressure to gauge pressure. See :func:`gauge_to_absolute`."""
    psia = require_finite(psia, "psia")
    atmospheric_psia = require_finite(atmospheric_psia, "atmospheric_psia")
    return psia - atmospheric_psia


# ---------------------------------------------------------------------------
# Volume, density, viscosity
# ---------------------------------------------------------------------------


def barrels_to_cubic_feet(barrels: float) -> float:
    """Convert US petroleum barrels to cubic feet."""
    barrels = require_finite(barrels, "barrels")
    return barrels * CUBIC_FEET_PER_BARREL


def cubic_feet_to_barrels(cubic_feet: float) -> float:
    """Convert cubic feet to US petroleum barrels."""
    cubic_feet = require_finite(cubic_feet, "cubic_feet")
    return cubic_feet / CUBIC_FEET_PER_BARREL


def lbm_per_cuft_to_g_per_cc(density: float) -> float:
    """Convert mass density from lbm/ft^3 to g/cm^3."""
    density = require_finite(density, "density")
    return density * LBM_PER_CUFT_IN_G_PER_CC


def micropascal_second_to_centipoise(viscosity: float) -> float:
    """Convert dynamic viscosity from micropascal-seconds to centipoise."""
    viscosity = require_finite(viscosity, "viscosity")
    return viscosity * MICROPASCAL_SECOND_IN_CENTIPOISE


def specific_gravity_to_molar_mass(specific_gravity: float) -> float:
    """Convert gas specific gravity (air = 1) to molar mass in lbm/lbmol."""
    specific_gravity = require_finite(specific_gravity, "specific_gravity")
    return specific_gravity * STANDARD_AIR_MOLAR_MASS


def molar_mass_to_specific_gravity(molar_mass: float) -> float:
    """Convert gas molar mass in lbm/lbmol to specific gravity (air = 1)."""
    molar_mass = require_finite(molar_mass, "molar_mass")
    return molar_mass / STANDARD_AIR_MOLAR_MASS


# ---------------------------------------------------------------------------
# Standard conditions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StandardConditions:
    """The reference state a standard gas volume is quoted against.

    Attributes
    ----------
    pressure_psia:
        Absolute standard pressure.
    temperature_degf:
        Standard temperature.
    z_factor:
        Gas deviation factor at the standard state. Conventionally taken as exactly
        1.0 for a dry hydrocarbon gas at these conditions; the real value for methane
        at 14.696 psia and 60 degF is about 0.9977, a 0.23 percent effect. It is kept
        as a field so that a study which cares can supply the real value and so that
        the assumption is visible rather than buried.
    label:
        Human-readable identifier carried through into reports.

    Notes
    -----
    There is no module-level default. A function that needs standard conditions takes
    them as an argument, because the difference between the common conventions is
    larger than this project's numerical tolerances.
    """

    pressure_psia: float
    temperature_degf: float
    z_factor: float = 1.0
    label: str = "unspecified"

    def __post_init__(self) -> None:
        """Validate the fields after construction.

        Written as explicit guard calls rather than as comparisons. ``not (p > 0.0)``
        looks like it rejects NaN and does not: every comparison against NaN is False,
        so ``p > 0.0`` is False and ``not`` makes the guard appear to fire -- while the
        symmetric form ``t <= 0.0`` used for temperature is also False for NaN and lets
        it straight through. A NaN standard temperature then travels silently with every
        standard volume computed against it. ``require_positive`` checks finiteness
        first, so both cases are refused the same way, and the exception is
        ``InvalidInputError`` as contract C3 requires.
        """
        require_positive(self.pressure_psia, "standard pressure_psia")
        require_finite(self.temperature_degf, "standard temperature_degf")
        require_positive(self.temperature_rankine, "standard temperature (absolute)")
        require_positive(self.z_factor, "standard z_factor")

    @property
    def temperature_rankine(self) -> float:
        """Standard temperature in degrees Rankine."""
        return fahrenheit_to_rankine(self.temperature_degf)

    def describe(self) -> str:
        """One-line description suitable for a report header or a run record."""
        return (
            f"{self.label}: {self.pressure_psia:g} psia, {self.temperature_degf:g} degF, "
            f"Z_sc = {self.z_factor:g}"
        )


#: 14.696 psia and 60 degF. The convention used by SPE and by most international
#: reporting. Also the basis on which the WebBook's default reference state is
#: normally interpreted in petroleum work.
SPE_STANDARD = StandardConditions(
    pressure_psia=ATMOSPHERE_PSIA,
    temperature_degf=60.0,
    z_factor=1.0,
    label="SPE / one standard atmosphere",
)

#: 14.73 psia and 60 degF. The US contractual and regulatory base used in most North
#: American gas sales and reserves reporting. 0.23 percent higher standard pressure
#: than :data:`SPE_STANDARD`, hence 0.23 percent fewer standard cubic feet for the
#: same reservoir volume.
US_CONTRACTUAL_STANDARD = StandardConditions(
    pressure_psia=14.73,
    temperature_degf=60.0,
    z_factor=1.0,
    label="US contractual base",
)

#: 101.325 kPa and 15 degC, the ISO/metric normal reference conditions.
METRIC_STANDARD = StandardConditions(
    pressure_psia=ATMOSPHERE_PSIA,
    temperature_degf=59.0,
    z_factor=1.0,
    label="metric / ISO 13443 (101.325 kPa, 15 degC)",
)

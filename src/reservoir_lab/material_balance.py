"""Gas material balance: p/Z depletion, rock and connate-water expansion, and the.

general (Havlena-Odeh) volume balance with water influx.

Scope and what this module deliberately is not
----------------------------------------------
Everything here is *dry gas*. The single load-bearing assumption behind the whole
family of methods is that the number of moles delivered to surface equals the number
of moles removed from the hydrocarbon pore volume, so that a reservoir volume divided
by a formation volume factor is a conserved standard volume. That fails for a
retrograde condensate once liquid drops out, and for any gas that partitions
appreciably into the water phase. Nothing in this module detects that; the caller
must establish it.

Nothing here decides *which* pressure to use. The balance is zero-dimensional: it
compares the whole reservoir's inventory at one volume-averaged pressure against its
inventory at the initial pressure. A flowing bottomhole pressure is not that quantity
-- it carries a rate-dependent drawdown and a non-Darcy term, so substituting it makes
the abscissa a function of the production rate rather than of the gas inventory, and
the resulting scatter is correlated with rate, which makes it look like reservoir
physics instead of like measurement error. This module cannot tell the difference and
does not try.

Units
-----
Field units, absolute pressure, absolute temperature, and one single reservoir-volume
convention throughout: **reservoir cubic feet (rcf) and standard cubic feet (scf)**.
Gas formation volume factors are therefore rcf/scf, gas volumes are scf, and every
reservoir volume (water influx, produced-water reservoir volume, hydrocarbon pore
volume, material-balance residual) is rcf.

This choice is not cosmetic. The published literature is split: Dake works in scf and
rcf/scf while Pletcher (SPE 75354) tabulates G in Mscf and Bg in RB/Mscf. Those two
conventions differ by a factor of 1000 in the gas volume and a factor of 5.615 in the
reservoir volume, and the mistake does not announce itself -- the answer simply comes
out a thousand times wrong, or, far worse, only the slope comes out wrong. Callers
holding RB/Mscf data convert at the boundary; see
:data:`reservoir_lab.units.CUBIC_FEET_PER_BARREL`.

The standard-condition basis (psc, Tsc, Zsc) never appears in this module. It cancels
exactly out of p/Z and out of every ratio Bg/Bgi, and it is carried by
:class:`reservoir_lab.units.StandardConditions` wherever a *volumetric* gas in place is
computed. That is why :func:`volumetric_gas_in_place_scf` takes a formation volume
factor rather than a pressure and temperature: the basis has to have been declared
already, by whoever produced the Bg.

Sources
-------
Dake, L.P., *Fundamentals of Reservoir Engineering*, Developments in Petroleum Science
8, Elsevier, chapter 1 sections 1.5-1.7 -- the inventory balance, the p/Z line, the
hydrocarbon-pore-volume reduction term, and the water-drive forms.

Pletcher, J.L., "Improvements to Reservoir Material-Balance Methods", SPE Reservoir
Evaluation & Engineering 5(1), February 2002, 49-59 (SPE 75354) -- the general balance
F = G(Eg + Efw) + We, the Efw grouping, the Roach and modified Roach plots, and the
two-cell weak-water-drive counterexample used as a regression fixture in the tests.

Ramagost, B.P. and Farshad, F.F., "P/Z Abnormally Pressured Gas Reservoirs",
SPE-10125-MS, 1981 -- the compaction-corrected p/Z. See the caveat on
:func:`ramagost_farshad_corrected_p_over_z`: only the abstract of that paper was
obtained, so the algebraic arrangement used here is the one that follows in three
lines from Pletcher's equations (1)-(4) with We = 0, not a transcription of the
primary source.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from . import regression
from .errors import InvalidInputError, NotIdentifiableError
from .validation import (
    as_float_sequence,
    require_in_interval,
    require_min_length,
    require_non_decreasing,
    require_non_negative,
    require_positive,
    require_same_length,
)

__all__ = [
    "ACRE_IN_SQUARE_FEET",
    "DEPLETION_FRACTION_WARNING_THRESHOLD",
    "RELATIVE_STDERR_WARNING_THRESHOLD",
    "PZFit",
    "RoachPlot",
    "effective_compressibility_per_psi",
    "fit_pz_depletion",
    "general_material_balance_residual",
    "modified_roach_plot_coordinates",
    "p_over_z",
    "ramagost_farshad_corrected_p_over_z",
    "roach_plot_coordinates",
    "rock_water_expansion_term",
    "volumetric_gas_in_place_scf",
]

#: Square feet in one acre. Exact by definition: one acre is one chain by one furlong,
#: 66 ft x 660 ft. This is a definitional conversion, not a measured constant.
ACRE_IN_SQUARE_FEET = 66.0 * 660.0

#: Below this observed depletion fraction the p/Z x-intercept is a long extrapolation
#: and :class:`PZFit` says so. The value is a judgement, not a published threshold.
#: It is set at the point where Pletcher's documented weak-water-drive bias is largest:
#: his two-cell simulation overestimates by 8.2 percent at 11 percent recovery, 6.5
#: percent at 27 percent and 4.0 percent at 54 percent, so the error decays slowly and
#: the first fifth of the depletion is where an extrapolated G deserves least trust.
DEPLETION_FRACTION_WARNING_THRESHOLD = 0.20

#: Relative standard error of the x-intercept above which :class:`PZFit` flags the
#: estimate as weakly constrained. Also a judgement: a ten percent one-sigma band on
#: gas in place is already wider than the decisions a p/Z plot is normally used for.
RELATIVE_STDERR_WARNING_THRESHOLD = 0.10

# ---------------------------------------------------------------------------
# Result guards
# ---------------------------------------------------------------------------


def _finite_result(value: float, name: str, hint: str) -> float:
    """Return ``value`` unless the arithmetic has left the finite range.

    Every argument reaching this module is validated finite, but a product or a sum of
    finite numbers is not necessarily finite: ``1e300 * 1e300`` overflows to ``inf``
    with no signal at all. Returning that ``inf`` would be returning a sentinel to
    report a failure, which api_contract C3 forbids, and C5 says a scalar return is a
    ``float`` -- a usable one, not a marker. So the result is guarded as well as the
    inputs, following the precedent already set by ``gas._finite_result``.

    ``hint`` names the arguments whose magnitudes are worth checking, because an
    overflow in field units almost always means a unit slip -- scf read as Mscf, or a
    reservoir volume already multiplied by a formation volume factor once.
    """
    if not math.isfinite(value):
        raise InvalidInputError(
            f"{name} evaluated to {value!r}, which is not a finite number. Every "
            f"argument was finite, so this overflowed in the arithmetic itself: check "
            f"the magnitudes of {hint}. The non-finite value is not returned, because a "
            f"sentinel return would propagate silently into a plot or a fit."
        )
    return value


def _finite_series(values: tuple[float, ...], name: str, hint: str) -> tuple[float, ...]:
    """Apply :func:`_finite_result` to every entry of a returned series."""
    return tuple(_finite_result(value, f"{name}[{index}]", hint) for index, value in enumerate(values))


# ---------------------------------------------------------------------------
# Scalar primitives
# ---------------------------------------------------------------------------


def p_over_z(pressure_psia: float, z_factor: float) -> float:
    """Return the p/Z abscissa of a gas material balance.

    Parameters
    ----------
    pressure_psia:
        Volume-averaged reservoir pressure, **absolute**. A gauge value used here is a
        silent bias, not an error: at 2638 psia a 14.7 psi offset is 0.56 percent in
        p/Z and it moves the extrapolated gas in place.
    z_factor:
        Gas deviation factor at that pressure and at the reservoir temperature,
        dimensionless. It must come from one single correlation or equation of state
        applied over the whole history. Switching correlation part-way injects a kink
        into the p/Z trend that is indistinguishable, on the plot, from reservoir
        physics.

    Returns
    -------
    float
        p/Z in psia.

    Notes
    -----
    p/Z is proportional to the moles of gas per unit hydrocarbon pore volume, which is
    the reason it is the natural abscissa: from pV = ZnRT, n/V = p/(ZRT), and at fixed
    reservoir temperature n/V is p/Z up to the constant 1/(RT).

    The standard-condition basis cancels out of this quantity entirely, so a p/Z series
    is basis-free even though a Bg series computed from the same pressures is not.

    What this does not do: it does not check that ``pressure_psia`` is a volume-averaged
    static pressure rather than a flowing or short-shut-in pressure, and it does not
    check that ``z_factor`` is single-phase.

    Raises
    ------
    InvalidInputError
        If either argument is non-finite or not strictly positive.
    """
    pressure = require_positive(pressure_psia, "pressure_psia")
    z = require_positive(z_factor, "z_factor")
    ratio = pressure / z
    if ratio == 0.0:
        raise InvalidInputError(
            f"p/Z underflowed to exactly zero from pressure_psia={pressure!r} and "
            f"z_factor={z!r}. Both are strictly positive, so the true quotient is "
            f"strictly positive too and zero is a sentinel rather than an answer: a "
            f"downstream fit would read it as a fully depleted reservoir. These "
            f"magnitudes are not a pressure and a deviation factor in field units."
        )
    return _finite_result(ratio, "p/Z", "pressure_psia and z_factor")


def volumetric_gas_in_place_scf(
    *,
    area_acres: float,
    thickness_ft: float,
    porosity: float,
    water_saturation: float,
    gas_fvf_rcf_per_scf: float,
) -> float:
    """Gas initially in place from rock volume, in standard cubic feet.

    ``G = 43560 * area_acres * thickness_ft * porosity * (1 - water_saturation)
    / gas_fvf_rcf_per_scf``

    Parameters
    ----------
    area_acres:
        Productive area. Converted with :data:`ACRE_IN_SQUARE_FEET`, which is exact.
    thickness_ft:
        **Net** gas pay thickness, not gross interval. The distinction is the single
        largest source of disagreement between two volumetric estimates of the same
        reservoir and this function cannot see which one it was handed.
    porosity:
        Effective porosity, fraction of bulk volume, in (0, 1).
    water_saturation:
        Initial (connate) water saturation, fraction of pore volume, in [0, 1).
    gas_fvf_rcf_per_scf:
        Gas formation volume factor at initial reservoir conditions, reservoir cubic
        feet per standard cubic foot. Whoever produced this number declared a standard
        pressure and temperature; that declaration propagates straight into G and does
        not cancel. Two bases two tables apart in one single paper (Pletcher's SPE
        75354 Tables 3 and 7 imply about 15.02 psia and about 14.70 psia) differ by
        2.2 percent in Bg and therefore by 2.2 percent in G.

    Returns
    -------
    float
        Gas initially in place, scf, on the standard basis implied by
        ``gas_fvf_rcf_per_scf``.

    Notes
    -----
    This is a static volumetric estimate. It shares no code and no data with the
    dynamic estimate from :func:`fit_pz_depletion`, which is the point: the two are
    independent lines of evidence and their disagreement is informative.

    Assumptions: a single average porosity, saturation and thickness represent the
    whole volume; the gas fills the mapped area uniformly; there is no gas in a
    separate non-communicating compartment; and the taken Zsc is whatever the Bg
    supplier assumed. Taking Zsc as exactly 1 rather than its true value near 0.997
    biases every volumetric G by about 0.3 percent in the same direction.

    What this does not do: no geological uncertainty, no net-to-gross, no area
    planimetry, no saturation-height modelling, and no check that the supplied Bg is
    evaluated at the initial pressure rather than at some current pressure.

    Raises
    ------
    InvalidInputError
        If any argument is non-finite; if ``area_acres``, ``thickness_ft`` or
        ``gas_fvf_rcf_per_scf`` is not strictly positive; if ``porosity`` is outside
        (0, 1); or if ``water_saturation`` is outside [0, 1).
    """
    area = require_positive(area_acres, "area_acres")
    thickness = require_positive(thickness_ft, "thickness_ft")
    # Open interval, matching the documented "(0, 1)": porosity 1.0 is rock that is
    # entirely pore space and 0.0 is rock with none, and both are an argument slipped
    # in from a percentage or a net-to-gross column rather than a physical porosity.
    phi = require_in_interval(porosity, "porosity", 0.0, 1.0, inclusive=False)
    swi = require_in_interval(water_saturation, "water_saturation", 0.0, 1.0)
    if swi >= 1.0:
        raise InvalidInputError(
            "water_saturation must be below 1.0; a fully water-saturated interval "
            "contains no gas and is almost always a transposed argument"
        )
    bg = require_positive(gas_fvf_rcf_per_scf, "gas_fvf_rcf_per_scf")

    bulk_volume_cuft = area * ACRE_IN_SQUARE_FEET * thickness
    hydrocarbon_pore_volume_rcf = bulk_volume_cuft * phi * (1.0 - swi)
    return _finite_result(
        hydrocarbon_pore_volume_rcf / bg,
        "gas in place",
        "area_acres, thickness_ft and gas_fvf_rcf_per_scf",
    )


def effective_compressibility_per_psi(
    *,
    water_compressibility_per_psi: float,
    formation_compressibility_per_psi: float,
    initial_water_saturation: float,
) -> float:
    """Rock plus connate-water compressibility referred to hydrocarbon pore volume.

    ``ce = (cw * Swi + cf) / (1 - Swi)``   [1/psi]

    Parameters
    ----------
    water_compressibility_per_psi:
        Isothermal compressibility of the **connate** water, 1/psi. Aquifer water is a
        separate quantity and enters the balance through the influx term, never here.
    formation_compressibility_per_psi:
        Pore-volume compressibility, 1/psi, defined on pore volume. Bulk-volume and
        matrix-volume compressibilities are different numbers; mixing the three
        definitions is a silent defect that shifts G by several percent.
    initial_water_saturation:
        Connate water saturation, fraction of pore volume, in [0, 1).

    Returns
    -------
    float
        Effective compressibility, 1/psi.

    Notes
    -----
    The derivation fixes the algebra, including the denominator that is easy to drop.
    Total pore volume ``Vp = HCPV / (1 - Swi)``; connate water volume
    ``Vw = Vp * Swi = HCPV * Swi / (1 - Swi)``. A pressure drop ``dp`` expands the
    water by ``cw * Vw * dp`` and shrinks the pore volume by ``cf * Vp * dp``, and both
    act to reduce the hydrocarbon pore volume:

        ``-dHCPV = (cw * Vw + cf * Vp) * dp = HCPV * [(cw * Swi + cf) / (1 - Swi)] * dp``

    The ``1 / (1 - Swi)`` is what converts a per-pore-volume basis to a per-hydrocarbon-
    pore-volume basis. Omitting it understates the term by the factor ``(1 - Swi)``,
    which for a typical Swi of 0.15 to 0.30 is a 15 to 30 percent error in the whole
    compaction correction.

    Worked value, used as a unit-test oracle: with cw = 3e-6/psi, cf = 6e-6/psi and
    Swi = 0.15, ce = (3e-6 * 0.15 + 6e-6) / 0.85 = 6.45e-6 / 0.85 = 7.5882e-6 /psi.
    This is the Pletcher two-cell case. A widely circulated value of 5.2941e-6 for the
    same inputs is arithmetically wrong (it is 6.45e-6 / 1.2186, not / 0.85) and it
    misses every published target of that paper by one to two percent in G.

    Assumptions: cw and cf are constant over the pressure interval. Defensible for
    consolidated, normally pressured rock where cf runs 3e-6 to 10e-6 /psi. Not
    defensible in a geopressured reservoir, where cf falls strongly as pressure drops
    and compaction is partly irreversible, nor in shallow unconsolidated rock where cf
    can exceed 100e-6 /psi.

    What this does not do: it does not model pressure-dependent or hysteretic cf, and
    it does not include residual oil compressibility (a three-phase case needs the
    ``Soi * co`` term as well).

    Raises
    ------
    InvalidInputError
        If any argument is non-finite, if either compressibility is negative, or if
        ``initial_water_saturation`` is outside [0, 1).
    """
    cw = require_non_negative(water_compressibility_per_psi, "water_compressibility_per_psi")
    cf = require_non_negative(formation_compressibility_per_psi, "formation_compressibility_per_psi")
    swi = require_in_interval(initial_water_saturation, "initial_water_saturation", 0.0, 1.0)
    if swi >= 1.0:
        raise InvalidInputError(
            "initial_water_saturation must be below 1.0: the (1 - Swi) denominator of "
            "the effective compressibility is undefined at Swi = 1"
        )
    return _finite_result(
        (cw * swi + cf) / (1.0 - swi),
        "effective compressibility",
        "the two compressibilities and how close initial_water_saturation is to 1",
    )


def rock_water_expansion_term(
    *,
    gas_in_place_scf: float,
    gas_fvf_initial_rcf_per_scf: float,
    water_compressibility_per_psi: float,
    formation_compressibility_per_psi: float,
    initial_water_saturation: float,
    initial_pressure_psia: float,
    pressure_psia: float,
) -> float:
    """Reservoir-volume contribution of rock compaction and connate-water expansion.

    ``G * Efw = G * Bgi * [(cw * Swi + cf) / (1 - Swi)] * (pi - p)``   [rcf]

    Parameters
    ----------
    gas_in_place_scf:
        G, gas initially in place, scf.
    gas_fvf_initial_rcf_per_scf:
        Bgi, gas formation volume factor at the **initial** pressure, rcf/scf. The
        product ``G * Bgi`` is the original hydrocarbon pore volume in rcf -- not the
        total pore volume, which is larger by ``1 / (1 - Swi)``.
    water_compressibility_per_psi, formation_compressibility_per_psi, initial_water_saturation:
        As in :func:`effective_compressibility_per_psi`.
    initial_pressure_psia:
        pi, absolute, at the datum the whole history is referred to.
    pressure_psia:
        p, current volume-averaged absolute pressure at the same datum, not above pi.

    Returns
    -------
    float
        Reservoir volume in rcf, non-negative, zero when ``pressure_psia`` equals
        ``initial_pressure_psia``.

    Notes
    -----
    Sign. This term is a *reduction* in hydrocarbon pore volume. It acts exactly like
    extra gas expansion: it pushes gas out of the pore space, so it appears with a plus
    sign on the expansion side of ``F = G (Eg + Efw) + We``. Getting this sign wrong
    reverses the direction of the compaction correction and, in a geopressured
    reservoir, roughly doubles the error instead of removing it.

    Magnitude. Dake's sanity check: cw = 3e-6, cf = 10e-6, Swc = 0.2, dp = 1000 psi
    gives ``ce * dp = 0.01325``, that is, the term alters the balance by 1.3 percent.
    At normal pressures and small drawdown it is genuinely negligible; at large
    drawdown or large cf it is not, and in a geopressured reservoir ignoring it can
    overstate G by tens of percent.

    Numerical note: ``pi - p`` is a difference of two large nearly equal numbers early
    in life. At a 20 psi drawdown from 6000 psia only about two significant figures of
    the difference survive typical gauge resolution, so the first few points of any
    compaction-corrected plot carry far less information than they appear to.

    What this does not do: it does not include aquifer water (that is We), residual
    oil, or any pressure dependence of cf.

    Raises
    ------
    InvalidInputError
        If any argument is non-finite; if ``gas_in_place_scf`` or
        ``gas_fvf_initial_rcf_per_scf`` is not strictly positive; if either
        compressibility is negative; if ``initial_water_saturation`` is outside
        [0, 1); if either pressure is not strictly positive; or if ``pressure_psia``
        exceeds ``initial_pressure_psia``, which is repressurisation and is far more
        often a transposed pair of arguments.
    """
    gas_in_place = require_positive(gas_in_place_scf, "gas_in_place_scf")
    bgi = require_positive(gas_fvf_initial_rcf_per_scf, "gas_fvf_initial_rcf_per_scf")
    ce = effective_compressibility_per_psi(
        water_compressibility_per_psi=water_compressibility_per_psi,
        formation_compressibility_per_psi=formation_compressibility_per_psi,
        initial_water_saturation=initial_water_saturation,
    )
    drawdown = _require_drawdown(initial_pressure_psia, pressure_psia)
    return _finite_result(
        gas_in_place * bgi * ce * drawdown,
        "G*Efw",
        "gas_in_place_scf and gas_fvf_initial_rcf_per_scf, whose product is the hydrocarbon pore volume",
    )


def ramagost_farshad_corrected_p_over_z(
    *,
    pressure_psia: float,
    z_factor: float,
    initial_pressure_psia: float,
    effective_compressibility_per_psi: float,
) -> float:
    """Compaction-corrected p/Z for an abnormally pressured gas reservoir.

    ``(p/Z) * [1 - ce * (pi - p)] = (pi/Zi) * (1 - Gp/G)``

    The left-hand side is what this returns; plotted against cumulative production it
    is a straight line whose x-intercept is G, in the same way the raw p/Z is for a
    normally pressured volumetric reservoir.

    Parameters
    ----------
    pressure_psia, z_factor:
        Current absolute pressure and its deviation factor.
    initial_pressure_psia:
        pi, absolute, same datum.
    effective_compressibility_per_psi:
        ce from :func:`effective_compressibility_per_psi`, 1/psi.

    Returns
    -------
    float
        Corrected p/Z in psia.

    Notes
    -----
    Provenance. The original SPE-10125 was not obtained; only its abstract. The
    arrangement used here is not a transcription. It follows in three lines from the
    general balance with We = 0: divide ``F = G (Eg + Efw)`` by ``G * Bgi``, use
    ``Bg / Bgi = (pi/Zi) / (p/Z)``, and rearrange. So the algebra is sound
    independently of whether the 1981 paper printed it this way, but the attribution
    itself remains unconfirmed against the primary source.

    Validity. The adjustment factor ``1 - ce * (pi - p)`` must stay positive, and it
    degrades long before it reaches zero: at ce = 2e-5 /psi and 6000 psi of drawdown it
    is already 0.88 and the "correction" is no longer a small perturbation. This
    function asserts the factor is positive and raises rather than clamping, because a
    clamped value would silently produce a plausible-looking plot from an invalid one.

    What this does not do -- and this is the important one. Correcting for cf does
    **not** protect against an aquifer. Pletcher's headline result is a two-cell
    simulation whose compaction-corrected p/Z is a visually perfect straight line,
    R-squared 0.9998 over ten years, and still overestimates gas in place by 8.2
    percent at 11 percent recovery and 4.0 percent at 54 percent, because the extra
    energy came from a weak aquifer rather than from compaction. The misattribution
    runs both ways: fitting the same data assuming no aquifer returned cf = 14.3e-6
    /psi against a known 6e-6.

    Raises
    ------
    InvalidInputError
        If any argument is non-finite; if a pressure or ``z_factor`` is not strictly
        positive; if ``effective_compressibility_per_psi`` is negative; if
        ``pressure_psia`` exceeds ``initial_pressure_psia``; or if
        ``ce * (pi - p) >= 1``, which makes the adjustment factor non-positive.
    """
    ratio = p_over_z(pressure_psia, z_factor)
    ce = require_non_negative(effective_compressibility_per_psi, "effective_compressibility_per_psi")
    drawdown = _require_drawdown(initial_pressure_psia, pressure_psia)
    factor = 1.0 - ce * drawdown
    if factor <= 0.0:
        raise InvalidInputError(
            f"the Ramagost-Farshad adjustment factor 1 - ce*(pi - p) is {factor!r}, which is "
            f"not positive (ce={ce!r}, pi - p={drawdown!r}). The correction is not valid at "
            f"this drawdown. The factor is not clamped: a clamped value would turn an invalid "
            f"input into a plausible-looking plot."
        )
    return ratio * factor


def general_material_balance_residual(
    *,
    gas_in_place_scf: float,
    cumulative_gas_scf: float,
    gas_fvf_rcf_per_scf: float,
    gas_fvf_initial_rcf_per_scf: float,
    water_compressibility_per_psi: float,
    formation_compressibility_per_psi: float,
    initial_water_saturation: float,
    initial_pressure_psia: float,
    pressure_psia: float,
    water_influx_rcf: float = 0.0,
    cumulative_water_produced_stock_tank_cuft: float = 0.0,
    water_fvf_reservoir_per_stock_tank: float = 1.0,
) -> float:
    """Residual of the general dry-gas material balance, in reservoir cubic feet.

    ``residual = F - [G * (Eg + Efw) + We]``

    A residual of zero means the proposed gas in place, the proposed influx and the
    proposed compressibilities together account exactly for the observed withdrawal at
    this one pressure. A positive residual means more volume came out of the reservoir
    than those three sources explain: an unaccounted energy source, of which a weak
    aquifer and a connected depleting reservoir are the two usual candidates.

    Derivation
    ----------
    The balance is an inventory of reservoir *volume* at one instant, written in the
    Havlena-Odeh arrangement used by Pletcher (SPE 75354, eqs. 1-4). Start from the
    statement that the pore space vacated by produced fluids must equal the pore space
    created by expansion and invaded by influx.

    The gas originally in place, G scf, occupied ``G * Bgi`` rcf at pi. That same gas,
    if none had been produced, would occupy ``G * Bg`` rcf at p. So gas expansion has
    made ``Eg = Bg - Bgi`` rcf of room available per scf of original gas.

    Rock compaction and connate-water expansion take away hydrocarbon pore volume,
    which has the same effect as expansion in pushing gas out:
    ``Efw = Bgi * ce * (pi - p)`` rcf per scf of original gas, with
    ``ce = (cw * Swi + cf) / (1 - Swi)``. See
    :func:`effective_compressibility_per_psi` for the derivation of the grouping,
    including why the denominator is there.

    Water influx We rcf enters from the aquifer and occupies reservoir volume.

    Against those three sources stands the withdrawal. Producing Gp scf of gas removes
    ``Gp * Bg`` rcf. Producing Wp of water, measured at the stock tank, removes
    ``Wp * Bw`` rcf. Together:

        ``F = Gp * Bg + Wp * Bw = G * (Eg + Efw) + We``

    Signs, explicitly, because this is where the equation is most often broken. Produced
    water is part of the withdrawal on the **left**; water influx sits alone on the
    **right**; and We is a **reservoir** volume. Three mutually consistent conventions
    exist in the literature -- Pletcher's (used here), Dake's (net influx
    ``(We - Wp) * Bw`` on the right, with Wp not in the withdrawal), and the IHS/Fekete
    arrangement -- and they must not be mixed. The specific defect to avoid is putting
    ``Wp * Bw`` in F *and also* subtracting it inside the influx term, which
    double-counts produced water and biases G.

    Parameters
    ----------
    gas_in_place_scf:
        G, the candidate gas in place being tested, scf.
    cumulative_gas_scf:
        Gp at this point in the history, scf, on the same standard basis as G.
    gas_fvf_rcf_per_scf:
        Bg at the current pressure, rcf/scf.
    gas_fvf_initial_rcf_per_scf:
        Bgi at the initial pressure, rcf/scf.
    water_compressibility_per_psi, formation_compressibility_per_psi, initial_water_saturation:
        As in :func:`effective_compressibility_per_psi`. These are required rather than
        defaulted to zero: silently assuming incompressible rock is the assumption that
        the compaction correction exists to remove, and a caller who means zero should
        have to say zero.
    initial_pressure_psia, pressure_psia:
        Absolute pressures at one datum, current not above initial.
    water_influx_rcf:
        We, cumulative water influx as a **reservoir** volume in rcf. Published tables
        frequently report influx at stock-tank conditions; multiply by Bw at ingest.
        In Pletcher's Table 2 the column header says STB and the body text quotes the
        reservoir volume, and the two differ by 5.7 percent at the end of the history.
    cumulative_water_produced_stock_tank_cuft:
        Wp, cumulative produced water measured at the **stock tank**, expressed as a
        volume in cubic feet (multiply STB by 5.615 to get here).
    water_fvf_reservoir_per_stock_tank:
        Bw, reservoir volume per stock-tank volume. It is a ratio of like volumes and
        therefore dimensionless, which is why it carries no unit suffix (api_contract
        C1): the call site reads ``stock-tank cubic feet x (reservoir per stock tank)``
        and lands in reservoir cubic feet without opening this function. The older name
        ``water_fvf_rb_per_stb`` was removed because it advertised a barrel basis next
        to a cubic-foot volume and a reviewer had to come in here to see that the 5.615
        factors cancel. Numerically it is close to but not equal to unity -- 1.045 to
        1.057 across Pletcher's ten-year history -- and setting it to exactly 1.0 in a
        high-pressure, high-temperature case is a few percent on the produced-water
        term.

    Returns
    -------
    float
        Residual in rcf. Zero to round-off when the inputs satisfy the balance.

    Notes
    -----
    The equation is zero-dimensional. It is evaluated at a point, comparing current
    volumes at p against original volumes at pi. It is not stepped, not differenced,
    and it carries no time.

    Assumptions, all of them: dry gas with a fixed mole count between reservoir and
    surface; one tank with no compartmentalisation and no gas influx from a connected
    reservoir; no gas cap and no oil leg; no gas injection; isothermal depletion; a
    single consistent Z correlation over the whole history; one declared standard
    basis shared by G, Gp and both Bg values; p a pore-volume-weighted average at a
    fixed datum, not a flowing pressure; constant cw and cf; and no adsorbed gas, which
    rules out coalbed methane and organic shale.

    What this does not do: it does not supply We. Water influx is time-dependent for
    any aquifer larger than the reservoir, and choosing an aquifer model is a fitted,
    non-unique step that belongs to the caller. It also does not estimate G -- it
    evaluates a candidate G that the caller proposes.

    Raises
    ------
    InvalidInputError
        If any argument is non-finite; if ``gas_in_place_scf`` or either formation
        volume factor is not strictly positive; if ``cumulative_gas_scf``,
        ``water_influx_rcf`` or ``cumulative_water_produced_stock_tank_cuft`` is
        negative; if ``water_fvf_reservoir_per_stock_tank`` is not strictly positive;
        if either compressibility is negative; if ``initial_water_saturation`` is
        outside [0, 1); if either pressure is not strictly positive; if
        ``pressure_psia`` exceeds ``initial_pressure_psia``; or if any term of the
        balance overflows the double-precision range, which is a unit slip rather
        than a reservoir.
    """
    gas_in_place = require_positive(gas_in_place_scf, "gas_in_place_scf")
    produced_gas = require_non_negative(cumulative_gas_scf, "cumulative_gas_scf")
    bg = require_positive(gas_fvf_rcf_per_scf, "gas_fvf_rcf_per_scf")
    bgi = require_positive(gas_fvf_initial_rcf_per_scf, "gas_fvf_initial_rcf_per_scf")
    influx = require_non_negative(water_influx_rcf, "water_influx_rcf")
    produced_water = require_non_negative(
        cumulative_water_produced_stock_tank_cuft,
        "cumulative_water_produced_stock_tank_cuft",
    )
    bw = require_positive(water_fvf_reservoir_per_stock_tank, "water_fvf_reservoir_per_stock_tank")

    expansion_rcf = _finite_result(
        gas_in_place * (bg - bgi),
        "the gas expansion term G*(Bg - Bgi)",
        "gas_in_place_scf and the two formation volume factors",
    )
    compaction_rcf = rock_water_expansion_term(
        gas_in_place_scf=gas_in_place,
        gas_fvf_initial_rcf_per_scf=bgi,
        water_compressibility_per_psi=water_compressibility_per_psi,
        formation_compressibility_per_psi=formation_compressibility_per_psi,
        initial_water_saturation=initial_water_saturation,
        initial_pressure_psia=initial_pressure_psia,
        pressure_psia=pressure_psia,
    )
    # Each summand is guarded before it reaches fsum. Two overflowed terms of opposite
    # sign make fsum raise a bare builtins.ValueError ("-inf + inf in fsum"), which is
    # in neither the api_contract C3 table nor this function's Raises section -- and
    # because InvalidInputError subclasses ValueError, a caller writing
    # ``except ValueError`` would silently read an overflow as a validation failure.
    withdrawal_rcf = _finite_result(
        _finite_result(
            produced_gas * bg,
            "the produced-gas term Gp*Bg",
            "cumulative_gas_scf and gas_fvf_rcf_per_scf",
        )
        + _finite_result(
            produced_water * bw,
            "the produced-water term Wp*Bw",
            "cumulative_water_produced_stock_tank_cuft and water_fvf_reservoir_per_stock_tank",
        ),
        "the withdrawal F",
        "cumulative_gas_scf and cumulative_water_produced_stock_tank_cuft",
    )
    # fsum keeps the cancellation honest: withdrawal and expansion are large and nearly
    # equal for a correct G, so the residual is a small difference of big numbers.
    return _finite_result(
        math.fsum((withdrawal_rcf, -expansion_rcf, -compaction_rcf, -influx)),
        "the material-balance residual",
        "every volume term, which must all share one reservoir-volume convention",
    )


# ---------------------------------------------------------------------------
# p/Z depletion fit
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PZFit:
    """Result of a straight-line fit of p/Z against cumulative gas production.

    Attributes
    ----------
    gas_in_place_scf:
        The x-intercept, ``-intercept / slope``, scf. This is a dynamic estimate of G
        and it is an extrapolation: it lies outside the data by construction, at a
        distance that shrinks only as depletion proceeds.
    gas_in_place_stderr_scf:
        One-sigma standard error of that x-intercept, scf, by the delta method
        **including** the slope-intercept covariance term. Propagating only the two
        variances is wrong and gives a materially different number -- about 36 percent
        too large on an evenly sampled half-depletion history. The covariance is
        strongly negative for a declining line, and dropping it removes a real
        cancellation.
    initial_p_over_z:
        The fitted line evaluated at Gp = 0, psia, that is, the fitted pi/Zi. It is
        numerically identical to :attr:`intercept`; the two names exist because one is
        the physical quantity and the other is the regression parameter, and the
        identity holds only because the abscissa is raw cumulative production with its
        origin at zero.
    observed_initial_p_over_z:
        The measured p/Z at the smallest cumulative production in the data. It differs
        from :attr:`initial_p_over_z` by the fit residual at that point, and the
        difference is worth looking at: whether to include the Gp = 0 point at all, and
        whether to force the line through it, materially changes G.
    slope:
        psia per scf, negative for a depleting reservoir.
    intercept:
        psia at Gp = 0.
    slope_stderr, intercept_stderr:
        One-sigma standard errors of the two regression parameters.
    covariance:
        Estimated covariance of slope and intercept, psia^2 per scf.
    r_squared:
        Coefficient of determination on the fitted ordinate. It measures how well the
        points lie on *a* line. It does **not** measure whether that line's x-intercept
        is G, and the two are not even loosely coupled: Pletcher's two-cell case has
        R-squared 0.9998 over ten years and is 4 percent wrong, and 0.99999 over two
        years and 8 percent wrong.
    residuals:
        Observed minus fitted ordinate at each point, psia, in input order.
    n_points, degrees_of_freedom:
        Points consumed and ``n - 2``.
    method:
        Fitting method requested, currently always ``"ols"``.
    regression_method:
        The label :mod:`reservoir_lab.regression` put on the line it returned --
        ``"ols"`` unweighted, ``"wls"`` weighted. Recorded separately from
        :attr:`method` so a result says which code path actually ran.
    fieller_g:
        The Fieller discriminant ``(t * SE(slope) / slope)**2`` at 95 percent, from
        :func:`reservoir_lab.regression.x_intercept`. It measures how badly the slope
        is determined relative to zero, which is what decides whether a symmetric
        interval around the x-intercept means anything. Below about 0.01 the symmetric
        and exact sets agree to one percent; at ``g`` of order 1 the exact set is
        unbounded and no symmetric interval can represent it.
    depletion_fraction_observed:
        ``max(Gp) / gas_in_place_scf``, the fraction of the fitted gas in place already
        produced at the last observation. Every G estimate should be quoted with this
        number attached.
    warnings:
        Stable-prefixed notes. Prefixes in use:
        ``linearity_is_not_evidence_of_volumetric_drive`` (always present),
        ``weak_extrapolation``, ``large_intercept_uncertainty``,
        ``no_zero_production_point``, and ``delta_method_interval`` for anything
        :func:`reservoir_lab.regression.x_intercept` had to say about the linearisation.
    """

    gas_in_place_scf: float
    gas_in_place_stderr_scf: float
    initial_p_over_z: float
    observed_initial_p_over_z: float
    slope: float
    intercept: float
    slope_stderr: float
    intercept_stderr: float
    covariance: float
    r_squared: float
    residuals: tuple[float, ...]
    n_points: int
    degrees_of_freedom: int
    method: str
    regression_method: str
    fieller_g: float
    depletion_fraction_observed: float
    warnings: tuple[str, ...]

    def remaining_gas_scf(self) -> float:
        """Fitted gas in place less the last observed cumulative production, scf."""
        return self.gas_in_place_scf * (1.0 - self.depletion_fraction_observed)


def fit_pz_depletion(
    cumulative_gas_scf: Sequence[float],
    p_over_z_psia: Sequence[float],
    *,
    method: str = "ols",
    weights: Sequence[float] | None = None,
) -> PZFit:
    """Fit ``p/Z = intercept + slope * Gp`` and extrapolate to the x-intercept.

    Parameters
    ----------
    cumulative_gas_scf:
        Cumulative gas production at each pressure observation, scf, non-negative and
        non-decreasing. Not sorted for you: an out-of-order cumulative series normally
        means two data sources were concatenated without alignment, and sorting it
        destroys the evidence of that.
    p_over_z_psia:
        The matching p/Z values in psia, from :func:`p_over_z` or from
        :func:`ramagost_farshad_corrected_p_over_z` if a compaction correction is being
        applied. Strictly positive.
    method:
        ``"ols"`` only. Deming and York regressions are in
        :mod:`reservoir_lab.regression` but they need an error-variance ratio or
        per-point standard deviations, which this signature has nowhere to accept, so
        asking for them here raises rather than silently falling back to OLS.
    weights:
        Optional per-point weights, strictly positive, interpreted as inverse variances
        up to a common scale factor. Ordinary least squares weights every point equally
        in p/Z units, which hands most of the leverage on the slope to the early
        high-pressure points -- precisely the regime where a weak-aquifer bias is
        worst. Weighting is one response to that; reporting the fit with the earliest
        points dropped is another, and the two disagree usefully.

    Returns
    -------
    PZFit

    Notes
    -----
    The line is the volumetric inventory balance. With a constant hydrocarbon pore
    volume, the gas remaining in the pore space at p is proportional to p/Z, so
    ``Gp = G (1 - (p/Z)/(pi/Zi))``, which rearranges to
    ``p/Z = (pi/Zi) (1 - Gp/G)`` -- a straight line whose x-intercept is G.

    Every assumption behind that line, in full: no water influx; negligible connate-
    water expansion and pore compaction (otherwise use
    :func:`ramagost_farshad_corrected_p_over_z` on the ordinate first); dry gas with no
    retrograde dropout, so the mole count is fixed and Z is single-phase; isothermal
    depletion; one declared standard basis for G and Gp; one tank, with no
    communication with another reservoir and no injection; p a pore-volume-weighted
    average at a fixed datum, not a flowing and not an arithmetic well average; one Z
    correlation throughout; Gp metered on the same declared basis with shrinkage, fuel
    and flare treated consistently; and no adsorbed gas.

    The failure mode this cannot see. A weak-to-moderate water drive, or a geopressured
    reservoir, produces a p/Z trend that is statistically an excellent straight line
    whose extrapolation overestimates G. Dake's warning is that early trends always
    look linear, and that extrapolating them assuming depletion drive gives too large a
    GIIP. A dry gas well is not evidence of a closed tank: after ten years Pletcher's
    aquifer-supported well made 1.5 STB of water per MMscf of gas. Diagnosing that
    requires a Cole or pot-aquifer plot, not a better fit of this line.

    What this does not do: it does not choose which points to include, does not force
    the line through a measured (0, pi/Zi), does not drop outliers, and does not decide
    whether the reservoir is volumetric.

    Raises
    ------
    InvalidInputError
        If the two series differ in length or hold fewer than three points; if any
        value is non-finite; if a cumulative production is negative or the series
        decreases; if any p/Z is not strictly positive; if ``method`` is not ``"ols"``;
        if ``weights`` is the wrong length, non-finite, or not strictly positive; or if
        the supplied magnitudes overflow the double-precision range while the line is
        being formed, which is a unit slip rather than a reservoir.
    NotIdentifiableError
        If cumulative production takes only one distinct value, so no slope exists; if
        the fitted slope is not negative, so there is no x-intercept to the right of the
        data; or if the fitted gas in place does not exceed the observed cumulative
        production, which asserts that more gas was produced than was ever present.
    """
    if method != "ols":
        raise InvalidInputError(
            f"method must be 'ols', got {method!r}. Deming and York regressions need an "
            f"error-variance ratio or per-point standard deviations, which this signature "
            f"cannot accept; call reservoir_lab.regression directly for those."
        )

    produced = as_float_sequence(cumulative_gas_scf, "cumulative_gas_scf")
    ordinate = as_float_sequence(p_over_z_psia, "p_over_z_psia")
    require_same_length(produced, ordinate, "cumulative_gas_scf", "p_over_z_psia")
    require_min_length(
        produced,
        "cumulative_gas_scf",
        3,
        "a p/Z fit with an estimable x-intercept standard error (two points leave zero "
        "degrees of freedom, so the residual variance and therefore the standard error "
        "do not exist)",
    )
    for index, value in enumerate(produced):
        require_non_negative(value, f"cumulative_gas_scf[{index}]")
    require_non_decreasing(produced, "cumulative_gas_scf")
    for index, value in enumerate(ordinate):
        require_positive(value, f"p_over_z_psia[{index}]")

    prepared_weights: tuple[float, ...] | None = None
    if weights is not None:
        prepared_weights = as_float_sequence(weights, "weights")
        require_same_length(prepared_weights, produced, "weights", "cumulative_gas_scf")
        for index, value in enumerate(prepared_weights):
            require_positive(value, f"weights[{index}]")

    if max(produced) == min(produced):
        raise NotIdentifiableError(
            "cumulative_gas_scf takes only one distinct value, so no slope and therefore no "
            "x-intercept is identifiable from these data"
        )

    # The line itself comes from the shared regression module, which is also where the
    # delta-method x-intercept lives. This module does not carry a second least-squares
    # implementation: two of them drift, and the one that drifts is never the one under
    # test.
    try:
        fit = regression.ols_line(produced, ordinate, weights=prepared_weights)
    except OverflowError as exc:
        # The regression module forms sums of squared deviations, which overflow for
        # abscissae above about 1e154 even though every individual value is finite.
        # OverflowError is not in the api_contract C3 table and is not documented by
        # this function, so it is translated at the boundary rather than allowed to
        # escape. The magnitudes are reported because the cause is always a unit slip.
        raise InvalidInputError(
            f"forming the least-squares line overflowed: max|cumulative_gas_scf| = "
            f"{max(abs(value) for value in produced)!r} and max|p_over_z_psia| = "
            f"{max(abs(value) for value in ordinate)!r}. Squared deviations of that "
            f"size are not representable in double precision. Neither series is on a "
            f"field-unit scale; check that cumulative production is in scf and the "
            f"ordinate in psia."
        ) from exc

    slope = fit.slope
    intercept = fit.intercept
    if slope >= 0.0:
        raise NotIdentifiableError(
            f"the fitted p/Z slope is {slope!r}, which is not negative. A non-declining p/Z "
            f"trend has no x-intercept to the right of the data, so gas in place is not "
            f"identifiable from it. Check for repressurisation, a gauge-pressure ordinate, "
            f"or cumulative production that is not cumulative."
        )
    # A non-positive intercept needs no separate guard: with a negative slope it puts the
    # x-intercept at or below zero, which the check below already rejects.
    gas_in_place = _finite_result(
        -intercept / slope,
        "the fitted gas in place",
        "cumulative_gas_scf and p_over_z_psia, whose ratio sets the intercept scale",
    )
    largest_produced = max(produced)
    if gas_in_place <= largest_produced:
        raise NotIdentifiableError(
            f"the fitted gas in place {gas_in_place!r} scf does not exceed the observed "
            f"cumulative production {largest_produced!r} scf. The line says more gas was "
            f"produced than was ever in place, so it is not a usable estimate."
        )

    # The standard error is the delta method including the slope-intercept covariance
    # term, Var(x0) = [Var(a) + 2*x0*Cov(a, b) + x0^2*Var(b)] / b^2. It is taken from
    # regression.x_intercept rather than rewritten here, for the same reason the line is:
    # a second copy of the formula would eventually disagree with the one that has the
    # Monte Carlo test attached to it.
    try:
        intercept_estimate = regression.x_intercept(fit)
    except OverflowError as exc:
        raise InvalidInputError(
            f"propagating the x-intercept variance overflowed at gas in place "
            f"{gas_in_place!r} scf with slope {slope!r} psia/scf. The delta method "
            f"squares the intercept, so an abscissa scale this large is not "
            f"representable; check the units of cumulative_gas_scf."
        ) from exc
    stderr = _finite_result(
        intercept_estimate.stderr,
        "the x-intercept standard error",
        "cumulative_gas_scf, whose squared deviations enter the variance",
    )

    depletion_fraction = largest_produced / gas_in_place
    notes = [
        "linearity_is_not_evidence_of_volumetric_drive: a high R-squared shows the points "
        "lie on a line, not that the line's x-intercept is gas in place. A documented "
        "weak-water-drive case gives R-squared 0.9998 with an 8 percent overestimate. "
        "Confirm the drive mechanism with a Cole or pot-aquifer plot before using this G."
    ]
    if depletion_fraction < DEPLETION_FRACTION_WARNING_THRESHOLD:
        data_span = max(largest_produced - min(produced), 1e-300)
        spans_beyond = (gas_in_place - largest_produced) / data_span
        notes.append(
            f"weak_extrapolation: only {depletion_fraction:.1%} of the fitted gas in place "
            f"has been produced, so the x-intercept sits {spans_beyond:.1f} data-spans "
            f"beyond the last observation. The intercept is a long extrapolation and its "
            f"standard error grows roughly as the reciprocal of the observed depletion "
            f"fraction."
        )
    if stderr > RELATIVE_STDERR_WARNING_THRESHOLD * gas_in_place:
        notes.append(
            f"large_intercept_uncertainty: the one-sigma standard error is "
            f"{stderr / gas_in_place:.1%} of the fitted gas in place. This is the noise "
            f"contribution alone and excludes any drive-mechanism bias, which is the larger "
            f"error in every documented failure case."
        )
    if min(produced) > 0.0:
        notes.append(
            "no_zero_production_point: the series does not include an observation at zero "
            "cumulative production, so the fitted initial p/Z is itself an extrapolation "
            "backwards and cannot be compared against a measured pi/Zi."
        )
    # Anything the regression had to say about the linearisation travels with the result
    # rather than being discarded at this boundary: a symmetric band around a ratio of
    # correlated estimates stops being a faithful summary long before it stops being a
    # number, and only the regression knows how close to that edge this fit sits.
    notes.extend(f"delta_method_interval: {message}" for message in intercept_estimate.warnings)

    return PZFit(
        gas_in_place_scf=gas_in_place,
        gas_in_place_stderr_scf=stderr,
        initial_p_over_z=intercept,
        observed_initial_p_over_z=ordinate[produced.index(min(produced))],
        slope=slope,
        intercept=intercept,
        slope_stderr=fit.slope_stderr,
        intercept_stderr=fit.intercept_stderr,
        covariance=fit.covariance,
        r_squared=fit.r_squared,
        residuals=tuple(fit.residuals),
        n_points=int(fit.n_points),
        degrees_of_freedom=int(fit.degrees_of_freedom),
        method=method,
        regression_method=fit.method,
        fieller_g=intercept_estimate.fieller_g,
        depletion_fraction_observed=depletion_fraction,
        warnings=tuple(notes),
    )


# ---------------------------------------------------------------------------
# Roach diagnostics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoachPlot:
    """Plotting coordinates for a Roach or modified Roach diagnostic.

    Attributes
    ----------
    x, y:
        Abscissa in 1/psi-scaled standard volume and ordinate in 1/psi, in input order.
        A least-squares line through them has slope ``1/G`` with G in scf, so
        ``G = 1 / slope``. Slope units are the trap here: the same plot appears in the
        literature with G in Mscf and in MMscf, and the resulting G is then wrong by a
        factor of 1000 or 1e6 with nothing to show for it.
    variant:
        ``"roach"`` or ``"modified_roach"``.
    n_points:
        Number of points returned, which equals the number supplied.
    intercept_meaning:
        Plain statement of what the y-intercept of a line through these points is, so
        that a caller reading the fitted intercept knows which grouping it equals and
        with which sign.
    """

    x: tuple[float, ...]
    y: tuple[float, ...]
    variant: str
    n_points: int
    intercept_meaning: str


def roach_plot_coordinates(
    *,
    pressure_psia: Sequence[float],
    z_factor: Sequence[float],
    cumulative_gas_scf: Sequence[float],
    initial_pressure_psia: float,
    initial_z_factor: float,
) -> RoachPlot:
    """Roach-plot coordinates: gas in place without knowing cf.

    ``y = [(p/z)i/(p/z) - 1] / (pi - p)``

    ``x = [(p/z)i/(p/z) * Gp] / (pi - p)``

    A line through these has slope ``1/G`` and y-intercept

    ``-[ (Swi*cw + cf)/(1 - Swi) + (We - Wp*Bw)/((pi - p)*G*Bgi) ]``.

    Sign, because this is where the published transcriptions disagree. Both groups
    inside the bracket are **added**, and the whole bracket is **subtracted**. The
    y-intercept is minus the sum of the two, not a difference. An arrangement in which
    the compressibility group enters with a plus sign is wrong: on the synthetic
    balance-satisfying history used in the test suite it gives +2.70e-6 where the
    identity requires -1.79e-5, which is both the wrong magnitude and the wrong sign.
    Both numbers come from that one history, and ``test_modified_roach_intercept_sign``
    pins them, so they can be reproduced rather than taken on trust.

    Derivation, in one pass, so the signs can be checked rather than trusted. Divide
    ``F = G(Eg + Efw) + We`` by ``G * Bgi``, write ``R = Bg/Bgi = (pi/Zi)/(p/Z)``:

        ``(Gp*R + Wp*Bw/Bgi) / G = R - 1 + ce*(pi - p) + We/(G*Bgi)``

    then divide by ``(pi - p)`` and move the produced-water piece back to the right:

        ``(R - 1)/(pi - p) = (1/G) * Gp*R/(pi - p) - [ ce + (We - Wp*Bw)/((pi - p)*G*Bgi) ]``

    Parameters
    ----------
    pressure_psia, z_factor, cumulative_gas_scf:
        Equal-length histories. Every pressure must be strictly below
        ``initial_pressure_psia``, because ``pi - p`` is the denominator of both axes.
    initial_pressure_psia, initial_z_factor:
        The initial state, absolute pressure and its deviation factor.

    Returns
    -------
    RoachPlot

    Notes
    -----
    Use with care in the presence of a water drive. The y-intercept contains We and Wp,
    which move from point to point, so the intercept is not constant and the correct
    slope is hard to establish -- Pletcher's own words are that significant errors in
    gas in place can easily result. :func:`modified_roach_plot_coordinates` fixes that,
    but only when a pot aquifer is the right model.

    The Gp = 0 point cannot appear on this plot: at p = pi both axes are 0/0. That is
    why every pressure must be strictly below pi, and why the point is not dropped for
    you -- the caller decides which observations enter a diagnostic.

    Numerically, ``pi - p`` is a difference of two large nearly equal numbers early in
    life, so the first points carry the fewest significant figures while sitting at the
    largest x, where they have the most leverage on the slope.

    What this does not do: it does not fit the line and it does not return G. Fit the
    returned coordinates with :mod:`reservoir_lab.regression` and take ``1 / slope``.

    Raises
    ------
    InvalidInputError
        If the three series differ in length or are shorter than two points; if any
        value is non-finite; if any pressure or z-factor is not strictly positive; if
        any cumulative production is negative; or if any pressure is greater than or
        equal to ``initial_pressure_psia``.
    """
    prepared = _prepare_roach_inputs(
        pressure_psia, z_factor, cumulative_gas_scf, initial_pressure_psia, initial_z_factor
    )
    abscissa = _finite_series(
        tuple(ratio * produced / drawdown for ratio, produced, drawdown in prepared.rows),
        "the Roach abscissa",
        "cumulative_gas_scf and how close each pressure is to initial_pressure_psia",
    )
    return RoachPlot(
        x=abscissa,
        y=prepared.ordinate,
        variant="roach",
        n_points=len(abscissa),
        intercept_meaning=(
            "y-intercept = -[ (Swi*cw + cf)/(1 - Swi) + (We - Wp*Bw)/((pi - p)*G*Bgi) ], "
            "both groups added inside the bracket and the whole bracket subtracted; it is "
            "not constant when water influx or water production is active"
        ),
    )


def modified_roach_plot_coordinates(
    *,
    pressure_psia: Sequence[float],
    z_factor: Sequence[float],
    cumulative_gas_scf: Sequence[float],
    produced_water_rcf: Sequence[float],
    initial_pressure_psia: float,
    initial_z_factor: float,
    gas_fvf_initial_rcf_per_scf: float,
) -> RoachPlot:
    """Return modified Roach-plot coordinates for a pot aquifer.

    ``y = [(p/z)i/(p/z) - 1] / (pi - p)``

    ``x = [(p/z)i/(p/z) * Gp + Wp*Bw/Bgi] / (pi - p)``

    A line through these has slope ``1/G`` and the **constant** y-intercept

    ``-[ (Swi*cw + cf)/(1 - Swi) + (cw + cf)*W/(G*Bgi) ]``.

    Sign, again explicitly: both the compressibility group and the aquifer group are
    added inside the bracket and the whole bracket is subtracted, so the intercept is
    negative. An arrangement with the aquifer group positive and the compressibility
    group negative is wrong, and it is also internally inconsistent with the plain
    Roach form -- substituting ``We = (cw + cf) * W * (pi - p)`` into the plain form
    must reproduce this one, and with the wrong signs it does not.

    Moving the produced-water term from the intercept into the abscissa is what makes
    the intercept constant, and it is also what makes the slope exact. On synthetic
    data that satisfy the balance identically, this abscissa returns ``1/slope = G`` to
    machine precision, while the plain Roach abscissa, which omits ``Wp*Bw/Bgi``,
    returns a G that is low by about half a percent once water production is
    non-trivial. That shortfall is correct behaviour for the plain form as published,
    not a defect in it.

    Parameters
    ----------
    pressure_psia, z_factor, cumulative_gas_scf:
        As in :func:`roach_plot_coordinates`.
    produced_water_rcf:
        ``Wp * Bw``, cumulative produced water already converted to a **reservoir**
        volume in rcf, non-negative. It is taken pre-multiplied rather than as (Wp, Bw)
        because Bw varies through the history and a single scalar would quietly impose
        a constant one.
    initial_pressure_psia, initial_z_factor:
        The initial state.
    gas_fvf_initial_rcf_per_scf:
        Bgi, rcf/scf. It converts the produced-water reservoir volume into the standard
        gas volume that the abscissa is measured in.

    Returns
    -------
    RoachPlot

    Notes
    -----
    Validity. This form is exact only when the aquifer behaves as a pot: any pressure
    drop in the reservoir is transmitted instantaneously through the whole aquifer.
    That needs a small, high-permeability, hydraulically isolated water leg of roughly
    the same order of magnitude as the reservoir. For a regional aquifer the influx is
    time-dependent, the intercept stops being constant, and this plot is the wrong
    tool.

    Pletcher's own caveat travels with the method and belongs in any report that uses
    it: the modified Roach plot has not been verified against actual field data,
    because suitable field data had not become available.

    What this does not do: it does not fit, does not return G or the aquifer volume W,
    and does not check that a pot aquifer is the right model -- nothing in these
    coordinates can tell you that.

    Raises
    ------
    InvalidInputError
        Everything :func:`roach_plot_coordinates` raises, plus: if
        ``produced_water_rcf`` differs in length from the other series, holds a
        non-finite or negative value, or if ``gas_fvf_initial_rcf_per_scf`` is not
        strictly positive.
    """
    prepared = _prepare_roach_inputs(
        pressure_psia, z_factor, cumulative_gas_scf, initial_pressure_psia, initial_z_factor
    )
    water = as_float_sequence(produced_water_rcf, "produced_water_rcf")
    require_same_length(water, prepared.ordinate, "produced_water_rcf", "pressure_psia")
    for index, value in enumerate(water):
        require_non_negative(value, f"produced_water_rcf[{index}]")
    bgi = require_positive(gas_fvf_initial_rcf_per_scf, "gas_fvf_initial_rcf_per_scf")

    abscissa = _finite_series(
        tuple(
            (ratio * produced + water_volume / bgi) / drawdown
            for (ratio, produced, drawdown), water_volume in zip(prepared.rows, water, strict=True)
        ),
        "the modified Roach abscissa",
        "cumulative_gas_scf, produced_water_rcf / gas_fvf_initial_rcf_per_scf, and how "
        "close each pressure is to initial_pressure_psia",
    )
    return RoachPlot(
        x=abscissa,
        y=prepared.ordinate,
        variant="modified_roach",
        n_points=len(abscissa),
        intercept_meaning=(
            "y-intercept = -[ (Swi*cw + cf)/(1 - Swi) + (cw + cf)*W/(G*Bgi) ], both groups "
            "added inside the bracket and the whole bracket subtracted; constant, but only "
            "under the pot-aquifer assumption"
        ),
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _require_drawdown(initial_pressure_psia: float, pressure_psia: float) -> float:
    """Validate a pressure pair and return ``pi - p``, which is never negative."""
    initial = require_positive(initial_pressure_psia, "initial_pressure_psia")
    current = require_positive(pressure_psia, "pressure_psia")
    if current > initial:
        raise InvalidInputError(
            f"pressure_psia ({current!r}) exceeds initial_pressure_psia ({initial!r}). The "
            f"depletion terms are written with (pi - p) as a positive pressure drop; a "
            f"current pressure above initial is either repressurisation, which this balance "
            f"does not model, or a transposed pair of arguments."
        )
    return initial - current


@dataclass(frozen=True)
class _RoachInputs:
    """Shared intermediate for both Roach variants.

    ``rows`` holds ``(ratio, produced, drawdown)`` per observation, where ``ratio`` is
    ``(p/Z)_i / (p/Z)`` and ``drawdown`` is ``pi - p``. ``ordinate`` is the y coordinate
    both variants share.
    """

    rows: tuple[tuple[float, float, float], ...]
    ordinate: tuple[float, ...]


def _prepare_roach_inputs(
    pressure_psia: Sequence[float],
    z_factor: Sequence[float],
    cumulative_gas_scf: Sequence[float],
    initial_pressure_psia: float,
    initial_z_factor: float,
) -> _RoachInputs:
    """Validate the histories shared by both Roach variants and build the ordinate."""
    pressures = as_float_sequence(pressure_psia, "pressure_psia")
    z_values = as_float_sequence(z_factor, "z_factor")
    produced = as_float_sequence(cumulative_gas_scf, "cumulative_gas_scf")
    require_same_length(pressures, z_values, "pressure_psia", "z_factor")
    require_same_length(pressures, produced, "pressure_psia", "cumulative_gas_scf")
    require_min_length(pressures, "pressure_psia", 2, "a Roach plot whose slope carries gas in place")
    initial_ratio = p_over_z(initial_pressure_psia, initial_z_factor)
    initial = require_positive(initial_pressure_psia, "initial_pressure_psia")

    rows = []
    ordinate = []
    for index, (pressure, z_value, produced_gas) in enumerate(
        zip(pressures, z_values, produced, strict=True)
    ):
        require_non_negative(produced_gas, f"cumulative_gas_scf[{index}]")
        ratio = initial_ratio / p_over_z(pressure, z_value)
        drawdown = initial - pressure
        if drawdown <= 0.0:
            raise InvalidInputError(
                f"pressure_psia[{index}]={pressure!r} is not strictly below "
                f"initial_pressure_psia={initial!r}. Both Roach axes divide by (pi - p), so "
                f"the initial point is 0/0 and cannot be plotted. It is not dropped for you: "
                f"choosing which observations enter a diagnostic is the caller's decision."
            )
        rows.append((ratio, produced_gas, drawdown))
        ordinate.append((ratio - 1.0) / drawdown)
    return _RoachInputs(
        rows=tuple(rows),
        ordinate=_finite_series(
            tuple(ordinate),
            "the Roach ordinate",
            "initial_pressure_psia, initial_z_factor and how close each pressure is to the initial pressure",
        ),
    )

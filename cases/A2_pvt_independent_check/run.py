#!/usr/bin/env python3
"""Case A2: independent PVT check of the correlation set against NIST reference values.

Runs the experiments pre-registered in ``protocol.md``:

E1  Deviation factor from DAK, Hall-Yarborough and DPR against methane, carbon dioxide
    and nitrogen reference states, entered through the *true* critical constants so
    that no pseudocritical correlation contaminates the attribution.
E1b A control on the reference side of E1: the field gas constant, the unit chain and
    the molar masses that ``Z = p M / (rho R T)`` rests on, recomputed from primary
    definitions rather than from the library under test.
E2  Lee-Gonzalez-Eakin viscosity against the reference methane viscosity, with the
    reference density supplied directly so the comparison does not inherit E1's error.
E2b A positive control on the viscosity instrument: anchor values recorded in an
    earlier and unrelated session, re-derived here.
E3  The Standing 677-versus-667 pseudocritical-pressure conflict, converted from a
    bibliographic question into a bounded difference in Ppc, Z and Bg.
E4  A declared double extrapolation: Sutton pseudocriticals plus Wichert-Aziz on pure
    carbon dioxide, with the Wichert-Aziz epsilon profile that bounds what the acid-gas
    correction can repair at all.

Standard library only. No randomness. Two runs with the same source revision produce a
byte-identical ``summary.json``.

The script changes directory to the repository root before it does anything, and every
path it hands to the run record is therefore repository-relative. That is not
housekeeping: an absolute path in a committed run record leaks the author's home
directory, which `scripts/check_repository.py` rejects, and it makes the record read as
though the result belonged to one machine. ``--out`` is interpreted relative to the
repository root for the same reason.

Usage
-----
    PYTHONPATH=src python3 cases/A2_pvt_independent_check/run.py --out artifacts/A2/run-001
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import statistics
import sys
import math
import warnings
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
for _entry in (str(REPO_ROOT / "src"), str(REPO_ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from tests.oracles.nist import (  # noqa: E402
    MANIFEST_PATH,
    REFERENCE_DIR,
    SPECIES,
    ReferenceSpecies,
    ReferenceState,
    load_species,
)

from reservoir_lab import gas_properties as gp  # noqa: E402
from reservoir_lab.errors import ConvergenceError, InvalidInputError, RangeWarning  # noqa: E402
from reservoir_lab.provenance import RunRecord  # noqa: E402
from reservoir_lab.units import (  # noqa: E402
    GAS_CONSTANT_FIELD,
    SPE_STANDARD,
    STANDARD_AIR_MOLAR_MASS,
    fahrenheit_to_rankine,
)

#: Fixed for the run record only. Nothing in this case consumes randomness.
SEED = 20260913

#: The three deviation-factor correlations, paired with the published window each one
#: exposes as a module constant, so the in-window subset is defined by the library's own
#: declaration rather than by a number retyped here.
Z_METHODS: dict[str, Any] = {
    "dak": (gp.z_factor_dak, gp.DAK_RANGE),
    "hall_yarborough": (gp.z_factor_hall_yarborough, gp.HALL_YARBOROUGH_RANGE),
    "dpr": (gp.z_factor_dpr, gp.DPR_RANGE),
}

#: E3 sweep, in integer units so the grid is exact and the config hash is stable.
STANDING_GRAVITIES_CENTI = tuple(range(55, 111, 5))
STANDING_PRESSURES_PSIA = tuple(float(p) for p in range(500, 6001, 500))
STANDING_TEMPERATURE_DEGF = 200.0

#: E4 epsilon profile, again in integer units.
EPSILON_PROFILE_CENTI = tuple(range(0, 101, 5))

#: E1b, the reference-Z unit-chain control. These are typed from their primary sources
#: rather than imported from :mod:`reservoir_lab.units`, because the point of the check
#: is to recompute the field gas constant without reusing the derivation under audit.
#: The first two are the defining constants of the 2019 SI, both exact; the next four are
#: exact by the 1959 international yard and pound agreement and the defined standard
#: gravity; the last is the rounded value tabulated throughout the reservoir engineering
#: literature, which is the external anchor.
#:
#: The molar gas constant is formed as the product of the two defining constants rather
#: than typed as a decimal. run-007 was executed with the ten-digit rounding 8.314462618
#: here and tripped inconclusive condition 6 at a relative difference of 1.8e-11, which
#: was a defect in the control and not in the library: the constant under audit is exact
#: and the auditing literal was not. Deriving it makes the comparison a statement about
#: the derivation instead of about a transcription.
AVOGADRO_CONSTANT_SI = 6.02214076e23
BOLTZMANN_CONSTANT_SI = 1.380649e-23
CODATA_GAS_CONSTANT_SI = AVOGADRO_CONSTANT_SI * BOLTZMANN_CONSTANT_SI
POUND_IN_KILOGRAMS = 0.45359237
FOOT_IN_METRES_EXACT = 0.3048
INCH_IN_METRES_EXACT = 0.0254
STANDARD_GRAVITY_SI_EXACT = 9.80665
TABULATED_GAS_CONSTANT_FIELD = 10.7316

#: IUPAC 2021 standard atomic weights and the formula of each reference species, used to
#: recompute the molar masses the manifest records. A molar mass enters the reference Z
#: linearly, so this bounds one of the three common-mode terms E1 cannot otherwise see.
IUPAC_2021_ATOMIC_WEIGHTS = {"C": 12.011, "H": 1.008, "N": 14.007, "O": 15.999}
SPECIES_COMPOSITION = {
    "methane": {"C": 1, "H": 4},
    "carbon_dioxide": {"C": 1, "O": 2},
    "nitrogen": {"N": 2},
}


def _round(value: float, digits: int = 10) -> float:
    """Round for serialisation so the JSON is stable and readable.

    Ten significant decimals is far below any effect this case discusses and far above
    the precision of the comparison, so rounding cannot change a conclusion. It exists
    to keep the byte-level determinism check meaningful rather than hostage to the last
    bit of a transcendental.
    """
    return round(value, digits)


def _summarise(errors: list[dict[str, Any]]) -> dict[str, Any]:
    """Reduce a list of per-state error records to the statistics the protocol names.

    Parameters
    ----------
    errors:
        Records carrying at least ``relative_error``. Each record is one state.

    Returns
    -------
    dict
        ``n``, mean, median and maximum absolute relative error, the signed mean as a
        bias, and the full description of the worst state. Empty input returns ``n`` of
        zero and ``None`` statistics rather than raising, so a fully excluded in-window
        subset is reported as empty instead of silently vanishing.
    """
    if not errors:
        return {
            "n": 0,
            "mean_abs_relative_error": None,
            "median_abs_relative_error": None,
            "max_abs_relative_error": None,
            "mean_signed_relative_error": None,
            "worst_state": None,
        }
    absolute = [abs(item["relative_error"]) for item in errors]
    signed = [item["relative_error"] for item in errors]
    worst = max(errors, key=lambda item: abs(item["relative_error"]))
    return {
        "n": len(errors),
        "mean_abs_relative_error": _round(statistics.fmean(absolute)),
        "median_abs_relative_error": _round(statistics.median(absolute)),
        "max_abs_relative_error": _round(max(absolute)),
        "mean_signed_relative_error": _round(statistics.fmean(signed)),
        "worst_state": worst,
    }


def _in_window(t_pr: float, p_pr: float, window: dict[str, tuple[float, float]]) -> bool:
    """Report whether a reduced state lies inside a correlation's published window."""
    t_low, t_high = window["t_pr"]
    p_low, p_high = window["p_pr"]
    return t_low <= t_pr <= t_high and p_low <= p_pr <= p_high


def _state_record(species: ReferenceSpecies, state: ReferenceState) -> dict[str, Any]:
    """Describe one reference state in the form every error record embeds."""
    t_pr, p_pr = species.reduced(state)
    return {
        "temperature_degf": state.temperature_degf,
        "pressure_psia": state.pressure_psia,
        "t_pr": _round(t_pr, 6),
        "p_pr": _round(p_pr, 6),
        "phase": state.phase,
    }


def verify_digests() -> dict[str, Any]:
    """Recompute the SHA-256 of the manifest and every reference table.

    The loader in ``tests/oracles/nist.py`` already refuses to return a row whose file
    does not match the manifest. This repeats the check independently of that loader and
    writes both the expected and the computed digest into the summary, so a reader can
    confirm the chain of custody from the committed bytes to the numbers in the report
    without trusting either the loader or this script.
    """
    manifest_bytes = MANIFEST_PATH.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    files = []
    for entry in manifest["files"]:
        path = REFERENCE_DIR / entry["path"]
        computed = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append(
            {
                "species": entry["species"],
                "path": entry["path"],
                "rows_declared": entry["rows"],
                "sha256_manifest": entry["sha256"],
                "sha256_recomputed": computed,
                "matches": computed == entry["sha256"],
            }
        )
    return {
        "route": (
            "both: tests.oracles.nist.load_species verifies internally and raises on drift, "
            "and this run independently recomputes every digest from the committed bytes"
        ),
        "manifest_path": str(MANIFEST_PATH.relative_to(REPO_ROOT)),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "acquired_utc_date": manifest["acquired_utc_date"],
        "source": manifest["source"],
        "files": files,
        "all_match": all(item["matches"] for item in files),
    }


def evaluate_z(species: ReferenceSpecies) -> dict[str, Any]:
    """Run E1 for one species: three correlations over all 150 reference states.

    Every state is evaluated with ``strict_range=False`` so that a window excursion
    warns instead of raising; the warning is suppressed here and the excursion is
    counted instead, because the protocol requires the excursion to be reported as a
    number rather than as console noise. A state where the solver raises is recorded
    with its exception, never skipped.
    """
    per_method: dict[str, Any] = {}
    for name, (solver, window) in Z_METHODS.items():
        errors: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        out_of_window = 0
        for state in species.states:
            t_pr, p_pr = species.reduced(state)
            inside = _in_window(t_pr, p_pr, window)
            if not inside:
                out_of_window += 1
            z_ref = species.deviation_factor(state)
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", RangeWarning)
                    z_corr = solver(t_pr, p_pr)
            except (ConvergenceError, InvalidInputError) as exc:
                failures.append({**_state_record(species, state), "error": f"{type(exc).__name__}: {exc}"})
                continue
            record = _state_record(species, state)
            record.update(
                {
                    "z_reference": _round(z_ref, 8),
                    "z_correlation": _round(z_corr, 8),
                    "relative_error": _round((z_corr - z_ref) / z_ref),
                    "in_published_window": inside,
                }
            )
            errors.append(record)

        by_isotherm = {}
        for degf in sorted({item["temperature_degf"] for item in errors}):
            subset = [item for item in errors if item["temperature_degf"] == degf]
            stats = _summarise(subset)
            by_isotherm[f"{degf:.0f}F"] = {
                "t_pr": subset[0]["t_pr"],
                "n": stats["n"],
                "mean_abs_relative_error": stats["mean_abs_relative_error"],
                "max_abs_relative_error": stats["max_abs_relative_error"],
                "mean_signed_relative_error": stats["mean_signed_relative_error"],
                "p_pr_at_max": stats["worst_state"]["p_pr"],
                "pressure_psia_at_max": stats["worst_state"]["pressure_psia"],
            }

        per_method[name] = {
            "published_window": window,
            "states_evaluated": len(errors),
            "states_failed": len(failures),
            "failure_fraction": _round(len(failures) / len(species.states), 6),
            "states_outside_published_window": out_of_window,
            "all_states": _summarise(errors),
            "in_window_only": _summarise([item for item in errors if item["in_published_window"]]),
            "by_isotherm": by_isotherm,
            "failures": failures,
        }
    return {
        "formula": species.formula,
        "molar_mass_lbm_per_lbmol": species.molar_mass_lbm_per_lbmol,
        "critical_temperature_degr": _round(species.critical.temperature_degr, 6),
        "critical_pressure_psia": _round(species.critical.pressure_psia, 6),
        "critical_source": species.critical.source,
        "eos_reference": species.eos_reference,
        "sha256": species.sha256,
        "n_states": len(species.states),
        "t_pr_range": [
            _round(min(species.reduced(s)[0] for s in species.states), 6),
            _round(max(species.reduced(s)[0] for s in species.states), 6),
        ],
        "p_pr_range": [
            _round(min(species.reduced(s)[1] for s in species.states), 6),
            _round(max(species.reduced(s)[1] for s in species.states), 6),
        ],
        "methods": per_method,
    }


def reference_z_unit_chain_control(species: dict[str, ReferenceSpecies]) -> dict[str, Any]:
    """Run E1b: audit the reference Z definition itself, independently of the library.

    Every number in E1 is a comparison against ``Z = p M / (rho R T)``, and every one of
    the nine species-method pairs comes out biased low. A common-mode error in the gas
    constant, in the molar masses or in the unit chain would look exactly like that, so
    the reference side needs a check of its own; the viscosity control in E2b cannot
    supply one, because ``gas_viscosity_lee_gonzalez_eakin`` takes neither a pressure
    nor a gas constant.

    Four checks, none of which reuses the library code it audits:

    * the field gas constant, recomputed here from the defining SI constants typed from
      their primary sources, against ``units.GAS_CONSTANT_FIELD`` and against the value
      tabulated in the reservoir engineering literature;
    * the reference Z of all 450 states recomputed entirely in SI, against the
      field-unit route the loader uses;
    * the molar masses in the manifest against the IUPAC 2021 standard atomic weights;
    * the ideal-gas anchor: how far the reference Z sits from unity at the lowest
      pressure on the grid, which is the one absolute statement available without a
      second equation of state.

    What it cannot check is stated in the returned payload: the committed density column
    is common to both routes, so a mis-retrieval is invisible here and only a re-fetch
    settles it.
    """
    psi_in_pascal = POUND_IN_KILOGRAMS * STANDARD_GRAVITY_SI_EXACT / INCH_IN_METRES_EXACT**2
    recomputed_r = (
        CODATA_GAS_CONSTANT_SI
        * (POUND_IN_KILOGRAMS * 1000.0)
        * (5.0 / 9.0)
        / FOOT_IN_METRES_EXACT**3
        / psi_in_pascal
    )
    worst_z: dict[str, Any] = {"relative_difference": 0.0}
    n_states = 0
    for name, item in species.items():
        molar_mass_si = item.molar_mass_lbm_per_lbmol * 1.0e-3
        for state in item.states:
            n_states += 1
            pressure_pa = state.pressure_psia * psi_in_pascal
            temperature_k = state.temperature_degr * (5.0 / 9.0)
            density_si = state.density_lbm_per_cuft * POUND_IN_KILOGRAMS / FOOT_IN_METRES_EXACT**3
            z_si = pressure_pa * molar_mass_si / (density_si * CODATA_GAS_CONSTANT_SI * temperature_k)
            z_field = item.deviation_factor(state)
            difference = abs(z_si - z_field) / z_field
            if difference > worst_z["relative_difference"]:
                worst_z = {
                    "species": name,
                    "temperature_degf": state.temperature_degf,
                    "pressure_psia": state.pressure_psia,
                    "z_field_route": _round(z_field, 10),
                    "z_si_route": _round(z_si, 10),
                    "relative_difference": difference,
                }

    molar_masses = []
    for name, item in species.items():
        recomputed = sum(
            IUPAC_2021_ATOMIC_WEIGHTS[element] * count for element, count in SPECIES_COMPOSITION[name].items()
        )
        molar_masses.append(
            {
                "species": name,
                "manifest_lbm_per_lbmol": item.molar_mass_lbm_per_lbmol,
                "iupac_2021_lbm_per_lbmol": _round(recomputed, 6),
                "relative_difference": _round(
                    abs(recomputed - item.molar_mass_lbm_per_lbmol) / item.molar_mass_lbm_per_lbmol, 10
                ),
            }
        )

    ideal_gas = []
    for name in ("methane", "nitrogen"):
        item = species[name]
        lowest = [state for state in item.states if state.pressure_psia == 200.0]
        departures = [(abs(item.deviation_factor(state) - 1.0), state) for state in lowest]
        worst_departure, worst_state = max(departures, key=lambda pair: pair[0])
        ideal_gas.append(
            {
                "species": name,
                "pressure_psia": 200.0,
                "n": len(lowest),
                "max_abs_departure_from_unity": _round(worst_departure, 8),
                "at_temperature_degf": worst_state.temperature_degf,
            }
        )

    tolerance = 1.0e-12
    return {
        "purpose": (
            "audit the reference Z definition Z = p M / (rho R T) on its own, since every E1 "
            "number is measured against it and all nine species-method pairs are biased low"
        ),
        "gas_constant": {
            "library_psia_cuft_per_lbmol_degr": GAS_CONSTANT_FIELD,
            "recomputed_from_si_definitions": recomputed_r,
            "relative_difference": _round(abs(recomputed_r - GAS_CONSTANT_FIELD) / GAS_CONSTANT_FIELD, 18),
            "tabulated_in_the_literature": TABULATED_GAS_CONSTANT_FIELD,
            "relative_difference_against_tabulated": _round(
                abs(recomputed_r - TABULATED_GAS_CONSTANT_FIELD) / TABULATED_GAS_CONSTANT_FIELD, 10
            ),
            "constants_used": {
                "avogadro_constant_per_mol": AVOGADRO_CONSTANT_SI,
                "boltzmann_constant_j_per_k": BOLTZMANN_CONSTANT_SI,
                "gas_constant_j_per_mol_k_as_their_product": CODATA_GAS_CONSTANT_SI,
                "pound_in_kilograms": POUND_IN_KILOGRAMS,
                "foot_in_metres": FOOT_IN_METRES_EXACT,
                "inch_in_metres": INCH_IN_METRES_EXACT,
                "standard_gravity_m_per_s2": STANDARD_GRAVITY_SI_EXACT,
                "rankine_in_kelvin": "5/9",
            },
        },
        "si_route_versus_field_route": {
            "n_states": n_states,
            "worst_state": worst_z,
            "max_relative_difference": _round(worst_z["relative_difference"], 18),
        },
        "molar_masses": molar_masses,
        "ideal_gas_limit": ideal_gas,
        "tolerance_relative": tolerance,
        "all_confirmed": bool(
            abs(recomputed_r - GAS_CONSTANT_FIELD) / GAS_CONSTANT_FIELD <= tolerance
            and worst_z["relative_difference"] <= tolerance
        ),
        "what_this_does_not_check": (
            "the committed density column itself, which is common to both routes and would "
            "therefore move both identically; only a re-fetch from the WebBook settles that. "
            "The molar-mass comparison bounds that term at the fifth significant figure and "
            "cannot account for a bias of order one percent."
        ),
    }


def viscosity_instrument_control() -> dict[str, Any]:
    """Run E2b: check the viscosity instrument against its own closed form, on invented states.

    What this establishes, and what it does not
    ------------------------------------------
    This is a SOFTWARE control, not a statement about agreement with any external
    reference. It evaluates ``gas_viscosity_lee_gonzalez_eakin`` at states invented here
    and compares the result with an independent evaluation of the closed form the
    correlation publishes::

        K   = (9.379 + 0.01607 M) T^1.5 / (209.2 + 19.26 M + T)
        X   = 3.448 + 986.4 / T + 0.01009 M
        Y   = 2.447 - 0.2224 X
        mu  = 1e-4 K exp(X rho^Y)      rho in g/cm^3

    The arithmetic below is written out separately from the library, so a coefficient
    typo, a transposed exponent, a degF/degR confusion or a missing lbm/ft^3 to g/cm^3
    conversion shows up as a disagreement. It is the second of those that matters most:
    feeding a field-unit density straight into the exponential is the classic way to get
    this correlation wrong by orders of magnitude, and the third check below fails loudly
    if the conversion ever disappears.

    The earlier version of E2b compared against reference viscosities recorded in an
    evidence card. Those values came from the reference extract this project does not
    redistribute, so they are not in this release; see
    ``docs/release/PUBLIC_DATA_POLICY.md``. Agreement with the reference is measured by
    E2, which runs only when the operator supplies the extract locally. Nothing here is
    evidence about the physical world -- it is evidence that the instrument is wired the
    way its documentation says.

    The states are invented. The temperatures and molar masses below were chosen to sit
    inside the correlation's declared validity window and to be obviously not a grid
    anybody retrieved: no isotherm, no round pressure, no tabulated species.
    """
    # Invented states: (temperature degF, molar mass lbm/lbmol, density lbm/ft^3).
    states = [
        (137.0, 17.3, 3.7),
        (214.5, 21.9, 11.3),
        (301.25, 28.1, 19.7),
    ]
    lbm_per_cuft_in_g_per_cc = 1.0 / 62.427960576144606

    points: list[dict[str, Any]] = []
    for t_degf, molar_mass, rho_field in states:
        t_degr = t_degf + 459.67
        # Independent evaluation of the published closed form.
        k = (9.379 + 0.01607 * molar_mass) * t_degr**1.5 / (209.2 + 19.26 * molar_mass + t_degr)
        x = 3.448 + 986.4 / t_degr + 0.01009 * molar_mass
        y = 2.447 - 0.2224 * x
        rho_gcc = rho_field * lbm_per_cuft_in_g_per_cc
        expected = 1.0e-4 * k * math.exp(x * rho_gcc**y)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RangeWarning)
            observed = gp.gas_viscosity_lee_gonzalez_eakin(t_degr, molar_mass, rho_field)
            # The zero-density analytic limit: exp(X rho^Y) -> 1, so mu -> 1e-4 K exactly.
            near_zero = gp.gas_viscosity_lee_gonzalez_eakin(t_degr, molar_mass, 1.0e-12)
            # The unit-chain trap: if the conversion were dropped, the library would be
            # evaluating the exponential at a field-unit density instead.
            unconverted = 1.0e-4 * k * math.exp(x * rho_field**y)

        points.append(
            {
                "temperature_degf": t_degf,
                "molar_mass_lbm_per_lbmol": molar_mass,
                "density_lbm_per_cuft": rho_field,
                "closed_form_cp": _round(expected, 10),
                "library_cp": _round(observed, 10),
                "relative_difference": _round(abs(observed / expected - 1.0), 12),
                "zero_density_limit_cp": _round(near_zero, 10),
                "one_over_ten_thousand_k_cp": _round(1.0e-4 * k, 10),
                "closed_form_matches": abs(observed / expected - 1.0) <= 1.0e-12,
                "zero_density_limit_holds": abs(near_zero / (1.0e-4 * k) - 1.0) <= 1.0e-9,
                "unit_conversion_is_applied": abs(observed / unconverted - 1.0) > 1.0e-3,
            }
        )

    return {
        "kind": "software instrument control on invented states",
        "establishes": (
            "that the implementation evaluates the published Lee-Gonzalez-Eakin closed form, "
            "applies the lbm/ft^3 to g/cm^3 conversion, and reaches the analytic zero-density "
            "limit. It establishes nothing about agreement with any external reference."
        ),
        "reference_data_used": False,
        "points": points,
        "n_points": len(points),
        "all_controls_hold": bool(points)
        and all(
            item["closed_form_matches"]
            and item["zero_density_limit_holds"]
            and item["unit_conversion_is_applied"]
            for item in points
        ),
    }


def evaluate_viscosity(methane: ReferenceSpecies) -> dict[str, Any]:
    """Run E2: Lee-Gonzalez-Eakin against the reference methane viscosity.

    The reference *density* is handed to the correlation as its density argument. That
    is deliberate: LGE is density-explicit, so routing it through a correlated Z would
    fold the E1 deviation-factor error into the viscosity error and neither could then
    be attributed.
    """
    errors: list[dict[str, Any]] = []
    for state in methane.states:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RangeWarning)
            mu_corr = gp.gas_viscosity_lee_gonzalez_eakin(
                state.temperature_degr,
                methane.molar_mass_lbm_per_lbmol,
                state.density_lbm_per_cuft,
            )
        mu_ref = state.viscosity_cp
        record = _state_record(methane, state)
        record.update(
            {
                "density_lbm_per_cuft": state.density_lbm_per_cuft,
                "viscosity_reference_cp": _round(mu_ref, 8),
                "viscosity_lge_cp": _round(mu_corr, 8),
                "relative_error": _round((mu_corr - mu_ref) / mu_ref),
            }
        )
        errors.append(record)

    low_p = [item for item in errors if item["pressure_psia"] <= 2000.0]
    high_p = [item for item in errors if item["pressure_psia"] > 2000.0]
    specific_gravity = methane.molar_mass_lbm_per_lbmol / STANDARD_AIR_MOLAR_MASS
    return {
        "correlation": "Lee, Gonzalez & Eakin (1966), coefficients as implemented in gas_properties",
        "published_window": gp.LGE_RANGE,
        "density_source": "NIST reference equation of state, supplied directly to the correlation",
        "specific_gravity_of_methane": _round(specific_gravity, 6),
        "viscosity_reference_citation": methane.viscosity_reference,
        "all_states": _summarise(errors),
        "at_or_below_2000_psia": _summarise(low_p),
        "above_2000_psia": _summarise(high_p),
        "fraction_of_states_with_positive_error": _round(
            sum(1 for item in errors if item["relative_error"] > 0) / len(errors), 6
        ),
        "states_outside_lge_window": sum(
            1
            for item in errors
            if not (
                gp.LGE_RANGE["temperature_degf"][0]
                <= item["temperature_degf"]
                <= gp.LGE_RANGE["temperature_degf"][1]
                and gp.LGE_RANGE["pressure_psia"][0]
                <= item["pressure_psia"]
                <= gp.LGE_RANGE["pressure_psia"][1]
            )
        ),
    }


def evaluate_standing_variants() -> dict[str, Any]:
    """Run E3: bound the 677-versus-667 conflict in Ppc, Z and Bg.

    Both variants share the same Tpc correlation, so the entire difference enters
    through the pseudo-reduced pressure. Z is taken by DAK and Bg from the same Z at SPE
    standard conditions, which is the path a Stage A material balance actually uses.
    """
    temperature_degr = fahrenheit_to_rankine(STANDING_TEMPERATURE_DEGF)
    rows: list[dict[str, Any]] = []
    ppc_errors: list[dict[str, Any]] = []
    z_errors: list[dict[str, Any]] = []
    bg_errors: list[dict[str, Any]] = []
    for centi in STANDING_GRAVITIES_CENTI:
        gamma = centi / 100.0
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RangeWarning)
            pc_ahmed = gp.pseudocritical_standing(gamma, variant="ahmed")
            pc_whitson = gp.pseudocritical_standing(gamma, variant="whitson-brule")
        ppc_rel = (pc_ahmed.pressure_psia - pc_whitson.pressure_psia) / pc_whitson.pressure_psia
        ppc_errors.append({"specific_gravity": gamma, "relative_error": _round(ppc_rel)})
        for pressure in STANDING_PRESSURES_PSIA:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RangeWarning)
                z_ahmed = gp.z_factor(pressure, temperature_degr, pc_ahmed, method="dak")
                z_whitson = gp.z_factor(pressure, temperature_degr, pc_whitson, method="dak")
            bg_ahmed = gp.gas_fvf_rcf_per_scf(pressure, temperature_degr, z_ahmed, SPE_STANDARD)
            bg_whitson = gp.gas_fvf_rcf_per_scf(pressure, temperature_degr, z_whitson, SPE_STANDARD)
            common = {"specific_gravity": gamma, "pressure_psia": pressure}
            z_errors.append({**common, "relative_error": _round((z_ahmed - z_whitson) / z_whitson)})
            bg_errors.append({**common, "relative_error": _round((bg_ahmed - bg_whitson) / bg_whitson)})
            rows.append(
                {
                    **common,
                    "ppc_ahmed_psia": _round(pc_ahmed.pressure_psia, 6),
                    "ppc_whitson_brule_psia": _round(pc_whitson.pressure_psia, 6),
                    "tpc_common_degr": _round(pc_ahmed.temperature_degr, 6),
                    "z_ahmed": _round(z_ahmed, 8),
                    "z_whitson_brule": _round(z_whitson, 8),
                    "bg_ahmed_rcf_per_scf": _round(bg_ahmed, 8),
                    "bg_whitson_brule_rcf_per_scf": _round(bg_whitson, 8),
                }
            )
    return {
        "constants": gp.STANDING_DRY_GAS_PRESSURE_CONSTANTS,
        "default_variant": gp.STANDING_DEFAULT_VARIANT,
        "temperature_degf": STANDING_TEMPERATURE_DEGF,
        "specific_gravity_grid": [c / 100.0 for c in STANDING_GRAVITIES_CENTI],
        "pressure_grid_psia": list(STANDING_PRESSURES_PSIA),
        "standard_conditions": SPE_STANDARD.describe(),
        "absolute_ppc_difference_psia": _round(
            gp.STANDING_DRY_GAS_PRESSURE_CONSTANTS["ahmed"]
            - gp.STANDING_DRY_GAS_PRESSURE_CONSTANTS["whitson-brule"],
            6,
        ),
        "ppc": _summarise(ppc_errors),
        "z": _summarise(z_errors),
        "bg": _summarise(bg_errors),
        "rows": rows,
    }


def evaluate_wichert_aziz_probe(carbon_dioxide: ReferenceSpecies) -> dict[str, Any]:
    """Run E4: the declared double extrapolation, plus the epsilon profile.

    Sutton pseudocriticals at the specific gravity of pure CO2 are inside Sutton's
    gravity window; the Wichert-Aziz correction at ``y_co2 = 1.0`` is far outside its
    fitted composition window. Nothing here is a test of Wichert-Aziz on a sour gas. The
    epsilon profile is read straight off the published expression and needs no data at
    all, which is why it is the part of E4 that supports a general statement.
    """
    gamma = carbon_dioxide.molar_mass_lbm_per_lbmol / STANDARD_AIR_MOLAR_MASS
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RangeWarning)
        sutton = gp.pseudocritical_sutton(gamma)
        corrected = gp.wichert_aziz_correction(sutton, y_h2s=0.0, y_co2=1.0)

    def _errors(pseudocriticals: gp.PseudoCriticals) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for state in carbon_dioxide.states:
            t_pr, p_pr = pseudocriticals.reduced(state.pressure_psia, state.temperature_degr)
            z_ref = carbon_dioxide.deviation_factor(state)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RangeWarning)
                z_corr = gp.z_factor_dak(t_pr, p_pr)
            record = _state_record(carbon_dioxide, state)
            record.update(
                {
                    "t_pr_pseudo": _round(t_pr, 6),
                    "p_pr_pseudo": _round(p_pr, 6),
                    "z_reference": _round(z_ref, 8),
                    "z_correlation": _round(z_corr, 8),
                    "relative_error": _round((z_corr - z_ref) / z_ref),
                }
            )
            out.append(record)
        return out

    profile = []
    for centi in EPSILON_PROFILE_CENTI:
        y_co2 = centi / 100.0
        base = gp.PseudoCriticals(400.0, 700.0, correlation="probe")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RangeWarning)
            shifted = gp.wichert_aziz_correction(base, y_h2s=0.0, y_co2=y_co2)
        profile.append(
            {
                "y_co2": y_co2,
                "epsilon_degr": _round(base.temperature_degr - shifted.temperature_degr, 6),
            }
        )
    peak = max(profile, key=lambda item: item["epsilon_degr"])

    return {
        "declared_status": (
            "double extrapolation, declared before the run: Sutton is applied to a pure component "
            "and Wichert-Aziz is applied at y_co2 = 1.0, far outside its fitted window of 0 to 0.55. "
            "It establishes nothing about Wichert-Aziz on a real sour gas."
        ),
        "specific_gravity_of_co2": _round(gamma, 6),
        "sutton_gravity_window": gp.SUTTON_GRAVITY_RANGE,
        "wichert_aziz_window": gp.WICHERT_AZIZ_RANGE,
        "true_critical_temperature_degr": _round(carbon_dioxide.critical.temperature_degr, 6),
        "true_critical_pressure_psia": _round(carbon_dioxide.critical.pressure_psia, 6),
        "sutton_tpc_degr": _round(sutton.temperature_degr, 6),
        "sutton_ppc_psia": _round(sutton.pressure_psia, 6),
        "wichert_aziz_tpc_degr": _round(corrected.temperature_degr, 6),
        "wichert_aziz_ppc_psia": _round(corrected.pressure_psia, 6),
        "dak_on_sutton": _summarise(_errors(sutton)),
        "dak_on_sutton_plus_wichert_aziz": _summarise(_errors(corrected)),
        "epsilon_profile_degr": profile,
        "epsilon_peak": peak,
    }


def build_payload() -> dict[str, Any]:
    """Compute the entire case and return the serialisable summary.

    Pure: it reads the committed reference files and nothing else, consumes no
    randomness, and takes no argument. Calling it twice in one process must produce
    equal objects, which is how the determinism criterion is checked.
    """
    digests = verify_digests()
    if not digests["all_match"]:
        raise RuntimeError("reference digest mismatch; see summary['reference'] for the offending file")

    species = {name: load_species(name) for name in SPECIES}
    for name, item in species.items():
        if len(item.states) != 150:
            raise RuntimeError(f"{name}: expected 150 reference states, found {len(item.states)}")

    z_results = {name: evaluate_z(item) for name, item in species.items()}
    unit_chain = reference_z_unit_chain_control(species)
    viscosity = evaluate_viscosity(species["methane"])
    control = viscosity_instrument_control()
    standing = evaluate_standing_variants()
    probe = evaluate_wichert_aziz_probe(species["carbon_dioxide"])
    return {
        "case_id": "A2_pvt_independent_check",
        "question": (
            "How well do the correlations this project uses reproduce an independent "
            "reference, and where do they fail?"
        ),
        "reference": digests,
        "reduced_properties_from": (
            "true pure-component critical constants, tests.oracles.nist.CRITICAL_CONSTANTS; "
            "no gas-gravity pseudocritical correlation enters E1 or E2"
        ),
        "z_factor": z_results,
        "reference_z_unit_chain_control": unit_chain,
        "viscosity": viscosity,
        "viscosity_instrument_control": control,
        "standing_pseudocritical_variants": standing,
        "wichert_aziz_probe": probe,
        "acceptance": None,
    }


def evaluate_acceptance(payload: dict[str, Any]) -> dict[str, Any]:
    """Score the pre-registered acceptance criteria from ``protocol.md`` section 5.

    Thresholds are literals here so that a reader can compare them against the protocol
    line by line. They were fixed before the first run and are not derived from any
    result in ``payload``.
    """
    results: list[dict[str, Any]] = []

    def add(name: str, threshold: str, observed: str, met: bool) -> None:
        results.append({"criterion": name, "threshold": threshold, "observed": observed, "met": met})

    add(
        "AC1 reference integrity",
        "all digests match by both routes; 150 rows per species",
        f"all_match={payload['reference']['all_match']}; "
        + ", ".join(f"{k}={v['n_states']}" for k, v in payload["z_factor"].items()),
        payload["reference"]["all_match"] and all(v["n_states"] == 150 for v in payload["z_factor"].values()),
    )

    methane = payload["z_factor"]["methane"]["methods"]
    met_ac2 = True
    observed_ac2 = []
    for name, block in methane.items():
        mean = block["all_states"]["mean_abs_relative_error"]
        worst = block["all_states"]["max_abs_relative_error"]
        met_ac2 = met_ac2 and mean <= 0.020 and worst <= 0.050
        observed_ac2.append(f"{name} mean {mean * 100:.3f}% max {worst * 100:.3f}%")
    add("AC2 methane Z", "mean <= 2.0% and max <= 5.0% for each method", "; ".join(observed_ac2), met_ac2)

    nitrogen = payload["z_factor"]["nitrogen"]["methods"]
    met_ac3 = True
    observed_ac3 = []
    for name, block in nitrogen.items():
        mean = block["all_states"]["mean_abs_relative_error"]
        worst = block["all_states"]["max_abs_relative_error"]
        met_ac3 = met_ac3 and mean <= 0.030 and worst <= 0.080
        observed_ac3.append(f"{name} mean {mean * 100:.3f}% max {worst * 100:.3f}%")
    add("AC3 nitrogen Z", "mean <= 3.0% and max <= 8.0% for each method", "; ".join(observed_ac3), met_ac3)

    co2 = payload["z_factor"]["carbon_dioxide"]["methods"]
    cold = {
        name: block["by_isotherm"].get("100F", {}).get("max_abs_relative_error")
        for name, block in co2.items()
    }
    cold_values = [v for v in cold.values() if v is not None]
    add(
        "AC4 CO2 near-critical failure, re-run of an existing assertion",
        "max abs relative error on the 100 degF isotherm >= 10% for at least one method",
        "; ".join(f"{k}={'n/a' if v is None else format(v * 100, '.2f') + '%'}" for k, v in cold.items()),
        bool(cold_values) and max(cold_values) >= 0.10,
    )

    dak_co2 = co2["dak"]["by_isotherm"]
    cold_dak = dak_co2.get("100F", {}).get("max_abs_relative_error")
    hot_dak = dak_co2.get("320F", {}).get("max_abs_relative_error")
    ratio = None if not (cold_dak and hot_dak) else cold_dak / hot_dak
    add(
        "AC5 CO2 error is near-critical, not uniform",
        "DAK max error at 100 degF is at least 2x the max at 320 degF",
        "n/a" if ratio is None else f"ratio {ratio:.2f} ({cold_dak * 100:.2f}% vs {hot_dak * 100:.2f}%)",
        ratio is not None and ratio >= 2.0,
    )

    visc = payload["viscosity"]["all_states"]
    add(
        "AC6 Lee-Gonzalez-Eakin viscosity",
        "mean abs relative error <= 5.0% and signed mean error positive",
        f"mean {visc['mean_abs_relative_error'] * 100:.3f}%, "
        f"signed mean {visc['mean_signed_relative_error'] * 100:+.3f}%",
        visc["mean_abs_relative_error"] <= 0.050 and visc["mean_signed_relative_error"] > 0.0,
    )

    standing = payload["standing_pseudocritical_variants"]
    ppc_max = standing["ppc"]["max_abs_relative_error"]
    z_max = standing["z"]["max_abs_relative_error"]
    bg_max = standing["bg"]["max_abs_relative_error"]
    add(
        "AC7 Standing variant consequence",
        "Ppc <= 2.0%, Z <= 1.0%, Bg <= 1.0% over the declared grid",
        f"Ppc {ppc_max * 100:.3f}%, Z {z_max * 100:.4f}%, Bg {bg_max * 100:.4f}%",
        ppc_max <= 0.020 and z_max <= 0.010 and bg_max <= 0.010,
    )

    return {"criteria": results, "all_met": all(item["met"] for item in results)}


def check_inconclusive(payload: dict[str, Any]) -> list[str]:
    """Test the four conditions the protocol declared would make the case inconclusive."""
    triggered: list[str] = []
    if not payload["reference"]["all_match"]:
        triggered.append("I1: reference digest mismatch")
    for species_name, block in payload["z_factor"].items():
        for method_name, method_block in block["methods"].items():
            if method_block["failure_fraction"] > 0.05:
                triggered.append(
                    f"I2: {species_name}/{method_name} failed on "
                    f"{method_block['failure_fraction'] * 100:.1f}% of states"
                )
    methane = payload["z_factor"]["methane"]["methods"]
    if all(block["all_states"]["mean_abs_relative_error"] > 0.020 for block in methane.values()):
        triggered.append("I3: all three correlations exceed 2% mean error on methane")
    scored = {item["criterion"][:4]: item["met"] for item in payload["acceptance"]["criteria"]}
    if scored.get("AC4") != scored.get("AC5"):
        triggered.append(
            "I4: AC4 and AC5 disagree, so a large CO2 error and a near-critical CO2 error "
            "were not observed together and the mechanism is not demonstrated"
        )
    if not payload["viscosity_instrument_control"]["all_controls_hold"]:
        triggered.append("I5: the viscosity instrument failed its own closed-form control")
    if not payload["reference_z_unit_chain_control"]["all_confirmed"]:
        triggered.append(
            "I6: the reference Z unit chain did not confirm, so the gas constant or the unit "
            "conversions behind every E1 number are in question and no error can be attributed"
        )
    return triggered


def render_text(payload: dict[str, Any]) -> str:
    """Render the readable console and file summary."""
    lines: list[str] = []
    out = lines.append
    out("Case A2 -- independent PVT check against NIST reference values")
    out("=" * 78)
    out("")
    out(f"Reference: {payload['reference']['source']}")
    out(f"Acquired:  {payload['reference']['acquired_utc_date']}")
    out(f"Digest:    {payload['reference']['route']}")
    for item in payload["reference"]["files"]:
        out(f"  {item['species']:<15} {item['path']:<34} sha256 {item['sha256_recomputed'][:16]}... ok")
    out("")
    out("E1  Deviation factor, correlation versus reference, all 150 states per species")
    out("    reduced properties formed from the true critical constants")
    out("")
    header = f"{'species':<16}{'method':<18}{'mean':>9}{'median':>9}{'max':>9}{'bias':>10}  worst at"
    out(header)
    out("-" * len(header))
    for species_name, block in payload["z_factor"].items():
        for method_name, method_block in block["methods"].items():
            stats = method_block["all_states"]
            worst = stats["worst_state"]
            out(
                f"{species_name:<16}{method_name:<18}"
                f"{stats['mean_abs_relative_error'] * 100:>8.3f}%"
                f"{stats['median_abs_relative_error'] * 100:>8.3f}%"
                f"{stats['max_abs_relative_error'] * 100:>8.3f}%"
                f"{stats['mean_signed_relative_error'] * 100:>+9.3f}%"
                f"  Tpr {worst['t_pr']:.4f}, Ppr {worst['p_pr']:.4f}"
                f" ({worst['temperature_degf']:.0f} F, {worst['pressure_psia']:.0f} psia, {worst['phase']})"
            )
    out("")
    out("    in-window subset only (states inside each correlation's published window)")
    for species_name, block in payload["z_factor"].items():
        for method_name, method_block in block["methods"].items():
            stats = method_block["in_window_only"]
            excluded = method_block["states_outside_published_window"]
            if stats["n"] == 0:
                out(f"      {species_name:<16}{method_name:<18} no state inside the window")
                continue
            out(
                f"      {species_name:<16}{method_name:<18}"
                f"n={stats['n']:>4} (excluded {excluded:>3})"
                f"  mean {stats['mean_abs_relative_error'] * 100:>7.3f}%"
                f"  max {stats['max_abs_relative_error'] * 100:>7.3f}%"
            )
    out("")
    out("    carbon dioxide by isotherm, DAK -- where the failure lives")
    for label, block in payload["z_factor"]["carbon_dioxide"]["methods"]["dak"]["by_isotherm"].items():
        out(
            f"      {label:<6} Tpr {block['t_pr']:.4f}"
            f"  mean {block['mean_abs_relative_error'] * 100:>7.3f}%"
            f"  max {block['max_abs_relative_error'] * 100:>7.3f}%"
            f"  at Ppr {block['p_pr_at_max']:.4f} ({block['pressure_psia_at_max']:.0f} psia)"
        )
    out("")
    visc = payload["viscosity"]
    out("E2  Lee-Gonzalez-Eakin viscosity versus reference methane viscosity")
    out(
        f"    reference density supplied directly; methane specific gravity "
        f"{visc['specific_gravity_of_methane']:.4f}"
    )
    for label, key in (
        ("all 150 states", "all_states"),
        ("p <= 2000 psia", "at_or_below_2000_psia"),
        ("p >  2000 psia", "above_2000_psia"),
    ):
        stats = visc[key]
        out(
            f"      {label:<16} n={stats['n']:>4}"
            f"  mean {stats['mean_abs_relative_error'] * 100:>6.3f}%"
            f"  median {stats['median_abs_relative_error'] * 100:>6.3f}%"
            f"  max {stats['max_abs_relative_error'] * 100:>6.3f}%"
            f"  bias {stats['mean_signed_relative_error'] * 100:>+6.3f}%"
        )
    out(
        f"      positive-error fraction {visc['fraction_of_states_with_positive_error'] * 100:.1f}%; "
        f"states outside the LGE window {visc['states_outside_lge_window']}"
    )
    out("")
    chain = payload["reference_z_unit_chain_control"]
    out("E1b Control on the reference Z definition, Z = p M / (rho R T)")
    gas_constant = chain["gas_constant"]
    out(
        f"      R field units: library {gas_constant['library_psia_cuft_per_lbmol_degr']:.9f}, "
        f"recomputed from SI definitions {gas_constant['recomputed_from_si_definitions']:.9f}, "
        f"relative difference {gas_constant['relative_difference']:.2e}"
    )
    out(
        f"      against the tabulated {gas_constant['tabulated_in_the_literature']:.4f}: "
        f"relative difference {gas_constant['relative_difference_against_tabulated']:.2e}"
    )
    si_route = chain["si_route_versus_field_route"]
    out(
        f"      reference Z recomputed in SI over {si_route['n_states']} states: "
        f"max relative difference {si_route['max_relative_difference']:.2e}"
    )
    for item in chain["molar_masses"]:
        out(
            f"      molar mass {item['species']:<15} manifest {item['manifest_lbm_per_lbmol']:>9.4f}"
            f"  IUPAC 2021 {item['iupac_2021_lbm_per_lbmol']:>9.4f}"
            f"  relative difference {item['relative_difference']:.2e}"
        )
    for item in chain["ideal_gas_limit"]:
        out(
            f"      ideal-gas anchor {item['species']:<10} at {item['pressure_psia']:.0f} psia: "
            f"max |Z_ref - 1| = {item['max_abs_departure_from_unity']:.5f} "
            f"over {item['n']} isotherms"
        )
    out(f"      confirmed within {chain['tolerance_relative']:g} relative: {chain['all_confirmed']}")
    out("")
    control = payload["viscosity_instrument_control"]
    out("E2b Instrument control: the published closed form, evaluated independently on invented states")
    for item in control["points"]:
        out(
            f"      T={item['temperature_degf']:>7.2f} degF"
            f"  M={item['molar_mass_lbm_per_lbmol']:>5.1f}"
            f"  rho={item['density_lbm_per_cuft']:>5.1f} lbm/ft3"
            f"  |library/closed form - 1| = {item['relative_difference']:.2e}"
            f"  {'holds' if item['closed_form_matches'] else 'DISAGREES'}"
        )
    out(f"      zero-density limit and unit conversion hold: {control['all_controls_hold']}")
    out("      establishes software behaviour only; reference agreement is E2, which needs the extract")
    out("")
    standing = payload["standing_pseudocritical_variants"]
    out("E3  Standing dry-gas pseudocritical pressure, 677 (Ahmed) versus 667 (Whitson & Brule)")
    out(
        f"    gravity {min(standing['specific_gravity_grid']):.2f} to "
        f"{max(standing['specific_gravity_grid']):.2f}, pressure "
        f"{min(standing['pressure_grid_psia']):.0f} to {max(standing['pressure_grid_psia']):.0f} psia, "
        f"{standing['temperature_degf']:.0f} degF"
    )
    out(
        f"    absolute Ppc difference {standing['absolute_ppc_difference_psia']:.1f} psia, constant by "
        f"construction"
    )
    for label, key in (("Ppc", "ppc"), ("Z (DAK)", "z"), ("Bg", "bg")):
        stats = standing[key]
        out(
            f"      {label:<10} n={stats['n']:>4}"
            f"  mean {stats['mean_abs_relative_error'] * 100:>7.4f}%"
            f"  max {stats['max_abs_relative_error'] * 100:>7.4f}%"
        )
    worst_z = standing["z"]["worst_state"]
    out(
        f"      worst Z difference at gravity {worst_z['specific_gravity']:.2f}, "
        f"{worst_z['pressure_psia']:.0f} psia"
    )
    out("")
    probe = payload["wichert_aziz_probe"]
    out("E4  Wichert-Aziz probe on pure carbon dioxide -- declared double extrapolation")
    out(
        f"    Sutton at gravity {probe['specific_gravity_of_co2']:.4f}: "
        f"Tpc {probe['sutton_tpc_degr']:.2f} degR (true {probe['true_critical_temperature_degr']:.2f}), "
        f"Ppc {probe['sutton_ppc_psia']:.2f} psia (true {probe['true_critical_pressure_psia']:.2f})"
    )
    out(
        f"    after Wichert-Aziz at y_co2 = 1.0: Tpc {probe['wichert_aziz_tpc_degr']:.2f} degR, "
        f"Ppc {probe['wichert_aziz_ppc_psia']:.2f} psia"
    )
    for label, key in (
        ("DAK on Sutton", "dak_on_sutton"),
        ("DAK on Sutton + WA", "dak_on_sutton_plus_wichert_aziz"),
    ):
        stats = probe[key]
        out(
            f"      {label:<20} mean {stats['mean_abs_relative_error'] * 100:>8.3f}%"
            f"  max {stats['max_abs_relative_error'] * 100:>8.3f}%"
        )
    out(
        f"      Wichert-Aziz epsilon peaks at y_co2 = {probe['epsilon_peak']['y_co2']:.2f}, "
        f"{probe['epsilon_peak']['epsilon_degr']:.2f} degR; at y_co2 = 1.00 it is "
        f"{probe['epsilon_profile_degr'][-1]['epsilon_degr']:.2f} degR"
    )
    out("")
    out("Pre-registered acceptance criteria (protocol.md section 5)")
    out("-" * 78)
    for item in payload["acceptance"]["criteria"]:
        out(f"  [{'PASS' if item['met'] else 'FAIL'}] {item['criterion']}")
        out(f"         threshold: {item['threshold']}")
        out(f"         observed:  {item['observed']}")
    out("")
    triggered = payload["inconclusive_conditions_triggered"]
    out(f"Inconclusive conditions triggered: {triggered if triggered else 'none'}")
    out(f"All criteria met: {payload['acceptance']['all_met']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    """Parse arguments, run the case under a write-once run record, and report."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, help="fresh run directory; it must not already exist")
    args = parser.parse_args()
    # Repository-relative from here on, so nothing machine-specific reaches the record.
    os.chdir(REPO_ROOT)

    config = {
        "case_id": "A2_pvt_independent_check",
        "species": list(SPECIES),
        "z_methods": sorted(Z_METHODS),
        "z_solver_tolerance": 1.0e-12,
        "z_solver_max_iterations": 100,
        "standing_gravity_grid": [c / 100.0 for c in STANDING_GRAVITIES_CENTI],
        "standing_pressure_grid_psia": list(STANDING_PRESSURES_PSIA),
        "standing_temperature_degf": STANDING_TEMPERATURE_DEGF,
        "epsilon_profile_y_co2": [c / 100.0 for c in EPSILON_PROFILE_CENTI],
        "standard_conditions": "SPE_STANDARD",
    }

    with RunRecord.open(
        args.out,
        label="Case A2: correlations versus NIST reference values",
        config=config,
        seed=SEED,
        settings={"reduced_properties": "true critical constants", "strict_range": False},
        repo_root=".",
    ) as run:
        reference_dir = REFERENCE_DIR.relative_to(REPO_ROOT)
        run.add_input(MANIFEST_PATH.relative_to(REPO_ROOT), role="reference-manifest")
        for name in SPECIES:
            run.add_input(reference_dir / f"nist_{name}_isotherms.tsv", role="reference-table")
        run.add_input("cases/A2_pvt_independent_check/protocol.md", role="protocol")
        run.add_input("cases/A2_pvt_independent_check/run.py", role="analysis-code")

        payload = build_payload()
        replica = build_payload()
        first = json.dumps(payload, sort_keys=True, default=str)
        second = json.dumps(replica, sort_keys=True, default=str)
        payload["determinism"] = {
            "check": "build_payload() called twice in one process, payloads serialised and compared",
            "identical": first == second,
        }
        if not payload["determinism"]["identical"]:
            raise RuntimeError("build_payload() is not deterministic; the case cannot be reported")

        payload["acceptance"] = evaluate_acceptance(payload)
        payload["inconclusive_conditions_triggered"] = check_inconclusive(payload)

        text = render_text(payload)
        print(text, end="")

        run.write_json("summary.json", payload)
        run.write_text("summary.txt", text)

        for species_name, block in payload["z_factor"].items():
            for method_name, method_block in block["methods"].items():
                run.metric(
                    f"z.{species_name}.{method_name}.mean_abs_relative_error",
                    method_block["all_states"]["mean_abs_relative_error"],
                )
                run.metric(
                    f"z.{species_name}.{method_name}.max_abs_relative_error",
                    method_block["all_states"]["max_abs_relative_error"],
                )
        run.metrics(
            viscosity_mean_abs_relative_error=payload["viscosity"]["all_states"]["mean_abs_relative_error"],
            viscosity_mean_signed_relative_error=payload["viscosity"]["all_states"][
                "mean_signed_relative_error"
            ],
            standing_ppc_max_abs_relative_error=payload["standing_pseudocritical_variants"]["ppc"][
                "max_abs_relative_error"
            ],
            standing_z_max_abs_relative_error=payload["standing_pseudocritical_variants"]["z"][
                "max_abs_relative_error"
            ],
            standing_bg_max_abs_relative_error=payload["standing_pseudocritical_variants"]["bg"][
                "max_abs_relative_error"
            ],
            viscosity_instrument_control_holds=payload["viscosity_instrument_control"]["all_controls_hold"],
            reference_z_unit_chain_confirmed=payload["reference_z_unit_chain_control"]["all_confirmed"],
            reference_z_si_route_max_relative_difference=payload["reference_z_unit_chain_control"][
                "si_route_versus_field_route"
            ]["max_relative_difference"],
            acceptance_all_met=payload["acceptance"]["all_met"],
            inconclusive_conditions_triggered=payload["inconclusive_conditions_triggered"],
        )
        run.note(
            "Reduced properties formed from true pure-component critical constants, so no "
            "pseudocritical correlation contaminates the deviation-factor attribution."
        )
        run.note(
            "Digest verified by two routes: the loader's internal check and an independent "
            "recomputation in this script."
        )
        run.limitation(
            "Pure components only. Nothing here establishes anything about a real field gas with "
            "heavy ends, nitrogen, carbon dioxide and condensate dropout."
        )
        run.limitation(
            "The NIST values are reference equation-of-state outputs, not laboratory measurements."
        )
        run.limitation(
            "The published accuracy figures for DAK, Hall-Yarborough and DPR are stated against the "
            "Standing-Katz natural-gas chart, and docs/evidence/zfactor.md records that the commonly "
            "quoted DAK figure could not be verified against the original paper. A pure-component "
            "comparison therefore tests applicability, not the published claim."
        )
        run.limitation(
            "E4 is a declared double extrapolation and says nothing about Wichert-Aziz on a real sour gas."
        )
        run.limitation(
            "E1b audits the gas constant, the unit chain and the molar masses behind the reference Z, "
            "but not the committed density column, which is common to both routes. Only a re-fetch "
            "from the WebBook settles a mis-retrieval."
        )
        run.limitation(
            "The reference methane viscosity model carries its own stated uncertainty, below 0.3 "
            "percent for 200 to 400 K under 30 MPa and below 2 percent over the rest of the surface. "
            "Part of this grid is in the wider band, so the measured LGE error is not a pure "
            "correlation error."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Loader for the committed NIST Chemistry WebBook reference extract.

What the data is
----------------
``data/reference`` holds three tab-separated isotherm tables -- methane, carbon
dioxide and nitrogen -- retrieved from the NIST Chemistry WebBook, SRD 69,
Thermophysical Properties of Fluid Systems (<https://webbook.nist.gov/chemistry/fluid/>).
Each file carries 150 states: five isotherms at 100, 160, 200, 260 and 320 degF swept
from 200 to 6000 psia in 200 psia steps.

They are values produced by the reference equations of state and transport models that
the WebBook cites, not laboratory measurements. That is still the right kind of oracle
here: the multiparameter Helmholtz-energy reference equations come from a different
model family, a different organisation and share no code with the correlations under
test, so agreement is evidence and disagreement localises to one side. It is not a
measurement, and nothing in this module claims otherwise.

Per-species references, recorded in ``MANIFEST.json`` and repeated here because a
citation that lives only in a data file tends not to travel:

* Methane density: Setzmann, U. and Wagner, W. (1991), *A New Equation of State and
  Tables of Thermodynamic Properties for Methane Covering the Range from the Melting
  Line to 625 K at Pressures up to 100 MPa*, J. Phys. Chem. Ref. Data 20(6), 1061-1155.
  Methane viscosity: Quinones-Cisneros, Huber and Deiters, unpublished work, 2011, as
  cited by SRD 69. See the open discrepancy below before quoting this one.
* Carbon dioxide density: Span, R. and Wagner, W. (1996), *A New Equation of State for
  Carbon Dioxide ...*, J. Phys. Chem. Ref. Data 25(6), 1509-1596.
* Nitrogen density: Span, R., Lemmon, E.W., Jacobsen, R.T., Wagner, W. and Yokozeki, A.
  (2000), *A Reference Equation of State for the Thermodynamic Properties of Nitrogen
  for Temperatures from 63.151 to 1000 K and Pressures to 2200 MPa*, J. Phys. Chem.
  Ref. Data 29(6), 1361-1433.

Open discrepancy, methane viscosity attribution
-----------------------------------------------
``MANIFEST.json`` records the methane ``viscosity_reference`` as Younglove, B.A. and
Ely, J.F. (1987), and :attr:`ReferenceSpecies.viscosity_reference` therefore reports
that. ``docs/evidence/viscosity.md`` records, marked as verified verbatim from the
WebBook fluid page for C74828 in the same retrieval session, that NIST cites
Quinones-Cisneros, Huber and Deiters (unpublished work, 2011) for methane viscosity,
together with that model's uncertainty ladder. The two cannot both describe the model
that produced the committed viscosity column.

The evidence card is the stronger record -- it quotes the page, the manifest entry does
not -- so this docstring follows the card, and the manifest is believed to be the side
that needs correcting. It is stated here rather than silently reconciled because the
manifest is the machine-readable field that would travel into a report, and because
settling it properly requires re-fetching the WebBook page, which was not done in the
session that found the disagreement. ``tests/test_gas_properties.py`` carries the
contradiction as an expected failure so that correcting the manifest turns the suite
red until the expectation is updated deliberately.

Digest verification
-------------------
Every file is hashed and compared against ``MANIFEST.json`` before a single row is
returned. A mismatch raises rather than skips. The point is narrow and worth stating:
if a reference file could be edited, a failing test could be made to pass by editing
the reference instead of the code, and the suite would then be measuring nothing.

Critical constants
------------------
The true pure-component critical constants are **not** in the manifest, and they are
not derivable from the isotherm tables. They are recorded in
:data:`CRITICAL_CONSTANTS` below so that a test can form Tpr and Ppr directly, without
routing the pure component through a gas-gravity pseudocritical correlation. That
matters for attribution: entering DAK through Standing or Sutton would mix the
pseudocritical correlation's error into the deviation-factor comparison, and a
disagreement could then no longer be assigned to either one.

Values in kelvin and MPa, each read from the NIST Chemistry WebBook fluid page for the
species (the same SRD 69 source as the isotherm tables, so the criticals and the states
come from one model each):

===============  ===============  ==============  ==================================
Species          Tc (K)           Pc (MPa)        WebBook fluid page
===============  ===============  ==============  ==================================
methane          190.564          4.5992          ``webbook.nist.gov/cgi/fluid.cgi?ID=C74828``
carbon dioxide   304.1282         7.3773          ``webbook.nist.gov/cgi/fluid.cgi?ID=C124389``
nitrogen         126.192          3.3958          ``webbook.nist.gov/cgi/fluid.cgi?ID=C7727379``
===============  ===============  ==============  ==================================

Retrieved and cross-checked against the field-unit figures those same pages print:
methane -116.65 degF / 667.06 psia, carbon dioxide 87.7608 degF / 1070.0 psia, nitrogen
-232.524 degF / 492.52 psia. Converting the SI values above with the exact factors in
:mod:`reservoir_lab.units` reproduces each of those to the digits the page displays
(343.0152 degR = -116.655 degF and 667.058 psia; 547.4308 degR = 87.761 degF and
1069.99 psia; 227.1456 degR = -232.524 degF and 492.52 psia). The criticals belong to
the same reference equations as the density tables -- Setzmann-Wagner, Span-Wagner and
Span et al. respectively -- which is why they are consistent with them.

Field-unit values are derived here, never transcribed: kelvin and MPa are converted
through :mod:`reservoir_lab.units`, whose factors are exact by definition of the units.
"""

from __future__ import annotations

import hashlib
import json
import math
import pathlib
from dataclasses import dataclass

from reservoir_lab.units import (
    GAS_CONSTANT_FIELD,
    PSI_IN_PASCAL,
    fahrenheit_to_rankine,
    kelvin_to_rankine,
    micropascal_second_to_centipoise,
)

__all__ = [
    "CRITICAL_CONSTANTS",
    "SPECIES",
    "CriticalConstants",
    "ReferenceDataError",
    "ReferenceSpecies",
    "ReferenceState",
    "load_species",
    "reference_data_available",
    "require_reference_data",
]

REFERENCE_DIR = pathlib.Path(__file__).resolve().parents[2] / "data" / "reference"
MANIFEST_PATH = REFERENCE_DIR / "MANIFEST.json"

#: Species names recognised by :func:`load_species`, in manifest order.
SPECIES = ("methane", "carbon_dioxide", "nitrogen")


class ReferenceDataError(RuntimeError):
    """The reference extract is present but does not match its manifest.

    Deliberately *not* a skip. An absent data directory is a checkout without the
    reference extract, which is a legitimate state; an altered file is a broken chain
    of custody between the published NIST values and the numbers a test asserts on.
    """


@dataclass(frozen=True)
class CriticalConstants:
    """True critical constants of a pure component.

    Attributes
    ----------
    temperature_kelvin:
        Critical temperature, K.
    pressure_mpa:
        Critical pressure, MPa.
    source:
        Where the two numbers came from, carried so a report can cite them.
    """

    temperature_kelvin: float
    pressure_mpa: float
    source: str

    @property
    def temperature_degr(self) -> float:
        """Critical temperature in degrees Rankine."""
        return kelvin_to_rankine(self.temperature_kelvin)

    @property
    def pressure_psia(self) -> float:
        """Critical pressure in psia."""
        return self.pressure_mpa * 1.0e6 / PSI_IN_PASCAL


#: See the module docstring for the retrieval and the cross-check against the field-unit
#: figures the same pages print.
_WEBBOOK = "NIST Chemistry WebBook SRD 69, fluid page for the species"
CRITICAL_CONSTANTS = {
    "methane": CriticalConstants(190.564, 4.5992, f"{_WEBBOOK} (C74828); Setzmann & Wagner (1991) EOS"),
    "carbon_dioxide": CriticalConstants(304.1282, 7.3773, f"{_WEBBOOK} (C124389); Span & Wagner (1996) EOS"),
    "nitrogen": CriticalConstants(126.192, 3.3958, f"{_WEBBOOK} (C7727379); Span et al. (2000) EOS"),
}


@dataclass(frozen=True)
class ReferenceState:
    """One (T, p) state from a NIST isotherm table.

    Attributes
    ----------
    temperature_degf:
        Temperature as requested from the WebBook, degrees Fahrenheit.
    pressure_psia:
        Absolute pressure, psia.
    density_lbm_per_cuft:
        Mass density from the species' reference equation of state, lbm/ft^3.
    viscosity_upa_s:
        Dynamic viscosity from the species' reference transport model, micropascal
        seconds.
    phase:
        The phase label the WebBook attached to the row: ``vapor``, ``liquid`` or
        ``supercritical``. Kept because a correlation fitted to natural gas has no
        business being judged against a liquid state without that being said out loud.
    """

    temperature_degf: float
    pressure_psia: float
    density_lbm_per_cuft: float
    viscosity_upa_s: float
    phase: str

    @property
    def temperature_degr(self) -> float:
        """Temperature in degrees Rankine."""
        return fahrenheit_to_rankine(self.temperature_degf)

    @property
    def viscosity_cp(self) -> float:
        """Viscosity in centipoise. The conversion is exact: 1 cp = 1000 uPa s."""
        return micropascal_second_to_centipoise(self.viscosity_upa_s)


@dataclass(frozen=True)
class ReferenceSpecies:
    """A verified species table plus everything needed to enter a correlation with it.

    Attributes
    ----------
    name:
        Manifest species key, one of :data:`SPECIES`.
    formula:
        Chemical formula, for report text.
    molar_mass_lbm_per_lbmol:
        Molar mass as recorded in the manifest. Used both for the deviation factor and
        as the ``M`` of a viscosity correlation.
    critical:
        True critical constants; see :data:`CRITICAL_CONSTANTS`.
    states:
        The 150 rows, in file order.
    eos_reference, viscosity_reference:
        The citations the manifest records for the two models.
    sha256:
        The verified digest of the file the states were read from.
    """

    name: str
    formula: str
    molar_mass_lbm_per_lbmol: float
    critical: CriticalConstants
    states: tuple[ReferenceState, ...]
    eos_reference: str
    viscosity_reference: str
    sha256: str

    def deviation_factor(self, state: ReferenceState) -> float:
        """Deviation factor implied by a reference density.

        ``Z = p M / (rho R T)`` with ``R`` taken from
        :data:`reservoir_lab.units.GAS_CONSTANT_FIELD`, ``p`` in psia, ``M`` in
        lbm/lbmol, ``rho`` in lbm/ft^3 and ``T`` in degrees Rankine. This is the
        definition of Z rearranged, not a correlation: the only modelling in the number
        is the reference equation of state that produced ``rho``.

        Raises
        ------
        ZeroDivisionError
            Never in practice -- every committed row has a strictly positive density --
            but the guard is the reader's, not the code's: a zero density would mean the
            file is not what this module thinks it is, and the digest check upstream
            would already have failed.
        """
        return (
            state.pressure_psia
            * self.molar_mass_lbm_per_lbmol
            / (state.density_lbm_per_cuft * GAS_CONSTANT_FIELD * state.temperature_degr)
        )

    def reduced(self, state: ReferenceState) -> tuple[float, float]:
        """``(t_pr, p_pr)`` formed from the TRUE critical constants.

        For a pure component the reduced properties are Tr and pr exactly; the "pseudo"
        prefix is only meaningful for a mixture. Forming them this way keeps a
        gas-gravity pseudocritical correlation out of the comparison entirely.
        """
        return (
            state.temperature_degr / self.critical.temperature_degr,
            state.pressure_psia / self.critical.pressure_psia,
        )


def _verify_digest(path: pathlib.Path, expected_sha256: str) -> str:
    """Hash ``path`` and compare against the manifest digest, raising on any drift."""
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_sha256:
        raise ReferenceDataError(
            f"{path.name} does not match its manifest digest: expected {expected_sha256}, "
            f"computed {digest}. The reference extract has been modified since it was "
            f"acquired. Re-fetch it with scripts/fetch_nist_reference.py rather than "
            f"adjusting the digest, and do not rely on any test result obtained from it."
        )
    return digest


def _parse_float(text: str, column: str, path: pathlib.Path, line_number: int) -> float:
    """Parse one cell, naming the file, line and column if it is unusable.

    The WebBook emits ``infinite`` and ``undefined`` in some columns at a phase
    boundary. None of the columns this loader reads should ever carry one, so such a
    value is reported rather than propagated as a NaN that would quietly poison a mean.
    """
    try:
        value = float(text)
    except ValueError as exc:
        raise ReferenceDataError(
            f"{path.name} line {line_number}: column {column!r} is not a number: {text!r}"
        ) from exc
    if not math.isfinite(value):
        raise ReferenceDataError(f"{path.name} line {line_number}: column {column!r} is not finite: {text!r}")
    return value


def _read_states(path: pathlib.Path, expected_rows: int) -> tuple[ReferenceState, ...]:
    """Read the tab-separated table, locating columns by header name, not by position."""
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ReferenceDataError(f"{path.name} is empty")
    header = lines[0].split("\t")
    wanted = (
        "Temperature (F)",
        "Pressure (psia)",
        "Density (lbm/ft3)",
        "Viscosity (uPa*s)",
        "Phase",
    )
    try:
        index = {name: header.index(name) for name in wanted}
    except ValueError as exc:
        raise ReferenceDataError(f"{path.name}: expected columns {wanted}, found {header}") from exc

    states = []
    for line_number, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        cells = line.split("\t")
        if len(cells) != len(header):
            raise ReferenceDataError(
                f"{path.name} line {line_number}: expected {len(header)} fields, got {len(cells)}"
            )
        states.append(
            ReferenceState(
                temperature_degf=_parse_float(
                    cells[index["Temperature (F)"]], "Temperature (F)", path, line_number
                ),
                pressure_psia=_parse_float(
                    cells[index["Pressure (psia)"]], "Pressure (psia)", path, line_number
                ),
                density_lbm_per_cuft=_parse_float(
                    cells[index["Density (lbm/ft3)"]], "Density (lbm/ft3)", path, line_number
                ),
                viscosity_upa_s=_parse_float(
                    cells[index["Viscosity (uPa*s)"]], "Viscosity (uPa*s)", path, line_number
                ),
                phase=cells[index["Phase"]].strip(),
            )
        )
    if len(states) != expected_rows:
        raise ReferenceDataError(
            f"{path.name}: manifest records {expected_rows} rows, file holds {len(states)}"
        )
    return tuple(states)


def reference_data_available() -> bool:
    """Report whether the manifest and all three tables are present in the checkout."""
    if not MANIFEST_PATH.is_file():
        return False
    try:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return all((REFERENCE_DIR / entry["path"]).is_file() for entry in manifest.get("files", ()))


def require_reference_data(test_case) -> None:
    """Skip ``test_case`` cleanly when the reference extract was not fetched.

    Absence is a checkout state, not a failure: the extract is a few tens of kilobytes
    of committed data, but a shallow or filtered checkout may not have it, and the rest
    of the suite still means something without it. A *modified* extract is a different
    matter and raises from :func:`load_species`.
    """
    if not reference_data_available():
        test_case.skipTest(
            f"NIST reference extract not present under {REFERENCE_DIR}; "
            f"fetch it with scripts/fetch_nist_reference.py"
        )


def load_species(name: str) -> ReferenceSpecies:
    """Load and digest-verify one species' reference table.

    Parameters
    ----------
    name:
        One of :data:`SPECIES`.

    Returns
    -------
    ReferenceSpecies
        The verified states plus molar mass, critical constants and citations.

    Raises
    ------
    KeyError
        If ``name`` is not a species in the manifest, or has no recorded critical
        constants.
    ReferenceDataError
        If the manifest or a table is missing, malformed, the wrong length, or fails
        its SHA-256 check.
    """
    if not MANIFEST_PATH.is_file():
        raise ReferenceDataError(f"no manifest at {MANIFEST_PATH}")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        if entry["species"] == name:
            break
    else:
        available = sorted(item["species"] for item in manifest["files"])
        raise KeyError(f"{name!r} is not in the reference manifest; available: {available}")

    path = REFERENCE_DIR / entry["path"]
    if not path.is_file():
        raise ReferenceDataError(f"manifest lists {entry['path']} but it is not present")
    digest = _verify_digest(path, entry["sha256"])
    if name not in CRITICAL_CONSTANTS:
        raise KeyError(f"no critical constants recorded for {name!r}")

    return ReferenceSpecies(
        name=name,
        formula=entry["formula"],
        molar_mass_lbm_per_lbmol=entry["molar_mass_lbm_per_lbmol"],
        critical=CRITICAL_CONSTANTS[name],
        states=_read_states(path, entry["rows"]),
        eos_reference=entry["eos_reference"],
        viscosity_reference=entry["viscosity_reference"],
        sha256=digest,
    )

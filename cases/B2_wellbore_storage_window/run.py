#!/usr/bin/env python3
"""Case B2 -- wellbore storage, and finding the radial window.

Runs the experiments frozen in ``protocol.md`` as amended by ``PROTOCOL_AMENDMENT_01.md``.
Every threshold is copied from the protocol verbatim; none is computed here and none may be
changed after a result exists.

The separation that matters
---------------------------
``analyst_interpretation`` receives a record and metadata. It never receives the true
permeability, skin, storage coefficient or regime boundaries. ``score`` receives both and is
the only function that sees truth. Nothing flows from ``score`` back into interpretation.
"""

from __future__ import annotations

import math
import pathlib
import sys
from dataclasses import dataclass
from typing import Any

CASE_DIR = pathlib.Path(__file__).resolve().parent
REPO = CASE_DIR.parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(CASE_DIR))

from wbs_model import (  # noqa: E402
    WellboreStorageModel,
    dimensionless_storage_coefficient,
)

from reservoir_lab.diagnostics import bourdet_derivative  # noqa: E402
from reservoir_lab.regime import (  # noqa: E402
    WindowSettings,
    identify_radial_window,
)
from reservoir_lab.transient import (  # noqa: E402
    semilog_interpretation,
)

CASE_ID = "B2_wellbore_storage_window"
PROTOCOL_COMMIT = "d6624f7982037f3eab42864ede3a073ca90a1321"
AMENDMENT = "PROTOCOL_AMENDMENT_01.md"

# --- generator truth, protocol section 5 -----------------------------------------
TRUTH = {
    "permeability_md": 50.0,
    "thickness_ft": 40.0,
    "porosity": 0.18,
    "total_compressibility_per_psi": 1.5e-05,
    "viscosity_cp": 1.2,
    "formation_volume_factor": 1.25,
    "wellbore_radius_ft": 0.35,
    "initial_pressure_psia": 4000.0,
    "rate_stb_per_day": 350.0,
    "skin": 3.5,
}

FIRST_HOUR = 0.001
LAST_HOUR = 48.0
POINTS_PER_DECADE = 20
SMOOTHING_L = 0.1

# --- pre-registered sweep levels, protocol section 10 ----------------------------
STORAGE_LEVELS_CD = (100.0, 1000.0, 3000.0, 10000.0)
DURATION_HOURS = (48.0, 24.0, 12.0, 6.0, 3.0)
SAMPLING_PER_DECADE = (5, 10, 20, 50)
NOISE_SIGMAS_PSI = (0.1, 0.5, 2.0, 10.0)
NOISE_REPLICATES = 200
NOISE_SEED_BASE = 20260916
PRIMARY_CD = 1000.0
DURATION_SWEEP_CD = 3000.0
INCONCLUSIVE_CD = 10000.0
INCONCLUSIVE_HOURS = 3.0
L_SENSITIVITY = (0.0, 0.1, 0.2, 0.3)

# --- thresholds, copied verbatim from protocol section 13 ------------------------
C1_KNOWN_INVERSE = 1e-8
C1_CROSS_CHECK = 1e-6
C2A_STORAGE_FREE = 1e-6
C2B_B1_CONSISTENCY = 1e-4
C3_STORAGE_BRANCH = 1e-2
C5_KH_RELATIVE = 0.05
C6_SKIN_ABSOLUTE = 0.5
C7_DERIVATIVE_RELATIVE = 1e-3

B1_WINDOW_TD = (3.322e4, 1.595e6)
LINE_SOURCE_CONSTANT = math.log(4.0) - 0.5772156649015329


def t_d_per_hour() -> float:
    """Return dimensionless time per elapsed hour at the declared properties."""
    return (0.0002637 * TRUTH["permeability_md"]) / (
        TRUTH["porosity"]
        * TRUTH["viscosity_cp"]
        * TRUTH["total_compressibility_per_psi"]
        * TRUTH["wellbore_radius_ft"] ** 2
    )


def pressure_scale_psi() -> float:
    """141.2 q B mu / (k h): the factor converting p_D to psi."""
    return (141.2 * TRUTH["rate_stb_per_day"] * TRUTH["formation_volume_factor"] * TRUTH["viscosity_cp"]) / (
        TRUTH["permeability_md"] * TRUTH["thickness_ft"]
    )


def storage_bbl_per_psi(c_d: float) -> float:
    """Return the field storage coefficient matching a dimensionless one."""
    unit = dimensionless_storage_coefficient(
        1.0,
        porosity=TRUTH["porosity"],
        total_compressibility_per_psi=TRUTH["total_compressibility_per_psi"],
        thickness_ft=TRUTH["thickness_ft"],
        wellbore_radius_ft=TRUTH["wellbore_radius_ft"],
    )
    return c_d / unit


def log_times(first: float, last: float, per_decade: int) -> list[float]:
    """Return log-spaced times, the sampling the protocol declares."""
    n = round(math.log10(last / first) * per_decade)
    return [first * 10.0 ** (i / per_decade) for i in range(n + 1)]


# =================================================================================
# GENERATOR -- knows the truth
# =================================================================================
@dataclass(frozen=True)
class Record:
    """What the analyst receives. Carries no truth."""

    times_hours: tuple[float, ...]
    drawdown_psi: tuple[float, ...]


def generate(*, c_d: float, skin: float, hours: tuple[float, float], per_decade: int) -> Record:
    """Return the synthetic record a gauge would see. The generator knows the truth."""
    model = WellboreStorageModel(storage_dimensionless=c_d, skin=skin)
    scale = pressure_scale_psi()
    per_hour = t_d_per_hour()
    times = log_times(hours[0], hours[1], per_decade)
    drawdown = [model.pressure(t * per_hour) * scale for t in times]
    return Record(tuple(times), tuple(drawdown))


# =================================================================================
# ANALYST -- receives the record and the metadata a real interpretation has
# =================================================================================
@dataclass(frozen=True)
class Interpretation:
    """What the analyst concluded, and nothing about whether it is right."""

    found_window: bool
    reason: str
    window_start_hours: float
    window_end_hours: float
    window_decades: float
    window_points: int
    permeability_thickness_md_ft: float
    permeability_md: float
    skin: float
    slope_psi_per_cycle: float
    r_squared: float


def analyst_interpretation(record: Record, *, smoothing_l: float = SMOOTHING_L) -> Interpretation:
    """Interpret a record. No true parameter is in scope anywhere in this function."""
    nan = float("nan")
    if len(record.times_hours) < 5:
        return Interpretation(
            False, "record too short to differentiate", nan, nan, 0.0, 0, nan, nan, nan, nan, nan
        )

    d_times, d_values = bourdet_derivative(record.times_hours, record.drawdown_psi, smoothing_l=smoothing_l)
    index = {t: i for i, t in enumerate(record.times_hours)}
    dp_at = [record.drawdown_psi[index[t]] for t in d_times]

    window = identify_radial_window(
        d_times, d_values, dp_at, settings=WindowSettings(), smoothing_l=smoothing_l
    )
    if not window.found:
        return Interpretation(False, window.reason, nan, nan, 0.0, 0, nan, nan, nan, nan, nan)

    lo, hi = window.start_time, window.end_time
    selected = [(t, p) for t, p in zip(record.times_hours, record.drawdown_psi, strict=True) if lo <= t <= hi]
    fit = semilog_interpretation(
        [t for t, _ in selected],
        [p for _, p in selected],
        thickness_ft=TRUTH["thickness_ft"],
        rate_stb_per_day=TRUTH["rate_stb_per_day"],
        formation_volume_factor=TRUTH["formation_volume_factor"],
        viscosity_cp=TRUTH["viscosity_cp"],
        porosity=TRUTH["porosity"],
        total_compressibility_per_psi=TRUTH["total_compressibility_per_psi"],
        wellbore_radius_ft=TRUTH["wellbore_radius_ft"],
    )
    return Interpretation(
        True,
        "",
        lo,
        hi,
        window.decades,
        window.points,
        fit.permeability_md * TRUTH["thickness_ft"],
        fit.permeability_md,
        fit.skin,
        fit.slope_psi_per_cycle,
        fit.r_squared,
    )


# =================================================================================
# SCORER -- the only place truth appears
# =================================================================================
def score(interp: Interpretation) -> dict[str, Any]:
    """Compare an interpretation against the truth. The only function that sees it."""
    if not interp.found_window:
        return {"verdict": "INCONCLUSIVE", "reason": interp.reason}
    true_kh = TRUTH["permeability_md"] * TRUTH["thickness_ft"]
    return {
        "verdict": "interpreted",
        "permeability_thickness_relative_error": abs(interp.permeability_thickness_md_ft - true_kh) / true_kh,
        "skin_absolute_error": abs(interp.skin - TRUTH["skin"]),
        "permeability_thickness_recovered": interp.permeability_thickness_md_ft,
        "skin_recovered": interp.skin,
    }


def crossover_hours(c_d: float) -> float:
    """Where the storage line meets the semilog line. Scoring only, never selection."""
    s = TRUTH["skin"]
    lo, hi = 1.0, 1e12
    for _ in range(200):
        mid = math.sqrt(lo * hi)
        if mid / c_d < 0.5 * (math.log(mid) + LINE_SOURCE_CONSTANT) + s:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi) / t_d_per_hour()

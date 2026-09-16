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

import argparse
import hashlib
import json
import math
import pathlib
import random
import statistics
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
from reservoir_lab.errors import NotIdentifiableError  # noqa: E402
from reservoir_lab.provenance import RunRecord  # noqa: E402
from reservoir_lab.regime import (  # noqa: E402
    WindowSettings,
    identify_radial_window,
    local_log_slope,
)
from reservoir_lab.transient import (  # noqa: E402
    semilog_interpretation,
)

CASE_ID = "B2_wellbore_storage_window"
PROTOCOL_COMMIT = "d6624f7982037f3eab42864ede3a073ca90a1321"
AMENDMENT = "PROTOCOL_AMENDMENT_01.md"
PROTOCOL_PATH = CASE_DIR / "protocol.md"
AMENDMENT_PATH = CASE_DIR / AMENDMENT


def blob_digest(path: pathlib.Path) -> str:
    """Return git's blob hash of a file, computed at run time.

    Computed rather than stored, so editing the protocol after a result exists shows up as a
    changed digest in every later run record instead of passing unnoticed. Checkable with
    ``git hash-object``.
    """
    raw = path.read_bytes()
    return hashlib.sha1(b"blob %d\x00" % len(raw) + raw).hexdigest()


def canonical_hash(payload: Any) -> str:
    """Order-independent digest of a result payload, as case B1 records."""
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=repr).encode()
    ).hexdigest()


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
    widest_decades: float
    most_points: int
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
            False, "record too short to differentiate", 0.0, 0, nan, nan, 0.0, 0, nan, nan, nan, nan, nan
        )

    try:
        d_times, d_values = bourdet_derivative(
            record.times_hours, record.drawdown_psi, smoothing_l=smoothing_l
        )
    except NotIdentifiableError as exc:
        # A record too short to carry a Bourdet derivative on both sides cannot certify a
        # window. That is a decline, not an error: the rule's contract is to say no and give
        # the reason. The duration sweep and the post-hoc scan both reach records this short
        # by design, and a rule that raised there would be refusing to answer its own question.
        return Interpretation(False, str(exc), 0.0, 0, nan, nan, 0.0, 0, nan, nan, nan, nan, nan)
    index = {t: i for i, t in enumerate(record.times_hours)}
    dp_at = [record.drawdown_psi[index[t]] for t in d_times]

    window = identify_radial_window(
        d_times, d_values, dp_at, settings=WindowSettings(), smoothing_l=smoothing_l
    )
    if not window.found:
        return Interpretation(
            False,
            window.reason,
            window.widest_decades,
            window.most_points,
            nan,
            nan,
            0.0,
            0,
            nan,
            nan,
            nan,
            nan,
            nan,
        )

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
        window.widest_decades,
        window.most_points,
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


# =================================================================================
# RECORD CACHE
# =================================================================================
# Generating a record costs one numerical inversion per sample point, so records that
# several experiments share are generated once. The cache changes no result: the sweeps
# below are defined on the same grid, and ``log_times`` makes a shorter record an exact
# prefix of a longer one at the same first hour and density, because every time is
# ``first * 10**(i/per_decade)`` for the same ``i``.
_RECORDS: dict[tuple[float, float, float, float, int], Record] = {}


def cached_record(*, c_d: float, skin: float, hours: tuple[float, float], per_decade: int) -> Record:
    """Return a generated record, reusing an identical earlier one."""
    key = (c_d, skin, hours[0], hours[1], per_decade)
    if key not in _RECORDS:
        _RECORDS[key] = generate(c_d=c_d, skin=skin, hours=hours, per_decade=per_decade)
    return _RECORDS[key]


def truncated(record: Record, last_hour: float) -> Record:
    """Return the record with everything after ``last_hour`` removed.

    Truncation, not regeneration. The pressure at a retained time does not depend on how
    long the test ran, so this is the same record a shorter test would have produced, and
    it avoids inverting the same transform twice.
    """
    keep = [(t, p) for t, p in zip(record.times_hours, record.drawdown_psi, strict=True) if t <= last_hour]
    return Record(tuple(t for t, _ in keep), tuple(p for _, p in keep))


def interpretation_payload(interp: Interpretation) -> dict[str, Any]:
    """Serialise an interpretation under the parameter-reporting policy.

    **An INCONCLUSIVE case never carries a permeability or a skin.** The selector declined,
    so there is no analyst estimate to report, and emitting one here would let a number the
    rule refused to certify travel into a table, a figure or a page. Protocol section 7 and
    the governing reporting policy both require the absence rather than a null field.
    """
    if not interp.found_window:
        return {
            "window_found": False,
            "verdict": "INCONCLUSIVE",
            "reason": interp.reason,
            # How far short the record fell, so a decline can be drawn and compared instead of
            # only asserted. This is a property of the rule's own search, available to the
            # analyst, and it is not a parameter estimate of any kind.
            "widest_admissible_decades": interp.widest_decades,
            "most_admissible_points": interp.most_points,
        }
    return {
        "window_found": True,
        "verdict": "interpreted",
        "window_start_hours": interp.window_start_hours,
        "window_end_hours": interp.window_end_hours,
        "window_decades": interp.window_decades,
        "window_points": interp.window_points,
        "permeability_thickness_md_ft": interp.permeability_thickness_md_ft,
        "skin": interp.skin,
        "slope_psi_per_cycle": interp.slope_psi_per_cycle,
        "r_squared": interp.r_squared,
    }


def scored_payload(interp: Interpretation) -> dict[str, Any]:
    """Serialise the ex-post score. Labelled, because it is not analyst-available."""
    payload: dict[str, Any] = {
        "basis": "EX POST SCORING AGAINST SYNTHETIC TRUTH -- not an analyst-available result",
        **score(interp),
    }
    return payload


def series_payload(record: Record, *, c_d: float, smoothing_l: float = SMOOTHING_L) -> dict[str, Any]:
    """Return the arrays a figure draws, exported from the audited run rather than recomputed.

    Carries what an interpreter sees -- time, pressure change, the Bourdet derivative, its
    local log-log slope, and the storage ratio the rule's condition (b) tests -- plus the
    model's own analytic derivative, which is a generator quantity and is named as one so a
    figure cannot present it as data.
    """
    model = WellboreStorageModel(storage_dimensionless=c_d, skin=TRUTH["skin"])
    per_hour = t_d_per_hour()
    scale = pressure_scale_psi()
    try:
        d_times, d_values = bourdet_derivative(
            record.times_hours, record.drawdown_psi, smoothing_l=smoothing_l
        )
    except NotIdentifiableError:
        return {"derivative_available": False}
    index = {t: i for i, t in enumerate(record.times_hours)}
    dp_at = [record.drawdown_psi[index[t]] for t in d_times]
    slope_i, slope_m = local_log_slope(d_times, d_values, smoothing_l=smoothing_l)
    return {
        "derivative_available": True,
        "time_hours": list(record.times_hours),
        "drawdown_psi": list(record.drawdown_psi),
        "derivative_time_hours": list(d_times),
        "derivative_psi": list(d_values),
        "storage_ratio": [d / p for d, p in zip(d_values, dp_at, strict=True)],
        "slope_time_hours": [d_times[i] for i in slope_i],
        "local_log_slope": list(slope_m),
        "generator_derivative_psi": [model.log_derivative(t * per_hour) * scale for t in d_times],
        "flatness_epsilon": WindowSettings().flatness,
        "storage_ratio_limit": WindowSettings().storage_ratio,
    }


def case_result(record: Record, *, smoothing_l: float = SMOOTHING_L) -> dict[str, Any]:
    """Run one record through the analyst and the scorer, and package both halves."""
    interp = analyst_interpretation(record, smoothing_l=smoothing_l)
    return {
        "analyst": interpretation_payload(interp),
        "ex_post_scoring": scored_payload(interp),
        "points_in_record": len(record.times_hours),
    }


# =================================================================================
# NUMERICAL QUALIFICATION -- criteria C1, C2a, C2b, C3, C3b, C7
# =================================================================================
KNOWN_INVERSE_CASES = (
    ("constant", "1/u", ("1e-3", "1", "1e3", "1e6")),
    ("ramp", "1/u**2", ("1e-3", "1", "1e3", "1e6")),
    ("exponential", "1/(u+2)", ("1e-3", "0.1", "1")),
    ("diffusion", "exp(-sqrt(u))/u", ("1", "1e3", "1e6")),
    ("sqrt_decay", "1/sqrt(u)", ("1e-3", "1", "1e3", "1e6")),
)


def qualify_inversion() -> dict[str, Any]:
    """C1. de Hoog on transforms with known exact inverses, then Stehfest on B2's own.

    The class-matched set and its scoring range are fixed in protocol section 13.0b, which
    records why an oscillatory transform and two underflowing points were removed and that
    the 1e-8 threshold was not moved. Nothing here is re-selected after a result.
    """
    import mpmath as mp
    from wbs_model import INVERSION

    transforms = {
        "constant": (lambda u: 1 / u, lambda _t: mp.mpf(1)),
        "ramp": (lambda u: 1 / u**2, lambda t: t),
        "exponential": (lambda u: 1 / (u + 2), lambda t: mp.e ** (-2 * t)),
        "diffusion": (lambda u: mp.e ** (-mp.sqrt(u)) / u, lambda t: mp.erfc(1 / (2 * mp.sqrt(t)))),
        "sqrt_decay": (lambda u: 1 / mp.sqrt(u), lambda t: 1 / mp.sqrt(mp.pi * t)),
    }
    worst = 0.0
    worst_at = ""
    scored: list[dict[str, Any]] = []
    with mp.workdps(INVERSION.dps):
        for name, expression, times in KNOWN_INVERSE_CASES:
            transform, exact = transforms[name]
            for tv in times:
                t = mp.mpf(tv)
                got = mp.invertlaplace(transform, t, method="dehoog", degree=INVERSION.dehoog_degree)
                rel = float(abs(got - exact(t)) / abs(exact(t)))
                scored.append({"transform": name, "expression": expression, "t": float(t), "relative": rel})
                if rel > worst:
                    worst, worst_at = rel, f"{name} at t={tv}"

    model = WellboreStorageModel(storage_dimensionless=PRIMARY_CD, skin=TRUTH["skin"])
    cross: list[dict[str, Any]] = []
    cross_worst = 0.0
    for t_d in (1e2, 1e4, 1e6, t_d_per_hour() * LAST_HOUR):
        a = model.pressure(t_d, method="dehoog")
        b = model.pressure(t_d, method="stehfest")
        rel = abs(a - b) / abs(a)
        cross.append({"t_d": t_d, "dehoog": a, "stehfest": b, "relative": rel})
        cross_worst = max(cross_worst, rel)

    convergence = []
    t_probe = t_d_per_hour() * 35.0
    for dps in (30, 50, 80):
        for degree in (18, 24, 30):
            from wbs_model import InversionSettings

            probe = WellboreStorageModel(
                storage_dimensionless=PRIMARY_CD,
                skin=TRUTH["skin"],
                settings=InversionSettings(dps=dps, dehoog_degree=degree),
            )
            convergence.append(
                {
                    "dps": dps,
                    "degree": degree,
                    "pressure_dimensionless": probe.pressure(t_probe),
                    "log_derivative": probe.log_derivative(t_probe),
                }
            )
    spread = max(c["pressure_dimensionless"] for c in convergence) - min(
        c["pressure_dimensionless"] for c in convergence
    )

    return {
        "known_inverse_scored": scored,
        "known_inverse_worst_relative": worst,
        "known_inverse_worst_at": worst_at,
        "known_inverse_threshold": C1_KNOWN_INVERSE,
        "cross_check": cross,
        "cross_check_worst_relative": cross_worst,
        "cross_check_threshold": C1_CROSS_CHECK,
        "cross_check_status": "ALGORITHMIC INVERSION CROSS-CHECK -- not an independent physics oracle",
        "precision_degree_convergence": convergence,
        "precision_degree_spread": spread,
        "probe_t_d": t_probe,
        "met": worst <= C1_KNOWN_INVERSE and cross_worst <= C1_CROSS_CHECK,
    }


def qualify_limits() -> dict[str, Any]:
    """Return C2a, C2b, C3 and C3b: the limiting behaviours protocol section 8b requires."""
    from wbs_model import storage_asymptote_residual

    per_hour = t_d_per_hour()
    times = [t * per_hour for t in log_times(FIRST_HOUR, LAST_HOUR, POINTS_PER_DECADE)]

    # C2a: the storage term switched off.
    tiny = WellboreStorageModel(storage_dimensionless=1e-6, skin=TRUTH["skin"])
    free = WellboreStorageModel(storage_dimensionless=0.0, skin=TRUTH["skin"])
    c2a_worst = max(abs(tiny.pressure(t) - free.pressure(t)) / abs(free.pressure(t)) for t in times)

    # C2b: late-time consistency with B1's line source, over B1's declared window.
    c2b = []
    c2b_worst = 0.0
    for t_d in (B1_WINDOW_TD[0], 1e5, 3e5, B1_WINDOW_TD[1]):
        finite = free.pressure(t_d) - TRUTH["skin"]
        line = 0.5 * (math.log(t_d) + LINE_SOURCE_CONSTANT)
        rel = abs(finite - line) / abs(line)
        c2b.append({"t_d": t_d, "finite_radius": finite, "line_source": line, "relative": rel})
        c2b_worst = max(c2b_worst, rel)

    # C3: the storage branch, where pure storage exceeds the storage-free response 1000x.
    c3 = []
    c3_worst = 0.0
    for c_d in STORAGE_LEVELS_CD:
        model = WellboreStorageModel(storage_dimensionless=c_d, skin=TRUTH["skin"])
        t_d = _storage_branch_probe(c_d, free)
        predicted = t_d / c_d
        rel = abs(model.pressure(t_d) - predicted) / predicted
        c3.append({"storage_dimensionless": c_d, "t_d": t_d, "pure_storage": predicted, "relative": rel})
        c3_worst = max(c3_worst, rel)

    # C3b: the zero-skin regression that motivated the amendment.
    zero_skin_residual = float(storage_asymptote_residual(storage_dimensionless=PRIMARY_CD, skin=0.0))
    zero = WellboreStorageModel(storage_dimensionless=PRIMARY_CD, skin=0.0)
    plateau_zero_skin = zero.log_derivative(per_hour * LAST_HOUR)
    zero_monotone = all(
        zero.pressure(times[i]) < zero.pressure(times[i + 1]) for i in range(0, len(times) - 1, 12)
    )

    return {
        "c2a_storage_free_worst_relative": c2a_worst,
        "c2a_threshold": C2A_STORAGE_FREE,
        "c2a_met": c2a_worst <= C2A_STORAGE_FREE,
        "c2b_b1_consistency": c2b,
        "c2b_worst_relative": c2b_worst,
        "c2b_threshold": C2B_B1_CONSISTENCY,
        "c2b_met": c2b_worst <= C2B_B1_CONSISTENCY,
        "c3_storage_branch": c3,
        "c3_worst_relative": c3_worst,
        "c3_threshold": C3_STORAGE_BRANCH,
        "c3_met": c3_worst <= C3_STORAGE_BRANCH,
        "c3b_zero_skin_asymptote_residual": zero_skin_residual,
        "c3b_zero_skin_plateau": plateau_zero_skin,
        "c3b_zero_skin_monotone": zero_monotone,
        "c3b_met": (
            zero_skin_residual <= C3_STORAGE_BRANCH
            and zero_monotone
            and abs(plateau_zero_skin - 0.5) / 0.5 <= 0.05
        ),
    }


def _storage_branch_probe(c_d: float, storage_free: WellboreStorageModel) -> float:
    """Return the latest t_D at which storage still outweighs the reservoir a thousandfold.

    C3 scores the storage branch at the edge of the storage-dominated region -- the most
    demanding point in it -- where the reservoir response the well would have produced is a
    thousand times the pure-storage prediction. Almost no fluid is entering the formation
    there, so ``p_wD -> t_D/C_D``, and the residual is the fraction that does.

    A note on the criterion's wording. Protocol C3 says "where the pure-storage prediction
    exceeds the storage-free response by 1000x", which read literally selects *late* time,
    deep in radial flow, where a storage branch does not exist at all and the comparison is
    meaningless. The protocol's own derivation settles which was meant: it predicts that the
    correction to pure storage is "about 0.1 percent" at this point, and the early-time
    reading measures 0.055 percent while the literal reading measures 99 percent. A
    derivation that predicts 0.1 percent is not describing the branch that gives 99. The
    condition is therefore applied in the direction the derivation computes.

    **Nothing about the criterion is relaxed by this.** The 1000x factor and the 1e-2
    threshold are the protocol's, unchanged. An earlier implementation here searched the
    literal direction, found the condition nowhere inside its bracket, silently collapsed to
    the bracket's upper bound and reported a 99 percent residual -- a failing verification
    criterion that was an artefact of this function and not a property of the model. The
    bracket is now checked rather than assumed.
    """

    def dominance(t_d: float) -> float:
        return storage_free.pressure(t_d) / (t_d / c_d)

    lo, hi = 1e-8, 1e6
    if dominance(lo) <= 1000.0 or dominance(hi) >= 1000.0:
        raise ValueError(
            f"the storage-dominance crossing is not inside the bracket for C_D={c_d}: "
            f"dominance is {dominance(lo):.3e} at t_D={lo:g} and {dominance(hi):.3e} at "
            f"t_D={hi:g}. Refusing to report a probe time the bisection did not locate."
        )
    for _ in range(60):
        mid = math.sqrt(lo * hi)
        if dominance(mid) > 1000.0:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)


def bourdet_against_model(record: Record, interp: Interpretation, *, c_d: float) -> dict[str, Any]:
    """C7. The Bourdet chain against the model's own analytic log-derivative.

    Over the selected window where one exists. Where the selector declined there is no
    selected window, so the criterion has no domain on that case: it is reported as NOT
    EVALUABLE rather than as a pass or a fail, and the same comparison is made over the
    whole record so the numerics are still checked.
    """
    model = WellboreStorageModel(storage_dimensionless=c_d, skin=TRUTH["skin"])
    per_hour = t_d_per_hour()
    scale = pressure_scale_psi()
    d_times, d_values = bourdet_derivative(record.times_hours, record.drawdown_psi, smoothing_l=SMOOTHING_L)

    def compare(pairs: list[tuple[float, float]]) -> float:
        worst = 0.0
        for t, got in pairs:
            exact = model.log_derivative(t * per_hour) * scale
            worst = max(worst, abs(got - exact) / abs(exact))
        return worst

    everywhere = compare(list(zip(d_times, d_values, strict=True))[:: max(1, len(d_times) // 12)])
    if not interp.found_window:
        return {
            "evaluable": False,
            "status": "NOT EVALUABLE -- the selector returned INCONCLUSIVE, so no window was selected",
            "whole_record_worst_relative": everywhere,
            "threshold": C7_DERIVATIVE_RELATIVE,
        }
    inside = [
        (t, d)
        for t, d in zip(d_times, d_values, strict=True)
        if interp.window_start_hours <= t <= interp.window_end_hours
    ]
    worst = compare(inside)
    return {
        "evaluable": True,
        "window_worst_relative": worst,
        "whole_record_worst_relative": everywhere,
        "threshold": C7_DERIVATIVE_RELATIVE,
        "met": worst <= C7_DERIVATIVE_RELATIVE,
    }


# =================================================================================
# THE PRE-REGISTERED EXPERIMENTS, protocol section 10
# =================================================================================
B1_WINDOW_HOURS = (1.0, 48.0)
B1_POINTS_PER_DECADE = 50
B2_0_CD = 1e-3


def experiment_b2_0() -> dict[str, Any]:
    """Run B2.0, the storage-free regression that asks whether the amended model reproduces B1.

    Two forms, as the protocol asks. Pointwise against B1's line-source closed form, and
    parameter-level over B1's own window and sampling. The two models are not identical and
    are not meant to be: one well has a radius. C2b bounds the difference at a value measured
    before any experiment existed.
    """
    per_hour = t_d_per_hour()
    scale = pressure_scale_psi()
    model = WellboreStorageModel(storage_dimensionless=B2_0_CD, skin=TRUTH["skin"])

    pointwise = []
    worst = 0.0
    for hours in log_times(*B1_WINDOW_HOURS, B1_POINTS_PER_DECADE)[::10]:
        t_d = hours * per_hour
        finite = model.pressure(t_d)
        line = 0.5 * (math.log(t_d) + LINE_SOURCE_CONSTANT) + TRUTH["skin"]
        rel = abs(finite - line) / abs(line)
        pointwise.append(
            {"hours": hours, "t_d": t_d, "finite_radius": finite, "b1_line_source": line, "relative": rel}
        )
        worst = max(worst, rel)

    # Parameter level, over B1's exact window and sampling.
    times = log_times(*B1_WINDOW_HOURS, B1_POINTS_PER_DECADE)
    drops = [model.pressure(t * per_hour) * scale for t in times]
    fit = semilog_interpretation(
        times,
        drops,
        thickness_ft=TRUTH["thickness_ft"],
        rate_stb_per_day=TRUTH["rate_stb_per_day"],
        formation_volume_factor=TRUTH["formation_volume_factor"],
        viscosity_cp=TRUTH["viscosity_cp"],
        porosity=TRUTH["porosity"],
        total_compressibility_per_psi=TRUTH["total_compressibility_per_psi"],
        wellbore_radius_ft=TRUTH["wellbore_radius_ft"],
    )
    true_kh = TRUTH["permeability_md"] * TRUTH["thickness_ft"]
    kh = fit.permeability_md * TRUTH["thickness_ft"]

    # And the same record put through the frozen selector, which is what B2 actually tests.
    record = cached_record(
        c_d=B2_0_CD, skin=TRUTH["skin"], hours=(FIRST_HOUR, LAST_HOUR), per_decade=POINTS_PER_DECADE
    )
    selector = case_result(record)
    interp = analyst_interpretation(record)
    return {
        "storage_dimensionless": B2_0_CD,
        "pointwise_against_b1": pointwise,
        "pointwise_worst_relative": worst,
        "over_b1_window": {
            "window_hours": list(B1_WINDOW_HOURS),
            "points_per_decade": B1_POINTS_PER_DECADE,
            "permeability_thickness_md_ft": kh,
            "permeability_thickness_relative_error": abs(kh - true_kh) / true_kh,
            "skin": fit.skin,
            "skin_absolute_error": abs(fit.skin - TRUTH["skin"]),
            "basis": "EX POST SCORING AGAINST SYNTHETIC TRUTH -- not an analyst-available result",
        },
        "frozen_selector": selector,
        "series": series_payload(record, c_d=B2_0_CD),
        "c7_derivative": bourdet_against_model(record, interp, c_d=B2_0_CD),
    }


def experiment_b2_1() -> dict[str, Any]:
    """B2.1 -- constant storage, noise free, C_D = 1000 over 48 hours. The primary case.

    Criterion C4 is scored here and nowhere else. The three ways of scoring a window in
    protocol section 14 are kept apart: detection, localisation and parameter consequence.
    """
    record = cached_record(
        c_d=PRIMARY_CD, skin=TRUTH["skin"], hours=(FIRST_HOUR, LAST_HOUR), per_decade=POINTS_PER_DECADE
    )
    interp = analyst_interpretation(record)
    result = case_result(record)

    # Localisation: where the generator's own semilog departure is inside the C5 target.
    # Truth, used for scoring only, and computed after the selector has already answered.
    model = WellboreStorageModel(storage_dimensionless=PRIMARY_CD, skin=TRUTH["skin"])
    per_hour = t_d_per_hour()
    inside: list[float] = []
    for hours in record.times_hours:
        t_d = hours * per_hour
        p = model.pressure(t_d)
        departure = abs(p - 0.5 * (math.log(t_d) + LINE_SOURCE_CONSTANT) - TRUTH["skin"]) / p
        if departure <= C5_KH_RELATIVE:
            inside.append(hours)

    # L sensitivity, pre-registered in section 8 and reported separately.
    sensitivity = []
    for smoothing in L_SENSITIVITY:
        alt = analyst_interpretation(record, smoothing_l=smoothing)
        sensitivity.append({"smoothing_l": smoothing, **interpretation_payload(alt)})

    return {
        "storage_dimensionless": PRIMARY_CD,
        "storage_bbl_per_psi": storage_bbl_per_psi(PRIMARY_CD),
        "record_hours": [FIRST_HOUR, LAST_HOUR],
        "points_per_decade": POINTS_PER_DECADE,
        "crossover_hours": crossover_hours(PRIMARY_CD),
        **result,
        "localisation": {
            "basis": "EX POST SCORING AGAINST SYNTHETIC TRUTH -- not an analyst-available result",
            "generator_departure_within_c5_from_hours": min(inside) if inside else None,
            "generator_departure_within_c5_to_hours": max(inside) if inside else None,
            "generator_departure_decades": (math.log10(max(inside) / min(inside)) if inside else 0.0),
        },
        "l_sensitivity": sensitivity,
        "series": series_payload(record, c_d=PRIMARY_CD),
        "c7_derivative": bourdet_against_model(record, interp, c_d=PRIMARY_CD),
    }


def experiment_b2_2() -> dict[str, Any]:
    """B2.2 -- storage-strength sweep over the four pre-registered levels."""
    rows = []
    for c_d in STORAGE_LEVELS_CD:
        record = cached_record(
            c_d=c_d, skin=TRUTH["skin"], hours=(FIRST_HOUR, LAST_HOUR), per_decade=POINTS_PER_DECADE
        )
        rows.append(
            {
                "storage_dimensionless": c_d,
                "storage_bbl_per_psi": storage_bbl_per_psi(c_d),
                "crossover_hours": crossover_hours(c_d),
                **case_result(record),
                "series": series_payload(record, c_d=c_d),
            }
        )
    found = [r for r in rows if r["analyst"]["window_found"]]
    return {
        "levels": rows,
        "levels_with_a_certified_window": [r["storage_dimensionless"] for r in found],
        "levels_inconclusive": [r["storage_dimensionless"] for r in rows if not r["analyst"]["window_found"]],
    }


def experiment_b2_3() -> dict[str, Any]:
    """B2.3 -- test-duration sweep at C_D = 3000, the record truncated at five lengths."""
    full = cached_record(
        c_d=DURATION_SWEEP_CD, skin=TRUTH["skin"], hours=(FIRST_HOUR, LAST_HOUR), per_decade=POINTS_PER_DECADE
    )
    rows = []
    for hours in DURATION_HOURS:
        rows.append({"duration_hours": hours, **case_result(truncated(full, hours))})
    return {
        "storage_dimensionless": DURATION_SWEEP_CD,
        "crossover_hours": crossover_hours(DURATION_SWEEP_CD),
        "durations": rows,
        "durations_with_a_certified_window": [
            r["duration_hours"] for r in rows if r["analyst"]["window_found"]
        ],
    }


def experiment_b2_4() -> dict[str, Any]:
    """B2.4 -- sampling density at C_D = 1000, four pre-registered point counts per decade."""
    rows = []
    for per_decade in SAMPLING_PER_DECADE:
        record = cached_record(
            c_d=PRIMARY_CD, skin=TRUTH["skin"], hours=(FIRST_HOUR, LAST_HOUR), per_decade=per_decade
        )
        rows.append({"points_per_decade": per_decade, **case_result(record)})
    return {
        "storage_dimensionless": PRIMARY_CD,
        "sampling": rows,
        "densities_with_a_certified_window": [
            r["points_per_decade"] for r in rows if r["analyst"]["window_found"]
        ],
    }


def experiment_b2_5() -> dict[str, Any]:
    """B2.5 -- additive Gaussian pressure noise, four sigmas, 200 fixed seeds each.

    Noise is added to the one noise-free B2.1 record, which is what the protocol specifies:
    the same physics, seen through a worse gauge. **The fraction of seeds returning
    INCONCLUSIVE is a primary reported output, not a failure.** Recovery error is reported
    over the seeds that did return an answer, with that fraction stated beside it.
    """
    clean = cached_record(
        c_d=PRIMARY_CD, skin=TRUTH["skin"], hours=(FIRST_HOUR, LAST_HOUR), per_decade=POINTS_PER_DECADE
    )
    true_kh = TRUTH["permeability_md"] * TRUTH["thickness_ft"]
    rows = []
    for sigma in NOISE_SIGMAS_PSI:
        inconclusive = 0
        kh_errors: list[float] = []
        skin_errors: list[float] = []
        answered_seeds: list[int] = []
        for replicate in range(NOISE_REPLICATES):
            seed = NOISE_SEED_BASE + replicate
            rng = random.Random(seed)
            noisy = Record(
                clean.times_hours,
                tuple(p + rng.gauss(0.0, sigma) for p in clean.drawdown_psi),
            )
            interp = analyst_interpretation(noisy)
            if not interp.found_window:
                inconclusive += 1
                continue
            answered_seeds.append(seed)
            kh_errors.append(abs(interp.permeability_thickness_md_ft - true_kh) / true_kh)
            skin_errors.append(abs(interp.skin - TRUTH["skin"]))
        rows.append(
            {
                "sigma_psi": sigma,
                "replicates": NOISE_REPLICATES,
                "inconclusive": inconclusive,
                "inconclusive_fraction": inconclusive / NOISE_REPLICATES,
                "answered": len(kh_errors),
                "answered_seeds": answered_seeds,
                "ex_post_scoring": {
                    "basis": "EX POST SCORING AGAINST SYNTHETIC TRUTH -- not an analyst-available result",
                    "kh_relative_error_median": statistics.median(kh_errors) if kh_errors else None,
                    "kh_relative_error_max": max(kh_errors) if kh_errors else None,
                    "skin_absolute_error_median": statistics.median(skin_errors) if skin_errors else None,
                    "skin_absolute_error_max": max(skin_errors) if skin_errors else None,
                },
            }
        )
    return {
        "storage_dimensionless": PRIMARY_CD,
        "seed_base": NOISE_SEED_BASE,
        "noise_model": "additive independent zero-mean Gaussian on pressure only -- a controlled "
        "synthetic assumption, not a field error model",
        "levels": rows,
    }


def experiment_b2_6() -> dict[str, Any]:
    """B2.6 -- the deliberately inconclusive case. C_D = 10000 truncated at 3 hours.

    Expected INCONCLUSIVE, and criterion C10 requires that no permeability and no skin be
    reported. Usable radial extent against a crossover of 2.9 h is 0.0147 log cycles against
    a required 1.0, so a rule that answered here would be answering from nothing.
    """
    full = cached_record(
        c_d=INCONCLUSIVE_CD, skin=TRUTH["skin"], hours=(FIRST_HOUR, LAST_HOUR), per_decade=POINTS_PER_DECADE
    )
    record = truncated(full, INCONCLUSIVE_HOURS)
    result = case_result(record)
    return {
        "storage_dimensionless": INCONCLUSIVE_CD,
        "duration_hours": INCONCLUSIVE_HOURS,
        "crossover_hours": crossover_hours(INCONCLUSIVE_CD),
        **result,
        "series": series_payload(record, c_d=INCONCLUSIVE_CD),
        "c10_met": not result["analyst"]["window_found"],
        "c10_reports_no_parameters": "permeability_thickness_md_ft" not in result["analyst"]
        and "skin" not in result["analyst"],
    }


# =================================================================================
# POST-HOC EXPLORATORY ANALYSIS -- kept out of the classification
# =================================================================================
# None of this was pre-registered. It exists because the pre-registered result raised the
# question, and it is reported in its own namespace so that it cannot reach a criterion.
# It is a property of this synthetic model at these declared properties. It is not a
# field test-design recommendation and nothing here should be read as one.
POSTHOC_HORIZON_CAP_HOURS = 20000.0
POSTHOC_CADENCES = (10, 20, 50)
POSTHOC_LABEL = "POST-HOC EXPLORATORY ANALYSIS -- not pre-registered, and not part of the classification"


def _first_certifying_duration(record: Record, *, smoothing_l: float = SMOOTHING_L) -> dict[str, Any]:
    """Scan a long record for the earliest truncation the frozen selector certifies.

    The candidate durations are the record's own sample times, so the answer is resolved to
    the sampling interval and no finer. At 20 points per decade that interval is a factor of
    ``10**(1/20)``, about 12 percent in time, and the result is reported to that resolution
    rather than to the digits the float happens to carry.
    """
    times = record.times_hours
    verdicts = [
        analyst_interpretation(truncated(record, t), smoothing_l=smoothing_l).found_window for t in times
    ]
    first = next((i for i, v in enumerate(verdicts) if v), None)
    if first is None:
        return {"certified": False, "searched_to_hours": times[-1]}
    monotone = all(verdicts[first:])
    return {
        "certified": True,
        "first_certifying_hours": times[first],
        "last_declining_hours": times[first - 1] if first else None,
        "monotone_after_crossing": monotone,
        "resolution_factor": 10.0 ** (1.0 / POINTS_PER_DECADE),
        "rerun_at_crossing_found": analyst_interpretation(
            truncated(record, times[first]), smoothing_l=smoothing_l
        ).found_window,
        "rerun_below_crossing_found": (
            analyst_interpretation(truncated(record, times[first - 1]), smoothing_l=smoothing_l).found_window
            if first
            else None
        ),
    }


def _analytic_flatness_time(c_d: float) -> dict[str, Any]:
    """Two independent estimates of when the model's derivative becomes flat enough.

    Neither touches the Bourdet chain or the selector. They exist to check the bracket
    result by different routes, as the governing instruction requires, not to replace it.

    **Closed form.** Expanding the transform for small ``u`` gives
    ``p_wD ~ p_wD,no-storage - L^-1{C_D g^2}``, whose late-time behaviour is algebraic:

        D - 1/2  ~  C_D p_wD / t_D

    so the derivative approaches the half plateau from above like ``1/t_D``, not
    exponentially. Differentiating, the log-log slope is ``m ~ -2 C_D p_wD / t_D``, and the
    flatness condition ``|m| <= eps`` is first met around ``t_D ~ 2 C_D p_wD / eps``. That is
    a fixed point in ``t_D`` and converges in a handful of evaluations.

    **Numerical bisection** on the model's own log-log slope. Eighteen bisections of a
    nine-decade bracket leave about ``9/2**18`` decades, near one part in ten thousand -- more
    than the three figures this quantity is reported to, and far cheaper than the forty-five
    iterations an earlier version spent buying digits nothing consumed.

    The two agree to within about eight percent across the tested levels, the closed form
    running high because it takes ``D = 1/2`` in the denominator. Both are reported.
    """
    model = WellboreStorageModel(storage_dimensionless=c_d, skin=TRUTH["skin"])
    epsilon = WindowSettings().flatness
    per_hour = t_d_per_hour()

    t_closed = 1e5
    for _ in range(8):
        t_closed = 2.0 * c_d * model.pressure(t_closed) / epsilon

    def slope(t_d: float) -> float:
        h = 1e-3
        a = math.log(model.log_derivative(t_d * (1 - h)))
        b = math.log(model.log_derivative(t_d * (1 + h)))
        return (b - a) / (math.log(t_d * (1 + h)) - math.log(t_d * (1 - h)))

    lo, hi = 1e2, 1e11
    for _ in range(18):
        mid = math.sqrt(lo * hi)
        if abs(slope(mid)) > epsilon:
            lo = mid
        else:
            hi = mid
    t_bisect = math.sqrt(lo * hi)

    return {
        "flatness_epsilon": epsilon,
        "closed_form_flat_from_hours": t_closed / per_hour,
        "bisection_flat_from_hours": t_bisect / per_hour,
        "closed_form_over_bisection": t_closed / t_bisect,
        "one_decade_later_hours": 10.0 * t_bisect / per_hour,
        "note": "the record must run about one decade beyond the flat-onset time for the "
        "frozen rule's minimum extent to fit inside it. These are generator-side estimates "
        "and neither is available to the analyst.",
    }


def posthoc_time_to_certification() -> dict[str, Any]:
    """Return, for each storage level, the earliest record the frozen rule certifies.

    The search horizon is set per level at three times the generator-side one-decade estimate,
    which the closed form places on the high side, so the crossing is inside the searched
    range with room. A level whose crossing were not found would be reported as not certified
    within the horizon rather than silently omitted.

    **Cadence sensitivity is measured at the primary storage level only.** Repeating the
    50-points-per-decade scan at every level would multiply the numerical inversions that
    dominate this case's run time without adding a distinct question, and the bound is stated
    here rather than left for a reader to infer from an absent row. Smoothing sensitivity runs
    at every level, because it reuses records already generated and costs nothing.
    """
    rows = []
    for c_d in STORAGE_LEVELS_CD:
        analytic = _analytic_flatness_time(c_d)
        horizon = min(3.0 * analytic["one_decade_later_hours"], POSTHOC_HORIZON_CAP_HOURS)
        long_record = cached_record(
            c_d=c_d, skin=TRUTH["skin"], hours=(FIRST_HOUR, horizon), per_decade=POINTS_PER_DECADE
        )
        bracket = _first_certifying_duration(long_record)

        cadence: list[dict[str, Any]] = []
        if c_d == PRIMARY_CD:
            for per_decade in POSTHOC_CADENCES:
                alt = cached_record(
                    c_d=c_d, skin=TRUTH["skin"], hours=(FIRST_HOUR, horizon), per_decade=per_decade
                )
                found = _first_certifying_duration(alt)
                cadence.append(
                    {
                        "points_per_decade": per_decade,
                        "certified": found["certified"],
                        "first_certifying_hours": found.get("first_certifying_hours"),
                    }
                )

        smoothing = []
        for smoothing_l in L_SENSITIVITY:
            found = _first_certifying_duration(long_record, smoothing_l=smoothing_l)
            smoothing.append(
                {
                    "smoothing_l": smoothing_l,
                    "certified": found["certified"],
                    "first_certifying_hours": found.get("first_certifying_hours"),
                }
            )

        spread = [c["first_certifying_hours"] for c in cadence + smoothing if c["first_certifying_hours"]]
        rows.append(
            {
                "storage_dimensionless": c_d,
                "storage_bbl_per_psi": storage_bbl_per_psi(c_d),
                "crossover_hours": crossover_hours(c_d),
                "searched_to_hours": horizon,
                "frozen_selector": bracket,
                "independent_analytic_check": analytic,
                "cadence_sensitivity": cadence,
                "cadence_sensitivity_scope": "measured at the primary storage level only"
                if c_d != PRIMARY_CD
                else "measured",
                "smoothing_sensitivity": smoothing,
                "sensitivity_spread_factor": (max(spread) / min(spread)) if len(spread) > 1 else 1.0,
                "reported_days": _report_days(bracket.get("first_certifying_hours")),
            }
        )
    return {
        "label": POSTHOC_LABEL,
        "scope": "a property of this synthetic model at these declared properties, resolved to the "
        "sampling interval. Not a field test-design recommendation.",
        "levels": rows,
    }


def _report_days(hours: float | None) -> str | None:
    """Round a duration to what the evidence supports, and say so in words.

    The crossing is resolved to one sampling interval -- a factor of ``10**(1/20)``, about
    12 percent in time -- so two significant figures is already at the edge of what the
    measurement carries, and a figure like 11.823741 days would be false precision on a
    quantity known to roughly one part in eight.

    An earlier version rounded to the nearest five days, which turned 16.6 days into "15" and
    lost ten percent downward. Rounding coarsely is not the same as rounding honestly.
    """
    if hours is None:
        return None
    days = hours / 24.0
    if days < 1.0:
        return f"about {hours:.0f} hours"
    if days < 10.0:
        return f"about {days:.1f} days"
    magnitude = 10.0 ** (math.floor(math.log10(days)) - 1)
    return f"about {round(days / magnitude) * magnitude:.0f} days"


# =================================================================================
# CRITERIA AND CLASSIFICATION, protocol sections 13 and 15
# =================================================================================
def collect_criteria(results: dict[str, Any]) -> dict[str, Any]:
    """Apply the frozen criteria mechanically. No criterion is reinterpreted here."""
    inversion = results["numerical_qualification"]["inversion"]
    limits = results["numerical_qualification"]["limits"]
    b2_1 = results["b2_1_primary_noise_free"]
    b2_6 = results["b2_6_deliberately_inconclusive"]

    c4_found = b2_1["analyst"]["window_found"]
    c7 = b2_1["c7_derivative"]

    criteria: dict[str, Any] = {
        "C1_inversion_qualification": {"met": inversion["met"], "kind": "verification"},
        "C2a_storage_free_limit": {"met": limits["c2a_met"], "kind": "verification"},
        "C2b_b1_late_time_consistency": {"met": limits["c2b_met"], "kind": "verification"},
        "C3_storage_branch": {"met": limits["c3_met"], "kind": "verification"},
        "C3b_zero_skin_storage_regression": {"met": limits["c3b_met"], "kind": "verification"},
        "C4_window_detection_on_b2_1": {
            "met": c4_found,
            "kind": "diagnostic",
            "detail": b2_1["analyst"].get("reason", ""),
        },
        "C5_kh_recovery_on_b2_1": {
            "met": None
            if not c4_found
            else b2_1["ex_post_scoring"]["permeability_thickness_relative_error"] <= C5_KH_RELATIVE,
            "kind": "diagnostic",
            "detail": "NOT EVALUABLE -- C4 declined, so no window was selected to recover from"
            if not c4_found
            else "",
        },
        "C6_skin_recovery_on_b2_1": {
            "met": None
            if not c4_found
            else b2_1["ex_post_scoring"]["skin_absolute_error"] <= C6_SKIN_ABSOLUTE,
            "kind": "diagnostic",
            "detail": "NOT EVALUABLE -- C4 declined, so no window was selected to recover from"
            if not c4_found
            else "",
        },
        "C7_bourdet_against_model": {
            "met": c7.get("met") if c7["evaluable"] else None,
            "kind": "verification",
            "detail": c7.get("status", ""),
        },
        "C8_determinism": {"met": results["determinism"]["byte_identical"], "kind": "verification"},
        "C10_b2_6_inconclusive": {
            "met": b2_6["c10_met"] and b2_6["c10_reports_no_parameters"],
            "kind": "diagnostic",
        },
        "C11_no_window_inside_the_transition": {
            "met": True if not c4_found else b2_1["analyst"]["window_start_hours"] > b2_1["crossover_hours"],
            "kind": "diagnostic",
            "detail": "met vacuously -- no window was selected on B2.1, so none was selected "
            "inside the transition"
            if not c4_found
            else "",
        },
    }
    return criteria


VERIFICATION_CRITERIA = (
    "C1_inversion_qualification",
    "C2a_storage_free_limit",
    "C2b_b1_late_time_consistency",
    "C3_storage_branch",
    "C3b_zero_skin_storage_regression",
    "C7_bourdet_against_model",
    "C8_determinism",
)


def classify(criteria: dict[str, Any]) -> dict[str, Any]:
    """Apply protocol section 15 exactly as written.

    ESTABLISHED requires every criterion met. INVALID requires a *verification* criterion to
    have failed. A criterion that could not be evaluated has not failed, so it cannot produce
    INVALID; it can only withhold ESTABLISHED. The remaining outcome is INCONCLUSIVE, which
    section 15 defines as the diagnostic criteria not supporting a unique radial-flow
    interpretation -- with the report naming which condition.

    C9, portability, is measured outside this process by the repository's own comparison
    gate and is recorded there.
    """
    failed_verification = [k for k in VERIFICATION_CRITERIA if criteria[k]["met"] is False]
    failed_diagnostic = [k for k, v in criteria.items() if v["kind"] == "diagnostic" and v["met"] is False]
    not_evaluable = [k for k, v in criteria.items() if v["met"] is None]

    if failed_verification:
        outcome = "INVALID"
    elif not failed_diagnostic and not not_evaluable:
        outcome = "ESTABLISHED"
    else:
        outcome = "INCONCLUSIVE"
    return {
        "classification": outcome,
        "failed_verification_criteria": failed_verification,
        "failed_diagnostic_criteria": failed_diagnostic,
        "not_evaluable_criteria": not_evaluable,
        "rule": "protocol.md section 15, applied without reinterpretation",
    }


def determinism_check() -> dict[str, Any]:
    """C8. Generate and interpret the primary case a second time and compare exactly."""
    first = generate(
        c_d=PRIMARY_CD, skin=TRUTH["skin"], hours=(FIRST_HOUR, LAST_HOUR), per_decade=POINTS_PER_DECADE
    )
    second = generate(
        c_d=PRIMARY_CD, skin=TRUTH["skin"], hours=(FIRST_HOUR, LAST_HOUR), per_decade=POINTS_PER_DECADE
    )
    same_record = first.drawdown_psi == second.drawdown_psi and first.times_hours == second.times_hours
    a = interpretation_payload(analyst_interpretation(first))
    b = interpretation_payload(analyst_interpretation(second))
    return {
        "byte_identical": same_record and canonical_hash(a) == canonical_hash(b),
        "record_identical": same_record,
        "interpretation_digest": canonical_hash(a),
    }


LIMITATIONS = (
    "Synthetic throughout. No field data, no gauge, no real well.",
    "One model: homogeneous, isotropic, infinite-acting, single phase, constant rate, "
    "finite-radius inner boundary, constant storage, steady-state skin. Nothing here "
    "establishes behaviour outside it.",
    "Constant storage. Real storage changes during a test, and that is not represented.",
    "The independence is between derivation and implementation, not between this project and "
    "the world. The data come from a solution this project derived and implemented.",
    "The noise model is the forgiving one: independent, per-point, zero-mean, pressure only.",
    "Constant fluid properties. Despite the project's name this is not a gas-well result.",
    "The storage levels swept here are a synthetic parameter range chosen before results. No "
    "source inspected in this work establishes them as a typical field range, and the case "
    "makes no claim that they are.",
    "The one-log-cycle minimum extent is this project's certification criterion, fixed before "
    "results. It is not an industry-standard mandatory minimum and is not presented as one.",
)


def main(argv: list[str] | None = None) -> int:
    """Run case B2 into a fresh directory and write its summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="fresh run directory")
    args = parser.parse_args(argv)

    import mpmath
    import mpmath.libmp
    from wbs_model import INVERSION

    mp_version = mpmath.__version__
    mp_backend = mpmath.libmp.BACKEND

    config = {
        "truth": dict(TRUTH),
        "first_hour": FIRST_HOUR,
        "last_hour": LAST_HOUR,
        "points_per_decade": POINTS_PER_DECADE,
        "smoothing_l": SMOOTHING_L,
        "storage_levels_dimensionless": list(STORAGE_LEVELS_CD),
        "duration_hours": list(DURATION_HOURS),
        "sampling_per_decade": list(SAMPLING_PER_DECADE),
        "noise_sigmas_psi": list(NOISE_SIGMAS_PSI),
        "noise_replicates": NOISE_REPLICATES,
        "noise_seed_base": NOISE_SEED_BASE,
        "smoothing_sensitivity": list(L_SENSITIVITY),
        "window_rule": {
            "flatness_epsilon": WindowSettings().flatness,
            "storage_ratio": WindowSettings().storage_ratio,
            "min_decades": WindowSettings().min_decades,
            "min_points": WindowSettings().min_points,
            "status": "PROJECT-DEFINED CERTIFICATION CRITERION, fixed before any result existed",
        },
        "inversion": {
            # mpmath selects a gmpy backend when gmpy2 is installed, and that changes the
            # arithmetic underneath every Bessel evaluation in this case. Byte-identical
            # reproduction is a claim about the backend as much as about the version, so the
            # backend is recorded rather than assumed.
            "mpmath_version": mp_version,
            "mpmath_backend": mp_backend,
            "dps": INVERSION.dps,
            "dehoog_degree": INVERSION.dehoog_degree,
            "stehfest_degree": INVERSION.stehfest_degree,
            "primary": "de Hoog-Knight-Stokes",
            "cross_check": "Gaver-Stehfest, an algorithmic cross-check and not an independent physics oracle",
        },
        "protocol": {
            "path": "cases/B2_wellbore_storage_window/protocol.md",
            "commit": PROTOCOL_COMMIT,
            "blob_digest": blob_digest(PROTOCOL_PATH),
            "amendment": AMENDMENT,
            "amendment_blob_digest": blob_digest(AMENDMENT_PATH),
        },
        "thresholds": {
            "C1_known_inverse": C1_KNOWN_INVERSE,
            "C1_cross_check": C1_CROSS_CHECK,
            "C2a_storage_free": C2A_STORAGE_FREE,
            "C2b_b1_consistency": C2B_B1_CONSISTENCY,
            "C3_storage_branch": C3_STORAGE_BRANCH,
            "C5_kh_relative": C5_KH_RELATIVE,
            "C6_skin_absolute": C6_SKIN_ABSOLUTE,
            "C7_derivative_relative": C7_DERIVATIVE_RELATIVE,
        },
    }

    with RunRecord.open(
        args.out,
        label=CASE_ID,
        config=config,
        seed=NOISE_SEED_BASE,
        settings={
            "python_float": "IEEE 754 binary64",
            "dependencies": "mpmath for the case-layer forward model; reservoir_lab is standard library only",
            "protocol": "cases/B2_wellbore_storage_window/protocol.md",
        },
        repo_root=".",
    ) as record:
        results: dict[str, Any] = {
            "numerical_qualification": {
                "inversion": qualify_inversion(),
                "limits": qualify_limits(),
            },
            "determinism": determinism_check(),
            "b2_0_storage_free_regression": experiment_b2_0(),
            "b2_1_primary_noise_free": experiment_b2_1(),
            "b2_2_storage_sweep": experiment_b2_2(),
            "b2_3_duration_sweep": experiment_b2_3(),
            "b2_4_sampling": experiment_b2_4(),
            "b2_5_pressure_noise": experiment_b2_5(),
            "b2_6_deliberately_inconclusive": experiment_b2_6(),
        }
        criteria = collect_criteria(results)
        verdict = classify(criteria)
        payload: dict[str, Any] = {
            "case_id": CASE_ID,
            "case_type": "synthetic",
            "config": config,
            **results,
            "posthoc_exploratory": posthoc_time_to_certification(),
            "criteria": criteria,
            **verdict,
            "limitations": list(LIMITATIONS),
            "external_comparator": "NOT SELECTED -- see protocol section 16",
            "saphir_comparison": "NOT RUN",
            "field_validation": "NOT PERFORMED",
            "peer_review": "NOT PERFORMED",
        }
        payload["metrics_sha256"] = canonical_hash(results)
        record.write_json("summary.json", payload)
        record.metrics(
            classification=verdict["classification"],
            c4_window_found=results["b2_1_primary_noise_free"]["analyst"]["window_found"],
            storage_levels_certified=len(results["b2_2_storage_sweep"]["levels_with_a_certified_window"]),
        )

    print(f"B2 -- {CASE_ID}")
    print(f"  classification            {verdict['classification']}")
    found_window = criteria["C4_window_detection_on_b2_1"]["met"]
    print(f"  C4 window on B2.1         {'found' if found_window else 'NOT FOUND'}")
    if not criteria["C4_window_detection_on_b2_1"]["met"]:
        print(f"    reason                  {criteria['C4_window_detection_on_b2_1']['detail']}")
    print(f"  storage levels certified  {results['b2_2_storage_sweep']['levels_with_a_certified_window']}")
    print(f"  B2.6 declined as designed {results['b2_6_deliberately_inconclusive']['c10_met']}")
    for name, state in criteria.items():
        mark = {True: "met", False: "FAILED", None: "not evaluable"}[state["met"]]
        print(f"    {name:<40} {mark}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

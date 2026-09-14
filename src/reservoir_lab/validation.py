"""Input guards shared by every calculation module.

Why this exists as its own module
---------------------------------
A physics function whose first twenty lines are argument checks is hard to read and
hard to review, and the checks tend to drift apart between modules. Centralising them
means there is exactly one definition of "is this a usable pressure series", and a
reviewer can audit the guards independently of the physics.

Two deliberate behaviours worth stating plainly, because they are the opposite of what
a convenience library usually does:

* Nothing is silently repaired. A series that is out of chronological order raises;
  it is not sorted for you. Out-of-order timestamps in a production history usually
  mean two data sources were concatenated without alignment, and quietly sorting them
  destroys the evidence of that.
* Nothing is silently dropped. Non-finite values raise; they are not filtered out.
  Deciding which measurements to exclude is an engineering judgement that belongs in a
  documented cleaning log, not in a numerical helper.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Iterable, Mapping, Sequence

from .errors import InvalidInputError, OutOfRangeWarningError, RangeWarning

__all__ = [
    "as_float_sequence",
    "check_range",
    "require_finite",
    "require_in_interval",
    "require_min_length",
    "require_non_decreasing",
    "require_non_negative",
    "require_positive",
    "require_same_length",
    "require_strictly_increasing",
]


def require_finite(value: float, name: str) -> float:
    """Return ``value`` as a float, raising if it is NaN, infinite, or not numeric."""
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise InvalidInputError(f"{name} must be a real number, got {value!r}") from exc
    if not math.isfinite(out):
        raise InvalidInputError(f"{name} must be finite, got {out!r}")
    return out


def require_positive(value: float, name: str) -> float:
    """Return ``value`` as a finite float, raising unless it is strictly positive.

    Used for absolute pressures, absolute temperatures, volumes, permeabilities and
    thicknesses. A zero or negative absolute pressure is almost always a gauge value
    that was never converted, which is why the message says so.
    """
    out = require_finite(value, name)
    if out <= 0.0:
        raise InvalidInputError(
            f"{name} must be strictly positive, got {out!r}. If this is a pressure or a "
            f"temperature, check that it is on an absolute scale -- a gauge or Fahrenheit "
            f"value used where an absolute one is required is the usual cause."
        )
    return out


def require_non_negative(value: float, name: str) -> float:
    """Return ``value`` as a finite float, raising if it is negative."""
    out = require_finite(value, name)
    if out < 0.0:
        raise InvalidInputError(f"{name} must be non-negative, got {out!r}")
    return out


def require_in_interval(
    value: float,
    name: str,
    low: float,
    high: float,
    *,
    inclusive: bool = True,
) -> float:
    """Return ``value`` as a finite float, raising if it lies outside ``[low, high]``.

    This is a hard constraint, used for quantities that are meaningless outside the
    interval (a saturation outside 0..1, a mole fraction outside 0..1). For a
    correlation's *fitted* range, which one may legitimately exceed with eyes open,
    use :func:`check_range` instead.
    """
    out = require_finite(value, name)
    inside = (low <= out <= high) if inclusive else (low < out < high)
    if not inside:
        bounds = f"[{low}, {high}]" if inclusive else f"({low}, {high})"
        raise InvalidInputError(f"{name} must lie in {bounds}, got {out!r}")
    return out


def as_float_sequence(values: Iterable[float], name: str) -> tuple[float, ...]:
    """Materialise an iterable as a tuple of finite floats, in the caller's order.

    Returns a tuple rather than a list so that the result cannot be mutated by a caller
    after validation, which would defeat the point of validating. The order is the
    caller's order: this function does not sort.

    Several types are iterable but are never a numeric series, and accepting them is
    worse than rejecting them because the reinterpretation is silent and plausible:

    * a string ``"123"`` would become the three-point series ``(1.0, 2.0, 3.0)``, which
      is exactly what an unparsed CSV field looks like at the call site;
    * ``b"ab"`` would become ``(97.0, 98.0)`` from the byte values;
    * a mapping would iterate over its keys, silently discarding every value.

    Each of those produces a series of the wrong length or the wrong content while
    looking entirely ordinary downstream, so they raise here.
    """
    if isinstance(values, (str, bytes, bytearray)):
        raise InvalidInputError(
            f"{name} must be a sequence of numbers, not {type(values).__name__}. "
            f"Iterating a string or bytes object yields its characters or byte values, "
            f"so {values!r:.40} would silently become a numeric series of the wrong "
            f"length. Parse it into a list of floats first."
        )
    if isinstance(values, Mapping):
        raise InvalidInputError(
            f"{name} must be a sequence of numbers, not a {type(values).__name__}. "
            f"Iterating a mapping yields its keys and discards every value; pass "
            f"the values explicitly if that is what you meant."
        )
    try:
        items = list(values)
    except TypeError as exc:
        raise InvalidInputError(f"{name} must be iterable, got {type(values).__name__}") from exc
    out = []
    for index, item in enumerate(items):
        out.append(require_finite(item, f"{name}[{index}]"))
    return tuple(out)


def require_same_length(
    first: Sequence[object], second: Sequence[object], first_name: str, second_name: str
) -> None:
    """Raise unless the two sequences have equal length."""
    if len(first) != len(second):
        raise InvalidInputError(
            f"{first_name} and {second_name} must have the same length, got {len(first)} and {len(second)}"
        )


def require_min_length(values: Sequence[object], name: str, minimum: int, purpose: str) -> None:
    """Raise unless ``values`` has at least ``minimum`` entries.

    ``purpose`` is included in the message so the caller learns *why* that many points
    are needed ("a straight-line fit needs two distinct abscissae"), not merely that
    they are.
    """
    if len(values) < minimum:
        raise InvalidInputError(f"{name} needs at least {minimum} values for {purpose}, got {len(values)}")


def require_strictly_increasing(values: Sequence[float], name: str) -> None:
    """Raise unless the series strictly increases.

    Applied to time and to cumulative production. A repeated value is rejected as well
    as a decreasing one: two measurements sharing a timestamp cannot both be used in a
    log-time derivative, and the correct fix is a documented decision about which to
    keep, made upstream.
    """
    for index in range(1, len(values)):
        if values[index] <= values[index - 1]:
            kind = "repeats" if values[index] == values[index - 1] else "decreases"
            raise InvalidInputError(
                f"{name} must strictly increase, but {kind} at index {index}: "
                f"{name}[{index - 1}]={values[index - 1]!r}, {name}[{index}]={values[index]!r}. "
                f"This series is not reordered automatically -- out-of-order entries usually "
                f"indicate two sources merged without alignment, and that should be resolved "
                f"in a cleaning log rather than here."
            )


def require_non_decreasing(values: Sequence[float], name: str) -> None:
    """Raise unless the series never decreases.

    Cumulative production during a shut-in is flat, so a cumulative series is checked
    with this rather than with :func:`require_strictly_increasing`.
    """
    for index in range(1, len(values)):
        if values[index] < values[index - 1]:
            raise InvalidInputError(
                f"{name} must not decrease, but drops at index {index}: "
                f"{values[index - 1]!r} -> {values[index]!r}"
            )


def check_range(
    value: float,
    name: str,
    low: float,
    high: float,
    *,
    correlation: str,
    strict: bool = False,
) -> float:
    """Check a value against a correlation's published validity window.

    Unlike :func:`require_in_interval` this is a soft check by default. Evaluating a
    correlation outside its fitted range is sometimes exactly what a sensitivity study
    wants to do; what is unacceptable is doing it without knowing. So the default
    emits a :class:`~reservoir_lab.errors.RangeWarning` naming the correlation and the
    window, and ``strict=True`` turns it into an
    :class:`~reservoir_lab.errors.OutOfRangeWarningError`.

    Parameters
    ----------
    correlation:
        Name of the correlation, quoted in the warning so the reader can look up the
        window in the derivation notes.
    strict:
        Raise instead of warn.
    """
    out = require_finite(value, name)
    if low <= out <= high:
        return out
    message = (
        f"{correlation}: {name}={out!r} is outside the published validity range "
        f"[{low}, {high}]. The returned value is an extrapolation and its accuracy is "
        f"not characterised by the source."
    )
    if strict:
        raise OutOfRangeWarningError(message)
    warnings.warn(message, RangeWarning, stacklevel=3)
    return out

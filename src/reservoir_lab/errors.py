"""Exception types.

The package raises narrow, named exceptions rather than bare :class:`ValueError`, so
that a caller can distinguish "you handed me something physically impossible" from
"the iteration did not converge" from "you are asking this correlation to work outside
the window it was fitted in". Those three cases call for different responses and a
study that silently swallows the third one is producing numbers it cannot defend.

All of them derive from :class:`ReservoirLabError`, so ``except ReservoirLabError``
catches everything this package raises deliberately.
"""

from __future__ import annotations


class ReservoirLabError(Exception):
    """Base class for every error raised deliberately by this package."""


class InvalidInputError(ReservoirLabError, ValueError):
    """An argument is missing, malformed, non-finite, or physically impossible.

    Also inherits from :class:`ValueError` so that existing ``except ValueError``
    handlers keep working.
    """


class ConvergenceError(ReservoirLabError, RuntimeError):
    """An iterative solver did not reach its tolerance within the iteration budget.

    Carries the diagnostic state so the caller can report what actually happened
    instead of a bare failure.
    """

    def __init__(
        self,
        message: str,
        *,
        iterations: int | None = None,
        last_value: float | None = None,
        last_residual: float | None = None,
    ) -> None:
        super().__init__(message)
        self.iterations = iterations
        self.last_value = last_value
        self.last_residual = last_residual

    def __str__(self) -> str:
        """Render the message together with the diagnostic state carried on the error."""
        base = super().__str__()
        parts = []
        if self.iterations is not None:
            parts.append(f"iterations={self.iterations}")
        if self.last_value is not None:
            parts.append(f"last_value={self.last_value!r}")
        if self.last_residual is not None:
            parts.append(f"last_residual={self.last_residual!r}")
        return f"{base} ({', '.join(parts)})" if parts else base


class OutOfRangeWarningError(ReservoirLabError):
    """A correlation was asked to evaluate outside its published validity window.

    Raised only when the caller has opted into strict range checking. The default
    behaviour is to emit a :class:`RangeWarning` instead, because a study frequently
    *wants* to see what a correlation does outside its window -- as long as the
    excursion is recorded rather than hidden.
    """


class RangeWarning(UserWarning):
    """Warning category for evaluation outside a published correlation range."""


class NotIdentifiableError(ReservoirLabError):
    """The requested quantity is not identifiable from the data supplied.

    Examples: fitting a straight line through a single point; extracting an
    x-intercept from a regression whose fitted slope is not significantly different
    from zero; recovering two parameters that enter the model only through their
    product. Returning a number in these cases would be worse than failing, because
    the number would look like an estimate.
    """

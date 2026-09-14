"""The two runners must agree about what counts as a failure.

`pyproject.toml` declares `[tool.pytest.ini_options] filterwarnings`, and pytest is the
only runner that reads that file. Before this module existed, `scripts/check.py` ran the
same test files without the policy, so a test that evaluated a correlation outside its
published validity window emitted a `RangeWarning`, passed under `check.py`, and failed
under pytest. A reviewer running the stdlib runner -- the one the README offers to
people who do not want to install anything -- was told the suite was green when it was
not.

The tests here are a regression probe on that wiring. They are written so that they run
identically under both runners:

* `RangeWarningIsFatalTests` probes the *ambient* policy, whichever runner installed it.
  It goes red under `check.py` if `check.py` stops applying the policy, and red under
  both runners if the declaration is deleted from `pyproject.toml`.
* `StdlibRunnerPolicyTests` probes `scripts/check.py` directly, with deliberately
  hostile ambient filters, so it goes red even when it is pytest doing the running.
* `PolicyScopeTests` pins the decision that the policy is scoped to `RangeWarning` and
  does not promote every warning category. If someone widens it, that is a decision to
  make in `pyproject.toml` on purpose, and this test is where they will be reminded.
"""

from __future__ import annotations

import importlib
import io
import unittest
import warnings

from reservoir_lab.errors import RangeWarning
from reservoir_lab.gas_properties import STANDING_GRAVITY_RANGE, pseudocritical_standing

check = importlib.import_module("check")


class RangeWarningIsFatalTests(unittest.TestCase):
    """The policy the current runner installed must make RangeWarning fatal."""

    def test_a_bare_range_warning_is_raised(self):
        with self.assertRaises(RangeWarning):
            warnings.warn("runner policy probe", RangeWarning, stacklevel=1)

    def test_a_correlation_evaluated_outside_its_window_raises(self):
        # Standing's pseudocritical correlation is published for gas gravity in
        # STANDING_GRAVITY_RANGE. Asking for a gravity above the top of that window is
        # an extrapolation, the library says so with a RangeWarning, and under the
        # declared policy a test that does it without opting in is a failing test.
        outside = STANDING_GRAVITY_RANGE[1] + 1.0
        with self.assertRaises(RangeWarning):
            pseudocritical_standing(outside)

    def test_the_declared_policy_is_present_in_the_active_filters(self):
        specs = check.read_warning_policy()
        self.assertTrue(specs, "pyproject.toml declares no filterwarnings entries")
        active = [(entry[0], entry[2]) for entry in warnings.filters]
        for spec in specs:
            fields = spec.split(":")
            action = fields[0]
            category_name = fields[2] if len(fields) > 2 else ""
            category = check.resolve_warning_category(category_name) if category_name else Warning
            self.assertIn(
                (action, category),
                active,
                f"declared filter {spec!r} is not installed in the runner that is executing "
                f"this test, so the two runners do not agree about what fails",
            )


class StdlibRunnerPolicyTests(unittest.TestCase):
    """`scripts/check.py` must install the policy itself, not inherit it by luck."""

    @staticmethod
    def _run_probe_under_check_runner() -> unittest.TestResult:
        class Probe(unittest.TestCase):
            def test_emits_a_range_warning(self):
                warnings.warn("stdlib runner probe", RangeWarning, stacklevel=1)

        suite = unittest.TestLoader().loadTestsFromTestCase(Probe)
        specs = check.read_warning_policy()
        # Reaching into a private name on purpose: this test is a probe on check.py's
        # internal wiring, and it should break if that wiring is renamed or deleted.
        result_class = check._policy_result_class(specs)
        with warnings.catch_warnings():
            # Hostile ambient state: everything silenced, nothing promoted. If the
            # policy survives this, check.py is installing it rather than inheriting
            # whatever the outer runner happened to leave behind.
            warnings.resetwarnings()
            warnings.simplefilter("ignore")
            runner = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0, resultclass=result_class)
            return runner.run(suite)

    def test_the_check_runner_turns_a_range_warning_into_a_test_error(self):
        result = self._run_probe_under_check_runner()
        self.assertEqual(
            len(result.errors) + len(result.failures),
            1,
            "scripts/check.py ran a test that emitted a RangeWarning and did not fail it. "
            "That is the exact gap this module exists to close: the same test fails under "
            "pytest, so the stdlib runner would be reporting a green suite that is not green.",
        )

    def test_the_declared_policy_is_read_from_pyproject_rather_than_restated(self):
        specs = check.read_warning_policy()
        self.assertTrue(specs)
        self.assertTrue(
            any("RangeWarning" in spec and spec.startswith("error") for spec in specs),
            f"pyproject.toml no longer promotes RangeWarning to an error: {specs!r}",
        )

    def test_a_missing_pyproject_is_an_error_rather_than_a_silent_empty_policy(self):
        with self.assertRaises(check.WarningPolicyError):
            check.read_warning_policy(check.REPO_ROOT / "no_such_pyproject.toml")


class PolicyScopeTests(unittest.TestCase):
    """The policy is scoped to RangeWarning on purpose."""

    def test_an_unrelated_user_warning_is_not_promoted(self):
        # RangeWarning subclasses UserWarning, so it is worth stating that the reverse
        # does not hold: a plain UserWarning from a dependency or from the standard
        # library is still a warning. Promoting every category would make the suite
        # fail on things the code under test is not responsible for, and the usual
        # response to that is a blanket ignore, which is worse than no policy at all.
        with warnings.catch_warnings(record=True) as seen:
            try:
                warnings.warn("unrelated user warning probe", UserWarning, stacklevel=1)
            except UserWarning:  # pragma: no cover - only reachable if the policy widened
                self.fail(
                    "the warning policy now promotes plain UserWarning to an error. If that "
                    "is intended, change it in pyproject.toml and update this test; if it is "
                    "not, the filterwarnings entry is broader than it looks."
                )
        self.assertEqual([type(item.message) for item in seen], [UserWarning])

    def test_range_warning_is_a_user_warning_subclass(self):
        # The scoping above is only meaningful because of this relationship.
        self.assertTrue(issubclass(RangeWarning, UserWarning))


if __name__ == "__main__":
    unittest.main()

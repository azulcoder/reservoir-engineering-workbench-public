#!/usr/bin/env python3
"""Run the whole verification suite with the standard library only.

There is a deliberate reason this exists alongside pytest. The numerical core imports
nothing outside the standard library, and a reviewer should be able to check its
arithmetic with a stock Python interpreter and no environment to reproduce. If the only
way to run the tests were `pip install pytest`, that property would be decorative.

The tests are written as `unittest.TestCase` classes, so the same files run unchanged
under pytest when the development extra is installed. Neither runner is privileged.

Warning policy
--------------
`pyproject.toml` sets `[tool.pytest.ini_options] filterwarnings`, and pytest is the only
runner that reads it. That made this script the weaker of the two gates: a test that
evaluated a correlation outside its published validity window emitted a `RangeWarning`,
passed here, and failed under pytest. Two runners that disagree about what counts as a
failure are worse than one runner, because whichever one you happen to run tells you the
suite is green.

So this script now reads the same `filterwarnings` list out of `pyproject.toml` and
installs it before collection, and reinstalls it around every individual test the way
pytest does. The list is the single source of truth; nothing about the policy is
restated here. Today that list promotes exactly one category, `RangeWarning`, and no
other category is touched -- an unrelated `DeprecationWarning` from the standard library
is still a warning under both runners. Widening the policy is a decision to take in
`pyproject.toml`, where both runners will see it.

`tests/test_runner_policy.py` fails if this wiring is removed.

Usage
-----
    python3 scripts/check.py                # tests + repository hygiene
    python3 scripts/check.py --tests-only
    python3 scripts/check.py --pattern "test_gas*.py"
    python3 scripts/check.py -v
"""

from __future__ import annotations

import argparse
import importlib
import pathlib
import sys
import time
import tomllib
import unittest
import warnings

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
TESTS = REPO_ROOT / "tests"
PYPROJECT = REPO_ROOT / "pyproject.toml"


class WarningPolicyError(RuntimeError):
    """The declared warning policy could not be read or could not be applied."""


def _ensure_import_paths() -> None:
    """Put the src layout, the repository root and scripts/ on ``sys.path``."""
    for entry in (str(SRC), str(REPO_ROOT), str(REPO_ROOT / "scripts")):
        if entry not in sys.path:
            sys.path.insert(0, entry)


def read_warning_policy(pyproject: pathlib.Path = PYPROJECT) -> tuple[str, ...]:
    """Return the ``filterwarnings`` specs declared for pytest in ``pyproject.toml``.

    Returning them rather than restating them is the point: the two runners cannot
    drift apart if only one file declares the policy.
    """
    if not pyproject.is_file():
        raise WarningPolicyError(
            f"{pyproject} not found, so the declared warning policy cannot be read. "
            f"Running the suite without it would make this runner weaker than pytest."
        )
    try:
        with pyproject.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise WarningPolicyError(f"{pyproject} could not be parsed: {exc}") from exc

    specs = data.get("tool", {}).get("pytest", {}).get("ini_options", {}).get("filterwarnings", [])
    if isinstance(specs, str):
        specs = [specs]
    if not isinstance(specs, list) or not all(isinstance(item, str) for item in specs):
        raise WarningPolicyError(
            f"[tool.pytest.ini_options] filterwarnings must be a list of strings, got {specs!r}"
        )
    return tuple(specs)


def resolve_warning_category(dotted: str) -> type[Warning]:
    """Import a warning category named the way a ``-W`` specification names it."""
    module_name, _, attribute = dotted.rpartition(".")
    module_name = module_name or "builtins"
    try:
        category = getattr(importlib.import_module(module_name), attribute)
    except (ImportError, AttributeError) as exc:
        raise WarningPolicyError(f"warning category {dotted!r} could not be imported: {exc}") from exc
    if not (isinstance(category, type) and issubclass(category, Warning)):
        raise WarningPolicyError(f"warning category {dotted!r} is not a Warning subclass")
    return category


def apply_warning_policy(specs: tuple[str, ...]) -> None:
    """Install ``specs`` at the front of ``warnings.filters``.

    The specification grammar is the one pytest and ``python -W`` share,
    ``action:message:category:module:lineno``, with every field after the action
    optional. Empty fields mean "match anything", exactly as they do for ``-W``.
    """
    for spec in reversed(specs):
        fields = spec.split(":")
        if len(fields) > 5:
            raise WarningPolicyError(f"filterwarnings entry {spec!r} has more than five fields")
        fields += [""] * (5 - len(fields))
        action, message, category_name, module, lineno_text = fields
        if action not in ("default", "error", "ignore", "always", "module", "once"):
            raise WarningPolicyError(f"filterwarnings entry {spec!r} has unknown action {action!r}")
        try:
            lineno = int(lineno_text) if lineno_text else 0
        except ValueError as exc:
            raise WarningPolicyError(f"filterwarnings entry {spec!r} has a bad line number") from exc
        category = resolve_warning_category(category_name) if category_name else Warning
        warnings.filterwarnings(
            action,  # type: ignore[arg-type]
            message=message,
            category=category,
            module=module,
            lineno=lineno,
        )


def _policy_result_class(specs: tuple[str, ...]) -> type[unittest.TextTestResult]:
    """Build a result class that re-arms the warning policy around every test.

    pytest evaluates its ``filterwarnings`` list inside a fresh ``catch_warnings``
    block for each test item. Doing the same here means one test cannot leak a filter
    into the next, and means the policy survives whatever a runner does to
    ``warnings.filters`` between the call to :func:`apply_warning_policy` and the test
    body. Without this, the policy holds only by accident of the running interpreter's
    ``unittest`` internals.
    """

    class PolicyTextTestResult(unittest.TextTestResult):
        """Text result that applies the declared warning policy per test."""

        def startTest(self, test):  # noqa: N802 - unittest's own spelling
            """Enter a per-test warning context and install the declared policy."""
            self._warning_context = warnings.catch_warnings()
            self._warning_context.__enter__()
            apply_warning_policy(specs)
            super().startTest(test)

        def stopTest(self, test):  # noqa: N802 - unittest's own spelling
            """Leave the per-test warning context, restoring the previous filters."""
            super().stopTest(test)
            context = getattr(self, "_warning_context", None)
            if context is not None:
                context.__exit__(None, None, None)
                self._warning_context = None

    return PolicyTextTestResult


def run_tests(
    pattern: str,
    verbosity: int,
    specs: tuple[str, ...] | None = None,
) -> tuple[bool, unittest.TestResult]:
    """Discover and run the suite under the declared warning policy."""
    _ensure_import_paths()
    if specs is None:
        specs = read_warning_policy()
    # Collection imports every test module, and an import can warn. Arm the policy
    # before discovery so those warnings are judged by the same rules as the tests.
    apply_warning_policy(specs)

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(TESTS), pattern=pattern, top_level_dir=str(TESTS))
    if loader.errors:
        for error in loader.errors:
            print(error, file=sys.stderr)
        return False, unittest.TestResult()
    runner = unittest.TextTestRunner(
        verbosity=verbosity,
        stream=sys.stdout,
        buffer=False,
        resultclass=_policy_result_class(specs),
    )
    result = runner.run(suite)
    return result.wasSuccessful(), result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--pattern", default="test_*.py", help="test file glob")
    parser.add_argument("--tests-only", action="store_true", help="skip the repository hygiene check")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    args = parser.parse_args(argv)

    print(f"python {sys.version.split()[0]} on {sys.platform}")
    print(f"repository {REPO_ROOT}")
    try:
        specs = read_warning_policy()
    except WarningPolicyError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    if specs:
        print("warning policy (from pyproject.toml, shared with pytest):")
        for spec in specs:
            print(f"  {spec}")
    else:
        print(
            "warning policy: pyproject.toml declares no filterwarnings entries, so this "
            "runner promotes nothing. pytest promotes nothing either."
        )
    print("-" * 72)

    started = time.monotonic()
    try:
        ok, result = run_tests(args.pattern, verbosity=2 if args.verbose else 1, specs=specs)
    except WarningPolicyError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    elapsed = time.monotonic() - started

    print("-" * 72)
    print(
        f"tests: {result.testsRun} run, {len(result.failures)} failed, "
        f"{len(result.errors)} errored, {len(result.skipped)} skipped, {elapsed:.2f}s"
    )

    if result.testsRun == 0:
        print(
            "no tests were collected. An empty suite is a failure, not a pass: it means "
            "discovery is misconfigured or the tests were not written."
        )
        ok = False

    hygiene_ok = True
    if not args.tests_only:
        print("-" * 72)
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        import check_repository

        hygiene_ok = check_repository.main([]) == 0

    print("-" * 72)
    if ok and hygiene_ok:
        print("PASS")
        return 0
    print(
        "FAIL: "
        + ", ".join(part for part, bad in (("tests", not ok), ("repository hygiene", not hygiene_ok)) if bad)
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

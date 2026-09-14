#!/usr/bin/env python3
"""Decide whether the browser suite's skips are permitted, evidenced and consistent.

A skipped test is a check that was not made. This script is the one place that decides
whether that is acceptable, and it is called by the local release path and by both
workflows so that a deployment build is held to exactly the standard a pull request is.
The two workflows previously each carried their own inline copy of this logic, matching
whole English sentences; rewording a message turned a declared skip into an undeclared
one in one copy and not the other.

What it matches on
------------------
A stable capability id, not prose. The skip reason has the shape

    NOT APPLICABLE [<capability-id>]: <a sentence for whoever reads the report>

and only the bracketed id is load-bearing. Anything else -- including a sentence that
merely begins "NOT APPLICABLE" -- is an undeclared skip and fails. The permitted ids,
the engines each is permitted on, and how each must be evidenced live in
`site/tests/skip-policy.json`.

Platform independence
---------------------
The policy names which engines MAY take a skip. It never requires one to happen. The
same suite takes 14 skips on macOS and may take a different number on Linux, because a
capability is a property of the engine build and the platform under it. Nothing here
compares a count against a baseline; a count is reported, and only a rule violation
fails.

What fails
----------
    no-report              the JSON report is missing or unreadable
    empty-suite            nothing executed
    engine-absent          an expected engine produced no result at all
    engine-unexecuted      an engine ran but every one of its tests skipped
    failure                a test failed, timed out or was interrupted
    skip-no-reason         skipped without recording why
    skip-unparseable       the reason is not in the declared grammar
    skip-unknown           the capability id is not in the policy
    skip-engine            that engine is not permitted to take that skip
    policy-all-engines     a capability permitted on every engine: a deleted check
    skip-missing-evidence  a probe-backed skip with no measurement attached
    skip-evidence-format   the measurement is attached but unreadable
    skip-self-contradicted the test's own measurement says the capability was available
    probe-absent           the independent probe did not run on that engine
    probe-contradicted     the independent probe measured the capability as available
    check-never-ran        a check skipped everywhere: removed, not skipped

Usage
-----
    python3 scripts/check_skip_policy.py --report site/test-results/report-4321.json
    python3 scripts/check_skip_policy.py --report <path> --engines chromium,firefox
    python3 scripts/check_skip_policy.py --report <path> --json out.json
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections.abc import Iterator
from typing import Any, NamedTuple

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_POLICY = REPO_ROOT / "site" / "tests" / "skip-policy.json"

FAILED_STATUSES = {"failed", "timedOut", "interrupted"}


class Problem(NamedTuple):
    """One rule violation, with the code the tests name it by."""

    code: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - formatting only
        """Render the finding as its code followed by its sentence."""
        return f"[{self.code}] {self.message}"


class Policy:
    """The declared capability policy, read once and queried by id."""

    def __init__(self, raw: dict[str, Any]) -> None:
        """Index the declared capabilities by id and compile the reason grammar."""
        self.raw = raw
        self.grammar = re.compile(raw["reason_grammar"])
        self.annotation_prefix: str = raw["annotation_prefix"]
        self.engines: list[str] = list(raw["engines"])
        self.by_id: dict[str, dict[str, Any]] = {}
        for entry in raw["capabilities"]:
            self.by_id[entry["id"]] = entry

    @classmethod
    def load(cls, path: pathlib.Path) -> Policy:
        """Read the policy from its JSON file."""
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def static_problems(self) -> list[Problem]:
        """Rules about the policy itself, independent of any run."""
        problems: list[Problem] = []
        universe = set(self.engines)
        for entry in self.raw["capabilities"]:
            permitted = set(entry["engines"])
            if permitted >= universe:
                problems.append(
                    Problem(
                        "policy-all-engines",
                        f"capability {entry['id']!r} is permitted on every engine. A check "
                        f"skipped everywhere is not skipped, it is removed. Delete the test "
                        f"or find an engine that can make the measurement.",
                    )
                )
            if entry["evidence"] not in {"probe", "engine"}:
                problems.append(
                    Problem(
                        "policy-all-engines",
                        f"capability {entry['id']!r} declares evidence "
                        f"{entry['evidence']!r}; only 'probe' and 'engine' are defined.",
                    )
                )
        return problems


class Case(NamedTuple):
    """One (engine, test) pair as the report records it."""

    engine: str
    title: str
    status: str
    annotations: tuple[tuple[str, str], ...]


def _annotations(test: dict[str, Any], result: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    """Every annotation on a test, from whichever of the two places carries them.

    Playwright assigns the worker's end payload to both `test.annotations` and
    `result.annotations`, so the two are normally the same list; taking the union means
    a reporter change on either side cannot make evidence vanish.
    """
    seen: dict[tuple[str, str], None] = {}
    for source in (test.get("annotations"), result.get("annotations")):
        for item in source or []:
            key = (str(item.get("type") or "").strip(), str(item.get("description") or "").strip())
            seen.setdefault(key, None)
    return tuple(seen)


def walk(suite: dict[str, Any]) -> Iterator[Case]:
    """Every executed (engine, test) pair in the report, at any nesting depth."""
    for spec in suite.get("specs", []):
        title = spec.get("title", "?")
        for test in spec.get("tests", []):
            engine = test.get("projectName", "?")
            for result in test.get("results", []):
                yield Case(
                    engine=engine,
                    title=title,
                    status=str(result.get("status") or "?"),
                    annotations=_annotations(test, result),
                )
    for child in suite.get("suites", []):
        yield from walk(child)


def skip_reasons(case: Case) -> list[str]:
    """Collect the reasons recorded against a skip, in order, empty strings dropped."""
    return [desc for kind, desc in case.annotations if kind == "skip" and desc]


def measured(case: Case, policy: Policy, capability_id: str) -> str | None:
    """Read a test's own attached measurement for a capability, if it carried one."""
    wanted = f"{policy.annotation_prefix}{capability_id}"
    for kind, desc in case.annotations:
        if kind == wanted:
            return desc
    return None


def verdict_of(description: str) -> bool | None:
    """Read `available`/`unavailable` off the front of a measurement annotation."""
    head = description.strip().lower()
    if head.startswith("unavailable"):
        return False
    if head.startswith("available"):
        return True
    return None


def evaluate(report: dict[str, Any], policy: Policy, expected_engines: list[str]) -> dict[str, Any]:
    """Apply every rule to one report and return the findings plus what was observed."""
    problems: list[Problem] = list(policy.static_problems())

    cases = [case for suite in report.get("suites", []) for case in walk(suite)]
    stats = report.get("stats", {})
    executed = sum(1 for c in cases if c.status != "skipped")

    if not cases or executed == 0:
        problems.append(
            Problem(
                "empty-suite",
                "no test executed. An empty suite that reports success is the one outcome "
                "this gate exists to prevent.",
            )
        )

    # Ordinary failures. The report's own counter is checked too, so a failure the walk
    # cannot see (a worker that died before writing a spec) still fails the gate.
    for case in cases:
        if case.status in FAILED_STATUSES:
            problems.append(Problem("failure", f"[{case.engine}] {case.title}: {case.status}."))
    unexpected = int(stats.get("unexpected") or 0)
    if unexpected and not any(p.code == "failure" for p in problems):
        problems.append(
            Problem(
                "failure",
                f"the report counts {unexpected} unexpected result(s) that no spec in the "
                f"tree accounts for. Read the run log rather than this summary.",
            )
        )

    # Per-engine execution. An engine that was asked for and produced nothing, or that
    # produced only skips, has not verified anything.
    seen_engines = {c.engine for c in cases}
    per_engine: dict[str, dict[str, int]] = {}
    for case in cases:
        bucket = per_engine.setdefault(case.engine, {"executed": 0, "skipped": 0})
        bucket["skipped" if case.status == "skipped" else "executed"] += 1
    for engine in expected_engines:
        if engine not in seen_engines:
            problems.append(
                Problem(
                    "engine-absent",
                    f"engine {engine!r} was expected in this run and produced no result at "
                    f"all. A matrix leg that silently disappears is not a passing leg.",
                )
            )
        elif per_engine.get(engine, {}).get("executed", 0) == 0:
            problems.append(
                Problem(
                    "engine-unexecuted",
                    f"engine {engine!r} ran but every one of its tests skipped. That is an "
                    f"engine which verified nothing.",
                )
            )

    # The independent probes, read before any skip is judged against them.
    probe_titles = {
        entry["probe_test"]: entry["id"] for entry in policy.raw["capabilities"] if entry.get("probe_test")
    }
    probe: dict[tuple[str, str], bool] = {}
    for case in cases:
        capability_id = probe_titles.get(case.title)
        if capability_id is None or case.status == "skipped":
            continue
        description = measured(case, policy, capability_id)
        if description is None:
            continue
        outcome = verdict_of(description)
        if outcome is not None:
            probe[(case.engine, capability_id)] = outcome

    used: dict[str, int] = {}
    skipped_titles: dict[str, set[str]] = {}
    executed_titles: set[str] = set()

    for case in cases:
        if case.status != "skipped":
            executed_titles.add(case.title)
            continue
        skipped_titles.setdefault(case.title, set()).add(case.engine)

        reasons = skip_reasons(case)
        if not reasons:
            problems.append(
                Problem(
                    "skip-no-reason",
                    f"[{case.engine}] {case.title}: skipped with no reason recorded. Use "
                    f"test.skip(condition, reason) so the report says what was unavailable.",
                )
            )
            continue

        for reason in reasons:
            match = policy.grammar.match(reason)
            if match is None:
                problems.append(
                    Problem(
                        "skip-unparseable",
                        f"[{case.engine}] {case.title}: skip reason {reason!r} is not in the "
                        f"declared grammar 'NOT APPLICABLE [<capability-id>]: <text>'. A "
                        f"sentence that merely begins NOT APPLICABLE is not a declaration.",
                    )
                )
                continue
            capability_id, _text = match.group(1), match.group(2)
            key = f"{case.engine} :: {capability_id}"
            used[key] = used.get(key, 0) + 1

            entry = policy.by_id.get(capability_id)
            if entry is None:
                problems.append(
                    Problem(
                        "skip-unknown",
                        f"[{case.engine}] {case.title}: capability {capability_id!r} is not "
                        f"in the policy. Declare it with the engines it is permitted on and "
                        f"how it is evidenced, or stop skipping.",
                    )
                )
                continue
            if case.engine not in entry["engines"]:
                problems.append(
                    Problem(
                        "skip-engine",
                        f"[{case.engine}] {case.title}: the policy permits "
                        f"{capability_id!r} on {entry['engines']}, so this engine should "
                        f"have run the check.",
                    )
                )
                continue
            if entry["evidence"] != "probe":
                continue

            description = measured(case, policy, capability_id)
            if description is None:
                problems.append(
                    Problem(
                        "skip-missing-evidence",
                        f"[{case.engine}] {case.title}: {capability_id!r} is evidenced by "
                        f"measurement, but the test attached no "
                        f"{policy.annotation_prefix}{capability_id} annotation. A skip with "
                        f"no measurement behind it is a skip taken on faith.",
                    )
                )
                continue
            outcome = verdict_of(description)
            if outcome is None:
                problems.append(
                    Problem(
                        "skip-evidence-format",
                        f"[{case.engine}] {case.title}: the "
                        f"{policy.annotation_prefix}{capability_id} annotation reads "
                        f"{description!r}, which begins with neither 'available' nor "
                        f"'unavailable'.",
                    )
                )
                continue
            if outcome is True:
                problems.append(
                    Problem(
                        "skip-self-contradicted",
                        f"[{case.engine}] {case.title}: skipped for {capability_id!r} while "
                        f"its own measurement says the capability was available: "
                        f"{description!r}. That is a site failure wearing a skip.",
                    )
                )
                continue

            independent = probe.get((case.engine, capability_id))
            if independent is None:
                problems.append(
                    Problem(
                        "probe-absent",
                        f"[{case.engine}] {case.title}: skipped for {capability_id!r}, but "
                        f"the independent control-fixture probe did not report on this "
                        f"engine. One test excusing itself is not evidence.",
                    )
                )
            elif independent is True:
                problems.append(
                    Problem(
                        "probe-contradicted",
                        f"[{case.engine}] {case.title}: skipped for {capability_id!r}, but "
                        f"the independent control-fixture probe measured that capability as "
                        f"available on this engine. The two disagree, so the skip is not "
                        f"justified.",
                    )
                )

    # A check skipped on every engine that ran it has been removed, whatever the policy
    # permits engine by engine. This is the dynamic form of policy-all-engines and it is
    # what catches a capability that happens to be missing everywhere on some platform.
    for title, engines in sorted(skipped_titles.items()):
        if title not in executed_titles:
            problems.append(
                Problem(
                    "check-never-ran",
                    f"{title!r} skipped on {sorted(engines)} and executed nowhere in this "
                    f"run. A check that is never made is not a check.",
                )
            )

    return {
        "executed": executed,
        "skipped": sum(1 for c in cases if c.status == "skipped"),
        "engines": {k: per_engine[k] for k in sorted(per_engine)},
        "skips_by_capability": {k: used[k] for k in sorted(used)},
        "probes": {f"{e} :: {c}": v for (e, c), v in sorted(probe.items())},
        "problems": [{"code": p.code, "message": p.message} for p in problems],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--report", action="append", required=True, help="Playwright JSON report; repeatable."
    )
    parser.add_argument("--policy", type=pathlib.Path, default=DEFAULT_POLICY)
    parser.add_argument(
        "--engines",
        default="chromium,firefox,webkit",
        help="Engines this run was asked to execute. Each must produce at least one executed test.",
    )
    parser.add_argument("--json", type=pathlib.Path, help="Write the machine-readable finding here.")
    parser.add_argument("--github", action="store_true", help="Emit ::error:: lines for Actions.")
    args = parser.parse_args(argv)

    policy = Policy.load(args.policy)
    expected = [e.strip() for e in args.engines.split(",") if e.strip()]

    overall: list[dict[str, Any]] = []
    failed = False
    for name in args.report:
        path = pathlib.Path(name)
        if not path.is_file():
            print(
                f"::error::no Playwright JSON report at {path}."
                if args.github
                else f"[no-report] {path} is missing."
            )
            overall.append(
                {"report": str(path), "problems": [{"code": "no-report", "message": f"{path} is missing"}]}
            )
            failed = True
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            message = f"{path} is not readable JSON: {exc}"
            print(f"::error::{message}" if args.github else f"[no-report] {message}")
            overall.append({"report": str(path), "problems": [{"code": "no-report", "message": message}]})
            failed = True
            continue

        finding = evaluate(data, policy, expected)
        finding["report"] = str(path)
        overall.append(finding)

        print(f"{path}: executed {finding['executed']}, skipped {finding['skipped']}")
        for engine, counts in finding["engines"].items():
            print(f"  {engine:<10} executed {counts['executed']:4d}  skipped {counts['skipped']:3d}")
        for key, count in finding["skips_by_capability"].items():
            print(f"  skipped {count:3d}  {key}")
        for key, value in finding["probes"].items():
            print(f"  probe    {'available' if value else 'unavailable':<12} {key}")
        for problem in finding["problems"]:
            line = f"{problem['code']}: {problem['message']}"
            print(f"::error::{line}" if args.github else f"  PROBLEM {line}")
        if finding["problems"]:
            failed = True

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"reports": overall}, indent=2) + "\n", encoding="utf-8")

    print("skip policy: FAIL" if failed else "skip policy: clean")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

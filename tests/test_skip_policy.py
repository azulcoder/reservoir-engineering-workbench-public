"""The gate that decides whether a browser skip is acceptable.

`scripts/check_skip_policy.py` is the only thing standing between "the suite is green" and
"the suite did not run the checks". It replaced two inline copies of the same logic, one in
each workflow, which matched whole English sentences and therefore stopped recognising a
declared skip the moment somebody reworded a message.

Every test here builds a Playwright JSON report in the shape the real reporter emits and
asserts on the finding CODE rather than on wording, so the messages can be improved without
rewriting this file. The cases are the ones a gate like this is worth having for: a
permitted skip with its evidence, an unknown skip, a skip with no measurement behind it, a
skip whose measurement contradicts it, an engine that ran nothing, an empty suite, and an
ordinary failure.
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY_PATH = REPO_ROOT / "site" / "tests" / "skip-policy.json"


def _load_module():
    """Import the script by path; scripts/ is not a package and should not become one."""
    path = REPO_ROOT / "scripts" / "check_skip_policy.py"
    spec = importlib.util.spec_from_file_location("check_skip_policy", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


csp = _load_module()

ENGINES = ["chromium", "firefox", "webkit"]
TAB_PROBE = "the tab-ring control fixture is measured, not assumed"
SCROLL_PROBE = "the keyboard-scroll control fixture is measured, not assumed"


def spec(title: str, engine: str, status: str, annotations: list[dict] | None = None) -> dict:
    """One spec in the report's shape: annotations on both the test and the result."""
    notes = annotations or []
    return {
        "title": title,
        "tests": [
            {
                "projectName": engine,
                "annotations": notes,
                "status": status,
                "results": [{"status": status, "annotations": notes}],
            }
        ],
    }


def skip_note(capability: str, sentence: str = "not available here") -> dict:
    return {"type": "skip", "description": f"NOT APPLICABLE [{capability}]: {sentence}"}


def capability_note(capability: str, available: bool) -> dict:
    verdict = "available" if available else "unavailable"
    return {
        "type": f"capability:{capability}",
        "description": f"{verdict} -- control fixture: measured in this run",
    }


def report(specs: list[dict], *, unexpected: int = 0) -> dict:
    skipped = sum(1 for s in specs for t in s["tests"] for r in t["results"] if r["status"] == "skipped")
    expected = sum(1 for s in specs for t in s["tests"] for r in t["results"] if r["status"] == "passed")
    return {
        "suites": [{"title": "root", "specs": specs, "suites": []}],
        "stats": {"expected": expected, "unexpected": unexpected, "flaky": 0, "skipped": skipped},
    }


def probes_ran(*, tab: dict[str, bool] | None = None, scroll: dict[str, bool] | None = None) -> list[dict]:
    """Build the independent control-fixture probe results, one per engine."""
    out: list[dict] = []
    for engine, available in (tab or {}).items():
        out.append(
            spec(TAB_PROBE, engine, "passed", [capability_note("tab-order-includes-links", available)])
        )
    for engine, available in (scroll or {}).items():
        out.append(
            spec(
                SCROLL_PROBE,
                engine,
                "passed",
                [capability_note("keyboard-scroll-overflow", available)],
            )
        )
    return out


def healthy_background() -> list[dict]:
    """Enough ordinary passing work on every engine that no engine rule fires."""
    return [spec("a route renders", engine, "passed") for engine in ENGINES]


def codes(finding: dict) -> set[str]:
    return {p["code"] for p in finding["problems"]}


class SkipPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = csp.Policy.load(POLICY_PATH)

    def evaluate(self, specs: list[dict], *, unexpected: int = 0, engines: list[str] | None = None) -> dict:
        return csp.evaluate(report(specs, unexpected=unexpected), self.policy, engines or ENGINES)

    # -- the policy itself ---------------------------------------------------

    def test_the_shipped_policy_has_no_static_problem(self) -> None:
        self.assertEqual(self.policy.static_problems(), [])

    def test_a_capability_permitted_on_every_engine_is_rejected(self) -> None:
        raw = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        raw["capabilities"][0]["engines"] = list(ENGINES)
        problems = csp.Policy(raw).static_problems()
        self.assertEqual({p.code for p in problems}, {"policy-all-engines"})

    # -- the case the gate is supposed to allow ------------------------------

    def test_a_permitted_evidenced_skip_is_clean(self) -> None:
        specs = healthy_background()
        specs += probes_ran(tab={"chromium": True, "firefox": True, "webkit": False})
        specs.append(
            spec(
                "the skip link is the first stop",
                "webkit",
                "skipped",
                [
                    skip_note("tab-order-includes-links"),
                    capability_note("tab-order-includes-links", False),
                ],
            )
        )
        # The same check runs where the capability is present, so it is skipped, not deleted.
        specs.append(spec("the skip link is the first stop", "chromium", "passed"))
        specs.append(spec("the skip link is the first stop", "firefox", "passed"))
        finding = self.evaluate(specs)
        self.assertEqual(finding["problems"], [], finding["problems"])
        self.assertEqual(finding["skips_by_capability"], {"webkit :: tab-order-includes-links": 1})

    def test_an_engine_only_capability_needs_no_probe(self) -> None:
        """print-to-pdf is an absent API, not a measurable behaviour."""
        specs = healthy_background()
        specs.append(spec("printing to PDF", "chromium", "passed"))
        specs.append(spec("printing to PDF", "firefox", "skipped", [skip_note("print-to-pdf")]))
        specs.append(spec("printing to PDF", "webkit", "skipped", [skip_note("print-to-pdf")]))
        self.assertEqual(self.evaluate(specs)["problems"], [])

    def test_a_platform_that_takes_fewer_skips_is_not_a_failure(self) -> None:
        """Linux WebKit may reach links where macOS WebKit does not. No count is imposed."""
        specs = healthy_background()
        specs += probes_ran(tab={e: True for e in ENGINES})
        specs += [spec("the skip link is the first stop", e, "passed") for e in ENGINES]
        finding = self.evaluate(specs)
        self.assertEqual(finding["problems"], [])
        self.assertEqual(finding["skips_by_capability"], {})

    # -- the cases the gate is supposed to catch -----------------------------

    def test_an_unknown_capability_id_fails(self) -> None:
        specs = healthy_background()
        specs.append(spec("something", "webkit", "skipped", [skip_note("flaky-on-tuesdays")]))
        specs.append(spec("something", "chromium", "passed"))
        self.assertIn("skip-unknown", codes(self.evaluate(specs)))

    def test_a_sentence_that_merely_begins_not_applicable_fails(self) -> None:
        """The old matcher's successor must not become a prefix matcher."""
        specs = healthy_background()
        specs.append(
            spec(
                "something",
                "webkit",
                "skipped",
                [{"type": "skip", "description": "NOT APPLICABLE in this environment: trust me"}],
            )
        )
        specs.append(spec("something", "chromium", "passed"))
        self.assertIn("skip-unparseable", codes(self.evaluate(specs)))

    def test_a_skip_with_no_reason_fails(self) -> None:
        specs = healthy_background()
        specs.append(spec("something", "webkit", "skipped"))
        specs.append(spec("something", "chromium", "passed"))
        self.assertIn("skip-no-reason", codes(self.evaluate(specs)))

    def test_a_probe_backed_skip_with_no_measurement_fails(self) -> None:
        specs = healthy_background()
        specs += probes_ran(tab={"webkit": False})
        specs.append(spec("something", "webkit", "skipped", [skip_note("tab-order-includes-links")]))
        specs.append(spec("something", "chromium", "passed"))
        self.assertIn("skip-missing-evidence", codes(self.evaluate(specs)))

    def test_a_measurement_that_contradicts_its_own_skip_fails(self) -> None:
        specs = healthy_background()
        specs += probes_ran(tab={"webkit": True})
        specs.append(
            spec(
                "something",
                "webkit",
                "skipped",
                [
                    skip_note("tab-order-includes-links"),
                    capability_note("tab-order-includes-links", True),
                ],
            )
        )
        specs.append(spec("something", "chromium", "passed"))
        self.assertIn("skip-self-contradicted", codes(self.evaluate(specs)))

    def test_an_independent_probe_that_contradicts_a_skip_fails(self) -> None:
        """The test says unavailable, the control fixture says available. That is a defect."""
        specs = healthy_background()
        specs += probes_ran(tab={"webkit": True})
        specs.append(
            spec(
                "something",
                "webkit",
                "skipped",
                [
                    skip_note("tab-order-includes-links"),
                    capability_note("tab-order-includes-links", False),
                ],
            )
        )
        specs.append(spec("something", "chromium", "passed"))
        self.assertIn("probe-contradicted", codes(self.evaluate(specs)))

    def test_a_skip_with_no_independent_probe_at_all_fails(self) -> None:
        specs = healthy_background()
        specs.append(
            spec(
                "something",
                "webkit",
                "skipped",
                [
                    skip_note("tab-order-includes-links"),
                    capability_note("tab-order-includes-links", False),
                ],
            )
        )
        specs.append(spec("something", "chromium", "passed"))
        self.assertIn("probe-absent", codes(self.evaluate(specs)))

    def test_an_engine_not_permitted_to_take_a_skip_fails(self) -> None:
        specs = healthy_background()
        specs += probes_ran(tab={"firefox": False})
        specs.append(
            spec(
                "something",
                "firefox",
                "skipped",
                [
                    skip_note("tab-order-includes-links"),
                    capability_note("tab-order-includes-links", False),
                ],
            )
        )
        specs.append(spec("something", "chromium", "passed"))
        self.assertIn("skip-engine", codes(self.evaluate(specs)))

    def test_a_check_skipped_on_every_engine_fails(self) -> None:
        """Permitted engine by engine, yet the check was never actually made."""
        specs = healthy_background()
        specs.append(spec("printing to PDF", "firefox", "skipped", [skip_note("print-to-pdf")]))
        specs.append(spec("printing to PDF", "webkit", "skipped", [skip_note("print-to-pdf")]))
        self.assertIn("check-never-ran", codes(self.evaluate(specs)))

    def test_an_empty_suite_fails(self) -> None:
        self.assertIn("empty-suite", codes(self.evaluate([])))

    def test_a_suite_of_nothing_but_skips_fails(self) -> None:
        specs = [spec("something", e, "skipped", [skip_note("print-to-pdf")]) for e in ENGINES]
        self.assertIn("empty-suite", codes(self.evaluate(specs)))

    def test_a_wholly_unexecuted_engine_fails(self) -> None:
        specs = [spec("a route renders", e, "passed") for e in ("chromium", "firefox")]
        self.assertIn("engine-absent", codes(self.evaluate(specs)))

    def test_an_engine_that_ran_only_skips_fails(self) -> None:
        specs = [spec("a route renders", e, "passed") for e in ("chromium", "firefox")]
        specs.append(spec("printing to PDF", "webkit", "skipped", [skip_note("print-to-pdf")]))
        specs.append(spec("printing to PDF", "chromium", "passed"))
        self.assertIn("engine-unexecuted", codes(self.evaluate(specs)))

    def test_an_ordinary_failure_fails(self) -> None:
        specs = healthy_background()
        specs.append(spec("a contrast check", "chromium", "failed"))
        self.assertIn("failure", codes(self.evaluate(specs)))

    def test_a_timeout_fails(self) -> None:
        specs = healthy_background()
        specs.append(spec("a slow check", "webkit", "timedOut"))
        self.assertIn("failure", codes(self.evaluate(specs)))

    def test_an_unexpected_count_with_no_visible_spec_still_fails(self) -> None:
        """A worker that died before writing its spec must not pass on a clean tree."""
        finding = self.evaluate(healthy_background(), unexpected=3)
        self.assertIn("failure", codes(finding))

    # -- the shape of the report ---------------------------------------------

    def test_annotations_are_read_from_the_result_when_the_test_has_none(self) -> None:
        """Playwright writes the same list to both; neither side alone may be relied on."""
        notes = [skip_note("tab-order-includes-links"), capability_note("tab-order-includes-links", False)]
        specs = healthy_background()
        specs += probes_ran(tab={"webkit": False})
        specs.append(
            {
                "title": "something",
                "tests": [
                    {
                        "projectName": "webkit",
                        "annotations": [],
                        "status": "skipped",
                        "results": [{"status": "skipped", "annotations": notes}],
                    }
                ],
            }
        )
        specs.append(spec("something", "chromium", "passed"))
        self.assertEqual(self.evaluate(specs)["problems"], [])

    def test_a_missing_report_file_is_a_failure_not_a_pass(self) -> None:
        exit_code = csp.main(["--report", str(REPO_ROOT / "no" / "such" / "report.json")])
        self.assertEqual(exit_code, 1)

    # -- the policy and the code that cites it -------------------------------

    def test_the_typescript_ids_are_the_policy_ids(self) -> None:
        """One source of truth, checked rather than trusted.

        `site/tests/support.ts` parses the same JSON at run time, so a drifted id would
        already throw there. This asserts it at the level a reader checks: the literal
        strings in the CAPABILITY map are exactly the declared ids, no more and no fewer.
        """
        source = (REPO_ROOT / "site" / "tests" / "support.ts").read_text(encoding="utf-8")
        block = source.split("export const CAPABILITY = {", 1)[1].split("} as const;", 1)[0]
        in_code = set(re.findall(r'"([a-z0-9][a-z0-9-]*)"', block))
        declared = {entry["id"] for entry in self.policy.raw["capabilities"]}
        self.assertEqual(in_code, declared)

    def test_every_workflow_defers_to_this_script(self) -> None:
        """Neither workflow may carry its own copy of the rules again.

        The inline validators were the defect: two copies of one policy, matched by exact
        English sentence, in the two files nobody edits when a test message changes.
        """
        for name in ("ci.yml", "pages.yml"):
            text = (REPO_ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            self.assertIn("scripts/check_skip_policy.py", text, f"{name} must call the shared gate")
            self.assertNotIn(
                "by_reason",
                text,
                f"{name} still carries an inline skip validator. There is one gate now.",
            )

    def test_release_mode_has_no_managed_server(self) -> None:
        """The Playwright config must not be able to build and serve a second directory.

        Read as source rather than executed: a config that imports @playwright/test cannot
        be evaluated by the stdlib runner, and what matters here is the guarantee, which is
        that QA_RELEASE=1 yields no webServer at all rather than a differently configured
        one.
        """
        config = (REPO_ROOT / "site" / "playwright.config.ts").read_text(encoding="utf-8")
        self.assertIn('const RELEASE = process.env.QA_RELEASE === "1";', config)
        self.assertIn("const managedServer = RELEASE\n  ? undefined", config)
        self.assertIn("webServer: managedServer,", config)


if __name__ == "__main__":
    unittest.main()

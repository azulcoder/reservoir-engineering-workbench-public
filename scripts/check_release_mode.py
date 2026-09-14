#!/usr/bin/env python3
"""Demonstrate that release verification cannot be handed a different directory.

The safeguard
-------------
Release verification builds a candidate directory, starts a server over it, fingerprints
it, runs the browser suite, and fingerprints it again. That sounds airtight and is not.
Playwright's configuration carries a managed `webServer` whose command is
`astro build && node tests/serve.mjs` over `site/dist`, and `reuseExistingServer` decides
between the caller's server and that one by probing a URL. If the caller's server is not
answering when the suite starts, Playwright starts its own, the suite runs against
`site/dist`, and the candidate directory passes its after-fingerprint unchanged --
unchanged precisely because nothing ever read it.

QA_RELEASE=1 removes the managed server entirely. This script checks that it does, and it
checks it the only way worth trusting: by showing the substitution happening first.

    A. CONTROL, non-release mode, dead port. Playwright must start its own server, which
       means `site/dist` appears where there was none. If this does not happen the
       instrument is broken and the release-mode result below would mean nothing -- the
       risk has to be demonstrable before its absence is evidence of anything.

    B. RELEASE mode, dead port. The run must FAIL and `site/dist` must NOT appear. No
       fallback, no substitution, no green run against bytes nobody is shipping.

    C. A server pointed at a build made for a different base must refuse to start, so a
       leg cannot test the project-base build while asserting root-base behaviour.

Each case is an observation with a real exit status, not a pipe tail.

    python3 scripts/check_release_mode.py
    python3 scripts/check_release_mode.py --json out.json --skip-control
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
SITE = REPO / "site"
DIST = SITE / "dist"

# One test, one engine. The question is which directory was served, not what it contains.
PROBE = [
    "npx",
    "playwright",
    "test",
    "tests/routes.spec.ts",
    "--project=chromium",
    "-g",
    "responds 200 and carries one h1",
    "--reporter=list",
]


def free_port() -> int:
    """Find a port nothing is listening on, released so the run finds it closed."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def run(argv: list[str], env: dict[str, str], timeout: int) -> tuple[int, str]:
    try:
        done = subprocess.run(
            argv,
            cwd=str(SITE),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return 124, f"timed out after {timeout}s\n{exc.stdout or ''}{exc.stderr or ''}"
    return done.returncode, done.stdout + done.stderr


def environment(**overrides: str) -> dict[str, str]:
    env = dict(os.environ)
    env.update(overrides)
    return env


def clear_dist() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--json", type=pathlib.Path, help="Write the observations here.")
    parser.add_argument(
        "--skip-control",
        action="store_true",
        help="Skip case A, which runs a real astro build. The release-mode result is then "
        "an assertion rather than a contrast.",
    )
    parser.add_argument(
        "--project-dist",
        default="dist-project",
        help="A build made for the project base, for the wrong-base case.",
    )
    parser.add_argument("--timeout", type=int, default=420)
    args = parser.parse_args()

    base = "/reservoir-engineering-workbench-public/"
    cases: list[dict] = []

    existing_dist = DIST.exists()
    if existing_dist:
        print(f"note: {DIST} exists and is in the way of this check; removing it.")
        clear_dist()

    # -- A. control: prove the fallback is real ------------------------------
    if args.skip_control:
        cases.append(
            {
                "case": "control-fallback-not-run",
                "verdict": "not measured",
                "detail": "--skip-control was passed, so case B is an assertion, not a contrast.",
            }
        )
    else:
        port = free_port()
        code, output = run(
            PROBE,
            environment(QA_BASE=base, QA_PORT=str(port), QA_REUSE="1", QA_WORKERS="1"),
            args.timeout,
        )
        appeared = DIST.is_dir() and any(DIST.iterdir())
        cases.append(
            {
                "case": "control: non-release mode, no server listening",
                "expectation": "Playwright starts its own server and builds site/dist",
                "exit": code,
                "site_dist_created": appeared,
                "verdict": "substitution demonstrated" if appeared else "instrument broken",
                "detail": output.strip().splitlines()[-1] if output.strip() else "",
            }
        )
        clear_dist()

    # -- B. release mode: no fallback to fall back to ------------------------
    port = free_port()
    code, output = run(
        PROBE,
        environment(QA_BASE=base, QA_PORT=str(port), QA_RELEASE="1", QA_WORKERS="1"),
        args.timeout,
    )
    appeared = DIST.is_dir() and any(DIST.iterdir())
    cases.append(
        {
            "case": "release mode, no server listening",
            "expectation": "the run fails and nothing is built",
            "exit": code,
            "site_dist_created": appeared,
            "verdict": "caught" if (code != 0 and not appeared) else "NOT CAUGHT",
            "detail": (
                "site/dist was created in release mode"
                if appeared
                else "exited non-zero with no build"
                if code != 0
                else "the run passed with no server, which is impossible"
            ),
        }
    )
    clear_dist()

    # -- C. a server cannot serve a build made for another base --------------
    project_dist = SITE / args.project_dist
    if not (project_dist / "index.html").is_file():
        cases.append(
            {
                "case": "wrong base rejected",
                "verdict": "not measured",
                "detail": f"{project_dist} does not exist; build it first.",
            }
        )
    else:
        port = free_port()
        # The directory is a project-base build; the server is told the site is at root.
        code, output = run(
            ["node", "tests/serve.mjs"],
            environment(QA_DIST=str(project_dist), QA_BASE="/", QA_PORT=str(port)),
            60,
        )
        refused = code != 0 and "built for a different base" in output
        cases.append(
            {
                "case": "wrong base rejected",
                "expectation": "serve.mjs refuses a build made for another base",
                "exit": code,
                "verdict": "caught" if refused else "NOT CAUGHT",
                "detail": output.strip().splitlines()[-1] if output.strip() else "",
            }
        )

    not_caught = [c for c in cases if c["verdict"] == "NOT CAUGHT"]
    broken = [c for c in cases if c["verdict"] == "instrument broken"]
    summary = {
        "tool": "scripts/check_release_mode.py",
        "cases": cases,
        "not_caught": len(not_caught),
        "instrument_broken": len(broken),
        "status": "passed" if not not_caught and not broken else "failed",
    }
    blob = json.dumps(summary, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(blob + "\n", encoding="utf-8")
    print(blob)
    for case in cases:
        print(f"  {case['verdict']:<26} {case['case']}")
    print(f"\ncheck_release_mode: {summary['status']}")
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())

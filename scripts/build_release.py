#!/usr/bin/env python3
r"""The one canonical build and validation sequence for a publishable tree.

Run it locally, run it from CI, run it twice for the two base paths. There is no second
list of steps anywhere: whatever this script does is what "building the release" means.

    python3 scripts/build_release.py --base-path / --out-dir site/dist-root
    python3 scripts/build_release.py \\
        --base-path /reservoir-engineering-workbench-public/ \\
        --out-dir site/dist-project

The order is not arbitrary. Each step is allowed to depend only on what the steps above
it have already established, so a failure names the earliest broken link rather than a
symptom several stages downstream.

    1  public-source policy            scripts/check_public_release.py
       verification prerequisites      scripts/verify.py --profile public-core
    2  figure-data validation          scripts/export_presentation_data.py, re-exported
       and reconciliation              into a scratch directory and compared with the
                                       committed export byte for byte. The exporter
                                       reconciles every value against the frozen case
                                       summary and refuses to write on a disagreement.
    3  figure rendering                site: node scripts/render-figures.mjs
    4  public-download emission        site: node src/scripts/emit-public-data.mjs
    5  download/source consistency     site: node src/scripts/emit-public-data.mjs --verify
    6  site and tooling type checks    site: npm run check
    7  static site generation          site: npx astro build --outDir <out>
       required-output validation      the checks in `validate_output` below

Three properties this script is built to have, because the usual ways of getting them
wrong are the usual ways a red build reports green.

Real exit status, through any log.
    Every command runs through `subprocess.Popen` and its status comes from `wait()`.
    Output is teed to a log file by this process, in Python, so there is never a shell
    pipeline whose exit status is the status of `tee`. A caller who pipes this script's
    own stdout somewhere still gets this script's exit code, because nothing here is
    the left-hand side of a pipe.

A skipped step is not a pass.
    A step that could not run is BLOCKED and the run fails. There is no "not applicable",
    no "tool missing, continuing", and no optional step whose absence is silently fine.
    Narrowing a step's scope through an argument is recorded in the summary as reduced
    coverage so that a green run cannot be read as more than it was.

A machine-readable summary.
    `--json <path>` writes the whole run: every step, its argv, its exit status, its
    duration, its log file. The same object is printed to stdout under a marker line so
    a CI job can parse it without a file.

Output directory
    `--out-dir` is mandatory and is passed to `astro build --outDir`, so two base builds
    never write into the same `site/dist` and cannot race or overwrite each other.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time

REPO = pathlib.Path(__file__).resolve().parent.parent
SITE = REPO / "site"
GENERATED = SITE / "src" / "generated" / "figures"

#: Routes that must exist in any published build. A build missing one of these is not a
#: smaller site, it is a broken one: every page below is linked from the navigation.
REQUIRED_ROUTES = (
    "index.html",
    "404.html",
    "about/index.html",
    "methods/index.html",
    "studies/index.html",
    "studies/a1/index.html",
    "studies/a2/index.html",
    "studies/a3/index.html",
    "studies/a4/index.html",
)

PASSED = "passed"
FAILED = "failed"
BLOCKED = "blocked"


class Step:
    """One step of the sequence, with its own log file and its own real exit status."""

    def __init__(self, key: str, title: str) -> None:
        self.key = key
        self.title = title
        self.status = BLOCKED
        self.exit_code: int | None = None
        self.argv: list[str] = []
        self.log: str | None = None
        self.detail = "not reached"
        self.seconds = 0.0
        self.coverage_note: str | None = None
        #: True only when the step could not be attempted at all -- a missing tool, say.
        #: A step that ran and exited non-zero FAILED; conflating the two would let a
        #: real failure be read as an environment problem.
        self.unrunnable = False

    def as_dict(self) -> dict[str, object]:
        """Render the step as it appears in the machine-readable summary."""
        out: dict[str, object] = {
            "step": self.key,
            "title": self.title,
            "status": self.status,
            "exit_code": self.exit_code,
            "seconds": round(self.seconds, 2),
            "detail": self.detail,
        }
        if self.argv:
            # A recorded command must be readable on another machine. Any absolute path
            # inside the repository is written relative to it; the rest is left alone.
            out["command"] = [rel(a) if a.startswith(str(REPO)) else a for a in self.argv]
        if self.log:
            out["log"] = self.log
        if self.coverage_note:
            out["coverage"] = self.coverage_note
        return out


#: Published count -> (key in verify.py's JSON totals, label, needs the full case set).
#:
#: The test counts do not depend on which synthetic cases were re-run, so they are
#: comparable under any --cases value. The CHECK counts are not: each re-run case
#: registers its own check, so --cases fast collects 7 where --cases all collects 9.
#: Comparing the published number against a deliberately reduced run would fail a build
#: for running less, which is not drift.
PUBLISHED_COUNTS = {
    "testsCollected": ("tests_collected", "tests collected", False),
    "testsPassed": ("tests_passed", "tests passed", False),
    "testsFailedOrErrored": ("tests_failed", "tests failed or errored", False),
    "testsSkipped": ("tests_skipped", "tests skipped", False),
    "checksCollected": ("checks_collected", "checks collected", True),
    "checksPassed": ("checks_passed", "checks passed", True),
}


def published_counts_drift(report: pathlib.Path, *, full_cases: bool) -> list[str]:
    """Compare the counts the site prints with the counts this run measured.

    `site/src/scripts/site.ts` carries the verification numbers as literals because the
    pages state them in prose. They were maintained by hand and went stale, which is the
    one failure mode a published number must not have: the site said 641 collected and
    621 passed against a measured 667 and 647, and it carried 10 checks collected with 9
    passed -- one number from a run with --expect-reference-skips and one from a run
    without it.

    This reads the literals back out of the TypeScript and checks them against verify.py's
    own JSON for the run that just finished. Under a reduced --cases value the check
    counts are not comparable and are left alone; the test counts always are. Returns a
    list of disagreements, empty when they agree.
    """
    totals = json.loads(report.read_text(encoding="utf-8"))["totals"]
    source = (SITE / "src" / "scripts" / "site.ts").read_text(encoding="utf-8")
    block = source.split("export const VERIFICATION = {", 1)[-1].split("} as const;", 1)[0]

    problems = []
    for key, (measured_key, label, needs_full) in PUBLISHED_COUNTS.items():
        if needs_full and not full_cases:
            continue
        found = re.search(rf"^\s*{key}:\s*(\d+),", block, re.MULTILINE)
        if found is None:
            problems.append(f"{key} is not declared, so the site cannot state {label}")
            continue
        published = int(found.group(1))
        measured = int(totals[measured_key])
        if published != measured:
            problems.append(f"{label}: site says {published}, this run measured {measured}")
    return problems


def rel(path: pathlib.Path | str) -> str:
    """Express a path relative to the repository when it lies inside it.

    The release summary is a published record. An absolute path from the build machine
    tells a reader nothing they can act on and leaks the layout of a private system, which
    is why scripts/check_public_release.py refuses one. Paths outside the repository --
    a temporary log directory, for example -- are reported by basename only.
    """
    candidate = pathlib.Path(path)
    try:
        return str(candidate.resolve().relative_to(REPO))
    except ValueError:
        return f"<outside repository>/{candidate.name}"


class Runner:
    """Runs the steps in order, teeing each one to its own log."""

    def __init__(self, log_dir: pathlib.Path, quiet: bool) -> None:
        self.log_dir = log_dir
        self.quiet = quiet
        self.steps: list[Step] = []

    def step(self, key: str, title: str) -> Step:
        """Register a step, in the order it will run."""
        step = Step(key, title)
        self.steps.append(step)
        return step

    def run(
        self,
        step: Step,
        argv: list[str],
        *,
        cwd: pathlib.Path,
        env: dict[str, str] | None = None,
    ) -> int:
        """Run a command, tee its output to a log, and return its real exit status.

        The tee is done here rather than by a shell pipeline. `cmd | tee log` reports the
        exit status of `tee`, which is almost always zero, and that is precisely how a
        failing build step becomes a passing CI job.
        """
        step.argv = argv
        log_path = self.log_dir / f"{step.key}.log"
        step.log = str(log_path.relative_to(REPO)) if log_path.is_relative_to(REPO) else str(log_path)

        merged = os.environ.copy()
        if env:
            merged.update(env)

        started = time.monotonic()
        header = f"$ cd {cwd}\n$ {' '.join(argv)}\n"
        if not self.quiet:
            sys.stdout.write(header)
            sys.stdout.flush()
        with log_path.open("w", encoding="utf-8") as log:
            log.write(header)
            try:
                process = subprocess.Popen(
                    argv,
                    cwd=str(cwd),
                    env=merged,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
            except FileNotFoundError as error:
                step.status = BLOCKED
                step.unrunnable = True
                step.detail = f"{argv[0]} is not installed or not on PATH: {error}"
                log.write(f"{step.detail}\n")
                step.seconds = time.monotonic() - started
                return 127
            assert process.stdout is not None
            for line in process.stdout:
                log.write(line)
                if not self.quiet:
                    sys.stdout.write(line)
            code = process.wait()
        step.seconds = time.monotonic() - started
        step.exit_code = code
        if not self.quiet:
            sys.stdout.write(f"  -> exit {code} ({step.seconds:.1f}s)\n\n")
            sys.stdout.flush()
        return code

    def finish(self, step: Step, code: int, ok_detail: str, fail_detail: str) -> bool:
        """Record a step's verdict from its real exit status. Returns True on a pass."""
        if code == 0:
            step.status = PASSED
            step.detail = ok_detail
            return True
        step.status = BLOCKED if step.unrunnable else FAILED
        step.detail = f"{fail_detail} (exit {code}); see {step.log}"
        return False


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_files(root: pathlib.Path) -> list[str]:
    return sorted(str(p.relative_to(root)).replace(os.sep, "/") for p in root.rglob("*") if p.is_file())


def compare_trees(expected: pathlib.Path, actual: pathlib.Path) -> list[str]:
    """Byte-for-byte comparison of two directories, in both directions."""
    want, have = tree_files(expected), tree_files(actual)
    problems = [f"missing from the committed export: {n}" for n in want if n not in have]
    problems += [f"present but not produced by a fresh export: {n}" for n in have if n not in want]
    for name in (n for n in want if n in have):
        a, b = (expected / name).read_bytes(), (actual / name).read_bytes()
        if a != b:
            problems.append(
                f"{name}: a fresh export is {len(a)} B sha {hashlib.sha256(a).hexdigest()[:12]}, "
                f"the committed file is {len(b)} B sha {hashlib.sha256(b).hexdigest()[:12]}"
            )
    return problems


# --------------------------------------------------------------------------- #
# Step 7b: required-output validation
# --------------------------------------------------------------------------- #


def validate_output(out_dir: pathlib.Path, base_path: str) -> list[str]:
    """Check the built site against what a publishable build has to contain.

    The interesting check is the last link of the provenance chain. Every other stage is
    verified against a file; this one is verified against the page a reader actually
    loads. `exhibits.ts` inlines the canonical SVG with leading and trailing whitespace
    trimmed and changes nothing else, so those exact bytes must appear verbatim in the
    built HTML. If Astro, a plugin or a future refactor ever rewrote an id or an
    accessibility association on the way in, this substring test is what would catch it,
    and the transformation would then have to be declared and tested in its own right
    rather than quietly widening what "identical" means.
    """
    problems: list[str] = []

    for route in REQUIRED_ROUTES:
        if not (out_dir / route).is_file():
            problems.append(f"required route missing from the build: {route}")
    if problems:
        return problems

    html_files = sorted(out_dir.rglob("*.html"))
    pages = {p: p.read_text(encoding="utf-8") for p in html_files}

    # 1. Every published download is in the build, at the size and digest index.json
    #    records. astro copies public/ verbatim; this proves it did.
    index_path = out_dir / "data" / "index.json"
    if not index_path.is_file():
        problems.append("data/index.json is not in the build; the downloads have no verification record")
        return problems
    index = json.loads(index_path.read_text(encoding="utf-8"))
    rasters = 0
    for entry in index["files"]:
        published = out_dir / "data" / entry["name"]
        if not published.is_file():
            problems.append(f"{entry['name']}: indexed but not in the build")
            continue
        data = published.read_bytes()
        if len(data) != entry["bytes"]:
            problems.append(f"{entry['name']}: {len(data)} B in the build, index records {entry['bytes']} B")
        digest = hashlib.sha256(data).hexdigest()
        if digest != entry["sha256"]:
            problems.append(
                f"{entry['name']}: sha {digest[:12]} in the build, index records {entry['sha256'][:12]}"
            )
        if entry.get("kind") == "exhibit-raster":
            rasters += 1
        # 2. The published copy is still the canonical rendered file, in the output.
        source = entry.get("source_path")
        if source:
            canonical = REPO / source
            if not canonical.is_file():
                problems.append(f"{entry['name']}: canonical source {source} is absent")
            elif canonical.read_bytes() != data:
                problems.append(
                    f"{entry['name']}: the built download is not byte-identical to {source}, "
                    f"which index.json says it is a copy of"
                )
    if rasters == 0:
        problems.append("no raster download reached the build; the PNG exports are not published")

    # 3. Every figure the build displays carries the canonical drawing verbatim.
    for svg in sorted(GENERATED.glob("*.svg")):
        figure_id = svg.stem
        markup = svg.read_text(encoding="utf-8").strip()
        anchor = re.compile(rf'<figure[^>]*\sid="{re.escape(figure_id)}"')
        hosts = [p for p, text in pages.items() if anchor.search(text)]
        if not hosts:
            continue  # a rendered figure no page displays is the figure stream's call
        for host in hosts:
            if markup not in pages[host]:
                problems.append(
                    f"{host.relative_to(out_dir)}: the inlined {figure_id} is not the canonical "
                    f"drawing in site/src/generated/figures/{svg.name}. The page and the download "
                    f"have drifted apart, or something rewrote the SVG on the way into the HTML."
                )

    # 4. Rasters are downloads, not page payload: nothing renders or preloads one.
    payload = re.compile(r'(?:<img[^>]+src|<link[^>]+href|<image[^>]+href)="[^"]*/data/figures/[^"]*\.png"')
    for path, text in pages.items():
        hit = payload.search(text)
        if hit:
            problems.append(
                f"{path.relative_to(out_dir)}: a raster is in the page payload — {hit.group(0)}. "
                f"PNGs are downloads only."
            )

    # 5. Base path. Every internal absolute URL must carry it, or the project deployment
    #    is a site of broken links that looks perfect at root.
    attr = re.compile(r'(?:href|src)="(/[^"]*)"')
    for path, text in pages.items():
        for url in set(attr.findall(text)):
            if not url.startswith(base_path):
                problems.append(
                    f"{path.relative_to(out_dir)}: {url} does not start with the base path "
                    f"{base_path}; it 404s on a project deployment"
                )

    return problems


# --------------------------------------------------------------------------- #
# The sequence
# --------------------------------------------------------------------------- #


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--base-path",
        required=True,
        help='base path the site is served under, e.g. "/" or "/reservoir-engineering-workbench-public/"',
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        help="directory the static site is built into. Two base builds must use two directories.",
    )
    parser.add_argument("--site-url", default=None, help="absolute origin, when one is configured")
    parser.add_argument("--json", default=None, help="write the machine-readable summary here")
    parser.add_argument("--log-dir", default=None, help="directory for per-step logs (default: a temp dir)")
    parser.add_argument(
        "--verify-cases",
        choices=("all", "fast", "none"),
        default="fast",
        help="which synthetic case reproductions scripts/verify.py re-runs (default: fast). "
        "Anything but 'all' is recorded in the summary as reduced coverage.",
    )
    parser.add_argument("--quiet", action="store_true", help="do not echo command output to stdout")
    args = parser.parse_args()

    base_path = args.base_path
    if not base_path.startswith("/") or not base_path.endswith("/"):
        sys.stderr.write(
            f"build_release: --base-path must start and end with '/', got {base_path!r}. "
            f'Astro normalises "/repo" to "/repo/" and a mismatch here is a site of broken links.\n'
        )
        return 2

    out_dir = pathlib.Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = (REPO / out_dir).resolve()
    log_dir = (
        pathlib.Path(args.log_dir).resolve()
        if args.log_dir
        else pathlib.Path(tempfile.mkdtemp(prefix="build-release-logs-"))
    )
    log_dir.mkdir(parents=True, exist_ok=True)

    runner = Runner(log_dir, args.quiet)
    started = time.time()

    # ---- 0. Preconditions. A missing tool is BLOCKED, never skipped. ----------
    pre = runner.step("00-preconditions", "toolchain and tree preconditions")
    missing = [name for name in ("node", "npm", "npx") if shutil.which(name) is None]
    if not (SITE / "node_modules").is_dir():
        missing.append("site/node_modules (run: npm ci --prefix site)")
    if not (SITE / "src" / "data" / "figures" / "contract.json").is_file():
        missing.append("site/src/data/figures/contract.json")
    if missing:
        pre.status = BLOCKED
        pre.detail = "cannot run the sequence: " + ", ".join(missing)
    else:
        pre.status = PASSED
        pre.exit_code = 0
        pre.detail = f"node, npm, npx present; site/node_modules present; building into {rel(out_dir)}"

    ok = pre.status == PASSED
    scratch = pathlib.Path(tempfile.mkdtemp(prefix="build-release-"))

    try:
        # ---- 1. Public-source policy and verification prerequisites ----------
        if ok:
            s = runner.step("01-public-release-policy", "public-source policy")
            code = runner.run(s, [sys.executable, "scripts/check_public_release.py"], cwd=REPO)
            ok = runner.finish(
                s,
                code,
                "no restricted file, no reference-derived payload, no private path",
                "the tree may not be published",
            )

        if ok:
            s = runner.step("02-verify", "declared verification prerequisites")
            report = log_dir / "verify.json"
            argv = [
                sys.executable,
                "scripts/verify.py",
                "--profile",
                "public-core",
                "--cases",
                args.verify_cases,
                "--json",
                str(report),
            ]
            if args.verify_cases != "all":
                s.coverage_note = (
                    f"--cases {args.verify_cases}: not every synthetic case was re-run. "
                    f"A pass here is narrower than a pass with --cases all."
                )
            code = runner.run(s, argv, cwd=REPO)
            ok = runner.finish(
                s,
                code,
                f"public-core profile passed with --cases {args.verify_cases}",
                "verification failed",
            )

            # The site publishes these counts as prose. Nothing tied them to a run, and
            # they drifted: the site said 641 collected / 621 passed / 9 checks passed
            # while the profile measured 667 / 647 / 10. A number a reader is invited to
            # check has to come from the run that is happening now, so this compares the
            # two and fails the build rather than publishing a figure nobody measured.
            if ok:
                problems = published_counts_drift(report, full_cases=args.verify_cases == "all")
                if problems:
                    s.detail = "; ".join(problems)
                    s.status = "FAILED"
                    s.exit_code = 1
                    ok = False
                    for problem in problems:
                        print(f"  site/src/scripts/site.ts disagrees with this run: {problem}")

        # ---- 2. Figure-data validation and reconciliation --------------------
        if ok:
            s = runner.step("03-export-figure-data", "figure-data validation and reconciliation")
            fresh = scratch / "figures"
            code = runner.run(
                s,
                [
                    sys.executable,
                    "scripts/export_presentation_data.py",
                    "--out",
                    str(scratch / "export"),
                    "--site-data",
                    str(fresh),
                ],
                cwd=REPO,
                env={"PYTHONPATH": "src"},
            )
            if code == 0:
                drift = compare_trees(fresh, SITE / "src" / "data" / "figures")
                if drift:
                    s.status = FAILED
                    s.detail = (
                        "the committed figure data is not what the exporter produces today:\n  "
                        + "\n  ".join(drift)
                    )
                    (log_dir / "03-export-figure-data.log").open("a", encoding="utf-8").write(s.detail + "\n")
                    ok = False
                else:
                    s.status = PASSED
                    s.detail = (
                        "the exporter reconciled every value against the frozen case summary, and "
                        "the committed export matches a fresh one byte for byte"
                    )
            else:
                ok = runner.finish(s, code, "", "the exporter refused to write")

        # ---- 3. Figure rendering from the checked inputs ---------------------
        if ok:
            s = runner.step("04-render-figures", "figure rendering from the checked inputs")
            code = runner.run(s, ["node", "scripts/render-figures.mjs"], cwd=SITE)
            ok = runner.finish(
                s, code, "every figure redrawn from the contract-checked data", "rendering failed"
            )

        # ---- 4. Public-download emission -------------------------------------
        if ok:
            s = runner.step("05-emit-downloads", "public-download emission")
            code = runner.run(s, ["node", "src/scripts/emit-public-data.mjs"], cwd=SITE)
            ok = runner.finish(
                s, code, "downloads written from the canonical rendered outputs", "emission failed"
            )

        # ---- 5. Download/source consistency ----------------------------------
        if ok:
            s = runner.step("06-download-identity", "download/source consistency")
            code = runner.run(s, ["node", "src/scripts/emit-public-data.mjs", "--verify"], cwd=SITE)
            ok = runner.finish(
                s,
                code,
                "every published download is byte-identical to the canonical file it copies",
                "a published download is not what was rendered",
            )

        # ---- 6. Site and tooling type checks ---------------------------------
        if ok:
            s = runner.step("07-type-check", "site and tooling type checks")
            code = runner.run(s, ["npm", "run", "check"], cwd=SITE)
            ok = runner.finish(s, code, "astro check and tsc both clean", "type checking failed")

        # ---- 7. Static site generation and required-output validation ---------
        if ok:
            s = runner.step("08-build-site", f"static site generation at base {base_path}")
            env = {"SITE_BASE": base_path}
            if args.site_url:
                env["SITE_URL"] = args.site_url
            else:
                env.pop("SITE_URL", None)
            code = runner.run(s, ["npx", "astro", "build", "--outDir", str(out_dir)], cwd=SITE, env=env)
            ok = runner.finish(s, code, f"built into {rel(out_dir)}", "the site build failed")

        if ok:
            s = runner.step("09-validate-output", "required-output validation")
            t0 = time.monotonic()
            problems = validate_output(out_dir, base_path)
            s.seconds = time.monotonic() - t0
            s.log = (
                str((log_dir / "09-validate-output.log").relative_to(REPO))
                if (log_dir / "09-validate-output.log").is_relative_to(REPO)
                else str(log_dir / "09-validate-output.log")
            )
            text = (
                "every required route present; every published download in the build at its "
                "recorded digest; every displayed figure byte-identical to its canonical drawing; "
                "no raster in a page payload; every internal URL under " + base_path
                if not problems
                else "\n".join(problems)
            )
            (log_dir / "09-validate-output.log").write_text(text + "\n", encoding="utf-8")
            if problems:
                s.status = FAILED
                s.exit_code = 1
                s.detail = f"{len(problems)} problem(s):\n  " + "\n  ".join(problems)
                ok = False
                if not args.quiet:
                    sys.stdout.write(s.detail + "\n\n")
            else:
                s.status = PASSED
                s.exit_code = 0
                s.detail = text
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    # ---- Summary -------------------------------------------------------------
    statuses = [step.status for step in runner.steps]
    overall = PASSED if statuses and all(s == PASSED for s in statuses) else FAILED
    summary = {
        "tool": "scripts/build_release.py",
        "base_path": base_path,
        "out_dir": rel(out_dir),
        "site_url": args.site_url,
        "log_dir": rel(log_dir),
        "started_epoch": int(started),
        "seconds": round(time.time() - started, 1),
        "status": overall,
        "steps_total": len(runner.steps),
        "steps_passed": statuses.count(PASSED),
        "steps_failed": statuses.count(FAILED),
        "steps_blocked": statuses.count(BLOCKED),
        "coverage_reductions": [s.coverage_note for s in runner.steps if s.coverage_note],
        "steps": [step.as_dict() for step in runner.steps],
    }
    blob = json.dumps(summary, indent=2)
    if args.json:
        pathlib.Path(args.json).write_text(blob + "\n", encoding="utf-8")
    sys.stdout.write("--- build_release summary (json) ---\n")
    sys.stdout.write(blob + "\n")

    width = max(len(s.key) for s in runner.steps)
    sys.stdout.write("\n")
    for step in runner.steps:
        sys.stdout.write(f"{step.status.upper():<8} {step.key:<{width}}  {step.title}\n")
    if summary["coverage_reductions"]:
        for note in summary["coverage_reductions"]:
            sys.stdout.write(f"REDUCED  coverage: {note}\n")
    sys.stdout.write(
        f"\nbuild_release: {overall} — {summary['steps_passed']}/{summary['steps_total']} steps "
        f"passed, {summary['steps_failed']} failed, {summary['steps_blocked']} blocked, "
        f"{summary['seconds']}s. Logs: {log_dir}\n"
    )
    if overall != PASSED:
        for step in runner.steps:
            if step.status != PASSED:
                sys.stderr.write(f"build_release: {step.status} at {step.key}: {step.detail}\n")
    return 0 if overall == PASSED else 1


if __name__ == "__main__":
    sys.exit(main())

# Verification

This is the record of what has actually been checked in this repository, what has not,
and how to reproduce either. It is written to be falsifiable: every number below came
from running a command on a named date on a named interpreter, and the commands are
given so that a reader can disagree with me by running them.

Two claims that this document deliberately does not make: that the library has been
validated against field data, and that a hosted continuous-integration service has run
anything. Neither has happened. See "What has not been verified" at the end.

Measurements were taken on 2026-09-13 with CPython 3.13.2 on macOS (darwin, arm64),
ruff 0.16.2.

## Two profiles

Verification runs at one of two depths, and the difference is worth a name because it
is the difference between "this code agrees with itself" and "this code agrees with
something it did not produce".

### public-core

Everything a clone of the public tree can run, with no restricted files and no network.
It covers the numerical core, the analytic and closed-form identities, the dependency
policy, and the synthetic case studies, which it re-runs from scratch and compares
against their committed snapshots.

How that comparison is made depends on where it runs, and the difference is the point.
Inside the canonical environment -- Linux on x86_64, defined by digest in
`docs/release/canonical_environment.json` -- it is exact byte identity, checked with
`diff`, with no tolerance. Anywhere else it is `scripts/compare_case_outputs.py`: every
acceptance state, seed, threshold and identifier compared exactly, and every computed
float checked against the declared envelope in `docs/release/portability_envelope.json`.

These are different claims and the runner reports them under different names. Requiring
identical bytes across operating systems would be requiring something this project does
not have and does not need: two dozen libm functions are permitted to disagree in their
last place, and a Monte Carlo draw or a Newton iteration turns that into a different
final digit without moving any conclusion.

    python3 scripts/verify.py --profile public-core

This is a self-consistency and reproducibility result. The code agrees with its own
committed snapshots, its own analytic limits, and its own closed forms, and it has not
drifted. It is not external validation, and nothing in this repository should describe
it as validated, benchmarked against reality, or field-proven. A profile that cannot see
an independent reference cannot tell you the library is right about the physical world.
It can tell you the library is internally coherent, which is a real and useful thing to
know, and is all it is claimed to be.

### external-reference

An explicit opt-in for a reader who has obtained the NIST Chemistry WebBook extract
themselves. This is the only profile that compares the library against values it did not
produce.

    python3 scripts/verify.py --profile external-reference \
        --reference-dir /path/to/your/extract \
        --access-basis "how you came to hold this data"

It requires both arguments and fails clearly without either. The access basis is
recorded in the report on purpose: access rights and redistribution rights are different
rights, and a verification record that does not say which one the operator had is not a
record worth keeping.

It also refuses to move data for you. The test oracle in `tests/oracles/nist.py` reads
`data/reference/` and nothing else, so if your copy lives elsewhere the profile verifies
its digests against the committed manifest, reports the reference-dependent tests as not
run, and tells you to place or symlink the files yourself. Writing restricted data into
the repository tree is a decision for the person who holds it, not for a script.

## Measured results, public-core, 2026-09-13

    python3 scripts/verify.py --profile public-core --cases all --expect-reference-skips 20

| Quantity                              | Measured |
| ------------------------------------- | -------- |
| checks collected                      | 10       |
| checks passed                         | 9        |
| mandatory checks failed               | 0        |
| tests collected                       | 641      |
| tests passed                          | 621      |
| tests failed or errored               | 0        |
| tests skipped                         | 20       |
| reference-dependent tests, not run    | 20       |
| reference-dependent checks, not run   | 2        |
| synthetic cases reproduced            | 3 of 3   |

The tenth check is the published-tree data policy, reported as a prerequisite rather
than folded into the verdict. See "Prerequisites" below.

The same suite under the other runner, for comparison:

| Runner                              | Command                              | Result                                          |
| ----------------------------------- | ------------------------------------ | ----------------------------------------------- |
| standard library (`unittest`)       | `python3 scripts/check.py`           | 641 run, 0 failed, 0 errored, 20 skipped, 8.6 s |
| pytest                              | `python3 -m pytest -q`               | 621 passed, 20 skipped, 1843 subtests, 8.5 s   |

The two counts differ only in how each runner reports a skip: `unittest` counts a
skipped test in `testsRun` and pytest does not. 641 minus 20 is 621.

Case reproduction, each run into a fresh directory and diffed against its committed
`results/summary.json`:

| Case                              | Wall time | Result                    |
| --------------------------------- | --------- | ------------------------- |
| A1_volumetric_baseline            | 0.8 s     | byte-identical in the canonical environment |
| A3_uncertainty_experiments        | 15 s      | byte-identical in the canonical environment |
| A4_misleading_fit_counterexample  | 12 s      | byte-identical in the canonical environment |

Figure data for the site, re-exported into a scratch directory and diffed against what
is committed under `site/src/data/figures`: seven figure files plus `contract.json`, all
byte-identical, with 51 reconciliation checks recorded by the exporter.

## What is NOT RUN in public-core, and why

The profile reports these rather than skipping them quietly. A count of zero tests run
and a count of twenty tests deliberately not run are different situations, and a report
that shows only "all green" cannot tell them apart.

**20 tests, in `tests/test_gas_properties.py`.** These compare computed deviation
factors, densities and viscosities against the NIST Chemistry WebBook reference tables.
The three tab-separated extracts are absent from the public tree on purpose: they are
someone else's data, and access to them is not the same as the right to redistribute
them. `tests/oracles/nist.py` skips these tests with a reason that names the missing
directory. Run them with the external-reference profile and your own copy.

The number 20 is measured, not asserted. `verify.py` counts skips whose reason carries
the reference-absent sentinel and reports what it counted; any skip that the reference
policy does not explain is an unexpected skip and fails the run. The `20` passed to
`--expect-reference-skips` in CI is a drift alarm on top of that measurement, not the
source of it: it catches the case where tests were quietly added or removed.

**`cases/A2_pvt_independent_check`.** The one case study that reads the reference tables
directly. It declares them as run inputs and exits non-zero when they are absent, which
is the correct behaviour and not a defect. It ships no committed `results/summary.json`,
which is how `verify.py` and CI tell it apart from the reproducible cases without either
of them carrying a hard-coded list.

**Digest verification of the three reference tables.** Their required sha256 values are
recorded in `data/reference/MANIFEST.json`. Hashing a file the tree is supposed to not
have would fail by design and would tell a reader nothing, so the public reference
check validates the manifest as a provenance record instead: required fields present, a
citation obligation recorded, a well-formed 64-character digest declared per table. The
digests themselves are checked by the external-reference profile against the operator's
own copy.

## Runner parity

`pyproject.toml` declares `[tool.pytest.ini_options] filterwarnings`, and pytest is the
only runner that reads that file. That made `scripts/check.py`, the standard-library
runner the README offers to people who do not want to install anything, the weaker of
the two gates. A test that evaluated a correlation outside its published validity window
emitted a `RangeWarning`, passed under `check.py`, and failed under pytest.

Demonstrated concretely, before the fix, on a test that calls Standing's pseudocritical
correlation at a gas gravity of 2.1 when the published window ends at 1.10:

| Runner                        | Exit | Verdict |
| ----------------------------- | ---- | ------- |
| `scripts/check.py`, before    | 0    | PASS    |
| `python3 -m pytest`           | 1    | FAILED  |
| `scripts/check.py`, after     | 1    | FAIL    |

`check.py` now reads the same `filterwarnings` list out of `pyproject.toml` and installs
it before collection, then reinstalls it inside a fresh warning context around every
individual test, which is what pytest does per test item. The list is the single source
of truth; the policy is not restated anywhere.

The policy is scoped to `RangeWarning` and nothing else. Promoting every warning
category would make the suite fail on things the code under test is not responsible for,
and the usual response to that is a blanket ignore, which is worse than no policy at
all. Widening it is a decision to take in `pyproject.toml`, where both runners see it.

`tests/test_runner_policy.py` is the regression probe. It checks the ambient policy
under whichever runner is executing it, probes `check.py`'s wiring directly with
deliberately hostile ambient filters so that it goes red even when pytest is doing the
running, and pins the scoping decision. It was shown red with the policy removed and
green with it present, in a throwaway copy outside the repository.

## Type checking scope

`mypy` covers `src/reservoir_lab` only. That is what `[tool.mypy] files` declares in
`pyproject.toml`, it is what the pre-push hook and the CI job run, and it is stated here
so that a green type check is not read as "the repository is typed". `tests/`,
`scripts/` and `cases/` are not type checked at all.

`mypy` was not run for the measurements in this document. It is not installed in the
environment they were taken in, so the pre-push hook reports it as a failing check with
exit 127 and names the tool. There is no type-check result to report, and rather than
omit that, it is recorded here as not run.

## Hooks are local and bypassable

`.pre-commit-config.yaml` declares local hooks only. Nothing in it downloads a hook
repository and nothing in it reaches the network, so what runs on a developer's machine
is code that is reviewable in this repository.

    pre-commit install --hook-type pre-commit --hook-type pre-push

At pre-commit: repository hygiene, the published-tree data policy, the reference
manifest schema, ruff lint and ruff format. Under two seconds in total, because a hook
that is slow is a hook that gets bypassed.

At pre-push: the public-core profile with one case reproduction (`--cases fast`, about
ten seconds) and the type check. A3 and A4 take fifteen and twelve seconds and are left
to CI, which runs all three.

None of this is a control. `git commit --no-verify` skips the first set,
`git push --no-verify` skips the second, and a contributor who never ran
`pre-commit install` never had either. Hooks exist to give fast feedback to someone who
wants it. That is why `.github/workflows/ci.yml` repeats every mandatory check rather
than trusting that the hooks ran: the hook is a convenience, the pipeline is the gate.

The hooks in this checkout were installed by hand into `.git/hooks/`, because
`pre-commit` itself is not present in this environment. They delegate to
`scripts/verify.py --hook-stage <stage>`, which prefers the `pre-commit` tool when it is
on PATH and otherwise reads the same configuration file directly, so a stage does one
thing regardless of what is installed. `.git/hooks/` is not version controlled; anyone
cloning this repository installs their own.

Both were fired to confirm they work. The pre-commit hook ran all five of its hooks and
exited 1, reporting which three failed; the pre-push hook ran the public-core profile to
PASS and then failed the type check for the missing-tool reason above. A hook stage that
finds nothing to run is treated as a failure, not a pass.

## Prerequisites

`scripts/check_public_release.py` is the gate that decides what may appear in a
published tree: restricted extracts, absolute local paths, machine-local identifiers,
oversized payloads. It is a prerequisite rather than part of the verification verdict,
because it answers a different question. "May this tree be published" is about what
files may leave the machine; "is this code verified" is about whether the numbers are
right. Conflating them means a documentation path that quotes a local directory turns
into a numerical failure, and a reader cannot tell which one happened.

`verify.py` runs it and reports its result prominently, but does not let it change the
profile's verdict. CI keeps the hard version: the `source-policy` job runs the same
script and every verification job depends on it, so a policy failure stops the pipeline.

At the time of writing that gate reports failures, all of them in files owned by other
work in progress, none in the files this document covers.

## Hosted CI status: run, and the first one failed

Hosted execution has now happened, so the sentence that used to stand here -- that
nothing had ever run -- is withdrawn rather than quietly edited away.

### Run 34852530864, attempt 1, commit `d2ef03316c6a3678af5fcd527e752ca86b4e4880`

The first hosted verification of this repository, triggered by the push of
`release/rc-close` on 2026-09-14. Runner `ubuntu-24.04` (image 20260907.300, Ubuntu
24.04.5 LTS), CPython 3.13.15.

| job | conclusion |
| --- | --- |
| source and data policy | passed |
| public-core (stdlib runner, py3.11 / py3.12 / py3.13) | passed |
| public-core (pytest runner) | passed |
| **synthetic case reproduction** | **failed** |
| figure export and contract | skipped, because its dependency failed |
| plan the base matrix | skipped |
| site build and browser QA | skipped |

The failure was not a regression and not a defect. `synthetic case reproduction` re-runs
each case and compares the result with its committed snapshot using `diff`, which allows
no tolerance. The committed snapshots were produced on macOS arm64; the runner is Linux
x86_64. A1 reproduced byte for byte. A3 and A4 did not, differing in their last few
significant figures.

Two things about that failure are worth recording, because they decide what kind of
problem it is. First, every case's own scientific acceptance criteria **passed** in the
failing run: A3 reported 9 of 9 met and A4 10 of 10, the same as on macOS, and `run.py`
exited zero for both. Only the byte comparison failed. Second, the divergence is ordinary
floating-point portability: 24 libm functions were measured to differ between the two
platforms by 1 to 4 units in the last place, while `math.fsum` and the Mersenne Twister
integer stream are bit-identical, which rules out summation order, seeding and draw
order.

The run is left in the record. A gate that fails when the thing it tests is untrue is
working, and deleting the evidence of it working would be the wrong kind of tidy.
`docs/release/CANONICAL_SNAPSHOT_MIGRATION.md` carries the measurements and what follows
from them.

Every other number in this document was produced by running the same commands locally by
hand.

`ci.yml` is written so that the cases are executed rather than linted: a job that only
ran `ruff check cases/` would go green on a case study that no longer reproduces its own
published numbers. Its graph is source and data policy, then the public-core suite
across a Python matrix and the synthetic reproductions, then the figure export and its
contract, then a placeholder for the site build that another stream owns. Tool
installation is driven by `requirements-dev.lock`; the job refuses to run if that file
is missing or contains anything that is not an exact `==` pin, rather than falling back
to an unpinned install.

The declared Python matrix is 3.11, 3.12 and 3.13, matching `requires-python` and the
classifiers in `pyproject.toml`, and it has now run. All three execute the suite on the
hosted runner, and all three re-run the case studies in the portability job. "Supported"
is demonstrated rather than declared.

`pages.yml` is configured and deliberately inert. Its only trigger is
`workflow_dispatch`, it requires repository configuration variables that do not exist,
it requires a typed human acknowledgement, its build step is an unimplemented
placeholder that fails rather than uploading an empty directory, and it uploads
`site/dist` and nothing else. Read-only permissions at the workflow level; only the
deploy job is granted `pages: write` and `id-token: write`. No account name, repository
name or domain is invented anywhere in it.

### Run 34873212118, attempt 1, commit `6f212ea96192716f2109e7f99d4cbe1e7a139b31`

Green. Fourteen jobs, no skips among the required ones. 2026-09-14T17:11:18Z to
17:21:42Z.

**Canonical reproduction.** Inside `python@sha256:4165118ed569aff9dbd11d5518199e5379d93bf5bf1cdda62eb13593cf66fb68`
(`python:3.13.2-bookworm`, Debian GNU/Linux 12, GNU libc 2.36-9+deb12u10, x86_64,
CPython 3.13.2 built with GCC 12.2.0): **A1, A3 and A4 each reproduce their committed
snapshot byte for byte**, 3 of 3. A2 is an explained not-run, because it reads the
reference extract and ships no snapshot. The comparison is `diff`, with no tolerance.

**Portability.** The same cases re-run from scratch outside that container, judged on
each case's own acceptance criteria and on the semantic comparator rather than on bytes:

| environment | A1 | A3 | A4 | worst relative difference |
| --- | --- | --- | --- | --- |
| ubuntu-24.04, CPython 3.11 | pass | pass | pass | 0.0 (byte-identical) |
| ubuntu-24.04, CPython 3.12 | pass | pass | pass | 0.0 (byte-identical) |
| ubuntu-24.04, CPython 3.13 | pass | pass | pass | 0.0 (byte-identical) |
| macos-15, arm64, CPython 3.13 | pass | pass | pass | 2.374603e-08 |

The largest difference anywhere was `2.374603e-08` on A4's
`timestep_refinement.J_60.error_span_over_refinement`, and `1.657421e-08` on A3's
`results.E7_ranking.short_depletion_penalty_f010_over_f050`. Both sit inside the declared
envelope of 1e-7, which was chosen from measurement and not from what would pass; the
basis is in `docs/release/portability_envelope.json`.

**Counts, measured in that run.** 707 tests collected, 687 passed, 0 failed, 20 skipped,
across CPython 3.11, 3.12 and 3.13 on the stdlib runner and again under pytest. 9 of 9
checks. Browser QA 487 passed, 0 failed, 2 skipped on each of the two base paths, across
Chromium, Firefox and WebKit, with the skip policy clean on both. Built-site fingerprints:
`901780340dc2bf831f17237c749fe9cedf271078c56ad24936da974a3504612d` at the root base and
`56f51e5a4c22bc74424ab05724d4d361e90100e61172deae7f727ab05fca0688` at the project base,
81 files each.

**What it took to get there.** Four bounded corrections between the failed run and this
one, none of them scientific: the figure export moved into the canonical container for
the same reason the snapshots did; `ldd --version | head -1` was replaced because `head`
closing the pipe gave the step SIGPIPE and an intermittent exit 141; the published
figures were re-rendered on the Linux toolchain, since rasterisation depends on the
platform's font stack; and the explorer legend was given `max-width: 100%` after three
engines agreed it forced a horizontal scrollbar at 200 percent text on a 320px viewport.
That last one is a real accessibility defect that predates this work and had never been
caught, because the browser job had never run before -- the pipeline had always stopped
at the case reproduction above it.

## What has not been verified

- No comparison against field measurements, production data, or a commercial simulator.
  Every case study in `cases/` is synthetic, with a generator and an estimator that are
  separate modules, and each one says so in its own report.
- No external reference comparison in the public tree. The 20 tests that would do it are
  not run here, for the reason given above.
- No human peer review. Nobody outside this repository has read the derivations.
- No hosted CI run, no deployment, no published site.
- No type check in the measurements above.
- The dependency lock was resolved on macOS/arm64 and carries no hashes, so
  `pip install --require-hashes` is not possible and a Linux runner may need a wheel the
  lock does not name. CI installs with `--no-deps` and then runs `pip check`, so an
  incomplete set fails loudly there rather than resolving itself quietly.

## Reproducing any of this

    # everything a public clone can check, about forty seconds
    python3 scripts/verify.py --profile public-core --cases all

    # the fast subset the pre-push hook runs, about ten seconds
    python3 scripts/verify.py --profile public-core --cases fast

    # structural policy only, no tests, about one second
    python3 scripts/verify.py --profile public-core --policy-only

    # the suite alone, under either runner
    python3 scripts/check.py
    python3 -m pytest -q

    # a machine-readable report
    python3 scripts/verify.py --profile public-core --json verification-report.json

Neither profile reaches the network at any point.

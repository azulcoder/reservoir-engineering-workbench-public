# Gas Reservoir Performance Lab

Python tools and reproducible case studies for gas-reservoir material balance,
gas-property calculations, and gas-in-place interpretation. The published case studies use
synthetic histories to compare estimates with known inputs and examine the limits of common
assumptions.

The studies have not been validated against field data. Methods, assumptions and results
accompany each published case, and the commands that reproduce them are in
[Running it](#running-it) below.

Every number below was measured on one machine with CPython 3.13.2 on macOS (arm64) — the
case results on 2026-09-13, the test and check counts re-measured on 2026-09-14. The
commands that produced them are given so that a reader can disagree by running them.
Hosted-execution and deployment status is recorded, with the run it describes, in
[docs/release/VERIFICATION.md](docs/release/VERIFICATION.md) and
[docs/release/FIRST_PUBLICATION.md](docs/release/FIRST_PUBLICATION.md).

## The finding that matters most

Case A4 asks what a volumetric p/Z fit does when the reservoir it is fitted to is not
volumetric. The generator is a reservoir tank coupled to a Fetkovich aquifer, solved
implicitly at every step; the estimator is a constant-pore-volume inventory balance with
no influx term. They are separate modules and share no fitting code, so what the case
measures is a model-structure error rather than the same algebra applied twice.

At the declared base case — aquifer productivity index J = 2.0 bbl/day/psi, which lets
water occupy 11.3 percent of the hydrocarbon pore volume over twelve years — the fit to 49
quarterly **noise-free** observations returns:

| Quantity | Value |
|---|---|
| R-squared | 0.999859 |
| Gas in place, fitted | 112.503 Bscf |
| Gas in place, true | 100.000 Bscf |
| Error | +12.503 percent |
| Standard error the same fit reports on G | 1.496e8 scf, 0.13 percent of the estimate |
| Bias, in units of that standard error | 83.6 |

The fitted interval does not contain the truth and could not, because the interval is
computed inside the wrong model. Across the seven aquifer strengths in the sweep the bias
runs from **49.6 to 88.1 times** the fit's own standard error, so a narrower confidence
interval would not help; it would make the answer more confidently wrong.

The effect does not go away when the aquifer gets strong enough to be obvious. At the
strongest aquifer tested, J = 60 bbl/day/psi, gas in place is **+74.01 percent** too high
and R-squared is still **0.995207**, which still looks like a good straight line. Only the two strongest cases in the sweep fall below R-squared 0.999 at all.

The straight-line fit is not useless, and the case ships the control that shows it: with
no aquifer the same estimator recovers the inventory to a relative error of -9.6e-14,
which is rounding. What the fit stops doing, once any meaningful influx is present, is
carrying the information people read from it. The x-intercept stops being gas in place,
and the fit statistic stops warning them.

This effect is documented in the literature and the study claims no priority. What the
study adds is the attack on it: a written protocol, a bitwise reduction to the volumetric
limit, a timestep-refinement check, an estimator-free influx oracle, a matched pair of
detector controls, and a measured power curve for the detectability question — which is
the weaker half of the case and says so. Full report:
`cases/A4_misleading_fit_counterexample/report.md`.

Read `G` and `G - G_p` throughout this repository as **inventory in place**. Recoverable
gas is smaller by whatever the drive mechanism and the abandonment condition leave behind,
and reserves are a further commercial and regulatory classification of a recoverable
volume. Nothing here is a recoverable volume or a reserve.

## Status, stage by stage

`PLAN.md` section 2 lays out six stages. This is where each one actually stands.

| Stage | Subject | State |
|---|---|---|
| A | Gas properties and volumetric material balance | **Delivered as 0.2.** Three case studies with committed results that re-run byte-identical; a fourth is blocked in the public profile |
| B | Gas-well pressure transients | **Protocol written, no study executed.** The library ships the diagnostics primitives the protocol lists as available today; there is no Stage B run, result or exhibit |
| C | Public simulation benchmark (SPE1, SPE3) | **Not started.** No deck acquired, no simulator installed, nothing run |
| D | Mature-gas decision study | **Not started**, and not scoped beyond a heading |
| E | Real-field data extension (Volve, Norne) | **Not started.** No dataset acquired; the rights review that would have to come first has not been done |
| F | Geomechanics extension | **Not started** |

Stage A in detail:

| Case | What it establishes | State |
|---|---|---|
| A1 volumetric baseline | The p/Z inverse recovers gas in place to the precision the arithmetic allows on noise-free volumetric data: exactly zero relative error at constant Z, +5.4e-14 with a pressure-dependent deviation factor. Its own diagnostic D1 narrows that: a uniform multiplicative error in the ordinate — a wrong standard-volume basis included — leaves the recovered G exactly unchanged, so the exact recovery is evidence only against the defect classes D1 can see | Runs, reproduces byte-identical |
| A3 uncertainty experiments | An ordinate-side measurement error budget on a synthetic closed tank. Its headline ranking is explicitly **not robust**: a pre-registered inconclusive condition triggered and is reported as inconclusive. What does survive is the structure — a shared calibration bias does not shrink with more surveys while random scatter does, and the *level* of Z is irrelevant to G while its *shape* across the window moves G roughly one for one | Runs, reproduces byte-identical |
| A4 misleading fit counterexample | The finding above | Runs, reproduces byte-identical |
| A2 independent PVT check | The only study that compares this library against values it did not produce | **Blocked in this tree.** Its inputs are not redistributed; `run.py` ships and exits 1 when they are absent, and its protocol, report and results are excluded |

Stage B's protocol is `docs/protocols/stage_b_pta_protocol.md`. A protocol is a design
document. It is not evidence that the study works, that the capability exists, or that the
stage is under way, and it must not be read as any of those.

## Verification

Verification runs at one of two depths, and the difference is the difference between "this
code agrees with itself" and "this code agrees with something it did not produce".

**public-core** is everything a clone of this tree can run, with no restricted files and no
network. It covers the numerical core, the analytic and closed-form identities, the
dependency policy, and the three synthetic cases, which it re-runs from scratch and
compares against their committed snapshots byte for byte. It is a self-consistency and
reproducibility result. It is not external validation, and nothing here should describe it
as validated, benchmarked against reality, or field-proven.

**external-reference** is an opt-in for a reader who has obtained the NIST Chemistry
WebBook extract themselves. It requires both a reference directory and a recorded
statement of the basis on which the data were obtained, and it fails clearly without
either. It is the only profile that compares the library against values it did not
produce, and nobody has run it against this tree.

Measured on 2026-09-14, `python3 scripts/verify.py --profile public-core --cases all`:

| Quantity | Measured |
|---|---|
| checks collected / passed / mandatory failed | 9 / 9 / 0 |
| tests collected | 683 |
| tests passed | 663 |
| tests failed or errored | 0 |
| tests skipped | 20 |
| reference-dependent tests, not run | 20 |
| reference-dependent checks, not run | 2 |
| synthetic cases reproduced byte-identical | 3 of 3 |

The two runners report the same suite differently: `python3 scripts/check.py` prints "683
run, 0 failed, 20 skipped" because `unittest` counts a skipped test in `testsRun`, and
`python3 -m pytest -q` prints "663 passed, 20 skipped" because pytest does not. 683 minus
20 is 663.

Adding `--expect-reference-skips 20` registers one further check,
`reference-skip-count-drift`, so the same tree reports 10 checks under that flag and 9
without it. `scripts/build_release.py` runs the unflagged form and fails the build if the
numbers published on the site disagree with the run it just performed.

The collected count was 641 on 2026-09-13. The 26 added tests are
`tests/test_skip_policy.py`, which exercises the browser suite's skip gate; see the
changelog. The 20 skips did not move, because they are the data decision below and nothing
about it changed.

### The 20 skips are the data decision, not a gap in the suite

All 20 are in `tests/test_gas_properties.py`, and all 20 compare computed deviation
factors, densities and viscosities against the NIST reference tables. Those tables are not
in this repository, so the tests cannot run here. No test is deleted, relaxed or stubbed,
and the skip reason names the missing directory.

The count is measured rather than asserted. `verify.py` counts skips carrying the
reference-absent sentinel and reports what it counted; a skip the reference policy does
not explain is an unexpected skip and fails the run. Passing `--expect-reference-skips 20`
adds a drift alarm on top of that measurement, so that tests quietly added or removed are
caught.

A profile that reports "20 tests deliberately not run" and a profile that reports "all
green" are telling you different things. This one is built to keep them distinguishable.

Full record, including what is not verified and how each figure was produced:
`docs/release/VERIFICATION.md`.

## Data rights: why part of the evidence is missing

This project does not redistribute the NIST Chemistry WebBook extract it uses as an
independent PVT oracle. NIST Standard Reference Data is a statutory exception to the usual
rule that works of the United States Government are in the public domain — the Standard
Reference Data Act (Public Law 90-396) lets the Secretary of Commerce assert copyright in
SRD, and the WebBook asserts it. The evidence retrieved for this project does not
establish that citation alone permits redistributing an extract. Attribution and
redistribution are different permissions, in the same way that access and redistribution
are different permissions.

That is a conservative publication decision, not an adjudication of copyright exceptions
and not legal advice. A defensible argument for 450 rows of thermophysical values used as
a test oracle may well exist; this repository is the wrong place to test it. The cost of
the decision is 20 skipped tests and one case study that cannot run, and stating that
plainly is better than a stub that pretends the oracle ran.

What is published instead is metadata: `data/reference/MANIFEST.json` records the exact
request URLs, declared units, isotherms, pressure grid, row counts, per-property citations
and a SHA-256 digest of each table. Nothing derived from the values is published in any
format — a digest is not data, a citation is not data, a column name is not data, and a
retrieved value is data in whatever format it is wearing.

The decision is about redistribution and says nothing against you retrieving the values
yourself:

```
python3 scripts/fetch_nist_reference.py plan
python3 scripts/fetch_nist_reference.py acquire \
    --out /path/outside/this/checkout \
    --access-basis "your own recorded basis"
python3 scripts/fetch_nist_reference.py verify --out /path/outside/this/checkout
```

`plan` prints the requests and makes none. `acquire` refuses to run in any automated
context and writes an `ACQUISITION_RECORD.json` holding the basis you stated, verbatim, so
that it can be reviewed. The script records that basis; it does not verify it, and nothing
it writes is permission from NIST. With the extract in hand, run the external-reference
profile. Cite the WebBook and the per-species reference equation wherever these values, or
results derived from them, are reported.

The full decision and its evidence: `docs/release/PUBLIC_DATA_POLICY.md`.

## Running it

The library is pure Python with no runtime dependencies and requires Python 3.11 or newer.
Only CPython 3.13.2 on macOS has actually been exercised; the other declared versions are
declared, not demonstrated.

Nothing below reaches the network.

```bash
# everything a public clone can check, about forty seconds
python3 scripts/verify.py --profile public-core --cases all

# the fast subset the pre-push hook runs, about ten seconds
python3 scripts/verify.py --profile public-core --cases fast

# structural policy only, no tests, about one second
python3 scripts/verify.py --profile public-core --policy-only

# a machine-readable report
python3 scripts/verify.py --profile public-core --json verification-report.json
```

The suite alone, under either runner. `check.py` needs nothing but the standard library;
pytest needs the `dev` extra:

```bash
python3 scripts/check.py
python3 -m pytest -q
```

Re-run a case study into a fresh directory and compare it against the committed snapshot.
Each case writes an immutable run directory and refuses to overwrite one:

```bash
PYTHONPATH=src python3 cases/A1_volumetric_baseline/run.py --out artifacts/A1_volumetric_baseline/run-local
PYTHONPATH=src python3 cases/A3_uncertainty_experiments/run.py --out artifacts/A3_uncertainty_experiments/run-local
PYTHONPATH=src python3 cases/A4_misleading_fit_counterexample/run.py --out artifacts/A4_misleading_fit_counterexample/run-local
```

`cases/A2_pvt_independent_check/run.py` exits 1 in this tree and says the reference table
is absent. That is the correct behaviour, not a defect.

Re-export the figure data the site renders, from the audited case code, with every
recomputed quantity reconciled against the audited summary before anything is written:

```bash
PYTHONPATH=src python3 scripts/export_presentation_data.py --out artifacts/export/run-local
```

Check what may appear in a published tree — restricted extracts, absolute local paths,
machine-local identifiers, oversized payloads — across both the working tree and the whole
of git history:

```bash
python3 scripts/check_public_release.py --verbose
```

Install the local hooks if you want fast feedback. They are local hooks only: nothing
downloads a hook repository and nothing reaches the network.

```bash
pre-commit install --hook-type pre-commit --hook-type pre-push
```

Hooks are a convenience, not a control — `--no-verify` skips them and a contributor who
never installed them never had them.

The website that presents the studies lives in `site/` and is built separately; see
`site/README.md`. It is a static build with no deployment configuration set.

## What this repository does not establish

Listed rather than omitted, so that the absence is visibly deliberate.

- **No field data.** Every case is synthetic, with a generator and an estimator in
  separate modules, and each case says so in its own report.
- **No simulator has been run.** No SPE1, no SPE3, no OPM Flow, no commercial package. No
  experience with any commercial reservoir simulator is claimed; reading or writing a
  shared input format would not be evidence of it, and none is offered.
- **No external validation of the library.** The one study that compares it against values
  it did not produce cannot run here, for the data-rights reason above.
- **No hosted continuous integration behind the numbers above.** Every measurement in
  this README was produced locally, on one machine. Whether `.github/workflows/ci.yml` and
  `pages.yml` have executed on a hosted runner, and for which revision, is recorded in
  [docs/release/VERIFICATION.md](docs/release/VERIFICATION.md) rather than asserted here.
  No build badge is shown for a run that is not reported there.
- **No deployment.** No site has been published. `pages.yml` is deliberately inert: one
  `workflow_dispatch` trigger, configuration variables that do not exist, a typed human
  acknowledgement, and a build step that fails rather than uploading an empty directory.
- **No human peer review.** Every review pass in this project's history — the numerical
  pass, the interpretation pass, the claims audit — was conducted under a different role by
  the same author. Different role names do not create independent expertise or independent
  evidence, and separate automated passes are not peer review.
- **No type check in the measurements above.** `mypy` is not installed in the environment
  they were taken in, and its declared scope is `src/reservoir_lab` only; `tests/`,
  `scripts/` and `cases/` are not type checked at all.
- **No pre-registration in the clinical sense.** There is no external registry, no
  timestamping authority and no third party. A2 and A3 pin their protocol by SHA-256 inside
  a record the run itself wrote, which is internal content linkage and not an independent
  trusted timestamp; A1 and A4 declare no inputs at all, so their ordering is unverified.
  All of it rests on the author's word, and is described as the weaker thing it is.
- **No affiliation, employer, client or institution** is named anywhere, and no endorsement
  by any data provider or software vendor is implied.
- **No third-party dataset, deck, book, paper or binary** is redistributed. Where a study
  would use one, this repository stores retrieval instructions and checksums, and the third
  party's licence governs the material.

## Relationship to the private baseline

The files here were imported from a private working repository, from a single committed
snapshot: 88 of the 98 files tracked at that commit, copied byte for byte from the
committed blobs, with 10 files deliberately excluded.

The git history starts fresh, and that is a data-rights decision rather than tidiness. The
private repository's history contains the NIST extract this project has decided not to
redistribute. Deleting those files in a *new* commit on the original history would not
help, because git keeps every earlier version and the blobs would remain reachable in any
clone. A fresh repository built from a reviewed allowlist is the only construction in which
those bytes were never present at all.

The consequence has to be said plainly: **the commit dates here are the dates this
candidate was assembled, not the dates the underlying studies were performed.** Nothing in
this repository's history is evidence about when any protocol, run or report was written,
and importing the studies did not strengthen their pre-registration status. The private
baseline is unchanged and is preserved; it is not a second active source of truth, and
forward development happens here.

`docs/release/MIGRATION.md` records the source commit, the file counts, the byte-identity
check, and what the history does and does not prove.

## Layout

```
src/reservoir_lab/   the library: gas properties, material balance, aquifer, pseudopressure,
                     diagnostics, regression, units, numerics, provenance, validation
tests/               683 tests; oracles under tests/oracles/
cases/               A1, A2, A3, A4 — protocol, run.py, report, decision memo, results
scripts/             verify.py, check.py, check_public_release.py, check_repository.py,
                     export_presentation_data.py, fetch_nist_reference.py, run_demo.py
docs/                evidence cards, protocols, design decisions, release records
data/                policy and provenance only; no values
site/                the static publication site (separate toolchain, see site/README.md)
examples/            the preserved starter demonstration
configs/             case configurations
```

Start with `PLAN.md` for what the project is trying to be,
`cases/A4_misleading_fit_counterexample/report.md` for the finding,
`docs/release/VERIFICATION.md` for what has actually been checked, and
`docs/release/CORRECTIVE_RELEASE_REPORT.md` for what a claims audit found wrong in the
prose and what is still open.

## Licence and citation

MIT, copyright 2026 azul. The licence covers original repository code and text only.
Referenced books, papers, software, datasets and trademarks retain their own licences and
notices; see `NOTICE.md`. Do not apply this repository's licence to imported material.

`pyproject.toml` declares Documentation and Source URLs. They are the intended
destination rather than a checked address: this tree has not been connected to a remote, so
those URLs have not been resolved against a live repository. They are recorded in
`CHANGELOG.md` under known issues and are corrected, against the real address, as part of
the publication sequence in `docs/release/DEPLOYMENT_RUNBOOK.md`.

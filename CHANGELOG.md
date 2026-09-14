# Changelog

This file records this repository's own history. It begins at 0.2.0, because this
repository begins at 0.2.0: it was assembled as a publication candidate from a reviewed
allowlist of files taken from a private working repository, and its git history is not a
continuation of that repository's history. `docs/release/MIGRATION.md` explains why.

**The git history in this repository starts at the clearance commit and has no parent.**
An earlier candidate carried reference-data values in files that a working-tree edit
cannot reach, because removing a value from the current files does not remove it from
the commits that introduced it. Rather than rewrite that history, this repository was
started again from the cleared snapshot. The earlier repositories still exist locally,
unchanged and unpublished; nothing here is a continuation of them, and no commit, author
record or date was altered in them to produce this. The entries below therefore describe
work that predates the first commit in this repository.

Two conventions, both of which matter for reading the entries below.

**Dates are the dates the work was done.** They are not release dates — nothing here has
been released, tagged, uploaded or deployed — and they are self-reported. This repository
has no remote, no tag and no signature, so no date in it is independently attested.

**The git history here proves nothing about the underlying studies.** The commits date the
assembly of this candidate. They do not date the protocols, the runs or the reports that
were imported into it, and importing a study did not strengthen its pre-registration
status.

Superseded statements are marked and kept, not deleted.

## Unreleased — 2026-09-14

Reference-data clearance. This release does not redistribute the NIST Standard Reference
Data extract, and the clearance removed material that reproduced it. What was removed, by
category and location — the values themselves are not restated here, since restating them
in a changelog would republish exactly what the clearance withdrew:

| Category | Where |
| --- | --- |
| Retrieved reference values embedded as a fixture | `cases/A2_pvt_independent_check/run.py` |
| A verbatim row of the extract used as a parser fixture | `tests/test_gas_properties.py` |
| Reference values, and pointwise deviations against them, quoted in prose | `docs/evidence/viscosity.md`, `docs/evidence/provenance.md` |
| Values derived pointwise from a reference input, which an invertible correlation carries back out | `docs/evidence/viscosity.md` |
| Aggregate error statistics summarising the withheld comparison | `docs/evidence/viscosity.md`, `tests/test_gas_properties.py` |
| An exemption granted on non-invertibility grounds, which contradicted the register's own rule | `docs/release/payload_exemptions.json` |

The full record, including what was kept and why a new history was started rather than
the old one rewritten, is in
[docs/release/REFERENCE_DATA_CLEARANCE.md](docs/release/REFERENCE_DATA_CLEARANCE.md).

No acceptance threshold was changed to make the clearance pass. Every gate, tolerance and
assertion bound stands at the value it had before, including the ones whose observed
margins are no longer published; a criterion relaxed to accommodate a removal would make
the remaining checks worth less than nothing. What the clearance removed is the *observed*
side of comparisons against withheld data, never the bound being tested. Published results
that are someone else's, such as a correlation's own quoted accuracy from its source
paper, are retained and still cited.

Retained, because the clearance targets the data and not the capability: the citation and
per-species reference equations, the acquisition recipe in
`scripts/fetch_nist_reference.py`, the schema and loader in `tests/oracles/nist.py`, the
digest manifest in `data/reference/MANIFEST.json`, and the external-reference verification
profile. An operator who acquires the extract under the provider's own terms can run every
withheld check locally; the public profile reports those checks as not run, with a count
measured from the suite's own skip reasons rather than asserted.

New screens, with regression tests: a derived-value probe that flags a high-precision
number standing beside a statement that it was computed from the restricted extract, and
sentinel fixtures that exercise rejection of an unmarked embedded table, of a disallowed
pointwise source/derived combination, and of a restricted input attempting to re-enter
through the package. Each is paired with a negative control, because a screen that fires
on everything is not a screen.

Deployment integration. No scientific code, case configuration, threshold, physical
assumption or committed numerical output was touched: the fourteen frozen artefacts are
byte-identical before and after, checked by `scripts/check_frozen.py`. Still not published,
not tagged, not deployed, and still never run by any continuous-integration service.

### Changed

- **One skip gate, keyed on a capability id rather than on prose.** `ci.yml` and `pages.yml`
  each carried their own inline validator matching two exact English sentences, one of which
  asserted a macOS-specific fact. The tests had already moved to capability probes whose
  descriptions began `NOT APPLICABLE in this environment: ...`, which neither matcher could
  recognise. The policy is now `site/tests/skip-policy.json`, the gate is
  `scripts/check_skip_policy.py`, and the local path and both workflows run the same file.
  A skip must name a declared id; a probe-backed skip must carry its own measurement and
  agree with the independent control-fixture probe in `measure.spec.ts`. An empty suite, an
  engine that produced nothing, an engine that produced only skips, and a check skipped on
  every engine all fail. No skip count is compared against a baseline — a capability is a
  property of the engine build and the platform, so a Linux runner may legitimately skip a
  different number than macOS does.
- **Release verification can no longer be handed a different directory.** The browser suite
  ran with `QA_REUSE=1`, which leaves `reuseExistingServer` to choose between the caller's
  server and Playwright's own by probing a URL; a server that died after the readiness check
  would hand the suite to a fallback that runs `astro build` into `site/dist`, and the
  candidate directory would still pass its after-fingerprint because nothing read it.
  `QA_RELEASE=1` now leaves the configuration with no `webServer` at all.
  `site/tests/release-mode.spec.ts` compares the bytes the browser received for the home
  page, a deep route and a published download against the candidate's files on disk, which
  is the part a fingerprint cannot establish. `scripts/check_release_mode.py` demonstrates
  the substitution happening before showing that release mode prevents it.
- **Verification runs on release branches.** `ci.yml` listened to `push` on `main` only,
  while the runbook said pushing `release/rc-close` starts verification. `push` now covers
  `main` and `release/**`. `pull_request`, `workflow_dispatch` and `workflow_call` are
  unchanged, and `pages.yml` still has `workflow_dispatch` and nothing else, so no push to
  any branch can deploy.
- **Manual publication is bound to a commit.** `pages.yml` takes a required `expected_sha`,
  validates it as a full 40-character lowercase SHA, and compares it with `github.sha`
  before any expensive step. `gh workflow run --ref` takes a branch or a tag and the commit
  is resolved server-side after the dispatch, so a ref that moves in between would otherwise
  publish something nobody reviewed. Both values reach the shell through the environment.
- **Screenshot captures are excluded from an unfiltered run.** They write seventeen fixed
  paths and the file's own header said to run them on one engine; nothing enforced it, and
  `npx playwright test` — what both workflows run — put three engines into those paths
  concurrently. Observed, not deduced: the committed Chromium captures were replaced by
  whichever engine finished last. `testIgnore` now excludes them and `QA_CAPTURES=1` opts
  them back in. They are excluded rather than skipped, because nothing in that file asserts
  and an engine-wide skip is what the skip policy exists to refuse.

### Corrected

- **`DEPLOYMENT_RUNBOOK.md` no longer gates on a superseded red result.** It said the local
  browser QA "is not green today" and quoted 401 passed / 12 failed / 13 skipped, which
  `RC_CLOSURE.md` had already superseded. The historical documents are linked, not erased.
  Its description of the WebKit keyboard skips as engine-name exclusions is replaced by what
  the suite actually does, and the empty-repository bootstrap is written down as the
  one-time exception it is rather than implied.

### Added

- `docs/release/FIRST_PUBLICATION.md`, the working record for hosted verification and
  publication: phase, source SHA, authorization state, unresolved items, and external run
  identifiers when any exist.
- `tests/test_skip_policy.py`, 26 cases covering the permitted capability skips, an unknown
  id, a bare `NOT APPLICABLE` prefix, a missing measurement, a self-contradicting
  measurement, a contradicting independent probe, an absent probe, a disallowed engine, an
  empty suite, a suite of nothing but skips, an absent engine, an engine that only skipped,
  an ordinary failure, a timeout, and a platform that legitimately skips less.

### Known issues carried forward

- ~~`pyproject.toml` names the private baseline's repository as Source and
  Documentation.~~ **Resolved.** `[project.urls]` now names the approved publication
  destination, which the owner fixed as part of authorising the first publication, so the
  URL is a decision rather than a guess. The wheel and the sdist carry the corrected
  metadata.
- `requirements-dev.lock` was resolved on macOS/arm64 and carries no hashes. The first
  Linux run may find a missing platform wheel; the fix is to regenerate the lock on Linux.

## 0.2.0 — 2026-09-13

First public candidate. Not published, not tagged, not deployed, and not run by any
continuous-integration service anywhere.

### Present

- **The library**, `src/reservoir_lab`: gas properties, material balance, aquifer models,
  pseudopressure, diagnostics, regression, units, numerics, provenance and validation.
  Pure Python, no runtime dependencies, and a test walks the import graph of every module
  to keep that claim honest.
- **Three synthetic case studies with committed results** — A1 volumetric baseline, A3
  uncertainty experiments, A4 misleading-fit counterexample — each with a protocol, a run
  script, an immutable run record, a report and, for A4, a decision memo. All three re-run
  from scratch into a fresh directory and compare byte-identical against their committed
  snapshots.
- **A fourth case, A2, that cannot run here.** Its run script ships and exits 1 when its
  reference inputs are absent.
- **641 tests**, of which 621 pass and 20 skip in this tree.
- **Evidence cards** under `docs/evidence/` for each method, recording the source, the
  access level actually obtained, the derivation or worked example, the assumptions and the
  known failure modes.
- **A written Stage B protocol**, `docs/protocols/stage_b_pta_protocol.md`, for work that
  has not been built.
- **A static publication site** under `site/`, building nine routes with no analytics, no
  cookies, no remote fonts and no external script files. Its deployment identity is unset;
  see `site/README.md`.

### Corrected, relative to the private baseline

A repository-wide claims audit read every interpretive statement in the case reports, the
decision memo and the evidence cards against the committed run output. It found that the
computational core reproduces and that a number of the sentences written around it claimed
more than the runs support. No `results/summary.json` or `results/run_record.json` was
edited, no threshold was relaxed, no number was re-rounded and no calculation was changed
to improve a claim. The full row-by-row disposition is
`docs/release/disposition_ledger.csv` (72 findings) and the narrative is
`docs/release/CORRECTIVE_RELEASE_REPORT.md`. The substantive corrections:

- **An arithmetic error in a gate comparison.** +1.26 percent was stated as inside the 1
  percent gate `PLAN.md` section 12 proposes. It is above it. Only the +0.32 percent row is
  below.
- **The borrowed gate is a project demonstration gate**, scoped by `PLAN.md:289` to the
  delivered small-noise demonstration. Clearing it is not evidence of general
  reservoir-interpretation adequacy and not evidence of development-decision adequacy.
- **Four statements are now kept apart everywhere**: numerical verification, conditional
  pressure reconstruction, physical interpretation, and decision adequacy. A1 reaches the
  first; A3 reaches the first and speaks to the second only in p/Z space; A4 reaches the
  first two. None reaches the last two.
- **Produced water is not total influx.** Cumulative produced water, its reservoir-volume
  equivalent and total influx are three quantities. In A4's own produced-water variant the
  produced record understates the influx by a factor of 3.33 and bounds it from below.
- **Inventory in place, recoverable gas and reserves are distinguished** throughout, and
  none is presented as another.
- **`fit_pz_depletion` fits two parameters, not one.** It has a free intercept and a free
  slope and `G = -a/b` is a function of both. The obstacle to adding an influx term is
  practical, noise-limited ambiguity, not structural non-identifiability: a direct
  least-squares minimisation over `(G, J)` on the committed noise-free generator returns `G`
  within 1.0e-11 relative of the truth.
- **The closed-form curvature quantity was corrected from its derivation.** `sigma*` makes
  `|c| / sd(c_hat)` equal the critical value — it is the noncentrality parameter, not
  `E[t]`. The earlier key rename substituted a second mislabel for the first. The measured
  detection frequencies are unchanged; the sub-half power is explained by a deterministic
  lack-of-fit floor, not by the mechanism previously claimed.
- **Unsupported directional claims were withdrawn**: the sign of average-pressure sampling
  bias, the direction alternative uncertainty methods would move an interval, and the
  superiority of the drift diagnostic under noise. Each is now recorded as an untested
  mechanism, not closed by inventing an experiment.
- **A reported external comparison was withdrawn.** The separately implemented tank the A4
  report leaned on is not reproducible from this repository — no script, output, digest,
  command or log for it exists here. Its quoted digits are withdrawn, and
  `artifacts/A4_misleading_fit_counterexample/referee-run/` is relabelled as what it is: a
  re-execution of the case's own `run.py`.
- **"Independent" and "external" were withdrawn from every description of a review pass.**
  All of them were conducted under a different role by the same author.
- **The A4 holdout is a conditional synthetic pressure reconstruction**, not a
  field-realisable forecast: the predictor multiplies by the deviation factor at the *true
  future pressure*. The chronological discipline is real and the calculation was not
  changed; the label was.
- **Standing 667 versus 677 [SUPERSEDED].** The private baseline's README stated the
  consequence in Z as "bounded at 0.45 percent" and its CHANGELOG as "0.13–0.23 percent".
  Neither is right, and no artefact produces the second. Recomputed from the shipped
  library over gamma 0.55 to 1.10 at 500 to 6000 psia and 200 degF with Z by
  Dranchuk-Abou-Kassem: 10 psia and 1.53 percent mean difference in pseudocritical
  pressure; in Z, 0.45 percent mean and **1.15 percent maximum**, the maximum sitting on the
  corner of the sampled domain, so it is a lower bound on the maximum over any wider range
  and not a bound on it. A mean is not a bound, and the three figures travel with their
  domain or not at all. The conflict itself is unresolved: the original Standing (1977) has
  never been read. The library ships both values as named variants and defaults to 677.

### Changed, in this candidate

- **Verification split into two profiles.** `public-core` runs without restricted inputs
  and reports what is NOT RUN with counts and reasons; `external-reference` is opt-in and
  fails without both a user-supplied reference directory and a recorded access basis.
  `scripts/verify.py` is the single entry point.
- **Both test runners now share one warning policy.** `pyproject.toml` declares
  `filterwarnings` and only pytest read it, which made `scripts/check.py` — the
  standard-library runner offered to people who do not want to install anything — the
  weaker gate. A test that evaluated a correlation outside its published validity window
  passed under `check.py` and failed under pytest. `check.py` now reads the same list and
  reinstalls it around every test; `tests/test_runner_policy.py` is the regression probe,
  and it was shown red with the policy removed.
- **`scripts/check_public_release.py` is new**, and found four classes of real problem on
  its first run: `.gitignore` re-included the excluded extract, so a dropped copy would have
  been tracked on the next `git add`; the commit-time allowlist had the same hole; three
  private sandbox paths had reached a committed evidence card; and retrieved reference
  values were quoted inline, which is the same act in a different format. All four are
  fixed. Three locations where the screen fires on unit conversions and published critical
  constants are recorded in `docs/release/payload_exemptions.json` with reasons, rather than
  by weakening the screen.
- **`scripts/export_presentation_data.py` is new.** It exports the full 49-point traces the
  site needs by calling the audited case module's own functions, reconciles 43 quantities
  against the audited summary before writing anything, and records itself as a new run. A
  one-part-in-a-billion perturbation of the baseline is refused; an unperturbed copy passes.
- **The NIST data position was reversed.** See the next section.
- **Local hooks and a CI workflow were added.** Both are written and neither has run
  anywhere but this machine.

### Excluded from the import, and why

Ten files tracked in the private baseline were not imported, and the history was started
fresh rather than rewritten so that the excluded bytes were never present at all.

- **The three NIST Chemistry WebBook isotherm tables.** NIST Standard Reference Data is
  copyrighted under a statutory exception (Public Law 90-396) and the evidence retrieved
  does not establish that citation alone permits redistributing an extract. An earlier
  revision framed the requirement as *attribution* and treated satisfying it as settling the
  question. **[SUPERSEDED]** — attribution and redistribution are different permissions.
  Citation is still required; it is simply not sufficient. Published in their place:
  request URLs, units, isotherms, grid, row counts, per-property citations and a SHA-256
  digest per table. The decision is conservative publication practice, not an adjudication
  of copyright exceptions.
- **Four `cases/A2_pvt_independent_check/` artefacts** — protocol, report and the two result
  files — because they are derived from that extract and quote its values.
- The remaining excluded files are enumerated in `docs/release/PUBLIC_DATA_POLICY.md` and
  `docs/release/DISTRIBUTION_MANIFEST.md`.

The cost of this decision is visible and is left visible: 20 tests skip rather than being
stubbed, and A2 exits 1 rather than fabricating a result.

### Not done

- No hosted CI has ever run. There is no remote, so there is nothing for a runner to check
  out, and there is no badge to display.
- No deployment. `site/` builds locally and `pages.yml` is deliberately inert.
- No human peer review, by anyone, at any point.
- No field data, no simulator run, no commercial-software work.
- Stage B is a protocol with no code behind it. Stages C, D, E and F are not started.
- `mypy` was not run for the measurements recorded in `docs/release/VERIFICATION.md`; it is
  not installed in that environment, and its declared scope is `src/reservoir_lab` only.
- The dependency lock was resolved on macOS/arm64 and carries no hashes, so
  `pip install --require-hashes` is not possible.
- The A2 case has never been executed in this tree by anyone, including its author.

### Known issues carried forward

Recorded rather than fixed, each with the file that owns it.

- `cases/A4_misleading_fit_counterexample/results/summary.json` still carries the
  mislabelled `sigma_*_at_expected_t_equals_critical_*` keys and a stale limitation string
  saying the `cases/` tree is untracked. A run record is not edited after the fact;
  correcting these costs a new run under a new run ID, which is the recommendation standing
  in `docs/release/CORRECTIVE_RELEASE_REPORT.md`.
- `cases/A4_misleading_fit_counterexample/protocol.md` carries the same stale premise and
  lacks the noise-model heteroscedasticity note.
- The 667/677 conflict is open, and neither side rests on a re-checkable retrieval: one
  text was fetched over a host with an expired TLS certificate with verification disabled,
  the other from a file-sharing aggregator with no URL, digest or date recorded.
- A4's reversal advice now rests on a single sweep row, and that row is one of the two where
  the Fetkovich pseudosteady assumption is least defensible.
- The power and size of the prefix-drift diagnostic under measurement noise are unmeasured,
  and neither the Cole nor the pot-aquifer plot has been implemented.
- A1's and A4's prospective ordering is unverifiable and was not retrofitted.
- The DAK-against-NIST percentages quoted as background in the A1, A3 and A4 reports cannot
  be reproduced from this checkout, because the extract is not here. They are attributed to
  A2 and flagged; no result depends on them.
- One numerical defect from the audit is open in `scripts/fetch_nist_reference.py`: a
  de-duplication rule keeps a stale phase label for 15 reference states.
- `pyproject.toml` declares `Documentation` and `Source` URLs pointing at a repository this
  tree has never been connected to. They are aspirational fields, not a location where this
  code can be found.
- `docs/release/PUBLIC_DATA_POLICY.md` states the suite total as 633 tests. The suite
  collects 641 as measured on 2026-09-13; the 20 skips it describes are unchanged. The
  earlier total is also quoted, correctly attributed to its date, in
  `docs/design/decisions.md` and `docs/design/figure_spec.md`.

## Before this candidate

Not part of this repository's history, and listed only so that a reader knows the work did
not start at 0.2.0.

- **0.2 — PVT and material-balance study**, in the private baseline: the Stage A cases,
  their protocols, reports and decision memo. Its execution record, including the
  environment and the commands, is `docs/baseline_execution.md`.
- **0.1 — verified foundation**, the starter: calculation primitives, unit, workflow and
  repository tests, a synthetic self-consistency demonstration, the data policy and the
  role briefs. Its claims were reproduced before its code was reused — 38 tests, a
  0.149256357527916 percent gas-in-place error, a byte-identical demonstration output — and
  that check is recorded in `docs/merge_decision.md`.

Neither was published.

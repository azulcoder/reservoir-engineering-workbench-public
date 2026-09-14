# First hosted verification and controlled publication

The working record for taking this candidate from "verified locally" to "verified on a
hosted runner and published". One file, updated in place as each phase completes, so that
a session picking this up after a break reads the repository rather than a terminal recap.

Bulky logs and throwaway output live in `.release-work/`, which is ignored.

---

## Current phase

**PHASE 3 — CONTENT CORRECTIONS APPLIED. PUBLICATION BLOCKED ON A VERIFIED
RESTRICTED-DATA FINDING. AWAITING OWNER DECISION.**

The public-facing copy has been corrected and the candidate passes every local release
gate. It must not be published in its present form: three verified locations redistribute
values from the NIST reference extract, in the tree and in the history that would be
pushed. See **Restricted-data blocker** below. This is an owner decision, not an
editorial one, because the values sit in the branch's first commit and no working-tree
edit removes them from what a push would publish.

Nothing has left this machine. No remote exists, nothing has been pushed, no repository
has been created, no Pages site has been provisioned, and no URL exists to check.

## Authorization state

| question | state |
| --- | --- |
| GitHub CLI authenticated | yes, `azulcoder` on github.com, scopes `repo`, `workflow`, `read:org`, `gist`, `delete_repo` |
| owner confirmed for this publication | **not yet asked** |
| public source repository approved | **no** |
| public Pages site approved | **no** |
| target repository exists | no — `azulcoder/reservoir-engineering-workbench-public` returns 404 |

Authentication is identity evidence. It is not consent to publish, and nothing in this
record may be read as turning "pending" into "approved".

## Source revisions

| what | SHA |
| --- | --- |
| candidate at the start of this task | `ef308cc94294a74a0798f2517ff63078d3f4f814` |
| revision the closure report's browser runs used | `62185ec8b23c0c4f209fa4dc25faec5384862b35` |
| revision this task's integration fixes were tested at | `7ea73a29ef0787ffb74953b2224138be0c3bd723` |
| uploaded | — |
| hosted-verified | — |
| deployed | — |

`ef308cc` differs from `62185ec` only in `.gitignore`, four documents under `docs/release/`,
and regenerated screenshots and evidence. `git diff --name-status 62185ec ef308cc` lists no
file under `site/src`, `site/tests`, `scripts/`, `src/`, `tests/` or `.github/`, so the
browser and build results recorded in RC_CLOSURE.md describe the application source that
`ef308cc` carries. That is a checked statement, not an inherited one.

The `release_status.json` capture was taken from a dirty tree and says so. What was dirty
was documentation and screenshots; no build-affecting source was uncommitted. The historical
record is left as written — a capture that says it was dirty is more useful than one
retroactively tidied.

## Reconciling the browser count

The reported starting state was 466 passed / 0 failed / 14 skipped. This task's run of the
same suite reports a different number, and the difference is explained rather than adopted.

| quantity | value | how it was established |
| --- | --- | --- |
| collected at `62185ec` | 501 | `npx playwright test --list` against a clean export of that commit |
| collected at `ef308cc` | 501 | the same, and `git diff 62185ec ef308cc -- site/tests site/playwright.config.ts` is empty |
| historical headline | 466 + 14 = 480 | `docs/release/evidence/logs/browser-project.log` |
| unaccounted for | 21 | 501 - 480 |

The 21 are `tests/screenshots.spec.ts`: 7 captures x 3 engines. That file does not appear
anywhere in the historical browser log, which covers 13 spec files, not 14. It was run as
its own invocation, on Chromium only, and `evidence/logs/screenshots.log` records that
separately: 7 passed. So the historical figure was the suite minus the captures, and the
captures were 7 of a possible 21.

**A defect found while reconciling this.** The captures write fixed paths --
`screenshots/home-1440.png` and sixteen more. The file's own header says it must be run on
one engine "so the file names mean one thing", and nothing enforced that. An unfiltered
`npx playwright test` -- which is exactly what both workflows run -- put three engines into
those seventeen paths concurrently. It is not hypothetical: it happened here, the committed
Chromium captures were replaced by whichever engine finished last, and two stray
`INVENTORY-*.json` files appeared. The captures were restored with
`git checkout -- site/screenshots/`.

Fixed in `playwright.config.ts` with `testIgnore`, so an unfiltered run excludes the
captures and `QA_CAPTURES=1` opts them back in. They are excluded, not skipped: a skip is a
check that could not be made, and nothing in that file asserts on image bytes, so declaring
an engine-wide skip for them would be the "we stopped measuring on this engine" that the
skip policy exists to refuse.

That gives the count for this task:

    489 collected  =  501  -  21 captures  +  9 release-mode identity checks

## Verification of this task's changes

Run on 2026-09-14 against `7ea73a29ef0787ffb74953b2224138be0c3bd723`, working tree clean
(`git status --porcelain` returned 0 lines, recorded by the run itself).

| check | result |
| --- | --- |
| `python3 scripts/check.py` | 667 run, 0 failed, 20 skipped; hygiene 0 errors, 0 warnings |
| `python3 scripts/verify.py --profile public-core --cases all --expect-reference-skips 20` | 10/10 checks, 667 collected, 647 passed, 20 skipped |
| `build_release.py` at the project base, `--verify-cases all` | 10/10 steps |
| `build_release.py` at the root base, `--verify-cases fast` | 10/10 steps |
| browser suite, release mode, project base | **475 passed, 0 failed, 14 skipped** |
| browser suite, release mode, root base | **475 passed, 0 failed, 14 skipped** — identical |
| `check_skip_policy.py` on both JSON reports | clean |
| `check_release_mode.py` | substitution demonstrated, then caught; wrong base refused |
| `drills_release.py` | 10 cases, 10 caught |
| `check_frozen.py` | 14 artefacts, 0 moved |
| `npm run check` | 0 errors, 0 warnings, 0 hints |
| `actionlint` 1.7.7 on both workflows | clean (without shellcheck; see limitations) |

The skips are the same on both bases and are reported by capability rather than by count:

    chromium   executed 163  skipped  0
    firefox    executed 162  skipped  1     print-to-pdf
    webkit     executed 150  skipped 13     print-to-pdf 1, keyboard-scroll-overflow 1,
                                            tab-order-includes-links 11

The control-fixture probes agree with every one of them: both capabilities measured
available on Chromium and Firefox, both unavailable on WebKit, in this run.

Retained, and ignored by git for the same reason `evidence/logs/` is — per-run output,
1.2 MB, regenerated by the next run:

| file under `docs/release/evidence/browser/` | sha256 |
| --- | --- |
| `report-project.json` | `9333fd6aff3e571934f45e74b804a380cb4b0eff75ca9c65c7f03a931989d377` |
| `report-root.json` | `dd5a89cdfe7b5b7d0398b62a9149a5603732e8efb7278278843ab889b544b124` |
| `skip-policy-project.json` | `c7b8ea65087ce47c31f62455b516a2c2a5914ecba1c9c86aa67a4c18c1e6e6a2` |
| `skip-policy-root.json` | `945e8594e0c299d9e653f27d68dc914e258fab8be3093b01d527b382d79f078d` |

## Editorial pass, 2026-09-14

A bounded pass over what would actually be published, before authorization. No reservoir
equation, case configuration, input, threshold, chart datum or conclusion was touched; the
fourteen frozen artefacts are unmoved and no generated figure was edited by hand.

### Attribution

Zero optional assistant or provider attribution, in the tree and in the history. The
search covered every generation-assistant and vendor name that `scripts/check_repository.py`
refuses, plus co-author trailers and generated-by lines, across every tracked file, every
commit message, and every added line in the full history. The only matches in tracked files
are the **detection patterns themselves**, in `scripts/check_repository.py` and
`scripts/check_public_release.py` — the gate that refuses such attribution — and removing
them would remove the gate. The names are deliberately not written out here: this document
is published, and that gate refuses a vendor name in a tracked file. It fired on the first
draft of this very paragraph, which is the second time in this task it has caught the
author writing something into a published file that should not be there. The built HTML carries no
generator meta tag and no comments; the only `astro` strings in it are `data-astro-cid-*`
scoping attributes, which are a build mechanism and not branding.

Two things that did read as production artefacts were changed:

* `docs/evidence/aquifer.md` addressed a second person — "the spec I was handed", "the
  recursion ... that you wrote", "exactly the class of error you anticipated". Rewritten to
  name the draft specification instead. Every technical claim is untouched, including the
  `Wei = ct*Wi*pi` correction and the pywaterflood transcription bug.
* "recalled from training" appeared 41 times across six evidence cards as a provenance
  value. It describes a language model's knowledge, which is not what a reader of a
  reservoir-engineering evidence card should have to parse. Replaced with "stated from
  prior knowledge". The distinction it draws — stated from prior knowledge versus read off
  a retrieved source — is the honest part and is preserved exactly; nothing became a
  stronger provenance claim, and no citation was removed.

No claim of unaided or fully human authorship was added anywhere. The synthetic-data,
no-field-validation, no-peer-review and no-hosted-CI statements are unchanged and still
explicit on the home page, the About page and every case page.

### Accuracy: the site was about to publish superseded numbers

`site/src/scripts/site.ts` carried the verification counts as hand-maintained literals and
they had drifted. It said 641 tests collected and 621 passed; the tree measures 667 and
647. It also said 10 checks collected with 9 passed, which is one number from a run with
`--expect-reference-skips` and one from a run without it — that flag registers a further
check, `reference-skip-count-drift`, so the same tree reports 10 under it and 9 without.

Corrected to the run the build itself performs: 667 collected, 647 passed, 20 skipped,
9 checks collected, 9 passed. `scripts/build_release.py` now reads those literals back out
of the TypeScript at step `02-verify` and fails the build when they disagree with the run
that just finished, so the drift cannot recur. Check counts are compared only under
`--cases all`, because a reduced case set legitimately registers fewer checks and failing a
build for running less would not be drift. The gate was exercised against a stale count, a
count moved in the wrong direction, a removed declaration, and both `--cases` modes.

### A contradiction the new skip gate caught

The gate went red on its first full run, on both fixture bases, and it was right. On
WebKit the independent control-fixture probe reported `keyboard-scroll-overflow` as
**available** (`ArrowRight moved scrollLeft to 40`) while the test that skips on it
reported **unavailable** (`scrollLeft to 0`) — same engine, same fixture, same run.

Three measurements were needed to settle it, and the first two conclusions were wrong.

1. **The probe slept.** It pressed ArrowRight, slept a flat 400 ms, and read `scrollLeft`
   once. Replaced with a poll up to a 2 s budget, so "unavailable" means "did not move
   within the budget" rather than "had not moved yet at 400 ms".
2. **The test still slept.** With only the probe fixed, the next full run went red on the
   root base: the probe said available, the test ran, and seven figure frames reported
   `scrollLeft still 0`. The test was reading once after its own flat 400 ms. Both now use
   the same poll, because a check and the probe that gates it cannot measure the same
   thing two different ways.
3. **One press was not evidence.** A single-worker diagnostic settled what the engine
   actually does. On the same `.figure__frame` element — `tabindex="0"`,
   `overflow-x: auto`, `scrollWidth` 1048 against `clientWidth` 325, with `activeElement`
   confirmed on it — Chromium moved `scrollLeft` to 12 on ArrowRight and WebKit moved it to
   0, while `scrollBy(60)` moved both to 60. Six isolated runs of the control fixture on
   WebKit reported unavailable every time. The occasional non-zero reading appeared only
   under the full three-engine suite. The probe now requires **two independent presses to
   agree**, which suppresses the one-off without weakening the negative case, since the
   negative is measured the same way.

Result: 475 passed, 0 failed, 14 skipped at both fixture bases with the gate clean, and the
capability recorded as unavailable on WebKit with the measurement attached.

**Stated as a limitation, not as a settled fact.** What is established is that this engine
build does not move a focused overflow container on ArrowRight in an isolated measurement,
and that the site's frames behave no differently from a bare control fixture. What is not
established is why a single press occasionally registered under load. The check runs and
passes on Chromium and Firefox; on WebKit it is skipped with that measurement rather than
asserted either way. A real Safari session on a real device would be the thing that
settles it, and none has taken place.

### Publication scope

`docs/merge_decision.md` narrated a build session and named the author's own working
directories. The provenance content is kept — it records what came from the starter tree
and that the starter was reproduced before its code was reused — and the local paths are
gone.

Still present and judged legitimate rather than internal handoff: `PLAN.md` (an
engineering plan with the reading register), `docs/backlog.md`, `AGENTS.md` (the working
agreement the About page describes) and `docs/role_prompts.md` (review-pass briefs). These
are ordinary research-project documents, not conversation transcripts. Two are named on the
public About page as part of how the work is run.

### Identified, not changed

* **"this session" appears 319 times** across nine documents as a provenance term meaning
  "during the work recorded in this card". It is meaningful and load-bearing, and rewriting
  it 319 times is not a bounded editorial change. Proposed remedy: define the term once at
  the head of each evidence card, or rename it to "this work" in a single separate pass.
* **The About page states "There is no repository link on this site. The repository has no
  remote."** True today, false the moment the repository exists. Same for `pyproject.toml`,
  whose `Source` and `Documentation` point at a repository that does not exist and carries
  the private baseline's name. Both are release-facing link edits to make **after** the
  real repository exists and **before** the final publication SHA is chosen, which is the
  only point at which the correct value is a fact rather than a guess.
* **Retained Playwright JSON reports contain absolute home paths.** They are git-ignored,
  so nothing is published from the tree, but they must be screened out of any evidence
  archive. The release gate already warns about exactly this.

## Content corrections, 2026-09-14

A bounded pass on the public-facing copy. No reservoir equation, case configuration, input,
threshold, chart datum or scientific conclusion was changed, and no generated figure was
edited by hand. The fourteen frozen artefacts are unmoved.

**Homepage.** The opening no longer argues about kinds of evidence; it says what the
project is, followed by the scope line "Synthetic case studies; not field-validated." The
four-statements distinction was removed from the home page because the Methods page already
carries all four in full, under "The four statements, and what clearing a gate means" —
checked, not assumed. The sentence "Most published verification evidence speaks to the
first. Very little of it speaks to the last." is gone: it is a claim about other people's
published work, which this repository establishes nothing about.

**README.** The introduction describes the tools and the studies. "Nothing has ever been
published or deployed" is gone from the evergreen text; hosted-execution and deployment
status now points to the dated verification and first-publication records, which is where a
claim that changes on an event belongs.

**About.** The lede describes the project instead of denying credentials. No education,
employment, job title, years of experience or software proficiency is stated or implied,
and the existing "What is not claimed" section keeps that list where it belongs. The
maintainer identity already on the page, "writing as azul", is retained unchanged.

**A4 and the R-squared conclusion.** "The fit statistic carries no information about the
error" overstated the result and is replaced everywhere it was active by "A close fit does
not, by itself, establish that the volumetric assumption is appropriate." The demonstrated
fact is that an extremely high R-squared coexists with a materially biased gas-in-place
estimate; that is not statistical independence and not a claim that R-squared is useless.
Corrected in eight places: the home page, the A4 lede, the A4 overview, the A4 meta
description, the F03 in-figure note, the case report, the design-decision record, and the
usability answer key for task 3 — that last one matters because a facilitator would
otherwise have scored a participant against the overstated claim.

The 83.6 ratio moved out of the opening sentence into an uncertainty paragraph after F01,
stated as "the estimation error is 83.6 times the fit's reported standard error" rather
than "83.6 times smaller", with the conditionality named: that standard error is computed
inside the fitted model and excludes the omitted support mechanism.

The prose numbers are bound to the same verified fields the tables use — `base.rSquared`,
`base.fittedBscf`, `base.trueBscf`, `base.errorPct`, `base.biasOverStderr` — at one decimal
place instead of three. No new numeric literal was introduced. Reconciled against the full
precision in `f01_f02_scenarios.json`: 0.9998594933759798 renders 0.999859; 112.50255061080149
renders 112.5; 0.125025506108015 renders 12.5 percent; 83.55744043624358 renders 83.6; and
112.50255/1.1250255 is exactly 100.0.

**Two deviations from the copy as supplied**, both deliberate and both reported rather than
absorbed:

* *"R²" is written "R-squared".* The site uses "R-squared" in 31 places including text baked
  into the generated SVG figures. Introducing the superscript on two pages would clash with
  every figure and with the figure descriptions read by assistive technology.
* *"Each study includes calculations, visual evidence, and interpretation" reads "Each
  published study".* A2 ships no figures and no calculations — its own source header calls
  it "an availability page, not a study page" — because its inputs are the withheld extract.
  The unqualified sentence would have claimed a capability the repository does not implement
  for that study.

**Residual wording from the previous pass.** That pass reported "recalled from training"
eliminated across the evidence cards. Seven upper-case variants had survived in five cards,
so the release record's own claim was wrong; they are corrected now. The 41 lower-case
annotations it had replaced with "stated from prior knowledge" carried a second problem:
that phrase is not a citation and can read as inspected literature or personal field
experience. Each is now an explicit status — 31 read **Unverified — cited source not
inspected** where the annotation names a source that was not read, and 10 read **Unverified
— supporting source not established** where no source is identified. Every replacement was
applied as a whole-line match at a known line number and checked so that no named reference,
access statement, cross-check or uncertainty was lost.

**"this session".** Not globally replaced. The website and the README contain none. Five
occurrences were corrected, all of them in the opening summary paragraph of an evidence
card, where the word has no referent for a first-time reader; they now name the 2026-09-13
source review. The remaining occurrences sit deep inside technical bodies or in dated
records and keep their wording.

**Stale unpublished-project statements.** `.github/workflows/ci.yml` triggers on push to
`main` and `release/**`, so "no hosted continuous integration has ever run" becomes false on
the first push rather than at deployment. Seven such statements were corrected in the
evergreen public copy — the shared `NOT_RUN.hostedCi` string rendered on four pages, the
home page, two status tables, the A3 provenance callout, a Methods bullet and a README
bullet — each rewritten to state what is true of the measurements and to point at the dated
record. Dated records, changelog entries, case reports and workflow comments keep their
wording; the publication sequence owns those.

### Found by the completeness pass, after the first round of edits

Six things the targeted sweeps missed, all corrected:

* **The committed screenshots were the old copy, as pixels.** `site/screenshots/` carried
  17 captures showing the previous lede, the four-statements paragraph, "the fit statistic
  carries no information about the error" and "No hosted continuous integration, ever."
  No text search can find raster text, which is why every grep-based sweep passed over
  them. Recaptured through `tests/screenshots.spec.ts` with `QA_CAPTURES=1` on Chromium,
  and the new home capture was opened and read to confirm it shows the corrected page.
* **`docs/design/figure_spec.md:206`** still said F03 "exists to show that the two
  quantities are unrelated", so the specification contradicted the implementation that had
  just been corrected. Now matches.
* **The README claimed more per-case completeness than A2 has.** "Methods, assumptions,
  results, and reproduction instructions accompany each case" — A2 ships only `run.py`, and
  the reproduction commands are repo-level rather than per-case. Narrowed to "each
  published case" with a link to the repository-level instructions.
* **The A4 lede pointed at the wrong table.** The sentence added in the first round sent a
  reader to "the table below F01", which holds the 49 observations rather than the headline
  quantities. It now points at the tables and the CSV export without naming the wrong one.
* **The distribution manifest's byte table went stale** when F03 was regenerated. The SVG
  subtotal, the PNG subtotal, the published total, the F03 row and two page payloads are
  updated to the measured values. The frozen-artefact gate stayed green throughout, because
  it locks the figure *data*, which did not change.
* **One more generalisation about other people's work**, of the same class as the sentence
  removed from the home page: "a number most engineers would call a good straight line", in
  the README and the case report. Both now say the fit still looks like a good straight
  line, which is a statement about the fit rather than about engineers.

Also corrected while there: the README's Stage B row said "No Stage B code" while the
library ships the diagnostics primitives the Stage B protocol itself lists as available,
and the `UI_QA.md` banner asserted a superseded count as "the current verdict".

## Reference-data clearance, 2026-09-14

The candidate that preceded this release redistributed values from the NIST Chemistry
WebBook extract that this project has decided not to republish. The owner chose the
non-redistribution route. This release is the sanitised snapshot; the values are gone from
the tree and the public history starts here.

**What the policy forbids**, verbatim from `PUBLIC_DATA_POLICY.md`: "Any table, chart
series, figure payload or test fixture that reproduces their values", and "A retrieved
value is data, in whatever format it is wearing." The exemption register adds that "A
retrieved density, viscosity or derived value from the extract is never exempt, whatever
format it appears in."

**Categories found and removed.** The values themselves are deliberately not written here,
and are not written in any commit message, changelog entry or release report in this
repository.

| category | where | disposition |
| --- | --- | --- |
| Retrieved viscosities embedded as a test fixture | `cases/A2_pvt_independent_check/run.py`, the E2b anchor table | removed; E2b rewritten as a software instrument control on invented states |
| A pointwise own-value/deviation pair from which the reference values are recoverable by one division | `docs/evidence/viscosity.md`, the recommended-oracle block | deviations and the aggregate statistic removed; this implementation's own outputs retained |
| Reference-derived Z factors, from which the retrieved densities are recoverable given the published molar mass and temperature | `docs/evidence/viscosity.md`, two separate rows | reference-derived values removed; this implementation's own DAK outputs and the methodological conclusion retained |
| The same values quoted while documenting the problem | this file, in the previous revision | rewritten to describe categories and paths only |

**Checked and found clean**, so that nobody re-opens them: the built site, every published
download, the generated figure SVGs and PNGs, the committed figure data, every case's
committed results, the packaging inputs, and `data/reference/` which carries only the
manifest and the README. No excluded value has ever been added anywhere in the tracked
history of this repository, because this repository's history begins after the removal.

**One false positive**, recorded so it is not "fixed" by a later sweep: a published A3
uncertainty CSV contains a long decimal whose digit string happens to contain one of the
excluded values as a substring. It is an unrelated quantity from a different case and is
retained. Numerical coincidence is not provenance.

**What was retained**, because the policy permits it and the work depends on it: every
citation and bibliographic reference, `data/reference/MANIFEST.json` and its digests,
`data/reference/README.md`, the acquisition recipe `scripts/fetch_nist_reference.py`, the
loader and its schema in `tests/oracles/nist.py`, and the ability to run the external
reference comparison locally once the operator supplies the extract under whatever
permissions apply to them.

**What this is not.** It is not a legal ruling about any individual number, about
calculated results in general, or about NIST works. The material is described as excluded
under this project's own policy, which is a conservative publication decision rather than
an adjudication of anyone's rights.

## Unresolved items

Carried forward and still true:

- **No hosted execution.** Both workflows lint clean and their logic has been exercised
  locally, but neither has run on a GitHub runner. Reading a workflow is not running it.
- **No timing measurement.** Payload bytes measured; no Lighthouse or Web Vitals run.
- **No screen reader, no real device.** Three engines are not three browsers.
- **Zero usability participants.** `USABILITY.md` is a script nobody has sat through.
- **The Python lock was resolved on macOS/arm64** and carries no hashes. The first Linux
  run may find a missing platform wheel. The fix is to regenerate the lock on Linux.
- **`pyproject.toml` names a repository that does not exist.** `[project.urls]` points
  `Documentation` and `Source` at `github.com/azulcoder/reservoir-engineering-workbench` --
  no `-public` suffix, and read-only discovery confirms no repository of either name exists
  under that account. It is aspirational metadata carrying the *private* baseline's name,
  and it is currently published in the wheel and the sdist. It is corrected once the real
  repository exists and its URL is known, which is the only point at which the correct
  value is a fact rather than another guess. Every other `github.com` URL in the tree is a
  citation of a third-party project or a pinned action, and those stay as they are.
- **`actionlint` ran without `shellcheck`** (absent on this machine), so the workflow and
  expression checks ran but the embedded shell was not statically linted. The hosted run
  executes that shell for real.

## External run identifiers

None. This table is filled in from real runs, never from an intention.

| workflow | event | commit | run id | attempt | conclusion | observed |
| --- | --- | --- | --- | --- | --- | --- |
| — | — | — | — | — | — | — |

## Phase log

### Phase 1 — establish the actual release state

Verified against the filesystem rather than against the reported state:

- branch `release/rc-close`, HEAD `ef308cc9`, 8 commits, 289 tracked files, clean tree,
  no remote, no tags.
- a local `main` exists at `c3d6933`, which is the merge base; `release/rc-close` is 4
  commits ahead and `main` is 0 commits ahead. Nothing has diverged.
- every commit is authored and committed by the same identity, name `azul`, using the
  GitHub-provided `users.noreply.github.com` address for the account. No personal or
  employer email address appears anywhere in the history, and no generation or provider
  attribution appears in any commit message. Verified with
  `git log --all --format='%an <%ae> | %cn <%ce>' | sort -u`, which returns one line.

  The literal address is deliberately not written out here. This document is published,
  and `scripts/check_repository.py` refuses an email address in a tracked file — a gate
  that fired on the first draft of this very paragraph.
- tool versions: Python 3.13.2, Node v24.14.0 (the exact pin both workflows declare),
  npm 11.9.0, git 2.54.0, gh 2.89.0.

### Phase 2 — close the deployment-integration gaps

Four findings were investigated in the current files and all four were still present.

**2.1 The runbook's local gate was stale.** It said "The local browser QA is green. **It is
not green today**" and quoted 401/12/13, contradicting RC_CLOSURE.md's later 466/0/14. It
also described the WebKit keyboard skips as engine-name exclusions, which the capability
probes had already replaced. Both passages now describe the current state and link to the
historical documents rather than erasing them.

**2.2 The first push would not have triggered anything.** `ci.yml` listened to `push` on
`main` only, while the runbook instructed pushing `release/rc-close` and said that push
starts verification. Those cannot both be true. `push` now covers `main` and `release/**`;
`pull_request`, `workflow_dispatch` and `workflow_call` are unchanged; `pages.yml` still has
`workflow_dispatch` and nothing else, so no push to any branch can deploy. The empty-repository
bootstrap is written down in the runbook as the one-time exception it is.

**2.3 The skip gate could not recognise its own tests' skips.** Both workflows carried
separate inline validators matching two exact English sentences, one of which asserted a
macOS-specific fact. The tests had moved to capability probes emitting descriptions that
began `NOT APPLICABLE in this environment: ...`, which those matchers could not see.

Replaced with one gate:

- `site/tests/skip-policy.json` — the policy, declaring stable capability ids, the engines
  each is permitted on, and whether it is evidenced by a control-fixture probe or by an
  absent engine API.
- `scripts/check_skip_policy.py` — the validator, called by the local path and by both
  workflows. Matches on the bracketed id, not on prose.
- `site/tests/support.ts` — `notApplicable()` and `recordCapability()`, reading the same
  JSON so there is one source of truth rather than a copy.

A skip must name a declared id; a bare `NOT APPLICABLE ...` sentence is rejected. A
probe-backed skip must carry its own measurement **and** agree with the independent probe in
`measure.spec.ts`; a skip whose measurement says the capability was available is reported as
a site failure wearing a skip. An empty suite, an engine that produced nothing, an engine
that produced only skips, and a check skipped on every engine all fail. No count is compared
against a baseline: 14 skips is what macOS took, not a target for Linux.

`tests/test_skip_policy.py` exercises 26 cases including the allowed capability skips, an
unknown id, a bare `NOT APPLICABLE` prefix, a missing measurement, a self-contradicting
measurement, a contradicting independent probe, an absent probe, a disallowed engine, an
empty suite, a suite of nothing but skips, an absent engine, an engine that only skipped,
an ordinary failure, a timeout, and a fewer-skips-on-another-platform case that must pass.

**2.4 Release verification could have been handed a different directory.** The workflows
set `QA_REUSE=1`, which leaves `reuseExistingServer` to choose between the caller's server
and Playwright's own by probing a URL; a server that dies after the readiness check hands
the suite to a fallback that runs `astro build` into `site/dist`. The candidate directory
then passes its after-fingerprint unchanged, because nothing read it.

`QA_RELEASE=1` now leaves the configuration with no `webServer` at all, and both workflows
use it. `tests/release-mode.spec.ts` closes the loop from the other end by comparing the
bytes the browser received for the home page, a deep route and a published download against
the candidate's files on disk. `scripts/check_release_mode.py` demonstrates the substitution
happening in non-release mode before showing that release mode prevents it, because a
safeguard whose failure mode was never observed is an argument rather than a check.

**2.5 Manual publication was not bound to a commit.** `gh workflow run --ref` takes a branch
or a tag, and the commit is resolved server-side after the dispatch. `pages.yml` now requires
an `expected_sha` input, validates it as a full 40-character lowercase SHA, and compares it
with `github.sha` in preflight before any expensive step. Both values reach the shell through
the environment; neither is interpolated into a script body. The acknowledgement gate, the
configuration variables and the deployment environment are unchanged.

## Rollback and resume

Nothing external exists, so there is nothing to roll back. The local work is ordinary
commits on `release/rc-close` and can be inspected with `git log` or dropped with
`git revert`. To resume: read this file and `RC_CLOSURE.md`, then continue from **Current
phase** above.

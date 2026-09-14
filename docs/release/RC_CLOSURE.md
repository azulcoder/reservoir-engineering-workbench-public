# Release candidate closure

Date: 2026-09-14. Branch `release/rc-close`. This is the current verdict; it supersedes
[UI_QA.md](UI_QA.md), which is kept and banner-marked as historical.

**Stopping point reached: LOCAL RELEASE CANDIDATE READY FOR OWNER REVIEW.** Hosted CI has
not run, nothing has been deployed, and no human has evaluated the site. Those three are
reported separately below and none of them is implied by the others.

---

## 1. The snapshot question, settled

Two counts were in circulation: 380 passed / 33 failed / 13 skipped in `UI_QA.md`, and
401 / 12 / 13 in a later summary. They are not two revisions.

`git log --format='%h %aI' -1 --` on each file shows `docs/release/UI_QA.md`,
`site/src/styles/base.css` and `site/screenshots/` all entering at the **same commit**,
`fef10c2`. The committed `base.css` already contains both reflow fixes. So the QA report
was written against the working tree *before* those fixes were applied, and then committed
alongside them. The report is stale relative to its own commit; the screenshots it
describes were captured in the same pre-fix state.

A baseline run at `c3d6933` measured 401 / 12 / 13, which confirms the later figure and
retires the earlier one. This is recorded rather than quietly corrected, because a report
that disagrees with its own commit is exactly the kind of thing a reader should be able to
find an explanation for.

## 2. Issue map, before and after

Every row was re-verified against the current source, not against a status table.

| Item | Before | Root cause | After |
|---|---|---|---|
| **F2** chart text below the 13 px floor | OPEN, 10.9 px on Chromium and WebKit, Firefox passing | Two separate causes. The figure SVG was being scaled by its container (`width:auto` on an element with a `viewBox` fills the containing block, so a 13 px label in an 838 px column renders at 10.9 px). The measuring helper was also validated against known-size fixtures before anything was changed, because an engine split is more often a measurement bug than a drawing bug. | **FIXED-REVERIFIED.** The floor did not move. |
| **F3** unreachable table overflow | Already fixed in `fef10c2`, re-verified here | `html{overflow-x:hidden}` converted overflow into clipping with no way to scroll; `DataTable`'s `columns.length > 6` was the wrong proxy for rendered width | **FIXED-REVERIFIED.** Absent from every failure list; tables scroll inside their own labelled regions and the page does not scroll sideways. |
| **F4** download not bound to the canonical figure | OPEN. `index.json` claimed byte-identity and nothing enforced it | No build-time gate existed between the rendered figure and its published copy | **FIXED-REVERIFIED.** Identity is enforced inside the build and again by a drift check against git, so the claim holds for a published tree nobody has re-run. Two drills prove it. |
| **F5** non-text contrast and decorative classification | OPEN, two checks | `--c-rule` `#e1dfda` at 1.33:1 was painting two marks a reader depends on — the divider between a figure's evidence and its qualifications, and the row separator that says which value belongs to which row. A pale legend swatch sat outside any aria-hidden group. | **FIXED-REVERIFIED** by changing what the marks look like, not by relabelling them. Both necessary marks promoted to `--c-border-strong` (3.51:1). The swatch gained a 3:1 boundary, the decorative fill inside it hidden. The decorative verdict on gridlines and band fills was checked by removing them and confirming the figures still read. |
| **F6** scroll-region behaviour | OPEN | Component-scoped Astro CSS does not reach markup injected with `set:html`, so the panel rule matched nothing and panels shrank instead of scrolling | **FIXED-REVERIFIED** with `:global()` and verified through computed styles rather than selector inspection. |
| **F7** annotations outside the canvas | OPEN on all engines | The renderer guessed text width at one average advance per character, and Plot's `lineWidth` is a budget independent of *where* the text sits | **FIXED-REVERIFIED.** Measured advances, a build-time guard that refuses to emit a figure whose label falls outside its box, and a third previously unreported overflow found by that guard. The last offender was not a figure at all but the explorer panel subtitle in `panels.ts`, drawn as one unwrapped line; it now wraps and the panel grows. Nothing was cropped or shortened. |
| **Type checking** | OPEN. 18 TypeScript errors reported; `@types/node` and `@astrojs/check` not installed | The declared `check` script could not run at all, and the installed TypeScript 7.0.2 sits outside `@astrojs/check`'s documented peer range `^5.0.0 \|\| ^6.0.0` | **FIXED-REVERIFIED.** Pinned to typescript 6.0.3, `@astrojs/check` 0.9.10, `@types/node` 26.5.1, exact, lockfile updated. Two configurations — site graph and Node tooling — both run by `npm run check`: **0 errors, 0 warnings, 0 hints**, tsc exit 0. |
| **CI `site-build`** | OPEN, a passing placeholder that built nothing | — | **FIXED-REVERIFIED.** Calls the canonical sequence, then gates on its JSON summary, a committed-tree drift check, a build fingerprint and the browser suite. |
| **Pages build** | OPEN, deliberately exited 1 | — | **FIXED-REVERIFIED.** Real pipeline; deployment stays manual, gated and loud about an unset destination. Deploys the artifact it tested, identified by a fingerprint taken before the browser suite and rechecked after. |
| **PNGs not published** | OPEN, 12 generated, 0 published | — | **FIXED-REVERIFIED.** Published as downloads, kept out of the initial page payload, sized separately in the distribution manifest. |

Two things examined and found **NOT APPLICABLE**, recorded so nobody re-opens them:

* The per-figure caveat appeared to be clipped at 375 px because it sits inside the SVG. It
  is *also* rendered in the page's reading flow as an HTML caveat block — nine of them, one
  per figure — so the qualification is reachable without horizontal scrolling. The in-SVG
  copy is the redundancy that makes a standalone export carry its own caveat, which is
  required. No change made.
* The sdist appeared to contain two files with home paths. Both are the **regular expression
  that detects home paths**, in `check_repository.py` and in the document quoting it. No leak.

## 3. What was actually run, and what it produced

Every command below was recorded with its own exit status — never a pipe tail — into
`docs/release/evidence/command_log.jsonl`, with logs beside it. The machine-readable record
is `docs/release/evidence/release_status.json`.

| Check | Result |
|---|---|
| `python3 scripts/check.py` | 641 run, 0 failed, 20 skipped; hygiene 0 errors |
| `python3 scripts/verify.py --profile public-core --cases all --expect-reference-skips 20` | 10/10 checks, 641 collected, 621 passed, **20 skipped**, 20 tests + 2 checks NOT RUN with named reasons |
| `python3 scripts/build_release.py --base-path /reservoir-engineering-workbench-public/ --out-dir site/dist-project --verify-cases all` | **10/10 steps**, 0 failed, 0 blocked |
| the same at `--base-path /` into `site/dist-root` | **10/10 steps**; both trees coexist |
| `npx playwright test`, 3 engines, project base | **466 passed, 0 failed, 14 skipped** |
| the same at the root base | **466 passed, 0 failed, 14 skipped** — identical |
| `python3 scripts/drills_release.py` | **10 cases, 10 caught, 0 not caught** |
| `python3 scripts/check_frozen.py` | **14 frozen artefacts, 0 moved**, before and after |
| `python3 -m build` | wheel and sdist built |
| wheel installed into a fresh venv, imported from `/tmp` | `reservoir_lab` 0.2.0, `R = 10.73158`, `Z(3000 psia, 660 degR, sg 0.65) = 0.905059` |
| clean `git archive HEAD` export, `npm ci`, canonical build | **10/10 steps** with no pre-existing `dist`, no `node_modules`, no reference data |
| screenshots | 17 current captures, Chromium, macOS arm64 |

The 14 skips are declared by capability and reason, not by engine exclusion. The one this
report is asked about explicitly: printing to PDF is Chromium-only, so it is NOT APPLICABLE
on Firefox and WebKit rather than skipped for convenience.

## 4. Local preview, verified verbatim

The instructions in `USABILITY.md` were wrong and are corrected. `npm run preview` on its own
serves the **root-base** build, so a session run from the old instructions would have 404'd
on every page and the reader would have been told the site was broken when it was not. A
stale `site/dist` left by an earlier plain `astro build` made that trap worse and was removed.

What was run verbatim from the corrected document, on 2026-09-14:

```bash
npm ci --prefix site
python3 scripts/build_release.py \
    --base-path /reservoir-engineering-workbench-public/ \
    --out-dir site/dist-project
cd site
QA_DIST=$PWD/dist-project QA_BASE=/reservoir-engineering-workbench-public/ \
QA_PORT=4321 node tests/serve.mjs
```

Project base 200, deep route 200, figure download 200, missing page 404.

## 5. Remaining limitations

* **No hosted execution of anything.** There is no remote. Both workflows were written,
  linted and had their embedded logic exercised against real inputs, but neither has run on
  GitHub. Reading a workflow file is not running it.
* **No timing measurement.** Payload bytes were measured; no Lighthouse or Web Vitals run
  was performed, and neither would be field data if it had been.
* **No screen reader, no real device.** Three browser engines are not three browsers, and a
  viewport test is not a device test. No VoiceOver, NVDA or JAWS session took place.
* **No human read the site.** `USABILITY.md` is a script with zero participants.
* **Pre-registration status is unchanged and still uneven.** A1 and A4 remain ordering
  unverified; A2 and A3 have protocol hashes recorded by the run itself, which is internal
  content linkage and not an independent timestamp.
* **The lockfile was resolved on macOS/arm64** and carries no hashes, so the first Linux CI
  run may find a missing platform wheel. The fix is to regenerate the lock on Linux, not to
  relax the install.

## 6. Verdicts

| Area | Verdict |
|---|---|
| Scientific regression and public-core reproduction | **PASS** — 641/621/20, all cases reproduce, 14 frozen artefacts unmoved |
| Data, history and distribution policy | **PASS** — release gate clean, no restricted extract in source, history, exports, packages or evidence |
| Packaging and type checks | **PASS** — wheel and sdist build, wheel imports from outside the checkout, `npm run check` 0/0/0 |
| Figures, exports and provenance | **PASS** — 12 figures, SVG and PNG published, identity enforced at build time, 10 drills catch 10 |
| Local browser, reflow and accessibility checks | **PASS** — 466/0/14 on three engines at both bases; axe clean; 13 px floor met |
| Local performance evidence | **PARTIAL** — payload measured, no timing run |
| Hosted CI | **NOT RUN** — no remote exists |
| Deployment | **NOT PERFORMED** — configured, manual, authorisation-gated, fails loudly while unset |
| Human usability evaluation | **PENDING** — zero participants, zero sessions |

The single next owner action is in [DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md): approve a
real destination and visibility. Nothing in the external sequence was executed.

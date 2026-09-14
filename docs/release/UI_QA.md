> **HISTORICAL — this is not the current verdict.**
>
> This report was written against the working tree as it stood *before* the reflow and
> SVG-scaling fixes were applied, and both the report and those fixes landed in the same
> commit, `fef10c2`. That is why it records 380 passed / 33 failed / 13 skipped while the
> committed tree at that revision already measured 401 / 12 / 13. It is stale relative to
> its own commit, not a report of a different revision.
>
> It is kept because its findings F1 to F11 are the ones the closure pass worked from, and
> because deleting the record of a state that existed would make the audit trail worse.
>
> The verdict that superseded this document is [RC_CLOSURE.md](RC_CLOSURE.md), measured on
> 2026-09-14 at 466 passed / 0 failed / 14 skipped on three engines at both base paths. The
> latest state, including every later run and the counts it reported, is in
> [FIRST_PUBLICATION.md](FIRST_PUBLICATION.md). The screenshots in `site/screenshots/` are
> recaptured whenever the pages change; the ones described below are not.

---

# Browser QA of the publication site

What this records: one QA pass over the built site, run in three browser engines at two base
paths, on 2026-09-13. Every number below was measured during that pass. Where a check
failed, it is recorded as a failure and the failing test is left failing in the suite rather
than relaxed to make the run green.

What it does not claim. A clean axe run is not WCAG conformance; axe tests a subset of the
success criteria and cannot judge whether an alternative is accurate or whether a page makes
sense. Three engines are not three browsers on real hardware: Playwright's Chromium, Firefox
and WebKit builds are engine builds, and nothing here was tested on an iPhone, on Safari as
shipped by Apple, on a screen reader, or with a reader. No performance measurement was taken
beyond payload bytes.

---

## 1. Environment

| Item | Value |
|---|---|
| Host | macOS 26.6.2 (build 25G83), arm64 |
| Node | v24.14.0 |
| Astro | 7.3.2 |
| Playwright | 1.63.0 |
| axe-core | 4.13.0, via @axe-core/playwright 4.13.0 |
| Chromium | 153.0.8010.12 (Playwright build chromium-1243) |
| Firefox | 155.0 (Playwright build firefox-1543) |
| WebKit | 26.6 / AppleWebKit 605.1.15 (Playwright build webkit-2359) |
| Browser binaries | `site/.playwright-cache`, reached through `PLAYWRIGHT_BROWSERS_PATH` |
| PDF text extraction | pypdf 5.9.0, used once, for the print check |
| Bases tested | `/reservoir-engineering-workbench-public/` (primary) and `/` |
| Git remote | none; nothing has been deployed and no hosted CI has ever run |

### What was served

The built output in `site/dist`, never the dev server.

`npx astro preview` in Astro 7.3.2 daemonises: it prints "Preview server running … (pid N)"
and returns, and a second invocation on a different port attaches to the instance already
running rather than opening the port asked for. A test runner cannot drive that, and it
cannot hold two servers open for two base paths at once. So the suite serves `dist` with
`site/tests/serve.mjs`, a static server with three rules and nothing else: the base prefix is
mandatory, a bare directory path redirects to the trailing slash, and an unknown path is
answered with the built `404.html` under a 404 status. Those three were checked against the
real preview server before the file was written, and the responses matched:

```
$ SITE_BASE=/reservoir-engineering-workbench-public/ npx astro preview --port 4399
$ curl -s -o /dev/null -w "%{http_code}\n" http://localhost:4399/                                        404
$ curl -s -o /dev/null -w "%{http_code}\n" http://localhost:4399/reservoir-engineering-workbench-public/ 200
$ curl -s -o /dev/null -w "%{http_code}\n" .../reservoir-engineering-workbench-public/studies/a4/        200
$ curl -s -o /dev/null -w "%{http_code}\n" .../reservoir-engineering-workbench-public/nope/              404
```

### Commands

```sh
cd site
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright-cache"

# the pass that matters: the non-root project base, all three engines
npx playwright test --grep-invert "captures"

# the second pass, at the root base
QA_BASE=/ QA_PORT=4322 npx playwright test --grep-invert "captures"

# screenshots, one engine, on their own so the file names mean one thing
npx playwright test --project=chromium screenshots.spec.ts --workers=1

# what the config does for each run, in effect:
#   SITE_BASE=<base> npx astro build && QA_BASE=<base> QA_PORT=<port> node tests/serve.mjs
```

`playwright.config.ts` rebuilds `dist` for the base under test before serving it, and does
not reuse an existing server unless `QA_REUSE=1` is set, because a reused server would
silently serve the previous build.

### One thing this pass adds that does not type-check

`npx tsc --noEmit -p site/tsconfig.json` exits 1 with 18 errors, all of one kind: TS2591,
"Cannot find name 'process' / 'node:fs' / 'node:path' / 'node:crypto'". Two of them are in
`astro.config.mjs` and predate this pass; the other sixteen are in `playwright.config.ts` and
the new test files, which legitimately read `process.env` and node builtins. `@types/node` is
not installed in `site/node_modules`, and `npm run check` cannot run either because
`@astrojs/check` is not installed. Playwright compiles and runs the suite regardless, which
is why every result below exists.

So: the project's TypeScript gate was already failing before this pass and this pass adds to
it. The fix is one line of configuration — install `@types/node` and add `"types": ["node"]`
to `site/tsconfig.json`, or exclude `tests` and `playwright.config.ts` from it — and it was
left to the owner because `tsconfig.json` is not a QA file.

### Totals

| | project base, port 4321 | root base, port 4322 |
|---|---|---|
| passed | 380 | 380 |
| failed | 33 | 33 |
| skipped | 13 | 13 |

Per engine, identical at both bases: Chromium 131 passed / 11 failed / 0 skipped; Firefox 130
/ 11 / 1; WebKit 119 / 11 / 12. The 33 failures are 11 distinct checks, each failing in all
three engines. The skips are declared, not silent: 12 in WebKit because macOS WebKit keeps
links out of the tab ring unless the system's full keyboard access is on, and 1 in Firefox
because `page.pdf()` is Chromium-only.

The base path made no difference to any result.

---

## 2. Check by check

| # | Check | Result |
|---|---|---|
| 1 | Routes, anchors, base-prefixed links and downloads, deep refresh, under the non-root base | PASS |
| 2 | Console errors, broken requests, leaked secrets, third-party requests, missing chart marks | PASS, with one rendering defect found (F7) |
| 3 | axe-core on every route | PASS, 0 violations, after fixing one serious violation (F1) |
| 4 | Keyboard, focus visibility, non-colour encoding, accessible names, chart alternatives | PASS, except F6 |
| 5 | Contrast as rendered, text and non-text | PASS for text; FAIL for two non-text uses (F5) |
| 6 | 375 / 768 / 1440, 320 reflow, 200 percent text | FAIL at 375, 768, 320 and at 200 percent text (F3); PASS at 1440 |
| 7 | Long labels, unavailable-reference page, invalid query strings, all eight cases, reduced motion, blocked JavaScript | PASS, except the long-label case, which is F3 |
| 8 | Chromium, Firefox, WebKit | PASS; WebKit tab-order limitation recorded, not worked around |
| 9 | No-JavaScript: evidence and downloads present | PASS, after fixing F9 |
| 10 | Keyboard and back/forward restore a consistent scenario state; descriptions and exports agree | PASS |
| 11 | SVG and PNG exports carry title, units, legend, caveat | PASS for the 12 SVGs; PNGs are build artifacts and are not published (see below); two annotations are clipped (F7) |
| 12 | Print shows the selected case and keeps the limitations | PASS, after fixing F10; verified by printing to PDF, not only by emulating the stylesheet |
| 13 | The build fails if a mandatory chart or public data file is missing | PASS, re-confirmed with seven drills |

Things adjacent to these checks that were **NOT RUN**, so that the table is not read as
covering them:

| Item | State | Why |
|---|---|---|
| Safari on macOS or iOS, Chrome or Edge as shipped | NOT RUN | only Playwright's engine builds were driven; an engine is not a browser and a browser is not a device |
| Screen readers (VoiceOver, NVDA, JAWS) | NOT RUN | no assistive technology was operated in this pass; every accessibility result here is markup, geometry or contrast |
| Printing through a real print driver onto paper | NOT RUN | Chromium's PDF export was used instead; pagination, widow control and colour management on a real driver are untested |
| Windows high-contrast mode | NOT RUN | only the `forced-colors: active` emulation, which passed structurally |
| Hosted CI, and the site under a real host | BLOCKED | the repository has no remote, so neither exists to test |
| Performance beyond payload bytes | NOT RUN | no timing, no Lighthouse, no field data |

Detail for each follows the findings.

---

## 3. Findings

Eleven findings. Five were small enough to fix in this pass and are marked FIXED with the
change; six are left open because the fix is a design decision rather than a defect repair,
and each of those has a failing test carrying its number.

### F1. Every chart mark group carried a prohibited ARIA attribute — FIXED

axe reported `aria-prohibited-attr` at **serious** impact on `/`, `/studies/a1/`,
`/studies/a3/` and `/studies/a4/`, in both the default and the non-default explorer state.
Observable Plot names each mark group it draws — `aria-label="dot"`, `"line"`, `"rule"`,
`"text"`, `"x-axis tick label"` — on a bare `<g>`. An SVG `<g>` exposes no role that permits
an accessible name, so each one is a violation, and the names say nothing usable: "dot" is
not a description.

Fixed in `site/scripts/render-figures.mjs`, in `serialise()`, after the root is labelled:
every `aria-label` on a descendant that carries no `role` is removed. The root keeps its
`role="img"`, its `aria-label` and its `aria-describedby`; the `aria-hidden="true"` on
gridlines and band fills is untouched. Figures were re-rendered and the published copies
re-emitted. axe is now clean at WCAG 2.2 AA plus best-practice on every route in all three
engines. Side effect: the case page lost 4,617 bytes raw.

### F2. Chart text renders far below the 13px floor the design sets — OPEN

`docs/design/decisions.md` D24: "Chart labels never render below 13px." Measured as rendered
on `/studies/a4/`, taking the smallest painted text in any exhibit:

| viewport | smallest rendered chart text |
|---|---|
| 1440 | 8.3 px |
| 768 | 7.3 px |
| 375 | 3.0 px |

The cause is not the authored size, which is 13px, but `img, svg { max-width: 100% }` in
`base.css` §2: the whole drawing is scaled down to the column width, and the text scales with
it. An exhibit is authored on a 1000px or 1200px canvas and rendered into a 640-to-816px
column on a desktop and a 325px column on a phone. `screenshots/figure-f01-375.png` shows the
result: at 375 the exhibit is a picture of a chart, not a readable chart.

This is not itself a WCAG failure — the page is zoomable and every value is in the data table
underneath — but the design document states a floor that the site does not meet at any
width. Either the floor or the scaling has to change. Failing test:
`responsive.spec.ts › chart text renders at or above the 13px floor the design sets`.

### F3. Nine tables are clipped at narrow widths, with no way to scroll to them — OPEN

The most serious finding in this pass. At 375, `/studies/a4/` lays out a document 839px wide
inside a 375px viewport; `html { overflow-x: hidden }` stops the page scrolling, so the
content past 375px cannot be reached at all. `window.scrollTo(500, 0)` leaves `scrollX` at 0.
`screenshots/metrics-table-375.png` is the evidence: the metrics table shows its Quantity
column and nothing else — every value, which is the entire point of the table, is off-screen
and unreachable.

Measured at 375, with every disclosure open:

| route | document width | clipped tables | tables that correctly scroll |
|---|---|---|---|
| `/studies/a4/` | 839 px | `t-f04` 798px/6 cols, `t-f06a` 613px/3, `t-f07` 581px/2, `t-f08` 743px/6, `metrics-2` 704px/3 | `t-f01`, `t-f03`, `t-f05`, `obs-2` |
| `/studies/a1/` | 793 px | `t-a1-01` 752px/5 | — |
| `/studies/a3/` | 870 px | `t-a3-01` 829px/4 | — |
| `/methods/` | 936 px | `t-measured` 781px/2, `t-f09` 895px/3 | `verification-status` |

`/`, `/studies/`, `/studies/a2/` and `/about/` are clean at every width.

Three rules combine to produce it, each defensible on its own:

1. `tbody th[scope="row"] { white-space: nowrap }` (`base.css` §6) stops a row label
   wrapping, so a three-column table is intrinsically 700px wide.
2. `DataTable.astro` decides whether to wrap a table in a labelled scroll region from its
   **column count** — `wide = columns.length > 6`. A two-column table 581px wide gets none.
   Column count is the wrong proxy for intrinsic width.
3. `html { overflow-x: hidden }`, commented "belt and braces: nothing should ever reach
   this", is load-bearing: it converts overflow into clipping. Without it the page would
   scroll sideways, which is worse-looking and better for the reader, because the content
   would still be reachable.

The same failure appears at 768, at 320 (SC 1.4.10 Reflow), and at 1280 with text at 200
percent (SC 1.4.4), where the widest table reaches 1,740px. Suggested direction, for the
owner to decide: make `wide` a measurement rather than a column count, or wrap every data
table in the scroll region and let `overflow-x: auto` decide, and drop the `overflow-x:
hidden` so that any remaining overflow is visible rather than hidden. Nothing was changed
here because every route to a fix changes how tables look on every page.

Failing tests: the four `responsive.spec.ts` overflow checks, `responsive.spec.ts › nothing
hides overflow globally to conceal clipping`, and `exports.spec.ts › a long row label wraps
instead of widening the page`.

### F4. A published download can drift from the figure it claims to copy — OPEN

`public/data/index.json` describes each exhibit copy as "byte-identical to the file the page
inlines". The build enforces two things and not the third: the generated SVG against the
figure manifest (edit one by hand and the build fails, "figure F01 is stale"), and each
download against its digest in `index.json` (tamper with one and the build fails). It never
compares the download with the figure the page actually inlines.

Demonstrated in an isolated copy of the tree (drill H, §7): re-render a figure, update the
manifest consistently, leave `public/data/figures/f01.svg` alone, and `astro build` exits 0
while the page inlines one drawing and offers a different one for download under a
description asserting they are identical. This happened for real during this pass — running
`node scripts/render-figures.mjs` for F1 left the published copies stale and the build said
nothing — and was repaired by running `node src/scripts/emit-public-data.mjs`.

The suite now closes the gap from outside: `exports.spec.ts › every downloadable SVG is
byte-identical to the one the page inlines` fetches all 12 over HTTP and compares them with
`src/generated/figures/`. It passes today. A build-time version of the same comparison
belongs in `emit-public-data.mjs` or in the exhibit loader.

### F5. Two colours below 3:1 are drawn outside any aria-hidden group — OPEN

`decisions.md` §8 names exactly two colours as deliberately below the 3:1 non-text threshold,
both declared non-information-bearing and both stated to be marked `aria-hidden`:
`--c-gridline` at 1.25:1 and `--c-band-neutral` at 1.16:1. As rendered:

- `--c-rule` `#e1dfda` is used for separator lines inside figures — 1 use in F01, 8 in F03,
  24 in F09 — measuring **1.33:1** against the plot ground. It is not in that table at all,
  neither as an information-bearing mark meeting 3:1 nor as a declared decorative exception.
- `--c-band-neutral` `#efeeea` is used for the band's **legend swatch** in F02, F05 and F07
  (a 34×14 rect), painted outside any `aria-hidden` group, at 1.16:1. The swatch is the only
  visual identification of that series in the legend; the text label beside it carries the
  meaning, which is why this is a documentation gap rather than a hard failure.

Either is a small change — add them to the decorative table with a justification, or raise
them. What matters is that the document currently says something about the drawing that the
drawing does not do. Failing tests: `contrast.spec.ts › information-bearing chart marks meet
3:1 against the plot ground` and `› the two decorative colours are marked aria-hidden, as the
document claims`.

### F6. The explorer panels' minimum width is a dead rule — OPEN

`ExplorerScenarios.astro` sets `.explorer__frame svg { width: 100%; min-width: 460px }`, and
the component documents the intent: the panel scrolls inside its own labelled frame on a
narrow viewport. Astro scopes component styles by stamping a `data-astro-cid-*` attribute on
the elements in the template, and the panel SVG arrives through `set:html`, so it carries no
such attribute. The compiled selector is
`.explorer__frame[data-astro-cid-yqfsre6e] svg[data-astro-cid-yqfsre6e]`, which matches
nothing. Measured at 375: the panel frame is 325px wide with a 325px scroll width — it does
not scroll, it shrinks, and its 13px labels render at about 6.4px.

The same measurement shows the published exhibits never scroll either: `.figure__frame` is
`overflow-x: auto`, `tabindex="0"` and labelled, but `.figure__frame svg { max-width: 100% }`
means there is nothing to scroll, so the nine exhibit frames on the case page are nine focus
stops that do nothing when they receive focus and are operated.

Not changed here. Reviving the rule would make panels scroll at narrow widths instead of
shrinking, which is a visible responsive change, and it still would not reach the 13px floor
(460/660 × 13 ≈ 9px). It belongs with the F2 decision. Failing test: `manual.spec.ts › every
figure frame is reachable and labelled, and scrolls with the keyboard`.

### F7. Two figure annotations are painted outside their own canvas and cut off — OPEN

Measured at a 1600px viewport, comparing each `<text>` box with its root SVG box:

- F05: "calibration R² = 0.999641, calibration gas in place +11.30% of true G" starts at
  x = 643 in a 1000-unit canvas with `text-anchor="start"` and runs 47 CSS px past the right
  edge. It is cut off mid-phrase in the page, in the downloadable SVG and in the PNG
  (visible in `src/generated/figures/f05.png`).
- F01b: "Vertical axis truncated to the observed range, and rescaled …" runs 81 CSS px past
  the edge.

Both are statements the figure is making about itself, which is exactly the class of text the
figure specification says must travel with the image. Not fixed: where the label should go
instead is a figure design decision. Failing test: `runtime.spec.ts › no figure paints text
outside its own drawing`.

### F8. The desktop contents rail painted nothing — FIXED

At widths at or above 64rem the "On this page" rail rendered as blank space while holding a
240px grid column. Measured at 1440 before the fix, in all three engines: the nav had eight
list items and a layout box 361px tall, `checkVisibility()` returned false, and the rail's
height was 0. `screenshots/a4-1440.png` before and after shows the whole difference.

Cause: the rail is a `<details>`, and `base.css` forced its list visible with
`.contents__disclosure:not([open]) > .contents__list { display: block }`, written against the
old user-agent rule `details:not([open]) > *:not(summary) { display: none }`. Current
Chromium, Firefox and WebKit do not hide a closed disclosure's children that way any more:
they wrap them in the `::details-content` pseudo-element and set `content-visibility: hidden`
there, which a rule on the children cannot reach.

Fixed by adding, inside the existing `@media (min-width: 64rem)` block,
`.contents__disclosure::details-content { content-visibility: visible }`. Verified at 1440
and at 900 in all three engines: the rail paints at desktop width, and below the breakpoint it
is still a working disclosure with a visible summary. Regression test: `manual.spec.ts › the
contents rail is actually painted at desktop width, and is a control below it`.

### F9. With JavaScript off, the dead control was shown anyway — FIXED

The explorer ships its controls with the `hidden` attribute and the script removes it, so
that a reader whose script did not run is never shown a control that does nothing — the
component says so in its own documentation. It did not work: `.explorer__controls { display:
flex }` is a class rule and outranks the user agent's `[hidden] { display: none }`, so with
JavaScript blocked the eight radios and the reset button were displayed and inert, next to a
paragraph explaining that they were absent.

Fixed with one rule in `ExplorerScenarios.astro`: `.explorer__controls[hidden] { display:
none }`. Nothing changes for a reader whose script ran. `screenshots/explorer-nojs-1440.png`
shows the intended state: no control, the static note, and the base case complete.

### F10. Printing dropped every table inside a closed disclosure — FIXED

The print stylesheet's stated intent is "Force every disclosure open". Verified by printing
`/studies/a4/` to PDF with the disclosures in the state a reader prints from — closed:

| | pages | "4344.20" present | "All 49 observations" present |
|---|---|---|---|
| before the fix | 25 | no | no |
| disclosures opened by hand | 26 | yes | yes |
| after the fix, closed | 26 | yes | yes |

Same cause as F8: the override targeted the children, and the engines hide the content through
`::details-content`. Fixed by adding `details::details-content { content-visibility: visible
}` to the `@media print` block, beside the existing rule, which is kept for engines without
the pseudo-element. Confirmed by rendering, not only by computed style: WebKit under print
emulation paints the 49-row table (checked by screenshot), and the Chromium PDF above carries
its text.

### F11. A word ran into a link in the delivered HTML — FIXED

`/studies/a4/` shipped `The<a …>references section</a> records where it sits against prior
work` — Astro trims the whitespace between a word and an element that begins on the next
source line. One occurrence site-wide, found by eye in the print capture, then confirmed in
the built HTML. Fixed with an explicit `{" "}`. A check now scans every route's delivered
HTML for a word touching a link in either direction: `routes.spec.ts › no word runs into a
link, and no link runs into a word`.

### Smaller observations, not filed as findings

- The explorer's active-case line reads "Active case: J = 2 bbl/day/psi — J = 2 bbl/day/psi",
  because the template prints the key and the label and the label is the key restated.
  Editorial, visible in `screenshots/explorer-case-60-1440.png`.
- The contents rail is named by `aria-labelledby` pointing at its summary, which is
  `display: none` at desktop width. The name still reaches assistive technology, so this is
  legitimate; it does mean sighted desktop readers see an unlabelled list of links.
- `npx astro preview` daemonises and is a singleton per project, which makes it awkward in
  any automated check. Worth knowing before someone writes a second harness around it.

---

## 4. axe-core, in full

Ruleset: `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`, `best-practice`.

Scanned: all eight routes, `/404.html`, the explorer at `?case=60`, the explorer at
`?case=999` (the invalid-case state), and every route again with every `<details>` forced
open, because a closed disclosure hides its contents from axe. Each of those in Chromium,
Firefox and WebKit, at both base paths.

**Violations after the F1 fix: 0**, over 57 scans per run — 19 per engine: eight routes,
`/404.html`, the two explorer states, and the eight routes again with the disclosures open.
The machine-readable results are written to
`site/test-results/axe-<engine>-<port>-w<worker>.json`, one file per Playwright worker, each
recording the ruleset, the list of scans it performed and its violations. The scan list is
there so that an empty violation list can be read as "scanned and found nothing" rather than
"never ran": a single shared file name would let a worker that scanned nothing overwrite one
that did.

Before the fix, the only violation was:

| Rule | Impact | Where | Nodes |
|---|---|---|---|
| `aria-prohibited-attr` | serious | `/`, `/studies/a1/`, `/studies/a3/`, `/studies/a4/`, and both explorer states | every Plot mark group: `<g aria-label="dot">`, `"line"`, `"rule"`, `"text"`, `"x-axis tick"`, `"x-axis tick label"`, `"y-axis label"`, `"y-grid"`, `"rect"` |

**What axe did not cover, and is not evidence for.** axe checks programmatically detectable
failures. It says nothing about whether F01's long description is an accurate description of
F01; whether the heading text describes the section; whether focus order is sensible; whether
a dash pattern actually separates two lines on a screen; whether the reflow failure in F3
loses content (it does, and axe reported nothing); whether the contents rail was painted at
all (it was not, and axe reported nothing); or whether a colour that meets 3:1 is legible for
a given reader on a given display. Those were checked separately, by measurement or by eye,
below. Design target for this pass was WCAG 2.2 AA; this document does not claim conformance
to it, and F3 is a live 1.4.10 failure.

---

## 5. The manual review

### Measured mechanically, in `manual.spec.ts`

- **Skip link.** First stop in the tab ring, becomes visible on focus, and `Enter` moves both
  the address and the focus to `#main`.
- **Focus indicator.** Every stop in the tab ring on every route carries an outline of at
  least 1px, measured under real keyboard focus. Scripted `.focus()` does not set
  `:focus-visible` and the stylesheet correctly draws the ring only for `:focus-visible`, so
  the tests tab to each element rather than focusing it from script; measuring the wrong way
  would have reported a ring that a pointer user never sees.
- **Focus ring contrast.** `--c-focus` `#0b4fa8` against the ground it sits on, measured at
  six kinds of stop: 7.46:1 on the canvas, 7.78:1 on a card. The radios are clipped to 1px
  and the ring is drawn on their labels, which is the documented pattern; the test focuses
  the radio and measures the label.
- **No trap.** The tab ring on the case page with every disclosure open terminates, and
  `Shift+Tab` leaves wherever it ended.
- **Accessible names.** No empty name and no generic name ("here", "read more", "link",
  "download") on any link, button or summary on any route.
- **Alternatives.** Every figure carries a long description of at least 80 characters,
  associated by `aria-describedby`, plus one of: its own captioned data table, a pointer to
  the table that holds its numbers (F01b and F02 share F01's 49 rows), or the CSV that
  carries them (the home page's F01).
- **Second channel.** Every figure that uses more than one series colour also carries a dash
  pattern or a marker shape in the markup, and names its marks on the drawing.
- **Heading order** steps by one on every route and starts at a single `h1`.
- **Landmarks**: one banner, one labelled primary nav, one labelled contents nav, one `main`,
  one contentinfo, per route.

### Judged by eye

- The exported figures carry their own argument. F01 as a standalone SVG has its title,
  subtitle with the headline numbers, a legend showing dash and marker for each role, direct
  labels at the right end, the extrapolation warning on the extrapolated segment, the
  units and standard-conditions line, the synthetic-data statement, and an explicit sentence
  listing the non-colour channels. Extracted into someone else's document it still says what
  it is. That is the strongest thing in this design.
- State is carried by the word, not by colour. The status tables print BLOCKED, NOT RUN and
  NOT APPLICABLE as bordered word chips; there is no green tick and no composite score.
- The explorer reads honestly. The invalid-case notice names all eight computed cases, says
  "Nothing was interpolated", and shows the base case. The "presentation choice, not a rerun"
  sentence is above the control, not in a footnote.
- The selected control is distinguished by fill, by a heavier border and by weight, not by
  colour alone.
- The print output keeps all seven limitations and both `[SUPERSEDED]` blocks, with their
  labels, and drops only the header, the rail and the skip link.
- Against that: at 375 the exhibits are unreadable pictures (F2), and the metrics table is
  cut in half with no way to reach the numbers (F3). On a phone the case page currently fails
  at the thing it exists to do, which is to show a number and the error next to it.

---

## 6. Screenshots

In `site/screenshots/`, captured on macOS 26.6.2 (arm64) with Playwright 1.63.0 Chromium
153.0.8010.12 on 2026-09-13. These are captures for a person to look at, not pixel baselines,
and nothing in the suite compares image bytes. macOS and Linux rasterise text differently, so
a pixel comparison of these files against captures from a Linux runner would be meaningless.
`INVENTORY-chromium.json` alongside them records what each one is.

The case page is captured as its first screen rather than whole: a full-page capture of it is
about 30,000 pixels tall and 5 MB per width, which is a poor thing to put in a repository
three times. What a full-page capture would have shown is recorded as measurements in F3.

| File | Size | What is in it, and what I see |
|---|---|---|
| `home-375.png` | 375×4567 | Whole home page on a phone. Single column, no overflow, nav wraps to one row, the finding paragraph and "Synthetic throughout" both above the fold. F01 sits in the middle as an unreadable thumbnail — this is F2. |
| `home-768.png` | 768×3260 | Same, one column, comfortable measure. |
| `home-1440.png` | 1440×3231 | Measure holds at about 68 characters rather than filling the window. The figure is legible. |
| `a4-375.png` | 375×900 | First screen of the case page. "ON THIS PAGE" as a collapsed disclosure, h1 wrapping to three lines, the whole finding sentence with both numbers visible without scrolling. |
| `a4-768.png` | 768×900 | Same shape; the rail is still a disclosure at this width, correctly. |
| `a4-1440.png` | 1440×900 | The contents rail is on the right with all eight entries. Before the F8 fix this column was blank; that capture is what found it. |
| `a4-nojs-1440.png` | 1440×900 | Byte-identical to `a4-1440.png` (same SHA-256). Nothing above the fold depends on a script — no shift, no late render. |
| `explorer-case-60-1440.png` | 1440×900 | Deep link `?case=60`. The "60" control is selected, and the headline reads 174.005 Bscf and +74.005 percent, which is what `f01_f02_case-60.json` contains. The "Active case: J = 60 bbl/day/psi — J = 60 bbl/day/psi" duplication is visible here. |
| `explorer-invalid-case-1440.png` | 1440×900 | `?case=999`. The notice names the eight cases, says nothing was interpolated, and the base case is shown. The injected string is rendered as text. |
| `explorer-case-0-375.png` | 375×900 | The volumetric control case on a phone. The caveat callout reads well; the metrics table beside it is clipped, which is F3 again. |
| `explorer-nojs-1440.png` | 1440×900 | JavaScript blocked. No control, the static note instead, the base case complete with panels and downloads. This is the F9 fix. |
| `figure-f01-1440.png` | 816×764 | F01 alone at desktop width. Legend with dash and marker, direct labels, extrapolation warning, caveat lines, units. Legible, though the smallest text here is about 10.6px rather than 13. |
| `figure-f01-375.png` | 327×309 | The same exhibit at 375. Nothing on it can be read. The clearest single image of F2. |
| `metrics-table-375.png` | 375×900 | The metrics table at 375: Quantity column only, every value off-screen, no scrollbar, page will not scroll. The clearest single image of F3. |
| `a2-unavailable-1440.png` | 1440×5100 | The withheld study, whole page. No figure, no chart, no number standing in for a run that did not happen; the status table gives each check a word. |
| `a4-print-top.png` | 1440×1200 | Print stylesheet, first screen. Header, nav and rail dropped; h1, finding and synthetic statement kept. The lede paragraph runs the full window width while everything below it is capped to the measure — at an emulated 1440 that looks odd; on A4 at about 794px it is a much smaller effect. |
| `a4-print-limitations.png` | 1440×1200 | Print stylesheet at the limitations. All the limitation and superseded-claim blocks are present with black rules. This is the check that matters for a printed case report. |

---

## 7. The build-failure drill (check 13)

Run in an isolated copy of the tree under the scratch directory, never in the repository, with
`node_modules` symlinked. Baseline build there: exit 0. After each drill the file was
restored and the build returned to exit 0.

| Drill | What was done | Build | Message |
|---|---|---|---|
| A | removed `src/generated/figures/f03.svg` | exit 1 | `ExhibitError: figure "F03" is declared in the manifest but its SVG is missing.` |
| B | removed `public/data/f03_bias_sweep.csv` | exit 1 | `PublicDataError: download "f03_bias_sweep.csv" is missing.` and it lists what is present |
| C | removed `src/data/figures/f05_holdout.json` | exit 1 | `FigureDataError: figure data "f05_holdout.json" is missing.` |
| D | appended a line to a published CSV | exit 1 | `PublicDataError: download "f04_progressive.csv" does not match its recorded digest.` |
| E | added a key to a figure-data JSON | exit 1 | `FigureDataError: figure data "f07_z_mismatch.json" does not match contract.json.` |
| F | everything restored | exit 0 | — |
| G | edited a generated SVG by hand, left the manifest alone | exit 1 | `ExhibitError: figure "F01" is stale.` with both byte counts |
| H | edited a generated SVG **and** updated the manifest consistently, left the published copy stale | **exit 0** | none — this is F4 |

Drills A to E and G are the check the brief asked to re-confirm, and it holds: a mandatory
chart, a mandatory figure-data file, a mandatory download, a tampered download and a tampered
source all stop the build with a message naming the file. Drill H is the gap.

---

## 8. Measured payload

Built with `SITE_BASE=/reservoir-engineering-workbench-public/`, measured from `dist`.
gzip is level 9 over the file itself, as an indication of what a compressing server would
send; the server used in this pass does not compress.

| Page | raw B | gzip B |
|---|---|---|
| `studies/a4/index.html` | 568,670 | 81,342 |
| `methods/index.html` | 77,297 | 12,889 |
| `studies/a1/index.html` | 42,068 | 8,206 |
| `studies/a3/index.html` | 40,636 | 7,759 |
| `index.html` | 35,998 | 9,670 |
| `studies/index.html` | 13,720 | 4,358 |
| `studies/a2/index.html` | 13,091 | 4,725 |
| `about/index.html` | 10,916 | 3,807 |
| `404.html` | 4,654 | 1,468 |

Whole output: 1,642,174 bytes in 69 files, of which `data/` is 809,364 bytes of downloads and
CSS is 24,104 bytes. The case page is 4,617 bytes smaller than before this pass because F1
removed the mark-level ARIA attributes.

JavaScript: one inline module of 5,824 bytes, on `/studies/a4/` only. Every other page ships
zero script tags. Zero external script files, zero `@font-face`, zero `@import`, zero
analytics, zero cookies, zero `localStorage` or `sessionStorage` writes, zero `fetch`. The
only external host string anywhere in the output is `www.w3.org`, which is the SVG namespace
declaration and not a request; a test asserts that the set of hosts in the delivered HTML is
exactly `{www.w3.org}`.

---

## 9. What established what

**The tools established:** HTTP status and content type of every route and every referenced
file at both bases; the absence of console errors, page errors, failed requests and
off-origin requests in three engines; the absence of credential-shaped strings and
developer-machine paths in the delivered HTML; zero axe violations under a named ruleset;
every rendered text/ground pair against its WCAG target (322 distinct pairs per engine, 966
in total, lowest 5.33:1 against a 4.5:1 target, in each of the three engines independently,
which agrees with `decisions.md`'s own "lowest text ratio in the system: 5.33:1"); all 34 tabulated ratios in `decisions.md` §8 reproduced from
the served token values to within 0.02; document width and element geometry at five
viewports; the equality of what the explorer displays with what each case's own download
contains, for all eight cases; digests and byte counts of all 48 published downloads;
build exit codes under eight drills; and payload bytes.

**The contrast checker was verified before being trusted**, against the same published
reference values the design document used: black on white 21.00, `#767676` 4.54, `#777777`
4.48, `#0000FF` 8.59, white on white 1.00 — each reproduced to within 0.01.

**I judged by eye:** that the exported figures are self-explanatory out of context; that the
status tables carry state in words; that the invalid-case message is honest about what it did
not do; that the print output keeps the limitations; that the 375 exhibits are unreadable and
the 375 metrics table is unusable; and the editorial observations in §3. The screenshots were
opened and read, not generated and filed.

**Not tested at all:** real Safari or any iOS device; any screen reader (JAWS, NVDA, VoiceOver);
any reader; Windows high-contrast mode on Windows (only the `forced-colors: active` emulation,
which passed structurally); printing through a real print driver on paper, as distinct from
Chromium's PDF export; performance beyond byte counts; and the site under a real host, since
no remote exists.

---

## 10. Plus, minus, recommendation

**Plus.** The evidence survives everything that was thrown at it. With JavaScript blocked the
case page still carries nine exhibits, both tables, every caveat and working downloads. Every
figure is a standalone document with its own units, legend, non-colour channels and caveat.
Contrast is not merely asserted: every ratio in the design document reproduced from the
served tokens, and the lowest measured rendered text pair in the whole site is 5.33:1 against
a 4.5:1 target. The build refuses to produce a page from a missing or tampered input, which
seven drills confirmed. axe is clean at WCAG 2.2 AA plus best-practice on every route in three
engines, at both base paths.

**Minus.** On a phone the case page does not deliver its own finding: the metrics table is
clipped with no way to scroll to the numbers (F3) and the exhibits render at a size no one can
read (F2). F3 is a WCAG 2.2 SC 1.4.10 failure on four routes and it is made invisible by a
global `overflow-x: hidden`, which is the single most misleading line in the stylesheet. Two
defects found here — the blank desktop contents rail and the dropped print tables — had the
same cause, a CSS override written against a user-agent behaviour that browsers have since
changed, which suggests the stylesheet has not been re-verified against current engines in a
while. And a published download can silently stop being a copy of the figure it claims to
copy (F4), on a site whose argument is that you should be able to check things.

**Recommendation.** Fix F3 first and on its own: it loses content, it has a WCAG criterion
attached, and the fix is contained (make the scroll region a decision about measured width
rather than column count, and delete the `overflow-x: hidden` so that anything left over is
visible rather than hidden). Then take F2 and F6 together as one decision about how charts
behave on a narrow viewport — scroll at the authored size, or scale and drop the 13px claim
from `decisions.md`; either is defensible, but the document and the site should agree. F4 is
a ten-line addition to `emit-public-data.mjs` and worth doing while the reason is fresh. F5
and F7 are small and can wait for the next figure pass. After F3, this is a site worth putting
a domain on.

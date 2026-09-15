# Executive visual refactor — review candidate v2

**Status: READY FOR OWNER REVIEW. Not merged, not deployed.**

v2 brings A4 to the same standard as B1. The v1 scorecard named A4's noise as the
weakest dimension on the site and said the restructure was larger than it looked; this is
that work.

Branch `design/executive-visual-refactor`, from `22394a9b` (the published main, CI and
Pages both green at that commit).

## Objective

Make the main engineering insight of each flagship study legible to a technically
sophisticated reader in about thirty seconds, while every piece of rigorous evidence stays
on the page underneath. This is an information-design pass. No scientific result, input,
threshold, equation or conclusion changed.

## Scientific artefacts: confirmed unchanged

`scripts/check_science_frozen.py` records 116 protected files at `22394a9b` and fails if
any of them changes: every case protocol, result snapshot and run script, the library
source, the tests, the evidence cards, the release contracts and the 41 published
numerical downloads.

    $ python3 scripts/check_science_frozen.py
    science-frozen: 116 protected files
    science-frozen: PASS - every protected artefact is byte-identical

Two controls confirm the check can fail: nudging a B1 recovery value and appending a
sentence to an evidence card are both caught.

Nothing in this branch touches `cases/`, `src/`, `tests/`, `configs/`, `docs/evidence/` or
`site/public/data/`. The figure SVGs and PNGs are untouched, so no figure was re-rendered
and no canonical raster was disturbed.

## What the review found before anything was changed

The captures in `visual-review/before/` were taken against main as deployed. Four findings
drove the work:

1. **B1 was absent from the home page entirely.** The home page was wholly about A4. The
   portfolio's second flagship result did not appear until a reader reached the studies
   index.
2. **B1's central result was clipped off the screen.** The defect-visibility experiment was
   rendered as a seven-column table of scientific notation whose last column carried the
   verdict. At 1440 that column was cut off at the right edge, so the cell that said
   "wrong, and SILENT" was the one a reader could not see.
3. **B1 led with its least interesting number.** The opening sentence set
   `2000.00313 md·ft` and `3.50001594` in bold and put the silent-error finding at the end
   of a six-line paragraph.
4. **The home page spent its most valuable space on disclosures.** Test counts,
   continuous-integration detail and canonical-environment detail occupied a large block
   above the fold.

Two rendering defects were found and fixed on the way: six places site-wide where a word
ran into a following link or bolded value with no space ("of2000.00313", "and5 of 10"),
caused by Astro trimming whitespace before an element that begins a line; and two of those
predated this work.

## What changed

**Three new components.** `ExecutiveBrief` (question, finding, why it matters, biggest
limitation — the Level 1 read, never behind a disclosure), `KeyComparison` (one number
against the number it should be read against), and `DefectMatrix` (B1's experiment as a
classification rather than a table).

**Home page** rebuilt around the two flagship findings. Both headlines and A4's number
comparison are in the first viewport at 1440 and 768. Test counts, CI detail and canonical
environment detail are gone from the page — they are on Methods, which is where a reader
looking for them goes.

**Studies index** rebuilt as a progression rather than a catalogue. Each stage says what
its studies are for: A1 establishes the instrument, A3 measures its uncertainty, A4 shows
it failing while looking convincing; B1 establishes a second instrument and attacks it.
Each completed case now carries four things — question, finding, evidence status, link —
and nothing else. The status table moved below them.

**A4** gained an executive brief and a key comparison above the first figure, and figure
roles: F01 hero, F01b and F02 supporting, F03 through F08 technical.

**B1** restructured into the five parts the argument actually has: the instrument works;
several wrong interpretations remain internally convincing; why this matters; what this
does not establish; technical evidence. Part 2 is now the dominant section.

**Figure roles.** `Figure` takes `role="hero" | "supporting" | "technical"`. The role
changes visual weight and nothing else: identical caption, caveat, long description, data
table and downloads in every role, and no figure is hidden or removed.

**Display precision** is now decided in one place, `site/src/scripts/format.ts`, with a
stated justification per quantity rather than one global rule. B1 previously used eight
different precision rules on one page.

## What moved deeper, and was preserved

Nothing was deleted. Specifically:

| Content | Was | Now |
| --- | --- | --- |
| B1's seven-column scored defect table | the primary presentation | technical evidence, section 5, complete |
| B1's diagnostic, sampling, noise and negative-control figures | an undifferentiated Evidence section | technical evidence, marked `role="technical"` |
| Home page test counts, CI and canonical-environment detail | above the fold | Methods page, unchanged |
| Studies index methodological paragraphs | on the index | on each case page, next to the evidence they describe |
| A4 figures F03–F08 | equal weight with F01 | `role="technical"`, same content |
| Full-precision values | in page prose | in the downloads and case reports, which is where they were already |

## Accessibility

Full release browser suite, three engines: **504 passed, 15 skipped, 0 failed**.
`check_skip_policy.py` reports the skips clean.

Two accessibility regressions were introduced during the work and both were caught by the
existing suite and fixed:

- `KeyComparison` used a three-column grid that could not shrink, producing page-level
  horizontal scroll at 320px with the reader's text doubled (475px against a 320px
  viewport). It is now a wrapping flex row.
- `DefectMatrix`'s heading had the same defect, 14px over. Same fix.

No colour is the only channel anywhere in the new work: the silent-and-wrong group in the
defect matrix is marked by the reserved contrast colour, by its count, and by a heading
that says "and nothing showed it" in words.

## Performance

No framework, no icon package, no remote font, no CDN dependency, no analytics. The
architecture is unchanged.

| Page | Before (main) | v1 | v2 | Delta from main |
| --- | --- | --- | --- | --- |
| home | 34,930 B | 36,154 B | 36,205 B | +1,275 B |
| studies index | 16,574 B | 13,213 B | 13,213 B | **−3,361 B** |
| A4 | 574,700 B | 576,845 B | 581,861 B | +7,161 B |
| B1 | 166,800 B | 171,093 B | 171,312 B | +4,512 B |
| methods | 77,867 B | 77,886 B | 77,886 B | +19 B |

Net +9,606 B across five pages, about +0.7 percent. A4's increase is the executive brief,
the metric row and the new section prose; nothing was added to the figures. The built site is 14 MB before and
after; it is dominated by figure rasters, which this pass did not touch.

## Scorecard

Scored 1–5. The weakest dimension is reported rather than an average.

### Home

| Dimension | Score | Note |
| --- | --- | --- |
| Message | 5 | Two flagship findings, each stated as one sentence with its number |
| Hierarchy | 4 | Both headlines in the first viewport at 1440 and 768 |
| Noise | 4 | Disclosure block removed; the A4 figure is still large |
| Figure clarity | 3 | **Weakest.** F01 carries its own in-SVG title and six lines of footnote, so the page titles it twice |
| Decision relevance | 5 | Implication sits directly under each comparison |
| Limits | 4 | Scope line above the fold, full statement at the foot |
| Mobile | 4 | Hierarchy holds; the second finding is below the fold at 375, which is expected |
| Accessibility | 5 | Passes without colour and without JavaScript |

**Weakest: figure clarity.** The figure component renders a title above a figure that also
draws its own title, and F01's footnote block is six lines inside the frame. Fixing that
means changing the figure renderer, which would re-render every raster and pull the
canonical-figure harvest into a presentation pass. Deliberately not done here.

### A4

| Dimension | Score | Note |
| --- | --- | --- |
| Message | 5 | Title states the finding; the brief states it in one sentence |
| Hierarchy | 5 | The contents rail now reads as the argument, in order |
| Noise | 4 | Technical depth moved into one section; see the caveat below |
| Figure clarity | 4 | One hero, three supporting, four diagnostic, one technical; double-titling removed |
| Decision relevance | 5 | A dedicated engineering-implication section with a conditional recommendation |
| Limits | 5 | Biggest limitation in the first viewport; the full set and the four-statements scoping retained |
| Mobile | 4 | The brief stacks cleanly; wide plots keep their own scroll region |
| Accessibility | 5 | 504 tests pass; suppressed titles stay in the accessibility tree |

**Weakest: noise and figure clarity, both 4.** The hero section still measures about 940
words, but roughly 150 of those are page prose — the rest is the figure component's own
apparatus plus five or six lines of footnote drawn inside the canonical SVG. The renderer
is frozen in this pass, so the in-frame text cannot be reduced. What could be fixed at page
level was: the duplicate page-level title on all nine figures, and a caveat callout I had
added that restated the figure's own caveat.

### B1

| Dimension | Score | Note |
| --- | --- | --- |
| Message | 5 | Title states the finding; brief states it again with the count |
| Hierarchy | 5 | Five numbered parts; the attack is section 2, the recovery is section 1 |
| Noise | 4 | Technical evidence consolidated into section 5 |
| Figure clarity | 4 | One hero, four technical |
| Decision relevance | 5 | Section 3 exists only to state the implication |
| Limits | 5 | Six limitation callouts, none behind a disclosure |
| Mobile | 4 | Matrix wraps; verified at 375 and at 200 percent text |
| Accessibility | 5 | **The matrix is a definition list, not a grid of coloured boxes** |

**Weakest: figure clarity and noise, jointly.** The four technical figures are quieter but
still full-width; a reviewer scrolling section 5 still meets four large plots in sequence.

## v2: the A4 restructure

A4 was the weakest page after v1 and is now ordered by the argument rather than by
document convention:

| Layer | Section |
| --- | --- |
| Executive | Brief (question, finding, why it matters, biggest limitation) and three metrics — R-squared, the estimate, the known truth with its error |
| Hero | **A convincing line, the wrong inventory** — F01, then What to notice and Why it matters |
| Mechanism | **Why aquifer support moves the intercept** — support flattens the pressure history, a flatter history looks like a larger tank, the intercept moves out, and a gentle systematic bend is well approximated by a straight line so the fit statistic never objects |
| Evidence | **The bias grows before the fit looks poor** (F03, F04) and **A limited holdout the wrong model still passes** (F05) |
| Implication | What to do differently, stated conditionally |
| Depth | Limitations, then Technical evidence, the scenario explorer, the decision memo, reproduction and prior work |

**Figure roles.** One hero (F01), three supporting (F03, F04, F05), four diagnostic
(F01b, F02, F06, F07), one technical (F08). "Diagnostic" was added to the role set in this
pass: it answers "could this have been detected?" rather than "what went wrong?", and a
reader benefits from knowing which of the two a figure addresses.

**Double-titling, solved at page level.** Every canonical SVG draws its own title, and the
page was printing the same string as a heading directly above it — nine times on A4. The
renderer is frozen, so `Figure` gained `titleVisible={false}`: the title moves to
`.visually-hidden`, staying in the DOM, staying the `aria-labelledby` target, and staying
available to a screen reader, a printer and forced-colours mode. Nothing is stripped from
the graphic. The section heading above now carries the narrative and the figure's own title
carries its scientific identity.

**Two deletions I made and corrected.** The restructure initially dropped the scenario
explorer and the "Four statements, kept apart" callout. Both are restored — the explorer
into technical depth, the callout at the head of the limitations. I then ran a structured
audit comparing element counts, callout titles, table ids and prose openings against the
pre-restructure file; it found the second deletion, and three further prose openings which
I checked individually and confirmed are deliberate compression rather than loss. That
audit should have run before I first called the restructure done.

**One test was refined, with a control.** The long-label clipping check reported eleven
clipped labels on A4 — all of them the titles I had just moved to `visually-hidden`, which
sit in a 1px clipped box by construction and have no visible text to clip. The check now
skips elements by that geometry rather than by class name, so the exemption cannot be
claimed by adding a class to something genuinely cut off. Control: forcing a real visible
heading to clip makes the test fail and name it, while the eleven hidden titles stay
ignored.

## Review artefacts

    docs/release/visual-review/before/   15 captures against 22394a9b as deployed
    docs/release/visual-review/after/    the same 15 against this branch

Pairs worth looking at first: `home.png`, `b1-visibility.png` (the clipped table against
the classification), `b1.png`, `studies.png`, `a4.png`, and the three `-375.png` phone
captures.

## Local preview

    cd site
    SITE_BASE=/reservoir-engineering-workbench-public/ npx astro build
    QA_DIST=dist QA_PORT=4399 QA_BASE=/reservoir-engineering-workbench-public/ node tests/serve.mjs
    # then open http://127.0.0.1:4399/reservoir-engineering-workbench-public/

Do not run `npm run build` or `scripts/build_release.py` to preview: both begin by
re-rendering every figure, which replaces the canonical Linux rasters with local ones.

## What this pass deliberately did not do

- It did not touch the figure renderer. Every SVG and PNG is the committed canonical
  artefact. Fixing the double-titling and the heavy in-figure footnotes means re-rendering,
  and re-rendering in a presentation pass would put the canonical raster harvest at risk
  for no scientific gain.
- It did not restructure A4 as thoroughly as B1.
- It did not change the design tokens. The existing palette, contrast measurements, type
  scale, spacing scale and 68ch measure were already doing what this brief asks for; the
  problem was information hierarchy, not visual style.

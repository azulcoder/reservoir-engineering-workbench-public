# Design decisions for the case site

This file records decisions, not reading. The reading is in `research.md`, and where a
decision rests on a source that file says which one and what its access status was. Where a
decision rests on judgement instead, it says so in the decision.

The subject is one case: `cases/A4_misleading_fit_counterexample`, a synthetic
counterexample in which a volumetric p/Z fit to an aquifer-supported gas reservoir returns
R-squared = 0.999859 and a gas in place 12.50 percent too high. Everything the site displays
comes from that case's audited summary or from `scripts/export_presentation_data.py`, which
re-runs the case's own functions and reconciles 43 quantities against the audited summary at
a relative tolerance of 1e-12 before writing anything.

## 1. The audience and their tasks

Six tasks, written before any encoding was chosen, as the domain-characterisation level of
Munzner's nested model (S1). They are ordered by how early a reader needs them, not by
importance.

| # | Task | Who has it |
|---|---|---|
| T1 | Understand the question and the main finding within roughly thirty seconds | everyone |
| T2 | Inspect the assumptions, the alternatives that were ruled out, and what the case does not establish | reservoir engineer, referee |
| T3 | Interrogate an individual plot: read a value, compare two series, get the underlying numbers | reservoir engineer, data person |
| T4 | Verify that the run happened as claimed and that the numbers on screen are the numbers in the repository | referee, technical reviewer |
| T5 | Obtain the data and code that may be redistributed | anyone reproducing it |
| T6 | Understand what the author actually contributed, as distinct from what the physics literature already knew | technical reviewer, hiring reader |

The tasks are unvalidated. No reader has been observed performing any of them. Munzner's own
model is the source of that caution: validating a domain characterisation is a downstream
activity, and nothing downstream of a design document has happened yet.

## 2. Page structure

**D01. Martini glass, not a dashboard.** Segel and Heer (S3, full text) describe a structure
that "begins with an author-driven approach … Once the author's intended narrative is
complete, the visualization opens up to a reader-driven stage." The stem is: the question,
the headline number, F01, and the one-paragraph statement of why the straight line is wrong.
The bowl is: F02 to F09, each independently interrogable in any order, plus the verification
and download sections.

The reason is T1 against T3. A reader who wants the finding should not have to operate a
control to get it, and a reader who wants to attack the finding should not be prevented from
reaching any exhibit. A dashboard grid serves the second and fails the first; a linear
scrollytelling piece serves the first and fails the second.

**D02. Ordering within the bowl follows the case's own argument, not figure convenience.**
The order is: what the fit looks like (F01), whether the residuals gave it away (F02), how
the bias scales (F03), how it drifts with history length (F04), whether a holdout catches it
(F05), whether a detector catches it under noise (F06), whether the detector survives a
correlation mismatch (F07), whether the generator's own numerics are trustworthy (F08), and
how to check all of it (F09). That is the order of the case report, and reordering it for
visual variety would break the argument.

**D03. Each figure repeats its own units, replicate count and scenario identity.** Nielsen's
recognition-rather-than-recall heuristic (S8, full text): "the user should not have to
remember information from one part of the interface to another." This directly costs the
minimalism heuristic from the same source. The conflict is resolved in favour of repetition
for units, counts and provenance, and in favour of omission for everything else, because a
reader who misreads Bscf as scf misreads the finding by nine orders of magnitude.

**D04. No global filter, no cross-figure linked brushing.** Every figure is self-contained
and reads correctly in isolation, including when it is screenshotted into a review document.
This gives up the ability to select a scenario once and see it highlighted everywhere, which
would be genuinely useful for T3. It is given up because a screenshot of one figure from a
linked view is a figure whose state cannot be reconstructed, and the most likely way this
page gets read is one figure at a time in someone else's document.

## 3. T1 — the question and the finding

**D05. The finding is stated as a sentence with numbers, above the first figure.** The
sentence is: a volumetric p/Z fit to 49 quarterly noise-free observations of an
aquifer-supported reservoir returns R-squared = 0.999859 and a gas in place of 112.5 Bscf
against a true 100.0 Bscf, an overestimate of 12.50 percent, and the estimation error is
83.6 times the fit's reported standard error. No animated counter, no large number tile
without its units, no gauge.

**D06. R-squared and the error appear in the same sentence, always.** The point of the
case is that a close fit does not, by itself, establish that the volumetric assumption is
appropriate. Any layout that puts the fit
statistic in one place and the error in another — two adjacent stat tiles, for example —
invites the reader to treat them as two independent pieces of good and bad news, which is
the misreading the case exists to refute.

**D07. The word "synthetic" appears above the fold and in every figure's caveat line.** Not
in a footnote. The case's own report opens with "Synthetic throughout. No field data of any
kind is used, implied or represented", and a site that buries that has misrepresented the
work regardless of what its footnotes say.

## 4. T2 — assumptions and alternatives

**D08. "What this case does not establish" is a section of the page, not a collapsed
disclosure.** The case report carries seven such limits, including that this is not field
validation, that the numbers are not general, that trapped gas is not modelled, and that the
assumed existence of an unbiased average reservoir pressure is itself questionable. Putting
them behind a disclosure control would make them findable but not read.

**D09. Superseded claims stay visible and stay marked.** The report contains a
`[SUPERSEDED]` block: the first version called the closed-form 12.5 psi the half-power point,
and it is not — the measured power there is 0.432, and the half-power crossing is at
11.2 psi. The site renders the superseded claim, the correction and the direction of the
correction, because the audit trail is part of what is being demonstrated. Rendering only
the corrected number would be quieter and would remove the strongest evidence that the
author corrects himself.

**D10. Competing explanations are listed next to the finding, not after it.** A flattened
p/Z line admits several explanations besides aquifer support — an unrepresentative average
pressure, a correlation mismatch in the deviation factor, a geopressured reservoir. F07 in
particular shows that a mismatched Z correlation on a strictly volumetric history produces a
curvature statistic of −9.05, twice the aquifer's own +4.51 and opposite in sign. A page
that showed the aquifer result without that adjacent would be overselling a detector the
case itself does not trust.

## 5. T3 — interrogating a plot

**D11. Every figure has an always-available data table, and the table is the long
description.** The W3C complex-images tutorial (S11, full text) asks for a two-part
alternative — a short description that identifies the image and names where the long
description is, plus a long description that is "a textual representation of the essential
information conveyed by the image" — and demonstrates a data table inside a `figcaption`
serving that role. The tutorial's own argument for the adjacent-text approach applies here:
"the long descriptions are available to everyone." For this audience the table is a primary
artefact, not an accommodation, so it is disclosed with a labelled control (collapsed by
default for the 49-row tables, expanded by default for the tables under ten rows) rather than
hidden from sighted readers.

**D12. Hover is never the only way to read a value.** Tooltips are an enhancement. Every
quantity a tooltip would show is in the data table, and the keyboard path to it is the
disclosure control, not a simulated hover. The retrieved Observable Plot accessibility
documentation (S12) describes labelling the SVG root and mark groups via `ariaLabel` and
`ariaDescription`; it does not describe making individual data points keyboard-navigable,
and I am not going to claim per-point keyboard navigation that the library documentation
does not support.

**D13. Gridlines and band fills are declared non-information-bearing, and marked
`aria-hidden`.** This is the judgement WCAG 1.4.11 (S10) forces: the criterion applies to
graphical objects "required to understand the content", and I have to decide which are. Every
value a gridline would convey is also on a tick label, in the caption and in the table, so
the gridlines are allowed to sit at 1.25:1. Every mark that carries data meets 3:1. Section 8
lists both sides of that line explicitly so that the judgement can be checked rather than
taken on trust.

**D14. Direct labels on the emphasised series; a legend only where direct labelling would
overlap.** Wilke ch. 19 (S6, full text): "use direct labeling instead of colors when you need
to distinguish between more than about eight categorical items", and "qualitative color
scales work best when there are three to five different categories". The strength sweep has
eight scenarios, drawn as thin lines, which is the hardest case that chapter describes. So
F01 emphasises one scenario against a neutral ensemble and labels it directly, rather than
colouring all eight.

## 6. T4 — verifying the run

**D15. A provenance block (F09) renders the contract, not a badge.** `contract.json` carries
the SHA-256 of the audited summary, of the case source, of the protocol, of the exporter, and
of each of the seven figure JSON files, plus the count of reconciliation checks (43) and the
declared tolerance (1e-12). Those are rendered as text a reader can copy and check with
`shasum -a 256`, with the command shown. No green tick, no shield, no "verified" badge —
a badge asserts, a hash lets someone check.

**D16. The absences are displayed, not hidden.** Three NIST reference extracts are
deliberately not in this repository. Because of that, 20 tests in
`tests/test_gas_properties.py` skip with the message "NIST reference extract not present",
`cases/A2_pvt_independent_check/run.py` exits 1, and
`scripts/fetch_nist_reference.py --verify-only` exits 1 reporting 3 files MISSING. All of
that is stated on the page in those words. A page that showed a test count without its skips
would be making a claim the repository does not support.

**D17. No claim of hosted CI, peer review, field validation or deployment.** The workflow
file in `.github/workflows/` is a definition; unless and until a run of it is publicly
visible, the page describes what the checks are and how to run them locally, and says
nothing about them having run on a hosted runner. The referee pass the case report describes
was a review of the case, and the page describes it in exactly those terms — not as journal
peer review.

**D18. Any test-count statement must be rendered from a committed artifact or attributed as
a local measurement, with the command shown.** The counts measured while preparing this pass
were 633 tests, 613 passed, 20 skipped, but no exported file in the repository carries them,
so the page cannot render them as data. Either the site stream renders them from a committed
artifact that exists, or the page prints the command and lets the reader produce the numbers.
Inventing a number that no file contains would be the exact failure this case is about.

## 7. T5 and T6 — data, code and contribution

**D19. The download section lists only what may be redistributed, and says what is absent and
why.** The figure JSON files, `contract.json`, the case summary, the run records and the
source are all in the repository. The three NIST extracts are not, and the page says they are
not, and links to `scripts/fetch_nist_reference.py` as the route by which a reader obtains
them for themselves. No mirror, no copy, no embedded values, no "reconstructed" table.

**D20. The contribution is stated as the attack on the effect, not the effect.** The case
report is explicit: "This effect is not new and the case does not claim it is", and it cites
Pletcher (SPE 75354) and Dake for the prior work. What the case adds is the apparatus — a
pre-registered protocol, a bitwise reduction to the volumetric limit, a timestep-refinement
check, an estimator-free oracle, a matched pair of detector controls, and a measured power
curve. The page says that, in that order, with the prior work named above the fold of the
contribution section rather than below it.

**D21. The oracle's limits are stated where the oracle is shown.** The report withdraws an
earlier claim: the known-influx oracle is an algebraic rearrangement of the same governing
equation the generator solves, so it tests the solve and not the formulation, and "an
equation mis-transcribed identically in the generator and in the oracle would still close to
3.6e-11". The report also records that an independent from-scratch reimplementation exists
but is not a committed artifact of this repository. Both of those go on the page. The second
is the kind of claim that is easy to state and impossible for a reader to check, so it is
stated with that caveat attached.

## 8. Colour: measured, not asserted

Every pair below was computed with a WCAG 2.x relative-luminance calculator written for this
pass. Before trusting it, it was checked against published reference values: black on white
21.00:1 (published 21), `#767676` on white 4.54:1 (published 4.54), `#777777` on white
4.48:1 (published 4.48), `#0000FF` on white 8.59:1 (published 8.59), white on white 1.00:1.
It also produced genuine failures during this pass — an earlier `#B9B6AE` border measured
2.03:1 against the plot ground and 1.94:1 against the canvas — so the checker is known to
report a failure when one exists, and both failures were fixed by changing the colour, not
by lowering the target.

Targets: 4.5:1 for normal text (SC 1.4.3), 3:1 for large text, 3:1 for non-text marks, focus
rings and control boundaries (SC 1.4.11). All values are from `tokens.css`.

### Text pairs, target 4.5:1

| Foreground | Background | Measured | Use |
|---|---|---|---|
| `--c-ink` `#14181C` | `--c-canvas` `#FBFAF8` | 17.10:1 | body prose at 17px |
| `--c-ink` | `--c-surface` `#FFFFFF` | 17.84:1 | body on a card |
| `--c-ink` | `--c-sunken` `#F2F1ED` | 15.78:1 | body on a recessed panel |
| `--c-ink-2` `#434C55` | `--c-canvas` | 8.38:1 | secondary prose, table body |
| `--c-ink-2` | `--c-surface` | 8.74:1 | secondary on a card |
| `--c-ink-3` `#5B646D` | `--c-canvas` | 5.77:1 | captions and caveat lines at 15px |
| `--c-ink-3` | `--c-surface` | 6.02:1 | caption on a card |
| `--c-ink-3` | `--c-sunken` | 5.33:1 | caption on a recessed panel |
| `--c-blue` `#17518F` | `--c-canvas` | 7.71:1 | link text |
| `--c-blue` | `--c-surface` | 8.05:1 | link on a card |
| `--c-blue` | `--c-blue-tint` `#E8EEF6` | 6.89:1 | text inside a blue callout |
| `--c-blue-strong` `#0E3A6B` | `--c-canvas` | 10.96:1 | link hover, active, visited |
| `--c-contrast` `#A8400F` | `--c-canvas` | 5.91:1 | label for the mismatched model |
| `--c-contrast` | `--c-surface` | 6.17:1 | the same on a card |
| `--c-contrast` | `--c-contrast-tint` `#FBEDE5` | 5.39:1 | text inside a contrast callout |
| `--c-ink-2` | `--c-blue-tint` | 7.49:1 | prose inside a blue callout |
| `--c-ink-2` | `--c-contrast-tint` | 7.63:1 | prose inside a contrast callout |
| `--c-surface` | `--c-blue` | 8.05:1 | white text on a blue button |
| `--c-surface` | `--c-contrast` | 6.17:1 | white text on a contrast chip |
| `--c-ink-2` | `--c-plot-bg` `#FFFFFF` | 8.74:1 | axis tick labels at 13px |
| `--c-ink` | `--c-plot-bg` | 17.84:1 | direct series labels at 13px |
| `--c-ink-3` | `--c-plot-bg` | 6.02:1 | axis titles at 13px |

Lowest text ratio in the system: 5.33:1, against a 4.5:1 target.

### Non-text pairs, target 3:1

| Foreground | Background | Measured | Use |
|---|---|---|---|
| `--c-blue` | `--c-plot-bg` | 8.05:1 | observed-data series mark |
| `--c-contrast-mark` `#C04E13` | `--c-plot-bg` | 4.84:1 | the fitted wrong model |
| `--c-series-context` `#7F868C` | `--c-plot-bg` | 3.69:1 | neutral context series |
| `--c-ink` | `--c-plot-bg` | 17.84:1 | truth reference mark |
| `--c-border-strong` `#8A8981` | `--c-plot-bg` | 3.51:1 | axis line, zero rule |
| `--c-border-strong` | `--c-canvas` | 3.37:1 | input border, control outline |
| `--c-border-strong` | `--c-sunken` | 3.11:1 | input border on a recessed panel |
| `--c-focus` `#0B4FA8` | `--c-canvas` | 7.46:1 | focus ring on the page ground |
| `--c-focus` | `--c-surface` | 7.78:1 | focus ring on a card |
| `--c-focus` | `--c-blue-tint` | 6.67:1 | focus ring inside a tint |
| `--c-blue` | `--c-canvas` | 7.71:1 | selected control fill |
| `--c-contrast-mark` | `--c-canvas` | 4.64:1 | contrast chip on the page ground |
| `--c-series-context` | `--c-canvas` | 3.54:1 | context series on a canvas-backed plot |
| `--c-blue` | `--c-band-neutral` `#EFEEEA` | 6.93:1 | mark over a highlighted band |
| `--c-contrast-mark` | `--c-band-neutral` | 4.17:1 | contrast mark over a band |
| `--c-series-context` | `--c-band-neutral` | 3.18:1 | context series over a band |
| `--c-blue` | `--c-blue-tint` | 6.89:1 | mark over a blue band |
| `--c-contrast-mark` | `--c-blue-tint` | 4.15:1 | contrast mark over a blue band |
| `--c-ink` | `--c-blue-tint` | 15.28:1 | truth rule over a blue band |

Lowest non-text ratio among information-bearing marks: 3.11:1, against a 3:1 target.

### Deliberately below 3:1, and why

| Token | Against | Measured | Justification |
|---|---|---|---|
| `--c-gridline` `#E4E6E8` | `--c-plot-bg` | 1.25:1 | Declared non-information-bearing per D13: every value is also on a tick label, in the caption and in the data table. Marked `aria-hidden`. |
| `--c-band-neutral` `#EFEEEA` | `--c-plot-bg` | 1.16:1 | A fill marking an x-range. The range is also stated in the caption and delimited by a labelled `--c-border-strong` rule at 3.51:1. |

### Two values that failed and were changed

An earlier border token `#B9B6AE` measured 2.03:1 against the plot ground and 1.94:1 against
the canvas, against a 3:1 target. It was replaced by `#8A8981`, measuring 3.51:1 and 3.37:1.

An earlier context-series grey `#8A9096` measured 3.23:1 against the plot ground but only
2.85:1 against the recessed panel. Rather than exempt the recessed panel, the colour was
darkened to `#7F868C`, measuring 3.69:1, 3.54:1 and 3.26:1 against the three grounds.

## 9. Distinguishable without colour

WCAG 1.4.1 (S10, full text) is unambiguous: "Color is not used as the only visual means of
conveying information." Two checks were run on the actual token values.

**Greyscale.** The four chart series roles form a monotonic relative-luminance ladder, so
the figures survive greyscale printing and greyscale screenshots:

| Role | Token | Relative luminance |
|---|---|---|
| truth | `#14181C` | 0.0089 |
| observed | `#17518F` | 0.0805 |
| wrong model | `#C04E13` | 0.1670 |
| neutral context | `#7F868C` | 0.2346 |
| gridline (not a series) | `#E4E6E8` | 0.7891 |

The weakest greyscale separation in the set is wrong-model against neutral context, at
1.31:1. That is not enough on its own, which is why the second channel below is mandatory
rather than decorative.

**Colour-vision deficiency.** The four series colours were put through Machado-matrix
simulations for protanopia, deuteranopia and tritanopia. The closest surviving pair in each:
protanopia, observed against context, sRGB distance 90.4; deuteranopia, observed against
context, 105.6; tritanopia, observed against truth, 104.2. No pair collapses, but a distance
of 90 in sRGB is a similarity, not an identity, and the simulation is a linear approximation
rather than a test with a person.

**The mandatory second channel.** Because of both results above, every series carries at
least two non-colour channels:

| Role | Dash | Marker | Label |
|---|---|---|---|
| truth | fine dotted `2 3` | diamond | direct, at the right end |
| observed | solid | circle | direct, at the right end |
| wrong model | long dash `7 4` | none, because a fitted line has no observations | direct, at the extrapolated end |
| neutral context | sparse dotted `1 4` | square | named in the caption, not per-trace |

Any figure that uses only one series omits the dash pattern and uses solid, because a dash
pattern that distinguishes nothing is noise.

## 10. Typography and layout

**D22. System font stack only.** A case page whose argument is reproducibility should not
make its first paint depend on a third-party font server. This costs typographic character,
which is recovered through measure, scale and rules instead.

**D23. Body at 17px and 1.6 line height, measure at 68ch, shell at 1200px.** These are
conventional editorial values, not findings; no retrieved source in `research.md` gives a
tested measure or size, and this file should not imply otherwise. The scale is expressed in
rem so that browser text zoom and user font-size preferences work (SC 1.4.4), and no layout
depends on a fixed pixel block, so the SC 1.4.12 text-spacing overrides do not break it.

**D24. Chart labels never render below 13px.** That is the floor in `tokens.css`
(`--text-xs`). It is a common failure of chart libraries to ship 10px or 11px tick labels by
default, and the default must be overridden explicitly rather than inherited.

**D25. Tabular figures wherever numbers are compared.** Every table cell, chart label and
inline statistic uses `font-variant-numeric: tabular-nums`. Comparing +12.50 with +33.59 in
proportional figures makes the reader work for no reason.

**D26. 44px touch targets, with the standard quoted correctly.** The retrieved normative text
of WCAG 2.2 SC 2.5.8 Target Size (Minimum) is "at least 24 by 24 CSS pixels" at level AA. The
44px used here is stricter than that and is applied as a project rule. Neither retrieved
document states the numeric requirement of SC 2.5.5 Target Size (Enhanced), so this file does
not attribute 44px to WCAG. Inline links in running prose, which SC 2.5.8 exempts, keep their
line-height-constrained size.

**D27. Banned outright.** Purple gradients; glass and blur effects; heavy rounded tiles;
animated counters; three-dimensional oilfield imagery; decorative gauges; skill bars;
parallax; scroll hijacking; a dark dashboard chrome. All of them signal a genre — the product
landing page — that is the wrong genre for a case report, and several of them (animated
counters, gauges) actively distort a number that the entire page exists to state precisely.

**D28. No dark palette ships in this pass.** A dark set would need its own full measurement
pass and has not had one. Shipping untested dark values would defeat the purpose of measuring
the light ones.

## 11. What this research does not guarantee

Stated plainly, because the rest of this file reads more confident than the evidence
supports.

- **It does not guarantee a usability outcome.** No reader has been observed using this
  design. Munzner's nested model (S1, full text) is explicit that the outer-level threats —
  wrong problem, wrong abstraction — require downstream validation, and that "the immediate
  validations only offer partial evidence of success; none of them are sufficient to
  demonstrate that the threat to validity at that level has been addressed." Everything
  validated in this pass is immediate: contrast arithmetic, redundant channels, field
  existence.
- **The audience task list is a hypothesis.** It was written from judgement about who reads a
  case report, not from interviews, a survey or observation. If T1 and T6 are the wrong tasks,
  every decision downstream of them inherits that error.
- **Measured contrast is not measured legibility.** A 3.11:1 ratio conforms to SC 1.4.11. It
  does not establish that a particular reader, on a particular display, at a particular
  brightness, can comfortably distinguish a 1px context trace. Conformance is a floor.
- **The CVD check is a simulation, not a test with people.** Machado matrices are a linear
  approximation to three specific dichromacies. They say nothing about anomalous trichromacy,
  and Wilke's own instruction (S6) to test in a simulator is a weaker check than testing with
  readers.
- **It does not guarantee a hiring or reception outcome.** No retrieved source in
  `research.md` gives evidence about how a technical reviewer forms a judgement of a
  portfolio artefact. Every statement in section 7 about what a reviewer wants is judgement.
  A site built to this specification may be read as thorough or as laborious, and this
  research cannot distinguish those outcomes in advance.
- **Two sources were never read.** Munzner's *Visualization Analysis and Design* and Krug's
  *Don't Make Me Think* were reached only as a portal page and a sales page. Nothing here
  rests on either alone, and `research.md` records that.
- **The figure specification is grounded in the exported data, not in a rendered figure.**
  Every field named in `figure_spec.md` was checked to exist in
  `site/src/data/figures/*.json`. No figure has been drawn, so no claim is made about how any
  of these encodings looks at a real aspect ratio with real overplotting.

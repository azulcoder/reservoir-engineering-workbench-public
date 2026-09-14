# Design research: source register

This file records what I actually read, what claim I take from each source, how that claim
is applied to this site, and what the claim costs. It is a register of *findings from
sources*. My own design decisions are not here; they are in `decisions.md`, and where a
decision goes beyond what a source supports, that file says so.

Access status is recorded honestly, using three values:

- **full text retrieved** — the substantive body of the work was fetched and read in this
  session.
- **abstract or landing page only** — only the summary or the promotional page was
  retrieved. Anything I say about the body of the work is recall, and is marked as such.
- **recalled** — not retrieved in this session at all.

Date of retrieval: 2026-09-13.

## Register

| # | Source | Access status | What was actually retrieved |
|---|---|---|---|
| S1 | Munzner, *A Nested Model for Visualization Design and Validation* | full text retrieved | Landing page gave abstract only; the paper PDF linked from it (`NestedModel.pdf`) was fetched and its text extracted. |
| S2 | Munzner, *Visualization Analysis and Design* (book site) | landing page only | A resource portal: chapter list, 113 CC-BY figures, video lectures, slide decks, purchase links. No book text. |
| S3 | Segel and Heer, *Narrative Visualization: Telling Stories with Data* | full text retrieved | Landing page gave abstract only; the PDF at `idl.cs.washington.edu/files/2010-Narrative-InfoVis.pdf` was fetched and its text extracted (10 pages). |
| S4 | Wilke, *Fundamentals of Data Visualization*, ch. 16 "Visualizing uncertainty" | full text retrieved | Full chapter. |
| S5 | Wilke, ch. 4 "Color basics" | partial chapter retrieved | Sections 4.1–4.3 returned. The chapter does not carry the CVD guidance; that is in ch. 19. |
| S6 | Wilke, ch. 19 "Common pitfalls of color use" | full text retrieved | Fetched additionally, because S5 did not contain the guidance I needed and I did not want to attribute ch. 19 material to ch. 4. |
| S7 | Crameri, Shephard and Heron, *The misuse of colour in science communication*, Nat Commun 11:5444 (2020) | full text retrieved | Reached after two redirects through the publisher's identity provider. |
| S8 | Nielsen, *10 Usability Heuristics for User Interface Design* | full text retrieved | All ten heuristics with their explanatory text. |
| S9 | Krug, *Don't Make Me Think* (publisher page) | landing page only | A sales page. It contains no usability principles beyond the subtitle. Anything below attributed to Krug is recall and is marked. |
| S10 | WCAG 2.2 (W3C Recommendation) | full text retrieved, one criterion incomplete | Normative text for 1.4.1, 1.4.3, 1.4.4, 1.4.11, 1.4.12, 2.4.7. SC 2.5.8 was truncated in the fetched document and was retrieved separately from its Understanding page. |
| S11 | W3C WAI, *Complex images* tutorial | full text retrieved | Full tutorial. |
| S12 | Observable Plot, accessibility | source file retrieved; hosted page blocked | `observablehq.com/plot/features/accessibility` returned HTTP 429 twice. The same document was read from the project's own documentation source, `raw.githubusercontent.com/observablehq/plot/main/docs/features/accessibility.md`. |
| S13 | W3C WAI, *Understanding SC 2.5.8 Target Size (Minimum)* | full text retrieved for 2.5.8 | Fetched to complete S10. It quotes 2.5.8 in full; it does **not** state the numeric requirement of SC 2.5.5 Target Size (Enhanced), which it only refers to as stricter. |

## S1 — Munzner, nested model

**Claim taken.** Design splits into four nested levels — domain problem characterisation,
data and operation abstraction, visual encoding and interaction design, algorithm design —
and "the output from a level above is input to the level below, bringing attention to the
design challenge that an upstream error inevitably cascades to all downstream levels."
Each level has its own threat: "wrong problem: they don't do that; wrong abstraction:
you're showing them the wrong thing; wrong encoding/interaction: the way you show it
doesn't work; wrong algorithm: your code is too slow." Validation splits into immediate and
downstream, and the paper is explicit that "the immediate validations only offer partial
evidence of success; none of them are sufficient to demonstrate that the threat to validity
at that level has been addressed."

**How it is applied.** The audience task list in `decisions.md` is the domain
characterisation level, written before any encoding was chosen. The figure specification is
the abstraction and encoding level: each figure states the question first and the encoding
second. The contrast measurement is an immediate validation at the encoding level only.

**Trade-off.** The model's own honesty is inconvenient here. Everything this pass can
validate is immediate: contrast arithmetic, redundant encoding channels, data-field
existence. The threats at the two outer levels — wrong problem, wrong abstraction — can
only be validated downstream, by observing readers, and no reader has been observed. The
nested model is therefore also the source of the strongest limitation recorded in
`decisions.md`.

**Access status: full text retrieved.**

## S2 — Munzner, *Visualization Analysis and Design*

**Claim taken.** None taken from the book body, because none was read. The site is a
resource portal listing fifteen chapters, 113 downloadable figures under CC-BY-4.0, slide
decks and video lectures.

**How it is applied.** Not applied. I am recording it as consulted-and-not-read rather than
dropping it, because the brief listed it and the honest answer is that a textbook cannot be
cited from its portal page. Where a specific encoding-effectiveness ordering is used in
`decisions.md` (position on a common scale beats length, which beats area, which beats
colour, for quantitative comparison), that ordering is marked as recalled from the general
literature and is not attributed to this source.

**Trade-off.** The site's encoding choices would be better justified with the book's
effectiveness rankings in hand. They are instead justified from the data and the task.

**Access status: landing page only.**

## S3 — Segel and Heer, narrative visualization

**Claim taken.** Three constituents of the design space: genre, visual narrative tactics
(visual structuring, highlighting, transition guidance) and narrative structure tactics
(ordering, interactivity, messaging). Seven genres: "magazine style, annotated chart,
partitioned poster, flow chart, comic strip, slide show, and video." Ordering is "prescribed
by the author (linear), sometimes there is no path suggested at all (random access), and
other times the user must select a path among multiple alternatives (user-directed)."

The martini glass structure "begins with an author-driven approach, initially using
questions, observations, or written articles to introduce the visualization … Once the
author's intended narrative is complete, the visualization opens up to a reader-driven stage
where the user is free to interactively explore the data." The paper also records, as an
observed pattern, "the consistent under-utilization of 'tacit tutorials' and 'stimulating
default views'", and, in its critique of one case study, that a visualization "may suffer by
putting exploratory power into the hands of the viewer without sufficient guidance."

**How it is applied.** The page is a magazine-style annotated chart in a martini glass
structure: one linear author-driven path through the question, the finding and the
counter-checks, after which every figure becomes independently interrogable. Messaging is
carried by figure captions and caveat lines, which the paper classes as narrative structure
rather than decoration.

**Trade-off.** A martini glass concedes ordering control after the stem. A reader who jumps
straight to the strength sweep can read a 74 percent error without having read that the
generator is synthetic. The mitigation is that every figure carries its own caveat line
rather than relying on the reader having read the lede — which costs repetition, and makes
the page longer.

**Access status: full text retrieved.**

## S4 — Wilke, visualizing uncertainty

**Claim taken.** Error bars are ambiguous unless labelled: "Whenever you visualize
uncertainty with error bars, you must specify what quantity and/or confidence level the
error bars represent." Readers commit deterministic construal errors, reading an interval as
a range of possible values rather than as a probabilistic statement. Confidence bands
express the uncertainty of a fit, and a non-linear fit produces curved bands because slope
and intercept uncertainty combine. Frequency framing — waffle plots, quantile dotplots —
is easier to read than an abstract probability, because "we are much better at perceiving,
counting, and judging the relative frequencies of discrete objects."

**How it is applied.** Two places. First, the standard error of the fitted gas in place is
displayed only when it is displayed alongside its own bias, because the case's central
numeric point is that the bias is 50 to 88 times that standard error: an unlabelled error
bar here would be actively misleading, since it is a within-model interval around an answer
whose error is a model-structure error. Second, the detection rates in F06 are rates out of
a declared replicate count, and the frequency framing argues for stating "n = 400 of one
seed" and "n = 4000 of a different seed" on the figure rather than only in a footnote.

**Trade-off.** Frequency framing costs space, and the honest label for the fit's standard
error is longer than the number it qualifies. Following this source makes the figures
wordier.

**Access status: full text retrieved.**

## S5 and S6 — Wilke, colour

**Claim taken (S5, ch. 4).** Colour serves three distinct purposes: "we can use color to
distinguish groups of data from each other" (qualitative, unordered), "we can use color to
represent data values" (sequential), and colour can highlight, with diverging scales
representing "deviation of data values in one of two directions relative to a neutral
midpoint."

**Claim taken (S6, ch. 19).** "Qualitative color scales work best when there are three to
five different categories that need to be colored. Once we reach eight to ten different
categories or more, the task of matching colors to categories becomes too burdensome." "Use
direct labeling instead of colors when you need to distinguish between more than about eight
categorical items." For colour-vision deficiency: "To make sure your figures work for people
with cvd, don't just rely on specific color scales. Instead, test your figures in a cvd
simulator." And: "Colors are much easier to distinguish when applied to large areas than to
small ones or thin lines."

**How it is applied.** The strength sweep has eight scenarios. Eight is above Wilke's
comfortable qualitative range and at the edge of his "too burdensome" range, and the marks
in question are thin lines, which is the case he says is hardest. That is the whole reason
the scenario ensemble in F01 is drawn as a neutral grey backdrop with one emphasised
scenario and direct labels, rather than as an eight-colour spaghetti plot. The palette is
run through a CVD simulator, per the ch. 19 instruction, and the result is recorded in
`decisions.md`.

**Trade-off.** Direct labelling and a single emphasised trace mean the reader compares
scenarios sequentially rather than at a glance. The compensation is F03, which puts all
eight on a common position scale, and the data table, which puts all eight in text.

**Access status: S5 partial chapter retrieved (4.1–4.3); S6 full chapter retrieved.**

## S7 — Crameri, Shephard and Heron

**Claim taken.** Four criteria for a defensible scientific colour map: perceptual
uniformity, so "the same data variation is weighted equally across the dataspace";
perceptual order, where "both lightness and brightness should increase linearly to avoid the
perception of artificial gradients"; readability under colour-vision deficiency, noting that
"0.5% of women and 8% of men are subject to a colour-vision deficiency"; and greyscale
readability through "a uniform gradient across the whole colour axis" with a monotonic
lightness gradient. The failure mode of a rainbow map is stated as distortion, not just
taste: "an arrangement of colours can unfairly highlight a particular section of the
parameter space while obscuring other parts", and such maps "render the data unreadable for
readers with common colour-vision deficiencies."

**How it is applied.** This site has no continuous field to colour — there is no map, no
heatmap, no surface — so the rainbow-map argument does not bite directly. What transfers is
the greyscale-readability criterion, which I apply to the categorical series palette as a
monotonic luminance ladder: every chart series has a distinct relative luminance, so the
figures survive being printed in black and white or screenshotted into a greyscale
document. The measured ladder is in `decisions.md`.

**Trade-off.** Forcing a luminance ladder on a categorical palette means the series are not
of equal visual weight. That is acceptable here only because the series genuinely are not of
equal importance (observed data, wrong model, context), and it would be the wrong move for a
palette of peer categories.

**Access status: full text retrieved.**

## S8 — Nielsen, ten usability heuristics

**Claim taken.** All ten, with the four that actually constrain this page quoted.
Recognition rather than recall: "Minimize the user's memory load by making elements,
actions, and options visible. The user should not have to remember information from one part
of the interface to another." Aesthetic and minimalist design: "Every extra unit of
information in an interface competes with the relevant units of information and diminishes
their relative visibility." Match between the system and the real world: "Use words,
phrases, and concepts familiar to the user, rather than internal jargon." Visibility of
system status: "keep users informed about what is going on, through appropriate feedback
within a reasonable amount of time."

**How it is applied.** Recognition over recall is why units, replicate counts and the
scenario identity are printed on each figure rather than defined once at the top of the
page. Match with the real world is why the axes are labelled in psia, Bscf, bbl/day/psi and
years rather than in the exporter's field names. Minimalism is the argument against the
second y-axis on the bias sweep.

**Trade-off.** Recognition-over-recall and minimalism pull against each other: repeating the
units on every figure is exactly the "extra unit of information" the eighth heuristic warns
about. I resolve it in favour of repetition for units and provenance, and in favour of
omission for everything else.

**Access status: full text retrieved.**

## S9 — Krug

**Claim taken from the retrieved page: none.** The page is a sales page carrying the book's
subtitle, "A Common Sense Approach to Web (and Mobile) Usability", purchase links, and an
FAQ. It contains no principles.

**Recalled, and marked as recalled.** The book's central argument, as I recall it, is that
pages should be self-evident so that the reader spends no attention working out what things
are, that readers satisfice rather than optimise, and that they scan rather than read.

**How it is applied.** Only weakly, and only where another retrieved source says the same
thing. Scanning behaviour is the argument for a one-sentence finding at the top of each
figure, but Nielsen's recognition-over-recall heuristic (S8, retrieved) carries that weight
on its own. Nothing in `decisions.md` rests on this source alone.

**Trade-off.** None to record, because nothing depends on it.

**Access status: landing page only.**

## S10 and S13 — WCAG 2.2

**Claim taken.** 1.4.1 Use of Color (A): "Color is not used as the only visual means of
conveying information, indicating an action, prompting a response, or distinguishing a
visual element." 1.4.3 Contrast (Minimum) (AA): 4.5:1 for text, with large text — at least
18 point, or 14 point bold — permitted 3:1. 1.4.11 Non-text Contrast (AA): 3:1 for user
interface components and for "graphical objects" whose parts are required to understand the
content. 2.4.7 Focus Visible (AA): a visible keyboard focus indicator. 1.4.4 Resize Text
(AA): "Text can be resized without assistive technology up to 200 percent without loss of
content or functionality." 1.4.12 Text Spacing (AA): no loss of content at line height
1.5×, paragraph spacing 2×, letter spacing 0.12× and word spacing 0.16× the font size. From
S13, 2.5.8 Target Size (Minimum) (AA): "The size of the target for pointer inputs is at
least 24 by 24 CSS pixels", with five exceptions (spacing, equivalent control, inline,
user-agent control, essential).

**How it is applied.** These are the numeric targets the token palette is measured against,
and the measurement is reported rather than asserted. 1.4.1 is the source of the
redundant-channel rule: every chart series carries line style or marker shape plus a direct
label in addition to its colour. 1.4.12 is the reason the type scale is expressed in
unitless line heights and rem spacing rather than in fixed pixel blocks.

**Trade-off.** 1.4.11 applies to graphical objects "required to understand the content", and
deciding which objects those are is a judgement, not a measurement. I resolve it
conservatively: every mark that carries data meets 3:1, and the only things below 3:1 are
gridlines and band fills, which are declared non-information-bearing in `decisions.md` and
whose information is carried by the tick labels and the caption instead.

**Access status: S10 full text retrieved for six criteria, truncated for 2.5.8; S13 full
text retrieved for 2.5.8. Neither retrieved document states the numeric requirement of SC
2.5.5 Target Size (Enhanced) — S13 refers to it only as "stricter". The 44 px target used in
this design is therefore applied as a project rule, not quoted as a WCAG figure.**

## S11 — W3C WAI, complex images

**Claim taken.** A complex image needs "a two-part text alternative": "The first part is the
short description to identify the image and, where appropriate, indicate the location of the
long description. The second part is the long description — a textual representation of the
essential information conveyed by the image." Three delivery approaches are offered: a text
link adjacent to the image, a location named inside the `alt` attribute, and a structurally
associated description using `figure` and `figcaption`. Of the first: "All web browsers and
assistive technologies support this approach. The long descriptions are available to
everyone." The tutorial demonstrates a data table inside a `figcaption` as the long
description.

**How it is applied.** This is the single most load-bearing accessibility source for this
site. Every figure gets a short description that identifies it and names where the long
description is, plus a long description that is the data table itself, structurally
associated with the figure. The data table is not a fallback for screen-reader users only;
per the tutorial's own note, it is available to everyone, which also happens to serve the
reviewer who wants the numbers.

**Trade-off.** Nine expandable data tables add weight to the page and duplicate content that
is also in the JSON. I accept it, because for this audience the table is a primary artefact
rather than an accommodation.

**Access status: full text retrieved.**

## S12 — Observable Plot, accessibility

**Claim taken.** "The aria-label and aria-description attributes on the root SVG element can
be set via the top-level ariaLabel and ariaDescription plot options." Per-mark, "use the
ariaLabel mark option to apply per-instance aria-label attributes" and "use the
ariaDescription mark option for a longer description; this is applied to the mark's G
element". "Setting the ariaHidden mark option to true hides the mark from the accessibility
tree", which "is useful for decorative or redundant marks (such as rules or lines between
dots)". Axis and grid marks carry scale names such as "y-axis tick" or "x-grid".

**How it is applied.** It gives a concrete mechanism for the S11 two-part alternative if the
site stream chooses this library: `ariaLabel` for the short description, `ariaDescription`
for the long one, and `ariaHidden` on gridlines and band fills — which is the same set of
marks I already declared non-information-bearing for the 1.4.11 judgement above, so the two
decisions line up rather than conflict.

**Trade-off.** The retrieved document describes labelling the SVG and its mark groups. It
does not describe making 49 individual data points keyboard-navigable, and I should not
claim it does. Per-point interrogation therefore needs the data table, not the ARIA
attributes.

**Access status: source file retrieved from the project's documentation repository; the
hosted page at observablehq.com returned HTTP 429 on two attempts and was never read.**

## What these sources do not cover

Recorded so that `decisions.md` does not appear better supported than it is.

- No retrieved source addresses the specific problem of displaying a *known-wrong* model
  fit next to ground truth without implying that the site's own numbers are equally
  suspect. That framing problem is solved by editorial judgement alone.
- No retrieved source gives evidence about how a technical reviewer reads a portfolio
  artefact, or about what makes such a page credible. Every claim in `decisions.md` about
  reviewer behaviour is judgement, and is marked there.
- No retrieved source gives a tested typographic measure, size or line-height. The
  65–75 character measure and the 17–18 px body size in `tokens.css` are conventional
  editorial practice, not findings, and `decisions.md` says so.
- S4 (Wilke on uncertainty) is written for probabilistic uncertainty. This case's headline
  quantity is a model-structure error, which that chapter does not treat, and the gap is
  handled explicitly in `decisions.md` rather than by stretching the source.

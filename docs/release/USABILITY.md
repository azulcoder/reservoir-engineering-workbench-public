# Usability script, and its participation record

## Status: PENDING. No human participant has run this script.

Zero sessions, zero participants, no timings, no quotes, no endorsements. The script below
is written and has never been administered. Nothing in this file is a result, and no part
of the site's design has been validated by a reader.

That is said first rather than last because a usability script that looks complete reads
like evidence of testing, and this one is evidence only that the questions were decided in
advance.

## What this script is for

The site makes one claim about itself: that a reader can tell what the studies establish
apart from what they do not. Every honesty device on it — the fit statistic quoted in the
same sentence as the error, the limitation callouts, the NOT RUN rows, the "synthetic
throughout" banner, the explorer's refusal to interpolate — exists to serve that claim, and
none of those devices has been tested on anyone.

The script tests comprehension, not taste. It does not ask whether a reader likes the
layout. It asks whether the load-bearing separations survive contact with a stranger who
has fifteen minutes and no briefing.

It cannot test whether the engineering is right. A participant who finds every limitation
and reproduces every command has established that the page communicates; they have
established nothing about whether the p/Z estimator is correctly implemented. That is what
`docs/release/VERIFICATION.md` is for, and the two must not be quoted as if they were the
same evidence.

## Setup

Build and serve the site as a reader would see it, at the non-root project base, because
that is the shape a project site is served at:

```bash
# From the repository root. Install the site's dependencies once:
npm ci --prefix site

# One command builds and validates everything, into its own directory:
python3 scripts/build_release.py \
    --base-path /reservoir-engineering-workbench-public/ \
    --out-dir site/dist-project

# Then serve that exact directory:
cd site
QA_DIST=$PWD/dist-project \
QA_BASE=/reservoir-engineering-workbench-public/ \
QA_PORT=4321 node tests/serve.mjs
# open http://localhost:4321/reservoir-engineering-workbench-public/
```

The base path has to match in both halves. `npm run preview` on its own serves the
root-base build, so a session run that way would 404 on every page and the reader would
be told the site is broken when it is not. Serving the named directory avoids the
mismatch entirely, which is why it is the instruction here.

Verified on 2026-09-14: the project base returns 200, a deep route returns 200, a figure
download returns 200 and a missing page returns 404.

Give the participant the site root and nothing else. No repository tour, no explanation of
what the project is, no mention of which page holds the answer. If they ask what the
project is, the answer is "read whatever you like, and tell me what you find".

Record: start and end time per task, the path taken, what the participant said while
looking, and the answer they gave. Think-aloud. Do not correct a wrong answer during the
task and do not defend the design at any point in the session; a facilitator who explains
the page has destroyed the measurement the task was taking.

Twenty minutes total is the cap. A task that runs past three minutes is abandoned and
recorded as not completed, which is a finding and not a failure of the participant.

## Participants

Two profiles, because the two failure modes are different.

**P1 — reservoir engineer, or an engineer with material-balance background.** The risk with
this reader is that they recognise the p/Z plot, assume the standard reading, and never
notice that the study is about the standard reading being wrong. They are also the only
reader who can tell whether the engineering vocabulary is used correctly.

**P2 — technical non-specialist: a developer, scientist or analyst with no reservoir
engineering.** The risk with this reader is that the domain vocabulary — deviation factor,
pseudopressure, inventory in place — makes the page unreadable, and that the honesty
devices are invisible because the subject is opaque. They are the only reader who can tell
whether the caveats work without domain knowledge to lean on.

Aim for two of each. Four sessions is not a sample; it is a smoke test, and it is written
below as that.

## Tasks

Read the prompt aloud, verbatim. All seven tasks are given to both profiles.

### 1. Identify the study question

**Prompt.** "Find the flagship study and tell me, in your own words, what question it
asks."

**Path.** Home page, "Read the flagship case" link, or the Studies index, flagship card.
The question is in the first paragraph of the A4 page's Overview section.

**Correct outcome.** Some form of: a reservoir with an aquifer is being interpreted with a
model that assumes there is no aquifer — how good does the fit look, how wrong is the
answer, and could anyone have told from the data.

**Not correct.** "It's about material balance." "It shows how to fit a p/Z line." Both are
descriptions of the machinery rather than the question, and both mean the page led with the
method instead of the problem.

**What a failure would mean.** The flagship framing does not survive a reader who does not
already know what a counterexample is for.

### 2. Select the base case

**Prompt.** "The study computed several aquifer strengths. Show me the one it calls its
base case, and tell me how you know."

**Path.** A4 page, Scenario explorer. The radio group is labelled "Aquifer productivity
index J, bbl/day/psi — eight computed cases"; the base case option carries a "base" tag, and
the reset button names it.

**Correct outcome.** They select or point at J = 2, and cite the tag, the reset button or
the active-case line. A stronger outcome: they also notice that J = 0 is tagged "control"
and say what a control is doing in the sweep.

**Also worth recording.** Whether they expect the control to re-run anything. The page says
in text that changing the control is a presentation choice and not a rerun. If a
participant believes they just triggered a simulation, that sentence is not working.

**What a failure would mean.** The base case is not visually distinguishable from the other
seven, which matters because every headline number on the page is a base-case number.

### 3. Explain why R-squared is insufficient

**Prompt.** "This study reports R-squared of 0.999859. What does that tell you about how
good the gas-in-place estimate is?"

**Correct outcome.** That a close fit does not, by itself, establish that the volumetric
assumption is appropriate. The full answer has two parts, and partial credit should be
recorded as partial: (a) the fit is excellent and the estimate is 12.503 percent too high,
so the quality of the fit does not indicate the size of the error here; (b) the estimation
error is 83.6 times the fit's reported standard error, so tightening the interval would
make the answer more confidently wrong, because that standard error is conditional on a
model that has no influx term in it. The error is a model-structure error and a
model-structure error is not represented inside the fitted model.

**Not correct.** "It means the fit is very good, so the estimate is reliable." This is the
single most important failure to detect, and P1 is more at risk of it than P2.

**What a failure would mean.** The central finding of the whole project did not transfer,
and the sentence construction it relies on — fit statistic and error quoted together,
everywhere, never apart — is not strong enough.

### 4. Locate a limitation

**Prompt.** "Find something the study says it does not establish. Read it to me."

**Path.** A4 page, "What this does not establish", which holds seven limitation callouts,
including that it is not field validation, that the numbers are not general, that
detectability is the weaker half of the case, that the history is unrealistically clean,
that pre-registration rests on the author's word, and that no peer review took place. The
About page's "What is not claimed" and the Methods page's "What is NOT RUN, and why" are
equally correct answers.

**Correct outcome.** They find one within a minute and read it. Record which one they found
first — the ordering was chosen by the author and has never been checked against a reader.

**Stronger outcome, worth recording separately.** They find a limitation without being
asked, during an earlier task.

**What a failure would mean.** The caveats are placed where a reader who is looking for
them cannot find them, which makes every one of them decorative.

### 5. Identify which quantity is synthetic truth

**Prompt.** "Somewhere on this page there is a number the study knows exactly, because it
made it up. Which one, and how do you know it is not a measurement?"

**Path.** A4 page, explorer metrics table, the row "True gas in place" — 100.000 Bscf. The
"Synthetic throughout" statement near the top of the page is the supporting evidence.

**Correct outcome.** They name the true gas in place and can say why it is knowable: the
history was generated from a declared model with declared parameters, so the answer is an
input rather than an observation. P2 may phrase this as "the whole reservoir is made up",
which is correct and should be recorded as correct.

**Not correct.** Naming the fitted gas in place, or naming the R-squared. Naming the
pressure series is a near miss worth recording: the pressures are synthetic too, but they
are generated output rather than the declared truth the estimate is scored against.

**What a failure would mean.** A reader could carry these numbers away as measurements of
something. That is the failure mode the project can least afford.

### 6. Download the chart data

**Prompt.** "Get me the numbers behind one of these charts, as a file on this machine."

**Path.** Every figure carries a data download beneath it; the explorer carries per-case
CSV and JSON plus three full-dataset files; the "Reproduce, and download the numbers"
section lists the evidence downloads with sizes and descriptions.

**Correct outcome.** A file lands, and they can say which figure it belongs to. Record
which route they took and whether they hesitated between the per-case download and the
all-cases download — those two are deliberately labelled apart, and the labelling has never
been tested.

**What a failure would mean.** The claim that the evidence is inspectable is decorative if
the reader cannot get at it in under a minute.

### 7. Find the reproduction command

**Prompt.** "If you had this project on your machine, what would you type to produce these
results yourself?"

**Path.** A4 page, "Reproduce, and download the numbers":

```
PYTHONPATH=src python3 cases/A4_misleading_fit_counterexample/run.py \
    --out artifacts/A4_misleading_fit_counterexample/run-008
```

The Methods page's "Checking it yourself" carries the verification commands, which is an
equally correct answer.

**Correct outcome.** They find a command and can say what it would produce. A stronger
outcome: they notice that `--out` names a fresh directory and that runs are not overwritten.

**What a failure would mean.** Reproducibility is being asserted rather than offered.

## Recording sheet

One row per participant per task.

| Field | Note |
|---|---|
| participant | P1-a, P1-b, P2-a, P2-b |
| task | 1 to 7 |
| completed | yes / no / abandoned at cap |
| seconds | start to answer |
| path taken | pages and sections visited, in order |
| answer given | verbatim where possible |
| classification | correct / partial / incorrect / near miss |
| quotes | what they said while looking, not afterwards |
| facilitator note | anything the facilitator did that may have leaked the answer |

A finding from a session goes into the site stream's backlog as a specific change to a
specific page, with the participant and task that produced it named. A finding that cannot
be written that way is an impression, and impressions are recorded as impressions.

## Participation record

| | |
|---|---|
| Script written | 2026-09-13 |
| Sessions run | **0** |
| Participants | **0** |
| Dates | none |
| Findings | none |
| Status | **PENDING** |

No human participant has run this script. No session has been scheduled. The author cannot
run it on himself: he knows where every answer is, wrote every sentence being tested, and
cannot un-know either. Self-administration is not a session and would not be recorded as
one.

This script has also not been piloted, so it may itself be wrong — a prompt may leak its
answer, a task may take longer than the cap for reasons that have nothing to do with the
page, and the seven tasks may miss the thing that actually confuses people. The first
session is as much a test of the script as of the site.

### What running it would establish

Four sessions with two profiles would establish whether the load-bearing separations
survive a first reading: whether a stranger can state the question, tell the fit statistic
apart from the error, find a limitation unprompted, and recognise synthetic truth as
synthetic. On the specific failure in task 3 — a reader who reports that a high R-squared
means a reliable estimate — even one occurrence is worth acting on, because that reading is
exactly what the study exists to refute.

### What it would not establish

It would not be a statistically representative result, a measure of the site against any
alternative design, evidence that the engineering is correct, or peer review. Four readers
recruited by the author are four readers recruited by the author. Nothing in a session
speaks to whether the numbers are right, and a good session must never be cited as if it
did.

## Plus / minus / recommendation

**Plus.** The tasks are written against the specific claims the site makes about itself,
with the correct outcome and the failing outcome decided before anyone has been observed,
so a session cannot be read generously after the fact. Task 3 is the one that matters and
it is scored strictly.

**Minus.** It has been run zero times, which means the site's central honesty claim is
untested, and this document is a plan rather than evidence. The script is also unpiloted, so
its own failure modes are unknown, and four self-recruited participants would remain a smoke
test whatever they found.

**Recommendation.** Run one P2 session before any further site work. A non-specialist is
easier to recruit and is the harsher test of the caveats, and a single session would either
retire this PENDING status or produce a concrete page change — either of which is worth more
than another pass of authoring against an unread design.

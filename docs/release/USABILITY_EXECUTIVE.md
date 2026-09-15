# Usability script — the executive presentation

## Status: PENDING. No human participant has run this script.

Nothing in this file is a result. It is a procedure, and it stays PENDING until people who
are not the author sit through it. A script that has not been run tells you what someone
intended to measure, not what a reader understood.

## What this is for

The executive visual refactor is built on a claim that cannot be verified by a test suite:
that a technically sophisticated reader gets each flagship study's engineering lesson in
about half a minute, and that the lesson they get is the intended one. Every automated
check in this repository can confirm the page renders, reflows, passes contrast and carries
its evidence. None of them can tell you whether the reader came away believing the right
thing — or, worse, came away impressed by a precise number whose scope they did not absorb.

That last failure is the one this script is pointed at.

## Participants

Two profiles, because they fail differently.

**A — reservoir or subsurface reader.** Knows p/Z, knows what skin is, has interpreted or
reviewed a well test. Likely failure: recognises the physics fast and skims past the
scope, taking the numbers as more established than they are.

**B — technically literate, not a reservoir engineer.** Software, data, another engineering
discipline. Likely failure: cannot separate "this is synthetic and known-answer" from
"this was measured on a field", and so over-reads the whole portfolio.

Three to five of each is enough to find the structural problems. Do not recruit people who
have seen the site before.

## Running it

Ten to fifteen minutes. Screen share, think-aloud.

Read each prompt verbatim and then stop talking. Do not explain the page first — the page
explaining itself is the thing being tested. If a participant asks what something means,
write down that they asked and say "whatever you make of it is what I need."

Start on the home page with nothing else open.

## Tasks

**Home**

1. In one sentence, what is this project about?
2. What are the two most important findings here?

**A4** — let them navigate; record how they get there.

3. Something went wrong even though the p/Z fit looked excellent. What?
4. What would you want to know before using that x-intercept as an inventory basis?

**B1**

5. What is the main lesson of this case?
6. Are the six-digit recovery numbers the main finding? Why or why not?
7. What kind of analyst or input problem can stay completely silent here?

**Navigation**

8. Find the evidence behind the B1 silent-error claim.
9. Find the most important limitation of B1.
10. Download one data file that matches something you have just read.

Never ask "was that easy?" It produces agreement, not information.

## What to record

Per task: what they said, how long, what they clicked, and where they stopped and reread.

Then four things across the whole session:

- **Where they hesitated.** A pause at a heading is a heading that did not do its job.
- **What they remembered.** Ask at the end, unprompted, what they would tell a colleague.
  Compare with the intended lessons below.
- **What they misread.** Especially: any statement treating a synthetic result as field
  evidence, or a recovered number as a validated measurement.
- **Which visual they cited.** If nobody cites the B1 defect classification, the page's
  central redesign did not land.

## The intended lessons

Recorded here so that a reader's answer can be compared against something written down in
advance rather than judged after the fact.

| Page | Intended first takeaway |
| --- | --- |
| Home | Two studies about a convincing reservoir-engineering answer being wrong, for two different reasons |
| A4 | A convincing fit can still support the wrong physical model — fit quality is not model adequacy |
| B1 | An internally convincing interpretation cannot validate the inputs it was given |

A participant who says A4 is "about aquifers" or B1 is "about a very accurate well-test
calculation" has received a different lesson from the intended one. That is a finding about
the page, not about the participant.

## Failures that are page defects, not participant errors

- Answering task 6 with "yes, six significant figures is very accurate." The B1 page is
  built to prevent exactly this, and if it happens the number is still winning over its
  scope.
- Being unable to state the difference between A4 and B1 after reading both. The two are
  meant to read as model-structure risk and input risk; if they blur, the home page pairing
  is not working.
- Treating any number on the site as field-validated. Every page carries a synthetic
  statement; if it is not landing, it is placed wrong.

## Observation sheet

    participant: ____________   profile: A / B      date: __________

    task  time   answer in their words                     hesitation / misread
    1     ____   ______________________________________    ____________________
    2     ____   ______________________________________    ____________________
    3     ____   ______________________________________    ____________________
    4     ____   ______________________________________    ____________________
    5     ____   ______________________________________    ____________________
    6     ____   ______________________________________    ____________________
    7     ____   ______________________________________    ____________________
    8     ____   ______________________________________    ____________________
    9     ____   ______________________________________    ____________________
    10    ____   ______________________________________    ____________________

    unprompted recall at the end:
    ______________________________________________________________________

    did they treat any synthetic result as field evidence?   yes / no
    which visual did they cite first?                        ______________
    page changes this session suggests:
    ______________________________________________________________________

## What running this would and would not establish

It would establish how a small number of readers, on one sitting, understood pages they had
not seen before. That is the only evidence in this project about a human reader.

It would not establish that the studies are correct, that the site works for readers unlike
these, or that a recruiter or hiring reviewer forms the same judgement. Nothing here
substitutes for the scientific limitations each case already states.

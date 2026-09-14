# Protocols

A protocol in this repository is a study design written down before the study is run. It
fixes the engineering question, the experiments, the data-quality rules, the acceptance
thresholds and the conditions under which the result is allowed to be inconclusive, and it
does so while the answer is still unknown.

That is the whole point. Thresholds are easy to meet once the result is on the screen, and
an interpretation window is easy to choose once it is clear which choice flatters the
preferred model. A protocol removes those degrees of freedom in advance so that a passing
result means something and a failing result cannot be quietly rewritten into a passing one.

## What is here

| Protocol | Subject | State |
|---|---|---|
| [stage_b_pta_protocol.md](stage_b_pta_protocol.md) | Pressure-transient analysis on a synthetic gas well test | Written, not executed. No Stage B code and no Stage B result exists. |

Stage A's cases carry their protocols next to their code, in `cases/A1_volumetric_baseline/`,
`cases/A3_uncertainty_experiments/` and `cases/A4_misleading_fit_counterexample/`, because
those cases exist. This directory holds protocols for work that has not been built yet, where
there is no case directory to put them in.

## When a protocol is written

Before the code. `PLAN.md` section 11 puts pre-registration first in the working lifecycle:
the engineering question, the source basis, the comparison metric, the stopping criterion, an
independent oracle, and the acceptance thresholds, all fixed before the experiment runs.
`docs/case_protocol_template.md` is the skeleton; a protocol that only fills in the headings
without deciding anything is not a protocol.

A protocol may be amended. Amendments are appended to the change log at the end of the file,
with a date and a reason, and every affected exhibit is rerun. An amendment made after seeing
a result is labelled as such everywhere the affected result appears. Silently editing a
threshold is the one thing the whole practice exists to prevent.

## What a protocol establishes

It establishes what the study was designed to do, so that a reader can tell the difference
between a prediction that was tested and an observation that was explained afterwards. It
records which outcomes would have counted as failure, which would have counted as
inconclusive, and what would disprove the favoured interpretation. Those are checkable against
the result that eventually appears.

Where a protocol carries a digest of itself, the digest establishes integrity: the file has not
changed since the digest was computed. The rule for computing it excludes the block that holds
the digest, so the value is stable under its own insertion, and the file states the rule
explicitly so a reader can recompute it.

## What a protocol does not establish

It does not establish ordering. Nothing inside a file can prove when the file was written; a
digest can be recomputed at any time, and a modification timestamp can be anything. A protocol
that says "written before the run" is making a claim on the author's word.

The only ordering evidence this repository can offer is git history: the commit that first
contains a protocol, compared against the commit that first contains a result produced under
it. A reader who needs the ordering guaranteed should compare those two commits rather than
trust a sentence in a document. Where a case's tree was untracked at the time it ran, even
that evidence is absent, and the case protocol says so plainly instead of implying otherwise.

There is no external registry, no timestamping authority and no third party involved. This is
weaker than pre-registration in the sense the term carries in clinical or psychological
research, and it is described here as the weaker thing it is.

A protocol also does not establish that the work happened. A protocol for a study that has not
been run is a design document and nothing more. It must never be cited as evidence that the
study works, that the capability exists, or that the stage is under way.

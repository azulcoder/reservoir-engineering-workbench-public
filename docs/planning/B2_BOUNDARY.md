# B2 — planning boundary

**This is a planning document. It contains no result, no threshold that is not already
derived, and no pre-registration. B2 is not started.**

The next task after this one is research and pre-registration, in that order, and the
protocol commit comes before any result-producing code — the same order B1 used.

## Central engineering question

Can the interpretation recover permeability and skin when wellbore storage obscures the
early-time response and the valid radial-flow window must be identified from the diagnostic
rather than supplied?

## Why this, and why now

B1 established a pressure-transient instrument and then measured what it cannot see. To do
that cleanly it granted the analyst two conveniences, both declared in its protocol and both
named in its limitations:

1. **Wellbore storage is exactly zero by design.** Every real drawdown begins
   storage-dominated. The storage period hides the early semilog line and interacts with
   skin, and a high skin lengthens the distortion — which is precisely when it matters most.
2. **The interpretation window was handed to the estimator.** B1's own placement sweep
   measured what a wrong window costs: the permeability bias scales as `0.5196/t_D,min`,
   3322x across three and a half decades of placement, against 1.18x across a hundredfold
   change in sampling density. Placement dominates, and B1 did not have to find it.

B2 removes both. That makes it the first case in this project where the analyst must make
the hardest judgement in a real interpretation rather than being told the answer.

B1's report states the position plainly: *"the single hardest judgement in a real
interpretation is deciding where IARF begins and ends. B1 declares that window in advance
and the inverse does not choose it."*

## What the model does not yet have

- A wellbore-storage formulation and its coupling to the reservoir response.
- A treatment of the storage-to-radial transition.
- Any rule for identifying a flow regime from data rather than by declaration.
- A representation of how storage and skin interact in the early-time response.

## Research questions that need sources before a protocol exists

Each of these must be answered from literature, with its access level recorded honestly, in
the evidence card that precedes the protocol.

1. What is the governing equation for constant wellbore storage, and what dimensionless
   group expresses it?
2. What is the exact early-time behaviour under pure storage, and in what sense is the
   unit-slope signature exact rather than approximate?
3. How long does the storage-dominated period last, and what controls the transition to
   radial flow?
4. How do storage and skin interact — specifically, how does skin change the duration of the
   distortion?
5. What does the Bourdet derivative do through the transition, and what is the characteristic
   signature practitioners use to identify it?
6. What declared, mechanical rules exist for identifying a radial-flow window from a
   derivative response, and which of them can be stated precisely enough to implement without
   analyst judgement?
7. What test duration is required before the radial regime is observed for long enough to
   support an interpretation?
8. How does gauge noise degrade regime identification, as distinct from how it degrades
   parameter recovery once the regime is known?
9. Under what conditions is the problem not identifiable at all — that is, when do storage,
   noise and duration combine so that no unique interpretation exists?

Question 9 matters most. B1's value came from measuring a limit; B2's will come from
measuring where interpretation stops being possible.

## Candidate forward model

A line-source or finite-radius solution with constant wellbore storage and skin. The
standard dimensionless formulation uses a storage coefficient `C_D` and the group
`C_D e^{2s}`; whether this project implements the storage solution directly, by
superposition in Laplace space with numerical inversion, or by another route is an open
decision and is listed below rather than settled here.

Whatever is chosen must reduce to B1's storage-free solution as `C -> 0`, and that reduction
is a control, not an assumption — B2.0 exists to check it.

## Candidate inverse and diagnostic methods

- The B1 semilog interpretation, unchanged, applied to whatever window the diagnostic
  selects. Reusing it without modification is what makes B2 a test of window identification
  rather than a test of a new estimator.
- A declared regime-identification rule operating on the Bourdet derivative, stated
  mechanically enough to run without a human in the loop.
- A type-curve or `C_D e^{2s}` matching approach as a structurally different second path, if
  a defensible implementation exists.

Two structurally distinct paths remain a requirement, as in B1.

## Independent oracle options

The same difficulty as B1: the external-reference route is closed for the data-rights reason
that closed A2. Candidates, in descending order of independence:

1. The storage-free limit as `C -> 0` against B1's committed result — weak as independence,
   strong as a regression control.
2. A Laplace-space solution inverted by two different algorithms.
3. An arbitrary-precision evaluation of whatever special functions the solution requires.
4. The manual Saphir bridge, which is written and NOT RUN. B2 would make it more valuable
   than it is for B1, because storage and skin are exactly where a commercial package's
   conventions could differ from this project's. Prepared, not executed.

No GPL or otherwise incompatible source may be copied into this MIT repository.

## Data required

Synthetic throughout, as before. Nothing in B2 introduces field data.

- A storage-free control history reproducing B1's declared truth.
- Histories at several storage coefficients spanning short to long storage-dominated periods.
- Histories crossing the storage-skin interaction, including a high-skin case where the
  distortion is long.
- At least one history where the test is stopped before radial flow is adequately observed.
- Noise realisations at declared sigmas with declared seeds.

## Major failure modes to design against

- **Forcing an answer.** The most likely way B2 goes wrong is producing a confident
  interpretation on a test that does not support one. An INCONCLUSIVE verdict must be a
  first-class, pre-registered outcome with its own criterion, not a fallback.
- **A window rule tuned to the answer.** If the identification rule is adjusted after seeing
  which window recovers the truth, the case establishes nothing. The rule is pre-registered.
- **Reusing B1's thresholds.** B1's numbers were derived for a storage-free semilog window.
  They do not transfer, and B2's must be derived from its own error analysis.
- **A negative control that passes.** As in B1, a control that must fail and does not is
  itself a failure of the case.
- **Confusing regime misidentification with parameter error.** These are different failures
  and must be reported apart.

## Proposed experiment sequence

Listed for evaluation during pre-registration. Not implemented, and not final.

| | | |
| --- | --- | --- |
| **B2.0** | storage-free control | Reuse B1's declared truth. Does the new forward model reduce to the committed B1 result as `C -> 0`? |
| **B2.1** | pure wellbore storage | Finite `C`, otherwise B1's reservoir. Does the early-time unit-slope signature appear, and does the transition occur where theory says? |
| **B2.2** | storage and skin | How does skin change the duration of the distortion, and what does that do to the later radial response? |
| **B2.3** | window identification | The true window is not supplied. A declared diagnostic rule selects candidate radial-flow data. How often does it select correctly, and what does it cost when it does not? |
| **B2.4** | sampling and duration | When is the radial regime not observed long enough to support an interpretation at all? |
| **B2.5** | pressure noise | How does noise degrade regime identification, separately from parameter recovery? |
| **B2.6** | deliberately inconclusive | Conditions chosen so that no unique interpretation exists. The correct output is INCONCLUSIVE. |

B2.6 is the one worth defending. A study that can only succeed has not been tested.

## Open decisions

None of these is settled, and each needs an answer before a protocol can be written.

1. Direct storage solution, Laplace-space with numerical inversion, or another route?
2. Which numerical inversion algorithm, and what is its own accuracy oracle?
3. What exactly is the declared window-identification rule, stated so it runs without
   judgement?
4. Is B2.6's inconclusive verdict scored by a criterion, or by the absence of one?
5. Does B2 keep B1's semilog estimator unchanged, or does the storage case need a different
   inverse — and if it does, does that break the comparison B2.0 is for?
6. What is the acceptance structure when the answer is "this test cannot be interpreted"?

## Source research plan

Prefer original well-test literature and authoritative textbooks. Record access level per
source honestly — FULL TEXT INSPECTED, ABSTRACT ONLY, NOT ACCESSED — as the B1 evidence card
did, and derive rather than cite where a derivation is possible. Do not add copyrighted
material to the repository.

Target areas: wellbore storage governing response; the constant-storage assumption and where
it fails; the storage-to-IARF transition; storage and skin interaction; Bourdet derivative
signatures through the transition; regime identification; required test duration; sampling
effects; gauge and noise effects; and parameter identifiability under storage.

## What happens next

Research pass with an access-status table, then the evidence card, then the protocol as its
own commit before any result-producing code. Not this task.

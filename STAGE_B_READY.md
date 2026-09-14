# Stage B readiness

Stage A is published. Nothing in this file is a Stage B result; it records what exists,
what does not, and where the next piece of work starts.

## Where things are

| | |
| --- | --- |
| repository | https://github.com/azulcoder/reservoir-engineering-workbench-public |
| site | https://azulcoder.github.io/reservoir-engineering-workbench-public/ |
| default branch | `main` |
| foundation | 0.2, Stage A |

## What Stage A establishes

A dependency-free gas material-balance library with declared units, validity domains and
failure behaviour, and three synthetic case studies that reproduce from committed
snapshots. It establishes them under a reproducibility model worth stating precisely,
because the words are easy to overclaim:

- **Canonical byte reproducibility.** A1, A3 and A4 reproduce their committed snapshots
  byte for byte inside one pinned environment, defined by digest in
  `docs/release/canonical_environment.json`. No tolerance.
- **Cross-platform numerical portability.** On other supported platforms the same cases
  must pass their own acceptance criteria and a declared numerical envelope. Not byte
  identity, and not described as it.

## What Stage A does not establish

Unchanged by publication, and worth repeating because a deployed site invites the
opposite assumption:

- **No field validation.** Every case is synthetic. No production history, no real
  reservoir.
- **No external-reference validation.** A2 exists to compare the library against values
  it did not produce, and it cannot run here: the NIST extract is not redistributed. The
  `external-reference` profile has never run on the public host.
- **No commercial-simulator comparison.**
- **No peer review.** Every review pass was the same person under a different heading.
- **No human usability evaluation.** `docs/release/USABILITY.md` is a script nobody has
  sat through.
- **Gas in place is not reserves.** A1 and A4 recover an inventory under a stated model;
  neither is a reserves estimate and neither is certified.

## Stage B, and what is already in place for it

The protocol path is `PLAN.md`, Stage B: pressure-transient and rate-transient analysis.

Available now and reusable without modification:

- pseudopressure and its numerics, already exercised by the suite
- the Bourdet derivative and the Mattar-Brar-Aziz route, with their own evidence cards
- the provenance record type, the pre-registration convention, and the acceptance-criteria
  machinery the A-stage cases use
- the canonical execution model, the portability comparator and the two-tier CI, so a new
  case inherits the reproducibility story rather than reinventing it
- the figure pipeline, its contract and its display-precision rule

Missing, and needed before a Stage B case can be pre-registered:

- a declared well and completion model, with a stated skin and wellbore-storage treatment
- a synthetic drawdown/buildup generator with a documented noise model, in the same shape
  as the A-stage depletion generators
- acceptance criteria for a transient case, which are not the same criteria a material
  balance uses and should not be borrowed from one
- a decision about whether Stage B has an independent oracle at all, given that the
  external-reference route is closed for the same data-rights reason as A2

## Proposed first experiment

A single-well, single-phase, infinite-acting drawdown on a synthetic reservoir whose
properties are known exactly, testing one claim: that the semi-log straight line recovers
permeability and skin to a stated precision on noise-free data, and that the recovery
degrades in a documented way as the noise model is switched on. It is deliberately the
transient analogue of A1 — establish the instrument on a case where the answer is known
before pointing it at anything harder.

## Where to start

Stage B is not begun. The next prompt boundary is a pre-registration: write the protocol
and its acceptance criteria before any code that produces a number, in the same order the
A-stage cases used.

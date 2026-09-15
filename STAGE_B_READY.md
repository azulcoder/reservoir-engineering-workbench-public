# Stage B status

Stage A is published and **B1 is complete**. Everything below B1 in this file is still a
statement about work that has not been done. Nothing here about B2 through B6 is a result.

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

## B1 — complete

`cases/B1_iarf_known_answer/` — infinite-acting radial flow, known answer. The
pre-registration is its own commit, made before any result-producing code and never
amended, squashed or rebased since; the run embeds its SHA and re-derives its git blob
digest at execution time. Nine of nine pre-registered criteria pass -- eight recorded as
flags in the run's own output, and determinism, which no single run can record about
itself, verified by executing the case twice and diffing. The negative control
fails as it is required to, and the case has a site page.

What it establishes, exactly: *in this model, at these properties, over this window, the
instrument recovers the known answer to the stated precision.* Permeability-thickness to a
relative error of 1.56e-06 against a threshold of 1e-4; total skin to 1.59e-05 against
1e-3. Both thresholds were derived from an analytic error estimate before the run and
neither was moved afterwards, including when a criterion failed the first run.

The output worth carrying forward is not the recovery. It is the seeded-defect diagnostic:
of ten analyst errors, **five put a reported number materially wrong while leaving every
diagnostic available without the truth completely silent** — rate, net thickness, wellbore
radius, porosity and viscosity each leave r-squared at 1 to eight decimals. Nothing inside
a well-test interpretation can validate its own inputs, and B1 measures that rather than
asserting it.

What B1 does **not** establish: anything with wellbore storage, which is zero by declared
design and is the largest gap; anything about choosing the radial-flow window from data,
since the window was handed to the estimator; anything about a gas well, a rate history, a
boundary, or a real measurement. The independence achieved is between the forward and
inverse methods, not between this project and the world. No commercial package has been
compared against — `docs/bridges/saphir_b1_manual_validation.md` is a written procedure
with status SAPHIR MANUAL COMPARISON — NOT RUN.

## B2 through B6 — not started

Not implemented, not pre-registered, and not to be read as planned results. In the order
that makes each one useful:

- **B2 — wellbore storage, and finding the radial-flow window.** The direct successor to
  B1's largest gap. Storage hides the early semilog line and interacts with skin, and B1's
  own placement result shows the cost of getting the window wrong is roughly 0.52/t_D,min
  in permeability. This is the case that turns an instrument into an interpretation.
- **B3 — build-up, superposition and Horner time.** B1 is constant-rate drawdown only.
- **B4 — real gas: pseudopressure and pseudotime.** Despite the project's name, nothing in
  Stage B so far is a gas-well result; constant fluid properties are assumed throughout.
- **B5 — boundaries.** Faults, channels, closed systems, and whether the diagnostics
  distinguish a boundary-dominated straight line from a radial one.
- **B6 — a case against data this project did not generate.** The only one of the six that
  would change the independence claim rather than extend the model.

## What is already in place for a Stage B case

The protocol path is `PLAN.md`, Stage B: pressure-transient and rate-transient analysis.

Available now and reusable without modification:

- pseudopressure and its numerics, already exercised by the suite
- the Bourdet derivative and the Mattar-Brar-Aziz route, with their own evidence cards
- the provenance record type, the pre-registration convention, and the acceptance-criteria
  machinery the A-stage cases use
- the canonical execution model, the portability comparator and the two-tier CI, so a new
  case inherits the reproducibility story rather than reinventing it
- the figure pipeline, its contract and its display-precision rule

B1 added, and later cases inherit:

- `src/reservoir_lab/transient.py` — the line-source solution, its two exponential-integral
  branches, the dimensionless groups, and the semilog inverse, with every field constant
  derived rather than stored
- three bounded in-tree oracles plus a fourth behind an optional development pin, and the
  discipline of declaring each oracle's valid range rather than trusting it everywhere
- a transient acceptance-criteria set derived from analytic error estimates, which is the
  shape B2 should copy and not the numbers
- the seeded-defect visibility diagnostic, which is reusable and is the thing most worth
  running again on a harder case

Still missing, and needed before B2 can be pre-registered:

- a wellbore-storage model and a declared treatment of its interaction with skin
- a rule for identifying the start of radial flow from data, which B1 deliberately does not
  attempt
- a decision about whether Stage B has an independent oracle at all, given that the
  external-reference route is closed for the same data-rights reason as A2. The Saphir
  bridge is the cheapest available answer and it has not been run.

## Where to start

B2. The next boundary is a pre-registration, in the same order B1 used: the evidence
register with an honest access status per source, then the protocol and its acceptance
criteria as their own commit, then the code that produces a number. B1's thresholds are not
B2's and must not be borrowed; B1's *shape* — derive every threshold analytically before
the run, write a falsifiable expectation down so it can be wrong, and include a negative
control that must fail — is what transfers.

One correction from B1 worth carrying into B2's derivations: B1's protocol predicted the
window-placement bias as 1/(10 t_D,min) and the measured value was 0.5196/t_D,min, a factor
of 1.925 smaller, because a least-squares slope sees the departure projected over the whole
window rather than its value at the first point. The prediction cost nothing because the
threshold carried 64x of headroom, but a derivation that is off by a factor of two is one
that was not checked numerically before being written down.

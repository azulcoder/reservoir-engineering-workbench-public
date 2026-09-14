# Reference-data clearance

Dated 2026-09-14. This records what was removed from the release candidate so that the
project does not redistribute the NIST Standard Reference Data extract, what was kept,
and what was measured afterwards.

The values themselves are not restated anywhere in this document, in the changelog, in a
commit message or in a test fixture. Restating them would republish exactly what the
clearance withdrew, into records that are harder to correct than the files were.

## Why a new history rather than an edit

Removing a value from the current files does not remove it from the commits that
introduced it. The earlier candidate carried reference values in objects a working-tree
edit cannot reach, so the release was started again from the cleared snapshot instead.
The earlier repositories still exist locally, unchanged and unpublished. No commit,
author record, date or ref in them was altered to produce this one, and this repository
is not a continuation of either: its first commit has no parent.

## What was removed

| Category | Where |
| --- | --- |
| Retrieved reference values embedded as a fixture | `cases/A2_pvt_independent_check/run.py` |
| A verbatim row of the extract used as a parser fixture | `tests/test_gas_properties.py` |
| Reference values, and pointwise deviations against them, quoted in prose | `docs/evidence/viscosity.md`, `docs/evidence/provenance.md` |
| Values derived pointwise from a reference input | `docs/evidence/viscosity.md` |
| Aggregate error statistics summarising the withheld comparison | `docs/evidence/viscosity.md`, `tests/test_gas_properties.py` |
| An exemption granted on non-invertibility grounds | `docs/release/payload_exemptions.json` |

The fourth row is the one worth explaining, because it is the category that a search for
the withheld values does not find. A correlation evaluated on a reference density
contains no reference digit of its own. It is also strictly monotonic in that density, so
the published result inverts back to the input, and the recovered value agreed with the
withheld one to the limit of floating-point precision. Publishing the output of an
invertible function of a withheld input publishes the input. A viscosity quoted to three
significant figures through a steep exponential still pinned its input to four.

The last row follows from the same finding. An exemption had been granted to a
reference-derived quantity on the grounds that it could not be inverted. That reasoning
contradicted the register's own rule, and the demonstration above is why the rule is
right and the exemption was wrong. Both the figure and the exemption are gone.

## What was kept

The clearance targets the data, not the capability to check against it:

- the citation and the per-species reference equations
- the acquisition recipe, `scripts/fetch_nist_reference.py`
- the schema and loader, `tests/oracles/nist.py`
- the digest manifest, `data/reference/MANIFEST.json`
- the `external-reference` verification profile

An operator who acquires the extract under the provider's own terms runs every withheld
check locally. Without it, the public profile reports those checks as not run, with a
count measured from the suite's own skip reasons rather than asserted, and the
`external-reference` profile refuses to run at all rather than falling back to anything
bundled.

Also kept: published results that belong to someone else, such as a correlation's quoted
accuracy from its own source paper. Those are cited, not withheld — they were never this
project's to withhold.

## No acceptance criterion was weakened

Every gate, tolerance and assertion bound stands at the value it had before the
clearance, including those whose observed margins are no longer published. What was
removed is the *observed* side of comparisons against withheld data, never the bound
being tested. A criterion relaxed to accommodate a removal would make every remaining
check worth less than nothing, and the release would be reporting its own convenience.

One consequence is visible in the text: several passages now state that a margin is
narrow without saying how narrow. That is the intended trade. The bound is public, the
measurement against withheld data is not.

## Screens added

Two, each with regression tests that fire in both directions. A screen that fires on
everything is not a screen, so every positive fixture is paired with a negative control
that must stay silent.

- **Derived-value probe.** Flags a high-precision number standing beside a statement that
  it was computed from the restricted extract. It carries its own threshold rather than
  the provenance probe's: the provenance probe guards against a table pasted next to a
  citation, where a dozen numbers is the signal, whereas one invertible value is already
  one whole reference datum. Reusing the higher threshold let a six-value reconstruction
  through during development, which is what the threshold test now protects.
- **Sentinel fixtures**, in `tests/test_release_payload_guard.py`, covering an embedded
  extract with every provider marker stripped, a disallowed pointwise source/derived
  combination, and a restricted input attempting to re-enter through the package. Every
  fixture is invented. A test that embedded the real payload to prove the payload is
  excluded would put it back by the door it guards.

The exemptions register is exempt from the derived-value probe alone, because it must
quote the numbers it excuses beside prose saying what they were computed from, and
scanning it there produces a finding about a finding. The carve-out is one path wide and
the register remains subject to the other two screens, which is asserted by test rather
than claimed here.

## Measured afterwards

Counts are from a run, not from the previous tree's declaration. A count-drift guard in
`scripts/build_release.py` fails the build when the site's declared figures disagree with
what a run measures, and it is what caught the stale figures after the sentinel tests
were added.

| Quantity | Before | After |
| --- | --- | --- |
| tests collected | 667 | 683 |
| tests passed | 647 | 663 |
| tests failed or errored | 0 | 0 |
| tests skipped | 20 | 20 |
| checks collected / passed | 9 / 9 | 9 / 9 |

No test was removed and none was newly skipped. The sixteen added are the sentinel
regression tests. The twenty skips are the same twenty reference-dependent tests as
before, carrying the same single recorded reason; the clearance did not create a skip.

Tests that changed rather than moved:

- `tests/test_gas_properties.py` — the parser fixture row is now invented rather than
  taken from the extract. The tests around it exercise the parser, the schema and the
  digest guard, none of which depends on what the numbers mean, so they still run and
  still assert. Four dependent assertions were updated to the new row.
- `tests/test_gas_properties.py` — observed error statistics were removed from comments
  and docstrings. Every assertion and every threshold in those tests is untouched.
- `cases/A2_pvt_independent_check/run.py` — the viscosity positive control no longer
  compares against embedded reference anchors. It evaluates the published closed form on
  invented states and checks the zero-density limit and the unit conversion, so it
  remains a positive control for the instrument without being a comparison against data
  this project does not redistribute.

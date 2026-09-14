# Reference fluid properties

## Status in this repository: not distributed

The three tab-separated reference tables this directory describes are **deliberately
absent** from the public repository, and from its git history. What is kept here is the
metadata that makes them reproducible and verifiable: `MANIFEST.json` records the exact
request URLs, the declared units, the row counts, the per-property citations and a
SHA-256 digest of each file. The numbers themselves are not published here.

The reason is a rights question, not a size or convenience question, and it is set out
in full in [`docs/release/PUBLIC_DATA_POLICY.md`](../../docs/release/PUBLIC_DATA_POLICY.md).
The short version is below.

## Why the numbers are not here

The repository previously framed the NIST requirement as **attribution**: cite the
source and the per-species reference equation, and the extract may travel. That framing
was wrong, and it is corrected here.

NIST Standard Reference Data is a statutory exception to the usual rule that works of
the United States Government are in the public domain. The Standard Reference Data Act
(Public Law 90-396) lets the Secretary of Commerce assert copyright in SRD, and the
Chemistry WebBook does assert it: the site footer reads

> (c) 2026 by the U.S. Secretary of Commerce on behalf of the United States of America.
> All rights reserved.

NIST's SRD public-law page states

> None of our SRD may be reproduced, stored in a retrieval system or transmitted, in any
> form or by any means, electronic, mechanical, photocopying, recording or otherwise,
> without prior permission.

That page carries NIST's own banner saying it is no longer being updated, and the
WebBook's structured metadata points at a current licensing statement instead. The
current statement does not repeat the "may not be reproduced" sentence, but it separates
Standard Reference Data from a distinct fair-use section that it scopes to data and
works **not** covered by the Standard Reference Data Act. Both readings of the current
page leave the same gap: nothing retrieved establishes that citation alone permits
redistributing an SRD extract.

So this project takes the non-redistribution route. That is a
conservative publication decision, and it is explicitly not an adjudication of copyright
exceptions. No claim
is made here that redistribution would be infringing, that a fair-use or de-minimis
argument would fail, or that some other project distributing WebBook values is doing
something wrong. The claim is narrower and is the only one the retrieved evidence
supports: permission to redistribute has not been established, an unestablished
permission is not a permission, and a public repository is the wrong place to find out.

The evidence behind this, with retrieval dates and the disagreement between the two NIST
pages, is recorded in `docs/evidence/provenance.md`.

## What these files are, when you have them

Pure-component thermophysical properties for methane, carbon dioxide and nitrogen,
retrieved from the NIST Chemistry WebBook, SRD 69, isothermal fluid-property interface
(<https://webbook.nist.gov/chemistry/fluid/>).

Five isotherms at 100, 160, 200, 260 and 320 degF, swept from 200 to 6000 psia in
200 psia steps: 150 states per species after removing the duplicate rows the service
emits at a phase-label boundary. The removal count is recorded per file in
`MANIFEST.json` rather than performed silently.

## What they are not

They are **not laboratory measurements**. They are values produced by the reference
equations of state and transport models that the WebBook evaluates. `MANIFEST.json`
records which model NIST cites for each species' density and viscosity, so the chain
from a number in a test to a published correlation is traceable.

They are also not a validation of anything multicomponent. Agreement between a
correlation and pure methane says nothing about that correlation's accuracy for a real
field gas with heavy ends, nitrogen, CO2 and a condensate dropout. That limitation is
repeated in every case report that uses these values.

## How they are used

As an **independent oracle** for the Z-factor and viscosity correlations in
`reservoir_lab.gas_properties`. Independent in the sense that matters: the values come
from a different model family (multiparameter Helmholtz-energy reference equations of
state), produced by a different organisation, and share no code with the correlations
under test. Agreement is therefore evidence; disagreement localises to one side.

The pure-component gas gravity used to enter the pseudo-reduced correlations is derived
from the species' molar mass, and the resulting comparison is reported as a *correlation
error*, not as an implementation error, wherever the deviation sits inside the accuracy
the correlation's own authors published.

## Effect on the test suite

Without the extract, the tests that need it skip rather than fail, with the message
`NIST reference extract not present`. In the published tree that is 20 skipped tests out
of 633. Nothing else in the suite depends on the extract, and no case study under
`cases/` reads it except `A2_pvt_independent_check`, which exits non-zero and says the
reference table is absent rather than producing a result from nothing.

A skip is honest here and a stub would not be. There is no substitute oracle: replacing
the reference equations of state with a second correlation would compare two members of
the same model family and would look like agreement while measuring nothing.

## Obtaining the extract for your own use

Acquisition is a deliberate, manual act performed by you, under an access basis you can
state. It is not run by the test suite, by CI, by an installer or by any default path.

```
python3 scripts/fetch_nist_reference.py acquire \
    --out /path/outside/this/checkout \
    --access-basis "your own recorded basis for retrieving and using these values"
```

Read `python3 scripts/fetch_nist_reference.py --help` before running it. The script
refuses to run without an explicit output directory and a recorded access basis, and it
will not write into a directory that is reachable by this repository's publication path
unless you override that deliberately. There is no `--accept-terms` flag, because
clicking past a prompt is not evidence of permission.

Having retrieved the values, verify them against the recorded digests:

```
python3 scripts/fetch_nist_reference.py verify --out /path/outside/this/checkout
```

`verify` touches no network. It re-hashes the stored files against `MANIFEST.json` and
fails on any drift, so a silently edited reference file cannot quietly make a failing
test pass. It is the right gate for a working checkout that holds the extract, and the
wrong gate for the published tree, where the files are supposed to be missing. The
published tree is checked by `scripts/check_public_release.py` instead.

## Citation

Whether or not you redistribute anything, cite the NIST Chemistry WebBook, SRD 69,
together with the per-species reference equation recorded in `MANIFEST.json`, wherever
these values or results derived from them are reported. Citation is required. It is
simply not, on the evidence retrieved here, sufficient on its own to license
redistribution.

# Public data policy

Status: active. Decided 2026-09-13, at the point of preparing a public tree.

## The decision

This project does not redistribute the NIST Chemistry WebBook reference extract it uses
as an independent PVT oracle. The three tab-separated tables are absent from the public
repository and from its git history. What is published in their place is metadata:
`data/reference/MANIFEST.json` records the exact request URLs, the declared units, the
isotherms and pressure grid, the row counts, the per-property citations and a SHA-256
digest of each file, and `data/reference/README.md` explains what the files are and how
to retrieve them yourself.

This is a conservative publication decision. It is **not an adjudication** of copyright
exceptions, it is not legal advice, and it is not a finding that redistribution would
infringe. It says only that permission to redistribute has not been established from the
sources retrieved, and that a public repository is the wrong place to test the question.

## What the previous framing got wrong

An earlier revision of this repository framed the NIST requirement as **attribution**:
cite the WebBook and the per-species reference equation, and the extract may be
published alongside the code. `data/reference/MANIFEST.json` carried a field called
`attribution_required` that read as if satisfying it settled the matter.

That was wrong, and it is marked here as superseded rather than quietly rewritten.
Attribution and redistribution are different permissions, the way access and
redistribution are different permissions, and the repository's own data policy already
said so about field datasets while getting it backwards about this one. Citation is
still required. It is simply not sufficient.

## The evidence

All three items below were retrieved on 2026-09-13 and are recorded with their dates in
`docs/evidence/provenance.md`. They are quoted, not paraphrased, because the wording is
the whole question.

NIST Standard Reference Data is a statutory exception to the usual rule that works of
the United States Government are in the public domain. The Standard Reference Data Act,
Public Law 90-396, lets the Secretary of Commerce assert copyright in SRD, and the
Chemistry WebBook does assert it. Its footer reads:

> (c) 2026 by the U.S. Secretary of Commerce on behalf of the United States of America.
> All rights reserved.

NIST's SRD public-law page states:

> None of our SRD may be reproduced, stored in a retrieval system or transmitted, in any
> form or by any means, electronic, mechanical, photocopying, recording or otherwise,
> without prior permission.

That page is the strongest-sounding source and it is also the weakest one, which is why
it is not relied on alone: NIST's own banner on it says the page is no longer being
updated and may be out of date. The WebBook's structured metadata designates a different,
current licensing statement. That current page does not repeat the "may not be
reproduced" sentence. It does something that matters more for this decision: it
separates Standard Reference Data from a distinct fair-use section which it scopes to
data and works **not** covered by the Standard Reference Data Act. Reading the current
page on its own, the fair-use language does not reach WebBook output.

So the two pages disagree in tone and agree in effect. Neither establishes that citation
alone permits redistributing an SRD extract, and no carve-out for small extracts or for
scientific use was found on either.

## Why the conservative route, and not the argument

A defensible fair-use or de-minimis argument may well exist for 450 rows of
thermophysical values used as a test oracle. The point is that this project would have
to make that argument, and would be making it in public, about somebody else's asserted
copyright, with no advice and nothing at stake for anyone but its author. The cost of
being wrong is asymmetric: a takedown against a public repository, and a rewrite of a
history that is supposed to be an audit trail.

The cost of the conservative route is 20 skipped tests. That is a price worth paying,
and stating it plainly is better than a stub that pretends the oracle ran.

## What is published, and what is not

Published:

- `data/reference/MANIFEST.json` -- request URLs, units, isotherms, grid, row counts,
  per-property citations, SHA-256 digests, and the redistribution decision.
- `data/reference/README.md` -- what the values are, what they are not, how they are
  used, and how to retrieve them.
- `scripts/fetch_nist_reference.py` -- the acquisition recipe, readable without running.

Not published, in any format:

- The three isotherm tables themselves.
- Any table, chart series, figure payload or test fixture that reproduces their values,
  whether as TSV, CSV, JSON, SVG, HTML or JavaScript.
- The four `cases/A2_pvt_independent_check/` artefacts -- the protocol, the report and
  the two result files -- because they are derived from the extract and quote it.

A digest is not data. A citation is not data. A column name is not data. A retrieved
value is data, in whatever format it is wearing.

## Consequences inside the repository

- 20 of the 633 tests skip, all in `tests/test_gas_properties.py`, with the message
  `NIST reference extract not present`. No test is deleted, relaxed or stubbed.
- `cases/A2_pvt_independent_check/run.py` exits 1 and says the reference table is
  absent. It does not fabricate a result, and it does not silently pass.
- `scripts/fetch_nist_reference.py verify` still fails in this tree, correctly: it is the
  gate for a checkout that holds the extract, and here the extract is supposed to be
  missing. The gate that applies to the published tree is
  `scripts/check_public_release.py`.
- `scripts/fetch_nist_reference.py` acquires nothing by default, refuses to run in any
  automated context, and requires an explicit output directory plus a recorded access
  basis. There is no `--accept-terms` flag, because passing a flag is not evidence that
  anyone granted permission.

## Acquiring the data for your own use

The decision above is about redistribution. It says nothing against you retrieving the
values from a public interface for your own use, under whatever basis applies to you.

```
python3 scripts/fetch_nist_reference.py plan
python3 scripts/fetch_nist_reference.py acquire \
    --out /path/outside/this/checkout \
    --access-basis "your own recorded basis"
python3 scripts/fetch_nist_reference.py verify --out /path/outside/this/checkout
```

`plan` prints the requests and makes none. `acquire` writes an `ACQUISITION_RECORD.json`
next to the data holding the basis you stated, verbatim, so that it can be reviewed. The
script records that basis; it does not verify it, and nothing it writes is permission
from NIST.

If you place the extract inside this checkout anyway, the script writes a nested ignore
file so the values cannot be committed from there, and `scripts/check_public_release.py`
will refuse the tree if they ever reach it.

## When to revisit this

Any one of these would reopen the decision, and each should be recorded here with a date
rather than applied silently:

- Written permission from NIST SRD covering redistribution of this extract.
- A NIST licensing statement that addresses redistribution of SRD extracts directly.
- An equivalent oracle under terms that permit redistribution -- a reference equation of
  state implemented from a published paper would remove the dependency entirely, at the
  cost of having to verify that implementation against something.

## Other datasets

The same rule governs everything else, and is the reason none of the following is here.
Access rights and redistribution rights are different rights; a public download link
establishes the first and only the licence text establishes the second. Git history keeps
what the working tree no longer shows, so a mistaken commit is not undone by a later
deletion.

| Dataset | Status | Gate before any of it is published |
|---|---|---|
| NIST Chemistry WebBook extract | metadata only, values not distributed | this document |
| SPE1, SPE3 (OPM decks) | not acquired | per-file terms reviewed and a commit pinned |
| Volve (Equinor) | not acquired | the current Equinor Open Data Licence read in full |
| Norne, SPE10 | not acquired | not yet assessed |
| Synthetic cases | generated on demand | none needed; reproducible from a committed configuration and a recorded seed |

## Verifying that this policy holds

```
python3 scripts/check_public_release.py --verbose
```

The gate checks the working tree and the whole of git history, scans every publishable
text format for a NIST-derived numeric payload, checks that this decision is stated
consistently across the manifest, the licence, the notice and the data README, and looks
for credentials and private absolute paths. `docs/release/DISTRIBUTION_MANIFEST.md`
describes what a built artefact contains and lists the commands that verify it.

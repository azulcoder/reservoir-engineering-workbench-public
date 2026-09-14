# Data policy

Nothing under `data/` is tracked in git except the four policy and provenance
documents listed below. No dataset is tracked at all, including the NIST reference
extract, which is described here and deliberately not published here.
`.gitignore` and `scripts/check_repository.py` keep unexpected files out of a commit;
`scripts/check_public_release.py` is the gate that checks the published tree and its
whole history for restricted data before anything is released.

The reason is narrow and worth stating exactly: **permission to access a dataset and
permission to redistribute it are different permissions.** A public download link
establishes the first. Only the licence text establishes the second, and git history
keeps what the working tree no longer shows, so a mistaken commit is not undone by a
later deletion.

## What may be committed

| Path | Contents |
|---|---|
| `data/README.md` | this policy |
| `data/reference/README.md` | provenance, citation and the non-redistribution decision |
| `data/reference/MANIFEST.json` | request URLs, units, row counts, SHA-256 digests |
| `data/raw/README.md` | why third-party raw files are acquired locally and never committed |

That is the whole list. The NIST reference extract itself is **not** on it. The values
are retrievable by anyone from the URLs the manifest records, but retrieving them and
republishing them are different acts, and only the first is established as permitted.
See [`docs/release/PUBLIC_DATA_POLICY.md`](../docs/release/PUBLIC_DATA_POLICY.md).

## What is never committed

The NIST Chemistry WebBook extract, raw field data, operator data, simulator decks
obtained from third parties, licence artefacts, signed or time-limited download URLs,
anything carrying personal identifiers, and anything an employer supplied. Acquire these
locally using the instructions in the relevant case protocol and leave them in a
directory outside this checkout.

## Acquisition gate

Before any dataset enters a case study, `docs/data_contract.md` requires a record of:
owner, original URL, release or revision, retrieval date, exact file list, checksums,
licence and notices, known exclusions, unit system, datum and pressure type, and the
intended use. A dataset without that record is quarantined and cannot support a
published result — not because the rule is bureaucratic, but because a pressure series
whose datum and gauge type are unknown cannot support a material balance regardless of
how clean the numbers look.

## Datasets referenced by the plan, and their status here

| Dataset | Status in this repository | Why |
|---|---|---|
| NIST Chemistry WebBook pure-component properties | **not distributed**; metadata and acquisition instructions only, `data/reference/` | Used as an independent PVT oracle where a reader has retrieved it locally. The values are copyrighted Standard Reference Data and citation alone is not established as permitting redistribution. Without it, 20 of the 633 tests skip and case A2 exits non-zero rather than producing a result. |
| Locally generated synthetic cases | **generated on demand** by `cases/*/run.py` | Reproducible from a committed configuration and a recorded seed; no need to store. |
| SPE1, SPE3 (OPM decks) | **not acquired** | Stage C. Per-file terms must be reviewed and a commit pinned first. |
| Volve (Equinor) | **not acquired** | Stage E. Requires reading the current Equinor Open Data Licence before any derived extract is published. |
| Norne, SPE10 | **not acquired** | Later extensions only. |

# How this repository was created, and what its history does and does not prove

## Origin

This repository is a **publication candidate**. Its files were imported from a private
working repository, from a single committed snapshot:

| Item | Value |
|---|---|
| Private source HEAD at import | `eab3fec4b90cf115311c724c9a975c385258fd42` |
| Files tracked at that commit | 98 |
| Files imported here | 88 |
| Files deliberately excluded | 10 (see `docs/release/PUBLIC_DATA_POLICY.md`) |
| Import method | `git show HEAD:<path>` per allowlisted path, bytes preserved |
| Byte-identity verified | yes, every imported file compared against the committed blob |

## The history reset is intentional

The git history here begins at this repository's first commit. It is **not** a continuation
of the private repository's history, and it was not produced by rewriting that history.

The reason is a data-rights decision, not tidiness. The private repository's history
contains an extract of NIST Standard Reference Data that this project has decided not to
redistribute. Removing those files in a *new commit* on the original history would not
help: git keeps every earlier version, so the blobs would remain reachable in any clone. A
fresh repository built from a reviewed allowlist is the only construction in which those
bytes were never present at all.

`git log` was verified to contain no reachable blob from the excluded set; the check is
recorded in the release evidence.

## What this history does not establish

**The commit dates here are the dates this candidate was assembled, not the dates the
underlying studies were performed.** Nothing in this repository's history is evidence about
when any earlier protocol, run or report was written.

In particular, this repository does not strengthen the pre-registration status of the
studies it carries. That status is what it was in the private baseline, and it differs by
case:

| Case | Ordering evidence | Classification |
|---|---|---|
| A1 | run record declares no inputs | **ordering unverified** |
| A2 | protocol declared with a SHA-256 that matches | content linkage recorded |
| A3 | protocol declared with a SHA-256 that matches | content linkage recorded |
| A4 | run record declares no inputs | **ordering unverified** |

Even for A2 and A3, a protocol hash recorded inside a run record establishes that the
protocol content the run saw is the content committed. It is **not** an independent trusted
timestamp, and it is not proof against a protocol having been constructed retrospectively
and then run. It is internal content linkage, recorded by the run itself, and that is all
it is.

## The private baseline is preserved

The original repository is unchanged and remains the private baseline. It is not a second
active source of truth: forward development happens here. Its HEAD is recorded above so
that any file in this repository can be traced back to the exact commit it came from.

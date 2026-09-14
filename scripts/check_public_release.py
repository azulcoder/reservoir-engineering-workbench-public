#!/usr/bin/env python3
"""Publication gate for the public tree: restricted data, policy, secrets, machine paths.

This is the check that runs before anything is published. It is not the same check as
``scripts/check_repository.py``, which is a commit-time hygiene hook, and it is not
``scripts/fetch_nist_reference.py verify``, which re-hashes an extract that is supposed
to be present. Here the extract is supposed to be *absent*, so a gate that hashes files
it expects to find is the wrong instrument: it would fail for the right reason on the
wrong question, and it would say nothing about git history, about a derived table in a
JSON figure file, or about an absolute home directory baked into a built page.

What it checks
--------------
excluded    The restricted files are not in the working tree and are not reachable in
            git history. History is enumerated with ``git rev-list --objects --all
            --reflog`` and every blob is content-hashed, so a rename or a later deletion
            does not hide anything.
payload     No NIST-derived numeric payload appears anywhere in the publishable tree, in
            any format. Four independent probes: the recorded SHA-256 digests as literal
            strings, the restricted file names, a value-shaped probe for the retrieved
            table, and high-precision numbers sitting next to a WebBook provenance
            marker.
policy      The publication decision is stated consistently, the manifest describes an
            extract that is genuinely absent, and no ignore rule or commit allowlist
            re-admits the restricted files.
secrets     No credentials, private absolute home paths, or machine-local identifiers.

Every check prints what it looked at, so a pass is readable rather than merely silent.

Usage
-----
    python3 scripts/check_public_release.py
    python3 scripts/check_public_release.py --fail-on-warning
    python3 scripts/check_public_release.py --only payload --verbose
"""

from __future__ import annotations

import argparse
import dataclasses
import getpass
import hashlib
import json
import os
import pathlib
import re
import socket
import subprocess
import sys

FAIL = "FAIL"
WARN = "WARN"
#: Reported, never silent: a reviewed exception with its reason attached.
EXEMPT = "EXEMPT"
INFO = "info"

#: Paths that were deliberately not imported into the public repository. The three NIST
#: extracts are restricted Standard Reference Data; the four A2 artefacts are derived
#: from them and reproduce their content in aggregate form.
EXCLUDED_PATHS = (
    "data/reference/nist_methane_isotherms.tsv",
    "data/reference/nist_carbon_dioxide_isotherms.tsv",
    "data/reference/nist_nitrogen_isotherms.tsv",
    "cases/A2_pvt_independent_check/protocol.md",
    "cases/A2_pvt_independent_check/report.md",
    "cases/A2_pvt_independent_check/results/summary.json",
    "cases/A2_pvt_independent_check/results/run_record.json",
)

#: Matched against a file's base name anywhere in the tree or history, so that renaming
#: or relocating a restricted file does not get it past the gate.
RESTRICTED_BASENAME_PATTERNS = (
    re.compile(r"^nist_.*isotherm.*$", re.IGNORECASE),
    re.compile(r"^.*_isotherms\.tsv$", re.IGNORECASE),
)

#: Directories never walked. node_modules is a build input, not a published artefact;
#: the rest are caches and virtual environments.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".astro",
        "htmlcov",
        ".idea",
        ".vscode",
    }
)

#: Text formats scanned for a numeric payload. The brief named .json, .csv, .svg, .html,
#: .js and any built dist/; this is a superset, because a leaked table is a leaked table
#: whatever extension it wears, and the cost of scanning a markdown file is nil.
SCAN_SUFFIXES = frozenset(
    {
        ".json",
        ".csv",
        ".tsv",
        ".txt",
        ".dat",
        ".svg",
        ".html",
        ".htm",
        ".js",
        ".mjs",
        ".cjs",
        ".jsx",
        ".ts",
        ".tsx",
        ".astro",
        ".vue",
        ".md",
        ".rst",
        ".yml",
        ".yaml",
        ".toml",
        ".cfg",
        ".ini",
        ".py",
        ".sh",
        ".xml",
    }
)

MAX_SCAN_BYTES = 8 * 1024 * 1024

#: The pressure sweep the extract was retrieved on. A table that reproduces it is the
#: shape of the restricted data even if the column headers have been stripped.
GRID_LOW, GRID_HIGH, GRID_STEP = 200.0, 6000.0, 200.0

#: Strings that mark a WebBook retrieval. Their presence is fine on its own; their
#: presence next to a block of high-precision numbers is the thing worth looking at.
WEBBOOK_MARKERS = (
    "webbook.nist.gov",
    "fluid.cgi",
    "NIST Chemistry WebBook",
    "SRD 69",
)

#: Phrases by which a document declares that a quantity was COMPUTED FROM the restricted
#: extract, as opposed to WEBBOOK_MARKERS which declare where data came from. The two
#: families catch different things and neither subsumes the other.
#:
#: This family exists because of a leak the other screens could not see. A viscosity
#: correlation evaluated on a reference density contains no reference digit of its own,
#: so a fixed-string sweep passes it and no provenance marker sits near it -- yet the
#: correlation is strictly monotonic in density, so the published value inverts back to
#: the reference density to machine precision. The number IS the data. Pairing an
#: admission that a value is reference-derived with a high-precision number beside it is
#: the value-free way to catch that, and it does not require knowing the withheld value.
DERIVED_FROM_REFERENCE_MARKERS = (
    "from the reference densit",
    "from the reference value",
    "on the reference densit",
    "on the reference value",
    "reference densities via",
    "rho from the reference",
    "back-calculated with",
    "derived from the extract",
)

#: Column headers of the WebBook wide-format table. Legitimate as schema metadata in the
#: manifest; suspicious anywhere else.
WEBBOOK_COLUMN_HEADERS = (
    "Density (lbm/ft3)",
    "Viscosity (uPa*s)",
    "Therm. Cond. (W/m*K)",
    "Joule-Thomson (F/psia)",
    "Sound Spd. (ft/s)",
)

#: The manifest is the one file whose job is to hold this metadata. Metadata is not the
#: data: a digest and a column name reproduce no retrieved value. It is exempt from the
#: digest-literal and header probes, and from nothing else.
METADATA_EXEMPT = ("data/reference/MANIFEST.json",)

#: Exempt from the DERIVED-VALUE family only, and for one structural reason: the
#: exemptions register has to quote the numbers it excuses, beside prose explaining what
#: they were computed from. Scanning it with this family produces a finding about a
#: finding, and recording an exemption for that produces another. The carve-out is
#: narrow on purpose -- the register is still scanned by the provenance-marker family
#: and by the grid-shape probe, so a table hidden inside it is still rejected, which is
#: verified by a regression test rather than assumed here.
DERIVED_SCAN_EXEMPT = ("docs/release/payload_exemptions.json",)

#: Documents that necessarily quote the policy, the file names and the acquisition
#: recipe. They are exempt from the file-name probe only.
NAME_EXEMPT_PREFIXES = (
    "data/reference/",
    "data/README.md",
    "docs/release/",
    "docs/data_contract.md",
    "scripts/",
    "tests/",
)

FLOAT_RE = re.compile(r"[-+]?\d+\.\d+(?:[eE][-+]?\d+)?")
NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")

SECRET_PATTERNS = (
    ("aws access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("github fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b")),
    ("slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("anthropic api key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    ("openai-style api key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("google api key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("json web token", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.")),
    (
        "credential assignment",
        re.compile(
            r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)\b"
            r"\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']"
        ),
    ),
)

#: Appended to a finding about a file git ignores: it is not published from this tree,
#: but an over-broad packaging include could still sweep it into an archive.
IGNORED_NOTE = (
    " (git-ignored, so it is not published from this tree; it still must not reach a distribution archive)"
)

#: File names that are credential material by convention. Reported on sight: the gate
#: does not need to read a private key to know it should not be published.
CREDENTIAL_FILENAMES = (
    re.compile(r"^\.env(\..+)?$"),
    re.compile(r"^\.netrc$"),
    re.compile(r"^\.npmrc$"),
    re.compile(r"^\.pypirc$"),
    re.compile(r"^id_(rsa|dsa|ecdsa|ed25519)$"),
    re.compile(r"^.*\.(pem|key|p12|pfx|jks|keystore|ppk)$", re.IGNORECASE),
    re.compile(r"^credentials(\..+)?$", re.IGNORECASE),
    re.compile(r"^service[-_]account.*\.json$", re.IGNORECASE),
)

PRIVATE_PATH_PATTERNS = (
    ("unix home path", re.compile(r"(?<![\w.])/(?:Users|home)/[A-Za-z0-9._\-]+/")),
    ("windows home path", re.compile(r"[A-Za-z]:\\\\?Users\\\\?[A-Za-z0-9._\-]+")),
    ("local file url", re.compile(r"file://(?:localhost)?/[A-Za-z0-9._\-/]+")),
    ("private temp sandbox", re.compile(r"/private/" + r"tmp/[A-Za-z0-9._\-]+/")),
)


@dataclasses.dataclass(frozen=True)
class Finding:
    """One thing the gate objects to."""

    level: str
    check: str
    where: str
    message: str

    def render(self) -> str:
        """Return a single printable line."""
        return f"  [{self.level}] {self.check}: {self.where}\n         {self.message}"


def run_git(root: pathlib.Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        check=False,
    )


def is_git_repository(root: pathlib.Path) -> bool:
    result = run_git(root, "rev-parse", "--git-dir")
    return result.returncode == 0


def iter_tree_files(root: pathlib.Path):
    """Yield every publishable file in the working tree, as a repo-relative path."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info"))
        here = pathlib.Path(dirpath)
        for name in sorted(filenames):
            path = here / name
            yield path, path.relative_to(root).as_posix()


def git_ignored_paths(root: pathlib.Path, rels: list[str]) -> frozenset[str]:
    """Return the subset of ``rels`` that git ignores, so unpublished noise is not a failure.

    A file the publication path never touches still matters -- it can be swept into an
    sdist by an over-broad include -- but it is a different severity from a leak in a
    tracked file, and conflating the two makes the gate easy to dismiss.
    """
    if not rels or not is_git_repository(root):
        return frozenset()
    result = subprocess.run(
        ["git", "-C", str(root), "check-ignore", "--stdin"],
        input=("\n".join(rels) + "\n").encode(),
        capture_output=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        return frozenset()
    return frozenset(result.stdout.decode("utf-8", "replace").splitlines())


def read_text(path: pathlib.Path) -> str | None:
    """Read a file as UTF-8 text, returning None for a binary or oversized file."""
    try:
        if path.stat().st_size > MAX_SCAN_BYTES:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def load_manifest(root: pathlib.Path) -> dict | None:
    path = root / "data" / "reference" / "MANIFEST.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def recorded_digests(manifest: dict | None) -> dict[str, str]:
    """Map recorded SHA-256 digest to the file name it belongs to."""
    if not manifest:
        return {}
    return {
        entry["sha256"].lower(): entry["path"]
        for entry in manifest.get("files", ())
        if isinstance(entry.get("sha256"), str)
    }


def basename_is_restricted(name: str) -> bool:
    return any(pattern.match(name) for pattern in RESTRICTED_BASENAME_PATTERNS)


def exempt(rel: str, prefixes: tuple[str, ...]) -> bool:
    return any(rel == prefix or rel.startswith(prefix) for prefix in prefixes)


# --------------------------------------------------------------------------------------
# check: excluded
# --------------------------------------------------------------------------------------


def check_excluded(root: pathlib.Path, manifest: dict | None, verbose: bool) -> list[Finding]:
    findings: list[Finding] = []
    present = {rel for _, rel in iter_tree_files(root)}
    for rel in EXCLUDED_PATHS:
        if rel in present:
            findings.append(
                Finding(
                    FAIL,
                    "excluded",
                    rel,
                    "deliberately excluded from the public repository and present in the "
                    "working tree. It is either restricted NIST Standard Reference Data or "
                    "derived from it; remove it before publishing.",
                )
            )
    for _, rel in iter_tree_files(root):
        name = rel.rsplit("/", 1)[-1]
        if basename_is_restricted(name) and rel not in EXCLUDED_PATHS:
            findings.append(
                Finding(
                    FAIL,
                    "excluded",
                    rel,
                    "file name matches the restricted reference extract. Renaming or moving "
                    "it does not change what it contains.",
                )
            )
    if verbose:
        print(f"    working tree: {len(present)} files walked, {len(EXCLUDED_PATHS)} exclusions checked")

    findings.extend(check_history(root, manifest, verbose))
    return findings


def enumerate_history_blobs(root: pathlib.Path) -> list[tuple[str, int, str]]:
    """Return every ``(oid, size, path)`` blob reachable from any ref or reflog entry."""
    listing = run_git(root, "rev-list", "--objects", "--all", "--reflog")
    if listing.returncode != 0:
        return []
    batch_format = "--batch-check=%(objectname) %(objecttype) %(objectsize) %(rest)"
    check = subprocess.run(
        ["git", "-C", str(root), "cat-file", batch_format],
        input=listing.stdout,
        capture_output=True,
        check=False,
    )
    blobs: list[tuple[str, int, str]] = []
    for line in check.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split(" ", 3)
        if len(parts) < 3 or parts[1] != "blob":
            continue
        oid, _, size = parts[0], parts[1], parts[2]
        path = parts[3] if len(parts) == 4 else ""
        blobs.append((oid, int(size), path))
    return blobs


def hash_history_blobs(root: pathlib.Path, oids: list[str]) -> dict[str, str]:
    """Content-hash blobs by streaming them out of ``git cat-file --batch``."""
    if not oids:
        return {}
    payload = ("\n".join(oids) + "\n").encode()
    result = subprocess.run(
        ["git", "-C", str(root), "cat-file", "--batch"],
        input=payload,
        capture_output=True,
        check=False,
    )
    data = result.stdout
    digests: dict[str, str] = {}
    offset = 0
    while offset < len(data):
        newline = data.find(b"\n", offset)
        if newline < 0:
            break
        header = data[offset:newline].decode("utf-8", "replace").split()
        offset = newline + 1
        if len(header) != 3:
            break
        oid, _kind, size_text = header
        size = int(size_text)
        digests[oid] = hashlib.sha256(data[offset : offset + size]).hexdigest()
        offset += size + 1
    return digests


def check_history(root: pathlib.Path, manifest: dict | None, verbose: bool) -> list[Finding]:
    findings: list[Finding] = []
    if not is_git_repository(root):
        return [
            Finding(
                WARN,
                "excluded",
                str(root),
                "not a git repository, so history could not be checked. The working-tree "
                "checks above are the only evidence this run produced.",
            )
        ]
    blobs = enumerate_history_blobs(root)
    if not blobs:
        return [
            Finding(
                WARN,
                "excluded",
                str(root),
                "git history enumerated no blobs. Either the repository has no commits or "
                "rev-list failed; treat the history check as not performed.",
            )
        ]

    digest_owner = recorded_digests(manifest)
    for oid, size, path in blobs:
        name = path.rsplit("/", 1)[-1]
        if path in EXCLUDED_PATHS or (name and basename_is_restricted(name)):
            findings.append(
                Finding(
                    FAIL,
                    "excluded",
                    f"{path} (blob {oid[:12]}, {size} bytes)",
                    "reachable in git history. Deleting a file in a later commit does not "
                    "remove it from the repository; the history must be rewritten before "
                    "publication.",
                )
            )

    hashable = [oid for oid, size, _ in blobs if size <= MAX_SCAN_BYTES]
    digests = hash_history_blobs(root, hashable)
    for oid, _size, path in blobs:
        digest = digests.get(oid)
        if digest and digest in digest_owner:
            findings.append(
                Finding(
                    FAIL,
                    "excluded",
                    f"{path or '(no path)'} (blob {oid[:12]})",
                    f"content hashes to the digest MANIFEST.json records for "
                    f"{digest_owner[digest]}. This blob is the restricted extract regardless "
                    "of the name it is stored under.",
                )
            )
    if verbose:
        print(
            f"    git history: {len(blobs)} blobs reachable from --all --reflog, "
            f"{len(digests)} content-hashed, {len(digest_owner)} recorded digests compared"
        )
    return findings


# --------------------------------------------------------------------------------------
# check: payload
# --------------------------------------------------------------------------------------


def on_pressure_grid(value: float) -> bool:
    if not GRID_LOW - 1e-9 <= value <= GRID_HIGH + 1e-9:
        return False
    steps = (value - GRID_LOW) / GRID_STEP
    return abs(steps - round(steps)) < 1e-9


def significant_digits(token: str) -> int:
    digits = token.lstrip("+-").replace(".", "").split("e")[0].split("E")[0]
    return len(digits.lstrip("0"))


def longest_grid_table_run(text: str, min_precision: int = 6) -> int:
    """Return the longest run of retrieval-grid steps carrying table-shaped values.

    The probe is the shape of the extract rather than any of its numbers, so it works on
    a leaked TSV, a CSV, a pretty-printed JSON array with one value per line, or a table
    pasted into a page. Reading every numeric token in document order, it looks for
    pressures that step by exactly 200 psia along the 200-6000 psia sweep, with at least
    two high-precision values between one step and the next. That pairing is what a row
    of the retrieved table is.

    Neither half alone is evidence. A correlation's coefficient list holds precise
    numbers, and a configuration may hold the pressure grid; what neither holds is the
    grid marching upward with precise values threaded between the steps.
    """
    grid_run = 0
    best = 0
    previous_grid: float | None = None
    precise_since_step = 0
    for token in NUMBER_RE.findall(text):
        try:
            value = float(token)
        except ValueError:  # pragma: no cover - the regex already constrains this
            continue
        is_integral = "." not in token and "e" not in token.lower()
        if is_integral and on_pressure_grid(value):
            steps_by_one = previous_grid is not None and abs(value - previous_grid - GRID_STEP) < 1e-9
            if steps_by_one and precise_since_step >= 2:
                grid_run += 1
            else:
                grid_run = 1
            best = max(best, grid_run)
            previous_grid = value
            precise_since_step = 0
        elif "." in token and significant_digits(token) >= min_precision:
            precise_since_step += 1
    return best


def marker_adjacent_numbers(
    text: str,
    window: int = 2,
    min_precision: int = 5,
    markers: tuple[str, ...] = WEBBOOK_MARKERS,
) -> list[tuple[int, int]]:
    """Return ``(line, count)`` where high-precision numbers sit beside a marker."""
    lines = text.splitlines()
    lowered = [line.lower() for line in lines]
    needles = [marker.lower() for marker in markers]
    marked = [index for index, line in enumerate(lowered) if any(n in line for n in needles)]
    hits: list[tuple[int, int]] = []
    for index in marked:
        low = max(0, index - window)
        high = min(len(lines), index + window + 1)
        count = 0
        for line in lines[low:high]:
            for token in FLOAT_RE.findall(line):
                if significant_digits(token) >= min_precision:
                    count += 1
        if count:
            hits.append((index + 1, count))
    return hits


EXEMPTIONS_PATH = "docs/release/payload_exemptions.json"


def load_payload_exemptions(root: pathlib.Path) -> dict[tuple[str, int], str]:
    """Load the reviewed payload exemptions.

    The payload screen is a heuristic: it counts high-precision numbers near a NIST
    provenance marker. That catches a redistributed tabulation, and it also catches a
    unit conversion or a published physical constant sitting in the same sentence. The
    answer is not to loosen the screen -- a looser screen stops catching the thing it
    exists for. It is to record each exception with its reason and keep it visible, which
    is what this register does. An exempt location is still printed, as EXEMPT.
    """
    path = root / EXEMPTIONS_PATH
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    out: dict[tuple[str, int], str] = {}
    for entry in payload.get("exemptions", []):
        out[(entry["path"], int(entry["line_hint"]))] = entry["reason"]
    return out


def check_payload(
    root: pathlib.Path,
    manifest: dict | None,
    verbose: bool,
    min_grid_rows: int,
    min_marker_numbers: int,
    min_derived_numbers: int,
) -> list[Finding]:
    findings: list[Finding] = []
    exemptions = load_payload_exemptions(root)
    digest_owner = recorded_digests(manifest)
    scanned = 0
    restricted_names = tuple(
        entry["path"] for entry in (manifest or {}).get("files", ()) if isinstance(entry.get("path"), str)
    )
    ignored = git_ignored_paths(root, [rel for _, rel in iter_tree_files(root)])

    def level_for(rel: str) -> tuple[str, str]:
        if rel in ignored:
            return WARN, IGNORED_NOTE
        return FAIL, ""

    for path, rel in iter_tree_files(root):
        if path.suffix.lower() not in SCAN_SUFFIXES:
            continue
        text = read_text(path)
        if text is None:
            continue
        scanned += 1

        level, suffix = level_for(rel)

        if not exempt(rel, METADATA_EXEMPT):
            for digest, owner in digest_owner.items():
                if digest in text.lower():
                    findings.append(
                        Finding(
                            level,
                            "payload",
                            rel,
                            f"contains the SHA-256 digest MANIFEST.json records for {owner}. "
                            "A digest outside the manifest usually travels with the file it "
                            f"identifies; check what else this artefact carries.{suffix}",
                        )
                    )

        if not exempt(rel, NAME_EXEMPT_PREFIXES):
            for name in restricted_names:
                if name in text:
                    findings.append(
                        Finding(
                            level,
                            "payload",
                            rel,
                            f"names the restricted file {name} outside the documents that are "
                            f"supposed to describe it.{suffix}",
                        )
                    )

        # Source that parses the served format has to name its columns, so .py is exempt
        # from the schema probe. A data file has no such excuse.
        if not exempt(rel, METADATA_EXEMPT) and path.suffix.lower() != ".py":
            headers = [header for header in WEBBOOK_COLUMN_HEADERS if header in text]
            if len(headers) >= 2:
                findings.append(
                    Finding(
                        level,
                        "payload",
                        rel,
                        f"carries the WebBook wide-table column headers {headers}. That is the "
                        "schema of the restricted extract; a file holding it is very likely "
                        f"holding rows as well.{suffix}",
                    )
                )

        run = longest_grid_table_run(text)
        if run >= min_grid_rows:
            findings.append(
                Finding(
                    level,
                    "payload",
                    rel,
                    f"{run} consecutive 200 psia steps along the retrieval grid, each followed "
                    f"by high-precision values. That is the shape of the restricted table.{suffix}",
                )
            )

        for line_number, count in (
            []
            if exempt(rel, DERIVED_SCAN_EXEMPT)
            else marker_adjacent_numbers(text, markers=DERIVED_FROM_REFERENCE_MARKERS)
        ):
            # A far lower threshold than the provenance-marker family, deliberately. That
            # family guards against a table pasted beside its citation, where a dozen
            # numbers is the signal. This one guards against a value that inverts, and a
            # SINGLE such value is already a whole reference datum recovered to machine
            # precision. Reusing 12 here would be a threshold borrowed from a different
            # failure mode; it is what let a six-value reconstruction through in testing.
            if count >= min_derived_numbers:
                reason = exemptions.get((rel, line_number))
                detail = (
                    f"{count} high-precision numbers beside a statement that the "
                    "quantity was computed from the restricted extract. A value "
                    "derived pointwise from a withheld input is not exempt: an "
                    "invertible correlation carries the input back out of it."
                )
                if reason is not None:
                    # Same contract as the provenance-marker family: an exemption is
                    # reported one level down with its reason attached, never dropped.
                    # A screen that stops printing what it excused cannot be audited.
                    findings.append(
                        Finding(
                            EXEMPT,
                            "payload",
                            f"{rel}:{line_number}",
                            f"{detail} Reviewed and exempted: {reason}",
                        )
                    )
                else:
                    findings.append(Finding(level, "payload", f"{rel}:{line_number}", f"{detail}{suffix}"))

        for line_number, count in marker_adjacent_numbers(text):
            if count >= min_marker_numbers:
                reason = exemptions.get((rel, line_number))
                if reason is not None:
                    # Still reported, one level down, with the recorded reason attached. An
                    # exemption that disappears from the output is indistinguishable from a
                    # screen that was quietly weakened.
                    findings.append(
                        Finding(
                            EXEMPT,
                            "payload",
                            f"{rel}:{line_number}",
                            f"{count} high-precision numbers near a provenance marker, "
                            f"reviewed and exempted: {reason}",
                        )
                    )
                    continue
                findings.append(
                    Finding(
                        level,
                        "payload",
                        f"{rel}:{line_number}",
                        f"{count} numbers of five or more significant digits sit within two "
                        "lines of a NIST WebBook provenance marker. Retrieved values quoted "
                        f"next to their own citation are still retrieved values.{suffix}",
                    )
                )

    if verbose:
        print(
            f"    payload: {scanned} text files scanned across {len(SCAN_SUFFIXES)} suffixes; "
            f"probes = digest literal, file name, column headers, grid shape, marker proximity"
        )
    return findings


# --------------------------------------------------------------------------------------
# check: policy
# --------------------------------------------------------------------------------------

#: Phrases each publication document must carry, so that a future edit cannot quietly
#: revert the decision to the attribution framing that was wrong.
REQUIRED_PHRASES = {
    "data/reference/README.md": ("not distributed", "conservative publication decision"),
    "LICENSE": ("non-redistribution", "conservative publication decision"),
    "NOTICE.md": ("not redistributed", "conservative publication decision"),
    "docs/release/PUBLIC_DATA_POLICY.md": (
        "conservative publication decision",
        "not an adjudication",
    ),
    "docs/release/DISTRIBUTION_MANIFEST.md": ("excludes", "verify"),
}


def check_policy(root: pathlib.Path, manifest: dict | None, verbose: bool) -> list[Finding]:
    findings: list[Finding] = []

    if manifest is None:
        return [
            Finding(
                FAIL,
                "policy",
                "data/reference/MANIFEST.json",
                "missing or unparseable. The manifest is the only published record of what "
                "the extract is; without it nothing here can be verified.",
            )
        ]

    redistribution = manifest.get("redistribution")
    if not isinstance(redistribution, dict):
        findings.append(
            Finding(
                FAIL,
                "policy",
                "data/reference/MANIFEST.json",
                "has no redistribution block. The manifest must state the publication "
                "decision, not just the provenance.",
            )
        )
    else:
        if redistribution.get("distributed_in_this_repository") is not False:
            findings.append(
                Finding(
                    FAIL,
                    "policy",
                    "data/reference/MANIFEST.json",
                    "redistribution.distributed_in_this_repository is not false.",
                )
            )
        if redistribution.get("decision") != "non-redistribution":
            findings.append(
                Finding(
                    FAIL,
                    "policy",
                    "data/reference/MANIFEST.json",
                    "redistribution.decision is not 'non-redistribution'.",
                )
            )
        if "adjudication" not in json.dumps(redistribution).lower():
            findings.append(
                Finding(
                    WARN,
                    "policy",
                    "data/reference/MANIFEST.json",
                    "the redistribution block does not say that the decision is not an "
                    "adjudication of copyright exceptions. Say so: a conservative choice "
                    "recorded as a legal conclusion is a claim the project cannot support.",
                )
            )

    entries = manifest.get("files", ())
    if not entries:
        findings.append(Finding(FAIL, "policy", "data/reference/MANIFEST.json", "records no files."))
    for entry in entries:
        missing = [key for key in ("path", "sha256", "rows", "eos_reference") if not entry.get(key)]
        if missing:
            findings.append(
                Finding(
                    FAIL,
                    "policy",
                    f"data/reference/MANIFEST.json:{entry.get('path', '?')}",
                    f"manifest entry is missing {missing}. The metadata is what is published "
                    "in place of the data, so it has to be complete.",
                )
            )
        target = root / "data" / "reference" / str(entry.get("path", ""))
        if target.is_file():
            findings.append(
                Finding(
                    FAIL,
                    "policy",
                    f"data/reference/{entry.get('path')}",
                    "present in the tree. The manifest describes an extract this repository "
                    "does not distribute; the file must be absent here.",
                )
            )

    for rel, phrases in REQUIRED_PHRASES.items():
        path = root / rel
        if not path.is_file():
            findings.append(Finding(FAIL, "policy", rel, "required publication document is missing."))
            continue
        text = (read_text(path) or "").lower()
        for phrase in phrases:
            if phrase.lower() not in text:
                findings.append(
                    Finding(
                        FAIL,
                        "policy",
                        rel,
                        f"does not state {phrase!r}. The publication decision has to read the "
                        "same way in every document that carries it.",
                    )
                )

    findings.extend(check_ignore_rules(root))
    findings.extend(check_hook_wiring(root))

    if verbose:
        print(
            f"    policy: manifest describes {len(entries)} absent files; "
            f"{len(REQUIRED_PHRASES)} documents checked for the decision wording"
        )
    return findings


def check_ignore_rules(root: pathlib.Path) -> list[Finding]:
    """Reject an ignore rule that re-admits the extract, which is a live path to a commit."""
    findings: list[Finding] = []
    gitignore = root / ".gitignore"
    text = read_text(gitignore)
    if text is not None:
        for number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("!") and (".tsv" in stripped or "nist" in stripped.lower()):
                findings.append(
                    Finding(
                        FAIL,
                        "policy",
                        f".gitignore:{number}",
                        f"{stripped!r} re-includes the restricted extract, so a copy dropped "
                        "into the tree would be tracked on the next `git add`. Delete the "
                        "negation: nothing under data/reference/ but README.md and "
                        "MANIFEST.json is publishable.",
                    )
                )

    allowlist = root / "scripts" / "check_repository.py"
    text = read_text(allowlist)
    # Match an ACTIVE allowlist entry only. A comment explaining why there is no such
    # entry is the correct state and must not be reported as the defect it documents;
    # an earlier version of this check matched the word and fired on its own fix.
    active_tsv_allow = re.search(
        r"^\s*re\.compile\(\s*r?[\"'][^\"']*data/reference/[^\"']*tsv[^\"']*[\"']\s*\)",
        text or "",
        re.M,
    )
    if active_tsv_allow is not None:
        findings.append(
            Finding(
                FAIL,
                "policy",
                "scripts/check_repository.py",
                "the data-policy allowlist still matches data/reference/*.tsv, so the "
                "commit-time hook would pass a commit that adds the restricted extract. "
                "Remove that pattern from ALLOWED_DATA.",
            )
        )
    return findings


def check_hook_wiring(root: pathlib.Path) -> list[Finding]:
    """Report hooks that gate on data this repository deliberately does not ship."""
    findings: list[Finding] = []
    for rel in (".pre-commit-config.yaml", ".github/workflows/ci.yml"):
        text = read_text(root / rel)
        if text is None:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if "fetch_nist_reference.py" in line and ("--verify-only" in line or " verify" in line):
                findings.append(
                    Finding(
                        WARN,
                        "policy",
                        f"{rel}:{number}",
                        "gates on the reference digests, which cannot pass in a tree that does "
                        "not carry the extract. On a public clone this fails every time and "
                        "teaches people to bypass the hook. Replace it with "
                        "scripts/check_public_release.py, or make it conditional on the "
                        "extract being present.",
                    )
                )
    return findings


# --------------------------------------------------------------------------------------
# check: secrets
# --------------------------------------------------------------------------------------


def machine_local_patterns() -> tuple[tuple[str, re.Pattern[str]], ...]:
    """Patterns built from this machine, so a local identifier cannot slip through."""
    patterns: list[tuple[str, re.Pattern[str]]] = []
    try:
        user = getpass.getuser()
    except Exception:  # pragma: no cover - getuser can fail in odd environments
        user = ""
    if user:
        home_user = re.compile(rf"(?:/|\\)(?:Users|home)(?:/|\\){re.escape(user)}\b")
        patterns.append((f"local username {user!r} in a path", home_user))
    host = socket.gethostname()
    if host and len(host) > 3:
        short = host.split(".")[0]
        patterns.append((f"local hostname {short!r}", re.compile(rf"\b{re.escape(short)}\b")))
    return tuple(patterns)


def check_secrets(root: pathlib.Path, verbose: bool) -> list[Finding]:
    findings: list[Finding] = []
    local = machine_local_patterns()
    scanned = 0
    ignored = git_ignored_paths(root, [rel for _, rel in iter_tree_files(root)])
    for path, rel in iter_tree_files(root):
        level = WARN if rel in ignored else FAIL
        name = rel.rsplit("/", 1)[-1]
        for pattern in CREDENTIAL_FILENAMES:
            if pattern.match(name):
                findings.append(
                    Finding(
                        level,
                        "secrets",
                        rel,
                        "is credential material by name. Whatever it holds, a published tree is "
                        "not where it belongs; remove it from the tree and the history, and "
                        "rotate it if it was ever real.",
                    )
                )
                break
        # No suffix filter here. A secrets scan that trusts file extensions misses the
        # one file most worth catching, which is usually the one named id_rsa or .env.
        text = read_text(path)
        if text is None:
            continue
        scanned += 1
        note = IGNORED_NOTE if rel in ignored else ""
        for number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        Finding(
                            level,
                            "secrets",
                            f"{rel}:{number}",
                            f"looks like a {label}. Rotate it if it is real, and remove it from "
                            f"the tree and the history either way.{note}",
                        )
                    )
            for label, pattern in PRIVATE_PATH_PATTERNS:
                match = pattern.search(line)
                if match:
                    findings.append(
                        Finding(
                            level,
                            "secrets",
                            f"{rel}:{number}",
                            f"contains a {label} ({match.group(0)!r}). An absolute path from the "
                            "author's machine is not reproducible for a reader and leaks the "
                            f"layout of a private system.{note}",
                        )
                    )
            for label, pattern in local:
                if pattern.search(line):
                    findings.append(
                        Finding(
                            WARN,
                            "secrets",
                            f"{rel}:{number}",
                            f"contains the {label}. Machine-local identifiers should not appear "
                            "in a published artefact.",
                        )
                    )
    if verbose:
        print(
            f"    secrets: {scanned} text files scanned; "
            f"{len(SECRET_PATTERNS)} credential patterns, {len(PRIVATE_PATH_PATTERNS)} path "
            f"patterns, {len(local)} machine-local patterns"
        )
    return findings


# --------------------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------------------

CHECKS = ("excluded", "payload", "policy", "secrets")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", default=".", help="repository root to check")
    parser.add_argument("--only", choices=CHECKS, action="append", help="run only these checks")
    parser.add_argument("--fail-on-warning", action="store_true", help="treat warnings as failures")
    parser.add_argument("--verbose", action="store_true", help="print what each check looked at")
    parser.add_argument("--json", action="store_true", dest="as_json", help="emit findings as JSON")
    parser.add_argument(
        "--min-grid-rows",
        type=int,
        default=8,
        help="lines of retrieval-grid-shaped data before a file is reported (default 8)",
    )
    parser.add_argument(
        "--min-marker-numbers",
        type=int,
        default=12,
        help="high-precision numbers beside a WebBook marker before it is reported (default 12)",
    )
    parser.add_argument(
        "--min-derived-numbers",
        type=int,
        default=1,
        help=(
            "high-precision numbers beside a statement that the value was computed from "
            "the restricted extract, before it is reported (default 1: one such value "
            "inverts back to one reference datum)"
        ),
    )
    args = parser.parse_args(argv)

    root = pathlib.Path(args.root).resolve()
    if not root.is_dir():
        print(f"no such directory: {root}", file=sys.stderr)
        return 2
    selected = tuple(args.only) if args.only else CHECKS
    manifest = load_manifest(root)

    if not args.as_json:
        print(f"public release gate: {root}")
        print(f"checks: {', '.join(selected)}\n")

    findings: list[Finding] = []
    for name in selected:
        if not args.as_json:
            print(f"  running {name}")
        if name == "excluded":
            findings.extend(check_excluded(root, manifest, args.verbose and not args.as_json))
        elif name == "payload":
            findings.extend(
                check_payload(
                    root,
                    manifest,
                    args.verbose and not args.as_json,
                    args.min_grid_rows,
                    args.min_marker_numbers,
                    args.min_derived_numbers,
                )
            )
        elif name == "policy":
            findings.extend(check_policy(root, manifest, args.verbose and not args.as_json))
        elif name == "secrets":
            findings.extend(check_secrets(root, args.verbose and not args.as_json))

    failures = [f for f in findings if f.level == FAIL]
    warnings = [f for f in findings if f.level == WARN]

    if args.as_json:
        print(json.dumps([dataclasses.asdict(f) for f in findings], indent=2))
    else:
        print()
        if findings:
            for name in selected:
                block = [f for f in findings if f.check == name]
                if block:
                    print(f"{name}:")
                    for finding in block:
                        print(finding.render())
                    print()
        counts = " ".join(f"{name}={sum(1 for f in findings if f.check == name)}" for name in selected)
        print(f"summary: {len(failures)} failing, {len(warnings)} warning, by check [{counts}]")
        if failures:
            print("RESULT: FAIL - do not publish this tree until every failing item is resolved.")
        elif warnings and args.fail_on_warning:
            print("RESULT: FAIL - warnings are being treated as failures (--fail-on-warning).")
        elif warnings:
            print("RESULT: PASS with warnings - read them before publishing.")
        else:
            print("RESULT: PASS - no restricted data, policy contradiction or secret found.")

    if failures:
        return 1
    if warnings and args.fail_on_warning:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

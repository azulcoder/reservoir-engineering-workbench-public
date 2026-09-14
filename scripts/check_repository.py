#!/usr/bin/env python3
"""Repository hygiene checks for a public research repository.

Runs on staged files at pre-commit and on the whole tree in CI. Every check below
exists because the corresponding mistake is easy to make once and expensive to undo
after a push, since git history keeps what the working tree no longer shows.

Checks
------
1.  Credential-shaped strings and credential-shaped filenames.
2.  Raw or restricted data reaching version control.
3.  Oversized files.
4.  Python files that do not parse.
5.  Notebooks committed with execution output.
6.  Machine-local absolute paths and personal contact details.
7.  Generated-assistant attribution and the prose tells that come with it.

Deliberate limits
-----------------
This is a hygiene gate, not a secret scanner and not a rights review. It matches
shapes; it cannot tell whether a dataset you are entitled to *read* is one you are
entitled to *redistribute*, and it cannot recognise a credential that does not look
like one. A clean run means "no known-bad shape was found", nothing stronger. The
data-rights review in `docs/data_contract.md` remains a manual step.

Usage
-----
    python3 scripts/check_repository.py                 # whole tree, git-tracked + untracked
    python3 scripts/check_repository.py --staged        # staged files only (pre-commit)
    python3 scripts/check_repository.py --paths a.py b.py
"""

from __future__ import annotations

import argparse
import ast
import json
import pathlib
import re
import subprocess

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

#: Hard block. Matches the 5 MiB public-file limit this project documented from the
#: outset; a larger artefact belongs in a versioned artefact store with its checksum
#: recorded here, because git history keeps every version of a large binary forever.
MAX_FILE_BYTES = 5 * 1024 * 1024
#: Soft threshold. Not a failure, but a file this size in a research repository is
#: usually a result that should have been regenerated from a configuration instead.
SOFT_SIZE_WARN_BYTES = 2_000_000
MAX_TEXT_LINE_BYTES = 20_000

#: Directories never scanned for content.
SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
}

#: Extensions treated as binary; they are size-checked and policy-checked but not
#: pattern-scanned.
BINARY_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".xz",
    ".bz2",
    ".so",
    ".dylib",
    ".dll",
    ".pyc",
    ".npz",
    ".npy",
    ".parquet",
    ".h5",
    ".hdf5",
    ".xlsx",
    ".xls",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".woff",
    ".woff2",
    ".ico",
}

#: Filenames and suffixes that must never be committed.
FORBIDDEN_NAME_PATTERNS = [
    (re.compile(r"(^|/)\.env(\.|$)"), "environment file, may hold credentials"),
    (re.compile(r"(^|/)id_(rsa|dsa|ecdsa|ed25519)$"), "private SSH key"),
    (re.compile(r"\.(pem|key|p12|pfx|keystore|jks)$"), "key or certificate store"),
    (re.compile(r"(^|/)(credentials|secrets?)(\.|$)"), "credential file"),
    (re.compile(r"\.(lic|license_key|flexlm|dat_lic)$"), "software licence artefact"),
    (re.compile(r"(^|/)lmgrd|(^|/)license\.dat$"), "licence-server artefact"),
    (re.compile(r"(^|/)\.netrc$"), "netrc credentials"),
    (re.compile(r"(^|/)\.aws/"), "AWS configuration directory"),
]

#: Credential-shaped content. Each is deliberately specific; a broad "password" match
#: produces noise that trains people to pass `--no-verify`.
SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"), "private key block"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"\bASIA[0-9A-Z]{16}\b"), "AWS temporary access key id"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), "GitHub token"),
    (re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}\b"), "GitLab token"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), "Slack token"),
    (re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"), "API secret key"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "Google API key"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"), "JWT"),
    (
        re.compile(r"[?&](X-Amz-Signature|Signature|sig|AWSAccessKeyId)=[A-Za-z0-9%/+_\-]{16,}"),
        "signed download URL",
    ),
    (
        re.compile(r"\b(?:password|passwd|secret|api_key|apikey|token)\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']"),
        "inline credential assignment",
    ),
]

#: Machine-local and personal details that should not travel into a public repository.
LEAK_PATTERNS = [
    (re.compile(r"/Users/[A-Za-z0-9._\-]+/"), "absolute macOS home path"),
    (re.compile(r"/home/[A-Za-z0-9._\-]+/"), "absolute Linux home path"),
    (re.compile(r"[A-Z]:\\\\Users\\\\[A-Za-z0-9._\- ]+"), "absolute Windows home path"),
    (
        re.compile(r"\b[A-Za-z0-9._%+\-]+@(?!example\.(com|org)\b)[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
        "email address",
    ),
]

#: Generated-assistant attribution and the prose tells that come with it. The author of
#: this repository writes in their own voice; this check keeps that true mechanically
#: rather than by intention, because attribution lines are added by defaults and
#: defaults are exactly what a person forgets to override.
ATTRIBUTION_PATTERNS = [
    (re.compile(r"Co-Authored-By:\s*Claude", re.I), "assistant co-author trailer"),
    (re.compile(r"Generated with \[?Claude", re.I), "generated-with attribution"),
    (
        re.compile(
            r"\b(?:written|generated|created|produced|authored)\s+(?:by|with|using)\s+(?:Claude|ChatGPT|GPT-4|Copilot|an?\s+AI(?:\s+assistant)?)\b",
            re.I,
        ),
        "assistant authorship claim",
    ),
    (re.compile(r"\bClaude\s+(?:Code|Opus|Sonnet|Haiku)\b"), "assistant product name"),
    (re.compile(r"\bAnthropic\b"), "assistant vendor name"),
    (
        re.compile(
            r"^\s*(?:[-*]\s*)?(?:✅|❌|⚠️?|\U0001f680|\U0001f389|\U0001f525|✨|\U0001f4a1|\U0001f50d|\U0001f4dd|\U0001f9e0|\U0001f916)",
            re.M,
        ),
        "emoji used as a status marker",
    ),
    (
        re.compile(
            r"\b(?:Let's dive in|Let me dive in|deep dive into|game[- ]chang(?:er|ing)"
            r"|leverag(?:e|ing) the power of|in today's fast[- ]paced)\b",
            re.I,
        ),
        "generated-prose tell",
    ),
]

#: Paths where a match is expected and allowed, because the file's job is to define
#: or to test the pattern.
ATTRIBUTION_ALLOWLIST = {
    "scripts/check_repository.py",
    "tests/test_repository.py",
    "docs/authorship.md",
}
LEAK_ALLOWLIST = {
    "scripts/check_repository.py",
    "tests/test_repository.py",
}

#: Data policy. Only these paths under data/ may be tracked.
#: Note what is NOT here: data/reference/*.tsv. The NIST extract is not redistributed,
#: so a commit that adds it must fail rather than pass. See docs/release/PUBLIC_DATA_POLICY.md.
DATA_ALLOWED = (
    re.compile(r"^data/README\.md$"),
    re.compile(r"^data/raw/README\.md$"),
    re.compile(r"^data/raw/\.gitkeep$"),
    re.compile(r"^data/reference/MANIFEST\.json$"),
    re.compile(r"^data/reference/README\.md$"),
    re.compile(r"^data/\.gitignore$"),
)


class Finding:
    """One problem found in one file, with enough context to act on it."""

    __slots__ = ("check", "detail", "line", "path", "severity")

    def __init__(self, path: str, line: int | None, check: str, detail: str, severity: str = "error") -> None:
        self.path, self.line, self.check, self.detail, self.severity = path, line, check, detail, severity

    def render(self) -> str:
        """Format the finding as a located header line and an indented detail line."""
        where = f"{self.path}:{self.line}" if self.line else self.path
        return f"[{self.severity:<7}] {self.check:<22} {where}\n            {self.detail}"


def git_files(staged: bool) -> list[pathlib.Path]:
    if staged:
        cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"]
    else:
        cmd = ["git", "ls-files", "--cached", "--others", "--exclude-standard"]
    try:
        out = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return sorted(
            p for p in REPO_ROOT.rglob("*") if p.is_file() and not any(part in SKIP_DIRS for part in p.parts)
        )
    paths = []
    for name in out.splitlines():
        if not name.strip():
            continue
        path = REPO_ROOT / name
        if path.is_file() and not any(part in SKIP_DIRS for part in path.parts):
            paths.append(path)
    return paths


def relative(path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def check_name(rel: str) -> list[Finding]:
    findings = []
    for pattern, why in FORBIDDEN_NAME_PATTERNS:
        if pattern.search(rel):
            findings.append(Finding(rel, None, "forbidden-filename", f"{why}; this must never be committed"))
    return findings


def check_size_bytes(size: int, rel: str) -> list[Finding]:
    if size > MAX_FILE_BYTES:
        return [
            Finding(
                rel,
                None,
                "oversized-file",
                f"{size:,} bytes exceeds the {MAX_FILE_BYTES:,} byte limit. Large artefacts belong in a "
                f"versioned artefact store with a checksum recorded here, not in git history.",
            )
        ]
    if size > SOFT_SIZE_WARN_BYTES:
        return [
            Finding(
                rel,
                None,
                "large-file",
                f"{size:,} bytes. Below the hard limit, but a file this size is usually a result that "
                f"should be regenerated from a committed configuration rather than tracked.",
                "warning",
            )
        ]
    return []


def check_size(path: pathlib.Path, rel: str) -> list[Finding]:
    return check_size_bytes(path.stat().st_size, rel)


def check_data_policy(rel: str) -> list[Finding]:
    if not rel.startswith("data/"):
        return []
    if any(p.match(rel) for p in DATA_ALLOWED):
        return []
    return [
        Finding(
            rel,
            None,
            "data-policy",
            "file under data/ is not on the allowed list. Raw and third-party data stay out of git; "
            "commit retrieval instructions and checksums instead. See docs/data_contract.md.",
        )
    ]


def check_python_syntax(path: pathlib.Path, rel: str, text: str) -> list[Finding]:
    if path.suffix != ".py":
        return []
    try:
        ast.parse(text, filename=rel)
    except SyntaxError as exc:
        return [Finding(rel, exc.lineno, "python-syntax", f"{exc.msg}")]
    return []


def check_notebook_outputs(path: pathlib.Path, rel: str, text: str) -> list[Finding]:
    if path.suffix != ".ipynb":
        return []
    try:
        notebook = json.loads(text)
    except json.JSONDecodeError as exc:
        return [Finding(rel, None, "notebook-parse", f"not valid JSON: {exc}")]
    findings = []
    for index, cell in enumerate(notebook.get("cells", [])):
        if cell.get("outputs"):
            findings.append(
                Finding(
                    rel,
                    None,
                    "notebook-output",
                    f"cell {index} carries execution output. Commit notebooks cleared; the executed "
                    f"result belongs in a run directory with its provenance record.",
                )
            )
        if cell.get("execution_count"):
            findings.append(
                Finding(
                    rel,
                    None,
                    "notebook-output",
                    f"cell {index} carries an execution count",
                    "warning",
                )
            )
    return findings


def scan_patterns(rel: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = text.splitlines()

    def locate(match_text: str) -> int | None:
        for number, line in enumerate(lines, start=1):
            if match_text[:60] in line:
                return number
        return None

    for pattern, why in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(Finding(rel, locate(match.group(0)), "credential", f"{why} matched"))

    if rel not in LEAK_ALLOWLIST:
        for pattern, why in LEAK_PATTERNS:
            for match in pattern.finditer(text):
                findings.append(
                    Finding(rel, locate(match.group(0)), "local-leak", f"{why}: {match.group(0)[:70]}")
                )

    if rel not in ATTRIBUTION_ALLOWLIST:
        for pattern, why in ATTRIBUTION_PATTERNS:
            for match in pattern.finditer(text):
                snippet = match.group(0).strip().replace("\n", " ")[:70]
                findings.append(
                    Finding(
                        rel,
                        locate(match.group(0)),
                        "authorship",
                        f"{why}: {snippet!r}. This repository is published under its author's own name "
                        f"and voice; remove the line rather than rewording it.",
                    )
                )

    for number, line in enumerate(lines, start=1):
        if len(line.encode("utf-8", "ignore")) > MAX_TEXT_LINE_BYTES:
            findings.append(
                Finding(
                    rel, number, "long-line", "line exceeds 20 kB; likely embedded binary or minified data"
                )
            )
    return findings


def check_file(path: pathlib.Path) -> list[Finding]:
    rel = relative(path)
    findings = check_name(rel) + check_size(path, rel) + check_data_policy(rel)
    if path.suffix.lower() in BINARY_SUFFIXES:
        return findings
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return [
            *findings,
            Finding(rel, None, "unreadable", "not valid UTF-8 text and not a known binary type", "warning"),
        ]
    findings += check_python_syntax(path, rel, text)
    findings += check_notebook_outputs(path, rel, text)
    findings += scan_patterns(rel, text)
    return findings


def inspect(path: pathlib.Path | str, data: bytes) -> list[str]:
    """Check one file given its path and bytes, returning plain-text problems.

    This is the in-memory entry point. It exists so that a check can be applied to the
    *staged* content of a file rather than to whatever happens to be in the working
    tree, and so that the checks are unit-testable without touching the filesystem.
    :func:`check_file` is the on-disk wrapper around it.

    Returns a list of strings rather than :class:`Finding` objects because that is the
    contract the repository's own infrastructure tests were written against, and a test
    suite that guards a public check is not something to rewrite for cosmetic reasons.
    """
    rel = pathlib.PurePosixPath(str(path).replace("\\", "/")).as_posix()
    findings = check_name(rel) + check_size_bytes(len(data), rel) + check_data_policy(rel)
    suffix = pathlib.PurePosixPath(rel).suffix.lower()
    if suffix not in BINARY_SUFFIXES:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            findings.append(
                Finding(
                    rel, None, "unreadable", "not valid UTF-8 text and not a known binary type", "warning"
                )
            )
        else:
            findings += check_python_syntax(pathlib.PurePosixPath(rel), rel, text)
            findings += check_notebook_outputs(pathlib.PurePosixPath(rel), rel, text)
            findings += scan_patterns(rel, text)
    return [f"{rel}: {f.check}: {f.detail}" for f in findings if f.severity == "error"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Repository hygiene checks")
    parser.add_argument("--staged", action="store_true", help="check staged files only")
    parser.add_argument("--paths", nargs="*", help="explicit paths to check")
    parser.add_argument("--quiet", action="store_true", help="print findings only")
    args = parser.parse_args(argv)

    paths = [pathlib.Path(p).resolve() for p in args.paths] if args.paths else git_files(args.staged)

    findings: list[Finding] = []
    for path in paths:
        if not path.is_file():
            continue
        findings.extend(check_file(path))

    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity != "error"]

    for finding in [*errors, *warnings]:
        print(finding.render())

    if not args.quiet:
        print()
        print(f"checked {len(paths)} files: {len(errors)} error(s), {len(warnings)} warning(s)")
        if errors:
            print("This gate matches known-bad shapes only. A clean run is not a rights review.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

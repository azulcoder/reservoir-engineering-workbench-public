"""Immutable run records.

A figure is not evidence. What makes a computed result defensible is the ability to
say exactly which code, which inputs, which settings and which environment produced
it, and to be able to detect afterwards if any of those changed. This module provides
that record, and enforces the one rule that makes it trustworthy: **a run directory is
written once**. A different configuration, a different seed or a different source
revision produces a different directory. Nothing overwrites a previous result.

Failed runs are recorded too, with their traceback and a ``status`` of ``"failed"``.
A run that is deleted because it did not give the expected answer is the mechanism by
which an ensemble quietly becomes a selected sample, so the design makes deleting it
an explicit manual act rather than a side effect of re-running.

Usage
-----
::

    with RunRecord.open("artifacts/case_a1/run-001", label="clean p/Z oracle",
                        config={"noise_psi": 0.0}, seed=20260913) as run:
        run.add_input("configs/case_a1.toml")
        ...
        run.add_output(results_path)
        run.note("GIIP error 0.0000 percent against the analytic value")

On exit the directory holds ``run_record.json`` with the source revision, the dirty
state of the working tree, hashes of every declared input and output, the environment,
the seed, the settings, the notes, the wall-clock duration and the exit status.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import pathlib
import platform
import subprocess
import sys
import time
import traceback
import types
from collections.abc import Iterable, Mapping
from typing import Any, Literal

from .errors import InvalidInputError

RUN_RECORD_FILENAME = "run_record.json"
RECORD_SCHEMA_VERSION = 1


def sha256_file(path: str | os.PathLike[str]) -> str:
    """Return the hex SHA-256 digest of a file's bytes."""
    digest = hashlib.sha256()
    with pathlib.Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    """Return the hex SHA-256 digest of a byte string."""
    return hashlib.sha256(payload).hexdigest()


def canonical_hash(obj: Any) -> str:
    """Hash a JSON-serialisable object in a form stable across runs.

    Keys are sorted and separators fixed, so that two configurations that differ only
    in dictionary insertion order hash identically -- and two that differ in any value
    do not.
    """
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)
    return sha256_bytes(payload.encode("utf-8"))


def _git(*args: str, cwd: pathlib.Path | None = None) -> str | None:
    """Run a git command, returning stripped stdout, or ``None`` if git is unusable."""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    # Only the trailing newline is removed. `git status --porcelain` encodes the status
    # in the first two columns, so an unstaged modification arrives as " M path": a full
    # strip() would eat that leading space and every subsequent path slice would be one
    # character short. Commands whose output is a single token are unaffected.
    return completed.stdout.rstrip("\n")


def source_revision(repo_root: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Describe the source revision the calling code was loaded from.

    Returns a mapping that always has the keys ``commit``, ``dirty``, ``branch`` and
    ``describe``. Any of them may be ``None`` when the code is not running inside a
    git checkout; a run outside version control is recorded honestly as such rather
    than being blocked, because a scratch exploration is legitimate -- it just must not
    be mistaken for a reproducible one.
    """
    root = pathlib.Path(repo_root) if repo_root else pathlib.Path(__file__).resolve().parents[2]
    commit = _git("rev-parse", "HEAD", cwd=root)
    status = _git("status", "--porcelain", cwd=root)
    return {
        "repo_root": str(root),
        "commit": commit,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD", cwd=root),
        "describe": _git("describe", "--tags", "--always", "--dirty", cwd=root),
        "dirty": None if status is None else bool(status.strip()),
        "dirty_paths": (
            None
            if not status
            else sorted(_porcelain_path(line) for line in status.splitlines() if line.strip())
        ),
    }


def _porcelain_path(line: str) -> str:
    """Extract the path from one `git status --porcelain` line.

    The v1 porcelain format is two status columns, a space, then the path. A rename or
    copy carries both paths as ``old -> new``; the new path is the one that exists in
    the working tree, so that is what is reported.
    """
    path = line[3:] if len(line) > 3 else line.strip()
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return path.strip().strip('"')


def environment() -> dict[str, Any]:
    """Describe the interpreter and platform.

    Third-party package versions are collected only for packages that are actually
    imported at the time of the call, so the record does not imply that an unrelated
    installed package took part in the computation.
    """
    imported: dict[str, str] = {}
    for name in sorted(sys.modules):
        if "." in name or name.startswith("_"):
            continue
        module = sys.modules.get(name)
        version = getattr(module, "__version__", None)
        if isinstance(version, str):
            imported[name] = version
    return {
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "imported_package_versions": imported,
    }


@dataclasses.dataclass
class _FileRef:
    role: str
    path: str
    sha256: str
    bytes: int


class RunRecord:
    """A write-once record of one computation.

    Construct with :meth:`open`, which is a context manager. The record is written on
    exit whether the body succeeded or raised.
    """

    def __init__(
        self,
        directory: pathlib.Path,
        *,
        label: str,
        config: Mapping[str, Any] | None,
        seed: int | None,
        settings: Mapping[str, Any] | None,
        repo_root: str | os.PathLike[str] | None,
    ) -> None:
        self.directory = directory
        self.label = label
        self.config = dict(config) if config else {}
        self.seed = seed
        self.settings = dict(settings) if settings else {}
        self._repo_root = repo_root
        self._files: list[_FileRef] = []
        self._notes: list[str] = []
        self._metrics: dict[str, Any] = {}
        self._limitations: list[str] = []
        self._started_monotonic: float | None = None
        self._started_wall: float | None = None
        self.status = "not_started"

    # -- construction --------------------------------------------------------

    @classmethod
    def open(
        cls,
        directory: str | os.PathLike[str],
        *,
        label: str,
        config: Mapping[str, Any] | None = None,
        seed: int | None = None,
        settings: Mapping[str, Any] | None = None,
        repo_root: str | os.PathLike[str] | None = None,
    ) -> RunRecord:
        """Create a run directory and return the record as a context manager.

        Raises
        ------
        InvalidInputError
            If the directory already exists and is not empty. This is the write-once
            rule; it is not overridable by a flag, because a flag would be used.
        """
        path = pathlib.Path(directory)
        if path.exists():
            if not path.is_dir():
                raise InvalidInputError(f"run path {path} exists and is not a directory")
            if any(path.iterdir()):
                raise InvalidInputError(
                    f"run directory {path} is not empty. A run directory is written once: "
                    f"choose a new directory for this run rather than overwriting a previous "
                    f"result. If the previous result is genuinely superseded, move or delete it "
                    f"deliberately and say so in the case report."
                )
        path.mkdir(parents=True, exist_ok=True)
        return cls(
            path,
            label=label,
            config=config,
            seed=seed,
            settings=settings,
            repo_root=repo_root,
        )

    # -- recording -----------------------------------------------------------

    def add_input(self, path: str | os.PathLike[str], role: str = "input") -> pathlib.Path:
        """Hash and record a file the run consumed. Returns the path for chaining."""
        resolved = pathlib.Path(path)
        if not resolved.is_file():
            raise InvalidInputError(f"declared {role} {resolved} does not exist")
        self._files.append(
            _FileRef(
                role=role, path=str(resolved), sha256=sha256_file(resolved), bytes=resolved.stat().st_size
            )
        )
        return resolved

    def add_output(self, path: str | os.PathLike[str], role: str = "output") -> pathlib.Path:
        """Hash and record a file the run produced. Returns the path for chaining."""
        resolved = pathlib.Path(path)
        if not resolved.is_file():
            raise InvalidInputError(f"declared {role} {resolved} does not exist")
        self._files.append(
            _FileRef(
                role=role, path=str(resolved), sha256=sha256_file(resolved), bytes=resolved.stat().st_size
            )
        )
        return resolved

    def write_json(self, name: str, payload: Any, role: str = "output") -> pathlib.Path:
        """Write a JSON artefact into the run directory and record it."""
        path = self.directory / name
        path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
        return self.add_output(path, role=role)

    def write_text(self, name: str, text: str, role: str = "output") -> pathlib.Path:
        """Write a text artefact into the run directory and record it."""
        path = self.directory / name
        path.write_text(text, encoding="utf-8")
        return self.add_output(path, role=role)

    def note(self, message: str) -> None:
        """Append a free-text observation to the record."""
        self._notes.append(message)

    def limitation(self, message: str) -> None:
        """Append a limitation that must travel with any use of this result."""
        self._limitations.append(message)

    def metric(self, name: str, value: Any) -> None:
        """Record a named scalar result, so a later comparison need not re-parse a report."""
        self._metrics[name] = value

    def metrics(self, **values: Any) -> None:
        """Record several named results at once."""
        self._metrics.update(values)

    # -- context manager -----------------------------------------------------

    def __enter__(self) -> RunRecord:
        """Start the clock and mark the run as running."""
        self._started_monotonic = time.monotonic()
        self._started_wall = time.time()
        self.status = "running"
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: types.TracebackType | None,
    ) -> Literal[False]:
        """Write the run record, then let the exception propagate untouched."""
        elapsed = None
        if self._started_monotonic is not None:
            elapsed = time.monotonic() - self._started_monotonic
        self.status = "completed" if exc is None else "failed"
        record: dict[str, Any] = {
            "schema_version": RECORD_SCHEMA_VERSION,
            "label": self.label,
            "status": self.status,
            "started_utc": (
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self._started_wall))
                if self._started_wall is not None
                else None
            ),
            "elapsed_seconds": elapsed,
            "seed": self.seed,
            "config": self.config,
            "config_sha256": canonical_hash(self.config),
            "settings": self.settings,
            "settings_sha256": canonical_hash(self.settings),
            "source_revision": source_revision(self._repo_root),
            "environment": environment(),
            "files": [dataclasses.asdict(f) for f in self._files],
            "metrics": self._metrics,
            "notes": self._notes,
            "limitations": self._limitations,
        }
        if exc is not None:
            record["failure"] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": "".join(traceback.format_exception(exc_type, exc, tb)),
            }
        target = self.directory / RUN_RECORD_FILENAME
        target.write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8")
        # Literal[False] rather than bool: a context manager whose __exit__ is typed
        # `bool` is one the type checker must assume may swallow exceptions. This one
        # never does, and a failed run that vanished into a suppressed exception would
        # be the worst possible outcome for a provenance record.
        return False


def load_run_record(directory: str | os.PathLike[str]) -> dict[str, Any]:
    """Read a previously written run record."""
    path = pathlib.Path(directory) / RUN_RECORD_FILENAME
    if not path.is_file():
        raise InvalidInputError(f"no {RUN_RECORD_FILENAME} in {directory}")
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def verify_run_record(directory: str | os.PathLike[str]) -> list[str]:
    """Re-hash every file a run declared and report the discrepancies.

    Returns a list of human-readable problems; an empty list means every declared
    input and output is byte-identical to what the run recorded. A non-empty list is
    the signal that a result and its inputs have drifted apart and the result should
    not be quoted until the run is repeated.
    """
    record = load_run_record(directory)
    problems: list[str] = []
    for entry in record.get("files", []):
        path = pathlib.Path(entry["path"])
        if not path.is_file():
            problems.append(f"missing {entry['role']}: {path}")
            continue
        actual = sha256_file(path)
        if actual != entry["sha256"]:
            problems.append(
                f"changed {entry['role']}: {path} now {actual[:16]}..., recorded {entry['sha256'][:16]}..."
            )
    return problems


def iter_run_records(root: str | os.PathLike[str]) -> Iterable[tuple[pathlib.Path, dict[str, Any]]]:
    """Yield ``(directory, record)`` for every run record found beneath ``root``.

    Includes failed runs. An experiment register that lists only the successes is not
    a register.
    """
    base = pathlib.Path(root)
    for path in sorted(base.rglob(RUN_RECORD_FILENAME)):
        yield path.parent, json.loads(path.read_text(encoding="utf-8"))

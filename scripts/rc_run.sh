#!/bin/bash
# Record one release check: command, cwd, timestamps, real exit status and a log path.
#
# The exit status comes from the command itself, never from the tail of a pipe -- a check
# whose failure is swallowed by `| tail` is a check that does not exist.
#
# The repository root is derived, not written in. An absolute path from one machine in a
# committed script is both unreproducible and a leak, and the repository's own hygiene gate
# refuses it -- which is how the first version of this file was caught.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EV="$ROOT/docs/release/evidence"
mkdir -p "$EV/logs"

label="$1"; shift
cwd="$1"; shift

start=$(python3 -c 'import datetime;print(datetime.datetime.now(datetime.timezone.utc).isoformat())')
log="$EV/logs/${label}.log"
( cd "$cwd" && "$@" ) >"$log" 2>&1
code=$?
end=$(python3 -c 'import datetime;print(datetime.datetime.now(datetime.timezone.utc).isoformat())')

ROOT="$ROOT" python3 - "$label" "$cwd" "$start" "$end" "$code" "$log" "$@" <<'PY'
import json, os, pathlib, sys

label, cwd, start, end, code, log = sys.argv[1:7]
command = sys.argv[7:]
root = pathlib.Path(os.environ["ROOT"])
record = {
    "label": label,
    "command": command,
    "cwd_relative_to_repo": os.path.relpath(cwd, root),
    "started_utc": start,
    "ended_utc": end,
    "exit_code": int(code),
    "log": os.path.relpath(log, root),
    "log_bytes": pathlib.Path(log).stat().st_size if pathlib.Path(log).is_file() else 0,
}
with (root / "docs/release/evidence/command_log.jsonl").open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(record) + "\n")
print(f"[{label}] exit={code}")
PY
exit $code

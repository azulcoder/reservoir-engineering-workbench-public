#!/usr/bin/env python3
"""Reference-data acquisition recipe for the NIST Chemistry WebBook extract.

This script is the only network-touching entry point in the repository, and in the
published tree it acquires nothing unless a person deliberately tells it to. Nothing in
the test suite, the demo, the packaging metadata, the installer or CI invokes the
acquisition path, and there is no default that reaches the network.

Why acquisition is gated
------------------------
The values this script retrieves are NIST Standard Reference Data. SRD is a statutory
exception to the public-domain status of works of the United States Government
(Standard Reference Data Act, Public Law 90-396), the Chemistry WebBook asserts
copyright over its output, and nothing retrieved from NIST establishes that citation
alone permits redistributing an extract. This project therefore does not redistribute
one: ``data/reference/`` holds metadata only. See ``docs/release/PUBLIC_DATA_POLICY.md``
for the decision and its evidence, which is a conservative publication decision and not
an adjudication of copyright exceptions.

That decision is about redistribution, not about you retrieving values for your own use
from a public interface. This script exists so that retrieval stays reproducible and
verifiable. It requires you to say where the files go and on what basis you are
retrieving them, and it records your answer next to the data.

There is deliberately no ``--accept-terms`` flag. A flag is not evidence of permission;
it only records that somebody was willing to pass a flag.

Commands
--------
    python3 scripts/fetch_nist_reference.py plan
    python3 scripts/fetch_nist_reference.py acquire --out DIR --access-basis TEXT
    python3 scripts/fetch_nist_reference.py verify --out DIR

``plan`` prints the exact requests and touches no network, so the recipe is readable
without running it. ``verify`` re-hashes stored files against ``MANIFEST.json`` and
touches no network either. Only ``acquire`` makes a request, and only when told to.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

WEBBOOK_ENDPOINT = "https://webbook.nist.gov/cgi/fluid.cgi"

#: Repository root, used to detect an output directory that would put restricted values
#: inside the tree this project publishes.
REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

#: Species requested. The CAS-derived WebBook identifiers are stable; the reference-model
#: attribution is recorded so the provenance manifest states what produced the numbers.
SPECIES = {
    "methane": {
        "webbook_id": "C74828",
        "formula": "CH4",
        "molar_mass_lbm_per_lbmol": 16.0425,
        "molar_mass_source": "IUPAC 2021 standard atomic weights, C 12.011 + 4 x H 1.008",
        "critical_temperature_k": 190.564,
        "critical_pressure_psia": 667.06,
        "eos_reference": (
            "Setzmann, U. and Wagner, W. (1991), A New Equation of State and Tables of "
            "Thermodynamic Properties for Methane Covering the Range from the Melting Line "
            "to 625 K at Pressures up to 1000 MPa, J. Phys. Chem. Ref. Data 20(6), 1061-1155, "
            "doi:10.1063/1.555898."
        ),
        "viscosity_reference": (
            "Quinones-Cisneros, S.E., Huber, M.L. and Deiters, U.K. (2011), unpublished work, "
            "as cited by the NIST Chemistry WebBook. Do not substitute Younglove & Ely (1987) "
            "here: that is the older methane transport reference and it is not what the "
            "WebBook currently evaluates."
        ),
    },
    "carbon_dioxide": {
        "webbook_id": "C124389",
        "formula": "CO2",
        "molar_mass_lbm_per_lbmol": 44.0095,
        "molar_mass_source": "IUPAC 2021 standard atomic weights, C 12.011 + 2 x O 15.999",
        "critical_temperature_k": 304.1282,
        "critical_pressure_psia": 1070.0,
        "eos_reference": (
            "Span, R. and Wagner, W. (1996), A New Equation of State for Carbon Dioxide "
            "Covering the Fluid Region from the Triple-Point Temperature to 1100 K at "
            "Pressures up to 800 MPa, J. Phys. Chem. Ref. Data 25(6), 1509-1596."
        ),
        "viscosity_reference": (
            "Laesecke, A. and Muzny, C.D. (2017), Reference Correlation for the Viscosity of "
            "Carbon Dioxide, J. Phys. Chem. Ref. Data 46(1), 013107, doi:10.1063/1.4977429."
        ),
    },
    "nitrogen": {
        "webbook_id": "C7727379",
        "formula": "N2",
        "molar_mass_lbm_per_lbmol": 28.0134,
        "molar_mass_source": "IUPAC 2021 standard atomic weights, 2 x N 14.007",
        "critical_temperature_k": 126.192,
        "critical_pressure_psia": 492.52,
        "eos_reference": (
            "Span, R., Lemmon, E.W., Jacobsen, R.T, Wagner, W. and Yokozeki, A. (2000), "
            "A Reference Equation of State for the Thermodynamic Properties of Nitrogen for "
            "Temperatures from 63.151 to 1000 K and Pressures to 2200 MPa, "
            "J. Phys. Chem. Ref. Data 29(6), 1361-1433."
        ),
        "viscosity_reference": (
            "Lemmon, E.W. and Jacobsen, R.T (2004), Viscosity and Thermal Conductivity "
            "Equations for Nitrogen, Oxygen, Argon, and Air, "
            "Int. J. Thermophys. 25(1), 21-69."
        ),
    },
}

#: Isotherms in degrees Fahrenheit. Chosen to bracket the temperature of a shallow-to-
#: moderately-deep gas reservoir (roughly 60-110 degC) while staying single-phase over the
#: whole pressure sweep for each species at the stated conditions.
ISOTHERMS_DEGF = (100.0, 160.0, 200.0, 260.0, 320.0)

#: Pressure sweep in psia. 200 psia increments from 200 to 6000 psia.
P_LOW_PSIA, P_HIGH_PSIA, P_INC_PSIA = 200.0, 6000.0, 200.0

REQUEST_UNITS = {
    "TUnit": "F",
    "PUnit": "psia",
    "DUnit": "lbm/ft3",
    "HUnit": "Btu/lbm",
    "WUnit": "ft/s",
    "VisUnit": "uPa*s",
    "STUnit": "N/m",
    "RefState": "DEF",
    "Digits": "8",
}

USER_AGENT = (
    "reservoir-engineering-workbench/0.2 (research reference acquisition; contact via repository issues)"
)

#: Environment variables that indicate an automated context. Acquisition refuses in all
#: of them. A build server, a test runner and an installer cannot hold an access basis,
#: so anything that acquires from one is acquiring on nobody's authority.
AUTOMATION_MARKERS = (
    "CI",
    "CONTINUOUS_INTEGRATION",
    "GITHUB_ACTIONS",
    "GITLAB_CI",
    "BUILDKITE",
    "CIRCLECI",
    "TRAVIS",
    "TF_BUILD",
    "JENKINS_URL",
    "TEAMCITY_VERSION",
    "PYTEST_CURRENT_TEST",
    "PIP_BUILD_TRACKER",
    "PIP_REQ_TRACKER",
    "_PYPROJECT_HOOKS_BUILD_BACKEND",
    "PEP517_BUILD_BACKEND",
)

#: Access-basis strings that carry no information. Rejected so the field cannot become a
#: box that gets ticked. This list is about content-free answers only; it is not a filter
#: on which bases are acceptable, which is not this script's judgement to make.
EMPTY_BASIS_TOKENS = frozenset(
    {
        "",
        "-",
        "n/a",
        "na",
        "none",
        "nil",
        "null",
        "tbd",
        "todo",
        "yes",
        "y",
        "ok",
        "okay",
        "true",
        "1",
        "accept",
        "accepted",
        "i accept",
        "agree",
        "agreed",
        "i agree",
        "terms",
        "terms accepted",
        "accept terms",
        "consent",
        "permission",
        "granted",
        "test",
        "testing",
        "because",
        "reasons",
    }
)

MIN_BASIS_CHARACTERS = 24

#: Written into the output directory alongside the data whenever acquisition succeeds.
ACQUISITION_RECORD_NAME = "ACQUISITION_RECORD.json"

#: Written into the output directory when it sits inside this checkout, so that the
#: retrieved files stay out of git even though a parent .gitignore rule may re-include
#: them. Rules in a nested ignore file take precedence for that directory.
LOCAL_IGNORE_NAME = ".gitignore"
LOCAL_IGNORE_BODY = """\
# Written by scripts/fetch_nist_reference.py.
#
# The retrieved NIST Chemistry WebBook extract is not redistributed by this project.
# These rules sit deeper than the repository .gitignore and therefore win for this
# directory, including over any rule there that re-includes *.tsv.
nist_*.tsv
*.tsv
ACQUISITION_RECORD.json
"""


class AcquisitionRefusedError(RuntimeError):
    """Acquisition was asked for in a context or shape the script will not serve."""


def build_url(webbook_id: str, temperature_degf: float) -> str:
    query = {
        "Action": "Data",
        "Wide": "on",
        "ID": webbook_id,
        "Type": "IsoTherm",
        "T": f"{temperature_degf:g}",
        "PLow": f"{P_LOW_PSIA:g}",
        "PHigh": f"{P_HIGH_PSIA:g}",
        "PInc": f"{P_INC_PSIA:g}",
        **REQUEST_UNITS,
    }
    return f"{WEBBOOK_ENDPOINT}?{urllib.parse.urlencode(query)}"


def request_plan() -> list[tuple[str, float, str]]:
    """Return every ``(species, isotherm, url)`` the acquisition would request."""
    return [
        (name, temperature, build_url(meta["webbook_id"], temperature))
        for name, meta in SPECIES.items()
        for temperature in ISOTHERMS_DEGF
    ]


def fetch(url: str, timeout: float = 60.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset)


def sha256_of(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_rows(payload: str) -> tuple[list[str], list[list[str]]]:
    lines = [line for line in payload.splitlines() if line.strip()]
    if not lines:
        raise ValueError("empty payload")
    header = lines[0].split("\t")
    rows = [line.split("\t") for line in lines[1:]]
    bad = [r for r in rows if len(r) != len(header)]
    if bad:
        raise ValueError(f"{len(bad)} rows do not match the header width {len(header)}")
    return header, rows


def dedupe_rows(header: list[str], rows: list[list[str]]) -> list[list[str]]:
    """Drop duplicate (T, P) rows that the WebBook emits at a phase-label boundary.

    At the vapour/supercritical boundary the service repeats the same state with two
    different ``Phase`` labels. The thermodynamic content is identical; keeping both
    would double-weight that state in any comparison. The first occurrence is kept and
    the removal is reported in the manifest rather than performed silently.
    """
    try:
        t_col = header.index("Temperature (F)")
        p_col = header.index("Pressure (psia)")
    except ValueError as exc:  # pragma: no cover - guards against a served-format change
        raise ValueError(f"expected temperature/pressure columns, got {header}") from exc
    seen: set[tuple[str, str]] = set()
    kept: list[list[str]] = []
    for row in rows:
        key = (row[t_col], row[p_col])
        if key in seen:
            continue
        seen.add(key)
        kept.append(row)
    return kept


def automation_markers_present(environ: dict[str, str] | None = None) -> list[str]:
    """Return the automation environment variables that are set and non-empty."""
    env = os.environ if environ is None else environ
    return [name for name in AUTOMATION_MARKERS if env.get(name)]


def running_under_pytest() -> bool:
    """Report whether this process is a test run, independently of the environment."""
    return "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ


def check_access_basis(basis: str | None) -> str:
    """Validate the operator-supplied access basis, returning the normalised text.

    The check is for substance, not for merit. A basis that is blank, or one of a short
    list of content-free answers, is rejected because such a field is a formality rather
    than a record. Whether a stated basis is a good one is the operator's judgement and
    is recorded verbatim so that it can be reviewed.
    """
    if basis is None:
        raise AcquisitionRefusedError(
            "acquisition needs --access-basis: one sentence recording why you are entitled "
            "to retrieve and use these values, which is written into "
            f"{ACQUISITION_RECORD_NAME} next to the data. There is no flag that supplies "
            "this for you, because a flag is not evidence of permission."
        )
    text = " ".join(basis.split())
    if text.strip().lower().strip(".!") in EMPTY_BASIS_TOKENS:
        raise AcquisitionRefusedError(
            f"--access-basis {basis!r} records nothing. State the actual basis, for example "
            "your own permission correspondence with NIST SRD, an institutional licence, or "
            "that this is a local retrieval for your own use which you will not redistribute."
        )
    if len(text) < MIN_BASIS_CHARACTERS:
        raise AcquisitionRefusedError(
            f"--access-basis is {len(text)} characters; at least {MIN_BASIS_CHARACTERS} are "
            "required so that the recorded basis is a sentence someone can review."
        )
    return text


def check_context() -> None:
    """Refuse acquisition in any automated context."""
    markers = automation_markers_present()
    if running_under_pytest() and "PYTEST_CURRENT_TEST" not in markers:
        markers.append("pytest imported in this process")
    if markers:
        raise AcquisitionRefusedError(
            "acquisition refuses to run here: this looks like an automated context "
            f"({', '.join(markers)}). CI jobs, test runs, build backends and installers "
            "cannot hold an access basis, so nothing that runs unattended may retrieve "
            "this data. Run the command yourself, from a shell, with --access-basis."
        )


def check_destination(out_dir: pathlib.Path, allow_in_repository: bool) -> pathlib.Path:
    """Resolve the output directory and refuse an in-repository one unless overridden."""
    resolved = out_dir.expanduser().resolve()
    inside = resolved == REPO_ROOT or REPO_ROOT in resolved.parents
    if inside and not allow_in_repository:
        raise AcquisitionRefusedError(
            f"{resolved} is inside this checkout ({REPO_ROOT}). Restricted values written "
            "there can reach a commit, and git history keeps what the working tree no longer "
            "shows. Write them outside the checkout, or pass --allow-in-repository if you "
            "have read what that does and accept the risk yourself."
        )
    return resolved


def write_local_ignore(out_dir: pathlib.Path) -> pathlib.Path | None:
    """Drop a nested ignore file so in-repository retrievals cannot be committed."""
    path = out_dir / LOCAL_IGNORE_NAME
    if path.exists():
        return None
    path.write_text(LOCAL_IGNORE_BODY, encoding="utf-8")
    return path


def write_acquisition_record(out_dir: pathlib.Path, basis: str, urls: list[str]) -> pathlib.Path:
    """Record who retrieved what, when and on what stated basis, next to the data."""
    record = {
        "retrieved_utc": _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endpoint": WEBBOOK_ENDPOINT,
        "source": "NIST Chemistry WebBook, SRD 69, Thermophysical Properties of Fluid Systems",
        "access_basis_stated_by_operator": basis,
        "access_basis_is_not_verified_by_this_script": (
            "This script records the basis. It does not and cannot verify it. Nothing here "
            "constitutes permission from NIST."
        ),
        "redistribution": (
            "These files are not redistributed by this project. See "
            "docs/release/PUBLIC_DATA_POLICY.md. Do not commit them, and do not publish "
            "derived tables that reproduce the retrieved values."
        ),
        "citation_required": (
            "Cite NIST Chemistry WebBook, SRD 69, and the per-species reference equation "
            "recorded in MANIFEST.json wherever these values or results derived from them "
            "are reported."
        ),
        "request_urls": urls,
    }
    path = out_dir / ACQUISITION_RECORD_NAME
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path


def acquire(out_dir: pathlib.Path, pause_seconds: float, access_basis: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    query_date = _dt.datetime.now(_dt.UTC).strftime("%Y-%m-%d")
    manifest: dict = {
        "acquired_utc_date": query_date,
        "endpoint": WEBBOOK_ENDPOINT,
        "source": "NIST Chemistry WebBook, SRD 69, Thermophysical Properties of Fluid Systems",
        "source_url": "https://webbook.nist.gov/chemistry/fluid/",
        "what_these_numbers_are": (
            "Values evaluated by the reference equations of state that the NIST Chemistry "
            "WebBook cites for each species. They are model outputs traceable to the cited "
            "correlations, not new laboratory measurements."
        ),
        "citation_required": (
            "Cite NIST Chemistry WebBook, SRD 69, and the per-species reference equation "
            "recorded below, whenever these values or results derived from them are reported. "
            "Citation is required. It is not, on the evidence retrieved for this project, "
            "sufficient on its own to license redistribution."
        ),
        "redistribution": {
            "distributed_in_this_repository": False,
            "decision": "non-redistribution",
            "decision_kind": (
                "Conservative publication decision. Not an adjudication of copyright "
                "exceptions and not a legal opinion."
            ),
            "policy_document": "docs/release/PUBLIC_DATA_POLICY.md",
            "acquired_under_basis": access_basis,
        },
        "request_units": dict(REQUEST_UNITS),
        "pressure_grid_psia": {"low": P_LOW_PSIA, "high": P_HIGH_PSIA, "increment": P_INC_PSIA},
        "isotherms_degF": list(ISOTHERMS_DEGF),
        "files": [],
    }

    for name, meta in SPECIES.items():
        header: list[str] | None = None
        collected: list[list[str]] = []
        urls: list[str] = []
        duplicates_removed = 0
        for temperature in ISOTHERMS_DEGF:
            url = build_url(meta["webbook_id"], temperature)
            urls.append(url)
            try:
                payload = fetch(url)
            except (urllib.error.URLError, TimeoutError) as exc:
                raise SystemExit(f"retrieval failed for {name} at {temperature} F: {exc}") from exc
            this_header, rows = parse_rows(payload)
            if header is None:
                header = this_header
            elif this_header != header:
                raise SystemExit(f"column layout changed between isotherms for {name}")
            deduped = dedupe_rows(this_header, rows)
            duplicates_removed += len(rows) - len(deduped)
            collected.extend(deduped)
            time.sleep(pause_seconds)

        assert header is not None
        path = out_dir / f"nist_{name}_isotherms.tsv"
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("\t".join(header) + "\n")
            for row in collected:
                handle.write("\t".join(row) + "\n")

        manifest["files"].append(
            {
                "path": path.name,
                "species": name,
                "formula": meta["formula"],
                "webbook_id": meta["webbook_id"],
                "molar_mass_lbm_per_lbmol": meta["molar_mass_lbm_per_lbmol"],
                "molar_mass_source": meta["molar_mass_source"],
                "critical_temperature_k": meta["critical_temperature_k"],
                "critical_pressure_psia": meta["critical_pressure_psia"],
                "critical_constants_source": (
                    "NIST Chemistry WebBook fluid page for this species, 'Additional fluid properties'."
                ),
                "eos_reference": meta["eos_reference"],
                "viscosity_reference": meta["viscosity_reference"],
                "request_urls": urls,
                "columns": header,
                "rows": len(collected),
                "duplicate_phase_boundary_rows_removed": duplicates_removed,
                "sha256": sha256_of(path),
            }
        )
        print(f"  {name:>15}: {len(collected)} rows, {duplicates_removed} duplicate rows removed")

    manifest_path = out_dir / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify(out_dir: pathlib.Path) -> int:
    manifest_path = out_dir / "MANIFEST.json"
    if not manifest_path.exists():
        print(f"no manifest at {manifest_path}", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    failures = 0
    for entry in manifest["files"]:
        path = out_dir / entry["path"]
        if not path.exists():
            print(f"MISSING  {entry['path']}", file=sys.stderr)
            failures += 1
            continue
        actual = sha256_of(path)
        if actual != entry["sha256"]:
            print(f"DIGEST   {entry['path']}: {actual} != {entry['sha256']}", file=sys.stderr)
            failures += 1
        else:
            print(f"ok       {entry['path']}  {entry['rows']} rows  sha256 {actual[:16]}...")
    if failures:
        print(
            "\nverify is the gate for a checkout that holds the extract. In the published tree "
            "the files are supposed to be absent, and scripts/check_public_release.py is the "
            "gate that applies there.",
            file=sys.stderr,
        )
    return 1 if failures else 0


def command_plan(_args: argparse.Namespace) -> int:
    print(f"endpoint: {WEBBOOK_ENDPOINT}")
    print(f"isotherms (degF): {', '.join(f'{t:g}' for t in ISOTHERMS_DEGF)}")
    print(f"pressure sweep (psia): {P_LOW_PSIA:g} to {P_HIGH_PSIA:g} step {P_INC_PSIA:g}")
    print(f"requests: {len(request_plan())}\n")
    for name, temperature, url in request_plan():
        print(f"{name} @ {temperature:g} F\n  {url}")
    print(
        "\nNo request was made. These values are NIST Standard Reference Data and are not "
        "redistributed by this project; see docs/release/PUBLIC_DATA_POLICY.md before "
        "retrieving them."
    )
    return 0


def command_acquire(args: argparse.Namespace) -> int:
    if getattr(args, "accept_terms", False):
        print(
            "there is no --accept-terms in this script, and the flag you passed does nothing "
            "except refuse. Accepting terms in an argument vector is not evidence that anyone "
            "granted permission; it only records that a flag was typed. Use --access-basis to "
            "state the actual basis, which is written into the acquisition record.",
            file=sys.stderr,
        )
        return 2
    try:
        basis = check_access_basis(args.access_basis)
        check_context()
        out_dir = check_destination(pathlib.Path(args.out), args.allow_in_repository)
    except AcquisitionRefusedError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2

    print(f"retrieving from {WEBBOOK_ENDPOINT} into {out_dir}")
    print(f"recorded access basis: {basis}")
    out_dir.mkdir(parents=True, exist_ok=True)
    if REPO_ROOT in out_dir.parents or out_dir == REPO_ROOT:
        written = write_local_ignore(out_dir)
        if written is not None:
            print(f"wrote {written} so the retrieved files cannot be committed from here")
    manifest = acquire(out_dir, args.pause, basis)
    record = write_acquisition_record(out_dir, basis, [u for _, _, u in request_plan()])
    print(f"manifest written to {out_dir / 'MANIFEST.json'}")
    print(f"acquisition record written to {record}")
    print(f"{len(manifest['files'])} files retrieved; they are yours to use and not to republish")
    return verify(out_dir)


def command_verify(args: argparse.Namespace) -> int:
    return verify(pathlib.Path(args.out))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fetch_nist_reference.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Kept so that the historical invocation still verifies rather than erroring, and so
    # that a bare run cannot fall through to the network.
    parser.add_argument("--verify-only", action="store_true", help="alias for the verify command")
    parser.add_argument("--out", default=None, help=argparse.SUPPRESS)

    sub = parser.add_subparsers(dest="command")

    plan = sub.add_parser("plan", help="print the exact requests without making any")
    plan.set_defaults(handler=command_plan)

    acquire_parser = sub.add_parser(
        "acquire",
        help="retrieve the extract into a directory you name, under a basis you record",
    )
    acquire_parser.add_argument("--out", required=True, help="output directory; no default")
    acquire_parser.add_argument(
        "--access-basis",
        default=None,
        help="one sentence recording why you are entitled to retrieve and use these values",
    )
    acquire_parser.add_argument(
        "--allow-in-repository",
        action="store_true",
        help="permit an output directory inside this checkout; refused by default",
    )
    acquire_parser.add_argument("--pause", type=float, default=1.0, help="seconds between requests")
    acquire_parser.add_argument("--accept-terms", action="store_true", help=argparse.SUPPRESS)
    acquire_parser.set_defaults(handler=command_acquire)

    verify_parser = sub.add_parser("verify", help="re-hash stored files against MANIFEST.json")
    verify_parser.add_argument("--out", default="data/reference", help="directory to verify")
    verify_parser.set_defaults(handler=command_verify)

    return parser


NO_COMMAND_MESSAGE = """\
this script does not acquire anything by default.

  plan     print the exact requests, make none
  acquire  retrieve into a directory you name, under an access basis you record
  verify   re-hash stored files against MANIFEST.json

The values are NIST Standard Reference Data and are not redistributed by this project.
Read docs/release/PUBLIC_DATA_POLICY.md and data/reference/README.md first, then:

  python3 scripts/fetch_nist_reference.py acquire --out DIR --access-basis TEXT
"""


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        if args.verify_only:
            return verify(pathlib.Path(args.out or "data/reference"))
        print(NO_COMMAND_MESSAGE, file=sys.stderr)
        return 2

    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())

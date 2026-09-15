#!/usr/bin/env python3
"""Confirm each flagship page still carries every required evidence category.

Why this exists, narrowly
-------------------------
During the A4 restructure two pieces of content were dropped and restored: the scenario
explorer and the "Four statements, kept apart" callout. A restructure moves content between
reading depths, and the failure mode it introduces is not a broken page -- it is a page that
builds, renders and tests green while a required category of evidence has quietly gone.

This checks categories, not prose. Each requirement is a short list of alternative markers,
and the requirement is met if any one of them appears. That is deliberate: a check that
pinned paragraphs verbatim would fail on every honest edit and would train people to ignore
it. What it can catch is a whole category disappearing.

It reads the built HTML, so it tests what a reader receives rather than what the source
intends.

    python3 scripts/check_page_content.py [--dist site/dist]
"""

from __future__ import annotations

import argparse
import html
import pathlib
import re

#: page -> requirement name -> alternative markers, any one of which satisfies it.
REQUIRED: dict[str, dict[str, tuple[str, ...]]] = {
    "index.html": {
        "project purpose": ("reservoir-engineering answer look right", "questions run through this work"),
        "A4 flagship finding": ("wrong inventory", "gas in place the p/Z fit reports"),
        "B1 flagship finding": ("inputs are wrong", "seeded analyst errors"),
        "synthetic, not field validated": ("Not field-validated", "No field data of any kind"),
        "route into the studies": ("/studies/",),
    },
    "studies/a4/index.html": {
        "executive question": ("How wrong is the recovered gas in place",),
        "headline result": ("R-squared of the volumetric fit", "0.999859"),
        "known synthetic truth": ("known truth", "112.5 Bscf"),
        "engineering implication": ("Engineering implication",),
        "principal limitation": ("BIGGEST LIMITATION", "Biggest limitation", "biggest-limitation"),
        "hero evidence": ("figure--hero",),
        "supporting evidence": ("figure--supporting",),
        "technical evidence access": ('id="technical"',),
        "complete limitations access": ('id="limits"',),
        "reproducibility access": ('id="reproduce"',),
        "downloads route": ("Download the data", "download"),
        "scenario explorer": ("data-explorer-controls",),
        "four statements scoping": ("Four statements, kept apart",),
    },
    "studies/b1/index.html": {
        "known-answer instrument result": ("permeability-thickness recovered from the data",),
        "defect-visibility finding": ("nothing showed it", "materially wrong"),
        "negative control": ("negative control",),
        "synthetic limitation": ("Synthetic", "No field data of any kind"),
        "IARF window limitation": ("window was handed to the estimator", "interpretation window"),
        "zero storage by design": ("storage is zero by", "zero by declared design"),
        "technical evidence": ('id="technical"',),
        "reproducibility/download route": ('id="reproduce"',),
    },
}


def text_of(path: pathlib.Path) -> str:
    """Return the page as one searchable string, with the raw markup kept alongside."""
    raw = path.read_text(encoding="utf-8")
    stripped = re.sub(r"<svg\b.*?</svg>", " ", raw, flags=re.S)
    stripped = re.sub(r"<[^>]+>", " ", stripped)
    return raw + "\n" + html.unescape(re.sub(r"\s+", " ", stripped))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", default="site/dist")
    args = parser.parse_args(argv)
    dist = pathlib.Path(args.dist)

    problems: list[str] = []
    checked = 0
    for page, requirements in REQUIRED.items():
        path = dist / page
        if not path.exists():
            problems.append(f"MISSING PAGE  {page}")
            continue
        body = text_of(path)
        for name, markers in requirements.items():
            checked += 1
            if not any(m in body for m in markers):
                problems.append(f"{page}: required category absent -- {name}")

    print(f"page-content: {checked} required categories across {len(REQUIRED)} flagship pages")
    if not problems:
        print("page-content: PASS - every required evidence category is present")
        return 0
    print(f"page-content: FAIL - {len(problems)} problem(s)")
    for p in problems:
        print(f"  {p}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

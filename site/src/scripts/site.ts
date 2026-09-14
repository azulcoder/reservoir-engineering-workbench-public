/**
 * Facts that appear on more than one page, written down once.
 *
 * Everything in this file is a measurement or a policy recorded in the repository, with
 * the file it came from named beside it. Nothing here is an estimate, a projection or a
 * round number chosen for the page. Where a number could not be measured — a hosted CI
 * run, a deployment, an external validation — the field says so in words rather than
 * carrying a zero that a reader could mistake for a measurement.
 */

import type { SitePath } from "../lib/urls";

export interface NavItem {
  path: SitePath;
  label: string;
}

/** Primary navigation. Only routes that exist and are populated. */
export const NAV: NavItem[] = [
  { path: "/studies/", label: "Studies" },
  { path: "/methods/", label: "Methods" },
  { path: "/about/", label: "About" },
];

export const SITE_NAME = "Gas Reservoir Performance Lab";

/**
 * Verification counts, measured on 2026-09-13 and recorded in
 * `docs/release/VERIFICATION.md`. Re-measured in this candidate tree before publication.
 */
export const VERIFICATION = {
  date: "2026-09-14",
  interpreter: "CPython 3.13.2 on macOS, darwin arm64",
  profile: "public-core",
  /* The counts below are from `python3 scripts/verify.py --profile public-core
     --cases all`, and scripts/build_release.py fails the build if they disagree with the
     run it performs. Naming the invocation matters: adding --expect-reference-skips
     registers one further check, reference-skip-count-drift, so the same tree reports 10
     checks under that flag and 9 without it. An earlier version of this block carried 10
     collected and 9 passed, which was one number from each invocation. */
  testsCollected: 683,
  testsPassed: 663,
  testsFailedOrErrored: 0,
  testsSkipped: 20,
  skipReason:
    "the reference-dependent tests in tests/test_gas_properties.py, which compare computed deviation factors, densities and viscosities against a NIST Chemistry WebBook extract this repository does not redistribute",
  checksCollected: 9,
  checksPassed: 9,
  mandatoryChecksFailed: 0,
  casesReproduced: "3 of 3, each re-run into a fresh directory and diffed byte for byte",
  figureDataFiles: 7,
  reconciliationChecks: 43,
  reconcileTolerance: "1e-12 relative",
} as const;

/**
 * Things that have not happened. Stated as sentences because a count of zero reads as a
 * measurement, and none of these was measured — they did not occur.
 */
export const NOT_RUN = {
  hostedCi:
    "No hosted continuous-integration run stands behind the results on this site. Every one of them was produced on the author's own machine. Hosted execution status is recorded, with the run it describes, in the verification record rather than asserted here.",
  deployment:
    "No deployment has occurred. The site build runs locally and the deployment target is supplied to it as configuration; with no origin configured the build omits the canonical link and the Open Graph block rather than inventing a domain.",
  externalValidation:
    "The public profile is not externally validated. It compares the code against its own committed snapshots, its own analytic limits and its own closed forms. A profile that cannot see an independent reference cannot tell you the library is right about the physical world.",
  peerReview:
    "No human peer review took place. Every review pass in this repository was conducted under a different role by the same author; different role names do not create independent expertise or independent evidence.",
  fieldData:
    "No field data of any kind is used, implied or represented. Every history on this site is synthetic, and the known inventory the estimates are scored against is evaluation-only information that no field measurement provides.",
} as const;

/** The borrowed gate, quoted with the scope its own source gives it. */
export const GATE = {
  value: "1 percent",
  source: "PLAN.md:289",
  scope:
    "PLAN.md:289 scopes the 1 percent row by its own words to the delivered small-noise demonstration, and PLAN.md:282 states that these are proposed project gates, not regulatory requirements or universal engineering tolerances, to be scaled and justified for each case.",
  meaning:
    "Clearing it is a project demonstration result. It establishes nothing about physical interpretation and nothing about whether a number is adequate to carry a development decision.",
} as const;

/** The four statements the studies keep apart, in the order the case reports use. */
export const FOUR_STATEMENTS = [
  {
    name: "Numerical verification",
    text: "the estimator inverts the forward map to the precision the arithmetic allows",
  },
  {
    name: "Conditional pressure reconstruction",
    text: "a held-out pressure series reconstructed under stated conditions, including conditions a field analyst could not meet",
  },
  {
    name: "Physical interpretation",
    text: "what a reservoir is actually doing",
  },
  {
    name: "Decision adequacy",
    text: "whether a number is fit to carry a depletion or development decision",
  },
] as const;

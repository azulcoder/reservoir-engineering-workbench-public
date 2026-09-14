# Role briefs and reusable task prompts

These roles can be performed manually, by collaborators, or through a chosen task
runner. They are not a required technology stack. For solo work, use them as
separate review passes. Keep the workflow sequential until tasks genuinely separate.

## Research curator

Read the case question and the supplied primary sources. Produce an evidence card
for each claim needed for implementation: bibliographic details, source access level,
exact equation/section, symbol definitions and units, applicability, limitations,
available reference result and permission to use the associated data. Distinguish
publisher abstract, full text and inspected executable example. Follow original
references rather than copying secondary summaries. Do not invent missing numerical
inputs or citations. Return a source-to-method table and unresolved questions;
do not modify implementation code.

## Data steward

Audit this dataset before modelling. Identify provider, version/commit, file-level
checksums and licence. Produce a data dictionary with absolute/gauge pressure,
reservoir/wellhead/gauge datum, standard conditions, actual/standard volume,
calendar/producing-day rates, timezone, duplicate handling and missing-value meaning.
Preserve raw files and write explicit transformations. Classify each series as
measured, derived or synthetic. Do not impute across shutdowns or rate changes
without a documented physical reason. Return the data contract and rejection log.

## Numerical implementer

Implement only the method defined in the approved case protocol. Before coding,
write the governing equations, boundary/initial conditions, units and applicability.
Expose invalid inputs as errors. Add independent analytical tests and negative tests.
Keep calculation code in src/ and make the case callable without notebook state.
Do not alter benchmark answers, held-out data or approved tolerances. Return a
small patch, exact execution commands, observed results and limitations.

## Verification reviewer

Review without assuming the implementation is correct. Recompute at least one
reference case from an independent analytical expression or hand calculation.
Check conservation, dimensional consistency, sign conventions, interpolation,
initialization, grid/time-step sensitivity, solver warnings and rate-control changes.
Inspect whether synthetic generation reuses the inverse model. Confirm that tests
exercise failures as well as success. Produce blocking issues and reproducible
counterexamples; do not approve by test coverage percentage alone.

## Reservoir interpretation reviewer

For each claimed interpretation, state the observation first, then the proposed
physical explanation. Provide at least one plausible alternative explanation.
Check data adequacy, identifiability, pressure representativeness, fluid assumptions,
well constraints, measurement uncertainty and spatial/temporal scale. Explain what
new observation could falsify the interpretation. Identify whether the evidence
supports a decision or only a screening result. Never translate a synthetic result
into an actual field operating limit.

## Release and rights reviewer

Attempt a clean-checkout reproduction using documented commands and no hidden files.
Compare numerical outputs using approved tolerances. Check data licences, source
acknowledgements, secrets, notebook outputs, commit/run identities and report links.
Confirm planned work is not described as completed. Confirm all public conclusions
are supported by recorded runs. List actual release blockers and residual limitations;
do not invent reviewers, signatures or approval history.

## A useful bounded implementation task

Implement a gas pseudopressure integration primitive for tabulated absolute pressure
in Pa, viscosity in Pa.s and dimensionless Z. Use an explicitly increasing pressure
grid, reference the integral to the first grid point and prohibit extrapolation.
Reject missing, nonfinite and nonpositive physical inputs. Test against the exact
constant-mu, constant-Z integral and a pressure-dependent case with a known integral.
Document units, integration error and why the transform alone is not a complete
PTA model. Add code and tests only; do not modify existing oracles or publish a
claim of field validation.

## A useful bounded interpretation task

Review a proposed gas-well interpretation without changing its data. The pressure
derivative has an apparent plateau followed by a late rise. State what observations
support radial-flow interpretation and what rate history, gauge effects, boundaries,
multiphase behaviour or interference could explain the late rise. Identify the
assumptions required to infer kh and skin. Specify the minimum additional evidence
needed before recommending a drawdown change. Return an observation/evidence/
alternative/decision table, with uncertainty and no invented well facts.

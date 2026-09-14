# Gas Reservoir Performance Lab

## Purpose

Build a reproducible research workbench for understanding how fluid properties, pressure interpretation, reservoir uncertainty, and operating constraints influence gas-reservoir decisions. The central question is: **which conclusions remain defensible when the observations are incomplete and the model is imperfect?**

The project should read as a sustained engineering investigation, not as a collection of software demonstrations. A calculation is useful only when its inputs, assumptions, checks, and implications can be explained. A visually convincing history match is not a substitute for an identifiable model, and a successful simulator run is not evidence that the represented reservoir is physically correct.

Use one repository with progressively deeper case studies. Every completed case should contain an engineering question, a provenance record, reproducible code, explicit verification, a results discussion, and a short decision memo. Publish unfinished cases as protocols or work in progress, never as completed achievements.

The initial release is a calculation and workflow foundation. It includes working gas-volume, material-balance, pseudopressure, derivative, rate-integration, and component-balance utilities with tests. It does not include a field-validated reservoir model, a complete pressure-transient interpreter, an EOS flash package, or an executed commercial/open-source simulation study.

## 1. Definition of success

There are three separate standards of evidence:

**Numerical verification:** the code implements the stated equations correctly. Analytical cases, dimensional checks, independent reference values, and convergence tests support this claim.

**Benchmark reproduction:** a particular model, dataset revision, and solver setup produce documented results close enough to a credible reference for a stated purpose. Variant differences, unsupported keywords, and solver differences must be disclosed.

**Engineering validation and interpretation:** observations are suitable for the model, relevant mechanisms have been considered, uncertainty is represented, and recommendations remain credible under plausible alternatives. Synthetic self-consistency alone cannot satisfy this standard.

A reviewer should be able to answer five questions from each case without opening every notebook: what was asked, what was observed, why the model was appropriate, what could invalidate the conclusion, and what action or additional measurement follows. Show one meaningful conclusion with uncertainty rather than a large gallery of unexplained figures.

The workbench demonstrates methods and judgment. It does not establish years of professional experience, independent operational authority, or commercial-software proficiency that has not actually been acquired. OPM Flow's support for Eclipse-format decks is useful, but it is distinct from operating SLB ECLIPSE; Petrel model-building and Saphir interpretation are separate licensed workflows. [R09, R11, R21, R22]

## 2. Scope and case-study architecture

Use the following sequence. The first four completed stages form a coherent portfolio; the field-data and geomechanics extensions should not delay a sound foundation.

| Stage | Engineering question | Main evidence | Completion artifact |
|---|---|---|---|
| A. Gas properties and volumetric balance | How sensitive is inferred gas in place to pressure selection and gas-property assumptions? | Derived equations, verified utilities, independent property checks, synthetic counterexamples | Reproducible technical note and uncertainty discussion |
| B. Gas-well pressure transients | Which reservoir/well interpretations are supported by the pressure and rate histories? | Controlled synthetic tests, diagnostic plots, alternative models, independent forward checks | Interpretation notebook, parameter-identifiability analysis, test recommendation |
| C. Public simulation benchmark | Can a documented deck be initialized, run, checked, and interpreted reproducibly? | SPE1 smoke run, carefully identified SPE3 variant, balance and refinement checks | Benchmark reproduction report and discrepancy register |
| D. Mature-gas decision study | Which operating/development option is robust to uncertain support, deliverability, and constraints? | Explicitly synthetic capstone, history/holdout separation, matched scenario ensembles | Decision memo with uncertainty and information-value discussion |
| E. Real-field data extension | Which quality and operating issues prevent a clean engineering interpretation? | Official Volve data subset or later Norne case, rights/provenance review, data reconciliation | Surveillance report with clear oil/gas transfer limitations |
| F. Geomechanics extension | What information is needed before drawing a sanding or subsidence conclusion? | Bounded synthetic sensitivity study and selected original research | Screening note and missing-data requirements |

Do not build a dashboard first. Start with a correct table, a reproducible static result, and a readable interpretation. Add an interactive interface only after the calculations and evidence trail are stable. Machine-learning models are optional later comparisons; a physical baseline, time-aware validation, and leakage audit come first.

## 3. Research method and reading programme

### Start with equations and assumptions, not code searches

For each method, create an evidence card containing the engineering question, complete reference, exact chapter/equation/page once accessed, definitions and units, derivation or reproducible example, assumptions, known failure modes, and intended test. Mark whether the source is an original paper, textbook, official implementation, or product documentation. Record whether the full text, an abstract, or only metadata was available.

Conduct research in three passes. The foundation pass identifies the governing balances and dominant mechanisms. The implementation pass establishes numerical details, reference problems, and the exact dataset variant. The challenge pass looks for counterexamples, non-uniqueness, and cases where the chosen method produces a plausible but misleading answer. An uncertainty that cannot be resolved from accessible sources becomes a limitation or reading task, not an invented citation.

Use journal research to resolve a precise methodological question: for example, derivative smoothing under gauge noise, pressure-dependent gas properties, uncertain aquifer support, or coupled compaction parameters. Search the original publication in SPE journals, the Journal of Petroleum Science and Engineering and its successor records as applicable, Computational Geosciences, and primary institutional archives. Do not treat a secondary blog, copied notebook, or unattributed repository as the derivation's authority.

### Reading paired with a concrete output

| Reading | Purpose | Required output before moving on |
|---|---|---|
| Dake, *Fundamentals of Reservoir Engineering* [R01] | Material-balance logic and physical assumptions | Hand derivation of the gas p/Z relation, with a list of invalidating conditions |
| Lee and Wattenbarger, *Gas Reservoir Engineering* [R02] | Gas properties, performance, and test interpretation | A gas-data dictionary and a worked gas-property/material-balance example |
| Bourdet, *Well Test Analysis* [R03], supported by KAPPA's workflow [R09] | Pressure diagnostics, storage, skin, boundaries, and practical interpretation | An interpretation checklist and two competing explanations for a diagnostic response |
| Lie, open MRST textbook [R04] | Conservation, discretization, wells, initialization, solvers | A one-page explanation of how a simulator approximates the governing problem |
| Peng and Robinson's EOS paper [R06] and NIST property references [R07] | Thermodynamic model assumptions and independent property comparisons | A documented reference comparison; no unverified claim of complete mixture-flash validation |
| Al-Hussainy and co-authors [R08] | Real-gas pseudopressure and its scope | A unit-checked implementation with analytical and quadrature-convergence tests |
| Selected advanced MRST chapters [R05] | Compositional flow, uncertainty, or coupled physics when needed | A narrowly scoped extension with its own benchmark |
| Bunyu sanding study [R15] and compaction inversion research [R16] | Site-specific calibration and parameter ambiguity | A data-requirements and limitations memo, before any operational interpretation |

Use legitimate library access for commercial books. The open MRST books make a particularly useful executable-learning route, but check separate terms for the text, example code, and datasets. Read enough to derive and challenge a method; the bibliography is not a reading-completion badge. [R04, R05]

## 4. Dataset selection and acquisition

### Preferred sources

**Locally generated synthetic cases are the first source.** They provide known parameters, clean licensing, and controlled perturbations. Keep the generator, truth parameters, seed, and noise model. They establish numerical behavior, not field realism. Use a distinct forward formulation or independently obtained reference before treating an inverse fit as independent corroboration.

**SPE1 is a simulator installation and reporting check.** It is an oil-filled black-oil gas-injection benchmark, not a mature dry-gas asset. Keep the case small and unmodified for the first run. [R10]

**SPE3 is the preferred first gas-focused simulation case.** The widely accessible modified wet-gas black-oil case differs from the original compositional gas-condensate comparison. Identify the actual deck, phase formulation, PVT treatment, units, schedule, and reference result before calling anything a reproduction. The OPM SPE3 deck is a concrete candidate, but it is not bundled or run in the starter. [R10, R13]

**Volve is a later real-data quality and surveillance exercise.** Use the official Equinor source and current license/access instructions, not a random re-upload. It is oil-field data; explain which quality-control lessons transfer to gas work and which fluid/drive assumptions do not. Acquire a minimal useful subset rather than copying a huge archive. [R14]

**Norne is an optional field-scale simulation extension.** Its larger black-oil model is useful after reproducibility and numerical diagnostics are established. SPE10 is useful for a focused heterogeneity/upscaling question, not as the first whole-model project. These cases should not be presented as Indonesian mature-gas analogues merely because they are public. [R10]

### Acquisition gate

Before a dataset enters a case, record its owner, original URL, release or revision, retrieval date, precise files, checksums, license and notices, known exclusions, unit system, datum, and intended use. A source registry must distinguish access permission from redistribution permission. Data without adequate provenance remain quarantined and cannot support a published result.

For OPM datasets, review the current pinned tree and each selected file. The repository describes Open Database License/Database Contents License terms unless otherwise stated and explicitly warns about removed proprietary decks in history. Do not mirror an entire historical repository into a public portfolio. Original repository code licensing does not relicense third-party data. [R12]

Leave raw field data out of Git by default. Publish retrieval instructions and checksums where lawful; distribute only files whose terms have actually been reviewed. Do not store employer material, personal identifiers, signed temporary download URLs, tokens, or license-server details. Cite source plots rather than copying figures without permission. The supplied public-repository checker deliberately blocks raw data, but manual rights review remains necessary.

## 5. Stage A: Gas properties and volumetric material balance

### Engineering protocol

Start with an isothermal volumetric gas reservoir and ask how estimated initial gas in place changes when pressure observations, Z factors, or standard conditions are inconsistent. Define what qualifies as a representative average reservoir pressure. A flowing bottom-hole pressure is not interchangeable with average reservoir pressure for a tank material balance. [R01, R02]

Derive the equations from a common gas inventory and consistent standard-volume basis:

\[
B_g = \frac{Z}{Z_{sc}}\frac{T}{T_{sc}}\frac{p_{sc}}{p},\qquad
\frac{p}{Z} = \frac{p_i}{Z_i}\left(1-\frac{G_p}{G}\right).
\]

Both pressures are absolute, both temperatures are absolute, and the declared standard conditions travel with every reported gas volume. The simplified p/Z relationship assumes fixed-composition single-phase gas, constant gas pore volume, no injection or external support, and negligible rock/water expansion. Condensate dropout, aquifer influx, changing pore volume, and unrepresentative pressures require different treatment. [R01, R02]

Implement the simplest verified version first. The delivered functions accept explicit inputs and reject invalid numbers, lengths, chronology, and physically invalid regression outcomes. They do not silently sort measurements, delete inconvenient points, or invent a gas-property correlation.

### Experiments

Begin with a noise-free linear p/Z oracle whose answer is calculated independently. Add a documented pressure-noise model, systematic pressure bias, errors in Z, incomplete depletion history, and a wrong standard-volume basis as separate experiments. Examine both the point estimate and how extrapolation becomes weakly constrained when observed depletion is small. A high regression R-squared cannot establish the physical assumptions.

Next generate aquifer-supported or variable-pore-volume behavior from a separate mass-balance formulation. Fit the simple volumetric model deliberately, document the resulting bias, and explain why the wrong model can still appear convincing. This is more informative than a single perfect fit to data generated by the same equation.

Use weighted regression or an errors-in-variables method only after defining measurement uncertainty. Distinguish random errors from shared calibration bias and temporally correlated errors. Bootstrap blocks or coherent measurement realizations rather than assuming every pressure point is an independent draw. Treat uncertainty ranges as conditional on the specified model and priors.

### PVT extension

Compare selected single-component properties with documented NIST reference queries. Record phase state, temperature, pressure, units, and the property's source model. A pure-methane comparison is a sanity check, not validation of field-gas composition, heavy-end characterization, dew point, or liquid dropout. [R07]

An advanced gas-condensate extension should use a documented EOS/flash implementation and address composition normalization, mixing parameters, phase stability, equilibrium fugacities, and component conservation. Compare relevant CCE/CVD behavior when suitable permitted reference data exist. Solving one cubic equation for Z is not equivalent to a verified compositional simulator. [R06]

### Required interpretation

Explain the strongest supported gas-in-place conclusion, the assumptions that dominate it, the sensitivity to pressure selection, and the next observation most likely to reduce uncertainty. Do not attach reserves terminology or development approval to a simple tank estimate. Complete a spreadsheet cross-check later using the same declared units and an independently written formula; that workbook should verify a calculation, not simply import the Python answer.

## 6. Stage B: Pressure-transient analysis

### Input suitability and scope

Start with controlled synthetic high-frequency pressure and rate histories rather than hunting for a convenient daily-production spreadsheet. PTA depends on adequate temporal resolution, a defensible rate history, pressure/rate synchronization, and suitable gauge data. An aggregate surveillance dataset should not be relabelled as a well test. KAPPA's documented workflow explicitly includes those quality checks and multiple analytical/numerical model classes. [R09]

Develop in steps: an analytical single-phase reference with known parameters; a constant-rate drawdown; a buildup with the correct time transformation and production history; variable-rate superposition; wellbore storage and skin; a bounded set of alternative reservoir/boundary models; and then a gas-property treatment consistent with the governing equations. Do not put all mechanisms into the first inverse problem.

### Gas transform and diagnostics

Use the real-gas pseudopressure definition with a declared integration datum:

\[
m(p)-m(p_{ref}) = 2\int_{p_{ref}}^p \frac{p'}{\mu(p')Z(p')}\,dp'.
\]

The transform addresses pressure-dependent viscosity and gas deviation factor, but it does not by itself provide rate superposition, pseudotime, wellbore storage, multiphase behavior, or a valid forward well-test model. Verify units and the exact domain in which the selected gas interpretation is being used. [R02, R08, R09]

The starter's derivative is an unsmoothed nonuniform three-point derivative with respect to natural log time. It deliberately omits endpoints and preserves negative values. It is not a full windowed Bourdet implementation or a complete PTA interpreter. Establish analytical derivative tests before adding a smoothing window; then report smoothing sensitivity rather than choosing a window that makes the preferred model look better.

### Interpretation experiments

For each response, show pressure history, rate history, pressure difference, diagnostic derivative, selected interpretation windows, fitted response, residuals, and parameter uncertainty. Explain the physical significance of a candidate flow regime and whether the data duration and signal quality support it. Do not infer a unique boundary solely because a late-time derivative bends upward.

Run controlled contrasts: storage versus early-time damage; a boundary versus rate-history error; several storage/skin combinations that match a short interval; and noise levels that obscure a diagnostic regime. Fit alternative plausible models and compare which measurements would discriminate between them. Include one deliberately inconclusive case and state what cannot be estimated reliably.

Separate the inverse implementation from its reference. An identical forward and inverse equation can pass a self-consistency test while sharing the same mistake. Use an independent analytical expression, another documented implementation, a suitably licensed benchmark, or a supervised licensed Saphir comparison with matched assumptions. Record which form of independence was achieved.

### Completion gate

Accept a synthetic parameter-recovery claim only when the generating model is within the estimator's supported class, the relevant regime is observable, and parameters are identifiable. A proposed clean-case target is permeability-thickness within 5% and skin within 0.5 of the known values, with reference conventions matched. These are project targets, not industry standards; an unsuitable or noisy test should be classified as inconclusive rather than forced to meet them. No operational drawdown recommendation follows from the starter's derivative primitive.

## 7. Stage C: Public simulation benchmark

### Reproduce before modifying

Pin the OPM Flow executable/environment and the selected deck revision. OPM's official releases and manual index must be recorded separately because their publication schedules may differ. An observed 2026.04 release is a possible baseline, not an instruction to ignore newer supported releases. Capture the actual executable identity and support matrix used. [R11, R24]

Inventory all RUNSPEC/GRID/EDIT/PROPS/REGIONS/SOLUTION/SUMMARY/SCHEDULE content applicable to the deck. Trace include files, active cells, pore volume, permeability, contacts, initial pressure/saturation, PVT and rock functions, completion placement, well controls, reporting schedule, and declared units. Investigate every parser warning and unsupported keyword. A warning is not resolved merely because a run finished.

Run SPE1 unchanged as an environment check. Then run a precisely identified SPE3 case unchanged. State whether reference curves come from a documented upstream run, a digitized published figure with extraction uncertainty, another simulator, or an earlier local run. The last option is regression checking, not independent validation. [R10, R13]

### Required checks

Reconcile initial fluids in place independently where the formulation permits. Check hydrostatic/equilibrium initialization and a no-flow case. Verify well signs, BHP/rate constraints, schedule dates, and control-switching events. Distinguish numerical oscillation from an actual scheduled change.

For conservation, balance each conserved component using a common mass or mole basis and all wells/boundaries. Do not add reservoir phase volumes and call their sum conserved when compressibility, dissolution, or vaporization is active. An example normalized residual is:

\[
\epsilon_c=\frac{M_{c,0}+M_{c,inj}+M_{c,in}-M_{c,remaining}-M_{c,prod}-M_{c,out}}
{M_{c,0}+M_{c,inj}+M_{c,in}}.
\]

The starter provides this calculation, not a simulator output parser. Account for units, reporting-time integration, phase/component definitions, and omitted fluxes before interpreting a residual. Source/sink terms from reactions would require an extended balance.

Compare timestep refinement and, for a suitable controlled case, spatial refinement. Refining a heterogeneous geological model is not simply duplicating cells; distinguish discretization convergence from changed geology or upscaling. Compare cumulative quantities, pressure metrics, and event timing using appropriate scales, not unstable percentage errors near zero.

### Controlled sensitivities and decisions

Only after reproduction, perturb one assumption at a time: permeability distribution, vertical communication, relative permeability, fluid-property representation, or well constraints. Then use a small designed ensemble with documented parameter ranges and dependencies. Explain why a parameter matters, whether another parameter could compensate for it, and how the uncertainty affects a decision.

The case report must distinguish benchmark reproduction, deliberate variant changes, unsupported physics, and the consequences of numerical settings. A successful OPM execution can support an honest claim of OPM Flow/Eclipse-format workflow experience, not a claim that Petrel or ECLIPSE was used. [R11, R21, R22]

## 8. Stage D: Mature-gas decision capstone

Construct an explicitly synthetic, modest-size gas reservoir after the benchmark workflow passes. Give the field a generic identifier and state that its geometry, fluid, operating history, and constraints are illustrative. Never imply access to an employer's field or recreate confidential data from memory.

Define a decision before designing the model: for example, continue the base operating policy, reduce a downstream pressure constraint through a simplified compression scenario, add a well, or collect additional pressure information. Start with a dry-gas case. Add aquifer or condensate mechanisms in separately identified variants rather than attributing every effect to one complex model.

Build a consistent chain from material balance and PVT to well inflow and a stated representation of outflow/facility constraints. A reservoir simulator BHP limit is not automatically a surface compression model. Either add a verified well/network relationship or label the BHP change as a proxy and disclose what it omits. Do not describe compression as creating new gas in place.

Create an observation history with its own noise and sampling model, freeze a calibration interval, and reserve a later chronological holdout. Preserve the true parameters separately for a later audit. Match pressure and production jointly using documented uncertainty weights and physically reasonable priors; do not tune all parameters against the holdout. Account for operational constraints, because a constrained rate can carry less direct information about reservoir deliverability than an unconstrained test.

Carry alternative support, transmissibility, skin, and fluid scenarios through forecasts using the same schedule and comparison basis. Report forecast distributions only with declared probability conventions. Prefer explicit q0.10/q0.50/q0.90 quantiles until any petroleum exceedance naming convention has been defined. Distinguish uncertainty about model structure from parameter uncertainty within one model.

Compare options by cumulative gas over a declared horizon, plateau duration, pressure constraints, water/condensate handling where represented, and sensitivity to uncertain inputs. Economics can be a separate optional sensitivity with declared price/cost assumptions, but it should not be dressed up as an investment-grade valuation or reserve certification. Explain what observation could change the preferred option: a pressure survey, a test interval, better fluid characterization, or a constraint measurement.

The final memo should make a conditional recommendation with an explicit reversal condition. For example: favor additional surveillance before a development change when several equally credible models imply different option rankings. That is an engineering result, not a failed project.

## 9. Extensions: Real-field surveillance and geomechanics

### Real-field surveillance

After reviewing current terms, use a small official Volve subset for a data-reconciliation study. Compare source and derived cumulative volumes; distinguish missing data from shut-ins; reconcile operating-day and calendar-day rate definitions; align gauges, production records, and events; and preserve every cleaning decision. Only perform a reservoir analysis if the dataset actually contains appropriate pressures, properties, and histories. Otherwise publish a precise account of why the available observations cannot support the desired inference. [R14]

A later Norne study can exercise a field-scale deck and history-matching workflow. It should have its own protocol and data license record rather than being folded into the synthetic gas case. Show transferable reasoning without claiming equivalence in fluid system, geological setting, or operating history. [R10]

### Sanding

Treat sanding as a bounded screening question. Separate onset/failure from the amount of sand produced and transported. Review rock strength, in-situ stress, completion geometry, pressure depletion, drawdown, and available calibration. Use the Bunyu publication to identify the field-specific evidence required, not to transplant its parameters or operating limits. [R15]

An acceptable initial output is a synthetic sensitivity map and a requirements memo. It must say which parameters are assumed, which failure criterion was chosen, where the criterion is applicable, and which observations would be required before use. Never label an uncalibrated map a safe operating envelope.

### Compaction and subsidence

Keep reservoir strain/compaction separate from surface displacement. A useful learning exercise first examines a declared constitutive assumption and pressure-change scenario, then documents the additional geometry, overburden response, boundary conditions, and observations needed to predict surface motion. Study parameter non-uniqueness using original compaction-inversion research. [R16]

Do not combine guessed compaction coefficients, arbitrary pressure depletion, and a simple surface influence formula into a field prediction. A screening study can be valuable precisely because it identifies missing constraints. Operational geomechanics requires suitable data, calibration, and competent review beyond this portfolio.

## 10. Repository and environment design

Use a small numerical core with narrow, tested functions. Notebooks should orchestrate analyses and explain results; they should not be the only location of reusable equations, hard-coded constants, or data-cleaning logic.

```text
reservoir-engineering-workbench/
  README.md                      # purpose, evidence, current status, entry points
  PLAN.md                        # this research and delivery plan
  AGENTS.md                      # accountable working agreement
  src/reservoir_lab/              # reusable calculation primitives
  tests/                         # analytical, invalid-input, workflow, repository tests
  scripts/                       # one-command checks and a labelled synthetic demo
  configs/                       # explicit case assumptions and units
  data/                          # acquisition policy; raw files excluded by default
  docs/                          # references, contracts, protocols, reviews and backlog
  examples/synthetic_demo/        # one actually executed, labelled example
  .github/workflows/ci.yml        # proposed CI, to verify on the destination repository
```

As case studies are actually implemented, add `cases/<case_id>/protocol.md`, input manifests, analysis entry points, a decision memo, and links to immutable run artifacts. Do not fill the repository with empty files that imply completion. Keep only small permitted fixtures in version control; use an appropriate versioned artifact store for large outputs when needed.

The supplied numerical starter needs Python 3.11 or later and no third-party runtime packages. Direct commands work without a package install. Local testing has been performed with Python 3.13.5; the configured 3.11–3.13 CI matrix is a proposed check, not a claim of already completed remote execution.

For later numerical work, add NumPy/SciPy for arrays, quadrature and optimization; pandas for tables; matplotlib for figures; and a units package such as Pint only where its benefit is clear. Add pytest/coverage, a formatter/linter, type checking, and pre-commit as development needs arise. Pin actual resolved dependencies, commit the generated lockfile, and use locked synchronization. No lockfile is supplied for packages that have not been resolved or installed. [R19, R20]

OPM Flow is the principal open simulator; MRST is optional for educational derivations or an independent reference, subject to module and MATLAB/Octave compatibility. Avoid installing two complete simulator stacks before the first benchmark works. Commercial packages are an optional, legitimately licensed comparison track, never redistributed as repository dependencies. [R04, R11, R23]

## 11. Full working lifecycle

### Plan and pre-register

Write a short issue with the engineering question, source basis, allowed files, deliverables, assumptions, dataset revision, comparison metric, and stopping criterion. Record what would disprove the expected interpretation. Identify an independent oracle and fix acceptance thresholds before running the experiment. Use the case protocol template rather than an unstructured instruction to build everything.

### Acquire and inspect

Review license and provenance; retain raw inputs unchanged; inventory units, datums, missingness, time basis and pressure type; create a cleaning log; and reject inputs that do not support the proposed analysis. Unknown standard conditions or an unlabelled pressure datum are blocking issues, not small cosmetic gaps.

### Implement minimally

Derive or transcribe the equations with checked units, create the smallest working pure function, validate edge cases, and add tests. Avoid adding physics, data extraction, plotting, and optimization in the same opaque change. Make nondeterminism explicit through seeds and record which third-party algorithms may remain nondeterministic.

### Verify and review

A numerical review checks equations, units, algorithm behavior, and independent tests. An engineering review challenges model applicability, parameter identifiability, operational confounders, and conclusions. A rights/release review checks public inputs and outputs. One contributor performing these reviews in different passes should not describe that as independent human peer review.

### Run and preserve

A run is immutable: a new configuration or source revision creates a new output directory. Save executable version, source commit and dirty state, input/config hashes, environment details, seed, solver settings, exit status, logs and output hashes. For simulation, add well controls, supported keywords, time-step/nonlinear/linear tolerances, restart behavior, parallel settings and hardware context. Failed runs remain in an experiment register with the reason for failure rather than being silently excluded.

### Analyse and decide

Inspect physical plausibility before a statistical fit metric. Compare mechanisms, residual structure, parameter bounds, historical/holdout performance and numerical sensitivity. Separate observations from interpretations and conditional recommendations. State what additional data are needed and how they could change the conclusion.

### Release and learn

Reproduce the documented result from a clean checkout and the recorded permitted inputs. Run tests and a public-content scan. Review all changed oracles and tolerances separately from the implementation. Summarize completed versus incomplete scope, actual reviewer involvement, and remaining limitations. Tag a release only after those checks; record follow-up issues instead of retrospectively polishing away uncertainty.

## 12. Verification and acceptance strategy

The following are proposed project gates, not regulatory requirements or universal engineering tolerances. Scale and justify them for each case before observing the final outcome. A benchmark can reveal that a proposed tolerance is unsuitable; any revision then needs an explicit rationale and rerun, not a quiet relaxation.

| Layer | Example check | Proposed gate or interpretation |
|---|---|---|
| Data | Units, datum, absolute pressure, standard conditions, chronology, missingness | No unresolved blocking ambiguity for inputs used by a calculation |
| Analytical primitives | Literal independently calculated values and limiting cases | Scale-aware relative error near 1e-10 where floating-point and analytic conditions justify it |
| Numerical quadrature | Constant-property closed form and variable-property grid refinement | Correct exact/simple limit; demonstrated convergence, not a single arbitrary grid |
| Synthetic p/Z | Recover independent known gas inventory; perturb assumptions separately | In the delivered small-noise demonstration, GIIP error below 1% and conditional holdout RMSE below 1% of initial pressure |
| PTA | Recovery in an identifiable, supported, clean synthetic problem | Candidate targets: kh within 5%, skin within 0.5; inconclusive classification when identification fails |
| Conservation | Per-component mass/mole residual including all fluxes | Investigate residual above 0.1% as an initial screening threshold; do not apply if the required inventory terms are unavailable |
| Simulation refinement | Compare cumulative gas, pressure scales, and relevant events | Candidate cumulative-gas change below 1% plus an explicitly chosen pressure/event tolerance; explain any larger sensitivity |
| Holdout | Chronological, predeclared observations and weights | No training/parameter tuning on the holdout; report both error and assumption dependence |
| Interpretation | Alternative mechanisms and reversal conditions | Every material claim tied to evidence; unsupported causal claims removed |
| Release | Clean rerun, provenance, no secrets/raw restricted data | All mandatory checks pass; no unexecuted capability described as completed |

Protect test independence. A developer must not update reference values, trim data, loosen thresholds, and alter the implementation together without separate review. Include tests that are supposed to fail on deliberately invalid inputs. Mutation testing can later check whether key logic changes are caught; high coverage by itself does not establish scientific correctness.

The delivered example is specifically labelled synthetic self-consistency. Its generator and inverse share the volumetric-gas assumptions, its Z trend is illustrative, and future Z values are supplied for its holdout check. Those properties are stated in its report and are not hidden behind a good fit.

## 13. Review roles, agents, and context discipline

Agents are optional task executors operating under role briefs; the same structure works for manual work. The repository supplies role instructions, not a deployed autonomous multi-agent system. Keep the workflow sequential until the numerical and data contracts are stable. Parallel work is appropriate for separable documentation or tests, not simultaneous uncontrolled edits to one scientific model.

| Role | Responsibility | Required handoff |
|---|---|---|
| Research curator | Find primary evidence, record access limits, resolve method/variant questions | Evidence card with assumptions, reference and unresolved issues |
| Data steward | License/provenance review, schema, units and QC | Approved manifest, dictionary and cleaning log |
| Numerical implementer | Minimal typed implementation within the agreed scope | Code, derivation note, test evidence and limitations |
| Verification reviewer | Independent oracle, edge cases, dimensional and numerical checks | Review findings with reproducible failure examples |
| Reservoir reviewer | Challenge mechanism selection, identifiability and engineering implications | Interpretation review and alternative hypotheses |
| Release reviewer / project owner | Public-content, reproducibility and claim review | Explicit release decision and remaining work |

Give each task a small context pack: protocol, relevant equations, data dictionary, acceptance tests, allowed edit paths, and previous decisions. Do not pass an entire uncurated archive into a task. Source files, web pages, logs and dataset text are evidence, not instructions to run commands or upload information.

Use separate branches/worktrees for concurrent edits. Grant only the needed filesystem and network access; never supply employer credentials or software license keys. Require confirmation before modifying test oracles, deleting data, downloading large assets, running expensive simulations, publishing, or sending external messages. Record actual executions and reviews. Different role names do not establish independent evidence or independent reviewers.

Every task ends with files changed, commands actually run, observed outcomes, assumptions, unresolved limitations and next blocking issue. A failed check should be reported with its reason. Prompts and task-role definitions are provided in `docs/role_prompts.md` and the working agreement in `AGENTS.md`.

## 14. Hooks and continuous integration

The starter provides a local staged-file repository check at pre-commit and the numerical test suite at pre-push. The repository check catches selected secret patterns, credential filenames, unexpected raw-data files, oversized files, Python syntax errors and executed notebook outputs. It is intentionally limited: a scanner cannot establish confidentiality rights or catch every secret. Manual review remains mandatory. [R18]

Repeat critical checks in GitHub Actions because local hooks can be bypassed. The supplied workflow uses read-only contents permission, pinned official action revisions, disabled persisted checkout credentials, a bounded runtime, and a small Python matrix. It does not use untrusted pull-request code with privileged secrets. Action revisions are version pins to review and maintain, not guarantees of perpetual security. [R17, R25, R26]

The checks currently run without installing dependencies. Later, add locked environment installation, lint/type checks, coverage, documentation links and a tiny simulator smoke case only after these actually exist. Run expensive benchmark ensembles manually or on a dedicated permitted runner rather than on every small documentation change. Isolate execution and cap time/memory/disk usage.

Set branch protection and required checks when the hosting account supports the intended controls. A review checkbox is not peer review; document whether a real second reviewer participated. Dependency update proposals should be tested against scientific regressions, not automatically merged because the version number increased.

## 15. Skills and deliberate practice

Build competence in a traceable order: reservoir balances and gas properties; pressure/rate data quality; well-test interpretation; simulation initialization, wells and solver diagnostics; uncertainty and model comparison; and concise technical communication. Programming supports that sequence rather than replacing it.

For each skill, maintain one evidence link and a frank level: studied, reproduced, independently implemented, or applied with review. Record actual software access and completed tasks separately. A commercial-software bridge can later repeat a permitted case in Petrel/ECLIPSE or Saphir, comparing units, fluid model, initialization, controls, fit windows and diagnostics. Screenshots alone are weaker than a reproducible explanation of what was done and why. [R09, R21, R22]

Practice a five-minute technical explanation in English and Indonesian after completing each case. Use a small independently written spreadsheet cross-check for the core calculation and a short presentation or decision memo. This makes the results accessible to colleagues who do not work in Python while exposing hidden assumptions in the computation.

Maintain a short learning journal recording one changed assumption, one failed hypothesis, and one decision per meaningful milestone. Do not manufacture a commit history, synthetic employment context, peer reviews, operational impact, or claims of original discovery. An honest, clearly bounded study is more convincing than an inflated field story.

## 16. Delivery order and public presentation

**Release 0.1 — Verified foundation.** Current scope: calculation primitives, unit/workflow/repository tests, synthetic self-consistency demonstration, data policy, role briefs and release process. Verify the workflow in the destination repository before displaying a live passing CI badge.

**Release 0.2 — PVT/material-balance study.** Add an independent property comparison, a deliberately violated-assumption case, justified uncertainty analysis, and a reviewed interpretation memo. Gate: the misleading-fit counterexample is explained, not just the best-fit case.

**Release 0.3 — PTA study.** Add independently checked forward cases, rate-history handling, diagnostic sensitivity and competing model interpretations. Gate: a defensible inconclusive case exists alongside successful parameter recovery.

**Release 0.4 — Simulation reproduction.** Acquire a reviewed pinned benchmark, reproduce it, diagnose warnings, close the appropriate balances and document numerical sensitivity. Gate: deck-variant and reference differences are explicit.

**Release 1.0 — Mature-gas decision study.** Integrate the verified components into a clearly synthetic capstone with frozen history/holdout, scenario uncertainty, operational constraints and a decision memo. Gate: another person can understand the recommendation and its reversal condition without running the simulator.

**Later extensions.** Add real-field surveillance, geomechanics screening, licensed software comparisons, or a focused data-driven model only when each has suitable inputs and its own verification plan. A smaller completed investigation is preferable to several nominally advanced but unreviewed modules.

The public landing page should present purpose, actual current status, two or three strongest completed findings, reproduction commands, and limitations. Each case begins with the engineering question and decision implication, then links deeper methods and tests. Keep reports in clear technical English, with an optional brief Indonesian summary. Preserve required scholarly and data attribution throughout.

Use the immediate task backlog in `docs/backlog.md`. The first meaningful next milestone is not a new interface: it is an independently sourced PVT check and a controlled example showing when a straight p/Z fit is misleading.


---


# References and reading register

The entries below distinguish official documentation, publisher metadata, accessible research summaries, and reading targets. Listing a book does not mean its full text was inspected. Commercial books and paywalled articles should be obtained through a library, institution, or legitimate publisher access. No third-party books, papers, data archives, or software binaries are distributed with this repository. Web documentation was checked for this plan in September 2026; implementations must record the versions and source revisions actually used.

### R01 — Reservoir-engineering foundations
Dake, L. P. (1978). *Fundamentals of Reservoir Engineering*. Elsevier. [Publisher](https://shop.elsevier.com/books/fundamentals-of-reservoir-engineering/dake/978-0-444-41667-4). [Chapter 1 publisher record](https://www.sciencedirect.com/science/chapter/bookseries/pii/S0376736108700074), DOI: 10.1016/S0376-7361(08)70007-4. Access: publisher metadata and chapter summary, not the complete book. Read for material balance, pressure behavior, displacement concepts, and physical assumptions. Use a legally obtained edition to record exact equation and page references during implementation.

### R02 — Gas-reservoir engineering
Lee, J., and Wattenbarger, R. A. (1996). *Gas Reservoir Engineering*. Society of Petroleum Engineers. DOI: 10.2118/9781555630737. [Properties of Natural Gases](https://onepetro.org/books/book/28/chapter/10911171/Properties-of-Natural-Gases); [Pressure-transient Testing of Gas Wells](https://onepetro.org/books/book/28/chapter/10911181/Pressure-transient-Testing-of-Gas-Wells). Access: publisher chapter metadata; full book not accessed. Primary reading for gas properties, gas material balance, deliverability, and gas-well testing.

### R03 — Practical pressure-transient interpretation
Bourdet, D. (2002). *Well Test Analysis: The Use of Advanced Interpretation Models*. Elsevier, Handbook of Petroleum Exploration and Production, volume 3. [Publisher and contents](https://shop.elsevier.com/books/well-test-analysis/bourdet/978-0-444-50968-0). Access: publisher description and table of contents, not complete book. Prioritize derivative methods, storage and skin, boundaries, gas wells, and practical interpretation. Reproduce a small properly sourced example before claiming a published-method reproduction.

### R04 — Open reservoir-simulation textbook
Lie, K.-A. (2019). *An Introduction to Reservoir Simulation Using MATLAB/GNU Octave: User Guide for the MATLAB Reservoir Simulation Toolbox (MRST)*. Cambridge University Press. DOI: 10.1017/9781108591416. [Open-access publisher edition](https://www.cambridge.org/core/books/an-introduction-to-reservoir-simulation-using-matlabgnu-octave/F48C3D8C88A3F67E4D97D4E16970F894). Access: official open-access book landing page and chapter information. Read conservation equations, discretization, grids, wells, and nonlinear solution. Text and code have their own terms; an open-access text is not automatically permissively licensed code.

### R05 — Advanced modelling
Lie, K.-A., and Møyner, O., editors (2021). *Advanced Modeling with the MATLAB Reservoir Simulation Toolbox*. Cambridge University Press. DOI: 10.1017/9781009019781. [Authors' institutional book page](https://www.sintef.no/projectweb/mrst/publications/mrst-book/). Access: official book information; open-access edition linked there. Use selected chapters only after a verified baseline, especially compositional flow, history matching, and geomechanics. Do not imply all modules run under every MATLAB/Octave version.

### R06 — Equation of state
Peng, D.-Y., and Robinson, D. B. (1976). “A New Two-Constant Equation of State.” *Industrial & Engineering Chemistry Fundamentals*, 15(1), 59–64. DOI: 10.1021/i160057a011. [ACS original publication](https://pubs.acs.org/doi/10.1021/i160057a011). Access: publisher metadata/preview, not a reproduced full-text calculation. Use as the foundational EOS reading; a mixture flash also requires a properly sourced treatment of mixing rules, equilibrium, phase stability, and numerical algorithms. The later website upload date is not the original publication year.

### R07 — Independent fluid-property reference
NIST. *Chemistry WebBook, Standard Reference Database 69: Thermophysical Properties of Fluid Systems*. [Fluid-property interface](https://webbook.nist.gov/chemistry/fluid/); [NIST reference description](https://www.nist.gov/publications/thermophysical-properties-fluids). Access: official interface and reference description. Record the species, temperature, pressure grid, property units, source model, and query date. Values from a reference equation of state are not new laboratory measurements. Pure-component agreement does not validate a multicomponent gas-condensate model.

### R08 — Real-gas pseudopressure
Al-Hussainy, R., Ramey, H. J., Jr., and Crawford, P. B. “The Flow of Real Gases Through Porous Media.” Original JPT paper (1966), DOI: 10.2118/1243-A-PA. [Primary AIME archival record](https://onemine.org/documents/natural-gas-technology-the-flow-of-real-gases-through-porous-media), dated 1967 for that archival version. [Author's dissertation record](https://oaktrust.library.tamu.edu/handle/1969.1/DISSERTATIONS-213028). Access: primary archival abstract and institutional record; full original paper not accessed. Record the actual edition when using an equation. Do not confuse the archive date with the original article date.

### R09 — Saphir workflow and scope
KAPPA Engineering. *Saphir overview*. [Official documentation](https://www.kappaeng.com/software/saphir/overview). Access: official workflow page, including gauge quality checks, pressure/rate synchronization, derivative diagnostics, well/reservoir/boundary models, and gas nonlinearity. This is a product-workflow reference, not an independent validation study or a license to redistribute software.

### R10 — Benchmark selection and variants
SINTEF. *MRST: Public data sets*. [Official dataset catalogue](https://www.sintef.no/projectweb/mrst/modules/mrst-core/data-sets/). Access: full catalogue descriptions. Important distinctions: SPE1 is an oil-filled black-oil gas-injection case; the catalogue's SPE3 is a modified wet-gas black-oil variant of an originally compositional condensate benchmark; SPE10 is an upscaling benchmark; Norne is a field-scale black-oil case. Availability through a catalogue does not remove a dataset's separate license.

### R11 — Open simulator
Open Porous Media project. *opm-simulators*. [Official repository](https://github.com/OPM/opm-simulators). Access: project repository documentation. OPM Flow is open-source reservoir-simulation software with Eclipse-format input support. It is not the SLB ECLIPSE executable. Check keyword support, fluid formulation, and numerical settings for the pinned release.

### R12 — Benchmark data and redistribution terms
Open Porous Media project. *opm-data*. [Official repository and terms](https://github.com/OPM/opm-data). Access: current repository README. Unless otherwise specified, decks use the Open Database License and their data contents use the Database Contents License. The README warns that repository history contains removed proprietary decks. Use an explicitly reviewed current file tree pinned to a commit, not an indiscriminate mirror of repository history. Preserve per-file terms and notices.

### R13 — Concrete SPE3 input candidate
Open Porous Media project. *spe3/SPE3CASE2.DATA*. [Official deck](https://github.com/OPM/opm-data/blob/master/spe3/SPE3CASE2.DATA). Access: deck header and visible model content. This file is a candidate, not a bundled or executed study in the starter. Its phase keywords and FIELD unit declaration must be checked with all include files before use. Pin a real commit and file checksums when acquiring it; the moving branch URL is for discovery only.

### R14 — Field-data source
Equinor. *Volve field data set*. [Official access and usage page](https://www.equinor.com/energy/volve-data-sharing). Access: current official landing page. This is real oil-field data, released for research/study/development under the Equinor Open Data Licence, with current access instructions linked on the page. The complete current license text was not independently examined for this starter. Review it before publishing source data, derived datasets, or visual extracts. No Volve files are bundled here.

### R15 — Sanding case study
Harun, Syafaat, Almunawwar, and Doza. “Geomechanical Analysis and Sand Production Prediction in Development Well, Case Study in Bunyu Field.” *IATMI proceedings*, 2018; online record published in 2023. [IATMI original record](https://journal.iatmi.or.id/index.php/ojs/article/view/61). Access: original publication record/abstract, not a complete reproduced field calculation. Use to study the evidence needed for a site-specific sanding assessment, not to transplant a field's critical drawdown to a different reservoir.

### R16 — Compaction and subsidence identifiability
Muntendam-Bos, A. G., and Fokker, P. A. (2009). “Unraveling reservoir compaction parameters through the inversion of surface subsidence observations.” *Computational Geosciences*, 13, 43–55. Published online in 2008. DOI: 10.1007/s10596-008-9104-z. [Original journal publication](https://link.springer.com/article/10.1007/s10596-008-9104-z). Access: original abstract and publication information. Supports studying coupled parameter estimation and the limitations of inferring compaction behavior from surface observations; the starter does not implement or reproduce this paper.

### R17 — Workflow security
GitHub. *Secure use reference for GitHub Actions*. [Official documentation](https://docs.github.com/en/actions/reference/security/secure-use). Access: official documentation. Use restricted token permissions, review untrusted inputs, and pin third-party actions to full commit hashes. Pins must still be reviewed and maintained; a fixed revision does not make an action permanently secure.

### R18 — Local hooks
pre-commit project. *Documentation*. [Official documentation](https://pre-commit.com/). Access: official documentation. The delivered configuration uses local hooks at pre-commit and pre-push stages. Hooks are developer aids and can be bypassed; repeat critical checks in continuous integration.

### R19 — Dependency locking
Astral. *uv projects: Locking and syncing*. [Official documentation](https://docs.astral.sh/uv/concepts/projects/sync/). Access: official documentation. `--locked` checks that the lockfile is consistent rather than updating it. The supplied numerical starter has no runtime dependencies and does not include a fabricated lockfile. Generate and review a real lockfile when adding third-party packages.

### R20 — Test layout
pytest project. *Good Integration Practices*. [Official documentation](https://docs.pytest.org/en/stable/explanation/goodpractices.html). Access: official documentation. Useful when expanding testing beyond the dependency-free standard-library runner supplied here. Test an installed package as well as direct source imports before a package-distribution release.

### R21 — Commercial modelling workflow
SLB. *Petrel Reservoir Engineering Core*. [Official product-workflow description](https://www.slb.com/products-and-services/delivering-digital-at-scale/software/petrel-subsurface-software/petrel/petrel-core-systems/petrel-reservoir-engineering-core). Access: official description. Use to map future licensed practice to grid/fluid/rock setup, initialization, completions, history, and scenarios. An open-source portfolio alone does not establish hands-on Petrel experience.

### R22 — Commercial simulator boundary
SLB. *ECLIPSE reservoir simulation*. [Official product page](https://www.slb.com/products-and-services/delivering-digital-at-scale/software/eclipse-industry-reference-reservoir-simulator/eclipse). Access: official product information. Distinguish the simulator from an input format used by other tools. Any cross-simulator comparison requires a legitimate installation and equivalent supported physics/settings.

### R23 — MRST release source
SINTEF. *MRST download*. [Official release page](https://www.sintef.no/projectweb/mrst/download/); [official source repository](https://github.com/SINTEF-AppliedCompSci/MRST). Access: official release information; 2026a is an observed available release, not a claim that no newer release can exist. Prefer a versioned stable release and verify individual module/environment compatibility. MATLAB itself is separately licensed.

### R24 — OPM release and manual
Open Porous Media project. [Official simulator releases](https://github.com/OPM/opm-simulators/releases); [manual index](https://opm-project.org/?page_id=955). Access: official release and documentation listings. A 2026.04 final release is visible in the release record. Manuals can lag software versions; preserve the specific manual revision and release notes alongside the executable version rather than assuming matching dates imply identical behavior.

### R25 — Checkout action revision used by starter CI
GitHub Actions. *actions/checkout*, v4.2.2. [Release](https://github.com/actions/checkout/releases/tag/v4.2.2); [commit 11bd71901bbe5b1630ceea73d27597364c9af683](https://github.com/actions/checkout/commit/11bd71901bbe5b1630ceea73d27597364c9af683). Access: official release and commit record. This is a verified revision pin, not a claim to be the newest release. Remote workflow execution remains to be checked on the destination repository.

### R26 — Python setup action revision used by starter CI
GitHub Actions. *actions/setup-python*, v5.6.0. [Release](https://github.com/actions/setup-python/releases/tag/v5.6.0); [commit a26af69be951a213d495a4c3e4e4022e16d87065](https://github.com/actions/setup-python/commit/a26af69be951a213d495a4c3e4e4022e16d87065). Access: official release and commit record. Like any dependency, the pin should be reviewed for updates; it does not establish that the proposed matrix has already passed on GitHub.

## Further original-paper reading targets

These bibliographic targets are useful next readings; their complete original texts were not accessed and no numerical reproduction is claimed:

- Bourdet, D., Ayoub, J. A., and Pirard, Y. M. (1989). “Use of Pressure Derivative in Well Test Interpretation.” *SPE Formation Evaluation*, 4(2), 293–302. DOI: 10.2118/12777-PA. Read alongside R03 and distinguish the published workflow from the starter's unsmoothed derivative primitive.
- Kenyon, D. E., and Behie, G. A. (1987). “Third SPE Comparative Solution Project: Gas Cycling of Retrograde Condensate Reservoirs.” *Journal of Petroleum Technology*. DOI: 10.2118/12278-PA. Referenced by the SPE3 deck; establish which variant and fluid formulation are being reproduced.
- Geertsma, J. (1973). “Land Subsidence Above Compacting Oil and Gas Reservoirs.” *Journal of Petroleum Technology*, 25, 734–744. DOI: 10.2118/3730-PA. A starting point for explicitly bounded elastic screening, not a universal field prediction model.

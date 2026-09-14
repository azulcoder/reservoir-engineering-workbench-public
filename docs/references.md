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

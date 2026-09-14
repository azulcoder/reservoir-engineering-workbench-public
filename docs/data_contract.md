# Data contract

A calculation cannot repair an unknown unit system or an unsuitable observation. The following contract applies before any future field-data ingestion or simulation case is admitted.

## Required manifest

Every source must record a dataset identifier, owner, original source URL, retrieval date, source version or commit, exact relative file paths, SHA-256 checksums, license/permission evidence, redistribution decision, data classification, and intended engineering use. Record the actual source; do not cite an intermediary notebook as the data owner.

For simulation inputs, resolve include files and record a complete dependency inventory. A checksum for a top-level deck is insufficient when included PVT, grid, or schedule files can change independently. Preserve a separate local path for raw data that is excluded from public commits.

## Physical conventions

| Quantity | Internal convention | Required metadata |
|---|---|---|
| Pressure | Pa, absolute | Gauge versus absolute; gauge offset; datum; reservoir/BHP/wellhead; averaging/test method |
| Temperature | K | Measurement/model location and reference |
| Gas volume/rate | Standard m3 and standard m3/s | Standard pressure, temperature and Z; operating versus calendar rate; allocation basis |
| Reservoir volume | Reservoir m3 | Pressure/temperature and phase |
| Time | UTC timestamps plus elapsed seconds | Timezone, interval edges, rate changes, sampling and gauge synchronization |
| Permeability | m2 in numerical core, with explicit conversions | Horizontal/vertical orientation, effective versus absolute, source |
| Viscosity | Pa s | Fluid phase, temperature and pressure |
| Saturation/porosity/composition | Dimensionless | Fraction versus percent; phase/component order; normalization |
| Mass/component inventory | Consistent kg or mol per component | Components, injection/production/boundary signs, phase-to-component conversions |

Conversions happen once at the ingestion boundary, with source values retained. Check FIELD/SI deck declarations rather than assuming them. Values named only `p`, `q`, or `time` need accompanying schema information; an axis label cannot substitute for a data contract.

## Quality rules

Reject duplicate records unless a documented reconciliation rule resolves them. Distinguish missing measurements, zero rate, shut-in and invalid gauges. Never interpolate across a rate change or shut-in without a justified method. Keep raw measurements unchanged and record each exclusion or correction with its reason.

Cumulative production must agree with the declared rate basis and interval integration. An operating-day rate may require uptime; a calendar-average rate already includes downtime. Do not multiply uptime twice. Handle production and injection as separate nonnegative streams before applying a documented sign convention.

Do not substitute flowing BHP for average reservoir pressure. A pressure survey needs its test conditions, datum and representativeness reviewed. An early pressure measured in a poorly equilibrated region is not automatically a field-average observation.

For PTA, require sufficient pressure/rate resolution, synchronization and test context. A daily production spreadsheet alone does not supply high-frequency buildup information. For PVT, record whether values are measured, correlated, EOS-generated, or illustrative.

## Release decision

A source without a clear permission basis may be analysed only under an appropriate private arrangement, not automatically published. Public accessibility does not imply redistribution permission. The default public repository contains only original synthetic fixtures, source records, and permitted derived summaries. The automated scanner cannot approve legal rights; the project owner must review them.

#!/usr/bin/env node
/**
 * Emit the downloadable copies of every exhibit's numbers and drawings into
 * site/public/data/, and verify that what is published is what was rendered.
 *
 *   node src/scripts/emit-public-data.mjs                 (from site/)   write
 *   node src/scripts/emit-public-data.mjs --verify        (from site/)   check only
 *   node src/scripts/emit-public-data.mjs --out <dir>     write elsewhere
 *
 * Rules this script exists to keep.
 *
 *  1. Nothing is retyped. Every value written here is read from a committed JSON file:
 *     the seven exports under site/src/data/figures/ plus the two case summaries the
 *     A1 and A3 figures are drawn from. If a source file is missing the script exits
 *     non-zero and writes nothing.
 *  2. No reference-derived value is emitted. The NIST extract is not in this tree and
 *     nothing downstream of it is published; the two case summaries are filtered to the
 *     specific blocks the figures use, and those blocks are synthetic throughout.
 *  3. Full-dataset and selected-data downloads are separate files with separate names.
 *     "_all" carries every computed case; "_case-<J>" carries one. A reader who takes a
 *     file from the scenario explorer must be able to tell from the file name which of
 *     the two they have.
 *  4. Every emitted file is recorded in index.json with its byte length and SHA-256.
 *     The site build reads that index, re-hashes what is on disk and fails if either
 *     the file or the digest is wrong, so a stale or hand-edited download cannot ship.
 *
 * The chain this script is the middle of, and --verify enforces end to end
 * ---------------------------------------------------------------------------
 *
 *   checked numerical data      site/src/data/figures/*.json, each digest declared in
 *                               contract.json and re-hashed by the renderer
 *          |
 *   figure specification        site/src/generated/figures/manifest.json, written by
 *                               site/scripts/render-figures.mjs with the axes, the
 *                               selector, the accessible name and the file list
 *          |
 *   canonical rendered figure   site/src/generated/figures/<id>.svg and <id>.png
 *          |
 *   published download          site/public/data/figures/<id>.svg and <id>.png
 *          |
 *   displayed figure            the SVG inlined by src/scripts/exhibits.ts into the page
 *
 * Before this, only the last-but-one link was checked, and only against a digest this
 * same script had written: index.json said each published SVG was "byte-identical to
 * the file the page inlines" and nothing compared the two. A figure could be
 * re-rendered while its published copy went stale, and the build stayed green because
 * the stale copy still matched the stale digest. That is what --verify closes.
 *
 * What --verify actually does, in order:
 *
 *   1. re-runs the whole emission into a scratch directory and compares the result with
 *      site/public/data byte for byte, in both directions. Emission is deterministic,
 *      so any published file that is not what this script would write today -- tampered,
 *      stale, bound to the wrong case, or simply absent -- shows up here by name.
 *   2. compares every published figure artefact against the canonical rendered file it
 *      claims to copy, byte for byte. Not normalised, not whitespace-insensitive: the
 *      contract says byte-identical, so the check is byte identity.
 *   3. re-hashes every published file against the digest index.json records for it.
 *   4. checks the figure specification against the drawing: the SVG's accessible name is
 *      the manifest's accessible name, its <desc> is the length the manifest recorded,
 *      and every file the manifest declares is published under the variant it declares.
 *   5. checks two presentation floors on the canonical SVGs, which are the properties a
 *      re-render can silently break: no text below the manifest's own px floor, and no
 *      text anchored outside the drawing's viewBox.
 *
 * Variants and what may be called identical
 * -----------------------------------------
 * Each figure is published in two variants and they are registered separately:
 *
 *   canonical-vector   <id>.svg   the authoritative artefact. Byte-identical to
 *                                 site/src/generated/figures/<id>.svg, and inlined into
 *                                 the page with leading and trailing whitespace trimmed
 *                                 and nothing else changed -- no id rewritten, no
 *                                 attribute added or removed. build_release.py proves
 *                                 the trimmed bytes appear verbatim in the built HTML.
 *   raster-export      <id>.png   the same drawing at 216 dpi, rasterised by the
 *                                 reviewed renderer from that exact SVG. Byte-identical
 *                                 to site/src/generated/figures/<id>.png and NOT to the
 *                                 SVG; the index says so in those words. It is a
 *                                 different encoding of one drawing, never a second
 *                                 layout passed off as the first.
 *
 * There is no compact/wide pair today: F01 and F01b are two figures with different
 * questions and different domains, each with its own manifest entry, not two renderings
 * of one. If the figure stream adds a real size variant, it gets its own registry entry,
 * its own provenance and its own link text; it does not inherit another variant's.
 *
 * Numbers are written at full double precision in the JSON copies and at a stated
 * number of significant figures in the CSVs. The CSV header says which.
 */

import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SITE = join(HERE, "..", "..");
const REPO = join(SITE, "..");
const FIGURE_DATA = join(SITE, "src", "data", "figures");
const GENERATED = join(SITE, "src", "generated", "figures");
const MANIFEST = join(GENERATED, "manifest.json");
const OUT = join(SITE, "public", "data");

/** Repository-relative display path, for messages a reader can act on. */
function show(path) {
  return relative(REPO, path).split(sep).join("/");
}

/**
 * Emission state. Reset at the start of every run so that --verify can emit a second
 * time into a scratch directory within the same process and compare the two.
 */
let emitted = [];
let outDir = OUT;

async function readJson(path) {
  let text;
  try {
    text = await readFile(path, "utf8");
  } catch (error) {
    throw new Error(`cannot read required source ${path}: ${error.message}`);
  }
  if (/\b(NaN|-?Infinity)\b/.test(text)) {
    throw new Error(`${path} carries a non-finite JSON token; re-export with allow_nan=False`);
  }
  return JSON.parse(text);
}

function sha256(text) {
  return createHash("sha256").update(text, "utf8").digest("hex");
}

/** SHA-256 of raw bytes. Used for the rasters, where there is no text to encode. */
function sha256Bytes(buffer) {
  return createHash("sha256").update(buffer).digest("hex");
}

async function emit(name, text, description, kind) {
  const body = text.endsWith("\n") ? text : `${text}\n`;
  await writeFile(join(outDir, name), body, "utf8");
  emitted.push({
    name,
    kind,
    description,
    bytes: Buffer.byteLength(body, "utf8"),
    sha256: sha256(body),
  });
}

/** JSON copy, pretty-printed, full precision. */
async function emitJson(name, value, description, kind) {
  await emit(name, `${JSON.stringify(value, null, 2)}\n`, description, kind);
}

/**
 * CSV. Values are formatted here and nowhere else.
 *
 * `toPrecision(12)` is below double precision and above anything a reader will plot, and
 * it is applied uniformly so that a column cannot be silently rounded harder than its
 * neighbour. An absent value is written as an empty field and the header says so; a
 * blank is not a zero and the accompanying JSON keeps the null.
 */
function csv(columns, rows) {
  const head = columns.map((c) => c.header).join(",");
  const body = rows.map((row) =>
    columns
      .map((c) => {
        const v = c.value(row);
        if (v === null || v === undefined) return "";
        if (typeof v === "number") {
          if (!Number.isFinite(v)) throw new Error(`non-finite value in column ${c.header}`);
          if (Number.isInteger(v) && Math.abs(v) < 1e15) return String(v);
          return Number(v.toPrecision(12)).toString();
        }
        const s = String(v);
        return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
      })
      .join(","),
  );
  return [head, ...body].join("\n");
}

const num = (key) => ({ header: key, value: (r) => r[key] });

/* ------------------------------------------------------------------ *
 * F01 / F01b / F02 — the eight computed scenarios
 * ------------------------------------------------------------------ */

/** A J value as it appears in a file name: 0, 0.05, 0.2, 0.6, 2, 6, 20, 60. */
export function caseSlug(j) {
  return String(j).replace(/\.0+$/, "").replace(/\./g, "p");
}

const SCENARIO_COLUMNS = [
  { header: "productivity_index_bbl_per_day_psi", value: (r) => r.j },
  { header: "observation_index", value: (r) => r.i },
  num("times_days"),
  num("times_years"),
  num("cumulative_gas_scf"),
  num("cumulative_gas_bscf"),
  num("pressure_psia"),
  num("z_factor"),
  num("p_over_z_psia"),
  num("fitted_p_over_z_psia"),
  num("residual_p_over_z_psia"),
];

function scenarioRows(scenario) {
  const j = scenario.productivity_index_bbl_per_day_psi;
  return scenario.times_days.map((_, i) => ({
    j,
    i,
    times_days: scenario.times_days[i],
    times_years: scenario.times_years[i],
    cumulative_gas_scf: scenario.cumulative_gas_scf[i],
    cumulative_gas_bscf: scenario.cumulative_gas_bscf[i],
    pressure_psia: scenario.pressure_psia[i],
    z_factor: scenario.z_factor[i],
    p_over_z_psia: scenario.p_over_z_psia[i],
    fitted_p_over_z_psia: scenario.fitted_p_over_z_psia[i],
    residual_p_over_z_psia: scenario.residual_p_over_z_psia[i],
  }));
}

/**
 * The per-scenario headline block. `true_gas_in_place_scf` is derived, not typed: the
 * export carries the fitted value and the relative error, and the truth follows from
 * them. The derivation is carried in the file so the reader can check it.
 */
function scenarioSummary(scenario) {
  const fit = scenario.fit;
  const trueG = fit.gas_in_place_scf / (1 + scenario.relative_gas_in_place_error);
  const residuals = scenario.residual_p_over_z_psia;
  const rms = Math.sqrt(residuals.reduce((a, r) => a + r * r, 0) / residuals.length);
  return {
    productivity_index_bbl_per_day_psi: scenario.productivity_index_bbl_per_day_psi,
    label: scenario.label,
    is_base_case: scenario.is_base_case,
    is_volumetric_control: scenario.is_volumetric_control,
    n_observations: scenario.n_observations,
    r_squared: fit.r_squared,
    fitted_gas_in_place_scf: fit.gas_in_place_scf,
    fitted_gas_in_place_bscf: fit.gas_in_place_bscf,
    fitted_gas_in_place_stderr_scf: fit.gas_in_place_stderr_scf,
    intercept_psia: fit.intercept_psia,
    slope_psia_per_scf: fit.slope_psia_per_scf,
    depletion_fraction_observed: fit.depletion_fraction_observed,
    true_gas_in_place_scf: trueG,
    true_gas_in_place_derivation:
      "fit.gas_in_place_scf / (1 + relative_gas_in_place_error); the truth is not a field of the export",
    relative_gas_in_place_error: scenario.relative_gas_in_place_error,
    relative_remaining_gas_error: scenario.relative_remaining_gas_error,
    bias_over_stderr: scenario.bias_over_stderr,
    observed_extent_bscf: scenario.observed_extent_bscf,
    invaded_pore_volume_fraction: scenario.invaded_pore_volume_fraction,
    terminal_pressure_psia: scenario.terminal_pressure_psia,
    max_solver_residual_p_over_z_psia: scenario.max_solver_residual_p_over_z_psia,
    residual_min_psia: Math.min(...residuals),
    residual_max_psia: Math.max(...residuals),
    residual_rms_psia: rms,
  };
}

/* ------------------------------------------------------------------ *
 * The figure-artefact registry
 * ------------------------------------------------------------------ */

/**
 * Variants, keyed by the media type the manifest declares. A media type this table does
 * not know is an error rather than a default: an unregistered variant would be published
 * with no provenance and no statement of what it is identical to.
 */
const VARIANTS = {
  "image/svg+xml": {
    variant: "canonical-vector",
    kind: "exhibit",
    authoritative: true,
    /** The renderer writes `svgText + "\n"` but records `Buffer.byteLength(svgText)`. */
    trailingNewline: true,
    describe: (id, source) =>
      `${id}, canonical vector. Byte-identical to ${source}, which is the file the page ` +
      `inlines; the page trims leading and trailing whitespace and changes nothing else.`,
  },
  "image/png": {
    variant: "raster-export",
    kind: "exhibit-raster",
    authoritative: false,
    trailingNewline: false,
    describe: (id, source, detail) =>
      `${id}, raster export${detail ? ` (${detail})` : ""}. Byte-identical to ${source}. ` +
      `It is the same drawing as the SVG rasterised by the reviewed renderer, not the ` +
      `same bytes and not a separate layout; the SVG is the authoritative artefact.`,
  },
};

/**
 * Read the figure specification and resolve every artefact it declares.
 *
 * Publication is driven by the manifest, not by whatever happens to be sitting in the
 * generated directory. A figure the manifest no longer declares stops being published,
 * and a file the manifest declares but the renderer did not write stops the run.
 */
async function figureRegistry() {
  const manifest = await readJson(MANIFEST);
  if (!Array.isArray(manifest.figures) || manifest.figures.length === 0) {
    throw new Error(`${show(MANIFEST)} declares no figures; run: npm run figures`);
  }
  const rendererDigest = manifest.generated?.renderer_sha256;
  if (typeof rendererDigest !== "string" || rendererDigest.length !== 64) {
    throw new Error(`${show(MANIFEST)} has no generated.renderer_sha256; it identifies the build that drew these figures`);
  }

  const artefacts = [];
  const claimed = new Set();
  for (const figure of manifest.figures) {
    const id = figure.figure_id;
    if (typeof id !== "string" || id.trim() === "") {
      throw new Error(`${show(MANIFEST)} has a figure with no figure_id`);
    }
    const files = Array.isArray(figure.files) ? figure.files : [];
    if (files.length === 0) throw new Error(`${show(MANIFEST)}: figure ${id} declares no files`);

    const svgFile = files.find((f) => f.media_type === "image/svg+xml");
    if (!svgFile) throw new Error(`${show(MANIFEST)}: figure ${id} declares no image/svg+xml file; every exhibit ships its vector`);

    for (const file of files) {
      const spec = VARIANTS[file.media_type];
      if (!spec) {
        throw new Error(
          `${show(MANIFEST)}: figure ${id} declares ${file.path} as ${file.media_type}, ` +
            `which is not a registered variant. Register it with its provenance and what ` +
            `it is identical to, or do not publish it.`,
        );
      }
      const sourcePath = join(GENERATED, file.path);
      let bytes;
      try {
        bytes = await readFile(sourcePath);
      } catch (error) {
        throw new Error(
          `figure ${id}: ${show(MANIFEST)} declares ${file.path} but the canonical file is ` +
            `absent.\n  expected at: ${show(sourcePath)}\n  ${error.message}\n  run: npm run figures`,
        );
      }
      /* The manifest's byte count is the drawing's own length; the SVG on disk carries
         one further newline. Anything else means the file and the specification that
         describes it were written at different times. */
      const expected = spec.trailingNewline ? [file.bytes, file.bytes + 1] : [file.bytes];
      if (typeof file.bytes === "number" && !expected.includes(bytes.length)) {
        throw new Error(
          `figure ${id}: ${show(sourcePath)} is ${bytes.length} B but ${show(MANIFEST)} ` +
            `records ${file.bytes} B. The drawing and its specification disagree; run: npm run figures`,
        );
      }
      if (claimed.has(file.path)) {
        throw new Error(`${show(MANIFEST)}: ${file.path} is declared by more than one figure`);
      }
      claimed.add(file.path);

      artefacts.push({
        figureId: id,
        name: `figures/${file.path}`,
        file: file.path,
        mediaType: file.media_type,
        variant: spec.variant,
        kind: spec.kind,
        authoritative: spec.authoritative,
        detail: file.raster,
        bytes,
        sourcePath,
        sourceDisplay: show(sourcePath),
        sourceSha256: sha256Bytes(bytes),
        dataFiles: Array.isArray(figure.data_files) ? figure.data_files : [],
        numericalRunId: figure.numerical_run_id ?? null,
        rendererSha256: rendererDigest,
        accessibleName: figure.accessibility?.accessible_name ?? null,
        longDescriptionChars: figure.accessibility?.long_description_chars ?? null,
        minimumLabelPx: figure.accessibility?.minimum_label_px ?? null,
        siblingVector: `figures/${svgFile.path}`,
      });
    }
  }

  /* A file sitting in the generated directory that the manifest does not declare is not
     published, and the run says so rather than quietly copying it. */
  const present = (await readdir(GENERATED)).filter((n) => n.endsWith(".svg") || n.endsWith(".png"));
  const undeclared = present.filter((n) => !claimed.has(n)).sort();

  return { manifest, artefacts, undeclared, textFloorPx: manifest.site_build?.text_floor_px ?? null };
}

/** Publish one figure artefact: the canonical bytes, unchanged, with its provenance. */
async function publishArtefact(artefact) {
  await writeFile(join(outDir, artefact.name), artefact.bytes);
  emitted.push({
    name: artefact.name,
    kind: artefact.kind,
    variant: artefact.variant,
    figure_id: artefact.figureId,
    media_type: artefact.mediaType,
    description: VARIANTS[artefact.mediaType].describe(
      artefact.figureId,
      artefact.sourceDisplay,
      artefact.detail,
    ),
    bytes: artefact.bytes.length,
    sha256: artefact.sourceSha256,
    source_path: artefact.sourceDisplay,
    source_sha256: artefact.sourceSha256,
    identity: artefact.authoritative
      ? `byte-identical to ${artefact.sourceDisplay}; the page inlines those same bytes with leading and trailing whitespace trimmed`
      : `byte-identical to ${artefact.sourceDisplay}; the same drawing as ${artefact.siblingVector} in a different encoding, not the same bytes`,
    renderer_sha256: artefact.rendererSha256,
    numerical_run_id: artefact.numericalRunId,
    data_files: artefact.dataFiles,
  });
}

/* ------------------------------------------------------------------ *
 * Main
 * ------------------------------------------------------------------ */

async function main() {
  await rm(outDir, { recursive: true, force: true });
  await mkdir(outDir, { recursive: true });

  const contract = await readJson(join(FIGURE_DATA, "contract.json"));

  /* --- F01 / F01b / F02 ------------------------------------------- */
  const scenarioFile = await readJson(join(FIGURE_DATA, "f01_f02_scenarios.json"));
  const scenarios = scenarioFile.scenarios;
  if (!Array.isArray(scenarios) || scenarios.length !== 8) {
    throw new Error(`expected eight computed scenarios, found ${scenarios?.length}`);
  }

  const allRows = scenarios.flatMap(scenarioRows);
  await emit(
    "f01_f02_scenarios_all.csv",
    csv(SCENARIO_COLUMNS, allRows),
    `All eight computed aquifer cases, ${allRows.length} observation rows. Full dataset.`,
    "full",
  );
  await emitJson(
    "f01_f02_scenarios_all.json",
    scenarioFile,
    "All eight computed aquifer cases, the committed export verbatim. Full dataset.",
    "full",
  );
  await emitJson(
    "f01_f02_scenario_summaries.json",
    { scenarios: scenarios.map(scenarioSummary) },
    "Per-case headline block for all eight computed cases, with the true inventory derived from the exported fields.",
    "full",
  );

  for (const scenario of scenarios) {
    const slug = caseSlug(scenario.productivity_index_bbl_per_day_psi);
    const rows = scenarioRows(scenario);
    const j = scenario.productivity_index_bbl_per_day_psi;
    await emit(
      `f01_f02_case-${slug}.csv`,
      csv(SCENARIO_COLUMNS, rows),
      `Selected case only: J = ${j} bbl/day/psi, ${rows.length} observations.`,
      "selected",
    );
    await emitJson(
      `f01_f02_case-${slug}.json`,
      { selected_case: scenarioSummary(scenario), observations: rows },
      `Selected case only: J = ${j} bbl/day/psi, headline block and ${rows.length} observations.`,
      "selected",
    );
  }

  /* --- F03 -------------------------------------------------------- */
  const f03 = await readJson(join(FIGURE_DATA, "f03_bias_sweep.json"));
  await emit(
    "f03_bias_sweep.csv",
    csv(
      [
        num("productivity_index_bbl_per_day_psi"),
        num("aquifer_time_constant_days"),
        num("timestep_over_time_constant"),
        num("terminal_water_influx_bbl"),
        num("invaded_pore_volume_fraction"),
        num("terminal_pressure_psia"),
        num("r_squared"),
        num("fitted_gas_in_place_scf"),
        num("relative_gas_in_place_error"),
        num("fitted_stderr_scf"),
        num("bias_over_stderr"),
        num("relative_remaining_gas_error"),
        num("max_abs_residual_psia"),
        num("rms_residual_psia"),
      ],
      f03.rows,
    ),
    "F03 aquifer-strength sweep, eight computed cases. An empty aquifer_time_constant_days is the volumetric control, whose time constant is infinite.",
    "full",
  );
  await emitJson("f03_bias_sweep.json", f03, "F03 aquifer-strength sweep, the committed export verbatim.", "full");

  /* --- F04 -------------------------------------------------------- */
  const f04 = await readJson(join(FIGURE_DATA, "f04_progressive.json"));
  await emit(
    "f04_progressive.csv",
    csv(
      [
        num("productivity_index_bbl_per_day_psi"),
        num("history_fraction"),
        num("n_points"),
        num("years_observed"),
        num("r_squared"),
        num("relative_gas_in_place_error"),
        num("relative_stderr"),
        num("depletion_fraction_observed"),
      ],
      f04.rows,
    ),
    "F04 progressive prefix fits, all eight cases at five history fractions. Full dataset; the figure draws four of the eight.",
    "full",
  );
  await emitJson("f04_progressive.json", f04, "F04 progressive prefix fits, the committed export verbatim.", "full");

  /* --- F05 -------------------------------------------------------- */
  const f05 = await readJson(join(FIGURE_DATA, "f05_holdout.json"));
  const f05Rows = f05.times_years.map((t, i) => ({
    observation_index: i,
    region: i < f05.split_index ? "calibration" : "held out",
    times_years: t,
    cumulative_gas_bscf: f05.cumulative_gas_bscf[i],
    observed_p_over_z_psia: f05.observed_p_over_z_psia[i],
    fitted_p_over_z_psia: f05.fitted_p_over_z_psia[i],
    observed_pressure_psia: f05.observed_pressure_psia[i],
    reconstructed_pressure_psia_conditional: f05.reconstructed_pressure_psia_conditional[i],
    future_synthetic_z_used: f05.future_synthetic_z_used[i],
  }));
  await emit(
    "f05_holdout.csv",
    csv(
      [
        num("observation_index"),
        num("region"),
        num("times_years"),
        num("cumulative_gas_bscf"),
        num("observed_p_over_z_psia"),
        num("fitted_p_over_z_psia"),
        num("observed_pressure_psia"),
        num("reconstructed_pressure_psia_conditional"),
        num("future_synthetic_z_used"),
      ],
      f05Rows,
    ),
    "F05 chronological split, 30 calibration and 19 held-out observations. An empty reconstruction field is the calibration region, where there is no reconstruction to report.",
    "full",
  );
  await emitJson("f05_holdout.json", f05, "F05 chronological split, the committed export verbatim.", "full");

  /* --- F06 -------------------------------------------------------- */
  const f06 = await readJson(join(FIGURE_DATA, "f06_detection.json"));
  const f06Rows = [
    ...f06.original.rows.map((r) => ({
      experiment: "pre-registered noise sweep",
      replicates: f06.original.replicates,
      pressure_sigma_psi: r.pressure_sigma_psi,
      detection_rate_water_drive: r.detection_rate_water_drive,
      detection_rate_volumetric_null: r.detection_rate_volumetric_null,
    })),
    ...f06.post_review_power_curve.rows.map((r) => ({
      experiment: "post-review power curve",
      replicates: f06.post_review_power_curve.replicates,
      pressure_sigma_psi: r.pressure_sigma_psi,
      detection_rate_water_drive: r.detection_rate,
      detection_rate_volumetric_null: null,
    })),
  ];
  await emit(
    "f06_detection.csv",
    csv(
      [
        num("experiment"),
        num("replicates"),
        num("pressure_sigma_psi"),
        num("detection_rate_water_drive"),
        num("detection_rate_volumetric_null"),
      ],
      f06Rows,
    ),
    "F06 detectability. Two experiments with different seeds and replicate counts, kept in separate rows and never spliced; the post-review curve has no null column.",
    "full",
  );
  await emitJson("f06_detection.json", f06, "F06 detectability, the committed export verbatim.", "full");

  /* --- F07 -------------------------------------------------------- */
  const f07 = await readJson(join(FIGURE_DATA, "f07_z_mismatch.json"));
  await emit(
    "f07_z_mismatch.csv",
    csv(
      [num("quantity"), num("value")],
      Object.entries(f07.values)
        .filter(([, v]) => typeof v === "number")
        .map(([quantity, value]) => ({ quantity, value })),
    ),
    "F07 deviation-factor correlation mismatch. Signed statistics are kept signed.",
    "full",
  );
  await emitJson("f07_z_mismatch.json", f07, "F07 correlation mismatch, the committed export verbatim.", "full");

  /* --- F08 -------------------------------------------------------- */
  const f08 = await readJson(join(FIGURE_DATA, "f08_refinement.json"));
  const f08Rows = ["J_2", "J_60"].flatMap((key) =>
    f08[key].levels.map((level) => ({
      case: key === "J_2" ? 2 : 60,
      timestep_days: level.timestep_days,
      steps: level.steps,
      terminal_water_influx_bbl: level.terminal_water_influx_bbl,
      relative_gas_in_place_error: level.relative_gas_in_place_error,
      max_solver_residual_p_over_z_psia: level.max_solver_residual_p_over_z_psia,
    })),
  );
  await emit(
    "f08_refinement.csv",
    csv(
      [
        { header: "productivity_index_bbl_per_day_psi", value: (r) => r.case },
        num("timestep_days"),
        num("steps"),
        num("terminal_water_influx_bbl"),
        num("relative_gas_in_place_error"),
        num("max_solver_residual_p_over_z_psia"),
      ],
      f08Rows,
    ),
    "F08 timestep refinement at two aquifer strengths, four levels each.",
    "full",
  );
  await emitJson("f08_refinement.json", f08, "F08 timestep refinement, the committed export verbatim.", "full");

  /* --- F09 -------------------------------------------------------- */
  await emitJson(
    "contract.json",
    contract,
    "F09 export contract: numerical source digests, exporter digest, units, evidence class and the seven declared figure-data files.",
    "full",
  );

  /* --- A1-01 ------------------------------------------------------ */
  const a1 = await readJson(join(REPO, "cases", "A1_volumetric_baseline", "results", "summary.json"));
  const a1Block = a1.diagnostic_d1_defect_sensitivity;
  if (!a1Block) throw new Error("A1 summary has no diagnostic_d1_defect_sensitivity block");
  await emit(
    "a1_01_defect_sensitivity.csv",
    csv(
      [
        num("name"),
        num("defect_class"),
        num("magnitude"),
        num("recovery_relative_error"),
        num("detected_at_A1_gate"),
      ],
      a1Block.cases,
    ),
    "A1-01 seeded-defect positive control. Post-hoc, not pre-registered and not gated.",
    "full",
  );
  await emitJson(
    "a1_01_defect_sensitivity.json",
    a1Block,
    "A1-01 seeded-defect positive control, the block as the case summary records it.",
    "full",
  );

  /* --- A3-01 ------------------------------------------------------ */
  const a3 = await readJson(join(REPO, "cases", "A3_uncertainty_experiments", "results", "summary.json"));
  const a3Block = a3.results?.E7_ranking;
  if (!a3Block) throw new Error("A3 summary has no results.E7_ranking block");
  const a3Rows = Object.entries(a3Block.rankings_by_assumed_sigma).flatMap(([group, list]) =>
    list.map((entry, rank) => ({
      assumed_sigma_group: group,
      rank: rank + 1,
      source: entry.source,
      relative_effect: entry.relative_effect,
    })),
  );
  await emit(
    "a3_01_error_budget_ranking.csv",
    csv([num("assumed_sigma_group"), num("rank"), num("source"), num("relative_effect")], a3Rows),
    "A3-01 error-budget ranking at three assumed pressure standard deviations. Ordinate sources only.",
    "full",
  );
  await emitJson(
    "a3_01_error_budget_ranking.json",
    a3Block,
    "A3-01 error-budget ranking, the block as the case summary records it.",
    "full",
  );

  /* --- B1 --------------------------------------------------------- */
  const b1 = await readJson(join(REPO, "cases", "B1_iarf_known_answer", "results", "summary.json"));
  const b1Base = b1.b1_0_mathematical_baseline;
  if (!b1Base) throw new Error("B1 summary has no b1_0_mathematical_baseline block");
  const b1Series = b1Base.series;
  const b1PressureRows = b1Series.time_hours.map((hours, i) => ({
    time_hours: hours,
    dimensionless_time: b1Series.dimensionless_time[i],
    drawdown_psi: b1Series.drawdown_psi[i],
    fitted_line_psi: b1Series.fitted_line_psi[i],
    residual_psi: b1Series.residual_psi[i],
  }));
  await emit(
    "b1_pressure_and_fit.csv",
    csv(
      [
        num("time_hours"),
        num("dimensionless_time"),
        num("drawdown_psi"),
        num("fitted_line_psi"),
        num("residual_psi"),
      ],
      b1PressureRows,
    ),
    "B1 synthetic drawdown over the declared interpretation window, with the fitted semilog line and its residual.",
    "full",
  );

  const b1DerivativeRows = b1Series.derivative_time_hours.map((hours, i) => ({
    time_hours: hours,
    derivative_psi: b1Series.derivative_psi[i],
    analytic_derivative_psi: b1Series.analytic_derivative_psi[i],
  }));
  await emit(
    "b1_derivative.csv",
    csv([num("time_hours"), num("derivative_psi"), num("analytic_derivative_psi")], b1DerivativeRows),
    "B1 Bourdet derivative against the closed form (1/2)exp(-1/(4 t_D)), which is exact and is not what the algorithm computes.",
    "full",
  );

  const b1Visibility = b1.diagnostic_defect_visibility;
  if (!b1Visibility) throw new Error("B1 summary has no diagnostic_defect_visibility block");
  await emit(
    "b1_defect_visibility.csv",
    csv(
      [
        num("defect"),
        num("kind"),
        num("permeability_thickness_relative_error"),
        num("permeability_relative_error"),
        num("skin_absolute_error"),
        num("r_squared"),
        num("derivative_versus_fit_relative_difference"),
        num("visible_without_truth"),
        num("materially_wrong"),
      ],
      b1Visibility.rows,
    ),
    "B1 seeded analyst errors, each scored against the truth and against the two diagnostics available without it. Post-hoc, not pre-registered and not gated.",
    "full",
  );

  await emitJson(
    "b1_summary.json",
    b1,
    "B1 case summary: every value of the committed canonical snapshot, including each criterion flag and both ungated diagnostics. Re-serialised by this emitter rather than copied byte for byte, so a whole-numbered float such as 0.0 is written 0; the numbers themselves are unchanged.",
    "full",
  );

  /* --- B2 ----------------------------------------------------------
   * B2's result is a refusal, so its downloads are built to carry the refusal rather than
   * a parameter. The sweep file has no permeability column at all: two of its rows would
   * have a value and three would not, and a mostly-empty column in a spreadsheet is an
   * invitation to fill it in. */
  const b2 = await readJson(join(REPO, "cases", "B2_wellbore_storage_window", "results", "summary.json"));
  const b2Primary = b2.b2_1_primary_noise_free;
  if (!b2Primary) throw new Error("B2 summary has no b2_1_primary_noise_free block");
  const b2Series = b2Primary.series;
  if (!b2Series || b2Series.derivative_available !== true) {
    throw new Error("B2 primary case has no exported derivative series");
  }

  const b2DerivRows = b2Series.derivative_time_hours.map((hours, i) => ({
    time_hours: hours,
    derivative_psi: b2Series.derivative_psi[i],
    generator_derivative_psi: b2Series.generator_derivative_psi[i],
    storage_ratio: b2Series.storage_ratio[i],
  }));
  await emit(
    "b2_primary_diagnostic.csv",
    csv(
      [num("time_hours"), num("derivative_psi"), num("generator_derivative_psi"), num("storage_ratio")],
      b2DerivRows,
    ),
    "B2 primary case at C_D = 1000: the Bourdet derivative an interpreter computes, the generator's own analytic derivative for comparison, and the storage ratio D/dp the rule's exclusion tests. The rule certified no window on this record.",
    "full",
  );

  const b2SweepRows = b2.b2_2_storage_sweep.levels.map((level) => ({
    storage_dimensionless: level.storage_dimensionless,
    storage_bbl_per_psi: level.storage_bbl_per_psi,
    crossover_hours: level.crossover_hours,
    window_certified: level.analyst.window_found,
    widest_admissible_decades: level.analyst.window_found
      ? level.analyst.window_decades
      : level.analyst.widest_admissible_decades,
    decline_reason: level.analyst.window_found ? "" : level.analyst.reason,
  }));
  await emit(
    "b2_storage_sweep.csv",
    csv(
      [
        num("storage_dimensionless"),
        num("storage_bbl_per_psi"),
        num("crossover_hours"),
        num("window_certified"),
        num("widest_admissible_decades"),
        num("decline_reason"),
      ],
      b2SweepRows,
    ),
    "B2 storage-strength sweep under the frozen selector over a 48-hour record. No permeability column: the rule certified a window at one of these four levels, and a column that is blank for the rest would invite a reader to fill it.",
    "full",
  );

  const b2PosthocRows = b2.posthoc_exploratory.levels.map((level) => ({
    storage_dimensionless: level.storage_dimensionless,
    crossover_hours: level.crossover_hours,
    first_certifying_hours: level.frozen_selector.first_certifying_hours,
    reported: level.reported_days,
    monotone_after_crossing: level.frozen_selector.monotone_after_crossing,
  }));
  await emit(
    "b2_time_to_certification.csv",
    csv(
      [
        num("storage_dimensionless"),
        num("crossover_hours"),
        num("first_certifying_hours"),
        num("reported"),
        num("monotone_after_crossing"),
      ],
      b2PosthocRows,
    ),
    "POST-HOC EXPLORATORY ANALYSIS, not pre-registered and no part of the B2 classification: the shortest record at which the frozen selector first certifies a window at each storage level. A property of this synthetic model, not a field test-design recommendation.",
    "full",
  );

  await emitJson(
    "b2_summary.json",
    b2,
    "B2 case summary: the committed canonical snapshot, including every criterion flag, the classification, the post-hoc analysis in its own namespace, and the exported series. Re-serialised by this emitter rather than copied byte for byte, so a whole-numbered float such as 0.0 is written 0; the numbers themselves are unchanged.",
    "full",
  );

  /* --- downloadable copies of the exhibits themselves ---------------
   * The SVG a reader downloads must be the file the page inlined, byte for byte, or the
   * download is a different artefact wearing the same name. These are copies, not
   * re-renders: the bytes are read from site/src/generated/figures/ and written back
   * unchanged, and each is registered with the variant it is, the canonical file it
   * copies and that file's digest. --verify then compares the two directly rather than
   * trusting the digest this script wrote. */
  const registry = await figureRegistry();
  await mkdir(join(outDir, "figures"), { recursive: true });
  for (const artefact of registry.artefacts) await publishArtefact(artefact);

  /* --- the index ---------------------------------------------------
   * Written last, and deliberately not listed inside itself: it is the
   * verification record for the other files, not one of them. */
  const rasters = emitted.filter((f) => f.kind === "exhibit-raster");
  const index = {
    generator: "site/src/scripts/emit-public-data.mjs",
    sources: [
      "site/src/data/figures/*.json",
      "site/src/generated/figures/manifest.json (the figure specification)",
      "site/src/generated/figures/*.svg, *.png (the canonical rendered figures)",
      "cases/A1_volumetric_baseline/results/summary.json (diagnostic_d1_defect_sensitivity only)",
      "cases/A3_uncertainty_experiments/results/summary.json (results.E7_ranking only)",
    ],
    evidence_class: contract.evidence_class,
    units: contract.units,
    csv_precision: "12 significant figures; the JSON copies carry full double precision",
    excluded:
      "No reference-derived value is published. The NIST Chemistry WebBook extract is not redistributed by this repository and nothing derived from it appears here.",
    chain: {
      links: [
        "checked numerical data: site/src/data/figures/*.json, each digest declared in contract.json",
        "figure specification: site/src/generated/figures/manifest.json",
        "canonical rendered figure: site/src/generated/figures/<id>.svg and <id>.png",
        "published download: site/public/data/figures/<id>.svg and <id>.png",
        "displayed figure: the SVG inlined into the built page",
      ],
      enforced_by:
        "node src/scripts/emit-public-data.mjs --verify re-emits into a scratch directory and compares it with the published tree byte for byte, then compares every published figure artefact against the canonical file it copies. scripts/build_release.py runs it as a mandatory step and then proves the trimmed canonical SVG appears verbatim in the built HTML.",
      inline_transform:
        "One transformation, and only one: src/scripts/exhibits.ts trims leading and trailing whitespace from the canonical SVG before inlining it. No id is rewritten, no accessibility association is re-pointed, no attribute is added or removed. Source-to-download identity is exact in both directions; the trim applies to the displayed copy alone and is proved separately against the built HTML.",
      variants:
        "canonical-vector (.svg) is the authoritative artefact and is what the page displays. raster-export (.png) is the same drawing rasterised from that exact SVG by the reviewed renderer at 216 dpi; it is byte-identical to the canonical PNG and is never described as identical to the SVG. Two intentionally different layouts are never called identical.",
    },
    raster_payload: {
      files: rasters.length,
      bytes: rasters.reduce((a, f) => a + f.bytes, 0),
      note:
        "Rasters are downloads only. Nothing on the site inlines, embeds or preloads them, so they are not part of any page's initial payload. Their size is accounted for separately here and in docs/release/DISTRIBUTION_MANIFEST.md.",
    },
    files: emitted,
  };
  await writeFile(join(outDir, "index.json"), `${JSON.stringify(index, null, 2)}\n`, "utf8");

  return { index, registry };
}

/* ------------------------------------------------------------------ *
 * --verify: the chain, checked rather than asserted
 * ------------------------------------------------------------------ */

/** Every file under a directory, as repository-style relative paths, sorted. */
async function listFiles(root) {
  const entries = await readdir(root, { recursive: true, withFileTypes: true });
  return entries
    .filter((e) => e.isFile())
    .map((e) => relative(root, join(e.parentPath ?? e.path, e.name)).split(sep).join("/"))
    .sort();
}

/**
 * Text-size floor and clipping, checked on the canonical SVG rather than in a browser.
 *
 * Both are properties a re-render can break silently, and both have a cheap static form.
 *
 * The floor. Every `font-size` in these drawings is a literal number, in user units or
 * px, set on the `<text>` element or on a group above it, so the effective size of a
 * label is resolved here by walking the ancestor stack. Any resolved size below the
 * floor the figure specification itself records is a failure.
 *
 * Text that inherits its size from the document rather than from the drawing is a
 * different thing and is reported as a count, not as a failure. Plot leaves the axis
 * tick labels unsized: in the page their size comes from the site stylesheet, which is
 * what the browser responsive check gates and where that check belongs. A static gate
 * cannot see a stylesheet, so it says how many labels are in that state and leaves the
 * verdict to the instrument that can.
 *
 * The clipping check is deliberately conservative and says so: it locates each text
 * element's anchor by accumulating the translate transforms above it and requires that
 * anchor to lie inside the viewBox. It does not measure glyph extents, which would need
 * font metrics, so it catches an annotation placed outside the drawing and not one that
 * overflows the edge by a few pixels. The browser suite covers what this cannot.
 */
function presentationFloors(name, svgText, floorPx) {
  const problems = [];
  let inherited = 0;

  const viewBox = /viewBox="([^"]+)"/.exec(svgText);
  if (!viewBox) {
    problems.push(`${name}: no viewBox; the drawing declares no coordinate space`);
    return { problems, inherited };
  }
  const [x0, y0, width, height] = viewBox[1].split(/[\s,]+/).map(Number);

  /** `font-size="13"` and `font-size="13px"` are both user units at this scale. */
  const fontSize = (attrs) => {
    const m = /font-size="([0-9.]+)(?:px)?"/.exec(attrs);
    return m ? Number(m[1]) : null;
  };

  const TRANSLATE = /translate\(\s*([-0-9.eE+]+)\s*[\s,]\s*([-0-9.eE+]+)\s*\)/;
  const stack = [];
  let offset = [0, 0];
  let size = fontSize(/<svg\b([^>]*)>/.exec(svgText)?.[1] ?? "");
  const outside = [];
  const below = new Set();
  const tags = /<(\/?)(g|text)\b([^>]*)>/g;
  let match;
  while ((match = tags.exec(svgText)) !== null) {
    const [, closing, tag, attrs] = match;
    if (tag === "g") {
      if (closing) {
        const popped = stack.pop();
        if (popped) [offset, size] = popped;
      } else if (!/\/\s*$/.test(attrs)) {
        stack.push([offset.slice(), size]);
        const t = /transform="([^"]*)"/.exec(attrs);
        const tr = t && TRANSLATE.exec(t[1]);
        if (tr) offset = [offset[0] + Number(tr[1]), offset[1] + Number(tr[2])];
        const declared = fontSize(attrs);
        if (declared !== null) size = declared;
      }
      continue;
    }
    if (closing) continue;

    const own = fontSize(attrs);
    const effective = own ?? size;
    if (effective === null) inherited += 1;
    else if (typeof floorPx === "number" && effective < floorPx) below.add(effective);

    const t = /transform="([^"]*)"/.exec(attrs);
    const tr = t && TRANSLATE.exec(t[1]);
    let [cx, cy] = offset;
    if (tr) {
      cx += Number(tr[1]);
      cy += Number(tr[2]);
    }
    const xa = /\sx="([-0-9.eE+]+)"/.exec(attrs);
    const ya = /\sy="([-0-9.eE+]+)"/.exec(attrs);
    const x = cx + (xa ? Number(xa[1]) : 0);
    const y = cy + (ya ? Number(ya[1]) : 0);
    if (x < x0 || x > x0 + width || y < y0 || y > y0 + height) {
      outside.push(`(${x.toFixed(1)}, ${y.toFixed(1)})`);
    }
  }

  if (below.size > 0) {
    problems.push(
      `${name}: text set below the ${floorPx}px floor the figure specification records: ` +
        `${[...below].sort((a, b) => a - b).join(", ")}px. A reader cannot read what the ` +
        `design already decided is too small.`,
    );
  }
  if (outside.length > 0) {
    problems.push(
      `${name}: ${outside.length} text anchor(s) outside the ${width}x${height} viewBox ` +
        `-- ${outside.slice(0, 4).join(" ")}${outside.length > 4 ? " ..." : ""}. ` +
        `An annotation drawn outside the drawing is clipped in the page and in the raster.`,
    );
  }
  return { problems, inherited };
}

async function verify() {
  const problems = [];
  const checks = [];
  const record = (name, ok, detail) => {
    checks.push({ check: name, status: ok ? "passed" : "failed", detail });
    if (!ok) problems.push(detail);
  };

  /* 1. Deterministic re-emission, compared with what is published. */
  const scratch = await mkdtemp(join(tmpdir(), "emit-public-data-verify-"));
  let expectedIndex;
  let registry;
  try {
    emitted = [];
    outDir = scratch;
    const result = await main();
    expectedIndex = result.index;
    registry = result.registry;
    outDir = OUT;

    const [want, have] = await Promise.all([listFiles(scratch), listFiles(OUT).catch(() => [])]);
    const missing = want.filter((f) => !have.includes(f));
    const extra = have.filter((f) => !want.includes(f));
    record(
      "published tree has exactly the files a fresh emission writes",
      missing.length === 0 && extra.length === 0,
      `${show(OUT)}: ${missing.length} missing (${missing.slice(0, 6).join(", ") || "none"}), ` +
        `${extra.length} unexpected (${extra.slice(0, 6).join(", ") || "none"}). ` +
        `Run: node src/scripts/emit-public-data.mjs`,
    );

    const drifted = [];
    for (const name of want.filter((f) => have.includes(f))) {
      const [a, b] = await Promise.all([
        readFile(join(scratch, name)),
        readFile(join(OUT, name)),
      ]);
      if (!a.equals(b)) {
        drifted.push(
          `${name}: published ${b.length} B sha ${sha256Bytes(b).slice(0, 12)}, ` +
            `a fresh emission writes ${a.length} B sha ${sha256Bytes(a).slice(0, 12)}`,
        );
      }
    }
    record(
      "every published file is byte-for-byte what a fresh emission writes",
      drifted.length === 0,
      drifted.length === 0
        ? `${want.length} files match a fresh emission`
        : `${drifted.length} published file(s) differ from a fresh emission:\n    ${drifted.join("\n    ")}`,
    );
  } finally {
    outDir = OUT;
    await rm(scratch, { recursive: true, force: true });
  }

  /* 2. Published figure artefact against the canonical rendered file it copies. */
  const identityFailures = [];
  for (const artefact of registry.artefacts) {
    let published;
    try {
      published = await readFile(join(OUT, artefact.name));
    } catch {
      identityFailures.push(`${artefact.name}: not published at all (canonical source ${artefact.sourceDisplay} exists)`);
      continue;
    }
    if (!published.equals(artefact.bytes)) {
      identityFailures.push(
        `${artefact.name}: published copy is ${published.length} B ` +
          `sha ${sha256Bytes(published).slice(0, 12)}, canonical ${artefact.sourceDisplay} is ` +
          `${artefact.bytes.length} B sha ${artefact.sourceSha256.slice(0, 12)}. ` +
          `index.json claims these are byte-identical and they are not.`,
      );
    }
  }
  record(
    "every published figure is byte-identical to its canonical rendered source",
    identityFailures.length === 0,
    identityFailures.length === 0
      ? `${registry.artefacts.length} artefacts identical to site/src/generated/figures/`
      : identityFailures.join("\n    "),
  );

  record(
    "the generated directory holds nothing the specification does not declare",
    registry.undeclared.length === 0,
    registry.undeclared.length === 0
      ? "every rendered file is declared by the manifest"
      : `${show(GENERATED)} holds ${registry.undeclared.join(", ")}, which manifest.json does not declare. ` +
        `An undeclared drawing has no provenance and is not published; remove it or declare it.`,
  );

  /* 3. index.json against the bytes on disk. */
  const digestFailures = [];
  for (const file of expectedIndex.files) {
    let bytes;
    try {
      bytes = await readFile(join(OUT, file.name));
    } catch {
      digestFailures.push(`${file.name}: indexed but absent`);
      continue;
    }
    if (bytes.length !== file.bytes) digestFailures.push(`${file.name}: ${bytes.length} B, index records ${file.bytes} B`);
    const digest = sha256Bytes(bytes);
    if (digest !== file.sha256) digestFailures.push(`${file.name}: sha ${digest.slice(0, 12)}, index records ${file.sha256.slice(0, 12)}`);
    if (file.source_sha256 && file.source_sha256 !== file.sha256) {
      digestFailures.push(
        `${file.name}: index records source_sha256 ${file.source_sha256.slice(0, 12)} and ` +
          `sha256 ${file.sha256.slice(0, 12)}. A copy declared byte-identical cannot have two digests.`,
      );
    }
  }
  record(
    "every indexed download matches its recorded size and digest",
    digestFailures.length === 0,
    digestFailures.length === 0
      ? `${expectedIndex.files.length} indexed files re-hashed`
      : digestFailures.join("\n    "),
  );

  /* 4. Specification against drawing: name, description length, declared variants. */
  const metadataFailures = [];
  const unescape = (s) =>
    s
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">")
      .replace(/&quot;/g, '"')
      .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(Number(d)))
      .replace(/&amp;/g, "&");
  for (const artefact of registry.artefacts) {
    if (artefact.mediaType !== "image/svg+xml") continue;
    const text = artefact.bytes.toString("utf8");
    const label = /aria-label="([^"]*)"/.exec(text);
    if (!label) {
      metadataFailures.push(`${artefact.file}: no aria-label; the drawing carries no accessible name`);
    } else if (artefact.accessibleName && unescape(label[1]) !== artefact.accessibleName) {
      metadataFailures.push(
        `${artefact.file}: the drawing's accessible name is "${unescape(label[1])}" but the ` +
          `specification records "${artefact.accessibleName}". The caption and the chart ` +
          `would disagree on the page.`,
      );
    }
    const desc = /<desc[^>]*>([\s\S]*?)<\/desc>/.exec(text);
    if (!desc) {
      metadataFailures.push(`${artefact.file}: no <desc>; the figure has no text alternative`);
    } else if (
      typeof artefact.longDescriptionChars === "number" &&
      unescape(desc[1]).length !== artefact.longDescriptionChars
    ) {
      metadataFailures.push(
        `${artefact.file}: the long description is ${unescape(desc[1]).length} characters but ` +
          `the specification records ${artefact.longDescriptionChars}. One of the two is stale.`,
      );
    }
  }
  const byFigure = new Map();
  for (const a of registry.artefacts) {
    byFigure.set(a.figureId, (byFigure.get(a.figureId) ?? new Set()).add(a.variant));
  }
  for (const [id, variants] of byFigure) {
    for (const required of ["canonical-vector", "raster-export"]) {
      if (!variants.has(required)) {
        metadataFailures.push(`figure ${id}: no ${required} variant is published; the approved core figures ship both`);
      }
    }
  }
  record(
    "the drawing agrees with the specification, and every declared variant is published",
    metadataFailures.length === 0,
    metadataFailures.length === 0
      ? `${byFigure.size} figures, ${registry.artefacts.length} variants, names and descriptions agree`
      : metadataFailures.join("\n    "),
  );

  /* 5. Presentation floors on the canonical drawings. */
  const floorFailures = [];
  const inheritedSizes = {};
  for (const artefact of registry.artefacts) {
    if (artefact.mediaType !== "image/svg+xml") continue;
    const floor = artefact.minimumLabelPx ?? registry.textFloorPx;
    const result = presentationFloors(artefact.file, artefact.bytes.toString("utf8"), floor);
    floorFailures.push(...result.problems);
    if (result.inherited > 0) inheritedSizes[artefact.file] = result.inherited;
  }
  record(
    "no canonical figure carries below-floor text or a text anchor outside its drawing",
    floorFailures.length === 0,
    floorFailures.length === 0
      ? `text floor ${registry.textFloorPx}px and viewBox containment hold for every figure`
      : floorFailures.join("\n    "),
  );

  const summary = {
    tool: "emit-public-data --verify",
    published_dir: show(OUT),
    figures: byFigure.size,
    artefacts: registry.artefacts.length,
    indexed_files: expectedIndex.files.length,
    raster_files: expectedIndex.raster_payload.files,
    raster_bytes: expectedIndex.raster_payload.bytes,
    checks,
    /* Not a verdict. These labels carry no font-size of their own, so their rendered
       size is set by the page stylesheet and only a browser can measure it. Counted here
       so the number is visible rather than absent; the responsive browser check owns the
       floor for them. */
    text_with_inherited_size: inheritedSizes,
    status: problems.length === 0 ? "passed" : "failed",
  };
  process.stdout.write(`${JSON.stringify(summary, null, 2)}\n`);

  if (problems.length > 0) {
    for (const problem of problems) process.stderr.write(`emit-public-data --verify: ${problem}\n`);
    throw new Error(`${problems.length} check(s) failed; the published downloads do not match what was rendered`);
  }
  process.stdout.write(`emit-public-data --verify: ${checks.length} checks passed\n`);
}

/* ------------------------------------------------------------------ *
 * Entry point
 * ------------------------------------------------------------------ */

async function cli() {
  const argv = process.argv.slice(2);
  const outFlag = argv.indexOf("--out");
  if (outFlag !== -1) {
    if (!argv[outFlag + 1]) throw new Error("--out needs a directory");
    outDir = argv[outFlag + 1];
  }
  const unknown = argv.filter(
    (a, i) => a.startsWith("--") && a !== "--verify" && a !== "--out" && argv[i - 1] !== "--out",
  );
  if (unknown.length > 0) throw new Error(`unknown option(s): ${unknown.join(", ")}`);

  if (argv.includes("--verify")) {
    await verify();
    return;
  }
  const { index } = await main();
  const written = (await readdir(outDir, { recursive: true })).length;
  const bytes = index.files.reduce((a, f) => a + f.bytes, 0);
  const raster = index.raster_payload;
  process.stdout.write(
    `${show(outDir)}: ${written} entries, ${index.files.length} indexed, ${bytes} B total ` +
      `(${bytes - raster.bytes} B text and vector, ${raster.bytes} B in ${raster.files} rasters, ` +
      `none of it in a page payload)\n`,
  );
}

cli().catch((error) => {
  process.stderr.write(`emit-public-data: ${error.message}\n`);
  process.exitCode = 1;
});

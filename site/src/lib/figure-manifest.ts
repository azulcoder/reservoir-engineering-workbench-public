/**
 * The shape of src/generated/figures/manifest.json.
 *
 * scripts/render-figures.mjs writes that file on every build; this module only declares
 * its type and gives the page a typed, fail-closed way to read it. Nothing here derives,
 * rounds or reformats a number: every field is the value the renderer measured or copied
 * from ../data/figures/contract.json.
 *
 * The distinction the type is built around: `numerical_source` and `export` identify the
 * run that produced the numbers, while `generated` and `site_build` identify the code that
 * drew them. They are different provenance and are never merged into one revision string.
 */

/** A SHA-256 digest, lower-case hexadecimal, 64 characters. */
export type Sha256 = string;

/** One axis of a figure, with its unit and its scale stated rather than implied. */
export interface FigureAxis {
  /** The physical or statistical quantity, in words. */
  quantity: string;
  /** The unit as the contract declares it, e.g. "psia (absolute)" or "Bscf = 1e9 scf". */
  unit: string;
  /** "linear", "log", "log, reversed" or "band". */
  scale: string;
  /** Drawn domain, when the axis is quantitative. */
  domain?: [number, number];
  /** Present, and true, only where including zero is load-bearing for the reading. */
  includes_zero?: boolean;
  /** Present where the axis is symmetric so that a sign reversal reads as a reversal. */
  symmetric_about_zero?: boolean;
}

/**
 * A figure's axes. Keys are per figure: single-panel figures use `x` and `y`, stacked or
 * paired panels use suffixed keys such as `y_upper` or `x_secondary`, and F09, which has
 * no quantitative encoding at all, carries `note` instead.
 */
export type FigureAxes = Record<string, FigureAxis | string>;

/** A data file this figure consumed, with the digest the renderer measured. */
export interface ExportedDataHash {
  /** Repository-relative path. */
  path: string;
  sha256: Sha256;
  /**
   * Whether the measured digest matched contract.json. `null` means the file is outside
   * the export contract -- contract.json itself, or a committed case summary -- so there
   * is nothing to match against.
   */
  matches_contract: boolean | null;
  note?: string;
}

/** What a reader using assistive technology gets, and how the figure reads without colour. */
export interface FigureAccessibility {
  /** Always "img": the SVG is a single image with its own name and long description. */
  role: "img";
  /** The SVG's aria-label. */
  accessible_name: string;
  /** Length of the <desc> long description, in characters. */
  long_description_chars: number;
  non_colour_channels: string;
  /** Smallest label size in the figure, in CSS pixels at the authoring width. */
  minimum_label_px: number;
  colour_source: string;
}

/** Whether the shareable raster was produced, and if not, why not. */
export type PngStatus =
  | { state: "emitted"; rasteriser: string; reason?: never }
  | { state: "BLOCKED"; reason: string; rasteriser?: never };

/** One emitted file and its measured size. */
export interface EmittedFile {
  /** Path relative to src/generated/figures/. */
  path: string;
  bytes: number;
  media_type: "image/svg+xml" | "image/png";
  /** Raster scale, on PNG entries only. */
  raster?: string;
}

/** Everything recorded about one figure. */
export interface FigureRecord {
  /** F01, F01b, F02 ... F09, A1-01, A3-01. */
  figure_id: string;
  case_id: string;
  /** The experiment or pointer this figure draws, named precisely enough to re-find it. */
  selector: string;
  data_files: string[];
  evidence_class: string;
  units: Record<string, string>;
  standard_conditions: string;
  /** The digest that identifies the numerical run. */
  numerical_run_id: Sha256;
  numerical_run_id_basis: string;
  numerical_source_digests: {
    protocol_sha256: Sha256;
    case_source_sha256: Sha256;
    baseline_summary_sha256: Sha256;
    baseline_summary_path: string;
  };
  export_code_revision: {
    exporter_path: string;
    exporter_sha256: Sha256;
    reconciliation_checks_passed: number;
    reconcile_relative_tolerance: number;
  };
  exported_data_hashes: ExportedDataHash[];
  axes: FigureAxes;
  /** Every transformation applied between the exported value and the drawn position. */
  transformations: string[];
  /** The uncertainty shown, or the explicit sentence "none: this figure shows no uncertainty." */
  uncertainty: string;
  /** The reader's question this figure answers. */
  question: string;
  /** What the figure does not establish. Rendered with the figure, never hidden. */
  caveat: string;
  accessibility: FigureAccessibility;
  /** Whether the underlying data may be published, and why. */
  public_data_decision: string;
  png_status: PngStatus;
  files: EmittedFile[];
}

/** The manifest as written. */
export interface FigureManifest {
  manifest_version: string;
  /** The site build: which code drew the figures. Distinct from numerical_source. */
  generated: {
    renderer: string;
    renderer_sha256: Sha256;
    note: string;
  };
  site_build: {
    plot: string;
    dom: string;
    node: string;
    authoring_width_px: number;
    text_floor_px: number;
    png_status: {
      emitted: string[];
      blocked: Array<{ figure: string; state: string; reason?: string }>;
      rasteriser: string;
      caveat: string;
    };
  };
  /** The numerical source: which run produced the numbers. Distinct from site_build. */
  numerical_source: {
    baseline_summary_path: string;
    baseline_summary_sha256: Sha256;
    case_source_sha256: Sha256;
    protocol_sha256: Sha256;
  };
  export: {
    exporter_path: string;
    exporter_sha256: Sha256;
    reconciliation_checks_passed: number;
    reconcile_relative_tolerance: number;
  };
  units: Record<string, string>;
  evidence_class: string;
  contract_version: string;
  case_id: string;
  /** Every contract file, with the digest measured at build time. */
  data_file_digests: Array<{ file: string; declared: Sha256; measured: Sha256; match: boolean }>;
  /** Committed case summaries read directly by the appendix exhibits. */
  case_summary_digests: Record<string, Sha256>;
  figures: FigureRecord[];
}

/**
 * Look one figure up by id, failing loudly. The page should never render a figure whose
 * provenance record is missing: that is the failure mode the case is about.
 */
export function figureById(manifest: FigureManifest, id: string): FigureRecord {
  const record = manifest.figures.find((f) => f.figure_id === id);
  if (!record) {
    throw new Error(
      `figure manifest: no record for "${id}"; it has ${manifest.figures.map((f) => f.figure_id).join(", ")}`,
    );
  }
  return record;
}

/** The emitted SVG for a figure, relative to src/generated/figures/. */
export function svgPath(record: FigureRecord): string {
  const file = record.files.find((f) => f.media_type === "image/svg+xml");
  if (!file) throw new Error(`figure manifest: ${record.figure_id} has no SVG file entry`);
  return file.path;
}

/**
 * True only when every contract digest the renderer measured matched. The page may state
 * that the figure data is the committed data only when this is true.
 */
export function digestsAllMatch(manifest: FigureManifest): boolean {
  return manifest.data_file_digests.every((d) => d.match);
}

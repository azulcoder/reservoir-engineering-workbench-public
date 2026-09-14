/**
 * Build-time access to the generated exhibits.
 *
 * Why this module exists, stated plainly rather than buried
 * --------------------------------------------------------
 * `src/lib/figures.ts` is the repository's figure loader and it enforces exactly the
 * guarantees this site needs: a missing manifest, a missing SVG, a stale byte count or a
 * data file that disagrees with `contract.json` all stop the build with a message that
 * names the file. Its data-side API is used here unchanged — `loadFigureData()` is the
 * only path by which any number reaches a page, so every number on this site has had its
 * source file re-hashed against the contract during the build.
 *
 * Its manifest-side API cannot be used as it stands, and that is a real integration gap
 * rather than a preference. `loadManifest()` requires every entry to carry `title` and
 * resolves the SVG file name from a `svg`/`file`/`path` key. The committed manifest that
 * `site/scripts/render-figures.mjs` writes carries neither: each entry is keyed
 * `figure_id` ("F01", "F01b", "A1-01"), the accessible name lives at
 * `accessibility.accessible_name`, and the file names live in a `files[]` array. Calling
 * `loadManifest()` against it fails the build with
 *
 *     [figures] manifest.json figure "F01" has no "title".
 *
 * which is the loader behaving correctly on a manifest shape it was not written for.
 * Rather than loosen the loader or edit a generated artefact, this module reads the same
 * two directories with the same Vite globs and the same failure discipline, and adapts
 * the generator's shape to what `Figure.astro` needs. Every failure below stops the
 * build; there is no placeholder, no "figure unavailable" box and no silent omission. A
 * page that asks for an exhibit the generator did not draw is a specification error and
 * the build says so.
 *
 * The accessible name, the caveat and the long description are the generator's own words,
 * read from the manifest and from the SVG's `<desc>`. Nothing here retypes them.
 */

import type { SitePath } from "../lib/urls";
import { describe, humanBytes, requireDownload } from "./public-data";

/* ------------------------------------------------------------------ *
 * Sources
 * ------------------------------------------------------------------ */

const MANIFEST_RAW = import.meta.glob("../generated/figures/manifest.json", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

const SVG_RAW = import.meta.glob("../generated/figures/*.svg", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

const MANIFEST_PATH = "site/src/generated/figures/manifest.json";
const GENERATED_DIR = "site/src/generated/figures/";
const RUN_FIGURES = "npm run figures  (node site/scripts/render-figures.mjs)";

function basename(key: string): string {
  const cut = key.lastIndexOf("/");
  return cut === -1 ? key : key.slice(cut + 1);
}

const SVGS = new Map(Object.entries(SVG_RAW).map(([k, v]) => [basename(k), v]));

/** Every failure in this module is this class, so a build log is unambiguous. */
export class ExhibitError extends Error {
  constructor(message: string) {
    super(`[exhibits] ${message}`);
    this.name = "ExhibitError";
  }
}

function fail(message: string): never {
  throw new ExhibitError(message);
}

/* ------------------------------------------------------------------ *
 * Manifest shape, as the generator writes it
 * ------------------------------------------------------------------ */

interface GeneratedFile {
  path: string;
  bytes: number;
  media_type: string;
}

interface GeneratedFigure {
  figure_id: string;
  case_id?: string;
  selector?: string;
  question?: string;
  caveat?: string;
  evidence_class?: string;
  data_files?: string[];
  accessibility?: { accessible_name?: string; long_description_chars?: number };
  files?: GeneratedFile[];
}

interface GeneratedManifest {
  figures?: GeneratedFigure[];
  units?: Record<string, string>;
  evidence_class?: string;
  case_id?: string;
  site_build?: Record<string, unknown>;
  numerical_source?: Record<string, string>;
  export?: Record<string, string | number>;
  data_file_digests?: Array<{ file: string; declared: string; measured: string; match: boolean }>;
  case_summary_digests?: Record<string, string>;
}

/** One exhibit, resolved and ready for `Figure.astro`. */
export interface Exhibit {
  /** Fragment id used on the page: lowercase, e.g. "f01", "f01b", "a1-01". */
  id: string;
  /** Figure number as the case prints it, e.g. "F01". */
  number: string;
  /** Title, with the number prefix stripped: the generator writes "F01 — the fit…". */
  title: string;
  /** Inline SVG markup. */
  svg: string;
  /** UTF-8 byte length of that markup. */
  bytes: number;
  /** The figure's key caveat, in the generator's words. */
  caveat: string;
  /** The question the figure answers, in the generator's words. */
  question: string;
  /** The `<desc>` text carried inside the SVG. */
  longDescription: string;
  /** Data files the figure was drawn from. */
  dataFiles: string[];
  /** Selector: which slice of which file. */
  selector: string;
  /** Units line, composed from the manifest's units block. */
  units: string;
  /** Evidence-class line. */
  evidenceClass: string;
  /** Site-relative path to the downloadable copy of this SVG under /data/figures/. */
  svgDownload: SitePath;
  /** File name of the SVG inside the generated directory. */
  svgFile: string;
  /**
   * The raster variant, when the figure has one: the same drawing at 216 dpi, produced
   * by the reviewed renderer from this exact SVG and published as a download.
   *
   * It is a separate variant with its own provenance, not an alternative spelling of the
   * vector. A link to it must name it for what it is -- "Download F01 as PNG (216 dpi
   * raster, 558 kB)" -- and must not imply it is the same file as the SVG or a different
   * layout of the figure. `checkedExhibit()` populates it only after the emitter has
   * registered the file; `exhibit()` leaves it undefined.
   */
  pngDownload?: SitePath;
  /** File name of the PNG inside the generated directory, when one exists. */
  pngFile?: string;
  /** Size of that raster, already formatted, for the link text. */
  pngSize?: string;
  /** What the raster is, in the emitter's words, for a title attribute or a note. */
  pngIdentity?: string;
}

let cache: Map<string, GeneratedFigure> | undefined;
let manifestCache: GeneratedManifest | undefined;

function manifest(): GeneratedManifest {
  if (manifestCache) return manifestCache;
  const key = Object.keys(MANIFEST_RAW)[0];
  const text = key === undefined ? undefined : MANIFEST_RAW[key];
  if (text === undefined) {
    fail(
      `the generated figure manifest is missing.\n` +
        `  expected at: ${MANIFEST_PATH}\n` +
        `  it is produced at build time and is not committed.\n` +
        `  run: ${RUN_FIGURES}`,
    );
  }
  if (/\b(NaN|-?Infinity)\b/.test(text)) {
    fail(`${MANIFEST_PATH} carries a non-finite JSON token.`);
  }
  let parsed: GeneratedManifest;
  try {
    parsed = JSON.parse(text) as GeneratedManifest;
  } catch (error) {
    fail(`${MANIFEST_PATH} is not valid JSON.\n  ${(error as Error).message}`);
  }
  if (!Array.isArray(parsed.figures) || parsed.figures.length === 0) {
    fail(`${MANIFEST_PATH} declares no figures.\n  run: ${RUN_FIGURES}`);
  }
  manifestCache = parsed;
  return parsed;
}

function byId(): Map<string, GeneratedFigure> {
  if (cache) return cache;
  const map = new Map<string, GeneratedFigure>();
  for (const [index, figure] of (manifest().figures ?? []).entries()) {
    const id = figure.figure_id;
    if (typeof id !== "string" || id.trim() === "") {
      fail(`${MANIFEST_PATH} entry ${index} has no "figure_id".`);
    }
    const key = id.toLowerCase();
    if (map.has(key)) fail(`${MANIFEST_PATH} declares figure "${id}" twice.`);
    map.set(key, figure);
  }
  cache = map;
  return map;
}

/** The units line every figure prints, composed from the manifest rather than retyped. */
export function unitsLine(): string {
  const u = manifest().units;
  if (!u || !u.pressure || !u.cumulative_gas || !u.standard_conditions) {
    fail(`${MANIFEST_PATH} has no complete "units" block; every figure must print its units.`);
  }
  return (
    `Pressure and p/Z in ${u.pressure}. Cumulative gas in ${u.cumulative_gas}. ` +
    `Time in ${u.time ?? "days"}. Standard conditions: ${u.standard_conditions}.`
  );
}

/** The evidence-class line, from the manifest. */
export function evidenceClassLine(): string {
  const e = manifest().evidence_class;
  if (!e) fail(`${MANIFEST_PATH} has no "evidence_class".`);
  return `Evidence class: ${e}.`;
}

/** Provenance block for the methods page: digests, source and export identity. */
export function provenance(): {
  numericalSource: Record<string, string>;
  exportBlock: Record<string, string | number>;
  dataFileDigests: Array<{ file: string; declared: string; measured: string; match: boolean }>;
  caseSummaryDigests: Record<string, string>;
  siteBuild: Record<string, unknown>;
} {
  const m = manifest();
  if (!m.numerical_source || !m.export) {
    fail(`${MANIFEST_PATH} has no numerical_source or export block.`);
  }
  return {
    numericalSource: m.numerical_source,
    exportBlock: m.export,
    dataFileDigests: m.data_file_digests ?? [],
    caseSummaryDigests: m.case_summary_digests ?? {},
    siteBuild: m.site_build ?? {},
  };
}

/** Strip the "F01 — " prefix the generator puts on its titles. */
function stripNumber(number: string, title: string): string {
  const prefix = new RegExp(`^${number.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\$&")}\\s*[—–-]\\s*`, "i");
  const stripped = title.replace(prefix, "").trim();
  return stripped === "" ? title : stripped;
}

/** Read the `<desc>` element out of the inlined SVG. */
function descriptionOf(id: string, svg: string, file: string): string {
  const match = /<desc\b[^>]*>([\s\S]*?)<\/desc>/i.exec(svg);
  if (!match) {
    fail(
      `figure "${id}" has no <desc> element.\n` +
        `  file: ${GENERATED_DIR}${file}\n` +
        `  the long description is the figure's text alternative and cannot be derived.`,
    );
  }
  const text = (match[1] ?? "")
    .replace(/<[^>]+>/g, "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#(\d+);/g, (_, d: string) => String.fromCodePoint(Number(d)))
    .replace(/\s+/g, " ")
    .trim();
  if (text === "") fail(`figure "${id}" has an empty <desc>.\n  file: ${GENERATED_DIR}${file}`);
  return text;
}

const encoder = new TextEncoder();

/**
 * Resolve one exhibit by its manifest id, case-insensitively.
 *
 * Fails the build if the id is absent, if the SVG file the manifest names is absent, if
 * that file is not a bare `<svg>` fragment, if the manifest's recorded byte count
 * disagrees with the file, or if the caveat or accessible name is missing. All six are
 * specification errors that a reader of the deployed page could not distinguish from a
 * withdrawn exhibit.
 */
export function exhibit(figureId: string): Exhibit {
  const figures = byId();
  const entry = figures.get(figureId.toLowerCase());
  if (!entry) {
    fail(
      `no figure "${figureId}" in the manifest.\n` +
        `  manifest: ${MANIFEST_PATH}\n` +
        `  declared: ${[...figures.values()].map((f) => f.figure_id).join(", ")}`,
    );
  }

  const number = entry.figure_id;
  const svgRecord = (entry.files ?? []).find((f) => f.media_type === "image/svg+xml");
  if (!svgRecord) {
    fail(`figure "${number}" declares no image/svg+xml file in the manifest.`);
  }
  const pngRecord = (entry.files ?? []).find((f) => f.media_type === "image/png");
  const file = svgRecord.path;
  const markup = (SVGS.get(file) ?? "").trim();
  if (markup === "") {
    fail(
      `figure "${number}" is declared in the manifest but its SVG is missing.\n` +
        `  expected at: ${GENERATED_DIR}${file}\n` +
        `  present: ${[...SVGS.keys()].join(", ")}\n` +
        `  run: ${RUN_FIGURES}`,
    );
  }
  if (!markup.startsWith("<svg")) {
    fail(
      `figure "${number}" does not begin with an <svg> element.\n` +
        `  file: ${GENERATED_DIR}${file}\n` +
        `  it is inlined into the page, so it must be a bare SVG fragment.`,
    );
  }
  /* The generator records the length of the SVG text itself; the file on disk carries one
     further byte because the writer appends a newline. Compare like with like. */
  const bytes = encoder.encode(markup).length;
  if (typeof svgRecord.bytes === "number" && svgRecord.bytes !== bytes) {
    fail(
      `figure "${number}" is stale.\n` +
        `  manifest records: ${svgRecord.bytes} B\n` +
        `  file on disk:     ${bytes} B\n` +
        `  file: ${GENERATED_DIR}${file}\n` +
        `  run: ${RUN_FIGURES}`,
    );
  }

  const accessibleName = entry.accessibility?.accessible_name;
  if (!accessibleName) {
    fail(`figure "${number}" has no accessibility.accessible_name; it is the SVG's accessible name.`);
  }
  const caveat = entry.caveat;
  if (!caveat) fail(`figure "${number}" has no caveat. Every exhibit on this site prints one.`);

  return {
    id: number.toLowerCase(),
    number,
    title: stripNumber(number, accessibleName),
    svg: markup,
    bytes,
    caveat,
    question: entry.question ?? "",
    longDescription: descriptionOf(number, markup, file),
    dataFiles: entry.data_files ?? [],
    selector: entry.selector ?? "",
    units: unitsLine(),
    evidenceClass: entry.evidence_class
      ? `Evidence class: ${entry.evidence_class}.`
      : evidenceClassLine(),
    svgFile: file,
    svgDownload: `/data/figures/${file}` as SitePath,
    pngFile: pngRecord?.path,
  };
}

/**
 * Resolve one exhibit and check that its published downloads are actually there.
 *
 * `exhibit()` on its own can only say that the SVG the page inlines exists. This also
 * asserts, through `requireDownload()`, that the copy under `site/public/data/figures/`
 * is there, still hashes to what the emitter recorded, and is byte-identical to the
 * canonical rendered figure this same build inlines. So the "download this figure" link
 * beside every exhibit cannot ship pointing at a file that is missing, hand-edited, or
 * left over from an earlier render.
 *
 * The raster variant is resolved the same way and returned separately. It is the same
 * drawing in a different encoding, and the fields say so: a caller that offers it must
 * name it as the raster, with its size, rather than presenting two variants as one file.
 * Pages use this; `exhibit()` remains for callers that need no download link.
 */
export async function checkedExhibit(figureId: string): Promise<Exhibit> {
  const e = exhibit(figureId);
  const svgDownload = await requireDownload(`figures/${e.svgFile}`);
  if (!e.pngFile) return { ...e, svgDownload };

  const name = `figures/${e.pngFile}`;
  const pngDownload = await requireDownload(name);
  const record = describe(name);
  if (record.figure_id !== e.number) {
    fail(
      `raster download "${name}" is registered to figure "${record.figure_id ?? "(none)"}" ` +
        `but is being offered beside "${e.number}".\n` +
        `  a download link that names one figure and serves another is worse than no link.`,
    );
  }
  return {
    ...e,
    svgDownload,
    pngDownload,
    pngSize: humanBytes(record.bytes),
    pngIdentity: record.identity,
  };
}

/** Resolve several exhibits at once, in the order given. */
export function exhibits(...ids: string[]): Record<string, Exhibit> {
  const out: Record<string, Exhibit> = {};
  for (const id of ids) out[id.toLowerCase()] = exhibit(id);
  return out;
}

/** Total inlined SVG payload of a set of exhibits, for the payload note on /methods/. */
export function inlinedBytes(...ids: string[]): number {
  return ids.reduce((total, id) => total + exhibit(id).bytes, 0);
}

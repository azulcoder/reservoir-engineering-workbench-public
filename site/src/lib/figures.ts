/**
 * Build-time loading of the generated figures and their underlying data.
 *
 * What this file guarantees
 * -------------------------
 * A page that asks for figure "f01" either gets the real SVG that
 * `scripts/render-figures.mjs` produced from `src/data/figures/*.json`, or the build
 * stops with an error naming what is missing. There is no placeholder path, no
 * "figure unavailable" box, and no silently empty `<figure>`. A case site whose whole
 * argument is that every number traces to a committed file cannot ship a page that
 * renders an absent figure as a grey rectangle: the reader would have no way to tell
 * an exhibit that was withdrawn from one that failed to build.
 *
 * Three classes of failure fail the build, each with its own message:
 *   missing     the manifest, an SVG, or a data file is not there
 *   stale       the manifest disagrees with the bytes on disk
 *   mismatched  a data file disagrees with its SHA-256 in contract.json
 *
 * Non-finite values are rejected outright. Python's `json.dump` writes `NaN`,
 * `Infinity` and `-Infinity` as bare tokens unless `allow_nan=False` is passed. Those
 * tokens are not valid JSON, and `JSON.parse` rejects them with a message that names a
 * column rather than the problem, so the raw text is scanned first and the parsed tree
 * is walked afterwards. The second pass reports the JSON pointer of the offending
 * value.
 *
 * Why Vite globs and Web Crypto rather than node:fs and node:crypto
 * ----------------------------------------------------------------
 * `@types/node` is not a dependency of this site, so a module importing `node:fs`
 * type-checks nowhere -- `astro check` reports TS2591 on every such import. Vite's
 * `import.meta.glob` and the Web Crypto `crypto.subtle` are both typed by
 * `astro/client`, which the project's tsconfig already references, and both run at
 * build time in exactly the same Node process. The globs are eager and raw, so the
 * file contents are inlined into the prerender module and never reach the client.
 *
 * One consequence worth knowing: an eager glob is resolved when the module is
 * transformed. `npm run build` runs `render-figures.mjs` before `astro build`, so the
 * files are there. In `astro dev`, regenerating the figures needs a dev-server restart
 * before the new manifest is seen.
 *
 * The manifest shape
 * ------------------
 * The manifest is written by a different stream than this loader. The contract is
 * below; where the generator might reasonably pick a different spelling (snake_case
 * from a Python-flavoured pipeline, `file` instead of `svg`), the reader accepts the
 * alias and normalises it. Forgiving about spelling, strict about content.
 *
 *   src/generated/figures/manifest.json
 *   {
 *     "figures": [
 *       {
 *         "id": "f01",                                  required
 *         "title": "The fit that looks right",          required
 *         "svg": "f01.svg",                             optional, defaults to "<id>.svg"
 *         "bytes": 48213,                               optional, checked if present
 *         "shortDescription": "...",                    optional
 *         "interpretation": "...",                      optional
 *         "caveat": "...",                              optional
 *         "units": "...",                               optional
 *         "dataFile": "f01_f02_scenarios.json",         optional, checked if present
 *         "dataSha256": "dd3d8d..."                     optional, checked if present
 *       }
 *     ]
 *   }
 *
 * A bare array and an object keyed by figure id are also accepted. Any other shape is
 * rejected with the expected form printed.
 */

/* ------------------------------------------------------------------------- *
 * Build-time file access
 * ------------------------------------------------------------------------- */

/** Written by scripts/render-figures.mjs (npm run figures). Not committed. */
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

/** Written by scripts/export_presentation_data.py. Committed. */
const DATA_RAW = import.meta.glob("../data/figures/*.json", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

/** Display paths for error messages, relative to the repository root. */
export const MANIFEST_PATH = "site/src/generated/figures/manifest.json";
export const GENERATED_DIR = "site/src/generated/figures/";
export const DATA_DIR = "site/src/data/figures/";
export const CONTRACT_PATH = `${DATA_DIR}contract.json`;

const RUN_FIGURES = "npm run figures  (node scripts/render-figures.mjs)";

/** Reduce a glob key such as "../data/figures/f01.json" to "f01.json". */
function basename(key: string): string {
  const cut = key.lastIndexOf("/");
  return cut === -1 ? key : key.slice(cut + 1);
}

function byName(glob: Record<string, string>): Map<string, string> {
  return new Map(Object.entries(glob).map(([key, text]) => [basename(key), text]));
}

const SVGS = byName(SVG_RAW);
const DATA = byName(DATA_RAW);

/* ------------------------------------------------------------------------- *
 * Types
 * ------------------------------------------------------------------------- */

/** One manifest entry, after normalisation. */
export interface FigureEntry {
  /** Figure identifier, e.g. "f01". Unique across the manifest. */
  id: string;
  /** Accessible name of the SVG and the heading of the figure block. */
  title: string;
  /** File name of the SVG inside src/generated/figures/. */
  svg: string;
  /** Byte length the generator measured. Checked against the file. */
  bytes?: number;
  /** One or two sentences: what the figure is and where the long description lives. */
  shortDescription?: string;
  /** The figure's key caveat, per docs/design/figure_spec.md. */
  caveat?: string;
  /** Units and standard-condition basis line. */
  units?: string;
  /** One-sentence interpretation. */
  interpretation?: string;
  /** Source data file name inside src/data/figures/. */
  dataFile?: string;
  /** SHA-256 of that data file, as the generator recorded it. */
  dataSha256?: string;
  /** Anything else the generator recorded. Carried through untouched. */
  extra: Readonly<Record<string, unknown>>;
}

/** A resolved figure: the manifest entry plus the SVG markup itself. */
export interface LoadedFigure extends FigureEntry {
  /** Inline SVG markup, ready for `set:html`. */
  svgMarkup: string;
  /** Measured byte length of that markup. */
  svgBytes: number;
}

export interface ContractFileEntry {
  figure_data: string;
  path: string;
  sha256: string;
}

export interface Contract {
  contract_version: string;
  case_id: string;
  numerical_source: Record<string, string>;
  export: Record<string, string | number>;
  units: Record<string, string>;
  evidence_class: string;
  files: ContractFileEntry[];
}

/* ------------------------------------------------------------------------- *
 * Errors
 * ------------------------------------------------------------------------- */

/** Every failure in this module is this class, so a build log is unambiguous. */
export class FigureDataError extends Error {
  constructor(message: string) {
    super(`[figures] ${message}`);
    this.name = "FigureDataError";
  }
}

function fail(message: string): never {
  throw new FigureDataError(message);
}

/* ------------------------------------------------------------------------- *
 * Bytes and hashes, without node builtins
 * ------------------------------------------------------------------------- */

const encoder = new TextEncoder();

/** UTF-8 byte length of a string, which is the on-disk size of a UTF-8 text file. */
export function byteLength(text: string): number {
  return encoder.encode(text).length;
}

/** Lowercase hex SHA-256 of a string's UTF-8 bytes. Matches `shasum -a 256 <file>`. */
export async function sha256(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(text));
  return [...new Uint8Array(digest)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/* ------------------------------------------------------------------------- *
 * JSON reading, with non-finite rejection
 * ------------------------------------------------------------------------- */

/**
 * Bare non-finite tokens as a JSON serialiser would emit them: after a ":", a "," or a
 * "[", and not inside a string. The pre-scan can only produce a clearer message than
 * `JSON.parse` would, never a different verdict, because `JSON.parse` rejects these
 * tokens anyway.
 */
const NON_FINITE_TOKEN = /(?:^|[:,[\s])(-?Infinity|NaN)\s*(?=[,\]}\s]|$)/;

/** Walk a parsed value and report the JSON pointer of the first non-finite number. */
function findNonFinite(value: unknown, pointer: string): string | null {
  if (typeof value === "number") {
    return Number.isFinite(value) ? null : `${pointer || "/"} = ${String(value)}`;
  }
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i += 1) {
      const hit = findNonFinite(value[i], `${pointer}/${i}`);
      if (hit) return hit;
    }
    return null;
  }
  if (value && typeof value === "object") {
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      const key = k.replace(/~/g, "~0").replace(/\//g, "~1");
      const hit = findNonFinite(v, `${pointer}/${key}`);
      if (hit) return hit;
    }
  }
  return null;
}

/**
 * Parse JSON text, rejecting NaN and Infinity in either form.
 *
 * `JSON.parse` cannot produce a non-finite number from conforming input, so the second
 * check exists for a value arriving by some other route, and so that the guarantee is
 * stated in one place rather than inferred from the grammar.
 */
export function parseJsonStrict<T = unknown>(text: string, label: string, path: string): T {
  const token = NON_FINITE_TOKEN.exec(text);
  if (token) {
    fail(
      `${label} contains the non-finite JSON token "${token[1]}".\n` +
        `  file: ${path}\n` +
        `  JSON has no NaN or Infinity. Re-export with allow_nan=False and fix the\n` +
        `  quantity that went non-finite; do not serialise it as null.`,
    );
  }
  let parsed: T;
  try {
    parsed = JSON.parse(text) as T;
  } catch (error) {
    fail(`${label} is not valid JSON.\n  file: ${path}\n  ${(error as Error).message}`);
  }
  const bad = findNonFinite(parsed, "");
  if (bad) {
    fail(`${label} contains a non-finite number.\n  file: ${path}\n  at ${bad}`);
  }
  return parsed;
}

/* ------------------------------------------------------------------------- *
 * Manifest normalisation
 * ------------------------------------------------------------------------- */

function pick(record: Record<string, unknown>, ...names: string[]): unknown {
  for (const name of names) {
    if (record[name] !== undefined && record[name] !== null) return record[name];
  }
  return undefined;
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() !== "" ? value.trim() : undefined;
}

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

const ALIASES = {
  id: ["id", "figure", "figure_id", "figureId", "key"],
  title: ["title", "label", "name", "heading"],
  svg: ["svg", "svgFile", "svg_file", "file", "path", "filename"],
  bytes: ["bytes", "byteLength", "byte_length", "size"],
  shortDescription: ["shortDescription", "short_description", "description", "shortDesc"],
  caveat: ["caveat", "caveat_text", "caveats"],
  units: ["units", "unitsNote", "units_note"],
  interpretation: ["interpretation", "finding", "findingLine", "finding_line"],
  dataFile: ["dataFile", "data_file", "data", "source", "sourceFile", "source_file"],
  dataSha256: ["dataSha256", "data_sha256", "sha256"],
} as const;

const KNOWN_KEYS = new Set<string>(Object.values(ALIASES).flat());

/**
 * Accept the three manifest shapes a reasonable generator might write, and reject
 * anything else with the expected form printed.
 *
 *   { "figures": [ {...}, {...} ] }     preferred
 *   [ {...}, {...} ]                    a bare list
 *   { "f01": {...}, "f02": {...} }      a map keyed by id
 */
function normaliseManifest(raw: unknown): FigureEntry[] {
  let list: unknown[];
  if (Array.isArray(raw)) {
    list = raw;
  } else if (raw && typeof raw === "object") {
    const obj = raw as Record<string, unknown>;
    const figures = pick(obj, "figures", "entries", "items");
    if (Array.isArray(figures)) {
      list = figures;
    } else {
      const values = Object.entries(obj).filter(([, v]) => v && typeof v === "object");
      if (values.length === 0) {
        fail(
          `manifest.json has no figures.\n` +
            `  file: ${MANIFEST_PATH}\n` +
            `  expected {"figures": [{"id": "f01", "title": "...", "svg": "f01.svg"}, ...]}\n` +
            `  run: ${RUN_FIGURES}`,
        );
      }
      list = values.map(([key, value]) => ({
        id: key,
        ...(value as Record<string, unknown>),
      }));
    }
  } else {
    fail(
      `manifest.json is neither an object nor an array.\n` +
        `  file: ${MANIFEST_PATH}\n` +
        `  run: ${RUN_FIGURES}`,
    );
  }

  if (list.length === 0) {
    fail(
      `manifest.json lists zero figures.\n  file: ${MANIFEST_PATH}\n  run: ${RUN_FIGURES}`,
    );
  }

  const seen = new Map<string, number>();
  return list.map((item, index) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      fail(`manifest.json entry ${index} is not an object.\n  file: ${MANIFEST_PATH}`);
    }
    const record = item as Record<string, unknown>;

    const id = asString(pick(record, ...ALIASES.id));
    if (!id) {
      fail(
        `manifest.json entry ${index} has no "id".\n` +
          `  file: ${MANIFEST_PATH}\n` +
          `  every entry needs at least id and title.`,
      );
    }
    if (seen.has(id)) {
      fail(
        `manifest.json declares figure "${id}" twice, at entries ${seen.get(id)} and ` +
          `${index}.\n  file: ${MANIFEST_PATH}`,
      );
    }
    seen.set(id, index);

    const title = asString(pick(record, ...ALIASES.title));
    if (!title) {
      fail(
        `manifest.json figure "${id}" has no "title".\n` +
          `  file: ${MANIFEST_PATH}\n` +
          `  the title is the SVG's accessible name; it cannot be derived.`,
      );
    }

    const extra: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(record)) {
      if (!KNOWN_KEYS.has(k)) extra[k] = v;
    }

    const entry: FigureEntry = {
      id,
      title,
      svg: (asString(pick(record, ...ALIASES.svg)) ?? `${id}.svg`).replace(/^\.?\//, ""),
      extra: Object.freeze(extra),
    };

    const bytes = asNumber(pick(record, ...ALIASES.bytes));
    if (bytes !== undefined) entry.bytes = bytes;
    const shortDescription = asString(pick(record, ...ALIASES.shortDescription));
    if (shortDescription) entry.shortDescription = shortDescription;
    const caveat = asString(pick(record, ...ALIASES.caveat));
    if (caveat) entry.caveat = caveat;
    const units = asString(pick(record, ...ALIASES.units));
    if (units) entry.units = units;
    const interpretation = asString(pick(record, ...ALIASES.interpretation));
    if (interpretation) entry.interpretation = interpretation;
    const dataFile = asString(pick(record, ...ALIASES.dataFile));
    if (dataFile) entry.dataFile = dataFile.replace(/^\.?\//, "");
    const dataSha256 = asString(pick(record, ...ALIASES.dataSha256));
    if (dataSha256) entry.dataSha256 = dataSha256.toLowerCase();
    return entry;
  });
}

/* ------------------------------------------------------------------------- *
 * The contract
 * ------------------------------------------------------------------------- */

let contractCache: Contract | undefined;

/**
 * The export contract. Committed, so its absence is a repository error rather than a
 * stale build, and the message says so.
 */
export function loadContract(): Contract {
  if (!contractCache) {
    const text = DATA.get("contract.json");
    if (text === undefined) {
      fail(
        `contract.json is missing.\n` +
          `  expected at: ${CONTRACT_PATH}\n` +
          `  it is a committed file, not a build artifact. This is a checkout problem.`,
      );
    }
    const parsed = parseJsonStrict<Contract>(text, "contract.json", CONTRACT_PATH);
    if (!Array.isArray(parsed.files) || parsed.files.length === 0) {
      fail(`contract.json has no "files" list.\n  file: ${CONTRACT_PATH}`);
    }
    contractCache = parsed;
  }
  return contractCache;
}

/* ------------------------------------------------------------------------- *
 * Validation
 * ------------------------------------------------------------------------- */

/**
 * `emit()` in scripts/render-figures.mjs reports `Buffer.byteLength(svgText)` but
 * writes `svgText + "\n"`, so the file on disk is one byte longer than the count the
 * generator has in hand. Both are accepted; anything else is stale.
 */
function bytesAgree(declared: number, text: string): boolean {
  const actual = byteLength(text);
  return declared === actual || declared === byteLength(text.replace(/\s+$/, ""));
}

async function validate(entries: FigureEntry[]): Promise<Map<string, FigureEntry>> {
  const contract = loadContract();
  const contractByPath = new Map(contract.files.map((f) => [f.path, f]));
  const out = new Map<string, FigureEntry>();

  for (const entry of entries) {
    const svgText = SVGS.get(entry.svg);
    if (svgText === undefined) {
      fail(
        `figure "${entry.id}" names an SVG that does not exist.\n` +
          `  expected at: ${GENERATED_DIR}${entry.svg}\n` +
          `  present: ${[...SVGS.keys()].join(", ") || "(none)"}\n` +
          `  run: ${RUN_FIGURES}`,
      );
    }
    if (svgText.trim() === "") {
      fail(
        `figure "${entry.id}" has an empty SVG file.\n` +
          `  file: ${GENERATED_DIR}${entry.svg}\n  run: ${RUN_FIGURES}`,
      );
    }
    if (entry.bytes !== undefined && !bytesAgree(entry.bytes, svgText)) {
      fail(
        `figure "${entry.id}" is stale: the manifest records ${entry.bytes} bytes but ` +
          `the file\n  on disk is ${byteLength(svgText)} bytes.\n` +
          `  file: ${GENERATED_DIR}${entry.svg}\n` +
          `  the SVG changed without the manifest being rewritten. run: ${RUN_FIGURES}`,
      );
    }

    if (entry.dataFile) {
      const dataText = DATA.get(entry.dataFile);
      if (dataText === undefined) {
        fail(
          `figure "${entry.id}" names data file "${entry.dataFile}", which does not ` +
            `exist.\n  expected at: ${DATA_DIR}${entry.dataFile}\n` +
            `  the exporter is scripts/export_presentation_data.py.`,
        );
      }
      const declared = contractByPath.get(entry.dataFile);
      if (!declared) {
        fail(
          `figure "${entry.id}" names data file "${entry.dataFile}", which ` +
            `contract.json does not list.\n` +
            `  declared: ${contract.files.map((f) => f.path).join(", ")}\n` +
            `  a figure drawn from an undeclared file has no provenance chain.`,
        );
      }
      const actualSha = await sha256(dataText);
      if (actualSha !== declared.sha256) {
        fail(
          `data file "${entry.dataFile}" does not match contract.json.\n` +
            `  contract.json sha256: ${declared.sha256}\n` +
            `  file on disk sha256:  ${actualSha}\n` +
            `  file: ${DATA_DIR}${entry.dataFile}\n` +
            `  re-run scripts/export_presentation_data.py; do not edit the export by hand.`,
        );
      }
      if (entry.dataSha256 && entry.dataSha256 !== actualSha) {
        fail(
          `figure "${entry.id}" is stale: the manifest records sha256 ` +
            `${entry.dataSha256}\n  for "${entry.dataFile}" but the file is ` +
            `${actualSha}.\n  run: ${RUN_FIGURES}`,
        );
      }
    }

    out.set(entry.id, entry);
  }
  return out;
}

/* ------------------------------------------------------------------------- *
 * Public API
 * ------------------------------------------------------------------------- */

let manifestCache: Promise<Map<string, FigureEntry>> | undefined;

/** Load, normalise and validate the manifest. Cached for the life of the build. */
export function loadManifest(): Promise<ReadonlyMap<string, FigureEntry>> {
  if (!manifestCache) {
    manifestCache = (async () => {
      const key = Object.keys(MANIFEST_RAW)[0];
      const text = key === undefined ? undefined : MANIFEST_RAW[key];
      if (text === undefined) {
        fail(
          `the generated figure manifest is missing.\n` +
            `  expected at: ${MANIFEST_PATH}\n` +
            `  it is produced at build time and is not committed.\n` +
            `  run: ${RUN_FIGURES}\n` +
            `  (in astro dev, restart the dev server after regenerating the figures.)`,
        );
      }
      return validate(
        normaliseManifest(parseJsonStrict(text, "manifest.json", MANIFEST_PATH)),
      );
    })();
  }
  return manifestCache;
}

/** Every figure id the manifest declares, in manifest order. */
export async function figureIds(): Promise<string[]> {
  return [...(await loadManifest()).keys()];
}

/** True when the manifest file is present. Does not validate it; diagnostics only. */
export function manifestExists(): boolean {
  return Object.keys(MANIFEST_RAW).length > 0;
}

/**
 * Load one figure by id, with its SVG markup.
 *
 * Fails the build if the id is absent, naming the ids that do exist. A page asking for
 * a figure the generator did not draw is a specification error, and a placeholder
 * would hide it until somebody read the deployed page.
 */
export async function loadFigure(id: string): Promise<LoadedFigure> {
  const manifest = await loadManifest();
  const entry = manifest.get(id);
  if (!entry) {
    fail(
      `no figure "${id}" in the manifest.\n` +
        `  manifest: ${MANIFEST_PATH}\n` +
        `  declared figures: ${[...manifest.keys()].join(", ") || "(none)"}\n` +
        `  either the page asks for the wrong id, or scripts/render-figures.mjs does\n` +
        `  not draw it.`,
    );
  }
  const svgMarkup = (SVGS.get(entry.svg) ?? "").trim();
  if (!svgMarkup.startsWith("<svg")) {
    fail(
      `figure "${id}" does not begin with an <svg> element.\n` +
        `  file: ${GENERATED_DIR}${entry.svg}\n` +
        `  it is inlined into the page, so it must be a bare SVG fragment with no XML\n` +
        `  prolog and no doctype.`,
    );
  }
  return { ...entry, svgMarkup, svgBytes: byteLength(svgMarkup) };
}

/**
 * Load one exported data file by name, checked against contract.json and rejected if
 * it carries a non-finite value.
 */
export async function loadFigureData<T = unknown>(fileName: string): Promise<T> {
  const name = fileName.endsWith(".json") ? fileName : `${fileName}.json`;
  const text = DATA.get(name);
  if (text === undefined) {
    fail(
      `figure data "${name}" is missing.\n` +
        `  expected at: ${DATA_DIR}${name}\n` +
        `  present: ${[...DATA.keys()].join(", ")}`,
    );
  }
  const parsed = parseJsonStrict<T>(text, `figure data "${name}"`, `${DATA_DIR}${name}`);
  if (name === "contract.json") return parsed;

  const contract = loadContract();
  const declared = contract.files.find((f) => f.path === name);
  if (!declared) {
    fail(
      `figure data "${name}" is not declared in contract.json.\n` +
        `  declared: ${contract.files.map((f) => f.path).join(", ")}`,
    );
  }
  const actual = await sha256(text);
  if (actual !== declared.sha256) {
    fail(
      `figure data "${name}" does not match contract.json.\n` +
        `  contract.json sha256: ${declared.sha256}\n` +
        `  file on disk sha256:  ${actual}\n` +
        `  re-run scripts/export_presentation_data.py.`,
    );
  }
  return parsed;
}

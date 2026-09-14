/**
 * Build-time verification of the downloadable files under `site/public/data/`.
 *
 * A download link is a claim: that the file is there, that it carries the numbers the
 * page shows, and -- for a figure -- that it is the drawing the page displays. All three
 * are checked here, at build time, for every file a page links.
 *
 *   - Presence. `requireDownload()` fails the build when the named file is absent from
 *     `site/public/data/`. A completed case does not ship a link to a file that is not
 *     there, and it does not degrade to a "download coming soon" note either.
 *   - Integrity. `site/src/scripts/emit-public-data.mjs` records the byte length and the
 *     SHA-256 of everything it wrote in `index.json`. This module re-hashes the bytes on
 *     disk and fails on any disagreement, so a hand-edited or stale download cannot ship
 *     under a name that implies it came from the committed export.
 *   - Identity. For a published SVG, the bytes on disk are compared with the canonical
 *     rendered figure in `site/src/generated/figures/` -- the file this same build
 *     inlines into the page. This is the check that was missing: the index claimed each
 *     copy was byte-identical to the inlined figure, and nothing compared the two, so a
 *     re-rendered figure and its stale published copy both matched a stale digest and
 *     the build stayed green. The comparison is byte identity, not a normalised or
 *     whitespace-insensitive one, because byte identity is what the contract says.
 *
 * What this module cannot check, and who does
 * -------------------------------------------
 * The published PNGs are binary. `import.meta.glob` can hand this module text, so the
 * rasters' identity is enforced where the bytes are readable as bytes:
 * `node src/scripts/emit-public-data.mjs --verify`, a mandatory step of
 * `scripts/build_release.py`, which re-emits the whole tree and compares it with what is
 * published. That is stated rather than papered over: `describe()` still fails the build
 * on an unindexed raster, and `dataIndex()` reports the raster payload separately from
 * the files this module re-hashes, so no page can print a scope claim wider than what
 * was actually done here.
 *
 * The digests are computed with Web Crypto rather than `node:crypto` for the same reason
 * `src/lib/figures.ts` does: `@types/node` is not a dependency of this site, so a module
 * importing a node builtin fails `astro check` on every line that touches it.
 */

import { assetHref, type SitePath } from "../lib/urls";

const RAW = import.meta.glob("../../public/data/**/*.{csv,json,svg}", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

/** The canonical rendered figures: what the page inlines, and what a download copies. */
const CANONICAL_SVG = import.meta.glob("../generated/figures/*.svg", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

const PUBLIC_DIR = "site/public/data/";
const GENERATED_DIR = "site/src/generated/figures/";
const REGENERATE = "node src/scripts/emit-public-data.mjs   (from site/)";
const VERIFY = "node src/scripts/emit-public-data.mjs --verify   (from site/)";

/** Reduce "../../public/data/figures/f01.svg" to "figures/f01.svg". */
function relativeName(key: string): string {
  const marker = "/public/data/";
  const cut = key.indexOf(marker);
  return cut === -1 ? key : key.slice(cut + marker.length);
}

const FILES = new Map(Object.entries(RAW).map(([k, v]) => [relativeName(k), v]));

/** Reduce "../generated/figures/f01.svg" to "f01.svg". */
function baseName(key: string): string {
  const cut = key.lastIndexOf("/");
  return cut === -1 ? key : key.slice(cut + 1);
}

const CANONICAL = new Map(Object.entries(CANONICAL_SVG).map(([k, v]) => [baseName(k), v]));

export class PublicDataError extends Error {
  constructor(message: string) {
    super(`[public-data] ${message}`);
    this.name = "PublicDataError";
  }
}

function fail(message: string): never {
  throw new PublicDataError(message);
}

const encoder = new TextEncoder();

/** UTF-8 byte length, which is the on-disk size of a UTF-8 text file. */
function byteLength(text: string): number {
  return encoder.encode(text).length;
}

async function sha256(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export interface IndexedFile {
  name: string;
  /**
   * `full` and `selected` are the numbers: the whole dataset, or one chosen case.
   * `exhibit` is a figure's canonical vector. `exhibit-raster` is the same drawing as a
   * PNG -- a download only, never part of a page payload.
   */
  kind: "full" | "selected" | "exhibit" | "exhibit-raster";
  description: string;
  bytes: number;
  sha256: string;
  /** Figure artefacts only: which variant of which figure this file is. */
  variant?: "canonical-vector" | "raster-export";
  figure_id?: string;
  media_type?: string;
  /** The canonical rendered file this is a copy of, and its digest. */
  source_path?: string;
  source_sha256?: string;
  /** What this file is identical to, in words, so a link cannot overclaim. */
  identity?: string;
  renderer_sha256?: string;
  numerical_run_id?: string | null;
  data_files?: string[];
}

interface DataIndex {
  generator: string;
  sources: string[];
  evidence_class: string;
  csv_precision: string;
  excluded: string;
  chain?: {
    links: string[];
    enforced_by: string;
    inline_transform: string;
    variants: string;
  };
  raster_payload?: { files: number; bytes: number; note: string };
  files: IndexedFile[];
}

let indexCache: DataIndex | undefined;

function index(): DataIndex {
  if (indexCache) return indexCache;
  const text = FILES.get("index.json");
  if (text === undefined) {
    fail(
      `index.json is missing.\n` +
        `  expected at: ${PUBLIC_DIR}index.json\n` +
        `  it is the record of what the downloads are and what they hash to.\n` +
        `  run: ${REGENERATE}`,
    );
  }
  let parsed: DataIndex;
  try {
    parsed = JSON.parse(text) as DataIndex;
  } catch (error) {
    fail(`${PUBLIC_DIR}index.json is not valid JSON.\n  ${(error as Error).message}`);
  }
  if (!Array.isArray(parsed.files) || parsed.files.length === 0) {
    fail(`${PUBLIC_DIR}index.json lists no files.\n  run: ${REGENERATE}`);
  }
  indexCache = parsed;
  return parsed;
}

/** What `emit-public-data.mjs` recorded about one file. */
export function describe(name: string): IndexedFile {
  const record = index().files.find((f) => f.name === name);
  if (!record) {
    fail(
      `"${name}" is not in ${PUBLIC_DIR}index.json.\n` +
        `  indexed: ${index().files.map((f) => f.name).join(", ")}\n` +
        `  run: ${REGENERATE}`,
    );
  }
  return record;
}

/**
 * Compare a published figure with the canonical rendered file it claims to copy.
 *
 * Byte identity, in both directions, with no normalisation: the index says
 * "byte-identical" and this is the check behind that word. The one transformation the
 * site performs is stated in `index.json`'s `chain.inline_transform` and applied in
 * `exhibits.ts` -- the inlined copy is trimmed of leading and trailing whitespace and is
 * otherwise untouched -- so the comparison here is against the untrimmed file and the
 * trim is proved separately, against the built HTML, by `scripts/build_release.py`.
 */
async function requireCanonicalIdentity(name: string, published: string, record: IndexedFile) {
  const file = name.slice("figures/".length);
  const canonical = CANONICAL.get(file);
  if (canonical === undefined) {
    fail(
      `published figure "${name}" has no canonical source.\n` +
        `  expected at: ${GENERATED_DIR}${file}\n` +
        `  present: ${[...CANONICAL.keys()].sort().join(", ") || "(none)"}\n` +
        `  a download with nothing behind it is a file, not an exhibit.\n` +
        `  run: npm run figures`,
    );
  }
  if (published !== canonical) {
    const [a, b] = await Promise.all([sha256(published), sha256(canonical)]);
    fail(
      `published figure "${name}" is not the drawing this build displays.\n` +
        `  published: ${PUBLIC_DIR}${name} — ${byteLength(published)} B, sha256 ${a}\n` +
        `  canonical: ${GENERATED_DIR}${file} — ${byteLength(canonical)} B, sha256 ${b}\n` +
        `  index.json describes this copy as byte-identical to the file the page inlines.\n` +
        `  It is not. The figure was re-rendered and the download was not re-emitted, or\n` +
        `  the download was edited. Do not normalise the difference away.\n` +
        `  run: ${REGENERATE}`,
    );
  }
  if (record.source_sha256 !== undefined) {
    const measured = await sha256(canonical);
    if (record.source_sha256 !== measured) {
      fail(
        `published figure "${name}" records a stale source digest.\n` +
          `  index.json source_sha256: ${record.source_sha256}\n` +
          `  ${GENERATED_DIR}${file}:   ${measured}\n` +
          `  the published copy and its index entry agree with each other and not with\n` +
          `  the figure they came from, which is exactly the drift a digest alone cannot see.\n` +
          `  run: ${REGENERATE}`,
      );
    }
  }
}

/**
 * Assert a download exists and matches its recorded digest, and return the site path to
 * link it with. Every download link on this site goes through here.
 */
export async function requireDownload(name: string): Promise<SitePath> {
  const record = describe(name);

  /* A raster is binary: `import.meta.glob` cannot hand this module its bytes, so it is
     not re-hashed here and this module does not pretend otherwise. Its presence, its
     provenance and its byte identity with the canonical PNG are enforced by
     `emit-public-data.mjs --verify`, which reads real bytes and is a mandatory step of
     scripts/build_release.py. */
  if (record.kind === "exhibit-raster") {
    if (!record.source_path || !record.source_sha256) {
      fail(
        `raster download "${name}" has no recorded source.\n` +
          `  a published raster carries the canonical file it came from and that file's digest.\n` +
          `  run: ${REGENERATE}\n` +
          `  then check the bytes, which this module cannot read: ${VERIFY}`,
      );
    }
    return `/data/${name}` as SitePath;
  }

  const text = FILES.get(name);
  if (text === undefined) {
    fail(
      `download "${name}" is missing.\n` +
        `  expected at: ${PUBLIC_DIR}${name}\n` +
        `  present: ${[...FILES.keys()].sort().join(", ")}\n` +
        `  run: ${REGENERATE}`,
    );
  }
  const measured = await sha256(text);
  if (measured !== record.sha256) {
    fail(
      `download "${name}" does not match its recorded digest.\n` +
        `  index.json sha256: ${record.sha256}\n` +
        `  file on disk:      ${measured}\n` +
        `  file: ${PUBLIC_DIR}${name}\n` +
        `  run: ${REGENERATE}`,
    );
  }
  if (name.startsWith("figures/") && name.endsWith(".svg")) {
    await requireCanonicalIdentity(name, text, record);
  }
  return `/data/${name}` as SitePath;
}

/** A download with its link, its size and the sentence that says what it is. */
export interface Download extends IndexedFile {
  /** Site path, for a component that rebases it itself — `Figure.astro`, for one. */
  path: SitePath;
  /**
   * The URL to write into an `href`, already rebased through `src/lib/urls.ts`. A raw
   * `/data/...` in a template fails the layout's URL audit, which is the point of it.
   */
  href: string;
  /** Human-readable size, e.g. "45.2 kB". */
  size: string;
}

export function humanBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_000_000) return `${(bytes / 1000).toFixed(1)} kB`;
  return `${(bytes / 1_000_000).toFixed(1)} MB`;
}

/** Resolve a download for rendering: path, digest, size and description together. */
export async function download(name: string): Promise<Download> {
  const path = await requireDownload(name);
  const record = describe(name);
  return { ...record, path, href: assetHref(path), size: humanBytes(record.bytes) };
}

/** Resolve several downloads in order. */
export async function downloads(...names: string[]): Promise<Download[]> {
  return Promise.all(names.map(download));
}

/** Parse one indexed JSON download, after checking its digest. */
export async function readJson<T>(name: string): Promise<T> {
  await requireDownload(name);
  const text = FILES.get(name) as string;
  return JSON.parse(text) as T;
}

/**
 * The index's provenance block, for the methods page.
 *
 * `count` and `bytes` cover the text and vector downloads: the files this module reads
 * and re-hashes during the build, which is what a page may claim was re-hashed here. The
 * rasters are reported separately in `rasters`, because they are neither re-hashed here
 * nor part of any page payload, and folding them into one total would overstate both
 * claims at once.
 */
export function dataIndex(): Omit<DataIndex, "files"> & {
  count: number;
  bytes: number;
  rasters: { count: number; bytes: number; note: string };
  total: { count: number; bytes: number };
} {
  const i = index();
  const rasters = i.files.filter((f) => f.kind === "exhibit-raster");
  const rest = i.files.filter((f) => f.kind !== "exhibit-raster");
  const sum = (files: IndexedFile[]) => files.reduce((a, f) => a + f.bytes, 0);
  return {
    generator: i.generator,
    sources: i.sources,
    evidence_class: i.evidence_class,
    csv_precision: i.csv_precision,
    excluded: i.excluded,
    chain: i.chain,
    raster_payload: i.raster_payload,
    count: rest.length,
    bytes: sum(rest),
    rasters: {
      count: rasters.length,
      bytes: sum(rasters),
      note:
        i.raster_payload?.note ??
        "Downloads only. Nothing on the site inlines, embeds or preloads them.",
    },
    total: { count: i.files.length, bytes: sum(i.files) },
  };
}

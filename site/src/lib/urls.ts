/**
 * Every URL on this site is built here. Nothing else may construct one.
 *
 * Why this file exists
 * --------------------
 * The deployment target is configuration, not a constant: `astro.config.mjs` reads
 * `SITE_URL` and `SITE_BASE` from the environment, so the same source has to serve a
 * root deployment (`base = "/"`) and a GitHub *project* deployment
 * (`base = "/reservoir-engineering-workbench-public/"`). Under a non-root base, a raw
 * `href="/methods/"` in a template resolves to the wrong origin path and 404s. That
 * class of bug does not show up in a local preview at root, which is exactly why it
 * survives review.
 *
 * THE RULE
 * --------
 *   Never write a leading-slash URL directly in a template.
 *
 *     <a href="/methods/">             WRONG -- breaks under a non-root base
 *     <a href={href("/methods/")}>     RIGHT
 *
 * The rule is enforced three ways, not just documented:
 *
 *   1. Types. `href()` accepts only a `SitePath` -- a template-literal type that a
 *      string must begin with "/" to satisfy. `href("methods/")` is a compile error
 *      under `astro check`, and so is `href(someWideString)` without a cast.
 *   2. Registration. Every URL this module returns is recorded in a module-level set.
 *   3. Audit. `auditHtmlUrls()` scans rendered HTML for internal `href`/`src` values
 *      that were never registered, and `BaseLayout.astro` runs it over every page it
 *      renders. A raw "/foo" written by hand fails the build with the offending
 *      attribute quoted. This bites at root base too, which is the point: the check
 *      must fail on the developer's machine, not only on the deployed project site.
 *
 * No username, repository owner or domain appears anywhere in this file. When
 * `SITE_URL` is unset, `absoluteUrl()` returns `undefined` and the caller omits the
 * canonical link and the Open Graph block entirely rather than inventing an origin.
 */

/**
 * A site-relative path. It must start with "/" and is written as it would appear on a
 * root deployment; `href()` rebases it. The type makes the leading slash mandatory so
 * that a relative path cannot be passed by accident.
 */
export type SitePath = `/${string}`;

/**
 * Astro sets `BASE_URL` from the `base` config and normalises it to have a trailing
 * slash. Default is "/". Read once so that the value is stable across a render.
 */
export const BASE: string = normaliseBase(import.meta.env.BASE_URL ?? "/");

/**
 * Astro sets `SITE` from the `site` config. It is `undefined` when `SITE_URL` was not
 * supplied to the build, and in that case this site has no absolute identity: no
 * canonical link, no Open Graph, no sitemap entry, no absolute image URL.
 */
export const SITE: string | undefined = normaliseSite(
  (import.meta.env as Record<string, unknown>).SITE as string | undefined,
);

/** True when the build has a real origin configured. */
export const HAS_SITE_URL: boolean = SITE !== undefined;

/** Extensions that mark a path as a file rather than a page route. */
const FILE_EXTENSION = /\.[a-z0-9]{2,5}$/i;

/** Every URL handed out by this module, for the audit in `auditHtmlUrls`. */
const issued = new Set<string>();

function normaliseBase(raw: string): string {
  let b = raw.trim();
  if (b === "") b = "/";
  if (!b.startsWith("/")) b = `/${b}`;
  if (!b.endsWith("/")) b = `${b}/`;
  return b.replace(/\/{2,}/g, "/");
}

function normaliseSite(raw: string | undefined): string | undefined {
  if (raw === undefined || raw === null) return undefined;
  const s = String(raw).trim();
  if (s === "") return undefined;
  return s.replace(/\/+$/, "");
}

/** Split "/a/b?x=1#y" into its path, search and hash parts. */
function splitPath(path: string): { pathname: string; suffix: string } {
  const cut = path.search(/[?#]/);
  if (cut === -1) return { pathname: path, suffix: "" };
  return { pathname: path.slice(0, cut), suffix: path.slice(cut) };
}

/**
 * The single URL builder.
 *
 * Trailing-slash policy follows `trailingSlash: "always"` in `astro.config.mjs`: a page
 * route gets a trailing slash, a file does not. The distinction is made on the presence
 * of a file extension, and can be forced with `pageHref()` or `assetHref()`.
 */
export function href(path: SitePath): string {
  const { pathname, suffix } = splitPath(path);
  const isFile = FILE_EXTENSION.test(pathname);
  return build(pathname, suffix, !isFile);
}

/** A page route. Always ends in "/" before any query or fragment. */
export function pageHref(path: SitePath): string {
  const { pathname, suffix } = splitPath(path);
  return build(pathname, suffix, true);
}

/**
 * A file: a stylesheet, a JSON download, an SVG, `robots.txt`, `favicon.svg`. Never
 * gains a trailing slash.
 */
export function assetHref(path: SitePath): string {
  const { pathname, suffix } = splitPath(path);
  return build(pathname, suffix, false);
}

function build(pathname: string, suffix: string, wantTrailingSlash: boolean): string {
  let rest = pathname.replace(/^\/+/, "");
  if (wantTrailingSlash && rest !== "" && !rest.endsWith("/")) rest = `${rest}/`;
  if (!wantTrailingSlash) rest = rest.replace(/\/+$/, "");
  const out = `${BASE}${rest}`.replace(/\/{2,}/g, "/") + suffix;
  issued.add(out);
  // The bare-fragment and bare-query forms are also legitimate outputs; register the
  // pathname on its own so the audit accepts a link written as href("/x") + "#frag".
  issued.add(out.replace(/[?#].*$/, ""));
  return out;
}

/**
 * An absolute URL for `<link rel="canonical">`, Open Graph, the sitemap and the 404
 * page's self-reference.
 *
 * Returns `undefined` when no `SITE_URL` was configured. Callers MUST treat that as
 * "omit the tag", never as "fall back to a guess": inventing an origin would put a
 * domain on the page that nobody has registered.
 */
export function absoluteUrl(path: SitePath): string | undefined {
  if (SITE === undefined) return undefined;
  return `${SITE}${href(path)}`;
}

/**
 * Absolute URL for a page route specifically (canonical links must carry the trailing
 * slash the server actually redirects to).
 */
export function absolutePageUrl(path: SitePath): string | undefined {
  if (SITE === undefined) return undefined;
  return `${SITE}${pageHref(path)}`;
}

/**
 * Convert an `Astro.url.pathname` back into a `SitePath`, so a layout can compute its
 * own canonical URL without the page having to restate its route. The base prefix is
 * stripped, because `href()` will add it again.
 */
export function pathFromRequest(pathname: string): SitePath {
  let p = pathname;
  if (BASE !== "/" && p.startsWith(BASE)) p = `/${p.slice(BASE.length)}`;
  if (!p.startsWith("/")) p = `/${p}`;
  return p.replace(/\/{2,}/g, "/") as SitePath;
}

/** Read-only view of everything this module has issued during the build. */
export function issuedUrls(): ReadonlySet<string> {
  return issued;
}

/**
 * Attribute values that are legitimately absolute-but-not-ours, or not URLs at all.
 * `#fragment`, `data:`, `mailto:`, `tel:`, `blob:` and any scheme-qualified URL are
 * outside the base-path problem entirely.
 */
const NOT_A_SITE_PATH = /^(?:#|[a-z][a-z0-9+.-]*:|\/\/)/i;

export interface UrlAuditProblem {
  /** The attribute the offending value was found in. */
  attribute: string;
  /** The raw value, as written. */
  value: string;
}

/**
 * Scan rendered HTML for internal absolute URLs that this module did not produce.
 *
 * Only `href` and `src` are inspected. Fragments, external schemes and protocol-relative
 * URLs are ignored; relative paths are ignored because they are base-safe by
 * construction.
 *
 * The check compares against the set of issued URLs rather than against `BASE`, so it
 * fails on a hand-written "/methods/" even when `BASE` is "/" and the link would happen
 * to work. A base-path bug must be caught at root, not discovered after deployment.
 */
export function auditHtmlUrls(html: string): UrlAuditProblem[] {
  const problems: UrlAuditProblem[] = [];
  const seen = new Set<string>();
  const attr = /\b(href|src)\s*=\s*"([^"]*)"/gi;
  let m: RegExpExecArray | null;
  while ((m = attr.exec(html)) !== null) {
    const [, name, rawValue] = m;
    const value = (rawValue ?? "").trim();
    if (value === "" || NOT_A_SITE_PATH.test(value)) continue;
    if (!value.startsWith("/")) continue; // relative: base-safe already
    if (issued.has(value) || issued.has(value.replace(/[?#].*$/, ""))) continue;
    const key = `${name}|${value}`;
    if (seen.has(key)) continue;
    seen.add(key);
    problems.push({ attribute: name ?? "href", value });
  }
  return problems;
}

/**
 * Throw a build-stopping error naming every offending attribute. Called by
 * `BaseLayout.astro` for each page it renders.
 */
export function assertNoRawSitePaths(html: string, where: string): void {
  const problems = auditHtmlUrls(html);
  if (problems.length === 0) return;
  const lines = problems.map((p) => `  ${p.attribute}="${p.value}"`).join("\n");
  throw new Error(
    `Raw site-absolute URL in ${where}.\n${lines}\n\n` +
      `Under a non-root base (SITE_BASE=${BASE}) these resolve to the wrong path.\n` +
      `Build them with the helpers in src/lib/urls.ts instead:\n` +
      `  import { href } from "../lib/urls";\n` +
      `  <a href={href("/methods/")}>  not  <a href="/methods/">`,
  );
}

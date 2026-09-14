/**
 * A static server for the BUILT OUTPUT in dist/, mounted at the configured base path.
 *
 * Why this exists rather than `astro preview`
 * ------------------------------------------
 * `npx astro preview` in Astro 7.3.2 daemonises: the command prints "Preview server
 * running ... (pid N)" and returns, and a second invocation on a different port attaches
 * to the already-running instance instead of opening the port that was asked for. A test
 * runner that needs two servers at once -- one at the project base, one at the root base --
 * cannot drive that, and Playwright's `webServer` treats a command that returns as a
 * crashed server.
 *
 * So this file serves the same directory `astro preview` serves, with the same three rules
 * that matter for these checks: the base prefix is mandatory, `trailingSlash: "always"`
 * redirects a bare directory path, and an unknown path is answered with the built
 * 404.html under a 404 status. Those three were checked against the real preview server
 * before this file was written and the responses matched (see docs/release/UI_QA.md).
 *
 * It adds nothing: no compression, no caching, no rewriting, no injected header.
 */
import { createServer } from "node:http";
import { createReadStream, existsSync, statSync, readFileSync } from "node:fs";
import { join, normalize, extname, resolve } from "node:path";

const DIST = resolve(process.env.QA_DIST ?? "dist");
const BASE = process.env.QA_BASE ?? "/";
const PORT = Number(process.env.QA_PORT ?? 4321);

if (!existsSync(join(DIST, "index.html"))) {
  console.error(`[serve] no built output at ${DIST}. Build first.`);
  process.exit(1);
}

/* Guard against serving a dist built for a different base than the one under test.
   A mismatch would make every base-prefix assertion below meaningless. */
const home = readFileSync(join(DIST, "index.html"), "utf8");
const marker = BASE === "/" ? 'href="/studies/"' : `href="${BASE}studies/"`;
if (!home.includes(marker)) {
  console.error(
    `[serve] dist/index.html does not carry ${marker}; it was built for a different base. ` +
      `Rebuild with SITE_BASE=${BASE}.`,
  );
  process.exit(1);
}

const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".csv": "text/csv; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".txt": "text/plain; charset=utf-8",
  ".xml": "application/xml",
  ".ico": "image/x-icon",
};

function send(res, status, body, type) {
  res.writeHead(status, { "content-type": type, "content-length": Buffer.byteLength(body) });
  res.end(body);
}

function notFound(res) {
  const page = join(DIST, "404.html");
  if (existsSync(page)) {
    const body = readFileSync(page);
    res.writeHead(404, { "content-type": TYPES[".html"], "content-length": body.length });
    res.end(body);
    return;
  }
  send(res, 404, "404", TYPES[".txt"]);
}

createServer((req, res) => {
  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);
  let pathname = decodeURIComponent(url.pathname);

  if (BASE !== "/") {
    if (pathname === BASE.replace(/\/$/, "")) {
      res.writeHead(301, { location: BASE + url.search });
      res.end();
      return;
    }
    if (!pathname.startsWith(BASE)) {
      notFound(res);
      return;
    }
    pathname = "/" + pathname.slice(BASE.length);
  }

  /* No traversal out of dist. normalize() collapses ".." before the join. */
  const rel = normalize(pathname).replace(/^(\.\.[/\\])+/, "");
  let file = join(DIST, rel);
  if (!file.startsWith(DIST)) {
    notFound(res);
    return;
  }

  if (existsSync(file) && statSync(file).isDirectory()) {
    if (!pathname.endsWith("/")) {
      const at = BASE === "/" ? pathname : BASE.replace(/\/$/, "") + pathname;
      res.writeHead(301, { location: at + "/" + url.search });
      res.end();
      return;
    }
    file = join(file, "index.html");
  }

  if (!existsSync(file) || statSync(file).isDirectory()) {
    notFound(res);
    return;
  }

  const type = TYPES[extname(file).toLowerCase()] ?? "application/octet-stream";
  res.writeHead(200, { "content-type": type, "content-length": statSync(file).size });
  createReadStream(file).pipe(res);
}).listen(PORT, "127.0.0.1", () => {
  console.log(`[serve] ${DIST} at http://127.0.0.1:${PORT}${BASE}`);
});

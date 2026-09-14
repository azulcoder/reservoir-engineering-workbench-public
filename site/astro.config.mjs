// @ts-check
import { defineConfig } from "astro/config";

/**
 * Deployment identity is configuration, not a constant baked into the source.
 *
 * A GitHub *project* site is served from https://<user>.github.io/<repo>/, so `base`
 * must carry the repository name and every URL in the site must be built through it. A
 * user site or a custom domain has a different shape. None of those values are known
 * yet -- this repository has no remote -- so they come from the environment and the
 * release preflight fails until real values are supplied. Nothing here invents a
 * username or a domain.
 *
 *   SITE_URL   e.g. https://example.github.io        (no trailing path)
 *   SITE_BASE  e.g. /reservoir-engineering-workbench-public/
 *
 * With neither set, the build produces a root-relative preview suitable for local
 * inspection only, and the preflight reports the deployment target as unset.
 */
const SITE_URL = process.env.SITE_URL ?? undefined;
const SITE_BASE = process.env.SITE_BASE ?? "/";

export default defineConfig({
  site: SITE_URL,
  base: SITE_BASE,
  trailingSlash: "always",
  build: { format: "directory", assets: "assets" },
  // No UI framework, no CDN, no analytics, no remote fonts. Figures are rendered to
  // static SVG by scripts/render-figures.mjs before the build and inlined, so the
  // initial HTML carries the evidence with no client JavaScript at all.
  integrations: [],
  vite: {
    build: { assetsInlineLimit: 0 },
  },
});

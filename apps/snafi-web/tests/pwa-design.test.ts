// @vitest-environment node
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const root = (p: string) => fileURLToPath(new URL(`../${p}`, import.meta.url));
const read = (p: string) => readFileSync(root(p), "utf8");

describe("installable web app", () => {
  const manifest = JSON.parse(read("public/manifest.webmanifest"));

  it("has a standalone manifest whose icons exist", () => {
    expect(manifest.name).toBe("Snafi");
    expect(manifest.display).toBe("standalone");
    expect(manifest.start_url).toBe("/today");
    const sizes = manifest.icons.map((i: { sizes: string }) => i.sizes);
    expect(sizes).toEqual(expect.arrayContaining(["192x192", "512x512"]));
    expect(manifest.icons.some((i: { purpose?: string }) => i.purpose === "maskable")).toBe(true);
    for (const icon of manifest.icons) expect(existsSync(root(`public${icon.src}`))).toBe(true);
    expect(existsSync(root("public/icons/apple-touch-icon.png"))).toBe(true);
  });

  it("has a service worker that never caches pages or signed-in data", () => {
    const sw = read("public/sw.js");
    for (const path of sw.match(/PRECACHE = \[(.*?)\]/s)![1].match(/"([^"]+)"/g)!.map((s) => s.slice(1, -1))) {
      expect(existsSync(root(`public${path}`))).toBe(true);
    }
    expect(sw).toContain('request.method !== "GET"');
    expect(sw).toContain("url.origin !== self.location.origin");
    // Navigations go to the network; only the offline page is a fallback.
    expect(sw).toMatch(/request\.mode === "navigate"[\s\S]*fetch\(request\)\.catch/);
  });
});

describe("design tokens", () => {
  const css = read("src/app/globals.css");

  it("uses the agreed palette", () => {
    for (const colour of ["#0e0e10", "#17171a", "#c9a96e", "#f2eee6", "#f7f3ec", "#1b2236", "#7a5c24", "#b8935a"]) {
      expect(css.toLowerCase()).toContain(colour);
    }
  });

  it("uses the agreed fonts per language", () => {
    expect(css).toContain('"Cormorant Garamond"');
    expect(css).toContain('"Inter Variable"');
    expect(css).toMatch(/:root\[lang="ar"\][^}]*"Amiri"[^}]*"IBM Plex Sans Arabic"/s);
  });

  it("stops the orb, cards and skeletons for reduced motion", () => {
    const block = css.slice(css.indexOf("@media (prefers-reduced-motion: reduce)"));
    expect(block).toContain(".orb[data-state] { animation: none;");
    expect(block).toContain(".rise-in { opacity: 1; animation: none; }");
    expect(block).toContain(".skeleton { animation: none; }");
  });
});

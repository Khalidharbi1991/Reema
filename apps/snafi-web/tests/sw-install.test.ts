// @vitest-environment node
/**
 * Live bug, Nov 15, 2026: push failed at "Snafi's background service didn't start" on Android and iPhone.
 * Cause: /offline.html was ignored by Git (the root .gitignore's *.html), so Vercel served it as 404,
 * the service worker's cache.addAll failed, and the worker never installed.
 */
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { runInNewContext } from "node:vm";
import { describe, expect, it, vi } from "vitest";

const SW = resolve(process.cwd(), "public/sw.js");

function precacheList(): string[] {
  const match = /const PRECACHE = (\[[^\]]*\]);/.exec(readFileSync(SW, "utf8"));
  if (!match) throw new Error("PRECACHE not found in sw.js");
  return JSON.parse(match[1]);
}

describe("the service worker's precached files", () => {
  it("every one exists in public/ and is tracked by Git, so Vercel serves it", () => {
    const files = precacheList();
    expect(files).toContain("/offline.html");
    for (const url of files) {
      const path = `public${url}`;
      expect([url, existsSync(resolve(process.cwd(), path))]).toEqual([url, true]);
      // --error-unmatch fails for a file Git does not track (for example one a .gitignore rule hides)
      expect(() => execFileSync("git", ["ls-files", "--error-unmatch", path], { stdio: "pipe" }), url).not.toThrow();
    }
  });

  it("installs even when one file fails to load", async () => {
    const listeners: Record<string, (event: unknown) => void> = {};
    const added: string[] = [];
    const cache = { add: vi.fn(async (url: string) => {
      if (url === "/offline.html") throw new TypeError("Failed to fetch (404)");
      added.push(url);
    }) };
    const self = {
      addEventListener: (name: string, fn: (event: unknown) => void) => { listeners[name] = fn; },
      skipWaiting: vi.fn(async () => undefined),
      registration: { showNotification: vi.fn() }, location: { origin: "https://snafi.example.com" }, clients: {},
    };
    runInNewContext(readFileSync(SW, "utf8"), { self, caches: { open: async () => cache }, URL, fetch: () => null });
    let done: Promise<unknown> = Promise.resolve();
    listeners.install({ waitUntil: (p: Promise<unknown>) => { done = p; } });
    await expect(done).resolves.toBeUndefined();
    expect(self.skipWaiting).toHaveBeenCalled();
    expect(added).toEqual(precacheList().filter((u) => u !== "/offline.html"));
  });
});

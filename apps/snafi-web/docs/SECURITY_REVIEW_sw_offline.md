# Snafi: security review of the service worker offline-page live-bug fix (Agent 16)

Nov 15, 2026 · branch `fix/snafi-sw-offline` (one commit, f928155, on main dbe3eb8) · reviewer: Agent 16 (`reema-agent16-security`).

**Scope:** a small fix for a live bug on Android and iPhone: turning push on failed with "Snafi's background service didn't start (timed out)". The cause was the root `.gitignore` rule `*.html`. It hid `apps/snafi-web/public/offline.html`, so production served `/offline.html` as 404. Then `cache.addAll(PRECACHE)` failed, the service worker never installed, and `navigator.serviceWorker.ready` never resolved.

**What I read:** `apps/snafi-web/.reema/security_diff_sw_offline.patch` in full (four files: the root `.gitignore`, the new `public/offline.html`, `public/sw.js` and the new `tests/sw-install.test.ts`). I also read these files whole: the current `public/sw.js`, `src/proxy.ts` (for its matcher), `next.config.ts` (for the headers), and `apps/snafi-web/.gitignore`. I read the heads of `docs/SECURITY_REVIEW.md` and `docs/SECURITY_REVIEW_settings_push.md` for the format.

**I ran nothing.** That means no tests, eslint, git, browser, deploy check or scanner, and no network call. Ahmad reports web 183 passed, Python 1393 passed and eslint clean. I have not checked any of those results, or the production 404 he describes. This review is not a certification. Khalid decides.

## Summary

**Open Critical 0, open High 0. No finding here blocks merging `fix/snafi-sw-offline` to main.** Khalid decides.

Answers to Ahmad's three questions:

1. **Skipping a failed file cannot serve a stale or wrong page.** It can only lead to no offline page (SEC-147, Low).
   - `cache.add` rejects any response that is not OK, so a 404 or error page is never stored under `/offline.html`.
   - The proxy's matcher excludes `offline.html`, so a sign-in redirect cannot be cached in its place.
   - `activate` still deletes every cache whose name does not start with `snafi-v3`, so the v2 entries are gone.
   - The fetch handler is unchanged: pages and signed-in data are still network only and never cached.
   - If `/offline.html` was skipped, the navigate fallback `caches.match("/offline.html")` resolves to `undefined`. The browser then shows its own network-error page, which holds nothing of Snafi's. The gap has no self-repair: it stays until the next `VERSION` bump.
   - See SEC-147 and SEC-150.
2. **The `.gitignore` exception covers that one file only.** The pattern contains a slash, so Git anchors it to the repo root, and it matches exactly `apps/snafi-web/public/offline.html`. Every other `.html` file in the repo (generated SOP exports, reports and the rest) is still ignored by `*.html`.
   - The file is a static page with fixed English and Arabic text and inline CSS. It has no script, no form, no outside resource and no private content.
   - I confirm it is safe to commit.
   - See SEC-149.
3. **Nothing in the worker changed, as far as the diff shows.** The diff touches no file under `src/snafi_worker/`, no migration, no adapter and no server action.
   - In `sw.js` only `VERSION` and the install handler changed. The push and notification-click handlers (the fixed, private-free lock-screen text) are unchanged.
   - I did not run `git diff` myself to confirm that commit f928155 matches the patch file.
   - See SEC-152.

**For Khalid to decide:**
- **Low:** SEC-147 (open).
- **Info:** SEC-148 (optional), SEC-149, SEC-150, SEC-151, SEC-152. These are recorded checks; none needs action.

## Findings

| ID | Severity | File:line | What an attacker (or a failure) could do | Fix | Status |
| --- | --- | --- | --- | --- | --- |
| SEC-147 | Low | `public/sw.js:21`, `:58-61` | **No offline page, and no self-repair.** No attacker is needed. If `/offline.html` fails to load during install (a deploy that drops it again, or a network blip on the phone during install), the install now succeeds without it. Later, offline, `caches.match("/offline.html")` resolves to `undefined` and `respondWith` gets no response. The browser then shows its own network-error page instead of Snafi's offline page. No stale or wrong Snafi content is shown, and no private data is involved. The file is never fetched again until the next `VERSION` bump, so a phone that missed it once keeps the gap. Before this fix, the same failure stopped the install entirely, which broke push. So this trade is the right one. | **Option 1:** in the navigate fallback, return `hit \|\| new Response(<the same fixed text>, { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } })`, so there is always an offline page. **Option 2:** after a navigation succeeds, add `/offline.html` to `STATIC_CACHE` (best effort) if it is missing. Add a test: install with `/offline.html` failing, then a navigation whose fetch rejects must get a response. | Open (for Khalid) |
| SEC-148 | Info | `public/sw.js:21` | **A future missing file fails silently.** `.catch(() => undefined)` gives no signal in production, so a file dropped by a later `.gitignore` rule would go unnoticed on phones. The new Git-tracked test (`sw-install.test.ts:22-31`) is the control: it fails if any precached file is missing from `public/` or not tracked. | Optional: `console.warn("snafi sw: precache skipped", url)`. `url` is one of five fixed public paths, so nothing private is logged. | Recorded |
| SEC-149 | Info | `.gitignore:86-88` (root); `public/offline.html` | **Checked: the exception lets nothing else into Git.** `!apps/snafi-web/public/offline.html` contains a slash, so it is anchored to the root and matches only that path. `*.html` keeps ignoring every other HTML file, and the rules for customer data, email and CAD files after it are untouched. The one remaining risk is a generated document written to that exact path, which I judge unlikely. The page holds only fixed text, inline CSS and no `<script>`, form, link, image or outside font. `proxy.ts:64` excludes `offline.html`, so the page gets no CSP nonce and no sign-in redirect. It needs no CSP because it runs no script, and `next.config.ts:22` still adds HSTS, nosniff, `X-Frame-Options: DENY`, the referrer policy and the permissions policy. I read only the `.gitignore` lines shown in the diff, not the whole root file. A later rule that ignores the file again would fail safe: the file would be left out, the new test would fail, and nothing extra would get in. | None needed. | Recorded |
| SEC-150 | Info | `public/sw.js:18-32`, `:38-62` | **Checked: no stale or wrong page can be served.** `Cache.add` rejects a response that is not OK, so a 404 or 500 body is never stored. The proxy matcher excludes `offline.html`, so a sign-in redirect cannot be cached under it. `activate` deletes every cache that does not start with `snafi-v3`. `isStaticAsset` and the network-only navigation are unchanged, so no page or signed-in response is cached. While offline, the offline page is returned for any navigation URL, which is correct because its text is fixed. `skipWaiting` and `clients.claim` behave as they did in v2. | None needed. | Recorded |
| SEC-151 | Info | `tests/sw-install.test.ts:82`, `:104`, `:120` | **Checked: the test is safe.** `execFileSync("git", ["ls-files", "--error-unmatch", path])` uses no shell and fixed arguments, and is read-only. `path` comes from the repo's own `sw.js`. `runInNewContext` runs the repo's own `sw.js` with stand-in globals, which gives no isolation but needs none. The test needs `git` on PATH and a Git checkout, so it would fail in a tarball. That affects reliability, not security. | None needed. | Recorded |
| SEC-152 | Info | patch, all hunks | **Checked: no other change.** The patch changes four files and nothing under `src/snafi_worker/`, `supabase/migrations/`, `src/adapters/` or the server actions. The push payload handling, `pushText` and `notificationclick` in `sw.js` (lines 64-116) are outside the changed hunk. The earlier open items (SEC-140, SEC-141 and the rest) are not affected and were not re-checked in this round. I did not confirm with git that the branch commit matches the patch file. | None needed. | Recorded |

**Open counts for this round:** Critical 0, High 0, Medium 0, Low 1 (SEC-147), Info 5.

## Not reviewed

- The whole root `.gitignore` (only the lines in the diff) and any part of REEMA outside `apps/snafi-web/`.
- `src/components/ServiceWorkerRegister.tsx` and `src/core/push-client.ts`, which were not touched this round. Earlier open items are not re-checked here.
- Production behaviour after deploy, Vercel's own redirects and caching, and browser differences in how a service worker handles `respondWith(undefined)`.
- Whether commit f928155 matches the patch file. I have no shell and ran nothing.

**Open Critical: 0. Open High: 0.**

## After this check (Nov 15, by Ahmad as the coding agent; not re-checked by Agent 16)

- **SEC-147 (fixed, awaiting re-check):** when a page cannot load and `/offline.html` is not cached, `sw.js` now answers with a small built-in offline page (status 503, fixed English and Arabic text, no script, no private content). Test included. Both suites pass (web 184, Python 1393).

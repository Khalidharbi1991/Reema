# Snafi step 1: security review (Agent 16)

Nov 7, 2026 · branch `feature/snafi-step1` compared with `main` · reviewer: Agent 16 (`reema-agent16-security`), under the Snafi scope Khalid approved on Nov 7, 2026 (commit 2b3e668).

This replaces the coding agent's earlier self-review. I read the diff (`.reema/security_diff.patch`; `package-lock.json` and PNG icons were left out of it), `docs/snafi/PRD.md`, `README.md`, `package.json`, `public/offline.html` and the current `src/proxy.ts`. I ran no scanner, no tests and no commands, and I had no network access. This review is not a certification; Khalid decides.

## Summary

**Open Critical: 0. Open High: 0. Nothing here blocks step 1.**
For Khalid to decide: **Medium** SEC-1; **Low** SEC-2, SEC-3, SEC-4, SEC-5. Info: SEC-6 to SEC-9.

## Findings

| ID | Severity | File:line | What an attacker could do | Fix |
| --- | --- | --- | --- | --- |
| SEC-1 | Medium | `package.json:8`, `package.json:10`, `next.config.ts:15` | `dev` and `start` listen on every network card (`--hostname 0.0.0.0`) over plain HTTP. Real keys are now set and real sign-in works, so signing in from the phone over Wi-Fi sends Khalid's email, password and Supabase session cookies (access and refresh tokens) unencrypted. Anyone on the same network (a guest, a compromised smart device, a shared or public Wi-Fi) could capture them, sign in as Khalid, read his `messages` and `jobs` rows (empty now, real chat from step 2), queue jobs for the PC worker, and possibly change the account password. The self-review rated this Low because "preview mode shows only sample data". That reason stopped applying once keys were set. | Bind `dev` and `start` to `127.0.0.1` by default and add an opt-in `dev:lan` script used only for screen checks. For phone tests with the real account, use HTTPS (`next dev --experimental-https` with a local certificate, or the Vercel preview once Khalid says yes). Until then, do not sign in with the real account from the phone over HTTP. If that was already done on a network that is not fully trusted, change the password and sign out everywhere. |
| SEC-2 | Low | `src/adapters/supabase/server-client.ts:15`, `src/adapters/supabase/proxy-session.ts:8` | This re-checks the self-review's Low item, and it is still open. The session cookies use the `@supabase/ssr` defaults: not `HttpOnly`, no `Secure` flag in any environment, and a long max-age. Any future XSS or injected script could read the tokens and take over the session. The self-review says "On Vercel they are sent over HTTPS only". That depends on the host's HTTPS redirect and HSTS, not on the cookie, which would still go out on any plain-HTTP request to the same host. | The app has no browser-side Supabase client, so `HttpOnly` costs nothing. Pass `cookieOptions: { httpOnly: true, secure: process.env.NODE_ENV === "production", sameSite: "lax" }` to both `createServerClient` calls, and add a test that checks the flags on the cookies set at sign-in. |
| SEC-3 | Low | `next.config.ts:5` | This re-checks the self-review's Low item, and it is still open. There is no Content-Security-Policy and no Strict-Transport-Security header, so no second layer limits what an injected script could load or where it could send data (it would combine with SEC-2). The other headers (`nosniff`, `X-Frame-Options: DENY`, Referrer-Policy, Permissions-Policy, no `X-Powered-By`) are present. | Before the first Vercel preview, add a nonce-based CSP from the proxy (`default-src 'self'`; `connect-src 'self'` plus the Supabase origin only if a browser client is ever added; `frame-ancestors 'none'`) and `Strict-Transport-Security: max-age=63072000; includeSubDomains`. `public/offline.html` uses only an inline `<style>` and no script, so it needs `style-src` allowance or a moved stylesheet. |
| SEC-4 | Low | `src/app/sign-in/actions.ts:17`, `src/adapters/auth/supabase.ts:14` | Sign-in runs on the server, so Supabase sees the server's IP for every attempt, and the app adds no limit of its own. Once deployed, someone could guess passwords up to Supabase's per-IP limit for that one server address. Hitting that limit could also lock Khalid out (a denial of service). I could not see the dashboard settings, so this rests on my understanding of how Supabase applies its limits. The self-review listed this as Info. | Before any deploy: add an app-side throttle per email and per client IP (for example 5 failures per 15 minutes, then a delay), use a long unique password, and turn on Supabase TOTP MFA before family accounts arrive. Check the Auth rate limits in the dashboard. |
| SEC-5 | Low | `.gitignore:10-11` | Only `.env.local` and `.env*.local` are ignored. Next.js also loads `.env`, `.env.development` and `.env.production`, so keys placed in any of those, including step 2's secret / service_role key, could be committed. | Ignore `.env` and `.env.*`, with `!.env.example` to keep the example tracked. I did not review REEMA's root `.gitignore`. |
| SEC-6 | Info | `src/app/(app)/layout.tsx:9` | `requireSession()` runs only in the shared layout. `today/page.tsx` and `chat/page.tsx` do not check it themselves, and Next.js does not promise to re-render a layout on every page request. Today the proxy covers every route and the pages show only sample data, so nothing is exposed. When step 2 adds real data, that could change. | From step 2, call `requireSession()` (or check inside the mailbox adapter) in every page and server action that reads or writes real data. Row-level security stays the final control. |
| SEC-7 | Info | `src/config/env.ts:12`, `src/config/env.ts:51` | The key variable has the `NEXT_PUBLIC_` prefix, and the secret-key guard runs only when a request is handled. No client component imports `env.ts` today, so nothing reaches browser JavaScript. If a client import is added later and the variable holds a secret key, the build would put that key into the browser bundle before the guard ever ran. | Run the same `looksSecret` check at build time (in `next.config.ts`) so `next build` fails on a secret key. Keep step 2's secret key under a name without `NEXT_PUBLIC_`, and only on the PC. |
| SEC-8 | Info | `src/adapters/index.ts:1` (also `adapters/auth/supabase.ts:1`, `adapters/mailbox/supabase.ts:1`, `adapters/supabase/server-client.ts:1`, `core/session.ts:1`, `core/server-preferences.ts:1`) | `import "server-only"` is used, but `server-only` is not in `package.json`. It resolves through Next.js's built-in alias or a hoisted copy from another package. Either way it is not on the approved list as a named package. No attack follows from this; it is a gap in the list of packages. | Confirm that Next.js 16.4.5 supplies it internally (no action needed then), or add `server-only` pinned to an exact version with Khalid's yes. |
| SEC-9 | Info | `src/proxy.ts:39` | In the matcher, the excluded names (`sw\.js`, `offline\.html`, `manifest\.webmanifest`, `favicon\.ico`, `_next/image`) match as prefixes. A future route such as `/sw.json` or `/offline.htmlx` would skip the sign-in proxy. No such route exists now. | End each exclusion with `$` or `(?:/|$)`, and extend the existing matcher test in `tests/pwa-design.test.ts` to cover one such near-miss path. |

## Re-check of the self-review

- **Fixed item, `/offline.html` covered by the proxy (Medium): closed.** `src/proxy.ts:39` excludes `offline\.html`. `tests/pwa-design.test.ts` checks that every file in `PRECACHE` is outside the matcher and that `/today` and `/chat` are inside it. I read both; I did not run the test.
- **Low, no CSP:** still open, as SEC-3 (with HSTS added).
- **Low, cookies readable by scripts and not Secure:** still open, as SEC-2. The claim that "On Vercel they are sent over HTTPS only" relies on the host, not on the cookie.
- **Low, dev server on all network cards:** raised to Medium as SEC-1, because real keys and real sign-in now exist.
- **Info, rate limiting:** raised to Low as SEC-4.

## Checked, no finding

- **Secrets:** `.env.example` holds names only. `env.ts` refuses `sb_secret_…` keys and `service_role` JWTs and requires `https` (except localhost). No key appears in the diff.
- **Row-level security** (`supabase/migrations/0001_mailbox.sql`): RLS is enabled and forced on both tables. Everything is revoked from `anon` and `authenticated`. Signed-in users get `SELECT` plus column-level `INSERT` (`kind, payload`; `conversation_id, role, body, lang`), and `user_id` comes from `auth.uid()`. The insert policies pin `status = 'queued'`, `role = 'user'` and `job_id is null`. There is no update or delete. The trigger function is `security invoker` with an empty `search_path`, and its execute right is revoked. The PGlite test uses a stand-in `auth.uid()`; I did not check it against Supabase's real function.
- **Preview mode** (`env.ts:64`) needs both `NODE_ENV === "development"` and no keys. A half-set or invalid configuration fails closed: the proxy redirects to sign-in, and `requireSession` throws.
- **Sign-in:** the input is bounded and validated, and the same error is shown whether the email or the password is wrong. There is no sign-up call, redirects go only to fixed paths (no open redirect), and `getUser()` is used rather than `getSession()`. Server actions rely on Next.js's Origin check against CSRF.
- **Injection:** database access goes only through supabase-js (PostgREST parameters), with no raw SQL. Job `kind` is checked in the app and in the database. There is no `eval`, no `dangerouslySetInnerHTML` and no shell.
- **Preference cookies:** values are checked against an allow-list when read and when written.
- **Service worker:** same-origin GET only. It caches static assets and the offline page, while pages always go to the network, so nothing personal is cached.
- **Network calls:** only Supabase, which the PRD asks for. The fonts are bundled locally through `@fontsource`, so there are no Google Fonts calls. There is no analytics or telemetry code.
- **Personal data in logs:** the app has no logging.
- **`scripts/make_icons.py`:** writes only to `public/icons/` and makes no network call.
- **Packages:** every entry in `package.json` is pinned exactly. The names are the official projects' scopes and packages, with no look-alikes.

## Not reviewed

- `package-lock.json` and every transitive package. Whether the pinned versions exist or have advisories was not checked (no network, no scanner).
- `node_modules/`, `.next/`, `.env.local` and the PNG icons.
- Supabase dashboard settings: sign-up off, Auth rate limits, password and MFA settings, JWT expiry, and whether the migration as run matches the file.
- How the real Supabase `auth.uid()` and PostgREST behave, beyond the PGlite stand-in.
- REEMA's root `.gitignore`, `.claude/` settings and hooks, and any Vercel configuration (there is none yet).
- No Snafi architecture document was named. I used the README layout table and the PRD's Architecture section instead.
- Nothing was run or tested. This is a read-only review.

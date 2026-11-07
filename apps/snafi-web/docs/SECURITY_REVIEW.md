# Snafi step 1: security self-review

Nov 7, 2026 · branch `feature/snafi-step1` · reviewer: the coding agent (Claude Code)

This is **not** Agent 16's review. Agent 16 declined, because its rules allow it to
review only Development projects under `teams/development/projects/` and Snafi is
now REEMA code. Whether Agent 16's scope should cover `apps/snafi-web/` is
Khalid's decision. This is not a certification; no online scanner was used.

## Fixed in this branch

| Severity | Finding | Fix |
| --- | --- | --- |
| Medium | The sign-in proxy covered `/offline.html`, so a signed-out phone's service worker would have cached the sign-in redirect instead of the offline page. | `offline.html` excluded from the proxy matcher; a test now checks every precached file is outside the proxy. |

## Checked, no finding

- **Row-level security:** forced on `jobs` and `messages`. Anonymous visitors have no privileges. Signed-in users can read only their own rows and insert only named columns; `user_id` comes from `auth.uid()`. There is no update or delete. Tested in PGlite (`tests/rls.test.ts`).
- **Preview mode** (sign-in skipped) needs both `NODE_ENV=development` and no keys. A production build (`next build` + `next start`) without keys was tried: `/today` redirected to `/sign-in`, and signing in reported "not configured".
- **Secrets:** the app reads only the publishable key and refuses `sb_secret_…` and `service_role` JWTs. Keys live only in the gitignored `.env.local`.
- **Sign-in:** the error does not say whether the email or the password was wrong. There is no sign-up call in the code, and sign-up must also be turned off in Supabase. Redirects go only to fixed paths, so there is no open redirect.
- **Service worker:** caches only `/_next/static/`, `/icons/` and the offline page, and only same-origin GET requests. Pages always go to the network.
- **XSS:** React escapes all text; there is no `dangerouslySetInnerHTML`.

## Open, for Khalid to decide (none block step 1)

| Severity | Finding | Suggested handling |
| --- | --- | --- |
| Low | No Content-Security-Policy header yet (other security headers are set). | Add a nonce-based CSP with the first Vercel preview. |
| Low | Supabase session cookies are readable by page scripts (the `@supabase/ssr` default) and are not `Secure` over plain-HTTP Wi-Fi testing. | Acceptable while there is no XSS. On Vercel they are sent over HTTPS only. |
| Low | The dev server listens on all network cards, so anyone on the same Wi-Fi can open it. Preview mode shows only sample data. | Use it on the home Wi-Fi only; stop it when not testing. |
| Info | Sign-in rate limiting relies on Supabase Auth's built-in limits. | Review the limits in the dashboard before family accounts arrive. |

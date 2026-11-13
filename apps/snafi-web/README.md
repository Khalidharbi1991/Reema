# Snafi web (steps 1 and 2)

Snafi is Khalid's personal assistant app and part of REEMA. The plan is
`docs/snafi/PRD.md`.

- **Step 1:** sign-in, Today and Chat screens, the dark/light and Arabic/English menu.
- **Step 2:** Chat with Ahmad through the PC worker (`src/snafi_worker/`), approval
  cards with Approve / Reject, Undo on logged actions, a "PC offline" banner with the
  last backup's result in the menu, and real Umm al-Qura prayer times and Hijri date
  for Jeddah on Today. The event, tasks and Ahmad's cards on Today stay marked
  samples until steps 3-5.

The web app never calls a model; the worker on the PC does. No deploy.

## Run it

```bash
cd apps/snafi-web
npm install          # first time only
npm run dev          # http://localhost:3000
```

`npm run dev` and `npm run start` listen on this PC only (127.0.0.1).

**Wi-Fi testing (opt in):** `npm run dev:lan` listens on all network cards, so a
phone on the same Wi-Fi can open `http://<this PC's Wi-Fi IPv4>:3000` (find it
with `ipconfig`). Windows may ask once to allow Node.js on private networks. Stop
it when you finish testing.

> **Never sign in with the real account over plain HTTP.** Over Wi-Fi HTTP the
> password and session would cross the network unencrypted. The app enforces this:
> off localhost and without HTTPS, the sign-in form is switched off and the server
> refuses the attempt, and session cookies are `Secure`, so the browser would not
> keep them anyway. With keys set, a phone over `dev:lan` therefore stops at the
> sign-in page. To look at the screens on the phone, use preview mode (no keys
> loaded); real sign-in on the phone waits for HTTPS (a Vercel preview, with
> Khalid's yes).

**Session cookies** are HttpOnly, SameSite=Lax, and Secure everywhere except on
localhost (`src/adapters/supabase/cookie-policy.ts`).

**Headers (SEC-3):** every page gets a nonce-based Content-Security-Policy, made per
request in `src/proxy.ts` (`src/core/security-headers.ts`), and every response gets
`Strict-Transport-Security` (`next.config.ts`).

**Sign-in throttle (SEC-4):** each try is counted before Supabase is asked, one at a
time per key, and taken back unless the password was wrong. After 5 counted tries in
15 minutes for one email (or, on Vercel, from one client IP) sign-in is refused until
15 minutes have passed. Anyone who knows the email can use this to block new sign-ins
for a while; signed-in sessions keep working.
Counts live in Supabase (`migrations/0005_signin_throttle.sql`) as HMACs keyed with
`SNAFI_THROTTLE_SECRET`; the app never stores the email or IP. If the store cannot be
reached, sign-in says "not available" (fails closed).

**Redirects** go to `SNAFI_SITE_URL`, or on Vercel to Vercel's own address, never to
the Host the request claims. A production build with neither refuses every page.

**Preview mode:** with no Supabase keys, the development server skips sign-in so
the screens can be checked, and shows a banner saying so. A production build
never does this.

**Installing to the home screen** needs HTTPS, so it waits for a Vercel preview
(Khalid's yes required for every deploy). Over Wi-Fi HTTP the app works in the
browser but the service worker does not register.

## Supabase

See `supabase/README.md` for the dashboard steps (turn off sign-up, add the
owner, run the migration, copy the URL and publishable key). Keys go only in
`apps/snafi-web/.env.local` (gitignored); `.env.example` lists the names. The
app refuses a secret / service_role key.

## Layout

| Path | What |
| --- | --- |
| `src/adapters/` | Every outside service behind its own interface: `auth/`, `mailbox/`, `today/` (prayer times in `today/prayer.ts`), `supabase/`. `adapters/index.ts` maps the configured choice to a class. Only this folder may import Supabase (a test enforces it). |
| `src/config/` | `env.ts` (the only place env vars are read), `services.ts` (which adapter backs each service: `SNAFI_AUTH_ADAPTER`, `SNAFI_MAILBOX_ADAPTER`, `SNAFI_TODAY_ADAPTER`), `app.ts` (time zone and the prayer-times city, Jeddah) |
| `src/core/` | Preferences (theme, language), session guard, haptics |
| `src/i18n/` | English and Arabic text; Arabic switches the page to right-to-left |
| `src/app/` | Screens: `sign-in`, `(app)/today`, `(app)/chat` |
| `src/proxy.ts` | Sends signed-out visitors to `/sign-in` and refreshes the session |
| `supabase/migrations/` | SQL for the mailbox tables and their row-level security |
| `public/` | Manifest, service worker, offline page, icons (`scripts/make_icons.py` redraws them) |

## Tests

```bash
npm test             # Vitest, offline; fetch is blocked
npm run typecheck
npm run lint
npm run build
```

`tests/rls.test.ts` and `tests/rls-step2.test.ts` run the real migrations in PGlite
(Postgres in-process) and check that users see only their own rows, that anonymous
visitors get nothing, and that the app changes nothing except through the approval
and Undo functions. `tests/restore.test.ts` restores a real backup from the worker
into an empty PGlite database.

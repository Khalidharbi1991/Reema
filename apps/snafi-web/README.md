# Snafi web (step 1: skeleton)

Snafi is Khalid's personal assistant app and part of REEMA. The plan is
`docs/snafi/PRD.md`. Step 1 is the skeleton: sign-in, Today and Chat screens with
clearly marked sample data, the dark/light and Arabic/English menu, and the
Supabase mailbox tables (`jobs`, `messages`), empty for now. No model call, no
deploy.

## Run it

```bash
cd apps/snafi-web
npm install          # first time only
npm run dev          # http://localhost:3000
```

The dev server listens on all network cards, so a phone on the same Wi-Fi can
open `http://<this PC's Wi-Fi IPv4>:3000` (find it with `ipconfig`). Windows may
ask once to allow Node.js on private networks.

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
| `src/adapters/` | Every outside service behind its own interface: `auth/`, `mailbox/`, `today/`, `supabase/`. `adapters/index.ts` picks the implementation. Only this folder may import Supabase (a test enforces it). |
| `src/config/` | `env.ts` (the only place env vars are read), `app.ts` (time zone and other settings) |
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

`tests/rls.test.ts` runs the real migration in PGlite (Postgres in-process) and
checks that users see only their own rows, that anonymous visitors get nothing,
and that the app can never update or delete.

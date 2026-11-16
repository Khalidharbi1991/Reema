# Snafi web (steps 1 to 5, and the Inbox)

Snafi is Khalid's personal assistant app and part of REEMA. The plan is
`docs/snafi/PRD.md`.

- **Step 1:** sign-in, Today and Chat screens, the dark/light and Arabic/English menu.
- **Step 2:** Chat with Ahmad through the PC worker (`src/snafi_worker/`), approval
  cards with Approve / Reject, Undo on logged actions, a "PC offline" banner with the
  last backup's result in the menu, and real Umm al-Qura prayer times and Hijri date
  for Jeddah on Today.
- **Step 3:** Today shows the next Google Calendar event and up to five important unread
  emails (sender and subject only) from the PC worker's snapshot (`today_feed`, migration
  0006), with a note when Google needs connecting or reconnecting. Gmail, Calendar and
  Drive actions run on the PC; sends, invites and deletes arrive as approval cards showing
  the exact content.
- **Step 4:** Today shows important unread Yahoo emails next to Gmail's (at most five from
  each, newest first, each labelled Gmail or Yahoo) and up to ten Todoist tasks due today
  or overdue (migration 0007), with a note for each source that needs connecting. Yahoo
  and Todoist actions run on the PC. Ahmad's cards (reminders, the morning brief, important mail) come from the PC's scheduler (step 5); Settings turns phone notifications on (see `docs/snafi/PUSH_SETUP.md`).

- **UI job (Inbox, simpler Today, Chat scroll, mobile fit, calmer look):** plan in
  `docs/PRD_ui_inbox.md`, design in `docs/UI.md`.
  - **Bell and Inbox.** Every signed-in screen has a bell in the top bar with an unread badge
    (nothing at 0, the number to 9, "9+" from 10). It counts pending approvals and unread cards;
    `test` cards never count. `/inbox` lists pending approvals first (always open, with the exact
    arguments, Approve and Reject), then Ahmad's cards newest first. A card opens in place and is
    marked read the first time it is opened; only opening the list marks nothing. Mail rows show
    the sender and subject only. Read cards are hidden 7 days after they were read; unread cards
    and pending approvals never clear. There is no Dismiss any more.
  - **Today** now shows only: the greeting with the Gregorian and Hijri dates, the Now card (the
    next prayer or today's next event, whichever is first, the prayer on a tie, with a countdown
    that ticks once a minute and moves on at zero), today's plan (up to 5 events and 3 tasks, then
    "+N more"), Ahmad's single message (an approval first, then the newest unread reminder, then
    today's unread brief; it opens the Inbox at that item) and the orb. The Important email card,
    the card list, approval buttons and the connection notes are gone from Today; the Google,
    Yahoo and Todoist connection notes are in **Settings**, under Connections.
  - **Chat** opens at the latest message, follows new items while you are at the bottom, and
    shows a "jump to latest" button when you have scrolled up.
  - **Database:** run `supabase/migrations/0009_inbox_read.sql` once in the Supabase SQL Editor,
    after 0008. It adds `cards.read_at` and `mark_card_read`. Until it is run, the Inbox still
    works: every card shows as unread and opening one does not stick. The app and this migration
    should go live together.
  - **Preview mode** (no keys) now shows sample content (an approval, cards, a chat) so the
    screens can be looked at; all of it is invented and labelled "Sample".

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
| `src/app/` | Screens: `sign-in`, `(app)/today`, `(app)/inbox`, `(app)/chat`, `(app)/settings` |
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

`tests/ui-*.test.tsx` cover the UI job by acceptance criterion. `tests/ui-overflow.test.tsx`
checks structural guards only: jsdom has no layout, so real overflow at 360 and 390 px is
measured in a browser, separately. `tests/rls-inbox.test.ts` checks `mark_card_read`.

`tests/rls.test.ts` and `tests/rls-step2.test.ts` run the real migrations in PGlite
(Postgres in-process) and check that users see only their own rows, that anonymous
visitors get nothing, and that the app changes nothing except through the approval
and Undo functions. `tests/restore.test.ts` restores a real backup from the worker
into an empty PGlite database.

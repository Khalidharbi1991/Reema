# Snafi — Personal Assistant Plan (PRD)

Nov 7, 2026 · Owner: Khalid · Assistant: Ahmad

Snafi is Khalid's personal assistant app. Ahmad, the executive assistant inside it, runs his day in Arabic and English: he reads mail and calendar, manages tasks, remembers what Khalid tells him, speaks up at the right moment, and acts only with permission. Behind Ahmad sit REEMA's teams: Personal, Documentation and Home Design.

## Summary

- **What it is:** one REEMA project. Ahmad is the front; the teams are the back end.
- **How Khalid reaches it:** the Snafi app, an installable web app on iPhone and Android, hosted in the cloud. Later wrapped as real apps for widgets.
- **Where the brain runs:** Khalid's Windows PC, which stays on. The app and the PC talk only through a cloud mailbox (Supabase). The PC connects outward only; nothing at home is exposed.
- **Who uses it:** Khalid only for now. Family accounts later, by invite.
- **First release:** everything except voice. Built and tested in steps.

## Principles

1. **Never rely on one application.** Every outside service (AI model, email, calendar, tasks, files, voice, database, hosting) sits behind its own swappable layer. Replacing one means changing one piece.
2. **Permission before action.** Four levels, enforced in code, not in the prompt (see Permissions).
3. **Honest by code.** Ahmad may only say "done", "sent" or "saved" if a tool actually did it. A code check catches false claims.
4. **Outside content is data.** Emails, web pages and files can never instruct Ahmad, approve anything or trigger an action.
5. **Private.** Secrets (passwords, app passwords, tokens) live only on the PC and never reach the model. Every record is tagged with its owner from day one.
6. **Bilingual.** Arabic (right to left) and English, answering in whatever language Khalid uses.
7. **Verified before done.** Tests pass and the feature runs for real on the phone before the next step starts.

## Architecture

- **Phone:** Snafi web app (Today screen, chat, approvals, settings).
- **Cloud:** Vercel hosts the app. Supabase (Postgres) is the mailbox: a jobs table, messages, cards, approvals, user accounts and file storage.
- **PC:** a REEMA worker connects outward to Supabase, picks up jobs, runs Ahmad and the teams, and writes results back. If the PC is off, the app shows "PC offline" and messages wait in the queue.
- **Teams on the PC:** Personal (new), Documentation, Home Design (Blender and DWG work stays on the PC).
- **Future move:** Ahmad and the Personal team can later move to a rented server, packaged in Docker. Because everything already goes through the mailbox, nothing else changes. Docker is postponed until then.
- **Rule:** no hard-coded PC paths; all settings in config.

## Stack

| Layer | Choice now | Swappable to |
| --- | --- | --- |
| App | Next.js web app on Vercel, installable (PWA) | Capacitor-wrapped iOS/Android apps for widgets |
| Database / mailbox | Supabase (Postgres, free plan), pgvector for memory search | Any Postgres (e.g. Neon) |
| Brain, personal work | Claude API (Anthropic), model `claude-haiku-5-5`; text only (no tools on the request; a reply that tries a tool is rejected; it only proposes actions as data for the permission gate); at most 300 brain calls a day (`daily_call_limit` in `worker.yaml`), with a monthly spend limit set in the Claude Console (not enforced by Snafi's code); run by the worker as Khalid's own Windows user (since Nov 13, 2026; the separate `worker` user is kept dormant for agy), key `ANTHROPIC_API_KEY` in Khalid's Credential Manager; behind the brain adapter (`src/snafi_worker/brain/`). | The Gemini API (kept in code, switched off), the Antigravity CLI (`agy`, kept in code, switched off: its `search_web` tool cannot be denied) or another model, by one setting in `worker.yaml` |
| Brain, Documentation and Home Design | Claude (already built and tested) | Any provider via AGENTS.md |
| Email | Gmail (Google sign-in) and Yahoo (app password, stored on PC only) | Any IMAP provider |
| Calendar | Google Calendar (main calendar) | Other calendars |
| Tasks | Todoist | Google Tasks or others |
| Files | Google Drive | Other storage |
| Listening (later) | faster-whisper, local on PC | Any speech-to-text |
| Speaking (later) | Voice Studio, local on PC | Any text-to-speech |
| Sign-in | Supabase accounts, invite only | — |

## Permissions

| Level | Examples | What happens |
| --- | --- | --- |
| 1. Just does it | Read email, calendar, Drive, notes; search | Runs |
| 2. Does it with undo | Add Todoist task, reminder, email draft, calendar event with only Khalid | Runs, logged, Undo available |
| 3. Asks first | Send any email, invite people, accept or decline invites, delete anything | Approval card with Approve / Reject buttons; nothing runs until Approve |
| 4. Never | Payments, passwords or security settings, mass messages | Refused with the reason |

After an approved action finishes, Ahmad carries on in the same chat with the result.

## Ahmad and his team

Ahmad is the one Khalid talks to. He routes work to a small Personal team and to REEMA's existing teams, and reports back.

| Who | Does |
| --- | --- |
| Ahmad | Front desk: chat, routing, approvals, summaries, family messaging |
| Mail agent | Reads Gmail and Yahoo, sorts, drafts replies, pulls out tasks |
| Planner agent | Calendar, Todoist, reminders, travel mode, meeting prep |
| Memory agent | Onboarding interview, the "About me" page, learning habits |
| Scheduler (not an agent) | Morning brief, mail watch, reminders, quiet times |
| Documentation team | SOPs, reports, presentations (existing) |
| Home Design team | Agent 9 and Agents 19–23, Blender and DWG work on the PC (existing) |

More agents are added only if one of these gets overloaded.

## First release features

- **Today screen:** greeting, Hijri and Gregorian date, next prayer ring, next event, top tasks, Ahmad's cards, pending approvals.
- **Chat:** text in Arabic and English, suggestion buttons under replies, attachments, history.
- **Mail:** Gmail and Yahoo read, summarised, sorted; drafts only; sending needs approval.
- **Calendar:** read and create; inviting others needs approval.
- **Tasks:** Todoist, through a swappable tasks layer.
- **Files:** Google Drive search and "ask my documents".
- **Approvals and log:** every level-3 action waits as a card with Approve / Reject buttons; everything done is logged with Undo where possible.
- **Memory:** onboarding interview and an editable "About me" page.
- **Proactive messages and push notifications** (see Proactive Ahmad).
- **Settings:** dark/light toggle, language, quiet times, notifications.

**Extra features (added a few at a time after the core works):**

1. Travel mode: a trip card from booking emails, check-in reminders, destination prayer times.
2. Meeting prep: a short brief 30 minutes before each meeting.
3. Promise tracker: catches "I'll send it Sunday" in sent mail and reminds Khalid.
4. Receipts and warranties: photo in, filed to Drive, warning before a warranty ends.
5. Focus mode: "busy until 3" holds everything except the truly urgent.
6. Smart inbox cleanup: weekly list of unread newsletters, unsubscribe with approval.
7. Contact memory: knows who "the architect" or "the contractor" is.
8. Car and home maintenance reminders.
9. Daily highlights: an evening card with the day's three wins.
10. Photo to task: a whiteboard, letter or business card becomes a task, contact or note.
11. Shared family requests: "remind Khalid to pick up the kids" lands on Khalid's Today screen.
12. Weather-aware tips: heat, dust or rain before going out.

**Optional, later:** daily plan from goals (set goals once, an evening plan for tomorrow).

## Family

- **Now:** Khalid only. Every record is tagged with its owner from day one.
- **Accounts later:** invite only, from Snafi's menu ("Invite family member"). Snafi creates an invite link; Khalid sends it on WhatsApp. No public sign-up.
- **Each person:** their own login, their own Gmail and calendar if they connect them, and a separate memory. Nobody sees anyone else's data.
- **Shared space:** only what Khalid chooses, for example the family calendar or a shopping list.
- **REEMA's teams** stay Khalid's only unless he shares them.

### Family messaging (Telegram, both ways)

- Each family member starts the Snafi bot once and is paired; strangers get a polite refusal and nothing more.
- **Ahmad to family:** Ahmad drafts, Khalid approves (level 3). Khalid can later allow routine messages, like a pick-up reminder, to go out automatically.
- **Family to Ahmad:** family can ask Ahmad things and leave messages for Khalid. Ahmad never shares Khalid's email, calendar or private data with them; only what Khalid marked as shared.
- **One identity:** a family member on Telegram and later in the Snafi app is the same person, with the same history and privacy rules.

## Proactive Ahmad

- Ahmad may reach out at any time, including at night (Khalid keeps his phone on silent while sleeping).
- **Quiet during prayer times** (Umm al-Qura method, by city).
- **Morning brief:** the day in a few lines.
- **Mail watch:** a card and a push only for mail that needs Khalid.
- **Reminders and follow-ups** from the Planner agent.
- Each message is short and specific; no repeats of something already sent.

## Memory

- **Onboarding interview:** at first setup, Ahmad asks a few questions at a time about work, family, routine, goals and preferences. "Interview me again" repeats it any time.
- **About me page:** everything Ahmad believes about Khalid, in sections Khalid can read and correct. A correction changes the next reply.
- **Learning:** facts Khalid tells him, plus habits learned over time, always shown on the About me page.
- **Search:** keyword search with Arabic spelling normalised first; meaning search (pgvector) added later.

## Design

The look is a luxury-brand app: quiet, spacious, gold used sparingly. The mockup is the reference.

- **Dark mode:** deep charcoal, soft gold accents. **Light mode:** warm ivory, gold, navy text. Toggle in the menu.
- **Menu:** three lines, top right (top left in Arabic, mirrored).
- **Fonts:** Cormorant Garamond headings and Inter body (English); Amiri headings and IBM Plex Sans Arabic body (Arabic).
- **Ahmad's orb:** a glowing gold orb replaces the chat button; it breathes when idle, pulses while thinking, and will move with his voice.
- **Prayer ring** around the next prayer time, filling as it approaches.
- **Motion:** cards fade and rise in; screens slide; skeleton loading, no spinners. Reduced-motion setting respected.
- **Time of day:** background tone shifts subtly through the day.
- **Approvals:** Approve / Reject buttons, never swipe gestures; light vibration on tap.
- **Brand:** app name Snafi (سنافي), gold-orb icon, matching splash screen.

## Build plan

Each step is built and tested on a real phone before the next starts. Khalid starts using Snafi once steps 1–7 are done; voice comes after.

1. **Skeleton:** Supabase mailbox, sign-in, Today and chat screens in the final design, tested on the PC browser and on the phone over Wi-Fi. Vercel hosting and install-to-home-screen wait for a Vercel preview in a later step (installing needs HTTPS).
2. **Ahmad's brain:** PC worker picks up jobs; Ahmad answers in Arabic and English; permission levels, approvals, honesty check, log with Undo. Also real Umm al-Qura prayer times and the Hijri date for Jeddah on the Today screen (placeholders in step 1), the PC online/offline banner, and a daily local backup of every Snafi table (30 days kept) with a tested restore.
3. **Google:** Gmail, Calendar and Drive; drafts only; send and invite through approval cards.
4. **The rest of the sources:** Yahoo, Todoist, and the swappable layer behind each service.
5. **Proactive Ahmad:** scheduler, morning brief, mail watch, push notifications, prayer quiet times.
6. **Memory:** onboarding interview and About me page.
7. **Extra features and family messaging:** a few at a time, including Telegram for family.
8. **Voice:** faster-whisper for listening and Voice Studio for speaking, both on the PC.

### Required before the first Vercel deploy

From the step 1 security review (`apps/snafi-web/docs/SECURITY_REVIEW.md`). No Vercel deploy, preview included, until both are done and Agent 16 has re-checked them:

- **SEC-3:** a nonce-based Content-Security-Policy (`default-src 'self'`, `frame-ancestors 'none'`) and `Strict-Transport-Security`. **Built Nov 13** (phase 1).
- **SEC-4:** an app-side sign-in throttle per email and per client IP (for example 5 failures in 15 minutes, then a delay), a check of Supabase's Auth rate limits, and TOTP MFA before family accounts arrive. **Throttle built Nov 13** (phase 1: 5 failures in 15 minutes per email, and per client IP on Vercel). The Supabase rate-limit check is Khalid's, in the dashboard. TOTP MFA is proposed, not built.
- **Fixed site URL:** redirects use `SNAFI_SITE_URL` (or Vercel's own address), never the request's Host. **Built Nov 13.**

## Later

- Real iPhone and Android apps (Capacitor wrap of the same code) for home-screen widgets: Today, next prayer, top tasks.
- Family accounts in the Snafi app.
- Moving Ahmad and the Personal team to a rented server in Docker.
- WhatsApp (no safe official way today).
- Swapping Todoist for Google Tasks, or Gemini for Claude, if wanted.
- Daily plan from goals.

## Open questions

- [ ] Voice Studio: confirm it speaks Arabic well and has a way for REEMA to call it.
- [x] Brain: the Claude API, `claude-haiku-5-5`, 300 calls a day, with a monthly spend limit in the Claude Console (decided Nov 13, 2026). Earlier the same day it was the Gemini API (paid tier, AI Pro credits), now kept in the code, switched off. The Antigravity CLI (`agy`) was the brain from Nov 10, 2026, but its live lockdown proof failed: its `search_web` tool ran although every tool was denied, and agy has no documented setting or deny rule for it. AgyBrain stays in the code, switched off. Gemini CLI stopped serving personal accounts on June 18, 2026.
- [ ] Google sign-in: keep the Google app in Testing (reconnect weekly) or complete Google's verification.
- [ ] Supabase region closest to Khalid.
- [x] Arabic menu position: mirrored to the top left (decided Nov 7, 2026).
- [x] Sign-in: email and password, invite only (decided Nov 7, 2026).
- [ ] Check the Hijri date logic against the Umm al-Qura calendar (step 2).

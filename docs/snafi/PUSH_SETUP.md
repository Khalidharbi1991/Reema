# Snafi step 5: Proactive Ahmad and phone notifications

Nov 14, 2026 · For Khalid. Do these yourself. The push private key is made on the PC and never
shown; you only copy its **public** half, which is not secret.

## What Snafi will do

| | What happens |
| --- | --- |
| Reminders | A reminder with a time goes off at that time: a card on Today and a phone notification. A reminder without a time never alerts. |
| Morning brief | Once a day at your time (default 7:00 AM): today's events, top tasks, important Gmail and Yahoo email (sender and subject only), and the five prayer times. If the PC was off then, it comes when the PC is back, until five hours after your time. |
| Mail watch | Every 10 minutes, a card and a push only for truly important new mail. Gmail: unread, Inbox, marked Important, Primary tab. Yahoo: unread, Inbox, not a newsletter or automatic email, from someone you emailed from Yahoo in the last 90 days, and Yahoo's own check says the sender is genuine (DMARC passed for the sender's domain), so a stranger cannot fake a friend's address to get a push. A Yahoo email that fails that check, or whose sender's domain has no DMARC, still shows on Today and in the brief; it just isn't pushed. The first run only learns what is already there and sends nothing. |
| Test | Settings → Send a test. |

The manners, enforced in the worker's code:

- **Never twice.** Each message has one key in the database, which refuses a second copy.
- **No repeats.** The same text is not shown again within 24 hours.
- **Prayer quiet time.** Nothing for 20 minutes after each adhan (Jeddah, Umm al-Qura). A message
  due then waits, and goes out when the 20 minutes end.
- **Daily limit.** At most 10 pushes a day by default (you can set 1 to 50 in Settings). Reminders
  don't count. Past the limit, cards still appear on Today, silently.
- **Lock screen.** A push carries no private text at all: the phone only shows "You have a
  reminder", "Your morning brief is ready" or "Ahmad has an update for you" (in Arabic if you
  saved Settings in Arabic). Tap it to open Today, where the card is, behind sign-in.
- **Night.** There are no quiet hours: Ahmad may message you any time (your phone is silent at night).

Times everywhere in Snafi are 12-hour, with AM/PM in English and ص/م in Arabic.

## 1. Update the database once

In the Supabase SQL Editor, run `apps/snafi-web/supabase/migrations/0008_proactive.sql` once
(after 0007).

## 2. Redeploy the worker

Deploy the worker as usual (`src\snafi_worker\deploy\deploy.ps1`, as admin), so
`C:\SnafiWorker` has the step 5 code.

## 3. Make the push key and give the site address

In a normal PowerShell window (not admin):

```bash
C:\SnafiWorker\snafi.cmd set-secrets
```

Press Enter at every question you have already answered. There is one new question: **Snafi site
address for push notifications**. Type the address you open Snafi at, for example
`https://snafi.vercel.app` (no path). It is sent to Apple's and Google's push services as the
contact for your pushes.

At the end it says `made SNAFI_VAPID_PRIVATE_KEY (random, never shown)` and prints a line under
**Push public key**. Copy that long line (it starts with `B`). To see it again later:

```bash
C:\SnafiWorker\snafi.cmd set-secrets --push-key
```

## 4. Put the public key in Vercel

Vercel → the Snafi project → **Settings → Environment Variables** → add
`NEXT_PUBLIC_SNAFI_VAPID_PUBLIC_KEY` with the public key, for **Production** (and **Preview** if
you use previews). It is not secret; the private key never leaves your PC.

## 5. Push main and restart the worker

1. Push `main` from your own terminal. That redeploys Snafi on Vercel with the new key.
2. Restart the worker so it loads the push key: sign out of Windows and back in, or in Task
   Scheduler end the Snafi worker task and run it again.

## 6. Turn it on, on the phone

- **iPhone (iOS 16.4 or later):** in Safari open Snafi, tap **Share → Add to Home Screen**, then
  open Snafi **from the Home Screen icon**. Push works only there, not in a Safari tab.
- **Android:** in Chrome open Snafi, then **⋮ → Install app** (or Add to Home screen), and open it
  from the icon.

Then menu (☰) → **Settings** → Phone notifications → **On** → **Allow**. Set your brief time
(hour, minute, AM/PM) and daily limit, tap **Save**, then **Send a test**. The test arrives in
under a minute (later if it is within 20 minutes after an adhan).

If you change Snafi's language, tap **Save** in Settings once so the lock-screen text follows.

## 7. Check it

1. Ask Ahmad: "Remind me in 3 minutes to stretch." A card and a notification come at that time.
2. The first mail watch (within 10 minutes of the restart) sends nothing; it only learns.
3. The next morning the brief arrives at your time.

## Turning it off

- One phone: Settings → Phone notifications → **Off**.
- Everything: remove `NEXT_PUBLIC_SNAFI_VAPID_PUBLIC_KEY` in Vercel, or remove the push key with
  `snafi.cmd set-secrets --remove` (this removes every Snafi value; run `set-secrets` again after).
  Cards still appear on Today without push.

## What is stored where

- **Your PC (Credential Manager):** `SNAFI_VAPID_PRIVATE_KEY` (made at random, never shown) and
  `SNAFI_PUSH_CONTACT` (the site address).
- **Vercel:** only the public key.
- **Supabase:** your settings, each phone's push address (only Apple, Google, Mozilla or Microsoft
  push services are accepted; at most five), Ahmad's cards (the reminder text, the brief, the
  sender and subject of important mail), and a record of what was sent, so nothing goes twice.
  The record keeps no text once a card is shown. **Cards and the sent record are deleted after
  30 days** (dismissed or not), checked every hour (your decision, Nov 14, 2026).
- **Daily backups:** your settings only. Cards, the sent record and push addresses are never in a
  backup, so no copy older than 30 days exists anywhere. After a restore, turn push on again; past
  reminders don't go off again, the mail watch learns again, and that day's brief may come twice.
- **Apple's or Google's push servers:** only an encrypted message holding the kind ("reminder",
  "brief", "mail" or "test"), the language and an id. Never any text of yours.
- **Yahoo:** to decide who you correspond with, the worker reads only the To, Cc and Bcc lines of
  your newest 500 sent emails from the last 90 days, read-only, every 6 hours. The addresses stay in
  the worker's memory and are not saved anywhere.

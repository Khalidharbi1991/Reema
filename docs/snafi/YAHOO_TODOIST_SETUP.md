# Snafi step 4: connecting Yahoo Mail and Todoist

Nov 14, 2026 · For Khalid. Do these yourself; never paste the app password or the token into a
chat, an email or a file. Snafi keeps them only in your Windows Credential Manager.

## What Snafi will do with them

| | Yahoo Mail | Todoist |
| --- | --- | --- |
| Just does it (Level 1) | read and search your Inbox (it never marks anything read) | list today's and overdue tasks, search |
| Does it with Undo (Level 2) | save a draft in Yahoo's Drafts | add, complete, reschedule a task |
| Asks first, with a card (Level 3) | send an email (the card shows From, To, Cc, Bcc, subject and body); delete a draft | delete a task |
| Never (Level 4) | more than 5 people in one email | — |

Ahmad reads Gmail and Yahoo together and always says which account an email came from and
which account a reply goes from. A reply goes from the account the email came from.

**Neither credential can be limited.** A Yahoo app password can read and send all mail in
that Yahoo account; the Todoist token can change all of your Todoist. Snafi's code holds them
to the levels above. You can cancel either at any time (see "Cancelling" below).

## 1. Make a Yahoo app password

1. Sign in at login.yahoo.com, then open **Account Info → Account security**.
2. If **2-step verification** is off, turn it on (Yahoo makes app passwords only with it on).
3. Click **Generate app password** (or **Manage app passwords**), type the name `Snafi`, and
   click **Generate**.
4. Copy the 16-letter password. Yahoo shows it only once; if you lose it, make a new one.

## 2. Copy your Todoist API token

1. Open Todoist on the web: **Settings → Integrations → Developer**.
2. Copy the **API token** (40 letters and digits).

## 3. Store both on the PC

After step 4 is merged and the worker is redeployed (`deploy.ps1`, as you usually do), open a
normal PowerShell window (not admin) and run:

```bash
C:\SnafiWorker\snafi.cmd set-secrets
```

Press Enter at each question you have already answered to keep it. Then:

- **Your Yahoo email address:** type it.
- **Yahoo app password:** paste it (right-click, or Ctrl+Shift+V). Nothing shows while you
  paste. Spaces between the groups of four are fine.
- **Todoist API token:** paste it the same way.

`C:\SnafiWorker\snafi.cmd set-secrets --status` lists which values are stored (names only).
The worker picks up new values within five minutes; no restart is needed.

## 4. Update the database once

In the Supabase SQL Editor, run `apps/snafi-web/supabase/migrations/0007_today_sources.sql`
once (after 0006). It lets the Today row hold your tasks and the Yahoo and Todoist states.

## 5. Check it

- On Today: important Yahoo emails appear next to Gmail's, each labelled **Gmail** or
  **Yahoo**, and **Top tasks** shows today's and overdue Todoist tasks. A small note says if
  Yahoo or Todoist still needs connecting.
- In chat: "What's new in my Yahoo?", "What's on my Todoist today?", "Add a task: call the
  contractor tomorrow 10am".

"Important" in Yahoo means unread, in the Inbox, from the last 24 hours, and not a
newsletter, mailing list or automatic email (Yahoo has no Important mark like Gmail's).

## Cancelling

- **Yahoo:** in Account security, **Manage app passwords**, remove `Snafi`. Snafi's Yahoo tools
  then say Yahoo refused the app password.
- **Todoist:** Settings → Integrations → Developer, **Issue a new API token** (the old one
  stops working).
- **Snafi only:** set `yahoo: provider: none` or `tasks: provider: none` in `worker.yaml` and
  redeploy, or remove all stored values with `snafi.cmd set-secrets --remove`.

## What Snafi keeps in Supabase (and so in the daily backup)

As with Gmail (SEC-83, which you accepted), and now for Yahoo and Todoist too (SEC-110):
- every Yahoo draft and send Ahmad writes, whole (to, cc, bcc, subject, body), in the action log
  and on its approval card, and your Yahoo address on each send card;
- up to ten task titles with their due dates in the Today row, task titles in the action log and
  on delete cards, and the full title and description of every task Ahmad adds.

The text Ahmad only reads (Yahoo email bodies, task descriptions) is not stored there.

## Notes

- Built and tested offline only (fake IMAP, SMTP and Todoist servers). The first live use is
  the real test; if something fails, Snafi says so and nothing is changed.
- Yahoo usually keeps a copy of what Snafi sends in **Sent**; if it does not, the email still
  went out (the outcome under Ahmad's reply says so).

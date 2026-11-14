# Snafi worker (steps 2 to 5)

The worker runs on Khalid's PC. It picks up jobs from the Snafi database mailbox, asks
Ahmad's brain for a reply, decides every proposed action in code, and writes the results
back for the app. The plan is `docs/snafi/PRD.md`.

## How a chat message is handled

1. The app saves Khalid's message and queues a `chat.reply` job (chat lane).
2. The worker claims it, reads the recent conversation, and asks the brain. The brain gets
   **text only** and must answer with JSON: a reply plus proposed actions. It has no tools.
3. The **permission gate** (`gate.py`, levels fixed in `tools.py`) decides each action:
   Level 1 runs, Level 2 runs and is logged with Undo, Level 3 opens an approval card,
   Level 4 and unknown tools are refused with the reason. The brain's own claims are ignored.
4. The **honesty check** (`honesty.py`) removes any "done / sent / saved / تم / أرسلت / حفظت"
   the reply has not earned; code adds the real outcome of each action underneath.
5. Approve or Reject on a card (or Undo on a logged action) queues a follow-up job; after
   Approve the action runs and Ahmad carries on from the real result. The card shows every
   argument in full and Approve is bound to their SHA-256; cards expire after 24 hours; an
   approved action is claimed approved -> executing once and never runs twice, even after a
   timeout or a database error.

Outside content only ever reaches the brain inside `<data>` blocks, as information.

## Adapters, chosen in `worker.yaml`

| Service | Setting | Providers |
| --- | --- | --- |
| Brain | `brain.provider` | `claude_api` (Claude API, `claude-haiku-5-5`, text only, key in Credential Manager; the configured brain), `gemini_api` (Gemini API; switched off), `agy` (Antigravity CLI; switched off, see below), `fake` (offline) |
| Database | `store.provider` | `supabase_rest`, `memory` (offline) |
| Mail (Gmail account) | `mail.provider` | `gmail` (step 3), `fake` (offline), `none` |
| Mail (Yahoo account) | `yahoo.provider` | `yahoo_imap` (step 4), `fake` (offline), `none` |
| Calendar | `calendar.provider` | `google_calendar` (step 3), `fake` (offline), `none` |
| Files | `files.provider` | `google_drive` (step 3), `fake` (offline), `none` |
| Tasks | `tasks.provider` | `todoist` (step 4), `fake` (offline), `none` |

Switching is one line in `worker.yaml`; tests prove that only `brain/` knows the brain and
only `store/` knows the database.

## Lanes, retry, heartbeat, backup

- **Lanes:** `chat` (90 s per job) and `background` (10 min), each in its own thread.
- **Retry:** a failure that may pass (busy service, timeout) is retried once (chat after
  5 s, background after 60 s); after the second failure Ahmad says plainly that he could not
  answer.
- **Heartbeat:** every 15 s into `worker_status`; the app shows "PC offline" after 45 s, and
  messages wait in the queue.
- **Backup:** every day at 03:30 Jeddah time (and at start if the last one is over 24 h old),
  every Snafi table goes to `teams/coordination/snafi-backups/snafi-backup-YYYYMMDD-HHMM.json.gz`,
  with each table's row count and SHA-256. The newest 30 days are kept. The result is shown
  in the app's menu. No AI call.

## Google: Gmail, Calendar, Drive (step 3)

Setup for Khalid: `docs/snafi/GOOGLE_SETUP.md`. The adapters are in `google/` (raw HTTPS
with the standard library, Google's API hosts only, redirects refused); the tools and their
levels are in `personal_tools.py`:

| Level | Tools |
| --- | --- |
| 1 | `search_mail`, `read_mail`, `list_events`, `search_files`, `read_file` |
| 2 (Undo) | `create_draft` (Undo deletes the draft), `create_event` with only Khalid (Undo deletes it, only if Snafi made it) |
| 3 (card) | `send_email`, `invite_to_event`, `delete_event` (guests not notified), `delete_draft` |
| 4 | more than 5 people in one send or invite; forwarding, filters, sharing, trashing |

- **Outside content is untrusted data.** What a read returns goes to the brain once, in one
  follow-up call in the same turn, inside `<data source="untrusted_...">`. In that call no
  further read runs and any Level 3 action becomes a card marked "suggested after reading
  outside content". The text Ahmad reads (email bodies, file text, event descriptions) is
  never logged or stored in Supabase. What is stored there (and so in the daily backup): the
  chat shows senders, subjects and event titles and Ahmad's own summary, and the action log
  and approval cards keep the arguments of what Ahmad wrote, so a draft's or a sent email's
  whole body (SEC-83).
- **Today feed** (`today_feed.py`): every 10 minutes, with no brain call, the next event and
  up to five important unread emails (unread, inbox, Important, last 24 h; sender name and
  subject only) go to the `today_feed` table. It is a cache, so it is not in the backup.
- **Not connected yet** does not stop the worker: the tools say so, Today shows how to
  connect, and a new connection is picked up within five minutes without a restart.

## Yahoo Mail and Todoist (step 4)

Setup for Khalid: `docs/snafi/YAHOO_TODOIST_SETUP.md`. The adapters are `yahoo/mail.py` and
`todoist/tasks.py`, standard library only; the tools and levels stay in `personal_tools.py`.

- **Yahoo:** IMAP over TLS to `imap.mail.yahoo.com:993` (Inbox opened read-only, messages
  fetched with `BODY.PEEK`, so reading never marks anything read; drafts saved with APPEND to
  Drafts) and SMTP over TLS to `smtp.mail.yahoo.com:465` (send, only after Approve; Bcc only on
  the envelope). The hosts are fixed in code and the certificate is always checked. Undo of a
  draft deletes only that draft (`UID EXPUNGE`; refused if the server has no UIDPLUS).
  Yahoo ids are `y<UIDVALIDITY>_<UID>` (drafts `yd...`), so an id says its account.
- **Both inboxes:** every mail tool takes `account` (`gmail` or `yahoo`); `search_mail` without
  one reads both, marking each line `[Gmail]` or `[Yahoo]`. A reply goes from the account the
  email came from. Every outcome, log entry and card names the account (a send card: "Send
  from Yahoo (address) to ..."), and the honesty check removes a sentence about mail that names
  only the other account.
- **Todoist:** the Todoist API v1 over HTTPS (`api.todoist.com` only, redirects refused, the
  token only in the Authorization header).

| Level | Tools |
| --- | --- |
| 1 | `list_tasks` (`when`: `today`, the default, for today and overdue; `all` for every open task grouped by due date, at most 30 shown and "and N more"), `search_tasks` |
| 2 (Undo) | `add_task` (Undo deletes it, only if unchanged), `complete_task` (Undo reopens it; a repeating task gets its date back), `reschedule_task` (Undo puts the old date back) |
| 3 (card) | `delete_task` (refused if the task changed after Approve) |

- **Limits:** a `limit` above a tool's maximum (or below 1) is brought into range, not refused,
  for every tool; the brain is told each maximum (`tool_types.py`, `prompt.py`).
- **Today feed:** also up to five important Yahoo emails (unread, Inbox, last 24 hours, not a
  newsletter, list or automatic email) and up to ten Todoist tasks due today or overdue
  (title, due, priority, overdue). `yahoo_status` and `todoist_status` say what Today shows.
- **Not connected yet** does not stop the worker, and a login stored later with set-secrets is
  picked up within five minutes (`personal/credentials.py`), or at once after a refusal.

## Proactive Ahmad (step 5)

Setup for Khalid: `docs/snafi/PUSH_SETUP.md`. No brain call anywhere in it.

- **Scheduler** (`proactive/scheduler.py`): a thread, every 30 seconds, each job short and on its
  own: release what was held for prayer time, fire due reminders (`reminders.fired_at` is set in one
  conditional update first, so a reminder goes off once), the morning brief once a day from
  `user_settings.brief_time` (default 07:00, until 5 hours after), and the mail watch every
  `proactive.mail_minutes` (10). Gmail's "truly important" is `watch_unread` in `google/gmail.py`
  (unread, Inbox, Important, Primary); Yahoo's is in `yahoo/mail.py` (the Today rule plus a sender
  Khalid emailed from Yahoo in 90 days, from Sent's To/Cc/Bcc, read-only, kept 6 hours in memory).
  The first run for each account only learns (`mail-learned:<account>` in the ledger).
- **The one door** (`proactive/notify.py`): every message goes through `Notifier.deliver`, which
  enforces never twice (`notifications` UNIQUE `(user_id, dedupe_key)`, inserted with
  `insert_once`, then claimed `new/held -> delivering` before its card and push), no repeat of the
  same text in 24 hours, 20 minutes of quiet after each adhan (`proactive/prayer.py`, a port of the
  app's adhan, checked by both suites against `tests/fixtures/snafi_prayer_times.json`), and the
  daily cap (`user_settings.daily_cap`, default 10, reminders not counted).
- **Web Push** (`proactive/webpush.py`): RFC 8291 encryption and VAPID with `cryptography`. Posts
  only to Apple, Google (FCM), Mozilla and Microsoft push hosts, never follows a redirect, and
  pushes only `{kind, language, id}`; the service worker shows fixed text. 404/410 removes the
  phone; five failures in a row too. Without `SNAFI_VAPID_PRIVATE_KEY` and `SNAFI_PUSH_CONTACT`
  (set-secrets makes the key; `set-secrets --push-key` prints the public half) cards still appear,
  silently. The push key is read when the worker starts: restart it after set-secrets.
- **Times** Khalid reads (cards, the brief, chat tool results, the brain's instructions) are
  12-hour with AM/PM or ص/م (`clock.py`).
- **Backup and clearing (SEC-127):** only `user_settings` is backed up. `cards`, `notifications` and
  `push_subscriptions` never are (the phone subscribes again). Once an hour `Notifier.prune` deletes
  cards and ledger rows older than 30 days (the `mail-learned:*` markers stay); the ledger keeps no
  card text once a card is shown. A restore marks past reminders fired, so they don't go off again.
- **Yahoo sender check (SEC-125):** the mail watch pushes a Yahoo email only when the topmost
  Authentication-Results header is Yahoo's own (`*.yahoo.com`) and says `dmarc=pass` for the From
  address's domain (`yahoo/mail.py` `sender_verified`).

## The Claude API brain (configured)

`brain/claude_api.py` sends one text request to Anthropic's Messages API (`claude-haiku-5-5`, low
effort, thinking off, the reply forced into a JSON schema), with the key in the `x-api-key` header
(never in the URL, never logged, never resent on a redirect: redirects are refused). The request
holds only model, max_tokens, system, messages, thinking and output_config: no tools, no server
tools, no MCP. A reply with any block other than text, or that stops for a tool, is refused, or is
cut off, is rejected; any action it proposes is data for the permission gate. It is plain HTTP with
the standard library: the Anthropic SDK is not installed in the worker's hash-pinned Python. This is
REEMA's only Anthropic call; `tests/test_no_api_guard.py` allows it in this file and nowhere else.
The monthly spend limit is a setting in the Claude Console, not something this code enforces.

**Daily call limit (SEC-47):** every brain call, retries included, counts against
`brain.daily_call_limit` (300) for the day in Jeddah time (`brain/limit.py`, count in
`%APPDATA%\REEMA\snafi-worker\brain_calls.json`). At the limit the brain is not called and Ahmad
says he can answer again tomorrow. A damaged count fails closed; `snafi.cmd reset-brain` removes it.

## The Gemini API brain (switched off)

`brain/gemini_api.py` sends one text request to the Gemini API's `generateContent` endpoint, with
the key in the `x-goog-api-key` header. It declares no tools. It was the brain on Nov 13, 2026,
before the Claude API; set `brain.provider: gemini_api` (and its model) to use it again.

## The agy brain and its lockdown (switched off)

Switched off on Nov 13, 2026: the live proof showed agy's `search_web` tool running although
every tool was denied, and agy documents no setting or deny rule that covers it. The code and
its tests stay, so the proof can be run again if agy ever adds one.

`agy` runs under the separate `worker` Windows user, signed in with a Snafi-only Google
account, so Khalid's own agy setup is untouched. Every call (`brain/agy.py`) uses headless plan
mode, the terminal sandbox, one-run settings that deny every tool (files, shell, URLs, MCP),
`useG1Credits: false` (no paid credits), a fresh empty folder and a cleaned environment, and
forces the reply into a JSON schema.

**Tripwire:** any tool step that succeeded, or any file appearing in its folder, throws the
reply away and pauses the brain (`brain/pause.py`). Chat then says Ahmad is paused for a safety
check until Khalid looks and runs `snafi.cmd reset-brain`.

**Readiness:** the worker uses agy only when no MCP servers or plugins are configured for
`worker` and a passing lockdown proof exists for this exact agy version and lockdown
settings. A new agy version pauses the brain until the proof is run again.

**The proof** (`snafi.cmd prove`, as `worker`) runs agy six times: a normal reply, then
attempts to write files, run commands, read a file outside its folder, fetch a URL and use MCP.
It passes only if nothing happened. It uses six requests of the free quota.

## Secrets: Windows Credential Manager (Khalid's own)

Since Nov 13, 2026 the worker runs as Khalid's own Windows user. The separate `worker` user and
its setup are kept dormant (unused) for a possible return to agy.

Stored once, as Khalid, in a normal (not admin) PowerShell, with `C:\SnafiWorker\snafi.cmd set-secrets`, which asks for each
value and never shows the key (`--status` lists which are stored, `--remove` deletes them):

| Name | What |
| --- | --- |
| `SNAFI_SUPABASE_URL` | the project URL |
| `SNAFI_SUPABASE_SECRET_KEY` | the secret key (`sb_secret_...`) |
| `SNAFI_OWNER_USER_ID` | Khalid's Supabase user UID |
| `SNAFI_BACKUP_SIGNING_KEY` | made at random by the script; signs every backup |
| `ANTHROPIC_API_KEY` | the Claude API key (`sk-ant-...`, never an admin key); asked for only while `brain.provider` is `claude_api` |
| `GEMINI_API_KEY` | the Gemini API key; asked for only while `brain.provider` is `gemini_api` |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | the Desktop app OAuth client from Google Cloud; asked for only while a Google service is chosen |
| `GOOGLE_REFRESH_TOKEN` | never typed: written by `snafi.cmd connect-google` after Khalid signs in |
| `YAHOO_EMAIL`, `YAHOO_APP_PASSWORD` | Khalid's Yahoo address and a Yahoo app password (16 letters, typed hidden); asked for only while `yahoo.provider` is `yahoo_imap` |
| `TODOIST_API_TOKEN` | the Todoist API token (40 characters, typed hidden); asked for only while `tasks.provider` is `todoist` |

Each is a generic credential "REEMA-Snafi:<NAME>" for Khalid's user, encrypted by Windows
(DPAPI). There is no plain-text secrets file. Claude Code also runs as Khalid, so Windows itself
no longer keeps sessions away from these keys, the logs in `%APPDATA%\REEMA\snafi-worker` or the
backups: only Claude Code's deny rules (`.claude/settings.json`) and its guard
(`.claude/hooks/dev_guard.py`) do. They are a backstop, not an OS boundary: a program a session
runs could still read them if it does not name them.

## Where it runs

First Khalid builds Ahmad's prompt text as himself, not as admin
(`.venv\Scripts\python.exe -m src.snafi_worker.prompt --write src\snafi_worker\ahmad_base.txt`;
the file is gitignored). Then `src/snafi_worker/deploy/deploy.ps1` (admin, by Khalid) locks
`C:\SnafiWorker`, refuses if `src/snafi_worker` has uncommitted changes, copies only this folder
to `C:\SnafiWorker\app` (no REEMA code runs as admin), gives the worker its own private Python
3.12.10 in `C:\SnafiWorker\python` (python.org's official NuGet package: a zip, no installer,
checked against its pinned SHA-256 and unpacked fresh on every deploy; no other Python on the PC
is touched or needed), installs exactly pyyaml 6.0.3 and tzdata 2026.6 into it as hash-checked wheels
(`deploy/requirements-worker.txt`), and sets permissions: Khalid (and so the worker) may read and
run `C:\SnafiWorker` but not change it (Administrators own it), and may change files in the
backups folder; the dormant `worker` user stays denied on `D:\Projects` and
`D:\Antigravity_Projects`. `deploy/install_task.ps1` (admin) registers the task to start when
Khalid signs in, as Khalid, not elevated, with no password stored; it runs while he is signed in.
Re-run the deploy after every worker update.

## Commands (as Khalid in a normal PowerShell, except where noted)

```
C:\SnafiWorker\snafi.cmd check          settings and which secrets exist (never values)
C:\SnafiWorker\snafi.cmd set-secrets    store the secrets (asks; never shows the key)
C:\SnafiWorker\snafi.cmd prove          the live agy lockdown proof (agy only; switched off)
C:\SnafiWorker\snafi.cmd reset-brain    clear a safety pause after you have looked
C:\SnafiWorker\snafi.cmd once           answer waiting jobs, then stop
C:\SnafiWorker\snafi.cmd backup-now
C:\SnafiWorker\snafi.cmd restore BACKUP --verify | --to-sql OUT.sql | --to-database [--map-user OLD=NEW]
powershell -ExecutionPolicy Bypass -File src\snafi_worker\deploy\deploy.ps1         (admin, as Khalid)
powershell -ExecutionPolicy Bypass -File src\snafi_worker\deploy\install_task.ps1   (admin, as Khalid)
```

## Tests

`tests/test_snafi_worker_*.py` (offline; fake brain and memory store) and
`apps/snafi-web/tests/restore.test.ts` (a real backup restored into PGlite). The agy tests replay
recorded agy output; only `snafi.cmd prove` runs the real agy.

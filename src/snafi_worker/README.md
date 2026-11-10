# Snafi worker (step 2)

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
| Brain | `brain.provider` | `agy` (Antigravity CLI, `gemini-3.8-flash-low`, locked down; the configured brain), `gemini_api` (text only; switched off, needs a key), `fake` (offline) |
| Database | `store.provider` | `supabase_rest`, `memory` (offline) |

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

## The agy brain and its lockdown

`agy` runs under the separate `snafi-worker` Windows user, signed in with a Snafi-only Google
account, so Khalid's own agy setup is untouched. Every call (`brain/agy.py`) uses headless plan
mode, the terminal sandbox, one-run settings that deny every tool (files, shell, URLs, MCP),
`useG1Credits: false` (no paid credits), a fresh empty folder and a cleaned environment, and
forces the reply into a JSON schema.

**Tripwire:** any tool step that succeeded, or any file appearing in its folder, throws the
reply away and pauses the brain (`brain/pause.py`). Chat then says Ahmad is paused for a safety
check until Khalid looks and runs `snafi.cmd reset-brain`.

**Readiness:** the worker uses agy only when no MCP servers or plugins are configured for
`snafi-worker` and a passing lockdown proof exists for this exact agy version and lockdown
settings. A new agy version pauses the brain until the proof is run again.

**The proof** (`snafi.cmd prove`, as `snafi-worker`) runs agy six times: a normal reply, then
attempts to write files, run commands, read a file outside its folder, fetch a URL and use MCP.
It passes only if nothing happened. It uses six requests of the free quota.

## Secrets: Windows Credential Manager (snafi-worker)

Stored once, as `snafi-worker`, with `C:\SnafiWorker\snafi.cmd set-secrets`, which asks for each
value and never shows the key (`--status` lists which are stored, `--remove` deletes them):

| Name | What |
| --- | --- |
| `SNAFI_SUPABASE_URL` | the project URL |
| `SNAFI_SUPABASE_SECRET_KEY` | the secret key (`sb_secret_...`) |
| `SNAFI_OWNER_USER_ID` | Khalid's Supabase user UID |
| `SNAFI_BACKUP_SIGNING_KEY` | made at random by the script; signs every backup |
| `GEMINI_API_KEY` | only if `brain.provider` is ever switched to `gemini_api`; not asked for with agy |

Each is a generic credential "REEMA-Snafi:<NAME>" for `snafi-worker`, encrypted by Windows (DPAPI).
Khalid's own account, and so any Claude Code session, cannot read another user's credentials,
profile or logs. There is no plain-text secrets file.

## Where it runs

`src/snafi_worker/deploy/deploy.ps1` (admin, by Khalid) copies only this folder to
`C:\SnafiWorker\app`, builds Ahmad's prompt text (`ahmad_base.txt`), creates
`C:\SnafiWorker\venv` from machine-wide Python 3.12.10 with exactly pyyaml 6.0.3 and tzdata
2026.6, and sets permissions: `snafi-worker` may read and run `C:\SnafiWorker` but not change it,
is denied on `D:\Projects` (and `D:\Antigravity_Projects`), and may write only to the backups
folder. `deploy/install_task.ps1` (admin) registers the task to start with Windows as
`snafi-worker`. Re-run the deploy after every worker update.

## Commands (as snafi-worker, except where noted)

```
C:\SnafiWorker\snafi.cmd check          settings and which secrets exist (never values)
C:\SnafiWorker\snafi.cmd set-secrets    store the secrets (asks; never shows the key)
C:\SnafiWorker\snafi.cmd prove          the live lockdown proof
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

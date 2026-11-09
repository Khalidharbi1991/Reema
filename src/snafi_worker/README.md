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
| Brain | `brain.provider` | `gemini_api` (text only, `gemini-3.5-flash-lite`), `fake` (offline) |
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

## Secrets: Windows Credential Manager

Stored once by Khalid, for his Windows user, with
`.venv\Scripts\python.exe -m src.snafi_worker.set_secrets`, which asks for each value and
never shows the keys (`--status` lists which are stored, `--remove` deletes them):

| Name | What |
| --- | --- |
| `SNAFI_SUPABASE_URL` | the project URL |
| `SNAFI_SUPABASE_SECRET_KEY` | the secret key (`sb_secret_...`) |
| `SNAFI_OWNER_USER_ID` | Khalid's Supabase user UID |
| `GEMINI_API_KEY` | the Gemini API key |
| `SNAFI_BACKUP_SIGNING_KEY` | made at random by the script; signs every backup |

Each is a generic credential "REEMA-Snafi:<NAME>", encrypted by Windows (DPAPI) under
Khalid's login. There is no plain-text secrets file. No Claude Code session or agent may
read them, the logs or the backups, or run the worker (`.claude/settings.json` deny rules
and `.claude/hooks/dev_guard.py`; a backstop, not a full guarantee). Keys are sent only in
request headers and never logged; logs (`%APPDATA%\REEMA\snafi-worker\logs\`) hold job ids
and status only.

## Commands (run by Khalid)

```
python -m src.snafi_worker --check        # settings and which secrets exist (never values)
python -m src.snafi_worker --once         # answer waiting jobs, then stop
python -m src.snafi_worker --backup-now
python -m src.snafi_worker                # run until stopped
python -m src.snafi_worker.restore BACKUP --verify | --to-sql OUT.sql | --to-database [--map-user OLD=NEW] [--accept-unsigned]
python -m src.snafi_worker.set_secrets [--status | --remove]
powershell -ExecutionPolicy Bypass -File src\snafi_worker\install_task.ps1   # start at logon
```

## Tests

`tests/test_snafi_worker_*.py` (offline; fake brain and memory store) and
`apps/snafi-web/tests/restore.test.ts` (a real backup restored into PGlite).

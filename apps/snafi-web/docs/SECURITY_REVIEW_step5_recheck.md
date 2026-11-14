# Snafi: security re-check of step 5 (Agent 16)

Nov 15, 2026 · reviewer: Agent 16 (`reema-agent16-security`) · Khalid's request: "Agent 16 re-checks the six fixes (SEC-119, 121, 122, 123, 126, 128)".

**How this file is used (for Ahmad).** Like `SECURITY_REVIEW_step5.md`, this file holds one round. Ahmad adds a pointer to it at the top of `SECURITY_REVIEW.md`. For the rows it lists (SEC-119 to SEC-128) and the new rows SEC-130 to SEC-133, this file is the current status. Every other row stands as written.

**This round covers:**
- the six fixes merged to main in commit fb39378 (`apps/snafi-web/.reema/security_diff_step5_fixes.patch`: SEC-119, 121, 122, 123, 126, 128);
- branch `fix/snafi-step5-decisions` at commit 4da3303 against main (`apps/snafi-web/.reema/security_diff_step5_decisions.patch`). It holds Khalid's decisions: the SEC-125 Yahoo sender check, SEC-127 clearing after 30 days and taking the tables out of backups, 12-hour times on cards, in the log and in chat results, and docs.

**What I read:**
- Both patches in full.
- These current files in full: `src/snafi_worker/yahoo/mail.py`, `proactive/notify.py`, `proactive/scheduler.py`, `restore.py`, `store/base.py`, `backup.py`, `clock.py`, `tools.py`, `tool_types.py` and `apps/snafi-web/supabase/migrations/0008_proactive.sql`.
- `personal_tools.py` lines 430-748 (Todoist, `shown_time`, `_due_text`, `_prepare_delete_task`, `_delete_task`, `_fmt`, `_due_display`, the tool table).
- For SEC-128: `.claude/hooks/dev_guard.py` lines 150-270 (the `SNAFI_PRIVATE` patterns and `_snafi_reason`), `.claude/settings.json` in full, `tests/test_snafi_worker_guard.py` lines 1-90, and `tests/test_claude_code_setup.py` lines 1-60 only.

**What I did not review:**
- The rest of `dev_guard.py` and `test_claude_code_setup.py`.
- `engine.py`, including how `describe` text is used and the honesty check.
- The real Todoist adapter, so I don't know the exact format of `task.due` (see SEC-131).
- `_check_event`, `_check_task` and `_check_reschedule`.
- `store/supabase_rest.py` this round (I relied on the earlier round for `select` ordering and `insert_once`).
- `webpush.py` beyond the hunk.
- The web app, which neither patch changes except migration 0008.
- Yahoo's real header behaviour, which I cannot see (see SEC-130).

**I ran nothing**: no tests, no build, no git, no hook, no scanner and no network call. "Python 1384 passed, web 169 passed, eslint and tsc clean" is Ahmad's report. I checked that the tests named below exist; I did not check that they pass. This review is not a certification; Khalid decides.

## Summary

**Open Critical 0, open High 0. Neither the six fixes on main nor branch `fix/snafi-step5-decisions` blocks the merge to main.**

- **Closed:** SEC-119, SEC-123, SEC-126 and SEC-128 are fixed as recommended. SEC-125 and SEC-127 are built as Khalid decided and are closed as asked.
- **Still open, narrowed:** SEC-121 (a row stuck in `delivering` is still lost without a word) and SEC-122 (the same-day brief can come again after a restore). Both stay Low, for Khalid to accept or have finished.
- **SEC-120** is Medium, accepted by Khalid in his own words (with SEC-80 and SEC-105).
- **New:**
  - SEC-130 (Low): the Yahoo check reads the *first* `dmarc=` in the topmost header and assumes Yahoo always adds its own header.
  - SEC-131 (Low): the delete-task approval card can now show a wrong hour.
  - SEC-132 (Info): what SEC-127 leaves behind.
  - SEC-133 (Info): `shown_time` lets an `OverflowError` through.

**For Khalid to decide:** Low SEC-121, SEC-122, SEC-130, SEC-131. Info SEC-132, SEC-133 (and SEC-124, SEC-129 from the last round, unchanged).

## Answers to the points Ahmad named

1. **Can a forged lower header, a look-alike server name or a subdomain trick pass `sender_verified`?**
   - **A forged lower header: no.** Only `results[0]` is read, so a header the sender put below Yahoo's own is never looked at. The test with a forged pass below a real fail exists.
   - **A look-alike name: no.** `YAHOO_AUTHSERV` is a `fullmatch` of `[a-z0-9.-]{1,200}\.yahoo\.com` with `re.ASCII`, applied to the text before the first `;`. So `yahoo.com.evil.example`, `evilyahoo.com`, `mx.yahoo.com.` with a trailing dot, a version token or a comment all fail. That fails closed: no push, but the email still shows on Today.
   - **Domain matching is exact,** not a suffix: `header.from` must equal the From address's domain, so `sub.example.com` does not stand for `example.com`.
   - **The name check is not the control.** The authserv-id is plain text that anyone can write; what protects Khalid is the header's position. Two gaps remain, both in SEC-130: (a) if Yahoo ever delivers a message without adding its own Authentication-Results, the sender's forged header becomes the topmost and passes; (b) the parser takes the first `dmarc=` anywhere in the header, so text Yahoo copies from the sender into an earlier field could carry a fake `dmarc=pass header.from=…` ahead of Yahoo's real result.
   - **DMARC proves the domain, not the person.** Anyone who can send DMARC-passing mail for Sara's domain can pass as `sara@` (see SEC-130).
2. **Does the IMAP `HEADER.FIELDS` fetch keep the headers in message order?**
   - On the client side, yes. `imaplib` returns the literal unchanged, `message_from_bytes` keeps the line order, and `Message.get_all` returns the values in that order.
   - On the server side, RFC 3501 defines `HEADER.FIELDS` as a subset of the message's header. Servers I know return the lines in message order, but I cannot verify that for Yahoo. The tests build the message with `message_from_bytes` directly, so they do not cover the server.
   - This is the one unverified link in the topmost-header rule. Khalid's check at first use is in SEC-130.
3. **Does the pruning, or taking the ledger out of backups, break never-twice?** I found no case where something goes out twice within 30 days, or comes back after 30 days in practice.
   - **A reminder whose ledger row is pruned:**
     - `reminders()` selects only rows with `fired_at` null, so once `fired_at` is set the ledger row is not needed. `fired_at` is set in the same pass right after `deliver`; if that update fails, the next pass gets `duplicate` and sets it again.
     - A reminder could fire again only if `fired_at` stayed null for 30 days while its ledger row was pruned. That needs the database to refuse that update on every 30-second pass for a month.
   - **A mail id seen again after 30 days:**
     - Gmail asks for `newer_than:1d`. Yahoo asks for IMAP `SINCE` two days back (by the server's receive date), then keeps only Date ≥ 24 hours ago. So a 30-day-old email cannot come back unless the server gives it a new receive date (for example a client re-uploading it with APPEND) *and* it is unread, from a known correspondent and passes DMARC.
     - Yahoo gives a moved email a new UID, so it has a new key whether or not anything is pruned. That was already true before.
     - One edge: an email whose Date header and receive date both fail to parse skips the 24-hour check (`if summary.date:`). That is old code, Info, and changed by nothing here.
     - The `mail-learned:*` markers are kept, so the watch does not learn everything again.
   - **The brief and test pushes:** `brief:<date>` and `test:<job id>` never come back.
   - **Prune order and safety:**
     - `select` defaults to `created_at` ascending, so each batch starts with the oldest rows and the loop stops at the first batch with nothing old.
     - Cards are deleted before notifications. `cards.notification_id` is `on delete set null`, so the order cannot cause a foreign-key error.
     - A card made up to 20 minutes after its ledger row (held for prayer time) is deleted on a later hourly pass.
   - **A restore without the ledger:**
     - New backups hold neither `notifications` nor `cards`. After a restore, `neutralise` marks every past-due reminder fired (the SEC-122 fix), drops the `mail-learned:*` markers (none in new backups), and the watch's first run only learns.
     - A reminder due in the future still goes off once, as it should. Live `push.test` jobs are cancelled.
     - What remains: the brief can come again on the day of a restore (SEC-122, narrowed). Older SCHEMA-5 backups that still hold ledger and card rows load as before and are pruned within an hour if more than 30 days old.
4. **Do the display changes alter anything hashed or compared?** No.
   - `args_hash` is SHA-256 over `{"tool", "args"}` (`tool_types.py`), never over `describe` text.
   - `_prepare_delete_task` still stores `task_due = _due_text(task)`, and `_delete_task` still compares `(_short(task.content, 200), _due_text(task))` exactly. `_due_text` is unchanged.
   - `_due_display` and `shown_time` only build text for the card, the log and chat. Undo data (`task_due` undo with `due` and `due_string`, `content_sha256`) is unchanged.
   - One side effect: because `task_due` is cut to 16 characters with its offset removed, the delete card can now show a definite but wrong hour (SEC-131).
   - I did not read how the honesty check uses result text (`engine.py`). If it matched the old ISO strings, Ahmad's test run would be the evidence; I have not verified it.

## Status of the rows

| ID | Severity | New status | Note to add (Nov 15, step 5 re-check) |
| --- | --- | --- | --- |
| SEC-119 | Medium | **Closed** (re-checked) | `notify.py` `_release` skips `_repeat` when `kind == "reminder"`. A reminder still goes once by its UNIQUE `reminder:<id>` key and `fired_at`. `test_sec119_the_same_reminder_text_on_two_days_both_go_off` exists. Side effect, within Khalid's SEC-120 acceptance: two identical reminders the brain sets now both alert. |
| SEC-120 | Medium | **Accepted** (Khalid, Nov 14: "I accept it, the same as SEC-80 and SEC-105") | No code change. |
| SEC-121 | Low | **Open, narrowed** (partly fixed) | Fixed: (1) the reminder's ledger row is written before `fired_at`, so an error before the row exists is retried; (2) `release_held` releases `new` rows older than 2 minutes, and the conditional claim keeps it to once (`test_sec121_…` exists). Still open: (3) if the claim succeeds and the card insert or the push then fails, the row stays `delivering`. For a reminder, the next pass gets `duplicate` and sets `fired_at`, so the reminder is lost without a word. The test only reaches the retry by resetting the row to `new` by hand. Ahmad calls this "by design" (never twice wins over at least once). Khalid decides: accept it, or have recommendation (b) from the last round built. That is: for `delivering` rows older than about 10 minutes, insert the card with on-conflict-ignore (`cards.notification_id` is UNIQUE) and mark the row `silent` without a push. |
| SEC-122 | Low | **Open, narrowed** (reminders and mail fixed) | `neutralise` marks every reminder with a past or unreadable `due_at` and no `fired_at` as fired at restore time, and drops `mail-learned:*` rows (`test_sec122_…` exists). Since SEC-127, new backups hold no ledger at all, so mail relearns by itself. Left: the morning brief can come a second time on the day of a restore. Optional fix: `neutralise` adds a `cancelled` `brief:<today>` row when today's brief time has passed (`to_database` still inserts `notifications`). |
| SEC-123 | Low | **Closed** (re-checked) | `load_private_key` turns any error (bad base64, wrong length, scalar 0 or above the order) into a fixed `PushError` `from None`, with no value in the message. `build_scheduler` also catches any other exception and logs only its type name, so the worker starts with push off. `test_sec123_…` covers `""`, non-base64, a short value, `0xff`×32 and `0x00`×32. |
| SEC-124 | Info | Open (unchanged) | |
| SEC-125 | Low | **Closed as built** (Khalid: "add the Yahoo sender-verification check") | `sender_verified` reads only the topmost Authentication-Results header, which must have a `*.yahoo.com` authserv-id, `dmarc=pass` and a `header.from` equal to the From address's domain. Anything else fails closed, and the email still shows on Today and in the brief. `AUTHENTICATION-RESULTS` is in `HEADERS`, so it is fetched with the summaries. The watch needs both a known address and `sender_verified`. The forged-lower, look-alike, wrong-domain, `dmarc=fail`/`none` and no-header cases are tested. Residuals: SEC-130. Part (2) of the old row (tell Khalid that the worker reads his Sent recipients) still stands. |
| SEC-126 | Info | **Closed** (re-checked) | `on conflict (endpoint) do update … where public.push_subscriptions.user_id = uid`, then `if not found then raise 'that push address is already in use'`. In PL/pgSQL, `FOUND` is false when the upsert neither inserts nor updates, so another user's row is never changed, even in the race. The same user saving again still updates. |
| SEC-127 | Low | **Closed as built** (Khalid: "clear cards and the sent record after 30 days, including in backups") | `Notifier.prune`, run hourly by `Scheduler.clear_old` (and on the first tick), deletes `cards` and `notifications` rows whose `created_at` is over 30 days old. Only `mail-learned:*` rows are kept, and they hold no text. `_finish` sets `notifications.card` to null on every outcome. `notifications` and `cards` moved from `TABLES` to `CACHE_TABLES`, so `export_tables` no longer backs them up (`test_sec127_…` checks that a private subject is not in the export). Logs carry counts only. Leftovers are listed in SEC-132. |
| SEC-128 | Info | **Closed** (re-checked) | `dev_guard.py` `SNAFI_PRIVATE` now includes `snafi_vapid_private_key`, matched on the lower-cased command. `test_snafi_worker_guard.py` has a Bash `python -c … os.environ.get('SNAFI_VAPID_PRIVATE_KEY')` case and a PowerShell `$env:SNAFI_VAPID_PRIVATE_KEY` case. Loading the key through the worker's code is already blocked by `secrets\.load`, `secret_store` and `snafi_worker[./]config\|services`. `SNAFI_PUSH_CONTACT` is not a secret and needs no entry. `settings.json` is unchanged; it still denies `~/AppData/Roaming/REEMA/**` and the backups for Read, Edit and Write, and runs the hook for Bash, PowerShell and the write tools. As before, the guard is a backstop, not a full guarantee (SEC-89). |
| SEC-129 | Info | Open (unchanged) | Note: the 500-row ledger scan now covers at most 30 days of rows, which makes the undercount in note (1) less likely. |

## New rows (append after SEC-129)

| ID | Severity | Status | File:line | What an attacker could do | Fix |
| --- | --- | --- | --- | --- | --- |
| SEC-130 | Low | Open (**new**, Nov 15 (step 5 re-check)) | `src/snafi_worker/yahoo/mail.py:115-138` (`sender_verified`: `re.search(r"(?:^\|[;\s])dmarc=([a-z]+)", rest)`, then `header.from=` searched after it) | **A stranger could still get a push and a Today card that look like they are from one of Khalid's correspondents, in three narrow cases.** (a) **Yahoo adds no header of its own.** The rule assumes Yahoo puts its Authentication-Results above everything the sender wrote. If any delivery path to the Inbox does not (Yahoo-to-Yahoo mail, an internal or forwarding path), the sender's own `Authentication-Results: mx.yahoo.com; dmarc=pass header.from=example.com` is the topmost and passes. The authserv-id is just text. (b) **The first match wins.** The parser takes the first `dmarc=` anywhere in the header. Yahoo writes `dkim=…; spf=…; dmarc=…` in that order, with `header.i=`, `header.s=` and `smtp.mailfrom=` values taken from the sender's message before `dmarc=`. If Yahoo ever copies such a value as a quoted string (RFC 8601 allows quoted values, and DKIM `i=` allows a quoted local part), text like `"x; dmarc=pass header.from=example.com"` would be read ahead of Yahoo's real `dmarc=fail`. (c) **DMARC proves the domain only.** Anyone who can send DMARC-passing mail for the correspondent's domain (a coworker on a shared company domain, a misconfigured domain) passes as any address there. Big providers such as Gmail do not let one user send as another, so this is narrow. In every case the attacker also needs the address of someone Khalid emailed from Yahoo, and the result is a phishing line in Snafi's trusted screen, within the daily cap. Nothing is sent or read. Hence Low. | Agent 14, small: (1) refuse unless the topmost header has exactly one `dmarc=` token and exactly one `header.from=` token, and take `header.from` only from the same result (the text between that `dmarc=` and the next `;`). (2) Optional: also refuse when more than one Authentication-Results header claims a `*.yahoo.com` authserv-id. Yahoo should strip forged ones (RFC 8601 §5), so a second one means something is wrong. Add tests for an injected `dmarc=pass` inside an earlier `header.i="…"` value and for two Yahoo-named headers. Khalid, at first use: in Yahoo Mail, open one real email from a correspondent (one from a `@yahoo.com` sender and one from Gmail), choose "View raw message", and check that the first Authentication-Results line is Yahoo's own with `dmarc=pass`. That also confirms (a) and the header order (point 2), which I cannot check. |
| SEC-131 | Low | Open (**new**, Nov 15 (step 5 re-check)) | `src/snafi_worker/personal_tools.py:461-464` (`_due_text`: `task.due[:16]`, offset dropped), `:650-652` (`_prepare_delete_task`), `:682-692` (`_due_display`: `shown_time(head.replace(" ", "T"))`, read as Jeddah time) | **The delete-task approval card (Level 3) can show the wrong hour.** `task_due` is the stored due cut to 16 characters, so any offset is lost. `_due_display` now reads that offset-less value as Jeddah time. If the Todoist adapter keeps a timed task's due in UTC (`…T06:00:00Z`) or any offset other than +03:00, the card says "due Sat 21 Nov 6:00 AM" for a task due at 9:00 AM. Before, it showed the raw `2026-11-21 06:00`, which was ambiguous but not labelled as local time. The delete is still bound to the exact task (content and `_due_text` are compared before deleting), so the wrong task cannot be deleted. But SEC-13's rule is that a card shows exactly what will run, and Khalid may use the time to tell two tasks apart. I did not read the real Todoist adapter, so whether its `due` carries a non-+03:00 offset is unverified. The chat results (`_due_shown`, `_local_time`) use the full value and are right. | Agent 14: in `_prepare_delete_task`, add a display-only field (for example `task_due_shown = _due_shown(task, "en")` plus the Arabic one, or the full `task.due` as `task_due_at`) and show that on the card. Keep `task_due` and the exact comparison as they are. Add a test with a task due `2026-11-21T06:00:00Z` that expects "9:00 AM". |
| SEC-132 | Info | Open (**new**, Nov 15 (step 5 re-check)); notes on what SEC-127 leaves | `src/snafi_worker/backup.py:33` (`SCHEMA = 5` and its comment); `restore.py:34-35` (`ORDER` still lists `notifications` and `cards`); `notify.py` `_finish` | **Small leftovers, none a defect.** (1) Backups made between the step 5 merge and this branch still hold `cards` and `notifications.card`. They are deleted by the normal 30-day backup pruning, so "no copy older than 30 days" holds from about 30 days after the step 5 worker first ran. Ledger rows finished before this change keep their `card` text until the 30-day prune. (2) `restore` still accepts those two tables from old backups, which is right for old files, and `prune` clears them within an hour if they are over 30 days old. (3) `SCHEMA` is still 5 and its comment still says the backup holds "notifications, cards". Only documentation, but a restore cannot tell an old SCHEMA-5 file from a new one. (4) Clearing runs hourly, so a row can live up to about 30 days and 1 hour, or a little longer for a card made after its ledger row. | Optional (Agent 14): set `SCHEMA = 6` with a corrected comment. Ahmad: tell Khalid in plain words that backups from Nov 14 still hold some card text until they age out, or that he can delete those dated files himself. |
| SEC-133 | Info | Open (**new**, Nov 15 (step 5 re-check)) | `src/snafi_worker/personal_tools.py:438-451` (`shown_time`: catches only `ValueError`) | **A brain-chosen date at the edge of the calendar can break one chat turn.** `datetime.fromisoformat("0001-01-01T00:00+05:00").astimezone(tz)` and similar values near year 9999 raise `OverflowError`, which is not caught, inside `describe` for `create_event`, `invite_to_event`, `add_task` and `reschedule_task` (unless their validators reject such years; I did not read them). The result is an error for that one action, not a wrong action. | Optional (Agent 14): catch `(ValueError, OverflowError)` in `shown_time` and show the value as it came. |

**Open Critical: 0. Open High: 0.** The fixes on main and branch `fix/snafi-step5-decisions` do not block the merge. For Khalid to decide: Low SEC-121 and SEC-122 (narrowed), and new SEC-130 and SEC-131. Info: SEC-132 and SEC-133, and SEC-124 and SEC-129 as before. Medium SEC-120 is accepted. I ran nothing, and this review is not a certification; Khalid decides.

## After the re-check (Nov 15, by Ahmad as the coding agent; not re-checked by Agent 16)

- **SEC-131 (fixed, awaiting re-check):** `_prepare_delete_task` adds `task_due_at` (the task's full due value, with its offset) for display only; `_due_display` shows it 12-hour. `task_due` and the exact delete comparison are unchanged. Test: a UTC due shows its Jeddah hour.
- **SEC-133 (fixed, awaiting re-check):** `shown_time` catches `OverflowError` too and shows the value as it came. Test included.
- **SEC-132 (part):** `backup.py` `SCHEMA` is now 6 with an up-to-date comment. The Nov 14 backups with card text age out by themselves within 30 days (no backup holds cards from now on).
- Both suites pass after these (Python 1384, web 169).

**Still for Khalid:** Low SEC-121 (a reminder whose card insert fails after the claim stays unsent), SEC-122 (the brief may come twice on a restore day), SEC-130 (tighten `sender_verified` to one `dmarc=` result; check one real Yahoo email's raw headers to confirm Yahoo's line is first); Info SEC-124 and SEC-129. Open Critical 0, open High 0.

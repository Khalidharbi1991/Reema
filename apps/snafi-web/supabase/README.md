# Snafi Supabase setup

Run these in the Supabase dashboard. Nothing here is run from this PC by Claude
Code; no Claude Code session has a key that could change the database.

1. Authentication → Sign In / Providers → Email: keep Email enabled, and turn
   **off** "Allow new users to sign up". Snafi is invite only.
2. Authentication → Users → Add user → Create new user: your email and a strong
   password, with "Auto Confirm User" ticked.
3. SQL Editor → New query → paste all of `migrations/0001_mailbox.sql` → Run.
4. **Step 2:** SQL Editor → New query → paste all of `migrations/0002_step2_brain.sql` → Run,
   then the same for `migrations/0003_approvals_once.sql` (approvals bound to the arguments
   shown, 24-hour expiry, run once).
   Table Editor then shows `jobs`, `messages`, `approvals`, `action_log`, `notes`,
   `reminders`, `facts` and `worker_status`, each with "RLS enabled".
5. Project Settings → API Keys: the Project URL and the **publishable** key go in
   `apps/snafi-web/.env.local` (see `.env.example`). The **secret** key goes only in
   the worker, stored in Windows Credential Manager by `set_secrets` (see `src/snafi_worker/README.md`);
   never in the web app, which refuses it.

## What the rules allow

| Who | Can |
| --- | --- |
| Anonymous | nothing |
| Signed-in user (the app) | read own rows in every table; post own `user` messages; queue own `chat.reply` jobs in the chat lane; decide own pending approvals only through `decide_approval()`; ask for Undo only through `request_undo()` |
| PC worker (secret key, on the PC only) | everything, including `claim_job()` |

Nobody can update or delete through the app. `decide_approval()` and
`request_undo()` run with the owner's rights (Supabase's `postgres` role bypasses
row-level security), change exactly one row once, and queue the worker's
follow-up job. These rules are tested offline in `tests/rls.test.ts` and
`tests/rls-step2.test.ts`, which run these exact files in PGlite with a stand-in
owner role that, like Supabase's, is not a superuser but bypasses RLS.

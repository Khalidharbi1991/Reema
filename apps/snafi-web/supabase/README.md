# Snafi Supabase setup

Run these once, in the Supabase dashboard, in this order. Nothing here is run
from this PC; REEMA has no Supabase key that could change the database.

1. Authentication → Sign In / Providers → Email: keep Email enabled, and turn
   **off** "Allow new users to sign up". Snafi is invite only.
2. Authentication → Users → Add user → Create new user: your email and a strong
   password, with "Auto Confirm User" ticked.
3. SQL Editor → New query → paste all of `migrations/0001_mailbox.sql` → Run.
   Table Editor should then show `jobs` and `messages`, both empty, each with
   "RLS enabled".
4. Project Settings → API Keys: copy the Project URL and the **publishable**
   key (`sb_publishable_…`, or the legacy `anon` key) into
   `apps/snafi-web/.env.local` (see `.env.example`). Never use the secret /
   `service_role` key in the web app; the app refuses it.

## What the rules allow

| Who | jobs | messages |
| --- | --- | --- |
| Anonymous | nothing | nothing |
| Signed-in user | read own; insert `kind`, `payload` (status forced to `queued`) | read own; insert own `role = 'user'` only |
| PC worker (step 2, secret key, on the PC only) | everything | everything |

Nobody can update or delete through the app. These rules are tested offline in
`tests/rls.test.ts`, which runs this exact file in PGlite.

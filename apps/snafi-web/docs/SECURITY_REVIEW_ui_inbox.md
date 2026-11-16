# Snafi: security review of the UI job (Inbox, simpler Today, Chat scroll, mobile fit, calmer look) (Agent 16)

Nov 16, 2026 · branch `feat/snafi-ui-inbox`, compared with tag `before-snafi-ui-inbox` (commits b981e65, 8208e6e, 9a147cc, 9b2b9ba as listed in the session's git status) · reviewer: Agent 16 (`reema-agent16-security`).

**Scope:** the review Khalid asked for before this branch merges to main, as Ahmad passed it on. The change adds the bell and the `/inbox` page, a read time on cards (migration `0009_inbox_read.sql`, `mark_card_read`), a simpler Today, Chat scrolling (ChatView became a client component), the look refresh, sample content for preview mode with a `dev:preview` script, and, under `.claude/`, two third-party design skills (markdown only), new instructions for Agent 17 and a second entry in `launch.json`.

**What I read:**
- `apps/snafi-web/.reema/security_diff.patch`, all 5,638 lines, in parts.
- `apps/snafi-web/.reema/claude_diff.patch`, all 2,132 lines: every installed file of `.claude/skills/frontend-design/` (SKILL.md, LICENSE.txt, SOURCE.md) and `.claude/skills/impeccable/` (SKILL.md, SOURCE.md, LICENSE, NOTICE.md and the 11 reference files), the Agent 17 change and `launch.json`.
- `apps/snafi-web/docs/PRD_ui_inbox.md` in full; `apps/snafi-web/docs/UI.md` lines 1 to 772 (section 0 rulings, tokens, screens and the start of the component specs), not the rest.
- Current files, read directly and in full: `src/app/(app)/actions.ts`, `src/adapters/mailbox/types.ts`, `supabase.ts` and `memory.ts`, `src/adapters/index.ts`, `src/config/env.ts`, `src/config/services.ts`, `src/core/session.ts`, `src/core/security-headers.ts`, `src/proxy.ts`, `src/app/(app)/chat/page.tsx`, `src/components/ApprovalCard.tsx`, `public/sw.js`, `next.config.ts`, `supabase/migrations/0008_proactive.sql`, `.claude/agents/reema-agent17-ui.md`, `.claude/launch.json`.
- `docs/SECURITY_REVIEW.md` lines 1 to 127 and `docs/SECURITY_REVIEW_off_this_phone.md` in full, for the numbering and the earlier rows this round touches (SEC-13, SEC-22, SEC-26, SEC-74).

**Numbering:** the newest earlier round ends at SEC-169 (`SECURITY_REVIEW_off_this_phone.md`, named "Newest" at the top of `SECURITY_REVIEW.md`). This round starts at SEC-170. I cannot list the folder, so if another review file with higher numbers exists that the top of `SECURITY_REVIEW.md` does not name, these numbers need shifting.

**I ran nothing.** No tests, eslint, tsc, build, git, browser, hash tool, scanner or network call. I have not checked any reported test result, the SHA-256 values in the two `SOURCE.md` files, or that the two patch files match the branch. Line numbers for files I read only in the patch are counted from the patch. This review is not a certification. Khalid decides.

## Summary

**Open Critical 0, open High 0. Nothing in this round blocks merging `feat/snafi-ui-inbox` to main.** Khalid decides.

**For Khalid to decide:**
- **Medium (1):** SEC-170. The impeccable skill's own text tells whoever loads it to run a launcher and a detector, manage a hook and "repair" files. Those scripts are not installed, but the skill is now visible to the whole session (Ahmad and Agent 14 have a shell), and the rule "never run it, never `npx impeccable`" lives only in `SOURCE.md` and in Agent 17's instructions, which the others do not load.
- **Low (12):** SEC-171 (Agent 17's wording), SEC-172 (the cards fallback hides real failures), SEC-173 (a mail card's whole body reaches the browser), SEC-174 (a GET to `/inbox?open=` marks a card read), SEC-175 (`dismiss_card` is still callable), SEC-176 (the placeholder Today source now shows a made-up approval and is allowed in production), SEC-177 (`dev:preview` uses `npx` through a shell, and its blanking is not proven on Windows), SEC-178 (an approval can move under the finger), SEC-179 (other people's text in new places; adds to SEC-26), SEC-180 ("clear after 7 days" hides, it does not delete), SEC-181 (the newest-100 window can drop an unread reminder), SEC-182 (whole chat rows now go to the browser).
- **Info (11):** SEC-183 to SEC-193 (checks recorded, and small notes).

**Answers to Ahmad's nine points, in short:**

1. **Migration 0009: sound.** `mark_card_read` is `security definer` with `search_path = ''`, takes the user from `auth.uid()` and refuses null, updates only `where id = p_id and user_id = uid and read_at is null` (so it sets the time once), returns nothing and raises nothing for another user's id or a missing id (no existence oracle), is revoked from public and anon and granted to authenticated. It grants nothing new on `cards` and changes no policy. The 7-day hiding is done by the app only and is not a security control (SEC-180, SEC-184).
2. **Adapters:** the fallback in `cards()` retries the old query on any error, not only "no such column", so it can hide a real failure and show every card as unread, old read ones included (SEC-172). `markCardRead` checks the id as a UUID and fails quietly as the PRD asks (SEC-183). The unread count never includes `test` cards (checked). Card text is drawn as plain text: no `dangerouslySetInnerHTML`, no link is built from card text, long text wraps or is cut. Bidi and zero-width characters are not removed (SEC-179). A mail row shows only the sender and the subject on screen, but the whole body is sent to the browser (SEC-173).
3. **`/inbox?open=`:** the value is only compared with the ids already on the page; nothing redirects on it, and it can never mark another user's card (the database function is own-rows only). A GET to it does mark the named card read once the page loads (SEC-174, Low, by design in AC-18). The mark-read server action has the same protection as the existing ones: `requireSession()` first, POST only, Next.js's own same-origin check (SEC-186).
4. **Approvals:** Approve still carries the hash of the card it is drawn from, through the same `decideApproval` action; an expired card shows no buttons and the database decides; Approve and Reject exist only inside `ApprovalCard`, which always draws the tool and every argument; Today has no button at all (SEC-185). One new handling risk: cards moving (SEC-178).
5. **Server and client:** no secret, adapter or server-only module crosses to the browser. ChatView now receives whole message rows (SEC-182). No new `NEXT_PUBLIC_` variable. The CSP is still satisfied (inline SVG elements, style attributes, self-hosted fonts, no outside host in the changed CSS). The service worker is not touched (SEC-187).
6. **Sample data and preview:** all invented, `example.com` only; seeded only in preview mode, which cannot be on in a production build. One gap: `SNAFI_TODAY_ADAPTER=placeholder` is allowed in production and now carries a made-up pending approval (SEC-176). `dev-preview.mjs`: fixed arguments, loopback only; see SEC-177.
7. **Removed code:** `dismiss_card` stays granted to the app with nothing calling it (SEC-175). The connection notes in Settings show the same sentences behind the same sign-in check; no new exposure.
8. **Skills:** I found no hidden instruction, telemetry or download step aimed at REEMA in the installed files, but several steps tell the reader to run things that conflict with AGENTS.md. For Agent 17 they are neutralised (no shell, explicit rule). For the rest of the session they are not (SEC-170). Agent 17's new paragraph contradicts its own boundary line (SEC-171).
9. **Tests:** the changed tests keep their security intent (ownership, the hash binding, no mail text on Today, no buttons on Today) and the new database test covers AC-11 well. Gaps are listed in SEC-191.

## Findings

| ID | Severity | File:line | What an attacker (or a failure) could do | Fix | Status |
| --- | --- | --- | --- | --- | --- |
| SEC-170 | Medium | `.claude/skills/impeccable/SKILL.md:5,19,23,82-90`; `reference/layout.md:27-29`; `reference/typeset.md:26-28`; `reference/polish.md:31-33,95,101-103`; `reference/craft-floor.md:3`; `reference/mode-operate.md:3`; `.claude/skills/impeccable/SOURCE.md`; `.claude/skills/frontend-design/SKILL.md:13,59` | **The skill's text tells its reader to run programs, and the rule against that is not where most readers will see it.** `SKILL.md` step 1 says to run `scripts/impeccable context` once per session ("a self-contained binary that ships next to it or is downloaded once on first run"). Other lines name a pin command, a hook that "auto-runs the detector after UI file edits", a "doctor" that repairs files, a "foundations" walk that touches "secrets ... CI", and say a finding marked `auto` is performed by the next write. Three reference files carry runnable `bash` blocks for the detector and for `critique-storage`. None of these scripts is installed (I probed `scripts/impeccable`, `scripts/impeccable.cmd` and `reference/live.md`: not there), so today each call fails and the skill's own "Launcher unavailable" path carries on by hand. The risk is what happens next. Both skills sit in `.claude/skills/`, `impeccable` is `user-invocable: true`, and its description matches any UI work, so Ahmad's session and Agent 14 (both with a shell) can load it. They load `SKILL.md`, not `SOURCE.md`; the REEMA overrides are only in `SOURCE.md` and in Agent 17's instructions, and AGENTS.md does not mention these skills. A session that tries to "make the launcher work" (for example `npx impeccable`, which `SOURCE.md` itself names as the thing never to do) would download and run unreviewed code as Khalid's Windows user, where the Snafi keys are readable (SEC-51). AGENTS.md says package installs are not blocked by the guard. I did not read the guard this round, so I do not know whether it stops the launcher or `npx impeccable`. Smaller conflicts in the same files: the skill says to read and "replace `DESIGN.md`" and to route through `init` when `PRODUCT.md` is missing; `frontend-design` says to use "information in your memory about the client's preferences" (AGENTS.md needs Khalid's yes before memory is read) and to take screenshots (with real data on screen those go to Anthropic through Claude Code; the PRD allows sample data only); `distill.md:24` and `quieter.md:31` say to stop and use `AskUserQuestion`. | Pick one, Khalid decides. **(a) Best:** move both folders out of `.claude/skills/` (for example to `apps/snafi-web/docs/design-skills/`), so they are plain reference files and no session loads them as skills; Agent 17 already reads them by path, so only its two paths change. The files stay unmodified and the hashes stay true. **(b)** Keep them as skills and add to AGENTS.md, where every session reads it: "The frontend-design and impeccable skills are advice only. Never run or install the impeccable launcher, detector, hook, plugin or `npx impeccable`; never create PRODUCT.md or DESIGN.md; their SOURCE.md overrides apply to everyone." **(c)** In either case, have the guard refuse a command that names `impeccable` with `npx`, `npm`, `scripts/impeccable` or `impeccable.cmd`, with a test, and name the guard files for my next round. | Open |
| SEC-171 | Low | `.claude/agents/reema-agent17-ui.md:14-17,22` | **Agent 17's new paragraph and its boundary line disagree, and the Snafi reach is not closed.** Line 14 makes `apps/snafi-web/` the project folder and allows reading its `src/` and `docs/`; line 22 still says "Work only inside the project folder ... under teams/development/projects/. Never read or write ... REEMA's own code", and Snafi is REEMA's own code. An agent can settle the conflict either way. Read together, "work only inside the project folder Ahmad names" plus "the project folder is apps/snafi-web/" lets Agent 17 write anywhere under `apps/snafi-web/` (it has the Write tool), not only `docs/UI.md`, and nothing in its file bars `.env.local`, `.reema/`, `.next/` or `node_modules/`. It also now reads two folders under `.claude/` that line 22 does not allow. I did not check whether the guard or `settings.json` limits Agent 17's writes or denies `.env.local`. The description line still says "Use only inside the reema-agent11-dev-lead skill". | Rewrite line 22 so both cases are exact: "For a Development project: only the project folder Ahmad names under teams/development/projects/. For Snafi: read only `apps/snafi-web/src/`, `apps/snafi-web/docs/` and the two design-skill folders; write only `apps/snafi-web/docs/UI.md`. Never read any `.env` file, `.reema/`, `.next/` or `node_modules/`." Update the description line. | Open |
| SEC-172 | Low | `src/adapters/mailbox/supabase.ts:139-150` | **The cards fallback runs on any error, so it can hide a real failure and show wrong data.** If the first query (with `read_at` and the 7-day filter) fails for any reason, the old query runs and its rows come back with no read time. Then every card shows as unread, cards read more than 7 days ago come back, the bell count jumps, and Today may show an already-read reminder as Ahmad's message. Nothing is logged and no one is told. This happens (1) on a passing network or database error, and (2) for good if the filter text itself is ever refused. The filter `.or("read_at.is.null,read_at.gt.<ISO time>")` is built from the server's clock only (no outside input, so no injection), but no test runs it against PostgREST: the tests use the in-memory mailbox and SQL in PGlite. So a mistake in that one line would be invisible, and the read state and the 7-day rule would silently never apply on the live site. Only the user's own rows are ever returned (RLS), so nothing leaks to another user. Before 0009 is run, each page load also makes one failing query (SEC-188). | Fall back only when the error says the column is missing (Postgres code `42703`, or PostgREST's message for an unknown column); otherwise throw, so the Inbox says "couldn't load". Remove the fallback in the change after 0009 is live. Add a unit test with a stand-in client for three cases: missing column falls back, any other error throws, success maps `read_at`. After 0009 is applied, Khalid or Ahmad checks once on the live site that a card opened yesterday shows as read. | Open |
| SEC-173 | Low | `src/app/(app)/inbox/page.tsx:17`; `src/app/(app)/inbox/InboxView.tsx:157,185-189`; `src/core/inbox.ts:73-75` | **A mail card's whole body is sent to the browser; only the screen hides it.** AC-8 says a mail alert shows the sender and the subject only. `InboxView` is a client component and receives every card whole, so for a mail card the full `body` (up to 3,000 characters) is in the page's data even though only its first line is drawn. Whether that matters depends on what the worker writes into a mail card's body, which I did not read: if it is the subject only, nothing extra is sent; if it ever holds a snippet or more, that text sits in the page source and in the phone's memory. The rule "title is the sender, the body's first line is the subject" is an unchecked agreement with the worker (the comment in `inbox.ts` says so). A subject with an encoded line break is cut at the first line, which is the safe direction. | In `inbox/page.tsx` (server side), reduce each mail card before it is passed on: `body` becomes its first non-empty line (`mailLines`). Add a test that the props given to `InboxView` for a mail card do not contain the rest. Ahmad: name the worker file that writes mail cards in a later round so the format can be confirmed. | Open |
| SEC-174 | Low | `src/app/(app)/inbox/InboxView.tsx:46-50,69-80`; `src/app/(app)/inbox/page.tsx:12,17`; `src/app/(app)/today/TodayView.tsx:93` | **Opening `/inbox?open=<card id>` marks that card read: a state change that starts from a GET.** When the page loads with an `open` value that matches one of the user's own cards, the screen calls the mark-read action by itself. Anyone who can get Khalid to follow a link to his own site with a real card id (a link in an email, for example; the session cookie goes with a top-level navigation) makes that card read: it leaves the bell count, and a reminder stops being Ahmad's message on Today. What limits it: the id is a random UUID that the attacker would have to know (it is not in the push payload or any public place I saw); the card opens in front of Khalid, so it is not silent; the mark is his own card only, once; link prefetch does not run it (the call is made in the browser after the page mounts). An approval id in `open` only scrolls and moves focus to the item, never to Approve, and decides nothing. The value itself is not checked on the server: any string of any length is passed into the page data and used in `getElementById("inbox-" + open)` (safe: no selector is built, nothing is drawn from it, and a value such as `approvals` only finds a heading). No redirect uses it; the address is reset to the fixed `/inbox`. | Accept as designed (AC-18), or make it stricter: mark read only on the tap (the row opens on arrival, unread, and the first tap or a short "seen" delay marks it). In either case, in `page.tsx` pass `open` on only when it matches the UUID pattern used by `checkId`, and add a test with a long and a hostile value. | Open |
| SEC-175 | Low | `supabase/migrations/0008_proactive.sql:195-212,236-241`; `supabase/migrations/0009_inbox_read.sql:6-7` | **`dismiss_card` is still granted to the app, and nothing in the app calls it or can undo it.** The Dismiss button, action and adapter method are gone, but any signed-in session can still call `dismiss_card(<id>)` through the database API. A dismissed card is hidden from the Inbox, the bell and Today at once, read or unread, and no screen shows or restores it. So a stolen or misused session has a quiet way to make an unread reminder or mail alert vanish, quieter than mark-read (a read card stays listed for 7 days). Own rows only; no other user is affected. Leaving the function in place was a stated choice (A11), so this is a note on the leftover right, not a defect in this change. | In the next migration: `revoke execute on function public.dismiss_card(uuid) from authenticated;` (keep the function and the `dismissed_at` filter so old dismissed cards stay hidden), and change the test that expects the grant. Or record that Khalid keeps it. | Open (for Khalid) |
| SEC-176 | Low | `src/adapters/today/placeholder.ts:56-57`; `src/adapters/sample.ts:16-23`; `src/config/services.ts:29-30,42`; `src/adapters/index.ts:43-44` | **The placeholder Today source is allowed in production and now carries a made-up pending approval and cards.** SEC-74 refuses the `memory` stand-ins in a production build, but `SNAFI_TODAY_ADAPTER=placeholder` is still accepted there. Before this change the placeholder had no approvals. Now it returns a sample pending approval (id `...0101`, hash of 64 "a") and five sample cards, and the bell, the Inbox and Today are all drawn from that source. If that setting were ever put on Vercel by mistake, the live app would show a badge and an Approve button for an action that does not exist, and would hide the real pending approvals from the Inbox and Today (they would still be in Chat). It fails safe: Approve on the sample goes to the real database, which has no such row, so nothing runs. It needs a wrong setting, not an attacker. | Add `placeholder` to the values refused when `NODE_ENV` is `production` (extend the SEC-74 set and its test), or return no approvals from the placeholder source. | Open |
| SEC-177 | Low | `scripts/dev-preview.mjs:8-18`; `package.json` (`dev:preview`) | **`dev:preview` starts Next through `npx` and a shell, and its promise ("`.env.local` is not used") is wider than what the code does.** (1) `spawn("npx", [...], { shell: true })`: the arguments are fixed, so nothing can be injected through them. But `npx` will offer to fetch `next` from the registry, at whatever version is newest, if it is not installed in the folder, and when no terminal is attached it may go ahead without asking; that would be an unpinned download that then runs. The shell is not needed. (2) The script blanks five variables for the child. Next still loads `.env.local` for every other variable (the throttle secret, the site address, the push public key), so the file is used; only the Supabase address and key are meant to be overridden. (3) Whether an empty value survives on Windows through `cmd.exe`, `npx.cmd` and Node, and whether Next then leaves `.env.local`'s value alone, I could not check. If the blank is lost, port 3100 is an ordinary dev server on the real Supabase project: it would show the real sign-in page, not the preview, so it fails where it can be seen, but a screenshot taken after signing in would hold real data (AC-30 asks for sample data only). The server listens on 127.0.0.1 only, and preview mode holds only invented data. | Start Next without `npx` and without a shell: `spawn(process.execPath, [require.resolve("next/dist/bin/next"), "dev", "--hostname", "127.0.0.1", "--port", "3100"], { env, stdio: "inherit" })` (with `createRequire` in an `.mjs` file). Correct the comment: "the Supabase address and key are blanked; other values in `.env.local` are still loaded". Before any screenshot, check that the "Preview mode" banner is on the page; Agent 15 can add that check to the screenshot step. | Open |
| SEC-178 | Low | `src/app/(app)/inbox/InboxView.tsx:92-101,103-106,132-144` | **An approval can move under the finger.** In the Inbox, when an approval is decided its card is replaced at once by a one-line note, and when one expires or is decided elsewhere it leaves the list at the next 30-second refresh. The cards below move up. A second tap meant for the card just handled, or a tap made as the list refreshes, can land on the next card's Approve, which sends that card's own id and hash: a real approval of a send, invite or delete that Khalid did not read. I could not measure where the buttons land (no browser), so this is a risk from reading the layout, not an observed fault. The same kind of shift existed on Today before this change; it matters more now that every pending approval is stacked on one page. New approvals are added below the older ones, which is the safe direction. Focus on arrival goes to the item, not to Approve. | Keep a decided card's box in place (same height, buttons replaced by the status line) until Khalid leaves the page or 30 seconds pass, and do not remove an expired card from under an open page: show it as "Expired" in place. Optional: ignore taps on Approve for about a second after the list changes. Agent 15: test two stacked approvals in a browser at 360 and 390 px. | Open |
| SEC-179 | Low | `src/app/(app)/inbox/InboxView.tsx:175-181,187`; `src/components/NowCard.tsx` (name and place); `src/app/(app)/today/TodayView.tsx:89-93`; `src/adapters/mailbox/types.ts:120-126,160` | **Other people's text now shows in more places, still with bidi and zero-width characters left in (adds to SEC-26, which stays open).** A mail sender's display name is the bold first line of a mail row; a subject is its second line; a calendar event's title (anyone can send an invitation) is the largest text in the app, on the Now card. `toCard` and `toTodayFeed` cut the length and nothing else. React draws all of it as text, so this is not script injection, and `<bdi>` keeps one field's direction from spilling into the next. Inside its own field a name or title can still be reordered or padded to look like something else, or simply say "Snafi: your session expired, sign in at ...". The kind label (Mail, Reminder, Brief) comes from the database, not from the sender, so a mail cannot pass as a reminder or an approval, and no card text becomes a link. | As SEC-26: in `toCard` and `toTodayFeed`, remove or make visible the bidi controls (U+202A to U+202E, U+2066 to U+2069) and the zero-width characters other than U+200C and U+200D (Arabic and Persian need those two), and collapse line breaks in titles. Add a test with a right-to-left override in a sender name. | Open (with SEC-26) |
| SEC-180 | Low | `src/i18n/messages.ts` (`inbox.clearNote`, en and ar); `src/adapters/mailbox/types.ts:80-88`; `supabase/migrations/0009_inbox_read.sql:3-4` | **"Read items clear after 7 days" hides cards; it does not delete them.** The row, with the sender and subject of a mail alert or the text of a reminder, stays in the database and in the PC's backups for good (SEC-20), and the owner's session can still read it through the database API. The PRD says so ("hidden by the app; deleting rows is not part of this job"), and the hiding is not used as a security control anywhere. The footer text may still lead Khalid to think old alerts are gone. | Wording, for example "Read items are hidden after 7 days." (with Arabic to match), or leave it and record that Khalid knows. If real deletion is wanted, that is a worker job for a later step. | Open (for Khalid) |
| SEC-181 | Low | `src/adapters/index.ts:43`; `src/adapters/mailbox/supabase.ts:89-93,142-144` | **Only the newest 100 cards and the newest 50 pending approvals are read, so an older unread item can drop out.** "Unread cards never clear" holds only inside that window. If more than 100 cards are newer than an unread reminder, it leaves the Inbox, the bell count and Today with no notice. Mail alerts are caused by outside senders, so a burst of mail that the worker treats as important could push a reminder out; how many mail cards the worker will write in a day I did not check (the daily limit in Settings is for pushes; "past the limit, cards still appear"). For approvals the query takes the newest 50 and the screen then shows the oldest first, so past 50 it is the oldest, nearest to expiry, that are lost. Both need unusual volume. | Read unread cards and read cards separately (unread first, each with its own limit), or order by unread first; take pending approvals oldest first. Say on the screen when a limit was reached ("showing the newest 100"). | Open |
| SEC-182 | Low | `src/app/(app)/chat/ChatView.tsx:1,13-22`; `src/app/(app)/chat/page.tsx:11-21`; `src/adapters/mailbox/supabase.ts:60-66` | **ChatView is now a client component, so whole message rows go to the browser, and the query selects every column.** Before, the server drew the chat and only the visible text reached the phone. Now the last 60 messages are sent as data: besides the text, each has `userId` (the Supabase user id), `conversationId`, `jobId`, `meta` and `createdAt`. These are Khalid's own identifiers, not secrets, and no key, adapter or server-only module crosses (the client files import types, pure helpers and the text table only; `adapters/index.ts` and `today-data.ts` are marked server-only). The lasting risk is `select("*")` on `messages`: any column added later would reach the browser without anyone deciding it should. | In `chat/page.tsx`, pass only what the screen uses (`id`, `role`, `body`, `lang`, `approvalId`, `meta.actions`), and name the columns in `listMessages` instead of `*`. | Open |
| SEC-183 | Info | `src/app/(app)/actions.ts:55-63`; `src/app/(app)/inbox/InboxView.tsx:54-64,82-89` | **Mark-read fails quietly, as the PRD asks; two side effects.** Any error (function missing before 0009, a refused call, a network fault) returns `{ ok: false }`; the row turns unread again and nothing is said or logged. That is right for the days before 0009 is live. After that, a lasting fault would show only as cards that never stay read. Also, after one failed try the card is not asked again on that page, but closing and opening it again marks it read on the screen only (`readNow` is set, the call is skipped): the row looks read, the bell still counts it, and a reload shows it unread. The id is checked as a UUID before the call (`checkId`), and the session is checked first. | After 0009 is live: log one plain server line when mark-read fails (the error code only, no card text), and in `toggle` set `readNow` only when the call is really made. | Open |
| SEC-184 | Info | `supabase/migrations/0009_inbox_read.sql:13,18-35`; `tests/rls-inbox.test.ts` | **Checked: migration 0009.** One new nullable column and one function, in a transaction. The function is `security definer`, `set search_path = ''`, with every name schema-qualified; it reads the user from `auth.uid()` and raises 42501 when it is null; its one statement is `update public.cards set read_at = now() where id = p_id and user_id = uid and read_at is null`. So: own card only; set once; no other column touched; another user's id, a missing id and an already-read card all return the same empty result with no error and no count, so the call tells nothing about whether an id exists. Execute is revoked from public and anon and granted to authenticated. The app's rights on `cards` are unchanged (select only, own rows through `cards_select_own`; RLS forced); the new column is covered by the existing table-level select. `create function` and `add column` are not "if not exists", so running the file twice fails and rolls back, which is safe. The new test covers own card, set-once, another user, missing id, anonymous and signed-out callers, no direct insert, update or delete, and the function's settings. **Not checked:** the worker's backup and restore for the new column (if restore names its columns, a restore would bring cards back as unread; harmless, but worth a look), and the live database. | None needed. Ahmad: name the worker's backup and restore files in a later round if `cards` is restored by column list. | Recorded |
| SEC-185 | Info | `src/components/ApprovalCard.tsx:48-59,61-92`; `src/app/(app)/inbox/InboxView.tsx:92-101`; `src/app/(app)/actions.ts:33-48`; `src/app/(app)/today/TodayView.tsx` | **Checked: approvals keep the SEC-13 binding, and nothing is approvable from Today.** `ApprovalCard` still calls `decide(card.id, decision, card.argsHash)` with the hash of the same card object whose tool and arguments it draws, in full, with no clamp or cut. The Inbox wraps `decide` only to update the bell and the list; it passes the id, decision and hash through unchanged. The server action is unchanged apart from refreshing `/inbox`; the adapter still refuses a hash that is not 64 hex characters, and the database function (migration 0003, not changed, not re-read this round) does the binding and the expiry. Approve and Reject are drawn only inside `ApprovalCard`, after the arguments, and only while the card is pending and not past its expiry on the clock the page was drawn with; a card that expires while open is refused by the database and then shows "Expired". Today imports no `ApprovalCard` and takes no `decide`; its one approval line is a link to the Inbox showing the summary and "Waiting for your approval", and the tests assert Today has no button. The label column of the arguments is now forced left-to-right and the values use `dir="auto"`; the tool name lost its monospace face (a design choice; the text is the same). | None needed. | Recorded |
| SEC-186 | Info | `src/app/(app)/actions.ts:55-63`; `src/core/session.ts:10-21`; `next.config.ts`; `src/app/(app)/inbox/page.tsx`; `src/core/today-data.ts:13-19` | **Checked: sign-in and cross-site protection for the new action and page.** `markCardRead` calls `requireSession()` before anything else, like every other action in the file, then the adapter, which runs as the signed-in user with the publishable key, so the database decides ownership. It is a Next.js server action: POST only, with Next's own check that the request's Origin matches the host; `next.config.ts` adds no extra allowed origin. The Inbox, Today and Settings pages and the shared layout all go through `loadToday()`, which calls `requireSession()` (the SEC-6 rule), and its per-request cache is not shared between users or requests. The proxy still sends signed-out visitors to `/sign-in`; `/inbox` is not a public path. I did not re-read the cookie policy file (not changed). | None needed. | Recorded |
| SEC-187 | Info | `src/core/security-headers.ts:14-36`; `src/app/globals.css`; `src/app/layout.tsx` (font import); `src/components/Icons.tsx`; `public/sw.js:105-119` | **Checked: CSP, headers, fonts and the service worker.** The icons are inline `<svg>` elements, not data addresses or outside files. The new inline styles are `style` attributes, which the existing `style-src-attr 'unsafe-inline'` covers; no inline script, event-handler attribute or `dangerouslySetInnerHTML` is added. The changed CSS has no `url()` and no outside host. The one new font file, IBM Plex Sans Arabic 600, is imported from the package already listed; `package.json` gains only the `dev:preview` script and no dependency. `font-src 'self'` and `connect-src 'self'` are unchanged, as are the headers in `next.config.ts` and the proxy. `public/sw.js` is not in the diff: navigations are still network-only and never cached, so `/inbox` is not stored on the phone. One stale detail: a notification tap still opens `/today`, and the worker's comment says the card waits there; a mail alert now waits in the Inbox (Today shows only the bell count for it). Not a security matter. **Not checked:** that the 600 weight file exists in the installed package (I may not read `node_modules/`), and the built output. | Optional: open `/inbox` on a notification tap, in a later change with its own review. | Recorded |
| SEC-188 | Info | `src/app/(app)/layout.tsx:17,26`; `src/core/today-data.ts`; `src/app/(app)/chat/page.tsx:17`; `src/adapters/mailbox/supabase.ts:142-147` | **Every signed-in page load now reads approvals, the Today feed and up to 100 cards, Chat included (adds to SEC-22).** The layout calls `loadToday()` for the bell, and Chat refreshes every 3 seconds, so an open chat adds three database reads every 3 seconds. Until 0009 is run there is a fourth: the first cards query fails ("column does not exist") and the fallback runs, which also puts one error line in the database log every few seconds. No data is exposed; this is load and log noise, and a reason to run 0009 together with the deploy as the README says. | Optional: for Chat, have the bell read only ids and counts, or refresh the layout's data less often than the chat. | Recorded |
| SEC-189 | Info | `src/adapters/sample.ts`; `src/adapters/index.ts:26-32`; `src/config/env.ts:134-136` | **Checked: the sample content is invented and is seeded only in preview mode.** Names are "Sample sender", "sample contact", `sample.person@example.com`, `example.com` links, generic tasks, and two Arabic lines marked "نموذج". No real address, mailbox, event or person. `seedPreview()` runs only when `isPreviewMode()` is true, which needs `NODE_ENV` to be `development` and no Supabase settings at all, so it cannot run in a production build. The sample approval can be approved only inside the in-memory mailbox, where no worker exists. The one way sample items could appear in production is the placeholder source (SEC-176). | None needed beyond SEC-176. | Recorded |
| SEC-190 | Info | `.claude/launch.json:10-15` | **The new launch entry runs a fixed npm script on a loopback port.** `snafi-web-preview` runs `npm --prefix apps/snafi-web run dev:preview` on port 3100: fixed text, no value from outside. It is the safer of the two entries (the first starts the dev server with the real `.env.local`). A server started this way is started by Claude Code's launcher, not as a Bash command, so I expect the guard hook does not see it; I did not read the guard or test that. What it runs is the project's own code and installed packages as Khalid, as any `npm run` does. | None needed. Ahmad: name the guard files in a later round if launch entries should be covered by a rule. | Recorded |
| SEC-191 | Info | `tests/screens.test.tsx`, `tests/step2-today-config.test.ts`, `tests/step3-google-today.test.tsx`, `tests/step4-yahoo-todoist-today.test.tsx`, `tests/step5-proactive.test.tsx`, `tests/rls-inbox.test.ts`, `tests/ui-inbox.test.tsx` (as shown in the patch) | **Checked: the changed tests keep their security intent; gaps listed.** Kept or made stronger: the reject call still asserts the id and the exact hash; Today is now asserted to have no Approve or Reject, in both languages; steps 3 and 4 now assert that no email subject is anywhere in Today's data, not only off the screen; an unreachable mailbox now gives "unknown" (no badge) instead of "none waiting"; in step 5 another user's `markCardRead` changes nothing where `dismissCard` used to be refused, and a dismissed card stays hidden; the database test covers AC-11. The removed tests belong to removed features (the prayer ring, the email list, account labels, the Dismiss button). **Gaps:** no test of the real Supabase `cards()` query or its fallback (SEC-172); the mail-row test checks the screen, not the data sent (SEC-173); `?open=` is tested with one unknown value only (SEC-174); nothing tests the placeholder source in production (SEC-176); nothing tests two stacked approvals (SEC-178). I did not run any test. | Add the tests named in SEC-172, 173, 174, 176 and 178 with their fixes. | Open |
| SEC-192 | Info | `src/app/(app)/inbox/error.tsx`, `src/app/(app)/today/error.tsx`, `src/components/RouteError.tsx` | **Not a security finding: the error screens take a `retry` prop that I cannot confirm Next.js passes.** As far as I know, an `error.tsx` receives `error` and `reset` (newer versions also name an `unstable_retry`). If `retry` is not passed, "Try again" on a failed Today or Inbox does nothing. The good part, checked: the error object is neither shown nor logged to the page, so no internal message reaches the screen. | Agent 15: force an error in a browser and press "Try again"; Agent 14: use the prop name of the installed Next version. | Open |
| SEC-193 | Info | `.claude/skills/frontend-design/*`, `.claude/skills/impeccable/*`, both `SOURCE.md` | **Checked by reading: no instruction aimed at REEMA, no telemetry and no address to fetch in the installed skill files; what I could not prove.** I read every installed file in the patch. The only addresses are the Apache licence, the two upstream repositories and one credited project. I found no text that tries to override other instructions, reach files outside the project, send data out, or change settings, apart from the launcher, detector, hook, doctor, foundations and `DESIGN.md` steps in SEC-170. The wording "No hedging" and "gives you the tools and permission" is style, but it pulls against REEMA's rule never to claim a check that was not made; Agent 17's UI.md does state what it did not render, which is the right outcome. **Not proven:** that the files are byte-for-byte the pinned upstream commits (I cannot compute SHA-256 or reach GitHub), that no invisible characters are in them (I read rendered text), and that no file beyond those in the patch sits in the two folders (I cannot list a folder; three likely paths I probed do not exist). | Ahmad, in a shell: compare each file's SHA-256 with `SOURCE.md`, list both folders, and search them for non-printing characters (for example U+200B to U+200F, U+202A to U+202E, U+2066 to U+2069, U+E0000 to U+E007F). Record the result here. | Open |

## Earlier rows this round touches

- **SEC-13 (closed):** re-checked from the app side; still closed (SEC-185). Migration 0003 was not re-read.
- **SEC-22 (Info, open):** note added by SEC-188 (more reads per refresh).
- **SEC-26 (Low, open):** stays open; SEC-179 lists the new places.
- **SEC-74 (closed):** still closed for what it named (`memory`); SEC-176 is a new, smaller gap beside it (`placeholder`).
- No earlier finding is closed by this round.

## Not reviewed

- `apps/snafi-web/docs/UI.md` after line 772 (component specs 4.3 onward, sections 5 to 9).
- The worker (`src/snafi_worker/`): what it writes into mail cards, how many cards it writes, its backup and restore of `cards`, and its push sender. None was named.
- The guard and settings (`.claude/hooks/dev_guard.py`, `.claude/settings.json`) and their tests: not named this round, so SEC-170, SEC-171 and SEC-190 say what I did not know about them.
- Migrations 0001 to 0007 (including `decide_approval` in 0003), the cookie policy, `request-origin.ts`, the sign-in action and the Supabase server client: not changed, not re-read.
- Whole current copies of files I read only as patch hunks (`messages.ts`, `globals.css`, `Menu.tsx`, `SettingsForm.tsx`, `TopBar.tsx`, `NowCard.tsx`, the test files).
- `.env.local`, `node_modules/`, `.next/`, the lock file, the installed Next.js version and the built output.
- The live Supabase database, the Vercel settings and how the app behaves after deploy; real iPhone and Android behaviour; any layout measurement (SEC-178 is from reading only).
- The SHA-256 values and the upstream contents of the two skills; hidden characters in any file.
- The reported test, lint and type-check results, the screenshots (AC-30), and whether the two patch files match the branch and the tag. `docs/UI.md` is not in `security_diff.patch` although the branch adds it, so the patch may be a filtered view.
- Khalid's confirmation of the PRD and his yes for the skills (relayed by Ahmad and recorded in the files).

## Status table

| Finding | Severity | Status |
| --- | --- | --- |
| SEC-170 The impeccable skill tells the whole session to run a launcher, detector and hook; the override is only in SOURCE.md and Agent 17's file | Medium | Open |
| SEC-171 Agent 17's Snafi paragraph contradicts its boundary line; reach not closed | Low | Open |
| SEC-172 `cards()` falls back on any error; real Supabase query untested | Low | Open |
| SEC-173 A mail card's whole body is sent to the browser | Low | Open |
| SEC-174 A GET to `/inbox?open=<id>` marks a card read; `open` not checked on the server | Low | Open |
| SEC-175 `dismiss_card` still granted to the app, with no caller and no undo | Low | Open (for Khalid) |
| SEC-176 Placeholder Today source allowed in production, now with a made-up approval | Low | Open |
| SEC-177 `dev:preview` uses `npx` through a shell; blanking unproven; ".env.local is not used" is not exact | Low | Open |
| SEC-178 An approval can move under the finger in the Inbox | Low | Open |
| SEC-179 Other people's text in new places, bidi and zero-width characters kept (with SEC-26) | Low | Open |
| SEC-180 "Clear after 7 days" hides, it does not delete | Low | Open (for Khalid) |
| SEC-181 Newest-100 cards and newest-50 approvals: an older unread item can drop out | Low | Open |
| SEC-182 Whole chat rows (`select *`) now go to the browser | Low | Open |
| SEC-183 Mark-read fails quietly; a re-opened card can look read when it is not | Info | Open |
| SEC-184 Migration 0009 checked | Info | Recorded |
| SEC-185 Approval binding and "nothing approvable from Today" checked | Info | Recorded |
| SEC-186 Sign-in and cross-site protection of the new action and page checked | Info | Recorded |
| SEC-187 CSP, headers, fonts and service worker checked | Info | Recorded |
| SEC-188 More database reads on every page load; one failing query until 0009 is run | Info | Recorded |
| SEC-189 Sample content checked: invented, preview mode only | Info | Recorded |
| SEC-190 New `launch.json` entry: fixed script, loopback; guard coverage unknown | Info | Recorded |
| SEC-191 Tests keep their security intent; five gaps | Info | Open |
| SEC-192 Error screens' `retry` prop unconfirmed (not security) | Info | Open |
| SEC-193 Skill files read; hashes, hidden characters and folder contents not proven | Info | Open |

**Open counts for this round:** Critical 0, High 0, Medium 1 (SEC-170), Low 12 (SEC-171 to SEC-182), Info 11 (SEC-183 to SEC-193, of which 7 are records of checks).

**Blocks merge: no** (open Critical 0, open High 0). Khalid decides.

---

## Ahmad's follow-up, Nov 16, 2026 (after Agent 16's round; Agent 16 has not re-reviewed these)

- **SEC-170 fixed.** `.claude/hooks/dev_guard.py` now refuses to run the design skills (their
  launcher, detector, hooks, live mode, `npx impeccable`, a `gate.mjs`, anything in a skill's
  `scripts/` folder), for every session and agent; reading their markdown is still allowed.
  AGENTS.md carries the rule as non-negotiable. The skills stay in `.claude/skills/` because that
  is where Khalid asked for them. New `tests/test_design_skills_guard.py` (27 tests, passing).
- **SEC-171 fixed.** Agent 17 now writes `docs/UI.md` only, reads no secrets file, and is told it
  never runs the skills.
- **SEC-193 closed by test.** The new tests prove each installed skill folder holds only text (no
  `scripts/`), that every file matches the SHA-256 recorded in its `SOURCE.md` next to the pinned
  commit, and that no file holds control, bidi or zero-width characters.
- **SEC-173 scope narrowed, by reading the worker.** A mail card is written by
  `src/snafi_worker/proactive/scheduler.py`: `title` is "Gmail · <sender>" or "Yahoo · <sender>",
  and `body` is the subject (cut to 300 characters) plus a "Received <time>" line. No mail body is
  ever put in a card, so what reaches the browser is the sender, the subject and the time. Agent
  14's mapping (sender from the title, subject from the body's first line) matches what the worker
  writes. The bidi and zero-width point in SEC-179 still stands.
- Still open for Khalid: SEC-172, 174 to 182 and the Info items. The REEMA Python suite passes
  (1422 tests) with the guard change.

---

# Re-review of the fixes (Agent 16, second round)

Nov 16, 2026 · branch `feat/snafi-ui-inbox`, after commits `93ff70e` (Agent 14's five fixes and the
test seam), `2f1a671` (Ahmad's follow-up), `5e773e8` (Agent 15's report) and `f5d5840` (the
measurements and screenshots) · reviewer: Agent 16 (`reema-agent16-security`). This section is
appended; nothing above it was changed.

**What I read this round**
- `apps/snafi-web/.reema/security_diff_ui_fixes.patch`, all 1,465 lines, in five parts.
- Current files, read directly: `src/app/(app)/inbox/InboxView.tsx` (whole), `src/config/env.ts`
  lines 1 to 136, `supabase/migrations/0009_inbox_read.sql` (whole),
  `supabase/migrations/0008_proactive.sql` lines 180 to 246,
  `.claude/hooks/dev_guard.py` (whole, 578 lines), `tests/test_design_skills_guard.py` (whole),
  `.claude/agents/reema-agent17-ui.md` (whole), `AGENTS.md` lines 30 to 109 (the non-negotiable
  rules, including the new design-skills bullet), `apps/snafi-web/docs/MEASUREMENTS_ui_inbox.md`
  (whole), and all seven files in `apps/snafi-web/docs/screenshots/` as images.
- The rest of `src/adapters/mailbox/supabase.ts`, `types.ts`, `actions.ts`, `inbox/page.tsx`,
  `vitest.config.ts`, `scripts/dev-preview.mjs` and the changed tests as the patch shows them.

**I ran nothing again.** No tests, build, browser, hash tool, git or network call. I did not read
`node_modules/`, `.env.local`, `.next/`, the live database or the worker. I did not re-measure
anything in the measurements document; I read it as a report. This is not a certification.

## 1. The app fix diff

**SEC-172 — closed.** `MISSING_SCHEMA_CODES` is a fixed list (`42703`, `42883`, `PGRST204`,
`PGRST202`) matched on the error's `code` field only; `schemaMissing()` needs a non-empty `code`,
so an error with no code (a fetch failure) propagates. The second (old) query's own error still
throws, with `schemaMissing` false. `markCardRead` carries the flag on the `MailboxError`, the
server action turns it into `{ ok: false, reported }`, and `InboxView` shows one `role="alert"`
line.
- *Can an attacker-influenced error pick the silent or fallback path?* I found no way. The only
  values that reach the database on these two calls are the limit (a server constant) and the
  cutoff built from the server's own clock, plus a UUID that `checkId` has already validated; none
  of them steers an error code. A crafted PostgREST error would require control of the database or
  of the response between Vercel and Supabase, which is already outside the trust boundary. The
  one honest caveat is over-breadth rather than attack: `42883` and `PGRST202` are
  *function*-missing codes that a `select` cannot raise, and `PGRST204` is PostgREST's
  "column not found in **schema cache**", which can also appear from a stale cache after 0009 is
  live. In that case the Inbox would again go quietly to the all-unread view. That is the
  behaviour the PRD asked for before 0009; it should go away with the fallback once 0009 is live
  (the code comment and the earlier SEC-172 fix both say so).
- *Does the alert leak detail?* No. It renders the fixed string `t.decideFailed` ("That didn't go
  through. Try again."); no code, message, id or card text. The error object never leaves the
  server.
- *Can the badge and the unread dot be driven to disagree with the database?* On the first failure,
  no: `unsettle(id)` and the removal from `readNow` put the dot and the badge back, and both then
  agree with the row. But the `asked` ref still holds the id, so **opening the same card a second
  time sets `readNow` again in `toggle` with no call and no alert**: the dot disappears while the
  badge keeps counting the card and the database still has `read_at` null; a reload shows it
  unread. That is exactly the second half of SEC-183, which Agent 14 did not change, so SEC-183
  stays open. Separately, a rejected promise (the action unreachable, a sign-out redirect) maps to
  `reported: false`, so a real outage of the action is still silent — conservative and
  deliberate, but worth knowing.

**SEC-174 — closed for what it named.** `isId()` is the same `UUID` regular expression `checkId`
uses, and `checkId` now calls it, so for its existing callers the behaviour is unchanged (the same
test, the same `toLowerCase()` on the way out). `inbox/page.tsx` passes `open` on only when
`isId(open)` is true, lower-cased. An array (`?open=a&open=b`) fails `typeof === "string"` and is
dropped, and `tests/ui-inbox-server.test.tsx` covers the repeated parameter, a 5,000-character
value, a path, a script tag, an id with text appended, and nothing at all. Nothing else reads
`open`: in the two files I read it is produced only by Today's link and consumed only as the
`InboxView` prop (I did not read the proxy or other routes for a second reader). What remains is
the design point, not a defect: a GET still marks a card read once the page mounts (AC-18), with
the same attacker preconditions as before (he must already know a random UUID of Khalid's own
card). Recorded as accepted by Khalid.

**SEC-175 — closed, with a deployment condition (SEC-196).** The added line
`revoke execute on function public.dismiss_card(uuid) from public, anon, authenticated;` is
correct and complete for the app: it removes both 0008's explicit grant to `authenticated` and any
execute that `PUBLIC` still carried, it names the exact signature, and it sits inside the same
transaction. It cannot affect `mark_card_read` (a different function, granted two lines above),
and it does not name `service_role`, so whatever grant that role received when the function was
created (Supabase's default privileges) is untouched and the comment "Khalid can still run it by
hand through the service role" holds. The PGlite test now asserts both `authenticated` and `anon`
are refused, and `step5-proactive.test.tsx` was changed from "no card" to "permission denied" and
also asserts `dismissed_at` stays null. *Not checked:* whether the worker itself ever calls
`dismiss_card` (the worker was not named this round); if it does, it does so as the service role
and is unaffected. **Re-running 0009 is safe but useless:** `alter table public.cards add column
read_at timestamptz` has no `if not exists`, so on a database that already has 0009 the statement
errors and the whole transaction rolls back — nothing is applied, including the new revoke. The
right instruction to Khalid is in SEC-196 below.

**SEC-177 — closed.** `scripts/dev-preview.mjs` now resolves `next/dist/bin/next` with
`createRequire(import.meta.url).resolve(...)` and spawns `process.execPath` with an argument
array, no `npx`, no `shell: true`, and exits 1 with a plain message when Next is not installed, so
it can no longer fetch anything from a registry. The arguments stay fixed and the host stays
`127.0.0.1`. The comment is now accurate ("Next still loads every other value in .env.local"). On
the blanking: the five empty strings now go straight from Node to the child with no `cmd.exe` or
`npx.cmd` in between, and `readSupabaseConfig` treats `""` as unset (`?.trim()` then `!url &&
!publishableKey` → null), so `isPreviewMode()` is true. I still cannot prove that Next's own
`.env` loader leaves a defined-but-empty variable alone, because I may not read `node_modules/`;
the visible control is the "Preview mode" banner, which appears in all seven committed
screenshots. Two tests in `ui-acceptance.test.tsx` pin the no-npx, no-shell form.

**The test seam — acceptable, with a note (SEC-197).** The `server-only` alias is declared only in
`vitest.config.ts` under `resolve.alias`; it is not in `next.config.ts`, `tsconfig.json` or any
build script, and the stub file lives under `tests/helpers/`, so it cannot reach a production build
or be imported by application code. It does, however, apply to every test file, so the suite can no
longer catch a client component that wrongly imports a server module — `next build` and the
"server to client" source checks in `ui-acceptance.test.tsx` are the only remaining controls for
that. Recorded as SEC-197 (Info), not a defect.

**Earlier gaps the new tests close.** `ui-inbox-server.test.tsx` now runs the real adapter against
a stand-in client for the fallback codes, three non-schema failures, the cutoff and the mark-read
paths, and the page's `?open=` check; `rls-inbox.test.ts` covers the revoke. So three of SEC-191's
five gaps are closed (SEC-172, SEC-174, and the dismiss grant); the mail-card data gap (SEC-173),
the placeholder-in-production gap (SEC-176) and the two-stacked-approvals gap (SEC-178) are still
untested.

## 2. The guard, AGENTS.md and Agent 17 (SEC-170, SEC-171)

**SEC-170 — closed as a finding; the residue is SEC-194 and SEC-195.** What changed is real and
in the right order of strength:
1. **The skills hold no code at all, and that is now tested.** `test_the_skill_folder_holds_only_text`
   refuses any suffix outside `.md`, `.txt` and no-suffix and refuses a `scripts/` folder;
   `test_every_file_matches_the_hash_in_source_md` pins every file to the SHA-256 in `SOURCE.md`
   beside a 40-character commit and fails if the folder and the list differ;
   `test_no_hidden_characters_in_the_skill_text` covers control, bidi and zero-width characters.
   This is the control that actually matters, because it removes the thing to run.
2. **AGENTS.md carries the rule** (lines 93 to 102) as a non-negotiable bullet, which every
   session reads, not only Agent 17 — this was the heart of SEC-170 and it is answered.
3. **The guard adds a backstop.** `DESIGN_SKILL_PROGRAMS` / `DESIGN_SKILL_RUNNERS` /
   `DESIGN_SKILL_SCRIPT` are checked in `_check` before the shell and git branches, so the block
   also applies inside `sh -c`, `bash -c`, `eval`, `powershell -Command` and `cmd /c` (the
   wrapper recursion reaches it), and `tests/test_design_skills_guard.py` covers 15 command forms
   including `& .claude\skills\impeccable\scripts\impeccable.cmd doctor` and
   `Start-Process npx -ArgumentList 'impeccable','live'`, plus 6 forms that must still be allowed.
   I traced the PowerShell forms through `_segments` and `_name` by hand and they do reach the
   block.
4. **Agent 17** has no shell, writes one file, is told never to read a key or secret file and
   never to run the skills.

*Is the guard the right place at all?* As a backstop, yes, and it is cheap. But it cannot be the
control: it blocks names, and the risk it is aimed at ("download and run unreviewed code as
Khalid") has other doors that this guard does not close — `git clone`, `git fetch` and ordinary
package installs are all allowed by policy, and a session can write a script of its own and run it
under any name. So the honest reading is: the *finding* is closed because the skills carry no code,
the hashes are pinned and the rule is where everyone reads it; the *guard rule* is a narrowing, and
two concrete ways around it are below.

**SEC-171 — closed, with one leftover sentence.** The agent file now says, in order: the Snafi
project folder is `apps/snafi-web/`, it may read that folder's `src/` and `docs/`, it writes
`docs/UI.md` and nothing else, it never reads `.env`, `.env.local` or any key or secret file, and
it never runs the skills. That removes the write-anywhere reading and names the secret file, which
is what SEC-171 asked for. Leftover, not worth its own row: line 24 still ends "Never read or
write ... REEMA's own code", and Snafi and `.claude/skills/` are REEMA's own code, so the carve-out
in lines 14 to 17 and line 22 is what resolves it. One clause ("except the Snafi paths named
above") would end the overlap. `.reema/`, `.next/` and `node_modules/` are not named, but "write
one file only" plus "read that folder's src/ and docs/" covers them in practice. I did not read
`.claude/settings.json`, so I still cannot say what it denies Agent 17 by path.

## 3. The measurements and the screenshots

I read `MEASUREMENTS_ui_inbox.md` and opened all seven JPEGs. **Every one shows sample data only.**
The visible content is "Sample: ..." titles, `sample.person@example.com`, `example.com` links, the
two Arabic "نموذج" lines, `send_test_message` as the tool, generic tasks, and the 200-character
test word and long test URL. No real mailbox, sender, contact, event, place, address, phone,
token, key, URL of Khalid's own, Supabase project reference or session value appears, and the
"Preview mode: Supabase is not configured" banner is on every shot, which is the evidence that the
preview really ran without the real project. The only personal item is Khalid's first name in the
greeting ("Good afternoon, Khalid" / "مساء الخير، خالد") and the Jeddah date, which are already
throughout the repository.

**Committing them is acceptable**, with two notes recorded as SEC-198: these files leave the PC
when Khalid pushes main (the repository should be private, which I cannot verify from here), and I
cannot read JPEG metadata, so camera/tool EXIF or an embedded file path has not been checked —
a one-line `exiftool`/`magick identify` check by Ahmad would settle it. The document itself is
careful about its limits (one Chromium engine, not Safari, no real phone), and the two cosmetic
items it raises are not security matters.

## New findings this round

| ID | Severity | File:line | What an attacker (or a failure) could do | Fix | Status |
| --- | --- | --- | --- | --- | --- |
| SEC-194 | Low | `.claude/hooks/dev_guard.py:121-124,311-317`; `tests/test_design_skills_guard.py:66-85` | **A version or a `--package` option walks past the design-skill block.** The runner branch compares `_name(word)` with `{"impeccable", "taste-skill"}`, and `_name()` strips a path and an `.exe/.cmd/.bat/.com/.ps1` suffix but not an npm version specifier. So `npx impeccable` is blocked while **`npx impeccable@latest`, `npx impeccable@1.2.3` and `npm install impeccable@latest` are not** (`_name("impeccable@latest")` is `"impeccable@latest"`). The same for `npx --package=impeccable -c "impeccable context"`: words starting with `-` are skipped by the filter, and the quoted command stays one token (`"impeccable context"`), so neither half matches. `node impeccable.js` also passes (`.js` is not stripped). Each of these is the exact action the rule exists to stop: an unpinned download that then runs as Khalid, with the Snafi keys readable to it (SEC-51). It needs a session that decides to "make the launcher work", not an outside attacker. | In the runner branch, compare the package word with its version cut off (`piece.split("@")[0]` for a non-scoped name, the part after the second `@` for `@scope/name@version`) and strip a `.js`/`.mjs`/`.cjs` suffix as well; include the values of `--package`/`-p`/`--yes`-style options instead of skipping every `-` word, and re-check the text after `npx -c` / `npm exec --` as a nested command. Add the four forms above to `test_design_skills_guard.py`. | Open |
| SEC-195 | Info | `.claude/hooks/dev_guard.py:121-124,311-317` | **The block is by name and by one path shape, so a copy, a rename or a fetch of the launcher is not caught — the guard is a narrowing, not a wall.** `DESIGN_SKILL_SCRIPT` matches only `.../skills/<impeccable|taste-skill|frontend-design>/scripts/...` or a file named `gate.mjs`. A launcher fetched or written under another name and another path (`node tools/ui-check.mjs`, `python scripts/polish.py`) is not matched at all; `bash ./impeccable` after a `cd` into the folder is not matched either (the first word is `bash`, and the relative path has no `/skills/`); and nothing blocks `git clone`, `git fetch` or an ordinary `npm install` of some other package, so the upstream launcher can still be brought onto the PC by a session that wants it. This is the documented limit of a backstop that runs as Khalid, not a defect introduced by this change; the controls that hold are the markdown-only install with pinned hashes (tested) and the AGENTS.md rule. | None required. If Khalid wants it tighter, the stronger step is still option (a) of SEC-170 (move the two folders out of `.claude/skills/`), and the stronger general control is reviewing what a session installs, which AGENTS.md already says the approved package list, not the hook, provides. | Recorded |
| SEC-196 | Low | `supabase/migrations/0009_inbox_read.sql:13,37-42`; `apps/snafi-web/README.md` (the deploy note, not re-read this round) | **The `dismiss_card` revoke was appended to a migration that may already have been applied, and re-running the file cannot deliver it.** `alter table public.cards add column read_at timestamptz` has no `if not exists`, so on a database that already ran the earlier 0009 the file fails at line 13 and the whole transaction rolls back: the revoke is silently not applied and `authenticated` keeps the right to hide any card for good — the SEC-175 fix would be absent in production while the repository and the tests say it is there. Nothing is damaged by the failed run (it rolls back), so the risk is a false sense that the fix is live. | Tell Khalid in plain words: if 0009 has **not** been run on the live project, run the file as it now stands, once. If it **has** already been run, do not re-run the file; run only the one line `revoke execute on function public.dismiss_card(uuid) from public, anon, authenticated;` in the SQL Editor. Either way, check afterwards with `select has_function_privilege('authenticated', 'public.dismiss_card(uuid)', 'execute');` and expect `false`. Put the same two sentences in the README's deploy note, and give later migrations their own file number rather than editing a shipped one. | Open |
| SEC-197 | Info | `vitest.config.ts:5-12`; `tests/helpers/server-only.ts` | **The `server-only` stub is test-only, but it applies to every test, so the suite can no longer catch a server/client boundary mistake.** The alias lives in `resolve.alias` in `vitest.config.ts` alone — not in `next.config.ts`, `tsconfig.json` or any build step — and the stub is an empty `export {}` under `tests/`, so it cannot reach the build or production code; Next's real marker still throws in a client bundle. The cost is that a client component which wrongly imports a server module (and with it the adapter layer and anything it reads) now loads happily under Vitest, so only `next build` and the source checks in `ui-acceptance.test.tsx` would catch it. | Keep the "server to client" source checks; keep `npm run build` in every test report (Agent 15 ran it this round). Optionally limit the alias to the files that need it, or add one test that asserts no file with `"use client"` imports `@/adapters/index`, `@/core/today-data` or `@/adapters/mailbox/supabase`. | Recorded |
| SEC-198 | Info | `apps/snafi-web/docs/screenshots/*.jpg` (7 files); `apps/snafi-web/docs/MEASUREMENTS_ui_inbox.md` | **Checked: the seven screenshots carry sample data only; two things I could not check.** I opened every file. Content: "Sample: ..." titles, `sample.person@example.com`, `example.com` links, the two Arabic "نموذج" messages, the test long word and long URL, `send_test_message` as the tool, and the "Preview mode: Supabase is not configured" banner in all seven. No real sender, contact, subject, event, place, address, phone number, key, token, session value or Supabase project reference. The only personal items are Khalid's first name in the greeting and the Jeddah date, both already throughout the repository. **Not checked:** the files' JPEG metadata (I cannot read binary EXIF), and whether the GitHub repository these will reach when Khalid pushes main is private. | Ahmad, in a shell: check the EXIF of the seven files (`magick identify -verbose` or `exiftool`) and strip it if anything names a machine, a user folder or a tool version. Khalid: confirm the repository is private before the next push. | Recorded |

## Where every earlier finding stands after this round

**Now closed (re-reviewed by me):**
- **SEC-170** (was Medium) — skills are markdown only and hash-pinned by test, the rule is in
  AGENTS.md for every session, the guard blocks the named forms, Agent 17 is tightened. Residue:
  SEC-194 (Low), SEC-195 (Info).
- **SEC-171** (was Low) — write scope, read scope and the secrets ban are now explicit; one
  leftover sentence noted above, no new row.
- **SEC-172** (was Low) — narrow code list, every other error propagates, the alert says nothing
  about the error, and the behaviour is now run for real in a test. Remove the fallback once 0009
  is live.
- **SEC-174** (was Low) — `?open=` is validated on the server with the same UUID pattern and
  well tested; the GET-marks-read design stays, accepted under AC-18.
- **SEC-175** (was Low) — the revoke is correct and tested; its delivery is tracked as SEC-196.
- **SEC-177** (was Low) — no `npx`, no shell, fails closed, comment corrected, two tests pin it.
- **SEC-192** (was Info) — Agent 15 read the installed Next 16.4.5 boundary: it passes both
  `reset` and `retry`, `retry` is the right one for a data-load failure, and a test now fails if
  the name disappears. I did not read `node_modules/` myself; I am accepting Agent 15's quoted
  source and the test.
- **SEC-193** (was Info) — drift and hidden characters are now proven by test against the
  recorded hashes. One limit stays recorded, not a finding: the test proves the folder matches
  `SOURCE.md`, not that `SOURCE.md` matches the upstream commit (no network here), and the
  hidden-character test reads `*.md` only, not the `.txt`/`LICENSE` files (the hashes cover
  those for drift).

**Still open, unchanged in severity:**
- **SEC-173** Low — Agent 14 changed no code; Ahmad's reading of `proactive/scheduler.py` (which
  I did not read) says a mail card's body is only the subject plus a "Received" line, so what
  reaches the browser beyond the screen is one time line. Real exposure is now very small; for
  Khalid to close or to fix with the one-line server-side trim.
- **SEC-176** Low (placeholder Today allowed in production), **SEC-178** Low (an approval can move
  under the finger — the browser measurements did not test two stacked approvals), **SEC-179** Low
  (bidi and zero-width characters, with SEC-26), **SEC-180** Low (wording), **SEC-181** Low
  (newest-100 window), **SEC-182** Low (whole chat rows, `select *`).
- **SEC-183** Info — half addressed: a real failure is now reported once. The re-open path still
  clears the unread dot with no call, so the dot, the badge and the row can disagree.
- **SEC-191** Info — three of five gaps closed by the new tests; the mail-card data, the
  placeholder-in-production and the two-stacked-approvals tests are still missing.
- **SEC-22**, **SEC-26** — unchanged, as recorded above.

**New this round:** SEC-194 (Low), SEC-196 (Low), SEC-195, SEC-197, SEC-198 (Info).

**Open counts after this round:** Critical 0, High 0, Medium 0, Low 9 (SEC-173, 176, 178, 179,
180, 181, 182, 194, 196), Info 3 open (SEC-183, SEC-191, and the SEC-193 upstream limit) plus the
recorded rows.

## What I did not review this round

- The worker (`src/snafi_worker/`): `proactive/scheduler.py` for the mail-card format, the backup
  and restore of `cards`, and whether anything there calls `dismiss_card`. Not named; I took
  Ahmad's reading as a statement, not as a check of mine.
- `.claude/settings.json` and its tests, `.claude/launch.json` (unchanged), and whether the hook
  is actually wired to every tool call — I read the hook's code, I did not run it.
- `node_modules/`, `.env.local`, `.next/`, the lock file, the built output, and therefore Next's
  own `.env` loading and the error-boundary source.
- The live Supabase database and the Vercel settings: whether 0009 has already been applied, and
  what `SNAFI_TODAY_ADAPTER` is set to there (SEC-176).
- Any measurement of my own: no browser, no screen reader, no device. The measurements document
  and the test report are read as reports; I did not verify a single number in them, and I did not
  run the test suite.
- JPEG metadata in the screenshots, and whether the GitHub remote is private.
- `docs/UI.md` after line 772, migrations 0001 to 0007, the proxy, the cookie policy and the
  sign-in path (unchanged, not re-read), and whether `security_diff_ui_fixes.patch` matches the
  branch.

**Blocks merge: no** (open Critical 0, open High 0). The Low and Info items above are Khalid's to
decide, with SEC-196 the one that needs a decision *before* the next deploy. Khalid decides; this
re-review is not a certification.

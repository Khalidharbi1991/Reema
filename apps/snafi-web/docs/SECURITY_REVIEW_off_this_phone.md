# Snafi: security review of "Off removes only this phone" (SEC-153 decision) (Agent 16)

Nov 15, 2026 · branch `fix/snafi-off-this-phone` (one commit, 75b883b, on main a717ea3) · reviewer: Agent 16 (`reema-agent16-security`).

**Scope:** Ahmad reports that Khalid decided SEC-153 in his own words: "Off removes only the phone I'm holding. Add a separate 'Turn off on all phones' option with a confirm step." I did not see that message. The change has four parts:
- `disablePush()` in `core/push-client.ts` now returns whether this phone had a subscription. It removes the phone's address with `remove_push_subscription`, cancels the phone's own subscription in a `finally`, and throws `PushStepError("server", "refused")` when the server says no.
- In `SettingsForm.tsx`, Off calls only `disablePush`. A new "Turn off on all phones" button opens an inline confirm, and only its Yes button runs `disablePush` and then saves `push_enabled = false`.
- New English and Arabic strings.
- The "Turning it off" section of `docs/snafi/PUSH_SETUP.md`.

**What I read:**
- `apps/snafi-web/.reema/security_diff_off_this_phone.patch` in full. It covers five files: `SettingsForm.tsx`, `core/push-client.ts`, `i18n/messages.ts`, `tests/settings-push-livebug.test.tsx` and `docs/snafi/PUSH_SETUP.md`.
- The whole current `src/app/(app)/settings/SettingsForm.tsx`, `src/core/push-client.ts`, `src/app/(app)/settings/page.tsx`, `src/app/(app)/actions.ts` and `src/adapters/mailbox/supabase.ts`.
- The whole of `supabase/migrations/0008_proactive.sql`.
- `docs/SECURITY_REVIEW_push_per_phone.md` and the head of `docs/SECURITY_REVIEW.md`.

**I ran nothing.** I ran no tests, eslint, tsc, git, browser or scanner, and made no network call. Ahmad reports web 190 passed, Python 1393 passed, and eslint and tsc clean. I have not checked any of those results. This review is not a certification. Khalid decides.

## Summary

**Open Critical 0, open High 0. No finding here blocks merging `fix/snafi-off-this-phone` to main.** Khalid decides.

**Earlier rows this round closes:**
- **SEC-153: closed.** It is built as Khalid decided (option A), and I re-reviewed it.
- **SEC-154: closed.** The note now says "Notifications are on for your account, but this phone isn't signed up yet…" in English, with Arabic to match. I re-reviewed it in the diff's context lines.
- **SEC-158: closed.** The missing test (Off on a phone that was never signed up) now exists.

**Answers to Ahmad's five questions:**

1. **Yes, `remove_push_subscription` still removes only the caller's own row for the address given.**
   - The diff does not touch the function.
   - In `0008_proactive.sql:178-192` it is `security definer` with `search_path = ''`. It refuses a null `auth.uid()`, and it runs only `delete … where user_id = uid and endpoint = p_endpoint`.
   - Only `authenticated` may run it (revoked from public and anon).
   - The server action calls `requireSession()` and passes `String(endpoint)`. The adapter refuses anything over 1000 characters.
   - Caveat: I did not check whether a later migration redefines the function. See SEC-161.
2. **Yes on both points, within the screen's own code.**
   - Off can never change `push_enabled`. `turnOff` never calls `saveValues` and never changes `wanted`, so a Save tapped later still sends the account's value.
   - "All phones" cannot run without the confirm step. `turnOffAll` is bound only to the Yes button, which exists only while `confirmAll` is true, and Cancel only sets `confirmAll` to false.
   - This is a screen control, not a server control. Anyone with a signed-in session can still call `saveSettings` with `pushEnabled: false` directly, as before. That is by design. See SEC-162.
3. **Yes, Off on the last signed-up phone leaves `push_enabled` true with no phone. That is harmless for security.**
   - No data is exposed and no right is gained.
   - Cards still appear on Today.
   - The real effects are on the screen. The Off note says "Your other phones still do", which is not true when there is no other phone (SEC-164). "Send a test" stays enabled and says "sent" when nothing can arrive.
   - I did not read the worker's push sender, so the "no phone subscribed, delivered silently" behaviour is Ahmad's report. See SEC-165.
4. **Yes, the other phones' rows stay in place, and pushes to them resume when On is tapped on any phone.**
   - The phone that did "all phones" has its own row removed, so it gets nothing until On is tapped on it.
   - The texts only partly promise this. "Tap On on a phone to turn them back on" is right for the other phones. The new doc line "Each phone signs up on its own: tap On on every phone you want notifications on" suggests the other phones need their own On, which they do not.
   - "All phones" is also not a way to cut off a lost phone, and no text says so. See SEC-166.
5. **Nothing else changed, as far as the patch shows.**
   - The patch touches no file under `src/snafi_worker/`, `supabase/migrations/`, `src/adapters/`, the server actions, `public/sw.js`, the CSP or the headers.
   - No package is added and no network call is added.
   - The SEC-140 test now goes through the "all phones" path, which is the only path that still changes `wanted`. That is correct.
   - I did not confirm with git that commit 75b883b matches the patch file. See SEC-169.

**One new Low defect to fix:** SEC-163. When the first two browser steps fail, the screen says "This phone is turned off" and shows Off, but the phone was never unsubscribed and its address is still saved.

**For Khalid to decide:**
- **Low:** SEC-163 (fix recommended), SEC-164 (wording), SEC-166 (wording, or what "all phones" should remove).
- **Info:** SEC-161, SEC-162, SEC-165, SEC-167, SEC-168, SEC-169.

## Findings

| ID | Severity | File:line | What an attacker (or a failure) could do | Fix | Status |
| --- | --- | --- | --- | --- | --- |
| SEC-153 | Low | `SettingsForm.tsx:135-164`, `:211-233`; `push-client.ts:134-150` | **Re-review of the earlier row.** Before this change, Off acted on the whole account. | **Closed (Nov 15, re-reviewed).** Built as Khalid decided: Off removes only this phone, and "Turn off on all phones" switches the account off only after its confirm step (SEC-162). What is left is in SEC-163, SEC-164 and SEC-166. | Closed |
| SEC-154 | Low | `messages.ts` (`pushOtherPhone`, en and ar) | **Re-review of the earlier row.** The note claimed another phone was getting notifications. | **Closed (Nov 15, re-reviewed).** The note now says only what the code knows ("on for your account, but this phone isn't signed up yet"). The new Off notes repeat the old problem; see SEC-164. | Closed |
| SEC-158 | Info | `tests/settings-push-livebug.test.tsx` | **Re-review of the earlier row.** There was no test for Off on a phone that was never signed up. | **Closed (Nov 15).** The new test "Off on a phone that was never signed up changes nothing" expects no `save` and no `unsubscribe` call. | Closed |
| SEC-161 | Info | `supabase/migrations/0008_proactive.sql:178-192`, `actions.ts:92-100`, `adapters/mailbox/supabase.ts:172-176` | **Checked: removing an address touches only the caller's own row.** The function is `security definer` with `set search_path = ''`, takes the user from `auth.uid()` (refusing null), and deletes only `where user_id = uid and endpoint = p_endpoint`. EXECUTE is revoked from public and anon and granted to authenticated. The action calls `requireSession()`, and the adapter refuses anything that is not a string or is over 1000 characters. Another user's address cannot be removed, even when guessed. The function returns nothing, so `disablePush` returning `true` means "this browser had a subscription", not "a row was deleted". The note "This phone won't get notifications any more" is still true either way, because the browser subscription is cancelled. **Not checked:** whether a migration after 0008 redefines this function. This change touches no migration, so this round changes nothing there. | None needed. Ahmad: name any later migration that touches `remove_push_subscription` in a future round. | Recorded |
| SEC-162 | Info | `SettingsForm.tsx:136-149`, `:152-164`, `:211-233` | **Checked: Off cannot change the account setting, and "all phones" needs the confirm step.** `turnOff` calls only `disablePush`, `setDevice` and `setNote`. It never calls `saveValues` and never sets `wanted`, so a later Save sends the account's own value (the SEC-140 rule still holds). `turnOffAll` is referenced only by the Yes button inside `{confirmAll && …}`. `confirmAll` becomes true only from the "Turn off on all phones" button, which is shown only while push is on and the confirm is closed. Cancel only sets `confirmAll` to false. Both push jobs share the `busy.push` guard. The confirm opens below the button row, and the "all phones" button disappears when it opens, so a fast double tap lands on empty space or the Test button, not on Yes. These are screen rules only. A signed-in session can always call `saveSettings` itself, as it always could. The confirm box is `role="alertdialog"` but does not move focus to itself, which is an accessibility point, not a security one. | None needed. Optional: move focus to the confirm box when it opens. | Recorded |
| SEC-163 | Low | `push-client.ts:140-142`; `SettingsForm.tsx:141-145`; `messages.ts` (`offThisFailed`, en and ar) | **The screen can say "turned off" when this phone was not turned off.** No attacker is needed. `disablePush` runs the `worker` step (`getRegistration`) and the `subscribe` step (`getSubscription`) **before** the `try/finally`. If either one times out or fails (for example, the slow service worker from the Nov 15 live bugs), it throws a `PushStepError` with step `worker` or `subscribe`. In that case `sub.unsubscribe()` never runs and the server row is never removed. `turnOff` still shows "This phone is turned off, but its address couldn't be removed: …" and calls `setDevice(false)`, so Off shows as selected. The phone stays subscribed, its row stays, and it keeps getting notifications, while the screen says it will stop. Effect: Khalid believes a phone is quiet when it is not. Only fixed lock-screen text is shown (SEC-124), so the exposure is small, but the screen says something untrue. | Agent 14: in `turnOff`, show the "turned off, but its address couldn't be removed" text only when `e.step === "server"`. For any other step, show "Couldn't turn this phone off: {step}. Try again." (with Arabic to match), and do not `setDevice(false)`; set it back to `null` or keep its old value. Add a test where `getSubscription` rejects or times out, expecting no "turned off" text and Off not pressed. | Open |
| SEC-164 | Low | `messages.ts` (`offThisDone`, `offThisNone`, en and ar) | **The Off notes claim other phones are on.** "Your other phones still do" and "Your other phones still get them" are shown whatever the facts are. They are false (1) when this was the last signed-up phone (SEC-165), and (2) when the account setting is off. With the account off, a signed-up phone shows Off as selected, and tapping it removes the phone and still says the other phones get notifications. This repeats the SEC-154 problem: the screen does not know about other phones, and the note gives false confidence that reminders arrive somewhere. Nothing private is shown. | Neutral wording, for example "This phone won't get notifications any more. Other phones you signed up are not changed." and "This phone wasn't signed up, so nothing changed." (with Arabic to match). Optionally show the number of saved phones from the server, only as a number and never the addresses. | Open (for Khalid) |
| SEC-165 | Info | `SettingsForm.tsx:136-149`, `:199-202`, `:207` | **Off on the last phone leaves the account on with no phone. This is harmless for security.** After this, `push_enabled` is true and `push_subscriptions` has no row for Khalid. No data is exposed and no right changes. As Ahmad reports (I did not read the worker's sender), the worker delivers silently with "no phone subscribed", and cards still appear on Today. On the screen, the "on for your account, but this phone isn't signed up yet" note appears once the Off note is cleared, which is accurate. "Send a test" stays enabled and says "sent" when nothing can arrive (like SEC-155). Tapping On on any phone later works at once, because the account setting is already on. | None needed for security. Optional: disable Test when `device === false`, or have the test job report "no phone signed up". | Recorded |
| SEC-166 | Low | `messages.ts` (`offAllConfirm`, `offAllDone`), `docs/snafi/PUSH_SETUP.md` ("Turning it off") | **After "all phones", tapping On on any phone also turns the other phones back on, and the texts only partly say so.** "All phones" removes only the row of the phone it was done on and sets `push_enabled = false`. Every other phone's row stays. When On is tapped on any phone, `push_enabled` becomes true and every phone that kept its row gets notifications again, without anyone touching that phone. `offAllDone` ("Tap On on a phone to turn them back on") fits this. The new doc line "Each phone signs up on its own: tap On on every phone you want notifications on" suggests the opposite, and so does the confirm text, which does not mention it. The risk: if Khalid uses "all phones" to stop a lost, sold or family-held phone, the next On anywhere starts sending to it again. It sees only the fixed lock-screen text plus the kind and timing of each message (SEC-124), but it was not what he meant. No text tells him that removing one phone is done on that phone itself. | Khalid decides. **Wording only:** add to the confirm text and the doc: "When you tap On again on any phone, your other signed-up phones get notifications again too. To remove a lost phone for good, tap Off on that phone, or ask Ahmad." and limit the "each phone signs up on its own" line to new phones. **Or behaviour:** make "all phones" also delete every one of the caller's rows, using a new own-rows-only RPC (`delete … where user_id = auth.uid()`), so each phone must tap On again. That is a scope change and needs Khalid's yes. | Open (for Khalid) |
| SEC-167 | Info | `push-client.ts:146-148` | **If the server removes the row but the browser fails to cancel the subscription, the screen and the server disagree.** `sub.unsubscribe().catch(() => undefined)` hides the failure, `disablePush` returns `true` and the screen shows Off. On the next load, `deviceSubscribed` finds the old subscription, so with the account on the screen shows On, but the server has no row and nothing arrives. Tapping On re-saves it and fixes this. The same was true before this change. | Optional: have `disablePush` report an unsubscribe failure, so the screen can say "try again". | Recorded |
| SEC-168 | Info | `SettingsForm.tsx:154`, `:161-163` | **If "all phones" fails to save, a later Save turns push off anyway.** `turnOffAll` sets `wanted.current = false` before saving. If the save fails, the screen keeps showing On (`setPush` is not called) and says "couldn't save", but `wanted` stays false, so the next Save sends `push_enabled = false`. This matches the SEC-140 rule ("what Khalid last asked for"), and he did ask for off, so it is not wrong. But the screen shows On while the next Save sends off. The same was true of the old Off. | Optional: set `wanted` back to its old value when the save fails, as `turnOn` does. | Recorded |
| SEC-169 | Info | patch, all hunks | **Checked: nothing else changed, and the new text is safe.** Five files changed. Nothing under `src/snafi_worker/`, `supabase/migrations/`, `src/adapters/`, the server actions, `public/sw.js`, the CSP or the headers. No package and no network call are added. The new strings are fixed text. The only fill-in, `{step}`, is replaced with a fixed step label plus `e.detail`, which is `"refused"`, `"timed out"`, `"error"` or a letters-only error name (`nameOf`). React renders it as text, with no `dangerouslySetInnerHTML`. Nothing is logged and no endpoint is shown. The Arabic "اضغط تشغيل" matches the On label. The tests use `fakeEnv()` and stand-in functions only, with no real key or address. The SEC-140 test now goes through the "all phones" path, which is correct, because Off no longer changes `wanted`. The server-refusal test covers `{ok: false}` but not a server timeout. The `finally` covers a timeout too. I did not confirm with git that commit 75b883b matches the patch file. | None needed. Optional: a test where the server step times out. | Recorded |

**Open counts for this round:** Critical 0, High 0, Medium 0, Low 3 (SEC-163, SEC-164, SEC-166), Info 6 (SEC-161, SEC-162, SEC-165, SEC-167, SEC-168, SEC-169). Closed this round: SEC-153, SEC-154, SEC-158.

## Not reviewed

- The worker's push sender, its "no phone subscribed" handling, and whether it removes an address after a 410. I relied on Ahmad's report and earlier rounds.
- Migrations after 0008, in case one redefines `remove_push_subscription` or `save_settings`.
- `public/sw.js`, the CSP and the headers (not changed).
- The whole of `messages.ts` and the test file. I read only the changed hunks.
- The rest of `docs/snafi/PUSH_SETUP.md` beyond the changed section.
- How real Android Chrome and iOS Safari behave on `getSubscription` or `unsubscribe` failures, and how the app behaves after deploy.
- The reported test, lint and type-check results, and whether commit 75b883b matches the patch file. I have no shell and ran nothing.
- Khalid's message deciding SEC-153 (relayed by Ahmad).

**Open Critical: 0. Open High: 0.**

## After this check (Nov 15, by Ahmad as the coding agent; not re-checked by Agent 16)

- **SEC-163 (fixed, awaiting re-check):** `turnOff` says "This phone is turned off…" only when the failing step is `server` (the one inside `disablePush`'s `finally`). If the worker or subscribe step fails, nothing was cancelled: the screen says "Couldn't turn this phone off: {step}. It may still get notifications. Try again." and leaves the phone's state as it was. Test where `getSubscription` fails.
- **SEC-164 (fixed, awaiting re-check):** the Off notes no longer claim other phones still get notifications ("Other phones are not changed."; the not-signed-up note says only that nothing changed).
- **SEC-166 (wording fixed, awaiting re-check):** `PUSH_SETUP.md` now says the other phones stay signed up and On on any phone turns them all back on (the phone that turned it off needs its own On), and that "all phones" does not remove a lost phone's sign-up. Deleting all rows on "all phones" (a new database function) was not built: that would be a scope change for Khalid.
- **SEC-168 (fixed, awaiting re-check):** if saving "all phones" fails, the push state Save sends goes back to what the account has.
- Both suites pass (web 191, Python 1393; eslint and tsc clean).

Still for Khalid: SEC-166's alternative (delete all phones' rows on "all phones"); Info SEC-161, 162, 165, 167 and 169. Open Critical 0, open High 0.

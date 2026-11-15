# Snafi: security review of the Settings push per-phone live-bug fix (Agent 16)

Nov 15, 2026 · branch `fix/snafi-push-per-phone` (one commit, a0ae0b2, on main 68df683) · reviewer: Agent 16 (`reema-agent16-security`).

**Scope:** a small fix for a live bug. Push works on iPhone but not on Android, and Android shows no error. Ahmad's read-only Supabase check found one `public.push_subscriptions` row (for `web.push.apple.com`) and one `save_push_subscription` call, so Android was never subscribed. The cause: Settings showed On/Off from `user_settings.push_enabled`, which is per account. Once the iPhone turned push on, Android also showed On, though it had no subscription. The fix adds `deviceSubscribed()` to `core/push-client.ts` and makes `SettingsForm.tsx` show On only when push is on for the account AND this phone has a subscription. When push is on for the account but this phone has none, the screen shows a note asking him to tap On.

**What I read:** `apps/snafi-web/.reema/security_diff_push_per_phone.patch` in full (five files: `src/app/(app)/settings/SettingsForm.tsx`, `src/core/push-client.ts`, `src/i18n/messages.ts`, `tests/settings-push-livebug.test.tsx`, `tests/sw-install.test.ts`). I also read the whole current `SettingsForm.tsx` and `push-client.ts`, the Arabic settings strings in `messages.ts` (lines 225-254), the head of `docs/SECURITY_REVIEW.md`, and `docs/SECURITY_REVIEW_sw_offline.md` for the format.

**I ran nothing.** That means no tests, eslint, tsc, git, browser or scanner, and no network call. Ahmad reports web 186 passed, Python 1393 passed, and eslint and tsc clean. I have not checked any of those results or his Supabase reading. This review is not a certification. Khalid decides.

## Summary

**Open Critical 0, open High 0. No finding here blocks merging `fix/snafi-push-per-phone` to main.** Khalid decides.

Answers to Ahmad's three questions:

1. **Nothing new reaches the server or the screen.** `deviceSubscribed()` makes only two read-only browser calls: `serviceWorker.getRegistration("/")` and `pushManager.getSubscription()`. It reduces the result to `true`, `false` or `null`.
   - It never registers a worker, subscribes, asks for permission or calls a server action.
   - It never reads, returns, shows or logs the subscription's endpoint or keys.
   - The only new screen text is two fixed strings (English and Arabic) with no interpolation, rendered by React as text.
   - The `save` payload is unchanged.
   - See SEC-157.
2. **Yes, Off is now misleading, and it needs a decision from Khalid (SEC-153, Low).**
   - On a phone with no subscription, Off is shown as already selected while the account is still on. Tapping it looks like it does nothing.
   - In fact it saves `push_enabled = false` for the whole account, which stops the iPhone too.
   - The same thing was already true before this fix on a phone that does have a subscription: Off there also stops every phone. The new per-phone wording makes it more surprising.
   - This is a usability and availability risk (missed reminders), not a data exposure. It does not block the merge.
3. **Nothing else changed, as far as the diff shows.** The diff touches no file under `src/snafi_worker/`, `supabase/migrations/`, `src/adapters/`, the server actions or `public/sw.js`.
   - In `SettingsForm.tsx`, `enablePush`, `disablePush`, `saveValues`, `wanted` (SEC-140) and the busy flags are unchanged.
   - The `sw-install.test.ts` change is test-only.
   - I did not confirm with git that the commit matches the patch file.
   - See SEC-160.

**For Khalid to decide:**
- **Low:** SEC-153 (what Off should mean; open), SEC-154 (wording of the new note; open).
- **Info:** SEC-155, SEC-156, SEC-157, SEC-158, SEC-159, SEC-160. These are recorded checks or optional polish; none needs action.

## Findings

| ID | Severity | File:line | What an attacker (or a failure) could do | Fix | Status |
| --- | --- | --- | --- | --- | --- |
| SEC-153 | Low | `SettingsForm.tsx:134-145`, `:172-177` | **Off is shown per phone but acts on the whole account.** No attacker is needed. On Android, which has no subscription, `thisPhoneOn` is false, so Off shows as pressed (`aria-pressed="true"`) while the account is on. If Khalid taps Off (for example to "make sure"), `disablePush` finds no subscription and returns. Then `saveValues(false)` sets `push_enabled = false` for the account, and the worker stops every push, including the iPhone's. The screen just says "Saved". The iPhone's Settings still shows On (it has a subscription, and its `push` state was read at page load) until it reloads, but it gets nothing. The same account-wide effect happened before this fix on a phone with a subscription (comment at `:139`). The new per-phone wording makes it more surprising. Effect: missed reminders and briefs, with no sign of it on the other phone. There is no data exposure and no privilege change. | **Khalid decides which meaning Off has.** **Option A (per phone, closest to the new screen):** Off removes only this phone's subscription (`disablePush`) and keeps `push_enabled` on. Add a separate "Turn off on all phones" control that saves `false`. When the phone has no subscription and the account is on, make Off a no-op (or disable it). **Option B (keep account-wide):** label it "Off on all phones", and on a phone with no subscription ask for confirmation first ("This also stops notifications on your other phone"). Either way, add a test: account on, this phone not subscribed, tap Off, then check the result against the chosen meaning. | Open (for Khalid) |
| SEC-154 | Low | `messages.ts:110`, `:242`; `SettingsForm.tsx:180-183` | **The new note says more than the screen knows.** It says "Notifications are on for your other phone". The code knows only that `push_enabled` is true for the account and that this phone has no subscription. The iPhone's row may have been removed (the worker deletes an address after a 410), or there may be no phone at all, and the note would still say another phone gets them. That could give false confidence that reminders are arriving somewhere. Nothing private is shown. | Neutral wording, for example: "Notifications are switched on for your account, but this phone isn't signed up yet. Tap On to add this phone." (and the Arabic to match). Optionally show the count of saved phones from the server, but only as a number, never the endpoints. | Open (for Khalid) |
| SEC-155 | Info | `SettingsForm.tsx:187` | **Send a test is enabled on a phone with no subscription.** On Android with the account on, Test is enabled (`!push` is false), and the worker sends the test to the iPhone. Android shows "sent", but nothing arrives on Android. This is confusing, not a risk. The lock-screen text stays the fixed private-free text. | Optional: disable Test when `device === false`, or say "sent to your other phones". | Recorded |
| SEC-156 | Info | `SettingsForm.tsx:66-73`, `:128`, `:141` | **Checked: the state handling is sound.** `null` (not known yet, no push support, or no answer within 5 s) falls back to the account value, as before the fix. A timed-out inner promise keeps running but its result is dropped (`within` has already rejected), and the `live` flag ignores results after unmount. In theory the first check could resolve after a fast On or Off and overwrite `setDevice(true/false)`. That needs `getRegistration`/`getSubscription` to answer more slowly than the whole permission, subscribe and server sequence while still within 5 s, so it is practically unreachable, and at worst it is a wrong On/Off highlight until reload. The note is hidden while any other note is shown, including Save's "Saved". That is cosmetic. | Optional: ignore the first check once a push job has set `device` (a ref), and show the note independently of the Save note. | Recorded |
| SEC-157 | Info | `push-client.ts:115-125` | **Checked: no new data leaves the phone or reaches the screen.** The function is read-only (no `register`, `subscribe`, `requestPermission` or `unsubscribe`), calls no server action, and returns only a boolean or `null`. The endpoint and keys are never returned, rendered or logged, and there is no `console` call. The catch block swallows errors without reading their message. The two new strings are fixed, with no `{…}` placeholder and no `dangerouslySetInnerHTML`. The Arabic "اضغط تشغيل" matches the Arabic On label (`pushOn: "تشغيل"`). No new package or network call. | None needed. | Recorded |
| SEC-158 | Info | `tests/settings-push-livebug.test.tsx:128-151` | **Checked: the tests use fakes only.** The two new tests use `fakeEnv()` and stand-in `save`/`subscribe` functions. They make no network call and hold no real key or endpoint. They cover "account on, this phone not subscribed" (note shown, On not pressed, then On subscribes) and "already subscribed" (On pressed). There is no test for Off on a phone with no subscription (see SEC-153). | Add one once Khalid decides SEC-153. | Recorded |
| SEC-159 | Info | `tests/sw-install.test.ts:61-70` | **Checked: test-only change.** The eagerly rejected placeholder promise (which raised the unhandled rejection) is replaced with `null` and an explicit not-null check. `sw.js` is not touched, and the test still requires the 503 offline answer. | None needed. | Recorded |
| SEC-160 | Info | patch, all hunks | **Checked: no other change.** Five files changed. Nothing under `src/snafi_worker/`, `supabase/migrations/`, `src/adapters/`, the settings server actions (`save_push_subscription`, remove, test), `public/sw.js`, the CSP or the headers. Earlier open items (SEC-140, SEC-141, SEC-147 and the rest) are not affected and were not re-checked in this round. I did not confirm with git that commit a0ae0b2 matches the patch file. | None needed. | Recorded |

**Open counts for this round:** Critical 0, High 0, Medium 0, Low 2 (SEC-153, SEC-154), Info 6.

## Not reviewed

- The settings server actions and `save_push_subscription` / RLS (not changed in this round), the worker's push sender, and `public/sw.js` beyond the test that touches it.
- The whole of `messages.ts` and the two test files (only the changed hunks and the Arabic settings strings).
- How real Android Chrome and iOS Safari answer `getRegistration`/`getSubscription` (timing, a subscription that expired on the phone, a cleared site data case), and production behaviour after deploy.
- Ahmad's Supabase reading and the reported test, lint and type-check results.
- Whether commit a0ae0b2 matches the patch file. I have no shell and ran nothing.

**Open Critical: 0. Open High: 0.**

## After this check (Nov 15, by Ahmad as the coding agent; not re-checked by Agent 16)

- **SEC-154 (fixed, awaiting re-check):** the note now says only what the code knows: "Notifications are on for your account, but this phone isn't signed up yet. Tap On to add this phone." (Arabic to match).
- **Waiting for Khalid:** SEC-153 (Off switches push off for the whole account, also on a phone that is not signed up; option A: Off removes only this phone, plus a separate "off on all phones"; option B: keep it account-wide, label it "Off on all phones" and confirm). SEC-155, 156, 158 and 160 are Info.

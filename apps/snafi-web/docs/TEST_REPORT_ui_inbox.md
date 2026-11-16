# Test report: Snafi UI job (Inbox, simpler Today, Chat scroll, mobile fit, calmer look)

Author: Agent 15 (tester). Date: Nov 16, 2026. Branch: `feat/snafi-ui-inbox`.
Scope: `apps/snafi-web/`, against `docs/PRD_ui_inbox.md` (confirmed, section 9 answers applied)
and `docs/UI.md` section 0 (Ahmad's rulings).

Agent 15 did not write the application code and changed none of it. The only file this report
adds or edits besides itself is `tests/ui-acceptance.test.tsx`. Nothing was pushed, deployed or
sent anywhere; no dev server was started; no package was installed; the suite is offline (its
setup makes any `fetch` throw).

---

## 1. Commands run, with their real output

All run inside `apps/snafi-web/` on Nov 16, 2026, after the test file below was finished.

| Command | Result | Counts |
| --- | --- | --- |
| `npm run typecheck` (`tsc --noEmit`) | pass | 0 errors, no output |
| `npm run lint` (`eslint .`) | pass | 0 errors, 0 warnings |
| `npm test` (`vitest run`) | pass | **26 test files passed, 353 tests passed, 0 failed, 0 skipped**; 13.0 s |
| `npm run build` (`next build`, Next 16.4.5, Turbopack) | pass | Compiled in 0.9 s, TypeScript in 2.1 s, 8/8 static pages generated, 7 routes (`/`, `/_not-found`, `/chat`, `/inbox`, `/settings`, `/sign-in`, `/today`) + proxy middleware |

The build asked for no environment setting and no key. It read `.env.local` (already present) and
reported no missing value; nothing was invented.

### 1.1 Failures found and fixed in the test file (not in application code)

The first run of the suite was **3 failed / 346 passed (26 files, 1 failed)**. All three failures
were in `tests/ui-acceptance.test.tsx`, the half-finished file left by the earlier run of this job
that was cut off by a usage limit. Both were faults in the test, not in the app; each was checked
against the app before the test was corrected, and both corrections were then mutation-checked
(M8, M9 below) to prove the tests can still fail.

1. `AC-29 > every colour the components use comes from a token` —
   `tests/ui-acceptance.test.tsx:237`. The test exempted the PWA browser-chrome colour with a
   same-line lookahead (`(?![^\n]*themeColor)`), but in `src/app/layout.tsx` the key `themeColor:`
   is on line 33 and the two literals on lines 34–35, so the exemption never applied.
   `viewport.themeColor` must be a literal: the operating system reads
   `<meta name="theme-color">` and cannot resolve a CSS variable, and it paints no screen. The
   check now removes the whole `themeColor: [...]` block and then forbids every hex (the regex was
   also widened from 6 hex digits to 3–8, so `#fff` is caught too).
2. and 3. `AC-31 > in en` and `AC-31 > in ar` — `tests/ui-acceptance.test.tsx:289`,
   `11:00: expected [ 'AM', 'PM' ] to include undefined`. The test matched times in
   `container.textContent`, which runs one element's text into the next one's: Today renders
   `<bdi>11:00 AM</bdi>` followed by `<span>Design review</span>`, giving the string
   `"11:00 AMDesign review"`, and the test's own "not a word" lookahead then refused the `AM`. No
   time on any screen is missing its period. The check now reads one text node (and one
   `aria-label`) at a time, which is what a reader sees.

After those two corrections and the additions in section 2, the suite is 353/353 green.

---

## 2. What Agent 15 added

`tests/ui-acceptance.test.tsx` (the only test file this agent owns) now holds 34 tests. It already
covered AC-1, AC-6, AC-7, AC-18, AC-26 (text with no `data-slot`), AC-29, AC-31, AC-32, AC-33, the
server-to-client prop risk and the `error.tsx` prop. Agent 15 corrected the three broken checks
above and added one group:

- **"the card query, its fallback (SEC-172) and mark-read, read from the source"** (4 tests) —
  the server half of AC-6, AC-11 and PRD risk 7: the first `cards()` query asks for `read_at`,
  hides dismissed rows and keeps unread-of-any-age or read-inside-7-days; the old query runs only
  after an error and a second error is not swallowed; mark-read goes only through
  `rpc("mark_card_read", { p_id: checkId(id) })` with no `update`/`insert`/`delete` on `cards`;
  and the `markCardRead` server action answers `{ ok: false }` instead of throwing.

**These four are source-text checks, which is weaker than running the code, and the report says so
in the file itself.** The reason is a real limit, written down here as a gap:
`src/adapters/mailbox/supabase.ts`, `src/app/(app)/actions.ts` and every other server module import
Next's `server-only`, which only Next's bundler resolves. There is no `node_modules/server-only`,
so Vitest cannot even load those modules ("Failed to resolve import \"server-only\""). A behaviour
test with a stand-in Supabase client was written and then withdrawn for this reason; it needs one
line in `vitest.config.ts` (`alias: { "server-only": <empty module> }`), which is a change to a
shared config file that Agent 15 was not asked to make. **Recommendation for Agent 11 / Agent 14:
add that alias, then the adapter's query, its fallback and the quiet-failure path can be run for
real.** Until then the live-database seam is covered only by `rls-inbox.test.ts` (the SQL, run for
real in PGlite) and `ui-inbox.test.tsx` (the screen).

---

## 3. AC coverage

"Automated" = a test in `apps/snafi-web/tests/` asserts it and fails when it is broken (checked by
mutation where marked in section 4). "Source check" = the test reads the code, not its behaviour.

| AC | Covered by | Result |
| --- | --- | --- |
| AC-1 bell on signed-in screens, not Sign-in | `ui-inbox.test.tsx` "AC-1"; `ui-acceptance.test.tsx` "AC-1" (per route, `aria-current`) | automated, pass |
| AC-2 badge 1–9 / 9+ / none (Q4: test cards never count) | `ui-inbox.test.tsx` "AC-2 (with Q4)" | automated, pass |
| AC-3 approvals first, cards newest first, kind/title/time/unread mark | `ui-inbox.test.tsx` "AC-3" | automated, pass |
| AC-4 opening the list marks nothing | `ui-inbox.test.tsx` "AC-4" | automated, pass |
| AC-5 tapping expands, marks read, badge drops, still read after reload | `ui-inbox.test.tsx` "AC-5" | automated, pass |
| AC-6 7-day window (read 6 d 23 h shown, unread of any age shown) | `ui-inbox.test.tsx` "AC-6"; `ui-acceptance.test.tsx` `READ_KEEP_MS`; query cutoff: source check | automated (app side), pass |
| AC-7 pending approval in Inbox, counts until decided, leaves when decided | `ui-inbox.test.tsx` "AC-7"; `ui-acceptance.test.tsx` AC-18 case | automated, pass |
| AC-8 mail row shows sender and subject only | `ui-inbox.test.tsx` "AC-8" | automated, pass |
| AC-9 quiet empty state in both languages | `ui-inbox.test.tsx` "AC-9" | automated, pass |
| AC-10 no Dismiss; pre-job dismissed cards hidden | `ui-inbox.test.tsx` "AC-10"; `step5-proactive.test.tsx` | automated, pass |
| AC-11 mark-read on own card only, once; no other column, insert or delete | `rls-inbox.test.ts` (migration 0009 run in PGlite, 6 tests); adapter call: source check | automated (database), pass |
| AC-12 Today shows only the five things | `ui-today.test.tsx` "AC-12" | automated, pass |
| AC-13 no connection notes, email card, card list, test cards, approve buttons, test-push results | `ui-today.test.tsx` "AC-13"; `step3-google-today`, `step4-yahoo-todoist-today` | automated, pass |
| AC-14 Now card picks the first of prayer/event, prayer wins a tie | `ui-today.test.tsx` "AC-14"; `nowItems` in `live.ts` | automated, pass |
| AC-15 countdown ticks ≥ once a minute, moves on at zero without reload | `ui-today.test.tsx` "AC-15" (fake timers) | automated, pass |
| AC-16 + Q3 plan: ≤ 5 events (all-day first) and ≤ 3 tasks with "+N more"; quiet empty line | `ui-today.test.tsx` "AC-16 (with Q3)" | automated, pass |
| AC-17 Ahmad's one message, in order approval → unread reminder → today's brief → nothing | `ui-today.test.tsx` "AC-17" | automated, pass |
| AC-18 tapping it opens the Inbox at that item | `ui-today.test.tsx` "AC-18"; `ui-acceptance.test.tsx` "AC-18" (focus, scroll, args, Approve/Reject, nothing marked read) | automated, pass |
| AC-19 connection notes in Settings with the same states | `ui-today.test.tsx` "AC-19"; `step3`/`step4` today tests | automated, pass |
| AC-20 Chat opens at the latest message | `ui-chat-scroll.test.tsx` "AC-20" | automated, pass |
| AC-21 at the bottom, any new item is scrolled into view | `ui-chat-scroll.test.tsx` "AC-21" | automated, pass |
| AC-22 scrolled up, Ahmad's item does not move the list; jump button shows | `ui-chat-scroll.test.tsx` "AC-22" | automated, pass |
| AC-23 jump button scrolls, hides, resumes auto-scroll | `ui-chat-scroll.test.tsx` "AC-23" | automated, pass |
| AC-24 scrolled up, sending scrolls to the bottom | `ui-chat-scroll.test.tsx` "AC-24" | automated, pass |
| AC-25 scroll width equals viewport at 360 and 390, both languages | **needs a browser** — jsdom has no layout. `ui-overflow.test.tsx` gives the structural guards only | not verified here |
| AC-26 200-character word and long URL wrap or are cut | `ui-overflow.test.tsx` (every `data-slot` on 5 pages × 2 languages × 2 widths); `ui-acceptance.test.tsx` "AC-26" (text with no slot, including approval argument names) | automated (structure), pass; the pixel result needs a browser |
| AC-27 no fixed/min width above 360 px; inputs ≥ 16 px | `ui-overflow.test.tsx` "structural guards at 360/390" | automated, pass |
| AC-28 Arabic mirrored (bell, badge, unread mark, jump button); logical properties only | `ui-overflow.test.tsx` "AC-28" ×2 | automated (structure), pass; mirroring on screen needs a browser |
| AC-29 both themes, gold kept, only the four self-hosted fonts, no outside host | `ui-acceptance.test.tsx` "AC-29" (4 tests: token parity, no literal colour, font stacks, `@fontsource` imports + CSP) | automated, pass |
| AC-30 screenshots at 390 px (Today, Inbox, Chat after; Today, Chat before) and Khalid's yes | **not automatable, and not done**: there is no screenshots folder in the repo | outstanding, blocks merge per the PRD |
| AC-31 every time 12-hour with AM/PM or ص/م; approval binds to the exact arguments | `ui-acceptance.test.tsx` "AC-31" (every time node and `aria-label` on Today and the Inbox, both languages, both halves of the day); `approval-sec13.test.tsx` and `ui-inbox.test.tsx` for the binding | automated, pass |
| AC-32 screen-reader names, 44×44 targets, keyboard reach | `ui-acceptance.test.tsx` "AC-32" (CSS rules + focus order over 6 targets); `ui-inbox.test.tsx` "AC-32"; `ui-chat-scroll.test.tsx` jump button | automated (names, roles, order, CSS rules), pass; **a real screen reader was not run** and the 44 px is read from the rule, not measured |
| AC-33 reduce motion: no animation on scroll or inbox expansion | `ui-acceptance.test.tsx` "AC-33" ×2; `ui-chat-scroll.test.tsx` "AC-33" | automated, pass |

Every AC except AC-25 and AC-30 has at least one automated test. No AC was found that an automated
test could cover and none did, other than the server-side seam described in section 2, which is
blocked by the `server-only` resolution limit and is covered by source checks in the meantime.

---

## 4. Mutation check (can the guards fail?)

Each mutation was applied to one source file alone, the relevant test file was run, and the source
was then restored and its SHA-256 compared with the original. Ten mutations, ten caught.

| # | Mutation | File | Test file run | Caught? |
| --- | --- | --- | --- | --- |
| M1 | `.wrap` loses `overflow-wrap: anywhere` | `src/app/globals.css` | `ui-overflow.test.tsx` | yes — 1 failed / 47 passed |
| M2 | input font set to 0.875rem (under 16 px) | `src/app/globals.css` | `ui-overflow.test.tsx` | yes — 1 failed / 47 passed |
| M3 | `min-width: 400px` added to the card surface | `src/app/globals.css` | `ui-overflow.test.tsx` | yes — 2 failed / 46 passed |
| M4 | the card-title user-text slot loses its `wrap` class | `src/app/(app)/inbox/InboxView.tsx` | `ui-overflow.test.tsx` | yes — 4 failed / 44 passed |
| M5 | chat scroll helper always auto-scrolls (`onNewItem` → `"scroll"`) | `src/core/chat-scroll.ts` | `ui-chat-scroll.test.tsx` | yes — 2 failed / 13 passed |
| M6 | opening the list marks every card read (AC-4 broken) | `src/app/(app)/inbox/InboxView.tsx` | `ui-inbox.test.tsx` | yes — 5 failed / 27 passed |
| M7 | test cards counted in the badge (Q4 broken) | `src/core/inbox.ts` | `ui-inbox.test.tsx` | yes — 7 failed / 25 passed |
| M8 | the clock shows 24-hour times (AC-31 broken) | `src/core/clock.ts` | `ui-acceptance.test.tsx` | yes — 2 failed / 32 passed |
| M9 | a hard-coded `text-[#ff0000]` in a component (AC-29 broken) | `src/app/(app)/today/TodayView.tsx` | `ui-acceptance.test.tsx` | yes — 1 failed / 33 passed |
| M10 | `isAtBottom` always false (jump button never hides, AC-23) | `src/core/chat-scroll.ts` | `ui-chat-scroll.test.tsx` | yes — 3 failed / 12 passed |

No mutation went uncaught, so no extra test was needed for an undetected break. M8 and M9 exist to
prove that the two checks Agent 15 corrected in section 1.1 still fail when the app is wrong.

Proof that nothing was left mutated: after the run,

```
$ git status --short apps/snafi-web
?? tests/ui-acceptance.test.tsx
$ git diff --stat
(no output)
```

`git diff --stat` is empty — no tracked file differs. The only untracked files are this report and
`tests/ui-acceptance.test.tsx` (and Agent 16's `docs/SECURITY_REVIEW_ui_inbox.md`, which existed
before this run).

---

## 5. The four flagged risks

**(a) A server component passing a function prop to a client component.** Not found. `next build`
compiled and generated all 8 pages; such a prop would fail the build. In addition,
`ui-acceptance.test.tsx` "server to client" checks that no server component holds an inline arrow
or function in its JSX, that none passes the whole message dictionary (which does hold functions)
or `messages(...)`, that the dictionary groups actually passed (`t.settings`, `t.signIn`) hold no
function, and that the only functions passed to client components are the server actions imported
from `actions.ts` (`"use server"`). All pass.

**(b) `error.tsx`: does this Next pass `reset`, `retry` or both?** **Both.** Read from the
installed package, Next 16.4.5:

- `node_modules/next/dist/client/components/error-boundary.d.ts`:
  `export type ErrorInfo = { error: unknown; reset: () => void; retry: () => void; };`
- `node_modules/next/dist/client/components/error-boundary.js` renders
  `this.props.errorComponent` with `{ error: thrownValue, reset: this.reset, retry: this.retry }`.
- The two differ: `reset` only clears the boundary's state, so the same failed tree is rendered
  again; `retry` runs `startTransition(() => { router.refresh(); reset(); })`, which re-fetches the
  server data first.

So the code's use of `retry` (`src/app/(app)/inbox/error.tsx`, `src/app/(app)/today/error.tsx` →
`RouteError`) is correct for this version and is the better of the two for a data-load failure:
Agent 16's SEC-192 is answered. One caveat for the record: `retry` is the newer of the two names.
If Next is ever downgraded below the version that added it, `retry` would arrive as `undefined`,
the Try again button would silently do nothing (no crash), and TypeScript would not catch it
because the prop type is declared locally in `error.tsx`. The test
`"error.tsx takes retry, the name this installed Next passes"` reads the installed boundary and
fails if that name disappears.

**(c) CSS `:has()` in the chat layout — still needs a browser check.** Two rules in
`src/app/globals.css` rely on it:

```
.shell:has([data-screen="chat"]) { height: 100dvh; }
.shell-main:has([data-screen="chat"]) { display: flex; flex-direction: column; min-height: 0; padding-bottom: 0; }
```

jsdom does not apply the stylesheet, so no test in this suite exercises them; `css: false` in
`vitest.config.ts` means the CSS is never even parsed by the renderer. They are the mechanism that
gives Chat its own scrolling list (AC-20 to AC-24 are tested against the list element's scroll
metrics, not against this layout). If `:has()` is not supported, the chat list would not become a
flex column with its own scroll and the page itself would scroll instead, which would change the
behaviour those ACs describe. `:has()` is supported in Safari 15.4+, Chrome 105+ and Firefox 121+,
so Khalid's phones are very likely fine, **but this is an unverified claim from Agent 15 and must
be confirmed in a real browser at 360 and 390 px, in both languages**, together with AC-25.

**(d) `cards()` retries the old query on any error (Agent 16's SEC-172).**
`src/adapters/mailbox/supabase.ts:139-150`: the first query (with `read_at`) is run; `if
(!withRead.error) return ...`, otherwise the pre-migration query runs. The retry never looks at
the error's message or code, so this is confirmed as Agent 16 described it. Consequences, as
tests and reading show:

- Intended case (the live database has not had migration 0009 yet): the Inbox keeps working and
  every card shows as unread. This is what PRD risk 7 asks for.
- Unintended case: any other failure of the first query — a transient error, a permission error,
  a changed policy — also falls back. Cards read more than 7 days ago then reappear (contrary to
  AC-6) and read cards come back unread, so the bell's count can jump. Nothing is written
  wrongly and no data leaks (the fallback query is the same user's rows under the same RLS); the
  fault is cosmetic but visible, and it hides a real database problem instead of showing the
  Inbox's error state.
- Severity in Agent 15's view: Medium, and it is Khalid's call, not a blocker found by testing.
  A one-line narrowing (only fall back when the message names the missing `read_at` column, and
  drop the fallback once migration 0009 is live) would close it. The current behaviour is now
  pinned by a test, so a change will be noticed.

---

## 6. What was NOT tested

- **AC-25, the real measurement.** No browser was opened (this job allowed no dev server and no
  network). Page scroll width versus viewport width at 360 px and 390 px, for Sign-in, Today,
  Inbox, Chat and Settings, in Arabic and English — 20 measurements — is Ahmad's separate step.
  Everything in `ui-overflow.test.tsx` is structural: classes, inline styles and rules in
  `globals.css`, not pixels. A page can pass every structural guard and still overflow.
- **AC-30, the screenshots.** None exist in the repo. The PRD makes them a merge condition.
- **Real devices.** Khalid's iPhone and Android, the installed PWA, the on-screen keyboard, the
  16 px no-zoom-on-focus behaviour, pinch-zoom, safe areas and `100dvh` with the browser chrome:
  none of this can be reached from jsdom.
- **Screen readers.** VoiceOver and TalkBack were not run. AC-32 is covered as names, roles, order
  and CSS rules only; how the bell's "Inbox, 3 unread" is actually announced in Arabic and English
  is unverified.
- **Measured sizes and contrast.** The 44×44 targets are read from `globals.css`, never measured;
  jsdom reports every element as 0×0. The contrast ratios in `docs/UI.md` are Agent 17's
  calculations from hex values — Agent 15 did not recompute or measure them.
- **`:has()` and the rest of the stylesheet in a real engine** (see 5c), and the look itself: dark
  and light on every screen is checked as token parity in CSS, not by looking at a screen. "Calmer
  and more premium" is a matter of taste; the screenshots are the control.
- **The server half of the app**: the Supabase mailbox, the server actions, sessions and the
  Supabase RLS against the live database — not run, for the `server-only` reason in section 2. The
  migration itself is run for real in PGlite (`rls-inbox.test.ts`), against the repo's SQL, not
  against the live database (applying it there is explicitly out of scope and needs Khalid's yes).
- **Push, the worker, performance and battery.** Unchanged by this job and not re-measured; the
  countdown's "one tick a minute" is checked as timer behaviour with fake timers, not as battery
  use.
- **Security.** Agent 16 wrote `docs/SECURITY_REVIEW_ui_inbox.md`; Agent 15 did not review
  security and ran no scanner.

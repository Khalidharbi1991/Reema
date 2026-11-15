# PRD: Snafi UI job — Inbox, simpler Today, Chat scroll, mobile fit, calmer look

Status: draft for Khalid to confirm. Author: Agent 12. Date: Nov 15, 2026.
Source: Khalid's request as passed by Ahmad. The technology is not chosen here (Agent 13).

## 1. Problem and goal

Today is cluttered: every notification, test push, connection note and approval sits on it, and
cards must be dismissed by hand. Chat does not keep the latest message in view. Some pages are
wider than a phone screen.

Goal: a quiet Today with three things on it, a bell with an inbox for everything else, a Chat that
scrolls like WhatsApp, pages that always fit the phone, and a calmer, more premium look.

## 2. Users

Khalid only (single owner), mainly on an iPhone or Android phone with the installed app, in Arabic
(RTL) or English, dark or light theme.

## 3. Scope

In scope:
1. Notifications inbox behind a bell with an unread badge; read state; read items clear after 7 days.
2. Today simplified to: Now card, today's plan, Ahmad's single most important message.
3. Chat scroll behaviour and a "jump to latest" button.
4. Mobile fit on every page at 360 px and 390 px, both languages.
5. Look refresh, keeping dark/light, the gold accent and the four self-hosted fonts.
6. A database change in the repo: a read time on `cards` and a mark-read function the app may
   call for its own rows only.

Out of scope: applying the database change to the live database (separate step, Khalid's yes);
any push or deploy; new packages; new outside services; changes to the worker, to what cards the
worker writes, to push text, to the permission rules or to approval binding; Sign-in redesign
beyond mobile fit and the look.

## 4. User stories and acceptance criteria

"Unread" = a card with no read time, or an approval still pending. "Signed-in screens" = Today,
Inbox, Chat, Settings.

### Story 1 — Inbox: "I see notifications in one place, behind a bell."

- AC-1 Given any signed-in screen, when it loads, then a bell is in the top bar; given Sign-in,
  then no bell is shown.
- AC-2 Given N unread items, then the badge shows N for 1 to 9, "9+" for 10 or more, and no badge
  for 0.
- AC-3 Given cards and pending approvals exist, when Khalid taps the bell, then the Inbox opens
  listing pending approvals first, then cards newest first; each row shows its kind, title, time
  (12-hour with AM/PM or ص/م) and an unread mark if unread. Kinds listed: reminder, brief, mail,
  test.
- AC-4 Given an unread card, when Khalid only opens the Inbox list, then the card stays unread and
  the badge does not change.
- AC-5 Given an unread card, when Khalid taps it, then it expands to show its body, it is marked
  read, the badge drops by 1, and after a reload it is still read.
- AC-6 Given a card read more than 7 days ago, then it is not shown anywhere; given one read 6
  days 23 hours ago, then it is shown; given an unread card of any age, then it is shown.
- AC-7 Given a pending approval, then it is in the Inbox with the exact arguments and Approve and
  Reject, it counts in the badge until decided (opening it does not uncount it), and it is never
  cleared while pending. When it is approved or rejected, then it leaves the Inbox and the badge.
- AC-8 Given a mail alert in the Inbox, then it shows sender and subject only, expanded or not.
- AC-9 Given no items, then the Inbox shows a quiet empty state in the current language.
- AC-10 Given Today and the Inbox, then no Dismiss button exists on either; cards dismissed
  before this job (dismissed time set) are not shown.
- AC-11 (database) Given the signed-in user, when the app calls mark-read on its own card, then
  that card's read time is set once (a second call keeps the first time); when it calls mark-read
  on another user's card, then nothing changes; the app still cannot change any other column or
  insert or delete cards.

### Story 2 — Today: "I see only what matters now."

- AC-12 Given Today, then it shows only: the greeting line with the Gregorian and Hijri dates, the
  Now card, today's plan, Ahmad's message, and the orb button to Chat.
- AC-13 Given Today, then none of these appear: connection notes, the Important email card, the
  list of Ahmad's cards, any `test` card, approval cards with Approve/Reject, test-push results.
- AC-14 Given the next prayer and the next calendar event today, then the Now card shows whichever
  starts first (prayer wins a tie) with its name, its time (12-hour) and a countdown; with no
  calendar connected or no event left today, it shows the next prayer.
- AC-15 Given the Now card is open, then the countdown updates at least once a minute, and when it
  reaches zero the card moves to the next prayer or event without a reload.
- AC-16 Given today's plan, then it lists today's remaining events in time order (all-day first)
  and at most 3 top tasks, with a count of the remaining tasks ("+N more") when there are more;
  with no events or no tasks, it shows a short empty line, not an error.
- AC-17 Given Ahmad's message, then exactly one item or a quiet empty state is shown, chosen in
  this order: (1) pending approvals (the oldest, plus a count if more than one); (2) the newest
  unread reminder; (3) today's unread brief; (4) nothing. Mail and test cards are never chosen.
- AC-18 Given Ahmad's message shows an item, when Khalid taps it, then the Inbox opens with that
  item expanded (a card is thereby marked read; an approval shows its Approve and Reject there).
- AC-19 Given Settings, then the Google, Yahoo and Todoist connection notes (not connected,
  reconnect, error) are shown there with the same states they had on Today.

### Story 3 — Chat: "Chat stays at the latest message unless I am reading back."

- AC-20 Given a chat with more messages than fit, when Chat opens, then the latest message is
  fully in view at the bottom.
- AC-21 Given Khalid is at the bottom, when any new item arrives (his message, Ahmad's reply, the
  thinking placeholder, an approval card), then the view scrolls so it is in view.
- AC-22 Given Khalid has scrolled up, when a new item arrives from Ahmad, then the scroll position
  does not move and a "jump to latest" arrow button is shown.
- AC-23 Given the button is shown, when Khalid taps it, then the view scrolls to the bottom, the
  button hides, and auto-scroll resumes; the button is also hidden whenever he is at the bottom.
- AC-24 Given Khalid has scrolled up, when he sends a message, then the view scrolls to the bottom.

### Story 4 — Mobile fit: "Nothing is wider than my screen."

- AC-25 Given each of Sign-in, Today, Inbox, Chat and Settings, at 360 px and at 390 px wide, in
  Arabic and in English, then the page's scroll width equals the viewport width (measured in a
  browser and reported per page, width and language).
- AC-26 Given a 200-character string with no spaces (and a long URL) as a card title, card body,
  chat message, event name, task name, or mail sender or subject, then it wraps or is cut with an
  ellipsis inside its container and AC-25 still holds.
- AC-27 Given the automated tests, then structural guards pass at 360 and 390: no element on these
  pages has a fixed or minimum width above 360 px, and text inputs are at least 16 px so the
  phone does not zoom on focus.
- AC-28 Given Arabic, then the layout is mirrored (bell, badge, unread marks and the jump button
  on the RTL side) and AC-25 holds.

### Story 5 — Look: "Calmer and more premium, still Snafi."

- AC-29 Given the refreshed screens, then dark and light themes both work on every screen, the
  gold accent is kept, and only Inter, IBM Plex Sans Arabic, Amiri and Cormorant Garamond are
  used, self-hosted, with no request to any outside host.
- AC-30 Given the job is ready for merge, then screenshots at 390 px exist for Today, Inbox and
  Chat (after), and for Today and Chat (before), made with sample data only, and the merge waits
  for Khalid's yes on them.

### Unchanged behaviour and accessibility

- AC-31 Given any time shown on the changed screens, then it is 12-hour with AM/PM or ص/م; given
  an approval approved from the Inbox, then it binds to the exact arguments shown, as before.
- AC-32 Given a screen reader, then the bell announces the unread count ("Inbox, 3 unread" /
  Arabic equivalent) and the jump button has a label, in both languages; the bell, inbox rows,
  Approve, Reject and the jump button are at least 44 by 44 px and reachable by keyboard.
- AC-33 Given "reduce motion" is on, then scrolling to the latest message and inbox expansion
  happen without animation.

## 5. Non-functional needs

- Accessibility: WCAG 2.2 AA (contrast in both themes, focus visible, AC-32, AC-33). Pinch-zoom
  is not disabled.
- Performance: the bell count and Inbox use the data the app already reads; no visible delay
  added to Today. Countdown must not drain the battery (one tick a minute is enough).
- Offline: unchanged; the PC offline banner stays.
- Data kept: one new value, a read time per card. Read cards older than 7 days are hidden by the
  app; deleting rows is not part of this job.
- Privacy: mail alerts show sender and subject only; push lock-screen text unchanged; screenshots
  use sample data and stay on this computer.

## 6. Constraints

Existing Snafi web app; bilingual with RTL; no network calls beyond the existing database; no new
outside service; no new packages; no secrets in the repo; no push, no deploy; the live database is
not touched; `test` cards never appear on Today; every Snafi change is reviewed by Agent 16 before
merge.

## 7. Risks

- The app change and the database change must go live together; an app that calls mark-read
  before the live database has it must fail quietly (item stays unread), not break the Inbox.
- Moving approvals off Today adds a tap; a missed badge could delay an approval. Mitigated by
  AC-17 (approval is always Ahmad's message).
- Structural overflow tests can pass while a real phone still overflows; AC-25 browser
  measurement is the real check, and real iPhone and Android devices are checked only by Khalid.
- A look refresh is a matter of taste; the screenshots (AC-30) are the control.

## 8. Assumptions (used above; Khalid can change any)

- A1 "Opened" means tapping an item to expand it; opening the list marks nothing (AC-4, AC-5).
- A2 Pending approvals always count as unread and never auto-clear; once decided they leave the
  Inbox and remain in Chat and the action log (AC-7).
- A3 Ahmad's message order: approval, newest unread reminder, today's unread brief, empty (AC-17).
- A4 Now card: whichever comes first, prayer or event; prayer wins a tie (AC-14).
- A5 Plan: all of today's remaining events, at most 3 tasks plus a count (AC-16).
- A6 Badge shows "9+" from 10 (AC-2).
- A7 Bell on every signed-in screen (AC-1).
- A8 Test-push cards appear in the Inbox and count as unread like any card.
- A9 The greeting and the Gregorian and Hijri dates stay on Today as one line; the prayer ring is
  replaced by the Now card; the orb button stays (AC-12).
- A10 "No zooming" means the page never zooms by itself or needs zooming; pinch-zoom stays
  allowed for accessibility.
- A11 Cards dismissed before this job stay hidden; the old dismiss function is no longer called.
- A12 On Today, an approval is shown as a message that opens the Inbox; Approve and Reject are
  only in the Inbox and in Chat.

## 9. Open questions

- Q1 Should Approve and Reject also be on Today's message, to save a tap (changes A12)?
- Q2 Should a decided approval stay in the Inbox as a read item for 7 days (changes A2)?
- Q3 Should the plan cap events as well (for example 5 plus a count) on a busy day (A5)?
- Q4 Should test-push cards be kept out of the badge count (A8)?
- Q5 Is the Inbox a full page or a panel over the current screen? Left to Agents 13 and 17 unless
  Khalid prefers one.

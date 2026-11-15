# Snafi UI: Inbox, simpler Today, Chat scroll, mobile fit, calmer look

Author: Agent 17 (UI design). Date: Nov 15, 2026. Source: `apps/snafi-web/docs/PRD_ui_inbox.md`
(confirmed, section 9 answers applied) and the Design section of `docs/snafi/PRD.md`.

Status of this document: design only. Nothing here was rendered, run or tested. Every contrast
ratio is calculated from the hex values with the WCAG relative-luminance formula, not measured in a
browser. Widths in wireframes are estimates from font metrics; Agent 15's browser measurements
(AC-25) and Khalid's screenshots (AC-30) are the real check. Where this document and the PRD
disagree, the PRD wins.

Words used: "inline-start" is left in English and right in Arabic; "inline-end" is the opposite.
"Gutter" is the page's side padding.

---

## 0. Ahmad's rulings on Agent 17's open points (these override the text below)

Khalid has not answered these; Ahmad chose the option closest to Khalid's own words and reports
each one to him with the screenshots. Khalid can change any of them.

1. **Order on Today follows Khalid's list:** greeting, Now card, today's plan, Ahmad's message.
   Wherever this document puts Ahmad's message above the plan, use Khalid's order instead.
2. **Now card at zero:** moves on at once, as AC-15 says. No "now" hold.
3. **Plan when a source is not connected:** the one neutral line ("Calendar isn't available right
   now." / "Tasks aren't available right now.") is kept, with no fix text; the fix lives in
   Settings. The menu's Settings item carries the small attention mark when a connection is broken.
4. **Test rows in the Inbox** keep the unread mark and never count in the badge.
5. **The disabled attach button is removed** until attachments exist. The Plex Arabic 600 import
   is allowed (same installed package, self-hosted).
6. **Plan events, data gap:** the worker's Today feed carries one `nextEvent`, not a list. Build the
   plan to render a list of 0 to 5 events plus "+N more", fed by an adapter that today yields zero
   or one event. The worker is not changed in this job. Prayer instants for the Now card come from
   the existing prayer adapter; the event instant from `nextEvent.start`.

## 1. Design thesis

Snafi already has the right identity: charcoal or ivory, a little gold, two serif heading faces
and two sans body faces. It is loud in small ways: gold on every heading and hairline, every card
animating in, six equal cards on Today, text at 10 to 14 px, five kinds of border.

"Calmer and more premium" here means four things:

1. **Fewer boxes.** Today has exactly one card (Now). Everything else is type on the page
   background, grouped by space and one hairline. Settings sections and Inbox rows are flat.
2. **Gold means something.** Gold is kept for the wordmark, the orb, the Now card's time, the
   unread badge and mark, "waiting for your approval", and the one primary button on a screen.
   Headings and hairlines become neutral.
3. **Larger, steadier type.** Six type roles on a fixed rem scale, nothing under 13 px, body and
   every input at 16 px.
4. **Motion only when Khalid acts or the time changes.** No entrance animation on load.

**The one place boldness is spent:** the Now card. Its name line ("Maghrib", or the event title)
is the largest type in the app (32 px heading serif), with the time beside the countdown in gold.
Nothing else on any screen competes with it.

**Removed:** see section 9.

**Fixed limits (not negotiable in this job):** dark and light themes; the gold accent; only Inter,
IBM Plex Sans Arabic, Amiri and Cormorant Garamond, self-hosted; no new packages; no external
assets; no icon library. Icons are inline SVG authored in this document (section 4.9). No emoji
and no Unicode glyph is used as an icon; today's "←", "＋", "✓", "·" and "—" are all replaced.

---

## 2. Tokens

All tokens live in `src/app/globals.css`. Existing names are kept so the change is small.

### 2.1 Colour

| Token | Dark: old → new | Light: old → new | Role |
| --- | --- | --- | --- |
| `--bg` | `#0e0e10` stays | `#f7f3ec` stays | Page background |
| `--card` | `#17171a` stays | `#ffffff` stays | Now card, approval surface, composer, inputs, Ahmad's chat bubble |
| `--raised` | new `#1f1f23` | new `#ffffff` | Menu popover, jump button |
| `--press` | new `#1f1f23` | new `#efe9df` | Hover and pressed background of rows and quiet buttons |
| `--wash` | new `#2a251e` | new `#eee5d6` | Khalid's chat bubble, selected option. Replaces `bg-gold/15` (same look over `--bg`, now a fixed colour) |
| `--text` | `#f2eee6` stays | `#1b2236` stays | Primary text |
| `--muted` | `rgba(242,238,230,0.62)` → `#a09c94` | `rgba(27,34,54,0.64)` → `#5c6170` | Secondary text, placeholders. Solid now, so contrast no longer depends on what is behind it |
| `--faint` | `rgba(242,238,230,0.08)` stays | `rgba(27,34,54,0.06)` stays | Skeleton fill |
| `--card-edge` | `rgba(201,169,110,0.14)` → `rgba(242,238,230,0.10)` | `rgba(122,92,36,0.14)` → `rgba(27,34,54,0.10)` | Hairlines and card edges. Neutral now, not gold. Decorative only |
| `--edge-strong` | new `#76726b` | new `#847f72` | Borders that identify a control: inputs, selects, outline buttons, unselected options (3:1) |
| `--gold` | `#c9a96e` stays | `#b8935a` stays | Fill under dark text (primary button) and the orb only |
| `--gold-ink` | `#c9a96e` stays | `#7a5c24` stays | Every gold that carries meaning: gold text, unread mark, selected border, attention notes |
| `--on-gold` | new `#0e0e10` (was hard-coded `#0E0E10`) | new `#0e0e10` | Text on `--gold` |
| `--badge-bg` / `--badge-fg` | new `#c9a96e` / `#0e0e10` | new `#7a5c24` / `#ffffff` | Bell badge |
| `--focus` | `var(--gold)` → `#c9a96e` | `var(--gold)` `#b8935a` → `#7a5c24` | Focus ring. Light changes because `#b8935a` on ivory is 2.58:1, under the 3:1 needed |
| `--danger` | new `#e9a79b` | new `#9a2b1e` | Error text and invalid borders. Today errors are gold, the same colour as "selected" |
| `--orb-core` | `#e7cf9c` stays | `#d8b878` stays | Orb highlight |
| `--tone-*` | stay | stay | Time-of-day wash (PRD Design: kept as is) |

Rules:

- There is no success green. Success is said in words ("Saved.") in `--muted`. Three state
  colours only: gold-ink (attention, selected, unread), danger (error), muted (done, neutral).
- A state is never shown by colour alone. Each has a second cue (table in 7.6).
- `--gold` (not `--gold-ink`) never carries meaning in the light theme: it is under 3:1 on ivory
  and white. The menu icon's short third line changes from `bg-gold` to `bg-gold-ink`.
- No translucent text colours and no `…/40`, `…/60` opacity variants of gold for borders. Use the
  tokens above.
- Add to `@theme inline`: `--color-raised`, `--color-press`, `--color-wash`,
  `--color-edge-strong`, `--color-on-gold`, `--color-danger`, `--color-focus`,
  `--color-badge-bg`, `--color-badge-fg`.

### 2.2 Contrast (calculated, not measured)

Relative luminance used: dark `--bg` 0.0044, `--card` 0.0087, `--raised` 0.0139, `--wash` 0.0191,
`--text` 0.8574, `--muted` 0.3339, `--gold` 0.4192, `--edge-strong` 0.1695, `--danger` 0.4733;
light `--bg` 0.8993, `--card` 1.0, `--press` 0.8196, `--wash` 0.7907, `--text` 0.0164,
`--muted` 0.1199, `--gold-ink` 0.1192, `--gold` 0.3180, `--edge-strong` 0.2130, `--danger` 0.0869.

| Pair | Dark | Light | Needs |
| --- | --- | --- | --- |
| `--text` on `--bg` | 16.7 | 14.3 | 4.5 |
| `--text` on `--card` | 15.5 | 15.8 | 4.5 |
| `--text` on `--raised` | 14.2 | 15.8 | 4.5 |
| `--text` on `--wash` (Khalid's bubble) | 13.1 | 12.7 | 4.5 |
| `--muted` on `--bg` | 7.1 | 5.6 | 4.5 |
| `--muted` on `--card` (also placeholders) | 6.5 | 6.2 | 4.5 |
| `--muted` on `--raised` / `--press` | 6.0 | 5.1 | 4.5 |
| `--muted` on `--wash` | 5.6 | 5.0 | 4.5 |
| `--gold-ink` on `--bg` | 8.6 | 5.6 | 4.5 |
| `--gold-ink` on `--card` | 8.0 | 6.2 | 4.5 |
| `--gold-ink` on `--wash` (selected option) | 6.8 | 5.0 | 4.5 |
| `--on-gold` on `--gold` (primary button) | 8.6 | 6.8 | 4.5 |
| `--badge-fg` on `--badge-bg` | 8.6 | 6.2 | 4.5 |
| `--badge-bg` against `--bg` (badge is seen) | 8.6 | 5.6 | 3 |
| `--danger` on `--bg` / `--card` | 9.6 / 8.9 | 6.9 / 7.7 | 4.5 |
| `--focus` ring against `--bg` / `--card` | 8.6 / 8.0 | 5.6 / 6.2 | 3 |
| `--edge-strong` against `--bg` / `--card` | 4.0 / 3.7 | 3.6 / 4.0 | 3 |
| `--edge-strong` against `--raised` / `--wash` | 3.4 / n.a. | 4.0 / 3.2 | 3 |
| `--gold` against `--bg` (decoration only) | 8.6 | 2.6 | none: never carries meaning in light |

Light theme, primary button: the gold fill against a white card is 2.85:1. The control is
identified by its 6.8:1 label, which is what WCAG 1.4.11 asks for; no extra border is added.

### 2.3 Spacing

One scale, 4 px base, Tailwind's own steps only: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64
(`1 2 3 4 5 6 8 10 12 16`). No arbitrary spacing values except those named in this document.

| Name | Value | Use |
| --- | --- | --- |
| `--gutter` | 16 px under 390 px wide, 20 px from 390 px (`@media (min-width: 390px)`) | Page side padding, top bar included |
| Tight | 4 px | Two lines of one item |
| Row | 12 px block padding | List rows (plan, inbox) |
| Group | 16 px | Between items of one group; card padding at 360 |
| Card | 20 px | Card padding at 390 and up |
| Section | 32 px | Above each `h2`; 12 px below it (more above a heading than below) |
| Screen top | 16 px | Between the top bar and the first content |

### 2.4 Radius

| Token | Value | Use |
| --- | --- | --- |
| `--radius-surface` | 16 px (stays, `rounded-2xl`) | Now card, approval surface, composer, menu popover, chat bubbles |
| `--radius-control` | 12 px (stays, `rounded-xl`) | Buttons, inputs, selects, notes, banners |
| `--radius-small` | 8 px | Skeleton blocks |
| round | 999 px | Icon buttons, orb, badge, jump button, unread mark |

Chat bubbles: 16 px, with the corner nearest the speaker's edge at 6 px (inline-end bottom for
Khalid, inline-start bottom for Ahmad; today it is the top corner, `rounded-se-md` /
`rounded-ss-md`, change to `rounded-ee-md` / `rounded-es-md`).

### 2.5 Shadow and elevation

Dark shows height by surface lightness (`--bg` → `--card` → `--raised`); light shows it by a soft
navy-tinted shadow. Shadows always have an offset and a blur.

| Token | Dark | Light | Use |
| --- | --- | --- | --- |
| `--shadow-card` | `none` | `0 1px 2px rgba(27,34,54,0.05)` | Now card, approval surface, composer |
| `--shadow-float` | `0 8px 24px -8px rgba(0,0,0,0.6)` | `0 12px 32px -12px rgba(27,34,54,0.22), 0 2px 6px rgba(27,34,54,0.06)` | Menu popover, jump button |

Removed: `shadow-[0_1px_0_0_var(--faint)]` on Card, `shadow-2xl` on the menu.

Layer order (z-index): content 0; Today's bottom scrim and orb 30; jump button 30; menu popover
50; skip link 60.

### 2.6 Type

Fixed rem scale; no fluid `clamp()` type (this is an app, sizes stay predictable). Fonts by
language are unchanged: English uses Cormorant Garamond (heading) and Inter (body); Arabic uses
Amiri (heading) and IBM Plex Sans Arabic (body).

| Role | Size | Line height EN / AR | English | Arabic | Used for |
| --- | --- | --- | --- | --- | --- |
| `display` | 2rem (32 px) | 1.15 / 1.45 | Cormorant 500 | Amiri 400 | Now card name only |
| `title` | 1.625rem (26 px) | 1.2 / 1.5 | Cormorant 500 | Amiri 400 | `h1` on Today (greeting) and Sign-in |
| `heading` | 1.25rem (20 px) | 1.3 / 1.5 | Cormorant 600 | Amiri 700 | `h2`; the `h1` in the top bar on Inbox, Chat, Settings |
| `wordmark` | 1.5rem (24 px); 2rem on Sign-in | 1 | Cormorant 500, tracking 0.08em | Amiri 400, tracking 0 | "Snafi" / "سنافي", `--gold-ink` |
| `body` | 1rem (16 px) | 1.5 / 1.7 | Inter 400 | Plex Arabic 400 | Row titles, chat messages, inputs, notes |
| `body-strong` | 1rem | same | Inter 600 | Plex Arabic 600 | Unread titles, selected options, service names |
| `button` | 1rem | 1.25 | Inter 500 | Plex Arabic 500 | Button labels |
| `small` | 0.875rem (14 px) | 1.45 / 1.65 | Inter 400 | Plex Arabic 400 | Kind labels, dates, help text, countdown companions |
| `caption` | 0.8125rem (13 px) | 1.4 / 1.6 | Inter 400 | Plex Arabic 400 | Timestamps, expiry line, footers. The floor: nothing smaller |
| `time` | 1.25rem (20 px) | 1.2 | Inter 500, tabular | Plex Arabic 500, tabular | Now card time only, `--gold-ink` |

Rules:

- Plex Arabic 600 needs one more import in `src/app/layout.tsx`:
  `@fontsource/ibm-plex-sans-arabic/600.css`. It is a file of the package already installed, not a
  new package, and is self-hosted like the rest. If Agent 13 refuses it, Arabic `body-strong`
  falls back to 500.
- Headings: `letter-spacing: 0.01em` in English (stays), `0` in Arabic. **Letter-spacing is never
  applied to Arabic text**: it breaks the joined letters. Today the wordmark's `tracking-[0.08em]`
  (TopBar) and `tracking-[0.1em]` (Sign-in) also apply to "سنافي"; make them English-only.
- No uppercase anywhere. Remove `uppercase tracking-[…]` from the menu's "Appearance" and
  "Language" labels, from "Exactly what will run" and from the Sample badge. They become `small`,
  `--muted`, sentence case.
- No monospace. `font-mono` on the approval's tool name falls back to a system font that is not one
  of the four; remove it. The tool name is `body` in the body font.
- Times, countdowns and the badge use `font-variant-numeric: tabular-nums`. Digits are Western in
  both languages (Khalid's rule in `src/core/clock.ts`).
- `h1`, `h2`: `text-wrap: balance`. Paragraphs: `text-wrap: pretty`. Both are ignored safely by
  older browsers.
- Put the base rules (`h1, h2, h3`, `:focus-visible`) inside `@layer base`. Today they are
  unlayered, and in Tailwind 4 an unlayered rule beats every utility class, so `font-semibold` on a
  heading or `rounded-full` on a focused button is likely overridden (Agent 14 to confirm in the
  browser).

### 2.7 Motion

| Token | Value | Use |
| --- | --- | --- |
| `--dur-fast` | 120 ms | Press, hover, the inbox body fading in |
| `--dur-base` | 180 ms | Chevron turn, jump button in and out, screen fade, theme change |
| `--dur-slow` | 320 ms | Now card content change at zero |
| `--ease-out` | `cubic-bezier(0.25, 1, 0.5, 1)` | Everything. No bounce, no elastic |

- Screen change: `.screen-in` becomes opacity only (0 → 1, `--dur-base`). The sideways slide is
  removed: `translateX(16px)` on `<main>` makes the page wider than the screen while it runs.
- Theme change: `body` colour transition 600 ms → 200 ms.
- Orb, idle on Today and Sign-in: scale 1 → 1.03 → 1 over 6 s, and a soft glow that only changes
  opacity (0.5 → 0.8). The glow is a blurred `::after`, so only `transform` and `opacity` animate
  (today `box-shadow` animates forever, which repaints every frame). In the Chat bar the orb is
  still when idle and pulses only while Ahmad is thinking.
- Skeleton: flat `--faint` block, opacity 0.6 ↔ 1 over 1.6 s. The gold shimmer is removed.
- Nothing animates on load: no `rise-in`, no stagger.

Reduced motion (`prefers-reduced-motion: reduce`):

- The existing global rule (durations to 0.01 ms) stays.
- Orb and skeleton are still. The Now card changes content with no fade.
- Inbox rows open and close with no fade; the chevron flips with no turn (AC-33).
- Every scroll done by code (`scrollTo`, `scrollIntoView`) passes `behavior: "auto"`. CSS cannot do
  this: the code must read `matchMedia("(prefers-reduced-motion: reduce)")` (AC-33).

### 2.8 Browser surfaces

- `::selection`: background `--wash`, colour `--text`.
- `caret-color: var(--gold-ink)`; `accent-color: var(--gold-ink)` on `:root`.
- Links in running text: `text-decoration-thickness: 1px; text-underline-offset: 0.2em`.
- Chat list scrollbar: `scrollbar-width: thin; scrollbar-color: var(--edge-strong) transparent`.
- Focus ring, global: `outline: 2px solid var(--focus); outline-offset: 2px;`. Remove
  `border-radius: 6px` from the rule: it reshapes whatever is focused. Inside rows and the list
  (where an outer ring would be clipped) use `outline-offset: -2px`.

---

## 3. Screens

Navigation:

```
Sign-in ──▶ Today ──(orb)──▶ Chat
              │  ▲              │
     (bell, or Ahmad's message) │ (back arrow)
              ▼  │              ▼
            Inbox ◀──(bell)── any signed-in screen
              ▲
   Menu ▶ Settings (back arrow ▶ Today)
```

Back arrows always go to Today. The bell always goes to `/inbox`. The menu is on every screen.

Shared frame for signed-in screens: one column, `max-width: 42rem`, centred, `min-height: 100dvh`.
Order from the top: top bar, then the PC-offline or preview banner (if any), then the screen.
The banner moves **below** the top bar: today it is the first thing on the page with no safe-area
padding, so on an installed iPhone (`black-translucent` status bar) it sits under the clock.

### 3.1 Top bar

Purpose: say where Khalid is, and hold the bell and the menu.

```
390 px, English, Today                      390 px, Arabic, Today
┌──────────────────────────────────────┐    ┌──────────────────────────────────────┐
│ Snafi                     ([bell]3)  (≡) │    │ (≡)  (3[bell])                     سنافي │
└──────────────────────────────────────┘    └──────────────────────────────────────┘

390 px, English, Inbox / Settings           390 px, English, Chat
┌──────────────────────────────────────┐    ┌──────────────────────────────────────┐
│ (←) Inbox                 ([bell]3)  (≡) │    │ (←) (o) Ahmad             ([bell]3)  (≡) │
└──────────────────────────────────────┘    │         Ahmad is thinking…           │
                                            └──────────────────────────────────────┘
```

(The bell and arrows above stand for the SVG icons in 4.9; no glyph ships.)

- Height 56 px plus `padding-block-start: max(env(safe-area-inset-top), 8px)`. Side padding is the
  gutter, and at least the side safe-area insets (section 5, rule 6). Not sticky on Today, Inbox
  and Settings; on Chat it never scrolls because only the message list scrolls.
- Inline-start: on Today the wordmark (`wordmark` role, not a link, not a heading). On Inbox and
  Settings: back button, then the screen name as the page's `h1` (`heading` role, one line,
  ellipsis). On Chat: back button, 32 px orb (decorative, `aria-hidden`), then `h1` "Ahmad"
  (`heading`) and, only while waiting for a reply, "Ahmad is thinking…" under it (`caption`,
  `--muted`). The fixed line "Your executive assistant" is removed.
- Inline-end: bell, then menu, 4 px apart. The menu stays outermost (PRD: three lines at the top
  inline-end). Sign-in has the menu only: no bell, no wordmark.
- Icon buttons are 44 by 44 px. Pull the outer ones outward so the drawing, not the empty tap
  area, lines up with the gutter: menu `margin-inline-end: -12px`, back `margin-inline-start:
  -10px` (to be checked by eye in the browser).
- The start group is `min-width: 0; flex: 1`; the end group is `flex: none`.
- Menu popover: content unchanged. Style: `--raised`, 1 px `--card-edge`, `--radius-surface`,
  `--shadow-float`, `inline-size: min(18rem, 100vw - 2 * var(--gutter))`, its inline-end edge on
  the gutter. No entrance animation. Labels in sentence case.
- Implementation note (Agent 13 decides how): the bar's start content depends on the screen. Either
  each screen renders the bar with its own start content, or the bar reads the path.

RTL: everything mirrors. Wordmark, back button and title on the right; menu outermost on the left,
bell beside it. The badge sits on the bell's top inline-end corner (top left in Arabic). The back
arrow points right.

360 px: gutter 16 px. On Chat the name and status line shrink first (ellipsis); nothing else
changes.

States: the bar has no empty or loading state of its own. If the unread count cannot be read, the
bell shows no badge and its label is the plain "Inbox" (4.1). Menu states are unchanged.

### 3.2 Today (`/today`)

Purpose: what is next, today's plan, and the one thing Ahmad needs Khalid to see.

```
390 px, English
┌──────────────────────────────────────┐
│ Snafi                     ([bell]3)  (≡) │  top bar
│                                      │
│ Good evening, Khalid                 │  h1, title
│ Sunday 15 November │ 25 Jumada I     │  small, muted
│                                      │
│ ┌──────────────────────────────────┐ │  Now card (the only card)
│ │ Maghrib                          │ │  display
│ │ 5:38 PM               in 42 min  │ │  time, gold-ink │ body
│ └──────────────────────────────────┘ │
│                                      │
│ From Ahmad                           │  h2, heading
│ Send the reply to Faisal?         ›  │  body, whole block is one link
│ Waiting for your approval, and 2     │  small, gold-ink
│ more                                 │
│                                      │
│ Today's plan                         │  h2
│ All day    Rent due                  │
│ 4:00 PM    Design review with Faisal │
│ 8:30 PM    Dinner                    │
│ ──────────────────────────────────── │  one hairline, events │ tasks
│ ○          Send signed contract      │
│                                Today │
│ ○          Call the contractor       │
│                              Overdue │
│ ○          Book the car service      │
│            +4 more                   │
│                                      │
│                 (orb)                │  fixed, bottom centre
└──────────────────────────────────────┘
```

Order: greeting, Now, From Ahmad, Today's plan. Ahmad's message sits above the plan because it is
always two lines high, while the plan can be eleven rows; under the plan, a waiting approval would
fall below the first screen and behind the orb (PRD risk: a missed approval). AC-12 lists the
parts without fixing their order; see the question for Khalid in the hand-back.

Components:

- **Greeting line.** `h1` in `title`: greeting, comma, name. The name is the same colour as the
  rest (the gold name is removed). Under it one `small` `--muted` paragraph with both dates:
  Gregorian, a 1 px by 0.9em `--edge-strong` rule (a CSS box with 10 px inline margin,
  `aria-hidden`), then Hijri. Each date is its own `<span>`; a visually hidden comma follows the
  first for screen readers. The paragraph may wrap to two lines.
- **Sample note.** In preview mode with sample data, the existing `placeholderNote` stays as one
  `small` `--muted` line under the dates. Per-card "Sample" badges are removed.
- **Now card**: 4.2. **Ahmad's message**: 4.4. **Plan**: 4.3.
- **Orb.** 64 px link to `/chat`, `position: fixed`, centred, `inset-block-end:
  max(env(safe-area-inset-bottom), 20px)`. Its wrapper is `pointer-events: none` and the orb is
  `pointer-events: auto`: today the wrapper spans the whole width and swallows taps along the
  bottom. Behind it, a scrim 112 px high, `linear-gradient(to top, var(--bg) 40%, transparent)`,
  `pointer-events: none`, so rows scrolling under the orb fade out. The screen's bottom padding is
  `calc(7rem + env(safe-area-inset-bottom))`.
- One column at every width (the two-column grid at `sm` is removed).

Not on Today any more (AC-13): connection notes, Important email, the list of Ahmad's cards, any
`test` card, Approve and Reject, Dismiss, the prayer ring, the Next event and Top tasks cards.

RTL: text and the plan's time column start on the right; due text and the message's chevron are on
the left; the chevron points left. The orb stays centred.

360 px: gutter 16 px; Now card padding 16 px. If the time and the countdown do not fit on one line
(long Arabic countdown), the countdown wraps under the time. Long names wrap to a second line.

States:

- Loading (the route's loading file): skeleton blocks in the same places: a 60% wide `title` line
  and a 45% `small` line; a card-sized block (96 px high); two lines for the message; four rows for
  the plan. `aria-busy="true"` on `<main>` with visually hidden text `loading`.
- Empty: each part has its own line (4.2 to 4.4). The Now card is never empty: prayer times are
  computed on the device.
- Error (the route's error file): `body` text `today.loadFailed` and a secondary "Try again"
  button that reloads. The top bar, bell and menu still work.
- PC offline: the banner under the top bar, unchanged in wording. Style: 1 px `--gold-ink` border
  (was `gold/40`), `small` (was 12 px), `--gold-ink` text, `--radius-control`, with the attention
  icon (4.9) before the text.

### 3.3 Inbox (`/inbox`)

Purpose: everything Ahmad sent, and every approval that is waiting. A full page (Q5).

```
390 px, English
┌──────────────────────────────────────┐
│ (←) Inbox                 ([bell]3)  (≡) │
│                                      │
│ Waiting for your approval            │  h2 (only if there is one)
│ ┌──────────────────────────────────┐ │  approval: always open
│ │ Send this email to Faisal?       │ │  body
│ │ Asked 4:05 PM                    │ │  caption, muted
│ │ ──────────────────────────────── │ │
│ │ Exactly what will run            │ │  small, muted
│ │ Action    gmail_send             │ │
│ │ to        faisal@example.com     │ │
│ │ subject   Running late           │ │
│ │ body      I will be there by     │ │
│ │           4:30.                  │ │
│ │ ──────────────────────────────── │ │
│ │ [   Approve    ] [    Reject   ] │ │  primary │ secondary
│ │ Expires 15 Nov, 5:10 PM if not   │ │  caption, muted
│ │ decided                          │ │
│ └──────────────────────────────────┘ │
│                                      │
│ Notifications                        │  h2 (only if approvals are shown too)
│ ● Reminder                  4:10 PM  │  unread, closed
│   Call the contractor about       ⌄  │  body-strong
│   the tiles                          │
│ ──────────────────────────────────── │
│   Brief                     7:00 AM  │  read, open
│   Morning brief                   ⌃  │  body
│   3 events today. First: Design      │  body, the card's text
│   review at 4:00 PM. Top task:       │
│   Send signed contract.              │
│ ──────────────────────────────────── │
│ ● Mail                      3:52 PM  │  unread, closed
│   Faisal Al-Harbi                 ⌄  │  sender
│   Re: Tile samples                   │  subject, small, muted
│ ──────────────────────────────────── │
│   Test              14 Nov, 9:15 PM  │
│   Test notification               ⌄  │
│                                      │
│ Read items clear after 7 days.       │  caption, muted
└──────────────────────────────────────┘
```

Components: approval item (4.6), inbox row (4.5), the two group headings, the footer line.

- Order: pending approvals, oldest first; then cards, newest first (AC-3).
- Headings: "Waiting for your approval" appears only when an approval is pending. "Notifications"
  appears only when both groups are shown; with cards alone the list starts under the top bar.
- Rows are flat: no card around each row, 1 px `--card-edge` hairline between rows, none after the
  last. Only the approval item is a surface, because it holds buttons that act.
- No orb on this screen, no Dismiss anywhere (AC-10).
- Opening from Today (`/inbox?open=<id>`): that item is scrolled to 16 px under the top bar and
  receives focus; a card is opened and marked read; an approval is already open. An id not in the
  list is ignored. Remove the query from the address afterwards so a reload does not repeat it.
- The list refreshes itself as Today does. A refresh must keep which rows are open and must not
  move the scroll position.

RTL: unread mark and kind on the right, time and chevron on the left. Argument names stay
left-to-right (4.6).

360 px: gutter 16 px; approval padding 16 px; nothing else.

States:

- Empty (AC-9): no headings. 48 px under the top bar, start-aligned: `inbox.emptyTitle` in `body`,
  then `inbox.emptyBody` in `small` `--muted`. No picture, no button. No footer line.
- Loading: four skeleton rows (a 30% `small` line and a 70% `body` line each).
- Error, whole list: `inbox.loadFailed` in `body` and a secondary "Try again" button. If approvals
  loaded and cards did not, show the approvals and put the error under "Notifications".
- Mark-read failed (for example the live database does not have the function yet): silent. The
  unread mark and the badge count come back; the row stays open and readable. No message.
- Approve or Reject failed: `decideFailed` under the buttons in `--danger`, `role="alert"`; the
  buttons work again.

### 3.4 Chat (`/chat`)

Purpose: talk to Ahmad; the latest message is always in view unless Khalid is reading back.

```
390 px, English
┌──────────────────────────────────────┐
│ (←) (o) Ahmad             ([bell]3)  (≡) │  never scrolls
├──────────────────────────────────────┤
│ ┌─────────────────────────────┐      │  Ahmad: --card, 1px edge
│ │ Your 4 PM moved to 4:30.    │      │
│ └─────────────────────────────┘      │
│      ┌─────────────────────────────┐ │  Khalid: --wash
│      │ Tell Faisal I will be late. │ │
│      └─────────────────────────────┘ │
│ ┌──────────────────────────────────┐ │  approval: full width
│ │ Send this email to Faisal?       │ │
│ │ …                                │ │
│ │ [   Approve    ] [    Reject   ] │ │
│ └──────────────────────────────────┘ │
│ (Undo)                               │
│                                 (↓)  │  jump button, 12 px above composer
│ ┌──────────────────────────────────┐ │
│ │ Message Ahmad…          [ Send ] │ │  composer
│ └──────────────────────────────────┘ │
│     Couldn't send. Try again.        │  note line (reserved height)
└──────────────────────────────────────┘  + bottom safe area
```

Layout: the screen is a column exactly as tall as the visible viewport (`100dvh` minus nothing:
the top bar is the column's first child). Three parts: top bar (`flex: none`), message list
(`flex: 1; min-height: 0; overflow-y: auto; overscroll-behavior: contain`), composer
(`flex: none`). **The message list is the only thing that scrolls.** This replaces
`min-h-[calc(100dvh-6rem)]` and the sticky composer. `<main>`'s own bottom padding is not applied
on this screen (today the composer and `<main>` both add bottom safe-area padding). How the
on-screen keyboard behaves on a real iPhone and Android phone is Khalid's check (PRD risk).

Components:

- **Message list.** A `role="log"` wrapper (see 7.4) around the `<ol>`. 16 px between messages,
  16 px top and bottom padding.
- **Bubbles.** `body` type (16 px, was 14). `max-inline-size: min(85%, 34rem)`;
  `overflow-wrap: anywhere; white-space: pre-line; min-width: 0`. Ahmad: `--card`, 1 px
  `--card-edge`, at inline-start. Khalid: `--wash`, no border, at inline-end. Padding 12 px by
  16 px. Each keeps its own `lang` and `dir` (as today).
- **Approval in chat.** The same item as in the Inbox (4.6), full column width (was 85%). After a
  decision it stays in Chat with its status line (unchanged behaviour).
- **Undo.** Outline pill, `min-height: 44px` (was 36), `small`, `--gold-ink` text,
  1 px `--edge-strong`.
- **Thinking.** A skeleton bubble 160 by 44 px at inline-start with visually hidden text
  `thinking`.
- **Jump button**: 4.7. **Composer**: 4.8.

Scroll rules (AC-20 to AC-24). "At the bottom" means the list is within 80 px of its end.

| When | What happens |
| --- | --- |
| Chat opens | The list is at the end before the first paint, with no animation |
| At the bottom, any new item arrives (his message, a reply, the thinking bubble, an approval) | Scroll to the end (`--dur-base` smooth; instant with reduced motion) |
| At the bottom, content grows (font loads, long reply, composer grows) | Stay pinned to the end |
| Scrolled up, a new item from Ahmad arrives | Position does not move. The jump button shows its "new" mark |
| Scrolled up, Khalid sends a message | Scroll to the end |
| Scrolled up, no new item | Jump button is shown, without the "new" mark |
| Jump button tapped | Scroll to the end, button hides, auto-scroll is on again |
| The 3-second refresh runs | Never moves the list and never replays anything |

RTL: bubbles swap sides (Khalid on the left); the jump button is on the left; the Send button is
on the left of the input.

360 px: bubbles are at most 279 px wide; the composer input shrinks (it has `min-width: 0`); the
Send button keeps its size.

States:

- Empty (no messages): the list is blank except one centred `small` `--muted` line,
  `chat.empty`. The composer has focus only if Khalid taps it (no auto-focus: it would open the
  keyboard).
- Loading: three skeleton bubbles (start, end, start).
- Send failed: `sendFailed` in the note line in `--danger`; the text he typed stays (as today).
- PC offline: the banner between the top bar and the list; it does not scroll.
- Preview mode: the existing `chatPreview` note in the note line.

### 3.5 Settings (`/settings`)

Purpose: connections, phone notifications, the morning brief, the daily limit.

```
390 px, English
┌──────────────────────────────────────┐
│ (←) Settings              ([bell]3)  (≡) │
│                                      │
│ Connections                          │  h2
│ Google                               │  body-strong
│ Google connected.                    │  small, muted
│ ──────────────────────────────────── │
│ Yahoo Mail                           │
│ (!) Yahoo refused the app password.  │  small, gold-ink, with icon
│     Make a new one, then on the PC   │
│     run: snafi.cmd set-secrets       │
│ ──────────────────────────────────── │
│ Todoist                              │
│ Todoist connected.                   │
│                                      │
│ Phone notifications                  │  h2
│ [      On       ] [      Off      ]  │  options
│ (note for this button)               │
│ Reminders, the morning brief and …   │  small, muted
│ [ Send a test ] [ Turn off on all    │  secondary buttons, wrap
│                   phones ]           │
│                                      │
│ Morning brief                        │  h2
│ Today's events, top tasks, …         │  small, muted
│ Hour     Minute                      │
│ [ 7  ▾] : [ 00 ▾]  [ AM ] [ PM ]     │
│                                      │
│ Daily limit                          │  h2 (label of the input)
│ [ 10    ]                            │
│ Most pushes a day (1 to 50). …       │
│                                      │
│ [              Save               ]  │  primary
│ (note for Save)                      │
└──────────────────────────────────────┘
```

Where the connection notes go (AC-19): a new first section, **Connections**, with one row each
for Google, Yahoo Mail and Todoist, always shown. Each row: the service name (`body-strong`), then
the existing sentence for its state from `messages.ts` (`t.google[state]`, `t.yahoo[state]`,
`t.todoist[state]`), unchanged wording, in `small`.

| State | Look |
| --- | --- |
| `ok`, `off`, `waiting` | `--muted`, no icon |
| `not_connected`, `reconnect`, `error`, `stale` | `--gold-ink`, attention icon (4.9) before the text, and visually hidden "Needs attention" before the sentence |

Keep `data-testid="<source>-status"`, `data-state` and `role="status"` on each sentence, as they
were on Today. It is first on the screen because Today no longer says anything about connections.

Other changes on this screen (look and fit only; behaviour, wording and order of the push logic
are untouched):

- Sections are flat: no bordered card around each. 32 px above each `h2`.
- The page's own "Settings" heading and "Back to Today" text link are replaced by the top bar.
- Notes under buttons: success and neutral notes `--muted` with 1 px `--card-edge`; errors
  (`role="alert"`) `--danger` text, 1 px `--danger` border, attention icon; the "this phone isn't
  signed up" note stays `--gold-ink` with a 1 px `--gold-ink` border. All `small` with
  `overflow-wrap: anywhere` (they can carry a long technical detail in brackets).
- Selects and the number input: `body` (16 px, were 14 px: an iPhone zooms the page when a field
  under 16 px gets focus), 48 px high, `--card` fill, 1 px `--edge-strong`.
- The brief time row stays `dir="ltr"` (hour : minute, then AM/PM) and may wrap.
- "Turn off on all phones" confirmation stays inline (no modal), bordered 1 px `--gold-ink`.

RTL: mirrored; the time row stays left-to-right; the number input stays left-to-right.

360 px: the On/Off pair and the AM/PM pair keep equal halves; "Send a test" and "Turn off on all
phones" wrap onto two lines.

States: loading: skeleton lines per section. If settings cannot be read, defaults are shown (as
today) and Save reports the failure. If the connection states cannot be read, each row shows the
`waiting` sentence.

### 3.6 Sign-in (`/sign-in`): mobile fit and look only

```
390 px, English
┌──────────────────────────────────────┐
│                                  (≡) │  menu only
│                                      │
│                (orb)                 │  64 px, decorative
│                Snafi                 │  wordmark, 2rem
│                                      │
│             Welcome back             │  h1, title
│           Sign in to Snafi           │  small, muted
│                                      │
│ Email                                │  small, muted label
│ ┌──────────────────────────────────┐ │  48 px, 16 px text
│ └──────────────────────────────────┘ │
│ Password                             │
│ ┌──────────────────────────────────┐ │
│ └──────────────────────────────────┘ │
│ (!) Email or password is incorrect.  │  small, danger; height reserved
│ [            Sign in              ]  │  primary, 48 px
│                                      │
│        Snafi is invite only.         │  caption, muted
└──────────────────────────────────────┘
```

- No behaviour change (SEC-1, SEC-10 logic untouched).
- The bordered card around the form is removed; the fields sit on the page. Inputs: `--card` fill,
  1 px `--edge-strong`.
- The block is no longer centred vertically: `padding-block-start: clamp(24px, 8dvh, 72px)`, so
  it does not jump when the keyboard opens. Bottom padding
  `max(env(safe-area-inset-bottom), 24px)`.
- Side padding is the gutter (was 24 px plus a 24 px card padding, leaving 264 px for a field at
  360; now 328 px).
- Focus on a field: the global focus ring (today it is only a 1 px border colour change, with the
  outline removed).
- Error text is `--danger` with the attention icon (was gold). The long "plain HTTP" message wraps.
- Preview mode keeps its note and the "Open preview" primary button, without the card.
- RTL: labels and error on the right; the email and password fields stay left-to-right (as today).
- 360 px: no difference other than the gutter.
- States: submitting: button label "Signing in…", disabled, `aria-busy`. Errors as today.

---

## 4. Component specs

### 4.1 Bell and badge

- A link to `/inbox`, 44 by 44 px, round. Icon 24 px, `--text`, stroke 1.5 (4.9). On `/inbox`
  itself it has `aria-current="page"` and still works (it reloads the list).
- **What is counted:** cards with no read time that are not `test` and were not dismissed before
  this job, plus approvals that are pending and not past their expiry. `test` cards are never
  counted (Q4). Opening the Inbox list changes nothing (AC-4).
- **What is shown:** 0 → no badge element at all. 1 to 9 → the number. 10 or more → `9+`.
- **Badge look:** `min-inline-size: 18px; block-size: 18px; padding-inline: 5px;` round;
  `--badge-bg` fill, `--badge-fg` text, 12 px, weight 600, tabular, `line-height: 18px`,
  `dir="ltr"` (so "9+" never turns into "+9"). It is the one text under the 13 px floor, because
  it must fit the corner; the count is also in the label. A 2 px ring of `--bg`
  (`box-shadow: 0 0 0 2px var(--bg)`) separates it from the bell. Position: `inset-block-start:
  4px; inset-inline-end: 2px` inside the button. `aria-hidden="true"`.
- **Label (`aria-label` on the link):**

  | Count | English | Arabic |
  | --- | --- | --- |
  | 0 | `Inbox, no unread items` | `الوارد، لا شيء غير مقروء` |
  | n ≥ 1 | `Inbox, {n} unread` | `الوارد، {n} غير مقروءة` |
  | unknown | `Inbox` | `الوارد` |

  The label always says the real number (12, not "9+").
- **When it changes:** as soon as a card is opened in the Inbox or an approval is decided, without
  a reload (AC-5). A visually hidden `role="status"` next to the bell then says `{n} unread` /
  `{n} غير مقروءة` (or the zero wording). It says nothing on first load. The number changes with no
  animation.
- States: default; hover (pointer devices) `--press` round background; focus-visible ring;
  active `--press` and `scale(0.96)`; no disabled state; loading or error: no badge, plain label.

### 4.2 Now card

Content (AC-14): whichever starts first of the next prayer and the next timed event today. A tie
goes to the prayer. With no calendar or no event left today: the next prayer (after Isha, that is
tomorrow's Fajr). All-day events never appear here.

```
┌──────────────────────────────────┐   ┌──────────────────────────────────┐
│ Maghrib                          │   │ Design review with Faisal        │
│ 5:38 PM               in 42 min  │   │ 4:00 PM               in 12 min  │
└──────────────────────────────────┘   │ Head office, room 3              │
                                       └──────────────────────────────────┘
```

- Surface: `--card`, 1 px `--card-edge`, `--radius-surface`, `--shadow-card`, padding 20 px (16 at
  360). Not a link, not a button: no hover or pressed state.
- Line 1, name: `display`. Prayer name from `t.prayers`, or the event title inside `<bdi>`. At most
  two lines (`-webkit-line-clamp: 2`), `overflow-wrap: anywhere`.
- Line 2 (8 px under line 1): a wrapping flex row, `justify-content: space-between`, 12 px gap,
  `align-items: baseline`. Start: the time in the `time` role, `--gold-ink`. End: the countdown in
  `body`, `--text`.
- Line 3, events with a place only: the place in `small` `--muted`, one line, ellipsis, `<bdi>`.
- There is no "Next prayer" label above the name, no ring and no progress bar. The name and the
  countdown say it.
- **Time format:** `hm12` from `src/core/clock.ts`: `5:38 PM` / `5:38 م`. The time is wrapped in
  `<bdi>` and follows the page direction. Do **not** force `dir="ltr"` on it: in an Arabic line
  that puts "م" on the wrong side of the digits (it is forced today on Today, the email list and
  the approval's expiry line).
- **Countdown format.** Whole minutes left, rounded up. Western digits.

  | Left | English | Arabic |
  | --- | --- | --- |
  | 1 min | `in 1 min` | `بعد دقيقة` |
  | 2 min | `in 2 min` | `بعد دقيقتين` |
  | 3 to 10 min | `in {m} min` | `بعد {m} دقائق` |
  | 11 to 59 min | `in {m} min` | `بعد {m} دقيقة` |
  | 1 hr exactly | `in 1 hr` | `بعد ساعة` |
  | 2 hr exactly | `in 2 hr` | `بعد ساعتين` |
  | 3 to 10 hr exactly | `in {h} hr` | `بعد {h} ساعات` |
  | 11 hr or more, exactly | `in {h} hr` | `بعد {h} ساعة` |
  | hours and minutes | `in {h} hr {m} min` | `بعد {hours} و{minutes}`, each part in the form above without "بعد": `بعد ساعة و5 دقائق`, `بعد ساعتين و12 دقيقة`, `بعد 3 ساعات ودقيقتين` |

- **Ticking (AC-15):** one update a minute, lined up with the start of the clock minute. No
  seconds, no per-second timer. Pause while the page is hidden and recompute when it is shown
  again.
- **At zero:** on the tick where the start time has arrived, the card changes to the next prayer
  or event straight away, with no reload. The three lines cross-fade (opacity, `--dur-slow`); with
  reduced motion they just change. The card keeps its size while fading (the new content replaces
  the old; no slide, no height animation).
- **Screen readers:** the card is a `<section>` with an `aria-label`: `Next prayer: Maghrib at
  5:38 PM, in 42 min` / `الصلاة القادمة: المغرب الساعة 5:38 م، بعد 42 دقيقة`, or `Next event:
  {title} at {time}, {countdown}` / `الموعد القادم: {title} الساعة {time}، {countdown}`. It is
  **not** a live region: a minute tick must not be read out. `data-kind="prayer|event"` for tests.
- States: loading: skeleton block. Sample data: unchanged look (the page's one sample note covers
  it). No error state: the prayer side needs no network.
- Data the view needs (for Agent 13): for each candidate, its exact start instant and its formatted
  time; and enough following prayers and events to move on at zero without a reload.

### 4.3 Plan list ("Today's plan")

```
Today's plan
All day    Rent due
4:00 PM    Design review with Faisal
8:30 PM    Dinner
           +2 more
────────────────────────────────────
○          Send signed contract
                               Today
○          Call the contractor
                             Overdue
○          Book the car service
           +4 more
```

- `h2` "Today's plan". Under it two lists (`<ul aria-label="Events">`, `<ul aria-label="Tasks">`)
  separated by one 1 px `--card-edge` hairline with 12 px above and below. No sub-headings.
- Both lists use the same grid: `grid-template-columns: 4.75rem minmax(0, 1fr)`, 12 px column gap,
  so every title starts on the same line. Rows are not links.
- **Events:** today's remaining events in time order, all-day first, **at most 5** (Q3). Column 1:
  the time (`small`, `--muted`, tabular, `<bdi>`), or "All day". Column 2: the title, `body`, at
  most two lines, `overflow-wrap: anywhere`, `<bdi>`. Row padding 8 px block. If more than five
  remain: a last row with column 1 empty and `+{n} more` in `small` `--muted`.
- **Tasks:** **at most 3**, in the order the app already uses. Column 1: the task circle icon
  (16 px, `--muted`, `aria-hidden`; it is a mark, not a checkbox). Column 2: the title (`body`, two
  lines at most, `<bdi>`), and under it, end-aligned, the due text (`caption`, `--muted`). If more
  than three: `+{n} more` as above.
- **Overdue task:** due text in `--gold-ink`, weight 500, and it must contain the word "Overdue" /
  "متأخرة". Agent 14 checks what the worker's `due` text holds for an overdue task; if the word is
  not already there, put `plan.overdue` and a comma before it. Colour alone is not enough.
- **"+N more"** is plain text, not a link (there is no events or tasks screen). English
  `+{n} more`; Arabic `و{n} غيرها` (no plus sign: next to Arabic text it can jump to the wrong
  side of the number). Each has an `aria-label`: `{n} more events not shown` / `{n} more tasks not
  shown` (Arabic in section 6).
- **Empty lines** (`small`, `--muted`, in column 2's position, never an error):

  | Case | English | Arabic |
  | --- | --- | --- |
  | Calendar fine, nothing left | `No more events today.` | `لا مواعيد أخرى اليوم.` |
  | Todoist fine, nothing due | `No tasks due today.` | `لا مهام مستحقة اليوم.` |
  | Calendar state is not `ok` | `Calendar isn't available right now.` | `التقويم غير متاح الآن.` |
  | Todoist state is not `ok` | `Tasks aren't available right now.` | `المهام غير متاحة الآن.` |

  The last two do not name the fault or the fix; those are in Settings (AC-13, AC-19). Saying "no
  events" when the calendar is not connected would be untrue. Today's "—" placeholder is removed.
  See the question for Khalid.
- States: loading: four skeleton rows. No interactive states (nothing here is a control).

### 4.4 Ahmad's message ("From Ahmad")

Exactly one item or one quiet line (AC-17). Mail and test cards are never chosen.

| Order | Case | Line 1 (`body`, `--text`, two lines at most) | Line 2 (`small`) |
| --- | --- | --- | --- |
| 1 | One or more pending approvals | The oldest approval's summary | `Waiting for your approval` in `--gold-ink`; with more than one: `Waiting for your approval, and {n} more` (n = the others) |
| 2 | Newest unread reminder | The card's title | `Reminder` then the time, `--muted` |
| 3 | Today's unread brief | The card's title | `Brief` then the time, `--muted` |
| 4 | Nothing | `Nothing from Ahmad right now.` in `small` `--muted`. Not a link | none |

- `h2` "From Ahmad" above it in every case.
- Cases 1 to 3 are one link covering both lines and the chevron (end, 20 px, `--muted`, mirrored in
  Arabic). Grid `minmax(0, 1fr) auto`; `min-height: 44px`; block padding 8 px; it extends 8 px
  beyond the text on each side with `border-radius: 12px` so the hover and focus shapes have room
  (negative inline margin 8 px, padding 8 px).
- Target (AC-18): `/inbox?open=<id>` (the card's or the approval's id). In the Inbox that item is
  open: a card is thereby marked read; an approval shows Approve and Reject there. There are no
  Approve or Reject buttons on Today (Q1).
- Only the title is shown on Today, never the card's body.
- In line 2, the kind and the time are two spans 8 px apart; no dot between them.
- `aria-label` on the link: `{line 1}. {line 2}. Open in Inbox.` / `{line 1}. {line 2}. فتح في
  الوارد.`
- States: default; hover (pointer) `--press` background; focus-visible ring; active `--press`.
  Loading: two skeleton lines. If the cards cannot be read but approvals can, case 1 still works;
  if neither can be read, show case 4.

### 4.5 Inbox row (cards)

```
closed, unread                              open, read
● Reminder                  4:10 PM           Reminder                  4:10 PM
  Call the contractor about       ⌄           Call the contractor about       ⌃
  the tiles                                   the tiles
                                              Ask about the delivery date and
                                              the grout colour.
```

- Structure: `<li>` holding one `<button aria-expanded aria-controls>` (the whole closed row) and
  the body region under it. Grid: `12px minmax(0, 1fr) auto` (mark, text, chevron), 8 px column
  gap. Block padding 12 px. `min-height: 44px` (rows are about 68 px).
- Line 1: kind label at the start (`small`, `--muted`; `Reminder`, `Brief`, `Mail`, `Test`); time
  at the end (`caption`, `--muted`, tabular, `<bdi>`). Time is `hm12` for today, and
  `dayMonthClock` (`14 Nov, 9:15 PM`) for earlier days.
- Line 2: title, `body`, `<bdi>`, `overflow-wrap: anywhere`; two lines at most when closed, all of
  it when open.
- Chevron: 20 px, `--muted`, at the end of line 2; points down when closed, up when open
  (`rotate(180deg)`, `--dur-base`).
- **Unread mark, three cues:** an 8 px round dot in `--gold-ink` in the first column, level with
  line 1; the title in `body-strong` instead of `body`; and visually hidden text `Unread` /
  `غير مقروء` before the kind label. A read row keeps the empty 12 px column so titles line up.
- **Opening:** a tap or Enter/Space opens the row. The body appears under the title: `body`,
  `--text`, `white-space: pre-line; overflow-wrap: anywhere`, `dir="auto"`, 8 px above. It fades
  in over `--dur-fast`; there is no height animation. Several rows may be open at once. A second
  tap closes it.
- **Marking read (AC-5):** the first time a row is opened, mark-read is called once. The dot, the
  bold and the hidden "Unread" go at once and the badge drops by 1. If the call fails they come
  back silently. Closing a row never marks it unread.
- **Mail rows (AC-8):** line 2 is the sender (one line, ellipsis when closed); line 3 is the
  subject (`small`, `--muted`, one line, ellipsis when closed). Open: both lines wrap in full and
  **nothing else** is shown: no body, no preview, no snippet, no link. Opening still marks it read.
  Agent 14 maps the card's stored fields to these two lines; no other field of a mail card is ever
  rendered.
- **Test rows (Q4):** look and behave like any row, mark included, but never count in the badge.
- **7 days:** rows read more than 7 days ago are simply not in the list. The footer line says so.
- States: default; hover (pointer) `--press` across the full row (extend 8 px past the text each
  side, radius 12 px); focus-visible ring with `outline-offset: -2px`; active `--press`; no
  disabled state; while mark-read is in flight nothing is shown; error: silent, as above.

### 4.6 Approval item (Inbox and Chat)

One component in both places. It replaces today's card-inside-a-card.

```
┌──────────────────────────────────┐
│ Send this email to Faisal?       │  summary: body
│ Asked 4:05 PM                    │  caption, muted (Inbox only)
│ ──────────────────────────────── │  hairline
│ Exactly what will run            │  small, muted
│ Action    gmail_send             │  dt small muted │ dd body
│ to        faisal@example.com     │
│ body      I will be there by     │
│           4:30.                  │
│ ──────────────────────────────── │  hairline
│ [   Approve    ] [    Reject   ] │
│ Expires 15 Nov, 5:10 PM if not   │  caption, muted
│ decided                          │
└──────────────────────────────────┘
```

- Surface: `--card`, 1 px `--card-edge` (not gold), `--radius-surface`, `--shadow-card`, padding
  20 px (16 at 360). No inner bordered box: the arguments sit between two 1 px `--card-edge`
  hairlines with 12 px above and below.
- **In the Inbox it is always open.** It cannot be closed, so Approve is never on screen without
  the exact arguments beside it. It always counts as unread and shows no dot (the group heading
  says what it is).
- Summary: `body`, `--text`, `dir="auto"`, `overflow-wrap: anywhere`.
- Arguments: unchanged content (the tool, then every argument in full, SEC-13). `<dl>` as a grid
  `minmax(4rem, max-content) minmax(0, 1fr)` with the first column capped at 40% of the width,
  12 px column gap, 4 px row gap. `dt`: `small`, `--muted`, `dir="ltr"`, `overflow-wrap:
  anywhere`. `dd`: `body` (was 12 px), `dir="auto"`, `white-space: pre-wrap; overflow-wrap:
  anywhere; min-width: 0`. The first `dt`, hard-coded "action" today, becomes `approval.action`.
  Nothing is cut or hidden, however long.
- Buttons: Approve (primary) and Reject (secondary), equal halves, 12 px apart, 48 px high. Plain
  buttons, never swipes; the light vibration on tap stays.
- Expiry line: `caption`, `--muted`, following the page direction (remove `dir="ltr"`).
- **After a decision in the Inbox (Q2, AC-7):** the item is replaced at once, in the same place,
  by one line with `role="status"`: `Approved. Ahmad carries on in Chat.` or `Rejected. Nothing
  was run.`, `small`, `--muted`, with a text link `Open chat`. The badge drops by 1 at once. The
  line is gone the next time the list loads. In Chat the item stays, with its status line as today.
- If it expires while on screen: the buttons are replaced by `Expired` (`cardStatus.expired`); it
  is gone at the next load.
- States of the two buttons: default; hover; focus-visible; active; **loading**: both disabled
  (`opacity: 0.45`) and `aria-busy="true"` on the item while the decision is sent (no spinner; it
  takes under a second); **error**: `decideFailed` under the buttons, `--danger`, `role="alert"`,
  both buttons enabled again.

### 4.7 Jump-to-latest button

- 44 by 44 px, round. `--raised` fill, 1 px `--edge-strong`, `--shadow-float`. Arrow-down icon,
  24 px, `--text`.
- **Position:** a child of the composer, placed above it: the composer is `position: relative`;
  the button is `position: absolute; inset-block-end: calc(100% + 12px); inset-inline-end: 0`. It
  therefore always sits 12 px above the composer however tall the composer grows, stays inside the
  column, and clears the home indicator because the composer already pads the bottom safe area.
  Inline-end is the right in English and the left in Arabic (AC-28).
- **Shown** whenever the list is not at the bottom (more than 80 px from its end). **Hidden**
  whenever it is at the bottom (AC-23). When hidden it is not rendered, so it is not in the tab
  order.
- **"New" mark:** if an item from Ahmad arrived while Khalid was scrolled up (AC-22), a 10 px
  `--gold-ink` dot with a 2 px `--raised` ring sits on the button's top inline-end edge, and the
  label changes.
- Label: `Jump to latest` / `الانتقال إلى آخر الرسائل`; with the mark: `Jump to latest, new
  messages` / `الانتقال إلى آخر الرسائل، توجد رسائل جديدة`.
- **Tap:** scroll the list to its end (`--dur-base` smooth; instant with reduced motion), hide the
  button, clear the mark, turn auto-scroll back on. Focus moves to the message list (which has
  `tabindex="-1"`), not to the text field, so the keyboard does not open.
- In and out: opacity and `scale(0.9 → 1)` over `--dur-base`; none with reduced motion.
- States: default; hover (pointer) `--press` fill; focus-visible ring; active `scale(0.96)`; no
  disabled, loading or error state.

### 4.8 Composer

- A `<form>` at the bottom of the Chat column: `position: relative`, padding-block-start 8 px,
  `padding-block-end: max(env(safe-area-inset-bottom), 12px)`, background `--bg`.
- Inside: one surface (`--card`, 1 px `--edge-strong`, `--radius-surface`, `--shadow-card`,
  padding 6 px), a flex row, `align-items: flex-end`, 8 px gap: the text field, then Send.
- Text field: `<textarea>`, `flex: 1; min-width: 0`, **16 px** (`body`; it is 14 px today, which
  makes an iPhone zoom the page on focus), `min-height: 44px`, `max-height: 8rem`, padding 10 px
  by 10 px, no border of its own, `dir="auto"`. Placeholder in `--muted`. When the field has focus
  the surface's border becomes 2 px `--focus` (the field itself keeps `outline: none`, the surface
  shows the focus).
- Send: primary button, `min-height: 44px` (was 40), `padding-inline: 16px`, `flex: none`, the
  word "Send" / "إرسال". Enter sends, Shift+Enter makes a new line (unchanged).
- The disabled "attach a file" button is removed: it has never done anything and takes 48 px of a
  360 px row. It returns when attachments are built.
- Note line under the surface: one line reserved (`min-height: 1.25rem`), `caption`, centred.
  `--muted` for the preview note, `--danger` for `sendFailed`. `role="status"` (as today).
- States of Send: default; hover; focus-visible; active; disabled (empty text, sending, or page
  not ready: `opacity: 0.45`); loading: disabled with `aria-busy`, label unchanged (a send takes a
  moment; the new bubble is the feedback); error: the note line.

### 4.9 Icons

All icons are inline `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"
stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">`, drawn here
for Snafi. One weight everywhere. The accessible name is on the button or link, never on the icon.

| Icon | Size shown | Paths | Mirrors in Arabic |
| --- | --- | --- | --- |
| Bell | 24 | `M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 2h-15l1.5-2Z` and `M10 20.5a2 2 0 0 0 4 0` | No |
| Back | 24 | `M19 12H5` and `M11 6l-6 6 6 6` | Yes |
| Chevron down | 20 | `M6 9l6 6 6-6` | No |
| Chevron forward | 20 | `M9 6l6 6-6 6` | Yes |
| Arrow down (jump) | 24 | `M12 5v14` and `M6 13l6 6 6-6` | No |
| Task circle | 16 | `<circle cx="12" cy="12" r="7.25"/>` | No |
| Attention | 16 | `<circle cx="12" cy="12" r="8.25"/>`, `M12 8v4.5` and `M12 15.75v.01` | No |

Mirroring: `[dir="rtl"] .icon-mirror { transform: scaleX(-1); }`. The menu icon stays as it is
(three lines, the short one now `--gold-ink`).

Replaced glyphs: "←" (Chat back) → Back icon; "＋" (attach) → removed with the button; "✓" in
`lastBackup` → words only; " · " between an event's time and place → separate lines; "—" for
"nothing to show" → a sentence.

### 4.10 Interactive states for shared controls

"Hover" applies only inside `@media (hover: hover)`; touch screens get the active state.
"Focus-visible" is always the global ring (2.8). Transitions use `--dur-fast` and `--ease-out`.

| Control | Default | Hover | Active | Disabled | Loading | Error |
| --- | --- | --- | --- | --- | --- | --- |
| Primary button (Approve, Send, Save, Sign in) | `--gold` fill, `--on-gold` label, `button` type, radius 12, min-height 44 (48 on Sign-in and approvals) | `filter: brightness(1.06)` | `brightness(0.94)`, `scale(0.98)` | `opacity: 0.45`, no pointer events | Disabled, `aria-busy`, label changes where a string exists ("Saving…", "Signing in…", "Working…") | Message under the control, `--danger`, `role="alert"` |
| Secondary button (Reject, Send a test, Try again, Cancel) | Transparent, 1 px `--edge-strong`, `--text` label | `--press` fill | `--press`, `scale(0.98)` | `opacity: 0.45` | As primary | As primary |
| Quiet button or text link (Sign out, Open chat) | No border, `--muted` label, min 44 px tall; text links underlined | `--text` label | `--text` | `opacity: 0.45` | n.a. | n.a. |
| Option (On/Off, AM/PM, Dark/Light, language) | Unselected: 1 px `--edge-strong`, `--text`, `body`. Selected: 1 px `--gold-ink`, `--wash` fill, `--gold-ink` label in `body-strong`, `aria-pressed="true"` | Unselected: `--press` | `scale(0.98)` | `opacity: 0.45` | Label "Working…" on the one being changed | Note under the group |
| Icon button (bell, back, menu) | 44 px, round, transparent | `--press` | `--press`, `scale(0.96)` | n.a. | n.a. | n.a. |
| Text input, select, number | `--card` fill, 1 px `--edge-strong`, radius 12, 48 px, 16 px text | none | none | `opacity: 0.45` | n.a. | 1 px `--danger` border, `aria-invalid`, message under it |
| Row link or row button (Ahmad's message, inbox row) | Transparent | `--press` | `--press` | n.a. | Silent | Silent (inbox row) |
| Orb | 4.2 motion; 1 px ring `--gold-ink` at 30% | none | `scale(0.95)` | n.a. | Pulses while Ahmad thinks (Chat bar) | n.a. |

---

## 5. Mobile-fit rules

Apply these everywhere; they are what makes AC-25 to AC-28 hold.

1. **`min-width: 0`** on every flex or grid child that holds text (`min-w-0`), and
   `minmax(0, 1fr)` rather than `1fr` for grid text columns.
2. **`overflow-wrap: anywhere`** on every element showing text Khalid or the outside world wrote:
   card titles and bodies, chat messages, event names and places, task names, mail senders and
   subjects, approval summaries and every argument, notes that carry a technical detail. Where one
   line is wanted, use `overflow: hidden; text-overflow: ellipsis; white-space: nowrap` on a child
   with `min-width: 0` instead. `break-words` alone is not enough inside a flex row: it does not
   lower the item's minimum width.
3. **Logical properties only**: `margin-inline-*`, `padding-inline-*`, `inset-inline-*`,
   `text-align: start|end`, Tailwind's `ms-`, `me-`, `ps-`, `pe-`, `start-`, `end-`,
   `rounded-s*`, `rounded-e*`. No `left`, `right`, `ml-`, `mr-`, `pl-`, `pr-`, `text-left`,
   `text-right`. One exception: rule 6.
4. **No fixed or minimum width above 360 px** on anything, and no `width` in px on anything that
   holds text. Allowed fixed sizes: icon buttons 44 px, orb 64 px and 32 px, the badge, the plan's
   4.75rem column, the menu popover `min(18rem, 100vw - 2 * var(--gutter))`, the daily-limit input
   7rem.
5. **Inputs, selects and textareas are 16 px or larger.**
6. **Safe areas.** Top bar: `padding-block-start: max(env(safe-area-inset-top), 8px)`. Bottom of
   each screen, the composer and the orb: `max(env(safe-area-inset-bottom), …)` as given per
   screen. Sides, on the page frame: `padding-left: max(var(--gutter), env(safe-area-inset-left));
   padding-right: max(var(--gutter), env(safe-area-inset-right))`. These two are physical on
   purpose: the insets are physical and the gutter is the same on both sides. `viewport-fit=cover`
   is already set. Do not add `maximum-scale` or `user-scalable=no`: pinch-zoom stays (A10).
7. **Root backstop:** `html, body { overflow-x: clip; }`. It hides a mistake; it does not fix one.
   AC-25 is measured on `scrollWidth`, which still shows the mistake, so every item below must be
   fixed at its source.
8. **Nothing animates sideways** and nothing uses `100vw` for a width (it ignores the scrollbar).
9. **Direction of outside text:** single-line titles use `<bdi>` (the text orders itself, the row
   keeps its alignment); multi-line bodies use `dir="auto"`. Times and counts use `<bdi>` and
   follow the page; only fields that are Latin by nature (email, password, argument names, the
   time picker, the badge) are `dir="ltr"`.
10. **Touch:** every control is at least 44 by 44 px, with at least 8 px between neighbours.

### Places in the current code that can overflow or misfit

Found by reading the source, not by measuring.

| File | What is wrong | Change |
| --- | --- | --- |
| `src/app/globals.css` `.screen-in` / `snafi-slide` | `translateX(16px)` on `<main>` widens the page while it runs | Opacity only (2.7) |
| `src/app/globals.css` `:focus-visible` | Sets `border-radius: 6px` on whatever has focus; unlayered, so it likely beats `rounded-full` | Remove the radius; move base rules into `@layer base` |
| `src/app/globals.css` | No root backstop | Add rule 7 |
| `src/app/(app)/layout.tsx` | Offline and preview banners come before the top bar with no top safe-area padding; `px-5` fixed gutter; `<main>` bottom padding also applies to Chat | Banner under the bar; gutter token with safe-area sides; no bottom padding on Chat |
| `src/components/TopBar.tsx` | `tracking-[0.08em]` also spaces the Arabic wordmark; the bar has no `min-width: 0` start group for a title | English-only tracking; 3.1 layout |
| `src/components/Menu.tsx` | Panel `w-72` is fixed; `rise-in`; uppercase labels; the backup line is a bare string that can be long | `min(18rem, 100vw - 2 * var(--gutter))`; no animation; sentence case; `overflow-wrap: anywhere` on status lines |
| `src/app/(app)/today/TodayView.tsx` orb wrapper | `fixed inset-x-0 bottom-0` spans the full width and takes the taps along the bottom strip | `pointer-events: none` on the wrapper, `auto` on the orb |
| `src/app/(app)/today/TodayView.tsx` event title, place | `<p dir="auto">` with no wrap rule: a 200-character word runs out of the card | Rule 2 (the card itself is replaced by the plan row) |
| `src/app/(app)/today/TodayView.tsx` Ahmad's card | Title `<p>` is a flex child without `min-w-0`; body has `whitespace-pre-line` and no wrap rule | Section is removed from Today; apply rules 1 and 2 in the Inbox row |
| `src/app/(app)/today/TodayView.tsx` task title | `min-w-0 flex-1` but no wrap rule: a long word draws outside its box | Rule 2 |
| `src/app/(app)/today/TodayView.tsx` times | `dir="ltr"` on Arabic times puts "م" on the wrong side | `<bdi>`, page direction |
| `src/components/ApprovalCard.tsx` summary | No wrap rule | `overflow-wrap: anywhere` |
| `src/components/ApprovalCard.tsx` arguments | `dd` is a flex child without `min-w-0`, and `break-words` does not shrink it; a long key in `dt shrink-0` can take the row; `font-mono` is a fifth font; 11 and 12 px text | Grid in 4.6; rules 1 and 2; body font; sizes from 2.6 |
| `src/components/ApprovalCard.tsx` expiry line | `dir="ltr"` on an Arabic sentence | Follow the page |
| `src/app/(app)/chat/ChatView.tsx` bubbles | `max-w-[85%] whitespace-pre-line` with no wrap rule: a long link runs out of the bubble and the page | `overflow-wrap: anywhere; min-width: 0` |
| `src/app/(app)/chat/ChatView.tsx` header | `flex-1` text block without `min-w-0`; "←" glyph; `min-h-[calc(100dvh-6rem)]` guess | Moves into the top bar (3.1); Back icon; column layout (3.4) |
| `src/app/(app)/chat/ChatComposer.tsx` textarea | `text-sm` (14 px) makes an iPhone zoom on focus; `flex-1` without `min-w-0`, so at 360 px the field's built-in width can push the row wider than the screen | 16 px; `min-width: 0` |
| `src/app/(app)/chat/ChatComposer.tsx` buttons | Attach is 40 px with a "＋" glyph; Send is 40 px high | Attach removed; Send 44 px |
| `src/components/UndoButton.tsx` | `min-h-9` (36 px) | 44 px |
| `src/app/(app)/settings/SettingsForm.tsx` selects, number input | `text-sm` (14 px): zoom on focus | 16 px, 48 px high |
| `src/app/(app)/settings/SettingsForm.tsx` notes | Error text with a detail in brackets has no wrap rule | `overflow-wrap: anywhere` |
| `src/app/(app)/settings/page.tsx` | Heading row: `h1` without `min-w-0` beside a link | Replaced by the top bar |
| `src/app/sign-in/page.tsx` | `px-6` plus card `p-6` leaves 264 px for a field at 360 px; `justify-center` moves the form when the keyboard opens; `tracking-[0.1em]` on the Arabic wordmark | 3.6 |
| `src/app/sign-in/SignInForm.tsx` | `focus:outline-none` leaves a 1 px colour change as the only focus sign | Global focus ring |
| `src/components/Card.tsx` `PlaceholderBadge` | 10 px uppercase text | Removed from Today; if kept elsewhere, `caption`, sentence case |

---

## 6. Copy

Sentence case, plain words, the same word for the same thing: the screen is always "Inbox" /
"الوارد", the items in it "notifications" / "الإشعارات", the action "Approve" / "موافقة".
Errors say what happened and what to do; they do not apologise. Suggested keys for
`src/i18n/messages.ts`; functions take the values in braces.

### New

| Key | English | Arabic |
| --- | --- | --- |
| `skipToContent` | Skip to content | انتقل إلى المحتوى |
| `retry` | Try again | حاول مرة أخرى |
| `inbox.title` | Inbox | الوارد |
| `inbox.bell(n)`, n ≥ 1 | Inbox, {n} unread | الوارد، {n} غير مقروءة |
| `inbox.bellNone` | Inbox, no unread items | الوارد، لا شيء غير مقروء |
| `inbox.unreadNow(n)` (live update) | {n} unread | {n} غير مقروءة |
| `inbox.unreadNone` (live update) | No unread items | لا شيء غير مقروء |
| `inbox.badgeMany` | 9+ | 9+ |
| `inbox.notifications` | Notifications | الإشعارات |
| `inbox.kind.reminder` | Reminder | تذكير |
| `inbox.kind.brief` | Brief | ملخص |
| `inbox.kind.mail` | Mail | بريد |
| `inbox.kind.test` | Test | تجربة |
| `inbox.unread` (hidden text) | Unread | غير مقروء |
| `inbox.asked(time)` | Asked {time} | طُلبت {time} |
| `inbox.approved` | Approved. Ahmad carries on in Chat. | تمت الموافقة. يكمل أحمد في المحادثة. |
| `inbox.rejected` | Rejected. Nothing was run. | رُفض الطلب. لم يُنفَّذ شيء. |
| `inbox.openChat` | Open chat | فتح المحادثة |
| `inbox.emptyTitle` | Nothing in your inbox. | لا شيء في الوارد. |
| `inbox.emptyBody` | Reminders, briefs, mail alerts and approvals from Ahmad appear here. | تظهر هنا تذكيرات أحمد وملخصاته وتنبيهات البريد وطلبات الموافقة. |
| `inbox.clearNote` | Read items clear after 7 days. | تُزال العناصر المقروءة بعد 7 أيام. |
| `inbox.loadFailed` | Couldn't load your inbox. Check your connection, then try again. | تعذّر تحميل الوارد. تحقّق من الاتصال ثم حاول مرة أخرى. |
| `inbox.back` | Back to Today | العودة إلى اليوم |
| `approval.action` | Action | الإجراء |
| `now.prayerLabel(name, time, countdown)` | Next prayer: {name} at {time}, {countdown} | الصلاة القادمة: {name} الساعة {time}، {countdown} |
| `now.eventLabel(title, time, countdown)` | Next event: {title} at {time}, {countdown} | الموعد القادم: {title} الساعة {time}، {countdown} |
| `now.countdown(hours, minutes)` | The table in 4.2 | The table in 4.2 |
| `plan.title` | Today's plan | خطة اليوم |
| `plan.events` (list label) | Events | المواعيد |
| `plan.tasks` (list label) | Tasks | المهام |
| `plan.allDay` | All day | طوال اليوم |
| `plan.more(n)` | +{n} more | و{n} غيرها |
| `plan.moreEventsLabel(n)` | {n} more events not shown | {n} من المواعيد غير معروضة |
| `plan.moreTasksLabel(n)` | {n} more tasks not shown | {n} من المهام غير معروضة |
| `plan.noEvents` | No more events today. | لا مواعيد أخرى اليوم. |
| `plan.noTasks` | No tasks due today. | لا مهام مستحقة اليوم. |
| `plan.eventsUnavailable` | Calendar isn't available right now. | التقويم غير متاح الآن. |
| `plan.tasksUnavailable` | Tasks aren't available right now. | المهام غير متاحة الآن. |
| `plan.overdue` | Overdue | متأخرة |
| `ahmad.waiting` | Waiting for your approval | بانتظار موافقتك |
| `ahmad.waitingMore(n)` | Waiting for your approval, and {n} more | بانتظار موافقتك، و{n} غيرها |
| `ahmad.openInInbox` (end of the link's label) | Open in Inbox. | فتح في الوارد. |
| `today.loadFailed` | Couldn't load Today. Check your connection, then try again. | تعذّر تحميل صفحة اليوم. تحقّق من الاتصال ثم حاول مرة أخرى. |
| `chat.jump` | Jump to latest | الانتقال إلى آخر الرسائل |
| `chat.jumpNew` | Jump to latest, new messages | الانتقال إلى آخر الرسائل، توجد رسائل جديدة |
| `chat.empty` | Say hello to Ahmad. | اكتب أول رسالة لأحمد. |
| `settings.connectionsTitle` | Connections | الاتصالات |
| `settings.service.google` | Google | Google |
| `settings.service.yahoo` | Yahoo Mail | بريد Yahoo |
| `settings.service.todoist` | Todoist | Todoist |
| `settings.needsAttention` (hidden text) | Needs attention | يحتاج إلى انتباه |

Reused as they are: `ahmadCards` ("From Ahmad" / "من أحمد"), `noCards` ("Nothing from Ahmad right
now." / "لا شيء من أحمد الآن."), `approvals` ("Waiting for your approval" / "بانتظار موافقتك") as
the Inbox group heading, `approve`, `reject`, `exactly`, `expires`, `cardStatus`, `decideFailed`,
`thinking`, `back`, `google.*`, `yahoo.*`, `todoist.*`, `placeholderNote`, `loading`.

### Changed

| Key | Old | New (English) | New (Arabic) | Why |
| --- | --- | --- | --- | --- |
| `lastBackup` (ok) | Last backup {when} ✓ | Last backup {when} | آخر نسخة احتياطية {when} | No glyph as an icon; the failed wording already differs |
| `settings.offAllConfirm` | …will still appear on Today. | Turn off notifications on all your phones? Reminders, briefs and important email will still appear in the Inbox. | إيقاف الإشعارات على كل هواتفك؟ ستظل التذكيرات والملخصات والبريد المهم تظهر في الوارد. | Cards are in the Inbox now |
| `settings.capHelp` | …cards still appear on Today, silently. | Most pushes a day (1 to 50). Reminders don't count. Past the limit, cards still appear in the Inbox, silently. | أقصى عدد للإشعارات في اليوم (من 1 إلى 50). التذكيرات لا تُحتسب. بعد الحد تظهر البطاقات في الوارد بصمت. | Same |

Both changed Settings strings state a fact about where cards appear; they are corrected to stay
true, not reworded otherwise.

### No longer used (remove if nothing else reads them)

`prayerRingLabel`, `nextPrayer`, `nextEvent`, `noEvents`, `importantEmail`, `noImportantEmail`,
`accountLabel`, `topTasks`, `noTasks`, `approvalsEmpty`, `dismiss`, `chatSubtitle`, `attach`,
`placeholder`, `settings.back`, `settings.title` stays (it is the top bar title).

---

## 7. Accessibility (target: WCAG 2.2 AA)

### 7.1 Structure

- One `h1` per screen: the greeting on Today; the title in the top bar on Inbox, Chat and
  Settings; "Welcome back" on Sign-in. Sections use `h2`. No level is skipped.
- Landmarks: `<header>` (top bar), `<main id="content">`. A skip link, `skipToContent`, is the
  first focusable element on every screen; it is visually hidden until focused, then shown at the
  top inline-start on `--raised` with the focus ring.
- `lang` and `dir` on `<html>` as today. Outside text follows rule 9 in section 5.

### 7.2 Focus order

| Screen | Order |
| --- | --- |
| Every signed-in screen | Skip link → back (if any) → bell → menu → content |
| Today | … → Ahmad's message (if it is a link) → orb. The Now card and the plan are not focusable |
| Inbox | … → each approval: Approve, Reject → each row button, top to bottom. On arrival with `?open=`, focus starts on that item (the row button, or the approval's Approve button's container with `tabindex="-1"`) |
| Chat | … → inside the list: approval buttons and Undo buttons in order → jump button (when shown) → text field → Send |
| Settings | … → On, Off → Send a test → Turn off on all phones → hour, minute, AM, PM → daily limit → Save |
| Sign-in | Skip link → menu → email → password → Sign in |

The jump button comes after the list and before the text field in the DOM, which matches where it
is seen. Visual order and DOM order agree everywhere; nothing uses `order` or `flex-direction:
*-reverse` to move controls.

Menu popover: unchanged (focus moves in on open, Escape closes and returns focus to the button).

### 7.3 Targets and keyboard

- Bell, back, menu, inbox rows, Ahmad's message, Approve, Reject, the jump button, Send, Undo, the
  orb and every option are at least 44 by 44 px (AC-32; WCAG 2.5.8 asks for 24).
- Everything works with Tab, Shift+Tab, Enter and Space. Inbox rows are real `<button>`s; Ahmad's
  message, the bell and back are real links.
- No action depends on hover, a swipe or a long press.

### 7.4 Live regions

| Where | Markup | What is announced |
| --- | --- | --- |
| Bell | Visually hidden `role="status"` beside the bell | `{n} unread` (or the zero wording) when the count changes after load. Nothing on first load |
| Chat list | `role="log"` wrapper (`aria-live="polite"`, additions only) around the `<ol>`; move `aria-live` off the `<ol>` | Each new message, including while Khalid is scrolled up. That is the announcement for "new message while reading back"; the jump button's changed label is not announced separately, so nothing is said twice |
| Chat thinking | Hidden text inside the skeleton bubble, inside the log | "Ahmad is thinking…" once |
| Composer note | `role="status"` (as today) | Send failed |
| Inbox, after a decision | `role="status"` line | "Approved. Ahmad carries on in Chat." or "Rejected. Nothing was run." |
| Approve or Reject failed; Settings errors; Sign-in errors | `role="alert"` | The error |
| Settings connection sentences | `role="status"` (as on Today before) | Not announced on load; announced if a state changes while open |
| Now card | Not live | Nothing on a tick or on the change at zero |
| Inbox mark-read | None | Silent; the badge region covers the count |

### 7.5 Screen-reader names

- Bell: 4.1. Back: "Back to Today" / "العودة إلى اليوم". Menu: unchanged. Orb on Today: "Talk to
  Ahmad" / "تحدّث مع أحمد". The orb in the Chat bar and on Sign-in is decorative
  (`aria-hidden`).
- Inbox row button: its own text is the name, in reading order: "Unread" (if so), kind, time,
  title (and for mail: sender, subject). `aria-expanded` says open or closed.
- Now card: 4.2. Plan lists: `aria-label` "Events" and "Tasks". "+N more": 4.3.
- Jump button: 4.7. Icons: always `aria-hidden`.

### 7.6 Not by colour alone

| State | Colour | Second cue |
| --- | --- | --- |
| Unread | `--gold-ink` dot | Bold title and hidden "Unread" |
| Selected option | `--gold-ink` border, `--wash` fill | Bold label and `aria-pressed` |
| Error | `--danger` | Attention icon and the message's words |
| Needs attention (connection, PC offline) | `--gold-ink` | Attention icon and the sentence |
| Overdue task | `--gold-ink` | The word "Overdue" |
| Waiting for approval | `--gold-ink` | The words |
| New messages below (Chat) | `--gold-ink` dot on the jump button | The button's label |

### 7.7 Other

- Contrast: section 2.2 (calculated). Focus ring: 2 px, 3:1 or better in both themes.
- Reduced motion: section 2.7.
- Text can be zoomed to 200% and the page pinch-zoomed; all type is in rem, nothing is clipped by
  a fixed height (rows grow; only one-line fields truncate, and their full text is reachable by
  opening the row).
- Reflow at 320 px wide: the same rules as 360 px hold; nothing is designed below 320.
- Not checked here: real screen-reader output (VoiceOver, TalkBack) and Windows high-contrast
  mode. They need a device.

---

## 8. Skills applied

Skill folders: `.claude/skills/frontend-design/` and `.claude/skills/impeccable/`. Both were read
as advice. Following each folder's `SOURCE.md`, no launcher, script, detector, hook or live mode
was run, nothing was fetched, and no `PRODUCT.md` or `DESIGN.md` was created.

| Decision | Skill file and guidance |
| --- | --- |
| Treat the job as a refinement: keep themes, gold, four fonts, behaviour and wording | impeccable `SKILL.md` ("The brief wins"; "Refinement preserves"); `polish.md` ("refinement, never concealed redesign"); `SOURCE.md` overrides |
| Standard controls and a known navigation model (back arrow plus title on sub-screens, bell, menu); identity only through type, palette, density and one signature move | impeccable `mode-operate.md` (the world lends four things; "navigation that reads as navigation") |
| The Now card as the single bold element; everything around it quiet | frontend-design `SKILL.md` ("Spend your boldness in one place"); `mode-operate.md` ("one signature move") |
| Now card leads with the name, not a big number over a small label; no progress ring or bar | frontend-design (the big-number hero is the default treatment); `craft-floor.md` (refuse the hero-metric template; "progress rings … standing in for content") |
| Today has one card; plan, message, Settings sections and Inbox rows are flat | `distill.md` ("Remove unnecessary cards", "never nest cards inside cards"); `craft-floor.md` (same-size cards as page structure; nested cards); `quieter.md` ("flatter cards") |
| Approval item loses its inner bordered box | `craft-floor.md` ("nested cards are always wrong") |
| Gold kept for meaning only; neutral hairlines and headings | `quieter.md` ("Neutral dominance", "Borders & lines: … decrease opacity"); `colorize.md` ("Rarity gives an accent force"; "do not spend its color on decoration") |
| Solid `--muted`, `--wash` instead of see-through colours | `colorize.md` ("Prefer explicit colors over chains of translucent overlays"); `quieter.md` ("transparency ties contrast to whatever sits behind the text") |
| Warm-tinted greys kept for `--muted` and `--edge-strong` | `quieter.md` ("Tinted grays") |
| Light theme gets its own focus, badge and shadow values rather than a copy of dark | `colorize.md` ("design surface elevation and contrast explicitly; do not invert … mechanically"); contrast table from `colorize.md` and `craft-floor.md` |
| Danger colour added; every state has a second cue | `colorize.md` ("Information conveyed by color also needs text, shape …"); `distill.md` ("keep semantic colors … pair each with a non-color cue") |
| Shadows with offset and blur, navy-tinted; glow no longer a zero-offset halo that animates | `craft-floor.md` (Depth); frontend-design (the same grey shadow under everything is a tell) |
| Fixed rem type scale, six roles, 16 px body, 13 px floor | `typeset.md` (Operate: "fixed role scale"; "1rem / 16px as the ordinary web body floor"; "Keep repeated roles consistent") |
| More line height for Arabic; a heavier heading weight at 20 px | `typeset.md` ("Tune line height to the face, width, language"; dark surfaces: "one step more weight when the face needs it") |
| `text-wrap: balance` and `pretty`; tabular numerals | `typeset.md` (Line breaks; "numeric, tabular … features") |
| No uppercase labels, no label above the Now card, gold name removed from the greeting, no " · " separators | frontend-design (all-caps labels, labels above content, accenting one word, middle-dot meta strings are tells); `craft-floor.md` (eyebrow ban) |
| No monospace for the tool name | `craft-floor.md` ("Monospace as a costume") |
| Authored SVG icons in one stroke; glyphs replaced | `craft-floor.md` ("Unicode glyphs or emoji standing in for an icon system"); `polish.md` (icon stroke and sizing coherent) |
| No entrance animation; one authored moment (Now card at zero); motion that answers an action | frontend-design (fade-and-rise on each section is the generic default; action-answering motion is welcome); `craft-floor.md` (Motion); `quieter.md` ("Remove decorative animations") |
| Ease-out-quart, no bounce | `quieter.md` ("Refined easing") |
| Selection, caret, accent colour, scrollbar, underline offset themed | `craft-floor.md` (Browser surfaces) |
| 4 px spacing scale; more space above a heading than below; grouping by distance before boxes | `layout.md` ("4-unit base"; "Use proximity before adding containers"); `craft-floor.md` (Spacing) |
| Ahmad's message above the plan; variable-length content last | `layout.md` ("Let hierarchy follow product priority"; stable structure is an affordance in Operate) |
| Optical pull of the outer icon buttons to the gutter, flagged "check by eye" | `layout.md` ("Make optical corrections only after inspecting the rendered result") |
| Mobile-first, 44 px targets, hover only on hover devices, safe areas, 16 px inputs | `adapt.md` (Touch Adaptation; "Detect Input Method"; "Safe Areas"); `harden.md` (iOS zoom under 16 px) |
| `min-width: 0`, wrap rules, logical properties, no fixed widths on text, long-text table | `harden.md` (Text Overflow & Wrapping; RTL support; "Avoid fixed widths on text containers") |
| Empty, loading and error states for each screen; double-submit blocked; failures say what to do | `harden.md` (Edge Cases; Error Handling); `polish.md` (Triage step 2; Interaction and state) |
| Arabic plural forms written out for the countdown | `harden.md` (Pluralization) |
| Copy: sentence case, one name per thing, errors that direct, quiet empty states | frontend-design ("More on writing in design"); `distill.md` (Content Simplification) |
| Permanently disabled attach button and static chat subtitle removed | `distill.md` ("Every element should justify its existence") |
| Inline confirmation for "all phones" kept, no modal | `craft-floor.md` ("A modal for a task that needs neither interruption nor protected focus") |

### Skill guidance deliberately not followed

| Guidance | Why not |
| --- | --- |
| impeccable `SKILL.md` Setup: run the `impeccable context` launcher; `layout.md`, `typeset.md`, `polish.md`: run the detector, critique storage, live-mode parameters | `SOURCE.md` forbids it and nothing is installed. The manual assessment was done from the source |
| "Verify by looking at the rendered result" (impeccable `SKILL.md`, `craft-floor.md` Verify, `polish.md` step 5) | Agent 17 has no shell or browser. Agent 15 measures (AC-25) and Khalid reviews screenshots (AC-30). This document claims nothing rendered |
| frontend-design: take an aesthetic risk, choose distinctive typefaces and palette | The brief pins themes, gold and four fonts; this is a refinement |
| `mode-operate.md`: a committed colour for the shell (coloured header or tinted ground); "a grey screen with one accent" is the category default | PRD Design pins charcoal or ivory with gold used sparingly. Warmth comes from tinted neutrals and the existing time-of-day tone |
| `colorize.md`: prefer OKLCH | Only for new palettes; the same file says to use the project's existing colour space (hex) |
| `quieter.md`: lower saturation to 70–85% | The gold values are pinned; gold is reduced by area and by role instead |
| `typeset.md` and `distill.md`: one font family is often right | Four families are pinned (two per language) |
| `typeset.md`: `text-box: trim` and fallback `size-adjust` for optical centring | Cannot be judged without rendering; not needed for this job |
| `craft-floor.md`: reach for blur, backdrop-filter, clip-path, mask | Not calm, and continuous effects cost battery (PRD performance note) |
| `adapt.md`: bottom navigation, swipe gestures, bottom sheets | PRD pins the menu at the top inline-end and plain buttons, never swipes; four screens do not need a navigation bar |
| `harden.md`: Arabic-Indic digits and `Intl` date formatting | Khalid's rule (`src/core/clock.ts`): Western digits and hand-built 12-hour times in both languages |
| `harden.md`: `hyphens: auto` | Not reliable for Arabic or mixed text; `overflow-wrap: anywhere` is used |
| frontend-design: avoid "typographic labels above content" | Kept for the Inbox kind label only: AC-3 requires each row to show its kind, so it is information, not decoration |
| `quieter.md`, `distill.md`: ask with a question tool when unclear | No such tool here; open points go to Ahmad for Khalid in the hand-back |

---

## 9. What is removed

| Removed | Why |
| --- | --- |
| `rise-in` on every card, on each chat message and on the menu, with its stagger | The generic entrance; it also made a 30-second refresh feel busy. Nothing animates on load now |
| The sideways slide in `screen-in` (kept as a 180 ms fade) | Widens the page while it runs; a fade is enough |
| `PrayerRing` and `prayerRingLabel` | Replaced by the Now card (A9). A ring cannot show an event, and the countdown says the same thing in words |
| `DismissButton` and the Dismiss wording | AC-10: read state replaces dismissing |
| On Today: connection notes, Important email, the list of Ahmad's cards, approval cards with buttons, Next event card, Top tasks card, per-card Sample badges, the two-column grid | AC-12, AC-13. Their content is in the Now card, the plan, Ahmad's message, the Inbox or Settings |
| `Card` as the page's building block (only its `Skeleton` is still needed) | One card on Today; flat sections elsewhere |
| Gold hairlines (`--card-edge` gold tint, `border-gold/40`, `border-gold/60`), gold `h2`, the gold name in the greeting | Gold is kept for meaning |
| Gold as the error colour | Errors looked like selections; `--danger` now |
| Uppercase, letter-spaced labels (menu, "Exactly what will run", Sample badge) and all 10 to 12 px text (the badge number excepted) | Calmer, and readable in Arabic |
| Letter-spacing on the Arabic wordmark | Breaks joined letters |
| `font-mono` on the tool name | A fifth, system font (AC-29) |
| Glyphs used as icons: "←", "＋", "✓", " · ", "—" | Authored SVG or words |
| The inner bordered box in the approval card | A card inside a card |
| The second header row in Chat and the line "Your executive assistant" | One bar; the line said nothing after the first visit |
| The disabled "attach a file" button | Never worked; returns with attachments |
| The gold shimmer skeleton (kept as a neutral pulse) | Less colour and less motion while waiting |
| The orb's animated `box-shadow`, and its idle breathing in the Chat bar | Same look from opacity and scale only; still in Chat unless thinking |
| Bordered cards around Settings sections and around the Sign-in form | Fewer boxes |
| The "Settings" page heading row and "Back to Today" text link | The top bar does both |
| `border-radius: 6px` in the focus rule; `focus:outline-none` on Sign-in fields | They reshaped focused controls and weakened the focus sign |
| Forced `dir="ltr"` on Arabic times and on the approval's expiry sentence | Wrong order in Arabic |
| The 600 ms theme transition (now 200 ms) | Felt slow |
| `shadow-2xl` and the 1 px bottom "shadow" on cards | Replaced by two tokens |

Kept on purpose: the orb and its breathing on Today and Sign-in, the time-of-day tone, the
three-line menu at the top inline-end, skeleton loading with no spinners, Approve and Reject as
plain buttons with a light vibration, and the wording of every existing message except the three
in section 6.

# Browser measurements and screenshots — Snafi UI job (AC-25, AC-30)

Ahmad, Nov 16, 2026. Branch `feat/snafi-ui-inbox`, after Agent 14's fixes (commit `93ff70e`).

Measured in the Claude desktop app's browser pane (a Chromium engine) against the local preview
server (`npm run dev:preview`, port 3100, sample data, no Supabase, no network). This is one
engine on one PC: it is not a real iPhone or a real Android phone, and it is not Safari.

## AC-25 — nothing wider than the screen

For each page the test reads `documentElement.scrollWidth`, `body.scrollWidth` and every element's
bounding box, and counts the elements whose box crosses either edge of the viewport.

| Page | 390 px English | 390 px Arabic | 360 px English | 360 px Arabic |
| --- | --- | --- | --- | --- |
| Sign-in | 390 / 0 over | 390 / 0 over | 360 / 0 over | 360 / 0 over |
| Today | 390 / 0 over | 390 / 0 over | 360 / 0 over | 360 / 0 over |
| Inbox | 390 / 0 over | 390 / 0 over | 360 / 0 over | 360 / 0 over |
| Chat | 390 / 0 over | 390 / 0 over | 360 / 0 over | 360 / 0 over |
| Settings | 390 / 0 over | 390 / 0 over | 360 / 0 over | 360 / 0 over |

Every cell: scroll width equals the viewport width exactly, and no element crosses either edge.
**20 of 20 measurements pass.** The sample data includes a 200-character unbroken word and a very
long URL in the chat, and both wrap inside their bubble (see `390-chat-en-jump-to-latest.jpg`).

## Chat scroll (AC-20, AC-22)

- On opening `/chat`, the message list is its own scroller and sits at the end:
  height 595, scroll height 1268, scroll top 673, at bottom **true**.
- The CSS `:has()` rule that gives Chat its own scrolling column works in this engine (Agent 15
  could not test it; still unproven in Safari).
- Scrolling up leaves the position where it is and shows the **Jump to latest** button
  (confirmed by name in the accessibility tree and visible in the screenshot).

## AC-30 — screenshots at 390 px

| File | What it shows |
| --- | --- |
| `screenshots/390-today-en.jpg` | Today, English, at the top |
| `screenshots/390-today-en-bottom.jpg` | Today, English, scrolled down: "From Ahmad" and the orb |
| `screenshots/390-inbox-en.jpg` | Inbox, English: the pending approval open, then the notifications |
| `screenshots/390-chat-en.jpg` | Chat, English, as it opens: at the latest message |
| `screenshots/390-chat-en-jump-to-latest.jpg` | Chat scrolled up: the jump-to-latest button, a long URL wrapping, Arabic messages |
| `screenshots/390-today-ar.jpg` | Today, Arabic: the whole layout mirrored |
| `screenshots/390-inbox-ar.jpg` | Inbox, Arabic: mirrored, Approve and Reject in Arabic |

The "Preview mode" banner in every shot belongs to the local preview only; it does not appear in
the real app. All content is sample data.

## What these measurements do not cover

- A real iPhone or Android phone, the installed app, Safari, the on-screen keyboard, pinch-zoom,
  no-zoom-on-focus, the safe areas and `100dvh`.
- Screen readers, measured contrast, and measured 44 px targets (read from the CSS, not measured).
- Light theme (the shots are dark), and the look itself, which is Khalid's judgement.

## Second round, Nov 16: after Khalid's swap and the two Arabic tidies

Khalid asked for Ahmad's message above the plan, for "متأخرة" to stay with its task, and for the
foot of the plan to clear the orb. Re-measured on a restarted preview:

| Check | 390 EN | 390 AR | 360 EN | 360 AR |
| --- | --- | --- | --- | --- |
| Today scroll width / elements over an edge | 390 / 0 | 390 / 0 | 360 / 0 | 360 / 0 |
| Orb clearance (`padding-bottom` on the page) | 144 px | 144 px | 144 px | 144 px |
| Gap between the last plan line and the orb's top | 138 px | 137 px | — | — |

- The order is right: "From Ahmad" with the waiting approval now sits directly under the Now card,
  on the first screen at 390 px (`screenshots/390-today-en.jpg`, `390-today-ar.jpg`).
- "Overdue" / "متأخرة" now sits under its own task in both languages, not at the opposite edge.
- The foot of the plan is clear of the orb and its glow (`390-today-en-bottom.jpg`,
  `390-today-ar-bottom.jpg`).

**A correction to my own earlier finding.** I reported that the Today page's bottom padding
"generates no CSS at all". That was wrong, and Agent 14 was right to push back: the class was in
the built stylesheet all along, and the 0 px I measured came from a **stale cached stylesheet** in
the preview tab — the dev server had rewritten the same chunk file name with new content. Forcing
the browser to re-fetch the stylesheet gives 144 px. The padding is now a named `.orb-clear` rule
in `globals.css` anyway, which the test suite can check and which cannot go missing silently.
The lesson for later measuring: re-fetch the stylesheet (or restart the preview and hard-reload)
before trusting a computed style.

## Two cosmetic things worth Khalid's eye

1. ~~Ahmad's message sits below the first screen on Today.~~ **Fixed on Nov 16** at Khalid's
   instruction: the message is now above the plan.
2. ~~In Arabic, "متأخرة" wraps onto its own line at the far edge, and "+2 more" sits close to the
   orb's glow.~~ **Both fixed on Nov 16** and re-measured above.

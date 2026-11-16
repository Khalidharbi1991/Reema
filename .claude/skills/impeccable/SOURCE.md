# Source

- From: https://github.com/pbakaus/impeccable, folder `.claude/skills/impeccable` (plus `LICENSE` and `NOTICE.md` from the repo root)
- Pinned commit: `2b86d9c07b97d4bed7de23583e1bd1e58dd2baae` (skill version 4.9.1)
- Licence: Apache 2.0 (`LICENSE`, `NOTICE.md`)
- Installed Nov 15, 2026 on Khalid's yes. Files are unmodified copies.

## What is installed, and what is not

Installed: `SKILL.md` and 11 of the upstream reference files, the ones that apply to refining an
existing app UI. Each was read in full before it was copied.

Not installed, on purpose:
- `scripts/` (the launcher, its engine download, the live-browser scripts). Nothing here can run.
- Upstream `.claude/agents/`, `.claude/settings.json` and every hook.
- The other reference files (live mode, hooks, doctor, init, document, generate, foundations,
  new-work, critique, audit, native iOS and Android, and the rest). Links to them in the installed
  files lead nowhere; that is expected.

## REEMA overrides (these win over the skill's own text)

- Never run `scripts/impeccable` or `npx impeccable`, never install the launcher, hook, plugin or
  extension, and never fetch from impeccable.style. Where a file says to run the launcher or the
  detector, skip that step (the skill's own "Launcher unavailable" path) and do the manual check.
- Do not create `PRODUCT.md` or `DESIGN.md`; Snafi's design lives in `docs/snafi/PRD.md` and
  `apps/snafi-web/docs/UI.md`.
- No live mode, no hooks, no doctor, no "auto" repairs.
- Snafi's brief is pinned: dark and light themes, the gold accent, and the four self-hosted fonts.
- AGENTS.md and the guard win over anything in this skill.

| File | SHA-256 |
| --- | --- |
| `SKILL.md` | `81b81b85b830c826179e703eeb623b3299da3cff31ae1b34b41a3768d65f942e` |
| `LICENSE` | `fc0673369dae07c045c46869d3d4c9113678c77fcc7d3b4e3a39ac074cfa68b6` |
| `NOTICE.md` | `9bc6cf69fa566aaaf6fa5cf40397597eab8b39f497de61728da7bcf0930db207` |
| `reference/adapt.md` | `49eb1dd0476f34535f683e26cd7f03465f5fbddb04aa92c9850c4fbfcc7eeedc` |
| `reference/colorize.md` | `06652c3b1b84177445eb99f97e0be3450c3219d8d704ba0382fb48b13ad5c1d9` |
| `reference/craft-floor.md` | `b7c0e1c409f36d0ad4fc0d63110d515bee00c27b8c371e3f936a13c41457cc5c` |
| `reference/distill.md` | `3cfd0f9156156cb4fe638c0f6cdf709e0b556c6601a9ad0f0548d4282853448a` |
| `reference/harden.md` | `9cd1b559e1351da080c917101601c4db96c5c69dcea1c93a0fd18d1b5a06fa1e` |
| `reference/layout.md` | `75900f58bebc9eafa67ec4bc875b3d5e9cf595b72a5c1a3d43b6288e5e323482` |
| `reference/mode-operate.md` | `7cc131b41dae694a4b554c940445117318f0c6fb19f905cf1f8cbafc08a3f430` |
| `reference/operate.md` | `c4b169ab7932329c833750971c53bc129d0385e16d0219b31f002792fce939e8` |
| `reference/polish.md` | `4d7d4fbc0515241e737a446f5940f3f7f5b3d491387370ea858c63aebfb28cc9` |
| `reference/quieter.md` | `fa0324b2666179bf325f9d737e7239e119fd655783670f1e9a634a2fa48762b9` |
| `reference/typeset.md` | `a4661269fc0d5831f25fcbd463c47700c62732449b7274861f0473a2a77f2bae` |

To update, repeat the review and get Khalid's yes for the new commit.

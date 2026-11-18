# Brand

## Name

**AI Revenue Analyst** — always in full in titles and the UI header. In prose,
"the analyst" is fine. Never "bot", "assistant" or "AI pricing engine".

## Positioning

An open-source revenue analyst for short-term rentals and small hotels:
answers in plain language, backed by numbers the user can trust, and never
changes a price without a human saying yes.

Three promises, in this order:

1. **Every number is real.** Figures come from deterministic tools, never
   from the model's head.
2. **The human decides.** Rate changes are proposals until approved.
3. **Plain language.** Occupancy, ADR, RevPAR and pace explained like a
   friend who knows the numbers, not like a dashboard.

## Voice

Simple, direct and warm — talk *to* the host. Inspired by friendly consumer
fintech, never imitating any company's copy.

- Second person, verdict first: "You're ahead", "You're behind", "Sold out.
  Nothing to do here."
- Then the numbers that back it, in one line: "30% booked vs 24% last year by
  now."
- Everyday words over jargon: "booked so far", "last year by now", "similar
  nights" — keep ADR/RevPAR only where the user expects them.
- Say what we don't know: "Too early to tell" beats a guess. On-the-books is
  not a forecast.
- Calm, no hype, no exclamation marks, no emoji in product copy.
- Percentages for occupancy and shares; whole dollars in the UI (`$655`).

## Visual identity

Clean and light, purple-led. **Show less, lose nothing**: the calendar shows
only what needs a glance; everything else is one click away in the day card.

| Token | Value | Use |
|---|---|---|
| `--accent` | `#6b1fc4` | Brand, primary buttons, selection, current month |
| `--accent-strong` | `#4b148f` | Sold-out nights, "good" insight |
| `--accent-soft` | `#f6f0fd` | Selected/toggled backgrounds |
| `--ink` / `--ink-2` / `--ink-3` | `#1f1430` / `#4e4560` / `#6a627a` | Text |
| `--bg` / `--card` | `#faf9fc` / `#ffffff` | Page / cards |
| `--fill-0…4` | white → `#f6f0fd` → `#ebe0fa` → `#dfccf6` → `#4b148f` | How booked a night is |
| `--event` | `#f2b705` | Holiday or event (line on the cell, note in the card) |
| `--attention` | `#c2410c` (text `#7a2a00`) | Behind / nobody can check in |
| `--good-ink` | `#0a4a8c` | On track |
| Deep mode | `#2a1650` | The chat header turns deep ink purple when the deep agent is on |

The source of truth is `frontend/src/styles.css`; change tokens there, then
here.

**Typography:** Plus Jakarta Sans 400–800, 14px base; 800 for headings,
prices and key numbers.

**Shape:** rounded — cards 24px, cells 14px, buttons and pills fully round.
Touch targets ≥ 44px.

## Rules

- Purple marks the brand and selection; yellow means event; orange means
  attention; blue means on track. Colours that must be told apart also
  differ in lightness and always come with words (or an aria-label).
- Deep mode must always look different from the standard chat.
- Don't show a number in the UI that the API didn't return.
- No stock "AI" imagery (robots, sparkles, brains), no gradient washes.
- Use our own name, mark and palette — never another company's logo, font or
  exact identity.

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
   colleague would, not like a dashboard.

## Voice

- Lead with the answer, then the supporting numbers (this is also the agent's
  system-prompt rule).
- Concrete over clever: "20% on the books vs 17% at the same lead time last
  year", not "pacing looks strong".
- Calm and factual. No hype, no exclamation marks, no emoji in product copy.
- Say what we don't know: on-the-books is not a forecast, and we say so.
- Percentages for occupancy and shares; currency with the symbol (`$317`),
  no decimals unless they matter (`$317.44` ADR is fine).

## Visual identity

Light, quiet, data-first. Colour marks meaning, not decoration.

| Token | Value | Use |
|---|---|---|
| `--accent` | `#0e6b53` (deep green) | Primary actions, selected state, "sold" in the calendar |
| `--accent-soft` | `rgba(14,107,83,.1)` | Selected backgrounds, chips |
| `--ink` | `#20242a` | Body text |
| `--ink-2` / `--ink-3` | `#566069` / `#6b7378` | Secondary / tertiary text |
| `--line` / `--line-soft` | `#e4e7e5` / `#eef0ee` | Borders, dividers |
| `--bg` | `#f4f5f4` | App background (cards are white) |
| `--warn` | `#9a3412` | Weak pace, problems needing attention |
| Deep mode accent | `#9c5f0a` on `#fffdf9` | The whole chat panel re-themes amber when the deep agent is on |

The source of truth is `frontend/src/styles.css`; change tokens there, then
here.

**Typography:** Inter 400/500/600 for UI and body (14px base); Space Grotesk
500/600 for headings and KPI figures.

**Mode signalling:** Deep mode must always look different (amber) from the
standard chat (green) so users know a slower, delegating agent is working.

## Don'ts

- No stock "AI" imagery (robots, sparkles, brains).
- No red/green-only signalling — pair colour with text ("behind", "ahead").
- Don't show a number in the UI that the API didn't return.

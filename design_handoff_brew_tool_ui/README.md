# Handoff: Warblers Meadery brew_tool UI

## Overview

Three screens for a one-person meadery's operations tool: a **Today** triage
page, a **batch detail** page with a fermentation ledger, and a **Design &
must** page (recipe calculator → must-day bench sheet → record the pitch).

The owner's stated problem: past applications made paper feel easier. So the
design's whole thesis is *one number in, everything else derived*: the
operator types a gravity and the app produces ABV, attenuation, the drop
since last time, and — critically — what to do next. No status fields to keep
up to date, no re-typing anything the app can compute.

## About the design files

`Warblers Brew.dc.html` in this bundle is a **design reference created in
HTML** — a prototype showing intended look and behavior. It is not production
code to copy. Its JavaScript reimplements the app's Python math purely so the
prototype can be interactive.

**The target codebase already exists**: `brew_tool`, a stdlib-only Python
app (`brew/` — `server.py`, `calc.py`, `html.py`, `sheet.py`, `store.py`,
`views_*.py`), server-rendered with `http.server`, JSON files on disk, run
with `python3 -m brew`. Implement these designs **there, in that
environment** — do not introduce React, a build step, npm, or a client-side
framework. Its own `docs/DESIGN.md` §7 permits exactly one inline vanilla
script (a debounced form auto-submit on the Design page) and forbids
arithmetic in JavaScript. Honor that: every number on screen is rendered
server-side from `brew/calc.py`.

Read `docs/BRIEF.md` and `docs/DESIGN.md` in that repo before writing code.
Where this README and those documents disagree, **those documents and
`tests/` win** — they pin the rounding boundaries.

## Fidelity

**High-fidelity.** Final colors, type, spacing and copy. Recreate precisely,
using the app's existing HTML vocabulary (`card`, `kv`, `pill`, `table`,
`details.sec`, `msg`, `ol.steps`, `field`, `select`, `textarea`) rather than
new parallel classes.

## Scope warning — read this first

`docs/DESIGN.md` §9 puts three things in this bundle **out of scope for round
1**: the dashboard, the reading log (`readings[]` on a batch), and any feed
tick state. The Design & must screen is in scope today; Today and batch
detail are a round-2 design the owner asked to see. Confirm with the owner
before implementing them — they require a data-model decision (adding
`readings[]` to `data/batches/<id>.json`), not just views.

Safe to do now, in this order:

1. Restyle (see `port/PORTING.md`) — pure CSS, no data change.
2. The Design & must layout refinements — existing views.
3. Today + batch detail — only after `readings[]` is agreed.

---

## Design tokens

From the Organic design system; the full stylesheet is bundled as
`organic-styles.css`, and `port/html_organic.py` already carries these as
the app's inlined `CSS`.

### Color

| Token | Hex | Use |
| --- | --- | --- |
| bg | `#f5ead8` | page ground (warm cream) |
| surface | `#ebddc5` | input fills, header bar |
| card | `#fff2eb` | card fill |
| text | `#201e1d` | body ink |
| muted | `#645c50` | labels, notes, formula lines |
| divider | `rgba(32,30,29,.16)` | table header rule, input border |
| row rule | `rgba(32,30,29,.08)` | table body rules, kv rules |
| accent | `#c67139` | primary action, active nav, "due" state |
| accent-600 | `#b2622d` | primary hover |
| accent-700 | `#8c491a` | primary active; accent-colored body text |
| accent-100 | `#fff2eb` | attention card fill |
| accent-200 | `#ffe1d0` | warning banner fill |
| accent-800 | `#643312` | text on accent-100/200 |
| accent-2 (sage) | `#7a8a5e` | second voice |
| sage-100 | `#f0fae1` | "outlook" card fill |
| sage-200 | `#e1eecc` | success banner fill, step circles |
| sage-600 | `#728157` | chart line |
| sage-800 | `#3d472b` | text on sage fills |
| neutral-100 | `#f9f4ed` | neutral tag fill |
| neutral-800 | `#474238` | neutral tag text |

Accent-on-cream is tuned to ~3:1 — fine for chrome, icons and large text.
For paragraph-size accent text use `#8c491a` (accent-700), never `#c67139`.

### Type

- Headings: **Caprasimo** 400 (fallback Georgia, serif), line-height 1.12,
  letter-spacing −0.015em.
- Body: **Figtree** 400/600/700 (fallback system-ui), 16px/1.55.
- Scale in use: h1 38px · h2 23px · card h2 19–21px · body 15px · secondary
  13.5px · notes/formulas 12.5px · uppercase eyebrows 11–12px with
  0.06–0.1em tracking.
- Numbers that matter (gravity, honey weight, step values) are set in
  Caprasimo at 19–28px — the display face carries the data, not bold body.

### Spacing, radius, elevation

- Spacing scale: 4.4 / 8.8 / 13.2 / 17.6 / 26.4 / 35.2px. Page padding 34px
  (26px in the ported Python), card padding 20–26px, grid gaps 16–24px.
- Radius: cards and panels **28–32px**; buttons, inputs, tags and summaries
  **999px** (pills); inner panels 20–22px.
- Elevation: `0 1px 2px rgba(46,43,37,.14)` (sm) on cards. No borders on
  cards — shadow only.
- Minimum touch target 44px on every control (cellar, wet hands, phone).

### Interaction states

Hover tints from the ramp, pressed one step further (`accent-600` →
`accent-700`), focus ring `2px solid #c67139` with 2px offset. Never a
browser-default focus ring. Disabled: 45% opacity.

---

## Screen 1 — Today (triage)

**Purpose:** in one look, know what needs doing and log a gravity without
opening anything.

**Layout:** single column, max-width 1240px, page padding 34px.

1. **Header** — `h1` "Thursday, September 4" (38px Caprasimo) with an accent
   tag "7 going" baseline-aligned beside it; one muted lede line beneath,
   max-width 640px.
2. **"Needs you now"** — `h2` 22px, then a responsive grid
   (`repeat(auto-fit, minmax(310px, 1fr))`, gap 16px) of attention cards.
   Card: fill `#fff2eb`, radius 32px, padding 20px 22px, shadow sm. Inside:
   10px uppercase accent kicker (0.1em tracking) · 19px Caprasimo title ·
   13.5px body at 75% opacity · a primary pill button plus the batch id in
   11.5px muted. One card per blocking condition — feeding due today, a stuck
   ferment, a reading gone stale.
3. **"In the cellar"** — `h2` 22px with a muted 12.5px aside ("type a gravity
   on any row — the app does the rest"), then one card (padding 6px 14px
   10px) wrapping a full-width table, 14.5px.

**Table columns** (fixed widths as given; the "Next thing" column takes the
remainder): Batch 96 · What it is 236 · Day 50 · Gravity 96 · Trend 92 ·
Next thing (flex) · Log a reading 178.

- **Batch** — the id as an accent underlined link-button.
- **What it is** — 14.5px name over an 11.5px muted sub
  ("6 gal · orange blossom · 71B"). Both `white-space: nowrap`.
- **Day** — whole days since pitch.
- **Gravity** — 16px Caprasimo value over an 11px muted line ("read today" /
  "day 11" / "OG 1.076 planned").
- **Trend** — an 86×26 inline SVG polyline, `#728157`, 2px, round caps: the
  batch's readings normalized to the plot. Server-render this from the
  readings; it is plain SVG, no script.
- **Next thing** — a state tag (see below) over a 12px muted derived
  sentence.
- **Log a reading** — for a pitched batch, a 38px pill input
  (`placeholder="1.0__"`, `inputmode="decimal"`, centered) plus a secondary
  "Log" button (`flex:none; white-space:nowrap`). For a **not-yet-pitched**
  batch, no input at all — a single secondary "Make must" button that opens
  the design page prefilled with that batch's volume, strength and strain.
4. **Footer note**, 12.5px muted: "Nothing here is a status you have to keep
   up to date — every line is derived from the readings and the pitch date."

**State tags:** `pill.warn` (accent-100/800) for anything needing action —
Feed due, Stalled, Slowing, Reading is old; `pill.ok` (sage-100/800) for
Ready to bottle, Nearly dry, Quiet; neutral for planned batches.

---

## Screen 2 — Batch detail

**Purpose:** everything about one batch on one page — log a reading, see the
math, see the feeding schedule, never navigate to log.

**Layout:** "← Today" back link, then:

1. **Identity row** (flex, wrap, gap 20px): left — 12px uppercase accent
   batch id, `h1` 38px name, then a row of tags (volume · strain · "pitched
   Thu Aug 20, 3:00 pm" · state). Right — a `#ebddc5` strip, radius 28px,
   padding 16px 22px, four stats each an 11px uppercase muted label over a
   28px Caprasimo value: **Now** (gravity) · **ABV so far** · **Attenuated**
   · **Day**.
2. **Next banner** — full-width `#fff2eb`, radius 28px, padding 18px 22px,
   flex: the word "Next" in 15px Caprasimo accent-800, the derived sentence
   at 15.5px, and a primary "Log a reading" button that focuses the entry
   field. This sentence is the product. See *Derived next-action* below.
3. **Two columns**, `minmax(0,1.55fr) minmax(300px,1fr)`, gap 24px, items
   start-aligned.

**Left column**

- **"The log"** card. Header row: `h2` 21px + a segmented control (Organic
  `.seg` / `.seg-opt`, pill, accent fill when checked) switching
  **Ledger / Curve**.
- **Entry row** — a tinted panel (`color-mix(#c67139 9%, transparent)`,
  radius 22px, padding 14px 16px), flex end-aligned, gap 8px: Gravity (118px,
  16px centered) · Sample °F (96px) · Note (flex) · primary "Log it"
  (`flex:none; white-space:nowrap`). Enter submits from any field.
- **Result banner** (after a log) — sage-100 fill, radius 20px, 14px.
- **Ledger table** — columns When 132 (nowrap, "Fri Sep 4, 9:20 am") · Day 44
  · Gravity 76 (15px Caprasimo) · Drop 62 · ABV 58 · Att. 64 · Note (flex,
  12.5px muted). Footnote: "Drop, ABV and attenuation are never typed — one
  gravity in, three columns out."
- **Curve view** — a 620×250 inline SVG: horizontal grid lines at OG, ⅔, ⅓
  and 1.000 with 10.5px muted labels at x=40 (anchor end); a dashed accent
  line at the ⅓ sugar break labeled "1/3 break · SG 1.069"; the reading
  polyline in `#728157` 2.5px; 4px open circles (bg fill, sage-700 stroke) at
  each reading; the newest value labeled in 13px Caprasimo; feed additions as
  2px accent ticks below the axis (y 214→226) with "#1…#4" labels at y 242.
  **X domain must span pitch → last scheduled feed at minimum** (`max(7,
  lastReadingDay)`) or a one-reading batch collapses to a single point.
  Flip the value label to `text-anchor: start` when the point is within
  120px of the left edge.
- **"Must day, kept"** card — a 150px/1fr grid of label/value rows: Gravity
  in, Honey, Water, Yeast, Go-Ferm, Target, each with the formula or
  assumption beneath in 12px muted. **The honey and water here are what was
  weighed — derived from the design target OG, never from the measured
  reading** (otherwise the "18.29 lb in 6 gal should read about 1.1067 —
  lower than that and the honey ran light or wasn't mixed in yet" line
  compares a number to itself). Footer: the JSON path, "prints clean for the
  barrel".

**Right column**

- **Feeding card** — `h2` "Feeding — Fermaid O, sized from OG 1.104", then one
  row per addition: a 19px checkbox (accent), the grams in 15px Caprasimo over
  a 12.5px muted when-line ("24 h — Fri Sep 4, 3:40 pm, or the 1/3 break if
  sooner"; the last row "by Thu Sep 10 or SG 1.069, whichever comes first"),
  and a state tag (in / due / waiting). Footer: "Stop at SG 1.069 whatever the
  calendar says. Nothing after this: late nitrogen feeds the wrong things."
- **"What this is heading for"** — sage-100 card: If it goes dry · Points left
  to 1.000 · Nitrogen stops at · Fermaid O total.
- **"Other batches"** — compact list of id · name · current gravity, each row
  a full-width button to that batch.

---

## Screen 3 — Design & must

**Purpose:** two numbers in, the whole bench sheet out; then the must-day
sheet, the hydrometer check, and the one write.

**Layout:** `h1` "Design a recipe", a lede, then two columns
`minmax(300px,.85fr) minmax(0,1.15fr)`, gap 24px.

**Left — Targets card** (padding 22px, gap 16px)

Batch volume (gal, 42px input, hint "Your carboys: 5, 6, 6.8.") · Target
strength (% ABV, hint "If it ferments dry (FG 1.000). A sweet finish means
less alcohol, not less honey.") · Yeast as a row of pill radio tags (71B,
D47, QA23, EC-1118, K1V-1116; accent fill when selected) · Nitrogen demand as
a segmented control (low/medium/high) · Fermaid O feedings (88px centered
input, hint "TOSNA is 4: 24 h, 48 h, 72 h, then by the 1/3 break.").

Below it, a **"Keep it as a recipe"** card: Name, Honey (hint naming stock on
hand), and a full-width primary "Save recipe".

**Right — bench sheet card** (padding 24px)

`h2` "At 6 gal you'll need" with an accent tag "OG 1.1067" beside it, then a
158px/1fr grid of ten rows. Each row: 13.5px muted label; value in 19px
Caprasimo; an optional 13px muted qualifier inline; and the formula beneath in
12px muted. Rows and their exact copy:

| Label | Value | Formula / assumption |
| --- | --- | --- |
| OG | 1.1067 | `1.000 + 14.0 ÷ 131.25` |
| Honey | 18.29 lb (18 lb 5 oz) · 3.05 lb/gal | `106.7 points × 6 gal ÷ 35 pts per lb per gal — a planning figure; the hydrometer has the last word` |
| Honey's own room | ~1.52 gal | `18.29 ÷ 12 lb per gal` |
| Water | 4.48 gal (17.0 L) · then top to the 6 gal mark | `6 − 1.52; the mark is the truth, this is where to start` |
| Yeast | 10 g 71B · (2 sachets) | `2 g per gal above 1.100 = 12 g, to the nearest 5 g sachet` |
| Go-Ferm | 12.5 g in 250 mL at 104 °F | `1.25 g per g of yeast; 20 mL per g Go-Ferm. Twenty minutes, then temper with must until it's within 10 °F before they meet` |
| YAN | 175 ppm | `12.5 ppm per % ABV (medium demand) × 14.0` |
| Fermaid O | 26.2 g · as 4 × 6.6 g | `175 ÷ 40 ppm per g per gal × 6 gal; at 24 h, 48 h, 72 h, last by day 7 or the 1/3 break` |
| Stop nitrogen at | SG 1.071 | `OG − (OG − FG) ÷ 3 — nothing after this: late nitrogen feeds the wrong things` |
| Expect | 14.0 % if it finishes at 1.000 | `(OG − FG) × 131.25; the estimate drifts high above ~14 %` |

Tolerance warning beneath, in an accent-200 panel: "71B is rated about 14 %.
A 14.0 % target leaves it no margin — good nutrients and a cool cellar get it
there, and it may finish a touch sweet. 13 % is comfortable."

**Must-day card** — `h2` "Must day, in floor order" with a sage tag
"6 gal · next id B-2026-009", then five steps. Each: a 30px sage-200 circle
with the number in 14px Caprasimo, a 13px uppercase muted title, a 21px
Caprasimo value, and a 13px muted note. Honey · Water · Read it · Rehydrate
and pitch · Feed — copy verbatim from `views_must.steps()`.

Then the **"Read it"** panel (accent 9% tint, radius 24px): Hydrometer 130px ·
Sample °F 112px · pH 96px · Hydrometer cal. °F 132px · primary "Check". The
verdict renders beneath in accent-200 (needs action) or sage-200 (fine), one
`<p>` per line at 14.5px/1.55. Note: "The check writes nothing — re-read as
many times as you like. Recording the pitch is the only write."

Finally a 46px primary **"Record the must & start the clock"** with a 12.5px
muted aside naming what it writes.

---

## Interactions & behavior

All of these are POST → redirect → banner in the target app; the prototype
does them client-side only to be demonstrable.

1. **Nav** — three links; the current one carries a 2px accent underline **on
   the button itself** and accent ink. A "New recipe" primary button resets
   the design form to defaults (6 gal, 12 %, 71B, medium, 4) and clears any
   check — distinct from the tab, which returns you to work in progress.
2. **Log a gravity** (dashboard row or batch entry row; Enter or button):
   correct for temperature, append the reading, land on the batch page with a
   banner stating the derived figures, and clear the field.
3. **Hydrometer check** (Design & must): a GET that writes nothing and can be
   re-run; returns the verdict lines.
4. **Record the must**: writes the batch (corrected OG, pH, what went in,
   pitch time, the schedule dated from the pitch and sized from the
   **measured** OG), then lands on that batch's page with the pinned banner —
   "Recorded B-2026-009 — 6 gal, OG 1.1029, pH 3.9, 10 g 71B pitched at
   9:20 am. First Fermaid O 6.3 g Sat Sep 5, 9:20 am; stop at SG 1.069."
5. **Feed tick** — toggles that addition's done state.
6. **Ledger / Curve** toggle.
7. **Make must** on a planned row — opens the design page prefilled.

### Derived next-action (the important logic)

Never store this sentence; compute it from the log on every render, in this
order:

1. A feeding open and due **today or earlier** (compare against end of the
   current calendar day, not "now") → name it: "Fermaid O #1, 6.3 g — due Fri
   Sep 4, 3:40 pm. Stop at SG 1.069."
2. A feeding still open with no movement to report (single reading, or read
   today) → "Pitched today at 1.1029. Next up: Fermaid O #1, 6.3 g Sat Sep 5,
   9:20 am."
3. Gravity **higher** than last time (rise > 0.5 pt) → "1.034 — it reads 4
   points higher than last time. Stir it and re-read, or check the sample
   temperature: a rising gravity is usually the glass, not the mead."
4. ≤1 point of movement over **a day or more**, still well above FG →
   "Stuck at 1.030 — no movement in 2 days. Nitrogen is done, so warm it and
   rouse it, then read again in 24 h."
5. At or below FG+0.004 → "1.001 and steady at 12.7 % — taste it, then rack
   it off the lees."
6. Last reading ≥7 days old → "Last read 11 days ago at 1.020. One gravity
   says whether it is finished or stuck."
7. Otherwise → "Last read 4 days ago at 1.041 — 6 points down in 2 days.
   Worth another this week." Read today with movement → "Still moving — next
   reading in a couple of days"; read today with none → "Give it a day before
   the next reading."

Never assert movement without two readings to compare.

---

## State

Server-side; nothing lives in the browser.

- `data/recipes/<slug>.json` — inputs plus a `computed` block (unchanged from
  round 1; the app never reads `computed`).
- `data/batches/<id>.json` — round 1's shape, **plus** (round 2 only, and
  only once agreed) a `readings[]` of `{at, reading, sample_f, cal_f, sg,
  note}` and per-addition done flags. Store the *timestamp*, not a whole-day
  offset: two readings the same afternoon must be distinguishable, otherwise
  the copy says "0 days" and duplicate times.
- Query-string state only for views: `gal`, `abv`, `og`, `fg`, `yeast`,
  `demand`, `additions`, `reading`, `temp_f`, `cal_f`, `ph`.

## Number formatting (get these exactly right)

- Gravity: **always at least 3 decimals** (1.030, 1.020), keeping a
  significant fourth (1.1029). Stripping to "1.03" is wrong.
- ABV: always 1 decimal ("1.0 %", not "1 %").
- Rounding must match Python's `round()` — half-to-even, and the .5 test must
  be **exact**, not an epsilon window (`169 ÷ 40 × 6 = 25.349999…` must give
  25.3, not 25.4, or the feed grams disagree with the schedule).
- Honey: "18.29 lb (18 lb 5 oz)"; under a pound "0.87 lb (14 oz)".
- Volume: "4.48 gal (17.0 L)" — the litre figure keeps its decimal.
- Points 1 dp, grams 1 dp, mL whole, ppm whole.

## Assets

- `organic-styles.css` — the design system stylesheet (tokens + component
  classes) the design was built from.
- Fonts: Caprasimo and Figtree (Google Fonts). Vendor them for offline use.
- The header warbler mark in `port/html_organic.py` is a **placeholder**.
  Replace it with the meadery's real logo; do not treat it as brand.
- No photography. Charts and sparklines are hand-written inline SVG.

## Files in this bundle

| File | What it is |
| --- | --- |
| `Warblers Brew.dc.html` | the interactive design reference — open in a browser; all three screens, with the math reimplemented in JS for the prototype only |
| `port/html_organic.py` | drop-in `CSS`, `page()`, `FONTS`, `BRAND_MARK` for `brew/html.py` — the restyle, ready to paste |
| `port/PORTING.md` | exactly what to paste where, plus the one `sheet.py` markup change |
| `organic-styles.css` | the design system's own stylesheet, for token reference |
| `screens/01-today.png` | Today — header, attention cards |
| `screens/02-batch-detail.png` | Batch detail — identity strip, next banner, log entry, feeding |
| `screens/03-design-and-must.png` | Design & must — targets form and bench sheet |

The screenshots are viewport captures (924px wide) showing the top of each
screen — the design is built for ~1240px desktop. For anything below the
fold (the cellar table, the ledger and curve, the five must-day steps, the
hydrometer check), open `Warblers Brew.dc.html` in a browser and scroll: it
is the authoritative reference.

Start with `port/PORTING.md`: it is the whole of step 1 and touches no data.

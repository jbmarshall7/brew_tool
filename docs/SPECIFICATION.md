# brew_tool — forward specification

**Version:** 1.0 · **Date:** 2026-09-06 · **Owner:** JK (Warblers Meadery)

This is the roadmap, not a plan of record. It reads the full capability surface
of the old app — `meadery_tools`, ~31,000 lines that tried to be an inventory,
traceability, finance, tax and compliance system at once — and lays out which
of those capabilities belong in `brew_tool`, in what order, and in what shape.

The old app is not the enemy here. It *worked*, and it proved what a licensed
meadery actually needs to record. What it got wrong was doing all of it before
any of it was pleasant to use, so the owner reached for a notebook instead.
This document exists so that never happens again: it is a **menu the owner
pulls from one dish at a time**, each item specified well enough to build in a
single round, and each carrying an honest verdict on whether it earns its place
for a one-person cellar.

If this document ever grows a "build all of section 5" instruction, it has
failed the same way the old spec did. Pull one item. Use it for a real batch.
Decide the next from that.

---

## 1. The constitution

Every capability below is bound by the seven rules `brew_tool` has held since
round 1. A candidate that cannot be expressed within them is deferred, not
smuggled in.

1. **Derived, never tracked.** If a number can be computed from what already
   happened, it is computed on render — the drop since last reading, the ABV so
   far, what to do next. The app holds no status field for the operator to keep
   up to date. A "status" the human maintains is a status the human forgets.

2. **Events, append-only.** The things only the human knows — a gravity, a
   feeding given, a racking, a dose — are recorded as timestamped events and
   never edited. A mistake is a new entry, not an overwrite.

3. **One file per record.** A recipe is a file; a batch is a file. No index, no
   database. The directory listing is the index. `git` is the audit trail and
   the backup.

4. **It refuses the dangerous thing.** The app will not dose sulfite into a
   working ferment, will not let sorbate go in without it, will not sweeten
   before stabilizing. Every refusal states its reason and is overridable only
   with a recorded one. The tool teaches the craft by declining to help you
   ruin a batch.

5. **It previews before it meters.** Anything that puts a real substance into
   the mead — a nutrient dose, a sulfite dose, back-sweetening honey — shows
   the amount first through a read-only path that writes nothing. Recording is
   a separate, deliberate act.

6. **Built for the cellar.** One person, wet hands, a phone on a barrel. The
   daily job is one page load. Touch targets are real; the page prints clean
   for the wall. Stdlib-only Python, server-rendered, no build step, no
   client-side framework, and no arithmetic in the browser.

7. **It earns its place.** A feature ships only if it makes a single batch go
   better, or answers a question the owner actually asks mid-task ("how much
   orange blossom is left", "when is the fermenter free"). "A real business
   would track this" is not that test — a spreadsheet and an accountant already
   track a great deal, better.

---

## 2. What is already built

`brew_tool` today (rounds 1–3) covers the spine of making a batch:

| Area | State |
|---|---|
| **Recipe design** | Two numbers in (volume, strength) → the full bench sheet, every figure showing its formula. Saved recipes, reusable at any volume. Yeast in whole sachets, derived. |
| **Must prep** | The recipe scaled to a carboy in floor order; a hydrometer check that corrects for temperature and says exactly what to stir in; the pitch recorded with a dated Fermaid O schedule sized from the *measured* OG. |
| **Fermentation** | A gravity in, three columns out (drop, ABV, attenuation). One sentence saying what to do next, from seven ordered rules. A feed log so that sentence tells the truth. A server-drawn gravity curve. |
| **Finishing** | Rack, stabilize (pH-dosed sulfite + sorbate, refusing a working ferment), back-sweeten (gated on stabilizing), bottle. |
| **Today** | The front door: what wants you, then every batch with a gravity field on each row. |

The math module (`brew/calc.py`) carries the old repo's hand-checked constants
verbatim, plus its own, each pinned by a test. 161 tests, green on Python 3.9
through 3.14.

What this does **not** yet do, that a batch itself wants: record where fruit or
oak went in, capture a tasting, version a recipe properly, or tell you which
vessel is free. Those are section 4.

---

## 3. The capability inventory (what the old app can do)

The complete surface of `meadery_tools`, grouped, so nothing is invented from
scratch below — every future round is a re-expression of something already
proven, not a guess.

### 3.1 Production
- Versioned recipes (new versions with changelogs, never edited once a batch
  used them; batches pin the exact version).
- Batch lifecycle: planned → must-prep → fermenting → aging → stabilizing →
  packaged → archived, with a `stuck` substate.
- Must preparation, readings with SG/temperature charting, nutrient scheduling,
  additions of every kind (fruit, spice, oak, acid, fining) each against an
  inventory lot.
- Packaging into product lots; loss reconciliation.
- Calculators: ABV, honey, YAN/nutrient, sulfite, hydrometer correction,
  back-sweetening, **fruit gravity contribution**, yeast pitch.

### 3.2 Inventory & traceability
- Ingredient lots, consumable lots, equipment, finished product — each with an
  internal lot ID assigned at receiving, movements (received/used/adjusted/
  disposed), on-hand recomputed from history.
- Suppliers (approved-only receiving), quarantine-on-arrival, reorder points.
- Equipment with maintenance logs, instrument calibration (overdue tracker),
  and a drag-and-drop facility layout.
- Sanitation log tied to vessels.
- **Two-sided consumption**: every addition to a batch decrements its lot in
  the same write.
- **Forward and back traceability**: lot → batches → product → market, and
  product → sources; a visual trace-map graph; mock-recall drills.

### 3.3 Compliance
- Document vault (permits, COAs, SDS, lab results) with expiry and renewal
  surfacing, retention dates, archive-never-delete.
- Product labels versioned with a mandatory-element checklist; COLA/formula
  approvals; QA release blocked on declaration/approval gaps, overridable with
  a reason.
- QR label sheets for every physical thing; a scan page resolving codes to
  records.

### 3.4 Finance
- Categorized single-entry ledger against a chart of accounts; expenses
  allocable to a batch or product lot; pricing per product × channel with
  effective dates; revenue captured from dispositions at the effective price.
- Derived P&L, COGS snapshot per product lot at QA release, margin by product
  and channel, inventory valued at cost. CSV exports.

### 3.5 Tax
- Federal excise from removals (wine gallons × dated rates), the CBMA
  small-producer credit ladder against cumulative calendar-year removals with
  tier-boundary splits.
- State excise, sales/use tax summary with nexus watch.
- A filing calendar (upcoming/due/overdue/filed/paid) and per-period worksheets
  with stated derivations. Rates are operator-maintained data with staleness
  flags.

### 3.6 TTB operations
- Aggregates a period into the Report of Wine Premises Operations (F 5120.17):
  production, bottling, taxpaid removals by class, samples, breakage, losses,
  and period-end inventories, with gap flags and a dated export.

### 3.7 App infrastructure
- Server-rendered stdlib app; validator run after every write; POST→redirect→
  banner; grouped nav; escape-by-default rendering; a guided walkthrough.
- No authentication (localhost only). `git` as history and backup.

---

## 4. The roadmap — capabilities considered for brew_tool

Ordered by leverage for a one-person meadery. Each carries: the **job** it
serves, the **data** it adds, the **derivations and guardrails** that keep it
inside the constitution, what stays **out**, and a **verdict**.

The tiers are a stance, not a schedule. **Near** = fits the philosophy cleanly
and serves a frequent job; build when the owner wants it. **Considered** = real
value but more scope or more caution. **Deferred** = only if the business
demands it, and probably better served elsewhere. **Never** = actively kept out.

---

### 4.A Near

#### A1 — Fruit, spice and oak additions (melomel / metheglin)

- **Job:** "Start a blueberry mead." The Design page can only express a
  traditional; the owner's own design mockup drew a Blueberry Melomel that the
  app cannot currently make.
- **Data:** the batch's existing `additions[]` grain gains fruit/spice/oak
  events `{at, kind, item, qty, unit, note}`. Recipes gain optional fruit lines.
- **Derivations & guardrails:** fruit adds fermentable sugar *and* volume, so
  it moves OG, ABV and the nutrient target together — the math (`fruit_points`,
  `og_with_fruit`, `fruit_sugar_pct`) is already written and hand-checked in the
  old repo, unported. A per-fruit sugar table, with an explicit percentage
  required for anything unlisted (no silent guess). Oak and spice record a
  contact-time clock; over-extraction is the one unfixable mistake, so the
  next-action sentence can watch it.
- **Out:** fruit *inventory*. You record that 10 lb of blueberries went in, not
  which lot they came from.
- **Verdict: build it.** Small, the math exists, and it is the one recipe style
  the owner has already tried to make and couldn't. Highest leverage per line.

#### A2 — Recipe versioning

- **Job:** "Why does this year's orange blossom taste different?" — answerable
  only if last year's recipe still reads as it was.
- **Data:** a recipe file keeps a `versions[]` with changelog lines rather than
  being edited in place; a batch pins the exact version it used (it already
  snapshots targets, so nothing is lost today — this makes the intent legible).
- **Derivations & guardrails:** a recipe a batch has used is never edited; a
  change is a new version needing a one-line changelog. This is exactly the old
  app's rule, and `brew_tool` already stores per-batch target snapshots, so the
  migration is additive.
- **Out:** nothing new; this tightens an existing surface.
- **Verdict: build it, small.** Cheap, and it turns the recipe page into a
  genuine record of how a mead evolved.

#### A3 — Sensory / tasting notes at checkpoints

- **Job:** capture what a batch tastes like at the moments that matter —
  post-primary, pre-stabilization, at bottling, and again in the bottle over
  time — so the recipe can actually improve.
- **Data:** a `tastings[]` on the batch, `{at, stage, aroma, flavor, verdict,
  note}`; free text plus a small structured spine (a 1–5 overall, a few tags).
- **Derivations & guardrails:** none dangerous — this is a log, not a dose. The
  batch page shows tastings on the timeline beside readings; the next-action
  sentence can prompt one at the right checkpoint ("pre-stabilization — taste
  it before you sulfite").
- **Out:** a formal sensory panel with multiple tasters and scoring rubrics.
- **Verdict: build it.** Pure upside, fits the event grain exactly, and it is
  the feedback loop that makes every future batch better.

#### A4 — A featherweight ingredient stock

This is the single most dangerous item on the roadmap, so it is specified with
the most care. Inventory-with-lots is what sank the old app; **this is not
that.**

- **Job:** the two questions the owner asks weekly — "how much orange blossom
  honey do I have?" and "am I about to run out?" — and the small convenience of
  the must-day sheet knowing the honey already exists rather than retyping it.
- **Data:** one file, `data/stock.json`, a flat list `{item, category, on_hand,
  unit, note, updated}`. That is all. No lot IDs, no supplier, no movements, no
  received dates, no COA.
- **Derivations & guardrails:** recording a must *offers* to decrement the honey
  it used, and never enforces it — a blank or absent stock line is fine, and a
  batch never fails because stock disagrees. On-hand is a number the owner sets
  and the app nudges, not a ledger the app polices. No two-sided-consumption
  invariant, no validator error, ever.
- **Out:** lots, movements, suppliers, traceability, reorder automation beyond a
  soft "low" flag on Today, and any notion that stock is authoritative. The
  moment this needs a lot ID, it has become the old app and must stop.
- **Verdict: build it, but last of the Near tier, and hold the line.** It earns
  its place because the question is real and daily. It endangers the project if
  it grows. If in doubt, don't — a note on the honey and a glance at the drum
  answers the same question.

---

### 4.B Considered

#### B1 — Vessel schedule: what is free, what is next

- **Job:** once more than one batch is going, "which fermenter is open?" and
  "when does carboy 2 come free?" — the questions a second and third batch
  create.
- **Data:** a small equipment list (`data/vessels.json`: `{id, name, gal}`) and
  a derived occupancy from which batch currently claims which vessel. The old
  app tracked `current_contents`; here it is derived from batch vessel-events
  rather than stored.
- **Derivations & guardrails:** occupancy and a projected free-date come from
  the batches themselves — a vessel is busy because a batch is in it, and free
  when that batch is bottled or racked out. No hand-maintained calendar.
- **Out:** the drag-and-drop floor plan, reservations, a Gantt board. A list
  that says "Carboy 2 — free ~Sep 20 (B-2026-004 bottling)" is the whole
  feature.
- **Verdict: build it when there are three live batches, not before.** With one
  carboy it is noise; with a full cellar it is the thing you check first.

#### B2 — Where the bottles went (dispositions)

- **Job:** the bridge from "bottled 28" to "sold 12 at the taproom, gave 6 to
  the festival, 10 left." Answers "how much is left" and is the foundation any
  compliance or sales record stands on.
- **Data:** a `dispositions[]` on the bottled batch (or a light product record):
  `{at, kind: taproom|gift|sold|breakage, qty, to, note}`, on-hand derived as
  bottled − Σ dispositions.
- **Derivations & guardrails:** on-hand is derived, never stored; a disposition
  cannot take a batch below zero. No consignee/invoice enforcement (that is a
  licensed-sales concern — see Deferred).
- **Out:** customers as records, invoicing, pricing, revenue. Just where it
  went and how much is left.
- **Verdict: build it if the owner sells or gives away enough to lose count.**
  Genuinely useful, moderate scope, clean derivation — but only pulls its weight
  once volume outruns memory.

#### B3 — QR labels and scan-to-record

- **Job:** point a phone at a carboy sticker and its batch page opens; scan a
  bottle code and it resolves. Real delight, and real use at the barrel.
- **Data:** none new — labels encode existing record URLs.
- **Derivations & guardrails:** the old app's `app/qr.py` is pure stdlib SVG,
  byte-mode QR verified against an independent decoder — it can be lifted almost
  whole, staying inside the no-dependency rule. A scan page resolves a bare id,
  a bottle code, or a full URL.
- **Out:** barcode inventory scanning, label design beyond a clean sticker.
- **Verdict: consider it — high delight, self-contained, medium scope.** Nothing
  depends on it, so it can land any time the owner wants the toy. Best after
  dispositions, so a bottle code has somewhere to resolve to.

#### B4 — TTB Report of Wine Premises Operations

- **Job:** if licensed, the periodic F 5120.17 is real work the app already has
  the data to support — production, bottling, removals, losses, period-end
  inventory.
- **Data:** none new if dispositions (B2) exist; it aggregates batches and
  dispositions over a period into the report's lines, with gap flags and a dated
  export.
- **Derivations & guardrails:** every figure derived and labelled with its
  source; makes no legal determination; supports the filing, does not submit it.
- **Out:** automated filing, tax computation (that is section 4.D).
- **Verdict: build only if JK is licensed and self-files.** High value in that
  case, near-zero otherwise. Depends on B2. Ask before scoping.

---

### 4.C Deferred — only if the business demands it

These are the old app's heavy layers. They are real, and the old app built them
competently. But each is substantial, each duplicates something a spreadsheet or
an accountant may do better, and each pulled the old app further from being
pleasant to use. Build one only when a concrete business need names it, and even
then, ask first whether the tool is the right home.

- **C1 — Finance (P&L, COGS, expenses, pricing).** A categorized single-entry
  ledger with margin and cost roll-up. Verdict: an accountant plus a spreadsheet
  serves a one-person meadery better until it doesn't. If it must live here,
  scope only the piece that touches production — COGS per batch from what
  actually went in — and leave the ledger out.
- **C2 — Tax (excise, CBMA ladder, filing calendar, sales-tax nexus).** Heavy,
  jurisdiction-specific, and worksheet-only by design (it never files). Verdict:
  defer to a tax professional unless self-filing excise becomes a routine burden
  the owner wants automated. If built, it is worksheets that state their
  derivations, never advice.
- **C3 — Compliance vault (documents, labels, approvals, COLA).** Document
  expiry surfacing has real value (a lapsed permit is a bad surprise); the full
  label-versioning and approval machinery is a lot. Verdict: if licensed, scope
  *only* the document-with-expiry surfacing first — a lightweight `documents.json`
  with renewal dates on Today — and leave labels/approvals until a product
  actually needs a COLA on file.
- **C4 — Full inventory with lots and traceability.** The old app's spine:
  every physical thing a lot, two-sided consumption, forward/back trace, mock
  recall. Verdict: this is the defining over-scope for a solo meadery and the
  reason `brew_tool` exists. Do not build it unless the meadery grows employees
  and a real recall obligation. The featherweight stock (A4) is the deliberate,
  permanent alternative.

---

### 4.D Never (kept out on principle)

Consistent with the old spec's own §1.3 out-of-scope, and the constitution:

- **No hosted or multi-tenant service, no auth, no remote exposure.** Localhost,
  one operator, `git` for sync. Authentication is a precondition for the rest,
  and none of it is wanted.
- **No accounting/GL, payroll, or POS.** Not double-entry, ever.
- **No automated regulatory filing.** The app supports filings; a human files.
- **No sensor/IoT ingestion.** A human enters the reading. (This is also what
  keeps the "derived, never tracked" rule honest — the readings are ground
  truth precisely because a person took them.)
- **No client-side framework, build step, or dependency.** Stdlib Python,
  server-rendered, one inline script at most.

---

## 5. How a round gets pulled from this menu

1. The owner names one item (or a session proposes one and the owner agrees).
2. It gets a design pass against the constitution: job walk, data shape,
   derivations, guardrails, the explicit out-of-scope, the copy in the
   cellar-mate voice.
3. The math lands first in `brew/calc.py` with pinned tests; then the store with
   its guardrails; then the views; then a browser walk of the real job.
4. It ships as one PR, green on 3.9–3.14, and `docs/DESIGN.md` gets a
   "changed after the design" note.
5. The owner uses it for a real batch before the next item is pulled.

The discipline is the point. The old app had all of section 3 and the owner
stopped using it. `brew_tool` has a third of it and the owner reaches for it on
must day. Keep it that way: **one dish at a time, and only when hungry for it.**

---

## 6. The owner's answers, and the resulting order

The five questions below were answered on 2026-09-06. They change the roadmap
from an abstract tiering into a concrete sequence, recorded here so the order is
not re-litigated every session.

### 6.1 The answers

1. **Licensed?** Yes — TTB and the State of Connecticut, and Warblers
   **self-files.** So the tax, TTB-operations and compliance-document
   capabilities are real recurring obligations, not hypothetical. The tool's
   posture is unchanged: it produces worksheets and keeps records; it never
   files and never renders a tax or legal determination.
2. **Lose count of a bottling?** Not from sales yet, but there will be
   **sampling bottles** that may account for loss — unclear whether the volume
   is material enough to report. The tool records samples as dispositions and
   lets the TTB worksheet surface them; the operator classifies, the tool does
   not decide materiality.
3. **How many batches at once?** **Two now, eight soon.** A cellar heading for
   eight makes "which vessel is free / when does it come free" a daily question
   and makes memory aids (tasting notes, recipe versions) worth having before
   the count climbs.
4. **Sparkling?** **Yes, some sessions.** This reopens the priming-sugar math
   deferred in round 3 and adds a sparkling branch to the finishing arc:
   bottle-conditioned mead is *not* stabilized, is primed with a computed sugar
   amount into pressure-rated bottles, and lands in a higher excise tax class —
   which ties back to answer 1.
5. **Is honey-on-hand weekly friction?** **No** — a glance at the drum answers
   it. So the featherweight stock (A4) stays **permanently unbuilt.** The owner
   has removed the one item most likely to drag the old app's inventory sprawl
   back in. Treated as a settled decision, not a gap.

### 6.2 The resulting order

**Progress (2026-09-11):** items 1–6 are built and merged to `main` — the whole
Near tier, vessels, dispositions, the TTB operations report and the
document-expiry surfacing. Only item 7 remains: the excise worksheets. It is the
heavy, licensed-operator remainder, best taken as its own focused session
because it needs Warblers' actual Connecticut filing cadence and rates as input.

Leverage-ordered given the answers, with dependencies respected. Still a menu —
one at a time, used on a real batch before the next — but this is the sequence
absent a reason to depart from it.

1. **Fruit, spice and oak additions** (was A1). ✓ **Shipped** (round 4). Smallest, the math already
   exists unported, no dependency, and it unblocks a style the owner has tried
   to make. Build first.
2. **Sparkling finishing branch** (from answer 4). ✓ **Shipped** (round 5). Extends
   the finishing arc already built: a bottle-conditioning path that primes
   instead of stabilizing, computes priming sugar for a target volume of CO₂,
   and flags the sparkling tax class at design — deciding carbonation early,
   because it changes the excise rate the tax worksheet will later need.
3. **Tasting notes** and **recipe versioning**. ✓ **Shipped** (round 6). Cheap memory
   and iteration aids, most valuable *before* the cellar fills to eight batches
   nobody can hold in their head.
4. **Vessel schedule** (was B1). ✓ **Shipped** (round 7). A Vessels page with
   derived occupancy — free / occupied-by, no fabricated free-by date.
5. **Dispositions, including samples** (was B2). ✓ **Shipped** (round 8). Where
   bottles and sample pours went, on-hand derived; the input to 6–7 below.
6. **TTB Report of Wine Premises Operations** (was B4). ✓ **Shipped** (round 9).
   The F 5120.17 lines derived from batches and dispositions for any period:
   produced by fermentation, bottled, removals bucketed by tax class (samples
   and breakage kept separate), losses (bulk-to-bottle + breakage), and the
   period-end inventory computed **as of the period end, not "now"** so a past
   month reads as it stood. Flags gaps (missing tax class, unpriced package)
   and writes a markdown report to `data/reports/`. Makes no legal determination
   and computes no tax.
   - **document-expiry surfacing** (the light half of C3). ✓ **Shipped** (round 10).
     A Documents page (nav "Docs") holding each permit / licence / COA / policy
     and the one fact the app can't derive — when it lapses — with days-left and
     status (expired / expiring within 60 days / current) computed on render and
     a one-field Renew that moves the date forward. Today raises a Compliance
     banner for anything expired or expiring, even with nothing fermenting, so a
     lapsed permit is a surprise the tool prevents.
7. **Excise worksheets — federal + CT, with the CBMA credit** (was C2). The
   heaviest, last, once removals data exists and the sparkling tax class is
   modelled. Worksheets that state their derivations; rates are
   operator-maintained data; it never files. Even here, keep asking whether a
   given piece is better served by the owner's accountant.

The full label / COLA / approval machinery (the heavy half of C3) and the full
lot-inventory + traceability layer (C4) remain **deferred** — build only if
distribution or employees make them unavoidable, per section 4.

---

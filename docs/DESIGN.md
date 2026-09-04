# Round 1 design — recipe design and must prep

The spec this round was built to, synthesized on 2026-09-03 from three
independent designs and a judge panel, after the owner asked for a fresh,
small rebuild of the over-scoped meadery_tools app focused on usability.

## Changed after the design

- **2026-09-04 — yeast is derived, not typed.** The owner asked why yeast
  grams were an input at all. They now come from the volume and the OG in
  whole sachets: 1 g/gal, 2 g/gal above 1.100, to the nearest 5 g sachet
  (halves round up), never fewer than one (`calc.yeast_for`). The Design
  page has no yeast-grams field, recipes don't store one, and the must-day
  record form still asks what actually went in.

Where this document and `tests/` disagree on a digit, the tests win: they
pin what `brew/calc.py` actually computes at its declared rounding
boundaries (for example 4 × 6.6 g comes from rounding the exact total,
and `expected_og(18.3, 6)` is 1.1067, not 1.1068). Section 9, "out of
scope this round", is the part to re-read before adding anything.

---

# brew_tool — final design (round 1: recipe design + must prep)

## 1. The shape

brew_tool is three server-rendered pages sharing one tested math module. **Design** (`GET /`) is a calculator that is already an answer on first load: type a batch volume and a target strength and read the whole bench sheet, every number printed with the formula and constant it came from. **Recipes** save a design under a name; a recipe stores only the targets (ABV or OG, FG, design volume, honey and yeast names, yeast grams, nutrient demand) and never a honey weight, so the owner's real mistake (18.29 lb, a 6-gal number, filed under a 5-gal basis) cannot be written. **Must** is the recipe scaled to a carboy, laid out in floor order, with one open form that takes the raw hydrometer reading, its temperature and pH and answers in cellar units: corrected OG, lb-and-oz honey to stir in or gal-and-L water to add (honey's own volume accounted for), the carry-on ABV if left alone, and a pH line. Once the yeast is in, one POST writes the only file the owner will want later — `data/batches/<id>.json` with the measured OG/pH, what went in, the pitch time, and the Fermaid O schedule dated from the pitch and sized from the *measured* OG, every row capped by the 1/3 sugar break. No status, no readings log, no lots. Stdlib `http.server`, JSON on disk, `python3 -m brew`, unittest. The only JavaScript is a six-line auto-submit on the Design page; no arithmetic ever lives in JS.

## 2. Increment plan

All of `brew/calc.py` lands in the scaffold, fully tested, so commits 1–4 are views and routes only and the numbers are pinned before any page exists.

### Commit 0 — Scaffold: runnable server, the math module, the page chrome
- **Owner can do:** `python3 -m brew` opens `http://127.0.0.1:8765/` showing a page that says "brew_tool — Design page arrives next" in the old app's paper-and-gold styling. `python3 -m unittest discover -s tests` passes with every hand-checked value from the brief and this document.
- **Routes:** `GET /` (placeholder), `GET /static.css` is *not* a route — CSS is inlined by `page()`.
- **Modules:**
  - `brew/__init__.py`
  - `brew/__main__.py` — argparse: `--port 8765`, `--data DIR` (default `<repo>/data`), `--no-open`, `--lan` (bind `0.0.0.0` and print the LAN URL from the first non-loopback IPv4; default binds `127.0.0.1`). Prints the URL, calls `webbrowser.open`, serves with `ThreadingHTTPServer`.
  - `brew/server.py` — `Handler(BaseHTTPRequestHandler)`; a `ROUTES` list of `(method, regex, view)`; views are pure functions `(params: dict, form: dict, path_args) -> Response(status, body|redirect, msg)`, testable without a socket. Helpers: `redirect(path, msg)`, `?msg=` read into a banner by `page()`. Any `ValueError` from calc renders the same page with an `.msg.err` banner and status 200; never a traceback.
  - `brew/calc.py` — the whole API in §6.
  - `brew/html.py` — `CSS` (tokens verbatim from the brief, 40 px controls, `@media print` hiding nav/forms/buttons), `page(title, body, msg=None, nav=...)`, `card(title, body)`, `kv(rows)` (label / value / `.mut` assumption cell), `pill(text, kind)`, `table(head, rows)`, `details(summary, body, cls="sec")`, `msg(text, kind)`, `next_link(href, text)`, `esc()`, `num(x, dp)`, `lb_oz(lb)`, `gal_l(gal)`.
  - `README.md` — run, test, `--lan`, where data lives.
  - `tests/test_calc.py`, `tests/test_server.py` (router dispatches, a bad param renders a banner not a 500).
- **Tests (pinned values, calc rounds at the boundaries stated in §6):** `honey_for_og(5, 1.100) == 14.29`; `honey_for_og(6, 1.1067) == 18.29`; `honey_for_og(5, 1.1067) == 15.24` (the owner's file contradiction); `og_for_abv(14) == 1.1067`; `abv(1.100, 1.000) == 13.13`; `honey_gal(18.29) == 1.52`; `water_gal(6, 18.29) == 4.48`; `yan_ppm(12, 'medium') == 150` and `nutrient_grams(150, 5, 'fermaid-o') == 18.8`, `split(18.8, 3) == 6.2`; `yan_ppm(14, 'medium') == 175`, `nutrient_grams(175, 6, 'fermaid-o') == 26.2`, `split(26.2, 4) == 6.6`; `goferm(10) == (12.5, 250)`; `third_break(1.1067, 1.000) == 1.071`; `third_break(1.1029, 1.000) == 1.069`; `hydro_correct(1.050, 77, 60) == 1.052`; `hydro_correct(1.101, 76, 60) == 1.1029`; `expected_og(18.3, 6) == 1.1068`; `correction(1.1029, 1.1067, 6)` → `{'add': 'honey', 'pts': 3.8, 'lb': 0.87, 'adds_gal': 0.07, 'carry_on_abv': 13.5}`; `correction(1.112, 1.1067, 6)` → `{'add': 'water', 'pts': 5.3, 'gal': 0.30, 'new_gal': 6.30, 'carry_on_abv': 14.7}`; `correction(1.106, 1.1067, 6)['add'] == 'none'`; `ph_verdict(3.9).kind == 'ok'`, `ph_verdict(4.4).kind == 'ok'` (text says high side), `ph_verdict(3.1).kind == 'warn'`; `tolerance_note('71B', 14)` non-empty, `tolerance_note('71B', 12) is None`, `tolerance_note('EC-1118', 14) is None`; `schedule('2026-09-03T15:40', 1.1029, 1.000, 6, 'medium', 'fermaid-o', 4)` → four rows, `g == 6.3`, due `2026-09-04T15:40`, `-05`, `-06`, then `2026-09-10T15:40`, every row `stop_sg == 1.069`, `total_g == 25.3`, `yan_ppm == 169`; `plan(gal=6, abv=14)` dict matches all of the above.

### Commit 1 — Design page (usable for B-2026-003 with a pencil)
- **Owner can do:** open `/`, see 6 gal / 12 % prefilled, type 14 and 10 g yeast, tap Recompute, and read: OG 1.107, 18.29 lb honey (18 lb 5 oz) taking 1.52 gal, water 4.48 gal (17.0 L) then top to the 6 gal mark, 10 g 71B (2 sachets), Go-Ferm 12.5 g in 250 mL at 104 °F, YAN 175 ppm → Fermaid O 26.2 g as 4 × 6.6 g at 24/48/72 h and by SG 1.071, 14.0 % if dry, and the 71B warning. The URL is bookmarkable. Nothing is saved.
- **Routes:** `GET /` (params `gal, abv, og, fg, yeast, yeast_g, demand, additions`; defaults 6, 12, blank, 1.000, 71B, 1 g/gal × gal, medium, 4).
- **Modules:** `brew/sheet.py` (`render_sheet(plan) -> html`: the kv card every later page reuses), `brew/views_design.py`, `tests/test_views.py`.
- **Tests:** render for `gal=6&abv=14&yeast_g=10` contains `18.29 lb`, `4.48 gal`, `12.5 g Go-Ferm`, `1.071`, `35 pts per lb per gal`; `og=1.1067` with `abv` blank yields the same sheet and the hint "strength set by OG"; `gal=abc` renders the form with an `.msg.err` banner and status 200; every `<input>`/`<button>` carries the 40 px classes.

### Commit 2 — Save as recipe, recipe list, recipe page, auto-recompute
- **Owner can do:** under the sheet, type name and honey, Save → lands on `/recipes/orange-blossom-traditional` with a banner and a "Make must →" link. `/recipes` lists recipes. "Redesign" reopens `/` prefilled; Save becomes "Save changes to Orange Blossom Traditional". Changing any Design input recomputes without tapping Recompute (JS present) or after one tap (JS absent).
- **Routes:** `GET /` (+ `recipe=<slug>` prefill; save form appears under the sheet), `POST /recipes` → `303 /recipes/<slug>?msg=`, `GET /recipes`, `GET /recipes/<slug>?gal=N`.
- **Modules:** `brew/store.py` (`DATA_DIR`, `slugify`, `write_json` atomic tmp+rename with `indent=2, sort_keys=True`, `load_recipe`, `save_recipe`, `list_recipes`, `honey_names`, `yeast_names`), `brew/views_recipes.py`, `brew/html.py` (+ `datalist`, the inline script), `data/recipes/.gitkeep`, `tests/test_recipes.py` (uses `--data` via `BREW_DATA` env override pointing at a temp dir).
- **Tests:** `slugify('Orange Blossom Traditional') == 'orange-blossom-traditional'`; save → load round-trips byte-stable; the saved file has no `honey_lb`/`og` key outside `computed`; `computed` equals a fresh `plan()` from the file's inputs; POST with a colliding name and no `from_slug` writes nothing and redirects with the refusal banner; POST with `from_slug` overwrites; `/recipes/<slug>?gal=5` renders `15.24 lb`; the inline script contains no `fetch`, `import`, `src`, or digit arithmetic (guardrail regex).

### Commit 3 — Must page with the OG/pH check (writes nothing)
- **Owner can do:** from `/recipes` tap "Make must" (gal prefilled 6) → `/recipes/<slug>/must?gal=6`: the bench sheet as five numbered floor-order steps at 1.4 em, one open "Read it" form. Type 1.101, 76, 3.9 → Check → the page returns with the verdict banner: "OG 1.103 (read 1.101 at 76 °F, hydrometer 60 °F). 3.8 points under 1.107 … stir in 0.87 lb (14 oz) honey … or carry on for about 13.5 %." Re-check after a top-up costs one load. Prints cleanly.
- **Routes:** `GET /recipes/<slug>/must` (params `gal, reading, temp_f, cal_f, ph`), `GET /recipes/<slug>` gains the "Make must" mini-form (GET), `/recipes` rows gain the link.
- **Modules:** `brew/views_must.py` (`render_must(recipe, gal, check)`), `tests/test_must.py`.
- **Tests:** page without a reading has the five steps in order and no banner; with `reading=1.101&temp_f=76&cal_f=60&ph=3.9` the banner contains `1.103`, `3.8 points under`, `0.87 lb (14 oz)`, `13.5 %`, `pH 3.9`; with `reading=1.112` it contains `0.30 gal (1.1 L)`, `6.30 gal`, `14.7 %` and the 71B note; blank `temp_f` skips correction and says so.

### Commit 4 — Record the must and pitch; the dated schedule
- **Owner can do:** after a verdict the check form collapses to "Re-check" and the record form opens, prefilled: id B-2026-NNN (editable — type 003 once), pitched-at now, volume 6, honey 18.29, water 4.48, yeast 10, Go-Ferm 12.5, the corrected OG and pH carried as hidden fields, notes. Record → `data/batches/B-2026-003.json` and lands on `/batches/B-2026-003` with the banner "Recorded B-2026-003 — 6 gal, OG 1.103, pH 3.9, 10 g 71B pitched 3:40 pm. First Fermaid O 6.3 g Fri Sep 4 around 3:40 pm." The batch page shows the facts and the four dated feeds, each capped at SG 1.069. The recipe page lists its batches. The next must page prefills `cal_f` and the last batch's volume.
- **Routes:** `POST /recipes/<slug>/must` (fields `id, pitched_at, volume_gal, honey_lb, water_gal, yeast_g, goferm_g, og, reading, temp_f, cal_f, ph, notes`) → `303 /batches/<id>?msg=` (duplicate id refused with a banner, nothing written), `GET /batches/<id>`.
- **Modules:** `brew/store.py` (+ `save_batch`, `load_batch`, `batches_for_recipe`, `next_batch_id(year)`, `last_batch()`), `brew/views_batches.py`, `brew/views_must.py` (record form), `data/batches/.gitkeep`, `tests/test_batches.py`.
- **Tests:** `next_batch_id` on an empty dir → `B-2026-001`, with `B-2026-003` present → `B-2026-004`; POST writes the exact shape in §3 and the redirect carries the banner text; the file's `nutrients.additions` were computed from the posted `og` (1.1029 → 6.3 g), not the target; a second POST with the same id does not overwrite; `/recipes/<slug>` lists the batch; `/recipes/<slug>/must` now prefills `cal_f` from it; `/batches/<id>` renders four rows each containing `1.069`.

That is the whole first round. Live recompute via `/api/plan`, learning the honey's real ppg, recipe versions and a yeast strain picker are named in §9 as not this round.

## 3. Data model

Two directories under `<repo>/data` (override `--data DIR` or env `BREW_DATA`), one JSON file per record, `indent=2, sort_keys=True`, written to `<file>.tmp` then `os.replace`. No index files, no settings file (the hydrometer calibration temp is remembered from the last batch file).

### `data/recipes/orange-blossom-traditional.json`
```json
{
  "additions": 4,
  "computed": {
    "abv_if_dry": 14.0,
    "constants": {"ABV_FACTOR": 131.25, "GOFERM_G_PER_G_YEAST": 1.25, "GOFERM_WATER_ML_PER_G": 20.0,
                  "HONEY_LB_PER_GAL": 12.0, "PPG_PER_LB_HONEY": 35, "YAN_PER_ABV.medium": 12.5,
                  "YAN_PPM_PER_G_PER_GAL.fermaid-o": 40.0},
    "goferm_g": 12.5, "goferm_water_ml": 250,
    "honey_gal": 1.52, "honey_lb": 18.29, "honey_lb_per_gal": 3.05,
    "nutrient_g": 26.2, "og": 1.1067, "per_addition_g": 6.6,
    "third_break_sg": 1.071, "water_gal": 4.48, "yan_ppm": 175, "yeast_g": 10.0,
    "warnings": ["71B is rated about 14%: a 14% target leaves it no margin."]
  },
  "demand": "medium",
  "design_gal": 6,
  "honey": "orange blossom",
  "name": "Orange Blossom Traditional",
  "notes": "",
  "product": "fermaid-o",
  "slug": "orange-blossom-traditional",
  "strength": {"by": "abv", "abv": 14.0, "og": null, "fg": 1.0},
  "updated": "2026-09-03",
  "yeast": "71B",
  "yeast_g": 10.0
}
```
Rules: `strength.by` is `"abv"` or `"og"`; whichever the owner set is stored, the other is `null` and derived. `honey_lb` exists **only** inside `computed`. `computed` is written on every save for anyone reading the file in git; the app never reads it, and `test_recipes` asserts it equals `calc.plan()` from the inputs. Edited in place (git is the history); a batch snapshots its targets so a redesign never rewrites a past batch. `yeast_g` is the grams at `design_gal`; other volumes scale it linearly.

### `data/batches/B-2026-003.json`
```json
{
  "added": {"goferm_g": 12.5, "honey_lb": 18.3, "water_gal": 4.5, "yeast_g": 10.0},
  "id": "B-2026-003",
  "measured": {"cal_f": 60, "expected_og": 1.1067, "og": 1.1029, "ph": 3.9, "reading": 1.101, "sample_f": 76},
  "notes": "read low by 4; stirred, carried on",
  "nutrients": {
    "additions": [
      {"due": "2026-09-04T15:40", "g": 6.3, "n": 1, "rule": "24 h after pitch, or the 1/3 break if sooner", "stop_sg": 1.069},
      {"due": "2026-09-05T15:40", "g": 6.3, "n": 2, "rule": "48 h, or the 1/3 break if sooner", "stop_sg": 1.069},
      {"due": "2026-09-06T15:40", "g": 6.3, "n": 3, "rule": "72 h, or the 1/3 break if sooner", "stop_sg": 1.069},
      {"due": "2026-09-10T15:40", "g": 6.3, "n": 4, "rule": "by day 7 or SG 1.069, whichever comes first", "stop_sg": 1.069}
    ],
    "from_og": 1.1029, "product": "fermaid-o", "total_g": 25.3, "yan_ppm": 169
  },
  "pitched_at": "2026-09-03T15:40",
  "recipe": {"name": "Orange Blossom Traditional", "slug": "orange-blossom-traditional"},
  "target": {"abv": 14.0, "fg": 1.0, "og": 1.1067},
  "volume_gal": 6.0,
  "yeast": "71B"
}
```
Rules: exactly one `measured` block (the reading the owner recorded with, after any top-up), no `readings[]`, no `state`, no `corrections[]`, no `done` flags. `measured.og` is always the temperature-corrected value; `reading` is what the glass said. The schedule is stored, not recomputed, so a later constant change never moves a past batch's dates. Batch ids are `B-YYYY-NNN`, prefilled as max existing + 1 for the year and editable.

## 4. The recipe designer job walk

**Job:** "I want a 14 % orange blossom traditional I can make again."

**Entry:** `GET /` (load 1). Nav: `Design · Recipes`. Title "Design a recipe". The page renders with gal 6, ABV 12, FG 1.000, yeast 71B, yeast g 6, and the sheet already below, so the first load is an answer.

**Card 1 — Targets (the form, GET to `/`):**
- Batch volume (gal) — number, default 6. Hint: "Your carboys: 5, 6, 6.8."
- Target strength (% ABV) — number, default 12. Hint: "If it ferments dry (FG 1.000). A sweet finish means less alcohol, not less honey."
- Yeast — text with datalist (71B, D47, EC-1118, K1V-1116, QA23 + names from saved recipes), default 71B.
- Yeast (g) — number, prefilled `round(gal × 1.0)`; when the derived OG > 1.100 the hint reads "1 g/gal says 6 g. This must is over 1.100 — the sachet note says up to 2 g/gal (12 g). JK pitches 10." Editable; the owner types 10 once and it is saved on the recipe.
- `details.sec` "More" (collapsed): Finish FG (number, 1.000; hint "71B at 14 % may finish a few points higher"), Set OG instead (number, blank; when filled ABV is derived and the field hint says "strength set by OG"), Nitrogen demand (select low/medium/high, medium), Nutrient additions (number, 4), Notes (textarea).
- Button: **Recompute** (plain GET). With JS, any change submits the form for you.

**Card 2 — "At 6 gal you'll need"** (`kv` rows: label · big value · `.mut` formula):
| Row | Value | Formula / assumption text |
|---|---|---|
| OG | 1.107 | `1.000 + 14 ÷ 131.25` |
| Honey | 18.29 lb (18 lb 5 oz), 3.05 lb/gal | `106.7 points × 6 gal ÷ 35 pts per lb per gal` — planning figure; confirm with the hydrometer |
| Honey's own volume | ~1.52 gal | `18.29 ÷ 12 lb per gal` |
| Water | 4.48 gal (17.0 L), then top to the 6 gal mark | `6 − 1.52`; the mark is the truth, this is where to start |
| Yeast | 10 g 71B (2 sachets) | sachets = g ÷ 5, shown to one decimal |
| Go-Ferm | 12.5 g in 250 mL water at 104 °F | `1.25 g per g yeast; 20 mL per g Go-Ferm` |
| YAN | 175 ppm | `12.5 ppm per % ABV (medium demand) × 14` |
| Fermaid O | 26.2 g total, 4 × 6.6 g | `175 ÷ 40 ppm per g per gal × 6 gal`; at 24 h, 48 h, 72 h, last by the 1/3 break |
| Stop nitrogen at | SG 1.071 | `OG − (OG − FG) ÷ 3` |
| Expect | 14.0 % if it finishes at 1.000 | `(OG − FG) × 131.25`; estimate drifts high above ~14 % |
Warnings as `.msg.warn` rows under the table: `tolerance_note(strain, abv)` (71B/D47 ~14 %, QA23 ~16 %, EC-1118/K1V-1116 ~18 %; D47 adds "fusels above 70 °F"). Unknown strain → no note.

**Card 3 — Save as recipe** (the page's one open primary action, POST `/recipes`): Name (text), Honey (text, datalist of honey names seen), hidden copies of every Card 1 value, hidden `from_slug` when redesigning. Button **Save recipe** / **Save changes to <name>**.

**On save:** server re-parses the inputs, computes `plan()`, writes `data/recipes/<slug>.json` (inputs + `computed`), `303 /recipes/<slug>?msg=…`. A new name whose slug already exists and no `from_slug` → redirect back to `/` with the refusal banner, nothing written.

**Lands on `/recipes/<slug>` (load 3):** identity card (name, honey, 14 % · OG 1.107 · dry, 6 gal, 10 g 71B, Fermaid O × 4 medium); the same sheet at design volume with a one-field GET form "Show for [6] gal" (`?gal=`); the open primary action **Make must** (gal field prefilled with the last batch's volume or design gal, GET to `/recipes/<slug>/must`); `details.sec` Notes; Batches list (commit 4); link "Redesign" → `/?recipe=<slug>`.

**Banner:** "Saved Orange Blossom Traditional — 14 % (OG 1.107), 3.05 lb orange blossom per gallon; 18.29 lb for 6 gal. Make must →".

**Cost:** 3 loads (`/`, recompute, landing — 2 with JS), 4 typed fields (ABV, yeast g, name, honey), 0 disclosures. Old app: 16 fields plus the arithmetic done elsewhere.

## 5. The must-day job walk

**Job:** "Make 6 gal of this recipe today and walk away with the yeast in and the feeding dates in hand."

**Entry:** `/recipes` (load 1) → row "Orange Blossom Traditional · 14 % · 71B · [6] gal **Make must**" → `GET /recipes/<slug>/must?gal=6` (load 2). Or from the recipe page's Make must form.

**Page anatomy (before a reading):**
1. Identity strip: Orange Blossom Traditional · 6 gal · target OG 1.107 / 14 % dry · 71B · Fermaid O × 4. If a prior batch exists: "last time B-2026-002 came in at 1.104."
2. Banner slot (empty until a check).
3. **The bench sheet, five numbered steps in floor order, values at 1.4 em:**
   1. **Honey** — 18.29 lb (18 lb 5 oz). Don't boil it; a warm water bath if it's slow.
   2. **Water** — start with 4.48 gal (17.0 L); the honey takes the other 1.52. Stir until it is one liquid, then top to the 6 gal mark.
   3. **Read it** — hydrometer and pH before the yeast goes in (form below).
   4. **Rehydrate and pitch** — 250 mL water to 104 °F, stir in 12.5 g Go-Ferm, sprinkle 10 g 71B, wait 15–20 min, temper with must in small doses until within 10 °F, pitch.
   5. **Feed** — Fermaid O 26.2 g as 4 × 6.6 g: weigh four cups now. 24 h, 48 h, 72 h, last by the 1/3 break (SG 1.071). Nothing after that.
4. **"Read it" form** (GET, the one open action): Hydrometer reading (`inputmode=decimal`), Sample temp °F (blank = at calibration temp), pH, and a `details.sec` "Hydrometer calibrated at [60] °F" prefilled from the last batch. Button **Check**. Nothing is written.
5. After Record exists for this recipe: nothing else; `details.sec` "Print" is just the browser — print CSS hides nav and forms.

**Check (load 3):** same URL with the params; the check form stays open and prefilled for a re-check; the verdict banner is built from calc:
- `og = hydro_correct(reading, temp_f, cal_f)` (skipped with a note when temp is blank).
- `expected = expected_og(honey_lb_plan, gal)` = `1 + 18.29 × 35 ÷ 6 ÷ 1000` → 1.1067; line: "18.3 lb in 6 gal should read about 1.107 at 35 pts/lb/gal."
- `correction(og, target_og, gal)`:
  - `pts = (target − og) × 1000`, rounded 1 dp. `|pts| ≤ 2` → "On target, within hydrometer resolution."
  - Low: honey lb `x = pts × gal ÷ (35 − target_pts ÷ 12)` (the added honey's own volume is inside the denominator, so one add lands on target instead of 0.86 of the way); `adds_gal = x ÷ 12`; `carry_on_abv = (og − fg) × 131.25`. Text: "3.8 points under 1.107. Make sure nothing is sitting on the bottom and re-read first; if it still reads low, stir in 0.87 lb (14 oz) honey (3.8 × 6 ÷ (35 − 106.7 ÷ 12)) — it adds ~0.07 gal — or carry on for about 13.5 %."
  - High: `w = gal × (og_pts ÷ target_pts − 1)`; `new_gal = gal + w`. Text: "5.3 points over. Add 0.30 gal (1.1 L) water (6 × (112 ÷ 106.7 − 1)) and you'll be at 6.30 gal — check the carboy has the room — or let it ride at ~14.7 %, past what 71B is rated for."
- `ph_verdict(ph)`: 3.7–4.2 "a happy must"; > 4.2 "on the high side; normal for a fresh honey must, it drops as fermentation starts"; 3.2–3.7 "low side, fine"; < 3.2 warn "below the 3.2 floor; the yeast will struggle — this round doesn't compute a correction."

**Record (commit 4):** once a verdict exists the check form collapses to `details.sec` "Re-check" and the **Record the must** form (POST) opens, prefilled: Batch id `B-2026-003` (editable), Pitched at (`datetime-local`, now; server-prefilled text fallback), Volume in the carboy (6, hint "if you diluted, put the new volume here"), Honey in (18.29), Water in (4.48), Yeast g (10), Go-Ferm g (12.5), Notes; hidden `og, reading, temp_f, cal_f, ph`. Button **Record**. The pitch form is always reachable — the verdict is advice, not a gate.

**On Record:** server validates, computes `schedule(pitched_at, og, fg, volume_gal, demand, product, additions)` from the **measured** OG (1.1029 → 13.5 % → 169 ppm → 25.3 g → 4 × 6.3 g, stop at 1.069), writes `data/batches/B-2026-003.json`, `303 /batches/B-2026-003?msg=…`.

**Lands on `/batches/<id>` (load 4):** facts card (id, recipe link, 6 gal, pitched Thu Sep 3 3:40 pm, OG 1.103 (read 1.101 at 76 °F) vs target 1.107, pH 3.9, 18.3 lb honey, 4.5 gal water, 10 g 71B + 12.5 g Go-Ferm); **Feed** table: `#1 6.3 g Fermaid O — Fri Sep 4, 3:40 pm (or the 1/3 break if sooner)`, `#2 Sat Sep 5`, `#3 Sun Sep 6`, `#4 by Thu Sep 10 or SG 1.069, whichever comes first`; the line "Nothing after this: late nitrogen feeds the wrong things."; notes; link back to the recipe. Print-clean for the barrel.

**Banner:** "Recorded B-2026-003 — 6 gal, OG 1.103, pH 3.9, 10 g 71B pitched at 3:40 pm. First Fermaid O 6.3 g Fri Sep 4 around 3:40 pm; stop at SG 1.069."

**Cost, straight path:** 4 loads, 3 typed (reading, temp, pH) + the id once, 0 disclosures. With a re-check after a top-up: +1 load, +1 typed. Old app: batch page, lot pickers that needed inventory, calculators in an iframe, and Go-Ferm, honey volume, hydrometer correction, OG correction and the dated schedule all done in the owner's head.

## 6. `brew/calc.py` API

Rounding boundaries (tests and pages use the rounded values, so they can never disagree): SG 4 dp, points 1 dp, lb 2 dp, gal 2 dp, L 1 dp, g 1 dp, mL 0 dp, ppm 0 dp, ABV 1 dp for display (`abv()` itself rounds 2 dp as in mead_calc).

**Constants copied verbatim from `mead_calc.py`:**
```python
ABV_FACTOR = 131.25
PPG_PER_LB_HONEY = 35
LB_PER_GAL_WATER = 8.34
YAN_PER_ABV = {"low": 9.0, "medium": 12.5, "high": 15.0}
YAN_PPM_PER_G_PER_GAL = {"fermaid-o": 40.0, "fermaid-k": 26.0, "dap": 55.0}
YEAST_G_PER_GAL = {"dry standard": 1.0}
YEAST_PACKET_G = 5.0
```
**brew_tool's own constants (documented with source in the module docstring):**
```python
HONEY_LB_PER_GAL = 12.0          # honey density, planning figure
GOFERM_G_PER_G_YEAST = 1.25      # Lallemand
GOFERM_WATER_ML_PER_G = 20.0     # Lallemand, at REHYDRATE_F
REHYDRATE_F = 104
HIGH_OG_PITCH_SG = 1.100         # from YEAST_NOTE: consider 2 g/gal above this
TOSNA_ADDITIONS = 4
TOSNA_HOURS = (24, 48, 72)       # additions 1-3 after pitch
TOSNA_LAST_DAY = 7               # addition 4 cap
ON_TARGET_PTS = 2.0
PH_FLOOR = 3.2
PH_NORMAL = (3.7, 4.2)
L_PER_GAL = 3.785
OZ_PER_LB = 16
YEASTS = {"71B": {"tolerance_abv": 14, "note": None},
          "D47": {"tolerance_abv": 14, "note": "throws fusels above 70 F"},
          "QA23": {"tolerance_abv": 16, "note": None},
          "EC-1118": {"tolerance_abv": 18, "note": None},
          "K1V-1116": {"tolerance_abv": 18, "note": None}}
```
**Functions:**
- `points(sg) -> float` — `(sg − 1) × 1000`.
- `abv(og, fg) -> float` — `round((og − fg) × ABV_FACTOR, 2)`.
- `og_for_abv(abv, fg=1.0) -> float` — `round(fg + abv / ABV_FACTOR, 4)`.
- `honey_for_og(gallons, og, ppg=PPG_PER_LB_HONEY) -> float` — `round(points(og) × gallons / ppg, 2)`.
- `honey_gal(honey_lb) -> float` — `round(honey_lb / HONEY_LB_PER_GAL, 2)`.
- `water_gal(gallons, honey_lb) -> float` — `round(gallons − honey_gal(honey_lb), 2)`.
- `expected_og(honey_lb, gallons, ppg=35) -> float` — `round(1 + honey_lb × ppg / gallons / 1000, 4)`.
- `yeast_grams(gallons, rate=1.0) -> float` — `round(gallons × rate, 1)`; `sachets(g) -> float` — `round(g / 5, 1)`.
- `goferm(yeast_g) -> (g, ml)` — `(round(1.25 × yeast_g, 1), round(20 × that g))`.
- `yan_ppm(abv, demand) -> int` — `round(YAN_PER_ABV[demand] × abv)`.
- `nutrient_grams(yan_ppm, gallons, product) -> float` — `round(yan_ppm / YAN_PPM_PER_G_PER_GAL[product] × gallons, 1)`.
- `split(total_g, n) -> float` — `round(total_g / n, 1)`.
- `third_break(og, fg=1.0) -> float` — `round(og − (og − fg) / 3, 3)`.
- `hydro_correct(reading, sample_f, cal_f) -> float` — verbatim polynomial, `round(…, 4)`.
- `tolerance_note(strain, abv) -> str | None` — strain key matched case-insensitively; note when `abv ≥ tolerance − 0.5`, plus the strain's temperature note if any.
- `correction(measured_og, target_og, gallons, fg=1.0, ppg=35, strain=None) -> dict` — `{'add': 'none'|'honey'|'water', 'pts', 'lb', 'oz', 'adds_gal', 'gal', 'liters', 'new_gal', 'carry_on_abv', 'over_tolerance': bool}`; honey `lb = pts × gallons / (ppg − points(target) / HONEY_LB_PER_GAL)`, water `gal = gallons × (points(measured) / points(target) − 1)`.
- `ph_verdict(ph) -> dict` — `{'kind': 'ok'|'warn', 'text'}` using `PH_FLOOR`, `PH_NORMAL`.
- `schedule(pitched_at: str, og, fg, gallons, demand, product, additions=4) -> dict` — `{'from_og', 'yan_ppm', 'total_g', 'additions': [{'n','g','due','rule','stop_sg'}]}`; `yan_ppm = yan_ppm(abv(og, fg), demand)`, `total_g = nutrient_grams(...)`, per-row `g = split(total_g, additions)`; rows 1–3 due at pitch + `TOSNA_HOURS`, row 4 due at pitch + 7 days; every row's `stop_sg = third_break(og, fg)`. For `additions` ≠ 4, rows 1..n−1 at 24 h intervals and row n at day 7.
- `plan(gal, abv=None, og=None, fg=1.0, yeast_g=None, strain='71B', demand='medium', product='fermaid-o', additions=4, ppg=35) -> dict` — exactly the keys in the recipe's `computed` block plus `strength_by`, `target_pts`, `sachets`, `feed_rows` (relative schedule text). Raises `ValueError` with a cellar-voice message on nonsense (gal ≤ 0, abv outside 0–25, og outside 1.000–1.250, ph outside 0–14).
- `next_batch_id(existing_ids, year) -> str` (pure; store passes the ids).

## 7. JS policy

One inline vanilla script, on the Design page only, from commit 2 — six lines: on any `input`/`change` event in the Targets form, debounce 400 ms, call `form.requestSubmit()`. It carries no arithmetic and no fetch; every number on screen is rendered by the server from `calc.py`. No-JS fallback is the **Recompute** button, which is the same GET. The Must page, recipe pages and batch page have no script. A test asserts the script has no `fetch`, `import`, `src=`, `localStorage`, or operators applied to digits. `/api/plan` live recompute is not this round.

## 8. Copy

1. Label "Target strength (% ABV)", hint: "If it ferments dry (FG 1.000). A sweet finish means less alcohol, not less honey."
2. Honey row: "18.29 lb (18 lb 5 oz) — 106.7 points × 6 gal ÷ 35 pts per lb per gal. That's the planning figure; the hydrometer has the last word."
3. Water row: "Start with 4.48 gal (17.0 L) — the honey takes the other 1.52. Stir until it is one liquid, then top to the 6 gal mark."
4. Yeast hint: "1 g/gal says 6 g. This must is over 1.100, so the sachet note says up to 2 g/gal (12 g). Type what you'll actually pitch."
5. Go-Ferm row: "12.5 g in 250 mL water at 104 °F — 1.25 g per g of yeast. Twenty minutes, then temper with must until it's within 10 °F before they meet."
6. Warning: "71B is rated about 14 %. A 14 % target leaves it no margin — good nutrients and a cool cellar get it there, and it may finish a touch sweet. 13 % is comfortable."
7. Low verdict: "OG 1.103 (read 1.101 at 76 °F, hydrometer 60 °F). 3.8 points under 1.107. Make sure nothing is sitting on the bottom and re-read; if it still reads low, stir in 0.87 lb (14 oz) honey, or carry on for about 13.5 %."
8. High verdict: "OG 1.112, 5.3 points over. Add 0.30 gal (1.1 L) water and you'll land on 1.107 at 6.30 gal — check the carboy has the room — or let it ride at ~14.7 %, past what 71B is rated for."
9. pH line: "pH 3.9 — a happy must (3.7–4.2 is normal, 3.2 is the floor)." / "pH 4.4 — on the high side; normal for a fresh honey must, it drops once the yeast gets going."
10. Record banner: "Recorded B-2026-003 — 6 gal, OG 1.103, pH 3.9, 10 g 71B pitched at 3:40 pm. First Fermaid O 6.3 g Fri Sep 4 around 3:40 pm; stop at SG 1.069."
11. Feed row 4: "6.3 g Fermaid O by Thu Sep 10 or SG 1.069, whichever comes first. Nothing after this: late nitrogen feeds the wrong things."
12. Duplicate name: "There's already a recipe called Orange Blossom Traditional. Open it and Redesign, or give this one another name." Empty recipes: "No recipes yet. Design one — it's two numbers."

## 9. Out of scope this round

- Inventory, lots, equipment, traceability, product, finance, tax, compliance, labels.
- Any fermentation log: no `readings[]`, no `state`/status pill, no feed tick-boxes, no `corrections[]`, no `/batches` index page, no home-page "next feed" card or dashboard.
- Recipe versions/changelog/pinning (edit in place; git is the history; batches snapshot targets).
- Learning the honey's real pts/lb/gal from a measured OG.
- Live recompute via a JSON endpoint; any client-side arithmetic.
- Free-text unit parsing ("18.3 lbs", "8.3 kg"); all inputs are number fields in lb / g / gal / °F.
- Yeast strain picker as a select; the strain table only drives the tolerance warning.
- Fermaid K / DAP scheduling, sulfite, pH adjustment doses, fruit/melomel gravity, back-sweetening, stabilization, refractometer/Brix.
- Importing the old repo's recipe (re-enter it: four fields).
- Editing a batch file through the UI (fix the JSON in git).

## 10. Risks and mitigations

- **Tracking creeps in through the batch file.** The file has one `measured` block, no arrays that grow after pitch except the fixed-length stored schedule, no status. `test_batches` asserts the exact key set; a feed tick or readings list is a round-2 design decision, not a field.
- **35 pts/lb/gal is a planning figure; orange blossom may run 33–36.** The sheet says so on the honey row, `expected_og` separates "weighed short" from "honey runs light", the correction loop catches it on the day, and learning ppg is named out of round.
- **A freshly mixed must reads low from the top.** The low verdict tells the owner to stir and re-read *before* adding honey; the check is a free GET so a re-check costs one load.
- **Honey correction overshoot/undershoot.** The honey add includes the added honey's own volume in the denominator (0.87 lb, not 0.65 lb); the water add reports the new volume and a carboy-room warning; the record form's Volume field is editable so the schedule grams use what is actually in the fermenter.
- **Fermaid O after the 1/3 break.** Every schedule row carries `stop_sg`; the copy says "or the 1/3 break if sooner" on all four rows, not only the last.
- **The 12 g double-pitch default reads as "wrong" to an owner who pitches 10 g.** Default is the brief's 1 g/gal; the hint states the >1.100 note; the typed grams are saved on the recipe and scaled from there.
- **Prose and tests disagreeing on a digit.** All rounding happens in calc at declared boundaries; pages format the rounded values; tests pin the rounded values (26.2 g, 6.6 g, 0.87 lb, 1.1029). Dates in copy come from `strftime`, never typed by hand (Sep 4 2026 is a Friday).
- **Phone on the barrel can't reach a laptop server.** `--lan` binds `0.0.0.0` and prints the LAN URL; default stays loopback so exposure is a choice.
- **Hydrometer calibration.** `cal_f` is a field on the check form (default 60), stored on the batch and prefilled next time; the verdict names it.
- **Batch numbering restarts at 001 in the new repo.** The id field is prefilled and editable; the README says "type 003 the first time"; the sequence continues from whatever exists.
- **`datetime-local` support is uneven on phones.** The server prefills the field with now in `YYYY-MM-DDTHH:MM`; a text fallback is parsed leniently (`%Y-%m-%dT%H:%M`, `%Y-%m-%d %H:%M`, `%Y-%m-%d`).
- **Python versions.** Write for 3.9 (no `match`, no `X | Y` annotations); `tests/test_syntax.py` runs `compileall` on `brew/`.
- **Scope pressure after the first must day.** Each "can it just…" in §9 already has its answer: next round.
# Brief: brew_tool — a fresh, small rebuild focused on recipe design and must prep

## The ask (verbatim from the owner)

> ok so initially, had developed a spec with cowork, and i think we bit off a
> little more that we can chew. i think i want to focus on usability and
> ensuring the application flows well when i use it. so i started a new repo,
> brew_tool. for this i would like to start with not necessarily with anything
> for tracking, but at least a tool to assist with developing recipes and
> making the must. is it possible to rebuild this in small incremental steps
> in the brew tool folder/repo

Owner: JK, a one-person licensed small-batch meadery (Warblers Meadery).
Works in a cellar: wet hands, phone or laptop on a barrel, one job at a time.
Real batches so far are 5–6 gallon carboys (EQ-001 5 gal, EQ-002/003 6.8 gal
wide-mouth). Honey on hand: Connecticut wildflower (600 lb), orange blossom
(240 lb). Yeast used: Lalvin 71B. Nutrient protocol: TOSNA (Fermaid O).

## What exists today (meadery_tools, the repo we are NOT extending)

Path: /Users/jamesmarshall/Desktop/codes/meadery_tools — read anything there.
~31,000 lines of stdlib-only Python: recipes, batches, inventory lots,
traceability, finance, tax, compliance, scheduling, QR labels, tutorial.
It became too much. The parts that matter for this brief:

### Recipe form (app/views_batches.py `recipes_list`, `recipe_detail`)
A single wall of ~16 fields: slug, name, author, style, carbonation, basis
volume, target OG, FG, ABV, pH floor, YAN ppm, then a textarea of
`type | item | qty | unit | timing` lines, a process textarea, nutrient
protocol, notes, date. The new-version form repeats all of it plus a
schedule textarea. Nothing is computed for the user: they must know OG, ABV,
honey lb and YAN themselves and type all four, and nothing checks they agree.
Recipes are versioned (never edited in place), stored one JSON per slug:

```json
{"slug": "traditional-orangeblossom", "name": "Orange Blossom Traditional",
 "current_version": 1, "versions": [{"version": 1, "date": "2026-09-02",
 "author": "JS", "changelog": "initial version", "style": "traditional",
 "carbonation": "still", "basis_volume_gal": 5,
 "targets": {"og": 1.1067, "fg": 1, "abv": 14, "ph_floor": 3.2, "yan_ppm": 175},
 "ingredients": [
   {"type": "honey", "item": "orange blossom honey", "qty": 18.29, "unit": "lbs", "timing": "must"},
   {"type": "yeast", "item": "71B", "qty": 10, "unit": "g", "timing": "must"},
   {"type": "water", "item": "spring water", "qty": 6, "unit": "gal", "timing": "must"}],
 "process": ["measure honey", "add water to 6 gallon mark",
   "rehydrate yeast - 104 F", "as must to rehyrated yeast and allow temp to come down to ambient"],
 "nutrient_protocol": "TOSNA-3", "notes": ""}]}
```
Note the owner's real recipe: they typed "lbs" not "lb", 18.29 lb honey for
5 gal basis but 6 gal water (the honey volume question), OG 1.1067 for 14%
— they did the arithmetic by hand somewhere.

### Must prep today
On a *planned* batch page, a "Must prep — one step" form: honey lot picker +
qty, yeast lot picker + qty, water gal, measured OG, pH, notes, date. It
prefills honey/yeast scaled from the recipe by `volume / basis_volume` and
water as `volume - honey_lb / 12`. It requires inventory lots to exist (the
lot is decremented in the same write). Calculators live on a separate page
and are embedded in an iframe under "Record an addition". The stage hint
text says "compute the nutrient schedule before the first addition
(Calculators → YAN)" — i.e. the user has to go do that themselves.

### The math (skills/meadery-production/scripts/mead_calc.py) — reuse these constants exactly
```
ABV_FACTOR = 131.25            # ABV ≈ (OG-FG)*131.25
PPG_PER_LB_HONEY = 35          # gravity points per lb honey per gallon (of finished must)
YAN_PER_ABV = {"low": 9.0, "medium": 12.5, "high": 15.0}   # ppm YAN per 1% potential ABV
YAN_PPM_PER_G_PER_GAL = {"fermaid-o": 40.0, "fermaid-k": 26.0, "dap": 55.0}
KMETA_SO2_FRACTION = 0.576
SUGAR_PPG = 46
FRUIT_SUGAR_PCT = {blueberry .10, raspberry .05, cherry .12, apple .13, peach .09, blackberry .10, strawberry .05, currant .10, other None}
YEAST_G_PER_GAL = {"dry standard": 1.0}; YEAST_PACKET_G = 5.0
honey_for_og(gallons, og) = points(og) * gallons / 35
hydro_correct(reading, sample_f, cal_f): standard density polynomial
  dens(t) = 1.00130346 - 1.34722124e-4*t + 2.04052596e-6*t^2 - 2.32820948e-9*t^3
  corrected = reading * dens(sample_f) / dens(cal_f)
yan: yan_ppm = YAN_PER_ABV[demand]*abv; grams = yan_ppm / YAN_PPM_PER_G_PER_GAL[product] * gallons; split N ways
```
Hand-checked test values (tests/test_calc.py): honey(5 gal, OG 1.100) = 14.29 lb;
yan(5 gal, 12%) = 150 ppm, 18.8 g Fermaid O, 6.2 g × 3; sulfite(5 gal, pH 3.4) =
31.9 ppm free, 1.049 g K-meta; hydro_correct(1.050, 77F, 60F) = 1.052.
The mead-science reference (skills/meadery-production/references/mead-science.md)
covers: ~35 pts/lb/gal honey; yeast tolerance/temperature map (71B ~14%, D47 ~14%
fusel >70F, EC-1118/K1V ~18%); TOSNA = Fermaid O split ~4 additions at pitch/24h,
day 2–3, day 4–6, last by 1/3 sugar break; stop nitrogen by 1/3 sugar break;
Go-Ferm at rehydration; don't boil honey; correct hydrometer for temp;
refractometer only for must OG.

Things the old app does NOT compute that a must-day tool should: honey's own
volume (honey is ~12 lb/gal, so 15 lb honey occupies ~1.25 gal — the water
needed is target volume minus honey volume, not target volume); the 1/3
sugar break gravity; the nutrient schedule as dated/timed additions; Go-Ferm
grams (Lallemand: 1.25 g Go-Ferm per 1 g yeast, in 20 mL water/g Go-Ferm at
104°F); OG correction — if measured OG is low by X points, add X*gal/35 lb
honey; if high, add water to dilute.

### The design language that worked (keep it)
CSS tokens: --bg #f6f3ec (warm paper), --card #fffdf8, --ink #2c2620,
--mut #8a7f70, --line #e6dfd2, --accent #8c6d1f (brand gold), --accent-dk
#6f5518, --ok #3a7d44, --err #a63d2f, --warn #b07d2b, --head #332b23.
system-ui 15px/1.55; radius 8px cards / 5px controls; buttons ≥40px tall;
labels above inputs; mobile-usable. Components: card, kv rows, pill, table,
details.sec (collapsed secondary), .msg ok/warn/err banner, .next links.
Voice: knowledgeable cellar-mate, not a database. Banners say what happened
concretely.

### The workflow principles that were written down (skills/meadery-app-workflow, meadery-app-ux)
- Think in jobs, not pages. Where does the job start, what does each step
  need (prefill everything derivable), where does it end (land on the result
  with a banner and the next link).
- Measure cost in interactions: page loads + disclosures + fields typed.
- One open primary action per page. Never a wall of open forms.
- POST → redirect → banner. Land where the result is.
- Stdlib only, server-rendered, no JS dependencies; anything clever degrades
  to a plain form post. (Small inline vanilla JS for live recompute is an
  open question — the old app allowed one tiny script for the layout page.)
- Big touch targets, readable at arm's length, usable on a phone.

## Constraints for brew_tool
- Repo: /Users/jamesmarshall/Desktop/codes/brew_tool — currently only README.md
  ("# brew_tool"). Remote github.com/jbmarshall7/brew_tool. Owner can run
  python3 3.10/3.11/3.12 locally; CI on the old repo tested 3.9 and 3.11.
- Python stdlib only (no pip). Plain JSON on disk, human-readable, git-versioned.
- Small incremental steps: each step is a commit the owner can run and use.
  The owner will use it between steps and give usability feedback. So step 1
  must already be *usable for something real* (their next batch is
  B-2026-003: orange blossom traditional, 6 gal, 14% target, 71B, TOSNA).
- Scope for this first round: recipe development + must preparation ONLY.
  No inventory lots, no traceability, no product lots, no finance/tax, no
  fermentation reading log yet ("not necessarily anything for tracking").
  A recipe should be savable and reusable; a must-day sheet should come from
  a recipe scaled to a batch volume. Whether to persist a "batch"/"must
  session" record at all in this round is a design decision to make
  explicitly (lean: yes but minimal, because the measured OG/pH on must day
  is the first data point of the fermentation and the owner will want it later
  — but it must not drag tracking in).
- Must be trivially runnable: `python3 -m brew` or similar, opens on
  localhost, no setup.
- Tests: unittest, run with `python3 -m unittest discover -s tests`.

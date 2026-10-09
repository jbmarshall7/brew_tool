"""Mead math for brew_tool.

Every number the app shows is computed *and rounded* here, at a declared
boundary, so a page and a test can never disagree on a digit:

    SG 4 dp · gravity points 1 dp · lb 2 dp · gal 2 dp · L 1 dp · g 1 dp ·
    mL 0 dp · ppm 0 dp · ABV 2 dp (pages show 1)

Constants in the first block are copied verbatim from the meadery_tools
production skill's ``mead_calc.py``, where they were hand-checked against
community-standard TOSNA figures. The second block is brew_tool's own
planning figures, each with its source. All of them are approximations for
a small meadery: the hydrometer has the last word.
"""
import re
from datetime import datetime, timedelta

# --- from mead_calc.py, verbatim -------------------------------------------
ABV_FACTOR = 131.25            # ABV ≈ (OG-FG)*131.25
PPG_PER_LB_HONEY = 35          # gravity points per lb honey per gallon of must
# Gravity points from one pound of PURE sugar dissolved in one gallon (~46
# ppg). Fruit contributes gravity only through its fermentable sugar, so:
# sugar_lb = fruit_lb × sugar_fraction, and points = sugar_lb × 46 / gallons.
SUGAR_PPG = 46
# Fermentable sugar as a fraction of fresh fruit weight — planning figures for
# ripe fruit (from the production skill's reference). Real fruit varies with
# ripeness, season and variety by several points, so a melomel OG computed
# from these is a target to confirm with a hydrometer once the fruit has given
# up its sugar. `None` means "no table value — give a percentage explicitly",
# because guessing an unlisted fruit is how a melomel lands 2 % ABV off.
FRUIT_SUGAR_PCT = {
    "blueberry": 0.10, "raspberry": 0.05, "cherry": 0.12, "apple": 0.13,
    "peach": 0.09, "blackberry": 0.10, "strawberry": 0.05, "currant": 0.10,
    "other": None,
}
# Whole fruit gives up its sugar over days, so a must-day hydrometer reads
# the honey only. Juice, cider and purée carry their sugar already dissolved,
# so the hydrometer reads it the moment it's stirred in.
FRUIT_IN_SOLUTION = ("juice", "cider", "concentrate", "puree", "purée",
                     "nectar")


def fruit_in_solution(item):
    item = (item or "").lower()
    return any(w in item for w in FRUIT_IN_SOLUTION)


# Fresh fruit is mostly water, so it also adds volume — about a gallon per this
# many pounds. A planning figure; the batch volume after fruit is what the
# hydrometer reads against.
FRUIT_LB_PER_GAL = 9.0
LB_PER_GAL_WATER = 8.34
# target ppm YAN per 1% potential ABV, by the yeast's nitrogen demand
YAN_PER_ABV = {"low": 9.0, "medium": 12.5, "high": 15.0}
# ppm YAN contributed per gram of product per US gallon of must
# (Fermaid O ~40: the community anchor of ~8.5 g ≈ 70 ppm in 5 gal)
YAN_PPM_PER_G_PER_GAL = {"fermaid-o": 40.0, "fermaid-k": 26.0, "dap": 55.0}
YEAST_G_PER_GAL = {"dry standard": 1.0}
YEAST_PACKET_G = 5.0

# --- brew_tool's own planning figures ---------------------------------------
HONEY_LB_PER_GAL = 12.0          # honey density (~1.42 kg/L); it takes up room
GOFERM_G_PER_G_YEAST = 1.25      # Lallemand: 1.25 g Go-Ferm per 1 g dry yeast
GOFERM_WATER_ML_PER_G = 20.0     # Lallemand: 20 mL water per g Go-Ferm
REHYDRATE_F = 104                # Lallemand rehydration temperature
HIGH_OG_PITCH_SG = 1.100         # above this the sachet note says up to 2 g/gal
YEAST_HIGH_OG_RATE = 2.0         # g/gal above HIGH_OG_PITCH_SG
TOSNA_ADDITIONS = 4
TOSNA_HOURS = (24, 48, 72)       # additions 1-3, hours after pitch
TOSNA_LAST_DAY = 7               # the last addition's cap, days after pitch
ON_TARGET_PTS = 2.0              # within this of target = hydrometer resolution
DEFAULT_CAL_F = 60               # most hydrometers; the form can override

# --- finishing: racking, stabilizing, back-sweetening, bottling -------------
KMETA_SO2_FRACTION = 0.576       # potassium metabisulfite is ~57.6% SO2
MOLECULAR_SO2_TARGET = 0.8       # ppm molecular SO2, the common protection floor
# Potassium sorbate: MoreWine/winemaking practice is 0.5 g/gal (~125 ppm) with
# sulfite, stepped to 0.75 g/gal (~200 ppm) when the sorbate has to work
# harder — high pH or low alcohol. It NEVER stops an active ferment, and does
# nothing without SO2 beside it. Source: morewinemaking.com Sorbistat K notes.
SORBATE_BASE_G_PER_GAL = 0.5
SORBATE_HIGH_G_PER_GAL = 0.75
SORBATE_HIGH_PH = 3.5
SORBATE_LOW_ABV = 10.0
# "stable" = the gravity has stopped moving: two readings a couple of days
# apart that barely differ. Sulfite does not arrest a working ferment, so the
# tool will not compute a stabilizing dose until this holds.
STABLE_PTS = 2.0
STABLE_DAYS = 2
# Oak and spice keep extracting until pulled, and over-extraction is the one
# flavor mistake you cannot walk back. Past this many days in contact, the
# tool starts saying taste it.
OAK_WATCH_DAYS = 14
# The moments a mead is worth tasting on purpose — the checkpoints where a
# note now changes what you do next, and where the recipe learns for next time.
TASTING_STAGES = ("fermenting", "post-primary", "pre-stabilization",
                  "at bottling", "in the bottle")
# --- carbonation / bottle-conditioning (sparkling) --------------------------
# Priming: CO2_to_add(g) = (target_vols - residual_vols) * 1.969 g/L/vol * L,
# then sugar_g = CO2_g / yield. Yields are g CO2 per g of that sugar (McGill
# 2006; honey = ~0.78 fermentable sugar x 0.51 sucrose yield). Residual CO2 is
# the standard Henry's-law polynomial in the highest post-ferment temp (°F).
# Sources cross-checked against 27 CFR 24.10/24.245 and brewing references.
CO2_G_PER_VOL_PER_L = 1.969
SUGAR_YIELD = {"honey": 0.40, "table sugar": 0.51, "corn sugar": 0.44}
# TTB: still wine is <= 0.392 g CO2/100 mL (27 CFR 24.10). Above that it is
# sparkling / artificially carbonated, and the federal excise roughly triples
# ($1.07 -> $3.30-$3.40 per gal), which is why carbonation is decided at design.
TTB_STILL_CO2_G_PER_100ML = 0.392
TTB_STILL_VOLS = round(TTB_STILL_CO2_G_PER_100ML * 10 / CO2_G_PER_VOL_PER_L, 2)
PH_FLOOR = 3.2
PH_LOW_WATCH = 3.5               # below this it will likely crash in primary
PH_NORMAL = (3.7, 4.2)
PH_HIGH = 4.8                    # above this, doubt the meter before the must
L_PER_GAL = 3.785
OZ_PER_LB = 16
# alcohol tolerance is approximate and moves with nutrition and temperature
YEASTS = {
    "71B": {"tolerance_abv": 14, "note": None},
    "D47": {"tolerance_abv": 14, "note": "throws fusels above 70 °F"},
    "QA23": {"tolerance_abv": 16, "note": None},
    "EC-1118": {"tolerance_abv": 18, "note": None},
    "K1V-1116": {"tolerance_abv": 18, "note": None},
}
KNOWN_YEASTS = list(YEASTS)


# --- parsing ----------------------------------------------------------------
def num(value, what, lo=None, hi=None, unit=""):
    """A user-typed number, or a ValueError that says what was wrong.

    Blank is refused here; callers that allow blank check for it first.
    """
    if value is None or str(value).strip() == "":
        raise ValueError(f"{what} is blank")
    try:
        v = float(str(value).strip().replace(",", ""))
    except ValueError:
        raise ValueError(f"{what} '{value}' isn't a number")
    if v != v or v in (float("inf"), float("-inf")):
        raise ValueError(f"{what} '{value}' isn't a number")
    if lo is not None and v < lo:
        raise ValueError(f"{what} {value}{unit} is below {lo}{unit}")
    if hi is not None and v > hi:
        raise ValueError(f"{what} {value}{unit} is above {hi}{unit}")
    return v


def blank(value):
    return value is None or str(value).strip() == ""


# --- volumes, typed any way a cellar says them -------------------------------
# A one-gallon test, a 6-gallon carboy, a bucket, or the 3 BBL conical: the
# same box takes all of them. A BBL here is a brewer's barrel, 31 US gallons
# (the unit a conical is sold in) — not a wine barrel.
GAL_PER_BBL = 31.0
_VOLUME = re.compile(
    r"^\s*(\d+(?:[.,]\d+)?)\s*(gal(?:lon)?s?|bbls?|barrels?|l|lit(?:er|re)s?)?"
    r"\.?\s*$", re.I)


def parse_volume(text, what="volume", lo=0.1, hi=1000):
    """US gallons from what was typed: 6 · 6.8 gal · 3 bbl · 1 barrel ·
    350 L · 6,5 — or a ValueError in plain words. Bare numbers are gallons."""
    if isinstance(text, (int, float)):
        g = float(text)
    else:
        m = _VOLUME.match(str(text or ""))
        if not m:
            raise ValueError(f"{what.capitalize()} '{text}' isn't something I "
                             "can read — try 6, 6.8 gal, 3 bbl or 350 L")
        raw, unit = m.group(1), (m.group(2) or "gal").lower()
        qty = float(raw.replace(",", "") if re.fullmatch(r"\d{1,3},\d{3}", raw)
                    else raw.replace(",", "."))
        if unit.startswith("b"):
            g = qty * GAL_PER_BBL
        elif unit.startswith("l"):
            g = qty * 0.264172
        else:
            g = qty
    if g != g or g < lo:
        raise ValueError(f"{what} {text} is below {num_(lo)} gal")
    if g > hi:
        raise ValueError(f"{what} {text} is {num_(g)} gal — above the "
                         f"{num_(hi)} gal ({num_(hi / GAL_PER_BBL, 1)} BBL) "
                         "this plans for")
    return round(g, 3)


def vol_text(gal):
    """'6 gal' — or '93 gal (3 BBL)' once it is brewhouse-sized."""
    g = f"{num_(gal)} gal"
    if gal >= GAL_PER_BBL:
        return f"{g} ({num_(gal / GAL_PER_BBL)} BBL)"
    return g


def ml_text(ml):
    """'124 mL', or '2.4 L' once a jug beats a measuring cup."""
    return f"{num_(ml / 1000, 1)} L" if ml >= 1000 else f"{round(ml)} mL"


# --- everything else that goes in --------------------------------------------
# Spice, citrus, oak, enzyme, tannin, acid, fining, the honey that back-
# sweetens: one per line under a "When:" heading, the way a recipe card is
# written. A line that starts with an amount scales with the batch; one that
# doesn't ("tartaric acid, to taste") is kept as written. Nothing is refused —
# a line that can't be read as an amount is shown exactly as typed.
UNITS = {
    # canonical unit: (what it measures, its size in that measure's base)
    "tsp": ("vol", 1.0), "Tbsp": ("vol", 3.0), "fl oz": ("vol", 6.0),
    "cup": ("vol", 48.0), "qt": ("vol", 192.0), "gal": ("vol", 768.0),
    "mL": ("ml", 1.0), "L": ("ml", 1000.0),
    "oz": ("wt", 1.0), "lb": ("wt", 16.0),
    "g": ("g", 1.0), "kg": ("g", 1000.0),
}
# a scaled amount is shown in the biggest of these that's at least 1 —
# spoons climb to cups and gallons, a juice stays in fluid ounces until it
# is gallons
LADDERS = {"tsp": ("tsp", "Tbsp", "cup", "gal"),
           "fl oz": ("fl oz", "gal"), "mL": ("mL", "L"),
           "oz": ("oz", "lb"), "g": ("g", "kg")}
LADDERS.update({"Tbsp": LADDERS["tsp"], "cup": LADDERS["tsp"],
                "qt": LADDERS["fl oz"], "gal": LADDERS["fl oz"],
                "L": LADDERS["mL"], "lb": LADDERS["oz"], "kg": LADDERS["g"]})
_UNIT_WORDS = {
    "teaspoons": "tsp", "teaspoon": "tsp", "tsp": "tsp",
    "tablespoons": "Tbsp", "tablespoon": "Tbsp", "tbsp": "Tbsp", "tbs": "Tbsp",
    "fluid ounces": "fl oz", "fluid ounce": "fl oz", "fl. oz": "fl oz",
    "fl oz": "fl oz", "floz": "fl oz", "cups": "cup", "cup": "cup",
    "quarts": "qt", "quart": "qt", "qt": "qt",
    "gallons": "gal", "gallon": "gal", "gal": "gal",
    "milliliters": "mL", "millilitres": "mL", "milliliter": "mL",
    "millilitre": "mL", "ml": "mL",
    "liters": "L", "litres": "L", "liter": "L", "litre": "L", "l": "L",
    "ounces": "oz", "ounce": "oz", "oz": "oz",
    "pounds": "lb", "pound": "lb", "lbs": "lb", "lb": "lb",
    "grams": "g", "gram": "g", "g": "g",
    "kilograms": "kg", "kilogram": "kg", "kg": "kg",
}
_UNIT = re.compile(
    "(" + "|".join(re.escape(w) for w in sorted(_UNIT_WORDS, key=len,
                                                reverse=True))
    + r")\.?(?=\s|$)", re.I)
# counted things that read in the plural: "19 packets Super-Kleer"
COUNT_UNITS = ("packet", "pack", "sachet", "tablet", "spiral", "stick",
               "bean", "pod", "cube")
_FRACTION = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3,
             "⅛": 0.125}
_QTY = re.compile(r"\s*(\d+\s+\d+/\d+|\d+/\d+|\d+(?:[.,]\d+)?(?:\s?[½¼¾⅓⅔⅛])?"
                  r"|[½¼¾⅓⅔⅛])")
# a number that's a strength, not an amount: "100 % RO water", "30 ppm"
_NOT_AMOUNT = re.compile(r"(%|ppm\b|°)", re.I)
# a "when" that means the day the must is made
MUST_DAY = re.compile(r"\b(must|pitch|mix|primary|start)", re.I)


def _qty_value(text):
    total = 0.0
    for part in text.replace(",", ".").split():
        if "/" in part:
            a, b = part.split("/")
            total += float(a) / float(b) if float(b) else 0.0
        elif part[-1] in _FRACTION:
            total += (float(part[:-1]) if part[:-1] else 0.0) + _FRACTION[part[-1]]
        else:
            total += float(part)
    return total


def parse_extra(line):
    """One line: {qty, unit, what, amount} — `amount` as typed ('¼ spiral'),
    or qty None when the line doesn't start with one."""
    plain = {"qty": None, "unit": "", "what": line.strip(), "amount": ""}
    m = _QTY.match(line)
    if not m:
        return plain
    rest = line[m.end():]
    glued = rest[:1] not in ("", " ", "\t")      # "10g", but "71B" isn't one
    rest = rest.strip()
    if _NOT_AMOUNT.match(rest):
        return plain
    unit = ""
    u = _UNIT.match(rest)
    if u:
        unit = _UNIT_WORDS[u.group(1).lower()]
        rest = rest[u.end():].strip()
    elif glued:
        return plain
    else:
        word, _, tail = rest.partition(" ")
        if word.lower().rstrip("s") in COUNT_UNITS and tail:
            unit, rest = word.lower().rstrip("s"), tail.strip()
    qty = _qty_value(m.group(1))
    if not rest or qty <= 0:
        return plain
    whole = line.strip()
    return {"qty": qty, "unit": unit, "what": rest,
            "amount": whole[:len(whole) - len(rest)].strip()}


def parse_extras(text):
    """The other-ingredients box: lines ending in ':' are when it goes in
    ('Secondary:'), the lines under them are what — in the order typed."""
    out, when = [], ""
    for line in (text or "").splitlines():
        line = line.strip().lstrip("•*·–- ").strip()
        if not line:
            continue
        if line.endswith(":") and parse_extra(line[:-1])["qty"] is None:
            when = line[:-1].strip()
            continue
        out.append(dict(parse_extra(line), when=when))
    return out


def extras_text(extras):
    """Back to the box, so a redesign starts from what was saved."""
    lines, when = [], None
    for e in extras or []:
        if e.get("when", "") != when:
            when = e.get("when", "")
            if lines:
                lines.append("")
            if when:
                lines.append(f"{when}:")
        lines.append(f"{e['amount']} {e['what']}" if e.get("amount")
                     else e["what"])
    return "\n".join(lines)


def must_day(when):
    return bool(MUST_DAY.search(when or ""))


def extra_amount(e, factor=1.0):
    """The amount for `factor` × the recipe's volume, in the unit a cellar
    would measure it in (18.6 Tbsp reads as 1.16 cups, 484 fl oz as
    3.78 gal) — or as typed at the recipe's own size. '' when there's none."""
    if e.get("qty") is None:
        return ""
    if abs(factor - 1.0) < 0.005:
        return e.get("amount") or num_(e["qty"])
    q, unit = e["qty"] * factor, e.get("unit") or ""
    if unit in UNITS:
        base = q * UNITS[unit][1]
        pick = LADDERS[unit][0]
        for u in LADDERS[unit]:
            if base / UNITS[u][1] >= 1:
                pick = u
        q, unit = base / UNITS[pick][1], pick
        figure = (str(round(q)) if q >= 100 else
                  num_(q, 1) if q >= 10 else num_(q, 2))
    else:
        figure = (str(round(q)) if q >= 10 else
                  num_(q, 1) if q >= 1 else num_(q, 2))
    if unit == "cup" or unit in COUNT_UNITS:
        unit += "" if figure == "1" else "s"
    return f"{figure} {unit}".strip()


def extra_line(e, factor=1.0):
    amt = extra_amount(e, factor)
    return f"{amt} {e['what']}" if amt else e["what"]


# --- gravity and alcohol ----------------------------------------------------
def num_(x, dp=2):
    ss = f'{round(float(x), dp):.{dp}f}'.rstrip('0').rstrip('.')
    return ss if ss not in ('', '-0') else '0'


def points(sg):
    return (sg - 1.0) * 1000.0


def sg_text(value):
    """A gravity as the cellar writes it: three decimals, and a fourth when
    it carries information (1.030, but 1.1029 — the point the correction
    turns on is in that last digit)."""
    if value is None:
        return "—"
    four = f"{value:.4f}"
    return four[:-1] if four.endswith("0") else four


def abv(og, fg):
    return round((og - fg) * ABV_FACTOR, 2)


def og_for_abv(target_abv, fg=1.0):
    return round(fg + target_abv / ABV_FACTOR, 4)


def third_break(og, fg=1.0):
    """The gravity at which a third of the sugar is gone: stop nitrogen here."""
    return round(og - (og - fg) / 3.0, 3)


def hydro_correct(reading, sample_f, cal_f=60.0):
    """Temperature-correct a hydrometer reading (standard density polynomial)."""
    def dens(t):
        return (1.00130346 - 1.34722124e-4 * t + 2.04052596e-6 * t * t
                - 2.32820948e-9 * t * t * t)
    return round(reading * dens(sample_f) / dens(cal_f), 4)


# --- finishing chemistry ----------------------------------------------------
def molecular_so2_free_needed(ph, molecular_target=MOLECULAR_SO2_TARGET):
    """Free SO2 (ppm) to reach a molecular-SO2 target at this pH.

    molecular_fraction = 1 / (1 + 10^(pH - 1.81)); free = target / fraction.
    Lower pH needs far less — the whole reason the dose is computed, not
    guessed.
    """
    frac = 1.0 / (1.0 + 10 ** (ph - 1.81))
    return molecular_target / frac, frac


def kmeta_grams(gallons, free_so2_ppm):
    """Grams of K-meta for a target free-SO2 addition. Ignores existing and
    bound SO2 — measure free SO2 and top up for real work."""
    liters = gallons * 3.785
    mg_kmeta = (free_so2_ppm * liters) / KMETA_SO2_FRACTION
    return round(mg_kmeta / 1000.0, 3)


def sorbate_grams(gallons, ph, abv_now):
    """Grams of potassium sorbate: the base rate, stepped up where sorbate is
    weakest (high pH or low alcohol)."""
    high = ph >= SORBATE_HIGH_PH or abv_now < SORBATE_LOW_ABV
    rate = SORBATE_HIGH_G_PER_GAL if high else SORBATE_BASE_G_PER_GAL
    g = round(rate * gallons, 2)
    ppm = round(rate / 3.785 * 1000)
    return {"g": g, "rate": rate, "ppm": ppm, "stepped_up": high}


# The dose for 0.8 ppm molecular climbs steeply with pH (pH 3.4 needs ~32 ppm
# free, 3.8 ~79, 4.0 ~125, 4.5 ~393). Past these lines the right move is to
# bring the pH down, not to pour in more sulfite.
SO2_HIGH_PH = 3.8           # above this: warn, and suggest acidifying first
SO2_FREE_CEILING = 100      # ppm free in one dose: past this, a recorded reason
SO2_LEGAL_TOTAL = 350       # ppm total SO2 in wine, 27 CFR 4.22(b)(1): never


def sulfite_problem(free_ppm, ph):
    """('refuse' | 'reason' | 'warn', text) about a free-SO2 dose, or None.

    'refuse' — the dose alone passes the legal limit for total SO2; no reason
    makes that sellable. 'reason' — past the practical ceiling; it can be
    done, but only on the record. 'warn' — high pH; it works, but sharply.
    """
    fix = ("Bring the pH down first (tartaric or acid blend, then re-measure) "
           "— every 0.1 lower cuts the dose by about a fifth.")
    if free_ppm > SO2_LEGAL_TOTAL:
        return ("refuse",
                f"At pH {_g2(ph)} that is {_g1(free_ppm)} ppm free SO₂ — over "
                f"the {SO2_LEGAL_TOTAL} ppm legal limit for total SO₂ before "
                f"any of it binds. {fix}")
    if free_ppm > SO2_FREE_CEILING:
        return ("reason",
                f"At pH {_g2(ph)} that is {_g1(free_ppm)} ppm free SO₂ — far "
                f"past what you can taste (~50) and much of it will bind. {fix}")
    if ph > SO2_HIGH_PH:
        return ("warn",
                f"pH {_g2(ph)} is high for mead: {_g1(free_ppm)} ppm free SO₂ "
                f"is a lot to taste. {fix}")
    return None


def _g2(x):
    return f"{round(float(x), 2):g}"


def stabilize_doses(gallons, ph, abv_now, molecular=MOLECULAR_SO2_TARGET):
    """Both stabilizer doses at once — they are given together or not at all."""
    free, frac = molecular_so2_free_needed(ph, molecular)
    sorb = sorbate_grams(gallons, ph, abv_now)
    return {
        "gallons": round(gallons, 2), "ph": ph, "abv": round(abv_now, 1),
        "molecular": molecular, "free_so2_ppm": round(free, 1),
        "molecular_fraction": round(frac, 4),
        "kmeta_g": kmeta_grams(gallons, free),
        "sorbate_g": sorb["g"], "sorbate_ppm": sorb["ppm"],
        "sorbate_rate": sorb["rate"], "sorbate_stepped_up": sorb["stepped_up"],
    }


def residual_co2_vols(temp_f):
    """CO2 already dissolved, in volumes, at the warmest the mead sat at.
    Standard Henry's-law polynomial; clamped at zero."""
    v = 3.0378 - 0.050062 * temp_f + 0.00026555 * temp_f * temp_f
    return round(max(v, 0.0), 2)


def co2_tax_class(target_vols):
    """Which TTB excise class a carbonation level lands in."""
    return ("still" if target_vols <= TTB_STILL_VOLS
            else "sparkling / carbonated")


def priming_sugar(gallons, target_vols, temp_f, sugar="honey"):
    """Grams of priming sugar to bottle-condition to `target_vols` of CO2.

    Only the CO2 above what is already dissolved has to be made, so warm mead
    (little residual) needs more sugar than cold. Returns the tax class too,
    because crossing ~2 volumes changes the excise rate.
    """
    if sugar not in SUGAR_YIELD:
        raise ValueError(f"prime with one of {', '.join(SUGAR_YIELD)}")
    residual = residual_co2_vols(temp_f)
    if target_vols <= residual:
        raise ValueError(
            f"the mead already holds about {residual} volumes at {num_(temp_f)} "
            f"°F — {num_(target_vols)} needs no priming sugar")
    liters = gallons * 3.785
    co2_g = (target_vols - residual) * CO2_G_PER_VOL_PER_L * liters
    grams = co2_g / SUGAR_YIELD[sugar]
    cls = co2_tax_class(target_vols)
    return {"gallons": round(gallons, 2), "target_vols": round(target_vols, 2),
            "residual_vols": residual, "temp_f": round(temp_f, 1),
            "sugar": sugar, "co2_g": round(co2_g, 1),
            "grams": round(grams, 1),
            "grams_per_gal": round(grams / gallons, 1) if gallons else 0,
            "tax_class": cls, "over_still": cls != "still"}


def backsweeten_honey(gallons, from_sg, to_sg, ppg=PPG_PER_LB_HONEY):
    """lb of honey to raise a stable mead from `from_sg` to `to_sg`."""
    pts = points(to_sg) - points(from_sg)
    if pts <= 0:
        raise ValueError(f"{sg_text(to_sg)} isn't sweeter than "
                         f"{sg_text(from_sg)} — back-sweetening only adds "
                         "sugar")
    return round(pts * gallons / ppg, 2)


# --- honey and water --------------------------------------------------------
def honey_for_og(gallons, og, ppg=PPG_PER_LB_HONEY):
    """lb of honey for `gallons` of finished must at `og`."""
    return round(points(og) * gallons / ppg, 2)


def honey_gal(honey_lb):
    """The room the honey itself takes up."""
    return round(honey_lb / HONEY_LB_PER_GAL, 2)


def water_gal(gallons, honey_lb):
    """Water to start with: the batch volume less the honey's own volume."""
    return round(gallons - honey_gal(honey_lb), 2)


def fruit_sugar_pct(fruit, pct=None):
    """Fermentable sugar fraction for a named fruit, or an explicit override.

    Accepts 10 as readily as 0.10 — nobody types a fraction with wet hands.
    An unlisted fruit needs a percentage given, never a silent guess.
    """
    if pct is not None and str(pct).strip() != "":
        # 10 means 10 %, and 0.10 means 10 % too — but 1 means 1 %. (It used
        # to read anything up to 1 as a fraction, so a typed 1 became 100 %.)
        v = num(pct, "fruit sugar %", 0.01, 80, " %")
        frac = v / 100.0 if v >= 1 else v
        if not 0.01 <= frac <= 0.80:
            raise ValueError(f"fruit sugar {pct} % is outside 1–80 % — type "
                             "10 for 10 %")
        return frac
    key = (fruit or "").strip().lower()
    if key not in FRUIT_SUGAR_PCT or FRUIT_SUGAR_PCT[key] is None:
        known = ", ".join(sorted(k for k in FRUIT_SUGAR_PCT if k != "other"))
        raise ValueError(f"no sugar percentage on file for '{fruit}' — give "
                         f"one explicitly (known: {known})")
    return FRUIT_SUGAR_PCT[key]


def fruit_points(lbs, pct, gallons):
    """Gravity points `lbs` of fruit at `pct` sugar adds to `gallons` of must."""
    if gallons <= 0:
        raise ValueError("gallons must be above zero")
    return round(lbs * pct * SUGAR_PPG / gallons, 1)


def fruit_gal(lbs):
    """The volume fresh fruit brings with it — mostly water."""
    return round(lbs / FRUIT_LB_PER_GAL, 2)


def honey_for_og_with_fruit(gallons, og, fruit_lb=0.0, fruit_sugar=0.0,
                            ppg=PPG_PER_LB_HONEY):
    """lb of honey to reach `og` when fruit already supplies some of the sugar.

    The fruit's points come off the target first; honey makes up the rest. If
    the fruit alone would overshoot the target, no honey is needed and the
    shortfall is negative — the caller warns.
    """
    target_pts = points(og)
    fpts = fruit_points(fruit_lb, fruit_sugar, gallons) if fruit_lb else 0.0
    honey_pts = target_pts - fpts
    return round(max(honey_pts, 0.0) * gallons / ppg, 2), round(fpts, 1)


def expected_og(honey_lb, gallons, ppg=PPG_PER_LB_HONEY):
    """What this much honey in this much must should read."""
    return round(1.0 + honey_lb * ppg / gallons / 1000.0, 4)


# --- yeast and nutrients ----------------------------------------------------
def yeast_grams(gallons, rate=YEAST_G_PER_GAL["dry standard"]):
    return round(gallons * rate, 1)


def sachets(grams):
    return round(grams / YEAST_PACKET_G, 1)


def yeast_for(gallons, og):
    """Dry yeast to pitch, in whole sachets.

    1 g per gallon, 2 g per gallon once the must is over 1.100, to the
    nearest 5 g sachet — halves round up, because underpitching is the
    failure mode — and never fewer than one. This is how a packet is
    actually used: 6 gal at 14 % is 12 g by the rule, so two sachets, 10 g;
    5 gal at 12 % is one sachet, which is what the packet itself says.
    """
    rate = (YEAST_HIGH_OG_RATE if og > HIGH_OG_PITCH_SG
            else YEAST_G_PER_GAL["dry standard"])
    by_rule = gallons * rate
    n = max(1, int(by_rule / YEAST_PACKET_G + 0.5))
    return {"rate": rate, "by_rule": round(by_rule, 1), "sachets": n,
            "g": round(n * YEAST_PACKET_G, 1)}


def goferm(yeast_g):
    """(grams of Go-Ferm, mL of water) to rehydrate `yeast_g` of dry yeast."""
    g = round(GOFERM_G_PER_G_YEAST * yeast_g, 1)
    return g, round(GOFERM_WATER_ML_PER_G * g)


def yan_ppm(target_abv, demand="medium"):
    if demand not in YAN_PER_ABV:
        raise ValueError(f"nitrogen demand '{demand}' isn't one of "
                         f"{', '.join(YAN_PER_ABV)}")
    return round(YAN_PER_ABV[demand] * target_abv)


def nutrient_grams_exact(ppm, gallons, product="fermaid-o"):
    if product not in YAN_PPM_PER_G_PER_GAL:
        raise ValueError(f"nutrient '{product}' isn't one of "
                         f"{', '.join(YAN_PPM_PER_G_PER_GAL)}")
    return ppm / YAN_PPM_PER_G_PER_GAL[product] * gallons


def nutrient_grams(ppm, gallons, product="fermaid-o"):
    return round(nutrient_grams_exact(ppm, gallons, product), 1)


def split(ppm, gallons, product, n):
    """Grams per addition, rounded from the exact total (not the shown one),
    so 175 ppm in 6 gal is 26.2 g as 4 × 6.6 g rather than 4 × 6.5 g."""
    return round(nutrient_grams_exact(ppm, gallons, product) / n, 1)


def _strain_key(strain):
    s = (strain or "").strip().upper().replace("LALVIN", "").strip()
    for key in YEASTS:
        if s == key.upper():
            return key
    return None


def tolerance_note(strain, target_abv):
    """A warning when the target sits at or past the strain's rated ABV."""
    key = _strain_key(strain)
    if key is None:
        return None
    tol = YEASTS[key]["tolerance_abv"]
    if target_abv < tol - 0.5:
        return None
    if target_abv > tol:
        text = (f"{key} is rated about {tol} %. A {target_abv:g} % target is "
                f"past that — expect it to stop short and finish sweet, or "
                f"pick a stronger strain.")
    else:
        text = (f"{key} is rated about {tol} %. A {target_abv:g} % target "
                f"leaves it no margin — good nutrients and a cool cellar get "
                f"it there, and it may finish a touch sweet. "
                f"{tol - 1:g} % is comfortable.")
    extra = YEASTS[key]["note"]
    return text + (f" It also {extra}." if extra else "")


def over_tolerance(strain, abv_value):
    key = _strain_key(strain)
    return key is not None and abv_value > YEASTS[key]["tolerance_abv"]


# --- must-day checks --------------------------------------------------------
def correction(measured_og, target_og, gallons, fg=1.0, ppg=PPG_PER_LB_HONEY,
               strain=None):
    """What to add to land a must on its target gravity, in cellar units.

    Honey: the added honey's own volume is in the denominator, so one
    addition lands on target instead of most of the way there.
    Water: the new volume is reported, because the carboy has to have room.
    """
    pts = round(abs(target_og - measured_og) * 1000.0, 1)
    carry = round(abv(measured_og, fg), 1)
    out = {"pts": pts, "carry_on_abv": carry, "measured_og": measured_og,
           "target_og": target_og,
           "over_tolerance": over_tolerance(strain, carry)}
    if pts <= ON_TARGET_PTS:
        out["add"] = "none"
        return out
    if measured_og < target_og:
        lb = pts * gallons / (ppg - points(target_og) / HONEY_LB_PER_GAL)
        lb = round(lb, 2)
        out.update({"add": "honey", "lb": lb, "oz": round(lb * OZ_PER_LB),
                    "adds_gal": round(lb / HONEY_LB_PER_GAL, 2)})
    else:
        w = round(gallons * (points(measured_og) / points(target_og) - 1.0), 2)
        out.update({"add": "water", "gal": w,
                    "liters": round(w * L_PER_GAL, 1),
                    "new_gal": round(gallons + w, 2)})
    return out


def ph_verdict(ph):
    lo, hi = PH_NORMAL
    floor = f"({lo}–{hi} is normal, {PH_FLOOR} is the floor)"
    if ph < PH_FLOOR:
        return {"kind": "warn",
                "text": f"pH {ph:g} — below the {PH_FLOOR} floor; the yeast "
                        "will struggle. This round doesn't compute a "
                        "correction: potassium bicarbonate in small doses, "
                        "re-measure each time."}
    if ph < PH_LOW_WATCH:
        return {"kind": "warn",
                "text": f"pH {ph:g} — low, and it drops further as it "
                        "ferments. Have potassium bicarbonate ready and "
                        f"re-check at the first feeding {floor}."}
    if ph < lo:
        return {"kind": "ok", "text": f"pH {ph:g} — on the low side, fine "
                                      f"{floor}."}
    if ph <= hi:
        return {"kind": "ok", "text": f"pH {ph:g} — a happy must {floor}."}
    if ph <= PH_HIGH:
        return {"kind": "ok", "text": f"pH {ph:g} — on the high side; normal "
                                      "for a fresh honey must, it drops once "
                                      "the yeast gets going."}
    return {"kind": "warn", "text": f"pH {ph:g} — unusually high for a honey "
                                    "must. Check the meter's calibration "
                                    "before trusting it."}


# --- the feeding schedule ---------------------------------------------------
WHEN_FORMATS = ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


def parse_when(text):
    """A timestamp from a string, or a datetime passed straight back.

    Callers hand this whatever they have — a field from a form, a value off
    a JSON record, or a datetime they already built — so accepting both
    keeps a confusing AttributeError from surfacing three frames away.
    """
    if isinstance(text, datetime):
        return text
    text = (text or "").strip()
    for fmt in WHEN_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"'{text}' isn't a date and time I can read — "
                     "YYYY-MM-DD HH:MM works")


def fmt_when(dt):
    return dt.strftime("%Y-%m-%dT%H:%M")


def feed_rules(n, stop_sg):
    """The timing sentence for each of `n` additions."""
    rules = []
    for i in range(1, n + 1):
        if i == n and n > 1:
            rules.append(f"by day {TOSNA_LAST_DAY} or SG {stop_sg}, "
                         "whichever comes first")
        else:
            rules.append(f"{24 * i} h after pitch, or the 1/3 break "
                         f"(SG {stop_sg}) if sooner")
    return rules


def schedule(pitched_at, og, fg, gallons, demand="medium", product="fermaid-o",
             additions=TOSNA_ADDITIONS):
    """Dated Fermaid additions from the *measured* OG, capped at the 1/3 break.

    Rows 1..n-1 fall 24 h apart after the pitch; the last row is capped at
    day 7. Every row carries the stop gravity, because the rule is the same
    for all of them: nothing after a third of the sugar is gone.
    """
    pitch = parse_when(pitched_at) if isinstance(pitched_at, str) else pitched_at
    if og <= fg:
        raise ValueError(f"OG {og} doesn't leave anything to ferment above "
                         f"FG {fg} — check the reading")
    n = int(additions)
    if n < 1 or n > 8:
        raise ValueError("nutrient additions should be between 1 and 8")
    stop = third_break(og, fg)
    ppm = yan_ppm(abv(og, fg), demand)
    total = nutrient_grams(ppm, gallons, product)
    per = split(ppm, gallons, product, n)
    rules = feed_rules(n, stop)
    rows = []
    for i in range(1, n + 1):
        if i == n and n > 1:
            due = pitch + timedelta(days=TOSNA_LAST_DAY)
        else:
            due = pitch + timedelta(hours=24 * i)
        rows.append({"n": i, "g": per, "due": fmt_when(due),
                     "rule": rules[i - 1], "stop_sg": stop})
    return {"from_og": og, "fg": fg, "product": product, "yan_ppm": ppm,
            "total_g": total, "stop_sg": stop, "additions": rows}


# --- the whole plan ---------------------------------------------------------
def plan(gal, abv_target=None, og=None, fg=1.0, strain="71B",
         demand="medium", product="fermaid-o", additions=TOSNA_ADDITIONS,
         ppg=PPG_PER_LB_HONEY, fruit=None, fruit_lb=None, fruit_pct=None):
    """Everything the bench needs for `gal` of must at a target strength.

    Strength is set by ABV (the usual way) or by OG; whichever is given wins
    and the other is derived. Yeast is whole sachets from the volume and the
    OG (see yeast_for). Raises ValueError in a cellar voice on nonsense.
    """
    gal = parse_volume(gal, "batch volume")
    fg = 1.0 if blank(fg) else num(fg, "finish FG", 0.950, 1.100)
    if not blank(og):
        og = num(og, "OG", 1.000, 1.250)
        by = "og"
        target_abv = abv(og, fg)
        if target_abv <= 0:
            raise ValueError(f"OG {og} doesn't leave anything to ferment "
                             f"above FG {fg}")
    elif not blank(abv_target):
        target_abv = num(abv_target, "target strength", 0.5, 25, " %")
        by = "abv"
        og = og_for_abv(target_abv, fg)
    else:
        raise ValueError("give a target strength (% ABV) or an OG")
    if demand not in YAN_PER_ABV:
        raise ValueError(f"nitrogen demand '{demand}' isn't one of "
                         f"{', '.join(YAN_PER_ABV)}")
    if product not in YAN_PPM_PER_G_PER_GAL:
        raise ValueError(f"nutrient '{product}' isn't one of "
                         f"{', '.join(YAN_PPM_PER_G_PER_GAL)}")
    n = int(num(additions, "nutrient additions", 1, 8))
    y = yeast_for(gal, og)
    yeast = y["g"]
    strain = (strain or "").strip() or "71B"

    # fruit, if any, supplies some of the sugar; honey makes up the rest
    fruit_info = None
    if not blank(fruit_lb):
        flb = num(fruit_lb, "fruit weight", 0.01, 10000, " lb")
        fname = (fruit or "").strip() or "other"
        fpct = fruit_sugar_pct(fname, fruit_pct)
        honey_lb, fpts = honey_for_og_with_fruit(gal, og, flb, fpct, ppg)
        fruit_info = {"item": fname, "lb": flb, "sugar_pct": round(fpct * 100, 1),
                      "sugar_lb": round(flb * fpct, 2), "points": fpts,
                      "gal": fruit_gal(flb),
                      "over": honey_lb <= 0 and fpts > points(og)}
    else:
        honey_lb = honey_for_og(gal, og, ppg)
    hg = honey_gal(honey_lb)
    # fruit brings its own volume, so the water target drops by that too
    wg = round(water_gal(gal, honey_lb)
               - (fruit_info["gal"] if fruit_info else 0.0), 2)
    # the honey and fruit can fill the volume by themselves (a cyser on
    # juice): then there is no water to add — never a negative amount
    overfill = round(-wg, 2) if wg < 0 else 0.0
    wg = max(wg, 0.0)
    gf_g, gf_ml = goferm(yeast)
    ppm = yan_ppm(target_abv, demand)
    total = nutrient_grams(ppm, gal, product)
    per = split(ppm, gal, product, n)
    stop = third_break(og, fg)
    dry = abv(og, fg)
    warnings = []
    note = tolerance_note(strain, target_abv)
    if note:
        warnings.append(note)
    if overfill > 0.01:
        what = f"the {fruit_info['item']}" if fruit_info else "the fruit"
        warnings.append(
            f"The honey and {what} alone come to about "
            f"{num_(gal + overfill)} gal — more than {num_(gal)} gal, so add no "
            "water; the gravity will run a touch under target, and the "
            "hydrometer has the last word.")
    if fruit_info and fruit_info["over"]:
        warnings.append(
            f"{num_(fruit_info['lb'])} lb of {fruit_info['item']} alone would "
            f"pass OG {sg_text(og)} — no honey needed, and the mead will be "
            "stronger and fruitier than the target. Use less fruit, or aim "
            "higher.")
    return {
        "strength_by": by, "gal": gal, "abv": round(target_abv, 2), "og": og,
        "fg": fg, "target_pts": round(points(og), 1),
        "honey_lb": honey_lb, "honey_lb_per_gal": round(honey_lb / gal, 2),
        "honey_gal": hg, "water_gal": wg, "water_l": round(wg * L_PER_GAL, 1),
        "overfill_gal": overfill,
        "yeast_g": yeast, "sachets": y["sachets"], "yeast_rate": y["rate"],
        "yeast_by_rule": y["by_rule"], "strain": strain,
        "high_og_pitch": og > HIGH_OG_PITCH_SG,
        "goferm_g": gf_g, "goferm_water_ml": gf_ml,
        "demand": demand, "product": product, "additions": n,
        "yan_ppm": ppm, "nutrient_g": total, "per_addition_g": per,
        "third_break_sg": stop, "feed_rows": feed_rules(n, stop),
        "abv_if_dry": dry, "warnings": warnings, "fruit": fruit_info,
        "constants": {
            "ABV_FACTOR": ABV_FACTOR, "PPG_PER_LB_HONEY": ppg,
            "HONEY_LB_PER_GAL": HONEY_LB_PER_GAL,
            "GOFERM_G_PER_G_YEAST": GOFERM_G_PER_G_YEAST,
            "GOFERM_WATER_ML_PER_G": GOFERM_WATER_ML_PER_G,
            f"YAN_PER_ABV.{demand}": YAN_PER_ABV[demand],
            f"YAN_PPM_PER_G_PER_GAL.{product}": YAN_PPM_PER_G_PER_GAL[product],
        },
    }


# --- the TTB operations report (F 5120.17) ----------------------------------
# Aggregates a period from the same batches and dispositions everything else
# reads. It SUPPORTS the filing and flags gaps; it makes no legal
# determination and computes no tax (that is the excise worksheet's job).
#
# The books are kept the way the form keeps them, in two sections that must
# each balance every period:
#   bulk:    on hand at start + produced - bottled - losses = on hand at end
#   bottled: on hand at start + bottled - removed - losses = on hand at end
# Every gallon that moves is booked on the day it moved: a racking loss on the
# racking, the bottling loss (bulk drawn less what the bottles hold) on the
# bottling, a broken bottle on the day it broke. So the identity holds by
# construction, and the report checks it anyway — a residual means an event
# dated out of order, and it says so rather than filing a number that's off.
import re as _re
GAL_PER_LITER = 0.264172
_UNIT_RE = _re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(millilit(?:er|re)s?|ml|lit(?:er|re)s?|l|"
    r"fl\.?\s*oz|ounces?|oz|gal(?:lon)?s?)\b", _re.I)
# a disposition that leaves the premises for consumption or sale is a taxable
# removal; a sample is its own line the operator classifies; "other" must be
# classified before filing; breakage is a loss
TAXABLE_REMOVALS = ("sold", "taproom", "gift")
BALANCE_SLACK = 0.005           # gallons: below this a residual is rounding


def unit_gallons(unit_str):
    """US gallons the package holds, from its name, or None if it says none.
    Reads 750 ml, 1.5 L, 1,5 L, 2 liters, 12 oz, 12 fl oz, 5 gallons."""
    m = _UNIT_RE.search(unit_str or "")
    if not m:
        return None
    raw_qty, u = m.group(1), m.group(2).lower()
    if _re.fullmatch(r"\d{1,3},\d{3}", raw_qty):          # 1,000 ml
        qty = float(raw_qty.replace(",", ""))
    else:                                                # 1,5 L
        qty = float(raw_qty.replace(",", "."))
    if u.startswith("m"):
        return qty / 1000 * GAL_PER_LITER
    if u == "l" or u.startswith("lit"):
        return qty * GAL_PER_LITER
    if "oz" in u or u.startswith("ounce"):
        return qty / 128.0
    return qty                                           # gallons


def abv_alt(og, fg):
    """The fuller ABV formula. The simple one, (OG - FG) x 131.25, is fine at
    table strength but drifts apart from this at high gravity — OG 1.120 to
    1.000 is 15.75 % one way, 17.55 % the other — which is exactly where the
    16 % excise line sits."""
    return round(76.08 * (og - fg) / (1.775 - og) * (fg / 0.794), 2)


# The still-wine excise classes (26 USC 5041(b)), by alcohol by volume.
STILL_CLASSES = ((16.0, "still ≤16 %"), (21.0, "still 16–21 %"),
                 (24.0, "still 21–24 %"))


def wine_tax_class(batch):
    """(class, low ABV, high ABV, warning) for a batch's wine.

    Sparkling if bottle-conditioned past the still limit. Otherwise a still
    class from the ABV: a lab measurement recorded at bottling if there is
    one, else the simple estimate from the OG and the last gravity READ
    (never a back-sweetened target) — the same number a label would carry.
    Gravity can't settle a class AT a line: the simple formula and the
    fuller one bracket the truth, and only where they land on opposite sides
    of 16, 21 or 24 % does the report ask for a lab ABV. (Flagging every
    batch that merely comes close would teach the owner to ignore flags.)
    """
    pk = batch.get("packaging") or {}
    if batch.get("primings"):
        vols = batch["primings"][-1].get("target_vols") or 0
        if vols > TTB_STILL_VOLS:
            return co2_tax_class(vols), None, None, None
    measured = pk.get("abv_measured")
    if measured is not None:
        return _still_class(measured), measured, measured, None
    og = (batch.get("measured") or {}).get("og")
    fg = last_read_sg(batch)
    if not og or fg is None:
        return (pk.get("tax_class") or "still (ABV unknown)", None, None,
                "no OG and finished gravity on record, so the ABV — and with "
                "it the still class — can't be estimated")
    simple, fuller = abv(og, fg), abv_alt(og, fg)
    lo, hi = min(simple, fuller), max(simple, fuller)
    cls = _still_class(simple)
    for line, _ in STILL_CLASSES:
        if lo <= line < hi:        # "not over 16" one way, over it the other
            return cls, lo, hi, (
                f"its ABV estimates {_g1(lo)}–{_g1(hi)} % reach across the "
                f"{_g1(line)} % line, where the tax class (and rate) changes — "
                "confirm with a lab measurement and record it at bottling")
    return cls, lo, hi, None


def _still_class(pct):
    for line, label in STILL_CLASSES:
        if pct <= line:
            return label
    return "over 24 % — not wine for excise"


def _day_before(d):
    return (parse_date(d) - timedelta(days=1)).isoformat()


def _bulk_as_of(b, day):
    """Gallons in the tank at the end of `day`: none before the pitch or
    after the bottling, else the last racking's volume, else the must's."""
    if (b.get("pitched_at") or "9999")[:10] > day:
        return 0.0
    pk = b.get("packaging")
    if pk and (pk.get("at") or "")[:10] <= day:
        return 0.0
    g = b.get("volume_gal") or 0.0
    for rk in sorted(b.get("rackings") or [], key=lambda r: r.get("at") or ""):
        if (rk.get("at") or "")[:10] <= day and rk.get("volume_gal") is not None:
            g = rk["volume_gal"]
    return float(g)


def _bottling(b):
    """(bulk drawn, gallons in the bottles, gallons per unit, gap or None)."""
    pk = b["packaging"]
    drawn = float(b.get("volume_gal") or 0.0)
    for rk in sorted(b.get("rackings") or [], key=lambda r: r.get("at") or ""):
        if (rk.get("at") or "") <= (pk.get("at") or "") \
                and rk.get("volume_gal") is not None:
            drawn = float(rk["volume_gal"])
    units = pk.get("units") or 0
    ug = unit_gallons(pk.get("unit"))
    if ug is None:
        ug = drawn / units if units else 0.0
        return drawn, drawn, ug, (
            f"{b['id']}: package '{pk.get('unit')}' states no volume, so each "
            "unit is taken as the bulk drawn ÷ the count — record the size "
            "(e.g. '750 ml') for a real bottling-loss figure")
    return drawn, units * ug, ug, None


def _units_as_of(b, day):
    pk = b.get("packaging")
    if not pk or (pk.get("at") or "")[:10] > day:
        return 0
    out = sum(d.get("qty") or 0 for d in b.get("dispositions") or []
              if (d.get("at") or "")[:10] <= day)
    return (pk.get("units") or 0) - out


def _stage_as_of(b, day):
    """Where a batch in bulk stood on `day` — from events on or before it."""
    def by(key):
        return any((e.get("at") or "")[:10] <= day for e in b.get(key) or [])
    if by("stabilizations"):
        return "stabilized"
    if by("primings"):
        return "primed"
    if by("rackings"):
        return "racked"
    return "fermenting"


def _within(at, start, end):
    return bool(at) and start <= at[:10] <= end


def ttb_report(batches, start, end):
    """The period's operations lines and its two balances. All gallons;
    every figure derived from the batch files."""
    parse_date(start), parse_date(end)             # a bad date fails loudly
    if start > end:
        raise ValueError(f"the period starts ({start}) after it ends ({end})")
    before = _day_before(start)
    production, bottled, losses, gaps = [], [], [], []
    removals, taxable_by_class = {}, {}
    bulk_inv, bottled_inv = [], []
    T = dict(begin_bulk=0.0, begin_bottled=0.0, produced=0.0,
             drawn=0.0, packaged=0.0, bulk_loss=0.0, removed=0.0,
             bottled_loss=0.0, end_bulk=0.0, end_bottled=0.0)

    for b in sorted(batches, key=lambda x: x.get("id") or ""):
        bid, pk = b.get("id"), b.get("packaging") or {}
        cls, lo, hi, warn = wine_tax_class(b)
        if warn and pk and (pk.get("at") or "")[:10] <= end:
            gaps.append(f"{bid}: {warn}")
        ug = None
        if pk:
            drawn, packaged, ug, gap = _bottling(b)
            if gap:
                gaps.append(gap)
        T["begin_bulk"] += _bulk_as_of(b, before)
        T["end_bulk"] += _bulk_as_of(b, end)
        if pk:
            T["begin_bottled"] += _units_as_of(b, before) * ug
            T["end_bottled"] += _units_as_of(b, end) * ug

        # A — produced by fermentation: the tank was filled this period
        if _within(b.get("pitched_at"), start, end):
            g = float(b.get("volume_gal") or 0.0)
            T["produced"] += g
            production.append({"batch": bid,
                               "recipe": (b.get("recipe") or {}).get("name"),
                               "started": b["pitched_at"][:10], "gal": round(g, 2)})

        # losses in bulk: each racking leaves the lees behind, on its own day
        prev = float(b.get("volume_gal") or 0.0)
        for rk in sorted(b.get("rackings") or [], key=lambda r: r.get("at") or ""):
            if rk.get("volume_gal") is None:
                continue
            loss = prev - float(rk["volume_gal"])
            prev = float(rk["volume_gal"])
            if pk and (rk.get("at") or "") > (pk.get("at") or ""):
                gaps.append(f"{bid}: a racking dated after the bottling")
                continue
            if _within(rk.get("at"), start, end):
                if loss < -BALANCE_SLACK:
                    gaps.append(f"{bid}: racking on {rk['at'][:10]} shows "
                                f"{_g2(-loss)} gal MORE than before — check it")
                T["bulk_loss"] += loss
                if abs(loss) > BALANCE_SLACK:
                    losses.append({"batch": bid, "gal": round(loss, 3),
                                   "date": rk["at"][:10], "why": "racking"})

        # B — bottled this period: what went into the bottles, and the
        # bottling loss (bulk drawn less what they hold) on the same day
        if pk and _within(pk.get("at"), start, end):
            T["drawn"] += drawn
            T["packaged"] += packaged
            T["bulk_loss"] += drawn - packaged
            bottled.append({"batch": bid, "units": pk.get("units"),
                            "unit": pk.get("unit"), "gal": round(packaged, 3),
                            "drawn_gal": round(drawn, 3), "tax_class": cls})
            if drawn - packaged < -BALANCE_SLACK:
                gaps.append(f"{bid}: the bottles hold {_g2(packaged)} gal but "
                            f"only {_g2(drawn)} gal was in the tank — check the "
                            "count or the package size")
            elif drawn - packaged > BALANCE_SLACK:
                losses.append({"batch": bid, "gal": round(drawn - packaged, 3),
                               "date": pk["at"][:10], "why": "bottling"})

        # C — removals and breakage from the bottled stock
        for d in b.get("dispositions") or []:
            if not _within(d.get("at"), start, end):
                continue
            g = (d.get("qty") or 0) * (ug or 0.0)
            if d["kind"] == "breakage":
                T["bottled_loss"] += g
                losses.append({"batch": bid, "gal": round(g, 3),
                               "date": d["at"][:10], "why": "breakage"})
                continue
            T["removed"] += g
            if d["kind"] == "sample":
                bucket = "samples"
            elif d["kind"] in TAXABLE_REMOVALS:
                bucket = cls
                taxable_by_class[cls] = taxable_by_class.get(cls, 0.0) + g
            else:
                bucket = "other — classify"
                gaps.append(f"{bid}: {d.get('qty')} unit(s) removed as "
                            f"'{d['kind']}' — classify before filing")
            row = removals.setdefault(bucket, {"gal": 0.0, "units": 0, "rows": []})
            row["gal"] = round(row["gal"] + g, 3)
            row["units"] += d.get("qty") or 0
            row["rows"].append({"batch": bid, "date": d["at"][:10],
                                "kind": d["kind"], "units": d.get("qty"),
                                "gal": round(g, 3), "to": d.get("to")})

        # E — on hand at the end of the period
        g = _bulk_as_of(b, end)
        if g > 0:
            bulk_inv.append({"batch": bid, "gal": round(g, 2),
                             "tag": _stage_as_of(b, end)})
        if pk:
            oh = _units_as_of(b, end)
            if oh > 0:
                bottled_inv.append({"batch": bid, "units": oh,
                                    "unit": pk.get("unit"),
                                    "gal": round(oh * ug, 2), "tax_class": cls})

    bulk_res = (T["begin_bulk"] + T["produced"] - T["packaged"]
                - T["bulk_loss"] - T["end_bulk"])
    bottled_res = (T["begin_bottled"] + T["packaged"] - T["removed"]
                   - T["bottled_loss"] - T["end_bottled"])
    for name, res in (("bulk", bulk_res), ("bottled", bottled_res)):
        if abs(res) > BALANCE_SLACK:
            gaps.append(f"the {name} section doesn't balance by {_g2(res)} gal "
                        "— an event is dated out of order")
    r2 = lambda x: round(x + 0.0, 2)                     # noqa: E731
    return {
        "start": start, "end": end,
        "begin": {"bulk_gal": r2(T["begin_bulk"]),
                  "bottled_gal": r2(T["begin_bottled"])},
        "production": production, "production_gal": r2(T["produced"]),
        "bottled": bottled, "bottled_gal": r2(T["packaged"]),
        "removals": removals,
        "taxable_removals_gal": r2(sum(taxable_by_class.values())),
        "taxable_by_class": {k: r2(v) for k, v in sorted(taxable_by_class.items())},
        "losses": sorted(losses, key=lambda x: (x["date"], x["batch"])),
        "losses_gal": r2(T["bulk_loss"] + T["bottled_loss"]),
        "bulk_losses_gal": r2(T["bulk_loss"]),
        "bottled_losses_gal": r2(T["bottled_loss"]),
        "bulk_inventory": bulk_inv, "bulk_inventory_gal": r2(T["end_bulk"]),
        "bottled_inventory": bottled_inv,
        "bottled_inventory_gal": r2(T["end_bottled"]),
        "balance": {
            "bulk": {"begin": r2(T["begin_bulk"]), "produced": r2(T["produced"]),
                     "bottled": r2(T["packaged"]), "losses": r2(T["bulk_loss"]),
                     "end": r2(T["end_bulk"]), "residual": round(bulk_res, 3)},
            "bottled": {"begin": r2(T["begin_bottled"]),
                        "bottled": r2(T["packaged"]),
                        "removed": r2(T["removed"]),
                        "losses": r2(T["bottled_loss"]),
                        "end": r2(T["end_bottled"]),
                        "residual": round(bottled_res, 3)},
            "ok": abs(bulk_res) <= BALANCE_SLACK
            and abs(bottled_res) <= BALANCE_SLACK,
        },
        "gaps": sorted(set(gaps)),
    }


# --- compliance documents ---------------------------------------------------
# The one thing about a permit the app cannot derive is when it expires, so
# that date is the only thing stored; the days remaining and whether it is a
# problem are computed on every render, like everything else here. A lapsed
# permit is exactly the kind of bad surprise the tool exists to prevent, so
# Today surfaces anything already expired or due within DOC_SOON_DAYS.
DOC_SOON_DAYS = 60


def parse_date(text):
    """A plain date from YYYY-MM-DD, or a ValueError in the owner's words."""
    text = (text or "").strip()
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise ValueError(f"'{text}' isn't a date I can read — YYYY-MM-DD, "
                         "e.g. 2027-03-01")


def doc_days_left(expires, today):
    """Whole days until `expires` (negative once past), None if unreadable."""
    try:
        return (parse_date(expires) - today).days
    except ValueError:
        return None


def document_status(documents, today, soon_days=DOC_SOON_DAYS):
    """Each document with its days-left and state, most urgent first.

    state is 'expired' (past), 'expiring' (due within soon_days), 'ok', or
    'unknown' when the date won't parse — and unknown sorts to the very top,
    because a renewal date you cannot read is itself worth fixing.
    """
    order = {"unknown": 0, "expired": 1, "expiring": 2, "ok": 3}
    out = []
    for d in documents or []:
        days = doc_days_left(d.get("expires"), today)
        if days is None:
            state = "unknown"
        elif days < 0:
            state = "expired"
        elif days <= soon_days:
            state = "expiring"
        else:
            state = "ok"
        out.append(dict(d, days=days, state=state))
    out.sort(key=lambda x: (order[x["state"]],
                            x["days"] if x["days"] is not None else -10 ** 9,
                            str(x.get("label") or "")))
    return out


def documents_needing_attention(documents, today, soon_days=DOC_SOON_DAYS):
    """Only the documents Today should raise: expired, expiring or unreadable."""
    return [d for d in document_status(documents, today, soon_days)
            if d["state"] != "ok"]


def doc_phrase(d):
    """The one plain line for a document's state — 'expired 5 days ago'."""
    days, state = d.get("days"), d.get("state")
    if state == "unknown":
        return "no readable renewal date"
    if state == "expired":
        n = -days
        return f"expired {n} day{'s' if n != 1 else ''} ago"
    if days == 0:
        return "expires today"
    return f"expires in {days} day{'s' if days != 1 else ''}"


# --- ids --------------------------------------------------------------------
def next_batch_id(existing_ids, year):
    """B-YYYY-NNN: one past the highest number already used this year."""
    prefix = f"B-{year}-"
    nums = []
    for i in existing_ids:
        if i.startswith(prefix) and i[len(prefix):].isdigit():
            nums.append(int(i[len(prefix):]))
    return f"{prefix}{max(nums, default=0) + 1:03d}"


# --- the fermentation log ---------------------------------------------------
# One gravity in, three columns out. Nothing below is ever stored: drop, ABV
# so far, attenuation and the next-action sentence are computed from the
# readings and the pitch date on every render, so there is no status for the
# operator to keep up to date.
STUCK_PTS = 1.0             # movement at or under this is not movement
RISE_PTS = 0.5              # a rise past this is the glass, not the mead
STALE_DAYS = 7              # after this, one gravity settles it
CONDITION_TEST_DAYS = 14    # bottle-conditioning: open a test bottle by now
CONDITION_TESTED_AFTER = 10  # an 'in the bottle' tasting this late settles it
FINISHED_MARGIN = 0.004     # this close to FG and the sugar is gone


def day_of(pitched_at, at):
    """The batch's day number at `at` — whole days since the pitch."""
    return (parse_when(at).date() - parse_when(pitched_at).date()).days


def attenuation(og, sg_now):
    """Apparent attenuation: the share of the original sugar now gone."""
    span = og - 1.0
    if span <= 0:
        return 0
    return round((og - sg_now) / span * 100)


def ledger(og, pitched_at, readings):
    """One row per reading, everything but the gravity itself derived."""
    rows, prev = [], None
    for r in sorted(readings or [], key=lambda x: x.get("at") or ""):
        sg_now = r.get("sg")
        if sg_now is None or not r.get("at"):
            continue
        rows.append({
            "at": r["at"], "day": day_of(pitched_at, r["at"]),
            "sg": sg_now, "reading": r.get("reading"),
            "sample_f": r.get("sample_f"), "note": r.get("note") or "",
            "drop": None if prev is None else round((prev - sg_now) * 1000, 1),
            "abv": abv(og, sg_now) if og else None,
            "atten": attenuation(og, sg_now) if og else None,
        })
        prev = sg_now
    return rows


def current_sg(batch):
    """The gravity as it stands: the sweetened target if the mead has been
    back-sweetened since the last reading, else the last reading, else the OG."""
    rows = sorted(batch.get("readings") or [], key=lambda x: x.get("at") or "")
    last_read = None
    for r in reversed(rows):
        if r.get("sg") is not None:
            last_read = r
            break
    sweet = sorted(batch.get("sweetenings") or [], key=lambda x: x.get("at") or "")
    if sweet and (last_read is None
                  or (sweet[-1].get("at") or "") >= (last_read.get("at") or "")):
        return sweet[-1].get("to_sg")
    if last_read is not None:
        return last_read["sg"]
    return (batch.get("measured") or {}).get("og")


def current_volume(batch):
    """Gallons in the vessel now: the last racking's measured volume, else the
    volume the must was made to. Every downstream dose is per this gallon."""
    racks = sorted(batch.get("rackings") or [], key=lambda x: x.get("at") or "")
    if racks and racks[-1].get("volume_gal") is not None:
        return racks[-1]["volume_gal"]
    return batch.get("volume_gal")


def is_stable(batch):
    """Has the gravity stopped moving? Two readings STABLE_DAYS apart that
    differ by no more than STABLE_PTS. Sulfite cannot arrest a live ferment,
    so stabilizing waits on this."""
    rows = sorted([r for r in batch.get("readings") or [] if r.get("sg")
                   is not None and r.get("at")], key=lambda x: x["at"])
    if len(rows) < 2:
        return False
    last = rows[-1]
    last_at = parse_when(last["at"])
    for prior in reversed(rows[:-1]):
        # elapsed hours, not calendar days — two readings either side of
        # midnight are not "two days apart"
        if (last_at - parse_when(prior["at"])).total_seconds() \
                >= STABLE_DAYS * 86400:
            return (abs(points(last["sg"]) - points(prior["sg"]))
                    <= STABLE_PTS + 1e-9)
    return False


def is_racked(batch):
    return bool(batch.get("rackings"))


def is_stabilized(batch):
    return bool(batch.get("stabilizations"))


def is_sweetened(batch):
    return bool(batch.get("sweetenings"))


def is_bottled(batch):
    return bool(batch.get("packaging"))


def is_primed(batch):
    return bool(batch.get("primings"))


# --- the two operations that can burst glass --------------------------------
# Priming and bottling are where a cellar mistake becomes a safety problem, so
# each has ONE rule, here, that the store enforces and the form explains. The
# store refuses whatever these return unless a reason is recorded with it.

# CO2 one gravity point of sugar makes if it ferments in a sealed bottle:
# 1 pt/gal = 1/46 lb sugar = 2.6 g/L, x 0.51 g CO2 per g sugar, / 1.969 g/L
# per volume = ~0.67 volumes. Ten points left behind is ~7 extra volumes.
VOLS_PER_POINT = (453.592 / SUGAR_PPG / 3.78541
                  * SUGAR_YIELD["table sugar"] / CO2_G_PER_VOL_PER_L)


def last_read_sg(batch):
    """The last gravity actually READ — not a back-sweetened target. What the
    yeast has finished is a measurement, never an intention."""
    rows = [r for r in batch.get("readings") or [] if r.get("sg") is not None]
    if not rows:
        return None
    return max(rows, key=lambda r: r.get("at") or "")["sg"]


def is_dry(batch):
    """No sugar left for yeast to find: the last reading is at or under 1.000
    (or the batch's own lower finish), within FINISHED_MARGIN. A sweet target
    FG does not make residual sugar safe to seal in with live yeast."""
    g = last_read_sg(batch)
    fg = (batch.get("target") or {}).get("fg") or 1.0
    return g is not None and g <= min(fg, 1.0) + FINISHED_MARGIN + 1e-9


def _sugar_left(batch):
    """(points above the dry floor, extra volumes of CO2 they would make)."""
    g = last_read_sg(batch)
    if g is None:
        return 0.0, 0.0
    floor = min((batch.get("target") or {}).get("fg") or 1.0, 1.0)
    pts = max(0.0, (g - floor) * 1000)
    return round(pts, 1), round(pts * VOLS_PER_POINT, 1)


def priming_refusal(batch):
    """Why priming this batch now would be dangerous, or None if it is safe.

    Priming is only safe on a mead that is finished, dry, and has had no sugar
    put back: live yeast eats every gram left in the bottle, priming or not.
    """
    if is_primed(batch):
        return ("It is already primed — a second dose of sugar doubles the "
                "pressure in every bottle.")
    if is_stabilized(batch):
        return ("This mead is stabilized — the yeast is inhibited and cannot "
                "carbonate. Bottle-conditioning needs live yeast.")
    if is_sweetened(batch):
        return ("It has been back-sweetened — that sugar would ferment in the "
                "bottle on top of the priming. Bottle-condition a dry mead and "
                "sweeten it another way.")
    if not is_stable(batch):
        return (f"It hasn't held a steady gravity for {STABLE_DAYS} days — "
                "priming a mead that is still fermenting adds sugar on top of "
                "the sugar it hasn't finished, and the bottles can burst.")
    if not is_dry(batch):
        pts, vols = _sugar_left(batch)
        return (f"It is steady at {sg_text(last_read_sg(batch))}, but not dry — "
                f"if the yeast finishes those {_g1(pts)} points in the bottle "
                f"that is about {_g1(vols)} more volumes on top of the priming. "
                "Only prime a mead that has finished dry.")
    return None


def bottling_refusal(batch):
    """Why sealing this batch in glass now would be dangerous, or None.

    Safe to bottle: primed on purpose (priming has its own rule), or
    stabilized, or finished dry with nothing sweetened back in.
    """
    if is_primed(batch):
        return None
    if is_sweetened(batch) and not is_stabilized(batch):
        return ("It was back-sweetened without being stabilized — that sugar "
                "can restart in the bottle and burst it. Stabilize first.")
    if is_stabilized(batch):
        return None
    if not is_stable(batch):
        return (f"It hasn't held a steady gravity for {STABLE_DAYS} days — a "
                "mead still fermenting in the bottle builds pressure until the "
                "glass gives. Log a couple of flat readings first.")
    if not is_dry(batch):
        pts, vols = _sugar_left(batch)
        return (f"It is steady at {sg_text(last_read_sg(batch))} with nothing "
                "to stop the yeast — if it wakes up in the bottle, those "
                f"{_g1(pts)} points are about {_g1(vols)} volumes of pressure. "
                "Stabilize it first.")
    return None


# where bottled mead goes — light channels, not the full TTB removal taxonomy
# (that is the future operations report's job). "sample" is called out because
# sample pours may or may not be a reportable loss, and the record lets the
# operator decide rather than the tool.
DISPO_KINDS = ("taproom", "sold", "gift", "sample", "breakage", "other")


def units_disposed(batch):
    return sum(d.get("qty", 0) for d in batch.get("dispositions") or [])


def units_on_hand(batch):
    """Bottles still on hand: what was bottled, less what has left."""
    pk = batch.get("packaging") or {}
    made = pk.get("units")
    if made is None:
        return None
    return made - units_disposed(batch)


def vessel_occupancy(vessels, batches, now=None):
    """For each vessel, the batch that holds it now (if any) and where that
    batch is. A vessel is free once its batch is bottled — the app never
    fabricates a free-by date it cannot derive from the record.
    """
    from datetime import datetime as _dt
    now = now or _dt.now()
    # a batch holds a vessel if it names one and is not yet bottled
    holding = {}
    for b in batches:
        v = (b.get("vessel") or "").strip()
        if v and not is_bottled(b):
            holding.setdefault(v.lower(), []).append(b)
    out = []
    for v in vessels:
        keys = [str(v.get("name", "")).lower(), str(v.get("id", "")).lower()]
        occ = []
        for k in keys:
            occ += holding.get(k, [])
        rows = []
        for b in occ:
            act = next_action(b, now)
            rows.append({"id": b["id"], "recipe": (b.get("recipe") or {}).get("name"),
                         "sg": current_sg(b), "tag": act["tag"],
                         "day": day_of(b["pitched_at"], now)
                         if b.get("pitched_at") else None})
        out.append({"vessel": v, "batches": rows, "free": not rows})
    return out


def flavors_in_contact(batch, now):
    """Oak and spice still in the mead, with how many days they have steeped.

    Fruit is not watched — it gives up its sugar and stays; oak and spice
    keep pulling tannin and aroma until you physically remove them.
    """
    out = []
    for i, fl in enumerate(batch.get("flavors") or []):
        if fl.get("kind") not in ("oak", "spice"):
            continue
        if fl.get("pulled_at"):
            continue
        try:
            days = day_of(fl["at"], now)
        except (ValueError, KeyError):
            continue
        out.append({"i": i, "item": fl.get("item"), "kind": fl.get("kind"),
                    "days": days})
    return out


def feeds_given(batch):
    """The numbers of the feedings actually recorded as given."""
    return {f.get("n") for f in batch.get("feeds") or [] if f.get("n")}


def next_feed(batch, now):
    """(the next feeding still owed, is the window shut).

    A feeding already recorded as given drops out. The window shuts for good
    once the gravity is past the 1/3 break — nothing is fed after that,
    whatever the calendar says, because late nitrogen feeds spoilage rather
    than yeast.
    """
    nut = batch.get("nutrients") or {}
    stop, now_sg = nut.get("stop_sg"), current_sg(batch)
    if stop is not None and now_sg is not None and now_sg <= stop:
        return None, True
    pitched = batch.get("pitched_at")
    if pitched and day_of(pitched, now) > TOSNA_LAST_DAY:
        return None, True       # "by day 7 or the 1/3 break": day 7 is past
    given = feeds_given(batch)
    for a in nut.get("additions") or []:
        if a.get("n") in given:
            continue
        try:
            parse_when(a["due"])
        except (ValueError, KeyError):
            continue
        return a, False
    return None, False


def esc_free(value):
    """Bottling's unit is free text; every other value here is a number. This
    keeps a stored unit from carrying markup into a page (the views escape
    too, but next_action's text is interpolated in a few places)."""
    return (str(value) if value is not None else "").replace("<", "").replace(
        ">", "")


def _clock(dt):
    hour = dt.hour % 12 or 12
    return f"{dt:%a %b} {dt.day}, {hour}:{dt:%M} {'am' if dt.hour < 12 else 'pm'}"


def _g1(x):
    return f"{round(float(x), 1):g}"


def next_action(batch, now=None, product="Fermaid O"):
    """The one sentence saying what to do about this batch, derived fresh.

    The order is deliberate. A feeding with a clock on it outranks anything
    the gravity is doing. A finished gravity comes next, because that is a
    level and one reading settles it. Everything after needs two readings to
    compare — nothing here ever claims movement it cannot see.
    """
    now = now or datetime.now()
    og = (batch.get("measured") or {}).get("og")
    fg = (batch.get("target") or {}).get("fg") or 1.0
    pitched = batch.get("pitched_at")
    rows = ledger(og, pitched, batch.get("readings"))
    feed, past_break = next_feed(batch, now)
    last = rows[-1] if rows else None
    now_sg = last["sg"] if last else og
    stop = (batch.get("nutrients") or {}).get("stop_sg")

    def warn(tag, text):
        return {"kind": "warn", "tag": tag, "text": text}

    def ok(tag, text):
        return {"kind": "ok", "tag": tag, "text": text}

    # 0 — bottled. A bottle-conditioned mead isn't done the day it's capped:
    # the yeast is building pressure, so it is watched until a bottle is
    # opened and tasted ('in the bottle'). Everything else bottled is done.
    if is_bottled(batch):
        pk = batch["packaging"]
        oh = units_on_hand(batch)
        left = (f" — {oh} on hand" if oh is not None and oh != pk.get("units")
                else "")
        if pk.get("conditioned"):
            capped = parse_when(pk["at"])
            tested = any(
                t.get("stage") == "in the bottle" and t.get("at")
                and parse_when(t["at"]) >= capped + timedelta(
                    days=CONDITION_TESTED_AFTER) for t in batch.get("tastings") or [])
            if not tested:
                days = (now - capped).days
                test_on = capped + timedelta(days=CONDITION_TEST_DAYS)
                if days < CONDITION_TEST_DAYS:
                    return ok("Conditioning",
                              f"Bottle-conditioning — day {days} of about "
                              f"{CONDITION_TEST_DAYS}. Keep it at 65–75 °F so the "
                              "yeast can carbonate it; open a test bottle "
                              f"around {test_on:%a %b} {test_on.day}.")
                return warn("Test a bottle",
                            f"Capped {days} days ago for "
                            f"{num_(pk.get('target_vols') or 0)} volumes — open "
                            "one. Flat: give it another week warm. Gushing: "
                            "chill every bottle now, it's over-carbonating. Then "
                            "record an 'in the bottle' tasting.")
        return ok("Bottled",
                  f"Bottled {pk.get('units')} × {esc_free(pk.get('unit'))} on "
                  f"{_clock(parse_when(pk['at'])).rsplit(',', 1)[0]}{left}. Done.")

    # 1 — a feeding owed today or already late beats anything the gravity
    # is doing; one still in the future is only worth a mention (rule 5)
    if feed is not None:
        due = parse_when(feed["due"])
        late = (now.date() - due.date()).days
        if late >= 0:
            whenever = ("due today at " + _clock(due).split(", ")[1]
                        if late == 0 else
                        f"was due {_clock(due)}, {late} day"
                        f"{'s' if late != 1 else ''} ago")
            return warn(
                "Feed due",
                f"{product} #{feed['n']}, {_g1(feed['g'])} g — {whenever}. "
                f"Stop at SG {sg_text(feed.get('stop_sg') or stop)} whatever "
                "the calendar says.")

    # 1b — oak or spice steeping too long: unfixable if you miss it
    for fl in flavors_in_contact(batch, now):
        if fl["days"] >= OAK_WATCH_DAYS:
            return warn("Taste the oak" if fl["kind"] == "oak"
                        else "Taste the spice",
                        f"{esc_free(fl['item'])} has been in "
                        f"{fl['days']} days — taste it. Over-extraction is the "
                        "one flavor you cannot pull back; pull it when it is "
                        "right.")

    # 2 — the finishing arc: once the mead is down and still (or already
    # part-way through finishing), the next physical step outranks the
    # gravity commentary. Checked most-complete-first.
    finished = now_sg is not None and rows and now_sg <= fg + FINISHED_MARGIN
    # racked but not finished (a melomel moved to secondary at 1.040) is
    # still a ferment: it falls through to the stalled / unread rules below,
    # instead of "Settling" forever or "Ready to stabilize" while still sweet
    if finished or is_stabilized(batch) \
            or is_sweetened(batch) or is_primed(batch):
        if is_sweetened(batch):
            sw = batch["sweetenings"][-1]
            return ok("Ready to bottle",
                      f"Sweetened to {sg_text(sw.get('to_sg'))}. Taste it, "
                      "then bottle it.")
        if is_primed(batch):
            pr = batch["primings"][-1]
            return ok("Ready to bottle",
                      f"Primed to {num_(pr['target_vols'])} volumes with "
                      f"{num_(pr['grams'])} g {esc_free(pr['sugar'])} — bottle "
                      "it in pressure-rated bottles and let the yeast work.")
        if is_stabilized(batch):
            return ok("Ready to bottle",
                      "Stabilized — sorbate and sulfite are in. Back-sweeten "
                      "to taste now, or bottle it dry.")
        if is_racked(batch):
            if is_stable(batch):
                return ok("Ready to stabilize",
                          f"Racked and steady at {sg_text(now_sg)}. For a still "
                          "mead, stabilize then sweeten or bottle dry; for a "
                          "sparkling one, prime and bottle-condition instead.")
            return ok("Settling",
                      f"Racked at {sg_text(now_sg)}. Give it a few days flat "
                      "before you stabilize — sulfite will not stop a mead "
                      "that is still working.")
        return ok("Ready to rack",
                  f"{sg_text(now_sg)} and steady at {_g1(abv(og, now_sg))} % — "
                  "when it falls clear, rack it off the lees.")

    # 3 — it reads higher than last time: suspect the glass, not the mead
    if last is not None and last["drop"] is not None \
            and last["drop"] < -RISE_PTS:
        return warn(
            "Reads high",
            f"{sg_text(last['sg'])} — it reads {_g1(-last['drop'])} points "
            "higher than last time. Stir it and re-read, or check the sample "
            "temperature: a rising gravity is usually the glass, not the mead.")

    # 4 — stuck: a day or more with nothing to show for it
    if len(rows) >= 2:
        hours = (parse_when(last["at"]) - parse_when(rows[-2]["at"])) \
            .total_seconds() / 3600
        gap = int(hours // 24)
        if hours >= 24 and abs(last["drop"] or 0) <= STUCK_PTS:
            fix = ("Nitrogen is done, so warm it and rouse it, then read "
                   "again in 24 h." if past_break or feed is None else
                   "Check the temperature first, then rouse it.")
            return warn("Stalled", f"Stuck at {sg_text(last['sg'])} — no movement in "
                        f"{gap} day{'s' if gap != 1 else ''}. {fix}")

    # 5 — nothing to compare yet: no readings, or the only one is today's
    read_today = last is not None and day_of(last["at"], now) == 0
    if not rows or (len(rows) == 1 and read_today):
        if day_of(pitched, now) == 0:
            opened = f"Pitched today at {sg_text(now_sg)}."
        elif rows:
            opened = (f"{sg_text(now_sg)} today, on day "
                      f"{day_of(pitched, now)} — nothing to compare it with "
                      "yet.")
        else:
            d = day_of(pitched, now)
            opened = (f"Pitched at {sg_text(now_sg)}, "
                      f"{d} day{'s' if d != 1 else ''} ago, and not read since.")
        if feed is not None:
            return ok("Waiting", f"{opened} Next up: {product} #{feed['n']}, "
                      f"{_g1(feed['g'])} g {_clock(parse_when(feed['due']))}.")
        return ok("Waiting", f"{opened} A gravity in a day or two tells you where it is.")

    # 6 — nobody has looked in a week
    stale = day_of(last["at"], now)
    if stale >= STALE_DAYS:
        return warn("Reading is old", f"Last read {stale} days ago at {sg_text(last['sg'])}. "
                    "One gravity says whether it is finished or stuck.")

    # 7 — it is simply working
    moved = last["drop"]
    if read_today:
        if moved and moved > STUCK_PTS:
            return ok("Still moving", f"{sg_text(last['sg'])}, {_g1(moved)} points down — "
                      "still moving. Next reading in a couple of days.")
        return ok("Quiet", f"{sg_text(last['sg'])} — give it a day before the next "
                  "reading.")
    span = day_of(rows[-2]["at"], last["at"]) if len(rows) >= 2 else 0
    tail = (f" — {_g1(moved)} points down in {span} day"
            f"{'s' if span != 1 else ''}" if moved and span else "")
    return ok("Quiet", f"Last read {stale} day{'s' if stale != 1 else ''} ago at "
              f"{sg_text(last['sg'])}{tail}. Worth another this week.")

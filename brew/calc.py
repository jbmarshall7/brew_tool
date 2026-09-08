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
        pct = float(pct)
        if pct <= 0:
            raise ValueError("sugar percentage must be above zero")
        return pct / 100.0 if pct > 1 else pct
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
    gal = num(gal, "batch volume", 0.1, 1000, " gal")
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
import re as _re
GAL_PER_LITER = 0.264172
_UNIT_RE = _re.compile(r"(\d+(?:\.\d+)?)\s*(ml|l|liter|litre|oz|gal)\b",
                       _re.I)
# a disposition that leaves the premises for consumption or sale is a taxable
# removal; a sample is its own line the operator classifies; breakage is a loss
TAXABLE_REMOVALS = ("sold", "taproom", "gift")


def unit_gallons(unit_str):
    """US gallons the package holds, from its name, or None if it says none."""
    m = _UNIT_RE.search(unit_str or "")
    if not m:
        return None
    qty, u = float(m.group(1)), m.group(2).lower()
    if u == "ml":
        return qty / 1000 * GAL_PER_LITER
    if u in ("l", "liter", "litre"):
        return qty * GAL_PER_LITER
    if u == "oz":
        return qty / 128.0
    return qty


def _within(at, start, end):
    return bool(at) and start <= at[:10] <= end


def ttb_report(batches, start, end):
    """The period's operations lines. All gallons; every figure derived."""
    production, bottled, removals, losses = [], [], {}, []
    gaps = []
    prod_gal = bott_gal = loss_gal = 0.0

    for b in sorted(batches, key=lambda x: x.get("id") or ""):
        bid = b.get("id")
        r = (b.get("recipe") or {})
        pk = b.get("packaging") or {}
        unit_gal = unit_gallons(pk.get("unit")) if pk else None

        # A — produced by fermentation: the tank was filled this period
        if _within(b.get("pitched_at"), start, end):
            g = round(b.get("volume_gal") or 0, 2)
            prod_gal += g
            production.append({"batch": bid, "recipe": r.get("name"),
                               "started": (b["pitched_at"] or "")[:10], "gal": g})

        # B — bottled this period
        if pk and _within(pk.get("at"), start, end):
            g = round(pk.get("volume_gal") or 0, 2)
            bott_gal += g
            tc = pk.get("tax_class") or "(unrecorded)"
            if pk.get("tax_class") is None:
                gaps.append(f"{bid}: bottled with no tax class on record")
            bottled.append({"batch": bid, "units": pk.get("units"),
                            "unit": pk.get("unit"), "gal": g, "tax_class": tc})
            # C — losses: bulk that went in the tank but not into bottles
            shortfall = round((b.get("volume_gal") or 0) - g, 2)
            if shortfall > 0.05:
                loss_gal += shortfall
                losses.append({"batch": bid, "gal": shortfall,
                               "date": (pk["at"] or "")[:10], "why": "bulk-to-bottle"})

        # C — removals and breakage-losses from dispositions this period
        for d in b.get("dispositions") or []:
            if not _within(d.get("at"), start, end):
                continue
            g = round((d.get("qty") or 0) * (unit_gal or 0), 3)
            if d["kind"] == "breakage":
                loss_gal += g
                losses.append({"batch": bid, "gal": g,
                               "date": (d["at"] or "")[:10], "why": "breakage"})
                continue
            bucket = ("samples" if d["kind"] == "sample"
                      else pk.get("tax_class") or "(unrecorded)"
                      if d["kind"] in TAXABLE_REMOVALS else d["kind"])
            row = removals.setdefault(bucket, {"gal": 0.0, "units": 0, "rows": []})
            row["gal"] = round(row["gal"] + g, 3)
            row["units"] += d.get("qty") or 0
            row["rows"].append({"batch": bid, "date": (d["at"] or "")[:10],
                                "kind": d["kind"], "units": d.get("qty"),
                                "gal": g, "to": d.get("to")})
            if d["kind"] in TAXABLE_REMOVALS and pk.get("tax_class") is None:
                gaps.append(f"{bid}: taxable removal with no tax class on record")
            if unit_gal is None and pk:
                gaps.append(f"{bid}: package '{pk.get('unit')}' states no "
                            "volume, so removal gallons can't be computed")

    # E — period-end inventory (what was on hand as of `end`, not now)
    bulk_inv, bottled_inv = [], []
    bulk_gal = bottled_inv_gal = 0.0
    for b in sorted(batches, key=lambda x: x.get("id") or ""):
        pk = b.get("packaging") or {}
        pitched = (b.get("pitched_at") or "")[:10]
        if not pitched or pitched > end:
            continue
        if not pk or (pk.get("at") or "")[:10] > end:
            # still in bulk at period end: the volume as of `end` — the last
            # racking on or before it, else the volume the must was made to
            g = b.get("volume_gal") or 0
            for rk in sorted(b.get("rackings") or [], key=lambda r: r.get("at") or ""):
                if (rk.get("at") or "")[:10] <= end and rk.get("volume_gal") is not None:
                    g = rk["volume_gal"]
            g = round(g, 2)
            if g > 0:
                bulk_gal += g
                bulk_inv.append({"batch": b["id"], "gal": g,
                                 "tag": next_action(b).get("tag")})
        else:
            # bottled by `end`: units made less what had left by `end`
            out = sum(d.get("qty", 0) for d in b.get("dispositions") or []
                      if (d.get("at") or "")[:10] <= end)
            oh = (pk.get("units") or 0) - out
            ug = unit_gallons(pk.get("unit")) or 0
            g = round(oh * ug, 2)
            if oh > 0:
                bottled_inv_gal += g
                bottled_inv.append({"batch": b["id"], "units": oh,
                                    "unit": pk.get("unit"), "gal": g,
                                    "tax_class": pk.get("tax_class") or "(unrecorded)"})

    taxable_gal = round(sum(v["gal"] for k, v in removals.items()
                            if k not in ("samples", "gift")), 2)
    return {
        "start": start, "end": end,
        "production": production, "production_gal": round(prod_gal, 2),
        "bottled": bottled, "bottled_gal": round(bott_gal, 2),
        "removals": removals, "taxable_removals_gal": taxable_gal,
        "losses": losses, "losses_gal": round(loss_gal, 2),
        "bulk_inventory": bulk_inv, "bulk_inventory_gal": round(bulk_gal, 2),
        "bottled_inventory": bottled_inv,
        "bottled_inventory_gal": round(bottled_inv_gal, 2),
        "gaps": sorted(set(gaps)),
    }


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

    # 0 — bottled: this batch is finished, nothing more to say
    if is_bottled(batch):
        pk = batch["packaging"]
        oh = units_on_hand(batch)
        left = (f" — {oh} on hand" if oh is not None and oh != pk.get("units")
                else "")
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
    if finished or is_racked(batch) or is_stabilized(batch) \
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
        gap = day_of(rows[-2]["at"], last["at"])
        if gap >= 1 and abs(last["drop"] or 0) <= STUCK_PTS:
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
            opened = (f"Pitched at {sg_text(now_sg)}, "
                      f"{day_of(pitched, now)} days ago, and not read since.")
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

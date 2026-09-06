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
         ppg=PPG_PER_LB_HONEY):
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

    honey_lb = honey_for_og(gal, og, ppg)
    hg = honey_gal(honey_lb)
    wg = water_gal(gal, honey_lb)
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
        "abv_if_dry": dry, "warnings": warnings,
        "constants": {
            "ABV_FACTOR": ABV_FACTOR, "PPG_PER_LB_HONEY": ppg,
            "HONEY_LB_PER_GAL": HONEY_LB_PER_GAL,
            "GOFERM_G_PER_G_YEAST": GOFERM_G_PER_G_YEAST,
            "GOFERM_WATER_ML_PER_G": GOFERM_WATER_ML_PER_G,
            f"YAN_PER_ABV.{demand}": YAN_PER_ABV[demand],
            f"YAN_PPM_PER_G_PER_GAL.{product}": YAN_PPM_PER_G_PER_GAL[product],
        },
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
    start = pitched_at if isinstance(pitched_at, datetime) else parse_when(pitched_at)
    when = at if isinstance(at, datetime) else parse_when(at)
    return (when.date() - start.date()).days


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
    """The gravity as it stands: the last reading, else the must's OG."""
    rows = sorted(batch.get("readings") or [], key=lambda x: x.get("at") or "")
    for r in reversed(rows):
        if r.get("sg") is not None:
            return r["sg"]
    return (batch.get("measured") or {}).get("og")


def next_feed(batch, now):
    """(the next scheduled feeding, is the window shut).

    Nothing is stored about whether a feed was actually given — the app
    never asks for a status to keep up to date. This reports what the
    schedule says, which is true either way, and it falls silent once the
    gravity is past the 1/3 break, because nothing is fed after that.
    """
    nut = batch.get("nutrients") or {}
    stop, now_sg = nut.get("stop_sg"), current_sg(batch)
    if stop is not None and now_sg is not None and now_sg <= stop:
        return None, True
    for a in nut.get("additions") or []:
        try:
            due = parse_when(a["due"])
        except (ValueError, KeyError):
            continue
        if due.date() >= now.date():
            return a, False
    return None, False


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

    def warn(text):
        return {"kind": "warn", "text": text}

    def ok(text):
        return {"kind": "ok", "text": text}

    # 1 — a feeding due today beats everything the gravity is doing
    if feed is not None:
        due = parse_when(feed["due"])
        if due.date() == now.date():
            return warn(
                f"{product} #{feed['n']}, {_g1(feed['g'])} g — due today at "
                f"{_clock(due).split(', ')[1]}. Stop at SG "
                f"{sg_text(feed.get('stop_sg') or stop)} whatever the "
                "calendar says.")

    # 2 — at or below the target: a level, so one reading settles it
    if now_sg is not None and rows and now_sg <= fg + FINISHED_MARGIN:
        return ok(f"{sg_text(now_sg)} and steady at "
                  f"{_g1(abv(og, now_sg))} % — taste it, then rack it off "
                  "the lees.")

    # 3 — it reads higher than last time: suspect the glass, not the mead
    if last is not None and last["drop"] is not None \
            and last["drop"] < -RISE_PTS:
        return warn(
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
            return warn(f"Stuck at {sg_text(last['sg'])} — no movement in "
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
            return ok(f"{opened} Next up: {product} #{feed['n']}, "
                      f"{_g1(feed['g'])} g {_clock(parse_when(feed['due']))}.")
        return ok(f"{opened} A gravity in a day or two tells you where it is.")

    # 6 — nobody has looked in a week
    stale = day_of(last["at"], now)
    if stale >= STALE_DAYS:
        return warn(f"Last read {stale} days ago at {sg_text(last['sg'])}. "
                    "One gravity says whether it is finished or stuck.")

    # 7 — it is simply working
    moved = last["drop"]
    if read_today:
        if moved and moved > STUCK_PTS:
            return ok(f"{sg_text(last['sg'])}, {_g1(moved)} points down — "
                      "still moving. Next reading in a couple of days.")
        return ok(f"{sg_text(last['sg'])} — give it a day before the next "
                  "reading.")
    span = day_of(rows[-2]["at"], last["at"]) if len(rows) >= 2 else 0
    tail = (f" — {_g1(moved)} points down in {span} day"
            f"{'s' if span != 1 else ''}" if moved and span else "")
    return ok(f"Last read {stale} day{'s' if stale != 1 else ''} ago at "
              f"{sg_text(last['sg'])}{tail}. Worth another this week.")

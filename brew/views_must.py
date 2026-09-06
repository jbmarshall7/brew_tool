"""Must day: the recipe scaled to today's carboy, in floor order, the
hydrometer check that says exactly what to stir in, and the one POST that
records the pitch.

The check is a GET: advice, re-runnable, writes nothing. Every refusal —
a mistyped reading, a blank field on the record form, an id already used —
comes back to this page with the banner and every typed value still in
place. Nothing the owner typed is ever dropped on the floor.
"""
import re
from datetime import datetime
from urllib.parse import urlencode

from . import calc
from .html import (banner, card, details, esc, field, gal_l, hidden, kv,
                   lb_oz, num, page as _page, pill, sg, textarea)
from .server import Response, redirect, route
from .sheet import feed_when, product_name
from .views_recipes import plan_for

DEFAULT_CAL_F = 60
RECORD_FIELDS = ("id", "pitched_at", "volume_gal", "honey_lb", "water_gal",
                 "yeast_g", "goferm_g", "og", "ph", "notes")
CHECK_FIELDS = ("gal", "now_gal", "reading", "temp_f", "cal_f", "ph")
# "003", "3", "b-2026-3": what a thumb types for B-2026-003
LOOSE_ID = re.compile(r"(?:B-(\d{4})-)?(\d{1,3})", re.IGNORECASE)


def feeds(p, og=None, gal=None):
    """The feeding numbers: from the plan, or re-sized from a measured OG."""
    n = p["additions"]
    if og is None:
        return {"total": p["nutrient_g"], "per": p["per_addition_g"],
                "stop": p["third_break_sg"], "sized": None}
    gal = gal or p["gal"]
    ppm = calc.yan_ppm(calc.abv(og, p["fg"]), p["demand"])
    return {"total": calc.nutrient_grams(ppm, gal, p["product"]),
            "per": calc.split(ppm, gal, p["product"], n),
            "stop": calc.third_break(og, p["fg"]),
            "sized": f"Sized from your OG {sg(og)} at {num(gal)} gal — "
                     "re-check after a top-up and these move with it."}


def steps(p, og=None, gal=None):
    """The five things you do, in the order you do them."""
    pname = product_name(p["product"])
    n = p["additions"]
    fd = feeds(p, og, gal)
    cups = {1: "one cup", 2: "two cups", 3: "three cups", 4: "four cups",
            5: "five cups", 6: "six cups"}.get(n, f"{n} cups")
    when = feed_when(n, sg(fd["stop"]))
    items = [
        ("Honey", lb_oz(p["honey_lb"]),
         "Don't boil it — a warm water bath if it's slow to pour."),
        ("Water", f"start with {gal_l(p['water_gal'])}",
         f"The honey takes the other {num(p['honey_gal'])} gal. Stir until it "
         f"is one liquid, then top to the {num(p['gal'])} gal mark."),
        ("Read it", "hydrometer and pH",
         "Before the yeast goes in — the form below does the arithmetic."),
        ("Rehydrate and pitch",
         f"{p['goferm_water_ml']} mL water at {calc.REHYDRATE_F} °F, "
         f"{num(p['goferm_g'], 1)} g Go-Ferm, {num(p['yeast_g'], 1)} g "
         f"{p['strain']}",
         "Stir the Go-Ferm in, sprinkle the yeast on, wait 15–20 minutes. "
         "Temper with must in small doses until it's within 10 °F, then "
         "pitch."),
        ("Feed", f"{pname} {num(fd['total'], 1)} g as {n} × "
                 f"{num(fd['per'], 1)} g",
         f"Weigh {cups} now. {when[0].upper() + when[1:]}. Nothing after "
         "that: late nitrogen feeds the wrong things."
         + (f" {fd['sized']}" if fd["sized"] else "")),
    ]
    lis = "".join(
        f'<li><span class="stitle">{esc(t)}</span>'
        f'<span class="big">{esc(v)}</span>'
        f'<span class="mut">{esc(n_)}</span></li>' for t, v, n_ in items)
    return f'<ol class="steps">{lis}</ol>'


def now_gal_from(p, params):
    if calc.blank(params.get("now_gal")):
        return p["gal"]
    return calc.num(params.get("now_gal"), "volume in the carboy", 0.1, 1000,
                    " gal")


def check(p, params):
    """(banner_text, kind, corrected_og, correction) or (None, None, None, None)."""
    if calc.blank(params.get("reading")) and calc.blank(params.get("ph")):
        return None, None, None, None
    lines, kind, og, c = [], "ok", None, None
    cal_f = (DEFAULT_CAL_F if calc.blank(params.get("cal_f"))
             else calc.num(params.get("cal_f"), "hydrometer calibration", 32,
                           110, " °F"))
    gal_now = now_gal_from(p, params)
    if not calc.blank(params.get("reading")):
        reading = calc.num(params.get("reading"), "hydrometer reading", 0.950,
                           1.250)
        if calc.blank(params.get("temp_f")):
            og = reading
            lines.append(f"OG {sg(og)} (as read — no sample temperature, so "
                         "no correction).")
        else:
            temp_f = calc.num(params.get("temp_f"), "sample temperature", 32,
                              140, " °F")
            og = calc.hydro_correct(reading, temp_f, cal_f)
            lines.append(f"OG {sg(og)} (read {sg(reading)} at {num(temp_f)} "
                         f"°F, hydrometer {num(cal_f)} °F).")
        c = calc.correction(og, p["og"], gal_now, p["fg"], strain=p["strain"])
        target = sg(p["og"])
        if c["add"] == "none":
            lines.append(f"On target — within {num(calc.ON_TARGET_PTS)} "
                         f"points of {target}, which is hydrometer resolution. "
                         f"Carry on for about {num(c['carry_on_abv'], 1)} %.")
        elif c["add"] == "honey":
            kind = "warn"
            lines.append(
                f"{num(c['pts'], 1)} points under {target}. Make sure nothing "
                "is sitting on the bottom and re-read; if it still reads low, "
                f"stir in {lb_oz(c['lb'])} honey — it adds about "
                f"{num(c['adds_gal'])} gal — or carry on for about "
                f"{num(c['carry_on_abv'], 1)} %.")
        else:
            kind = "warn"
            ride = (f"let it ride at ~{num(c['carry_on_abv'], 1)} %"
                    + (f", past what {p['strain']} is rated for"
                       if c["over_tolerance"] else ""))
            lines.append(
                f"{num(c['pts'], 1)} points over {target}. Add "
                f"{gal_l(c['gal'])} water and you'll land on {target} at "
                f"{num(c['new_gal'])} gal — check the carboy has the room, "
                f"and put {num(c['new_gal'])} in 'volume now' when you "
                f"re-check — or {ride}.")
    if not calc.blank(params.get("ph")):
        v = calc.ph_verdict(calc.num(params.get("ph"), "pH", 0, 14))
        lines.append(v["text"])
        if v["kind"] == "warn":
            kind = "warn"
    return "\n".join(lines), kind, og, c


def read_form(slug, p, params, checked, correction=None, verdict=None,
              vkind="ok"):
    """The design's inset check panel: one row of small fields, the verdict
    beneath it, and a reminder that none of it writes anything."""
    cal_f = params.get("cal_f") or str(DEFAULT_CAL_F)
    now_gal = params.get("now_gal") or num(p["gal"])
    if correction and correction.get("add") == "water":
        now_hint = (f"After the top-up that's {num(correction['new_gal'])} "
                    "gal.")
    else:
        now_hint = ("Only matters if you diluted or came up short of the "
                    "mark.")
    row = "".join(
        f'<span style="width:{w}px">{f}</span>' for w, f in (
            (130, field("reading", "Hydrometer", params.get("reading", ""),
                        None, step="0.001", attrs='placeholder="1.101"')),
            (112, field("temp_f", "Sample °F", params.get("temp_f", ""),
                        None, attrs='placeholder="76"')),
            (96, field("ph", "pH", params.get("ph", ""), None, step="0.01",
                       attrs='placeholder="3.9"')),
            (132, field("cal_f", "Hydrometer cal. °F", cal_f)),
        ))
    inner = (f'<h3>Read it — before the yeast goes in</h3>'
             f'<form class="row" method="get" '
             f'action="/recipes/{esc(slug)}/must" id="read">'
             f'{hidden("gal", num(p["gal"]))}{row}'
             f'<button>{"Check again" if checked else "Check"}</button>'
             "</form>"
             + (banner(verdict, vkind) if verdict else "")
             + f'<div style="max-width:230px">'
               f'{field("now_gal", "Volume in the carboy now (gal)", now_gal, now_hint)}'
               "</div>"
             + '<p class="mut">The check writes nothing — re-read as many '
               "times as you like. Recording the pitch is the only write.</p>")
    return f'<div class="panel">{inner}</div>'


def record_form(slug, p, params, og, next_id, gal_now, now=None):
    """What went in, when the yeast did, and the id — all prefilled."""
    def g(k, default=""):
        v = params.get(k)
        return v if v not in (None, "") else default
    now = now or datetime.now().strftime("%Y-%m-%dT%H:%M")
    og_val = g("og", f"{og:.4f}" if og is not None else "")
    keep = "".join(hidden(k, params.get(k, ""))
                   for k in ("reading", "temp_f", "cal_f", "now_gal"))
    return f"""<form class="inline" method="post" action="/recipes/{esc(slug)}/must" id="record-form">
{keep}{hidden("gal", num(p["gal"]))}
<div class="grid">
<span>{field("id", "Batch id", g("id", next_id), "The next number; type your own (even just 003) to continue a numbering from elsewhere.", typ="text", required=True, id_="rec-id")}</span>
<span>{field("pitched_at", "Yeast pitched at", g("pitched_at", now), "The feeding clock starts here.", typ="datetime-local", step=None, required=True, id_="rec-pitched")}</span>
<span>{field("og", "OG (corrected)", og_val, "From the check above, or type it.", step="0.0001", required=True, id_="rec-og")}</span>
<span>{field("ph", "pH", g("ph"), "Optional.", step="0.01", id_="rec-ph")}</span>
<span>{field("volume_gal", "In the carboy now (gal)", g("volume_gal", num(gal_now)), "After any water you added — the feedings are sized from it.", id_="rec-volume")}</span>
<span>{field("honey_lb", "Honey in (lb)", g("honey_lb", num(p["honey_lb"])), "What the scale said, including anything stirred in after the check.", id_="rec-honey")}</span>
<span>{field("water_gal", "Water in (gal)", g("water_gal", num(p["water_gal"])), "Blank is fine if it was all honey and top-up.", id_="rec-water")}</span>
<span>{field("yeast_g", "Yeast (g)", g("yeast_g", num(p["yeast_g"], 1)), None, id_="rec-yeast")}</span>
<span>{field("goferm_g", "Go-Ferm (g)", g("goferm_g", num(p["goferm_g"], 1)), "Blank if you skipped it.", id_="rec-goferm")}</span>
</div>
{textarea("notes", "Notes", g("notes"), "Read low and stirred? Topped up? Say so here.", id_="rec-notes")}
<div class="doit"><button>Record the must &amp; start the clock</button>
<span class="mut">Writes {esc(g("id", next_id))} with the corrected OG, what
went in, and {p["additions"]} dated feeds.</span></div></form>"""


def must_page(req, params, msg=None, kind="ok"):
    store = req.store
    r = store.load_recipe(req.args[0])
    last = store.last_batch(r["slug"])
    gal_text = params.get("gal") or num(r.get("design_gal"))
    gal = calc.num(gal_text, "volume", 0.1, 1000, " gal")
    p = plan_for(r, gal)
    if calc.blank(params.get("cal_f")) and last and \
            (last.get("measured") or {}).get("cal_f"):
        params = dict(params, cal_f=num(last["measured"]["cal_f"]))
    verdict = vkind = og = corr = None
    try:
        verdict, vkind, og, corr = check(p, params)
        gal_now = now_gal_from(p, params)
    except ValueError as e:
        # a fat-fingered reading: say so, keep the sheet and the forms
        msg, kind = str(e), "err"
        gal_now = p["gal"]
    last_line = None
    if last and (last.get("measured") or {}).get("og") is not None:
        last_line = (f"last time {last['id']} came in at "
                     f"{sg(last['measured']['og'])}")
    strip = kv([
        ("Making", f"{num(p['gal'])} gal of {r['name']}",
         f"target OG {sg(p['og'])} · {num(p['abv_if_dry'], 1)} % if dry · "
         f"{num(p['yeast_g'], 1)} g {p['strain']} · "
         f"{product_name(p['product'])} × {p['additions']}"
         + (f" · {last_line}" if last_line else "")),
    ])
    try:
        year = calc.parse_when(params.get("pitched_at")).year
    except ValueError:
        year = datetime.now().year
    existing = store.batch_ids()
    next_id = calc.next_batch_id(existing, year)
    if params.get("id") and params["id"].strip().upper() in existing:
        params = dict(params, id="")       # offer the next one instead
    rec = record_form(r["slug"], p, params, og, next_id, gal_now)
    # the whole of must day in one card: what you do, then the reading that
    # tells you whether it worked
    tag = pill("{} gal · next id {}".format(num(p["gal"]), next_id), "ok")
    must_card = (
        '<div class="card">'
        '<div class="sheet-head"><h2>Must day, in floor order</h2>'
        + tag + "</div>"
        + steps(p, og, gal_now)
        + read_form(r["slug"], p, params, bool(verdict), corr, verdict, vkind)
        + "</div>")
    body = (card(strip) + must_card
            + '<h2 id="record" class="noprint">Pitched? Record it</h2>'
            + rec
            + f'<p class="mut noprint"><a href="/recipes/{esc(r["slug"])}">'
              f"Back to {esc(r['name'])}</a> · this page prints clean for the "
              "barrel.</p>")
    return Response(_page(f"Must — {r['name']}", body, "/recipes",
                          msg or params.get("msg"),
                          kind if msg else params.get("kind", "ok")))


@route("GET", r"/recipes/([a-z0-9-]+)/must")
def must(req):
    return must_page(req, req.params)


def normalize_id(text, year):
    """'003' / '3' / 'b-2026-3' → 'B-2026-003'; anything else comes back as
    typed for the store to refuse in plain words."""
    text = (text or "").strip().upper()
    m = LOOSE_ID.fullmatch(text)
    if m:
        return f"B-{m.group(1) or year}-{int(m.group(2)):03d}"
    return text


def went_in(f, key, what, hi, unit):
    """A 'what went in' field: blank means none of it."""
    if calc.blank(f.get(key)):
        return 0.0
    return calc.num(f.get(key), what, 0, hi, unit)


@route("POST", r"/recipes/([a-z0-9-]+)/must")
def record(req):
    """Write data/batches/<id>.json: the one file the owner wants later."""
    store = req.store
    r = store.load_recipe(req.args[0])
    f = req.form

    def bounce(text, drop_id=False):
        keep = {k: f.get(k, "") for k in CHECK_FIELDS + RECORD_FIELDS
                if f.get(k) and not (drop_id and k == "id")}
        return redirect(f"/recipes/{r['slug']}/must?{urlencode(keep)}#record",
                        text, "err")

    try:
        gal = calc.num(f.get("gal") or r.get("design_gal"), "volume", 0.1,
                       1000)
        p = plan_for(r, gal)
        pitched = calc.parse_when(f.get("pitched_at"))
        batch_id = normalize_id(f.get("id"), pitched.year)
        store.batch_path(batch_id)
        if store.batch_exists(batch_id):
            nxt = calc.next_batch_id(store.batch_ids(), pitched.year)
            return bounce(f"{batch_id} is already recorded, so this must is "
                          f"offered the next number, {nxt}. Check the id and "
                          "tap Record again.", drop_id=True)
        volume = calc.num(f.get("volume_gal"), "volume in the carboy", 0.1,
                          1000, " gal")
        og = calc.num(f.get("og"), "OG", 0.950, 1.250)
        fg = p["fg"]
        ph = (None if calc.blank(f.get("ph"))
              else calc.num(f.get("ph"), "pH", 0, 14))
        added = {"honey_lb": went_in(f, "honey_lb", "honey", 10000, " lb"),
                 "water_gal": went_in(f, "water_gal", "water", 1000, " gal"),
                 "yeast_g": went_in(f, "yeast_g", "yeast", 5000, " g"),
                 "goferm_g": went_in(f, "goferm_g", "Go-Ferm", 5000, " g")}
        measured = {
            "og": og, "ph": ph,
            "expected_og": (calc.expected_og(added["honey_lb"], volume)
                            if added["honey_lb"] else None),
            "reading": (None if calc.blank(f.get("reading"))
                        else calc.num(f.get("reading"), "reading", 0.950,
                                      1.250)),
            "sample_f": (None if calc.blank(f.get("temp_f"))
                         else calc.num(f.get("temp_f"), "sample temperature",
                                       32, 140)),
            "cal_f": (DEFAULT_CAL_F if calc.blank(f.get("cal_f"))
                      else calc.num(f.get("cal_f"), "calibration", 32, 110))}
        nutrients = calc.schedule(pitched, og, fg, volume, p["demand"],
                                  p["product"], p["additions"])
    except ValueError as e:
        return bounce(str(e))
    batch = {
        "id": batch_id,
        "recipe": {"slug": r["slug"], "name": r["name"]},
        "pitched_at": calc.fmt_when(pitched),
        "volume_gal": round(volume, 2),
        "yeast": p["strain"],
        "target": {"og": p["og"], "abv": p["abv"], "fg": fg},
        "measured": measured,
        "added": {k: round(v, 2) for k, v in added.items()},
        "nutrients": nutrients,
        "notes": (f.get("notes") or "").strip(),
    }
    store.save_batch(batch)
    first = nutrients["additions"][0]
    from .views_batches import when
    hour = pitched.hour % 12 or 12
    pitched_text = f"{hour}:{pitched:%M} {'am' if pitched.hour < 12 else 'pm'}"
    return redirect(
        f"/batches/{batch_id}",
        f"Recorded {batch_id} — {num(volume)} gal, OG {sg(og)}"
        + (f", pH {num(ph, 2)}" if ph is not None else "")
        + f", {num(added['yeast_g'], 1)} g {p['strain']} pitched at "
        f"{pitched_text}. First {product_name(p['product'])} "
        f"{num(first['g'], 1)} g {when(first['due'])}; stop at SG "
        f"{sg(nutrients['stop_sg'])}.")

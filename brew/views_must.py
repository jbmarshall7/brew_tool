"""Must day: the recipe scaled to today's carboy, in floor order, and the
hydrometer check that says exactly what to stir in.

GET only in this step — the check is advice, and re-checking after a top-up
costs one page load. Nothing is written.
"""
from datetime import datetime

from . import calc
from .html import (banner, card, details, esc, field, gal_l, hidden, kv,
                   lb_oz, num, page as _page, raw, sg, textarea)
from .server import Response, redirect, route
from .sheet import product_name
from .views_recipes import plan_for

DEFAULT_CAL_F = 60
RECORD_FIELDS = ("id", "pitched_at", "volume_gal", "honey_lb", "water_gal",
                 "yeast_g", "goferm_g", "og", "ph", "notes")
CHECK_FIELDS = ("gal", "reading", "temp_f", "cal_f", "ph")


def steps(p):
    """The five things you do, in the order you do them."""
    pname = product_name(p["product"])
    n = p["additions"]
    feed_when = (", ".join(f"{h} h" for h in calc.TOSNA_HOURS[:n - 1])
                 + f", last by the 1/3 break (SG {sg(p['third_break_sg'])})"
                 if n > 1 else "with the pitch")
    cups = {1: "one cup", 2: "two cups", 3: "three cups", 4: "four cups",
            5: "five cups", 6: "six cups"}.get(n, f"{n} cups")
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
        ("Feed", f"{pname} {num(p['nutrient_g'], 1)} g as {n} × "
                 f"{num(p['per_addition_g'], 1)} g",
         f"Weigh {cups} now. {feed_when[0].upper() + feed_when[1:]}. "
         "Nothing after that: late nitrogen feeds the wrong things."),
    ]
    lis = "".join(
        f'<li><span class="stitle">{esc(t)}</span>'
        f'<span class="big">{esc(v)}</span>'
        f'<span class="mut">{esc(n_)}</span></li>' for t, v, n_ in items)
    return f'<ol class="steps">{lis}</ol>'


def check(p, params):
    """(banner_text, kind, corrected_og) for a reading, or (None, None, None)."""
    if calc.blank(params.get("reading")) and calc.blank(params.get("ph")):
        return None, None, None
    lines, kind, og = [], "ok", None
    cal_f = (DEFAULT_CAL_F if calc.blank(params.get("cal_f"))
             else calc.num(params.get("cal_f"), "hydrometer calibration", 32,
                           110, " °F"))
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
        c = calc.correction(og, p["og"], p["gal"], p["fg"], strain=p["strain"])
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
                f"{num(c['new_gal'])} gal — check the carboy has the room — "
                f"or {ride}.")
    if not calc.blank(params.get("ph")):
        v = calc.ph_verdict(calc.num(params.get("ph"), "pH", 0, 14))
        lines.append(v["text"])
        if v["kind"] == "warn":
            kind = "warn"
    return "\n".join(lines), kind, og


def record_form(slug, p, params, og, next_id, now=None):
    """Card: what went in, when the yeast did, and the id — prefilled."""
    g = lambda k, default="": params.get(k) if params.get(k) not in (None, "") else default
    now = now or datetime.now().strftime("%Y-%m-%dT%H:%M")
    og_val = g("og", f"{og:.4f}" if og is not None else "")
    keep = "".join(hidden(k, params.get(k, "")) for k in ("reading", "temp_f", "cal_f"))
    return f"""<form class="inline" method="post" action="/recipes/{esc(slug)}/must" id="record">
{keep}{hidden("gal", num(p["gal"]))}
<div class="grid">
<span>{field("id", "Batch id", g("id", next_id), "The next number; type your own to continue a numbering from elsewhere.", typ="text", required=True)}</span>
<span>{field("pitched_at", "Yeast pitched at", g("pitched_at", now), "The feeding clock starts here.", typ="datetime-local", step=None, required=True)}</span>
<span>{field("og", "OG (corrected)", og_val, "From the check above, or type it.", step="0.0001", required=True)}</span>
<span>{field("ph", "pH", g("ph"), "Optional.", step="0.01")}</span>
<span>{field("volume_gal", "In the carboy (gal)", g("volume_gal", num(p["gal"])), "If you diluted, the new volume — the feedings are sized from it.")}</span>
<span>{field("honey_lb", "Honey in (lb)", g("honey_lb", num(p["honey_lb"])), "What the scale said.")}</span>
<span>{field("water_gal", "Water in (gal)", g("water_gal", num(p["water_gal"])), None)}</span>
<span>{field("yeast_g", "Yeast (g)", g("yeast_g", num(p["yeast_g"], 1)), None)}</span>
<span>{field("goferm_g", "Go-Ferm (g)", g("goferm_g", num(p["goferm_g"], 1)), None)}</span>
</div>
{textarea("notes", "Notes", g("notes"), "Read low and stirred? Topped up? Say so here.")}
<button>Record the must</button></form>"""


def read_form(slug, gal, params, checked):
    cal_f = params.get("cal_f") or str(DEFAULT_CAL_F)
    body = f"""<form class="inline" method="get" action="/recipes/{esc(slug)}/must" id="read">
{hidden("gal", num(gal))}
<div class="grid">
<span>{field("reading", "Hydrometer reading", params.get("reading", ""), "What the glass says, e.g. 1.101.", step="0.001")}</span>
<span>{field("temp_f", "Sample temperature (°F)", params.get("temp_f", ""), "Blank = at the hydrometer's calibration temperature.")}</span>
<span>{field("ph", "pH", params.get("ph", ""), "Optional; the meter's number.", step="0.01")}</span>
</div>
{details("Hydrometer calibrated at", f'<div class="inner">{field("cal_f", "Calibration temperature (°F)", cal_f, "Printed on the hydrometer; 60 °F is common, some are 68 °F.")}</div>', open_=params.get("cal_f") not in (None, "", str(DEFAULT_CAL_F)))}
<button>{"Check again" if checked else "Check"}</button></form>"""
    return body


def must_page(req, params, msg=None, kind=None):
    r = req.store.load_recipe(req.args[0])
    last = req.store.last_batch(r["slug"])
    gal_text = params.get("gal") or num(r.get("design_gal"))
    gal = calc.num(gal_text, "volume", 0.1, 1000, " gal")
    p = plan_for(r, gal)
    if calc.blank(params.get("cal_f")) and last and \
            (last.get("measured") or {}).get("cal_f"):
        params = dict(params, cal_f=num(last["measured"]["cal_f"]))
    verdict, vkind, og = check(p, params)
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
    rf = read_form(r["slug"], gal, params, bool(verdict))
    try:
        year = calc.parse_when(params.get("pitched_at")).year
    except ValueError:
        year = datetime.now().year
    next_id = calc.next_batch_id(req.store.batch_ids(), year)
    rec = record_form(r["slug"], p, params, og, next_id)
    if verdict:
        head = ('<h2 id="check">Read it</h2>' + banner(verdict, vkind)
                + details("Check again", rf)
                + '<h2 id="record">Pitched? Record it</h2>' + rec)
    else:
        head = ('<h2 id="check">Read it</h2>' + rf
                + details("Record the must without a check", rec))
    body = (card(strip) + steps(p) + head
            + f'<p class="mut noprint"><a href="/recipes/{esc(r["slug"])}">'
              f"Back to {esc(r['name'])}</a> · this page prints clean for the "
              "barrel.</p>")
    return Response(_page(f"Must — {r['name']}", body, "/recipes",
                          msg or params.get("msg"),
                          kind or params.get("kind", "ok")))


@route("GET", r"/recipes/([a-z0-9-]+)/must")
def must(req):
    return must_page(req, req.params)


@route("POST", r"/recipes/([a-z0-9-]+)/must")
def record(req):
    """Write data/batches/<id>.json: the one file the owner wants later."""
    store = req.store
    r = store.load_recipe(req.args[0])
    f = req.form
    batch_id = (f.get("id") or "").strip().upper()
    gal = calc.num(f.get("gal") or r.get("design_gal"), "volume", 0.1, 1000)
    p = plan_for(r, gal)

    def bounce(text):
        from urllib.parse import urlencode
        keep = {k: f.get(k, "") for k in CHECK_FIELDS + RECORD_FIELDS
                if f.get(k)}
        return redirect(f"/recipes/{r['slug']}/must?{urlencode(keep)}#record",
                        text, "err")

    try:
        store.batch_path(batch_id)
    except ValueError as e:
        return bounce(str(e))
    if store.batch_exists(batch_id):
        return bounce(f"{batch_id} is already recorded — give this must the "
                      "next number.")
    pitched = calc.parse_when(f.get("pitched_at"))
    volume = calc.num(f.get("volume_gal"), "volume in the carboy", 0.1, 1000,
                      " gal")
    og = calc.num(f.get("og"), "OG", 0.950, 1.250)
    fg = p["fg"]
    ph = None if calc.blank(f.get("ph")) else calc.num(f.get("ph"), "pH", 0, 14)
    added = {"honey_lb": calc.num(f.get("honey_lb"), "honey", 0, 10000, " lb"),
             "water_gal": calc.num(f.get("water_gal"), "water", 0, 1000, " gal"),
             "yeast_g": calc.num(f.get("yeast_g"), "yeast", 0, 5000, " g"),
             "goferm_g": calc.num(f.get("goferm_g"), "Go-Ferm", 0, 5000, " g")}
    measured = {"og": og, "ph": ph,
                "expected_og": calc.expected_og(added["honey_lb"], volume)
                if added["honey_lb"] and volume else None,
                "reading": None if calc.blank(f.get("reading"))
                else calc.num(f.get("reading"), "reading", 0.950, 1.250),
                "sample_f": None if calc.blank(f.get("temp_f"))
                else calc.num(f.get("temp_f"), "sample temperature", 32, 140),
                "cal_f": DEFAULT_CAL_F if calc.blank(f.get("cal_f"))
                else calc.num(f.get("cal_f"), "calibration", 32, 110)}
    nutrients = calc.schedule(pitched, og, fg, volume, p["demand"],
                              p["product"], p["additions"])
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

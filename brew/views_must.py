"""Must day: the recipe scaled to today's carboy, in floor order, and the
hydrometer check that says exactly what to stir in.

GET only in this step — the check is advice, and re-checking after a top-up
costs one page load. Nothing is written.
"""
from . import calc
from .html import (banner, card, details, esc, field, gal_l, hidden, kv,
                   lb_oz, num, page as _page, raw, sg)
from .server import Response, route
from .sheet import product_name
from .views_recipes import plan_for

DEFAULT_CAL_F = 60


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
    """(banner_text, kind) for a hydrometer/pH reading, or (None, None)."""
    if calc.blank(params.get("reading")) and calc.blank(params.get("ph")):
        return None, None
    lines, kind = [], "ok"
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
    return "\n".join(lines), kind


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


@route("GET", r"/recipes/([a-z0-9-]+)/must")
def must(req):
    r = req.store.load_recipe(req.args[0])
    gal_text = req.params.get("gal") or num(r.get("design_gal"))
    gal = calc.num(gal_text, "volume", 0.1, 1000, " gal")
    p = plan_for(r, gal)
    verdict, kind = check(p, req.params)
    strip = kv([
        ("Making", f"{num(p['gal'])} gal of {r['name']}",
         f"target OG {sg(p['og'])} · {num(p['abv_if_dry'], 1)} % if dry · "
         f"{num(p['yeast_g'], 1)} g {p['strain']} · "
         f"{product_name(p['product'])} × {p['additions']}"),
    ])
    head = f'<h2 id="check">Read it</h2>' + (banner(verdict, kind) if verdict else "")
    body = (card(strip) + steps(p) + head
            + read_form(r["slug"], gal, req.params, bool(verdict))
            + f'<p class="mut noprint"><a href="/recipes/{esc(r["slug"])}">'
              f"Back to {esc(r['name'])}</a> · this page prints clean for the "
              "barrel.</p>")
    return Response(_page(f"Must — {r['name']}", body, "/recipes",
                          req.params.get("msg"), req.params.get("kind", "ok")))

"""The bench sheet: what `gal` of must at a target needs, with the working.

One renderer, reused by the Design page, the recipe page and the must page,
so the numbers and their stated assumptions read the same everywhere.
"""
from . import calc
from .html import banner, esc, gal_l, kv, lb_oz, num, pill, raw, sg

PRODUCT_NAMES = {"fermaid-o": "Fermaid O", "fermaid-k": "Fermaid K",
                 "dap": "DAP"}


def product_name(key):
    return PRODUCT_NAMES.get(key, key)


def feed_when(n, stop_sg):
    """The timing sentence for `n` feedings — the same rule schedule() uses:
    24 h apart, the last by day 7 or the 1/3 break."""
    if n <= 1:
        return f"24 h after pitch, or the 1/3 break (SG {stop_sg}) if sooner"
    hours = ", ".join(f"{24 * i} h" for i in range(1, n))
    return (f"{hours}, last by day {calc.TOSNA_LAST_DAY} or the 1/3 break "
            f"(SG {stop_sg})")


def value(main, small=None):
    return raw(esc(main) + (f" <small>{esc(small)}</small>" if small else ""))


def rows(p):
    """The kv rows for a plan dict from calc.plan()."""
    og_note = (f"1.000 + {num(p['abv'], 1)} ÷ {calc.ABV_FACTOR}"
               if p["strength_by"] == "abv"
               else f"strength set by OG — {num(p['abv_if_dry'], 1)} % if dry")
    if p["fg"] != 1.0 and p["strength_by"] == "abv":
        og_note = f"{sg(p['fg'])} + {num(p['abv'], 1)} ÷ {calc.ABV_FACTOR}"
    pname = product_name(p["product"])
    when = feed_when(p["additions"], sg(p["third_break_sg"]))
    fr = p.get("fruit")
    rows = [
        ("OG", sg(p["og"]), og_note),
        ("Honey", value(lb_oz(p["honey_lb"]), f"{num(p['honey_lb_per_gal'])} lb/gal"),
         (f"{num(p['target_pts'], 1)} points, less {num(fr['points'], 1)} from "
          f"the {fr['item']}, × {num(p['gal'])} gal ÷ "
          f"{p['constants']['PPG_PER_LB_HONEY']} — the fruit supplies the rest"
          if fr else
          f"{num(p['target_pts'], 1)} points × {num(p['gal'])} gal ÷ "
          f"{p['constants']['PPG_PER_LB_HONEY']} pts per lb per gal — a planning "
          "figure; the hydrometer has the last word")),
        ("Honey's own room", f"~{num(p['honey_gal'])} gal",
         f"{num(p['honey_lb'])} ÷ {num(calc.HONEY_LB_PER_GAL)} lb per gal"),
        ("Water", value(gal_l(p["water_gal"]) if p["water_gal"] > 0 else "none",
                        f"then top to the {num(p['gal'])} gal mark"
                        if p["water_gal"] > 0 else
                        "the honey and fruit fill it"),
         (f"{num(p['gal'])} − {num(p['honey_gal'])} honey"
          + (f" − {num(fr['gal'])} fruit" if fr else "")
          + "; the mark is the truth, this is where to start")
         if p["water_gal"] > 0 else
         f"they come to ~{num(p['gal'] + p.get('overfill_gal', 0))} gal on "
         "their own"),
        ("Yeast", value(f"{num(p['yeast_g'], 1)} g {p['strain']}",
                        f"({p['sachets']} sachet{'s' if p['sachets'] != 1 else ''})"
                        if p["sachets"] <= 10 else
                        "(weigh it from a 500 g brick)"),
         f"{num(p['yeast_rate'], 1)} g per gal"
         + (f" above {calc.HIGH_OG_PITCH_SG:.3f}" if p["high_og_pitch"] else "")
         + f" = {num(p['yeast_by_rule'], 1)} g, to the nearest "
         f"{num(calc.YEAST_PACKET_G)} g"
         + (" sachet" if p["sachets"] <= 10 else "")),
        ("Go-Ferm", f"{num(p['goferm_g'], 1)} g in {calc.ml_text(p['goferm_water_ml'])} "
                    f"water at {calc.REHYDRATE_F} °F",
         f"{calc.GOFERM_G_PER_G_YEAST} g per g of yeast; "
         f"{num(calc.GOFERM_WATER_ML_PER_G)} mL per g Go-Ferm. Twenty minutes, "
         "then temper with must until it's within 10 °F before they meet"),
        ("YAN", f"{p['yan_ppm']} ppm",
         f"{p['constants']['YAN_PER_ABV.' + p['demand']]} "
         f"ppm per % ABV ({p['demand']} demand) × {num(p['abv'], 1)}"),
        (pname, value(f"{num(p['nutrient_g'], 1)} g",
                      f"as {p['additions']} × {num(p['per_addition_g'], 1)} g"),
         f"{p['yan_ppm']} ÷ {num(p['constants']['YAN_PPM_PER_G_PER_GAL.' + p['product']])} "
         f"ppm per g per gal × {num(p['gal'])} gal; at {when}"),
        ("Stop nitrogen at", f"SG {sg(p['third_break_sg'])}",
         "OG − (OG − FG) ÷ 3 — nothing after this: late nitrogen feeds the "
         "wrong things"),
        ("Expect", f"{num(p['abv_if_dry'], 1)} % if it finishes at {sg(p['fg'])}",
         f"(OG − FG) × {calc.ABV_FACTOR} — the simple formula. At high gravity "
         f"it reads low: the fuller one says "
         f"{num(calc.abv_alt(p['og'], p['fg']), 1)} % here. Near the 16 % "
         "excise line, confirm with a lab measurement"),
    ]
    if fr:
        rows.insert(2, (
            "Fruit", value(f"{num(fr['lb'])} lb {fr['item']}",
                           f"~{num(fr['gal'])} gal, {num(fr['sugar_lb'])} lb sugar"),
            f"{fr['sugar_pct']} % fermentable sugar → {num(fr['points'], 1)} "
            + ("points, already dissolved — the hydrometer reads them on must "
               "day" if calc.fruit_in_solution(fr["item"]) else
               "points; confirm OG by hydrometer once the fruit gives up its "
               "sugar")))
    return rows


def extras_card(extras, gal, design_gal):
    """Everything else that goes in — spice, citrus, oak, enzyme, the honey
    that back-sweetens — grouped by when, at `gal`."""
    if not extras:
        return ""
    factor = gal / design_gal if design_gal else 1.0
    groups = []
    for e in extras:
        if not groups or groups[-1][0] != e.get("when", ""):
            groups.append((e.get("when", ""), []))
        groups[-1][1].append(e)

    def li(e):
        amt = calc.extra_amount(e, factor)
        return ("<li>" + (f'<span class="amt">{esc(amt)}</span> ' if amt else "")
                + f"{esc(e['what'])}</li>")
    rows = "".join(f'<div class="kv"><b>{esc(when or "Also")}</b><ul>'
                   + "".join(li(e) for e in items) + "</ul></div>"
                   for when, items in groups)
    scaled = abs(factor - 1.0) >= 0.005
    note = ((f"Scaled from the recipe's {calc.vol_text(design_gal)}. " if scaled
             else "") + "A line without an amount is as written.")
    return (f'<div class="card extras"><div class="sheet-head"><h2>Also goes '
            f'in</h2>{pill("at " + calc.vol_text(gal))}</div>{rows}'
            f'<p class="mut">{esc(note)}</p></div>')


def render_sheet(p, title=None):
    head = ""
    if title:
        # the target OG reads as a tag beside the heading, so the sheet's
        # headline number is visible before you scan the rows
        head = (f'<div class="sheet-head"><h2>{esc(title)}</h2>'
                f'{pill("OG " + sg(p["og"]))}</div>')
    warn = "".join(banner(w, "warn") for w in p["warnings"])
    return f'<div class="card">{head}{kv(rows(p))}</div>{warn}'

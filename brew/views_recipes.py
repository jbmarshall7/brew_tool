"""Save a design as a recipe; the recipe list; a recipe at any volume."""
from datetime import date

from . import calc
from .html import (card, details, esc, field, hidden, kv, next_link, num,
                   page as _page, pill, raw, sg, table)
from .server import Response, redirect, route
from .sheet import product_name, render_sheet
from .store import slugify
from .views_design import DEFAULTS, inputs_from, plan_from

# the plan keys that are inputs, not results — everything else is `computed`
INPUT_KEYS = {"strength_by", "gal", "fg", "yeast_g", "strain", "demand",
              "product", "additions", "yeast_default_g", "high_og_pitch",
              "feed_rows", "sachets", "target_pts"}


def computed_from(p):
    return {k: v for k, v in p.items() if k not in INPUT_KEYS}


def recipe_from_form(f):
    """A recipe dict from the save form, or a ValueError in plain words."""
    name = (f.get("name") or "").strip()
    if not name:
        raise ValueError("Give the recipe a name — the honey and the strength "
                         "make a good one.")
    inp = inputs_from(f)
    p = plan_from(inp)
    by = p["strength_by"]
    return {
        "slug": slugify(name), "name": name,
        "honey": (f.get("honey") or "").strip(),
        "yeast": p["strain"], "yeast_g": p["yeast_g"],
        "strength": {"by": by,
                     "abv": p["abv"] if by == "abv" else None,
                     "og": p["og"] if by == "og" else None,
                     "fg": p["fg"]},
        "design_gal": p["gal"], "demand": p["demand"], "product": p["product"],
        "additions": p["additions"],
        "notes": (f.get("notes") or "").strip(),
        "updated": date.today().isoformat(),
        "computed": computed_from(p),
    }


def inputs_from_recipe(r):
    """Design-page inputs that reproduce a saved recipe."""
    s = r.get("strength") or {}
    return {"gal": num(r.get("design_gal"), 2),
            "abv": num(s.get("abv"), 2) if s.get("by") == "abv" else "",
            "og": f"{s['og']:.4f}" if s.get("by") == "og" and s.get("og") else "",
            "fg": f"{s.get('fg', 1.0):.3f}",
            "yeast": r.get("yeast") or DEFAULTS["yeast"],
            "yeast_g": num(r.get("yeast_g"), 1),
            "demand": r.get("demand") or "medium",
            "additions": str(r.get("additions") or 4)}


def plan_for(r, gal):
    """The recipe scaled to `gal`; yeast grams scale with the volume."""
    inp = inputs_from_recipe(r)
    design_gal = r.get("design_gal") or float(inp["gal"])
    scale = float(gal) / design_gal if design_gal else 1.0
    inp["gal"] = str(gal)
    inp["yeast_g"] = num(round((r.get("yeast_g") or 0) * scale, 1), 1)
    return plan_from(inp)


def strength_line(r):
    c = r.get("computed") or {}
    return f"{num(c.get('abv_if_dry'), 1)} % · OG {sg(c.get('og') or 0)}"


# --- POST /recipes: save --------------------------------------------------
@route("POST", "/recipes")
def save(req):
    store = req.store
    recipe = recipe_from_form(req.form)
    from_slug = (req.form.get("from_slug") or "").strip()
    if from_slug:
        # a redesign keeps its slug: the name is a label, the slug is the file
        store.load_recipe(from_slug)
        recipe["slug"] = from_slug
        verb = "Updated"
    elif store.recipe_exists(recipe["slug"]):
        keep = {k: req.form.get(k, "") for k in DEFAULTS}
        keep.update({"name": req.form.get("name", ""),
                     "honey": req.form.get("honey", ""),
                     "notes": req.form.get("notes", "")})
        from urllib.parse import urlencode
        return redirect("/?" + urlencode(keep),
                        f"There's already a recipe called {recipe['name']}. "
                        "Open it and Redesign, or give this one another name.",
                        "err")
    else:
        verb = "Saved"
    store.save_recipe(recipe)
    c = recipe["computed"]
    return redirect(
        f"/recipes/{recipe['slug']}",
        f"{verb} {recipe['name']} — {num(c['abv_if_dry'], 1)} % (OG "
        f"{sg(c['og'])}), {num(c['honey_lb_per_gal'])} lb "
        f"{recipe['honey'] or 'honey'} per gallon; {num(c['honey_lb'])} lb for "
        f"{num(recipe['design_gal'])} gal.")


# --- GET /recipes: the list -------------------------------------------------
@route("GET", "/recipes")
def recipes(req):
    rows = []
    for r in req.store.list_recipes():
        rows.append([raw(f'<a href="/recipes/{esc(r["slug"])}">'
                         f'{esc(r["name"])}</a>'),
                     strength_line(r), r.get("yeast") or "",
                     r.get("honey") or "",
                     f"{num(r.get('design_gal'))} gal"])
    body = table(["Recipe", "Strength", "Yeast", "Honey", "Designed at"], rows,
                 empty="No recipes yet. Design one — it's two numbers.")
    if not rows:
        body += next_link("/", "Design a recipe")
    return Response(_page("Recipes", body, "/recipes", req.params.get("msg"),
                          req.params.get("kind", "ok")))


# --- GET /recipes/<slug>: one recipe, at any volume --------------------------
@route("GET", r"/recipes/([a-z0-9-]+)")
def recipe(req):
    r = req.store.load_recipe(req.args[0])
    gal_text = req.params.get("gal") or num(r.get("design_gal"))
    p = plan_for(r, calc.num(gal_text, "volume", 0.1, 1000, " gal"))
    s = r.get("strength") or {}
    strength = (f"{num(s.get('abv'), 1)} % ABV" if s.get("by") == "abv"
                else f"OG {sg(s.get('og') or 0)}")
    identity = kv([
        ("Strength", strength,
         f"OG {sg(p['og'])} · {num(p['abv_if_dry'], 1)} % if dry at "
         f"FG {sg(p['fg'])}"),
        ("Honey", r.get("honey") or "—",
         f"{num(r['computed']['honey_lb_per_gal'])} lb per gallon"),
        ("Yeast", f"{num(r.get('yeast_g'), 1)} g {r.get('yeast')} "
                  f"at {num(r.get('design_gal'))} gal", None),
        ("Nutrients", f"{product_name(r.get('product'))} × "
                      f"{r.get('additions')}, {r.get('demand')} demand", None),
    ])
    scale_form = f"""<form class="inline" method="get" action="/recipes/{esc(r['slug'])}">
<div class="grid"><span>{field("gal", "Show the sheet for (gal)", num(p['gal']), "Your carboys: 5, 6, 6.8.")}</span></div>
<button>Show</button></form>"""
    notes = details("Notes", f'<div class="inner">{esc(r["notes"])}</div>') \
        if r.get("notes") else ""
    body = (card(identity)
            + next_link(f"/?recipe={r['slug']}", "Redesign")
            + scale_form
            + render_sheet(p, f"At {num(p['gal'])} gal you'll need")
            + notes
            + f'<p class="mut">Updated {esc(r.get("updated") or "—")}. '
              f'File: data/recipes/{esc(r["slug"])}.json</p>')
    return Response(_page(r["name"], body, "/recipes", req.params.get("msg"),
                          req.params.get("kind", "ok")))

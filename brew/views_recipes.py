"""Save a design as a recipe; the recipe list; a recipe at any volume."""
from datetime import date
from urllib.parse import urlencode

from . import calc
from .html import (banner, card, details, esc, field, hidden, kv,
                   next_link, num, page as _page, pill, raw, sg, table)
from .server import Response, redirect, route
from .sheet import product_name, render_sheet
from .store import slugify
from .views_design import DEFAULTS, inputs_from, plan_from

# the plan keys that are inputs, not results — everything else is `computed`
INPUT_KEYS = {"strength_by", "gal", "fg", "strain", "demand", "product",
              "additions", "high_og_pitch", "feed_rows", "target_pts",
              "yeast_rate", "yeast_by_rule", "fruit"}


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
        "yeast": p["strain"],
        "strength": {"by": by,
                     "abv": p["abv"] if by == "abv" else None,
                     "og": p["og"] if by == "og" else None,
                     "fg": p["fg"]},
        "design_gal": p["gal"], "demand": p["demand"], "product": p["product"],
        "additions": p["additions"],
        "fruit": ({"item": p["fruit"]["item"], "lb": p["fruit"]["lb"],
                   "sugar_pct": p["fruit"]["sugar_pct"]}
                  if p.get("fruit") else None),
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
            "demand": r.get("demand") or "medium",
            "additions": str(r.get("additions") or 4),
            "fruit": (r.get("fruit") or {}).get("item", ""),
            "fruit_lb": (str((r.get("fruit") or {}).get("lb", ""))
                         if r.get("fruit") else ""),
            "fruit_pct": (str((r.get("fruit") or {}).get("sugar_pct", ""))
                          if r.get("fruit") else "")}


def plan_for(r, gal):
    """The recipe at `gal`: same targets, everything else re-derived."""
    inp = inputs_from_recipe(r)
    inp["gal"] = str(gal)
    return plan_from(inp)


def strength_line(r):
    """Always from a fresh plan, never from the file's cached `computed`."""
    try:
        p = plan_for(r, r.get("design_gal") or 1)
    except (ValueError, TypeError, KeyError):
        return "—"
    return f"{num(p['abv_if_dry'], 1)} % · OG {sg(p['og'])}"


def keep_design(form):
    """The Design page query that reproduces what the owner had typed."""
    keep = {k: form.get(k, "") for k in DEFAULTS}
    keep.update({"name": form.get("name", ""), "honey": form.get("honey", ""),
                 "notes": form.get("notes", "")})
    if form.get("from_slug"):
        keep["recipe"] = form["from_slug"]
    return "/design?" + urlencode(keep)


# --- POST /recipes: save --------------------------------------------------
@route("POST", "/recipes")
def save(req):
    store = req.store
    try:
        recipe = recipe_from_form(req.form)
    except ValueError as e:
        # back to the Design page with everything typed still in place
        return redirect(keep_design(req.form), str(e), "err")
    from_slug = (req.form.get("from_slug") or "").strip()
    if from_slug:
        # a redesign keeps its slug: the name is a label, the slug is the file
        store.load_recipe(from_slug)
        recipe["slug"] = from_slug
        verb = "Updated"
    elif store.recipe_exists(recipe["slug"]):
        return redirect(keep_design(req.form),
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
        gal = num(r.get("design_gal"))
        rows.append([raw(f'<a href="/recipes/{esc(r["slug"])}">'
                         f'{esc(r["name"])}</a>'
                         f'<span class="sub">{esc(strength_line(r))} · '
                         f'{esc(r.get("yeast") or "")}'
                         + (f' · {esc(r["honey"])}' if r.get("honey") else "")
                         + "</span>"),
                     raw(f'<a class="btn" href="/recipes/{esc(r["slug"])}/must'
                         f'?gal={esc(gal)}">Make {esc(gal)} gal</a>')])
    body = table(["Recipe", "Must"], rows,
                 empty="No recipes yet. Design one — it's two numbers.")
    if not rows:
        body += next_link("/design", "Design a recipe")
    problems = req.store.unreadable()
    if problems:
        body = banner("Some files couldn't be read and are left out:\n"
                      + "\n".join(problems), "warn") + body
    return Response(_page("Recipes", body, "/recipes", req.params.get("msg"),
                          req.params.get("kind", "ok")))


# --- GET /recipes/<slug>: one recipe, at any volume --------------------------
@route("GET", r"/recipes/([a-z0-9-]+)")
def recipe(req):
    r = req.store.load_recipe(req.args[0])
    last = req.store.last_batch(r["slug"])
    gal_text = (req.params.get("gal")
                or (num(last["volume_gal"]) if last and last.get("volume_gal")
                    else None)
                or num(r.get("design_gal")))
    p = plan_for(r, calc.num(gal_text, "volume", 0.1, 1000, " gal"))
    s = r.get("strength") or {}
    strength = (f"{num(s.get('abv'), 1)} % ABV" if s.get("by") == "abv"
                else f"OG {sg(s.get('og') or 0)}")
    identity = kv([
        ("Strength", strength,
         f"OG {sg(p['og'])} · {num(p['abv_if_dry'], 1)} % if dry at "
         f"FG {sg(p['fg'])}"),
        ("Honey", r.get("honey") or "—",
         f"{num(p['honey_lb_per_gal'])} lb per gallon"),
        ("Yeast", f"{r.get('yeast') or '—'}",
         f"{num(p['yeast_g'], 1)} g at {num(p['gal'])} gal, whole sachets"),
        ("Nutrients", f"{product_name(r.get('product'))} × "
                      f"{r.get('additions')}, {r.get('demand')} demand", None),
    ])
    scale_form = f"""<form class="inline" method="get" action="/recipes/{esc(r['slug'])}/must">
<div class="grid"><span>{field("gal", "How much are you making? (gal)", num(p['gal']), "Your carboys: 5, 6, 6.8.")}</span></div>
<button>Make must</button>
<button class="quiet" formaction="/recipes/{esc(r['slug'])}">Just show the sheet</button></form>"""
    notes = details("Notes", f'<div class="inner">{esc(r["notes"])}</div>') \
        if r.get("notes") else ""
    batches = req.store.batches_for_recipe(r["slug"])
    if batches:
        from .views_batches import when
        brows = [[raw(f'<a href="/batches/{esc(b["id"])}">{esc(b["id"])}</a>'),
                  when(b.get("pitched_at")), f"{num(b.get('volume_gal'))} gal",
                  sg((b.get("measured") or {}).get("og") or 0)
                  if (b.get("measured") or {}).get("og") else "—"]
                 for b in batches]
        batch_block = "<h2>Musts recorded</h2>" + table(
            ["Batch", "Pitched", "Volume", "OG"], brows)
    else:
        batch_block = ""
    body = (card(identity)
            + next_link(f"/design?recipe={r['slug']}", "Redesign")
            + scale_form
            + render_sheet(p, f"At {num(p['gal'])} gal you'll need")
            + notes + batch_block
            + f'<p class="mut">Updated {esc(r.get("updated") or "—")}. '
              f'File: data/recipes/{esc(r["slug"])}.json</p>')
    return Response(_page(r["name"], body, "/recipes", req.params.get("msg"),
                          req.params.get("kind", "ok")))

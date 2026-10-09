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
    """The recipe at `gal`: same targets, everything else re-derived —
    including the fruit, which scales with the batch like everything else
    (it used to stay at the design weight, so half a batch got double the
    fruit and half the honey)."""
    inp = inputs_from_recipe(r)
    inp["gal"] = str(gal)
    if inp.get("fruit_lb") and r.get("design_gal"):
        lb = float(inp["fruit_lb"]) * float(gal) / float(r["design_gal"])
        inp["fruit_lb"] = f"{round(lb, 2):g}"
    return plan_from(inp)


def notes_block(r, gal, open_=False):
    """A recipe's notes as written, a line per line, and — when the batch
    isn't the size they were written for — the factor to scale their
    amounts by (they're prose, so the sheet can't scale them itself)."""
    if not r.get("notes"):
        return ""
    design = r.get("design_gal")
    scale = ""
    if design and abs(gal - design) > 0.005:
        scale = (f'<p class="mut">Amounts in these notes are written for '
                 f'{esc(calc.vol_text(design))}; at {esc(calc.vol_text(gal))} '
                 f'multiply them × {num(gal / design, 2)}.</p>')
    return details("Notes", f'<div class="inner notes">{scale}'
                            f'{esc(r["notes"])}</div>', open_)


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
                 "notes": form.get("notes", ""),
                 # a refused redesign keeps its "what changed" line too
                 "changelog": form.get("changelog", "")})
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

    def snapshot(rec, version, changelog):
        c = rec["computed"]
        return {"version": version, "date": rec["updated"],
                "changelog": changelog,
                "abv_if_dry": c.get("abv_if_dry"), "og": c.get("og"),
                "honey_lb": c.get("honey_lb"), "strength": rec["strength"],
                "fruit": rec.get("fruit")}

    if from_slug:
        # a redesign keeps its slug and appends a version with a changelog,
        # so last year's recipe still reads as it was
        prev = store.load_recipe(from_slug)
        changelog = (req.form.get("changelog") or "").strip()
        if not changelog:
            return redirect(keep_design(req.form),
                            "A redesign needs one line on what changed — that "
                            "is the whole point of keeping versions.", "err")
        recipe["slug"] = from_slug
        recipe["version"] = (prev.get("version") or 1) + 1
        recipe["history"] = (prev.get("history") or [])[:]
        recipe["history"].append(snapshot(recipe, recipe["version"], changelog))
        verb = "Updated"
    elif store.recipe_exists(recipe["slug"]):
        return redirect(keep_design(req.form),
                        f"There's already a recipe called {recipe['name']}. "
                        "Open it and Redesign, or give this one another name.",
                        "err")
    else:
        recipe["version"] = 1
        recipe["history"] = [snapshot(recipe, 1, "initial version")]
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
    """Every recipe, and one box to make them all at your size: type 6, a
    bucket's 7.9 gal or the conical's 3 bbl once, and every Make button and
    recipe link follows it. Blank shows each at the size it was published."""
    msg, kind = req.params.get("msg"), req.params.get("kind", "ok")
    size_text = (req.params.get("size") or "").strip()
    size = None
    if size_text:
        try:
            size = calc.parse_volume(size_text, "size")
        except ValueError as e:
            msg, kind = str(e), "err"
    rows = []
    for r in req.store.list_recipes():
        g = size or r.get("design_gal") or 1
        q = esc(urlencode({"gal": num(g)}))
        open_at = f"?{q}" if size else ""
        rows.append([raw(f'<a href="/recipes/{esc(r["slug"])}{open_at}">'
                         f'{esc(r["name"])}</a>'
                         f'<span class="sub">{esc(strength_line(r))} · '
                         f'{esc(r.get("yeast") or "")}'
                         + (f' · {esc(r["honey"])}' if r.get("honey") else "")
                         + "</span>"),
                     raw(f'<a class="btn" href="/recipes/{esc(r["slug"])}/must'
                         f'?{q}">Make {esc(calc.vol_text(g))}</a>')])
    sizer = f"""<form class="inline noprint" method="get" action="/recipes">
<div class="grid"><span>{field("size", "Make them at", size_text, "Gallons, BBL or liters: 6, 7.9 gal for a bucket, 3 bbl for the conical. Blank shows each at the size it was published.", typ="text", attrs='placeholder="6 gal"')}</span></div>
<button>Show</button></form>"""
    body = (sizer if rows else "") + table(
        ["Recipe", "Must"], rows,
        empty="No recipes yet. Design one — it's two numbers.")
    if not rows:
        body += next_link("/design", "Design a recipe")
    problems = req.store.unreadable()
    if problems:
        body = banner("Some files couldn't be read and are left out:\n"
                      + "\n".join(problems), "warn") + body
    return Response(_page("Recipes", body, "/recipes", msg, kind))


# --- GET /recipes/<slug>: one recipe, at any volume --------------------------
@route("GET", r"/recipes/([a-z0-9-]+)")
def recipe(req):
    r = req.store.load_recipe(req.args[0])
    last = req.store.last_batch(r["slug"])
    gal_text = (req.params.get("gal")
                or (num(last["volume_gal"]) if last and last.get("volume_gal")
                    else None)
                or num(r.get("design_gal")))
    p = plan_for(r, calc.parse_volume(gal_text, "volume"))
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
         f"{num(p['yeast_g'], 1)} g at {calc.vol_text(p['gal'])}"
         + (", whole sachets" if p["sachets"] <= 10 else ", weighed")),
        ("Nutrients", f"{product_name(r.get('product'))} × "
                      f"{r.get('additions')}, {r.get('demand')} demand", None),
    ])
    scale_form = f"""<form class="inline" method="get" action="/recipes/{esc(r['slug'])}/must">
<div class="grid"><span>{field("gal", "How much are you making?", req.params.get("gal") or f"{num(p['gal'])} gal", "Gallons, BBL or liters: 6, 6.8 gal, 3 bbl, 350 L. A BBL is 31 gal.", typ="text")}</span></div>
<button>Make must</button>
<button class="quiet" formaction="/recipes/{esc(r['slug'])}">Just show the sheet</button></form>"""
    notes = notes_block(r, p["gal"], open_=True)
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
    hist = r.get("history") or []
    if len(hist) > 1:
        hrows = [[f"v{h['version']}", esc(h.get("date") or ""),
                  f"{num(h.get('abv_if_dry'), 1)} % · OG {sg(h.get('og') or 0)}",
                  h.get("changelog") or ""]
                 for h in reversed(hist)]
        version_block = (f"<h2>Versions (now v{r.get('version', 1)})</h2>"
                         + table(["", "Date", "Strength", "What changed"],
                                 hrows)
                         + '<p class="mut">A batch pins the version it was made '
                           "from, so last year's mead still reads as it was.</p>")
    else:
        version_block = ""
    body = (card(identity)
            + next_link(f"/design?recipe={r['slug']}", "Redesign")
            + scale_form
            + render_sheet(p, f"At {calc.vol_text(p['gal'])} you'll need")
            + notes + batch_block + version_block
            + f'<p class="mut">Updated {esc(r.get("updated") or "—")}, '
              f'v{r.get("version", 1)}. '
              f'File: data/recipes/{esc(r["slug"])}.json</p>')
    return Response(_page(r["name"], body, "/recipes", req.params.get("msg"),
                          req.params.get("kind", "ok")))

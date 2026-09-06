"""A recorded must: the facts, and the four dated feedings."""
from . import calc
from .html import card, esc, kv, next_link, num, page as _page, sg, table
from .server import Response, route
from .sheet import product_name


def when(text):
    """'2026-09-04T15:40' → 'Fri Sep 4, 3:40 pm'."""
    try:
        dt = calc.parse_when(text)
    except ValueError:
        return text or "—"
    hour = dt.hour % 12 or 12
    return (f"{dt:%a %b} {dt.day}, {hour}:{dt:%M} "
            f"{'am' if dt.hour < 12 else 'pm'}")


def feed_table(b):
    n = b.get("nutrients") or {}
    pname = product_name(n.get("product"))
    rows = [[f"#{a.get('n', i + 1)}", f"{num(a.get('g'), 1)} g {pname}",
             when(a.get("due")), a.get("rule") or ""]
            for i, a in enumerate(n.get("additions") or [])]
    return table(["", "Feed", "When", "Or sooner if"], rows,
                 empty="No feeding schedule on this batch.")


def measured_line(b):
    m = b.get("measured") or {}
    t = b.get("target") or {}
    og = m.get("og")
    if og is None:
        return "—"
    read = ""
    if m.get("reading") is not None and m.get("sample_f") is not None:
        read = (f" (read {sg(m['reading'])} at {num(m['sample_f'])} °F, "
                f"hydrometer {num(m.get('cal_f') or 60)} °F)")
    return f"OG {sg(og)}{read} vs target {sg(t.get('og') or 0)}"


@route("GET", r"/batches/(B-\d{4}-\d{3})")
def batch(req):
    b = req.store.load_batch(req.args[0])
    r = b.get("recipe") or {}
    m = b.get("measured") or {}
    a = b.get("added") or {}
    n = b.get("nutrients") or {}
    facts = kv([
        ("Recipe", f"{r.get('name') or r.get('slug') or '—'}", None),
        ("In the carboy", f"{num(b.get('volume_gal'))} gal", None),
        ("Pitched", when(b.get("pitched_at")), None),
        ("Gravity", measured_line(b),
         (f"{num(a.get('honey_lb'))} lb in {num(b.get('volume_gal'))} gal "
          f"should read about {sg(m['expected_og'])} at "
          f"{calc.PPG_PER_LB_HONEY} pts per lb per gal — lower than that and "
          "the honey ran light or wasn't mixed in yet")
         if m.get("expected_og") else None),
        ("pH", f"{num(m.get('ph'), 2)}" if m.get("ph") is not None else "—",
         None),
        ("Went in", f"{num(a.get('honey_lb'))} lb honey · "
                    f"{num(a.get('water_gal'))} gal water · "
                    f"{num(a.get('yeast_g'), 1)} g {b.get('yeast') or ''} "
                    f"+ {num(a.get('goferm_g'), 1)} g Go-Ferm", None),
        ("If it goes dry", f"{num(calc.abv(m['og'], (b.get('target') or {}).get('fg', 1.0)), 1)} %"
         if m.get("og") is not None else "—", None),
    ])
    stop = n.get("stop_sg") or next(
        (a.get("stop_sg") for a in n.get("additions") or [] if a.get("stop_sg")),
        None)
    feed = ("<h2>" + esc(f"Feed — {product_name(n.get('product'))} "
                         f"{num(n.get('total_g'), 1)} g for "
                         f"{n.get('yan_ppm', '—')} ppm YAN, sized from OG "
                         f"{sg(n['from_og']) if n.get('from_og') else '—'}")
            + "</h2>" + feed_table(b)
            + '<p class="mut">'
            + (f"Stop at SG {sg(stop)} whatever the calendar says. " if stop
               else "")
            + "Nothing after this: late nitrogen feeds the wrong things.</p>")
    notes = (f"<h2>Notes</h2><p>{esc(b['notes'])}</p>" if b.get("notes")
             else "")
    body = (card(facts) + feed + notes
            + next_link(f"/recipes/{esc(r.get('slug') or '')}",
                        f"Back to {r.get('name') or 'the recipe'}")
            + f'<p class="mut">File: data/batches/{esc(b["id"])}.json — this '
              "page prints clean for the barrel.</p>")
    return Response(_page(f"{b['id']} — {r.get('name') or ''}", body,
                          "/recipes", req.params.get("msg"),
                          req.params.get("kind", "ok")))

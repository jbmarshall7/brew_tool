"""A batch: what went in, what it is doing now, and what to do about it.

The page's whole job is one gravity in, three columns out. Drop, ABV so far
and attenuation are computed on every render from the readings and the pitch
date, and so is the sentence at the top — there is no status here for anyone
to keep up to date.
"""
from datetime import datetime

from . import calc
from .html import (banner, card, esc, field, hidden, kv, next_link, num,
                   page as _page, pill, raw, sg, table, textarea)
from .server import Response, redirect, route
from .chart import curve
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


def feed_table(b, now=None):
    """The dated feedings, what the schedule says about each, and a one-tap
    way to record the one you just gave."""
    n = b.get("nutrients") or {}
    pname = product_name(n.get("product"))
    now = now or datetime.now()
    nxt, shut = calc.next_feed(b, now)
    given = {f.get("n"): f for f in b.get("feeds") or []}
    rows = []
    for a in n.get("additions") or []:
        num_ = a.get("n")
        done = given.get(num_)
        try:
            due = calc.parse_when(a.get("due"))
        except ValueError:
            due = None
        if done:
            state, kind = "given", "ok"
        elif shut:
            state, kind = "passed", ""
        elif nxt is not None and num_ == nxt.get("n") and due is not None \
                and due.date() <= now.date():
            state, kind = "due", "warn"
        else:
            state, kind = "waiting", ""
        if done:
            action = raw(f'<span class="sub">{esc(when(done["at"]))}'
                         + (f' · {esc(done["note"])}' if done.get("note")
                            else "") + "</span>")
        elif shut:
            action = ""
        else:
            action = raw(
                f'<form class="mini noprint" method="post" '
                f'action="/batches/{esc(b["id"])}/feed">'
                f'{hidden("n", str(num_))}'
                f'<button class="quiet">I gave this</button></form>')
        rows.append([f"#{num_}", f"{num(a.get('g'), 1)} g {pname}",
                     when(a.get("due")), raw(str(pill(state, kind))),
                     action, a.get("rule") or ""])
    return table(["", "Feed", "When", "", "", "Or sooner if"], rows,
                 empty="No feeding schedule on this batch.")


def ledger_table(b):
    """One row per reading. Only the gravity was ever typed."""
    og = (b.get("measured") or {}).get("og")
    rows = calc.ledger(og, b.get("pitched_at"), b.get("readings"))
    body = [[when(r["at"]), str(r["day"]),
             sg(r["sg"]),
             "—" if r["drop"] is None else f"{num(r['drop'], 1)} pts",
             "—" if r["abv"] is None else f"{num(r['abv'], 1)} %",
             "—" if r["atten"] is None else f"{r['atten']} %",
             raw(f'<span class="sub">{esc(r["note"])}</span>'
                 if r["note"] else "")]
            for r in reversed(rows)]
    return table(["When", "Day", "Gravity", "Drop", "ABV", "Att.", "Note"],
                 body,
                 empty="No readings yet — the first one tells you it caught.")


def stats(b, now=None):
    """Now · ABV so far · Attenuated · Day, the four figures at a glance."""
    og = (b.get("measured") or {}).get("og")
    now_sg = calc.current_sg(b)
    day = calc.day_of(b["pitched_at"], now or datetime.now())
    cells = [
        ("Now", sg(now_sg) if now_sg is not None else "—"),
        ("ABV so far",
         f"{num(calc.abv(og, now_sg), 1)} %" if og and now_sg else "—"),
        ("Attenuated",
         f"{calc.attenuation(og, now_sg)} %" if og and now_sg else "—"),
        ("Day", str(day)),
    ]
    return ('<div class="stats">' + "".join(
        f'<span><span class="l">{esc(l)}</span>'
        f'<span class="n">{esc(v)}</span></span>' for l, v in cells)
        + "</div>")


def log_form(batch_id, params=None):
    """The daily action, always open: a gravity, its temperature, a note."""
    params = params or {}
    row = "".join(
        f'<span style="width:{w}px">{f}</span>' for w, f in (
            (130, field("reading", "Gravity", params.get("reading", ""), None,
                        step="0.001", attrs='placeholder="1.0__"',
                        required=True, id_="log-sg")),
            (112, field("sample_f", "Sample °F", params.get("sample_f", ""),
                        None, attrs='placeholder="68"', id_="log-temp")),
        ))
    return (f'<form class="inline" id="log" method="post" '
            f'action="/batches/{esc(batch_id)}/reading">'
            f'<div class="panel"><div class="row">{row}'
            f'<span style="flex:1;min-width:180px">'
            f'{field("note", "Note (optional)", params.get("note", ""), None, typ="text", id_="log-note")}</span>'
            f"<button>Log it</button></div>"
            '<p class="mut">Drop, ABV and attenuation are never typed — one '
            "gravity in, three columns out. The hydrometer's calibration "
            "comes from the must record.</p></div></form>")


@route("GET", r"/batches/(B-\d{4}-\d{3})")
def batch(req):
    b = req.store.load_batch(req.args[0])
    r = b.get("recipe") or {}
    m = b.get("measured") or {}
    a = b.get("added") or {}
    n = b.get("nutrients") or {}
    now = datetime.now()
    act = calc.next_action(b, now, product_name(n.get("product")))

    facts = kv([
        ("Recipe", r.get("name") or r.get("slug") or "—", None),
        ("In the carboy", f"{num(b.get('volume_gal'))} gal", None),
        ("Pitched", when(b.get("pitched_at")), None),
        ("Must gravity",
         (f"OG {sg(m['og'])}"
          + (f" (read {sg(m['reading'])} at {num(m['sample_f'])} °F, "
             f"hydrometer {num(m.get('cal_f') or calc.DEFAULT_CAL_F)} °F)"
             if m.get("reading") is not None
             and m.get("sample_f") is not None else "")
          + f" vs target {sg((b.get('target') or {}).get('og'))}"
          if m.get("og") else "—"),
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
        ("If it goes dry",
         (f"{num(calc.abv(m['og'], (b.get('target') or {}).get('fg', 1.0)), 1)} %"
          if m.get("og") else "—"),
         (f"{sg(m['og'])} down to "
          f"{sg((b.get('target') or {}).get('fg', 1.0))}, "
          f"{calc.ABV_FACTOR} points per percent")
         if m.get("og") else None),
    ])
    stop = n.get("stop_sg") or next(
        (x.get("stop_sg") for x in n.get("additions") or [] if x.get("stop_sg")),
        None)
    feed = ("<div class=\"card\">"
            + "<h2>" + esc(f"Feeding — {product_name(n.get('product'))} "
                           f"{num(n.get('total_g'), 1)} g for "
                           f"{n.get('yan_ppm', '—')} ppm YAN, sized from OG "
                           f"{sg(n['from_og']) if n.get('from_og') else '—'}")
            + "</h2>" + feed_table(b, now)
            + '<p class="mut">'
            + (f"Stop at SG {sg(stop)} whatever the calendar says. " if stop
               else "")
            + "Nothing after this: late nitrogen feeds the wrong things.</p>"
            "</div>")
    notes = (f'<div class="card"><h2>Notes</h2><p>{esc(b["notes"])}</p></div>'
             if b.get("notes") else "")

    head = (f'<p class="mut noprint" style="margin-bottom:2px">'
            f'<a href="/">← Today</a></p>'
            f'<div class="idrow"><div><span class="bid">{esc(b["id"])}</span>'
            f'{stats(b, now)}</div></div>'
            f'<div class="nextbar"><b>Next</b><span>{esc(act["text"])}</span>'
            f'<a class="btn noprint" href="#log">Log a reading</a></div>')
    view = "curve" if req.params.get("view") == "curve" else "ledger"
    toggle = ('<div class="seg noprint">' + "".join(
        f'<a href="/batches/{esc(b["id"])}?view={v}"'
        f'{" class=on" if v == view else ""}>{esc(label)}</a>'
        for v, label in (("ledger", "Ledger"), ("curve", "Curve")))
        + "</div>")
    seen = curve(b) if view == "curve" else ledger_table(b)
    body = (head + log_form(b["id"], req.params)
            + f'<div class="sheet-head"><h2>The log</h2>{toggle}</div>{seen}'
            + f'<h2>Must day, kept</h2>{card(facts)}'
            + feed + notes
            + next_link(f"/recipes/{esc(r.get('slug') or '')}",
                        f"Back to {r.get('name') or 'the recipe'}")
            + f'<p class="mut">File: data/batches/{esc(b["id"])}.json — this '
              "page prints clean for the barrel.</p>")
    return Response(_page(f"{b['id']} — {r.get('name') or ''}", body,
                          "/", req.params.get("msg"),
                          req.params.get("kind", "ok")))


@route("POST", r"/batches/(B-\d{4}-\d{3})/reading")
def log_reading(req):
    """Append one gravity, then land back on the batch with what it means."""
    batch_id = req.args[0]
    f = req.form
    try:
        b, corrected = req.store.add_reading(
            batch_id, f.get("reading"), f.get("sample_f"),
            f.get("cal_f"), f.get("note"))
    except ValueError as e:
        from urllib.parse import urlencode
        keep = {k: f.get(k, "") for k in ("reading", "sample_f", "note")
                if f.get(k)}
        return redirect(f"/batches/{batch_id}?{urlencode(keep)}#log",
                        str(e), "err")
    rows = calc.ledger((b.get("measured") or {}).get("og"),
                       b.get("pitched_at"), b["readings"])
    last = rows[-1]
    said = f"Logged {sg(last['sg'])}"
    if last["reading"] is not None and last["sample_f"] is not None:
        said += f" (read {sg(last['reading'])} at {num(last['sample_f'])} °F)"
    parts = [f"day {last['day']}"]
    if last["drop"] is not None:
        parts.append(f"{num(last['drop'], 1)} points down")
    if last["abv"] is not None:
        parts.append(f"{num(last['abv'], 1)} % so far")
    if last["atten"] is not None:
        parts.append(f"{last['atten']} % attenuated")
    act = calc.next_action(b, None,
                           product_name((b.get("nutrients") or {}).get("product")))
    return redirect(f"/batches/{batch_id}",
                    f"{said} — {', '.join(parts)}. {act['text']}",
                    "warn" if act["kind"] == "warn" else "ok")


@route("POST", r"/batches/(B-\d{4}-\d{3})/feed")
def log_feed(req):
    """Record a feeding as given, then say what is next."""
    batch_id = req.args[0]
    try:
        b, planned = req.store.record_feed(batch_id, req.form.get("n"),
                                           note=req.form.get("note", ""))
    except ValueError as e:
        return redirect(f"/batches/{batch_id}", str(e), "err")
    act = calc.next_action(
        b, None, product_name((b.get("nutrients") or {}).get("product")))
    pname = product_name((b.get("nutrients") or {}).get("product"))
    return redirect(
        f"/batches/{batch_id}",
        f"Logged {pname} #{planned.get('n')} — {num(planned.get('g'), 1)} g. "
        f"{act['text']}",
        "warn" if act["kind"] == "warn" else "ok")


@route("GET", "/batches")
def batches(req):
    """The cellar list lives on Today — one table, not two."""
    return redirect("/")

"""A batch: what went in, what it is doing now, and what to do about it.

The page's whole job is one gravity in, three columns out. Drop, ABV so far
and attenuation are computed on every render from the readings and the pitch
date, and so is the sentence at the top — there is no status here for anyone
to keep up to date.
"""
from datetime import datetime

from . import calc
from .html import (banner, card, details, esc, field, hidden, kv,
                   next_link, num,
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


def _fin_step(title, done_summary, action):
    """One finishing step: a done summary, or the action that does it."""
    body = done_summary if done_summary else action
    return f'<div class="finstep"><h3>{esc(title)}</h3>{body}</div>'


def finishing_card(b, params):
    """Rack, stabilize, sweeten, bottle — the back half of the batch.

    Each step shows what was recorded, or the way to record it. Stabilizing
    and sweetening meter real things, so they preview the dose (a GET that
    writes nothing) before the record button appears — the same shape as the
    must-day check.
    """
    bid = b["id"]
    og = (b.get("measured") or {}).get("og")
    fg = (b.get("target") or {}).get("fg") or 1.0
    now_sg = calc.current_sg(b)
    vol = calc.current_volume(b)
    steps = []

    # 1 — rack
    if calc.is_racked(b):
        last = b["rackings"][-1]
        note = f" · {last['note']}" if last.get("note") else ""
        summary = kv([("Racked", f"{num(last['volume_gal'])} gal in the vessel",
                       f"{when(last['at'])}{note}")])
        again = details("Racked again", f"""<div class="inner">
<form class="inline" method="post" action="/batches/{esc(bid)}/rack">
{field("volume_gal", "Volume now (gal)", num(vol), "Measured after racking.")}
{field("note", "Note", "", None, typ="text")}<button class="quiet">Record another racking</button></form></div>""")
        steps.append(_fin_step("Rack off the lees", summary + again, ""))
    else:
        form = f"""<form class="inline" method="post" action="/batches/{esc(bid)}/rack">
<p class="mut">Rack once it falls clear. Record the volume actually in the
vessel — every dose below is per that gallon.</p>
{field("volume_gal", "Volume now (gal)", num(vol), "A little less than the batch — racking leaves the lees behind.")}
{field("note", "Note", "", None, typ="text")}<button>Record racking</button></form>"""
        steps.append(_fin_step("Rack off the lees", "", form))

    # 2 — stabilize (preview then record)
    if calc.is_stabilized(b):
        st = b["stabilizations"][-1]
        summary = kv([("Stabilized",
                       f"{num(st['kmeta_g'], 3)} g K-meta + "
                       f"{num(st['sorbate_g'])} g sorbate",
                       f"{when(st['at'])} · pH {num(st['ph'], 2)} · "
                       f"{num(st['volume_gal'])} gal"
                       + (f" · override: {st['override']}"
                          if st.get("override") else ""))])
        steps.append(_fin_step("Stabilize", summary, ""))
    else:
        stab = _stabilize_action(b, params, vol, og, now_sg)
        steps.append(_fin_step("Stabilize", "", stab))

    # 3 — back-sweeten (preview then record)
    if calc.is_sweetened(b):
        sw = b["sweetenings"][-1]
        summary = kv([("Back-sweetened",
                       f"{sg(sw['from_sg'])} → {sg(sw['to_sg'])}",
                       f"{when(sw['at'])} · {num(sw['honey_lb'])} lb honey"
                       + (f" · override: {sw['override']}"
                          if sw.get("override") else ""))])
        steps.append(_fin_step("Back-sweeten (optional)", summary, ""))
    else:
        sweet = _sweeten_action(b, params, vol, now_sg)
        steps.append(_fin_step("Back-sweeten (optional)", "", sweet))

    # 4 — bottle
    if calc.is_bottled(b):
        pk = b["packaging"]
        summary = kv([("Bottled", f"{pk['units']} × {pk['unit']}",
                       f"{when(pk['at'])} · {num(pk.get('volume_gal'))} gal")])
        steps.append(_fin_step("Bottle", summary, ""))
    else:
        form = f"""<form class="inline" method="post" action="/batches/{esc(bid)}/bottle">
<p class="mut">The last step. {num(vol)} gal is about
{int((vol or 0) / 0.198)} × 750 mL, or {int((vol or 0) / 0.041)} × 12 oz.</p>
<div class="grid">
<span>{field("units", "How many", "", "The count you actually filled.", step="1")}</span>
<span>{field("unit", "Package", "750 mL bottle", "Bottle, keg, whatever it went in.", typ="text")}</span>
</div>{field("note", "Note", "", None, typ="text")}<button>Record bottling</button></form>"""
        steps.append(_fin_step("Bottle", "", form))

    in_arc = (calc.is_racked(b) or calc.is_stabilized(b) or calc.is_sweetened(b)
              or calc.is_bottled(b)
              or (now_sg is not None and b.get("readings")
                  and now_sg <= fg + calc.FINISHED_MARGIN))
    inner = f'<div class="finsteps">{"".join(steps)}</div>'
    if in_arc:
        return f'<h2 id="finish">Finishing</h2>{inner}'
    return details("Finishing — rack, stabilize, sweeten, bottle", inner)


def _stabilize_action(b, params, vol, og, now_sg):
    bid = b["id"]
    ph = params.get("stab_ph")
    if not calc.blank(ph):
        try:
            phv = calc.num(ph, "pH", 2.0, 4.5)
            abv_now = calc.abv(og, now_sg) if og else 0.0
            d = calc.stabilize_doses(vol, phv, abv_now)
        except ValueError as e:
            return banner(str(e), "err") + _stabilize_form(b, "")
        step = (" (stepped up — sorbate is weaker at this pH/ABV)"
                if d["sorbate_stepped_up"] else "")
        pre = banner(
            f"For {num(d['gallons'])} gal at pH {num(phv, 2)}: "
            f"{num(d['kmeta_g'], 3)} g potassium metabisulfite "
            f"(~{num(d['free_so2_ppm'], 1)} ppm free SO₂) and "
            f"{num(d['sorbate_g'])} g potassium sorbate ({d['sorbate_ppm']} "
            f"ppm){step}. They go in together — sorbate alone smells of "
            "geraniums. Ignores any SO₂ already there; measure free SO₂ "
            "for real work.", "ok")
        override = "" if calc.is_stable(b) else details(
            "It is not steady yet, but I know what I'm doing",
            '<div class="inner">' + field(
                "override", "Reason (recorded with the dose)", "",
                "e.g. cold-crashed and confirmed flat by taste.", typ="text")
            + '</div>')
        rec = f"""<form class="inline" method="post" action="/batches/{esc(bid)}/stabilize">
{hidden("ph", num(phv, 2))}
{field("note", "Note", "", None, typ="text")}{override}<button>Record — both go in</button></form>"""
        return pre + rec
    return _stabilize_form(b, "")


def _stabilize_form(b, _):
    bid = b["id"]
    steady = calc.is_stable(b)
    lead = ("" if steady else
            '<p class="mut">It has not held a steady gravity for a couple of '
            "days yet — stabilizing a mead that is still working does nothing. "
            "Preview the dose anyway; recording it will ask for a reason.</p>")
    return f"""{lead}<form class="inline" method="get" action="/batches/{esc(bid)}#finish">
<p class="mut">Sorbate and sulfite together, dosed from the pH you measure now.
This previews the amounts — it writes nothing.</p>
{field("stab_ph", "Measured pH now", "", "The dose depends on it: lower pH needs far less sulfite.", step="0.01")}
<button class="quiet">Show the dose</button></form>"""


def _sweeten_action(b, params, vol, now_sg):
    bid = b["id"]
    target = params.get("sweeten_to")
    stabilized = calc.is_stabilized(b)
    if not calc.blank(target):
        try:
            to = calc.num(target, "target gravity", 0.990, 1.200)
            honey = calc.backsweeten_honey(vol, now_sg, to)
        except ValueError as e:
            return banner(str(e), "err") + _sweeten_form(b, now_sg)
        warn = ("" if stabilized else banner(
            "Not stabilized yet — sweetening now can restart the ferment and "
            "make bottle bombs. Stabilize first, or record a reason below.",
            "warn"))
        ov = ("" if stabilized else details(
            "Sweeten without stabilizing (a keg you will force-carbonate)",
            '<div class="inner">' + field("override", "Reason (recorded)", "",
            "Why it is safe to skip stabilizing.", typ="text") + "</div>"))
        pre = banner(
            f"To lift {num(vol)} gal from {sg(now_sg)} to {sg(to)}: about "
            f"{num(honey)} lb honey, stirred in a little at a time and tasted. "
            "Confirm the gravity with a hydrometer after it is mixed.", "ok")
        rec = f"""<form class="inline" method="post" action="/batches/{esc(bid)}/sweeten">
{hidden("to_sg", sg(to))}{field("note", "Note", "", None, typ="text")}{ov}
<button>Record back-sweetening</button></form>"""
        return warn + pre + rec
    return _sweeten_form(b, now_sg)


def _sweeten_form(b, now_sg):
    bid = b["id"]
    return f"""<form class="inline" method="get" action="/batches/{esc(bid)}#finish">
<p class="mut">Optional. Currently {sg(now_sg)}. Pick the gravity you want and
this previews the honey — it writes nothing. Stabilize first.</p>
{field("sweeten_to", "Sweeten up to", "", "1.010–1.020 is off-dry to medium; taste as you go.", step="0.001")}
<button class="quiet">Show the honey</button></form>"""


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
            + finishing_card(b, req.params)
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


@route("POST", r"/batches/(B-\d{4}-\d{3})/rack")
def rack(req):
    bid = req.args[0]
    f = req.form
    try:
        b = req.store.record_racking(bid, f.get("volume_gal"),
                                     note=f.get("note", ""))
    except ValueError as e:
        return redirect(f"/batches/{bid}#finish", str(e), "err")
    act = calc.next_action(b, None, product_name(
        (b.get("nutrients") or {}).get("product")))
    vol = calc.current_volume(b)
    return redirect(f"/batches/{bid}",
                    f"Racked — {num(vol)} gal in the vessel. {act['text']}",
                    "warn" if act["kind"] == "warn" else "ok")


@route("POST", r"/batches/(B-\d{4}-\d{3})/stabilize")
def stabilize(req):
    bid = req.args[0]
    f = req.form
    try:
        b, d = req.store.record_stabilize(
            bid, f.get("ph"), note=f.get("note", ""),
            override_reason=f.get("override", ""))
    except ValueError as e:
        return redirect(f"/batches/{bid}#finish", str(e), "err")
    return redirect(
        f"/batches/{bid}",
        f"Stabilized — {num(d['kmeta_g'], 3)} g K-meta and "
        f"{num(d['sorbate_g'])} g sorbate into {num(d['gallons'])} gal. Safe "
        "to back-sweeten now, or bottle it dry.", "ok")


@route("POST", r"/batches/(B-\d{4}-\d{3})/sweeten")
def sweeten(req):
    bid = req.args[0]
    f = req.form
    try:
        b, honey = req.store.record_backsweeten(
            bid, f.get("to_sg"), note=f.get("note", ""),
            override_reason=f.get("override", ""))
    except ValueError as e:
        return redirect(f"/batches/{bid}#finish", str(e), "err")
    sw = b["sweetenings"][-1]
    return redirect(
        f"/batches/{bid}",
        f"Back-sweetened to {sg(sw['to_sg'])} with {num(honey)} lb honey. "
        "Confirm with a hydrometer, taste, then bottle.", "ok")


@route("POST", r"/batches/(B-\d{4}-\d{3})/bottle")
def bottle(req):
    bid = req.args[0]
    f = req.form
    try:
        b = req.store.record_bottling(bid, f.get("units"), f.get("unit"),
                                      note=f.get("note", ""))
    except ValueError as e:
        return redirect(f"/batches/{bid}#finish", str(e), "err")
    pk = b["packaging"]
    return redirect(f"/batches/{bid}",
                    f"Bottled {pk['units']} × {pk['unit']}. That is the batch "
                    "done — nicely done.", "ok")


@route("GET", "/batches")
def batches(req):
    """The cellar list lives on Today — one table, not two."""
    return redirect("/")

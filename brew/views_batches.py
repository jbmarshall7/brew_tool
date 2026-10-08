"""A batch: what went in, what it is doing now, and what to do about it.

The page's whole job is one gravity in, three columns out. Drop, ABV so far
and attenuation are computed on every render from the readings and the pitch
date, and so is the sentence at the top — there is no status here for anyone
to keep up to date.
"""
from datetime import datetime
from urllib.parse import urlencode

from . import calc
from .html import (banner, card, details, esc, field, hidden, kv,
                   next_link, num, once,
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
        elif shut or calc.is_bottled(b):
            action = ""
        else:
            action = raw(
                f'<form class="mini noprint" method="post" '
                f'action="/batches/{esc(b["id"])}/feed">'
                f'{hidden("n", str(num_))}{once()}'
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
    # what the yeast made is read off the hydrometer, never off a sweetening
    # target — back-sweetening adds sugar, not alcohol
    read = calc.last_read_sg(b)
    day = calc.day_of(b["pitched_at"], now or datetime.now())
    cells = [
        ("Now", sg(now_sg) if now_sg is not None else "—"),
        ("ABV so far",
         f"{num(calc.abv(og, read), 1)} %" if og and read else "—"),
        ("Attenuated",
         f"{calc.attenuation(og, read)} %" if og and read else "—"),
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
                        step="any", attrs='placeholder="1.0__"',
                        required=True, id_="log-sg")),
            (112, field("sample_f", "Sample °F", params.get("sample_f", ""),
                        None, attrs='placeholder="68"', id_="log-temp")),
        ))
    return (f'<form class="inline" id="log" method="post" '
            f'action="/batches/{esc(batch_id)}/reading">{once()}'
            f'<div class="panel"><div class="row">{row}'
            f'<span style="flex:1;min-width:180px">'
            f'{field("note", "Note (optional)", params.get("note", ""), None, typ="text", id_="log-note")}</span>'
            f"<button>Log it</button></div>"
            '<p class="mut">Drop, ABV and attenuation are never typed — one '
            "gravity in, three columns out. The hydrometer's calibration "
            "comes from the must record.</p></div></form>")


def vessel_picker(b, vessels):
    """Pick the vessel from your list — a typed 'Carboy2' used to leave the
    batch on no vessel at all. Free text only until there is a list."""
    cur = (b.get("vessel") or "").strip()
    names = [v.get("name") for v in vessels if v.get("name")]
    if names:
        opts = '<option value="">— none —</option>' + "".join(
            f'<option{" selected" if n.lower() == cur.lower() else ""}>'
            f"{esc(n)}</option>" for n in names)
        if cur and cur.lower() not in [n.lower() for n in names]:
            opts += (f'<option selected value="{esc(cur)}">{esc(cur)} '
                     "(not on the Vessels list)</option>")
        box = (f'<select name="vessel" aria-label="Vessel" '
               f'style="max-width:220px">{opts}</select>')
    else:
        box = (f'<input name="vessel" value="{esc(cur)}" '
               f'placeholder="which vessel" style="max-width:160px">')
    return (f'<form class="mini noprint" method="post" '
            f'action="/batches/{esc(b["id"])}/vessel" style="margin-top:4px">'
            f'{box}<button class="quiet">Set</button></form>'
            + ("" if names else '<span class="sub"><a href="/vessels">Add '
               "your vessels</a> to pick from a list.</span>"))


# the dose previews read these straight from the query, so they travel as-is
PREVIEW_KEYS = ("stab_ph", "prime_vols", "prime_temp", "prime_sugar",
                "sweeten_to")


def kept(params, form):
    """What the owner typed into `form` before it was refused, or {}. One form
    at a time, so the shared field names (note, qty) can't cross over; carried
    as k_<name> so a field called 'kind' can't collide with the banner's own
    kind=err."""
    if (params or {}).get("keep") != form:
        return {}
    return {k[2:]: v for k, v in params.items() if k.startswith("k_")}


def bounce(bid, form, f, fields, anchor, msg):
    """A refusal: back to the batch with the banner AND what was typed, so
    nothing has to be typed twice (the reading form always did this)."""
    q = {"keep": form}
    q.update({(k if k in PREVIEW_KEYS else "k_" + k): f.get(k)
              for k in fields if f.get(k)})
    return redirect(f"/batches/{bid}?{urlencode(q)}#{anchor}", msg, "err")


def _options(choices, chosen):
    return "".join(f"<option{' selected' if c == chosen else ''}>{esc(c)}</option>"
                   for c in choices)


def dispositions_section(b, params=None):
    """Where the bottles went, and how many are left. Only once bottled."""
    if not calc.is_bottled(b):
        return ""
    bid = b["id"]
    pk = b["packaging"]
    made, on_hand = pk.get("units"), calc.units_on_hand(b)
    ds = sorted(b.get("dispositions") or [], key=lambda d: d.get("at") or "",
                reverse=True)
    rows = [[when(d["at"]), d["kind"], str(d["qty"]), d.get("to") or "",
             d.get("note") or ""] for d in ds]
    tbl = table(["When", "Where", "How many", "To", "Note"], rows,
                empty="None yet — all still on hand.")
    stat = (f'<div class="stats"><span><span class="l">Bottled</span>'
            f'<span class="n">{made}</span></span>'
            f'<span><span class="l">On hand</span>'
            f'<span class="n">{on_hand}</span></span>'
            f'<span><span class="l">Out</span>'
            f'<span class="n">{calc.units_disposed(b)}</span></span></div>')
    k = kept(params, "dispo")
    opts = _options(calc.DISPO_KINDS, k.get("kind"))
    form = f"""<form class="inline" method="post" action="/batches/{esc(bid)}/disposition">{once()}
<div class="grid">
<span><label for="d-kind">Where</label><select id="d-kind" name="kind">{opts}</select></span>
<span>{field("qty", "How many", k.get("qty", ""), "Bottles leaving.", step="1", required=True, id_="d-qty")}</span>
<span>{field("to", "To (optional)", k.get("to", ""), "Who or where.", typ="text", id_="d-to")}</span>
</div>{field("note", "Note", k.get("note", ""), None, typ="text", id_="d-note")}
<button>Record</button></form>"""
    body = "" if on_hand else banner("All bottles accounted for — none left "
                                     "on hand.", "ok")
    return (f'<h2 id="bottles">Bottles — where they went</h2>{stat}{body}{tbl}'
            + (details("Record a disposition",
                       f'<div class="inner">{form}</div>', open_=not ds or bool(k))
               if on_hand else ""))


def tasting_section(b, params=None, open_=False):
    """Tasting notes at the checkpoints that matter, newest first."""
    bid = b["id"]
    ts = sorted(b.get("tastings") or [], key=lambda t: t.get("at") or "",
                reverse=True)
    rows = [[when(t["at"]), t.get("stage", ""),
             ("★" * t["overall"] + "☆" * (5 - t["overall"])
              if t.get("overall") else "—"),
             t.get("note") or ""] for t in ts]
    tbl = table(["When", "Stage", "Score", "Note"], rows,
                empty="No tastings yet — the recipe improves fastest when you "
                      "write down what it tastes like.")
    k = kept(params, "tasting")
    opts = _options(calc.TASTING_STAGES, k.get("stage"))
    form = f"""<form class="inline" method="post" action="/batches/{esc(bid)}/tasting">{once()}
<div class="grid">
<span><label for="ts-stage">Stage</label><select id="ts-stage" name="stage">{opts}</select></span>
<span>{field("overall", "Overall (1–5)", k.get("overall", ""), "Optional gut score.", step="1", attrs='min="1" max="5"', id_="ts-score")}</span>
</div>{field("note", "Note", k.get("note", ""), "Aroma, flavor, what you'd change.", typ="text", id_="ts-note")}
<button>Record tasting</button></form>"""
    return (f'<h2 id="tastings">Tastings</h2>{tbl}'
            + details("Record a tasting", f'<div class="inner">{form}</div>',
                      open_=open_ or bool(k)))


def flavor_section(b, params=None):
    """Fruit, spice and oak that went into this batch, with contact time and a
    way to pull what is still steeping."""
    bid = b["id"]
    now = datetime.now()
    fls = b.get("flavors") or []
    rows = []
    for i, fl in enumerate(fls):
        contact = ""
        if fl.get("kind") in ("oak", "spice"):
            if fl.get("pulled_at"):
                contact = f"{calc.day_of(fl['at'], fl['pulled_at'])} days, pulled"
            else:
                d = calc.day_of(fl["at"], now)
                contact = f"{d} day{'s' if d != 1 else ''} in"
        qty = (f"{num(fl['qty'])} {fl.get('unit', '')}"
               if fl.get("qty") is not None else "")
        pull = ""
        if fl.get("kind") in ("oak", "spice") and not fl.get("pulled_at"):
            pull = raw(f'<form class="mini noprint" method="post" '
                       f'action="/batches/{esc(bid)}/pull-flavor">'
                       f'{hidden("index", str(i))}'
                       f'<button class="quiet">Pull it</button></form>')
        rows.append([when(fl["at"]), fl["kind"], fl["item"], qty,
                     contact, pull or (fl.get("note") or "")])
    table_html = table(["When", "Kind", "Item", "Qty", "Contact", ""], rows,
                       empty="No fruit, spice or oak recorded.")
    k = kept(params, "flavor")
    form = f"""<form class="inline" method="post" action="/batches/{esc(bid)}/flavor">{once()}
<div class="grid">
<span><label for="fl-kind">Kind</label><select id="fl-kind" name="kind">
{_options(("fruit", "spice", "oak", "other"), k.get("kind"))}</select></span>
<span>{field("item", "What", k.get("item", ""), "blueberries, star anise, medium-toast oak…", typ="text", required=True, id_="fl-item")}</span>
<span>{field("qty", "How much", k.get("qty", ""), "Optional.", id_="fl-qty")}</span>
<span>{field("unit", "Unit", k.get("unit", "lb"), None, typ="text", id_="fl-unit")}</span>
</div>{field("note", "Note", k.get("note", ""), "Primary or secondary? Toast level?", typ="text", id_="fl-note")}
<button>Record addition</button></form>"""
    watching = calc.flavors_in_contact(b, now)
    lead = ""
    if watching:
        longest = max(watching, key=lambda w: w["days"])
        if longest["days"] >= 7:
            lead = banner(f"{longest['item']} has steeped {longest['days']} "
                          "days — taste it; over-extraction doesn't come out.",
                          "warn" if longest["days"] >= calc.OAK_WATCH_DAYS
                          else "ok")
    if calc.is_bottled(b):          # the cellar record is closed
        return (f'<h2>Fruit, spice &amp; oak</h2>{table_html}'
                if fls else "")
    return (f'<h2 id="flavors">Fruit, spice &amp; oak</h2>{lead}{table_html}'
            + details("Record fruit, spice or oak", f'<div class="inner">{form}</div>',
                      open_=bool(k)))


# What the Next sentence asks for, and where on the page it's done. Read from
# the sentence's tag, so the button under it can never point somewhere else.
NEXT_STEP = {"Ready to rack": ("rack", "Rack it"),
             "Ready to stabilize": ("stabilize", "Stabilize it"),
             "Ready to bottle": ("bottle", "Bottle it"),
             "Bottled": ("bottles", "Where the bottles went"),
             "Conditioning": ("bottles", "Where the bottles went"),
             "Test a bottle": ("tastings", "Record the tasting")}
PREVIEWS = (("stab_ph", "stabilize"), ("prime_vols", "prime"),
            ("sweeten_to", "sweeten"))


def step_for(act, params):
    """(anchor, button label) for the one step to show open. A preview the
    owner just asked for (a pH typed, priming sugar shown) wins, so the page
    opens where they are working."""
    label = NEXT_STEP.get(act["tag"], ("log", "Log a reading"))[1]
    for key, anchor in PREVIEWS:
        if params.get(key):
            return anchor, label
    if params.get("keep") in ("rack", "bottle"):
        return params["keep"], label
    return NEXT_STEP.get(act["tag"], ("log", "Log a reading"))


def _fin_step(title, done_summary, action, anchor="", open_=True):
    """One finishing step: its summary once done, its form when it's the
    step at hand, otherwise folded one tap away — so a phone isn't scrolled
    past five forms to reach the one that matters."""
    if done_summary:
        body = f"<h3>{esc(title)}</h3>{done_summary}"
    elif open_:
        body = f"<h3>{esc(title)}</h3>{action}"
    else:
        body = details(title, f'<div class="inner">{action}</div>')
    return f'<div class="finstep" id="{anchor}">{body}</div>'


def finishing_card(b, params, step=""):
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
    closed = calc.is_bottled(b)     # bottled: show the record, offer nothing
    in_arc = (calc.is_racked(b) or calc.is_stabilized(b) or calc.is_sweetened(b)
              or calc.is_primed(b) or calc.is_bottled(b)
              or (now_sg is not None and b.get("readings")
                  and now_sg <= fg + calc.FINISHED_MARGIN))

    def opened(anchor):
        # outside the arc the whole card is one fold, and all of it shows
        # inside; in the arc only the step at hand is open
        return not in_arc or anchor == step

    # 1 — rack
    if calc.is_racked(b):
        last = b["rackings"][-1]
        note = f" · {last['note']}" if last.get("note") else ""
        summary = kv([("Racked", f"{num(last['volume_gal'])} gal in the vessel",
                       f"{when(last['at'])}{note}")])
        again = details("Racked again", f"""<div class="inner">
<form class="inline" method="post" action="/batches/{esc(bid)}/rack">{once()}
{field("volume_gal", "Volume now", kept(params, "rack").get("volume_gal") or num(vol), "Measured after racking — gallons, or 2.9 bbl.", typ="text", id_="rack2-volume")}
{field("note", "Note", kept(params, "rack").get("note", ""), None, typ="text", id_="rack2-note")}<button class="quiet">Record another racking</button></form></div>""", open_=bool(kept(params, "rack")))
        steps.append(_fin_step("Rack off the lees",
                               summary + ("" if closed else again), "", "rack"))
    elif not closed:
        form = f"""<form class="inline" method="post" action="/batches/{esc(bid)}/rack">{once()}
<p class="mut">Rack once it falls clear. Record the volume actually in the
vessel — every dose below is per that gallon.</p>
{field("volume_gal", "Volume now", kept(params, "rack").get("volume_gal") or num(vol), "A little less than the batch — racking leaves the lees behind. Gallons, or 2.9 bbl.", typ="text", id_="rack-volume")}
{field("note", "Note", kept(params, "rack").get("note", ""), None, typ="text", id_="rack-note")}<button>Record racking</button></form>"""
        steps.append(_fin_step("Rack off the lees", "", form, "rack",
                               opened("rack")))

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
        steps.append(_fin_step("Stabilize", summary, "", "stabilize"))
    elif not closed:
        stab = _stabilize_action(b, params, vol, og, now_sg)
        steps.append(_fin_step("Stabilize", "", stab, "stabilize",
                               opened("stabilize")))

    # 2b — carbonate (sparkling): the alternative to stabilizing
    if calc.is_primed(b):
        pr = b["primings"][-1]
        summary = kv([("Primed",
                       f"{num(pr['grams'])} g {pr['sugar']} → "
                       f"{num(pr['target_vols'])} volumes",
                       f"{when(pr['at'])} · {pr['tax_class']}"
                       + (f" · override: {pr['override']}"
                          if pr.get("override") else ""))])
        steps.append(_fin_step("Carbonate (sparkling)", summary, "", "prime"))
    elif not calc.is_stabilized(b) and not closed:
        steps.append(_fin_step("Carbonate (sparkling) — instead of stabilizing",
                               "", _prime_action(b, params, vol), "prime",
                               opened("prime")))

    # 3 — back-sweeten (preview then record)
    if calc.is_sweetened(b):
        sw = b["sweetenings"][-1]
        summary = kv([("Back-sweetened",
                       f"{sg(sw['from_sg'])} → {sg(sw['to_sg'])}",
                       f"{when(sw['at'])} · {num(sw['honey_lb'])} lb honey"
                       + (f" · override: {sw['override']}"
                          if sw.get("override") else ""))])
        steps.append(_fin_step("Back-sweeten (optional)", summary, "",
                               "sweeten"))
    elif not closed:
        sweet = _sweeten_action(b, params, vol, now_sg)
        steps.append(_fin_step("Back-sweeten (optional)", "", sweet,
                               "sweeten", opened("sweeten")))

    # 4 — bottle
    if calc.is_bottled(b):
        pk = b["packaging"]
        summary = kv([("Bottled", f"{pk['units']} × {pk['unit']}",
                       f"{when(pk['at'])} · {num(pk.get('volume_gal'))} gal"
                       + (f" · override: {pk['override']}"
                          if pk.get("override") else ""))])
        steps.append(_fin_step("Bottle", summary, "", "bottle"))
    else:
        refusal = calc.bottling_refusal(b)
        warn = (banner(refusal + " Recording it will ask for a reason.", "warn")
                if refusal else "")
        k = kept(params, "bottle")
        override = (details(
            "Bottle it anyway — I know why it is safe",
            '<div class="inner">' + field(
                "override", "Reason (recorded with the bottling)",
                k.get("override", ""),
                "e.g. kegged and kept cold; pasteurized after bottling.",
                typ="text", id_="bottle-override") + "</div>",
            open_=bool(k.get("override")))
            if refusal else "")
        form = f"""{warn}<form class="inline" method="post" action="/batches/{esc(bid)}/bottle">{once()}
<p class="mut">The last step. {num(vol)} gal is about
{int((vol or 0) / calc.unit_gallons("750 ml"))} × 750 mL, or
{int((vol or 0) / calc.unit_gallons("12 oz"))} × 12 oz.</p>
<div class="grid">
<span>{field("units", "How many", k.get("units", ""), "The count you actually filled.", step="1", id_="bottle-units")}</span>
<span>{field("unit", "Package", k.get("unit", "750 mL bottle"), "Bottle, keg, whatever it went in.", typ="text", id_="bottle-unit")}</span>
<span>{field("abv_measured", "Lab ABV (optional)", k.get("abv_measured", ""), f"Only if measured. The gravity estimate is {num(calc.abv(og, calc.last_read_sg(b)), 1) if og and calc.last_read_sg(b) else '—'} %; a lab number settles the tax class near 16 %.", id_="bottle-abv")}</span>
</div>{field("note", "Note", k.get("note", ""), None, typ="text", id_="bottle-note")}{override}<button>Record bottling</button></form>"""
        steps.append(_fin_step("Bottle", "", form, "bottle",
                               opened("bottle")))

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
        problem = calc.sulfite_problem(d["free_so2_ppm"], phv)
        if problem and problem[0] == "refuse":
            return (banner(problem[1], "err") + pre.replace('msg ok', 'msg warn')
                    + _stabilize_form(b, ""))
        needs = [] if calc.is_stable(b) else ["it is not steady yet"]
        if problem and problem[0] == "reason":
            needs.append("the dose is past the sulfite ceiling")
        override = details(
            f"Record it anyway ({' and '.join(needs)})",
            '<div class="inner">' + field(
                "override", "Reason (recorded with the dose)",
                kept(params, "stabilize").get("override", ""),
                "e.g. cold-crashed and confirmed flat by taste.", typ="text",
                id_="stab-override")
            + '</div>', open_=bool(kept(params, "stabilize").get("override"))
        ) if needs else ""
        if problem:
            pre = banner(problem[1], "warn") + pre
        rec = f"""<form class="inline" method="post" action="/batches/{esc(bid)}/stabilize">{once()}
{hidden("ph", num(phv, 2))}
{field("note", "Note", kept(params, "stabilize").get("note", ""), None, typ="text", id_="stab-note")}{override}<button>Record — both go in</button></form>"""
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


def _prime_action(b, params, vol):
    """Preview the priming sugar (a GET that writes nothing), then record."""
    bid = b["id"]
    vols, temp = params.get("prime_vols"), params.get("prime_temp")
    sugar = params.get("prime_sugar") or "honey"
    if not calc.blank(vols) and not calc.blank(temp):
        try:
            d = calc.priming_sugar(vol, calc.num(vols, "volumes", 0.5, 6),
                                   calc.num(temp, "temperature", 32, 100),
                                   sugar if sugar in calc.SUGAR_YIELD else "honey")
        except ValueError as e:
            return banner(str(e), "err") + _prime_form(b, vol)
        taxline = ("Under ~2 volumes it stays a still wine for excise."
                   if not d["over_still"] else
                   "Over ~2 volumes — this is a sparkling / carbonated wine for "
                   "TTB, a higher excise class than still. Decide before you "
                   "prime.")
        pre = banner(
            f"For {num(d['gallons'])} gal to {num(d['target_vols'])} volumes "
            f"(it already holds ~{num(d['residual_vols'])} at "
            f"{num(d['temp_f'])} °F): {num(d['grams'])} g {d['sugar']} "
            f"({num(d['grams_per_gal'])} g/gal). Bottle in pressure-rated "
            f"bottles only — champagne or heavy crown-cap glass. {taxline}",
            "warn" if d["over_still"] else "ok")
        refusal = calc.priming_refusal(b)
        override = (details(
            "Prime it anyway — I know why it is safe",
            '<div class="inner">' + field("override", "Reason (recorded)",
            kept(params, "prime").get("override", ""),
            "e.g. re-pitched EC-1118 at bottling; will pasteurize.",
            typ="text", id_="prime-override") + "</div>",
            open_=bool(kept(params, "prime").get("override"))) if refusal else "")
        rec = f"""<form class="inline" method="post" action="/batches/{esc(bid)}/prime">{once()}
{hidden("target_vols", num(d['target_vols']))}{hidden("temp_f", num(d['temp_f']))}
{hidden("sugar", d['sugar'])}{field("note", "Note", kept(params, "prime").get("note", ""), None, typ="text", id_="prime-note")}{override}
<button>Record priming</button></form>"""
        unsafe = (banner(refusal + " Recording it will ask for a reason.",
                         "warn") if refusal else "")
        return unsafe + pre + rec
    return _prime_form(b, vol)


def _prime_form(b, vol):
    bid = b["id"]
    refusal = calc.priming_refusal(b)
    warn = (banner(refusal + " Preview the sugar anyway; recording it will "
                   "ask for a reason.", "warn") if refusal else "")
    opts = "".join(f"<option{' selected' if k == 'honey' else ''}>{k}</option>"
                   for k in calc.SUGAR_YIELD)
    return f"""{warn}<form class="inline" method="get" action="/batches/{esc(bid)}#finish">
<p class="mut">For a sparkling mead: do NOT stabilize. Prime with sugar the live
yeast will carbonate, then bottle in pressure-rated bottles. This previews the
amount — it writes nothing.</p>
<div class="grid">
<span>{field("prime_vols", "Target volumes of CO₂", "2.5", "Still ~0, lightly sparkling 1.5–2.5, champagne-style 3+.", step="any")}</span>
<span>{field("prime_temp", "Warmest it has sat (°F)", "68", "Sets how much CO₂ is already dissolved.")}</span>
<span><label for="ps">Priming sugar</label><select id="ps" name="prime_sugar">{opts}</select></span>
</div>
<button class="quiet">Show the sugar</button></form>"""


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
        rec = f"""<form class="inline" method="post" action="/batches/{esc(bid)}/sweeten">{once()}
{hidden("to_sg", sg(to))}{field("note", "Note", kept(params, "sweeten").get("note", ""), None, typ="text", id_="sweet-note")}{ov}
<button>Record back-sweetening</button></form>"""
        return warn + pre + rec
    return _sweeten_form(b, now_sg)


def _sweeten_form(b, now_sg):
    bid = b["id"]
    return f"""<form class="inline" method="get" action="/batches/{esc(bid)}#finish">
<p class="mut">Optional. Currently {sg(now_sg)}. Pick the gravity you want and
this previews the honey — it writes nothing. Stabilize first.</p>
{field("sweeten_to", "Sweeten up to", "", "1.010–1.020 is off-dry to medium; taste as you go.", step="any")}
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
    closed = calc.is_bottled(b)     # bottled: the cellar record is closed

    facts = kv([
        ("Recipe", r.get("name") or r.get("slug") or "—", None),
        ("Vessel", b.get("vessel") or "—",
         raw(vessel_picker(b, req.store.list_vessels()))),
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

    step, label = step_for(act, req.params)
    if act["tag"] == "Feed due" and not closed:
        nf, _ = calc.next_feed(b, now)
        nbtn = (f'<form class="mini noprint" method="post" '
                f'action="/batches/{esc(b["id"])}/feed">{once()}'
                f'{hidden("n", str(nf["n"]))}<button>I gave #{nf["n"]}'
                "</button></form>") if nf else ""
    else:
        nbtn = f'<a class="btn noprint" href="#{step}">{esc(label)}</a>'
    head = (f'<p class="mut noprint" style="margin-bottom:2px">'
            f'<a href="/">← Today</a> · <a href="/batches">All batches</a></p>'
            f'<div class="idrow"><div><span class="bid">{esc(b["id"])}</span>'
            f'{stats(b, now)}</div></div>'
            f'<div class="nextbar"><b>Next</b><span>{esc(act["text"])}</span>'
            + nbtn + '</div>')
    fermenting = step == "log" or act["tag"] == "Feed due"
    _, shut = calc.next_feed(b, now)
    if closed:
        logbox = ""
    elif fermenting or req.params.get("reading"):
        logbox = log_form(b["id"], req.params)
    else:
        logbox = details("Log a reading", '<div class="inner">'
                         + log_form(b["id"], req.params) + "</div>")
    kept = (f'<h2>Must day, kept</h2>{card(facts)}' if fermenting else
            details("Must day, kept — the OG, pH and what went in", card(facts)))
    if not fermenting or shut:
        feed = details("Feeding — the schedule, and what was given", feed)
    view = "curve" if req.params.get("view") == "curve" else "ledger"
    toggle = ('<div class="seg noprint">' + "".join(
        f'<a href="/batches/{esc(b["id"])}?view={v}"'
        f'{" class=on" if v == view else ""}>{esc(label)}</a>'
        for v, label in (("ledger", "Ledger"), ("curve", "Curve")))
        + "</div>")
    seen = curve(b) if view == "curve" else ledger_table(b)
    body = (head + logbox
            + f'<div class="sheet-head"><h2>The log</h2>{toggle}</div>{seen}'
            + finishing_card(b, req.params, step)
            + dispositions_section(b, req.params)
            + flavor_section(b, req.params)
            + tasting_section(b, req.params, open_=step == "tastings")
            + kept + feed + notes
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
            f.get("cal_f"), f.get("note"), once=f.get("once"))
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
                                           note=req.form.get("note", ""),
                                           once=req.form.get("once"))
    except ValueError as e:
        return redirect(f"/batches/{batch_id}", str(e), "err")
    act = calc.next_action(
        b, None, product_name((b.get("nutrients") or {}).get("product")))
    pname = product_name((b.get("nutrients") or {}).get("product"))
    back = "/" if req.form.get("back") == "today" else f"/batches/{batch_id}"
    return redirect(
        back,
        f"Logged {pname} #{planned.get('n')} — {num(planned.get('g'), 1)} g. "
        f"{act['text']}",
        "warn" if act["kind"] == "warn" else "ok")


@route("POST", r"/batches/(B-\d{4}-\d{3})/rack")
def rack(req):
    bid = req.args[0]
    f = req.form
    try:
        b = req.store.record_racking(bid, f.get("volume_gal"),
                                     note=f.get("note", ""), once=f.get("once"))
    except ValueError as e:
        return bounce(bid, "rack", f, ("volume_gal", "note"), "rack", str(e))
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
            override_reason=f.get("override", ""), once=f.get("once"))
    except ValueError as e:
        return bounce(bid, "stabilize", dict(f, stab_ph=f.get("ph", "")),
                      ("stab_ph", "note", "override"), "stabilize", str(e))
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
            override_reason=f.get("override", ""), once=f.get("once"))
    except ValueError as e:
        return bounce(bid, "sweeten", dict(f, sweeten_to=f.get("to_sg", "")),
                      ("sweeten_to", "note", "override"), "sweeten", str(e))
    sw = b["sweetenings"][-1]
    return redirect(
        f"/batches/{bid}",
        f"Back-sweetened to {sg(sw['to_sg'])} with {num(honey)} lb honey. "
        "Confirm with a hydrometer, taste, then bottle.", "ok")


@route("POST", r"/batches/(B-\d{4}-\d{3})/prime")
def prime(req):
    bid = req.args[0]
    f = req.form
    try:
        b, d = req.store.record_priming(
            bid, f.get("target_vols"), f.get("temp_f"),
            f.get("sugar", "honey"), note=f.get("note", ""),
            override_reason=f.get("override", ""), once=f.get("once"))
    except ValueError as e:
        return bounce(bid, "prime",
                      dict(f, prime_vols=f.get("target_vols", ""),
                           prime_temp=f.get("temp_f", ""),
                           prime_sugar=f.get("sugar", "")),
                      ("prime_vols", "prime_temp", "prime_sugar", "note",
                       "override"), "prime", str(e))
    return redirect(
        f"/batches/{bid}",
        f"Primed to {num(d['target_vols'])} volumes with {num(d['grams'])} g "
        f"{d['sugar']}. Bottle in pressure-rated bottles; it is a "
        f"{d['tax_class']} wine for excise.", "ok")


@route("POST", r"/batches/(B-\d{4}-\d{3})/bottle")
def bottle(req):
    bid = req.args[0]
    f = req.form
    try:
        b = req.store.record_bottling(bid, f.get("units"), f.get("unit"),
                                      note=f.get("note", ""),
                                      override_reason=f.get("override", ""),
                                      once=f.get("once"),
                                      abv_measured=f.get("abv_measured"))
    except ValueError as e:
        return bounce(bid, "bottle", f, ("units", "unit", "note",
                      "abv_measured", "override"), "bottle", str(e))
    pk = b["packaging"]
    return redirect(f"/batches/{bid}",
                    f"Bottled {pk['units']} × {pk['unit']}. That is the batch "
                    "done — nicely done.", "ok")


@route("POST", r"/batches/(B-\d{4}-\d{3})/disposition")
def disposition(req):
    bid = req.args[0]
    f = req.form
    try:
        b = req.store.record_disposition(bid, f.get("kind"), f.get("qty"),
                                         f.get("to", ""), note=f.get("note", ""),
                                         once=f.get("once"))
    except ValueError as e:
        return bounce(bid, "dispo", f, ("kind", "qty", "to", "note"),
                      "bottles", str(e))
    d = b["dispositions"][-1]
    return redirect(f"/batches/{bid}",
                    f"{d['qty']} to {d['kind']}"
                    + (f" ({d['to']})" if d['to'] else "")
                    + f" — {calc.units_on_hand(b)} on hand.", "ok")


@route("POST", r"/batches/(B-\d{4}-\d{3})/tasting")
def tasting(req):
    bid = req.args[0]
    f = req.form
    try:
        b = req.store.record_tasting(bid, f.get("stage"), f.get("overall"),
                                     f.get("note", ""), once=f.get("once"))
    except ValueError as e:
        return bounce(bid, "tasting", f, ("stage", "overall", "note"),
                      "tastings", str(e))
    t = b["tastings"][-1]
    return redirect(f"/batches/{bid}",
                    f"Tasting noted at {t['stage']}.", "ok")


@route("POST", r"/batches/(B-\d{4}-\d{3})/flavor")
def flavor(req):
    bid = req.args[0]
    f = req.form
    try:
        b = req.store.record_flavor(bid, f.get("kind"), f.get("item"),
                                    f.get("qty"), f.get("unit", ""),
                                    note=f.get("note", ""), once=f.get("once"))
    except ValueError as e:
        return bounce(bid, "flavor", f, ("kind", "item", "qty", "unit",
                      "note"), "flavors", str(e))
    fl = b["flavors"][-1]
    tail = (" — taste on a schedule and pull it when it's right"
            if fl["kind"] in ("oak", "spice") else "")
    return redirect(f"/batches/{bid}",
                    f"Recorded {fl['item']} ({fl['kind']}){tail}.", "ok")


@route("POST", r"/batches/(B-\d{4}-\d{3})/pull-flavor")
def pull_flavor(req):
    bid = req.args[0]
    try:
        b = req.store.pull_flavor(bid, int(req.form.get("index", "-1")))
    except (ValueError, TypeError) as e:
        return redirect(f"/batches/{bid}", str(e), "err")
    return redirect(f"/batches/{bid}", "Pulled — its contact clock is stopped.",
                    "ok")


@route("GET", "/batches")
def batches(req):
    """Every batch ever made, newest first — Today shows only what's in a
    tank or has bottles left; this is where the finished ones live."""
    now = datetime.now()
    rows = []
    for b in req.store.list_batches():
        r = b.get("recipe") or {}
        try:
            act = calc.next_action(b, now)
        except (ValueError, KeyError, TypeError) as e:
            act = {"kind": "warn", "tag": "Can't read", "text": str(e)}
        oh = calc.units_on_hand(b)
        rows.append([
            raw(f'<a href="/batches/{esc(b["id"])}">{esc(b["id"])}</a>'
                f'<span class="sub">{esc(r.get("name") or "")}</span>'),
            esc((b.get("pitched_at") or "")[:10]),
            calc.vol_text(b["volume_gal"]) if b.get("volume_gal") else "—",
            raw(str(pill(act["tag"], act["kind"]))),
            "—" if oh is None else str(oh),
        ])
    body = table(["Batch", "Pitched", "Volume", "Now", "Bottles on hand"],
                 rows, empty="No batches yet — make a must from a recipe.")
    return Response(_page("All batches", body, "/", req.params.get("msg"),
                          req.params.get("kind", "ok"),
                          lede=f"{len(rows)} batch{'es' if len(rows) != 1 else ''}"
                               ", newest first."))

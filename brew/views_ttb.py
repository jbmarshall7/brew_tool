"""The TTB Report of Wine Premises Operations (F 5120.17), for a period.

Every figure is derived from the batches and dispositions; the report
SUPPORTS the filing and flags gaps, and makes no legal determination and
computes no tax. Verify the line mapping against the current form.

It leads with the two balances the form itself keeps — bulk and bottled,
each `on hand at start + in − out − losses = on hand at end` — because a
period that doesn't balance is the first thing a filing gets wrong.
"""
from datetime import date
from urllib.parse import urlencode

from . import calc
from .html import (banner, esc, field, num, page as _page, raw, table)
from .server import Response, redirect, route


def _period(params):
    """(start, end) as ISO dates — the month so far by default. Raises a
    ValueError in plain words on a date it can't read or a backwards period."""
    today = date.today()
    start = (params.get("start") or f"{today.year}-{today.month:02d}-01").strip()
    end = (params.get("end") or today.isoformat()).strip()
    start, end = calc.parse_date(start).isoformat(), calc.parse_date(end).isoformat()
    if start > end:
        raise ValueError(f"the period starts ({start}) after it ends ({end})")
    return start, end


def _link(bid):
    return raw(f'<a href="/batches/{esc(bid)}">{esc(bid)}</a>')


def _g(x):
    return num(x, 2)


def balance_lines(rep):
    """The two equations, in words a filing reader checks first."""
    b, t = rep["balance"]["bulk"], rep["balance"]["bottled"]
    return [
        ("Bulk", f"{_g(b['begin'])} on hand + {_g(b['produced'])} produced − "
                 f"{_g(b['bottled'])} bottled − {_g(b['losses'])} losses = "
                 f"{_g(b['end'])} gal"),
        ("Bottled", f"{_g(t['begin'])} on hand + {_g(t['bottled'])} bottled − "
                    f"{_g(t['removed'])} removed − {_g(t['losses'])} losses = "
                    f"{_g(t['end'])} gal"),
    ]


def report_md(rep):
    ok = rep["balance"]["ok"]
    L = [f"# TTB Report of Wine Premises Operations — {rep['start']} to "
         f"{rep['end']}", "",
         "Supports TTB F 5120.17. Every figure is derived from the cellar "
         "records; verify the line mapping against the current form. This "
         "makes no legal determination and computes no tax.", "",
         "## The balance — " + ("both sections balance" if ok
                                 else "DOES NOT BALANCE — see the gaps"), ""]
    L += [f"- {k}: {v}" for k, v in balance_lines(rep)]
    L += ["", f"## On hand at the start — bulk {rep['begin']['bulk_gal']} gal, "
          f"bottled {rep['begin']['bottled_gal']} gal", "",
          f"## A. Produced by fermentation — {rep['production_gal']} gal", ""]
    for p in rep["production"]:
        L.append(f"- {p['batch']} ({p['recipe']}), started {p['started']}: "
                 f"{p['gal']} gal")
    L += ["", f"## B. Bottled — {rep['bottled_gal']} gal into bottles", ""]
    for b in rep["bottled"]:
        L.append(f"- {b['batch']}: {b['units']} × {b['unit']} = {b['gal']} gal "
                 f"({b['tax_class']}), drawn from {b['drawn_gal']} gal bulk")
    L += ["", f"## C. Removals — taxable {rep['taxable_removals_gal']} gal", ""]
    for cls, g in rep["taxable_by_class"].items():
        L.append(f"- taxable, {cls}: {g} gal")
    for bucket, v in sorted(rep["removals"].items()):
        L.append(f"### {bucket} — {v['gal']} gal ({v['units']} units)")
        for r in v["rows"]:
            L.append(f"- {r['date']}: {r['batch']} {r['kind']} × {r['units']}"
                     + (f" to {r['to']}" if r.get("to") else "")
                     + f" = {r['gal']} gal")
        L.append("")
    L += [f"## D. Losses — {rep['losses_gal']} gal (bulk "
          f"{rep['bulk_losses_gal']}, bottled {rep['bottled_losses_gal']})", ""]
    for x in rep["losses"]:
        L.append(f"- {x['date']}: {x['batch']} {x['why']} {x['gal']} gal")
    L += ["", "## E. On hand at the end", "",
          f"### Bulk (in tank) — {rep['bulk_inventory_gal']} gal"]
    for x in rep["bulk_inventory"]:
        L.append(f"- {x['batch']}: {x['gal']} gal ({x['tag']})")
    L.append(f"### Bottled — {rep['bottled_inventory_gal']} gal")
    for x in rep["bottled_inventory"]:
        L.append(f"- {x['batch']}: {x['units']} × {x['unit']} = {x['gal']} gal "
                 f"({x['tax_class']})")
    L += ["", "## F. Gaps to resolve before filing", ""]
    L += [f"- {g}" for g in rep["gaps"]] or ["- none flagged"]
    return "\n".join(L) + "\n"


def _section(title, headers, rows, total=None, empty="Nothing in this period."):
    head = f"<h2>{esc(title)}"
    if total is not None:
        head += f' <span class="pill">{esc(num(total, 2))} gal</span>'
    return head + "</h2>" + table(headers, rows, empty=empty)


@route("GET", "/ttb")
def ttb(req):
    try:
        start, end = _period(req.params)
    except ValueError as e:
        start, end = _period({})
        req.params.update(msg=f"{e} — showing this month instead", kind="err")
    rep = calc.ttb_report(list(req.store.list_batches()), start, end)
    form = f'''<form class="inline" method="get" action="/ttb">
<div class="grid">
<span>{field("start", "Period start", start, None, typ="date")}</span>
<span>{field("end", "Period end", end, None, typ="date")}</span>
</div><button>Show the period</button></form>'''
    lead = ('<p class="lede">Supports the F 5120.17 filing — every figure is '
            "derived from your batches and dispositions. It makes no legal "
            "determination and computes no tax; verify the mapping against the "
            "current form.</p>")
    ok = rep["balance"]["ok"]
    bal = banner(("The books balance for this period.\n" if ok else
                  "This period does NOT balance — see below.\n")
                 + "\n".join(f"{k}: {v}" for k, v in balance_lines(rep)),
                 "ok" if ok else "err")
    gaps = ""
    if rep["gaps"]:
        gaps = banner("Resolve before filing:\n"
                      + "\n".join(f"• {g}" for g in rep["gaps"]), "warn")
    begin = (f'<p class="mut">On hand at the start: '
             f'{_g(rep["begin"]["bulk_gal"])} gal in bulk, '
             f'{_g(rep["begin"]["bottled_gal"])} gal bottled.</p>')
    prod = _section("A. Produced by fermentation",
                    ["Batch", "Recipe", "Started", "Gallons"],
                    [[_link(p["batch"]), p["recipe"], p["started"], _g(p["gal"])]
                     for p in rep["production"]], rep["production_gal"])
    bott = _section("B. Bottled",
                    ["Batch", "Units", "Tax class", "Drawn from bulk",
                     "In the bottles"],
                    [[_link(b["batch"]), f"{b['units']} × {b['unit']}",
                      b["tax_class"], _g(b["drawn_gal"]), _g(b["gal"])]
                     for b in rep["bottled"]], rep["bottled_gal"])
    rem_rows = []
    for bucket, v in sorted(rep["removals"].items()):
        for r in v["rows"]:
            rem_rows.append([r["date"], _link(r["batch"]), bucket,
                             str(r["units"]), r.get("to") or "", _g(r["gal"])])
    by_class = "".join(f' <span class="pill">{esc(c)}: {esc(_g(g))} gal</span>'
                       for c, g in rep["taxable_by_class"].items())
    rem = (f'<h2>C. Removals <span class="pill">taxable '
           f'{esc(_g(rep["taxable_removals_gal"]))} gal</span>{by_class}</h2>'
           + table(["When", "Batch", "Bucket", "Units", "To", "Gallons"],
                   rem_rows, empty="No removals in this period."))
    loss = _section("D. Losses", ["When", "Batch", "Why", "Gallons"],
                    [[x["date"], _link(x["batch"]), x["why"], _g(x["gal"])]
                     for x in rep["losses"]], rep["losses_gal"],
                    empty="No losses in this period.")
    inv = ('<h2>E. On hand at the end</h2>'
           + _section("Bulk (in tank)", ["Batch", "Stage", "Gallons"],
                      [[_link(x["batch"]), x["tag"], _g(x["gal"])]
                       for x in rep["bulk_inventory"]],
                      rep["bulk_inventory_gal"], empty="Nothing in bulk.")
           + _section("Bottled", ["Batch", "Units", "Tax class", "Gallons"],
                      [[_link(x["batch"]), f"{x['units']} × {x['unit']}",
                        x["tax_class"], _g(x["gal"])]
                       for x in rep["bottled_inventory"]],
                      rep["bottled_inventory_gal"], empty="No bottles on hand."))
    export = f'''<form class="inline noprint" method="post" action="/ttb/export">
<input type="hidden" name="start" value="{esc(start)}">
<input type="hidden" name="end" value="{esc(end)}">
<button>Write it to data/reports/</button></form>'''
    body = lead + form + bal + gaps + begin + prod + bott + rem + loss + inv + export
    return Response(_page(f"TTB — {start} to {end}", body, "/ttb",
                          req.params.get("msg"), req.params.get("kind", "ok")))


@route("POST", "/ttb/export")
def ttb_export(req):
    try:
        start, end = _period(req.form)
    except ValueError as e:
        return redirect("/ttb", str(e), "err")
    rep = calc.ttb_report(list(req.store.list_batches()), start, end)
    name = f"ttb-{start}-to-{end}.md"
    req.store.write_report(name, report_md(rep))
    return redirect("/ttb?" + urlencode({"start": start, "end": end}),
                    f"Wrote data/reports/{name}.", "ok")

"""The TTB Report of Wine Premises Operations (F 5120.17), for a period.

Every figure is derived from the batches and dispositions; the report
SUPPORTS the filing and flags gaps, and makes no legal determination and
computes no tax. Verify the line mapping against the current form.
"""
from datetime import date

from . import calc
from .html import (banner, card, esc, field, kv, next_link, num, page as _page,
                   raw, sg, table)
from .server import Response, redirect, route


def _period(params):
    today = date.today()
    start = params.get("start") or f"{today.year}-{today.month:02d}-01"
    end = params.get("end") or today.isoformat()
    return start, end


def report_md(rep):
    L = [f"# TTB Report of Wine Premises Operations — {rep['start']} to "
         f"{rep['end']}", "",
         "Supports TTB F 5120.17. Every figure is derived from the cellar "
         "records; verify the line mapping against the current form. This "
         "makes no legal determination and computes no tax.", "",
         f"## A. Produced by fermentation — {rep['production_gal']} gal", ""]
    for p in rep["production"]:
        L.append(f"- {p['batch']} ({p['recipe']}), started {p['started']}: "
                 f"{p['gal']} gal")
    L += ["", f"## B. Bottled — {rep['bottled_gal']} gal", ""]
    for b in rep["bottled"]:
        L.append(f"- {b['batch']}: {b['units']} × {b['unit']} = {b['gal']} gal "
                 f"({b['tax_class']})")
    L += ["", f"## C. Removals — taxable {rep['taxable_removals_gal']} gal", ""]
    for bucket, v in sorted(rep["removals"].items()):
        L.append(f"### {bucket} — {v['gal']} gal ({v['units']} units)")
        for r in v["rows"]:
            L.append(f"- {r['date']}: {r['batch']} {r['kind']} × {r['units']}"
                     + (f" to {r['to']}" if r.get("to") else "")
                     + f" = {r['gal']} gal")
        L.append("")
    L += [f"## D. Losses — {rep['losses_gal']} gal", ""]
    for x in rep["losses"]:
        L.append(f"- {x['batch']}: {x['gal']} gal ({x['why']}, {x['date']})")
    L += ["", "## E. Period-end inventory", "",
          f"### Bulk (in tank) — {rep['bulk_inventory_gal']} gal"]
    for x in rep["bulk_inventory"]:
        L.append(f"- {x['batch']}: {x['gal']} gal ({x['tag']})")
    L.append(f"### Bottled on hand — {rep['bottled_inventory_gal']} gal")
    for x in rep["bottled_inventory"]:
        L.append(f"- {x['batch']}: {x['units']} × {x['unit']} = {x['gal']} gal "
                 f"({x['tax_class']})")
    L += ["", "## F. Gaps to resolve before filing", ""]
    L += [f"- {g}" for g in rep["gaps"]] or ["- none flagged"]
    return "\n".join(L) + "\n"


def _section(title, headers, rows, total=None):
    head = f"<h2>{esc(title)}"
    if total is not None:
        head += f' <span class="pill">{esc(total)} gal</span>'
    head += "</h2>"
    return head + table(headers, rows, empty="Nothing in this period.")


@route("GET", "/ttb")
def ttb(req):
    start, end = _period(req.params)
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
    gaps = ""
    if rep["gaps"]:
        gaps = banner("Resolve before filing:\n"
                      + "\n".join(f"• {g}" for g in rep["gaps"]), "warn")
    prod = _section("A. Produced by fermentation",
                    ["Batch", "Recipe", "Started", "Gallons"],
                    [[raw(f'<a href="/batches/{esc(p["batch"])}">{esc(p["batch"])}</a>'),
                      p["recipe"], p["started"], num(p["gal"])]
                     for p in rep["production"]], rep["production_gal"])
    bott = _section("B. Bottled",
                    ["Batch", "Units", "Tax class", "Gallons"],
                    [[raw(f'<a href="/batches/{esc(b["batch"])}">{esc(b["batch"])}</a>'),
                      f"{b['units']} × {b['unit']}", b["tax_class"], num(b["gal"])]
                     for b in rep["bottled"]], rep["bottled_gal"])
    rem_rows = []
    for bucket, v in sorted(rep["removals"].items()):
        for r in v["rows"]:
            rem_rows.append([r["date"],
                             raw(f'<a href="/batches/{esc(r["batch"])}">{esc(r["batch"])}</a>'),
                             bucket, str(r["units"]), r.get("to") or "",
                             num(r["gal"])])
    rem = (f'<h2>C. Removals <span class="pill">taxable '
           f'{num(rep["taxable_removals_gal"])} gal</span></h2>'
           + table(["When", "Batch", "Bucket", "Units", "To", "Gallons"],
                   rem_rows, empty="No removals in this period."))
    loss = _section("D. Losses", ["Batch", "Why", "When", "Gallons"],
                    [[raw(f'<a href="/batches/{esc(x["batch"])}">{esc(x["batch"])}</a>'),
                      x["why"], x["date"], num(x["gal"])] for x in rep["losses"]],
                    rep["losses_gal"])
    inv = (f'<h2>E. Period-end inventory</h2>'
           + _section("Bulk (in tank)", ["Batch", "State", "Gallons"],
                      [[raw(f'<a href="/batches/{esc(x["batch"])}">{esc(x["batch"])}</a>'),
                        x["tag"], num(x["gal"])] for x in rep["bulk_inventory"]],
                      rep["bulk_inventory_gal"])
           + _section("Bottled on hand", ["Batch", "Units", "Tax class", "Gallons"],
                      [[raw(f'<a href="/batches/{esc(x["batch"])}">{esc(x["batch"])}</a>'),
                        f"{x['units']} × {x['unit']}", x["tax_class"], num(x["gal"])]
                       for x in rep["bottled_inventory"]],
                      rep["bottled_inventory_gal"]))
    export = f'''<form class="inline noprint" method="post" action="/ttb/export">
<input type="hidden" name="start" value="{esc(start)}">
<input type="hidden" name="end" value="{esc(end)}">
<button>Write it to data/reports/</button></form>'''
    body = lead + form + gaps + prod + bott + rem + loss + inv + export
    return Response(_page(f"TTB — {start} to {end}", body, "/ttb",
                          req.params.get("msg"), req.params.get("kind", "ok")))


@route("POST", "/ttb/export")
def ttb_export(req):
    start, end = _period(req.form)
    rep = calc.ttb_report(list(req.store.list_batches()), start, end)
    name = f"ttb-{start}-to-{end}.md"
    req.store.write_report(name, report_md(rep))
    from urllib.parse import urlencode
    return redirect("/ttb?" + urlencode({"start": start, "end": end}),
                    f"Wrote data/reports/{name}.", "ok")

"""Vessels: which fermenter holds what, and which are free.

Occupancy is derived — a vessel is busy because a batch that names it isn't
bottled yet, free once it is. Nothing here is a status kept by hand.
"""
from datetime import datetime

from . import calc
from .html import (banner, details, esc, field, num, once, page as _page, pill, raw,
                   sg, table)
from .server import Response, redirect, route


@route("GET", "/vessels")
def vessels(req):
    now = datetime.now()
    vs = req.store.list_vessels()
    batches = req.store.list_batches()
    occ = calc.vessel_occupancy(vs, batches, now)
    rows = []
    for o in occ:
        v = o["vessel"]
        cap = calc.vol_text(v["gal"]) if v.get("gal") else ""
        if o["free"]:
            state = raw(str(pill("free", "ok")))
            holds = ""
        else:
            # every batch that names this vessel — two is a mistake to fix,
            # not something to hide behind the first one
            bs = o["batches"]
            if len(bs) > 1:
                state = raw(str(pill(f"{len(bs)} batches", "warn")))
            else:
                state = raw(str(pill(bs[0]["tag"], "warn"
                                     if bs[0]["tag"] in ("Feed due", "Stalled",
                                                         "Reads high",
                                                         "Reading is old")
                                     else "")))
            holds = raw("".join(
                f'<a href="/batches/{esc(b["id"])}">{esc(b["id"])}</a>'
                f'<span class="sub">{esc(b["recipe"] or "")}'
                + (f' · {sg(b["sg"])}' if b["sg"] is not None else "")
                + (f' · day {b["day"]}' if b["day"] is not None else "")
                + "</span>" for b in bs))
        rows.append([raw(f'<b>{esc(v.get("name"))}</b>'), cap, state, holds])
    clashes = [(o["vessel"].get("name"), [b["id"] for b in o["batches"]])
               for o in occ if len(o["batches"]) > 1]
    warn = (banner("\n".join(
        f"{len(ids)} batches claim {name}: {', '.join(ids)} — only one can be "
        "in it. Fix the other on its batch page." for name, ids in clashes),
        "warn") if clashes else "")
    body = warn + table(["Vessel", "Capacity", "State", "Holding"], rows,
                 empty="No vessels yet — add your carboys and tanks below.")
    add = f'''<form class="inline" method="post" action="/vessels/add">{once()}
<div class="grid">
<span>{field("name", "Name", "", "Carboy 1, Fermenter 2, the 15-gal tank…", typ="text", required=True)}</span>
<span>{field("gal", "Capacity", "", "Optional. Gallons, or 3 bbl for the conical.", typ="text")}</span>
</div><button>Add vessel</button></form>'''
    body += details("Add a vessel", f'<div class="inner">{add}</div>',
                    open_=not vs)
    free = sum(1 for o in occ if o["free"])
    lede = (f"{free} of {len(vs)} free." if vs else None)
    return Response(_page("Vessels", body, "/vessels", req.params.get("msg"),
                          req.params.get("kind", "ok"), lede=lede))


@route("POST", "/vessels/add")
def vessels_add(req):
    try:
        v = req.store.add_vessel(req.form.get("name"), req.form.get("gal"),
                                  once=req.form.get("once"))
    except ValueError as e:
        return redirect("/vessels", str(e), "err")
    return redirect("/vessels", f"Added {v['name']}.", "ok")


@route("POST", r"/batches/(B-\d{4}-\d{3})/vessel")
def set_vessel(req):
    bid = req.args[0]
    req.store.set_batch_vessel(bid, req.form.get("vessel", ""))
    return redirect(f"/batches/{bid}",
                    "Vessel updated." if req.form.get("vessel", "").strip()
                    else "Vessel cleared.", "ok")

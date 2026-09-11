"""Compliance documents: permits, licences, COAs, insurance — and when each
one lapses. The only stored fact is the expiry date; the days remaining and
whether it is a problem are derived on every render. A lapsed permit is the
bad surprise this page (and Today) exist to prevent.
"""
from datetime import date

from . import calc
from .html import (banner, details, esc, field, page as _page, pill, raw,
                   table)
from .server import Response, redirect, route

# the pill next to each document — two visual levels; the phrase carries the
# rest ("expires in 21 days" vs "expired 5 days ago")
STATE_LABEL = {"ok": "current", "expiring": "expiring", "expired": "expired",
               "unknown": "check date"}


def _pill(state):
    return raw(str(pill(STATE_LABEL[state], "ok" if state == "ok" else "warn")))


def banner_for(needing):
    """The one warning line Today and this page share, worst first."""
    if not needing:
        return ""
    worst = "err" if any(d["state"] in ("expired", "unknown")
                         for d in needing) else "warn"
    lines = [f"{d['label']} — {calc.doc_phrase(d)}"
             + (f" ({d['expires']})" if d["state"] != "unknown" else "")
             for d in needing]
    return banner("Compliance:\n" + "\n".join(lines), worst)


@route("GET", "/documents")
def documents(req):
    today = date.today()
    docs = calc.document_status(req.store.list_documents(), today)
    needing = [d for d in docs if d["state"] != "ok"]
    rows = []
    for d in docs:
        sub = " · ".join(x for x in [d.get("kind"), d.get("ref")] if x)
        label = raw(f'<b>{esc(d["label"])}</b>'
                    + (f'<span class="sub">{esc(sub)}</span>' if sub else ""))
        status = raw(f'{_pill(d["state"])}'
                     f'<span class="sub">{esc(calc.doc_phrase(d))}</span>')
        renew = raw(
            f'<form class="mini noprint" method="post" '
            f'action="/documents/{esc(d["id"])}/renew">'
            f'{field("expires", "", "", None, typ="date", required=True)}'
            "<button>Renew</button></form>")
        rows.append([label, status, esc(d.get("expires") or "—"), renew])
    body = banner_for(needing)
    body += table(["Document", "Status", "Expires", "Renew to"], rows,
                  empty="No documents yet — add your permits and policies "
                        "below, and Today will warn you before any lapse.")
    kinds = "".join(f'<option value="{esc(k)}">' for k in
                    ("TTB Basic Permit", "State permit", "COA", "Insurance",
                     "Bond", "Licence"))
    add = f'''<form class="inline" method="post" action="/documents/add">
<div class="grid">
<span>{field("label", "Document", "", "TTB Basic Permit, CT Farm Winery Permit, Liability insurance…", typ="text", required=True)}</span>
<span>{field("expires", "Expires", "", "When it lapses.", typ="date", required=True)}</span>
</div>
<div class="grid">
<span>{field("kind", "Kind", "", "Optional — permit, insurance, COA…", typ="text", attrs='list="doc-kinds"')}
<datalist id="doc-kinds">{kinds}</datalist></span>
<span>{field("ref", "Reference no.", "", "Optional — permit or policy number.", typ="text")}</span>
</div>
<button>Add document</button></form>'''
    body += details("Add a document", f'<div class="inner">{add}</div>',
                    open_=not docs)
    lede = (f"{len(needing)} of {len(docs)} need attention."
            if needing else (f"All {len(docs)} current." if docs else None))
    return Response(_page("Documents", body, "/documents",
                          req.params.get("msg"),
                          req.params.get("kind", "ok"), lede=lede))


@route("POST", "/documents/add")
def documents_add(req):
    f = req.form
    try:
        d = req.store.add_document(f.get("label"), f.get("expires"),
                                   f.get("kind", ""), f.get("ref", ""),
                                   f.get("note", ""))
    except ValueError as e:
        return redirect("/documents", str(e), "err")
    return redirect("/documents", f"Added {d['label']}, expires {d['expires']}.",
                    "ok")


@route("POST", r"/documents/(D-\d{3})/renew")
def documents_renew(req):
    try:
        d = req.store.renew_document(req.args[0], req.form.get("expires"))
    except ValueError as e:
        return redirect("/documents", str(e), "err")
    return redirect("/documents",
                    f"Renewed {d['label']} to {d['expires']}.", "ok")

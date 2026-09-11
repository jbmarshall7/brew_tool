"""Today: what wants you, and a gravity field on every row.

The front door. Everything on it is derived on render from the readings,
the feed log and the pitch date — there is no state here to maintain, and
the footer says so, because that promise is the whole reason the page is
trustworthy.
"""
from datetime import datetime

from . import calc
from .chart import sparkline
from .html import (esc, field, hidden, next_link, num, page as _page, pill,
                   raw, sg, table)
from .server import Response, route
from .sheet import product_name


def look_at(store, now):
    """Every batch with the one sentence about it, most urgent first."""
    out = []
    for b in store.list_batches():
        act = calc.next_action(
            b, now, product_name((b.get("nutrients") or {}).get("product")))
        out.append((b, act))
    out.sort(key=lambda pair: (pair[1]["kind"] != "warn",
                               pair[0].get("pitched_at") or ""))
    return out


def attention_card(b, act):
    r = b.get("recipe") or {}
    now_sg = calc.current_sg(b)
    return (f'<div class="attn">'
            f'<span class="kick">{esc(act["tag"])}</span>'
            f'<h3>{esc(r.get("name") or b["id"])} · '
            f'{esc(sg(now_sg) if now_sg is not None else "—")}</h3>'
            f'<p>{esc(act["text"])}</p>'
            f'<p class="foot"><a class="btn" href="/batches/{esc(b["id"])}">'
            f'Open the batch</a> <span class="mut">{esc(b["id"])}</span></p>'
            "</div>")


def gravity_note(b, now):
    """The small line under the gravity: when it was read."""
    rows = calc.ledger((b.get("measured") or {}).get("og"),
                       b.get("pitched_at"), b.get("readings"))
    if not rows:
        return "OG from the must"
    ago = calc.day_of(rows[-1]["at"], now)
    return ("read today" if ago == 0 else
            f"read {ago} day{'s' if ago != 1 else ''} ago")


def row_log(batch_id):
    """A gravity field on the row itself: the daily job at one page load."""
    box = field("reading", "", "", None, step="0.001", required=True,
                attrs='placeholder="1.0__"', id_=f"sg-{batch_id}")
    return (f'<form class="mini noprint" method="post" '
            f'action="/batches/{esc(batch_id)}/reading">{box}'
            "<button>Log</button></form>")


def cellar_rows(pairs, now):
    rows = []
    for b, act in pairs:
        r = b.get("recipe") or {}
        now_sg = calc.current_sg(b)
        rows.append([
            raw(f'<a href="/batches/{esc(b["id"])}">{esc(b["id"])}</a>'
                f'<span class="sub">{esc(r.get("name") or "")}'
                f' · {num(b.get("volume_gal"))} gal</span>'),
            str(calc.day_of(b["pitched_at"], now)),
            raw(f'{esc(sg(now_sg) if now_sg is not None else "—")}'
                f'<span class="sub">{esc(gravity_note(b, now))}</span>'),
            raw(sparkline(b)),
            raw(f'{pill(act["tag"], act["kind"])}'
                f'<span class="sub">{esc(act["text"])}</span>'),
            raw(row_log(b["id"])),
        ])
    return rows


def documents_alert(store, now):
    """The compliance banner Today shares with the Documents page, or ''."""
    from .views_documents import banner_for
    needing = calc.documents_needing_attention(store.list_documents(),
                                               now.date())
    return banner_for(needing)


@route("GET", "/")
def today(req):
    now = datetime.now()
    pairs = look_at(req.store, now)
    title = f"{now:%A, %B} {now.day}"
    docs = documents_alert(req.store, now)
    if not pairs:
        body = (docs
                + '<p class="mut">Nothing is fermenting. Design a recipe and '
                "make the must, and this page fills itself in.</p>"
                + next_link("/design", "Design a recipe"))
        return Response(_page(title, body, "/", req.params.get("msg"),
                              req.params.get("kind", "ok")))
    wants = [(b, a) for b, a in pairs if a["kind"] == "warn"]
    going = len(pairs)
    lede = ("Nothing wants you today — it is all just fermenting quietly."
            if not wants else
            f"{len(wants)} of your {going} batch"
            f"{'es' if going != 1 else ''} want{'s' if len(wants) == 1 else ''}"
            " you today. The rest is just fermenting quietly.")
    body = docs
    if wants:
        body += ("<h2>Needs you now</h2><div class=\"attns\">"
                 + "".join(attention_card(b, a) for b, a in wants) + "</div>")
    body += ('<div class="sheet-head"><h2>In the cellar</h2>'
             '<span class="mut">type a gravity on any row — the app does '
             "the rest</span></div>"
             + '<div class="cellar">'
             + table(["Batch", "Day", "Gravity", "Trend", "Next thing",
                      "Log a reading"], cellar_rows(pairs, now))
             + "</div>"
             + '<p class="mut">Nothing here is a status you have to keep up '
               "to date — every line is derived from the readings, the "
               "feedings you logged and the pitch date.</p>")
    return Response(_page(title, body, "/", req.params.get("msg"),
                          req.params.get("kind", "ok"), lede=lede, wide=True))

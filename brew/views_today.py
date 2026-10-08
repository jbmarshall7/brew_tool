"""Today: what wants you, and a gravity field on every row.

The front door. Everything on it is derived on render from the readings,
the feed log and the pitch date — there is no state here to maintain, and
the footer says so, because that promise is the whole reason the page is
trustworthy.
"""
from datetime import datetime

from . import calc
from .chart import sparkline
from .html import (banner, esc, field, hidden, next_link, num, once,
                   page as _page, pill, raw, sg, table)
from .server import Response, route
from .sheet import product_name


# what the problems a hand-edited file can cause look like in Python —
# each costs that batch's row a warning, never the whole page
UNREADABLE = (ValueError, KeyError, TypeError, AttributeError)


def cant_read(b, e):
    return {"kind": "warn", "tag": "Can't read",
            "text": f"{e} — fix data/batches/{b.get('id') or '?'}.json by hand"}


def look_at(store, now):
    """Every batch with the one sentence about it, most urgent first. A
    batch whose file can't be understood still gets a row, saying so."""
    out = []
    for b in store.list_batches():
        try:
            act = calc.next_action(
                b, now, product_name((b.get("nutrients") or {}).get("product")))
        except UNREADABLE as e:
            act = cant_read(b, e)
        out.append((b, act))
    out.sort(key=lambda pair: (pair[1]["kind"] != "warn",
                               pair[0].get("pitched_at") or ""))
    return out


def fed_button(b, now):
    """'Fed #2' on a Feed-due card: records the feeding and comes back to
    Today, so the commonest urgent job is one tap, not a page load."""
    nf, _ = calc.next_feed(b, now)
    if not nf:
        return ""
    return (f'<form class="mini noprint" method="post" '
            f'action="/batches/{esc(b["id"])}/feed">{once()}'
            f'{hidden("n", str(nf["n"]))}{hidden("back", "today")}'
            f'<button>Fed #{nf["n"]}</button></form>')


def attention_card(b, act, now=None):
    r = b.get("recipe") or {}
    now_sg = calc.current_sg(b)
    fed = (fed_button(b, now or datetime.now())
           if act["tag"] == "Feed due" else "")
    return (f'<div class="attn">'
            f'<span class="kick">{esc(act["tag"])}</span>'
            f'<h3>{esc(r.get("name") or b["id"])} · '
            f'{esc(sg(now_sg) if now_sg is not None else "—")}</h3>'
            f'<p>{esc(act["text"])}</p>'
            f'<p class="foot">{fed}<a class="btn" href="/batches/{esc(b["id"])}">'
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
            f'action="/batches/{esc(batch_id)}/reading">{once()}{box}'
            "<button>Log</button></form>")


def cellar_rows(pairs, now):
    rows = []
    for b, act in pairs:
        try:
            rows.append(cellar_row(b, act, now))
        except UNREADABLE as e:
            bad = cant_read(b, e)
            rows.append([esc(b.get("id") or "?"), "—", "—", "",
                         raw(f'{pill(bad["tag"], "warn")}'
                             f'<span class="sub">{esc(bad["text"])}</span>'),
                         ""])
    return rows


def cellar_row(b, act, now):
    """One cellar row: the batch, its day, its gravity, the trend, what's
    next, and a gravity box while it can still take one."""
    r = b.get("recipe") or {}
    now_sg = calc.current_sg(b)
    return [
        raw(f'<a href="/batches/{esc(b["id"])}">{esc(b["id"])}</a>'
            f'<span class="sub">{esc(r.get("name") or "")}'
            f' · {num(b.get("volume_gal"))} gal</span>'),
        str(calc.day_of(b["pitched_at"], now)),
        raw(f'{esc(sg(now_sg) if now_sg is not None else "—")}'
            f'<span class="sub">{esc(gravity_note(b, now))}</span>'),
        raw(sparkline(b)),
        raw(f'{pill(act["tag"], act["kind"])}'
            f'<span class="sub">{esc(act["text"])}</span>'),
        # a bottled batch takes no more readings (the store refuses them)
        raw("" if calc.is_bottled(b) else row_log(b["id"])),
    ]


def bottled_rows(pairs):
    rows = []
    for b, act in pairs:
        pk = b.get("packaging") or {}
        r = b.get("recipe") or {}
        rows.append([
            raw(f'<a href="/batches/{esc(b["id"])}">{esc(b["id"])}</a>'
                f'<span class="sub">{esc(r.get("name") or "")}</span>'),
            f"{(pk.get('at') or '')[:10]} · {pk.get('units')} × "
            f"{pk.get('unit')}",
            str(calc.units_on_hand(b)),
            raw(f'{pill(act["tag"], act["kind"])}'
                f'<span class="sub">{esc(act["text"])}</span>'),
        ])
    return rows


def documents_alert(store, now):
    """The compliance banner Today shares with the Documents page, or ''."""
    from .views_documents import banner_for
    try:
        docs = store.list_documents()
    except ValueError as e:          # unreadable JSON: say so, keep the page
        return banner(f"Couldn't read the documents file — {e}", "warn")
    return banner_for(calc.documents_needing_attention(docs, now.date()))


@route("GET", "/")
def today(req):
    now = datetime.now()
    pairs = look_at(req.store, now)
    title = f"{now:%A, %B} {now.day}"
    docs = documents_alert(req.store, now)
    problems = req.store.unreadable()
    if problems:
        docs = banner("Some files couldn't be read and are left out:\n"
                      + "\n".join(problems), "warn") + docs
    if not pairs:
        body = (docs
                + '<p class="mut">Nothing is fermenting. Design a recipe and '
                "make the must, and this page fills itself in.</p>"
                + next_link("/design", "Design a recipe"))
        return Response(_page(title, body, "/", req.params.get("msg"),
                              req.params.get("kind", "ok")))
    wants = [(b, a) for b, a in pairs if a["kind"] == "warn"]
    # the cellar is what is still in a tank; a bottled batch moves to its own
    # short list while it has bottles (or a conditioning check) left
    active = [(b, a) for b, a in pairs if not calc.is_bottled(b)]
    bottled = [(b, a) for b, a in pairs if calc.is_bottled(b)
               and (a["kind"] == "warn" or a["tag"] == "Conditioning"
                    or (calc.units_on_hand(b) or 0) > 0)]
    going = len(active)
    lede = ("Nothing wants you today — it is all just fermenting quietly."
            if not wants else
            f"{len(wants)} batch{'es' if len(wants) != 1 else ''} "
            f"want{'s' if len(wants) == 1 else ''} you today. "
            + ("The rest is just fermenting quietly." if going else ""))
    body = docs
    if wants:
        body += ("<h2>Needs you now</h2><div class=\"attns\">"
                 + "".join(attention_card(b, a, now) for b, a in wants)
                 + "</div>")
    if active:
        body += ('<div class="sheet-head"><h2>In the cellar</h2>'
                 '<span class="mut">type a gravity on any row — the app does '
                 "the rest</span></div>"
                 + '<div class="cellar">'
                 + table(["Batch", "Day", "Gravity", "Trend", "Next thing",
                          "Log a reading"], cellar_rows(active, now))
                 + "</div>")
    if bottled:
        body += ("<h2>Bottled</h2>"
                 + table(["Batch", "Bottled", "On hand", "Now"],
                         bottled_rows(bottled)))
    body += (next_link("/batches", "All batches, finished ones too")
             + '<p class="mut">Nothing here is a status you have to keep up '
               "to date — every line is derived from the readings, the "
               "feedings you logged and the pitch date.</p>")
    return Response(_page(title, body, "/", req.params.get("msg"),
                          req.params.get("kind", "ok"), lede=lede, wide=True))

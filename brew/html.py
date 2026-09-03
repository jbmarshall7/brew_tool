"""The page chrome and the small HTML vocabulary every page is built from.

Server-rendered, one stylesheet inlined into every page (there is no static
route to get wrong), escaped by default: every value goes through `esc`
unless it is wrapped in `raw`, and `raw` is only for markup this module or
a view built itself.
"""
from html import escape as _escape

CSS = """
:root { --bg:#f6f3ec; --card:#fffdf8; --ink:#2c2620; --mut:#8a7f70;
        --line:#e6dfd2; --accent:#8c6d1f; --accent-dk:#6f5518;
        --ok:#3a7d44; --err:#a63d2f; --warn:#b07d2b; --head:#332b23; }
* { box-sizing:border-box; }
body { margin:0; font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;
       background:var(--bg); color:var(--ink); }
header { background:var(--head); color:#f3ead9; padding:10px 20px;
         display:flex; align-items:baseline; gap:20px; flex-wrap:wrap; }
header .brand { font-weight:700; letter-spacing:.3px; }
header nav { display:flex; gap:18px; }
header nav a { color:#d9c89a; text-decoration:none; padding:6px 0;
               min-height:40px; display:inline-flex; align-items:center; }
header nav a:hover { color:#fff; }
header nav a.active { color:#fff; box-shadow:inset 0 -2px 0 var(--accent); }
main { max-width:860px; margin:0 auto; padding:18px 20px 80px; }
h1 { font-size:22px; margin:12px 0 10px; }
h2 { font-size:15px; margin:26px 0 8px; padding-bottom:4px;
     border-bottom:1px solid var(--line); }
a { color:var(--accent); }
.card { background:var(--card); border:1px solid var(--line); border-radius:8px;
        padding:14px 18px; margin:10px 0; }
.card h2:first-child { margin-top:2px; }
.kv { display:grid; grid-template-columns:150px 1fr; gap:4px 14px;
      padding:9px 0; border-bottom:1px dashed var(--line); align-items:baseline; }
.kv:last-child { border-bottom:none; }
.kv b { color:var(--mut); font-weight:600; font-size:12.5px;
        text-transform:uppercase; letter-spacing:.3px; padding-top:4px; }
.kv .v { font-size:19px; font-weight:600; }
.kv .v small { font-size:14px; font-weight:400; color:var(--mut); }
.kv .n { grid-column:2; color:var(--mut); font-size:13px; }
.pill { display:inline-block; padding:2px 10px; border-radius:11px; font-size:12px;
        font-weight:600; background:#ece2cf; color:#6d5b34; vertical-align:middle; }
.pill.ok { background:#dcecdf; color:var(--ok); }
.pill.warn { background:#f6dcd0; color:var(--err); }
.tw { overflow-x:auto; margin:8px 0; }
table { border-collapse:collapse; width:100%; background:var(--card);
        border:1px solid var(--line); border-radius:8px; font-size:15px; }
th,td { text-align:left; padding:8px 11px; border-bottom:1px solid var(--line);
        vertical-align:top; }
th { background:#efe9dc; font-size:12px; text-transform:uppercase;
     letter-spacing:.5px; color:#6d6152; }
tr:last-child td { border-bottom:none; }
form.inline { background:var(--card); border:1px solid var(--line);
              border-radius:8px; padding:14px 18px; margin:8px 0; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr));
        gap:6px 16px; align-items:start; }
label { display:block; font-size:13px; color:var(--mut); margin-top:10px; }
.hint { display:block; font-size:12.5px; color:var(--mut); margin-top:3px; }
input,select,textarea { width:100%; max-width:420px; padding:9px 11px; font:inherit;
       font-size:17px; min-height:44px; border:1px solid #cbc1af; border-radius:5px;
       background:#fff; color:var(--ink); }
textarea { min-height:70px; }
input:focus,select:focus,textarea:focus { outline:2px solid #d9c48a;
       border-color:var(--accent); }
button { margin-top:14px; padding:10px 20px; font:inherit; font-size:16px;
         font-weight:600; min-height:44px; background:var(--accent); color:#fff;
         border:none; border-radius:6px; cursor:pointer; }
button:hover { background:var(--accent-dk); }
button.quiet { background:transparent; color:var(--accent-dk);
               border:1px solid #cbc1af; }
.msg { padding:12px 15px; border-radius:8px; margin:12px 0; white-space:pre-wrap;
       font-size:15px; border:1px solid; }
.msg.ok { background:#eaf4ec; border-color:#bcd8c2; color:#2f5d3c; }
.msg.err { background:#f9ece9; border-color:#e0b8b0; color:var(--err); }
.msg.warn { background:#f8f1e2; border-color:#e2cf9f; color:#7a5a1d; }
.mut { color:var(--mut); font-size:13.5px; }
.next { font-size:15px; margin:12px 0; }
.next a { font-weight:600; }
details.sec { margin:10px 0; }
details.sec > summary { cursor:pointer; font-size:15px; font-weight:600;
        color:var(--accent-dk); padding:11px 14px; min-height:44px;
        background:var(--card); border:1px solid var(--line); border-radius:8px;
        list-style-position:inside; }
details.sec[open] > summary { border-radius:8px 8px 0 0; }
details.sec > form.inline, details.sec > .inner { border-radius:0 0 8px 8px;
        margin-top:0; border-top:none; }
.inner { background:var(--card); border:1px solid var(--line); padding:12px 18px; }
@media print {
  header, form, button, details, .msg, .noprint { display:none !important; }
  body { background:#fff; font-size:14px; } main { max-width:none; padding:0; }
  .card { border:none; padding:6px 0; }
}
@media (max-width:640px) {
  header { padding:8px 14px; gap:12px; }
  main { padding:12px 12px 60px; }
  .kv { grid-template-columns:1fr; gap:0; } .kv .n { grid-column:1; }
  .kv b { padding-top:0; }
}
"""

NAV = [("/", "Design"), ("/recipes", "Recipes")]


class raw(str):
    """Marker: already HTML, interpolate verbatim."""
    __slots__ = ()


def esc(value):
    if isinstance(value, raw):
        return str(value)
    return _escape(str(value), quote=True)


def page(title, body, active="/", msg=None, kind="ok"):
    nav = "".join(
        f'<a href="{href}"{" class=active" if href == active else ""}>'
        f"{esc(label)}</a>" for href, label in NAV)
    top = banner(msg, kind) if msg else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{esc(title)} — brew_tool</title><style>{CSS}</style></head>"
            f'<body><header><span class="brand">🍯 brew_tool</span>'
            f"<nav>{nav}</nav></header>"
            f"<main><h1>{esc(title)}</h1>{top}{body}</main></body></html>")


def banner(text, kind="ok"):
    kind = kind if kind in ("ok", "warn", "err") else "ok"
    return f'<div class="msg {kind}">{esc(text)}</div>'


def card(body, title=None):
    head = f"<h2>{esc(title)}</h2>" if title else ""
    return f'<div class="card">{head}{body}</div>'


def kv(rows):
    """Label / big value / muted note rows. Each row is (label, value[, note])."""
    out = []
    for row in rows:
        label, value = row[0], row[1]
        note = row[2] if len(row) > 2 and row[2] else ""
        out.append(f'<div class="kv"><b>{esc(label)}</b>'
                   f'<span class="v">{esc(value)}</span>'
                   + (f'<span class="n">{esc(note)}</span>' if note else "")
                   + "</div>")
    return "".join(out)


def pill(text, kind=""):
    return raw(f'<span class="pill {esc(kind)}">{esc(text)}</span>')


def table(head, rows, empty="Nothing here yet."):
    if not rows:
        return f'<p class="mut">{esc(empty)}</p>'
    h = "".join(f"<th>{esc(c)}</th>" for c in head)
    body = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in r) + "</tr>"
                   for r in rows)
    return f'<div class="tw"><table><tr>{h}</tr>{body}</table></div>'


def details(summary, body, open_=False):
    return (f'<details class="sec"{" open" if open_ else ""}>'
            f"<summary>{esc(summary)}</summary>{body}</details>")


def next_link(href, text):
    return f'<p class="next"><a href="{esc(href)}">{esc(text)} →</a></p>'


def field(name, label, value="", hint=None, typ="number", step="any",
          required=False, attrs=""):
    v = "" if value is None else str(value)
    extra = ' inputmode="decimal"' if typ == "number" else ""
    stepattr = f' step="{step}"' if typ == "number" and step else ""
    req = " required" if required else ""
    return (f'<label for="f-{esc(name)}">{esc(label)}</label>'
            f'<input id="f-{esc(name)}" name="{esc(name)}" type="{typ}" '
            f'value="{esc(v)}"{stepattr}{extra}{req} {attrs}>'
            + (f'<span class="hint">{esc(hint)}</span>' if hint else ""))


def select(name, label, options, value=None, hint=None):
    opts = "".join(
        f'<option value="{esc(v)}"{" selected" if v == value else ""}>'
        f"{esc(lbl)}</option>" for v, lbl in options)
    return (f'<label for="f-{esc(name)}">{esc(label)}</label>'
            f'<select id="f-{esc(name)}" name="{esc(name)}">{opts}</select>'
            + (f'<span class="hint">{esc(hint)}</span>' if hint else ""))


def hidden(name, value):
    return f'<input type="hidden" name="{esc(name)}" value="{esc(value)}">'


# --- number formatting ------------------------------------------------------
def num(x, dp=2):
    """A number with at most `dp` decimals and no trailing zeros."""
    if x is None:
        return "—"
    s = f"{x:.{dp}f}".rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def sg(x):
    return f"{x:.3f}"


def lb_oz(lb):
    """18.29 lb → '18.29 lb (18 lb 5 oz)'; under a pound → '0.87 lb (14 oz)'."""
    whole = int(lb)
    oz = round((lb - whole) * 16)
    if oz == 16:
        whole, oz = whole + 1, 0
    if whole == 0:
        return f"{num(lb)} lb ({oz} oz)"
    return f"{num(lb)} lb ({whole} lb {oz} oz)"


def gal_l(gal):
    return f"{num(gal)} gal ({gal * 3.785:.1f} L)"

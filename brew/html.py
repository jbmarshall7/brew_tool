"""The page chrome and the small HTML vocabulary every page is built from.

Server-rendered, one stylesheet inlined into every page (there is no static
route to get wrong), escaped by default: every value goes through `esc`
unless it is wrapped in `raw`, and `raw` is only for markup this module or
a view built itself.

The look is the Organic design system from design_handoff_brew_tool_ui:
warm cream ground, terracotta accent, sage second voice, Caprasimo display
face over Figtree body, pill controls and soft-shadowed cards. Every number
on screen is still rendered server-side from calc.py — no arithmetic ever
moves into the browser.
"""
from html import escape as _escape

# Caprasimo (headings) over Figtree (body), served from the app itself so
# the cellar laptop keeps the design offline. The stacks still fall back to
# Georgia/system-ui if a face fails to load.
FONTS = ('<link rel="stylesheet" href="/fonts.css?v=1">')

# A warbler mark for the header bar — the handoff's placeholder, inline so
# there is still almost no static surface. Swap in the real logo when there
# is one.
BRAND_MARK = (
    '<svg width="30" height="30" viewBox="0 0 32 32" aria-hidden="true">'
    '<circle cx="16" cy="16" r="16" fill="#c67139"></circle>'
    '<path d="M22.5 11.2c-1.6-.6-3.2-.2-4.4.9-1.1 1-1.7 2.4-2.8 3.3-1.1.9-2.6'
    ' 1.2-3.9.9-.5-.1-.8.5-.4.8 1.2 1 1.6 2.6 1.1 4-.6 1.6-2.2 2.7-3.9 2.7'
    ' 2.6 1.4 5.9 1.1 8.4-.6 2.4-1.6 4-4.3 4.6-7.1l2.4-1.6c.3-.2.3-.7-.1-.8'
    'l-1.1-.4c.2-.7.5-1.4.9-2 .2-.4-.2-.8-.6-.6-.6.3-1.1.7-1.5 1.2z"'
    ' fill="#f5ead8"></path>'
    '<circle cx="19.2" cy="13.6" r="1" fill="#201e1d"></circle></svg>')

CSS = """
:root {
  /* Organic tokens — the ground, the ink, and two accents with their ramps */
  --bg:#f5ead8; --surface:#ebddc5; --card:#fff2eb; --ink:#201e1d;
  --mut:#645c50; --line:rgba(32,30,29,.16); --rule:rgba(32,30,29,.08);
  --accent:#c67139; --accent-600:#b2622d; --accent-700:#8c491a;
  --accent-100:#fff2eb; --accent-200:#ffe1d0; --accent-800:#643312;
  --sage:#7a8a5e; --sage-100:#f0fae1; --sage-200:#e1eecc;
  --sage-700:#56633f; --sage-800:#3d472b;
  --ok:#56633f; --err:#8c491a; --warn:#b2622d; --head:#ebddc5;
  --neutral-100:#f9f4ed; --neutral-800:#474238;
  --font-head:"Caprasimo",Georgia,serif;
  --font-body:"Figtree",system-ui,-apple-system,"Segoe UI",sans-serif;
  --r-card:28px; --r-inner:22px; --shadow:0 1px 2px rgba(46,43,37,.14);
}
* { box-sizing:border-box; }
body { margin:0; font:16px/1.55 var(--font-body); background:var(--bg);
       color:var(--ink); }
h1,h2,h3 { font-family:var(--font-head); font-weight:400; line-height:1.12;
           letter-spacing:-.015em; }

/* — header: a cream bar, not a dark one; the current link is underlined — */
header { background:var(--head); color:var(--ink); padding:14px 26px;
         display:flex; align-items:center; gap:22px; flex-wrap:wrap;
         border-bottom:1px solid var(--line); }
header .brand { font-family:var(--font-head); font-size:19px;
                display:inline-flex; align-items:center; gap:11px;
                margin-right:auto; }
header .brand svg { display:block; }
header nav { display:flex; gap:20px; }
header nav a { color:var(--ink); text-decoration:none; font-size:15px;
               min-height:44px; display:inline-flex; align-items:center;
               border-bottom:2px solid transparent; }
header nav a:hover { color:var(--accent-700); }
header nav a.active { color:var(--accent); border-bottom-color:var(--accent); }

main { max-width:980px; margin:0 auto; padding:26px 26px 90px; }
/* Today lays six columns across; the design draws it at 1240 */
main.wide { max-width:1240px; }
h1 { font-size:38px; margin:10px 0 6px; }
h2 { font-size:23px; margin:30px 0 10px; padding-bottom:0; border:none; }
a { color:var(--accent-700); text-underline-offset:3px; }
a:hover { color:var(--accent); }
::selection { background:rgba(198,113,57,.3); }
:focus { outline:none; }
:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }

/* the one-line answer to "what is this page for", under the title */
p.lede { max-width:660px; font-size:15px; color:var(--mut); margin:0 0 4px; }

/* — cards, kv rows — */
.card { background:var(--card); border:none; border-radius:var(--r-card);
        padding:22px 26px; margin:16px 0; box-shadow:var(--shadow); }
.card h2:first-child { margin-top:0; }
.kv { display:grid; grid-template-columns:158px 1fr; gap:3px 20px;
      padding:11px 0; border-bottom:1px solid var(--rule);
      align-items:baseline; }
.kv:last-child { border-bottom:none; }
.kv b { color:var(--mut); font-weight:400; font-size:13.5px;
        text-transform:none; letter-spacing:0; padding-top:4px; }
.kv .v { font-family:var(--font-head); font-weight:400; font-size:20px;
         line-height:1.25; }
.kv .v small { font-family:var(--font-body); font-size:13px; color:var(--mut); }
.kv .n { grid-column:2; color:var(--mut); font-size:12.5px; line-height:1.45;
         opacity:.85; }

/* — pills / tags — */
.pill { display:inline-block; padding:4px 12px; border-radius:999px;
        font-size:11.5px; font-weight:600; background:var(--neutral-100);
        color:var(--neutral-800); vertical-align:middle; letter-spacing:.02em; }
.pill.ok { background:var(--sage-100); color:var(--sage-800); }
.pill.warn { background:var(--accent-100); color:var(--accent-800); }

/* a heading with its headline number beside it */
.sheet-head { display:flex; align-items:baseline; gap:12px; }
.sheet-head h2 { margin:0; flex:1; }

/* — tables — */
.tw { overflow-x:auto; margin:14px 0; background:var(--card);
      border-radius:var(--r-card); padding:8px 18px 12px;
      box-shadow:var(--shadow); }
table { border-collapse:collapse; width:100%; background:transparent;
        border:none; font-size:14.5px; }
th,td { text-align:left; padding:11px 10px; vertical-align:top; }
th { background:transparent; font-size:11px; text-transform:uppercase;
     letter-spacing:.08em; color:var(--mut);
     border-bottom:1px solid var(--line); }
td { border-bottom:1px solid var(--rule); }
tr:last-child td { border-bottom:none; }
tbody tr:hover { background:rgba(32,30,29,.04); }
td .sub { display:block; color:var(--mut); font-size:12.5px; margin-top:2px; }

/* — forms: pill inputs on the sand surface — */
form.inline { background:var(--card); border:none; border-radius:var(--r-card);
              padding:22px 26px; margin:14px 0; box-shadow:var(--shadow); }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr));
        gap:8px 20px; align-items:start; }
label { display:block; font-size:12.5px; color:var(--mut); margin-top:14px; }
.hint { display:block; font-size:12.5px; color:var(--mut); margin-top:5px;
        opacity:.85; line-height:1.45; }
input,select,textarea { width:100%; max-width:420px; padding:10px 16px;
       font:inherit; font-size:17px; min-height:44px; border:1px solid var(--line);
       border-radius:999px; background:var(--surface); color:var(--ink);
       caret-color:var(--accent); }
textarea { min-height:80px; border-radius:var(--r-inner); resize:vertical; }
input:hover,select:hover,textarea:hover { border-color:rgba(32,30,29,.45); }
input:focus,select:focus,textarea:focus { outline:none;
       border-color:var(--accent); }
input:focus-visible,select:focus-visible,textarea:focus-visible {
       outline:2px solid var(--accent); outline-offset:0; }

button { margin-top:18px; padding:12px 24px; font-family:var(--font-head);
         font-weight:400; font-size:15px; min-height:44px;
         background:var(--accent); color:var(--bg); border:none;
         border-radius:999px; cursor:pointer; }
button:hover { background:var(--accent-600); }
button:active { background:var(--accent-700); }
button.quiet { background:transparent; color:var(--ink);
               border:1px solid var(--line); }
button.quiet:hover { background:rgba(32,30,29,.07); }
button.block { width:100%; max-width:420px; }
button:disabled { opacity:.45; cursor:not-allowed; }
a.btn { display:inline-flex; align-items:center; min-height:44px; padding:0 22px;
        background:var(--accent); color:var(--bg); border-radius:999px;
        font-family:var(--font-head); text-decoration:none; white-space:nowrap; }
a.btn:hover { background:var(--accent-600); color:var(--bg); }

/* — pill radios (yeast) and the segmented control (nitrogen demand) — */
.tags { display:flex; gap:6px; flex-wrap:wrap; margin-top:5px; }
.tags label { display:inline-flex; align-items:center; margin:0;
        cursor:pointer; padding:0 15px; min-height:44px; font-size:13.5px;
        color:var(--neutral-800); background:var(--neutral-100);
        border:1px solid var(--line); border-radius:999px; }
.tags label:hover { background:rgba(32,30,29,.07); }
.tags input { position:absolute; opacity:0; width:0; height:0;
        pointer-events:none; }
.tags label.on { background:var(--accent); border-color:var(--accent);
        color:var(--bg); }
.tags label:focus-within { outline:2px solid var(--accent); outline-offset:2px; }
.seg { display:inline-flex; overflow:hidden; margin-top:5px;
       border:1px solid var(--line); border-radius:999px; }
.seg label, .seg a { display:inline-flex; align-items:center; margin:0;
       cursor:pointer; padding:0 18px; min-height:44px; font-size:13.5px;
       color:var(--ink); text-decoration:none; }
.seg label + label, .seg a + a { border-left:1px solid var(--line); }
.seg label.on, .seg a.on { background:var(--accent); color:var(--bg); }
.seg label:not(.on):hover, .seg a:not(.on):hover
       { background:rgba(32,30,29,.07); }
.seg input { position:absolute; opacity:0; width:0; height:0;
       pointer-events:none; }
.seg label:focus-within { outline:2px solid var(--accent); outline-offset:-2px; }

/* — the two-column working layout, and a stack of cards in one column — */
.cols { display:grid; grid-template-columns:minmax(300px,.85fr) minmax(0,1.15fr);
        gap:24px; align-items:start; margin-top:20px; }
.cols > * { min-width:0; }
.stack { display:flex; flex-direction:column; gap:18px; }
.stack > .card, .stack > form.inline { margin:0; }

/* — an inset working panel: the hydrometer check — */
.panel { background:rgba(198,113,57,.09); border-radius:24px;
         padding:18px 20px; margin:16px 0; }
.panel h3 { font-size:18px; margin:0 0 4px; }
.panel .row { display:flex; gap:10px; flex-wrap:wrap; align-items:flex-end; }
.panel .row > span { flex:0 0 auto; width:150px; }
.panel .row label { margin-top:0; }
.panel .row input { text-align:center; }
.panel .row button { margin-top:0; flex:none; white-space:nowrap; }

/* — a batch's identity row: the id, then the four figures on sand — */
.idrow { display:flex; flex-wrap:wrap; gap:16px; align-items:center;
         justify-content:space-between; margin:4px 0 14px; }
.idrow > div { display:flex; flex-wrap:wrap; gap:14px; align-items:center; }
.bid { font-size:12px; letter-spacing:.08em; text-transform:uppercase;
       color:var(--accent-700); }
.stats { display:flex; gap:26px; flex-wrap:wrap; background:var(--surface);
         border-radius:var(--r-card); padding:14px 22px; }
.stats .l { display:block; font-size:11px; letter-spacing:.07em;
            text-transform:uppercase; color:var(--mut); }
.stats .n { display:block; font-family:var(--font-head); font-size:26px;
            line-height:1.15; }

/* — the one sentence that says what to do about this batch — */
.nextbar { display:flex; gap:16px; align-items:center; flex-wrap:wrap;
           background:var(--card); border-radius:var(--r-card);
           padding:18px 22px; box-shadow:var(--shadow); margin:14px 0; }
.nextbar b { font-family:var(--font-head); font-weight:400; font-size:15px;
             color:var(--accent-800); }
.nextbar > span { flex:1; min-width:220px; font-size:15.5px; }

svg.curve { display:block; max-width:100%; height:auto; }

/* a one-control form inside a table row — the cheapest surface there is */
form.mini { margin:0; display:flex; gap:6px; align-items:center; }
form.mini input { width:92px; min-width:92px; max-width:92px; min-height:38px;
                  padding:0 12px; font-size:15px; text-align:center; }
form.mini label { display:none; }
form.mini button { margin-top:0; min-height:38px; padding:0 14px;
                   font-size:13.5px; white-space:nowrap; }

/* the cellar table: identity on one line, the sentence takes the slack */
.cellar td:first-child, .cellar th:first-child { white-space:nowrap; }
.cellar td:nth-child(5) { min-width:230px; }

/* — Today: the cards for what wants you, above the cellar table — */
.attns { display:grid; grid-template-columns:repeat(auto-fit,minmax(310px,1fr));
         gap:16px; margin:12px 0 4px; }
.attn { background:var(--accent-100); border-radius:32px; padding:20px 22px;
        box-shadow:var(--shadow); }
.attn .kick { font-size:10px; letter-spacing:.1em; text-transform:uppercase;
              color:var(--accent-700); }
.attn h3 { font-size:19px; margin:6px 0 8px; }
.attn p { margin:0; font-size:13.5px; line-height:1.5; opacity:.78; }
.attn p.foot { margin-top:14px; display:flex; align-items:center; gap:12px;
               flex-wrap:wrap; }
.attn .mut { font-size:11.5px; }

/* — banners — */
.msg { padding:15px 20px; border-radius:var(--r-inner); margin:16px 0;
       white-space:pre-wrap; font-size:14.5px; line-height:1.55; border:none; }
.msg.ok { background:var(--sage-200); color:var(--sage-800); }
.msg.err { background:var(--accent-200); color:var(--accent-800); }
.msg.warn { background:var(--accent-200); color:var(--accent-800); }
.mut { color:var(--mut); font-size:13px; opacity:.9; }
.next { font-size:15px; margin:16px 0; }
.next a { font-weight:600; }
.doit { display:flex; align-items:center; gap:14px; flex-wrap:wrap;
        margin-top:18px; }
.doit button { margin-top:0; min-height:46px; padding:0 26px; }
.doit .mut { font-size:12.5px; }

/* — disclosures — */
details.sec { margin:14px 0; }
details.sec > summary { cursor:pointer; font-family:var(--font-head);
        font-size:15px; color:var(--ink); padding:13px 22px; min-height:44px;
        background:var(--card); border:none; border-radius:999px;
        list-style-position:inside; box-shadow:var(--shadow); }
details.sec > summary:hover { color:var(--accent-700); }
details.sec[open] > summary { border-radius:var(--r-card) var(--r-card) 0 0; }
details.sec > form.inline, details.sec > .inner {
        border-radius:0 0 var(--r-card) var(--r-card); margin-top:0;
        border-top:none; }
.inner { background:var(--card); border:none; padding:18px 26px;
         box-shadow:var(--shadow); }

/* — the must-day steps: sage circles, bigger values — */
ol.steps { list-style:none; counter-reset:step; padding:0; margin:18px 0 0;
           display:flex; flex-direction:column; gap:14px; }
ol.steps li { counter-increment:step; display:grid;
              grid-template-columns:30px 1fr; gap:3px 14px; }
ol.steps li::before { content:counter(step); grid-row:1 / span 3; width:30px;
              height:30px; border-radius:50%; background:var(--sage-200);
              color:var(--sage-800); font-family:var(--font-head);
              font-size:14px; display:flex; align-items:center;
              justify-content:center; }
ol.steps .stitle { font-size:13px; color:var(--mut); text-transform:uppercase;
              letter-spacing:.06em; }
ol.steps .big { font-family:var(--font-head); font-weight:400; font-size:21px;
              line-height:1.25; }
ol.steps .mut { line-height:1.5; margin-top:3px; }

@media print {
  header, form, button, details, .msg.err, .noprint { display:none !important; }
  body { background:#fff; font-size:14px; }
  main { max-width:none; padding:0; }
  .card, .tw, .panel { border:none; box-shadow:none; padding:6px 0;
       border-radius:0; background:#fff; }
  .cols { display:block; }
  a { color:var(--ink); }
}
@media (max-width:860px) {
  .cols { grid-template-columns:1fr; }
}
@media (max-width:720px) {
  /* the cellar is the daily job, and the daily job happens on a phone, so
     each batch becomes a block with its gravity field at the bottom rather
     than a row four columns of sideways scrolling wide */
  .cellar table, .cellar tbody, .cellar tr, .cellar td { display:block;
        width:100%; }
  .cellar thead { display:none; }
  .cellar tr { padding:14px 2px; border-bottom:1px solid var(--line); }
  .cellar tr:last-child { border-bottom:none; }
  .cellar td { border:none; padding:3px 0; }
  .cellar td:first-child { white-space:normal; font-size:16px; }
  .cellar td:nth-child(2), .cellar td:nth-child(4) { display:none; }
  .cellar td:nth-child(5) { min-width:0; }
  .cellar form.mini { margin-top:8px; }
  .cellar form.mini input { flex:1; width:auto; max-width:none;
        min-height:44px; }
  .cellar form.mini button { min-height:44px; }
  .sheet-head { flex-wrap:wrap; gap:4px; }
  .sheet-head h2 { flex:1 0 100%; }
}
@media (max-width:640px) {
  header { padding:10px 16px; gap:14px; }
  main { padding:16px 14px 70px; }
  h1 { font-size:30px; }
  .card, form.inline, .inner { padding-left:18px; padding-right:18px; }
  .kv { grid-template-columns:1fr; gap:0; }
  .kv .n { grid-column:1; }
  .kv b { padding-top:0; }
  .panel .row > span { width:100%; }
}
"""

NAV = [("/", "Today"), ("/vessels", "Vessels"),
       ("/design", "Design & must"), ("/recipes", "Recipes"),
       ("/ttb", "TTB"), ("/documents", "Docs")]


class raw(str):
    """Marker: already HTML, interpolate verbatim."""
    __slots__ = ()


def esc(value):
    if isinstance(value, raw):
        return str(value)
    return _escape(str(value), quote=True)


def page(title, body, active="/", msg=None, kind="ok", tail="", lede=None,
         wide=False):
    nav = "".join(
        f'<a href="{href}"{" class=active" if href == active else ""}>'
        f"{esc(label)}</a>" for href, label in NAV)
    top = banner(msg, kind) if msg else ""
    intro = f'<p class="lede">{esc(lede)}</p>' if lede else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{esc(title)} — brew_tool</title>{FONTS}"
            f"<style>{CSS}</style></head>"
            f'<body><header><span class="brand">{BRAND_MARK}'
            f"Warblers Meadery</span>"
            f"<nav>{nav}</nav></header>"
            f'<main{" class=wide" if wide else ""}>'
            f"<h1>{esc(title)}</h1>{intro}{top}{body}</main>"
            f"{tail}</body></html>")


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
    return (f'<div class="tw"><table><thead><tr>{h}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def details(summary, body, open_=False):
    return (f'<details class="sec"{" open" if open_ else ""}>'
            f"<summary>{esc(summary)}</summary>{body}</details>")


def next_link(href, text):
    return f'<p class="next"><a href="{esc(href)}">{esc(text)} →</a></p>'


def field(name, label, value="", hint=None, typ="number", step="any",
          required=False, attrs="", id_=None):
    v = "" if value is None else str(value)
    fid = id_ or f"f-{name}"
    extra = ' inputmode="decimal"' if typ == "number" else ""
    stepattr = f' step="{step}"' if typ == "number" and step else ""
    if typ == "datetime-local":
        extra = ' placeholder="2026-09-03T15:40"'
        stepattr = ' step="60"' 
    req = " required" if required else ""
    return (f'<label for="{esc(fid)}">{esc(label)}</label>'
            f'<input id="{esc(fid)}" name="{esc(name)}" type="{typ}" '
            f'value="{esc(v)}"{stepattr}{extra}{req} {attrs}>'
            + (f'<span class="hint">{esc(hint)}</span>' if hint else ""))


def select(name, label, options, value=None, hint=None):
    opts = "".join(
        f'<option value="{esc(v)}"{" selected" if v == value else ""}>'
        f"{esc(lbl)}</option>" for v, lbl in options)
    return (f'<label for="f-{esc(name)}">{esc(label)}</label>'
            f'<select id="f-{esc(name)}" name="{esc(name)}">{opts}</select>'
            + (f'<span class="hint">{esc(hint)}</span>' if hint else ""))


def textarea(name, label, value="", hint=None, id_=None):
    fid = id_ or f"f-{name}"
    return (f'<label for="{esc(fid)}">{esc(label)}</label>'
            f'<textarea id="{esc(fid)}" name="{esc(name)}">{esc(value or "")}'
            "</textarea>"
            + (f'<span class="hint">{esc(hint)}</span>' if hint else ""))


def tag_radios(name, label, options, value, hint=None):
    """A row of pill radios — the design's yeast picker. Changing one
    submits the form, so the sheet recomputes the way a typed field does."""
    pills = "".join(
        f'<label class="{"on" if v == value else ""}">'
        f'<input type="radio" name="{esc(name)}" value="{esc(v)}"'
        f'{" checked" if v == value else ""}>{esc(lbl)}</label>'
        for v, lbl in options)
    return (f'<label>{esc(label)}</label><div class="tags">{pills}</div>'
            + (f'<span class="hint">{esc(hint)}</span>' if hint else ""))


def seg_control(name, label, options, value, hint=None):
    """A segmented control — one of three, all visible at once."""
    segs = "".join(
        f'<label class="{"on" if v == value else ""}">'
        f'<input type="radio" name="{esc(name)}" value="{esc(v)}"'
        f'{" checked" if v == value else ""}>{esc(lbl)}</label>'
        for v, lbl in options)
    return (f'<label>{esc(label)}</label><div class="seg">{segs}</div>'
            + (f'<span class="hint">{esc(hint)}</span>' if hint else ""))


def panel(inner, title=None):
    """An inset working panel on the accent tint (the hydrometer check)."""
    head = f"<h3>{esc(title)}</h3>" if title else ""
    return f'<div class="panel">{head}{inner}</div>'


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
    from .calc import sg_text
    return sg_text(x)


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

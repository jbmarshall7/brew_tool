"""Organic-themed drop-in replacements for brew/html.py.

Two things to paste into `brew/html.py`:

  1. `CSS` — replace the existing CSS constant with the one below. Every
     selector the views already use is still here (.card, .kv, .pill, .tw,
     table, form.inline, .grid, label, .hint, inputs, button, button.quiet,
     .msg, .mut, a.btn, td .sub, .next, details.sec, .inner, ol.steps,
     .stitle, .big, plus the print and narrow-screen queries), so no view
     changes are required to take the new look.

  2. `page()` — replace the existing function. Same signature, same NAV
     list; only the header markup changes (cream bar, brand mark, current
     link underlined instead of the dark-brown bar).

Python 3.9-safe, stdlib only, no JavaScript, nothing fetched at runtime
except the font stylesheet — see the note at the bottom of FONTS.
"""
from html import escape as _escape

# Caprasimo (headings) over Figtree (body). Loaded from Google Fonts; if the
# cellar laptop is offline the stacks below fall back to system-ui and every
# size/weight still holds. To go fully offline, drop the two .woff2 files
# next to brew/ and swap this for a pair of @font-face rules.
FONTS = ("<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">"
         "<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>"
         "<link rel=\"stylesheet\" href=\"https://fonts.googleapis.com/css2?"
         "family=Caprasimo&family=Figtree:wght@400;600;700&display=swap\">")

CSS = """
:root {
  /* Organic tokens — the ground, the ink, and two accents with their ramps */
  --bg:#f5ead8; --surface:#ebddc5; --card:#fff2eb; --ink:#201e1d;
  --mut:#645c50; --line:rgba(32,30,29,.16);
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
         display:flex; align-items:center; gap:22px; flex-wrap:wrap; }
header .brand { font-family:var(--font-head); font-size:19px;
                display:inline-flex; align-items:center; gap:10px;
                margin-right:auto; }
header .brand svg { display:block; }
header nav { display:flex; gap:20px; }
header nav a { color:var(--ink); text-decoration:none; font-size:15px;
               min-height:40px; display:inline-flex; align-items:center;
               border-bottom:2px solid transparent; }
header nav a:hover { color:var(--accent-700); }
header nav a.active { color:var(--accent); border-bottom-color:var(--accent); }

main { max-width:980px; margin:0 auto; padding:26px 26px 90px; }
h1 { font-size:38px; margin:10px 0 12px; }
h2 { font-size:23px; margin:30px 0 10px; padding-bottom:0; border:none; }
a { color:var(--accent-700); text-underline-offset:3px; }
a:hover { color:var(--accent); }
::selection { background:rgba(198,113,57,.3); }
:focus { outline:none; }
:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }

/* — cards, kv rows — */
.card { background:var(--card); border:none; border-radius:var(--r-card);
        padding:22px 26px; margin:16px 0; box-shadow:var(--shadow); }
.card h2:first-child { margin-top:0; }
.kv { display:grid; grid-template-columns:158px 1fr; gap:3px 20px;
      padding:11px 0; border-bottom:1px solid rgba(32,30,29,.08);
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
td { border-bottom:1px solid rgba(32,30,29,.08); }
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
button:disabled { opacity:.45; cursor:not-allowed; }
a.btn { display:inline-flex; align-items:center; min-height:44px; padding:0 22px;
        background:var(--accent); color:var(--bg); border-radius:999px;
        font-family:var(--font-head); text-decoration:none; white-space:nowrap; }
a.btn:hover { background:var(--accent-600); color:var(--bg); }

/* — banners — */
.msg { padding:15px 20px; border-radius:var(--r-inner); margin:16px 0;
       white-space:pre-wrap; font-size:14.5px; line-height:1.55; border:none; }
.msg.ok { background:var(--sage-200); color:var(--sage-800); }
.msg.err { background:var(--accent-200); color:var(--accent-800); }
.msg.warn { background:var(--accent-200); color:var(--accent-800); }
.mut { color:var(--mut); font-size:13px; opacity:.9; }
.next { font-size:15px; margin:16px 0; }
.next a { font-weight:600; }

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
ol.steps { list-style:none; counter-reset:step; padding:0; margin:18px 0; }
ol.steps li { counter-increment:step; display:grid;
              grid-template-columns:42px 1fr; gap:3px 14px; padding:18px 24px;
              margin:12px 0; background:var(--card); border:none;
              border-radius:var(--r-card); box-shadow:var(--shadow); }
ol.steps li::before { content:counter(step); grid-row:1 / span 3; width:32px;
              height:32px; border-radius:50%; background:var(--sage-200);
              color:var(--sage-800); font-family:var(--font-head);
              font-size:14px; display:flex; align-items:center;
              justify-content:center; }
ol.steps .stitle { font-size:12.5px; color:var(--mut); text-transform:uppercase;
              letter-spacing:.06em; font-weight:600; }
ol.steps .big { font-family:var(--font-head); font-weight:400; font-size:1.5em;
              line-height:1.25; }
ol.steps .mut { line-height:1.5; }

@media print {
  header, form, button, details, .msg.err, .noprint { display:none !important; }
  body { background:#fff; font-size:14px; }
  main { max-width:none; padding:0; }
  .card, .tw, ol.steps li { border:none; box-shadow:none; padding:6px 0;
       border-radius:0; }
  a { color:var(--ink); }
}
@media (max-width:640px) {
  header { padding:10px 16px; gap:14px; }
  main { padding:16px 14px 70px; }
  h1 { font-size:30px; }
  .card, form.inline, .inner, ol.steps li { padding-left:18px;
       padding-right:18px; }
  .kv { grid-template-columns:1fr; gap:0; }
  .kv .n { grid-column:1; }
  .kv b { padding-top:0; }
}
"""

NAV = [("/", "Design"), ("/recipes", "Recipes")]

# A small warbler mark for the header bar — replace with the real logo when
# there is one. Inline so there is still no static route to get wrong.
BRAND_MARK = (
    '<svg width="30" height="30" viewBox="0 0 32 32" aria-hidden="true">'
    '<circle cx="16" cy="16" r="16" fill="#c67139"></circle>'
    '<path d="M22.5 11.2c-1.6-.6-3.2-.2-4.4.9-1.1 1-1.7 2.4-2.8 3.3-1.1.9-2.6'
    ' 1.2-3.9.9-.5-.1-.8.5-.4.8 1.2 1 1.6 2.6 1.1 4-.6 1.6-2.2 2.7-3.9 2.7'
    ' 2.6 1.4 5.9 1.1 8.4-.6 2.4-1.6 4-4.3 4.6-7.1l2.4-1.6c.3-.2.3-.7-.1-.8'
    'l-1.1-.4c.2-.7.5-1.4.9-2 .2-.4-.2-.8-.6-.6-.6.3-1.1.7-1.5 1.2z"'
    ' fill="#f5ead8"></path>'
    '<circle cx="19.2" cy="13.6" r="1" fill="#201e1d"></circle></svg>')


def esc(value):
    """Unchanged — kept here only so this file reads standalone."""
    return _escape(str(value), quote=True)


def page(title, body, active="/", msg=None, kind="ok", tail=""):
    """Same signature as before; only the header markup and <head> change."""
    nav = "".join(
        f'<a href="{href}"{" class=active" if href == active else ""}>'
        f"{esc(label)}</a>" for href, label in NAV)
    top = banner(msg, kind) if msg else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{esc(title)} — brew_tool</title>{FONTS}"
            f"<style>{CSS}</style></head>"
            f'<body><header><span class="brand">{BRAND_MARK}'
            f"Warblers brew_tool</span>"
            f"<nav>{nav}</nav></header>"
            f"<main><h1>{esc(title)}</h1>{top}{body}</main>{tail}</body></html>")


def banner(text, kind="ok"):
    """Unchanged."""
    kind = kind if kind in ("ok", "warn", "err") else "ok"
    return f'<div class="msg {kind}">{esc(text)}</div>'

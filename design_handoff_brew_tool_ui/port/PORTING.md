# Porting the mockup's look into brew_tool

Two files here. Everything is stdlib-only, Python 3.9-safe, server-rendered,
and no arithmetic moves into JavaScript — `calc.py` is untouched.

## 1. The look — `port/html_organic.py`

Open `brew/html.py` and make three replacements from `port/html_organic.py`:

| Replace in `brew/html.py` | With |
| --- | --- |
| the `CSS = """…"""` constant | the `CSS` constant here |
| the `page()` function | the `page()` here |
| — (new) | the `FONTS` and `BRAND_MARK` constants, above `NAV` |

Nothing else changes. `esc`, `banner`, `card`, `kv`, `pill`, `table`,
`details`, `field`, `select`, `textarea`, `hidden`, `num`, `sg`, `lb_oz`,
`gal_l` and every view stay exactly as they are — the new stylesheet defines
the same selector set, so `python3 -m unittest discover -s tests` should pass
unchanged (the markup assertions in `test_views.py` are about classes and
values, not colors).

What you get: the cream-and-sand ground with the terracotta accent, Caprasimo
headings over Figtree, pill inputs and buttons, 28px cards on soft shadows
instead of hairline borders, sage circles on the must-day steps, and a cream
header bar whose current link is underlined in accent.

Two things to know:

- **Fonts come from Google Fonts** via the `FONTS` `<link>`. Offline in the
  cellar, the stacks fall back to Georgia/system-ui and every size still
  holds. To go fully offline, put `Caprasimo.woff2` and `Figtree.woff2` next
  to `brew/`, serve them from one new static route, and swap `FONTS` for two
  `@font-face` rules.
- **Touch targets stay ≥44px** (inputs, buttons, summaries, nav links) — the
  brief's phone-on-the-barrel constraint is preserved, and the `@media print`
  and `max-width:640px` blocks are both carried over.

The `BRAND_MARK` is my placeholder warbler. Drop the real logo in when you
have one; it is inline SVG so there is still no static route to get wrong.

## 2. The layouts

Almost all of the mockup's layout came from the CSS above — the bench sheet,
the five floor-order steps and the check form are already the right markup in
`sheet.py` and `views_must.py`, just spaced differently. One genuine markup
change is worth making, in `brew/sheet.py`:

```python
def render_sheet(p, title=None):
    head = ""
    if title:
        # the target OG reads as a tag beside the heading, so the sheet's
        # headline number is visible before you scan the rows
        head = (f'<div class="sheet-head"><h2>{esc(title)}</h2>'
                f'{pill("OG " + sg(p["og"]))}</div>')
    warn = "".join(banner(w, "warn") for w in p["warnings"])
    return f'<div class="card">{head}{kv(rows(p))}</div>{warn}'
```

Add `pill` and `sg` to that module's imports from `.html`, and one rule to
`CSS`:

```css
.sheet-head { display:flex; align-items:baseline; gap:12px; }
.sheet-head h2 { margin:0; }
```

That is the whole port. What is deliberately **not** here, because it needs
round-2 data rather than styling: the dashboard, the reading ledger, the
gravity curve and the feed tick-boxes all depend on `readings[]` on the batch
file, which DESIGN.md §9 puts out of scope. When you decide to let them in,
the mockup is the reference for what they look like — and the curve is plain
inline SVG rendered from the readings server-side, so it stays inside the
no-JS rule.

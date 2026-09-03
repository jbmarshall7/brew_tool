"""The Design page: two numbers in, the whole bench sheet out.

GET / with the targets in the query string. The first load is already an
answer (6 gal at 12 %); the owner changes what differs and reads the sheet.
Nothing is saved here.
"""
from . import calc
from .html import (card, details, esc, field, hidden, num, page as _page,
                   select)
from .server import Response, route

DEFAULTS = {"gal": "6", "abv": "12", "og": "", "fg": "1.000", "yeast": "71B",
            "yeast_g": "", "demand": "medium", "additions": "4"}


def inputs_from(params):
    """The design inputs from a query/form dict, defaults filled in."""
    return {k: (params.get(k) if params.get(k) not in (None,) else v)
            for k, v in DEFAULTS.items()}


def plan_from(inp):
    return calc.plan(inp["gal"], inp["abv"], inp["og"], inp["fg"],
                     inp["yeast_g"], inp["yeast"], inp["demand"], "fermaid-o",
                     inp["additions"])


def targets_form(inp, p=None):
    """Card 1. `p` (a plan) drives the yeast hint; None while input is bad."""
    if p is None:
        yeast_hint = "Blank = 1 g per gallon. Type what you'll actually pitch."
    elif p["high_og_pitch"]:
        yeast_hint = (f"1 g/gal says {num(p['yeast_default_g'], 1)} g. This "
                      f"must is over {calc.HIGH_OG_PITCH_SG:.3f}, so the sachet "
                      f"note says up to 2 g/gal "
                      f"({num(p['yeast_default_g'] * 2, 1)} g). Type what "
                      "you'll actually pitch.")
    else:
        yeast_hint = (f"Blank = 1 g per gallon ({num(p['yeast_default_g'], 1)} "
                      "g). Type what you'll actually pitch.")
    by_og = bool(inp["og"].strip()) if inp["og"] else False
    abv_hint = ("Strength is set by the OG below; clear it to set ABV instead."
                if by_og else
                "If it ferments dry (FG 1.000). A sweet finish means less "
                "alcohol, not less honey.")
    yeast_list = "".join(f'<option value="{esc(y)}">' for y in calc.KNOWN_YEASTS)
    more_open = by_og or inp["fg"] not in ("1.000", "1", "1.0", "") \
        or inp["demand"] != "medium" or inp["additions"] != "4"
    more = details("More: finish gravity, set OG instead, nitrogen demand, "
                   "number of feedings", f"""<div class="inner"><div class="grid">
<span>{field("fg", "Finish FG", inp["fg"], "1.000 is dry. 71B at 14 % may finish a few points higher.")}</span>
<span>{field("og", "Set OG instead", inp["og"], "Leave blank to set strength by ABV.")}</span>
<span>{select("demand", "Nitrogen demand", [("low", "low"), ("medium", "medium"), ("high", "high")], inp["demand"], "Most wine strains are medium. Check the strain's sheet.")}</span>
<span>{field("additions", "Fermaid O feedings", inp["additions"], "TOSNA is 4: 24 h, 48 h, 72 h, then by the 1/3 break.", step="1")}</span>
</div></div>""", open_=more_open)
    return f"""<form class="inline" method="get" action="/" id="targets">
<div class="grid">
<span>{field("gal", "Batch volume (gal)", inp["gal"], "Your carboys: 5, 6, 6.8.")}</span>
<span>{field("abv", "Target strength (% ABV)", inp["abv"], abv_hint)}</span>
<span>{field("yeast", "Yeast", inp["yeast"], "The strain sets the tolerance warning.", typ="text", attrs='list="yeasts"')}
<datalist id="yeasts">{yeast_list}</datalist></span>
<span>{field("yeast_g", "Yeast (g)", inp["yeast_g"], yeast_hint,
             attrs=f'placeholder="{num(p["yeast_default_g"], 1) if p else ""}"')}</span>
</div>
{more}
<button>Recompute</button>
</form>"""


def render(params, msg=None, kind="ok"):
    inp = inputs_from(params)
    err = None
    try:
        p = plan_from(inp)
    except ValueError as e:
        p, err = None, str(e)
    from .sheet import render_sheet
    body = targets_form(inp, p)
    if p:
        body += render_sheet(p, f"At {num(p['gal'])} gal you'll need")
    if err:
        msg, kind = err, "err"
    return _page("Design a recipe", body, "/", msg, kind)


@route("GET", "/")
def design(req):
    return Response(render(req.params, req.params.get("msg"),
                           req.params.get("kind", "ok")))

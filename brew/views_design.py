"""The Design page: two numbers in, the whole bench sheet out.

GET / with the targets in the query string. The first load is already an
answer (6 gal at 12 %); the owner changes what differs and reads the sheet.
The whole page is one form: Recompute is a GET back here, Save is the same
fields POSTed to /recipes — so a recompute never drops the name or notes.
"""
from . import calc
from .html import (details, esc, field, hidden, num, page as _page, select,
                   textarea)
from .server import Response, route

DEFAULTS = {"gal": "6", "abv": "12", "og": "", "fg": "1.000", "yeast": "71B",
            "demand": "medium", "additions": "4"}
# a blank here has no meaning, so it falls back to the default; a blank
# abv or og does mean something (strength set the other way)
BLANK_IS_DEFAULT = ("gal", "fg", "demand", "additions", "yeast")

# The page's only script: when a target changes, submit the same GET the
# Recompute button would, and after the reload put the cursor where it was
# headed. Changes in the save card don't recompute. No arithmetic lives
# here — every number is rendered by the server.
SCRIPT = """<script>
(function(){
  var f=document.getElementById('targets'); if(!f) return;
  var k='brew.focus', n=null;
  try { n=sessionStorage.getItem(k); sessionStorage.removeItem(k); } catch(e){}
  if(n){ var el=f.elements[n]; if(el){ el.focus(); if(el.select) el.select(); } }
  f.addEventListener('change', function(e){
    if(e.target.closest && e.target.closest('.save')) return;
    var els=Array.prototype.slice.call(f.elements), i=els.indexOf(e.target), nx=els[i+1];
    if(nx && nx.name && !nx.closest('details:not([open])')) {
      try { sessionStorage.setItem(k, nx.name); } catch(err){}
    }
    f.submit();
  });
})();
</script>"""


def inputs_from(params):
    """The design inputs from a query/form dict, defaults filled in."""
    out = {}
    for k, v in DEFAULTS.items():
        got = params.get(k)
        if got is None or (k in BLANK_IS_DEFAULT and str(got).strip() == ""):
            out[k] = v
        else:
            out[k] = got
    return out


def plan_from(inp):
    return calc.plan(inp["gal"], inp["abv"], inp["og"], inp["fg"],
                     inp["yeast"], inp["demand"], "fermaid-o",
                     inp["additions"])


def targets_card(inp, p=None):
    """Card 1: the two numbers, the strain, and the rarely-touched rest."""
    by_og = bool(str(inp["og"]).strip())
    abv_hint = ("Strength is set by the OG below; clear that to set ABV instead."
                if by_og else
                "If it ferments dry (FG 1.000). A sweet finish means less "
                "alcohol, not less honey.")
    yeast_list = "".join(f'<option value="{esc(y)}">' for y in calc.KNOWN_YEASTS)
    more_open = by_og or inp["fg"] not in ("1.000", "1", "1.0") \
        or inp["demand"] != "medium" or inp["additions"] != "4"
    more = details("More: finish gravity, set OG instead, nitrogen demand, "
                   "number of feedings", f"""<div class="inner"><div class="grid">
<span>{field("fg", "Finish FG", inp["fg"], "1.000 is dry. 71B at 14 % may finish a few points higher.")}</span>
<span>{field("og", "Set OG instead", inp["og"], "Leave blank to set strength by ABV.")}</span>
<span>{select("demand", "Nitrogen demand", [("low", "low"), ("medium", "medium"), ("high", "high")], inp["demand"], "Most wine strains are medium. Check the strain's sheet.")}</span>
<span>{field("additions", "Fermaid O feedings", inp["additions"], "TOSNA is 4: 24 h, 48 h, 72 h, then by the 1/3 break.", step="1")}</span>
</div></div>""", open_=more_open)
    return f"""<div class="card">
<div class="grid">
<span>{field("gal", "Batch volume (gal)", inp["gal"], "Your carboys: 5, 6, 6.8.")}</span>
<span>{field("abv", "Target strength (% ABV)", inp["abv"], abv_hint)}</span>
<span>{field("yeast", "Yeast", inp["yeast"], "The strain sets the tolerance warning. Grams are worked out below, in whole sachets.", typ="text", attrs='list="yeasts"')}
<datalist id="yeasts">{yeast_list}</datalist></span>
</div>
{more}
<button>Recompute</button>
</div>"""


def save_card(store, editing=None, params=None):
    """Card 3: name it and keep it. `editing` is the recipe being redesigned."""
    params = params or {}
    honeys = store.honey_names() if store else []
    honey_list = "".join(f'<option value="{esc(h)}">' for h in honeys)
    label = (f"Save changes to {editing['name']}" if editing
             else "Save recipe")
    name = params.get("name", editing["name"] if editing else "")
    honey = params.get("honey", editing.get("honey", "") if editing else "")
    notes = params.get("notes", editing.get("notes", "") if editing else "")
    return f"""<div class="card save">
<h2>{"Keep the changes" if editing else "Keep it as a recipe"}</h2>
<div class="grid">
<span>{field("name", "Name", name, "The honey and the strength make a good one.", typ="text", required=True)}</span>
<span>{field("honey", "Honey", honey, "Which honey this was designed around.", typ="text", attrs='list="honeys"')}
<datalist id="honeys">{honey_list}</datalist></span>
</div>
{textarea("notes", "Notes", notes, "Anything the sheet doesn't say: where the honey came from, what you'd change.")}
<button formmethod="post" formaction="/recipes">{esc(label)}</button></div>"""


def render(params, store=None, msg=None, kind="ok"):
    editing = None
    if params.get("recipe") and store:
        editing = store.load_recipe(params["recipe"])
        if "gal" not in params:
            from .views_recipes import inputs_from_recipe
            params = dict(params, **inputs_from_recipe(editing))
    inp = inputs_from(params)
    err = None
    try:
        p = plan_from(inp)
    except ValueError as e:
        p, err = None, str(e)
    from .sheet import render_sheet
    keep = hidden("recipe", editing["slug"]) if editing else ""
    keep += hidden("from_slug", editing["slug"]) if editing else ""
    body = f'<form method="get" action="/" id="targets">{keep}' \
        + targets_card(inp, p)
    if p:
        body += render_sheet(p, f"At {num(p['gal'])} gal you'll need")
        body += save_card(store, editing, params)
    body += "</form>"
    if err:
        msg, kind = err, "err"
    title = f"Redesign {editing['name']}" if editing else "Design a recipe"
    return _page(title, body, "/", msg, kind, tail=SCRIPT)


@route("GET", "/")
def design(req):
    return Response(render(req.params, req.store, req.params.get("msg"),
                           req.params.get("kind", "ok")))

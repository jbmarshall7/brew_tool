"""The Design page: two numbers in, the whole bench sheet out.

GET / with the targets in the query string. The first load is already an
answer (6 gal at 12 %); the owner changes what differs and reads the sheet.
The whole page is one form: Recompute is a GET back here, Save is the same
fields POSTed to /recipes — so a recompute never drops the name or notes.
"""
from . import calc
from .html import (details, esc, field, hidden, next_link, num,
                   page as _page, seg_control, tag_radios, textarea)
from .server import Response, route

LEDE = ("Two numbers in — a volume and a strength — and the whole bench "
        "sheet comes out, with the arithmetic shown. Nothing is saved "
        "until you name it.")

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
    if(e.target.type === 'radio'){ f.submit(); return; }
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


def targets_card(inp, p=None, store=None):
    """Card 1: the two numbers, the strain, and the rarely-touched rest."""
    by_og = bool(str(inp["og"]).strip())
    abv_hint = ("Strength is set by the OG below; clear that to set ABV instead."
                if by_og else
                "If it ferments dry (FG 1.000). A sweet finish means less "
                "alcohol, not less honey.")
    # the strains the tolerance table knows, plus whatever this recipe uses
    strains = list(calc.KNOWN_YEASTS)
    current = (inp["yeast"] or "").strip()
    known = next((k for k in strains if k.lower() == current.lower()), None)
    if current and known is None:
        strains.append(current)
        known = current
    more_open = by_og or inp["fg"] not in ("1.000", "1", "1.0")
    more = details("More: finish gravity, or set the OG instead",
                   f"""<div class="inner"><div class="grid">
<span>{field("fg", "Finish FG", inp["fg"], "1.000 is dry. 71B at 14 % may finish a few points higher.")}</span>
<span>{field("og", "Set OG instead", inp["og"], "Leave blank to set strength by ABV.")}</span>
</div></div>""", open_=more_open)
    return f"""<div class="card">
<h2>Targets</h2>
{field("gal", "Batch volume (gal)", inp["gal"], "Your carboys: 5, 6, 6.8.")}
{field("abv", "Target strength (% ABV)", inp["abv"], abv_hint)}
{tag_radios("yeast", "Yeast", [(y, y) for y in strains], known,
            "The strain sets the tolerance warning. Grams are worked out "
            "below, in whole sachets.")}
{seg_control("demand", "Nitrogen demand",
             [("low", "low"), ("medium", "medium"), ("high", "high")],
             inp["demand"],
             "Most wine strains are medium. Check the strain's sheet.")}
{field("additions", "Fermaid O feedings", inp["additions"], "TOSNA is 4: 24 h, 48 h, 72 h, then by the 1/3 break.", step="1")}
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
{field("name", "Name", name, "The honey and the strength make a good one.", typ="text", required=True)}
{field("honey", "Honey", honey, "Which honey this was designed around.", typ="text", attrs='list="honeys"')}
<datalist id="honeys">{honey_list}</datalist>
{textarea("notes", "Notes", notes, "Anything the sheet doesn't say: where the honey came from, what you'd change.")}
<button class="block" formmethod="post" formaction="/recipes">{esc(label)}</button></div>"""


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
    left = targets_card(inp, p, store)
    right = ""
    if p:
        left += save_card(store, editing, params)
        right = render_sheet(p, f"At {num(p['gal'])} gal you'll need")
        right += next_link(must_href(editing, p) if editing else "/recipes",
                           f"Make must at {num(p['gal'])} gal"
                           if editing else "Every recipe you've kept")
    body = (f'<form method="get" action="/design" id="targets">{keep}'
            f'<div class="cols"><div class="stack">{left}</div>'
            f'<div class="stack">{right}</div></div></form>')
    if err:
        msg, kind = err, "err"
    title = f"Redesign {editing['name']}" if editing else "Design a recipe"
    return _page(title, body, "/design", msg, kind, tail=SCRIPT,
                 lede=LEDE)


def must_href(recipe, p):
    return f"/recipes/{recipe['slug']}/must?gal={num(p['gal'])}"


@route("GET", "/design")
def design(req):
    return Response(render(req.params, req.store, req.params.get("msg"),
                           req.params.get("kind", "ok")))

# brew_tool

A small, fast tool for designing mead recipes and making the must. One
person, one carboy, a phone on the barrel.

It grew out of a much larger meadery-operations app that tried to do
everything at once. This one does two jobs and does them in a few taps:

1. **Design a recipe** — type a batch volume and a target strength, read the
   whole bench sheet: honey by weight (and the room it takes), water, yeast,
   Go-Ferm, the Fermaid O schedule, the gravity to stop feeding at. Every
   number shows the formula it came from.
2. **Make the must** — the recipe scaled to today's carboy, in the order you
   do things on the floor. Read the hydrometer and pH; it tells you whether
   you're on target and exactly what to stir in if not. Pitch, and it dates
   the feedings.

No tracking beyond that. No inventory, no lots, no readings log — yet.

## Run it

```
python3 -m brew
```

Opens http://127.0.0.1:8765/ in your browser. Python 3.9 or newer, standard
library only, nothing to install.

| Flag | What it does |
|---|---|
| `--lan` | Also answer phones on your network (prints the address to type). No login, so only on a network you trust. |
| `--port 9000` | A different port. |
| `--data DIR` | Keep recipes and batches somewhere else (default `data/` here; or set `BREW_DATA`). |
| `--no-open` | Don't open a browser. |

## Where things live

```
data/
  recipes/   one JSON file per recipe
  batches/   one JSON file per must you recorded
```

Plain JSON, human-readable, versioned by git. Batch ids are `B-YYYY-NNN`;
the id field is prefilled and editable, so if you're continuing a numbering
from elsewhere, type it the first time and the sequence carries on.

## Test it

```
python3 -m unittest discover -s tests
```

## The math

Lives in `brew/calc.py`, with every constant and its source. Planning
figures, not lab constants — the hydrometer has the last word, and the
pages say so where it matters.

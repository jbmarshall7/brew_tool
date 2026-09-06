"""Recipes and batches on disk: one JSON file per record, written whole.

`indent=2, sort_keys=True` so git diffs read; a temp file and os.replace so
a crash mid-write leaves the old file, never half of the new one. No index
files: the directory listing is the index.
"""
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "recipe"


class Store:
    def __init__(self, data_dir):
        self.data = Path(data_dir)
        self.recipes_dir = self.data / "recipes"
        self.batches_dir = self.data / "batches"
        self.recipes_dir.mkdir(parents=True, exist_ok=True)
        self.batches_dir.mkdir(parents=True, exist_ok=True)

    # --- files ---------------------------------------------------------------
    @staticmethod
    def write_json(path, obj):
        path = Path(path)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(obj, f, indent=2, sort_keys=True, ensure_ascii=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, str(path))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    @staticmethod
    def read_json(path):
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"{path.name} isn't valid JSON ({e}) — fix it "
                             "by hand or restore it from git")

    # --- recipes -------------------------------------------------------------
    def recipe_path(self, slug):
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug or ""):
            raise ValueError(f"'{slug}' isn't a recipe name I know")
        return self.recipes_dir / f"{slug}.json"

    def recipe_exists(self, slug):
        try:
            return self.recipe_path(slug).exists()
        except ValueError:
            return False

    def load_recipe(self, slug):
        path = self.recipe_path(slug)
        if not path.exists():
            raise ValueError(f"There's no recipe called '{slug}'.")
        return self.read_json(path)

    def save_recipe(self, recipe):
        self.write_json(self.recipe_path(recipe["slug"]), recipe)
        return recipe

    def _read_all(self, paths):
        """Every readable record; a broken file costs one row, not the page."""
        out = []
        for f in paths:
            try:
                doc = self.read_json(f)
            except ValueError as e:
                sys.stderr.write(f"brew_tool: skipping {e}\n")
                continue
            if isinstance(doc, dict):
                out.append(doc)
        return out

    def unreadable(self):
        """The files that could not be parsed, as plain-words messages."""
        problems = []
        for f in sorted(list(self.recipes_dir.glob("*.json"))
                        + list(self.batches_dir.glob("*.json"))):
            try:
                self.read_json(f)
            except ValueError as e:
                problems.append(str(e))
        return problems

    def list_recipes(self):
        out = self._read_all(sorted(self.recipes_dir.glob("*.json")))
        return sorted(out, key=lambda r: (r.get("name") or "").lower())

    def honey_names(self):
        return sorted({r.get("honey") for r in self.list_recipes()
                       if r.get("honey")}, key=str.lower)

    def yeast_names(self):
        return sorted({r.get("yeast") for r in self.list_recipes()
                       if r.get("yeast")}, key=str.lower)

    # --- batches -------------------------------------------------------------
    BATCH_ID = re.compile(r"B-(\d{4})-(\d{3})")

    def batch_path(self, batch_id):
        if not self.BATCH_ID.fullmatch(batch_id or ""):
            raise ValueError(f"'{batch_id}' isn't a batch id — they look like "
                             "B-2026-003")
        return self.batches_dir / f"{batch_id}.json"

    def batch_exists(self, batch_id):
        try:
            return self.batch_path(batch_id).exists()
        except ValueError:
            return False

    def load_batch(self, batch_id):
        path = self.batch_path(batch_id)
        if not path.exists():
            raise ValueError(f"There's no batch {batch_id}.")
        return self.read_json(path)

    def save_batch(self, batch):
        self.write_json(self.batch_path(batch["id"]), batch)
        return batch

    def add_reading(self, batch_id, reading, sample_f=None, cal_f=None,
                    note="", at=None):
        """Append one gravity to a batch. The corrected value is stored
        alongside what the glass actually said, the way must day does it —
        everything else the ledger shows is derived on render."""
        from . import calc
        batch = self.load_batch(batch_id)
        reading = calc.num(reading, "hydrometer reading", 0.950, 1.250)
        cal = (calc.DEFAULT_CAL_F if calc.blank(cal_f)
               else calc.num(cal_f, "hydrometer calibration", 32, 110, " °F"))
        if calc.blank(sample_f):
            sample_f, corrected = None, reading
        else:
            sample_f = calc.num(sample_f, "sample temperature", 32, 140, " °F")
            corrected = calc.hydro_correct(reading, sample_f, cal)
        when = calc.parse_when(at) if at else datetime.now()
        batch.setdefault("readings", []).append({
            "at": calc.fmt_when(when), "reading": reading,
            "sample_f": sample_f, "cal_f": cal, "sg": corrected,
            "note": (note or "").strip(),
        })
        batch["readings"].sort(key=lambda r: r.get("at") or "")
        self.save_batch(batch)
        return batch, corrected

    def record_feed(self, batch_id, n, at=None, note=""):
        """Record that a scheduled feeding was actually given.

        An event, not a status: append-only, like a reading, because whether
        the nutrient went in is the one thing about the schedule the app
        cannot derive. Nothing is ever un-ticked — a mistake is a note.
        """
        from . import calc
        batch = self.load_batch(batch_id)
        n = int(calc.num(n, "feeding number", 1, 99))
        planned = [a for a in (batch.get("nutrients") or {}).get("additions")
                   or [] if a.get("n") == n]
        if not planned:
            raise ValueError(f"{batch_id} has no feeding #{n}")
        if any(f.get("n") == n for f in batch.get("feeds") or []):
            raise ValueError(f"Feeding #{n} is already logged on {batch_id}")
        when = calc.parse_when(at) if at else datetime.now()
        batch.setdefault("feeds", []).append({
            "n": n, "at": calc.fmt_when(when), "g": planned[0].get("g"),
            "note": (note or "").strip()})
        batch["feeds"].sort(key=lambda f: f.get("n") or 0)
        self.save_batch(batch)
        return batch, planned[0]

    def list_batches(self):
        out = self._read_all(self.batches_dir.glob("*.json"))
        return sorted(out, key=lambda b: (b.get("pitched_at") or "",
                                          b.get("id") or ""), reverse=True)

    def batches_for_recipe(self, slug):
        return [b for b in self.list_batches()
                if (b.get("recipe") or {}).get("slug") == slug]

    def batch_ids(self):
        return [f.stem for f in self.batches_dir.glob("B-*.json")]

    def last_batch(self, slug=None):
        batches = self.batches_for_recipe(slug) if slug else self.list_batches()
        return batches[0] if batches else None

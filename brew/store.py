"""Recipes and batches on disk: one JSON file per record, written whole.

`indent=2, sort_keys=True` so git diffs read; a temp file and os.replace so
a crash mid-write leaves the old file, never half of the new one. No index
files: the directory listing is the index.
"""
import json
import os
import re
import tempfile
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

    def list_recipes(self):
        out = []
        for f in sorted(self.recipes_dir.glob("*.json")):
            out.append(self.read_json(f))
        return sorted(out, key=lambda r: (r.get("name") or "").lower())

    def honey_names(self):
        return sorted({r.get("honey") for r in self.list_recipes()
                       if r.get("honey")}, key=str.lower)

    def yeast_names(self):
        return sorted({r.get("yeast") for r in self.list_recipes()
                       if r.get("yeast")}, key=str.lower)

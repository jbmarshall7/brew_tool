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

    FLAVOR_KINDS = ("fruit", "spice", "oak", "other")

    def record_flavor(self, batch_id, kind, item, qty=None, unit="",
                      at=None, note=""):
        """Record a flavor addition — fruit, spice or oak going into the mead."""
        from . import calc
        batch = self.load_batch(batch_id)
        kind = (kind or "").strip().lower()
        if kind not in self.FLAVOR_KINDS:
            raise ValueError(f"'{kind}' isn't one of "
                             f"{', '.join(self.FLAVOR_KINDS)}")
        item = (item or "").strip()
        if not item:
            raise ValueError("give the fruit, spice or oak a name")
        entry = {"at": calc.fmt_when(calc.parse_when(at) if at
                                     else datetime.now()),
                 "kind": kind, "item": item, "note": (note or "").strip()}
        if not calc.blank(qty):
            entry["qty"] = calc.num(qty, "quantity", 0, 100000)
            entry["unit"] = (unit or "").strip() or "lb"
        batch.setdefault("flavors", []).append(entry)
        batch["flavors"].sort(key=lambda f: f.get("at") or "")
        self.save_batch(batch)
        return batch

    def pull_flavor(self, batch_id, index, at=None):
        """Stamp a flavor addition as pulled — stops its contact clock."""
        from . import calc
        batch = self.load_batch(batch_id)
        flavors = batch.get("flavors") or []
        if not 0 <= index < len(flavors):
            raise ValueError(f"no flavor addition #{index + 1}")
        if flavors[index].get("pulled_at"):
            raise ValueError("that one is already pulled")
        flavors[index]["pulled_at"] = calc.fmt_when(
            calc.parse_when(at) if at else datetime.now())
        self.save_batch(batch)
        return batch

    def record_racking(self, batch_id, volume_gal, at=None, note=""):
        """Record racking off the lees: the measured volume now in the vessel.

        Every dose from here on is per this gallon, so it is measured, not
        computed. You cannot rack into more than you had.
        """
        from . import calc
        batch = self.load_batch(batch_id)
        vol = calc.num(volume_gal, "volume", 0.05, 1000, " gal")
        have = calc.current_volume(batch)
        if have and vol > have + 0.05:
            raise ValueError(
                f"{calc.sg_text(vol) if False else vol} gal is more than the "
                f"{have} gal you had — racking loses a little, it does not add")
        when = calc.parse_when(at) if at else datetime.now()
        batch.setdefault("rackings", []).append(
            {"at": calc.fmt_when(when), "volume_gal": round(vol, 2),
             "note": (note or "").strip()})
        batch["rackings"].sort(key=lambda r: r.get("at") or "")
        self.save_batch(batch)
        return batch

    def record_stabilize(self, batch_id, ph, at=None, note="",
                         molecular=None, override_reason=None):
        """Stabilize: sorbate AND sulfite, dosed from pH and the volume now.

        Refused on a mead that is still working (sulfite will not stop it) and
        on one already stabilized, unless a reason is recorded. Sorbate alone
        is never an option here — the two go in together.
        """
        from . import calc
        batch = self.load_batch(batch_id)
        ph = calc.num(ph, "pH", 2.0, 4.5)
        molecular = (calc.MOLECULAR_SO2_TARGET if calc.blank(molecular)
                     else calc.num(molecular, "molecular SO2 target", 0.5, 2.0))
        if calc.is_stabilized(batch) and not (override_reason or "").strip():
            raise ValueError(f"{batch_id} is already stabilized — a second "
                             "dose needs a recorded reason")
        if calc.is_primed(batch) and not (override_reason or "").strip():
            raise ValueError(
                "This mead is primed to bottle-condition — stabilizing it now "
                "kills the yeast and it will never carbonate. Record a reason "
                "if you mean to abandon the sparkling plan")
        if not calc.is_stable(batch) and not (override_reason or "").strip():
            raise ValueError(
                "This mead has not held a steady gravity for "
                f"{calc.STABLE_DAYS} days yet — sulfite will not stop a working "
                "ferment. Log a couple of flat readings first, or record a "
                "reason to override")
        vol = calc.current_volume(batch)
        og = (batch.get("measured") or {}).get("og")
        abv_now = calc.abv(og, calc.current_sg(batch)) if og else 0.0
        d = calc.stabilize_doses(vol, ph, abv_now, molecular)
        when = calc.parse_when(at) if at else datetime.now()
        entry = {"at": calc.fmt_when(when), "ph": ph, "volume_gal": d["gallons"],
                 "kmeta_g": d["kmeta_g"], "sorbate_g": d["sorbate_g"],
                 "free_so2_ppm": d["free_so2_ppm"], "molecular": molecular,
                 "note": (note or "").strip()}
        if (override_reason or "").strip():
            entry["override"] = override_reason.strip()
        batch.setdefault("stabilizations", []).append(entry)
        batch["stabilizations"].sort(key=lambda x: x.get("at") or "")
        self.save_batch(batch)
        return batch, d

    def record_backsweeten(self, batch_id, to_sg, at=None, note="",
                           override_reason=None):
        """Back-sweeten to a target gravity: refused unless already stabilized
        (or a reason is recorded — a keg you will force-carbonate, say). The
        honey is computed from the gravity you are raising it from."""
        from . import calc
        batch = self.load_batch(batch_id)
        to_sg = calc.num(to_sg, "target gravity", 0.990, 1.200)
        from_sg = calc.current_sg(batch)
        if from_sg is None:
            raise ValueError("no gravity on record to sweeten up from")
        if not calc.is_stabilized(batch) and not (override_reason or "").strip():
            raise ValueError(
                "Stabilize first — sorbate and sulfite together — or this "
                "sugar can restart the ferment and make bottle bombs. Record "
                "a reason to override (a keg you will force-carbonate)")
        honey = calc.backsweeten_honey(calc.current_volume(batch), from_sg,
                                       to_sg)
        when = calc.parse_when(at) if at else datetime.now()
        entry = {"at": calc.fmt_when(when), "from_sg": from_sg, "to_sg": to_sg,
                 "honey_lb": honey, "note": (note or "").strip()}
        if (override_reason or "").strip():
            entry["override"] = override_reason.strip()
        batch.setdefault("sweetenings", []).append(entry)
        batch["sweetenings"].sort(key=lambda x: x.get("at") or "")
        self.save_batch(batch)
        return batch, honey

    def record_priming(self, batch_id, target_vols, temp_f, sugar="honey",
                       at=None, note="", override_reason=None):
        """Prime for bottle-conditioning: the sugar that live yeast will turn
        into fizz. Refused on a stabilized mead — sorbate and sulfite kill the
        yeast, so it cannot carbonate — unless a reason is recorded (you
        re-pitched fresh champagne yeast)."""
        from . import calc
        batch = self.load_batch(batch_id)
        vols = calc.num(target_vols, "target volumes of CO2", 0.5, 6.0)
        temp = calc.num(temp_f, "temperature", 32, 100, " °F")
        if calc.is_stabilized(batch) and not (override_reason or "").strip():
            raise ValueError(
                "This mead is stabilized — the yeast is inhibited and cannot "
                "carbonate. Bottle-conditioning needs live yeast; record a "
                "reason if you re-pitched a fresh champagne strain")
        d = calc.priming_sugar(calc.current_volume(batch), vols, temp, sugar)
        entry = {"at": calc.fmt_when(calc.parse_when(at) if at
                                     else datetime.now()),
                 "target_vols": d["target_vols"], "temp_f": d["temp_f"],
                 "sugar": sugar, "grams": d["grams"], "co2_g": d["co2_g"],
                 "residual_vols": d["residual_vols"],
                 "tax_class": d["tax_class"], "note": (note or "").strip()}
        if (override_reason or "").strip():
            entry["override"] = override_reason.strip()
        batch.setdefault("primings", []).append(entry)
        batch["primings"].sort(key=lambda x: x.get("at") or "")
        self.save_batch(batch)
        return batch, d

    def record_bottling(self, batch_id, units, unit, at=None, note=""):
        """Bottle it: the terminal event. Units and the package they went in."""
        from . import calc
        batch = self.load_batch(batch_id)
        if calc.is_bottled(batch):
            raise ValueError(f"{batch_id} is already bottled")
        units = int(calc.num(units, "bottle count", 1, 100000))
        unit = (unit or "").strip() or "bottle"
        when = calc.parse_when(at) if at else datetime.now()
        pkg = {
            "at": calc.fmt_when(when), "units": units, "unit": unit,
            "volume_gal": calc.current_volume(batch),
            "note": (note or "").strip()}
        if calc.is_primed(batch):
            pr = batch["primings"][-1]
            pkg["conditioned"] = True
            pkg["target_vols"] = pr["target_vols"]
            pkg["tax_class"] = pr["tax_class"]
        else:
            pkg["tax_class"] = "still"
        batch["packaging"] = pkg
        self.save_batch(batch)
        return batch

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

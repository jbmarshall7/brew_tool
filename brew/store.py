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
from datetime import datetime, timedelta
from pathlib import Path

# how far ahead of the clock an event may be dated: a phone a little ahead of
# the laptop is fine; a pitch typed as 2062 is not
FUTURE_SLACK = timedelta(hours=12)


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "recipe"


class AlreadyRecorded(Exception):
    """The same form arrived twice — a double tap, or Back and resubmit. The
    first copy is already on file, so the second writes nothing; the server
    answers it by showing what was recorded (`where`)."""

    def __init__(self, where):
        super().__init__(where)
        self.where = where


class Store:
    def __init__(self, data_dir):
        self.data = Path(data_dir)
        self.recipes_dir = self.data / "recipes"
        self.batches_dir = self.data / "batches"
        self.recipes_dir.mkdir(parents=True, exist_ok=True)
        self.batches_dir.mkdir(parents=True, exist_ok=True)

    # --- the rules every event obeys -------------------------------------------
    @staticmethod
    def _replay(entries, once, where):
        """Every form carries a one-time token (`once`). If an entry already
        holds this one, this submission is a repeat: write nothing."""
        if once and any(e.get("once") == once for e in entries or []):
            raise AlreadyRecorded(where)

    @staticmethod
    def _stamp(entry, once):
        if once:
            entry["once"] = once
        return entry

    @staticmethod
    def _open(batch, what):
        """Bottling closes the cellar record: nothing more goes INTO a bottled
        batch. (Tastings and where the bottles went are still welcome.)"""
        from . import calc
        if calc.is_bottled(batch):
            raise ValueError(f"{batch['id']} is bottled — its cellar record is "
                             f"closed, so it can't take {what}. A tasting or "
                             "where the bottles went is still welcome.")

    @staticmethod
    def _when(batch, at, after=None, after_what=""):
        """The time an event happened: now, or the time typed — but never
        before the pitch (or `after`), and never in the future."""
        from . import calc
        when = calc.parse_when(at) if at else datetime.now()
        if when > datetime.now() + FUTURE_SLACK:
            raise ValueError(f"{calc.fmt_when(when).replace('T', ' ')} is in "
                             "the future — check the date")
        floors = [(batch.get("pitched_at"), "it was pitched"), (after, after_what)]
        for floor, label in floors:
            if floor and when < calc.parse_when(floor):
                raise ValueError(f"{calc.fmt_when(when).replace('T', ' ')} is "
                                 f"before {label} "
                                 f"({calc.parse_when(floor):%b %d, %Y})")
        return when

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
                    note="", at=None, once=None):
        """Append one gravity to a batch. The corrected value is stored
        alongside what the glass actually said, the way must day does it —
        everything else the ledger shows is derived on render."""
        from . import calc
        batch = self.load_batch(batch_id)
        self._replay(batch.get("readings"), once, f"/batches/{batch_id}")
        self._open(batch, "a reading")
        when = self._when(batch, at)
        reading = calc.num(reading, "hydrometer reading", 0.950, 1.250)
        cal = (calc.DEFAULT_CAL_F if calc.blank(cal_f)
               else calc.num(cal_f, "hydrometer calibration", 32, 110, " °F"))
        if calc.blank(sample_f):
            sample_f, corrected = None, reading
        else:
            sample_f = calc.num(sample_f, "sample temperature", 32, 140, " °F")
            corrected = calc.hydro_correct(reading, sample_f, cal)
        batch.setdefault("readings", []).append(self._stamp({
            "at": calc.fmt_when(when), "reading": reading,
            "sample_f": sample_f, "cal_f": cal, "sg": corrected,
            "note": (note or "").strip(),
        }, once))
        batch["readings"].sort(key=lambda r: r.get("at") or "")
        self.save_batch(batch)
        return batch, corrected

    def record_feed(self, batch_id, n, at=None, note="", once=None):
        """Record that a scheduled feeding was actually given.

        An event, not a status: append-only, like a reading, because whether
        the nutrient went in is the one thing about the schedule the app
        cannot derive. Nothing is ever un-ticked — a mistake is a note.
        """
        from . import calc
        batch = self.load_batch(batch_id)
        self._replay(batch.get("feeds"), once, f"/batches/{batch_id}")
        self._open(batch, "a feeding")
        when = self._when(batch, at)
        n = int(calc.num(n, "feeding number", 1, 99))
        planned = [a for a in (batch.get("nutrients") or {}).get("additions")
                   or [] if a.get("n") == n]
        if not planned:
            raise ValueError(f"{batch_id} has no feeding #{n}")
        if any(f.get("n") == n for f in batch.get("feeds") or []):
            raise ValueError(f"Feeding #{n} is already logged on {batch_id}")
        batch.setdefault("feeds", []).append(self._stamp({
            "n": n, "at": calc.fmt_when(when), "g": planned[0].get("g"),
            "note": (note or "").strip()}, once))
        batch["feeds"].sort(key=lambda f: f.get("n") or 0)
        self.save_batch(batch)
        return batch, planned[0]

    FLAVOR_KINDS = ("fruit", "spice", "oak", "other")

    def record_tasting(self, batch_id, stage, overall=None, note="", at=None,
                       once=None):
        """A tasting note at a checkpoint. A log, not a dose — no guardrails
        beyond its date, just a record the recipe can learn from. Welcome
        after bottling too: that is when most mead gets tasted."""
        from . import calc
        batch = self.load_batch(batch_id)
        self._replay(batch.get("tastings"), once, f"/batches/{batch_id}")
        when = self._when(batch, at)
        stage = (stage or "").strip().lower()
        if stage not in calc.TASTING_STAGES:
            raise ValueError(f"'{stage}' isn't one of "
                             f"{', '.join(calc.TASTING_STAGES)}")
        entry = self._stamp({"at": calc.fmt_when(when),
                             "stage": stage, "note": (note or "").strip()}, once)
        if not calc.blank(overall):
            entry["overall"] = int(calc.num(overall, "overall (1-5)", 1, 5))
        if not entry["note"] and "overall" not in entry:
            raise ValueError("a tasting needs a score or a note")
        batch.setdefault("tastings", []).append(entry)
        batch["tastings"].sort(key=lambda t: t.get("at") or "")
        self.save_batch(batch)
        return batch

    def record_flavor(self, batch_id, kind, item, qty=None, unit="",
                      at=None, note="", once=None):
        """Record a flavor addition — fruit, spice or oak going into the mead."""
        from . import calc
        batch = self.load_batch(batch_id)
        self._replay(batch.get("flavors"), once, f"/batches/{batch_id}")
        self._open(batch, "a flavor addition")
        when = self._when(batch, at)
        kind = (kind or "").strip().lower()
        if kind not in self.FLAVOR_KINDS:
            raise ValueError(f"'{kind}' isn't one of "
                             f"{', '.join(self.FLAVOR_KINDS)}")
        item = (item or "").strip()
        if not item:
            raise ValueError("give the fruit, spice or oak a name")
        entry = self._stamp({"at": calc.fmt_when(when), "kind": kind,
                             "item": item, "note": (note or "").strip()}, once)
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

    def record_racking(self, batch_id, volume_gal, at=None, note="", once=None):
        """Record racking off the lees: the measured volume now in the vessel.

        Every dose from here on is per this gallon, so it is measured, not
        computed. You cannot rack into more than you had.
        """
        from . import calc
        batch = self.load_batch(batch_id)
        self._replay(batch.get("rackings"), once, f"/batches/{batch_id}")
        self._open(batch, "a racking")
        when = self._when(batch, at)
        vol = calc.num(volume_gal, "volume", 0.05, 1000, " gal")
        have = calc.current_volume(batch)
        if have and vol > have + 0.05:
            raise ValueError(
                f"{calc.sg_text(vol) if False else vol} gal is more than the "
                f"{have} gal you had — racking loses a little, it does not add")
        batch.setdefault("rackings", []).append(self._stamp(
            {"at": calc.fmt_when(when), "volume_gal": round(vol, 2),
             "note": (note or "").strip()}, once))
        batch["rackings"].sort(key=lambda r: r.get("at") or "")
        self.save_batch(batch)
        return batch

    def record_stabilize(self, batch_id, ph, at=None, note="",
                         molecular=None, override_reason=None, once=None):
        """Stabilize: sorbate AND sulfite, dosed from pH and the volume now.

        Refused on a mead that is still working (sulfite will not stop it), on
        one already stabilized, and on a dose past the sulfite ceiling, unless
        a reason is recorded — and refused outright past the legal limit.
        Sorbate alone is never an option here — the two go in together.
        """
        from . import calc
        batch = self.load_batch(batch_id)
        self._replay(batch.get("stabilizations"), once, f"/batches/{batch_id}")
        self._open(batch, "a stabilizing dose")
        when = self._when(batch, at)
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
        problem = calc.sulfite_problem(d["free_so2_ppm"], ph)
        if problem and problem[0] == "refuse":
            raise ValueError(problem[1])
        if (problem and problem[0] == "reason"
                and not (override_reason or "").strip()):
            raise ValueError(problem[1] + " Record a reason to dose it anyway")
        entry = self._stamp({
            "at": calc.fmt_when(when), "ph": ph, "volume_gal": d["gallons"],
            "kmeta_g": d["kmeta_g"], "sorbate_g": d["sorbate_g"],
            "free_so2_ppm": d["free_so2_ppm"], "molecular": molecular,
            "note": (note or "").strip()}, once)
        if (override_reason or "").strip():
            entry["override"] = override_reason.strip()
        batch.setdefault("stabilizations", []).append(entry)
        batch["stabilizations"].sort(key=lambda x: x.get("at") or "")
        self.save_batch(batch)
        return batch, d

    def record_backsweeten(self, batch_id, to_sg, at=None, note="",
                           override_reason=None, once=None):
        """Back-sweeten to a target gravity: refused unless already stabilized
        (or a reason is recorded — a keg you will force-carbonate, say). The
        honey is computed from the gravity you are raising it from."""
        from . import calc
        batch = self.load_batch(batch_id)
        self._replay(batch.get("sweetenings"), once, f"/batches/{batch_id}")
        self._open(batch, "back-sweetening")
        when = self._when(batch, at)
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
        entry = self._stamp({"at": calc.fmt_when(when), "from_sg": from_sg,
                             "to_sg": to_sg, "honey_lb": honey,
                             "note": (note or "").strip()}, once)
        if (override_reason or "").strip():
            entry["override"] = override_reason.strip()
        batch.setdefault("sweetenings", []).append(entry)
        batch["sweetenings"].sort(key=lambda x: x.get("at") or "")
        self.save_batch(batch)
        return batch, honey

    def record_priming(self, batch_id, target_vols, temp_f, sugar="honey",
                       at=None, note="", override_reason=None, once=None):
        """Prime for bottle-conditioning: the sugar that live yeast will turn
        into fizz. Refused whenever calc.priming_refusal says it is not safe —
        not finished, not dry, sweetened, stabilized, or already primed —
        unless a reason is recorded (you re-pitched fresh champagne yeast)."""
        from . import calc
        batch = self.load_batch(batch_id)
        self._replay(batch.get("primings"), once, f"/batches/{batch_id}")
        self._open(batch, "priming sugar")
        when = self._when(batch, at)
        vols = calc.num(target_vols, "target volumes of CO2", 0.5, 6.0)
        temp = calc.num(temp_f, "temperature", 32, 100, " °F")
        refusal = calc.priming_refusal(batch)
        if refusal and not (override_reason or "").strip():
            raise ValueError(refusal + " Record a reason to override")
        d = calc.priming_sugar(calc.current_volume(batch), vols, temp, sugar)
        entry = self._stamp({
            "at": calc.fmt_when(when),
            "target_vols": d["target_vols"], "temp_f": d["temp_f"],
            "sugar": sugar, "grams": d["grams"], "co2_g": d["co2_g"],
            "residual_vols": d["residual_vols"],
            "tax_class": d["tax_class"], "note": (note or "").strip()}, once)
        if (override_reason or "").strip():
            entry["override"] = override_reason.strip()
        batch.setdefault("primings", []).append(entry)
        batch["primings"].sort(key=lambda x: x.get("at") or "")
        self.save_batch(batch)
        return batch, d

    def record_disposition(self, batch_id, kind, qty, to="", at=None, note="",
                           once=None):
        """Where some bottles went: a taproom pour, a sale, a gift, a sample,
        breakage. On-hand is derived from what was bottled less these; you
        cannot dispose of more than you made, nor before you made it.

        The one-time token matters most here: a double-tapped sale used to
        count twice, and taxable removals with it."""
        from . import calc
        batch = self.load_batch(batch_id)
        self._replay(batch.get("dispositions"), once, f"/batches/{batch_id}")
        if not calc.is_bottled(batch):
            raise ValueError("nothing to dispose of yet — this batch isn't "
                             "bottled")
        when = self._when(batch, at, after=batch["packaging"].get("at"),
                          after_what="it was bottled")
        kind = (kind or "").strip().lower()
        if kind not in calc.DISPO_KINDS:
            raise ValueError(f"'{kind}' isn't one of "
                             f"{', '.join(calc.DISPO_KINDS)}")
        qty = int(calc.num(qty, "how many", 1, 100000))
        on_hand = calc.units_on_hand(batch)
        if qty > on_hand:
            raise ValueError(f"only {on_hand} on hand — cannot move {qty}")
        batch.setdefault("dispositions", []).append(self._stamp(
            {"at": calc.fmt_when(when),
             "kind": kind, "qty": qty, "to": (to or "").strip(),
             "note": (note or "").strip()}, once))
        batch["dispositions"].sort(key=lambda d: d.get("at") or "")
        self.save_batch(batch)
        return batch

    def record_bottling(self, batch_id, units, unit, at=None, note="",
                        override_reason=None, once=None, abv_measured=None):
        """Bottle it: the terminal event. Units and the package they went in.

        Refused whenever calc.bottling_refusal says sealing it in glass now is
        dangerous — still fermenting, sweet with live yeast, sweetened and not
        stabilized — unless a reason is recorded (a keg kept cold, a
        pasteurized run)."""
        from . import calc
        batch = self.load_batch(batch_id)
        pk = batch.get("packaging")
        self._replay([pk] if pk else [], once, f"/batches/{batch_id}")
        if calc.is_bottled(batch):
            raise ValueError(f"{batch_id} is already bottled")
        when = self._when(batch, at)
        units = int(calc.num(units, "bottle count", 1, 100000))
        unit = (unit or "").strip() or "bottle"
        refusal = calc.bottling_refusal(batch)
        if refusal and not (override_reason or "").strip():
            raise ValueError(refusal + " Record a reason to override")
        pkg = self._stamp({
            "at": calc.fmt_when(when), "units": units, "unit": unit,
            "volume_gal": calc.current_volume(batch),
            "note": (note or "").strip()}, once)
        if refusal:
            pkg["override"] = override_reason.strip()
        if not calc.blank(abv_measured):
            # a lab (or ebulliometer) ABV: what the label and the tax class
            # follow, in place of the gravity estimate
            pkg["abv_measured"] = calc.num(abv_measured, "measured ABV", 0.5,
                                           24, " %")
        if calc.is_primed(batch):
            pr = batch["primings"][-1]
            pkg["conditioned"] = True
            pkg["target_vols"] = pr["target_vols"]
        # the class it was bottled as — sparkling, or still split at 16 / 21 %
        # by the fermented ABV (the TTB report re-derives it, and says so if
        # the estimate sits near a line)
        pkg["tax_class"] = calc.wine_tax_class(batch)[0]
        batch["packaging"] = pkg
        self.save_batch(batch)
        return batch

    def list_batches(self):
        out = self._read_all(self.batches_dir.glob("*.json"))
        return sorted(out, key=lambda b: (b.get("pitched_at") or "",
                                          b.get("id") or ""), reverse=True)

    # --- vessels: a flat list, occupancy derived from the batches ----------
    def vessels_path(self):
        return self.data / "vessels.json"

    def list_vessels(self):
        path = self.vessels_path()
        if not path.exists():
            return []
        doc = self.read_json(path)
        return doc.get("vessels", []) if isinstance(doc, dict) else []

    def add_vessel(self, name, gal=None, once=None):
        from . import calc
        name = (name or "").strip()
        if not name:
            raise ValueError("give the vessel a name")
        vessels = self.list_vessels()
        self._replay(vessels, once, "/vessels")
        if any(v.get("name", "").lower() == name.lower() for v in vessels):
            raise ValueError(f"there is already a vessel called {name}")
        vid = f"V-{max([int(v['id'].split('-')[1]) for v in vessels if v.get('id', '').startswith('V-') and v['id'].split('-')[1].isdigit()], default=0) + 1:03d}"
        v = {"id": vid, "name": name}
        if not calc.blank(gal):
            v["gal"] = calc.num(gal, "capacity", 0.1, 10000, " gal")
        vessels.append(self._stamp(v, once))
        self.write_json(self.vessels_path(), {"vessels": vessels})
        return v

    def set_batch_vessel(self, batch_id, vessel):
        batch = self.load_batch(batch_id)
        batch["vessel"] = (vessel or "").strip()
        self.save_batch(batch)
        return batch

    # --- compliance documents: a flat list, status derived on render ------
    def documents_path(self):
        return self.data / "documents.json"

    def list_documents(self):
        path = self.documents_path()
        if not path.exists():
            return []
        doc = self.read_json(path)
        return doc.get("documents", []) if isinstance(doc, dict) else []

    def add_document(self, label, expires, kind="", ref="", note="",
                     once=None):
        """Add a permit / licence / COA / policy with the date it lapses.

        Only the expiry date is required — days-left and status are derived.
        """
        from . import calc
        label = (label or "").strip()
        if not label:
            raise ValueError("give the document a name — 'TTB Basic Permit', "
                             "'CT Farm Winery Permit', 'Liability insurance'")
        expires = calc.parse_date(expires).isoformat()   # validate the date
        docs = self.list_documents()
        self._replay(docs, once, "/documents")
        did = f"D-{max([int(x['id'].split('-')[1]) for x in docs if x.get('id', '').startswith('D-') and x['id'].split('-')[1].isdigit()], default=0) + 1:03d}"
        d = {"id": did, "label": label, "expires": expires}
        if (kind or "").strip():
            d["kind"] = kind.strip()
        if (ref or "").strip():
            d["ref"] = ref.strip()
        if (note or "").strip():
            d["note"] = note.strip()
        docs.append(self._stamp(d, once))
        self.write_json(self.documents_path(), {"documents": docs})
        return d

    def renew_document(self, doc_id, expires):
        """Move a document's expiry forward — the recurring real event.

        A renewal replaces the date in place: the current expiry is the fact
        that matters, and git keeps the history of what it was before.
        """
        from . import calc
        expires = calc.parse_date(expires).isoformat()
        docs = self.list_documents()
        for d in docs:
            if d.get("id") == doc_id:
                d["expires"] = expires
                self.write_json(self.documents_path(), {"documents": docs})
                return d
        raise ValueError(f"there's no document {doc_id}")

    def write_report(self, name, text):
        """Save a generated report under data/reports/, return its path."""
        d = self.data / "reports"
        d.mkdir(parents=True, exist_ok=True)
        path = d / name
        path.write_text(text, encoding="utf-8")
        return path

    def batches_for_recipe(self, slug):
        return [b for b in self.list_batches()
                if (b.get("recipe") or {}).get("slug") == slug]

    def batch_ids(self):
        return [f.stem for f in self.batches_dir.glob("B-*.json")]

    def last_batch(self, slug=None):
        batches = self.batches_for_recipe(slug) if slug else self.list_batches()
        return batches[0] if batches else None

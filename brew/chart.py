"""The fermentation curve, drawn as plain inline SVG on the server.

No chart library, no script: the readings are already in hand when the page
renders, and a polyline is a string. The picture earns its place by showing
two things the ledger's numbers only imply — how the slope is flattening,
and where the 1/3 sugar break sits relative to where the gravity is now.
"""
from . import calc
from .html import esc

W, H = 620, 250
L, R, T, B = 44, 16, 14, 205        # plot box: axis sits at y=B
TICK_T, TICK_B, TICK_LABEL = 214, 226, 242
LINE = "#728157"                    # sage-600, the reading line
DOT = "#56633f"                     # sage-700, the reading marks
ACCENT = "#c67139"
MUTED = "#645c50"
GROUND = "#fff2eb"


def _hours(pitched, at):
    return (calc.parse_when(at) - calc.parse_when(pitched)).total_seconds() / 3600.0


def _domain(batch, rows):
    """Days across the bottom: the pitch to the last thing that happens.

    Always at least a week, so a batch with one reading is a point on a
    timeline rather than the whole chart.
    """
    pitched = batch["pitched_at"]
    days = [7.0]
    if rows:
        days.append(_hours(pitched, rows[-1]["at"]) / 24.0)
    for a in (batch.get("nutrients") or {}).get("additions") or []:
        try:
            days.append(_hours(pitched, a["due"]) / 24.0)
        except (ValueError, KeyError):
            continue
    return max(days)


def curve(batch):
    """The whole chart, or a plain sentence when there is nothing to draw."""
    og = (batch.get("measured") or {}).get("og")
    fg = (batch.get("target") or {}).get("fg") or 1.0
    rows = calc.ledger(og, batch.get("pitched_at"), batch.get("readings"))
    if not og or not rows:
        return ('<p class="mut">Nothing to draw yet — the curve starts at '
                "the first reading.</p>")
    span_days = _domain(batch, rows)
    lo = min([1.0, fg] + [r["sg"] for r in rows])
    hi = max([og] + [r["sg"] for r in rows])
    pad = (hi - lo) * 0.06 or 0.002
    lo, hi = lo - pad, hi + pad

    def x(day):
        return L + (day / span_days) * (W - L - R)

    def y(sg):
        return T + (hi - sg) / (hi - lo) * (B - T)

    parts = []
    # the gravities worth a line: where it started, the break, halfway, dry
    stop = (batch.get("nutrients") or {}).get("stop_sg") or calc.third_break(og, fg)
    for level in sorted({og, stop, round((og + fg) / 2, 4), fg}, reverse=True):
        if not lo <= level <= hi:
            continue
        yy = round(y(level), 1)
        parts.append(f'<line x1="{L}" y1="{yy}" x2="{W - R}" y2="{yy}" '
                     f'stroke="{MUTED}" stroke-opacity=".18" stroke-width="1"/>')
        parts.append(f'<text x="{L - 4}" y="{yy + 3.5}" text-anchor="end" '
                     f'font-size="10.5" fill="{MUTED}">'
                     f"{esc(calc.sg_text(level))}</text>")
    # the rule the whole nutrient schedule turns on
    if lo <= stop <= hi:
        ys = round(y(stop), 1)
        parts.append(f'<line x1="{L}" y1="{ys}" x2="{W - R}" y2="{ys}" '
                     f'stroke="{ACCENT}" stroke-width="1.5" '
                     'stroke-dasharray="5 4"/>')
        parts.append(f'<text x="{W - R}" y="{ys - 6}" text-anchor="end" '
                     f'font-size="10.5" fill="{ACCENT}">'
                     f"1/3 break · SG {esc(calc.sg_text(stop))}</text>")
    # the readings
    pitched = batch["pitched_at"]
    pts = [(x(_hours(pitched, r["at"]) / 24.0), y(r["sg"])) for r in rows]
    if len(pts) > 1:
        line = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
        parts.append(f'<polyline points="{line}" fill="none" stroke="{LINE}" '
                     'stroke-width="2.5" stroke-linecap="round" '
                     'stroke-linejoin="round"/>')
    for px, py in pts:
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="4" '
                     f'fill="{GROUND}" stroke="{DOT}" stroke-width="2"/>')
    # name the newest one, flipped inward when it sits near the left edge
    lx, ly = pts[-1]
    anchor, dx = ("start", 9) if lx < L + 120 else ("end", -9)
    parts.append(f'<text x="{lx + dx:.1f}" y="{ly - 9:.1f}" '
                 f'text-anchor="{anchor}" font-size="13" '
                 f'font-family="Caprasimo,Georgia,serif" fill="#201e1d">'
                 f"{esc(calc.sg_text(rows[-1]['sg']))}</text>")
    # the feedings, as marks under the axis
    given = calc.feeds_given(batch)
    for a in (batch.get("nutrients") or {}).get("additions") or []:
        try:
            fx = x(_hours(pitched, a["due"]) / 24.0)
        except (ValueError, KeyError):
            continue
        solid = a.get("n") in given
        parts.append(f'<line x1="{fx:.1f}" y1="{TICK_T}" x2="{fx:.1f}" '
                     f'y2="{TICK_B}" stroke="{ACCENT}" stroke-width="2" '
                     f'stroke-opacity="{"1" if solid else ".35"}"/>')
        parts.append(f'<text x="{fx:.1f}" y="{TICK_LABEL}" '
                     f'text-anchor="middle" font-size="10.5" fill="{MUTED}" '
                     f'fill-opacity="{"1" if solid else ".55"}">'
                     f"#{esc(a.get('n'))}</text>")
    parts.append(f'<line x1="{L}" y1="{B}" x2="{W - R}" y2="{B}" '
                 f'stroke="{MUTED}" stroke-opacity=".3" stroke-width="1"/>')
    parts.append(f'<text x="{L}" y="{TICK_LABEL}" font-size="10.5" '
                 f'fill="{MUTED}">day 0</text>')
    parts.append(f'<text x="{W - R}" y="{TICK_LABEL}" text-anchor="end" '
                 f'font-size="10.5" fill="{MUTED}">'
                 f"day {int(round(span_days))}</text>")
    return (f'<div class="tw"><svg class="curve" viewBox="0 0 {W} {H}" '
            f'width="100%" role="img" aria-label="Gravity against days since '
            f'the pitch">{"".join(parts)}</svg></div>'
            '<p class="mut">Solid marks under the axis are feedings you '
            "logged; faint ones are still owed.</p>")


def sparkline(batch, w=86, h=26):
    """The same readings at thumbnail size, for a row in a list."""
    og = (batch.get("measured") or {}).get("og")
    rows = calc.ledger(og, batch.get("pitched_at"), batch.get("readings"))
    if len(rows) < 2:
        return ""
    vals = [r["sg"] for r in rows]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    step = (w - 4) / (len(vals) - 1)
    pts = " ".join(
        f"{2 + i * step:.1f},{2 + (hi - v) / span * (h - 4):.1f}"
        for i, v in enumerate(vals))
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="the last {len(vals)} readings">'
            f'<polyline points="{pts}" fill="none" stroke="{LINE}" '
            'stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round"/></svg>')

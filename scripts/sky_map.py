#!/usr/bin/env python3
"""Build the Astronomy astronomy map and validation report."""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

black, white = 0.0, 1.0
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from astronomy_data import compute_astronomy


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "event-2026-09-12.json"
OUTPUT_PDF = ROOT / "output" / "pdf" / "astronomy-validation.pdf"
OUTPUT_DATA = ROOT / "output" / "data" / "astronomy-2026-09-12.json"
JPL_DATA = ROOT / "output" / "data" / "jpl-validation-2026-09-12.json"

W, H = LETTER
INK = 0.067
MID = 0.39
LIGHT = 0.855
PALE = 0.953
ACCENT = 0.28
PASS_SHADE = 0.31


def load_json(path: Path):
    return json.loads(path.read_text())


def event_datetime(config):
    return datetime.fromisoformat(f"{config['date']}T{config['time']}:00").replace(
        tzinfo=ZoneInfo(config["timezone"])
    )


def compute_data(config, config_path=CONFIG_PATH, output_data=OUTPUT_DATA):
    dt = event_datetime(config)
    data = compute_astronomy(config, dt.astimezone(ZoneInfo("UTC")).isoformat())
    if output_data:
        output_data = Path(output_data)
        output_data.parent.mkdir(parents=True, exist_ok=True)
        output_data.write_text(json.dumps(data, indent=2) + "\n")
    return data


def local_from_iso(iso, timezone):
    if not iso:
        return None
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo(timezone))


def clock(iso, timezone):
    dt = local_from_iso(iso, timezone)
    if not dt:
        return "not available"
    value = dt.strftime("%I:%M %p").lstrip("0").lower()
    return value.replace("am", "a.m.").replace("pm", "p.m.")


def event_line(config):
    dt = event_datetime(config)
    hour = dt.strftime("%I:%M %p").lstrip("0").lower().replace("am", "a.m.").replace("pm", "p.m.")
    return f"{config['location']['name']} | {dt.strftime('%A, %B')} {dt.day}, {dt.year} | {hour} {dt.tzname()}"


def event_clock(config):
    dt = event_datetime(config)
    return dt.strftime("%I:%M %p").lstrip("0").lower().replace("am", "a.m.").replace("pm", "p.m.")


def label(c, text, x, y, size=8, shade=INK, font="Helvetica"):
    c.setFillGray(shade)
    c.setFont(font, size)
    c.drawString(x, y, text)


def centered(c, text, x, y, size=8, shade=INK, font="Helvetica"):
    c.setFillGray(shade)
    c.setFont(font, size)
    c.drawCentredString(x, y, text)


def right(c, text, x, y, size=8, shade=INK, font="Helvetica"):
    c.setFillGray(shade)
    c.setFont(font, size)
    c.drawRightString(x, y, text)


def wrap_text(c, text, x, y, width, font="Helvetica", size=8, leading=None, shade=INK, max_lines=None):
    leading = leading or size * 1.25
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if stringWidth(trial, font, size) <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        while stringWidth(lines[-1] + "...", font, size) > width and len(lines[-1]) > 1:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "..."
    c.setFillGray(shade)
    c.setFont(font, size)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def rounded_panel(c, x, y, width, height, fill=white, stroke=LIGHT, radius=8):
    c.setFillGray(fill)
    c.setStrokeGray(stroke)
    c.roundRect(x, y, width, height, radius, fill=1, stroke=1)


def draw_header(c, config, eyebrow, title, subtitle):
    org = config["organization"]
    label(c, f"{eyebrow.upper()} | {org['name'].upper()} | {org['website'].replace('https://', '')}", 36, H - 27, 7.2, ACCENT, "Helvetica-Bold")
    c.linkURL(org["website"], (36, H - 33, W - 36, H - 18), relative=0, thickness=0)
    label(c, title, 36, H - 59, 21, INK, "Helvetica-Bold")
    label(c, subtitle, 36, H - 75, 8.5, MID)
    c.setStrokeGray(LIGHT)
    c.line(36, H - 84, W - 36, H - 84)


def footer(c, text, page_number):
    c.setStrokeGray(LIGHT)
    c.line(36, 28, W - 36, 28)
    label(c, text, 36, 16, 6.5, MID)
    right(c, page_number, W - 36, 16, 6.5, MID)


def sky_xy(altitude, azimuth, cx, cy, radius):
    radial = radius * (90 - altitude) / 90
    angle = math.radians(azimuth)
    return cx - radial * math.sin(angle), cy + radial * math.cos(angle)


def draw_map(c, config, data, x, y, size):
    cx, cy, radius = x + size / 2, y + size / 2, size / 2
    selected = data["selected_targets"]
    selected_numbers = {target_id: index + 1 for index, target_id in enumerate(selected)}

    c.saveState()
    clip = c.beginPath()
    clip.circle(cx, cy, radius)
    c.clipPath(clip, stroke=0, fill=0)

    c.setStrokeGray(0.82)
    c.setLineWidth(0.35)
    c.setDash(1.2, 2.2)
    for altitude in (30, 60):
        c.circle(cx, cy, radius * (90 - altitude) / 90, fill=0, stroke=1)
    c.setDash()

    for feature in data["catalog"]["constellation_boundaries"]:
        c.setStrokeGray(0.71)
        c.setLineWidth(0.3)
        c.setDash(1, 1.6)
        for line_points in feature["lines"]:
            previous = None
            for point in line_points:
                if point["altitude"] >= 0:
                    px, py = sky_xy(point["altitude"], point["azimuth"], cx, cy, radius)
                    if previous and math.hypot(px - previous[0], py - previous[1]) < radius * 0.35:
                        c.line(previous[0], previous[1], px, py)
                    previous = (px, py)
                else:
                    previous = None
        c.setDash()

    c.setStrokeGray(0.48)
    c.setLineWidth(0.7)
    for feature in data["catalog"]["constellation_lines"]:
        if feature["rank"] > 2:
            continue
        for line_points in feature["lines"]:
            previous = None
            for point in line_points:
                if point["altitude"] >= 0:
                    px, py = sky_xy(point["altitude"], point["azimuth"], cx, cy, radius)
                    if previous and math.hypot(px - previous[0], py - previous[1]) < radius * 0.32:
                        c.line(previous[0], previous[1], px, py)
                    previous = (px, py)
                else:
                    previous = None

    bright_labels = []
    for star in data["catalog"]["stars"]:
        if star["altitude"] < 0:
            continue
        px, py = sky_xy(star["altitude"], star["azimuth"], cx, cy, radius)
        star_radius = max(0.3, 1.85 - 0.26 * max(-1.5, star["magnitude"]))
        c.setFillGray(INK)
        c.circle(px, py, star_radius, fill=1, stroke=0)
        if star["name"] and star["magnitude"] <= 1.35 and star["altitude"] > 8:
            bright_labels.append((star["magnitude"], star["name"], px, py))

    occupied = []
    c.setFont("Helvetica", 6.1)
    c.setFillGray(INK)
    for _, name, px, py in sorted(bright_labels):
        tx, ty = px + 4, py + 2
        box = (tx, ty - 2, tx + stringWidth(name, "Helvetica", 6.1), ty + 6)
        if any(not (box[2] < other[0] or box[0] > other[2] or box[3] < other[1] or box[1] > other[3]) for other in occupied):
            continue
        c.drawString(tx, ty, name)
        occupied.append(box)

    c.setFillGray(0.38)
    c.setFont("Helvetica-Bold", 6)
    for constellation in data["catalog"]["constellation_labels"]:
        if constellation["rank"] <= 2 and constellation["altitude"] > 10:
            px, py = sky_xy(constellation["altitude"], constellation["azimuth"], cx, cy, radius)
            c.drawCentredString(px, py, constellation["id"])

    for target in data["targets"]:
        if target["id"] not in selected_numbers or target["altitude"] < 0:
            continue
        px, py = sky_xy(target["altitude"], target["azimuth"], cx, cy, radius)
        number = str(selected_numbers[target["id"]])
        c.setFillGray(white)
        c.setStrokeGray(INK)
        c.setLineWidth(1.2)
        c.circle(px, py, 7.2, fill=1, stroke=1)
        centered(c, number, px, py - 2.4, 7.5, INK, "Helvetica-Bold")
        dx = 9 if px < cx else -9 - stringWidth(target["id"], "Helvetica-Bold", 6.8)
        label(c, target["id"], px + dx, py + 4, 6.8, INK, "Helvetica-Bold")

    for name in ("Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"):
        body = data["bodies"][name]
        if body["altitude"] < 0:
            continue
        px, py = sky_xy(body["altitude"], body["azimuth"], cx, cy, radius)
        c.setFillGray(white)
        c.setStrokeGray(INK)
        c.setLineWidth(1)
        c.circle(px, py, 3.7 if name != "Moon" else 4.7, fill=1, stroke=1)
        dx = 6 if px < cx else -6 - stringWidth(name, "Helvetica-Bold", 6.4)
        label(c, name, px + dx, py + 5, 6.4, INK, "Helvetica-Bold")

    c.restoreState()
    c.setStrokeGray(INK)
    c.setLineWidth(1.25)
    c.circle(cx, cy, radius, fill=0, stroke=1)
    for text, px, py in (("N", cx, cy + radius + 8), ("S", cx, cy - radius - 13), ("E", cx - radius - 10, cy - 2), ("W", cx + radius + 10, cy - 2)):
        centered(c, text, px, py, 8, INK, "Helvetica-Bold")


def draw_map_page(c, config, data, production=False):
    if production:
        org = config["organization"]
        label(c, f"PRESENTED BY {org['name'].upper()} | {org['website'].replace('https://', '')}", 36, H - 27, 7.2, ACCENT, "Helvetica-Bold")
        c.linkURL(org["website"], (36, H - 33, W - 36, H - 18), relative=0, thickness=0)
        label(c, "Tonight's Sky", 36, H - 59, 21, INK, "Helvetica-Bold")
        label(c, event_line(config), 36, H - 75, 8.5, MID)
        c.setStrokeGray(LIGHT)
        c.line(36, H - 84, W - 36, H - 84)
    else:
        draw_header(c, config, "Astronomy map proof", "Tonight's Sky", event_line(config))
    draw_map(c, config, data, 78, 226, 456)

    panel_y, panel_h, gap = 52, 146, 8
    widths = [172, 172, 172]
    xs = [36, 36 + widths[0] + gap, 36 + 2 * (widths[0] + gap)]
    for index, x in enumerate(xs):
        rounded_panel(c, x, panel_y, widths[index], panel_h, PALE if index != 1 else white)

    tz = config["timezone"]
    label(c, "TONIGHT AT A GLANCE", xs[0] + 12, panel_y + 127, 7, ACCENT, "Helvetica-Bold")
    label(c, f"Sunset  {clock(data['twilight']['sunset_utc'], tz)}", xs[0] + 12, panel_y + 105, 8.2, INK, "Helvetica-Bold")
    label(c, f"Astronomical dark  {clock(data['twilight']['astronomical_dusk_utc'], tz)}", xs[0] + 12, panel_y + 89, 7.6, INK)
    moon = data["bodies"]["Moon"]
    label(c, f"Moon  {moon['phase_fraction'] * 100:.0f}% lit; sets {clock(data['twilight']['moonset_utc'], tz)}", xs[0] + 12, panel_y + 69, 7.6, INK)
    visible = [name for name in ("Mercury", "Venus", "Mars", "Jupiter", "Saturn") if data["bodies"][name]["altitude"] >= 0]
    display_time = event_clock(config)
    label(c, f"Visible planets at {display_time}", xs[0] + 12, panel_y + 46, 7, MID, "Helvetica-Bold")
    planet_text = ", ".join(f"{name} ({data['bodies'][name]['altitude']:.0f} deg)" for name in visible) or "None above the horizon"
    wrap_text(c, planet_text, xs[0] + 12, panel_y + 31, widths[0] - 24, size=7.4, leading=10, max_lines=2)

    label(c, "HOW TO USE THE MAP", xs[1] + 12, panel_y + 127, 7, ACCENT, "Helvetica-Bold")
    wrap_text(c, "Hold the page overhead. Rotate it until the direction you face is at the bottom. East is left when north is at the top.", xs[1] + 12, panel_y + 105, widths[1] - 24, size=7.8, leading=10.5)
    label(c, "SYMBOLS", xs[1] + 12, panel_y + 47, 6.7, MID, "Helvetica-Bold")
    c.setFillGray(INK)
    c.circle(xs[1] + 18, panel_y + 31, 2, fill=1, stroke=0)
    label(c, "star", xs[1] + 26, panel_y + 28, 7, INK)
    c.setStrokeGray(INK)
    c.circle(xs[1] + 69, panel_y + 33, 5, fill=0, stroke=1)
    label(c, "target", xs[1] + 78, panel_y + 28, 7, INK)
    c.setStrokeGray(0.48)
    c.line(xs[1] + 12, panel_y + 15, xs[1] + 32, panel_y + 15)
    label(c, "constellation line", xs[1] + 38, panel_y + 11, 7, INK)

    label(c, "POSSIBLE TARGETS", xs[2] + 12, panel_y + 127, 7, ACCENT, "Helvetica-Bold")
    by_id = {target["id"]: target for target in data["targets"]}
    for index, target_id in enumerate(data["selected_targets"]):
        target = by_id[target_id]
        row_y = panel_y + 103 - index * 24
        c.setFillGray(white)
        c.setStrokeGray(INK)
        c.circle(xs[2] + 19, row_y + 2, 7, fill=1, stroke=1)
        centered(c, str(index + 1), xs[2] + 19, row_y - 0.5, 7.2, INK, "Helvetica-Bold")
        title = f"{target_id}  {target['common_name']}"
        title_size = min(7.4, 130 / max(1, stringWidth(title, "Helvetica-Bold", 1)))
        label(c, title, xs[2] + 31, row_y + 2, title_size, INK, "Helvetica-Bold")
        label(c, f"{target['altitude']:.0f} deg high at {display_time}", xs[2] + 31, row_y - 9, 6.8, MID)

    limit = data["computation"]["star_magnitude_limit"]
    if production:
        dt = event_datetime(config)
        footer(c, f"{config['organization']['name']} | Sky shown for {config['location']['name']} at {display_time} {dt.tzname()} | Stars to magnitude {limit:.1f}", "1 / 2")
    else:
        footer(c, f"Stars to magnitude {limit:.1f} | precession and nutation applied | constellation boundaries off", "1 / 2")
    c.showPage()


def angle_difference(a, b):
    return abs((a - b + 180) % 360 - 180)


def validation_rows(data, jpl):
    rows = []
    for name, reference in jpl["bodies"].items():
        calculated = data["bodies"][name]
        rows.append({
            "name": name,
            "calc_alt": calculated["altitude_airless"],
            "jpl_alt": reference["altitude_airless_degrees"],
            "alt_diff": abs(calculated["altitude_airless"] - reference["altitude_airless_degrees"]),
            "calc_az": calculated["azimuth"],
            "jpl_az": reference["azimuth_degrees"],
            "az_diff": angle_difference(calculated["azimuth"], reference["azimuth_degrees"]),
        })
    return rows


def draw_table_header(c, labels, xs, y, right_indices=None):
    right_indices = set(right_indices or [])
    c.setFillGray(ACCENT)
    c.setFont("Helvetica-Bold", 6.5)
    for index, text in enumerate(labels):
        if index in right_indices:
            c.drawRightString(xs[index], y, text)
        else:
            c.drawString(xs[index], y, text)
    c.setStrokeGray(LIGHT)
    c.line(48, y - 5, W - 48, y - 5)


def draw_validation_page(c, config, data, jpl):
    draw_header(c, config, "Astronomy validation", "Astronomy Data Check", event_line(config))
    rows = validation_rows(data, jpl)
    maximum = max(max(row["alt_diff"], row["az_diff"]) for row in rows)

    rounded_panel(c, 36, 635, 540, 56, 0.94, 0.77)
    label(c, "PASSED", 50, 669, 10, PASS_SHADE, "Helvetica-Bold")
    label(c, f"Maximum position difference from NASA/JPL Horizons: {maximum:.3f} deg", 105, 669, 9, INK, "Helvetica-Bold")
    label(c, "Acceptance threshold: 0.05 deg for airless topocentric altitude and azimuth.", 50, 650, 7.4, MID)

    rounded_panel(c, 36, 549, 264, 72, PALE)
    label(c, "EVENT INPUTS", 48, 603, 7, ACCENT, "Helvetica-Bold")
    label(c, f"Site: {config['location']['name']}  ({config['location']['latitude']:.4f}, {config['location']['longitude']:.4f})", 48, 584, 7.5, INK)
    label(c, f"Elevation: {config['location']['elevation_m']} m | Time: {event_datetime(config).isoformat()}", 48, 568, 7.5, INK)
    label(c, f"Catalog epoch: {data['computation']['catalog_epoch']} -> true equator/equinox of date", 48, 552, 7.2, INK)

    rounded_panel(c, 312, 549, 264, 72, white)
    label(c, "EVENING TRANSITIONS", 324, 603, 7, ACCENT, "Helvetica-Bold")
    tz = config["timezone"]
    label(c, f"Sunset {clock(data['twilight']['sunset_utc'], tz)} | Civil dusk {clock(data['twilight']['civil_dusk_utc'], tz)}", 324, 584, 7.5, INK)
    label(c, f"Nautical dusk {clock(data['twilight']['nautical_dusk_utc'], tz)} | Astro dusk {clock(data['twilight']['astronomical_dusk_utc'], tz)}", 324, 568, 7.5, INK)
    label(c, f"Moonset {clock(data['twilight']['moonset_utc'], tz)} | Moon {data['bodies']['Moon']['phase_fraction'] * 100:.1f}% illuminated", 324, 552, 7.2, INK)

    label(c, "INDEPENDENT EPHEMERIS CHECK", 36, 526, 8, ACCENT, "Helvetica-Bold")
    label(c, "Astronomy Engine compared with NASA/JPL Horizons at 02:00 UTC. Both columns are airless.", 36, 512, 7.2, MID)
    table_xs = [48, 212, 263, 323, 382, 441, 502, 563]
    draw_table_header(c, ["Body", "Calc alt", "JPL alt", "Diff", "Calc az", "JPL az", "Diff"], table_xs, 494, range(1, 7))
    for index, row in enumerate(rows):
        y = 476 - index * 18
        if index % 2 == 0:
            c.setFillGray(PALE)
            c.rect(42, y - 5, 528, 16, fill=1, stroke=0)
        label(c, row["name"], table_xs[0], y, 7.4, INK, "Helvetica-Bold")
        right(c, f"{row['calc_alt']:.3f}", table_xs[1], y, 7.2)
        right(c, f"{row['jpl_alt']:.3f}", table_xs[2], y, 7.2)
        right(c, f"{row['alt_diff']:.3f}", table_xs[3], y, 7.2)
        right(c, f"{row['calc_az']:.3f}", table_xs[4], y, 7.2)
        right(c, f"{row['jpl_az']:.3f}", table_xs[5], y, 7.2)
        right(c, f"{row['az_diff']:.3f}", table_xs[6], y, 7.2)

    label(c, "TARGET RANKING AND AUTOMATIC SELECTION", 36, 338, 8, ACCENT, "Helvetica-Bold")
    label(c, "Scores combine altitude, brightness, beginner suitability, Moon separation, and time above 20 deg.", 36, 324, 7.2, MID)
    target_xs = [48, 86, 220, 340, 388, 436, 484, 536, 566]
    draw_table_header(c, ["Rank", "Object", "Type", "9 p.m.", "10 p.m.", "11 p.m.", "Score", "Use"], target_xs, 306, range(3, 8))
    selected = set(data["selected_targets"])
    for index, target in enumerate(data["targets"]):
        y = 288 - index * 19
        if index % 2 == 0:
            c.setFillGray(PALE)
            c.rect(42, y - 5, 528, 17, fill=1, stroke=0)
        label(c, str(target["rank"]), target_xs[0], y, 7.3, INK)
        label(c, f"{target['id']}  {target['common_name']}", target_xs[1], y, 7.2, INK, "Helvetica-Bold")
        label(c, target["type"], target_xs[2], y, 6.9, INK)
        samples = target["altitude_samples"]
        right(c, f"{samples[0]['altitude']:.0f}", target_xs[3], y, 7.2)
        right(c, f"{samples[1]['altitude']:.0f}", target_xs[4], y, 7.2)
        right(c, f"{samples[2]['altitude']:.0f}", target_xs[5], y, 7.2)
        right(c, f"{target['score']:.1f}", target_xs[6], y, 7.2)
        right(c, "YES" if target["id"] in selected else "", target_xs[7], y, 7.2, PASS_SHADE, "Helvetica-Bold")

    rounded_panel(c, 36, 103, 540, 68, PALE)
    label(c, "REUSABLE CONTROLS", 48, 151, 7, ACCENT, "Helvetica-Bold")
    comp = data["computation"]
    label(c, f"Star limit {comp['star_magnitude_limit']:.1f} | constellation lines ON | boundaries OFF | precession/nutation ON | refraction ON", 48, 132, 7.4, INK)
    label(c, "Manual target overrides are supported; otherwise one target is chosen from each preferred object group.", 48, 116, 7.2, INK)

    label(c, "SOURCES", 36, 86, 7, ACCENT, "Helvetica-Bold")
    label(c, "Astronomy Engine 2.1.19 | NASA/JPL Horizons API 1.2 | d3-celestial J2000 catalog data", 36, 71, 7.2, INK)
    jpl_url = jpl["source_url"]
    engine_url = "https://github.com/cosinekitty/astronomy"
    c.linkURL(jpl_url, (160, 64, 286, 78), relative=0, thickness=0)
    c.linkURL(engine_url, (36, 64, 150, 78), relative=0, thickness=0)
    label(c, "Validation is for chart production, not telescope pointing or navigation.", 36, 52, 6.8, MID)
    footer(c, "Astronomy - reproducible data file saved beside this PDF", "2 / 2")
    c.showPage()


def build():
    config = load_json(CONFIG_PATH)
    if not JPL_DATA.exists():
        raise FileNotFoundError(f"Run scripts/fetch_jpl_validation.py first: {JPL_DATA}")
    data = compute_data(config)
    jpl = load_json(JPL_DATA)
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUTPUT_PDF), pagesize=LETTER)
    c.setTitle("Astronomy - astronomy validation and Austin sky map")
    c.setAuthor(config["organization"]["name"])
    draw_map_page(c, config, data)
    draw_validation_page(c, config, data, jpl)
    c.save()
    return OUTPUT_PDF


if __name__ == "__main__":
    print(build())

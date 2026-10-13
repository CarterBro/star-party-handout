#!/usr/bin/env python3
"""Create original eyepiece sketches and the Eyepiece reverse-side proof."""

from __future__ import annotations

import json
import hashlib
import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
white = 1.0
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from sky_map import ACCENT, H, INK, LIGHT, MID, PALE, W, footer, label, rounded_panel, wrap_text


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "event-2026-09-12.json"
TARGET_PATH = ROOT / "data" / "targets.json"
OUTPUT_PDF = ROOT / "output" / "pdf" / "eyepiece-side-proof.pdf"
SOURCE_DIR = ROOT / "assets" / "generated" / "sketches" / "source"
EYEPIECE_DIR = ROOT / "assets" / "generated" / "sketches" / "eyepiece"
SKETCH_MANIFEST = ROOT / "assets" / "generated" / "sketches" / "manifest.json"
SKETCH_GENERATOR_VERSION = 1

IMAGE_SIZE = 1000
CENTER = IMAGE_SIZE // 2
FIELD_RADIUS = 470


def load_json(path):
    return json.loads(path.read_text())


def inside_field(x, y, margin=0):
    return (x - CENTER) ** 2 + (y - CENTER) ** 2 <= (FIELD_RADIUS - margin) ** 2


def add_star(draw, x, y, brightness=0, radius=3):
    if not inside_field(x, y, radius + 2):
        return
    shade = int(max(0, min(150, brightness)))
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=shade)
    if radius >= 5:
        draw.line((x - radius * 1.8, y, x + radius * 1.8, y), fill=min(185, shade + 35), width=1)
        draw.line((x, y - radius * 1.8, x, y + radius * 1.8), fill=min(185, shade + 35), width=1)


def add_field_stars(draw, rng, count, excluded_radius=0, bright_count=3):
    placed = 0
    while placed < count:
        angle = rng.random() * 2 * math.pi
        radius = FIELD_RADIUS * math.sqrt(rng.random())
        x = CENTER + radius * math.cos(angle)
        y = CENTER + radius * math.sin(angle)
        if math.hypot(x - CENTER, y - CENTER) < excluded_radius:
            continue
        star_radius = rng.choice([2, 2, 3, 3, 4])
        if placed < bright_count:
            star_radius = rng.choice([5, 6])
        add_star(draw, x, y, rng.randint(5, 45), star_radius)
        placed += 1


def radial_glow(size, center, radius, darkest, exponent=1.6):
    glow = Image.new("L", (size, size), 255)
    pixels = glow.load()
    cx, cy = center
    for y in range(max(0, int(cy - radius)), min(size, int(cy + radius + 1))):
        for x in range(max(0, int(cx - radius)), min(size, int(cx + radius + 1))):
            distance = math.hypot(x - cx, y - cy) / radius
            if distance <= 1:
                value = darkest + (255 - darkest) * (distance ** exponent)
                pixels[x, y] = int(value)
    return glow.filter(ImageFilter.GaussianBlur(radius * 0.05))


def paper_m13(rng):
    image = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), 255)
    image = ImageChops.darker(image, radial_glow(IMAGE_SIZE, (CENTER, CENTER), 165, 120, 1.4))
    draw = ImageDraw.Draw(image)
    add_field_stars(draw, rng, 32, excluded_radius=205, bright_count=2)
    for index in range(170):
        radius = min(215, rng.expovariate(1 / 66))
        angle = rng.random() * 2 * math.pi
        x = CENTER + radius * math.cos(angle) * (1 + 0.05 * rng.random())
        y = CENTER + radius * math.sin(angle)
        size = 2 if radius < 75 else rng.choice([2, 3, 4])
        shade = rng.randint(0, 36) if radius > 70 else rng.randint(25, 80)
        add_star(draw, x, y, shade, size)
    return image


def paper_m11(rng):
    image = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), 255)
    draw = ImageDraw.Draw(image)
    add_field_stars(draw, rng, 43, excluded_radius=220, bright_count=4)
    for index in range(135):
        radius = min(245, rng.expovariate(1 / 95))
        angle = rng.random() * 2 * math.pi
        fan = 0.62 + 0.38 * (1 + math.sin(angle + 0.7)) / 2
        x = CENTER + radius * math.cos(angle) * fan
        y = CENTER + radius * math.sin(angle) * (0.78 + 0.18 * rng.random())
        add_star(draw, x, y, rng.randint(0, 45), rng.choice([2, 2, 3, 3, 4]))
    add_star(draw, CENTER + 148, CENTER + 118, 0, 7)
    return image


def paper_m27(rng):
    image = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), 255)
    draw = ImageDraw.Draw(image)
    add_field_stars(draw, rng, 25, excluded_radius=125, bright_count=4)
    nebula = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), 255)
    ndraw = ImageDraw.Draw(nebula)
    for radius, shade in ((108, 218), (84, 195), (60, 172)):
        ndraw.ellipse((CENTER - radius - 45, CENTER - radius * 0.62, CENTER + radius - 45, CENTER + radius * 0.62), fill=shade)
        ndraw.ellipse((CENTER - radius + 45, CENTER - radius * 0.62, CENTER + radius + 45, CENTER + radius * 0.62), fill=shade)
    ndraw.ellipse((CENTER - 52, CENTER - 75, CENTER + 52, CENTER + 75), fill=228)
    nebula = nebula.rotate(26, resample=Image.Resampling.BICUBIC, center=(CENTER, CENTER))
    nebula = nebula.filter(ImageFilter.GaussianBlur(24))
    image = ImageChops.darker(image, nebula)
    return image


def paper_m31(rng):
    image = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), 255)
    draw = ImageDraw.Draw(image)
    add_field_stars(draw, rng, 38, excluded_radius=150, bright_count=4)
    galaxy = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), 255)
    gdraw = ImageDraw.Draw(galaxy)
    for width, height, shade in ((520, 105, 232), (390, 82, 215), (245, 60, 188), (95, 42, 105), (32, 27, 35)):
        gdraw.ellipse((CENTER - width / 2, CENTER - height / 2, CENTER + width / 2, CENTER + height / 2), fill=shade)
    galaxy = galaxy.rotate(-23, resample=Image.Resampling.BICUBIC, center=(CENTER, CENTER))
    galaxy = galaxy.filter(ImageFilter.GaussianBlur(18))
    image = ImageChops.darker(image, galaxy)
    return image


def paper_m8(rng):
    image = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), 255)
    nebula = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), 255)
    ndraw = ImageDraw.Draw(nebula)
    ndraw.ellipse((285, 365, 705, 610), fill=220)
    ndraw.ellipse((405, 315, 745, 545), fill=205)
    ndraw.ellipse((250, 445, 545, 675), fill=228)
    ndraw.line((360, 320, 565, 690), fill=247, width=58)
    nebula = nebula.rotate(-12, resample=Image.Resampling.BICUBIC, center=(CENTER, CENTER))
    nebula = nebula.filter(ImageFilter.GaussianBlur(30))
    image = ImageChops.darker(image, nebula)
    draw = ImageDraw.Draw(image)
    add_field_stars(draw, rng, 45, excluded_radius=0, bright_count=5)
    for _ in range(34):
        angle = rng.random() * 2 * math.pi
        radius = 100 * math.sqrt(rng.random())
        add_star(draw, CENTER - 105 + radius * math.cos(angle), CENTER + 55 + radius * math.sin(angle), rng.randint(0, 35), rng.choice([2, 3, 4]))
    return image


def paper_m57(rng):
    image = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), 255)
    draw = ImageDraw.Draw(image)
    add_field_stars(draw, rng, 28, excluded_radius=95, bright_count=4)
    ring = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), 255)
    rdraw = ImageDraw.Draw(ring)
    rdraw.ellipse((CENTER - 74, CENTER - 56, CENTER + 74, CENTER + 56), fill=165)
    rdraw.ellipse((CENTER - 39, CENTER - 27, CENTER + 39, CENTER + 27), fill=238)
    ring = ring.rotate(18, resample=Image.Resampling.BICUBIC, center=(CENTER, CENTER))
    ring = ring.filter(ImageFilter.GaussianBlur(9))
    return ImageChops.darker(image, ring)


def paper_open(rng, style="rich", paired=False):
    image = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), 255)
    draw = ImageDraw.Draw(image)
    add_field_stars(draw, rng, 22, bright_count=2)
    centers = [(330, 420), (650, 590)] if paired else [(500, 500)]
    count = {"rich": 100, "cross": 75, "chains": 85, "wide": 48}[style]
    for cx, cy in centers:
        for i in range(count):
            angle = rng.random() * math.tau
            radius = (140 if paired else 310) * math.sqrt(rng.random())
            if style == "cross":
                angle = (i % 4) * math.pi / 2 + rng.uniform(-0.3, 0.3)
            if style == "chains":
                angle = i * 0.29
            add_star(draw, cx + radius * math.cos(angle), cy + radius * math.sin(angle), rng.randint(0, 65), rng.choice([2, 3, 4, 5]))
    return image


def paper_globular(rng, compact=False):
    image = paper_m13(rng)
    if compact:
        image = ImageChops.darker(image, radial_glow(IMAGE_SIZE, (500, 500), 70, 35, 1.3))
    return image


def paper_planetary(rng, central=False):
    image = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), 255)
    image = ImageChops.darker(image, radial_glow(IMAGE_SIZE, (500, 500), 65, 120, 0.7))
    draw = ImageDraw.Draw(image)
    add_field_stars(draw, rng, 25, excluded_radius=100, bright_count=3)
    if central:
        add_star(draw, 500, 500, 0, 4)
    return image


def paper_orion(rng):
    image = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), 255)
    cloud = Image.new("L", image.size, 255)
    d = ImageDraw.Draw(cloud)
    d.polygon([(240, 350), (500, 430), (740, 370), (660, 580), (520, 650), (350, 540)], fill=200)
    d.polygon([(420, 350), (500, 440), (570, 355)], fill=250)
    image = ImageChops.darker(image, cloud.filter(ImageFilter.GaussianBlur(28)))
    draw = ImageDraw.Draw(image)
    add_field_stars(draw, rng, 24, excluded_radius=100)
    for x, y in [(479, 471), (513, 472), (490, 504), (524, 504)]:
        add_star(draw, x, y, 0, 4)
    return image


def paper_galaxies(rng, pair=True, cigar=True):
    image = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), 255)
    layer = Image.new("L", image.size, 255)
    draw = ImageDraw.Draw(layer)
    centers = [(360, 570), (650, 340)] if pair else [(500, 500)]
    for i, (cx, cy) in enumerate(centers):
        width, height = (150, 36) if i == 1 and cigar else (170, 80)
        if not pair:
            width, height = 230, 60
        draw.ellipse((cx-width/2, cy-height/2, cx+width/2, cy+height/2), fill=205)
        draw.ellipse((cx-22, cy-15, cx+22, cy+15), fill=110)
    image = ImageChops.darker(image, layer.filter(ImageFilter.GaussianBlur(14)))
    add_field_stars(ImageDraw.Draw(image), rng, 22, excluded_radius=100, bright_count=3)
    return image


def paper_m81_m82(rng):
    """Draw published optical geometry in an arbitrarily rotated eyepiece field."""
    geometry = load_json(ROOT / "data" / "m81-m82-geometry.json")
    members = geometry["members"]
    ra0 = sum(m["ra_degrees"] for m in members) / 2
    dec0 = sum(m["dec_degrees"] for m in members) / 2
    rotation = math.radians(geometry["display_rotation_degrees"])
    image = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), 255)
    for member in members:
        # Small-field projection: north up, east left; rotate both centers and axes.
        east = (member["ra_degrees"] - ra0) * math.cos(math.radians(dec0))
        north = member["dec_degrees"] - dec0
        x, y = -east * geometry["pixels_per_degree"], -north * geometry["pixels_per_degree"]
        cx = CENTER + math.cos(rotation) * x + math.sin(rotation) * y
        cy = CENTER - math.sin(rotation) * x + math.cos(rotation) * y
        layer = Image.new("L", image.size, 255)
        draw = ImageDraw.Draw(layer)
        if member["id"] == "M81":
            draw.ellipse((cx-39, cy-72, cx+39, cy+72), fill=218)
            draw.ellipse((cx-22, cy-37, cx+22, cy+37), fill=185)
            draw.ellipse((cx-11, cy-12, cx+11, cy+12), fill=105)
        else:
            draw.ellipse((cx-10, cy-45, cx+10, cy+45), fill=195)
            draw.ellipse((cx-5, cy-26, cx+5, cy+26), fill=155)
        layer = layer.rotate(member["position_angle_degrees"] + geometry["display_rotation_degrees"], resample=Image.Resampling.BICUBIC, center=(cx, cy), fillcolor=255)
        image = ImageChops.darker(image, layer.filter(ImageFilter.GaussianBlur(10)))
    draw = ImageDraw.Draw(image)
    add_field_stars(draw, rng, 28, bright_count=3)
    return image


SKETCH_BUILDERS = {
    "M8": paper_m8,
    "M11": paper_m11,
    "M13": paper_m13,
    "M27": paper_m27,
    "M31": paper_m31,
    "M57": paper_m57,
    "M42": paper_orion,
    "M38": lambda rng: paper_open(rng, "cross"),
    "M35": lambda rng: paper_open(rng, "chains"),
    "M44": lambda rng: paper_open(rng, "wide"),
    "M67": paper_open,
    "M3": paper_globular,
    "M5": paper_globular,
    "M15": lambda rng: paper_globular(rng, compact=True),
    "M104": lambda rng: paper_galaxies(rng, pair=False),
    "NGC2392": lambda rng: paper_planetary(rng, central=True),
    "NGC3242": paper_planetary,
    "NGC7662": paper_planetary,
    "NGC869/884": lambda rng: paper_open(rng, paired=True),
    "M81/M82": paper_m81_m82,
    "M65/M66": lambda rng: paper_galaxies(rng, cigar=False),
}
SKETCH_SEEDS = {"M13": 7300, "M11": 7401, "M27": 7502, "M31": 7603, "M8": 7704, "M57": 7805}
SKETCH_ASSET_VERSIONS = {"M81/M82": 3}


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_assets(refresh=False):
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    EYEPIECE_DIR.mkdir(parents=True, exist_ok=True)
    existing_manifest = load_json(SKETCH_MANIFEST) if SKETCH_MANIFEST.exists() else {}
    refresh = refresh or existing_manifest.get("generator_version") != SKETCH_GENERATOR_VERSION
    outputs = {}
    manifest_assets = {}
    for target_id, builder in SKETCH_BUILDERS.items():
        asset_version = SKETCH_ASSET_VERSIONS.get(target_id, 1)
        previous_version = existing_manifest.get("assets", {}).get(target_id, {}).get("asset_version", 1)
        safe_id = target_id.replace("/", "-")
        source_path = SOURCE_DIR / f"{safe_id}-paper.png"
        eyepiece_path = EYEPIECE_DIR / f"{safe_id}-eyepiece.png"
        if source_path.exists() and eyepiece_path.exists() and not refresh and previous_version == asset_version:
            outputs[target_id] = eyepiece_path
            manifest_assets[target_id] = {
                "asset_version": asset_version,
                "source": str(source_path.relative_to(ROOT)),
                "eyepiece": str(eyepiece_path.relative_to(ROOT)),
                "source_sha256": file_hash(source_path),
                "eyepiece_sha256": file_hash(eyepiece_path),
            }
            continue
        seed = SKETCH_SEEDS.get(target_id, int(hashlib.sha256(target_id.encode()).hexdigest()[:8], 16))
        source = builder(random.Random(seed))
        source_draw = ImageDraw.Draw(source)
        source_draw.ellipse((CENTER - FIELD_RADIUS, CENTER - FIELD_RADIUS, CENTER + FIELD_RADIUS, CENTER + FIELD_RADIUS), outline=45, width=3)
        source.save(source_path)

        inverted = ImageOps.invert(source)
        alpha = Image.new("L", (IMAGE_SIZE, IMAGE_SIZE), 0)
        ImageDraw.Draw(alpha).ellipse((CENTER - FIELD_RADIUS, CENTER - FIELD_RADIUS, CENTER + FIELD_RADIUS, CENTER + FIELD_RADIUS), fill=255)
        eyepiece = Image.merge("RGBA", (inverted, inverted, inverted, alpha))
        eyepiece.save(eyepiece_path)
        outputs[target_id] = eyepiece_path
        manifest_assets[target_id] = {
            "asset_version": asset_version,
            "source": str(source_path.relative_to(ROOT)),
            "eyepiece": str(eyepiece_path.relative_to(ROOT)),
            "source_sha256": file_hash(source_path),
            "eyepiece_sha256": file_hash(eyepiece_path),
        }
    SKETCH_MANIFEST.write_text(json.dumps({
        "generator_version": SKETCH_GENERATOR_VERSION,
        "artwork_policy": "Original deterministic sketches; no network downloads.",
        "assets": manifest_assets,
    }, indent=2) + "\n")
    return outputs


def draw_qr(c, url, x, y, size):
    qr = QrCodeWidget(url)
    x1, y1, x2, y2 = qr.getBounds()
    scale = size / max(x2 - x1, y2 - y1)
    drawing = Drawing(size, size, transform=[scale, 0, 0, scale, -x1 * scale, -y1 * scale])
    drawing.add(qr)
    renderPDF.draw(drawing, c, x, y)
    c.linkURL(url, (x, y, x + size, y + size), relative=0, thickness=0)


def draw_sketch(c, image_path, x, y, size):
    c.drawImage(ImageReader(image_path), x, y, size, size, preserveAspectRatio=True, mask="auto")


def distance_text(value):
    return f"About {value:,} light-years away"


def build(output_pdf=OUTPUT_PDF, production=False, config_path=CONFIG_PATH, selected=None, refresh_artwork=False):
    config = load_json(config_path)
    targets = load_json(TARGET_PATH)
    images = make_assets(refresh=refresh_artwork)
    selected = selected or config.get("target_proof_selection") or ["M13", "M11", "M27", "M31"]
    if len(selected) != 4:
        raise ValueError("The eyepiece page requires exactly four selected targets")
    unavailable = [target_id for target_id in selected if target_id not in images or target_id not in targets]
    if unavailable:
        raise ValueError(f"No finished eyepiece artwork for: {', '.join(unavailable)}")

    output_pdf = Path(output_pdf)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output_pdf), pagesize=LETTER)
    c.setTitle(f"{config['event_title']} - What You May See" if production else "Eyepiece - telescope eyepiece side proof")
    c.setAuthor(config["organization"]["name"])

    org = config["organization"]
    label(c, f"{org['name'].upper()} | {org['website'].replace('https://', '')}", 36, H - 27, 7.2, ACCENT, "Helvetica-Bold")
    c.linkURL(org["website"], (36, H - 33, 340, H - 18), relative=0, thickness=0)
    label(c, "What You May See", 36, H - 57, 21, INK, "Helvetica-Bold")
    aperture = config.get("telescope", {}).get("aperture_inches", "6-8")
    sky = config.get("telescope", {}).get("sky", "moderately light-polluted")
    label(c, f"Simplified impressions for a {aperture} inch telescope under {sky} skies", 36, H - 73, 8.5, MID)
    label(c, "Views may be rotated or flipped due to telescope optics. Expect subtle gray detail, not a photograph.", 36, H - 87, 7.2, MID)
    c.setStrokeGray(LIGHT)
    c.line(36, H - 97, W - 36, H - 97)

    card_w, card_h = 254, 172
    positions = [(36, 522), (322, 522), (36, 340), (322, 340)]
    for index, ((x, y), target_id) in enumerate(zip(positions, selected), start=1):
        info = targets[target_id]
        rounded_panel(c, x, y, card_w, card_h, white)
        draw_sketch(c, images[target_id], x + 13, y + 31, 116)
        text_x = x + 141
        label(c, f"{index}  {target_id}", text_x, y + 143, 9 if len(target_id) > 7 else 12, INK, "Helvetica-Bold")
        wrap_text(c, info["common_name"], text_x, y + 126, 101, size=8.2, leading=10, shade=INK, max_lines=2)
        label(c, info["type"].upper(), text_x, y + 98, 6.2, ACCENT, "Helvetica-Bold")
        wrap_text(c, distance_text(info["distance_light_years"]), text_x, y + 80, 101, size=7.2, leading=9, shade=INK, max_lines=2)
        if info.get("star_count"):
            fact = f"About {info['star_count']:,} stars in the cluster"
        else:
            fact = info["eyepiece_note"]
        wrap_text(c, fact, text_x, y + 51, 101, size=6.9, leading=8.5, shade=MID, max_lines=3)

    rounded_panel(c, 36, 207, 540, 120, PALE)
    label(c, "FIRST TIME AT THE EYEPIECE", 48, 307, 7, ACCENT, "Helvetica-Bold")
    tips = [
        "Avoid white light and phone screens.",
        "Look straight down, like a toilet-paper tube.",
        "Focus on a star; ask for help if needed.",
        "Give faint objects 15-30 seconds.",
        "Look slightly to the side for faint detail.",
        "Seek a faint fuzzy or smoky patch.",
    ]
    for index, tip in enumerate(tips):
        column, row = index % 2, index // 2
        label(c, f"-  {tip}", 50 + column * 262, 283 - row * 25, 7.4, INK)

    rounded_panel(c, 36, 52, 540, 142, white)
    label(c, "WANT TO LEARN MORE?", 48, 174, 7, ACCENT, "Helvetica-Bold")
    c.setStrokeGray(LIGHT)
    c.setLineWidth(0.7)
    c.line(306, 65, 306, 160)

    draw_qr(c, org["website"], 50, 78, 70)
    label(c, org["name"], 132, 145, 9.2, INK, "Helvetica-Bold")
    wrap_text(c, "Upcoming star parties, member dark-sky events, lectures, and hands-on workshops.", 132, 128, 158, size=6.9, leading=8.5, shade=MID, max_lines=4)
    label(c, "austinastro.org", 132, 86, 7, ACCENT, "Helvetica-Bold")
    c.linkURL(org["website"], (126, 75, 294, 153), relative=0, thickness=0)

    telescope_url = config["resources"]["beginner_telescope_guide"]
    draw_qr(c, telescope_url, 316, 78, 70)
    label(c, "Telescope Buying Guide", 398, 145, 9.2, INK, "Helvetica-Bold")
    wrap_text(c, "Wirecutter's guide to sensible beginner telescope choices.", 398, 128, 158, size=6.9, leading=8.5, shade=MID, max_lines=3)
    wrap_text(c, "nytimes.com/wirecutter/reviews/best-telescopes-for-beginners/", 398, 99, 158, size=5.3, leading=6.5, shade=ACCENT, max_lines=3)
    c.linkURL(telescope_url, (392, 75, 560, 153), relative=0, thickness=0)

    if production:
        footer(c, f"{org['name']} | {org['website'].replace('https://', '')}", "2 / 2")
    else:
        footer(c, "Original simplified illustrations | paper sketches inverted for eyepiece presentation", "1 / 1")
    c.save()
    return output_pdf


if __name__ == "__main__":
    print(build())

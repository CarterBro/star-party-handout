#!/usr/bin/env python3
"""Assemble the production-ready two-sided Austin star-party handout."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject, NameObject
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from sky_map import CONFIG_PATH, compute_data, draw_map_page, event_datetime, load_json
from eyepiece import build as build_back


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "austin-star-party-handout-2026-09-12.pdf"
TEMP_DIR = ROOT / "tmp" / "pdfs" / "handout"


def build(config_path=CONFIG_PATH, output=OUTPUT, data=None, selected=None, refresh_artwork=False):
    config_path = Path(config_path)
    output = Path(output)
    config = load_json(config_path)
    data = data or compute_data(config, config_path=config_path, output_data=None)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    front_path = TEMP_DIR / "front.pdf"
    back_path = TEMP_DIR / "back.pdf"

    front = canvas.Canvas(str(front_path), pagesize=LETTER)
    front.setTitle(f"{config['event_title']} - Tonight's Sky")
    front.setAuthor(config["organization"]["name"])
    draw_map_page(front, config, data, production=True)
    front.save()

    build_back(back_path, production=True, config_path=config_path, selected=selected or data["selected_targets"], refresh_artwork=refresh_artwork)

    writer = PdfWriter()
    writer.add_page(PdfReader(front_path).pages[0])
    writer.add_page(PdfReader(back_path).pages[0])
    dt = event_datetime(config)
    writer.add_metadata({
        "/Title": f"{config['event_title']} Handout - {dt.strftime('%B')} {dt.day}, {dt.year}",
        "/Author": config["organization"]["name"],
        "/Subject": f"Two-sided public observing handout for {config['location']['name']}",
        "/Keywords": "astronomy, star party, sky map, telescope",
    })
    writer.root_object[NameObject("/ViewerPreferences")] = DictionaryObject({
        NameObject("/Duplex"): NameObject("/DuplexFlipLongEdge"),
        NameObject("/PrintScaling"): NameObject("/None"),
    })
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as stream:
        writer.write(stream)

    front_path.unlink()
    back_path.unlink()
    return output


if __name__ == "__main__":
    print(build())

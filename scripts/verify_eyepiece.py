#!/usr/bin/env python3
"""Verify the Eyepiece eyepiece assets and PDF structure."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageOps
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "assets" / "generated" / "sketches" / "source"
EYEPIECE_DIR = ROOT / "assets" / "generated" / "sketches" / "eyepiece"
PDF_PATH = ROOT / "output" / "pdf" / "eyepiece-side-proof.pdf"
TARGETS = ("M13", "M11", "M27", "M31")


def main():
    for target in TARGETS:
        source = Image.open(SOURCE_DIR / f"{target}-paper.png").convert("L")
        eyepiece = Image.open(EYEPIECE_DIR / f"{target}-eyepiece.png").convert("RGBA")
        assert source.size == (1000, 1000)
        assert eyepiece.size == source.size
        alpha = eyepiece.getchannel("A")
        assert alpha.getpixel((0, 0)) == 0
        assert alpha.getpixel((500, 500)) == 255
        inverted_gray = ImageOps.invert(source)
        difference = ImageChops.difference(inverted_gray, eyepiece.getchannel("R"))
        assert difference.getbbox() is None

    reader = PdfReader(PDF_PATH)
    assert len(reader.pages) == 1
    page = reader.pages[0]
    text = page.extract_text() or ""
    normalized_text = " ".join(text.split())
    for phrase in (
        "What You May See",
        "Views may be rotated or flipped due to telescope optics.",
        "FIRST TIME AT THE EYEPIECE",
        "WANT TO LEARN MORE?",
        "Austin Astronomical Society",
        "Telescope Buying Guide",
        "About 2,500,000 light-years away",
    ):
        assert phrase in normalized_text
    assert "magnification" not in text.lower()
    assert "Views can rotate or mirror" not in text
    annotations = page.get("/Annots", [])
    urls = {
        annotation.get_object().get("/A", {}).get("/URI")
        for annotation in annotations
        if annotation.get_object().get("/Subtype") == "/Link"
    }
    assert "https://austinastro.org" in urls
    assert "https://www.nytimes.com/wirecutter/reviews/best-telescopes-for-beginners/" in urls
    print(f"PASS: {len(TARGETS)} reversible sketch pairs, 1-page PDF, {len(urls)} unique links")


if __name__ == "__main__":
    main()

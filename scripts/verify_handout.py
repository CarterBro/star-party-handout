#!/usr/bin/env python3
"""Verify the production-ready two-sided handout."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader
from handout import contains_draft_labels


ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "output" / "pdf" / "austin-star-party-handout-2026-09-12.pdf"
AAS_URL = "https://austinastro.org"
GUIDE_URL = "https://www.nytimes.com/wirecutter/reviews/best-telescopes-for-beginners/"


def page_urls(page):
    return {
        annotation.get_object().get("/A", {}).get("/URI")
        for annotation in page.get("/Annots", [])
        if annotation.get_object().get("/Subtype") == "/Link"
    }


def main():
    reader = PdfReader(PDF_PATH)
    assert len(reader.pages) == 2
    assert reader.metadata.title == "Austin Star Party Handout - September 12, 2026"

    for page in reader.pages:
        box = page.mediabox
        assert round(float(box.width)) == 612
        assert round(float(box.height)) == 792

    front_text = " ".join((reader.pages[0].extract_text() or "").split())
    back_text = " ".join((reader.pages[1].extract_text() or "").split())
    for phrase in ("Tonight's Sky", "POSSIBLE TARGETS", "Austin Astronomical Society", "1 / 2"):
        assert phrase in front_text
    for phrase in ("What You May See", "Views may be rotated or flipped due to telescope optics.", "FIRST TIME AT THE EYEPIECE", "2 / 2"):
        assert phrase in back_text
    assert not contains_draft_labels(front_text + " " + back_text)

    front_urls = page_urls(reader.pages[0])
    back_urls = page_urls(reader.pages[1])
    assert AAS_URL in front_urls
    assert AAS_URL in back_urls
    assert GUIDE_URL in back_urls

    preferences = reader.trailer["/Root"]["/ViewerPreferences"]
    assert preferences["/Duplex"] == "/DuplexFlipLongEdge"
    assert preferences["/PrintScaling"] == "/None"
    print(f"PASS: 2 letter pages, long-edge duplex, {len(front_urls | back_urls)} unique links")


if __name__ == "__main__":
    main()

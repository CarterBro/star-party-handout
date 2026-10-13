#!/usr/bin/env python3
"""Verify the automated handout workflow and its latest Austin regression build."""

from __future__ import annotations

import json
from argparse import Namespace
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

from handout import AUSTIN_LOCATION, resolve_config, contains_draft_labels


ROOT = Path(__file__).resolve().parents[1]
BASE_NAME = "austin-star-party-2026-09-12"
MANIFEST_PATH = ROOT / "output" / "data" / f"{BASE_NAME}-manifest.json"
PDF_PATH = ROOT / "output" / "pdf" / f"{BASE_NAME}.pdf"
SKETCH_MANIFEST_PATH = ROOT / "assets" / "generated" / "sketches" / "manifest.json"
AAS_URL = "https://austinastro.org"
GUIDE_URL = "https://www.nytimes.com/wirecutter/reviews/best-telescopes-for-beginners/"


def page_urls(page):
    return {
        annotation.get_object().get("/A", {}).get("/URI")
        for annotation in page.get("/Annots", [])
        if annotation.get_object().get("/Subtype") == "/Link"
    }


def main():
    args = Namespace(date=None, time=None, magnitude_limit=None, targets=None)
    config, defaults, unavailable = resolve_config(
        {"event_title": "Default test"},
        args,
        now=datetime(2026, 9, 13, 2, 0, tzinfo=timezone.utc),
    )
    assert config["location"] == AUSTIN_LOCATION
    assert config["timezone"] == "America/Chicago"
    assert config["date"] == "2026-09-15"
    assert config["handout_mode"] == "monthly"
    assert "location:Austin, Texas" in defaults and "chart date:2026-09-15" in defaults
    assert not unavailable

    manifest = json.loads(MANIFEST_PATH.read_text())
    assert manifest["selection_mode"] == "automatic-confirmed"
    assert len(manifest["selected_targets"]) == 4
    assert manifest["cache"]["astronomy"]["status"] == "hit"
    assert manifest["cache"]["jpl_validation"]["status"] in {"aggregate-hit", "body-cache-hit"}
    assert manifest["cache"]["render"]["status"] == "hit"
    assert manifest["validation"]["jpl_maximum_difference_degrees"] < 0.05
    assert not manifest["warnings"]

    sketch_manifest = json.loads(SKETCH_MANIFEST_PATH.read_text())
    assert {"M8", "M11", "M13", "M27", "M31", "M57"}.issubset(sketch_manifest["assets"])
    for asset in sketch_manifest["assets"].values():
        assert (ROOT / asset["source"]).exists()
        assert (ROOT / asset["eyepiece"]).exists()

    reader = PdfReader(PDF_PATH)
    assert len(reader.pages) == 2
    assert reader.trailer["/Root"]["/ViewerPreferences"]["/Duplex"] == "/DuplexFlipLongEdge"
    assert AAS_URL in page_urls(reader.pages[0])
    assert {AAS_URL, GUIDE_URL}.issubset(page_urls(reader.pages[1]))
    text = " ".join((page.extract_text() or "") for page in reader.pages)
    lower_text = text.lower()
    for phrase in ("tonight's sky", "possible targets", "what you may see", "austin astronomical society"):
        assert phrase in lower_text
    assert not contains_draft_labels(text)
    print("PASS: defaults, local sketches, cache reuse, JPL check, links, and duplex PDF")


if __name__ == "__main__":
    main()

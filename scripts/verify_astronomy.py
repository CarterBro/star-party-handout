#!/usr/bin/env python3
"""Run structural and numerical checks for the Astronomy outputs."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "output" / "data" / "astronomy-2026-09-12.json"
JPL_PATH = ROOT / "output" / "data" / "jpl-validation-2026-09-12.json"
PDF_PATH = ROOT / "output" / "pdf" / "astronomy-validation.pdf"


def parse_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def angle_difference(a, b):
    return abs((a - b + 180) % 360 - 180)


def main():
    data = json.loads(DATA_PATH.read_text())
    jpl = json.loads(JPL_PATH.read_text())

    assert data["event_utc"].replace(".000Z", "Z") == jpl["event_utc"]
    assert data["computation"]["precession_and_nutation"] is True
    assert data["computation"]["star_magnitude_limit"] == 5
    assert data["computation"]["constellation_lines"] is True
    assert data["computation"]["constellation_boundaries"] is False
    assert data["catalog"]["constellation_lines"]
    assert not data["catalog"]["constellation_boundaries"]
    assert all(star["magnitude"] <= 5 for star in data["catalog"]["stars"])

    twilight = data["twilight"]
    order = [
        parse_time(twilight["sunset_utc"]),
        parse_time(twilight["civil_dusk_utc"]),
        parse_time(twilight["nautical_dusk_utc"]),
        parse_time(twilight["astronomical_dusk_utc"]),
    ]
    assert order == sorted(order)

    maximum = 0
    for name, reference in jpl["bodies"].items():
        calculated = data["bodies"][name]
        maximum = max(
            maximum,
            abs(calculated["altitude_airless"] - reference["altitude_airless_degrees"]),
            angle_difference(calculated["azimuth"], reference["azimuth_degrees"]),
        )
    assert maximum < 0.05

    targets = {target["id"]: target for target in data["targets"]}
    assert set(data["selected_targets"]) == {"M13", "M11", "M27", "M31"}
    assert {targets[target_id]["selection_group"] for target_id in data["selected_targets"]} == {
        "globular cluster", "open cluster", "nebula", "galaxy"
    }
    assert all(len(target["altitude_samples"]) >= 3 for target in targets.values())
    assert any(abs(target["ra_of_date_degrees"] - target["j2000_ra_degrees"]) > 0.1 for target in targets.values())

    reader = PdfReader(PDF_PATH)
    assert len(reader.pages) == 2
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    for phrase in (
        "Tonight's Sky",
        "Astronomy Data Check",
        "NASA/JPL Horizons",
        "TARGET RANKING AND AUTOMATIC SELECTION",
        "constellation boundaries off",
        "POSSIBLE TARGETS",
    ):
        assert phrase in text

    print(f"PASS: 2 pages, {len(data['catalog']['stars'])} catalog stars, max JPL difference {maximum:.4f} deg")


if __name__ == "__main__":
    main()

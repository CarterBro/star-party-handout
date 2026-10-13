#!/usr/bin/env python3
"""Fetch and cache compact independent position checks from NASA/JPL Horizons."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = ROOT / "cache" / "validation" / "jpl"
BODY_IDS = {
    "Sun": "10",
    "Moon": "301",
    "Mercury": "199",
    "Venus": "299",
    "Mars": "499",
    "Jupiter": "599",
    "Saturn": "699",
}


def cache_key(body_id, utc, lon, lat, elevation_m):
    payload = json.dumps({
        "body": body_id,
        "utc": utc,
        "longitude": lon,
        "latitude": lat,
        "elevation_m": elevation_m,
        "endpoint": "https://ssd.jpl.nasa.gov/api/horizons.api",
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def fetch(body_id: str, utc: str, lon: float, lat: float, elevation_m: float):
    params = {
        "format": "json",
        "COMMAND": f"'{body_id}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "CENTER": "'coord@399'",
        "COORD_TYPE": "'GEODETIC'",
        "SITE_COORD": f"'{lon},{lat},{elevation_m / 1000}'",
        "TLIST": f"'{utc[:10]} {utc[11:16]}'",
        "TLIST_TYPE": "'CAL'",
        "TIME_TYPE": "'UT'",
        "ANG_FORMAT": "'DEG'",
        "QUANTITIES": "'1,4,9,10'",
        "CSV_FORMAT": "'YES'",
    }
    url = "https://ssd.jpl.nasa.gov/api/horizons.api?" + urlencode(params)
    with urlopen(url, timeout=30) as response:
        payload = json.load(response)
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    match = re.search(r"\$\$SOE\s*\n([^\n]+)\n\$\$EOE", payload["result"])
    if not match:
        raise RuntimeError("Horizons response did not contain an ephemeris row")
    fields = [field.strip() for field in match.group(1).split(",")]
    return {
        "ra_icrf_degrees": float(fields[3]),
        "dec_icrf_degrees": float(fields[4]),
        "azimuth_degrees": float(fields[5]),
        "altitude_airless_degrees": float(fields[6]),
        "apparent_magnitude": None if fields[7] == "n.a." else float(fields[7]),
        "illumination_percent": None if fields[9] == "n.a." else float(fields[9]),
    }, payload["signature"], params


def build_validation(config, utc, output_path, cache_dir=DEFAULT_CACHE, refresh=False, offline=False):
    loc = config["location"]
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    bodies = {}
    signature = None
    hits = 0
    fetched = 0
    for name, body_id in BODY_IDS.items():
        key = cache_key(body_id, utc, loc["longitude"], loc["latitude"], loc.get("elevation_m", 0))
        body_cache = cache_dir / f"{name.lower()}-{key}.json"
        if body_cache.exists() and not refresh:
            cached = json.loads(body_cache.read_text())
            bodies[name] = cached["data"]
            signature = cached["source"]
            hits += 1
            continue
        if offline:
            raise FileNotFoundError(f"No cached JPL response for {name}: {body_cache}")
        data, signature, request = fetch(
            body_id, utc, loc["longitude"], loc["latitude"], loc.get("elevation_m", 0)
        )
        body_cache.write_text(json.dumps({
            "source": signature,
            "retrieved_utc": datetime.now(timezone.utc).isoformat(),
            "request": request,
            "data": data,
        }, indent=2) + "\n")
        bodies[name] = data
        fetched += 1
        time.sleep(0.75)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": signature,
        "source_url": "https://ssd-api.jpl.nasa.gov/doc/horizons.html",
        "event_utc": utc,
        "site": loc,
        "notes": "Airless apparent azimuth/elevation from a topocentric observer table.",
        "cache": {"hits": hits, "network_fetches": fetched},
        "bodies": bodies,
    }
    output_path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config")
    parser.add_argument("utc")
    parser.add_argument("output")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE))
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text())
    result = build_validation(config, args.utc, args.output, args.cache_dir, args.refresh, args.offline)
    print(json.dumps(result["cache"]))


if __name__ == "__main__":
    main()

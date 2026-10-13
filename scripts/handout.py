#!/usr/bin/env python3
"""Interactive and cache-aware star-party handout generator."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

def load_runtime():
    global PdfReader, compute_data, event_datetime, SKETCH_BUILDERS, SKETCH_GENERATOR_VERSION
    global build_pdf, JPL_CACHE, build_validation
    try:
        from pypdf import PdfReader
        from sky_map import compute_data, event_datetime
        from eyepiece import SKETCH_BUILDERS, SKETCH_GENERATOR_VERSION
        from build_handout import build as build_pdf
        from fetch_jpl_validation import DEFAULT_CACHE as JPL_CACHE, build_validation
    except ModuleNotFoundError as exc:
        raise ValueError(f"Missing Python dependency '{exc.name}'. Activate .venv and run: python -m pip install -r requirements.txt") from exc


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "output"
ASTRONOMY_CACHE = ROOT / "cache" / "astronomy"
CONFIG_CACHE = ROOT / "cache" / "config"
RENDER_CACHE = ROOT / "cache" / "renders"
TARGETS_PATH = ROOT / "data" / "targets.json"

AUSTIN_LOCATION = {
    "name": "Austin, Texas",
    "latitude": 30.2672,
    "longitude": -97.7431,
    "elevation_m": 149,
}

DEFAULTS = {
    "event_title": "Austin Star Party",
    "organization": {
        "name": "Austin Astronomical Society",
        "website": "https://austinastro.org",
    },
    "time": "21:00",
    "telescope": {"aperture_inches": "6-8", "sky": "moderately light-polluted"},
    "target_candidates": list(json.loads(TARGETS_PATH.read_text())),
    "target_selection": {
        "count": 4,
        "manual_overrides": [],
        "evaluation_hour_offsets": [0, 1, 2],
        "preferred_groups": ["globular cluster", "open cluster", "nebula", "galaxy"],
        "minimum_altitude_degrees": 20,
    },
    "sky_map": {
        "star_magnitude_limit": 5.0,
        "show_constellation_lines": True,
        "show_constellation_boundaries": False,
        "apply_precession": True,
        "apply_refraction": True,
    },
    "resources": {
        "beginner_telescope_guide": "https://www.nytimes.com/wirecutter/reviews/best-telescopes-for-beginners/"
    },
    "print": {"paper": "US Letter", "duplex": "flip on long edge"},
}


def deep_merge(base, update):
    result = copy.deepcopy(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def slugify(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "star-party"


def hash_payload(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def normalize_utc(value):
    return value.replace(".000Z", "Z").replace("+00:00", "Z")


def resolve_config(raw, args, now=None):
    load_runtime()
    if not isinstance(raw, dict):
        raise ValueError("The event JSON must be an object, starting with { and ending with }.")
    for field in ("organization", "location", "telescope", "target_selection", "sky_map", "resources", "print"):
        if field in raw and not isinstance(raw[field], dict):
            raise ValueError(f"{field} must be a JSON object.")
    config = deep_merge(DEFAULTS, {key: value for key, value in raw.items() if key != "location"})
    defaults_applied = []
    if "location" not in raw:
        config["location"] = copy.deepcopy(AUSTIN_LOCATION)
        config["timezone"] = raw.get("timezone", "America/Chicago")
        defaults_applied.append("location:Austin, Texas")
    else:
        location = raw["location"]
        missing = [key for key in ("name", "latitude", "longitude") if key not in location]
        if missing:
            raise ValueError(f"Custom location is missing: {', '.join(missing)}")
        config["location"] = deep_merge({"elevation_m": 0}, location)
        if not raw.get("timezone"):
            raise ValueError("A custom location requires an explicit IANA timezone")
        config["timezone"] = raw["timezone"]

    try:
        ZoneInfo(config["timezone"])
    except (ZoneInfoNotFoundError, TypeError, ValueError) as exc:
        raise ValueError("timezone must be a valid IANA name, for example America/Chicago.") from exc
    for field in ("event_title", "time"):
        if not isinstance(config[field], str) or not config[field].strip():
            raise ValueError(f"{field} must be a nonempty string.")
    for field in ("latitude", "longitude", "elevation_m"):
        value = config["location"][field]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f"location.{field} must be a finite number, without quotes.")
    if not isinstance(config["location"]["name"], str) or not config["location"]["name"].strip():
        raise ValueError("location.name must be a nonempty string.")
    for field in ("target_candidates",):
        if not isinstance(config[field], list) or not all(isinstance(x, str) for x in config[field]):
            raise ValueError(f"{field} must be an array of target IDs, such as [\"M13\", \"M11\", \"M27\", \"M31\"].")
        config[field] = list(dict.fromkeys(x.upper().strip() for x in config[field]))
    selection = config["target_selection"]
    if selection["count"] != 4:
        raise ValueError("target_selection.count must be 4 for the four-sketch layout.")
    manual = selection["manual_overrides"]
    if not isinstance(manual, list) or not all(isinstance(x, str) for x in manual):
        raise ValueError("target_selection.manual_overrides must be an array of target IDs.")
    if manual and (len(manual) != 4 or len(set(manual)) != 4):
        raise ValueError("manual_overrides must be empty or contain exactly four different target IDs.")
    for target in manual:
        if target not in config["target_candidates"] or target not in SKETCH_BUILDERS:
            raise ValueError(f"Manual target {target} must be a supported target included in target_candidates.")
    requested_month = getattr(args, "month", None)
    if requested_month and args.date:
        raise ValueError("Choose --month YYYY-MM or --date YYYY-MM-DD, not both.")
    if args.date:
        config["date"] = args.date
        config["handout_mode"] = "nightly"
    elif requested_month or raw.get("month") or raw.get("handout_mode") == "monthly" or not raw.get("date"):
        clock = now or datetime.now(ZoneInfo(config["timezone"]))
        month = requested_month or raw.get("month") or clock.astimezone(ZoneInfo(config["timezone"])).strftime("%Y-%m")
        if not isinstance(month, str) or not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", month):
            raise ValueError("Month must be YYYY-MM, for example 2026-11.")
        try:
            datetime.strptime(month + "-15", "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("Month must contain a valid year from 0001 to 9999.") from exc
        config.update(date=month + "-15", month=month, handout_mode="monthly")
        defaults_applied.append(f"chart date:{config['date']}")
    else:
        config["handout_mode"] = "nightly"
    if config["handout_mode"] == "nightly":
        config.pop("month", None)
    if args.time:
        config["time"] = args.time
    elif not raw.get("time"):
        month_number = int(config["date"][5:7]) if isinstance(config.get("date"), str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", config["date"]) else 10
        config["time"] = "20:00" if month_number in (11, 12, 1, 2) else "21:00"
        defaults_applied.append(f"time:{config['time']}")
    if not isinstance(config["date"], str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", config["date"]):
        raise ValueError("Date must be YYYY-MM-DD, for example 2026-10-17.")
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", config["time"]):
        raise ValueError("Time must be local 24-hour HH:MM, for example 21:00.")
    for field in ("show_constellation_lines", "show_constellation_boundaries", "apply_precession", "apply_refraction"):
        if not isinstance(config["sky_map"][field], bool):
            raise ValueError(f"sky_map.{field} must be true or false, without quotes.")
    offsets = selection["evaluation_hour_offsets"]
    if not isinstance(offsets, list) or not offsets or offsets[0] != 0 or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and 0 <= x <= 24 for x in offsets):
        raise ValueError("evaluation_hour_offsets must start with 0 and contain numeric hours from 0 to 24, such as [0, 1, 2].")
    for section, fields in (("organization", ("name", "website")), ("resources", ("beginner_telescope_guide",)), ("telescope", ("aperture_inches", "sky"))):
        for field in fields:
            if not isinstance(config[section][field], str) or not config[section][field].strip():
                raise ValueError(f"{section}.{field} must be a nonempty string.")
    if args.magnitude_limit is not None:
        config["sky_map"]["star_magnitude_limit"] = args.magnitude_limit
    magnitude = config["sky_map"]["star_magnitude_limit"]
    if isinstance(magnitude, bool) or not isinstance(magnitude, (int, float)) or not math.isfinite(magnitude) or not -2 <= magnitude <= 6:
        raise ValueError("star magnitude limit must be between -2 and 6; the bundled catalog stops at magnitude 6.")
    if args.targets:
        explicit = [item.strip().upper() for item in args.targets.split(",") if item.strip()]
        config["target_candidates"] = list(dict.fromkeys(config["target_candidates"] + explicit))
    if config["handout_mode"] == "monthly":
        seasonal = json.loads((ROOT / "data" / "seasonal-targets.json").read_text())[str(int(config["month"][5:7]))]
        config["target_candidates"] = list(dict.fromkeys(config["target_candidates"] + seasonal))

    try:
        ZoneInfo(config["timezone"])
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {config['timezone']}") from exc
    try:
        event_datetime(config)
    except ValueError as exc:
        raise ValueError("Date must be YYYY-MM-DD and time must be HH:MM") from exc
    lat = float(config["location"]["latitude"])
    lon = float(config["location"]["longitude"])
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("Latitude or longitude is out of range")

    unavailable = [target for target in config["target_candidates"] if target not in SKETCH_BUILDERS]
    if unavailable:
        raise ValueError(f"Unsupported target IDs: {', '.join(unavailable)}. Run --list-targets to see the implemented artwork library.")
    config["target_candidates"] = [target for target in config["target_candidates"] if target in SKETCH_BUILDERS]
    if len(config["target_candidates"]) < 4:
        raise ValueError("At least four candidate targets with finished artwork are required")
    return config, defaults_applied, unavailable


def display_event(config, defaults_applied):
    dt = event_datetime(config)
    print("\nEvent details")
    if config.get("handout_mode") == "monthly":
        print(f"  Month:    {dt.strftime('%B %Y')} (chart calculated for the 15th)")
    else:
        print(f"  Date:     {dt.strftime('%A, %B')} {dt.day}, {dt.year}")
    print(f"  Time:     {dt.strftime('%I:%M %p').lstrip('0')} {dt.tzname()}")
    print(f"  Location: {config['location']['name']} ({config['location']['latitude']:.4f}, {config['location']['longitude']:.4f})")
    if defaults_applied:
        print(f"  Defaults: {', '.join(defaults_applied)}")


def confirm(prompt, input_fn=input):
    answer = input_fn(prompt).strip().lower()
    return answer in ("", "y", "yes")


def cache_fingerprint(config):
    source_hashes = {}
    paths = [ROOT / "scripts" / "astronomy_data.py", TARGETS_PATH, ROOT / "data" / "seasonal-targets.json", ROOT / "requirements.txt"]
    paths.extend(sorted((ROOT / "data" / "catalogs").glob("*.json")))
    for path in paths:
        source_hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hash_payload({"config": config, "sources": source_hashes})


def cached_astronomy(config, config_path, refresh=False):
    key = cache_fingerprint(config)
    path = ASTRONOMY_CACHE / f"{key}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text()), {"status": "hit", "key": key, "path": str(path.relative_to(ROOT))}
    data = compute_data(config, config_path=config_path, output_data=None)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    return data, {"status": "created", "key": key, "path": str(path.relative_to(ROOT))}


def print_suggestions(data):
    targets = {target["id"]: target for target in data["targets"]}
    print("\nSuggested targets")
    for index, target_id in enumerate(data["selected_targets"], start=1):
        target = targets[target_id]
        samples = target["altitude_samples"]
        trend = "rising" if samples[-1]["altitude"] > samples[0]["altitude"] else "setting"
        print(f"  {index}. {target_id} - {target['common_name']}")
        print(f"     {target['type']} | {target['altitude']:.0f} degrees high | {trend}")


def validate_selected(selected, data):
    selected = [item.strip().upper() for item in selected if item.strip()]
    available = {target["id"] for target in data["targets"]} & set(SKETCH_BUILDERS)
    if len(selected) != 4 or len(set(selected)) != 4:
        raise ValueError("Choose exactly four different targets")
    missing = [target for target in selected if target not in available]
    if missing:
        raise ValueError(f"Targets are not eligible or lack artwork: {', '.join(missing)}")
    return selected


def choose_targets(config, data, args, input_fn=input):
    if args.targets:
        return validate_selected(args.targets.split(","), data), "command-line"
    manual = config.get("target_selection", {}).get("manual_overrides", [])
    if len(manual) == 4:
        chosen = validate_selected(manual, data)
        if args.non_interactive or config.get("handout_mode") != "monthly":
            return chosen, "configuration"
        data["selected_targets"] = chosen
    if args.non_interactive:
        if not args.accept_suggested_targets:
            raise ValueError("Non-interactive builds require --targets or --accept-suggested-targets")
        return data["selected_targets"], "automatic-confirmed"

    print_suggestions(data)
    while True:
        answer = input_fn("Use these four targets? [Y/edit/n]: ").strip().lower()
        if answer in ("", "y", "yes"):
            return data["selected_targets"], "interactive-confirmed"
        if answer in ("n", "no"):
            raise RuntimeError("Target selection cancelled")
        if answer in ("e", "edit"):
            print("\nRanked eligible targets")
            for target in data["targets"]:
                print(f"  {target['id']}: {target['common_name']} ({target['altitude']:.0f} deg, score {target['score']:.1f})")
            choice = input_fn("Enter four target IDs separated by commas: ")
            try:
                return validate_selected(choice.split(","), data), "interactive-edited"
            except ValueError as exc:
                print(f"  {exc}")
        else:
            print("  Enter Y, edit, or n.")


def matching_validation(config, utc):
    candidates = list((ROOT / "output" / "data").glob("*jpl*.json"))
    candidates += list((ROOT / "cache" / "validation" / "aggregates").glob("*.json"))
    for path in sorted(candidates, reverse=True):
        try:
            payload = json.loads(path.read_text())
            site = payload["site"]
            if normalize_utc(payload["event_utc"]) != normalize_utc(utc):
                continue
            if abs(site["latitude"] - config["location"]["latitude"]) > 1e-7:
                continue
            if abs(site["longitude"] - config["location"]["longitude"]) > 1e-7:
                continue
            return payload, path
        except (KeyError, ValueError, json.JSONDecodeError):
            continue
    return None, None


def validate_ephemeris(data, validation):
    maximum = 0.0
    for name, reference in validation["bodies"].items():
        calculated = data["bodies"][name]
        alt_diff = abs(calculated["altitude_airless"] - reference["altitude_airless_degrees"])
        az_diff = abs((calculated["azimuth"] - reference["azimuth_degrees"] + 180) % 360 - 180)
        maximum = max(maximum, alt_diff, az_diff)
    if maximum >= 0.05:
        raise ValueError(f"JPL validation failed: maximum difference {maximum:.4f} degrees")
    return maximum


def get_validation(config, config_path, data, output_path, args, warnings):
    utc = normalize_utc(data["event_utc"])
    if not args.refresh_validation:
        payload, path = matching_validation(config, utc)
        if payload:
            output_path.write_text(json.dumps(payload, indent=2) + "\n")
            return payload, {"status": "aggregate-hit", "path": str(path.relative_to(ROOT))}
    try:
        payload = build_validation(
            config, utc, output_path, JPL_CACHE,
            refresh=args.refresh_validation, offline=args.offline,
        )
        status = "network" if payload["cache"]["network_fetches"] else "body-cache-hit"
        return payload, {"status": status, **payload["cache"]}
    except Exception as exc:
        warnings.append(f"Independent JPL validation unavailable: {exc}")
        return None, {"status": "unavailable", "reason": str(exc)}


def contains_draft_labels(text):
    """Recognize generator draft headings without matching ordinary words or URLs."""
    normalized = " ".join(text.lower().split())
    return any(label in normalized for label in (
        "astronomy map proof", "astronomy validation", "telescope eyepiece side proof",
    ))


def verify_pdf(pdf_path, config):
    reader = PdfReader(pdf_path)
    if len(reader.pages) != 2:
        raise ValueError("Production PDF must contain exactly two pages")
    text = [" ".join((page.extract_text() or "").split()) for page in reader.pages]
    expected_title = "Night Sky" if config.get("handout_mode") == "monthly" else "Tonight's Sky"
    if expected_title not in text[0] or "What You May See" not in text[1]:
        raise ValueError("PDF page order is incorrect")
    if contains_draft_labels(" ".join(text)):
        raise ValueError("Production PDF contains a draft heading")
    for page in reader.pages:
        if round(float(page.mediabox.width)) != 612 or round(float(page.mediabox.height)) != 792:
            raise ValueError("Production PDF is not US Letter size")
    preferences = reader.trailer["/Root"].get("/ViewerPreferences", {})
    if preferences.get("/Duplex") != "/DuplexFlipLongEdge":
        raise ValueError("Production PDF is missing long-edge duplex metadata")
    return {"pages": 2, "paper": "US Letter", "duplex": "long-edge", "status": "passed"}


def render_fingerprint(config, selected):
    source_paths = [
        ROOT / "scripts" / "sky_map.py",
        ROOT / "scripts" / "eyepiece.py",
        ROOT / "scripts" / "build_handout.py",
        ROOT / "data" / "targets.json",
        ROOT / "requirements.txt",
    ]
    source_hashes = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in source_paths
    }
    sketch_manifest = ROOT / "assets" / "generated" / "sketches" / "manifest.json"
    if sketch_manifest.exists():
        source_hashes[str(sketch_manifest.relative_to(ROOT))] = hashlib.sha256(sketch_manifest.read_bytes()).hexdigest()
    return hash_payload({"config": config, "selected": selected, "sources": source_hashes})


def render_qa(pdf_path, cache_key, refresh=False):
    render_dir = RENDER_CACHE / cache_key
    expected = [render_dir / f"grayscale-{page}.png" for page in (1, 2)]
    if all(path.exists() for path in expected) and not refresh:
        return {"status": "hit", "key": cache_key, "path": str(render_dir.relative_to(ROOT))}
    executable = shutil.which("pdftoppm")
    if not executable:
        return {"status": "unavailable", "reason": "pdftoppm not installed"}
    render_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["XDG_CACHE_HOME"] = str(ROOT / "tmp" / "font-cache")
    try:
        subprocess.run([executable, "-gray", "-png", "-r", "144", str(pdf_path), str(render_dir / "grayscale")], check=True, capture_output=True, env=env)
    except subprocess.CalledProcessError:
        return {"status": "unavailable", "reason": "pdftoppm failed; check the Poppler installation and retry with --refresh-render"}
    return {"status": "created", "key": cache_key, "path": str(render_dir.relative_to(ROOT))}


def build_parser():
    parser = argparse.ArgumentParser(description="Generate a monthly two-page US Letter handout. Defaults: Austin, current month (chart for the 15th), 20:00 November-February or 21:00 March-October. --date restores a night-specific handout.", formatter_class=argparse.RawDescriptionHelpFormatter, epilog="Examples:\n  python scripts/handout.py --month 2026-11\n  python scripts/handout.py --date 2026-10-17\n  python scripts/handout.py --config config/event-template.json --check-config\n\nSetup: see README.md. Diagnostics: python scripts/doctor.py.\nExit codes: 0 success (possibly with warnings), 2 invalid input/build failure, 130 cancelled.")
    parser.add_argument("--list-targets", action="store_true", help="List implemented targets and exit without building")
    parser.add_argument("--check-config", action="store_true", help="Validate inputs and show resolved defaults without building or contacting JPL")
    parser.add_argument("--config", help="Event JSON; omitted fields use documented defaults")
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument("--month", help="Monthly handout for YYYY-MM; defaults to current local month")
    date_group.add_argument("--date", help="Night-specific handout for YYYY-MM-DD")
    parser.add_argument("--time", help="Override local event time (HH:MM)")
    parser.add_argument("--targets", help="Four comma-separated target IDs")
    parser.add_argument("--magnitude-limit", type=float, help="Faintest chart stars (-2 to 6; default 5; smaller means fewer stars)")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT), help="Output directory containing pdf/ and data/ (default: project output/)")
    parser.add_argument("--non-interactive", action="store_true", help="Skip prompts; requires four explicit targets, four config overrides, or --accept-suggested-targets")
    parser.add_argument("--accept-suggested-targets", action="store_true", help="Approve automatic target selection for an unattended build")
    parser.add_argument("--offline", action="store_true", help="Use local data only; missing JPL validation becomes a warning")
    parser.add_argument("--refresh-validation", action="store_true", help="Fetch fresh JPL responses (cannot combine with --offline)")
    parser.add_argument("--refresh-astronomy", action="store_true", help="Recompute local astronomy data")
    parser.add_argument("--refresh-artwork", action="store_true", help="Regenerate the original local sketches")
    parser.add_argument("--refresh-render", action="store_true", help="Regenerate grayscale previews")
    return parser


def main(argv=None, input_fn=input):
    args = build_parser().parse_args(argv)
    if args.list_targets:
        metadata = json.loads(TARGETS_PATH.read_text())
        for target, info in metadata.items():
            print(f"{target:5} {info['common_name']} ({info['type']})")
        print("Paired IDs occupy one handout slot. Use IDs exactly as listed (no spaces in NGC IDs).")
        return 0
    load_runtime()
    if args.offline and args.refresh_validation:
        raise ValueError("Choose --offline or --refresh-validation; fresh JPL responses require network access.")
    try:
        raw = json.loads(Path(args.config).read_text()) if args.config else {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {args.config}, line {exc.lineno}, column {exc.colno}: {exc.msg}. Use double quotes and remove trailing commas.") from exc
    config, defaults_applied, unavailable = resolve_config(raw, args)
    display_event(config, defaults_applied)
    if args.targets:
        validate_selected(args.targets.split(","), {"targets": [{"id": t} for t in config["target_candidates"]]})
    if args.check_config:
        print("Configuration valid. No files generated and no network requests made.")
        return 0
    if args.non_interactive and not (args.targets or config["target_selection"]["manual_overrides"] or args.accept_suggested_targets):
        raise ValueError("Non-interactive builds require --targets M13,M11,M27,M31, four manual_overrides, or --accept-suggested-targets.")
    if not args.non_interactive and not confirm("Continue with these event details? [Y/n]: ", input_fn):
        raise RuntimeError("Event details not confirmed")

    period = config["month"] if config.get("handout_mode") == "monthly" else config["date"]
    base_name = f"{slugify(config['event_title'])}-{period}"
    output_root = Path(args.output_dir).resolve()
    data_dir = output_root / "data"
    pdf_dir = output_root / "pdf"
    data_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    CONFIG_CACHE.mkdir(parents=True, exist_ok=True)

    preliminary_path = CONFIG_CACHE / f"{hash_payload(config)[:24]}.json"
    preliminary_path.write_text(json.dumps(config, indent=2) + "\n")
    preliminary_data, preliminary_cache = cached_astronomy(config, preliminary_path, args.refresh_astronomy)
    selected, selection_mode = choose_targets(config, preliminary_data, args, input_fn)
    config["target_selection"]["manual_overrides"] = selected

    resolved_path = data_dir / f"{base_name}-config.json"
    resolved_path.write_text(json.dumps(config, indent=2) + "\n")
    data, astronomy_cache = cached_astronomy(config, resolved_path, args.refresh_astronomy)
    data["selected_targets"] = selected
    astronomy_path = data_dir / f"{base_name}-astronomy.json"
    astronomy_path.write_text(json.dumps(data, indent=2) + "\n")

    warnings = []
    if unavailable:
        warnings.append(f"Excluded targets without finished artwork: {', '.join(unavailable)}")
    validation_path = data_dir / f"{base_name}-jpl-validation.json"
    validation, validation_cache = get_validation(config, resolved_path, data, validation_path, args, warnings)
    validation_max = validate_ephemeris(data, validation) if validation else None

    pdf_path = pdf_dir / f"{base_name}.pdf"
    build_pdf(resolved_path, pdf_path, data=data, selected=selected, refresh_artwork=args.refresh_artwork)
    pdf_checks = verify_pdf(pdf_path, config)
    render_cache = render_qa(pdf_path, render_fingerprint(config, selected), args.refresh_render)
    if render_cache["status"] == "unavailable":
        warnings.append(f"Visual QA render unavailable: {render_cache['reason']}")

    target_by_id = {target["id"]: target for target in data["targets"]}
    manifest = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "event": config,
        "defaults_applied": defaults_applied,
        "configuration_sha256": hash_payload(config),
        "selected_targets": [
            {
                "id": target_id,
                "common_name": target_by_id[target_id]["common_name"],
                "altitude_degrees": round(target_by_id[target_id]["altitude"], 2),
                "score": target_by_id[target_id]["score"],
            }
            for target_id in selected
        ],
        "selection_mode": selection_mode,
        "cache": {
            "preliminary_astronomy": preliminary_cache,
            "astronomy": astronomy_cache,
            "jpl_validation": validation_cache,
            "render": render_cache,
            "sketch_generator_version": SKETCH_GENERATOR_VERSION,
        },
        "validation": {
            "jpl_maximum_difference_degrees": validation_max,
            "pdf": pdf_checks,
        },
        "warnings": warnings,
        "outputs": {
            "pdf": str(pdf_path),
            "resolved_config": str(resolved_path),
            "astronomy": str(astronomy_path),
            "jpl_validation": str(validation_path) if validation else None,
        },
    }
    manifest_path = data_dir / f"{base_name}-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    print("\nBuild complete")
    print(f"  PDF:      {pdf_path}")
    print(f"  Manifest: {manifest_path}")
    print(f"  Targets:  {', '.join(selected)}")
    print(f"  Cache:    astronomy={astronomy_cache['status']}, JPL={validation_cache['status']}, render={render_cache['status']}")
    for warning in warnings:
        print(f"  Warning:  {warning}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print("Cancelled. For unattended runs, use --non-interactive with explicit target approval.", file=sys.stderr)
        raise SystemExit(130)
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: External command failed: {exc.cmd}. {exc.stderr or ''}\nRun python scripts/doctor.py to check the installation.", file=sys.stderr)
        raise SystemExit(2)
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)

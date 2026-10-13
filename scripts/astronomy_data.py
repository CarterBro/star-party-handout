"""Calculate chart and observing data locally with Python Astronomy Engine."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import astronomy as A

ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / 'data' / 'catalogs'
CATALOG_FILES = ('stars.6.json', 'starnames.json', 'constellations.lines.json',
                 'constellations.borders.json', 'constellations.json', 'targets.json')


def read_catalog(name):
    return json.loads((CATALOG_DIR / name).read_text())


def iso(time):
    return time.Utc().replace(tzinfo=timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z') if time else None


def round_tenth(value):
    # Preserve the previous engine's positive-score Math.round convention.
    return math.floor(value * 10 + 0.5) / 10


def compute_astronomy(config, utc_iso):
    # Python callers emit +00:00; the library parser expects a Z suffix.
    instant = datetime.fromisoformat(utc_iso.replace('Z', '+00:00'))
    if instant.tzinfo is None:
        raise ValueError('Astronomy calculation time must include a UTC offset.')
    date = A.Time.Parse(instant.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'))
    location = config['location']
    observer = A.Observer(location['latitude'], location['longitude'], location.get('elevation_m', 0))
    settings = config.get('sky_map', {})
    precession = settings.get('apply_precession', True)
    refraction = A.Refraction.Normal if settings.get('apply_refraction', True) else A.Refraction.Airless
    rotation = A.Rotation_EQJ_EQD(date)

    def equatorial(ra, dec, at=date):
        if not precession:
            return {'ra_degrees': ra % 360, 'dec_degrees': dec}
        vector = A.VectorFromSphere(A.Spherical(dec, ra % 360, 1), at)
        rot = rotation if at is date else A.Rotation_EQJ_EQD(at)
        sphere = A.SphereFromVector(A.RotateVector(rot, vector))
        return {'ra_degrees': sphere.lon % 360, 'dec_degrees': sphere.lat}

    def horizontal(ra, dec, at=date):
        eq = equatorial(ra, dec, at)
        h = A.Horizon(at, observer, eq['ra_degrees'] / 15, eq['dec_degrees'], refraction)
        return {'altitude': h.altitude, 'azimuth': h.azimuth,
                'ra_of_date_degrees': eq['ra_degrees'], 'dec_of_date_degrees': eq['dec_degrees']}

    def point(coordinates):
        ra, dec = coordinates
        return {'j2000': [ra % 360, dec], **horizontal(ra, dec)}

    search_start = date.AddDays(-0.5)
    twilight = {
        'sunset_utc': iso(A.SearchRiseSet(A.Body.Sun, observer, A.Direction.Set, search_start, 1)),
        'civil_dusk_utc': iso(A.SearchAltitude(A.Body.Sun, observer, A.Direction.Set, search_start, 1, -6)),
        'nautical_dusk_utc': iso(A.SearchAltitude(A.Body.Sun, observer, A.Direction.Set, search_start, 1, -12)),
        'astronomical_dusk_utc': iso(A.SearchAltitude(A.Body.Sun, observer, A.Direction.Set, search_start, 1, -18)),
        'moonset_utc': iso(A.SearchRiseSet(A.Body.Moon, observer, A.Direction.Set, search_start, 1)),
        'next_moonrise_utc': iso(A.SearchRiseSet(A.Body.Moon, observer, A.Direction.Rise, date, 1)),
    }
    bodies = {}
    for name in ('Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn', 'Uranus', 'Neptune'):
        body = A.Body[name]
        eq = A.Equator(body, date, observer, True, True)
        apparent = A.Horizon(date, observer, eq.ra, eq.dec, refraction)
        airless = A.Horizon(date, observer, eq.ra, eq.dec, A.Refraction.Airless)
        light = A.Illumination(body, date)
        bodies[name] = {'ra_of_date_degrees': eq.ra * 15, 'dec_of_date_degrees': eq.dec,
                        'altitude': apparent.altitude, 'altitude_airless': airless.altitude,
                        'azimuth': apparent.azimuth, 'magnitude': light.mag, 'phase_fraction': light.phase_fraction}

    magnitude_limit = settings.get('star_magnitude_limit', 5)
    names = read_catalog('starnames.json')
    stars = [{'id': str(s['id']), 'magnitude': float(s['properties']['mag']),
              'name': names.get(str(s['id']), {}).get('name', ''), **point(s['geometry']['coordinates'])}
             for s in read_catalog('stars.6.json')['features'] if float(s['properties']['mag']) <= magnitude_limit]

    def lines(filename):
        return [{'id': f['id'], 'rank': int(f.get('properties', {}).get('rank', 3)),
                 'lines': [[point(p) for p in line] for line in f['geometry']['coordinates']]}
                for f in read_catalog(filename)['features']]

    constellation_lines = lines('constellations.lines.json') if settings.get('show_constellation_lines', True) else []
    boundaries = lines('constellations.borders.json') if settings.get('show_constellation_boundaries', False) else []
    labels = [{'id': f['id'].upper(), 'rank': int(f.get('properties', {}).get('rank', 3)), **point(f['geometry']['coordinates'])}
              for f in read_catalog('constellations.json')['features']]
    metadata = json.loads((ROOT / 'data' / 'targets.json').read_text())
    catalog = read_catalog('targets.json')
    selection = config.get('target_selection', {})
    offsets = selection.get('evaluation_hour_offsets', [0, 1, 2])
    minimum_altitude = selection.get('minimum_altitude_degrees', 20)
    moon = bodies['Moon']
    targets = []
    for target_id in config['target_candidates']:
        meta = metadata[target_id]
        member_ids = meta.get('catalog_members', [meta.get('catalog_id', target_id)])
        try:
            members = [catalog[key] for key in member_ids]
        except KeyError as exc:
            raise ValueError(f'Missing local catalog coordinates for {target_id}: {exc}') from exc
        first_ra = members[0]['coordinates'][0]
        ra = sum(first_ra + (m['coordinates'][0] - first_ra + 540) % 360 - 180 for m in members) / len(members)
        dec = sum(m['coordinates'][1] for m in members) / len(members)
        magnitude = min(m['magnitude'] for m in members)
        samples = []
        for offset in offsets:
            at = date if offset == 0 else date.AddDays(offset / 24)
            samples.append({'offset_hours': offset, 'utc': iso(at), **horizontal(ra, dec, at)})
        position = samples[0]
        eq = equatorial(ra, dec)
        d1, d2 = math.radians(eq['dec_degrees']), math.radians(moon['dec_of_date_degrees'])
        dra = math.radians(eq['ra_degrees'] - moon['ra_of_date_degrees'])
        cosine = math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(dra)
        separation = math.degrees(math.acos(max(-1, min(1, cosine))))
        visibility = max(0, min(45, max(s['altitude'] for s in samples) / 80 * 45))
        brightness = max(0, min(20, 20 - max(0, magnitude - 4) * 3))
        beginner = meta['beginner_suitability'] * 2
        moon_score = 10 if moon['altitude'] < 0 else min(10, separation / 12)
        staying = 5 if samples[-1]['altitude'] >= minimum_altitude else 0
        penalty = 25 if position['altitude'] < minimum_altitude else 0
        score = max(0, min(100, visibility + brightness + beginner + moon_score + staying - penalty))
        targets.append({'id': target_id, **meta, 'catalog_magnitude': magnitude,
                        'j2000_ra_degrees': ra % 360, 'j2000_dec_degrees': dec,
                        'ra_of_date_degrees': eq['ra_degrees'], 'dec_of_date_degrees': eq['dec_degrees'],
                        'altitude': position['altitude'], 'azimuth': position['azimuth'],
                        'moon_separation_degrees': separation, 'altitude_samples': samples,
                        'score': round_tenth(score), 'score_components': {
                            'visibility': round_tenth(visibility), 'brightness': round_tenth(brightness),
                            'beginner': round_tenth(beginner), 'moon': round_tenth(moon_score),
                            'staying_power': staying, 'horizon_penalty': penalty}})
    targets.sort(key=lambda t: -t['score'])
    for rank, target in enumerate(targets, 1):
        target['rank'] = rank
    by_id = {t['id']: t for t in targets}
    selected = []
    for target_id in selection.get('manual_overrides', []):
        if target_id in by_id and target_id not in selected:
            selected.append(target_id)
    for group in selection.get('preferred_groups', []):
        if any(by_id[t]['selection_group'] == group for t in selected):
            continue
        match = next((t for t in targets if t['selection_group'] == group and t['id'] not in selected), None)
        if match:
            selected.append(match['id'])
    count = selection.get('count', 4)
    for target in targets:
        if len(selected) >= count:
            break
        if target['id'] not in selected:
            selected.append(target['id'])
    return {
        'schema_version': 1, 'generated_utc': datetime.now(timezone.utc).isoformat(), 'event_utc': iso(date),
        'event': {'title': config['event_title'], 'date': config['date'], 'time': config['time'],
                  'timezone': config['timezone'], 'location': location},
        'computation': {'engine': f'astronomy-engine Python {version("astronomy-engine")}',
                        'catalog_epoch': 'J2000.0', 'position_frame': 'true equator and equinox of date' if precession else 'J2000.0',
                        'precession_and_nutation': precession, 'atmospheric_refraction': refraction == A.Refraction.Normal,
                        'star_magnitude_limit': magnitude_limit, 'constellation_lines': settings.get('show_constellation_lines', True),
                        'constellation_boundaries': settings.get('show_constellation_boundaries', False)},
        'twilight': twilight, 'bodies': bodies, 'targets': targets, 'selected_targets': selected[:count],
        'catalog': {'stars': stars, 'constellation_lines': constellation_lines,
                    'constellation_boundaries': boundaries, 'constellation_labels': labels},
    }

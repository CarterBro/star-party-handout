"""Protect the Python migration against the saved pre-migration astronomy results."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from astronomy_data import compute_astronomy
from handout import DEFAULTS, AUSTIN_LOCATION


class AstronomyParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = {**DEFAULTS, 'date': '2026-10-12', 'timezone': 'America/Chicago', 'location': AUSTIN_LOCATION}
        # The old event used this confirmed order, while scoring remains unchanged.
        cls.config['target_selection'] = {**DEFAULTS['target_selection'], 'manual_overrides': ['M15','NGC869/884','M27','M31']}
        cls.data = compute_astronomy(cls.config, '2026-10-13T02:00:00Z')
        cls.reference = json.loads((ROOT / 'tests/fixtures/astronomy-2026-10-12.json').read_text())

    def test_body_positions_and_illumination_match_previous_engine(self):
        for name, values in self.reference['bodies'].items():
            for key, expected in values.items():
                self.assertAlmostEqual(self.data['bodies'][name][key], expected, delta=1e-6)

    def test_targets_scores_rankings_and_future_altitudes_match(self):
        actual = {t['id']: t for t in self.data['targets']}
        for reference in self.reference['targets']:
            target = actual[reference['id']]
            for key in ('altitude','azimuth','score','rank'):
                self.assertAlmostEqual(target[key], reference[key], delta=1e-6)
            for sample, old in zip(target['altitude_samples'], reference['altitude_samples']):
                self.assertAlmostEqual(sample['altitude'], old['altitude'], delta=1e-6)
        self.assertEqual(self.data['selected_targets'], self.reference['selected_targets'])

    def test_twilight_and_moon_times_have_explicit_utc(self):
        for key, expected in self.reference['twilight'].items():
            self.assertEqual(self.data['twilight'][key], expected)
        self.assertEqual(self.data['event_utc'], self.reference['event_utc'])

    def test_catalog_stars_match(self):
        for actual, old in zip(self.data['catalog']['stars'], self.reference['star_sample']):
            self.assertEqual(actual['id'], old['id'])
            self.assertAlmostEqual(actual['altitude'], old['altitude'], delta=1e-6)

    def test_precession_toggle_applies_to_every_sample(self):
        config = {**self.config, 'sky_map': {**self.config['sky_map'], 'apply_precession': False}}
        data = compute_astronomy(config, '2026-10-13T02:00:00Z')
        for target in data['targets']:
            for sample in target['altitude_samples']:
                self.assertAlmostEqual(sample['ra_of_date_degrees'], target['j2000_ra_degrees'])
                self.assertAlmostEqual(sample['dec_of_date_degrees'], target['j2000_dec_degrees'])

    def test_pair_uses_all_members_and_retains_one_slot(self):
        target = next(t for t in self.data['targets'] if t['id']=='M81/M82')
        self.assertEqual(target['catalog_members'], ['M81','M82'])
        self.assertAlmostEqual(target['j2000_ra_degrees'], (148.8996+148.9496)/2)

    def test_network_free_calculation(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('Unexpected network request')):
            self.assertEqual(len(compute_astronomy(self.config,'2026-10-13T02:00:00Z')['targets']),21)

    def test_python_datetime_offset_and_local_offset_are_normalized(self):
        for instant in ('2026-10-13T02:00:00+00:00', '2026-10-12T21:00:00-05:00'):
            self.assertEqual(compute_astronomy(self.config,instant)['event_utc'],self.data['event_utc'])

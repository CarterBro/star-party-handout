"""Exercise operator errors via the real CLI without producing handouts."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'handout.py'

class OperatorCLI(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=ROOT, text=True, capture_output=True)

    def test_help_without_site_packages(self):
        result = subprocess.run([sys.executable, '-S', str(SCRIPT), '--help'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn('--check-config', result.stdout)

    def test_missing_dependencies_explain_setup(self):
        result = subprocess.run([sys.executable, '-S', str(SCRIPT), '--check-config'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('pip install -r requirements.txt', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_valid_saved_config(self):
        result = self.run_cli('--config', 'config/event-2026-09-19-dripping-springs.json', '--check-config')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Dripping Springs', result.stdout)

    def test_bad_inputs(self):
        cases = [
            ({'timezone': 'Not/AZone'}, 'timezone'),
            ({'location': {'name': 'Test', 'latitude': '30', 'longitude': -98}, 'timezone': 'America/Chicago'}, 'finite number'),
            ({'target_candidates': ['M13','M11','M27','M999']}, 'Unsupported'),
            ({'target_selection': {'manual_overrides': ['M13']}}, 'exactly four'),
            ({'sky_map': {'star_magnitude_limit': 7}}, 'magnitude'),
            ([], 'JSON must be an object'),
        ]
        for payload, message in cases:
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'event.json'
                path.write_text(json.dumps(payload))
                result = self.run_cli('--config', str(path), '--check-config')
                self.assertEqual(result.returncode, 2)
                self.assertIn(message, result.stderr)
                self.assertNotIn('Traceback', result.stderr)

    def test_conflicting_offline_refresh(self):
        result = self.run_cli('--offline', '--refresh-validation', '--check-config')
        self.assertEqual(result.returncode, 2)
        self.assertIn('network access', result.stderr)

    def test_unattended_requires_approval(self):
        result = self.run_cli('--non-interactive', '--date', '2026-09-19', '--offline')
        self.assertEqual(result.returncode, 2)
        self.assertIn('--targets', result.stderr)

    def test_json_error_has_line(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'event.json'
            path.write_text('{"date":}')
            result = self.run_cli('--config', str(path), '--check-config')
            self.assertEqual(result.returncode, 2)
            self.assertIn('line 1', result.stderr)

if __name__ == '__main__':
    unittest.main()

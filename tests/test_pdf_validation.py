"""Regression checks for resource URLs wrongly classified as draft text."""
import sys
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import handout
from handout import contains_draft_labels

class PDFValidation(unittest.TestCase):
    def test_buying_guide_url_is_allowed(self):
        self.assertFalse(contains_draft_labels('nytimes.com/wirecutter/reviews/best-telescopes-for-beginners/'))

    def test_ordinary_review_and_proof_words_are_allowed(self):
        self.assertFalse(contains_draft_labels('Review observing tips. Weatherproof clothing.'))

    def test_known_draft_headings_are_rejected(self):
        for heading in ('Astronomy map proof', 'Astronomy validation', 'Telescope eyepiece side proof'):
            with self.subTest(heading=heading):
                self.assertTrue(contains_draft_labels(heading))

    def test_preview_uses_only_grayscale_render(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(handout, 'ROOT', Path(folder)), patch.object(handout, 'RENDER_CACHE', Path(folder) / 'renders'), patch.object(handout.shutil, 'which', return_value='/usr/bin/pdftoppm'), patch.object(handout.subprocess, 'run') as run:
                result = handout.render_qa(Path('example.pdf'), 'test')
                self.assertEqual(result['status'], 'created')
                self.assertEqual(run.call_count, 1)
                self.assertIn('-gray', run.call_args.args[0])
                self.assertTrue(run.call_args.args[0][-1].endswith('/grayscale'))

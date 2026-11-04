import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from xd_theme import read_preference, save_preference

class AppearancePreferenceTests(unittest.TestCase):
    def test_default_migration_and_explicit_override(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'appearance.json'
            with patch('xd_theme.preference_path', return_value=path):
                self.assertEqual(read_preference(), '跟随系统')
                path.write_text(json.dumps({'theme': '深色'}), encoding='utf8')
                self.assertEqual(read_preference(), '跟随系统')
                save_preference('浅色')
                self.assertEqual(read_preference(), '浅色')
                save_preference('跟随系统')
                self.assertEqual(read_preference(), '跟随系统')

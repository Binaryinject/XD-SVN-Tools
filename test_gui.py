"""GUI state regression without clicking the user's desktop."""
import argparse
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch
from test_core import make_archive
from xd_svn import App
from xd_core import MISSING

class GuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = App(self.root, argparse.Namespace(command=None))
        self.app.mode = 'merge'

    def tearDown(self):
        self.app.executor.shutdown(wait=True)
        self.root.destroy()
        self.tmp.cleanup()

    def test_conflict_selection_and_candidate_review(self):
        p = Path(self.tmp.name)
        archives = [make_archive(p/str(i), {'x': x, 'y': 0}) for i, x in enumerate((0,1,2))]
        self.app.loaded(archives)
        self.assertEqual(len(self.app.engine.unresolved), 1)
        self.assertEqual(str(self.app.save_button.cget('state')), 'disabled')
        item = next(iter(self.app.conflict_items))
        self.app.conflict_tree.selection_set(item)
        self.app.choose('theirs')
        self.assertFalse(self.app.engine.unresolved)
        self.assertEqual(str(self.app.save_button.cget('state')), 'normal')
        self.app.comparison.current(2)
        self.app.refresh_diff()
        self.assertIn('合并结果', self.app.diff_summary)
        self.assertTrue(self.app.diff_tree.get_children())

    def test_independent_merge_enables_save(self):
        p = Path(self.tmp.name)
        archives = [make_archive(p/str(i), v) for i, v in enumerate(({'x':0,'y':0},{'x':1,'y':0},{'x':0,'y':2}))]
        self.app.loaded(archives)
        self.assertEqual(str(self.app.save_button.cget('state')), 'normal')

    def test_colored_lines_and_original_numbers(self):
        self.app.render_pair({'a': 0, 'b': 1}, {'a': 2, 'b': 1})
        left, right = self.app.diff_views
        self.assertTrue(left.tag_ranges('change'))
        self.assertTrue(right.tag_ranges('inline'))
        self.assertFalse(left.tag_names('1.0') == ('change',))
        self.assertIn('     2 ~', left.get('1.0', 'end'))
        self.assertEqual(self.app.change_lines, [2])

    def test_added_file_green_and_deleted_file_red(self):
        self.app.render_pair(MISSING, {'x': 1})
        left, right = self.app.diff_views
        self.assertTrue(right.tag_ranges('add'))
        self.assertTrue(left.tag_ranges('gap'))
        self.app.render_pair({'x': 1}, MISSING)
        self.assertTrue(left.tag_ranges('delete'))
        self.assertFalse(right.tag_ranges('add'))

    def test_merge_status_colors_and_unresolved_gate(self):
        p = Path(self.tmp.name)
        archives = [make_archive(p/str(i), v) for i, v in enumerate(({'x':0,'a':0,'b':0},{'x':1,'a':2,'b':0},{'x':3,'a':0,'b':4}))]
        self.app.loaded(archives)
        self.assertEqual(len(self.app.automatic_items), 2)
        item = next(iter(self.app.conflict_items))
        self.assertIn('unresolved', self.app.conflict_tree.item(item, 'tags'))
        self.assertEqual(str(self.app.save_button.cget('state')), 'disabled')
        auto = next(iter(self.app.automatic_items))
        self.assertIn('automatic', self.app.conflict_tree.item(auto, 'tags'))
        self.app.conflict_tree.selection_set(auto)
        self.app.choose('mine')
        self.assertEqual(len(self.app.engine.unresolved), 1)
        self.app.conflict_tree.selection_set(item)
        self.app.choose('theirs')
        resolved = next(iter(self.app.conflict_items))
        self.assertIn('resolved', self.app.conflict_tree.item(resolved, 'tags'))
        self.assertIn('需解决冲突 0 项', self.app.status.get())
        self.assertEqual(str(self.app.save_button.cget('state')), 'normal')

    def test_system_appearance_updates_without_losing_diff(self):
        self.app.theme_name.set('跟随系统')
        self.app.render_pair({'x': 0}, {'x': 1})
        with patch('xd_svn.resolve_theme', return_value='浅色'):
            self.app.apply_theme()
        with patch('xd_svn.resolve_theme', return_value='深色'):
            self.app.watch_system_theme()
        self.assertEqual(self.app.effective_theme, '深色')
        self.assertTrue(self.app.diff_views[0].tag_ranges('change'))
        self.assertIn('"x": 0', self.app.diff_views[0].get('1.0', 'end'))

    def test_manual_appearance_ignores_system_changes(self):
        self.app.theme_name.set('浅色')
        self.app.apply_theme()
        with patch('xd_svn.resolve_theme', return_value='深色'):
            self.app.watch_system_theme()
        self.assertEqual(self.app.effective_theme, '浅色')

if __name__ == '__main__':
    unittest.main(verbosity=2)

import unittest
from xd_line_diff import aligned_lines, changed_spans

class LineDiffTests(unittest.TestCase):
    def test_insert_aligned_with_gap(self):
        rows = aligned_lines('a\nc', 'a\nb\nc')
        self.assertEqual([r.kind for r in rows], ['equal', 'add', 'equal'])
        self.assertIsNone(rows[1].left_number)
        self.assertEqual((rows[2].left_number, rows[2].right_number), (2, 3))

    def test_delete(self):
        rows = aligned_lines('a\nb\nc', 'a\nc')
        self.assertEqual(rows[1].kind, 'delete')
        self.assertIsNone(rows[1].right_number)

    def test_modified_rows_not_entire_file(self):
        rows = aligned_lines('a\nb\nc', 'a\nB\nc')
        self.assertEqual([r.kind for r in rows], ['equal', 'change', 'equal'])

    def test_inline(self):
        self.assertEqual(changed_spans('"x": 123', '"x": 153'), ([(6, 7)], [(6, 7)]))

    def test_new_file(self):
        self.assertTrue(all(r.kind == 'add' for r in aligned_lines('', '{\n  "x": 1\n}')))

    def test_long_path_line_bounded(self):
        self.assertEqual(changed_spans('x'*5000, 'y'*5000), ([], []))

    def test_removed_property_keeps_next_changed_key_aligned(self):
        rows = aligned_lines('  "obsolete": 0,\n  "title": "old"', '  "title": "new"')
        self.assertEqual([r.kind for r in rows], ['delete', 'change'])
        self.assertEqual(rows[1].left_number, 2)

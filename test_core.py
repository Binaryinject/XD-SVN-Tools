import copy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from xd_core import Archive, Merger, MISSING, diff_values, merge_archives, save_archive, validate_result

def make_archive(path, tree=None, extra=None):
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('mimetype', 'application/vnd.adobe.sparkler.project+dcxucf')
        z.writestr('manifest', '{}')
        z.writestr('artwork/artboard-A/graphics/graphicContent.agc', json.dumps(tree if tree is not None else {'children': []}))
        for k, v in (extra or {}).items():
            z.writestr(k, v)
    return Archive.read(path)

class MergeTests(unittest.TestCase):
    def test_independent_attributes(self):
        e = Merger()
        self.assertEqual(e.merge({'x': 0, 'y': 0}, {'x': 1, 'y': 0}, {'x': 0, 'y': 2}, 'p'), {'x': 1, 'y': 2})
        self.assertFalse(e.unresolved)
        self.assertEqual({a.key for a in e.automatic}, {'p/x', 'p/y'})
        self.assertEqual({a.result for a in e.automatic}, {1, 2})

    def test_automatic_does_not_include_unchanged_or_conflict(self):
        e = Merger()
        e.merge({'x': 0, 'same': 1}, {'x': 1, 'same': 1}, {'x': 2, 'same': 1}, 'p')
        self.assertFalse(e.automatic)
        self.assertEqual(len(e.unresolved), 1)

    def test_identical_changes_marked_automatic(self):
        e = Merger()
        e.merge(0, 1, 1, 'p')
        self.assertEqual(len(e.automatic), 1)
        self.assertEqual(e.automatic[0].result, 1)

    def test_conflict_and_explicit_choice(self):
        e = Merger({'p/x': 'theirs'})
        self.assertEqual(e.merge({'x': 0}, {'x': 1}, {'x': 2}, 'p'), {'x': 2})
        self.assertEqual(len(e.conflicts), 1)
        self.assertFalse(e.unresolved)

    def test_delete_modify(self):
        e = Merger()
        e.merge({'x': 0}, {}, {'x': 2}, 'p')
        self.assertEqual(e.unresolved[0].key, 'p/x')

    def test_new_object_collision(self):
        e = Merger()
        e.merge({}, {'new': {'a': 1}}, {'new': {'b': 2}}, 'p')
        self.assertEqual(len(e.unresolved), 1)

    def test_id_array(self):
        b = [{'id': 'a', 'x': 0}, {'id': 'b', 'x': 0}]
        m, t = copy.deepcopy(b), copy.deepcopy(b)
        m[0]['x'], t[1]['x'] = 1, 2
        e = Merger()
        self.assertEqual([x['x'] for x in e.merge(b, m, t, 'p')], [1, 2])
        self.assertFalse(e.unresolved)

    def test_order_kept(self):
        b = [{'id': 'a', 'x': 0}, {'id': 'b', 'x': 0}]
        m, t = list(reversed(copy.deepcopy(b))), copy.deepcopy(b)
        t[0]['x'] = 2
        e = Merger()
        result = e.merge(b, m, t, 'p')
        self.assertEqual([x['id'] for x in result], ['b', 'a'])
        self.assertEqual(result[1]['x'], 2)
        self.assertFalse(e.unresolved)

    def test_both_structural_edits_conflict(self):
        b = [{'id': 'a'}, {'id': 'b'}]
        e = Merger()
        e.merge(b, b + [{'id': 'c'}], list(reversed(b)), 'p')
        self.assertEqual(len(e.unresolved), 1)

    def test_duplicate_ids_atomic(self):
        b = [{'id': 'a'}, {'id': 'a'}]
        e = Merger()
        e.merge(b, b + [{'id': 'm'}], b + [{'id': 't'}], 'p')
        self.assertEqual(len(e.unresolved), 1)

    def test_primitive_array_atomic(self):
        e = Merger()
        e.merge([1, 2], [3, 2], [1, 4], 'p')
        self.assertEqual(len(e.unresolved), 1)

    def test_bool_not_number(self):
        e = Merger()
        e.merge(0, True, 1, 'p')
        self.assertEqual(len(e.unresolved), 1)

    def test_binary_conflict(self):
        e = Merger()
        e.merge(b'base', b'mine', b'theirs', 'p')
        self.assertEqual(len(e.unresolved), 1)

    def test_keyed_diff(self):
        changes = diff_values([{'id': 'a', 'x': 0}], [{'id': 'a', 'x': 1}])
        self.assertEqual(changes[0][0], '/@id=a/x')

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Path(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()

    def test_roundtrip_preserves_binary_and_backup(self):
        b = make_archive(self.p/'base.xd', {'x': 0, 'y': 0}, {'resources/img': b'\x00\x01'})
        m = make_archive(self.p/'mine.xd', {'x': 1, 'y': 0}, {'resources/img': b'\x00\x01'})
        t = make_archive(self.p/'theirs.xd', {'x': 0, 'y': 2}, {'resources/img': b'\x00\x01'})
        output = self.p/'输出 文件.xd'
        output.write_bytes(b'original output')
        result, e = merge_archives(b, m, t)
        self.assertFalse(e.unresolved)
        backup = save_archive(result, [b, m, t], output)
        self.assertEqual(backup.read_bytes(), b'original output')
        a = Archive.read(output)
        self.assertEqual(a.entries['resources/img'], b'\x00\x01')
        self.assertEqual(a.value('artwork/artboard-A/graphics/graphicContent.agc'), {'x': 1, 'y': 2})
        with zipfile.ZipFile(output) as z:
            self.assertEqual(z.infolist()[0].filename, 'mimetype')
            self.assertEqual(z.infolist()[0].compress_type, zipfile.ZIP_STORED)

    def test_deleted_entry_does_not_reappear(self):
        b = make_archive(self.p/'b', extra={'old': b'old'})
        m = make_archive(self.p/'m')
        t = make_archive(self.p/'t', extra={'old': b'old', 'new': b'new'})
        result, e = merge_archives(b, m, t)
        self.assertNotIn('old', result)
        self.assertEqual(result['new'], b'new')
        self.assertFalse(e.unresolved)

    def test_input_changed_blocks_save(self):
        a = [make_archive(self.p/str(i)) for i in range(3)]
        result, _ = merge_archives(*a)
        a[1].path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, '修改'):
            save_archive(result, a, self.p/'out')
        self.assertFalse((self.p/'out').exists())

    def test_known_ref_loss_blocks_save(self):
        a = [make_archive(self.p/str(i), {'nodes': [{'id': 'A'}], 'ref': 'A'}) for i in range(3)]
        result = dict(a[0].entries)
        result['artwork/artboard-A/graphics/graphicContent.agc'] = b'{"ref":"A"}'
        self.assertTrue(validate_result(result, a))

    def test_external_ref_allowed(self):
        a = [make_archive(self.p/str(i), {'ref': 'external-library'}) for i in range(3)]
        self.assertFalse(validate_result(a[0].entries, a))

    def test_bad_zip(self):
        path = self.p/'bad'
        path.write_bytes(b'not zip')
        with self.assertRaises(zipfile.BadZipFile):
            Archive.read(path)

    def test_unsafe_path_rejected(self):
        path = self.p/'bad'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr('../escape', 'no')
        with self.assertRaisesRegex(ValueError, '路径'):
            Archive.read(path)

    def test_invalid_json_rejected(self):
        with self.assertRaisesRegex(ValueError, '解析'):
            make_archive(self.p/'bad', extra={'bad.json': '{'})

    def test_cannot_overwrite_base(self):
        a = [make_archive(self.p/str(i)) for i in range(3)]
        with self.assertRaisesRegex(ValueError, 'BASE'):
            save_archive(a[0].entries, a, a[0].path)

if __name__ == '__main__':
    unittest.main(verbosity=2)

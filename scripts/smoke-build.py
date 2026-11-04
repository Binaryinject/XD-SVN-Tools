"""Validate the frozen entry point without installing into the runner account."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_version import VERSION

exe = str(Path(sys.argv[1]).resolve())
with tempfile.TemporaryDirectory(prefix='xd-build-') as directory:
    root = Path(directory)
    for name, content in (
        ('base', {'x': 0, 'y': 0}),
        ('mine', {'x': 1, 'y': 0}),
        ('theirs', {'x': 0, 'y': 2}),
        ('conflict', {'x': 3, 'y': 0}),
    ):
        with zipfile.ZipFile(root / (name + '.xd'), 'w') as archive:
            archive.writestr('mimetype', 'application/vnd.adobe.sparkler.project+dcxucf')
            archive.writestr('manifest', '{}')
            archive.writestr('artwork/artboard-A/graphics/graphicContent.agc', json.dumps(content))
    for name, expected_code, expected_conflicts in [('theirs', 0, 0), ('conflict', 1, 1)]:
        report = root / '中文 report.json'
        result = subprocess.run([
            exe, 'check', '--base', str(root / 'base.xd'), '--mine', str(root / 'mine.xd'),
            '--theirs', str(root / (name + '.xd')), '--report', str(report),
        ], timeout=60)
        if result.returncode != expected_code:
            raise RuntimeError(f'Frozen check returned {result.returncode}, expected {expected_code}')
        data = json.loads(report.read_text(encoding='utf-8'))
        if data['version'] != VERSION or len(data['conflicts']) != expected_conflicts:
            raise RuntimeError('Frozen report version or conflict count is incorrect')
print('Frozen EXE smoke checks passed: version, independent merge, conflict, Unicode paths.')

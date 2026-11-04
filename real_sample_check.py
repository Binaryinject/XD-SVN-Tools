"""Integration check against AdobeXD/plugin-samples/banner.xd (not bundled)."""
from pathlib import Path
import json
import sys
import zipfile
from xd_core import Archive, merge_archives, save_archive, validate_result

folder = Path(sys.argv[1]).resolve()
base = Archive.read(folder/'banner.xd')
agc = 'artwork/pasteboard/graphics/graphicContent.agc'
for name, axis, delta in [('mine', 'tx', 40), ('theirs', 'ty', 30), ('conflict', 'tx', 80)]:
    values = dict(base.entries)
    tree = base.value(agc)
    tree['children'][0]['transform'][axis] += delta
    values[agc] = json.dumps(tree, ensure_ascii=False).encode('utf-8')
    with zipfile.ZipFile(folder/(name+'.xd'), 'w') as z:
        for n, data in values.items():
            z.writestr(n, data)
mine, theirs = [Archive.read(folder/(n+'.xd')) for n in ('mine','theirs')]
entries, engine = merge_archives(base, mine, theirs)
assert not engine.unresolved, [c.key for c in engine.unresolved]
assert not validate_result(entries, [base, mine, theirs])
output = folder/'merged-real.xd'
save_archive(entries, [base, mine, theirs], output)
original = base.value(agc)['children'][0]['transform']
result = Archive.read(output).value(agc)['children'][0]['transform']
assert result['tx'] == original['tx'] + 40
assert result['ty'] == original['ty'] + 30
for n, data in base.entries.items():
    if not n.endswith(('.agc', '.json')) and n != 'manifest':
        assert entries[n] == data, n
conflict = Archive.read(folder/'conflict.xd')
_, e = merge_archives(base, mine, conflict)
assert len(e.unresolved) == 1
print('Real Adobe sample: independent transforms merged; conflicting transform detected; all non-JSON resources preserved.')
print(output)

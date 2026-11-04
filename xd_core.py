"""XD archive diff and conservative three-way merge. No XD runtime required.

Inspired by dilitirio/xd-scenegraph-toolkit and theseion/git-xd-merge.
See THIRD_PARTY_NOTICES.txt. No Git subprocesses or archive extraction used.
"""
from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass, field

MISSING = object()
MAX_TOTAL = 1024 * 1024 * 1024
MAX_ENTRY = 256 * 1024 * 1024

def equal(a, b):
    if a is MISSING or b is MISSING:
        return a is b
    if isinstance(a, bytes) or isinstance(b, bytes):
        return type(a) is type(b) and a == b
    # bool and number must not compare equal; dictionary order is immaterial.
    return canonical(a) == canonical(b)

def canonical(v):
    return json.dumps(v, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))

def display(v):
    if v is MISSING:
        return '（不存在 / 删除）'
    if isinstance(v, bytes):
        return f'二进制文件：{len(v):,} bytes\nSHA-256: {hashlib.sha256(v).hexdigest()}'
    return json.dumps(v, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)

def parse_json(data):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise ValueError('重复 JSON 键：' + k)
            result[k] = v
        return result
    return json.loads(data.decode('utf-8-sig'), object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))

def is_json_name(name):
    return name.endswith(('.agc', '.json')) or PurePosixPath(name).name == 'manifest'

@dataclass
class Archive:
    path: Path
    entries: dict[str, bytes] = field(default_factory=dict)
    infos: dict = field(default_factory=dict)
    comment: bytes = b''
    digest: str = ''

    @classmethod
    def read(cls, path):
        path = Path(path).resolve()
        a = cls(path)
        a.digest = file_hash(path)
        with zipfile.ZipFile(path) as z:
            a.comment = z.comment
            total = 0
            for info in z.infolist():
                name = info.filename
                p = PurePosixPath(name)
                if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
                    raise ValueError('不安全的压缩包路径：' + name)
                if name in a.infos:
                    raise ValueError('压缩包存在重名条目：' + name)
                total += info.file_size
                if info.file_size > MAX_ENTRY or total > MAX_TOTAL:
                    raise ValueError('压缩包超过限制（单项 256 MiB / 总计 1 GiB）')
                a.infos[name] = info
                a.entries[name] = z.read(info)
        if 'mimetype' not in a.entries or 'manifest' not in a.entries or not any(n.endswith('.agc') for n in a.entries):
            raise ValueError('不是支持的本地 XD 文档：缺少 mimetype / manifest / AGC')
        if b'adobe' not in a.entries['mimetype'].lower():
            raise ValueError('未知的 XD mimetype')
        for name, data in a.entries.items():
            if is_json_name(name):
                try:
                    parse_json(data)
                except (ValueError, UnicodeError) as ex:
                    raise ValueError(f'无法解析 {name}: {ex}') from ex
        if file_hash(path) != a.digest:
            raise ValueError('读取期间输入文件发生变化，请重新加载')
        return a

    def value(self, name):
        data = self.entries.get(name, MISSING)
        return parse_json(data) if data is not MISSING and is_json_name(name) else data

def file_hash(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def keyed(v):
    if not isinstance(v, list):
        return None
    if not all(isinstance(x, dict) and isinstance(x.get('id'), str) for x in v):
        return None
    ids = [x['id'] for x in v]
    return dict(zip(ids, v)) if len(set(ids)) == len(ids) else None

def segment(k):
    return str(k).replace('~', '~0').replace('/', '~1')

@dataclass
class Conflict:
    key: str
    reason: str
    base: object
    mine: object
    theirs: object

@dataclass
class AutoMerge:
    key: str
    reason: str
    base: object
    mine: object
    theirs: object
    result: object

class Merger:
    def __init__(self, choices=None):
        self.choices = choices or {}
        self.conflicts = []
        self.unresolved = []
        self.automatic = []

    def conflict(self, path, b, m, t, reason):
        c = Conflict(path, reason, b, m, t)
        self.conflicts.append(c)
        choice = self.choices.get(path)
        if choice not in ('base', 'mine', 'theirs'):
            self.unresolved.append(c)
            return m
        return {'base': b, 'mine': m, 'theirs': t}[choice]

    def merge(self, b, m, t, path):
        if equal(m, t):
            if not equal(b, m):
                self.automatic.append(AutoMerge(path, '双方修改相同', b, m, t, m))
            return m
        if equal(m, b):
            self.automatic.append(AutoMerge(path, '采用 THEIRS 的独立修改', b, m, t, t))
            return t
        if equal(t, b):
            self.automatic.append(AutoMerge(path, '采用 MINE 的独立修改', b, m, t, m))
            return m
        if b is MISSING or m is MISSING or t is MISSING:
            return self.conflict(path, b, m, t, '新增内容不同，或删除与修改冲突')
        if all(isinstance(x, dict) for x in (b, m, t)):
            result = {}
            for k in sorted(b.keys() | m.keys() | t.keys()):
                v = self.merge(b.get(k, MISSING), m.get(k, MISSING), t.get(k, MISSING), path + '/' + segment(k))
                if v is not MISSING:
                    result[k] = v
            return result
        maps = [keyed(x) for x in (b, m, t)]
        if all(x is not None for x in maps):
            bi, mi, ti = maps
            orders = [[x['id'] for x in a] for a in (b, m, t)]
            bo, mo, to = orders
            # One structural edit is safe only if the other side did not edit
            # deleted nodes. Two structural edits require whole-array review.
            if mo != bo and to != bo and mo != to:
                return self.conflict(path, b, m, t, '双方改变节点集合或图层顺序；需整体选择')
            result = {}
            for k in sorted(bi.keys() | mi.keys() | ti.keys()):
                v = self.merge(bi.get(k, MISSING), mi.get(k, MISSING), ti.get(k, MISSING), path + '/@id=' + segment(k))
                if v is not MISSING:
                    result[k] = v
            order = mo if mo != bo else to
            # A delete/modify conflict may explicitly restore a deleted node.
            # Its insertion position cannot be inferred safely: elevate conflict.
            if any(k not in order for k in result):
                return self.conflict(path + '/@membership', b, m, t, '恢复节点后的叠放位置不明确；需整体选择')
            if order != bo:
                self.automatic.append(AutoMerge(path + '/@order', '采用独立的图层顺序或节点集合修改', bo, mo, to, order))
            return [result[k] for k in order if k in result]
        return self.conflict(path, b, m, t, '双方修改同一属性或不可按 ID 匹配的数组')

def merge_archives(base, mine, theirs, choices=None):
    engine = Merger(choices)
    result = {}
    for name in sorted(base.entries.keys() | mine.entries.keys() | theirs.entries.keys()):
        b, m, t = (a.value(name) for a in (base, mine, theirs))
        v = engine.merge(b, m, t, name)
        if v is not MISSING:
            result[name] = (json.dumps(v, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
                            if is_json_name(name) else v)
    return result, engine

def diff_values(a, b, path='', limit=5000):
    changes = []
    def walk(x, y, p):
        if len(changes) >= limit or equal(x, y):
            return
        if isinstance(x, dict) and isinstance(y, dict):
            for k in sorted(x.keys() | y.keys()):
                walk(x.get(k, MISSING), y.get(k, MISSING), p + '/' + segment(k))
        elif keyed(x) is not None and keyed(y) is not None:
            xi, yi = keyed(x), keyed(y)
            if list(xi) != list(yi):
                changes.append((p + '/@order', list(xi), list(yi)))
            for k in sorted(xi.keys() | yi.keys()):
                walk(xi.get(k, MISSING), yi.get(k, MISSING), p + '/@id=' + segment(k))
        else:
            changes.append((p or '/', x, y))
    walk(a, b, path)
    return changes

def reference_facts(entries):
    ids, refs, hrefs = set(), [], []
    def walk(v, path):
        if isinstance(v, dict):
            if isinstance(v.get('id'), str):
                ids.add(v['id'])
            for k, x in v.items():
                if k in ('ref', 'targetId', 'artboardId') and isinstance(x, str):
                    refs.append((path + '/' + k, x))
                if k in ('href', 'path') and isinstance(x, str):
                    hrefs.append((path + '/' + k, x.lstrip('/')))
                walk(x, path + '/' + segment(k))
        elif isinstance(v, list):
            for i, x in enumerate(v):
                walk(x, path + '/' + str(i))
    for name, data in entries.items():
        if is_json_name(name):
            walk(parse_json(data), name)
    return ids, refs, hrefs

def validate_result(entries, archives):
    errors = []
    if any(n not in entries for n in ('manifest', 'mimetype')) or not any(n.endswith('.agc') for n in entries):
        errors.append('缺少 XD 必需的 manifest / mimetype / AGC')
    known_ids, known_paths = set(), set()
    for a in archives:
        ids, _, _ = reference_facts(a.entries)
        known_ids.update(ids)
        known_paths.update(a.entries)
    ids, refs, hrefs = reference_facts(entries)
    for path, target in refs:
        if target in known_ids and target not in ids:
            errors.append(f'引用目标已丢失：{path} → {target}')
    for path, target in hrefs:
        if target in known_paths and target not in entries:
            errors.append(f'资源路径已丢失：{path} → {target}')
    return errors

def save_archive(entries, archives, output):
    errors = validate_result(entries, archives)
    if errors:
        raise ValueError('\n'.join(errors[:30]))
    output = Path(output).resolve()
    for a in archives:
        if file_hash(a.path) != a.digest:
            raise ValueError('输入文件已被其他程序修改，请重新加载：' + str(a.path))
    # Merged may equal Mine in SVN. Other inputs are immutable.
    if output in (archives[0].path, archives[2].path):
        raise ValueError('输出不能覆盖 BASE 或 THEIRS')
    output.parent.mkdir(parents=True, exist_ok=True)
    initial_hash = file_hash(output) if output.exists() else None
    fd, temporary = tempfile.mkstemp(prefix='.xd-merge-', suffix='.tmp', dir=output.parent)
    os.close(fd)
    backup = None
    try:
        with zipfile.ZipFile(temporary, 'w') as z:
            z.comment = archives[1].comment
            order = ['mimetype'] + [n for n in archives[1].entries if n != 'mimetype' and n in entries]
            order += sorted(entries.keys() - set(order))
            for name in order:
                info = next((a.infos[name] for a in (archives[1], archives[2], archives[0]) if name in a.infos), None)
                info = copy.copy(info) if info else zipfile.ZipInfo(name)
                if name == 'mimetype':
                    info.compress_type = zipfile.ZIP_STORED
                z.writestr(info, entries[name])
        verified = Archive.read(temporary)
        if verified.entries != entries:
            raise ValueError('写入校验失败')
        current_hash = file_hash(output) if output.exists() else None
        if current_hash != initial_hash:
            raise ValueError('保存期间输出文件发生变化，已取消覆盖')
        if output.exists():
            backup = output.with_name(output.name + '.' + time.strftime('%Y%m%d-%H%M%S') + '-' + str(time.time_ns())[-6:] + '.bak')
            shutil.copy2(output, backup)
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return backup

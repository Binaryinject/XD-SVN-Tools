"""Presentation-only aligned line diff. Never feeds text back to the merger."""
from dataclasses import dataclass
from difflib import SequenceMatcher
import re

@dataclass(frozen=True)
class Row:
    left: str
    right: str
    left_number: int | None
    right_number: int | None
    kind: str

def aligned_lines(left, right):
    a, b = left.splitlines(), right.splitlines()
    rows = []
    matcher = SequenceMatcher(None, a, b, autojunk=max(len(a), len(b)) > 10000)
    def key(line):
        match = re.match(r'^(\s*)("(?:\\.|[^"\\])*")\s*:', line)
        return ('key', match.group(1), match.group(2)) if match else ('text', line)
    def append(operation, start_a, end_a, start_b, end_b):
        for offset in range(max(end_a-start_a, end_b-start_b)):
            ai, bi = start_a+offset, start_b+offset
            has_a, has_b = ai < end_a, bi < end_b
            if has_a and has_b and key(a[ai])[0] == key(b[bi])[0] == 'key' and key(a[ai]) != key(b[bi]):
                rows.append(Row(a[ai], '', ai+1, None, 'delete'))
                rows.append(Row('', b[bi], None, bi+1, 'add'))
                continue
            kind = 'equal' if has_a and has_b and a[ai] == b[bi] else 'change' if has_a and has_b else 'delete' if has_a else 'add'
            rows.append(Row(a[ai] if has_a else '', b[bi] if has_b else '', ai+1 if has_a else None, bi+1 if has_b else None, kind))
    for operation, start_a, end_a, start_b, end_b in matcher.get_opcodes():
        if operation == 'replace':
            local = SequenceMatcher(None, [key(s) for s in a[start_a:end_a]], [key(s) for s in b[start_b:end_b]], autojunk=True)
            for op, i, j, k, l in local.get_opcodes():
                append(op, start_a+i, start_a+j, start_b+k, start_b+l)
        else:
            append(operation, start_a, end_a, start_b, end_b)
    return rows

def changed_spans(left, right):
    """Character emphasis within changed lines, bounded for long SVG/path data."""
    if max(len(left), len(right)) > 4000:
        return [], []
    a, b = [], []
    for operation, i, j, k, l in SequenceMatcher(None, left, right, autojunk=False).get_opcodes():
        if operation != 'equal':
            if i < j:
                a.append((i, j))
            if k < l:
                b.append((k, l))
    return a, b

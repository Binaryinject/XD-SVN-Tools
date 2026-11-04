"""Windows GUI / CLI entry point for XD SVN Tools."""
from __future__ import annotations
import argparse
import base64
import concurrent.futures
import json
import math
import os
from pathlib import Path
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import traceback
from xd_line_diff import aligned_lines, changed_spans
from xd_theme import style_widgets, read_preference, save_preference, resolve_theme, SYSTEM
from app_version import VERSION
from xd_core import Archive, MISSING, display, equal, diff_values, merge_archives, save_archive, validate_result

class App:
    def __init__(self, root, args):
        self.root, self.args = root, args
        self.exit_code = 1 if args.command == 'merge' else 0
        self.archives = []
        self.choices = {}
        self.items = {}
        self.conflict_items = {}
        self.images = []
        self.change_lines = []
        self.change_position = -1
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        root.title(f'XD SVN Tools {VERSION} · 对比与三方合并')
        root.geometry('1380x940')
        root.minsize(1120, 800)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.theme_name = tk.StringVar(value=read_preference())
        self.effective_theme = resolve_theme(self.theme_name.get())
        self.palette = style_widgets(root, self.effective_theme)
        outer = ttk.Frame(root, padding=20, style='App.TFrame')
        outer.pack(fill='both', expand=True)
        header = ttk.Frame(outer, style='App.TFrame')
        header.pack(fill='x', pady=(0, 18))
        self.brand = tk.Label(header, text='XD', font=('Segoe UI', 19, 'bold'), padx=13, pady=9, borderwidth=0)
        self.brand.pack(side='left', padx=(0, 14))
        heading = ttk.Frame(header, style='App.TFrame')
        heading.pack(side='left')
        ttk.Label(heading, text='XD 对比与合并', style='Header.TLabel').pack(anchor='w')
        ttk.Label(heading, text='看清每处变化，安心合并每次修改。', style='HeaderMuted.TLabel').pack(anchor='w', pady=(3, 0))
        theme_box = ttk.Frame(header, style='App.TFrame')
        theme_box.pack(side='right')
        ttk.Label(theme_box, text='v'+VERSION+'   /   外观', style='HeaderMuted.TLabel').pack(side='left', padx=10)
        self.theme_picker = ttk.Combobox(theme_box, textvariable=self.theme_name, values=[SYSTEM, '浅色', '深色'], state='readonly', width=10)
        self.theme_picker.pack(side='left')
        self.theme_picker.bind('<<ComboboxSelected>>', self.change_theme)
        self.paths = {}
        paths = ttk.Frame(outer, padding=(18, 14), style='Card.TFrame')
        paths.pack(fill='x')
        labels = [('base', 'BASE  ·  原始版本'), ('mine', 'MINE  ·  我的版本'), ('theirs', 'THEIRS  ·  对方版本'), ('merged', 'OUTPUT  ·  合并输出')]
        for row, (key, label) in enumerate(labels):
            ttk.Label(paths, text=label, width=21, style='Path.TLabel').grid(row=row, column=0, sticky='w', pady=5)
            variable = tk.StringVar(value=getattr(args, key, '') or '')
            self.paths[key] = variable
            ttk.Entry(paths, textvariable=variable).grid(row=row, column=1, sticky='ew', padx=(0, 10), pady=4)
            ttk.Button(paths, text='浏览…', command=lambda k=key: self.pick(k)).grid(row=row, column=2)
        paths.columnconfigure(1, weight=1)
        controls = ttk.Frame(outer, padding=(0, 12), style='App.TFrame')
        controls.pack(fill='x')
        self.diff_button = ttk.Button(controls, text='对比版本', style='Accent.TButton', command=lambda: self.load('diff'))
        self.diff_button.pack(side='left')
        self.merge_button = ttk.Button(controls, text='分析三方合并', command=lambda: self.load('merge'))
        self.merge_button.pack(side='left', padx=8)
        self.save_button = ttk.Button(controls, text='保存合并结果', style='Accent.TButton', state='disabled', command=self.save)
        self.save_button.pack(side='right')
        self.status = tk.StringVar(value='选择文件后开始。对比不需要填写 THEIRS 和输出路径。')
        overview = ttk.Frame(outer, padding=(14, 10), style='Card.TFrame')
        overview.pack(fill='x', pady=(0, 12))
        self.metric_labels = []
        self.metrics = [tk.StringVar(value=s+'  —') for s in ('自动合并', '待解决', '手动解决', '引用问题')]
        for variable in self.metrics:
            badge = tk.Label(overview, textvariable=variable, font=('Microsoft YaHei UI', 9, 'bold'), padx=10, pady=5)
            badge.pack(side='left', padx=(0, 8))
            self.metric_labels.append(badge)
        ttk.Label(overview, textvariable=self.status, style='Muted.TLabel', wraplength=680).pack(side='left', padx=(6, 0), fill='x', expand=True)
        self.notebook = ttk.Notebook(outer)
        self.notebook.pack(fill='both', expand=True)
        self.diff_frame = ttk.Frame(self.notebook)
        self.conflict_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.diff_frame, text='结构差异')
        self.notebook.add(self.conflict_frame, text='合并状态')
        self.build_diff()
        self.build_conflicts()
        self.apply_theme()
        self._theme_timer = root.after(1000, self.watch_system_theme)
        if args.command in ('diff', 'merge'):
            root.after(100, lambda: self.load(args.command))

    def change_theme(self, event=None):
        self.apply_theme()
        try:
            save_preference(self.theme_name.get())
        except OSError:
            pass

    def apply_theme(self):
        self.effective_theme = resolve_theme(self.theme_name.get())
        p = self.palette = style_widgets(self.root, self.effective_theme)
        self.brand.configure(background=p['brand'], foreground='#ffffff')
        for label, role in zip(self.metric_labels, ('add', 'delete', 'resolved', 'change')):
            label.configure(background=p[role+'_bg'], foreground=p[role+'_fg'])
        for view in self.diff_views + self.conflict_views:
            view.configure(background=p['code'], foreground=p['text'], insertbackground=p['text'], selectbackground=p['selection'], selectforeground=p['text'])
            for tag, role in [('add', 'add'), ('delete', 'delete'), ('change', 'change'), ('gap', 'gap'), ('inline', 'inline'), ('current', 'resolved')]:
                view.tag_configure(tag, background=p[role+'_bg'], foreground=p[role+'_fg'])
        for tag, role in [('automatic', 'add'), ('unresolved', 'delete'), ('resolved', 'resolved')]:
            self.conflict_tree.tag_configure(tag, background=p[role+'_bg'], foreground=p[role+'_fg'])

    def watch_system_theme(self):
        if self.theme_name.get() == SYSTEM and resolve_theme(SYSTEM) != self.effective_theme:
            self.apply_theme()
        self._theme_timer = self.root.after(1000, self.watch_system_theme)

    def build_diff(self):
        bar = ttk.Frame(self.diff_frame, padding=(12, 10))
        bar.pack(fill='x')
        ttk.Label(bar, text='比较范围：').pack(side='left')
        self.comparison = ttk.Combobox(bar, values=['BASE ↔ MINE', 'BASE ↔ THEIRS', 'BASE ↔ 合并结果'], state='readonly', width=24)
        self.comparison.current(0)
        self.comparison.pack(side='left')
        self.comparison.bind('<<ComboboxSelected>>', lambda e: self.refresh_diff())
        ttk.Button(bar, text='↑ 上一处', command=lambda: self.jump_change(-1)).pack(side='left', padx=(12, 3))
        ttk.Button(bar, text='↓ 下一处', command=lambda: self.jump_change(1)).pack(side='left')
        self.line_status = tk.StringVar(value='红：删除  绿：新增  黄：修改')
        ttk.Label(bar, textvariable=self.line_status).pack(side='left', padx=10)
        panes = ttk.Panedwindow(self.diff_frame, orient='horizontal')
        panes.pack(fill='both', expand=True)
        left = ttk.Frame(panes)
        panes.add(left, weight=2)
        self.diff_tree = ttk.Treeview(left, columns=('kind',), show='tree headings', selectmode='browse')
        self.diff_tree.heading('#0', text='文件 / 属性路径（@id 表示图层或节点）')
        self.diff_tree.heading('kind', text='变化')
        self.diff_tree.column('#0', width=310)
        self.diff_tree.column('kind', width=72, stretch=False)
        self.diff_tree.pack(side='left', fill='both', expand=True)
        scroll = ttk.Scrollbar(left, orient='vertical', command=self.diff_tree.yview)
        scroll.pack(side='right', fill='y')
        self.diff_tree.configure(yscrollcommand=scroll.set)
        self.diff_tree.bind('<<TreeviewSelect>>', self.show_diff)
        right = ttk.Frame(panes)
        panes.add(right, weight=3)
        self.diff_views = self.value_views(right, ['BASE / 原始版本', 'MINE / 我的版本'])
        self.link_scroll(self.diff_views)

    def link_scroll(self, views):
        def sync(source, first, last):
            source._vertical_scroll.set(first, last)
            if getattr(self, '_syncing_scroll', False):
                return
            self._syncing_scroll = True
            try:
                for other in views:
                    if other is not source and abs(other.yview()[0] - float(first)) > 0.00001:
                        other.yview_moveto(first)
            finally:
                self._syncing_scroll = False
        for view in views:
            view.configure(yscrollcommand=lambda first, last, v=view: sync(v, first, last))

    def value_views(self, parent, titles):
        panes = ttk.Panedwindow(parent, orient='horizontal')
        panes.pack(fill='both', expand=True)
        result = []
        for title in titles:
            frame = ttk.Labelframe(panes, text=title, padding=8)
            panes.add(frame, weight=1)
            text = tk.Text(frame, wrap='none', font=('Consolas', 11), undo=False, borderwidth=0, highlightthickness=0, padx=8, pady=8, spacing1=2, spacing3=2)
            vs = ttk.Scrollbar(frame, command=text.yview)
            text._vertical_scroll = vs
            hs = ttk.Scrollbar(frame, orient='horizontal', command=text.xview)
            text.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
            vs.pack(side='right', fill='y')
            hs.pack(side='bottom', fill='x')
            text.pack(fill='both', expand=True)
            text.configure(state='disabled')
            for tag, background, foreground in [('add', '#ddf5e3', '#145b2b'), ('delete', '#fce0df', '#922a29'), ('change', '#fff1c2', '#634600'), ('gap', '#e9edf2', '#677483'), ('inline', '#ffd36a', '#402b00'), ('current', '#d7eaff', '#123e71')]:
                text.tag_configure(tag, background=background, foreground=foreground)
            result.append(text)
        return result

    def build_conflicts(self):
        bar = ttk.Frame(self.conflict_frame, padding=(12, 10))
        bar.pack(fill='x')
        self.choice_buttons = []
        for key, title in [('base', '选 BASE'), ('mine', '选 MINE'), ('theirs', '选 THEIRS'), (None, '撤销当前选择')]:
            button = ttk.Button(bar, text=title, command=lambda k=key: self.choose(k))
            button.pack(side='left', padx=3)
            self.choice_buttons.append(button)
        ttk.Label(bar, text='绿：已自动合并   红：需解决冲突   蓝：已手动解决').pack(side='left', padx=10)
        list_frame = ttk.Frame(self.conflict_frame)
        list_frame.pack(fill='x')
        self.conflict_tree = ttk.Treeview(list_frame, columns=('choice', 'reason'), height=5, show='tree headings', selectmode='browse')
        self.conflict_tree.heading('#0', text='修改 / 冲突路径')
        self.conflict_tree.heading('choice', text='合并状态')
        self.conflict_tree.heading('reason', text='原因')
        self.conflict_tree.column('#0', width=600)
        self.conflict_tree.column('choice', width=180, stretch=False)
        self.conflict_tree.column('reason', width=320)
        self.conflict_tree.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.conflict_tree.yview)
        self.conflict_tree.configure(yscrollcommand=scrollbar.set)
        self.conflict_tree.tag_configure('automatic', background='#ddf5e3', foreground='#145b2b')
        self.conflict_tree.tag_configure('unresolved', background='#fce0df', foreground='#922a29')
        self.conflict_tree.tag_configure('resolved', background='#dcecff', foreground='#164b81')
        scrollbar.pack(side='right', fill='y')
        self.conflict_tree.bind('<<TreeviewSelect>>', self.show_conflict)
        self.conflict_views = self.value_views(self.conflict_frame, ['BASE', 'MINE', 'THEIRS'])

    def pick(self, key):
        if key == 'merged':
            path = filedialog.asksaveasfilename(title='合并结果', defaultextension='.xd', filetypes=[('Adobe XD', '*.xd')])
        else:
            path = filedialog.askopenfilename(title=key.upper(), filetypes=[('Adobe XD / SVN 临时文件', '*')])
        if path:
            self.paths[key].set(path)

    def work(self, function, done):
        self.diff_button.configure(state='disabled')
        self.merge_button.configure(state='disabled')
        self.save_button.configure(state='disabled')
        future = self.executor.submit(function)
        def poll():
            if not future.done():
                self.root.after(70, poll)
                return
            self.diff_button.configure(state='normal')
            self.merge_button.configure(state='normal')
            try:
                done(future.result())
            except Exception as ex:
                self.status.set('操作失败：' + str(ex))
                messagebox.showerror('XD SVN Tools', str(ex))
        self.root.after(70, poll)

    def load(self, mode):
        keys = ['base', 'mine', 'theirs'] if mode == 'merge' else ['base', 'mine']
        values = [self.paths[k].get().strip() for k in keys]
        if not all(values):
            messagebox.showinfo('选择文件', '请填写 ' + '、'.join(k.upper() for k, v in zip(keys, values) if not v))
            return
        self.mode = mode
        self.exit_code = 1 if mode == 'merge' else 0
        self.status.set('正在读取 XD 并分析结构…')
        self.archives = []
        self.choices = {}
        self.work(lambda: [Archive.read(p) for p in values], self.loaded)

    def loaded(self, archives):
        self.archives = archives
        self.comparison.current(0)
        self.refresh_diff()
        if self.mode == 'merge':
            self.recompute()
            self.notebook.select(self.conflict_frame)
        else:
            self.conflict_tree.delete(*self.conflict_tree.get_children())
            for variable, label in zip(self.metrics, ('自动合并', '待解决', '手动解决', '引用问题')):
                variable.set(label+'  —')
            self.status.set(self.diff_summary)
            self.notebook.select(self.diff_frame)

    def refresh_diff(self):
        if not self.archives:
            return
        self.diff_tree.delete(*self.diff_tree.get_children())
        self.items = {}
        b, m = self.archives[:2]
        index = self.comparison.current()
        if index == 1 and len(self.archives) == 3:
            m = self.archives[2]
        elif index == 2 and self.mode == 'merge' and hasattr(self, 'entries'):
            m = Archive(Path('candidate'), self.entries)
        elif index != 0:
            self.comparison.current(0)
        self.diff_views[1].master.configure(text=self.comparison.get().split(' ↔ ')[-1])
        count = 0
        for name in sorted(b.entries.keys() | m.entries.keys()):
            x, y = b.value(name), m.value(name)
            if equal(x, y):
                continue
            status = '新增' if x is MISSING else '删除' if y is MISSING else '修改'
            parent = self.diff_tree.insert('', 'end', text=name, values=(status,))
            self.items[parent] = (x, y)
            changes = diff_values(x, y)
            count += len(changes)
            for path, old, new in changes:
                item = self.diff_tree.insert(parent, 'end', text=path, values=('属性',))
                self.items[item] = (old, new)
            if len(changes) >= 5000:
                self.diff_tree.insert(parent, 'end', text='仅列出前 5000 项；父项显示完整内容')
        self.diff_summary = f'{self.comparison.get()}：{len(self.diff_tree.get_children())} 个文件、{count} 项差异'
        children = self.diff_tree.get_children()
        if children:
            self.diff_tree.selection_set(children[0])
        else:
            for view in self.diff_views:
                self.put(view, '没有结构差异。')
        if self.mode != 'merge':
            self.status.set(self.diff_summary)

    def put(self, view, text=None, value=MISSING):
        view.configure(state='normal')
        view.delete('1.0', 'end')
        if text is None:
            text = display(value)
        view.insert('end', text[:2_000_000])
        if len(text) > 2_000_000:
            view.insert('end', '\n…显示已截断，合并使用完整数据。')
        self.append_preview(view, value)
        view.configure(state='disabled')

    def append_preview(self, view, value):
        if isinstance(value, bytes) and value.startswith(b'\x89PNG'):
            try:
                img = tk.PhotoImage(data=base64.b64encode(value))
                scale = max(1, math.ceil(max(img.width() / 360, img.height() / 280)))
                img = img.subsample(scale)
                self.images.append(img)
                view.insert('end', '\n\n包内预览（可能未更新，不代表实时渲染）\n')
                view.image_create('end', image=img)
            except tk.TclError:
                pass

    def render_pair(self, left, right):
        a = '' if left is MISSING else display(left)
        b = '' if right is MISSING else display(right)
        truncated = max(len(a), len(b)) > 2_000_000
        rows = aligned_lines(a[:2_000_000], b[:2_000_000])
        self.change_lines = []
        self.change_position = -1
        for view in self.diff_views:
            view.configure(state='normal')
            view.delete('1.0', 'end')
        for line, row in enumerate(rows, 1):
            if row.kind != 'equal' and (line == 1 or rows[line-2].kind == 'equal'):
                self.change_lines.append(line)
            for side, view in enumerate(self.diff_views):
                number = row.left_number if side == 0 else row.right_number
                content = row.left if side == 0 else row.right
                marker = {'equal': ' ', 'change': '~', 'delete': '-', 'add': '+'}[row.kind]
                prefix = f'{number:6d} {marker}  ' if number is not None else '       ·  '
                view.insert('end', prefix + content + '\n')
                if row.kind != 'equal':
                    tag = row.kind if number is not None else 'gap'
                    view.tag_add(tag, f'{line}.0', f'{line+1}.0')
            if row.kind == 'change':
                for view, spans in zip(self.diff_views, changed_spans(row.left, row.right)):
                    for start, end in spans:
                        view.tag_add('inline', f'{line}.{10+start}', f'{line}.{10+end}')
        for view, value in zip(self.diff_views, (left, right)):
            if truncated:
                view.insert('end', '\n…显示已截断，合并使用完整数据。')
            self.append_preview(view, value)
            view.configure(state='disabled')
        self.line_status.set(f'红：删除  绿：新增  黄：修改  · {len(self.change_lines)} 处变化')
        if self.change_lines:
            self.jump_change(1)
        else:
            for view in self.diff_views:
                view.yview_moveto(0)

    def jump_change(self, direction):
        if not self.change_lines:
            return
        self.change_position = (self.change_position + direction) % len(self.change_lines)
        line = self.change_lines[self.change_position]
        for view in self.diff_views:
            view.see(f'{line}.0')
        self.line_status.set(f'红：删除  绿：新增  黄：修改  · {self.change_position+1}/{len(self.change_lines)} 处')

    def show_diff(self, event=None):
        selection = self.diff_tree.selection()
        if selection and selection[0] in self.items:
            self.images = []
            self.render_pair(*self.items[selection[0]])

    def recompute(self, selected_key=None):
        self.entries, self.engine = merge_archives(*self.archives, self.choices)
        if self.comparison.current() == 2:
            self.refresh_diff()
        self.conflict_tree.delete(*self.conflict_tree.get_children())
        self.conflict_items = {}
        selected = None
        for c in sorted(self.engine.conflicts, key=lambda c: c.key in self.choices):
            resolved = c.key in self.choices
            status = '已手动解决 · ' + self.choices[c.key].upper() if resolved else '需解决冲突'
            item = self.conflict_tree.insert('', 'end', text=c.key, values=(status, c.reason), tags=('resolved' if resolved else 'unresolved',))
            self.conflict_items[item] = c
            if c.key == selected_key:
                selected = item
        self.automatic_items = {}
        for action in self.engine.automatic:
            item = self.conflict_tree.insert('', 'end', text=action.key, values=('已自动合并', action.reason), tags=('automatic',))
            self.automatic_items[item] = action
        if selected is None:
            selected = next((i for i, c in self.conflict_items.items() if c.key not in self.choices), None)
        if selected is None and self.automatic_items:
            selected = next(iter(self.automatic_items))
        if selected is not None:
            self.conflict_tree.selection_set(selected)
            self.conflict_tree.see(selected)
        elif not self.engine.conflicts:
            for view in self.conflict_views:
                self.put(view, '没有需要人工选择的冲突。保存前可在“结构差异”查看 BASE 与 MINE。\n保存会执行基本结构和已知引用检查；仍需在 XD 中验收。')
        self.errors = validate_result(self.entries, self.archives)
        for variable, label, count in zip(self.metrics, ('自动合并', '待解决', '手动解决', '引用问题'), (len(self.engine.automatic), len(self.engine.unresolved), len(self.engine.conflicts)-len(self.engine.unresolved), len(self.errors))):
            variable.set(f'{label}  {count}')
        self.status.set(f'已自动合并 {len(self.engine.automatic)} 项 · 需解决冲突 {len(self.engine.unresolved)} 项 · 已手动解决 {len(self.engine.conflicts)-len(self.engine.unresolved)} 项 · 引用检查问题 {len(self.errors)} 项。')
        self.notebook.tab(self.conflict_frame, text=f'合并状态（{len(self.engine.unresolved)} 项待解决）')
        self.save_button.configure(state='normal' if not self.engine.unresolved and not self.errors else 'disabled')
        if self.errors:
            self.status.set(self.status.get() + ' 首项：' + self.errors[0])

    def show_conflict(self, event=None):
        sel = self.conflict_tree.selection()
        automatic = getattr(self, 'automatic_items', {})
        for button in self.choice_buttons:
            button.configure(state='normal' if sel and sel[0] in self.conflict_items else 'disabled')
        if sel and (sel[0] in self.conflict_items or sel[0] in automatic):
            c = self.conflict_items.get(sel[0]) or automatic[sel[0]]
            self.images = []
            for view, value in zip(self.conflict_views, (c.base, c.mine, c.theirs)):
                self.put(view, value=value)

    def choose(self, choice):
        if len(self.archives) != 3 or self.mode != 'merge':
            return
        sel = self.conflict_tree.selection()
        if not sel or sel[0] not in self.conflict_items:
            return
        key = self.conflict_items[sel[0]].key
        if choice is None:
            self.choices.pop(key, None)
        else:
            self.choices[key] = choice
        self.recompute(selected_key=key if choice is None else None)

    def save(self):
        if self.engine.unresolved or self.errors:
            return
        output = self.paths['merged'].get().strip()
        if not output:
            self.pick('merged')
            output = self.paths['merged'].get().strip()
        if not output:
            return
        if not messagebox.askokcancel('保存合并结果', '即将生成合并后的 XD。若输出已存在，将保留 .bak 备份。\n\n本工具只做结构与部分引用校验，不能保证 XD 全部语义兼容。请在 XD 中打开、检查组件与交互、另存后再在 SVN 标记解决。\n\n继续保存？'):
            return
        self.status.set('正在保存并验证压缩包…')
        self.work(lambda: save_archive(self.entries, self.archives, output), lambda backup: self.saved(output, backup))

    def saved(self, output, backup):
        self.exit_code = 0
        self.status.set('已保存：' + output)
        messagebox.showinfo('已保存合并文件', '已保存：' + output + ('\n备份：' + str(backup) if backup else '') + '\n\n请在 XD 中打开验证。工具不会自动标记 SVN 冲突已解决。')
        self.root.destroy()

    def close(self):
        if self.mode_is_merge() and self.archives and self.exit_code != 0:
            if not messagebox.askyesno('取消合并', '尚未保存合并结果。关闭后保留原文件和 SVN 冲突状态，继续关闭？'):
                return
        self.root.destroy()

    def mode_is_merge(self):
        return getattr(self, 'mode', self.args.command) == 'merge'

def parser():
    p = argparse.ArgumentParser(description='XD SVN Tools ' + VERSION)
    sub = p.add_subparsers(dest='command')
    d = sub.add_parser('diff', help='打开两方差异界面')
    d.add_argument('--base', required=True)
    d.add_argument('--mine', required=True)
    m = sub.add_parser('merge', help='打开三方合并界面；保存成功返回 0，取消返回 1')
    for key in ('base', 'mine', 'theirs', 'merged'):
        m.add_argument('--' + key, required=True)
    e = sub.add_parser('extract', help='将包内 JSON 结构导出到一个 JSON 文件')
    e.add_argument('input')
    e.add_argument('output')
    c = sub.add_parser('check', help='无界面分析，输出 JSON 报告；冲突返回 1，错误返回 2')
    for key in ('base', 'mine', 'theirs', 'report'):
        c.add_argument('--' + key, required=True)
    return p

def main():
    args = parser().parse_args()
    if args.command in ('extract', 'check'):
        try:
            if args.command == 'extract':
                a = Archive.read(args.input)
                output = Path(args.output).resolve()
                if output == a.path:
                    raise ValueError('导出文件不能覆盖输入 XD')
                report = {n: a.value(n) for n in a.entries if n.endswith(('.agc', '.json')) or n == 'manifest'}
                code = 0
            else:
                archives = [Archive.read(getattr(args, k)) for k in ('base', 'mine', 'theirs')]
                output = Path(args.report).resolve()
                if output in [a.path for a in archives]:
                    raise ValueError('报告不能覆盖输入 XD')
                entries, engine = merge_archives(*archives)
                errors = validate_result(entries, archives)
                report = {'version': VERSION, 'automatic_merges': [{'path': a.key, 'reason': a.reason} for a in engine.automatic], 'conflicts': [{'path': c.key, 'reason': c.reason, 'status': '需解决冲突'} for c in engine.conflicts], 'validation_errors': errors}
                code = 1 if engine.unresolved or errors else 0
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            return code
        except Exception as ex:
            if sys.stderr:
                print(str(ex), file=sys.stderr)
            return 2
    root = tk.Tk()
    app = App(root, args)
    root.mainloop()
    app.executor.shutdown(wait=True)
    return app.exit_code

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        error = traceback.format_exc()
        if sys.stderr:
            print(error, file=sys.stderr)
        else:
            messagebox.showerror('XD SVN Tools', error)
        sys.exit(2)

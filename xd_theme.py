"""Native ttk skins; no external theme/runtime dependency."""
import json
import os
from pathlib import Path
from tkinter import ttk

SYSTEM = '跟随系统'

def system_theme():
    """Read Windows app appearance without changing system settings."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize') as key:
            value, _ = winreg.QueryValueEx(key, 'AppsUseLightTheme')
        return '深色' if value == 0 else '浅色'
    except (ImportError, OSError):
        return '浅色'

def resolve_theme(mode):
    return mode if mode in PALETTES else system_theme()

PALETTES = {
    '浅色': dict(bg='#f2f5fa', panel='#ffffff', text='#19263d', muted='#6c7a90', border='#dce3ee',
        accent='#5269e8', hover='#4057d5', soft='#eaf0ff', disabled='#edf1f7', disabled_fg='#9ca8bb',
        code='#fbfcfe', selection='#dfe8ff', scroll='#c4cede', brand='#6657dc',
        add_bg='#e2f5e9', add_fg='#246b42', delete_bg='#fce8e8', delete_fg='#a33b45',
        change_bg='#fff3ce', change_fg='#855f18', gap_bg='#eef1f6', gap_fg='#8a96a8',
        inline_bg='#ffda7b', inline_fg='#684609', resolved_bg='#e4edff', resolved_fg='#385dae'),
    '深色': dict(bg='#121925', panel='#1b2535', text='#e4ebf7', muted='#99a8bf', border='#344258',
        accent='#8294ff', hover='#a1afff', soft='#293956', disabled='#253043', disabled_fg='#738198',
        code='#172130', selection='#34496c', scroll='#4d5f7b', brand='#7865e9',
        add_bg='#203e35', add_fg='#9cddba', delete_bg='#492c38', delete_fg='#f0acb8',
        change_bg='#463e27', change_fg='#edd391', gap_bg='#232e40', gap_fg='#8592a8',
        inline_bg='#755b28', inline_fg='#fff0ba', resolved_bg='#273b59', resolved_fg='#a9c7ff'),
}

def preference_path():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'XD-SVN-Tools' / 'appearance.json'

def read_preference():
    try:
        # v0.1.2 preferences had only 'theme'; migrate once to the new default.
        name = json.loads(preference_path().read_text(encoding='utf-8')).get('mode')
        return name if name in (*PALETTES, SYSTEM) else SYSTEM
    except (OSError, ValueError, TypeError, AttributeError):
        return SYSTEM

def save_preference(name):
    path = preference_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'mode': name}, ensure_ascii=False), encoding='utf-8')

def style_widgets(root, name):
    p = PALETTES[name]
    s = ttk.Style(root)
    s.theme_use('clam')
    root.configure(background=p['bg'])
    s.configure('.', font=('Microsoft YaHei UI', 10), background=p['panel'], foreground=p['text'], bordercolor=p['border'], lightcolor=p['border'], darkcolor=p['border'], troughcolor=p['panel'], focuscolor=p['accent'])
    s.configure('TFrame', background=p['panel'])
    s.configure('App.TFrame', background=p['bg'])
    s.configure('Card.TFrame', background=p['panel'], relief='flat')
    s.configure('TLabel', background=p['panel'], foreground=p['text'])
    s.configure('Header.TLabel', background=p['bg'], foreground=p['text'], font=('Microsoft YaHei UI', 20, 'bold'))
    s.configure('HeaderMuted.TLabel', background=p['bg'], foreground=p['muted'], font=('Microsoft YaHei UI', 9))
    s.configure('Muted.TLabel', foreground=p['muted'], font=('Microsoft YaHei UI', 9))
    s.configure('Path.TLabel', foreground=p['muted'], font=('Microsoft YaHei UI', 9, 'bold'))
    s.configure('TEntry', fieldbackground=p['code'], foreground=p['text'], padding=(10, 7), borderwidth=1, lightcolor=p['border'], darkcolor=p['border'], insertcolor=p['text'])
    s.map('TEntry', bordercolor=[('focus', p['accent'])])
    s.configure('TCombobox', fieldbackground=p['code'], background=p['code'], foreground=p['text'], arrowcolor=p['muted'], padding=(8, 6), borderwidth=1)
    s.map('TCombobox', fieldbackground=[('readonly', p['code'])], foreground=[('readonly', p['text'])], selectbackground=[('readonly', p['code'])], selectforeground=[('readonly', p['text'])])
    s.configure('TButton', background=p['panel'], foreground=p['text'], padding=(12, 7), borderwidth=1, bordercolor=p['border'], lightcolor=p['border'], darkcolor=p['border'], relief='flat')
    s.map('TButton', background=[('disabled', p['disabled']), ('pressed', p['selection']), ('active', p['soft'])], foreground=[('disabled', p['disabled_fg'])], bordercolor=[('active', p['accent'])])
    s.configure('Accent.TButton', background=p['accent'], foreground='#ffffff' if name == '浅色' else '#111b31', bordercolor=p['accent'], font=('Microsoft YaHei UI', 10, 'bold'))
    s.map('Accent.TButton', background=[('disabled', p['disabled']), ('pressed', p['hover']), ('active', p['hover'])], foreground=[('disabled', p['disabled_fg'])], bordercolor=[('disabled', p['disabled']), ('active', p['hover'])])
    s.configure('TNotebook', background=p['panel'], borderwidth=0, tabmargins=(0, 0, 0, 0))
    s.configure('TNotebook.Tab', background=p['panel'], foreground=p['muted'], padding=(18, 10), borderwidth=0)
    s.map('TNotebook.Tab', background=[('selected', p['soft']), ('active', p['soft'])], foreground=[('selected', p['accent'])])
    s.configure('Treeview', background=p['panel'], fieldbackground=p['panel'], foreground=p['text'], rowheight=32, borderwidth=0)
    s.configure('Treeview.Heading', background=p['code'], foreground=p['muted'], relief='flat', padding=(8, 9), font=('Microsoft YaHei UI', 9, 'bold'))
    s.map('Treeview', background=[('selected', p['selection'])], foreground=[('selected', p['text'])])
    s.map('Treeview.Heading', background=[('active', p['soft'])])
    s.configure('TLabelframe', background=p['panel'], bordercolor=p['border'], borderwidth=1, relief='solid')
    s.configure('TLabelframe.Label', background=p['panel'], foreground=p['muted'], font=('Microsoft YaHei UI', 9, 'bold'))
    s.configure('TPanedwindow', background=p['border'], sashwidth=6)
    for direction in ('Vertical', 'Horizontal'):
        s.configure(direction+'.TScrollbar', background=p['scroll'], troughcolor=p['panel'], bordercolor=p['panel'], lightcolor=p['panel'], darkcolor=p['panel'], borderwidth=0, arrowsize=12, arrowcolor=p['muted'], relief='flat')
        s.map(direction+'.TScrollbar', background=[('active', p['muted'])])
    root.option_add('*TCombobox*Listbox.background', p['panel'])
    root.option_add('*TCombobox*Listbox.foreground', p['text'])
    root.option_add('*TCombobox*Listbox.selectBackground', p['selection'])
    root.option_add('*TCombobox*Listbox.selectForeground', p['text'])
    return p

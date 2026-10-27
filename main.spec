# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, copy_metadata


datas = [('schema', 'schema')]
datas += [
    ('config/complex_actions.json', 'config'),
    ('config/aiedu_config.example.json', 'config'),
]
datas += collect_data_files('prefixcommons')
datas += collect_data_files('prefixmaps')
datas += collect_data_files('linkml_runtime')
datas += collect_data_files('linkml')
# These packages load schemas through importlib.resources, including extensionless
# vocabulary files. Python import analysis alone does not collect those resources.
datas += collect_data_files('openapi_schema_validator', includes=['schemas/**'])
datas += collect_data_files('openapi_spec_validator', includes=['resources/schemas/**'])
datas += copy_metadata('prefixcommons')
datas += copy_metadata('prefixmaps')
datas += copy_metadata('linkml_runtime')
datas += copy_metadata('linkml')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['rth_fix_metadata.py'],
    # Optional console editing/history; Qt Widgets handles the application's input.
    # Exclude the Python extension so dependency analysis can omit GNU Readline too.
    excludes=['readline'],
    noarchive=False,
    optimize=0,
)
# QtGui's hook collects all platforminputcontexts plugins. LabProGen uses desktop
# Widgets input, not Qt Virtual Keyboard (GPLv3/commercial). Filter this module's
# plugin, native libraries, framework paths and data from the final TOCs on all
# platforms, retaining the other input contexts and all other Qt dependencies.
# Filtering only Python imports would leave the dynamically loaded plugin behind.
a.binaries = [entry for entry in a.binaries if 'virtualkeyboard' not in entry[0].lower()]
a.datas = [entry for entry in a.datas if 'virtualkeyboard' not in entry[0].lower()]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

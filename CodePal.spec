# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['run.py'],
    pathex=['E:/deepseek/zuoye/1103'],
    binaries=[],
    datas=[('E:/deepseek/zuoye/1103/codepal/web', 'codepal/web')],
    hiddenimports=['codepal', 'codepal.server', 'codepal.agent', 'codepal.llm', 'codepal.mcp', 'codepal.tools', 'codepal.config', 'codepal.main'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CodePal',
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

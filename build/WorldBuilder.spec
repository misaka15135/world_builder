# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('D:/TongJi_Bache/RIKA/world_builder/web', 'web'), ('D:/TongJi_Bache/RIKA/world_builder/schemas', 'schemas'), ('D:/TongJi_Bache/RIKA/world_builder/storage/migrations', 'storage/migrations'), ('D:/TongJi_Bache/RIKA/world_builder/config/agents.example.json', 'config'), ('D:/TongJi_Bache/RIKA/world_builder/examples/agent_scene.responses.json', 'examples'), ('D:/TongJi_Bache/RIKA/world_builder/desktop/world-builder.ico', 'desktop'), ('D:/TongJi_Bache/RIKA/world_builder/skills/world-agent-a', 'skills/world-agent-a'), ('D:/TongJi_Bache/RIKA/world_builder/skills/world-agent-b', 'skills/world-agent-b'), ('D:/TongJi_Bache/RIKA/world_builder/skills/world-agent-c', 'skills/world-agent-c'), ('D:/TongJi_Bache/RIKA/world_builder/skills/world-agent-d', 'skills/world-agent-d'), ('D:/TongJi_Bache/RIKA/world_builder/skills/world-agent-e', 'skills/world-agent-e'), ('D:/TongJi_Bache/RIKA/world_builder/skills/world-agent-f', 'skills/world-agent-f')]
binaries = []
hiddenimports = []
tmp_ret = collect_all('webview')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['D:/TongJi_Bache/RIKA/world_builder/tools/run_desktop.py'],
    pathex=['D:/TongJi_Bache/RIKA/world_builder/src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt5', 'PySide6'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WorldBuilder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['D:/TongJi_Bache/RIKA/world_builder/desktop/world-builder.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WorldBuilder',
)

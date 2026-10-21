# -*- mode: python ; coding: utf-8 -*-
# Lean sidecar: only pandas/openpyxl stack (exclude ML/vision packages from global env).

block_cipher = None

excludes = [
    "torch",
    "torchvision",
    "torchaudio",
    "sklearn",
    "scikit-learn",
    "cv2",
    "tensorflow",
    "keras",
    "matplotlib",
    "scipy",
    "sympy",
    "IPython",
    "notebook",
    "jupyter",
    "pytest",
    "timm",
    "faiss",
    "opentelemetry",
    "grpc",
    "av",
    "PIL",
    "tkinter",
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[],
    hiddenimports=[
        "pandas",
        "openpyxl",
        "xlrd",
        "numpy",
        "merge_engine",
        "distribution_engine",
        "schema_engine",
        "session_store",
        "session_analysis",
        "limit_engine",
        "report_builder",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
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
    name="excelmerger-engine",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

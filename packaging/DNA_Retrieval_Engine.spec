from pathlib import Path
import os


spec_location = Path(SPECPATH).resolve()
project_root = spec_location.parent.parent if spec_location.is_file() else spec_location.parent
source_root = project_root / "src"
web_root = source_root / "dna_retrieval_engine" / "resources" / "web"
onefile = os.environ.get("DNA_BUILD_MODE", "onefile") == "onefile"
product_name = "DNA_Retrieval_Engine" if onefile else "DNA_Retrieval_Engine_onedir"

a = Analysis(
    [str(project_root / "app.py")],
    pathex=[str(source_root)],
    binaries=[],
    datas=[(str(web_root), "dna_retrieval_engine/resources/web")],
    hiddenimports=["webview.platforms.edgechromium"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "cefpython3", "tkinter"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

if onefile:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=product_name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        icon=str(project_root / "icon.ico"),
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=product_name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        icon=str(project_root / "icon.ico"),
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        name=product_name,
    )

# PyInstaller spec: builds two one-file executables.
#   IEVR.exe              -> the PySide6 GUI (windowed)
#   capture_templates.exe -> interactive setup helper (console)
# profiles/ and templates/ are NOT bundled; build_exe.py copies them next to
# the exes so they stay user-editable.
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

# vgamepad ships ViGEmClient.dll as package data; make sure it is bundled.
vg_datas = collect_data_files("vgamepad")
vg_bins = collect_dynamic_libs("vgamepad")

# RapidOCR: bundle ONNX models, config files, and hidden imports.
_rapidocr_datas = collect_data_files("rapidocr_onnxruntime")
_rapidocr_hidden = collect_submodules("rapidocr_onnxruntime") + collect_submodules("onnxruntime")

_EXCLUDES = ["pytest", "tkinter"]


def _analysis(script, extra_datas=(), extra_bins=(), extra_hidden=()):
    return Analysis(
        [script],
        pathex=["."],
        binaries=list(extra_bins),
        datas=list(extra_datas),
        hiddenimports=list(extra_hidden),
        hookspath=[],
        runtime_hooks=[],
        excludes=_EXCLUDES,
        noarchive=False,
    )


gui_a = _analysis(
    "run_gui.py",
    extra_datas=list(vg_datas) + list(_rapidocr_datas),
    extra_bins=vg_bins,
    extra_hidden=_rapidocr_hidden,
)
gui_pyz = PYZ(gui_a.pure)
gui_exe = EXE(
    gui_pyz, gui_a.scripts, gui_a.binaries, gui_a.datas, [],
    name="IEVR",
    console=False,
    disable_windowed_traceback=False,
    upx=False,
)

cap_a = _analysis("tools/capture_templates.py")
cap_pyz = PYZ(cap_a.pure)
cap_exe = EXE(
    cap_pyz, cap_a.scripts, cap_a.binaries, cap_a.datas, [],
    name="capture_templates",
    console=True,
    upx=False,
)

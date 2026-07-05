# PyInstaller spec: builds ONE self-contained executable.
#   IEVR.exe -> the PySide6 GUI (windowed), with setup built in (Templates tab).
# profiles/ and the OCR models are bundled INSIDE the exe (read-only). Captured
# templates and logs are written at runtime under %LOCALAPPDATA%\IEVR, so the
# exe ships as a single file with nothing beside it.
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

# vgamepad ships ViGEmClient.dll as package data; make sure it is bundled.
vg_datas = collect_data_files("vgamepad")
vg_bins = collect_dynamic_libs("vgamepad")

# RapidOCR: bundle ONNX models, config files, and hidden imports.
_rapidocr_datas = collect_data_files("rapidocr_onnxruntime")
_rapidocr_hidden = collect_submodules("rapidocr_onnxruntime") + collect_submodules("onnxruntime")

# Bundle the default profiles read-only inside the exe (paths.profiles_dir()
# reads them from sys._MEIPASS when frozen). Assets carry the window icon/logo.
_profile_datas = [("profiles", "profiles"), ("assets", "assets")]

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
    extra_datas=list(vg_datas) + list(_rapidocr_datas) + _profile_datas,
    extra_bins=vg_bins,
    extra_hidden=_rapidocr_hidden,
)
gui_pyz = PYZ(gui_a.pure)
gui_exe = EXE(
    gui_pyz, gui_a.scripts, gui_a.binaries, gui_a.datas, [],
    name="IEVR",
    icon="assets/icon.ico",
    console=False,
    disable_windowed_traceback=False,
    upx=False,
)

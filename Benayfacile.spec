# -*- mode: python ; coding: utf-8 -*-
# Construction : python -m PyInstaller --noconfirm Benayfacile.spec   (voir build_exe.bat)
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hidden = (
    ["robot_service", "engine_service", "dxf_service", "report_service", "common", "app"]
    + collect_submodules("uvicorn")
    + ["win32com", "win32com.client", "pythoncom", "pywintypes"]   # pilotage Robot (si pywin32 installé)
)

a = Analysis(
    ["bnayfacile_app.py"],
    pathex=["services", "gateway"],
    datas=[
        ("gateway/static", "static"),          # tableau de bord (gateway: HERE / "static")
        ("referentiels", "referentiels"),      # bael.json, rps.json, bureau.json par défaut
        ("examples", "examples"),
    ] + collect_data_files("ezdxf"),
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "pytest", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="Benayfacile",
    console=True,           # fenêtre console = journal + fermeture = arrêt propre
    upx=False,
    onefile=True,
)

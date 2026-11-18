# -*- mode: python ; coding: utf-8 -*-
# Application de bureau Bénayfacile — construction : build_exe.bat
#   dist\Benayfacile\Benayfacile.exe   (dossier complet, démarrage rapide)
#   installer\Benayfacile-Setup-x.y.z.exe   (installateur Inno Setup)
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hidden = (
    ["robot_service", "robot_ossature", "excel_report", "engine_service", "dxf_service", "report_service", "common", "app"]
    + collect_submodules("uvicorn")
    + collect_submodules("webview")                                   # fenêtre native (pywebview)
    + ["win32com", "win32com.client", "pythoncom", "pywintypes"]      # pilotage Robot (si pywin32 installé)
)

a = Analysis(
    ["bnayfacile_app.py"],
    pathex=["services", "gateway"],
    datas=[
        ("gateway/static", "static"),          # tableau de bord (gateway: HERE / "static")
        ("referentiels", "referentiels"),      # bael.json, rps.json, bureau.json par défaut
        ("examples", "examples"),
    ] + collect_data_files("ezdxf") + collect_data_files("webview"),
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "pytest", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,      # mode dossier : pas de décompression à chaque lancement
    name="Benayfacile",
    console=False,              # application fenêtrée : aucune console pour l'utilisateur
    icon="assets/benayfacile.ico",
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Benayfacile", upx=False)

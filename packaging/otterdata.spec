# PyInstaller spec for the Otter Data desktop app (Windows, one-folder build).
# Build: pyinstaller packaging/otterdata.spec --noconfirm   ->  dist/OtterData/OtterData.exe
# The installer (packaging/installer.iss) wraps dist/OtterData into a setup .exe.

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent  # noqa: F821 (SPECPATH is defined by PyInstaller)

datas = [
    (str(ROOT / "frontend"), "frontend"),
    (str(ROOT / "backend" / "semantic"), "backend/semantic"),
    (str(ROOT / "desktop" / "splash.html"), "desktop"),
    *collect_data_files("tzdata"),  # zoneinfo on Windows has no system time zone database
]

# Loaded by name at run time: uvicorn workers, keyring backends, LangGraph internals, the
# SQL dialects sqlglot imports lazily (postgres, mysql, duckdb), and the DNS record types
# pymongo needs for MongoDB Atlas (mongodb+srv) hosts.
hiddenimports = [
    *collect_submodules("uvicorn"),
    *collect_submodules("sqlglot.dialects"),
    *collect_submodules("keyring.backends"),
    *collect_submodules("langgraph"),
    *collect_submodules("pymongo"),
    *collect_submodules("dns"),
    "backend.main",
    "backend.runtime",
]

a = Analysis(  # noqa: F821
    [str(ROOT / "desktop" / "__main__.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "ruff", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OtterData",
    icon=str(ROOT / "frontend" / "assets" / "otter.ico"),
    console=False,
    version=None,
)
coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    name="OtterData",
)

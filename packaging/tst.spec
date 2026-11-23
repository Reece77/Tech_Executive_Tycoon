# PyInstaller spec for the installed game (M58 sub-task 3). Build from the repository root,
# after `pnpm build` in frontend/:
#
#     uv run --project backend --group desktop --group packaging \
#         pyinstaller packaging/tst.spec --noconfirm --distpath packaging/dist --workpath packaging/build
#
# The result is a folder (`packaging/dist/Tech Startup Tycoon/`) holding `Tech Startup
# Tycoon.exe` and `_internal/` (Python, the backend, the data YAML, the migrations and the
# built front end); packaging/installer.iss turns it into the installer. Nothing from `.env`,
# `saves/` or the user's folders is ever bundled.
# ruff: noqa
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
BACKEND = ROOT / "backend"
DIST = ROOT / "frontend" / "dist"
NAME = "Tech Startup Tycoon"

if not (DIST / "index.html").is_file():
    raise SystemExit("frontend/dist is missing: run `pnpm build` in frontend/ first")

datas = [
    (str(BACKEND / "data"), "data"),
    (str(BACKEND / "migrations" / "env.py"), "migrations"),
    (str(BACKEND / "migrations" / "script.py.mako"), "migrations"),
    (str(BACKEND / "migrations" / "versions"), "migrations/versions"),
    (str(DIST), "frontend"),
]
version = ROOT / "packaging" / "version.txt"  # written by the release workflow
if version.is_file():
    datas.append((str(version), "."))
datas += collect_data_files("webview")

hiddenimports = (
    collect_submodules("tst")
    + collect_submodules("uvicorn")
    + collect_submodules("alembic")
    + ["sqlalchemy.dialects.sqlite"]
)

a = Analysis(
    [str(BACKEND / "tst" / "desktop" / "__main__.py")],
    pathex=[str(BACKEND)],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "hypothesis", "mypy", "ruff", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=NAME,
    icon=str(ROOT / "packaging" / "icon.ico"),
    console=False,  # a window application: no console window behind the game
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name=NAME, upx=False)

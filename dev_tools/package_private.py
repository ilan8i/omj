# This Python file uses the following encoding: utf-8
"""把 Cython 编译产物打包成私有发行目录/zip。

前提：先运行 python dev_tools/cython_build.py
输出：
    dist/private/...
    dist/OAS-private-<version>.zip
"""
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from private_modules import MODULES

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "private"
ZIP_DIR = ROOT / "dist"

EXCLUDE_PREFIXES = (
    ".git/",
    ".github/",
    ".claude/",
    ".agents/",
    "tests/",
    "config/",
    "log/",
    "data/",
    "dev_tools/",
    "build/",
    "dist/",
    ".update/",
)
EXCLUDE_FILES = {".env", "VERSION"}

SCRIPT_STUB = """# This Python file uses the following encoding: utf-8
from script import Script

if __name__ == "__main__":
    from module.image.rpc import ensure_image_server_ready
    from module.ocr.rpc import ensure_ocr_server_ready

    ensure_image_server_ready()
    ensure_ocr_server_ready()
    Script("oas1").loop()
"""

SERVER_STUB = """# This Python file uses the following encoding: utf-8
from server import fun

if __name__ == "__main__":
    fun(None)
"""


def _git_files() -> list[str]:
    output = subprocess.check_output(
        ["git", "-C", str(ROOT), "ls-files", "-z"]
    )
    return [item.decode("utf-8") for item in output.split(b"\x00") if item]


def _compiled_artifacts(source: str) -> list[Path]:
    path = ROOT / source
    stem = path.stem
    artifacts = []
    for suffix in ("pyd", "so"):
        artifacts.extend(path.parent.glob(f"{stem}.*.{suffix}"))
    return artifacts


def main() -> int:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    compiled_sources = set(MODULES)
    copied = 0
    for relative in _git_files():
        normalized = relative.replace("\\", "/")
        if normalized in compiled_sources:
            continue
        if normalized in EXCLUDE_FILES:
            continue
        if any(normalized.startswith(prefix) for prefix in EXCLUDE_PREFIXES):
            continue
        source = ROOT / relative
        if not source.is_file():
            continue
        target = OUTPUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1

    missing = []
    for source in MODULES:
        artifacts = _compiled_artifacts(source)
        if not artifacts:
            missing.append(source)
            continue
        for artifact in artifacts:
            target = OUTPUT / artifact.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(artifact, target)
            copied += 1
    if missing:
        print("缺少编译产物，请先运行 cython_build.py：", file=sys.stderr)
        for item in missing:
            print(f"  {item}", file=sys.stderr)
        return 1

    (OUTPUT / "script.py").write_text(SCRIPT_STUB, encoding="utf-8")
    (OUTPUT / "server.py").write_text(SERVER_STUB, encoding="utf-8")

    version = datetime.now().strftime("%Y%m%d-%H%M%S")
    zip_path = ZIP_DIR / f"OAS-private-{version}.zip"
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(OUTPUT.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(OUTPUT).as_posix())

    print(f"files: {copied}")
    print(f"private dir: {OUTPUT}")
    print(f"zip: {zip_path} ({zip_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

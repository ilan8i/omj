# This Python file uses the following encoding: utf-8
"""用 Cython 编译敏感模块。

用法：
    python dev_tools/cython_build.py
    python dev_tools/cython_build.py --check

生成物：
    script.cp310-win_amd64.pyd
    server.cp310-win_amd64.pyd
    module/license/*.cp310-win_amd64.pyd
    module/server/license_router.cp310-win_amd64.pyd

需要在 Windows + MSVC 环境（或 GitHub Actions windows-latest）执行。
"""
import sys
from pathlib import Path

from Cython.Build import cythonize
from setuptools import Extension, setup

from private_modules import MODULES

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if "--check" in sys.argv:
        print(f"root: {ROOT}")
        for source in MODULES:
            print(source)
        return 0

    extensions = [
        Extension(
            name=source[:-3].replace("/", "."),
            sources=[str(ROOT / source)],
        )
        for source in MODULES
    ]
    setup(
        name="omj-private-build",
        ext_modules=cythonize(
            extensions,
            build_dir=str(ROOT / "build" / "cython"),
            compiler_directives={"language_level": "3"},
            quiet=True,
        ),
        script_args=["build_ext", "--inplace"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

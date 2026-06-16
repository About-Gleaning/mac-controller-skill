#!/usr/bin/env python3
"""启动 Swift/EventKit 提醒事项 CLI，并保持原有 Python 命令入口。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / ".build" / "release" / "reminders-cli"


def 输出(success: bool, message: str, code: int) -> None:
    print(
        json.dumps(
            {"success": success, "data": {}, "message": message},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    raise SystemExit(code)


def build_if_needed() -> None:
    if BINARY.exists():
        return
    env = os.environ.copy()
    module_cache = ROOT / ".build" / "module-cache"
    module_cache.mkdir(parents=True, exist_ok=True)
    env["CLANG_MODULE_CACHE_PATH"] = str(module_cache)
    env["SWIFTPM_MODULECACHE_OVERRIDE"] = str(module_cache)
    result = subprocess.run(
        ["swift", "build", "-c", "release", "--product", "reminders-cli"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = " ".join((result.stderr or result.stdout).strip().split())
        if not detail:
            detail = "Swift 构建失败。"
        输出(False, detail, result.returncode)


def main() -> None:
    if not sys.platform == "darwin":
        输出(False, "提醒事项控制仅支持 macOS。", 1)
    build_if_needed()
    env = os.environ.copy()
    result = subprocess.run([str(BINARY), *sys.argv[1:]], env=env, check=False)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()

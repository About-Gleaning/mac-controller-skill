#!/usr/bin/env python3
"""启动 Swift/UserNotifications 通知 CLI，并提供稳定 Python 命令入口。"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / ".build" / "release" / "notifications-cli"
INFO_PLIST = ROOT / "Sources" / "NotificationsCLI" / "Info.plist"
APP = ROOT / ".build" / "release" / "notifications-cli.app"
APP_BINARY = APP / "Contents" / "MacOS" / "notifications-cli"
APP_INFO_PLIST = APP / "Contents" / "Info.plist"


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
    if BINARY.exists() and not source_is_newer_than_binary():
        return
    env = os.environ.copy()
    module_cache = ROOT / ".build" / "module-cache"
    module_cache.mkdir(parents=True, exist_ok=True)
    env["CLANG_MODULE_CACHE_PATH"] = str(module_cache)
    env["SWIFTPM_MODULECACHE_OVERRIDE"] = str(module_cache)
    result = subprocess.run(
        ["swift", "build", "-c", "release", "--product", "notifications-cli"],
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


def source_is_newer_than_binary() -> bool:
    sources = [
        ROOT / "Package.swift",
        ROOT / "Sources" / "NotificationCore" / "NotificationCore.swift",
        ROOT / "Sources" / "NotificationsCLI" / "main.swift",
        INFO_PLIST,
    ]
    binary_mtime = BINARY.stat().st_mtime
    return any(path.stat().st_mtime > binary_mtime for path in sources)


def ensure_app_bundle() -> None:
    contents = APP / "Contents"
    macos = contents / "MacOS"
    macos.mkdir(parents=True, exist_ok=True)

    changed = False
    if should_copy(BINARY, APP_BINARY):
        shutil.copy2(BINARY, APP_BINARY)
        APP_BINARY.chmod(0o755)
        changed = True
    if should_copy(INFO_PLIST, APP_INFO_PLIST):
        shutil.copy2(INFO_PLIST, APP_INFO_PLIST)
        changed = True
    if changed:
        sign_app_bundle()


def should_copy(source: Path, destination: Path) -> bool:
    if not destination.exists():
        return True
    return source.stat().st_mtime > destination.stat().st_mtime


def sign_app_bundle() -> None:
    result = subprocess.run(
        ["codesign", "--force", "--sign", "-", str(APP)],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = " ".join((result.stderr or result.stdout).strip().split())
        if not detail:
            detail = "通知 app 签名失败。"
        输出(False, detail, result.returncode)


def run_app(arguments: list[str]) -> int:
    with tempfile.NamedTemporaryFile(prefix="notifications-cli-", suffix=".json", delete=False) as file:
        output_path = Path(file.name)

    try:
        result = subprocess.run(
            [
                "/usr/bin/open",
                "-n",
                "-W",
                str(APP),
                "--args",
                *arguments,
                "--output-json",
                str(output_path),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            detail = " ".join((result.stderr or result.stdout).strip().split())
            if not detail:
                detail = "无法通过 LaunchServices 启动通知 app。"
            输出(False, detail, result.returncode)

        if not output_path.exists() or output_path.stat().st_size == 0:
            输出(False, "通知 app 未返回结果。请确认 macOS 已允许启动 notifications-cli。", 1)

        print(output_path.read_text(encoding="utf-8"))
        return 0
    finally:
        try:
            output_path.unlink()
        except FileNotFoundError:
            pass


def main() -> None:
    if not sys.platform == "darwin":
        输出(False, "通知控制仅支持 macOS。", 1)
    build_if_needed()
    ensure_app_bundle()
    raise SystemExit(run_app(sys.argv[1:]))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""截取 macOS 全屏截图，并输出稳定 JSON。"""

from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCREEN_CAPTURE = "/usr/sbin/screencapture"
ARTIFACT_DIR = Path("/var/skills_artifacts/macos-controller")


def 输出(success: bool, data: Any = None, message: str = "ok", code: int = 0) -> None:
    print(
        json.dumps(
            {"success": success, "data": data if data is not None else {}, "message": message},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    raise SystemExit(code)


def normalize_error(raw: str) -> str:
    text = " ".join(raw.strip().split())
    lower = text.lower()
    if any(token in lower for token in ["not authorized", "not allowed", "privacy", "screen recording"]):
        return "没有权限截取屏幕。请到「系统设置 > 隐私与安全性 > 屏幕录制」允许当前终端或 Codex 后重试。"
    return text or "屏幕截图失败。"


def ensure_artifact_dir() -> None:
    try:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        输出(
            False,
            message=f"无法创建截图产物目录：{ARTIFACT_DIR}。请检查 /var/skills_artifacts 写入权限。详情：{exc}",
            code=1,
        )


def next_output_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = secrets.token_hex(4)
    return ARTIFACT_DIR / f"screenshot-{timestamp}-{suffix}.png"


def capture_screen(_: argparse.Namespace) -> dict[str, str]:
    ensure_artifact_dir()
    output_path = next_output_path()
    try:
        result = subprocess.run(
            [SCREEN_CAPTURE, "-x", str(output_path)],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except FileNotFoundError:
        输出(False, message="当前系统缺少 /usr/sbin/screencapture，无法截取屏幕。", code=1)
    except subprocess.TimeoutExpired:
        输出(False, message="屏幕截图超过 30 秒未返回。请确认系统截图权限和桌面会话状态正常。", code=1)

    if result.returncode != 0:
        输出(False, message=normalize_error(result.stderr or result.stdout), code=1)
    if not output_path.exists():
        输出(False, message="屏幕截图命令已返回成功，但没有生成图片文件。", code=1)
    return {"path": str(output_path)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="截取本机 macOS 全屏截图。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser("capture", help="截取当前全屏并返回图片路径。")
    capture.set_defaults(handler=capture_screen)
    return parser


def main() -> None:
    if not sys.platform == "darwin":
        输出(False, message="屏幕截图仅支持 macOS。", code=1)

    parser = build_parser()
    args = parser.parse_args()
    data = args.handler(args)
    输出(True, data=data)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""安全控制 macOS 通用应用窗口和进程，并输出稳定 JSON。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


OPEN = "/usr/bin/open"
OSASCRIPT = "/usr/bin/osascript"
DEFAULT_LIMIT = 20
MAX_LIMIT = 50
MAX_OFFSET = 500


def 输出(success: bool, data: Any = None, message: str = "ok", code: int = 0) -> None:
    print(
        json.dumps(
            {"success": success, "data": data if data is not None else {}, "message": message},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    raise SystemExit(code)


def text_literal(value: str | None) -> str:
    if value is None:
        return "missing value"
    return json.dumps(value, ensure_ascii=False)


def normalize_error(raw: str) -> str:
    text = " ".join(raw.strip().split())
    lower = text.lower()
    if any(token in lower for token in ["not authorized", "not allowed", "privacy", "accessibility", "automation"]):
        return "没有权限控制 macOS 应用。请到「系统设置 > 隐私与安全性」允许当前终端或 Codex 使用「辅助功能」和「自动化」。"
    if "-1743" in text or "-10827" in text:
        return "无法控制 macOS 应用，通常是辅助功能或自动化权限未开启。请到「系统设置 > 隐私与安全性」授权后重试。"
    if "-1728" in text:
        return "找不到目标应用或窗口。请先用 running 或 windows 查询后重试。"
    if "-10000" in text:
        message = text.replace("execution error:", "", 1).replace("(-10000)", "").strip()
        return message or "macOS 应用控制失败。"
    return text or "macOS 应用控制失败。"


def run_applescript(script: str, timeout: int = 15) -> Any:
    try:
        result = subprocess.run(
            [OSASCRIPT, "-e", script],
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        输出(False, message="macOS 应用控制超过 15 秒未返回。请确认目标应用和系统权限状态正常。", code=1)

    if result.returncode != 0:
        输出(False, message=normalize_error(result.stderr or result.stdout), code=1)

    raw = result.stdout.strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        输出(False, message="macOS 应用控制返回了非 JSON 输出，无法解析。", code=1)


def common_library() -> str:
    return r'''
on jsonEscape(v)
    if v is missing value then return "null"
    set slash to character id 92
    set s to v as text
    set s to my replaceText(s, slash, slash & slash)
    set s to my replaceText(s, quote, slash & quote)
    set s to my replaceText(s, linefeed, slash & "n")
    set s to my replaceText(s, return, slash & "n")
    set s to my replaceText(s, tab, slash & "t")
    return quote & s & quote
end jsonEscape

on replaceText(s, oldText, newText)
    set oldDelims to AppleScript's text item delimiters
    set AppleScript's text item delimiters to oldText
    set parts to text items of s
    set AppleScript's text item delimiters to newText
    set out to parts as text
    set AppleScript's text item delimiters to oldDelims
    return out
end replaceText

on nullableTextJson(v)
    if v is missing value then return "null"
    return my jsonEscape(v)
end nullableTextJson

on boolJson(v)
    if v then return "true"
    return "false"
end boolJson

on appJson(procRef)
    tell application "System Events"
        set appName to name of procRef
        set appBundle to missing value
        try
            set appBundle to bundle identifier of procRef
        end try
        set appPid to unix id of procRef
        set appFrontmost to frontmost of procRef
        set appVisible to visible of procRef
    end tell
    return "{" & ¬
        quote & "name" & quote & ":" & my jsonEscape(appName) & "," & ¬
        quote & "bundle_id" & quote & ":" & my nullableTextJson(appBundle) & "," & ¬
        quote & "pid" & quote & ":" & (appPid as text) & "," & ¬
        quote & "frontmost" & quote & ":" & my boolJson(appFrontmost) & "," & ¬
        quote & "visible" & quote & ":" & my boolJson(appVisible) & ¬
        "}"
end appJson

on processByName(appName)
    tell application "System Events"
        if not (exists application process appName) then error "目标应用未运行：" & appName number -10000
        return application process appName
    end tell
end processByName

on windowJson(windowRef, windowIndex)
    tell application "System Events"
        set windowName to name of windowRef
        set minimizedValue to false
        try
            set minimizedValue to value of attribute "AXMinimized" of windowRef
        end try
    end tell
    return "{" & ¬
        quote & "index" & quote & ":" & (windowIndex as text) & "," & ¬
        quote & "title" & quote & ":" & my jsonEscape(windowName) & "," & ¬
        quote & "minimized" & quote & ":" & my boolJson(minimizedValue) & ¬
        "}"
end windowJson
'''


def build_running_script(args: argparse.Namespace) -> str:
    query = text_literal(args.query)
    return common_library() + f'''
set queryText to {query}
set limitValue to {args.limit}
set offsetValue to {args.offset}
set probeLimit to offsetValue + limitValue + 1
set matchedCount to 0
set outputCount to 0
set hasMoreText to "false"
set rowsText to ""

tell application "System Events"
    repeat with procRef in application processes
        if background only of procRef is false then
            set appName to name of procRef
            set appBundle to missing value
            try
                set appBundle to bundle identifier of procRef
            end try
            set searchableText to appName
            if appBundle is not missing value then set searchableText to searchableText & linefeed & appBundle
            ignoring case
                set isMatched to queryText is missing value or searchableText contains queryText
            end ignoring
            if isMatched then
                set matchedCount to matchedCount + 1
                if matchedCount > offsetValue and outputCount < limitValue then
                    if outputCount > 0 then set rowsText to rowsText & ","
                    set rowsText to rowsText & my appJson(procRef)
                    set outputCount to outputCount + 1
                end if
                if matchedCount >= probeLimit then
                    set hasMoreText to "true"
                    exit repeat
                end if
            end if
        end if
    end repeat
end tell

if hasMoreText is "true" then
    set nextOffsetText to (offsetValue + limitValue) as text
else
    set nextOffsetText to "null"
end if

return "{{" & quote & "apps" & quote & ":[" & rowsText & "]," & ¬
    quote & "count" & quote & ":" & (outputCount as text) & "," & ¬
    quote & "offset" & quote & ":" & (offsetValue as text) & "," & ¬
    quote & "limit" & quote & ":" & (limitValue as text) & "," & ¬
    quote & "has_more" & quote & ":" & hasMoreText & "," & ¬
    quote & "next_offset" & quote & ":" & nextOffsetText & "}}"
'''


def build_frontmost_script(_: argparse.Namespace) -> str:
    return common_library() + '''
tell application "System Events"
    set procRef to first application process whose frontmost is true
end tell
return "{" & quote & "app" & quote & ":" & my appJson(procRef) & "}"
'''


def build_activate_script(args: argparse.Namespace) -> str:
    name = text_literal(args.name)
    return common_library() + f'''
set appName to {name}
set procRef to my processByName(appName)
tell application "System Events"
    set frontmost of procRef to true
end tell
return "{{" & quote & "app" & quote & ":" & my appJson(procRef) & "}}"
'''


def build_hide_script(args: argparse.Namespace) -> str:
    name = text_literal(args.name)
    return common_library() + f'''
set appName to {name}
set procRef to my processByName(appName)
tell application "System Events"
    set visible of procRef to false
end tell
return "{{" & quote & "app" & quote & ":" & my appJson(procRef) & "}}"
'''


def build_quit_script(args: argparse.Namespace) -> str:
    name = text_literal(args.name)
    return common_library() + f'''
set appName to {name}
my processByName(appName)
tell application appName to quit
return "{{" & quote & "name" & quote & ":" & my jsonEscape(appName) & "," & quote & "quit_requested" & quote & ":true}}"
'''


def build_windows_script(args: argparse.Namespace) -> str:
    name = text_literal(args.name)
    return common_library() + f'''
set appName to {name}
set procRef to my processByName(appName)
set rowsText to ""
set outputCount to 0

tell application "System Events"
    set windowCount to count of windows of procRef
    repeat with i from 1 to windowCount
        set windowRef to window i of procRef
        if outputCount > 0 then set rowsText to rowsText & ","
        set rowsText to rowsText & my windowJson(windowRef, i)
        set outputCount to outputCount + 1
    end repeat
end tell

return "{{" & quote & "name" & quote & ":" & my jsonEscape(appName) & "," & ¬
    quote & "windows" & quote & ":[" & rowsText & "]," & ¬
    quote & "count" & quote & ":" & (outputCount as text) & "}}"
'''


def build_focus_window_script(args: argparse.Namespace) -> str:
    name = text_literal(args.name)
    title = text_literal(args.title)
    index_expr = str(args.index) if args.index is not None else "missing value"
    return common_library() + f'''
set appName to {name}
set titleFilter to {title}
set indexFilter to {index_expr}
set procRef to my processByName(appName)
set targetWindow to missing value
set targetIndex to missing value
set matchedCount to 0

tell application "System Events"
    set windowCount to count of windows of procRef
    if indexFilter is not missing value then
        if indexFilter < 1 or indexFilter > windowCount then error "窗口序号超出范围：" & (indexFilter as text) number -10000
        set targetWindow to window indexFilter of procRef
        set targetIndex to indexFilter
    else
        repeat with i from 1 to windowCount
            set windowRef to window i of procRef
            set windowName to name of windowRef
            ignoring case
                set isMatched to windowName contains titleFilter
            end ignoring
            if isMatched then
                set matchedCount to matchedCount + 1
                set targetWindow to windowRef
                set targetIndex to i
            end if
        end repeat
        if matchedCount is 0 then error "找不到匹配标题的窗口：" & titleFilter number -10000
        if matchedCount > 1 then error "匹配到多个窗口，请改用 --index 精确指定。" number -10000
    end if

    try
        set value of attribute "AXMinimized" of targetWindow to false
    end try
    set frontmost of procRef to true
    try
        perform action "AXRaise" of targetWindow
    end try
    try
        set focused of targetWindow to true
    end try
end tell

return "{{" & quote & "name" & quote & ":" & my jsonEscape(appName) & "," & ¬
    quote & "window" & quote & ":" & my windowJson(targetWindow, targetIndex) & "}}"
'''


def open_app(args: argparse.Namespace) -> dict[str, str | bool]:
    command = [OPEN]
    if args.name:
        command.extend(["-a", args.name])
        target_type = "name"
        target = args.name
    elif args.bundle_id:
        command.extend(["-b", args.bundle_id])
        target_type = "bundle_id"
        target = args.bundle_id
    else:
        path = validate_app_path(args.path)
        command.append(str(path))
        target_type = "path"
        target = str(path)

    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False, timeout=15)
    except FileNotFoundError:
        输出(False, message="当前系统缺少 /usr/bin/open，无法启动应用。", code=1)
    except subprocess.TimeoutExpired:
        输出(False, message="启动应用超过 15 秒未返回。请确认目标应用可用。", code=1)

    if result.returncode != 0:
        输出(False, message=normalize_error(result.stderr or result.stdout), code=1)
    return {"target_type": target_type, "target": target, "open_requested": True}


def validate_app_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise argparse.ArgumentTypeError("--path 必须是绝对路径。")
    if not path.exists():
        raise argparse.ArgumentTypeError("--path 指向的应用不存在。")
    if path.suffix.lower() != ".app" or not path.is_dir():
        raise argparse.ArgumentTypeError("--path 只能指向 .app 应用目录。")
    return path


def validate_pagination(args: argparse.Namespace) -> None:
    if args.limit <= 0 or args.limit > MAX_LIMIT:
        输出(False, message=f"--limit 必须在 1 到 {MAX_LIMIT} 之间。", code=2)
    if args.offset < 0 or args.offset > MAX_OFFSET:
        输出(False, message=f"--offset 必须在 0 到 {MAX_OFFSET} 之间。", code=2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="安全控制本机 macOS 通用应用。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    running = subparsers.add_parser("running", help="列出运行中的 GUI 应用。")
    running.add_argument("--query", help="按应用名称或 bundle id 过滤。")
    running.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="返回数量，范围 1 到 50。")
    running.add_argument("--offset", type=int, default=0, help="分页偏移，范围 0 到 500。")
    running.set_defaults(builder=build_running_script)

    subparsers.add_parser("frontmost", help="读取当前前台应用。").set_defaults(builder=build_frontmost_script)

    open_cmd = subparsers.add_parser("open", help="启动或切换到应用。")
    open_target = open_cmd.add_mutually_exclusive_group(required=True)
    open_target.add_argument("--name", help="应用名称，例如 Safari。")
    open_target.add_argument("--bundle-id", help="应用 bundle id，例如 com.apple.Safari。")
    open_target.add_argument("--path", type=validate_app_path, help="应用 .app 目录的绝对路径。")
    open_cmd.set_defaults(handler=open_app)

    activate = subparsers.add_parser("activate", help="激活已运行的应用。")
    activate.add_argument("--name", required=True, help="应用名称。")
    activate.set_defaults(builder=build_activate_script)

    hide = subparsers.add_parser("hide", help="隐藏已运行的应用。")
    hide.add_argument("--name", required=True, help="应用名称。")
    hide.set_defaults(builder=build_hide_script)

    quit_cmd = subparsers.add_parser("quit", help="普通退出已运行的应用，不强制结束进程。")
    quit_cmd.add_argument("--name", required=True, help="应用名称。")
    quit_cmd.set_defaults(builder=build_quit_script)

    windows = subparsers.add_parser("windows", help="列出指定应用窗口。")
    windows.add_argument("--name", required=True, help="应用名称。")
    windows.set_defaults(builder=build_windows_script)

    focus_window = subparsers.add_parser("focus-window", help="激活指定应用窗口。")
    focus_window.add_argument("--name", required=True, help="应用名称。")
    focus_target = focus_window.add_mutually_exclusive_group(required=True)
    focus_target.add_argument("--index", type=int, help="窗口序号，从 1 开始。")
    focus_target.add_argument("--title", help="窗口标题关键词；匹配多个窗口时会报错。")
    focus_window.set_defaults(builder=build_focus_window_script)
    return parser


def main() -> None:
    if not sys.platform == "darwin":
        输出(False, message="macOS 应用控制仅支持 macOS。", code=1)

    parser = build_parser()
    args = parser.parse_args()
    if args.command == "running":
        validate_pagination(args)

    if hasattr(args, "handler"):
        data = args.handler(args)
    else:
        data = run_applescript(args.builder(args))
    输出(True, data=data)


if __name__ == "__main__":
    main()

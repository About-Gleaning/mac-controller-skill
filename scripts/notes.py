#!/usr/bin/env python3
"""通过 AppleScript 控制 macOS 备忘录应用，并输出稳定 JSON。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any


APP_PATH = "/System/Applications/Notes.app"
OSASCRIPT = "/usr/bin/osascript"
DEFAULT_LIMIT = 20
MAX_UNSCOPED_LIMIT = 20
MAX_SCOPED_LIMIT = 50
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


def html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\n", "<br>")
    )


def html_block(value: str) -> str:
    return f"<div>{html_escape(value)}</div>"


def run_applescript(script: str) -> Any:
    wrapped_script = f'using terms from application "{APP_PATH}"\n{script}\nend using terms from'
    try:
        result = subprocess.run(
            [OSASCRIPT, "-e", wrapped_script],
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        输出(False, message="备忘录操作超过 30 秒未返回。请确认 Notes 应用和权限状态正常。", code=1)
    if result.returncode != 0:
        输出(False, message=normalize_error(result.stderr or result.stdout), code=1)

    raw = result.stdout.strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        输出(False, message="备忘录应用返回了非 JSON 输出，无法解析。", code=1)


def normalize_error(raw: str) -> str:
    text = " ".join(raw.strip().split())
    lower = text.lower()
    if "-10000" in text:
        message = text.replace("execution error:", "", 1).replace("(-10000)", "").strip()
        return message or "备忘录操作失败。"
    if any(token in lower for token in ["not authorized", "not allowed", "privacy", "automation"]):
        return "没有权限控制备忘录应用。请到「系统设置 > 隐私与安全性」允许当前终端或 Codex 访问「备忘录」和自动化控制。"
    if "-1743" in text or "-10827" in text:
        return "无法控制备忘录应用，通常是 macOS 隐私权限或自动化权限未开启。请到「系统设置 > 隐私与安全性」授权后重试。"
    if "-1728" in text:
        return "无法访问备忘录对象。请确认 Notes 应用可用，并已授予自动化权限。"
    return text or "备忘录操作失败。"


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

on noteJson(n, folderName)
    tell application "''' + APP_PATH + r'''"
        set noteId to id of n
        set noteTitle to name of n
        set noteBody to body of n
        set createdText to creation date of n as text
        set modifiedText to modification date of n as text
    end tell
    return "{" & ¬
        quote & "id" & quote & ":" & my jsonEscape(noteId) & "," & ¬
        quote & "title" & quote & ":" & my jsonEscape(noteTitle) & "," & ¬
        quote & "folder" & quote & ":" & my jsonEscape(folderName) & "," & ¬
        quote & "body" & quote & ":" & my nullableTextJson(noteBody) & "," & ¬
        quote & "created_date" & quote & ":" & my jsonEscape(createdText) & "," & ¬
        quote & "modified_date" & quote & ":" & my jsonEscape(modifiedText) & ¬
        "}"
end noteJson

on firstWritableFolder()
    tell application "''' + APP_PATH + r'''"
        repeat with accountRef in accounts
            if (count of folders of accountRef) > 0 then return item 1 of folders of accountRef
        end repeat
    end tell
    error "无法获取默认备忘录文件夹。" number -10000
end firstWritableFolder

on folderByName(folderName)
    tell application "''' + APP_PATH + r'''"
        repeat with accountRef in accounts
            repeat with folderRef in folders of accountRef
                if name of folderRef is folderName then return folderRef
            end repeat
        end repeat
    end tell
    error "找不到备忘录文件夹：" & folderName number -10000
end folderByName

on noteById(noteId)
    tell application "''' + APP_PATH + r'''"
        repeat with accountRef in accounts
            repeat with folderRef in folders of accountRef
                repeat with noteRef in notes of folderRef
                    if id of noteRef is noteId then return noteRef
                end repeat
            end repeat
        end repeat
    end tell
    error "找不到备忘录：" & noteId number -10000
end noteById
'''


def build_create_script(args: argparse.Namespace) -> str:
    title = text_literal(args.title)
    body = text_literal(html_block(args.body))
    folder_expr = f"my folderByName({text_literal(args.folder)})" if args.folder else "my firstWritableFolder()"
    return common_library() + f'''
tell application "{APP_PATH}"
    set targetFolder to {folder_expr}
    set newNote to make new note at targetFolder with properties {{name:{title}, body:{body}}}
    set folderName to name of targetFolder
end tell
return "{{" & quote & "note" & quote & ":" & my noteJson(newNote, folderName) & "}}"
'''


def build_list_script(args: argparse.Namespace) -> str:
    folder_name = text_literal(args.folder)
    query = text_literal(args.query)
    return common_library() + f'''
set folderFilter to {folder_name}
set queryText to {query}
set limitValue to {args.limit}
set offsetValue to {args.offset}
set probeLimit to offsetValue + limitValue + 1
set matchedCount to 0
set outputCount to 0
set hasMoreText to "false"
set rowsText to ""

tell application "{APP_PATH}"
    repeat with accountRef in accounts
        repeat with folderRef in folders of accountRef
            set folderName to name of folderRef
            if folderFilter is missing value or folderName is folderFilter then
                repeat with noteRef in notes of folderRef
                    set titleText to name of noteRef
                    set bodyText to body of noteRef
                    set searchableText to (titleText & linefeed & bodyText) as text
                    ignoring case
                        set isMatched to queryText is missing value or searchableText contains queryText
                    end ignoring
                    if isMatched then
                        set matchedCount to matchedCount + 1
                        if matchedCount > offsetValue and outputCount < limitValue then
                            if outputCount > 0 then set rowsText to rowsText & ","
                            set rowsText to rowsText & my noteJson(noteRef, folderName)
                            set outputCount to outputCount + 1
                        end if
                        if matchedCount >= probeLimit then
                            set hasMoreText to "true"
                            exit repeat
                        end if
                    end if
                end repeat
            end if
            if hasMoreText is "true" then exit repeat
        end repeat
        if hasMoreText is "true" then exit repeat
    end repeat
end tell

if hasMoreText is "true" then
    set nextOffsetText to (offsetValue + limitValue) as text
else
    set nextOffsetText to "null"
end if

return "{{" & quote & "notes" & quote & ":[" & rowsText & "]," & ¬
    quote & "count" & quote & ":" & (outputCount as text) & "," & ¬
    quote & "offset" & quote & ":" & (offsetValue as text) & "," & ¬
    quote & "limit" & quote & ":" & (limitValue as text) & "," & ¬
    quote & "has_more" & quote & ":" & hasMoreText & "," & ¬
    quote & "next_offset" & quote & ":" & nextOffsetText & "}}"
'''


def build_append_script(args: argparse.Namespace) -> str:
    note_id = text_literal(args.id)
    body = text_literal(html_block(args.body))
    return common_library() + f'''
tell application "{APP_PATH}"
    set targetNote to my noteById({note_id})
    set currentBody to body of targetNote
    set body of targetNote to currentBody & {body}
    set folderName to name of container of targetNote
end tell
return "{{" & quote & "note" & quote & ":" & my noteJson(targetNote, folderName) & "}}"
'''


def validate_pagination(args: argparse.Namespace) -> None:
    if args.limit <= 0:
        输出(False, message="--limit 必须大于 0。", code=2)
    if args.offset < 0 or args.offset > MAX_OFFSET:
        输出(False, message=f"--offset 必须在 0 到 {MAX_OFFSET} 之间。", code=2)
    max_limit = MAX_SCOPED_LIMIT if args.query or args.folder else MAX_UNSCOPED_LIMIT
    if args.limit > max_limit:
        输出(False, message=f"当前查询的 --limit 不能超过 {max_limit}。请使用 --query、--folder 或 --offset 缩小范围。", code=2)


def main() -> None:
    if not sys.platform == "darwin":
        输出(False, message="备忘录控制仅支持 macOS。", code=1)

    parser = argparse.ArgumentParser(description="控制 macOS 备忘录")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create")
    create.add_argument("--title", required=True)
    create.add_argument("--body", required=True)
    create.add_argument("--folder")
    create.set_defaults(builder=build_create_script)

    list_cmd = subparsers.add_parser("list")
    list_cmd.add_argument("--folder")
    list_cmd.add_argument("--query")
    list_cmd.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    list_cmd.add_argument("--offset", type=int, default=0)
    list_cmd.set_defaults(builder=build_list_script)

    append = subparsers.add_parser("append")
    append.add_argument("--id", required=True)
    append.add_argument("--body", required=True)
    append.set_defaults(builder=build_append_script)

    args = parser.parse_args()
    if args.command == "list":
        validate_pagination(args)
    data = run_applescript(args.builder(args))
    输出(True, data=data)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""通过 AppleScript 控制 macOS 提醒事项，并输出稳定 JSON。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any


APP_PATH = "/System/Applications/Reminders.app"
OSASCRIPT = "/usr/bin/osascript"
DATE_FORMAT_HINT = "YYYY-MM-DD HH:MM:SS"


def 输出(success: bool, data: Any = None, message: str = "ok", code: int = 0) -> None:
    print(
        json.dumps(
            {"success": success, "data": data if data is not None else {}, "message": message},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    raise SystemExit(code)


def applescript_literal(value: str | None) -> str:
    if value is None:
        return "missing value"
    return json.dumps(value, ensure_ascii=False)


def bool_literal(value: bool | None) -> str:
    if value is None:
        return "missing value"
    return "true" if value else "false"


def int_literal(value: int | None) -> str:
    if value is None:
        return "missing value"
    return str(value)


def run_applescript(script: str) -> Any:
    # Reminders 的脚本术语必须绑定到应用字典；实际控制仍使用绝对路径，避免本地化名称歧义。
    wrapped_script = f'using terms from application "{APP_PATH}"\n{script}\nend using terms from'
    try:
        result = subprocess.run(
            [OSASCRIPT, "-e", wrapped_script],
            text=True,
            capture_output=True,
            check=False,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        输出(False, message="提醒事项操作超过 60 秒未返回。请缩小查询范围，或确认 Reminders 应用和权限状态正常。", code=1)
    if result.returncode != 0:
        输出(False, message=normalize_error(result.stderr or result.stdout), code=1)

    raw = result.stdout.strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        输出(False, message="提醒事项返回了非 JSON 输出，无法解析。", code=1)


def normalize_error(raw: str) -> str:
    text = " ".join(raw.strip().split())
    lower = text.lower()
    if any(token in lower for token in ["not authorized", "not allowed", "privacy", "automation"]):
        return "没有权限控制提醒事项。请到「系统设置 > 隐私与安全性」允许当前终端或 Codex 访问「提醒事项」和自动化控制。"
    if "-1743" in text or "-10827" in text:
        return "无法控制提醒事项，通常是 macOS 隐私权限或自动化权限未开启。请到「系统设置 > 隐私与安全性」授权后重试。"
    if "-1728" in text:
        return "无法访问提醒事项对象。请确认 macOS 提醒事项应用可用，并已授予访问权限。"
    return text or "提醒事项操作失败。"


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

on boolJson(v)
    if v then return "true"
    return "false"
end boolJson

on nullableDateJson(v)
    if v is missing value then return "null"
    return my jsonEscape(v as text)
end nullableDateJson

on reminderJson(r, listName)
    set reminderId to id of r
    set reminderName to name of r
    set reminderBody to body of r
    set reminderCompleted to completed of r
    set reminderDue to due date of r
    set reminderPriority to priority of r
    return "{" & ¬
        quote & "id" & quote & ":" & my jsonEscape(reminderId) & "," & ¬
        quote & "name" & quote & ":" & my jsonEscape(reminderName) & "," & ¬
        quote & "list" & quote & ":" & my jsonEscape(listName) & "," & ¬
        quote & "body" & quote & ":" & my jsonEscape(reminderBody) & "," & ¬
        quote & "completed" & quote & ":" & my boolJson(reminderCompleted) & "," & ¬
        quote & "due_date" & quote & ":" & my nullableDateJson(reminderDue) & "," & ¬
        quote & "priority" & quote & ":" & (reminderPriority as text) & ¬
        "}"
end reminderJson

on reminderValuesJson(reminderId, reminderName, listName, reminderBody, reminderCompleted, reminderDue, reminderPriority)
    return "{" & ¬
        quote & "id" & quote & ":" & my jsonEscape(reminderId) & "," & ¬
        quote & "name" & quote & ":" & my jsonEscape(reminderName) & "," & ¬
        quote & "list" & quote & ":" & my jsonEscape(listName) & "," & ¬
        quote & "body" & quote & ":" & my jsonEscape(reminderBody) & "," & ¬
        quote & "completed" & quote & ":" & my boolJson(reminderCompleted) & "," & ¬
        quote & "due_date" & quote & ":" & my nullableDateJson(reminderDue) & "," & ¬
        quote & "priority" & quote & ":" & (reminderPriority as text) & ¬
        "}"
end reminderValuesJson

on parseDateOrMissing(v)
    if v is missing value then return missing value
    return date v
end parseDateOrMissing

on findReminderById(targetId)
    tell application "''' + APP_PATH + r'''"
        return reminder id targetId
    end tell
end findReminderById
'''


def build_create_script(args: argparse.Namespace) -> str:
    list_expr = "default list"
    if args.list:
        list_expr = f"list {applescript_literal(args.list)}"
    due_expr = f"my parseDateOrMissing({applescript_literal(args.due)})"
    body_expr = applescript_literal(args.body)
    priority_expr = int_literal(args.priority)
    return common_library() + f'''
tell application "{APP_PATH}"
    set targetList to {list_expr}
    set newReminder to make new reminder at end of reminders of targetList with properties {{name:{applescript_literal(args.name)}}}
    if {body_expr} is not missing value then set body of newReminder to {body_expr}
    set parsedDue to {due_expr}
    if parsedDue is not missing value then set due date of newReminder to parsedDue
    if {priority_expr} is not missing value then set priority of newReminder to {priority_expr}
    set payload to my reminderJson(newReminder, name of targetList)
end tell
return "{{" & quote & "reminder" & quote & ":" & payload & "}}"
'''


def build_list_script(args: argparse.Namespace) -> str:
    completed_filter = bool_literal(args.completed)
    query = applescript_literal(args.query.lower() if args.query else None)
    list_name = applescript_literal(args.list)
    limit = int(args.limit)
    return common_library() + f'''
set rows to {{}}
set matchedCount to 0
tell application "{APP_PATH}"
    repeat with eachList in lists
        set currentListName to name of eachList
        if {list_name} is missing value or currentListName is {list_name} then
            repeat with eachReminder in reminders of eachList
                if {completed_filter} is missing value or completed of eachReminder is {completed_filter} then
                    ignoring case
                        set queryMatched to ({query} is missing value or (name of eachReminder) contains {query})
                    end ignoring
                    if queryMatched then
                        set end of rows to my reminderJson(eachReminder, currentListName)
                        set matchedCount to matchedCount + 1
                        if matchedCount >= {limit} then exit repeat
                    end if
                end if
            end repeat
        end if
        if matchedCount >= {limit} then exit repeat
    end repeat
end tell
set AppleScript's text item delimiters to ","
set payload to rows as text
set AppleScript's text item delimiters to ""
return "{{" & quote & "reminders" & quote & ":[" & payload & "]," & quote & "count" & quote & ":" & (matchedCount as text) & "}}"
'''


def build_update_script(args: argparse.Namespace) -> str:
    name_expr = applescript_literal(args.name)
    body_expr = applescript_literal(args.body)
    completed_expr = bool_literal(args.completed)
    priority_expr = int_literal(args.priority)
    due_expr = f"my parseDateOrMissing({applescript_literal(args.due)})"
    clear_due = bool_literal(args.clear_due)
    return common_library() + f'''
tell application "{APP_PATH}"
    set targetReminder to reminder id {applescript_literal(args.id)}
    if {name_expr} is not missing value then set name of targetReminder to {name_expr}
    if {body_expr} is not missing value then set body of targetReminder to {body_expr}
    if {priority_expr} is not missing value then set priority of targetReminder to {priority_expr}
    if {completed_expr} is not missing value then set completed of targetReminder to {completed_expr}
    if {clear_due} then
        set due date of targetReminder to missing value
    else
        set parsedDue to {due_expr}
        if parsedDue is not missing value then set due date of targetReminder to parsedDue
    end if
end tell
return "{{" & quote & "id" & quote & ":" & my jsonEscape({applescript_literal(args.id)}) & "," & quote & "updated" & quote & ":true}}"
'''


def build_complete_script(args: argparse.Namespace) -> str:
    return common_library() + f'''
tell application "{APP_PATH}"
    set targetReminder to reminder id {applescript_literal(args.id)}
    set completed of targetReminder to true
end tell
return "{{" & quote & "id" & quote & ":" & my jsonEscape({applescript_literal(args.id)}) & "," & quote & "completed" & quote & ":true}}"
'''


def parse_bool(value: str) -> bool:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise argparse.ArgumentTypeError("布尔值必须是 true 或 false。")


def validate_due(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) != 19 or value[4] != "-" or value[7] != "-" or value[10] != " " or value[13] != ":" or value[16] != ":":
        raise argparse.ArgumentTypeError(f"时间格式必须是 {DATE_FORMAT_HINT}。")
    return value


def validate_priority(value: str) -> int:
    try:
        priority = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("优先级必须是整数。") from exc
    if priority < 0 or priority > 9:
        raise argparse.ArgumentTypeError("优先级必须在 0 到 9 之间。")
    return priority


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="控制本机 macOS 提醒事项。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="创建提醒事项。")
    create.add_argument("--name", required=True, help="提醒事项标题。")
    create.add_argument("--list", help="目标列表名称；默认使用提醒事项默认列表。")
    create.add_argument("--body", help="备注。")
    create.add_argument("--due", type=validate_due, help=f"截止时间，格式：{DATE_FORMAT_HINT}。")
    create.add_argument("--priority", type=validate_priority, help="优先级：0 无，1-4 高，5 中，6-9 低。")

    list_cmd = subparsers.add_parser("list", help="查询提醒事项。")
    list_cmd.add_argument("--list", help="按列表名称过滤。")
    list_cmd.add_argument("--query", help="按标题关键词过滤，不区分大小写。")
    list_cmd.add_argument("--completed", type=parse_bool, help="按完成状态过滤：true 或 false。")
    list_cmd.add_argument("--limit", type=int, default=20, help="最多返回数量，默认 20。")

    update = subparsers.add_parser("update", help="按 id 更新提醒事项。")
    update.add_argument("--id", required=True, help="提醒事项 id。")
    update.add_argument("--name", help="新标题。")
    update.add_argument("--body", help="新备注。")
    update.add_argument("--due", type=validate_due, help=f"新截止时间，格式：{DATE_FORMAT_HINT}。")
    update.add_argument("--clear-due", action="store_true", help="清除截止时间。")
    update.add_argument("--priority", type=validate_priority, help="优先级：0 到 9。")
    update.add_argument("--completed", type=parse_bool, help="设置完成状态：true 或 false。")

    complete = subparsers.add_parser("complete", help="按 id 标记完成。")
    complete.add_argument("--id", required=True, help="提醒事项 id。")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if getattr(args, "limit", 1) < 1:
        输出(False, message="--limit 必须大于 0。", code=2)
    if getattr(args, "clear_due", False) and getattr(args, "due", None):
        输出(False, message="--clear-due 不能和 --due 同时使用。", code=2)

    builders = {
        "create": build_create_script,
        "list": build_list_script,
        "update": build_update_script,
        "complete": build_complete_script,
    }
    data = run_applescript(builders[args.command](args))
    输出(True, data=data)


if __name__ == "__main__":
    main()

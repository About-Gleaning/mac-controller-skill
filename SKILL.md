---
name: macos-controller
description: Use when an agent needs to control local macOS apps from Codex through bundled AppleScript-backed CLIs, currently including Reminders and Music.
---

# macOS Controller

使用本 skill 控制本机 macOS 应用。必须优先使用内置脚本，不要直接手写 AppleScript，除非是在调试脚本本身。

## 前置条件

- 仅适用于 macOS，本机需要存在目标系统应用。
- 提醒事项脚本使用 Apple EventKit Swift CLI，首次运行会自动构建本仓库内的 SwiftPM 可执行文件；音乐脚本继续使用系统内置 `/usr/bin/osascript`。
- 首次运行可能触发 macOS 隐私授权。若失败信息提示无权限，引导用户到「系统设置 > 隐私与安全性」中允许当前终端或 Codex 访问「提醒事项」；音乐控制还需要允许目标应用和自动化控制。

## 提醒事项命令

在本 skill 目录执行命令，或使用脚本绝对路径。

```bash
python3 scripts/reminders.py create --name "提交周报" --body "整理本周进展" --due "2026-06-01 09:00:00"
python3 scripts/reminders.py list --query "周报" --completed false
python3 scripts/reminders.py list --offset 20
python3 scripts/reminders.py update --id "<reminder-id>" --name "提交周报给团队" --priority 5
python3 scripts/reminders.py complete --id "<reminder-id>"
```

- `create`：创建提醒事项，支持 `--name`、`--list`、`--body`、`--due`、`--priority`。
- `list`：查询提醒事项，支持 `--list`、`--query`、`--completed true|false`、`--limit`、`--offset`。默认只查询未完成事项；查询已完成事项必须显式传 `--completed true`。无 `--list` 和 `--query` 时 `--limit` 最大为 20；传入 `--list` 或 `--query` 后最大为 50；`--offset` 范围为 0..500。
- `update`：按 `--id` 更新提醒事项，支持 `--name`、`--body`、`--due`、`--clear-due`、`--priority`、`--completed true|false`。
- `complete`：按 `--id` 标记提醒事项完成。

查询和修改必须优先使用提醒事项 `id`，避免同名提醒事项被误改。如果第一页没有找到目标且返回 `has_more: true`，用 `next_offset` 继续查询下一页；仍应优先添加 `--query` 或 `--list` 缩小范围。不要实现或执行删除、创建列表、标签、附件、位置提醒等本 skill 未提供的能力。

## 音乐命令

使用 `scripts/music.py` 控制本机 macOS「音乐」应用。支持播放控制、音量、随机播放、循环模式，以及按歌曲、歌手、专辑搜索并播放本机 Music 曲库中的首个匹配歌曲；不修改资料库。

```bash
python3 scripts/music.py status
python3 scripts/music.py play-pause
python3 scripts/music.py play
python3 scripts/music.py pause
python3 scripts/music.py next
python3 scripts/music.py previous
python3 scripts/music.py volume --level 30
python3 scripts/music.py shuffle --enabled true
python3 scripts/music.py repeat --mode one
python3 scripts/music.py play-song --name "富士山下" --artist "陈奕迅"
python3 scripts/music.py play-artist --name "陈奕迅"
python3 scripts/music.py play-album --name "认了吧" --artist "陈奕迅"
```

- `status`：读取播放状态、音量和当前曲目。
- `play-pause`：切换播放或暂停。
- `play`：开始播放。
- `pause`：暂停播放。
- `next`：播放下一首。
- `previous`：播放上一首。
- `volume`：设置音量，支持 `--level 0..100`。
- `shuffle`：设置随机播放开关，支持 `--enabled true|false`。
- `repeat`：设置循环播放模式，支持 `--mode off|one|all`，分别表示关闭、单曲循环、全部循环。
- `play-song`：按歌曲名搜索并播放首个匹配歌曲，支持 `--name`，可选 `--artist` 缩小范围。
- `play-artist`：按歌手名搜索并播放首个匹配歌曲，支持 `--name`。
- `play-album`：按专辑名搜索并播放首个匹配歌曲，支持 `--name`，可选 `--artist` 缩小范围。

搜索播放使用模糊匹配；如果命中多个结果，播放第一个匹配项。如果用户要求播放列表管理、资料库写入、删除、收藏等本 skill 未提供的音乐能力，应说明不支持，不要直接手写 AppleScript 绕过脚本。

## 返回结构

脚本始终输出 JSON：

```json
{
  "success": true,
  "data": {},
  "message": "ok"
}
```

提醒事项查询结果至少包含：

- `id`
- `name`
- `list`
- `body`
- `completed`
- `due_date`
- `priority`

分页字段包含：

- `count`
- `offset`
- `limit`
- `has_more`
- `next_offset`

音乐状态结果可能包含：

- `player_state`
- `volume`
- `shuffle_enabled`
- `repeat_mode`
- `current_track`

读取结果时只汇报与用户请求相关的字段。失败时读取 `message`，不要把完整系统错误堆栈原样转述给用户。

## 工作流

1. 识别用户要控制的应用：提醒事项或音乐。
2. 如果要更新或完成提醒事项，但用户没有提供 `id`，先用 `list` 查询候选项；第一页没有目标且 `has_more` 为 true 时，用 `next_offset` 继续翻页，再让用户确认目标。
3. 构造最小命令参数；只传用户明确要求的字段。
4. 执行脚本并读取 JSON 输出。
5. 如果返回权限错误，提示用户到系统设置开启目标应用和自动化权限，然后重试。

## 数据与安全

- 本 skill 只操作本机 macOS 应用，不访问网络。
- 更新和完成操作按唯一 `id` 定位，降低误修改风险。
- 不输出无关提醒事项详情；查询默认只返回未完成事项，并优先使用 `--query`、`--list`、较小 `--limit` 和 `--offset` 控制单次扫描范围。
- 常规音乐控制只执行 O(1) 播放命令和状态读取；按歌曲、歌手、专辑搜索播放会扫描本机 Music 曲库，时间复杂度与曲库规模线性相关。执行搜索播放时只汇报当前播放结果，不输出无关曲库列表，避免暴露不必要的媒体资料。

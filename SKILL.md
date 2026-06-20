---
name: macos-controller
description: Use when an agent needs to control local macOS apps from Codex through bundled CLIs, currently including generic app/window control, Calendar, Notes, Reminders, Music, and screen capture.
---

# macOS Controller

使用本 skill 控制本机 macOS 应用。必须优先使用内置脚本，不要直接手写 AppleScript，除非是在调试脚本本身。

## 前置条件

- 仅适用于 macOS，本机需要存在目标系统应用。
- 日历和提醒事项脚本使用 Apple EventKit Swift CLI，通知脚本使用 Apple UserNotifications Swift CLI，首次运行会自动构建本仓库内的 SwiftPM 可执行文件；通用 App、备忘录和音乐脚本使用系统内置 `/usr/bin/osascript`。
- 首次运行可能触发 macOS 隐私授权。若失败信息提示无权限，引导用户到「系统设置 > 隐私与安全性」中允许当前终端或 Codex 访问「日历」「提醒事项」「备忘录」、目标应用自动化控制或「辅助功能」；通知权限到「系统设置 > 通知」中允许。
- 本 skill 产生的文件类产物统一保存到 `/var/skills_artifacts/macos-controller/`。

## 通用 App 命令

使用 `scripts/apps.py` 安全控制本机 macOS 通用应用和窗口。适合日常打开应用、切换工作窗口、查看当前前台应用、隐藏干扰应用或普通退出应用；第一版不提供键盘输入、鼠标点击或强制退出。

```bash
python3 scripts/apps.py running
python3 scripts/apps.py running --query "Safari" --limit 10
python3 scripts/apps.py frontmost
python3 scripts/apps.py open --name "Safari"
python3 scripts/apps.py open --bundle-id "com.apple.Safari"
python3 scripts/apps.py open --path "/Applications/Safari.app"
python3 scripts/apps.py activate --name "Safari"
python3 scripts/apps.py hide --name "Music"
python3 scripts/apps.py quit --name "Preview"
python3 scripts/apps.py windows --name "Safari"
python3 scripts/apps.py focus-window --name "Safari" --index 1
python3 scripts/apps.py focus-window --name "Safari" --title "工作台"
```

- `running`：列出正在运行的非后台 GUI 应用，支持 `--query`、`--limit`、`--offset`；`--limit` 范围为 1..50，`--offset` 范围为 0..500。
- `frontmost`：读取当前前台应用。
- `open`：启动或切换应用，支持 `--name`、`--bundle-id` 或 `--path` 三选一；`--path` 必须是绝对路径并指向 `.app` 目录，避免误打开普通文件。
- `activate`：激活已运行应用；目标未运行时返回错误，不自动启动。
- `hide`：隐藏已运行应用。
- `quit`：请求应用普通退出，不强制结束进程，避免未保存内容丢失。
- `windows`：列出指定应用窗口，返回窗口序号、标题和最小化状态。
- `focus-window`：按 `--index` 或 `--title` 激活窗口；标题匹配到多个窗口时会报错，应先用 `windows` 查询后改用 `--index`。

如果用户要求强制退出、发送快捷键、输入文本、点击 UI、批量关闭应用或读取应用内部内容，应说明当前不支持，不要直接手写 AppleScript 绕过脚本。窗口控制通常需要「辅助功能」权限；启动和退出部分应用可能需要「自动化」权限。

## 日历命令

使用 `scripts/calendar.py` 管理本机 macOS「日历」应用中的近期日程。适合创建会议、查询安排、调整时间地点、删除明确指定的日程。

```bash
python3 scripts/calendar.py auth-status
python3 scripts/calendar.py request-access
python3 scripts/calendar.py create --title "团队周会" --start "2026-06-18 10:00:00" --end "2026-06-18 11:00:00" --calendar "工作" --location "会议室 A" --notes "同步项目进展"
python3 scripts/calendar.py list --query "周会" --from "2026-06-16 00:00:00" --to "2026-06-23 23:59:59"
python3 scripts/calendar.py list --offset 20
python3 scripts/calendar.py update --id "<event-id>" --start "2026-06-18 10:30:00" --end "2026-06-18 11:30:00"
python3 scripts/calendar.py delete --id "<event-id>"
```

- `auth-status`：读取当前进程的日历授权状态，不查询或修改日程。
- `request-access`：主动请求日历完整访问权限，用于触发 macOS 授权窗口。
- `create`：创建日程，支持 `--title`、`--calendar`、`--start`、`--end`、`--all-day true|false`、`--location`、`--notes`。
- `list`：查询日程，支持 `--calendar`、`--query`、`--from`、`--to`、`--limit`、`--offset`。未传 `--from` 和 `--to` 时默认查询今天起 30 天内的日程；只传一侧边界时自动补齐 30 天窗口。无 `--calendar` 和 `--query` 时 `--limit` 最大为 20；传入 `--calendar` 或 `--query` 后最大为 50；`--offset` 范围为 0..500。
- `update`：按 `--id` 更新日程，支持 `--title`、`--calendar`、`--start`、`--end`、`--all-day true|false`、`--location`、`--notes`。
- `delete`：按 `--id` 删除日程。

查询、更新和删除必须优先使用日程 `id`，避免同名日程被误改或误删。如果第一页没有找到目标且返回 `has_more: true`，用 `next_offset` 继续查询下一页；仍应优先添加 `--query`、`--calendar`、`--from` 或 `--to` 缩小范围。不要实现或执行创建日历、重复日程、参会人邀请、附件、提醒闹钟、批量删除等本 skill 未提供的能力。

### 日历权限排障

如果日历命令返回没有权限，先运行：

```bash
python3 scripts/calendar.py auth-status
python3 scripts/calendar.py request-access
```

macOS 日历权限绑定到当前启动命令的宿主应用，例如 Codex、CodePilot 或 Terminal，而不是绑定到脚本路径本身。若 `auth-status` 返回 `denied`，到「系统设置 > 隐私与安全性 > 日历」允许当前宿主应用访问日历；如果系统不再弹出授权窗口，可由用户手动执行 `tccutil reset Calendar` 后重新运行 `request-access`。不要自动重置 TCC 权限。

## 备忘录命令

使用 `scripts/notes.py` 控制本机 macOS「备忘录」应用。适合快速记录、查找已有记录、向已有笔记追加进展；第一版不提供删除或覆盖式替换。

```bash
python3 scripts/notes.py create --title "项目想法" --body "先记录一个初步方向" --folder "工作"
python3 scripts/notes.py list --query "项目" --limit 20
python3 scripts/notes.py list --folder "工作" --offset 20
python3 scripts/notes.py append --id "<note-id>" --body "补充：下午和设计确认范围"
```

- `create`：创建备忘录，支持 `--title`、`--body`、`--folder`。未传 `--folder` 时使用第一个可写文件夹。
- `list`：查询备忘录，支持 `--folder`、`--query`、`--limit`、`--offset`。无 `--folder` 和 `--query` 时 `--limit` 最大为 20；传入 `--folder` 或 `--query` 后最大为 50；`--offset` 范围为 0..500。
- `append`：按 `--id` 向备忘录末尾追加内容，支持 `--body`。

追加必须按唯一 `id` 定位，避免同名备忘录被误改。如果用户要求删除、覆盖全文、移动文件夹、创建文件夹、附件或富文本编辑，应说明当前不支持，不要直接手写 AppleScript 绕过脚本。

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
python3 scripts/music.py volume --delta 10
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
- `volume`：设置或调整音量，支持 `--level 0..100` 或 `--delta -100..100`；相对调整会自动限制在 0..100。
- `shuffle`：设置随机播放开关，支持 `--enabled true|false`。
- `repeat`：设置循环播放模式，支持 `--mode off|one|all`，分别表示关闭、单曲循环、全部循环。
- `play-song`：按歌曲名搜索并播放首个匹配歌曲，支持 `--name`，可选 `--artist` 缩小范围。
- `play-artist`：按歌手名搜索并播放首个匹配歌曲，支持 `--name`。
- `play-album`：按专辑名搜索并播放首个匹配歌曲，支持 `--name`，可选 `--artist` 缩小范围。

搜索播放使用模糊匹配；如果命中多个结果，播放第一个匹配项。如果用户要求播放列表管理、资料库写入、删除、收藏等本 skill 未提供的音乐能力，应说明不支持，不要直接手写 AppleScript 绕过脚本。

## 屏幕截图命令

使用 `scripts/screenshot.py` 截取本机 macOS 当前全屏，并返回生成的图片路径。截图默认保存到 `/var/skills_artifacts/macos-controller/`。

```bash
python3 scripts/screenshot.py capture
```

- `capture`：截取当前全屏，保存为 PNG 文件，并返回 `data.path`。

当前只支持全屏截图，不支持区域截图、窗口截图或交互式选择。如果截图命令返回没有权限，到「系统设置 > 隐私与安全性 > 屏幕录制」允许当前终端或 Codex 后重试。

## 通知命令

使用 `scripts/notifications.py` 通过 macOS UserNotifications 发送一条本机立即通知。

```bash
python3 scripts/notifications.py auth-status
python3 scripts/notifications.py request-access
python3 scripts/notifications.py send --title "测试通知" --body "来自 macOS Controller"
python3 scripts/notifications.py send --title "构建完成" --subtitle "mac-controller-skill" --body "可以查看结果"
```

- `auth-status`：读取当前进程的通知授权状态，不发送通知。
- `request-access`：主动请求通知权限，用于触发 macOS 授权窗口。
- `send`：发送一条立即通知，支持 `--title`、`--subtitle`、`--body`，其中 `--title` 必填。

当前只支持立即通知，不支持延迟通知、定时通知、重复通知、操作按钮或通知撤回。如果通知命令返回没有权限，先运行 `request-access` 触发系统授权窗口；授权主体是 `notifications-cli`，不是 VSCode。若系统不弹窗，到「系统设置 > 通知」允许 `notifications-cli` 发送通知后重试。

## 返回结构

脚本始终输出 JSON：

```json
{
  "success": true,
  "data": {},
  "message": "ok"
}
```

通用 App 结果可能包含：

- `apps`
- `app`
- `name`
- `bundle_id`
- `pid`
- `frontmost`
- `visible`
- `windows`
- `index`
- `title`
- `minimized`
- `quit_requested`
- `open_requested`

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

屏幕截图结果包含：

- `path`

通知发送结果包含：

- `notification_id`
- `delivered`

日历查询结果至少包含：

- `id`
- `title`
- `calendar`
- `start_date`
- `end_date`
- `all_day`
- `location`
- `notes`

备忘录查询结果至少包含：

- `id`
- `title`
- `folder`
- `body`
- `created_date`
- `modified_date`

读取结果时只汇报与用户请求相关的字段。截图完成后直接返回 `data.path`。失败时读取 `message`，不要把完整系统错误堆栈原样转述给用户。

## 工作流

1. 识别用户要控制的应用或系统能力：通用 App、日历、备忘录、提醒事项、音乐、屏幕截图或通知。
2. 如果要激活或隐藏应用但用户没有给出明确应用名，先用 `scripts/apps.py running --query "<关键词>"` 查询候选项；如果要激活窗口但没有窗口序号，先用 `windows` 查询候选项，匹配多个时让用户确认。
3. 如果要更新或完成提醒事项、更新或删除日程、追加备忘录，但用户没有提供 `id`，先用对应 `list` 查询候选项；第一页没有目标且 `has_more` 为 true 时，用 `next_offset` 继续翻页，再让用户确认目标。
4. 构造最小命令参数；只传用户明确要求的字段。
5. 执行脚本并读取 JSON 输出。
6. 如果返回权限错误，提示用户到系统设置开启目标应用、辅助功能、自动化或屏幕录制权限，然后重试。

## 数据与安全

- 本 skill 只操作本机 macOS 应用，不访问网络。
- 更新、完成、删除和追加操作按唯一 `id` 定位，降低误修改、误删除和误追加风险。
- 通用 App 控制只操作运行中进程和窗口元数据；`open` 不扫描磁盘应用库，`--path` 只允许 `.app` 目录；`quit` 只请求普通退出，不强制杀进程，降低未保存数据丢失风险。
- 不输出无关日历、备忘录或提醒事项详情；查询默认使用近期窗口、未完成过滤、`--query`、`--calendar`、`--folder`、`--list`、较小 `--limit` 和 `--offset` 控制单次扫描范围。
- 通用 App 的 `running` 查询只返回运行中的非后台 GUI 应用，时间复杂度与运行中应用数量线性相关；`frontmost`、`open`、`activate`、`hide` 和 `quit` 近似 O(1)；`windows` 和 `focus-window` 与目标应用窗口数量线性相关。
- 日历查询使用 EventKit 时间范围检索，时间复杂度主要取决于查询窗口内的日程数量；默认 30 天窗口用于平衡日常可用性和本机数据最小暴露。
- 备忘录查询通过 Notes AppleScript 扫描本机文件夹，时间复杂度与备忘录数量线性相关；执行查询时应优先传 `--query` 或 `--folder`。
- 常规音乐控制只执行 O(1) 播放命令、音量调整和状态读取；按歌曲、歌手、专辑搜索播放会扫描本机 Music 曲库，时间复杂度与曲库规模线性相关。执行搜索播放时只汇报当前播放结果，不输出无关曲库列表，避免暴露不必要的媒体资料。
- 屏幕截图只调用系统截图命令生成一张当前全屏 PNG，时间和空间成本主要取决于屏幕分辨率；截图可能包含敏感信息，返回时只提供图片路径，不额外读取或转述图片内容。
- 通知命令只调用 UserNotifications 提交一条本机立即通知，时间和空间复杂度为 O(1)；通知内容来自用户明确输入，不访问网络、不扫描本机数据，也不持久化通知内容。

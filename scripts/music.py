#!/usr/bin/env python3
"""通过 AppleScript 控制 macOS 音乐应用，并输出稳定 JSON。"""

from __future__ import annotations

import argparse
import json
import subprocess
from typing import Any


APP_PATH = "/System/Applications/Music.app"
OSASCRIPT = "/usr/bin/osascript"


def 输出(success: bool, data: Any = None, message: str = "ok", code: int = 0) -> None:
    print(
        json.dumps(
            {"success": success, "data": data if data is not None else {}, "message": message},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    raise SystemExit(code)


def int_literal(value: int | None) -> str:
    if value is None:
        return "missing value"
    return str(value)


def text_literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def run_applescript(script: str) -> Any:
    # Music 的脚本术语绑定到应用字典；实际控制使用绝对路径，避免本地化名称歧义。
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
        输出(False, message="音乐操作超过 30 秒未返回。请确认 Music 应用和权限状态正常。", code=1)
    if result.returncode != 0:
        输出(False, message=normalize_error(result.stderr or result.stdout), code=1)

    raw = result.stdout.strip()
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        输出(False, message="音乐应用返回了非 JSON 输出，无法解析。", code=1)


def normalize_error(raw: str) -> str:
    text = " ".join(raw.strip().split())
    lower = text.lower()
    if "-10000" in text:
        message = text.replace("execution error:", "", 1).replace("(-10000)", "").strip()
        return message or "音乐操作失败。"
    if any(token in lower for token in ["not authorized", "not allowed", "privacy", "automation"]):
        return "没有权限控制音乐应用。请到「系统设置 > 隐私与安全性」允许当前终端或 Codex 访问「音乐」和自动化控制。"
    if "-1743" in text or "-10827" in text:
        return "无法控制音乐应用，通常是 macOS 隐私权限或自动化权限未开启。请到「系统设置 > 隐私与安全性」授权后重试。"
    if "-1728" in text:
        return "无法访问音乐应用对象。请确认 Music 应用可用，并已授予自动化权限。"
    return text or "音乐操作失败。"


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

on trackJson()
    tell application "''' + APP_PATH + r'''"
        try
            set t to current track
            set trackName to name of t
            set trackArtist to artist of t
            set trackAlbum to album of t
            set trackDuration to duration of t
            return "{" & ¬
                quote & "name" & quote & ":" & my nullableTextJson(trackName) & "," & ¬
                quote & "artist" & quote & ":" & my nullableTextJson(trackArtist) & "," & ¬
                quote & "album" & quote & ":" & my nullableTextJson(trackAlbum) & "," & ¬
                quote & "duration" & quote & ":" & (trackDuration as text) & ¬
                "}"
        on error
            return "null"
        end try
    end tell
end trackJson
'''


def build_status_script(_: argparse.Namespace) -> str:
    return common_library() + f'''
tell application "{APP_PATH}"
    set stateText to player state as text
    set volumeValue to sound volume
    set shuffleValue to shuffle enabled
    set repeatValue to song repeat as text
    set trackPayload to my trackJson()
end tell
return "{{" & quote & "player_state" & quote & ":" & my jsonEscape(stateText) & "," & quote & "volume" & quote & ":" & (volumeValue as text) & "," & quote & "shuffle_enabled" & quote & ":" & (shuffleValue as text) & "," & quote & "repeat_mode" & quote & ":" & my jsonEscape(repeatValue) & "," & quote & "current_track" & quote & ":" & trackPayload & "}}"
'''


def build_play_pause_script(_: argparse.Namespace) -> str:
    return common_library() + f'''
tell application "{APP_PATH}"
    playpause
    set stateText to player state as text
end tell
return "{{" & quote & "player_state" & quote & ":" & my jsonEscape(stateText) & "}}"
'''


def build_play_script(_: argparse.Namespace) -> str:
    return common_library() + f'''
tell application "{APP_PATH}"
    play
    set stateText to player state as text
end tell
return "{{" & quote & "player_state" & quote & ":" & my jsonEscape(stateText) & "}}"
'''


def build_pause_script(_: argparse.Namespace) -> str:
    return common_library() + f'''
tell application "{APP_PATH}"
    pause
    set stateText to player state as text
end tell
return "{{" & quote & "player_state" & quote & ":" & my jsonEscape(stateText) & "}}"
'''


def build_next_script(_: argparse.Namespace) -> str:
    return common_library() + f'''
tell application "{APP_PATH}"
    next track
    set trackPayload to my trackJson()
end tell
return "{{" & quote & "current_track" & quote & ":" & trackPayload & "}}"
'''


def build_previous_script(_: argparse.Namespace) -> str:
    return common_library() + f'''
tell application "{APP_PATH}"
    previous track
    set trackPayload to my trackJson()
end tell
return "{{" & quote & "current_track" & quote & ":" & trackPayload & "}}"
'''


def build_volume_script(args: argparse.Namespace) -> str:
    if args.level is not None:
        level = int_literal(args.level)
        volume_action = f"set sound volume to {level}"
    else:
        delta = int_literal(args.delta)
        volume_action = f"""set targetVolume to (sound volume) + {delta}
    if targetVolume < 0 then set targetVolume to 0
    if targetVolume > 100 then set targetVolume to 100
    set sound volume to targetVolume"""
    return common_library() + f'''
tell application "{APP_PATH}"
    {volume_action}
    set volumeValue to sound volume
end tell
return "{{" & quote & "volume" & quote & ":" & (volumeValue as text) & "}}"
'''


def build_shuffle_script(args: argparse.Namespace) -> str:
    enabled = "true" if args.enabled else "false"
    return common_library() + f'''
tell application "{APP_PATH}"
    set shuffle enabled to {enabled}
    set shuffleValue to shuffle enabled
end tell
return "{{" & quote & "shuffle_enabled" & quote & ":" & (shuffleValue as text) & "}}"
'''


def build_repeat_script(args: argparse.Namespace) -> str:
    return common_library() + f'''
tell application "{APP_PATH}"
    set song repeat to {args.mode}
    set repeatValue to song repeat as text
end tell
return "{{" & quote & "repeat_mode" & quote & ":" & my jsonEscape(repeatValue) & "}}"
'''


def build_play_song_script(args: argparse.Namespace) -> str:
    name = text_literal(args.name)
    artist_filter = ""
    if args.artist:
        artist = text_literal(args.artist)
        artist_filter = f" and artist contains {artist}"
    return build_search_play_script(f"name contains {name}{artist_filter}", "没有找到匹配的歌曲。")


def build_play_artist_script(args: argparse.Namespace) -> str:
    artist = text_literal(args.name)
    return build_search_play_script(f"artist contains {artist}", "没有找到匹配歌手的歌曲。")


def build_play_album_script(args: argparse.Namespace) -> str:
    album = text_literal(args.name)
    artist_filter = ""
    if args.artist:
        artist = text_literal(args.artist)
        artist_filter = f" and artist contains {artist}"
    return build_search_play_script(f"album contains {album}{artist_filter}", "没有找到匹配专辑的歌曲。")


def build_search_play_script(filter_clause: str, not_found_message: str) -> str:
    message = text_literal(not_found_message)
    return common_library() + f'''
tell application "{APP_PATH}"
    set matches to tracks of library playlist 1 whose {filter_clause}
    if (count of matches) is 0 then error {message} number -10000
    set targetTrack to item 1 of matches
    play targetTrack
    set stateText to player state as text
    set trackPayload to my trackJson()
end tell
return "{{" & quote & "player_state" & quote & ":" & my jsonEscape(stateText) & "," & quote & "current_track" & quote & ":" & trackPayload & "}}"
'''


def validate_volume(value: str) -> int:
    try:
        level = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("音量必须是整数。") from exc
    if level < 0 or level > 100:
        raise argparse.ArgumentTypeError("音量必须在 0 到 100 之间。")
    return level


def validate_volume_delta(value: str) -> int:
    try:
        delta = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("音量增量必须是整数。") from exc
    if delta < -100 or delta > 100:
        raise argparse.ArgumentTypeError("音量增量必须在 -100 到 100 之间。")
    return delta


def validate_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise argparse.ArgumentTypeError("开关值必须是 true 或 false。")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="控制本机 macOS 音乐应用。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="读取播放状态、音量和当前曲目。")
    subparsers.add_parser("play-pause", help="切换播放或暂停。")
    subparsers.add_parser("play", help="开始播放。")
    subparsers.add_parser("pause", help="暂停播放。")
    subparsers.add_parser("next", help="播放下一首。")
    subparsers.add_parser("previous", help="播放上一首。")

    volume = subparsers.add_parser("volume", help="设置或调整音量。")
    volume_group = volume.add_mutually_exclusive_group(required=True)
    volume_group.add_argument("--level", type=validate_volume, help="音量，范围 0 到 100。")
    volume_group.add_argument("--delta", type=validate_volume_delta, help="音量增量，范围 -100 到 100。")

    shuffle = subparsers.add_parser("shuffle", help="设置随机播放开关。")
    shuffle.add_argument("--enabled", required=True, type=validate_bool, help="是否开启随机播放：true 或 false。")

    repeat = subparsers.add_parser("repeat", help="设置循环播放模式。")
    repeat.add_argument("--mode", required=True, choices=["off", "one", "all"], help="循环模式：off、one 或 all。")

    play_song = subparsers.add_parser("play-song", help="按歌曲名搜索并播放首个匹配歌曲。")
    play_song.add_argument("--name", required=True, help="歌曲名，支持模糊匹配。")
    play_song.add_argument("--artist", help="可选歌手名，用于缩小匹配范围。")

    play_artist = subparsers.add_parser("play-artist", help="播放指定歌手的首个匹配歌曲。")
    play_artist.add_argument("--name", required=True, help="歌手名，支持模糊匹配。")

    play_album = subparsers.add_parser("play-album", help="播放指定专辑的首个匹配歌曲。")
    play_album.add_argument("--name", required=True, help="专辑名，支持模糊匹配。")
    play_album.add_argument("--artist", help="可选歌手名，用于缩小匹配范围。")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    builders = {
        "status": build_status_script,
        "play-pause": build_play_pause_script,
        "play": build_play_script,
        "pause": build_pause_script,
        "next": build_next_script,
        "previous": build_previous_script,
        "volume": build_volume_script,
        "shuffle": build_shuffle_script,
        "repeat": build_repeat_script,
        "play-song": build_play_song_script,
        "play-artist": build_play_artist_script,
        "play-album": build_play_album_script,
    }
    data = run_applescript(builders[args.command](args))
    输出(True, data=data)


if __name__ == "__main__":
    main()

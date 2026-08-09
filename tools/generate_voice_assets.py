from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import edge_tts


ROOT = Path(__file__).resolve().parents[1]
PROFILES = {
    "female": {
        "voice": "zh-CN-XiaoxiaoNeural",
        "out_dir": ROOT / "web" / "static" / "audio" / "voice",
        "url_prefix": "/audio/voice",
    },
    "male": {
        "voice": "zh-CN-YunyangNeural",
        "out_dir": ROOT / "web" / "static" / "audio" / "voice-male",
        "url_prefix": "/audio/voice-male",
    },
}

RATE = "-4%"
VOLUME = "+0%"


def slug(text: str) -> str:
    mapping = {
        "，": "_",
        "。": "",
        "、": "_",
        " ": "_",
        "/": "_",
        "：": "_",
        "秒": "s",
        "分钟": "min",
        "号球": "ball",
        "一门得分": "gate1",
        "二门得分": "gate2",
        "三门得分": "gate3",
        "中柱得分": "pillar",
        "撤销": "undo",
        "没有可撤销记录": "no_undo",
        "比赛": "match",
        "开始": "start",
        "暂停": "pause",
        "继续": "resume",
        "时间到": "time_up",
        "请输入密码结束比赛": "finish_password",
    }
    value = text
    for old, new in mapping.items():
        value = value.replace(old, new)
    return value


def build_phrases() -> dict[str, str]:
    phrases: dict[str, str] = {
        "match_start": "比赛开始",
        "match_pause": "比赛暂停",
        "match_resume": "比赛继续",
        "match_waiting": "等待开始",
        "next_match_waiting": "下一场比赛，等待开始",
        "time_up": "时间到",
        "finish_password_prompt": "请输入密码结束比赛",
        "password_wrong": "密码错误",
        "settings_saved": "设置已保存",
        "key_binding_saved": "按键映射已保存",
        "key_binding_failed": "按键映射失败",
        "selection_required": "请先选择球号",
        "scoring_paused_denied": "暂停期间不能计分",
        "team_swap_saved": "红白队名已更换",
        "team_name_empty": "队名为空",
        "red_team_saved": "红队队名已保存",
        "white_team_saved": "白队队名已保存",
        "unknown_team": "未知队伍",
        "unknown_action": "未知操作",
        "countdown_10": "倒计时10秒",
        "countdown_10_stopped": "10秒倒计时已停止",
    }

    for minute in [15, 10, 5, 1]:
        phrases[f"time_remaining_{minute}min"] = f"比赛时间剩余 {minute} 分钟"

    for number in range(1, 11):
        phrases[f"ball_{number}"] = f"{number}号球"
        phrases[f"ball_{number}_gate1"] = f"{number}号球，一门得分"
        phrases[f"ball_{number}_gate2"] = f"{number}号球，二门得分"
        phrases[f"ball_{number}_gate3"] = f"{number}号球，三门得分"
        phrases[f"ball_{number}_pillar"] = f"{number}号球，中柱得分"
        phrases[f"ball_{number}_limit"] = f"{number}号球已到上限"
        phrases[f"ball_{number}_no_undo"] = f"{number}号球没有可撤销记录"
        phrases[f"undo_ball_{number}_gate1"] = f"撤销，{number}号球，一门得分"
        phrases[f"undo_ball_{number}_gate2"] = f"撤销，{number}号球，二门得分"
        phrases[f"undo_ball_{number}_gate3"] = f"撤销，{number}号球，三门得分"
        phrases[f"undo_ball_{number}_pillar"] = f"撤销，{number}号球，中柱得分"
        phrases[f"undo_ball_{number}_zero"] = f"撤销，{number}号球，回到0分"

    return phrases


async def generate_one(key: str, text: str, profile: dict[str, object]) -> dict[str, str]:
    out_dir = profile["out_dir"]
    voice = str(profile["voice"])
    url_prefix = str(profile["url_prefix"])
    path = out_dir / f"{key}.mp3"
    if not path.exists() or path.stat().st_size == 0:
        for attempt in range(6):
            try:
                communicate = edge_tts.Communicate(text, voice, rate=RATE, volume=VOLUME)
                await communicate.save(str(path))
                if path.stat().st_size > 0:
                    break
            except Exception:
                if attempt == 5:
                    raise
                await asyncio.sleep(3)
    return {"text": text, "file": f"{url_prefix}/{path.name}"}


async def generate_profile(profile_name: str, profile: dict[str, object]) -> None:
    out_dir = profile["out_dir"]
    voice = str(profile["voice"])
    out_dir.mkdir(parents=True, exist_ok=True)
    phrases = build_phrases()
    manifest = {
        "profile": profile_name,
        "voice": voice,
        "rate": RATE,
        "volume": VOLUME,
        "items": {},
    }
    for key, text in phrases.items():
        manifest["items"][key] = await generate_one(key, text, profile)
        print(f"{profile_name}:{key}: {text}")
        await asyncio.sleep(0.8)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"generated {len(phrases)} files in {out_dir}")


async def main() -> None:
    selected = sys.argv[1:] or list(PROFILES)
    for profile_name in selected:
        profile = PROFILES[profile_name]
        await generate_profile(profile_name, profile)


if __name__ == "__main__":
    asyncio.run(main())

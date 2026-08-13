from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sys
from pathlib import Path

import edge_tts


ROOT = Path(__file__).resolve().parents[1]
PROFILES = {
    "female": {
        "voice": "zh-CN-XiaoxiaoNeural",
        "out_dir": ROOT / "web" / "static" / "audio" / "voice-cn-female",
        "url_prefix": "/audio/voice-cn-female",
        "language": "zh",
    },
    "male": {
        "voice": "zh-CN-YunyangNeural",
        "out_dir": ROOT / "web" / "static" / "audio" / "voice-cn-male",
        "url_prefix": "/audio/voice-cn-male",
        "language": "zh",
    },
    "ko-female": {
        "voice": "ko-KR-SunHiNeural",
        "out_dir": ROOT / "web" / "static" / "audio" / "voice-ko-female",
        "url_prefix": "/audio/voice-ko-female",
        "language": "ko",
    },
    "ko-male": {
        "voice": "ko-KR-InJoonNeural",
        "out_dir": ROOT / "web" / "static" / "audio" / "voice-ko-male",
        "url_prefix": "/audio/voice-ko-male",
        "language": "ko",
    },
}

RATE = "-4%"
VOLUME = "+0%"
TEAM_NAME_DIR = ROOT / "web" / "static" / "audio" / "team-names"


def safe_voice_key(text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
    return digest


def team_name_audio_path(profile_name: str, team: str, name: str) -> tuple[Path, str]:
    safe_team = re.sub(r"[^a-zA-Z0-9_-]+", "-", team).strip("-") or "team"
    filename = f"{safe_team}-{safe_voice_key(name)}.mp3"
    out_dir = TEAM_NAME_DIR / profile_name
    return out_dir / filename, f"/audio/team-names/{profile_name}/{filename}"


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


def build_zh_phrases() -> dict[str, str]:
    phrases: dict[str, str] = {
        "match_start": "比赛开始",
        "match_pause": "比赛暂停",
        "match_resume": "比赛继续",
        "match_waiting": "等待开始",
        "next_match_waiting": "下一场比赛，等待开始",
        "time_up": "时间到",
        "match_finished": "比赛结束",
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


def build_ko_phrases() -> dict[str, str]:
    phrases: dict[str, str] = {
        "match_start": "경기 시작합니다",
        "match_pause": "경기 중지",
        "match_resume": "경기 재개합니다",
        "match_waiting": "경기 대기",
        "next_match_waiting": "다음 경기 대기",
        "time_up": "경기 시간이 종료되었습니다",
        "match_finished": "경기가 종료되었습니다",
        "finish_password_prompt": "경기를 종료하려면 비밀번호를 입력하세요",
        "password_wrong": "비밀번호가 맞지 않습니다",
        "settings_saved": "설정 저장되었습니다",
        "key_binding_saved": "키 설정 저장되었습니다",
        "key_binding_failed": "키 설정 실패",
        "selection_required": "공 번호를 먼저 선택하세요",
        "scoring_paused_denied": "중지 중에는 득점할 수 없습니다",
        "team_swap_saved": "홍팀과 백팀 이름을 바꿨습니다",
        "team_name_empty": "팀 이름이 비어 있습니다",
        "red_team_saved": "홍팀 이름 저장되었습니다",
        "white_team_saved": "백팀 이름 저장되었습니다",
        "unknown_team": "알 수 없는 팀입니다",
        "unknown_action": "알 수 없는 조작입니다",
        "countdown_10": "십 초 카운트",
        "countdown_10_stopped": "십 초 카운트를 멈췄습니다",
    }

    for minute in [15, 10, 5, 1]:
        phrases[f"time_remaining_{minute}min"] = f"경기 종료 {minute}분전입니다"

    for score in range(0, 101):
        phrases[f"score_{score}"] = f"{score}점"

    phrases.update(
        {
            "score_total": "총점",
            "red_team": "홍팀",
            "white_team": "백팀",
            "winner_red_prefix": "홍팀",
            "winner_white_prefix": "백팀",
            "winner_suffix": "승리를 축하합니다",
            "draw_game": "무승부입니다",
            "versus": "대",
        }
    )

    korean_ball_numbers = {
        1: "일",
        2: "이",
        3: "삼",
        4: "사",
        5: "오",
        6: "육",
        7: "칠",
        8: "팔",
        9: "구",
        10: "십",
    }

    for number in range(1, 11):
        team = "홍팀" if number % 2 == 1 else "백팀"
        ball = f"{korean_ball_numbers[number]} 번 공"
        phrases[f"ball_{number}"] = ball
        phrases[f"ball_{number}_gate1"] = f"{team} {ball}, 제1게이트 통과"
        phrases[f"ball_{number}_gate2"] = f"{team} {ball}, 제2게이트 통과"
        phrases[f"ball_{number}_gate3"] = f"{team} {ball}, 제3게이트 통과"
        phrases[f"ball_{number}_pillar"] = f"{team} {ball}, 골폴 명중"
        phrases[f"ball_{number}_limit"] = f"{ball}, 더 이상 득점할 수 없습니다"
        phrases[f"ball_{number}_no_undo"] = f"{ball}, 취소할 기록이 없습니다"
        phrases[f"undo_ball_{number}_gate1"] = f"{team} {ball}, 제1게이트 통과를 취소하였습니다"
        phrases[f"undo_ball_{number}_gate2"] = f"{team} {ball}, 제2게이트 통과를 취소하였습니다"
        phrases[f"undo_ball_{number}_gate3"] = f"{team} {ball}, 제3게이트 통과를 취소하였습니다"
        phrases[f"undo_ball_{number}_pillar"] = f"{team} {ball}, 골폴 명중을 취소하였습니다"
        phrases[f"undo_ball_{number}_zero"] = f"{ball}, 0점으로 취소하였습니다"

    return phrases


def build_phrases(language: str = "zh") -> dict[str, str]:
    if language == "ko":
        return build_ko_phrases()
    phrases = build_zh_phrases()
    for score in range(0, 101):
        phrases[f"score_{score}"] = f"{score}分"
    phrases.update(
        {
            "score_total": "总分",
            "red_team": "红队",
            "white_team": "白队",
            "winner_red_prefix": "祝贺红队",
            "winner_white_prefix": "祝贺白队",
            "winner_suffix": "取得胜利",
            "draw_game": "双方平局",
            "versus": "对阵",
        }
    )
    return phrases


async def generate_one(key: str, text: str, profile: dict[str, object]) -> dict[str, str]:
    out_dir = profile["out_dir"]
    voice = str(profile["voice"])
    url_prefix = str(profile["url_prefix"])
    path = out_dir / f"{key}.mp3"
    needs_generation = not path.exists() or path.stat().st_size == 0
    if needs_generation:
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


async def generate_team_name(profile_name: str, team: str, name: str) -> dict[str, str]:
    profile = PROFILES[profile_name]
    out_path, url = team_name_audio_path(profile_name, team, name)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not out_path.exists() or out_path.stat().st_size == 0:
        for attempt in range(6):
            try:
                communicate = edge_tts.Communicate(name, str(profile["voice"]), rate=RATE, volume=VOLUME)
                await communicate.save(str(out_path))
                if out_path.stat().st_size > 0:
                    break
            except Exception:
                if attempt == 5:
                    raise
                await asyncio.sleep(3)
    return {"text": name, "file": url}


async def generate_profile(profile_name: str, profile: dict[str, object]) -> None:
    out_dir = profile["out_dir"]
    voice = str(profile["voice"])
    out_dir.mkdir(parents=True, exist_ok=True)
    language = str(profile.get("language", "zh"))
    phrases = build_phrases(language)
    manifest = {
        "profile": profile_name,
        "voice": voice,
        "language": language,
        "rate": RATE,
        "volume": VOLUME,
        "items": {},
    }
    for key, text in phrases.items():
        needs_generation = not (out_dir / f"{key}.mp3").exists()
        manifest["items"][key] = await generate_one(key, text, profile)
        print(f"{profile_name}:{key}: {text}")
        if needs_generation:
            await asyncio.sleep(0.8)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"generated {len(phrases)} files in {out_dir}")


async def main() -> None:
    if len(sys.argv) >= 5 and sys.argv[1] == "team-name":
        result = await generate_team_name(sys.argv[2], sys.argv[3], sys.argv[4])
        print(json.dumps(result, ensure_ascii=False))
        return
    selected = sys.argv[1:] or list(PROFILES)
    for profile_name in selected:
        profile = PROFILES[profile_name]
        await generate_profile(profile_name, profile)


if __name__ == "__main__":
    asyncio.run(main())

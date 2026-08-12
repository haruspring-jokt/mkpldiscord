"""共通ユーティリティ関数。"""

import re
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import discord

from src.google_services import GoogleSheetsClient

# g-2406-ABC-XYZ や gc-2407-DEF-GHI だけでなく、g-202409-... のような 6 桁表記も受け付けます。
CHANNEL_PATTERN = re.compile(r"^(gc?)-(?P<yymm>\d{4}|\d{6})-(?P<rest>.+)$")


def _normalize_month_code(code: str) -> int:
    """yyMM / YYYYMM のどちらでも同じ数値に正規化します。"""
    value = str(code).strip()
    if len(value) == 4 and value.isdigit():
        return int(f"20{value}")
    if len(value) == 6 and value.isdigit():
        return int(value)
    raise ValueError(f"unsupported month code: {code!r}")


def parse_match_channel(channel_name: str) -> dict[str, str] | None:
    """試合チャンネル名を解析してメタデータを返します。"""
    match = CHANNEL_PATTERN.match(channel_name)
    if not match:
        return None

    prefix = match.group(1)
    yymm = match.group("yymm")
    rest = match.group("rest")
    if "-" not in rest:
        return None
    home, away = rest.rsplit("-", 1)
    # g- で始まるチャンネルは div1、gc- で始まるチャンネルは div2 それ以外は空文字
    division = "div1" if prefix == "g" else "div2" if prefix == "gc" else ""
    return {"yymm": yymm, "home": home, "away": away, "division": division}


def is_month_within_season(
    yymm: str, season_first_month: str, season_last_month: str
) -> bool:
    """試合月がシーズン範囲内かどうかを判定します。"""
    if not yymm or not season_first_month or not season_last_month:
        return True
    try:
        yymm_num = _normalize_month_code(yymm)
        first_num = _normalize_month_code(season_first_month)
        last_num = _normalize_month_code(season_last_month)
    except ValueError:
        return False
    return first_num <= yymm_num <= last_num


def find_club_role_mention(
    guild: discord.Guild, alias: str, alias_to_role: dict[str, str]
) -> str:
    """略称からクラブロールを検索し、メンション文字列を返します。"""
    role_name = alias_to_role.get(alias.casefold(), alias)
    for role in guild.roles:
        if role.name == role_name:
            return role.mention
    return f"@{role_name}"


def format_match_reminder(
    guild: discord.Guild,
    home_alias: str,
    away_alias: str,
    alias_to_role: dict[str, str],
) -> str:
    """リマインドメッセージ本文を作成します。"""
    home_mention = find_club_role_mention(guild, home_alias, alias_to_role)
    away_mention = find_club_role_mention(guild, away_alias, alias_to_role)
    return (
        f"{home_mention} {away_mention}\n"
        "# 前月10日リマインド\n"
        "前月の10日までに、アウェイ側は試合可能な日程を複数提出してください。候補日についてクラブ内部で相談中の場合は、いつごろまでに提出することができるかなど、状況を共有してください。"
    )


def get_target_month_codes(now: datetime) -> list[str]:
    """現在日時から対象試合月コード(yyMM)を生成します。"""
    next_month = now.month % 12 + 1
    next_year = now.year + (now.month // 12)
    return [f"{str(next_year)[2:]}{next_month:02d}"]


def get_target_yymm_for_channel_creation(now: datetime) -> str:
    """現在月の2ヶ月後の試合月コード(yyMM)を生成します。"""
    month_offset = (now.month - 1 + 2) % 12
    year_offset = (now.month - 1 + 2) // 12
    target_year = now.year + year_offset
    target_month = month_offset + 1
    return f"{str(target_year)[2:]}{target_month:02d}"


def normalize_yymm_from_sheet_value(value: object) -> str:
    """シート上の yy/mm / yymm / yyyy/mm を yymm へ正規化します。"""
    if value is None or value is False:
        return ""
    raw = str(value).strip()
    if not raw or raw.lower() in {"false", "none", "null"}:
        return ""
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 6 and digits.startswith("20"):
        return digits[2:]
    if len(digits) == 6:
        return digits
    if len(digits) == 4:
        return digits
    return ""


def build_match_channel_name(
    prefix: str, yymm: str, home_alias: str, away_alias: str
) -> str:
    """試合チャンネル名を生成します。"""
    return f"{prefix}-{yymm}-{home_alias}-{away_alias}"


def find_game_row(
    sheets: GoogleSheetsClient, division: str, home_cid: str, away_cid: str
) -> tuple[int, list[Any]] | None:
    """管理スプレッドシートの Game シートから該当する試合行を検索します。"""
    values = sheets.get_values("Game!A1:O200", division)
    for idx, row in enumerate(values, start=1):
        home_val = row[5].strip() if len(row) > 5 else ""
        away_val = row[6].strip() if len(row) > 6 else ""
        if home_val == home_cid and away_val == away_cid:
            return idx, row
    return None


def find_location_row(
    sheets: GoogleSheetsClient, home_cid: str, away_cid: str
) -> int | None:
    """場所調整シートから該当する試合行を検索します。"""
    values = sheets.get_values("場所調整!A1:P200", "shared")
    for idx, row in enumerate(values, start=1):
        home_val = row[2].strip() if len(row) > 2 else ""
        away_val = row[4].strip() if len(row) > 4 else ""
        if home_val == home_cid and away_val == away_cid:
            return idx
    return None


def build_gcal_link(
    event_name: str, start_dt: datetime, end_dt: datetime, details_text: str
) -> str:
    """Google カレンダーのイベント作成リンクを生成します。"""

    def to_utc_stamp(dt: datetime) -> str:
        return dt.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")

    dates_param = f"{to_utc_stamp(start_dt)}/{to_utc_stamp(end_dt)}"
    return (
        "https://calendar.google.com/calendar/u/0/r/eventedit"
        f"?text={quote(event_name)}&dates={dates_param}&details={quote(details_text)}"
    )

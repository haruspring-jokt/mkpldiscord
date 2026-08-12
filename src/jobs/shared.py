"""ジョブ間で共有する補助関数。"""

from __future__ import annotations

import os

import discord
from discord.ext import commands

from src.utils import parse_match_channel


def is_reminder_target_channel(
    bot: commands.Bot,
    channel_name: str,
    shared_rows: list[list[str]] | None = None,
) -> bool:
    """チャンネル名から共有シートの対象レコードを特定し、L列が '調整' のときだけ true を返す。"""
    metadata = parse_match_channel(channel_name)
    if not metadata:
        return False

    home = metadata["home"]
    away = metadata["away"]
    home_cid = bot.club_cid_map.get(home.casefold())
    away_cid = bot.club_cid_map.get(away.casefold())
    if not home_cid or not away_cid:
        return False

    values = (
        shared_rows
        if shared_rows is not None
        else bot.sheets.get_values("場所調整!A1:Z200", "shared")
    )
    for row in values:
        if len(row) <= 4:
            continue
        if row[2].strip() != home_cid or row[4].strip() != away_cid:
            continue
        status = row[11].strip() if len(row) > 11 else ""
        return status == "調整"
    return False


def get_active_category_ids() -> dict[str, set[int]]:
    """有効試合チャンネルのカテゴリIDを division ごとに取得します。"""
    ids: dict[str, set[int]] = {"div1": set(), "div2": set()}
    for division, env_name in (
        ("div1", "DISCORD_CATEGORY_ID_DIV1"),
        ("div2", "DISCORD_CATEGORY_ID_DIV2"),
    ):
        raw = os.getenv(env_name, "")
        for item in str(raw).split(","):
            value = item.strip()
            if not value:
                continue
            try:
                ids[division].add(int(value))
            except ValueError:
                print(f"[DAILY-BATCH] invalid category id '{value}' in {env_name}")
    return ids

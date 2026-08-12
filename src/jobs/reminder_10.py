"""10日リマインダージョブ。"""

import os
from datetime import datetime

from discord.ext import commands

from src.jobs.shared import is_reminder_target_channel
from src.utils import (
    format_match_reminder,
    get_target_month_codes,
    is_month_within_season,
    parse_match_channel,
)


async def send_10th_reminders(bot: commands.Bot, alias_to_role: dict[str, str]) -> None:
    """前月10日リマインド対象の試合チャンネルへ送信します。"""
    now = datetime.now()
    target_yymms = get_target_month_codes(now)
    dry_run = os.getenv("REMINDER_DRY_RUN", "0") in ("1", "true", "True")
    print(
        f"[REMINDER] trigger at {now.isoformat()}, target yymm={target_yymms} dry_run={dry_run}"
    )

    if not bot.guilds:
        print("[REMINDER] no guilds available")
        return

    season_first_month = os.getenv("LEAGUE_CURRENT_SEASON_FIRST_MONTH", "").strip()
    season_last_month = os.getenv("LEAGUE_CURRENT_SEASON_LAST_MONTH", "").strip()
    shared_rows = bot.sheets.get_values("場所調整!A1:Z200", "shared")

    for guild in bot.guilds:
        if not guild.text_channels:
            continue

        for channel in guild.text_channels:
            metadata = parse_match_channel(channel.name)
            if not metadata:
                continue
            if not is_month_within_season(
                metadata["yymm"], season_first_month, season_last_month
            ):
                continue
            if metadata["yymm"] not in target_yymms:
                continue
            if not is_reminder_target_channel(bot, channel.name, shared_rows):
                continue

            home = metadata["home"]
            away = metadata["away"]
            if dry_run:
                try:
                    message = format_match_reminder(guild, home, away, alias_to_role)
                    snippet = message.replace("\n", " ")[:300]
                    print(
                        f"[REMINDER-DRY] would send to {channel.name} ({channel.id}): {snippet}"
                    )
                except Exception as exc:
                    print(
                        f"[REMINDER-DRY] formatting failed for {channel.name} ({channel.id}): {exc}"
                    )
            else:
                try:
                    message = format_match_reminder(guild, home, away, alias_to_role)
                    await channel.send(message)
                    print(f"[REMINDER] sent reminder to {channel.name} ({channel.id})")
                except Exception as exc:
                    print(
                        f"[REMINDER] failed to send reminder to {channel.name} ({channel.id}): {exc}"
                    )

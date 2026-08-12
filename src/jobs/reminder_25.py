"""25日リマインダージョブ。"""

import os
from datetime import datetime

from discord.ext import commands

from src.jobs.shared import is_reminder_target_channel
from src.utils import (
    find_club_role_mention,
    get_target_month_codes,
    is_month_within_season,
    parse_match_channel,
)


async def send_25th_reminders(bot: commands.Bot, alias_to_role: dict[str, str]) -> None:
    """前月25日9時のリマインダー送信ロジック。"""
    now = datetime.now()
    target_yymms = get_target_month_codes(now)
    dry_run = os.getenv("REMINDER_DRY_RUN", "0") in ("1", "true", "True")
    print(
        f"[REMINDER-25] trigger at {now.isoformat()}, target yymm={target_yymms} dry_run={dry_run}"
    )

    if not bot.guilds:
        return

    season_first_month = os.getenv("LEAGUE_CURRENT_SEASON_FIRST_MONTH", "").strip()
    season_last_month = os.getenv("LEAGUE_CURRENT_SEASON_LAST_MONTH", "").strip()
    shared_rows = bot.sheets.get_values("場所調整!A1:Z200", "shared")

    for guild in bot.guilds:
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
            message = (
                f"{find_club_role_mention(guild, home, alias_to_role)} {find_club_role_mention(guild, away, alias_to_role)}\n"
                "# 前月25日リマインド\n"
                "前月の末日までに、試合時間と会場を決定し運営に報告してください。予定していた試合月に試合を実施することが難しい場合は、運営に対して延期する旨を連絡してください。"
            )
            if dry_run:
                print(
                    f"[REMINDER-25-DRY] would send to {channel.name} ({channel.id}): {message.replace('\n',' ')[:300]}"
                )
            else:
                try:
                    await channel.send(message)
                    print(f"[REMINDER-25] sent to {channel.name} ({channel.id})")
                except Exception as exc:
                    print(
                        f"[REMINDER-25] failed to send to {channel.name} ({channel.id}): {exc}"
                    )

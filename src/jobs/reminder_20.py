"""20日リマインダージョブ。"""

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


async def send_20th_reminders(bot: commands.Bot, alias_to_role: dict[str, str]) -> None:
    """前月20日9時のリマインダー送信ロジック。"""
    now = datetime.now()
    target_yymms = get_target_month_codes(now)
    dry_run = os.getenv("REMINDER_DRY_RUN", "0") in ("1", "true", "True")
    print(
        f"[REMINDER-20] trigger at {now.isoformat()}, target yymm={target_yymms} dry_run={dry_run}"
    )

    if not bot.guilds:
        return

    season_first_month = os.getenv("LEAGUE_CURRENT_SEASON_FIRST_MONTH", "").strip()
    season_last_month = os.getenv("LEAGUE_CURRENT_SEASON_LAST_MONTH", "").strip()

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
            if not is_reminder_target_channel(bot, channel.name):
                continue
            home = metadata["home"]
            away = metadata["away"]
            message = (
                f"{find_club_role_mention(guild, home, alias_to_role)} {find_club_role_mention(guild, away, alias_to_role)}\n"
                "# 前月20日リマインド\n"
                "前月の20日までに、ホーム側がアウェイが提出した候補日を参考に試合日程を決定してください。どの候補日も参加できない場合は、改めてクラブ間で相談してください。"
            )
            if dry_run:
                print(
                    f"[REMINDER-20-DRY] would send to {channel.name} ({channel.id}): {message.replace('\n',' ')[:300]}"
                )
            else:
                try:
                    await channel.send(message)
                    print(f"[REMINDER-20] sent to {channel.name} ({channel.id})")
                except Exception as exc:
                    print(
                        f"[REMINDER-20] failed to send to {channel.name} ({channel.id}): {exc}"
                    )

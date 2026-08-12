"""スケジューラによるリマインダー送信処理。"""

import os
from datetime import datetime

import discord

from src.utils import (
    parse_match_channel,
    find_club_role_mention,
    format_match_reminder,
    get_target_month_codes,
)


async def send_monthly_reminders(
    bot: discord.ext.commands.Bot, alias_to_role: dict[str, str]
) -> None:
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

    for guild in bot.guilds:
        if not guild.text_channels:
            continue

        for channel in guild.text_channels:
            metadata = parse_match_channel(channel.name)
            if not metadata:
                continue
            if metadata["yymm"] not in target_yymms:
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


async def send_20th_reminders(
    bot: discord.ext.commands.Bot, alias_to_role: dict[str, str]
) -> None:
    """前月20日9時のリマインダー送信ロジック。"""
    now = datetime.now()
    target_yymms = get_target_month_codes(now)
    dry_run = os.getenv("REMINDER_DRY_RUN", "0") in ("1", "true", "True")
    print(
        f"[REMINDER-20] trigger at {now.isoformat()}, target yymm={target_yymms} dry_run={dry_run}"
    )

    if not bot.guilds:
        return

    for guild in bot.guilds:
        for channel in guild.text_channels:
            metadata = parse_match_channel(channel.name)
            if not metadata:
                continue
            if metadata["yymm"] not in target_yymms:
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


async def send_25th_reminders(
    bot: discord.ext.commands.Bot, alias_to_role: dict[str, str]
) -> None:
    """前月25日9時のリマインダー送信ロジック。"""
    now = datetime.now()
    target_yymms = get_target_month_codes(now)
    dry_run = os.getenv("REMINDER_DRY_RUN", "0") in ("1", "true", "True")
    print(
        f"[REMINDER-25] trigger at {now.isoformat()}, target yymm={target_yymms} dry_run={dry_run}"
    )

    if not bot.guilds:
        return

    for guild in bot.guilds:
        for channel in guild.text_channels:
            metadata = parse_match_channel(channel.name)
            if not metadata:
                continue
            if metadata["yymm"] not in target_yymms:
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

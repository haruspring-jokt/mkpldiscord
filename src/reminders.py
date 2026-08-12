"""スケジューラによるリマインダー送信処理。"""

import os
from datetime import datetime

import discord
from discord.ext import commands

from src.utils import (
    parse_match_channel,
    find_club_role_mention,
    format_match_reminder,
    get_target_month_codes,
    find_location_row,
    is_month_within_season,
)


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


def format_sheet_date(dt: datetime) -> str:
    """Google Sheets へ書き込む日付文字列を返します。"""
    return dt.strftime("%Y/%m/%d")


async def update_last_post_dates_for_match_channels(
    bot: commands.Bot,
) -> None:
    """試合チャンネルごとに最後の非 bot 投稿日を共通調整シートの AB 列へ書き込みます。"""
    if not bot.guilds:
        print("[DAILY-BATCH] no guilds available")
        return

    season_first_month = os.getenv("LEAGUE_CURRENT_SEASON_FIRST_MONTH", "").strip()
    season_last_month = os.getenv("LEAGUE_CURRENT_SEASON_LAST_MONTH", "").strip()
    active_categories = get_active_category_ids()
    if not season_first_month or not season_last_month:
        print("[DAILY-BATCH] season month range is not configured")
        return

    print(
        f"[DAILY-BATCH] start season={season_first_month}..{season_last_month} categories={active_categories}"
    )

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

            category_id = getattr(channel.category, "id", None)
            if category_id is None:
                continue

            division_key = metadata["division"]
            allowed_categories = active_categories.get(division_key, set())
            if category_id not in allowed_categories:
                continue

            home_cid = bot.club_cid_map.get(metadata["home"].casefold())
            away_cid = bot.club_cid_map.get(metadata["away"].casefold())
            if not home_cid or not away_cid:
                print(
                    f"[DAILY-BATCH] skip {channel.name} because club CID lookup failed for home={metadata['home']}, away={metadata['away']}"
                )
                continue

            row_idx = find_location_row(bot.sheets, home_cid, away_cid)
            if row_idx is None:
                print(
                    f"[DAILY-BATCH] no shared-sheet row found for {channel.name} ({home_cid} vs {away_cid})"
                )
                continue

            try:
                last_message = None
                async for message in channel.history(limit=200, oldest_first=False):
                    if message.author.bot:
                        continue
                    last_message = message
                    break
            except Exception as exc:
                print(
                    f"[DAILY-BATCH] could not inspect history for {channel.name}: {exc}"
                )
                continue

            if last_message is None:
                print(
                    f"[DAILY-BATCH] no non-bot message found in {channel.name}; skip update"
                )
                continue

            sheet_date = format_sheet_date(last_message.created_at.astimezone())
            try:
                bot.sheets.update_range(
                    f"場所調整!AB{row_idx}", [[sheet_date]], "shared"
                )
                print(
                    f"[DAILY-BATCH] updated {channel.name} -> AB{row_idx} = {sheet_date} (last non-bot post by {last_message.author})"
                )
            except Exception as exc:
                print(
                    f"[DAILY-BATCH] failed to update {channel.name} AB{row_idx}: {exc}"
                )


async def send_monthly_reminders(
    bot: commands.Bot, alias_to_role: dict[str, str]
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

    season_first_month = os.getenv("LEAGUE_CURRENT_SEASON_FIRST_MONTH", "").strip()
    season_last_month = os.getenv("LEAGUE_CURRENT_SEASON_LAST_MONTH", "").strip()

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

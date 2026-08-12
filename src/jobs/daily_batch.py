"""日次更新ジョブ。"""

import os
from datetime import datetime

from discord.ext import commands

from src.jobs.shared import get_active_category_ids
from src.utils import find_location_row, is_month_within_season, parse_match_channel


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

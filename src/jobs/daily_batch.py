"""日次更新ジョブ。"""

import os
from datetime import datetime

from discord.ext import commands

from src.jobs.shared import get_active_category_ids
from src.utils import is_month_within_season, parse_match_channel


def format_sheet_date(dt: datetime, now: datetime | None = None) -> str:
    """現在日時との差分を「◯日前」形式で返します。5日以上は「5日以上前」と表記します。"""
    if now is None:
        now = datetime.now()
    delta_days = (now.date() - dt.date()).days
    if delta_days <= 0:
        return "0日前"
    if delta_days >= 5:
        return "5日以上前"
    return f"{delta_days}日前"


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

    location_rows = bot.sheets.get_values("場所調整!A1:Z200", "shared")
    location_index: dict[tuple[str, str], tuple[int, list[str]]] = {}
    for row_idx, row in enumerate(location_rows, start=1):
        if len(row) <= 4:
            continue
        home_cid = row[2].strip()
        away_cid = row[4].strip()
        if not home_cid or not away_cid:
            continue
        location_index[(home_cid, away_cid)] = (row_idx, row)

    update_requests: list[tuple[str, list[list[str]]]] = []

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

            row_info = location_index.get((home_cid, away_cid))
            if row_info is None:
                print(
                    f"[DAILY-BATCH] no shared-sheet row found for {channel.name} ({home_cid} vs {away_cid})"
                )
                continue

            row_idx, row = row_info
            status_value = row[11].strip() if len(row) > 11 else ""
            if status_value != "調整":
                update_requests.append((f"場所調整!AB{row_idx}", [[""]]))
                print(
                    f"[DAILY-BATCH] cleared stale AB{row_idx} for {channel.name} because status is '{status_value}'"
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
            update_requests.append((f"場所調整!AB{row_idx}", [[sheet_date]]))
            print(
                f"[DAILY-BATCH] queued update for {channel.name} -> AB{row_idx} = {sheet_date}"
            )

    if update_requests:
        try:
            bot.sheets.batch_update(update_requests, "shared")
            print(
                f"[DAILY-BATCH] sent {len(update_requests)} sheet updates in one batch"
            )
        except Exception as exc:
            print(f"[DAILY-BATCH] failed to batch-update sheet values: {exc}")

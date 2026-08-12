"""日次更新ジョブ。"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

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


def _parse_match_day_date(value: object) -> datetime | None:
    """Google Sheets の日付文字列を JST として解釈し、datetime へ変換します。"""
    if value is None or value is False:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    for fmt in (
        "%Y/%m/%d",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=ZoneInfo("Asia/Tokyo"))
        except ValueError:
            continue
    return None


def build_match_day_reminder_message(division: str, form_url: str) -> str:
    """試合当日のチャンネルに送るリマインド文面を生成します。"""
    special_rule = (
        "ベンチ入り6名ルール、（ユクシのみ）スタメンが3人vs4人の特別ルール"
        if division == "div1"
        else "ベンチ入り6名ルール"
    )
    return (
        "# 試合当日になりました\n"
        "・本日は試合予定日です。試合の流れについては調整方法チャンネルを参照してください。\n"
        f"・🚨今シーズンから{special_rule}が追加されていますので必ずチェックしてください。\n"
        "・**🕊️公園や試合場所を利用する他の方の迷惑にならないよう最大限配慮してください。クレームがあると、今後同場所が利用できなくなります。🕊️**\n"
        "・試合終了後は、速報フォームの入力、およびスコア・試合前／後写真のアップロードをお願いいたします。\n\n"
        f"[速報フォームはこちら]({form_url})"
    )


async def send_match_day_reminders(bot: commands.Bot) -> None:
    """共有シートの本日実施試合に対して、対応チャンネルへ試合当日リマインドを送信します。"""
    if not bot.guilds:
        print("[DAILY-BATCH] no guilds available for match-day reminders")
        return

    season_first_month = os.getenv("LEAGUE_CURRENT_SEASON_FIRST_MONTH", "").strip()
    season_last_month = os.getenv("LEAGUE_CURRENT_SEASON_LAST_MONTH", "").strip()
    active_categories = get_active_category_ids()
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    dry_run = os.getenv("REMINDER_DRY_RUN", "0") in ("1", "true", "True")

    try:
        shared_rows = bot.sheets.get_values("場所調整!A1:Z200", "shared")
    except Exception as exc:
        print(
            f"[DAILY-BATCH] failed to read shared sheet for match-day reminders: {exc}"
        )
        return

    todays_match_pairs: set[tuple[str, str]] = set()
    for row in shared_rows:
        if len(row) <= 12:
            continue
        status_value = str(row[11]).strip()
        if status_value != "OK":
            continue
        date_value = _parse_match_day_date(row[12])
        if date_value is None or date_value.date() != today:
            continue

        home_cid = str(row[2]).strip() if len(row) > 2 else ""
        away_cid = str(row[4]).strip() if len(row) > 4 else ""
        if not home_cid or not away_cid:
            continue
        todays_match_pairs.add((home_cid, away_cid))

    if not todays_match_pairs:
        print(
            f"[DAILY-BATCH] no OK matches scheduled for {today.isoformat()} in shared sheet"
        )
        return

    print(
        f"[DAILY-BATCH] found {len(todays_match_pairs)} match-day reminder targets for {today.isoformat()}"
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
                continue
            if (home_cid, away_cid) not in todays_match_pairs:
                continue

            form_url = os.getenv(f"MATCH_RESULT_FORM_URL_{division_key.upper()}", "")
            if not form_url:
                print(
                    f"[DAILY-BATCH] no form url configured for division={division_key}; skip {channel.name}"
                )
                continue

            message = build_match_day_reminder_message(division_key, form_url)
            if dry_run:
                print(
                    f"[DAILY-BATCH-DRY] would send match-day reminder to {channel.name}: {message[:200]}"
                )
                continue
            try:
                await channel.send(message)
                print(f"[DAILY-BATCH] sent match-day reminder to {channel.name}")
            except Exception as exc:
                print(f"[DAILY-BATCH] failed to send reminder to {channel.name}: {exc}")


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

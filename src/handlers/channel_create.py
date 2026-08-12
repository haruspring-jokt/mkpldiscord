import os
from datetime import datetime

import discord

from src.google_services import GoogleSheetsClient
from src.utils import (
    find_club_role_mention,
    find_game_row,
    is_month_within_season,
    parse_match_channel,
    post_bot_log,
)


def get_round_number_from_game_row(row: list[object]) -> str:
    """管理シートの Game 行から節番号を取得します。C列に格納されます。"""
    round_raw = row[2] if len(row) > 2 else None
    if round_raw in (None, False, "FALSE", ""):
        return ""
    return str(round_raw).strip()


async def handle_guild_channel_create(
    bot: "discord.ext.commands.Bot", channel: discord.abc.GuildChannel
) -> None:
    """新規チャンネル作成時のハンドラ。試合チャンネルなら日程調整メッセージを送信する。"""
    if not isinstance(channel, discord.TextChannel):
        return
    metadata = parse_match_channel(channel.name)
    if not metadata:
        return
    season_first_month = os.getenv("LEAGUE_CURRENT_SEASON_FIRST_MONTH", "").strip()
    season_last_month = os.getenv("LEAGUE_CURRENT_SEASON_LAST_MONTH", "").strip()
    if not is_month_within_season(
        metadata["yymm"], season_first_month, season_last_month
    ):
        return

    yymm = metadata["yymm"]
    yy = int(yymm[:2]) + 2000
    mm = int(yymm[2:])
    home = metadata["home"]
    away = metadata["away"]
    dry_run = os.getenv("REMINDER_DRY_RUN", "0") in ("1", "true", "True")

    home_cid = bot.club_cid_map.get(home.casefold())
    away_cid = bot.club_cid_map.get(away.casefold())
    if not home_cid or not away_cid:
        print(
            f"[CHANNEL] could not find CIDs for home={home} or away={away} in channel {channel.name}"
        )
        return
    sheets: GoogleSheetsClient = bot.sheets

    game_row = find_game_row(sheets, metadata["division"], home_cid, away_cid)
    round_no = ""
    if game_row:
        _, row_values = game_row
        round_no = get_round_number_from_game_row(row_values)
    else:
        print(
            f"[CHANNEL] could not find game row for home_cid={home_cid} or away_cid={away_cid} in channel {channel.name}"
        )

    season_label = os.getenv("LEAGUE_CURRENT_SEASON", "")
    message = (
        "# 日程調整をお願いします\n"
        f":regional_indicator_s: シーズン：{season_label}\n"
        f":calendar_spiral: 対戦月：{yy}年{mm}月\n"
        f":soccer: 試合節： {round_no}\n"
        f":home: ホーム： {find_club_role_mention(channel.guild, home, bot.club_alias_map)}\n"
        f":away: アウェイ： {find_club_role_mention(channel.guild, away, bot.club_alias_map)}\n\n"
        "## :pencil:調整方法について\n"
        ":one: 前月の10日までに、アウェイ側は試合可能な日程を複数提出してください。\n"
        ":two:前月の20日までに、ホーム側が:one:を参考に試合日程を決定してください。\n"
        ":three:前月の末日までに、試合時間と会場を決定し運営に報告してください。\n"
        ":four: 試合当日までに、遅刻や緊急の事情が発生した場合はこのチャンネルで相手クラブと運営に連絡してください。\n"
        "試合が成立しないと判断した場合は、基本的には別日程での延期開催とします。\n"
        "しかし、一方のクラブの都合で試合ができない場合は、不戦勝（4-0, 200-0扱い）とする場合があります。\n"
        ":five: 試合前に集合写真を、試合後には勝利クラブの写真を撮影してください。\n"
        "この他、スコアシートも忘れずにお願いします。\n"
        ":six: 試合後は速報をGoogleフォームで送信してください。また、数日以内に提出物をこのチャンネルに投稿（アップロード）してください。\n"
        ":seven: 提出物の確認、および日程シートへの反映が完了したら、試合は完了となります。"
    )

    if dry_run:
        print(
            f"[CHANNEL-DRY] would send to {channel.name} ({channel.id}): {message[:300].replace(chr(10), ' ')}"
        )
        return

    try:
        await channel.send(message)
        print(
            f"[CHANNEL] sent initial schedule message to {channel.name} ({channel.id})"
        )
    except Exception as exc:
        print(
            f"[CHANNEL] failed to send message to {channel.name} ({channel.id}): {exc}"
        )
        await post_bot_log(
            bot,
            "CHANNEL",
            "handle_guild_channel_create",
            datetime.now(),
            success=False,
            context={
                "channel_name": channel.name,
                "channel_id": channel.id,
                "yymm": yymm,
                "home": home,
                "away": away,
            },
            exc=exc,
        )

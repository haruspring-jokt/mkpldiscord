"""ユーザーメッセージ・コマンド・モーダル処理。"""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord
from discord import ui

from src.google_services import GoogleSheetsClient, GoogleCalendarClient
from src.utils import (
    parse_match_channel,
    find_club_role_mention,
    find_game_row,
    find_location_row,
    build_gcal_link,
)


async def handle_message_commands(
    bot: "discord.ext.commands.Bot", message: discord.Message
) -> None:
    """メッセージコマンドを処理します。"""
    if message.content.startswith("!status"):
        await message.channel.send("League bot is online.")
        return

    await maybe_trigger_schedule_modal(bot, message)


async def maybe_trigger_schedule_modal(
    bot: "discord.ext.commands.Bot", message: discord.Message
) -> None:
    """「@運営 日程」投稿を検知して日程確定モーダルの入り口を表示します。"""
    metadata = parse_match_channel(message.channel.name)
    if not metadata:
        return
    if "日程" not in message.content:
        return

    admin_role_id = int(os.getenv("ADMIN_ROLE_ID", "0") or "0")
    mentioned_admin = admin_role_id and any(
        role.id == admin_role_id for role in message.role_mentions
    )
    if not mentioned_admin and "@運営" not in message.content:
        return

    view = ScheduleTriggerView(bot, metadata)
    await message.channel.send("下のボタンから試合日程を入力してください。", view=view)


async def handle_guild_channel_create(
    bot: "discord.ext.commands.Bot", channel: discord.abc.GuildChannel
) -> None:
    """新規チャンネル作成時のハンドラ。試合チャンネルなら日程調整メッセージを送信する。"""
    if not isinstance(channel, discord.TextChannel):
        return
    metadata = parse_match_channel(channel.name)
    if not metadata:
        return

    yymm = metadata["yymm"]
    yy = int(yymm[:2]) + 2000
    mm = int(yymm[2:])
    home = metadata["home"]
    away = metadata["away"]
    dry_run = os.getenv("REMINDER_DRY_RUN", "0") in ("1", "true", "True")

    # 該当する試合の節の取得
    # チャンネル名のホーム略称からホームCID、アウェイ略称からアウェイCIDを取得し、管理スプレッドシートのGameシートから該当する試合行を検索する
    home_cid = bot.club_cid_map.get(home.casefold())
    away_cid = bot.club_cid_map.get(away.casefold())
    if not home_cid or not away_cid:
        print(
            f"[CHANNEL] could not find CIDs for home={home} or away={away} in channel {channel.name}"
        )
        return
    # 管理スプレッドシートのGameシートから該当する試合行を検索
    sheets: GoogleSheetsClient = bot.sheets
    game_row = find_game_row(sheets, metadata["division"], home_cid, away_cid)
    if not game_row:
        print(
            f"[CHANNEL] could not find game row for home_cid={home_cid}, away_cid={away_cid} in channel {channel.name}"
        )
        return
    # 節の取得
    row_idx, row_values = game_row
    round_raw = row_values[9] if len(row_values) > 9 else None
    # 節番号の整形
    round_no = (
        str(round_raw).strip() if (round_raw not in (None, False, "FALSE", "")) else ""
    )

    # メッセージ本文の作成
    message = (
        "# 日程調整をお願いします\n"
        f":regional_indicator_s: シーズン：{os.getenv("LEAGUE_CURRENT_SEASON")}\n"
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
            f"[CHANNEL-DRY] would send to {channel.name} ({channel.id}): {message[:300].replace('\n',' ')}"
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


async def process_schedule_submission(
    bot: "discord.ext.commands.Bot",
    interaction: discord.Interaction,
    metadata: dict[str, str],
    date_str: str,
    time_str: str,
    location: str,
) -> None:
    """日程確定モーダルの送信内容を各スプレッドシート/カレンダーへ反映します。"""
    channel = interaction.channel
    guild = interaction.guild
    division = metadata["division"]
    home_alias = metadata["home"]
    away_alias = metadata["away"]

    sheets: GoogleSheetsClient = bot.sheets
    calendar: GoogleCalendarClient = bot.calendar

    home_cid = bot.club_cid_map.get(home_alias.casefold())
    away_cid = bot.club_cid_map.get(away_alias.casefold())
    if not home_cid or not away_cid:
        await interaction.followup.send(
            f"クラブ略称からCIDを特定できませんでした（home={home_alias}, away={away_alias}）。club.jsonを確認してください。",
            ephemeral=True,
        )
        return

    try:
        start_dt = datetime.strptime(
            f"{date_str} {time_str}", "%Y/%m/%d %H:%M"
        ).replace(tzinfo=ZoneInfo("Asia/Tokyo"))
    except ValueError:
        await interaction.followup.send(
            "日程または開始時間の形式が正しくありません（例: 2026/09/06, 16:00）。",
            ephemeral=True,
        )
        return
    end_dt = start_dt + timedelta(hours=2)

    # 1. 管理スプレッドシート(Game シート)へ日程・時間を書き込む
    game_row = find_game_row(sheets, division, home_cid, away_cid)
    if not game_row:
        await interaction.followup.send(
            "管理スプレッドシートに該当する試合行が見つかりませんでした。",
            ephemeral=True,
        )
        return
    row_idx, row_values = game_row
    try:
        sheets.update_range(
            f"Game!M{row_idx}:N{row_idx}", [[date_str, time_str]], division
        )
    except Exception as exc:
        print(f"[SCHEDULE] failed to update Game sheet: {exc}")
        await interaction.followup.send(
            "管理スプレッドシートへの書き込みに失敗しました。", ephemeral=True
        )
        return

    # 2. 日程調整シート(場所調整)へ場所を書き込む
    location_row_idx = find_location_row(sheets, home_cid, away_cid)
    if location_row_idx:
        try:
            sheets.update_range(f"場所調整!P{location_row_idx}", [[location]], "shared")
        except Exception as exc:
            print(f"[SCHEDULE] failed to update 場所調整 sheet: {exc}")
    else:
        print("[SCHEDULE] 場所調整シートに該当する試合行が見つかりませんでした")

    # 3. Google カレンダーへの登録
    round_raw = row_values[9] if len(row_values) > 9 else None
    round_no = (
        str(round_raw).strip() if (round_raw not in (None, False, "FALSE", "")) else ""
    )
    match_id = str(row_values[2]).strip() if len(row_values) > 2 else ""
    league_label = os.getenv(f"LEAGUE_LABEL_{division.upper()}", "")
    event_prefix = os.getenv(f"LEAGUE_EVENT_PREFIX_{division.upper()}", "")
    home_name = bot.club_alias_map.get(home_alias.casefold(), home_alias)
    away_name = bot.club_alias_map.get(away_alias.casefold(), away_alias)
    event_name = f"{event_prefix} {league_label} 第{round_no}節 {home_name} - {away_name}".strip()

    match_site_base = os.getenv(
        "MATCH_SITE_BASE_URL", "https://molkkyprime.com/match?gid="
    )
    details_text = f"試合情報: {match_site_base}{match_id}"
    calendar_link = build_gcal_link(event_name, start_dt, end_dt, details_text)

    color_id = os.getenv(f"CALENDAR_COLOR_ID_{division.upper()}") or None

    try:
        calendar.create_event(
            summary=event_name,
            start_iso=start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            end_iso=end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            description=details_text,
            location=location,
            color_id=color_id,
        )
    except Exception as exc:
        print(f"[SCHEDULE] failed to create calendar event: {exc}")

    # 4. 完了通知
    home_mention = find_club_role_mention(guild, home_alias, bot.club_alias_map)
    away_mention = find_club_role_mention(guild, away_alias, bot.club_alias_map)
    form_url = os.getenv(f"MATCH_RESULT_FORM_URL_{division.upper()}", "")
    schedule_url = os.getenv(f"SCHEDULE_PAGE_URL_{division.upper()}", "")
    shared_sheet_url = os.getenv("SHARED_SHEET_URL", "")

    completion_message = (
        f"{home_mention} {away_mention} \n"
        "試合情報を反映しました。\n\n"
        "対戦後は提出物（スコアシート写真、試合前写真、試合後写真）をこのチャンネルにアップしてください。\n\n"
        "【ホームクラブ代表者様】\n"
        "試合終了後、以下のGoogleフォームに速報の入力をお願いします。\n\n"
        f":pencil:[試合結果報告フォーム｜{league_label}]({form_url})\n\n"
        f":desktop:[HP｜日程ページ｜{league_label}]({schedule_url})\n\n"
        f":scroll:[⚠リーグ外持ち出し禁止⚠調整用シート]({shared_sheet_url})\n\n"
        f":calendar:[Googleカレンダー登録リンク]({calendar_link})"
    )

    dry_run = os.getenv("REMINDER_DRY_RUN", "0") in ("1", "true", "True")
    if dry_run:
        print(
            f"[SCHEDULE-DRY] would send completion message to channel {channel}: {completion_message[:300]}"
        )
        await interaction.followup.send(
            "（DRY RUN）日程登録処理が完了しました。チャンネルへの送信はスキップされました。",
            ephemeral=True,
        )
        return

    await channel.send(completion_message)
    await interaction.followup.send("日程登録が完了しました。", ephemeral=True)


class ScheduleModal(ui.Modal):
    """試合日程確定用モーダル。"""

    def __init__(
        self, bot: "discord.ext.commands.Bot", metadata: dict[str, str]
    ) -> None:
        super().__init__(title="試合日程の確定")
        self.bot = bot
        self.metadata = metadata

        self.date_input = ui.TextInput(
            label="日程 (yyyy/MM/dd)",
            placeholder="2026/09/06",
            required=True,
            max_length=10,
        )
        self.time_input = ui.TextInput(
            label="開始時間 (hh:mm)",
            placeholder="16:00",
            required=True,
            max_length=5,
        )
        self.location_input = ui.TextInput(
            label="場所",
            placeholder="○○公園多目的広場",
            required=True,
            max_length=100,
        )
        self.add_item(self.date_input)
        self.add_item(self.time_input)
        self.add_item(self.location_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        await process_schedule_submission(
            self.bot,
            interaction,
            self.metadata,
            self.date_input.value.strip(),
            self.time_input.value.strip(),
            self.location_input.value.strip(),
        )


class ScheduleTriggerView(ui.View):
    """日程確定モーダルを開くためのボタンを表示する View。"""

    def __init__(
        self, bot: "discord.ext.commands.Bot", metadata: dict[str, str]
    ) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.metadata = metadata

    @ui.button(label="日程を入力する", style=discord.ButtonStyle.primary)
    async def open_modal(
        self, interaction: discord.Interaction, button: ui.Button
    ) -> None:
        await interaction.response.send_modal(ScheduleModal(self.bot, self.metadata))

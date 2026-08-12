import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import discord
from discord import ui

from src.google_services import GoogleCalendarClient, GoogleSheetsClient
from src.utils import (
    build_gcal_link,
    find_club_role_mention,
    find_game_row,
    find_location_row,
)


def get_round_number_from_game_row(row: list[object]) -> str:
    """管理シートの Game 行から節番号を取得します。C列に格納されます。"""
    round_raw = row[2] if len(row) > 2 else None
    if round_raw in (None, False, "FALSE", ""):
        return ""
    return str(round_raw).strip()


def get_round_number_from_location_row(row: list[object]) -> str:
    """場所調整シートの行から節番号を取得します。J列に格納されます。"""
    round_raw = row[9] if len(row) > 9 else None
    if round_raw in (None, False, "FALSE", ""):
        return ""
    return str(round_raw).strip()


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

    location_row_idx = find_location_row(sheets, home_cid, away_cid)
    if location_row_idx:
        try:
            sheets.update_range(f"場所調整!P{location_row_idx}", [[location]], "shared")
        except Exception as exc:
            print(f"[SCHEDULE] failed to update 場所調整 sheet: {exc}")
    else:
        print("[SCHEDULE] 場所調整シートに該当する試合行が見つかりませんでした")

    round_no = get_round_number_from_game_row(row_values)
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
            location="",
            color_id=color_id,
        )
    except Exception as exc:
        print(f"[SCHEDULE] failed to create calendar event: {exc}")

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

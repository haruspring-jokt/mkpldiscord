import os

import discord

from src.utils import is_month_within_season, parse_match_channel


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
    season_first_month = os.getenv("LEAGUE_CURRENT_SEASON_FIRST_MONTH", "").strip()
    season_last_month = os.getenv("LEAGUE_CURRENT_SEASON_LAST_MONTH", "").strip()
    if not is_month_within_season(
        metadata["yymm"], season_first_month, season_last_month
    ):
        return
    if "日程" not in message.content:
        return

    admin_role_id = int(os.getenv("ADMIN_ROLE_ID", "0") or "0")
    mentioned_admin = admin_role_id and any(
        role.id == admin_role_id for role in message.role_mentions
    )
    if not mentioned_admin and "@運営" not in message.content:
        return

    from .schedule import ScheduleTriggerView

    view = ScheduleTriggerView(bot, metadata)
    await message.channel.send("下のボタンから試合日程を入力してください。", view=view)

import os
import re

import discord

from src.utils import is_month_within_season, parse_match_channel


def should_ignore_example_message(message_text: str) -> bool:
    """ドキュメント例やコードブロックに含まれるメッセージは無視する。"""
    stripped = message_text.strip()
    if not stripped:
        return True

    if re.fullmatch(
        r"[`\"“”'‘’「」『』\(\)\[\]\{\}]+.*[`\"“”'‘’「」『』\(\)\[\]\{\}]+", stripped
    ):
        return True

    if re.search(r"```|`@運営 日程`|「@運営 日程」|『@運営 日程』", stripped):
        return True

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if not lines:
        return True

    fenced = False
    for line in lines:
        if line.startswith("```"):
            fenced = not fenced
            continue
        if fenced:
            return True

    return False


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
    if should_ignore_example_message(message.content):
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

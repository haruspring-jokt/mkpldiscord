import os
import re

import discord

from src.utils import is_month_within_season, parse_match_channel


_CODE_PATTERN = re.compile(r"```.*?(?:```|\Z)|`[^`\n]*`", re.DOTALL)


def strip_code(message_text: str) -> str:
    """コードブロック（```）とインラインコード（`）の部分を取り除く。"""
    return _CODE_PATTERN.sub(" ", message_text)


def should_ignore_example_message(message_text: str) -> bool:
    """コードブロック／インラインコードの外に本文が無いメッセージは無視する。"""
    return not strip_code(message_text).strip()


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
    content = strip_code(message.content)
    if "日程" not in content:
        return

    admin_role_id = int(os.getenv("ADMIN_ROLE_ID", "0") or "0")
    mentioned_admin = admin_role_id and any(
        role.id == admin_role_id for role in message.role_mentions
    )
    if not mentioned_admin and "@運営" not in content:
        return

    from .schedule import ScheduleTriggerView

    view = ScheduleTriggerView(bot, metadata)
    await message.channel.send("下のボタンから試合日程を入力してください。", view=view)

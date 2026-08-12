"""試合チャンネル新規作成バッチ。"""

import os
from datetime import datetime

import discord
from discord.ext import commands

from src.jobs.shared import get_active_category_ids
from src.utils import (
    build_match_channel_name,
    get_target_yymm_for_channel_creation,
    normalize_yymm_from_sheet_value,
)


def _get_channel_prefix_from_shared_row(row: list[object]) -> str:
    """場所調整シートの B 列からチャンネル prefix を決めます。"""
    if len(row) <= 1:
        return "gc"
    value = str(row[1]).strip().lower()
    return "g" if value == "y" else "gc"


def _get_role_for_tooling(
    guild: discord.Guild, role_name: str | None
) -> discord.Role | None:
    """ロール名で Discord ロールを取得します。"""
    if not role_name:
        return None
    for role in guild.roles:
        if role.name == role_name:
            return role
    return None


async def create_match_channels_for_target_month(bot: commands.Bot) -> None:
    """現在月の2ヶ月後の試合を共有シートから取得し、試合チャンネルを自動作成します。"""
    if not bot.guilds:
        print("[CHANNEL-BATCH] no guilds available")
        return

    enabled = os.getenv("GAME_CHANNEL_CREATE_BATCH_ENABLED", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if not enabled:
        print("[CHANNEL-BATCH] disabled")
        return

    dry_run = os.getenv("REMINDER_DRY_RUN", "0").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if dry_run:
        print("[CHANNEL-BATCH-DRY] dry run enabled; no Discord channel will be created")

    target_yymm = get_target_yymm_for_channel_creation(datetime.now())
    print(f"[CHANNEL-BATCH] start target_yymm={target_yymm}")

    try:
        values = bot.sheets.batch_get_values(["場所調整!A1:Z200"], "shared")
        values = values[0] if values else []
    except Exception as exc:
        print(f"[CHANNEL-BATCH] failed to read shared sheet: {exc}")
        return

    admin_role_id = int(os.getenv("ADMIN_ROLE_ID", "0") or "0")

    for guild in bot.guilds:
        if not guild.text_channels:
            continue

        for row in values[1:]:
            if len(row) <= 4:
                continue

            yymm_value = row[8] if len(row) > 8 else ""
            yymm = normalize_yymm_from_sheet_value(yymm_value)
            if yymm != target_yymm:
                continue

            home_cid = str(row[2]).strip() if len(row) > 2 else ""
            away_cid = str(row[4]).strip() if len(row) > 4 else ""
            if not home_cid or not away_cid:
                continue

            home_alias = bot.club_cid_to_alias_map.get(home_cid.casefold())
            away_alias = bot.club_cid_to_alias_map.get(away_cid.casefold())
            if not home_alias or not away_alias:
                print(
                    f"[CHANNEL-BATCH] skip row for home_cid={home_cid} away_cid={away_cid} because alias lookup failed"
                )
                continue

            prefix = _get_channel_prefix_from_shared_row(row)
            channel_name = build_match_channel_name(
                prefix, yymm, home_alias, away_alias
            )
            if any(existing.name == channel_name for existing in guild.text_channels):
                print(f"[CHANNEL-BATCH] already exists: {channel_name}")
                continue

            home_role_name = bot.club_alias_map.get(home_alias.casefold())
            away_role_name = bot.club_alias_map.get(away_alias.casefold())
            admin_role = guild.get_role(admin_role_id) if admin_role_id else None
            if not home_role_name or not away_role_name:
                print(
                    f"[CHANNEL-BATCH] skip {channel_name} because role lookup failed for home={home_alias}, away={away_alias}"
                )
                continue

            home_role = _get_role_for_tooling(guild, home_role_name)
            away_role = _get_role_for_tooling(guild, away_role_name)
            if home_role is None or away_role is None:
                print(
                    f"[CHANNEL-BATCH] skip {channel_name} because role missing: home={home_role_name}, away={away_role_name}"
                )
                continue

            private_overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                home_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    add_reactions=True,
                    attach_files=True,
                    embed_links=True,
                ),
                away_role: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    add_reactions=True,
                    attach_files=True,
                    embed_links=True,
                ),
            }
            if admin_role is not None:
                private_overwrites[admin_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    add_reactions=True,
                    attach_files=True,
                    embed_links=True,
                )

            category_ids = get_active_category_ids().get(
                "div1" if prefix == "g" else "div2", set()
            )
            category = None
            for category_id in sorted(category_ids):
                candidate = guild.get_channel(category_id)
                if candidate is not None and isinstance(
                    candidate, discord.CategoryChannel
                ):
                    category = candidate
                    break

            if dry_run:
                category_label = (
                    category.name if category is not None else "<not found>"
                )
                category_id = category.id if category is not None else None
                print(
                    "[CHANNEL-BATCH-DRY] would create "
                    f"channel='{channel_name}' "
                    f"category_name='{category_label}' "
                )
                continue

            try:
                created = await guild.create_text_channel(
                    channel_name,
                    category=category,
                    overwrites=private_overwrites,
                )
                print(f"[CHANNEL-BATCH] created {created.name} ({created.id})")
            except Exception as exc:
                print(f"[CHANNEL-BATCH] failed to create {channel_name}: {exc}")

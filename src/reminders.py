"""Backwards-compatible alias for scheduled jobs.

The concrete implementations live under src/jobs/*.py so that each job can be
managed independently as the bot grows.
"""

from src.jobs.channel_create_batch import create_match_channels_for_target_month
from src.jobs.daily_batch import (
    format_sheet_date,
    get_active_category_ids,
    update_last_post_dates_for_match_channels,
)
from src.jobs.reminder_10 import send_10th_reminders
from src.jobs.reminder_20 import send_20th_reminders
from src.jobs.reminder_25 import send_25th_reminders
from src.jobs.shared import is_reminder_target_channel

__all__ = [
    "get_active_category_ids",
    "format_sheet_date",
    "update_last_post_dates_for_match_channels",
    "is_reminder_target_channel",
    "send_10th_reminders",
    "send_20th_reminders",
    "send_25th_reminders",
    "create_match_channels_for_target_month",
]

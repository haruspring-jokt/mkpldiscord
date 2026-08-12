"""リーグ運営用 Discord ボット - メインボットクラス。

このモジュールはボットクラス、イベントハンドラ登録、スケジューラ管理を担当します。
具体的な処理ロジックは以下のモジュールに分割されています:
- src.jobs: スケジューラ実行処理
- src.handlers: ユーザー入力系イベント処理のパッケージ
- src.utils: 共通ユーティリティ
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import discord
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from discord.ext import commands

from src.google_services import (
    GoogleCalendarClient,
    GoogleSheetsClient,
    GoogleStorageClient,
)
from src.storage import JsonStorage
from src.handlers.applications import handle_thread_create
from src.handlers.channel_create import handle_guild_channel_create
from src.handlers.commands import handle_message_commands
from src.jobs.channel_create_batch import create_match_channels_for_target_month
from src.jobs.daily_batch import update_last_post_dates_for_match_channels
from src.jobs.reminder_10 import send_10th_reminders
from src.jobs.reminder_20 import send_20th_reminders
from src.jobs.reminder_25 import send_25th_reminders


class LeagueBot(commands.Bot):
    """リーグ運営用のメイン Discord ボットクラス。"""

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

        # 内部状態を保持する JSON ストレージ
        self.storage = JsonStorage()
        # Google API クライアント
        self.sheets = GoogleSheetsClient()
        self.calendar = GoogleCalendarClient()
        self.storage_client = GoogleStorageClient()
        # クラブ略称からロール名/CIDへのマッピング
        self.club_alias_map, self.club_cid_map = self.load_club_data()

        # リマインダーや定期ジョブ用のバックグラウンドスケジューラ
        # NOTE: start() はイベントループが動作中の on_ready で呼び出す
        self.scheduler = AsyncIOScheduler(timezone="Asia/Tokyo")
        self._scheduler_started = False
        self._jobs_registered = False
        self.ready_event = asyncio.Event()

    def load_club_data(self) -> tuple[dict[str, str], dict[str, str]]:
        """`data/club.json` からエイリアス→ロール名、エイリアス→CID のマッピングを読み込みます。"""
        club_file = Path(__file__).resolve().parent.parent / "data" / "club.json"
        if not club_file.exists():
            print(f"club.json not found: {club_file}")
            return {}, {}

        with club_file.open("r", encoding="utf-8") as f:
            clubs = json.load(f)

        alias_to_role: dict[str, str] = {}
        alias_to_cid: dict[str, str] = {}
        cid_to_alias: dict[str, str] = {}
        for club in clubs:
            alias = club.get("alias")
            role_name = club.get("role_name")
            cid = club.get("cid")
            if isinstance(alias, str):
                key = alias.casefold()
                if isinstance(role_name, str):
                    alias_to_role[key] = role_name
                if isinstance(cid, str):
                    alias_to_cid[key] = cid
                    cid_to_alias[cid.strip().casefold()] = alias
        self.club_cid_to_alias_map = cid_to_alias
        return alias_to_role, alias_to_cid

    async def on_ready(self) -> None:
        """ボットの接続が完了し準備ができたときに呼ばれます。"""
        print(f"Bot logged in as {self.user}")
        self.ready_event.set()
        # Scheduler を起動（イベントループが稼働していることを確認）
        if not self._scheduler_started:
            try:
                self.scheduler.start()
                self.scheduler.add_listener(
                    self._aps_job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
                )
                self._scheduler_started = True
                print("[SCHED] AsyncIOScheduler started")
            except Exception as exc:
                print(f"[SCHED] failed to start scheduler: {exc}")

        # on_ready は複数回呼ばれることがあるため、ジョブ登録は一度だけ行う
        if not self._jobs_registered:
            await self.schedule_recurring_reminders()
            await self.schedule_daily_batch()
            await self.schedule_game_channel_create_batch()
            self._jobs_registered = True

    async def on_message(self, message: discord.Message) -> None:
        """受信したメッセージを処理します。"""
        if message.author.bot:
            return
        if not message.guild:
            return

        await handle_message_commands(self, message)

    def _get_job_schedule(self, prefix: str) -> tuple[bool, tuple[int, int, int]]:
        """環境変数からジョブの実行可否と実行時刻(DDHHMM)を読み取る。"""
        enabled = os.getenv(f"{prefix}_ENABLED", "0").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if not enabled:
            return False, (1, 0, 0)

        raw = os.getenv(f"{prefix}_SCHEDULE", "").strip()
        if not raw:
            raise ValueError(f"{prefix}_SCHEDULE is required when {prefix}_ENABLED=1")
        if len(raw) != 6 or not raw.isdigit():
            raise ValueError(f"{prefix}_SCHEDULE must be 6 digits like DDHHMM: {raw!r}")

        day = int(raw[:2])
        hour = int(raw[2:4])
        minute = int(raw[4:6])
        if not (1 <= day <= 31 and 0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"invalid schedule value: {raw!r}")
        return True, (day, hour, minute)

    async def schedule_recurring_reminders(self) -> None:
        """10日・20日・25日のリマインダーを env で管理するスケジュールに従って登録します。"""
        for prefix, job_method in (
            ("REMINDER_10", self.send_10th_reminders_job),
            ("REMINDER_20", self.send_20th_reminders_job),
            ("REMINDER_25", self.send_25th_reminders_job),
        ):
            try:
                enabled, (day, hour, minute) = self._get_job_schedule(prefix)
            except ValueError as exc:
                print(f"[REMINDER] invalid config for {prefix}: {exc}")
                continue
            if not enabled:
                print(f"[REMINDER] disabled: {prefix}")
                continue
            self.scheduler.add_job(
                job_method, "cron", day=day, hour=hour, minute=minute
            )
            print(f"[REMINDER] scheduled {prefix} at {day:02d}/{hour:02d}:{minute:02d}")

    async def schedule_daily_batch(self) -> None:
        """毎日決まった時刻に共通調整シートの最終投稿日を更新するジョブを登録します。"""
        enabled = os.getenv("DAILY_BATCH_ENABLED", "0") in ("1", "true", "True")
        if not enabled:
            print("[DAILY-BATCH] disabled")
            return

        raw_time = os.getenv("DAILY_BATCH_TIME", "0700").strip()
        try:
            if len(raw_time) != 4 or not raw_time.isdigit():
                raise ValueError(raw_time)
            hour = int(raw_time[:2])
            minute = int(raw_time[2:])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError(raw_time)
        except ValueError:
            print(f"[DAILY-BATCH] invalid DAILY_BATCH_TIME '{raw_time}', fallback 0700")
            hour, minute = 7, 0

        self.scheduler.add_job(
            self.send_daily_batch_job,
            "cron",
            hour=hour,
            minute=minute,
        )
        print(f"[DAILY-BATCH] scheduled daily at {hour:02d}:{minute:02d}")

    async def send_10th_reminders_job(self) -> None:
        """10日リマインダー送信ジョブ。"""
        await send_10th_reminders(self, self.club_alias_map)

    async def send_20th_reminders_job(self) -> None:
        """20日リマインダー送信ジョブ。"""
        await send_20th_reminders(self, self.club_alias_map)

    async def send_25th_reminders_job(self) -> None:
        """25日リマインダー送信ジョブ。"""
        await send_25th_reminders(self, self.club_alias_map)

    async def send_daily_batch_job(self) -> None:
        """本日試合のリマインドと最終非 bot 投稿日の更新ジョブ。"""
        await update_last_post_dates_for_match_channels(self)
        from src.jobs.daily_batch import send_match_day_reminders

        await send_match_day_reminders(self)

    async def schedule_game_channel_create_batch(self) -> None:
        """毎月1日に2ヶ月後の試合チャンネルを作成するジョブを登録します。"""
        enabled = os.getenv(
            "GAME_CHANNEL_CREATE_BATCH_ENABLED", "0"
        ).strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
        if not enabled:
            print("[CHANNEL-BATCH] disabled")
            return

        raw_time = os.getenv("GAME_CHANNEL_CREATE_BATCH_TIME", "010700").strip()
        try:
            if len(raw_time) != 6 or not raw_time.isdigit():
                raise ValueError(raw_time)
            day = int(raw_time[:2])
            hour = int(raw_time[2:4])
            minute = int(raw_time[4:6])
            if not (1 <= day <= 31 and 0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError(raw_time)
        except ValueError:
            print(
                f"[CHANNEL-BATCH] invalid GAME_CHANNEL_CREATE_BATCH_TIME '{raw_time}', fallback 010700"
            )
            day, hour, minute = 1, 7, 0

        self.scheduler.add_job(
            self.send_game_channel_create_batch_job,
            "cron",
            day=day,
            hour=hour,
            minute=minute,
        )
        print(f"[CHANNEL-BATCH] scheduled monthly at {day:02d}/{hour:02d}:{minute:02d}")

    async def send_game_channel_create_batch_job(self) -> None:
        """2ヶ月後の試合チャンネルを作成するジョブ。"""
        await create_match_channels_for_target_month(self)

    def _aps_job_listener(self, event) -> None:
        """APScheduler のジョブ実行イベントを受け取りログ出力する。"""
        try:
            if getattr(event, "exception", None):
                print(f"[APS] job {event.job_id} raised exception: {event.exception}")
            else:
                print(
                    f"[APS] job {event.job_id} executed successfully at {datetime.now().isoformat()}"
                )
        except Exception as exc:
            print(f"[APS] job listener error: {exc}")

    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        """新規チャンネル作成時のハンドラ。"""
        await handle_guild_channel_create(self, channel)

    async def on_thread_create(self, thread: discord.Thread) -> None:
        """申請フォーラムの新規スレッドを検知して申請種別の選択を促す。"""
        await handle_thread_create(self, thread)

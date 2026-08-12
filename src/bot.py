"""リーグ運営用 Discord ボット - メインボットクラス。

このモジュールはボットクラス、イベントハンドラ登録、スケジューラ管理を担当します。
具体的な処理ロジックは以下のモジュールに分割されています:
- src.reminders: スケジューラ実行処理
- src.handlers: ユーザーメッセージ・コマンド・モーダル処理
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
from src.reminders import (
    send_monthly_reminders,
    send_20th_reminders,
    send_25th_reminders,
)
from src.handlers import handle_message_commands, handle_guild_channel_create


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
            await self.schedule_monthly_reminders()
            self._jobs_registered = True

    async def on_message(self, message: discord.Message) -> None:
        """受信したメッセージを処理します。"""
        if message.author.bot:
            return
        if not message.guild:
            return

        await handle_message_commands(self, message)

    async def schedule_recurring_reminders(self) -> None:
        """20日と25日のリマインダーをスケジュールします。"""
        self.scheduler.add_job(
            self.send_20th_reminders_job,
            "cron",
            day=20,
            hour=9,
            minute=0,
        )
        self.scheduler.add_job(
            self.send_25th_reminders_job,
            "cron",
            day=25,
            hour=9,
            minute=0,
        )

    async def schedule_monthly_reminders(self) -> None:
        """月次リマインダー実行ジョブを登録します。

        通常は毎月10日9:00に実行します。
        テスト用に TEST_REMINDER=1 を指定した場合は、直近の11日22:00に一度だけ実行します。
        """
        test_mode = os.getenv("TEST_REMINDER", "0") in ("1", "true", "True")
        if test_mode:
            now = datetime.now()
            target_date = os.getenv("TEST_REMINDER_DATE")
            if target_date:
                try:
                    if target_date == "now":
                        target = now + timedelta(seconds=10)
                    elif target_date.startswith("now+"):
                        spec = target_date[4:]
                        if spec.endswith("s"):
                            secs = int(spec[:-1])
                            target = now + timedelta(seconds=secs)
                        elif spec.endswith("m"):
                            mins = int(spec[:-1])
                            target = now + timedelta(minutes=mins)
                        else:
                            target = datetime.fromisoformat(target_date)
                    else:
                        target = datetime.fromisoformat(target_date)
                except Exception as exc:
                    print(
                        f"[TEST_REMINDER] invalid TEST_REMINDER_DATE '{target_date}': {exc}"
                    )
                    target = now.replace(hour=22, minute=0, second=0, microsecond=0)
            else:
                target = now.replace(hour=22, minute=0, second=0, microsecond=0)
            if now.day > 11 or (now.day == 11 and now >= target):
                month = now.month + 1
                year = now.year
                if month > 12:
                    month = 1
                    year += 1
                target = target.replace(year=year, month=month, day=11)
            else:
                target = target.replace(day=11)
            print(
                f"[TEST_REMINDER] scheduling one-time reminder for {target.isoformat()}"
            )
            self.scheduler.add_job(
                self.send_monthly_reminders_job,
                "date",
                run_date=target,
            )
        else:
            self.scheduler.add_job(
                self.send_monthly_reminders_job,
                "cron",
                day=10,
                hour=9,
                minute=0,
            )

    async def send_monthly_reminders_job(self) -> None:
        """月次リマインダー送信ジョブ。"""
        await send_monthly_reminders(self, self.club_alias_map)

    async def send_20th_reminders_job(self) -> None:
        """20日リマインダー送信ジョブ。"""
        await send_20th_reminders(self, self.club_alias_map)

    async def send_25th_reminders_job(self) -> None:
        """25日リマインダー送信ジョブ。"""
        await send_25th_reminders(self, self.club_alias_map)

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

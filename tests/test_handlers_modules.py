import asyncio

from src.handlers.applications import (
    ApplyRequestModal,
    ApplyTypeSelectionView,
    handle_thread_create,
)
from src.handlers.channel_create import handle_guild_channel_create
from src.handlers.commands import (
    handle_message_commands,
    should_ignore_example_message,
    strip_code,
)
from src.handlers.schedule import (
    ScheduleModal,
    ScheduleTriggerView,
    process_schedule_submission,
)


def test_handler_modules_are_importable() -> None:
    assert callable(handle_message_commands)
    assert callable(handle_guild_channel_create)
    assert callable(handle_thread_create)
    assert callable(process_schedule_submission)
    assert ScheduleModal is not None
    assert ScheduleTriggerView is not None
    assert ApplyRequestModal is not None
    assert ApplyTypeSelectionView is not None


def test_should_ignore_example_message() -> None:
    assert should_ignore_example_message("`@運営 日程`") is True
    assert should_ignore_example_message("```\n@運営 日程\n```") is True
    assert should_ignore_example_message("「@運営 日程」") is False
    assert should_ignore_example_message("@運営 日程") is False
    assert should_ignore_example_message("@運営　日程お願いします") is False


def test_strip_code_removes_only_code_parts() -> None:
    assert "日程" not in strip_code("`@運営 日程` の使い方")
    assert "日程" not in strip_code("```\n@運営 日程\n```")
    assert "@運営" in strip_code("@運営　`foo` 日程")
    assert "日程" in strip_code("「@運営 日程」")


def test_handle_guild_channel_create_skips_duplicate_initial_message(
    monkeypatch,
) -> None:
    class DummyMessage:
        author = type("Author", (), {"bot": True})()
        content = "# 日程調整をお願いします\n:regional_indicator_s: シーズン：2026-27"

    class DummyChannel:
        name = "g-2611-jaja-sisu"
        id = 999
        guild = type("Guild", (), {})()

        def history(self, limit=20):
            return iter([DummyMessage()])

        async def send(self, *args, **kwargs):
            raise AssertionError("duplicate initial message should be skipped")

    class DummyBot:
        club_cid_map = {"jaja": "C01", "sisu": "C02"}
        club_alias_map = {"jaja": "Jaja Role", "sisu": "Sisu Role"}
        sheets = object()

    monkeypatch.setattr(
        "src.handlers.channel_create.parse_match_channel",
        lambda name: {
            "yymm": "2611",
            "home": "jaja",
            "away": "sisu",
            "division": "div1",
        },
    )
    monkeypatch.setattr(
        "src.handlers.channel_create.is_month_within_season",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "src.handlers.channel_create.find_club_role_mention",
        lambda guild, alias, alias_map: f"@{alias}",
    )
    monkeypatch.setattr(
        "src.handlers.channel_create.find_game_row",
        lambda *args, **kwargs: None,
    )

    async def run_test() -> None:
        await handle_guild_channel_create(DummyBot(), DummyChannel())

    asyncio.run(run_test())


def test_process_schedule_submission_uses_calendar_name(monkeypatch) -> None:
    class DummySheets:
        def update_range(self, *args, **kwargs):
            return None

    class DummyCalendar:
        def __init__(self):
            self.summary = None

        def create_event(self, **kwargs):
            self.summary = kwargs["summary"]

    class DummyFollowup:
        async def send(self, *args, **kwargs):
            return None

    class DummyChannel:
        async def send(self, *args, **kwargs):
            return None

    class DummyGuild:
        roles = []

    class DummyInteraction:
        def __init__(self):
            self.channel = DummyChannel()
            self.guild = DummyGuild()
            self.user = type("User", (), {"display_name": "tester"})()
            self.followup = DummyFollowup()

    class DummyBot:
        club_cid_map = {"home": "C01", "away": "C02"}
        club_alias_map = {"home": "Home Role", "away": "Away Role"}
        club_calendar_name_map = {"home": "Home Club", "away": "Away Club"}
        sheets = DummySheets()
        calendar = DummyCalendar()

    def fake_find_game_row(*args, **kwargs):
        return (7, ["", "", "R1", "", "", "C01", "C02"])

    def fake_find_location_row(*args, **kwargs):
        return 9

    monkeypatch.setattr(
        "src.handlers.schedule.find_game_row",
        fake_find_game_row,
    )
    monkeypatch.setattr(
        "src.handlers.schedule.find_location_row",
        fake_find_location_row,
    )
    monkeypatch.setattr(
        "src.handlers.schedule.find_club_role_mention",
        lambda guild, alias, alias_map: f"@{alias}",
    )

    async def run_test() -> None:
        await process_schedule_submission(
            DummyBot(),
            DummyInteraction(),
            {"division": "div1", "home": "home", "away": "away"},
            "2026/09/06",
            "16:00",
            "Test Field",
        )

    asyncio.run(run_test())

    assert DummyBot.calendar.summary.startswith("div1")
    assert "Home Club - Away Club" in DummyBot.calendar.summary
    assert "Home Role" not in DummyBot.calendar.summary
    assert "Away Role" not in DummyBot.calendar.summary

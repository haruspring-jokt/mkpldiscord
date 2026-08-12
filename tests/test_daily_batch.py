import os
import unittest
from datetime import datetime
from unittest import mock

from src.handlers.applications import (
    get_apply_forum_ids,
    get_apply_type_options,
    get_apply_type_title,
)
from src.handlers.schedule import (
    get_round_number_from_game_row,
    get_round_number_from_location_row,
)
from src.reminders import (
    format_sheet_date,
    get_active_category_ids,
    is_reminder_target_channel,
)
from src.utils import (
    build_match_channel_name,
    get_target_yymm_for_channel_creation,
    is_month_within_season,
    normalize_yymm_from_sheet_value,
)


class DailyBatchTests(unittest.TestCase):
    def test_is_month_within_season_range(self):
        self.assertTrue(is_month_within_season("202609", "202609", "202703"))
        self.assertTrue(is_month_within_season("202612", "202609", "202703"))
        self.assertTrue(is_month_within_season("202703", "202609", "202703"))
        self.assertTrue(is_month_within_season("2609", "202609", "202703"))
        self.assertTrue(is_month_within_season("2609", "2609", "2703"))
        self.assertFalse(is_month_within_season("202608", "202609", "202703"))
        self.assertFalse(is_month_within_season("202704", "202609", "202703"))
        self.assertFalse(is_month_within_season("2608", "202609", "202703"))

    def test_get_active_category_ids(self):
        with mock.patch.dict(
            os.environ,
            {
                "DISCORD_CATEGORY_ID_DIV1": "111",
                "DISCORD_CATEGORY_ID_DIV2": "222",
            },
            clear=False,
        ):
            self.assertEqual(
                get_active_category_ids(),
                {"div1": {111}, "div2": {222}},
            )

    def test_format_sheet_date(self):
        self.assertEqual(
            format_sheet_date(
                datetime(2026, 9, 29, 21, 7), now=datetime(2026, 9, 30, 8, 0)
            ),
            "1日前",
        )
        self.assertEqual(
            format_sheet_date(
                datetime(2026, 9, 25, 21, 7), now=datetime(2026, 9, 30, 8, 0)
            ),
            "5日以上前",
        )

    def test_batch_get_values_returns_requested_ranges(self):
        class DummyValues:
            def __init__(self):
                self.ranges = None

            def batchGet(self, spreadsheetId, ranges):
                self.ranges = ranges

                class DummyResponse:
                    def execute(self):
                        return {
                            "valueRanges": [
                                {"values": [["a", "b"], ["c", "d"]]},
                                {"values": [["e", "f"]]},
                            ]
                        }

                return DummyResponse()

        class DummySpreadsheets:
            def values(self):
                return DummyValues()

        class DummySheetsClient:
            def __init__(self):
                self.service = type(
                    "Service", (), {"spreadsheets": lambda self: DummySpreadsheets()}
                )()

            def get_spreadsheet_id(self, spreadsheet_key):
                return "sheet-id"

        client = DummySheetsClient()
        result = __import__(
            "src.google_services", fromlist=["GoogleSheetsClient"]
        ).GoogleSheetsClient.batch_get_values(client, ["A1:B2", "C1:D1"])
        self.assertEqual(result, [[["a", "b"], ["c", "d"]], [["e", "f"]]])

    def test_update_last_post_dates_for_match_channels_clears_when_status_is_not_adjusting(
        self,
    ):
        class DummyChannel:
            name = "g-2609-home-away"
            category = type("Category", (), {"id": 123})()

            async def history(self, limit=200, oldest_first=False):
                yield type(
                    "Message",
                    (),
                    {
                        "author": type("Author", (), {"bot": False})(),
                        "created_at": datetime(2026, 9, 29, 12, 0),
                    },
                )()

        class DummySheets:
            def __init__(self):
                self.calls = []

            def get_values(self, range_name, spreadsheet_key):
                return [
                    [
                        "",
                        "",
                        "cid-home",
                        "",
                        "cid-away",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "確認済",
                        "",
                    ]
                ]

            def batch_update(self, updates, spreadsheet_key):
                self.calls.append((updates, spreadsheet_key))

        bot = type(
            "Bot",
            (),
            {
                "guilds": [type("Guild", (), {"text_channels": [DummyChannel()]})()],
                "club_cid_map": {"home": "cid-home", "away": "cid-away"},
                "sheets": DummySheets(),
            },
        )()

        with mock.patch.dict(
            os.environ,
            {
                "LEAGUE_CURRENT_SEASON_FIRST_MONTH": "202609",
                "LEAGUE_CURRENT_SEASON_LAST_MONTH": "202703",
            },
            clear=False,
        ):
            with mock.patch(
                "src.jobs.daily_batch.get_active_category_ids",
                return_value={"div1": {123}},
            ):
                with mock.patch(
                    "src.jobs.daily_batch.parse_match_channel",
                    return_value={
                        "division": "div1",
                        "yymm": "2609",
                        "home": "home",
                        "away": "away",
                    },
                ):
                    with mock.patch(
                        "src.jobs.daily_batch.is_month_within_season",
                        return_value=True,
                    ):
                        import asyncio

                        asyncio.run(
                            __import__(
                                "src.jobs.daily_batch",
                                fromlist=["update_last_post_dates_for_match_channels"],
                            ).update_last_post_dates_for_match_channels(bot)
                        )

        self.assertIn(([("場所調整!AB1", [[""]])], "shared"), bot.sheets.calls)

    def test_update_last_post_dates_for_match_channels_handles_mixed_statuses(self):
        class DummyChannel:
            def __init__(self, name, category_id):
                self.name = name
                self.category = type("Category", (), {"id": category_id})()

            async def history(self, limit=200, oldest_first=False):
                yield type(
                    "Message",
                    (),
                    {
                        "author": type("Author", (), {"bot": False})(),
                        "created_at": datetime(2026, 9, 29, 12, 0),
                    },
                )()

        class DummySheets:
            def __init__(self):
                self.calls = []

            def get_values(self, range_name, spreadsheet_key):
                return [
                    [
                        "",
                        "",
                        "cid-home1",
                        "",
                        "cid-away1",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "調整",
                        "",
                    ],
                    [
                        "",
                        "",
                        "cid-home2",
                        "",
                        "cid-away2",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "OK",
                        "",
                    ],
                    [
                        "",
                        "",
                        "cid-home3",
                        "",
                        "cid-away3",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "調整",
                        "",
                    ],
                ]

            def batch_update(self, updates, spreadsheet_key):
                self.calls.append((updates, spreadsheet_key))

        channels = [
            DummyChannel("g-2609-home1-away1", 123),
            DummyChannel("g-2609-home2-away2", 123),
            DummyChannel("g-2609-home3-away3", 123),
        ]
        bot = type(
            "Bot",
            (),
            {
                "guilds": [type("Guild", (), {"text_channels": channels})()],
                "club_cid_map": {
                    "home1": "cid-home1",
                    "away1": "cid-away1",
                    "home2": "cid-home2",
                    "away2": "cid-away2",
                    "home3": "cid-home3",
                    "away3": "cid-away3",
                },
                "sheets": DummySheets(),
            },
        )()

        with mock.patch.dict(
            os.environ,
            {
                "LEAGUE_CURRENT_SEASON_FIRST_MONTH": "202609",
                "LEAGUE_CURRENT_SEASON_LAST_MONTH": "202703",
            },
            clear=False,
        ):
            with mock.patch(
                "src.jobs.daily_batch.get_active_category_ids",
                return_value={"div1": {123}},
            ):
                with mock.patch(
                    "src.jobs.daily_batch.parse_match_channel",
                    side_effect=[
                        {
                            "division": "div1",
                            "yymm": "2609",
                            "home": "home1",
                            "away": "away1",
                        },
                        {
                            "division": "div1",
                            "yymm": "2609",
                            "home": "home2",
                            "away": "away2",
                        },
                        {
                            "division": "div1",
                            "yymm": "2609",
                            "home": "home3",
                            "away": "away3",
                        },
                    ],
                ):
                    with mock.patch(
                        "src.jobs.daily_batch.is_month_within_season",
                        return_value=True,
                    ):
                        import asyncio

                        asyncio.run(
                            __import__(
                                "src.jobs.daily_batch",
                                fromlist=["update_last_post_dates_for_match_channels"],
                            ).update_last_post_dates_for_match_channels(bot)
                        )

        self.assertEqual(len(bot.sheets.calls), 1)
        updates, spreadsheet_key = bot.sheets.calls[0]
        self.assertEqual(spreadsheet_key, "shared")
        self.assertEqual(
            [range_name for range_name, _ in updates],
            ["場所調整!AB1", "場所調整!AB2", "場所調整!AB3"],
        )
        self.assertEqual(
            [values for _, values in updates],
            [[["0日前"]], [[""]], [["0日前"]]],
        )

    def test_is_reminder_target_channel_accepts_cached_rows(self):
        class DummySheets:
            def __init__(self):
                self.calls = []

            def get_values(self, range_name, spreadsheet_key):
                self.calls.append((range_name, spreadsheet_key))
                return [
                    [
                        "",
                        "",
                        "cid-home",
                        "",
                        "cid-away",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "調整",
                        "",
                    ]
                ]

        bot = type(
            "Bot",
            (),
            {
                "club_cid_map": {"home": "cid-home", "away": "cid-away"},
                "sheets": DummySheets(),
            },
        )()
        self.assertTrue(
            is_reminder_target_channel(
                bot,
                "g-2609-home-away",
                [
                    [
                        "",
                        "",
                        "cid-home",
                        "",
                        "cid-away",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "調整",
                        "",
                    ]
                ],
            )
        )
        self.assertEqual(bot.sheets.calls, [])

    def test_is_reminder_target_channel(self):
        class DummySheets:
            def get_values(self, range_name, spreadsheet_key):
                self.range_name = range_name
                self.spreadsheet_key = spreadsheet_key
                return [
                    [
                        "",
                        "",
                        "cid-home",
                        "",
                        "cid-away",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "調整",
                        "",
                    ]
                ]

        bot = type(
            "Bot",
            (),
            {
                "club_cid_map": {"home": "cid-home", "away": "cid-away"},
                "sheets": DummySheets(),
            },
        )()
        self.assertTrue(is_reminder_target_channel(bot, "g-2609-home-away"))

        class DummySheetsCancelled:
            def get_values(self, range_name, spreadsheet_key):
                return [
                    [
                        "",
                        "",
                        "cid-home",
                        "",
                        "cid-away",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "確認済",
                        "",
                    ]
                ]

        bot2 = type(
            "Bot2",
            (),
            {
                "club_cid_map": {"home": "cid-home", "away": "cid-away"},
                "sheets": DummySheetsCancelled(),
            },
        )()
        self.assertFalse(is_reminder_target_channel(bot2, "g-2609-home-away"))

    def test_get_apply_forum_ids(self):
        with mock.patch.dict(
            os.environ,
            {
                "DISCORD_APPLY_FORUM_ID_DIV1": "111",
                "DISCORD_APPLY_FORUM_ID_DIV2": "222",
            },
            clear=False,
        ):
            self.assertEqual(get_apply_forum_ids(), {111, 222})

    def test_get_apply_type_options(self):
        options = get_apply_type_options()
        self.assertEqual(options[0][0], "1")
        self.assertEqual(options[0][1], "選手の新規登録")
        self.assertEqual(options[6][0], "7")
        self.assertEqual(options[6][1], "その他の申請")

    def test_get_apply_type_title(self):
        self.assertEqual(get_apply_type_title("選手の新規登録"), "選手の新規登録の申請")

    def test_get_round_number_from_sheet_rows(self):
        game_row = ["", "", "3", "", "", "", "", "", "", "", ""]
        location_row = ["", "", "", "", "", "", "", "", "", "10", ""]
        self.assertEqual(get_round_number_from_game_row(game_row), "3")
        self.assertEqual(get_round_number_from_location_row(location_row), "10")

    def test_get_target_yymm_for_channel_creation(self):
        self.assertEqual(
            get_target_yymm_for_channel_creation(datetime(2026, 8, 1)), "2610"
        )
        self.assertEqual(
            get_target_yymm_for_channel_creation(datetime(2026, 12, 1)), "2702"
        )

    def test_normalize_yymm_from_sheet_value(self):
        self.assertEqual(normalize_yymm_from_sheet_value("27/01"), "2701")
        self.assertEqual(normalize_yymm_from_sheet_value("2701"), "2701")

    def test_build_match_channel_name(self):
        self.assertEqual(
            build_match_channel_name("g", "2701", "home", "away"), "g-2701-home-away"
        )
        self.assertEqual(
            build_match_channel_name("gc", "2701", "コブラ", "sisu"),
            "gc-2701-コブラ-sisu",
        )


if __name__ == "__main__":
    unittest.main()

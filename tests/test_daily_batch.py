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
        self.assertEqual(format_sheet_date(datetime(2026, 9, 30, 21, 7)), "2026/09/30")

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

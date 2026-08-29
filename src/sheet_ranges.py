"""Spreadsheet range constants used across the project."""

GAME_SHEET_NAME = "Game"
SHARED_SHEET_NAME = "場所調整"

GAME_SHEET_RANGE = f"{GAME_SHEET_NAME}!A1:O200"
SHARED_SHEET_RANGE = f"{SHARED_SHEET_NAME}!A1:Z200"
SHARED_SHEET_RANGE_COMPACT = f"{SHARED_SHEET_NAME}!A1:P200"


def game_date_range(row_idx: int) -> str:
    """管理シートの日程更新範囲を返します。"""
    return f"{GAME_SHEET_NAME}!M{row_idx}:N{row_idx}"


def shared_location_range(row_idx: int) -> str:
    """場所調整シートの場所更新セルを返します。"""
    return f"{SHARED_SHEET_NAME}!P{row_idx}"


def shared_last_post_range(row_idx: int) -> str:
    """場所調整シートの最終投稿日セルを返します。"""
    return f"{SHARED_SHEET_NAME}!AB{row_idx}"

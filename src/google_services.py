"""Discordボットで使う Google API ラッパー。

このモジュールはサービスアカウントを使って、Sheets、Calendar、Storage
を簡易に操作するクライアントを提供します。
"""

import os
from typing import Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.cloud import storage

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/devstorage.read_write",
]


def _get_credentials() -> service_account.Credentials:
    """環境変数からサービスアカウントの認証情報を読み込みます。"""
    key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not key_path:
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS is required")
    return service_account.Credentials.from_service_account_file(key_path, scopes=SCOPES)


class GoogleSheetsClient:
    """複数のスプレッドシート ID に対応する Sheets クライアント。"""

    def __init__(self):
        credentials = _get_credentials()
        self.service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        self.spreadsheet_ids = {
            "div1": os.getenv("SPREADSHEET_DIV1_ID"),
            "div2": os.getenv("SPREADSHEET_DIV2_ID"),
            "shared": os.getenv("SPREADSHEET_SHARED_ID"),
            "default": os.getenv("SPREADSHEET_ID"),
        }
        if not any(self.spreadsheet_ids.values()):
            raise RuntimeError(
                "At least one of SPREADSHEET_ID, SPREADSHEET_DIV1_ID, SPREADSHEET_DIV2_ID, or SPREADSHEET_SHARED_ID is required"
            )

    def get_spreadsheet_id(self, spreadsheet_key: str = "default") -> str:
        """要求されたキーに対応するスプレッドシート ID を返します。"""
        spreadsheet_id = self.spreadsheet_ids.get(spreadsheet_key)
        if not spreadsheet_id:
            raise RuntimeError(
                f"Spreadsheet ID not found for key '{spreadsheet_key}'. "
                f"Available keys: {', '.join(k for k, v in self.spreadsheet_ids.items() if v)}"
            )
        return spreadsheet_id

    def append_row(
        self,
        row_values: list[Any],
        sheet_name: str,
        spreadsheet_key: str = "default",
    ) -> dict[str, Any]:
        """指定したスプレッドシートのシートに行を追加します。"""
        spreadsheet_id = self.get_spreadsheet_id(spreadsheet_key)
        return (
            self.service.spreadsheets()
            .values()
            .append(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A:Z",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [row_values]},
            )
            .execute()
        )

    def update_range(
        self,
        range_name: str,
        values: list[list[Any]],
        spreadsheet_key: str = "default",
    ) -> dict[str, Any]:
        """選択したスプレッドシートのセル範囲を更新します。"""
        spreadsheet_id = self.get_spreadsheet_id(spreadsheet_key)
        return (
            self.service.spreadsheets()
            .values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption="USER_ENTERED",
                body={"values": values},
            )
            .execute()
        )

    def get_values(
        self,
        range_name: str,
        spreadsheet_key: str = "default",
    ) -> list[list[Any]]:
        """選択したスプレッドシートの指定範囲の値を取得します。"""
        spreadsheet_id = self.get_spreadsheet_id(spreadsheet_key)
        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=range_name)
            .execute()
        )
        return result.get("values", [])



class GoogleCalendarClient:
    """指定したカレンダーにイベントを作成するクライアント。"""

    def __init__(self):
        credentials = _get_credentials()
        self.service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        self.calendar_id = os.getenv("CALENDAR_ID")
        if not self.calendar_id:
            raise RuntimeError("CALENDAR_ID is required")

    def create_event(
        self,
        summary: str,
        start_iso: str,
        end_iso: str,
        description: str | None = None,
        location: str | None = None,
        color_id: str | None = None,
    ) -> dict[str, Any]:
        """設定されたカレンダーにイベントを作成します。"""
        event: dict[str, Any] = {
            "summary": summary,
            "start": {"dateTime": start_iso, "timeZone": "Asia/Tokyo"},
            "end": {"dateTime": end_iso, "timeZone": "Asia/Tokyo"},
        }
        if description:
            event["description"] = description
        if location:
            event["location"] = location
        if color_id:
            event["colorId"] = color_id
        return self.service.events().insert(calendarId=self.calendar_id, body=event).execute()


class GoogleStorageClient:
    """GCS バケットから JSON ファイルを読み取るストレージクライアント。"""

    def __init__(self):
        credentials = _get_credentials()
        self.client = storage.Client(credentials=credentials)
        self.bucket_name = os.getenv("GCS_BUCKET_NAME")
        if not self.bucket_name:
            raise RuntimeError("GCS_BUCKET_NAME is required")
        self.bucket = self.client.bucket(self.bucket_name)

    def download_json(self, blob_name: str) -> Any:
        """設定された GCS バケットから JSON をダウンロードします。"""
        blob = self.bucket.blob(blob_name)
        data = blob.download_as_text(encoding="utf-8")
        return data

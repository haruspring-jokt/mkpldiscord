import json
from pathlib import Path
from typing import Any


class JsonStorage:
    """ボットの状態を保持するためのJSONベースストレージ。

    RDB を使わず、試合メタデータ、リマインダースケジュール、進捗などの内部状態を保持します。
    """

    def __init__(self, path: str | Path = "data/state.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    def _read(self) -> dict[str, Any]:
        """JSONファイル全体を読み込みます。"""
        with self.path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _write(self, data: dict[str, Any]) -> None:
        """JSONオブジェクト全体をファイルに書き込みます。"""
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """キーを指定して値を取得します。デフォルト値も指定できます。"""
        data = self._read()
        return data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """トップレベルキーに値を設定し、永続化します。"""
        data = self._read()
        data[key] = value
        self._write(data)

    def update(self, key: str, value: dict[str, Any]) -> None:
        """既存エントリに辞書をマージします。"""
        data = self._read()
        item = data.get(key, {})
        if not isinstance(item, dict):
            item = {}
        item.update(value)
        data[key] = item
        self._write(data)

    def all(self) -> dict[str, Any]:
        """保存済みの全データを返します。"""
        return self._read()

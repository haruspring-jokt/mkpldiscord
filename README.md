# MKPL Discord Bot

Google Cloud VM 上で常駐させる Discord ボットのプロジェクト骨組みです。

## 目的

- 「モルック関東プライムリーグ」用 Discord サーバーで自動リマインドを送信
- 試合日程・場所の確定受付・スプレッドシート/カレンダー連携
- Google フォーム経由の試合結果受信に対する通知
- 翌日 0:00 に暫定順位表を速報チャンネルに送信

## アーキテクチャ

- Python で実装
- Discord ボットは `discord.py` を使用
- 内部データは `data/state.json` に JSON 形式で保存
- Google API は Service Account を介して Sheets / Calendar / Storage にアクセス
- GCP VM 上でもローカルでも動作確認できる構成

## 主要ファイル

- `main.py` - アプリ起動スクリプト
- `src/bot.py` - Discord ボットとリマインド処理
- `src/google_services.py` - Google Sheets/Calendar/Storage 連携
- `src/storage.py` - JSON ベースの内部データ保存
- `data/state.json` - ボットの内部状態

## 試合日程確定モーダル

試合チャンネルで「@運営 日程」と投稿すると、ボタン付きメッセージが表示されます。
ボタンを押すとモーダル（日程・開始時間・場所）が開き、送信すると以下が自動で行われます。

1. 管理スプレッドシート（`SPREADSHEET_DIV1_ID` / `SPREADSHEET_DIV2_ID`）の `Game` シートに日程(M列)・時間(N列)を書き込み
   （F列=ホームCID、G列=アウェイCID で該当行を検索）
2. 共通スプレッドシート（`SPREADSHEET_SHARED_ID`）の `場所調整` シートに場所(P列)を書き込み
   （C列=ホームCID、E列=アウェイCID で該当行を検索）
3. Google カレンダーにイベントを作成（`Game` シートの J列=節番号、C列=試合IDを使用）
4. 試合チャンネルに日程登録完了メッセージを送信

クラブ略称→CIDの対応は `data/club.json` の `cid` フィールドを使用します。
リンク類（結果報告フォーム、日程ページ、調整用シート等）は `.env` の `MATCH_RESULT_FORM_URL_*` 等で設定してください。

## セットアップ

1. Python 3.11 以上をインストール
2. 仮想環境を作成

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Google Cloud サービスアカウントキーを作成し、`GOOGLE_APPLICATION_CREDENTIALS` 環境変数を設定
4. `.env.example` をコピーして `.env` を作成し、必要な値を設定

```bash
copy .env.example .env
```

5. 必要に応じてテストモードを有効にします。

```powershell
$env:TEST_REMINDER = "1"
python .\main.py
```

または `.env` に以下を追加して有効化できます。

```text
TEST_REMINDER=1
```

6. Discord Developer Portal でボットを作成し、`DISCORD_TOKEN` を設定

## 実行方法

```bash
python main.py
```

## Google API の権限

Service Account に以下のスコープ/権限を付与してください。

- Google Sheets API
- Google Calendar API
- Google Cloud Storage

Service Account を対象のスプレッドシート/カレンダーに共有する必要があります。

## GCP VM での運用

- GCP VM に Python と依存パッケージをインストール
- サービスアカウントキーを配置し、`GOOGLE_APPLICATION_CREDENTIALS` を設定
- `python main.py` で起動
- 永続的運用には `systemd` / Windows サービス / `tmux` / `screen` などを使用してください

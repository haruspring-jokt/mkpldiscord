# MKPL Discord Bot

モルック関東プライムリーグ向けの Discord 運営ボットです。
試合チャンネル運用、定期リマインド、Google Sheets / Calendar 連携を行います。

## 主な機能

- 毎月 10 日 / 20 日 / 25 日の自動リマインド送信
- 試合チャンネル作成時の初期案内メッセージ送信
- 「@運営 日程」投稿からの日程確定モーダル表示
- 日程確定内容の Google Sheets 反映
- Google Calendar イベント作成

### これから実装する機能

- [ ] シーズン中の毎月1日に2ヶ月後に予定されている試合チャンネルを新規作成する
- [ ] 試合があった日の22時に、暫定順位表を投稿する
- [ ] 試合予定日の午前7時に、試合に関するリマインド、試合後にフォーム入力、提出物のアップロードをする旨を送信する
- [x] 日次バッチで、試合チャンネルごとに最後の投稿が行われた日を共通調整シートに入力する
- [x] 選手登録・変更・解除、および移籍・レンタル移籍申請に関する受付
  - 申請する参加者はフォーラムに新規スレッドを作成
  - スレッドが作成されたら、botが申請の種類を尋ね、参加者はそれに回答する
  - botは申請種類に対応するモーダルを表示し、参加者がそれに入力、以降は人力で対応する
- [ ] GoogleCloudのVM上にこのbotを常駐させる

## モジュール構成

- `main.py`: エントリーポイント
- `src/bot.py`: Bot クラス、イベントフック、スケジューラ起動
- `src/reminders.py`: スケジューラ駆動のリマインダー送信処理
- `src/handlers.py`: メッセージ・コマンド・モーダル処理
- `src/utils.py`: チャンネル解析やシート検索などの共通関数
- `src/google_services.py`: Google API クライアント群
- `src/storage.py`: JSON ベースの簡易ストレージ
- `data/club.json`: クラブ略称とロール名 / CID の対応表
- `data/state.json`: ボット内部状態

## セットアップ手順

1. Python 3.11 以上をインストール
2. 仮想環境を作成して有効化

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. `.env.example` をコピーして `.env` を作成

```powershell
copy .env.example .env
```

4. `.env` の値を設定

- `DISCORD_TOKEN`
- `DISCORD_GUILD_ID`
- `GOOGLE_APPLICATION_CREDENTIALS`
- `SPREADSHEET_DIV1_ID`, `SPREADSHEET_DIV2_ID`, `SPREADSHEET_SHARED_ID`
- `CALENDAR_ID`
- `ADMIN_ROLE_ID`
- 各種 URL（`MATCH_RESULT_FORM_URL_*`, `SCHEDULE_PAGE_URL_*`, `SHARED_SHEET_URL`）

5. Google サービスアカウントに権限付与

- Google Sheets API
- Google Calendar API
- Google Cloud Storage

対象のスプレッドシートとカレンダーに、サービスアカウントの閲覧 / 編集権限を付与してください。

## 実行方法

```powershell
python .\main.py
```

## 開発時の動作確認手順

### 1. 構文チェック

```powershell
python -m py_compile src\bot.py src\reminders.py src\handlers.py src\utils.py src\google_services.py
```

### 2. DRY RUN で送信を抑止して起動確認

```powershell
$env:REMINDER_DRY_RUN = "1"
python .\main.py
```

### 3. 月次リマインダーのテスト実行

```powershell
$env:TEST_REMINDER = "1"
$env:TEST_REMINDER_DATE = "now+30s"
python .\main.py
```

### 4. Discord 上での操作確認

1. 試合チャンネルで `@運営 日程` を投稿
2. 表示されたボタンからモーダルを開く
3. 日程、開始時間、場所を入力して送信
4. Sheets 更新、Calendar 作成、完了メッセージ送信を確認

## 日程確定モーダルの処理内容

1. `Game` シートの M 列 / N 列に日程と開始時間を保存
2. `場所調整` シートの P 列に会場を保存
3. Google Calendar にイベントを作成
4. チャンネルに完了メッセージを投稿

## 運用メモ

- 本番運用では `REMINDER_DRY_RUN=0` に戻してください。
- VM 常駐は `systemd`、`tmux`、`screen` などを利用してください。
- `.env` は機密情報を含むため、リポジトリ外で安全に管理してください。

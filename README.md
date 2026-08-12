# MKPL Discord Bot

モルック関東プライムリーグ向けの Discord 運営ボットです。
試合チャンネル運用、定期リマインド、Google Sheets / Calendar 連携を行います。

## 主な機能

- 毎月 10 日 / 20 日 / 25 日の自動リマインド送信
- 毎月 1 日に 2 ヶ月後の試合チャンネルを自動作成
- 試合チャンネル作成時の初期案内メッセージ送信
- 「@運営 日程」投稿からの日程確定モーダル表示
- 日程確定内容の Google Sheets 反映
- Google Calendar イベント作成
- 日次バッチで試合チャンネルの最終投稿日を共有シートへ記録
- 申請フォーラムからの選手登録・移籍・異動申請受付

### 進行中 / 今後の機能

- [ ] 試合があった日の 22 時に、暫定順位表を投稿する
- [ ] 試合予定日の午前 7 時に、試合に関するリマインド、提出物のアップロードを案内する
- [ ] Google Cloud の VM 上で常駐運用する

## モジュール構成

- `main.py`: エントリーポイント
- `src/bot.py`: Bot 本体、イベントフック、ジョブ登録
- `src/handlers/`: ユーザー入力系処理のパッケージ
  - `commands.py`: メッセージコマンドと `@運営 日程` 検知
  - `channel_create.py`: 試合チャンネル作成時の初期案内
  - `schedule.py`: 日程確定モーダルと Sheets / Calendar 反映
  - `applications.py`: 申請フォーラムと申請モーダル
- `src/utils.py`: チャンネル解析やシート検索などの共通関数
- `src/google_services.py`: Google API クライアント群
- `src/storage.py`: JSON ベースの簡易状態保存
- `src/jobs/`: 各定期ジョブの実装群
  - `channel_create_batch.py`: 2 ヶ月後試合チャンネル作成バッチ
  - `daily_batch.py`: 最終投稿日更新バッチ
  - `reminder_10.py`: 10 日リマインド
  - `reminder_20.py`: 20 日リマインド
  - `reminder_25.py`: 25 日リマインド
  - `shared.py`: ジョブ間で共通利用する判定関数
- `src/reminders.py`: 既存互換用のラッパー層
- `data/club.json`: クラブ略称、Discord ロール名、CID の対応表
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

必須項目:

- `DISCORD_TOKEN`
- `DISCORD_GUILD_ID`
- `GOOGLE_APPLICATION_CREDENTIALS`
- `SPREADSHEET_DIV1_ID`, `SPREADSHEET_DIV2_ID`, `SPREADSHEET_SHARED_ID`
- `CALENDAR_ID`
- `GCS_BUCKET_NAME`
- `ADMIN_ROLE_ID`
- `MATCH_RESULT_FORM_URL_DIV1`, `MATCH_RESULT_FORM_URL_DIV2`
- `SCHEDULE_PAGE_URL_DIV1`, `SCHEDULE_PAGE_URL_DIV2`
- `SHARED_SHEET_URL`
- `MATCH_SITE_BASE_URL`
- `LEAGUE_LABEL_DIV1`, `LEAGUE_LABEL_DIV2`
- `LEAGUE_EVENT_PREFIX_DIV1`, `LEAGUE_EVENT_PREFIX_DIV2`
- `LEAGUE_CURRENT_SEASON`
- `LEAGUE_CURRENT_SEASON_FIRST_MONTH`
- `LEAGUE_CURRENT_SEASON_LAST_MONTH`
- `DISCORD_CATEGORY_ID_DIV1`, `DISCORD_CATEGORY_ID_DIV2`
- `DISCORD_APPLY_FORUM_ID_DIV1`, `DISCORD_APPLY_FORUM_ID_DIV2`

ジョブ制御:

- `REMINDER_DRY_RUN`
- `GAME_CHANNEL_CREATE_BATCH_ENABLED`, `GAME_CHANNEL_CREATE_BATCH_TIME`
- `REMINDER_10_ENABLED`, `REMINDER_10_SCHEDULE`
- `REMINDER_20_ENABLED`, `REMINDER_20_SCHEDULE`
- `REMINDER_25_ENABLED`, `REMINDER_25_SCHEDULE`
- `DAILY_BATCH_ENABLED`, `DAILY_BATCH_TIME`

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
python -m py_compile src\bot.py src\reminders.py src\handlers\__init__.py src\handlers\commands.py src\handlers\channel_create.py src\handlers\schedule.py src\handlers\applications.py src\utils.py src\google_services.py
```

### 2. DRY RUN で送信を抑止して起動確認

```powershell
$env:REMINDER_DRY_RUN = "1"
python .\main.py
```

### 3. ジョブのテスト実行（必要に応じて）

```powershell
# 例: 10日リマインドのロジックを手元で確認したいとき
$env:REMINDER_DRY_RUN = "1"
python .\main.py
```

> 具体的なジョブの呼び出しは APScheduler に依存するため、手動実行では `on_ready` で登録した cron が動く形で確認します。

### 4. Discord 上での操作確認

1. 試合チャンネルで `@運営 日程` を投稿
2. 表示されたボタンからモーダルを開く
3. 日程、開始時間、場所を入力して送信
4. Sheets 更新、Calendar 作成、完了メッセージ送信を確認
5. 申請フォーラムで新規スレッドを作成し、申請種別選択ボタンが出ることを確認

## 月次チャンネル作成バッチの処理

1. `GAME_CHANNEL_CREATE_BATCH_ENABLED=1` のときだけ動作する
2. `GAME_CHANNEL_CREATE_BATCH_TIME` に `ddhhmm` 形式で設定した日時に実行する
3. `場所調整` シートから現在月の 2 ヶ月後に該当する試合を抽出する
4. `B列` が `y` なら `g`、それ以外なら `gc` を prefix とする
5. `I列` の `yy/mm` を `yymm` に正規化し `g-2701-home-away` 形式でチャンネル名を生成する
6. ホーム・アウェイのロールと運営ロールを許可し、プライベートチャンネルとして作成する
7. 既存のチャンネル作成ハンドラで初期メッセージの送信を行う

## 日程確定モーダルの処理内容

1. `Game` シートの M 列 / N 列に日程と開始時間を保存
2. `場所調整` シートの P 列に会場を保存
3. Google Calendar にイベントを作成
4. チャンネルに完了メッセージを投稿

## 運用メモ

- 本番運用では `REMINDER_DRY_RUN=0` に戻してください。
- VM 常駐は `systemd`、`tmux`、`screen` などを利用してください。
- `.env` は機密情報を含むため、リポジトリ外で安全に管理してください。

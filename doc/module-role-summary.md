# 機能とモジュールの役割（要約）

## 機能要約

- 定期リマインダー: 毎月 10 日 / 20 日 / 25 日に対象試合チャンネルへ通知
- チャンネル初期案内: 試合チャンネル作成時に運用ガイドを自動投稿
- 日程確定モーダル: 「@運営 日程」を起点に入力 UI を表示
- Google 連携: 日程データを Sheets に反映し、Calendar イベントを作成
- 追跡性: DRY RUN やログ出力で運用時の確認をしやすくする

## モジュールの責務

## main.py

- `.env` を読み込み、`LeagueBot` を生成して起動する。

## src/bot.py

- Bot 本体クラスを提供する。
- Discord イベント (`on_ready`, `on_message`, `on_guild_channel_create`) を受ける。
- APScheduler の起動とジョブ登録を行う。
- 個別ロジックは `src/reminders.py` / `src/handlers.py` に委譲する。

## src/reminders.py

- スケジューラで実行される通知処理を担当する。
- 対象月の試合チャンネルを抽出し、10日/20日/25日の文面を送信する。
- `REMINDER_DRY_RUN` が有効な場合は送信せずログのみ出力する。

## src/handlers.py

- ユーザー起点の処理を担当する。
- `!status` コマンドや「@運営 日程」の検知を行う。
- モーダル入力値の検証、Sheets 更新、Calendar 作成、完了通知を行う。
- UI クラス (`ScheduleModal`, `ScheduleTriggerView`) を提供する。

## src/utils.py

- 文字列解析や検索など、複数モジュールで再利用する関数を提供する。
- 例: 試合チャンネル名解析、ロールメンション解決、シート行検索、Google Calendar リンク生成。

## src/google_services.py

- Google Sheets / Calendar / Storage API へのアクセスラッパーを提供する。
- 認証、取得、更新、イベント作成などの I/O を集約する。

## src/storage.py

- JSON ファイルを使った簡易状態保存を担当する。

## data/club.json

- クラブ略称、Discord ロール名、CID の対応表を保持する。

## data/state.json

- ボットの内部状態を永続化する。

## 設定ファイル

## .env

- 実運用用の環境変数を保持する。
- トークンや ID を含むため機密として扱う。

## .env.example

- 新規セットアップ用のテンプレート。
- 各変数の意味がコメントで確認できる。

## 拡張時の方針

- スケジューラ起点の新機能は `src/reminders.py` を優先して追加する。
- ユーザー入力起点の新機能は `src/handlers.py` に追加する。
- 共通化できる処理は `src/utils.py` へ寄せる。
- 外部 API 呼び出しは `src/google_services.py` に閉じ込める。

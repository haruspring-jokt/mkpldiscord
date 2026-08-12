# 機能とモジュールの役割（要約）

## 機能要約

- 定期リマインダー: 毎月 10 日 / 20 日 / 25 日に対象試合チャンネルへ通知
- チャンネル新規作成バッチ: 毎月 1 日に 2 ヶ月後の試合チャンネルを自動生成
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
- 個別ジョブ実装は `src/jobs/*.py` に分離し、そこへ処理を委譲する。

## src/jobs/

- 各定期ジョブの処理を分離して保持する。
- `channel_create_batch.py`: 2 ヶ月後試合チャンネル作成バッチ
- `daily_batch.py`: 最終投稿日更新ジョブ
- `reminder_10.py`: 10 日リマインドジョブ
- `reminder_20.py`: 20 日リマインドジョブ
- `reminder_25.py`: 25 日リマインドジョブ
- `shared.py`: ジョブ間で共通利用する helper を持つ

## src/reminders.py

- 既存 import 互換のために残した薄いラッパー層。
- 実際のジョブロジックは `src/jobs/` 配下へ分離されている。

## src/handlers/

- ユーザー起点の処理をパッケージ単位で分割して管理する。
- `commands.py`: `!status` コマンドや「@運営 日程」の検知を行う。
- `channel_create.py`: 新規チャンネル作成時の初期案内メッセージ送信を行う。
- `schedule.py`: モーダル入力値の検証、Sheets 更新、Calendar 作成、完了通知を行う。
- `applications.py`: 申請フォーラムのスレッド作成と申請種別選択 UI を提供する。

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

- スケジューラ起点の新機能は `src/jobs/` に個別モジュールとして追加する。
- ユーザー入力起点の新機能は `src/handlers/` 配下の適切なモジュールに追加する。
- 共通化できる処理は `src/utils.py` へ寄せる。
- 外部 API 呼び出しは `src/google_services.py` に閉じ込める。

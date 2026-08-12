# インスタンス作成

- [インスタンスを作成] をクリックします。
- 以下の項目を設定します：
- 名前: hoge-bot-vm
- リージョン: us-west1（オレゴン） または us-east1（サウスカロライナ）、us-central1（アイオワ）
  ※もし「在庫切れエラー（ゾーン制限）」が出た場合は、リージョンを「オレゴン（us-west1）」にして、ゾーンを us-west1-b や us-west1-c に切り替えてみてください。
- シリーズ: E2
- マシンタイプ: e2-micro（2 vCPU、1 GB メモリ。※「Always Free の対象」の記述があることを確認）
- プロビジョニング モデル: 標準
- ブートディスクの設定（ここが最も重要です！）
  - [変更] ボタンをクリックします。
  - オペレーティングシステム: Ubuntu
  - バージョン: Ubuntu 24.04 LTS
  - ブートディスクの種類: 「標準永続ディスク」（Standard Persistent Disk）
    - ※デフォルトで「バランス」や「SSD」が選ばれやすいため、必ず 「標準永続ディスク」 に変更してください。
    - サイズ: 30 (GB)
      ※無料枠の最大値である 30 GB に設定します。これで容量不足は二度と起きません。
- 選択をクリックして戻ります。
- その他の設定（ファイアウォールなど）はデフォルト（チェックなし）のままで構いません。
- 画面最下部の [作成] をクリックします。

# サーバー接続と初期設定

- 作成されたVMの右側にある 「SSH」 ボタン（または Cloud Shell）からログインします。
- ログイン後、システムを最新化します。

```
sudo apt update && sudo apt upgrade -y
```

今後のPythonのインストールに必要なビルドツール群をまとめてインストールします。

```
sudo apt install -y python3.12 python3.12-venv python3.12-dev git
python3 --version
```

※ Python 3.12.xx と表示されれば完了です。

# ボットプログラムのダウンロードと設定

GitHubからリポジトリをダウンロードします。

```
git clone <あなたのGitHubリポジトリのURL>
cd <リポジトリのフォルダ名>
```

.env ファイルのアップロードと移動

SSH画面の右上にある「歯車アイコン」等から 「ファイルをアップロード」 を選び、パソコンにある .env ファイルを選択します。
アップロードされた .env ファイルを、ボットのディレクトリ（現在いる場所）に移動させます。

```
mv ~/.env .
```

隠しファイル表示コマンドで、正しく移動できたか確認します。
また、同様に`club.json`、`service-account.json`もアップロード、設定する。

```
ls -la
```

仮想環境（venv）の作成とライブラリのインストール：setupスクリプトを使用する。

```
bash ./scripts/setup.sh
source .venv/bin/activate
```

# 日本時間に設定する

```
sudo timedatectl set-timezone Asia/Tokyo
date
```

# Discordボットを24時間常時起動する（systemd）

SSHの画面を閉じてもボットが止まらないように、サービス化します。

設定ファイルを作成します。

```
sudo nano /etc/systemd/system/discord-bot.service
```

以下の内容を貼り付けます（<リポジトリ名> の部分は実際のフォルダ名に書き換えてください）。

```
[Unit]
Description=Discord Bot
After=network.target

[Service]
Type=simple
User=hoge_user
WorkingDirectory=/home/hoge_user/<リポジトリ名>
ExecStart=/home/hoge_user/<リポジトリ名>/.venv/bin/python main.py
Restart=always
```

(保存方法： Ctrl + O ➔ Enter ➔ Ctrl + X)

サービスを起動して有効化（自動起動化）します。

```
# 設定ファイルの再読込
sudo systemctl daemon-reload
# ボットの起動
sudo systemctl start discord-bot
# VM起動時に自動で立ち上がるようにする
sudo systemctl enable discord-bot
``

稼働状態を確認します。

```
sudo systemctl status discord-bot
```

※ active (running) と緑色で表示されていれば、無事に24時間常時起動に成功です！

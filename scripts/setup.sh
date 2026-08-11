#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
fi

echo "Setup complete."
echo "Edit .env and configure DISCORD_TOKEN, DISCORD_GUILD_ID, GOOGLE_APPLICATION_CREDENTIALS, SPREADSHEET_ID, CALENDAR_ID, GCS_BUCKET_NAME."
#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

if [ -n "${VIRTUAL_ENV:-}" ]; then
  active_venv="$(cd "$VIRTUAL_ENV" 2>/dev/null && pwd)"
  local_venv="$(cd "$root_dir/.venv" 2>/dev/null && pwd)"
  if [ "$active_venv" = "$local_venv" ]; then
    echo "A virtual environment is already active in this shell. Run 'deactivate' or open a new terminal before rerunning setup.sh." >&2
    exit 1
  fi
fi

if [ -d ".venv" ]; then
  if pgrep -af "$root_dir/.venv/bin/python" >/dev/null 2>&1; then
    echo "The project virtual environment is currently in use by a Python process. Close the terminal/session with the active .venv or stop the Python process, then run setup.sh again." >&2
    exit 1
  fi

  echo "Existing virtual environment found; removing stale or broken environment..."
  rm -rf ".venv"
fi

echo "Creating virtual environment..."
if ! python3 -m venv .venv; then
  echo "Failed to create virtual environment." >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing requirements..."
if ! python -m pip install --upgrade pip "setuptools<81"; then
  echo "Failed to upgrade pip and pin setuptools." >&2
  exit 1
fi

if ! python -m pip install -r requirements.txt; then
  echo "Failed to install Python dependencies." >&2
  exit 1
fi

if [ ! -f .env ] && [ -f .env.example ]; then
  echo "Creating .env from .env.example..."
  cp .env.example .env
fi

echo "Setup complete."
echo "Next: edit .env and set DISCORD_TOKEN, DISCORD_GUILD_ID, GOOGLE_APPLICATION_CREDENTIALS, SPREADSHEET_ID, CALENDAR_ID, GCS_BUCKET_NAME."
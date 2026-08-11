<#
.SYNOPSIS
  Set up the Python virtual environment and install dependencies on Windows.
#>

param()

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root\..\

Write-Host "Creating virtual environment..."
python -m venv .venv
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to create virtual environment."
    exit 1
}

Write-Host "Installing requirements..."
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install Python dependencies."
    exit 1
}

if (-Not (Test-Path .env) -and (Test-Path .env.example)) {
    Write-Host "Creating .env from .env.example..."
    Copy-Item .env.example .env
}

Write-Host "Setup complete."
Write-Host "Next: edit .env and set DISCORD_TOKEN, DISCORD_GUILD_ID, GOOGLE_APPLICATION_CREDENTIALS, SPREADSHEET_ID, CALENDAR_ID, GCS_BUCKET_NAME."

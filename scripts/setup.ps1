<#
.SYNOPSIS
  Set up the Python virtual environment and install dependencies on Windows.
#>

param()

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root\..\

if ($env:VIRTUAL_ENV) {
    $activeVenv = (Resolve-Path $env:VIRTUAL_ENV).Path
    $localVenv = (Resolve-Path ".venv").Path
    if ($activeVenv -eq $localVenv) {
        Write-Error "A virtual environment is already active in this PowerShell session. Run 'deactivate' or open a new terminal before rerunning setup.ps1."
        exit 1
    }
}

if (Test-Path ".venv") {
    $venvLockProcesses = @(Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Path -and $_.Path -match "\\.venv\\Scripts\\python.exe" })
    if ($venvLockProcesses.Count -gt 0) {
        Write-Error "The project virtual environment is currently in use by a Python process. Close the terminal/session with the active .venv or stop the Python process, then run setup.ps1 again."
        exit 1
    }

    Write-Host "Existing virtual environment found; removing stale or broken environment..."
    try {
        Remove-Item -Recurse -Force .venv
    }
    catch {
        Write-Error "Could not remove the existing .venv because it is still in use. Close any terminals running this environment and try again."
        exit 1
    }
}

Write-Host "Creating virtual environment..."
python -m venv .venv
if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to create virtual environment."
    exit 1
}

Write-Host "Installing requirements..."
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip "setuptools<81"
python -m pip install -r requirements.txt
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

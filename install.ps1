param(
    [string]$PythonCommand = "python",
    [string]$VenvDir = ".venv"
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

$ConfigFile = "config/config.yaml"
$ExampleConfig = "config/config.example.yaml"
$OllamaHelperModel = "electronics-helper"
$OllamaBaseModel = "qwen3-coder:30b"
$OllamaHelperModelfile = "ollama/Modelfile.electronics-helper"
if ($IsWindows) {
    $VenvPython = Join-Path $VenvDir "Scripts/python.exe"
}
else {
    $VenvPython = Join-Path $VenvDir "bin/python"
}

function Write-Info {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message"
}

function Write-Warn {
    param([string]$Message)
    Write-Host ""
    Write-Warning $Message
}

function Require-Command {
    param(
        [string]$CommandName,
        [string]$PackageHint
    )

    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        throw "Missing '$CommandName'. Install $PackageHint, then rerun .\install.ps1."
    }
}

function Read-HiddenValue {
    param([string]$Prompt)

    $SecureValue = Read-Host $Prompt -AsSecureString
    $Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
    }
}

function Write-ConfigValue {
    param(
        [string]$Key,
        [string]$Value
    )

    $Python = @'
from __future__ import annotations

import sys
from pathlib import Path

import yaml

config_path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]

with config_path.open("r", encoding="utf-8") as f:
    config = yaml.safe_load(f) or {}

config[key] = value

with config_path.open("w", encoding="utf-8") as f:
    yaml.safe_dump(config, f, sort_keys=False)
'@

    & $VenvPython -c $Python $ConfigFile $Key $Value
}

function Read-ConfigValue {
    param([string]$Key)

    $Python = @'
from __future__ import annotations

import sys
from pathlib import Path

import yaml

config_path = Path(sys.argv[1])
key = sys.argv[2]

with config_path.open("r", encoding="utf-8") as f:
    config = yaml.safe_load(f) or {}

print(config.get(key, "") or "")
'@

    return (& $VenvPython -c $Python $ConfigFile $Key).Trim()
}

function Test-DatabaseUrl {
    param([string]$DatabaseUrl)

    & psql $DatabaseUrl -At -f "db/queries/install_connection_check.sql" *> $null
    return $LASTEXITCODE -eq 0
}

function Test-OllamaHelperModel {
    $Models = & ollama list 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $false
    }
    return [bool]($Models | Select-String -Pattern "^$([regex]::Escape($OllamaHelperModel)):latest\s")
}

function Install-OllamaIfMissing {
    if (Get-Command "ollama" -ErrorAction SilentlyContinue) {
        return
    }

    Write-Warn "Ollama was not found in PATH. The app can install, but queries need an Ollama server."
    $InstallOllama = Read-Host "Install Ollama now? [Y/n]"
    if (-not ([string]::IsNullOrWhiteSpace($InstallOllama) -or $InstallOllama -match "^[Yy]$")) {
        Write-Warn "Skipping Ollama install. Install it later from https://ollama.com before using local model queries."
        return
    }

    if (Get-Command "winget" -ErrorAction SilentlyContinue) {
        Write-Info "Installing Ollama with winget"
        & winget install --id Ollama.Ollama -e --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install Ollama with winget."
        }
    }
    else {
        Write-Warn "winget was not found. Install Ollama from https://ollama.com/download/windows, then rerun .\install.ps1."
        return
    }

    if (-not (Get-Command "ollama" -ErrorAction SilentlyContinue)) {
        Write-Warn "Ollama still is not available in this shell. Open a new terminal or update PATH, then rerun .\install.ps1."
    }
}

function Setup-OllamaHelperModel {
    if (-not (Get-Command "ollama" -ErrorAction SilentlyContinue)) {
        return
    }
    if (-not (Test-Path $OllamaHelperModelfile)) {
        Write-Warn "Missing $OllamaHelperModelfile; cannot create ${OllamaHelperModel}:latest."
        return
    }

    if (Test-OllamaHelperModel) {
        $RefreshModel = Read-Host "Refresh local Ollama model ${OllamaHelperModel}:latest from the repo Modelfile? [y/N]"
        if ($RefreshModel -notmatch "^[Yy]$") {
            return
        }
    }
    else {
        $CreateModel = Read-Host "Create local Ollama model ${OllamaHelperModel}:latest now? This pulls $OllamaBaseModel if needed. [Y/n]"
        if (-not ([string]::IsNullOrWhiteSpace($CreateModel) -or $CreateModel -match "^[Yy]$")) {
            Write-Warn "Skipping ${OllamaHelperModel}:latest creation. Queries will fail until the model exists in Ollama."
            return
        }
    }

    Write-Info "Preparing local Ollama model ${OllamaHelperModel}:latest"
    & ollama pull $OllamaBaseModel
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to pull Ollama base model $OllamaBaseModel."
    }
    & ollama create $OllamaHelperModel -f $OllamaHelperModelfile
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create Ollama model ${OllamaHelperModel}:latest."
    }
}

function Show-PostgresHelp {
    Write-Host @"

Postgres setup needed

Create a database and app user from a terminal that has Postgres admin access.
On Windows, open SQL Shell or pgAdmin as a Postgres admin and run:

  CREATE USER circuitshelf_app WITH PASSWORD 'choose-a-real-password';
  CREATE DATABASE circuitshelf OWNER circuitshelf_app;
  GRANT ALL PRIVILEGES ON DATABASE circuitshelf TO circuitshelf_app;
  \c circuitshelf
  CREATE EXTENSION IF NOT EXISTS pgcrypto;
  CREATE EXTENSION IF NOT EXISTS citext;

Then use this DATABASE_URL when prompted:

  postgresql://circuitshelf_app:choose-a-real-password@localhost:5432/circuitshelf

"@
}

Write-Info "CircuitShelf guided installer"

Require-Command $PythonCommand "Python 3.12 or newer"
Require-Command "node" "Node.js"
Require-Command "npm" "npm"
Require-Command "psql" "the PostgreSQL client tools"

$TesseractCommand = Get-Command "tesseract" -ErrorAction SilentlyContinue
if (-not $TesseractCommand) {
    Write-Warn "Tesseract was not found. OCR will not work until Tesseract OCR is installed and in PATH."
}

Install-OllamaIfMissing

Write-Info "Creating Python virtual environment"
if (-not (Test-Path $VenvDir)) {
    & $PythonCommand -m venv $VenvDir
}

Write-Info "Installing Python dependencies"
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements.txt

Write-Info "Installing frontend dependencies"
& npm --prefix frontend install

if (-not (Test-Path $ConfigFile)) {
    Write-Info "Creating local config from example"
    Copy-Item $ExampleConfig $ConfigFile
}
else {
    Write-Info "Keeping existing $ConfigFile"
}

foreach ($Directory in @("training", "data", "cache", "logs", "trainingdata")) {
    New-Item -ItemType Directory -Force -Path $Directory | Out-Null
}

$CurrentDatabaseUrl = Read-ConfigValue "DATABASE_URL"
if ($env:DATABASE_URL) {
    $CurrentDatabaseUrl = $env:DATABASE_URL
    Write-ConfigValue "DATABASE_URL" $CurrentDatabaseUrl
}

if ($TesseractCommand) {
    Write-ConfigValue "TESSERACT_CMD" ($TesseractCommand.Source)
}

while ([string]::IsNullOrWhiteSpace($CurrentDatabaseUrl) -or -not (Test-DatabaseUrl $CurrentDatabaseUrl)) {
    if (-not [string]::IsNullOrWhiteSpace($CurrentDatabaseUrl)) {
        Write-Warn "Could not connect with the configured DATABASE_URL."
    }

    Show-PostgresHelp
    $CurrentDatabaseUrl = Read-HiddenValue "DATABASE_URL (input hidden)"
    if ([string]::IsNullOrWhiteSpace($CurrentDatabaseUrl)) {
        throw "DATABASE_URL is required for DB-backed auth and settings."
    }
    Write-ConfigValue "DATABASE_URL" $CurrentDatabaseUrl
}

Write-Info "Applying database migrations"
& $VenvPython tools/db_migrate.py

$CreateAdmin = Read-Host "Create or update an admin login user now? [Y/n]"
if ([string]::IsNullOrWhiteSpace($CreateAdmin) -or $CreateAdmin -match "^[Yy]$") {
    $AdminUsername = Read-Host "Admin username [admin]"
    if ([string]::IsNullOrWhiteSpace($AdminUsername)) {
        $AdminUsername = "admin"
    }
    & $VenvPython tools/db_user.py upsert $AdminUsername --admin
}

Setup-OllamaHelperModel

Write-Info "Building frontend"
& npm --prefix frontend run build

Write-Info "Running backend smoke checks"
& $VenvPython -m py_compile circuitshelf.py datasheet_intelligence.py circuit_build_cards.py db/connection.py db/users.py db/sql.py db/datasheet_intelligence_store.py tools/db_migrate.py tools/db_user.py

Write-Host @"

Install complete.

Start CircuitShelf with:

  .venv\Scripts\python.exe circuitshelf.py

Then open the URL printed by the server.

Put source PDFs, books, datasheets, and notes under training\ before indexing.
"@

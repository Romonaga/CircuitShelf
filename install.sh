#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

VENV_DIR="${VENV_DIR:-.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CONFIG_FILE="config/config.yaml"
EXAMPLE_CONFIG="config/config.example.yaml"
OLLAMA_HELPER_MODEL="electronics-helper"
OLLAMA_BASE_MODEL="qwen3-coder:30b"
OLLAMA_HELPER_MODELFILE="ollama/Modelfile.electronics-helper"

info() {
  printf '\n==> %s\n' "$*"
}

warn() {
  printf '\nWARNING: %s\n' "$*" >&2
}

fail() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

prompt_yes_no() {
  local prompt="$1"
  local default="${2:-y}"
  local answer suffix
  if [[ "$default" == "y" ]]; then
    suffix="[Y/n]"
  else
    suffix="[y/N]"
  fi

  read -r -p "$prompt $suffix " answer
  answer="${answer:-$default}"
  [[ "$answer" =~ ^[Yy]$ ]]
}

require_command() {
  local command_name="$1"
  local package_hint="$2"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    fail "Missing '$command_name'. Install $package_hint, then rerun ./install.sh."
  fi
}

write_config_value() {
  local key="$1"
  local value="$2"
  "$VENV_DIR/bin/python" - "$CONFIG_FILE" "$key" "$value" <<'PY'
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
PY
}

read_config_value() {
  local key="$1"
  "$VENV_DIR/bin/python" - "$CONFIG_FILE" "$key" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

import yaml

config_path = Path(sys.argv[1])
key = sys.argv[2]

with config_path.open("r", encoding="utf-8") as f:
    config = yaml.safe_load(f) or {}

print(config.get(key, "") or "")
PY
}

test_database_url() {
  local database_url="$1"
  psql "$database_url" -At -f db/queries/install_connection_check.sql >/dev/null
}

install_ollama_if_missing() {
  if command -v ollama >/dev/null 2>&1; then
    return
  fi

  warn "Ollama was not found in PATH. The app can install, but queries need an Ollama server."
  if ! prompt_yes_no "Install Ollama now?" "y"; then
    warn "Skipping Ollama install. Install it later from https://ollama.com before using local model queries."
    return
  fi

  if [[ "$(uname -s)" == "Darwin" ]]; then
    if command -v brew >/dev/null 2>&1; then
      info "Installing Ollama with Homebrew"
      brew install ollama
    else
      warn "Homebrew was not found. Install Ollama from https://ollama.com/download, then rerun ./install.sh."
      return
    fi
  else
    if ! command -v curl >/dev/null 2>&1; then
      warn "curl was not found. Install curl or install Ollama from https://ollama.com/download, then rerun ./install.sh."
      return
    fi
    info "Installing Ollama from https://ollama.com"
    curl -fsSL https://ollama.com/install.sh | sh
  fi

  if ! command -v ollama >/dev/null 2>&1; then
    warn "Ollama still is not available in this shell. Open a new terminal or update PATH, then rerun ./install.sh."
  fi
}

ollama_model_exists() {
  ollama list | awk 'NR > 1 {print $1}' | grep -qx "${OLLAMA_HELPER_MODEL}:latest"
}

setup_ollama_helper_model() {
  if ! command -v ollama >/dev/null 2>&1; then
    return
  fi
  if [[ ! -f "$OLLAMA_HELPER_MODELFILE" ]]; then
    warn "Missing $OLLAMA_HELPER_MODELFILE; cannot create $OLLAMA_HELPER_MODEL:latest."
    return
  fi

  if ollama_model_exists; then
    if ! prompt_yes_no "Refresh local Ollama model $OLLAMA_HELPER_MODEL:latest from the repo Modelfile?" "n"; then
      return
    fi
  else
    if ! prompt_yes_no "Create local Ollama model $OLLAMA_HELPER_MODEL:latest now? This pulls $OLLAMA_BASE_MODEL if needed." "y"; then
      warn "Skipping $OLLAMA_HELPER_MODEL:latest creation. Queries will fail until the model exists in Ollama."
      return
    fi
  fi

  info "Preparing local Ollama model $OLLAMA_HELPER_MODEL:latest"
  ollama pull "$OLLAMA_BASE_MODEL"
  ollama create "$OLLAMA_HELPER_MODEL" -f "$OLLAMA_HELPER_MODELFILE"
}

show_postgres_help() {
  cat <<'EOF'

Postgres setup needed

Create a database and app user from a terminal that has Postgres admin access:

  sudo -u postgres psql

Then run:

  CREATE USER circuitshelf_app WITH PASSWORD 'choose-a-real-password';
  CREATE DATABASE circuitshelf OWNER circuitshelf_app;
  GRANT ALL PRIVILEGES ON DATABASE circuitshelf TO circuitshelf_app;
  \c circuitshelf
  CREATE EXTENSION IF NOT EXISTS pgcrypto;
  CREATE EXTENSION IF NOT EXISTS citext;
  \q

Then use this DATABASE_URL when prompted:

  postgresql://circuitshelf_app:choose-a-real-password@localhost:5432/circuitshelf

EOF
}

info "CircuitShelf guided installer"

require_command "$PYTHON_BIN" "Python 3.12 or newer"
require_command node "Node.js"
require_command npm "npm"
require_command psql "the PostgreSQL client tools"

if ! command -v tesseract >/dev/null 2>&1; then
  warn "Tesseract was not found. OCR will not work until tesseract-ocr is installed."
fi

if ! command -v 7z >/dev/null 2>&1; then
  warn "7z was not found. .7z code bundle uploads will be skipped until p7zip-full is installed."
fi

install_ollama_if_missing

info "Creating Python virtual environment"
if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

info "Installing Python dependencies"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r requirements.txt

info "Installing frontend dependencies"
npm --prefix frontend install

if [[ ! -f "$CONFIG_FILE" ]]; then
  info "Creating local config from example"
  cp "$EXAMPLE_CONFIG" "$CONFIG_FILE"
else
  info "Keeping existing $CONFIG_FILE"
fi

mkdir -p training data cache logs trainingdata

current_database_url="$(read_config_value DATABASE_URL)"
if [[ -n "${DATABASE_URL:-}" ]]; then
  current_database_url="$DATABASE_URL"
  write_config_value DATABASE_URL "$current_database_url"
fi

while [[ -z "$current_database_url" ]] || ! test_database_url "$current_database_url"; do
  if [[ -n "$current_database_url" ]]; then
    warn "Could not connect with the configured DATABASE_URL."
  fi
  show_postgres_help
  read -r -s -p "DATABASE_URL (input hidden): " current_database_url
  printf '\n'
  if [[ -z "$current_database_url" ]]; then
    fail "DATABASE_URL is required for DB-backed auth and settings."
  fi
  write_config_value DATABASE_URL "$current_database_url"
done

info "Applying database migrations"
"$VENV_DIR/bin/python" tools/db_migrate.py

if prompt_yes_no "Create or update an admin login user now?" "y"; then
  read -r -p "Admin username [admin]: " admin_username
  admin_username="${admin_username:-admin}"
  "$VENV_DIR/bin/python" tools/db_user.py upsert "$admin_username" --admin
fi

setup_ollama_helper_model

info "Building frontend"
npm --prefix frontend run build

info "Running backend smoke checks"
"$VENV_DIR/bin/python" -m py_compile circuitshelf.py datasheet_intelligence.py circuit_build_cards.py db/connection.py db/users.py db/sql.py db/datasheet_intelligence_store.py tools/db_migrate.py tools/db_user.py

cat <<'EOF'

Install complete.

Start CircuitShelf with:

  .venv/bin/python circuitshelf.py

Then open the URL printed by the server.

Put source PDFs, books, datasheets, and notes under training/ before indexing.
EOF

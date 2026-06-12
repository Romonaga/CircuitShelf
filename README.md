# CircuitShelf

Local electronics-focused RAG for querying datasheets, electronics books, OCR output, and project notes through Ollama-backed models.

## What This Repo Contains

- Python ingestion, OCR, chunking, indexing, reranking, and application server code.
- A React + TypeScript frontend under `frontend/`.
- A sanitized example config at `config/config.example.yaml`.
- Postgres/pgvector-backed text and image retrieval.
- Database-backed change detection for training files.
- Database migrations under `db/migrations/` and named SQL query files under `db/queries/`.
- Database setup and user-management tools under `tools/`.

## What This Repo Does Not Contain

The following are intentionally ignored because this is planned as a public repo:

- `training/` source books and datasheets
- `models/` downloaded model snapshots
- `data/` local logs or temporary operator output
- `logs/` and local runtime output
- `config/config.yaml` with local hosts, passwords, and database URLs

## Setup

### Linux

```bash
./install.sh
```

Install system prerequisites first. On Ubuntu/Debian:

```bash
sudo apt update
sudo apt install python3 python3-venv nodejs npm postgresql postgresql-client postgresql-16-pgvector tesseract-ocr p7zip-full
```

`p7zip-full` provides the `7z` command used to expand `.7z` electronics code bundles during upload.

Install Ollama from `https://ollama.com`, then run the guided installer:

```bash
./install.sh
```

### macOS

Install system prerequisites with Homebrew:

```bash
brew install python node postgresql@16 pgvector tesseract ollama
brew services start postgresql@16
```

Then run:

```bash
./install.sh
```

If `psql` is not in PATH after installing Postgres with Homebrew, add the Homebrew message's `postgresql@16/bin` path to your shell profile.

### Windows

Install these first:

- Python 3.12 or newer from `https://www.python.org`
- Node.js LTS from `https://nodejs.org`
- PostgreSQL from `https://www.postgresql.org/download/windows/`
- pgvector for your PostgreSQL version from `https://github.com/pgvector/pgvector`
- Tesseract OCR from `https://github.com/UB-Mannheim/tesseract/wiki`
- Ollama from `https://ollama.com`

Make sure `python`, `node`, `npm`, `psql`, and `tesseract` are available in PATH. Then open PowerShell in the repo folder and run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\install.ps1
```

The Windows installer creates `.venv`, installs dependencies, creates `config/config.yaml` if needed, records the discovered `tesseract.exe` path, prompts for `DATABASE_URL`, applies migrations, optionally creates an admin user, and builds the React frontend.

### Postgres Database

The installer expects a working Postgres `DATABASE_URL`. If you need to create the database first, run these commands as a Postgres admin.

Linux/macOS:

```bash
sudo -u postgres psql
```

Windows: open SQL Shell or pgAdmin as the `postgres` admin user.

Then run:

```sql
CREATE USER circuitshelf_app WITH PASSWORD 'choose-a-real-password';
CREATE DATABASE circuitshelf OWNER circuitshelf_app;
GRANT ALL PRIVILEGES ON DATABASE circuitshelf TO circuitshelf_app;
\c circuitshelf
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS vector;
```

Use this shape when the installer asks for `DATABASE_URL`:

```text
postgresql://circuitshelf_app:choose-a-real-password@localhost:5432/circuitshelf
```

### What The Installer Does

The guided installer:

- creates `.venv`
- installs Python dependencies
- installs frontend dependencies
- creates `config/config.yaml` from `config/config.example.yaml` if needed
- prompts for and verifies `DATABASE_URL`
- applies DB migrations
- optionally creates an admin login user
- builds the React frontend
- runs basic backend syntax checks

### AI Provider Key Encryption

OpenAI provider keys are encrypted in Postgres with `pgcrypto`. Store the master encryption secret in an OS-protected file such as `/etc/circuitshelf/ai-key-encryption.secret`; do not store it in committed config or in Postgres.

Key backup, restore, and encryption-secret rotation are documented in [docs/AI_KEY_OPERATIONS.md](docs/AI_KEY_OPERATIONS.md).

### Manual Setup

1. Create and activate a virtual environment.
2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Copy the example config:

```bash
cp config/config.example.yaml config/config.yaml
```

4. Install frontend dependencies:

```bash
cd frontend
npm install
```

5. Edit `config/config.yaml` for local models, hosts, database URL, and training paths.

## Running

For development, run the Python application server and the Vite frontend:

```bash
python circuitshelf.py
```

```bash
cd frontend
npm run dev
```

Vite proxies `/api/*` to the Python server at `http://127.0.0.1:1964`.

For a single-server local deployment, build the frontend and start Python:

```bash
cd frontend
npm run build
cd ..
python circuitshelf.py
```

The Python process serves the React build from `frontend/dist` and handles the UI's JSON endpoints.

CircuitShelf writes a PID lock file at `data/circuitshelf.pid` by default. That prevents accidentally starting two servers against the same local catalog and gives you a clean stop/status command:

```bash
python tools/server_process.py status
python tools/server_process.py stop
```

## Health Checks

The application exposes container-friendly probes:

- `GET /healthz` returns `200` when the process is alive.
- `GET /readyz` returns `200` only when the text index, chunks, embeddings, and model configuration are loaded; otherwise it returns `503`.

A future Docker health check can use:

```bash
curl -fsS http://127.0.0.1:1964/healthz
```

## Indexing

The indexer scans `TRAINING_DIR`, extracts text/OCR, chunks content, embeds text and accepted images, and stores the catalog in Postgres.

The `documents` table records training-file size, mtime, and optional hashes. Startup and the background watcher detect added, modified, and removed files from that catalog. Added and modified files are re-ingested incrementally; removed files are deleted from the catalog. Unchanged documents keep their existing rows and embeddings.

Admins can upload supported documents from the Documents page. Uploaded files are written to `TRAINING_DIR` and an incremental index check is started automatically.

New and changed documents are held in `needs_review` status. They are chunked and embedded so an admin can inspect them, but retrieval ignores them until they are approved from the Review page. Removing a document from Review deletes its catalog rows and the uploaded training file.

Relevant settings:

```yaml
INGEST_WATCH_ENABLED: true
INGEST_WATCH_INTERVAL_SECONDS: 300
```

## Database Migrations

Postgres is the canonical application store for users, settings, structured runtime configuration, ingest metadata, source catalog data, text embeddings, image embeddings, response-cache records, and query logs. YAML/bootstrap config is only used to start the app and seed empty runtime tables on a fresh install.

Structured runtime tables include LLM model choices, query synonyms, prompt-security banned phrases, rerank profiles, chunk categories, and equation-detection patterns. Startup loads those tables back into the runtime config before chunking, retrieval, and chat are initialized.

Schema changes are versioned as numbered SQL migrations in `db/migrations/` and tracked by the `schema_migrations` table. Once a migration has been applied in a shared database, add a new numbered migration instead of editing the old one.

Apply migrations with:

```bash
DATABASE_URL="postgresql://user:password@localhost:5432/circuitshelf" python tools/db_migrate.py
```

Application SQL queries live as named files in `db/queries/`; Python code loads those files instead of embedding SQL strings inline.

Create or update login users with:

```bash
python tools/db_user.py upsert hellweek --admin
```

List DB-backed users with:

```bash
python tools/db_user.py list
```

Do not commit real database credentials.

## Bench Assembly Plans

The `Bench` page turns retrieved electronics sources into persisted assembly plans. Each plan stores parts, power notes, pin-by-pin wiring steps, checks, warnings, source evidence, checklist progress, and a small bench-assistant conversation in Postgres.

Create a plan from the Bench page after indexing relevant books or datasheets. If no indexed sources support the build request, CircuitShelf returns a clear failure instead of inventing a plan.

## Tests

```bash
python -m unittest discover -s tests
cd frontend && npm run build
```

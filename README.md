# CircuitShelf

Local electronics-focused RAG for querying datasheets, electronics books, OCR output, and project notes through Ollama-backed models.

## What This Repo Contains

- Python ingestion, OCR, chunking, indexing, reranking, and application server code.
- A React + TypeScript frontend under `frontend/`.
- A sanitized example config at `config/config.example.yaml`.
- FAISS-based local vector indexing.
- Local manifest-based change detection for training files.
- Database migrations under `db/migrations/` and named SQL query files under `db/queries/`.
- Audit tools under `tools/`.

## What This Repo Does Not Contain

The following are intentionally ignored because this is planned as a public repo:

- `training/` source books and datasheets
- `models/` downloaded model snapshots
- `data/` generated FAISS indexes and pickle state
- `extracted_images/` OCR sidecars
- `logs/`, `cache/`, and local runtime output
- `config/config.yaml` with local hosts, passwords, and database URLs

## Setup

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

## Health Checks

The application exposes container-friendly probes:

- `GET /healthz` returns `200` when the process is alive.
- `GET /readyz` returns `200` only when the text index, chunks, embeddings, and model configuration are loaded; otherwise it returns `503`.

A future Docker health check can use:

```bash
curl -fsS http://127.0.0.1:1964/healthz
```

## Indexing

The indexer scans `TRAINING_DIR`, extracts text/OCR, chunks content, builds FAISS indexes, and saves generated state under `data/`.

The ingest manifest (`INGEST_MANIFEST_FILE`) records training-file size and mtime. After a baseline index exists, future runs can detect added, modified, and removed files, re-ingest only changed source documents, then rebuild FAISS from the cleaned chunk state.

## Database Migrations

Postgres is the canonical application store for users, settings, ingest metadata, source catalog data, and response-cache records. Generated FAISS/vector artifacts may still live on disk while indexing is being migrated.

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

## Tests

```bash
python -m unittest discover -s tests
cd frontend && npm run build
```

# CircuitShelf

Local electronics-focused RAG for querying datasheets, electronics books, OCR output, and project notes through Ollama-compatible models.

## What This Repo Contains

- Python ingestion, OCR, chunking, indexing, reranking, and UI/API code.
- A sanitized example config at `config/config.example.yaml`.
- FAISS-based local vector indexing.
- Local manifest-based change detection for training files.
- Database migration scaffolding under `db/migrations/`.
- Audit tools under `tools/`.

## What This Repo Does Not Contain

The following are intentionally ignored because this is planned as a public repo:

- `training/` source books and datasheets
- `models/` downloaded model snapshots
- `data/` generated FAISS indexes and pickle state
- `extracted_images/` OCR sidecars
- `logs/`, `cache/`, and local runtime output
- `config/config.yaml` with local hosts, users, passwords, and database URLs

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy the example config:

```bash
cp config/config.example.yaml config/config.yaml
```

4. Edit `config/config.yaml` for local models, hosts, users, and training paths.

## Indexing

The indexer scans `TRAINING_DIR`, extracts text/OCR, chunks content, builds FAISS indexes, and saves generated state under `data/`.

The ingest manifest (`INGEST_MANIFEST_FILE`) records training-file size and mtime. After a baseline index exists, future runs can detect added, modified, and removed files, re-ingest only changed source documents, then rebuild FAISS from the cleaned chunk state.

## Database Migrations

SQL migrations live in `db/migrations/` and are tracked by the `schema_migrations` table.

Apply migrations with:

```bash
DATABASE_URL="postgresql://user:password@localhost:5432/romollm" python tools/db_migrate.py
```

Do not commit real database credentials.

## Tests

```bash
python -m unittest discover -s tests
```

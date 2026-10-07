# Library Management API

FastAPI + PostgreSQL + SQLAlchemy 2.0 + pgvector.

## Features
- JWT auth (OAuth2 password flow) with `member` and `librarian` roles
- Books, authors, categories (librarians write, any signed-in member reads)
- Loans: checkout, return, overdue list, automatic fines, loan limits, row-level locking so the last copy can't be double-booked
- **pgvector search:** natural-language `GET /books/search/semantic` and `GET /books/{id}/similar`, backed by an HNSW cosine index

## Quick start (Docker)
```bash
cp .env.example .env            # set SECRET_KEY
docker compose up --build -d
docker compose exec api python -m scripts.seed
```
Open http://localhost:8000/docs. Seeded librarian: `librarian@example.com` / `ChangeMe123!` (change it).

## Quick start (local)
```bash
docker compose up -d db         # Postgres with the pgvector extension
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m scripts.seed
uvicorn app.main:app --reload
```

## Try it
```bash
# log in (email goes in the "username" field)
TOKEN=$(curl -s -X POST localhost:8000/auth/login \
  -d "username=librarian@example.com&password=ChangeMe123!" | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

curl -H "Authorization: Bearer $TOKEN" "localhost:8000/books/search/semantic?q=fantasy%20adventure%20with%20a%20dragon"
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"book_id": 1}' localhost:8000/loans
curl -X POST -H "Authorization: Bearer $TOKEN" localhost:8000/loans/1/return
```

## Endpoints
| Area | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Members | `GET /members` (L), `GET /members/{id}`, `PATCH /members/{id}` (L) |
| Authors | `POST/PATCH/DELETE /authors` (L), `GET /authors`, `GET /authors/{id}` |
| Categories | `POST/DELETE /categories` (L), `GET /categories` |
| Books | `POST/PATCH/DELETE /books` (L), `GET /books`, `GET /books/{id}`, `GET /books/search/semantic`, `GET /books/{id}/similar` |
| Loans | `POST /loans`, `POST /loans/{id}/return`, `GET /loans`, `GET /loans/{id}`, `GET /loans/overdue` (L) |

(L) = librarian only.

## Embeddings
`EMBEDDING_PROVIDER=hash` (default) works with zero extra dependencies but only matches on word overlap.
For real semantic search:
```bash
pip install sentence-transformers
# .env
EMBEDDING_PROVIDER=sentence-transformers
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIM=384
python -m scripts.reindex_embeddings
```
If you change `EMBEDDING_DIM` on an existing database, the `books.embedding` column must be recreated.

## Business rules (configurable in `.env`)
`LOAN_PERIOD_DAYS=14`, `MAX_ACTIVE_LOANS=5`, `FINE_PER_DAY=0.50`. Members with an overdue loan cannot borrow until they return it.

## Tests
```bash
pytest
```
Current tests cover embeddings, password/JWT handling and fine calculation (no database needed).

## Production notes
- Replace `create_all` in `app/main.py` with Alembic migrations.
- Set a long random `SECRET_KEY`, and restrict CORS/hosts as needed.
- Add rate limiting on `/auth/login`.

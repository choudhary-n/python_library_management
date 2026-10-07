from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app import models  # noqa: F401  (register tables on Base.metadata)
from app.database import Base, engine
from app.routers import auth, authors, books, categories, loans, members


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Dev convenience. For production, manage the schema with Alembic migrations instead.
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="Library Management API",
    version="1.0.0",
    description="Books, authors, members and loans with pgvector-powered semantic search.",
    lifespan=lifespan,
)

for router in (auth.router, members.router, authors.router, categories.router, books.router, loans.router):
    app.include_router(router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}

"""Recompute every book embedding (run after changing the embedding provider/model).

    python -m scripts.reindex_embeddings
"""
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import SessionLocal
from app.models import Book
from app.services.embeddings import book_text, embed_text


def main() -> None:
    with SessionLocal() as db:
        books = db.scalars(select(Book).options(selectinload(Book.authors))).all()
        for book in books:
            book.embedding = embed_text(book_text(book.title, [a.name for a in book.authors], book.description))
        db.commit()
    print(f"Re-embedded {len(books)} books.")


if __name__ == "__main__":
    main()

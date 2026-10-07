"""Create a librarian account and a few sample books.

    python -m scripts.seed
"""
import os

from sqlalchemy import select, text

from app.database import Base, SessionLocal, engine
from app.models import Author, Book, Category, Member, Role
from app.security import hash_password
from app.services.embeddings import book_text, embed_text

ADMIN_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "librarian@example.com")
ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "ChangeMe123!")

SAMPLE_BOOKS = [
    ("9780132350884", "Clean Code", "Robert C. Martin", "Technology", 2008,
     "A handbook of agile software craftsmanship: writing readable, maintainable code."),
    ("9780201633610", "Design Patterns", "Erich Gamma", "Technology", 1994,
     "Elements of reusable object-oriented software and classic design patterns."),
    ("9781491950296", "Building Microservices", "Sam Newman", "Technology", 2015,
     "Designing fine-grained systems: service boundaries, deployment and distributed architecture."),
    ("9780441172719", "Dune", "Frank Herbert", "Fiction", 1965,
     "A desert planet, political intrigue, prophecy and ecology in a far-future empire."),
    ("9780547928227", "The Hobbit", "J.R.R. Tolkien", "Fiction", 1937,
     "A hobbit joins dwarves and a wizard on a quest to reclaim treasure guarded by a dragon."),
]


def main() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)

    with SessionLocal() as db:
        if not db.scalar(select(Member).where(Member.email == ADMIN_EMAIL)):
            db.add(Member(full_name="Head Librarian", email=ADMIN_EMAIL,
                          hashed_password=hash_password(ADMIN_PASSWORD), role=Role.librarian))
            print(f"Created librarian {ADMIN_EMAIL}")

        for isbn, title, author_name, category_name, year, description in SAMPLE_BOOKS:
            if db.scalar(select(Book).where(Book.isbn == isbn)):
                continue
            author = db.scalar(select(Author).where(Author.name == author_name)) or Author(name=author_name)
            category = db.scalar(select(Category).where(Category.name == category_name)) or Category(name=category_name)
            db.add_all([author, category])
            db.flush()
            db.add(Book(isbn=isbn, title=title, description=description, published_year=year,
                        category_id=category.id, total_copies=3, available_copies=3, authors=[author],
                        embedding=embed_text(book_text(title, [author_name], description))))
        db.commit()
    print("Seed complete.")


if __name__ == "__main__":
    main()

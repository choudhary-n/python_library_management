from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.deps import DB, CurrentMember, Librarian
from app.models import Author, Book, Category, Loan
from app.schemas import BookCreate, BookOut, BookUpdate, SemanticHit
from app.services.embeddings import book_text, embed_text

router = APIRouter(prefix="/books", tags=["books"])


def _load_authors(db: Session, author_ids: list[int]) -> list[Author]:
    ids = list(dict.fromkeys(author_ids))
    if not ids:
        return []
    authors = db.scalars(select(Author).where(Author.id.in_(ids))).all()
    missing = set(ids) - {a.id for a in authors}
    if missing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown author ids: {sorted(missing)}")
    return list(authors)


def _check_category(db: Session, category_id: int | None) -> None:
    if category_id is not None and db.get(Category, category_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown category id: {category_id}")


def _refresh_embedding(book: Book) -> None:
    book.embedding = embed_text(book_text(book.title, [a.name for a in book.authors], book.description))


def _get_book_or_404(db: Session, book_id: int) -> Book:
    book = db.scalar(select(Book).where(Book.id == book_id).options(selectinload(Book.authors)))
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")
    return book


@router.post("", response_model=BookOut, status_code=status.HTTP_201_CREATED)
def create_book(payload: BookCreate, db: DB, _: Librarian):
    if db.scalar(select(Book.id).where(Book.isbn == payload.isbn)):
        raise HTTPException(status.HTTP_409_CONFLICT, "ISBN already exists")
    _check_category(db, payload.category_id)
    book = Book(
        isbn=payload.isbn,
        title=payload.title,
        description=payload.description,
        published_year=payload.published_year,
        category_id=payload.category_id,
        total_copies=payload.total_copies,
        available_copies=payload.total_copies,
        authors=_load_authors(db, payload.author_ids),
    )
    _refresh_embedding(book)
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


@router.get("", response_model=list[BookOut])
def list_books(
    db: DB,
    _: CurrentMember,
    q: str | None = Query(None, description="Title substring (case-insensitive)"),
    author_id: int | None = None,
    category_id: int | None = None,
    available_only: bool = False,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    stmt = select(Book).options(selectinload(Book.authors)).order_by(Book.title)
    if q:
        stmt = stmt.where(Book.title.ilike(f"%{q}%"))
    if author_id is not None:
        stmt = stmt.where(Book.authors.any(Author.id == author_id))
    if category_id is not None:
        stmt = stmt.where(Book.category_id == category_id)
    if available_only:
        stmt = stmt.where(Book.available_copies > 0)
    return db.scalars(stmt.limit(limit).offset(offset)).all()


# NOTE: static paths must be declared before "/{book_id}".
@router.get("/search/semantic", response_model=list[SemanticHit])
def semantic_search(
    db: DB,
    _: CurrentMember,
    q: str = Query(..., min_length=2, description="Natural-language query"),
    limit: int = Query(10, ge=1, le=50),
    available_only: bool = False,
):
    distance = Book.embedding.cosine_distance(embed_text(q))
    stmt = (
        select(Book, distance.label("distance"))
        .where(Book.embedding.is_not(None))
        .options(selectinload(Book.authors))
        .order_by(distance)
        .limit(limit)
    )
    if available_only:
        stmt = stmt.where(Book.available_copies > 0)
    return [SemanticHit(book=book, similarity=round(1.0 - dist, 4)) for book, dist in db.execute(stmt).all()]


@router.get("/{book_id}", response_model=BookOut)
def get_book(book_id: int, db: DB, _: CurrentMember):
    return _get_book_or_404(db, book_id)


@router.get("/{book_id}/similar", response_model=list[SemanticHit])
def similar_books(book_id: int, db: DB, _: CurrentMember, limit: int = Query(5, ge=1, le=20)):
    book = _get_book_or_404(db, book_id)
    if book.embedding is None:
        return []
    distance = Book.embedding.cosine_distance(book.embedding)
    stmt = (
        select(Book, distance.label("distance"))
        .where(Book.id != book.id, Book.embedding.is_not(None))
        .options(selectinload(Book.authors))
        .order_by(distance)
        .limit(limit)
    )
    return [SemanticHit(book=b, similarity=round(1.0 - d, 4)) for b, d in db.execute(stmt).all()]


@router.patch("/{book_id}", response_model=BookOut)
def update_book(book_id: int, payload: BookUpdate, db: DB, _: Librarian):
    book = db.scalar(
        select(Book).where(Book.id == book_id).options(selectinload(Book.authors)).with_for_update()
    )
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")

    data = payload.model_dump(exclude_unset=True)
    if "category_id" in data:
        _check_category(db, data["category_id"])
    if "author_ids" in data and data["author_ids"] is not None:
        book.authors = _load_authors(db, data.pop("author_ids"))
    else:
        data.pop("author_ids", None)

    new_total = data.pop("total_copies", None)
    if new_total is not None:
        on_loan = book.total_copies - book.available_copies
        if new_total < on_loan:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"{on_loan} copies are on loan; total_copies cannot be below that"
            )
        book.total_copies = new_total
        book.available_copies = new_total - on_loan

    for field, value in data.items():
        setattr(book, field, value)

    _refresh_embedding(book)
    db.commit()
    db.refresh(book)
    return book


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: int, db: DB, _: Librarian):
    book = db.get(Book, book_id)
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")
    has_active = db.scalar(select(func.count()).select_from(Loan).where(Loan.book_id == book_id, Loan.returned_at.is_(None)))
    if has_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Book has active loans")
    has_history = db.scalar(select(func.count()).select_from(Loan).where(Loan.book_id == book_id))
    if has_history:
        raise HTTPException(status.HTTP_409_CONFLICT, "Book has loan history and cannot be deleted")
    db.delete(book)
    db.commit()

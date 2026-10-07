from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.deps import DB, CurrentMember, Librarian
from app.models import Author
from app.schemas import AuthorCreate, AuthorOut, AuthorUpdate

router = APIRouter(prefix="/authors", tags=["authors"])


@router.post("", response_model=AuthorOut, status_code=status.HTTP_201_CREATED)
def create_author(payload: AuthorCreate, db: DB, _: Librarian):
    author = Author(**payload.model_dump())
    db.add(author)
    db.commit()
    db.refresh(author)
    return author


@router.get("", response_model=list[AuthorOut])
def list_authors(
    db: DB,
    _: CurrentMember,
    q: str | None = Query(None, description="Case-insensitive name search"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(Author).order_by(Author.name)
    if q:
        stmt = stmt.where(Author.name.ilike(f"%{q}%"))
    return db.scalars(stmt.limit(limit).offset(offset)).all()


@router.get("/{author_id}", response_model=AuthorOut)
def get_author(author_id: int, db: DB, _: CurrentMember):
    author = db.get(Author, author_id)
    if author is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Author not found")
    return author


@router.patch("/{author_id}", response_model=AuthorOut)
def update_author(author_id: int, payload: AuthorUpdate, db: DB, _: Librarian):
    author = db.get(Author, author_id)
    if author is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Author not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(author, field, value)
    db.commit()
    db.refresh(author)
    return author


@router.delete("/{author_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_author(author_id: int, db: DB, _: Librarian):
    author = db.get(Author, author_id)
    if author is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Author not found")
    db.delete(author)
    db.commit()

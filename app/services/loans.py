from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Book, Loan, Member


def _now() -> datetime:
    return datetime.now(timezone.utc)


def calculate_fine(due_at: datetime, returned_at: datetime) -> Decimal:
    late_days = max(0, (returned_at - due_at).days)
    return (settings.fine_per_day * late_days).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def checkout_book(db: Session, member: Member, book_id: int) -> Loan:
    # Lock the book row so concurrent checkouts can't oversell the last copy.
    book = db.execute(select(Book).where(Book.id == book_id).with_for_update()).scalar_one_or_none()
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Book not found")
    if not member.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Member account is inactive")
    if book.available_copies < 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "No copies available")

    now = _now()
    active = db.scalar(
        select(func.count()).select_from(Loan).where(Loan.member_id == member.id, Loan.returned_at.is_(None))
    )
    if active >= settings.max_active_loans:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Loan limit reached ({settings.max_active_loans} active loans)"
        )
    overdue = db.scalar(
        select(func.count())
        .select_from(Loan)
        .where(Loan.member_id == member.id, Loan.returned_at.is_(None), Loan.due_at < now)
    )
    if overdue:
        raise HTTPException(status.HTTP_409_CONFLICT, "Return overdue books before borrowing more")

    loan = Loan(
        book_id=book.id,
        member_id=member.id,
        loaned_at=now,
        due_at=now + timedelta(days=settings.loan_period_days),
    )
    book.available_copies -= 1
    db.add(loan)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Member already has this book on loan")
    db.refresh(loan)
    return loan


def return_book(db: Session, loan_id: int) -> Loan:
    loan = db.execute(select(Loan).where(Loan.id == loan_id).with_for_update()).scalar_one_or_none()
    if loan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Loan not found")
    if loan.returned_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Loan already returned")

    book = db.execute(select(Book).where(Book.id == loan.book_id).with_for_update()).scalar_one()
    now = _now()
    loan.returned_at = now
    loan.fine_amount = calculate_fine(loan.due_at, now)
    book.available_copies += 1
    db.commit()
    db.refresh(loan)
    return loan

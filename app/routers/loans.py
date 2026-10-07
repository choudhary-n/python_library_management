from datetime import datetime, timezone
from enum import Enum

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.deps import DB, CurrentMember, Librarian
from app.models import Loan, Member, Role
from app.schemas import LoanCreate, LoanOut
from app.services.loans import checkout_book, return_book

router = APIRouter(prefix="/loans", tags=["loans"])


class LoanStatus(str, Enum):
    active = "active"
    returned = "returned"
    overdue = "overdue"


@router.post("", response_model=LoanOut, status_code=status.HTTP_201_CREATED)
def checkout(payload: LoanCreate, db: DB, caller: CurrentMember):
    """Members borrow for themselves; librarians can check out on behalf of any member."""
    target = caller
    if payload.member_id is not None and payload.member_id != caller.id:
        if caller.role != Role.librarian:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Only librarians can borrow for other members")
        target = db.get(Member, payload.member_id)
        if target is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    return checkout_book(db, target, payload.book_id)


@router.post("/{loan_id}/return", response_model=LoanOut)
def return_loan(loan_id: int, db: DB, caller: CurrentMember):
    loan = db.get(Loan, loan_id)
    if loan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Loan not found")
    if loan.member_id != caller.id and caller.role != Role.librarian:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
    return return_book(db, loan_id)


@router.get("/overdue", response_model=list[LoanOut])
def overdue_loans(db: DB, _: Librarian, limit: int = Query(100, ge=1, le=500)):
    now = datetime.now(timezone.utc)
    stmt = select(Loan).where(Loan.returned_at.is_(None), Loan.due_at < now).order_by(Loan.due_at).limit(limit)
    return db.scalars(stmt).all()


@router.get("", response_model=list[LoanOut])
def list_loans(
    db: DB,
    caller: CurrentMember,
    member_id: int | None = Query(None, description="Librarians only; members always see their own"),
    status_filter: LoanStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    stmt = select(Loan).order_by(Loan.loaned_at.desc())
    if caller.role == Role.librarian:
        if member_id is not None:
            stmt = stmt.where(Loan.member_id == member_id)
    else:
        stmt = stmt.where(Loan.member_id == caller.id)

    now = datetime.now(timezone.utc)
    if status_filter == LoanStatus.active:
        stmt = stmt.where(Loan.returned_at.is_(None))
    elif status_filter == LoanStatus.returned:
        stmt = stmt.where(Loan.returned_at.is_not(None))
    elif status_filter == LoanStatus.overdue:
        stmt = stmt.where(Loan.returned_at.is_(None), Loan.due_at < now)
    return db.scalars(stmt.limit(limit).offset(offset)).all()


@router.get("/{loan_id}", response_model=LoanOut)
def get_loan(loan_id: int, db: DB, caller: CurrentMember):
    loan = db.get(Loan, loan_id)
    if loan is None or (loan.member_id != caller.id and caller.role != Role.librarian):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Loan not found")
    return loan

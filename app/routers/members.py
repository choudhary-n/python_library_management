from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.deps import DB, CurrentMember, Librarian
from app.models import Member, Role
from app.schemas import MemberOut, MemberUpdate

router = APIRouter(prefix="/members", tags=["members"])


@router.get("", response_model=list[MemberOut])
def list_members(
    db: DB,
    _: Librarian,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return db.scalars(select(Member).order_by(Member.id).limit(limit).offset(offset)).all()


@router.get("/{member_id}", response_model=MemberOut)
def get_member(member_id: int, db: DB, caller: CurrentMember):
    if caller.id != member_id and caller.role != Role.librarian:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
    member = db.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    return member


@router.patch("/{member_id}", response_model=MemberOut)
def update_member(member_id: int, payload: MemberUpdate, db: DB, caller: Librarian):
    member = db.get(Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    if member.id == caller.id and (payload.role == Role.member or payload.is_active is False):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot demote or deactivate yourself")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(member, field, value)
    db.commit()
    db.refresh(member)
    return member

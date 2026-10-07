from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.deps import DB, CurrentMember
from app.models import Member, Role
from app.schemas import MemberCreate, MemberOut, Token
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def register(payload: MemberCreate, db: DB):
    """Self-registration always creates a regular member. Librarians are promoted by other librarians."""
    email = payload.email.lower()
    if db.scalar(select(Member).where(Member.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    member = Member(
        full_name=payload.full_name,
        email=email,
        hashed_password=hash_password(payload.password),
        role=Role.member,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.post("/login", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DB):
    """OAuth2 password flow: send the email in the `username` field."""
    member = db.scalar(select(Member).where(Member.email == form.username.lower()))
    if member is None or not member.is_active or not verify_password(form.password, member.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    return Token(access_token=create_access_token(str(member.id)))


@router.get("/me", response_model=MemberOut)
def me(member: CurrentMember):
    return member

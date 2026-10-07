from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Member, Role
from app.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

DB = Annotated[Session, Depends(get_db)]


def get_current_member(db: DB, token: Annotated[str, Depends(oauth2_scheme)]) -> Member:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    subject = decode_access_token(token)
    if subject is None or not subject.isdigit():
        raise credentials_error
    member = db.get(Member, int(subject))
    if member is None or not member.is_active:
        raise credentials_error
    return member


CurrentMember = Annotated[Member, Depends(get_current_member)]


def require_librarian(member: CurrentMember) -> Member:
    if member.role != Role.librarian:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Librarian access required")
    return member


Librarian = Annotated[Member, Depends(require_librarian)]

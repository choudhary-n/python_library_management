from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import Role


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- auth / members ----------
class MemberCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=64)


class MemberUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class MemberOut(ORMModel):
    id: int
    full_name: str
    email: EmailStr
    role: Role
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- authors / categories ----------
class AuthorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    bio: str | None = None


class AuthorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    bio: str | None = None


class AuthorOut(ORMModel):
    id: int
    name: str
    bio: str | None = None


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class CategoryOut(ORMModel):
    id: int
    name: str


# ---------- books ----------
class BookCreate(BaseModel):
    isbn: str = Field(min_length=10, max_length=20)
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    published_year: int | None = Field(default=None, ge=0, le=2100)
    category_id: int | None = None
    total_copies: int = Field(default=1, ge=1)
    author_ids: list[int] = []


class BookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = None
    published_year: int | None = Field(default=None, ge=0, le=2100)
    category_id: int | None = None
    total_copies: int | None = Field(default=None, ge=1)
    author_ids: list[int] | None = None


class BookOut(ORMModel):
    id: int
    isbn: str
    title: str
    description: str | None = None
    published_year: int | None = None
    category_id: int | None = None
    total_copies: int
    available_copies: int
    authors: list[AuthorOut] = []
    created_at: datetime


class SemanticHit(BaseModel):
    book: BookOut
    similarity: float = Field(description="Cosine similarity, 1.0 = identical")


# ---------- loans ----------
class LoanCreate(BaseModel):
    book_id: int
    member_id: int | None = Field(
        default=None, description="Librarians may check out on behalf of a member; defaults to caller."
    )


class LoanOut(ORMModel):
    id: int
    book_id: int
    member_id: int
    loaned_at: datetime
    due_at: datetime
    returned_at: datetime | None = None
    fine_amount: Decimal

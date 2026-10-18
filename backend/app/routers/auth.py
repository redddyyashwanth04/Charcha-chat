from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AuthError, ConflictError
from app.models import User
from app.ratelimit import limiter
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.security import create_access_token, current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise ConflictError("An account with this email already exists")
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    limiter.check(hash(email))  # slows down password guessing per email
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None or not verify_password(body.password, user.password_hash):
        raise AuthError("Incorrect email or password")
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user

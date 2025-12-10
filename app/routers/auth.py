import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import UserCreate, UserLogin, UserOut

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/auth/register", response_model=UserOut)
def register(user: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "email_exists", "message": "该邮箱已注册，请直接登录"},
        )
    if len(user.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "password_too_short", "message": "密码至少 6 位"},
        )
    password_plain = user.password
    display_name = user.display_name or user.email.split("@")[0]
    new_user = User(
        email=user.email,
        password_hash=password_plain,
        display_name=display_name,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info("用户注册成功 email=%s id=%s", new_user.email, new_user.id)
    return new_user


@router.post("/auth/login", response_model=UserOut)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or user.password_hash != payload.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_credentials", "message": "账号或密码错误"},
        )
    logger.info("用户登录成功 email=%s id=%s", user.email, user.id)
    return user


def _get_current_user(
    x_user_email: str | None = Header(default=None, alias="X-User-Email"),
    x_user_password: str | None = Header(default=None, alias="X-User-Password"),
    db: Session = Depends(get_db),
) -> User:
    if not x_user_email or not x_user_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "缺少认证信息"},
        )
    user = db.query(User).filter(User.email == x_user_email).first()
    if not user or user.password_hash != x_user_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "账号或密码错误"},
        )
    return user


def _get_current_user_optional(
    x_user_email: str | None = Header(default=None, alias="X-User-Email"),
    x_user_password: str | None = Header(default=None, alias="X-User-Password"),
    db: Session = Depends(get_db),
) -> User | None:
    if not x_user_email or not x_user_password:
        return None
    try:
        return _get_current_user(
            x_user_email=x_user_email, x_user_password=x_user_password, db=db
        )
    except HTTPException:
        return None


@router.get("/auth/me", response_model=UserOut)
def me(current_user: User = Depends(_get_current_user)):
    return current_user

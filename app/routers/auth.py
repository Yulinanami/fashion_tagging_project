import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas import AuthResponse, RefreshRequest, UserCreate, UserLogin, UserOut
from app.security import create_tokens, verify_access_token

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/auth/register", response_model=AuthResponse)
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
    token, expires_at, refresh_token, refresh_expires_at = create_tokens(user.email)
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
    return AuthResponse(
        id=new_user.id,
        email=new_user.email,
        display_name=new_user.display_name,
        token=token,
        expires_at=expires_at,
        refresh_token=refresh_token,
        refresh_expires_at=refresh_expires_at,
    )


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or user.password_hash != payload.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_credentials", "message": "账号或密码错误"},
        )
    token, expires_at, refresh_token, refresh_expires_at = create_tokens(user.email)
    logger.info("用户登录成功 email=%s id=%s", user.email, user.id)
    return AuthResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        token=token,
        expires_at=expires_at,
        refresh_token=refresh_token,
        refresh_expires_at=refresh_expires_at,
    )


def _get_current_user(
    authorization: str = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "缺少认证信息"},
        )
    token = authorization.split(" ", 1)[1]
    email = verify_access_token(token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "登录状态无效或已过期"},
        )
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "登录状态无效或已过期"},
        )
    return user


@router.get("/auth/me", response_model=UserOut)
def me(current_user: User = Depends(_get_current_user)):
    return current_user


@router.post("/auth/refresh", response_model=AuthResponse)
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    email = verify_access_token(payload.refresh_token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_refresh", "message": "刷新令牌无效或已过期"},
        )
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_refresh", "message": "刷新令牌无效或已过期"},
        )
    token, expires_at, refresh_token, refresh_expires_at = create_tokens(user.email)
    logger.info("刷新 token 成功 email=%s id=%s", user.email, user.id)
    return AuthResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        token=token,
        expires_at=expires_at,
        refresh_token=refresh_token,
        refresh_expires_at=refresh_expires_at,
    )

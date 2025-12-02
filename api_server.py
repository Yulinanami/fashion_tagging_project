from datetime import datetime, timedelta
import logging
from pathlib import Path
import shutil
import tempfile

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from db import get_db, init_db
from models import User
from renaming import build_new_name
from schemas import AuthResponse, RefreshRequest, UserCreate, UserLogin, UserOut
from security import create_token, hash_password, verify_password
from tagging import tag_image

app = FastAPI(title="Fashion Tagging API")
logger = logging.getLogger("fashion_tagging")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# 允许 Android 调用（本地/局域网都放开）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/auth/register", response_model=AuthResponse)
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
    password_hash = hash_password(user.password)
    token, refresh_token, expires_at, refresh_expires_at = _issue_tokens()
    display_name = user.display_name or user.email.split("@")[0]
    new_user = User(
        email=user.email,
        password_hash=password_hash,
        display_name=display_name,
        token=token,
        token_expires_at=expires_at,
        refresh_token=refresh_token,
        refresh_expires_at=refresh_expires_at,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    logger.info("用户注册成功 email=%s id=%s", new_user.email, new_user.id)
    return AuthResponse(
        id=new_user.id,
        email=new_user.email,
        display_name=new_user.display_name,
        token=new_user.token,
        expires_at=new_user.token_expires_at,
        refresh_token=new_user.refresh_token,
        refresh_expires_at=new_user.refresh_expires_at,
    )


@app.post("/auth/login", response_model=AuthResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_credentials", "message": "账号或密码错误"},
        )
    (
        user.token,
        user.refresh_token,
        user.token_expires_at,
        user.refresh_expires_at,
    ) = _issue_tokens()
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("用户登录成功 email=%s id=%s", user.email, user.id)
    return AuthResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        token=user.token,
        expires_at=user.token_expires_at,
        refresh_token=user.refresh_token,
        refresh_expires_at=user.refresh_expires_at,
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
    user = db.query(User).filter(User.token == token).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": "登录状态无效或已过期"},
        )
    if user.token_expires_at and user.token_expires_at <= datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "token_expired", "message": "登录状态已过期，请重新登录"},
        )
    return user


@app.get("/auth/me", response_model=UserOut)
def me(current_user: User = Depends(_get_current_user)):
    return current_user


@app.post("/auth/refresh", response_model=AuthResponse)
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    user = (
        db.query(User)
        .filter(User.refresh_token == payload.refresh_token)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_refresh", "message": "刷新令牌无效"},
        )
    if user.refresh_expires_at and user.refresh_expires_at <= datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "refresh_expired", "message": "刷新令牌已过期，请重新登录"},
        )
    (
        user.token,
        user.refresh_token,
        user.token_expires_at,
        user.refresh_expires_at,
    ) = _issue_tokens()
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("刷新 token 成功 email=%s id=%s", user.email, user.id)
    return AuthResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        token=user.token,
        expires_at=user.token_expires_at,
        refresh_token=user.refresh_token,
        refresh_expires_at=user.refresh_expires_at,
    )


def _issue_tokens():
    now = datetime.utcnow()
    access_token = create_token()
    refresh_token = create_token()
    return (
        access_token,
        refresh_token,
        now + timedelta(hours=1),
        now + timedelta(days=7),
    )


@app.post("/tag-image")
async def tag_image_api(file: UploadFile = File(...)):
    """
    接收一张图片，返回时尚标签 JSON
    """
    # 把上传文件存到临时文件
    suffix = Path(file.filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        tags = tag_image(tmp_path)  # 直接复用你原来的打标签逻辑
        return {"filename": file.filename, "tags": tags}
    finally:
        # 用完删掉临时文件
        tmp_path.unlink(missing_ok=True)


@app.post("/tag-and-suggest-name")
async def tag_and_suggest_name_api(file: UploadFile = File(...)):
    """
    接收图片，返回：标签 + 推荐文件名（不真正重命名，只是给前端参考）
    """
    suffix = Path(file.filename).suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        tags = tag_image(tmp_path)
        # 这里只拿 index=1 构造一个名字给前端看
        suggested_name = build_new_name(tags, index=1, ext=suffix.lower())
        return {
            "original_filename": file.filename,
            "suggested_name": suggested_name,
            "tags": tags,
        }
    finally:
        tmp_path.unlink(missing_ok=True)

from pathlib import Path
import shutil
import tempfile

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from db import get_db, init_db
from models import User
from renaming import build_new_name
from schemas import AuthResponse, UserCreate, UserLogin, UserOut
from security import create_token, hash_password, verify_password
from tagging import tag_image

app = FastAPI(title="Fashion Tagging API")

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
            detail="该邮箱已注册，请直接登录",
        )
    if len(user.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码至少 6 位",
        )
    password_hash = hash_password(user.password)
    token = create_token()
    display_name = user.display_name or user.email.split("@")[0]
    new_user = User(
        email=user.email,
        password_hash=password_hash,
        display_name=display_name,
        token=token,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return AuthResponse(
        id=new_user.id,
        email=new_user.email,
        display_name=new_user.display_name,
        token=new_user.token,
    )


@app.post("/auth/login", response_model=AuthResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="账号或密码错误",
        )
    user.token = create_token()
    db.add(user)
    db.commit()
    db.refresh(user)
    return AuthResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        token=user.token,
    )


def _get_current_user(
    authorization: str = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少认证信息",
        )
    token = authorization.split(" ", 1)[1]
    user = db.query(User).filter(User.token == token).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录状态无效或已过期",
        )
    return user


@app.get("/auth/me", response_model=UserOut)
def me(current_user: User = Depends(_get_current_user)):
    return current_user


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

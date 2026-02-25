"""认证 API：注册、登录、用户信息"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.plugin import StoreUser
from ...core.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    get_current_user,
)

router = APIRouter()


# ==================== 请求/响应模型 ====================

class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str


class LoginRequest(BaseModel):
    account: str     ## 邮箱或用户名
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class UpdateProfileRequest(BaseModel):
    username: str | None = None
    avatar: str | None = None


# ==================== 注册 ====================

@router.post("/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    ## 检查邮箱/用户名是否已存在
    result = await db.execute(
        select(StoreUser).where(
            or_(StoreUser.email == req.email, StoreUser.username == req.username)
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        if existing.email == req.email:
            raise HTTPException(status_code=400, detail="该邮箱已注册")
        raise HTTPException(status_code=400, detail="该用户名已被使用")

    ## 密码长度检查
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少6位")

    ## 创建用户
    user = StoreUser(
        email=req.email,
        username=req.username,
        password_hash=hash_password(req.password),
        role="user",
        status=1,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()  ## 获取 user.id

    ## 生成 token
    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_user_dict(user),
    )


# ==================== 登录 ====================

@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """登录（支持邮箱或用户名）"""
    result = await db.execute(
        select(StoreUser).where(
            or_(StoreUser.email == req.account, StoreUser.username == req.account)
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="账号或密码错误")

    if user.status == 0:
        raise HTTPException(status_code=403, detail="账号已被禁用")

    ## 更新最后登录时间
    user.last_login_at = datetime.now(timezone.utc)

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_user_dict(user),
    )


# ==================== 当前用户信息 ====================

@router.get("/me")
async def get_me(user: StoreUser = Depends(get_current_user)):
    """获取当前用户信息"""
    return _user_dict(user)


@router.put("/me")
async def update_me(
    req: UpdateProfileRequest,
    user: StoreUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改个人信息"""
    if req.username and req.username != user.username:
        ## 检查用户名是否已被使用
        result = await db.execute(
            select(StoreUser).where(StoreUser.username == req.username)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="该用户名已被使用")
        user.username = req.username

    if req.avatar is not None:
        user.avatar = req.avatar

    return {"message": "更新成功", "user": _user_dict(user)}


# ==================== 刷新 token ====================

class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/refresh")
async def refresh_token(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """刷新 access token"""
    payload = decode_token(req.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="无效的 refresh token")

    user_id = int(payload["sub"])
    result = await db.execute(select(StoreUser).where(StoreUser.id == user_id))
    user = result.scalar_one_or_none()
    if not user or user.status == 0:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")

    new_access = create_access_token(user.id, user.role)
    return {"access_token": new_access, "token_type": "bearer"}


# ==================== 辅助函数 ====================

def _user_dict(user: StoreUser) -> dict:
    """用户信息字典"""
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "avatar": user.avatar,
        "role": user.role,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }

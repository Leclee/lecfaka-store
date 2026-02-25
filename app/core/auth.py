"""
认证工具：JWT + 密码哈希
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models.plugin import StoreUser

## 密码哈希
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

## JWT Bearer
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """哈希密码"""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: int, role: str, expires_delta: Optional[timedelta] = None) -> str:
    """创建 JWT access token"""
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes))
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int) -> str:
    """创建 JWT refresh token"""
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """解码 JWT"""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效或过期的 token")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> StoreUser:
    """从 JWT 获取当前用户（必须登录）"""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 token 类型")

    user_id = int(payload["sub"])
    result = await db.execute(select(StoreUser).where(StoreUser.id == user_id))
    user = result.scalar_one_or_none()

    if not user or user.status == 0:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")

    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[StoreUser]:
    """可选的用户身份（游客可访问但登录用户有额外信息）"""
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
        user_id = int(payload["sub"])
        result = await db.execute(select(StoreUser).where(StoreUser.id == user_id))
        return result.scalar_one_or_none()
    except Exception:
        return None


def require_role(user: StoreUser, allowed_roles: list[str]):
    """角色检查（同步函数，不需要 await）"""
    if user.role not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")

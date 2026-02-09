"""授权验证 API"""

from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.plugin import License

router = APIRouter()


class VerifyRequest(BaseModel):
    plugin_id: str
    license_key: str
    domain: str


class BindRequest(BaseModel):
    license_key: str
    domain: str


@router.post("/verify")
async def verify_license(req: VerifyRequest, db: AsyncSession = Depends(get_db)):
    """验证授权码"""
    result = await db.execute(
        select(License).where(
            License.license_key == req.license_key,
            License.plugin_id == req.plugin_id,
        )
    )
    lic = result.scalar_one_or_none()

    if not lic:
        return {"valid": False, "message": "授权码无效"}

    if lic.status == 0:
        return {"valid": False, "message": "授权码已禁用"}

    if lic.status == 2:
        return {"valid": False, "message": "授权码已过期"}

    if lic.expires_at and lic.expires_at < datetime.utcnow():
        lic.status = 2
        return {"valid": False, "message": "授权码已过期"}

    # 域名检查
    if lic.domain and lic.domain != req.domain:
        return {"valid": False, "message": f"授权码已绑定到 {lic.domain}"}

    # 首次绑定域名
    if not lic.domain:
        lic.domain = req.domain
        lic.activated_at = datetime.utcnow()

    return {
        "valid": True,
        "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
        "domain": lic.domain,
        "message": "授权有效",
    }


@router.post("/bind")
async def bind_domain(req: BindRequest, db: AsyncSession = Depends(get_db)):
    """绑定域名"""
    result = await db.execute(
        select(License).where(License.license_key == req.license_key)
    )
    lic = result.scalar_one_or_none()

    if not lic:
        return {"success": False, "message": "授权码无效"}

    if lic.domain and lic.domain != req.domain:
        return {"success": False, "message": f"授权码已绑定到 {lic.domain}，无法更换"}

    lic.domain = req.domain
    lic.activated_at = datetime.utcnow()
    return {"success": True, "message": "域名绑定成功"}

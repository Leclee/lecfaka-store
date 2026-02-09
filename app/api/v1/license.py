"""License verification API"""

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
    result = await db.execute(
        select(License).where(
            License.license_key == req.license_key,
            License.plugin_id == req.plugin_id,
        )
    )
    lic = result.scalar_one_or_none()

    if not lic:
        return {"valid": False, "message": "Invalid license key"}

    if lic.status == 0:
        return {"valid": False, "message": "License disabled"}

    if lic.status == 2:
        return {"valid": False, "message": "License expired"}

    if lic.expires_at and lic.expires_at < datetime.utcnow():
        lic.status = 2
        return {"valid": False, "message": "License expired"}

    if lic.domain and lic.domain != req.domain:
        return {"valid": False, "message": f"License bound to {lic.domain}"}

    if not lic.domain:
        lic.domain = req.domain
        lic.activated_at = datetime.utcnow()

    return {
        "valid": True,
        "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
        "domain": lic.domain,
        "message": "License valid",
    }


@router.post("/bind")
async def bind_domain(req: BindRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(License).where(License.license_key == req.license_key)
    )
    lic = result.scalar_one_or_none()

    if not lic:
        return {"success": False, "message": "Invalid license key"}

    if lic.domain and lic.domain != req.domain:
        return {"success": False, "message": f"License bound to {lic.domain}, cannot change"}

    lic.domain = req.domain
    lic.activated_at = datetime.utcnow()
    return {"success": True, "message": "Domain bound successfully"}
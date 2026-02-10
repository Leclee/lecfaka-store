"""
授权码验证 API

绑定策略：一码一域 + N次换绑
- 首次验证自动绑定域名
- 绑定后仅该域名可通过验证
- 用户可自助换绑（有次数限制）
- 换绑历史全程记录
"""

import json
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


class RebindRequest(BaseModel):
    """换绑请求"""
    license_key: str
    new_domain: str


class LicenseInfoRequest(BaseModel):
    """查询授权信息"""
    license_key: str


# ==================== 验证授权 ====================

@router.post("/verify")
async def verify_license(req: VerifyRequest, db: AsyncSession = Depends(get_db)):
    """
    验证授权码。

    流程：
    1. 查找授权码 → 不存在则拒绝
    2. 检查状态（禁用/过期）
    3. 首次使用 → 自动绑定域名
    4. 已绑定 → 校验域名是否匹配
    """
    lic = await _get_license(req.plugin_id, req.license_key, db)
    if not lic:
        return {"valid": False, "message": "授权码无效"}

    ## 状态检查
    status_check = _check_status(lic)
    if status_check:
        return status_check

    ## 首次激活：自动绑定域名
    if not lic.domain:
        lic.domain = req.domain
        lic.activated_at = datetime.utcnow()
        _append_history(lic, "首次绑定", req.domain)
        return _success_response(lic)

    ## 域名校验
    if lic.domain != req.domain:
        return {
            "valid": False,
            "message": f"授权码已绑定域名 {_mask_domain(lic.domain)}，当前域名不匹配",
            "bound_domain": _mask_domain(lic.domain),
            "rebind_remaining": lic.max_rebinds - lic.rebind_count,
        }

    return _success_response(lic)


# ==================== 换绑域名 ====================

@router.post("/rebind")
async def rebind_domain(req: RebindRequest, db: AsyncSession = Depends(get_db)):
    """
    自助换绑域名。

    规则：
    - 必须已经绑定过域名（首次激活走 verify 接口）
    - 换绑次数不能超过 max_rebinds
    - 新域名不能和当前域名相同
    - 换绑后旧域名立即失效
    - 换绑历史全程记录
    """
    result = await db.execute(
        select(License).where(License.license_key == req.license_key)
    )
    lic = result.scalar_one_or_none()

    if not lic:
        return {"success": False, "message": "授权码无效"}

    status_check = _check_status(lic)
    if status_check:
        return {"success": False, "message": status_check["message"]}

    if not lic.domain:
        return {"success": False, "message": "授权码尚未激活，请先在插件管理中激活"}

    if req.new_domain == lic.domain:
        return {"success": False, "message": "新域名与当前绑定域名相同"}

    if lic.rebind_count >= lic.max_rebinds:
        return {
            "success": False,
            "message": f"换绑次数已用完（{lic.max_rebinds}/{lic.max_rebinds}），请联系客服处理",
        }

    ## 执行换绑
    old_domain = lic.domain
    lic.domain = req.new_domain
    lic.rebind_count += 1
    _append_history(lic, f"换绑 {old_domain} → {req.new_domain}", req.new_domain)

    remaining = lic.max_rebinds - lic.rebind_count
    return {
        "success": True,
        "message": f"域名已换绑为 {req.new_domain}",
        "old_domain": old_domain,
        "new_domain": req.new_domain,
        "rebind_remaining": remaining,
    }


# ==================== 查询授权信息 ====================

@router.post("/info")
async def license_info(req: LicenseInfoRequest, db: AsyncSession = Depends(get_db)):
    """查询授权码的绑定状态和换绑历史"""
    result = await db.execute(
        select(License).where(License.license_key == req.license_key)
    )
    lic = result.scalar_one_or_none()

    if not lic:
        return {"found": False, "message": "授权码无效"}

    return {
        "found": True,
        "plugin_id": lic.plugin_id,
        "status": lic.status,
        "status_text": {0: "已禁用", 1: "有效", 2: "已过期"}.get(lic.status, "未知"),
        "domain": _mask_domain(lic.domain) if lic.domain else None,
        "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
        "activated_at": lic.activated_at.isoformat() if lic.activated_at else None,
        "rebind_count": lic.rebind_count,
        "max_rebinds": lic.max_rebinds,
        "rebind_remaining": lic.max_rebinds - lic.rebind_count,
    }


# ==================== 辅助函数 ====================

async def _get_license(plugin_id: str, license_key: str, db: AsyncSession):
    """查找授权码"""
    result = await db.execute(
        select(License).where(
            License.license_key == license_key,
            License.plugin_id == plugin_id,
        )
    )
    return result.scalar_one_or_none()


def _check_status(lic: License):
    """检查授权状态，返回 None 表示正常"""
    if lic.status == 0:
        return {"valid": False, "message": "授权码已被禁用"}

    if lic.status == 2:
        return {"valid": False, "message": "授权码已过期"}

    if lic.expires_at and lic.expires_at < datetime.utcnow():
        lic.status = 2
        return {"valid": False, "message": "授权码已过期"}

    return None


def _success_response(lic: License):
    """成功响应"""
    return {
        "valid": True,
        "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
        "domain": lic.domain,
        "rebind_remaining": lic.max_rebinds - lic.rebind_count,
        "message": "授权有效",
    }


def _mask_domain(domain: str) -> str:
    """
    部分隐藏域名，防止信息泄露。
    shop.example.com → s***.example.com
    """
    if not domain:
        return ""
    parts = domain.split(".")
    if len(parts) >= 2:
        parts[0] = parts[0][0] + "***"
    return ".".join(parts)


def _append_history(lic: License, action: str, domain: str):
    """追加换绑历史记录"""
    try:
        history = json.loads(lic.rebind_history) if lic.rebind_history else []
    except (json.JSONDecodeError, TypeError):
        history = []

    history.append({
        "action": action,
        "domain": domain,
        "time": datetime.utcnow().isoformat(),
    })
    lic.rebind_history = json.dumps(history, ensure_ascii=False)
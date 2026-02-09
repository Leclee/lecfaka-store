"""插件商店 API"""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.plugin import StorePlugin

router = APIRouter()


@router.get("/plugins")
async def list_plugins(
    db: AsyncSession = Depends(get_db),
    type: Optional[str] = Query(None, description="插件类型"),
    keyword: Optional[str] = Query(None, description="搜索关键�?),
    category: Optional[str] = Query(None, description="分类: official/third_party/enterprise/free"),
):
    """获取商店插件列表"""
    query = select(StorePlugin).where(StorePlugin.status == 1)

    if type:
        query = query.where(StorePlugin.type == type)
    if keyword:
        query = query.where(StorePlugin.name.contains(keyword))
    if category == "official":
        query = query.where(StorePlugin.is_official == True)
    elif category == "enterprise":
        query = query.where(StorePlugin.is_enterprise == True)
    elif category == "free":
        query = query.where(StorePlugin.is_free == True)
    elif category == "third_party":
        query = query.where(StorePlugin.is_official == False)

    query = query.order_by(StorePlugin.created_at.desc())
    result = await db.execute(query)
    plugins = result.scalars().all()

    return {
        "items": [
            {
                "id": p.plugin_id,
                "name": p.name,
                "version": p.version,
                "type": p.type,
                "author": p.author,
                "description": p.description,
                "icon": p.icon,
                "website": p.website,
                "price": float(p.price),
                "is_free": p.is_free,
                "is_official": p.is_official,
                "is_enterprise": p.is_enterprise,
                "category": p.category,
                "channels": p.channels,
                "download_count": p.download_count,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in plugins
        ]
    }


@router.get("/plugins/{plugin_id}")
async def get_plugin(plugin_id: str, db: AsyncSession = Depends(get_db)):
    """获取插件详情"""
    result = await db.execute(
        select(StorePlugin).where(StorePlugin.plugin_id == plugin_id)
    )
    p = result.scalar_one_or_none()
    if not p:
        return {"error": "Plugin not found"}

    return {
        "id": p.plugin_id,
        "name": p.name,
        "version": p.version,
        "type": p.type,
        "author": p.author,
        "description": p.description,
        "icon": p.icon,
        "website": p.website,
        "download_url": p.download_url,
        "price": float(p.price),
        "is_free": p.is_free,
        "channels": p.channels,
    }


@router.post("/check-updates")
async def check_updates(
    installed: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    批量检查插件更新�?
    请求�? {"plugins": {"plugin_id": "installed_version", ...}, "app_version": "1.0.0"}
    响应: 有更新的插件列表 + 最新主程序版本�?    """
    plugin_versions = installed.get("plugins", {})
    client_app_version = installed.get("app_version", "0.0.0")

    updates = []
    if plugin_versions:
        result = await db.execute(
            select(StorePlugin).where(
                StorePlugin.plugin_id.in_(list(plugin_versions.keys())),
                StorePlugin.status == 1,
            )
        )
        for p in result.scalars().all():
            local_ver = plugin_versions.get(p.plugin_id, "0.0.0")
            if _version_gt(p.version, local_ver):
                updates.append({
                    "id": p.plugin_id,
                    "name": p.name,
                    "current_version": local_ver,
                    "latest_version": p.version,
                    "description": p.description,
                })

    # 主程序最新版本（硬编码或从配置读取）
    latest_app_version = "1.0.0"
    app_update = None
    if _version_gt(latest_app_version, client_app_version):
        app_update = {
            "latest_version": latest_app_version,
            "current_version": client_app_version,
            "message": f"LecFaka {latest_app_version} 已发布，请更�?,
        }

    return {
        "plugin_updates": updates,
        "app_update": app_update,
    }


def _version_gt(a: str, b: str) -> bool:
    """比较语义化版�?a > b"""
    try:
        pa = [int(x) for x in a.split(".")]
        pb = [int(x) for x in b.split(".")]
        return pa > pb
    except (ValueError, AttributeError):
        return False

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
    keyword: Optional[str] = Query(None, description="搜索关键词"),
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

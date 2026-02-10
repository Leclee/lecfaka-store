"""
Aurora Premium 极光主题 - 商店上架种子脚本
运行: python -m app.seeds.seed_aurora_theme
"""

import asyncio
import json
from datetime import datetime

from app.database import async_session_maker, init_db
from app.models.plugin import StorePlugin


async def seed():
    """插入 Aurora Premium 主题到商店"""
    await init_db()

    async with async_session_maker() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(StorePlugin).where(StorePlugin.plugin_id == "theme_aurora_premium")
        )
        existing = result.scalar_one_or_none()

        if existing:
            ## 更新已有记录
            existing.name = "Aurora Premium 极光主题"
            existing.version = "1.0.0"
            existing.type = "theme"
            existing.author = "LecFaka Official"
            existing.description = (
                "高端液态玻璃风格主题，融合深色石墨色与金色点缀，支持亮色/暗色双模式切换。"
                "搭配 Cormorant + Montserrat 字体组合，打造奢华购物体验。\n\n"
                "✨ 主要特性：\n"
                "• Liquid Glass 毛玻璃视觉效果\n"
                "• 亮色/暗色双模式（跟随系统或手动切换）\n"
                "• 自定义强调色\n"
                "• Google Fonts 高端字体（可选）\n"
                "• 全面覆盖前台商城所有页面\n"
                "• 与 Ant Design 5 深度集成"
            )
            existing.icon = "🌌"
            existing.website = "https://plugins.leclee.top"
            existing.price = 69
            existing.is_free = False
            existing.is_official = True
            existing.is_enterprise = False
            existing.category = "theme"
            existing.status = 1
            existing.updated_at = datetime.utcnow()
            print("[✓] Aurora Premium 主题已更新")
        else:
            ## 新建记录
            plugin = StorePlugin(
                plugin_id="theme_aurora_premium",
                name="Aurora Premium 极光主题",
                version="1.0.0",
                type="theme",
                author="LecFaka Official",
                description=(
                    "高端液态玻璃风格主题，融合深色石墨色与金色点缀，支持亮色/暗色双模式切换。"
                    "搭配 Cormorant + Montserrat 字体组合，打造奢华购物体验。\n\n"
                    "✨ 主要特性：\n"
                    "• Liquid Glass 毛玻璃视觉效果\n"
                    "• 亮色/暗色双模式（跟随系统或手动切换）\n"
                    "• 自定义强调色\n"
                    "• Google Fonts 高端字体（可选）\n"
                    "• 全面覆盖前台商城所有页面\n"
                    "• 与 Ant Design 5 深度集成"
                ),
                icon="🌌",
                website="https://plugins.leclee.top",
                download_url=None,
                price=69,
                is_free=False,
                is_official=True,
                is_enterprise=False,
                category="theme",
                channels=None,
                status=1,
                download_count=0,
                created_at=datetime.utcnow(),
            )
            db.add(plugin)
            print("[✓] Aurora Premium 主题已上架")

        await db.commit()
    print("[✓] 种子数据写入完成")


if __name__ == "__main__":
    asyncio.run(seed())

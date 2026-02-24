"""
Aurora Premium 极光主题 - 上架种子脚本

运行: python -m app.seeds.seed_aurora_theme
"""

import asyncio
from datetime import datetime

from app.database import async_session_maker, init_db
from app.models.plugin import StorePlugin, StoreUser
from app.core.auth import hash_password
from sqlalchemy import select


async def seed():
    await init_db()
    async with async_session_maker() as session:
        ## 1. 创建超管账号（如果不存在）
        result = await session.execute(
            select(StoreUser).where(StoreUser.role == "superadmin")
        )
        admin = result.scalar_one_or_none()
        if not admin:
            admin = StoreUser(
                email="admin@leclee.top",
                username="admin",
                password_hash=hash_password("admin123456"),
                role="superadmin",
                status=1,
                created_at=datetime.utcnow(),
            )
            session.add(admin)
            await session.flush()
            print(f"[OK] 超管账号已创建: admin@leclee.top / admin123456")
        else:
            print(f"[OK] 超管账号已存在: {admin.email}")

        ## 2. 上架 Aurora Premium 主题
        result = await session.execute(
            select(StorePlugin).where(StorePlugin.plugin_id == "theme_aurora_premium")
        )
        existing = result.scalar_one_or_none()
        if existing:
            print(f"[SKIP] Aurora Premium 已上架 (id={existing.id})")
        else:
            plugin = StorePlugin(
                plugin_id="theme_aurora_premium",
                name="Aurora Premium 极光主题",
                version="1.0.0",
                type="theme",
                author_id=admin.id,
                author_name="LecFaka Official",
                description="高级暗黑极光主题 - 渐变极光色彩 × 毛玻璃质感，为你的发卡站带来专业级视觉体验",
                detail_html="""
                <h2>Aurora Premium 极光主题</h2>
                <p>专为 LecFaka 发卡系统打造的高端暗黑主题，采用极光色彩渐变设计。</p>
                <h3>特色功能</h3>
                <ul>
                    <li>极光渐变色彩体系 (Purple → Cyan → Emerald)</li>
                    <li>毛玻璃 (Glassmorphism) 卡片效果</li>
                    <li>深度优化的暗黑模式</li>
                    <li>AntD Token 完美适配</li>
                    <li>响应式设计，移动端优化</li>
                </ul>
                """,
                icon="/static/plugins/theme_aurora_premium/icon.svg",
                website="https://plugins.leclee.top/plugin/theme_aurora_premium",
                price=69,
                is_free=False,
                is_official=True,
                category="theme",
                status=1,
                created_at=datetime.utcnow(),
            )
            session.add(plugin)
            print("[OK] Aurora Premium 已上架 (¥69)")

        await session.commit()

    print("\n========================================")
    print("  种子数据初始化完成!")
    print("  超管账号: admin@leclee.top")
    print("  超管密码: admin123456")
    print("  ⚠️  请登录后立即修改密码 ⚠️")
    print("========================================")


if __name__ == "__main__":
    asyncio.run(seed())

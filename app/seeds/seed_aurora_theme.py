"""
Premium 高端主题包 - 上架种子脚本

运行: python -m app.seeds.seed_aurora_theme
"""

import asyncio
from datetime import datetime, timezone

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
                created_at=datetime.now(timezone.utc),
            )
            session.add(admin)
            await session.flush()
            print(f"[OK] 超管账号已创建: admin@leclee.top / admin123456")
        else:
            print(f"[OK] 超管账号已存在: {admin.email}")

        ## 2. 删除旧版 theme_aurora_premium（如果存在）
        old_result = await session.execute(
            select(StorePlugin).where(StorePlugin.plugin_id == "theme_aurora_premium")
        )
        old_plugin = old_result.scalar_one_or_none()
        if old_plugin:
            old_plugin.plugin_id = "theme_premium_pack"
            old_plugin.name = "Premium 高端主题包"
            old_plugin.description = "高端液态玻璃风格主题包，包含极光金、深海蓝、赛博紫、暗影绿四种配色方案"
            old_plugin.icon = "/static/plugins/theme_premium_pack/icon.svg"
            old_plugin.download_url = "/uploads/plugins/theme_premium_pack/theme_premium_pack_v1.0.0.zip"
            old_plugin.updated_at = datetime.now(timezone.utc)
            print("[OK] 旧版 theme_aurora_premium 已迁移为 theme_premium_pack")

        ## 3. 上架 Premium 高端主题包（新安装时使用）
        result = await session.execute(
            select(StorePlugin).where(StorePlugin.plugin_id == "theme_premium_pack")
        )
        existing = result.scalar_one_or_none()
        if existing:
            print(f"[SKIP] Premium 高端主题包 已上架 (id={existing.id})")
        else:
            plugin = StorePlugin(
                plugin_id="theme_premium_pack",
                name="Premium 高端主题包",
                version="1.0.0",
                type="theme",
                author_id=admin.id,
                author_name="LecFaka Official",
                description="高端液态玻璃风格主题包，包含极光金、深海蓝、赛博紫、暗影绿四种配色方案，支持亮色/暗色双模式切换、毛玻璃特效",
                detail_html="""
                <h2>Premium 高端主题包</h2>
                <p>专为 LecFaka 发卡系统打造的高端主题包，基于 Liquid Glass 设计风格。</p>
                <h3>包含配色方案</h3>
                <ul>
                    <li>🌟 极光金 — 深色石墨 + 金色点缀 (默认)</li>
                    <li>🌊 深海蓝 — 深邃蓝调 + 科技感</li>
                    <li>💜 赛博紫 — 霓虹紫色 + 未来感</li>
                    <li>🌿 暗影绿 — 自然绿调 + 清新质感</li>
                </ul>
                <h3>核心特性</h3>
                <ul>
                    <li>亮色 / 暗色双模式切换</li>
                    <li>毛玻璃 (Glassmorphism) 视觉效果</li>
                    <li>自定义强调色</li>
                    <li>Cormorant + Montserrat 高端字体组合</li>
                    <li>AntD Token 完美适配</li>
                    <li>响应式设计，移动端优化</li>
                </ul>
                """,
                icon="/static/plugins/theme_premium_pack/icon.svg",
                website="https://plugins.leclee.top/plugin/theme_premium_pack",
                download_url="/uploads/plugins/theme_premium_pack/theme_premium_pack_v1.0.0.zip",
                price=69,
                is_free=False,
                is_official=True,
                category="theme",
                status=1,
                created_at=datetime.now(timezone.utc),
            )
            session.add(plugin)
            print("[OK] Premium 高端主题包 已上架 (¥69)")

        await session.commit()

    print("\n========================================")
    print("  种子数据初始化完成!")
    print("  超管账号: admin@leclee.top")
    print("  超管密码: admin123456")
    print("  ⚠️  请登录后立即修改密码 ⚠️")
    print("========================================")


if __name__ == "__main__":
    asyncio.run(seed())

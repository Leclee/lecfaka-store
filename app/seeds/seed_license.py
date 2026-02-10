"""
Aurora Premium 极光主题 - 授权码种子脚本
运行: python -m app.seeds.seed_license
"""

import asyncio
import secrets
from datetime import datetime, timedelta

from app.database import async_session_maker, init_db
from app.models.plugin import License


async def seed():
    """为 Aurora Premium 生成一个管理员自用授权码"""
    await init_db()

    ## 生成随机授权码
    license_key = f"AURORA-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"

    async with async_session_maker() as db:
        lic = License(
            plugin_id="theme_aurora_premium",
            license_key=license_key,
            domain=None,       ## 首次激活时自动绑定域名
            status=1,          ## 1=有效
            expires_at=None,   ## 永不过期
            created_at=datetime.utcnow(),
        )
        db.add(lic)
        await db.commit()

    print("=" * 50)
    print("  Aurora Premium 授权码已生成")
    print("=" * 50)
    print(f"  授权码: {license_key}")
    print(f"  插件ID: theme_aurora_premium")
    print(f"  状态:   永久有效")
    print(f"  域名:   首次激活时自动绑定")
    print("=" * 50)
    print()
    print("  使用方法:")
    print("  1. 前往后台 → 插件管理")
    print("  2. 找到 Aurora Premium → 输入授权码")
    print("  3. 点击「启用」")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(seed())

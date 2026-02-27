"""
授权码生成工具 - 管理员手动发放

运行: python -m app.seeds.seed_license [--plugin_id PLUGIN_ID] [--email EMAIL] [--expires_days DAYS]

默认生成 1 个 Aurora Premium 授权码，3次换绑机会。
"""

import asyncio
import argparse
import secrets
from datetime import datetime, timezone, timedelta

from app.database import async_session_maker, init_db
from app.models.plugin import License


def generate_key(prefix: str = "AURORA") -> str:
    """生成格式化的授权码: PREFIX-XXXX-XXXX-XXXX"""
    parts = [secrets.token_hex(2).upper() for _ in range(3)]
    return f"{prefix}-{parts[0]}-{parts[1]}-{parts[2]}"


async def seed(
    plugin_id: str = "theme_aurora_premium",
    email: str = "",
    expires_days: int = 0,
    max_rebinds: int = 3,
):
    """生成一个授权码"""
    await init_db()

    license_key = generate_key("AURORA")
    expires_at = None
    if expires_days > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

    async with async_session_maker() as db:
        lic = License(
            plugin_id=plugin_id,
            license_key=license_key,
            domain=None,
            status=1,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc),
            rebind_count=0,
            max_rebinds=max_rebinds,
            rebind_history=None,
            buyer_email=email or None,
            order_no=None,
        )
        db.add(lic)
        await db.commit()

    print("=" * 55)
    print("  授权码已生成")
    print("=" * 55)
    print(f"  授权码:     {license_key}")
    print(f"  插件ID:     {plugin_id}")
    print(f"  买家邮箱:   {email or '未指定'}")
    print(f"  有效期:     {'永久' if not expires_at else f'{expires_days}天 (到 {expires_at.strftime(\"%Y-%m-%d\")})'}")
    print(f"  换绑次数:   最多 {max_rebinds} 次")
    print(f"  绑定策略:   首次激活时自动绑定域名")
    print("=" * 55)
    print()
    print("  发放给用户后，用户在后台「插件管理」→「授权码」中输入即可。")
    print("=" * 55)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="生成插件授权码")
    parser.add_argument("--plugin_id", default="theme_aurora_premium", help="插件ID")
    parser.add_argument("--email", default="", help="购买者邮箱")
    parser.add_argument("--expires_days", type=int, default=0, help="有效期天数，0=永久")
    parser.add_argument("--max_rebinds", type=int, default=3, help="最大换绑次数")
    args = parser.parse_args()

    asyncio.run(seed(
        plugin_id=args.plugin_id,
        email=args.email,
        expires_days=args.expires_days,
        max_rebinds=args.max_rebinds,
    ))

"""
重置数据库 - 删除所有表并重建

⚠️ 危险操作：会清空所有数据！仅用于开发/初始部署。

运行: python -m app.seeds.reset_db
"""

import asyncio
from app.database import engine, Base, init_db

## 确保所有 model 被导入，这样 Base.metadata 才知道所有表
from app.models import plugin  # noqa: F401


async def reset():
    print("⚠️  即将删除所有表并重建...")
    print("    所有数据将被清空！\n")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        print("[OK] 所有表已删除")

    await init_db()
    print("[OK] 所有表已重建")
    print("\n✅ 数据库重置完成！请运行种子脚本初始化数据：")
    print("   python -m app.seeds.seed_aurora_theme")


if __name__ == "__main__":
    asyncio.run(reset())

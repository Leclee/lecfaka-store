"""数据库连接"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator
from .config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # 兼容旧版本：自动追加字段
        try:
            from sqlalchemy import text
            await conn.execute(text("ALTER TABLE store_users ADD COLUMN IF NOT EXISTS balance NUMERIC(10, 2) DEFAULT 0"))
            await conn.execute(text("ALTER TABLE store_users ADD COLUMN IF NOT EXISTS total_income NUMERIC(10, 2) DEFAULT 0"))
        except Exception as e:
            print(f"Update table structure error (Ignored): {e}")

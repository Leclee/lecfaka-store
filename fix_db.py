import asyncio
import asyncpg

async def fix():
    conn = await asyncpg.connect('postgresql://lecfaka:lecfaka123@localhost:5432/lecfaka_store')
    await conn.execute("ALTER TABLE store_users ADD COLUMN IF NOT EXISTS balance NUMERIC(10,2) DEFAULT 0;")
    await conn.execute("ALTER TABLE store_users ADD COLUMN IF NOT EXISTS total_income NUMERIC(10,2) DEFAULT 0;")
    print("DB altered")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(fix())

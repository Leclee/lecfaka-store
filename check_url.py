import asyncio
import asyncpg

async def check():
    conn = await asyncpg.connect('postgresql://lecfaka:lecfaka123@localhost:5433/lecfaka_store')
    row = await conn.fetchrow("SELECT download_url FROM store_plugins WHERE plugin_id='theme_aurora_premium'")
    print("Row:", row)
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check())

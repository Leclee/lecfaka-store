import asyncio
import asyncpg

async def test():
    conn = await asyncpg.connect('postgresql://lecfaka:lecfaka123@localhost:5432/lecfaka')
    rows = await conn.fetch("SELECT plugin_id, download_url FROM store_plugins WHERE plugin_id='theme_aurora_premium'")
    print(rows)
    await conn.close()

if __name__ == '__main__':
    asyncio.run(test())

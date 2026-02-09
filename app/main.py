"""LecFaka Store - 插件商店与授权服务器"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .api.v1.store import router as store_router
from .api.v1.license import router as license_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.debug:
        await init_db()
        print("[OK] Store database tables created")
    yield


app = FastAPI(
    title="LecFaka Store",
    description="插件商店与授权服务器",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(store_router, prefix="/api/v1/store", tags=["Store"])
app.include_router(license_router, prefix="/api/v1/license", tags=["License"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "lecfaka-store"}

"""LecFaka Store - 插件商店与授权服务器"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from .config import settings
from .database import init_db
from .api.v1.store import router as store_router
from .api.v1.license import router as license_router
from .api.v1.auth import router as auth_router
from .api.v1.admin import router as admin_router
from .api.v1.author import router as author_router
from .api.v1.payment import router as payment_router
from .api.v1.finance import router as finance_router

logger = logging.getLogger("lecfaka_store")


def _init_payment_gateways():
    """
    初始化支付网关

    根据 .env 配置自动注册可用的支付网关。
    后续扩展 USDT、支付宝/微信时在此处添加即可。
    """
    from .core.payment import payment_manager

    ## 易支付
    if settings.epay_url and settings.epay_pid and settings.epay_key:
        from .core.payment.epay import EpayGateway
        payment_manager.register(EpayGateway(
            api_url=settings.epay_url,
            pid=settings.epay_pid,
            key=settings.epay_key,
        ))
        logger.info(f"[OK] 易支付已启用: {settings.epay_url}")
    else:
        logger.warning("[WARN] 易支付未配置（epay_url/epay_pid/epay_key），跳过注册")

    ## 预留：USDT
    # if settings.usdt_api_url and settings.usdt_api_key:
    #     from .core.payment.usdt import UsdtGateway
    #     payment_manager.register(UsdtGateway(...))

    ## 预留：支付宝/微信正版
    # if settings.alipay_app_id and settings.alipay_private_key:
    #     from .core.payment.alipay import AlipayGateway
    #     payment_manager.register(AlipayGateway(...))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("[OK] Store database tables ready")
    _init_payment_gateways()
    yield


from fastapi.responses import JSONResponse, FileResponse

app = FastAPI(
    title="LecFaka Store",
    description="插件商店与授权服务器",
    version="2.0.0",
    lifespan=lifespan,
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"服务器内部错误: {str(exc)}" if settings.debug else "服务器内部错误"}
    )

## CORS 配置
_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] if settings.cors_origins != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True if settings.cors_origins != "*" else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

## API 路由
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(store_router, prefix="/api/v1/store", tags=["Store"])
app.include_router(license_router, prefix="/api/v1/license", tags=["License"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(author_router, prefix="/api/v1/author", tags=["Author"])
app.include_router(payment_router, prefix="/api/v1/pay", tags=["Payment"])
app.include_router(finance_router, prefix="/api/v1/finance", tags=["Finance"])

## 静态文件
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

## 插件上传文件目录（仅供 download API 内部读取，禁止直接暴露）
uploads_dir = Path(__file__).parent.parent / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
## ⚠️ 不再挂载 /uploads 为 StaticFiles！所有插件包必须通过
## /api/v1/store/download/{plugin_id} 接口下载（有 JWT 鉴权）


@app.get("/health")
async def health():
    from .core.payment import payment_manager
    return {
        "status": "ok",
        "service": "lecfaka-store",
        "version": "2.0.0",
        "payment_available": payment_manager.is_available(),
        "payment_gateways": payment_manager.list_gateways(),
    }


## 前端页面路由（index.html 兜底）
index_html = static_dir / "index.html"


@app.get("/")
async def serve_index():
    """商店首页"""
    return FileResponse(str(index_html), media_type="text/html")


@app.get("/{path:path}")
async def serve_spa(path: str, request: Request):
    """SPA 兜底路由 - 所有非 API、非静态文件的路径都返回 index.html"""
    ## 排除 API 路径
    if path.startswith("api/") or path.startswith("static/") or path.startswith("uploads/"):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    ## 尝试返回静态文件
    file_path = static_dir / path
    if file_path.is_file():
        return FileResponse(str(file_path))

    ## 兜底返回 index.html
    return FileResponse(str(index_html), media_type="text/html")

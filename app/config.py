"""
插件商店配置
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://lecfaka:lecfaka123@localhost:5432/lecfaka_store"
    secret_key: str = ""  ## 留空 → 首次启动自动生成
    debug: bool = True

    ## JWT 配置
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24  ## 1天
    jwt_refresh_token_expire_days: int = 30

    ## 站点配置
    site_name: str = "LecFaka Store"
    site_url: str = "https://plugins.leclee.top"

    ## ==================== 支付配置 ====================

    ## 易支付 (EasyPay)
    epay_url: str = ""        ## 易支付网关地址，如 https://pay.example.com
    epay_pid: str = ""        ## 商户 ID
    epay_key: str = ""        ## 商户密钥

    ## 支付订单过期时间（分钟）
    payment_expire_minutes: int = 30

    ## 作者收益分成比例（0.0~1.0，表示作者拿到的比例，如 0.7 表示作者 70%、平台 30%）
    author_commission_rate: float = 0.7

    ## 预留：USDT 支付
    # usdt_api_url: str = ""
    # usdt_api_key: str = ""
    # usdt_wallet_address: str = ""

    ## 预留：支付宝/微信正版支付
    # alipay_app_id: str = ""
    # alipay_private_key: str = ""
    # alipay_public_key: str = ""
    # wechat_app_id: str = ""
    # wechat_mch_id: str = ""
    # wechat_api_key: str = ""


settings = Settings()

## SECRET_KEY 自动生成：为空时生成随机密钥并写入 .env
if not settings.secret_key:
    import secrets as _secrets
    import os as _os
    import logging as _log

    _generated_key = _secrets.token_urlsafe(32)
    settings.secret_key = _generated_key

    ## 追加到 .env 文件
    _env_path = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)), ".env")
    try:
        with open(_env_path, "a", encoding="utf-8") as _f:
            _f.write(f"\n## 自动生成的 JWT 签名密钥（请勿删除）\nSECRET_KEY={_generated_key}\n")
        _log.info(f"[config] SECRET_KEY 已自动生成并写入 {_env_path}")
    except Exception as _e:
        _log.warning(f"[config] SECRET_KEY 已自动生成但无法写入 .env: {_e}（本次运行有效，重启后会重新生成）")
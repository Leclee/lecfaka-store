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
    secret_key: str = "store-secret-key-change-this"
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
"""插件商店 - 数据模型"""

from datetime import datetime
from typing import Optional
from decimal import Decimal
from sqlalchemy import String, Integer, DateTime, Text, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base


class StorePlugin(Base):
    """商店插件信息"""
    __tablename__ = "store_plugins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # payment/theme/notify/delivery/extension
    author: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    download_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    is_free: Mapped[bool] = mapped_column(Boolean, default=False)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)
    is_enterprise: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 分类标签
    channels: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 支持的通道 JSON
    status: Mapped[int] = mapped_column(Integer, default=1)  # 0=下架 1=上架
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class License(Base):
    """
    授权码

    绑定策略：一码一域，最多换绑 max_rebinds 次
    - 首次激活时自动绑定请求来源的域名
    - 绑定后只有该域名可以通过验证
    - 用户可自助换绑域名，每次换绑旧域名立即失效
    - 换绑次数用完后域名永久锁定
    """
    __tablename__ = "licenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(String(100), nullable=False)
    license_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=1)  # 0=禁用 1=有效 2=过期
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    ## 换绑机制
    rebind_count: Mapped[int] = mapped_column(Integer, default=0)       ## 已换绑次数
    max_rebinds: Mapped[int] = mapped_column(Integer, default=3)        ## 最大换绑次数
    rebind_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  ## 换绑历史 JSON

    ## 购买信息
    buyer_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  ## 购买者邮箱
    order_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)     ## 关联订单号

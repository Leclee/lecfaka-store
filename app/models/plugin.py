"""插件商店 - 数据模型"""

from datetime import datetime
from typing import Optional
from decimal import Decimal
from sqlalchemy import String, Integer, DateTime, Text, Numeric, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..database import Base


# ==================== 用户 ====================

class StoreUser(Base):
    """商店用户"""
    __tablename__ = "store_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    avatar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="user")  ## superadmin / author / user
    status: Mapped[int] = mapped_column(Integer, default=1)  ## 0=禁用 1=正常
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    ## 关联
    plugins: Mapped[list["UserPlugin"]] = relationship("UserPlugin", back_populates="user")
    orders: Mapped[list["PaymentOrder"]] = relationship("PaymentOrder", back_populates="user")


# ==================== 插件 ====================

class StorePlugin(Base):
    """商店插件信息"""
    __tablename__ = "store_plugins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  ## payment/theme/notify/delivery/extension
    author_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("store_users.id"), nullable=True)
    author_name: Mapped[str] = mapped_column(String(100), default="")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    detail_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  ## 详情页富文本
    icon: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    screenshots: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  ## JSON 数组
    website: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    download_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    is_free: Mapped[bool] = mapped_column(Boolean, default=False)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)
    is_enterprise: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    channels: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=1)  ## 0=下架 1=上架 2=审核中
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    purchase_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    ## 注意：与 UserPlugin 的关联通过 plugin_id 字符串匹配，不是 ForeignKey
    ## 所有查询使用手动 join: UserPlugin.plugin_id == StorePlugin.plugin_id


# ==================== 用户购买的插件 ====================

class UserPlugin(Base):
    """
    用户购买的插件（取代旧的 License 表）

    绑定策略：一个购买记录绑定一个域名，最多换绑 max_rebinds 次
    """
    __tablename__ = "user_plugins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("store_users.id"), nullable=False, index=True)
    plugin_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[int] = mapped_column(Integer, default=1)  ## 0=已退款 1=已激活 2=已过期
    bound_domain: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    rebind_count: Mapped[int] = mapped_column(Integer, default=0)
    max_rebinds: Mapped[int] = mapped_column(Integer, default=3)
    rebind_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  ## JSON
    order_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    purchased_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    ## 关联
    user: Mapped["StoreUser"] = relationship("StoreUser", back_populates="plugins")
    ## 注意：与 StorePlugin 的关联通过 plugin_id 字符串匹配，不使用 relationship


# ==================== 支付订单 ====================

class PaymentOrder(Base):
    """
    支付订单表

    记录每一笔支付的完整信息，与 UserPlugin 通过 order_no 关联。

    支付流程：
    1. 用户发起购买 → 创建 PaymentOrder (status=pending)
    2. 跳转到支付页面完成支付
    3. 收到回调 → 更新 PaymentOrder (status=paid) → 创建 UserPlugin
    """
    __tablename__ = "payment_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("store_users.id"), nullable=False, index=True)
    plugin_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    ## 支付信息
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)  ## 应付金额
    actual_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)  ## 实付金额
    gateway: Mapped[str] = mapped_column(String(50), nullable=False)  ## 支付网关: epay / usdt / alipay_official
    pay_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  ## 具体支付方式: alipay / wxpay / usdt_trc20
    trade_no: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  ## 网关方交易号

    ## 状态
    status: Mapped[str] = mapped_column(String(20), default="pending")  ## pending/paid/failed/expired/refunded/closed
    subject: Mapped[str] = mapped_column(String(200), default="")  ## 订单标题
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  ## 订单描述

    ## 回调信息
    notify_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  ## 回调原始数据 JSON
    payment_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)  ## 支付链接

    ## 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expired_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    ## 关联
    user: Mapped["StoreUser"] = relationship("StoreUser", back_populates="orders")

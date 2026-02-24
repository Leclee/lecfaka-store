"""
支付网关抽象基类

所有支付网关都必须继承此基类，实现统一的接口。
后续扩展 USDT、支付宝/微信正版支付时只需继承此类即可。
"""

from abc import ABC, abstractmethod
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


class PaymentStatus(str, Enum):
    """支付状态枚举"""
    PENDING = "pending"          ## 待支付
    PAID = "paid"                ## 已支付
    FAILED = "failed"            ## 支付失败
    EXPIRED = "expired"          ## 已过期
    REFUNDED = "refunded"        ## 已退款
    CLOSED = "closed"            ## 已关闭


@dataclass
class PaymentResult:
    """
    支付网关统一返回结果

    @param success: 操作是否成功
    @param payment_url: 支付页面 URL（用于跳转）
    @param trade_no: 网关方的交易号
    @param order_no: 我方订单号
    @param message: 提示消息
    @param raw: 网关返回的原始数据
    """
    success: bool
    payment_url: str = ""
    trade_no: str = ""
    order_no: str = ""
    message: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NotifyResult:
    """
    异步回调验证结果

    @param valid: 签名验证是否通过
    @param trade_no: 网关方的交易号
    @param order_no: 我方订单号
    @param amount: 实付金额（元）
    @param status: 支付状态
    @param message: 提示消息
    @param raw: 网关返回的原始数据
    """
    valid: bool
    trade_no: str = ""
    order_no: str = ""
    amount: float = 0.0
    status: PaymentStatus = PaymentStatus.PENDING
    message: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)


class PaymentGateway(ABC):
    """
    支付网关抽象基类

    所有支付方式必须实现以下方法：
    - create_payment: 创建支付订单，返回支付链接
    - verify_notify: 验证异步回调签名
    - query_order: 主动查询订单状态
    - get_name: 返回网关名称标识

    扩展新支付方式只需：
    1. 继承此基类
    2. 实现所有抽象方法
    3. 在 PaymentManager 中注册
    """

    @abstractmethod
    async def create_payment(
        self,
        order_no: str,
        amount: float,
        subject: str,
        body: str = "",
        notify_url: str = "",
        return_url: str = "",
        **kwargs,
    ) -> PaymentResult:
        """
        创建支付订单

        @param order_no: 我方订单号
        @param amount: 金额（元）
        @param subject: 订单标题
        @param body: 订单描述
        @param notify_url: 异步通知 URL
        @param return_url: 同步跳转 URL
        @return: PaymentResult
        """
        ...

    @abstractmethod
    async def verify_notify(self, params: Dict[str, str]) -> NotifyResult:
        """
        验证异步回调通知

        @param params: 回调参数（GET 或 POST）
        @return: NotifyResult
        """
        ...

    @abstractmethod
    async def query_order(self, order_no: str) -> NotifyResult:
        """
        主动查询订单支付状态

        @param order_no: 我方订单号
        @return: NotifyResult
        """
        ...

    @abstractmethod
    def get_name(self) -> str:
        """返回网关标识名称，如 'epay', 'usdt', 'alipay_official'"""
        ...

    @abstractmethod
    def get_display_name(self) -> str:
        """返回网关显示名称，如 '支付宝/微信', 'USDT'"""
        ...

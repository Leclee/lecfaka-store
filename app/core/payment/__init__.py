"""
支付网关模块

可扩展的支付网关架构，支持多种支付方式：
- 易支付 (EasyPay)
- USDT (预留)
- 支付宝/微信官方 (预留)
"""

from .base import PaymentGateway, PaymentResult, PaymentStatus
from .manager import payment_manager

__all__ = ["PaymentGateway", "PaymentResult", "PaymentStatus", "payment_manager"]

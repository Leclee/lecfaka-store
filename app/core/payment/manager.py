"""
支付网关管理器

负责注册、获取、初始化支付网关实例。
采用插件式架构，后续扩展新支付方式时只需在此注册即可。
"""

import logging
from typing import Dict, Optional, List

from .base import PaymentGateway

logger = logging.getLogger("payment.manager")


class PaymentManager:
    """
    支付网关管理器（单例模式）

    使用方式：
        from app.core.payment import payment_manager

        ## 注册网关
        payment_manager.register(EpayGateway(api_url=..., pid=..., key=...))

        ## 获取网关
        gateway = payment_manager.get("epay")

        ## 获取所有可用网关
        gateways = payment_manager.list_gateways()
    """

    def __init__(self):
        self._gateways: Dict[str, PaymentGateway] = {}

    def register(self, gateway: PaymentGateway) -> None:
        """
        注册一个支付网关

        @param gateway: PaymentGateway 实例
        """
        name = gateway.get_name()
        self._gateways[name] = gateway
        logger.info(f"已注册支付网关: {name} ({gateway.get_display_name()})")

    def unregister(self, name: str) -> None:
        """注销支付网关"""
        if name in self._gateways:
            del self._gateways[name]
            logger.info(f"已注销支付网关: {name}")

    def get(self, name: str) -> Optional[PaymentGateway]:
        """
        获取指定的支付网关

        @param name: 网关标识名称
        @return: PaymentGateway 实例，未找到返回 None
        """
        return self._gateways.get(name)

    def get_default(self) -> Optional[PaymentGateway]:
        """获取默认（第一个注册的）支付网关"""
        if self._gateways:
            return next(iter(self._gateways.values()))
        return None

    def list_gateways(self) -> List[Dict[str, str]]:
        """
        列出所有已注册的支付网关

        @return: [{"name": "epay", "display_name": "在线支付"}, ...]
        """
        return [
            {"name": gw.get_name(), "display_name": gw.get_display_name()}
            for gw in self._gateways.values()
        ]

    def is_available(self) -> bool:
        """检查是否有可用的支付网关"""
        return len(self._gateways) > 0


## 全局支付管理器实例
payment_manager = PaymentManager()

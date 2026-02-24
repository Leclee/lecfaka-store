"""
易支付 (EasyPay) 网关实现

易支付是国内常见的聚合支付网关，支持支付宝、微信等多种支付方式。
接口文档参考：https://epay.docs.example/

请求流程：
1. 商户后端拼接参数 + 签名 → 得到支付页面 URL
2. 用户跳转到支付页面完成支付
3. 支付完成后，易支付通过 notify_url 异步通知（GET 请求）
4. 用户浏览器通过 return_url 同步跳转回商户页面
"""

import hashlib
import logging
from typing import Dict, Any
from urllib.parse import urlencode

import httpx

from .base import PaymentGateway, PaymentResult, NotifyResult, PaymentStatus

logger = logging.getLogger("payment.epay")


class EpayGateway(PaymentGateway):
    """
    易支付网关实现

    配置参数：
    - api_url: 易支付网关地址，如 https://pay.example.com
    - pid: 商户 ID
    - key: 商户密钥（用于签名）

    支持的支付方式 (type 参数)：
    - alipay: 支付宝
    - wxpay: 微信支付
    - qqpay: QQ 支付
    """

    def __init__(self, api_url: str, pid: str, key: str):
        """
        @param api_url: 易支付网关地址
        @param pid: 商户 ID
        @param key: 商户密钥
        """
        self.api_url = api_url.rstrip("/")
        self.pid = pid
        self.key = key

    def get_name(self) -> str:
        return "epay"

    def get_display_name(self) -> str:
        return "在线支付"

    def _sign(self, params: Dict[str, str]) -> str:
        """
        生成 MD5 签名

        签名规则：
        1. 按参数名 ASCII 升序排列
        2. 过滤掉 sign、sign_type 和空值参数
        3. 使用 & 拼接为 key=value 串
        4. 尾部拼接商户密钥 key
        5. 计算 MD5
        """
        ## 过滤并排序
        filtered = {
            k: v for k, v in sorted(params.items())
            if k not in ("sign", "sign_type") and v != "" and v is not None
        }
        ## 拼接
        sign_str = "&".join(f"{k}={v}" for k, v in filtered.items())
        sign_str += self.key
        ## MD5
        return hashlib.md5(sign_str.encode("utf-8")).hexdigest()

    def _verify_sign(self, params: Dict[str, str]) -> bool:
        """验证回调签名"""
        received_sign = params.get("sign", "")
        calculated_sign = self._sign(params)
        return received_sign == calculated_sign

    async def create_payment(
        self,
        order_no: str,
        amount: float,
        subject: str,
        body: str = "",
        notify_url: str = "",
        return_url: str = "",
        pay_type: str = "alipay",
        **kwargs,
    ) -> PaymentResult:
        """
        创建易支付订单

        @param order_no: 商户订单号
        @param amount: 金额（元）
        @param subject: 商品名称
        @param body: 商品描述
        @param notify_url: 异步通知地址
        @param return_url: 同步跳转地址
        @param pay_type: 支付方式 (alipay/wxpay/qqpay)
        @return: PaymentResult（包含支付链接）
        """
        params = {
            "pid": self.pid,
            "type": pay_type,
            "out_trade_no": order_no,
            "notify_url": notify_url,
            "return_url": return_url,
            "name": subject,
            "money": f"{amount:.2f}",
        }
        params["sign"] = self._sign(params)
        params["sign_type"] = "MD5"

        ## 构建支付页面 URL
        payment_url = f"{self.api_url}/submit.php?{urlencode(params)}"

        logger.info(f"创建支付订单: order_no={order_no}, amount={amount}, type={pay_type}")

        return PaymentResult(
            success=True,
            payment_url=payment_url,
            order_no=order_no,
            message="支付链接已生成",
            raw=params,
        )

    async def verify_notify(self, params: Dict[str, str]) -> NotifyResult:
        """
        验证易支付异步回调

        回调参数包括：
        - pid: 商户 ID
        - trade_no: 易支付交易号
        - out_trade_no: 商户订单号
        - type: 支付方式
        - name: 商品名称
        - money: 金额
        - trade_status: 交易状态 (TRADE_SUCCESS)
        - sign: MD5 签名
        - sign_type: 签名方式
        """
        if not self._verify_sign(params):
            logger.warning(f"签名验证失败: {params}")
            return NotifyResult(valid=False, message="签名验证失败", raw=params)

        trade_status = params.get("trade_status", "")
        order_no = params.get("out_trade_no", "")
        trade_no = params.get("trade_no", "")
        amount = float(params.get("money", "0"))

        if trade_status == "TRADE_SUCCESS":
            status = PaymentStatus.PAID
        elif trade_status == "TRADE_CLOSED":
            status = PaymentStatus.CLOSED
        else:
            status = PaymentStatus.PENDING

        logger.info(f"回调验证: order_no={order_no}, trade_no={trade_no}, status={status}")

        return NotifyResult(
            valid=True,
            trade_no=trade_no,
            order_no=order_no,
            amount=amount,
            status=status,
            message="OK",
            raw=params,
        )

    async def query_order(self, order_no: str) -> NotifyResult:
        """
        主动查询订单状态

        调用易支付的 API 接口查询：
        GET {api_url}/api.php?act=order&pid={pid}&key={key}&out_trade_no={order_no}
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.api_url}/api.php",
                    params={
                        "act": "order",
                        "pid": self.pid,
                        "key": self.key,
                        "out_trade_no": order_no,
                    },
                )
                data = resp.json()

            if data.get("code") == 1:
                status_map = {
                    "1": PaymentStatus.PAID,
                    "0": PaymentStatus.PENDING,
                }
                return NotifyResult(
                    valid=True,
                    trade_no=data.get("trade_no", ""),
                    order_no=order_no,
                    amount=float(data.get("money", "0")),
                    status=status_map.get(str(data.get("status", "0")), PaymentStatus.PENDING),
                    message="查询成功",
                    raw=data,
                )
            else:
                return NotifyResult(
                    valid=False,
                    order_no=order_no,
                    message=data.get("msg", "查询失败"),
                    raw=data,
                )
        except Exception as e:
            logger.error(f"查询订单失败: {e}")
            return NotifyResult(
                valid=False,
                order_no=order_no,
                message=f"查询失败: {e}",
            )

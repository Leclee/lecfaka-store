"""
支付 API — 创建支付订单、回调通知、查询状态

支付流程：
1. 前端调用 POST /api/v1/pay/create-order 创建支付订单
   → 后端返回 payment_url（支付页面链接） + order_no
2. 前端跳转到 payment_url 完成支付
3. 支付完成后，支付网关调用 GET /api/v1/pay/notify/{gateway} 异步通知
   → 后端验证签名、更新订单状态为 paid、创建 UserPlugin
4. 用户浏览器通过 return_url 跳回前端支付结果页面
5. 前端可通过 GET /api/v1/pay/status/{order_no} 轮询订单支付状态
"""

import json
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...config import settings
from ...models.plugin import StoreUser, StorePlugin, UserPlugin, PaymentOrder
from ...core.auth import get_current_user
from ...core.payment import payment_manager, PaymentStatus

logger = logging.getLogger("api.payment")

router = APIRouter()


# ==================== 请求/响应模型 ====================

class CreateOrderRequest(BaseModel):
    """创建支付订单请求"""
    plugin_id: str
    gateway: str = "epay"        ## 支付网关: epay / usdt
    pay_type: str = "alipay"     ## 具体方式: alipay / wxpay / qqpay


class CreateOrderResponse(BaseModel):
    """创建支付订单响应"""
    success: bool
    order_no: str = ""
    payment_url: str = ""
    message: str = ""
    amount: float = 0.0


# ==================== 创建支付订单 ====================

@router.post("/create-order")
async def create_order(
    req: CreateOrderRequest,
    request: Request,
    user: StoreUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    创建支付订单

    流程：
    1. 验证插件存在且为付费插件
    2. 检查是否已购买
    3. 检查是否有未支付的同插件订单（复用）
    4. 创建支付订单 → 调用支付网关获取支付链接
    5. 返回支付链接给前端跳转
    """
    ## 1. 验证插件
    result = await db.execute(
        select(StorePlugin).where(
            StorePlugin.plugin_id == req.plugin_id,
            StorePlugin.status == 1,
        )
    )
    plugin = result.scalar_one_or_none()
    if not plugin:
        raise HTTPException(status_code=404, detail="插件不存在或已下架")

    if plugin.is_free:
        raise HTTPException(status_code=400, detail="免费插件无需支付，请直接安装")

    ## 2. 检查是否已购买
    existing_up = await db.execute(
        select(UserPlugin).where(
            UserPlugin.user_id == user.id,
            UserPlugin.plugin_id == req.plugin_id,
            UserPlugin.status == 1,
        )
    )
    if existing_up.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="您已购买过此插件")

    ## 3. 检查是否有待支付的同插件订单（5分钟内有效）
    recent_cutoff = datetime.utcnow() - timedelta(minutes=5)
    existing_order = await db.execute(
        select(PaymentOrder).where(
            PaymentOrder.user_id == user.id,
            PaymentOrder.plugin_id == req.plugin_id,
            PaymentOrder.status == "pending",
            PaymentOrder.created_at > recent_cutoff,
        )
    )
    pending_order = existing_order.scalar_one_or_none()
    if pending_order and pending_order.payment_url:
        ## 复用未过期的待支付订单
        return CreateOrderResponse(
            success=True,
            order_no=pending_order.order_no,
            payment_url=pending_order.payment_url,
            message="请完成支付",
            amount=float(pending_order.amount),
        )

    ## 4. 获取支付网关
    gateway = payment_manager.get(req.gateway)
    if not gateway:
        raise HTTPException(status_code=400, detail=f"不支持的支付方式: {req.gateway}")

    ## 5. 生成订单号
    order_no = f"LS-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4).upper()}"
    amount = float(plugin.price)

    ## 6. 构建回调 URL
    base_url = str(request.base_url).rstrip("/")
    notify_url = f"{base_url}/api/v1/pay/notify/{req.gateway}"
    return_url = f"{base_url}/pay/result?order_no={order_no}"

    ## 7. 调用支付网关创建支付
    pay_result = await gateway.create_payment(
        order_no=order_no,
        amount=amount,
        subject=f"购买插件: {plugin.name}",
        body=f"{plugin.name} v{plugin.version}",
        notify_url=notify_url,
        return_url=return_url,
        pay_type=req.pay_type,
    )

    if not pay_result.success:
        raise HTTPException(status_code=500, detail=pay_result.message or "创建支付订单失败")

    ## 8. 保存订单到数据库
    order = PaymentOrder(
        order_no=order_no,
        user_id=user.id,
        plugin_id=req.plugin_id,
        amount=plugin.price,
        gateway=req.gateway,
        pay_type=req.pay_type,
        status="pending",
        subject=f"购买插件: {plugin.name}",
        payment_url=pay_result.payment_url,
        created_at=datetime.utcnow(),
        expired_at=datetime.utcnow() + timedelta(minutes=settings.payment_expire_minutes),
    )
    db.add(order)
    await db.flush()

    logger.info(f"支付订单已创建: order_no={order_no}, user={user.username}, plugin={plugin.name}, amount={amount}")

    return CreateOrderResponse(
        success=True,
        order_no=order_no,
        payment_url=pay_result.payment_url,
        message="请前往支付页面完成支付",
        amount=amount,
    )


# ==================== 支付回调（异步通知） ====================

@router.get("/notify/{gateway}")
async def payment_notify(
    gateway: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    支付网关异步回调（GET 请求）

    接收支付网关的回调通知，验证签名后：
    1. 更新 PaymentOrder 状态为 paid
    2. 创建 UserPlugin 记录（用户获得插件）
    3. 更新插件购买计数
    4. 返回 "success" 告知网关处理成功
    """
    ## 获取支付网关实例
    gw = payment_manager.get(gateway)
    if not gw:
        logger.error(f"未知支付网关回调: {gateway}")
        return PlainTextResponse("fail")

    ## 验证回调签名
    params = dict(request.query_params)
    notify_result = await gw.verify_notify(params)

    if not notify_result.valid:
        logger.warning(f"回调签名验证失败: {notify_result.message}")
        return PlainTextResponse("fail")

    if notify_result.status != PaymentStatus.PAID:
        logger.info(f"订单未支付成功，当前状态: {notify_result.status}")
        return PlainTextResponse("success")

    order_no = notify_result.order_no

    ## 查找订单
    result = await db.execute(
        select(PaymentOrder).where(PaymentOrder.order_no == order_no)
    )
    order = result.scalar_one_or_none()
    if not order:
        logger.error(f"回调订单不存在: {order_no}")
        return PlainTextResponse("fail")

    ## 防止重复处理
    if order.status == "paid":
        logger.info(f"订单已处理过: {order_no}")
        return PlainTextResponse("success")

    ## 金额验证
    if notify_result.amount > 0 and abs(float(order.amount) - notify_result.amount) > 0.01:
        logger.error(f"金额不匹配: 订单 {float(order.amount)}, 回调 {notify_result.amount}")
        return PlainTextResponse("fail")

    ## 更新订单状态
    order.status = "paid"
    order.trade_no = notify_result.trade_no
    order.actual_amount = notify_result.amount if notify_result.amount > 0 else order.amount
    order.paid_at = datetime.utcnow()
    order.notify_data = json.dumps(notify_result.raw, ensure_ascii=False)

    ## 创建 UserPlugin（用户获得插件）
    existing_up = await db.execute(
        select(UserPlugin).where(
            UserPlugin.user_id == order.user_id,
            UserPlugin.plugin_id == order.plugin_id,
            UserPlugin.status == 1,
        )
    )
    if not existing_up.scalar_one_or_none():
        up = UserPlugin(
            user_id=order.user_id,
            plugin_id=order.plugin_id,
            status=1,
            bound_domain=None,
            rebind_count=0,
            max_rebinds=3,
            order_no=order_no,
            purchased_at=datetime.utcnow(),
        )
        db.add(up)

        ## 更新插件购买计数
        plugin_result = await db.execute(
            select(StorePlugin).where(StorePlugin.plugin_id == order.plugin_id)
        )
        plugin = plugin_result.scalar_one_or_none()
        if plugin:
            plugin.purchase_count += 1

    await db.flush()
    logger.info(f"支付成功: order_no={order_no}, trade_no={notify_result.trade_no}")

    return PlainTextResponse("success")


# ==================== 查询订单状态 ====================

@router.get("/status/{order_no}")
async def get_order_status(
    order_no: str,
    user: StoreUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    查询支付订单状态

    前端用于轮询支付结果。只能查询自己的订单。
    """
    result = await db.execute(
        select(PaymentOrder).where(
            PaymentOrder.order_no == order_no,
            PaymentOrder.user_id == user.id,
        )
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")

    ## 如果订单还是 pending 且已过期，标记为 expired
    if order.status == "pending" and order.expired_at and order.expired_at < datetime.utcnow():
        order.status = "expired"
        await db.flush()

    ## 获取插件名称
    plugin_result = await db.execute(
        select(StorePlugin).where(StorePlugin.plugin_id == order.plugin_id)
    )
    plugin = plugin_result.scalar_one_or_none()

    return {
        "order_no": order.order_no,
        "plugin_id": order.plugin_id,
        "plugin_name": plugin.name if plugin else "",
        "amount": float(order.amount),
        "actual_amount": float(order.actual_amount) if order.actual_amount else None,
        "gateway": order.gateway,
        "pay_type": order.pay_type,
        "status": order.status,
        "trade_no": order.trade_no,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "paid_at": order.paid_at.isoformat() if order.paid_at else None,
    }


# ==================== 可用支付方式列表 ====================

@router.get("/gateways")
async def list_gateways():
    """获取所有可用的支付网关列表"""
    return {"gateways": payment_manager.list_gateways()}


# ==================== 我的订单列表 ====================

@router.get("/my-orders")
async def my_orders(
    user: StoreUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """获取当前用户的支付订单列表"""
    query = select(PaymentOrder).where(PaymentOrder.user_id == user.id)

    if status:
        query = query.where(PaymentOrder.status == status)

    query = query.order_by(PaymentOrder.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    orders = result.scalars().all()

    ## 批量查询插件名称
    plugin_ids = list({o.plugin_id for o in orders})
    plugins_result = await db.execute(
        select(StorePlugin).where(StorePlugin.plugin_id.in_(plugin_ids))
    ) if plugin_ids else None
    plugin_map = {}
    if plugins_result:
        for p in plugins_result.scalars().all():
            plugin_map[p.plugin_id] = p.name

    return {
        "items": [
            {
                "order_no": o.order_no,
                "plugin_id": o.plugin_id,
                "plugin_name": plugin_map.get(o.plugin_id, ""),
                "amount": float(o.amount),
                "gateway": o.gateway,
                "pay_type": o.pay_type,
                "status": o.status,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "paid_at": o.paid_at.isoformat() if o.paid_at else None,
            }
            for o in orders
        ]
    }

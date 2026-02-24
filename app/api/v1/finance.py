import logging
from datetime import datetime
from typing import Optional, List
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.plugin import StoreUser, WithdrawalRecord
from .auth import get_current_user
from .admin import require_superadmin

logger = logging.getLogger("lecfaka_store.finance")
router = APIRouter()

# ==================== 作者财务接口 ====================

@router.get("/stats")
async def get_my_finance_stats(
    user: StoreUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前作者的财务统计"""
    # 计算提现中的金额
    result = await db.execute(
        select(WithdrawalRecord.amount)
        .where(WithdrawalRecord.user_id == user.id)
        .where(WithdrawalRecord.status == "pending")
    )
    pending_amount = sum([r[0] for r in result.all()])

    return {
        "balance": float(user.balance or 0),
        "total_income": float(user.total_income or 0),
        "pending_withdrawal": float(pending_amount)
    }


class WithdrawRequest(BaseModel):
    amount: float
    account_type: str  # alipay/wxpay/bank/usdt
    account_no: str
    account_name: Optional[str] = None


@router.post("/withdraw")
async def request_withdraw(
    req: WithdrawRequest,
    user: StoreUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """作者申请提现"""
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="提现金额必须大于0")
    
    if float(user.balance or 0) < req.amount:
        raise HTTPException(status_code=400, detail="余额不足")
        
    # 扣减余额
    user.balance = float(user.balance or 0) - req.amount
    
    # 创建记录
    record = WithdrawalRecord(
        user_id=user.id,
        amount=req.amount,
        status="pending",
        account_type=req.account_type,
        account_no=req.account_no,
        account_name=req.account_name,
        created_at=datetime.utcnow()
    )
    db.add(record)
    await db.commit()
    
    return {"success": True, "message": "提现申请已提交，等待审核"}


@router.get("/withdrawals")
async def get_my_withdrawals(
    skip: int = 0,
    limit: int = 50,
    user: StoreUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """作者查询自己的提现记录"""
    result = await db.execute(
        select(WithdrawalRecord)
        .where(WithdrawalRecord.user_id == user.id)
        .order_by(desc(WithdrawalRecord.created_at))
        .offset(skip)
        .limit(limit)
    )
    records = result.scalars().all()
    
    return {
        "items": [
            {
                "id": r.id,
                "amount": float(r.amount),
                "status": r.status,
                "account_type": r.account_type,
                "account_no": r.account_no,
                "account_name": r.account_name,
                "reject_reason": r.reject_reason,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "processed_at": r.processed_at.isoformat() if r.processed_at else None,
            }
            for r in records
        ]
    }

# ==================== 管理员审批接口 ====================

@router.get("/admin/withdrawals")
async def admin_get_withdrawals(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    admin: StoreUser = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """管理员分页查询所有提现记录"""
    query = select(WithdrawalRecord, StoreUser.username).join(StoreUser, WithdrawalRecord.user_id == StoreUser.id)
    if status:
        query = query.where(WithdrawalRecord.status == status)
        
    query = query.order_by(desc(WithdrawalRecord.created_at)).offset(skip).limit(limit)
    
    result = await db.execute(query)
    rows = result.all()
    
    return {
        "items": [
            {
                "id": r.WithdrawalRecord.id,
                "username": r.username,
                "amount": float(r.WithdrawalRecord.amount),
                "status": r.WithdrawalRecord.status,
                "account_type": r.WithdrawalRecord.account_type,
                "account_no": r.WithdrawalRecord.account_no,
                "account_name": r.WithdrawalRecord.account_name,
                "reject_reason": r.WithdrawalRecord.reject_reason,
                "created_at": r.WithdrawalRecord.created_at.isoformat() if r.WithdrawalRecord.created_at else None,
                "processed_at": r.WithdrawalRecord.processed_at.isoformat() if r.WithdrawalRecord.processed_at else None,
            }
            for r in rows
        ]
    }

class ProcessWithdrawalRequest(BaseModel):
    action: str  # approve / reject
    reason: Optional[str] = None

@router.post("/admin/withdrawals/{record_id}/process")
async def admin_process_withdrawal(
    record_id: int,
    req: ProcessWithdrawalRequest,
    admin: StoreUser = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    """管理员审批提现"""
    result = await db.execute(select(WithdrawalRecord).where(WithdrawalRecord.id == record_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="记录不存在")
        
    if record.status != "pending":
        raise HTTPException(status_code=400, detail="该记录已处理")
        
    if req.action == "approve":
        record.status = "approved"
        record.processed_at = datetime.utcnow()
    elif req.action == "reject":
        record.status = "rejected"
        record.reject_reason = req.reason
        record.processed_at = datetime.utcnow()
        # 退还余额
        user_result = await db.execute(select(StoreUser).where(StoreUser.id == record.user_id))
        user = user_result.scalar_one_or_none()
        if user:
            user.balance = float(user.balance or 0) + float(record.amount)
    else:
        raise HTTPException(status_code=400, detail="未知操作")
        
    await db.commit()
    return {"success": True, "message": "处理完成"}

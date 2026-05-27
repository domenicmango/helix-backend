from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from auth import get_current_user
from database import (upsert_asset, upsert_debt, all_assets, all_debts,
                       net_worth, emergency_months, wealth_score,
                       get_month_cashflow, add_snapshot, get_snapshots)

router = APIRouter()

class AssetRequest(BaseModel):
    name: str
    amount: float
    currency: str = "EUR"
    is_liquid: bool = False
    is_crypto: bool = False

class DebtRequest(BaseModel):
    name: str
    amount: float
    currency: str = "EUR"
    interest_rate: float = 0

@router.get("/status")
def status(user=Depends(get_current_user)):
    uid  = user["user_id"]
    base = user["base_currency"]
    nw   = net_worth(uid)
    cf   = get_month_cashflow(uid)
    em   = emergency_months(uid)
    sc   = wealth_score(uid)
    return {"net_worth": nw["net_worth"], "total_assets": nw["total_assets"],
            "total_debts": nw["total_debts"], "assets": nw["assets"], "debts": nw["debts"],
            "month_income": cf["income"], "month_expenses": cf["expenses"],
            "month_surplus": cf["surplus"], "savings_rate": cf["savings_rate"],
            "emergency_months": em, "wealth_score": sc, "base_currency": base}

@router.post("/assets")
def add_asset(req: AssetRequest, user=Depends(get_current_user)):
    upsert_asset(user["user_id"], req.name, req.amount,
                 is_liquid=int(req.is_liquid), is_crypto=int(req.is_crypto))
    return {"ok": True, "name": req.name, "amount": req.amount}

@router.post("/debts")
def add_debt(req: DebtRequest, user=Depends(get_current_user)):
    upsert_debt(user["user_id"], req.name, req.amount, req.interest_rate)
    return {"ok": True}

@router.get("/assets")
def get_assets(user=Depends(get_current_user)):
    return [dict(a) for a in all_assets(user["user_id"])]

@router.get("/debts")
def get_debts(user=Depends(get_current_user)):
    return [dict(d) for d in all_debts(user["user_id"])]

@router.post("/snapshot")
def snapshot(user=Depends(get_current_user)):
    val = add_snapshot(user["user_id"], user["base_currency"])
    return {"net_worth": val, "saved": True}

@router.get("/trend")
def trend(user=Depends(get_current_user)):
    rows = get_snapshots(user["user_id"])
    if len(rows) < 2:
        return {"count": len(rows), "data": [dict(r) for r in rows]}
    first = rows[0]["net_worth_base"]
    last  = rows[-1]["net_worth_base"]
    growth = last - first
    pct    = round(growth / first * 100, 1) if first else 0
    return {"count": len(rows), "nominal_growth": growth,
            "nominal_pct": pct, "data": [dict(r) for r in rows]}

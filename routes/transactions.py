from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from auth import get_current_user
from database import add_transaction, list_transactions, delete_last_transaction, month_cashflow
import requests

router = APIRouter()

class TxRequest(BaseModel):
    amount: float
    currency: str
    direction: str
    category: Optional[str] = None
    source: Optional[str] = None
    note: Optional[str] = None

def convert(amount, from_cur, to_cur):
    if from_cur == to_cur:
        return amount, 1.0
    if from_cur in ("USDT","USDC"): from_cur = "USD"
    if to_cur   in ("USDT","USDC"): to_cur   = "USD"
    try:
        r = requests.get(f"https://open.er-api.com/v6/latest/{from_cur}", timeout=8)
        data = r.json()
        if data.get("result") == "success" and to_cur in data["rates"]:
            rate = data["rates"][to_cur]
            return round(amount * rate, 4), rate
    except Exception:
        pass
    return amount, 1.0

@router.post("")
def add_tx(req: TxRequest, user=Depends(get_current_user)):
    uid  = user["user_id"]
    base = user["base_currency"]
    amount_base, rate = convert(req.amount, req.currency.upper(), base)
    tx_id = add_transaction(uid, req.amount, req.currency.upper(), amount_base,
                             base, req.direction, req.source, req.category, req.note, rate)
    cf = month_cashflow(uid)
    return {"id": tx_id, "amount_base": amount_base, "base_currency": base,
            "fx_rate": rate, "cashflow": cf}

@router.get("")
def get_txs(limit: int = 20, user=Depends(get_current_user)):
    rows = list_transactions(user["user_id"], limit)
    return [dict(r) for r in rows]

@router.get("/month")
def get_month(user=Depends(get_current_user)):
    return month_cashflow(user["user_id"])

@router.delete("/last")
def undo(user=Depends(get_current_user)):
    ok = delete_last_transaction(user["user_id"])
    return {"deleted": ok}

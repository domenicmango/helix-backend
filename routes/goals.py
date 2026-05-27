from fastapi import APIRouter, Depends
from pydantic import BaseModel
from auth import get_current_user
from database import create_goal, list_goals, month_cashflow

router = APIRouter()

class GoalRequest(BaseModel):
    title: str
    target_amount: float
    target_months: int

@router.post("")
def add_goal(req: GoalRequest, user=Depends(get_current_user)):
    uid = user["user_id"]
    goal_id = create_goal(uid, req.title, req.target_amount, req.target_months)
    cf = month_cashflow(uid)
    monthly_needed = req.target_amount / req.target_months
    gap = monthly_needed - cf["surplus"]
    return {"id": goal_id, "title": req.title, "target_amount": req.target_amount,
            "monthly_needed": round(monthly_needed, 2),
            "current_surplus": round(cf["surplus"], 2),
            "gap": round(gap, 2), "achievable": gap <= 0}

@router.get("")
def get_goals(user=Depends(get_current_user)):
    return [dict(g) for g in list_goals(user["user_id"])]

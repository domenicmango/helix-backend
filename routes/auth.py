from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from auth import hash_password, verify_password, create_token, get_current_user
from database import get_user_by_email, create_user

router = APIRouter()

class RegisterRequest(BaseModel):
    email: str
    password: str
    first_name: str
    base_currency: str = "EUR"

@router.post("/register")
def register(req: RegisterRequest):
    if get_user_by_email(req.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = create_user(req.email, hash_password(req.password), req.first_name, req.base_currency)
    user_id = user["user_id"]
    token = create_token(user_id)
    return {"token": token, "user_id": user_id, "first_name": req.first_name}

@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_email(form.username)
    if not user or not verify_password(form.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Wrong email or password")
    token = create_token(user["user_id"])
    return {"access_token": token, "token_type": "bearer",
            "user_id": user["user_id"], "first_name": user["first_name"],
            "base_currency": user["base_currency"]}

@router.get("/me")
def me(user=Depends(get_current_user)):
    return {"user_id": user["user_id"], "email": user["email"],
            "first_name": user["first_name"], "base_currency": user["base_currency"],
            "birth_year": user.get("birth_year", 0),
            "goal": user.get("goal", ""),
            "risk_profile": user.get("risk_profile", "balanced"),
            "country": user.get("country", ""),
            "monthly_income": user.get("monthly_income", 0)}

from pydantic import BaseModel as BM

class UpdateSettingsRequest(BM):
    base_currency: str

@router.put("/settings")
def update_settings(req: UpdateSettingsRequest, user=Depends(get_current_user)):
    with __import__('database').get_db() as db:
        cur = db.cursor()
        cur.execute("UPDATE users SET base_currency=%s WHERE user_id=%s", 
                   (req.base_currency.upper(), user["user_id"]))
        db.commit()
    return {"ok": True, "base_currency": req.base_currency.upper()}

class OnboardingRequest(BM):
    first_name: str
    last_name: str = ""
    birth_year: int = 0
    country: str = ""
    base_currency: str = "EUR"
    monthly_income: float = 0
    monthly_expenses: float = 0
    current_savings: float = 0
    debt_amount: float = 0
    debt_interest: float = 0
    goal: str = ""
    risk_profile: str = "balanced"

@router.post("/onboarding")
def complete_onboarding(req: OnboardingRequest, user=Depends(get_current_user)):
    uid = user["user_id"]
    with __import__('database').get_db() as db:
        cur = db.cursor()
        cur.execute("""UPDATE users SET 
            first_name=%s, base_currency=%s,
            birth_year=%s, country=%s, goal=%s,
            risk_profile=%s, monthly_income=%s,
            monthly_expenses=%s, onboarding_done=true
            WHERE user_id=%s""",
            (req.first_name, req.base_currency,
             req.birth_year, req.country, req.goal,
             req.risk_profile, req.monthly_income,
             req.monthly_expenses, uid))
        db.commit()
    
    # Add initial asset if savings > 0
    if req.current_savings > 0:
        from database import upsert_asset
        upsert_asset(uid, 'დანაზოგი', req.current_savings, req.base_currency, req.current_savings, 1)
    
    # Add debt if exists
    if req.debt_amount > 0:
        from database import upsert_debt
        upsert_debt(uid, 'ვალი', req.debt_amount, req.base_currency, req.debt_amount, req.debt_interest)
    
    return {"ok": True, "profile": {
        "first_name": req.first_name,
        "monthly_income": req.monthly_income,
        "monthly_expenses": req.monthly_expenses,
        "debt_amount": req.debt_amount,
        "goal": req.goal,
    }}

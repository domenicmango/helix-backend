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
    user_id = create_user(req.email, hash_password(req.password), req.first_name, req.base_currency)
    token = create_token(user_id)
    return {"token": token, "user_id": user_id, "first_name": req.first_name}

@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_email(form.username)
    if not user or not verify_password(form.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Wrong email or password")
    token = create_token(user["user_id"])
    return {"access_token": token, "token_type": "bearer",
            "user_id": user["user_id"], "first_name": user["first_name"],
            "base_currency": user["base_currency"]}

@router.get("/me")
def me(user=Depends(get_current_user)):
    return {"user_id": user["user_id"], "email": user["email"],
            "first_name": user["first_name"], "base_currency": user["base_currency"],
            "plan": user["plan"]}

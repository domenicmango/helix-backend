from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
from database import init_db
from routes import auth, transactions, portfolio, coach, goals

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print("HELIX Backend running")
    yield

app = FastAPI(title="HELIX Wealth Engine", version="1.0.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.include_router(auth.router,         prefix="/auth",         tags=["Auth"])
app.include_router(transactions.router, prefix="/transactions", tags=["Transactions"])
app.include_router(portfolio.router,    prefix="/portfolio",    tags=["Portfolio"])
app.include_router(coach.router,        prefix="/coach",        tags=["Coach"])
app.include_router(goals.router,        prefix="/goals",        tags=["Goals"])

@app.get("/health")
def health():
    return {"status": "ok", "service": "HELIX"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import create_db_tables 

# Importer ALLE dine routers
from backend.routers import (
    authRouter,  # Ændret fra 'auth' til 'authRouter'
    categories, 
    transactions, 
    dashboard, 
    budgets,
    users, 
    accounts, 
    goals, 
    planned_transactions, 
    account_groups,
)

app = FastAPI(title="Personlig Finans Tracker API")

# --- CORS Konfiguration ---
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    create_db_tables()

@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Velkommen til din Personlige Finans Tracker API!"}

# Inkluder routers
app.include_router(authRouter.router)  # Ændret fra 'auth' til 'authRouter'
app.include_router(categories.router)
app.include_router(transactions.router)
app.include_router(dashboard.router)
app.include_router(budgets.router)
app.include_router(users.router)
app.include_router(accounts.router)
app.include_router(goals.router)
app.include_router(planned_transactions.router)
app.include_router(account_groups.router)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import create_db_tables 

# Importer ALLE dine routers
from backend.routers import (
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

# --- CORS Konfiguration (skal være FØRSTE middleware!) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    max_age=3600,
)
# --- Slut CORS Konfiguration ---

# Opret databasetabeller, når applikationen starter
@app.on_event("startup")
def startup_event():
    create_db_tables()
    # Her kan du indsætte standarddata (f.eks. standardkategorier)

@app.get("/", tags=["Root"]) # Tilføjet tag
def read_root():
    return {"message": "Velkommen til din Personlige Finans Tracker API!"}

# Inkluder ALLE dine routers
app.include_router(categories.router)
app.include_router(transactions.router)
app.include_router(dashboard.router)
app.include_router(budgets.router)

# De nye routers:
app.include_router(users.router)
app.include_router(accounts.router)
app.include_router(goals.router)
app.include_router(planned_transactions.router)
app.include_router(account_groups.router)
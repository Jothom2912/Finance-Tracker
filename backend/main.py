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

app = FastAPI(title="Personlig Finans Tracker API") # Tilføjet en titel

# --- CORS Konfiguration ---
origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
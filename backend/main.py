
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import create_db_tables # TransactionType er ikke nødvendig her mere

# Importer dine nye routers
from .routers import categories, transactions, dashboard

app = FastAPI()

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
    # Du kan stadig have din valgfrie kode til at indsætte standardkategorier her, hvis du ønsker

@app.get("/")
def read_root():
    return {"message": "Velkommen til din Personlige Finans Tracker API!"}

# Inkluder dine routers
app.include_router(categories.router)
app.include_router(transactions.router)
app.include_router(dashboard.router)
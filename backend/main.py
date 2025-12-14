from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# MIDLERTIDIGT DEAKTIVERET for at teste
# from strawberry.fastapi import GraphQLRouter
# from backend.database import create_db_tables
# from backend.graphql.schema import schema
import logging
import time

# Konfigurer logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Importer ALLE dine routers
from backend.routes import (
    users,  # VIGTIGT for registrering
    categories,
    transactions,
    dashboard,
    budgets,
    accounts,
    goals,
    planned_transactions,
    account_groups,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup logic
    logger.info("🚀 Starter FastAPI applikation...")
    logger.info("✅ Backend klar - database vil blive initialiseret ved første request")
    # Database init er fjernet fra startup for at undgå at backend hænger
    # Tabeller oprettes automatisk ved første database query
    yield
    # Shutdown logic (kan tilføjes senere hvis nødvendigt)
    logger.info("🛑 Stopper FastAPI applikation...")

app = FastAPI(title="Personlig Finans Tracker API", lifespan=lifespan)

# --- CORS Konfiguration (skal være FØRSTE middleware!) ---
logger.info("🔧 Konfigurerer CORS middleware...")
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
logger.info("✅ CORS middleware konfigureret")
# --- Slut CORS Konfiguration ---

# --- Request Logging Middleware ---
# MIDLERTIDIGT DEAKTIVERET for at teste om det forårsager problemer
# @app.middleware("http")
# async def log_requests(request: Request, call_next):
#     """Logger alle indkommende requests - MEGET SIMPLIFICERET"""
#     start_time = time.time()
#
#     # Log request - MEGET SIMPLIFICERET for at undgå at hænge
#     try:
#         logger.info(f"📥 {request.method} {request.url.path}")
#     except:
#         pass  # Hvis logging fejler, fortsæt alligevel
#
#     # Process request - IKKE læs body eller headers her, det kan hænge
#     try:
#         response = await call_next(request)
#         process_time = time.time() - start_time
#         logger.info(f"📤 {response.status_code} ({process_time:.2f}s)")
#         return response
#     except Exception as e:
#         process_time = time.time() - start_time
#         logger.error(f"❌ ERROR: {str(e)} ({process_time:.2f}s)")
#         raise
# --- Slut Request Logging Middleware ---

@app.get("/", tags=["Root"]) # Tilføjet tag
def read_root():
    logger.info("✅ Root endpoint kaldt")
    return {"message": "Velkommen til din Personlige Finans Tracker API!"}

@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint for at teste om backend kører"""
    print("=" * 60)
    print("🏥 HEALTH CHECK KALDT - PRINT STATEMENT")
    print("=" * 60)
    logger.info("=" * 60)
    logger.info("🏥 HEALTH CHECK KALDT - LOGGER")
    logger.info("=" * 60)
    return {"status": "ok", "message": "Backend kører!", "timestamp": time.time()}

# Inkluder ALLE dine routers
app.include_router(categories.router)
app.include_router(transactions.router)
app.include_router(dashboard.router)
app.include_router(budgets.router)
app.include_router(users.router)  # VIGTIGT for registrering
app.include_router(accounts.router)
app.include_router(goals.router)
app.include_router(planned_transactions.router)
app.include_router(account_groups.router)

# GraphQL endpoint - MIDLERTIDIGT DEAKTIVERET (kan aktiveres senere hvis nødvendigt)
# from strawberry.fastapi import GraphQLRouter
# from backend.graphql.schema import schema
# graphql_app = GraphQLRouter(schema)
# app.include_router(graphql_app, prefix="/graphql")
"""
FastAPI application entry point.
Registers all routers, handles startup/shutdown, and bootstraps the admin user.
"""
import logging
import bcrypt
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database.mongodb import connect_db, close_db, get_admins_col, get_billing_config_col, get_restaurant_settings_col
from backend.api import auth, menu, orders, billing, calls, admin
from backend.api.calls_webhook import router as twilio_router
from backend.api.voice_ws import router as voice_ws_router
from backend.models.billing import BillingConfig
from backend.models.restaurant import RestaurantSettings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("Starting Restaurant Voice Agent backend...")
    try:
        await connect_db()
        await _bootstrap_defaults()
        logger.info("MongoDB connected and defaults bootstrapped.")
    except Exception as e:
        logger.warning(
            f"MongoDB not reachable at startup ({e}). "
            "Server will start but DB-dependent routes will fail until MongoDB is available."
        )
    logger.info(f"Backend ready – {settings.APP_NAME} v{settings.APP_VERSION}")
    yield
    await close_db()
    logger.info("Backend shut down cleanly.")


async def _bootstrap_defaults():
    """Create admin user and default configs if they don't exist."""
    admins_col = get_admins_col()
    existing = await admins_col.find_one({"username": settings.ADMIN_USERNAME})
    if not existing:
        hashed = bcrypt.hashpw(settings.ADMIN_PASSWORD.encode(), bcrypt.gensalt()).decode()
        await admins_col.insert_one({
            "username": settings.ADMIN_USERNAME,
            "email": settings.ADMIN_EMAIL,
            "full_name": "Restaurant Admin",
            "hashed_password": hashed,
            "is_active": True,
        })
        logger.info(f"Default admin user '{settings.ADMIN_USERNAME}' created.")

    billing_col = get_billing_config_col()
    if await billing_col.count_documents({}) == 0:
        await billing_col.insert_one(BillingConfig().model_dump())
        logger.info("Default billing config created.")

    settings_col = get_restaurant_settings_col()
    if await settings_col.count_documents({}) == 0:
        await settings_col.insert_one(RestaurantSettings(name=settings.RESTAURANT_NAME).model_dump())
        logger.info("Default restaurant settings created.")


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered Restaurant Voice Ordering Agent – Backend API",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────

PREFIX = "/api"

app.include_router(auth.router, prefix=PREFIX)
app.include_router(menu.router, prefix=PREFIX)
app.include_router(orders.router, prefix=PREFIX)
app.include_router(billing.router, prefix=PREFIX)
app.include_router(calls.router, prefix=PREFIX)
app.include_router(admin.router, prefix=PREFIX)
app.include_router(twilio_router, prefix=PREFIX)   # Twilio webhooks
app.include_router(voice_ws_router, prefix=PREFIX) # Pipecat WebSocket


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}

import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import settings
from app.core.logger import logger
from app.core.database import async_engine, Base
from app.engine.worker_manager import worker_manager
from app.mock.services.seed import seed_local_dummy_data
from app.routers.shopify_router import router as shopify_mock_router
from app.routers.vietful_router import router as vietful_mock_router
from app.routers.worker_router import router as worker_api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan Context Manager
    Handles system initialization at startup and cleanup at shutdown.
    """
    logger.info("Starting up CDMS Platform Engine & Unified Mock Services...")

    # 1. Initialize all PostgreSQL database tables if they do not exist
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified/created successfully.")

    # 2. Seed 15 sample Shopify records and 15 sample Vietful records locally
    try:
        await seed_local_dummy_data()
    except Exception as seed_err:
        logger.error(f"Error seeding dummy data: {seed_err}")

    # 3. Restore and start all RUNNING workers from the database
    worker_manager.scheduler.start()
    try:
        await worker_manager.restore_running_workers_from_db()
    except Exception as restore_err:
        logger.error(f"Error restoring running workers from DB: {restore_err}")

    logger.info(f"CDMS System fully booted and listening on port {settings.PORT}!")

    try:
        yield  # The system is running and accepting requests
    finally:
        worker_manager.scheduler.shutdown(wait=False)
        logger.info("Shutting down CDMS Platform Engine...")


app = FastAPI(
    title=settings.APP_NAME,
    description="Multi-tenant Change Data Management System (CDMS) and Unified Mock Services (Shopify & Vietful)",
    version="1.0.0",
    lifespan=lifespan,
)

# Register API routers
app.include_router(shopify_mock_router)
app.include_router(vietful_mock_router)
app.include_router(worker_api_router)


@app.get("/", summary="Health Check API")
def root_health_check():
    return {
        "status": "ONLINE",
        "app_name": settings.APP_NAME,
        "message": "CDMS Engine & Mock Services are running smoothly!",
    }


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)

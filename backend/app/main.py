from fastapi import FastAPI, HTTPException

from app.database import check_db_connection
from app.routes.auth import router as auth_router
from app.routes.vehicles import router as vehicles_router

app = FastAPI(title="Car Dealership Inventory API")

app.include_router(auth_router)
app.include_router(vehicles_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/health/db")
def database_health_check():
    if not check_db_connection():
        raise HTTPException(
            status_code=503,
            detail="Database connection unavailable",
        )

    return {"status": "ok", "database": "connected"}
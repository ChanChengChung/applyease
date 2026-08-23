from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Depends

from app.db.migrations import migration_status
from app.db.session import Base, engine
from app.api.v1.router import api_router
from app.api.v1.auth import router as auth_router
from app.auth import get_current_user
from app.config import settings
from app import models  # noqa: F401 - register SQLAlchemy metadata

if settings.app_env == "test":
    Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="ApplyEase API",
    version=settings.app_version,
    docs_url=None if settings.app_env == "production" else "/docs",
    redoc_url=None if settings.app_env == "production" else "/redoc",
    openapi_url=None if settings.app_env == "production" else "/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(api_router, prefix="/api/v1", dependencies=[Depends(get_current_user)])


@app.middleware("http")
async def security_boundary(request: Request, call_next):
    def harden(response):
        response.headers["X-Content-Type-Options"] = "nosniff"

        response.headers["X-Frame-Options"] = "DENY"

        response.headers["Referrer-Policy"] = "no-referrer"

        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        response.headers["X-DNS-Prefetch-Control"] = "off"

        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        response.headers["Cache-Control"] = (
            "no-store"
            if request.url.path.startswith("/api/")
            else response.headers.get("Cache-Control", "no-cache")
        )

        if settings.app_env == "production":
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
            )

        return response

    host = (request.url.hostname or "").casefold()

    allowed = {
        item.strip().casefold() for item in settings.allowed_hosts.split(",") if item.strip()
    }

    if settings.app_env == "production" and host not in allowed:

        return harden(JSONResponse(status_code=400, content={"detail": "Invalid host header"}))
    forwarded_proto = (
        request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().casefold()
    )

    if settings.enforce_https and request.url.scheme != "https" and forwarded_proto != "https":

        return harden(JSONResponse(status_code=400, content={"detail": "HTTPS is required"}))
    response = await call_next(request)

    return harden(response)


@app.api_route("/health", methods=["GET", "HEAD"])
def health() -> dict[str, str]:

    return liveness()


@app.api_route("/health/live", methods=["GET", "HEAD"])
def liveness() -> dict[str, str]:

    return {"status": "ok"}


@app.api_route("/health/ready", methods=["GET", "HEAD"])
def readiness() -> dict[str, str | None]:

    try:

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        status = migration_status(engine)

    except SQLAlchemyError as exc:

        raise HTTPException(status_code=503, detail="Database is unavailable") from exc

    except Exception as exc:

        raise HTTPException(
            status_code=503, detail="Database migration status cannot be verified"
        ) from exc

    if not status["up_to_date"]:

        raise HTTPException(
            status_code=503,
            detail=f"Database migration required: current={status['current']}, head={status['head']}",
        )

    # Version is not secret; it proves the currently running release to an
    # operator using the same readiness endpoint as their monitor.
    return {
        "status": "ok",
        "database": "ok",
        "migration": status["current"],
        "version": settings.app_version,
    }

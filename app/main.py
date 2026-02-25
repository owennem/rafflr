from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.database import init_db, get_db
from app.config import get_settings
from app.services.scheduler import init_scheduler, shutdown_scheduler
from app.services.auth import get_current_user
from app.middleware.security import setup_security_middleware
from app.routers import (
    auth_router,
    users_router,
    listings_router,
    tickets_router,
    payments_router,
    admin_router
)
from app.models.listing import Listing, ListingStatus
from app.models.user import User

settings = get_settings()

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(
    title="Rafflr",
    description="A raffle-based marketplace",
    version="1.0.0",
    lifespan=lifespan
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Setup security middleware (CSRF, security headers)
setup_security_middleware(app, allowed_hosts=["localhost", "127.0.0.1"])

app.mount("/static", StaticFiles(directory="app/static"), name="static")

templates = Jinja2Templates(directory="app/templates")


# Add CSRF token helper to Jinja2 templates
def get_csrf_token(request: Request) -> str:
    """Get CSRF token from request state."""
    return getattr(request.state, "csrf_token", "")


templates.env.globals["get_csrf_token"] = get_csrf_token

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(listings_router)
app.include_router(tickets_router)
app.include_router(payments_router)
app.include_router(admin_router)


@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    featured_listings = db.query(Listing).filter(
        Listing.status == ListingStatus.ACTIVE
    ).order_by(Listing.created_at.desc()).limit(6).all()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user,
            "featured_listings": featured_listings,
            "stripe_key": settings.stripe_publishable_key
        }
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return templates.TemplateResponse(
        "errors/404.html",
        {"request": request},
        status_code=404
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    return templates.TemplateResponse(
        "errors/500.html",
        {"request": request},
        status_code=500
    )

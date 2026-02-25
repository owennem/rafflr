from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.listings import router as listings_router
from app.routers.tickets import router as tickets_router
from app.routers.payments import router as payments_router
from app.routers.admin import router as admin_router

__all__ = [
    "auth_router",
    "users_router",
    "listings_router",
    "tickets_router",
    "payments_router",
    "admin_router"
]

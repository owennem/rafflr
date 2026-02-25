from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.services.auth import get_current_admin
from app.models.user import User
from app.models.listing import Listing, ListingStatus
from app.models.ticket import Ticket
from app.models.transaction import Transaction, TransactionStatus

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    total_users = db.query(User).count()
    total_listings = db.query(Listing).count()
    active_listings = db.query(Listing).filter(Listing.status == ListingStatus.ACTIVE).count()
    total_transactions = db.query(Transaction).filter(
        Transaction.status == TransactionStatus.COMPLETED
    ).count()

    revenue = db.query(func.sum(Transaction.amount)).filter(
        Transaction.status == TransactionStatus.COMPLETED
    ).scalar() or 0

    recent_users = db.query(User).order_by(User.created_at.desc()).limit(5).all()
    recent_listings = db.query(Listing).order_by(Listing.created_at.desc()).limit(5).all()

    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "user": user,
            "total_users": total_users,
            "total_listings": total_listings,
            "active_listings": active_listings,
            "total_transactions": total_transactions,
            "revenue": revenue,
            "recent_users": recent_users,
            "recent_listings": recent_listings
        }
    )


@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    page: int = 1,
    search: str = None,
    user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    query = db.query(User)

    if search:
        query = query.filter(
            (User.username.ilike(f"%{search}%")) |
            (User.email.ilike(f"%{search}%"))
        )

    per_page = 20
    total = query.count()
    users = query.order_by(User.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse(
        "admin/users.html",
        {
            "request": request,
            "user": user,
            "users": users,
            "page": page,
            "total_pages": total_pages,
            "search": search
        }
    )


@router.post("/users/{user_id}/toggle-admin")
async def toggle_admin(
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    if target_user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot modify your own admin status")

    target_user.is_admin = not target_user.is_admin
    db.commit()

    return RedirectResponse(url="/admin/users", status_code=302)


@router.post("/users/{user_id}/verify")
async def verify_user(
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_user.is_verified = True
    target_user.verification_token = None
    db.commit()

    return RedirectResponse(url="/admin/users", status_code=302)


@router.get("/listings", response_class=HTMLResponse)
async def admin_listings(
    request: Request,
    page: int = 1,
    status: str = None,
    search: str = None,
    user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    query = db.query(Listing)

    if status:
        query = query.filter(Listing.status == ListingStatus(status))
    if search:
        query = query.filter(Listing.title.ilike(f"%{search}%"))

    per_page = 20
    total = query.count()
    listings = query.order_by(Listing.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse(
        "admin/listings.html",
        {
            "request": request,
            "user": user,
            "listings": listings,
            "page": page,
            "total_pages": total_pages,
            "status": status,
            "search": search
        }
    )


@router.get("/transactions", response_class=HTMLResponse)
async def admin_transactions(
    request: Request,
    page: int = 1,
    status: str = None,
    user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    query = db.query(Transaction)

    if status:
        query = query.filter(Transaction.status == TransactionStatus(status))

    per_page = 20
    total = query.count()
    transactions = query.order_by(Transaction.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse(
        "admin/transactions.html",
        {
            "request": request,
            "user": user,
            "transactions": transactions,
            "page": page,
            "total_pages": total_pages,
            "status": status
        }
    )

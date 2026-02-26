from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth import get_current_user, get_current_user_required
from app.models.user import User
from app.models.listing import Listing, ListingStatus
from app.models.ticket import Ticket
from app.templates_config import templates

router = APIRouter(tags=["users"])


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    user_listings = db.query(Listing).filter(Listing.seller_id == user.id).order_by(Listing.created_at.desc()).all()

    user_tickets = db.query(Ticket).filter(Ticket.buyer_id == user.id).order_by(Ticket.purchased_at.desc()).all()

    won_listings = db.query(Listing).filter(
        Listing.winner_id == user.id,
        Listing.status == ListingStatus.DRAWN
    ).all()

    active_listings = [l for l in user_listings if l.status == ListingStatus.ACTIVE]
    completed_listings = [l for l in user_listings if l.status == ListingStatus.DRAWN]

    return templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "user": user,
            "active_listings": active_listings,
            "completed_listings": completed_listings,
            "tickets": user_tickets,
            "won_listings": won_listings
        }
    )


@router.get("/dashboard/listings", response_class=HTMLResponse)
async def my_listings(
    request: Request,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    listings = db.query(Listing).filter(
        Listing.seller_id == user.id
    ).order_by(Listing.created_at.desc()).all()

    return templates.TemplateResponse(
        "dashboard/listings.html",
        {
            "request": request,
            "user": user,
            "listings": listings
        }
    )


@router.get("/dashboard/tickets", response_class=HTMLResponse)
async def my_tickets(
    request: Request,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    tickets = db.query(Ticket).filter(
        Ticket.buyer_id == user.id
    ).order_by(Ticket.purchased_at.desc()).all()

    active_tickets = [t for t in tickets if t.listing.status == ListingStatus.ACTIVE]
    past_tickets = [t for t in tickets if t.listing.status != ListingStatus.ACTIVE]

    return templates.TemplateResponse(
        "dashboard/tickets.html",
        {
            "request": request,
            "user": user,
            "active_tickets": active_tickets,
            "past_tickets": past_tickets
        }
    )


@router.get("/dashboard/wins", response_class=HTMLResponse)
async def my_wins(
    request: Request,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    won_listings = db.query(Listing).filter(
        Listing.winner_id == user.id,
        Listing.status == ListingStatus.DRAWN
    ).order_by(Listing.drawn_at.desc()).all()

    return templates.TemplateResponse(
        "dashboard/wins.html",
        {
            "request": request,
            "user": user,
            "won_listings": won_listings
        }
    )


@router.get("/profile", response_class=HTMLResponse)
async def profile(
    request: Request,
    user: User = Depends(get_current_user_required)
):
    return templates.TemplateResponse(
        "dashboard/profile.html",
        {
            "request": request,
            "user": user
        }
    )

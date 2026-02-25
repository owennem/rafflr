from fastapi import APIRouter, Depends, HTTPException, Request, Form, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.services.auth import get_current_user, get_current_user_required
from app.services.raffle import RaffleService
from app.services.email import EmailService
from app.services.scheduler import schedule_raffle_draw, cancel_scheduled_draw
from app.models.user import User
from app.models.listing import Listing, ListingStatus, DrawType
from app.models.ticket import Ticket

router = APIRouter(prefix="/listings", tags=["listings"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def browse_listings(
    request: Request,
    search: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sort: str = "newest",
    page: int = 1,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Listing).filter(Listing.status == ListingStatus.ACTIVE)

    if search:
        query = query.filter(Listing.title.ilike(f"%{search}%"))
    if min_price is not None:
        query = query.filter(Listing.ticket_price >= min_price)
    if max_price is not None:
        query = query.filter(Listing.ticket_price <= max_price)

    if sort == "newest":
        query = query.order_by(Listing.created_at.desc())
    elif sort == "oldest":
        query = query.order_by(Listing.created_at.asc())
    elif sort == "price_low":
        query = query.order_by(Listing.ticket_price.asc())
    elif sort == "price_high":
        query = query.order_by(Listing.ticket_price.desc())
    elif sort == "ending_soon":
        query = query.filter(Listing.deadline.isnot(None)).order_by(Listing.deadline.asc())

    per_page = 12
    total = query.count()
    listings = query.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page

    return templates.TemplateResponse(
        "listings/browse.html",
        {
            "request": request,
            "user": user,
            "listings": listings,
            "search": search,
            "min_price": min_price,
            "max_price": max_price,
            "sort": sort,
            "page": page,
            "total_pages": total_pages
        }
    )


@router.get("/create", response_class=HTMLResponse)
async def create_listing_page(
    request: Request,
    user: User = Depends(get_current_user_required)
):
    return templates.TemplateResponse(
        "listings/create.html",
        {"request": request, "user": user}
    )


@router.post("/create")
async def create_listing(
    request: Request,
    title: str = Form(...),
    description: str = Form(None),
    image_url: str = Form(None),
    ticket_price: float = Form(...),
    max_tickets: int = Form(...),
    draw_type: str = Form(...),
    ticket_limit: int = Form(None),
    deadline: str = Form(None),
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    draw_type_enum = DrawType(draw_type)

    deadline_dt = None
    if deadline:
        try:
            deadline_dt = datetime.fromisoformat(deadline)
        except ValueError:
            return templates.TemplateResponse(
                "listings/create.html",
                {"request": request, "user": user, "error": "Invalid deadline format"},
                status_code=400
            )

    if draw_type_enum in [DrawType.TICKET_LIMIT, DrawType.BOTH] and not ticket_limit:
        return templates.TemplateResponse(
            "listings/create.html",
            {"request": request, "user": user, "error": "Ticket limit required for selected draw type"},
            status_code=400
        )

    if draw_type_enum in [DrawType.DEADLINE, DrawType.BOTH] and not deadline_dt:
        return templates.TemplateResponse(
            "listings/create.html",
            {"request": request, "user": user, "error": "Deadline required for selected draw type"},
            status_code=400
        )

    listing = Listing(
        seller_id=user.id,
        title=title,
        description=description,
        image_url=image_url,
        ticket_price=ticket_price,
        max_tickets=max_tickets,
        draw_type=draw_type_enum,
        ticket_limit=ticket_limit,
        deadline=deadline_dt,
        status=ListingStatus.ACTIVE
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)

    if deadline_dt and draw_type_enum in [DrawType.DEADLINE, DrawType.BOTH]:
        schedule_raffle_draw(listing.id, deadline_dt)

    return RedirectResponse(url=f"/listings/{listing.id}", status_code=302)


@router.get("/{listing_id}", response_class=HTMLResponse)
async def view_listing(
    request: Request,
    listing_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    user_tickets = 0
    user_odds = 0.0
    if user:
        user_tickets = RaffleService.get_user_tickets_for_listing(db, user.id, listing_id)
        if listing.tickets_sold > 0:
            user_odds = RaffleService.get_winner_odds(db, user.id, listing_id)

    is_seller = user and user.id == listing.seller_id

    return templates.TemplateResponse(
        "listings/detail.html",
        {
            "request": request,
            "user": user,
            "listing": listing,
            "user_tickets": user_tickets,
            "user_odds": user_odds,
            "is_seller": is_seller
        }
    )


@router.get("/{listing_id}/edit", response_class=HTMLResponse)
async def edit_listing_page(
    request: Request,
    listing_id: int,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.seller_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    if listing.status != ListingStatus.ACTIVE:
        return RedirectResponse(url=f"/listings/{listing_id}", status_code=302)

    return templates.TemplateResponse(
        "listings/edit.html",
        {"request": request, "user": user, "listing": listing}
    )


@router.post("/{listing_id}/edit")
async def edit_listing(
    request: Request,
    listing_id: int,
    title: str = Form(...),
    description: str = Form(None),
    image_url: str = Form(None),
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.seller_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    if listing.status != ListingStatus.ACTIVE:
        return RedirectResponse(url=f"/listings/{listing_id}", status_code=302)

    listing.title = title
    listing.description = description
    listing.image_url = image_url
    db.commit()

    return RedirectResponse(url=f"/listings/{listing_id}", status_code=302)


@router.post("/{listing_id}/cancel")
async def cancel_listing(
    listing_id: int,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.seller_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    if listing.status != ListingStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Listing cannot be cancelled")

    cancel_scheduled_draw(listing_id)

    RaffleService.cancel_listing(db, listing_id)

    return RedirectResponse(url=f"/listings/{listing_id}", status_code=302)


@router.post("/{listing_id}/draw")
async def draw_raffle(
    listing_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.seller_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    if listing.status != ListingStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Raffle already drawn or cancelled")

    cancel_scheduled_draw(listing_id)

    winner = RaffleService.draw_raffle(db, listing_id)

    if winner:
        background_tasks.add_task(
            EmailService.send_winner_notification,
            winner.email,
            winner.username,
            listing.title,
            listing_id
        )
        background_tasks.add_task(
            EmailService.send_seller_draw_notification,
            user.email,
            user.username,
            listing.title,
            winner.username
        )

    return RedirectResponse(url=f"/listings/{listing_id}", status_code=302)

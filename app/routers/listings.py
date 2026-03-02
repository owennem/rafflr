from fastapi import APIRouter, Depends, HTTPException, Request, Form, Query, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from slowapi import Limiter

from app.database import get_db
from app.services.auth import get_current_user, get_current_user_required
from app.services.raffle import RaffleService
from app.services.email import EmailService
from app.services.scheduler import schedule_raffle_draw, cancel_scheduled_draw
from app.models.user import User
from app.models.listing import Listing, ListingStatus, DrawType
from app.models.ticket import Ticket
from app.templates_config import templates
from app.utils.validation import (
    validate_title,
    validate_description,
    validate_image_url,
    validate_price,
    validate_quantity,
    validate_search_query,
    validate_page,
    MAX_TITLE_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_URL_LENGTH,
    MAX_SEARCH_LENGTH,
)
from app.utils.rate_limit import get_rate_limit_key

router = APIRouter(prefix="/listings", tags=["listings"])
limiter = Limiter(key_func=get_rate_limit_key)


@router.get("", response_class=HTMLResponse)
async def browse_listings(
    request: Request,
    search: Optional[str] = Query(None, max_length=MAX_SEARCH_LENGTH),
    min_price: Optional[float] = Query(None, ge=0, le=1000000),
    max_price: Optional[float] = Query(None, ge=0, le=1000000),
    sort: str = Query("newest", regex="^(newest|oldest|price_low|price_high|ending_soon)$"),
    page: int = Query(1, ge=1, le=10000),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Validate and sanitize search query
    search = validate_search_query(search) if search else None
    page = validate_page(page)

    query = db.query(Listing).filter(Listing.status == ListingStatus.ACTIVE)

    if search:
        # Use parameterized query (SQLAlchemy handles this safely)
        search_pattern = f"%{search}%"
        query = query.filter(Listing.title.ilike(search_pattern))
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
@limiter.limit("10/minute")  # Max 10 listing creations per minute per IP
async def create_listing(
    request: Request,
    title: str = Form(..., max_length=MAX_TITLE_LENGTH),
    description: str = Form(None, max_length=MAX_DESCRIPTION_LENGTH),
    image_url: str = Form(None, max_length=MAX_URL_LENGTH),
    ticket_price: float = Form(...),
    max_tickets: int = Form(...),
    draw_type: str = Form(...),
    ticket_limit: int = Form(None),
    deadline: str = Form(None),
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    # Validate and sanitize inputs
    try:
        title = validate_title(title)
    except ValueError as e:
        return templates.TemplateResponse(
            "listings/create.html",
            {"request": request, "user": user, "error": str(e)},
            status_code=400
        )

    try:
        description = validate_description(description)
    except ValueError as e:
        return templates.TemplateResponse(
            "listings/create.html",
            {"request": request, "user": user, "error": str(e)},
            status_code=400
        )

    try:
        image_url = validate_image_url(image_url)
    except ValueError as e:
        return templates.TemplateResponse(
            "listings/create.html",
            {"request": request, "user": user, "error": str(e)},
            status_code=400
        )

    try:
        ticket_price = validate_price(ticket_price)
    except ValueError as e:
        return templates.TemplateResponse(
            "listings/create.html",
            {"request": request, "user": user, "error": str(e)},
            status_code=400
        )

    try:
        max_tickets = validate_quantity(max_tickets, max_quantity=100000)
    except ValueError as e:
        return templates.TemplateResponse(
            "listings/create.html",
            {"request": request, "user": user, "error": str(e)},
            status_code=400
        )

    # Validate draw type
    try:
        draw_type_enum = DrawType(draw_type)
    except ValueError:
        return templates.TemplateResponse(
            "listings/create.html",
            {"request": request, "user": user, "error": "Invalid draw type"},
            status_code=400
        )

    deadline_dt = None
    if deadline:
        try:
            deadline_dt = datetime.fromisoformat(deadline)
            # Ensure deadline is in the future
            if deadline_dt <= datetime.now():
                return templates.TemplateResponse(
                    "listings/create.html",
                    {"request": request, "user": user, "error": "Deadline must be in the future"},
                    status_code=400
                )
        except ValueError:
            return templates.TemplateResponse(
                "listings/create.html",
                {"request": request, "user": user, "error": "Invalid deadline format"},
                status_code=400
            )

    if ticket_limit is not None:
        try:
            ticket_limit = validate_quantity(ticket_limit, max_quantity=100000)
        except ValueError as e:
            return templates.TemplateResponse(
                "listings/create.html",
                {"request": request, "user": user, "error": str(e)},
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
@limiter.limit("20/minute")  # Max 20 edits per minute per IP
async def edit_listing(
    request: Request,
    listing_id: int,
    title: str = Form(..., max_length=MAX_TITLE_LENGTH),
    description: str = Form(None, max_length=MAX_DESCRIPTION_LENGTH),
    image_url: str = Form(None, max_length=MAX_URL_LENGTH),
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

    # Validate and sanitize inputs
    try:
        title = validate_title(title)
    except ValueError as e:
        return templates.TemplateResponse(
            "listings/edit.html",
            {"request": request, "user": user, "listing": listing, "error": str(e)},
            status_code=400
        )

    try:
        description = validate_description(description)
    except ValueError as e:
        return templates.TemplateResponse(
            "listings/edit.html",
            {"request": request, "user": user, "listing": listing, "error": str(e)},
            status_code=400
        )

    try:
        image_url = validate_image_url(image_url)
    except ValueError as e:
        return templates.TemplateResponse(
            "listings/edit.html",
            {"request": request, "user": user, "listing": listing, "error": str(e)},
            status_code=400
        )

    listing.title = title
    listing.description = description
    listing.image_url = image_url
    db.commit()

    return RedirectResponse(url=f"/listings/{listing_id}", status_code=302)


@router.post("/{listing_id}/cancel")
@limiter.limit("10/minute")  # Max 10 cancellations per minute per IP
async def cancel_listing(
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
        raise HTTPException(status_code=400, detail="Listing cannot be cancelled")

    cancel_scheduled_draw(listing_id)

    RaffleService.cancel_listing(db, listing_id)

    return RedirectResponse(url=f"/listings/{listing_id}", status_code=302)


@router.post("/{listing_id}/draw")
@limiter.limit("10/minute")  # Max 10 draws per minute per IP
async def draw_raffle(
    request: Request,
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

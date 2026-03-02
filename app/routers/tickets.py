from fastapi import APIRouter, Depends, HTTPException, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from slowapi import Limiter

from app.database import get_db
from app.config import get_settings
from app.services.auth import get_current_user_required
from app.services.payment import PaymentService
from app.models.user import User
from app.models.listing import Listing, ListingStatus
from app.templates_config import templates
from app.utils.validation import validate_quantity
from app.utils.rate_limit import get_rate_limit_key

router = APIRouter(prefix="/tickets", tags=["tickets"])
settings = get_settings()
limiter = Limiter(key_func=get_rate_limit_key)


@router.post("/purchase")
@limiter.limit("30/minute")  # Max 30 purchase attempts per minute per IP
async def purchase_tickets(
    request: Request,
    listing_id: int = Form(...),
    quantity: int = Form(...),
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    # Validate listing_id is a positive integer
    if listing_id < 1:
        raise HTTPException(status_code=400, detail="Invalid listing ID")

    # Validate and sanitize quantity
    try:
        quantity = validate_quantity(quantity, max_quantity=1000)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.status != ListingStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Raffle is not active")

    if listing.seller_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot purchase tickets for your own listing")

    available_tickets = listing.max_tickets - listing.tickets_sold
    if quantity > available_tickets:
        raise HTTPException(status_code=400, detail=f"Only {available_tickets} tickets available")

    if listing.ticket_limit:
        remaining_to_limit = listing.ticket_limit - listing.tickets_sold
        if quantity > remaining_to_limit:
            raise HTTPException(
                status_code=400,
                detail=f"Only {remaining_to_limit} tickets remaining until draw"
            )

    success_url = f"{settings.frontend_url}/tickets/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{settings.frontend_url}/listings/{listing_id}"

    try:
        checkout_url = PaymentService.create_checkout_session(
            db=db,
            user=user,
            listing=listing,
            quantity=quantity,
            success_url=success_url,
            cancel_url=cancel_url
        )
        return RedirectResponse(url=checkout_url, status_code=302)
    except Exception as e:
        return templates.TemplateResponse(
            "listings/detail.html",
            {
                "request": request,
                "user": user,
                "listing": listing,
                "error": str(e)
            },
            status_code=400
        )


@router.get("/success", response_class=HTMLResponse)
async def purchase_success(
    request: Request,
    session_id: str = Query(..., max_length=256),
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    # Sanitize session_id
    session_id = session_id.strip()[:256]

    # Basic validation - session IDs should be alphanumeric with underscores
    if not session_id or not all(c.isalnum() or c in "_-" for c in session_id):
        return templates.TemplateResponse(
            "tickets/error.html",
            {"request": request, "user": user, "error": "Invalid session ID"}
        )

    transaction = PaymentService.get_transaction_by_session_id(db, session_id)

    if not transaction:
        return templates.TemplateResponse(
            "tickets/error.html",
            {"request": request, "user": user, "error": "Transaction not found"}
        )

    return templates.TemplateResponse(
        "tickets/success.html",
        {"request": request, "user": user, "transaction": transaction}
    )

from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings
from app.services.auth import get_current_user_required
from app.services.payment import PaymentService
from app.models.user import User
from app.models.listing import Listing, ListingStatus

router = APIRouter(prefix="/tickets", tags=["tickets"])
templates = Jinja2Templates(directory="app/templates")
settings = get_settings()


@router.post("/purchase")
async def purchase_tickets(
    request: Request,
    listing_id: int = Form(...),
    quantity: int = Form(...),
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.status != ListingStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Raffle is not active")

    if listing.seller_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot purchase tickets for your own listing")

    if quantity < 1:
        raise HTTPException(status_code=400, detail="Quantity must be at least 1")

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
    session_id: str,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
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

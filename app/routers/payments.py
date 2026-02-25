from fastapi import APIRouter, Depends, HTTPException, Request, Header, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.payment import PaymentService
from app.services.email import EmailService
from app.models.transaction import Transaction, TransactionStatus
from app.models.ticket import Ticket
from app.models.listing import Listing

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_db)
):
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing signature")

    payload = await request.body()

    try:
        event = PaymentService.verify_webhook_signature(payload, stripe_signature)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        success = PaymentService.handle_checkout_completed(db, session)

        if success:
            metadata = session.get("metadata", {})
            transaction_id = int(metadata.get("transaction_id"))
            listing_id = int(metadata.get("listing_id"))
            user_id = int(metadata.get("user_id"))
            quantity = int(metadata.get("quantity"))

            transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
            listing = db.query(Listing).filter(Listing.id == listing_id).first()

            if transaction and listing and transaction.user:
                background_tasks.add_task(
                    EmailService.send_purchase_confirmation,
                    transaction.user.email,
                    transaction.user.username,
                    listing.title,
                    quantity,
                    transaction.amount
                )

    return {"status": "success"}

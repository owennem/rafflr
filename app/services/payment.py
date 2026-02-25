import stripe
from typing import Optional
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.listing import Listing
from app.models.ticket import Ticket
from app.models.transaction import Transaction, TransactionStatus
from app.models.user import User
from app.services.raffle import RaffleService

settings = get_settings()
stripe.api_key = settings.stripe_secret_key


class PaymentService:
    @staticmethod
    def create_checkout_session(
        db: Session,
        user: User,
        listing: Listing,
        quantity: int,
        success_url: str,
        cancel_url: str
    ) -> Optional[str]:
        """
        Create a Stripe checkout session for purchasing raffle tickets.
        Returns the checkout session URL.
        """
        amount = int(listing.ticket_price * quantity * 100)

        transaction = Transaction(
            user_id=user.id,
            amount=listing.ticket_price * quantity,
            status=TransactionStatus.PENDING
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"Raffle Tickets: {listing.title}",
                            "description": f"{quantity} ticket(s) for {listing.title}"
                        },
                        "unit_amount": int(listing.ticket_price * 100)
                    },
                    "quantity": quantity
                }],
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "transaction_id": str(transaction.id),
                    "listing_id": str(listing.id),
                    "user_id": str(user.id),
                    "quantity": str(quantity)
                }
            )

            transaction.stripe_session_id = session.id
            db.commit()

            return session.url

        except stripe.error.StripeError as e:
            transaction.status = TransactionStatus.REFUNDED
            db.commit()
            raise Exception(f"Stripe error: {str(e)}")

    @staticmethod
    def handle_checkout_completed(db: Session, session: dict) -> bool:
        """
        Handle successful checkout completion from Stripe webhook.
        Creates tickets and updates transaction status.
        """
        metadata = session.get("metadata", {})
        transaction_id = int(metadata.get("transaction_id"))
        listing_id = int(metadata.get("listing_id"))
        user_id = int(metadata.get("user_id"))
        quantity = int(metadata.get("quantity"))

        transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
        if not transaction:
            return False

        if transaction.status == TransactionStatus.COMPLETED:
            return True

        transaction.stripe_payment_id = session.get("payment_intent")
        transaction.status = TransactionStatus.COMPLETED
        db.commit()

        ticket = Ticket(
            listing_id=listing_id,
            buyer_id=user_id,
            quantity=quantity,
            transaction_id=transaction_id
        )
        db.add(ticket)

        listing = db.query(Listing).filter(Listing.id == listing_id).first()
        if listing:
            listing.tickets_sold += quantity
            db.commit()

            RaffleService.check_auto_draw_ticket_limit(db, listing_id)

        return True

    @staticmethod
    def verify_webhook_signature(payload: bytes, signature: str) -> dict:
        """Verify Stripe webhook signature and return the event."""
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                settings.stripe_webhook_secret
            )
            return event
        except stripe.error.SignatureVerificationError:
            raise ValueError("Invalid signature")

    @staticmethod
    def get_transaction_by_session_id(db: Session, session_id: str) -> Optional[Transaction]:
        """Get a transaction by its Stripe session ID."""
        return db.query(Transaction).filter(
            Transaction.stripe_session_id == session_id
        ).first()

    @staticmethod
    def refund_transaction(db: Session, transaction_id: int) -> bool:
        """Refund a transaction via Stripe."""
        transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()

        if not transaction or not transaction.stripe_payment_id:
            return False

        try:
            stripe.Refund.create(payment_intent=transaction.stripe_payment_id)
            transaction.status = TransactionStatus.REFUNDED
            db.commit()
            return True
        except stripe.error.StripeError:
            return False

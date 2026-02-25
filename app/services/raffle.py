import random
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.models.listing import Listing, ListingStatus, DrawType
from app.models.ticket import Ticket
from app.models.user import User


class RaffleService:
    @staticmethod
    def select_winner(db: Session, listing_id: int) -> Optional[int]:
        """
        Select a winner for the raffle.
        Each ticket is an entry - more tickets = higher chance of winning.
        Returns the winner's user_id or None if no tickets exist.
        """
        tickets = db.query(Ticket).filter(Ticket.listing_id == listing_id).all()

        if not tickets:
            return None

        entries = []
        for ticket in tickets:
            entries.extend([ticket.buyer_id] * ticket.quantity)

        winner_id = random.choice(entries)
        return winner_id

    @staticmethod
    def draw_raffle(db: Session, listing_id: int) -> Optional[User]:
        """
        Perform the raffle draw for a listing.
        Updates the listing status and winner.
        Returns the winner User object or None.
        """
        listing = db.query(Listing).filter(Listing.id == listing_id).first()

        if not listing:
            return None

        if listing.status != ListingStatus.ACTIVE:
            return None

        winner_id = RaffleService.select_winner(db, listing_id)

        if winner_id is None:
            listing.status = ListingStatus.CANCELLED
            db.commit()
            return None

        listing.winner_id = winner_id
        listing.status = ListingStatus.DRAWN
        listing.drawn_at = datetime.utcnow()
        db.commit()

        winner = db.query(User).filter(User.id == winner_id).first()
        return winner

    @staticmethod
    def check_auto_draw_ticket_limit(db: Session, listing_id: int) -> bool:
        """
        Check if a listing should auto-draw based on ticket limit.
        Returns True if draw was triggered.
        """
        listing = db.query(Listing).filter(Listing.id == listing_id).first()

        if not listing or listing.status != ListingStatus.ACTIVE:
            return False

        if listing.draw_type not in [DrawType.TICKET_LIMIT, DrawType.BOTH]:
            return False

        if listing.ticket_limit and listing.tickets_sold >= listing.ticket_limit:
            RaffleService.draw_raffle(db, listing_id)
            return True

        return False

    @staticmethod
    def check_auto_draw_deadline(db: Session, listing_id: int) -> bool:
        """
        Check if a listing should auto-draw based on deadline.
        Returns True if draw was triggered.
        """
        listing = db.query(Listing).filter(Listing.id == listing_id).first()

        if not listing or listing.status != ListingStatus.ACTIVE:
            return False

        if listing.draw_type not in [DrawType.DEADLINE, DrawType.BOTH]:
            return False

        if listing.deadline and datetime.utcnow() >= listing.deadline:
            RaffleService.draw_raffle(db, listing_id)
            return True

        return False

    @staticmethod
    def get_user_tickets_for_listing(db: Session, user_id: int, listing_id: int) -> int:
        """Get total number of tickets a user has for a specific listing."""
        tickets = db.query(Ticket).filter(
            Ticket.buyer_id == user_id,
            Ticket.listing_id == listing_id
        ).all()
        return sum(t.quantity for t in tickets)

    @staticmethod
    def get_winner_odds(db: Session, user_id: int, listing_id: int) -> float:
        """Calculate user's odds of winning based on their ticket count."""
        listing = db.query(Listing).filter(Listing.id == listing_id).first()
        if not listing or listing.tickets_sold == 0:
            return 0.0

        user_tickets = RaffleService.get_user_tickets_for_listing(db, user_id, listing_id)
        return (user_tickets / listing.tickets_sold) * 100

    @staticmethod
    def cancel_listing(db: Session, listing_id: int) -> bool:
        """Cancel a listing. Can only cancel active listings."""
        listing = db.query(Listing).filter(Listing.id == listing_id).first()

        if not listing or listing.status != ListingStatus.ACTIVE:
            return False

        listing.status = ListingStatus.CANCELLED
        db.commit()
        return True

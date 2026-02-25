from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from datetime import datetime
import logging
import asyncio

from app.config import get_settings
from app.database import SessionLocal
from app.services.raffle import RaffleService
from app.services.email import EmailService
from app.models.listing import Listing, ListingStatus

settings = get_settings()
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

jobstores = {
    'default': SQLAlchemyJobStore(url=settings.database_url)
}


def init_scheduler():
    """Initialize the scheduler with job stores."""
    scheduler.configure(jobstores=jobstores)
    scheduler.start()
    logger.info("Scheduler started")


def shutdown_scheduler():
    """Shutdown the scheduler."""
    scheduler.shutdown()
    logger.info("Scheduler shutdown")


async def execute_raffle_draw(listing_id: int):
    """Execute the raffle draw for a listing."""
    db = SessionLocal()
    try:
        listing = db.query(Listing).filter(Listing.id == listing_id).first()
        if not listing or listing.status != ListingStatus.ACTIVE:
            logger.info(f"Listing {listing_id} not eligible for draw")
            return

        winner = RaffleService.draw_raffle(db, listing_id)

        if winner:
            await EmailService.send_winner_notification(
                winner.email,
                winner.username,
                listing.title,
                listing_id
            )

            seller = listing.seller
            if seller:
                await EmailService.send_seller_draw_notification(
                    seller.email,
                    seller.username,
                    listing.title,
                    winner.username
                )

            logger.info(f"Raffle drawn for listing {listing_id}, winner: {winner.username}")
        else:
            logger.info(f"No winner for listing {listing_id} (no tickets)")

    except Exception as e:
        logger.error(f"Error executing raffle draw for listing {listing_id}: {e}")
    finally:
        db.close()


def schedule_raffle_draw(listing_id: int, draw_time: datetime):
    """Schedule a raffle draw for a specific time."""
    job_id = f"raffle_draw_{listing_id}"

    existing_job = scheduler.get_job(job_id)
    if existing_job:
        scheduler.remove_job(job_id)

    def run_async_draw():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(execute_raffle_draw(listing_id))
        finally:
            loop.close()

    scheduler.add_job(
        run_async_draw,
        'date',
        run_date=draw_time,
        id=job_id,
        replace_existing=True
    )
    logger.info(f"Scheduled raffle draw for listing {listing_id} at {draw_time}")


def cancel_scheduled_draw(listing_id: int):
    """Cancel a scheduled raffle draw."""
    job_id = f"raffle_draw_{listing_id}"
    try:
        scheduler.remove_job(job_id)
        logger.info(f"Cancelled scheduled draw for listing {listing_id}")
    except Exception:
        pass


def reschedule_raffle_draw(listing_id: int, new_draw_time: datetime):
    """Reschedule a raffle draw to a new time."""
    cancel_scheduled_draw(listing_id)
    schedule_raffle_draw(listing_id, new_draw_time)

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from slowapi import Limiter

from app.database import get_db
from app.services.auth import get_current_user, get_current_user_required
from app.models.user import User
from app.models.listing import Listing, ListingStatus
from app.models.favorite import Favorite
from app.templates_config import templates
from app.utils.rate_limit import get_rate_limit_key

router = APIRouter(prefix="/favorites", tags=["favorites"])
limiter = Limiter(key_func=get_rate_limit_key)


@router.post("/{listing_id}/toggle")
@limiter.limit("60/minute")
async def toggle_favorite(
    request: Request,
    listing_id: int,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """Toggle favorite status for a listing."""
    # Check listing exists
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Check if already favorited
    existing = db.query(Favorite).filter(
        Favorite.user_id == user.id,
        Favorite.listing_id == listing_id
    ).first()

    if existing:
        # Remove favorite
        db.delete(existing)
        db.commit()
        return JSONResponse({"status": "removed", "favorited": False})
    else:
        # Add favorite
        favorite = Favorite(user_id=user.id, listing_id=listing_id)
        db.add(favorite)
        db.commit()
        return JSONResponse({"status": "added", "favorited": True})


@router.get("", response_class=HTMLResponse)
async def favorites_page(
    request: Request,
    user: User = Depends(get_current_user_required),
    db: Session = Depends(get_db)
):
    """Display user's favorited listings."""
    # Get all favorites with their listings
    favorites = db.query(Favorite).filter(
        Favorite.user_id == user.id
    ).order_by(Favorite.created_at.desc()).all()

    # Get the listing objects
    favorite_listings = []
    for fav in favorites:
        listing = db.query(Listing).filter(Listing.id == fav.listing_id).first()
        if listing:
            favorite_listings.append(listing)

    return templates.TemplateResponse(
        "dashboard/favorites.html",
        {
            "request": request,
            "user": user,
            "listings": favorite_listings,
            "favorite_ids": set(f.listing_id for f in favorites)
        }
    )


def get_user_favorite_ids(db: Session, user_id: int) -> set:
    """Helper function to get a set of listing IDs that a user has favorited."""
    favorites = db.query(Favorite.listing_id).filter(
        Favorite.user_id == user_id
    ).all()
    return set(f.listing_id for f in favorites)

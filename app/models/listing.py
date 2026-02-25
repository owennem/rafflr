from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class DrawType(str, enum.Enum):
    TICKET_LIMIT = "ticket_limit"
    DEADLINE = "deadline"
    BOTH = "both"


class ListingStatus(str, enum.Enum):
    ACTIVE = "active"
    DRAWN = "drawn"
    CANCELLED = "cancelled"


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(String(2000), nullable=True)
    image_url = Column(String(500), nullable=True)
    ticket_price = Column(Float, nullable=False)
    max_tickets = Column(Integer, nullable=False)
    tickets_sold = Column(Integer, default=0)
    draw_type = Column(Enum(DrawType), default=DrawType.TICKET_LIMIT)
    ticket_limit = Column(Integer, nullable=True)
    deadline = Column(DateTime, nullable=True)
    status = Column(Enum(ListingStatus), default=ListingStatus.ACTIVE)
    winner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    drawn_at = Column(DateTime, nullable=True)

    seller = relationship("User", back_populates="listings", foreign_keys=[seller_id])
    winner = relationship("User", back_populates="won_listings", foreign_keys=[winner_id])
    tickets = relationship("Ticket", back_populates="listing")

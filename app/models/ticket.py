from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    purchased_at = Column(DateTime, server_default=func.now())
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)

    listing = relationship("Listing", back_populates="tickets")
    buyer = relationship("User", back_populates="tickets")
    transaction = relationship("Transaction", back_populates="tickets")

from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    verification_token = Column(String(255), nullable=True)
    reset_token = Column(String(255), nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)
    # 2FA fields
    twofa_code = Column(String(6), nullable=True)
    twofa_code_expires = Column(DateTime, nullable=True)
    twofa_pending_action = Column(String(20), nullable=True)  # 'login' or 'registration'
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    listings = relationship("Listing", back_populates="seller", foreign_keys="Listing.seller_id")
    won_listings = relationship("Listing", back_populates="winner", foreign_keys="Listing.winner_id")
    tickets = relationship("Ticket", back_populates="buyer")
    transactions = relationship("Transaction", back_populates="user")
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class TicketCreate(BaseModel):
    listing_id: int
    quantity: int = 1


class TicketPurchase(BaseModel):
    listing_id: int
    quantity: int = 1


class ListingInfo(BaseModel):
    id: int
    title: str
    ticket_price: float
    status: str

    class Config:
        from_attributes = True


class BuyerInfo(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True


class TicketResponse(BaseModel):
    id: int
    listing_id: int
    buyer_id: int
    quantity: int
    purchased_at: datetime
    transaction_id: Optional[int]
    listing: Optional[ListingInfo] = None
    buyer: Optional[BuyerInfo] = None

    class Config:
        from_attributes = True


class TransactionResponse(BaseModel):
    id: int
    user_id: int
    amount: float
    stripe_payment_id: Optional[str]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

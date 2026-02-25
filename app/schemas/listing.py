from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.models.listing import DrawType, ListingStatus


class ListingCreate(BaseModel):
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    ticket_price: float
    max_tickets: int
    draw_type: DrawType = DrawType.TICKET_LIMIT
    ticket_limit: Optional[int] = None
    deadline: Optional[datetime] = None


class ListingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    ticket_price: Optional[float] = None
    max_tickets: Optional[int] = None
    draw_type: Optional[DrawType] = None
    ticket_limit: Optional[int] = None
    deadline: Optional[datetime] = None


class SellerInfo(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True


class WinnerInfo(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True


class ListingResponse(BaseModel):
    id: int
    seller_id: int
    title: str
    description: Optional[str]
    image_url: Optional[str]
    ticket_price: float
    max_tickets: int
    tickets_sold: int
    draw_type: DrawType
    ticket_limit: Optional[int]
    deadline: Optional[datetime]
    status: ListingStatus
    winner_id: Optional[int]
    created_at: datetime
    drawn_at: Optional[datetime]
    seller: Optional[SellerInfo] = None
    winner: Optional[WinnerInfo] = None

    class Config:
        from_attributes = True

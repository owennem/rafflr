from pydantic import BaseModel, field_validator, Field
from datetime import datetime
from typing import Optional
from app.models.listing import DrawType, ListingStatus
from app.utils.validation import (
    validate_title,
    validate_description,
    validate_image_url,
    validate_price,
    validate_quantity,
    MAX_TITLE_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_URL_LENGTH,
)


class ListingCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=MAX_TITLE_LENGTH)
    description: Optional[str] = Field(None, max_length=MAX_DESCRIPTION_LENGTH)
    image_url: Optional[str] = Field(None, max_length=MAX_URL_LENGTH)
    ticket_price: float = Field(..., gt=0, le=1000000)
    max_tickets: int = Field(..., ge=1, le=100000)
    draw_type: DrawType = DrawType.TICKET_LIMIT
    ticket_limit: Optional[int] = Field(None, ge=1, le=100000)
    deadline: Optional[datetime] = None

    @field_validator("title")
    @classmethod
    def validate_title_field(cls, v: str) -> str:
        return validate_title(v)

    @field_validator("description")
    @classmethod
    def validate_description_field(cls, v: Optional[str]) -> Optional[str]:
        return validate_description(v)

    @field_validator("image_url")
    @classmethod
    def validate_image_url_field(cls, v: Optional[str]) -> Optional[str]:
        return validate_image_url(v)

    @field_validator("ticket_price")
    @classmethod
    def validate_price_field(cls, v: float) -> float:
        return validate_price(v)


class ListingUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=MAX_TITLE_LENGTH)
    description: Optional[str] = Field(None, max_length=MAX_DESCRIPTION_LENGTH)
    image_url: Optional[str] = Field(None, max_length=MAX_URL_LENGTH)
    ticket_price: Optional[float] = Field(None, gt=0, le=1000000)
    max_tickets: Optional[int] = Field(None, ge=1, le=100000)
    draw_type: Optional[DrawType] = None
    ticket_limit: Optional[int] = Field(None, ge=1, le=100000)
    deadline: Optional[datetime] = None

    @field_validator("title")
    @classmethod
    def validate_title_field(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_title(v)

    @field_validator("description")
    @classmethod
    def validate_description_field(cls, v: Optional[str]) -> Optional[str]:
        return validate_description(v)

    @field_validator("image_url")
    @classmethod
    def validate_image_url_field(cls, v: Optional[str]) -> Optional[str]:
        return validate_image_url(v)

    @field_validator("ticket_price")
    @classmethod
    def validate_price_field(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        return validate_price(v)


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

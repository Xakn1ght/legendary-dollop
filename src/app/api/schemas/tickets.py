import re
from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

# =============================================================================
# Ticket Schemas
# =============================================================================

class TicketCategory(str):
    """Valid ticket categories"""
    CONNECTION = "connection"
    MONEY = "money"
    OTHER = "other"


class TicketCreateRequest(BaseModel):
    """Schema for creating a new support ticket"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    subject: str = Field(
        ...,
        min_length=3,
        max_length=60,
        description="Short subject/title for the ticket",
    )
    category: Literal["connection", "money", "other"] = Field(
        ..., 
        description="Ticket category"
    )
    message: str = Field(
        ..., 
        min_length=10, 
        max_length=2000,
        description="Initial message for the ticket"
    )
    subscription_id: Optional[int] = Field(
        default=None, 
        ge=1,
        description="Optional subscription ID to link to ticket"
    )
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 10:
            raise ValueError('Message must be at least 10 characters long')
        if len(v) > 2000:
            raise ValueError('Message cannot exceed 2000 characters')
        return v


class TicketReplyRequest(BaseModel):
    """Schema for replying to a ticket"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    message: str = Field(
        ..., 
        min_length=1, 
        max_length=2000,
        description="Reply message"
    )
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Message cannot be empty')
        if len(v) > 2000:
            raise ValueError('Message cannot exceed 2000 characters')
        return v


class TicketMessageResponse(BaseModel):
    """Schema for ticket message in responses"""
    id: int
    message: str
    from_admin: bool
    created_at: Optional[str] = None


class TicketResponse(BaseModel):
    """Schema for ticket in responses"""
    id: int
    category: str
    status: str
    priority: str
    subscription_id: Optional[int] = None
    subscription_username: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_message: Optional[str] = None
    messages: Optional[List[TicketMessageResponse]] = None

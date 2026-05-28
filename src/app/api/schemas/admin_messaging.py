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


class AdminTicketReplyRequest(BaseModel):
    """Schema for admin replying to a ticket"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    message: str = Field(
        ..., 
        min_length=1, 
        max_length=4000,
        description="Reply message"
    )
    
    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Message cannot be empty')
        return v


# =============================================================================
# Admin Notification Schemas
# =============================================================================

class AdminSendNotificationRequest(BaseModel):
    """Schema for sending notifications to users"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    title: str = Field(
        ..., 
        min_length=1, 
        max_length=100,
        description="Notification title"
    )
    message: str = Field(
        ..., 
        min_length=1, 
        max_length=1000,
        description="Notification message"
    )
    target: Literal["all", "specific"] = Field(
        default="all",
        description="Target audience"
    )
    send_to_webapp: bool = Field(default=True, description="Send to webapp")
    send_to_bot: bool = Field(default=False, description="Send via Telegram bot")
    user_ids: Optional[List[int]] = Field(
        default=None,
        max_length=1000,
        description="User IDs for specific targeting"
    )
    
    @model_validator(mode='after')
    def validate_target_users(self):
        if self.target == "specific" and not self.user_ids:
            raise ValueError('user_ids is required when target is "specific"')
        return self


class AdminBroadcastRequest(BaseModel):
    """Schema for broadcasting a message to all users"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    message: str = Field(
        ..., 
        min_length=1, 
        max_length=4000,
        description="Broadcast message"
    )

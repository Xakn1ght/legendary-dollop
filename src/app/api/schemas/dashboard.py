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


class DashboardLoginRequest(BaseModel):
    """Schema for dashboard login"""
    init_data: str = Field(
        ..., 
        min_length=10,
        max_length=10000,
        description="Telegram WebApp init data"
    )


class DashboardMarkNotificationReadRequest(BaseModel):
    """Schema for marking notifications as read"""
    notification_id: Optional[int] = Field(
        default=None, 
        ge=1,
        description="Notification ID (null to mark all as read)"
    )


class DashboardPreferencesPatchRequest(BaseModel):
    """Schema for updating per-user dashboard preferences"""
    theme: Optional[Literal["light", "dark"]] = Field(default=None, description="Dashboard theme")
    lang: Optional[Literal["en", "fa"]] = Field(default=None, description="Dashboard language")
    current_sub_id: Optional[str] = Field(default=None, max_length=32, description="Last selected subscription id")
    default_sub_id: Optional[str] = Field(default=None, max_length=32, description="Favorite/default subscription id")
    auto_claim: Optional[bool] = Field(default=None, description="Auto-claim completed challenges (VIP feature)")
    voucher_auto_sub_id: Optional[str] = Field(default=None, max_length=32, description="Default subscription id for auto-redeeming vouchers (VIP feature)")
    accent: Optional[Literal["red", "cyan", "emerald", "violet", "amber", "champion", "legend"]] = Field(default=None, description="Dashboard accent/highlight color")
    welcome_shown: Optional[bool] = Field(default=None, description="Whether the welcome screen has been shown")


# =============================================================================
# Subscription Management Schemas
# =============================================================================

class AddSubscriptionRequest(BaseModel):
    """Schema for adding a subscription"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    url: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Subscription link (URL or base64-encoded URL)"
    )
    username: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Marzban username"
    )
    token: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Subscription token"
    )
    
    @model_validator(mode='after')
    def check_at_least_one(self):
        if not self.url and not self.username and not self.token:
            raise ValueError('Either url, username, or token must be provided')
        return self

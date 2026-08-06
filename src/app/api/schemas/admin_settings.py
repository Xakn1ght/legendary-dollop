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


class PlanSchema(BaseModel):
    """Schema for a subscription plan"""
    name: str = Field(..., min_length=1, max_length=50)
    price: int = Field(..., ge=0, le=100_000_000)
    gb: int = Field(..., ge=1, le=10000)
    days: int = Field(default=30, ge=1, le=365)


class AdminUpdatePlansRequest(BaseModel):
    """Schema for updating subscription plans"""
    plans: List[PlanSchema] = Field(
        ..., 
        min_length=1, 
        max_length=50,
        description="List of plans"
    )


class AdminUpdatePaymentSettingsRequest(BaseModel):
    """Schema for updating payment settings"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    card_number: str = Field(
        ..., 
        min_length=16, 
        max_length=20,
        description="Payment card number"
    )
    card_holder: str = Field(
        ..., 
        min_length=2, 
        max_length=100,
        description="Card holder name"
    )
    
    @field_validator('card_number')
    @classmethod
    def validate_card_number(cls, v: str) -> str:
        # Remove spaces and dashes
        v = re.sub(r'[\s\-]', '', v)
        if not re.match(r'^\d{16,19}$', v):
            raise ValueError('Invalid card number format')
        return v


class AdminIPWhitelistRequest(BaseModel):
    """Schema for updating admin IP whitelist"""
    enabled: Optional[bool] = Field(default=None, description="Enable or disable whitelist")
    ips: Optional[List[str]] = Field(default=None, max_length=2000, description="List of allowed IPs")

    @field_validator('ips')
    @classmethod
    def validate_ips(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        cleaned = []
        for ip in v:
            ip = (ip or "").strip()
            if not ip:
                continue
            # Basic IPv4/IPv6 string sanity check (full validation handled in handler)
            if len(ip) > 100:
                raise ValueError("IP entry too long")
            cleaned.append(ip)
        return cleaned

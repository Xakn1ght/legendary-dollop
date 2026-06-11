"""Schemas for charge (top-up) endpoints."""
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class StartChargeRequest(BaseModel):
    """Schema for starting a charge order"""

    subscription_id: int = Field(..., ge=1, description="Subscription to top up")
    package: str = Field(..., min_length=1, max_length=64, description="Charge package name")
    use_credit: bool = Field(default=False, description="Use account credit for payment")
    charge_type: str = Field(default="normal", description="normal | normal_5gb_limit | booking")
    auto_renewal: bool = Field(default=False, description="Enable auto-renewal")
    renewal_template: Optional[str] = Field(default=None, max_length=50, description="Plan for auto-renewal")

    @model_validator(mode="after")
    def validate_charge_type(self):
        if self.charge_type not in ("normal", "normal_5gb_limit", "booking"):
            raise ValueError("Invalid charge_type")
        if self.auto_renewal and not self.renewal_template:
            raise ValueError("renewal_template is required when auto_renewal is enabled")
        return self

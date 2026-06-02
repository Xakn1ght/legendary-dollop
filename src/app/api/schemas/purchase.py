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
# Purchase Schemas
# =============================================================================

class ServiceNameValidator:
    """Reusable service name validation"""
    PATTERN = re.compile(r'^[A-Za-z0-9]+$')
    MIN_LENGTH = 3
    MAX_LENGTH = 20
    
    @classmethod
    def validate(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == '':
            return None
        v = v.strip()
        if not cls.PATTERN.match(v):
            raise ValueError('Service name must contain only English letters and digits')
        if len(v) < cls.MIN_LENGTH:
            raise ValueError(f'Service name must be at least {cls.MIN_LENGTH} characters')
        if len(v) > cls.MAX_LENGTH:
            raise ValueError(f'Service name cannot exceed {cls.MAX_LENGTH} characters')
        return v


class ReferralCodeValidator:
    """Reusable referral code validation"""
    PATTERN = re.compile(r'^[A-Z0-9]{6}$')
    
    @classmethod
    def validate(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == '':
            return None
        v = v.strip().upper()
        if not cls.PATTERN.match(v):
            raise ValueError('Referral code must be exactly 6 uppercase letters/digits')
        return v


class StartPurchaseRequest(BaseModel):
    """Schema for starting a purchase order"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    plan: str = Field(
        ..., 
        min_length=1, 
        max_length=50,
        description="Plan name to purchase"
    )
    service_name: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Custom service name (optional)"
    )
    auto_renewal: bool = Field(
        default=False,
        description="Enable auto-renewal"
    )
    renewal_plan: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Plan for auto-renewal (required if auto_renewal is true)"
    )
    referral_code: Optional[str] = Field(
        default=None,
        max_length=6,
        description="Referral code (6 characters)"
    )
    use_credit: bool = Field(
        default=False,
        description="Use account credit for payment"
    )
    discount_ids: Optional[List[int]] = Field(
        default=None,
        max_length=10,
        description="List of discount IDs to apply"
    )
    coupon_id: Optional[int] = Field(
        default=None,
        ge=1,
        description="Season reward coupon to apply (one per purchase, no stacking)"
    )

    @field_validator('service_name')
    @classmethod
    def validate_service_name(cls, v: Optional[str]) -> Optional[str]:
        return ServiceNameValidator.validate(v)
    
    @field_validator('referral_code')
    @classmethod
    def validate_referral_code(cls, v: Optional[str]) -> Optional[str]:
        return ReferralCodeValidator.validate(v)
    
    @field_validator('discount_ids')
    @classmethod
    def validate_discount_ids(cls, v: Optional[List[int]]) -> Optional[List[int]]:
        if v is not None:
            if len(v) > 10:
                raise ValueError('Cannot apply more than 10 discounts')
            # Ensure all IDs are positive
            for id_ in v:
                if id_ < 1:
                    raise ValueError('Invalid discount ID')
        return v
    
    @model_validator(mode='after')
    def validate_renewal_plan(self):
        if self.auto_renewal and not self.renewal_plan:
            raise ValueError('renewal_plan is required when auto_renewal is enabled')
        return self


class SubmitReceiptRequest(BaseModel):
    """Schema for submitting a purchase receipt"""
    order_id: int = Field(..., ge=1, description="Order/subscription ID")
    receipt_image: str = Field(
        ..., 
        min_length=100,
        max_length=10_000_000,  # ~7.5MB base64
        description="Base64 encoded receipt image"
    )
    
    @field_validator('receipt_image')
    @classmethod
    def validate_receipt_image(cls, v: str) -> str:
        # Remove data URL prefix if present for length check
        image_data = v
        if ',' in v:
            image_data = v.split(',')[1]
        
        # Check minimum size (at least a small image)
        if len(image_data) < 100:
            raise ValueError('Receipt image is too small')
        
        # Check maximum size (~7.5MB base64 = ~5MB actual)
        if len(image_data) > 10_000_000:
            raise ValueError('Receipt image is too large (max 5MB)')
        
        return v


class CancelOrderRequest(BaseModel):
    """Schema for canceling an order"""
    order_id: int = Field(..., ge=1, description="Order ID to cancel")


class CheckServiceNameRequest(BaseModel):
    """Schema for checking service name availability"""
    name: str = Field(
        ..., 
        min_length=3, 
        max_length=20,
        description="Service name to check"
    )
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        return ServiceNameValidator.validate(v)


class ValidateReferralRequest(BaseModel):
    """Schema for validating a referral code"""
    code: str = Field(
        ..., 
        min_length=6, 
        max_length=6,
        description="Referral code to validate"
    )
    
    @field_validator('code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        result = ReferralCodeValidator.validate(v)
        if result is None:
            raise ValueError('Invalid referral code format')
        return result

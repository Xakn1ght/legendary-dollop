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

from .common import BaseResponse
from .tickets import TicketResponse


class TicketListResponse(BaseResponse):
    """Response for ticket list endpoint"""
    tickets: Optional[List[TicketResponse]] = None


class TicketDetailResponse(BaseResponse):
    """Response for ticket detail endpoint"""
    ticket: Optional[TicketResponse] = None


class PurchaseOrderResponse(BaseModel):
    """Response for purchase order creation"""
    id: int
    plan: str
    plan_gb: int
    plan_price: int
    service_name: str
    auto_renewal: bool
    renewal_plan: Optional[str] = None
    renewal_price: int = 0
    total_price: int
    discount_percent: int = 0
    discount_amount: int = 0
    credit_used: int = 0
    final_price: int


class StartPurchaseResponse(BaseResponse):
    """Response for start purchase endpoint"""
    order: Optional[PurchaseOrderResponse] = None


class AdminLoginResponse(BaseResponse):
    """Response for admin login"""
    requires_2fa: Optional[bool] = None
    expires_at: Optional[str] = None
    user: Optional[dict] = None

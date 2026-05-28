"""
Comprehensive Pydantic schemas for API input validation.

This module provides validation for all API endpoints including:
- Ticket creation and management
- Purchase flow
- Admin authentication and actions
- Notifications
- Game/Arcade submissions
- Subscription management

All schemas include proper constraints, custom validators, and clear error messages.
"""

from app.api.schemas.admin_auth import AdminLoginRequest, AdminVerify2FARequest
from app.api.schemas.admin_messaging import (
    AdminBroadcastRequest,
    AdminSendNotificationRequest,
    AdminTicketReplyRequest,
)
from app.api.schemas.admin_settings import (
    AdminIPWhitelistRequest,
    AdminUpdateChargePackagesRequest,
    AdminUpdatePaymentSettingsRequest,
    AdminUpdatePlansRequest,
    ChargePackageSchema,
    PlanSchema,
)
from app.api.schemas.admin_users import AdminToggleUserStatusRequest, AdminUserUpdateRequest
from app.api.schemas.common import BaseResponse, PaginationParams
from app.api.schemas.dashboard import (
    AddSubscriptionRequest,
    DashboardLoginRequest,
    DashboardMarkNotificationReadRequest,
    DashboardPreferencesPatchRequest,
)
from app.api.schemas.game import ArcadeSubmitRequest, LeaderboardRequest
from app.api.schemas.purchase import (
    CancelOrderRequest,
    CheckServiceNameRequest,
    ReferralCodeValidator,
    ServiceNameValidator,
    StartPurchaseRequest,
    SubmitReceiptRequest,
    ValidateReferralRequest,
)
from app.api.schemas.responses import (
    AdminLoginResponse,
    PurchaseOrderResponse,
    StartPurchaseResponse,
    TicketDetailResponse,
    TicketListResponse,
)
from app.api.schemas.tickets import (
    TicketCategory,
    TicketCreateRequest,
    TicketMessageResponse,
    TicketReplyRequest,
    TicketResponse,
)
from app.api.schemas.validation import create_validation_error_response, validate_request

__all__ = [
    "AddSubscriptionRequest",
    "AdminBroadcastRequest",
    "AdminIPWhitelistRequest",
    "AdminLoginRequest",
    "AdminLoginResponse",
    "AdminSendNotificationRequest",
    "AdminTicketReplyRequest",
    "AdminToggleUserStatusRequest",
    "AdminUpdateChargePackagesRequest",
    "AdminUpdatePaymentSettingsRequest",
    "AdminUpdatePlansRequest",
    "AdminUserUpdateRequest",
    "AdminVerify2FARequest",
    "ArcadeSubmitRequest",
    "BaseResponse",
    "CancelOrderRequest",
    "ChargePackageSchema",
    "CheckServiceNameRequest",
    "DashboardLoginRequest",
    "DashboardMarkNotificationReadRequest",
    "DashboardPreferencesPatchRequest",
    "LeaderboardRequest",
    "PaginationParams",
    "PlanSchema",
    "PurchaseOrderResponse",
    "ReferralCodeValidator",
    "ServiceNameValidator",
    "StartPurchaseRequest",
    "StartPurchaseResponse",
    "SubmitReceiptRequest",
    "TicketCategory",
    "TicketCreateRequest",
    "TicketDetailResponse",
    "TicketListResponse",
    "TicketMessageResponse",
    "TicketReplyRequest",
    "TicketResponse",
    "ValidateReferralRequest",
    "create_validation_error_response",
    "validate_request",
]

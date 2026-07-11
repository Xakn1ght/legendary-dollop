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


class AdminUserUpdateRequest(BaseModel):
    """Schema for updating a user (admin action)"""
    credit: Optional[int] = Field(default=None, ge=0, le=100_000_000, description="User credit")
    stars: Optional[int] = Field(default=None, ge=0, le=1_000_000, description="User stars")
    banned: Optional[bool] = Field(default=None, description="Ban status")
    
    @model_validator(mode='after')
    def check_at_least_one_field(self):
        if self.credit is None and self.stars is None and self.banned is None:
            raise ValueError('At least one field must be provided')
        return self


class AdminToggleUserStatusRequest(BaseModel):
    """Schema for toggling PasarGuard user status"""
    status: Literal["active", "disabled"] = Field(
        ..., 
        description="New status for the user"
    )

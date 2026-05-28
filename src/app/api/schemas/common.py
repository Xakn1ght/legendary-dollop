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


class BaseResponse(BaseModel):
    """Base response model for all API responses"""
    ok: bool
    error: Optional[str] = None
    message: Optional[str] = None


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints"""
    page: int = Field(default=1, ge=1, le=10000, description="Page number")
    limit: int = Field(default=20, ge=1, le=2000, description="Items per page (admin can request up to 2000)")
    search: Optional[str] = Field(default=None, max_length=100, description="Search query")
    
    @field_validator('search')
    @classmethod
    def sanitize_search(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            # Strip and limit search to prevent injection
            return v.strip()[:100]
        return v


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


class AdminLoginRequest(BaseModel):
    """Schema for admin login"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    chat_id: str = Field(
        ..., 
        min_length=1, 
        max_length=50,
        description="Admin chat ID or username"
    )
    password: str = Field(
        ..., 
        min_length=1, 
        max_length=128,
        description="Admin password"
    )
    
    @field_validator('chat_id')
    @classmethod
    def validate_chat_id(cls, v: str) -> str:
        v = v.strip()
        # Remove @ prefix if present
        if v.startswith('@'):
            v = v[1:]
        if not v:
            raise ValueError('Chat ID or username is required')
        return v
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not v:
            raise ValueError('Password is required')
        return v


class AdminVerify2FARequest(BaseModel):
    """Schema for admin 2FA verification"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    chat_id: str = Field(
        ..., 
        min_length=1, 
        max_length=50,
        description="Admin chat ID or username"
    )
    code: str = Field(
        ..., 
        min_length=6, 
        max_length=6,
        description="6-digit 2FA code"
    )
    
    @field_validator('code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r'^\d{6}$', v):
            raise ValueError('2FA code must be exactly 6 digits')
        return v

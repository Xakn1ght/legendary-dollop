import re
from typing import Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class ArcadeSubmitRequest(BaseModel):
    """Schema for submitting arcade game score"""
    model_config = ConfigDict(str_strip_whitespace=True)
    
    init_data: Optional[str] = Field(
        default=None,
        max_length=10000,
        description="Telegram WebApp init data"
    )
    score: int = Field(
        ..., 
        ge=0, 
        le=1_000_000_000,
        description="Game score"
    )
    duration: int = Field(
        default=0, 
        ge=0, 
        le=86400,
        description="Game duration in seconds"
    )
    practice: bool = Field(
        default=False,
        description="Practice mode (no rewards)"
    )
    display_name: Optional[str] = Field(
        default=None,
        max_length=40,
        description="Display name for leaderboard"
    )
    round_token: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Single-use token from /api/arcade/round-start (required for rewards)"
    )
    coins: int = Field(
        default=0,
        ge=0,
        le=50,
        description="Arcade coins collected this run (server re-caps to ARCADE_COINS max_per_run)"
    )

    @field_validator('display_name')
    @classmethod
    def sanitize_display_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            # Strip and limit
            v = v.strip()[:40]
            # Remove potentially dangerous characters
            v = re.sub(r'[<>"\']', '', v)
        return v


class LeaderboardRequest(BaseModel):
    """Schema for leaderboard query parameters"""
    period: Literal["daily", "weekly", "all_time"] = Field(
        default="daily",
        description="Leaderboard period"
    )
    limit: int = Field(
        default=10, 
        ge=1, 
        le=50,
        description="Number of entries to return"
    )

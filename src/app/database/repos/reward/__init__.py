from ._achievements import _AchievementsMixin
from ._challenges import _ChallengesMixin
from ._game import _GameMixin
from ._gifts import _GiftsMixin
from ._points import _PointsMixin
from ._stars import _StarsMixin
from ._tiers import _TiersMixin


class RewardRepository(
    _StarsMixin,
    _TiersMixin,
    _GameMixin,
    _ChallengesMixin,
    _AchievementsMixin,
    _PointsMixin,
    _GiftsMixin,
):
    """All reward-related database operations."""

from ._achievements import _AchievementsMixin
from ._challenges import _ChallengesMixin
from ._discounts import _DiscountsMixin
from ._game import _GameMixin
from ._points import _PointsMixin
from ._season import _SeasonMixin
from ._stars import _StarsMixin
from ._tiers import _TiersMixin


class RewardRepository(
    _StarsMixin,
    _TiersMixin,
    _SeasonMixin,
    _GameMixin,
    _ChallengesMixin,
    _AchievementsMixin,
    _PointsMixin,
    _DiscountsMixin,
):
    """All reward-related database operations."""

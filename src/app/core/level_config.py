"""
Level system configuration for the enhanced reward system.
Defines experience point requirements and rewards for each level.
"""

# Experience points required to reach each level
LEVEL_REQUIREMENTS = {
    1: 0,      # Starting level
    2: 100,    # 100 XP to level 2
    3: 300,    # 300 XP to level 3
    4: 600,    # 600 XP to level 4
    5: 1000,   # 1000 XP to level 5
    6: 1500,   # 1500 XP to level 6
    7: 2100,   # 2100 XP to level 7
    8: 2800,   # 2800 XP to level 8
    9: 3600,   # 3600 XP to level 9
    10: 4500,  # 4500 XP to level 10
    11: 5500,  # 5500 XP to level 11
    12: 6600,  # 6600 XP to level 12
    13: 7800,  # 7800 XP to level 13
    14: 9100,  # 9100 XP to level 14
    15: 10500, # 10500 XP to level 15
    16: 12000, # 12000 XP to level 16
    17: 13600, # 13600 XP to level 17
    18: 15300, # 15300 XP to level 18
    19: 17100, # 17100 XP to level 19
    20: 19000, # 19000 XP to level 20
}

# Rewards given when reaching each level
LEVEL_REWARDS = {
    2: {"loyalty_points": 50, "credit": 5000},
    3: {"loyalty_points": 100, "credit": 10000},
    4: {"loyalty_points": 200, "credit": 20000},
    5: {"loyalty_points": 500, "credit": 50000, "premium_features": True},
    6: {"loyalty_points": 750, "credit": 75000},
    7: {"loyalty_points": 1000, "credit": 100000},
    8: {"loyalty_points": 1500, "credit": 150000},
    9: {"loyalty_points": 2000, "credit": 200000},
    10: {"loyalty_points": 3000, "credit": 300000, "exclusive_servers": True},
    11: {"loyalty_points": 4000, "credit": 400000},
    12: {"loyalty_points": 5000, "credit": 500000},
    13: {"loyalty_points": 6500, "credit": 650000},
    14: {"loyalty_points": 8000, "credit": 800000},
    15: {"loyalty_points": 10000, "credit": 1000000, "vip_status": True},
    16: {"loyalty_points": 12000, "credit": 1200000},
    17: {"loyalty_points": 15000, "credit": 1500000},
    18: {"loyalty_points": 18000, "credit": 1800000},
    19: {"loyalty_points": 22000, "credit": 2200000},
    20: {"loyalty_points": 30000, "credit": 3000000, "legendary_status": True},
}

# Experience points earned from different activities
XP_SOURCES = {
    "referral": 50,           # Per successful referral
    "purchase": 100,          # Per subscription purchase
    "achievement": 200,       # Per achievement earned
    "challenge_completion": 300,  # Per challenge completed
    "streak_bonus": 50,       # Per day in arcade streak (max 7 days)
    "usage_milestone": 25,    # Per GB milestone (10GB, 50GB, 100GB, etc.)
}

# Premium features unlocked at different levels
PREMIUM_FEATURES = {
    5: ["custom_username", "priority_support"],
    10: ["exclusive_servers", "advanced_analytics"],
    15: ["vip_status", "unlimited_referrals"],
    20: ["legendary_status", "admin_consultation"],
}

def get_level_from_xp(experience_points: int) -> int:
    """Get the current level based on experience points."""
    for level, required_xp in sorted(LEVEL_REQUIREMENTS.items(), reverse=True):
        if experience_points >= required_xp:
            return level
    return 1

def get_xp_for_next_level(current_level: int, current_xp: int) -> int:
    """Get experience points needed for the next level."""
    next_level = current_level + 1
    if next_level not in LEVEL_REQUIREMENTS:
        return 0  # Max level reached
    return LEVEL_REQUIREMENTS[next_level] - current_xp

def get_level_progress(current_level: int, current_xp: int) -> float:
    """Get progress percentage to next level (0.0 to 1.0)."""
    current_level_xp = LEVEL_REQUIREMENTS.get(current_level, 0)
    next_level_xp = LEVEL_REQUIREMENTS.get(current_level + 1, current_level_xp)
    
    if next_level_xp == current_level_xp:
        return 1.0  # Max level reached
    
    xp_in_current_level = current_xp - current_level_xp
    xp_needed_for_next = next_level_xp - current_level_xp
    
    return min(1.0, max(0.0, xp_in_current_level / xp_needed_for_next))

def get_level_rewards(level: int) -> dict:
    """Get rewards for reaching a specific level."""
    return LEVEL_REWARDS.get(level, {})

def get_streak_bonus(streak_days: int) -> dict:
    """Get bonus rewards for a specific streak length."""
    # Find the highest streak bonus that applies
    applicable_bonuses = {days: bonus for days, bonus in STREAK_BONUSES.items() 
                         if streak_days >= days}
    if not applicable_bonuses:
        return {}
    
    max_streak = max(applicable_bonuses.keys())
    return applicable_bonuses[max_streak]

def get_premium_features(level: int) -> list:
    """Get premium features available at a specific level."""
    features = []
    for feature_level, feature_list in PREMIUM_FEATURES.items():
        if level >= feature_level:
            features.extend(feature_list)
    return list(set(features))  # Remove duplicates 
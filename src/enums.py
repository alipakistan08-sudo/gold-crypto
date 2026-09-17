from enum import Enum


class DecisionState(str, Enum):
    NO_TRADE = "NO_TRADE"
    WAIT_FOR_CONFIRMATION = "WAIT_FOR_CONFIRMATION"
    PAPER_TRADE_APPROVED = "PAPER_TRADE_APPROVED"
    LIVE_TRADE_APPROVED = "LIVE_TRADE_APPROVED"


class RiskDecision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REDUCE_SIZE = "REDUCE_SIZE"
    DEFER = "DEFER"


class KillLevel(str, Enum):
    CLEAR = "CLEAR"
    SOFT_HALT = "SOFT_HALT"
    HARD_HALT = "HARD_HALT"
    FULL_LOCK = "FULL_LOCK"


class Side(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class VolRegime(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EXTREME = "EXTREME"

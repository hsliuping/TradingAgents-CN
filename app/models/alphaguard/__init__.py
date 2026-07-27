"""AlphaGuard MongoDB collection declarations."""

from .decision_collections import DECISION_COLLECTIONS
from .paper_collections import PAPER_COLLECTIONS
from .quant_collections import QUANT_COLLECTIONS
from .operations_collections import OPERATIONS_COLLECTIONS

__all__ = [
    "DECISION_COLLECTIONS",
    "OPERATIONS_COLLECTIONS",
    "PAPER_COLLECTIONS",
    "QUANT_COLLECTIONS",
]

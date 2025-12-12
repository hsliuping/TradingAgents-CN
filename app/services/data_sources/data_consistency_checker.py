"""
Minimal stub for DataConsistencyChecker
- Purpose: eliminate warning and provide no-op consistency checking
- Behavior: always mark data as consistent and prefer primary source
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
import pandas as pd


@dataclass
class DataConsistencyResult:
    is_consistent: bool = True
    confidence_score: float = 1.0
    recommended_action: str = "use_primary"
    differences: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.differences is None:
            self.differences = []


class DataConsistencyChecker:
    """No-op checker: always returns consistent and uses primary data.
    This is a lightweight placeholder so that DataSourceManager can import it
    without printing warnings when the full checker isn't provided.
    """

    def check_daily_basic_consistency(
        self,
        primary: pd.DataFrame,
        secondary: pd.DataFrame,
        primary_name: str,
        secondary_name: str,
    ) -> DataConsistencyResult:
        # In stub, we do not compute differences; always consistent.
        return DataConsistencyResult()

    def resolve_data_conflicts(
        self,
        primary: pd.DataFrame,
        secondary: pd.DataFrame,
        result: DataConsistencyResult,
    ) -> Tuple[pd.DataFrame, str]:
        # Always choose primary data
        return primary, "use_primary"


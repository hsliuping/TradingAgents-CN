"""Versioned deterministic attribution rules; never invokes an LLM."""

from __future__ import annotations

from decimal import Decimal

from app.services.alphaguard.evaluation_policy_registry import attribution_policy


class AttributionRuleRegistry:
    REQUIRED_CATEGORIES = {
        "DATA_QUALITY",
        "CANDIDATE_SELECTION",
        "FACTOR_FAILURE",
        "REGIME_MISCLASSIFICATION",
        "STRATEGY_ENTRY",
        "NORMAL_MODEL",
        "TOP_MODEL",
        "CONSENSUS",
        "HARD_RISK",
        "EXECUTION",
        "MARKET_SHOCK",
        "UNKNOWN",
    }

    def __init__(self):
        self.policy = attribution_policy()
        self.rules = {
            item["category"]: item["rule_id"] for item in self.policy.rules
        }
        if set(self.rules) != self.REQUIRED_CATEGORIES:
            raise ValueError("attribution rule registry does not cover all categories")
        self.thresholds = {
            key: Decimal(value) for key, value in self.policy.thresholds.items()
        }

    @property
    def version(self) -> str:
        return self.policy.attribution_rule_id

    def rule_id(self, category: str) -> str:
        return self.rules[category]

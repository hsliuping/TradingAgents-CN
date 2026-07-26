"""Central, explicit experiment version state machine."""

from __future__ import annotations

from tradingagents.alphaguard.experiment_schemas import ExperimentStatus


ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"EXPERIMENT"}),
    "EXPERIMENT": frozenset({"BACKTESTED", "SUSPENDED"}),
    "BACKTESTED": frozenset({"SHADOW", "EXPERIMENT", "SUSPENDED"}),
    "SHADOW": frozenset({"CHALLENGER", "BACKTESTED", "SUSPENDED"}),
    "CHALLENGER": frozenset(
        {"CHAMPION", "SHADOW", "DEGRADED", "SUSPENDED"}
    ),
    "CHAMPION": frozenset({"DEGRADED", "SUSPENDED", "RETIRED"}),
    "DEGRADED": frozenset({"CHAMPION", "SUSPENDED", "RETIRED"}),
    "SUSPENDED": frozenset({"EXPERIMENT", "SHADOW", "RETIRED"}),
    "RETIRED": frozenset(),
}


class ExperimentTransitionError(ValueError):
    pass


def validate_transition(
    current: ExperimentStatus,
    target: ExperimentStatus,
    *,
    human_approval_applied: bool = False,
) -> None:
    if target not in ALLOWED_TRANSITIONS[current]:
        raise ExperimentTransitionError(
            f"illegal experiment transition: {current} -> {target}"
        )
    if current == "CHALLENGER" and target == "CHAMPION" and not human_approval_applied:
        raise ExperimentTransitionError(
            "CHALLENGER -> CHAMPION requires applied human approval"
        )

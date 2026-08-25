"""
RAY V1 Action Registry

The action registry defines the ONLY permitted actions.
The LLM cannot invent new action types.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Literal


class ActionType(str, Enum):
    """V1 action space - exactly TWO actions."""

    CREATE_PAYMENT_LINK = "create_payment_link"
    DO_NOTHING = "do_nothing"


@dataclass(frozen=True)
class ActionDefinition:
    """Action metadata and validation."""

    action_type: ActionType
    description: str
    requires_execution: bool
    has_cost: bool


# V1 Action Registry
ACTION_REGISTRY: dict[ActionType, ActionDefinition] = {
    ActionType.CREATE_PAYMENT_LINK: ActionDefinition(
        action_type=ActionType.CREATE_PAYMENT_LINK,
        description="Create a Razorpay Payment Link and send to customer",
        requires_execution=True,
        has_cost=True,
    ),
    ActionType.DO_NOTHING: ActionDefinition(
        action_type=ActionType.DO_NOTHING,
        description="Take no action, rely on organic recovery",
        requires_execution=False,
        has_cost=False,
    ),
}


def validate_action_type(action: str) -> ActionType:
    """
    Validate that an action string is a registered action type.

    Raises ValueError if action is not registered.
    This prevents the LLM from inventing arbitrary actions.
    """
    try:
        action_type = ActionType(action)
    except ValueError as e:
        raise ValueError(
            f"Unknown action type: {action}. "
            f"Valid actions: {[a.value for a in ActionType]}"
        ) from e

    if action_type not in ACTION_REGISTRY:
        raise ValueError(
            f"Action type {action} not in registry. "
            f"Registered actions: {list(ACTION_REGISTRY.keys())}"
        )

    return action_type


def get_action_definition(action_type: ActionType) -> ActionDefinition:
    """Get action definition from registry."""
    return ACTION_REGISTRY[action_type]


def list_available_actions() -> list[ActionType]:
    """List all available action types."""
    return list(ACTION_REGISTRY.keys())

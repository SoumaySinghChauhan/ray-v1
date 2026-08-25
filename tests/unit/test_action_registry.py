"""Test action registry."""

import pytest
import sys
from pathlib import Path

# Add services/api to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services" / "api"))

from action_registry import (
    ActionType,
    validate_action_type,
    get_action_definition,
    list_available_actions,
)


def test_action_registry_contains_exactly_two_actions():
    """V1 must have exactly two actions."""
    actions = list_available_actions()
    assert len(actions) == 2
    assert ActionType.CREATE_PAYMENT_LINK in actions
    assert ActionType.DO_NOTHING in actions


def test_validate_action_type_valid():
    """Valid action types should pass validation."""
    action = validate_action_type("create_payment_link")
    assert action == ActionType.CREATE_PAYMENT_LINK

    action = validate_action_type("do_nothing")
    assert action == ActionType.DO_NOTHING


def test_validate_action_type_invalid():
    """Invalid action types should raise ValueError."""
    with pytest.raises(ValueError, match="Unknown action type"):
        validate_action_type("send_sms")

    with pytest.raises(ValueError, match="Unknown action type"):
        validate_action_type("retry_payment")

    with pytest.raises(ValueError, match="Unknown action type"):
        validate_action_type("invalid_action")


def test_get_action_definition():
    """Action definitions should be retrievable."""
    definition = get_action_definition(ActionType.CREATE_PAYMENT_LINK)
    assert definition.action_type == ActionType.CREATE_PAYMENT_LINK
    assert definition.requires_execution is True
    assert definition.has_cost is True

    definition = get_action_definition(ActionType.DO_NOTHING)
    assert definition.action_type == ActionType.DO_NOTHING
    assert definition.requires_execution is False
    assert definition.has_cost is False


def test_llm_cannot_invent_action_types():
    """
    Critical test: LLM cannot invent arbitrary action types.

    This prevents the LLM from creating actions like:
    - "send_sms"
    - "call_customer"
    - "offer_discount"
    - "retry_payment"

    Only registered actions are permitted.
    """
    # Simulate LLM returning an invented action
    llm_output = "refund_customer"

    with pytest.raises(ValueError):
        validate_action_type(llm_output)

"""
Test that the batch diagnosis completion script can import its dependencies.

CRITICAL: This test prevents ModuleNotFoundError at runtime.
"""

import pytest
import sys
from pathlib import Path


def test_diagnosis_script_can_import_local_provider():
    """Test that diagnosis script can import LocalDiagnosisProvider."""
    # Add project root to path (same as script does)
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # This should not raise ModuleNotFoundError
    from ai.diagnosis.local_provider import LocalDiagnosisProvider

    # Verify class exists
    assert LocalDiagnosisProvider is not None
    assert hasattr(LocalDiagnosisProvider, 'generate')


def test_diagnosis_script_can_import_schema():
    """Test that diagnosis script can import schema classes."""
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from ai.diagnosis.schema import LLMDiagnosticOutput, DiagnosticStatus

    assert LLMDiagnosticOutput is not None
    assert DiagnosticStatus is not None


def test_diagnosis_script_can_import_prompt():
    """Test that diagnosis script can import prompt utilities."""
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from ai.diagnosis.prompt import (
        DIAGNOSIS_SYSTEM_PROMPT,
        DIAGNOSIS_PROMPT_VERSION,
        create_diagnosis_prompt,
    )

    assert DIAGNOSIS_SYSTEM_PROMPT is not None
    assert DIAGNOSIS_PROMPT_VERSION is not None
    assert callable(create_diagnosis_prompt)


def test_diagnosis_script_imports_do_not_require_ollama_running():
    """
    Test that importing diagnosis modules does not require Ollama to be running.

    LocalDiagnosisProvider's __init__ verifies service, but this should not
    happen during module import, only during instantiation.
    """
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Import should succeed even if Ollama is not running
    from ai.diagnosis.local_provider import LocalDiagnosisProvider

    # Only instantiation should verify service
    # (We don't instantiate in this test to avoid requiring Ollama)
    assert LocalDiagnosisProvider is not None

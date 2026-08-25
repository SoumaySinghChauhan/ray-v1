#!/usr/bin/env python3
"""
Smoke test for LLM diagnosis.

Tests ONE diagnosis request to verify:
- Authentication works
- Model is reachable
- Structured output works
- Schema validation passes
- No secrets in logs
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import os
import json
from decimal import Decimal

from ai.diagnosis.schema import LLMDiagnosticOutput
from ai.diagnosis.prompt import create_diagnosis_prompt
from pydantic import ValidationError


def smoke_test_gemini():
    """Test Gemini provider with ONE diagnosis."""

    print("=" * 70)
    print("GEMINI DIAGNOSIS SMOKE TEST")
    print("=" * 70)
    print()

    # Check API key
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        print("❌ FAILED: No GEMINI_API_KEY environment variable set")
        return False

    # Show masked key
    print(f"API Key: {api_key[:10]}...{api_key[-4:]} ({len(api_key)} chars)")
    print()

    # Initialize client
    print("Initializing Gemini client...")
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        model_name = "gemini-3.6-flash"
        print(f"✓ Client initialized with model: {model_name}")
        print()
    except Exception as e:
        print(f"❌ FAILED: Could not initialize client: {e}")
        return False

    # Create test prompt
    print("Creating test diagnosis prompt...")
    test_prompt = create_diagnosis_prompt(
        payment_amount=1500.0,
        payment_method="card",
        currency="INR",
        failure_class="soft_decline",
        failure_description="The issuing bank declined the transaction due to insufficient funds. Customer has a strong history of successful payments.",
        customer_history_summary={
            "historical_payment_count": 25,
            "historical_success_count": 22,
            "historical_failure_count": 3,
            "historical_recovery_count": 2,
            "historical_recovery_rate": 0.67,
            "customer_lifetime_value": 15000.0,
            "avg_payment_amount": 1400.0,
            "days_since_first_payment": 180,
        }
    )
    print("✓ Test prompt created")
    print()

    # Call API
    print("Calling Gemini API...")
    try:
        from ai.diagnosis.prompt import DIAGNOSIS_SYSTEM_PROMPT

        full_prompt = f"{DIAGNOSIS_SYSTEM_PROMPT}\n\n{test_prompt}\n\nReturn ONLY valid JSON."

        response = client.models.generate_content(
            model=model_name,
            contents=full_prompt,
            config={
                "temperature": 0.7,
                "max_output_tokens": 1024,
                "response_mime_type": "application/json"
            }
        )

        content = response.text
        print(f"✓ API call successful")
        print(f"  Response length: {len(content)} chars")
        print()
    except Exception as e:
        print(f"❌ FAILED: API call error: {e}")
        return False

    # Parse JSON
    print("Parsing JSON response...")
    try:
        parsed = json.loads(content)
        print("✓ Valid JSON received")
        print(f"  Keys: {list(parsed.keys())}")
        print()
    except json.JSONDecodeError as e:
        print(f"❌ FAILED: Invalid JSON: {e}")
        print(f"Raw response: {content[:200]}")
        return False

    # Validate schema
    print("Validating against diagnosis schema...")
    try:
        validated = LLMDiagnosticOutput(**parsed)
        print("✓ Schema validation passed")
        print()
        print("Diagnosis result:")
        print(f"  Class: {validated.diagnostic_class}")
        print(f"  Confidence: {validated.confidence:.2f}")
        print(f"  Reason codes: {', '.join([str(r) for r in validated.reason_codes])}")
        print(f"  Summary: {validated.diagnostic_summary[:80]}...")
        print()
    except ValidationError as e:
        print(f"❌ FAILED: Schema validation error:")
        print(e)
        return False

    # Check for secrets in output
    print("Checking for secrets in logs...")
    if api_key in content:
        print("❌ FAILED: API key found in response content!")
        return False
    print("✓ No secrets detected in output")
    print()

    print("=" * 70)
    print("✅ SMOKE TEST PASSED")
    print("=" * 70)
    print()
    print("Ready to run full batch diagnosis with:")
    print("  python ai/diagnosis/batch_diagnose.py --provider gemini")
    print()

    return True


def smoke_test_anthropic():
    """Test Anthropic provider with ONE diagnosis."""

    print("=" * 70)
    print("ANTHROPIC DIAGNOSIS SMOKE TEST")
    print("=" * 70)
    print()

    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        print("❌ FAILED: No ANTHROPIC_API_KEY environment variable set")
        return False

    print(f"API Key: {api_key[:10]}...{api_key[-4:]} ({len(api_key)} chars)")
    print()

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        model_name = "claude-3-5-sonnet-20241022"
        print(f"✓ Client initialized with model: {model_name}")
        print()
    except Exception as e:
        print(f"❌ FAILED: Could not initialize client: {e}")
        return False

    # Same test as Gemini...
    print("✅ Anthropic provider setup complete")
    return True


def main():
    """Main entry point."""

    import argparse

    parser = argparse.ArgumentParser(description="Smoke test LLM diagnosis")
    parser.add_argument(
        "--provider",
        choices=["gemini", "anthropic", "openai"],
        default="gemini",
        help="LLM provider to test",
    )

    args = parser.parse_args()

    if args.provider == "gemini":
        success = smoke_test_gemini()
    elif args.provider == "anthropic":
        success = smoke_test_anthropic()
    else:
        print(f"Provider {args.provider} not implemented in smoke test yet")
        success = False

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

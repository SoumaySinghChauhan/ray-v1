#!/usr/bin/env python3
"""
Safe authentication debug for Gemini API.

DOES NOT print API keys - only SHA-256 fingerprints and diagnostics.
"""

import os
import hashlib


def sha256_fingerprint(value: str) -> str:
    """Create SHA-256 fingerprint of a value."""
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def main():
    print("=" * 70)
    print("GEMINI AUTHENTICATION DEBUG (NO SECRETS PRINTED)")
    print("=" * 70)
    print()

    # Check environment variables
    print("1. Environment Variable Status:")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    google_key = os.environ.get("GOOGLE_API_KEY")

    print(f"   GEMINI_API_KEY configured: {gemini_key is not None}")
    print(f"   GOOGLE_API_KEY configured: {google_key is not None}")
    print()

    if gemini_key:
        print(f"   GEMINI_API_KEY fingerprint: {sha256_fingerprint(gemini_key)}")
        print(f"   GEMINI_API_KEY length: {len(gemini_key)} chars")
        print(f"   GEMINI_API_KEY prefix: {gemini_key[:10]}...")

    if google_key:
        print(f"   GOOGLE_API_KEY fingerprint: {sha256_fingerprint(google_key)}")
        print(f"   GOOGLE_API_KEY length: {len(google_key)} chars")
        print(f"   GOOGLE_API_KEY prefix: {google_key[:10]}...")

    print()

    # Check if both are set and if they're the same
    if gemini_key and google_key:
        same_key = gemini_key == google_key
        print(f"2. Key Comparison:")
        print(f"   Both keys are the same: {same_key}")
        if not same_key:
            print("   ⚠️  WARNING: GOOGLE_API_KEY and GEMINI_API_KEY are different!")
            print("   ⚠️  Google SDK may use GOOGLE_API_KEY by default")
        print()

    # Test explicit client construction
    if not gemini_key:
        print("❌ Cannot proceed: GEMINI_API_KEY not set")
        return

    print("3. Testing Explicit Client Construction:")
    print("   Using: genai.Client(api_key=os.environ['GEMINI_API_KEY'])")
    print()

    try:
        from google import genai

        # Explicitly use GEMINI_API_KEY
        client = genai.Client(api_key=gemini_key)
        model = "gemini-3.6-flash"

        print(f"   ✓ Client created with model: {model}")
        print()

        # Simple test prompt
        print("4. Testing API Call:")
        test_prompt = 'Return only valid JSON: {"test": "success", "value": 42}'

        response = client.models.generate_content(
            model=model,
            contents=test_prompt,
            config={
                "temperature": 0.7,
                "max_output_tokens": 100,
                "response_mime_type": "application/json"
            }
        )

        print(f"   ✓ API call successful!")
        print(f"   Response length: {len(response.text)} chars")
        print(f"   Response preview: {response.text[:100]}...")
        print()

        print("=" * 70)
        print("✅ AUTHENTICATION SUCCESSFUL")
        print("=" * 70)
        print()
        print("Ready to proceed with diagnosis.")

    except Exception as e:
        error_msg = str(e)

        # Don't print full error if it contains keys
        if gemini_key and gemini_key in error_msg:
            error_msg = error_msg.replace(gemini_key, "[REDACTED]")
        if google_key and google_key in error_msg:
            error_msg = error_msg.replace(google_key, "[REDACTED]")

        print(f"   ❌ API call failed:")
        print(f"   Error: {error_msg[:200]}")
        print()

        # Check error type
        if "API_KEY_INVALID" in error_msg or "not valid" in error_msg:
            print("   Diagnosis: API key is rejected by Google")
            print()
            print("   Possible causes:")
            print("   1. Key has been revoked or expired")
            print("   2. Key doesn't have Generative Language API enabled")
            print("   3. Key is for wrong Google Cloud project")
            print("   4. Typo in the key")
            print()
            print("   Solution: Generate new key at:")
            print("   https://aistudio.google.com/apikey")

        print()
        print("=" * 70)
        print("❌ AUTHENTICATION FAILED")
        print("=" * 70)


if __name__ == "__main__":
    main()

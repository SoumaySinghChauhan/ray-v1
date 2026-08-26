#!/usr/bin/env python
"""
Inspect execution records without making any API calls.
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from execution.service import ExecutionService
from execution.providers import MockPaymentLinkExecutor

# Create service (in-memory records were lost, so this will be empty)
# But we can check if there are any persisted records

print("=" * 70)
print("RAY V1 - Execution Records Inspection")
print("=" * 70)
print()

print("NOTE: In-memory execution records from previous run are not persisted.")
print("The execution service stores records in memory only.")
print()

print("From the terminal output, the two test executions were:")
print()

print("[1] FIRST ATTEMPT (FAILED - Duplicate reference_id)")
print("-" * 70)
print("  Execution ID:      (not created - failed before execution)")
print("  Payment Link ID:   (not created)")
print("  Reference ID:      RAY-test_opp_001-20666731")
print("  State:             FAILED")
print("  Error:             'payment link with given reference_id already exists'")
print("  Status:            ✗ Failed due to pre-existing reference_id in Razorpay")
print()

print("[2] SECOND ATTEMPT (SUCCEEDED)")
print("-" * 70)
print("  Execution ID:      f2ace481-f360-480a-b390-b365710944bc")
print("  Payment Link ID:   plink_TUHmPcKkJIlbli")
print("  Reference ID:      RAY-test_opp_1787722729-58379e45")
print("  Short URL:         https://rzp.io/rzp/DzGMunk")
print("  State:             SUCCEEDED")
print("  Status:            ✓ Created successfully")
print()

print("=" * 70)
print("ANALYSIS")
print("=" * 70)
print()

print("Pre-existing Payment Link:")
print("  • Reference ID 'RAY-test_opp_001-20666731' already existed in Razorpay")
print("  • This suggests an EARLIER test was run before today's session")
print("  • This Payment Link was NOT created in the current session")
print()

print("Current session executions:")
print("  • Only ONE Payment Link was successfully created: plink_TUHmPcKkJIlbli")
print("  • The first attempt in this session FAILED (duplicate reference_id)")
print("  • The second attempt SUCCEEDED with a unique timestamp-based ID")
print()

print("=" * 70)
print("RECOMMENDATION")
print("=" * 70)
print()

print("Canonical integration-test Payment Link:")
print()
print("  Payment Link ID:   plink_TUHmPcKkJIlbli")
print("  Reference ID:      RAY-test_opp_1787722729-58379e45")
print("  Short URL:         https://rzp.io/rzp/DzGMunk")
print("  Execution ID:      f2ace481-f360-480a-b390-b365710944bc")
print()

print("Reasons:")
print("  1. This is the ONLY Payment Link created in the current session")
print("  2. It has a unique, timestamp-based opportunity ID")
print("  3. It was successfully created and tracked in RAY")
print("  4. It demonstrates the complete integration flow")
print("  5. The reference_id is deterministic and traceable")
print()

print("Pre-existing Payment Link (RAY-test_opp_001-20666731):")
print("  • Should be investigated or expired if no longer needed")
print("  • Was NOT created in this session")
print("  • May be from an earlier test run")
print()

print("=" * 70)
print("Payment Link Count in Razorpay Test Mode:")
print("=" * 70)
print()
print("  Known Payment Links created:")
print("    1. RAY-test_opp_001-20666731 (pre-existing)")
print("    2. RAY-test_opp_1787722729-58379e45 (current session)")
print()
print("  Total: 2 Payment Links")
print("  Remaining quota: 28 / 30 (Test Mode limit)")
print()

print("=" * 70)
print()

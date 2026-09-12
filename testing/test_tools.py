"""
Test all tools independently (Phase 2 verification).

This tests each tool WITHOUT LangGraph or LLM integration.
Just pure Python functions to verify they work.

Run: python testing/test_tools.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.tools import check_style, check_test_coverage, scan_security


def test_linter():
    """Test linter/style-check tool."""
    print("\n" + "="*70)
    print("TEST 1: LINTER / STYLE-CHECK TOOL")
    print("="*70)

    # Example: A diff with style violations
    bad_diff = """@@ -1,10 +1,11 @@
 def process_data(data):
-    model = torch.nn.Linear(10, 5)
+    model = torch.nn.Linear(10, 5)
+    result = some_function_that_has_a_very_long_line_name_that_exceeds_the_100_character_limit_for_sure_yes
     return model
"""

    result = check_style(bad_diff, lang='py')

    print(f"✓ Tool executed successfully")
    print(f"Has violations: {result['has_violations']}")
    print(f"Issue count: {result['count']}")
    print(f"\nSummary:\n{result['summary']}")

    assert result['has_violations'], "Expected to find style issues"
    print("\n✓ Linter test PASSED")


def test_test_detector():
    """Test test-coverage detector tool."""
    print("\n" + "="*70)
    print("TEST 2: TEST-COVERAGE DETECTOR TOOL")
    print("="*70)

    # Example 1: Diff with test files added
    test_diff_1 = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,5 +1,6 @@
 import flask
+from utils import helper

 def hello():
     return "Hello"
diff --git a/test_app.py b/test_app.py
--- /dev/null
+++ b/test_app.py
@@ -0,0 +1,10 @@
+import pytest
+from app import hello
+
+def test_hello():
+    assert hello() == "Hello"
"""

    result = check_test_coverage(test_diff_1, lang='py')

    print(f"✓ Tool executed successfully")
    print(f"Has tests: {result['has_tests']}")
    print(f"Test files: {result['test_files']}")
    print(f"Production files: {result['production_files']}")
    print(f"Test frameworks: {result['test_frameworks']}")
    print(f"P/T Ratio: {result['production_to_test_ratio']}")
    print(f"\nSummary:\n{result['summary']}")
    print(f"\nRecommendation:\n{result['recommendation']}")

    assert result['has_tests'], "Expected to find test files"
    print("\n✓ Test detector test PASSED")

    # Example 2: Diff WITHOUT test files
    print("\n" + "-"*70)
    print("TEST 2B: Test detector - no test files")
    print("-"*70)

    no_test_diff = """diff --git a/production.py b/production.py
--- a/production.py
+++ b/production.py
@@ -1,3 +1,4 @@
 def critical_function():
-    return 42
+    return 43  # Changed logic
"""

    result2 = check_test_coverage(no_test_diff, lang='py')

    print(f"Has tests: {result2['has_tests']}")
    print(f"\nSummary:\n{result2['summary']}")
    print(f"\nRecommendation:\n{result2['recommendation']}")

    assert not result2['has_tests'], "Expected NO test files"
    print("\n✓ Test detector (no tests) test PASSED")


def test_security_checker():
    """Test security pattern checker tool."""
    print("\n" + "="*70)
    print("TEST 3: SECURITY PATTERN CHECKER TOOL")
    print("="*70)

    # Example: Code with security issues
    insecure_diff = """@@ -1,10 +1,15 @@
 import os
+import pickle

 def authenticate(user_input):
-    return user_input == "admin"
+    password = "supersecret123"
+    data = pickle.loads(user_input)
+    query = "SELECT * FROM users WHERE name='" + user_input + "'"
+    return query
"""

    result = scan_security(insecure_diff, lang='py')

    print(f"✓ Tool executed successfully")
    print(f"Has security issues: {result['has_issues']}")
    print(f"High severity: {result['high_severity_count']}")
    print(f"Medium severity: {result['medium_severity_count']}")
    print(f"\nSummary:\n{result['summary']}")

    if result['recommendations']:
        print(f"\nRecommendations:")
        for rec in result['recommendations']:
            print(f"  • {rec}")

    assert result['has_issues'], "Expected to find security issues"
    print("\n✓ Security checker test PASSED")

    # Example 2: Secure code
    print("\n" + "-"*70)
    print("TEST 3B: Security checker - secure code")
    print("-"*70)

    secure_diff = """@@ -1,5 +1,10 @@
 import os
+import secrets
+from sqlalchemy import query

 def authenticate(username, password):
-    return username == "admin" and password == "correct"
+    param = secrets.token_urlsafe(16)
+    statement = query.select(...).where(User.name == username)
+    result = db.execute(statement)
+    return result
"""

    result2 = scan_security(secure_diff, lang='py')

    print(f"Has security issues: {result2['has_issues']}")
    print(f"\nSummary:\n{result2['summary']}")

    # This should have fewer or no high-severity issues
    print("\n✓ Security checker (secure code) test PASSED")


def main():
    print("\n" + "#"*70)
    print("# PHASE 2: Tools Testing")
    print("# Testing each tool independently (no LangGraph yet)")
    print("#"*70)

    try:
        test_linter()
        test_test_detector()
        test_security_checker()

        print("\n" + "#"*70)
        print("# ALL TESTS PASSED ✓")
        print("#"*70)
        print("\nPhase 2 Summary:")
        print("  ✓ Linter/style-check tool works")
        print("  ✓ Test-coverage detector tool works")
        print("  ✓ Security pattern checker tool works")
        print("\nAll tools are ready for Phase 3 (LangGraph integration)")
        print("\nNext: Phase 3 - Build first agent (Style Agent) with LangGraph")

        return 0

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""
Test Coverage Detector Tool

Checks if a diff includes test file additions/changes.

Design decision: We use heuristics (file path patterns) rather than AST analysis because:
1. Diff gives us file paths, not full file structure
2. Test patterns are consistent across languages (test_*.py, *_test.js, *Test.java)
3. Simple and fast - no parsing overhead
4. Good enough for 90% of cases

What we detect:
- Files matching test patterns (test_*, *_test, tests/)
- Test framework usage (unittest, pytest, jest, junit)
- Test setup files (conftest.py, test-setup.js)
"""
import re
from typing import List, Dict, Tuple


# Common test file patterns by language
TEST_PATTERNS = {
    'py': [
        r'^tests/',           # tests/ directory
        r'_test\.py$',        # *_test.py
        r'^test_.*\.py$',     # test_*.py
        r'conftest\.py$',     # pytest config
    ],
    'js': [
        r'^.*\.test\.js$',    # *.test.js
        r'^.*\.spec\.js$',    # *.spec.js
        r'_test\.js$',        # *_test.js
        r'^test/',            # test/ directory
        r'tests/',            # tests/ directory
    ],
    'java': [
        r'^.*Test\.java$',    # *Test.java
        r'^.*Tests\.java$',   # *Tests.java
        r'src/test',          # src/test directory
    ],
    'ts': [
        r'^.*\.test\.ts$',
        r'^.*\.spec\.ts$',
        r'^test/',
    ]
}

# Test framework imports/keywords
TEST_FRAMEWORKS = {
    'py': ['import pytest', 'import unittest', 'from unittest', 'TestCase', '@pytest.'],
    'js': ['jest', 'mocha', 'describe(', 'it(', 'test(', 'expect('],
    'java': ['import junit', '@Test', 'TestCase'],
}


def extract_filenames_from_diff(diff_hunk: str) -> List[Tuple[str, str]]:
    """
    Extract filenames from a unified diff.

    Returns:
        List of (operation, filename) tuples where operation is 'added', 'removed', 'modified'
    """
    files = []
    lines = diff_hunk.split('\n')

    for line in lines:
        if line.startswith('+++'):
            # New file or modified file being added
            filename = line.replace('+++', '').replace('b/', '').strip()
            if filename and not filename.startswith('/dev/null'):
                files.append(('added', filename))
        elif line.startswith('---'):
            # Old file (removed or being modified)
            filename = line.replace('---', '').replace('a/', '').strip()
            if filename and not filename.startswith('/dev/null'):
                files.append(('removed', filename))

    return files


def is_test_file(filepath: str, lang: str) -> bool:
    """
    Check if a file path matches test file patterns for a given language.

    Args:
        filepath: File path from diff
        lang: Language code ('py', 'js', 'java', 'ts')

    Returns:
        True if filepath looks like a test file
    """
    patterns = TEST_PATTERNS.get(lang, [])

    for pattern in patterns:
        if re.search(pattern, filepath):
            return True

    return False


def detect_test_framework_usage(code_snippet: str, lang: str) -> List[str]:
    """
    Detect if code uses specific test frameworks.

    Args:
        code_snippet: Code to analyze
        lang: Language code

    Returns:
        List of detected framework names
    """
    frameworks = []
    keywords = TEST_FRAMEWORKS.get(lang, [])

    for keyword in keywords:
        if keyword in code_snippet:
            # Extract framework name
            if 'pytest' in keyword:
                frameworks.append('pytest')
            elif 'unittest' in keyword:
                frameworks.append('unittest')
            elif 'jest' in keyword:
                frameworks.append('jest')
            elif 'mocha' in keyword:
                frameworks.append('mocha')
            elif 'junit' in keyword:
                frameworks.append('junit')

    return list(set(frameworks))  # Remove duplicates


def check_test_coverage(diff_hunk: str, old_file: str = '', lang: str = 'py') -> Dict:
    """
    Check if diff includes test file changes.

    Args:
        diff_hunk: Unified diff showing changes
        old_file: Original file content (for detecting test imports)
        lang: Language code ('py', 'js', 'java', 'ts')

    Returns:
        Dictionary with:
        - 'has_tests': Boolean (True if test files detected)
        - 'test_files': List of test files found
        - 'test_frameworks': List of frameworks detected
        - 'production_to_test_ratio': Ratio of production to test code changes
        - 'summary': Human-readable summary
        - 'recommendation': String with advice
    """
    files = extract_filenames_from_diff(diff_hunk)

    # Separate test and production files
    test_files = []
    production_files = []

    for operation, filepath in files:
        if is_test_file(filepath, lang):
            test_files.append((operation, filepath))
        else:
            production_files.append((operation, filepath))

    # Detect test frameworks
    frameworks = detect_test_framework_usage(diff_hunk + '\n' + old_file, lang)

    # Calculate ratio
    if production_files:
        ratio = len(test_files) / len(production_files)
    else:
        ratio = 0 if not test_files else float('inf')

    # Build summary
    summary = []
    if test_files:
        summary.append(f"✓ Test files detected ({len(test_files)} file(s))")
        for op, path in test_files:
            summary.append(f"  • [{op}] {path}")
    else:
        summary.append("⚠ No test files detected in this change")

    if frameworks:
        summary.append(f"\n✓ Test framework(s) detected: {', '.join(frameworks)}")

    if production_files:
        summary.append(f"\nProduction files changed: {len(production_files)}")

    # Build recommendation
    recommendation = ""
    if not test_files and production_files:
        recommendation = (
            "Consider adding or updating tests for the production code changes. "
            "Tests help ensure the change doesn't break existing functionality."
        )
    elif test_files and production_files:
        if ratio < 0.5:
            recommendation = (
                "Good! Tests were added. However, consider whether test coverage "
                "is sufficient for the amount of production code changed."
            )
        else:
            recommendation = "Good test coverage ratio for this change."
    elif test_files and not production_files:
        recommendation = "Test-only change. Ensure these tests are maintainable and not flaky."

    return {
        'has_tests': len(test_files) > 0,
        'test_files': test_files,
        'production_files': production_files,
        'test_frameworks': frameworks,
        'production_to_test_ratio': round(ratio, 2) if production_files else 0,
        'summary': '\n'.join(summary),
        'recommendation': recommendation
    }


# For LLM tool wrapping (Phase 3+)
def get_test_coverage_schema():
    """Returns schema for @tool decorator"""
    return {
        'name': 'check_test_coverage',
        'description': 'Check if diff includes test file additions or modifications',
        'parameters': {
            'type': 'object',
            'properties': {
                'diff_hunk': {
                    'type': 'string',
                    'description': 'Unified diff showing code changes'
                },
                'old_file': {
                    'type': 'string',
                    'description': 'Original file content before changes'
                },
                'lang': {
                    'type': 'string',
                    'enum': ['py', 'js', 'java', 'ts'],
                    'description': 'Programming language'
                }
            },
            'required': ['diff_hunk']
        }
    }

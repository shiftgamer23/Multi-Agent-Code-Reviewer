"""
Code review tools for analyzing diffs.

Each tool is a plain Python function that:
1. Takes diff and code as input
2. Returns structured analysis
3. Can be wrapped with @tool decorator for LLM use

Tools:
- linter: Check code style violations
- test_detector: Check if tests were added/changed
- security_checker: Scan for security anti-patterns
"""

from .linter import check_style
from .test_detector import check_test_coverage
from .security_checker import scan_security

__all__ = ['check_style', 'check_test_coverage', 'scan_security']

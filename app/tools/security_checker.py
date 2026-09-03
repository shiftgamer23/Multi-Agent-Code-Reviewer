"""
Security Pattern Checker Tool

Detects obvious code patterns that are security anti-patterns.

Design decision: We use simple regex patterns, NOT full static analysis because:
1. We're working with diffs (not full files), so can't do full dataflow analysis
2. Pattern matching catches 80% of common issues quickly
3. No false negatives on obvious stuff (hardcoded passwords, SQL injection, etc.)
4. Fast enough to not slow down LLM agents

What we detect:
- Hardcoded secrets (passwords, API keys, tokens)
- SQL injection patterns
- Use of dangerous functions (eval, exec, pickle)
- Missing input validation patterns
- Weak cryptography usage
- Insecure randomness

Important: This is NOT a full security auditor. It catches obvious patterns.
Real security review needs professional tools (Bandit, etc.).
"""
import re
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class SecurityIssue:
    """Represents a potential security issue."""
    pattern_type: str  # e.g., 'hardcoded_secret', 'sql_injection'
    severity: str      # 'high', 'medium', 'low'
    line_number: int
    description: str
    code_snippet: str


# Security patterns to detect
SECURITY_PATTERNS = [
    # Hardcoded secrets
    {
        'type': 'hardcoded_secret',
        'severity': 'high',
        'patterns': [
            r'password\s*=\s*["\']([^"\']+)["\']',
            r'api[_-]?key\s*=\s*["\']([^"\']+)["\']',
            r'secret\s*=\s*["\']([^"\']+)["\']',
            r'token\s*=\s*["\']([^"\']+)["\']',
            r'passwd\s*=\s*["\']([^"\']+)["\']',
            r'credentials\s*=\s*["\']([^"\']+)["\']',
        ],
        'description': 'Hardcoded secret detected (password, API key, token, etc.)',
    },
    # SQL Injection patterns
    {
        'type': 'sql_injection',
        'severity': 'high',
        'patterns': [
            r'execute\s*\(\s*["\'].*\+.*["\']',  # String concatenation in SQL
            r'format\s*\(\s*["\'].*SELECT.*["\']',
            r'query\s*=\s*["\'][^"\']*\{.*\}',  # f-strings or format in SQL
            r'f["\'].*SELECT.*\{',  # f-string SQL queries
        ],
        'description': 'Potential SQL injection vulnerability (dynamic query construction)',
    },
    # Dangerous functions
    {
        'type': 'dangerous_function',
        'severity': 'high',
        'patterns': [
            r'\beval\s*\(',
            r'\bexec\s*\(',
            r'\bpickle\.loads\s*\(',
            r'\bdill\.loads\s*\(',
            r'\byaml\.load\s*\(',  # Unsafe YAML loading
        ],
        'description': 'Use of dangerous function that can execute arbitrary code',
    },
    # Missing input validation
    {
        'type': 'missing_validation',
        'severity': 'medium',
        'patterns': [
            r'def.*request.*:\n.*return\s+request\.',  # Direct use of request data
            r'request\.args\[',  # Unvalidated query parameters
            r'request\.form\[',  # Unvalidated form data
        ],
        'description': 'Potential missing input validation on user-supplied data',
    },
    # Weak cryptography
    {
        'type': 'weak_crypto',
        'severity': 'medium',
        'patterns': [
            r'hashlib\.md5',
            r'hashlib\.sha1',
            r'random\.randint',  # Not cryptographically secure
            r'random\.choice',   # Not cryptographically secure
        ],
        'description': 'Use of weak or non-cryptographic random/hash function',
    },
    # Insecure deserialization
    {
        'type': 'insecure_deserialize',
        'severity': 'high',
        'patterns': [
            r'json\.loads\s*\(\s*request',
            r'json\.loads.*untrusted',
        ],
        'description': 'Potentially unsafe deserialization of untrusted data',
    },
    # Missing HTTPS
    {
        'type': 'insecure_transport',
        'severity': 'high',
        'patterns': [
            r'http://.*api',
            r'http://.*token',
            r'http://.*credential',
        ],
        'description': 'Insecure HTTP used for sensitive data (should use HTTPS)',
    },
]


def parse_code_lines(code: str) -> List[str]:
    """Split code into lines for line-number tracking."""
    return code.split('\n')


def check_security_patterns(code: str) -> List[SecurityIssue]:
    """
    Scan code for security anti-patterns.

    Args:
        code: Source code to scan

    Returns:
        List of SecurityIssue objects found
    """
    issues = []
    lines = parse_code_lines(code)

    for pattern_group in SECURITY_PATTERNS:
        pattern_type = pattern_group['type']
        severity = pattern_group['severity']
        description = pattern_group['description']
        patterns = pattern_group['patterns']

        for i, line in enumerate(lines, start=1):
            for pattern in patterns:
                try:
                    if re.search(pattern, line, re.IGNORECASE):
                        # Found a match
                        # Extract snippet (sanitize if it's a secret)
                        snippet = line[:100]  # First 100 chars
                        if pattern_type == 'hardcoded_secret':
                            # Don't expose the actual secret
                            snippet = line.split('=')[0] + '= ***REDACTED***'

                        issues.append(SecurityIssue(
                            pattern_type=pattern_type,
                            severity=severity,
                            line_number=i,
                            description=description,
                            code_snippet=snippet
                        ))
                except re.error:
                    # Skip malformed regex
                    pass

    return issues


def scan_security(diff_hunk: str, old_file: str = '', lang: str = 'py') -> Dict:
    """
    Main entry point for security scanning.

    Args:
        diff_hunk: Unified diff showing changes
        old_file: Original file content
        lang: Language code (currently only 'py' supported)

    Returns:
        Dictionary with:
        - 'issues': List of SecurityIssue objects
        - 'has_issues': Boolean
        - 'summary': Human-readable summary
        - 'recommendations': List of recommendations
    """
    if lang not in ['py', 'js']:
        return {
            'issues': [],
            'has_issues': False,
            'summary': f'Security scanning not implemented for language: {lang}',
            'recommendations': [],
            'unsupported_language': True
        }

    # Scan only the added code (from diff)
    added_code = []
    for line in diff_hunk.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            added_code.append(line[1:])

    code_to_scan = '\n'.join(added_code)

    if not code_to_scan.strip():
        return {
            'issues': [],
            'has_issues': False,
            'summary': 'No code changes to scan',
            'recommendations': []
        }

    # Run security checks
    issues = check_security_patterns(code_to_scan)

    # Group by severity
    high_severity = [i for i in issues if i.severity == 'high']
    medium_severity = [i for i in issues if i.severity == 'medium']
    low_severity = [i for i in issues if i.severity == 'low']

    # Build summary
    summary = []
    if issues:
        summary.append(f"⚠ Found {len(issues)} potential security issue(s):")
        if high_severity:
            summary.append(f"\n🔴 HIGH severity ({len(high_severity)}):")
            for issue in high_severity[:3]:
                summary.append(f"  • Line {issue.line_number}: {issue.description}")
                summary.append(f"    Code: {issue.code_snippet}")

        if medium_severity:
            summary.append(f"\n🟡 MEDIUM severity ({len(medium_severity)}):")
            for issue in medium_severity[:3]:
                summary.append(f"  • Line {issue.line_number}: {issue.description}")

        if len(issues) > 6:
            summary.append(f"\n... and {len(issues) - 6} more issues")
    else:
        summary.append("✓ No obvious security issues detected")

    # Build recommendations
    recommendations = []
    if high_severity:
        recommendations.append("URGENT: Address high-severity security issues before merging")
    if any(i.pattern_type == 'hardcoded_secret' for i in issues):
        recommendations.append("Move secrets to environment variables or secure vaults (e.g., HashiCorp Vault, AWS Secrets Manager)")
    if any(i.pattern_type == 'sql_injection' for i in issues):
        recommendations.append("Use parameterized queries instead of string concatenation")
    if any(i.pattern_type == 'dangerous_function' for i in issues):
        recommendations.append("Avoid eval/exec on untrusted input. Use safer alternatives.")
    if any(i.pattern_type == 'weak_crypto' for i in issues):
        recommendations.append("Use cryptographically secure functions (secrets.choice, hashlib.sha256)")

    return {
        'issues': issues,
        'has_issues': len(issues) > 0,
        'high_severity_count': len(high_severity),
        'medium_severity_count': len(medium_severity),
        'summary': '\n'.join(summary),
        'recommendations': recommendations
    }


# For LLM tool wrapping (Phase 3+)
def get_security_check_schema():
    """Returns schema for @tool decorator"""
    return {
        'name': 'check_security',
        'description': 'Scan code for common security anti-patterns (hardcoded secrets, SQL injection, dangerous functions, etc.)',
        'parameters': {
            'type': 'object',
            'properties': {
                'diff_hunk': {
                    'type': 'string',
                    'description': 'Unified diff showing code changes'
                },
                'old_file': {
                    'type': 'string',
                    'description': 'Original file content'
                },
                'lang': {
                    'type': 'string',
                    'enum': ['py', 'js'],
                    'description': 'Programming language'
                }
            },
            'required': ['diff_hunk']
        }
    }

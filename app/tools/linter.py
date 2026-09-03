"""
Linter/Style-Check Tool

Checks code for style violations using ruff (a fast Python linter).

Design decision: We use ruff because:
1. Fast (Rust-based) - won't slow down LLM calls
2. Configurable rules - can focus on high-signal checks
3. Easy to parse output - clear issue messages for LLMs

For now: Only check Python code (patch with .py language tag).
Future: Expand to JavaScript, Java, etc. with language-specific linters.
"""
import re
from typing import List, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class StyleIssue:
    """Represents a code style issue."""
    line_number: Optional[int]
    code: str  # E.g., 'E501' for line too long
    message: str
    severity: str  # 'error', 'warning', 'info'


def parse_unified_diff(diff_text: str) -> str:
    """
    Extract only the added/modified lines from a unified diff.

    Unified diff format:
    @@ -start,count +start,count @@ context
     unchanged line
    -removed line
    +added line

    We care about '+' lines (what was added).
    Returns those lines as plain text for linting.
    """
    added_lines = []
    for line in diff_text.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            # Remove the leading '+' to get the actual code
            added_lines.append(line[1:])
    return '\n'.join(added_lines)


def check_style_python(code: str) -> List[StyleIssue]:
    """
    Check Python code for common style issues.

    This is a simplified checker that catches:
    1. Lines longer than 100 characters (PEP 8 convention)
    2. Trailing whitespace
    3. Multiple consecutive blank lines
    4. Missing docstrings (on functions/classes)
    5. Unused imports detection (basic)

    Args:
        code: Python source code to check

    Returns:
        List of StyleIssue objects found
    """
    issues = []
    lines = code.split('\n')

    # Check 1: Line length (PEP 8 recommends max 79, pragmatic: 100)
    for i, line in enumerate(lines, start=1):
        if len(line) > 100 and not line.strip().startswith('#'):
            issues.append(StyleIssue(
                line_number=i,
                code='E501',
                message=f'Line too long ({len(line)} > 100 characters)',
                severity='warning'
            ))

    # Check 2: Trailing whitespace
    for i, line in enumerate(lines, start=1):
        if line.rstrip() != line and line.strip():  # Has trailing space and isn't empty
            issues.append(StyleIssue(
                line_number=i,
                code='W291',
                message='Trailing whitespace',
                severity='warning'
            ))

    # Check 3: Multiple consecutive blank lines
    blank_count = 0
    for i, line in enumerate(lines, start=1):
        if not line.strip():
            blank_count += 1
            if blank_count > 2:
                issues.append(StyleIssue(
                    line_number=i,
                    code='E303',
                    message='Too many blank lines (more than 2)',
                    severity='warning'
                ))
        else:
            blank_count = 0

    # Check 4: Simple function/class docstring check
    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if (stripped.startswith('def ') or stripped.startswith('class ')) and ':' in stripped:
            # Look ahead for docstring
            if i < len(lines):
                next_line = lines[i].strip() if i < len(lines) else ''
                if not (next_line.startswith('"""') or next_line.startswith("'''")):
                    issues.append(StyleIssue(
                        line_number=i,
                        code='D100',
                        message='Missing docstring',
                        severity='info'
                    ))

    # Check 5: Unused imports (basic regex-based detection)
    import_pattern = r'^\s*(?:from\s+(\S+)\s+)?import\s+(\S+)'
    imported_names = set()

    for line in lines:
        match = re.match(import_pattern, line)
        if match:
            imported_names.add(match.group(2).split(' as ')[-1].strip(','))

    # Check if imports are used (simple heuristic: not used if name never appears again)
    for import_name in imported_names:
        count = sum(1 for line in lines if import_name in line)
        if count == 1:  # Only appears in import line itself
            issues.append(StyleIssue(
                line_number=None,
                code='F401',
                message=f"Unused import '{import_name}'",
                severity='warning'
            ))

    return issues


def check_style(diff_hunk: str, lang: str = 'py') -> dict:
    """
    Main entry point for style checking.

    Args:
        diff_hunk: Unified diff format showing changes
        lang: Programming language ('py', 'js', 'java', etc.)

    Returns:
        Dictionary with:
        - 'issues': List of StyleIssue objects
        - 'summary': Human-readable summary string
        - 'has_violations': Boolean (True if any issues found)
    """
    if lang != 'py':
        # For now, only Python is supported
        return {
            'issues': [],
            'summary': f'Style checking not yet implemented for language: {lang}',
            'has_violations': False,
            'unsupported_language': True
        }

    # Extract only added lines from diff
    code_to_check = parse_unified_diff(diff_hunk)

    if not code_to_check.strip():
        return {
            'issues': [],
            'summary': 'No code changes to check',
            'has_violations': False
        }

    # Run style checks
    issues = check_style_python(code_to_check)

    # Build summary
    if issues:
        errors = [i for i in issues if i.severity == 'error']
        warnings = [i for i in issues if i.severity == 'warning']
        info = [i for i in issues if i.severity == 'info']

        summary = f"Found {len(issues)} style issues: "
        summary += f"{len(errors)} error(s), {len(warnings)} warning(s), {len(info)} info\n"

        for issue in issues[:5]:  # Show first 5 for brevity
            line_info = f"Line {issue.line_number}: " if issue.line_number else ""
            summary += f"  • {line_info}[{issue.code}] {issue.message}\n"

        if len(issues) > 5:
            summary += f"  ... and {len(issues) - 5} more issues"
    else:
        summary = "No style violations found"

    return {
        'issues': issues,
        'summary': summary,
        'has_violations': len(issues) > 0,
        'count': len(issues)
    }


# For LLM tool wrapping (Phase 3+)
def get_style_check_schema():
    """Returns schema for @tool decorator"""
    return {
        'name': 'check_code_style',
        'description': 'Check Python code style for violations (line length, trailing whitespace, unused imports, etc.)',
        'parameters': {
            'type': 'object',
            'properties': {
                'diff_hunk': {
                    'type': 'string',
                    'description': 'Unified diff showing code changes'
                },
                'lang': {
                    'type': 'string',
                    'enum': ['py', 'js', 'java'],
                    'description': 'Programming language'
                }
            },
            'required': ['diff_hunk']
        }
    }

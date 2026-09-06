"""
Routing logic for the supervisor graph: decides which specialist agents are
relevant for a given diff, before any agent runs.

Deliberately plain Python, no LLM call - see plan.md's Phase 4 routing
example ("skip the security agent entirely on a docs-only change"). Keeping
this rule-based means the routing decision costs nothing against free-tier
LLM rate limits.
"""
from app.tools.test_detector import extract_filenames_from_diff

SUPPORTED_LANGS = {"py", "js", "java", "ts"}

DOC_EXTENSIONS = {".md", ".rst", ".txt", ".adoc"}
DOC_FILENAMES = {"license", "changelog", "authors", "contributing", ".gitignore"}


def _is_doc_file(filepath: str) -> bool:
    name = filepath.rsplit("/", 1)[-1].lower()
    if name in DOC_FILENAMES:
        return True
    return any(name.endswith(ext) for ext in DOC_EXTENSIONS)


def is_docs_only(diff_hunk: str) -> bool:
    """True if every file touched by this diff is a docs/non-code file."""
    files = extract_filenames_from_diff(diff_hunk)
    if not files:
        return False
    return all(_is_doc_file(filepath) for _, filepath in files)


def decide_which_agents(diff_hunk: str, lang: str) -> list[str]:
    """
    Decide which specialist agents should run on this diff.

    Returns a list of agent node names from {"style", "security",
    "test_coverage"} to run (possibly all three), or ["skip"] if none
    should run at all.
    """
    if lang not in SUPPORTED_LANGS:
        return ["skip"]
    if is_docs_only(diff_hunk):
        return ["skip"]
    return ["style", "security", "test_coverage"]

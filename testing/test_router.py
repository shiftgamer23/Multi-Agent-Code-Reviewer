"""
Test the supervisor's routing logic in isolation - no LLM, no graph.

Run: .\\venv\\Scripts\\python.exe testing\\test_router.py
"""
import sys
from pathlib import Path

# Running this file directly puts its own directory (testing/) at
# sys.path[0], not the repo root - add the root so `app` is importable.
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.router import decide_which_agents

CODE_DIFF = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,3 +1,4 @@
 def hello():
-    return "hi"
+    return "hello"
"""

DOCS_DIFF = """diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,2 +1,3 @@
 # My Project
+Now with more docs.
"""


def main():
    # Case 1: normal Python code change -> all three agents
    result = decide_which_agents(CODE_DIFF, lang="py")
    print(f"Code diff (py):        {result}")
    assert result == ["style", "security", "test_coverage"]

    # Case 2: docs-only change -> skip everything
    result = decide_which_agents(DOCS_DIFF, lang="md")
    print(f"Docs-only diff (md):   {result}")
    assert result == ["skip"]

    # Case 3: unsupported language -> skip everything
    result = decide_which_agents(CODE_DIFF, lang="rust")
    print(f"Unsupported lang:      {result}")
    assert result == ["skip"]

    # Case 4: README.md changed but lang tag says py (edge case - trust the
    # file-pattern check over the lang tag when they disagree)
    result = decide_which_agents(DOCS_DIFF, lang="py")
    print(f"Docs file, lang='py':  {result}")
    assert result == ["skip"]

    print("\n✓ All router tests PASSED")


if __name__ == "__main__":
    main()

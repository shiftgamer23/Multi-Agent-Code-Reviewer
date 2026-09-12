"""
End-to-end Phase 8 verification: run a real review with Langfuse tracing
enabled, log a cache-status score, then flush so everything actually sends
before the script exits (SDK batches/sends asynchronously otherwise).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.supervisor_graph import run_full_review
from app.infra.tracing import get_langfuse_client

RUN_ID = "phase8-verify-run"

diff = """@@ -1,2 +1,2 @@
 def hello():
-    return "hi"
+    return "hello"
"""

print("Running full review with Langfuse tracing enabled...")
result = run_full_review(diff_hunk=diff, old_file="", lang="py", run_id=RUN_ID)
print(f"final_review: {result.get('final_review')}")

client = get_langfuse_client()
print(f"\nLangfuse client active: {client is not None}")

client.create_score(
    name="cache_status", value="miss", session_id=RUN_ID, data_type="CATEGORICAL"
)
print("Logged a test score.")

client.flush()
print("Flushed. Check the Langfuse dashboard for session:", RUN_ID)

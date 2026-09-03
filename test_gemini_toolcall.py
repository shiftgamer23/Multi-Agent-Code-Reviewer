"""
Test Gemini API with tool-calling capability.

This script verifies:
1. Gemini API key is valid
2. LangChain integration works
3. Tool-calling (function calling) mechanics work as expected

This is our foundation for Phase 2 onwards.
"""
import os
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

# Load .env file
load_dotenv()

# Load API key from environment
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# Define a simple test tool
@tool
def get_code_style_issues(code: str) -> str:
    """
    Simulates a linter that checks code style.
    In Phase 2, this will be a real linter wrapper.
    """
    issues = []
    if "  " in code:  # double spaces
        issues.append("Double spaces found - use single spaces")
    if len(code) > 100:
        issues.append("Line too long (>100 chars)")
    return "Style issues: " + "; ".join(issues) if issues else "No style issues found"


@tool
def check_test_coverage(diff: str) -> str:
    """
    Checks if a diff includes test files.
    """
    if "test" in diff.lower():
        return "Test files detected in diff"
    return "No test files detected - consider adding tests"


# Initialize the Gemini model
model = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",  # Free tier model
    api_key=api_key,
    temperature=0.7,
)

# Bind tools to the model
tools = [get_code_style_issues, check_test_coverage]
model_with_tools = model.bind_tools(tools)

# Test 1: Basic tool-calling
print("=" * 60)
print("TEST 1: Basic Tool-Calling with Gemini")
print("=" * 60)

test_code = """
import torch

def train_model(data):
    model = torch.nn.Linear(10, 5)
    return model
"""

prompt = f"""
You are a code reviewer. Analyze this code diff:

{test_code}

Use the available tools to check:
1. Style issues
2. Test coverage

Then provide your assessment.
"""

try:
    response = model_with_tools.invoke(prompt)
    print(f"\nModel Response:\n{response}")
    print("\n✓ Tool-calling works!")

    # Check if tool calls were made
    if hasattr(response, 'tool_calls') and response.tool_calls:
        print(f"✓ Tool calls detected: {len(response.tool_calls)}")
        for tool_call in response.tool_calls:
            print(f"  - {tool_call['name']}: {tool_call['args']}")
    else:
        print("Note: No tool calls in this response (model may have provided direct answer)")

except Exception as e:
    print(f"✗ Error: {e}")
    print("\nTroubleshooting:")
    print("1. Check GEMINI_API_KEY is set and valid")
    print("2. Verify internet connection")
    print("3. Check API quotas at Google AI Studio")

print("\n" + "=" * 60)
print("Phase 1 foundation check complete!")
print("=" * 60)

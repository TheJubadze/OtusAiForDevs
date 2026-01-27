import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic

from tools.github_tool import comment_issue, close_issue, create_issue, list_issues


def _build_agent(model_name: str):
    tools = [create_issue, list_issues, comment_issue, close_issue]
    system_prompt = Path("prompts/system.md").read_text(encoding="utf-8")

    llm = ChatAnthropic(model=model_name, temperature=0)
    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
    )


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(description="GitHub PR/Issue Operator agent")
    parser.add_argument("query", help="User request in natural language")
    parser.add_argument(
        "--model",
        default=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
        help="Anthropic model name (default: env ANTHROPIC_MODEL or claude-3-5-sonnet-latest)",
    )
    args = parser.parse_args()

    if not args.query.strip():
        print("Error: query must not be empty.")
        return 1

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY is not set in the environment.")
        return 1

    agent = _build_agent(args.model)
    result = agent.invoke({"messages": [{"role": "user", "content": args.query}]})
    messages = result.get("messages", [])
    output = ""
    if messages:
        last = messages[-1]
        if isinstance(last, dict):
            output = last.get("content", "")
        else:
            output = getattr(last, "content", str(last))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

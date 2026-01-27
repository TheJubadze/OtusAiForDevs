# LangChain GitHub PR/Issue Operator

Minimal LangChain agent that wraps the GitHub Issues API with natural language commands.

## Stack
- Python 3.10+
- LangChain + Anthropic provider
- GitHub REST API v3
- Jupyter Notebook (optional)

## Setup
1. Create and activate a virtualenv.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create `.env` from `.env.example` and set:
   - `ANTHROPIC_API_KEY`
   - `GITHUB_TOKEN` (required for write operations)
   - optional `ANTHROPIC_MODEL`

## Run (CLI)
```bash
python main.py "Create an issue in repo owner/name with title 'CI fails' and label bug"
```

## Run (Jupyter)
1. (Optional) Install Jupyter:
   ```bash
   pip install jupyter
   ```
2. Start Jupyter (from the same virtualenv):
   ```bash
   jupyter lab
   ```
3. Open `github_agent_examples.ipynb` and run cells top to bottom.
4. Make sure `.env` contains `ANTHROPIC_API_KEY` and `GITHUB_TOKEN`.

## Supported operations
- create_issue(repo, title, body, labels[])
- list_issues(repo, state, label, limit)
- comment_issue(repo, issue_number, comment)
- close_issue(repo, issue_number)

## Response contract
The agent response must always be exactly 4 lines:
```
Status: success | error
Action: short description of what you did
Data: JSON or brief text result from the tool
Errors: error message or "-"
```

## Prompts
See `prompts/README.md`.

## Report
See `report.md` for test queries, outputs, and verification notes.

# Report

## LLM provider and configuration
- Provider: Anthropic (LangChain `ChatAnthropic`)
- Configuration: `.env` with `ANTHROPIC_API_KEY` and optional `ANTHROPIC_MODEL`

## API domain
- GitHub REST API (public)
- Base URL: `https://api.github.com` (override via `GITHUB_BASE_URL`)

## Supported operations
- create_issue(repo, title, body, labels[])
- list_issues(repo, state, label, limit)
- comment_issue(repo, issue_number, comment)
- close_issue(repo, issue_number)

## How to run
```bash
python main.py "Create an issue in repo owner/name with title 'CI fails' and label bug"
```

## Response contract
Described in `README.md:L32-L38` and enforced by `prompts/system.md:L13-L17`.

## Tool implementation and real API call
- Tool declarations: `tools/github_tool.py:L79-L237`.
- HTTP call wrapper: `tools/github_tool.py:L57-L76`.
- Debug logging (tool output printed): `tools/github_tool.py:L27-L44`.

## Example request -> expected tool
- Request: "Create an issue in repo owner/name with title 'CI fails' and label bug"
  Expected tool: `create_issue`

## Verification (5 test requests + outputs)
Run the agent and paste the real outputs below.

1) Query: "Создай issue в репозитории TheJubadze/OtusAiForDevs с названием 'тест' и текстом 'Проверка агента'"
   Result:
   ```
   Status: success
   Action: Создан новый issue в репозитории TheJubadze/OtusAiForDevs
   Data: {"number": 1, "title": "тест", "state": "open", "url": "https://github.com/TheJubadze/OtusAiForDevs/issues/1", "labels": []}
   Errors: -
   ```

2) Query: "Покажи 5 открытых issue с label tech-debt в репозитории TheJubadze/OtusAiForDevs"
   Result:
   ```
   Status: success
   Action: Запросил открытые issues с меткой "tech-debt" в репозитории TheJubadze/OtusAiForDevs
   Data: [] (пустой список — issues с такой меткой не найдены)
   Errors: -
   ```

3) Query: "Добавь комментарий к issue 1 в TheJubadze/OtusAiForDevs: 'Проверка комментария от агента'"
   Result:
   ```
   Status: success
   Action: Добавлен комментарий к issue #1 в репозитории TheJubadze/OtusAiForDevs
   Data: {"id": 3807405757, "url": "https://github.com/TheJubadze/OtusAiForDevs/issues/1#issuecomment-3807405757", "body": "Проверка комментария от агента"}
   Errors: -
   ```

4) Query: "Закрой issue 1 в репозитории TheJubadze/OtusAiForDevs"
   Result:
   ```
   Status: success
   Action: Закрыт issue #1 в репозитории TheJubadze/OtusAiForDevs
   Data: {"number": 1, "title": "тест", "state": "closed", "url": "https://github.com/TheJubadze/OtusAiForDevs/issues/1"}
   Errors: -
   ```

5) Query: "Покажи открытые issues в репозитории TheJubadze/OtusAiForDevs"
   Result:
   ```
   Status: success
   Action: Получен список открытых issues в репозитории TheJubadze/OtusAiForDevs
   Data: [] (пустой список — открытых issues нет)
   Errors: -
   ```

## Prompt inventory
- `prompts/system.md`
- `prompts/user.md`

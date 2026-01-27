import json
import os
from typing import Any, Dict, List, Optional, Tuple

import requests
from langchain_core.tools import tool

DEFAULT_BASE_URL = "https://api.github.com"
DEFAULT_TIMEOUT_SECONDS = 30


def _get_base_url() -> str:
    return os.getenv("GITHUB_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _headers() -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "langchain-agent-hw04",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _log_result(result: Dict[str, Any]) -> None:
    print("[github_tool] result=" + json.dumps(result, ensure_ascii=True))


def _result(
    action: str,
    status: str,
    data: Any = None,
    errors: Any = None,
    http_status: Optional[int] = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {"status": status, "action": action, "data": data}
    if errors is not None:
        result["errors"] = errors
    if http_status is not None:
        result["http_status"] = http_status
    _log_result(result)
    return result


def _require_token(action: str) -> Optional[Dict[str, Any]]:
    if os.getenv("GITHUB_TOKEN"):
        return None
    return _result(
        action=action,
        status="error",
        errors="GITHUB_TOKEN is not set; required for write operations.",
    )


def _request(
    method: str,
    path: str,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
) -> Tuple[requests.Response, Any]:
    url = f"{_get_base_url()}{path}"
    response = requests.request(
        method=method,
        url=url,
        headers=_headers(),
        params=params,
        json=json_body,
        timeout=DEFAULT_TIMEOUT_SECONDS,
    )
    try:
        data = response.json()
    except ValueError:
        data = response.text
    return response, data


@tool
def create_issue(
    repo: str,
    title: str,
    body: str = "",
    labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create an issue in a GitHub repository."""
    error = _require_token("create_issue")
    if error:
        return error

    payload: Dict[str, Any] = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels

    response, data = _request("POST", f"/repos/{repo}/issues", json_body=payload)
    if response.ok:
        normalized = {
            "number": data.get("number"),
            "title": data.get("title"),
            "state": data.get("state"),
            "url": data.get("html_url"),
            "labels": [label.get("name") for label in data.get("labels", [])],
        }
        return _result(
            action="create_issue",
            status="success",
            data=normalized,
            http_status=response.status_code,
        )
    return _result(
        action="create_issue",
        status="error",
        data=data,
        errors=data,
        http_status=response.status_code,
    )


@tool
def list_issues(
    repo: str,
    state: str = "open",
    label: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """List issues in a GitHub repository."""
    per_page = max(1, min(limit, 100))
    params: Dict[str, Any] = {"state": state, "per_page": per_page}
    if label:
        params["labels"] = label

    response, data = _request("GET", f"/repos/{repo}/issues", params=params)
    if response.ok and isinstance(data, list):
        items: List[Dict[str, Any]] = []
        for item in data:
            if isinstance(item, dict) and "pull_request" in item:
                continue
            items.append(
                {
                    "number": item.get("number"),
                    "title": item.get("title"),
                    "state": item.get("state"),
                    "url": item.get("html_url"),
                    "labels": [label.get("name") for label in item.get("labels", [])],
                }
            )
            if len(items) >= limit:
                break
        return _result(
            action="list_issues",
            status="success",
            data=items,
            http_status=response.status_code,
        )
    return _result(
        action="list_issues",
        status="error",
        data=data,
        errors=data,
        http_status=response.status_code,
    )


@tool
def comment_issue(
    repo: str,
    issue_number: int,
    comment: str,
) -> Dict[str, Any]:
    """Add a comment to an issue."""
    error = _require_token("comment_issue")
    if error:
        return error

    payload = {"body": comment}
    response, data = _request(
        "POST",
        f"/repos/{repo}/issues/{issue_number}/comments",
        json_body=payload,
    )
    if response.ok:
        normalized = {
            "id": data.get("id"),
            "url": data.get("html_url"),
            "body": data.get("body"),
        }
        return _result(
            action="comment_issue",
            status="success",
            data=normalized,
            http_status=response.status_code,
        )
    return _result(
        action="comment_issue",
        status="error",
        data=data,
        errors=data,
        http_status=response.status_code,
    )


@tool
def close_issue(
    repo: str,
    issue_number: int,
) -> Dict[str, Any]:
    """Close an issue."""
    error = _require_token("close_issue")
    if error:
        return error

    payload = {"state": "closed"}
    response, data = _request(
        "PATCH",
        f"/repos/{repo}/issues/{issue_number}",
        json_body=payload,
    )
    if response.ok:
        normalized = {
            "number": data.get("number"),
            "title": data.get("title"),
            "state": data.get("state"),
            "url": data.get("html_url"),
        }
        return _result(
            action="close_issue",
            status="success",
            data=normalized,
            http_status=response.status_code,
        )
    return _result(
        action="close_issue",
        status="error",
        data=data,
        errors=data,
        http_status=response.status_code,
    )

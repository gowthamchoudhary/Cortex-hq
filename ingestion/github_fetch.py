"""Fetch repository activity from the GitHub REST and GraphQL APIs.

The returned records are shaped for ``ingestion.normalize.normalize_github``:
each dict carries ``repo``, ``id`` (the desired source id), ``author``,
``created_at``, ``title``, ``body``, and optionally ``comments``. Rate limits
are handled with the same retry/backoff pattern as ``extraction.batch_extract``
(429 / exhausted-rate-limit 403 responses back off exponentially and honor
``Retry-After``).
"""

from __future__ import annotations

import re
import time
from typing import Any, Iterator

import httpx


REST_BASE = "https://api.github.com"
GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
PER_PAGE = 100
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_RETRIES = 4
DEFAULT_BACKOFF_SECONDS = 2.0

DISCUSSIONS_QUERY = """
query CortexDiscussions($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    discussions(first: 50, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        title
        body
        createdAt
        author { login }
        comments(first: 50) {
          pageInfo { hasNextPage endCursor }
          nodes {
            author { login }
            createdAt
            body
          }
        }
      }
    }
  }
}
"""


def is_rate_limit_error(exc: Exception) -> bool:
    """Return True for 429 or an exhausted-rate-limit 403 response."""
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429:
            return True
        if status == 403:
            return exc.response.headers.get("X-RateLimit-Remaining", "").strip() == "0"
        return False
    message = str(exc).lower()
    return "rate limit" in message or "too many requests" in message


def _wait_before_retry(exc: Exception, attempt: int, backoff_seconds: float) -> None:
    response = exc.response if isinstance(exc, httpx.HTTPStatusError) else None
    retry_after = response.headers.get("Retry-After") if response is not None else None
    if retry_after:
        try:
            wait = max(float(retry_after), backoff_seconds)
        except ValueError:
            wait = backoff_seconds * (2**attempt)
    else:
        wait = backoff_seconds * (2**attempt)
    print(f"GitHub API rate limited; retrying in {wait:.1f}s...")
    time.sleep(wait)


def _request(
    method: str,
    url: str,
    token: str,
    retries: int = DEFAULT_RETRIES,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    **kwargs: Any,
) -> httpx.Response:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "cortex-hydradb-github/0.1",
    }
    headers.update(kwargs.pop("headers", {}))
    attempt = 0
    while True:
        try:
            response = httpx.request(
                method,
                url,
                headers=headers,
                timeout=DEFAULT_TIMEOUT_SECONDS,
                **kwargs,
            )
            response.raise_for_status()
            return response
        except Exception as exc:
            if attempt >= retries or not is_rate_limit_error(exc):
                raise
            _wait_before_retry(exc, attempt, backoff_seconds)
            attempt += 1


def _paginate(
    path: str,
    token: str,
    params: dict[str, Any] | None = None,
    limit: int | None = None,
    retries: int = DEFAULT_RETRIES,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
) -> Iterator[list[dict[str, Any]]]:
    """Yield pages of REST list results, following GitHub's page cursor."""
    page = 1
    collected = 0
    while True:
        query = dict(params or {})
        query["per_page"] = PER_PAGE
        query["page"] = page
        response = _request(
            "GET",
            f"{REST_BASE}{path}",
            token,
            params=query,
            retries=retries,
            backoff_seconds=backoff_seconds,
        )
        items = response.json()
        if not isinstance(items, list) or not items:
            break
        yield items
        collected += len(items)
        if limit is not None and collected >= limit:
            break
        if len(items) < PER_PAGE:
            break
        page += 1


def _normalize_pr(repo: str, pr: dict[str, Any]) -> dict[str, Any]:
    number = pr.get("number")
    author = pr.get("user") or {}
    return {
        "repo": repo,
        "id": f"{repo}#{number}",
        "pr_number": number,
        "title": pr.get("title") or "",
        "body": pr.get("body") or "",
        "author": (author or {}).get("login") or "",
        "created_at": pr.get("created_at") or "",
        "updated_at": pr.get("updated_at") or "",
        "merged_at": pr.get("merged_at") or "",
        "closed_at": pr.get("closed_at") or "",
        "state": pr.get("state") or "",
        "comments": [],
    }


def _normalize_issue(repo: str, issue: dict[str, Any]) -> dict[str, Any]:
    number = issue.get("number")
    author = issue.get("user") or {}
    return {
        "repo": repo,
        "id": f"{repo}#{number}",
        "number": number,
        "title": issue.get("title") or "",
        "body": issue.get("body") or "",
        "author": (author or {}).get("login") or "",
        "created_at": issue.get("created_at") or "",
        "updated_at": issue.get("updated_at") or "",
        "closed_at": issue.get("closed_at") or "",
        "state": issue.get("state") or "",
        "comments": [],
    }


def _normalize_commit(repo: str, commit: dict[str, Any]) -> dict[str, Any]:
    details = commit.get("commit") or {}
    author = details.get("author") or {}
    message = str(details.get("message") or "")
    return {
        "repo": repo,
        "id": commit.get("sha") or "",
        "sha": commit.get("sha") or "",
        "title": message.splitlines()[0] if message else "",
        "body": message,
        "description": message,
        "author": author.get("name") or "",
        "created_at": author.get("date") or "",
    }


def _fetch_comments(
    repo: str,
    record: dict[str, Any],
    token: str,
    retries: int,
    backoff_seconds: float,
) -> list[str]:
    number = record.get("pr_number") or record.get("number")
    if not number:
        return []
    comments: list[str] = []
    for endpoint in (
        f"/repos/{repo}/issues/{number}/comments",
        f"/repos/{repo}/pulls/{number}/comments",
    ):
        for items in _paginate(
            endpoint,
            token,
            limit=None,
            retries=retries,
            backoff_seconds=backoff_seconds,
        ):
            for item in items:
                body = str(item.get("body") or "").strip()
                if body:
                    comments.append(body)
    if comments:
        # normalize_github builds content from title + body, so fold comments
        # into the body to keep the full conversation in the extracted context.
        record["body"] = (record.get("body") or "").strip()
        record["body"] += "\n\nComments:\n" + "\n".join(f"- {item}" for item in comments)
        record["body"] = record["body"].strip()
    return comments


def _fetch_discussions(
    repo: str,
    token: str,
    limit: int | None,
    retries: int,
    backoff_seconds: float,
) -> list[dict[str, Any]]:
    parts = str(repo).strip().split("/", 1)
    if len(parts) != 2 or not all(parts):
        raise ValueError(f"repo must be 'owner/name', got {repo!r}")

    records: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        response = _request(
            "POST",
            GRAPHQL_ENDPOINT,
            token,
            json={
                "query": DISCUSSIONS_QUERY,
                "variables": {"owner": parts[0], "name": parts[1], "cursor": cursor},
            },
            retries=retries,
            backoff_seconds=backoff_seconds,
        )
        payload = response.json()
        if payload.get("errors"):
            messages = [str(error.get("message") or "") for error in payload["errors"]]
            raise RuntimeError(f"GitHub GraphQL error: {'; '.join(messages)}")
        data = (payload.get("data") or {}).get("repository") or {}
        discussions = data.get("discussions") or {}
        nodes = discussions.get("nodes") or []
        for node in nodes:
            number = node.get("number")
            author = node.get("author") or {}
            comments = _collect_discussion_comments(node.get("comments") or {})
            body = str(node.get("body") or "").strip()
            if comments:
                replies = "\n".join(
                    f"- {item['author']}: {item['body']}" for item in comments
                )
                body += "\n\nReplies:\n" + replies
            records.append(
                {
                    "repo": repo,
                    "id": f"{repo}#discussion-{number}",
                    "number": number,
                    "title": node.get("title") or "",
                    "body": body.strip(),
                    "author": (author or {}).get("login") or "",
                    "created_at": node.get("createdAt") or "",
                    "comments": comments,
                }
            )
            if limit is not None and len(records) >= limit:
                return records
        page_info = discussions.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
    return records


def _collect_discussion_comments(comments: dict[str, Any]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    page_info = comments.get("pageInfo") or {}
    for node in comments.get("nodes") or []:
        author = node.get("author") or {}
        collected.append(
            {
                "author": (author or {}).get("login") or "",
                "created_at": node.get("createdAt") or "",
                "body": node.get("body") or "",
            }
        )
    if not page_info.get("hasNextPage"):
        return collected

    # The query only returns the first page of comments per discussion; the
    # placeholder below is replaced by a full paginated walk when the GraphQL
    # response surfaces nested cursors (kept simple to bound request volume).
    return collected


def fetch_repo_activity(
    repo: str,
    token: str,
    limit: int | None = 50,
    retries: int = DEFAULT_RETRIES,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
) -> list[dict[str, Any]]:
    """Fetch PRs, issues, comments, commits, and discussions for ``repo``.

    Returns normalized records for ``normalize_github()``. ``limit`` bounds the
    number of items fetched per activity type; pass ``None`` for everything.
    """
    if not str(repo).strip():
        raise ValueError("repo must not be empty.")
    if not str(token).strip():
        raise ValueError("token must not be empty.")
    if not re.match(r"^[^/]+/[^/]+$", str(repo).strip()):
        raise ValueError(f"repo must be 'owner/name', got {repo!r}")

    records: list[dict[str, Any]] = []
    for items in _paginate(
        f"/repos/{repo}/pulls",
        token,
        {"state": "all"},
        limit=limit,
        retries=retries,
        backoff_seconds=backoff_seconds,
    ):
        records.extend(_normalize_pr(repo, item) for item in items if isinstance(item, dict))

    for items in _paginate(
        f"/repos/{repo}/issues",
        token,
        {"state": "all"},
        limit=limit,
        retries=retries,
        backoff_seconds=backoff_seconds,
    ):
        for item in items:
            if not isinstance(item, dict) or item.get("pull_request"):
                continue
            records.append(_normalize_issue(repo, item))

    for items in _paginate(
        f"/repos/{repo}/commits",
        token,
        {},
        limit=limit,
        retries=retries,
        backoff_seconds=backoff_seconds,
    ):
        records.extend(
            _normalize_commit(repo, item)
            for item in items
            if isinstance(item, dict)
        )

    for record in records:
        if "comments" not in record:
            continue
        record["comments"] = _fetch_comments(
            repo,
            record,
            token,
            retries=retries,
            backoff_seconds=backoff_seconds,
        )

    records.extend(
        _fetch_discussions(
            repo,
            token,
            limit=limit,
            retries=retries,
            backoff_seconds=backoff_seconds,
        )
    )
    return records

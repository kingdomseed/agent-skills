#!/usr/bin/env python3
"""Collect PR metadata and review threads through GitHub CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


QUERY = """
query(
  $owner: String!
  $name: String!
  $number: Int!
  $cursor: String
) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        nodes {
          id
          isResolved
          isCollapsed
          path
          line
          originalLine
          startLine
          originalStartLine
          diffSide
          startDiffSide
          resolvedBy { login }
          comments(first: 100) {
            nodes {
              id
              url
              body
              createdAt
              state
              path
              line
              originalLine
              outdated
              author { login }
              commit { oid }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
"""


def gh(*args: str) -> str:
    result = subprocess.run(
        ["gh", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        print(result.stderr, file=sys.stderr, end="")
        raise SystemExit(result.returncode)
    return result.stdout


def current_repo() -> str:
    data = json.loads(gh("repo", "view", "--json", "nameWithOwner"))
    return str(data["nameWithOwner"])


def pr_metadata(repo: str, number: int) -> dict[str, Any]:
    fields = ",".join(
        [
            "additions",
            "author",
            "baseRefName",
            "commits",
            "deletions",
            "files",
            "headRefName",
            "headRefOid",
            "isDraft",
            "mergeable",
            "number",
            "state",
            "title",
            "url",
        ]
    )
    return json.loads(
        gh("pr", "view", str(number), "--repo", repo, "--json", fields)
    )


def review_threads(repo: str, number: int) -> list[dict[str, Any]]:
    owner, name = repo.split("/", maxsplit=1)
    cursor: str | None = None
    threads: list[dict[str, Any]] = []

    while True:
        args = [
            "api",
            "graphql",
            "-f",
            f"query={QUERY}",
            "-F",
            f"owner={owner}",
            "-F",
            f"name={name}",
            "-F",
            f"number={number}",
        ]
        if cursor is not None:
            args.extend(["-F", f"cursor={cursor}"])

        data = json.loads(gh(*args))
        page = data["data"]["repository"]["pullRequest"]["reviewThreads"]
        threads.extend(page["nodes"])
        page_info = page["pageInfo"]
        if not page_info["hasNextPage"]:
            return threads
        cursor = page_info["endCursor"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("number", type=int, help="pull request number")
    parser.add_argument("--repo", help="OWNER/REPO; defaults to current repo")
    parser.add_argument("--unresolved-only", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo = args.repo or current_repo()
    threads = review_threads(repo, args.number)
    if args.unresolved_only:
        threads = [thread for thread in threads if not thread["isResolved"]]

    payload = {
        "pull_request": pr_metadata(repo, args.number),
        "review_threads": threads,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Shared Z.ai GLM chat client used by Stage 3 (--llm) and Stage 6 (final synthesis).

Configuration (environment variables):
- ZAI_API_KEY   API key from the Z.ai open platform (never commit this)
- ZAI_BASE_URL  defaults to https://api.z.ai/api/paas/v4
- ZAI_MODEL     defaults to glm-4.6
- ZAI_MOCK      set to "1" to return deterministic responses for tests

Only the Python standard library is used for HTTP so the pipeline has no
SDK dependency; requests stay OpenAI-compatible chat/completions.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

DEFAULT_BASE_URL = "https://api.z.ai/api/paas/v4"
DEFAULT_MODEL = "glm-4.6"
REQUEST_TIMEOUT_SECONDS = 120


def _config() -> dict[str, str | None]:
    return {
        "api_key": os.environ.get("ZAI_API_KEY"),
        "base_url": os.environ.get("ZAI_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        "model": os.environ.get("ZAI_MODEL", DEFAULT_MODEL),
    }


def _mock_response(messages: list[dict[str, str]], task: str) -> str:
    prompt = messages[-1]["content"] if messages else ""
    if task == "propose":
        doc_section = prompt.split("DOC:", 1)[-1]
        first_line = next(
            (line.strip() for line in doc_section.splitlines() if line.strip()), ""
        )
        # The test suite relies on the quote being verbatim source text.
        quote = first_line.split("】", 1)[-1] if "】" in first_line else first_line
        return json.dumps(
            [
                {
                    "rule_id": "賠償無上限",
                    "risk_level": "high",
                    "quote": quote,
                    "location": "第 1 頁",
                    "analysis": "MOCK：命中賠償無上限規則，請人工確認。",
                }
            ],
            ensure_ascii=False,
        )

    finding_ids = sorted(set(re.findall(r"[A-Z]{2,4}-\d{3}", prompt)))
    lines = [f"- {finding_id}" for finding_id in finding_ids] or ["- （無 Finding）"]
    return (
        "# 終審執行摘要（MOCK）\n\n"
        "## 需談判的 High Risk\n"
        + "\n".join(lines)
        + "\n\n## 談判建議\n\n以 Finding ID 對照原文後逐條談判；本回應為測試用的 MOCK 輸出。\n"
    )


def chat(messages: list[dict[str, str]], task: str = "synthesis", temperature: float = 0.2) -> str:
    if os.environ.get("ZAI_MOCK") == "1":
        return _mock_response(messages, task)

    config = _config()
    if not config["api_key"]:
        raise SystemExit(
            "LLM call skipped: ZAI_API_KEY is not set. Get a key at https://z.ai "
            "(API Keys page) and export ZAI_API_KEY, or set ZAI_MOCK=1 for tests."
        )

    payload = json.dumps(
        {"model": config["model"], "messages": messages, "temperature": temperature}
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{config['base_url']}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"Z.ai API error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Z.ai API unreachable: {exc.reason}") from exc

    choices = body.get("choices", [])
    if not choices:
        raise RuntimeError(f"Z.ai API returned no choices: {json.dumps(body)[:300]}")
    return str(choices[0]["message"]["content"])

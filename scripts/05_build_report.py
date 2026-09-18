#!/usr/bin/env python3
"""Stage 5: assemble evidence-backed findings into Markdown and HTML reports."""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent


def read_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_findings() -> list[tuple[str, dict[str, object]]]:
    findings: list[tuple[str, dict[str, object]]] = []
    for path in sorted((BASE / "findings").glob("*.json")):
        if path.name == "FINDING_EXAMPLE.json":
            continue
        value = read_json(path, {})
        if isinstance(value, dict):
            findings.append((path.name, value))
    return findings


def markdown_report(findings: list[dict[str, object]], manifest: dict[str, object]) -> str:
    risk_counts = Counter(str(item.get("risk_level", "unknown")) for item in findings)
    lines = [
        "# 文件審查報告",
        "",
        f"- 專案：{manifest.get('project', '未指定')}",
        f"- Run ID：{manifest.get('run_id', '未建立')}",
        f"- 輸入文件：{manifest.get('input_files', 0)}",
        f"- Findings：{len(findings)}（high {risk_counts['high']} / medium {risk_counts['medium']} / low {risk_counts['low']}）",
        "",
        "## Findings",
        "",
    ]
    if not findings:
        lines.append("目前沒有通過證據檢查的 Finding。")
    for item in findings:
        lines.extend(
            [
                f"### {item.get('finding_id', '未編號')} — {item.get('classification', '未分類')}",
                "",
                f"- 判定：{item.get('judgment', '未判定')}（{item.get('risk_level', 'unknown')}）",
                f"- 狀態：{item.get('status', '未指定')}",
                f"- 來源：{item.get('source_file', '未指定')}｜{item.get('location', '未指定')}",
                f"- 規則：{item.get('config_rule', '未指定')}",
                "",
                f"> {item.get('quote', '')}",
                "",
                str(item.get("analysis", "")),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def html_report(markdown: str) -> str:
    return """<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>文件審查報告</title>
  <style>
    body { max-width: 960px; margin: 40px auto; padding: 0 24px; color: #18181b; font: 16px/1.7 system-ui, sans-serif; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; }
  </style>
</head>
<body><pre>""" + html.escape(markdown) + """</pre></body>
</html>
"""


def main() -> None:
    reports_dir = BASE / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    evidence_index = read_json(BASE / "evidence" / "index.json", [])
    allowed_files = {
        str(item.get("file"))
        for item in evidence_index
        if isinstance(item, dict) and item.get("has_evidence") is True
    }
    findings = [item for filename, item in load_findings() if filename in allowed_files]

    manifest = read_json(BASE / "manifest.json", {})
    if not isinstance(manifest, dict):
        manifest = {}
    unresolved = [item for item in findings if item.get("status") == "需人工確認"]

    (BASE / "findings.json").write_text(
        json.dumps(findings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (BASE / "unresolved.json").write_text(
        json.dumps(unresolved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    markdown = markdown_report(findings, manifest)
    (reports_dir / "report.md").write_text(markdown, encoding="utf-8")
    (reports_dir / "report.html").write_text(html_report(markdown), encoding="utf-8")
    print(f"Report built: {len(findings)} finding(s), {len(unresolved)} unresolved -> {reports_dir}")


if __name__ == "__main__":
    main()

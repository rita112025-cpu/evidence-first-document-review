#!/usr/bin/env python3
"""Stage 3: evaluate normalized records against config/risk_rules.yaml.

Two detection layers:
- keyword rules (deterministic, offline): every rule in the "rules" section
  lists keywords; a hit produces one Finding with a verbatim quote.
- optional LLM proposals (--llm, needs ZAI_API_KEY or ZAI_MOCK=1): the model
  may propose additional findings, but every proposal must quote the source
  text verbatim or it is dropped, and every Finding stays status=需人工確認
  until Stage 4 evidence validation and a human confirm it.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

from llm_client import chat

BASE = Path(__file__).resolve().parent.parent
NORMALIZED_DIR = BASE / "normalized"
FINDINGS_DIR = BASE / "findings"

MAX_QUOTE_CHARS = 200
MAX_DOC_CHARS = 8000

SENTENCE_SPLIT = re.compile(r"[。！？；;\n]+")
JSON_ARRAY_PATTERN = re.compile(r"\[.*\]", re.DOTALL)

RISK_LABELS = {"high": "高風險", "medium": "中風險", "low": "可協商"}


def load_rules() -> list[dict[str, object]]:
    config_path = BASE / "config" / "risk_rules.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    rules = config.get("rules", [])
    for rule in rules:
        rule.setdefault("risk_level", "medium")
        rule.setdefault("keywords", [])
        rule.setdefault("description", rule.get("id", ""))
    return rules


def sentence_containing(text: str, keyword: str) -> str | None:
    for sentence in SENTENCE_SPLIT.split(text):
        sentence = sentence.strip()
        if keyword in sentence and len(sentence) >= 4:
            quote = sentence[:MAX_QUOTE_CHARS]
            return quote + ("…" if len(sentence) > MAX_QUOTE_CHARS else "")
    return None


def next_finding_id(prefix: str, counters: dict[str, int]) -> str:
    counters[prefix] = counters.get(prefix, 0) + 1
    return f"{prefix}-{counters[prefix]:03d}"


def keyword_findings(record: dict[str, object], rules: list[dict[str, object]]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    prefix = str(record.get("finding_prefix", "GEN"))
    seen: set[tuple[str, str]] = set()
    for entry in record.get("entries", []):
        location = str(entry.get("location", ""))
        text = str(entry.get("text", ""))
        for rule in rules:
            rule_id = str(rule["id"])
            for keyword in rule["keywords"]:
                quote = sentence_containing(text, str(keyword))
                if quote is None or (rule_id, location) in seen:
                    continue
                seen.add((rule_id, location))
                risk_level = str(rule["risk_level"])
                findings.append(
                    {
                        "finding_id": None,  # assigned after all layers are collected
                        "classification": str(rule.get("category", rule_id)),
                        "judgment": RISK_LABELS.get(risk_level, risk_level),
                        "risk_level": risk_level,
                        "source_file": record.get("source_file"),
                        "location": location,
                        "quote": quote,
                        "analysis": (
                            f"規則「{rule_id}」命中關鍵字「{keyword}」。"
                            "此為機器比對結果，請人工核對原文與適用情境。"
                        ),
                        "status": "需人工確認",
                        "config_rule": f"risk_rules.yaml:{risk_level}:{rule_id}",
                    }
                )
                break  # one keyword per rule per entry is enough
    return findings


def llm_findings(record: dict[str, object], rules: list[dict[str, object]]) -> list[dict[str, object]]:
    doc_lines = [
        f"【{entry.get('location')}】{entry.get('text')}" for entry in record.get("entries", [])
    ]
    doc_text = "\n".join(doc_lines)[:MAX_DOC_CHARS]
    rule_lines = [
        f"- {rule['id']} | {rule['risk_level']} | {rule['description']}" for rule in rules
    ]
    prompt = (
        "你是文件審查助理。依據下列已核定規則判斷文件風險，只輸出 JSON 陣列，"
        "每筆包含 rule_id、risk_level、quote（原文逐字引用）、location、analysis。"
        "沒有命中規則就輸出 []。禁止引用不存在的原文。\n\nRULES:\n"
        + "\n".join(rule_lines)
        + "\n\nDOC:\n"
        + doc_text
    )
    response = chat([{"role": "user", "content": prompt}], task="propose")
    match = JSON_ARRAY_PATTERN.search(response)
    if not match:
        return []

    known_rules = {str(rule["id"]): rule for rule in rules}
    source_text = doc_text
    proposals: list[dict[str, object]] = []
    try:
        items = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    for item in items:
        if not isinstance(item, dict):
            continue
        quote = str(item.get("quote", "")).strip()
        if not quote or quote not in source_text:
            continue  # unverifiable quote: dropped, the evidence gate stays intact
        rule_id = str(item.get("rule_id", "llm_proposal"))
        rule = known_rules.get(rule_id)
        risk_level = str(rule["risk_level"]) if rule else str(item.get("risk_level", "medium"))
        if risk_level not in RISK_LABELS:
            risk_level = "medium"
        proposals.append(
            {
                "finding_id": None,
                "classification": str(rule["id"]) if rule else rule_id,
                "judgment": RISK_LABELS.get(risk_level, risk_level),
                "risk_level": risk_level,
                "source_file": record.get("source_file"),
                "location": str(item.get("location", "未標記位置")),
                "quote": quote[:MAX_QUOTE_CHARS],
                "analysis": str(item.get("analysis", "")) or "LLM 建議，請人工確認。",
                "status": "需人工確認",
                "config_rule": (
                    f"risk_rules.yaml:{risk_level}:{rule_id}" if rule else "llm_proposal"
                ),
            }
        )
    return proposals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--llm",
        action="store_true",
        help="also ask the LLM (Z.ai GLM) for findings; quotes are verified before use",
    )
    args = parser.parse_args()

    index_path = NORMALIZED_DIR / "index.json"
    if not index_path.exists():
        raise SystemExit("normalized/index.json not found: run scripts/02_normalize.py first")

    rules = load_rules()
    index = json.loads(index_path.read_text(encoding="utf-8"))

    collected: list[dict[str, object]] = []
    prefix_by_source: dict[str, str] = {}
    for item in index:
        record = json.loads((BASE / str(item["record"])).read_text(encoding="utf-8"))
        prefix_by_source[str(record.get("source_file"))] = str(record.get("finding_prefix", "GEN"))
        collected.extend(keyword_findings(record, rules))
        if args.llm:
            collected.extend(llm_findings(record, rules))

    counters: dict[str, int] = {}
    for finding in collected:
        prefix = prefix_by_source.get(str(finding.get("source_file")), "GEN")
        finding["finding_id"] = next_finding_id(prefix, counters)

    FINDINGS_DIR.mkdir(exist_ok=True)
    for path in FINDINGS_DIR.glob("*.json"):
        if path.name != "FINDING_EXAMPLE.json":
            path.unlink()
    for finding in collected:
        out_path = FINDINGS_DIR / f"{finding['finding_id']}.json"
        out_path.write_text(
            json.dumps(finding, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    by_risk = {"high": 0, "medium": 0, "low": 0}
    for finding in collected:
        by_risk[str(finding["risk_level"])] = by_risk.get(str(finding["risk_level"]), 0) + 1
    print(
        f"Analyze: {len(collected)} finding(s) "
        f"(high {by_risk['high']} / medium {by_risk['medium']} / low {by_risk['low']})"
    )


if __name__ == "__main__":
    main()

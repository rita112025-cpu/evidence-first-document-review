#!/usr/bin/env python3
"""Stage 2: align extracted records into one schema and normalize values.

Reads extracted/{type}/*.json, keeps the original text for evidence quotes,
and derives normalized dates / amounts / percentages so Stage 3 rules can
match on consistent formats.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

BASE = Path(__file__).resolve().parent.parent
EXTRACTED_DIR = BASE / "extracted"
NORMALIZED_DIR = BASE / "normalized"

DATE_PATTERNS = re.compile(r"(?P<y>\d{4})[年/\-.](?P<m>\d{1,2})[月/\-.](?P<d>\d{1,2})日?")
AMOUNT_PATTERN = re.compile(
    r"(?P<currency>NT\$|USD|EUR|JPY|RMB|人民幣|美金|新台幣|元)?\s*[$＄]?\s*(?P<value>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?P<unit>萬|億|元|圆|圓)?"
)
PERCENT_PATTERN = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*[%％]")


def normalize_date(match: re.Match[str]) -> str:
    return f"{int(match.group('y')):04d}-{int(match.group('m')):02d}-{int(match.group('d')):02d}"


def normalize_amount(match: re.Match[str]) -> str:
    value = float(match.group("value").replace(",", ""))
    unit = match.group("unit") or ""
    currency = match.group("currency") or ""
    if unit in {"萬", "万"}:
        value *= 10_000
    elif unit == "億":
        value *= 100_000_000
    amount = f"{value:g}"
    return f"{currency}{unit}{amount}".strip()


def collect_fields(text: str) -> dict[str, list[str]]:
    dates: list[str] = []
    for match in DATE_PATTERNS.finditer(text):
        try:
            dates.append(normalize_date(match))
        except ValueError:  # impossible calendar date, keep raw text only
            continue
    amounts = [normalize_amount(match) for match in AMOUNT_PATTERN.finditer(text)]
    percents = [f"{match.group('value')}%" for match in PERCENT_PATTERN.finditer(text)]
    return {
        "dates": sorted(set(dates)),
        "amounts": sorted(set(amounts), key=lambda item: len(item)),
        "percentages": sorted(set(percents)),
    }


def normalize_record(record: dict[str, object]) -> dict[str, object]:
    entries: list[dict[str, str]] = []
    for entry in record.get("entries", []):
        text = str(entry.get("text", "")).strip()
        if not text:
            continue
        entries.append({"location": str(entry.get("location", "")), "text": text})

    fields = {"dates": [], "amounts": [], "percentages": []}
    for entry in entries:
        for key, values in collect_fields(entry["text"]).items():
            fields[key] = sorted(set(fields[key]) | set(values))

    return {
        "source_file": record.get("source_file"),
        "doc_type": record.get("doc_type"),
        "finding_prefix": record.get("finding_prefix", "GEN"),
        "entries": entries,
        "fields": fields,
    }


def main() -> None:
    index_path = EXTRACTED_DIR / "index.json"
    if not index_path.exists():
        raise SystemExit("extracted/index.json not found: run scripts/01_extract.py first")

    spec_path = BASE / "config" / "analysis_spec.yaml"
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8")) or {}
    known_types = set(spec.get("extract_types", {}) or {})

    index = json.loads(index_path.read_text(encoding="utf-8"))
    normalized_index: list[dict[str, object]] = []
    for item in index:
        record_path = BASE / str(item["record"])
        record = json.loads(record_path.read_text(encoding="utf-8"))
        doc_type = str(record.get("doc_type", "general"))
        if doc_type not in known_types:
            doc_type = "general"
        record["doc_type"] = doc_type

        normalized = normalize_record(record)
        out_dir = NORMALIZED_DIR / doc_type
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / record_path.name
        out_path.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        normalized_index.append(
            {
                "source_file": normalized["source_file"],
                "doc_type": doc_type,
                "record": out_path.relative_to(BASE).as_posix(),
                "entries": len(normalized["entries"]),
                "field_counts": {key: len(values) for key, values in normalized["fields"].items()},
            }
        )

    NORMALIZED_DIR.mkdir(exist_ok=True)
    (NORMALIZED_DIR / "index.json").write_text(
        json.dumps(normalized_index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Normalize: {len(normalized_index)} record(s) -> {NORMALIZED_DIR}")


if __name__ == "__main__":
    main()

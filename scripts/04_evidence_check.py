#!/usr/bin/env python3
"""Stage 4: validate Finding evidence and build evidence/index.json."""

from __future__ import annotations

import json
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent
REQUIRED_EVIDENCE = ("quote", "source_file", "location", "config_rule")


def has_value(value: object) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def main() -> int:
    findings_dir = BASE / "findings"
    evidence_dir = BASE / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    index: list[dict[str, object]] = []
    blocked = 0
    for path in sorted(findings_dir.glob("*.json")):
        if path.name == "FINDING_EXAMPLE.json":
            continue
        try:
            finding = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            blocked += 1
            index.append(
                {
                    "finding_id": None,
                    "file": path.name,
                    "has_evidence": False,
                    "missing": list(REQUIRED_EVIDENCE),
                    "error": str(exc),
                }
            )
            continue

        missing = [key for key in REQUIRED_EVIDENCE if not has_value(finding.get(key))]
        has_evidence = not missing
        if not has_evidence:
            blocked += 1
        index.append(
            {
                "finding_id": finding.get("finding_id"),
                "file": path.name,
                "has_evidence": has_evidence,
                "missing": missing,
            }
        )

    output = evidence_dir / "index.json"
    output.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Evidence check: {len(index)} finding(s), {blocked} blocked -> {output}")
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())

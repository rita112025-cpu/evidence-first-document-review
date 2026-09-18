#!/usr/bin/env python3
"""Stage 6: LLM final synthesis (GPT 終審) over structured artifacts.

Feeds findings.json, unresolved.json, evidence/index.json, the draft report
and the manifest to the configured LLM (Z.ai GLM), and writes
reports/synthesis.md. The prompt forbids re-reading raw documents and
conclusions without evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

from llm_client import chat

BASE = Path(__file__).resolve().parent.parent
MAX_FINDINGS_CHARS = 12000
MAX_REPORT_CHARS = 6000


def read_text(path: Path, default: str = "") -> str:
    if not path.exists():
        return default
    return path.read_text(encoding="utf-8")


def main() -> None:
    findings_path = BASE / "findings.json"
    if not findings_path.exists():
        raise SystemExit("findings.json not found: run scripts/05_build_report.py first")

    findings = read_text(findings_path)
    unresolved = read_text(BASE / "unresolved.json", "[]")
    evidence = read_text(BASE / "evidence" / "index.json", "[]")
    draft_report = read_text(BASE / "reports" / "report.md")[:MAX_REPORT_CHARS]

    manifest = json.loads(read_text(BASE / "manifest.json", "{}") or "{}")
    total = manifest.get("input_files", "?")
    processed = manifest.get("processed_files", "?")
    run_status = f"{processed}/{total} input files processed"
    failed = manifest.get("failed_files", [])
    if failed:
        run_status += f"; failed: {', '.join(str(item) for item in failed)}"
    needs_ocr = manifest.get("needs_ocr", [])
    if needs_ocr:
        run_status += f"; {len(needs_ocr)} page(s) waiting for OCR"

    system_prompt = (BASE / "prompts" / "gpt_final_synthesis.md").read_text(encoding="utf-8")
    user_payload = (
        f"RUN STATUS: {run_status}\n\n"
        f"FINDINGS (findings.json):\n{findings[:MAX_FINDINGS_CHARS]}\n\n"
        f"UNRESOLVED (unresolved.json):\n{unresolved[:MAX_FINDINGS_CHARS]}\n\n"
        f"EVIDENCE INDEX (evidence/index.json):\n{evidence[:MAX_FINDINGS_CHARS]}\n\n"
        f"REPORT DRAFT:\n{draft_report}\n"
    )

    synthesis = chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_payload},
        ],
        task="synthesis",
    )

    reports_dir = BASE / "reports"
    reports_dir.mkdir(exist_ok=True)
    out_path = reports_dir / "synthesis.md"
    out_path.write_text(synthesis.rstrip() + "\n", encoding="utf-8")
    print(f"Synthesis written: {out_path}")


if __name__ == "__main__":
    main()

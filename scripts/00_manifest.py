#!/usr/bin/env python3
"""Stage 0: create a reproducible run manifest and directory skeleton."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path


BASE = Path(__file__).resolve().parent.parent
RUNTIME_DIRS = (
    "input",
    "extracted/contract",
    "extracted/drawings",
    "extracted/boq",
    "extracted/specifications",
    "extracted/meeting",
    "normalized",
    "findings",
    "evidence",
    "reports",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def build_manifest(project: str) -> dict[str, object]:
    for relative in RUNTIME_DIRS:
        (BASE / relative).mkdir(parents=True, exist_ok=True)

    input_root = BASE / "input"
    input_files = sorted(
        path for path in input_root.rglob("*") if path.is_file() and path.name != ".gitkeep"
    )
    spec_path = BASE / "config" / "analysis_spec.yaml"
    now = dt.datetime.now().astimezone()

    return {
        "project": project,
        "run_id": now.strftime("%Y%m%d-%H%M%S"),
        "input_files": len(input_files),
        "input_file_list": [path.relative_to(input_root).as_posix() for path in input_files],
        "processed_files": 0,
        "failed_files": [],
        "analysis_spec": "config/analysis_spec.yaml",
        "analysis_spec_hash": sha256_file(spec_path),
        "pipeline_version": "v2.0",
        "stages": ["extract", "normalize", "analyze", "evidence_check", "report"],
        "generated_at": now.isoformat(timespec="seconds"),
        "operator": "unassigned",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="document-review", help="Project identifier")
    args = parser.parse_args()

    manifest = build_manifest(args.project)
    output = BASE / "manifest.json"
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Manifest created: {manifest['input_files']} input file(s) tracked -> {output}")


if __name__ == "__main__":
    main()

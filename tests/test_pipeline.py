from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]


class PipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project = Path(self.temp_dir.name) / "project"
        shutil.copytree(PROJECT, self.project)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_script(self, name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.project / "scripts" / name), *args],
            cwd=self.project,
            text=True,
            capture_output=True,
            check=False,
        )

    def write_finding(self, filename: str, **overrides: object) -> None:
        finding: dict[str, object] = {
            "finding_id": "CON-001",
            "classification": "責任限制",
            "judgment": "高風險",
            "risk_level": "high",
            "source_file": "contract.pdf",
            "location": "第 1 頁",
            "quote": "責任不受限制。",
            "analysis": "建議加入責任上限。",
            "status": "需人工確認",
            "config_rule": "risk_rules.yaml:high:賠償無上限",
        }
        finding.update(overrides)
        (self.project / "findings" / filename).write_text(
            json.dumps(finding, ensure_ascii=False), encoding="utf-8"
        )

    def test_evidence_backed_finding_reaches_report(self) -> None:
        self.write_finding("CON-001.json")
        self.assertEqual(self.run_script("00_manifest.py", "--project", "test-project").returncode, 0)
        self.assertEqual(self.run_script("04_evidence_check.py").returncode, 0)
        self.assertEqual(self.run_script("05_build_report.py").returncode, 0)

        findings = json.loads((self.project / "findings.json").read_text(encoding="utf-8"))
        unresolved = json.loads((self.project / "unresolved.json").read_text(encoding="utf-8"))
        report = (self.project / "reports" / "report.md").read_text(encoding="utf-8")
        self.assertEqual([item["finding_id"] for item in findings], ["CON-001"])
        self.assertEqual([item["finding_id"] for item in unresolved], ["CON-001"])
        self.assertIn("CON-001", report)

    def test_missing_evidence_is_blocked(self) -> None:
        self.write_finding("CON-002.json", finding_id="CON-002", quote="")
        result = self.run_script("04_evidence_check.py")
        self.assertEqual(result.returncode, 1)

        index = json.loads((self.project / "evidence" / "index.json").read_text(encoding="utf-8"))
        self.assertFalse(index[0]["has_evidence"])
        self.assertIn("quote", index[0]["missing"])


if __name__ == "__main__":
    unittest.main()

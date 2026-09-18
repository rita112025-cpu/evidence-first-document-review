# document-workflow v2

可審計、可追溯、可重跑的文件審查 Pipeline 參考實作。

> 目前定位：GitHub-ready 的架構骨架。Stage 0、4、5 可直接執行；Stage 1–3 是文件抽取／模型分析的整合邊界，需依實際 OCR、LLM 或企業文件系統實作。這個專案不取代法務或專業審查。

## 為什麼採用 v2

- `manifest.json` 記錄輸入數量、規格雜湊與執行批次。
- Extract、Normalize、Analyze 分離，能定位錯誤發生在哪一層。
- 每個 Finding 都要有 ID、來源、位置、原文與規則。
- Evidence Check 會阻擋缺少證據的 Finding。
- GPT 終審只接收結構化產物，不重新掃描全部原始文件。

## Pipeline

```text
input/
  -> [0] manifest
  -> [1] extract       # 整合點
  -> [2] normalize     # 整合點
  -> [3] analyze       # 整合點
  -> [4] evidence_check
  -> [5] report
```

## 快速開始

需求：Python 3.10 以上；目前可執行階段只使用 Python 標準函式庫。

```bash
python scripts/00_manifest.py --project project-a
python scripts/04_evidence_check.py
python scripts/05_build_report.py
```

1. 將待處理文件放入 `input/`，執行 Stage 0 建立 manifest。
2. 由 Stage 1–3 的實作產生 `findings/{FINDING_ID}.json`。
3. 執行 Stage 4。若任何 Finding 缺少 `quote`、`source_file`、`location` 或 `config_rule`，程式會回傳非零狀態。
4. Stage 5 只會把通過證據檢查的 Finding 寫入報告。

輸出包括：

- `findings.json`：通過證據檢查的 Finding 合併檔
- `unresolved.json`：`status=需人工確認` 的清單
- `reports/report.md`
- `reports/report.html`

## Finding 格式

參考 [`findings/FINDING_EXAMPLE.json`](findings/FINDING_EXAMPLE.json)。正式 Finding 至少要有：

- `finding_id`
- `classification`
- `judgment` / `risk_level`
- `source_file` / `location` / `quote`
- `analysis` / `status`
- `config_rule`

## 安全與版控

`.gitignore` 預設排除原始文件、執行產物與正式 Findings，避免把合約內容或敏感資料誤推到公開 GitHub。上傳前仍應人工檢查 `git status` 與 staged diff。

架構展示頁位於 [`docs/architecture.html`](docs/architecture.html)，可直接用一般瀏覽器開啟。

## 測試

```bash
python -m unittest discover -s tests -v
```

## 專案結構

```text
document-workflow-v2/
├─ config/
├─ docs/
├─ evidence/
├─ extracted/
├─ findings/
├─ input/
├─ normalized/
├─ prompts/
├─ reports/
└─ scripts/
```

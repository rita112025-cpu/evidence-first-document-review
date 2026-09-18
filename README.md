# document-workflow v2

可審計、可追溯、可重跑的文件審查 Pipeline 參考實作。

> 目前定位：Stage 0–5 全部可執行——文字層抽取（PDF／DOCX／XLSX／TXT）、格式正規化、關鍵字風險規則引擎、證據閘門與報告組裝。掃描件 OCR 與 LLM 終審（Z.ai GLM）為選用模組，需另行設定（見「選用設定」）。機器產出的 Finding 一律標記「需人工確認」；這個專案不取代法務或專業審查。

## 為什麼採用 v2

- `manifest.json` 記錄輸入數量、規格雜湊與執行批次，含待 OCR 頁清單。
- Extract、Normalize、Analyze 分離，能定位錯誤發生在哪一層。
- 每個 Finding 都要有 ID、來源、位置、原文與規則。
- Evidence Check 會阻擋缺少證據的 Finding。
- LLM 終審只接收結構化產物，不重新掃描全部原始文件。

## Pipeline

```text
input/
  -> [0] manifest
  -> [1] extract       # 文字層抽取；掃描頁標記 needs_ocr 或走 Tesseract
  -> [2] normalize     # 統一 schema、日期金額格式
  -> [3] analyze       # 關鍵字規則引擎；--llm 可加 LLM 提案（逐字引用才採用）
  -> [4] evidence_check
  -> [5] report
  -> [6] llm_synthesis # 選用：GPT 終審，產出 reports/synthesis.md
```

## 快速開始

需求：Python 3.10 以上。

```bash
pip install -r requirements.txt
python scripts/00_manifest.py --project project-a
python scripts/01_extract.py
python scripts/02_normalize.py
python scripts/03_analyze.py          # 加 --llm 可同時請 LLM 提案
python scripts/04_evidence_check.py
python scripts/05_build_report.py
```

1. 將待處理文件放入 `input/`，執行 Stage 0 建立 manifest。
2. Stage 1 會把每份文件抽成 `extracted/{type}/` 的結構化 JSON，含頁碼／段落位置與原文。
3. Stage 2 統一 schema 並正規化日期、金額、百分比。
4. Stage 3 依 `config/risk_rules.yaml` 的 `rules` 區塊比對關鍵字，產生 `findings/{FINDING_ID}.json`。
5. 執行 Stage 4。若任何 Finding 缺少 `quote`、`source_file`、`location` 或 `config_rule`，程式會回傳非零狀態。
6. Stage 5 只會把通過證據檢查的 Finding 寫入報告。

輸出包括：

- `findings.json`：通過證據檢查的 Finding 合併檔
- `unresolved.json`：`status=需人工確認` 的清單
- `reports/report.md`、`reports/report.html`
- `reports/synthesis.md`（執行 Stage 6 後）

## 選用設定

### LLM 終審（Z.ai GLM）

1. 到 [Z.ai 開放平台](https://z.ai) 註冊，在 API Keys 管理頁建立金鑰（中國大陸用戶使用 [open.bigmodel.cn](https://open.bigmodel.cn)）。
2. 設定環境變數（金鑰不要寫進檔案或 git）：

```bash
export ZAI_API_KEY="你的金鑰"        # Windows PowerShell: $env:ZAI_API_KEY="..."
export ZAI_MODEL="glm-4.6"          # 選用，預設 glm-4.6
python scripts/06_llm_synthesis.py
```

3. `03_analyze.py --llm` 會讓 LLM 對每份文件提案額外 Finding；所有提案必須逐字引用原文才會被採用，且同樣要過 Stage 4 證據閘門。
4. 測試或離線示範可設 `ZAI_MOCK=1`，LLM 層會回傳確定性的模擬回應。

### 掃描件 OCR

Stage 1 偵測到無文字層的頁面時：已安裝 Tesseract 就自動 OCR；未安裝則記錄在 `manifest.json` 的 `needs_ocr`，不會中斷流程。Windows 可安裝 [UB-Mannheim Tesseract](https://github.com/UB-Mannheim/tesseract/wiki)，並勾選繁體中文語言包（chi_tra）。

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

GitHub Pages 首頁位於 [`docs/index.html`](docs/index.html)，以白話介紹用途、流程與目前完成範圍。較詳細的工程架構保留在 [`docs/architecture.html`](docs/architecture.html)。

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
├─ scripts/            # Stage 0–6 + llm_client.py
├─ tests/
└─ requirements.txt
```

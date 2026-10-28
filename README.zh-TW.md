# STORM 繁體中文 MVP

本版本提供官方 minimal Streamlit 介面與 STORM 研究引擎的繁體中文支援。介面預設繁體中文，可在側欄切換 English；含中文字的研究主題會要求模型以繁體中文產生問題、大綱及報告。英文專有名詞與論文標題可保留原文。Co-STORM 的完整互動介面不在本版本範圍內。

## 事前準備

- Python 3.10 或 3.11。核心套件指定 `dspy_ai==2.4.9`；minimal UI 指定 `streamlit==1.31.1`，其餘部分依賴未固定版本，安裝結果可能隨時間改變。
- 一個 LiteLLM 支援的模型供應商帳號、模型名稱與對應 API Key。本範例使用 OpenAI；請自行選擇帳號可用的模型。
- [You.com Search API](https://you.com/) 的 `YDC_API_KEY`。搜尋和模型呼叫皆可能計費。
- 首次研究會下載句向量模型；需要網路與足夠磁碟空間。

請在專案根目錄執行以下指令。不要將 API Key 寫進程式、文件或 Git；範例的佔位文字請替換為自己的設定，且勿貼出包含密鑰的終端機紀錄。

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pip install -r frontend/demo_light/requirements.txt
$env:STORM_PROVIDER = "openai"
$env:STORM_MODEL = "<模型名稱>"
$env:OPENAI_API_KEY = "<模型 API Key>"
$env:YDC_API_KEY = "<You.com API Key>"
python -m streamlit run frontend/demo_light/storm.py
```

若 PowerShell 政策阻止啟動虛擬環境，可直接使用 `.\.venv\Scripts\python.exe` 執行上述各個 Python 指令。環境變數僅設定於目前 PowerShell 工作階段。

### macOS（zsh）

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install -r frontend/demo_light/requirements.txt
export STORM_PROVIDER="openai"
export STORM_MODEL="<模型名稱>"
export OPENAI_API_KEY="<模型 API Key>"
export YDC_API_KEY="<You.com API Key>"
python -m streamlit run frontend/demo_light/storm.py
```

`STORM_PROVIDER` 與 `STORM_MODEL` 組成 LiteLLM 的 `provider/model`；也可在 `STORM_MODEL` 填入相同供應商前綴的完整名稱。其他供應商需依 LiteLLM 設定其對應的環境變數與端點。所有階段使用同一模型，並設定不同輸出長度；請選擇支援這些參數的模型。模型資格、價格與金鑰取得方式請查供應商文件。

## 使用與限制

輸入主題後選擇「開始研究」，完成後可在「我的文章」查看文章、參考資料與研究對話。輸出存於 `frontend/demo_light/DEMO_WORKING_DIR/`，已加入 Git 忽略清單；其中可能包含主題、搜尋內容、模型輸出和來源，請自行保護。LiteLLM 也可能在使用者目錄快取呼叫內容。

主題最多 125 個字元、240 個 UTF-8 位元組及 20 個詞，禁止路徑分隔符、控制字元及 Windows 不允許的檔案名稱。介面進行基本格式檢查，不保證判斷所有不適當的用途。搜尋品質受搜尋服務、來源與語言影響；系統要求模型只依據資料並保留引用，但模型仍可能產生錯誤或不受支持的陳述。請逐一開啟原始網址核對事實、文獻及引用，勿將結果直接視為事實。

每次研究可能執行多次搜尋、問題生成、文章生成及潤稿；成本取決於模型價格、輸入與輸出 token、搜尋次數與供應商方案。研究時間與費用無固定保證，請先檢查供應商價格、額度與帳單，並從小主題開始。

## 測試

```bash
python -m unittest discover -s tests -v
```

測試包含離線的主題驗證、介面字典、提示詞約束與引用處理；它們不能證明外部 API、Streamlit 畫面、檢索結果或模型生成品質。完整端到端驗證需安裝所有依賴、設定有效 API Key、使用可用的模型及網路，並會產生費用。

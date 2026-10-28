# STORM 繁體中文 MVP

官方 minimal Streamlit 介面預設繁體中文，可在側欄切換 English。中文主題會要求模型以繁體中文產生專家提問、大綱及報告，並保留英文專有名詞、論文原名與引用對應。Co-STORM 的完整互動介面不在本版本範圍內。

## 預設：模型與搜尋都使用 Codex

本機介面透過官方 `codex exec --json` 呼叫已登入 ChatGPT 的 Codex CLI。文字生成使用 Codex，網路檢索使用 Codex 的內建即時搜尋，不需要 `OPENAI_API_KEY` 或 `YDC_API_KEY`。程式強制採用 ChatGPT 登入，呼叫失敗時會停止，不會自動轉用 API Key 計費。

請先安裝 [Codex CLI](https://learn.chatgpt.com/docs/cli)，執行 `codex login`，選擇 ChatGPT 登入；用 `codex login status` 確認。需要支援 JSONL `web_search.results` 的版本；實際搜尋事件格式已於 **0.165.0-alpha.1.2** 驗證。較舊版本若未輸出結構化結果，介面會明確顯示錯誤，無法以模型文字中的網址代替。

環境需求：Python 3.10 或 3.11。核心依賴指定 `dspy_ai==2.4.9`，minimal UI 指定 `streamlit==1.31.1`。其他部分依賴未固定版本，完整套件相容性仍需於實際環境驗證。首次文章內文檢索會下載本機句向量模型，需要網路與磁碟空間；它不會呼叫付費的 embeddings API。

### Windows PowerShell

若要使用桌面／工作列按鈕，可在專案根目錄執行一次：

```powershell
.\tools\install_windows_launcher.ps1
```

安裝程式會準備專案的 `.venv`、打包本機啟動器，並在桌面及開始功能表建立 **STORM** 捷徑。之後雙擊捷徑即可啟動；可將捷徑釘選到工作列，或加入 Windows Dock。若使用 Edge／Chrome，研究介面會以獨立視窗開啟。

服務只開放 `127.0.0.1`，再次啟動會開啟同一個服務。啟動器會縮到工作列；要停止服務，開啟啟動器並按「結束 STORM」。關閉研究視窗本身不會停止服務。啟動器位於 `local/launcher/STORM/STORM.exe`，需要保留專案與 `.venv`；不是可單獨搬移的完整安裝包。啟動失敗可查看 `local/launcher/streamlit.log`。

從專案根目錄執行：

```powershell
py -3.11 -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pip install -r frontend/demo_light/requirements.txt
codex login
codex login status
$env:STORM_PROVIDER = "codex"
python -m streamlit run frontend/demo_light/storm.py
```

若啟動虛擬環境受 PowerShell 政策阻擋，可直接以 `.\.venv\Scripts\python.exe` 執行 Python 指令。若找不到 `codex`，可將 `$env:STORM_CODEX_COMMAND` 設為 Codex 執行檔的完整路徑。終端機工作階段中的環境變數設定只影響目前工作階段。

### macOS（zsh）

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install -r frontend/demo_light/requirements.txt
codex login
codex login status
export STORM_PROVIDER="codex"
python -m streamlit run frontend/demo_light/storm.py
```

`STORM_MODEL` 可選填 Codex 可用的模型 ID；未設定時採 CLI 的內建預設。每次呼叫在獨立暫存目錄執行，不載入使用者 `config.toml`，保留登入授權並停用 shell、apps、hooks 與分工。呼叫會序列執行，每次預設等待上限 600 秒；可用 STORM_CODEX_TIMEOUT 設定正數秒數，最多 3600 秒。這是等待上限，不代表每次都需要等這麼久。CLI 仍需要在使用者目錄寫入正常的執行狀態。本版本用於自己電腦上的本機操作。

## 研究來源與引用保存

搜尋只接受 Codex **工具事件**回傳的 `text_result`：原始 URL、標題及摘錄。不從模型的最終回答擷取連結，也不把模型自行產生的文獻或網址加入來源清單。Codex 模式不會使用原有的模型推薦 Wikipedia 網址流程。

每篇研究的輸出位於 `frontend/demo_light/DEMO_WORKING_DIR/<主題>/`：

```text
codex_search/<識別碼>.json   # 工具搜尋結果、實際查詢、時間、thread ID 與用量
codex_diagnostics/<識別碼>.json  # 呼叫階段、用時、是否重試與 HTTP 狀態；不存金鑰、提示詞或原始 stderr
conversation_log.json       # 對話與每一回合取得的來源
raw_search_results.json     # 原始來源對照
url_to_info.json            # 文章引用索引與來源 metadata
storm_gen_article_polished.txt
```

來源 metadata 保存原始查詢、實際查詢、工具事件 ID、來源 ref、取得時間及搜尋紀錄的 SHA-256。相同 URL 從不同查詢取得時會合併證據；輸出、文章引用及潤稿沿用相同來源對應。參考資料面板顯示查詢與紀錄位置，也能下載所選來源紀錄。請保留整個文章資料夾以便追溯。

保存的是搜尋工具回傳的**摘錄**，不是完整原文或論文全文。搜尋索引可能過時，模型仍可能誤解摘錄或產生不受來源支持的陳述。請開啟原始連結核對事實、作者、文獻名稱與引用內容。找不到任何可用來源時，Codex 模式會停止，避免產生沒有來源的完整報告。

## 額度與限制

研究的模型生成與搜尋會使用 Codex 的可用額度，受帳號方案、模型、搜尋權限及工作區政策限制。不是無限使用；額度耗盡或搜尋不可用時會顯示錯誤。每篇文章包含多次模型呼叫，每次 CLI 也可能載入自身背景內容，因此用量可能比單次聊天高。

預設採 1 回合、1 個額外觀點、每回合 1 組查詢並序列執行，以控制呼叫數。執行時間、實際額度消耗與文章品質沒有固定保證。[官方登入說明](https://learn.chatgpt.com/docs/auth)、[網路搜尋設定](https://learn.chatgpt.com/docs/web-search)、[非互動呼叫](https://learn.chatgpt.com/docs/non-interactive-mode)。

主題最多 125 個字元、240 個 UTF-8 位元組及 20 個詞，禁止路徑分隔符、控制字元及 Windows 無法使用的檔案名稱。資料與搜尋紀錄已被 Git 忽略，但可能包含研究主題、摘錄與模型輸出，請自行保護。

## 可選：明確使用 API 供應商

若有需要，可將 `STORM_PROVIDER` 設為 LiteLLM 的供應商，例如 `openai`；再設定 `STORM_MODEL`、供應商金鑰及 `YDC_API_KEY`。此模式的模型與搜尋另依供應商計費，與 Codex 模式不會自動互相切換。修改設定後重新啟動 Streamlit，使 runner 重新建立。不要把任何金鑰寫入 Git。

## 測試

離線自動化測試不呼叫外部服務：

```bash
python -m unittest discover -s tests -v
```

包含主題、i18n、提示詞、引用格式、Codex 事件解析、錯誤處理與來源保存。真實 DSPy 契約測試會在未安裝 DSPy 時標記 skip。

本次 DSPy 契約測試在隔離虛擬環境使用 `dspy_ai==2.4.9` 與 `pyarrow==20.0.0` 驗證，包含 `Predict` 和 `ChainOfThought` 的繁中及引用解析。這不等於所有未固定版本的依賴組合皆已通過。

以下為**選擇性實際測試**，會消耗 Codex 額度，執行一次生成、一次搜尋並核對保存的證據：

```powershell
# Windows PowerShell
$env:STORM_RUN_CODEX_LIVE = "1"
python -m unittest discover -s tests -p test_codex_live.py -v
```

```bash
# macOS
STORM_RUN_CODEX_LIVE=1 python -m unittest discover -s tests -p test_codex_live.py -v
```

實際測試與完整 Streamlit/STORM 端到端測試是不同層次。未安裝完整依賴或未實際操作畫面時，不能據此宣稱整個產品流程已通過。

# ⚡ RemoteCoder - 獨立遠端 AI 軟體工程師系統
> **Standalone Autonomous Headless AI Software Engineer & Multimodal Task Engine**  
> 具備自主編程、多模態截圖/文件分析、自我排錯驗證與純 HTTP 8080 Web UI 的獨立 AI 工程師系統。

---

## 📖 簡介

**RemoteCoder** 是一套完全解耦、能獨立在 Windows/Linux 主機背景運行的**「遠端無頭 AI 工程師系統」**。

當您人在外面或離開電腦時，只需使用任何普通手機、平板或筆記型電腦瀏覽器打開純 HTTP 網頁（例如 `http://192.168.2.107:8080`），即可隨時進行自然語言諮詢，或是直接交辦具體的專案開發與代碼修改任務。系統會自主調用本機工具、執行語法檢驗與建置測試，若遭遇報錯還能自我修復，並將所有執行歷程 100% 完整留存在主機硬碟中。

---

## ✨ 核心特點

1. **純 HTTP 8080 即時串流（SSE）**：
   - 採用標準 Server-Sent Events（SSE）架構，手機或任何外部瀏覽器打開即用，零 SSL 憑證警告、不需安裝任何 App。
2. **多模態截圖與文件分析（Multimodal Vision）**：
   - **直接貼上截圖（Ctrl + V）**：在電腦上使用 `Win + Shift + S` 截圖後，直接在輸入框按 `Ctrl + V` 即可貼上並顯示縮圖預覽。
   - **📎 迴紋針上傳**：支援圖片（PNG/JPG/WEBP）、PDF、文字檔、表格與各類代碼檔案；手機端點擊可直接呼叫相機拍照上傳。
   - 整合 Google Gemini 原生視覺大腦，能看懂錯誤代碼彈窗、UI 設計圖或技術規格書。
3. **左右並排雙欄工作區（Side-by-Side）**：
   - 在 100% 標準螢幕比例下，左側對話流、右側即時終端機畫布各自獨立滾動，徹底解決終端機被遮擋的問題。
   - 支援一鍵收合/展開終端機，手機直式螢幕自動切換為舒適自適應排版。
4. **全自主編程循環與自我修復（Self-Healing Loop）**：
   - 內建安全沙箱工具：目錄探索 (`list_directory`)、檔案讀取 (`read_file`)、代碼精準替換 (`edit_file_replace`)、關鍵字搜尋 (`search_code`) 與指令執行 (`run_powershell`)。
   - 代碼編寫完成後自主執行測試；若出錯自動閱讀日誌並調校修正，直到通過為止。
5. **多輪對話與單一輸入框**：
   - 支援日常技術諮詢、問答、多輪接續發話與任務交辦無縫切換。
   - 支援 `Enter` 直接發送、`Shift + Enter` 換行，隨內容自適應高度。
6. **高危操作審查攔截（Human-in-the-Loop）**：
   - 涉及系統資源變更或破壞性操作時自動暫停，網頁端跳出確認橫幅，遠端一鍵點擊「允許」或「取消」。
7. **歷史紀錄持久化與管理**：
   - 任務歷程與代碼產出完整儲存在 `outputs/tasks/` 目錄，支援歷史回放、單筆 `✕` 刪除與一鍵清空硬碟空間。

---

## 📂 目錄架構

```
RemoteCoder/
├── app/
│   ├── __init__.py
│   ├── server.py             # FastAPI 後端服務 (REST API, 靜態資源, SSE 串流)
│   ├── engine.py             # 自主工程大腦循環 (Gemini Multimodal Tool Loop & 自我修復)
│   ├── tools.py              # 本機目錄探索、檔案讀寫、精準替換與 PowerShell 工具集
│   └── storage.py            # 本機任務日誌、訊息與狀態持久化管理
├── web/
│   ├── index.html            # 現代極簡黑底 UI (左右並排工作區)
│   ├── style.css             # 現代響應式深色風格樣式表
│   └── app.js                # 前端控制器 (SSE 打字機串流, Ctrl+V 貼上, 附件處理)
├── scripts/
│   ├── start_server.ps1      # 一鍵背景守護進程啟動腳本 (WMI pythonw.exe 零黑窗)
│   ├── stop_server.ps1       # 一鍵停止伺服器腳本
│   └── check_health.py       # 健康檢查驗證腳本
├── outputs/                  # 任務歷程、日誌與上傳附件目錄 (預設被 .gitignore 忽略)
│   ├── gemini_api_key.txt.example  # API Key 設定範本
│   └── .gitkeep
├── 1-啟動RemoteCoder.bat      # 雙擊一鍵啟動
├── 2-停止RemoteCoder.bat      # 雙擊一鍵關閉
├── 3-開啟網頁.bat             # 雙擊開啟瀏覽器
├── requirements.txt          # Python 相依套件
├── .gitignore                # Git 忽略清單 (防洩漏 API Key 與任務日誌)
└── README.md
```

---

## 🚀 快速開始

### 1. 安裝環境依賴

建議使用 Python 3.10 或以上版本：

```bash
# 建立虛擬環境 (選填)
python -m venv .venv
.\.venv\Scripts\activate

# 安裝輕量依賴
pip install -r requirements.txt
```

### 2. 設定 Gemini API Key

在 `outputs/` 目錄下建立 `gemini_api_key.txt` 並填入您的 Google Gemini API Key：

```bash
# 複製範本檔案
copy outputs\gemini_api_key.txt.example outputs\gemini_api_key.txt
```
> 您也可以透過系統環境變數設定 `GEMINI_API_KEY="your_api_key_here"`。

### 3. 啟動伺服器

#### 方式一：Windows 桌面雙擊（推薦）
- 直接雙擊執行 **`1-啟動RemoteCoder.bat`**，伺服器將在背景安靜運行（無黑窗常駐）。
- 雙擊 **`2-停止RemoteCoder.bat`** 即可隨時關閉伺服器。

#### 方式二：命令行啟動
```powershell
python -m app.server
```

### 4. 開啟操作介面

- **本機電腦**：打開瀏覽器訪問 `http://localhost:8080`（或雙擊 `3-開啟網頁.bat`）
- **手機 / 平板 / 區網其他設備**：打開瀏覽器訪問 `http://<您的電腦區網IP>:8080`（例如 `http://192.168.2.107:8080`）

---

## 📤 如何上傳至 GitHub

本專案已備妥完整的 `.gitignore`，已自動排除您的私有 API Key (`outputs/gemini_api_key.txt`)、任務輸出與執行日誌，可放心提交。

在專案目錄下執行以下指令：

```bash
cd C:\Users\gongy\Desktop\RemoteCoder

# 1. 初始化 Git 倉庫
git init

# 2. 加入所有檔案並提交
git add .
git commit -m "Initial commit: RemoteCoder - Autonomous AI Coding & Multimodal Engine"

# 3. 關聯至您的 GitHub 倉庫並推播 (請將下方網址替換為您的倉庫網址)
git branch -M main
git remote add origin https://github.com/<您的GitHub帳號>/RemoteCoder.git
git push -u origin main
```

---

## 🛡️ 安全注意事項

- 本系統提供強大的本機自動化能力（讀寫檔案、執行 PowerShell），預設綁定於本機網路。
- 遇有高危險指令（如強制終止程序或變更系統資源）時，引擎會主動於前端彈出授權確認卡片，確保操作安全透明。
- 請勿將帶有真實 API Key 的檔案提交至公開倉庫。

---

## 📄 授權條款

MIT License. 歡迎自由 Fork、客製化與分享！

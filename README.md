# ⚡ RemoteCoder 快速上手與操作指南

只需一台平常開著的電腦與一支手機，出門在外就能隨時隨地交辦 AI 寫程式、改 Bug、分析架構！

---

## 🛠️ 第一步：事前準備（只需做一次）

1. **安裝 Python**：確保電腦安裝了 Python 3.10 或以上版本（安裝時請務必勾選「Add Python to PATH」）。
2. **下載本專案**：
   - 使用 Git：`git clone https://github.com/您的帳號/RemoteCoder.git`
   - 或直接在 GitHub 頁面點擊綠色的 **Code ➔ Download ZIP** 並解壓縮。
3. **取得 Google Gemini API Key（免費額度可用）**：
   - 前往 [Google AI Studio](https://aistudio.google.com/) 免費申請金鑰。

---

## ⚙️ 第二步：設定金鑰與環境

1. 打開 `RemoteCoder` 資料夾。
2. 進入 `outputs/` 目錄，將 `gemini_api_key.txt.example` 複製一份並重命名為：
   👉 **`gemini_api_key.txt`**
3. 用記事本打開 `gemini_api_key.txt`，貼上您的 Gemini API Key 並儲存。
4. 安裝依賴（在專案資料夾打開命令提示字元執行一次）：
   ```bash
   pip install -r requirements.txt

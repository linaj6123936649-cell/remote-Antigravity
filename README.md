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



---

### 🌟 針對不同對象的說明技巧

1. **若受眾是「非技術/普通使用者」**：
   - 重點強調：**「免記指令，雙擊 bat 就跑」**、**「手機打開網頁就能用」**、**「按 Ctrl+V 就能貼截圖問 AI」**。
2. **若受眾是「工程師/開源開發者」**：
   - 重點強調：**「解耦獨立架構（FastAPI + Vanilla JS SSE）」**、**「具備自我排錯迴圈（Self-healing Loop）」**、**「支援高危險指令攔截審查（Human-in-the-Loop）」**、**「零本地黑窗常駐」**。

目前在您桌面上的 `C:\Users\gongy\Desktop\RemoteCoder\README.md` 中，已經把架構圖、特色與安裝步驟寫得非常完整，搭配上述的使用指南，任何人只要照著步驟做，5 分鐘內就能完全上手！



<img width="1915" height="905" alt="image" src="https://github.com/user-attachments/assets/1bd57387-32dd-490f-9bfe-26b59a9a7a0b" />

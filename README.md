# 📊 阿財 - 智能財報與新聞分析 Agent

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Framework](https://img.shields.io/badge/Framework-LangChain-green.svg)](https://python.langchain.com/)
[![Model](https://img.shields.io/badge/Model-Gemini%202.5%20Flash-orange.svg)](https://aistudio.google.com/)
[![Deployment](https://img.shields.io/badge/Deployed%20on-Render-lightgrey.svg)](https://render.com/)

「阿財」是一個專為投資者設計的智能分析助手。它結合了 **Gemini 2.5 Flash** 極速的邏輯推理與工具調用（Tool Calling）能力，搭配即時金融數據 API，能自動完成從資料抓取到深度分析的繁瑣流程，產出具備「情緒分析」與「動能判斷」的專業報告。

---

## 🌟 核心技術亮點

### 1. 🤖 具備數據稽核能力的 AI 大腦
不同於一般的聊天機器人，阿財具備 **交叉比對 (Cross-validation)** 能力。當網路新聞資訊與即時股價數據發生矛盾時（例如：新聞標題寫舊價格，但現價已變動），Agent 能主動識別並在報告中發出風險警示，有效防止 AI 幻覺。

### 2. ⚡ 高效能快取機制 (Caching)
導入 `lru_cache` 技術優化底層資料中心。針對同一檔股票的多次工具呼叫（如：同時查股價、財報、動能），系統僅會向 Yahoo Finance 請求一次原始數據，大幅提升 **80% 以上** 的回應速度。

### 3. 🛡️ 完善的邊界防錯 (Robustness)
- **智能轉譯**：輸入「凌通科技」等中文名稱，系統會自動利用內建知識轉譯為 `4952.TW`。
- **異常處理**：針對台股虧損公司常見的「YoY 無資料」現象，系統具備優雅的攔截機制，確保程式不會崩潰並如實回報。

---

## 🛠️ 系統架構圖 (Architecture)

[在此可放入你的系統架構圖圖片，若無可將此行刪除]

### 系統層次：
* **交互層 (Interaction)**: Streamlit / Web UI。
* **邏輯層 (Reasoning)**: LangChain + Google Gemini 2.5 Flash（專注於低延遲與高效率的工具調度）。
* **工具層 (Tools)**: 五大自定義工具（股價、新聞、基本面、短期動能、公司資訊）。
* **數據層 (Data)**: yfinance API & DuckDuckGo Search。

---

## 📋 標準作業流程 (SOP)

Agent 在接收到指令後，會嚴格執行以下分析步驟：
1. **Company ID**: 確認公司正確代碼與產業定位。
2. **Live Price**: 抓取最新成交價與漲跌幅。
3. **Market News**: 檢索最新新聞並進行情緒摘要（包含外資動向、違約交割等警示）。
4. **Fundamentals**: 分析營收、淨利率等長期基本面指標。
5. **Momentum**: 交叉比對季營收/盈餘成長率，判斷短期爆發力。

---

## 🚀 快速開始 (Quick Start)

### 環境需求
- Python 3.9+
- Google AI Studio API Key

### 安裝步驟
1. 複製本專案：
   ```bash
   git clone https://github.com/Bingyanho/stock-agent-project.git
   cd stock-agent-project
   ```
2. 安裝必要套件：
   ```bash
   pip install -r requirements.txt
   ```
3. 設定 .env 檔案：
   ```bash
   GOOGLE_API_KEY=你的金鑰
   ```
4. 執行應用程式：
   ```bash
   streamlit run app.py
   ```

---

## 🔍 推薦測試情境 (Test Cases)
* **台股測試：**分析台積電 (驗證中文名稱轉代碼)

* **美股測試：**分析 NVDA (驗證全球化數據支援)

* **邏輯測試：**比較 2317 與 2382，誰的財報動能更強？ (驗證多工具交叉推論)

* **防呆測試：**分析一檔黑馬股 A123 (驗證系統對錯誤資訊的防禦力)

---

## ⚠️ 免責聲明
本專案僅供「生成式人工智慧實務應用」課程學術研究使用，不構成任何形式的投資建議。
AI 產出之內容可能存在偏差，投資前請務必參閱官方公開資訊觀測站。

---

## 👨‍💻 作者
何秉諺
國立清華大學 電機工程學系 28級
📧bingyan1008@gmail.com
# 📈 智能台股分析 AI Agent

這是一個基於 **Google Gemini 2.5 Flash** 與 **LangGraph** 框架開發的智能台股分析系統。透過 AI Agent 自動調用外部工具，系統能夠即時抓取台股基本面、財報數據與最新新聞，並具備邏輯推理能力，產出深度的情緒分析與多檔股票綜合比較報告。

## ✨ 核心亮點功能

* **🧠 深度推理與情緒分析**：使用 Gemini 2.5 Flash 進行精準的自然語言理解，突破傳統死板的關鍵字計分，提供具備上下文邏輯的 AI 情緒評分。
* **⚡ 平行工具調用 (Parallel Function Calling)**：支援同時查詢多檔股票（如台積電 vs 聯電），Agent 能夠在單一思考節點內平行發射多個爬蟲請求，大幅提升分析效率。
* **🛡️ 防爬蟲與穩定性機制**：內建請求節流 (Throttling) 機制，避免觸發免費 API (Yahoo Finance, DuckDuckGo) 的封鎖；並透過 LangGraph 的 Session 管理，防止 AI 產生記憶污染與幻覺。

## 🛠️ 技術棧 (Tech Stack)

* **AI 核心**：Google Gemini 2.5 Flash, LangChain, LangGraph
* **後端架構**：FastAPI, Uvicorn, Pydantic
* **前端介面**：Streamlit
* **資料來源**：`yfinance` (Yahoo 財經), `duckduckgo-search` (DuckDuckGo 搜尋)

## 🚀 如何在本地端運行 (Local Setup)

1. **安裝環境依賴套件**：
   ```bash
   pip install -r requirements.txt
import os
import time
from typing import Any
import contextvars # ✨ 新增：用來在背景無感傳遞使用者 ID
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from tools.stock_tools import (
    get_company_info,
    get_stock_price,
    get_stock_news,
    get_financial_report,
    get_recent_momentum,
    get_quant_portfolio_status,
    run_quant_analysis_engine,
    modify_cash_balance,
    correct_buy_position,
    generate_portfolio_pie_chart,
    manual_buy_stock,
    manual_sell_stock
)

load_dotenv()

# ✨ 新增全局變數：存放當下發送請求的使用者 ID
# FastAPI 收到帶有 Token 的請求後，會把解析出來的使用者 ID 放進來，供工具讀取。
current_user_id = contextvars.ContextVar("current_user_id", default=None)

# ─────────────────────────────────────────────
# 1. 建立 LLM (換上穩定的大腦)
# ─────────────────────────────────────────────
def create_llm() -> ChatGoogleGenerativeAI:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("請在環境變數或 .env 中設定 GOOGLE_API_KEY")
    
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", # 使用穩定且支援工具的 2.5 flash
        google_api_key=api_key,
        temperature=0.1,
        max_output_tokens=4096,
        max_retries=5,  
        timeout=120,    
    )

# ─────────────────────────────────────────────
# 2. 系統提示詞 (多使用者 & 動態圖表版)
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """你是一個名叫「阿財」的專業全球金融分析師與「混合型 (Hybrid) 智能投資顧問」AI。
你不僅精通總體經濟與個股分析，同時具備執行「量化交易策略」與「個人專屬帳戶管理」的能力。請用專業、自信但親切的語氣與使用者對話。

# 🛠️【阿財全域核心最高守則】(所有情境適用)
1. 🛑 **代碼轉換與過濾**：若使用者提供中文名稱，請務必自動轉換為代碼（台股如 2330.TW）。傳遞參數給工具時，請確保過濾掉中文，僅傳入正確格式之代碼。
2. 🛑 **多檔分析迭代**：若使用者同時要求分析多檔股票（例如：分析台積電和聯發科），你必須針對「每一檔」股票分別呼叫完整的工具鏈（Info -> Price -> News -> Finance -> Momentum），不可只查其中一檔。

==================================================
🌟【情境 A：單檔或多檔股票分析】
觸發時機：當使用者要求分析特定股票（不論數量）或詢問是否能買進時。

執行步驟：
1. **對每一檔股票**：依序呼叫 `get_company_info`、`get_stock_price`、`get_stock_news`、`get_financial_report` 與 `get_recent_momentum`。
2. **搜尋優化**：呼叫 `get_stock_news` 時，參數請傳入「代碼+中文名稱」（如："2330.TW 台積電"）以提升精準度。
3. 嚴格使用以下 Markdown 格式為每一檔股票輸出獨立報告：

# 📊 [股票名稱] ([股票代碼]) 深度分析報告
**💰 目前報價：** [最新股價] | **🏭 產業類別：** [產業類別]
---
### 1️⃣ 營運與財務亮點
* **營收與獲利表現：** [總結財報數據。若缺失，請以該公司核心業務補充]
* **近期成長動能：** [盈餘成長率、EPS 等動能指標]
* **關鍵亮點：** [該公司的護城河或財報特別之處]

### 2️⃣ 近期市場動態與產業展望
* **🗞️ 最新焦點：** [必須包含來自 get_stock_news 的 1-2 則重點，並說明影響。若無新聞，請寫出該產業的近期大趨勢]
* **🌐 產業佈局：** [補充該公司在關鍵領域如 AI、半導體等的佈局]

### 3️⃣ 技術面與市場預期
* **短期趨勢：** [強勢 / 整理 / 弱勢 評估]
* **市場預期：** [結合基本面與消息面給出評價]

---
### 💡 阿財綜合點評
[融合基本面、消息面與技術面，給出專業分析。]
* **🟢 潛在上漲機會 (Bull Case)：** [利多因素]
* **🔴 潛在下行風險 (Bear Case)：** [風險因素]

### 🌡️ 市場情緒評分：[0-10 分] / 10
* **評分理由：** [總結一句話]

(如果是多檔分析，請在最後加上「阿財的對比建議」區塊)

==================================================
💼【情境 B：查詢帳戶與持股狀況】
觸發時機：當使用者詢問「賺還賠」、「持股狀況」、「資產配置」或要求「畫圓餅圖」時。
執行步驟：
1. 呼叫 `get_quant_portfolio_status` 獲取資金與持股狀態。
2. 呼叫 `generate_portfolio_pie_chart` 觸發前端繪圖。
3. 必須嚴格使用以下 Markdown 格式輸出報告：

# 💼 您的專屬投資組合健康檢查
* **💰 總資產估值：** [計算出的總資產]
* **💵 可用現金餘額：** [現金數值]
* **🍩 資產視覺化：** ✅ 已為您在系統介面同步更新最新的資產配置圓餅圖。

### 📋 目前持股診斷
* **[股票名稱] ([代碼])**：持有 [股數] 股 | 成本價：[價格]
  * *阿財短評：[根據該股近期概況給出一句話的簡短建議，如抱牢、留意停損等]*
*(若無持股，請溫馨提醒目前為空手狀態)*

==================================================
🚀【情境 C：執行量化策略】
觸發時機：當使用者要求「掃描市場」、「執行量化」、「今天該買賣什麼」時。
執行步驟：
1. 呼叫 `run_quant_analysis_engine`。
2. ⚠️【自動質化分析指令】：檢視量化引擎回傳的「買進動作」名單。**如果有建議買進的個股**，請你自動擷取這些股票的代碼，並**主動為每一檔即將買進的股票**呼叫 `get_company_info`、`get_financial_report`、`get_recent_momentum` 與 `get_stock_news` 進行快速掃描。
3. 必須嚴格使用以下 Markdown 格式輸出報告：

# 🤖 每日量化策略執行報告

> **🌍 大盤環境：** [大盤狀態]
> **💰 最新總資產：** [結算資產]

---

### 🛑 賣出動作 (Take Profit / Stop Loss)
* [根據工具回傳的賣出訊息，條列式輸出。若無賣出動作，請寫「✅ 目前無賣出訊號，安心抱牢。」]

### 🎯 買進動作 (New Positions)
[若有買進動作，請嚴格依照下方的 Markdown 表格格式繪製；若無買進動作，請寫「⚠️ 今日無符合條件個股，或因預算/大盤條件暫緩買進。」]

| 股票名稱 | 股票代碼 | 買進股數 | 參考單價 |
| :--- | :--- | :--- | :--- |
| [名稱] | `[代碼]` | [股數] | [價格] |

### 📊 買進名單質化健檢 (Fundamental Check)
[⚠️ 若今日無買進動作，請直接省略此區塊。若有買進，請根據你在步驟 2 呼叫工具所獲得的資料所有買進的股票寫出 1~2 句話的精華總結，融合其營收動能與最新新聞焦點。]
* **[股票名稱] (`[代碼]`)**：[例如：近期營收受惠 AI 伺服器大幅成長創下新高，惟需留意短線外資籌碼鬆動之新聞事件。]

### 🔍 動能觀察名單 (Watchlist)
🏷️ [將工具回傳的前 5 檔潛力名單代碼，使用反單引號包裝，並用頓號分隔，例如：`2454.TW`、`3037.TW`]
==================================================
🛠️【情境 D：帳戶資料校正與手動下單】
觸發時機：當使用者要求「手動買賣/新增股票」、「修改現金餘額」或「建立初始庫存」時。
執行步驟：
1. 若使用者要求買進/新增持股，呼叫 `manual_buy_stock`。
2. 若使用者要求賣出/減少持股，呼叫 `manual_sell_stock`。
3. 若使用者單純修改現金，呼叫 `modify_cash_balance`。
4. 以親切的語氣回報執行結果，並提醒使用者可查看左側更新後的圓餅圖。
==================================================
"""

TOOLS = [
    get_company_info,
    get_stock_price,
    get_stock_news,
    get_financial_report,
    get_recent_momentum,
    get_quant_portfolio_status,
    run_quant_analysis_engine,
    modify_cash_balance,
    correct_buy_position,
    generate_portfolio_pie_chart,
    manual_buy_stock,
    manual_sell_stock
]

class StockAnalysisSession:
    def __init__(self):
        llm = create_llm()
        self.agent_executor = create_react_agent(llm, TOOLS)
        self.chat_history: list[Any] = []

    def analyze(self, user_input: str) -> dict:
        self.chat_history.clear()
        messages = [SystemMessage(content=SYSTEM_PROMPT)]
        messages.extend(self.chat_history)
        messages.append(HumanMessage(content=user_input))

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                result = self.agent_executor.invoke(
                    {"messages": messages},
                    config={"recursion_limit": 50}
                )
                raw_content = result["messages"][-1].content
                final_output = raw_content if isinstance(raw_content, str) else "".join(
                    b["text"] for b in raw_content if isinstance(b, dict) and b.get("type") == "text"
                )

                self.chat_history.append(HumanMessage(content=user_input))
                self.chat_history.append(AIMessage(content=final_output))
                
                # 計算使用的工具數量
                tool_calls_count = (len(result["messages"]) - len(messages)) // 2

                return {
                    "output": final_output,
                    "steps": tool_calls_count
                }

            except Exception as e:
                error_msg = str(e)
                print(f"\n[系統除錯] 🛑 偵測到原始錯誤: {repr(e)}") 
                
                if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                    if attempt < max_attempts - 1:
                        print(f"\n⚠️ 觸發流量限制！強制休眠 60 秒後進行第 {attempt + 2} 次重試...")
                        time.sleep(60)
                    else:
                        raise Exception("API 額度已耗盡，重試 3 次失敗。請稍後再試。")
                else:
                    raise e

    def reset(self):
        self.chat_history = []
        print("✅ 對話歷史已清除")

# ─────────────────────────────────────────────
# 5. CLI 介面 (終端機測試專用)
# ─────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  📈 智能財報與新聞分析 Agent「阿財」 (多租戶資料庫版)")
    print("  輸入股票代碼 (如: 2330 或 3529) 或問題開始分析")
    print("=" * 60)

    try:
        session = StockAnalysisSession()
        # ✨ 新增：如果在終端機直接執行測試，預設假裝是 user_id = 1 登入
        current_user_id.set(1) 
        print("💡 [系統提示] 目前以 CLI 模式執行，預設綁定使用者 ID: 1")
    except Exception as e:
        print(f"❌ 初始化失敗：{e}")
        return

    while True:
        user_input = input("\n🧑 你：").strip()
        if not user_input: continue
        if user_input.lower() == "exit": break
        if user_input.lower() == "reset":
            session.reset()
            continue

        print("\n🤖 阿財正在分析中...")
        try:
            result = session.analyze(user_input)
            print("-" * 60)
            print(result["output"])
            print("-" * 60)
            print(f"(本次分析使用了約 {result['steps']} 個工具步驟)")
        except Exception as e:
            print(f"\n❌ 分析過程發生錯誤: {e}")

if __name__ == "__main__":
    main()
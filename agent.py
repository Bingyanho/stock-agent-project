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

🚨【最高指導原則：絕對不可捏造資料與干涉紀律】🚨
1. 反幻覺鐵則：若工具回傳「無法取得」或查無資料，必須如實回答「目前無法取得該資料」，絕對不可自行瞎掰數據或新聞。
2. 參數傳遞鐵則：單檔股票工具的 `symbol` 參數「必須且只能」是股票代號 (台股請務必加上 .TW 或 .TWO，例如 2330.TW；美股請直接輸入代碼如 AAPL)。
3. 尊重量化紀律：嚴格遵守量化引擎給出的買賣訊號，不可自行修改系統判斷的買賣點。

==================================================
🌟【情境 A：單檔股票深度分析】
觸發時機：當使用者單純詢問某檔特定股票（如：幫我分析台積電、蘋果能買嗎）時。
執行步驟：
1. 依序呼叫 `get_company_info`、`get_stock_price`。
2. 呼叫 `get_stock_news`、`get_financial_report` 與 `get_recent_momentum`。
3. 必須嚴格使用以下 Markdown 格式輸出報告：

# 📊 [股票名稱] ([股票代碼]) 深度分析報告
**💰 目前報價：** [最新股價] | **🏭 產業類別：** [產業類別]
---
### 1️⃣ 營運與財務亮點
* **營收與獲利：** [總結財報與動能工具的回傳數據]
* **關鍵亮點：** [列出財報中值得注意的特別事項]

### 2️⃣ 近期市場動態
* **[新聞事件 1 標題]：** [簡要說明對公司的影響]
* **[新聞事件 2 標題]：** [簡要說明對公司的影響]

### 3️⃣ 技術面與籌碼動能
* **短期趨勢：** [根據動能數據給出強勢/整理/弱勢評估]

---
### 💡 阿財綜合點評
[融合基本面、消息面與技術面，給出 1-2 段專業且客觀的綜合分析，指出潛在上漲機會與下行風險。]

### 🌡️ 市場情緒評分：[0-10 分] / 10
*(0=極度悲觀，5=中立，10=極度樂觀)*
* **評分理由：** [用一句話總結為何給出此分數]

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
2. 必須嚴格使用以下 Markdown 格式輸出報告：

# 🤖 每日量化策略執行報告
**🌍 大盤環境狀態：** [大盤狀態] | **💰 最新總資產：** [結算資產]
---
### 🛑 賣出動作 (Take Profit / Stop Loss)
[列出工具回傳的賣出訊息，若無則寫「✅ 目前無賣出訊號，持股續抱。」]

### 🎯 買進動作 (New Positions)
[列出工具回傳的買進訊息，若無則寫「⚠️ 今日無符合條件個股，或因預算/大盤條件暫緩買進。」]

### 🔍 動能觀察名單 (Watchlist)
* [列出前 5 檔潛力名單]

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
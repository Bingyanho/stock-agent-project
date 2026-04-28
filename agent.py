import os
import time
from typing import Any
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
    correct_buy_position
)

load_dotenv()

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
# 2. 系統提示詞 (終極防呆版)
# ─────────────────────────────────────────────
SYSTEM_PROMPT = """你是一個名叫「阿財」的專業全球金融分析師與「混合型 (Hybrid) 智能投資顧問」AI。
你不僅精通台灣股市（台股）與美國股市（美股）的數據與新聞分析，同時具備執行「量化交易策略」與「帳戶管理」的能力。

🚨【最高指導原則：絕對不可捏造資料與干涉紀律】🚨
1. **反幻覺鐵則**：如果某個工具回傳「找不到資料」、「未知」或「發生錯誤」，你必須在報告中如實寫出「無法取得該項資料」，絕對不可以用你自己的記憶去瞎掰、腦補或張冠李戴！
2. **參數傳遞鐵則**：所有呼叫單檔股票工具的 `symbol` 參數「必須且只能」是股票代號（例如 2330, 4952, AAPL）。如果使用者輸入的是「公司中文/英文名稱」，你必須先利用你的內建知識，將其轉換為「正確的股票代碼」後，再傳入工具中！絕對不可以把中文名稱直接丟給工具！
3. **尊重量化紀律**：如果量化引擎給出「賣出」或「大盤轉空」的訊號，AI 絕對不可以建議使用者凹單或加碼，必須嚴格遵守紀律。

請根據使用者的問題，判斷並執行以下三種【標準作業流程 (SOP)】之一：

==================================================
🌟【情境 A：單檔股票深度分析】(當使用者詢問特定一檔或多檔股票時)
你必須「依序」完成以下步驟：
1. `get_company_info`：確認公司正確名稱與產業。
2. `get_stock_price`：確認最新股價與漲跌走勢。
3. `get_stock_news`：確認近期市場消息面與新聞。
4. `get_financial_report`：確認長期財務基石（營收、淨利）。
5. `get_recent_momentum`：確認「短期成長動能」（季營收/盈餘成長率、EPS）。

【特別指令：深度情緒與動能分析】
1. 結合新舊數據：將長期財務與短期成長率(YoY)交叉比對。如果總營收高但成長率下滑，給予謹慎評價；若成長率顯著轉正，視為潛在利多。
2. 情緒評分：綜合考量上下文，給出 0 到 10 分的情緒分數（0=極度悲觀，5=中立，10=極度樂觀）。

回報格式（🚨 務必使用標準 Markdown 純文字撰寫，絕對禁止使用 HTML 標籤）：
## 📊 [股票名稱] ([股票代號]) 綜合分析報告
### 🟢 利多因素
* **[重點關鍵字]**：[詳細說明，包含近期成長動能指標...]
### 🔴 利空因素
* **[重點關鍵字]**：[詳細說明...] (如無則寫：目前無法取得明確的利空因素)
---
### 🧠 AI 情緒綜合解析
* **🎯 情緒評分：** [分數] / 10
* **📝 判斷理由：** [結合消息面、財務面與動能面總結...]

==================================================
💼【情境 B：查詢帳戶與持股狀況】(當使用者問「我現在賺還賠」、「目前持股狀況」或「持股風險」時)
1. 呼叫 `get_quant_portfolio_status` 獲取最新的帳戶現金、總資產與持股清單 (JSON格式)。
2. 針對「目前持有」的股票，主動呼叫 `get_stock_news` 獲取最新市場消息。
3. 產出【📊 投資組合健康檢查報告】：
   - 列出目前總資產、現金與報酬率。
   - 針對有潛在風險（新聞偏空）的持股提出強烈警告。
   - 針對獲利豐厚且新聞偏多的持股，給予抱牢建議。

==================================================
🚀【情境 C：執行量化策略】(當使用者要求「跑今天的交易程式」、「產出交易日報」或「執行量化掃描」時)
1. 直接呼叫 `run_quant_analysis_engine`。
2. 根據工具回傳的數據，排版成易於閱讀的【📈 今日量化交易決策報告】。
3. [AI 附加價值]：從「建議買進」的股票，快速呼叫 `get_stock_news` 和 `get_recent_momentum`，並在報告結尾補充你的「AI 質化觀點背書」。

==================================================
🛠️【情境 D：帳戶資料校正與手動修改】(當使用者要求「修改現金」或「更新實際買進價格/股數」時)
你有權限協助使用者校正本地資料庫的帳務誤差。
1. 若使用者要求修改現金餘額：呼叫 `modify_cash_balance`。
2. 若使用者要求更新特定股票的買進紀錄（如價格、股數）：
   - 務必先將使用者提到的公司名稱轉換為股票代碼（如 2330.TW）。
   - 呼叫 `correct_buy_position`。
3. 執行完畢後，產出【✅ 帳戶更新報告】，用親切專業的語氣向使用者確認更新結果，並列出目前的剩餘現金。
==================================================
---
⚠️ **免責聲明**：以上分析僅供學術與系統測試參考，不構成任何真實投資建議。
"""

# ─────────────────────────────────────────────
# 3. 工具清單
# ─────────────────────────────────────────────
TOOLS = [
    get_company_info,
    get_stock_price,
    get_stock_news,
    get_financial_report,
    get_recent_momentum,
    get_quant_portfolio_status,
    run_quant_analysis_engine,
    modify_cash_balance,
    correct_buy_position
]

# ─────────────────────────────────────────────
# 4. 對話管理與 Agent 執行
# ─────────────────────────────────────────────
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
                # 執行 Agent，並放寬思考步數到 15 步
                result = self.agent_executor.invoke(
                    {"messages": messages},
                    config={"recursion_limit": 50}
                )

                # 解析最後回傳的文字內容
                raw_content = result["messages"][-1].content
                if isinstance(raw_content, list):
                    final_output = "".join(
                        block["text"] for block in raw_content if isinstance(block, dict) and block.get("type") == "text"
                    )
                else:
                    final_output = raw_content

                # 更新對話紀錄
                self.chat_history.append(HumanMessage(content=user_input))
                self.chat_history.append(AIMessage(content=final_output))

                generated_msgs = len(result["messages"]) - len(messages)
                tool_calls_count = generated_msgs // 2 if generated_msgs > 0 else 0

                return {
                    "output": final_output,
                    "steps": tool_calls_count,
                }

            except Exception as e:
                error_msg = str(e)
                
                # 👈 【新增這行】把最原始的錯誤訊息印出來，我們來抓真兇！
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
# 5. CLI 介面
# ─────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  📈 智能財報與新聞分析 Agent「阿財」 (期末專案版)")
    print("  輸入股票代碼 (如: 2330 或 3529) 或問題開始分析")
    print("=" * 60)

    try:
        session = StockAnalysisSession()
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

        print("\n🤖 阿財正在調用工具並分析資料中...\n")
        try:
            result = session.analyze(user_input)
            print(f"{'─'*60}")
            print(result["output"])
            print(f"{'─'*60}")
            print(f"（本次分析使用了約 {result['steps']} 個工具步驟）")
        except Exception as e:
            print(f"❌ 分析時發生錯誤：{e}")

if __name__ == "__main__":
    main()
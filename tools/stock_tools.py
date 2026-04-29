import yfinance as yf
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
import time
from functools import lru_cache # 🌟 新增：引入快取模組
from stock_quant import run_daily_strategy, DB_FILE
import json
import os
import matplotlib.pyplot as plt

plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'PingFang HK', 'SimHei', 'Arial Unicode MS'] 
plt.rcParams['axes.unicode_minus'] = False

def _get_valid_ticker(symbol: str) -> str:
    """自動判斷台股或美股代碼"""
    symbol = str(symbol).strip().upper() # 轉大寫，例如 aapl 變 AAPL
    
    # 如果已經有後綴了（如 .TW, .TWO, .US），就直接回傳
    if "." in symbol:
        return symbol
    
    # 如果全是數字，判定為台股，加上 .TW
    if symbol.isdigit():
        return f"{symbol}.TW"
    
    # 如果包含英文字母，判定為美股（或其他市場），直接回傳
    # yfinance 預設美股不需後綴
    return symbol

# 🌟 新增：建立快取中心，相同的股票代碼只會向 Yahoo 請求一次資料！
@lru_cache(maxsize=10)
def _get_stock_info(ticker_str: str):
    print(f"   -> [網路請求] 向 Yahoo 索取 {ticker_str} 底層資料 (有快取就不會重複出現)...", flush=True)
    time.sleep(1) # 溫柔地停頓一下，避免被鎖
    return yf.Ticker(ticker_str).info

def load_account():
    if not os.path.exists(DB_FILE):
        return {"cash": 200000, "portfolio": [], "cooldowns": {}}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_account(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

@tool
def get_company_info(symbol: str) -> str:
    """取得公司正式名稱與產業類別"""
    print(f"\n[Tool] 抓取公司資料: {symbol}", flush=True)
    ticker_str = _get_valid_ticker(symbol)
    try:
        # 🌟 改用快取中心拿資料
        info = _get_stock_info(ticker_str)
        
        # 這裡加上明確的標註，告訴 Agent 這是官方資料
        official_name = info.get("longName", "未知")
        short_name = info.get("shortName", "未知")
        sector = info.get("sector", "未知")
        
        return f"【官方紀錄名稱】: {official_name} (簡稱: {short_name}), 產業: {sector}"
    except Exception as e:
        return f"無法取得代碼 {symbol} 的正式名稱。"
    

@tool
def get_stock_price(symbol: str) -> str:
    """取得當前股價數據"""
    print(f"\n[Tool] 抓取股價: {symbol}", flush=True)
    ticker_str = _get_valid_ticker(symbol)
    try:
        # 🌟 改用快取中心拿資料 (如果剛剛查過公司資料，這裡會瞬間完成！)
        info = _get_stock_info(ticker_str)
        
        # 直接從 info 裡面安全地把股價拿出來
        price = info.get('currentPrice', info.get('regularMarketPrice', '無法取得'))
        prev = info.get('previousClose', '無法取得')
        return f"目前股價: {price}, 昨收價: {prev}"
    except Exception as e:
        print(f"❌ [錯誤 - 股價] {e}", flush=True)
        return "⚠️ 股價暫時無法取得"

@tool
def get_stock_news(symbol: str) -> str:
    """透過搜尋引擎取得最新新聞"""
    print(f"\n[Tool] 搜尋新聞: {symbol}", flush=True)
    time.sleep(2) # 避免被搜尋引擎封鎖
    
    # 🌟 順手幫你優化：如果是美股，用英文搜尋比較準；台股維持中文
    query = f"台股 {symbol} 最新財經新聞分析" if symbol.isdigit() else f"US stock {symbol} latest financial news"
    
    try:
        search = DuckDuckGoSearchRun()
        results = search.run(query)
        
        if results:
            # 👇 核心修改：設定最大字數限制 (這裡設為 1000 字)
            max_chars = 1000
            if len(results) > max_chars:
                results = results[:max_chars] + "\n...(為節省記憶體，已截斷後續新聞內容)"
            
            return f"🔍 搜尋結果：\n{results}"
        else:
            return "近期無重大新聞。"
            
    except Exception as e:
        print(f"❌ [錯誤 - 新聞搜尋] {e}", flush=True)
        return "⚠️ 新聞搜尋目前無法使用"

@tool
def get_financial_report(symbol: str) -> str:
    """取得財務簡報"""
    print(f"\n[Tool] 抓取財報: {symbol}", flush=True)
    ticker_str = _get_valid_ticker(symbol)
    try:
        # 🌟 改用快取中心拿資料 (瞬間完成！)
        info = _get_stock_info(ticker_str)
        rev = info.get('totalRevenue', "無法取得")
        margins = info.get('profitMargins', "無法取得")
        return f"代碼: {ticker_str}, 總營收: {rev}, 淨利率: {margins}"
    except Exception as e:
        print(f"❌ [錯誤 - 財報] {e}", flush=True)
        return "⚠️ 財報系統暫時無法讀取"
    
@tool
def get_recent_momentum(symbol: str) -> str:
    """取得公司近期的短期財務動能 (包含季營收成長率、季盈餘成長率與EPS)"""
    print(f"\n[Tool] 抓取近期動能: {symbol}", flush=True)
    ticker_str = _get_valid_ticker(symbol)
    try:
        # 🌟 再次受惠於 Cache 機制，這裡會瞬間完成，不用重新連線！
        info = _get_stock_info(ticker_str)
        
        # 取得近期(季度)成長性指標
        q_rev_growth = info.get('quarterlyRevenueGrowth')
        q_earn_growth = info.get('earningsGrowth')
        trailing_eps = info.get('trailingEps', '無法取得')

        # 幫助小數點轉換為百分比，方便 AI 大腦閱讀
        def fmt_pct(val):
            if isinstance(val, (int, float)):
                return f"{val * 100:.2f}%"
            return "無資料"

        return (
            f"【{ticker_str} 短期財報動能】\n"
            f"- 季營收成長率 (YoY): {fmt_pct(q_rev_growth)}\n"
            f"- 季盈餘成長率 (YoY): {fmt_pct(q_earn_growth)}\n"
            f"- 近四季累積 EPS: {trailing_eps}"
        )
    except Exception as e:
        print(f"❌ [錯誤 - 近期動能] {e}", flush=True)
        return "⚠️ 近期動能指標暫時無法取得"
    
@tool
def get_quant_portfolio_status():
    """
    讀取目前的量化交易帳戶狀態，包含現金、持股明細、總資產與報酬率。
    當使用者問『我現在賺多少？』或『我的持股狀況如何？』時使用。
    """
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            account = json.load(f)
        # 這裡可以加入一些簡單的計算逻辑，回傳易於 AI 閱讀的字串
        return json.dumps(account, ensure_ascii=False)
    except Exception as e:
        return f"無法讀取帳戶資料: {e}"

@tool
def run_quant_analysis_engine():
    """
    執行量化掃描與交易策略邏輯。會產出今日的大盤訊號、買進指令、賣出指令與動能雷達。
    當使用者要求『執行今天的分析』或『產出交易報告』時使用。
    """
    try:
        # 執行你原本程式中的核心函式
        account, equity, market_status, sell_msg, buy_msg, watchlist = run_daily_strategy()
        
        report_summary = {
            "大盤環境": market_status,
            "建議賣出": sell_msg,
            "建議買進": buy_msg,
            "總資產": f"{equity:,.0f}",
            "動能觀察名單": watchlist[:5] # 只給前五名避免 token 太長
        }
        return json.dumps(report_summary, ensure_ascii=False)
    except Exception as e:
        return f"執行量化引擎時出錯: {e}"
    
@tool
def modify_cash_balance(new_cash: float) -> str:
    """
    手動校正虛擬帳戶的可用現金餘額。
    當使用者說「將帳戶現金修改為 XXX」、「幫我把現金設定成 XXX」時呼叫此工具。
    """
    try:
        account = load_account()
        old_cash = account.get('cash', 0)
        account['cash'] = float(new_cash)
        save_account(account)
        return f"帳戶現金校正完成！原本餘額：{old_cash:,.0f} 元，更新後餘額：{new_cash:,.0f} 元。"
    except Exception as e:
        return f"修改現金失敗：{e}"

@tool
def correct_buy_position(ticker: str, real_price: float, real_shares: int) -> str:
    """
    同步真實買進價格與股數，用來校正帳戶內的持倉紀錄。
    當使用者說「我實際買進 XXX，價格 YYY，股數 ZZZ，請幫我更新」時呼叫此工具。
    傳入的 ticker 必須是完整的股票代號 (如 2330.TW)。
    """
    try:
        ticker = str(ticker).upper()
        if not (".TW" in ticker or ".TWO" in ticker): 
            ticker += ".TW"

        account = load_account()
        found = False
        for pos in account['portfolio']:
            if pos['Ticker'] == ticker:
                # 1. 把舊的預估扣款加回去
                old_est_cost = pos['Shares'] * pos['Entry_Price']
                account['cash'] += old_est_cost
                # 2. 更新成真實數據
                pos['Entry_Price'] = float(real_price)
                pos['Shares'] = int(real_shares)
                # 3. 扣除真實款項
                account['cash'] -= (real_price * real_shares)
                found = True
                break
                
        if found:
            save_account(account)
            return f"買進對帳完成！【{ticker}】已修正為 {real_shares} 股 @ {real_price}元。目前庫存剩餘現金: {account['cash']:,.0f} 元。"
        else:
            return f"找不到 {ticker} 的持倉紀錄，請確認是否已在策略中成交。"
    except Exception as e:
        return f"修正持倉失敗：{e}"

@tool
def generate_portfolio_pie_chart() -> str:
    """
    繪製目前帳戶的資產現值分布圖（包含現金與各檔持股的即時市值比例）。
    當使用者要求「畫圓餅圖」、「顯示資產比例」、「繪製持股分布」時呼叫此工具。
    """
    try:
        # 1. 讀取帳戶資料
        db_file = "trading_account.json"
        if not os.path.exists(db_file):
            return "錯誤：找不到帳戶資料檔。"
        
        with open(db_file, "r", encoding="utf-8") as f:
            account = json.load(f)
            
        cash = account.get('cash', 0)
        portfolio = account.get('portfolio', [])
        
        labels = []
        sizes = []
        
        # 2. 加入可用現金
        if cash > 0:
            labels.append(f"現金\n{cash:,.0f} 元")
            sizes.append(cash)
            
        # 3. 獲取當前股價並計算「即時市值」
        for pos in portfolio:
            ticker = pos.get('Ticker', '')
            name = pos.get('Name', ticker)
            shares = pos.get('Shares', 0)
            
            if shares > 0 and ticker:
                # 抓取最新股價
                try:
                    stock = yf.Ticker(ticker)
                    # 獲取最近一個交易日的收盤價
                    current_price = stock.history(period="1d")['Close'].iloc[-1]
                except Exception:
                    # 如果網路異常抓不到，退回使用成本價作為保底方案
                    current_price = pos.get('Entry_Price', 0)
                    
                current_value = shares * current_price  # 市值 = 股數 * 現價
                
                if current_value > 0:
                    labels.append(f"{name}\n{current_value:,.0f} 元")
                    sizes.append(current_value)
                
        if not sizes:
            return "帳戶中目前沒有資產或現金可以繪製圖表。"
            
        # 4. 繪製現代感甜甜圈圖 (Donut Chart)
        plt.figure(figsize=(10, 8)) # 稍微放大畫布比例
        colors = plt.cm.Set3.colors # 換一組更清晰、對比度更好的配色
        
        # 設定每個區塊微微分開 (explode)
        explode = [0.03] * len(sizes)
        
        wedges, texts, autotexts = plt.pie(
            sizes, 
            labels=labels, 
            autopct='%1.1f%%', 
            startangle=140, 
            colors=colors, 
            explode=explode,
            pctdistance=0.82, # 調整百分比數字的位置
            textprops={'fontsize': 13, 'fontweight': 'bold'} # 🔥 加大、加粗標籤字體
        )
        
        # 讓百分比的數字更醒目
        for autotext in autotexts:
            autotext.set_fontsize(14)
            autotext.set_color('darkred')
            
        # 畫中間的白圓，製造甜甜圈效果
        centre_circle = plt.Circle((0,0), 0.65, fc='white')
        fig = plt.gcf()
        fig.gca().add_artist(centre_circle)
        
        # 在甜甜圈正中間加上「總資產」資訊
        total_value = sum(sizes)
        plt.text(0, 0, f"總資產現值\n{total_value:,.0f} 元", 
                 ha='center', va='center', fontsize=18, fontweight='bold', color='dimgrey')
            
        plt.title('📊 投資組合即時現值分布', fontsize=20, fontweight='bold', pad=20)
        plt.axis('equal') 
        
        # 5. 存檔為圖片
        save_path = "portfolio_pie.png"
        plt.savefig(save_path, bbox_inches='tight', dpi=300) # dpi=300 讓畫質變超清晰
        plt.close() 
        
        return f"✅ 資產現值圖表已成功生成 (已連線抓取最新股價計算)，並儲存為 `{save_path}`。"
        
    except Exception as e:
        return f"繪製圖表失敗：{e}"
import yfinance as yf
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
import time

# 內部輔助函數：自動判斷上市 (.TW) 或上櫃 (.TWO)
def _get_valid_ticker(symbol: str) -> str:
    # 如果使用者已經輸入了後綴，就直接用
    if symbol.endswith(".TW") or symbol.endswith(".TWO"):
        return symbol
    
    # 先測試上市 (.TW)
    ticker_tw = f"{symbol}.TW"
    stock_tw = yf.Ticker(ticker_tw)
    if not stock_tw.history(period="1d").empty:
        return ticker_tw
        
    # 如果上市找不到，測試上櫃 (.TWO)
    ticker_two = f"{symbol}.TWO"
    stock_two = yf.Ticker(ticker_two)
    if not stock_two.history(period="1d").empty:
        return ticker_two
        
    # 如果都找不到，回傳一個明確的錯誤字串讓 Agent 知道
    time.sleep(1)
    return "NOT_FOUND"

@tool
def get_company_info(symbol: str) -> str:
    """取得公司基本資料與產業類別，必須傳入股票代碼 (如: 2330)"""
    valid_ticker = _get_valid_ticker(symbol)
    if valid_ticker == "NOT_FOUND":
        return f"錯誤：資料庫找不到代碼 {symbol} 的公司，請不要自行編造資料。"
        
    info = yf.Ticker(valid_ticker).info
    name = info.get("longName", "未知名稱")
    sector = info.get("sector", "未知產業")
    industry = info.get("industry", "未知子產業")
    time.sleep(4)
    return f"公司名稱: {name}, 產業: {sector} - {industry}"

@tool
def get_stock_price(symbol: str) -> str:
    """取得當前股價與基本數據，必須傳入股票代碼"""
    valid_ticker = _get_valid_ticker(symbol)
    if valid_ticker == "NOT_FOUND":
        return f"錯誤：無法取得 {symbol} 的股價資料。"
        
    info = yf.Ticker(valid_ticker).info
    current_price = info.get("currentPrice", info.get("regularMarketPrice", "未知"))
    previous_close = info.get("previousClose", "未知")
    time.sleep(1)
    return f"目前股價: {current_price}, 昨收價: {previous_close}"

@tool
def get_stock_news(symbol: str) -> str:
    """取得近期相關新聞標題，必須傳入股票代碼"""
    # 我們不再依賴 yfinance 的新聞，直接組裝關鍵字讓 DuckDuckGo 去查台灣新聞
    query = f"台股 {symbol} 最新財經新聞"
    print(f"\n[系統提示] 🌐 強制啟動繁體中文網路搜尋: {query}...")
    
    try:
        search = DuckDuckGoSearchRun()
        results = search.run(query)
        
        if not results:
            time.sleep(1)
            return "近期無重大新聞。"
        time.sleep(1)
        return f"最新網路搜尋結果：\n{results}"
    except Exception as e:
        print(f"\n[系統提示] ❌ 搜尋發生錯誤: {e}")
        time.sleep(1)
        return "搜尋引擎暫時無法使用，請回報無法取得新聞。"

@tool
def get_financial_report(symbol: str) -> str:
    """取得最新財報摘要 (營收、毛利率等)，必須傳入股票代碼"""
    valid_ticker = _get_valid_ticker(symbol)
    if valid_ticker == "NOT_FOUND":
        return "錯誤：無法取得財報資料。"
        
    info = yf.Ticker(valid_ticker).info
    revenue = info.get("totalRevenue", "未知")
    margins = info.get("profitMargins", "未知")
    time.sleep(1)
    return f"總營收: {revenue}, 淨利率: {margins}"

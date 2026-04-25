import yfinance as yf
import requests
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
import time

# 🌟 終極解藥 1：建立一個「偽裝成真人瀏覽器」的連線 Session
custom_session = requests.Session()
custom_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})

def _get_valid_ticker(symbol: str) -> str:
    """自動判斷上市或上櫃，加入防呆與偽裝機制"""
    if symbol.endswith(".TW") or symbol.endswith(".TWO"):
        return symbol
    
    # 🌟 終極解藥 2：全面加上 try...except 捕捉 Yahoo 的阻擋
    try:
        time.sleep(1)
        ticker_tw = f"{symbol}.TW"
        # 傳入偽裝的 session
        stock_tw = yf.Ticker(ticker_tw, session=custom_session)
        if not stock_tw.history(period="1d").empty:
            return ticker_tw
    except Exception:
        pass # 如果報錯就略過，試試看上櫃
        
    try:
        time.sleep(1)
        ticker_two = f"{symbol}.TWO"
        stock_two = yf.Ticker(ticker_two, session=custom_session)
        if not stock_two.history(period="1d").empty:
            return ticker_two
    except Exception:
        pass
        
    return "NOT_FOUND"

@tool
def get_company_info(symbol: str) -> str:
    """取得公司基本資料與產業類別"""
    valid_ticker = _get_valid_ticker(symbol)
    if valid_ticker == "NOT_FOUND":
        return f"⚠️ 無法取得 {symbol} 的公司基本資料 (可能受到 Yahoo 阻擋或代碼錯誤)。"
        
    try:
        time.sleep(1)
        info = yf.Ticker(valid_ticker, session=custom_session).info
        name = info.get("longName", "未知名稱")
        sector = info.get("sector", "未知產業")
        industry = info.get("industry", "未知子產業")
        return f"公司名稱: {name}, 產業: {sector} - {industry}"
    except Exception as e:
        return "⚠️ Yahoo 財經伺服器阻擋，暫時無法取得公司資料。"

@tool
def get_stock_price(symbol: str) -> str:
    """取得當前股價與基本數據"""
    valid_ticker = _get_valid_ticker(symbol)
    if valid_ticker == "NOT_FOUND":
        return f"⚠️ 無法取得 {symbol} 的股價資料。"
        
    try:
        time.sleep(1)
        info = yf.Ticker(valid_ticker, session=custom_session).info
        current_price = info.get("currentPrice", info.get("regularMarketPrice", "未知"))
        previous_close = info.get("previousClose", "未知")
        return f"目前股價: {current_price}, 昨收價: {previous_close}"
    except Exception as e:
        return "⚠️ Yahoo 財經伺服器阻擋，暫時無法取得股價。"

@tool
def get_financial_report(symbol: str) -> str:
    """取得最新財報摘要"""
    valid_ticker = _get_valid_ticker(symbol)
    if valid_ticker == "NOT_FOUND":
        return "⚠️ 無法取得財報資料。"
        
    try:
        time.sleep(1)
        info = yf.Ticker(valid_ticker, session=custom_session).info
        revenue = info.get("totalRevenue", "未知")
        margins = info.get("profitMargins", "未知")
        return f"總營收: {revenue}, 淨利率: {margins}"
    except Exception as e:
        return "⚠️ Yahoo 財經伺服器阻擋，暫時無法取得財報。"

@tool
def get_stock_news(symbol: str) -> str:
    """取得近期相關新聞標題"""
    time.sleep(3) # 避開 DuckDuckGo 阻擋
    query = f"台股 {symbol} 最新財經新聞"
    
    try:
        search = DuckDuckGoSearchRun()
        results = search.run(query)
        if not results:
            return "近期無重大新聞。"
        return f"最新網路搜尋結果：\n{results}"
    except Exception as e:
        return "⚠️ 搜尋引擎頻率過高被阻擋，請使用其他已知資訊分析。"
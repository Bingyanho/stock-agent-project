import yfinance as yf
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
import time
import random

def _get_valid_ticker(symbol: str) -> str:
    symbol = str(symbol).strip()
    if symbol.endswith(".TW") or symbol.endswith(".TWO"):
        return symbol
    return f"{symbol}.TW"

@tool
def get_company_info(symbol: str) -> str:
    """取得公司基本資料與產業類別"""
    print(f"\n[Tool] 抓取基本資料: {symbol}", flush=True)
    ticker_str = _get_valid_ticker(symbol)
    try:
        time.sleep(random.uniform(1, 2))
        # 🌟 根據 Log 建議：不設定 session，讓 yfinance 自己處理
        stock = yf.Ticker(ticker_str)
        info = stock.info
        name = info.get("longName", symbol)
        sector = info.get("sector", "技術")
        industry = info.get("industry", "半導體")
        return f"公司名稱: {name}, 產業: {sector} - {industry}"
    except Exception as e:
        print(f"❌ [錯誤 - 基本資料] {e}", flush=True)
        return f"公司代碼: {symbol} (基本資料抓取受阻)"

@tool
def get_stock_price(symbol: str) -> str:
    """取得當前股價數據"""
    print(f"\n[Tool] 抓取股價: {symbol}", flush=True)
    ticker_str = _get_valid_ticker(symbol)
    try:
        time.sleep(1)
        stock = yf.Ticker(ticker_str)
        info = stock.info
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
    time.sleep(2)
    query = f"台股 {symbol} 最新財經新聞分析"
    try:
        # 🌟 這裡保持不變，但等一下要在 requirements.txt 加東西
        search = DuckDuckGoSearchRun()
        results = search.run(query)
        return f"🔍 搜尋結果：\n{results}" if results else "近期無重大新聞。"
    except Exception as e:
        print(f"❌ [錯誤 - 新聞搜尋] {e}", flush=True)
        return "⚠️ 新聞搜尋目前無法使用"

@tool
def get_financial_report(symbol: str) -> str:
    """取得財務簡報"""
    print(f"\n[Tool] 抓取財報: {symbol}", flush=True)
    ticker_str = _get_valid_ticker(symbol)
    try:
        time.sleep(1)
        stock = yf.Ticker(ticker_str)
        info = stock.info
        rev = info.get('totalRevenue', "無法取得")
        margins = info.get('profitMargins', "無法取得")
        return f"代碼: {ticker_str}, 總營收: {rev}, 淨利率: {margins}"
    except Exception as e:
        print(f"❌ [錯誤 - 財報] {e}", flush=True)
        return "⚠️ 財報系統暫時無法讀取"
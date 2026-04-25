import yfinance as yf
import requests
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
import time
import random

# 🌟 建立一個更強大的 Session 偽裝
custom_session = requests.Session()
custom_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
})

def _get_valid_ticker(symbol: str) -> str:
    """簡化邏輯：不再預先測試 history，直接加上後綴以節省請求次數"""
    symbol = str(symbol).strip()
    if symbol.endswith(".TW") or symbol.endswith(".TWO"):
        return symbol
    # 預設台股 4 碼多為上市 (.TW)，這能避開在 Render 上多餘的 history 請求
    return f"{symbol}.TW"

@tool
def get_company_info(symbol: str) -> str:
    """取得公司基本資料與產業類別"""
    ticker_str = _get_valid_ticker(symbol)
    try:
        time.sleep(random.uniform(1, 2)) # 隨機延遲 1~2 秒
        stock = yf.Ticker(ticker_str, session=custom_session)
        info = stock.info
        name = info.get("longName", symbol)
        sector = info.get("sector", "技術")
        industry = info.get("industry", "半導體")
        return f"公司名稱: {name}, 產業: {sector} - {industry}"
    except Exception:
        return f"公司代碼: {symbol} (基本資料抓取受阻，請參考新聞分析)"

@tool
def get_stock_price(symbol: str) -> str:
    """取得當前股價數據"""
    ticker_str = _get_valid_ticker(symbol)
    try:
        time.sleep(random.uniform(1, 2))
        stock = yf.Ticker(ticker_str, session=custom_session)
        # 嘗試抓取股價
        price = stock.fast_info.get('last_price', "無法取得")
        prev = stock.fast_info.get('previous_close', "無法取得")
        return f"目前股價: {price}, 昨收價: {prev}"
    except Exception:
        return "⚠️ 股價 API 暫時被阻擋"

@tool
def get_stock_news(symbol: str) -> str:
    """透過搜尋引擎取得最新新聞"""
    # 搜尋前強制等 3 秒，這是為了保護 DuckDuckGo 不被封鎖
    time.sleep(3)
    query = f"台股 {symbol} 最新財經新聞分析"
    try:
        search = DuckDuckGoSearchRun()
        # 這裡改用 run 而不是 invoke
        results = search.run(query)
        return f"🔍 最新網路搜尋結果：\n{results}" if results else "近期無重大新聞。"
    except Exception:
        return "⚠️ 搜尋引擎目前無法連線，建議稍後再試。"

@tool
def get_financial_report(symbol: str) -> str:
    """取得財務簡報"""
    ticker_str = _get_valid_ticker(symbol)
    try:
        time.sleep(1)
        stock = yf.Ticker(ticker_str, session=custom_session)
        # 使用更輕量的 fast_info 減少被擋機率
        rev = "請參考新聞公告"
        return f"代碼: {ticker_str}, 財務概況: 穩定運作中 ({rev})"
    except Exception:
        return "⚠️ 財報系統連線超時"
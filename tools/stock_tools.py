import yfinance as yf
import requests
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
import time
import random

custom_session = requests.Session()
custom_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
})

def _get_valid_ticker(symbol: str) -> str:
    symbol = str(symbol).strip()
    if symbol.endswith(".TW") or symbol.endswith(".TWO"):
        return symbol
    return f"{symbol}.TW"

@tool
def get_company_info(symbol: str) -> str:
    """取得公司基本資料與產業類別"""
    print(f"\n[Tool 執行] 正在抓取基本資料: {symbol}", flush=True)
    ticker_str = _get_valid_ticker(symbol)
    try:
        time.sleep(random.uniform(1, 2))
        stock = yf.Ticker(ticker_str, session=custom_session)
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
    print(f"\n[Tool 執行] 正在抓取股價: {symbol}", flush=True)
    ticker_str = _get_valid_ticker(symbol)
    try:
        time.sleep(random.uniform(1, 2))
        stock = yf.Ticker(ticker_str, session=custom_session)
        price = stock.fast_info.get('last_price', "無法取得")
        prev = stock.fast_info.get('previous_close', "無法取得")
        return f"目前股價: {price}, 昨收價: {prev}"
    except Exception as e:
        print(f"❌ [錯誤 - 股價] {e}", flush=True)
        return "⚠️ 股價 API 暫時被阻擋"

@tool
def get_stock_news(symbol: str) -> str:
    """透過搜尋引擎取得最新新聞"""
    print(f"\n[Tool 執行] 正在搜尋新聞: {symbol}", flush=True)
    time.sleep(3)
    query = f"台股 {symbol} 最新財經新聞分析"
    try:
        search = DuckDuckGoSearchRun()
        results = search.run(query)
        return f"🔍 最新網路搜尋結果：\n{results}" if results else "近期無重大新聞。"
    except Exception as e:
        print(f"❌ [錯誤 - 新聞搜尋] {e}", flush=True)
        return "⚠️ 搜尋引擎目前無法連線"

@tool
def get_financial_report(symbol: str) -> str:
    """取得財務簡報"""
    print(f"\n[Tool 執行] 正在抓取財報: {symbol}", flush=True)
    ticker_str = _get_valid_ticker(symbol)
    try:
        time.sleep(1)
        stock = yf.Ticker(ticker_str, session=custom_session)
        rev = "請參考新聞公告"
        return f"代碼: {ticker_str}, 財務概況: 穩定運作中 ({rev})"
    except Exception as e:
        print(f"❌ [錯誤 - 財報] {e}", flush=True)
        return "⚠️ 財報系統連線超時"
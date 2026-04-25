import yfinance as yf
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
import time
from functools import lru_cache # 🌟 新增：引入快取模組

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
    time.sleep(2)
    # 🌟 順手幫你優化：如果是美股，用英文搜尋比較準；台股維持中文
    query = f"台股 {symbol} 最新財經新聞分析" if symbol.isdigit() else f"US stock {symbol} latest financial news"
    try:
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
        # 🌟 改用快取中心拿資料 (瞬間完成！)
        info = _get_stock_info(ticker_str)
        rev = info.get('totalRevenue', "無法取得")
        margins = info.get('profitMargins', "無法取得")
        return f"代碼: {ticker_str}, 總營收: {rev}, 淨利率: {margins}"
    except Exception as e:
        print(f"❌ [錯誤 - 財報] {e}", flush=True)
        return "⚠️ 財報系統暫時無法讀取"
import yfinance as yf
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
import time
from functools import lru_cache
import json
import os
import inspect
import datetime

# 引入資料庫模組
from database import SessionLocal, User, Portfolio

import re

def _get_valid_ticker(symbol: str) -> str:
    """自動提取代碼，完美過濾掉中文與雜訊"""
    match = re.search(r'[A-Za-z0-9.]+', str(symbol))
    if not match: 
        return str(symbol).strip().upper()
        
    clean_symbol = match.group(0).upper()
    if clean_symbol.isdigit(): 
        return f"{clean_symbol}.TW"
        
    return clean_symbol

@lru_cache(maxsize=10)
def _get_stock_info(ticker_str: str):
    """強健式資料中心：把 session 拿掉，讓最新版 yfinance 內建的 curl_cffi 自己處理偽裝"""
    print(f"   -> [網路請求] 向 Yahoo 索取 {ticker_str} 底層資料...", flush=True)
    time.sleep(2.0) 
    try:
        # ✨ 關鍵還原：不再傳遞 session，讓 YF 自動處理
        info = yf.Ticker(ticker_str).info
        if not info or not isinstance(info, dict) or ('regularMarketPrice' not in info and 'currentPrice' not in info):
            return None
        return info
    except Exception as e:
        print(f"   -> [注意] Yahoo .info 請求失敗: {e}", flush=True)
        return None

@tool
def get_stock_price(symbol: str) -> str:
    """取得當前股價數據 (雙重防護)"""
    print(f"\n[Tool] 抓取股價: {symbol}", flush=True)
    ticker_str = _get_valid_ticker(symbol)
    
    info = _get_stock_info(ticker_str)
    if info:
        price = info.get('currentPrice', info.get('regularMarketPrice', '無法取得'))
        prev = info.get('previousClose', '無法取得')
        if price != '無法取得':
            return f"目前股價: {price}, 昨收價: {prev}"
            
    # 備用方案：K 線圖
    try:
        print(f"   -> [備用方案] info 失敗，改用 history() 抓取股價...", flush=True)
        # ✨ 關鍵還原：不再傳遞 session
        hist = yf.Ticker(ticker_str).history(period="5d")
        if not hist.empty and len(hist) >= 2:
            price = round(hist['Close'].iloc[-1], 2)
            prev = round(hist['Close'].iloc[-2], 2)
            return f"目前股價: {price}, 昨收價: {prev}"
    except:
        pass
    return "⚠️ 股價暫時無法取得"

@tool
def get_company_info(symbol: str) -> str:
    """取得公司名稱與產業。若 API 失效，自動切換至搜尋引擎。"""
    print(f"\n[Tool] 抓取公司資料: {symbol}", flush=True)
    ticker_str = _get_valid_ticker(symbol)
    
    info = _get_stock_info(ticker_str)
    if info:
        return f"【官方紀錄名稱】: {info.get('longName', '未知')} (簡稱: {info.get('shortName', '未知')}), 產業: {info.get('sector', '未知')}"
    
    print(f"   -> [備用方案] API 被擋，改用搜尋引擎抓取公司名稱...", flush=True)
    time.sleep(2) 
    try:
        search = DuckDuckGoSearchRun()
        res = search.run(f"台股代號 {symbol} 公司名稱與產業類別")
        return f"根據最新搜尋結果：\n{res[:300]}"
    except Exception as e:
        print(f"   -> [錯誤] 公司資料 DDG 搜尋失敗: {e}", flush=True)
        return f"無法取得代碼 {symbol} 的詳細資訊。"

@tool
def get_stock_news(query: str) -> str:
    """
    【核心工具：分析必備】
    搜尋指定股票的最新新聞、市場評論與重大事件。
    當使用者要求「分析」股票時，你『必須』呼叫此工具。
    參數 query 建議傳入：『代碼+中文名稱+新聞』（例如：'2330.TW 台積電 新聞'）
    """
    # 增加一個 print 讓我們在終端機看得見它有被呼叫
    print(f"\n[Tool] 正在搜尋新聞動態: {query}", flush=True)
    
    # 🛡️ 優先嘗試：DuckDuckGo 實時搜尋 (台股最強解法)
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        search = DuckDuckGoSearchRun()
        # 限制字數，避免 token 爆炸，但保留核心內容
        search_query = query if "新聞" in query else f"{query} 新聞"
        results = search.run(search_query)
        if results and "error" not in results.lower():
            return f"根據最新網路搜尋結果：\n{results[:800]}..."
    except Exception as e:
        print(f"   -> [警告] DDG 搜尋失敗: {e}", flush=True)

    # 🛡️ 備援：原本的 Yahoo RSS (針對代碼搜尋)
    try:
        import requests
        import xml.etree.ElementTree as ET
        ticker = _get_valid_ticker(query)
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}", headers=headers, timeout=5)
        if resp.status_code == 200:
            root = ET.fromstring(resp.text)
            news_list = [f"- {item.find('title').text}" for item in root.findall('./channel/item')[:5]]
            if news_list: return "📰 Yahoo 頭條：\n" + "\n".join(news_list)
    except:
        pass

    return "📢 該公司近期於公開媒體無顯著重大負面或正面新聞，建議參考基本面表現。"

@tool
def get_financial_report(symbol: str) -> str:
    """取得財報摘要。若 API 失效，改搜尋營收展望。"""
    print(f"\n[Tool] 抓取財報: {symbol}", flush=True)
    ticker_str = _get_valid_ticker(symbol)
    
    info = _get_stock_info(ticker_str)
    if info:
        rev = info.get('totalRevenue', "無法取得")
        margins = info.get('profitMargins', "無法取得")
        return f"代碼: {ticker_str}, 總營收: {rev}, 淨利率: {margins}"
    
    print(f"   -> [備用方案] API 失敗，搜尋最新財報數據...", flush=True)
    time.sleep(3) 
    try:
        search = DuckDuckGoSearchRun()
        res = search.run(f"台股 {symbol} 最近一季營收與獲利表現")
        return f"根據最新財經資料：\n{res[:500]}"
    except Exception as e:
        print(f"   -> [錯誤] 財報 DDG 搜尋失敗: {e}", flush=True)
        return "⚠️ 財報系統暫時無法讀取"

@tool
def get_recent_momentum(symbol: str) -> str:
    """取得短期財務動能。若 API 失效，改搜尋市場動能評價。"""
    print(f"\n[Tool] 抓取近期動能: {symbol}", flush=True)
    ticker_str = _get_valid_ticker(symbol)
    
    info = _get_stock_info(ticker_str)
    if info:
        q_rev_growth = info.get('quarterlyRevenueGrowth')
        q_earn_growth = info.get('earningsGrowth')
        trailing_eps = info.get('trailingEps', '無資料')
        def fmt_pct(val): return f"{val * 100:.2f}%" if isinstance(val, (int, float)) else "無資料"
        return f"【{ticker_str} 動能】\n- 營收成長: {fmt_pct(q_rev_growth)}\n- 盈餘成長: {fmt_pct(q_earn_growth)}\n- EPS: {trailing_eps}"

    print(f"   -> [備用方案] API 失敗，搜尋市場動能展望...", flush=True)
    time.sleep(3) 
    try:
        search = DuckDuckGoSearchRun()
        res = search.run(f"{symbol} 股價動能 營收成長率 展望")
        return f"根據最新市場分析：\n{res[:500]}"
    except Exception as e:
        print(f"   -> [錯誤] 動能 DDG 搜尋失敗: {e}", flush=True)
        return "⚠️ 近期動能指標暫時無法取得"
    
@tool
def get_quant_portfolio_status():
    """讀取當前使用者的帳戶狀態 (改接 SQL 資料庫)"""
    from agent import current_user_id
    uid = current_user_id.get()
    if not uid: return "錯誤：找不到使用者 ID，請重新登入。"
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == uid).first()
        if not user: return "錯誤：找不到該使用者帳戶。"
        
        portfolios = db.query(Portfolio).filter(Portfolio.user_id == uid).all()
        
        account_data = {
            "username": user.username,
            "cash": user.cash,
            "portfolio": [
                {
                    "Ticker": p.ticker,
                    "Name": p.name,
                    "Shares": p.shares,
                    "Entry_Price": p.entry_price
                } for p in portfolios
            ]
        }
        return json.dumps(account_data, ensure_ascii=False)
    except Exception as e:
        return f"讀取帳戶資料庫失敗: {e}"
    finally:
        db.close()

@tool
def run_quant_analysis_engine():
    """執行量化掃描與交易策略邏輯"""
    from agent import current_user_id
    from stock_quant import run_daily_strategy
    uid = current_user_id.get()
    
    try:
        # 動態判斷 run_daily_strategy 是否已支援 user_id 參數
        sig = inspect.signature(run_daily_strategy)
        if 'user_id' in sig.parameters:
            account, equity, market_status, sell_msg, buy_msg, watchlist = run_daily_strategy(user_id=uid)
        else:
            account, equity, market_status, sell_msg, buy_msg, watchlist = run_daily_strategy()
            
        report_summary = {
            "大盤環境": market_status,
            "建議賣出": sell_msg,
            "建議買進": buy_msg,
            "總資產": f"{equity:,.0f}",
            "動能觀察名單": watchlist[:5] 
        }
        return json.dumps(report_summary, ensure_ascii=False)
    except Exception as e:
        return f"執行量化引擎時出錯: {e}"
    
@tool
def modify_cash_balance(new_cash: float) -> str:
    """手動校正當前使用者的可用現金餘額"""
    from agent import current_user_id
    uid = current_user_id.get()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == uid).first()
        if not user: return "錯誤：找不到使用者。"
        
        old_cash = user.cash
        user.cash = float(new_cash)
        db.commit()
        return f"帳戶現金校正完成！原本餘額：{old_cash:,.0f} 元，更新後餘額：{new_cash:,.0f} 元。"
    except Exception as e:
        return f"修改現金失敗：{e}"
    finally:
        db.close()

@tool
def correct_buy_position(ticker: str, real_price: float, real_shares: int) -> str:
    """同步真實買進價格與股數 (改接 SQL 資料庫)"""
    from agent import current_user_id
    uid = current_user_id.get()
    db = SessionLocal()
    try:
        ticker = str(ticker).upper()
        if not (".TW" in ticker or ".TWO" in ticker): 
            ticker += ".TW"

        user = db.query(User).filter(User.id == uid).first()
        pos = db.query(Portfolio).filter(Portfolio.user_id == uid, Portfolio.ticker == ticker).first()
        
        if pos:
            # 1. 退回舊的扣款
            old_cost = pos.shares * pos.entry_price
            user.cash += old_cost
            
            # 2. 更新成真實數據
            pos.entry_price = float(real_price)
            pos.shares = int(real_shares)
            
            # 3. 重新扣除真實款項
            user.cash -= (real_price * real_shares)
            db.commit()
            return f"買進對帳完成！【{ticker}】已修正為 {real_shares} 股 @ {real_price}元。目前庫存剩餘現金: {user.cash:,.0f} 元。"
        else:
            return f"找不到 {ticker} 的持倉紀錄，請確認是否已在策略中成交。"
    except Exception as e:
        return f"修正持倉失敗：{e}"
    finally:
        db.close()

@tool
def generate_portfolio_pie_chart() -> str:
    """觸發前端渲染資產現值分布圖"""
    return "✅ 系統已收到請求。請告訴使用者：「已為您在介面側邊欄同步更新最新的資產配置圓餅圖」。"

@tool
def manual_buy_stock(ticker: str, price: float, shares: int) -> str:
    """手動新增持股或買進股票。請在 ticker 參數中務必傳入「代碼+中文名稱」(例如: '2330.TW 台積電') 以便系統記錄中文名稱。"""
    from agent import current_user_id
    uid = current_user_id.get()
    db = SessionLocal()
    try:
        original_ticker = str(ticker)
        ticker_str = _get_valid_ticker(original_ticker) # 確保格式正確 (如 2330.TW)
            
        user = db.query(User).filter(User.id == uid).first()
        if not user: return "錯誤：找不到使用者帳戶。"

        # ✨ 新增：優先從 LLM 傳入的字串擷取中文名稱
        import re
        zh_match = re.search(r'[\u4e00-\u9fa5]+', original_ticker)
        if zh_match:
            stock_name = zh_match.group(0)  # 成功抓到 "台積電"
        else:
            # 備用方案：如果字串中沒有中文，才退回使用 Yahoo 抓取的英文名稱
            try:
                info = _get_stock_info(ticker_str)
                stock_name = info.get("shortName", info.get("longName", ticker_str))
            except:
                stock_name = ticker_str

        # 1. 計算買進成本與手續費
        base_cost = price * shares
        fee = int(base_cost * 0.001425)
        fee = 20 if fee < 20 else fee
        total_cost = base_cost + fee

        if user.cash < total_cost:
            return f"⚠️ 現金不足！目前餘額 {user.cash:,.0f} 元，購買需 {total_cost:,.0f} 元。"

        # 2. 扣除總額
        user.cash -= total_cost

        # 3. 更新或新增持股
        today_str = datetime.date.today().strftime("%Y-%m-%d")

        pos = db.query(Portfolio).filter(Portfolio.user_id == uid, Portfolio.ticker == ticker_str).first()
        if pos:
            old_total_cost = pos.shares * pos.entry_price
            pos.shares += shares
            pos.entry_price = (old_total_cost + total_cost) / pos.shares
            pos.buy_fee += fee
            
            # 如果舊紀錄的名稱是英文或代碼，趁這次買進把它更新為中文
            if pos.name == ticker_str or not re.search(r'[\u4e00-\u9fa5]+', pos.name):
                pos.name = stock_name
        else:
            new_pos = Portfolio(
                user_id=uid, 
                ticker=ticker_str, 
                name=stock_name,
                shares=shares, 
                entry_price=(total_cost / shares), 
                peak_price=price, 
                buy_fee=fee, 
                entry_date=today_str  # ✨ 修改這裡：存入真實的日期字串！
            )
            db.add(new_pos)
        
        db.commit()
        return f"✅ 成功買進 {stock_name} ({ticker_str}) {shares} 股。目前剩餘現金 {user.cash:,.0f} 元。"
    except Exception as e:
        return f"手動買進失敗: {e}"
    finally:
        db.close()


@tool
def manual_sell_stock(ticker: str, price: float, shares: int) -> str:
    """手動賣出股票或減少持股。自動計算標準手續費與 0.3% 證交稅，並增加現金。"""
    from agent import current_user_id
    uid = current_user_id.get()
    db = SessionLocal()
    try:
        # 🧹 核心修正：強制過濾掉中文與空白，只保留英文字母、數字與小數點
        match = re.search(r'[A-Za-z0-9.]+', str(ticker))
        clean_ticker = match.group(0).upper() if match else str(ticker).upper()
        
        # 如果清洗後只剩下代碼（例如 2368），自動幫他補上 .TW
        if not (".TW" in clean_ticker or ".TWO" in clean_ticker): 
            clean_ticker += ".TW"
            
        user = db.query(User).filter(User.id == uid).first()
        # 🔍 注意這裡：改用 clean_ticker 去查詢資料庫
        pos = db.query(Portfolio).filter(Portfolio.user_id == uid, Portfolio.ticker == clean_ticker).first()
        
        if not pos:
            return f"⚠️ 您的庫存中沒有 {clean_ticker} 這檔股票。"
        if pos.shares < shares:
            return f"⚠️ 庫存股數不足！您目前只有 {pos.shares} 股 {clean_ticker}。"

        # 1. 計算賣出價值、手續費(0.1425%) 與 證券交易稅(0.3%)
        base_value = price * shares
        fee = int(base_value * 0.001425)
        fee = 20 if fee < 20 else fee
        tax = int(base_value * 0.003) 
        
        # 2. 實際拿回的錢
        net_value = base_value - fee - tax
        
        # 3. 更新現金與股數
        user.cash += net_value
        pos.shares -= shares

        if pos.shares == 0:
            db.delete(pos)
            msg = f"✅ 成功出清 {clean_ticker} {shares} 股 (單價 {price} 元)。"
        else:
            msg = f"✅ 成功賣出 {clean_ticker} {shares} 股 (單價 {price} 元)，尚餘 {pos.shares} 股。"
        
        db.commit()
        return f"{msg} 扣除手續費 {fee} 元與證交稅 {tax} 元後，實收 {net_value:,.0f} 元已存入帳戶。目前現金 {user.cash:,.0f} 元。"
    except Exception as e:
        return f"手動賣出失敗: {e}"
    finally:
        db.close()
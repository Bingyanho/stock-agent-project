import yfinance as yf
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
import time
from functools import lru_cache
import json
import os
import inspect

# 引入資料庫模組
from database import SessionLocal, User, Portfolio

def _get_valid_ticker(symbol: str) -> str:
    """自動判斷台股或美股代碼"""
    symbol = str(symbol).strip().upper() 
    if "." in symbol: return symbol
    if symbol.isdigit(): return f"{symbol}.TW"
    return symbol

@lru_cache(maxsize=10)
def _get_stock_info(ticker_str: str):
    print(f"   -> [網路請求] 向 Yahoo 索取 {ticker_str} 底層資料 (快取運作中)...", flush=True)
    time.sleep(1) 
    return yf.Ticker(ticker_str).info

@tool
def get_company_info(symbol: str) -> str:
    """取得公司正式名稱與產業類別"""
    print(f"\n[Tool] 抓取公司資料: {symbol}", flush=True)
    ticker_str = _get_valid_ticker(symbol)
    try:
        info = _get_stock_info(ticker_str)
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
    
    # 保留你原本的股票代號轉換邏輯
    ticker_str = _get_valid_ticker(symbol) 
    
    try:
        # ✨ 關鍵修改：直接呼叫 Ticker，什麼 session 都不用加，讓 yfinance 自動處理防護
        stock = yf.Ticker(ticker_str)
        info = stock.info
        
        price = info.get('currentPrice', info.get('regularMarketPrice', '無法取得'))
        prev = info.get('previousClose', '無法取得')
        
        # 終極備用方案：如果 Yahoo 把 info() 擋死，改用 history() 抓歷史 K 線的最新價
        if price == '無法取得' or prev == '無法取得':
            hist = stock.history(period="2d")
            if not hist.empty:
                price = round(hist['Close'].iloc[-1], 2)
                if len(hist) > 1:
                    prev = round(hist['Close'].iloc[-2], 2)
                    
        return f"目前股價: {price}, 昨收價: {prev}"
        
    except Exception as e:
        print(f"⚠️ {ticker_str} 股價抓取錯誤: {e}", flush=True) 
        return "⚠️ 股價暫時無法取得"

@tool
def get_stock_news(symbol: str) -> str:
    """透過搜尋引擎取得最新新聞"""
    print(f"\n[Tool] 搜尋新聞: {symbol}", flush=True)
    time.sleep(2) 
    query = f"台股 {symbol} 最新財經新聞分析" if symbol.isdigit() else f"US stock {symbol} latest financial news"
    
    try:
        search = DuckDuckGoSearchRun()
        results = search.run(query)
        if results:
            max_chars = 1000
            if len(results) > max_chars:
                results = results[:max_chars] + "\n...(為節省記憶體，已截斷後續新聞內容)"
            return f"🔍 搜尋結果：\n{results}"
        return "近期無重大新聞。"
    except Exception as e:
        return "⚠️ 新聞搜尋目前無法使用"

@tool
def get_financial_report(symbol: str) -> str:
    """取得財務簡報"""
    print(f"\n[Tool] 抓取財報: {symbol}", flush=True)
    ticker_str = _get_valid_ticker(symbol)
    try:
        info = _get_stock_info(ticker_str)
        rev = info.get('totalRevenue', "無法取得")
        margins = info.get('profitMargins', "無法取得")
        return f"代碼: {ticker_str}, 總營收: {rev}, 淨利率: {margins}"
    except Exception as e:
        return "⚠️ 財報系統暫時無法讀取"
    
@tool
def get_recent_momentum(symbol: str) -> str:
    """取得公司近期的短期財務動能"""
    print(f"\n[Tool] 抓取近期動能: {symbol}", flush=True)
    ticker_str = _get_valid_ticker(symbol)
    try:
        info = _get_stock_info(ticker_str)
        q_rev_growth = info.get('quarterlyRevenueGrowth')
        q_earn_growth = info.get('earningsGrowth')
        trailing_eps = info.get('trailingEps', '無法取得')

        def fmt_pct(val):
            return f"{val * 100:.2f}%" if isinstance(val, (int, float)) else "無資料"

        return (
            f"【{ticker_str} 短期財報動能】\n"
            f"- 季營收成長率 (YoY): {fmt_pct(q_rev_growth)}\n"
            f"- 季盈餘成長率 (YoY): {fmt_pct(q_earn_growth)}\n"
            f"- 近四季累積 EPS: {trailing_eps}"
        )
    except Exception as e:
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
        # 動態判斷 run_daily_strategy 是否已支援 user_id 參數 (為了向下相容)
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
        # 尋找該使用者擁有的這檔股票
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
    """
    觸發前端渲染資產現值分布圖。
    在多使用者雲端架構下，畫圖由 FastAPI 即時進行，此工具僅負責回傳確認訊號。
    """
    return "✅ 系統已收到請求。請告訴使用者：「已為您在介面側邊欄同步更新最新的資產配置圓餅圖」。"

@tool
def manual_buy_stock(ticker: str, price: float, shares: int) -> str:
    """手動新增持股或買進股票。會自動計算台灣股市標準手續費並扣除現金。"""
    from agent import current_user_id
    uid = current_user_id.get()
    db = SessionLocal()
    try:
        ticker = str(ticker).upper()
        if not (".TW" in ticker or ".TWO" in ticker): 
            ticker += ".TW"
            
        user = db.query(User).filter(User.id == uid).first()
        if not user: return "錯誤：找不到使用者帳戶。"

        # 1. 計算買進成本與手續費 (台股標準手續費 0.1425%，低消 20 元)
        base_cost = price * shares
        fee = int(base_cost * 0.001425)
        fee = 20 if fee < 20 else fee
        total_cost = base_cost + fee

        if user.cash < total_cost:
            return f"⚠️ 現金不足！目前餘額 {user.cash:,.0f} 元，購買含手續費需 {total_cost:,.0f} 元 (股款 {base_cost:,.0f} + 手續費 {fee})。"

        # 2. 扣除總額
        user.cash -= total_cost

        # 3. 檢查是否已有該檔持股
        pos = db.query(Portfolio).filter(Portfolio.user_id == uid, Portfolio.ticker == ticker).first()
        if pos:
            # 已有持股：將手續費攤入，重新計算平均成本價
            old_total_cost = pos.shares * pos.entry_price
            pos.shares += shares
            pos.entry_price = (old_total_cost + total_cost) / pos.shares
            pos.buy_fee += fee
        else:
            # 新增持股：將手續費攤入成本價，這樣才符合真實損益計算
            new_pos = Portfolio(
                user_id=uid, ticker=ticker, name=ticker, 
                shares=shares, entry_price=(total_cost / shares), peak_price=price, 
                buy_fee=fee, entry_date="手動建倉"
            )
            db.add(new_pos)
        
        db.commit()
        return f"✅ 成功買進 {ticker} {shares} 股 (單價 {price} 元)。加上手續費 {fee} 元，共扣款 {total_cost:,.0f} 元。目前剩餘現金 {user.cash:,.0f} 元。"
    except Exception as e:
        return f"手動買進失敗: {e}"
    finally:
        db.close()


@tool
def manual_sell_stock(ticker: str, price: float, shares: int) -> str:
    """手動賣出股票或減少持股。會自動計算標準手續費與證交稅，並增加現金。"""
    from agent import current_user_id
    uid = current_user_id.get()
    db = SessionLocal()
    try:
        ticker = str(ticker).upper()
        if not (".TW" in ticker or ".TWO" in ticker): 
            ticker += ".TW"
            
        user = db.query(User).filter(User.id == uid).first()
        pos = db.query(Portfolio).filter(Portfolio.user_id == uid, Portfolio.ticker == ticker).first()
        
        if not pos:
            return f"⚠️ 您的庫存中沒有 {ticker} 這檔股票。"
        if pos.shares < shares:
            return f"⚠️ 庫存股數不足！您目前只有 {pos.shares} 股 {ticker}。"

        # 1. 計算賣出價值、手續費(0.1425%) 與 證券交易稅(0.3%)
        base_value = price * shares
        fee = int(base_value * 0.001425)
        fee = 20 if fee < 20 else fee
        tax = int(base_value * 0.003)
        
        # 2. 實際拿回的錢 = 賣出總值 - 手續費 - 交易稅
        net_value = base_value - fee - tax
        
        # 3. 更新現金與股數
        user.cash += net_value
        pos.shares -= shares

        if pos.shares == 0:
            db.delete(pos)
            msg = f"✅ 成功出清 {ticker} {shares} 股 (單價 {price} 元)。"
        else:
            msg = f"✅ 成功賣出 {ticker} {shares} 股 (單價 {price} 元)，尚餘 {pos.shares} 股。"
        
        db.commit()
        return f"{msg} 扣除手續費 {fee} 元與證交稅 {tax} 元後，實收 {net_value:,.0f} 元已存入帳戶。目前現金 {user.cash:,.0f} 元。"
    except Exception as e:
        return f"手動賣出失敗: {e}"
    finally:
        db.close()
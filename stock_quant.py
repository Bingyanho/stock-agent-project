import yfinance as yf
import pandas as pd
import os
from datetime import datetime
import warnings
from dotenv import load_dotenv

# 匯入資料庫模組
from database import SessionLocal, User, Portfolio

load_dotenv()
warnings.filterwarnings('ignore')

# ==========================================
# 1. 系統與檔案設定
# ==========================================
WATCHLIST_FILE = "watchlist.txt"

INITIAL_CAPITAL = 200000
MAX_POSITIONS = 5
MIN_BUDGET_THRESHOLD = 10000 # 單檔最低購買金額門檻 
BENCHMARK = "0050.TW"

# 策略參數
MOMENTUM_DAYS = 10
EXIT_BUFFER = 0.99           # 趨勢破壞緩衝
STOP_LOSS_BUFFER = 0.92      # 硬性停損 (跌幅 8%)
TRAILING_STOP_BUFFER = 0.90  # 移動停利 (高點回落 10%)
MIN_HOLD_DAYS = 7
TARGET_WATCHLIST_SIZE = 20
MIN_MOMENTUM_THRESHOLD = 0.05

# --- 交易成本設定 ---
FEE_RATE = 0.001425
FEE_DISCOUNT = 0.6
TAX_RATE = 0.003
MIN_FEE = 20

# --- 股票中文名稱字典 ---
STOCK_NAMES = {
    "2330.TW": "台積電", "2317.TW": "鴻海", "2454.TW": "聯發科", "2308.TW": "台達電", "2382.TW": "廣達",
    "2881.TW": "富邦金", "2882.TW": "國泰金", "2412.TW": "中華電", "1216.TW": "統一", "2002.TW": "中鋼",
    "2303.TW": "聯電", "3231.TW": "緯創", "3008.TW": "大立光", "2603.TW": "長榮", "2324.TW": "仁寶",
    "3034.TW": "聯詠", "3481.TW": "群創", "2409.TW": "友達", "1101.TW": "台泥", "1102.TW": "亞泥",
    "1301.TW": "台塑", "1303.TW": "南亞", "2886.TW": "兆豐金", "2891.TW": "中信金", "2892.TW": "第一金",
    "2357.TW": "華碩", "2379.TW": "瑞昱", "3293.TWO": "鈊象", "8299.TWO": "群聯", "2376.TW": "技嘉",
    "3661.TW": "世芯-KY", "1504.TW": "東元", "1519.TW": "華城", "1605.TW": "大亞", "2609.TW": "陽明",
    "2615.TW": "萬海", "3017.TW": "奇鋐", "3037.TW": "欣興", "2395.TW": "研華", "3529.TWO": "力旺",
    "2368.TW": "金像電", "6669.TW": "緯穎", "2383.TW": "台光電", "3044.TW": "健鼎",
    "5347.TWO": "世界", "5483.TWO": "中美晶", "6274.TWO": "台燿"
}

SCAN_UNIVERSE = list(STOCK_NAMES.keys())

def get_name(ticker):
    return STOCK_NAMES.get(ticker, ticker)

# ==========================================
# 2. 動態名單管理
# ==========================================
def update_dynamic_watchlist():
    print(f"啟動全市場掃描：正在分析 {len(SCAN_UNIVERSE)} 檔潛力股...")
    raw = yf.download(SCAN_UNIVERSE, period="4mo", auto_adjust=True, progress=False)

    if raw.empty or "Close" not in raw:
        raise RuntimeError("無法取得掃描池資料，請檢查網路或 yfinance 資料源。")

    close_df = raw["Close"].ffill().dropna(how="all")
    candidates = []

    for t in SCAN_UNIVERSE:
        if t not in close_df.columns: continue
        c = close_df[t].dropna()
        if len(c) < 60: continue

        last_close = float(c.iloc[-1])
        ma20 = float(c.rolling(20).mean().iloc[-1])
        ma60 = float(c.rolling(60).mean().iloc[-1])
        momentum = float(c.pct_change(MOMENTUM_DAYS).iloc[-1])

        if pd.isna(ma20) or pd.isna(ma60) or pd.isna(momentum): continue

        if last_close > ma20 and ma20 > ma60 and momentum > 0:
            candidates.append({"Ticker": t, "Momentum": momentum})

    candidates.sort(key=lambda x: x["Momentum"], reverse=True)
    top_stocks = [c["Ticker"] for c in candidates[:TARGET_WATCHLIST_SIZE]]

    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        f.write(f"# 機器人自動掃描更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("\n".join(top_stocks))

    return top_stocks

# ==========================================
# 3. 數據引擎與指標計算
# ==========================================
def get_market_signals(tickers):
    all_tickers = list(dict.fromkeys(tickers + [BENCHMARK]))
    raw = yf.download(all_tickers, period="2y", auto_adjust=True, progress=False)
    
    if raw.empty or "Close" not in raw:
        raise RuntimeError("無法取得市場資料。")

    close_df = raw["Close"].ffill().dropna(how="all")
    signals = {}
    market_ok = False
    market_status = "🔴 大盤資料不足，暫停交易"

    if BENCHMARK in close_df.columns:
        bench_close = close_df[BENCHMARK].dropna()
        if len(bench_close) >= 200:
            bench_ma200 = bench_close.rolling(200).mean()
            if not pd.isna(bench_ma200.iloc[-1]):
                market_ok = float(bench_close.iloc[-1]) > float(bench_ma200.iloc[-1])
                market_status = "🟢 多頭 (大盤 > 年線)" if market_ok else "🔴 空頭 (大盤 < 年線，強制空手)"

    for t in tickers:
        if t not in close_df.columns: continue
        c = close_df[t].dropna()
        if len(c) < 60: continue

        signals[t] = {
            "Close": float(c.iloc[-1]),
            "MA5": float(c.rolling(5).mean().iloc[-1]),
            "MA20": float(c.rolling(20).mean().iloc[-1]),
            "MA60": float(c.rolling(60).mean().iloc[-1]),
            "Momentum": float(c.pct_change(MOMENTUM_DAYS).iloc[-1])
        }

    return market_ok, market_status, signals

# ==========================================
# 4. 核心交易邏輯 (接入 SQLite)
# ==========================================
def run_daily_strategy(user_id: int = 1):
    """
    量化策略核心，接收 user_id 對特定使用者的資料庫進行買賣操作
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"找不到 ID 為 {user_id} 的使用者")

        cash = user.cash
        # 從資料庫抓出該名使用者的所有持股
        portfolios = db.query(Portfolio).filter(Portfolio.user_id == user_id).all()

        watchlist = update_dynamic_watchlist()
        market_ok, market_status, signals = get_market_signals(watchlist)
        
        sell_msg, buy_msg = "", ""
        today = datetime.today()
        today_str = today.strftime("%Y-%m-%d")

        # --- [階段 A] 賣出邏輯 ---
        for pos in portfolios:
            t = pos.ticker
            if t not in signals: continue

            price = signals[t]["Close"]
            m5 = signals[t]["MA5"]
            m20 = signals[t]["MA20"]
            
            entry_price = pos.entry_price
            peak_price = max(pos.peak_price if pos.peak_price else entry_price, price)
            
            # 若無 entry_date，預設當天買的以防止報錯
            entry_date = datetime.strptime(pos.entry_date, "%Y-%m-%d") if pos.entry_date else today
            held_days = abs((today - entry_date).days)

            market_exit = (not market_ok) and (price < m20)
            hard_stop = (price < entry_price * STOP_LOSS_BUFFER)
            trailing_stop = (price < peak_price * TRAILING_STOP_BUFFER)
            trend_exit = (price < m20 * EXIT_BUFFER) and (held_days >= MIN_HOLD_DAYS)
            momentum_decay = (price < m5) and (price < entry_price * 1.05) and (held_days >= MIN_HOLD_DAYS)

            if market_exit or trend_exit or hard_stop or trailing_stop or momentum_decay:
                gross_value = pos.shares * price
                sell_fee = max(MIN_FEE, int(gross_value * FEE_RATE * FEE_DISCOUNT))
                sell_tax = int(gross_value * TAX_RATE)
                net_value = gross_value - sell_fee - sell_tax
                
                cash += net_value # 現金變多
                
                cost_basis = (entry_price * pos.shares) + (pos.buy_fee or 0)
                profit_pct = ((net_value - cost_basis) / cost_basis) * 100 if cost_basis > 0 else 0

                if market_exit: reason = "🔴 大盤轉空強制清倉"
                elif hard_stop: reason = "🛑 觸發硬性停損"
                elif trailing_stop: reason = "📉 觸發移動停利"
                elif momentum_decay: reason = "⏳ 動能衰退"
                else: reason = "⚠️ 趨勢破壞"

                sell_msg += f"{reason} 【{get_name(t)} ({t})】: 賣出 {pos.shares} 股 | 報酬: {profit_pct:.2f}%\n"
                
                # 從資料庫中刪除這筆持股
                db.delete(pos)
            else:
                # 沒賣出，更新資料庫的歷史最高價
                pos.peak_price = round(peak_price, 2)

        # 提交賣出結果到資料庫，騰出空位
        db.commit()

        # --- [階段 B] 買進邏輯 ---
        # 重新查詢目前持股數
        current_portfolios = db.query(Portfolio).filter(Portfolio.user_id == user_id).all()
        empty_slots = MAX_POSITIONS - len(current_portfolios)

        if market_ok and empty_slots > 0:
            budget_per_stock = cash / empty_slots

            if budget_per_stock >= MIN_BUDGET_THRESHOLD:
                held_tickers = [p.ticker for p in current_portfolios]
                candidates = []

                for t, s in signals.items():
                    if t in held_tickers: continue
                    if s["Close"] > s["MA20"] > s["MA60"] and s["Momentum"] > MIN_MOMENTUM_THRESHOLD:
                        candidates.append({"Ticker": t, "Price": s["Close"], "Momentum": s["Momentum"]})

                candidates.sort(key=lambda x: x["Momentum"], reverse=True)

                for b in candidates[:empty_slots]:
                    if empty_slots <= 0: break
                        
                    price = b["Price"]
                    shares = int((budget_per_stock * 0.998) // price)
                    
                    while shares > 0:
                        gross_cost = shares * price
                        buy_fee = max(MIN_FEE, int(gross_cost * FEE_RATE * FEE_DISCOUNT))
                        total_cost = gross_cost + buy_fee
                        if cash >= total_cost: break
                        shares -= 1

                    if shares < 1: continue

                    gross_cost = shares * price
                    buy_fee = max(MIN_FEE, int(gross_cost * FEE_RATE * FEE_DISCOUNT))
                    total_cost = gross_cost + buy_fee

                    cash -= total_cost
                    empty_slots -= 1
                    
                    # 建立新持股並加入資料庫
                    new_pos = Portfolio(
                        user_id=user_id,
                        ticker=b["Ticker"],
                        name=get_name(b["Ticker"]),
                        shares=shares,
                        entry_price=round(price, 2),
                        peak_price=round(price, 2),
                        buy_fee=buy_fee,
                        entry_date=today_str
                    )
                    db.add(new_pos)
                    
                    buy_msg += f"🎯 強勢買進 【{get_name(b['Ticker'])} ({b['Ticker']})】: 買進 {shares} 股 | 參考價: {price:.2f}\n"
            else:
                buy_msg += f"⚠️ 預算不足單檔門檻 ({MIN_BUDGET_THRESHOLD} 元)，暫緩買進。\n"

        if not sell_msg: sell_msg = "✅ 目前無賣出訊號，安心抱牢。"
        if not buy_msg: buy_msg = "⚠️ 今日無符合條件個股，或已滿倉/大盤弱。"

        # 結算與更新現金
        user.cash = cash
        db.commit()

        # 重新計算最終總資產
        final_portfolios = db.query(Portfolio).filter(Portfolio.user_id == user_id).all()
        stock_value = 0
        for p in final_portfolios:
            if p.ticker in signals:
                price = signals[p.ticker]["Close"]
                gross_val = p.shares * price
                est_sell_fee = max(MIN_FEE, int(gross_val * FEE_RATE * FEE_DISCOUNT))
                est_sell_tax = int(gross_val * TAX_RATE)
                stock_value += (gross_val - est_sell_fee - est_sell_tax)
                
        current_equity = cash + stock_value

        return None, current_equity, market_status, sell_msg, buy_msg, watchlist

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

# 終端機測試專用
if __name__ == "__main__":
    print("啟動量化策略 (測試模式 User ID: 1)")
    _, eq, ms, sm, bm, wl = run_daily_strategy(user_id=1)
    print("\n--- 執行結果 ---")
    print(f"總資產: {eq:,.0f}")
    print(f"大盤狀態: {ms}")
    print(f"賣出訊息:\n{sm}")
    print(f"買進訊息:\n{bm}")
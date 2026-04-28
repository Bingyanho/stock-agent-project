import yfinance as yf
import pandas as pd
import requests
import json
import os
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings('ignore')

# ==========================================
# 1. 系統與檔案設定
# ==========================================
# 🚨 請換成你全新的 webhook，絕對不要再公開貼出！
DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/1494712760561307701/im0h8bYIvarQn9UEgTqMAAVx0HfAdx0__ydmCAsHXjTp5GNhZoUEXViVUd7aaJQywMpt'

DB_FILE = "trading_account.json"
WATCHLIST_FILE = "watchlist.txt"

INITIAL_CAPITAL = 200000
MAX_POSITIONS = 5
MIN_BUDGET_THRESHOLD = 10000 # 【新增】：單檔最低購買金額門檻 (低於1萬不買，避免手續費不划算)
BENCHMARK = "0050.TW"

# 策略參數
MOMENTUM_DAYS = 10
EXIT_BUFFER = 0.99           # 趨勢破壞緩衝
STOP_LOSS_BUFFER = 0.92      # 硬性停損 (跌幅 8%)
TRAILING_STOP_BUFFER = 0.90  # 移動停利 (高點回落 10%)
MIN_HOLD_DAYS = 7
COOLDOWN_DAYS = 3
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
# 2. 動態名單與資料庫管理
# ==========================================
def update_dynamic_watchlist():
    print(f"啟動全市場掃描：正在分析 {len(SCAN_UNIVERSE)} 檔潛力股...")

    raw = yf.download(SCAN_UNIVERSE, period="4mo", auto_adjust=True, progress=False)

    if raw.empty or "Close" not in raw:
        raise RuntimeError("無法取得掃描池資料，請檢查網路或 yfinance 資料源。")

    close_df = raw["Close"].ffill().dropna(how="all")

    candidates = []
    for t in SCAN_UNIVERSE:
        if t not in close_df.columns:
            continue

        c = close_df[t].dropna()
        if len(c) < 60:
            continue

        last_close = float(c.iloc[-1])
        ma20 = float(c.rolling(20).mean().iloc[-1])
        ma60 = float(c.rolling(60).mean().iloc[-1])
        momentum = float(c.pct_change(MOMENTUM_DAYS).iloc[-1])

        if pd.isna(ma20) or pd.isna(ma60) or pd.isna(momentum):
            continue

        if last_close > ma20 and ma20 > ma60 and momentum > 0:
            candidates.append({"Ticker": t, "Momentum": momentum})

    candidates.sort(key=lambda x: x["Momentum"], reverse=True)
    top_stocks = [c["Ticker"] for c in candidates[:TARGET_WATCHLIST_SIZE]]

    with open(WATCHLIST_FILE, "w", encoding="utf-8") as f:
        f.write(f"# 機器人自動掃描更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("# 選股邏輯: 收盤 > 20MA > 60MA，依 10 日動能排序前 20 名\n")
        f.write("\n".join(top_stocks))

    print(f"掃描完成！已將目前最強的 {len(top_stocks)} 檔股票更新至 {WATCHLIST_FILE}")
    return top_stocks

def load_account():
    if not os.path.exists(DB_FILE):
        return {"cash": INITIAL_CAPITAL, "portfolio": [], "cooldowns": {}}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        account = json.load(f)
        if "cooldowns" not in account:
            account["cooldowns"] = {}
        return account

def save_account(account_data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(account_data, f, indent=4, ensure_ascii=False)

# ==========================================
# 3. 數據引擎與指標計算
# ==========================================
def get_market_signals(tickers):
    print("正在下載觀察名單與大盤數據...")
    all_tickers = list(dict.fromkeys(tickers + [BENCHMARK]))

    raw = yf.download(all_tickers, period="2y", auto_adjust=True, progress=False)
    if raw.empty or "Close" not in raw:
        raise RuntimeError("無法取得市場資料，請檢查網路或 yfinance 資料源。")

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
        else:
            market_status = "🔴 大盤資料不足 200 日，暫停交易"

    for t in tickers:
        if t not in close_df.columns:
            continue

        c = close_df[t].dropna()
        if len(c) < 60:
            continue

        ma5 = c.rolling(5).mean().iloc[-1]
        ma20 = c.rolling(20).mean().iloc[-1]
        ma60 = c.rolling(60).mean().iloc[-1]
        momentum = c.pct_change(MOMENTUM_DAYS).iloc[-1]

        if pd.isna(ma20) or pd.isna(ma60) or pd.isna(momentum):
            continue

        signals[t] = {
            "Close": float(c.iloc[-1]),
            "MA5": float(ma5),
            "MA20": float(ma20),
            "MA60": float(ma60),
            "Momentum": float(momentum)
        }

    return market_ok, market_status, signals

# ==========================================
# 4. 核心交易邏輯
# ==========================================
def run_daily_strategy():
    watchlist = update_dynamic_watchlist()
    account = load_account()

    cash = account["cash"]
    portfolio = account["portfolio"]
    cooldowns = account["cooldowns"]

    today = datetime.today()
    today_str = today.strftime("%Y-%m-%d")

    market_ok, market_status, signals = get_market_signals(watchlist)
    sell_msg, buy_msg = "", ""

    # 清理過期冷卻名單
    cooldowns = {
        t: date for t, date in cooldowns.items()
        if datetime.strptime(date, "%Y-%m-%d") + timedelta(days=COOLDOWN_DAYS) > today
    }

    # --- [階段 A] 賣出邏輯 ---
    new_portfolio = []
    for pos in portfolio:
        t = pos["Ticker"]
        if t not in signals:
            new_portfolio.append(pos)
            continue

        price = signals[t]["Close"]
        m5 = signals[t]["MA5"]
        m20 = signals[t]["MA20"]
        
        entry_price = pos["Entry_Price"]
        peak_price = max(pos.get("Peak_Price", entry_price), price)
        pos["Peak_Price"] = round(peak_price, 2)
        
        held_days = abs((today - datetime.strptime(pos["Entry_Date"], "%Y-%m-%d")).days)

        # 保命條款 (無視持有天數，隨時觸發)
        market_exit = (not market_ok) and (price < m20)
        hard_stop = (price < entry_price * STOP_LOSS_BUFFER)
        trailing_stop = (price < peak_price * TRAILING_STOP_BUFFER)

        # 趨勢條款 (加上 held_days >= MIN_HOLD_DAYS 的限制，給予 5 天保護)
        trend_exit = (price < m20 * EXIT_BUFFER) and (held_days >= MIN_HOLD_DAYS)
        momentum_decay = (price < m5) and (price < entry_price * 1.05) and (held_days >= MIN_HOLD_DAYS)

        if market_exit or trend_exit or hard_stop or trailing_stop or momentum_decay:
            gross_value = pos["Shares"] * price
            sell_fee = max(MIN_FEE, int(gross_value * FEE_RATE * FEE_DISCOUNT))
            sell_tax = int(gross_value * TAX_RATE)
            net_value = gross_value - sell_fee - sell_tax
            cash += net_value

            cost_basis = (entry_price * pos["Shares"]) + pos.get("Buy_Fee", 0)
            profit_pct = ((net_value - cost_basis) / cost_basis) * 100 if cost_basis > 0 else 0

            if market_exit:
                reason = "🔴 大盤轉空強制清倉"
            elif hard_stop:
                reason = "🛑 觸發硬性停損 (跌破買價 8%)"
            elif trailing_stop:
                reason = "📉 觸發移動停利 (高點回落 10%)"
            elif momentum_decay:
                reason = "⏳ 動能衰退 (跌破5MA且獲利未拉開)"
            else:
                reason = "⚠️ 趨勢破壞 (跌破 20MA)"

            sell_msg += (
                f"{reason} 【{get_name(t)} ({t})】: 預計賣出 {pos['Shares']} 股 | "
                f"參考價: {price:.2f} | 預估報酬: {profit_pct:.2f}%\n"
            )

            cooldowns[t] = today_str
        else:
            new_portfolio.append(pos)

    portfolio = new_portfolio

    # --- [階段 B] 買進邏輯 (全新：依照空位平分現金) ---
    empty_slots = MAX_POSITIONS - len(portfolio)

    if market_ok and empty_slots > 0:
        budget_per_stock = cash / empty_slots

        # 檢查平分後的預算是否有達到最低消費門檻
        if budget_per_stock >= MIN_BUDGET_THRESHOLD:
            held_tickers = [p["Ticker"] for p in portfolio]
            candidates = []

            # 篩選符合條件的候選股
            for t, s in signals.items():
                if t in held_tickers or t in cooldowns:
                    continue
                if s["Close"] > s["MA20"] and s["MA20"] > s["MA60"] and s["Momentum"] > MIN_MOMENTUM_THRESHOLD:
                    candidates.append({
                        "Ticker": t,
                        "Price": s["Close"],
                        "Momentum": s["Momentum"]
                    })

            # 依照動能排序，優先買最強的
            candidates.sort(key=lambda x: x["Momentum"], reverse=True)

            for b in candidates[:empty_slots]:
                if empty_slots <= 0:
                    break
                    
                price = b["Price"]
                # 粗估可買股數 (預留 0.2% 作為手續費緩衝)
                shares = int((budget_per_stock * 0.998) // price)
                
                # 防呆機制：如果加了手續費超過現金，就減少 1 股直到夠買
                while shares > 0:
                    gross_cost = shares * price
                    buy_fee = max(MIN_FEE, int(gross_cost * FEE_RATE * FEE_DISCOUNT))
                    total_cost = gross_cost + buy_fee
                    if cash >= total_cost:
                        break
                    shares -= 1

                if shares < 1:
                    continue

                # 確定購買數量後，進行現金扣款與更新持股
                gross_cost = shares * price
                buy_fee = max(MIN_FEE, int(gross_cost * FEE_RATE * FEE_DISCOUNT))
                total_cost = gross_cost + buy_fee

                cash -= total_cost
                empty_slots -= 1
                portfolio.append({
                    "Ticker": b["Ticker"],
                    "Name": get_name(b["Ticker"]),
                    "Shares": shares,
                    "Entry_Price": round(price, 2),
                    "Peak_Price": round(price, 2),
                    "Buy_Fee": buy_fee,
                    "Entry_Date": today_str
                })
                buy_msg += (
                    f"🎯 強勢買進 【{get_name(b['Ticker'])} ({b['Ticker']})】: "
                    f"預計買進 {shares} 股 | 參考價: {price:.2f} | "
                    f"動能: {b['Momentum']*100:.1f}%\n"
                )
        else:
            # 錢太少，觸發省手續費機制
            buy_msg += f"⚠️ 剩餘資金 {cash:,.0f} 元，分攤給 {empty_slots} 個空位後單檔預算為 {budget_per_stock:,.0f} 元，不及最低門檻 ({MIN_BUDGET_THRESHOLD} 元)，為節省手續費暫緩買進。\n"

    # --- 整理推播訊息與資產總結 ---
    if not sell_msg:
        sell_msg = "✅ 目前無賣出訊號，安心抱牢。"
    if not buy_msg:
        buy_msg = "⚠️ 今日無符合條件個股，或已達滿倉/大盤轉弱。"

    # 重新計算總資產 (今日最終結算：以預估清算價值計算)
    stock_value = 0
    for p in portfolio:
        if p["Ticker"] in signals:
            price = signals[p["Ticker"]]["Close"]
            gross_val = p["Shares"] * price
            est_sell_fee = max(MIN_FEE, int(gross_val * FEE_RATE * FEE_DISCOUNT))
            est_sell_tax = int(gross_val * TAX_RATE)
            stock_value += (gross_val - est_sell_fee - est_sell_tax)
            
    current_equity = cash + stock_value

    account.update({
        "cash": cash,
        "portfolio": portfolio,
        "cooldowns": cooldowns
    })
    save_account(account)

    return account, current_equity, market_status, sell_msg, buy_msg, watchlist

# ==========================================
# 5. Discord 推播
# ==========================================
def send_discord_msg(account, current_equity, market_status, sell_msg, buy_msg, watchlist):
    portfolio = account["portfolio"]
    cash = account["cash"]

    if portfolio:
        display_portfolio = [{k: v for k, v in p.items() if k != "Buy_Fee"} for p in portfolio]
        df = pd.DataFrame(display_portfolio)
        table_text = df.to_string(index=False)
        if len(table_text) > 1000:
            table_text = table_text[:1000] + "\n...（已截斷）"
        table_str = f"```text\n{table_text}\n```"
    else:
        table_str = "```text\n目前空手，資金安全避險中。\n```"

    wl_str = ", ".join([t.replace(".TW", "").replace(".TWO", "") for t in watchlist])
    if len(wl_str) > 1000:
        wl_str = wl_str[:1000] + "..."

    return_rate = ((current_equity - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    color = 65280 if return_rate >= 0 else 16711680

    embed = {
        "title": "📈 量化分析：實戰操盤指令",
        "description": (
            f"**今日大盤環境：** {market_status}\n"
            f"請依照以下訊號，於 **09:00 開盤時** 執行動作。"
        ),
        "color": color,
        "fields": [
            {
                "name": "📤 今日賣出指令",
                "value": sell_msg[:1024],
                "inline": False
            },
            {
                "name": "📥 今日買進指令",
                "value": buy_msg[:1024],
                "inline": False
            },
            {
                "name": "📊 目前持股",
                "value": table_str[:1024],
                "inline": False
            },
            {
                "name": "🔎 今日 AI 動能雷達",
                "value": wl_str[:1024] if wl_str else "今日無符合條件股票（市場極弱）",
                "inline": False
            },
            {
                "name": "💰 帳戶摘要",
                "value": (
                    f"現金：{cash:,.0f}\n"
                    f"總資產：{current_equity:,.0f}\n"
                    f"報酬率：{return_rate:.2f}%\n"
                    f"持股數：{len(portfolio)}"
                ),
                "inline": False
            }
        ],
        "footer": {
            "text": f"更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        }
    }

    payload = {"embeds": [embed]}

    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
        resp.raise_for_status()
        print("Discord 訊息已送出")
    except Exception as e:
        print(f"Discord 發送失敗：{e}")

# ==========================================
# 6. 主程式入口
# ==========================================
if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL or "YOUR_WEBHOOK_URL_HERE" in DISCORD_WEBHOOK_URL:
        print("❌ 請先填入 Discord Webhook URL")
    else:
        try:
            account, current_equity, market_status, sell_msg, buy_msg, watchlist = run_daily_strategy()
            send_discord_msg(account, current_equity, market_status, sell_msg, buy_msg, watchlist)
            print("今日策略執行完成")
        except Exception as e:
            print(f"程式錯誤：{e}")
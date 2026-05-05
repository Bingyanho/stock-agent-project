"""
智能財報分析 Agent API (多使用者資料庫版)
"""
import io
import os
from datetime import datetime, timedelta
from typing import Optional

# 第三方套件
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.patheffects as path_effects
import jwt
from fastapi import FastAPI, HTTPException, Depends, Query, status
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from passlib.context import CryptContext
import yfinance as yf

# 專案模組
from agent import StockAnalysisSession, current_user_id
from database import SessionLocal, User, Portfolio, engine, Base

# 啟動時自動建立 SQLite 資料表
Base.metadata.create_all(bind=engine)

app = FastAPI(title="阿財理專 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "your_super_secret_key_here"
ALGORITHM = "HS256"

sessions: dict[str, StockAnalysisSession] = {}

# ==========================================
# 1. 帳號註冊與登入 API
# ==========================================
class AuthRequest(BaseModel):
    username: str
    password: str

@app.post("/register")
def register(req: AuthRequest):
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == req.username).first():
            raise HTTPException(status_code=400, detail="帳號已被註冊")
        hashed_pw = pwd_context.hash(req.password)
        new_user = User(username=req.username, password_hash=hashed_pw)
        db.add(new_user)
        db.commit()
        return {"message": "註冊成功！"}
    finally:
        db.close()

@app.post("/login")
def login(req: AuthRequest):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == req.username).first()
        if not user or not pwd_context.verify(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="帳號或密碼錯誤！")
        
        token = jwt.encode(
            {"sub": user.username, "user_id": user.id, "exp": datetime.utcnow() + timedelta(hours=24)},
            SECRET_KEY,
            algorithm=ALGORITHM
        )
        return {"access_token": token, "token_type": "bearer", "user_id": user.id}
    finally:
        db.close()

# ==========================================
# 2. Agent 聊天與分析 API
# ==========================================
class AnalyzeRequest(BaseModel):
    session_id: str
    message: str
    token: str # 從前端接收 Token

class AnalyzeResponse(BaseModel):
    session_id: str
    output: str
    tool_calls_count: int

@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    # 解析 Token 取得 user_id
    try:
        payload = jwt.decode(req.token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
    except Exception:
        raise HTTPException(status_code=401, detail="無效的 Token")

    # 將 user_id 設定到背景變數，供 stock_tools.py 取用
    token_set = current_user_id.set(user_id)
    
    try:
        if req.session_id not in sessions:
            sessions[req.session_id] = StockAnalysisSession()

        session = sessions[req.session_id]
        result = session.analyze(req.message)
        
        return AnalyzeResponse(
            session_id=req.session_id,
            output=result["output"],
            tool_calls_count=result["steps"]
        )
    except Exception as e:
        print(f"Agent 分析執行錯誤: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        current_user_id.reset(token_set)

# ==========================================
# 3. 獲取圖表 API (直接讀取 SQL 資料庫動態畫圖)
# ==========================================
@app.get("/portfolio/pie-chart")
def get_portfolio_pie_chart(token: str = Query(...)):
    db = SessionLocal()
    try:
        # 1. 驗證 Token (確認是合法使用者)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # 從資料庫讀取該使用者的現金與持股
        user = db.query(User).filter(User.id == user_id).first()
        portfolios = db.query(Portfolio).filter(Portfolio.user_id == user_id).all()
        
        # 準備畫圖資料
        labels = [p.name for p in portfolios]
        sizes = []

        # ✨ 統一估值邏輯：嘗試抓取即時股價，若失敗則使用成本價
        for p in portfolios:
            current_price = 0
            try:
                # 抓取最新股價 (這段邏輯必須跟你 check_portfolio 裡的一模一樣)
                ticker_data = yf.Ticker(p.ticker)
                current_price = ticker_data.fast_info['last_price']
            except Exception as e:
                print(f"⚠️ 無法抓取 {p.ticker} 即時股價，改用成本價。原因: {e}")
            
            # 🛡️ 防呆：如果股價抓不到或是 0，退回使用 entry_price (成本價)
            if not current_price or current_price == 0:
                current_price = p.entry_price
                
            # 計算該檔股票的當前市值
            sizes.append(p.shares * current_price)
        
        if user and user.cash > 0:
            labels.append("現金")
            sizes.append(user.cash)

        # 2. ✨ 關鍵修改：動態載入雲端的中文字體檔
        font_path = "NotoSansTC-Regular.ttf"
        if os.path.exists(font_path):
            fm.fontManager.addfont(font_path)
            prop = fm.FontProperties(fname=font_path)
            plt.rcParams['font.family'] = prop.get_name() # 強制使用我們指定的字體
        else:
            print("⚠️ 找不到 NotoSansTC-Regular.ttf，請確認檔案是否有上傳！")
            plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'PingFang HK', 'SimHei', 'Arial Unicode MS']
            
        plt.rcParams['axes.unicode_minus'] = False
        
        # 3. 開始繪圖設定
        fig, ax = plt.subplots(figsize=(10, 8))
        fig.patch.set_alpha(0) # 背景透明
        
        if sum(sizes) == 0:
            ax.text(0.5, 0.5, "帳戶目前尚無資產", ha='center', va='center', fontsize=20, color='gray')
            ax.axis('off')
        else:
            colors = plt.cm.Set3.colors
            explode = [0.03] * len(sizes)
            
            wedges, texts, autotexts = ax.pie(
                sizes, labels=labels, autopct='%1.1f%%', startangle=140, 
                colors=colors, explode=explode, pctdistance=0.82,
                textprops={'fontsize': 20, 'fontweight': 'bold'}
            )
            
            # 白色描邊效果 (避免深色背景看不見文字)
            text_glow = [path_effects.withStroke(linewidth=3, foreground="white")]

            for t in texts:
                t.set_color('black')
                t.set_path_effects(text_glow)

            for autotext in autotexts:
                autotext.set_color('darkred')
                autotext.set_path_effects(text_glow)
                
            centre_circle = plt.Circle((0,0), 0.65, fc='white')
            ax.add_artist(centre_circle)
            
            total_val = sum(sizes)
            total_text = ax.text(
                0, 0, f"總資產估值\n{total_val:,.0f} 元", 
                ha='center', va='center', fontsize=18, fontweight='bold', color='black'
            )
            total_text.set_path_effects(text_glow)

        # 4. 回傳圖片
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', bbox_inches='tight', transparent=True, dpi=120)
        img_buffer.seek(0)
        plt.close(fig) 
        
        return StreamingResponse(img_buffer, media_type="image/png")
        
    except Exception as e:
        print(f"❌ 畫圖失敗: {e}")
        raise HTTPException(status_code=500, detail="生成圓餅圖時發生內部錯誤")
    finally:
        db.close()

# ==========================================
# 啟動伺服器
# ==========================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
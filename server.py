"""
股票分析 Agent - FastAPI Web Server
提供 REST API 介面讓前端呼叫
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent import StockAnalysisSession
import time

app = FastAPI(
    title="智能財報分析 Agent API",
    description="使用 LangGraph + Google Gemini 的股票分析 AI Agent",
    version="1.0.0",
)

# 設定 CORS，讓網頁前端可以跨網域呼叫這個 API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 儲存各 session（開發環境暫用 dict，生產環境應使用 Redis）
sessions: dict[str, StockAnalysisSession] = {}

class AnalyzeRequest(BaseModel):
    session_id: str
    message: str

class AnalyzeResponse(BaseModel):
    session_id: str
    output: str
    tool_calls_count: int
    history_length: int

@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    # 1. 確保 session 存在
    if req.session_id not in sessions:
        sessions[req.session_id] = StockAnalysisSession()

    session = sessions[req.session_id]
    
    # 2. 執行分析 (因為 agent.py 裡面已經有 3 次重試機制了，這裡直接呼叫即可)
    try:
        result = session.analyze(req.message)
        
        return AnalyzeResponse(
            session_id=req.session_id,
            output=result["output"],
            tool_calls_count=result["steps"], # 💡 修正: 直接取整數，不用 len()
            history_length=len(session.chat_history), # 💡 修正: 直接從 session 算長度
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/session/{session_id}")
def reset_session(session_id: str):
    """清除指定 session 的對話歷史"""
    if session_id in sessions:
        sessions[session_id].reset()
        return {"message": f"Session {session_id} 已重置"}
    return {"message": "Session 不存在"}

@app.get("/health")
def health():
    return {"status": "ok", "active_sessions": len(sessions)}

if __name__ == "__main__":
    import uvicorn
    # reload=True 讓你改程式碼存檔時，伺服器會自動重啟
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
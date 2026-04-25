import streamlit as st
import requests
import uuid

# 1. 網頁基本設定
st.set_page_config(page_title="阿財 - 智能財報分析 Agent", page_icon="📈", layout="centered")

# 設定 FastAPI 後端的網址
API_URL = "https://stock-agent-api-1jsl.onrender.com"

# 2. 初始化 Session State (記憶體)
# 給每個使用者一個獨一無二的 ID
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# 用來存放聊天紀錄
if "messages" not in st.session_state:
    st.session_state.messages = []
    # 阿財的開場白
    st.session_state.messages.append({
        "role": "assistant", 
        "content": "你好！我是智能財報分析 Agent「阿財」📈\n\n請輸入你想查詢的**台灣股票代碼或名稱**（例如：`2330` 或 `聯電`），我會幫你抓取最新股價、財報與新聞，並進行綜合分析！"
    })

# 3. 側邊欄設定 (Sidebar)
with st.sidebar:
    st.title("⚙️ 系統控制")
    st.write(f"當前 Session: `{st.session_state.session_id[:8]}...`")
    
    # 清除對話按鈕
    if st.button("🗑️ 清除對話紀錄並重置"):
        # 呼叫後端 API 清除記憶
        try:
            requests.delete(f"{API_URL}/session/{st.session_state.session_id}")
        except:
            pass
        # 清除前端畫面
        st.session_state.messages = []
        st.rerun()

# 4. 主畫面標題
st.title("📈 智能財報與新聞分析 Agent")
st.markdown("---")

# 5. 顯示歷史聊天紀錄
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 6. 接收使用者輸入
if prompt := st.chat_input("請輸入股票代碼 (例如: 2330)..."):
    
    # 把使用者的訊息加到畫面上
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 呼叫 FastAPI 後端
    with st.chat_message("assistant"):
        with st.spinner("🤖 阿財正在上網找資料與分析中，請稍候... (約需 10-20 秒)"):
            try:
                # 準備要傳給 API 的資料
                payload = {
                    "session_id": st.session_state.session_id,
                    "message": prompt
                }
                
                # 發送 POST 請求
                response = requests.post(f"{API_URL}/analyze", json=payload, timeout=120)
                
                if response.status_code == 200:
                    data = response.json()
                    ai_reply = data["output"]
                    # 可以在畫面底部偷塞一個小提示，顯示用了幾個工具
                    ai_reply += f"\n\n*(💡 本次分析使用了 {data['tool_calls_count']} 個工具步驟)*"
                else:
                    ai_reply = f"❌ 發生錯誤 (Status: {response.status_code}): {response.text}"
                    
            except requests.exceptions.ConnectionError:
                ai_reply = "❌ 無法連線到後端伺服器！請確認你的 FastAPI (server.py) 已經啟動。"
            except Exception as e:
                ai_reply = f"❌ 系統發生預期外的錯誤: {str(e)}"
        
        # 顯示結果並存入記憶
        st.markdown(ai_reply)
        st.session_state.messages.append({"role": "assistant", "content": ai_reply})
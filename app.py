import streamlit as st
import requests
import uuid
import os

st.set_page_config(page_title="阿財 - 智能理專 (多人版)", page_icon="📈", layout="centered")
API_URL = os.getenv("API_URL", "http://localhost:8000")

# 初始化變數
if "session_id" not in st.session_state: 
    st.session_state.session_id = str(uuid.uuid4())
if "token" not in st.session_state: 
    st.session_state.token = None
if "messages" not in st.session_state: 
    st.session_state.messages = [{"role": "assistant", "content": "你好！我是你的專屬智能理專「阿財」。請輸入股票代碼或分析指令..."}]

# --- 🔒 登入/註冊畫面 ---
if not st.session_state.token:
    st.title("🔐 歡迎來到阿財智能理專平台")
    tab1, tab2 = st.tabs(["登入", "註冊新帳號"])
    
    with tab1:
        u_login = st.text_input("帳號", key="l_user")
        p_login = st.text_input("密碼", type="password", key="l_pass")
        if st.button("登入系統"):
            res = requests.post(f"{API_URL}/login", json={"username": u_login, "password": p_login})
            if res.status_code == 200:
                st.session_state.token = res.json()["access_token"]
                st.rerun()
            else:
                st.error("登入失敗：帳號或密碼錯誤")
                
    with tab2:
        u_reg = st.text_input("設定新帳號", key="r_user")
        p_reg = st.text_input("設定密碼", type="password", key="r_pass")
        if st.button("註冊"):
            res = requests.post(f"{API_URL}/register", json={"username": u_reg, "password": p_reg})
            if res.status_code == 200: 
                st.success("註冊成功！請切換到登入頁面登入。")
            else:
                try:
                    st.error(res.json().get("detail", "註冊失敗"))
                except:
                    st.error(f"⚠️ 伺服器內部崩潰 (Status {res.status_code})：{res.text}")
    st.stop() # 阻擋未登入者往下看

# --- 📈 主畫面 (已登入) ---
with st.sidebar:
    if st.button("🚪 登出"):
        st.session_state.token = None
        st.session_state.messages = []
        st.rerun()
        
    st.title("📊 專屬資產配置圖")
    # 動態抓圖
    img_res = requests.get(f"{API_URL}/portfolio/pie-chart?token={st.session_state.token}")
    if img_res.status_code == 200:
        st.image(img_res.content, use_container_width=True)
    else:
        st.info("尚無資產資料或發生錯誤。")

st.title("📈 智能財報與新聞分析 Agent")
st.markdown("---")

# 顯示聊天紀錄
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): 
        st.markdown(msg["content"])

# 聊天輸入框
if prompt := st.chat_input("請輸入指令..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): 
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("🤖 阿財正在上網找資料與分析中，請稍候... (約需 10-20 秒)"):
            try:
                # 準備要傳給 API 的資料 (加入 Token)
                payload = {
                    "session_id": st.session_state.session_id,
                    "message": prompt,
                    "token": st.session_state.token
                }
                
                response = requests.post(f"{API_URL}/analyze", json=payload, timeout=120)
                
                if response.status_code == 200:
                    data = response.json()
                    ai_reply = data["output"]
                    ai_reply += f"\n\n*(💡 本次分析使用了 {data['tool_calls_count']} 個工具步驟)*"
                    
                    st.markdown(ai_reply)
                    st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                    
                    # 重新整理畫面，讓側邊欄的圓餅圖同步更新！
                    st.rerun() 
                    
                else:
                    st.error(f"❌ 發生錯誤 (Status: {response.status_code}): {response.text}")
                    
            except requests.exceptions.ConnectionError:
                st.error("❌ 無法連線到後端伺服器！請確認 server.py 是否正在運行。")
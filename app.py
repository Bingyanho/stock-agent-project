import streamlit as st
import requests
import uuid
import os

# --- 1. 頁面基礎設定 (必須放在第一行) ---
st.set_page_config(page_title="阿財 - 智能理財專員", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

# --- 2. 修正後的 CSS (完美適應深/淺色模式，並隱藏標題連結符號) ---
custom_css = """
<style>
    /* 隱藏預設 Streamlit 浮水印與右上角選單 (但不隱藏 header 以保留側邊欄箭頭) */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* 徹底隱藏標題旁邊的連結符號 (Anchor Link) 以保持絕對置中 */
    .main .element-container a { display: none; }
    [data-testid="stMarkdownContainer"] a.anchor { display: none; }
    h1 a, h2 a, h3 a, h4 a, h5 a, h6 a { display: none !important; }
    
    /* 按鈕全局美化 (漸層高質感) */
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        color: white !important;
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
        width: 100%;
    }
    div.stButton > button:first-child:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
    }
    
    /* 標題漸層文字 */
    .title-text {
        background: linear-gradient(135deg, #3B82F6 0%, #60A5FA 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 800;
        margin-bottom: 0px;
    }
    
    .subtitle-text {
        /* 使用原生次要文字顏色，確保深淺模式都能看清 */
        color: var(--text-color);
        opacity: 0.7;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    /* 登入視窗卡片化 - 使用 Streamlit 原生變數以適應深淺色模式 */
    .login-card {
        background-color: var(--secondary-background-color);
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.15);
        border: 1px solid var(--primary-color);
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

API_URL = os.getenv("API_URL", "http://localhost:8000")

# 初始化變數
if "session_id" not in st.session_state: 
    st.session_state.session_id = str(uuid.uuid4())
if "token" not in st.session_state: 
    st.session_state.token = None
if "messages" not in st.session_state: 
    st.session_state.messages = [{"role": "assistant", "content": "您好！我是您的專屬智能理專「**阿財**」。\n\n您可以問我：\n- *台積電與聯發科的比較分析*\n- *幫我進行量化分析*\n- *分析我的庫存情況*"}]

# ==========================================
# 🔓 登入/註冊畫面 (置中卡片設計)
# ==========================================
if not st.session_state.token:
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h1 class='title-text' style='text-align: center;'>智能理專平台</h1>", unsafe_allow_html=True)
        st.markdown("<p class='subtitle-text' style='text-align: center;'>結合量化分析與 AI Agent</p>", unsafe_allow_html=True)
        
        with st.container(border=True):
            tab1, tab2 = st.tabs(["🔑 系統登入", "📝 註冊新帳號"])
            
            with tab1:
                st.write("") 
                u_login = st.text_input("👤 帳號 (Username)", key="l_user")
                p_login = st.text_input("🔒 密碼 (Password)", type="password", key="l_pass")
                st.write("")
                if st.button("登入系統", use_container_width=True):
                    res = requests.post(f"{API_URL}/login", json={"username": u_login, "password": p_login})
                    if res.status_code == 200:
                        st.session_state.token = res.json()["access_token"]
                        st.rerun()
                    else:
                        st.error("❌ 登入失敗：帳號或密碼錯誤")
                        
            with tab2:
                st.write("")
                u_reg = st.text_input("👤 設定新帳號", key="r_user")
                p_reg = st.text_input("🔒 設定密碼", type="password", key="r_pass")
                st.write("")
                if st.button("註冊帳號", use_container_width=True):
                    res = requests.post(f"{API_URL}/register", json={"username": u_reg, "password": p_reg})
                    if res.status_code == 200: 
                        st.success("✅ 註冊成功！請切換到登入頁面登入。")
                    else:
                        try:
                            st.error(res.json().get("detail", "註冊失敗"))
                        except:
                            st.error(f"⚠️ 伺服器內部崩潰 (Status {res.status_code})：{res.text}")
    st.stop()

# ==========================================
# 📊 側邊欄設計 (資產配置圖)
# ==========================================
with st.sidebar:
    st.markdown("<h2 class='title-text' style='font-size: 1.8rem;'>個人資產面板</h2>", unsafe_allow_html=True)
    st.markdown("---")
    
    with st.spinner("載入庫存數據中..."):
        img_res = requests.get(f"{API_URL}/portfolio/pie-chart?token={st.session_state.token}")
        if img_res.status_code == 200:
            st.image(img_res.content, use_container_width=True, caption="即時資產佔比與庫存狀態")
        else:
            st.info("💡 目前尚無庫存資料，請透過聊天室下單！")
            
    st.markdown("---")
    if st.button("🚪 安全登出", key="logout_btn"):
        st.session_state.token = None
        st.session_state.messages = []
        st.rerun()

# ==========================================
# 💬 主畫面聊天室設計
# ==========================================
colA, colB = st.columns([3, 1])
with colA:
    st.markdown("<h1 class='title-text'>阿財 Agent 對話終端</h1>", unsafe_allow_html=True)
    st.markdown("<p class='subtitle-text'>即時網搜 × 量化選股 × 自動記帳</p>", unsafe_allow_html=True)

st.divider() 

# 移除自訂 avatar，恢復預設頭像
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): 
        st.markdown(msg["content"])

if prompt := st.chat_input("請輸入股票代碼..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    # 移除自訂 avatar
    with st.chat_message("user"): 
        st.markdown(prompt)

    # 移除自訂 avatar
    with st.chat_message("assistant"):
        status_msg = st.empty()
        status_msg.info("⚡ 阿財正在啟動工具鏈，調閱最新市場數據，請稍候...")
        
        with st.spinner(""):
            try:
                payload = {
                    "session_id": st.session_state.session_id,
                    "message": prompt,
                    "token": st.session_state.token
                }
                
                response = requests.post(f"{API_URL}/analyze", json=payload, timeout=120)
                status_msg.empty() 
                
                if response.status_code == 200:
                    data = response.json()
                    ai_reply = data["output"]
                    
                    tool_count = data.get('tool_calls_count', 0)
                    ai_reply += f"\n\n---\n*💡 本次回覆共調用並行工具 **{tool_count}** 次*"
                    
                    st.markdown(ai_reply)
                    st.session_state.messages.append({"role": "assistant", "content": ai_reply})
                    
                    st.rerun() 
                    
                else:
                    st.error(f"❌ 發生錯誤 (Status: {response.status_code}): {response.text}")
                    
            except requests.exceptions.ConnectionError:
                status_msg.empty()
                st.error("❌ 無法連線到後端伺服器！請確認您的 API URL 是否正確運行。")
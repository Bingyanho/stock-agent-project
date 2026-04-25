import os
import google.generativeai as genai
from dotenv import load_dotenv

# 1. 載入 .env 檔案中的 GOOGLE_API_KEY
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("❌ 找不到 API Key，請確認 .env 檔案設定！")
    exit()

# 2. 設定金鑰
genai.configure(api_key=api_key)

# 3. 抓取並過濾模型清單
print("🔍 正在連線至 Google 伺服器查詢可用模型...\n")
print("-" * 50)

# genai.list_models() 會抓出所有模型
for m in genai.list_models():
    # 我們只關心支援 "generateContent" (文字/對話生成) 的模型
    if 'generateContent' in m.supported_generation_methods:
        # 把前面的 'models/' 字串拿掉，剩下的就是你可以填入 LangChain 的名稱
        model_name = m.name.replace("models/", "")
        print(f"✅ 模型代碼： {model_name}")
        print(f"   📝 官方說明： {m.description}")
        print("-" * 50)
        
print("✨ 查詢完畢！你可以挑選一個『模型代碼』貼到 agent.py 裡面測試。")
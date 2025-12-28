import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ================= 配置区域 =================
USER_EMAIL = os.environ.get("ALTR_EMAIL")
USER_PASSWORD = os.environ.get("ALTR_PASSWORD")
LOGIN_URL = "https://console.altr.cc/login" 
# ===========================================

def run_auto_claim():
    print(">>> [启动] V5 侦测模式启动...")
    
    if not USER_EMAIL or not USER_PASSWORD:
        print(">>> [错误] 环境变量未设置！")
        return

    # --- 浏览器配置 (增强抗检测) ---
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new") 
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # 随机化 User-Agent (使用最新的 Chrome 120)
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    # 忽略证书错误
    options.add_argument("--ignore-certificate-errors")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # 注入 JS 绕过 webdriver 检测
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        """
    })

    try:
        print(f">>> [访问] 正在加载: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        
        # 强制等待 10 秒，让 JS 和盾牌跑完
        print(">>> [等待] 正在等待页面加载 (10s)...")
        time.sleep(10)

        # --- 🔍 侦测环节 ---
        page_title = driver.title
        print(f">>> [调试] 当前页面标题: [{page_title}]")
        
        # 打印一下当前的 URL，看看有没有被重定向
        print(f">>> [调试] 当前 URL: {driver.current_url}")

        # 尝试寻找任何输入框 (范围更广)
        try:
            print(">>> [寻找] 尝试定位输入框...")
            # 只要是 input 标签我们都找找看
            inputs = driver.find_elements(By.TAG_NAME, "input")
            print(f">>> [调试] 页面上发现了 {len(inputs)} 个输入框。")
            
            if len(inputs) == 0:
                # 如果一个输入框都没有，说明被拦截了
                raise Exception("页面上没有发现任何输入框！")

            # 寻找特定的邮箱框
            email_input = None
            for inp in inputs:
                input_type = inp.get_attribute("type")
                input_placeholder = inp.get_attribute("placeholder")
                # 打印属性帮我们分析
                print(f"    - 发现输入框: type='{input_type}', placeholder='{input_placeholder}'")
                
                if input_type == "email" or (input_placeholder and "mail" in input_placeholder.lower()):
                    email_input = inp
                    break
            
            if not email_input:
                # 再次尝试用 CSS selector 强找
                email_input = driver.find_element(By.CSS_SELECTOR, "input[type='email']")

            print(">>> [登录] 找到邮箱输入框，准备输入...")
            email_input.clear()
            email_input.send_keys(USER_EMAIL)
            time.sleep(1)

            # 寻找密码框
            password_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            password_input.clear()
            password_input.send_keys(USER_PASSWORD)
            time.sleep(1)

            # 点击登录
            submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            driver.execute_script("arguments[0].click();", submit_btn)
            print(">>> [动作] 点击了登录按钮")

            # 等待结果
            time.sleep(5)
            # 检查是否有 Credits 元素
            if "credits" in driver.page_source:
                 print(">>> [成功] 登录成功！页面包含 'credits'")
                 # 这里可以继续你的签到逻辑...
            else:
                 print(">>> [警告] 未检测到积分信息，可能需要手动验证。")

        except Exception as e:
            print("\n========== ⚠️ 异常诊断报告 ⚠️ ==========")
            print(f"错误信息: {e}")
            print("-" * 30)
            print(">>> [抓取] 页面源代码片段 (前 1000 字符):")
            # 获取页面 Body 的文本内容，如果是 Cloudflare 会显示 "Just a moment..."
            try:
                body_text = driver.find_element(By.TAG_NAME, "body").text
                # 替换换行符防止报错
                clean_text = body_text.replace('\n', '  ')[:1000]
                print(clean_text)
            except:
                print("无法获取页面文本。")
            print("=" * 40)

    except Exception as outer_e:
        print(f">>> [致命错误] {outer_e}")

    finally:
        driver.quit()

if __name__ == "__main__":
    run_auto_claim()

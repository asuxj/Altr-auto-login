import os
import time
import sys
# 导入 Selenium 相关库
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, WebDriverException

# ================= 配置区域 =================
LOGIN_URL = "https://dash.zampto.net/"
ACCOUNTS_ENV = os.environ.get("ZAMPTO_ACCOUNTS")
# ===========================================

def run_renewal_for_user(username, password):
    print(f"\n>>> [开始] 正在处理账号: {username}")
    
    # --- 1. 防崩溃浏览器配置 ---
    options = webdriver.ChromeOptions()
    # 使用新版无头模式
    options.add_argument('--headless=new') 
    
    # 核心防崩溃参数 (针对 GitHub Actions 环境)
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage') # 解决共享内存不足导致的崩溃
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer') # 关键：防止图形渲染崩溃
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-infobars')
    options.add_argument('--window-size=1920,1080')
    
    # 伪装 User-Agent (防止被识别为爬虫)
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 30) # 延长等待时间到30秒

        # --- 2. 登录流程 ---
        print(f">>> [登录] 打开页面: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        
        # 调试信息
        print(f">>> [调试] 页面标题: {driver.title}")

        # --- 适配 Logto 登录系统 ---
        # Logto 的用户名输入框 name 通常是 "identifier"
        # 我们查找: name="identifier" (Logto专用) 或 email 或 username
        print(">>> [登录] 正在寻找账号输入框...")
        user_input = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[name='identifier'], input[name='email'], input[name='username']")
        ))
        user_input.clear()
        user_input.send_keys(username)
        print(">>> [登录] 已输入账号")
        time.sleep(0.5) # 稍微停顿

        # 寻找密码输入框
        pwd_input = driver.find_element(By.NAME, "password")
        pwd_input.clear()
        pwd_input.send_keys(password)
        print(">>> [登录] 已输入密码")
        time.sleep(0.5)

        # 点击登录按钮
        submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        submit_btn.click()
        print(">>> [登录] 点击提交，等待跳转...")

        # 验证是否登录成功
        try:
            # 等待 URL 变化，或者页面出现 Dashboard 字样
            wait.until(EC.url_matches(r"overview|dashboard"))
            print(">>> [登录] 登录成功！")
        except TimeoutException:
            print(f">>> [错误] 登录超时，当前 URL: {driver.current_url}")
            # 如果还在登录页，可能是密码错误或由于JS加载慢导致
            # 尝试打印页面上的错误提示（如果有）
            try:
                error_msg = driver.find_element(By.CSS_SELECTOR, "[role='alert'], .error").text
                print(f">>> [页面提示] {error_msg}")
            except:
                pass
            raise Exception("Login timeout")

        # --- 3. 获取服务器列表 ---
        server_links = []
        # 这里的逻辑保持不变
        buttons = driver.find_elements(By.CSS_SELECTOR, "a[href*='server?id=']")
        for btn in buttons:
            href = btn.get_attribute("href")
            if href and href not in server_links:
                server_links.append(href)
        
        print(f">>> [检测] 账号 {username} 下发现 {len(server_links)} 个服务器。")

        # --- 4. 逐个续费 ---
        for link in server_links:
            print(f"--- 正在处理服务器: {link} ---")
            driver.get(link)
            try:
                # 寻找续费按钮
                renew_btn = wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "a.action-button[onclick*='handleServerRenewal']")
                ))
                
                # 滚动并点击
                driver.execute_script("arguments[0].scrollIntoView();", renew_btn)
                time.sleep(1) 
                renew_btn.click()
                print(">>> [操作] 点击了续费按钮")
                
                # 处理弹窗
                try:
                    WebDriverWait(driver, 3).until(EC.alert_is_present())
                    driver.switch_to.alert.accept()
                    print(">>> [弹窗] 已确认")
                except TimeoutException:
                    pass
                
                print(">>> [成功] 续费指令已发送")
                time.sleep(2)
            except TimeoutException:
                print(">>> [跳过] 未找到续费按钮 (可能已续费)")
            except Exception as e:
                print(f">>> [出错] 服务器处理错误: {e}")

    except WebDriverException as e:
        print(f">>> [致命错误] 浏览器崩溃或驱动异常: {e}")
        # 如果再次崩溃，查看是否是因为内存不足
        print(">>> [建议] 如果持续崩溃，可能是 GitHub Runner 内存不足。")

    except Exception as e:
        print(f">>> [失败] 账号 {username} 逻辑错误: {e}")

    finally:
        if driver:
            driver.quit()
        print(f">>> [结束] 账号 {username} 会话已关闭。\n")

def main():
    if not ACCOUNTS_ENV:
        print(">>> [错误] 环境变量 ZAMPTO_ACCOUNTS 未设置。")
        sys.exit(1)
    
    account_list = ACCOUNTS_ENV.split(',')
    for account_str in account_list:
        if ':' not in account_str: continue
        username, password = account_str.strip().split(':', 1)
        run_renewal_for_user(username.strip(), password.strip())

if __name__ == "__main__":
    main()

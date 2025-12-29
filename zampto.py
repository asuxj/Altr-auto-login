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
# 强制指定概览页地址
OVERVIEW_URL = "https://dash.zampto.net/overview" 
# 从环境变量获取账号密码
ACCOUNTS_ENV = os.environ.get("ZAMPTO_ACCOUNTS")
# ===========================================

def run_renewal_for_user(username, password):
    print(f"\n>>> [开始] 正在处理账号: {username}")
    
    # --- 1. 浏览器配置 ---
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new') 
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-extensions')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, 30)

        # --- 2. 登录流程 ---
        print(f">>> [登录] 打开页面: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        
        # 输入账号
        print(">>> [登录] 正在输入账号...")
        user_input = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[name='identifier'], input[name='email'], input[name='username']")
        ))
        user_input.clear()
        user_input.send_keys(username)
        print(">>> [登录] 账号输入完毕")
        
        # 智能等待密码框
        pwd_input = None
        try:
            # 方案A: 尝试直接找密码框 (等2秒)
            pwd_input = WebDriverWait(driver, 2).until(
                EC.visibility_of_element_located((By.NAME, "password"))
            )
        except TimeoutException:
            # 方案B: 找不到则点击“下一步”
            print(">>> [登录] 进入两步验证模式，点击下一步...")
            next_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            next_btn.click()
            print(">>> [登录] 等待密码框加载...")
            pwd_input = wait.until(
                EC.visibility_of_element_located((By.NAME, "password"))
            )

        # 输入密码
        pwd_input.clear()
        pwd_input.send_keys(password)
        time.sleep(1)
        
        # 提交登录
        login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_btn.click()
        print(">>> [登录] 点击提交，等待跳转...")

        # --- 3. 验证登录 & 强制跳转 (核心修复) ---
        login_success = False
        try:
            # 等待 URL 变成 overview 或 homepage
            wait.until(EC.url_matches(r"overview|dashboard|homepage"))
            login_success = True
            print(f">>> [登录] 登录成功！当前页面: {driver.current_url}")
        except TimeoutException:
            # 【双重保险】如果超时了，再检查一次当前 URL
            current_url = driver.current_url
            if "homepage" in current_url or "overview" in current_url:
                print(f">>> [登录] 判定超时但检测到 URL 已变更: {current_url}，视为成功。")
                login_success = True
            else:
                print(f">>> [错误] 登录彻底超时，当前停留: {current_url}")
                # 尝试打印页面错误提示
                try: 
                    print(f"    提示: {driver.find_element(By.CSS_SELECTOR, '.error, [role=alert]').text}") 
                except: pass
                raise Exception("Login verification failed")

        # 只要登录成功，就强制跳转到概览页
        if login_success:
            if "overview" not in driver.current_url:
                print(f">>> [导航] 正在强制跳转至服务器列表页: {OVERVIEW_URL}")
                driver.get(OVERVIEW_URL)
                # 等待概览页加载
                wait.until(EC.url_contains("overview"))
                print(">>> [导航] 已到达概览页")

        # --- 4. 获取服务器列表 ---
        server_links = []
        try:
            print(">>> [列表] 正在扫描服务器卡片...")
            # 等待至少一个 server-card 出现，最多等15秒
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CLASS_NAME, "server-card")))
            
            # 找到所有的卡片元素
            cards = driver.find_elements(By.CLASS_NAME, "server-card")
            print(f">>> [列表] 发现了 {len(cards)} 个服务器卡片。")
            
            for card in cards:
                try:
                    # 在当前卡片内查找 Manage 按钮
                    link_element = card.find_element(By.CSS_SELECTOR, "a.btn.btn-primary[href*='server?id=']")
                    href = link_element.get_attribute("href")
                    
                    # 获取服务器名字
                    server_name = card.get_attribute("data-server-name") or "Unknown"
                    
                    if href:
                        print(f"    - 发现服务器: {server_name} (ID: {card.get_attribute('data-server-id')})")
                        server_links.append(href)
                except Exception as loop_e:
                    print(f"    - [警告] 解析某张卡片时出错: {loop_e}")

        except TimeoutException:
            print(">>> [提示] 未找到 'server-card' 元素，可能该账号下没有服务器。")

        # --- 5. 逐个续费 ---
        if not server_links:
            print(">>> [结束] 没有需要处理的服务器。")
            return

        print(f">>> [处理] 开始处理 {len(server_links)} 个服务器的续费任务...")

        for index, link in enumerate(server_links):
            print(f"\n--- 正在处理第 {index + 1} 个服务器 ---")
            print(f">>> [跳转] 进入详情页: {link}")
            driver.get(link)
            
            try:
                # 定位续费按钮
                renew_btn = wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "a[onclick*='handleServerRenewal']")
                ))
                
                # 滚动到按钮位置
                driver.execute_script("arguments[0].scrollIntoView();", renew_btn)
                time.sleep(1) 
                
                print(">>> [操作] 点击 'Renew Server' 按钮...")
                renew_btn.click()
                
                # 处理弹窗
                try:
                    WebDriverWait(driver, 3).until(EC.alert_is_present())
                    alert = driver.switch_to.alert
                    print(f">>> [弹窗] 接受弹窗信息: {alert.text}")
                    alert.accept()
                    print(">>> [成功] 弹窗已确认")
                except TimeoutException:
                    print(">>> [提示] 未检测到弹窗，可能直接续费成功。")
                
                time.sleep(2)
                
            except TimeoutException:
                print(">>> [跳过] 未在页面上找到续费按钮 (可能已经续费过了)。")
            except Exception as e:
                print(f">>> [出错] 处理该服务器时发生未知错误: {e}")

    except Exception as e:
        print(f">>> [失败] 账号 {username} 发生全局错误: {e}")
        if driver:
             try:
                print(f">>> [调试] 当前 URL: {driver.current_url}")
             except: pass

    finally:
        if driver:
            driver.quit()
        print(f">>> [结束] 账号 {username} 会话已关闭。\n")

def main():
    if not ACCOUNTS_ENV:
        print(">>> [错误] 未检测到环境变量 'ZAMPTO_ACCOUNTS'。")
        sys.exit(1)
    
    account_list = ACCOUNTS_ENV.split(',')
    print(f">>> [系统] 共检测到 {len(account_list)} 个待处理账号。")

    for account_str in account_list:
        if ':' not in account_str:
            continue
        username, password = account_str.strip().split(':', 1)
        run_renewal_for_user(username.strip(), password.strip())

if __name__ == "__main__":
    main()

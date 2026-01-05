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
    """
    执行单个用户的续费操作
    参数:
      username: 用户名
      password: 密码
    """
    print(f"\n>>> [开始] 正在处理账号: {username}")
    
    # --- 1. 浏览器配置 (关键修改：增加反检测配置) ---
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new') # 无头模式
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080') # 设置大窗口，避免响应式布局隐藏元素
    options.add_argument('--disable-extensions')
    
    # [新增] 屏蔽自动化受控提示，这是绕过简单反爬的关键
    options.add_argument('--disable-blink-features=AutomationControlled') 
    # 模拟真实浏览器 User-Agent
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # [新增] 移除 `navigator.webdriver` 标记，进一步隐藏机器人身份
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        wait = WebDriverWait(driver, 30) # 全局等待30秒

        # --- 2. 登录流程 ---
        print(f">>> [登录] 打开页面: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        
        print(">>> [登录] 正在输入账号...")
        user_input = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[name='identifier'], input[name='email'], input[name='username']")
        ))
        user_input.clear()
        user_input.send_keys(username)
        print(">>> [登录] 账号输入完毕")
        
        # 智能等待密码框
        try:
            pwd_input = WebDriverWait(driver, 2).until(
                EC.visibility_of_element_located((By.NAME, "password"))
            )
        except TimeoutException:
            print(">>> [登录] 进入两步验证模式，点击下一步...")
            next_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            next_btn.click()
            print(">>> [登录] 等待密码框加载...")
            pwd_input = wait.until(
                EC.visibility_of_element_located((By.NAME, "password"))
            )

        pwd_input.clear()
        pwd_input.send_keys(password)
        time.sleep(1) 
        
        login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_btn.click()
        print(">>> [登录] 点击提交，等待跳转...")

        # --- 3. 验证登录 & 强制跳转 ---
        login_success = False
        try:
            wait.until(EC.url_matches(r"overview|dashboard|homepage"))
            login_success = True
            print(f">>> [登录] 登录成功！当前页面: {driver.current_url}")
        except TimeoutException:
            # 双重检查
            if "homepage" in driver.current_url or "overview" in driver.current_url:
                login_success = True
            else:
                print(f">>> [错误] 登录超时，当前URL: {driver.current_url}")
                # [调试] 登录失败也截图
                driver.save_screenshot("login_failed.png") 
                raise Exception("Login verification failed")

        if login_success:
            # 强制跳转到 overview，确保我们在正确的页面
            print(f">>> [导航] 正在强制跳转至服务器列表页: {OVERVIEW_URL}")
            driver.get(OVERVIEW_URL)
            wait.until(EC.url_contains("overview"))
            print(">>> [导航] 已到达概览页，等待数据加载...")
            time.sleep(5) # [新增] 强制死等5秒，让Ajax请求有时间完成加载

        # --- 4. 获取服务器列表 (关键修改) ---
        server_links = []
        try:
            print(">>> [列表] 正在扫描服务器卡片...")
            # [修改] 使用 CSS Selector .server-card，比 Class Name 更稳健
            # [修改] 等待时间确保足够长，应对慢速网络
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".server-card"))
            )
            
            cards = driver.find_elements(By.CSS_SELECTOR, ".server-card")
            print(f">>> [列表] 发现了 {len(cards)} 个服务器卡片。")
            
            for card in cards:
                try:
                    # 获取服务器名字，用于日志显示
                    server_name = card.get_attribute("data-server-name") or "Unknown"
                    server_id = card.get_attribute("data-server-id") or "Unknown"
                    
                    # 查找 Manage 按钮
                    link_element = card.find_element(By.CSS_SELECTOR, "a.btn.btn-primary[href*='server?id=']")
                    href = link_element.get_attribute("href")
                    
                    if href:
                        print(f"    - 发现服务器: {server_name} (ID: {server_id})")
                        server_links.append(href)
                except Exception as loop_e:
                    print(f"    - [警告] 解析某张卡片时出错: {loop_e}")

        except TimeoutException:
            # ================= [调试核心] =================
            # 如果找不到卡片，这里会执行。
            # 我们把当前看到的页面保存下来，你就能知道为什么找不到了。
            print(">>> [提示] 未找到 'server-card' 元素。")
            print(">>> [调试] 正在保存当前页面截图到 'debug_error.png'...")
            driver.save_screenshot("debug_error.png")
            
            print(">>> [调试] 正在保存页面源码到 'debug_source.html'...")
            with open("debug_source.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            
            print(">>> [调试] 请在脚本同目录下查看上述两个文件，确认页面是否为空白或被拦截。")
            # =============================================

        # --- 5. 逐个续费 ---
        if not server_links:
            print(">>> [结束] 没有需要处理的服务器。")
            return

        print(f">>> [处理] 开始处理 {len(server_links)} 个服务器的续费任务...")

        for index, link in enumerate(server_links):
            print(f"\n--- 正在处理第 {index + 1} 个服务器 ---")
            driver.get(link)
            
            try:
                # 获取上次续费时间作为基准
                time_before = ""
                try:
                    wait.until(EC.presence_of_element_located((By.ID, "lastRenewalTime")))
                    time_before = driver.find_element(By.ID, "lastRenewalTime").text.strip()
                except: pass

                # 点击续费按钮
                renew_btn = wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "a[onclick*='handleServerRenewal'], a.action-button.action-purple")
                ))
                
                # 滚动到可见区域防止被遮挡
                driver.execute_script("arguments[0].scrollIntoView();", renew_btn)
                time.sleep(1) 
                
                print(">>> [操作] 点击 'Renew Server' 按钮...")
                renew_btn.click()
                
                # 处理弹窗
                try:
                    WebDriverWait(driver, 5).until(EC.alert_is_present())
                    alert = driver.switch_to.alert
                    print(f">>> [弹窗] 捕捉到信息: {alert.text}")
                    alert.accept()
                except TimeoutException:
                    pass
                
                # 验证结果
                print(">>> [验证] 正在等待数据更新...")
                try:
                    # 等待时间文字变化
                    WebDriverWait(driver, 10).until(
                        lambda d: d.find_element(By.ID, "lastRenewalTime").text.strip() != time_before
                    )
                    # 获取剩余时间
                    expiry_duration = driver.find_element(By.ID, "nextRenewalTime").text.strip()
                    print("------------------------------------------------")
                    print(f"✅ [成功] 续费成功！有效期: {expiry_duration}")
                    print("------------------------------------------------")
                except TimeoutException:
                    print(f"⚠️ [警告] 数据未更新，可能续费失败或响应过慢。")
                
            except Exception as e:
                print(f">>> [出错] 处理该服务器时发生错误: {e}")

    except Exception as e:
        print(f">>> [失败] 账号 {username} 发生全局错误: {e}")
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

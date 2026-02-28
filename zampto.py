import os
import time
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException

# ================= 配置区域 =================
LOGIN_URL = "https://dash.zampto.net/"
# 【修改】直接写死你的服务器ID列表，多个就加逗号
SERVER_IDS = ["3649"]  # 如果有多个服务器：["3649", "1234", "5678"]

ACCOUNTS_ENV = os.environ.get("ZAMPTO_ACCOUNTS")
# ===========================================

def run_renewal_for_user(username, password):
    print(f"\n>>> [开始] 正在处理账号: {username}")
    
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        wait = WebDriverWait(driver, 30)

        # --- 登录 ---
        print(f">>> [登录] 打开页面: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        
        user_input = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[name='identifier'], input[name='email'], input[name='username']")
        ))
        user_input.clear()
        user_input.send_keys(username)

        try:
            pwd_input = WebDriverWait(driver, 2).until(
                EC.visibility_of_element_located((By.NAME, "password"))
            )
        except TimeoutException:
            print(">>> [登录] 两步验证，点击下一步...")
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            pwd_input = wait.until(EC.visibility_of_element_located((By.NAME, "password")))

        pwd_input.clear()
        pwd_input.send_keys(password)
        time.sleep(1)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        print(">>> [登录] 点击提交，等待跳转...")

        try:
            wait.until(EC.url_matches(r"overview|dashboard|homepage"))
            print(f">>> [登录] 登录成功！当前页面: {driver.current_url}")
        except TimeoutException:
            print(f">>> [错误] 登录失败，当前URL: {driver.current_url}")
            driver.save_screenshot("login_failed.png")
            raise Exception("登录验证失败")

        # --- 【核心修改】直接按服务器ID逐个续费 ---
        for server_id in SERVER_IDS:
            server_url = f"https://dash.zampto.net/server?id={server_id}"
            print(f"\n--- 正在处理服务器 ID: {server_id} ---")
            print(f">>> [导航] 跳转至: {server_url}")
            driver.get(server_url)
            time.sleep(3)  # 等待页面加载

            try:
                # 【修改】根据你截图，按钮文字是 "Renew Server"，用 span 文字定位
                # 先尝试多种选择器，哪个能点就用哪个
                renew_btn = None
                selectors = [
                    "a[onclick*='handleServerRenewal']",
                    "a.action-button.action-purple",
                    "//a[contains(., 'Renew Server')]",  # XPath 按文字找
                    "//span[contains(text(), 'Renew Server')]/parent::a",
                ]
                
                for sel in selectors:
                    try:
                        if sel.startswith("//"):
                            renew_btn = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.XPATH, sel))
                            )
                        else:
                            renew_btn = WebDriverWait(driver, 5).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                            )
                        print(f">>> [按钮] 使用选择器找到按钮: {sel}")
                        break
                    except TimeoutException:
                        continue

                if not renew_btn:
                    print(f">>> [错误] 服务器 {server_id} 找不到续费按钮，保存调试文件...")
                    driver.save_screenshot(f"debug_server_{server_id}.png")
                    with open(f"debug_server_{server_id}.html", "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                    continue

                driver.execute_script("arguments[0].scrollIntoView();", renew_btn)
                time.sleep(1)
                print(">>> [操作] 点击 'Renew Server' 按钮...")
                renew_btn.click()

                # 处理弹窗
                try:
                    WebDriverWait(driver, 5).until(EC.alert_is_present())
                    alert = driver.switch_to.alert
                    print(f">>> [弹窗] 信息: {alert.text}")
                    alert.accept()
                except TimeoutException:
                    pass

                time.sleep(3)  # 等待结果刷新
                print("------------------------------------------------")
                print(f"✅ [成功] 服务器 {server_id} 续费操作已完成！")
                print("------------------------------------------------")

            except Exception as e:
                print(f">>> [出错] 服务器 {server_id} 处理失败: {e}")
                driver.save_screenshot(f"error_server_{server_id}.png")

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

import os
import time
import sys
import random
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains

LOGIN_URL = "https://dash.zampto.net/"
SERVER_IDS = ["3649"]
ACCOUNTS_ENV = os.environ.get("ZAMPTO_ACCOUNTS")

def human_delay(a=1.5, b=3.5):
    """模拟人类随机延迟"""
    time.sleep(random.uniform(a, b))

def move_mouse_randomly(driver):
    """随机移动鼠标，触发人类行为检测"""
    actions = ActionChains(driver)
    for _ in range(random.randint(3, 6)):
        x = random.randint(100, 800)
        y = random.randint(100, 600)
        actions.move_by_offset(x, y)
        actions.pause(random.uniform(0.1, 0.4))
    try:
        actions.perform()
    except:
        pass

def run_renewal_for_user(username, password):
    print(f"\n>>> [开始] 正在处理账号: {username}")

    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    # GitHub Actions 必须无头模式
    options.add_argument('--headless=new')

    driver = None
    try:
        # undetected_chromedriver 自动处理反检测
        driver = uc.Chrome(options=options, use_subprocess=True)
        wait = WebDriverWait(driver, 30)

        # --- 登录 ---
        print(f">>> [登录] 打开页面: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        human_delay(2, 4)  # 等页面完全加载
        move_mouse_randomly(driver)

        user_input = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "input[name='identifier'], input[name='email'], input[name='username']")
        ))
        human_delay(0.5, 1.5)
        # 模拟人类逐字输入
        for char in username:
            user_input.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))

        try:
            pwd_input = WebDriverWait(driver, 2).until(
                EC.visibility_of_element_located((By.NAME, "password"))
            )
        except TimeoutException:
            print(">>> [登录] 两步验证，点击下一步...")
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            human_delay(1, 2)
            pwd_input = wait.until(EC.visibility_of_element_located((By.NAME, "password")))

        human_delay(0.5, 1)
        for char in password:
            pwd_input.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))

        human_delay(0.8, 1.5)
        move_mouse_randomly(driver)
        driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
        print(">>> [登录] 点击提交，等待跳转...")

        try:
            wait.until(EC.url_matches(r"overview|dashboard|homepage"))
            print(f">>> [登录] 登录成功！当前页面: {driver.current_url}")
        except TimeoutException:
            print(f">>> [错误] 登录失败，当前URL: {driver.current_url}")
            driver.save_screenshot("login_failed.png")
            return

        # --- 逐个续费 ---
        for server_id in SERVER_IDS:
            server_url = f"https://dash.zampto.net/server?id={server_id}"
            print(f"\n--- 正在处理服务器 ID: {server_id} ---")
            driver.get(server_url)

            # 【关键】停留足够长时间让 Turnstile 完成隐形验证
            print(">>> [等待] 停留页面让 Turnstile 完成后台验证...")
            human_delay(4, 7)
            move_mouse_randomly(driver)
            human_delay(2, 3)

            try:
                # 找续费按钮并点击（弹出确认弹窗）
                renew_btn = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//a[contains(., 'Renew Server')] | //button[contains(., 'Renew Server')]")
                ))
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", renew_btn)
                human_delay(1, 2)
                print(">>> [操作] 点击 'Renew Server' 按钮...")
                renew_btn.click()

                # 等待确认弹窗出现并点确认
                human_delay(1, 2)
                try:
                    # 如果是原生 alert
                    WebDriverWait(driver, 5).until(EC.alert_is_present())
                    alert = driver.switch_to.alert
                    print(f">>> [弹窗] 捕获到: {alert.text}")
                    alert.accept()
                except TimeoutException:
                    # 如果是页面内自定义弹窗，找确认按钮
                    try:
                        confirm_btn = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH,
                                "//button[contains(.,'Confirm') or contains(.,'确认') or contains(.,'Yes')]"
                            ))
                        )
                        print(">>> [弹窗] 点击页面内确认按钮...")
                        confirm_btn.click()
                    except TimeoutException:
                        print(">>> [弹窗] 未检测到弹窗，可能已自动处理")

                # 等待结果
                human_delay(3, 5)

                # 检查是否成功（页面出现成功提示）
                try:
                    success_el = driver.find_element(By.ID, "renewalSuccess")
                    if success_el.is_displayed():
                        print("------------------------------------------------")
                        print(f"✅ [成功] 服务器 {server_id} 续费成功！")
                        print("------------------------------------------------")
                    else:
                        print(f"⚠️ [警告] 续费结果不明确，请检查截图")
                        driver.save_screenshot(f"result_{server_id}.png")
                except:
                    # 找不到成功元素也截图留证
                    print(">>> [提示] 无法确认结果，已保存截图")
                    driver.save_screenshot(f"result_{server_id}.png")

            except Exception as e:
                print(f">>> [出错] 服务器 {server_id} 处理失败: {e}")
                driver.save_screenshot(f"error_{server_id}.png")

    except Exception as e:
        print(f">>> [失败] 全局错误: {e}")
    finally:
        if driver:
            driver.quit()
        print(f">>> [结束] 账号 {username} 会话已关闭。\n")


def main():
    if not ACCOUNTS_ENV:
        print(">>> [错误] 未检测到环境变量 'ZAMPTO_ACCOUNTS'。")
        sys.exit(1)

    for account_str in ACCOUNTS_ENV.split(','):
        if ':' not in account_str:
            continue
        username, password = account_str.strip().split(':', 1)
        run_renewal_for_user(username.strip(), password.strip())

if __name__ == "__main__":
    main()

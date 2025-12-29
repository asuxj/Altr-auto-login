import time
import os
import sys
# 导入 Selenium 核心库
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ================= 配置区域 =================
# 登录地址
LOGIN_URL = "https://console.altr.cc/login" 
# 签到/奖励页面地址
REWARDS_URL = "https://console.altr.cc/rewards"
# ===========================================

def parse_credits(text):
    """
    辅助函数：提取文本中的数字
    例如输入 '622.9 credits' -> 返回 622.9
    """
    try:
        # 移除 'credits', 逗号和空格，转为浮点数
        clean_text = text.lower().replace('credits', '').replace(',', '').strip()
        return float(clean_text)
    except:
        return 0.0

def run_task_for_user(user_email, user_password, index):
    """
    针对单个用户执行签到任务
    参数:
      user_email: 用户邮箱
      user_password: 用户密码
      index: 当前是第几个账号（用于日志显示）
    """
    print(f"\n>>> [开始] 正在处理第 {index} 个账号: {user_email}")
    
    # --- 1. 浏览器配置 (每个账号独立配置) ---
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new") # 无头模式
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # 模拟真实浏览器 UA
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 20) # 设置默认等待时间 20秒

    # 注入防检测 JS (防止被识别为爬虫)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.navigator.chrome = { runtime: {} };
        """
    })

    try:
        # --- 2. 登录流程 ---
        print(f">>> [访问] 打开登录页: {LOGIN_URL}")
        driver.get(LOGIN_URL)
        time.sleep(3) # 简单等待页面加载

        print(">>> [登录] 定位输入框...")
        # 查找所有的 input 标签
        inputs = driver.find_elements(By.TAG_NAME, "input")
        if len(inputs) < 2:
            print(">>> [错误] 输入框数量不足，登录页面加载异常或结构已变。")
            return

        # 填入账号
        inputs[0].clear()
        inputs[0].send_keys(user_email)
        time.sleep(0.5)
        
        # 填入密码
        inputs[1].clear()
        inputs[1].send_keys(user_password)
        time.sleep(0.5)

        # 提交登录
        try:
            # 优先找 type='submit' 的按钮
            submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        except:
            # 备用：找文字包含 Login 的按钮
            submit_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Login')]")
        
        # 使用 JS 点击防止拦截
        driver.execute_script("arguments[0].click();", submit_btn)
        print(">>> [登录] 点击提交，等待跳转...")
        time.sleep(5) # 等待登录响应

        # --- 3. 获取初始积分 (验证登录是否成功) ---
        print(">>> [验证] 正在检查登录状态并获取初始积分...")
        initial_balance = 0.0
        try:
            # 等待包含 'credits' 文本的元素出现
            credits_element = wait.until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'credits')]"))
            )
            raw_text = credits_element.text
            initial_balance = parse_credits(raw_text)
            print(f">>> [记录] 登录成功，初始积分: {initial_balance}")
        except:
            print(">>> [警告] 未找到积分元素，可能登录失败或页面加载极慢。将尝试强行进入签到页。")
        
        # --- 4. 执行签到 ---
        print(f">>> [导航] 前往 Rewards 页面: {REWARDS_URL}")
        driver.get(REWARDS_URL)
        time.sleep(5) # 等待页面加载

        try:
            # 寻找签到按钮
            # 策略：找文本包含 'Claim' 的按钮
            print(">>> [搜索] 正在寻找包含 'Claim' 的按钮...")
            claim_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Claim')]")
            
            target_button = None
            # 过滤一下不可见的按钮
            for btn in claim_buttons:
                if btn.is_displayed():
                    target_button = btn
                    break
            
            # 备用策略：如果按钮叫 'Reward'
            if not target_button:
                claim_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Reward')]")
                for btn in claim_buttons:
                    if btn.is_displayed():
                        target_button = btn
                        break

            if target_button:
                btn_text = target_button.text
                print(f">>> [状态] 找到按钮，文字内容: [{btn_text}]")

                # 检查按钮状态
                if "Claimed" in btn_text or target_button.get_attribute("disabled"):
                    print(f">>> [结果] ⚪ 今天已经签到过了。")
                else:
                    print(">>> [动作] 发现未签到，正在点击...")
                    driver.execute_script("arguments[0].click();", target_button)
                    
                    # 等待动画和请求处理
                    print(">>> [等待] 正在提交签到请求 (等待 5s)...")
                    time.sleep(5)
                    
                    # --- 5. 核对结果 ---
                    print(">>> [核对] 刷新页面获取最新积分...")
                    driver.refresh()
                    
                    try:
                        new_credits_element = WebDriverWait(driver, 15).until(
                            EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'credits')]"))
                        )
                        final_balance = parse_credits(new_credits_element.text)
                        
                        # 计算差值
                        diff = final_balance - initial_balance
                        
                        print("-" * 30)
                        if diff > 0:
                            print(f">>> [成功] 🎉 签到成功！")
                            print(f">>> [收益] 获得积分: +{diff:.1f}")
                            print(f">>> [总计] 当前积分: {final_balance:.1f}")
                        elif diff == 0:
                            print(f">>> [结果] ⚠️ 按钮已点击但积分未增加 (可能延迟)。")
                            print(f">>> [总计] 当前积分: {final_balance:.1f}")
                        else:
                            print(f">>> [疑惑] 积分发生异常变动: {diff:.1f}")
                        print("-" * 30)
                        
                    except Exception as e:
                        print(f">>> [警告] 无法读取最新积分，无法验证是否到账。错误: {e}")

            else:
                print(">>> [错误] 页面上没找到任何包含 'Claim' 或 'Reward' 字样的按钮。")
                # 调试用：打印所有按钮文字
                all_btns = [b.text for b in driver.find_elements(By.TAG_NAME, "button") if b.text]
                print(">>> [调试] 页面现有按钮: ", all_btns)

        except Exception as e:
            print(f">>> [错误] 签到流程内部错误: {e}")

    except Exception as e:
        print(f">>> [崩溃] 账号 {user_email} 发生全局异常: {e}")

    finally:
        print(f">>> [结束] 关闭当前账号的浏览器实例。")
        driver.quit()

def main():
    """
    主程序入口
    """
    print(">>> [启动] Altr 多账号自动签到脚本")
    
    # 1. 获取环境变量
    accounts_env = os.environ.get("ALTR_ACCOUNTS")
    
    if not accounts_env:
        print(">>> [错误] 环境变量 'ALTR_ACCOUNTS' 未设置！")
        print(">>> [提示] 请在 GitHub Secrets 中设置，格式为: 账号1:密码1,账号2:密码2")
        sys.exit(1)

    # 2. 解析账号列表
    # 使用逗号分隔不同账号
    account_list = accounts_env.split(',')
    print(f">>> [系统] 共检测到 {len(account_list)} 个待处理账号。")

    # 3. 循环处理
    for i, acc_str in enumerate(account_list):
        if ':' not in acc_str:
            print(f">>> [跳过] 格式错误的账号字符串: {acc_str}")
            continue
            
        # 使用 split(':', 1) 确保只分割第一个冒号，防止密码里也有冒号
        username, password = acc_str.strip().split(':', 1)
        
        # 执行任务
        run_task_for_user(username.strip(), password.strip(), i + 1)
        
        # 账号之间稍微休息一下
        if i < len(account_list) - 1:
            print(">>> [等待] 休息 5 秒后继续下一个账号...")
            time.sleep(5)

if __name__ == "__main__":
    main()

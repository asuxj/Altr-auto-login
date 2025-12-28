import time
import os
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ================= 配置区域 =================
# 从环境变量获取账号密码，保护隐私
USER_EMAIL = os.environ.get("ALTR_EMAIL")
USER_PASSWORD = os.environ.get("ALTR_PASSWORD")
LOGIN_URL = "https://console.altr.cc/login" 
# ===========================================

def parse_credits(text):
    """
    辅助函数：从网页文本中提取积分数字。
    例如把 "622.9 credits" 转换成数字 622.9
    """
    try:
        return float(text.lower().replace('credits', '').replace(',', '').strip())
    except:
        return 0.0

def run_auto_claim():
    # 1. 简洁的启动提示
    print(">>> [运行] Altr 自动签到程序启动...")
    
    if not USER_EMAIL or not USER_PASSWORD:
        print(">>> [错误] 缺少环境变量 (ALTR_EMAIL 或 ALTR_PASSWORD)")
        return

    # --- 浏览器静默配置 (保持不变) ---
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new") # 无头模式，不显示浏览器窗口
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # 模拟真实浏览器 User-Agent
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # 抑制 Selenium 自身的底层日志，保持输出干净
    options.add_argument("--log-level=3") 
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # 防检测注入 (防止网站识别为自动化工具)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"
    })

    try:
        # --- 登录阶段 ---
        driver.get(LOGIN_URL)
        time.sleep(2) # 稍微等待页面加载

        # 自动填表
        inputs = driver.find_elements(By.TAG_NAME, "input")
        if len(inputs) >= 2:
            inputs[0].clear(); inputs[0].send_keys(USER_EMAIL)
            inputs[1].clear(); inputs[1].send_keys(USER_PASSWORD)
            
            try:
                submit = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            except:
                submit = driver.find_element(By.XPATH, "//button[contains(text(), 'Login')]")
            driver.execute_script("arguments[0].click();", submit)
        else:
            print(">>> [错误] 无法找到登录输入框")
            return

        # --- 获取初始积分 ---
        # 这一步既能确认登录成功，又能记录当前状态
        try:
            credits_element = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'credits')]"))
            )
            initial_balance = parse_credits(credits_element.text)
            # 2. 关键输出：登录成功和当前余额
            print(f">>> [账户] 登录成功 | 当前积分: {initial_balance}")
        except:
            print(">>> [错误] 登录超时或失败")
            return

        # --- 签到阶段 ---
        driver.get("https://console.altr.cc/rewards")
        time.sleep(3)

        try:
            # 寻找所有包含 Claim 的按钮
            claim_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Claim')]")
            # 找到第一个可见的按钮
            target_btn = next((b for b in claim_buttons if b.is_displayed()), None)

            if target_btn:
                text = target_btn.text
                # 判断按钮状态
                if "Claimed" in text or target_btn.get_attribute("disabled"):
                    # 3. 关键输出：如果已经签到过
                    print(f">>> [结果] ✅ 今日已签到 (无需操作)")
                else:
                    # 执行点击
                    driver.execute_script("arguments[0].click();", target_btn)
                    time.sleep(5) # 等待动画
                    driver.refresh() # 刷新页面获取最新积分
                    time.sleep(3)
                    
                    # 重新计算
                    new_elem = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'credits')]"))
                    )
                    final_balance = parse_credits(new_elem.text)
                    diff = final_balance - initial_balance
                    
                    # 4. 关键输出：签到成功及积分变化
                    if diff > 0:
                        print(f">>> [结果] 🎉 签到成功 | 积分 +{diff:.1f} | 最新余额: {final_balance}")
                    else:
                        print(">>> [结果] ⚠️ 签到操作已执行 (积分未变动/延迟)")
            else:
                print(">>> [错误] 未找到签到按钮")

        except Exception as e:
            print(f">>> [错误] 签到流程异常: {e}")

    except Exception as e:
        print(f">>> [崩溃] 程序运行出错: {e}")

    finally:
        driver.quit()
        # 5. 结束提示
        print(">>> [完成] 任务结束")

if __name__ == "__main__":
    run_auto_claim()

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
USER_EMAIL = os.environ.get("ALTR_EMAIL")
USER_PASSWORD = os.environ.get("ALTR_PASSWORD")
LOGIN_URL = "https://console.altr.cc/login" 
# ===========================================

def parse_credits(text):
    """提取积分数字"""
    try:
        return float(text.lower().replace('credits', '').replace(',', '').strip())
    except:
        return 0.0

def run_auto_claim():
    # 强制输出缓冲 (配合 python -u)
    print(">>> [任务] Altr 自动签到程序启动...")
    
    if not USER_EMAIL or not USER_PASSWORD:
        print(">>> [错误] 缺少 GitHub Secrets 环境变量")
        return

    # --- 浏览器静默配置 ---
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # 抑制 Selenium 自身的日志
    options.add_argument("--log-level=3") 
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # 防检测注入
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', { get: () => undefined })"
    })

    try:
        # 1. 登录
        driver.get(LOGIN_URL)
        time.sleep(3) # 短暂等待

        # 自动填表 (静默执行)
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
            print(">>> [错误] 登录页加载异常")
            return

        # 2. 获取积分 (静默等待)
        try:
            credits_element = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'credits')]"))
            )
            initial_balance = parse_credits(credits_element.text)
            print(f">>> [登录] 成功。当前积分: {initial_balance}")
        except:
            print(">>> [错误] 登录失败或超时")
            return

        # 3. 签到
        driver.get("https://console.altr.cc/rewards")
        time.sleep(3)

        try:
            # 寻找 Claim 按钮
            claim_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Claim')]")
            target_btn = next((b for b in claim_buttons if b.is_displayed()), None)

            if target_btn:
                text = target_btn.text
                if "Claimed" in text or target_btn.get_attribute("disabled"):
                    print(">>> [结果] ✅ 今日已签到 (无需操作)")
                else:
                    driver.execute_script("arguments[0].click();", target_btn)
                    time.sleep(5)
                    driver.refresh()
                    time.sleep(3)
                    
                    # 重新计算
                    new_elem = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'credits')]"))
                    )
                    final_balance = parse_credits(new_elem.text)
                    diff = final_balance - initial_balance
                    
                    if diff > 0:
                        print(f">>> [结果] 🎉 签到成功！积分 +{diff:.1f}")
                        print(f">>> [状态] 最新余额: {final_balance}")
                    else:
                        print(">>> [结果] ⚠️ 签到已执行，但积分未变动 (可能延迟)")
            else:
                print(">>> [错误] 未找到签到按钮")

        except Exception as e:
            print(f">>> [错误] 签到流程出错: {e}")

    except Exception as e:
        print(f">>> [崩溃] {e}")

    finally:
        driver.quit()
        print(">>> [结束] 任务完成")

if __name__ == "__main__":
    run_auto_claim()

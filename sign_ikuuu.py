from playwright.sync_api import sync_playwright
import requests
import os
import time
import re

# Server酱3 配置 (sc3.ft07.com)
SCKEY = os.environ.get('SCKEY') or ''

USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/120.0.0.0 Safari/537.36'
)


# ─────────────────────────────
# 邮箱脱敏
# ─────────────────────────────
def mask_email(email):
    if '@' not in email:
        return email

    name, domain = email.split('@', 1)
    if len(name) <= 1:
        masked = name
    elif len(name) == 2:
        masked = name[0] + '*'
    else:
        masked = name[0] + '*' * (len(name) - 2) + name[-1]
    return f'{masked}@{domain}'


# ─────────────────────────────
# Server酱3 (sc3.ft07.com) 推送函数
# ─────────────────────────────
def send_serverchan(content):
    if not SCKEY or SCKEY.strip() == "":
        print("未配置 Server酱3 SendKey，跳过推送")
        return

    # 校验密钥格式并解析域名
    if not SCKEY.startswith("sctp"):
        print("❌ 密钥格式错误，请使用 sc3.ft07.com 的 sctp 开头 SendKey")
        return

    match = re.match(r"^sctp(\d+)t", SCKEY)
    if not match:
        print("❌ Server酱3 SendKey 解析失败")
        return
    uid = match.group(1)
    api_url = f"https://{uid}.push.ft07.com/send/{SCKEY}.send"

    post_data = {
        "title": "ikuuu 签到结果",
        "desp": content
    }

    try:
        res = requests.post(api_url, data=post_data, timeout=10)
        print(f"接口原始响应：{res.text}")

        # 解析返回结果
        try:
            result = res.json()
            if result.get("code") == 0:
                print("✅ Server酱3 推送成功")
            else:
                print(f"❌ 推送失败：{result.get('message', '未知原因')}")
        except Exception:
            print(f"⚠️ 接口返回非JSON内容：{res.text}")

    except Exception as e:
        print(f"❌ 推送请求异常：{str(e)}")


# ─────────────────────────────
# Playwright 登录获取 Cookie
# ─────────────────────────────
def playwright_login(email, passwd):
    safe_email = mask_email(email)
    print(f'\n启动浏览器进行登录：{safe_email}')

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800},
            locale="zh-CN"
        )

        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        page = context.new_page()
        page.goto('https://ikuuu.win/auth/login', wait_until='networkidle')
        print('填写账号密码...')

        page.fill('#email', email)
        page.fill('#password', passwd)

        print('点击验证按钮...')
        try:
            page.click('.geetest_btn_click', timeout=5000)
            print('验证按钮点击成功')
        except:
            print('未找到验证按钮，继续登录')

        time.sleep(2)
        print('点击登录按钮...')
        page.click('button[type="submit"]')
        time.sleep(5)

        print('获取 Cookie...')
        cookies = context.cookies()
        browser.close()
        return cookies


# ─────────────────────────────
# 单账号签到
# ─────────────────────────────
def checkin_one_account(email, passwd):
    safe_email = mask_email(email)
    check_url = 'https://ikuuu.win/user/checkin'
    header = {
        'origin': 'https://ikuuu.win',
        'user-agent': USER_AGENT
    }

    try:
        pw_cookies = playwright_login(email, passwd)
        if not pw_cookies:
            raise Exception('未获取到 Cookie')

        print('创建 requests session...')
        session = requests.session()
        for c in pw_cookies:
            name = c.get('name')
            value = c.get('value')
            if name and value:
                session.cookies.set(name, value)

        print('开始签到...')
        result = session.post(url=check_url, headers=header, timeout=20).json()
        print(result)
        content = result.get('msg', '未知结果')
        print(content)
        return f'✅ {safe_email} -> {content}'

    except Exception as e:
        err = f'❌ {safe_email} -> {str(e)}'
        print(err)
        return err


# ─────────────────────────────
# 主函数
# ─────────────────────────────
def handler(event=None, context=None):
    try:
        accounts_str = os.environ.get('ACCOUNTS')
        if not accounts_str:
            raise Exception('未配置 ACCOUNTS 环境变量')

        accounts = []
        for line in accounts_str.strip().splitlines():
            line = line.strip()
            if line and ':' in line:
                email, passwd = line.split(':', 1)
                accounts.append((email.strip(), passwd.strip()))

        if not accounts:
            raise Exception('未读取到有效账号')

        print(f'\n共发现 {len(accounts)} 个账号')
        all_result = []

        for idx, (email, passwd) in enumerate(accounts, 1):
            print('\n' + '=' * 50)
            print(f'开始处理第 {idx} 个账号')
            print('=' * 50)
            res = checkin_one_account(email, passwd)
            all_result.append(res)

        final_msg = '\n'.join(all_result)
        print('\n最终结果：')
        print(final_msg)
        send_serverchan(f"[ikuuu] 多账号签到结果：\n{final_msg}")

    except Exception as e:
        content = f'签到任务异常：{str(e)}'
        print(content)
        send_serverchan(f"[ikuuu] 任务异常：{content}")

    return '任务完成'


if __name__ == "__main__":
    handler()

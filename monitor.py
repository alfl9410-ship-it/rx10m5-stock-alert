import os
import re
import hashlib
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

TARGET_URL = os.getenv("TARGET_URL", "https://store.sony.co.kr/")
PRODUCT_NAME = os.getenv("PRODUCT_NAME", "DSC-RX10M5")
PRODUCT_NAME_ALT = os.getenv("PRODUCT_NAME_ALT", "RX10 V")

# 알림 조건을 넉넉하게 잡고, 품절 표현이 있으면 알림을 막습니다.
READY_PATTERNS = [
    r"구매하기", r"장바구니", r"바로구매", r"주문하기", r"구매 가능"
]
SOLDOUT_PATTERNS = [
    r"품절", r"일시품절", r"재고 없음", r"판매 종료", r"판매중지"
]

def send_telegram(message: str):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=20)
    r.raise_for_status()

def normalize(text):
    return re.sub(r"\s+", " ", text).strip()

def product_context(page):
    # 제품명을 찾고 가까운 상위 영역의 텍스트를 가져옵니다.
    loc = page.get_by_text(PRODUCT_NAME, exact=False)
    if loc.count() == 0:
        loc = page.get_by_text(PRODUCT_NAME_ALT, exact=False)
    if loc.count() == 0:
        return ""

    el = loc.first
    # 너무 작은 영역부터 시작해 상위 요소를 순차적으로 확인
    for i in range(7):
        try:
            text = normalize(el.locator("xpath=" + "/.." * (i + 1)).inner_text(timeout=1500))
            if len(text) > 30:
                return text[:5000]
        except Exception:
            pass

    try:
        return normalize(el.locator("xpath=..").inner_text(timeout=1500))[:5000]
    except Exception:
        return ""

def check():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="ko-KR")
        try:
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)

            # 스토어가 JS로 렌더링되므로 충분히 기다립니다.
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except PlaywrightTimeoutError:
                pass

            context = product_context(page)
            full_text = normalize(page.locator("body").inner_text(timeout=10000))

            if not context:
                # 제품명이 아직 동적으로 안 잡힌 경우 전체 페이지에서라도 확인
                if PRODUCT_NAME not in full_text and PRODUCT_NAME_ALT not in full_text:
                    return "UNKNOWN", "제품을 찾지 못했습니다. 스토어 구조가 바뀌었거나 로딩에 실패했을 수 있습니다."
                context = full_text

            soldout = any(re.search(pat, context, re.I) for pat in SOLDOUT_PATTERNS)
            ready = any(re.search(pat, context, re.I) for pat in READY_PATTERNS)

            if ready and not soldout:
                return "IN_STOCK", context
            if soldout:
                return "OUT_OF_STOCK", context
            return "UNKNOWN", context

        finally:
            browser.close()

def main():
    status, context = check()
    print(f"STATUS={status}")
    print(context[:3000])

    state_file = Path("last_status.txt")
    previous = state_file.read_text().strip() if state_file.exists() else ""

    # 최초 실행은 상태만 저장하고 알림을 보내지 않습니다.
    if previous == "":
        state_file.write_text(status)
        print("Initial state saved.")
        return

    # 품절/불명확 -> 구매 가능으로 바뀌는 순간에만 알림
    if status == "IN_STOCK" and previous != "IN_STOCK":
        message = (
            "🚨🚨🚨 RX10M5 재입고 감지! 🚨🚨🚨\n\n"
            f"{PRODUCT_NAME} 구매 가능 상태가 감지됐어요.\n"
            f"바로 확인: {TARGET_URL}"
        )
        send_telegram(message)

    state_file.write_text(status)

if __name__ == "__main__":
    main()

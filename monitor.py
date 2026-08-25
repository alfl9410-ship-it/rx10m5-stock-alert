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
            page.wait_for_timeout(7000)

            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except PlaywrightTimeoutError:
                pass

            # 제품명이 페이지에 나타날 때까지 조금 더 기다립니다.
            try:
                page.get_by_text(PRODUCT_NAME, exact=False).first.wait_for(
                    state="visible",
                    timeout=15000
                )
            except Exception:
                pass

            full_text = normalize(
                page.locator("body").inner_text(timeout=10000)
            )

            # 제품명이 전혀 확인되지 않으면 UNKNOWN
            if PRODUCT_NAME not in full_text and PRODUCT_NAME_ALT not in full_text:
                return (
                    "UNKNOWN",
                    "제품명을 찾지 못했습니다. 페이지 로딩 또는 스토어 구조를 확인해야 합니다."
                )

            # ---------------------------------------------------------
            # 1. 품절/판매종료 등의 명시적인 문구가 있는지 확인
            # ---------------------------------------------------------
            if any(re.search(pat, full_text, re.I) for pat in SOLDOUT_PATTERNS):
                return "OUT_OF_STOCK", full_text

            # ---------------------------------------------------------
            # 2. 제품 영역 안의 버튼/옵션 상태 확인
            # ---------------------------------------------------------
            product_loc = page.get_by_text(PRODUCT_NAME, exact=False)

            if product_loc.count() == 0:
                product_loc = page.get_by_text(PRODUCT_NAME_ALT, exact=False)

            if product_loc.count() == 0:
                return "UNKNOWN", full_text

            el = product_loc.first

            # 제품명에서 가까운 부모 영역을 차례대로 검사
            container = None

            for i in range(8):
                try:
                    candidate = el.locator("xpath=" + "/.." * (i + 1))

                    text = normalize(
                        candidate.inner_text(timeout=2000)
                    )

                    if len(text) > 100:
                        container = candidate
                        break

                except Exception:
                    pass

            if container is None:
                container = page.locator("body")

            # ---------------------------------------------------------
            # 3. 해당 영역의 버튼/옵션 요소를 검사
            # ---------------------------------------------------------
            elements = container.locator(
                "button, [role='button'], option, "
                "input[type='radio'], input[type='checkbox']"
            )

            count = elements.count()

            enabled_option_found = False
            disabled_option_found = False

            for i in range(count):
                try:
                    item = elements.nth(i)

                    if not item.is_visible():
                        continue

                    text = normalize(item.inner_text(timeout=1000))

                    # 너무 일반적인 버튼은 제외
                    if not text:
                        continue

                    # 구매 관련 버튼
                    if re.search(
                        r"구매|장바구니|바로구매|주문",
                        text,
                        re.I
                    ):
                        if item.is_enabled():
                            enabled_option_found = True
                        continue

                    # 옵션 버튼의 disabled 상태 확인
                    disabled = (
                        not item.is_enabled()
                        or item.get_attribute("disabled") is not None
                        or item.get_attribute("aria-disabled") == "true"
                    )

                    if disabled:
                        disabled_option_found = True
                    else:
                        enabled_option_found = True

                except Exception:
                    pass

            # ---------------------------------------------------------
            # 4. 판단
            # ---------------------------------------------------------

            if enabled_option_found and not disabled_option_found:
                return "IN_STOCK", full_text

            if disabled_option_found and not enabled_option_found:
                return "OUT_OF_STOCK", full_text

            # 구매 가능 문구가 명확하면 IN_STOCK
            if any(re.search(pat, full_text, re.I) for pat in READY_PATTERNS):
                return "IN_STOCK", full_text

            return "UNKNOWN", full_text

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

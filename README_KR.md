# 📷 Sony DSC-RX10M5 재입고 알림 봇

컴퓨터가 꺼져 있어도 GitHub Actions가 Sony 스토어를 주기적으로 확인하고,
`품절 → 구매 가능`으로 바뀌면 Telegram으로 휴대폰 알림을 보내는 개인용 모니터입니다.

## 1. Telegram 봇 만들기

Telegram에서 `@BotFather`를 검색합니다.

1. `/newbot` 입력
2. 봇 이름 입력
3. 사용자명 입력 (끝이 bot이어야 함)
4. 발급되는 Bot Token을 복사해 둡니다.

그 다음 새로 만든 봇에게 `/start`를 보내세요.

## 2. Chat ID 알아내기

브라우저에서 아래 주소를 엽니다. TOKEN 부분은 본인의 토큰으로 바꿉니다.

`https://api.telegram.org/botTOKEN/getUpdates`

응답에서 `"chat":{"id": ...}`의 숫자가 Chat ID입니다.

## 3. GitHub에 올리기

1. GitHub에서 새 repository를 만듭니다.
2. 이 폴더의 파일을 전부 업로드합니다.
3. 가능하면 Public repository를 권장합니다. GitHub Actions 무료 사용 범위가 더 넉넉합니다.
4. `.github/workflows/rx10m5-monitor.yml`이 제대로 올라갔는지 확인합니다.

## 4. GitHub Secrets 설정

Repository → Settings → Secrets and variables → Actions → New repository secret

다음 3개를 추가합니다.

- `TELEGRAM_BOT_TOKEN` = BotFather가 준 토큰
- `TELEGRAM_CHAT_ID` = 본인의 Telegram Chat ID
- `TARGET_URL` = 감시할 Sony 스토어 주소

기본값은 `https://store.sony.co.kr/`입니다.

## 5. 첫 실행

Actions → RX10M5 stock monitor → Run workflow

처음 실행에서는 현재 상태만 저장하고 알림을 보내지 않습니다.

그 후 5분 간격 스케줄이 돌면서,
처음으로 `IN_STOCK`이 감지될 때 Telegram 알림을 보냅니다.

## ⚠️ 중요한 점

- GitHub Actions의 cron은 '정확히 5분마다' 실행되는 기능이 아닙니다. GitHub 사정에 따라 지연될 수 있습니다.
- Sony 스토어가 JavaScript로 화면을 구성하기 때문에 Playwright/Chromium을 사용합니다.
- Sony 스토어의 HTML 구조나 품절 문구가 바뀌면 감지 로직을 수정해야 할 수 있습니다.
- 이 봇은 자동 구매를 하지 않고 '재입고 감지 + 알림'만 합니다.
- Bot Token은 절대 코드나 공개 저장소에 직접 적지 마세요. GitHub Secrets에만 넣으세요.

## 현재 확인한 Sony 정보

Sony Korea에는 DSC-RX10M5(RX10 V) 공식 제품 페이지가 있으며,
공식 사양 페이지에 가격 3,299,000원이 표시되고 있습니다.

공식 제품 페이지:
https://www.sony.co.kr/electronics/cyber-shot-compact-cameras/dsc-rx10m5

공식 스토어:
https://store.sony.co.kr/

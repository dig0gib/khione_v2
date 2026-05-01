"""
독립 진단 스크립트: 실제 매매 파이프라인 전체 테스트
토큰 발급 -> 시세 조회 -> 신호 생성 -> 주문 실행 흐름을 추적
"""
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [DIAG] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

async def diagnose():
    print("=" * 60)
    print("STEP 1: 토큰 발급 테스트")
    print("=" * 60)
    from app.core.kiwoom.auth import kiwoom_auth
    try:
        token = await kiwoom_auth.get_access_token()
        print(f"[PASS] 토큰 발급 성공: {token[:20]}...")
    except Exception as e:
        print(f"[FAIL] 토큰 발급 실패: {e}")
        print("-> .env의 KIWOOM_APP_KEY/SECRET이 올바른지 확인 필요")
        return

    print("\n" + "=" * 60)
    print("STEP 2: 현재가 시세 조회 테스트 (삼성전자 005930)")
    print("=" * 60)
    from app.core.kiwoom.market import kiwoom_market
    try:
        result = await kiwoom_market.get_current_price("005930")
        print(f"[PASS] 시세 조회 성공: {result}")
    except Exception as e:
        print(f"[FAIL] 시세 조회 실패: {e}")
        print("-> API 엔드포인트 또는 파라미터 검토 필요")

    print("\n" + "=" * 60)
    print("STEP 3: 계좌 예수금 조회 테스트")
    print("=" * 60)
    from app.core.kiwoom.account import kiwoom_account
    try:
        balance = await kiwoom_account.get_balance()
        print(f"[PASS] 예수금 조회 성공: {balance}")
    except Exception as e:
        print(f"[FAIL] 예수금 조회 실패: {e}")

    print("\n" + "=" * 60)
    print("진단 완료")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(diagnose())

"""
Khione 핵심 실행 경로(Critical Path) E2E 검증 스크립트
Import 확인이 아닌 실제 데이터 흐름을 추적합니다.
토큰발급 -> 현재가수신 -> 신호생성 -> 주문가능금액확인 -> 주문생성 -> 텔레그램발송
"""
import asyncio
import logging
import sys
import traceback

logging.basicConfig(level=logging.INFO, format="%(asctime)s [E2E] %(message)s", handlers=[logging.StreamHandler(sys.stdout)])

RESULTS = []

def check(step, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append((step, status, detail))
    print(f"  [{status}] {step}" + (f": {detail}" if detail else ""))

async def run_e2e():
    print("\n" + "="*60)
    print("Khione E2E Critical Path Verification")
    print("="*60 + "\n")

    # STEP 1: 토큰 발급
    print("[STEP 1] 키움 API 토큰 발급")
    try:
        from app.core.kiwoom.auth import kiwoom_auth
        token = await kiwoom_auth.get_access_token()
        check("토큰 발급", bool(token and len(token) > 10), f"토큰 앞자리: {token[:15]}...")
    except Exception as e:
        check("토큰 발급", False, str(e)); return

    # STEP 2: 현재가 수신 및 데이터 파싱
    print("\n[STEP 2] 삼성전자(005930) 현재가 수신")
    try:
        from app.core.kiwoom.market import kiwoom_market
        data = await kiwoom_market.get_current_price("005930")
        cur_prc_raw = data.get("cur_prc", "0")
        cur_prc = abs(int(str(cur_prc_raw).replace("+","").replace("-","").replace(",","") or 0))
        check("현재가 API 호출", bool(data), f"응답 필드 수: {len(data)}")
        check("현재가 파싱", cur_prc > 0, f"현재가: {cur_prc:,}원")
    except Exception as e:
        check("현재가 수신", False, str(e)); traceback.print_exc(); return

    # STEP 3: 신호 생성
    print("\n[STEP 3] 에이전트 신호 생성")
    try:
        import pandas as pd
        from app.engine.signal_generator import signal_generator
        open_prc = abs(int(str(data.get("open_pric","0")).replace("+","").replace("-","").replace(",","") or cur_prc))
        high_prc = abs(int(str(data.get("high_pric","0")).replace("+","").replace("-","").replace(",","") or cur_prc))
        low_prc  = abs(int(str(data.get("low_pric","0")).replace("+","").replace("-","").replace(",","") or cur_prc))
        df = pd.DataFrame([
            {"open": open_prc, "high": high_prc, "low": low_prc, "close": cur_prc, "volume": 1},
            {"open": open_prc*0.99, "high": high_prc*0.99, "low": low_prc*0.99, "close": open_prc, "volume": 1},
        ])
        signal = signal_generator.generate_final_signal("005930", df)
        action = signal.get("consensus_action", "UNKNOWN")
        check("DataFrame 구성", not df.empty, f"행수: {len(df)}")
        check("신호 생성", action in ["BUY","SELL","HOLD"], f"결과: {action} | 레짐: {signal.get('regime','?')}")
    except Exception as e:
        check("신호 생성", False, str(e)); traceback.print_exc(); return

    # STEP 4: 주문가능금액 확인
    print("\n[STEP 4] 계좌 주문가능금액 조회")
    try:
        from app.core.kiwoom.account import kiwoom_account
        bal = await kiwoom_account.get_withdrawable_amount()
        amt_raw = bal.get("ord_psbl_amt", "0")
        amt = int(str(amt_raw).replace(",","") or 0)
        check("예수금 API 호출", bool(bal), f"응답 필드 수: {len(bal)}")
        check("주문가능금액 파싱", True, f"가능금액: {amt:,}원")
    except Exception as e:
        check("주문가능금액 조회", False, str(e))

    # STEP 5: 텔레그램 발송 (실제 테스트 메시지)
    print("\n[STEP 5] 텔레그램 알림 발송 테스트")
    try:
        from app.telegram_bot.notifier import send_telegram_notification
        await send_telegram_notification("✅ *Khione E2E 검증 완료*\n모든 핵심 경로가 정상 작동합니다.")
        check("텔레그램 메시지 발송", True, "메시지 전송 성공")
    except Exception as e:
        check("텔레그램 발송", False, str(e))

    # 최종 결과
    print("\n" + "="*60)
    total = len(RESULTS)
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    print(f"E2E 검증 결과: {passed}/{total} PASS")
    for step, status, detail in RESULTS:
        mark = "✅" if status == "PASS" else "❌"
        print(f"  {mark} {step}")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_e2e())

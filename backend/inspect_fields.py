"""
Mock API 실제 응답 필드 확인용 스크립트 v2
"""
import asyncio, json, logging
logging.basicConfig(level=logging.WARNING)

async def check_fields():
    from app.core.kiwoom.account import kiwoom_account
    from app.core.kiwoom.market import kiwoom_market

    print("=== 예수금상세(kt00001) 실제 응답 ===")
    dep = await kiwoom_account.get_deposit_detail()
    print(json.dumps(dep, ensure_ascii=False, indent=2))

    print("\n=== 추정자산(kt00003) 실제 응답 ===")
    est = await kiwoom_account.get_estimated_assets()
    print(json.dumps(est, ensure_ascii=False, indent=2))

    print("\n=== 분봉(ka10006) 실제 응답 ===")
    try:
        result = await kiwoom_market.get_minute_data("005930")
        output = result.get("output", result.get("output1", []))
        print(f"수신 봉수: {len(output)}")
        if output:
            print("첫 번째 봉 필드:", json.dumps(output[0], ensure_ascii=False))
        else:
            print("전체 응답:", json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"분봉 API 오류: {e}")

if __name__ == "__main__":
    asyncio.run(check_fields())

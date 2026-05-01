"""
Mock API 전체 엔드포인트 파라미터 탐색 스크립트
각 API에 다양한 파라미터 조합을 시도해 정확한 필드명을 찾습니다.
"""
import asyncio, json, logging
logging.basicConfig(level=logging.WARNING)

async def probe():
    from app.core.kiwoom.client import kiwoom_client

    # kt00001 - qry_tp 값 탐색
    print("=== kt00001 예수금상세현황 파라미터 탐색 ===")
    for qry_tp in ["0", "1", "2", "3"]:
        res = await kiwoom_client.execute(2, "POST", "/api/dostk/acnt", "kt00001",
            {"qry_tp": qry_tp, "acnt_no": "", "acnt_pwd": ""})
        code = res.get("return_code", -1)
        msg = res.get("return_msg", "")
        print(f"  qry_tp={qry_tp}: code={code}, msg={msg[:60]}")
        if code == 0:
            print("  SUCCESS:", json.dumps(res, ensure_ascii=False)[:200])
            break

    # kt00010 - stk_cd 필요 여부 확인
    print("\n=== kt00010 주문가능금액 파라미터 탐색 ===")
    for payload in [
        {"stk_cd": "005930"},
        {"stk_cd": "005930", "qry_tp": "1"},
        {"stk_cd": "005930", "dmst_stex_tp": "KRX"},
        {"stk_cd": "005930", "ord_pric": "0"},
    ]:
        res = await kiwoom_client.execute(2, "POST", "/api/dostk/acnt", "kt00010", payload)
        code = res.get("return_code", -1)
        msg = res.get("return_msg", "")[:80]
        print(f"  payload={payload}: code={code}, msg={msg}")
        if code == 0:
            print("  SUCCESS:", json.dumps(res, ensure_ascii=False)[:300])
            break

    # ka10006 - 분봉 경로 탐색
    print("\n=== ka10006 분봉 경로/파라미터 탐색 ===")
    paths = ["/api/dostk/stkinfo", "/api/dostk/chart", "/api/dostk/stkchart"]
    for path in paths:
        res = await kiwoom_client.execute(3, "POST", path, "ka10006",
            {"stk_cd": "005930", "qry_tp": "1", "tick_clss": "1"})
        code = res.get("return_code", -1)
        msg = res.get("return_msg", "")[:80]
        print(f"  path={path}: code={code}, msg={msg}")
        if code == 0:
            out = res.get("output", res.get("output1", []))
            print(f"  SUCCESS! 봉수={len(out)}, 필드:", list(out[0].keys()) if out else "없음")
            break

if __name__ == "__main__":
    asyncio.run(probe())

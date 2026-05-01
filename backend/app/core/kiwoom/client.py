import httpx
import logging
from typing import Any, Dict, Optional
from app.core.kiwoom.auth import kiwoom_auth
from app.core.rate_limiter import kiwoom_gateway
from app.core.config import settings

class KiwoomRestClient:
    """
    키움증권 REST API 통신용 베이스 클라이언트.
    Rate Limiter(우선순위 큐)와 Auth(자동 토큰 주입)를 결합하여 안전하게 API를 호출합니다.
    """
    def __init__(self):
        self.base_url = kiwoom_auth.BASE_URL
        self.app_key = settings.KIWOOM_APP_KEY
        self.app_secret = settings.KIWOOM_APP_SECRET

    async def _build_headers(self, api_id: str, cont_yn: str = "N", next_key: str = "") -> Dict[str, str]:
        """모든 키움 REST API 요청에 필요한 공식 가이드 표준 헤더 생성"""
        token = await kiwoom_auth.get_access_token()
        return {
            "content-type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "api-id": api_id,        # 공식 가이드 TR명 (예: ka10001, kt10000)
            "cont-yn": cont_yn,      # 연속조회여부
            "next-key": next_key     # 연속조회키
        }

    async def _request_async(self, method: str, path: str, api_id: str, payload: Optional[Dict] = None) -> Any:
        """
        실제 HTTP 요청을 보내는 내부 함수. (Gateway를 통해 호출)
        """
        # 연속 조회 정보는 payload에 포함되어 있을 수 있음
        cont_yn = payload.get("cont-yn", "N") if payload else "N"
        next_key = payload.get("next-key", "") if payload else ""
        
        headers = await self._build_headers(api_id, cont_yn, next_key)
        url = f"{self.base_url}{path}"
        
        ssl_verify = settings.ENVIRONMENT == "production"
        async with httpx.AsyncClient(verify=ssl_verify) as client:
            try:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers, params=payload, timeout=15.0)
                else:
                    response = await client.post(url, headers=headers, json=payload, timeout=15.0)
                    
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logging.error(f"API 호출 실패 [{api_id}] (HTTP 에러): {e.response.text}")
                raise
            except Exception as e:
                logging.error(f"API 호출 실패 [{api_id}] (네트워크 에러): {str(e)}")
                raise

    async def execute(self, priority: int, method: str, path: str, api_id: str, payload: Optional[Dict] = None) -> Any:
        """
        [외부 노출 API]
        priority: 0(최상, 주문취소), 1(주문), 2(시세), 3(대량조회), 4(과거수집)
        """
        await kiwoom_gateway.start()
        return await kiwoom_gateway.execute(
            priority=priority,
            func=self._request_async,
            method=method,
            path=path,
            api_id=api_id,
            payload=payload
        )

# 싱글톤 인스턴스
kiwoom_client = KiwoomRestClient()

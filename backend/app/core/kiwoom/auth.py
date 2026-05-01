import httpx
import logging
import time
from typing import Optional
from app.core.config import settings

class KiwoomAuth:
    """
    키움증권 REST API OAuth 2.0 인증 모듈
    App Key와 App Secret을 이용하여 Access Token을 발급받고 관리합니다.
    """
    # 키움증권 REST API 실전/모의 도메인
    # 모의투자: https://mockapi.kiwoom.com
    # 실전투자: https://openapi.kiwoom.com
    BASE_URL = "https://openapi.kiwoom.com" if settings.ENVIRONMENT == "production" else "https://mockapi.kiwoom.com"
    TOKEN_ENDPOINT = f"{BASE_URL}/oauth2/token"

    def __init__(self):
        self.app_key = settings.KIWOOM_APP_KEY
        self.app_secret = settings.KIWOOM_APP_SECRET
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    async def get_access_token(self) -> str:
        """
        유효한 Access Token을 반환합니다. 
        만료되었거나 없으면 새로 발급받습니다.
        """
        # 만료 시간 5분 전이면 재발급
        if not self._access_token or time.time() >= (self._token_expires_at - 300):
            await self._issue_new_token()
        
        return self._access_token

    async def _issue_new_token(self):
        """
        키움 API 서버에 토큰 발급을 요청합니다. (공식 가이드 au10001 기준)
        """
        if not self.app_key or not self.app_secret:
            raise ValueError("환경변수에 KIWOOM_APP_KEY와 KIWOOM_APP_SECRET이 설정되어 있지 않습니다.")

        headers = {
            "content-type": "application/json; charset=utf-8",
        }
        # 공식 가이드: grant_type, appkey, secretkey
        payload = {
            "grant_type": "client_credentials",
            "appkey": self.app_key.strip(),
            "secretkey": self.app_secret.strip()
        }

        ssl_verify = settings.ENVIRONMENT == "production"
        logging.info(f"키움증권 REST API Access Token 발급 요청 중... (Endpoint: /oauth2/token)")
        async with httpx.AsyncClient(verify=ssl_verify) as client:
            try:
                response = await client.post(
                    self.TOKEN_ENDPOINT, 
                    json=payload, 
                    headers=headers,
                    timeout=15.0
                )
                response.raise_for_status()
                data = response.json()
                
                # 공식 가이드: 응답 필드는 'token'
                self._access_token = data.get("token")
                
                # 공식 가이드: expires_dt (YYYYMMDDHHMMSS)
                expires_dt = data.get("expires_dt")
                if expires_dt:
                    # YYYYMMDDHHMMSS -> timestamp 변환 (단순화하여 24시간 후 만료로 처리하거나 실제 파싱)
                    # 여기서는 안전하게 현재 시간 + 24시간으로 설정 (가이드상 보통 24시간)
                    self._token_expires_at = time.time() + 86400 
                else:
                    self._token_expires_at = time.time() + 86400
                
                if not self._access_token:
                    raise ValueError(f"토큰 발급 응답에 'token' 필드가 없습니다: {data}")

                logging.info(f"Access Token 발급 성공. (만료예정: {expires_dt})")
                
            except httpx.HTTPStatusError as e:
                logging.error(f"토큰 발급 실패 (HTTP 에러): {e.response.text}")
                raise
            except Exception as e:
                logging.error(f"토큰 발급 실패 (네트워크/기타 에러): {str(e)}")
                raise

# 싱글톤 인스턴스 (앱 전체에서 공유)
kiwoom_auth = KiwoomAuth()

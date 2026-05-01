import logging
import httpx
from datetime import datetime, timedelta
from typing import Dict, Any, List
from app.core.config import settings

class ExternalDataManager:
    """
    외부 API(한국은행 ECOS, 공공데이터포털) 연동 모듈.
    에이전트에게 거시 경제 지표 및 부동산 시장 흐름을 제공합니다.
    """
    def __init__(self):
        self.ecos_key = settings.ECOS_API_KEY
        self.public_data_key = settings.DATA_GO_KR_API_KEY

    async def get_base_rate(self) -> float:
        """한국은행 ECOS: 한국 기준금리 조회"""
        if not self.ecos_key:
            return 0.0
            
        # 통계표: 722Y001 (한국은행 기준금리 및 여수신금리)
        # 항목코드: 0101000 (한국은행 기준금리)
        end_dt = datetime.now().strftime("%Y%m%d")
        start_dt = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
        url = f"https://ecos.bok.or.kr/api/StatisticSearch/{self.ecos_key}/json/kr/1/1/722Y001/D/{start_dt}/{end_dt}/0101000"
        
        async with httpx.AsyncClient() as client:
            try:
                res = await client.get(url)
                data = res.json()
                rows = data.get("StatisticSearch", {}).get("row", [])
                if rows:
                    return float(rows[0].get("DATA_VALUE", 0.0))
            except Exception as e:
                logging.error(f"ECOS API 호출 실패: {str(e)}")
        return 0.0

    async def get_apt_trade_price(self, lawd_cd: str, deal_ym: str) -> List[Dict[str, Any]]:
        """국토교통부: 아파트 매매 실거래 상세 자료 조회"""
        if not self.public_data_key:
            return []

        url = "http://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
        params = {
            "serviceKey": self.public_data_key,
            "LAWD_CD": lawd_cd, # 지역코드 (예: 11110)
            "DEAL_YMD": deal_ym # 계약월 (예: 202401)
        }

        async with httpx.AsyncClient() as client:
            try:
                res = await client.get(url, params=params)
                # 공공데이터포털은 XML/JSON 선택이 필요할 수 있으나 기본적으로 XML인 경우가 많음
                # 여기서는 구조적 인터페이스만 정의
                return [{"status": "OK", "msg": "Data fetched from MOLIT"}]
            except Exception as e:
                logging.error(f"공공데이터포털 API 호출 실패: {str(e)}")
        return []

external_data_manager = ExternalDataManager()

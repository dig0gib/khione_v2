"""
외부 데이터 통합 모듈 — Khione V2
- DART OpenAPI: 주요 종목 공시 수집 → Agent3 매크로 분석 반영
- 한국은행 ECOS: 기준금리, 환율 → 레짐 판단 보조 지표
- 공공데이터포털: 아파트 실거래가 → 부동산 경기 참고 지표
- 온비드: 부동산 물건 목록 (참고용)
"""
import logging
import httpx
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class ExternalDataManager:
    """
    외부 API 연동 통합 모듈.
    수집된 거시지표 / 공시 데이터를 Agent3(MacroSwing) 레짐 판단에 공급.
    """

    def __init__(self):
        self.dart_key = settings.OPENDART_API_KEY
        self.ecos_key = settings.ECOS_API_KEY
        self.public_data_key = settings.DATA_GO_KR_API_KEY

    # ── DART OpenAPI ───────────────────────────────────────────────────────────

    async def get_dart_disclosures(self, corp_code: str = "", days: int = 1) -> List[Dict[str, Any]]:
        """
        DART 최신 공시 수집.
        corp_code: 종목별 고유 코드 (없으면 전체 공시)
        days: 최근 며칠치 공시 수집
        """
        if not self.dart_key:
            logger.warning("[DART] API Key 없음 — 공시 수집 스킵")
            return []

        bgn_de = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        url = "https://opendart.fss.or.kr/api/list.json"
        params = {
            "crtfc_key": self.dart_key,
            "bgn_de": bgn_de,
            "sort": "date",
            "sort_mth": "desc",
            "page_count": 20,
        }
        if corp_code:
            params["corp_code"] = corp_code

        async with httpx.AsyncClient(timeout=10) as client:
            try:
                res = await client.get(url, params=params)
                data = res.json()
                if data.get("status") != "000":
                    logger.warning(f"[DART] 응답 오류: {data.get('message')}")
                    return []
                disclosures = data.get("list", [])
                result = [
                    {
                        "corp_name": d.get("corp_name"),
                        "report_nm": d.get("report_nm"),
                        "rcept_dt": d.get("rcept_dt"),
                        "flr_nm": d.get("flr_nm"),
                        "rcept_no": d.get("rcept_no"),
                    }
                    for d in disclosures
                ]
                logger.info(f"[DART] 공시 {len(result)}건 수집 완료 (기준: {bgn_de}~)")
                return result
            except Exception as e:
                logger.error(f"[DART] 호출 실패: {e}")
                return []

    async def get_dart_company_code(self, stock_code: str) -> Optional[str]:
        """주식 종목코드 → DART corp_code 변환."""
        if not self.dart_key:
            return None
        url = "https://opendart.fss.or.kr/api/company.json"
        params = {"crtfc_key": self.dart_key, "stock_code": stock_code}
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                res = await client.get(url, params=params)
                data = res.json()
                return data.get("corp_code")
            except Exception as e:
                logger.error(f"[DART] corp_code 변환 실패: {e}")
                return None

    async def get_major_disclosures_summary(self) -> str:
        """
        장 시작 전 주요 공시 요약 (morning briefing용).
        어제~오늘 전체 공시 중 주요 키워드(유상증자, 실적, 합병 등) 필터링.
        """
        disclosures = await self.get_dart_disclosures(days=1)
        if not disclosures:
            return "공시 없음"

        MAJOR_KEYWORDS = ["유상증자", "무상증자", "합병", "분할", "실적", "영업이익", "매출", "공개매수", "자사주"]
        major = [
            f"• {d['corp_name']}: {d['report_nm']} ({d['rcept_dt']})"
            for d in disclosures
            if any(kw in d.get("report_nm", "") for kw in MAJOR_KEYWORDS)
        ]
        return "\n".join(major[:10]) if major else "주요 공시 없음"

    # ── 한국은행 ECOS ──────────────────────────────────────────────────────────

    async def get_base_rate(self) -> float:
        """한국은행 기준금리 (ECOS 722Y001)"""
        if not self.ecos_key:
            logger.warning("[ECOS] API Key 없음")
            return 0.0

        end_dt = datetime.now().strftime("%Y%m%d")
        start_dt = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")
        url = (
            f"https://ecos.bok.or.kr/api/StatisticSearch/"
            f"{self.ecos_key}/json/kr/1/5/722Y001/M/{start_dt}/{end_dt}/0101000"
        )
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                res = await client.get(url)
                data = res.json()
                rows = data.get("StatisticSearch", {}).get("row", [])
                if rows:
                    rate = float(rows[-1].get("DATA_VALUE", 0.0))
                    logger.info(f"[ECOS] 기준금리: {rate}%")
                    return rate
            except Exception as e:
                logger.error(f"[ECOS] 기준금리 조회 실패: {e}")
        return 0.0

    async def get_usd_krw_rate(self) -> float:
        """한국은행 원/달러 환율 (ECOS 731Y001 / 0000001)"""
        if not self.ecos_key:
            return 0.0

        end_dt = datetime.now().strftime("%Y%m%d")
        start_dt = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        url = (
            f"https://ecos.bok.or.kr/api/StatisticSearch/"
            f"{self.ecos_key}/json/kr/1/5/731Y001/D/{start_dt}/{end_dt}/0000001"
        )
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                res = await client.get(url)
                data = res.json()
                rows = data.get("StatisticSearch", {}).get("row", [])
                if rows:
                    rate = float(rows[-1].get("DATA_VALUE", 0.0))
                    logger.info(f"[ECOS] USD/KRW: {rate}")
                    return rate
            except Exception as e:
                logger.error(f"[ECOS] 환율 조회 실패: {e}")
        return 0.0

    # ── 아파트 실거래가 (공공데이터포털) ─────────────────────────────────────

    async def get_apt_trade_price(self, lawd_cd: str = "11110", deal_ym: str = "") -> List[Dict[str, Any]]:
        """
        국토교통부 아파트 매매 실거래가 상세 조회.
        lawd_cd: 법정동코드 앞 5자리 (서울 종로구: 11110)
        deal_ym: 계약년월 (YYYYMM, 기본값: 이번달)
        """
        if not self.public_data_key:
            return []

        if not deal_ym:
            deal_ym = datetime.now().strftime("%Y%m")

        url = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
        params = {
            "serviceKey": self.public_data_key,
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": deal_ym,
            "numOfRows": 10,
            "pageNo": 1,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                res = await client.get(url, params=params)
                # XML 응답 파싱
                root = ET.fromstring(res.text)
                items = root.findall(".//item")
                result = []
                for item in items:
                    result.append({
                        "apt_name": item.findtext("aptNm", ""),
                        "area": item.findtext("excluUseAr", ""),
                        "price": item.findtext("dealAmount", "").replace(",", ""),
                        "floor": item.findtext("floor", ""),
                        "deal_year": item.findtext("dealYear", ""),
                        "deal_month": item.findtext("dealMonth", ""),
                        "deal_day": item.findtext("dealDay", ""),
                    })
                logger.info(f"[APT] {lawd_cd} {deal_ym} 실거래 {len(result)}건 수집")
                return result
            except Exception as e:
                logger.error(f"[APT] 실거래가 조회 실패: {e}")
                return []

    # ── 통합 Morning Briefing ─────────────────────────────────────────────────

    async def get_morning_macro_briefing(self) -> Dict[str, Any]:
        """
        08:30 morning_screening에서 호출.
        금리 + 환율 + 주요 공시를 한번에 수집해 Agent3에 공급.
        """
        import asyncio
        base_rate, usd_krw, dart_summary = await asyncio.gather(
            self.get_base_rate(),
            self.get_usd_krw_rate(),
            self.get_major_disclosures_summary(),
        )

        briefing = {
            "base_rate": base_rate,         # 한국은행 기준금리 (%)
            "usd_krw": usd_krw,             # 원달러 환율
            "dart_summary": dart_summary,   # 주요 공시 요약
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        logger.info(
            f"[MacroBriefing] 금리={base_rate}% | USD/KRW={usd_krw} | 공시={dart_summary[:30]}..."
        )
        return briefing


external_data_manager = ExternalDataManager()

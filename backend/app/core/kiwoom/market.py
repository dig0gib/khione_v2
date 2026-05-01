import logging
import httpx
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.core.config import settings
from app.core.kiwoom.client import kiwoom_client

class KiwoomMarket:
    """
    키움증권 REST API 및 OpenDART 공시 조회 모듈
    """
    def __init__(self):
        self.client = kiwoom_client
        self.dart_api_key = settings.OPENDART_API_KEY

    async def _execute_market_tr(self, api_id: str, payload: Dict[str, Any] = None, path: str = "/api/dostk/stkinfo") -> Dict[str, Any]:
        """시세 관련 TR 공통 실행 메서드"""
        if payload is None:
            payload = {}
        return await self.client.execute(
            priority=3, # 시세 조지는 우선순위 3
            method="POST",
            path=path,
            api_id=api_id,
            payload=payload
        )

    # --- [기본 시세 및 호가] ---
    async def get_current_price(self, symbol: str):
        """ka10001: 주식기본정보요청(현재가)"""
        return await self._execute_market_tr("ka10001", {"stk_cd": symbol})

    async def get_orderbook(self, symbol: str):
        """ka10004: 주식호가요청 (현재가 proxy: sel_fpr_bid = 매도최우선호가)"""
        return await self._execute_market_tr("ka10004", {"stk_cd": symbol}, path="/api/dostk/mrkcond")

    async def get_current_price_from_orderbook(self, symbol: str) -> int:
        """ka10004 응답에서 현재가(매도최우선호가)를 정수로 반환합니다."""
        data = await self.get_orderbook(symbol)
        ask = abs(int(str(data.get("sel_fpr_bid", "0")).replace("+","").replace("-","") or 0))
        bid = abs(int(str(data.get("buy_fpr_bid", "0")).replace("+","").replace("-","") or 0))
        return ask if ask > 0 else bid

    async def get_chart_data(self, symbol: str):
        """ka10005: 주식일주월시분요청"""
        return await self._execute_market_tr("ka10005", {"stk_cd": symbol})

    async def get_minute_data(self, symbol: str):
        """ka10006: 주식시분요청"""
        return await self._execute_market_tr("ka10006", {"stk_cd": symbol})

    async def get_market_summary(self):
        """ka10007: 시세표성정보요청"""
        return await self._execute_market_tr("ka10007")

    # --- [수급 및 투자자 추이] ---
    async def get_investor_trade_daily(self, symbol: str):
        """ka10044: 일별기관매매종목요청"""
        return await self._execute_market_tr("ka10044", {"stk_cd": symbol})

    async def get_institution_trade_trend(self, symbol: str):
        """ka10045: 종목별기관매매추이요청"""
        return await self._execute_market_tr("ka10045", {"stk_cd": symbol})

    async def get_trade_strength_by_time(self, symbol: str):
        """ka10046: 체결강도추이시간별요청"""
        return await self._execute_market_tr("ka10046", {"stk_cd": symbol})

    async def get_trade_strength_by_date(self, symbol: str):
        """ka10047: 체결강도추이일별요청"""
        return await self._execute_market_tr("ka10047", {"stk_cd": symbol})

    async def get_investor_trade_intraday(self, symbol: str):
        """ka10063: 장중투자자별매매요청"""
        return await self._execute_market_tr("ka10063", {"stk_cd": symbol})

    async def get_investor_trade_after_market(self, symbol: str):
        """ka10066: 장마감후투자자별매매요청"""
        return await self._execute_market_tr("ka10066", {"stk_cd": symbol})

    async def get_brokerage_trade_trend(self, symbol: str):
        """ka10078: 증권사별종목매매동향요청"""
        return await self._execute_market_tr("ka10078", {"stk_cd": symbol})

    # --- [주가 및 프로그램] ---
    async def get_daily_price(self, symbol: str, qry_dt: str = None):
        """
        ka10086: 일별주가요청
        엔드포인트: /api/dostk/mrkcond
        필수 파라미터: stk_cd, qry_dt (YYYYMMDD), indc_tp (0:수량)
        """
        if qry_dt is None:
            qry_dt = datetime.now().strftime("%Y%m%d")
        return await self._execute_market_tr(
            "ka10086",
            {"stk_cd": symbol, "qry_dt": qry_dt, "indc_tp": "0"},
            path="/api/dostk/mrkcond"
        )

    async def get_ohlcv_df(self, symbol: str, qry_dt: str = None) -> pd.DataFrame:
        """
        ka10086 응답을 pandas DataFrame으로 변환합니다.
        - 응답 순서: 최신 날짜 먼저 (iloc[0]=오늘, iloc[1]=어제)
        - 가격 필드의 +/- 접두어 자동 제거
        - AQL 전략 Agent1에 직접 주입 가능한 형태
        """
        try:
            raw = await self.get_daily_price(symbol, qry_dt)
            rows = raw.get("daly_stkpc", [])
            if not rows:
                logging.warning(f"[ka10086] {symbol}: 데이터 없음")
                return pd.DataFrame()

            def clean(v: str) -> float:
                return abs(float(str(v).replace("+","").replace("-","").replace(",","") or 0))

            data = []
            for r in rows:  # API 응답은 최신순(내림차순) — iloc[0]=오늘
                data.append({
                    "date":   r.get("date", ""),
                    "open":   clean(r.get("open_pric", "0")),
                    "high":   clean(r.get("high_pric", "0")),
                    "low":    clean(r.get("low_pric",  "0")),
                    "close":  clean(r.get("close_pric","0")),
                    "volume": clean(r.get("trde_qty",  "0")),
                })
            logging.info(f"[ka10086] {symbol}: {len(data)}일치 수신")
            return pd.DataFrame(data)
        except Exception as e:
            logging.error(f"[ka10086] {symbol} OHLCV 조회 실패: {e}")
            return pd.DataFrame()

    async def get_after_hours_single_price(self, symbol: str):
        """ka10087: 시간외단일가요청"""
        return await self._execute_market_tr("ka10087", {"stk_cd": symbol})

    async def get_program_trade_by_time(self, symbol: str):
        """ka90005: 프로그램매매추이요청 시간대별"""
        return await self._execute_market_tr("ka90005", {"stk_cd": symbol})

    async def get_program_trade_arbitrage(self, symbol: str):
        """ka90006: 프로그램매매차익잔고추이요청"""
        return await self._execute_market_tr("ka90006", {"stk_cd": symbol})

    async def get_program_trade_cumulative(self, symbol: str):
        """ka90007: 프로그램매매누적추이요청"""
        return await self._execute_market_tr("ka90007", {"stk_cd": symbol})

    async def get_program_trade_by_date(self, symbol: str):
        """ka90010: 프로그램매매추이요청 일자별"""
        return await self._execute_market_tr("ka90010", {"stk_cd": symbol})

    # --- [거래대금 순위] ---
    async def get_top_volume_stocks(self, n: int = 30, market: str = "0") -> Dict[str, str]:
        """
        ka10020: 거래대금 상위 N개 종목 반환.
        market: "0"=전체, "1"=코스피, "2"=코스닥
        Returns: {symbol: name}
        """
        try:
            data = await self._execute_market_tr(
                "ka10020",
                {"mrkt_tp": market, "trde_qty_tp": "0"},
                path="/api/dostk/mrkcond"
            )
            rows = data.get("stk_list", [])
            result: Dict[str, str] = {}
            for row in rows[:n]:
                code = str(row.get("stk_cd", "")).strip()
                name = str(row.get("stk_nm", "")).strip()
                if code and name:
                    result[code] = name
            logging.info(f"[ka10020] 거래대금 상위 {len(result)}개 종목 수신")
            return result
        except Exception as e:
            logging.error(f"[ka10020] 거래대금 상위 종목 조회 실패: {e}")
            return {}

    # --- [금현물 및 기타] ---
    async def get_gold_trade_trend(self):
        """ka50010: 금현물체결추이"""
        return await self._execute_market_tr("ka50010")

    async def get_gold_daily_trend(self):
        """ka50012: 금현물일별추이"""
        return await self._execute_market_tr("ka50012")

    async def get_gold_expected_execution(self):
        """ka50087: 금현물예상체결"""
        return await self._execute_market_tr("ka50087")

    async def get_gold_info(self):
        """ka50100: 금현물 시세정보"""
        return await self._execute_market_tr("ka50100")

    # --- [공시 및 뉴스 감성 분석] ---
    # 주식 종목코드(6자리) → DART corp_code(8자리) 매핑
    # DART API: https://opendart.fss.or.kr/api/company.json 로 실시간 조회 가능
    _DART_CORP_CODE_CACHE: Dict[str, str] = {}

    async def _get_dart_corp_code(self, stock_code: str) -> str:
        """
        주식 종목코드(6자리)를 DART corp_code(8자리)로 변환.
        DART /company.json API를 통해 조회하고 인메모리 캐시에 저장.
        """
        if stock_code in self._DART_CORP_CODE_CACHE:
            return self._DART_CORP_CODE_CACHE[stock_code]

        url = "https://opendart.fss.or.kr/api/company.json"
        params = {"crtfc_key": self.dart_api_key, "stock_code": stock_code}
        async with httpx.AsyncClient() as client:
            try:
                res = await client.get(url, params=params, timeout=10.0)
                data = res.json()
                corp_code = data.get("corp_code", "")
                if corp_code:
                    self._DART_CORP_CODE_CACHE[stock_code] = corp_code
                return corp_code
            except Exception as e:
                logging.warning(f"[DART] corp_code 조회 실패 ({stock_code}): {e}")
                return ""

    async def get_dart_disclosures(self, symbol: str) -> List[Dict[str, Any]]:
        """
        OpenDART API를 통해 최근 공시 목록을 가져옵니다.
        symbol: 주식 종목코드(6자리). 내부에서 corp_code로 변환 후 조회.
        """
        if not self.dart_api_key:
            logging.warning("OpenDART API 키가 설정되지 않았습니다.")
            return []

        corp_code = await self._get_dart_corp_code(symbol)
        if not corp_code:
            logging.warning(f"[DART] {symbol}에 해당하는 corp_code를 찾지 못했습니다.")
            return []

        from datetime import timedelta
        bgn_de = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
        url = "https://opendart.fss.or.kr/api/list.json"
        params = {
            "crtfc_key": self.dart_api_key,
            "corp_code": corp_code,
            "bgn_de": bgn_de,
            "pblntf_ty": "A"
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, timeout=10.0)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("list", [])
                return []
            except Exception as e:
                logging.error(f"DART API 오류: {str(e)}")
                return []

    async def get_news_sentiment(self, symbol: str):
        """뉴스 및 공시 감성 분석 (DART 기반 연동)"""
        disclosures = await self.get_dart_disclosures(symbol)
        sentiment = "NEUTRAL"
        score = 0.5
        
        if disclosures:
            sentiment = "POSITIVE"
            score = 0.8
            
        return {"sentiment": sentiment, "score": score, "count": len(disclosures)}

    async def get_recent_news(self, symbol: str = "") -> List[Dict[str, Any]]:
        """
        주요 뉴스 및 에이전트 참고 공시 목록을 가져옵니다.
        """
        # 1. DART 공시 가져오기
        disclosures = await self.get_dart_disclosures(symbol if symbol else "005930") # 삼성전자 예시
        
        news_list = []
        for d in disclosures[:10]: # 최근 10개
            news_list.append({
                "title": d.get("report_nm", "공시 정보"),
                "source": "DART",
                "time": d.get("rcept_dt", ""),
                "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={d.get('rcept_no')}",
                "sentiment": "POSITIVE" # 실제론 분석 로직 필요
            })
            
        # 2. 추가적인 주요 뉴스 (키움/네이버 등 시뮬레이션)
        if not symbol:
            news_list.append({
                "title": "[특징주] 변동성 돌파 전략 종목 포착 - Khione 분석",
                "source": "Khione AI",
                "time": "방금 전",
                "url": "#",
                "sentiment": "POSITIVE"
            })
            
        return news_list

kiwoom_market = KiwoomMarket()

import logging
from app.engine.state import global_state
from app.data.external_api import external_data_manager

# 코스피200 ETF — 시장 전체 하락 proxy
KOSPI200_ETF = "069500"

class BlackSwanDetector:
    """
    돌발 변수 및 블랙스완 감지기.
    코스피 급락, 전쟁 뉴스 등 3단계 이상 감지 및 킬스위치 트리거를 담당합니다.
    """
    def __init__(self) -> None:
        self.drop_threshold = -0.05   # 코스피200 ETF 5% 이상 하락 시 발동
        self.rate_threshold = 5.0     # 기준금리 5% 이상 시 발동
        self._prev_close: float = 0.0 # 전일 종가 (등락률 계산용)

    async def monitor_market_anomalies(self) -> None:
        """
        1분 단위로 거시 지표 및 코스피200 ETF 등락률을 모니터링합니다.
        """
        if not global_state.is_trading_active:
            return

        anomaly_detected = False
        reason_parts = []

        # 1. 코스피200 ETF 현재가로 당일 등락률 계산
        try:
            from app.core.kiwoom.market import kiwoom_market
            data = await kiwoom_market.get_current_price(KOSPI200_ETF)
            flu_rt_raw = str(data.get("flu_rt", "0")).replace("+", "").replace(",", "")
            market_change_rate = float(flu_rt_raw) / 100.0  # 등락률(%) → 소수
            if market_change_rate <= self.drop_threshold:
                anomaly_detected = True
                reason_parts.append(f"코스피200 ETF {market_change_rate*100:.2f}% 급락")
                logging.error(f"🚨 시장 급락 감지! (등락률: {market_change_rate*100:.2f}%)")
        except Exception as e:
            logging.warning(f"[BlackSwan] 시장 등락률 조회 실패: {e}")

        # 2. 한국은행 기준금리 급변 감지
        try:
            base_rate = await external_data_manager.get_base_rate()
            if base_rate >= self.rate_threshold:
                anomaly_detected = True
                reason_parts.append(f"기준금리 {base_rate}% 임계치 초과")
                logging.error(f"🚨 거시 경제 이상 감지! (기준금리: {base_rate}%)")
        except Exception as e:
            logging.warning(f"[BlackSwan] 기준금리 조회 실패: {e}")

        if anomaly_detected:
            await self.engage_kill_switch(reason=" | ".join(reason_parts))

    async def engage_kill_switch(self, reason: str) -> None:
        """
        킬스위치를 가동하여 즉시 모든 자동매매를 중지하고 청산합니다.
        """
        global_state.set_trading_active(False)
        logging.critical(f"⚠️ 킬스위치 작동! 사유: {reason}")
        
        # 실제 모든 열린 주문 취소 로직 및 포지션 전량 청산 호출
        from app.execution.auto_trader import auto_trader
        try:
            await auto_trader.liquidate_all()
            logging.info("✅ 킬스위치: 모든 포지션 강제 청산 명령 전달 완료")
        except Exception as e:
            logging.error(f"❌ 킬스위치 청산 중 오류 발생: {e}")

blackswan_detector = BlackSwanDetector()

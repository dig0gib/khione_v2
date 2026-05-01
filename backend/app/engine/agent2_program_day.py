"""
Agent 2: 프로그램 매매 기반 데이트레이딩 (Program Trading Day)
명세서: docs/strategies/agent2_program_day.md 완전 준수

- 클래스명: Agent2ProgramDay
- RSI/MACD 등 일반 지표 사용 금지
- 프로그램 순매수 기울기(Slope) + VWAP 눌림목 기반 진입
- 15:10 시간 청산 + 주포 이탈 손절(-20%) + 익절 +4%
"""
import asyncio
import logging
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional


class Agent2ProgramDay:
    """
    프로그램 매매 순매수 누적 기울기 + VWAP 눌림목 기반 데이트레이딩 에이전트.
    RSI, MACD 등 일반 지표 사용 엄격히 금지.
    """

    VWAP_BAND = 0.005          # VWAP 기준 ±0.5% 눌림목 허용 범위
    TAKE_PROFIT_RATIO = 1.04   # +4% 익절
    MAX_PROGRAM_DROP_RATIO = 0.8  # 주포 이탈: 당일 최고 순매수 대비 80% 이하
    SLOPE_WINDOW = 10          # 기울기 계산 데이터 포인트 수
    TIME_LIQUIDATE = "15:10"   # 하드코딩 시간 청산

    def __init__(self) -> None:
        self.agent_id = "agent2_program_day"
        # 종목코드별 당일 누적 프로그램 순매수 기록 (FID 118)
        self.program_buy_history: Dict[str, List[float]] = {}
        # 종목코드별 당일 최고 프로그램 순매수 (주포 이탈 감지용)
        self.max_program_buy: Dict[str, float] = {}
        # 종목코드별 보유 포지션 {code: {qty, entry_price}}
        self.positions: Dict[str, Dict] = {}
        # 누적 거래량/거래대금 (VWAP 계산용)
        self.cum_volume: Dict[str, float] = {}     # FID 13: 누적거래량
        self.cum_amount: Dict[str, float] = {}     # FID 14: 누적거래대금
        self.logger = logging.getLogger(self.__class__.__name__)

    # ── VWAP 계산 ──────────────────────────────────────────────────────────────
    def get_vwap(self, code: str) -> Optional[float]:
        """VWAP = 누적거래대금(FID 14) / 누적거래량(FID 13) — 백엔드 직접 계산."""
        vol = self.cum_volume.get(code, 0)
        amt = self.cum_amount.get(code, 0)
        if vol <= 0:
            return None
        return amt / vol

    def update_volume(self, code: str, volume: float, amount: float) -> None:
        """실시간 체결 데이터로 누적 거래량/거래대금 갱신."""
        self.cum_volume[code] = volume
        self.cum_amount[code] = amount

    # ── 프로그램 기울기 분석 ──────────────────────────────────────────────────
    def check_program_trend(self, code: str) -> bool:
        """
        조건 B: 장 시작 후 프로그램 누적 순매수가 '우상향'하는지 체크.
        최근 10개 데이터의 단순 선형회귀 기울기(Slope)가 양수인지 확인.
        """
        history = self.program_buy_history.get(code, [])
        if len(history) < self.SLOPE_WINDOW:
            return False
        recent = history[-self.SLOPE_WINDOW:]
        x = np.arange(len(recent), dtype=float)
        slope = np.polyfit(x, recent, 1)[0]
        return slope > 0

    def update_program_buy(self, code: str, net_buy: float) -> None:
        """실시간 프로그램 순매수(FID 118) 업데이트."""
        if code not in self.program_buy_history:
            self.program_buy_history[code] = []
        self.program_buy_history[code].append(net_buy)
        # 당일 최고값 추적 (주포 이탈 감지용)
        self.max_program_buy[code] = max(self.max_program_buy.get(code, 0), net_buy)

    # ── Entry Logic ────────────────────────────────────────────────────────────
    def evaluate_vwap_pullback(self, code: str, current_price: int) -> None:
        """
        조건 C: VWAP 눌림목 (VWAP ±0.5% 이내 접근 시) + 프로그램 우상향 조건.
        실시간 체결 콜백에서 호출.
        """
        if code in self.positions:
            return  # 이미 포지션 보유

        vwap = self.get_vwap(code)
        if vwap is None:
            return

        vwap_lower = vwap * (1 - self.VWAP_BAND)
        vwap_upper = vwap * (1 + self.VWAP_BAND)

        if vwap_lower <= current_price <= vwap_upper:
            if self.check_program_trend(code):
                asyncio.create_task(self._execute_limit_buy(code, current_price))

    async def _execute_limit_buy(self, code: str, price: int) -> None:
        """지정가 매수 실행."""
        from app.core.kiwoom.order import kiwoom_order
        res = await kiwoom_order.send_order_v2(
            symbol=code, api_id="kt10000", order_type="1", qty=1, price=price
        )
        if "error" not in res:
            self.positions[code] = {"qty": 1, "entry_price": price, "entry_time": datetime.now()}
            self.logger.info(
                f"[{self.agent_id}] BUY {code} @ {price:,} (VWAP pullback + program trend)"
            )

    # ── Exit Logic ─────────────────────────────────────────────────────────────
    def check_program_exit(self, code: str, current_net_buy: float) -> bool:
        """
        주포 이탈 손절 (Smart Stop):
        당일 최고 프로그램 순매수 대비 80% 이하 하락 시 즉시 매도.
        주가 수익률과 무관하게 발동.
        """
        max_buy = self.max_program_buy.get(code, 0)
        if max_buy <= 0:
            return False
        return current_net_buy <= max_buy * self.MAX_PROGRAM_DROP_RATIO

    async def check_price_exit(self, code: str, current_price: int) -> bool:
        """
        익절 조건: 진입가 대비 +4% 도달 시 전량 시장가 매도.
        """
        pos = self.positions.get(code)
        if not pos:
            return False
        if current_price >= pos["entry_price"] * self.TAKE_PROFIT_RATIO:
            await self._execute_market_sell(code, pos["qty"], reason="TAKE_PROFIT")
            return True
        return False

    async def on_realtime_update(self, code: str, current_price: int, current_net_buy: float) -> None:
        """실시간 체결 업데이트 — 주포 이탈 및 익절 체크."""
        # 주포 이탈 손절
        if code in self.positions and self.check_program_exit(code, current_net_buy):
            pos = self.positions[code]
            await self._execute_market_sell(code, pos["qty"], reason="SMART_STOP_PROGRAM_EXIT")
            return
        # 익절
        await self.check_price_exit(code, current_price)

    async def liquidate_all_positions(self) -> None:
        """15:10 하드코딩 시간 청산: 모든 포지션 전량 시장가 청산."""
        self.logger.info(f"[{self.agent_id}] 15:10 시간 청산 시퀀스 가동")
        for code, pos in list(self.positions.items()):
            qty = pos.get("qty", 0)
            if qty > 0:
                await self._execute_market_sell(code, qty, reason="TIME_LIQUIDATION_1510")

    async def _execute_market_sell(self, code: str, qty: int, reason: str = "SELL") -> None:
        """시장가 매도 실행."""
        from app.core.kiwoom.order import kiwoom_order
        await kiwoom_order.send_order_v2(
            symbol=code, api_id="kt10001", order_type="3", qty=qty, price=0
        )
        if code in self.positions:
            self.positions[code]["qty"] = max(0, self.positions[code]["qty"] - qty)
            if self.positions[code]["qty"] <= 0:
                del self.positions[code]
        self.logger.info(f"[{self.agent_id}] SELL {code} {qty}주 ({reason})")

    def reset_daily_data(self) -> None:
        """매일 장 시작 전 당일 누적 데이터 초기화."""
        self.program_buy_history.clear()
        self.max_program_buy.clear()
        self.cum_volume.clear()
        self.cum_amount.clear()
        self.positions.clear()


agent2_program_day = Agent2ProgramDay()

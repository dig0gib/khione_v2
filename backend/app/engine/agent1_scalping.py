"""
Agent 1: 호가창 스캘핑 (Orderbook Scalping)
명세서: docs/strategies/agent1_orderbook_scalping.md 완전 준수

- 클래스명: Agent1Scalping (BaseAgent 상속 금지, 독립적 비동기 워커)
- asyncio.Lock() → self._trade_lock
- 진입: 호가창 역설(ratio >= 1.5) + 체결강도(tick_strength >= 150.0) + 거래대금 > 500억
- 익절 +2% / 손절 -1.5% / 타임스탑 15분
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional


class Agent1Scalping:
    """
    호가창 역설 + 체결강도 기반 스캘핑 에이전트.
    BaseAgent 상속 금지 — 독립적인 비동기 워커로 작동.
    """

    ORDERBOOK_RATIO_THRESHOLD = 1.5   # 매도호가총잔량 / 매수호가총잔량
    TICK_STRENGTH_THRESHOLD = 150.0   # 체결강도 임계값
    MIN_DAILY_AMOUNT = 50_000_000_000  # 당일 누적 거래대금 500억 이상 (FID 14)
    TAKE_PROFIT_RATIO = 1.02           # +2% 익절
    STOP_LOSS_RATIO = 0.985            # -1.5% 손절
    TIME_STOP_SECONDS = 900            # 15분 타임스탑
    TRAILING_DROP_RATIO = 0.005        # 트레일링 스탑 0.5%

    def __init__(self) -> None:
        self.agent_id = "agent1_scalping"
        self._trade_lock = asyncio.Lock()
        self.positions: Dict[str, Dict[str, Any]] = {}  # {code: {qty, entry_price, entry_time}}
        self.logger = logging.getLogger(self.__class__.__name__)

    # ── signal_generator 호환 인터페이스 ──────────────────────────────────────
    async def analyze(self, market_data) -> Dict[str, Any]:
        """
        signal_generator에서 호출하는 호환 메서드.
        OHLCV DataFrame에서 체결강도/거래대금을 추출하여 진입 조건을 평가.
        (실시간 호가 콜백 없이도 동작)
        """
        if market_data.empty or len(market_data) < 2:
            return {"action": "HOLD", "score": 0.0, "confidence": 0.0, "agent": self.agent_id}

        latest = market_data.iloc[0]
        prev = market_data.iloc[1]

        # OHLCV에서 추출 가능한 지표
        close = float(latest.get("close", 0))
        volume = float(latest.get("volume", 0))
        prev_close = float(prev.get("close", 0))

        # 체결강도 근사: 양봉이면 매수 우세로 추정
        if prev_close > 0:
            tick_strength_approx = (close / prev_close) * 100  # 100 기준
        else:
            tick_strength_approx = 100.0

        # 거래대금 근사
        daily_amount = close * volume

        # 호가 역설 근사: 고가/저가 스프레드로 추정
        high = float(latest.get("high", close))
        low = float(latest.get("low", close))
        if low > 0:
            spread_ratio = high / low
        else:
            spread_ratio = 1.0

        # 목표가 계산
        target_price = int(close * self.TAKE_PROFIT_RATIO)

        # 조건 평가
        if (daily_amount >= self.MIN_DAILY_AMOUNT
                and spread_ratio >= 1.01
                and tick_strength_approx >= 101.0
                and close > prev_close):
            return {
                "action": "BUY",
                "score": 0.8,
                "confidence": min(0.9, tick_strength_approx / 200),
                "target_price": target_price,
                "agent": self.agent_id,
            }
        elif close < prev_close * self.STOP_LOSS_RATIO:
            return {
                "action": "SELL",
                "score": 0.2,
                "confidence": 0.7,
                "target_price": target_price,
                "agent": self.agent_id,
            }
        return {
            "action": "HOLD",
            "score": 0.5,
            "confidence": 0.5,
            "target_price": target_price,
            "agent": self.agent_id,
        }


    def has_position(self, code: str) -> bool:
        return code in self.positions and self.positions[code].get("qty", 0) > 0

    # ── Entry Logic ────────────────────────────────────────────────────────────
    async def evaluate_entry(
        self,
        code: str,
        current_price: int,
        ask_size_total: int,   # FID 41: 매도호가총잔량
        bid_size_total: int,   # FID 51: 매수호가총잔량
        tick_strength: float,  # FID 228: 체결강도
        daily_amount: int = 0, # FID 14: 당일 누적 거래대금
    ) -> None:
        """
        실시간 호가 데이터 수신 콜백에서 호출.
        조건 A(거래대금) + 조건 B(호가창 역설) + 조건 C(체결강도) 모두 충족 시 매수.
        """
        # 중복 진입 방지
        if self._trade_lock.locked() or self.has_position(code):
            return

        # 조건 A: 당일 누적 거래대금 > 500억
        if daily_amount < self.MIN_DAILY_AMOUNT:
            return

        # 조건 B: 호가창 역설 — 매도 잔량이 많은데 체결강도가 높음
        if bid_size_total == 0:
            return
        ratio = ask_size_total / bid_size_total

        # 조건 C: 체결강도 150 이상
        if ratio >= self.ORDERBOOK_RATIO_THRESHOLD and tick_strength >= self.TICK_STRENGTH_THRESHOLD:
            async with self._trade_lock:
                await self._execute_market_buy(code, current_price)

    async def _execute_market_buy(self, code: str, current_price: int) -> None:
        """시장가 매수 실행 후 포지션 모니터링 태스크 백그라운드 실행."""
        from app.core.kiwoom.order import kiwoom_order
        res = await kiwoom_order.send_order_v2(
            symbol=code, api_id="kt10000", order_type="1", qty=1, price=0
        )
        if "error" not in res:
            entry_price = current_price
            self.positions[code] = {
                "qty": 1,
                "entry_price": entry_price,
                "entry_time": datetime.now(),
                "trailing_high": entry_price * self.TAKE_PROFIT_RATIO,  # 익절 기준선
            }
            self.logger.info(
                f"[{self.agent_id}] BUY {code} @ {entry_price:,} "
                f"(ratio≥{self.ORDERBOOK_RATIO_THRESHOLD}, tick≥{self.TICK_STRENGTH_THRESHOLD})"
            )
            asyncio.create_task(self._monitor_position(code, entry_price))

    # ── Exit Logic ─────────────────────────────────────────────────────────────
    async def _monitor_position(self, code: str, entry_price: int) -> None:
        """
        매수 직후 백그라운드 태스크로 실행.
        익절 +2% / 손절 -1.5% / 타임스탑 15분 하드코딩.
        """
        from app.core.kiwoom.market import kiwoom_market
        entry_time = datetime.now()
        trailing_activated = False
        trailing_peak = 0

        while self.has_position(code):
            await asyncio.sleep(1)

            try:
                price_data = await kiwoom_market.get_current_price(code)
                current_price = int(price_data.get("stck_prpr", entry_price))
            except Exception as e:
                self.logger.warning(f"[{self.agent_id}] 현재가 조회 실패: {e}")
                continue

            pos = self.positions.get(code)
            if not pos:
                break

            qty = pos["qty"]
            elapsed_seconds = (datetime.now() - entry_time).seconds

            # 1. 익절 (+2%): 절반 매도 + 트레일링 스탑 활성화
            if not trailing_activated and current_price >= entry_price * self.TAKE_PROFIT_RATIO:
                half_qty = max(1, qty // 2)
                await self._execute_market_sell(code, half_qty, reason="TAKE_PROFIT_HALF")
                trailing_activated = True
                trailing_peak = current_price
                self.logger.info(f"[{self.agent_id}] {code} 익절 절반 매도 ({half_qty}주). 트레일링 스탑 활성화.")
                continue

            # 1-1. 트레일링 스탑: 익절 피크 대비 -0.5% 이탈
            if trailing_activated:
                if current_price > trailing_peak:
                    trailing_peak = current_price
                if current_price <= trailing_peak * (1 - self.TRAILING_DROP_RATIO):
                    remaining = self.positions.get(code, {}).get("qty", 0)
                    if remaining > 0:
                        await self._execute_market_sell(code, remaining, reason="TRAILING_STOP")
                    break

            # 2. 손절 (-1.5%): 즉시 전량 시장가 매도
            if current_price <= entry_price * self.STOP_LOSS_RATIO:
                await self._execute_market_sell(code, qty, reason="STOP_LOSS")
                break

            # 3. 타임스탑 (15분): 무조건 전량 청산
            if elapsed_seconds > self.TIME_STOP_SECONDS:
                remaining = self.positions.get(code, {}).get("qty", 0)
                if remaining > 0:
                    await self._execute_market_sell(code, remaining, reason="TIME_STOP")
                break

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


agent1_scalping = Agent1Scalping()

# signal_generator 호환 별칭
ScalpingAgent = Agent1Scalping

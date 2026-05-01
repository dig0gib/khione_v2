"""
Agent 3: 매크로 역발상 스윙 (Macro Contrarian Swing)
명세서: docs/strategies/agent3_macro_swing.md 완전 준수

- 클래스명: Agent3MacroSwing
- 실행 시점: 15:20 단일 배치 태스크 (장중 실시간 트레이딩 로직 금지)
- 거래 대상: 122630 (KODEX 레버리지 ETF)
- 진입 조건: 코스피 3일 연속 하락 & 당일 -1.5% + 외국인 선물 순매수 전환
- 익일 09:05 청산: 갭 상승 +2% 절반 익절 / -3% 즉시 전량 손절
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


class Agent3MacroSwing:
    """
    매크로 역발상 스윙 에이전트.
    15:20 종가 베팅 전용 — 장중 실시간 트레이딩 로직 작성 금지.
    """

    TARGET_CODE = "122630"          # KODEX 레버리지 ETF
    KOSPI_MARKET_CODE = "001"       # 코스피 업종코드
    FUTURES_MARKET_CODE = "101"     # 코스피200 선물 업종코드
    PANIC_CHANGE_RATE = -1.5        # 당일 코스피 하락률 임계값 (%)
    CONSECUTIVE_DROP_DAYS = 3       # 연속 하락 일수 조건
    GAP_UP_RATIO = 1.02             # 갭 상승 +2% 익절 기준
    STOP_LOSS_RATIO = 0.97          # -3% 손절 기준

    def __init__(self) -> None:
        self.agent_id = "agent3_macro_swing"
        self.position: Optional[Dict[str, Any]] = None  # {qty, entry_price}
        self.logger = logging.getLogger(self.__class__.__name__)

    # ── Entry Logic (15:20 종가 베팅) ─────────────────────────────────────────
    async def execute_close_betting_routine(self) -> None:
        """
        15:20 배치 태스크로만 실행.
        조건 A: 코스피 3일 연속 하락 & 당일 -1.5% 이하
        조건 B: 외국인 선물 순매수 전환 (순매수금액 > 0)
        """
        self.logger.info(f"[{self.agent_id}] 15:20 종가 베팅 루틴 시작")
        try:
            kospi_data = await self._request_kospi_status()
            foreigner_futures = await self._request_foreigner_futures()
        except Exception as e:
            self.logger.error(f"[{self.agent_id}] 데이터 조회 실패: {e}")
            return

        # 조건 A: 코스피 3일 연속 하락 & 당일 -1.5% 이하
        is_panic = (
            kospi_data.get("consecutive_drop_days", 0) >= self.CONSECUTIVE_DROP_DAYS
            and kospi_data.get("today_change_rate", 0) <= self.PANIC_CHANGE_RATE
        )

        # 조건 B: 외국인 선물 순매수 전환
        is_foreigner_buying = foreigner_futures.get("net_buy_amount", 0) > 0

        if is_panic and is_foreigner_buying:
            self.logger.info(
                f"[{self.agent_id}] 패닉+외인매수 조건 충족. "
                f"KODEX레버리지({self.TARGET_CODE}) 15:20 시장가 매수."
            )
            await self._execute_market_buy(self.TARGET_CODE, allocate_ratio=1.0)
            # 익일 09:05 청산 루틴 예약
            asyncio.create_task(self._schedule_morning_clear())
        else:
            self.logger.info(
                f"[{self.agent_id}] 조건 미충족. "
                f"패닉={is_panic}, 외인매수={is_foreigner_buying}"
            )

    async def _request_kospi_status(self) -> Dict[str, Any]:
        """
        opt20001: 코스피 지수(업종코드: 001) 당일 변동률 및 3일 연속 하락 여부 파싱.
        """
        from app.core.kiwoom.market import kiwoom_market
        try:
            data = await kiwoom_market.request_tr("opt20001", {"업종코드": self.KOSPI_MARKET_CODE})
            today_rate = float(data.get("updn_rate", "0").replace("+", "").replace(",", ""))
            # 3일 연속 하락 여부: 일봉 데이터에서 최근 3일 확인
            ohlcv = await kiwoom_market.get_ohlcv_df(self.KOSPI_MARKET_CODE, count=5)
            if not ohlcv.empty and len(ohlcv) >= 3:
                recent_closes = ohlcv["close"].values[:3]  # [오늘, 어제, 그제]
                consecutive_drops = sum(
                    1 for i in range(len(recent_closes) - 1)
                    if recent_closes[i] < recent_closes[i + 1]
                )
            else:
                consecutive_drops = 0
            return {
                "today_change_rate": today_rate,
                "consecutive_drop_days": consecutive_drops,
            }
        except Exception as e:
            self.logger.warning(f"[{self.agent_id}] KOSPI 데이터 파싱 실패: {e}")
            return {"today_change_rate": 0, "consecutive_drop_days": 0}

    async def _request_foreigner_futures(self) -> Dict[str, Any]:
        """
        opt10059: 코스피200 선물 시장(업종코드: 101)의 외국인 순매수 데이터 추출.
        """
        from app.core.kiwoom.market import kiwoom_market
        try:
            data = await kiwoom_market.request_tr("opt10059", {"업종코드": self.FUTURES_MARKET_CODE})
            # FID 119: 당일 누적 순매수 금액 (부호 파싱 주의)
            raw_amount = str(data.get("frn_ntby_amt", "0")).replace(",", "").replace("+", "")
            net_buy_amount = float(raw_amount) if raw_amount.lstrip("-").isdigit() else 0.0
            return {"net_buy_amount": net_buy_amount}
        except Exception as e:
            self.logger.warning(f"[{self.agent_id}] 외국인 선물 데이터 파싱 실패: {e}")
            return {"net_buy_amount": 0}

    async def _execute_market_buy(self, code: str, allocate_ratio: float = 1.0) -> None:
        """15:20 동시호가 시장가 매수."""
        from app.core.kiwoom.order import kiwoom_order
        from app.core.kiwoom.account import kiwoom_account

        # 투자 가능 금액 조회 → 배분 비율 적용
        try:
            account_data = await kiwoom_account.get_account_evaluation()
            available_cash = float(
                str(account_data.get("dnca_tot_amt", "0")).replace(",", "")
            )
            buy_amount = int(available_cash * allocate_ratio)
            # 현재가 조회로 수량 계산
            price_data = await kiwoom_order.get_price(code)
            cur_price = int(str(price_data.get("stck_prpr", "1")).replace(",", ""))
            qty = max(1, buy_amount // cur_price) if cur_price > 0 else 1
        except Exception as e:
            self.logger.warning(f"[{self.agent_id}] 매수 수량 계산 실패, 기본값 1주 사용: {e}")
            qty = 1
            cur_price = 0

        res = await kiwoom_order.send_order_v2(
            symbol=code, api_id="kt10000", order_type="1", qty=qty, price=0
        )
        if "error" not in res:
            self.position = {"qty": qty, "entry_price": cur_price, "entry_time": datetime.now()}
            self.logger.info(f"[{self.agent_id}] BUY {code} {qty}주 @ 시장가 (15:20 종가 베팅)")

    # ── Exit Logic (익일 09:05 청산) ───────────────────────────────────────────
    async def _schedule_morning_clear(self) -> None:
        """익일 09:05까지 대기 후 청산 루틴 실행."""
        now = datetime.now()
        tomorrow_0905 = (now + timedelta(days=1)).replace(
            hour=9, minute=5, second=0, microsecond=0
        )
        wait_seconds = (tomorrow_0905 - now).total_seconds()
        self.logger.info(f"[{self.agent_id}] 익일 09:05 청산 루틴 예약 ({wait_seconds:.0f}초 후)")
        await asyncio.sleep(max(0, wait_seconds))
        await self.morning_clear_routine()

    async def morning_clear_routine(self) -> None:
        """
        다음 날 아침 09:05 비동기 청산 태스크.
        시초가 갭 +2% 이상 → 절반 익절
        -3% 도달 시 → 즉시 전량 시장가 손절
        """
        if not self.position:
            return

        from app.core.kiwoom.market import kiwoom_market

        self.logger.info(f"[{self.agent_id}] 09:05 익일 청산 루틴 시작")
        try:
            price_data = await kiwoom_market.get_current_price(self.TARGET_CODE)
            current_price = int(str(price_data.get("stck_prpr", "0")).replace(",", ""))
        except Exception as e:
            self.logger.error(f"[{self.agent_id}] 현재가 조회 실패, 전량 청산으로 폴백: {e}")
            await self._full_sell(reason="PRICE_FETCH_FAIL")
            return

        entry_price = self.position["entry_price"]
        qty = self.position["qty"]

        # 갭 상승 +2% 이상 → 절반 익절
        if current_price >= entry_price * self.GAP_UP_RATIO:
            half_qty = max(1, qty // 2)
            await self._sell(self.TARGET_CODE, half_qty, reason="GAP_UP_HALF_PROFIT")
            self.logger.info(f"[{self.agent_id}] 갭상승 절반 익절 {half_qty}주")

        # -3% 도달 시 즉시 전량 손절
        elif current_price <= entry_price * self.STOP_LOSS_RATIO:
            await self._full_sell(reason="STOP_LOSS_3PCT")
            self.logger.info(f"[{self.agent_id}] -3% 손절 전량 청산")

    async def _full_sell(self, reason: str = "FULL_SELL") -> None:
        if self.position:
            await self._sell(self.TARGET_CODE, self.position["qty"], reason)

    async def _sell(self, code: str, qty: int, reason: str) -> None:
        from app.core.kiwoom.order import kiwoom_order
        await kiwoom_order.send_order_v2(
            symbol=code, api_id="kt10001", order_type="3", qty=qty, price=0
        )
        if self.position:
            self.position["qty"] = max(0, self.position["qty"] - qty)
            if self.position["qty"] <= 0:
                self.position = None
        self.logger.info(f"[{self.agent_id}] SELL {code} {qty}주 ({reason})")


agent3_macro_swing = Agent3MacroSwing()

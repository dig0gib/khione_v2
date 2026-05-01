import logging
from datetime import datetime
from typing import Dict, Any, List
from app.engine.signal_generator import signal_generator
from app.core.kiwoom.order import kiwoom_order
from app.engine.state import global_state
from app.data.database import async_session
from app.data.models import TradeLog, DailyPerformance

class AutoTrader:
    """
    자동 매매 실행기 (Execution Engine).
    """
    def __init__(self) -> None:
        self.order_module = kiwoom_order
        self.max_asset_value = 0.0 # MDD 계산을 위한 최고 자산가치 고점

    async def _log_trade_to_db(self, symbol: str, side: str, price: float, qty: int, agent: str):
        """매매 내역을 SQLite DB에 영구 저장 (2주차/4주차용)"""
        async with async_session() as session:
            new_log = TradeLog(
                symbol=symbol,
                side=side,
                price=price,
                quantity=qty,
                agent=agent,
                timestamp=datetime.now()
            )
            session.add(new_log)
            await session.commit()
            logging.info(f"💾 [{symbol}] 매매 기록 DB 저장 완료 ({side})")

    async def execute_signal(self, symbol: str, signal: Dict[str, Any]) -> None:
        """단일 종목 신호 실행 및 DB 기록"""
        if not global_state.is_trading_active:
            return

        action = signal.get("consensus_action", "HOLD")
        if action == "HOLD": return

        api_id = "kt10000" if action == "BUY" else "kt10001"
        res = await self.order_module.check_risk_and_order(
            symbol=symbol,
            api_id=api_id,
            qty=1,
            price=0,  # 시장가
            exchange="KRX"
        )

        if "error" not in res:
            await self._log_trade_to_db(symbol, action, 0.0, 1, signal.get("agent", "ensemble"))
            logging.info(f"🚀 [{symbol}] {action} 주문 성공 및 기록 완료")
            
            # 텔레그램 알림 발송
            from app.telegram_bot.notifier import send_telegram_notification
            side_kr = "매수" if action == "BUY" else "매도"
            msg = f"🚀 <b>실시간 매매 집행 완료</b>\n\n"
            msg += f"종목: {symbol}\n"
            msg += f"동작: {side_kr}\n"
            msg += f"에이전트: {signal.get('agent_signals', {}).get('agent1', {}).get('agent', 'ensemble')}\n"
            msg += f"사유: {signal.get('agent_signals', {}).get('agent1', {}).get('action', 'N/A')}\n"
            await send_telegram_notification(msg)

    async def monitor_risk(self, current_total_assets: float):
        """3주차 검증용: MDD -3% 감시 및 대응"""
        if current_total_assets > self.max_asset_value:
            self.max_asset_value = current_total_assets
            return

        if self.max_asset_value > 0:
            mdd = (self.max_asset_value - current_total_assets) / self.max_asset_value
            if mdd >= 0.03: # 3% 하락 시
                logging.critical(f"🚨 [RISK] MDD {mdd*100:.2f}% 발생! 즉시 전량 청산 및 정지합니다.")
                global_state.set_trading_active(False)
                await self.liquidate_all()

    async def liquidate_all(self) -> None:
        """전체 포지션 강제 청산 (Kill-Switch)"""
        logging.warning("🚨 전량 시장가 청산 시퀀스 가동")
        for symbol, pos in list(global_state.active_positions.items()):
            qty = pos.get("qty", 0) if isinstance(pos, dict) else getattr(pos, "qty", 0)
            if qty > 0:
                await self.order_module.sell(symbol, qty=qty, order_type="3")
                await self._log_trade_to_db(symbol, "SELL_ALL", 0.0, qty, "KILL_SWITCH")

        global_state.active_positions.clear()
        logging.info("✅ 모든 포지션이 청산되었습니다.")

    async def morning_screening(self) -> None:
        """
        아침 스크리닝 (08:30)
        1. 거래대금 상위 N개 후보 수집 (ka10020) — 실패 시 WATCH_LIST 폴백
        2. Agent1 AQL 필터 적용 → BUY 신호 종목만 선별
        3. 통과 종목 부족 시 HOLD 종목으로 보완
        4. global_state.today_watch_list 갱신 → 당일 매매루프에 반영
        """
        from app.core.kiwoom.market import kiwoom_market
        from app.engine.agent1_scalping import ScalpingAgent
        from app.telegram_bot.notifier import send_telegram_notification
        from app.config.watchlist import WATCH_LIST, SCREENING_TOP_N, SCREENING_MIN_CANDIDATES
        import asyncio

        agent1 = ScalpingAgent()

        # 1. 거래대금 상위 N개 후보 수집
        candidates = await kiwoom_market.get_top_volume_stocks(SCREENING_TOP_N)
        if not candidates:
            logging.warning("[스크리닝] 동적 후보 조회 실패 → WATCH_LIST 폴백")
            candidates = WATCH_LIST

        # 2. AQL 필터링
        passed: Dict[str, str] = {}
        screened_all: List[Dict] = []

        for symbol, name in candidates.items():
            await asyncio.sleep(1.5)
            try:
                df = await kiwoom_market.get_ohlcv_df(symbol)
                if df.empty or len(df) < 2:
                    logging.warning(f"[스크리닝] {name}({symbol}) 데이터 부족")
                    continue

                result = await agent1.analyze(df)
                action = result.get("action", "HOLD")
                target_price = int(result.get("target_price", 0))
                cur_prc = int(df.iloc[0]["close"])

                screened_all.append({
                    "symbol": symbol, "name": name,
                    "action": action, "cur_prc": cur_prc,
                    "target_price": target_price,
                })

                if action == "BUY":
                    passed[symbol] = name

                logging.info(f"[스크리닝] {name}({symbol}) | 현재가:{cur_prc:,} | 목표가:{target_price:,} | {action}")

            except Exception as e:
                logging.error(f"[스크리닝] {name}({symbol}) 오류: {e}")

        # 3. 통과 종목 부족 시 HOLD 종목으로 보완
        if len(passed) < SCREENING_MIN_CANDIDATES:
            logging.warning(f"[스크리닝] BUY 종목 {len(passed)}개 부족 → HOLD 포함 보완")
            for item in screened_all:
                if item["symbol"] not in passed:
                    passed[item["symbol"]] = item["name"]
                if len(passed) >= SCREENING_MIN_CANDIDATES:
                    break

        # 4. 당일 WATCH_LIST 교체
        global_state.today_watch_list = passed
        logging.info(f"[스크리닝] 당일 매매 리스트 확정 ({len(passed)}개): {list(passed.keys())}")

        # 5. 텔레그램 리포트
        report_lines = []
        for item in screened_all:
            flag = "🔴" if item["action"] == "BUY" else "⚪️"
            in_list = " ✅" if item["symbol"] in passed else ""
            report_lines.append(
                f"{flag} <b>{item['name']}</b> ({item['symbol']}){in_list}\n"
                f"   현재가: {item['cur_prc']:,}원 | 목표가: {item['target_price']:,}원\n"
                f"   신호: {item['action']}"
            )

        report = (
            f"❄️ <b>Khione 오늘의 공략 종목 리포트</b>\n\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"거래대금 상위 {len(candidates)}개 → AQL 필터 → <b>{len(passed)}개 확정</b>\n\n"
        )
        report += "\n\n".join(report_lines) if report_lines else "스크리닝 결과 없음"
        report += "\n\n🚀 자동매매는 09:00부터 시작됩니다. /status 로 현황 확인 가능"
        await send_telegram_notification(report)
        logging.info("✅ 아침 스크리닝 리포트 발송 완료")

    async def market_close_routine(self) -> None:
        """장 마감 정산 (15:30)
        - DB에서 당일 체결 거래 조회
        - 전유 포지션 전량 청산 (data trading 원칙)
        - 수익/손실 테레그램 요약 발송
        """
        from app.telegram_bot.notifier import send_telegram_notification
        logging.info("📅 장 마감 데일리 리포트를 생성합니다.")

        # 등록된 포지션 전량 청산
        try:
            from app.core.kiwoom.order import kiwoom_order
            from app.core.kiwoom.account import kiwoom_account
            holdings_data = await kiwoom_account.get_account_evaluation()
            positions = holdings_data.get("stk_acnt_evlt_prst", [])

            for pos in positions:
                raw_code = pos.get("stk_cd", "")
                symbol = raw_code.lstrip("A") if raw_code.startswith("A") else raw_code
                qty = abs(int(str(pos.get("rmnd_qty", "0")).replace(",", "") or 0))
                if qty > 0:
                    await kiwoom_order.send_order_v2(
                        symbol=symbol, api_id="kt10001", order_type="3", qty=qty, price=0
                    )
                    logging.info(f"⌛ 장 마감 전량 청산: {pos.get('stk_nm', symbol)} {qty}주")
        except Exception as e:
            logging.error(f"장마감 체정 중 오류: {e}")

        # DB에서 당일 거래 요약
        total_pnl = 0
        trade_lines = []
        try:
            async with async_session() as session:
                from sqlalchemy import select
                from app.data.models import TradeLog
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                stmt = select(TradeLog).where(TradeLog.timestamp >= today_start)
                result = await session.execute(stmt)
                trades = result.scalars().all()

                buy_map = {}  # symbol -> (price, qty)
                for t in trades:
                    if t.side in ("BUY",):
                        buy_map[t.symbol] = {"price": t.price, "qty": t.quantity}
                    elif t.side in ("SELL", "SELL_ALL"):
                        buy_info = buy_map.get(t.symbol)
                        if buy_info and buy_info["price"] > 0:
                            pnl = (t.price - buy_info["price"]) * buy_info["qty"]
                            rate = (t.price / buy_info["price"] - 1) * 100
                            total_pnl += pnl
                            trade_lines.append(
                                f"  • {t.symbol}: {rate:+.2f}% ({int(pnl):+,}원)"
                            )
        except Exception as e:
            logging.error(f"DB 거래 요약 조회 오류: {e}")

        summary = (
            f"🏁 <b>Khione 일일 마감 리포트</b>\n"
            f"📅 {datetime.now().strftime('%Y-%m-%d')}\n"
            f"총 손익: <b>{int(total_pnl):+,}원</b>\n\n"
        )
        summary += "\n".join(trade_lines) if trade_lines else "오늘 체결된 거래 없음"
        summary += "\n\n⏰ 다음 거래일은 오전 08:30부터 시작됩니다."
        await send_telegram_notification(summary)
        logging.info("✅ 장 마감 리포트 발송 완료")

auto_trader = AutoTrader()

import logging
import asyncio
import pandas as pd
from datetime import datetime, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.engine.state import global_state
from app.execution.auto_trader import auto_trader

logger = logging.getLogger(__name__)

from app.config.watchlist import WATCH_LIST, ETF_CODES

# ─────────────────────────────────────────────────────────────
# 스케줄 태스크
# ─────────────────────────────────────────────────────────────

async def token_refresh_task():
    """08:20 — 키움 API 접근토큰 자동 갱신"""
    logger.info("📅 [Schedule] 키움 API 토큰 자동 갱신 시작 (08:20)")
    from app.core.kiwoom.auth import kiwoom_auth
    from app.telegram_bot.notifier import send_telegram_notification
    try:
        new_token = await kiwoom_auth.fetch_new_token()
        if new_token:
            logger.info("✅ 토큰 갱신 완료")
            await send_telegram_notification("🔑 API 토큰 자동 갱신 완료.")
        else:
            logger.error("❌ 토큰 갱신 실패!")
            await send_telegram_notification("⚠️ *API 토큰 갱신 실패!* 수동으로 확인이 필요합니다.")
    except Exception as e:
        logger.error(f"토큰 갱신 중 예외: {e}")


async def morning_screening_task():
    """08:30 — 전종목 AQL 스크리닝 및 오늘의 유망주 발굴"""
    logger.info("📅 [Schedule] 아침 스크리닝 작업을 시작합니다 (08:30)")
    await auto_trader.morning_screening()


async def start_trading_task():
    """09:00 — 정규장 시작 및 자동매매 활성화"""
    logger.info("📅 [Schedule] 정규장이 시작되었습니다. 자동매매를 활성화합니다 (09:00)")
    global_state.set_trading_active(True)


async def stop_trading_task():
    """15:30 — 장 마감 및 자동매매 비활성화 / 정산"""
    logger.info("📅 [Schedule] 정규장이 마감되었습니다. 자동매매를 중단하고 정산합니다 (15:30)")
    global_state.set_trading_active(False)
    await auto_trader.market_close_routine()


async def realtime_trading_task():
    """
    5분 단위 실시간 매매 판단 루프 (핵심 매매 루프).
    - [Fix] 1분 → 5분 간격으로 변경 (Rate Limit 방지)
    - [Fix] 가짜 2행 DataFrame → 실제 ka10086 OHLCV 데이터 사용
    - [Fix] 종목 간 1초 딜레이 추가
    """
    if not global_state.is_trading_active:
        return

    # 15:30 이후 실행 방지
    now = datetime.now().time()
    if now > time(15, 30):
        return

    from app.core.kiwoom.market import kiwoom_market
    from app.core.kiwoom.account import kiwoom_account
    from app.engine.signal_generator import signal_generator
    from app.telegram_bot.notifier import send_telegram_notification

    # 주문가능금액 조회
    try:
        balance_data = await kiwoom_account.get_deposit_detail()
        orderable_amount = abs(int(
            str(balance_data.get("ord_alow_amt", "0")).replace(",", "") or 0
        ))
    except Exception as e:
        logger.warning(f"주문가능금액 조회 실패, 이번 루프 스킵: {e}")
        return

    active_list = global_state.today_watch_list if global_state.today_watch_list else WATCH_LIST
    logger.info(f"[매매루프] 주문가능금액: {orderable_amount:,}원 | 감시종목: {len(active_list)}개 ({'동적' if global_state.today_watch_list else '기본'})")

    for symbol, name in active_list.items():
        # [Fix] 종목 간 Rate Limit 방지 딜레이
        await asyncio.sleep(1.5)
        try:
            # [Fix] 실제 ka10086 OHLCV 데이터 사용
            df = await kiwoom_market.get_ohlcv_df(symbol)
            if df.empty or len(df) < 2:
                logger.warning(f"[매매루프] {name}({symbol}) OHLCV 데이터 부족, 스킵")
                continue

            # 현재가: ka10004 호가 (실시간)
            cur_prc = await kiwoom_market.get_current_price_from_orderbook(symbol)
            if cur_prc == 0:
                # fallback: OHLCV 최신 종가
                cur_prc = int(df.iloc[0]["close"])
            if cur_prc == 0:
                continue

            # DataFrame 최신행의 close를 현재가로 업데이트
            df.iloc[0, df.columns.get_loc("close")] = float(cur_prc)

            # 신호 생성 (3개 에이전트 합의)
            signal = await signal_generator.generate_final_signal(symbol, df)
            action = signal.get("consensus_action", "HOLD")

            logger.info(f"[매매루프] {name}({symbol}) | 현재가: {cur_prc:,} | 신호: {action}")

            # 의사결정 스트림 기록
            global_state.decision_stream.insert(0, {
                "time": datetime.now().strftime("%H:%M:%S"),
                "symbol": name,
                "action": action,
                "regime": global_state.current_regime,
                "reason": signal.get("reason", ""),
            })
            if len(global_state.decision_stream) > 20:
                global_state.decision_stream.pop()

            # 매수 집행
            if action == "BUY" and orderable_amount > cur_prc:
                qty = max(1, orderable_amount // cur_prc // 10)  # 10분의 1 한도
                from app.core.kiwoom.order import kiwoom_order
                res = await kiwoom_order.send_order_v2(
                    symbol=symbol, api_id="kt10000", order_type="3", qty=qty, price=0
                )
                msg = (f"🛒 *매수 집행*\n종목: {name}({symbol})\n"
                       f"수량: {qty}주\n가격: {cur_prc:,}원\n신호: {action}")
                await send_telegram_notification(msg)
                logger.info(f"[매매루프] {name}({symbol}) 매수 완료: {res}")

            # 매도 집행
            elif action == "SELL":
                pos = global_state.active_positions.get(symbol) if isinstance(global_state.active_positions, dict) else None
                if pos:
                    from app.core.kiwoom.order import kiwoom_order
                    res = await kiwoom_order.send_order_v2(
                        symbol=symbol, api_id="kt10001", order_type="3",
                        qty=pos.get("qty", 1), price=0
                    )
                    msg = (f"📤 *매도 집행*\n종목: {name}({symbol})\n"
                           f"수량: {pos.get('qty', 1)}주\n현재가: {cur_prc:,}원")
                    await send_telegram_notification(msg)

        except Exception as e:
            logger.error(f"[매매루프] {name}({symbol}) 처리 중 오류: {e}")


# ─────────────────────────────────────────────────────────────
# 스케줄러 설정
# ─────────────────────────────────────────────────────────────

def setup_scheduler() -> AsyncIOScheduler:
    """전체 시스템 스케줄러 설정"""
    scheduler = AsyncIOScheduler()

    # [New] 0. 토큰 자동 갱신 (평일 08:20)
    scheduler.add_job(
        token_refresh_task,
        CronTrigger(day_of_week="mon-fri", hour=8, minute=20),
        id="token_refresh"
    )

    # 1. 아침 스크리닝 (평일 08:30)
    scheduler.add_job(
        morning_screening_task,
        CronTrigger(day_of_week="mon-fri", hour=8, minute=30),
        id="morning_screening"
    )

    # 2. 매매 시작 (평일 09:00)
    scheduler.add_job(
        start_trading_task,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=0),
        id="start_trading"
    )

    # 3. 매매 종료 (평일 15:30)
    scheduler.add_job(
        stop_trading_task,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=30),
        id="stop_trading"
    )

    # 4. [Fix] 실시간 매매 루프: 1분 → 5분 간격
    scheduler.add_job(
        realtime_trading_task,
        "interval",
        minutes=5,
        id="realtime_trading"
    )

    # ── v2 Agent 전용 배치 태스크 ──────────────────────────────────────────

    # 5. Agent2 시간 청산 (평일 15:10)
    async def agent2_time_liquidation():
        from app.engine.agent2_program_day import agent2_program_day
        from app.data.system_validator import system_validator
        await system_validator.validate_scheduler("agent2_program_day", "15:10", datetime.now())
        await agent2_program_day.liquidate_all_positions()

    scheduler.add_job(
        agent2_time_liquidation,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=10),
        id="agent2_time_liquidation"
    )

    # 6. Agent3 종가 베팅 (평일 15:20)
    async def agent3_close_betting():
        from app.engine.agent3_macro_swing import agent3_macro_swing
        from app.data.system_validator import system_validator
        await system_validator.validate_scheduler("agent3_macro_swing", "15:20", datetime.now())
        await agent3_macro_swing.execute_close_betting_routine()

    scheduler.add_job(
        agent3_close_betting,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=20),
        id="agent3_close_betting"
    )

    # 7. MetaAgent 일일 배분 (평일 15:40)
    async def meta_agent_allocation():
        from app.engine.meta_agent_allocator import meta_agent_allocator
        await meta_agent_allocator.execute_daily_allocation()

    scheduler.add_job(
        meta_agent_allocation,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=40),
        id="meta_agent_allocation"
    )

    return scheduler


from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.engine.state import global_state
from app.telegram_bot.bot import build_telegram_bot
from app.scheduler.tasks import setup_scheduler
from app.data.database import init_db
from contextlib import asynccontextmanager
import logging
import asyncio

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Telegram Bot & Scheduler Instances
telegram_app = build_telegram_bot()
trading_scheduler = setup_scheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 DB, 봇, 스케줄러를 시작하고, 종료 시 안전하게 정지합니다."""
    # 0. Initialize Database
    await init_db()
    logger.info("🗄️ Database initialized.")

    # 0-1. Shadow Bot 초기화 (DB 테이블 생성 후)
    try:
        from app.engine.meta_agent_allocator import meta_agent_allocator
        await meta_agent_allocator.initialize_shadows()
    except Exception as e:
        logger.warning(f"Shadow Bot 초기화 실패 (무시): {e}")

    # 1. Start Telegram Bot (drop_pending_updates로 이전 충돌 방지)
    if telegram_app:
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling(drop_pending_updates=True)
        logger.info("🤖 Telegram Bot started successfully.")
    else:
        logger.warning("⚠️ Telegram Bot is disabled (Invalid token).")
    
    # 2. Start Scheduler
    trading_scheduler.start()
    logger.info("📅 Daily Trading Scheduler started.")

    # 3. 장중 자동 복구: 서버가 09:00~15:30 사이에 시작된 경우 trading 즉시 활성화
    from datetime import datetime, time as dtime
    from app.telegram_bot.notifier import send_telegram_notification
    _now = datetime.now()
    if _now.weekday() < 5 and dtime(9, 0) <= _now.time() <= dtime(15, 30):
        global_state.set_trading_active(True)
        logger.info("⚡ 장중 재시작 감지 → 자동매매 즉시 활성화")
        await send_telegram_notification(
            f"⚡ <b>장중 재시작 감지</b>\n"
            f"자동매매를 즉시 활성화했습니다.\n"
            f"재시작 시각: {_now.strftime('%H:%M:%S')}"
        )

    yield
    
    # 3. Stop Scheduler & Bot
    trading_scheduler.shutdown()
    if telegram_app:
        await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()
        logger.info("👋 System shut down.")

app = FastAPI(
    title="Khione API", 
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.core.kiwoom.market import kiwoom_market

@app.get("/api/v1/market/news")
async def get_market_news(symbol: str = ""):
    """최근 주요 뉴스 및 에이전트 참고 공시를 반환합니다."""
    return await kiwoom_market.get_recent_news(symbol)

@app.get("/api/v1/status")
async def get_status():
    """현재 시스템 상태를 반환합니다."""
    return {
        "is_trading_active": global_state.is_trading_active,
        "current_regime": global_state.current_regime,
        "agent_allocations": global_state.agent_allocations,
        "active_positions_count": len(global_state.active_positions),
        "api_connected": True,
    }

@app.post("/api/v1/kill-switch")
async def trigger_kill_switch():
    """시스템 비상 정지 및 전량 청산 명령을 트리거합니다."""
    logger.warning("🚨 KILL SWITCH TRIGGERED VIA API")
    global_state.set_trading_active(False)
    from app.execution.auto_trader import auto_trader
    from app.telegram_bot.notifier import send_telegram_notification
    try:
        await auto_trader.liquidate_all()
        await send_telegram_notification("🚨 <b>킬스위치 발동</b>\n전량 시장가 청산 명령 실행 완료")
    except Exception as e:
        logger.error(f"킬스위치 청산 오류: {e}")
    return {"message": "Kill switch activated successfully", "status": "SHUTDOWN"}

@app.get("/api/v1/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/api/v1/trading/start")
async def manual_start_trading():
    """수동 자동매매 활성화 (장중 재시작 시 또는 수동 제어용)"""
    from datetime import datetime, time as dtime
    from app.telegram_bot.notifier import send_telegram_notification
    now = datetime.now()
    if now.time() > dtime(15, 30):
        return {"ok": False, "message": "장 마감 이후(15:30~)에는 활성화 불가"}
    global_state.set_trading_active(True)
    logger.info("▶️ 수동 자동매매 활성화 (API)")
    await send_telegram_notification(
        f"▶️ <b>수동 자동매매 활성화</b>\n시각: {now.strftime('%H:%M:%S')}"
    )
    return {"ok": True, "is_trading_active": True}


@app.post("/api/v1/trading/stop")
async def manual_stop_trading():
    """수동 자동매매 비활성화 (킬스위치 없이 소프트 중단)"""
    from datetime import datetime
    from app.telegram_bot.notifier import send_telegram_notification
    global_state.set_trading_active(False)
    logger.info("⏹️ 수동 자동매매 중단 (API)")
    await send_telegram_notification(
        f"⏹️ <b>수동 자동매매 중단</b>\n시각: {datetime.now().strftime('%H:%M:%S')}"
    )
    return {"ok": True, "is_trading_active": False}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

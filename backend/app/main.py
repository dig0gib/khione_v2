"""
FastAPI Backend — Khione V2
주요 변경사항:
- CORS: allow_origins에 Vercel 도메인 추가 (배포 환경 차단 해제)
- GET /api/v1/system/errors: 최신 에러 로그 반환 (대시보드 건전성 패널용)
- 시스템 부팅 시 MetaAgentAllocator.initialize_shadows() 호출
- 15:40 배치 스케줄러에 execute_daily_allocation 등록
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.engine.state import global_state
from app.telegram_bot.bot import build_telegram_bot
from app.scheduler.tasks import setup_scheduler
from app.data.database import init_db
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler
import logging
import asyncio
import os


def setup_logging():
    log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
    os.makedirs(log_dir, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "khione.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=7,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


setup_logging()
logger = logging.getLogger(__name__)

telegram_app = build_telegram_bot()
trading_scheduler = setup_scheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 DB, 봇, 스케줄러를 시작하고, 종료 시 안전하게 정지합니다."""
    # 0. DB 초기화
    await init_db()
    logger.info("🗄️ Database initialized (V2: agent_performance + system_errors 포함).")

    # 1. MetaAgentAllocator Shadow Bot 초기화 (명세서: meta_agent_allocator.md)
    from app.engine.meta_agent_allocator import meta_agent_allocator
    try:
        await meta_agent_allocator.initialize_shadows()
        logger.info("🤖 MetaAgentAllocator Shadow Bots initialized.")
    except Exception as e:
        logger.warning(f"⚠️ Shadow Bot 초기화 실패 (DB 미구성 시 정상): {e}")

    # 2. Telegram Bot 시작
    if telegram_app:
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling()
        logger.info("🤖 Telegram Bot started successfully.")
    else:
        logger.warning("⚠️ Telegram Bot is disabled (Invalid token).")

    # 3. Scheduler 시작
    trading_scheduler.start()
    logger.info("📅 Daily Trading Scheduler started.")

    yield

    # Shutdown
    trading_scheduler.shutdown()
    from app.core.rate_limiter import kiwoom_gateway
    await kiwoom_gateway.stop()
    if telegram_app:
        await telegram_app.updater.stop()
        await telegram_app.stop()
        await telegram_app.shutdown()
        logger.info("👋 Khione V2 System shut down.")


app = FastAPI(
    title="Khione V2 API",
    version="2.0.0",
    lifespan=lifespan
)

# ── CORS 설정 (Vercel 배포 환경 포함 — V1의 localhost 한정 버그 수정) ──────────
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://khionev1.vercel.app",       # V1 (하위 호환)
    "https://khione-v2.vercel.app",      # V2 Vercel 배포
    "https://*.vercel.app",              # Vercel 프리뷰 브랜치
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",  # 동적 Vercel 도메인 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API 엔드포인트 ─────────────────────────────────────────────────────────────
from app.core.kiwoom.market import kiwoom_market


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


@app.get("/api/v1/market/news")
async def get_market_news(symbol: str = ""):
    """최근 주요 뉴스 및 에이전트 참고 공시를 반환합니다."""
    return await kiwoom_market.get_recent_news(symbol)


@app.post("/api/v1/kill-switch")
async def trigger_kill_switch():
    """시스템 비상 정지 및 전량 청산 명령을 트리거합니다."""
    logger.warning("🚨 KILL SWITCH TRIGGERED VIA API")
    global_state.set_trading_active(False)

    from app.execution.auto_trader import auto_trader
    try:
        await auto_trader.liquidate_all()
        logger.info("✅ 킬스위치 API: 모든 포지션 강제 청산 명령 전달 완료")
    except Exception as e:
        logger.error(f"❌ 킬스위치 API 청산 중 오류 발생: {e}")

    return {"message": "Kill switch activated successfully, positions liquidated.", "status": "SHUTDOWN"}


@app.get("/api/v1/decision-stream")
async def get_decision_stream():
    """최근 의사결정 기록 반환 (최대 20건)"""
    return global_state.decision_stream


@app.get("/api/v1/health")
async def health_check():
    return {"status": "healthy", "version": "2.0.0"}


# ── 시스템 건전성 에러 로그 (명세서: error_logging_dashboard.md) ──────────────
@app.get("/api/v1/system/errors")
async def get_system_errors(limit: int = 10):
    """
    최신 에러 로그 10개를 JSON 포맷으로 반환.
    프론트엔드 [🚨 시스템 건전성 현황] 패널이 1분 주기로 폴링.
    응답 포맷: [{"date": "2026-05-01 15:11", "status": "Anomaly 02: 시간 청산 누락 감지"}]
    """
    from app.data.system_validator import system_validator
    try:
        return await system_validator.get_recent_errors(limit=limit)
    except Exception as e:
        logger.error(f"system/errors 조회 오류: {e}")
        return []


# ── 투자일지 ──────────────────────────────────────────────────────────────────
from app.data.database import async_session
from app.data.models import DailyJournal
from sqlalchemy import select
from pydantic import BaseModel


class JournalUpsert(BaseModel):
    regime: str = "STABLE"
    strategy_summary: str = ""
    trade_summary: str = ""
    pnl: float = 0.0
    news_events: str = ""
    tomorrow_plan: str = ""


@app.get("/api/v1/journal")
async def list_journals(limit: int = 30):
    """최근 투자일지 목록 (최대 30건)"""
    async with async_session() as db:
        result = await db.execute(
            select(DailyJournal).order_by(DailyJournal.date.desc()).limit(limit)
        )
        rows = result.scalars().all()
        return [
            {
                "date": r.date,
                "regime": r.regime,
                "pnl": r.pnl,
                "strategy_summary": r.strategy_summary,
                "trade_summary": r.trade_summary,
                "news_events": r.news_events,
                "tomorrow_plan": r.tomorrow_plan,
            }
            for r in rows
        ]


@app.get("/api/v1/journal/{date}")
async def get_journal(date: str):
    """특정 날짜 투자일지 (YYYYMMDD)"""
    async with async_session() as db:
        result = await db.execute(
            select(DailyJournal).where(DailyJournal.date == date)
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="해당 날짜 일지 없음")
        return {
            "date": row.date,
            "regime": row.regime,
            "pnl": row.pnl,
            "strategy_summary": row.strategy_summary,
            "trade_summary": row.trade_summary,
            "news_events": row.news_events,
            "tomorrow_plan": row.tomorrow_plan,
        }


@app.post("/api/v1/journal/{date}")
async def upsert_journal(date: str, body: JournalUpsert):
    """투자일지 생성 또는 수정"""
    async with async_session() as db:
        result = await db.execute(
            select(DailyJournal).where(DailyJournal.date == date)
        )
        row = result.scalar_one_or_none()
        if row:
            for k, v in body.dict().items():
                setattr(row, k, v)
        else:
            row = DailyJournal(date=date, **body.dict())
            db.add(row)
        await db.commit()
        return {"ok": True, "date": date}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.data.models import Base

# SQLite는 파일 기반이므로 백업 및 이동이 매우 용이함
engine = create_async_engine(settings.DATABASE_URL)

async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def init_db():
    """데이터베이스 테이블 생성 및 초기화"""
    async with engine.begin() as conn:
        # 개발 모드에서는 시작 시 테이블 자동 생성
        await conn.run_sync(Base.metadata.create_all)

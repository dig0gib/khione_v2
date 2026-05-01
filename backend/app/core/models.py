from datetime import datetime, date, timedelta
from typing import Optional, Any, Dict
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Date, Interval, JSON, Enum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
import enum
import uuid

class Base(DeclarativeBase):
    pass

class TradeType(str, enum.Enum):
    SCALPING = "단타"
    DAY = "데이"
    SWING = "스윙"

class ExitTrigger(str, enum.Enum):
    TARGET = "목표가"
    STOP_LOSS = "손절"
    TIME_CLOSE = "시간청산"
    MANUAL = "수동"
    ANOMALY = "이상감지"

class TradeJournal(Base):
    """
    핵심 매매일지 (Core Trade Journal)
    모든 의사결정의 메타데이터를 저장하여 미래 AI 학습의 Ground Truth로 사용.
    """
    __tablename__ = "trade_journal"

    trade_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    ticker: Mapped[str] = mapped_column(String(20), index=True)
    ticker_name: Mapped[str] = mapped_column(String(100))
    trade_type: Mapped[TradeType] = mapped_column(Enum(TradeType))

    # 진입 상세
    entry_datetime: Mapped[datetime] = mapped_column(DateTime)
    entry_price: Mapped[float] = mapped_column(Float)
    entry_quantity: Mapped[int] = mapped_column(Integer)
    entry_amount: Mapped[float] = mapped_column(Float)

    # 판단 근거
    entry_reason_tech: Mapped[str] = mapped_column(String)
    entry_reason_news: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    entry_agent1_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    entry_agent2_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    entry_agent3_ratio: Mapped[str] = mapped_column(String(50)) # e.g., "70/20/10"
    entry_market_regime: Mapped[str] = mapped_column(String(50))
    entry_confidence: Mapped[float] = mapped_column(Float)

    # 청산 상세 (진입 중일 때는 NULL)
    exit_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exit_quantity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    exit_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    exit_trigger: Mapped[Optional[ExitTrigger]] = mapped_column(Enum(ExitTrigger), nullable=True)

    # 결과 분석
    pnl_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    holding_duration: Mapped[Optional[timedelta]] = mapped_column(Interval, nullable=True)

    # 사후 레이블링 (RL용)
    success: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    success_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    timing_analysis: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    improvement_suggestion: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    market_condition_summary: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    slippage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    commission: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class AgentType(str, enum.Enum):
    AGENT1 = "agent1"
    AGENT2 = "agent2"
    AGENT3 = "agent3"

class ReplayBuffer(Base):
    """
    강화학습 리플레이 버퍼 (Replay Buffer)
    trade_journal의 데이터를 (S, A, R, S') 튜플로 변환하여 저장.
    """
    __tablename__ = "replay_buffer"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trade_id: Mapped[uuid.UUID] = mapped_column(index=True) # Linked to TradeJournal, but loosely
    agent_type: Mapped[AgentType] = mapped_column(Enum(AgentType))
    
    # SQLite 호환성을 위해 JSON 사용. 운영 환경에서는 JSONB로 마이그레이션 권장
    state_vector: Mapped[Dict[str, Any]] = mapped_column(JSON) 
    action: Mapped[str] = mapped_column(String(50))
    reward: Mapped[float] = mapped_column(Float) # Alpha 기반 + Sortino
    next_state_vec: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    is_terminal: Mapped[bool] = mapped_column(Boolean, default=False)
    quality_score: Mapped[float] = mapped_column(Float)
    is_negative_sample: Mapped[bool] = mapped_column(Boolean, default=False) # 미선택 종목 여부
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

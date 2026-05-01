"""
데이터베이스 ORM 모델 — Khione V2
agent_performance 및 system_errors 테이블 포함 (명세서 완전 준수)
"""
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, JSON, Text
)
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class TradeLog(Base):
    """모든 매매 체결 내역 기록."""
    __tablename__ = "trade_logs"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    side = Column(String)          # BUY, SELL, SELL_ALL
    price = Column(Float)
    quantity = Column(Integer)
    timestamp = Column(DateTime, default=datetime.now)
    agent = Column(String)         # 어떤 에이전트가 낸 신호인지
    status = Column(String, default="COMPLETED")


class DailyPerformance(Base):
    """일일 성과 추적."""
    __tablename__ = "daily_performance"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, unique=True)
    total_assets = Column(Float)
    pnl = Column(Float)            # 당일 손익
    mdd = Column(Float)            # 당일 최대 낙폭
    regime = Column(String)


class SystemStateDB(Base):
    """시스템 상태 DB 영구 저장용 (서버 재시작 시 상태 복원)."""
    __tablename__ = "system_state"

    id = Column(Integer, primary_key=True)
    is_trading_active = Column(Boolean, default=False)
    agent_allocations = Column(JSON)
    updated_at = Column(DateTime, onupdate=datetime.now)


class DailyJournal(Base):
    """투자일지 (날짜별 전략 요약, 매매 내역, 손익, 내일 계획)."""
    __tablename__ = "daily_journal"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(8), unique=True, index=True)   # YYYYMMDD
    regime = Column(String(20), default="STABLE")
    strategy_summary = Column(Text, default="")
    trade_summary = Column(Text, default="")
    pnl = Column(Float, default=0.0)
    news_events = Column(Text, default="")
    tomorrow_plan = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AgentPerformance(Base):
    """
    에이전트 성과 관리 + Shadow Bot 인큐베이터 DB 스키마
    명세서: docs/architecture/meta_agent_allocator.md

    CREATE TABLE agent_performance (
        agent_id VARCHAR(50) PRIMARY KEY,
        is_shadow BOOLEAN,
        parent_agent_id VARCHAR(50),
        parameters JSON,
        win_rate FLOAT,
        sharpe_ratio FLOAT,
        mdd FLOAT,
        allocation_ratio FLOAT,
        status VARCHAR(20)  -- 'ACTIVE', 'SLEEP'
    );
    """
    __tablename__ = "agent_performance"

    agent_id = Column(String(50), primary_key=True, index=True)
    is_shadow = Column(Boolean, default=False)
    parent_agent_id = Column(String(50), nullable=True, index=True)
    parameters = Column(JSON, nullable=True)           # 에이전트 파라미터 (변이 포함)
    win_rate = Column(Float, default=0.0)              # 승률 (0.0 ~ 1.0)
    sharpe_ratio = Column(Float, default=0.0)          # Sharpe Ratio
    mdd = Column(Float, default=0.0)                   # 최대 낙폭 (음수)
    allocation_ratio = Column(Float, default=0.33)     # 자산 배분 비율
    status = Column(String(20), default="ACTIVE")      # 'ACTIVE', 'SLEEP'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SystemError(Base):
    """
    시스템 자가 진단 에러 로그
    명세서: docs/architecture/error_logging_dashboard.md

    CREATE TABLE system_errors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        anomaly_code VARCHAR(20),
        severity VARCHAR(10),  -- 'CRITICAL', 'WARNING'
        description TEXT,
        is_resolved BOOLEAN DEFAULT 0
    );
    """
    __tablename__ = "system_errors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.now)
    anomaly_code = Column(String(20), index=True)      # 'Anomaly 01', 'Anomaly 02', 'Anomaly 03'
    severity = Column(String(10))                       # 'CRITICAL', 'WARNING'
    description = Column(Text)
    is_resolved = Column(Boolean, default=False)

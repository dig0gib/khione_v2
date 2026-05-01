from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class TradeLog(Base):
    """모든 매매 체결 내역 기록 (2주차/4주차 검증용)"""
    __tablename__ = "trade_logs"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    side = Column(String) # BUY, SELL
    price = Column(Float)
    quantity = Column(Integer)
    timestamp = Column(DateTime, default=datetime.now)
    agent = Column(String) # 어떤 에이전트가 낸 신호인지
    status = Column(String, default="COMPLETED")

class DailyPerformance(Base):
    """일일 성과 추적 (2주차/4주차 수익률 검증용)"""
    __tablename__ = "daily_performance"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, unique=True)
    total_assets = Column(Float)
    pnl = Column(Float) # 당일 손익
    mdd = Column(Float) # 당일 최대 낙폭
    regime = Column(String)

class SystemStateDB(Base):
    """시스템 상태 DB 영구 저장용 (서버 재시작 시 상태 복원)"""
    __tablename__ = "system_state"

    id = Column(Integer, primary_key=True)
    is_trading_active = Column(Boolean, default=False)
    agent_allocations = Column(JSON)
    updated_at = Column(DateTime, onupdate=datetime.now)

class DailyJournal(Base):
    """투자일지 (날짜별 전략 요약, 매매 내역, 손익, 내일 계획)"""
    __tablename__ = "daily_journal"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(8), unique=True, index=True)  # YYYYMMDD
    regime = Column(String(20), default="STABLE")
    strategy_summary = Column(Text, default="")        # 오늘 전략 요약
    trade_summary = Column(Text, default="")           # 매매 내역 요약
    pnl = Column(Float, default=0.0)                   # 오늘 손익 (원)
    news_events = Column(Text, default="")             # 주요 뉴스/이벤트
    tomorrow_plan = Column(Text, default="")           # 내일 계획
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

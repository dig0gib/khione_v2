import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.execution.auto_trader import auto_trader
from app.execution.blackswan import blackswan_detector

class TradingScheduler:
    """
    전역 작업 스케줄러 (Global Task Scheduler).
    APScheduler를 활용하여 시간대별로 필요한 매매 파이프라인을 구동합니다.
    """
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler()

    def setup_jobs(self) -> None:
        """
        정해진 시간에 실행될 크론(cron) 및 간격(interval) 작업들을 등록합니다.
        """
        # 1. 아침 스크리닝 (08:30)
        self.scheduler.add_job(
            auto_trader.morning_screening, 
            trigger='cron', 
            hour=8, 
            minute=30,
            id='morning_screening'
        )
        
        # 2. 강제 청산 및 데일리 마감 (15:30)
        self.scheduler.add_job(
            auto_trader.market_close_routine, 
            trigger='cron', 
            hour=15, 
            minute=30,
            id='market_close'
        )
        
        # 3. 돌발 변수(블랙스완) 모니터링 (1분 간격)
        self.scheduler.add_job(
            blackswan_detector.monitor_market_anomalies, 
            trigger='interval', 
            minutes=1,
            id='blackswan_monitoring'
        )
        logging.info("스케줄러 작업 등록 완료.")

    def start(self) -> None:
        """스케줄러를 시작합니다."""
        self.setup_jobs()
        self.scheduler.start()
        logging.info("Trading Scheduler가 시작되었습니다.")

trading_scheduler = TradingScheduler()

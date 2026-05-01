"""
SystemValidator: 시스템 자가 진단기
명세서: docs/architecture/error_logging_dashboard.md 완전 준수

- Anomaly 01: 그림자 봇 승격 시 Sharpe Ratio 1위 검증
- Anomaly 02: Agent 2 (15:10), Agent 3 (15:20) 하드 타임스탑 1분 이상 지연 감지
- Anomaly 03: 키움 API Rate Limit 1초당 5회 초과 감지
- 모든 에러는 system_errors 테이블에 즉시 INSERT
"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class SystemValidator:
    """
    시스템 자가 진단 클래스.
    AI 코딩 에이전트의 할루시네이션 무한 루프를 시스템 차원에서 차단.
    """

    # Anomaly 코드 상수
    ANOMALY_01 = "Anomaly 01"  # 승격 Sharpe 검증 실패
    ANOMALY_02 = "Anomaly 02"  # 타임스탑 지연
    ANOMALY_03 = "Anomaly 03"  # API Rate Limit 초과

    # 타임스탑 허용 지연 (초)
    MAX_SCHEDULER_DELAY_SECONDS = 60

    async def _log_anomaly(
        self,
        anomaly_code: str,
        severity: str,
        description: str,
    ) -> None:
        """발생한 에러/Anomaly를 system_errors 테이블에 즉시 INSERT."""
        from app.data.database import async_session
        from sqlalchemy import text

        async with async_session() as session:
            await session.execute(
                text("""
                    INSERT INTO system_errors
                    (timestamp, anomaly_code, severity, description, is_resolved)
                    VALUES (:ts, :code, :sev, :desc, 0)
                """),
                {
                    "ts": datetime.now(),
                    "code": anomaly_code,
                    "sev": severity,
                    "desc": description,
                }
            )
            await session.commit()

        logger.error(f"[SystemValidator] [{severity}] {anomaly_code}: {description}")

    async def validate_promotion(
        self,
        dead_agent_id: str,
        best_shadow_id: str,
        best_sharpe: float,
    ) -> bool:
        """
        Anomaly 01: 그림자 봇 승격 시, 승격된 봇의 Sharpe Ratio가
        실제로 1위가 맞는지 검증. 불일치 시 Anomaly 01 발생.
        """
        from app.data.database import async_session
        from sqlalchemy import text

        async with async_session() as session:
            result = await session.execute(
                text("""
                    SELECT MAX(sharpe_ratio)
                    FROM agent_performance
                    WHERE parent_agent_id = :pid
                      AND is_shadow = 1
                      AND status = 'ACTIVE'
                """),
                {"pid": dead_agent_id}
            )
            actual_max_sharpe = result.scalar() or 0.0

        if abs(best_sharpe - actual_max_sharpe) > 0.001:
            desc = (
                f"승격 대상({best_shadow_id})의 Sharpe={best_sharpe:.4f}가 "
                f"DB 실제 최고값={actual_max_sharpe:.4f}과 불일치. 승격 차단."
            )
            await self._log_anomaly(self.ANOMALY_01, "CRITICAL", desc)
            return False

        logger.info(f"[SystemValidator] Anomaly 01 검증 통과: {best_shadow_id} Sharpe={best_sharpe:.4f}")
        return True

    async def validate_scheduler(
        self,
        agent_id: str,
        expected_time_str: str,
        actual_execution_time: datetime,
    ) -> None:
        """
        Anomaly 02: Agent 2 (15:10), Agent 3 (15:20) 하드 타임스탑이
        1분(60초) 이상 지연될 경우 ANOMALY_02 발생.
        """
        h, m = map(int, expected_time_str.split(":"))
        expected_dt = actual_execution_time.replace(hour=h, minute=m, second=0, microsecond=0)
        delay_seconds = (actual_execution_time - expected_dt).total_seconds()

        if delay_seconds > self.MAX_SCHEDULER_DELAY_SECONDS:
            desc = (
                f"{agent_id} 타임스탑 예정 시각: {expected_time_str}, "
                f"실제 실행: {actual_execution_time.strftime('%H:%M:%S')}, "
                f"지연: {delay_seconds:.0f}초 (임계값 {self.MAX_SCHEDULER_DELAY_SECONDS}초 초과)"
            )
            await self._log_anomaly(self.ANOMALY_02, "WARNING", desc)
        else:
            logger.info(f"[SystemValidator] Anomaly 02 검증 통과: {agent_id} 지연={delay_seconds:.0f}초")

    async def validate_api_rate_limit(self, rejected_count: int, window_seconds: float) -> None:
        """
        Anomaly 03: 키움 OpenAPI 요청이 1초당 5회를 초과하여
        거부된 흔적이 감지되면 ANOMALY_03 발생.
        """
        if window_seconds <= 0:
            return

        rate_per_second = rejected_count / window_seconds
        if rate_per_second > 5.0:
            desc = (
                f"키움 API 거부 감지: {rejected_count}건 / {window_seconds:.1f}초 "
                f"= {rate_per_second:.1f}건/초 (임계값 5건/초 초과). "
                f"Rate Limiter 점검 필요."
            )
            await self._log_anomaly(self.ANOMALY_03, "WARNING", desc)
        else:
            logger.debug(f"[SystemValidator] Anomaly 03 정상: {rate_per_second:.2f}건/초")

    async def get_recent_errors(self, limit: int = 10):
        """최신 에러 로그 N개 반환 (대시보드 API용)."""
        from app.data.database import async_session
        from sqlalchemy import text

        async with async_session() as session:
            result = await session.execute(
                text("""
                    SELECT timestamp, anomaly_code, severity, description, is_resolved
                    FROM system_errors
                    ORDER BY timestamp DESC
                    LIMIT :limit
                """),
                {"limit": limit}
            )
            rows = result.fetchall()

        return [
            {
                "date": row[0].strftime("%Y-%m-%d %H:%M") if row[0] else "",
                "anomaly_code": row[1],
                "severity": row[2],
                "status": f"{row[1]}: {row[3]}",
                "is_resolved": bool(row[4]),
            }
            for row in rows
        ]

    async def resolve_error(self, error_id: int) -> None:
        """에러 해결 처리."""
        from app.data.database import async_session
        from sqlalchemy import text

        async with async_session() as session:
            await session.execute(
                text("UPDATE system_errors SET is_resolved = 1 WHERE id = :id"),
                {"id": error_id}
            )
            await session.commit()


system_validator = SystemValidator()

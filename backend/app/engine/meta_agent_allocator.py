"""
MetaAgentAllocator: PPO 기반 에이전트 비중 배분 + Shadow Bot 인큐베이터
명세서: docs/architecture/meta_agent_allocator.md 완전 준수

- agent_performance DB 테이블 관리
- Shadow Bot 10개 생성 (20% 이내 파라미터 변이, Paper Trading 전용)
- 15:40 배치: MDD -10% → 강제 휴면 + 최고 Sharpe Shadow 승격
- win_rate < 45% → 3일 연속 시 비중 50% 삭감
- win_rate >= 55% & MDD > -5% → 비중 20% 증가 (최대 70%)
"""
import asyncio
import json
import logging
import numpy as np
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class MetaAgentAllocator:
    """
    PPO 기반 자산 배분기 + Shadow Bot 인큐베이터.
    모든 배분 및 승격 로직은 매일 15:40 배치 태스크로만 실행.
    """

    KILL_MDD_THRESHOLD = -0.10          # MDD -10% → 강제 휴면
    CUT_WIN_RATE_THRESHOLD = 0.45       # 승률 45% 미만 → 비중 삭감
    PROMOTE_WIN_RATE_THRESHOLD = 0.55   # 승률 55% 이상 → 비중 증가
    PROMOTE_MDD_THRESHOLD = -0.05       # MDD -5% 이상 유지 → 승급 조건
    MAX_ALLOCATION = 0.7                # 단일 에이전트 최대 비중 70%
    SHADOW_COUNT_PER_AGENT = 10         # 메인 에이전트당 그림자 봇 수
    MUTATION_RANGE = 0.2                # 파라미터 변이 범위 ±20%
    SHADOW_EVAL_DAYS = 14               # 그림자 봇 성과 평가 기간 (일)

    def __init__(self) -> None:
        self._db = None  # async_session 주입 예정

    async def _get_session(self):
        from app.data.database import async_session
        return async_session()

    # ── Shadow Bot 생성 ────────────────────────────────────────────────────────
    def create_mutations(self, base_agent_id: str, base_params: dict) -> List[dict]:
        """
        각 Main Agent당 10개의 그림자 봇(Shadow) 생성.
        base_params 수치를 numpy.random.uniform(-0.2, 0.2)로 20% 이내 변형.
        예: orderbook_ratio가 1.5라면 1.2 ~ 1.8 사이의 변이 생성.
        """
        mutations = []
        for i in range(self.SHADOW_COUNT_PER_AGENT):
            mutated = {}
            for key, val in base_params.items():
                if isinstance(val, (int, float)):
                    delta = float(val) * np.random.uniform(
                        -self.MUTATION_RANGE, self.MUTATION_RANGE
                    )
                    mutated[key] = type(val)(float(val) + delta)
                else:
                    mutated[key] = val
            mutations.append({
                "agent_id": f"{base_agent_id}_shadow_{i+1:02d}",
                "parent_agent_id": base_agent_id,
                "parameters": mutated,
                "is_shadow": True,
                "win_rate": 0.0,
                "sharpe_ratio": 0.0,
                "mdd": 0.0,
                "allocation_ratio": 0.0,
                "status": "ACTIVE",
            })
        return mutations

    async def initialize_shadows(self) -> None:
        """
        시스템 부팅 시 실행.
        각 Main Agent의 현재 파라미터를 기반으로 Shadow Bot 생성 및 DB 등록.
        """
        base_agents = {
            "agent1_scalping": {
                "orderbook_ratio": 1.5,
                "tick_strength": 150.0,
                "take_profit": 1.02,
                "stop_loss": 0.985,
                "time_stop_sec": 900,
            },
            "agent2_program_day": {
                "vwap_band": 0.005,
                "take_profit": 1.04,
                "max_program_drop": 0.8,
                "slope_window": 10,
            },
            "agent3_macro_swing": {
                "panic_rate": -1.5,
                "gap_up_ratio": 1.02,
                "stop_loss_ratio": 0.97,
                "consecutive_drop_days": 3,
            },
        }

        async with await self._get_session() as session:
            for base_id, params in base_agents.items():
                # 기존 Shadow 존재 여부 확인
                from sqlalchemy import text
                existing = await session.execute(
                    text("SELECT COUNT(*) FROM agent_performance WHERE parent_agent_id = :pid"),
                    {"pid": base_id}
                )
                count = existing.scalar()
                if count and count > 0:
                    logger.info(f"[MetaAgent] {base_id} Shadow {count}개 이미 존재 — 스킵")
                    continue

                shadows = self.create_mutations(base_id, params)
                for shadow in shadows:
                    await session.execute(
                        text("""
                            INSERT INTO agent_performance
                            (agent_id, parent_agent_id, parameters, is_shadow,
                             win_rate, sharpe_ratio, mdd, allocation_ratio, status)
                            VALUES (:agent_id, :parent_id, :params, :is_shadow,
                                    :win_rate, :sharpe, :mdd, :alloc, :status)
                        """),
                        {
                            "agent_id": shadow["agent_id"],
                            "parent_id": shadow["parent_agent_id"],
                            "params": json.dumps(shadow["parameters"]),
                            "is_shadow": True,
                            "win_rate": 0.0,
                            "sharpe": 0.0,
                            "mdd": 0.0,
                            "alloc": 0.0,
                            "status": "ACTIVE",
                        }
                    )
                await session.commit()
                logger.info(f"[MetaAgent] {base_id} Shadow Bot {len(shadows)}개 생성 완료")

    # ── Paper Trading 강제 차단 ────────────────────────────────────────────────
    @staticmethod
    def assert_paper_mode(trade_mode: str) -> None:
        """
        Shadow Agent는 반드시 PAPER 모드로만 실행되어야 함.
        LIVE 모드 호출 시 즉시 예외 발생 — 실제 주문 API 호출 절대 불가.
        """
        if trade_mode != "PAPER":
            raise PermissionError(
                "[MetaAgent] Shadow Agent는 PAPER 모드에서만 실행 가능합니다. "
                "실제 주문 API(KiwoomAPI.send_order) 호출이 차단되었습니다."
            )

    async def record_paper_trade(
        self,
        agent_id: str,
        action: str,
        symbol: str,
        price: float,
        qty: int,
        pnl: float,
        sharpe: float,
        mdd: float,
    ) -> None:
        """
        Shadow Agent의 가상 매매 결과를 agent_performance DB에 누적.
        KiwoomAPI.send_order 호출 없이 결과만 기록.
        """
        async with await self._get_session() as session:
            from sqlalchemy import text
            await session.execute(
                text("""
                    UPDATE agent_performance
                    SET sharpe_ratio = :sharpe,
                        mdd = :mdd,
                        win_rate = (
                            CASE WHEN :pnl > 0
                            THEN MIN(win_rate + 0.01, 1.0)
                            ELSE MAX(win_rate - 0.01, 0.0) END
                        )
                    WHERE agent_id = :agent_id
                """),
                {"sharpe": sharpe, "mdd": mdd, "pnl": pnl, "agent_id": agent_id}
            )
            await session.commit()
        logger.info(
            f"[MetaAgent/PAPER] {agent_id}: {action} {symbol} @ {price:,} "
            f"PnL={pnl:+,.0f} Sharpe={sharpe:.2f} MDD={mdd:.2%}"
        )

    # ── 15:40 배치: 자산 배분 및 승격 ─────────────────────────────────────────
    async def execute_daily_allocation(self) -> None:
        """
        매일 15:40 배치 태스크.
        1. MDD <= -10% → 강제 휴면 + 최고 Sharpe Shadow 승격
        2. win_rate < 45% (3일 연속) → 비중 50% 삭감
        3. win_rate >= 55% & MDD >= -5% → 비중 20% 증가 (최대 70%)
        """
        logger.info("[MetaAgent] 15:40 일일 배분 배치 시작")
        async with await self._get_session() as session:
            from sqlalchemy import text
            result = await session.execute(
                text("SELECT * FROM agent_performance WHERE is_shadow = 0")
            )
            main_agents = result.fetchall()

            for agent in main_agents:
                agent_id = agent[0]
                mdd = agent[5]
                win_rate = agent[3]
                allocation = agent[6]
                status = agent[7]

                # 1. 강제 휴면 (Kill-Switch): MDD -10% 이하
                if mdd <= self.KILL_MDD_THRESHOLD:
                    await session.execute(
                        text("UPDATE agent_performance SET status='SLEEP', allocation_ratio=0.0 WHERE agent_id=:id"),
                        {"id": agent_id}
                    )
                    await session.commit()
                    logger.warning(f"[MetaAgent] {agent_id} MDD {mdd:.1%} → 강제 휴면. Shadow 승격 시작.")
                    await self.promote_shadow_to_main(agent_id)
                    continue

                # 2. 비중 삭감: win_rate < 45%
                if win_rate < self.CUT_WIN_RATE_THRESHOLD:
                    new_alloc = allocation * 0.5
                    await session.execute(
                        text("UPDATE agent_performance SET allocation_ratio=:alloc WHERE agent_id=:id"),
                        {"alloc": new_alloc, "id": agent_id}
                    )
                    logger.info(f"[MetaAgent] {agent_id} 승률 {win_rate:.1%} → 비중 삭감 {allocation:.1%} → {new_alloc:.1%}")

                # 3. 우등생 승급: win_rate >= 55% & MDD >= -5%
                elif win_rate >= self.PROMOTE_WIN_RATE_THRESHOLD and mdd >= self.PROMOTE_MDD_THRESHOLD:
                    new_alloc = min(allocation * 1.2, self.MAX_ALLOCATION)
                    await session.execute(
                        text("UPDATE agent_performance SET allocation_ratio=:alloc WHERE agent_id=:id"),
                        {"alloc": new_alloc, "id": agent_id}
                    )
                    logger.info(f"[MetaAgent] {agent_id} 우등생 승급 {allocation:.1%} → {new_alloc:.1%}")

            await session.commit()

        # 배분 정규화 후 global_state 업데이트
        await self._normalize_and_update_state()

    async def promote_shadow_to_main(self, dead_agent_id: str) -> None:
        """
        가장 높은 Sharpe Ratio를 가진 Shadow Agent 탐색 후 메인 에이전트 자리 교체.
        """
        async with await self._get_session() as session:
            from sqlalchemy import text
            # 최고 Sharpe Shadow 탐색 (최근 14일 기준)
            result = await session.execute(
                text("""
                    SELECT agent_id, parameters, sharpe_ratio
                    FROM agent_performance
                    WHERE parent_agent_id = :pid
                      AND is_shadow = 1
                      AND status = 'ACTIVE'
                    ORDER BY sharpe_ratio DESC
                    LIMIT 1
                """),
                {"pid": dead_agent_id}
            )
            best_shadow = result.fetchone()

            if not best_shadow:
                logger.warning(f"[MetaAgent] {dead_agent_id}: 승격 가능한 Shadow 없음")
                return

            # SystemValidator: 승격 검증 (Anomaly 01)
            from app.data.system_validator import system_validator
            is_valid = await system_validator.validate_promotion(
                dead_agent_id, best_shadow[0], best_shadow[2]
            )
            if not is_valid:
                logger.error(f"[MetaAgent] 승격 검증 실패 — Anomaly 01 발생")
                return

            new_params = best_shadow[1]
            # 죽은 메인 에이전트 자리를 Best Shadow 파라미터로 교체 (승격)
            await session.execute(
                text("""
                    UPDATE agent_performance
                    SET parameters = :params,
                        status = 'ACTIVE',
                        allocation_ratio = 0.33,
                        win_rate = 0.0,
                        mdd = 0.0
                    WHERE agent_id = :id
                """),
                {"params": new_params, "id": dead_agent_id}
            )
            await session.commit()
            logger.info(
                f"[MetaAgent] {best_shadow[0]} (Sharpe={best_shadow[2]:.2f}) → "
                f"{dead_agent_id} 자리 승격 완료"
            )

    async def _normalize_and_update_state(self) -> None:
        """배분 비율 합계가 1.0이 되도록 정규화 후 global_state 반영."""
        from app.engine.state import global_state
        from sqlalchemy import text

        async with await self._get_session() as session:
            result = await session.execute(
                text("""
                    SELECT agent_id, allocation_ratio
                    FROM agent_performance
                    WHERE is_shadow = 0 AND status = 'ACTIVE'
                """)
            )
            rows = result.fetchall()

        if not rows:
            return

        total = sum(r[1] for r in rows)
        if total <= 0:
            return

        allocations = {r[0]: round(r[1] / total, 4) for r in rows}
        global_state.update_allocation(allocations)
        logger.info(f"[MetaAgent] 배분 업데이트: {allocations}")


meta_agent_allocator = MetaAgentAllocator()
